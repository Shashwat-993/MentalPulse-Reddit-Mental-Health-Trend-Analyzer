# dbt (dbt-databricks)

The dbt project lives under `dbt/mentalpulse/` and is initialized in **Phase 1**:

```bash
cd dbt
dbt init mentalpulse            # adapter: databricks
```

Phase 1 re-expresses the Silver and Gold transforms as dbt models with tests:

- `not_null` / `unique` on key columns (e.g. `post_id`)
- `accepted_values` on `subreddit`

`profiles.yml` reads Databricks connection settings from the environment
(`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH`) — never commit
credentials. `target/`, `dbt_packages/`, and `logs/` are gitignored.
