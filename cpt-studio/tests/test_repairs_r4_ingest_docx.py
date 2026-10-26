"""Regressions for refutation round 4, INGEST lens, Word side.

- extraction:3: a list whose every bullet is the same box shape (Word's shadowed square ❑, a white square) is not a
  checklist the document marks: its items are written with the unread mark '[?]' (held), never '☐' (negated). A list
  whose bullets show both box states is still written ☐ / ☒ (round 3 ingest:5);
- extraction:5, contract:5: text formatted as struck through (w:strike, w:dstrike, directly or through a style) and
  white text with nothing shaded behind it are named and make the result partial, as the PDF side does; the text is
  kept;
- extraction:9: the numbering part is read once, so a large numbering part costs about what none does.

Each document is synthetic, built here from raw WordprocessingML, extracted with the sandboxed extract_document (or in
process where only extraction is timed), routed for real and assessed by the real engine.
"""
import io
import time
import unittest
import zipfile

from studio.gi import detect
from studio.ingest import docx as docx_module
from studio.ingest import pdf as pdf_module
from studio.ingest.docx import extract_docx
from studio.ingest.extract import Limits
from tests.support import docgen
from tests.test_repairs_r3_forms_docx import (_escape, docx_result, level, list_docx, note_paragraphs, numbering,
                                              numpr, paragraph)
from tests.test_repairs_r3_forms_pdf import codes
from tests.test_repairs_status_r2_routing import read

SNARE = 'Cold snare polypectomy of the sigmoid polyp'
FORCEPS = 'Cold forceps biopsy of the descending colon polyp'
NOTE_LINES = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Date of service: 2026-10-21',
              'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.',
              'Findings: A 6 mm sigmoid polyp and a 4 mm descending colon polyp were seen.', 'Procedures performed:']
IMPRESSION = 'Impression: Two polyps removed.'


# --- extraction:3 -- a box-shaped bullet on every item ------------------------------------------------------------

def bulleted(lvl_text, font, *, items=(SNARE, FORCEPS)):
    """The verifier's note: 'Procedures performed:' then list paragraphs whose numbering level is a bullet of
    ``lvl_text`` in ``font``, then the impression."""
    body = (note_paragraphs(NOTE_LINES) + ''.join(paragraph(item, numpr(1)) for item in items)
            + paragraph(IMPRESSION))
    data = docgen.make_docx_from_body(body)
    return docgen.rewrite_zip(data, {'word/numbering.xml': numbering({0: level(0, 'bullet', lvl_text, font)},
                                                                    {1: (0, '')})})


def unread_note(count):
    return (f'The document has {count} list item{"" if count == 1 else "s"} whose bullet is a box, and no list bullet '
            f'that is a checked box; {"it was" if count == 1 else "they were"} written as unread ([?]), so check the '
            'original.')


