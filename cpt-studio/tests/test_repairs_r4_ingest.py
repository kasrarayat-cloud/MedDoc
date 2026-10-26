"""Regressions for refutation round 4, INGEST lens, PDF check boxes: a printed box whose state the page does not show
plainly is never read as a decided box.

The rule (contract-r4b sections 1 and 2): where a widget, a radio button or a mark disagrees with a printed box, where
a printed box's position cannot be read, or where two candidates compete for it, extraction writes the unread mark
'[?]' and routing holds the item (BOX_UNREAD, a non-silent cue). A box with a label to its left on its row is not
tied to the next column's text (the round-2b placement is restored for that layout).

- extraction:0: a label-left box in a two-column table is not written before the next column's sentence;
- extraction:1: a printed ticked box under an unchecked widget is '[?]', never '☐';
- extraction:2: a radio button over a printed box replaces it like a check box;
- extraction:6, contract:1 (c): a mark other than X / ✓ over a printed box (an Ink tick, a path stamp, a typed ✗)
  makes it '[?]' and names the page;
- extraction:7, contract:1 (a, b): a printed box under a widget whose position cannot be read is '[?]';
- extraction:10: a widget laid over a printed box's ink (its left side bearing) replaces the box: one glyph;
- extraction:8: placing boxes on a crowded row stays near-linear.

Each PDF is synthetic and built here from raw PDF syntax with the round-3 builders, extracted with the sandboxed
extract_document (or in process where only the extraction is timed), routed for real and assessed by the real engine.
"""
import time
import unittest

from studio.ingest import pdf as pdf_module
from studio.gi import detect
from tests.test_repairs_ingest_pdf import esc, in_process, stream
from tests.test_repairs_r3_forms_pdf import (BIOPSY_ROW, FIELDS_NOTE, NOTE, SNARE_ROW, Form, boxed_line, codes,
                                             extracted, text_line, text_of, to_unicode, widget_rect)
from tests.test_repairs_r3_forms_routing import not_silent
from tests.test_repairs_status_r2_routing import read

UNREAD = '[?]'
OVERLAP = ('Page 1 has a form check box over a printed box whose position could not be read, so the box may show a '
           'different state than the text; check the original.')
UNREAD_NOTE = ('Page 1 has a printed box whose state a form check box or a mark placed on or beside it contradicts, or '
               'that could not be read as checked or not; it was written as unread ([?]), so check the original.')
BOX_UNREAD = detect.BOX_UNREAD


def held_unread(test, text, phrase):
    """The item at ``phrase`` is held by the unread box, with its non-silent cue."""
    status, cues = read(text, phrase)
    test.assertEqual(status, 'uncertain', (phrase, cues))
    test.assertTrue(not_silent(cues), cues)
    test.assertIn(BOX_UNREAD, cues)


# --- extraction:0 -- a label left of its box, in a two-column table -------------------------------------------------

def two_column(checked, *, column_wise=False, gap_to_right=27.94, tooltip=None, name='Biopsy'):
    """'Biopsy:' (Helvetica 11, 48.69-84.74 pt) with a check box 4 pt after it, and the next column's sentence
    starting ``gap_to_right`` pt right of the box, as Chrome prints an 80 pt label column."""
    sentence = 'Cold snare polypectomy of the 6 mm sigmoid polyp was performed.'
    right = 100.74 + gap_to_right
    rows = [(48.69, 640, 'Biopsy:'), (right, 640, sentence), (48.69, 620, 'Tattoo:'), (right, 620, 'Retrieval was complete.')]
    if column_wise:
        rows = [rows[0], rows[2], rows[1], rows[3]]
    form = Form(NOTE[:4] + rows)
    form.checkbox(name, (88.74, 637, 100.74, 649), checked, tu=tooltip)
    return form.build()


