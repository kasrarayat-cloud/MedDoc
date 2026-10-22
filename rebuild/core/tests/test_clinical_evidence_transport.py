"""Offline evidence-table losslessness and authoritative clinical validation."""
from copy import deepcopy
import json
import unittest

from anthropic import transform_schema

from core import clinical_evidence_transport as codec
from core import clinical_schema_transport as legacy
from core import source_assertion_generation as generation, source_assertion_graph as graph
from core.provider_schema import share_anthropic_schema
from core.tests.test_source_assertion_graph import IDENTITY, base_case, checker, run_case
from core.tests.test_source_assertion_generation import stated_time_case


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def obj(props):
    return {'type': 'object', 'additionalProperties': False,
        'required': list(props), 'properties': props}


def count(value, key):
    if type(value) is dict:
        return int(key in value) + sum(count(v, key) for v in value.values())
    if type(value) is list:
        return sum(count(v, key) for v in value)
    return 0


class ClinicalEvidenceTransportTests(unittest.TestCase):
    def roundtrip(self, schema, value):
        schema_before, before = deepcopy(schema), deepcopy(value)
        wire = codec.encode(schema, value)
        self.assertEqual(codec.decode(schema, codec.strict_loads(json.dumps(wire))), value)
        self.assertEqual(schema, schema_before)
        self.assertEqual(value, before)
        return wire

    def test_actual_sdk_reduces_objects_and_eliminates_union_without_mutation(self):
        schema = graph.extraction_schema()
        before = deepcopy(schema)
        old = transform_schema(legacy.wire_schema(schema))
        new = transform_schema(codec.wire_schema(schema))
        self.assertEqual((count(old, 'properties'), count(new, 'properties')), (29, 12))
        self.assertEqual((count(old, 'anyOf'), count(new, 'anyOf')), (1, 0))
        self.assertEqual((count(old, 'items'), count(new, 'items')), (32, 25))
        # Complete canonical annotations and enum mappings add descriptive bytes;
        # grammar reduction is typed objects/unions and enum lexical choices.
        role = new['properties']['value']['properties']['assertions']['items']['properties']['consumer_role']
        self.assertEqual(role['type'], 'integer')
        self.assertEqual(role['enum'], list(range(21)))
        self.assertEqual(transform_schema(share_anthropic_schema(new)), share_anthropic_schema(new))
        self.assertEqual(schema, before)

    def test_exact_deduplication_preserves_quote_unit_occurrence_and_order(self):
        schema = obj({'references': {'type': 'array', 'items': graph.REF, 'maxItems': 4},
            'absent': nullable(graph.REF)})
        first = {'quote': '界😀"\\\nexact', 'source_unit_id': 1, 'occurrence': 1}
        second = {**first, 'occurrence': 2}
        third = {**first, 'source_unit_id': 2}
        wire = self.roundtrip(schema, {'references': [first, second, first, third], 'absent': None})
        self.assertEqual(wire, {'transport': codec.TRANSPORT, 'evidence': [first, second, third],
            'value': {'references': [1, 2, 1, 3], 'absent': 0}})
        self.assertEqual(len(wire['evidence']), 3)

    def test_nullable_reference_distinct_from_empty_arrays_and_false_scalar(self):
        schema = obj({'ref': nullable(graph.REF),
            'nested': nullable({'type': 'array', 'items': nullable({'type': 'boolean'}), 'maxItems': 2})})
        for value, expected in [(None, []), ([], [[]]), ([None, False], [[[], [False]]])]:
            with self.subTest(value=value):
                wire = self.roundtrip(schema, {'ref': None, 'nested': value})
                self.assertEqual(wire['value'], {'ref': 0, 'nested': expected})
                self.assertEqual(wire['evidence'], [])

    def test_required_reference_id_rejects_zero_bool_negative_float_and_range(self):
        schema = obj({'ref': graph.REF, 'maybe': nullable(graph.REF)})
        wire = codec.encode(schema, {'ref': {'quote': 'exact', 'source_unit_id': 1, 'occurrence': 1}, 'maybe': None})
        for value in (0, False, True, -1, 1.0, 2, '1', None, {}, []):
            changed = deepcopy(wire); changed['value']['ref'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):codec.decode(schema, changed)

    def test_nullable_reference_id_zero_only_null_and_positive_only_present(self):
        schema = obj({'ref': nullable(graph.REF)})
        wire = codec.encode(schema, {'ref': None})
        for value in (False, True, -1, 0.0, 1, '0', None, {}, []):
            changed = deepcopy(wire); changed['value']['ref'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):codec.decode(schema, changed)

    def test_unused_duplicate_and_malformed_table_entries_refuse(self):
        schema = obj({'ref': graph.REF, 'maybe': nullable(graph.REF)})
        wire = codec.encode(schema, {'ref': {'quote': 'exact', 'source_unit_id': 1, 'occurrence': 1}, 'maybe': None})
        changes = []
        duplicate = deepcopy(wire); duplicate['evidence'].append(deepcopy(duplicate['evidence'][0])); changes.append(duplicate)
        unused = deepcopy(wire); unused['evidence'].append({'quote': 'unused', 'source_unit_id': 1, 'occurrence': 1}); changes.append(unused)
        for key, value in [('quote', ''), ('source_unit_id', True), ('source_unit_id', 0),
                           ('occurrence', 0), ('occurrence', 50001)]:
            changed = deepcopy(wire); changed['evidence'][0][key] = value; changes.append(changed)
        missing = deepcopy(wire); missing['evidence'][0].pop('occurrence'); changes.append(missing)
        extra = deepcopy(wire); extra['evidence'][0]['extra'] = 'unused'; changes.append(extra)
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(ValueError):codec.decode(schema, changed)

    def test_envelope_exact_marker_required_fields_and_extra_fields_refuse(self):
        schema = obj({'zero': {'type': 'integer', 'minimum': 0}})
        wire = self.roundtrip(schema, {'zero': 0})
        for change in ({**wire, 'transport': legacy.TRANSPORT}, {**wire, 'transport': None},
                       {**wire, 'extra': True}, {'evidence': [], 'value': {'zero': 0}},
                       {**wire, 'value': {}}, {**wire, 'value': {'zero': 0, 'extra': 1}},
                       {**wire, 'evidence': [{'quote': 'unused', 'source_unit_id': 1, 'occurrence': 1}]}):
            with self.subTest(change=change), self.assertRaises(ValueError):codec.decode(schema, change)

    def test_original_reference_constraints_are_kept_even_after_sdk_conversion(self):
        schema = obj({'ref': graph.REF, 'short': {'type': 'string', 'maxLength': 2}})
        ref = {'quote': 'x'*50000, 'source_unit_id': 1, 'occurrence': 50000}
        self.roundtrip(schema, {'ref': ref, 'short': 'ok'})
        for value in ({'ref': {**ref, 'quote': 'x'*50001}, 'short': 'ok'},
                      {'ref': {**ref, 'occurrence': True}, 'short': 'ok'},
                      {'ref': ref, 'short': 'too long'}):
            with self.assertRaises(ValueError):codec.encode(schema, value)
        wire = codec.encode(schema, {'ref': ref, 'short': 'ok'}); wire['value']['short'] = 'too long'
        with self.assertRaises(ValueError):codec.decode(schema, wire)

    def test_subject_normalization_retains_other_requires_name_branch(self):
        schema = obj({'subject': graph.extraction_schema()['properties']['facts']['items']['properties']['subject']})
        wire_schema = codec.wire_schema(schema)
        self.assertEqual(count(wire_schema, 'anyOf'), 0)
        for kind in ('patient', 'clinician', 'uncertain'):
            wire = self.roundtrip(schema, {'subject': {'kind': kind, 'name_span': None}})
            self.assertEqual(wire['value']['subject']['name_span'], 0)
        ref = {'quote': 'Synthetic Other', 'source_unit_id': 1, 'occurrence': 1}
        wire = self.roundtrip(schema, {'subject': {'kind': 'other', 'name_span': ref}})
        self.assertEqual(wire['value']['subject']['name_span'], 1)
        wire['value']['subject']['name_span'] = 0; wire['evidence'] = []
        with self.assertRaises(ValueError):codec.decode(schema, wire)
        with self.assertRaises(ValueError):codec.encode(schema, {'subject': {'kind': 'other', 'name_span': None}})

    def test_all_scalar_enums_preserve_exact_original_types_and_order(self):
        schema = obj({'boolean': {'type': 'boolean', 'enum': [False, True]},
            'integer': {'type': 'integer', 'enum': [1, 0]},
            'number': {'type': 'number', 'enum': [0.0, 0, 1.5]},
            'string': {'type': 'string', 'enum': ['false', '0', '']},
            'null': {'type': 'null', 'enum': [None]}})
        value = {'boolean': False, 'integer': 0, 'number': 0, 'string': '0', 'null': None}
        wire = self.roundtrip(schema, value)
        self.assertEqual(wire['value'], {'boolean': 0, 'integer': 1, 'number': 1, 'string': 1, 'null': 0})
        for number, ordinal in ((0.0, 0), (0, 1), (1.5, 2)):
            value['number'] = number
            wire = self.roundtrip(schema, value)
            self.assertEqual(wire['value']['number'], ordinal)
            self.assertIs(type(codec.decode(schema, wire)['number']), type(number))
        for key in schema['properties']:
            for invalid in (False, True, -1, 1.0, '0', None, 100):
                changed = deepcopy(wire); changed['value'][key] = invalid
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):codec.decode(schema, changed)

    def test_enum_ordinals_cannot_admit_a_value_of_the_wrong_original_type(self):
        schema = obj({'value': {'type': 'string', 'enum': ['0', 0, False]}})
        wire = self.roundtrip(schema, {'value': '0'})
        for ordinal in (1, 2):
            changed = deepcopy(wire); changed['value']['value'] = ordinal
            with self.assertRaises(ValueError):codec.decode(schema, changed)
        for original in (0, False):
            with self.assertRaises(ValueError):codec.encode(schema, {'value': original})

    def test_enum_mapping_description_is_complete_and_does_not_mutate_original(self):
        leaf = {'type': 'string', 'enum': ['界😀', 'false', 'quoted"\\\n'], 'description': 'Original purpose.'}
        schema = obj({'value': leaf}); before = deepcopy(schema)
        wire_leaf = codec.wire_schema(schema)['properties']['value']['properties']['value']
        self.assertEqual(wire_leaf['type'], 'integer')
        self.assertEqual(wire_leaf['enum'], [0, 1, 2])
        self.assertTrue(wire_leaf['description'].startswith('Original purpose.'))
        self.assertTrue(wire_leaf['description'].endswith(legacy._json(leaf['enum'])))
        self.assertEqual(schema, before)
        for value in leaf['enum']:self.roundtrip(schema, {'value': value})

    def test_reference_scalar_enum_is_also_encoded_and_revalidated(self):
        ref = deepcopy(graph.REF); ref['properties']['quote']['enum'] = ['exact', 'other']
        schema = obj({'reference': ref})
        wire = self.roundtrip(schema, {'reference': {'quote': 'exact', 'source_unit_id': 1, 'occurrence': 1}})
        self.assertEqual(wire['evidence'][0]['quote'], 0)

    def test_unrelated_scalar_union_stays_a_union_and_failed_branch_cannot_leak_reference(self):
        schema = obj({'choice': {'anyOf': [obj({'ref': graph.REF, 'kind': {'type': 'string', 'enum': ['a']}}),
            obj({'ref': graph.REF, 'kind': {'type': 'string', 'enum': ['b']}})]},
            'scalar': {'anyOf': [{'type': 'integer'}, {'type': 'string'}]}})
        ref = {'quote': 'exact', 'source_unit_id': 1, 'occurrence': 1}
        for scalar in (0, '0'):
            wire = self.roundtrip(schema, {'choice': {'ref': ref, 'kind': 'b'}, 'scalar': scalar})
            self.assertEqual(wire['evidence'], [ref])
            self.assertEqual(wire['value']['choice']['branch'], 1)
            self.assertEqual(wire['value']['scalar']['branch'], 0 if type(scalar) is int else 1)
            self.assertEqual(count(codec.wire_schema(schema), 'anyOf'), 2)

    def test_remaining_union_branch_tag_is_typed_closed_and_range_checked(self):
        schema = obj({'value': {'anyOf': [{'type': 'string', 'enum': ['a']}, {'type': 'string', 'enum': ['b']}]}})
        wire = self.roundtrip(schema, {'value': 'b'})
        for branch in (True, -1, 2, 1.0, '1', None):
            changed = deepcopy(wire); changed['value']['value']['branch'] = branch
            with self.subTest(branch=branch), self.assertRaises(ValueError):codec.decode(schema, changed)
        changed = deepcopy(wire); changed['value']['value']['value'] = 1
        with self.assertRaises(ValueError):codec.decode(schema, changed)

    def test_nonuniform_reference_constraints_and_unknown_schema_features_refuse(self):
        changed = deepcopy(graph.REF); changed['properties']['quote']['maxLength'] = 10
        with self.assertRaises(ValueError):codec.wire_schema(obj({'one': graph.REF, 'two': changed}))
        for extra in ({'pattern': 'x'}, {'$ref': '#/$defs/x'}, {'allOf': []}, {'default': 'guess'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):codec.wire_schema({'type': 'string', **extra})

    def test_original_schema_annotations_requirements_and_values_are_immutable(self):
        ref = deepcopy(graph.REF); ref['description'] = 'An exact source value.'
        ref['properties']['quote']['title'] = 'Quoted exact bytes'
        schema = obj({'reference': ref})
        before = deepcopy(schema); wire = codec.wire_schema(schema)
        self.assertTrue(wire['properties']['value']['properties']['reference']['description'].startswith(ref['description']))
        self.assertEqual(wire['properties']['evidence']['items']['properties']['quote']['title'], 'Quoted exact bytes')
        self.roundtrip(schema, {'reference': {'quote': 'Exact', 'source_unit_id': 1, 'occurrence': 1}})
        self.assertEqual(schema, before)

    def annotation_registry(self, schema):
        description = codec.wire_schema(schema)['description']
        return json.loads(description.split('Exact registry: ', 1)[1])

    def test_nullable_child_reference_governance_annotation_reaches_provider(self):
        reference = deepcopy(graph.REF)
        reference['description'] = 'NAME_EVIDENCE_FOR_THIS_PERSON_ONLY'
        reference['properties']['quote']['title'] = 'KEEP_COMPLETE_DOCUMENTED_NAME'
        schema = obj({'name': nullable(reference)})
        registry = self.annotation_registry(schema)
        self.assertIn({'text': reference['description'],
            'paths': ['/properties/name/anyOf/0/description']}, registry)
        self.assertIn({'text': 'KEEP_COMPLETE_DOCUMENTED_NAME',
            'paths': ['/properties/name/anyOf/0/properties/quote/title']}, registry)
        transformed = transform_schema(codec.wire_schema(schema))
        self.assertIn('NAME_EVIDENCE_FOR_THIS_PERSON_ONLY', transformed['description'])
        self.assertIn('KEEP_COMPLETE_DOCUMENTED_NAME', transformed['description'])

    def test_normalized_subject_branch_and_kind_annotations_are_not_lost(self):
        subject = deepcopy(graph.extraction_schema()['properties']['facts']['items']['properties']['subject'])
        subject['anyOf'][0]['description'] = 'PATIENT_BRANCH_GOVERNANCE'
        subject['anyOf'][0]['properties']['kind']['description'] = 'PATIENT_KIND_GOVERNANCE'
        subject['anyOf'][1]['title'] = 'OTHER_PERSON_BRANCH_TITLE'
        subject['anyOf'][1]['properties']['kind']['title'] = 'OTHER_PERSON_KIND_TITLE'
        registry = self.annotation_registry(obj({'subject': subject}))
        for text, path in [
                ('PATIENT_BRANCH_GOVERNANCE', '/properties/subject/anyOf/0/description'),
                ('PATIENT_KIND_GOVERNANCE', '/properties/subject/anyOf/0/properties/kind/description'),
                ('OTHER_PERSON_BRANCH_TITLE', '/properties/subject/anyOf/1/title'),
                ('OTHER_PERSON_KIND_TITLE', '/properties/subject/anyOf/1/properties/kind/title')]:
            self.assertIn({'text': text, 'paths': [path]}, registry)

    def test_normalized_subject_keeps_exact_original_branch_scope_and_nullability(self):
        subject = deepcopy(graph.extraction_schema()['properties']['facts']['items']['properties']['subject'])
        subject['anyOf'][0]['description'] = 'RULE_FOR_ORIGINAL_BRANCH_ZERO'
        subject['anyOf'][1]['properties']['kind']['description'] = 'RULE_FOR_ORIGINAL_BRANCH_ONE'
        first = obj({'subject': subject})
        alternate = deepcopy(first)
        variants = alternate['properties']['subject']['anyOf']
        variants[0]['properties']['kind']['enum'] = ['patient']
        variants[1]['properties']['kind']['enum'] = ['clinician', 'uncertain', 'other']
        # Same texts at the same original paths have different governing kinds.
        self.assertEqual(self.annotation_registry(first), self.annotation_registry(alternate))
        one, two = codec.wire_schema(first), codec.wire_schema(alternate)
        self.assertNotEqual(one, two)
        def branch_map(wire):
            description = wire['properties']['value']['properties']['subject']['description']
            return json.loads(description.split('Original subject branch map: ', 1)[1])
        self.assertEqual(branch_map(one), [
            {'branch': 0, 'kinds': ['patient', 'clinician', 'uncertain'], 'name_span_nullable': True},
            {'branch': 1, 'kinds': ['other'], 'name_span_nullable': False}])
        self.assertEqual(branch_map(two), [
            {'branch': 0, 'kinds': ['patient'], 'name_span_nullable': True},
            {'branch': 1, 'kinds': ['clinician', 'uncertain', 'other'], 'name_span_nullable': False}])
        canonical = {'subject': {'kind': 'clinician', 'name_span': None}}
        encoded = self.roundtrip(first, canonical)
        with self.assertRaises(ValueError):codec.encode(alternate, canonical)
        with self.assertRaises(ValueError):codec.decode(alternate, encoded)
        third = deepcopy(first)
        variants = third['properties']['subject']['anyOf']
        variants[0]['properties']['kind']['enum'] = ['patient', 'other']
        variants[1]['properties']['kind']['enum'] = ['clinician', 'uncertain']
        self.roundtrip(third, {'subject': {'kind': 'other', 'name_span': None}})
        self.assertIn('its exact original branch map specifies', codec.INSTRUCTIONS)

    def test_annotation_registry_deduplicates_text_with_unambiguous_escaped_paths(self):
        schema = obj({'a/b~c': {'type': 'string', 'title': 'Shared text', 'description': 'Shared text'},
            'ordinary': nullable({'type': 'string', 'description': 'Shared text'})})
        registry = self.annotation_registry(schema)
        self.assertEqual(registry, [{'text': 'Shared text', 'paths': [
            '/properties/a~1b~0c/title', '/properties/a~1b~0c/description',
            '/properties/ordinary/anyOf/0/description']}])

    def test_actual_three_stage_graph_roundtrip_restores_same_clinical_answers(self):
        for case in (base_case(), stated_time_case()):
            expected, _ = run_case(case)
            notes, fields, definitions, raw, assignment = case
            original = deepcopy(case); calls = []
            def send(role, attempt, payload, schema, instructions):
                calls.append(role)
                value = raw if role == 'extractor' else assignment if role == 'assigner' else checker(
                    payload['graph'], fields, definitions, assignment)
                return codec.decode(schema, codec.strict_loads(json.dumps(codec.encode(schema, value))))
            actual = generation.run(notes, fields, definitions, send, identity=IDENTITY)
            self.assertEqual(actual, expected)
            self.assertEqual(generation.restore(notes, actual['interpretation']), actual['answers'])
            self.assertEqual(calls, ['extractor', 'assigner', 'checker'])
            self.assertEqual(case, original)

    def test_table_does_not_waive_source_quote_ownership_validation(self):
        notes, fields, definitions, raw, assigned = base_case()
        raw['facts'][0]['value_span']['quote'] = 'Invented unrelated name'
        decoded = codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), raw))
        with self.assertRaises(Exception):graph.compile_graph(notes, decoded)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for text in ('{"transport":"x","transport":"y"}', '{"evidence":[{"quote":"a","quote":"b"}]}',
                     '{"value":NaN}', '{}{}'):
            with self.subTest(text=text), self.assertRaises(ValueError):codec.strict_loads(text)
