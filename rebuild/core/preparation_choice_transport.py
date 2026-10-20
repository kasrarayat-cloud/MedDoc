"""Reversible preparation-only wire encoding; canonical validation stays mandatory.

Only v3 component choices and their nullable option quote use JSON text on wire.
Canonical arrays, nulls and strings remain distinct and fully validated.
"""
from copy import deepcopy
import json

from documents import DocumentError

ARRAY_TRANSPORT = 'anthropic-shared-component-choices-json-v2'
TRANSPORT = 'anthropic-shared-component-choices-quote-json-v3'
TRANSPORTS = (ARRAY_TRANSPORT, TRANSPORT)
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


def invalid():
    return DocumentError('The preparation choice transport is invalid; its original response is retained.',
                         'invalid_response')


def instructions(transport):
    if transport not in TRANSPORTS:
        raise invalid()
    return INSTRUCTIONS if transport == ARRAY_TRANSPORT else QUOTE_INSTRUCTIONS


def wire_schema(canonical, transport=TRANSPORT):
    """Copy and replace only the versioned wire properties, before SDK lowering."""
    instructions(transport)
    value = deepcopy(canonical)
    try:
        properties = (value['properties']['answer_definitions']['properties']['fields']['items']
                      ['properties']['definition']['properties']['component_contract']['properties']
                      ['components']['items']['properties'])
        choices = properties['choices']
        if choices['type'] != 'array' or choices['items']['type'] != 'string':
            raise invalid()
        properties['choices'] = {'type': 'string', 'description': (
            'A JSON-encoded ordered array of this component\'s complete original string choices; '
            'the string [] for a non-choice component. Canonical constraints, checked after decoding: '
            + json.dumps(choices, ensure_ascii=False, sort_keys=True))}
        if transport == TRANSPORT:
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


def components(value):
    """Admit no missing path or fallback; preserve every other property for validation."""
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
            if (type(contract) is not dict or contract['contract'] != 'field-components-v3'
                    or type(contract['components']) is not list):
                raise invalid()
            for component in contract['components']:
                if type(component) is not dict:
                    raise invalid()
                yield component
    except (KeyError, TypeError):
        raise invalid() from None


def decode(response, transport=TRANSPORT):
    """Decode losslessly, then let the unchanged full canonical validator judge it."""
    instructions(transport)
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
            if transport == TRANSPORT:
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