class Extraction3BoxShapedBulletTests(unittest.TestCase):
    def test_an_ordinary_list_of_box_bullets_is_held_never_negated(self):
        for lvl_text, font in (('\uf071', 'Wingdings'), ('q', 'Wingdings'), ('\uf06f', 'Wingdings'), ('□', 'Arial'),
                               ('❏', 'Segoe UI Symbol')):
            with self.subTest(lvl_text=lvl_text, font=font):
                result = docx_result(bulleted(lvl_text, font))
                self.assertEqual((result.status, result.messages), ('ok', (unread_note(2),)))
                self.assertIn(f'Procedures performed:\n[?] {SNARE}\n[?] {FORCEPS}\n{IMPRESSION}', result.text)
                for phrase in (SNARE, FORCEPS):
                    status, cues = read(result.text, phrase)
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertIn(detect.BOX_UNREAD, cues)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))

    def test_an_all_unchecked_checklist_is_held_never_ready(self):
        result = docx_result(bulleted('\uf0a8', 'Wingdings', items=('Biopsy', 'Cold snare polypectomy')))
        self.assertIn('\n[?] Biopsy\n[?] Cold snare polypectomy\n', result.text)
        self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')), ('held', 'held'))

    def test_a_checklist_with_both_states_is_still_read(self):
        """Positive control (round 3 ingest:5): an unchecked level and a checked level in one document."""
        data = list_docx([('Cold snare polypectomy', numpr(2)), ('Biopsy', numpr(1))],
                         {0: level(0, 'bullet', '\uf0a8', 'Wingdings'), 1: level(0, 'bullet', '\uf0fe', 'Wingdings')},
                         {1: (0, ''), 2: (1, '')})
        result = docx_result(data)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n☒ Cold snare polypectomy\n☐ Biopsy'), result.text[-80:])
        self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')),
                         ('excluded', 'ready'))

    def test_a_list_of_checked_bullets_and_ordinary_bullets_are_as_before(self):
        result = docx_result(bulleted('\uf0fe', 'Wingdings'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn(f'Procedures performed:\n☒ {SNARE}\n☒ {FORCEPS}\n', result.text)
        for lvl_text, font in (('\uf0b7', 'Symbol'), ('o', 'Courier New'), ('\uf0a7', 'Wingdings')):
            with self.subTest(lvl_text=lvl_text, font=font):
                result = docx_result(bulleted(lvl_text, font))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn(f'Procedures performed:\n{SNARE}\n{FORCEPS}\n', result.text)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('ready', 'ready'))

    def test_the_unread_mark_is_the_pdf_sides(self):
        self.assertEqual(docx_module._ING_UNREAD_BOX, pdf_module._ING_UNREAD_BOX)
        self.assertNotIn(docx_module._ING_BULLET, docx_result(bulleted('\uf071', 'Wingdings')).text)


# --- extraction:5, contract:5 -- struck-through and white text ------------------------------------------------------

BIOPSY = 'A cold forceps biopsy was taken from the descending colon polyp.'
STRUCK_NOTE = ('The document has text formatted as struck through (1 run); it was read as written, so check it against '
               'the original.')
WHITE_NOTE = ('The document has text that a viewer may not show (white text with nothing shaded behind it, 1 run); it '
              'was read, so check it against the original.')
STYLES = ('<w:style w:type="character" w:styleId="Retracted"><w:name w:val="Retracted"/><w:rPr><w:strike/></w:rPr>'
          '</w:style><w:style w:type="paragraph" w:styleId="Struck"><w:name w:val="Struck"/><w:rPr><w:dstrike/></w:rPr>'
          '</w:style><w:style w:type="character" w:styleId="Ghost"><w:name w:val="Ghost"/><w:rPr>'
          '<w:color w:val="FFFFFF"/></w:rPr></w:style>')


def marked_note(run_properties='', paragraph_properties='', *, wrap=lambda p: p, styles=STYLES):
    """Family B of the verifier: no other denial in the note, so the formatting is the only signal."""
    sentence = (f'<w:p>{paragraph_properties}<w:r><w:t xml:space="preserve">Interventions: </w:t></w:r><w:r>'
                f'{run_properties}<w:t>{_escape(BIOPSY)}</w:t></w:r></w:p>')
    body = note_paragraphs(NOTE_LINES[:4]) + wrap(sentence) + paragraph('Impression: One polyp sampled.')
    data = docgen.make_docx_from_body(body)
    original = zipfile.ZipFile(io.BytesIO(data)).read('word/styles.xml').decode('utf-8')
    return docgen.rewrite_zip(data, {'word/styles.xml': original.replace('</w:styles>', styles + '</w:styles>').encode()})


class Extraction5StruckAndWhiteTextTests(unittest.TestCase):
    def test_struck_text_is_named_and_partial(self):
        cases = {'w:strike': ('<w:rPr><w:strike/></w:rPr>', ''),
                 'w:dstrike': ('<w:rPr><w:dstrike/></w:rPr>', ''),
                 'w:strike on': ('<w:rPr><w:strike w:val="on"/></w:rPr>', ''),
                 'a character style': ('<w:rPr><w:rStyle w:val="Retracted"/></w:rPr>', ''),
                 'a paragraph style': ('', '<w:pPr><w:pStyle w:val="Struck"/></w:pPr>')}
        for label, (run, para) in cases.items():
            with self.subTest(label):
                result = docx_result(marked_note(run, para))
                self.assertEqual(result.status, 'partial', result.messages)
                if label == 'a paragraph style':  # the label's run is struck too
                    self.assertIn('The document has text formatted as struck through (2 runs)', result.messages[0])
                else:
                    self.assertEqual(result.messages, (STRUCK_NOTE,))
                self.assertIn(BIOPSY, result.text)

    def test_white_text_is_named_and_partial(self):
        for label, run in (('direct', '<w:rPr><w:color w:val="FFFFFF"/></w:rPr>'),
                           ('near white', '<w:rPr><w:color w:val="FDFEFF"/></w:rPr>'),
                           ('a character style', '<w:rPr><w:rStyle w:val="Ghost"/></w:rPr>')):
            with self.subTest(label):
                result = docx_result(marked_note(run))
                self.assertEqual((result.status, result.messages), ('partial', (WHITE_NOTE,)))
                self.assertIn(BIOPSY, result.text)

    def test_the_text_is_kept_and_the_code_assessed_as_before(self):
        text = docx_result(marked_note('<w:rPr><w:strike/></w:rPr>')).text
        self.assertEqual(codes(text, ('45380', 'A cold forceps biopsy was taken'))[0], 'ready')

    def test_ordinary_formatting_stays_ok(self):
        cases = {'plain': ('', ''), 'underline': ('<w:rPr><w:u w:val="single"/></w:rPr>', ''),
                 'strike off': ('<w:rPr><w:strike w:val="0"/></w:rPr>', ''),
                 'a struck style turned off on the run': ('<w:rPr><w:rStyle w:val="Retracted"/><w:strike w:val="false"/>'
                                                          '</w:rPr>', ''),
                 'black text': ('<w:rPr><w:color w:val="000000"/></w:rPr>', ''),
                 'light grey text': ('<w:rPr><w:color w:val="F2F2F2"/></w:rPr>', ''),
                 'automatic colour': ('<w:rPr><w:color w:val="auto"/></w:rPr>', ''),
                 'white on a shaded run': ('<w:rPr><w:color w:val="FFFFFF"/><w:shd w:val="clear" w:color="auto" '
                                           'w:fill="1F3864"/></w:rPr>', ''),
                 'white on a highlight': ('<w:rPr><w:color w:val="FFFFFF"/><w:highlight w:val="darkBlue"/></w:rPr>', ''),
                 'white on a shaded paragraph': ('<w:rPr><w:color w:val="FFFFFF"/></w:rPr>',
                                                 '<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="000000"/></w:pPr>')}
        for label, (run, para) in cases.items():
            with self.subTest(label):
                result = docx_result(marked_note(run, para))
                self.assertEqual((result.status, result.messages), ('ok', ()))
        cell = ('<w:tbl><w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="1F3864"/></w:tcPr>{}</w:tc>'
                '</w:tr></w:tbl>')
        result = docx_result(marked_note('<w:rPr><w:color w:val="FFFFFF"/></w:rPr>', wrap=cell.format))
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_white_text_on_shading_a_style_paints_stays_ok(self):
        """A paragraph style's shading, and a table style's header-row shading (conditional formatting)."""
        shaded = STYLES + ('<w:style w:type="paragraph" w:styleId="Banner"><w:name w:val="Banner"/><w:pPr><w:shd '
                           'w:val="clear" w:color="auto" w:fill="1F3864"/></w:pPr></w:style>'
                           '<w:style w:type="table" w:styleId="DarkHeader"><w:name w:val="Dark Header"/>'
                           '<w:tblStylePr w:type="firstRow"><w:tcPr><w:shd w:val="clear" w:color="auto" '
                           'w:fill="1F3864"/></w:tcPr></w:tblStylePr></w:style>')
        white = '<w:rPr><w:color w:val="FFFFFF"/></w:rPr>'
        result = docx_result(marked_note(white, '<w:pPr><w:pStyle w:val="Banner"/></w:pPr>', styles=shaded))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        table = '<w:tbl><w:tblPr><w:tblStyle w:val="DarkHeader"/></w:tblPr><w:tr><w:tc>{}</w:tc></w:tr></w:tbl>'
        result = docx_result(marked_note(white, wrap=table.format, styles=shaded))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        result = docx_result(marked_note(white, styles=shaded))  # the same styles, unused: named
        self.assertEqual((result.status, result.messages), ('partial', (WHITE_NOTE,)))

    def test_struck_whitespace_is_not_counted(self):
        body = note_paragraphs(NOTE_LINES[:4]) + ('<w:p><w:r><w:t xml:space="preserve">Interventions: biopsy</w:t>'
                                                  '</w:r><w:r><w:rPr><w:strike/></w:rPr><w:t xml:space="preserve">   '
                                                  '</w:t></w:r></w:p>')
        result = docx_result(docgen.make_docx_from_body(body))
        self.assertEqual((result.status, result.messages), ('ok', ()))


# --- extraction:9 -- a large numbering part --------------------------------------------------------------------

def numbering_docx(levels: int, paragraphs: int, *, overrides: int = 0, ilvl_each: bool = False) -> bytes:
    """``levels`` w:lvl in one abstract numbering, a w:num pointing at it (with ``overrides`` level overrides), and
    ``paragraphs`` list paragraphs (each asking for its own ilvl when ``ilvl_each``)."""
    lvls = ''.join(f'<w:lvl w:ilvl="{n}"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="\uf0b7"/>'
                   f'<w:lvlJc w:val="left"/><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr></w:lvl>'
                   for n in range(1, levels + 1))
    lvl_overrides = ''.join(f'<w:lvlOverride w:ilvl="{n + 100000}"><w:startOverride w:val="1"/></w:lvlOverride>'
                            for n in range(overrides))
    xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="{docgen.W_NS}">'
           f'<w:abstractNum w:abstractNumId="0">{lvls}</w:abstractNum>'
           f'<w:num w:numId="1">{lvl_overrides}<w:abstractNumId w:val="0"/></w:num></w:numbering>').encode()
    body = note_paragraphs(NOTE_LINES) + ''.join(
        paragraph(f'Synthetic list item {n}.', numpr(1, ilvl=levels + 1 + n if ilvl_each else 0))
        for n in range(paragraphs))
    return docgen.rewrite_zip(docgen.make_docx_from_body(body), {'word/numbering.xml': xml})


