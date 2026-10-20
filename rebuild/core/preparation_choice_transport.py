"""Reversible preparation-only wire encoding; canonical validation stays mandatory.

Only v3 component choices cross the provider boundary as a JSON-array string.
This reduces array nesting without changing the canonical component contract.
"""
from copy import deepcopy
import json

from documents import DocumentError

TRANSPORT = 'anthropic-shared-component-choices-json-v2'
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


def invalid():
    return DocumentError('The preparation choice transport is invalid; its original response is retained.',
                         'invalid_response')


def wire_schema(canonical):
    """Copy and replace exactly one known schema property, before SDK lowering."""
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


def decode(response):
    """Decode losslessly, then let the unchanged full canonical validator judge it."""
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
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        component['choices'] = choices
    return value
