"""MentalPulse dashboard (Streamlit). Implemented in Phase 4.

Primary target: Streamlit-in-Snowflake. A local-Streamlit fallback (hitting
Snowflake) is documented for when Free Edition / plan limits get in the way.

Planned panels:
  * Subreddit sentiment trends over time
  * Crisis-signal volume over time (AGGREGATE ONLY — never individual content)
  * A chat box wired to the RAG agent (rag/agent.py)
  * A visible disclaimer banner (this is NOT a clinical tool)

Status: stub. Run with `streamlit run snowflake/04_streamlit_app.py` once built.
"""

from __future__ import annotations

# The disclaimer is shared from rag/prompts.py so the dashboard, README, and
# agent all show the same language.
DISCLAIMER_TODO = (
    "Research/portfolio project. NOT a diagnostic or crisis-intervention tool. "
    "Reports aggregate trends only — never individual users."
)


def main() -> None:
    # TODO(Phase 4): build the Streamlit app (trends, aggregate crisis volume,
    # agent chat, disclaimer banner). Import DISCLAIMER from rag.prompts.
    raise NotImplementedError("Dashboard is implemented in Phase 4.")


if __name__ == "__main__":
    main()
