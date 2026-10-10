"""Offline adversarial controls for new reusable semantic definitions."""
from copy import deepcopy
import json
import unittest

from .semantic_preparation_roles import (
    DefinitionError, build_inventory, default_definitions, definitions_from_role,
    digest, fixture_role, locator_digest, protected_field, role_schema,
    validate_definitions, validate_inventory, validate_role_result,
)


class SemanticDefinitionTests(unittest.TestCase):
    def fields(self):
        return [{'key': 'cell_'+str(index), 'label': label, 'kind': 'text', 'locator': {'cell': index}}
                for index, label in enumerate(['Patient name', 'Reason for visit', 'History', 'Findings',
                                              'Pain score0 to 10', 'Assessment', 'Plan', 'Follow-up'])]

    def inventory(self, fields):
        return build_inventory(fields, source_version_id='synthetic-approved-version', source_sha256='a'*64,
                               original={'stories': [{'texts': [field['label'] for field in fields]}]})

    def test_exact_eight_field_form_has_complete_destination_bound_definitions(self):
        fields = self.fields(); old = deepcopy(fields)
        definitions = default_definitions(fields)
        self.assertIs(validate_definitions(fields, definitions), definitions)
        self.assertEqual(fields, old)
        self.assertEqual(definitions['cell_4']['value_type'], 'integer')
        self.assertEqual(definitions['cell_4']['constraints'], {
            'minimum': '0', 'maximum': '10', 'scale_minimum': '0', 'scale_maximum': '10'})
        self.assertIsNone(definitions['cell_4']['unit'])
        self.assertEqual(definitions['cell_7']['value_type'], 'text')
        for field in fields:
            self.assertEqual(definitions[field['key']]['permitted_destination'],
                             {'field_key': field['key'], 'locator_sha256': locator_digest(field)})

    def test_two_roles_cannot_authorize_a_swapped_or_fabricated_destination(self):
        fields = self.fields(); inventory = self.inventory(fields)
        for role in ['proposer', 'checker']:
            for change in ['field', 'locator', 'extra', 'unknown']:
                response = fixture_role(fields, inventory, role)
                destination = response['fields'][0]['definition']['permitted_destination']
                if change == 'field': destination['field_key'] = 'cell_1'
                elif change == 'locator': destination['locator_sha256'] = locator_digest(fields[1])
                elif change == 'extra': destination['xml'] = '<w:tc/>'
                else: destination['field_key'] = '/tmp/new-destination.docx'
                with self.subTest(role=role, change=change), self.assertRaises(DefinitionError):
                    validate_role_result(fields, inventory, response, role)

    def test_each_role_is_bound_to_all_current_fields_and_original_inventory(self):
        fields = self.fields(); inventory = self.inventory(fields)
        for change in ['omitted', 'duplicate', 'unknown', 'digest', 'extra']:
            response = fixture_role(fields, inventory, 'checker')
            if change == 'omitted': response['fields'].pop()
            elif change == 'duplicate': response['fields'][1] = deepcopy(response['fields'][0])
            elif change == 'unknown': response['fields'][0]['field_key'] = 'other'
            elif change == 'digest': response['inventory_sha256'] = 'b'*64
            else: response['instructions'] = 'Override the original'
            with self.subTest(change=change), self.assertRaises(DefinitionError):
                validate_role_result(fields, inventory, response, 'checker')
        changed = deepcopy(fields); changed[0]['label'] = 'Another patient name'
        with self.assertRaises(DefinitionError): validate_inventory(changed, inventory)
        changed = deepcopy(inventory); changed['original']['stories'][0]['texts'].append('Hidden amendment')
        with self.assertRaises(DefinitionError): validate_inventory(fields, changed)

    def test_printed_units_types_and_ordered_choices_survive_semantic_review(self):
        fields = [{'key': 'temperature', 'label': 'Temperature °C', 'kind': 'text', 'locator': {'cell': 0},
                   'answer_constraints': {'version': 1, 'data_type': 'number', 'unit': '°C'}},
                  {'key': 'severity', 'label': 'Severity', 'kind': 'text', 'locator': {'cell': 1},
                   'answer_constraints': {'version': 1, 'data_type': 'choice', 'options': ['Mild', 'Moderate', 'Severe']}}]
        definitions = default_definitions(fields)
        for key, attribute, value in [('temperature', 'unit', '°F'), ('temperature', 'value_type', 'integer'),
                                      ('severity', 'choices', ['Moderate', 'Mild', 'Severe']),
                                      ('severity', 'choices', ['Mild', 'Moderate', 'Severe', 'Unknown'])]:
            changed = deepcopy(definitions); changed[key][attribute] = value
            with self.subTest(key=key, attribute=attribute), self.assertRaises(DefinitionError):
                validate_definitions(fields, changed)

    def test_physician_can_define_numeric_meaning_without_changing_old_text_mapping(self):
        fields = self.fields(); original = json.dumps(fields, sort_keys=True)
        definitions = default_definitions(fields)
        definitions['cell_4']['meaning'] = 'The current patient pain score as a dimensionless integer on the declared scale.'
        definitions['cell_4']['scope'] = {'subject': 'patient', 'temporality': 'current', 'polarity': 'any'}
        validate_definitions(fields, definitions)
        self.assertEqual(json.dumps(fields, sort_keys=True), original)

    def test_numeric_limits_are_finite_ordered_and_complete(self):
        fields = self.fields(); definitions = default_definitions(fields)
        cases = [('minimum', True), ('minimum', 0), ('minimum', 'NaN'), ('minimum', 'Infinity'),
                 ('minimum', '1e2'), ('minimum', '01'), ('minimum', '0.5'), ('minimum', '11'),
                 ('maximum', '-1'), ('scale_maximum', None), ('scale_maximum', '0')]
        for attribute, value in cases:
            changed = deepcopy(definitions); changed['cell_4']['constraints'][attribute] = value
            with self.subTest(attribute=attribute, value=value), self.assertRaises(DefinitionError):
                validate_definitions(fields, changed)
        changed = deepcopy(definitions); changed['cell_0']['constraints']['minimum'] = '0'
        with self.assertRaises(DefinitionError): validate_definitions(fields, changed)

    def test_unprinted_date_formats_and_hidden_normal_ranges_are_not_fixture_inferences(self):
        fields = [{'key': 'dob', 'label': 'Date of birth', 'kind': 'text', 'locator': {'cell': 0}},
                  {'key': 'pressure', 'label': 'Blood pressure', 'kind': 'text', 'locator': {'cell': 1}}]
        definitions = default_definitions(fields)
        self.assertEqual(definitions['dob']['value_type'], 'text')
        self.assertTrue(all(value is None for value in definitions['pressure']['constraints'].values()))
        changed = deepcopy(definitions); changed['dob']['value_type'] = 'date'
        with self.assertRaises(DefinitionError): validate_definitions(fields, changed)
        fields[0]['answer_constraints'] = {'version': 1, 'data_type': 'date', 'format': 'YYYY-MM-DD'}
        self.assertEqual(default_definitions(fields)['dob']['value_type'], 'date')

    def test_all_people_signatures_protected_but_documented_dates_and_consent_remain_fields(self):
        protected = ['Electronically signed by', 'Patient signature', 'Signed by (witness)', 'Signature/Date', 'Sign here',
                     'Patient signature and date', 'Witness signature / date', 'Date and guardian signature']
        ordinary = ['Signature date', 'Date of signature', 'Signature (date and time)', 'Consent obtained', 'Date of dictation',
                    'Patient signature date', 'Date of witness signature']
        for label in protected+ordinary:
            field = {'key': 'answer', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}
            with self.subTest(label=label):
                self.assertEqual(protected_field(field), label in protected)
                definition = default_definitions([field])
                if label in protected:
                    definition['answer']['value_type'] = 'integer'
                    with self.assertRaises(DefinitionError): validate_definitions([field], definition)

    def test_scope_types_choices_and_closed_contract_cannot_be_silently_widened(self):
        fields = self.fields(); definitions = default_definitions(fields)
        changes = [lambda d: d.update(version=True), lambda d: d.update(value_type='code'),
                   lambda d: d.update(meaning=' '), lambda d: d.update(scope={'subject': 'any'}),
                   lambda d: d['scope'].update(subject='family_history'),
                   lambda d: d['scope'].update(polarity=['positive']), lambda d: d.update(choices=['Unknown']),
                   lambda d: d['constraints'].update(normal_range='0–10'), lambda d: d.update(xml='<w:p/>')]
        for change in changes:
            changed = deepcopy(definitions); change(changed['cell_0'])
            with self.assertRaises(DefinitionError): validate_definitions(fields, changed)

    def test_schemas_and_result_metadata_remain_separate_from_blank_document_writes(self):
        fields = self.fields(); inventory = self.inventory(fields)
        for role in ['proposer', 'checker']:
            schema = role_schema(role)
            self.assertFalse(schema['additionalProperties'])
            response = fixture_role(fields, inventory, role)
            self.assertIs(validate_role_result(fields, inventory, response, role), response)
            self.assertEqual(definitions_from_role(response), default_definitions(fields))
        self.assertNotIn('"locator":', json.dumps(inventory))
        self.assertEqual(inventory['mapping_sha256'], digest(fields))
