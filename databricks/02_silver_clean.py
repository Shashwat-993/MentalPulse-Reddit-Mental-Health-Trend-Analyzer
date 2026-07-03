# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Clean
# MAGIC Bronze -> **Silver**: drop deleted/empty posts, normalize text, anonymize,
# MAGIC parse dates, dedupe — then **prove** zero raw usernames survived before
# MAGIC the table is written.
# MAGIC
# MAGIC Mirrors `ingestion/transforms.bronze_to_silver`; the PII patterns are
# MAGIC imported from `ingestion/anonymize.py` (run this notebook from a
# MAGIC Databricks Repos checkout so the repo is importable) — one source of
# MAGIC truth for what counts as PII.
# MAGIC
# MAGIC **Ground rule:** raw usernames MUST NOT survive into Silver. The salt
# MAGIC comes from a Databricks secret scope, never from code or config.

# COMMAND ----------

dbutils.widgets.text("catalog", "mentalpulse")
catalog = dbutils.widgets.get("catalog")
bronze_table = f"{catalog}.bronze.reddit_posts"
silver_table = f"{catalog}.silver.posts"

salt = dbutils.secrets.get(scope="mentalpulse", key="hash_salt")
assert salt, "Set the hash_salt secret: databricks secrets put-secret mentalpulse hash_salt"

# COMMAND ----------

import os
import sys

# Notebooks in a Databricks Repos checkout run with cwd = databricks/; put the
# repo root on sys.path so the ingestion package is importable.
sys.path.insert(0, os.path.abspath(".."))

from pyspark.sql import functions as F, Window

from ingestion.anonymize import DROP_COLUMNS, PII_PATTERNS, REDACTION_TEMPLATE
from ingestion.transforms import DELETED_MARKERS

# COMMAND ----------

bronze = spark.table(bronze_table)

# 1. normalize whitespace; drop empty/[deleted]/[removed] posts
text = F.trim(F.regexp_replace(F.col("post"), r"\s+", " "))
silver = (
    bronze.withColumn("text", text)
    .where(F.col("text").isNotNull() & (F.col("text") != ""))
    .where(~F.col("text").isin(*DELETED_MARKERS))
)

# 2. anonymize: salted SHA-256 author hash; drop raw identifier columns
silver = silver.withColumn(
    "author_hash",
    F.when(
        F.col("author").isNotNull(),
        F.sha2(F.concat(F.lit(f"{salt}:"), F.col("author")), 256),
    ),
).drop("post", *DROP_COLUMNS)

# 3. scrub PII from text — same patterns, same order, as ingestion/anonymize.py
for kind, pattern in PII_PATTERNS.items():
    silver = silver.withColumn(
        "text",
        F.regexp_replace("text", pattern.pattern, REDACTION_TEMPLATE.format(kind=kind)),
    )

# 4. parse dates; drop unparseable
silver = silver.withColumn(
    "created_date", F.to_date("created_date", "yyyy/MM/dd")
).where(F.col("created_date").isNotNull())

# 5. dedupe by post_id (earliest period alphabetically, for determinism)
dedupe = Window.partitionBy("post_id").orderBy("period", "source_file")
silver = (
    silver.withColumn("_rn", F.row_number().over(dedupe))
    .where(F.col("_rn") == 1)
    .select(
        "post_id",
        "subreddit",
        "created_date",
        "author_hash",
        "text",
        "period",
        "source_file",
        "ingested_at",
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verification — zero raw usernames in Silver (blocking)

# COMMAND ----------

leaked_columns = [c for c in DROP_COLUMNS if c in silver.columns]
assert not leaked_columns, f"Raw identifier column(s) survived: {leaked_columns}"

unhashed = (
    silver.select(F.col("author_hash").alias("value"))
    .join(bronze.select(F.col("author").alias("value")).distinct(), "value", "inner")
    .count()
)
assert unhashed == 0, f"{unhashed} raw author value(s) present in author_hash"

for kind, pattern in PII_PATTERNS.items():
    hits = silver.where(F.col("text").rlike(pattern.pattern)).count()
    assert hits == 0, f"{hits} unscrubbed {kind} pattern(s) remain in text"

print("verification passed: raw columns dropped, 0 raw authors, 0 PII patterns")

# COMMAND ----------

silver.write.format("delta").mode("overwrite").saveAsTable(silver_table)
print(f"{silver_table}: {spark.table(silver_table).count():,} rows")
