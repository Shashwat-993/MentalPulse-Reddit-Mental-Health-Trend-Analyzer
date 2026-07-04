-- Silver: clean, de-identified posts — the SQL mirror of
-- ingestion/transforms.bronze_to_silver (rules 1–5 in its docstring).
-- The salt comes from the Databricks secret scope via secret(), resolved
-- server-side at query time — it never appears in compiled SQL, manifest.json,
-- or dbt logs (env_var() would render it into all three). Same scope/key as
-- notebook 02; created once with:
--   databricks secrets create-scope mentalpulse
--   databricks secrets put-secret mentalpulse hash_salt

{{ config(alias='posts') }}

with cleaned as (

    select
        post_id,
        subreddit,
        -- try_to_date mirrors the local pipeline's errors="coerce": unparseable
        -- dates become NULL and are dropped below (ANSI mode would error).
        try_to_date(created_date, 'yyyy/MM/dd')        as created_date,
        case
            when author is not null
            then sha2(concat(secret('mentalpulse', 'hash_salt'), ':', author), 256)
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
        -- created_date breaks residual ties deterministically; rows tied on
        -- all three are byte-identical (post_id is content-derived), so the
        -- surviving row's content is stable either way.
        row_number() over (
            partition by post_id
            order by period, source_file, created_date
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
