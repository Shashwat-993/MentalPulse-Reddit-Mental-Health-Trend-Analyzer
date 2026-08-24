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
    S --> G[Gold Delta<br/>features + weekly aggregates]
    G -->|sentiment + crisis scores| G
    G --> SF[(Snowflake<br/>curated Gold)]
    FC[Public health guidance<br/>NIMH / NHS / WHO / CDC] -->|Firecrawl scrape| KC[Knowledge corpus<br/>chunked + citable]
    KC --> CX[Cortex Search<br/>enterprise retrieval]
    KC --> LV[LanceDB<br/>open-source retrieval]
    CX --> AG{{LangGraph agent<br/>+ Claude API}}
    LV --> AG
    SF -->|metric tool: the numbers| AG
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

> **Source note:** Phase 1 ingests a pre-collected Reddit research corpus
> (Low et al.'s Reddit Mental Health Dataset, Zenodo 3941387, ODC-PDDL;
> GoEmotions fallback) instead of the live Reddit API — no approval gate,
> identical downstream pipeline. Inspection at ingestion time showed the corpus
> **contains raw usernames**, so de-identification genuinely happens in our
> Bronze→Silver step (it is enforced and verified, not assumed). A live API
> source (e.g. Bluesky) can be added later.

## What the agent retrieves over (and what it deliberately does not)

The retrieval corpus is **public clinical guidance, not the Reddit posts.**

Indexing post text is the obvious move and the wrong one here. The agent's hard
rule (`rag/prompts.py`) is that it answers with aggregate, anonymized cohort
trends and never quotes or attributes an individual post — so a vector index of
post text would be a store of exactly the content the agent must refuse to
surface, one prompt-injection away from a policy violation, and every citation
would be a quote from a person in distress.

So the agent answers from two separated sources:

| Question | Source | Tool |
| -------- | ------ | ---- |
| "What do our numbers say?" | Gold aggregates (Snowflake / local parquet) | whitelisted SQL metric tool |
| "What does that mean clinically?" | Guidance corpus (Firecrawl-scraped) | retrieval tool, cited by URL |

`ingestion/resources.py` builds the second one: it scrapes an allowlisted set of
public, non-paywalled pages from NIMH, NHS, WHO, CDC, and the 988 Lifeline into
normalized, chunked documents that carry their source URL, title, and retrieval
date, so every retrieved claim is attributable. Scraping is **cache-first** —
re-runs cost zero Firecrawl credits, and `--offline` rebuilds from cache with no
API key at all. Off-allowlist or non-https seeds are refused before any request
is made; a moved or 404'd page is reported and skipped rather than failing the
build.

One seed is chosen to sit directly against our own result: the WHO brief on the
pandemic's 25% increase in anxiety and depression prevalence. Our Gold data shows
sentiment falling in all six communities after the March 2020 declaration and
crisis-signal rate rising in five of six — the corpus lets the agent set that
finding beside the published literature instead of asserting it alone.

## Medallion layers

| Layer  | Contents | Notes |
| ------ | -------- | ----- |
| Bronze | Raw corpus posts, as shipped | Immutable landing zone. Contains raw usernames — never leaves the machine/workspace (gitignored, restricted). |
| Silver | Anonymized, deduped, cleaned | Raw usernames salted-SHA-256 hashed here — they never reach Silver. PII scrubbed. First shareable layer. |
| Gold   | `gold_posts_features`, `gold_subreddit_weekly` | Per-post features + weekly subreddit aggregates; model scores added in Phase 2. |

Full column-level schemas: [`data_model.md`](data_model.md). The transforms
exist in three synchronized forms: pandas (`ingestion/transforms.py`, the
source of truth, runs locally), PySpark (`databricks/01–03`), and dbt SQL
(`dbt/mentalpulse/`, with schema tests).

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
