"""Reversible preparation-only wire encoding; canonical validation stays mandatory.

Versioned JSON text preserves canonical components without changing validation.
Earlier choices-only and choices/quote transports remain explicit for replay.
"""
from copy import deepcopy
import json

from documents import DocumentError

ARRAY_TRANSPORT = 'anthropic-shared-component-choices-json-v2'
QUOTE_TRANSPORT = 'anthropic-shared-component-choices-quote-json-v3'
TRANSPORT = 'anthropic-shared-components-json-v4'
COMPACT_TRANSPORT = 'anthropic-shared-component-rows-json-v5'
TRANSPORTS = (ARRAY_TRANSPORT, QUOTE_TRANSPORT, TRANSPORT, COMPACT_TRANSPORT)
COMPONENT_COLUMNS = ('id', 'question_quote', 'label', 'meaning', 'value_type', 'scope',
                     'unit', 'unit_requirement', 'required', 'encounter_scope', 'choices', 'option_quote')
SCOPE_COLUMNS = ('subject', 'temporality', 'polarity')
MAX_ENCODED_BYTES = 2 * 1024 * 1024  # The existing retained-response byte bound.
INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-choices-json-v2: ONLY '
    'answer_definitions.fields[].definition.component_contract.components[].choices '
    'is a string containing a JSON array of the complete original ordered string options. '
    'For a non-choice component return the string "[]". Escape quotes, backslashes and '
    'control characters as JSON requires; do not shorten, normalize, omit or reorder options. '
    'All other choices properties remain arrays. option_quote remains a string or null, '
    'with the same original source evidence requirements. This encoding grants no semantic '
    'approval and changes no canonical constraint. '
)
QUOTE_INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-choices-quote-json-v3: ONLY '
    'answer_definitions.fields[].definition.component_contract.components[].choices '
    'and option_quote use JSON text strings on wire. choices contains a JSON array '
    'of the complete original ordered string options; use the string "[]" for a '
    'non-choice component. option_quote contains exactly one JSON scalar: the string '
    '"null" encodes canonical null, while a JSON-quoted string encodes the exact '
    'canonical source quote. A source quote whose literal text is null must therefore '
    'be JSON-quoted, never confused with canonical null. Empty string is not a null '
    'sentinel. Escape quotes, backslashes and control characters as JSON requires; '
    'do not shorten, normalize, omit or reorder any source evidence. All other choices '
    'properties remain arrays. Canonical nullable option_quote requirements and every '
    'source/type/bound check remain mandatory after decoding. This encoding grants '
    'no semantic approval and changes no canonical constraint. '
)
COMPONENTS_INSTRUCTIONS = (
    ' Response transport anthropic-shared-components-json-v4: ONLY '
    'answer_definitions.fields[].definition.component_contract.components is a string '
    'containing one JSON array of the complete original ordered component objects. '
    'Preserve every component property, ID, question_quote, label, meaning, value_type, '
    'scope, unit, unit_requirement, required, encounter_scope, choices and option_quote '
    'with its canonical JSON type and exact source text. Inside this encoded array, '
    'choices remains an ordered array of strings and option_quote remains a string or '
    'null; do not encode either property again. Null, the literal string null, empty '
    'strings and empty arrays are distinct. Encode an empty component array as the '
    'string "[]" only where the canonical signing/protection contract permits it. '
    'component_contract.contract and rendering, all other outer properties and all '
    'other choices remain unchanged explicit JSON values. Escape quotes, backslashes '
    'and control characters as JSON requires. Do not shorten, normalize, omit, reorder '
    'or infer any component or source evidence. All canonical source, type, ownership, '
    'required, protection and bound checks remain mandatory after decoding. This '
    'encoding grants no semantic approval and changes no canonical constraint. '
)
COMPACT_INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-rows-json-v5: ONLY '
    'answer_definitions.fields[].definition.component_contract.components is a string '
    'containing one JSON array of complete ordered component ROWS. Each component row '
    'has EXACTLY twelve values in this order: [id, question_quote, label, meaning, '
    'value_type, scope, unit, unit_requirement, required, encounter_scope, choices, '
    'option_quote]. scope is EXACTLY [subject, temporality, polarity], three explicit '
    'strings in that order. Every position is mandatory; do not omit trailing nulls, '
    'empty arrays, or other values. id, question_quote, meaning, value_type, '
    'unit_requirement and encounter_scope are strings. label and unit are strings '
    'or null; required is a JSON boolean; choices is the complete ordered array of '
    'strings; option_quote is the exact original source string or null. '
    'Do not encode any individual position again. Canonical null, the literal string '
    'null, empty strings and empty arrays are distinct. Preserve all original text, '
    'Unicode, quotes and backslashes exactly with ordinary JSON escaping. Do not '
    'shorten, normalize, reorder, omit or infer any component, property or source '
    'evidence. An empty component array is the string "[]" only where the canonical '
    'signing/protection contract permits it. All twelve canonical property names '
    'and three scope names are restored by position before the unchanged complete '
    'canonical/source/type/ownership/required/protection/bound validation. '
    'component_contract.contract and rendering and ALL other outer properties '
    'remain unchanged explicit JSON values. This transport grants no approval '
    'and changes no canonical constraint. '
)


