{#
  Use custom schemas verbatim (silver / gold), not dbt's default
  <target_schema>_<custom_schema> concatenation — the medallion schema names
  are fixed by the lakehouse layout (mentalpulse.silver / mentalpulse.gold).

  Deliberate tradeoff: this project has a single workspace and a single
  profile target (`dev`), and every consumer (notebooks, Snowflake loader,
  docs) references the canonical schema names, so there is no second
  environment to isolate. If a prod/CI target is ever added, reintroduce
  isolation by gating the verbatim branch on `target.name` and prefixing
  `{{ target.schema }}_` for the others.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
