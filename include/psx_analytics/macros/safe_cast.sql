{% macro safe_cast(column, dtype) %}
  {% if target.type == 'snowflake' %}
    TRY_CAST(nullif({{ column }}, '') AS {{ dtype }})
  {% else %}
    nullif({{ column }}, '')::{{ dtype }}
  {% endif %}
{% endmacro %}

{% macro quote_column(column) %}
  {% if target.type == 'snowflake' %}
    "{{ column }}"
  {% else %}
    {{ column }}
  {% endif %}
{% endmacro %}

{% macro cast_date(column) %}
  {% if target.type == 'snowflake' %}
    TO_DATE({{ column }})
  {% else %}
    ({{ column }})::date
  {% endif %}
{% endmacro %}

{% macro round_numeric(expr, scale) %}
  {% if target.type == 'snowflake' %}
    round({{ expr }}, {{ scale }})
  {% else %}
    round(({{ expr }})::numeric, {{ scale }})
  {% endif %}
{% endmacro %}
