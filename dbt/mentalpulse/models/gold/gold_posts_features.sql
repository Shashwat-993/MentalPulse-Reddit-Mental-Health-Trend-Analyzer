-- Gold per-post features — mirror of ingestion/transforms.silver_to_gold_posts.
-- Model-score columns are typed NULL placeholders that Phase 2 backfills.

select
    post_id,
    subreddit,
    created_date,
    date_trunc('week', created_date)          as week,   -- Monday-start
    author_hash,
    length(text)                              as n_chars,
    size(split(text, '\\s+'))                 as n_words,
    cast(null as double)                      as sentiment_score,
    cast(null as string)                      as sentiment_label,
    cast(null as double)                      as crisis_score,
    cast(null as boolean)                     as crisis_flag
from {{ ref('silver_posts') }}
