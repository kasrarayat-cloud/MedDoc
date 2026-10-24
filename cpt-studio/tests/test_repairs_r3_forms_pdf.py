"""Regressions for refutation round 3, FORMS lens, PDF side: what a form's check boxes show reaches routing.

- ingest:0 / contract:2: a displayed check-box widget over a printed box replaces the printed glyph with its own
  state (a FreeText 'X' over a printed box checks it); a printed box under a widget whose position cannot be read
  makes the page partial;
- ingest:1 / contract:0: an unchecked box in an ordinary layout (two on a row, the label left of the box, numbered
  rows, the page drawn through a form XObject) never leaves its item ready: the glyph is placed where it can be
  tied, and otherwise the form-field line negates the printed label it names or holds the page;
- ingest:2: a yes/no pair of check boxes is written like a radio group, '<label>: <option>';
- ingest:3: a radio 'No' denies; its option glyphs are written when each widget can be tied to its option word;
- contract:4: a blank line inside a multi-line field value never ends the form-field block;
- ingest:14: the radio /Opt lookup is linear.

Each PDF is synthetic and built here from raw PDF syntax (or reportlab), extracted with the sandboxed
extract_document, routed for real for the document's own date and assessed by the real engine.
"""
import io
import time
import unittest

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from studio.ingest import Limits, extract_document
from tests.test_repairs_ingest_pdf import HELVETICA, esc, serialise, stream
from tests.test_repairs_status_r2_routing import read, run_engine
from tests.test_repairs_r3_forms_routing import not_silent, outcome

PDF = 'application/pdf'
FIELDS_NOTE = ('Page 1 has PDF form fields; their values were read and added after the page text, labelled as form '
               'fields.')
ANNOTATION_NOTE = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
                   'annotation text.')
NOTE = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (72, 720, 'Date of service: 2026-10-21'),
        (72, 700, 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.'),
        (72, 680, 'Findings: A 6 mm sigmoid polyp was seen.'), (72, 660, 'Interventions:')]
WIDTHS = '/FirstChar 32 /LastChar 255 /Widths [' + ' '.join(['1000'] * 224) + ']'
SYMBOL_DESCRIPTOR = (b'<< /Type /FontDescriptor /FontName /Wingdings-Regular /Flags 4 /FontBBox [0 -200 1000 900] '
                     b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>')


def to_unicode(pairs) -> bytes:
    entries = '\n'.join(f'<{code:02X}> <{text.encode("utf-16-be").hex().upper()}>' for code, text in pairs)
    return stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry '
                  '(Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic-UCS def\n/CMapType 2 def\n'
                  f'1 begincodespacerange\n<00> <FF>\nendcodespacerange\n{len(pairs)} beginbfchar\n{entries}\n'
                  'endbfchar\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')


# Fonts: /F1 Helvetica; /WD Wingdings as Word saves it (code A8 an empty box, FE a checked one); /ZA Zapf Dingbats
# ('o' an empty box); /MG a text font whose ToUnicode gives U+2610 / U+2612 (a Word content-control box).
FONT_OBJECTS = {4: HELVETICA, 6: b'<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>',
                20: (f'<< /Type /Font /Subtype /TrueType /BaseFont /Wingdings-Regular {WIDTHS} /FontDescriptor 21 0 R '
                     '/ToUnicode 22 0 R >>').encode(),
                21: SYMBOL_DESCRIPTOR, 22: to_unicode([(0xA8, '\uf0a8'), (0xFE, '\uf0fe')]),
                23: (f'<< /Type /Font /Subtype /TrueType /BaseFont /MS-Gothic {WIDTHS} /ToUnicode 24 0 R >>').encode(),
                24: to_unicode([(0x21, '☐'), (0x22, '☒')])}
