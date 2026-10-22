"""Versioned, lossless nullable values for clinical Anthropic stage schemas.

Only a declared anyOf[T, null] changes: [] means null and [value] means T.
The original schema (including bounds removed by the SDK) and the clinical
source validators remain authoritative. Historical requests never use this codec.
"""
from copy import deepcopy
import json
import math

CONFIG_KEY = 'semantic_schema_transport'
TRANSPORT = 'anthropic-nullable-singleton-arrays-v1'
EVIDENCE_TRANSPORT = 'anthropic-evidence-reference-table-v2'
CURRENT_TRANSPORT = 'anthropic-flat-typed-nodes-v3'
INSTRUCTIONS = (
    '\nClinical transport anthropic-nullable-singleton-arrays-v1: every schema-declared '
    'nullable value is an array: [] for null, or exactly [value] for a present value. '
    'Apply this recursively, including nullable values inside present objects. '
    'Non-nullable arrays retain their complete ordered items unchanged; a non-nullable '
    'null schema still emits null. At encoded nullable positions never emit null or '
    'put two items in the array. Never omit a required property or use a default. '
    'This encoding changes no source fact, subject, time, polarity, uncertainty, unit, '
    'scale, evidence reference, or clinical obligation.')


class TransportError(ValueError):
    pass


def invalid():
    return TransportError('The clinical schema transport is invalid.')


def selected(config):
    if CONFIG_KEY not in config:
        return False
    if (type(config[CONFIG_KEY]) is not str or config[CONFIG_KEY] not in (TRANSPORT, EVIDENCE_TRANSPORT, CURRENT_TRANSPORT)
            or config.get('mode') != 'live' or config.get('provider') != 'anthropic'
            or config.get('model') != 'claude-sonnet-5-5'):
        raise invalid()
    return True


def marker(config):
    return config[CONFIG_KEY] if selected(config) else None


def instructions(config):
    if marker(config) == CURRENT_TRANSPORT:
        from .clinical_node_transport import INSTRUCTIONS as value
        return value
    if marker(config) == EVIDENCE_TRANSPORT:
        from .clinical_evidence_transport import INSTRUCTIONS as value
        return value
    return INSTRUCTIONS


def transmitted_schema(schema, transport):
    """The exact supported schema passed to the SDK, retained before sending."""
    from anthropic import transform_schema
    from .provider_schema import share_anthropic_schema
    return share_anthropic_schema(transform_schema(wire_schema(schema, transport=transport)))


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def strict_loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise invalid()
            result[key] = value
        return result
    def constant(value):
        raise invalid()
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise invalid() from exc


def _nullable(schema):
    branches = schema.get('anyOf', [])
    nulls = [b for b in branches if b == {'type': 'null'}]
    return next((b for b in branches if b != {'type': 'null'}), None) if len(branches) == 2 and len(nulls) == 1 else None


def _schema(schema):
    """The complete finite schema vocabulary used by the clinical stages.

    Unknown keywords refuse before sending rather than silently losing a rule.
    Annotations are copied as data; they are never interpreted as schema nodes.
    """
    if type(schema) is not dict or set(schema) - {
            'type', 'anyOf', 'properties', 'required', 'additionalProperties', 'items',
            'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum',
            'enum', 'description', 'title'}:
        raise invalid()
    if any(key in schema and type(schema[key]) is not str for key in ('description', 'title')):
        raise invalid()
    if 'anyOf' in schema:
        if (set(schema) - {'anyOf', 'description', 'title'} or type(schema['anyOf']) is not list
                or not schema['anyOf']):
            raise invalid()
        for child in schema['anyOf']:
            _schema(child)
        return
    kind = schema.get('type')
    if kind not in ('object', 'array', 'string', 'integer', 'number', 'boolean', 'null'):
        raise invalid()
    allowed = {'type', 'enum', 'description', 'title'}
    if kind == 'object':
        allowed |= {'properties', 'required', 'additionalProperties'}
        props = schema.get('properties')
        required = schema.get('required')
        if (type(props) is not dict or any(type(k) is not str for k in props)
                or type(required) is not list or any(type(k) is not str for k in required)
                or len(set(required)) != len(required) or not set(required) <= set(props)
                or schema.get('additionalProperties') is not False):
            raise invalid()
        for child in props.values():
            _schema(child)
    elif kind == 'array':
        allowed |= {'items', 'minItems', 'maxItems'}
        _schema(schema.get('items'))
    elif kind == 'string':
        allowed |= {'minLength', 'maxLength'}
    elif kind in ('integer', 'number'):
        allowed |= {'minimum', 'maximum'}
    if set(schema) - allowed:
        raise invalid()
    for lower, upper in (('minItems', 'maxItems'), ('minLength', 'maxLength')):
        for key in (lower, upper):
            if key in schema and (type(schema[key]) is not int or schema[key] < 0):
                raise invalid()
        if lower in schema and upper in schema and schema[lower] > schema[upper]:
            raise invalid()
    for key in ('minimum', 'maximum'):
        if key in schema and (type(schema[key]) not in (int, float)
                or (type(schema[key]) is float and not math.isfinite(schema[key]))):
            raise invalid()
    if 'minimum' in schema and 'maximum' in schema and schema['minimum'] > schema['maximum']:
        raise invalid()
    if 'enum' in schema:
        if type(schema['enum']) is not list or not schema['enum']:
            raise invalid()
        for value in schema['enum']:
            if type(value) not in (str, int, float, bool, type(None)):
                raise invalid()
            _json(value)


