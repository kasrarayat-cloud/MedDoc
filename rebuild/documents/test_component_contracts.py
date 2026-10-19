"""Prospective form-contract tamper and preservation controls, all synthetic."""
from copy import deepcopy
import unittest

from .component_contracts import CONTRACT, fixture, literal_part
from .semantic_preparation_roles import (
    DefinitionError, build_inventory, default_definitions, digest, fixture_role,
    role_instructions, role_schema, validate_definitions, validate_role_result,
)


class ComponentContractTests(unittest.TestCase):
    def make(self, label='Patient name and record reference'):
        field = {'key': 'patient', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}
        definition = default_definitions([field])['patient']
        definition.update(version=4, answer_mode='narrative', patient_name_requirement='none',
            meaning='Patient name and record reference, both as documented and separately labelled.')
        definition['component_contract'] = {'contract': CONTRACT, 'rendering': 'labelled', 'components': [
            {'id': 'name', 'question_quote': label, 'label': 'Patient name', 'meaning': 'The complete documented patient name.',
             'value_type': 'person_name', 'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'},
             'unit': None, 'unit_requirement': 'none', 'required': True},
            {'id': 'reference', 'question_quote': label, 'label': 'record reference', 'meaning': 'The documented patient record reference.',
             'value_type': 'identifier', 'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'},
             'unit': None, 'unit_requirement': 'none', 'required': True}]}
        return field, definition

    def valid(self, field, definition):
        return validate_definitions([field], {field['key']: definition})

    def test_combined_identity_and_generic_heading_preserve_original_destination(self):
        for label in ('Patient name and record reference', 'Patient identification'):
            field, definition = self.make(label)
            before = deepcopy(field)
            self.assertEqual(self.valid(field, definition)['patient'], definition)
            self.assertEqual(field, before)

    def test_literal_labels_and_question_anchors_cannot_be_fabricated_or_take_word_fragments(self):
        for attribute, value in [('question_quote', 'Other person'), ('label', 'Patient nam'),
                                 ('label', 'invented label'), ('label', None), ('required', False),
                                 ('id', 'reference'), ('unit_requirement', 'normal')]:
            field, definition = self.make()
            definition['component_contract']['components'][0][attribute] = value
            with self.subTest(attribute=attribute, value=value), self.assertRaises(DefinitionError):
                self.valid(field, definition)
        self.assertFalse(literal_part('brain', 'rain'))
        self.assertTrue(literal_part('Blood pressure (mmHg)', 'mmHg'))

    def test_repeated_labels_and_optional_or_unanchored_components_are_refused(self):
        for mutate in (lambda c: c[1].update(label=c[0]['label']),
                       lambda c: c[1].update(required=1),
                       lambda c: c[1].update(question_quote=''),
                       lambda c: c[1].update(scope={'subject': 'unknown_person', 'temporality': 'any', 'polarity': 'any'}, value_type='person_name')):
            field, definition = self.make()
            mutate(definition['component_contract']['components'])
            with self.assertRaises(DefinitionError): self.valid(field, definition)

    def test_combined_components_cannot_be_collapsed_into_atomic_name(self):
        field, definition = self.make()
        definition.update(answer_mode='atomic', value_type='person_name')
        with self.assertRaises(DefinitionError): self.valid(field, definition)

    def test_printed_unit_remains_distinct_from_source_documented_unit(self):
        field, definition = self.make('Temperature °C')
        definition.update(value_type='number', answer_mode='atomic', unit='°C')
        definition['component_contract'] = fixture(field, definition)
        self.valid(field, definition)
        for mutate in (lambda c: c.update(unit='°F'), lambda c: c.update(unit_requirement='documented'),
                       lambda c: c.update(unit=None)):
            changed = deepcopy(definition)
            mutate(changed['component_contract']['components'][0])
            with self.assertRaises(DefinitionError): self.valid(field, changed)

    def test_protected_signing_has_no_generated_components(self):
        field, definition = self.make('Clinician signature')
        definition['component_contract'] = fixture(field, definition)
        self.valid(field, definition)
        definition['component_contract']['components'] = self.make()[1]['component_contract']['components']
        with self.assertRaises(DefinitionError): self.valid(field, definition)

    def test_two_roles_include_all_component_requirements_and_disclose_completeness_review(self):
        field, definition = self.make()
        inventory = build_inventory([field], source_version_id='synthetic-version', source_sha256='c'*64,
                                    original={'questions': [field['label']]})
        for role in ('proposer', 'checker'):
            response = {'inventory_sha256': inventory['inventory_sha256'], 'fields': [
                {'field_key': field['key'], 'definition': definition,
                 'state': 'proposed' if role == 'proposer' else 'pass', 'reason': ''}]}
            self.assertEqual(validate_role_result([field], inventory, response, role), response)
            schema = role_schema(role, 4)['properties']['fields']['items']['properties']['definition']
            self.assertIn('component_contract', schema['required'])
            instructions = role_instructions(role, 4)
            self.assertIn('Version 4', instructions)
            self.assertIn('COMPLETE blank form', instructions)
        for version in (1, 2, 3):
            old = fixture_role([field], inventory, 'proposer', definition_version=version)
            self.assertNotIn('component_contract', old['fields'][0]['definition'])
            self.assertNotIn('field-components-v1', role_instructions('proposer', version))

    def test_contract_changes_modify_approval_digest_without_altering_word_mapping(self):
        field, definition = self.make()
        fields_digest = digest([field]); initial = digest(definition)
        definition['component_contract']['components'][0]['scope']['temporality'] = 'current'
        self.valid(field, definition)
        self.assertNotEqual(initial, digest(definition))
        self.assertEqual(fields_digest, digest([field]))
