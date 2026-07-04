"""Load the local Gold parquet mirror into Snowflake (MENTALPULSE.GOLD).

GATED: run ONLY after the load approach + credit spend are approved (see
PROGRESS.md). Executes the statements in ``02_load_gold.sql`` — DDL, PUT to an
internal stage, COPY INTO — using credentials from ``.env``. Prereq: an admin
has run ``01_setup.sql`` and granted MENTALPULSE_ROLE to the user.

The XS warehouse auto-suspends after 60s; a full load of the current Gold
tables (~204k rows) is a few seconds of compute.

Run:
    python -m ingestion.run_pipeline        # ensure data/gold is current
    python snowflake/load_gold.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config.loader import load_config  # noqa: E402

GOLD_FILES = ["gold_posts_features.parquet", "gold_subreddit_weekly.parquet"]


def main() -> None:
    import snowflake.connector  # deferred: heavy dep, only needed here

    cfg = load_config()
    cfg.secrets.require("snowflake_account", "snowflake_user")
    if not (cfg.secrets.snowflake_pat or cfg.secrets.snowflake_password):
        raise RuntimeError("Set SNOWFLAKE_PAT (preferred) or SNOWFLAKE_PASSWORD")

    gold_dir = cfg.path("gold")
    missing = [f for f in GOLD_FILES if not (gold_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing {missing} under {gold_dir} — run `python -m ingestion.run_pipeline`"
        )

    # No role= here: PATs are restricted to the role they were minted with,
    # and Snowflake rejects a different role in the connect string. The SQL
    # script switches to MENTALPULSE_ROLE itself (USE ROLE, first statement).
    conn = snowflake.connector.connect(
        account=cfg.secrets.snowflake_account,
        user=cfg.secrets.snowflake_user,
        password=cfg.secrets.snowflake_pat or cfg.secrets.snowflake_password,
        warehouse=cfg.snowflake.warehouse,
    )
    try:
        sql = (REPO_ROOT / "snowflake" / "02_load_gold.sql").read_text()
        # Make the PUT file paths absolute for this machine.
        sql = sql.replace("file://data/gold/", f"file://{gold_dir}/")

        from io import StringIO

        from snowflake.connector.util_text import split_statements

        with conn.cursor() as cur:
            for stmt, _ in split_statements(StringIO(sql), remove_comments=True):
                try:
                    cur.execute(stmt)
                    print(f"[ok] {stmt.splitlines()[0][:80]}")
                except snowflake.connector.errors.ProgrammingError as exc:
                    # PAT sessions are pinned to the role the token was minted
                    # with and reject USE ROLE; continue as that role.
                    if "USE ROLE not allowed" in str(exc):
                        print(f"[skip] {stmt.strip()[:60]} (PAT role-restricted session)")
                    else:
                        raise
        with conn.cursor() as cur:
            for table in ("GOLD_POSTS_FEATURES", "GOLD_SUBREDDIT_WEEKLY"):
                cur.execute(f"SELECT COUNT(*) FROM MENTALPULSE.GOLD.{table}")
                print(f"{table}: {cur.fetchone()[0]:,} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
