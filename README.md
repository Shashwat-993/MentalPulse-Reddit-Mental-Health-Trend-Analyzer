# MentalPulse — Reddit Mental-Health Trend Analyzer

A portfolio data project: a mental-health **trend-intelligence** platform that
pipelines public Reddit community data, detects emotional/crisis signals over
time with two ML models, lets a researcher ask plain-English questions via a
retrieval-augmented agent, and surfaces everything in a dashboard.

It is built to demonstrate the full modern data stack end-to-end —
**ingestion → medallion lakehouse → ML → enterprise warehouse → semantic
retrieval → agentic RAG → dashboard** — targeting Data Engineering, Data
Science/ML, and GenAI/LLM roles.

> ⚠️ **Disclaimer — please read.** MentalPulse is a **research and portfolio
> project**. It is **NOT** a diagnostic, medical, or crisis-intervention tool and
> does not provide clinical advice. It reports **aggregate** trends across public
> Reddit communities and never represents or identifies individual people. If you
> or someone you know is in crisis, contact a local emergency service or crisis
> hotline.

## Responsible Data Use

These rules are non-negotiable and are enforced in code, not just documented:

1. **Public data only.** No private subreddits, DMs, or authenticated-user scraping.
2. **Anonymize at ingestion.** Author ids are salted-SHA-256 hashed (or dropped)
   in the first transform; raw usernames never survive past Bronze. PII (emails,
   phones, @handles, URLs) is stripped from text.
3. **Aggregate, never expose individuals.** Dashboards and agent answers report
   trends/cohorts only — never single-user content or re-identifying quotes.
4. **Not a clinical tool.** See the disclaimer above (also shown in the dashboard
   and the agent's system prompt).
5. **Respect Reddit API ToS + rate limits.** Descriptive User-Agent, aggressive
   caching, PRAW backoff. Non-commercial use only. API access is obtained
   through Reddit's **Responsible Builder Policy** access-request process
   (pre-approval required before app creation), with the research/portfolio
   use case — including any ML use of the data — declared up front.

## Tech stack

| Layer | Tooling |
| ----- | ------- |
| Ingestion | PRAW + Python |
| Lakehouse | Databricks Delta Lake, medallion (Bronze/Silver/Gold) |
| Transforms | dbt-databricks (models + tests) |
| ML + tracking | scikit-learn / HuggingFace transformers, MLflow |
| Warehouse | Snowflake (curated Gold) |
| Semantic retrieval | Snowflake Cortex Search **and** local LanceDB (swappable) |
| Agent | LangGraph + Claude API (official Anthropic SDK) |
| Dashboard | Streamlit (Streamlit-in-Snowflake; local fallback) |
| RAG eval | Ragas |

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the diagram, data flow,
and the open-source-vs-enterprise dual-deployment comparison.

## Repository layout

```
.
├── config/        # config.yaml + loader (reads .env for secrets)
├── ingestion/     # PRAW client, fetch posts/comments, anonymization
├── data/          # local Bronze/Silver/Gold mirror (gitignored)
├── databricks/    # medallion + model-training notebooks
├── dbt/           # dbt-databricks project (Silver/Gold models + tests)
├── snowflake/     # warehouse setup, Gold load, Cortex Search, Streamlit app
├── rag/           # retriever interface + 2 backends, tools, LangGraph agent
├── eval/          # Ragas evaluation (both retriever backends)
└── docs/          # architecture + interview narrative
```

## Setup

```bash
# 1. Python env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Secrets — copy and fill in (never commit .env)
cp .env.example .env

# 3. Sanity check config loading (prints which secrets are set; never values)
python -m config.loader
```

See [`.env.example`](.env.example) for the full list of credentials. Required
keys are introduced phase by phase (Reddit for Phase 1; Anthropic + Snowflake +
Databricks as later phases come online).

## How to run

Built incrementally across four phases — see [`PROGRESS.md`](PROGRESS.md) for
status and per-phase run instructions (added as each phase lands).

## Status

**Phase 0 — scaffold complete.** Project structure, config loader, pinned
dependencies, and responsible-use guardrails are in place. Phases 1–4 (data
engineering, ML, RAG agent, dashboard/eval) are next.

_Screenshots: TBD (added in Phase 4)._
