# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Crisis-Signal Classifier (Model B)
# MAGIC A transparent, defensible binary classifier (logistic regression /
# MAGIC gradient boosting) on engineered features: distress-keyword density (from a
# MAGIC documented, conservative lexicon — NOT a black box), sentiment velocity,
# MAGIC posting frequency, post length, time-of-day.
# MAGIC
# MAGIC **Weak supervision:** no ground-truth labels exist, so heuristic labels are
# MAGIC built from the lexicon + thresholds and the model is trained on those. This
# MAGIC is explicitly a weak-supervision BASELINE, documented with all caveats. It
# MAGIC flags posts/cohorts that warrant attention — it is NOT a diagnosis.
# MAGIC
# MAGIC **Status:** stub — implemented in Phase 2. Report feature importances for
# MAGIC explainability; track in MLflow.

# COMMAND ----------

# TODO(Phase 2):
#   * Engineer features; build weak/heuristic labels from the distress lexicon.
#   * Train a transparent classifier; log feature importances to MLflow.
#   * Write crisis_score + crisis_flag into gold_posts_features.

raise NotImplementedError("Crisis classifier is implemented in Phase 2.")
