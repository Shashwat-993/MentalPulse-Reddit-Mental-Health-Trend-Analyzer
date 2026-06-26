"""Data-access seam for the MentalPulse dashboard.

A thin boundary between the UI (``dashboard/app.py``) and wherever the numbers
come from. Today it returns deterministic sample data (``MockDataSource``); once
Phase 1 produces Gold tables it returns a live source reading Gold/Snowflake —
the UI does not change. This is the architecture's "Streamlit-in-Snowflake with
a local fallback" design, expressed as one swap point.

The query helpers below operate on the long-form weekly table and are pure
(no Streamlit), so they can be unit-tested without a running app — see
``tests/test_dashboard.py``.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import pandas as pd

from config.loader import Config, load_config
from rag.prompts import REFUSAL_MESSAGE

from .mock_data import build_weekly_aggregates

logger = logging.getLogger(__name__)

# Best-effort guardrail mirror for the PREVIEW analyst panel. The authoritative
# guardrail is the Phase 3 agent's system prompt (rag/prompts.py); this only
# illustrates it. It leans toward refusing anything that looks individual- or
# content-targeting (aggregate / cohort / trend questions pass). The regression
# tests in tests/test_dashboard.py pin known phrasings so it does not silently
# drift from the agent's hard rule.
_INDIVIDUAL_MARKERS = [
    r"\b(?:who|whose|author|authors|poster|posters|person|individual|individuals)\b",
    r"\b(?:user|users|username|usernames|handle|handles|profile|profiles)\b",
    r"\b(?:account|accounts|identify|verbatim|quote|quotes|dm|op)\b",
    r"de-?anonymi\w*",
    r"/?u/",
    r"posted by",
    r"real name",
    r"name of",
    r"(?:example|actual|specific|negative|saddest|top|that|this|the) post",
    r"direct message",
    r"private message",
    r"message the",
]
_INDIVIDUAL_REQUEST = re.compile("|".join(_INDIVIDUAL_MARKERS), re.IGNORECASE)


@dataclass
class DashboardData:
    """What the dashboard renders, plus whether it is sample (mock) data."""

    weekly: pd.DataFrame
    is_mock: bool
    source_label: str


class MockDataSource:
    """Serves deterministic synthetic aggregates until the pipeline exists."""

    is_mock = True
    source_label = "Sample data (mock)"

    def __init__(self, cfg: Config) -> None:
        subreddits = list(getattr(cfg.source, "subreddits", []))
        self._weekly = build_weekly_aggregates(subreddits)

    def load(self) -> DashboardData:
        return DashboardData(
            weekly=self._weekly, is_mock=True, source_label=self.source_label
        )


def _gold_available(cfg: Config) -> bool:
    """True once Phase 1 has produced Gold parquet under ``data/gold``.

    Uses ``rglob`` so partitioned / Delta-style output
    (``data/gold/<table>/part-*.parquet``) is detected, not just bare top-level
    files. Keep this in sync with the Phase 1 Gold writer's on-disk layout.
    """
    try:
        gold = cfg.path("gold")
    except Exception:
        return False
    return gold.exists() and any(gold.rglob("*.parquet"))


def get_data_source(cfg: Config | None = None) -> MockDataSource:
    """Return the active data source.

    Always returns a working source. The live Gold/Snowflake reader is wired in
    here in Phase 1; until it exists we deliberately fall back to mock — so
    dropping a Gold parquet mid-development can never brick the running
    dashboard (the trigger and the reader are decoupled on purpose).
    """
    cfg = cfg or load_config()
    if _gold_available(cfg):
        # Phase 1+: construct and return the live source here, e.g.
        #   return GoldDataSource(cfg)
        logger.info(
            "Gold data detected, but the live reader is not implemented yet; "
            "serving sample data."
        )
    return MockDataSource(cfg)


# --- aggregate query helpers (operate on the weekly long-form table) ----------
# All KPIs are computed over the passed-in (already filtered) frame, so every
# metric reflects the same selected window.


def kpis(weekly: pd.DataFrame) -> dict:
    if weekly.empty:
        return {
            "communities": 0,
            "total_posts": 0,
            "avg_sentiment": 0.0,
            "crisis_share": 0.0,
        }
    total_posts = int(weekly["n_posts"].sum())
    crisis_total = int(weekly["crisis_count"].sum())
    return {
        "communities": int(weekly["subreddit"].nunique()),
        "total_posts": total_posts,
        "avg_sentiment": float(weekly["sentiment"].mean()),
        "crisis_share": (crisis_total / total_posts) if total_posts else 0.0,
    }


def sentiment_pivot(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return pd.DataFrame()
    return weekly.pivot_table(index="week", columns="subreddit", values="sentiment")


def crisis_volume_pivot(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return pd.DataFrame()
    return weekly.pivot_table(
        index="week", columns="subreddit", values="crisis_count", aggfunc="sum"
    )


def community_overview(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return pd.DataFrame()
    overview = weekly.groupby("subreddit").agg(
        posts=("n_posts", "sum"),
        avg_sentiment=("sentiment", "mean"),
        crisis_signals=("crisis_count", "sum"),
    )
    # Guard the division so a zero-post cohort shows 0.0, not NaN.
    overview["crisis_share"] = (
        overview["crisis_signals"]
        .div(overview["posts"])
        .where(overview["posts"] > 0, 0.0)
        .round(4)
    )
    overview["avg_sentiment"] = overview["avg_sentiment"].round(3)
    return overview.reset_index().sort_values("posts", ascending=False)


def answer_question(question: str, weekly: pd.DataFrame) -> str:
    """Preview analyst: best-effort guardrail demo over the sample aggregates.

    The real LangGraph + Claude agent (``rag/agent.py``) replaces this in
    Phase 3 and carries the authoritative guardrail.
    """
    query = (question or "").strip()
    if not query:
        return (
            'Ask about aggregate trends — e.g. "which community trended most '
            'negative this quarter?"'
        )
    if _INDIVIDUAL_REQUEST.search(query):
        # Mirrors the agent's hard rule: aggregate/cohort answers only.
        return REFUSAL_MESSAGE
    if weekly.empty:
        return "No data is loaded yet."
    overview = community_overview(weekly)
    most_negative = overview.sort_values("avg_sentiment").iloc[0]
    highest_crisis = overview.sort_values("crisis_share", ascending=False).iloc[0]
    return (
        "_(Preview — the live LangGraph + Claude agent is wired in Phase 3; this "
        "is a canned answer over the sample aggregates.)_\n\n"
        f"Across the sample period, **r/{most_negative['subreddit']}** shows the most "
        f"negative average sentiment ({most_negative['avg_sentiment']:+.3f}), and "
        f"**r/{highest_crisis['subreddit']}** has the highest aggregate crisis-signal "
        f"share ({highest_crisis['crisis_share']:.1%}). These are aggregate, "
        "anonymized cohort trends only."
    )
