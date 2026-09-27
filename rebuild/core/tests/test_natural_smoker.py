"""Exact current-patient nonsmoker option bridge; synthetic selection and mocked worker only."""
import copy
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.models import Encounter
from core.security import private_path
from .test_v3_ordinary_context import CompleteOrdinaryNoteWorkflow, retained_note
from .test_v3_ordinary_input import ordinary_input_form
from .test_v3_ordinary_notes import LIVE, field, run
from .test_word_v3_workflow import V3EncounterFixture, part_text

FIELDS = [field('smoker', 'Smoker', 'choice', ['Yes', 'No'])]
QUOTE = 'The patient is a nonsmoker.'


class NaturalSmoker(SimpleTestCase):
    def answer(self, notes=QUOTE, quote=QUOTE, fields=None):
        return run(notes, {'Smoker': [quote]}, fields=fields or FIELDS)['Smoker']

    def test_explicit_present_patient_preserves_complete_source_evidence(self):
        for quote in (QUOTE, 'Patient is a nonsmoker.'):
            with self.subTest(quote=quote):
                answer = self.answer(quote, quote)
                self.assertEqual((answer['status'], answer['text']), ('supported', 'No'))
                self.assertEqual(answer['evidence'], [{'quote': quote, 'start': 0, 'end': len(quote)}])
                self.assertIsNone(g.governed_supported(g.governance_for(quote, FIELDS), quote, answer, 'Smoker'))

    def test_other_wording_is_not_a_current_patient_option(self):
        for quote in ('She is a nonsmoker.', 'He is a nonsmoker.', 'The mother is a nonsmoker.',
                      'The patient was a nonsmoker.', 'The patient used to be a nonsmoker.',
                      'The patient may be a nonsmoker.', 'The patient is not a nonsmoker.',
                      'The patient is not not a nonsmoker.', 'The patient is a smoker.',
                      'The patient is a nonsmoker?', 'The patient is a nonsmoker...',
                      'The patient is a never-smoker.', 'The patient is a non-smoker.',
                      'The patient is a nonsmoker now.', 'The patient is a nonsmoker, formerly a smoker.'):
            with self.subTest(quote=quote):
                answer = self.answer(quote, quote)
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertNotIn('suggestion', answer)

    def test_source_context_and_opposite_statements_stay_held(self):
        for notes in ('Family history:\n' + QUOTE, 'Hypothetical:\n' + QUOTE,
                      'Previous visit:\n' + QUOTE, QUOTE + ' Actually, she smokes.',
                      QUOTE + '\n\nCorrection: the patient smokes.',
                      QUOTE + ' The patient smokes daily.',
                      QUOTE + '\n\nThe patient smokes daily.',
                      'For her mother:\n\n' + QUOTE):
            with self.subTest(notes=notes):
                answer = self.answer(notes)
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertNotIn('suggestion', answer)

    def test_only_unambiguous_literal_binary_field_is_eligible(self):
        variants = []
        for options in (['Yes', 'No', 'Former'], ['Yes', 'Never'], ['Yes', 'No', 'No'], ['Yes.', 'No.']):
            variants.append([field('s', 'Smoker', 'choice', options)])
        contextual = copy.deepcopy(FIELDS); contextual[0]['context'] = 'Family history'; variants.append(contextual)
        printed = copy.deepcopy(FIELDS); printed[0]['locator']['target']['printed'] = ['Yes', 'No', 'No']; variants.append(printed)
        variants.append([field('s', 'Smoker', 'multi_choice', ['Yes', 'No'])])
        variants.append([*FIELDS, field('s2', 'Smoker?', 'choice', ['Yes', 'No'])])
        for fields in variants:
            with self.subTest(fields=fields):
                self.assertEqual(self.answer(fields=fields)['text'], '')
        for label in ('Smoker?', 'Former smoker', 'Never smoker', 'Mother smoker'):
            fs = [field('s', label, 'choice', ['Yes', 'No'])]
            self.assertEqual(run(QUOTE, {label: [QUOTE]}, fields=fs)[label]['text'], '')

    def test_note4_remains_held_without_a_pronoun_ownership_contract(self):
        note = retained_note('r1-note4')
        answer = self.answer(note['notes'], 'She is a nonsmoker.')
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_forged_partial_span_and_suggestion_never_gain_automatic_conversion(self):
        labels = g.recognized_labels(FIELDS)
        for notes, start, end, text in (('Not ' + QUOTE, 4, 4+len(QUOTE), QUOTE),
                                         (QUOTE, True, len(QUOTE), QUOTE),
                                         (QUOTE, 0, len(QUOTE)-1, QUOTE),
                                         (QUOTE, 0, len(QUOTE), 'Patient is a nonsmoker.')):
            evidence = [{'quote': text, 'start': start, 'end': end}]
            answer = {'text': text, 'status': 'supported', 'evidence': evidence}
            out = g.v3_option_answer(FIELDS[0], answer, notes, labels)
            self.assertNotEqual(out.get('text'), 'No')
        suggestion = {'text': '', 'status': 'conflict', 'suggestion': QUOTE,
                      'suggestion_evidence': [{'quote': QUOTE, 'start': 0, 'end': len(QUOTE)}]}
        self.assertNotIn('suggestion', g.v3_option_answer(FIELDS[0], suggestion, QUOTE, labels))

    def test_stored_relation_checks_the_same_whole_note_proof(self):
        for notes in (QUOTE + '\n\nThe patient smokes daily.',
                      'Historical statement:\n\n' + QUOTE,
                      QUOTE + '\n\nUnreviewed additional source.'):
            start = notes.index(QUOTE)
            answer = {'text': 'No', 'status': 'supported', 'reviewed': True,
                      'evidence': [{'quote': QUOTE, 'start': start, 'end': start + len(QUOTE)}]}
            page = g.as_currently_governed(g.governance_for(notes, FIELDS), notes, {**answer, 'label': 'Smoker'})
            self.assertEqual((page['status'], page['text']), ('conflict', ''))
            self.assertEqual(g.governed_decisions(notes, FIELDS, {'smoker': answer}), ['Smoker'])
            self.assertTrue(page['held_candidate']['context'])

    def test_malformed_companion_evidence_keeps_literal_relation_held(self):
        from core.v3_nonsmoker import evidence_needs_review
        good = {'quote': QUOTE, 'start': 0, 'end': len(QUOTE)}
        self.assertTrue(evidence_needs_review(QUOTE, FIELDS, [None, good]))
        self.assertTrue(evidence_needs_review(QUOTE, FIELDS, [{'quote': []}, good]))

    def test_text_field_keeps_its_existing_extractive_answer(self):
        out = run(QUOTE, {'Smoker': [QUOTE]}, fields=[field('s', 'Smoker', 'text')])['Smoker']
        self.assertEqual((out['status'], out['text']), ('supported', QUOTE))

    def test_existing_literal_labelled_values_are_unchanged(self):
        for notes, expected in (('Smoker: Yes.', 'Yes'), ('Smoker: No.', 'No')):
            self.assertEqual(self.answer(notes, notes)['text'], expected)


