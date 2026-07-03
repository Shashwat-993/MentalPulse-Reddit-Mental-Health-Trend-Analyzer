# MentalPulse — Data Model

Column-level contracts for the medallion layers. The pandas transforms in
`ingestion/transforms.py` are the source of truth; the Databricks notebooks
(`databricks/01–03`) and dbt models (`dbt/mentalpulse/`) mirror them and must
be updated together with this document.

**Source:** Low et al., *Reddit Mental Health Dataset* (Zenodo record 3941387,
ODC-PDDL). Configured subset (`config/config.yaml`): 6 subreddits
(mentalhealth, anxiety, depression, adhd, bipolarreddit, suicidewatch) × 2
collection windows (`pre` ≈ Dec 2018–Dec 2019, `post` = Jan–Apr 2020) —
203,293 posts, Nov 2018–Apr 2020, ~1 post per author per window.

## Bronze — `data/bronze/reddit_posts/` · `mentalpulse.bronze.reddit_posts`

Immutable raw landing zone. **Contains raw usernames** (verified at ingestion —
the corpus is *not* de-identified at the author level), so Bronze never leaves
the dev box / workspace: `data/` is gitignored and the Delta table is
access-restricted.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `post_id` | string (16 hex) | Derived at landing: `sha1(subreddit\|author\|date\|post)[:16]`. Dedupe/join key; platform-internal (local and Spark ids are not comparable). |
| `subreddit` | string | Community, as shipped (lowercase). |
| `author` | string | **RAW Reddit username, as shipped.** Hashed + dropped in Silver. |
| `created_date` | string | Post date as shipped (`YYYY/MM/DD`). |
| `post` | string | Raw post text (title + body, as concatenated by the corpus). |
| `period` | string | Corpus collection window (`2018`/`2019`/`pre`/`post`). |
| `source_file` | string | Originating corpus CSV (lineage). |
| `ingested_at` | timestamp | UTC landing time. |

The corpus's ~346 precomputed feature columns (readability/LIWC/tf-idf) are
not landed; Phase 2 derives its own features from text.

## Silver — `data/silver/posts.parquet` · `mentalpulse.silver.posts`

Clean, de-identified posts — the first shareable layer. Rules (in order):
drop empty/`[deleted]`/`[removed]` text → normalize whitespace → anonymize
(salted-SHA-256 `author_hash`, drop raw identifier columns, scrub PII:
emails, URLs, `u/` handles, `@` mentions, phone numbers) → parse dates →
dedupe by `post_id`. Every run must pass `ingestion.anonymize.assert_anonymized`
(zero raw usernames, zero unscrubbed PII) or Silver is not written.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `post_id` | string | Unique (tested in dbt + pytest). |
| `subreddit` | string | `accepted_values` tested against the configured list. |
| `created_date` | date | Parsed; unparseable rows dropped. |
| `author_hash` | string (64 hex) | Salted SHA-256 pseudonym (`MENTALPULSE_HASH_SALT`). Stable across runs; never a raw username. |
| `text` | string | Normalized + PII-scrubbed (`[REDACTED:<kind>]` markers). |
| `period`, `source_file`, `ingested_at` | | Lineage, carried from Bronze. |

## Gold — `data/gold/` · `mentalpulse.gold.*`

### `gold_posts_features` (per-post)

| Column | Type | Notes |
| ------ | ---- | ----- |
| `post_id` | string | Unique. |
| `subreddit` | string | |
| `created_date` | date | |
| `week` | date/timestamp | Monday-start week (`W-SUN` period start ≙ Spark `date_trunc('week')`). |
| `author_hash` | string | |
| `n_chars` | int | Length of cleaned text. |
| `n_words` | int | Whitespace-token count. |
| `sentiment_score` | float, nullable | **NULL until Phase 2** (transformer sentiment). |
| `sentiment_label` | string, nullable | NULL until Phase 2. |
| `crisis_score` | float, nullable | NULL until Phase 2 (weak-supervision classifier). |
| `crisis_flag` | boolean, nullable | NULL until Phase 2. |

### `gold_subreddit_weekly` (aggregate trends — the dashboard table)

| Column | Type | Notes |
| ------ | ---- | ----- |
| `subreddit` | string | |
| `week` | date/timestamp | Monday-start. |
| `n_posts` | int | |
| `n_active_authors` | int | Distinct `author_hash` (≈ `n_posts` in this corpus: ~1 post/author/window). |
| `avg_word_count` | float | |
| `sentiment` | float, nullable | Mean `sentiment_score`; **NULL (not 0) until Phase 2** — "no signal yet" is distinguishable from "signal is zero". |
| `crisis_count` | int, nullable | NULL until Phase 2. |
| `crisis_rate` | float, nullable | `crisis_count / n_posts`; NULL until Phase 2. |

## Snowflake (Phase 1/2 — gated)

Gold tables are loaded into `MENTALPULSE.GOLD` (see `snowflake/01_setup.sql`,
`02_load_gold.sql`, `load_gold.py`) once the approach/credits are approved.
Only curated, de-identified data ever leaves the lakehouse — never Bronze and
never raw identifiers. (The Phase 3 Cortex retrieval corpus will be a
dedicated curated table of anonymized text, built under the same rule.)
