# MentalPulse — Architecture

> Living document. The high-level design is below; the dual-deployment
> comparison table is filled in with real Ragas numbers in Phase 4.

## What it is

An end-to-end mental-health **trend-intelligence** platform over public Reddit
communities, demonstrating the modern data stack: ingestion → medallion
lakehouse → ML → enterprise warehouse → semantic retrieval → agentic RAG →
dashboard.

> **Disclaimer:** Research/portfolio project. NOT a diagnostic or
> crisis-intervention tool. Reports aggregate trends only — never individuals.

## High-level data flow

```mermaid
flowchart LR
    R[Reddit research corpus<br/>Low et al. / GoEmotions] --> B[Bronze Delta<br/>raw landed]
    B --> S[Silver Delta<br/>anonymized + cleaned]
    S --> G[Gold Delta<br/>features + daily aggregates]
    G -->|sentiment + crisis scores| G
    G --> SF[(Snowflake<br/>curated Gold)]
    SF --> CX[Cortex Search<br/>enterprise retrieval]
    G --> LV[LanceDB<br/>open-source retrieval]
    CX --> AG{{LangGraph agent<br/>+ Claude API}}
    LV --> AG
    SF --> AG
    AG --> DASH[Streamlit dashboard]

    subgraph Databricks (Free Edition)
        B
        S
        G
    end

    subgraph ML [MLflow-tracked models]
        M1[Sentiment scorer<br/>pretrained transformer]
        M2[Crisis classifier<br/>weak-supervision baseline]
    end
    S --> M1 --> G
    S --> M2 --> G
```

> **Source note:** Phase 1 ingests a pre-collected, already-anonymized Reddit
> research corpus (Low et al.'s Reddit Mental Health Dataset; GoEmotions
> fallback) instead of the live Reddit API — no approval gate, identical
> downstream pipeline. A live API source (e.g. Bluesky) can be added later.

## Medallion layers

| Layer  | Contents | Notes |
| ------ | -------- | ----- |
| Bronze | Raw Reddit posts + comments (from the research corpus) | Immutable landing zone. |
| Silver | Anonymized, deduped, cleaned | Raw usernames dropped/hashed here — they never reach Silver. PII stripped. |
| Gold   | `gold_posts_features`, `gold_subreddit_daily` | Per-post features + daily subreddit aggregates; model scores added in Phase 2. |

## Models (Phase 2)

- **Sentiment scorer (A):** pretrained transformer for social text; feature
  generation, not trained from scratch. Tracked in MLflow.
- **Crisis-signal classifier (B):** transparent classifier on engineered
  features (distress-keyword density from a documented conservative lexicon,
  sentiment velocity, posting frequency, length, time-of-day). Labels are
  **weak-supervision** heuristics — a documented baseline, explicitly NOT a
  diagnosis. Feature importances reported for explainability.

## Dual-deployment comparison (filled in Phase 4)

The same retrieval interface (`rag/retriever.py`) has two backends so we can
compare open-source vs enterprise head-to-head:

| Dimension | LanceDB (open-source) | Snowflake Cortex Search (enterprise) |
| --------- | --------------------- | ------------------------------------ |
| Cost | _TBD_ | _TBD_ |
| Setup effort | _TBD_ | _TBD_ |
| Latency | _TBD_ | _TBD_ |
| Retrieval quality (Ragas) | _TBD_ | _TBD_ |

## Responsible data use

Public data only; anonymize at ingestion; aggregate, never expose individuals;
not a clinical tool. Phase 1 uses a licensed, already-anonymized Reddit research
corpus (no live scraping); a live API path would require Reddit's Responsible
Builder Policy pre-approval and is deferred. See the README's "Responsible Data
Use" section.
