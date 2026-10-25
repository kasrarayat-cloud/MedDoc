"""Regressions for refutation round 5, INGEST lens, PDF annotations over printed boxes and text (repair round 4c).

- extraction:3 (critical): a text or choice field showing 'X' (or any value) over a printed box left the printed empty
  box as written, so a visibly ticked service was excluded. A displayed field that shows something over a printed box
  now leaves it unread ('[?]', named, partial), like any other mark that is not a check;
- extraction:6 (medium, over-hold): on a page drawn through a form XObject, any annotation anywhere on it made every
  printed box unread. The printed boxes inside the form are now placed on the page, so a mark leaves unread only the
  boxes it may cover; a box whose place cannot be read is still unread under any mark.

Each PDF is synthetic and built here from raw PDF syntax with the round-3 builders, extracted with the sandboxed
extract_document, routed for real and assessed by the real engine.
"""
import unittest

from tests.test_repairs_ingest_pdf import esc, serialise, stream
from tests.test_repairs_r3_forms_pdf import (BIOPSY_ROW, FIELDS_NOTE, FONTS, SNARE_ROW, Form, boxed_line, codes,
                                             extracted, text_line, widget_rect)
from tests.test_repairs_r4_ingest import UNREAD, UNREAD_NOTE, held_unread

ANNOTATION_NOTE = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
                   'annotation text.')
TICK = 'q 0 0 1 RG 1.5 w 2 7 m 6 3 l 13 13 l S Q'


class Placed(Form):
    """A page drawn through a form XObject, placed by ``place`` (the page's content) with the form's own /Matrix."""

    def __init__(self, place='q 1 0 0 1 0 0 cm /Fm0 Do Q', matrix=None):
        super().__init__(wrap=True)
        self.place, self.matrix = place, matrix

    def build(self) -> bytes:
        objects = dict(self.objects)
        objects[1] = b'<< /Type /Catalog /Pages 2 0 R ' + (b'/AcroForm 10 0 R ' if self.fields else b'') + b'>>'
        objects[2] = b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'
        matrix = f' /Matrix [{self.matrix}]' if self.matrix else ''
        objects[9] = stream('\n'.join(self.ops), f'/Type /XObject /Subtype /Form /BBox [0 0 612 792]{matrix} '
                            f'/Resources << {FONTS} >>')
        objects[5] = stream(self.place)
        annots = f'/Annots [{" ".join(f"{n} 0 R" for n in self.annots)}]' if self.annots else ''
        objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << {FONTS} /XObject << /Fm0 9 0 '
                      f'R >> >> /Contents 5 0 R {annots} >>').encode()
        if self.fields:
            objects[10] = (f'<< /Fields [{" ".join(f"{n} 0 R" for n in self.fields)}] /NeedAppearances false '
                           '/DR << /Font << /Helv 4 0 R /ZaDb 6 0 R >> >> /DA (/Helv 0 Tf 0 g) >>').encode()
        return serialise(objects)


def checklist(*, wrap=True, matrix=None, place='q 1 0 0 1 0 0 cm /Fm0 Do Q'):
    """Word's Wingdings checklist '☐ Biopsy' / '☒ Cold snare polypectomy', no form fields, on a page drawn through a
    form XObject (``place`` draws it; ``matrix`` is the form's own /Matrix), or on the page itself."""
    form = Placed(place, matrix) if wrap else Form()
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                    checked=True))
    return form


