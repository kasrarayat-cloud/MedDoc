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


if __name__ == '__main__':
    unittest.main()