class Extraction0LabelLeftBoxTests(unittest.TestCase):
    """A box with a label just left of it is not tied to the piece of the next column on its right: nothing is
    written, as at d05326ef, and the form-field line is left to routing."""

    def test_the_next_columns_sentence_is_never_negated(self):
        for column_wise in (False, True):
            for gap in (27.94, 6.0):
                with self.subTest(column_wise=column_wise, gap=gap):
                    result = extracted(two_column(False, column_wise=column_wise, gap_to_right=gap))
                    self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
                    self.assertNotIn('☐', result.text)
                    self.assertIn('[?] Cold snare polypectomy of the 6 mm sigmoid polyp was performed.', result.text)
                    self.assertIn('Biopsy: not checked', result.text)
                    self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_the_verifiers_input_holds_both_and_excludes_neither(self):
        """An unchecked 'Biopsy' box, the sentence 27.9 pt to its right: the box may be the label's or the sentence's,
        so what it sits beside is held, never negated, and the unchecked biopsy is never ready."""
        text = text_of(two_column(False))
        self.assertIn('Biopsy: [?] Cold snare polypectomy of the 6 mm sigmoid polyp was performed.', text)
        held_unread(self, text, 'Cold snare polypectomy')
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'), ('45380', 'Biopsy')), ('held', 'held'))

    def test_the_checked_twin_stays_ready(self):
        text = text_of(two_column(True))
        self.assertIn('Biopsy: ☒ Cold snare polypectomy of the 6 mm sigmoid polyp was performed.', text)
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'), ('45380', 'Biopsy')), ('ready', 'ready'))

    def test_ordinary_rows_still_get_their_glyphs(self):
        """Positive controls: a box after a list marker, and a second box whose left neighbour is the first box's
        label, are still tied (round 3 ingest:1)."""
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, '1.')).line(text_line(100, BIOPSY_ROW, 'Biopsy'))
        form.line(text_line(72, SNARE_ROW, '2)')).line(text_line(100, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 84), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(SNARE_ROW, 84), True, tu='Cold snare polypectomy')
        self.assertIn('Interventions:\n1. ☐ Biopsy\n2) ☒ Cold snare polypectomy\n', text_of(form.build()))
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy')).line(text_line(218, BIOPSY_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 200), True, tu='Cold snare polypectomy')
        text = text_of(form.build())
        self.assertIn('Interventions:\n☐ Biopsy ☒ Cold snare polypectomy\n', text)
        self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_bullet_left_of_the_box_is_a_list_marker(self):
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, '-')).line(text_line(100, BIOPSY_ROW, 'Biopsy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 84), False, tu='Biopsy')
        self.assertIn('Interventions:\n- ☐ Biopsy\n', text_of(form.build()))


# --- extraction:1 -- a printed ticked box under an unchecked widget -----------------------------------------------

def printed_ticked_under_off(variant, printed='wingdings'):
    """'☒ Cold snare polypectomy' printed (and '☐ Biopsy'), made fillable with unchecked widgets over both boxes;
    the snare widget's off appearance is ``variant``: 'outline' (the builder's stroked square), 'empty', 'absent'
    or 'opaque' (a white square)."""
    form = Form()
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed)).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                             printed, checked=True))
    form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
    form.checkbox('Check Box2', widget_rect(SNARE_ROW), False, tu='Cold snare polypectomy')
    snare = form.annots[-1]
    if variant in ('empty', 'opaque'):
        content = '' if variant == 'empty' else 'q 1 g 0 0 12 12 re f Q'
        n = form.add(stream(content, '/Type /XObject /Subtype /Form /BBox [0 0 12 12]').decode('latin-1'))
        form.objects[snare] = form.objects[snare].replace(b'/Off 8 0 R', b'/Off %d 0 R' % n)
    elif variant == 'absent':
        form.objects[snare] = form.objects[snare].replace(b' /Off 8 0 R', b'')
    return form.build()


class Extraction1PrintedTickUnderAnUncheckedWidgetTests(unittest.TestCase):
    def test_the_printed_tick_is_never_rewritten_unchecked(self):
        for printed in ('wingdings', 'text font'):  # Zapf Dingbats' checked glyph is the filled square, not a box
            for variant in ('outline', 'empty', 'absent', 'opaque'):
                with self.subTest(printed=printed, variant=variant):
                    result = extracted(printed_ticked_under_off(variant, printed))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    joined = result.text.replace('☐ ', '☐')
                    self.assertIn('Interventions:\n☐Biopsy\n[?]', joined)
                    self.assertNotIn('☐Cold snare', joined)
                    held_unread(self, result.text, 'Cold snare polypectomy')
                    self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')
                    # The unchecked biopsy under its unchecked widget still reads as the box says.
                    self.assertEqual(codes(result.text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_typed_brackets_too(self):
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, '[ ] Biopsy')).line(text_line(72, SNARE_ROW, '[x] Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), False, tu='Cold snare polypectomy')
        result = extracted(form.build())
        self.assertIn('Interventions:\n☐ Biopsy\n[?] Cold snare polypectomy\n', result.text)
        self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_a_widget_beside_a_printed_tick_does_not_untick_it(self):
        """The widget is just left of the printed box (tied to the piece the box starts): the same disagreement."""
        form = Form()
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', checked=True))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW, 51), False, tu='Cold snare polypectomy')
        text = text_of(form.build())
        self.assertIn('Interventions:\n[?] Cold snare polypectomy\n', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_agreeing_states_are_written_as_before(self):
        """Positive controls: a checked widget over a printed tick, and widgets over printed empty boxes."""
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                        checked=True))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', result.text)
        self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                         ('excluded', 'ready'))


