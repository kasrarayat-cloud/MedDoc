"""Ordinary destination guards, shared by generation and historical review."""
from django.test import SimpleTestCase
from core import generation as g
from .test_v3_ordinary_notes import field, run


class OrdinaryDestinationSide(SimpleTestCase):
    def assert_held_everywhere(self, target, notes):
        fields = [target]
        answer = run(notes, {target['label']: [notes]}, fields=fields)[target['label']]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        old = {'text': notes, 'status': 'supported', 'reviewed': True,
               'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
        governance = g.governance_for(notes, fields)
        self.assertIsNotNone(g.governed_supported(governance, notes, old, target['label']))
        page = g.as_currently_governed(governance, notes, {**old, 'label': target['label']})
        self.assertEqual((page['status'], page['text']), ('conflict', ''))
        self.assertEqual(g.governed_decisions(notes, fields, {target['key']: old}), [target['label']])

    def test_opposite_side_never_gains_a_unique_destination(self):
        for label in ('Right knee', 'Rt. knee', '(R) knee'):
            with self.subTest(label=label):
                self.assert_held_everywhere(field('site', label), 'The patient has left knee pain.')

    def test_complete_original_context_scopes_even_a_generic_label(self):
        target = field('site', 'Findings'); target['context'] = 'Current examination > Right knee'
        self.assert_held_everywhere(target, 'The patient has left knee pain.')

    def test_missing_or_mixed_side_is_not_a_specific_side_answer(self):
        for notes in ('The patient has knee pain.', 'The patient has bilateral knee pain.',
                      'The patient has right and left knee pain.'):
            with self.subTest(notes=notes):
                self.assert_held_everywhere(field('site', 'Right knee'), notes)

    def test_same_explicit_side_and_unscoped_destination_still_work(self):
        for label, notes in (('Right knee', 'The patient has right-sided knee pain.'),
                             ('Clinical findings', 'The patient has left knee pain.')):
            with self.subTest(label=label):
                fields = [field('site', label)]
                answer = run(notes, {label: [notes]}, fields=fields)[label]
                self.assertEqual((answer['status'], answer['text']), ('supported', notes))
                self.assertEqual(g.governed_decisions(notes, fields, {'site': {**answer, 'reviewed': True}}), [])

    def test_own_complete_labelled_value_keeps_its_explicit_scope(self):
        target = field('site', 'Right knee')
        notes = 'Right knee: painful.'
        answer = run(notes, {'Right knee': [notes]}, fields=[target])['Right knee']
        self.assertEqual((answer['status'], answer['text']), ('supported', 'painful.'))
