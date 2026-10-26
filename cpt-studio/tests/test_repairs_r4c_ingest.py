"""Regressions for refutation round 5, INGEST lens, PDF check boxes beside text (repair round 4c).

A displayed check box is written before the piece of page text it ties to. Where it may instead be the label's to its
left, or where the text line it would govern runs on into another column, its state is not written as decided: the
unread mark '[?]' is written and routing holds the item (contract-r4c section 1: never guess placement).

- extraction:0 (regression): boxes placed AFTER their option words ('Sedation: Moderate [x] MAC [ ]') in a two-column
  row: the last box is tied to the next column's sentence, and its unchecked state negated it;
- extraction:1 (regression): boxes placed BEFORE their option words ('Sedation: [x] Moderate [ ] MAC') in a two-column
  row: the line pypdf joins with the next column carried the last box's unchecked state into the next column;
- extraction:9 (over-hold): the first box of an ordinary 'Question: [ ] Yes [x] No' row was written '[?]' because the
  question sits to its left.

Each PDF is synthetic and built here from raw PDF syntax with the round-3 builders (pieces placed with reportlab's
Helvetica metrics, as the round-5 probes placed them), extracted with the sandboxed extract_document, routed for real
and assessed by the real engine.
"""
import unittest

from reportlab.pdfbase.pdfmetrics import stringWidth

from tests.test_repairs_r3_forms_pdf import FIELDS_NOTE, NOTE, Form, codes, extracted, text_line, text_of
from tests.test_repairs_r4_ingest import UNREAD, held_unread

SENTENCE = 'Cold snare polypectomy of the 6 mm sigmoid polyp was performed.'
ROW = 640


def width(text: str) -> float:
    return stringWidth(text, 'Helvetica', 11)


# --- extraction:0 -- option boxes after their option words, then the next column -------------------------------------

def trailing_row(first_on, second_on, *, kind='two boxes', gap=27.9, question='Sedation:', options=('Moderate', 'MAC'),
                 split=False, tooltips=False):
    """'Sedation:  Moderate [box]  MAC [box]', each box 4 pt after its option word and 8 pt before the next word, and
    the next column's sentence starting ``gap`` pt after the last box (the round-5 probe p12). ``kind``: two check
    boxes, or one check-box field whose kids carry the option names; ``split``: the question and the first option in
    one piece of text."""
    form = Form(NOTE[:4])
    x = 48.69
    boxes, place = [], x + width(question) + 8
    if split:
        form.line(text_line(x, ROW, f'{question} {options[0]}'))
        place = x + width(f'{question} {options[0]}') + 4
        boxes.append(place)
        place += 12 + 8
        rest = options[1:]
    else:
        form.line(text_line(x, ROW, question))
        rest = options
    for option in rest:
        form.line(text_line(place, ROW, option))
        place += width(option) + 4
        boxes.append(place)
        place += 12 + 8
    right = boxes[-1] + 12 + gap
    form.line(text_line(right, ROW, SENTENCE))
    form.line(text_line(48.69, ROW - 20, 'Tattoo:')).line(text_line(right, ROW - 20, 'Retrieval was complete.'))
    states = [first_on, second_on] + [False] * (len(options) - 2)
    rects = [(b, ROW - 3, b + 12, ROW + 9) for b in boxes]
    if kind == 'two boxes':
        for option, rect, on in zip(options, rects, states):
            form.checkbox(option if tooltips else f'Check Box{len(form.fields) + 1}', rect, on,
                          tu=option if tooltips else None)
    else:
        value = next((f'/{option}' for option, on in zip(options, states) if on), '/Off')
        form.group(question.rstrip(':'), [(rect, f'/{option}') for option, rect in zip(options, rects)], value,
                   radio=False)
    return form.build()


