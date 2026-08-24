"""Firecrawl-backed knowledge corpus: authoritative guidance for RAG grounding.

Why this exists
---------------
Phase 3's agent needs something to retrieve over. The obvious candidate — the
Reddit post text itself — is exactly what this project refuses to surface: the
guardrail (``rag/prompts.py``) answers with aggregate, anonymized cohort trends
and never quotes or attributes an individual post. Indexing the posts would put
the agent one prompt away from violating its own responsible-use stance, and
every citation would be a quote from a person in distress.

So we retrieve over the *literature* instead. This module scrapes a small,
allowlisted set of public clinical/public-health pages (NIMH, NHS, WHO, CDC,
988 Lifeline) into a citable document corpus. The agent then answers with:

  * **numbers** from Gold — the SQL metric tool (what our data says), and
  * **context** from this corpus — the retrieval tool (what health bodies say
    about the condition), each with a real source URL and retrieval date.

Design notes
------------
* **Allowlist, not open crawl.** ``ALLOWED_HOSTS`` is a closed set of public
  health institutions. A seed pointing anywhere else is refused before any
  request is made — this is a citation corpus, not a web scraper.
* **Cache-first.** Every response is cached by URL hash under
  ``knowledge.cache_dir``. Re-runs cost **zero** Firecrawl credits, and
  ``offline=True`` (or a missing API key) serves the cache alone, so a fresh
  clone with a warm cache needs no key at all.
* **Non-fatal per-URL failure.** A moved or 404'd page is reported, not raised —
  one stale seed can't fail the whole build.
* Standard library HTTP only, matching ``ingestion/corpus.py`` — no new pin.

Firecrawl's free tier is 1,000 credits/month (1 credit = 1 page, no card), and
the seed list is ~20 pages, so a full refresh costs ~2% of a free month.

Usage
-----
    python -m ingestion.resources              # scrape (cache-first) + write
    python -m ingestion.resources --offline    # cache only, zero credits
    python -m ingestion.resources --refresh    # force re-scrape (spends credits)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from config.loader import Config, load_config

logger = logging.getLogger(__name__)

FIRECRAWL_API = "https://api.firecrawl.dev/v2/scrape"
USER_AGENT = "MentalPulse/0.1 (portfolio research project; knowledge corpus)"

# Closed allowlist of public health / clinical authorities. Anything else is
# refused — see the module docstring. Add a host here only if it is a public,
# citable, non-paywalled health authority.
ALLOWED_HOSTS = frozenset(
    {
        "www.nimh.nih.gov",
        "nimh.nih.gov",
        "www.nhs.uk",
        "www.who.int",
        "www.cdc.gov",
        "988lifeline.org",
        "www.samhsa.gov",
        "www.mind.org.uk",
    }
)

# Firecrawl free tier: 2 concurrent requests and "low rate limits", so requests
# are serialized with a small gap rather than fired in parallel.
MIN_REQUEST_INTERVAL = 2.0

_MIN_DOC_WORDS = 80  # below this a "page" is a nav stub or an error page


class FirecrawlError(RuntimeError):
    """A Firecrawl request failed, or a page was requested that isn't cached."""


@dataclass(frozen=True)
class ResourceDoc:
    """One scraped guidance page, normalized for retrieval and citation."""

    url: str
    title: str
    source: str        # hostname — the citable publisher
    topic: str         # maps the doc to a community/theme (e.g. "depression")
    text: str          # cleaned markdown
    retrieved_at: str  # ISO-8601 UTC — citations state when we fetched it
    content_hash: str  # sha256 of text; changes only when the page changes

    @property
    def n_words(self) -> int:
        return len(self.text.split())