def annotate(form, kind, rect=None):
    """One displayed annotation of ``kind``: a sticky note, a highlight, a typed note, an ink signature or an ink tick."""
    if kind == 'sticky':
        rect = rect or (565, 760, 585, 780)
        popup = form.number + 2
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Text /Rect [{" ".join(map(str, rect))}] /F 4 '
                                    f'/Contents (Reviewed by the endoscopist.) /Popup {popup} 0 R >>'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Popup /Rect [400 650 600 760] /F 4 '
                                    f'/Parent {form.number} 0 R >>'))
    elif kind == 'highlight':
        x0, y0, x1, y1 = rect or (58, 736, 420, 752)
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Highlight /Rect [{x0} {y0} {x1} {y1}] /F 4 /C [1 1 0] '
                                    f'/QuadPoints [{x0} {y1} {x1} {y1} {x0} {y0} {x1} {y0}] >>'))
    elif kind == 'freetext':
        rect = rect or (400, 40, 560, 60)
        ap = form.add(stream('BT /Helv 10 Tf 2 4 Td (Reviewed) Tj ET', '/Type /XObject /Subtype /Form /BBox [0 0 160 20] '
                             '/Resources << /Font << /Helv 4 0 R >> >>').decode('latin-1'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /FreeText /Rect [{" ".join(map(str, rect))}] /F 4 '
                                    f'/Contents (Reviewed) /DA (/Helv 10 Tf 0 g) /AP << /N {ap} 0 R >> >>'))
    elif kind in ('ink', 'tick'):
        rect = rect or ((300, 80, 420, 110) if kind == 'ink' else (70, BIOPSY_ROW - 4, 85, BIOPSY_ROW + 11))
        ap = form.add(stream(TICK, f'/Type /XObject /Subtype /Form /BBox [0 0 {rect[2] - rect[0]} {rect[3] - rect[1]}]'
                             ).decode('latin-1'))
        form.annots.append(form.add(f'<< /Type /Annot /Subtype /Ink /Rect [{" ".join(map(str, rect))}] /F 4 '
                                    f'/InkList [[{rect[0] + 2} {rect[1] + 7} {rect[0] + 6} {rect[1] + 3} '
                                    f'{rect[0] + 13} {rect[1] + 13}]] /AP << /N {ap} 0 R >> >>'))
    return form


# --- extraction:6 -- a page drawn through a form XObject -------------------------------------------------------------