FONTS = '/Font << /F1 4 0 R /ZA 6 0 R /WD 20 0 R /MG 23 0 R >>'
PRINTED = {'wingdings': ('WD', 'A8', 'FE'), 'zapf': ('ZA', '6F', '6E'), 'text font': ('MG', '21', '22')}


def text_line(x, y, text, font='F1', size=11) -> str:
    return f'BT /{font} {size} Tf {x} {y} Td ({esc(text)}) Tj ET'


def boxed_line(x, y, label, printed='wingdings', checked=False, gap=18) -> str:
    """A Word checklist row: a printed box glyph, then its label after a tab, in one text object."""
    font, off, on = PRINTED[printed]
    return f'BT /{font} 11 Tf {x} {y} Td <{on if checked else off}> Tj /F1 11 Tf {gap} 0 Td ({esc(label)}) Tj ET'


class Form:
    """One page: content operators, widgets and annotations, serialised as raw PDF syntax."""

    def __init__(self, lines=None, wrap=False):
        self.ops = [text_line(x, y, t) for x, y, t in (NOTE if lines is None else lines)]
        self.wrap = wrap
        self.objects = dict(FONT_OBJECTS)
        # check mark appearance (Zapf '4'), and an empty square for off
        self.objects[7] = stream('q BT /ZaDb 10 Tf 0 g 1.5 2 Td (4) Tj ET Q', '/Type /XObject /Subtype /Form '
                                 '/BBox [0 0 12 12] /Resources << /Font << /ZaDb 6 0 R >> >>')
        self.objects[8] = stream('q 0.5 w 0.5 0.5 11 11 re S Q', '/Type /XObject /Subtype /Form /BBox [0 0 12 12]')
        self.annots, self.fields, self.number = [], [], 100

    def add(self, body: str) -> int:
        self.number += 1
        self.objects[self.number] = body.encode('latin-1') if isinstance(body, str) else body
        return self.number

    def line(self, op: str) -> 'Form':
        self.ops.append(op)
        return self

    def checkbox(self, name, rect, checked, tu=None, on='/Yes', flags=4) -> 'Form':
        tu = f'/TU ({esc(tu)})' if tu else ''
        state = on if checked else '/Off'
        n = self.add(f'<< /Type /Annot /Subtype /Widget /FT /Btn /T ({esc(name)}) {tu} /V {state} /AS {state} '
                     f'/Rect [{" ".join(map(str, rect))}] /F {flags} /P 3 0 R /MK << /CA (4) >> /DA (/ZaDb 0 Tf 0 g) '
                     f'/AP << /N << {on} 7 0 R /Off 8 0 R >> >> >>')
        self.annots.append(n)
        self.fields.append(n)
        return self

    def group(self, name, kids, value, *, radio=True, opt=None, tu=None) -> 'Form':
        """A radio group (or, radio=False, a check-box field with several kids): kids are (rect, on-state)."""
        parent = self.number + 1
        self.number += 1
        refs = []
        for rect, on in kids:
            state = on if on == value else '/Off'
            refs.append(self.add(f'<< /Type /Annot /Subtype /Widget /Parent {parent} 0 R /AS {state} '
                                 f'/Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R /MK << /CA (l) >> '
                                 f'/AP << /N << {on} 7 0 R /Off 8 0 R >> >> >>'))
        flags = '/Ff 49152' if radio else ''
        options = f'/Opt [{" ".join(f"({esc(o)})" for o in opt)}]' if opt else ''
        tu = f'/TU ({esc(tu)})' if tu else ''
        self.objects[parent] = (f'<< /FT /Btn {flags} /T ({esc(name)}) {tu} /V {value} {options} '
                                f'/Kids [{" ".join(f"{r} 0 R" for r in refs)}] >>').encode('latin-1')
        self.annots.extend(refs)
        self.fields.append(parent)
        return self

    def textfield(self, name, rect, value) -> 'Form':
        n = self.add(f'<< /Type /Annot /Subtype /Widget /FT /Tx /Ff 4096 /T ({esc(name)}) /V ({esc(value)}) '
                     f'/Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R /DA (/Helv 10 Tf 0 g) >>')
        self.annots.append(n)
        self.fields.append(n)
        return self

    def freetext(self, rect, contents) -> 'Form':
        """A typed note; a check mark is typed in Zapf Dingbats ('3' ✓, '4' ✔), as viewers draw one."""
        zapf = {'\u2713': '3', '\u2714': '4'}.get(contents)
        font, shown = ('/ZaDb 6 0 R', zapf) if zapf else ('/Helv 4 0 R', contents)
        name = '/ZaDb' if zapf else '/Helv'
        appearance = self.add(stream(f'BT {name} 12 Tf 1 2 Td ({esc(shown)}) Tj ET', '/Type /XObject /Subtype '
                                     f'/Form /BBox [0 0 {rect[2] - rect[0]} {rect[3] - rect[1]}] /Resources << /Font << '
                                     f'{name} {font.split(" ", 1)[1]} >> >>').decode('latin-1'))
        written = '<FEFF' + contents.encode('utf-16-be').hex().upper() + '>' if zapf else f'({esc(contents)})'
        self.annots.append(self.add(f'<< /Type /Annot /Subtype /FreeText /Rect [{" ".join(map(str, rect))}] /F 4 '
                                    f'/Contents {written} /DA ({name} 12 Tf 0 g) /AP << /N {appearance} 0 R >> >>'))
        return self

    def build(self) -> bytes:
        content = '\n'.join(self.ops)
        objects = dict(self.objects)
        objects[1] = (b'<< /Type /Catalog /Pages 2 0 R ' + (b'/AcroForm 10 0 R ' if self.fields else b'') + b'>>')
        objects[2] = b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'
        annots = f'/Annots [{" ".join(f"{n} 0 R" for n in self.annots)}]' if self.annots else ''
        if self.wrap:  # the page drawn through a form XObject, as stamping and overlay tools write it
            objects[9] = stream(content, f'/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << {FONTS} >>')
            objects[5] = stream('q 1 0 0 1 0 0 cm /Fm0 Do Q')
            resources = f'<< {FONTS} /XObject << /Fm0 9 0 R >> >>'
        else:
            objects[5] = stream(content)
            resources = f'<< {FONTS} >>'
        objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources {resources} /Contents 5 0 R '
                      f'{annots} >>').encode()
        if self.fields:
            objects[10] = (f'<< /Fields [{" ".join(f"{n} 0 R" for n in self.fields)}] /NeedAppearances false '
                           '/DR << /Font << /Helv 4 0 R /ZaDb 6 0 R >> >> /DA (/Helv 0 Tf 0 g) >>').encode()
        return serialise(objects)


