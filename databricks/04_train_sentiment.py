# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Sentiment Scorer (Model A)
# MAGIC Score each Silver post with a pretrained transformer sentiment/emotion
# MAGIC model (feature generation, not training from scratch). Writes a per-post
# MAGIC sentiment score + label into `gold_posts_features` and a week-over-week
# MAGIC trend into `gold_subreddit_daily`. Tracked in MLflow.
# MAGIC
# MAGIC **Status:** stub — implemented in Phase 2. Document the model choice and
# MAGIC its limits.

# COMMAND ----------

# TODO(Phase 2):
#   * Load the configured HF model (see config.yaml ml.sentiment_model).
#   * Score Silver posts; log params/metrics/artifacts to MLflow.
#   * Write scores back to Gold.

raise NotImplementedError("Sentiment scoring is implemented in Phase 2.")
