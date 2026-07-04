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

## Phase 1 — Data Engineering ✅
_Reddit research corpus → Bronze → Silver → Gold, mirrored locally + on
Databricks, with an approved path to load Gold into Snowflake._

> 🔄 **Source decision (2026-06-15):** the live Reddit API was dropped after the
> Responsible Builder Policy request went unanswered for 2+ weeks. Phase 1 now
> uses a **pre-collected Reddit research corpus** — primary: Low et al.'s Reddit
> Mental Health Dataset (Zenodo 3941387, ODC-PDDL); guaranteed-open fallback:
> GoEmotions (Apache-2.0). No approval gate, and the project keeps its Reddit
> framing.

> ⚠️ **Finding (2026-07-03):** the corpus is **not** de-identified at the author
> level — its `author` column holds raw Reddit usernames. De-identification
> therefore genuinely happens in our Bronze→Silver step, and Bronze/raw data
> must never leave the machine (`data/` is gitignored). Docs corrected.
- [x] Load research corpus → Bronze parquet — verified access, downloaded 6
      subreddits × pre/post windows (checksummed, cached), landed 203,293 rows
      (`ingestion/corpus.py`, `ingestion/load_corpus.py`)
- [x] `ingestion/anonymize.py` — salted-SHA-256 author hashing, PII scrub
      (email/URL/u-handle/@mention/phone), `assert_anonymized` verification
- [x] Local Silver + Gold transforms (`ingestion/transforms.py`,
      `ingestion/run_pipeline.py`) — run on the real corpus: 203,293 Silver
      rows, 396 weekly Gold rows, Nov 2018–Apr 2020, verification passed
- [x] Databricks lakehouse populated (2026-07-03): corpus CSVs uploaded to the
      `mentalpulse.bronze.raw` volume; Bronze Delta table created via the SQL
      Statement API using the exact logic of notebook 01. Bronze/Silver/Gold
      row counts match the local mirror (203,293 / 203,293 / 396), and the
      anonymization checks were re-proven in-warehouse (0 raw-author leaks,
      0 unscrubbed PII). Notebooks 01–03 remain the reproducible/documented
      path for cluster-based runs.
- [x] dbt project + tests — `dbt run` built silver/gold on Databricks and
      **`dbt test` passes 15/15** (not_null/unique `post_id`, accepted_values
      on `subreddit`, not_null dates/weeks/counts)
- [x] Snowflake `01_setup.sql` + loader (`02_load_gold.sql`,
      `snowflake/load_gold.py`) — **loaded and verified (2026-07-04)**:
      `MENTALPULSE.GOLD.GOLD_POSTS_FEATURES` 203,293 rows,
      `GOLD_SUBREDDIT_WEEKLY` 396 rows; per-subreddit totals and week spans
      match the local/Databricks Gold exactly; unscored sentiment/crisis
      columns are NULL as designed. Unblocked by a user-created network
      policy (PAT auth requires one). Loader notes: PAT sessions are pinned
      to their minted role (`USE ROLE` skipped), and parquet timestamps load
      via explicit micro-second casts in the COPY transforms.
- [x] Acceptance: local Bronze parquet ✅; zero raw usernames in Silver ✅
      (proven: 0 of 179,173 raw authors survive; enforced on every run +
      pytest, re-verified on Databricks); Gold schema documented ✅
      (`docs/data_model.md`); dbt tests pass ✅ (15/15 against the live
      workspace); Gold loaded into Snowflake ✅ (row counts verified)

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
> The dashboard shell was brought forward and runs now on sample data
> (`streamlit run dashboard/app.py`); it wires to live data as Phases 1-3 land.
- [~] Streamlit dashboard shell built & runnable on sample data
      (`dashboard/app.py`): sentiment trends, aggregate crisis volume, preview
      analyst panel, disclaimer banner; data-access seam swaps to live
      Gold/Snowflake. Streamlit-in-Snowflake deploy finalized in Phase 4.
- [ ] `eval/ragas_eval.py` — ~15 Q&A; faithfulness/relevancy/context P&R; both backends
- [ ] `docs/architecture.md` — finalize diagram + dual-deployment comparison table
- [ ] `docs/interview_narrative.md` — STAR writeup + 6–8 Q&A
- [ ] Finalize README (screenshots, run steps)
