# MentalPulse — Progress

Built one phase at a time. Each phase is verified before the next begins.

## Phase 0 — Scaffold ✅
- [x] Repo structure with stub files
- [x] `README.md` skeleton + Responsible Data Use section
- [x] `PROGRESS.md`
- [x] `.gitignore` (python + `.env` + `data/`)
- [x] Pinned `requirements.txt`
- [x] `config/config.yaml` + `config/loader.py` (reads `.env` for secrets)
- [x] `.env.example`
- [x] `docs/architecture.md` (diagram) + `docs/interview_narrative.md` skeleton

## Phase 1 — Data Engineering ⬜
_Reddit → Bronze → Silver → Gold, mirrored locally + on Databricks, with an
approved path to load Gold into Snowflake._
- [ ] `ingestion/reddit_client.py` — PRAW auth + caching
- [ ] `ingestion/fetch_posts.py` — posts + top-level comments → Bronze parquet
- [ ] `ingestion/anonymize.py` — salted hash + PII strip (Bronze→Silver)
- [ ] Databricks notebooks 01–03 (Bronze / Silver / Gold)
- [ ] dbt project + tests (not_null/unique keys, accepted_values on subreddit)
- [ ] Snowflake `01_setup.sql` + loader (**approve approach/credits first**)
- [ ] Acceptance: local Bronze parquet; zero raw usernames in Silver (proven);
      Gold schema documented; dbt tests pass; approved path to Snowflake

## Phase 2 — Machine Learning ⬜
_Two MLflow-tracked models; scores written back to Gold and pushed to Snowflake._
- [ ] Sentiment scorer (pretrained transformer) → Gold + weekly trend
- [ ] Crisis classifier (transparent; weak-supervision labels; importances)
- [ ] MLflow tracking (params/metrics/artifacts)
- [ ] Refresh Gold + Snowflake; Cortex `SENTIMENT` comparison (tiny sample first)
- [ ] Acceptance: both models run; Gold populated; Snowflake refreshed; docs

## Phase 3 — RAG + Agent ⬜
_LangGraph agent with a swappable retrieval layer (LanceDB vs Cortex Search)._
- [ ] `rag/retriever.py` — interface + LanceDB + Cortex backends (config-selectable)
- [ ] `rag/tools.py` — sql_metric_tool (whitelisted) + retrieval_tool
- [ ] `rag/agent.py` — routing, Claude API, cited answers, disclaimer + guardrails
- [ ] Acceptance: 5+ varied grounded answers; backend swap via config only;
      refuses individual-level/unsafe requests (**approve Cortex credits first**)

## Phase 4 — Dashboard, Eval, Polish ⬜
- [ ] Streamlit dashboard (sentiment trends, aggregate crisis volume, agent chat,
      disclaimer banner) — Streamlit-in-Snowflake + local fallback
- [ ] `eval/ragas_eval.py` — ~15 Q&A; faithfulness/relevancy/context P&R; both backends
- [ ] `docs/architecture.md` — finalize diagram + dual-deployment comparison table
- [ ] `docs/interview_narrative.md` — STAR writeup + 6–8 Q&A
- [ ] Finalize README (screenshots, run steps)