def extracted(data: bytes):
    return extract_document(data, 'synthetic.pdf', PDF, ocr=None)


def text_of(data: bytes) -> str:
    result = extracted(data)
    if result.status not in ('ok', 'partial') or not result.text:
        raise AssertionError((result.status, result.messages))
    return result.text


def codes(text: str, *picks) -> tuple:
    """The engine's outcome for each (code, phrase[, occurrence]) pick, each assessed on its own."""
    found = []
    for pick in picks:
        proposals, _ = run_engine(text, [pick])
        found.append(outcome(proposals[pick[0]]))
    return tuple(found)


BIOPSY_ROW, SNARE_ROW = 620, 600


def widget_rect(y, x=71, size=12):
    return (x, y - 3, x + size, y - 3 + size)


# --- ingest:0 / contract:2 ----------------------------------------------------------------------------------------

class Ingest0PrintedBoxUnderAWidgetTests(unittest.TestCase):
    """A checklist printed with boxes and made fillable (Acrobat 'Prepare Form'): the widget's state replaces the
    printed glyph under it; a FreeText 'X' over a printed box checks it."""

    def form(self, printed, biopsy, snare, *, tooltips=True, shift=0, flags=4):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed)).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                                 printed))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 71 - shift), biopsy, tu='Biopsy' if tooltips else None,
                      flags=flags)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW, 71 - shift), snare,
                      tu='Cold snare polypectomy' if tooltips else None, flags=flags)
        return form.build()

    def test_the_widget_decides_the_printed_box(self):
        for printed in PRINTED:
            for biopsy, snare in ((False, True), (True, False), (True, True), (False, False)):
                with self.subTest(printed=printed, biopsy=biopsy, snare=snare):
                    result = extracted(self.form(printed, biopsy, snare))
                    self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
                    glyph = {True: '☒', False: '☐'}
                    joined = result.text.replace('☐ ', '☐').replace('☒ ', '☒')  # Zapf glyphs come with no space
                    self.assertIn(f'Interventions:\n{glyph[biopsy]}Biopsy\n{glyph[snare]}Cold snare polypectomy\n', joined)
                    self.assertNotIn('☒ ☐', result.text)
                    self.assertNotIn('☐ ☒', result.text)
                    want = {True: 'ready', False: 'excluded'}
                    self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                     (want[biopsy], want[snare]))

    def test_a_shifted_widget_still_replaces_the_glyph(self):
        """Over the printed box (shifts 4 and 8) or just left of it (20): one glyph, the widget's."""
        for shift in (4, 8, 20):
            with self.subTest(shift=shift):
                text = text_of(self.form('wingdings', False, True, shift=shift))
                self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', text)

    def test_generic_field_names(self):
        text = text_of(self.form('wingdings', True, True, tooltips=False))
        self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')), ('ready', 'ready'))
        text = text_of(self.form('wingdings', False, True, tooltips=False))
        self.assertIn('☐ Biopsy\n☒ Cold snare polypectomy', text)
        self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_hidden_widget_leaves_the_printed_box(self):
        text = text_of(self.form('wingdings', True, True, flags=2))
        self.assertIn('☐ Biopsy\n☐ Cold snare polypectomy', text)

    def test_a_typed_x_over_a_printed_box_checks_it(self):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), 'X')
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION_NOTE,)))
        self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', result.text)
        self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                         ('excluded', 'ready'))
        for mark in ('x', '✓', '✔'):
            with self.subTest(mark=mark):
                form = Form()
                form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
                form.freetext((70, SNARE_ROW - 4, 84, SNARE_ROW + 10), mark)
                self.assertIn('☒ Cold snare polypectomy', text_of(form.build()))
        form = Form()  # a note typed beside the box is not a mark over it
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.freetext((300, SNARE_ROW - 4, 360, SNARE_ROW + 10), 'X')
        self.assertIn('☐ Cold snare polypectomy', text_of(form.build()))

    def test_bracket_boxes_under_widgets(self):
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, '[ ] Biopsy')).line(text_line(72, SNARE_ROW, '[ ] Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        text = text_of(form.build())
        self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', text)

    def test_two_boxes_over_one_printed_box_are_reported(self):
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 72), False, tu='Biopsy sampling')
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        # Two candidates for one printed box: unread, never the stale printed glyph (round 4 contract:1).
        self.assertIn('Interventions:\n[?] Biopsy\n', result.text)

    def test_a_box_under_a_widget_whose_position_cannot_be_read_is_reported(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [ ]')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy [ ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False, tu='Biopsy')
        form.checkbox('Check Box2', (214, SNARE_ROW - 3, 226, SNARE_ROW + 9), True, tu='Cold snare polypectomy')
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn('Page 1 has a form check box over a printed box whose position could not be read, so the box '
                      'may show a different state than the text; check the original.', result.messages)
        self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        self.assertNotEqual(codes(result.text, ('45380', 'Biopsy'))[0], 'ready')
        form = Form()  # a box at a known place under the widget, and another at an unknown place on its row
        form.line(f'BT /WD 11 Tf 72 {BIOPSY_ROW} Td <A8> Tj /F1 11 Tf 18 0 Td (Biopsy [ ]) Tj ET')
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True, tu='Biopsy')
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn('[?] Biopsy [?]', result.text)  # both candidates unread (round 4 contract:1, extraction:7)


