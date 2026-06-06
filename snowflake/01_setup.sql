-- ===========================================================================
-- MentalPulse — Snowflake setup (warehouse, database, schema, role, grants)
-- DRAFT TEMPLATE — finalized and run in Phase 1, and ONLY after you approve the
-- Databricks->Snowflake load approach and any credit spend. Review before running.
-- ===========================================================================

-- Extra-small warehouse, auto-suspend to minimize credit usage.
CREATE WAREHOUSE IF NOT EXISTS MENTALPULSE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'MentalPulse XS warehouse (cost-controlled)';

CREATE DATABASE IF NOT EXISTS MENTALPULSE
  COMMENT = 'MentalPulse curated Gold tables + Cortex Search corpus';

CREATE SCHEMA IF NOT EXISTS MENTALPULSE.GOLD
  COMMENT = 'Curated Gold tables loaded from the Databricks lakehouse';

-- Dedicated role + least-privilege grants (run as a role that can manage grants).
CREATE ROLE IF NOT EXISTS MENTALPULSE_ROLE;
GRANT USAGE   ON WAREHOUSE MENTALPULSE_WH    TO ROLE MENTALPULSE_ROLE;
GRANT USAGE   ON DATABASE  MENTALPULSE       TO ROLE MENTALPULSE_ROLE;
GRANT USAGE   ON SCHEMA    MENTALPULSE.GOLD  TO ROLE MENTALPULSE_ROLE;
GRANT CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT
  ON SCHEMA MENTALPULSE.GOLD TO ROLE MENTALPULSE_ROLE;

-- TODO(Phase 1): GRANT ROLE MENTALPULSE_ROLE TO USER <your_user>;