# --- extraction:2 -- radio buttons over printed boxes ---------------------------------------------------------------

def radio_row(value, *, layout, name='Biopsy taken', states=('/Yes', '/No')):
    form = Form()
    form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', checked=True))
    if layout == 'one piece':
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken: [ ] Yes [ ] No'))
        yes_x, no_x = 90 + 66.0, 90 + 66.0 + 37.3  # Helvetica 11: 'Biopsy taken: ' and '[ ] Yes '
        kids = [((yes_x - 1, BIOPSY_ROW - 3, yes_x + 11, BIOPSY_ROW + 9), states[0]),
                ((no_x - 1, BIOPSY_ROW - 3, no_x + 11, BIOPSY_ROW + 9), states[1])]
    else:  # Word's Wingdings boxes, each its own piece before its option word
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken:'))
        form.line(f'BT /WD 11 Tf 168 {BIOPSY_ROW} Td <A8> Tj ET').line(text_line(184, BIOPSY_ROW, 'Yes'))
        form.line(f'BT /WD 11 Tf 218 {BIOPSY_ROW} Td <A8> Tj ET').line(text_line(234, BIOPSY_ROW, 'No'))
        kids = [(widget_rect(BIOPSY_ROW, 167), states[0]), (widget_rect(BIOPSY_ROW, 217), states[1])]
    form.group(name, kids, value)
    return form.build()


class Extraction2RadioOverPrintedBoxesTests(unittest.TestCase):
    def test_a_selected_yes_is_never_excluded(self):
        for layout in ('one piece', 'pieces'):
            for name, states in (('Biopsy taken', ('/Yes', '/No')), ('Group1', ('/Choice1', '/Choice2'))):
                with self.subTest(layout=layout, name=name):
                    text = text_of(radio_row(states[0], layout=layout, name=name, states=states))
                    for phrase in ('Biopsy', 'Biopsy taken'):
                        self.assertNotEqual(codes(text, ('45380', phrase))[0], 'excluded', (phrase, text[-200:]))

    def test_known_boxes_are_replaced_by_the_radio_state(self):
        for name, states in (('Biopsy taken', ('/Yes', '/No')), ('Group1', ('/Choice1', '/Choice2'))):
            with self.subTest(name=name):
                yes = text_of(radio_row(states[0], layout='pieces', name=name, states=states))
                self.assertIn('Biopsy taken: ☒ Yes ☐ No', yes)
                self.assertNotIn('☐ ☒', yes)
                no = text_of(radio_row(states[1], layout='pieces', name=name, states=states))
                self.assertIn('Biopsy taken: ☐ Yes ☒ No', no)
                self.assertEqual(codes(no, ('45380', 'Biopsy'))[0], 'excluded')

    def test_boxes_inside_one_piece_are_unread_and_the_page_named(self):
        for value in ('/Yes', '/No'):
            with self.subTest(value=value):
                result = extracted(radio_row(value, layout='one piece'))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn(OVERLAP, result.messages)
                self.assertIn('Biopsy taken: [?] Yes [?] No', result.text)
                held_unread(self, result.text, 'Biopsy taken')


# --- extraction:6, contract:1 (c) -- other marks over a printed box -------------------------------------------------

