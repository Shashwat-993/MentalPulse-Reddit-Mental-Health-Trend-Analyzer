# MentalPulse — Interview Narrative

> Skeleton. Filled in during Phase 4 with concrete numbers and outcomes. Use it
> to rehearse explaining the project end-to-end.

## STAR summary

- **Situation:** _TBD_ — why a mental-health trend platform; the portfolio goal
  of demonstrating the full modern data stack for DE / DS-ML / GenAI roles.
- **Task:** _TBD_ — ingest public Reddit data responsibly, detect emotional /
  crisis trends with two models, and answer plain-English questions via a RAG
  agent, surfaced in a dashboard.
- **Action:** _TBD_ — medallion lakehouse on Databricks, dbt transforms+tests,
  two MLflow-tracked models, curated Gold in Snowflake, a swappable retriever
  (LanceDB vs Cortex Search), a LangGraph + Claude agent, Streamlit dashboard.
- **Result:** _TBD_ — working pipeline, Ragas backend comparison, dashboard.

## Likely interview questions (answers filled in Phase 4)

1. **Why a medallion (Bronze/Silver/Gold) architecture?** _TBD_
2. **Why two models, and why frame the crisis model as weak supervision?** _TBD_
   (no ground-truth labels → heuristic labels from a documented lexicon; a
   defensible baseline, explicitly not a diagnosis; feature importances for
   explainability.)
3. **Why a swappable retriever, and what did the Ragas comparison show?** _TBD_
4. **What are the responsible-AI choices and why?** _TBD_ (public data only;
   anonymize at ingestion; aggregate-only outputs; not a clinical tool.)
5. **Cost tradeoffs (Databricks Free Edition, Snowflake credits, local mirror)?**
   _TBD_
6. **How does the agent stay grounded and refuse unsafe requests?** _TBD_
7. **How would this scale / what would you change for production?** _TBD_
8. **What broke and how did you debug it?** _TBD_
