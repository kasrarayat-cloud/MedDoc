"""Complete canonical JSON over a constant, flat, typed node-table grammar.

The provider grammar contains no clinical object shape or clinical union. The
unchanged canonical schema and all downstream source validators remain final.
Historical transports are not decoded or changed by this module.
"""
from copy import deepcopy

from . import clinical_schema_transport as legacy

TRANSPORT = 'anthropic-flat-typed-nodes-v3'
TransportError = legacy.TransportError
INSTRUCTIONS = (
    '\nClinical transport anthropic-flat-typed-nodes-v3: return exactly '
    '{transport,nodes,strings,integers,numbers,booleans}. These tables encode '
    'the COMPLETE original canonical JSON model, not a summary. Every table '
    'is COLUMNAR: its parent, key and kind/value properties are parallel arrays '
    'of exactly equal length. Position i in those three columns is one row; '
    'never reorder a column independently, omit a cell or append padding. '
    'nodes contains every object, array and null, including empty containers. '
    'Its columns are {parent:[],key:[],kind:[]}; kind 0 means object, 1 array, '
    '2 null. A node row\'s one-based position is its node ID. Scalar tables '
    'have columns {parent:[],key:[],value:[]}, using '
    'the exact original JSON scalar type: strings, integers, decimal/exponent '
    'numbers, or booleans. Never put booleans in integers or numbers. '
    'parent is the containing node ID; 0 is used only for the single root, '
    'whose key is the empty string. An object child key is its exact property '
    'name, without path escaping. An array child key is its zero-based decimal '
    'index without a sign or leading zeros. Every non-root parent must be an '
    'object or array; null has no children. Node parents precede their children. '
    'No address may occur twice across any tables; array indices are contiguous '
    'and ordered from zero. Visit the complete original value in preorder, '
    'sorting object property names lexicographically and preserving array '
    'order, then append each visited value to its appropriate typed table. '
    'Never omit required properties, empty containers, nulls, references or '
    'array items. Empty tables still have all three empty columns. '
    'Preserve exact quote/unit/occurrence, ownership, temporality, '
    'polarity, uncertainty, units, scales and clinical obligations. The complete '
    'original canonical schema and its original annotations are supplied below; '
    'they remain authoritative at their exact original locations.')


def strict_loads(text):
    return legacy.strict_loads(text)


def _object(properties):
    return {'type': 'object', 'additionalProperties': False,
        'required': list(properties), 'properties': properties}


def wire_schema(schema):
    legacy._schema(schema)
    address = {'parent': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}},
        'key': {'type': 'array', 'items': {'type': 'string'}}}
    properties = {'transport': {'type': 'string', 'enum': [TRANSPORT]},
        'nodes': _object({**deepcopy(address),
            'kind': {'type': 'array', 'items': {'type': 'integer', 'enum': [0, 1, 2]}}})}
    for table, kind in (('strings', 'string'), ('integers', 'integer'),
                        ('numbers', 'number'), ('booleans', 'boolean')):
        properties[table] = _object({**deepcopy(address),
            'value': {'type': 'array', 'items': {'type': kind}}})
    result = _object(properties)
    result['description'] = (
        INSTRUCTIONS + ' Exact complete original canonical JSON schema, '
        'including every original constraint, branch and annotation: '
        + legacy._json(schema))
    return result


def encode(schema, value):
    legacy._schema(schema)
    canonical = legacy._value(schema, value, 'validate')
    legacy._json(canonical)
    wire = {'transport': TRANSPORT, 'nodes': [], 'strings': [],
        'integers': [], 'numbers': [], 'booleans': []}

    def visit(item, parent, key):
        kind = type(item)
        if kind in (dict, list) or item is None:
            wire['nodes'].append({'parent': parent, 'key': key,
                'kind': 0 if kind is dict else 1 if kind is list else 2})
            identifier = len(wire['nodes'])
            if kind is dict:
                for name in sorted(item):
                    visit(item[name], identifier, name)
            elif kind is list:
                for index, child in enumerate(item):
                    visit(child, identifier, str(index))
        else:
            table = {str: 'strings', int: 'integers', float: 'numbers',
                bool: 'booleans'}.get(kind)
            if table is None:
                raise legacy.invalid()
            wire[table].append({'parent': parent, 'key': key, 'value': item})

    visit(canonical, 0, '')
    result = {'transport': TRANSPORT}
    for table in ('nodes', 'strings', 'integers', 'numbers', 'booleans'):
        fields = ('parent', 'key', 'kind' if table == 'nodes' else 'value')
        result[table] = {field: [row[field] for row in wire[table]] for field in fields}
    return legacy._value(wire_schema(schema), result, 'validate')


def decode(schema, value):
    legacy._json(value)
    wire = legacy._value(wire_schema(schema), value, 'validate')
    rows = {}
    for table in ('nodes', 'strings', 'integers', 'numbers', 'booleans'):
        columns = wire[table]
        length = len(columns['parent'])
        if any(len(column) != length for column in columns.values()):
            raise legacy.invalid()
        # Check all column lengths before indexing; zip would silently truncate.
        rows[table] = [{field: column[index] for field, column in columns.items()}
            for index in range(length)]
    nodes = [None] + [{} if row['kind'] == 0 else [] if row['kind'] == 1
        else None for row in rows['nodes']]
    records = []
    for identifier, row in enumerate(rows['nodes'], 1):
        # An earlier parent is both an acyclicity and a complete-root condition.
        if row['parent'] >= identifier:
            raise legacy.invalid()
        records.append((row['parent'], row['key'], nodes[identifier]))
    for table, expected in (('strings', str), ('integers', int),
                            ('numbers', float), ('booleans', bool)):
        for row in rows[table]:
            if type(row['value']) is not expected or row['parent'] >= len(nodes):
                raise legacy.invalid()
            records.append((row['parent'], row['key'], deepcopy(row['value'])))
    roots = [item for parent, key, item in records if parent == 0 and key == '']
    if len(roots) != 1 or sum(parent == 0 for parent, _, _ in records) != 1:
        raise legacy.invalid()
    addresses = set()
    array_items = {}
    for parent, key, item in records:
        address = (parent, key)
        if address in addresses:
            raise legacy.invalid()
        addresses.add(address)
        if parent == 0:
            continue
        if parent >= len(nodes):
            raise legacy.invalid()
        container = nodes[parent]
        if type(container) is dict:
            container[key] = item
        elif type(container) is list:
            # Bound conversion by the actual record population, never by an
            # attacker-controlled sparse index or a speculative output limit.
            if (not key or any(c not in '0123456789' for c in key)
                    or (len(key) > 1 and key[0] == '0')
                    or len(key) > len(str(len(records)))):
                raise legacy.invalid()
            index = int(key)
            if index >= len(records):
                raise legacy.invalid()
            array_items.setdefault(parent, {})[index] = item
        else:
            raise legacy.invalid()
    for parent, items in array_items.items():
        if set(items) != set(range(len(items))):
            raise legacy.invalid()
        nodes[parent].extend(items[index] for index in range(len(items)))
    canonical = legacy._value(schema, roots[0], 'validate')
    # One complete encoding: catches reordered tables/IDs and alternate address
    # layouts after validating all original fields, types, bounds and branches.
    if legacy._json(encode(schema, canonical)) != legacy._json(wire):
        raise legacy.invalid()
    return canonical
