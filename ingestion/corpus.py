"""Zenodo research-corpus access: catalog, selection, and cached download.

The Phase 1 data source is Low et al.'s Reddit Mental Health Dataset
(Zenodo record 3941387, ODC-PDDL). Files are per-subreddit, per-period CSVs
named ``<subreddit>_<period>_features_tfidf_256.csv`` where period is one of
``2018 | 2019 | pre | post`` (pre = Dec 2018–Dec 2019, post = Jan–Apr 2020).

Downloads are cached in ``source.raw_dir`` and verified against the MD5
checksum published by the Zenodo API, so re-runs are cheap and a truncated
download can never be silently parsed.

Only the Python standard library is used for HTTP — no extra dependency.
"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ZENODO_API = "https://zenodo.org/api/records/{record_id}"
USER_AGENT = "MentalPulse/0.1 (research corpus loader; portfolio project)"
_CHUNK = 1 << 20  # 1 MiB


@dataclass(frozen=True)
class CorpusFile:
    """One downloadable file in the Zenodo record."""

    key: str          # e.g. "anxiety_post_features_tfidf_256.csv"
    url: str          # direct download link
    size: int         # bytes, per the API
    md5: str          # hex digest, per the API

    @property
    def subreddit(self) -> str:
        return self.key.split("_", 1)[0].lower()

    @property
    def period(self) -> str:
        return self.key.split("_")[1].lower()


def _request(url: str) -> urllib.request.Request:
    # Download URLs come from the Zenodo API response; refuse anything but
    # https so a compromised/mis-served response can't redirect urlopen to
    # file:// or another scheme.
    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-https corpus URL: {url!r}")
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def fetch_catalog(record_id: int) -> list[CorpusFile]:
    """Return the record's file list from the Zenodo API."""
    url = ZENODO_API.format(record_id=record_id)
    with urllib.request.urlopen(_request(url), timeout=60) as resp:
        record = json.load(resp)
    files = []
    for f in record.get("files", []):
        checksum = f.get("checksum", "")
        md5 = checksum.removeprefix("md5:")
        files.append(
            CorpusFile(key=f["key"], url=f["links"]["self"], size=f["size"], md5=md5)
        )
    if not files:
        raise RuntimeError(f"Zenodo record {record_id} lists no files")
    return files


def select_files(
    catalog: list[CorpusFile], subreddits: list[str], periods: list[str]
) -> list[CorpusFile]:
    """Pick the catalog entries for the configured subreddits and periods.

    Raises if any requested (subreddit, period) combination is missing, so a
    config typo fails loudly instead of silently ingesting fewer communities.
    """
    by_key = {(f.subreddit, f.period): f for f in catalog}
    wanted = [(s.lower(), p.lower()) for s in subreddits for p in periods]
    missing = [pair for pair in wanted if pair not in by_key]
    if missing:
        raise ValueError(
            f"Corpus has no file for: {missing}. Available subreddits: "
            f"{sorted({f.subreddit for f in catalog})}"
        )
    return [by_key[pair] for pair in wanted]


def _md5_of(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(file: CorpusFile, raw_dir: Path) -> Path:
    """Download one corpus file into ``raw_dir``, skipping verified cached copies.

    The file is written to a ``.part`` temp name and only moved into place
    after the MD5 matches, so an interrupted run never leaves a corrupt file
    that a later run would trust.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / file.key
    if dest.exists():
        if _md5_of(dest) == file.md5:
            logger.info("cached: %s", file.key)
            return dest
        logger.warning("checksum mismatch on cached %s — re-downloading", file.key)
        dest.unlink()

    part = dest.with_suffix(dest.suffix + ".part")
    logger.info("downloading %s (%.1f MB)", file.key, file.size / 1e6)
    with urllib.request.urlopen(_request(file.url), timeout=120) as resp, open(
        part, "wb"
    ) as out:
        while chunk := resp.read(_CHUNK):
            out.write(chunk)

    actual = _md5_of(part)
    if actual != file.md5:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {file.key}: expected {file.md5}, got {actual}"
        )
    part.replace(dest)
    return dest