def wire_schema(schema, *, transport=TRANSPORT):
    if transport == CURRENT_TRANSPORT:
        from .clinical_node_transport import wire_schema as convert
        return convert(schema)
    if transport == EVIDENCE_TRANSPORT:
        from .clinical_evidence_transport import wire_schema as convert
        return convert(schema)
    if transport != TRANSPORT:
        raise invalid()
    _schema(schema)
    def convert(node):
        child = _nullable(node)
        if child is not None:
            return {**{k: node[k] for k in ('title',) if k in node},
                'type': 'array', 'minItems': 0, 'maxItems': 1, 'items': convert(child),
                'description': node.get('description', '') + ' Nullable encoding: [] is null; exactly [value] is present.'}
        result = deepcopy(node)
        if 'anyOf' in node:
            result['anyOf'] = [convert(child) for child in node['anyOf']]
        if node.get('type') == 'object':
            result['properties'] = {key: convert(child) for key, child in node['properties'].items()}
        if node.get('type') == 'array':
            result['items'] = convert(node['items'])
        return result
    return convert(schema)


def _value(schema, value, direction):
    child = _nullable(schema)
    if child is not None:
        if direction == 'decode':
            if type(value) is not list or len(value) > 1:
                raise invalid()
            return None if not value else _value(child, value[0], direction)
        if value is None:
            return [] if direction == 'encode' else None
        present = _value(child, value, direction)
        return [present] if direction == 'encode' else present
    if 'anyOf' in schema:
        matches = []
        for branch in schema['anyOf']:
            try:
                matches.append(_value(branch, value, direction))
            except TransportError:
                pass
        if not matches or any(_json(x) != _json(matches[0]) for x in matches[1:]):
            raise invalid()
        return matches[0]
    kind = schema['type']
    valid = {'object': type(value) is dict, 'array': type(value) is list,
        'string': type(value) is str, 'integer': type(value) is int,
        'number': type(value) in (int, float), 'boolean': type(value) is bool,
        'null': value is None}[kind]
    if not valid:
        raise invalid()
    if kind in ('integer', 'number'):
        if ((type(value) is float and not math.isfinite(value)) or ('minimum' in schema and value < schema['minimum'])
                or ('maximum' in schema and value > schema['maximum'])):
            raise invalid()
    if kind in ('array', 'string'):
        lower, upper = ('minItems', 'maxItems') if kind == 'array' else ('minLength', 'maxLength')
        if (len(value) < schema.get(lower, 0) or (upper in schema and len(value) > schema[upper])):
            raise invalid()
    if 'enum' in schema and not any(_json(value) == _json(item) for item in schema['enum']):
        raise invalid()
    if kind == 'object':
        if not set(schema['required']) <= set(value) or set(value) - set(schema['properties']):
            raise invalid()
        return {key: _value(schema['properties'][key], item, direction) for key, item in value.items()}
    if kind == 'array':
        return [_value(schema['items'], item, direction) for item in value]
    return deepcopy(value)


def encode(schema, value):
    _schema(schema)
    _json(value)
    return _value(schema, value, 'encode')


def decode(schema, value):
    _schema(schema)
    _json(value)
    decoded = _value(schema, value, 'decode')
    # Recheck the complete original schema, independently of the wire grammar.
    return _value(schema, decoded, 'validate')


def response_value(text, request, *, config, provider, simulated):
    """Decode only a new request whose explicit immutable configuration agrees."""
    transport = request.get('schema_transport')
    if transport not in (TRANSPORT, EVIDENCE_TRANSPORT, CURRENT_TRANSPORT):
        if selected(config):
            raise invalid()
        # Historical readers retain their original parser. Their caller still
        # requires the entire envelope through retained_request_matches; an
        # unknown marker can never become an adopted historical request.
        return json.loads(text)
    if marker(config) != transport or provider != 'anthropic' or simulated is not False:
        raise invalid()
    if transport == CURRENT_TRANSPORT:
        from .clinical_node_transport import decode as restore
        return restore(request['schema'], strict_loads(text))
    if transport == EVIDENCE_TRANSPORT:
        from .clinical_evidence_transport import decode as restore
        return restore(request['schema'], strict_loads(text))
    return decode(request['schema'], strict_loads(text))
