"""Narrow retained source subjects; synthetic selection and mocked worker, never a provider call."""
import copy
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.security import private_path
from . import test_v3_ordinary_context as context_tests
from .test_v3_ordinary_input import ordinary_input_form
from .test_v3_ordinary_notes import LIVE, field, run
from .test_word_v3_workflow import V3EncounterFixture, part_text

ALLERGY = 'No known drug allergies.'
EXAMS = ('Neurological examination is normal.', 'Heart and lung examination was normal.')
FIELDS = [field('a', 'Allergies'), field('e', 'Examination', 'long_text'), field('p', 'Plan', 'long_text')]


class LiteralSubjects(SimpleTestCase):
    def test_exact_declaration_and_retained_heads_keep_every_source_word(self):
        for exam in EXAMS:
            notes = ALLERGY + ' ' + exam
            answers = run(notes, {'Allergies': [ALLERGY], 'Examination': [exam]}, fields=FIELDS)
            for label, quote in (('Allergies', ALLERGY), ('Examination', exam)):
                answer = answers[label]
                self.assertEqual((answer['status'], answer['text']), ('supported', quote))
                start = notes.index(quote)
                self.assertEqual(answer['evidence'], [{'quote': quote, 'start': start, 'end': start + len(quote)}])
                self.assertIsNone(g.governed_supported(g.governance_for(notes, FIELDS), notes, answer, label))

    def test_declaration_does_not_relax_fragments_or_other_allergy_wording(self):
        for quote in ('No known drug allergies', 'No known allergies.', 'Known drug allergies.',
                      'No drug allergies.', 'No known drug allergies?', 'No known drug allergies...',
                      'No known drug allergies currently.', 'No known drug allergies except penicillin.',
                      'Not no known drug allergies.', 'Previously no known drug allergies.',
                      'Her mother has no known drug allergies.'):
            with self.subTest(quote=quote):
                answer = run(quote, {'Allergies': [quote]}, fields=FIELDS)['Allergies']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertNotIn('suggestion', answer)

    def test_retained_anatomical_heads_do_not_strip_negation_or_qualifiers(self):
        for quote in ('Neurological examination is not normal.', 'Heart and lung examination was not performed today.'):
            answer = run(quote, {'Examination': [quote]}, fields=FIELDS)['Examination']
            self.assertTrue(answer['status'] == 'conflict' or answer['text'] == quote)
        for quote in ('No neurological examination was performed.', 'Previous neurological examination was normal.',
                      'Neurological examination of her mother is normal.', 'Neurological examination may be normal.',
                      'If heart and lung examination is normal, discharge.', 'Neurological examination normal.'):
            with self.subTest(quote=quote):
                answer = run(quote, {'Examination': [quote]}, fields=FIELDS)['Examination']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_new_subjects_cannot_fill_foreign_fields(self):
        for label, quote in (('Plan', ALLERGY), ('Examination', ALLERGY), ('Allergies', EXAMS[0]), ('Plan', EXAMS[1])):
            answer = run(quote, {label: [quote]}, fields=FIELDS)[label]
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
            evidence = [{'quote': quote, 'start': 0, 'end': len(quote)}]
            stored = {'status': 'supported', 'text': quote, 'evidence': evidence, 'reviewed': True}
            key = next(f['key'] for f in FIELDS if f['label'] == label)
            self.assertEqual(g.governed_decisions(quote, FIELDS, {key: stored}), [label])

    def test_family_scope_corrections_and_unknown_neighbours_remain_held(self):
        for label, quote in (('Allergies', ALLERGY), ('Examination', EXAMS[0]), ('Examination', EXAMS[1])):
            for notes in ('Family history:\n' + quote, 'For her mother:\n\n' + quote,
                          'Hypothetical:\n' + quote, 'Previous visit:\n' + quote,
                          'Father is here. ' + quote, quote + ' Actually, the previous statement is wrong.',
                          quote + '\n\nCorrection: the previous statement is wrong.'):
                with self.subTest(label=label, notes=notes):
                    answer = run(notes, {label: [quote]}, fields=FIELDS)[label]
                    self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                    self.assertNotIn('suggestion', answer)
                    start = notes.index(quote)
                    stored = {'status': 'supported', 'text': quote, 'reviewed': True,
                              'evidence': [{'quote': quote, 'start': start, 'end': start + len(quote)}]}
                    key = next(f['key'] for f in FIELDS if f['label'] == label)
                    self.assertEqual(g.governed_decisions(notes, FIELDS, {key: stored}), [label])

    def test_duplicate_declarations_and_cross_topic_allergy_references_stay_held(self):
        for other in (ALLERGY, 'Allergies: penicillin.', 'Assessment: probable penicillin allergy.'):
            for gap in (' ', '\n\n'):
                notes = ALLERGY + gap + other
                fields = FIELDS + [field('d', 'Assessment')]
                answer = run(notes, {'Allergies': [ALLERGY]}, fields=fields)['Allergies']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertNotIn('suggestion', answer)
                stored = {'status': 'supported', 'text': ALLERGY, 'reviewed': True,
                          'evidence': [{'quote': ALLERGY, 'start': 0, 'end': len(ALLERGY)}]}
                self.assertEqual(g.governed_decisions(notes, fields, {'a': stored}), ['Allergies'])

    def test_only_unique_unscoped_text_destination_qualifies(self):
        variants = [[*FIELDS, field('a2', 'Allergies')]]
        for kind in ('choice', 'multi_choice', 'checkbox'):
            variants.append([field('a', 'Allergies', kind, ['Yes', 'No'])])
        scoped = copy.deepcopy(FIELDS); scoped[0]['context'] = 'Family history'; variants.append(scoped)
        for fields in variants:
            answer = run(ALLERGY, {'Allergies': [ALLERGY]}, fields=fields)['Allergies']
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_new_exam_heads_refuse_scoped_destinations_in_generation_and_stored_review(self):
        for quote in EXAMS:
            for context in ('Mother', 'Family history', 'Left knee', 'Right knee', 'Previous visit',
                            'Section 2', 'Examination | Donor'):
                with self.subTest(quote=quote, context=context):
                    fields = copy.deepcopy(FIELDS)
                    fields[1]['context'] = context
                    answer = run(quote, {'Examination': [quote]}, fields=fields)['Examination']
                    self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                    self.assertNotIn('suggestion', answer)
                    stored = {'status': 'supported', 'text': quote, 'reviewed': True,
                              'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
                    reading = g.governance_for(quote, fields)
                    self.assertEqual(g.as_currently_governed(reading, quote, {**stored, 'label': 'Examination'})['status'], 'conflict')
                    self.assertEqual(g.governed_decisions(quote, fields, {'e': stored}), ['Examination'])


@override_settings(**LIVE)
class LiteralSubjectsWorkflow(V3EncounterFixture, TestCase):
    walk = context_tests.CompleteOrdinaryNoteWorkflow.walk

    def setUp(self):
        with patch('core.tests.test_word_v3_workflow.build_intake_form',
                   side_effect=lambda path: ordinary_input_form(path, ['Allergies', 'Examination'])):
            super().setUp()
        denial = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        denial.start(); self.addCleanup(denial.stop)

    def test_worker_review_save_finalize_exports_complete_negative_declaration_and_head(self):
        exam = EXAMS[0]
        self.walk(ALLERGY + ' ' + exam, {'Allergies': [ALLERGY], 'Examination': [exam]},
                  {'Allergies': ALLERGY, 'Examination': exam})
        body = part_text(private_path(self.encounter.export_path).read_bytes())
        self.assertIn(ALLERGY, body); self.assertIn(exam, body)

    def test_changed_scope_is_held_on_page_save_and_finalize(self):
        for quote, label in ((ALLERGY, 'Allergies'), (EXAMS[1], 'Examination')):
            notes = 'Family history:\n' + quote
            start = notes.index(quote)
            self.encounter.notes = notes
            self.encounter.answers = {self.key(label): {'status': 'supported', 'text': quote, 'reviewed': True,
                'evidence': [{'quote': quote, 'start': start, 'end': start + len(quote)}]}}
            self.encounter.save(update_fields=['notes', 'answers'])
            rows = self.client.get(f'/encounters/{self.encounter.pk}/').context['answer_rows']
            row = next(r for r in rows if r['label'] == label)
            self.assertEqual((row['status'], row['text']), ('conflict', ''))
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
            self.assertEqual(self.save({label: quote}).status_code, 302)
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
