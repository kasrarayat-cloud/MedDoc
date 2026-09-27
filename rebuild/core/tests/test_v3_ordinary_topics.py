"""Bounded source-topic repairs; repeated destinations remain unresolved."""
import json
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from documents import word_v3
from .test_v3_ordinary_notes import run, field, LIVE, unit_response
from .test_v3_ordinary_context import retained_note
from . import test_v3_ordinary_context as context
from .test_v3_ordinary_input import ordinary_input_form
from .test_word_v3_workflow import two_knees_form_bytes, V3EncounterFixture, part_text
from core.jobs import enqueue, run_one
from core.models import Encounter
from core.security import private_path


class RepeatedSourceTopics(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = word_v3.inspect(two_knees_form_bytes())['fields']

    def answers(self, notes):
        return g.generate(notes, self.fields, {**g.configuration(), 'mode': 'fixture'})[0]

    def test_unique_indication_keeps_its_destination_while_repeated_questions_stay_held(self):
        notes = 'Indication: synthetic knee review\nPain: yes\nComments: settled'
        answers = self.answers(notes)
        for f in self.fields:
            answer = answers[f['key']]
            expected = ('supported', 'synthetic knee review') if f['label'] == 'Indication' else ('conflict', '')
            self.assertEqual((answer['status'], answer['text']), expected, f['label'])
            if f['label'] == 'Indication':
                self.assertEqual(g.governed_decisions(notes, self.fields, {f['key']: {**answer, 'reviewed': True}}), [])

    def test_a_repeated_comment_cannot_erase_correction_or_reference_to_indication(self):
        prefix = 'Indication: synthetic knee review\nPain: yes\nComments: '
        indication = next(f for f in self.fields if f['label'] == 'Indication')
        self.assertEqual(self.answers(prefix + 'settled')[indication['key']]['status'], 'supported')
        for comment in ('Indication is wrong.', 'Actually, the indication is left knee pain.',
                        'Indication was cancelled.', 'The pain is in the other knee.'):
            notes = prefix + comment
            answers = self.answers(notes)
            self.assertEqual(answers[indication['key']]['status'], 'conflict', comment)
            for f in self.fields:
                if f['label'] != 'Indication': self.assertEqual(answers[f['key']]['status'], 'conflict')
            quote = 'Indication: synthetic knee review'
            old = {'status': 'supported', 'text': 'synthetic knee review', 'reviewed': True,
                   'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
            self.assertIn('Indication', g.governed_decisions(notes, self.fields, {indication['key']: old}))

    def test_plain_duplicate_side_context_cannot_become_a_harmless_boundary(self):
        indication = next(f for f in self.fields if f['label'] == 'Indication')
        prefix = 'Indication: right knee assessment\nPain: yes\nComments: '
        self.assertEqual(self.answers(prefix + 'settled')[indication['key']]['status'], 'supported')
        for tail in ('left knee', 'Lt knee', 'L knee', 'Ｌｅｆｔ knee', 'le\u200bft knee'):
            notes = prefix + tail
            self.assertEqual(self.answers(notes)[indication['key']]['status'], 'conflict', tail)
            quote = 'Indication: right knee assessment'
            old = {'status': 'supported', 'text': 'right knee assessment', 'reviewed': True,
                   'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
            self.assertIn('Indication', g.governed_decisions(notes, self.fields, {indication['key']: old}))


class NominalPlanTopic(SimpleTestCase):
    def test_visible_compatibility_denials_cannot_release_the_opposite_assessment(self):
        fields = [field('a', 'Assessment', 'long_text'), field('p', 'Plan', 'long_text')]
        for denial in ('no', 'NO', 'ｎｏ', 'n\u200bo'):
            for finding in ('infection.', 'active bacterial infection.'):
                with self.subTest(denial=denial, finding=finding):
                    plan = denial + ' ' + finding
                    notes = 'Assessment: ' + finding + '\nPlan: ' + plan
                    self.assertFalse(g.plain_value(plan))
                    answers = run(notes, {'Assessment': ['Assessment: ' + finding], 'Plan': ['Plan: ' + plan]}, fields=fields)
                    self.assertEqual((answers['Assessment']['status'], answers['Assessment']['text']), ('conflict', ''))
                    self.assertEqual(answers['Assessment']['held_candidate']['context'][0]['quote'], 'Plan: ' + plan)
                    self.assertEqual(answers['Plan']['text'], plan)
                    quote = 'Assessment: ' + finding
                    old = {'status': 'supported', 'text': finding, 'reviewed': True,
                           'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
                    self.assertEqual(g.governed_decisions(notes, fields, {'a': old}), ['Assessment'])

    def test_compatibility_reading_only_withholds_and_does_not_create_plain_answers(self):
        for value in ('ｎｏ infection.', 'consent ｔｏｍｏｒｒｏｗ.', 'ｍｏｔｈｅｒ present.', 'ａｓ ａｂｏｖｅ.'):
            self.assertFalse(g.plain_value(value), value)
        fields = [field('a', 'Assessment', 'long_text'), field('p', 'Plan', 'long_text')]
        for plan in ('amoxicillin ｉｆ symptoms develop.', 'consent ｔｏｍｏｒｒｏｗ.', 'ｓｅｅ above.'):
            notes = 'Assessment: infection.\nPlan: ' + plan
            answer = run(notes, {'Assessment': ['Assessment: infection.']}, fields=fields)['Assessment']
            self.assertEqual(answer['status'], 'conflict', plan)
        # The literal option grammar is still required: compatibility conversion
        # is never an authorization to choose a printed answer.
        self.assertIsNone(g.v3_option_value(field('s', 'Smoker', 'choice', ['Yes', 'No']), 'Ｎｏ.'))

    def test_nominal_denial_keeps_the_earlier_assessment_governed(self):
        fields = [field('a', 'Assessment', 'long_text'), field('p', 'Plan', 'long_text')]
        for assessment in ('infection.', 'active bacterial infection.'):
            plan = 'no ' + assessment
            notes = 'Assessment: ' + assessment + '\nPlan: ' + plan
            picks = {'Assessment': ['Assessment: ' + assessment], 'Plan': ['Plan: ' + plan]}
            answer = run(notes, picks, fields=fields)['Assessment']
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
            self.assertEqual(answer['held_candidate']['text'], assessment)
            self.assertEqual([e['quote'] for e in answer['held_candidate']['context']], ['Plan: ' + plan])
            for quote in ('Assessment: ' + assessment, assessment):
                start = notes.index(quote)
                old = {'status': 'supported', 'text': assessment, 'reviewed': True,
                       'evidence': [{'quote': quote, 'start': start, 'end': start + len(quote)}]}
                governance = g.governance_for(notes, fields)
                shown = g.as_currently_governed(governance, notes, {**old, 'label': 'Assessment'})
                self.assertEqual((shown['status'], shown['text']), ('conflict', ''))
                self.assertEqual(g.governed_decisions(notes, fields, {'a': old}), ['Assessment'])

    def test_retained_note5_keeps_its_direct_assessment_beside_complete_nominal_plan(self):
        case = retained_note('r1-note5')
        path = Path(__file__).resolve().parents[3] / 'docs/rebuild/v1/ordinary-input-20260927/evidence/known-results.json'
        fields = next(c['fields'] for c in json.loads(path.read_text())['cases'] if c['name'] == case['name'])
        answers = run(case['notes'], case['picks'], fields=fields)
        for label, value in (('Assessment', 'mechanical low back pain.'),
                             ('Plan', 'naproxen 500 mg twice daily with food and physiotherapy.')):
            self.assertEqual((answers[label]['status'], answers[label]['text']), ('supported', value))
            key = next(f['key'] for f in fields if f['label'] == label)
            self.assertEqual(g.governed_decisions(case['notes'], fields, {key: {**answers[label], 'reviewed': True}}), [])

    def test_named_plan_keeps_qualification_question_reference_and_later_changes(self):
        fields = [field('a', 'Allergies'), field('c', 'Consent obtained', 'checkbox', ['Consent obtained']),
                  field('p', 'Plan', 'long_text')]
        for plan in ('penicillin?', 'see above.', 'the allergies are wrong.', 'to be obtained tomorrow.',
                     'amoxicillin. Actually, do not give it.', 'amoxicillin\nIt was cancelled.'):
            notes = 'Allergies: penicillin.\nConsent obtained: yes.\nPlan: ' + plan
            quote = 'Allergies: penicillin.'
            answer = run(notes, {'Allergies': [quote]}, fields=fields)['Allergies']
            self.assertEqual(answer['status'], 'conflict', plan)
            old = {'status': 'supported', 'text': 'penicillin.', 'reviewed': True,
                   'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
            self.assertIn('Allergies', g.governed_decisions(notes, fields, {'a': old}), plan)


@override_settings(**LIVE)
class CompleteRepeatedTopicWorkflow(V3EncounterFixture, TestCase):
    def setUp(self):
        def form(path):
            data = two_knees_form_bytes(); Path(path).write_bytes(data); return data
        with patch('core.tests.test_word_v3_workflow.build_intake_form', side_effect=form):
            super().setUp()

    def test_unique_answer_survives_worker_review_save_and_export_with_explicit_duplicate_decisions(self):
        notes = 'Indication: synthetic knee review\nPain: yes\nComments: settled'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/notes/',
            {'revision': self.encounter.revision, 'notes': notes}).status_code, 302)
        picks = {f['label']: ['Indication: synthetic knee review' if f['label'] == 'Indication'
                            else 'Pain: yes' if f['kind'] == 'choice' else 'Comments: settled']
                 for f in self.version.fields}
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = lambda **kw: unit_response(json.loads(kw['messages'][0]['content']), picks)
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            self.assertTrue(run_one())
            self.assertEqual(client.return_value.messages.create.call_count, 1)
        job.refresh_from_db(); self.assertEqual(job.state, 'succeeded', job.error)
        self.encounter.refresh_from_db()
        page = self.client.get(f'/encounters/{self.encounter.pk}/')
        for row in page.context['answer_rows']:
            self.assertEqual(row['status'], 'supported' if row['label'] == 'Indication' else 'conflict')
        payload = self.answers_payload({'Indication': 'synthetic knee review'})
        # Explicit clinician recovery, never counted as automatic repeated-field success.
        for f in self.version.fields:
            if f['label'] != 'Indication': payload['blank_' + f['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/', payload).status_code, 302)
        self.encounter.refresh_from_db()
        for f in self.version.fields:
            self.assertEqual(self.encounter.answers[f['key']]['status'],
                             'supported' if f['label'] == 'Indication' else 'left_blank')
        self.finalize(); self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'finalized')
        body = part_text(private_path(self.encounter.export_path).read_bytes())
        self.assertIn('Indication: synthetic knee review', body)
        self.assertNotIn('☒', body)
        self.assertEqual(private_path(self.template.original_path).read_bytes(), self.original)


@override_settings(**LIVE)
class CompleteNominalPlanWorkflow(V3EncounterFixture, TestCase):
    walk = context.CompleteOrdinaryNoteWorkflow.walk

    def setUp(self):
        with patch('core.tests.test_word_v3_workflow.build_intake_form', side_effect=lambda path:
                   ordinary_input_form(path, ['Assessment', 'Plan', 'Allergies', 'Smoker'])):
            super().setUp()

    def test_retained_note5_on_four_field_form_preserves_all_nominal_plan_words(self):
        # Full unchanged notes, declared four-field form slice. The retained
        # nine-field oracle and its remaining SOAP holds are not replaced.
        case = retained_note('r1-note5')
        expected = {'Assessment': 'mechanical low back pain.',
                    'Plan': 'naproxen 500 mg twice daily with food and physiotherapy.',
                    'Allergies': 'sulfa.', 'Smoker': 'Yes'}
        self.walk(case['notes'], {label: case['picks'][label] for label in expected}, expected)

    def assert_stale_denial_cannot_finalize(self, denial):
        self.encounter.notes = 'Assessment: infection.\nPlan: ' + denial + ' infection.'
        self.encounter.answers = {}
        for f in self.version.fields:
            label = f['label']
            value = {'Assessment': 'infection.', 'Plan': denial + ' infection.'}.get(label, '')
            quote = label + ': ' + value
            start = self.encounter.notes.index(quote) if value else 0
            self.encounter.answers[f['key']] = {'status': 'supported' if value else 'missing',
                'text': value, 'reviewed': True, 'evidence':
                    [{'quote': quote, 'start': start, 'end': start + len(quote)}] if value else []}
        self.encounter.save(update_fields=['notes', 'answers'])
        page = self.client.get(f'/encounters/{self.encounter.pk}/')
        assessment = next(row for row in page.context['answer_rows'] if row['label'] == 'Assessment')
        self.assertEqual((assessment['status'], assessment['text']), ('conflict', ''))
        self.finalize(); self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized')
        self.assertFalse(self.encounter.export_path)
        self.assertEqual(self.save({'Assessment': 'infection.', 'Plan': denial + ' infection.'}).status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers[self.key('Assessment')]['status'], 'supported')
        self.finalize(); self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized')
        self.assertFalse(self.encounter.export_path)

    def test_stale_reviewed_assessment_cannot_finalize_past_a_nominal_denial(self):
        self.assert_stale_denial_cannot_finalize('no')

    def test_stale_reviewed_assessment_cannot_finalize_past_a_fullwidth_denial(self):
        self.assert_stale_denial_cannot_finalize('ｎｏ')