class Extraction6WrappedPageTests(unittest.TestCase):
    def test_a_distant_annotation_changes_nothing(self):
        for kind in ('sticky', 'highlight', 'freetext', 'ink'):
            with self.subTest(kind=kind):
                result = extracted(annotate(checklist(), kind).build())
                self.assertNotIn(UNREAD_NOTE, result.messages)
                self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy', result.text)
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                 ('excluded', 'ready'))

    def test_a_tick_over_a_box_leaves_that_box_unread(self):
        """The mutant the verifier tried (unread marks never reach boxes inside the form) read this '☐ Biopsy'."""
        result = extracted(annotate(checklist(), 'tick').build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(UNREAD_NOTE, result.messages)
        self.assertIn('Interventions:\n[?] Biopsy\n☒ Cold snare polypectomy', result.text)
        held_unread(self, result.text, 'Biopsy')
        self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_a_form_placed_with_a_matrix(self):
        """The form drawn scaled and moved (its /Matrix and the cm before its Do): its boxes are placed where they land."""
        for matrix, place, at in (('0.5 0 0 0.5 0 0', 'q 1 0 0 1 100 300 cm /Fm0 Do Q', (100 + 35, 300 + 0.5 * BIOPSY_ROW)),
                                  (None, 'q 0.8 0 0 0.8 20 40 cm /Fm0 Do Q', (20 + 0.8 * 72, 40 + 0.8 * BIOPSY_ROW))):
            with self.subTest(matrix=matrix, place=place):
                x, y = at
                far = extracted(annotate(checklist(matrix=matrix, place=place), 'sticky').build())
                self.assertNotIn(UNREAD_NOTE, far.messages)
                self.assertIn('☐ Biopsy\n☒ Cold snare polypectomy', far.text)
                near = extracted(annotate(checklist(matrix=matrix, place=place), 'tick',
                                          (x - 3, y - 4, x + 8, y + 7)).build())
                self.assertIn(UNREAD_NOTE, near.messages)
                self.assertIn('[?] Biopsy\n☒ Cold snare polypectomy', near.text)

    def test_a_box_whose_place_cannot_be_read_is_still_held(self):
        """The form drawn rotated: its text is not upright, so where its boxes land is not read, and any mark on the
        page leaves them unread (the round-4b hold, kept where placement fails)."""
        result = extracted(annotate(checklist(place='q 0 1 -1 0 792 0 cm /Fm0 Do Q'), 'sticky').build())
        self.assertNotIn('☐ Biopsy', result.text)
        self.assertNotIn('☒ Cold snare', result.text)

    def test_a_form_drawn_inside_a_form(self):
        """The checklist in a form (its /Matrix moves it 50, -30) drawn by a form (a cm moves it 10, 20) drawn by the page
        (a cm moves it 40, 60): its boxes land at x + 100, y + 50."""
        class Nested(Placed):
            def build(self):
                objects = dict(self.objects)
                objects[1] = b'<< /Type /Catalog /Pages 2 0 R >>'
                objects[2] = b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'
                objects[11] = stream('\n'.join(self.ops), f'/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Matrix '
                                     f'[1 0 0 1 50 -30] /Resources << {FONTS} >>')
                objects[9] = stream('q 1 0 0 1 10 20 cm /Fm1 Do Q', f'/Type /XObject /Subtype /Form /BBox [0 0 612 792] '
                                    f'/Resources << {FONTS} /XObject << /Fm1 11 0 R >> >>')
                objects[5] = stream('q 1 0 0 1 40 60 cm /Fm0 Do Q')
                annots = f'/Annots [{" ".join(f"{n} 0 R" for n in self.annots)}]' if self.annots else ''
                objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << {FONTS} /XObject << '
                              f'/Fm0 9 0 R >> >> /Contents 5 0 R {annots} >>').encode()
                return serialise(objects)

        def nested(rect):
            form = Nested()
            form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                            checked=True))
            return annotate(form, 'tick', rect).build()

        near = extracted(nested((169, BIOPSY_ROW + 46, 184, BIOPSY_ROW + 61)))
        self.assertIn('[?] Biopsy\n☒ Cold snare polypectomy', near.text)
        far = extracted(nested((70, BIOPSY_ROW - 4, 85, BIOPSY_ROW + 11)))  # where the box would be unmoved
        self.assertIn('☐ Biopsy\n☒ Cold snare polypectomy', far.text)

    def test_a_box_inside_a_line_of_the_form(self):
        """'1. [ ] Biopsy' in one piece of the form's text: the box's own place is not known, only its line's, so a tick
        right of where the line starts leaves it unread; a tick left of the line changes nothing."""
        form = Placed()
        form.line(text_line(72, BIOPSY_ROW, '1. [ ] Biopsy')).line(text_line(72, SNARE_ROW, '2. [ ] Cold snare polypectomy'))
        annotate(form, 'tick', (84, BIOPSY_ROW - 4, 99, BIOPSY_ROW + 11))
        result = extracted(form.build())
        self.assertIn('1. [?] Biopsy\n2. [ ] Cold snare polypectomy', result.text)
        form = Placed()
        form.line(text_line(72, BIOPSY_ROW, '1. [ ] Biopsy'))
        annotate(form, 'tick', (30, BIOPSY_ROW - 4, 45, BIOPSY_ROW + 11))
        self.assertIn('1. [ ] Biopsy', extracted(form.build()).text)

    def test_text_pending_when_a_form_is_drawn_is_not_placed_by_the_form(self):
        """A 'Do' inside a text object (tolerated, though invalid): pypdf writes the text pending at the Do while the form
        is entered, so that text's place is not read through the form (it would land 300 pt away): a tick over it on
        the page leaves it unread, as before."""
        form = Placed(f'BT /F1 11 Tf 72 {BIOPSY_ROW} Td ({esc("[ ] Biopsy")}) Tj /Fm0 Do ET', '1 0 0 1 300 0')
        form.line('BT /F1 11 Tf 100 100 Td (Signed) Tj ET')  # the form draws the note's lines, 300 pt right
        annotate(form, 'tick', (70, BIOPSY_ROW - 4, 85, BIOPSY_ROW + 11))
        result = extracted(form.build())
        self.assertNotIn('[ ] Biopsy', result.text)
        self.assertIn('Biopsy', result.text)

    def test_the_direct_page_is_unchanged(self):
        result = extracted(annotate(checklist(wrap=False), 'sticky').build())
        self.assertIn('☐ Biopsy\n☒ Cold snare polypectomy', result.text)
        result = extracted(annotate(checklist(wrap=False), 'tick').build())
        self.assertIn('[?] Biopsy\n☒ Cold snare polypectomy', result.text)


# --- extraction:3 -- a text or choice field over a printed box -------------------------------------------------------