# --- ingest:1 / contract:0 ----------------------------------------------------------------------------------------

def layout_form(name, biopsy, snare, *, tooltips):
    """The verifier's ordinary layouts: an unchecked biopsy box and a checked snare box."""
    tu = (lambda label: label) if tooltips else (lambda label: None)
    form = Form(wrap=name == 'xobject')
    if name in ('row', 'xobject-row'):
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy')).line(text_line(218, BIOPSY_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), biopsy, tu=tu('Biopsy'))
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 200), snare, tu=tu('Cold snare polypectomy'))
    elif name == 'label-left':
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy:')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy:'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 260), biopsy, tu=tu('Biopsy'))
        form.checkbox('Check Box2', widget_rect(SNARE_ROW, 260), snare, tu=tu('Cold snare polypectomy'))
    elif name == 'numbered':
        form.line(text_line(72, BIOPSY_ROW, '1.')).line(text_line(100, BIOPSY_ROW, 'Biopsy'))
        form.line(text_line(72, SNARE_ROW, '2.')).line(text_line(100, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 84), biopsy, tu=tu('Biopsy'))
        form.checkbox('Check Box2', widget_rect(SNARE_ROW, 84), snare, tu=tu('Cold snare polypectomy'))
    elif name == 'xobject':
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), biopsy, tu=tu('Biopsy'))
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), snare, tu=tu('Cold snare polypectomy'))
    return form.build()


