"""Agent tools (Phase 3).

Two tools the LangGraph agent can call:

  * ``sql_metric_tool`` — runs PARAMETERIZED / whitelisted queries against the
    Snowflake Gold tables for quantitative questions ("which subreddit had the
    biggest anxiety spike in March?"). No arbitrary SQL — only vetted templates.
  * ``retrieval_tool`` — calls the active Retriever (see ``rag/retriever.py``)
    for qualitative/context questions.

Both are constrained to aggregated, anonymized data only.
"""

from __future__ import annotations

from config.loader import Config


def sql_metric_tool(cfg: Config):
    """Build the quantitative metric tool over Snowflake Gold. Implemented in Phase 3.

    Uses a whitelist of parameterized query templates — never arbitrary SQL.
    """
    raise NotImplementedError("Implemented in Phase 3.")


def retrieval_tool(cfg: Config):
    """Build the qualitative retrieval tool over the active Retriever. Phase 3."""
    raise NotImplementedError("Implemented in Phase 3.")
