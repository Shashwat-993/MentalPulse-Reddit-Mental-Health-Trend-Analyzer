"""Fetch posts + top-level comments for the configured subreddits -> Bronze parquet.

Implemented in Phase 1. For each subreddit it pulls the configured listings
(top + new) over a configurable time window, plus top-level comments, and lands
the RAW output as parquet under ``data/bronze/``.

Captured per post (Bronze, pre-anonymization):
    post_id, subreddit, created_utc, score, num_comments, title, body,
    author_ref (RAW author id — to be hashed/dropped in Bronze->Silver)

Anonymization happens in the Bronze->Silver step (see ``anonymize.py`` and
``databricks/02_silver_clean.py``). Raw usernames MUST NOT survive into Silver.
"""

from __future__ import annotations

from pathlib import Path

from config.loader import Config


def fetch_to_bronze(cfg: Config) -> Path:
    """Fetch configured subreddits and write Bronze parquet. Returns the output dir.

    Implemented in Phase 1.
    """
    raise NotImplementedError("Implemented in Phase 1.")


if __name__ == "__main__":
    # TODO(Phase 1): from config.loader import load_config; fetch_to_bronze(load_config())
    raise SystemExit("fetch_posts is implemented in Phase 1.")
