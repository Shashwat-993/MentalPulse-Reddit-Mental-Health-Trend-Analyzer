"""Research corpus -> Bronze parquet (the Phase 1 landing step).

Downloads the configured subset of the Reddit Mental Health Dataset (see
``ingestion/corpus.py``) and lands the RAW post fields as parquet under
``data/bronze/reddit_posts/`` — one parquet file per corpus CSV.

Bronze schema (raw, pre-anonymization — must never leave this machine):
    post_id       deterministic id: sha1(subreddit|author|date|post)[:16].
                  The corpus has no native id; deriving a stable one at landing
                  gives Silver a dedupe/join key without altering raw fields.
    subreddit     community name, as shipped (lowercase)
    author        RAW Reddit username, as shipped — hashed + dropped in Silver
    created_date  post date string as shipped (YYYY/MM/DD)
    post          raw post text (title + body concatenated by the corpus)
    period        corpus collection window (2018 | 2019 | pre | post)
    source_file   originating corpus CSV (lineage)
    ingested_at   UTC timestamp of this landing run

The corpus's ~346 precomputed feature columns (readability/LIWC/tf-idf) are
not landed (``source.keep_feature_columns: false``): Phase 2 derives its own
features, and the raw post text is sufficient to reproduce them.

Run:
    python -m ingestion.load_corpus            # download (cached) + land Bronze
    python -m ingestion.load_corpus --offline  # land from already-downloaded CSVs
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.loader import Config, load_config
from ingestion.corpus import CorpusFile, download, fetch_catalog, select_files

logger = logging.getLogger(__name__)

RAW_COLUMNS = ["subreddit", "author", "date", "post"]


def derive_post_id(subreddit, author, date, post) -> str:
    """Stable 16-hex-char id for one post (not secret — just a dedupe/join key)."""
    raw = f"{subreddit}|{author}|{date}|{post}".encode("utf-8", errors="replace")
    return hashlib.sha1(raw).hexdigest()[:16]


def parse_corpus_csv(path: Path, *, period: str) -> pd.DataFrame:
    """Parse one corpus CSV into the Bronze frame (raw fields only)."""
    df = pd.read_csv(path, usecols=RAW_COLUMNS, dtype=str)
    df = df.rename(columns={"date": "created_date"})
    df["post_id"] = [
        derive_post_id(s, a, d, p)
        for s, a, d, p in zip(
            df["subreddit"], df["author"], df["created_date"], df["post"]
        )
    ]
    df["period"] = period
    df["source_file"] = path.name
    df["ingested_at"] = datetime.now(timezone.utc)
    ordered = [
        "post_id",
        "subreddit",
        "author",
        "created_date",
        "post",
        "period",
        "source_file",
        "ingested_at",
    ]
    return df[ordered]


def _bronze_dir(cfg: Config) -> Path:
    return cfg.path("bronze") / "reddit_posts"


def load_to_bronze(cfg: Config, *, offline: bool = False) -> Path:
    """Download the configured corpus subset and land it as Bronze parquet.

    Returns the Bronze table directory. With ``offline=True`` no network is
    used; already-downloaded CSVs in ``source.raw_dir`` are (re-)landed.
    """
    raw_dir = (cfg.repo_root / cfg.source.raw_dir).resolve()
    subreddits = list(cfg.source.subreddits)
    periods = list(cfg.source.periods)

    if offline:
        csvs = []
        for sub in subreddits:
            for period in periods:
                path = raw_dir / f"{sub}_{period}_features_tfidf_256.csv"
                if not path.exists():
                    raise FileNotFoundError(
                        f"--offline: expected {path} (run once without --offline)"
                    )
                csvs.append((path, period))
    else:
        catalog = fetch_catalog(int(cfg.source.zenodo_record_id))
        selected: list[CorpusFile] = select_files(catalog, subreddits, periods)
        csvs = [(download(f, raw_dir), f.period) for f in selected]

    out_dir = _bronze_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for path, period in csvs:
        frame = parse_corpus_csv(path, period=period)
        dest = out_dir / f"{path.stem.removesuffix('_features_tfidf_256')}.parquet"
        frame.to_parquet(dest, index=False)
        total += len(frame)
        logger.info("bronze: %s -> %s (%d rows)", path.name, dest.name, len(frame))
    logger.info("bronze complete: %d rows across %d files", total, len(csvs))
    return out_dir


def read_bronze(cfg: Config) -> pd.DataFrame:
    """Read the full Bronze table (all landed parquet files) as one frame."""
    out_dir = _bronze_dir(cfg)
    files = sorted(out_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No Bronze parquet under {out_dir} — run `python -m ingestion.load_corpus`"
        )
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip download; land Bronze from CSVs already in source.raw_dir",
    )
    args = parser.parse_args()
    out = load_to_bronze(load_config(), offline=args.offline)
    print(f"Bronze parquet written under: {out}")
