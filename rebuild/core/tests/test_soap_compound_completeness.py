"""Compound omission controls with source-owned facts, no provider or database."""
from copy import deepcopy
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.soap_destination_contracts import compound_components
from core.tests.test_semantic_generation import fact, assignments
from documents.semantic_preparation_roles import default_definitions


class SoapCompoundCompletenessTests(SimpleTestCase):
    header = 'Patient: Synthetic Ada Tern\nService date: 21 October 2027\n'
    identity = "The patient's full name together with the clinic record number, as documented. The question combines two distinct values (a patient name and an identifier) in one answer area."
    vitals = 'Blood pressure, pulse, temperature and weight, each documented with its units. The question combines four measurements in one answer area; no unit or range is printed.'
    measurements = ['Blood pressure 112/70 mmHg', 'pulse 74 beats per minute',
                    'temperature 36.8 degrees Celsius', 'weight 71.2 kg']

    def assess(self, body, meaning, quotes, selected=None, *, profile=None, label='Unrelated printed label'):
        notes = self.header+body
        fields = [{'key': 'answer', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['answer'].update(version=2, answer_mode='narrative', meaning=meaning,
            scope={'subject': 'patient', 'temporality': 'any', 'polarity': 'any'})
        units, _ = generation.source_units(notes, fields)
        raw = [fact(notes, fields, str(index), quote, kind='identity' if quote == 'Synthetic Ada Tern' else 'finding')
               for index, quote in enumerate(quotes)]
        before = deepcopy((fields, definitions, raw))
        profile = profile or semantic.SOAP_ASSERTION_SCOPE_CONTRACT
        validated = semantic.validate_facts(notes, units, {'facts': raw}, scope_contract=profile)
        picked = [str(i) for i in range(len(quotes))] if selected is None else [str(i) for i in selected]
        result = semantic._assign(notes, fields, definitions, validated,
            assignments(fields, {'answer': picked}), scope_contract=profile)['answer']
        self.assertEqual((fields, definitions, raw), before)
        return result

    def test_identity_requires_each_documented_component_even_if_extractor_omits_it(self):
        body = 'Record number: REF-728\nS\nShe reports discomfort.'
        quotes = ['Synthetic Ada Tern', 'REF-728']
        complete = self.assess(body, self.identity, quotes)
        self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
        self.assertEqual(complete['text'], 'Synthetic Ada Tern; REF-728')
        for extracted, selected in ((quotes, [0]), (quotes, [1]), (quotes[:1], None), ([], None)):
            result = self.assess(body, self.identity, extracted, selected)
            self.assertEqual(result['status'], 'conflict', result)
            self.assertEqual(result['text'], '')
            self.assertTrue(any('compound answer omits' in reason for reason in result['review_reasons']))

    def test_vitals_require_all_documented_labels_units_and_values(self):
        body = 'O\n'+', '.join(self.measurements)+'.'
        complete = self.assess(body, self.vitals, self.measurements)
        self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
        self.assertIn('Temperature 36.8 degrees Celsius', complete['text'])
        for selected in ([0], [0, 1, 2], [1, 2, 3], []):
            result = self.assess(body, self.vitals, self.measurements, selected)
            self.assertEqual(result['status'], 'conflict', result)
        result = self.assess(body, self.vitals, self.measurements[:1])
        self.assertEqual(result['status'], 'conflict', result)
        for fragments in (['112/70', '74', '36.8', '71.2'],
                          ['Blood pressure 112/70', 'pulse 74', 'temperature 36.8', 'weight 71.2']):
            result = self.assess(body, self.vitals, fragments)
            self.assertNotEqual(result['status'], 'supported')

    def test_undocumented_components_are_not_filled_or_made_into_obligations(self):
        result = self.assess('S\nShe reports discomfort.', self.identity, ['Synthetic Ada Tern'])
        self.assertEqual(result['status'], 'supported', result['review_reasons'])
        self.assertEqual(result['text'], 'Synthetic Ada Tern')
        result = self.assess('O\nBlood pressure 112/70 mmHg.', self.vitals, self.measurements[:1])
        self.assertEqual(result['status'], 'supported', result['review_reasons'])
        self.assertNotIn('weight', result['text'].casefold())

    def test_meaning_not_printed_label_controls_the_obligation(self):
        result = self.assess('O\n'+', '.join(self.measurements)+'.', 'Blood pressure',
            self.measurements[:1], label='Blood pressure, pulse, temperature and weight with units')
        self.assertEqual(result['status'], 'supported', result['review_reasons'])
        self.assertEqual(result['text'], self.measurements[0])
        for meaning in ('Blood pressure and pulse only. Exclude temperature.',
                        'Blood pressure, pulse, temperature and weight. Omit weight.',
                        'Blood pressure or pulse', 'An unfamiliar description of four values'):
            definition = default_definitions([{'key': 'answer', 'label': 'answer', 'kind': 'text', 'locator': {'cell': 0}}])['answer']
            definition.update(version=2, answer_mode='narrative', meaning=meaning)
            self.assertEqual(compound_components(definition), set())

    def test_foreign_or_historical_components_cannot_supply_current_obligations(self):
        for heading in ('Mother', 'Previous visit'):
            result = self.assess('O\nBlood pressure 112/70 mmHg.\n'+heading+'\nO\nWeight 71.2 kg.',
                self.vitals, self.measurements[:1])
            self.assertFalse(any('compound answer omits' in reason and 'weight' in reason
                for reason in result['review_reasons']), result)

    def test_unknown_vital_qualification_is_not_cut_off_by_component_detection(self):
        result = self.assess('O\nBlood pressure 112/70 mmHg, pulse 74 beats per minute but unverified.',
            'Blood pressure and pulse with units', self.measurements[:2])
        self.assertNotEqual(result['status'], 'supported', result)

    def test_old_contract_does_not_gain_compound_obligations(self):
        result = self.assess('Record number: REF-728\nHistory\nShe reports discomfort.', self.identity,
            ['Synthetic Ada Tern'], profile=semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT)
        self.assertFalse(any('compound answer omits' in reason for reason in result['review_reasons']))

    def test_general_measurement_components_keep_their_own_units(self):
        quotes = ['Height 165 cm', 'weight 71.2 kg', 'respiratory rate 16 breaths per minute', 'oxygen saturation 98 percent']
        meaning = 'Height, weight, respiratory rate and oxygen saturation with units'
        body = 'O\n'+', '.join(quotes)+'.'
        complete = self.assess(body, meaning, quotes)
        self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
        missing = self.assess(body, meaning, quotes, [0, 1, 2])
        self.assertEqual(missing['status'], 'conflict', missing)

    def test_new_preparation_cannot_seal_a_known_positive_subset(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from django.core.exceptions import ValidationError
        from core import word_contract
        from core.tests.test_compound_preparation_gate import CompoundPreparationGateTests
        for label, meaning in (
                ('Patient full name and clinic record number', "The patient's full name, as documented."),
                ('Blood pressure, pulse, temperature and weight with units', 'The documented blood pressure.')):
            prep, values = CompoundPreparationGateTests().prep(label=label)
            values['answer'].update(answer_mode='narrative', meaning=meaning)
            prep.corrections = {'answer_definitions': deepcopy(values)}
            before = deepcopy(prep.__dict__)
            with patch.object(word_contract, 'proposed', return_value=values):
                with self.assertRaises(ValidationError):
                    word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
            self.assertEqual(prep.__dict__, before)

    def test_copular_vital_and_clinic_record_header_omissions_remain_held(self):
        body = 'Clinic record: REF-728\nS\nShe reports discomfort.'
        quotes = ['Synthetic Ada Tern', 'REF-728']
        self.assertEqual(self.assess(body, self.identity, quotes)['status'], 'supported')
        for extracted, selected in ((quotes, [0]), (quotes[:1], None)):
            result = self.assess(body, self.identity, extracted, selected)
            self.assertEqual(result['status'], 'conflict', result)
        values = ['Blood pressure is 112/70 mmHg', *self.measurements[1:]]
        body = 'O\n'+', '.join(values)+'.'
        complete = self.assess(body, self.vitals, values)
        self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
        self.assertIn(values[0], complete['text'])
        for extracted, selected in ((values, [0]), (values, [1, 2, 3]), (values[:1], None)):
            result = self.assess(body, self.vitals, extracted, selected)
            self.assertEqual(result['status'], 'conflict', result)

    def test_known_component_cannot_disappear_with_a_leadin_or_missing_comma(self):
        quotes = self.measurements[:2]
        meaning = 'Blood pressure and pulse with units'
        bodies = ['O\n'+quotes[0]+' '+quotes[1]+'.',
                  'O\nMeasurements: '+', '.join(quotes)+'.',
                  'O\nVitals were '+', '.join(quotes)+'.']
        for body in bodies:
            with self.subTest(body=body):
                complete = self.assess(body, meaning, quotes)
                self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
                for extracted, selected in ((quotes, [1]), (quotes[1:], None)):
                    result = self.assess(body, meaning, extracted, selected)
                    self.assertEqual(result['status'], 'conflict', result)
                    self.assertTrue(any('compound answer omits' in reason for reason in result['review_reasons']))

    def test_unknown_leadin_or_separator_stays_required_and_cannot_lose_qualifiers(self):
        quotes = self.measurements[:2]
        meaning = 'Blood pressure and pulse with units'
        for body in ('O\nUnresolved measurement context: '+', '.join(quotes)+'.',
                     'O\nPossibly measured '+', '.join(quotes)+'.',
                     'O\n'+quotes[0]+' subject to confirmation; '+quotes[1]+'.',
                     'O\n'+quotes[0]+' except under an unknown condition, '+quotes[1]+'.'):
            with self.subTest(body=body):
                for extracted, selected in ((quotes, None), (quotes, [1]), (quotes[1:], None)):
                    result = self.assess(body, meaning, extracted, selected)
                    self.assertNotEqual(result['status'], 'supported', result)

    def test_qualified_reference_cannot_disappear_but_explicit_absence_stays_blank(self):
        for value in ('REF-728, confirmation pending', 'REF-728 (unverified)',
                      'possibly REF-728', 'REF-728 or REF-729'):
            result = self.assess('Clinic record: '+value+'\nS\nShe reports discomfort.',
                self.identity, ['Synthetic Ada Tern'])
            self.assertEqual(result['status'], 'conflict', result)
            self.assertTrue(any('reference' in reason for reason in result['review_reasons']))
        for value in ('not documented', 'not recorded', 'not available', 'unknown', ''):
            result = self.assess('Clinic record: '+value+'\nS\nShe reports discomfort.',
                self.identity, ['Synthetic Ada Tern'])
            self.assertEqual(result['status'], 'supported', result['review_reasons'])
            self.assertEqual(result['text'], 'Synthetic Ada Tern')

    def test_every_recognized_patient_header_keeps_its_name_obligation(self):
        labels = [prefix+name for prefix in ('', 'Current ', "Today's ", 'Today’s ')
                  for name in ('Patient', 'Patient name', 'Patient full name')]
        for label in labels:
            with self.subTest(label=label):
                self.header = label+': Synthetic Ada Tern\nService date: 21 October 2027\n'
                body = 'Clinic record: REF-728\nS\nShe reports discomfort.'
                quotes = ['Synthetic Ada Tern', 'REF-728']
                complete = self.assess(body, self.identity, quotes)
                self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
                for extracted, selected in ((quotes, [1]), (quotes[1:], None)):
                    result = self.assess(body, self.identity, extracted, selected)
                    self.assertEqual(result['status'], 'conflict', result)
                    self.assertTrue(any('name:patient' in reason for reason in result['review_reasons']))
