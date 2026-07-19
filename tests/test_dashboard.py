"""Tests for the dashboard data layer and the preview guardrail.

These are pure-pandas / pure-logic tests — no Streamlit runtime required.
"""
from __future__ import annotations

import pandas as pd
import pytest

from config.loader import load_config
from rag.prompts import REFUSAL_MESSAGE
from dashboard import data as dataio
from dashboard.mock_data import build_weekly_aggregates

SUBS = ["mentalhealth", "Anxiety", "depression"]


# --- mock data ---------------------------------------------------------------


def test_mock_is_deterministic():
    assert build_weekly_aggregates(SUBS).equals(build_weekly_aggregates(SUBS))


def test_mock_series_independent_of_list_order():
    a = build_weekly_aggregates(["Anxiety", "depression"])
    b = build_weekly_aggregates(["depression", "Anxiety"])
    ax = a[a["subreddit"] == "Anxiety"].reset_index(drop=True)
    bx = b[b["subreddit"] == "Anxiety"].reset_index(drop=True)
    assert ax.equals(bx)


def test_mock_schema_and_bounds():
    df = build_weekly_aggregates(SUBS, n_weeks=10)
    assert list(df.columns) == [
        "week",
        "subreddit",
        "n_posts",
        "sentiment",
        "crisis_rate",
        "crisis_count",
    ]
    assert len(df) == len(SUBS) * 10
    assert df["sentiment"].between(-1, 1).all()
    assert df["crisis_rate"].between(0, 1).all()
    assert (df["n_posts"] >= 50).all()


def test_mock_empty_subreddits():
    df = build_weekly_aggregates([])
    assert df.empty
    assert list(df.columns)[:2] == ["week", "subreddit"]


# --- aggregate helpers -------------------------------------------------------


def test_kpis():
    k = dataio.kpis(build_weekly_aggregates(SUBS))
    assert k["communities"] == len(SUBS)
    assert k["total_posts"] > 0
    assert -1 <= k["avg_sentiment"] <= 1
    assert 0 <= k["crisis_share"] <= 1


def test_kpis_empty():
    empty = build_weekly_aggregates([])
    assert dataio.kpis(empty) == {
        "communities": 0,
        "total_posts": 0,
        "avg_sentiment": 0.0,
        "crisis_share": 0.0,
    }


def test_community_overview_no_nan_on_zero_posts():
    df = pd.DataFrame(
        [
            {"week": pd.Timestamp("2024-01-07"), "subreddit": "x", "n_posts": 0,
             "sentiment": 0.0, "crisis_rate": 0.0, "crisis_count": 0},
            {"week": pd.Timestamp("2024-01-07"), "subreddit": "y", "n_posts": 100,
             "sentiment": -0.1, "crisis_rate": 0.05, "crisis_count": 5},
        ]
    )
    overview = dataio.community_overview(df)
    assert not overview["crisis_share"].isna().any()
    assert overview.loc[overview["subreddit"] == "x", "crisis_share"].iloc[0] == 0.0


def test_pivots_have_a_column_per_community():
    df = build_weekly_aggregates(SUBS)
    assert dataio.sentiment_pivot(df).shape[1] == len(SUBS)
    assert dataio.crisis_volume_pivot(df).shape[1] == len(SUBS)


# --- data source -------------------------------------------------------------