def mark_over_snare(kind):
    """'☐ Biopsy' / '☐ Cold snare polypectomy' (Word's Wingdings boxes) with a mark over the snare's box."""
    form = Form()
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
    rect = (70, SNARE_ROW - 4, 85, SNARE_ROW + 11)
    r = ' '.join(map(str, rect))
    tick = 'q 0 0 1 RG 1.5 w 2 7 m 6 3 l 13 13 l S Q'
    bbox = '/Type /XObject /Subtype /Form /BBox [0 0 15 15]'
    if kind == 'ink':
        ap = form.add(stream(tick, bbox).decode('latin-1'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Ink /Rect [{r}] /F 4 /InkList [[72 603 76 599 83 609]] '
                                    f'/AP << /N {ap} 0 R >> >>'))
    elif kind == 'ink without an appearance':
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Ink /Rect [{r}] /F 4 /InkList [[72 603 76 599 83 609]] '
                                    '/C [0 0 1] >>'))
    elif kind == 'stamp drawn as a path':
        ap = form.add(stream(tick, bbox).decode('latin-1'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Stamp /Rect [{r}] /F 4 /AP << /N {ap} 0 R >> >>'))
    elif kind == 'hidden ink':
        ap = form.add(stream(tick, bbox).decode('latin-1'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Ink /Rect [{r}] /F 2 /InkList [[72 603 76 599 83 609]] '
                                    f'/AP << /N {ap} 0 R >> >>'))
    else:  # FreeText showing ``kind``: Zapf Dingbats for the ballot marks, WinAnsi Helvetica otherwise
        zapf = {'✗': '7', '✘': '8'}.get(kind)
        font, shown = ('/ZaDb 6 0 R', zapf) if zapf else ('/Helv 4 0 R', kind.encode('cp1252').decode('latin-1'))
        name = font.split(' ')[0]
        ap = form.add(stream(f'BT {name} 12 Tf 1 2 Td ({esc(shown)}) Tj ET', f'{bbox} /Resources << /Font << {name} '
                             f'{font.split(" ", 1)[1]} >> >>').decode('latin-1'))
        written = '<FEFF' + kind.encode('utf-16-be').hex().upper() + '>'
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /FreeText /Rect [{r}] /F 4 /Contents {written} '
                                    f'/DA ({name} 12 Tf 0 g) /AP << /N {ap} 0 R >> >>'))
    return form.build()


class Extraction6OtherMarksOverAPrintedBoxTests(unittest.TestCase):
    def test_an_unrecognised_mark_leaves_the_box_unread(self):
        for kind in ('ink', 'ink without an appearance', 'stamp drawn as a path', '✗', '✘', '×', 'XX'):
            with self.subTest(kind=kind):
                result = extracted(mark_over_snare(kind))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn(UNREAD_NOTE, result.messages)
                self.assertIn('Interventions:\n☐ Biopsy\n[?] Cold snare polypectomy', result.text)
                held_unread(self, result.text, 'Cold snare polypectomy')
                self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_recognised_marks_still_check_the_box(self):
        for kind in ('X', '✓'):
            with self.subTest(kind=kind):
                form = Form()
                form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
                form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), kind)
                text = text_of(form.build())
                self.assertIn('☒ Cold snare polypectomy', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_a_mark_away_from_the_boxes_or_hidden_changes_nothing(self):
        form = Form()
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.annots.append(form.add('<< /Type /Annot /Subtype /Ink /Rect [300 590 330 615] /F 4 /InkList '
                                    '[[302 600 310 594 328 612]] >>'))
        result = extracted(form.build())
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertIn('☐ Cold snare polypectomy', result.text)
        hidden = extracted(mark_over_snare('hidden ink'))
        self.assertEqual(hidden.status, 'ok', hidden.messages)
        self.assertIn('☐ Cold snare polypectomy', hidden.text)


# --- extraction:7, contract:1 (a, b) -- a printed box whose position cannot be read under a widget -----------------

def wrapped_checklist(biopsy, snare, *, tooltips=False):
    """Word's Wingdings checklist on a page drawn through a form XObject, made fillable over the printed boxes."""
    form = Form(wrap=True)
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
    form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), biopsy, tu='Biopsy' if tooltips else None)
    form.checkbox('Check Box2', widget_rect(SNARE_ROW), snare, tu='Cold snare polypectomy' if tooltips else None)
    return form.build()


