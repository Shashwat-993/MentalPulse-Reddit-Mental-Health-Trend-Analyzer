-- Silver: clean, de-identified posts — the SQL mirror of
-- ingestion/transforms.bronze_to_silver (rules 1–5 in its docstring).
-- The salt comes from the environment; it is never materialized in a column.

{{ config(alias='posts') }}

with cleaned as (

    select
        post_id,
        subreddit,
        to_date(created_date, 'yyyy/MM/dd')            as created_date,
        case
            when author is not null
            then sha2(concat('{{ env_var("MENTALPULSE_HASH_SALT") }}', ':', author), 256)
        end                                            as author_hash,
        {{ scrub_pii("trim(regexp_replace(post, '\\\\s+', ' '))") }} as text,
        period,
        source_file,
        ingested_at
    from {{ source('bronze', 'reddit_posts') }}
    where post is not null
      and trim(regexp_replace(post, '\\s+', ' ')) not in ('', '[deleted]', '[removed]')

),

deduped as (

    select
        *,
        row_number() over (
            partition by post_id
            order by period, source_file
        ) as _rn
    from cleaned
    where created_date is not null

)

select
    post_id,
    subreddit,
    created_date,
    author_hash,
    text,
    period,
    source_file,
    ingested_at
from deduped
where _rn = 1
