-- Gold weekly aggregates per subreddit — the dashboard's trend table.
-- Mirror of ingestion/transforms.gold_subreddit_weekly. Unscored signals stay
-- NULL (not 0) until Phase 2, so "no signal yet" is distinguishable from
-- "signal is zero".

select
    subreddit,
    week,
    count(post_id)                            as n_posts,
    count(distinct author_hash)               as n_active_authors,
    round(avg(n_words), 2)                    as avg_word_count,
    avg(sentiment_score)                      as sentiment,
    sum(cast(crisis_flag as int))             as crisis_count,
    sum(cast(crisis_flag as int)) / count(post_id) as crisis_rate
from {{ ref('gold_posts_features') }}
group by subreddit, week
order by subreddit, week
