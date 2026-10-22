"""Lossless evidence-reference table for a new, explicitly versioned wire format.

Canonical schemas and clinical/source validators remain authoritative. The old
nullable-array transport is reused as a validator and is never modified here.
"""
from copy import deepcopy

from . import clinical_schema_transport as legacy

TRANSPORT = 'anthropic-evidence-reference-table-v2'
TransportError = legacy.TransportError
INSTRUCTIONS = (
    '\nClinical transport anthropic-evidence-reference-table-v2: return exactly '
    '{transport, evidence, value}. transport is the literal transport version. '
    'evidence is one ordered table of exact {quote, source_unit_id, occurrence} '
    'references; an integer reference ID is its ONE-BASED table position. '
    'Use 0 only for a nullable reference that is absent. Required references '
    'must use a positive ID. Reuse the same ID for an identical reference; '
    'never duplicate an entry or add an unused entry. Preserve exact quote text, '
    'unit and occurrence. value contains the complete original typed model with '
    'reference objects replaced by IDs. A normalized subject has kind and name_span; '
    'its exact original branch map specifies which kinds require a positive name '
    'reference and which permit 0. Other nullable values retain '
    'the [] for null / [value] for present encoding recursively. Non-nullable '
    'arrays retain every ordered item. Every original scalar enum is its ZERO-BASED '
    'integer ordinal in the complete exact JSON value list in that field description; '
    'do not emit the original string, boolean or number instead of its ordinal. '
    'Any other non-null union uses {branch, value}, with branch the zero-based '
    'original variant index and value its encoded value. '
    'The transport version itself remains a literal string. Never omit a required property or invent '
    'a default. This changes no clinical fact, source evidence, subject, time, '
    'polarity, uncertainty, unit, scale or obligation.')


def strict_loads(text):
    return legacy.strict_loads(text)


def _reference(node):
    return (node.get('type') == 'object'
        and set(node.get('properties', {})) == {'quote', 'source_unit_id', 'occurrence'}
        and set(node.get('required', [])) == {'quote', 'source_unit_id', 'occurrence'}
        and node.get('additionalProperties') is False
        and node['properties']['quote'].get('type') == 'string'
        and node['properties']['source_unit_id'].get('type') == 'integer'
        and node['properties']['occurrence'].get('type') == 'integer')


def _shape(node):
    if type(node) is dict:
        return {k: _shape(v) for k, v in node.items() if k not in ('description', 'title')}
    if type(node) is list:
        return [_shape(v) for v in node]
    return node


def _enum(node):
    return node.get('type') in ('string', 'integer', 'number', 'boolean', 'null') and 'enum' in node


def _annotation_registry(schema):
    """Retain every canonical annotation, including inside transformed branches.

    Paths point at the actual description/title value in the original schema;
    RFC6901 escaping keeps arbitrary clinical field names unambiguous.
    """
    texts = {}
    def visit(value, path):
        if type(value) is dict:
            for key, child in value.items():
                pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
                if key in ('description', 'title') and type(child) is str:
                    texts.setdefault(child, []).append(pointer)
                visit(child, pointer)
        elif type(value) is list:
            for i, child in enumerate(value):
                visit(child, path + '/' + str(i))
    visit(schema, '')
    return [{'text': text, 'paths': paths} for text, paths in texts.items()]


def _subject(node):
    """Only the clinical same-key subject union is normalized, not arbitrary unions."""
    branches = node.get('anyOf', [])
    if len(branches) != 2:
        return None
    kinds = []
    references = []
    branch_map = []
    for index, branch in enumerate(branches):
        if (branch.get('type') != 'object'
                or set(branch['properties']) != {'kind', 'name_span'}
                or set(branch['required']) != {'kind', 'name_span'}
                or branch.get('additionalProperties') is not False
                or set(branch) - {'type', 'properties', 'required', 'additionalProperties', 'description', 'title'}):
            return None
        kind = branch['properties']['kind']
        ref = branch['properties']['name_span']
        child = legacy._nullable(ref)
        if (kind.get('type') != 'string' or type(kind.get('enum')) is not list
                or any(type(v) is not str for v in kind['enum'])
                or set(kind) - {'type', 'enum', 'description', 'title'}
                or not _reference(child if child is not None else ref)):
            return None
        kinds.extend(kind['enum'])
        references.append(child if child is not None else ref)
        branch_map.append({'branch': index, 'kinds': deepcopy(kind['enum']),
            'name_span_nullable': child is not None})
    if (len(kinds) != len(set(kinds)) or set(kinds) != {'patient', 'clinician', 'uncertain', 'other'}
            or _shape(references[0]) != _shape(references[1])):
        return None
    # The original branch remains the final authority for other + absent name.
    return {'type': 'object', 'additionalProperties': False,
        'required': ['kind', 'name_span'], 'properties': {
            'kind': {'type': 'string', 'enum': kinds},
            'name_span': {'anyOf': [deepcopy(references[0]), {'type': 'null'}]}},
        **{k: node[k] for k in ('title',) if k in node},
        'description': node.get('description', '') +
            ' Original subject branches retain the following exact kind membership '
            'and name-reference nullability. Branch indices resolve the corresponding '
            'canonical annotation registry /anyOf/index paths; a required name uses '
            'a positive evidence ID. Original subject branch map: ' + legacy._json(branch_map)}


