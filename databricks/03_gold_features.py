# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Features
# MAGIC Silver -> **Gold** curated tables:
# MAGIC   * `gold_posts_features` — per-post features (token counts, posting hour,
# MAGIC     sentiment placeholder, crisis placeholder — model scores filled in Phase 2).
# MAGIC   * `gold_subreddit_daily` — daily aggregates per subreddit (post volume,
# MAGIC     avg score, etc.; sentiment trend added in Phase 2).
# MAGIC
# MAGIC **Status:** stub — feature engineering implemented in Phase 1; model score
# MAGIC columns populated in Phase 2.

# COMMAND ----------

# TODO(Phase 1): build the two Gold tables with the documented schema.
# TODO(Phase 2): backfill sentiment_score/label + crisis_score/flag columns.

raise NotImplementedError("Gold features are implemented in Phase 1/2.")
