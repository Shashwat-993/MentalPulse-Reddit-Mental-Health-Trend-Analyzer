# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Features
# MAGIC Silver -> **Gold** curated tables (mirrors `ingestion/transforms.py`):
# MAGIC   * `gold_posts_features` — per-post features; model-score columns are
# MAGIC     typed NULL placeholders that Phase 2 backfills.
# MAGIC   * `gold_subreddit_weekly` — weekly aggregates per subreddit (the
# MAGIC     dashboard's trend table). Unscored signals stay NULL, not 0, so
# MAGIC     consumers can tell "no signal yet" from "signal is zero".

# COMMAND ----------

dbutils.widgets.text("catalog", "mentalpulse")
catalog = dbutils.widgets.get("catalog")
silver_table = f"{catalog}.silver.posts"
posts_table = f"{catalog}.gold.gold_posts_features"
weekly_table = f"{catalog}.gold.gold_subreddit_weekly"

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, DoubleType, StringType

silver = spark.table(silver_table)

gold_posts = silver.select(
    "post_id",
    "subreddit",
    "created_date",
    # date_trunc('week') is Monday-start, matching the local pipeline
    F.date_trunc("week", "created_date").alias("week"),
    "author_hash",
    F.length("text").alias("n_chars"),
    F.size(F.split(F.col("text"), r"\s+")).alias("n_words"),
    F.lit(None).cast(DoubleType()).alias("sentiment_score"),
    F.lit(None).cast(StringType()).alias("sentiment_label"),
    F.lit(None).cast(DoubleType()).alias("crisis_score"),
    F.lit(None).cast(BooleanType()).alias("crisis_flag"),
)

gold_posts.write.format("delta").mode("overwrite").saveAsTable(posts_table)
print(f"{posts_table}: {spark.table(posts_table).count():,} rows")

# COMMAND ----------

weekly = (
    gold_posts.groupBy("subreddit", "week")
    .agg(
        F.count("post_id").alias("n_posts"),
        F.countDistinct("author_hash").alias("n_active_authors"),
        F.round(F.avg("n_words"), 2).alias("avg_word_count"),
        F.avg("sentiment_score").alias("sentiment"),
        # sum over all-NULL booleans is NULL — the honest "not scored yet"
        F.sum(F.col("crisis_flag").cast("int")).alias("crisis_count"),
    )
    .withColumn("crisis_rate", F.col("crisis_count") / F.col("n_posts"))
    .orderBy("subreddit", "week")
)

weekly.write.format("delta").mode("overwrite").saveAsTable(weekly_table)
print(f"{weekly_table}: {spark.table(weekly_table).count():,} rows")
