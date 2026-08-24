"""Tests for the Firecrawl knowledge-corpus ingester.

No network: a fake transport stands in for Firecrawl's HTTP layer, so these
cover the allowlist, the credit-saving cache, graceful degradation, and the
chunking contract the Phase 3 retriever depends on.
"""
from __future__ import annotations

import json

import pytest

from ingestion import resources as res


def _payload(markdown: str, url: str = "https://www.nimh.nih.gov/health/topics/depression",
             title: str = "Depression") -> dict:
    return {
        "success": True,
        "data": {
            "markdown": markdown,
            "metadata": {"title": title, "sourceURL": url, "statusCode": 200},
        },
    }


def _prose(words: int = 120, token: str = "word") -> str:
    return " ".join(f"{token}{i}" for i in range(words))


class FakeClient(res.FirecrawlClient):
    """Firecrawl client with a scripted transport and a call counter."""

    def __init__(self, cache_dir, responses: dict, **kwargs):
        kwargs.setdefault("min_interval", 0.0)
        super().__init__(api_key="test-key", cache_dir=cache_dir, **kwargs)
        self.responses = responses
        self.calls: list[str] = []

    def _post(self, url: str) -> dict:
        self.calls.append(url)
        try:
            return self.responses[url]
        except KeyError:
            raise res.FirecrawlError(f"Firecrawl HTTP 404 for {url}") from None


# --- allowlist ---------------------------------------------------------------


def test_rejects_host_off_the_allowlist(tmp_path):
    client = FakeClient(tmp_path, {})
    with pytest.raises(ValueError, match="allowlist"):
        client.scrape("https://example.com/mental-health")
    assert client.calls == []  # refused before any request is made


def test_rejects_non_https(tmp_path):
    client = FakeClient(tmp_path, {})
    with pytest.raises(ValueError, match="non-https"):
        client.scrape("http://www.nimh.nih.gov/health/topics/depression")


# --- cache (credit frugality) ------------------------------------------------


def test_second_scrape_is_served_from_cache(tmp_path):
    url = "https://www.nimh.nih.gov/health/topics/depression"
    client = FakeClient(tmp_path, {url: _payload(_prose())})

    first = client.scrape(url)
    second = client.scrape(url)

    assert first == second
    assert client.calls == [url]        # only one live request
    assert client.credits_spent == 1    # a cache hit costs nothing


def test_refresh_bypasses_the_cache(tmp_path):
    url = "https://www.nimh.nih.gov/health/topics/depression"
    client = FakeClient(tmp_path, {url: _payload(_prose())})
    client.scrape(url)
    client.scrape(url, refresh=True)
    assert client.calls == [url, url]
    assert client.credits_spent == 2


def test_offline_client_serves_cache_and_refuses_misses(tmp_path):
    url = "https://www.nimh.nih.gov/health/topics/depression"
    FakeClient(tmp_path, {url: _payload(_prose())}).scrape(url)  # warm the cache

    offline = FakeClient(tmp_path, {}, offline=True)
    assert offline.scrape(url)["markdown"]
    assert offline.calls == []

    with pytest.raises(res.FirecrawlError, match="not cached"):
        offline.scrape("https://www.who.int/news-room/fact-sheets/detail/suicide")


def test_missing_api_key_implies_offline(tmp_path):
    client = res.FirecrawlClient(api_key=None, cache_dir=tmp_path)
    assert client.offline is True


def test_unsuccessful_response_is_not_cached(tmp_path):
    url = "https://www.nimh.nih.gov/health/topics/depression"
    client = FakeClient(tmp_path, {url: {"success": False, "error": "blocked"}})
    with pytest.raises(res.FirecrawlError, match="success=false"):
        client.scrape(url)
    assert not list(tmp_path.glob("*.json"))
    assert client.credits_spent == 0


# --- normalization -----------------------------------------------------------


def test_clean_markdown_strips_chrome_and_unwraps_links():
    raw = (
        "# Depression\n"
        "![banner](https://img.example/x.png)\n"
        "- [Home](https://www.nhs.uk/) [Conditions](https://www.nhs.uk/c/)\n"
        "\n\n\n"
        "See the [treatment guidance](https://www.nhs.uk/t/) for details.\n"
    )
    cleaned = res.clean_markdown(raw)
    assert "img.example" not in cleaned          # image dropped
    assert "[Home]" not in cleaned               # nav-only line dropped
    assert "treatment guidance for details" in cleaned  # link unwrapped in place
    assert "\n\n\n" not in cleaned               # blank runs collapsed


def test_thin_page_yields_no_document():
    assert res.to_document(_payload("Page not found.")["data"], "u", "t") is None


def test_document_handles_list_valued_title():
    data = _payload(_prose())["data"]
    data["metadata"]["title"] = ["Depression", "NIMH"]
    doc = res.to_document(data, "https://www.nimh.nih.gov/x", "depression")
    assert doc.title == "Depression"
    assert doc.source == "www.nimh.nih.gov"
    assert doc.n_words >= res._MIN_DOC_WORDS


# --- crawl orchestration -----------------------------------------------------


