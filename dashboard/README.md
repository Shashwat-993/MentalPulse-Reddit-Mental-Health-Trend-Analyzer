# MentalPulse dashboard

A Streamlit app showing **aggregate** emotional and crisis-signal trends across
public Reddit mental-health communities, plus a preview analyst panel.

## Run

From the repo root:

```bash
pip install -r requirements.txt        # or just: pip install streamlit pandas
streamlit run dashboard/app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

## What it shows

- A persistent **disclaimer banner** (shared text from `rag/prompts.py`) — this
  is a research/portfolio project, not a clinical tool.
- **Sentiment trend by community** — weekly mean sentiment per subreddit.
- **Crisis-signal volume by community** — weekly aggregate counts only.
- **Community overview** — posts, average sentiment, and crisis share per
  community.
- **Ask the analyst (preview)** — a chat box that answers aggregate questions
  and refuses individual-level ones. This is a best-effort illustration; the
  authoritative guardrail lives in the Phase 3 agent. Regression tests pin the
  refusal behavior (see Tests).

## Sample vs live data

Until Phases 1-2 produce real Gold tables, the dashboard renders **deterministic
sample data** (clearly flagged in the UI). The swap to live data happens in one
place — `dashboard/data.py`:

- `get_data_source(cfg)` returns `MockDataSource` today.
- When Phase 1 writes Gold parquet (or Snowflake is reachable), it returns a
  live source instead — the UI is unchanged.

The aggregate query helpers in `dashboard/data.py` (`kpis`, `sentiment_pivot`,
`crisis_volume_pivot`, `community_overview`, `answer_question`) are pure pandas
and have no Streamlit dependency, so they are unit-testable on their own.

## Tests

Pure-pandas / guardrail tests (no Streamlit runtime needed):

```bash
pip install pytest
python -m pytest tests/test_dashboard.py -q
```

## Deployment

The local app here is the canonical dashboard. Deploying it to
**Streamlit-in-Snowflake** (reading Gold from Snowflake via a Snowpark session)
is finalized in Phase 4 — see `snowflake/04_streamlit_app.py`.
