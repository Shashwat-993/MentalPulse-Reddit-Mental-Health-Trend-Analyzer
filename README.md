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
2. **Anonymize at ingestion.** The research corpus turned out to contain **raw
   usernames** (verified 2026-07-03), so de-identification happens in our
   Bronze→Silver transform: every author id is salted-SHA-256 hashed and the
   raw column dropped — raw usernames never survive past Bronze, and Bronze
   never leaves the machine (`data/` is gitignored). PII (emails, phones,
   handles/@mentions, URLs) is scrubbed from text. Verified on every pipeline
   run (`ingestion.anonymize.assert_anonymized`) and pinned by tests.
3. **Aggregate, never expose individuals.** Dashboards and agent answers report
   trends/cohorts only — never single-user content or re-identifying quotes.
4. **Not a clinical tool.** See the disclaimer above (also shown in the dashboard
   and the agent's system prompt).
5. **Use a licensed research corpus, non-commercially.** Phase 1 sources a
   pre-collected Reddit research dataset (Low et al.'s Reddit Mental Health
   Dataset, Zenodo 3941387, ODC-PDDL; GoEmotions as a fallback) under its
   published open license — no live scraping. Non-commercial use only. (A live
   Reddit API path would require Responsible Builder Policy pre-approval and is
   deferred.)

## Tech stack

| Layer | Tooling |
| ----- | ------- |
| Ingestion | Reddit research corpus (Low et al. / GoEmotions) + Python |
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
├── ingestion/     # research-corpus loader, parsing, anonymization
├── data/          # local Bronze/Silver/Gold mirror (gitignored)
├── databricks/    # medallion + model-training notebooks
├── dbt/           # dbt-databricks project (Silver/Gold models + tests)
├── snowflake/     # warehouse setup, Gold load, Cortex Search, SiS deploy
├── rag/           # retriever interface + 2 backends, tools, LangGraph agent
├── dashboard/     # Streamlit dashboard (runnable now on sample data)
├── eval/          # Ragas evaluation (both retriever backends)
├── tests/         # pytest suite
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
keys are introduced phase by phase. Phase 1 needs **no** Reddit API keys (it loads
a research corpus); Snowflake + Databricks come online in Phase 1/2, and Anthropic
in Phase 3.

## How to run

The local data pipeline (needs `MENTALPULSE_HASH_SALT` in `.env`):

```bash
python -m ingestion.load_corpus    # download corpus (~590 MB, cached) + land Bronze
python -m ingestion.run_pipeline   # Bronze -> Silver -> Gold + anonymization proof
```

The dashboard is runnable now (sample data until Phase 2 scores land):

```bash
streamlit run dashboard/app.py
```

Tests: `pytest`. Cloud mirrors: see [`dbt/README.md`](dbt/README.md)
(dbt-databricks) and the notebooks in [`databricks/`](databricks/). The full
system is built incrementally across four phases — see
[`PROGRESS.md`](PROGRESS.md) for status.

## Status

**Phase 1 — local data engineering complete.** The research corpus (Low et
al.'s Reddit Mental Health Dataset — 203k posts, 6 communities, Nov 2018–Apr
2020) flows through Bronze → Silver → Gold locally, with de-identification
enforced and verified on every run (the corpus ships raw usernames; zero
survive into Silver — proven against all 179k authors). Databricks notebooks
and a tested dbt project mirror the transforms; the Snowflake loader is
code-complete and gated on cost approval. Next: run the cloud mirrors, then
Phase 2 (ML scoring).

_Screenshots: TBD (added in Phase 4)._