class Extraction9NumberingCostTests(unittest.TestCase):
    def timed(self, data):
        started = time.monotonic()
        result = extract_docx(data, Limits())
        return time.monotonic() - started, result

    def test_a_large_numbering_part_costs_about_what_none_does(self):
        baseline, plain = self.timed(numbering_docx(1, 1000))
        for label, data in (('20,000 levels', numbering_docx(20000, 1000)),
                            ('5,000 overrides', numbering_docx(1, 1000, overrides=5000)),
                            ('a missing level per paragraph', numbering_docx(5000, 500, ilvl_each=True))):
            with self.subTest(label):
                elapsed, result = self.timed(data)
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertLess(elapsed, 4 * baseline + 1.0, (elapsed, baseline))
        self.assertEqual(plain.status, 'ok')

    def test_levels_are_found_as_before(self):
        """Overrides before levels, the first of two levels for one ilvl, and a missing level."""
        xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="{docgen.W_NS}">'
               '<w:abstractNum w:abstractNumId="0">' + level(0, 'bullet', '\uf0a8', 'Wingdings')
               + level(0, 'bullet', '\uf0fe', 'Wingdings') + level(1, 'bullet', '\uf0a8', 'Wingdings') + '</w:abstractNum>'
               '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
               '<w:num w:numId="2"><w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"/>'
               '<w:lvlOverride w:ilvl="0">' + level(0, 'bullet', '\uf0fe', 'Wingdings') + '</w:lvlOverride>'
               '<w:lvlOverride w:ilvl="0">' + level(0, 'bullet', '\uf0a8', 'Wingdings') + '</w:lvlOverride></w:num>'
               '</w:numbering>').encode()
        body = note_paragraphs(NOTE_LINES) + ''.join(paragraph(text, numpr(num, ilvl)) for text, num, ilvl in (
            ('Biopsy', 1, 0), ('Cold snare polypectomy', 2, 0), ('Tattoo', 1, 5)))
        text = docx_result(docgen.rewrite_zip(docgen.make_docx_from_body(body), {'word/numbering.xml': xml})).text
        self.assertTrue(text.endswith('\n☐ Biopsy\n☒ Cold snare polypectomy\nTattoo'), text[-60:])


if __name__ == '__main__':
    unittest.main()
