"""Clinical source labels must retain side and subquestion boundaries."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from core.generation import fixture, validate_selections, Selection, Selections


class QuestionLabelTests(SimpleTestCase):
    def test_internal_colon_preserves_complete_question_and_evidence_offsets(self):
        fields = [{'key': 'right', 'label': 'Right previous treatment: vein'},
                  {'key': 'left', 'label': 'Left previous treatment: vein'}]
        notes = '  Right previous treatment: vein:  Synthetic right value\nLeft previous treatment: vein: Synthetic left value'
        answers = validate_selections(notes, fields, fixture(notes, fields))
        self.assertEqual([answers[key]['text'] for key in ('right', 'left')],
                         ['Synthetic right value', 'Synthetic left value'])
        for answer in answers.values():
            self.assertEqual(answer['status'], 'supported')
            for evidence in answer['evidence']:
                self.assertEqual(notes[evidence['start']:evidence['end']], evidence['quote'])

    def test_longer_matching_question_does_not_become_a_parent_answer(self):
        fields = [{'key': 'parent', 'label': 'History'}, {'key': 'specific', 'label': 'History: onset'}]
        notes = 'History: onset: Yesterday'
        answers = validate_selections(notes, fields, fixture(notes, fields))
        self.assertEqual(answers['parent']['status'], 'missing')
        self.assertEqual(answers['specific']['text'], 'Yesterday')
        with self.assertRaises(ValidationError):
            validate_selections(notes, fields, Selections(fields=[
                Selection(key='parent', quotes=['Yesterday'], conflict=False),
                Selection(key='specific', quotes=[], conflict=False)]))

    def test_unicode_question_and_negative_conflicting_values_keep_exact_offsets(self):
        fields = [{'key': 'context', 'label': 'Context'}, {'key': 'result', 'label': 'Straße: Befund'}]
        notes = 'Context: 🩺 source context\n STRASSE: Befund: No reflux documented.\nStraße: Befund: Reflux documented.'
        answers = validate_selections(notes, fields, fixture(notes, fields))
        self.assertEqual(answers['result']['status'], 'conflict')
        self.assertEqual([e['quote'] for e in answers['result']['evidence']],
                         ['No reflux documented.', 'Reflux documented.'])
        for evidence in answers['result']['evidence']:
            self.assertEqual(notes[evidence['start']:evidence['end']], evidence['quote'])

    def test_known_prewritten_label_does_not_hide_measurement_or_become_its_evidence(self):
        fields = [{'key': 'diameter', 'label': 'Right GSV at the SFJ: diameter (mm)'}]
        context = ['Prewritten statement: Right saphenous reflux finding']
        notes = fields[0]['label'] + ': 3.2 mm\n' + context[0] + ': No saphenous reflux in right lower extremity.'
        answers = validate_selections(notes, fields, fixture(notes, fields, context_labels=context), context_labels=context)
        self.assertEqual(answers['diameter']['text'], '3.2 mm')
        self.assertEqual(answers['diameter']['status'], 'supported')
        with self.assertRaises(ValidationError):
            validate_selections(notes, fields, Selections(fields=[Selection(key='diameter', quotes=['No saphenous reflux in right lower extremity.'], conflict=False)]), context_labels=context)
        # An unknown heading/line still carries potentially overriding context.
        unscoped = notes + '\nCorrection: measurement is uncertain.'
        self.assertEqual(validate_selections(unscoped, fields, fixture(unscoped, fields, context_labels=context), context_labels=context)['diameter']['status'], 'conflict')

    def test_context_label_more_specific_than_answer_label_is_not_its_answer(self):
        fields = [{'key': 'history', 'label': 'History'}]
        context = ['History: prior treatment']
        notes = 'History: prior treatment: No prior treatment.'
        answers = validate_selections(notes, fields, fixture(notes, fields, context_labels=context), context_labels=context)
        self.assertEqual(answers['history']['status'], 'missing')