def invalid():
    return DocumentError('The preparation choice transport is invalid; its original response is retained.',
                         'invalid_response')


def instructions(transport):
    if transport not in TRANSPORTS:
        raise invalid()
    if transport == COMPACT_TRANSPORT:
        return COMPACT_INSTRUCTIONS
    if transport == TRANSPORT:
        return COMPONENTS_INSTRUCTIONS
    return INSTRUCTIONS if transport == ARRAY_TRANSPORT else QUOTE_INSTRUCTIONS


def wire_schema(canonical, transport=TRANSPORT):
    """Copy and replace only the versioned wire properties, before SDK lowering."""
    instructions(transport)
    value = deepcopy(canonical)
    try:
        contract = (value['properties']['answer_definitions']['properties']['fields']['items']
                    ['properties']['definition']['properties']['component_contract']['properties'])
        if transport == COMPACT_TRANSPORT:
            original = contract['components']
            if (original['type'] != 'array' or original['items']['type'] != 'object'
                    or set(original['items']['properties']) != set(COMPONENT_COLUMNS)
                    or set(original['items']['required']) != set(COMPONENT_COLUMNS)):
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text containing complete ordered rows of EXACTLY twelve values: '
                + json.dumps(COMPONENT_COLUMNS) + '. The scope position is EXACTLY '
                + json.dumps(SCOPE_COLUMNS) + ' as three explicit string values in order. '
                'All positions are mandatory; no defaults, omission, extra positions or nested transport. '
                'Every canonical value and constraint below is preserved by position and '
                'checked after strict decoding: '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        if transport == TRANSPORT:
            original = contract['components']
            if original['type'] != 'array' or original['items']['type'] != 'object':
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text encoding the complete ordered array of canonical component objects. '
                'Inner choices are arrays and option_quote is null or a string; no nested transport. '
                'All canonical constraints are checked after strict decoding: '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        properties = contract['components']['items']['properties']
        choices = properties['choices']
        if choices['type'] != 'array' or choices['items']['type'] != 'string':
            raise invalid()
        properties['choices'] = {'type': 'string', 'description': (
            'A JSON-encoded ordered array of this component\'s complete original string choices; '
            'the string [] for a non-choice component. Canonical constraints, checked after decoding: '
            + json.dumps(choices, ensure_ascii=False, sort_keys=True))}
        if transport == QUOTE_TRANSPORT:
            quote = properties['option_quote']
            if (type(quote.get('anyOf')) is not list or len(quote['anyOf']) != 2
                    or [branch.get('type') for branch in quote['anyOf']] != ['string', 'null']):
                raise invalid()
            properties['option_quote'] = {'type': 'string', 'description': (
                'JSON text encoding exactly canonical null or the exact original source string. '
                'Use null (four characters) for canonical null, or a JSON-quoted string for a source quote. '
                'No empty-string sentinel. Canonical constraints, checked after decoding: '
                + json.dumps(quote, ensure_ascii=False, sort_keys=True))}
    except (KeyError, TypeError):
        raise invalid() from None
    return value


