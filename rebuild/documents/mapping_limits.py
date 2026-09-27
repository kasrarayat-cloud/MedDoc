"""Unicode code-point bounds for complete v3 metadata; never truncate."""
MAX_MAPPING_LABEL = 1000
MAX_MAPPING_CONTEXT = 1000

# HTML maxlength counts UTF-16 units; server code-point validation is authoritative.
MAX_MAPPING_INPUT_UNITS = 2 * MAX_MAPPING_LABEL