class Extraction0TrailingBoxesTests(unittest.TestCase):
    """The last of a row of boxes placed after their option words is the last option's, not the next column's: it is
    written '[?]' before the next column's sentence, never '☐'."""

    def test_the_round5_input_never_negates_the_next_column(self):
        for kind in ('two boxes', 'one field'):
            for tooltips in (False, True):
                with self.subTest(kind=kind, tooltips=tooltips):
                    text = text_of(trailing_row(True, False, kind=kind, tooltips=tooltips))
                    self.assertNotIn('☐ Cold snare', text)
                    self.assertIn(f'{UNREAD} {SENTENCE}', text)
                    held_unread(self, text, 'Cold snare polypectomy')
                    self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_every_unchecked_variant_holds_the_sentence(self):
        variants = {'both off': dict(first_on=False, second_on=False), 'split question': dict(split=True),
                    'three options': dict(options=('None', 'Moderate', 'MAC')), 'gap 12': dict(gap=12.0),
                    'gap 6': dict(gap=6.0), 'gap 4, as far as from its word': dict(gap=4.0), 'gap 40': dict(gap=40.0)}
        for name, changes in variants.items():
            with self.subTest(variant=name):
                arguments = dict(first_on=True, second_on=False) | changes
                text = text_of(trailing_row(arguments.pop('first_on'), arguments.pop('second_on'), **arguments))
                self.assertNotIn('☐ Cold snare', text)
                if name != 'gap 40':  # past BOX_GAP the last box is tied to nothing, and its row gets no glyph
                    self.assertIn(f'{UNREAD} {SENTENCE}', text)
                self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_no_unchecked_box_is_written_as_decided(self):
        """Neither unchecked box is written '☐': each may be the option word's to its left. The checked Moderate box
        keeps its glyph (a check negates nothing), and the line holds what it carries."""
        for first_on, second_on in ((True, False), (False, False), (False, True)):
            with self.subTest(first_on=first_on, second_on=second_on):
                text = text_of(trailing_row(first_on, second_on))
                self.assertNotIn('☐', text.split('[PDF form fields')[0])
                self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_text_whose_widths_the_font_does_not_give_is_not_measured(self):
        """The page's text in a TrueType font without /Widths, which pypdf measures with one default width: wide option
        words ('MMMMMM') then look shorter than they are, and the box after the first would seem to sit before the
        second. Text so measured gives no gaps, so the boxes are read as the label-left rule reads them."""
        from tests.test_repairs_ingest_pdf import esc
        form = Form(NOTE[:4])
        form.objects[4] = (b'<< /Type /Font /Subtype /TrueType /BaseFont /Synthetic-NoWidths /Encoding '
                           b'/WinAnsiEncoding >>')
        x = 48.69
        form.line(text_line(x, ROW, 'Sedation:'))
        first = x + width('Sedation:') + 8
        form.line(text_line(first, ROW, 'MMMMMM'))
        box1 = first + width('MMMMMM') + 4
        second = box1 + 12 + 8
        form.line(text_line(second, ROW, 'WWWWWW'))
        box2 = second + width('WWWWWW') + 4
        form.line(f'BT /F1 11 Tf {box2 + 12 + 27.9} {ROW} Td ({esc(SENTENCE)}) Tj ET')
        form.checkbox('Check Box1', (box1, ROW - 3, box1 + 12, ROW + 9), False)
        form.checkbox('Check Box2', (box2, ROW - 3, box2 + 12, ROW + 9), True)
        row = next(line for line in text_of(form.build()).split('\n') if line.startswith('Sedation'))
        self.assertNotIn('☐', row)
        self.assertIn(f'MMMMMM {UNREAD} WWWWWW', row)

    def test_every_box_checked_stays_ready(self):
        text = text_of(trailing_row(True, True))
        self.assertIn('Moderate ☒ MAC ☒ Cold snare', text)
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_where_the_option_words_end_cannot_be_measured(self):
        """Each option word written with trailing spaces that run under its box: where the word ends is not known, so the
        second box is read by the first: the first may be its left word's, so the second may be too."""
        form = Form(NOTE[:4])
        x = 48.69
        form.line(text_line(x, ROW, 'Sedation:'))
        first = x + width('Sedation:') + 8
        form.line(text_line(first, ROW, 'Moderate      '))
        box1 = first + width('Moderate') + 4
        second = box1 + 12 + 8
        form.line(text_line(second, ROW, 'MAC      '))
        box2 = second + width('MAC') + 4
        form.line(text_line(box2 + 12 + 27.9, ROW, SENTENCE))
        form.checkbox('Check Box1', (box1, ROW - 3, box1 + 12, ROW + 9), True)
        form.checkbox('Check Box2', (box2, ROW - 3, box2 + 12, ROW + 9), False)
        text = text_of(form.build())
        self.assertNotIn('☐ Cold snare', text)
        self.assertIn(f'{UNREAD} Cold snare', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')


# --- extraction:1 -- option boxes before their option words, then the next column ------------------------------------

def leading_row(first_on, second_on, *, gap=30.0, options=('Moderate', 'MAC'), question='Sedation:', tooltips=False,
                after=SENTENCE):
    """'Sedation:  [box] Moderate  [box] MAC', each box 4 pt before its option word, and the next column's ``after``
    starting ``gap`` pt after the last option word ends (the round-5 probe p13)."""
    form = Form(NOTE[:4])
    x = 48.69
    form.line(text_line(x, ROW, question))
    place, rects = x + width(question) + 8, []
    for option in options:
        rects.append((place, ROW - 3, place + 12, ROW + 9))
        form.line(text_line(place + 16, ROW, option))
        place += 16 + width(option) + 10
    right = place - 10 + gap
    if after:
        form.line(text_line(right, ROW, after))
    states = [first_on, second_on] + [False] * (len(options) - 2)
    for option, rect, on in zip(options, rects, states):
        form.checkbox(option if tooltips else f'Check Box{len(form.fields) + 1}', rect, on,
                      tu=option if tooltips else None)
    return form.build()


class Extraction1LeadingBoxesBeforeAColumnTests(unittest.TestCase):
    def test_the_last_option_never_negates_the_next_column(self):
        for gap in (18.0, 30.0, 70.0, 100.0):
            for tooltips in (False, True):
                with self.subTest(gap=gap, tooltips=tooltips):
                    text = text_of(leading_row(True, False, gap=gap, tooltips=tooltips))
                    self.assertNotIn('☐ MAC Cold snare', text)
                    self.assertIn(f'☒ Moderate {UNREAD} MAC Cold snare', text)
                    held_unread(self, text, 'Cold snare polypectomy')
                    self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_every_option_unchecked_and_three_options(self):
        text = text_of(leading_row(False, False))
        self.assertIn(f'☐ Moderate {UNREAD} MAC Cold snare', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        text = text_of(leading_row(False, True, options=('None', 'Moderate', 'MAC')))
        self.assertIn(f'☐ None ☒ Moderate {UNREAD} MAC Cold snare', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_checked_last_option_and_a_single_column_row_keep_their_glyphs(self):
        """(With generic field names an unchecked field line holds the page's other items: routing's own rule.)"""
        text = text_of(leading_row(False, True))
        self.assertIn('☐ Moderate ☒ MAC Cold snare', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        text = text_of(leading_row(True, False, question='Interventions:', options=('Biopsy', 'Cold snare polypectomy'),
                                   after=''))
        self.assertIn('Interventions: ☒ Biopsy ☐ Cold snare polypectomy', text)
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        self.assertNotEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_a_kerned_option_and_spaces_in_the_gap(self):
        """The last option drawn with a TJ array that opens with an adjustment is found where it starts (no hold for
        that); a string of spaces drawn in the column gap is no ink, so the gap is still read."""
        from tests.test_repairs_ingest_pdf import esc

        def row(after_spaces, after):
            form = Form(NOTE[:4])
            form.line(text_line(48.69, ROW, 'Sedation:'))
            first = 48.69 + width('Sedation:') + 8
            form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), True)
            form.line(text_line(first + 16, ROW, 'Moderate'))
            second = first + 16 + width('Moderate') + 10
            form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
            form.line(f'BT /F1 11 Tf {second + 16} {ROW} Td [-120 ({esc("MAC")})] TJ ET')
            end = second + 16 + 1.32 + width('MAC')
            if after_spaces:
                form.line(f'BT /F1 11 Tf {end + 2} {ROW} Td ({" " * 12}) Tj ET')
            if after:
                form.line(text_line(end + 40, ROW, after))
            return text_of(form.build())

        for after_spaces in (False, True):
            with self.subTest(after_spaces=after_spaces):
                text = row(after_spaces, SENTENCE)
                self.assertIn(f'☒ Moderate {UNREAD} MAC', text)
                self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        self.assertIn('Sedation: ☒ Moderate ☐ MAC', row(False, ''))  # alone on its line it keeps its glyph

    def test_one_text_operator_across_the_column_gap(self):
        """The last option and the next column's sentence drawn by one TJ array, with a string of spaces between them:
        the spaces are no ink, so the gap between the columns is read and the unchecked box holds the line."""
        from tests.test_repairs_ingest_pdf import esc
        form = Form(NOTE[:4])
        form.line(text_line(48.69, ROW, 'Sedation:'))
        first = 48.69 + width('Sedation:') + 8
        form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), True)
        form.line(text_line(first + 16, ROW, 'Moderate'))
        second = first + 16 + width('Moderate') + 10
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
        form.line(f'BT /F1 11 Tf {second + 16} {ROW} Td [({esc("MAC")}) -200 ({" " * 12}) -100 ({esc(SENTENCE)})] TJ ET')
        text = text_of(form.build())
        self.assertNotIn('☐ MAC', text)
        self.assertIn(f'{UNREAD} MAC', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_piece_whose_text_is_not_where_the_layer_puts_it_is_held(self):
        """The last option's piece opens with a string of spaces, so its text starts right of the piece's origin: where
        it ends cannot be read, so the box before it is held, never written as the next column's."""
        from tests.test_repairs_ingest_pdf import esc
        form = Form(NOTE[:4])
        form.line(text_line(48.69, ROW, 'Sedation:'))
        first = 48.69 + width('Sedation:') + 8
        form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), True)
        form.line(text_line(first + 16, ROW, 'Moderate'))
        second = first + 16 + width('Moderate') + 10
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
        form.line(f'BT /F1 11 Tf {second + 16} {ROW} Td ( ) Tj 6 0 Td ({esc("MAC")}) Tj ET')
        form.line(text_line(second + 16 + 6 + width('MAC') + 30, ROW, SENTENCE))
        text = text_of(form.build())
        self.assertNotIn('☐ MAC', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_an_option_written_in_pieces_is_one_option(self):
        """The last option's words drawn as separate pieces, a word space apart: no column gap, so the glyph stays."""
        form = Form(NOTE[:4])
        form.line(text_line(72, ROW, 'Interventions:'))
        box = 72 + width('Interventions:') + 8
        form.checkbox('Check Box1', (box, ROW - 3, box + 12, ROW + 9), True)
        form.line(text_line(box + 16, ROW, 'Biopsy'))
        second = box + 16 + width('Biopsy') + 10
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
        x = second + 16
        for word in ('Cold', 'snare', 'polypectomy'):
            form.line(text_line(x, ROW, word))
            x += width(word + ' ')
        text = text_of(form.build())
        self.assertIn('☒ Biopsy ☐ Cold snare polypectomy', text)
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')


# --- extraction:9 -- an ordinary yes/no row --------------------------------------------------------------------------

def yes_no_row(yes, no, *, names=('Biopsy yes', 'Biopsy no'), tooltips=None, question='Biopsy taken:'):
    """'Biopsy taken: [box] Yes [box] No' as two check boxes, each 4 pt before its option word, the first 6 pt after
    the question (the round-5 probe p5), then a performed sentence."""
    form = Form(NOTE[:4] + [(72, 660, 'Procedure details:')])
    form.line(text_line(72, 620, question))
    first = 72 + width(question) + 6
    form.checkbox(names[0], (first, 617, first + 10, 627), yes, tu=tooltips[0] if tooltips else None)
    form.line(text_line(first + 14, 620, 'Yes'))
    second = first + 14 + width('Yes') + 12
    form.checkbox(names[1], (second, 617, second + 10, 627), no, tu=tooltips[1] if tooltips else None)
    form.line(text_line(second + 14, 620, 'No'))
    form.line(text_line(72, 600, 'Cold snare polypectomy was performed.'))
    return form.build()


def section_row(biopsy, snare):
    form = Form(NOTE[:4])
    form.line(text_line(72, 660, 'Interventions:'))
    first = 72 + width('Interventions:') + 6
    form.checkbox('Check Box1', (first, 657, first + 10, 667), biopsy)
    form.line(text_line(first + 14, 660, 'Biopsy'))
    second = first + 14 + width('Biopsy') + 12
    form.checkbox('Check Box2', (second, 657, second + 10, 667), snare)
    form.line(text_line(second + 14, 660, 'Cold snare polypectomy'))
    return form.build()


class Extraction9OrdinaryYesNoRowTests(unittest.TestCase):
    def test_the_yes_no_row_is_read_as_it_shows(self):
        for names, tooltips in ((('Biopsy yes', 'Biopsy no'), None), (('Check Box1', 'Check Box2'), None),
                                (('Check Box1', 'Check Box2'), ('Biopsy taken: yes', 'Biopsy taken: no'))):
            with self.subTest(names=names, tooltips=tooltips):
                text = text_of(yes_no_row(False, True, names=names, tooltips=tooltips))
                self.assertIn('Biopsy taken: ☐ Yes ☒ No', text)
                self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
                text = text_of(yes_no_row(True, False, names=names, tooltips=tooltips))
                self.assertIn('Biopsy taken: ☒ Yes ☐ No', text)
                self.assertNotEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_a_word_with_trailing_spaces_under_the_next_box(self):
        """'Yes' written with trailing spaces that run under the No box: where it ends is not known, so the No box is read
        by the Yes box, which leads its word: both are written as they show."""
        form = Form(NOTE[:4] + [(72, 660, 'Procedure details:')])
        form.line(text_line(72, 620, 'Biopsy taken:'))
        first = 72 + width('Biopsy taken:') + 6
        form.checkbox('Check Box1', (first, 617, first + 10, 627), True)
        form.line(text_line(first + 14, 620, 'Yes' + ' ' * 8))
        second = first + 14 + width('Yes') + 12
        form.checkbox('Check Box2', (second, 617, second + 10, 627), False)
        form.line(text_line(second + 14, 620, 'No'))
        self.assertIn('Biopsy taken: ☒ Yes', text_of(form.build()))
        self.assertIn('☐ No', text_of(form.build()))

    def test_a_question_without_a_colon(self):
        text = text_of(yes_no_row(False, True, question='Biopsy taken'))
        self.assertIn('Biopsy taken ☐ Yes ☒ No', text)

    def test_the_section_row_reads_its_boxes(self):
        text = text_of(section_row(False, True))
        self.assertIn('Interventions: ☐ Biopsy ☒ Cold snare polypectomy', text)
        self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_lone_box_after_a_label_is_still_held(self):
        """Positive control (round-4 extraction:0): a single box with a label to its left and the next column's sentence
        to its right is held, whatever the gap."""
        from tests.test_repairs_r4_ingest import two_column
        for gap in (27.94, 6.0, 2.0):
            with self.subTest(gap=gap):
                result = extracted(two_column(False, gap_to_right=gap))
                self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
                self.assertIn(f'{UNREAD} Cold snare polypectomy', result.text)

    def test_labels_with_colons_after_each_box_keep_the_hold(self):
        """'Biopsy: [ ]  Polypectomy: [ ]' then the next column: each box follows its own label (the tied piece ends with
        a colon), so neither is written as the next piece's state."""
        form = Form(NOTE[:4])
        x = 48.69
        form.line(text_line(x, ROW, 'Biopsy:'))
        first = x + width('Biopsy:') + 4
        form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), False)
        form.line(text_line(first + 16, ROW, 'Polypectomy:'))
        second = first + 16 + width('Polypectomy:') + 4
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
        form.line(text_line(second + 40, ROW, SENTENCE))
        text = text_of(form.build())
        self.assertNotIn('☐ Polypectomy', text)
        self.assertNotIn('☐ Cold snare', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_colon_labels_the_next_box_even_where_the_box_hugs_it(self):
        """'Biopsy:  [ ] Polypectomy: [x]': the first box sits nearer 'Polypectomy:' than 'Biopsy:', but a word ending
        with a colon labels the box after it, so the unchecked first box is not written as Polypectomy's."""
        form = Form(NOTE[:4])
        form.line(text_line(48.69, ROW, 'Biopsy:'))
        first = 48.69 + width('Biopsy:') + 10
        form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), False)
        form.line(text_line(first + 14, ROW, 'Polypectomy:'))
        second = first + 14 + width('Polypectomy:') + 4
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), True)
        form.line(text_line(second + 12 + 27.9, ROW, SENTENCE))
        text = text_of(form.build())
        self.assertNotIn('☐ Polypectomy', text)
        self.assertIn(f'{UNREAD} Polypectomy:', text)


if __name__ == '__main__':
    unittest.main()
