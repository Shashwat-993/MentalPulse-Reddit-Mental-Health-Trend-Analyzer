"""MentalPulse dashboard (Streamlit) — local-runnable shell.

Run from the repo root:

    streamlit run dashboard/app.py

Shows aggregate sentiment and crisis-signal trends across public Reddit
mental-health communities, plus a preview analyst panel. Until the Phase 1-2
pipeline produces real Gold tables, it renders deterministic SAMPLE data
(clearly flagged). The data-access layer (``dashboard/data.py``) swaps to live
Gold/Snowflake with no change to this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when launched via `streamlit run dashboard/app.py`
# (Streamlit puts the script's own dir on sys.path, not the project root).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from config.loader import load_config  # noqa: E402
from rag.prompts import DISCLAIMER  # noqa: E402
from dashboard import data as dataio  # noqa: E402

st.set_page_config(page_title="MentalPulse", page_icon="🧭", layout="wide")


@st.cache_data(show_spinner=False)
def _load_weekly():
    cfg = load_config()
    loaded = dataio.get_data_source(cfg).load()
    return loaded.weekly, loaded.is_mock, loaded.source_label


def main() -> None:
    # Title + non-negotiable disclaimer banner render FIRST, before any data
    # load, so the disclaimer is always visible even if loading fails.
    st.title("MentalPulse — Mental-Health Trend Intelligence")
    st.caption(
        "Aggregate emotional & crisis-signal trends across public Reddit communities."
    )
    st.warning(DISCLAIMER, icon="⚠️")

    try:
        weekly, is_mock, source_label = _load_weekly()
    except Exception as exc:  # never let a data error hide the disclaimer
        st.error(f"Could not load data: {exc}")
        return

    if is_mock:
        st.info(
            "Showing **sample data** — the pipeline (Phases 1-3) is not built yet, "
            "so these numbers are synthetic and illustrative only.",
            icon="🧪",
        )

    # ---- Sidebar filters ----
    all_subs = (
        sorted(weekly["subreddit"].unique().tolist()) if not weekly.empty else []
    )
    with st.sidebar:
        st.header("Filters")
        st.caption(f"Data source: **{source_label}**")
        selected = st.multiselect("Communities", all_subs, default=all_subs)
        date_range = None
        if not weekly.empty:
            min_week = weekly["week"].min().to_pydatetime()
            max_week = weekly["week"].max().to_pydatetime()
            if min_week < max_week:
                date_range = st.slider(
                    "Date range",
                    min_value=min_week,
                    max_value=max_week,
                    value=(min_week, max_week),
                    format="YYYY-MM-DD",
                )

    if weekly.empty or not selected:
        st.info("Select at least one community to see trends.")
        return

    view = weekly[weekly["subreddit"].isin(selected)]
    if date_range:
        low, high = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        view = view[(view["week"] >= low) & (view["week"] <= high)]

    if view.empty:
        st.info("No data in the selected range.")
        return

    # ---- KPI row (all metrics over the selected window) ----
    metrics = dataio.kpis(view)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Communities", metrics["communities"])
    col2.metric("Posts (sample)", f"{metrics['total_posts']:,}")
    col3.metric("Avg sentiment", f"{metrics['avg_sentiment']:+.3f}")
    col4.metric("Crisis-signal share", f"{metrics['crisis_share']:.1%}")

    # ---- Sentiment trends ----
    st.subheader("Sentiment trend by community")
    st.caption("Weekly mean sentiment (-1 negative … +1 positive). Aggregate only.")
    st.line_chart(dataio.sentiment_pivot(view))

    # ---- Crisis-signal volume ----
    st.subheader("Crisis-signal volume by community")
    st.caption(
        "Weekly count of posts flagged by the (future) crisis classifier. "
        "**Aggregate counts only — never individual posts, users, or quotes.**"
    )
    st.area_chart(dataio.crisis_volume_pivot(view))

    # ---- Community overview ----
    st.subheader("Community overview")
    st.dataframe(
        dataio.community_overview(view),
        width="stretch",
        hide_index=True,
    )

    # ---- Preview analyst panel ----
    st.subheader("Ask the analyst · preview")
    st.caption(
        "A best-effort illustration of the guardrail — the authoritative version "
        "lives in the Phase 3 LangGraph + Claude agent. It answers aggregate "
        "questions and refuses individual-level ones."
    )
    question = st.chat_input("Ask about aggregate trends…")
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.markdown(dataio.answer_question(question, view))

    st.divider()
    st.caption(
        "Responsible use: public data only · anonymized at ingestion · aggregate, "
        "never individual · not a clinical tool. See the project README."
    )


if __name__ == "__main__":
    main()
