"""Regressions for refutation round 5, BOXES' findings, real files: fillable PDFs through the sandboxed extract_document,
then routing for the document's own date and the real validation engine.

- declared:0: a radio group asking whether the procedure was done ('Procedure performed?', or a generic 'Group1' whose
  tooltip asks it), answered No: extraction writes '<label>?: No', which the field done-question reader did not read,
  and the cancelled EUS was a ready 43242;
- declared:1: the same for 'Procedure cancelled?' answered No, read as a cancellation, so the performed EUS was
  excluded; also a text field typed 'No' beside its printed question standing alone.

Synthetic documents only, built here from raw PDF syntax.
"""
import unittest

from tests.test_repairs_r3_forms_pdf import codes, extracted, text_line, widget_rect
from tests.test_repairs_r4_boxes_pdf import EUS_LINE, EUS_LINES, page_form, row_y
from tests.test_repairs_status_r2_routing import family


def radio_form(question, selected, *, name=None, tu=None, at_end=True):
    """EUS_LINES with the printed ``question`` and its Yes / No radio row, at the end or right under the procedure."""
    lines = EUS_LINES + [question] if at_end else EUS_LINES[:1] + [question] + EUS_LINES[1:]
    index = len(EUS_LINES) if at_end else 1
    form = page_form(lines)
    y = row_y(lines, index)
    form.line(text_line(300, y, 'Yes')).line(text_line(360, y, 'No'))
    form.group(name or question, [(widget_rect(y, 284), '/Yes'), (widget_rect(y, 344), '/No')], f'/{selected}', tu=tu)
    return extracted(form.build())


def text_field_form(question, value):
    """EUS_LINES with the printed ``question`` standing alone and a text field beside it holding ``value``."""
    lines = EUS_LINES + [question]
    form = page_form(lines)
    y = row_y(lines, len(EUS_LINES))
    form.textfield(question.rstrip(':'), (330, y - 3, 560, y + 11), value)
    return extracted(form.build())


class Declared0DoneQuestionRadioTests(unittest.TestCase):
    """declared:0 (critical, a regression against 4347acd): a done-question radio answered No holds the EUS."""
    QUESTIONS = ('Procedure performed?', 'Was the procedure performed?', 'Procedure performed today?',
                 'Procedure completed?')

    def test_answered_no_holds(self):
        for question in self.QUESTIONS:
            for at_end in (True, False):
                with self.subTest(question=question, at_end=at_end):
                    result = radio_form(question, 'No', at_end=at_end)
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertIn(f'{question}: No', result.text)
                    self.assertNotEqual(family(result.text, 'gi.eus'), 'performed')
                    self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')

    def test_a_generic_name_with_the_question_as_its_tooltip(self):
        result = radio_form('Procedure performed?', 'No', name='Group1', tu='Procedure performed?')
        self.assertIn('Procedure performed?: No', result.text)
        self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')

    def test_answered_yes_stays_ready(self):
        for question in self.QUESTIONS:
            with self.subTest(question=question):
                result = radio_form(question, 'Yes')
                self.assertEqual(family(result.text, 'gi.eus'), 'performed')
                self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'ready')


class Declared1CancelQuestionRadioTests(unittest.TestCase):
    """declared:1 (critical, a regression against 4347acd): a cancellation question answered No is held, never read as
    a cancellation; answered Yes it still cancels."""
    QUESTIONS = ('Procedure cancelled?', 'Was the procedure cancelled?')

    def test_answered_no_is_never_excluded(self):
        for question in self.QUESTIONS:
            for at_end in (True, False):
                with self.subTest(question=question, at_end=at_end):
                    result = radio_form(question, 'No', at_end=at_end)
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertNotIn(family(result.text, 'gi.eus'), ('cancelled', 'negated'))
                    self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')
        result = radio_form('Procedure cancelled?', 'No', name='Group1', tu='Procedure cancelled?')
        self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')

    def test_a_text_field_beside_its_printed_question(self):
        for question in ('Procedure cancelled:', 'Procedure cancelled?', 'Was the procedure cancelled?'):
            with self.subTest(question=question):
                result = text_field_form(question, 'No')
                self.assertIn(question.rstrip(':') + ': No', result.text)
                self.assertNotIn(family(result.text, 'gi.eus'), ('cancelled', 'negated'))
                self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')
                yes = text_field_form(question, 'Yes')
                self.assertEqual(family(yes.text, 'gi.eus'), 'cancelled')

    def test_answered_yes_still_cancels(self):
        for question in self.QUESTIONS:
            with self.subTest(question=question):
                result = radio_form(question, 'Yes')
                self.assertEqual(family(result.text, 'gi.eus'), 'cancelled')
                self.assertIn(codes(result.text, ('43242', EUS_LINE))[0], ('excluded', 'held'))


if __name__ == '__main__':
    unittest.main()
