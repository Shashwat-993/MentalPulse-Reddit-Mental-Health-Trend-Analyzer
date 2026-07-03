-- ===========================================================================
-- MentalPulse — Load Gold tables into Snowflake
-- GATED: run ONLY after the load approach + credit spend are approved (see
-- PROGRESS.md). Path: export Gold parquet (the local mirror under data/gold/,
-- or a Databricks export), PUT to an internal stage, COPY INTO.
-- `snowflake/load_gold.py` executes exactly these statements from Python.
-- Schema mirrors docs/data_model.md — update both together.
-- ===========================================================================

USE ROLE MENTALPULSE_ROLE;
USE WAREHOUSE MENTALPULSE_WH;
USE SCHEMA MENTALPULSE.GOLD;

CREATE TABLE IF NOT EXISTS GOLD_POSTS_FEATURES (
  POST_ID          VARCHAR(16)   NOT NULL,
  SUBREDDIT        VARCHAR       NOT NULL,
  CREATED_DATE     DATE          NOT NULL,
  WEEK             DATE          NOT NULL,
  AUTHOR_HASH      VARCHAR(64),
  N_CHARS          INTEGER       NOT NULL,
  N_WORDS          INTEGER       NOT NULL,
  SENTIMENT_SCORE  FLOAT,          -- NULL until Phase 2
  SENTIMENT_LABEL  VARCHAR,        -- NULL until Phase 2
  CRISIS_SCORE     FLOAT,          -- NULL until Phase 2
  CRISIS_FLAG      BOOLEAN         -- NULL until Phase 2
);

CREATE TABLE IF NOT EXISTS GOLD_SUBREDDIT_WEEKLY (
  SUBREDDIT        VARCHAR       NOT NULL,
  WEEK             DATE          NOT NULL,
  N_POSTS          INTEGER       NOT NULL,
  N_ACTIVE_AUTHORS INTEGER       NOT NULL,
  AVG_WORD_COUNT   FLOAT,
  SENTIMENT        FLOAT,          -- NULL until Phase 2
  CRISIS_COUNT     INTEGER,        -- NULL until Phase 2
  CRISIS_RATE      FLOAT           -- NULL until Phase 2
);

CREATE STAGE IF NOT EXISTS GOLD_STAGE;
CREATE FILE FORMAT IF NOT EXISTS PQ TYPE = PARQUET;

-- Idempotent reload: truncate, stage, copy, clean up.
TRUNCATE TABLE IF EXISTS GOLD_POSTS_FEATURES;
TRUNCATE TABLE IF EXISTS GOLD_SUBREDDIT_WEEKLY;
PUT file://data/gold/gold_posts_features.parquet   @GOLD_STAGE AUTO_COMPRESS = FALSE;
PUT file://data/gold/gold_subreddit_weekly.parquet @GOLD_STAGE AUTO_COMPRESS = FALSE;
COPY INTO GOLD_POSTS_FEATURES
  FROM @GOLD_STAGE/gold_posts_features.parquet
  FILE_FORMAT = (FORMAT_NAME = PQ) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
COPY INTO GOLD_SUBREDDIT_WEEKLY
  FROM @GOLD_STAGE/gold_subreddit_weekly.parquet
  FILE_FORMAT = (FORMAT_NAME = PQ) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
REMOVE @GOLD_STAGE;
