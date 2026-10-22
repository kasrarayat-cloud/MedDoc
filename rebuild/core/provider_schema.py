"""Lossless local-reference sharing for Anthropic's compiled output grammar.

Run after the SDK's supported-schema conversion. Equal schema subtrees share
one definition; expanding the references restores that converted schema. This
does not relax the application's original schema or its clinical validation.
"""
from collections import Counter
from copy import deepcopy
import json


ANTHROPIC_SCHEMA_TRANSPORT = 'anthropic-shared-local-definitions-v1'

_MAPS = frozenset({'properties', 'patternProperties', 'dependentSchemas'})
_LISTS = frozenset({'allOf', 'anyOf', 'oneOf', 'prefixItems'})
_SINGLES = frozenset({'items', 'additionalProperties', 'unevaluatedProperties',
                      'contains', 'not', 'if', 'then', 'else', 'propertyNames'})


def retained_request_matches(request, expected, *, config, provider, simulated):
    """Bind the entire historical or explicitly marked transport envelope.

    Older requests have no transport marker. A marked request must name this
    exact transport on a real Anthropic stage; every other request field still
    has to match. Neither retained bytes nor the caller's expectation is edited.
    """
    if not isinstance(request, dict) or not isinstance(expected, dict):
        return False
    from . import anthropic_request_policy
    try:parameters=anthropic_request_policy.parameters(config)
    except anthropic_request_policy.PolicyError:return False
    if parameters:
        if provider!='anthropic' or simulated is not False:return False
        expected={**expected,anthropic_request_policy.ENVELOPE_KEY:parameters}
    from . import clinical_schema_transport as clinical
    try:new_transport=clinical.selected(config)
    except clinical.TransportError:return False
    if new_transport:
        if (request.get('schema_transport')!=clinical.marker(config) or provider!='anthropic'
                or simulated is not False):
            return False
        expected={**expected,'schema_transport':clinical.marker(config)}
        if clinical.marker(config) in (clinical.EVIDENCE_TRANSPORT, clinical.CURRENT_TRANSPORT, clinical.JSON_TRANSPORT):
            try:expected={**expected,'transmitted_schema':json.dumps(clinical.transmitted_schema(
                expected['schema'],clinical.marker(config)),ensure_ascii=False,separators=(',',':'),allow_nan=False)}
            except (KeyError,TypeError,ValueError):return False
    if 'schema_transport' in request:
        marker = request['schema_transport']
        if (type(marker) is not str or marker != (clinical.marker(config) if new_transport else ANTHROPIC_SCHEMA_TRANSPORT)
                or config.get('mode') != 'live' or config.get('provider') != 'anthropic'
                or provider != 'anthropic' or simulated is not False):
            return False
        expected = {**expected, 'schema_transport': marker}
    # JSON equality keeps booleans distinct from numbers, as the source store
    # already requires for immutable request reconstruction.
    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
    return canonical(request) == canonical(expected)


def _children(schema):
    for key, value in schema.items():
        if key in _MAPS and isinstance(value, dict):
            yield from (child for child in value.values() if isinstance(child, dict))
        elif key in _LISTS and isinstance(value, list):
            yield from (child for child in value if isinstance(child, dict))
        elif key in _SINGLES and isinstance(value, dict):
            yield value
        elif key == 'items' and isinstance(value, list):
            yield from (child for child in value if isinstance(child, dict))


def share_anthropic_schema(schema):
    """Return an independent schema with repeated objects/unions shared.

    Existing reference scopes and allOf schemas are left untouched (Anthropic
    does not support allOf combined with references). Definitions contain complete
    identical schemas (including descriptions), and references have no siblings.
    Only schema positions are visited: object defaults/examples remain data.
    """
    if not isinstance(schema, dict):
        return deepcopy(schema)
    counts = Counter()
    originals = {}
    existing_references = False

    def signature(node):
        return json.dumps(node, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

    def scan(node):
        nonlocal existing_references
        if any(key in node for key in ('$ref', '$defs', 'definitions', '$id', '$anchor',
                                       '$dynamicRef', '$dynamicAnchor', '$recursiveRef',
                                       '$recursiveAnchor', 'allOf')):
            existing_references = True
        if node.get('type') == 'object' or 'anyOf' in node:
            key = signature(node)
            counts[key] += 1
            originals.setdefault(key, node)
        for child in _children(node):
            scan(child)

    scan(schema)
    if existing_references:
        return deepcopy(schema)
    shared = {key for key, count in counts.items() if count > 1}
    if not shared:
        return deepcopy(schema)
    names = {}
    pending = []

    def render(node, defining=None):
        if isinstance(node, dict):
            key = signature(node) if node.get('type') == 'object' or 'anyOf' in node else None
            if key in shared and key != defining:
                if key not in names:
                    names[key] = 'shared_' + str(len(names) + 1)
                    pending.append(key)
                return {'$ref': '#/$defs/' + names[key]}
            result = deepcopy(node)
            for field, value in node.items():
                if field in _MAPS and isinstance(value, dict):
                    result[field] = {name: render(child) if isinstance(child, dict) else deepcopy(child)
                                     for name, child in value.items()}
                elif (field in _LISTS or field == 'items') and isinstance(value, list):
                    result[field] = [render(child) if isinstance(child, dict) else deepcopy(child)
                                     for child in value]
                elif field in _SINGLES and isinstance(value, dict):
                    result[field] = render(value)
            return result
        return deepcopy(node)

    result = render(schema)
    definitions = {}
    # Rendering a definition can discover another repeated nested schema. Only
    # reachable definitions are emitted, so sharing a parent adds no dead grammar.
    for key in pending:
        definitions[names[key]] = render(originals[key], defining=key)
    result['$defs'] = definitions
    # References can cost more than a tiny repeated schema. Never enlarge the
    # transmitted schema in an attempt to reduce its compiled grammar.
    return result if len(signature(result).encode()) < len(signature(schema).encode()) else deepcopy(schema)