def _reference_capacity(node):
    child = legacy._nullable(node)
    if _reference(node) or (child is not None and _reference(child)):
        return 1
    if child is not None:
        return _reference_capacity(child)
    if 'anyOf' in node:
        counts = [_reference_capacity(branch) for branch in node['anyOf']]
        return None if None in counts else max(counts)
    if node.get('type') == 'object':
        counts = [_reference_capacity(value) for value in node['properties'].values()]
        return None if None in counts else sum(counts)
    if node.get('type') == 'array':
        count = _reference_capacity(node['items'])
        return 0 if count == 0 else None if count is None or 'maxItems' not in node else count * node['maxItems']
    return 0


class _Codec:
    def __init__(self, schema):
        legacy._schema(schema)
        self.schema = schema
        self.reference = None
        self.evidence = []
        self.ids = {}
        self.used = set()
        self.value_schema = self.convert(schema)
        # A reference-free stage still has a closed, empty evidence table.
        reference = self.reference or {'type': 'object', 'additionalProperties': False,
            'required': ['quote', 'source_unit_id', 'occurrence'], 'properties': {
                'quote': {'type': 'string', 'minLength': 1, 'maxLength': 50000},
                'source_unit_id': {'type': 'integer', 'minimum': 1},
                'occurrence': {'type': 'integer', 'minimum': 1, 'maximum': 50000}}}
        self.reference_value_schema = deepcopy(reference)
        reference = deepcopy(reference)
        reference['properties'] = {k: self.convert(v) for k, v in reference['properties'].items()}
        reference['description'] = 'An exact source reference; its one-based table position is its ID.'
        evidence = {'type': 'array', 'items': reference}
        capacity = _reference_capacity(schema)
        if capacity is not None:
            evidence['maxItems'] = capacity
        self.wire = {'type': 'object', 'additionalProperties': False,
            'required': ['transport', 'evidence', 'value'], 'properties': {
                'transport': {'type': 'string', 'enum': [TRANSPORT]},
                'evidence': evidence, 'value': self.value_schema}}
        self.wire['description'] = (
            'Complete canonical annotation registry. Paths are JSON Pointers into '
            'the unchanged original canonical schema. Each title/description remains '
            'an obligation for the corresponding value field, including fields '
            'encoded as evidence IDs, enum ordinals, nullable arrays or normalized '
            'subject branches. Reference annotations govern the exact evidence '
            'selected at that original field; sharing an evidence entry never '
            'transfers another field or person\'s authority. Exact registry: '
            + legacy._json(_annotation_registry(schema)))

    def reference_id(self, node, nullable):
        child = legacy._nullable(node) if nullable else node
        if self.reference is None:
            self.reference = deepcopy(child)
        elif _shape(self.reference) != _shape(child):
            # Different source-reference constraints need a distinct transport.
            raise legacy.invalid()
        return {**{k: node[k] for k in ('title',) if k in node},
            'type': 'integer', 'minimum': 0 if nullable else 1,
            'description': node.get('description', '') +
                (' Evidence reference ID; 0 is null, otherwise a one-based table position.' if nullable
                 else ' Required positive evidence reference ID, a one-based table position.')}

    def convert(self, node):
        child = legacy._nullable(node)
        if _reference(node) or (child is not None and _reference(child)):
            return self.reference_id(node, child is not None)
        subject = _subject(node)
        if subject is not None:
            return self.convert(subject)
        if child is not None:
            return {**{k: node[k] for k in ('title',) if k in node},
                'type': 'array', 'minItems': 0, 'maxItems': 1, 'items': self.convert(child),
                'description': node.get('description', '') + ' Nullable encoding: [] is null; exactly [value] is present.'}
        if _enum(node):
            return {**{k: node[k] for k in ('title',) if k in node},
                'type': 'integer', 'enum': list(range(len(node['enum']))),
                'description': node.get('description', '') +
                    ' Zero-based enum ordinal; exact canonical JSON values by index: ' + legacy._json(node['enum'])}
        if 'anyOf' in node:
            return {**{k: node[k] for k in ('description', 'title') if k in node},
                'anyOf': [{'type': 'object', 'additionalProperties': False,
                    'required': ['branch', 'value'], 'properties': {
                        'branch': {'type': 'integer', 'enum': [i]}, 'value': self.convert(branch)}}
                    for i, branch in enumerate(node['anyOf'])]}
        result = deepcopy(node)
        if node.get('type') == 'object':
            result['properties'] = {k: self.convert(v) for k, v in node['properties'].items()}
        if node.get('type') == 'array':
            result['items'] = self.convert(node['items'])
        return result

    def apply(self, node, value, direction):
        child = legacy._nullable(node)
        if _reference(node) or (child is not None and _reference(child)):
            if direction == 'encode':
                if value is None and child is not None:
                    return 0
                key = legacy._json(value)
                if key not in self.ids:
                    self.evidence.append(deepcopy(value))
                    self.ids[key] = len(self.evidence)
                return self.ids[key]
            if type(value) is not int or value < 0 or value > len(self.evidence) or (value == 0 and child is None):
                raise legacy.invalid()
            if value == 0:
                return None
            self.used.add(value)
            return deepcopy(self.evidence[value - 1])
        subject = _subject(node)
        if subject is not None:
            return self.apply(subject, value, direction)
        if child is not None:
            if direction == 'encode':
                return [] if value is None else [self.apply(child, value, direction)]
            if type(value) is not list or len(value) > 1:
                raise legacy.invalid()
            return None if not value else self.apply(child, value[0], direction)
        if _enum(node):
            if direction == 'encode':
                matches = [i for i, item in enumerate(node['enum']) if legacy._json(item) == legacy._json(value)]
                if not matches:
                    raise legacy.invalid()
                return matches[0]
            if type(value) is not int or not 0 <= value < len(node['enum']):
                raise legacy.invalid()
            return deepcopy(node['enum'][value])
        if 'anyOf' in node:
            if direction == 'encode':
                for i, branch in enumerate(node['anyOf']):
                    try:
                        legacy._value(branch, value, 'validate')
                    except TransportError:
                        continue
                    return {'branch': i, 'value': self.apply(branch, value, direction)}
                raise legacy.invalid()
            if (type(value) is not dict or set(value) != {'branch', 'value'}
                    or type(value['branch']) is not int or not 0 <= value['branch'] < len(node['anyOf'])):
                raise legacy.invalid()
            branch = node['anyOf'][value['branch']]
            return legacy._value(branch, self.apply(branch, value['value'], direction), 'validate')
        if node['type'] == 'object':
            if type(value) is not dict or not set(node['required']) <= set(value) or set(value) - set(node['properties']):
                raise legacy.invalid()
            return {k: self.apply(node['properties'][k], v, direction) for k, v in value.items()}
        if node['type'] == 'array':
            if type(value) is not list:
                raise legacy.invalid()
            return [self.apply(node['items'], v, direction) for v in value]
        return legacy._value(node, value, 'validate')

    def reference_value(self, value, direction):
        return {k: self.apply(self.reference_value_schema['properties'][k], v, direction)
                for k, v in value.items()}


def wire_schema(schema):
    return _Codec(schema).wire


def encode(schema, value):
    codec = _Codec(schema)
    canonical = legacy._value(schema, value, 'validate')
    legacy._json(canonical)
    result = codec.apply(schema, canonical, 'encode')
    wire = {'transport': TRANSPORT,
        'evidence': [codec.reference_value(ref, 'encode') for ref in codec.evidence], 'value': result}
    return legacy._value(codec.wire, wire, 'validate')


def decode(schema, value):
    codec = _Codec(schema)
    legacy._json(value)
    wire = legacy._value(codec.wire, value, 'validate')
    codec.evidence = [legacy._value(codec.reference_value_schema, codec.reference_value(ref, 'decode'), 'validate')
                      for ref in wire['evidence']]
    if len({legacy._json(ref) for ref in codec.evidence}) != len(codec.evidence):
        raise legacy.invalid()
    decoded = codec.apply(schema, wire['value'], 'decode')
    if codec.used != set(range(1, len(codec.evidence) + 1)):
        raise legacy.invalid()
    return legacy._value(schema, decoded, 'validate')
