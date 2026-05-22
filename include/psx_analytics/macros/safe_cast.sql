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