def _check_url(url: str) -> str:
    """Return ``url`` if it is https and on the allowlist, else raise."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Refusing non-https knowledge URL: {url!r}")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(
            f"Host {parsed.hostname!r} is not on the knowledge-source allowlist. "
            f"Allowed: {sorted(ALLOWED_HOSTS)}"
        )
    return url


def _cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]}.json"


class FirecrawlClient:
    """Cache-first Firecrawl v2 ``/scrape`` client (stdlib HTTP).

    Parameters
    ----------
    api_key:
        Firecrawl key. ``None`` is allowed — the client then serves cached
        pages only and raises :class:`FirecrawlError` on a cache miss.
    offline:
        Force cache-only even when a key is present (proves zero-credit reruns).
    """

    def __init__(
        self,
        api_key: str | None,
        cache_dir: Path,
        *,
        offline: bool = False,
        timeout: int = 120,
        min_interval: float = MIN_REQUEST_INTERVAL,
        api_url: str = FIRECRAWL_API,
    ) -> None:
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.offline = offline or not api_key
        self.timeout = timeout
        self.min_interval = min_interval
        self.api_url = api_url
        self._last_request = 0.0
        self.credits_spent = 0  # live scrapes this run; cache hits cost nothing

    # -- transport (overridden in tests) -------------------------------------
    def _post(self, url: str) -> dict:
        """POST one scrape request and return the parsed JSON body."""
        body = json.dumps(
            {"url": url, "formats": ["markdown"], "onlyMainContent": True}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise FirecrawlError(f"Firecrawl HTTP {exc.code} for {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise FirecrawlError(f"Firecrawl request failed for {url}: {exc.reason}") from exc
        finally:
            self._last_request = time.monotonic()
        return payload

    def scrape(self, url: str, *, refresh: bool = False) -> dict:
        """Return the Firecrawl ``data`` payload for ``url``, cache-first."""
        _check_url(url)
        cached = _cache_path(self.cache_dir, url)
        if cached.exists() and not refresh:
            with open(cached, "r", encoding="utf-8") as fh:
                return json.load(fh)
        if self.offline:
            raise FirecrawlError(
                "not cached, and no Firecrawl API key is available — set "
                "FIRECRAWL_API_KEY in .env to fetch it (free tier: firecrawl.dev)"
            )

        payload = self._post(url)
        if not payload.get("success", False):
            raise FirecrawlError(f"Firecrawl returned success=false for {url}")
        data = payload.get("data") or {}
        if not data.get("markdown"):
            raise FirecrawlError(f"Firecrawl returned no markdown for {url}")

        self.credits_spent += 1
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".part")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        tmp.replace(cached)
        return data


# --- normalization -----------------------------------------------------------

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_NAV_LINE = re.compile(r"^\s*(?:[-*+]\s*)?(?:\[[^\]]*\]\([^)]*\)\s*)+$")
_BLANKS = re.compile(r"\n{3,}")


def clean_markdown(markdown: str) -> str:
    """Strip scaffolding Firecrawl's ``onlyMainContent`` still leaves behind.

    Removes image embeds and link-only lines (breadcrumbs, "related pages"
    rails), unwraps inline links to their anchor text, and collapses blank
    runs — so an embedding sees prose, not navigation.
    """
    kept = []
    for line in (markdown or "").splitlines():
        stripped = _IMAGE.sub("", line).strip()
        if not stripped:
            kept.append("")
            continue
        if _NAV_LINE.match(stripped):
            continue
        kept.append(_LINK.sub(r"\1", stripped))
    return _BLANKS.sub("\n\n", "\n".join(kept)).strip()


def to_document(data: dict, url: str, topic: str) -> ResourceDoc | None:
    """Build a :class:`ResourceDoc` from a Firecrawl payload.

    Returns ``None`` when the page yields too little prose to be worth
    embedding (an error page, a redirect stub, a nav-only shell).
    """
    text = clean_markdown(data.get("markdown", ""))
    if len(text.split()) < _MIN_DOC_WORDS:
        return None
    metadata = data.get("metadata") or {}
    title = metadata.get("title") or url.rstrip("/").rsplit("/", 1)[-1]
    if isinstance(title, list):  # Firecrawl documents metadata as str | list[str]
        title = title[0] if title else url
    source_url = metadata.get("sourceURL") or metadata.get("url") or url
    return ResourceDoc(
        url=source_url,
        title=str(title).strip(),
        source=urlparse(source_url).hostname or "",
        topic=topic,
        text=text,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    )


def crawl_sources(
    seeds: list[dict],
    client: FirecrawlClient,
    *,
    refresh: bool = False,
) -> tuple[list[ResourceDoc], list[tuple[str, str]]]:
    """Scrape every seed. Returns ``(documents, failures)``.

    Failures are ``(url, reason)`` pairs — a moved or thin page is reported and
    skipped, never raised, so one stale seed cannot fail the corpus build.
    Documents are de-duplicated on ``content_hash`` (health bodies syndicate the
    same page under several URLs).
    """
    documents: list[ResourceDoc] = []
    failures: list[tuple[str, str]] = []
    seen: set[str] = set()

    for seed in seeds:
        url, topic = seed["url"], seed.get("topic", "general")
        try:
            data = client.scrape(url, refresh=refresh)
        except (FirecrawlError, ValueError) as exc:
            logger.warning("skipping %s: %s", url, exc)
            failures.append((url, str(exc)))
            continue

        doc = to_document(data, url, topic)
        if doc is None:
            failures.append((url, "too little prose after cleaning"))
            continue
        if doc.content_hash in seen:
            logger.info("duplicate content, skipping: %s", url)
            continue
        seen.add(doc.content_hash)
        documents.append(doc)

    return documents, failures


# --- chunking (what the Phase 3 LanceDB index actually embeds) ----------------


def chunk_documents(
    documents: list[ResourceDoc],
    chunk_words: int = 220,
    overlap_words: int = 40,
) -> pd.DataFrame:
    """Split documents into overlapping, paragraph-aligned retrieval chunks.

    Chunks are packed on paragraph boundaries so a chunk rarely starts
    mid-sentence, with ``overlap_words`` carried across the seam so a fact
    spanning a boundary is still retrievable. Every chunk keeps its source URL,
    title, and retrieval date — the agent cites those, so they must survive
    chunking.
    """
    if overlap_words >= chunk_words:
        raise ValueError("overlap_words must be smaller than chunk_words")

    rows = []
    for doc in documents:
        paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]
        buffer: list[str] = []
        index = 0

        def flush(buf: list[str]) -> list[str]:
            """Emit ``buf`` as a chunk; return the overlap tail for the next one."""
            nonlocal index
            if not buf:
                return []
            rows.append(
                {
                    "chunk_id": f"{doc.content_hash}-{index:03d}",
                    "text": "\n\n".join(buf),
                    "url": doc.url,
                    "title": doc.title,
                    "source": doc.source,
                    "topic": doc.topic,
                    "retrieved_at": doc.retrieved_at,
                    "chunk_index": index,
                }
            )
            index += 1
            tail = " ".join(buf).split()[-overlap_words:]
            return [" ".join(tail)] if overlap_words else []

        for paragraph in paragraphs:
            pending = len(" ".join(buffer).split()) + len(paragraph.split())
            if buffer and pending > chunk_words:
                buffer = flush(buffer)
            buffer.append(paragraph)
        flush(buffer)

    return pd.DataFrame(
        rows,
        columns=[
            "chunk_id",
            "text",
            "url",
            "title",
            "source",
            "topic",
            "retrieved_at",
            "chunk_index",
        ],
    )


def write_corpus(
    documents: list[ResourceDoc], chunks: pd.DataFrame, out_dir: Path
) -> dict[str, Path]:
    """Write documents + chunks to parquet under ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = out_dir / "resource_docs.parquet"
    chunk_path = out_dir / "resource_chunks.parquet"
    pd.DataFrame([asdict(d) for d in documents]).to_parquet(doc_path, index=False)
    chunks.to_parquet(chunk_path, index=False)
    return {"documents": doc_path, "chunks": chunk_path}


