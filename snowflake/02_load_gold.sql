-- ===========================================================================
-- MentalPulse — Load Gold tables into Snowflake
-- DRAFT TEMPLATE — finalized in Phase 1. Proposed simplest reliable path for
-- Databricks Free Edition: export Gold to parquet/CSV, stage it, then COPY INTO.
-- Confirm the approach (and any credit spend) before running. A small Python
-- loader (snowflake-connector-python) will accompany these statements.
-- ===========================================================================

USE ROLE MENTALPULSE_ROLE;
USE WAREHOUSE MENTALPULSE_WH;
USE SCHEMA MENTALPULSE.GOLD;

-- TODO(Phase 1): define table DDL matching the documented Gold schema, e.g.
--   gold_posts_features(post_id, subreddit, created_utc, ... ,
--                       sentiment_score, sentiment_label, crisis_score, crisis_flag)
--   gold_subreddit_daily(subreddit, day, post_volume, avg_score, ...)

-- TODO(Phase 1): internal stage + file format, then COPY INTO from the export.
--   CREATE STAGE IF NOT EXISTS gold_stage;
--   CREATE FILE FORMAT IF NOT EXISTS pq TYPE = PARQUET;
--   PUT file://.../gold_posts_features.parquet @gold_stage;
--   COPY INTO gold_posts_features FROM @gold_stage FILE_FORMAT = (FORMAT_NAME = pq) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
