"""Run the local medallion pipeline: Bronze -> Silver -> Gold + verification.

This is the dev-box mirror of the Databricks notebooks (01–03). It reads the
Bronze parquet landed by ``ingestion/load_corpus.py``, applies the shared
transforms (``ingestion/transforms.py``), writes Silver and Gold parquet under
``data/``, and prints an anonymization verification report. It exits non-zero
if verification fails — a Silver layer with raw usernames is never written.

Run:
    python -m ingestion.load_corpus     # once: download corpus + land Bronze
    python -m ingestion.run_pipeline    # Bronze -> Silver -> Gold + verify
"""

from __future__ import annotations

import logging

from config.loader import load_config
from ingestion.load_corpus import read_bronze
from ingestion.transforms import (
    bronze_to_silver,
    gold_subreddit_weekly,
    silver_to_gold_posts,
)

logger = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config()
    cfg.secrets.require("hash_salt")

    bronze = read_bronze(cfg)
    print(f"Bronze:  {len(bronze):>9,} rows, "
          f"{bronze['author'].nunique():,} distinct raw authors")

    result = bronze_to_silver(bronze, salt=cfg.secrets.hash_salt)
    silver = result.frame

    silver_dir = cfg.path("silver")
    silver_dir.mkdir(parents=True, exist_ok=True)
    silver_path = silver_dir / "posts.parquet"
    silver.to_parquet(silver_path, index=False)
    print(f"Silver:  {len(silver):>9,} rows -> {silver_path}")
    for reason, count in result.dropped.items():
        print(f"         dropped {count:>7,}  ({reason})")

    gold_dir = cfg.path("gold")
    gold_dir.mkdir(parents=True, exist_ok=True)
    gold_posts = silver_to_gold_posts(silver)
    posts_path = gold_dir / "gold_posts_features.parquet"
    gold_posts.to_parquet(posts_path, index=False)
    weekly = gold_subreddit_weekly(gold_posts)
    weekly_path = gold_dir / "gold_subreddit_weekly.parquet"
    weekly.to_parquet(weekly_path, index=False)
    print(f"Gold:    {len(gold_posts):>9,} rows -> {posts_path}")
    print(f"Gold:    {len(weekly):>9,} rows -> {weekly_path}")

    # bronze_to_silver already ran assert_anonymized (it raises on failure);
    # restate the proof here so a pipeline run documents it visibly.
    print("\nAnonymization verification (enforced in bronze_to_silver):")
    print(f"  [ok] raw identifier columns dropped: author, author_fullname")
    print(f"  [ok] 0 of {len(result.raw_authors):,} raw authors appear in Silver")
    print(f"  [ok] 0 unscrubbed PII patterns (email/url/handle/mention/phone)")
    span = (silver["created_date"].min(), silver["created_date"].max())
    print(f"\nDate span: {span[0]:%Y-%m-%d} .. {span[1]:%Y-%m-%d}; "
          f"{weekly['week'].nunique()} distinct weeks; "
          f"{silver['subreddit'].nunique()} subreddits")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