@override_settings(**LIVE)
class NaturalSmokerWorkflow(V3EncounterFixture, TestCase):
    walk = CompleteOrdinaryNoteWorkflow.walk

    def setUp(self):
        with patch('core.tests.test_word_v3_workflow.build_intake_form',
                   side_effect=lambda path: ordinary_input_form(path, ['Smoker'])):
            super().setUp()
        denial = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        denial.start(); self.addCleanup(denial.stop)

    def test_worker_review_save_finalize_and_original_word_option(self):
        self.walk(QUOTE, {'Smoker': [QUOTE]}, {'Smoker': 'No'})
        self.assertIn('Smoker  ☐ Yes  ☒ No', part_text(private_path(self.encounter.export_path).read_bytes()))
        evidence = self.encounter.answers[self.key('Smoker')]['evidence']
        self.assertEqual(evidence, [{'quote': QUOTE, 'start': 0, 'end': len(QUOTE)}])

    def test_old_supported_value_with_changed_scope_is_held_on_page_save_and_finalize(self):
        for notes in ('Family history:\n' + QUOTE, QUOTE + '\n\nThe patient smokes daily.'):
            start = notes.index(QUOTE)
            self.encounter.notes = notes
            self.encounter.answers = {self.key('Smoker'): {'status': 'supported', 'text': 'No', 'reviewed': True,
                'evidence': [{'quote': QUOTE, 'start': start, 'end': start + len(QUOTE)}]}}
            self.encounter.save(update_fields=['notes', 'answers'])
            row = self.client.get(f'/encounters/{self.encounter.pk}/').context['answer_rows'][0]
            self.assertEqual((row['status'], row['text']), ('conflict', ''))
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
            self.assertEqual(self.save({'Smoker': 'No'}).status_code, 302)
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
