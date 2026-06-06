"""LangGraph agent over the MentalPulse data (Phase 3).

Routes a question to the right tool(s) — `sql_metric_tool` for quantitative
questions, `retrieval_tool` for qualitative ones — calls the Claude API via the
official Anthropic SDK, and synthesizes an answer that cites which Gold tables /
aggregates it used.

The system prompt (see `rag/prompts.py`) carries the not-a-clinical-tool
disclaimer and the guardrails that forbid surfacing individual-user content or
re-identifying quotes. The model id is read from the environment
(ANTHROPIC_MODEL); pull the current model name from the official Anthropic docs.
"""

from __future__ import annotations

from config.loader import Config


def build_agent(cfg: Config):
    """Construct the LangGraph agent (tools + Claude API + guardrails). Phase 3."""
    raise NotImplementedError("Implemented in Phase 3.")


def answer(cfg: Config, question: str) -> str:
    """Answer a natural-language question with a grounded, cited response. Phase 3.

    Declines requests for individual-level data or anything outside the
    aggregated dataset (see rag/prompts.py REFUSAL_MESSAGE).
    """
    raise NotImplementedError("Implemented in Phase 3.")
