"""MentalPulse dashboard (Streamlit).

Run from the repo root:

    streamlit run dashboard/app.py

Renders aggregate sentiment and crisis-signal trends across public Reddit
mental-health communities from the live Gold tables (Phases 1–2); falls back
to clearly-flagged deterministic sample data on a fresh clone. The data-access
layer (``dashboard/data.py``) owns that swap — this file only renders.

Design notes: categorical colors are a fixed entity→hue mapping (filters never
repaint surviving series), sentiment uses a red↔gray↔blue diverging scale,
crisis intensity a single-hue sequential ramp; every chart carries tooltips
and a legend, and the community table doubles as the accessible table view.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when launched via `streamlit run dashboard/app.py`
# (Streamlit puts the script's own dir on sys.path, not the project root).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from config.loader import load_config  # noqa: E402
from rag.prompts import DISCLAIMER  # noqa: E402
from dashboard import data as dataio  # noqa: E402

st.set_page_config(page_title="MentalPulse", page_icon="🧭", layout="wide")

# Fixed entity → hue mapping (validated palette; alphabetical assignment so a
# community keeps its color no matter which filters are active).
SERIES_COLORS = {
    "adhd": "#2a78d6",
    "anxiety": "#008300",
    "bipolarreddit": "#e87ba4",
    "depression": "#eda100",
    "mentalhealth": "#1baf7a",
    "suicidewatch": "#eb6834",
}
_FALLBACK_SLOTS = ["#4a3aa7", "#e34948"]  # for mock/unknown community names
DIVERGING = ["#e34948", "#f0efec", "#2a78d6"]  # negative ↔ neutral ↔ positive
SEQUENTIAL = ["#cde2fb", "#3987e5", "#0d366b"]  # low → high crisis intensity
GRID_INK = "#52514e"


def _color_scale(subreddits: list[str]) -> alt.Scale:
    domain, colors, spare = [], [], list(_FALLBACK_SLOTS)
    for sub in sorted(subreddits):
        domain.append(sub)
        colors.append(SERIES_COLORS.get(sub) or (spare.pop(0) if spare else "#52514e"))
    return alt.Scale(domain=domain, range=colors)


@st.cache_data(show_spinner=False)
def _load_weekly():
    cfg = load_config()
    loaded = dataio.get_data_source(cfg).load()
    return loaded.weekly, loaded.is_mock, loaded.source_label


def _covid_layers(view: pd.DataFrame) -> list[alt.Chart]:
    """Dashed marker at the WHO pandemic declaration, when the data spans it."""
    cutoff = dataio.COVID_CUTOFF
    if view.empty or not (view["week"].min() <= cutoff <= view["week"].max()):
        return []
    marker = pd.DataFrame({"week": [cutoff], "label": ["WHO pandemic declaration"]})
    rule = (
        alt.Chart(marker)
        .mark_rule(strokeDash=[4, 3], color=GRID_INK, strokeWidth=1.5)
        .encode(x="week:T", tooltip=[alt.Tooltip("label:N", title="Event"),
                                     alt.Tooltip("week:T", title="Date")])
    )
    text = (
        alt.Chart(marker)
        .mark_text(text="COVID-19 ▸", align="right", dx=-4, dy=-6, color=GRID_INK,
                   baseline="top", fontSize=11)
        .encode(x="week:T", y=alt.value(0))
    )
    return [rule, text]


def _trend_chart(view, field, title, fmt, scale, color_scale, zero_rule=False):
    tooltips = [
        alt.Tooltip("week:T", title="Week"),
        alt.Tooltip("subreddit:N", title="Community"),
        alt.Tooltip(f"{field}:Q", title=title, format=fmt),
        alt.Tooltip("n_posts:Q", title="Posts", format=","),
    ]
    line = (
        alt.Chart(view.dropna(subset=[field]))
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=alt.X("week:T", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y(f"{field}:Q", title=title, scale=scale,
                    axis=alt.Axis(format=fmt, gridOpacity=0.25)),
            color=alt.Color("subreddit:N", scale=color_scale,
                            legend=alt.Legend(title=None, orient="top")),
            tooltip=tooltips,
        )
    )
    layers = [line]
    if zero_rule:
        layers.insert(0, alt.Chart(pd.DataFrame({"y": [0.0]}))
                      .mark_rule(color=GRID_INK, opacity=0.5).encode(y="y:Q"))
    layers += _covid_layers(view)
    return alt.layer(*layers).properties(height=340).interactive(bind_y=False)


def _heatmap(view, field, title, color_range, domain_mid=None):
    scale = alt.Scale(range=color_range)
    if domain_mid is not None:
        scale = alt.Scale(range=color_range, domainMid=domain_mid)
    return (
        alt.Chart(view.dropna(subset=[field]))
        .mark_rect(stroke="#fcfcfb", strokeWidth=1)
        .encode(
            x=alt.X("week:T", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("subreddit:N", title=None),
            color=alt.Color(f"{field}:Q", scale=scale,
                            legend=alt.Legend(title=title)),
            tooltip=[
                alt.Tooltip("week:T", title="Week"),
                alt.Tooltip("subreddit:N", title="Community"),
                alt.Tooltip(f"{field}:Q", title=title, format=".3f"),
                alt.Tooltip("n_posts:Q", title="Posts", format=","),
            ],
        )
        .properties(height=240)
    )


def _delta_bars(split: pd.DataFrame, field: str, title: str, fmt: str, color_scale):
    return (
        alt.Chart(split)
        .mark_bar(cornerRadiusEnd=4, size=26)
        .encode(
            x=alt.X(f"{field}:Q", title=title, axis=alt.Axis(format=fmt, gridOpacity=0.25)),
            y=alt.Y("subreddit:N", title=None, sort="x"),
            color=alt.Color("subreddit:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("subreddit:N", title="Community"),
                alt.Tooltip(f"{field}:Q", title=title, format=fmt),
            ],
        )
        .properties(height=240)
    )


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
            "Showing **sample data** — run the pipeline "
            "(`python -m ingestion.load_corpus && python -m ingestion.run_pipeline`) "
            "to see the live corpus.",
            icon="🧪",
        )
    else:
        n_posts = int(weekly["n_posts"].sum())
        st.success(
            f"**Live data** — {n_posts:,} de-identified posts across "
            f"{weekly['subreddit'].nunique()} communities, "
            f"{weekly['week'].min():%b %Y} – {weekly['week'].max():%b %Y}. "
            "Sentiment: Twitter-RoBERTa. Crisis signal: weak-supervision "
            "classifier (calibrated). Aggregates only.",
            icon="📡",
        )

    # ---- Sidebar filters ----
    all_subs = sorted(weekly["subreddit"].unique().tolist()) if not weekly.empty else []
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
                    "Date range", min_value=min_week, max_value=max_week,
                    value=(min_week, max_week), format="YYYY-MM-DD",
                )
        smooth_on = st.toggle("Smooth trends (3-week mean)", value=True)
        with st.expander("About the data"):
            st.markdown(
                "Low et al., *Reddit Mental Health Dataset* (Zenodo 3941387, "
                "ODC-PDDL). De-identified at ingestion — salted-hashed authors, "
                "PII scrubbed; verified on every pipeline run. Sentiment is a "
                "tweet-calibrated transformer score in [−1, 1]; the crisis "
                "signal is a **weak-supervision baseline**, not a diagnosis. "
                "See `docs/data_model.md` for schemas and model caveats."
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

    plot_view = dataio.smooth(view) if smooth_on else view
    color_scale = _color_scale(selected)

    # ---- KPI row (all metrics over the selected window) ----
    metrics = dataio.kpis(view)
    cols = st.columns(5)
    cols[0].metric("Communities", metrics["communities"])
    cols[1].metric("Posts", f"{metrics['total_posts']:,}")
    cols[2].metric("Avg sentiment", f"{metrics['avg_sentiment']:+.3f}")
    cols[3].metric("Crisis-signal share", f"{metrics['crisis_share']:.1%}")
    cols[4].metric("Weeks", f"{view['week'].nunique()}")

    tab_trends, tab_covid, tab_heat, tab_comm, tab_ask = st.tabs(
        ["📈 Trends", "🦠 COVID-19 impact", "🗓️ Heatmaps", "👥 Communities", "💬 Ask (preview)"]
    )

    # ---- Trends ----
    with tab_trends:
        st.subheader("Sentiment trend by community")
        st.caption("Weekly mean sentiment (−1 negative … +1 positive). Aggregate only.")
        st.altair_chart(
            _trend_chart(plot_view, "sentiment", "Mean sentiment", "+.2f",
                         alt.Scale(zero=False), color_scale, zero_rule=True),
            use_container_width=True,
        )

        st.subheader("Crisis-signal rate by community")
        st.caption(
            "Weekly share of posts flagged by the crisis classifier — a "
            "weak-supervision baseline. **Aggregate rates only — never "
            "individual posts, users, or quotes.**"
        )
        st.altair_chart(
            _trend_chart(plot_view, "crisis_rate", "Crisis-signal rate", ".0%",
                         alt.Scale(zero=True), color_scale),
            use_container_width=True,
        )

        st.subheader("Post volume")
        volume = (
            alt.Chart(view)
            .mark_area(stroke="#fcfcfb", strokeWidth=1)
            .encode(
                x=alt.X("week:T", title=None, axis=alt.Axis(grid=False)),
                y=alt.Y("n_posts:Q", stack="zero", title="Posts / week",
                        axis=alt.Axis(format=",", gridOpacity=0.25)),
                color=alt.Color("subreddit:N", scale=color_scale,
                                legend=alt.Legend(title=None, orient="top")),
                tooltip=[
                    alt.Tooltip("week:T", title="Week"),
                    alt.Tooltip("subreddit:N", title="Community"),
                    alt.Tooltip("n_posts:Q", title="Posts", format=","),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(alt.layer(volume, *_covid_layers(view)), use_container_width=True)

        st.download_button(
            "Download filtered aggregates (CSV)",
            view.to_csv(index=False).encode(),
            file_name="mentalpulse_weekly_aggregates.csv",
            mime="text/csv",
        )

    # ---- COVID impact ----
    with tab_covid:
        split = dataio.covid_split(view)
        if split.empty:
            st.info(
                "The selected data doesn't span the WHO pandemic declaration "
                "(2020-03-11), so there is no before/after comparison to show."
            )
        else:
            st.caption(
                "Per-community change after the WHO pandemic declaration "
                "(2020-03-11) vs before — the natural experiment this corpus "
                "was collected around (Low et al., 2020)."
            )
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Δ mean sentiment** (after − before)")
                st.altair_chart(
                    _delta_bars(split, "sentiment_delta", "Δ sentiment", "+.3f", color_scale),
                    use_container_width=True,
                )
            with c2:
                st.markdown("**Δ crisis-signal rate** (after − before)")
                st.altair_chart(
                    _delta_bars(split, "crisis_rate_delta", "Δ crisis rate", "+.1%", color_scale),
                    use_container_width=True,
                )
            st.dataframe(
                split.rename(columns={
                    "subreddit": "Community",
                    "sentiment_pre": "Sentiment (pre)", "sentiment_post": "Sentiment (post)",
                    "sentiment_delta": "Δ sentiment",
                    "crisis_rate_pre": "Crisis rate (pre)", "crisis_rate_post": "Crisis rate (post)",
                    "crisis_rate_delta": "Δ crisis rate",
                    "posts_pre": "Posts (pre)", "posts_post": "Posts (post)",
                }),
                width="stretch", hide_index=True,
            )

    # ---- Heatmaps ----
    with tab_heat:
        st.subheader("Sentiment heatmap")
        st.caption("Red = negative, blue = positive; gray ≈ neutral.")
        st.altair_chart(
            _heatmap(view, "sentiment", "Mean sentiment", DIVERGING, domain_mid=0),
            use_container_width=True,
        )
        st.subheader("Crisis-signal rate heatmap")
        st.altair_chart(
            _heatmap(view, "crisis_rate", "Crisis rate", SEQUENTIAL),
            use_container_width=True,
        )

    # ---- Communities ----
    with tab_comm:
        st.subheader("Community overview")
        st.dataframe(dataio.community_overview(view), width="stretch", hide_index=True)

        st.subheader("Community drill-down")
        focus = st.selectbox("Community", selected)
        fview = view[view["subreddit"] == focus]
        if not fview.empty:
            k = dataio.kpis(fview)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Posts", f"{k['total_posts']:,}")
            d2.metric("Avg sentiment", f"{k['avg_sentiment']:+.3f}")
            d3.metric("Crisis share", f"{k['crisis_share']:.1%}")
            if "n_active_authors" in fview.columns:
                d4.metric("Active authors (wk avg)",
                          f"{fview['n_active_authors'].mean():,.0f}")
            fplot = dataio.smooth(fview) if smooth_on else fview
            st.altair_chart(
                _trend_chart(fplot, "sentiment", "Mean sentiment", "+.2f",
                             alt.Scale(zero=False), color_scale, zero_rule=True),
                use_container_width=True,
            )

    # ---- Preview analyst panel ----
    with tab_ask:
        st.caption(
            "A best-effort illustration of the guardrail — the authoritative "
            "version lives in the Phase 3 LangGraph agent. It answers aggregate "
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
