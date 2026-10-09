"""Offline counterexamples for independent, source-bound preparation metadata."""
from copy import deepcopy
import json
import unittest

from .engine import DocumentFailure
from .preparation_roles import PROTOCOL, role_rows, role_schema, validate_metadata_row


class PreparationMetadataTests(unittest.TestCase):
    def inventory(self, constraint=None, *, kind='existing', protected=False, issues=None):
        question = {'id': 'q1', 'text': 'Original complete question', 'protected_signing': protected}
        if constraint is not None:
            question['answer_constraints'] = deepcopy(constraint)
        anchor = {'id': 'a1', 'question_id': 'q1', 'kind': kind, 'protected_signing': protected}
        if kind == 'choose_cell':
            anchor['choices'] = [{'id': 'c1', 'column': 1}, {'id': 'c3', 'column': 3}]
        return {'protocol': PROTOCOL, 'questions': [question], 'anchors': [anchor], 'issues': issues or []}

    def test_source_constraints_are_proposed_and_checked_by_both_fixture_roles(self):
        constraints = [None, {'version': 1, 'data_type': 'text'},
                       {'version': 1, 'data_type': 'number', 'unit': '°C'},
                       {'version': 1, 'data_type': 'integer'},
                       {'version': 1, 'data_type': 'date', 'format': 'YYYY-MM-DD'},
                       {'version': 1, 'data_type': 'choice', 'options': ['Yes', 'No']}]
        for constraint in constraints:
            original = self.inventory(constraint)
            frozen = deepcopy(original)
            for role in ['proposer', 'checker']:
                row = role_rows(original, role)[0]
                self.assertIs(validate_metadata_row(original, original['anchors'][0], row), row)
                self.assertEqual(row['metadata']['label'], 'Original complete question')
                self.assertEqual(row['metadata']['destination'], 'a1')
                self.assertEqual(row['metadata']['data_type'], (constraint or {}).get('data_type', 'text'))
                self.assertEqual(row['metadata']['uncertainty'], 'constraints_unstated' if not constraint or constraint['data_type'] == 'text' else 'none')
            self.assertEqual(original, frozen)

    def test_two_roles_agreeing_on_invented_units_types_or_choices_is_refused(self):
        value = self.inventory({'version': 1, 'data_type': 'number', 'unit': '°C'})
        for role in ['proposer', 'checker']:
            for key, bad in [('unit', '°F'), ('data_type', 'integer'), ('label', 'Shortened question'),
                             ('choices', ['Yes', 'No']), ('uncertainty', 'none invented')]:
                row = role_rows(value, role)[0]
                row['metadata'][key] = bad
                with self.subTest(role=role, key=key), self.assertRaises(DocumentFailure):
                    validate_metadata_row(value, value['anchors'][0], row)

    def test_original_choice_order_and_single_original_choice_are_retained(self):
        value = self.inventory({'version': 1, 'data_type': 'choice', 'options': ['Mild', 'Moderate', 'Severe']})
        for options in [['Moderate', 'Mild', 'Severe'], ['Mild', 'Moderate'], ['Mild', 'Moderate', 'Severe', 'Unknown']]:
            row = role_rows(value, 'proposer')[0]
            row['metadata']['choices'] = options
            with self.subTest(options=options), self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], row)
        singleton = self.inventory({'version': 1, 'data_type': 'choice', 'options': ['Leg pain']})
        row = role_rows(singleton, 'checker')[0]
        self.assertEqual(row['metadata']['choices'], ['Leg pain'])
        validate_metadata_row(singleton, singleton['anchors'][0], row)

    def test_unstated_constraints_remain_visible_and_never_gain_a_clinical_type(self):
        value = self.inventory()
        value['questions'][0]['text'] = 'Date of birth'
        row = role_rows(value, 'proposer')[0]
        self.assertEqual(row['metadata'], {'label': 'Date of birth', 'data_type': 'text', 'unit': None,
                                         'choices': [], 'destination': 'a1', 'uncertainty': 'constraints_unstated'})
        for key, bad in [('data_type', 'date'), ('unit', 'kg'), ('choices', ['Yes', 'No']), ('uncertainty', 'none')]:
            forged = deepcopy(row)
            forged['metadata'][key] = bad
            with self.subTest(key=key), self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], forged)

    def test_protected_signing_is_never_converted_into_a_typed_writable_destination(self):
        value = self.inventory({'version': 1, 'data_type': 'number', 'unit': 'kg'}, kind='protected_blank', protected=True)
        row = role_rows(value, 'proposer')[0]
        self.assertEqual(row['metadata']['uncertainty'], 'signing_protected')
        self.assertEqual(row['metadata']['data_type'], 'text')
        self.assertIsNone(row['metadata']['unit'])
        for key, bad in [('destination', 'c1'), ('data_type', 'number'), ('uncertainty', 'none'), ('unit', 'kg')]:
            forged = deepcopy(row)
            forged['metadata'][key] = bad
            with self.subTest(key=key), self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], forged)

    def test_finite_placement_proposals_still_require_explicit_doctor_review(self):
        value = self.inventory(kind='choose_cell')
        proposer, checker = role_rows(value, 'proposer')[0], role_rows(value, 'checker')[0]
        self.assertEqual(proposer['decision'], 'needs_review')
        self.assertEqual(checker['verdict'], 'unresolved')
        self.assertEqual(proposer['metadata']['uncertainty'], 'placement_requires_review')
        for destination in ['c1', 'c3']:
            row = deepcopy(proposer)
            row['metadata']['destination'] = destination
            validate_metadata_row(value, value['anchors'][0], row)
        for destination in ['a1', 'c2', '/tmp/output.docx', '<w:tc/>', 'c3/../../a1']:
            row = deepcopy(proposer)
            row['metadata']['destination'] = destination
            with self.subTest(destination=destination), self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], row)

    def test_original_structural_uncertainty_is_not_erased_by_role_agreement(self):
        value = self.inventory(issues=[{'code': 'guided_layout', 'message': 'Unsupported source structure'}])
        for role in ['proposer', 'checker']:
            row = role_rows(value, role)[0]
            self.assertEqual(row['metadata']['uncertainty'], 'unsupported_structure')
            row['metadata']['uncertainty'] = 'constraints_unstated'
            with self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], row)

    def test_schema_is_closed_and_only_declares_metadata_and_finite_source_ids(self):
        for role, decision in [('proposer', 'decision'), ('checker', 'verdict')]:
            schema = role_schema(role)
            self.assertFalse(schema['additionalProperties'])
            row = schema['properties']['anchors']['items']
            self.assertEqual(set(row['required']), {'anchor_id', 'question_id', decision, 'metadata'})
            self.assertFalse(row['additionalProperties'])
            metadata = row['properties']['metadata']
            self.assertFalse(metadata['additionalProperties'])
            self.assertEqual(set(metadata['required']), {'label', 'data_type', 'unit', 'choices', 'destination', 'uncertainty'})
            self.assertNotIn('locator', json.dumps(schema))
        with self.assertRaises(DocumentFailure):
            role_schema('layout-writer')

    def test_wrong_associations_fabricated_keys_and_malformed_metadata_are_refused(self):
        value = self.inventory()
        base = role_rows(value, 'proposer')[0]
        for mutate in [lambda row: row.update(question_id='q2'), lambda row: row.update(anchor_id='a2'),
                       lambda row: row.update(verdict='pass'), lambda row: row['metadata'].update(locator='/etc/passwd'),
                       lambda row: row['metadata'].update(unit=True), lambda row: row['metadata'].update(choices=[False]),
                       lambda row: row['metadata'].update(destination=False), lambda row: row['metadata'].pop('uncertainty'),
                       lambda row: row.update(decision=[])]:
            row = deepcopy(base)
            mutate(row)
            with self.assertRaises(DocumentFailure):
                validate_metadata_row(value, value['anchors'][0], row)
        forged_anchor = deepcopy(value['anchors'][0])
        forged_anchor['question_id'] = 'q2'
        with self.assertRaises(DocumentFailure):
            validate_metadata_row(value, forged_anchor, base)

    def test_old_inventory_and_malformed_original_bindings_cannot_be_reinterpreted(self):
        value = self.inventory()
        value['protocol'] = 'blank-word-preparation-v1'
        with self.assertRaises(DocumentFailure):
            role_rows(value, 'proposer')
        for mutate in [lambda value: value['anchors'].append(deepcopy(value['anchors'][0])),
                       lambda value: value['questions'].append(deepcopy(value['questions'][0])),
                       lambda value: value['questions'][0].update(protected_signing=True),
                       lambda value: value['questions'][0].update(answer_constraints={'version': True, 'data_type': 'number'}),
                       lambda value: value['questions'][0].update(answer_constraints={'version': 1, 'data_type': 'number', 'unit': 'invented'}),
                       lambda value: value['questions'][0].update(answer_constraints={'version': 1, 'data_type': 'date', 'format': 'invented'}),
                       lambda value: value['anchors'][0].update(kind='choose_cell', choices=[{'id': 'c1'}, {'id': 'c1'}])]:
            malformed = self.inventory()
            mutate(malformed)
            with self.assertRaises(DocumentFailure):
                role_rows(malformed, 'checker')
