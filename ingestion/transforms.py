"""Medallion transforms: Bronze -> Silver -> Gold, as pure pandas functions.

These are the single source of truth for the transform logic. The local
pipeline (``ingestion/run_pipeline.py``) calls them directly; the Databricks
notebooks (``databricks/02_silver_clean.py``, ``03_gold_features.py``) and the
dbt models (``dbt/mentalpulse/models/``) re-express the same rules in
PySpark/SQL and must be kept in sync with what is documented here and in
``docs/data_model.md``.

Layer contracts:
  Silver (clean, de-identified posts — first shareable layer):
    post_id, subreddit, created_date, author_hash, text,
    period, source_file, ingested_at
  Gold ``gold_posts_features`` (per-post features; model scores in Phase 2):
    post_id, subreddit, created_date, week, author_hash, n_chars, n_words,
    sentiment_score, sentiment_label, crisis_score, crisis_flag
  Gold ``gold_subreddit_weekly`` (aggregate trends; the dashboard's table):
    subreddit, week, n_posts, n_active_authors, avg_word_count,
    sentiment, crisis_count, crisis_rate
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from ingestion.anonymize import anonymize_frame, assert_anonymized

# Reddit placeholder bodies for removed content, as shipped by the corpus.
DELETED_MARKERS = {"[deleted]", "[removed]"}

_WHITESPACE = re.compile(r"\s+")


@dataclass
class SilverResult:
    """Silver frame plus the audit trail of what was dropped and why."""

    frame: pd.DataFrame
    dropped: dict[str, int] = field(default_factory=dict)
    raw_authors: set[str] = field(default_factory=set)


def _normalize_text(value: str | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return _WHITESPACE.sub(" ", str(value)).strip()


def bronze_to_silver(bronze: pd.DataFrame, *, salt: str) -> SilverResult:
    """Clean + de-identify Bronze posts into the Silver contract.

    Rules (mirrored in the Databricks notebook and dbt model):
      1. drop rows with missing/empty/[deleted]/[removed] post text;
      2. normalize whitespace in text;
      3. anonymize: salted-hash author -> ``author_hash``, drop raw identifier
         columns, scrub PII patterns from text (``ingestion/anonymize.py``);
      4. parse ``created_date`` (YYYY/MM/DD) to a datetime; drop unparseable;
      5. dedupe by ``post_id`` (corpus periods can overlap), keeping the
         earliest period alphabetically for determinism.

    The verification (zero raw usernames in Silver) runs here on every call —
    a Silver frame that fails :func:`assert_anonymized` is never returned.
    """
    dropped: dict[str, int] = {}
    df = bronze.copy()

    raw_authors = {str(a) for a in df["author"].dropna().unique()}

    text = df["post"].map(_normalize_text)
    bad_text = text.isna() | (text == "") | text.isin(DELETED_MARKERS)
    dropped["empty_or_deleted_text"] = int(bad_text.sum())
    df = df.loc[~bad_text].copy()
    df["post"] = text.loc[~bad_text]

    df = anonymize_frame(df, salt=salt, text_columns=("post",))
    df = df.rename(columns={"post": "text"})

    parsed = pd.to_datetime(df["created_date"], format="%Y/%m/%d", errors="coerce")
    dropped["unparseable_date"] = int(parsed.isna().sum())
    df["created_date"] = parsed
    df = df.loc[parsed.notna()]

    before = len(df)
    # created_date breaks residual ties deterministically (mirrors the dbt
    # model); rows tied on all three are byte-identical since post_id is
    # content-derived.
    df = df.sort_values(["post_id", "period", "source_file", "created_date"]).drop_duplicates(
        subset="post_id", keep="first"
    )
    dropped["duplicate_post_id"] = before - len(df)

    ordered = [
        "post_id",
        "subreddit",
        "created_date",
        "author_hash",
        "text",
        "period",
        "source_file",
        "ingested_at",
    ]
    silver = df[ordered].reset_index(drop=True)

    assert_anonymized(silver, raw_authors=raw_authors, text_columns=("text",))
    return SilverResult(frame=silver, dropped=dropped, raw_authors=raw_authors)


def silver_to_gold_posts(silver: pd.DataFrame) -> pd.DataFrame:
    """Per-post feature table. Model-score columns are typed placeholders that
    Phase 2 backfills (kept nullable so "not scored yet" is distinguishable
    from a real score)."""
    gold = silver[
        ["post_id", "subreddit", "created_date", "author_hash"]
    ].copy()
    gold["week"] = silver["created_date"].dt.to_period("W-SUN").dt.start_time
    gold["n_chars"] = silver["text"].str.len().astype("int64")
    gold["n_words"] = silver["text"].str.split().str.len().astype("int64")
    gold["sentiment_score"] = pd.Series(pd.NA, index=gold.index, dtype="Float64")
    gold["sentiment_label"] = pd.Series(pd.NA, index=gold.index, dtype="string")
    gold["crisis_score"] = pd.Series(pd.NA, index=gold.index, dtype="Float64")
    gold["crisis_flag"] = pd.Series(pd.NA, index=gold.index, dtype="boolean")
    return gold


def gold_subreddit_weekly(gold_posts: pd.DataFrame) -> pd.DataFrame:
    """Weekly aggregates per subreddit — the dashboard's trend table.

    ``sentiment``/``crisis_*`` stay NA (not 0) until Phase 2 scores exist, so
    downstream consumers can tell "no signal yet" from "signal is zero".
    """
    weekly = (
        gold_posts.groupby(["subreddit", "week"], as_index=False)
        .agg(
            n_posts=("post_id", "count"),
            n_active_authors=("author_hash", "nunique"),
            avg_word_count=("n_words", "mean"),
            sentiment=("sentiment_score", "mean"),
            crisis_count=("crisis_flag", lambda s: s.sum(min_count=1)),
        )
        .sort_values(["subreddit", "week"])
        .reset_index(drop=True)
    )
    weekly["avg_word_count"] = weekly["avg_word_count"].round(2)
    weekly["crisis_count"] = weekly["crisis_count"].astype("Int64")
    weekly["crisis_rate"] = (weekly["crisis_count"] / weekly["n_posts"]).astype(
        "Float64"
    )
    return weekly
