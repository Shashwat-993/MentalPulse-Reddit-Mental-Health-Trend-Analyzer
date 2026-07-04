# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Crisis-Signal Classifier (Model B)
# MAGIC Weak-supervision BASELINE, mirrored from `ml/crisis.py` (source of truth).
# MAGIC
# MAGIC * Weak labels from a documented, conservative two-tier distress lexicon
# MAGIC   (one ACUTE phrase, or two distinct SEVERE terms ⇒ label 1).
# MAGIC * Transparent logistic regression on engineered features that deliberately
# MAGIC   exclude the ACUTE tier (severe-term density, first-person focus,
# MAGIC   negations, Model A sentiment, length) — the model generalizes the
# MAGIC   heuristic instead of copying it. Coefficients logged as importances.
# MAGIC * The corpus has ~1 post per author per window and date-only timestamps,
# MAGIC   so per-author velocity/frequency/time-of-day features are not
# MAGIC   computable — documented as dropped.
# MAGIC
# MAGIC This flags aggregate cohort trends. It is explicitly **NOT a diagnosis**
# MAGIC and individual posts are never surfaced. Run notebook 04 first
# MAGIC (features include `sentiment_score`).

# COMMAND ----------

dbutils.widgets.text("catalog", "mentalpulse")
catalog = dbutils.widgets.get("catalog")

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

import mlflow
from pyspark.sql import functions as F

from config.loader import load_config
from ml.crisis import build_features, train_and_score, weak_labels

cfg = load_config()
threshold = float(cfg.ml.crisis.weak_label_threshold)

# COMMAND ----------

silver = spark.table(f"{catalog}.silver.posts").select("post_id", "text").toPandas()
gold_pd = (
    spark.table(f"{catalog}.gold.gold_posts_features")
    .select("post_id", "sentiment_score")
    .toPandas()
)

mlflow.set_experiment(cfg.ml.mlflow_experiment)
with mlflow.start_run(run_name="crisis-classifier"):
    labels = weak_labels(silver["text"])
    features = build_features(silver, gold_pd)
    scores, report = train_and_score(features, labels, threshold=threshold)
    coefficients = report.pop("coefficients")
    mlflow.log_params({"classifier": "logistic_regression(balanced)", "threshold": threshold})
    mlflow.log_metrics({**report, "flag_rate": float(scores["crisis_flag"].mean())})
    mlflow.log_dict(coefficients, "feature_importances.json")

# COMMAND ----------

scores_sdf = spark.createDataFrame(scores)
gold = (
    spark.table(f"{catalog}.gold.gold_posts_features")
    .drop("crisis_score", "crisis_flag")
    .join(scores_sdf, "post_id", "left")
)
gold.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.gold.gold_posts_features"
)

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

print("crisis scores written to gold_posts_features + weekly refreshed")
