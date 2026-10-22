"""Offline flat-carrier losslessness, structural refusals and original gates."""
from copy import deepcopy
import json
import unittest

from anthropic import transform_schema

from core import clinical_node_transport as codec
from core import clinical_schema_transport as legacy


def obj(properties, required=None):
    return {'type': 'object', 'additionalProperties': False,
        'required': list(properties) if required is None else required,
        'properties': properties}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def append_row(wire, table, row):
    for key, value in row.items(): wire[table][key].append(value)


class ClinicalNodeTransportTests(unittest.TestCase):
    def roundtrip(self, schema, value):
        before, original = deepcopy(schema), deepcopy(value)
        wire = codec.encode(schema, value)
        decoded = codec.decode(schema, codec.strict_loads(json.dumps(wire)))
        self.assertEqual(legacy._json(decoded), legacy._json(value))
        self.assertEqual(schema, before)
        self.assertEqual(value, original)
        return wire

    def test_exact_types_unicode_null_empty_containers_and_keys(self):
        schema = obj({'/~': {'type': 'string'}, '': {'type': 'integer'},
            '0': {'type': 'number'}, 'false': {'type': 'boolean'},
            'none': {'type': 'null'}, 'array': {'type': 'array', 'items': {'type': 'string'}},
            'object': obj({}), 'nested': nullable({'type': 'array', 'items': nullable({'type': 'number'})})})
        value = {'/~': '界😀"\\\n', '': 2**80, '0': -0.0, 'false': False,
            'none': None, 'array': [], 'object': {}, 'nested': [None, 0.0, 0]}
        wire = self.roundtrip(schema, value)
        decoded = codec.decode(schema, wire)
        self.assertIs(type(decoded['0']), float)
        self.assertIs(type(decoded['nested'][1]), float)
        self.assertIs(type(decoded['nested'][2]), int)
        for kind, value in [('null', None), ('boolean', False), ('integer', 0),
                            ('number', 0.0), ('string', '')]:
            self.roundtrip({'type': kind}, value)
        self.roundtrip(obj({}), {})
        self.roundtrip({'type': 'array', 'items': {'type': 'string'}}, [])

    def test_wire_grammar_is_constant_flat_closed_and_low_arity(self):
        one = obj({'one': {'type': 'string'}})
        many = obj({str(i): nullable({'type': 'array', 'items': obj({'x': {'type': 'string',
            'enum': ['a', 'b']}})}) for i in range(40)})
        a, b = codec.wire_schema(one), codec.wire_schema(many)
        a.pop('description'); b.pop('description')
        self.assertEqual(a, b)
        sent = transform_schema(codec.wire_schema(many))
        def inspect(node):
            if type(node) is dict:
                self.assertNotIn('anyOf', node)
                self.assertNotIn('oneOf', node)
                if node.get('type') == 'object':
                    self.assertLessEqual(len(node['properties']), 6)
                    self.assertEqual(set(node['required']), set(node['properties']))
                    self.assertIs(node['additionalProperties'], False)
                if node.get('type') == 'array':
                    self.assertNotEqual(node['items'].get('type'), 'object')
                for value in node.values(): inspect(value)
            elif type(node) is list:
                for value in node: inspect(value)
        inspect(sent)

    def test_complete_original_schema_annotations_and_branches_retained(self):
        schema = obj({'subject': {'description': 'ORIGINAL_SUBJECT', 'anyOf': [
            obj({'kind': {'type': 'string', 'enum': ['patient'], 'title': 'PATIENT_SCOPE'},
                 'name': nullable({'type': 'string', 'description': 'OPTIONAL_NAME'})}),
            obj({'kind': {'type': 'string', 'enum': ['other'], 'title': 'OTHER_SCOPE'},
                 'name': {'type': 'string', 'description': 'EXACT_OTHER_NAME'}})]}})
        sent = transform_schema(codec.wire_schema(schema))
        self.assertTrue(sent['description'].endswith(legacy._json(schema)))
        self.roundtrip(schema, {'subject': {'kind': 'other', 'name': 'Synthetic Vale'}})

    def test_duplicate_addresses_across_tables_and_multiple_roots_refuse(self):
        schema = obj({'x': {'type': 'string'}})
        wire = codec.encode(schema, {'x': 'exact'})
        for mutate in (lambda x: append_row(x, 'strings', {'parent': 1, 'key': 'x', 'value': 'exact'}),
                       lambda x: append_row(x, 'integers', {'parent': 1, 'key': 'x', 'value': 0}),
                       lambda x: append_row(x, 'nodes', {'parent': 0, 'key': '', 'kind': 0}),
                       lambda x: append_row(x, 'strings', {'parent': 0, 'key': 'other', 'value': 'root'})):
            changed = deepcopy(wire); mutate(changed)
            with self.assertRaises(ValueError): codec.decode(schema, changed)

    def test_parent_cycles_forward_references_orphans_and_scalar_children_refuse(self):
        schema = obj({'a': obj({'x': {'type': 'string'}}), 'n': {'type': 'null'}})
        wire = codec.encode(schema, {'a': {'x': 'exact'}, 'n': None})
        for parent in (-1, True, 1.0, 2, 10**100):
            changed = deepcopy(wire); changed['nodes']['parent'][1] = parent
            with self.subTest(parent=parent), self.assertRaises(ValueError): codec.decode(schema, changed)
        changed = deepcopy(wire); changed['strings']['parent'][0] = 10**100
        with self.assertRaises(ValueError): codec.decode(schema, changed)
        changed = deepcopy(wire); changed['strings']['parent'][0] = 3
        with self.assertRaises(ValueError): codec.decode(schema, changed)

    def test_array_indices_dense_canonical_and_order_preserved(self):
        schema = {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 2}
        wire = self.roundtrip(schema, ['first', 'second'])
        for key in ('', '00', '01', '-1', '+1', '1.0', '١', '9'*10000, '2', '0'):
            changed = deepcopy(wire); changed['strings']['key'][1] = key
            with self.subTest(key=key[:20]), self.assertRaises(ValueError): codec.decode(schema, changed)
        changed = deepcopy(wire)
        for column in changed['strings'].values(): column.reverse()
        with self.assertRaises(ValueError): codec.decode(schema, changed)

    def test_node_order_and_semantically_equivalent_alternate_layout_refuse(self):
        schema = obj({'a': obj({}), 'b': obj({})})
        wire = codec.encode(schema, {'b': {}, 'a': {}})
        self.assertEqual(wire['nodes']['key'], ['', 'a', 'b'])
        for column in wire['nodes'].values(): column[1:] = reversed(column[1:])
        with self.assertRaises(ValueError): codec.decode(schema, wire)

    def test_scalar_tables_keep_bool_int_float_distinct(self):
        schema = obj({'i': {'type': 'integer'}, 'n': {'type': 'number'}, 'b': {'type': 'boolean'}})
        wire = codec.encode(schema, {'i': 1, 'n': 1.0, 'b': True})
        for table, value in [('integers', True), ('integers', 1.0),
                             ('numbers', 1), ('booleans', 1)]:
            changed = deepcopy(wire); changed[table]['value'][0] = value
            with self.subTest(table=table, value=value), self.assertRaises(ValueError): codec.decode(schema, changed)

    def test_original_required_closed_enum_type_and_bounds_refuse_after_decode(self):
        broad = obj({'x': {'type': 'string'}, 'a': {'type': 'array', 'items': {'type': 'integer'}}}, [])
        restricted = obj({'x': {'type': 'string', 'enum': ['ok'], 'maxLength': 2},
            'a': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'maxItems': 1}})
        for value in ({}, {'x': 'wrong', 'a': []}, {'x': 'ok', 'a': [0]},
                      {'x': 'ok', 'a': [1, 1]}):
            wire = codec.encode(broad, value)
            with self.subTest(value=value), self.assertRaises(ValueError): codec.decode(restricted, wire)
        extra = codec.encode(obj({'extra': {'type': 'string'}}), {'extra': 'x'})
        with self.assertRaises(ValueError): codec.decode(restricted, extra)

    def test_generic_union_and_optional_missing_distinct_from_null(self):
        schema = obj({'choice': {'anyOf': [{'type': 'integer'}, {'type': 'string'}]},
            'maybe': nullable({'type': 'boolean'})}, ['choice'])
        for value in ({'choice': 0}, {'choice': '0', 'maybe': None}, {'choice': 0, 'maybe': False}):
            self.roundtrip(schema, value)

    def test_envelope_rows_null_roots_missing_container_and_unknown_features_refuse(self):
        schema = obj({'x': {'type': 'string'}}); wire = codec.encode(schema, {'x': 'x'})
        mutations = [lambda x: x.update(transport='anthropic-evidence-reference-table-v2'),
            lambda x: x.update(extra=True), lambda x: x.pop('numbers'),
            lambda x: x['nodes'].clear(), lambda x: x['nodes']['kind'].__setitem__(0, True),
            lambda x: x['strings'].update(extra=[]), lambda x: x['strings'].pop('key')]
        for mutate in mutations:
            changed = deepcopy(wire); mutate(changed)
            with self.assertRaises(ValueError): codec.decode(schema, changed)
        with self.assertRaises(ValueError): codec.wire_schema({'type': 'string', 'default': 'invented'})

    def test_all_parallel_columns_are_checked_before_any_zip_truncation(self):
        schema = obj({'s': {'type': 'string'}, 'i': {'type': 'integer'},
            'f': {'type': 'number'}, 'b': {'type': 'boolean'}}, [])
        wire = codec.encode(schema, {'s': 'exact', 'i': 0, 'f': 0.0, 'b': False})
        for table in ('nodes', 'strings', 'integers', 'numbers', 'booleans'):
            for field in wire[table]:
                for longer in (False, True):
                    changed = deepcopy(wire)
                    if longer: changed[table][field].append(changed[table][field][0])
                    else: changed[table][field].pop()
                    with self.subTest(table=table, field=field, longer=longer), self.assertRaises(ValueError):
                        codec.decode(schema, changed)
        # Every original property is optional: dropping a final cell must still
        # fail, even though the shortened canonical object would be valid.
        dropped = deepcopy(wire); dropped['strings']['value'].clear()
        with self.assertRaises(ValueError): codec.decode(schema, dropped)

    def test_independently_reordered_address_column_is_not_canonical(self):
        schema = obj({'a': obj({'value': {'type': 'string'}}),
            'b': obj({'value': {'type': 'string'}})})
        wire = codec.encode(schema, {'a': {'value': 'one'}, 'b': {'value': 'two'}})
        wire['strings']['parent'].reverse()
        with self.assertRaises(ValueError): codec.decode(schema, wire)

    def test_strict_json_truncation_duplicate_keys_and_nonfinite_refuse(self):
        for text in ('{"nodes":[],"nodes":[]}', '{"numbers":[{"value":NaN}]}',
                     '{"nodes":[', '{}{}'):
            with self.assertRaises(ValueError): codec.strict_loads(text)

    def test_pydantic_original_model_roundtrip(self):
        from pydantic import BaseModel, ConfigDict
        class Original(BaseModel):
            model_config = ConfigDict(extra='forbid')
            label: str
            values: list[float]
            flag: bool
        value = Original(label='Exact', values=[-0.0, 1.5], flag=False).model_dump(mode='json')
        schema = Original.model_json_schema()
        wire = self.roundtrip(schema, value)
        self.assertEqual(Original.model_validate(codec.decode(schema, wire)).model_dump(mode='json'), value)

    def test_complete_three_stage_graph_and_source_gates_unchanged(self):
        from core import source_assertion_generation as generation, source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import IDENTITY, base_case, checker, run_case
        from core.tests.test_source_assertion_generation import stated_time_case
        for case in (base_case(), stated_time_case()):
            expected, _ = run_case(case)
            notes, fields, definitions, raw, assignment = case
            def send(role, attempt, payload, schema, instructions):
                value = raw if role == 'extractor' else assignment if role == 'assigner' else checker(
                    payload['graph'], fields, definitions, assignment)
                return codec.decode(schema, codec.encode(schema, value))
            actual = generation.run(notes, fields, definitions, send, identity=IDENTITY)
            self.assertEqual(actual, expected)
            self.assertEqual(generation.restore(notes, actual['interpretation']), actual['answers'])
        bad = deepcopy(raw); bad['facts'][0]['value_span']['quote'] = 'Invented source'
        decoded = codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), bad))
        with self.assertRaises(Exception): graph.compile_graph(notes, decoded)
