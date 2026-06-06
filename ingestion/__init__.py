"""Reddit ingestion package (Phase 1).

Pipeline: Reddit (PRAW) -> raw Bronze parquet -> anonymized/cleaned Silver.
Raw usernames are dropped/hashed in the Bronze->Silver step and must never
survive into Silver.
"""