def boxes_inside_their_lines(biopsy, snare, *, tooltips=False):
    form = Form()
    form.line(text_line(72, BIOPSY_ROW, '1. [ ] Biopsy')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy [ ]'))
    form.checkbox('Check Box1', (80.2, BIOPSY_ROW - 3, 92.2, BIOPSY_ROW + 9), biopsy, tu='Biopsy' if tooltips else None)
    form.checkbox('Check Box2', (213.0, SNARE_ROW - 3, 225.0, SNARE_ROW + 9), snare,
                  tu='Cold snare polypectomy' if tooltips else None)
    return form.build()


class Extraction7UnreadablePositionTests(unittest.TestCase):
    def test_a_wrapped_page_with_generic_names_is_held(self):
        for biopsy, snare in ((True, True), (False, True), (False, False)):
            for tooltips in (False, True):
                with self.subTest(biopsy=biopsy, snare=snare, tooltips=tooltips):
                    result = extracted(wrapped_checklist(biopsy, snare, tooltips=tooltips))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(OVERLAP, result.messages)
                    self.assertIn('Interventions:\n[?] Biopsy\n[?] Cold snare polypectomy\n', result.text)
                    for phrase in ('Biopsy', 'Cold snare polypectomy'):
                        held_unread(self, result.text, phrase)
                    self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                     ('held', 'held'))

    def test_boxes_inside_their_lines_are_held(self):
        for tooltips in (False, True):
            with self.subTest(tooltips=tooltips):
                result = extracted(boxes_inside_their_lines(True, True, tooltips=tooltips))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn('Interventions:\n1. [?] Biopsy\nCold snare polypectomy [?]\n', result.text)
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                 ('held', 'held'))

    def test_the_flat_page_still_reads_the_widgets(self):
        """Positive control: the same checklist drawn on the page itself."""
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True)
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', result.text)

    def test_a_printed_box_with_no_widget_over_it_is_read_as_printed(self):
        """A wrapped page whose only widget is a text field elsewhere: its printed boxes are not touched."""
        form = Form(wrap=True)
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy'))
        form.textfield('Comments', (300, 400, 500, 420), 'Tolerated well.')
        result = extracted(form.build())
        self.assertIn('Interventions:\n☐ Biopsy\n', result.text)


# --- extraction:10 -- a widget laid over a printed box's ink -------------------------------------------------------

def ink_aligned(biopsy, snare, *, printed='text font', shift=1.26, tooltips=False):
    """Widgets exactly over each printed box's visible square, which starts 0.09 em right of the glyph origin."""
    form = Form()
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed)).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                             printed))
    form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 72 + shift), biopsy, tu='Biopsy' if tooltips else None)
    form.checkbox('Check Box2', widget_rect(SNARE_ROW, 72 + shift), snare, tu='Cold snare polypectomy' if tooltips else None)
    return form.build()


def one_run_checklist(biopsy, snare, shift):
    """Box and label in one text run, one piece of page text (Chrome's '☐ Cold snare polypectomy' text node): a text
    font whose ToUnicode gives ☐ for '!' and every other code its own character; widgets over the boxes' ink."""
    form = Form()
    form.objects[24] = to_unicode([(0x21, '\u2610'), (0x22, '\u2612')]
                                  + [(code, chr(code)) for code in range(0x20, 0x7F) if code not in (0x21, 0x22)])
    for y, label in ((BIOPSY_ROW, 'Biopsy'), (SNARE_ROW, 'Cold snare polypectomy')):
        form.line(f'BT /MG 11 Tf 72 {y} Td (! {esc(label)}) Tj ET')
    form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 72 + shift), biopsy)
    form.checkbox('Check Box2', widget_rect(SNARE_ROW, 72 + shift), snare)
    return form.build()


