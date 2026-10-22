"""Complete canonical JSON text, without a provider output grammar or wrapper.

The full original schema is supplied once in the system instructions. Strict
local JSON, original-schema and downstream clinical validation stay mandatory.
"""
from copy import deepcopy

from . import clinical_schema_transport as legacy


TRANSPORT = 'anthropic-canonical-json-text-v5'
TransportError = legacy.TransportError
strict_loads = legacy.strict_loads
INSTRUCTIONS = (
    '\nClinical transport anthropic-canonical-json-text-v5: return the COMPLETE '
    'ordinary nested JSON value required by the original canonical schema and '
    'clinical instructions, directly as compact JSON text without unnecessary '
    'whitespace outside string values or explanatory prose. Reuse existing '
    'references instead of redundant repetition only where the original model '
    'permits it; never shorten quotes, omit required occurrences or change '
    'values. Do not wrap it in a JSON '
    'string, transport envelope, node table, markdown or prose. Do not return '
    'a summary, schema, empty example or partial result. Preserve every required '
    'property, fact, assertion, source-unit coverage disposition, reference, '
    'null, container and original scalar type. Preserve exact quotes/unit IDs/'
    'occurrences, ownership, polarity, uncertainty, event and encounter time, '
    'units, scales and all original constraints and annotations. When the stage '
    'requests source-unit coverage, cover every original source unit completely. '
    'Use valid JSON with unique object keys and finite numbers only.')


def instructions(schema):
    legacy._schema(schema)
    return (INSTRUCTIONS + '\nExact complete original canonical JSON schema, '
        'including every constraint, branch, title and description:\n'
        + legacy._json(schema))


def wire_schema(schema):
    """The local canonical model; no schema is sent as a provider format."""
    legacy._schema(schema)
    return deepcopy(schema)


def encode(schema, value):
    legacy._schema(schema)
    legacy._json(value)
    return legacy._value(schema, value, 'validate')


def decode(schema, value):
    # The caller strictly parses the entire response before this validation.
    return encode(schema, value)
