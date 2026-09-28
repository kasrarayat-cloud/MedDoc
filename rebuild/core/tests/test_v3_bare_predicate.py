"""Pinned finite-verb syntax keeps original patient source and context intact."""
from django.test import SimpleTestCase
from core import generation as g, v3_syntax as s
from .test_v3_ordinary_notes import field, run


class BarePatientPredicate(SimpleTestCase):
    def test_regular_finite_patient_verbs_are_complete_original_units(self):
        fields = [field('f', 'Clinical observations')]
        for verb in ('smokes', 'drinks', 'walks', 'coughs', 'falls', 'swims'):
            notes = 'The patient ' + verb + '.'
            answer = run(notes, {'Clinical observations': [notes]}, fields=fields)['Clinical observations']
            self.assertEqual((answer['status'], answer['text']), ('supported', notes), verb)
            self.assertEqual(g.governed_decisions(notes, fields, {'f': answer}), [])

    def test_noun_fragments_foreign_actor_and_qualified_shapes_gain_no_fallback(self):
        for notes in ('The patient feet.', 'The patient medications.', 'The patient diabetes.',
                      'The patient pain.', 'The patient smoke.', 'The patient advocate smokes.',
                      'The patient smokes if upset.', 'The patient does not smoke.',
                      'The patient smokes?', 'Her father smokes.'):
            self.assertFalse(s._bare_patient_clause(notes, (4, 11)), notes)
        fields = [field('f', 'Clinical observations')]
        for notes in ('The patient medications.', 'The patient diabetes.', 'The patient feet.',
                      'Family history:\nThe patient smokes.',
                      'The following symptoms are denied:\nThe patient coughs.'):
            quote = notes.split('\n')[-1]
            answer = run(notes, {'Clinical observations': [quote]}, fields=fields)['Clinical observations']
            self.assertEqual(answer['status'], 'conflict', notes)
