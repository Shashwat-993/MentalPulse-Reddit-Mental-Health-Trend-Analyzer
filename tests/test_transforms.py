"""Tests for the Bronze->Silver->Gold transforms on synthetic data.

The end-to-end anonymization proof (test_no_raw_username_survives_end_to_end)
is the executable form of the Phase 1 acceptance criterion "zero raw usernames
in Silver (proven)".
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.transforms import (
    bronze_to_silver,
    gold_subreddit_weekly,
    silver_to_gold_posts,
)

SALT = "test-salt-not-secret"
RAW_AUTHORS = ["jane_doe", "john_roe", "third_user"]


def make_bronze() -> pd.DataFrame:
    """Synthetic Bronze mirroring the corpus loader's output, with dirt:
    a duplicate post_id, [deleted]/empty text, a bad date, and PII in text."""
    now = datetime.now(timezone.utc)
    rows = [
        # clean posts
        ("p1", "anxiety", "jane_doe", "2019/01/07", "Feeling  better\nthis week", "pre"),
        ("p2", "anxiety", "john_roe", "2019/01/08", "Contact a@b.com or u/jane_doe", "pre"),
        ("p3", "depression", "third_user", "2020/02/03", "Long   day. www.example.com", "post"),
        # duplicate of p1 (overlapping corpus periods)
        ("p1", "anxiety", "jane_doe", "2019/01/07", "Feeling  better\nthis week", "2019"),
        # droppable rows
        ("p4", "anxiety", "jane_doe", "2019/01/09", "[deleted]", "pre"),
        ("p5", "anxiety", "jane_doe", "2019/01/09", "   ", "pre"),
        ("p6", "anxiety", "jane_doe", "not-a-date", "valid text here", "pre"),
    ]
    return pd.DataFrame(
        [
            {
                "post_id": pid,
                "subreddit": sub,
                "author": author,
                "created_date": date,
                "post": text,
                "period": period,
                "source_file": f"{sub}_{period}.csv",
                "ingested_at": now,
            }
            for pid, sub, author, date, text, period in rows
        ]
    )


@pytest.fixture()
def silver_result():
    return bronze_to_silver(make_bronze(), salt=SALT)


# --- Silver -----------------------------------------------------------------


def test_silver_schema_and_rows(silver_result):
    silver = silver_result.frame
    assert list(silver.columns) == [
        "post_id",
        "subreddit",
        "created_date",
        "author_hash",
        "text",
        "period",
        "source_file",
        "ingested_at",
    ]
    assert set(silver["post_id"]) == {"p1", "p2", "p3"}


def test_silver_drop_accounting(silver_result):
    assert silver_result.dropped == {
        "empty_or_deleted_text": 2,
        "unparseable_date": 1,
        "duplicate_post_id": 1,
    }


def test_silver_dedupe_prefers_earliest_period(silver_result):
    p1 = silver_result.frame.set_index("post_id").loc["p1"]
    assert p1["period"] == "2019"  # "2019" < "pre" alphabetically — deterministic


def test_silver_normalizes_whitespace(silver_result):
    p1 = silver_result.frame.set_index("post_id").loc["p1"]
    assert p1["text"] == "Feeling better this week"


def test_silver_dates_are_datetimes(silver_result):
    assert pd.api.types.is_datetime64_any_dtype(silver_result.frame["created_date"])


def test_no_raw_username_survives_end_to_end(silver_result):
    """Phase 1 acceptance: zero raw usernames in Silver, proven."""
    silver = silver_result.frame
    assert silver_result.raw_authors == set(RAW_AUTHORS)
    assert "author" not in silver.columns
    blob = silver.drop(columns="ingested_at").to_csv(index=False)
    for author in RAW_AUTHORS:
        assert author not in blob, f"raw username {author!r} leaked into Silver"
    # and the PII inside post text was scrubbed too
    assert "a@b.com" not in blob
    assert "www.example.com" not in blob


# --- Gold ---------------------------------------------------------------------


def test_gold_posts_features(silver_result):
    gold = silver_to_gold_posts(silver_result.frame)
    row = gold.set_index("post_id").loc["p1"]
    assert row["n_words"] == 4
    assert row["n_chars"] == len("Feeling better this week")
    assert row["week"].weekday() == 0  # weeks start on Monday
    # model-score placeholders exist, typed, and are NA until Phase 2
    for col in ("sentiment_score", "sentiment_label", "crisis_score", "crisis_flag"):
        assert gold[col].isna().all()


def test_gold_weekly_aggregates(silver_result):
    weekly = gold_subreddit_weekly(silver_to_gold_posts(silver_result.frame))
    assert list(weekly.columns) == [
        "subreddit",
        "week",
        "n_posts",
        "n_active_authors",
        "avg_word_count",
        "sentiment",
        "crisis_count",
        "crisis_rate",
    ]
    anxiety = weekly[weekly["subreddit"] == "anxiety"]
    assert int(anxiety["n_posts"].sum()) == 2
    assert int(anxiety["n_active_authors"].iloc[0]) == 2
    # unscored signals must be NA — "no signal yet", not "signal is zero"
    assert weekly["sentiment"].isna().all()
    assert weekly["crisis_count"].isna().all()
    assert weekly["crisis_rate"].isna().all()