def field_over_snare(printed, value='X', *, kind='text', appearance=True, tooltip=None, need_appearances=False,
                     wrap=False, rect=None, glyph=None, font='Helv'):
    """'[  ] Biopsy' / '[  ] Cold snare polypectomy' (or Wingdings or Zapf boxes) with a text field (or a combo box)
    showing ``value`` over the snare's box."""
    form = Form(wrap=wrap)
    if printed in ('[  ]', '[ ]'):
        form.line(text_line(72, BIOPSY_ROW, f'{printed} Biopsy')).line(text_line(72, SNARE_ROW,
                                                                                 f'{printed} Cold snare polypectomy'))
    else:
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed)).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                                 printed))
    rect = rect or (71.0, SNARE_ROW - 3, 85.5, SNARE_ROW + 11)
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    shown = glyph if glyph is not None else esc(value or '')
    written = None if value is None else (f'({esc(value)})' if value.isascii() else
                                          '<FEFF' + value.encode('utf-16-be').hex().upper() + '>')
    parts = [f'/Type /Annot /Subtype /Widget /T (Text1) /Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R',
             f'/DA (/{font} 10 Tf 0 g)', f'/V {written}' if written else '',
             f'/TU ({esc(tooltip)})' if tooltip else '']
    parts.append('/FT /Tx' if kind == 'text' else f'/FT /Ch /Ff {1 << 17} /Opt [( ) {written or "()"}]')
    if appearance:
        ap = form.add(stream(f'/Tx BMC q BT /{font} 10 Tf 0 g 3.6 3.2 Td ({shown}) Tj ET Q EMC',
                             f'/Type /XObject /Subtype /Form /BBox [0 0 {width} {height}] /Resources << /Font << '
                             '/Helv 4 0 R /ZaDb 6 0 R >> >>').decode('latin-1'))
        parts.append(f'/AP << /N {ap} 0 R >>')
    form.annots.append(form.add('<< ' + ' '.join(p for p in parts if p) + ' >>'))
    form.fields.append(form.annots[-1])
    data = form.build()
    if need_appearances:
        data = data.replace(b'/NeedAppearances false', b'/NeedAppearances true ')
    return data


