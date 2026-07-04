{#
  Scrub PII from a text column — the SQL mirror of
  ingestion/anonymize.scrub_text. Same patterns, same order, same redaction
  markers; keep the two in sync (tests/test_anonymize.py pins the Python side).
#}
{% macro scrub_pii(column) %}
    regexp_replace(
      regexp_replace(
        regexp_replace(
          regexp_replace(
            regexp_replace(
              {{ column }},
              '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}', '[REDACTED:email]'
            ),
            '(?i)(?:https?://|www\\.)\\S+', '[REDACTED:url]'
          ),
          '(?i)(?<![\\w/])/?u/[A-Za-z0-9_-]+', '[REDACTED:handle]'
        ),
        '(?<!\\w)@[A-Za-z0-9_]{2,}', '[REDACTED:mention]'
      ),
      '(?<!\\w)\\+?\\d[\\d\\s().-]{5,}\\d(?!\\w)', '[REDACTED:phone]'
    )
{% endmacro %}
