# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingest
# MAGIC Land the raw Reddit parquet (from `ingestion/fetch_posts.py`) into a
# MAGIC **Bronze** Delta table, as-is. No cleaning or anonymization here — Bronze
# MAGIC is the immutable raw landing zone.
# MAGIC
# MAGIC **Status:** stub — implemented in Phase 1.

# COMMAND ----------

# TODO(Phase 1):
#   * Read parquet from the Bronze volume / path.
#   * Write to a Bronze Delta table (e.g. mentalpulse.bronze.reddit_posts).
#   * Keep raw fields verbatim; anonymization is deferred to 02_silver_clean.

raise NotImplementedError("Bronze ingest is implemented in Phase 1.")