LAYOUTS = ('row', 'label-left', 'numbered', 'xobject')


class Ingest1OrdinaryLayoutTests(unittest.TestCase):
    """An unchecked box in an ordinary layout never leaves its item ready; the checked twins stay ready."""

    def test_an_unchecked_biopsy_is_never_ready(self):
        for name in LAYOUTS:
            for tooltips in (True, False):
                with self.subTest(layout=name, tooltips=tooltips):
                    text = text_of(layout_form(name, False, True, tooltips=tooltips))
                    printed = text.index('Biopsy')
                    self.assertLess(printed, text.index('[PDF form fields'))
                    block_line = 'Biopsy: not checked' if tooltips else 'Check Box1: not checked'
                    self.assertIn(block_line, text)
                    for phrase in ('Biopsy', block_line):
                        self.assertNotEqual(codes(text, ('45380', phrase))[0], 'ready', phrase)
                    self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_the_checked_twins_stay_ready(self):
        for name in LAYOUTS:
            for tooltips in (True, False):
                with self.subTest(layout=name, tooltips=tooltips):
                    text = text_of(layout_form(name, True, True, tooltips=tooltips))
                    self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                     ('ready', 'ready'))

    def test_glyphs_are_placed_where_each_box_can_be_tied(self):
        text = text_of(layout_form('row', False, True, tooltips=True))
        self.assertIn('Interventions:\n☐ Biopsy ☒ Cold snare polypectomy\n', text)
        self.assertEqual(read(text, 'Biopsy')[0], 'negated')
        text = text_of(layout_form('numbered', False, True, tooltips=True))
        self.assertIn('Interventions:\n1. ☐ Biopsy\n2. ☒ Cold snare polypectomy\n', text)
        self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')), ('excluded', 'ready'))

    def test_two_boxes_beside_one_label_write_nothing(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW, 60), True, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 74), False, tu='Biopsy sampling')
        self.assertIn('Interventions:\nBiopsy\n', text_of(form.build()))

    def test_a_named_field_negates_its_printed_label(self):
        for name in ('label-left', 'xobject'):
            with self.subTest(layout=name):
                text = text_of(layout_form(name, False, True, tooltips=True))
                self.assertEqual(read(text, 'Biopsy')[0], 'negated')
                self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                 ('excluded', 'ready'))

    def test_a_generic_field_name_holds_the_page(self):
        text = text_of(layout_form('label-left', False, True, tooltips=False))
        status, cues = read(text, 'Biopsy')
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(not_silent(cues), cues)
        self.assertIn('Check Box1: not checked', cues[0])
        self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')), ('held', 'held'))

    def test_a_reportlab_form(self):
        for checked in (False, True):
            with self.subTest(checked=checked):
                buffer = io.BytesIO()
                canvas = Canvas(buffer, pagesize=letter, invariant=1)
                canvas.setFont('Helvetica', 11)
                for x, y, line in NOTE + [(90, 620, 'Biopsy:'), (90, 600, 'Cold snare polypectomy:')]:
                    canvas.drawString(x, y, line)
                canvas.acroForm.checkbox(name='Biopsy', x=260, y=617, size=12, checked=checked, buttonStyle='check')
                canvas.acroForm.checkbox(name='Cold snare polypectomy', x=260, y=597, size=12, checked=True,
                                         buttonStyle='check')
                canvas.showPage()
                canvas.save()
                text = text_of(buffer.getvalue())
                self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'ready' if checked else 'excluded')
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')