class Extraction10WidgetOverTheBoxInkTests(unittest.TestCase):
    def test_one_glyph_the_widgets(self):
        for shift in (1.26, 1.5, 2.5):
            for printed in ('text font', 'wingdings'):
                with self.subTest(shift=shift, printed=printed):
                    text = text_of(ink_aligned(False, True, printed=printed, shift=shift, tooltips=True))
                    self.assertNotIn('☐ ☒', text)
                    self.assertNotIn('☐ ☐', text)
                    self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', text)
                    self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                     ('excluded', 'ready'))

    def test_checked_boxes_in_one_run_are_never_excluded(self):
        for shift in (1.26, 2.5):
            with self.subTest(shift=shift):
                text = text_of(one_run_checklist(True, True, shift))
                self.assertIn('Interventions:\n☒ Biopsy\n☒ Cold snare polypectomy\n', text)
                self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                 ('ready', 'ready'))

    def test_a_widget_well_right_of_the_box_is_not_over_it(self):
        """A widget starting half its width right of the printed box's origin is not over it: it is tied beside the
        label as before, and the two boxes the row then shows disagree (held). (Round 6 extraction:3: the checked
        widget still overlaps the printed box's drawn width, which its state denies, so the printed box is written
        unread rather than as the stale '☐'; the reading stays held.)"""
        form = Form()
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', 'text font'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW, 72 + 6.5), True, tu='Cold snare polypectomy')
        text = text_of(form.build())
        self.assertIn('Interventions:\n[?] ☒ Cold snare polypectomy\n', text)
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'held')
        form = Form()  # unchecked: a printed box left of the box is not a label, and both boxes agree
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', 'text font'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW, 72 + 6.5), False, tu='Cold snare polypectomy')
        text = text_of(form.build())
        self.assertIn('Interventions:\n☐ ☐ Cold snare polypectomy\n', text)
        # Round 4d BOXES3 (contract-r4d section 4, strict check-box rows): two boxes for one entry cannot be paired one
        # to one, so the item is held (it was excluded), never negated by a guess
        self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'held')


# --- contract:1 -- the repair's own inputs with Acrobat's default names ---------------------------------------------

class Contract1GenericNamesTests(unittest.TestCase):
    def test_the_unreadable_position_case_without_tooltips(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [ ]')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy [ ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False)
        form.checkbox('Check Box2', (214, SNARE_ROW - 3, 226, SNARE_ROW + 9), True)
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(OVERLAP, result.messages)
        self.assertIn('Biopsy [?]\nCold snare polypectomy [?]\n', result.text)
        self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_two_widgets_over_one_printed_box(self):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True)
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 72), False)
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn('Interventions:\n[?] Biopsy\n', result.text)
        held_unread(self, result.text, 'Biopsy')

    def test_an_unmarked_unchecked_box_is_still_excluded(self):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                        checked=True))
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                         ('excluded', 'ready'))


