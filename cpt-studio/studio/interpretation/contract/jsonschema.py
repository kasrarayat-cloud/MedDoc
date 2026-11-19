"""The schema generator and the canonical bytes of design v2's pins (docs/gemini-migration/FINAL-V2.md 1.4, 5.0, step 0b
of 8.1): gemini_schema, canonical and sha256_of, copied from v1's studio/interpretation/schema.py with identical
behaviour, so that the new path executes no v1 code (5.7) while its schemas and pins are derived and hashed exactly as
v1's are. tests/v2/test_types.py proves each equal to v1's on v1's own schemas, by value, the comparison computed in the
test.

A source-integrity copy (5.0), not a reader: it reads schema nodes, never document text. The one change from v1 is where
the implemented keywords live - an Enum instead of a module-level set of strings, which NoWordLists (5.7 measure 4)
refuses in contract/ - and the set it yields is v1's, so every schema is accepted, derived or refused as v1 does it.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum, unique
from typing import Any


@unique
class _Keyword(Enum):
    """The JSON-schema keywords gemini_schema implements: v1's schema._KEYWORDS."""
    TYPE = 'type'
    PROPERTIES = 'properties'
    REQUIRED = 'required'
    ADDITIONAL_PROPERTIES = 'additionalProperties'
    ITEMS = 'items'
    ENUM = 'enum'


_KEYWORDS = frozenset(keyword.value for keyword in _Keyword)


def gemini_schema(local: object) -> dict[str, Any]:
    """Gemini's responseSchema for ``local`` (a schema in the LOCAL form): each type upper-cased, additionalProperties
    dropped, properties, required, items and enum kept, and propertyOrdering set to each object's declaration order.
    Pure; a new dict that shares nothing with ``local``. ValueError for a keyword, a type or an object this generator
    does not implement - an object must forbid additional properties and require exactly its properties, in their order
    - so a schema change cannot pass ungenerated. v1's schema.gemini_schema, unchanged."""
    if not isinstance(local, dict):
        raise ValueError('A schema node must be a dict.')
    unknown = set(local) - _KEYWORDS
    if unknown:
        raise ValueError(f'The interpretation schema uses keywords gemini_schema does not implement: {sorted(unknown)}.')
    kind = local.get('type')
    node: dict[str, Any] = {'type': kind.upper() if isinstance(kind, str) else kind}
    if kind == 'object':
        properties = local.get('properties')
        if (not isinstance(properties, dict) or local.get('additionalProperties') is not False
                or list(local.get('required', ())) != list(properties)):
            raise ValueError('Every object in the interpretation schema must forbid additional properties and require '
                             'exactly the properties it declares, in their order.')
        node['properties'] = {key: gemini_schema(child) for key, child in properties.items()}
        node['required'] = list(properties)
        node['propertyOrdering'] = list(properties)
    elif kind == 'array':
        node['items'] = gemini_schema(local.get('items'))
    elif kind not in ('string', 'integer'):
        raise ValueError(f'The interpretation schema uses the type {kind!r}, which gemini_schema does not implement.')
    if 'enum' in local:
        values = local['enum']
        if kind != 'string' or not isinstance(values, list) or not values or not all(
                isinstance(value, str) for value in values) or len(set(values)) != len(values):
            raise ValueError('An enumeration in the interpretation schema must be a list of distinct strings.')
        node['enum'] = list(values)
    return node


def canonical(value: object) -> bytes:
    """``value`` as a request body is hashed and sent (providers.base.canonical_body): keys sorted, no spaces, UTF-8.
    v1's schema.canonical, unchanged."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha256_of(value: object) -> str:
    """The sha256 of ``value``'s canonical bytes (a schema) or of its UTF-8 bytes (a text). v1's schema.sha256_of,
    unchanged."""
    data = value.encode('utf-8') if isinstance(value, str) else canonical(value)
    return hashlib.sha256(data).hexdigest()