def _tmp_cfg(tmp_path):
    """A Config whose data paths point into tmp_path (absolute paths win when
    joined onto the repo root)."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "project: {name: test, environment: dev}\n"
        f"source: {{subreddits: [anxiety, depression]}}\n"
        "paths:\n"
        f"  bronze: {tmp_path / 'bronze'}\n"
        f"  silver: {tmp_path / 'silver'}\n"
        f"  gold: {tmp_path / 'gold'}\n"
    )
    return load_config(cfg_file)


def _write_gold_weekly(gold_dir):
    gold_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "subreddit": ["anxiety", "anxiety", "depression", "depression"],
            "week": pd.to_datetime(
                ["2020-03-02", "2020-03-16", "2020-03-02", "2020-03-16"]
            ),
            "n_posts": [100, 120, 200, 260],
            "n_active_authors": [100, 120, 200, 260],
            "avg_word_count": [150.0, 160.0, 170.0, 180.0],
            "sentiment": [-0.1, -0.2, -0.25, -0.3],
            "crisis_count": pd.array([10, 14, 60, 90], dtype="Int64"),
            "crisis_rate": [0.10, 0.117, 0.30, 0.346],
        }
    )
    frame.to_parquet(gold_dir / "gold_subreddit_weekly.parquet", index=False)
    return frame


def test_get_data_source_mock_when_no_gold(tmp_path):
    source = dataio.get_data_source(_tmp_cfg(tmp_path))
    assert source.is_mock is True
    assert not source.load().weekly.empty


def test_get_data_source_live_when_gold_exists(tmp_path):
    cfg = _tmp_cfg(tmp_path)
    _write_gold_weekly(tmp_path / "gold")
    source = dataio.get_data_source(cfg)
    assert source.is_mock is False

    loaded = source.load()
    assert loaded.is_mock is False
    # Contract columns lead; live extras ride along after them.
    assert list(loaded.weekly.columns[:6]) == [
        "week", "subreddit", "n_posts", "sentiment", "crisis_rate", "crisis_count",
    ]
    assert "n_active_authors" in loaded.weekly.columns
    assert pd.api.types.is_datetime64_any_dtype(loaded.weekly["week"])
    # The generic helpers work on the live frame unchanged.
    k = dataio.kpis(loaded.weekly)
    assert k["total_posts"] == 680
    assert 0 < k["crisis_share"] < 1


# --- covid split + smoothing ---------------------------------------------------


def test_covid_split_deltas(tmp_path):
    frame = _write_gold_weekly(tmp_path / "gold")
    split = dataio.covid_split(frame, cutoff=pd.Timestamp("2020-03-10"))
    anx = split.set_index("subreddit").loc["anxiety"]
    assert anx["sentiment_delta"] == pytest.approx(-0.1)
    assert anx["crisis_rate_delta"] == pytest.approx(0.017, abs=1e-3)
    assert anx["posts_pre"] == 100 and anx["posts_post"] == 120


def test_covid_split_empty_when_not_spanning():
    df = build_weekly_aggregates(SUBS)  # 2024 sample data — after the cutoff
    assert dataio.covid_split(df).empty
    assert dataio.covid_split(pd.DataFrame()).empty


def test_smooth_rolling_mean():
    df = pd.DataFrame(
        {
            "week": pd.to_datetime(["2020-01-06", "2020-01-13", "2020-01-20"]),
            "subreddit": "anxiety",
            "n_posts": [10, 10, 10],
            "sentiment": [0.0, 0.3, 0.6],
            "crisis_rate": [0.1, 0.1, 0.4],
            "crisis_count": [1, 1, 4],
        }
    )
    out = dataio.smooth(df, window=3)
    assert out["sentiment"].tolist() == pytest.approx([0.0, 0.15, 0.3])
    assert dataio.smooth(df, window=1).equals(df)


# --- preview guardrail -------------------------------------------------------

_AGGREGATE_OK = [
    "which community trended most negative this quarter?",
    "what's the crisis-signal trend over the last month?",
    "compare sentiment across subreddits",
    "how did anxiety sentiment change over time?",
    "which community has the most posts?",
]

_INDIVIDUAL_TARGETING = [
    "Show me the most negative post and who wrote it",
    "Quote some actual posts from r/depression",
    "Which person had the most crisis flags?",
    "List the accounts that posted in the crisis cohort",
    "Who wrote the saddest post last week?",
    "Tell me about the author of the top post",
    "Can you DM the poster?",
    "What's the handle of the OP?",
    "Identify the user with id 1234",
    "Who's that account?",
]


@pytest.fixture(scope="module")
def weekly():
    return build_weekly_aggregates(SUBS)


@pytest.mark.parametrize("question", _INDIVIDUAL_TARGETING)
def test_guardrail_refuses_individual_questions(question, weekly):
    assert dataio.answer_question(question, weekly) == REFUSAL_MESSAGE


@pytest.mark.parametrize("question", _AGGREGATE_OK)
def test_guardrail_allows_aggregate_questions(question, weekly):
    answer = dataio.answer_question(question, weekly)
    assert answer != REFUSAL_MESSAGE
    assert "aggregate" in answer.lower()


def test_guardrail_empty_question_prompts():
    assert "Ask about" in dataio.answer_question("", build_weekly_aggregates(SUBS))