class CompetingReadingsTests(unittest.TestCase):
    """Two readings of one printed box that disagree, or more than can be read, leave it unread."""

    def test_a_typed_x_with_an_unknown_position_box_on_its_row(self):
        form = Form()
        form.line(f'BT /WD 11 Tf 72 {SNARE_ROW} Td <A8> Tj /F1 11 Tf 18 0 Td (Cold snare polypectomy [ ]) Tj ET')
        form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), 'X')
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn('[?] Cold snare polypectomy [?]', result.text)

    def test_a_typed_x_over_a_box_whose_widget_is_unchecked(self):
        form = Form()
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW), False, tu='Cold snare polypectomy')
        form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), 'X')
        result = extracted(form.build())
        self.assertIn(UNREAD_NOTE, result.messages)
        self.assertIn('Interventions:\n[?] Cold snare polypectomy\n', result.text)
        form = Form()  # agreeing: a checked widget and a typed X
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), 'X')
        self.assertIn('Interventions:\n☒ Cold snare polypectomy\n', text_of(form.build()))

    def test_more_rows_than_can_be_read_under_one_widget(self):
        """Printed boxes on 40 distinct baselines within one widget's height: none is read as decided."""
        form = Form()
        for n in range(40):
            form.line(f'BT /WD 11 Tf 72 {SNARE_ROW + n * 0.05:.2f} Td <A8> Tj ET')
        form.line(text_line(90, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(OVERLAP, result.messages)
        self.assertNotIn('☐', result.text)
        self.assertNotIn('☒', result.text)
        self.assertEqual(result.text.count(UNREAD), 40)

    def test_the_printed_state_follows_the_box_vocabulary(self):
        import re
        printed_on = pdf_module._ING_printed_on
        for found, want in (('☐', False), ('☒', True), ('[ ]', False), ('[]', False), ('[x]', True), ('[X]', True)):
            with self.subTest(found=found):
                self.assertEqual(printed_on(pdf_module.PRINTED_BOX.fullmatch(found)), want)
        vocabulary = re.compile(r'(?P<off>\[ *\]|\(_\))|(?P<on>\[[xX*]\]|\(x\))')
        for found, want in (('[  ]', False), ('(_)', False), ('[*]', True), ('(x)', True)):
            with self.subTest(vocabulary=found):
                self.assertEqual(printed_on(vocabulary.fullmatch(found)), want)


# --- the seam with sections: an option row written with the unread mark ends at its line -------------------------------

def option_row_then_item():
    """'Biopsy taken: [ ] Yes [ ] No' in one piece with a radio group over the brackets (Yes selected), then a line
    naming a performed service with no clause of its own."""
    form = Form()
    form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken: [ ] Yes [ ] No'))
    form.line(text_line(90, SNARE_ROW, 'Cold snare polypectomy of the sigmoid polyp'))
    yes_x, no_x = 90 + 69.09, 90 + 69.09 + 34.24  # Helvetica 11: 'Biopsy taken: ' and '[ ] Yes '
    form.group('Biopsy taken', [((yes_x - 1, BIOPSY_ROW - 3, yes_x + 11, BIOPSY_ROW + 9), '/Yes'),
                                ((no_x - 1, BIOPSY_ROW - 3, no_x + 11, BIOPSY_ROW + 9), '/No')], '/Yes')
    return form.build()


@unittest.skipUnless(__import__('studio.gi.sections', fromlist=['_OPTION_ROW'])._OPTION_ROW.search(
    'Biopsy taken: [?] Yes [?] No'), 'needs sections._OPTION_ROW to read the unread mark (BOXES, round 4 structure:14)')
class UnreadOptionRowSeamTests(unittest.TestCase):
    """Runs once the shared box vocabulary reaches sections' option-row guard: until then a row extraction writes
    '[?] Yes [?] No' is read as a sentence cut at its line break, and its 'No' negates the next line's service."""

    def test_an_unread_option_row_never_negates_the_next_line(self):
        text = text_of(option_row_then_item())
        self.assertIn('Biopsy taken: [?] Yes [?] No\nCold snare polypectomy of the sigmoid polyp', text)
        held_unread(self, text, 'Biopsy taken')
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')


# --- the unread mark is the one routing holds ------------------------------------------------------------------------

class UnreadMarkContractTests(unittest.TestCase):
    def test_extraction_writes_what_routing_reads_as_unread(self):
        self.assertEqual(pdf_module._ING_UNREAD_BOX, UNREAD)
        self.assertIsNotNone(detect._BOX_UNREAD.fullmatch(UNREAD))
        self.assertIsNone(detect._BOX.fullmatch(UNREAD))


# --- extraction:8 -- a crowded row ------------------------------------------------------------------------------------

def crowded_row(count, *, rows=1, printed=False):
    """``count`` unchecked check boxes, each 8 pt box just left of its own one-letter label, on ``rows`` baselines of a
    wide page; with ``printed``, a typed '[ ]' under each box (a checklist made fillable)."""
    per_row = -(-count // rows)
    width, height = 30 + per_row * 20, 100 + rows * 20
    ops, annots, objects = [], [], {}
    number = 100
    for n in range(count):
        row, column = divmod(n, per_row)
        y = height - 60 - row * 20
        x = 20 + column * 20
        label = '[ ] A' if printed else 'A'
        ops.append(f'BT /F1 8 Tf {x + (0 if printed else 10)} {y} Td ({label}) Tj ET')
        number += 1
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Btn /T (B{n}) /V /Off /AS /Off '
                           f'/Rect [{x} {y - 2} {x + 8} {y + 6}] /F 4 /P 3 0 R /AP << /N << /Yes 7 0 R /Off 7 0 R >> >> >>'
                           ).encode()
        annots.append(number)
    objects.update({1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>',
                    2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                    3: (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 4 0 R >> '
                        f'>> /Contents 5 0 R /Annots [{" ".join(f"{a} 0 R" for a in annots)}] >>').encode(),
                    4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
                    5: stream('\n'.join(ops)),
                    7: stream('', '/Type /XObject /Subtype /Form /BBox [0 0 8 8]'),
                    10: (f'<< /Fields [{" ".join(f"{a} 0 R" for a in annots)}] /NeedAppearances false >>').encode()})
    from tests.test_repairs_ingest_pdf import serialise
    return serialise(objects)


def placement_inputs(data):
    """The page's layer and annotations, read as extraction reads them, so that placement alone can be timed."""
    import io

    import pypdf

    from studio.ingest.pdfannots import read_annotations
    from studio.ingest.pdfcontent import OptionalContent, analyse_page, resolved
    reader = pypdf.PdfReader(io.BytesIO(data))
    root = resolved(reader.trailer['/Root'])
    page, optional = reader.pages[0], OptionalContent(root)
    content = analyse_page(page, reader, optional)
    return pdf_module._layer_text(page, content), read_annotations(page, optional, resolved(root.get('/AcroForm')))


def marked_row(count, *, wide):
    """``count`` typed '[ ]' boxes on one row, and ``count`` ink marks: each over its own box, or each across the
    whole row."""
    width = 40 + count * 20
    ops = [f'BT /F1 8 Tf {20 + n * 20} 700 Td ([ ] A) Tj ET' for n in range(count)]
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
               5: stream('\n'.join(ops))}
    annots = []
    for n in range(count):
        x0, x1 = (10, width - 10) if wide else (18 + n * 20, 30 + n * 20)
        objects[100 + n] = (f'<< /Type /Annot /Subtype /Ink /Rect [{x0} 690 {x1} 712] /F 4 '
                            f'/InkList [[{x0} 700 {x1} 701]] >>').encode()
        annots.append(f'{100 + n} 0 R')
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} 792] /Resources << /Font << /F1 4 0 R >> >> '
                  f'/Contents 5 0 R /Annots [{" ".join(annots)}] >>').encode()
    from tests.test_repairs_ingest_pdf import serialise
    return serialise(objects)


