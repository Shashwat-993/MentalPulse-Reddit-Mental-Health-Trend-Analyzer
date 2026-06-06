# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Clean
# MAGIC Bronze -> **Silver**: anonymize, dedupe, drop deleted/removed/empty,
# MAGIC normalize text, enforce a clean schema.
# MAGIC
# MAGIC **Ground rule:** raw usernames MUST NOT survive into Silver. The notebook
# MAGIC applies `ingestion/anonymize.py` and asserts zero raw usernames remain.
# MAGIC
# MAGIC **Status:** stub — implemented in Phase 1.

# COMMAND ----------

# TODO(Phase 1):
#   * Hash author ids (salted SHA-256), drop raw author / author_fullname.
#   * Strip PII (emails, phones, @handles, URLs) from title/body.
#   * Dedupe by post_id; drop [deleted]/[removed]/empty bodies.
#   * Normalize text; write Silver Delta table + run the no-raw-usernames check.

raise NotImplementedError("Silver clean is implemented in Phase 1.")
