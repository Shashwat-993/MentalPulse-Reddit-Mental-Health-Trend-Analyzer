# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingest
# MAGIC Land the raw research-corpus CSVs into a **Bronze** Delta table, as-is.
# MAGIC No cleaning or anonymization here — Bronze is the immutable raw landing
# MAGIC zone (and therefore stays private: the corpus contains raw usernames).
# MAGIC
# MAGIC Mirrors `ingestion/load_corpus.py`. Inputs are the corpus CSVs uploaded to
# MAGIC a Unity Catalog volume (from the dev box: the files in `data/raw/`).
# MAGIC
# MAGIC Prereqs (run once by an admin):
# MAGIC ```sql
# MAGIC CREATE CATALOG IF NOT EXISTS mentalpulse;
# MAGIC CREATE SCHEMA  IF NOT EXISTS mentalpulse.bronze;
# MAGIC CREATE SCHEMA  IF NOT EXISTS mentalpulse.silver;
# MAGIC CREATE SCHEMA  IF NOT EXISTS mentalpulse.gold;
# MAGIC CREATE VOLUME  IF NOT EXISTS mentalpulse.bronze.raw;
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("catalog", "mentalpulse")
dbutils.widgets.text("raw_volume", "/Volumes/mentalpulse/bronze/raw")

catalog = dbutils.widgets.get("catalog")
raw_volume = dbutils.widgets.get("raw_volume")
bronze_table = f"{catalog}.bronze.reddit_posts"

# COMMAND ----------

from pyspark.sql import functions as F

RAW_COLUMNS = ["subreddit", "author", "date", "post"]

df = (
    spark.read.option("header", True)
    .option("multiLine", True)
    .option("escape", '"')
    .csv(f"{raw_volume}/*_features_tfidf_256.csv")
    .withColumn("source_file", F.element_at(F.split(F.input_file_name(), "/"), -1))
)

# Keep only the raw post fields; the corpus's ~346 precomputed feature columns
# are re-derived in Phase 2 (see config.yaml `source.keep_feature_columns`).
bronze = (
    df.select(*RAW_COLUMNS, "source_file")
    .withColumnRenamed("date", "created_date")
    # <subreddit>_<period>_features_tfidf_256.csv -> period
    .withColumn("period", F.split(F.col("source_file"), "_").getItem(1))
    # Deterministic id — Spark's null handling in concat_ws differs from the
    # local loader's Python f-string, so ids are platform-internal; they are a
    # dedupe/join key, never compared across the local and Databricks mirrors.
    .withColumn(
        "post_id",
        F.substring(
            F.sha1(F.concat_ws("|", "subreddit", "author", "created_date", "post")),
            1,
            16,
        ),
    )
    .withColumn("ingested_at", F.current_timestamp())
    .select(
        "post_id",
        "subreddit",
        "author",
        "created_date",
        "post",
        "period",
        "source_file",
        "ingested_at",
    )
)

bronze.write.format("delta").mode("overwrite").saveAsTable(bronze_table)
print(f"{bronze_table}: {spark.table(bronze_table).count():,} rows")