class Extraction8CrowdedRowCostTests(unittest.TestCase):
    def timed(self, data):
        """The best of two extractions, each after a collection (a timing, not the collector's or a busy host's)."""
        import gc
        best = result = None
        for _ in range(2):
            gc.collect()
            started = time.monotonic()
            result = in_process(data)
            elapsed = time.monotonic() - started
            best = elapsed if best is None else min(best, elapsed)
        return best, result

    def test_marks_across_a_crowded_row_cost_what_marks_over_one_box_cost(self):
        """Every mark over every box: past the candidates one mark may examine, the page's boxes are all unread
        without examining each mark's whole window."""
        import gc
        timings = []
        for wide in (True, False):
            layer, annotations = placement_inputs(marked_row(4000, wide=wide))
            best = None
            for _ in range(3):  # the best of three, each after a collection
                gc.collect()
                started = time.monotonic()
                text, _, overlap, named = pdf_module._placed_boxes(layer, annotations)
                elapsed = time.monotonic() - started
                best = elapsed if best is None else min(best, elapsed)
            timings.append(best)
            self.assertEqual(text.count(UNREAD), 4000)
            # Ink marks, not form check boxes: named as unread boxes either way (round 5 extraction:7)
            self.assertEqual((overlap, named), (False, True))
        self.assertLess(timings[0], 3 * timings[1] + 0.1, timings)

    def test_placement_on_a_crowded_row_is_near_linear(self):
        """Placement alone, without the parsing around it: one crowded row against the same boxes on 100 rows."""
        import gc
        for printed in (False, True):
            with self.subTest(printed=printed):
                timings = []
                for rows in (1, 100):
                    layer, annotations = placement_inputs(crowded_row(6000, rows=rows, printed=printed))
                    best = None
                    for _ in range(3):  # the best of three, each after a collection: a timing, not the collector's
                        gc.collect()
                        started = time.monotonic()
                        text = pdf_module._placed_boxes(layer, annotations)[0]
                        elapsed = time.monotonic() - started
                        best = elapsed if best is None else min(best, elapsed)
                    timings.append(best)
                    self.assertEqual(text.count('☐'), 6000)
                self.assertLess(timings[0], 3 * timings[1] + 0.1, timings)

    def test_one_crowded_row_costs_about_what_many_rows_cost(self):
        for printed in (False, True):
            with self.subTest(printed=printed):
                crowded, one = self.timed(crowded_row(4000, printed=printed))
                spread, many = self.timed(crowded_row(4000, rows=100, printed=printed))
                self.assertEqual(one.status, many.status)
                self.assertEqual((one.text.count('☐'), one.text.count('[?]')), (4000, 0))
                self.assertEqual((many.text.count('☐'), many.text.count('[?]')), (4000, 0))
                self.assertLess(crowded, 2 * spread + 0.5, (crowded, spread))


if __name__ == '__main__':
    unittest.main()