def test_crawl_reports_failures_without_raising(tmp_path):
    good = "https://www.nimh.nih.gov/health/topics/depression"
    moved = "https://www.who.int/news-room/fact-sheets/detail/suicide"
    off_list = "https://example.com/blog"
    client = FakeClient(tmp_path, {good: _payload(_prose())})

    docs, failures = res.crawl_sources(
        [
            {"url": good, "topic": "depression"},
            {"url": moved, "topic": "suicidewatch"},
            {"url": off_list, "topic": "general"},
        ],
        client,
    )

    assert [d.topic for d in docs] == ["depression"]
    assert {url for url, _ in failures} == {moved, off_list}


def test_crawl_deduplicates_syndicated_pages(tmp_path):
    a = "https://www.nimh.nih.gov/health/topics/depression"
    b = "https://www.nhs.uk/mental-health/conditions/depression/overview/"
    body = _prose()
    client = FakeClient(
        tmp_path, {a: _payload(body, url=a), b: _payload(body, url=b)}
    )
    docs, _ = res.crawl_sources(
        [{"url": a, "topic": "depression"}, {"url": b, "topic": "depression"}], client
    )
    assert len(docs) == 1  # identical content under two URLs indexes once


# --- chunking (the Phase 3 retrieval contract) -------------------------------


def _doc(text: str) -> res.ResourceDoc:
    return res.ResourceDoc(
        url="https://www.who.int/news-room/fact-sheets/detail/suicide",
        title="Suicide",
        source="www.who.int",
        topic="suicidewatch",
        text=text,
        retrieved_at="2026-08-24T00:00:00+00:00",
        content_hash="abc123",
    )


def test_chunks_overlap_and_keep_citation_metadata():
    doc = _doc("\n\n".join(_prose(100, f"p{i}_") for i in range(5)))
    chunks = res.chunk_documents([doc], chunk_words=220, overlap_words=40)

    assert len(chunks) > 1
    assert chunks["chunk_id"].is_unique
    # Every chunk can still be cited.
    assert (chunks["url"] == doc.url).all()
    assert (chunks["title"] == "Suicide").all()
    assert (chunks["retrieved_at"] == doc.retrieved_at).all()
    # The seam carries overlap_words forward, so a fact spanning a boundary
    # is retrievable from either side.
    first, second = chunks["text"].iloc[0].split(), chunks["text"].iloc[1].split()
    assert second[:40] == first[-40:]


def test_short_document_is_one_chunk():
    chunks = res.chunk_documents([_doc(_prose(50))], chunk_words=220)
    assert len(chunks) == 1
    assert chunks["chunk_index"].iloc[0] == 0


def test_empty_input_yields_typed_empty_frame():
    chunks = res.chunk_documents([])
    assert chunks.empty
    assert list(chunks.columns)[:3] == ["chunk_id", "text", "url"]


def test_overlap_must_be_smaller_than_chunk():
    with pytest.raises(ValueError, match="smaller"):
        res.chunk_documents([_doc(_prose())], chunk_words=50, overlap_words=50)


# --- config wiring -----------------------------------------------------------


def test_configured_seeds_are_all_on_the_allowlist():
    """The shipped seed list must never point off the allowlist."""
    from config.loader import load_config

    for seed in load_config().knowledge.sources:
        res._check_url(seed.url)


def test_write_corpus_roundtrips(tmp_path):
    import pandas as pd

    doc = _doc(_prose())
    chunks = res.chunk_documents([doc])
    paths = res.write_corpus([doc], chunks, tmp_path)
    assert pd.read_parquet(paths["documents"]).shape[0] == 1
    assert len(pd.read_parquet(paths["chunks"])) == len(chunks)


def test_failed_build_does_not_clobber_the_previous_corpus(tmp_path, monkeypatch):
    """A refresh that scrapes nothing must leave the last good corpus intact."""
    from config.loader import load_config

    out_dir, cache_dir = tmp_path / "out", tmp_path / "cache"
    out_dir.mkdir()
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "project: {name: test, environment: dev}\n"
        "knowledge:\n"
        f"  cache_dir: {cache_dir}\n"
        f"  out_dir: {out_dir}\n"
        "  chunk_words: 220\n"
        "  overlap_words: 40\n"
        "  sources:\n"
        "    - url: https://www.who.int/news-room/fact-sheets/detail/suicide\n"
        "      topic: suicidewatch\n"
    )
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    previous = out_dir / "resource_docs.parquet"
    previous.write_bytes(b"previous good corpus")

    report = res.build(load_config(cfg_file), offline=True)

    assert report["documents"] == 0
    assert len(report["failures"]) == 1
    assert report["paths"] == {}
    assert previous.read_bytes() == b"previous good corpus"


def test_cache_file_is_valid_json(tmp_path):
    url = "https://www.nimh.nih.gov/health/topics/depression"
    FakeClient(tmp_path, {url: _payload(_prose())}).scrape(url)
    cached = next(tmp_path.glob("*.json"))
    assert "markdown" in json.loads(cached.read_text(encoding="utf-8"))
