-- ===========================================================================
-- MentalPulse — Snowflake Cortex Search service over the anonymized corpus
-- DRAFT TEMPLATE — built in Phase 3. Cortex Search spends credits: confirm
-- before building and START SMALL (tiny sample first).
--
-- The corpus is AGGREGATED + ANONYMIZED text only — never individual-user
-- content that could re-identify someone.
-- ===========================================================================

USE ROLE MENTALPULSE_ROLE;
USE WAREHOUSE MENTALPULSE_WH;
USE SCHEMA MENTALPULSE.GOLD;

-- TODO(Phase 3):
--   * Build the anonymized text corpus table from Gold (no re-identifying content).
--   * CREATE CORTEX SEARCH SERVICE over it (start with a small sample).
--   * The CortexRetriever (rag/retriever.py) queries this service.
