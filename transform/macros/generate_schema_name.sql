-- Use the custom schema name as-is (e.g. "marts"), not "<target>_marts".
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