class Extraction3FieldOverAPrintedBoxTests(unittest.TestCase):
    def test_a_field_showing_x_over_a_printed_box_leaves_it_unread(self):
        cases = {'two-space brackets': dict(printed='[  ]'), 'one-space brackets': dict(printed='[ ]'),
                 'Wingdings box': dict(printed='wingdings'), 'Zapf box': dict(printed='zapf'),
                 'named': dict(printed='[  ]', tooltip='Cold snare polypectomy'), 'lower-case x': dict(printed='[  ]',
                                                                                                    value='x'),
                 'a check mark': dict(printed='[  ]', value='✔', glyph='4', font='ZaDb'),
                 'a combo box': dict(printed='[  ]', kind='choice'),
                 'drawn from its value': dict(printed='[  ]', appearance=False, need_appearances=True)}
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = extracted(field_over_snare(**kwargs))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn(UNREAD_NOTE, result.messages)
                snare = [line.replace(f'{UNREAD}Cold', f'{UNREAD} Cold') for line in result.text.split('\n')
                         if line.endswith('Cold snare polypectomy')]
                self.assertEqual(snare, [f'{UNREAD} Cold snare polypectomy'], result.text)
                held_unread(self, result.text, 'Cold snare polypectomy')
                self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_an_empty_field_and_a_field_elsewhere_change_nothing(self):
        for label, kwargs in (('no value', dict(value=None)), ('an empty value', dict(value='')),
                              ('elsewhere', dict(rect=(300, 400, 500, 420), value='Tolerated well.'))):
            with self.subTest(label):
                result = extracted(field_over_snare('[  ]', **kwargs))
                self.assertNotIn(UNREAD_NOTE, result.messages)
                self.assertIn('[  ] Cold snare polypectomy', result.text)
                self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_marks_that_check_are_as_before(self):
        """Controls: a FreeText 'X' and a checked check box over the printed box check it."""
        form = Form()
        form.line(text_line(72, SNARE_ROW, '[  ] Cold snare polypectomy'))
        form.freetext((71.0, SNARE_ROW - 3, 85.5, SNARE_ROW + 11), 'X')
        self.assertIn('☒ Cold snare polypectomy', extracted(form.build()).text)
        form = Form()
        form.line(text_line(72, SNARE_ROW, '[  ] Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW), True)
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertIn('☒ Cold snare polypectomy', result.text)

    def test_on_a_wrapped_page_the_field_leaves_only_its_box_unread(self):
        result = extracted(field_over_snare('wingdings', wrap=True))
        self.assertIn(UNREAD_NOTE, result.messages)
        self.assertIn('☐ Biopsy\n[?] Cold snare polypectomy', result.text)
        result = extracted(field_over_snare('wingdings', wrap=True, rect=(300, 400, 500, 420), value='Tolerated well.'))
        self.assertNotIn(UNREAD_NOTE, result.messages)
        self.assertIn('☐ Biopsy\n☐ Cold snare polypectomy', result.text)


# --- extraction:7 -- which message names a page whose boxes are unread ----------------------------------------------

OVERLAP = ('Page 1 has a form check box over a printed box whose position could not be read, so the box may show a '
           'different state than the text; check the original.')


def framed_checklist(rows):
    """A flat printed checklist of ``rows`` rows ('☒ Cold snare polypectomy' first), no form field, and one unfilled
    review frame (/Square, a red border, no /IC) drawn around it."""
    form = Form()
    form.line(boxed_line(72, 640, 'Cold snare polypectomy', checked=True))
    for n in range(1, rows):
        form.line(boxed_line(72, 640 - 13 * n, f'Checklist item {n}'))
    bottom = 640 - 13 * rows
    form.annots.append(form.add(f'<< /Type /Annot /Subtype /Square /Rect [60 {bottom} 400 655] /F 4 /C [1 0 0] '
                                '/BS << /W 1.5 >> /Contents (Reviewed) >>'))
    return form.build()


class Extraction7NoFormCheckBoxNoOverlapMessageTests(unittest.TestCase):
    def test_a_frame_around_a_long_flat_checklist_is_named_as_unread(self):
        """Past the rows one mark may read, every box is unread (the declared hold); the message names unread boxes,
        never a form check box the page does not have."""
        for rows in (36, 10):
            with self.subTest(rows=rows):
                result = extracted(framed_checklist(rows))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertNotIn(OVERLAP, result.messages)
                self.assertIn(UNREAD_NOTE, result.messages)
                self.assertIn('[?] Cold snare polypectomy', result.text)
                self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_a_typed_x_across_two_boxes_is_named_as_unread(self):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.freetext((70, SNARE_ROW - 4, 84, BIOPSY_ROW + 10), 'X')
        result = extracted(form.build())
        self.assertNotIn(OVERLAP, result.messages)
        self.assertIn(UNREAD_NOTE, result.messages)
        self.assertIn('[?] Biopsy\n[?] Cold snare polypectomy', result.text)

    def test_a_form_check_box_still_names_the_overlap(self):
        """Controls: a check box over a box whose position cannot be read, and more rows than one check box may read."""
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [ ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False)
        self.assertIn(OVERLAP, extracted(form.build()).messages)
        form = Form()
        for n in range(40):
            form.line(f'BT /WD 11 Tf 72 {SNARE_ROW + n * 0.05:.2f} Td <A8> Tj ET')
        form.line(text_line(90, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        result = extracted(form.build())
        self.assertIn(OVERLAP, result.messages)
        self.assertNotIn(UNREAD_NOTE, result.messages)


# --- extraction:4 -- a field's background, painted by the viewer ---------------------------------------------------

COVERED = ('Page 1 has strike-out, redaction or cover-up marks added as PDF annotations; the text under them was read '
           'as written, so check it against the original.')


def field_report(*, appearance=None, need=True, background='[1]', value='', translucent=False, kind='/Tx',
                 rect=None):
    """The round-4 report with one field over 'A cold forceps biopsy was taken from the polyp.': ``appearance`` None
    (none stored), 'empty' (one that draws nothing) or 'white' (one that paints its box white); NeedAppearances
    ``need`` (None: absent); /MK /BG ``background`` (None: no /MK)."""
    from tests.test_repairs_ingest_pdf import HELVETICA
    from tests.test_repairs_r4_ingest_covers import RECT, REPORT
    rect = rect or RECT
    width, height = round(rect[2] - rect[0], 2), round(rect[3] - rect[1], 2)
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in REPORT)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 8 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 5: stream(content)}
    parts = [f'/Type /Annot /Subtype /Widget /FT {kind} /T (Comments) /Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R',
             '/DA (/Helv 10 Tf 0 g)', f'/V ({esc(value)})' if value else '',
             f'/MK << /BG {background} >>' if background is not None else '', '/CA 0.5' if translucent else '']
    if kind == '/Ch':
        parts.append(f'/Ff {1 << 17} /Opt [() ({esc(value)})]')
    if appearance:
        drawn = '/Tx BMC EMC' if appearance == 'empty' else f'q 1 g 0 0 {width} {height} re f Q /Tx BMC EMC'
        objects[7] = stream(drawn, f'/Type /XObject /Subtype /Form /BBox [0 0 {width} {height}] /Resources << /Font << '
                            '/Helv 4 0 R >> >>')
        parts.append('/AP << /N 7 0 R >>')
    objects[6] = ('<< ' + ' '.join(p for p in parts if p) + ' >>').encode()
    flag = '' if need is None else f'/NeedAppearances {"true" if need else "false"} '
    objects[8] = f'<< /Fields [6 0 R] {flag}/DR << /Font << /Helv 4 0 R >> >> >>'.encode()
    objects[3] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R /Annots [6 0 R] >>')
    return serialise(objects)


class Extraction4FieldBackgroundTests(unittest.TestCase):
    def test_a_background_the_viewer_paints_over_text_is_named(self):
        cases = {'empty, regenerated': dict(), 'filled, regenerated': dict(value='Biopsy deferred.'),
                 'an RGB white': dict(background='[1 1 1]'), 'an appearance that draws nothing': dict(appearance='empty'),
                 'no appearance, NeedAppearances absent': dict(need=None),
                 'no appearance, NeedAppearances false': dict(need=False),
                 'a combo box': dict(kind='/Ch', value='Deferred')}
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = extracted(field_report(**kwargs))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn(COVERED, result.messages)
                self.assertIn('A cold forceps biopsy was taken from the polyp.', result.text)

    def test_no_background_or_none_over_text_is_not_named(self):
        cases = {'no background': dict(background=None), 'a transparent background': dict(background='[]'),
                 'translucent': dict(translucent=True), 'away from the text': dict(rect=(70, 300, 308.94, 315)),
                 'a stored appearance that draws nothing, not regenerated': dict(appearance='empty', need=False)}
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = extracted(field_report(**kwargs))
                self.assertNotIn(COVERED, result.messages)
                self.assertEqual(result.status, 'ok', result.messages)

    def test_a_stored_white_appearance_is_named_as_before(self):
        result = extracted(field_report(appearance='white', need=False, background=None))
        self.assertIn(COVERED, result.messages)


# --- extraction:10 -- white fields on fill-in lines ------------------------------------------------------------------

def fill_in_form(line='_' * 30, *, geometry='low', one_run=False, under=None, regenerated=False, graze=0.0):
    """'Indication:', 'Bowel preparation:' and 'Extent reached:', each followed by a fill-in ``line`` (or ``under``, a
    printed word, as the positive control), with a filled text field whose appearance paints a white box laid on each
    line: its bottom 3 pt under the baseline ('low', hiding the line's ink), 0.2 pt above it ('above'), or 1.2 pt under
    it ('on'). ``one_run``: the label and its line in one text-showing operator; ``regenerated``: no appearance,
    /NeedAppearances true, /MK /BG [1]."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from tests.test_repairs_ingest_pdf import HELVETICA
    rows = [('Indication:', 'Screening', 660), ('Bowel preparation:', 'Good', 640), ('Extent reached:', 'Cecum', 620)]
    content = [f'BT /F1 11 Tf 72 {y} Td ({esc(t)}) Tj ET' for y, t in (
        (740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (720, 'Colonoscopy procedure report'),
        (700, 'Date of service: 2026-10-21'), (590, 'Findings: A 6 mm sigmoid polyp was removed by cold snare polypectomy.'))]
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 4 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               5: HELVETICA}
    annots, number = [], 10
    for label, value, y in rows:
        printed = under or line
        x = round(72 + stringWidth(label + (' ' if one_run else ''), 'Helvetica', 11) + (0 if one_run else 4), 2)
        if one_run:
            content.append(f'BT /F1 11 Tf 72 {y} Td ({esc(label + " " + printed)}) Tj ET')
        else:
            content.append(f'BT /F1 11 Tf 72 {y} Td ({esc(label)}) Tj ET')
            content.append(f'BT /F1 11 Tf {x} {y} Td ({esc(printed)}) Tj ET')
        w = round(stringWidth(printed, 'Helvetica', 11), 2)
        bottom = {'low': y - 3, 'above': round(y + 0.2, 2), 'on': round(y - 1.2, 2)}[geometry]
        rect = (round(x - graze, 2), bottom, round(x + w, 2), bottom + 14)
        fw, fh = round(rect[2] - rect[0], 2), 14
        parts = [f'/Type /Annot /Subtype /Widget /FT /Tx /T ({esc(label.rstrip(":"))}) /V ({esc(value)}) /MK << /BG [1] >>',
                 f'/Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R /DA (/Helv 10 Tf 0 g)']
        if not regenerated:
            objects[number + 1] = stream(f'q 1 g 0 0 {fw} {fh} re f Q /Tx BMC q BT /Helv 10 Tf 0 g 2 3.5 Td ({esc(value)}) Tj '
                                         f'ET Q EMC', f'/Type /XObject /Subtype /Form /BBox [0 0 {fw} {fh}] /Resources '
                                         '<< /Font << /Helv 5 0 R >> >>')
            parts.append(f'/AP << /N {number + 1} 0 R >>')
        objects[number] = ('<< ' + ' '.join(parts) + ' >>').encode()
        annots.append(number)
        number += 2
    refs = ' '.join(f'{n} 0 R' for n in annots)
    objects[4] = (f'<< /Fields [{refs}] /NeedAppearances {"true" if regenerated else "false"} '
                  '/DR << /Font << /Helv 5 0 R >> >> >>').encode()
    objects[6] = stream('\n'.join(content))
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> '
                  f'/Contents 6 0 R /Annots [{refs}] >>').encode()
    return serialise(objects)


class Extraction10FillInLinesTests(unittest.TestCase):
    def test_a_white_field_on_a_fill_in_line_hides_no_text(self):
        cases = {'on the line': dict(geometry='on'), 'above the line': dict(geometry='above'),
                 'hiding the line': dict(geometry='low'), 'label and line in one run': dict(one_run=True),
                 'one run, hiding the line': dict(one_run=True, geometry='low'), 'dot leaders': dict(line='.' * 40),
                 'a dashed rule': dict(line='-' * 34), 'drawn by the viewer': dict(regenerated=True),
                 'grazing the label (less than its letters must show)': dict(one_run=True, graze=4.0)}
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = extracted(fill_in_form(**kwargs))
                self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))

    def test_a_decimal_point_drawn_alone_and_covered_is_named(self):
        """'1', '.' and '5' drawn by three operators, a white box over the point only: what shows reads '15', so the
        point is text, not a rule (a dot is a fill-in character only among three or more)."""
        from tests.test_repairs_ingest_pdf import HELVETICA
        content = '\n'.join([f'BT /F1 11 Tf 72 {y} Td ({esc(t)}) Tj ET' for y, t in (
            (740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (720, 'Date of service: 2026-10-21'),
            (700, 'Findings: A polyp was seen.'))] + ['BT /F1 11 Tf 72 680 Td (Size: ) Tj ET',
                                                     'BT /F1 11 Tf 102.6 680 Td (1) Tj ET', 'BT /F1 11 Tf 108.7 680 Td (.) Tj ET',
                                                     'BT /F1 11 Tf 111.8 680 Td (5 cm) Tj ET'])
        objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   4: HELVETICA, 5: stream(content), 6: b'<< /Type /Annot /Subtype /Square /Rect [107.7 676 112.8 692] /F 4 '
                   b'/IC [1 1 1] /C [1 1 1] >>'}
        objects[3] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                      b'/Contents 5 0 R /Annots [6 0 R] >>')
        result = extracted(serialise(objects))
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(COVERED, result.messages)

    def test_a_white_field_over_words_is_still_named(self):
        cases = {'a word under the field': dict(under='Biopsy taken'),
                 'a line ending in a word': dict(line='_' * 24 + ' mm'),
                 'a word between rules': dict(line='___ Biopsy ___'),
                 'one period': dict(line='1.5'), 'drawn by the viewer': dict(under='Biopsy taken', regenerated=True)}
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = extracted(fill_in_form(**kwargs))
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertIn(COVERED, result.messages)


if __name__ == '__main__':
    unittest.main()
