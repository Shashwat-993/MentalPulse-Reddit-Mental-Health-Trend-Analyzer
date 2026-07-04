# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Sentiment Scorer (Model A)
# MAGIC Score each Silver post with the configured pretrained transformer
# MAGIC (`config.yaml ml.sentiment_model`) — feature generation with a published
# MAGIC model, not training from scratch. Mirrors `ml/sentiment.py` (the local
# MAGIC runner, which is the source of truth for the scoring logic).
# MAGIC
# MAGIC Model: `cardiffnlp/twitter-roberta-base-sentiment-latest` (3-class).
# MAGIC `sentiment_score = P(positive) − P(negative) ∈ [−1, 1]`;
# MAGIC `sentiment_label = argmax`. Limits: Twitter-trained (short informal text;
# MAGIC posts are truncated), English-only, no sarcasm/context awareness —
# MAGIC documented in `docs/data_model.md`.
# MAGIC
# MAGIC Requires an ML runtime cluster (transformers + torch). Tracked in MLflow.

# COMMAND ----------

dbutils.widgets.text("catalog", "mentalpulse")
catalog = dbutils.widgets.get("catalog")

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

import mlflow
import pandas as pd
from pyspark.sql import functions as F

from config.loader import load_config
from ml.sentiment import SentimentScorer, score_frame

cfg = load_config()
model_name = cfg.ml.sentiment_model

# COMMAND ----------

silver = spark.table(f"{catalog}.silver.posts").select("post_id", "text").toPandas()

mlflow.set_experiment(cfg.ml.mlflow_experiment)
with mlflow.start_run(run_name="sentiment-scorer"):
    scorer = SentimentScorer(model_name, batch_size=64, max_length=256)
    mlflow.log_params(
        {
            "model": model_name,
            "batch_size": 64,
            "max_length": 256,
            "quantized_int8": scorer.quantized,
            "n_input_posts": len(silver),
        }
    )
    scores = score_frame(silver, scorer)
    mlflow.log_metrics(
        {
            "n_scored": len(scores),
            "mean_sentiment": float(scores["sentiment_score"].mean()),
        }
    )

# COMMAND ----------

# Merge scores into the Gold per-post table (schema unchanged — the columns
# exist as typed NULL placeholders from notebook 03 / dbt).
scores_sdf = spark.createDataFrame(scores)
gold = (
    spark.table(f"{catalog}.gold.gold_posts_features")
    .drop("sentiment_score", "sentiment_label")
    .join(scores_sdf, "post_id", "left")
)
gold.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.gold.gold_posts_features"
)

# Refresh the weekly aggregate table (same aggregation as notebook 03).
spark.table(f"{catalog}.gold.gold_posts_features").groupBy("subreddit", "week").agg(
    F.count("post_id").alias("n_posts"),
    F.countDistinct("author_hash").alias("n_active_authors"),
    F.round(F.avg("n_words"), 2).alias("avg_word_count"),
    F.avg("sentiment_score").alias("sentiment"),
    F.sum(F.col("crisis_flag").cast("int")).alias("crisis_count"),
).withColumn("crisis_rate", F.col("crisis_count") / F.col("n_posts")).orderBy(
    "subreddit", "week"
).write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.gold.gold_subreddit_weekly"
)

print("sentiment scores written to gold_posts_features + weekly refreshed")