# --- ingest:2 -- a yes/no pair of check boxes ------------------------------------------------------------------

def yes_no_form(value, *, radio, opt=None, tu=None, split=True, states=('/Yes', '/No')):
    form = Form()
    form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', checked=True))
    if split:
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken:')).line(text_line(184, BIOPSY_ROW, 'Yes'))
        form.line(text_line(234, BIOPSY_ROW, 'No'))
    else:
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken:        Yes         No'))
    form.group('Biopsy taken', [(widget_rect(BIOPSY_ROW, 168), states[0]), (widget_rect(BIOPSY_ROW, 218), states[1])],
               value, radio=radio, opt=opt, tu=tu)
    return form.build()


class Ingest2YesNoCheckBoxPairTests(unittest.TestCase):
    def test_the_option_marked_is_written(self):
        for value, line in (('/No', 'Biopsy taken: No'), ('/Yes', 'Biopsy taken: Yes'),
                            ('/Off', 'Biopsy taken: no option selected')):
            with self.subTest(value=value):
                result = extracted(yes_no_form(value, radio=False))
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertTrue(result.text.endswith('[PDF form fields on page 1]\n' + line), result.text[-80:])

    def test_options_listed_in_opt(self):
        text = text_of(yes_no_form('/1', radio=False, opt=['Yes', 'No'], states=('/0', '/1')))
        self.assertTrue(text.endswith('\nBiopsy taken: No'), text[-60:])

    def test_a_no_is_never_ready_and_a_yes_is(self):
        for split in (True, False):
            with self.subTest(split=split):
                no = text_of(yes_no_form('/No', radio=False, split=split))
                for phrase in ('Biopsy', 'Biopsy taken: No'):
                    self.assertNotEqual(codes(no, ('45380', phrase))[0], 'ready', phrase)
                yes = text_of(yes_no_form('/Yes', radio=False, split=split))
                self.assertEqual(codes(yes, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')), ('ready', 'ready'))

    def test_a_single_check_box_with_opt_is_a_set_of_options(self):
        for checked, line in ((True, 'Biopsy: Biopsy done'), (False, 'Biopsy: no option selected')):
            with self.subTest(checked=checked):
                form = Form()
                form.line(text_line(90, BIOPSY_ROW, 'Biopsy'))
                form.group('Biopsy', [(widget_rect(BIOPSY_ROW), '/0')], '/0' if checked else '/Off', radio=False,
                           opt=['Biopsy done'])
                self.assertTrue(text_of(form.build()).endswith('\n' + line))

    def test_a_single_check_box_keeps_checked_and_not_checked(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy'))
        form.checkbox('Biopsy', widget_rect(BIOPSY_ROW), False)
        self.assertTrue(text_of(form.build()).endswith('\nBiopsy: not checked'))


# --- ingest:3 -- a radio 'No' ---------------------------------------------------------------------------------------

class Ingest3RadioNoTests(unittest.TestCase):
    def test_a_selected_no_is_never_ready(self):
        for split in (True, False):
            for opt in (None, ['Yes', 'No']):
                with self.subTest(split=split, opt=opt):
                    states = ('/0', '/1') if opt else ('/Yes', '/No')
                    text = text_of(yes_no_form(states[1], radio=True, opt=opt, split=split, states=states))
                    self.assertTrue(text.endswith('\nBiopsy taken: No'), text[-60:])
                    for phrase in ('Biopsy', 'Biopsy taken: No'):
                        self.assertNotEqual(codes(text, ('45380', phrase))[0], 'ready', phrase)

    def test_a_selected_yes_stays_ready(self):
        for split in (True, False):
            with self.subTest(split=split):
                text = text_of(yes_no_form('/Yes', radio=True, split=split))
                self.assertEqual(codes(text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                                 ('ready', 'ready'))

    def test_radio_glyphs_only_before_their_own_option_words(self):
        text = text_of(yes_no_form('/Choice2', radio=True, states=('/Choice1', '/Choice2')))
        self.assertNotIn('☐', text.split('[PDF form fields')[0].replace('☐ Cold', ''))
        self.assertNotIn('☒ Yes', text)
        self.assertNotIn('☒ No', text)

    def test_a_radio_group_is_placed_whole_or_not_at_all(self):
        form = Form()  # on one row: the untied button keeps the row bare as well
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken:')).line(text_line(184, BIOPSY_ROW, 'Yes'))
        form.group('Biopsy taken', [(widget_rect(BIOPSY_ROW, 168), '/Yes'), (widget_rect(BIOPSY_ROW, 300), '/No')], '/No')
        self.assertIn('Biopsy taken: Yes\n', text_of(form.build()))
        form = Form()  # its options on rows of their own, one of them with no word beside its button
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy taken:')).line(text_line(184, BIOPSY_ROW, 'Yes'))
        form.line(text_line(184, SNARE_ROW, 'Not sure'))
        form.group('Biopsy taken', [(widget_rect(BIOPSY_ROW, 168), '/Yes'), (widget_rect(SNARE_ROW, 168), '/No')], '/No')
        text = text_of(form.build())
        self.assertNotIn('☐', text)
        self.assertNotIn('☒', text)

    def test_option_glyphs_where_each_widget_has_its_word(self):
        text = text_of(yes_no_form('/No', radio=True))
        self.assertIn('☐ Yes', text)
        self.assertIn('☒ No', text)
        self.assertNotIn('☒ Yes', text)


# --- contract:4 -- a multi-paragraph field value ------------------------------------------------------------------

class Contract4BlankLineInAFieldValueTests(unittest.TestCase):
    def form(self, value, last):
        form = Form(NOTE[:4] + [(72, 670, 'Comments:'), (72, 660, 'Interventions:')])
        form.textfield('Comments', (150, 664, 560, 680), value)
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy')).line(text_line(90, SNARE_ROW, 'Cold snare polypectomy'))
        form.line(text_line(72, 560, last))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True, tu='Cold snare polypectomy')
        return form.build()

    def test_the_block_runs_to_the_page_separator(self):
        for value in ('Polyp removed en bloc and retrieved.\n\nPatient tolerated the procedure well.',
                      'Polyp removed en bloc and retrieved.\r\r\rPatient tolerated the procedure well.\r',
                      'Polyp removed en bloc and retrieved.\n  \nPatient tolerated the procedure well.'):
            for last in ('Plan: Await pathology.', 'Prior procedures: Colonoscopy in 2019.'):
                with self.subTest(value=value, last=last):
                    text = text_of(self.form(value, last))
                    block = text[text.index('[PDF form fields on page 1]'):]
                    self.assertNotIn('\n\n', block)
                    self.assertIn('Comments: Polyp removed en bloc and retrieved.\nPatient tolerated the procedure '
                                  'well.\nBiopsy: not checked\nCold snare polypectomy: checked', block)
                    status, cues = read(text, 'Cold snare polypectomy: checked')
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy: checked'))[0], 'ready')


# --- contract:3 -- an unchecked status option in a PDF form ---------------------------------------------------------

class Contract3StatusOptionInAFormTests(unittest.TestCase):
    def test_an_unchecked_cancelled_box_is_not_a_cancellation(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                form = Form(NOTE[:2] + [(72, 700, 'Procedure: Colonoscopy with cold snare polypectomy.'),
                                        (90, 680, 'Procedure completed'), (90, 660, 'Procedure cancelled'),
                                        (72, 640, 'Findings: The colonoscope was advanced to the cecum. A 6 mm polyp '
                                                  'was removed with a cold snare.')])
                form.checkbox('Procedure completed', (260, 677, 272, 689), not cancelled)
                form.checkbox('Procedure cancelled', (260, 657, 272, 669), cancelled)
                text = text_of(form.build())
                want = 'excluded' if cancelled else 'ready'
                self.assertEqual(codes(text, ('45385', 'A 6 mm polyp was removed with a cold snare.'))[0], want)


# --- ingest:14 -- the radio /Opt lookup is linear ------------------------------------------------------------------

def big_radio(kids: int, with_opt: bool) -> bytes:
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 5: stream(text_line(72, 720, 'SYNTHETIC radio scale test') + '\n' +
                                       text_line(72, 700, 'Extent reached:')),
               7: stream('', '/Type /XObject /Subtype /Form /BBox [0 0 10 10]')}
    first = 100
    refs = ' '.join(f'{first + n} 0 R' for n in range(kids))
    opt = ('/Opt [' + ' '.join(f'(Option {n})' for n in range(kids)) + ']') if with_opt else ''
    objects[11] = f'<< /FT /Btn /Ff 49152 /T (Extent) /V /On {opt} /Kids [{refs}] >>'.encode()
    for n in range(kids):
        objects[first + n] = (f'<< /Type /Annot /Subtype /Widget /Parent 11 0 R /AS /On /Rect [72 600 82 610] /F 4 '
                              f'/P 3 0 R /AP << /N << /On 7 0 R /Off 7 0 R >> >> >>').encode()
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  f'/Contents 5 0 R /Annots [{refs}] >>').encode()
    objects[10] = b'<< /Fields [11 0 R] /NeedAppearances false >>'
    return serialise(objects)


class Ingest14RadioOptScaleTests(unittest.TestCase):
    def test_a_large_group_with_opt_reads_in_about_the_time_of_one_without(self):
        import pypdf

        from studio.ingest.pdfannots import read_annotations
        from studio.ingest.pdfcontent import OptionalContent, resolved

        def timed(data):
            reader = pypdf.PdfReader(io.BytesIO(data))
            root = resolved(reader.trailer['/Root'])
            page = reader.pages[0]
            for reference in page['/Annots']:  # warm the object cache: only the lookup is timed
                resolved(reference)
            started = time.monotonic()
            found = read_annotations(page, OptionalContent(root), resolved(root['/AcroForm']))
            return time.monotonic() - started, found

        with_opt, found = timed(big_radio(4000, True))
        without, _ = timed(big_radio(4000, False))
        self.assertEqual(found.fields, ['Extent: Option 3999'])
        self.assertLess(with_opt, 4 * without + 0.5, (with_opt, without))


if __name__ == '__main__':
    unittest.main()
