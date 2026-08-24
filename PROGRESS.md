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

## Phase 2 — Machine Learning ✅
_Two MLflow-tracked models; scores written back to Gold and pushed to Snowflake._
- [x] Sentiment scorer (pretrained transformer) → Gold + weekly trend
      (`ml/sentiment.py`): all 203,293 posts scored with
      `cardiffnlp/twitter-roberta-base-sentiment-latest` (int8-quantized,
      length-sorted batching, resumable 10k checkpoints — the run survived two
      container restarts). Weekly sentiment trend live: suicidewatch ≈ −0.33,
      depression ≈ −0.25, adhd ≈ 0.
- [x] Crisis classifier (transparent; weak-supervision labels; importances)
      (`ml/crisis.py`): two-tier distress lexicon → weak labels (23.1%
      prevalence); logistic regression on features that exclude the acute
      tier; flag threshold prevalence-calibrated to 0.614 (flag rate 23.05%;
      holdout vs weak labels: AUC 0.73, P/R ≈ 0.45/0.45). Importances logged
      (top: log_n_words +0.74, sentiment_score −0.55).
- [x] MLflow tracking (params/metrics/artifacts) — local `mlruns/`, both runs
      logged (model, quantization, thresholds, metrics, weekly-trend artifact,
      feature importances).
- [x] Refresh Gold + Snowflake; warehouse `SENTIMENT` comparison — local,
      Databricks, and Snowflake Gold all refreshed with scores (203,293 +
      396 rows verified in each). ⚠️ Cortex `SENTIMENT()` is **not available
      on Snowflake trial accounts**; the comparison ran on Databricks
      `ai_analyze_sentiment()` instead (200-post sample: 38% exact / 64%
      compatible agreement — see `docs/data_model.md`).
- [x] Acceptance: both models run ✅; Gold populated ✅ (all three targets);
      Snowflake refreshed ✅; docs ✅

## Phase 3 — RAG + Agent ⬜
_LangGraph agent with a swappable retrieval layer (LanceDB vs Cortex Search)._
- [x] `ingestion/resources.py` — **knowledge corpus via Firecrawl**. The agent
      retrieves over public clinical guidance (NIMH / NHS / WHO / CDC / 988),
      **not** the Reddit posts: the guardrail answers in aggregate and never
      quotes an individual, so indexing post text would store exactly what the
      agent must refuse to surface. 20 allowlisted seeds → cleaned, chunked,
      citable documents (URL + title + retrieval date survive chunking).
      Cache-first (re-runs cost 0 credits; `--offline` needs no key at all),
      https + hostname allowlist enforced before any request, per-URL failures
      reported not raised. Free tier is 1,000 credits/month and the seed list
      is ~20 pages. 19 tests against a fake transport — no network.
      ⏳ Needs `FIRECRAWL_API_KEY` in `.env` for the first (cache-cold) build.
- [ ] `rag/retriever.py` — interface + LanceDB + Cortex backends (config-selectable)
- [ ] `rag/tools.py` — sql_metric_tool (whitelisted) + retrieval_tool
- [ ] `rag/agent.py` — routing, Claude API, cited answers, disclaimer + guardrails
- [ ] Acceptance: 5+ varied grounded answers; backend swap via config only;
      refuses individual-level/unsafe requests
      > ⚠️ Constraint discovered 2026-07-04: Cortex AI features are **not
      > available on Snowflake trial accounts**, and the project is
      > zero-spend (no Anthropic API credits). Phase 3 therefore runs
      > LanceDB-only with a config-switchable LLM layer (Anthropic SDK path
      > code-complete; local transformer model for free end-to-end runs).
      > The Cortex retriever stays code-complete but unprovisioned.

## Phase 4 — Dashboard, Eval, Polish ⬜
> The dashboard was brought forward (2026-07-19) and now runs **feature-rich on
> live scored Gold data** (`streamlit run dashboard/app.py`).
- [x] Streamlit dashboard on live Gold (`dashboard/app.py` + `dashboard/data.py`):
      the data seam auto-detects `data/gold/gold_subreddit_weekly.parquet` and
      serves the real 203,293-post aggregates (mock fallback kept for fresh
      clones). Five tabs — 📈 Trends (sentiment + crisis-rate lines with a
      COVID-19 declaration marker), 🦠 COVID-19 impact (per-community pre/post
      Δ-sentiment and Δ-crisis bars + table: sentiment fell in all 6
      communities post-declaration; crisis rate rose in 5/6), 🗓️ Heatmaps
      (diverging sentiment, sequential crisis volume), 👥 Communities
      (overview + drill-down), 💬 Ask (guardrailed preview). Sidebar filters
      (communities, date range, 3-week smoothing), 5 KPIs, CSV export,
      accessibility-validated fixed color mapping. Verified by running
      headless and screenshotting every tab. Streamlit-in-Snowflake deploy
      finalized later in Phase 4.
- [ ] `eval/ragas_eval.py` — ~15 Q&A; faithfulness/relevancy/context P&R; both backends
- [ ] `docs/architecture.md` — finalize diagram + dual-deployment comparison table
- [ ] `docs/interview_narrative.md` — STAR writeup + 6–8 Q&A
- [ ] Finalize README (screenshots, run steps)
