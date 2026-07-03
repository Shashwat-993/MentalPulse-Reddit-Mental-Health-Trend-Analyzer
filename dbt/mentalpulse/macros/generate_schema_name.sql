{#
  Use custom schemas verbatim (silver / gold), not dbt's default
  <target_schema>_<custom_schema> concatenation — the medallion schema names
  are fixed by the lakehouse layout (mentalpulse.silver / mentalpulse.gold).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
