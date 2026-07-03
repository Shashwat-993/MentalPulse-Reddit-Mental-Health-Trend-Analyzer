# dbt (dbt-databricks)

The dbt project in `dbt/mentalpulse/` re-expresses the Silver and Gold
transforms (`ingestion/transforms.py` — the source of truth for the rules) as
tested SQL models over the Bronze Delta table landed by
`databricks/01_bronze_ingest.py`.

Models:

- `silver_posts` — clean + de-identify Bronze (salted-hash author, PII scrub
  via the `scrub_pii` macro, dedupe, date parsing)
- `gold_posts_features` — per-post features; Phase 2 model-score placeholders
- `gold_subreddit_weekly` — weekly aggregate trends (the dashboard's table)

Tests: `not_null` / `unique` on `post_id`, `accepted_values` on `subreddit`
(mirrors `config/config.yaml`), `not_null` on dates/weeks/counts.

## Running

Connection settings come from the environment (`.env`) — `DATABRICKS_HOST`,
`DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH` — plus `MENTALPULSE_HASH_SALT` for
the Silver author hashing. Never commit credentials.

```bash
cd dbt/mentalpulse
dbt debug --profiles-dir .     # check connection
dbt run   --profiles-dir .     # build silver + gold
dbt test  --profiles-dir .     # schema tests
```

Prereq: the Bronze table exists (run `databricks/01_bronze_ingest.py` once
after uploading the corpus CSVs to the `mentalpulse.bronze.raw` volume).
`target/`, `dbt_packages/`, and `logs/` are gitignored.
