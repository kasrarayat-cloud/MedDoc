"""Bounded compound-question checks; synthetic labels and no provider calls."""
from copy import deepcopy
import unittest

from . import semantic_preparation_roles as roles


def definition_case(label, *, printed=None):
    field = {'key': 'answer', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}
    if printed is not None:
        field['answer_constraints'] = printed
    fields = [field]
    values = roles.default_definitions(fields)
    values['answer'].update(version=2, answer_mode='atomic')
    values['answer']['scope']['subject'] = 'patient'
    return fields, values


class CompoundAnswerContractTests(unittest.TestCase):
    def issues(self, fields, values, contract=roles.COMPOUND_ANSWER_CONTRACT):
        return roles.compound_answer_issues(fields, values, meaning_contract=contract)

    def test_explicit_independent_value_lists_require_reviewed_narrative_mode(self):
        for label in ('Patient full name and clinic record number',
                      'Blood pressure, pulse, temperature and weight with units',
                      'Clinician name & reference number',
                      'Patient full name and clinician full name',
                      'Patient name and doctor name', 'Patient name and date of birth',
                      'Patient name and guardian name', 'Guardian name and witness name',
                      'Patient date of birth and clinician date of birth',
                      'Height and weight', 'Respiratory rate, oxygen saturation'):
            with self.subTest(label=label):
                fields, values = definition_case(label)
                before = deepcopy((fields, values))
                self.assertEqual(set(self.issues(fields, values)), {'answer'})
                with self.assertRaises(roles.DefinitionError):
                    roles.require_compound_answers(fields, values,
                        meaning_contract=roles.COMPOUND_ANSWER_CONTRACT)
                self.assertEqual((fields, values), before)
                values['answer']['answer_mode'] = 'narrative'
                self.assertEqual(self.issues(fields, values), {})
                self.assertIs(roles.require_compound_answers(fields, values,
                    meaning_contract=roles.COMPOUND_ANSWER_CONTRACT), values)
                self.assertEqual(fields, before[0])
                self.assertEqual(values['answer']['permitted_destination'],
                                 before[1]['answer']['permitted_destination'])

    def test_single_values_synonyms_alternatives_and_unknown_questions_are_unchanged(self):
        labels = ('Patient full name', 'Clinic record number', 'Blood pressure',
                  'Temperature', 'Pain score 0 to 10', 'Pulse and heart rate',
                  'First name and last name', 'Doctor name and physician name',
                  'Patient first name and patient last name', 'Name and patient name',
                  'Date of birth and patient date of birth', 'Temperature or weight',
                  'Blood pressure / pulse', 'Temperature and/or weight',
                  'Blood pressure: normal or elevated', 'Current or past medicine',
                  'Name and record number instructions', 'Pain and its duration',
                  'Heart rate and rhythm', 'Patient signature and date')
        for label in labels:
            with self.subTest(label=label):
                fields, values = definition_case(label)
                before = deepcopy((fields, values))
                self.assertEqual(self.issues(fields, values), {})
                self.assertEqual((fields, values), before)

    def test_printed_choices_remain_one_atomic_selection(self):
        for label in ('Temperature or weight', 'Temperature and weight',
                      'Blood pressure, pulse, temperature and weight with units'):
            fields, values = definition_case(label, printed={
                'version': 1, 'data_type': 'choice', 'options': ['Temperature', 'Weight']})
            before = deepcopy(values)
            self.assertEqual(self.issues(fields, values), {})
            self.assertEqual(values, before)

    def test_printed_constraints_are_not_replaced_to_make_compound_question_fit(self):
        fields, values = definition_case('Temperature and weight', printed={
            'version': 1, 'data_type': 'number', 'unit': 'kg'})
        before = deepcopy((fields, values))
        self.assertEqual(set(self.issues(fields, values)), {'answer'})
        self.assertEqual((fields, values), before)
        changed = deepcopy(values)
        changed['answer'].update(value_type='text', answer_mode='narrative')
        with self.assertRaises(roles.DefinitionError):
            self.issues(fields, changed)

    def test_unknown_explicit_contract_refuses_and_legacy_contracts_do_not_gain_guard(self):
        fields, values = definition_case('Patient full name and clinic record number')
        for contract in (None, roles.COMPOSITE_MEANING_CONTRACT):
            self.assertEqual(self.issues(fields, values, contract), {})
        with self.assertRaises(roles.DefinitionError):
            self.issues(fields, values, 'unrecognized-v3')

    def test_free_text_provider_meaning_cannot_manufacture_a_compound_question(self):
        fields, values = definition_case('Patient name')
        values['answer']['meaning'] = 'Combine name and clinic record number and all vital signs.'
        self.assertEqual(self.issues(fields, values), {})

    def test_narrative_meaning_cannot_explicitly_discard_a_requested_component(self):
        fields, values = definition_case('Patient full name and clinic record number')
        values['answer']['answer_mode'] = 'narrative'
        for meaning in ('Only the patient full name. Exclude all identifiers.',
                        'Record only the patient full name.', 'Exclude the clinic record number.',
                        'Do not include identifiers.', 'Patient full name without record number.',
                        'Provide the patient full name alone.'):
            with self.subTest(meaning=meaning):
                values['answer']['meaning'] = meaning
                self.assertEqual(set(self.issues(fields, values)), {'answer'})
                self.assertEqual(self.issues(fields, values, roles.COMPOSITE_MEANING_CONTRACT), {})
        for meaning in ('Only the patient full name and clinic record number.',
                        'Record the patient full name together with the clinic record number.',
                        'Record all requested details. Do not omit identifiers.',
                        'Include the patient name and record reference. Exclude clinician names.',
                        'Patient name and record number without adding other information.'):
            with self.subTest(meaning=meaning):
                values['answer']['meaning'] = meaning
                self.assertEqual(self.issues(fields, values), {})

    def test_narrative_owner_and_birth_date_subset_conflicts_are_specific(self):
        for label, meaning in (
            ('Patient name and clinician name', 'Only the patient name.'),
            ('Patient name and date of birth', 'Only the patient name.'),
            ('Patient name and date of birth', 'Exclude date of birth.'),
            ('Patient name and guardian name', 'Do not include guardian name.')):
            fields, values = definition_case(label)
            values['answer'].update(answer_mode='narrative', meaning=meaning)
            self.assertEqual(set(self.issues(fields, values)), {'answer'})
        fields, values = definition_case('Name and record number')
        values['answer'].update(answer_mode='narrative',
            meaning='Only the patient name and record number. Exclude clinician names.')
        self.assertEqual(self.issues(fields, values), {})

    def test_complete_affirmative_subset_cannot_silently_drop_printed_components(self):
        for label, meaning in (
            ('Patient full name and clinic record number', "The patient's full name, as documented."),
            ('Patient full name and clinic record number', 'Document the clinic record reference.'),
            ('Blood pressure, pulse, temperature and weight with units', 'The documented blood pressure.'),
            ('Blood pressure, pulse, temperature and weight with units', 'Record blood pressure and heart rate with units.'),
            ('Patient name and clinician name', 'The patient full name.'),
            ('Patient name and date of birth', 'Provide the patient date of birth.')):
            with self.subTest(label=label, meaning=meaning):
                fields, values = definition_case(label)
                values['answer'].update(answer_mode='narrative', meaning=meaning)
                before = deepcopy((fields, values))
                self.assertEqual(set(self.issues(fields, values)), {'answer'})
                self.assertEqual(self.issues(fields, values, roles.COMPOSITE_MEANING_CONTRACT), {})
                self.assertEqual((fields, values), before)

    def test_complete_positive_lists_and_unknown_prose_keep_their_separate_boundaries(self):
        for label, meaning in (
            ('Patient full name and clinic record number', "The patient's full name together with the clinic record number, as documented. The question combines two distinct values (a patient name and an identifier) in one answer area."),
            ('Blood pressure, pulse, temperature and weight with units', 'Blood pressure, heart rate, temperature and body weight, each documented with its units. The question combines four measurements in one answer area; no unit or range is printed.'),
            ('Patient name and doctor name', 'Patient full name and physician full name.'),
            ('Patient name and record number', 'Record all requested details. Do not omit identifiers.'),
            ('Patient name and record number', 'Do not provide the patient name alone; retain the complete question.'),
            ('Patient name and record number', 'Describe the requested identity and reference details in their source context.')):
            with self.subTest(label=label, meaning=meaning):
                fields, values = definition_case(label)
                values['answer'].update(answer_mode='narrative', meaning=meaning)
                self.assertEqual(self.issues(fields, values), {})

    def test_historical_no_contract_and_v1_prompt_bytes_match_unmodified_archive(self):
        # Independently computed from sealed upstream 98f788d7eee08ed648c0fcff129ad15995035227.
        envelope = {f'{role}-{version}-{timing}-{contract}': roles.role_instructions(
            role, version, timing_reference=timing, meaning_contract=contract)
            for version in (2, 3) for role in ('proposer', 'checker')
            for timing in (None, roles.TEMPORAL_REFERENCE_CONTRACT)
            for contract in (None, roles.COMPOSITE_MEANING_CONTRACT)}
        self.assertEqual(roles.digest(envelope),
                         'ae30d3d8c5a05e68051902cd5d1f59df1d470a82ec62305afb20b499944d305c')

    def test_new_instructions_are_explicit_and_additive_for_both_roles(self):
        for version in (2, 3):
            for role in ('proposer', 'checker'):
                for timing in (None, roles.TEMPORAL_REFERENCE_CONTRACT):
                    old = roles.role_instructions(role, version, timing_reference=timing,
                        meaning_contract=roles.COMPOSITE_MEANING_CONTRACT)
                    new = roles.role_instructions(role, version, timing_reference=timing,
                        meaning_contract=roles.COMPOUND_ANSWER_CONTRACT)
                    self.assertEqual(new.count(roles.COMPOUND_ANSWER_INSTRUCTIONS), 1)
                    self.assertEqual(new.replace(roles.COMPOUND_ANSWER_INSTRUCTIONS, ''), old)
        with self.assertRaises(roles.DefinitionError):
            roles.role_instructions('proposer', 1, meaning_contract=roles.COMPOUND_ANSWER_CONTRACT)


if __name__ == '__main__':
    unittest.main()