def contracts(value):
    """Admit no missing path or fallback; preserve every property for validation."""
    if type(value) is not dict:
        raise invalid()
    try:
        semantic = value['answer_definitions']
        if type(semantic) is not dict or type(semantic['fields']) is not list:
            raise invalid()
        for row in semantic['fields']:
            if type(row) is not dict or type(row['definition']) is not dict:
                raise invalid()
            contract = row['definition']['component_contract']
            if type(contract) is not dict or contract['contract'] != 'field-components-v3':
                raise invalid()
            yield contract
    except (KeyError, TypeError):
        raise invalid() from None


def components(value):
    """Walk canonical arrays without accepting encoded or incomplete objects."""
    for contract in contracts(value):
        if type(contract.get('components')) is not list:
            raise invalid()
        for component in contract['components']:
            if type(component) is not dict:
                raise invalid()
            yield component


def decode_components(response):
    """Decode exactly one array string, keeping every inner canonical value."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    for contract in contracts(value):
        try:
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            decoded = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(decoded) is not list or any(type(component) is not dict for component in decoded):
                raise invalid()
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        contract['components'] = decoded
    return value


def decode_component_rows(response):
    """Restore all explicit values, without inferring or defaulting semantic data."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    for contract in contracts(value):
        try:
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            rows = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(rows) is not list:
                raise invalid()
            decoded = []
            for row in rows:
                if type(row) is not list or len(row) != len(COMPONENT_COLUMNS):
                    raise invalid()
                component = dict(zip(COMPONENT_COLUMNS, row))
                scope = component['scope']
                if (any(type(component[key]) is not str for key in
                        ('id', 'question_quote', 'meaning', 'value_type', 'unit_requirement', 'encounter_scope'))
                        or any(component[key] is not None and type(component[key]) is not str
                               for key in ('label', 'unit', 'option_quote'))
                        or type(component['required']) is not bool
                        or type(scope) is not list or len(scope) != len(SCOPE_COLUMNS)
                        or any(type(item) is not str for item in scope)
                        or type(component['choices']) is not list
                        or any(type(item) is not str for item in component['choices'])):
                    raise invalid()
                component['scope'] = dict(zip(SCOPE_COLUMNS, scope))
                decoded.append(component)
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        contract['components'] = decoded
    return value


def decode(response, transport=TRANSPORT):
    """Decode losslessly, then let the unchanged full canonical validator judge it."""
    instructions(transport)
    if transport == COMPACT_TRANSPORT:
        return decode_component_rows(response)
    if transport == TRANSPORT:
        return decode_components(response)
    value = deepcopy(response)
    def constant(_):
        raise ValueError('Non-JSON constant')
    for component in components(value):
        try:
            encoded = component['choices']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            choices = json.loads(encoded, parse_constant=constant)
            if type(choices) is not list or any(type(choice) is not str for choice in choices):
                raise invalid()
            if transport == QUOTE_TRANSPORT:
                encoded_quote = component['option_quote']
                if (type(encoded_quote) is not str
                        or len(encoded_quote.encode('utf-8')) > MAX_ENCODED_BYTES):
                    raise invalid()
                quote = json.loads(encoded_quote, parse_constant=constant)
                if quote is not None and type(quote) is not str:
                    raise invalid()
                component['option_quote'] = quote
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        component['choices'] = choices
    return value