def build(cfg: Config, *, offline: bool = False, refresh: bool = False) -> dict:
    """Run the full knowledge-corpus build and return a verification report."""
    knowledge = cfg.knowledge
    seeds = [
        {"url": s.url, "topic": getattr(s, "topic", "general")}
        for s in knowledge.sources
    ]
    client = FirecrawlClient(
        api_key=cfg.secrets.firecrawl_api_key,
        cache_dir=(cfg.repo_root / knowledge.cache_dir).resolve(),
        offline=offline,
    )
    documents, failures = crawl_sources(seeds, client, refresh=refresh)
    chunks = chunk_documents(
        documents,
        chunk_words=knowledge.chunk_words,
        overlap_words=knowledge.overlap_words,
    )
    # Never overwrite a good corpus with an empty one — a failed refresh
    # (expired key, every seed moved) must leave the last build intact.
    paths = (
        write_corpus(documents, chunks, (cfg.repo_root / knowledge.out_dir).resolve())
        if documents
        else {}
    )
    return {
        "seeds": len(seeds),
        "documents": len(documents),
        "chunks": len(chunks),
        "words": sum(d.n_words for d in documents),
        "sources": sorted({d.source for d in documents}),
        "topics": sorted({d.topic for d in documents}),
        "credits_spent": client.credits_spent,
        "failures": failures,
        "paths": {k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--offline",
        action="store_true",
        help="serve cached pages only — never calls Firecrawl (zero credits)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-scrape every seed even if cached (spends one credit per page)",
    )
    parser.add_argument("--config", default=None, help="path to config.yaml")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config(args.config)
    report = build(cfg, offline=args.offline, refresh=args.refresh)

    print("\n=== Knowledge corpus ===")
    print(f"seeds:      {report['seeds']}")
    print(f"documents:  {report['documents']}")
    print(f"chunks:     {report['chunks']}")
    print(f"words:      {report['words']:,}")
    print(f"sources:    {', '.join(report['sources'])}")
    print(f"topics:     {', '.join(report['topics'])}")
    print(f"credits:    {report['credits_spent']} spent this run")
    for url, reason in report["failures"]:
        print(f"  ! skipped {url}: {reason}")
    if not report["documents"]:
        # A corpus with no documents is a failed build, not an empty success.
        print("\nNo documents built — the previous corpus (if any) was left intact.")
        return 1
    print(f"documents -> {report['paths']['documents']}")
    print(f"chunks    -> {report['paths']['chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
