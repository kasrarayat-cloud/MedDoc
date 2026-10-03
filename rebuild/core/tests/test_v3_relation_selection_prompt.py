"""Retained raw-ASR responses and source-heading/clinical-qualifier controls.

The provider response fixtures are synthetic, unchanged first outputs. New
selections are explicit offline counterfactuals, never a regraded provider run.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_transcript_context import proof
from .test_v3_field_relations import relation_wire
from .test_v3_supersession_floor import SONNET_55_DEFAULT, raw


FIXTURES = Path(__file__).parents[3] / 'docs/rebuild/v1/voice-retained-20261003/raw-asr-response-fixtures.json'


@override_settings(**SONNET_55_DEFAULT)
class SourceHeadingAndSelection(SimpleTestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURES.read_text())['cases']
        self.fields = self.cases[0]['catalogue']

    def answers(self, notes, label, picks, relations=None):
        field = next(f for f in self.fields if f['label'] == label)
        wire = relation_wire(notes, self.fields, {field['key']: picks},
                             overrides={(field['key'], quote): relation for quote, relation in (relations or {}).items()})
        result = raw(notes, self.fields, wire, g.SONNET_5_5)
        result['patient_default_context'] = proof(notes)
        return field, r.validated(result)[field['key']]

    def supported(self, notes, label, picks, relations=None):
        field, answer = self.answers(notes, label, picks, relations)
        self.assertEqual((answer['status'], answer['text']), ('supported', '\n'.join(picks)), answer)
        self.assertEqual([e['quote'] for e in answer['evidence']], picks)
        self.assertEqual(g.governed_decisions(notes, self.fields, {field['key']: answer}), [])
        page = g.as_currently_governed(g.governance_for(notes, self.fields), notes, {**field, **answer})
        self.assertEqual((page['status'], page['text']), ('supported', answer['text']))

    def held(self, notes, label, picks, relations=None):
        field, answer = self.answers(notes, label, picks, relations)
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), answer)
        stored = {**answer, 'status': 'supported', 'text': '\n'.join(picks)}
        self.assertEqual(g.governed_decisions(notes, self.fields, {field['key']: stored}), [label])
        page = g.as_currently_governed(g.governance_for(notes, self.fields), notes, {**field, **stored})
        self.assertEqual((page['status'], page['text']), ('conflict', ''))

    def test_retained_provider_responses_keep_their_original_fifteen_outcomes(self):
        for case in self.cases:
            with self.subTest(attempt=case['attempt']):
                notes = case['notes']
                review = case['persisted_review_evidence']
                self.assertTrue(review['patient_context_review_verified'])
                self.assertTrue(review['applied'][0]['patient_default_context'])
                self.assertFalse(review['applied'][0]['corrected'])
                self.assertEqual(case['reviewed_context_payload']['reviewed_sha256'], review['notes_sha256'])
                result = {'anthropic_response': SimpleNamespace(model=case['response_model'],
                    stop_reason=case['response_stop_reason'],
                    content=[SimpleNamespace(type='text', text=case['response_text'])]),
                    'ordinary_field_contract': r.CONTRACT, 'notes': notes, 'fields': case['catalogue'],
                    'full_catalogue': case['catalogue'], 'context_labels': case['context_labels'],
                    'requested_model': case['request_model'], 'patient_default_context': proof(notes)}
                answers = r.validated(result)
                for key, first in case['first_answers'].items():
                    self.assertEqual({name: answers[key].get(name) for name in ('status', 'text', 'evidence')}, first)

    def test_the_application_request_explains_the_exact_selection_union(self):
        compiled = r.compile_request('The patient reports knee pain.', self.fields, g.configuration(self.fields))
        instructions = compiled['wire']['system']
        self.assertIn('unit_ids must be exactly the union of context.answer and context.qualifier', instructions)
        self.assertIn('context.answer [2] and context.qualifier [1] require unit_ids [1,2], not [2]', instructions)
        self.assertIn('Never select independent, contrary or unresolved units', instructions)
        self.assertIn('A heading that adds a subject, negation, time, uncertainty or other clinical qualification', instructions)

    def test_an_exact_bare_heading_keeps_its_own_complete_patient_answer_useful(self):
        for label, source in (('Assessment', 'The patient has a left ankle sprain.'),
                              ('Plan', 'The patient will rest.')):
            with self.subTest(label=label):
                self.supported(label + '. ' + source, label, [source])

    def test_a_complete_clinical_qualifier_remains_in_the_headed_answer(self):
        first = 'The patient reports knee pain.'
        second = 'The patient reports that the pain is worse on stairs.'
        notes = 'Subjective. ' + first + ' ' + second
        self.supported(notes, 'Subjective', [first, second], {second: 'qualifier'})

    def test_no_declared_qualifier_is_adopted_without_its_complete_source(self):
        first = 'The patient reports knee pain.'
        second = 'The patient reports that the pain is worse on stairs.'
        self.held('Subjective. ' + first + ' ' + second, 'Subjective', [first], {second: 'qualifier'})
        # Even an exact bare heading declared a qualifier remains governed by
        # the existing selection contract. The application never repairs it.
        self.held('Assessment. The patient has a left ankle sprain.', 'Assessment',
                  ['The patient has a left ankle sprain.'], {'Assessment.': 'qualifier'})

    def test_a_heading_supplies_neither_an_actor_nor_a_clinical_fact(self):
        for source in ('Her father has a left ankle sprain.', 'She has a left ankle sprain.'):
            with self.subTest(source=source):
                self.held('Assessment. ' + source, 'Assessment', [source])
        self.held('Assessment. If the patient has a left ankle sprain, the patient will need review.',
                  'Assessment', ['If the patient has a left ankle sprain, the patient will need review.'])

    def test_a_documented_uncertain_assessment_keeps_its_uncertainty(self):
        source = 'The patient may have a left ankle sprain.'
        self.supported('Assessment. ' + source, 'Assessment', [source])

    def test_clinical_heading_modifiers_and_other_field_boundaries_still_hold(self):
        source = 'The patient has a left ankle sprain.'
        self.held('Assessment possible diagnosis. ' + source, 'Assessment', [source])
        self.held('Assessment. Plan. ' + source, 'Assessment', [source])

    def test_contradictions_and_corrections_still_govern_a_headed_answer(self):
        source = 'The patient has a left ankle sprain.'
        self.held('Assessment. ' + source + ' The patient does not have a left ankle sprain.',
                  'Assessment', [source])
        self.held('Assessment. ' + source + ' Correction: the earlier assessment was entered in error.',
                  'Assessment', [source])
