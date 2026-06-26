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


def test_get_data_source_returns_working_mock():
    source = dataio.get_data_source(load_config())
    assert source.is_mock is True
    assert not source.load().weekly.empty


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
