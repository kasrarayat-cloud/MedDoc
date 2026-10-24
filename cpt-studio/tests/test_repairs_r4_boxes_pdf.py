"""Regressions for refutation round 4, BOXES lens, real files: PDF forms and Word documents through the sandboxed
extract_document, then routing for the document's own date and the real validation engine.

- structure:12: a checklist typed with boxes routing reads ('[  ]', '(  )', '( )', '[_]') or drawn with a box glyph
  in a text font, made fillable: the widget over the printed box replaces it with its own state, so a checked
  polypectomy is never excluded;
- release:12 (b): a Word document whose box cell or paragraph is a plain box character (U+25A2, U+2B1C) in a text font:
  the unchecked biopsy is never ready.

Synthetic documents only, built here from raw PDF syntax or WordprocessingML.
"""
import unittest

from tests.support import docgen
from tests.test_repairs_ingest_pdf import stream
from tests.test_repairs_r3_forms_docx import DOCX, docx_result, note_paragraphs, paragraph
from tests.test_repairs_r3_forms_pdf import (BIOPSY_ROW, FONT_OBJECTS, FONTS, NOTE, SNARE_ROW, Form, codes, extracted,
                                             text_line, to_unicode, widget_rect)
from tests.test_repairs_status_r2_routing import read

SNARE = 'Cold snare polypectomy'

# A text font whose ToUnicode gives box characters that no symbol font maps (as a Word document saved as PDF writes a
# box typed in Segoe UI Symbol): code 23 U+25A1, 24 U+25A2, 25 U+2B1C, 26 U+2751.
GLYPH_FONT = (f'<< /Type /Font /Subtype /TrueType /BaseFont /Segoe-UI-Symbol /FirstChar 32 /LastChar 255 /Widths ['
              + ' '.join(['1000'] * 224) + '] /ToUnicode 31 0 R >>').encode()
GLYPHS = {'□': '23', '▢': '24', '⬜': '25', '❑': '26'}


class GlyphForm(Form):
    """The FORMS test page, with a text font whose glyphs are box characters (/SG)."""

    def __init__(self, lines=None):
        super().__init__(lines)
        self.objects[30] = GLYPH_FONT
        self.objects[31] = to_unicode([(int(code, 16), glyph) for glyph, code in GLYPHS.items()])

    def build(self) -> bytes:
        data = super().build()
        return data.replace(FONTS.encode(), FONTS.replace('>>', '/SG 30 0 R >>').encode())


def glyph_line(x, y, glyph, label):
    return f'BT /SG 11 Tf {x} {y} Td <{GLYPHS[glyph]}> Tj /F1 11 Tf 18 0 Td ({label}) Tj ET'


class Structure12TypedBoxUnderAWidgetTests(unittest.TestCase):
    """structure:12 (critical, new in 686d60b11). Routing read '[  ]', '(  )', '( )' and '[_]' as boxes, but the PDF reader
    replaced only '[ ]' and '[x]' with a widget's state, so a checked widget over '[  ] Cold snare polypectomy' left the
    printed empty box and the checked polypectomy was excluded. Both readers now build their boxes from the one
    vocabulary (studio.ingest.symbols)."""
    TYPED = ('[  ]', '(  )', '( )', '[_]', '[\t]', '[ ]')

    def form(self, typed, biopsy, snare, tooltips):
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, f'{typed} Biopsy')).line(text_line(72, SNARE_ROW, f'{typed} {SNARE}'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), biopsy, tu='Biopsy' if tooltips else None)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), snare, tu=SNARE if tooltips else None)
        return form.build()

    def test_the_widget_decides_the_typed_box(self):
        for typed in self.TYPED:
            for tooltips in (False, True):
                for biopsy, snare in ((False, True), (True, True), (False, False)):
                    with self.subTest(typed=typed, tooltips=tooltips, biopsy=biopsy, snare=snare):
                        result = extracted(self.form(typed, biopsy, snare, tooltips))
                        self.assertEqual(result.status, 'ok', result.messages)
                        glyph = {True: '☒', False: '☐'}
                        self.assertIn(f'Interventions:\n{glyph[biopsy]} Biopsy\n{glyph[snare]} {SNARE}\n', result.text)
                        biopsy_code, snare_code = codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE))
                        self.assertEqual(snare_code == 'excluded', not snare, (biopsy_code, snare_code))
                        self.assertNotEqual(biopsy_code, 'ready' if not biopsy else 'excluded')

    def test_a_box_glyph_in_a_text_font(self):
        for glyph in GLYPHS:
            with self.subTest(glyph=hex(ord(glyph))):
                form = GlyphForm()
                form.line(glyph_line(72, BIOPSY_ROW, glyph, 'Biopsy')).line(glyph_line(72, SNARE_ROW, glyph, SNARE))
                form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
                form.checkbox('Check Box2', widget_rect(SNARE_ROW), True, tu=SNARE)
                result = extracted(form.build())
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertIn(f'☐ Biopsy\n☒ {SNARE}', result.text.replace('☐Biopsy', '☐ Biopsy'))
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE)), ('excluded', 'ready'))

    def test_a_trailing_typed_box_whose_position_cannot_be_read_is_reported(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [  ]')).line(text_line(90, SNARE_ROW, f'{SNARE} [  ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False)
        form.checkbox('Check Box2', (214, SNARE_ROW - 3, 226, SNARE_ROW + 9), True)
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertTrue(any('form check box over a printed box' in m for m in result.messages), result.messages)


def glyph_docx(layout, glyph):
    """BOXED, then the biopsy marked with a plain ``glyph`` run in Segoe UI Symbol and the polypectomy with U+2612."""
    def run(text, font=None):
        props = f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}"/></w:rPr>' if font else ''
        return f'<w:r>{props}<w:t xml:space="preserve">{text}</w:t></w:r>'
    if layout == 'table':
        rows = [(glyph, 'Biopsy'), ('☒', SNARE)]
        body = '<w:tbl>' + ''.join(f'<w:tr><w:tc><w:p>{run(box, "Segoe UI Symbol")}</w:p></w:tc><w:tc>{paragraph(label)}'
                                   '</w:tc></w:tr>' for box, label in rows) + '</w:tbl>'
    else:
        body = ''.join(f'<w:p>{run(box, "Segoe UI Symbol")}{run(" " + label)}</w:p>'
                       for box, label in ((glyph, 'Biopsy'), ('☒', SNARE)))
    return docgen.make_docx_from_body(note_paragraphs() + body)


class Release12PlainBoxCharactersInWordTests(unittest.TestCase):
    """release:12 (b) (critical). A Word document whose box is the plain character U+25A2 or U+2B1C in a text font (not
    a content control) was passed over, so the unchecked biopsy was a ready 45380."""

    def test_the_unchecked_biopsy_is_never_ready(self):
        for layout in ('table', 'paragraphs'):
            for glyph in ('▢', '⬜'):
                with self.subTest(layout=layout, glyph=hex(ord(glyph))):
                    result = docx_result(glyph_docx(layout, glyph))
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertIn(glyph, result.text)
                    self.assertEqual(read(result.text, 'Biopsy')[0], 'negated')
                    self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE)), ('excluded', 'ready'))


if __name__ == '__main__':
    unittest.main()
