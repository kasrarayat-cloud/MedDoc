"""Versioned complete canonical JSON in a small, closed string envelope.

The provider writes ordinary nested canonical JSON, JSON-escaped once inside
document_json. The original schema and clinical validators remain authoritative;
this carrier never substitutes an abbreviated clinical model.
"""
from . import clinical_schema_transport as legacy


TRANSPORT = 'anthropic-canonical-json-v4'
TransportError = legacy.TransportError
strict_loads = legacy.strict_loads
INSTRUCTIONS = (
    '\nClinical transport anthropic-canonical-json-v4: first construct the COMPLETE '
    'ordinary nested JSON value required by the original canonical schema and '
    'clinical instructions. Return exactly two envelope properties: transport '
    'must be "anthropic-canonical-json-v4"; document_json must be a JSON STRING '
    'containing that entire canonical JSON value, escaped once as a string. '
    'Do not return a summary, empty example, schema, node table, parent IDs, '
    'parallel columns, markdown or prose. Do not omit any required property or '
    'any fact, assertion, coverage disposition, reference, null or container '
    'belonging to this stage\'s original canonical model. '
    'Preserve original scalar types, exact quotes/unit IDs/occurrences, ownership, '
    'polarity, uncertainty, event/encounter time, units, scales and every original '
    'constraint and annotation. When this stage requests source-unit coverage, '
    'cover every original source unit completely; a short skeleton is not a '
    'completed result. '
    'Generic serialization example only (not a clinical answer): canonical value '
    '{"items":[{"label":"A","value":2.5}],"missing":null,"ok":false} '
    'becomes {"transport":"anthropic-canonical-json-v4","document_json":'
    '"{\\"items\\":[{\\"label\\":\\"A\\",\\"value\\":2.5}],'
    '\\"missing\\":null,\\"ok\\":false}"}. '
    'Inside document_json write normal nested objects/arrays and original values; '
    'the outer JSON string adds escaping, not a new clinical representation.')


def instructions(schema):
    legacy._schema(schema)
    return (INSTRUCTIONS + '\nExact complete original canonical JSON schema, '
        'including every constraint, branch, title and description:\n'
        + legacy._json(schema))


def wire_schema(schema):
    legacy._schema(schema)
    return {'type': 'object', 'additionalProperties': False,
        'required': ['transport', 'document_json'],
        'properties': {
            'transport': {'type': 'string', 'enum': [TRANSPORT]},
            'document_json': {'type': 'string', 'minLength': 1}},
        'description': 'document_json contains the complete original canonical JSON value. '
            'Follow the full original schema and carrier instructions in the system message.'}


def encode(schema, value):
    legacy._schema(schema)
    legacy._json(value)
    canonical = legacy._value(schema, value, 'validate')
    return {'transport': TRANSPORT, 'document_json': legacy._json(canonical)}


def decode(schema, value):
    legacy._schema(schema)
    legacy._json(value)
    wire = legacy._value(wire_schema(schema), value, 'validate')
    canonical = strict_loads(wire['document_json'])
    legacy._json(canonical)
    return legacy._value(schema, canonical, 'validate')
