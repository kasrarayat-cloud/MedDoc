"""Regression tests for the extraction repairs of refutation round 2 (ingest:0 to ingest:12).

Every document is synthetic and built here, from raw PDF syntax, raw
WordprocessingML or with reportlab, python-docx, Pillow and pypdf; nothing is
read from disk. Each class names the finding it pins. Over-corrections carry
positive controls showing that an ordinary document still extracts 'ok' with
the same text.

The check-box contract shared with routing: extraction writes every check box
it recognises as ☐ (unchecked) or ☒ (checked).
"""
from __future__ import annotations

import io
import os
import re
import tempfile
import time
import unittest
import zlib

import docx
import pypdf
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw
from pypdf.generic._font import Font
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from studio.gi.detect import status_for_span
from studio.ingest import Limits, extract_document
from studio.ingest import docx as docx_ingest
from tests.support import docgen
from tests.test_ingest import FakeOcr, page_texts
from tests.test_repairs_ingest_pdf import HELVETICA, serialise, serialise_again, stream

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
UNCHECKED, CHECKED = '☐', '☒'
# Glyphs a symbol table may never emit any more: every recognised box is ☐ or ☒.
OTHER_BOXES = set('□▢◻◽⬜❏❐❑❒☑⌧⮽') | {
    '\U0001f790', '\U0001f5f5', '\U0001f5f7', '\U0001f5f9'}
NOTE_LINES = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING', 'Date of service: 2026-10-21',
              'Procedure: Colonoscopy.', 'Technique: The colonoscope was advanced to the cecum.',
              'Findings: A 6 mm sigmoid polyp was seen.', 'Interventions:']


def docx_extract(data: bytes):
    return docx_ingest.extract_docx(data, Limits())


def saved(document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def checklist_docx(box_segments) -> bytes:
    """NOTE_LINES, then one paragraph of ``box_segments``: (text, font) runs or ('SYM', font, hex) for w:sym."""
    document = docx.Document()
    for line in NOTE_LINES:
        document.add_paragraph(line)
    paragraph = document.add_paragraph()
    for segment in box_segments:
        if segment[0] == 'SYM':
            sym = OxmlElement('w:sym')
            sym.set(qn('w:font'), segment[1])
            sym.set(qn('w:char'), segment[2])
            paragraph.add_run()._r.append(sym)
            continue
        run = paragraph.add_run(segment[0])
        if segment[1]:
            run.font.name = segment[1]
    return saved(document)


def reading(text: str, item: str, occurrence: int = 0) -> str:
    """Routing's status for the ``occurrence``-th ``item`` in ``text`` (the cross-module check)."""
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(item, start + 1)
    return status_for_span(text, start, start + len(item))[0]


# --- ingest:0 — every symbol-font box becomes ☐ or ☒ --------------------------------------------

class SymbolBoxGlyphTests(unittest.TestCase):
    """ingest:0 — the usual Word empty box (Wingdings 168) and its siblings are written as ☐."""

    def test_wingdings_168_in_every_encoding_is_an_unchecked_box(self):
        for label, segments in {'typed U+00A8': [('¨', 'Wingdings'), (' Biopsy', None)],
                                'w:sym F0A8': [('SYM', 'Wingdings', 'F0A8'), (' Biopsy', None)],
                                'private-use U+F0A8': [('', 'Wingdings'), (' Biopsy', None)]}.items():
            with self.subTest(label):
                result = docx_extract(checklist_docx(segments))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_symbol_tables_emit_only_the_two_contract_boxes(self):
        for font, table in docx_ingest.SYMBOL_FONTS.items():
            with self.subTest(font=font):
                self.assertFalse(set(table.values()) & OTHER_BOXES, sorted(set(table.values()) & OTHER_BOXES))
        expected = {('wingdings', 0x6F): UNCHECKED, ('wingdings', 0x71): UNCHECKED, ('wingdings', 0x72): UNCHECKED,
                    ('wingdings', 0xA8): UNCHECKED, ('wingdings', 0x78): CHECKED, ('wingdings', 0xFD): CHECKED,
                    ('wingdings', 0xFE): CHECKED, ('wingdings2', 0xA3): UNCHECKED, ('wingdings2', 0x52): CHECKED,
                    ('wingdings2', 0x53): CHECKED, ('wingdings2', 0x54): CHECKED, ('zapfdingbats', 0x6F): UNCHECKED,
                    ('zapfdingbats', 0x70): UNCHECKED, ('zapfdingbats', 0x71): UNCHECKED,
                    ('zapfdingbats', 0x72): UNCHECKED}
        for (font, code), glyph in expected.items():
            with self.subTest(font=font, code=hex(code)):
                self.assertEqual(docx_ingest.SYMBOL_FONTS[font][code], glyph)

    def test_every_box_glyph_extraction_writes_reads_as_routing_expects(self):
        """Cross-module: each unchecked glyph a symbol table emits negates '<glyph> Biopsy'; no checked one does."""
        base = '\n'.join(NOTE_LINES) + '\n'
        for font, table in docx_ingest.SYMBOL_FONTS.items():
            for code, glyph in sorted(table.items()):
                if glyph not in (UNCHECKED, CHECKED):
                    continue
                with self.subTest(font=font, code=hex(code)):
                    status = reading(base + f'{glyph} Biopsy\n', 'Biopsy')
                    if glyph == UNCHECKED:
                        self.assertEqual(status, 'negated')
                    else:
                        self.assertNotEqual(status, 'negated')

    def test_checklist_of_mixed_symbol_boxes(self):
        segments = [('þ', 'Wingdings'), (' Cold snare polypectomy  ', None), ('¨', 'Wingdings'),
                    (' Biopsy  ', None), ('£', 'Wingdings 2'), (' Hot snare  ', None), ('R', 'Wingdings 2'),
                    (' Tattoo', None)]
        result = docx_extract(checklist_docx(segments))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('☒ Cold snare polypectomy  ☐ Biopsy  ☐ Hot snare  '
                                             '☒ Tattoo'), result.text)

    def test_ordinary_fonts_keep_their_own_characters(self):
        result = docx_extract(checklist_docx([('◻ ❑ ☑ ¨ Biopsy', 'Calibri')]))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('◻ ❑ ☑ ¨ Biopsy'))


# --- ingest:1 (Word half) — a legacy FORMCHECKBOX is written as its state ---------------------------

def form_checkbox(state: str) -> str:
    """A legacy FORMCHECKBOX field; ``state`` is the w:checkBox content (w:default / w:checked)."""
    return ('<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Check1"/><w:enabled/>'
            f'<w:calcOnExit w:val="0"/><w:checkBox><w:sizeAuto/>{state}</w:checkBox></w:ffData></w:fldChar></w:r>'
            '<w:r><w:instrText xml:space="preserve"> FORMCHECKBOX </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def legacy_checklist(rows) -> bytes:
    """NOTE_LINES as paragraphs, then one paragraph per (state, label)."""
    paragraphs = ''.join(f'<w:p><w:r><w:t xml:space="preserve">{line}</w:t></w:r></w:p>' for line in NOTE_LINES)
    for state, label in rows:
        paragraphs += f'<w:p>{form_checkbox(state)}<w:r><w:t xml:space="preserve"> {label}</w:t></w:r></w:p>'
    return docgen.make_docx_from_body(paragraphs)


class DocxLegacyCheckboxTests(unittest.TestCase):
    """ingest:1 (DOCX) — w:ffData/w:checkBox is written as ☐ / ☒ in place of the field, not counted."""

    def test_unchecked_and_checked_legacy_boxes(self):
        data = legacy_checklist([('<w:default w:val="0"/>', 'Biopsy'),
                                 ('<w:default w:val="0"/><w:checked/>', 'Cold snare polypectomy')])
        result = docx_extract(data)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy'),
                        result.text)
        self.assertEqual(reading(result.text, 'Biopsy'), 'negated')
        self.assertNotEqual(reading(result.text, 'Cold snare polypectomy'), 'negated')

    def test_checked_state_decides_over_the_default(self):
        cases = {'default on, no checked': ('<w:default w:val="1"/>', CHECKED),
                 'default on, checked off': ('<w:default w:val="1"/><w:checked w:val="0"/>', UNCHECKED),
                 'default off, checked false': ('<w:default/><w:checked w:val="false"/>', UNCHECKED),
                 'no default, no checked': ('', UNCHECKED),
                 'bare default': ('<w:default/>', CHECKED)}
        for label, (state, glyph) in cases.items():
            with self.subTest(label):
                result = docx_extract(legacy_checklist([(state, 'Biopsy')]))
                self.assertTrue(result.text.endswith(f'\n{glyph} Biopsy'), result.text)

    def test_drop_down_fields_are_still_counted(self):
        drop_down = ('<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Prep"/><w:ddList>'
                     '<w:listEntry w:val="Adequate"/></w:ddList></w:ffData></w:fldChar></w:r><w:r><w:instrText '
                     'xml:space="preserve"> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/>'
                     '</w:r><w:r><w:t xml:space="preserve"> prep quality</w:t></w:r></w:p>')
        result = docx_extract(docgen.make_docx_from_body(drop_down))
        self.assertEqual(result.messages, ('Not extracted from the document body: 1 legacy form-field value.',))

    def test_hidden_legacy_box_is_not_written(self):
        hidden = form_checkbox('<w:default w:val="0"/>').replace(
            '<w:r><w:fldChar w:fldCharType="begin">', '<w:r><w:rPr><w:vanish/></w:rPr><w:fldChar w:fldCharType="begin">')
        data = docgen.make_docx_from_body(f'<w:p>{hidden}<w:r><w:t xml:space="preserve"> Biopsy</w:t></w:r></w:p>')
        result = docx_extract(data)
        self.assertEqual(result.text, ' Biopsy')
        self.assertEqual(result.messages, ('Not extracted from the document body: 1 run of hidden text.',))

    def test_through_the_child_process(self):
        data = legacy_checklist([('<w:default w:val="0"/>', 'Biopsy')])
        result = extract_document(data, 'checklist.docx', DOCX, ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('☐ Biopsy'))


# --- ingest:2 — symbol fonts, private-use and control codes in PDF text ------------------------------

PDF = 'application/pdf'
NO_TEXT = 'No text could be read from the PDF.'
PDF_NOTE = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'),
            (72, 720, 'Date of service: 2026-10-21'), (72, 700, 'Procedure: Colonoscopy.'),
            (72, 680, 'Technique: The colonoscope was advanced to the cecum.'),
            (72, 660, 'Findings: A 6 mm sigmoid polyp was seen.'), (72, 640, 'Interventions:')]
SYMBOL_DESCRIPTOR = (b'<< /Type /FontDescriptor /FontName /Wingdings-Regular /Flags 4 /FontBBox [0 -200 1000 900] '
                     b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>')
WIDTHS = '/FirstChar 32 /LastChar 255 /Widths [' + ' '.join(['1000'] * 224) + ']'


def esc(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def to_unicode(pairs, code_bytes: int = 1) -> bytes:
    """A ToUnicode CMap: (code, text) pairs."""
    width = 2 * code_bytes
    entries = '\n'.join(f'<{code:0{width}X}> <{text.encode("utf-16-be").hex().upper()}>' for code, text in pairs)
    low, high = '0' * width, 'F' * width
    return stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry '
                  '(Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic-UCS def\n/CMapType 2 def\n'
                  f'1 begincodespacerange\n<{low}> <{high}>\nendcodespacerange\n{len(pairs)} beginbfchar\n{entries}\n'
                  'endbfchar\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')


def font_pdf(font: str, glyph_lines, *, extra: dict | None = None, note=PDF_NOTE) -> bytes:
    """One page: ``note`` in Helvetica (/F1), then each (y, hex codes in /F2, Helvetica text) line."""
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in note)
    for y, codes, label in glyph_lines:
        content += f'\nBT /F2 11 Tf 72 {y} Td <{codes}> Tj /F1 11 Tf ({esc(label)}) Tj ET'
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                   b'/F2 6 0 R >> >> /Contents 5 0 R >>'),
               4: HELVETICA, 5: stream(content), 6: font.encode()}
    objects.update(extra or {})
    return serialise(objects)


def wingdings(variant: str) -> tuple[str, dict]:
    """The Word 'Save as PDF' shape of a Wingdings font, in the verifier's four variants."""
    base = f'<< /Type /Font /Subtype /TrueType /BaseFont /Wingdings-Regular {WIDTHS} /FontDescriptor 8 0 R'
    extra = {8: SYMBOL_DESCRIPTOR}
    if variant == 'private-use ToUnicode':
        return base + ' /ToUnicode 7 0 R >>', extra | {7: to_unicode([(0xA8, ''), (0xFE, ''),
                                                                        (0x4A, '')])}
    if variant == 'no ToUnicode':
        return base + ' >>', extra
    if variant == 'WinAnsi, no ToUnicode':
        return base + ' /Encoding /WinAnsiEncoding >>', extra
    if variant == 'ballot-box ToUnicode':
        return base + ' /ToUnicode 7 0 R >>', extra | {7: to_unicode([(0xA8, '\u2610'), (0xFE, '\u2611')])}
    if variant == 'Latin-echo ToUnicode':
        return base + ' /ToUnicode 7 0 R >>', extra | {7: to_unicode([(0xA8, '\u00a8'), (0xFE, '\u00fe')])}
    raise ValueError(variant)


BOX_LINES = [(620, 'A8', ' Biopsy'), (600, 'FE', ' Cold snare polypectomy')]
VARIANTS = ('private-use ToUnicode', 'no ToUnicode', 'WinAnsi, no ToUnicode', 'ballot-box ToUnicode',
            'Latin-echo ToUnicode')


def pdf_extract(data: bytes, **kwargs):
    return extract_document(data, 'synthetic.pdf', PDF, **kwargs)


def undecodable_note(count: int, pages: str = 'Page 1 has') -> str:
    if count == 1:
        return (f'{pages} 1 character that does not map to text (symbol-font glyphs, private-use or control '
                'codes); it was not extracted.')
    return (f'{pages} {count} characters that do not map to text (symbol-font glyphs, private-use or control '
            'codes); they were not extracted.')


def composite_font(*, to_unicode_ref: str = '', cid_to_gid: str = '/Identity', base: str = 'ABCDEF+SyntheticSans'):
    return (f'<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding /Identity-H /DescendantFonts [9 0 R] '
            f'{to_unicode_ref} >>',
            {9: (f'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{base} /CIDSystemInfo << /Registry (Adobe) '
                 f'/Ordering (Identity) /Supplement 0 >> /FontDescriptor 10 0 R /CIDToGIDMap {cid_to_gid} /DW 500 '
                 '>>').encode(),
             10: (f'<< /Type /FontDescriptor /FontName /{base} /Flags 32 /FontBBox [0 -200 1000 900] /ItalicAngle 0 '
                  '/Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>').encode()})


GLYPH_WORDS = 'Colonoscopy cancelled'  # what the glyph-index codes below draw, one glyph per character
# Glyph indices 0x24 upward: pypdf would show them as '$%&...', printable text that means nothing.
GLYPH_CODES = ''.join(f'{index:04X}' for index in range(0x24, 0x24 + len(GLYPH_WORDS)))


class PdfSymbolFontTests(unittest.TestCase):
    """ingest:2 — a Word checklist saved as PDF keeps its boxes; nothing undecodable passes silently."""

    def test_wingdings_boxes_in_every_encoding(self):
        for variant in VARIANTS:
            with self.subTest(variant):
                font, extra = wingdings(variant)
                result = pdf_extract(font_pdf(font, BOX_LINES, extra=extra), ocr=None)
                self.assertEqual((result.status, result.method, result.messages), ('ok', 'pdf-text', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy'),
                                result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_symbol_font_inside_a_form_xobject(self):
        font, extra = wingdings('no ToUnicode')
        form = stream('BT /F2 11 Tf 0 0 Td <A8> Tj /F1 11 Tf ( Biopsy) Tj ET',
                      '/Type /XObject /Subtype /Form /BBox [0 0 300 20] /Resources << /Font << /F1 4 0 R /F2 6 0 R '
                      '>> >>')
        data = font_pdf(font, [], extra=extra | {9: form}).replace(
            b'/Font << /F1 4 0 R /F2 6 0 R >> >>', b'/Font << /F1 4 0 R /F2 6 0 R >> /XObject << /Fx 9 0 R >> >>')
        data = data.replace(b'(Interventions:) Tj ET', b'(Interventions:) Tj ET\nq 1 0 0 1 72 620 cm /Fx Do Q')
        result = pdf_extract(serialise_again(data), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Interventions:\n\u2610 Biopsy'), result.text)

    def test_zapf_dingbats_shadowed_box(self):
        result = pdf_extract(font_pdf('<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>',
                                      [(620, '6F', ' Biopsy')]), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n☐ Biopsy'), result.text)

    def test_unmapped_symbol_glyph_is_counted_not_shown_as_a_letter(self):
        for variant in ('private-use ToUnicode', 'no ToUnicode', 'WinAnsi, no ToUnicode'):
            with self.subTest(variant):
                font, extra = wingdings(variant)
                result = pdf_extract(font_pdf(font, [(620, '4A', ' Mood')], extra=extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
                self.assertTrue(result.text.endswith('Interventions:\n Mood'), result.text)

    def test_private_use_code_in_a_text_font_is_counted(self):
        font = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 7 0 R >>'
        result = pdf_extract(font_pdf(font, [(620, '41', ' Biopsy'), (600, '4141', ' Cold snare polypectomy')],
                                      extra={7: to_unicode([(0x41, '')])}), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(3),)))
        self.assertTrue(result.text.endswith('Interventions:\n Biopsy\n Cold snare polypectomy'), result.text)

    def test_word_symbol_bullets_are_read(self):
        font = (f'<< /Type /Font /Subtype /TrueType /BaseFont /Symbol {WIDTHS} /FontDescriptor 8 0 R '
                '/ToUnicode 7 0 R >>')
        result = pdf_extract(font_pdf(font, [(620, 'B7', ' Cold snare polypectomy')],
                                      extra={8: SYMBOL_DESCRIPTOR, 7: to_unicode([(0xB7, '')])}), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n• Cold snare polypectomy'), result.text)

    def test_composite_wingdings_maps_its_private_use_codes(self):
        font, extra = composite_font(to_unicode_ref='/ToUnicode 7 0 R', base='ABCDEF+Wingdings-Regular')
        extra[7] = to_unicode([(0x0003, ''), (0x0004, ''), (0x0005, 'A')], code_bytes=2)
        result = pdf_extract(font_pdf(font, [(620, '0003', ' Biopsy'), (600, '0004', ' Cold snare'),
                                             (580, '0005', ' Tattoo')], extra=extra), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
        self.assertTrue(result.text.endswith('☐ Biopsy\n☒ Cold snare\n Tattoo'), result.text)

    def test_glyph_index_font_without_tounicode_is_not_text(self):
        font, extra = composite_font()
        data = font_pdf(font, [(620, GLYPH_CODES, '')], extra=extra, note=[])
        alone = pdf_extract(data, ocr=None)
        self.assertEqual((alone.status, alone.text), ('failed', ''))
        self.assertEqual(alone.messages, ('Page 1 has no usable text layer and OCR is not available on this server.',
                                          undecodable_note(len(GLYPH_WORDS)), NO_TEXT))
        with FakeOcr() as fake:
            read = pdf_extract(data, ocr=fake.tools)
        self.assertEqual((read.status, read.method, read.ocr_pages), ('ok', 'pdf-ocr', (1,)))
        beside_text = pdf_extract(font_pdf(font, [(620, GLYPH_CODES, '')], extra=extra), ocr=None)
        self.assertEqual((beside_text.status, beside_text.messages),
                         ('ok', (undecodable_note(len(GLYPH_WORDS)),)))
        self.assertTrue(beside_text.text.endswith('Interventions:\n'), beside_text.text)

    def test_composite_fonts_that_name_characters_are_read(self):
        mapped, extra = composite_font(to_unicode_ref='/ToUnicode 7 0 R')
        extra[7] = to_unicode([(index, char) for index, char in enumerate(GLYPH_WORDS, 0x24)], code_bytes=2)
        result = pdf_extract(font_pdf(mapped, [(620, GLYPH_CODES, '')], extra=extra), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + GLYPH_WORDS), result.text)
        # CIDs mapped through a CIDToGIDMap stream are characters (here, Unicode): pypdf's reading is kept.
        unicode_cids = ''.join(f'{ord(char):04X}' for char in GLYPH_WORDS)
        cid_font, cid_extra = composite_font(cid_to_gid='11 0 R')
        cid_extra[11] = stream(bytes(2 * 128))
        kept = pdf_extract(font_pdf(cid_font, [(620, unicode_cids, '')], extra=cid_extra), ocr=None)
        self.assertEqual((kept.status, kept.messages), ('ok', ()))
        self.assertTrue(kept.text.endswith('\n' + GLYPH_WORDS), kept.text)

    def test_mapped_font_keeps_the_original_width_model(self):
        from studio.ingest.pdffonts import mapped_simple_font
        cases = {variant: wingdings(variant) for variant in VARIANTS}
        cases['Zapf Dingbats (core metrics)'] = ('<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>', {})
        cases['Symbol (core metrics)'] = ('<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>', {})
        for label, (font, extra) in cases.items():
            with self.subTest(label):
                page = pypdf.PdfReader(io.BytesIO(font_pdf(font, BOX_LINES, extra=extra))).pages[0]
                original = page['/Resources']['/Font']['/F2'].get_object()
                before, after = Font.from_font_resource(original), Font.from_font_resource(mapped_simple_font(original))
                self.assertEqual((after.space_char, after.space_width), (before.space_char, before.space_width))
                self.assertEqual(after.character_widths.get(after.space_char, 0) == 0,
                                 before.character_widths.get(before.space_char, 0) == 0)
                for code in range(256):
                    if chr(code) != before.space_char:
                        self.assertEqual(after.get_text_width(chr(code)), before.get_text_width(chr(code)), hex(code))


# --- ingest:1 (PDF half) — a form check box's state at the start of the line it sits beside --------

ZAPF = b'<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>'
FORM_NOTE = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'),
             (72, 720, 'Date of service: 2026-10-21'),
             (72, 700, 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.'),
             (72, 680, 'Findings: A 6 mm sigmoid polyp was seen.'), (72, 660, 'Interventions:')]
BOX_ROWS = [('Check Box1', 'Biopsy', False, (72, 618, 84, 630), (90, 620, 'Biopsy')),
            ('Check Box2', 'Cold snare polypectomy', True, (72, 598, 84, 610), (90, 600, 'Cold snare polypectomy'))]


def box_form(rows=BOX_ROWS, *, note=FORM_NOTE, tooltips: bool = False, flags: int = 4, radio: list | None = None) -> bytes:
    """``note`` and each row's label in the page content; one check-box widget per row.

    rows: (field name, tooltip, checked, widget rect, (x, y, label) or None).
    """
    lines = list(note) + [row[4] for row in rows if row[4]]
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in lines)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 5: stream(content), 6: ZAPF,
               7: stream('q BT /ZaDb 10 Tf 0 g 1.5 2 Td (4) Tj ET Q', '/Type /XObject /Subtype /Form /BBox [0 0 12 12] '
                         '/Resources << /Font << /ZaDb 6 0 R >> >>'),
               8: stream('', '/Type /XObject /Subtype /Form /BBox [0 0 12 12]')}
    widgets, number = [], 11
    for name, tooltip, checked, rect, _ in rows:
        state = '/Yes' if checked else '/Off'
        tu = f'/TU ({esc(tooltip)})' if tooltips else ''
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Btn /T ({esc(name)}) {tu} /V {state} /AS {state} '
                           f'/Rect [{rect[0]} {rect[1]} {rect[2]} {rect[3]}] /F {flags} /P 3 0 R /MK << /CA (4) >> '
                           '/DA (/ZaDb 0 Tf 0 g) /AP << /N << /Yes 7 0 R /Off 8 0 R >> >> >>').encode()
        widgets.append(number)
        number += 1
    for name, rect, selected in radio or []:
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Btn /Ff 49152 /T ({esc(name)}) '
                           f'/V {"/Yes" if selected else "/Off"} /AS {"/Yes" if selected else "/Off"} '
                           f'/Rect [{rect[0]} {rect[1]} {rect[2]} {rect[3]}] /F 4 /P 3 0 R '
                           '/AP << /N << /Yes 7 0 R /Off 8 0 R >> >> >>').encode()
        widgets.append(number)
        number += 1
    refs = ' '.join(f'{n} 0 R' for n in widgets)
    objects[3] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R /Annots [%s] >>' % refs.encode())
    objects[10] = (f'<< /Fields [{refs}] /NeedAppearances false /DA (/Helv 0 Tf 0 g) /DR << /Font << /Helv 4 0 R '
                   '/ZaDb 6 0 R >> >> >>').encode()
    return serialise(objects)


FIELDS_NOTE = ('Page 1 has PDF form fields; their values were read and added after the page text, labelled as form '
               'fields.')


class PdfFormCheckboxPlacementTests(unittest.TestCase):
    """ingest:1 (PDF) — the box's glyph goes at the start of the one line it sits beside; the block is unchanged."""

    def test_boxes_left_of_their_labels(self):
        for tooltips, block in ((False, 'Check Box1: not checked\nCheck Box2: checked'),
                                (True, 'Biopsy: not checked\nCold snare polypectomy: checked')):
            with self.subTest(tooltips=tooltips):
                result = pdf_extract(box_form(tooltips=tooltips), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n\n'
                                                     '[PDF form fields on page 1]\n' + block), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')
                self.assertNotEqual(reading(result.text, 'Cold snare polypectomy'), 'negated')

    def test_reportlab_form(self):
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=letter, invariant=1)
        canvas.setFont('Helvetica', 11)
        for x, y, text in FORM_NOTE + [(90, 620, 'Biopsy'), (90, 600, 'Cold snare polypectomy')]:
            canvas.drawString(x, y, text)
        canvas.acroForm.checkbox(name='Check Box1', x=72, y=617, size=12, checked=False, buttonStyle='check')
        canvas.acroForm.checkbox(name='Check Box2', x=72, y=597, size=12, checked=True, buttonStyle='check')
        canvas.showPage()
        canvas.save()
        result = pdf_extract(buffer.getvalue(), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertIn('Interventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n', result.text)
        self.assertTrue(result.text.endswith('Check Box1: not checked\nCheck Box2: checked'), result.text)

    def test_no_glyph_when_the_box_cannot_be_tied_exactly(self):
        biopsy = ('Check Box1', 'Biopsy', False)
        cases = {
            # The label starts left of the box ("Biopsy: [box]"): the line does not start beside it.
            'label before the box': [biopsy + ((140, 618, 152, 630), (90, 620, 'Biopsy:'))],
            # Two baselines inside the box's height.
            'two lines beside a tall box': [biopsy + ((72, 590, 84, 640), (90, 620, 'Biopsy'))],
            # The label starts far from the box.
            'label far away': [biopsy + ((72, 618, 84, 630), (300, 620, 'Biopsy'))],
            # The baseline is outside the box's vertical extent.
            'box above the label': [biopsy + ((72, 640, 84, 652), (90, 620, 'Biopsy'))],
        }
        for label, rows in cases.items():
            with self.subTest(label):
                note = FORM_NOTE + ([(90, 630, 'Cold snare polypectomy')] if label.startswith('two lines') else [])
                result = pdf_extract(box_form(rows, note=note), ocr=None)
                self.assertNotIn('☐', result.text)
                self.assertTrue(result.text.endswith('[PDF form fields on page 1]\nCheck Box1: not checked'),
                                result.text)

    def test_boxes_sharing_a_row(self):
        """Round 3 ingest:1 widened this: boxes on one row each write their glyph before their own label; a row
        holding a button that cannot be tied (here a radio button with no option word beside it) gets none."""
        rows = [('Check Box1', 'Biopsy', False, (72, 618, 84, 630), (90, 620, 'Biopsy')),
                ('Check Box2', 'Cold snare', True, (200, 618, 212, 630), (218, 620, 'Cold snare'))]
        result = pdf_extract(box_form(rows), ocr=None)
        self.assertIn('Interventions:\n☐ Biopsy ☒ Cold snare\n', result.text)
        self.assertTrue(result.text.endswith('Check Box1: not checked\nCheck Box2: checked'), result.text)
        radio = pdf_extract(box_form(rows[:1], radio=[('Extent', (200, 618, 212, 630), True)]), ocr=None)
        self.assertNotIn('☐', radio.text)

    def test_rotated_label_is_not_tied(self):
        upright = box_form(BOX_ROWS[:1])
        rotated = upright.replace(b'BT /F1 11 Tf 90 620 Td (Biopsy) Tj ET', b'BT /F1 11 Tf 0 1 -1 0 90 620 Tm (Biopsy) Tj ET')
        self.assertNotEqual(rotated, upright)
        result = pdf_extract(serialise_again(rotated), ocr=None)
        self.assertIn('Biopsy', result.text)
        self.assertNotIn('\u2610', result.text)

    def test_radio_buttons_write_no_glyph(self):
        result = pdf_extract(box_form([], note=FORM_NOTE + [(90, 620, 'Rectosigmoid only')],
                                      radio=[('Extent', (72, 618, 84, 630), True)]), ocr=None)
        self.assertTrue(result.text.endswith('Interventions:\nRectosigmoid only\n\n[PDF form fields on page 1]\n'
                                             'Extent: Yes'), result.text)

    def test_placed_glyphs_are_not_counted_as_read_text(self):
        # Read: 'Biopsy' (6) and 'Check Box1: not checked' (20 non-space characters) = 26; the glyph is not read.
        data = box_form(BOX_ROWS[:1], note=[])
        self.assertEqual(pdf_extract(data, ocr=None, limits=Limits(min_text_chars_per_page=26)).status, 'ok')
        short = pdf_extract(data, ocr=None, limits=Limits(min_text_chars_per_page=27))
        self.assertNotEqual(short.status, 'ok')
        self.assertEqual(short.messages[0], 'Page 1 has no usable text layer and OCR is not available on this server.')

    def test_hidden_box_writes_nothing(self):
        result = pdf_extract(box_form(BOX_ROWS[:1], flags=2), ocr=None)
        self.assertNotIn('☐', result.text)
        self.assertNotIn('[PDF form fields', result.text)

    def test_existing_label_then_box_form_is_unchanged(self):
        from tests.test_repairs_ingest_pdf import FORM_BLOCK, acroform_pdf
        result = pdf_extract(acroform_pdf(), ocr=None)
        self.assertTrue(result.text.endswith('Biopsy taken:\n\n' + FORM_BLOCK), result.text)


# --- ingest:11 — an appearance that is hidden, or draws nothing, is not what the value says --------

HIDDEN_ANNOTATIONS = 'Page 1 has hidden form fields or annotations; their text was not extracted.'
LAYER_NOTE = ('Page 1 has text in a layer that is hidden by default (optional content); that text was not '
              'extracted.')
MISMATCH = ('Page 1: form field "procedure" shows text that differs from its stored value; the stored value was '
            'read, so check it against the original.')
OFF_LAYER = '/OCProperties << /OCGs [30 0 R] /D << /OFF [30 0 R] >> >>'


def patched(data: bytes, replacements, extra: dict[int, bytes] | None = None) -> bytes:
    """``data`` with each (old, new) replaced exactly once and ``extra`` objects added, re-serialised."""
    for old, new in replacements:
        assert data.count(old) == 1, (old, data.count(old))
        data = data.replace(old, new)
    added = b''.join(b'%d 0 obj\n' % number + body + b'\nendobj\n' for number, body in (extra or {}).items())
    cut = data.rindex(b'xref\n')
    return serialise_again(data[:cut] + added + data[cut:])


class AnnotationAppearanceRuleTests(unittest.TestCase):
    """ingest:11 — the annotation reader keeps its own rule: an appearance whose /OC is off draws nothing."""

    def test_freetext_whose_appearance_is_in_an_off_layer_is_not_read(self):
        from tests.test_repairs_ingest_pdf import ADDENDUM, freetext_pdf
        for contents in (ADDENDUM, 'Different stored note: hot snare polypectomy of a 5 mm polyp.'):
            with self.subTest(contents=contents[:20]):
                data = freetext_pdf(contents=contents, catalog=OFF_LAYER.replace('30 0 R', '9 0 R'),
                                    extra_objects={9: b'<< /Type /OCG /Name (Draft) >>'})
                data = patched(data, [(b'/Subtype /Form /BBox [0 0 470 40]', b'/Subtype /Form /OC 9 0 R /BBox [0 0 470 40]')])
                result = pdf_extract(data, ocr=None)
                self.assertNotIn('polypectomy', result.text)
                self.assertNotIn('[PDF annotation', result.text)
                self.assertEqual(result.status, 'ok')
                self.assertIn(HIDDEN_ANNOTATIONS, result.messages)

    def test_freetext_whose_appearance_draws_nothing_is_partial(self):
        from tests.test_repairs_ingest_pdf import ADDENDUM, freetext_pdf
        data = patched(freetext_pdf(), [(b'Tj 0 -13 Td (', b'Tj 0 -13 Td (')], {})  # control: unchanged shape
        self.assertEqual(pdf_extract(data, ocr=None).status, 'ok')
        empty = freetext_pdf(extra_objects={7: stream('', '/Type /XObject /Subtype /Form /BBox [0 0 470 40]')})
        result = pdf_extract(empty, ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertIn(ADDENDUM, result.text)
        self.assertIn('Page 1: a text annotation shows text that differs from its stored text; the stored text was '
                      'read, so check it against the original.', result.messages)

    def test_text_field_whose_appearance_draws_nothing_or_is_hidden_is_partial(self):
        from tests.test_repairs_ingest_pdf import acroform_pdf
        procedure_ap = b'/Tx BMC q BT /Helv 11 Tf 0 g 2 4 Td (Colonoscopy, screening, to the cecum) Tj ET Q EMC'
        cases = {'empty string': acroform_pdf(appearance_override={'procedure': ''}),
                 'bare marked content': patched(acroform_pdf(), [(procedure_ap, b'/Tx BMC EMC')]),
                 'own /OC off': patched(acroform_pdf(), [
                     (b'/Type /Catalog /Pages 2 0 R /AcroForm 10 0 R', b'/Type /Catalog /Pages 2 0 R /AcroForm 10 0 R '
                      + OFF_LAYER.encode()),
                     (b'14 0 obj\n<< /Type /XObject /Subtype /Form', b'14 0 obj\n<< /Type /XObject /Subtype /Form /OC 30 0 R')],
                                       {30: b'<< /Type /OCG /Name (Draft) >>'})}
        for label, data in cases.items():
            with self.subTest(label):
                result = pdf_extract(data, ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertIn('procedure: Colonoscopy, screening, to the cecum', result.text)
                self.assertIn(MISMATCH, result.messages)

    def test_fields_viewers_draw_from_their_values_stay_ok(self):
        from tests.test_repairs_ingest_pdf import FIELDS_NOTE as ROUND1_FIELDS, acroform_pdf
        no_appearance = re.sub(rb' /AP << /N 14 0 R >>', b'', acroform_pdf())
        self.assertNotEqual(no_appearance, acroform_pdf())
        for label, data in (('no /AP', serialise_again(no_appearance)),
                            ('NeedAppearances', acroform_pdf(appearance_override={'procedure': ''},
                                                             need_appearances='true'))):
            with self.subTest(label):
                result = pdf_extract(data, ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (ROUND1_FIELDS,)))
                self.assertIn('procedure: Colonoscopy, screening, to the cecum', result.text)

    def test_stamp_whose_appearance_is_in_an_off_layer_is_named(self):
        from tests.test_repairs_ingest_pdf import freetext_pdf
        data = freetext_pdf(subtype='Stamp', catalog=OFF_LAYER.replace('30 0 R', '9 0 R'),
                            extra_objects={9: b'<< /Type /OCG /Name (Draft) >>'})
        data = patched(data, [(b'/Subtype /Form /BBox [0 0 470 40]', b'/Subtype /Form /OC 9 0 R /BBox [0 0 470 40]')])
        result = pdf_extract(data, ocr=None)
        self.assertNotIn('polypectomy', result.text)
        self.assertEqual((result.status, result.messages), ('ok', (LAYER_NOTE,)))


# --- ingest:12 — a radio group with /Opt reports the option, not its position ------------------------

def radio_form(options: list[str] | None, states: list[str], selected: int | None, label: str = 'Extent reached',
               printed: list[str] | None = None) -> bytes:
    """A radio group, one widget per state, each beside its printed option label."""
    printed = printed or options or states
    lines = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (72, 720, label + ':')]
    lines += [(300, 700 - 20 * index, text) for index, text in enumerate(printed)]
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in lines)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 5: stream(content), 6: ZAPF,
               7: stream('q BT /ZaDb 10 Tf 0 g 1.5 2 Td (l) Tj ET Q', '/Type /XObject /Subtype /Form /BBox [0 0 12 12] '
                         '/Resources << /Font << /ZaDb 6 0 R >> >>'),
               8: stream('', '/Type /XObject /Subtype /Form /BBox [0 0 12 12]')}
    kids = []
    for index, state in enumerate(states):
        number = 20 + index
        shown = f'/{state}' if selected == index else '/Off'
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /Parent 11 0 R /AS {shown} '
                           f'/Rect [280 {698 - 20 * index} 292 {710 - 20 * index}] /F 4 /P 3 0 R '
                           f'/AP << /N << /{state} 7 0 R /Off 8 0 R >> >> >>').encode()
        kids.append(f'{number} 0 R')
    value = f'/{states[selected]}' if selected is not None else '/Off'
    opt = '/Opt [' + ' '.join(f'({esc(option)})' for option in options) + ']' if options else ''
    objects[11] = (f'<< /FT /Btn /Ff 49152 /T (extent) /TU ({esc(label)}) /V {value} {opt} '
                   f'/Kids [{" ".join(kids)}] >>').encode()
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  f'/Contents 5 0 R /Annots [{" ".join(kids)}] >>').encode()
    objects[10] = b'<< /Fields [11 0 R] /NeedAppearances false /DR << /Font << /ZaDb 6 0 R >> >> >>'
    return serialise(objects)


EXTENTS = ['Cecum', 'Hepatic flexure', 'Rectosigmoid only']


class RadioOptionTests(unittest.TestCase):
    """ingest:12 — with /Opt, the selected widget's /Opt entry (by its place in /Kids) is the option."""

    def test_option_texts_are_reported(self):
        result = pdf_extract(radio_form(EXTENTS, ['0', '1', '2'], 2), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertTrue(result.text.endswith('[PDF form fields on page 1]\nExtent reached: Rectosigmoid only'),
                        result.text)

    def test_numeric_option_texts_are_not_read_as_positions(self):
        polyps = ['1', '2', '3', '4 or more']
        pdflib = pdf_extract(radio_form(polyps, ['0', '1', '2', '3'], 2, label='Number of polyps removed'), ocr=None)
        self.assertTrue(pdflib.text.endswith('\nNumber of polyps removed: 3'), pdflib.text)
        named = pdf_extract(radio_form(['1', '2', '3'], ['1', '2', '3'], 0, label='Number of polyps removed'),
                            ocr=None)
        self.assertTrue(named.text.endswith('\nNumber of polyps removed: 1'), named.text)

    def test_named_states_and_no_selection_are_unchanged(self):
        named = pdf_extract(radio_form(None, ['Cecum', 'Hepatic#20flexure', 'Rectosigmoid#20only'], 2,
                                       printed=EXTENTS), ocr=None)
        self.assertTrue(named.text.endswith('\nExtent reached: Rectosigmoid only'), named.text)
        none = pdf_extract(radio_form(EXTENTS, ['0', '1', '2'], None), ocr=None)
        self.assertTrue(none.text.endswith('\nExtent reached: no option selected'), none.text)


# --- ingest:10 — text outside the page box is not what the page shows --------------------------------

SHOWN_LINE = 'Procedure: Colonoscopy cancelled before sedation; patient will reschedule.'
UNSHOWN = 'Colonoscopy completed to the cecum; 7 mm polyp removed with cold snare polypectomy.'
OFF_PAGE = 'Page 1 has text placed outside the visible page area; that text was not extracted.'


def placed_pdf(extra_content: str, *, page_extra: str = '', resources: str = '',
               extra: dict[int, bytes] | None = None) -> bytes:
    content = f'BT /F1 12 Tf 72 720 Td ({esc(SHOWN_LINE)}) Tj ET\n' + extra_content
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] {page_extra} /Resources << /Font << '
                   f'/F1 4 0 R >> {resources} >> /Contents 5 0 R >>').encode(),
               4: HELVETICA, 5: stream(content)}
    objects.update(extra or {})
    return serialise(objects)


class OffPageTextTests(unittest.TestCase):
    """ingest:10 — text wholly outside the visible page box (crop within media) is excluded and named."""

    def test_text_a_viewer_does_not_show_is_excluded_and_named(self):
        cases = {'right of the page': f'BT /F1 12 Tf 700 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'below the page': f'BT /F1 12 Tf 72 -40 Td ({esc(UNSHOWN)}) Tj ET',
                 'moved off by cm': f'q 1 0 0 1 700 0 cm BT /F1 12 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET Q',
                 'left of the page': '\n'.join(f'BT /F1 12 Tf -900 {500 - 14 * n} Td ({esc(part)}) Tj ET'
                                               for n, part in enumerate(UNSHOWN.split('; ')))}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (OFF_PAGE,)))
                self.assertEqual(result.text.strip(), SHOWN_LINE)
        cropped = pdf_extract(placed_pdf(f'BT /F1 12 Tf 72 50 Td ({esc(UNSHOWN)}) Tj ET',
                                         page_extra='/CropBox [0 100 612 792]'), ocr=None)
        self.assertEqual((cropped.status, cropped.messages, cropped.text.strip()), ('ok', (OFF_PAGE,), SHOWN_LINE))

    def test_later_text_on_an_off_page_line_is_excluded_too(self):
        content = f'BT /F1 12 Tf 72 500 Td (Visible note.) Tj 700 0 Td ({esc(UNSHOWN)}) Tj ET'
        result = pdf_extract(placed_pdf(content), ocr=None)
        self.assertEqual(result.messages, (OFF_PAGE,))
        self.assertNotIn('cold snare', result.text)
        self.assertIn('Visible note.', result.text)

    def test_text_pushed_past_the_edge_by_the_text_before_it_is_excluded(self):
        lead = 'Findings: a long visible sentence that runs right up to the edge'
        start = 612 + 30 - stringWidth(lead, 'Helvetica', 12)  # the second piece starts 30 pt past the edge
        content = f'BT /F1 12 Tf {start:.2f} 500 Td ({esc(lead)}) Tj ({esc(UNSHOWN)}) Tj ET'
        result = pdf_extract(placed_pdf(content), ocr=None)
        self.assertEqual(result.messages, (OFF_PAGE,))
        self.assertIn(lead, result.text)
        self.assertNotIn('cold snare', result.text)

    def test_text_after_a_long_lead_on_the_same_line_is_still_read(self):
        # The lead is measured with its font's own widths (about 330 pt here), so the next piece starts on the page.
        # One em per glyph, the estimate for a font that cannot be measured, would start it past the right edge.
        lead = 'Findings: the mucosa of the whole colon looked normal today ok.'
        content = f'BT /F1 12 Tf 72 500 Td ({esc(lead)}) Tj ({esc(UNSHOWN)}) Tj ET'
        result = pdf_extract(placed_pdf(content), ocr=None)
        self.assertEqual(result.messages, ())
        self.assertIn(lead, result.text)
        self.assertIn('cold snare', result.text)

    def test_text_state_is_restored_by_q(self):
        content = f'/F1 12 Tf q /F1 400 Tf Q BT 72 -30 Td ({esc(UNSHOWN)}) Tj ET'
        result = pdf_extract(placed_pdf(content), ocr=None)
        self.assertEqual((result.messages, result.text.strip()), ((OFF_PAGE,), SHOWN_LINE))

    def test_form_placed_off_the_page_is_excluded(self):
        form = stream(f'BT /F1 12 Tf 0 10 Td ({esc(UNSHOWN)}) Tj ET',
                      '/Type /XObject /Subtype /Form /BBox [0 0 500 30] /Resources << /Font << /F1 4 0 R >> >>')
        result = pdf_extract(placed_pdf('q 1 0 0 1 700 400 cm /Fx Do Q', resources='/XObject << /Fx 6 0 R >>',
                                        extra={6: form}), ocr=None)
        self.assertEqual((result.status, result.messages, result.text.strip()), ('ok', (OFF_PAGE,), SHOWN_LINE))
        shown = pdf_extract(placed_pdf('q 1 0 0 1 72 400 cm /Fx Do Q', resources='/XObject << /Fx 6 0 R >>',
                                       extra={6: form}), ocr=None)
        self.assertEqual((shown.status, shown.messages), ('ok', ()))
        self.assertIn('cold snare', shown.text)

    def test_text_a_viewer_shows_is_still_read(self):
        cases = {'on the page': f'BT /F1 12 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'starts inside, runs past the edge': f'BT /F1 12 Tf 400 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'starts left of the page, runs into it': f'BT /F1 12 Tf -60 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'invisible OCR layer on the page': f'BT 3 Tr /F1 12 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'just inside the top edge': f'BT /F1 12 Tf 72 785 Td ({esc(UNSHOWN)}) Tj ET',
                 'rotated, on the page': f'BT /F1 12 Tf 0 1 -1 0 300 200 Tm ({esc(UNSHOWN)}) Tj ET',
                 # A TJ adjustment moves the next glyphs left: this one brings the sentence back onto the page.
                 'kerned back onto the page': f'BT /F1 12 Tf 700 450 Td [(x) 60000 ({esc(UNSHOWN)})] TJ ET'}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)

    # Round 3 evidence:1 — every tracked text-state parameter is pinned: ignoring one of them would read text a
    # viewer does not show, or drop text it does.
    TRACKED_LEAD = ('Procedure: Colonoscopy with cold snare polypectomy of the 7 mm sigmoid polyp and cold '
                    'forceps biopsy of the ascending colon')
    TRACKED_TAIL = ' - cancelled before sedation; the patient will reschedule.'

    def test_condensed_and_tightened_lines_keep_their_visible_tail(self):
        lead, tail = self.TRACKED_LEAD, self.TRACKED_TAIL
        natural = stringWidth(lead, 'Helvetica', 11)
        cases = {'50 Tz': ('50 Tz 60 690 Td', natural / 2),
                 '-1.5 Tc': ('-1.5 Tc 60 690 Td', natural - 1.5 * len(lead)),
                 '-6 Tw': ('-6 Tw 60 690 Td', natural - 6 * lead.count(' '))}
        for label, (state, measured) in cases.items():
            with self.subTest(label):
                # Measured as a viewer measures it the tail starts on the page; at the natural width, past its edge.
                self.assertLess(60 + measured, 612 - 11)
                self.assertGreater(60 + natural, 612 + 11)
                result = pdf_extract(placed_pdf(f'BT /F1 11 Tf {state} ({esc(lead)}) Tj ({esc(tail)}) Tj ET'),
                                     ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cancelled before sedation', result.text)

    def test_text_moved_below_the_page_by_the_leading_is_excluded(self):
        cases = {'T*': f'BT /F1 12 Tf 14 TL 72 40 Td T* T* T* T* T* ({esc(UNSHOWN)}) Tj ET',
                 "'": f"BT /F1 12 Tf 14 TL 72 40 Td T* T* T* T* ({esc(UNSHOWN)}) ' ET",
                 '"': f'BT /F1 12 Tf 14 TL 72 40 Td T* T* T* T* 0 0 ({esc(UNSHOWN)}) " ET',
                 'TD sets the leading': f'BT /F1 12 Tf 72 54 Td 0 -14 TD T* T* T* T* T* ({esc(UNSHOWN)}) Tj ET',
                 'a rise below the page': f'BT /F1 12 Tf -60 Ts 72 30 Td ({esc(UNSHOWN)}) Tj ET'}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages, result.text.strip()), ('ok', (OFF_PAGE,), SHOWN_LINE))
        # The controls: the same leading and rise leave the sentence on the page.
        for content in (f'BT /F1 12 Tf 14 TL 72 140 Td T* T* T* T* T* ({esc(UNSHOWN)}) Tj ET',
                        f'BT /F1 12 Tf 60 Ts 72 -30 Td ({esc(UNSHOWN)}) Tj ET'):
            with self.subTest(content[:40]):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)

    def test_text_in_a_form_is_judged_where_the_form_is_placed(self):
        # In the form's own space the sentence lies far left of x=0; the form is placed so that it shows.
        form = stream(f'BT /F1 12 Tf -1000 10 Td ({esc(UNSHOWN)}) Tj ET',
                      '/Type /XObject /Subtype /Form /BBox [-1100 0 0 30] /Resources << /Font << /F1 4 0 R >> >>')
        result = pdf_extract(placed_pdf('q 1 0 0 1 1100 400 cm /Fx Do Q', resources='/XObject << /Fx 6 0 R >>',
                                        extra={6: form}), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn('cold snare polypectomy', result.text)

    def test_ocr_renders_the_area_a_viewer_shows(self):
        from unittest import mock

        from studio.ingest import ocr
        calls = []

        def fake_run(name, argv, deadline, timeout_s):
            calls.append(argv)
            if name == 'pdftoppm':
                with open(argv[-1] + '.png', 'wb') as handle:
                    handle.write(b'page')
                return b''
            return b'Synthetic OCR text.'

        with mock.patch.object(ocr, '_run', side_effect=fake_run):
            outcome = ocr.ocr_page(ocr.OcrTools('/bin/true', '/bin/true', 'tesseract 0', 'pdftoppm 0'),
                                   'document.pdf', 1, dpi=300, timeout_s=10,
                                   workdir=tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.assertEqual(outcome.text, 'Synthetic OCR text.')
        self.assertIn('-cropbox', calls[0])


# --- ingest:3 — a short note typed over a full-page image is kept, never "No text could be read" ------

LETTERHEAD_NOTE = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Date of service: 2026-10-21',
                   'Office visit: colonoscopy reviewed with patient.', 'Dr. A. Rahman (fictional)']
SCAN_NOTE = ('Page {n} is mostly covered by an image and has only a short text layer (for example a stamp or a fax '
             'header), so it may be a scan; OCR is not available on this server, so the image was not read.')
LARGE_IMAGE = ('Page 1 combines a text layer with a large image; only the text layer was read, so check the text '
               'against the original if the image holds text.')
DRAWN = ('Page 1 has handwriting, drawings or stamps added as PDF annotations; they are not text, so check the '
         'original.')


def letterhead_page(lines=LETTERHEAD_NOTE, pixels=(1275, 1650)) -> bytes:
    """A full-page letterhead bitmap (header band, logo disc, footer band; no text) under a typed note."""
    image = Image.new('RGB', pixels, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, pixels[0], pixels[1] // 10), fill=(20, 40, 110))
    draw.ellipse((pixels[0] - 260, 30, pixels[0] - 60, 230), fill=(200, 200, 230))
    draw.rectangle((0, pixels[1] - pixels[1] // 16, pixels[0], pixels[1]), fill=(160, 160, 160))
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter, invariant=1)
    canvas.drawImage(ImageReader(image), 0, 0, width=612, height=792)
    canvas.setFont('Helvetica', 11)
    for number, line in enumerate(lines):
        canvas.drawString(72, 640 - 16 * number, line)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


class ShortNoteOverImageTests(unittest.TestCase):
    """ingest:3 — an unread scan-candidate page keeps its text layer; the result is partial, never failed."""

    def test_letterhead_note_without_ocr_is_partial_with_its_text(self):
        result = pdf_extract(letterhead_page(), ocr=None)
        self.assertEqual((result.status, result.method), ('partial', 'pdf-text'))
        self.assertEqual(result.text.strip(), '\n'.join(LETTERHEAD_NOTE))
        self.assertEqual(result.messages, (SCAN_NOTE.format(n=1),))

    def test_letterhead_note_whose_ocr_fails_is_partial_with_its_text(self):
        with FakeOcr(recognise='exit 3') as fake:
            result = pdf_extract(letterhead_page(), ocr=fake.tools)
        self.assertEqual((result.status, result.method, result.ocr_pages), ('partial', 'pdf-text', ()))
        self.assertEqual(result.text.strip(), '\n'.join(LETTERHEAD_NOTE))
        self.assertEqual(result.messages, ('Page 1 is mostly covered by an image and has only a short text layer, and '
                                           'OCR could not read it (tesseract exited with status 3).',))

    def test_two_short_letterhead_pages_keep_both_texts(self):
        data = docgen.concat_pdfs([letterhead_page(), letterhead_page(['Signature: Dr. A. Rahman (fictional)'])])
        result = pdf_extract(data, ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertEqual([text.strip() for text in page_texts(result)],
                         ['\n'.join(LETTERHEAD_NOTE), 'Signature: Dr. A. Rahman (fictional)'])
        self.assertEqual(result.messages, ('Pages 1-2 are mostly covered by an image and have only a short text layer '
                                           '(for example a stamp or a fax header), so they may be scans; OCR is not '
                                           'available on this server, so the images were not read.',))

    def test_round_one_protections_hold(self):
        with FakeOcr() as fake:
            read = pdf_extract(letterhead_page(), ocr=fake.tools)  # the contract: a short layer over an image is OCRed
        self.assertEqual((read.status, read.method, read.ocr_pages), ('ok', 'pdf-ocr', (1,)))
        long_note = LETTERHEAD_NOTE + ['Findings: ' + 'reflux symptoms reviewed in detail with the patient. ' * 5]
        typed = pdf_extract(letterhead_page(long_note), ocr=None)
        self.assertEqual((typed.status, typed.messages), ('ok', (LARGE_IMAGE,)))
        blank = pdf_extract(letterhead_page([]), ocr=None)
        self.assertEqual((blank.status, blank.text), ('failed', ''))


# --- ingest:6 — images an annotation's appearance paints are content too ------------------------------

FAX_LINES = [(72, 760, 'SYNTHETIC TEST DOCUMENT - fictional patient - NOT FOR BILLING'),
             (36, 778, 'Received via secure e-fax 2026-10-21 14:32 UTC - Page 1 of 1')]


def image_object(pixels=(1200, 1500)) -> bytes:
    data = zlib.compress(b'\xff' * (pixels[0] * pixels[1]))
    return (b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray /BitsPerComponent 8 '
            b'/Filter /FlateDecode /Length %d >>\nstream\n' % (pixels[0], pixels[1], len(data)) + data + b'\nendstream')


def annotated_image_pdf(annotation: str, *, rect=(36, 58, 576, 733), pixels=(1200, 1500),
                        in_content: bool = False) -> bytes:
    """A banner and a fax stamp; an image painted over ``rect`` by an annotation's appearance (or the content)."""
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    content = '\n'.join(f'BT /F1 8 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in FAX_LINES)
    resources = ''
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 9: image_object(pixels)}
    annots = ''
    if in_content:
        content += f'\nq {width} 0 0 {height} {rect[0]} {rect[1]} cm /Im0 Do Q'
        resources = '/XObject << /Im0 9 0 R >>'
    else:
        objects[8] = stream(f'q {width} 0 0 {height} 0 0 cm /Im0 Do Q', f'/Type /XObject /Subtype /Form /BBox [0 0 '
                            f'{width} {height}] /Resources << /XObject << /Im0 9 0 R >> >>')
        objects[7] = (f'<< /Type /Annot {annotation} /Rect [{rect[0]} {rect[1]} {rect[2]} {rect[3]}] /F 4 /P 3 0 R '
                      '/AP << /N 8 0 R >> >>').encode()
        annots = '/Annots [7 0 R]'
        if '/Widget' in annotation:
            objects[1] = b'<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [7 0 R] >> >>'
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> '
                  f'{resources} >> /Contents 5 0 R {annots} >>').encode()
    objects[5] = stream(content)
    return serialise(objects)


IMAGE_FIELD = '/Subtype /Widget /FT /Btn /Ff 65536 /T (photo) /MK << /TP 1 /I 8 0 R >>'
ANNOTATED = {'push-button image field': IMAGE_FIELD, 'square': '/Subtype /Square',
             'screen': '/Subtype /Screen', 'watermark': '/Subtype /Watermark'}


class AnnotationImageTests(unittest.TestCase):
    """ingest:6 — an image an annotation paints counts as drawn and towards the page's scan coverage."""

    def test_scan_painted_by_an_annotation_is_treated_like_a_page_scan(self):
        control = pdf_extract(annotated_image_pdf('', in_content=True), ocr=None)
        self.assertEqual((control.status, control.messages), ('partial', (SCAN_NOTE.format(n=1),)))
        for label, annotation in ANNOTATED.items():
            with self.subTest(label):
                result = pdf_extract(annotated_image_pdf(annotation), ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertEqual(result.messages[0], SCAN_NOTE.format(n=1))
                self.assertIn(DRAWN, result.messages)
                with FakeOcr() as fake:
                    read = pdf_extract(annotated_image_pdf(annotation), ocr=fake.tools)
                self.assertEqual((read.method, read.ocr_pages), ('pdf-ocr', (1,)))

    def test_small_image_field_is_named(self):
        result = pdf_extract(annotated_image_pdf(IMAGE_FIELD, rect=(72, 400, 216, 580), pixels=(300, 375)), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertIn(DRAWN, result.messages)

    def test_appearance_is_placed_on_its_rectangle(self):
        # A 540 x 675 appearance shown in a 144 x 180 pt field (PDF 32000-1 12.5.5): about 5% of the page, so
        # not a scan; its 1.8-megapixel image still gets the large-image note.
        data = annotated_image_pdf(IMAGE_FIELD).replace(b'/Rect [36 58 576 733]', b'/Rect [72 400 216 580]')
        result = pdf_extract(serialise_again(data), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (LARGE_IMAGE, DRAWN)))

    def test_cut_scan_painted_by_an_annotation_is_damaged_on_an_ocr_page(self):
        # Round 3 evidence:2 — an annotation's images are integrity-checked like the page's own on an OCR page.
        full = image_object()
        data = zlib.compress(b'\xff' * (1200 * 1500))
        cut = data[:len(data) * 6 // 10]
        short = full.replace(b'/Length %d >>' % len(data), b'/Length %d >>' % len(cut)).replace(data, cut)
        self.assertNotEqual(short, full)
        for label, annotation in (('push-button image field', IMAGE_FIELD), ('square', '/Subtype /Square'),
                                  ('stamp', '/Subtype /Stamp')):
            with self.subTest(label):
                intact = annotated_image_pdf(annotation)
                damaged = patched(intact, [(full, short)])
                with FakeOcr() as fake:
                    whole = pdf_extract(intact, ocr=fake.tools)
                    read = pdf_extract(damaged, ocr=fake.tools)
                self.assertEqual((whole.status, whole.method, whole.ocr_pages), ('ok', 'pdf-ocr', (1,)))
                self.assertNotIn(DAMAGED_PAGE.format(n=1), whole.messages)
                self.assertEqual((read.status, read.method, read.ocr_pages), ('partial', 'pdf-ocr', (1,)))
                self.assertIn(DAMAGED_PAGE.format(n=1), read.messages)

    def test_hidden_annotation_image_is_not_counted(self):
        result = pdf_extract(annotated_image_pdf('/Subtype /Square').replace(b'/F 4 /P 3 0 R', b'/F 2 /P 3 0 R'),
                             ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertNotIn(DRAWN, result.messages)


# --- ingest:7 — a scanned insert under half the page beside a short typed header is named -------------

INSERT_HEADER = ['SYNTHETIC TEST DOCUMENT - fictional patient', 'Endoscopy unit (fictional)',
                 'Date of service: 2026-10-21', 'See the scanned procedure record below.']


def insert_pdf(pixels, placed) -> bytes:
    content = '\n'.join(f'BT /F1 11 Tf 72 {740 - 16 * n} Td ({esc(line)}) Tj ET' for n, line in enumerate(INSERT_HEADER))
    content += '\nq {} 0 0 {} {} {} cm /Im0 Do Q'.format(placed[2], placed[3], placed[0], placed[1])
    return serialise({1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                      3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> '
                          b'/XObject << /Im0 6 0 R >> >> /Contents 5 0 R >>'),
                      4: HELVETICA, 5: stream(content), 6: image_object(pixels)})


class PartialPageInsertTests(unittest.TestCase):
    """ingest:7 — a dense image over a fifth of the page or more is named beside a text layer."""

    def test_inserts_under_one_megapixel_and_half_the_page_are_named(self):
        for label, pixels, placed in (('150 dpi insert, 45% of the page', (1275, 750), (0, 300, 612, 360)),
                                      ('96 dpi screenshot, 49% of the page', (816, 522), (0, 250, 612, 391))):
            with self.subTest(label):
                result = pdf_extract(insert_pdf(pixels, placed), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (LARGE_IMAGE,)))
                self.assertEqual(result.text.strip(), '\n'.join(INSERT_HEADER))

    def test_the_note_starts_at_a_fifth_of_the_page(self):
        # Round 3 evidence:5 — dense 150 dpi inserts under one megapixel just either side of 20%, and one at 30%.
        for label, pixels, placed, expected in (('20.12% of the page', (1275, 332), (0, 300, 612, 159.36), (LARGE_IMAGE,)),
                                                ('19.88% of the page', (1275, 328), (0, 300, 612, 157.44), ()),
                                                ('30.12% of the page', (1275, 497), (0, 300, 612, 238.56), (LARGE_IMAGE,))):
            with self.subTest(label):
                result = pdf_extract(insert_pdf(pixels, placed), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', expected))
                self.assertEqual(result.text.strip(), '\n'.join(INSERT_HEADER))


# --- ingest:4 — every encoding a page's text depends on must be seen to end ------------------------

DAMAGED_PAGE = ('Page {n} is damaged: part of its content could not be decoded, so its text may be incomplete or '
                'wrong.')
UNCHECKED_IMAGE = ('Page 1 was read with OCR, but its image could not be checked for completeness, so its text may '
                   'be incomplete.')
OCR_READ = 'Page 1 was read with OCR; OCR can misread characters — check evidence against the original.'


def in_process(data: bytes, tools=None):
    from studio.ingest.pdf import extract_pdf
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as workdir:
        return extract_pdf(data, Limits(), tools, time.monotonic() + 120, workdir)


def run_length(data: bytes) -> bytes:
    """A RunLengthDecode encoding of ``data``: literal runs of up to 128 bytes, then the EOD byte."""
    out = bytearray()
    for start in range(0, len(data), 128):
        piece = data[start:start + 128]
        out += bytes([len(piece) - 1]) + piece
    return bytes(out + b'\x80')


def two_page_pdf(filter_name: str, page2_stream: bytes) -> bytes:
    """The round-1 two-page shape; page 2's content is ``page2_stream`` under ``filter_name``."""
    from tests.test_repairs_ingest_pdf import PAGE1_LINES, page_content
    first = page_content(PAGE1_LINES)
    page = ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> '
            '/Contents {} 0 R >>')
    return serialise({1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
                      3: page.format(5).encode(), 4: page.format(6).encode(),
                      5: b'<< /Length %d >>\nstream\n' % len(first) + first + b'\nendstream',
                      6: (b'<< /Length %d /Filter /%s >>\nstream\n' % (len(page2_stream), filter_name.encode())
                          + page2_stream + b'\nendstream'),
                      7: HELVETICA})


def image_page(image_dict: str, data: bytes) -> bytes:
    """One image-only page (no text layer, so it is read with OCR): ``data`` drawn over the whole page."""
    return serialise({1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                      3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im0 4 0 R '
                          b'>> >> /Contents 5 0 R >>'),
                      4: f'<< /Type /XObject /Subtype /Image {image_dict} /Length {len(data)} >>\nstream\n'.encode()
                         + data + b'\nendstream',
                      5: stream('q 612 0 0 792 0 0 cm /Im0 Do Q')})


def fax_strip(compression: str, size=(1728, 2200)) -> bytes:
    """One CCITT strip, as libtiff writes it (Group 4 ends with EOFB, Group 3 with RTC)."""
    image = Image.new('1', size, 1)
    draw = ImageDraw.Draw(image)
    for row in range(40, size[1] - 40, 60):
        for column in range(60, size[0] - 200, 180):
            draw.rectangle((column, row, column + 120, row + 18), fill=0)
    from PIL import TiffImagePlugin
    saved, TiffImagePlugin.STRIP_SIZE = TiffImagePlugin.STRIP_SIZE, 1 << 30
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='TIFF', compression=compression)
    finally:
        TiffImagePlugin.STRIP_SIZE = saved
    tiff = Image.open(io.BytesIO(buffer.getvalue()))
    (offset,), (count,) = tiff.tag_v2[273], tiff.tag_v2[279]
    return buffer.getvalue()[offset:offset + count]


def jbig2_segment(number: int, kind: int, data: bytes, length: int | None = None) -> bytes:
    """A JBIG2 segment: header (no referred-to segments, 1-byte page association) and data."""
    declared = len(data) if length is None else length
    return (number.to_bytes(4, 'big') + bytes([kind, 0x00, 0x01]) + declared.to_bytes(4, 'big') + data)


JBIG2 = (jbig2_segment(0, 48, (1728).to_bytes(4, 'big') + (2200).to_bytes(4, 'big') + bytes(11))
         + jbig2_segment(1, 38, bytes(range(256)) * 40))


class StrictDecodingTests(unittest.TestCase):
    """ingest:4 — LZW and RunLength text streams, and CCITT, JBIG2 and JPEG 2000 images on OCR pages."""

    def test_lzw_content_stream_cut_anywhere_is_reported(self):
        from pypdf._codecs._codecs import LzwCodec
        from tests.test_repairs_ingest_pdf import PAGE2_LINES, page_content
        whole = LzwCodec().encode(page_content(PAGE2_LINES))
        intact = in_process(two_page_pdf('LZWDecode', whole))
        self.assertEqual((intact.status, intact.messages), ('ok', ()))
        self.assertIn('Retroflexion in the rectum performed', intact.text)
        for cut in range(1, len(whole)):
            with self.subTest(cut=cut):
                result = in_process(two_page_pdf('LZWDecode', whole[:cut]))
                self.assertNotEqual(result.status, 'ok')
                self.assertTrue(any(message.startswith('Page 2') for message in result.messages), result.messages)
        for keep in range(1, len(whole), 7):
            with self.subTest(zero_filled_from=keep):
                result = in_process(two_page_pdf('LZWDecode', whole[:keep] + bytes(len(whole) - keep)))
                self.assertIn(DAMAGED_PAGE.format(n=2), result.messages)
        through_child = pdf_extract(two_page_pdf('LZWDecode', whole[:128]), ocr=None)
        self.assertEqual(through_child.status, 'partial')
        self.assertIn(DAMAGED_PAGE.format(n=2), through_child.messages)

    def test_lzw_stream_without_an_initial_clear_code_is_whole(self):
        # pypdf's encoder starts with a clear-table code; a stream may also start without one. The table fills
        # past 511 entries here, so the code width grows exactly where the encoder's does.
        from pypdf._codecs._codecs import LzwCodec
        from tests.test_repairs_ingest_pdf import PAGE2_LINES, page_content
        content = page_content(PAGE2_LINES * 3)
        whole = LzwCodec().encode(content)
        bits = ''.join(f'{byte:08b}' for byte in whole)
        self.assertEqual(bits[:9], f'{256:09b}')
        rest = bits[9:] + '0' * (-len(bits[9:]) % 8)
        unclear = int(rest, 2).to_bytes(len(rest) // 8, 'big')
        self.assertEqual(LzwCodec().decode(unclear), content)
        result = in_process(two_page_pdf('LZWDecode', unclear))
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_lzw_code_the_table_does_not_hold_is_reported(self):
        def packed(codes):  # 9-bit codes, most significant bit first, as LZWDecode reads them
            bits = ''.join(f'{code:09b}' for code in codes)
            bits += '0' * (-len(bits) % 8)
            return int(bits, 2).to_bytes(len(bits) // 8, 'big')

        text = [ord(char) for char in 'BT /F1 11 Tf 72 720 Td (Cold snare polypectomy.) Tj ET']
        self.assertEqual(in_process(two_page_pdf('LZWDecode', packed([256] + text + [257]))).status, 'ok')
        result = in_process(two_page_pdf('LZWDecode', packed([256] + text[:20] + [400] + text[20:] + [257])))
        self.assertIn(DAMAGED_PAGE.format(n=2), result.messages)

    def test_cut_run_length_scan_read_with_ocr_is_damaged(self):
        pixels = bytes(range(256)) * (850 * 1100 // 256 + 1)
        whole = run_length(pixels[:850 * 1100])
        image = '/Width 850 /Height 1100 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /RunLengthDecode'
        self.assertEqual(self.ocr(image_page(image, whole)).messages, (OCR_READ,))
        for label, data in (('cut inside a run', whole[:len(whole) // 2]), ('only its end-of-data byte cut', whole[:-1])):
            with self.subTest(label):
                result = self.ocr(image_page(image, data))
                self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, DAMAGED_PAGE.format(n=1))))

    def test_run_length_content_stream_cut_is_reported(self):
        from tests.test_repairs_ingest_pdf import PAGE2_LINES, page_content
        whole = run_length(page_content(PAGE2_LINES))
        self.assertEqual(in_process(two_page_pdf('RunLengthDecode', whole)).status, 'ok')
        for cut in range(1, len(whole), 5):
            with self.subTest(cut=cut):
                self.assertNotEqual(in_process(two_page_pdf('RunLengthDecode', whole[:cut])).status, 'ok')

    def ocr(self, data: bytes):
        with FakeOcr() as fake:
            return pdf_extract(data, ocr=fake.tools)

    def test_cut_fax_scan_read_with_ocr_is_damaged(self):
        for compression, k in (('group4', -1), ('group3', 0)):
            strip = fax_strip(compression)
            image = f'/Width 1728 /Height 2200 /BitsPerComponent 1 /ImageMask false /ColorSpace /DeviceGray ' \
                    f'/Filter /CCITTFaxDecode /DecodeParms << /K {k} /Columns 1728 /Rows 2200 >>'
            with self.subTest(compression):
                whole = self.ocr(image_page(image, strip))
                self.assertEqual((whole.status, whole.method, whole.messages), ('ok', 'pdf-ocr', (OCR_READ,)))
                # Group 4 ends with EOFB, so any cut shows; Group 3 is checked by its EOL codes (one per row), so a
                # cut inside the very last row (at most one pixel row) cannot be seen: cut a few rows instead.
                end_cut = strip[:-3] if k < 0 else strip[:-200]
                for label, data in (('cut to a third', strip[:len(strip) // 3]),
                                    ('zero-filled from a third', strip[:len(strip) // 3]
                                     + bytes(len(strip) - len(strip) // 3)),
                                    ('end cut', end_cut)):
                    with self.subTest(label):
                        result = self.ocr(image_page(image, data))
                        self.assertEqual((result.status, result.messages), ('partial', (OCR_READ,
                                                                                        DAMAGED_PAGE.format(n=1))))

    def test_fax_scan_without_end_of_block_cannot_be_checked(self):
        image = ('/Width 1728 /Height 2200 /BitsPerComponent 1 /ColorSpace /DeviceGray /Filter /CCITTFaxDecode '
                 '/DecodeParms << /K -1 /Columns 1728 /Rows 2200 /EndOfBlock false >>')
        result = self.ocr(image_page(image, fax_strip('group4')))
        self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, UNCHECKED_IMAGE)))

    def test_cut_jbig2_scan_read_with_ocr_is_damaged(self):
        image = '/Width 1728 /Height 2200 /BitsPerComponent 1 /ColorSpace /DeviceGray /Filter /JBIG2Decode'
        self.assertEqual(self.ocr(image_page(image, JBIG2)).messages, (OCR_READ,))
        for cut in (len(JBIG2) // 3, len(JBIG2) - 1, 20):
            with self.subTest(cut=cut):
                result = self.ocr(image_page(image, JBIG2[:cut]))
                self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, DAMAGED_PAGE.format(n=1))))
        unknown = JBIG2[:30] + jbig2_segment(1, 38, bytes(64), length=0xFFFFFFFF)
        result = self.ocr(image_page(image, JBIG2[:30] + unknown[30:]))
        self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, UNCHECKED_IMAGE)))

    def test_cut_jpeg_2000_scan_read_with_ocr_is_damaged(self):
        buffer = io.BytesIO()
        Image.new('L', (850, 1100), 255).save(buffer, format='JPEG2000')
        jp2 = buffer.getvalue()
        image = '/Width 850 /Height 1100 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /JPXDecode'
        self.assertEqual(self.ocr(image_page(image, jp2)).messages, (OCR_READ,))
        for label, data in (('cut by a third', jp2[:len(jp2) * 2 // 3]), ('end marker cut', jp2[:-2])):
            with self.subTest(label):
                result = self.ocr(image_page(image, data))
                self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, DAMAGED_PAGE.format(n=1))))


# --- ingest:9 — a large lossless scan that decodes completely is not damaged --------------------------

class LargeLosslessScanTests(unittest.TestCase):
    """ingest:9 — past 75 MB decoded, an OCR image is still checked to its end, not called damaged."""

    def test_intact_scan_over_75_mb_is_ok_and_a_cut_one_is_damaged(self):
        width, height = 5000, 5001  # RGB: 75,015,000 bytes decoded
        row = (b'\xff' * 3 * 400 + b'\x00' * 3 * 100) * (width // 500)
        whole = zlib.compress(row * height, 6)
        image = f'/Width {width} /Height {height} /BitsPerComponent 8 /ColorSpace /DeviceRGB /Filter /FlateDecode'
        with FakeOcr() as fake:
            intact = pdf_extract(image_page(image, whole), ocr=fake.tools)
            cut = pdf_extract(image_page(image, whole[:len(whole) * 6 // 10]), ocr=fake.tools)
        self.assertEqual((intact.status, intact.method, intact.messages), ('ok', 'pdf-ocr', (OCR_READ,)))
        self.assertEqual((cut.status, cut.messages), ('partial', (OCR_READ, DAMAGED_PAGE.format(n=1))))

    def test_image_that_inflates_far_past_its_size_cannot_be_checked(self):
        bomb = zlib.compress(bytes(200 * 1024 * 1024), 9)  # 200 MiB of zeros for a 100 x 100 image
        image = '/Width 100 /Height 100 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /FlateDecode'
        with FakeOcr() as fake:
            result = pdf_extract(image_page(image, bomb), ocr=fake.tools)
        self.assertEqual((result.status, result.messages), ('partial', (OCR_READ, UNCHECKED_IMAGE)))


# --- ingest:5 — harmless bytes after %%EOF are padding, not an unfinished update -----------------------

UNFINISHED = ('The PDF is incomplete: it ends with data after its last end-of-file marker, such as an unfinished '
              'update. Upload the complete file.')
UNANCHORED = ('The PDF is incomplete: its last revision has no cross-reference pointer (startxref), so only an '
              'earlier revision could be read. Upload the complete file.')


class TrailingBytesTests(unittest.TestCase):
    """ingest:5 — a complete PDF with a repeated %%EOF, a DOS Ctrl-Z or a trailing comment reads as before."""

    def test_harmless_tails_are_accepted(self):
        whole = docgen.make_pdf(['Colonoscopy report. Date of service: 2026-10-21. Cecum reached.',
                                 'Findings: 5 mm sigmoid polyp removed with cold snare.'])
        self.assertTrue(whole.endswith(b'%%EOF\n'))
        tails = {'a repeated end marker': b'%%EOF\n', 'a repeated end marker, CRLF': b'%%EOF\r\n',
                 'a DOS end-of-file byte': b'\x1a', 'Ctrl-Z padding to 128 bytes': b'\x1a' * 97,
                 'a trailing comment': b'% end of document\n', 'a comment and a marker': b'% end\r\n%%EOF\r\n',
                 'markers and NUL padding': b'%%EOF\n\x00\x00%%EOF\n'}
        for label, tail in tails.items():
            with self.subTest(label):
                result = pdf_extract(whole + tail, ocr=None)
                self.assertEqual((result.status, len(result.pages), result.messages), ('ok', 2, ()))
                self.assertIn('cold snare', result.text)

    def test_cut_updates_are_still_refused(self):
        from tests.test_repairs_ingest_pdf import PROCEDURE, VISIT, add_page_update, revision1
        rev1, xref1 = revision1(VISIT)
        full = add_page_update(rev1, xref1, PROCEDURE)
        cut = full[:full.rindex(b'startxref')]
        cases = {'inside the update': (full[:-40], UNFINISHED),
                 'inside the update, then a comment': (full[:-40] + b'\n% end\n', UNFINISHED),
                 'inside the update, then Ctrl-Z': (full[:-40] + b'\x1a', UNFINISHED),
                 'before its startxref, then repeated markers': (cut + b'%%EOF\n%%EOF\n', UNANCHORED),
                 'before its startxref, a marker and a comment': (cut + b'%%EOF\n% end\n', UNANCHORED)}
        for label, (data, message) in cases.items():
            with self.subTest(label):
                result = pdf_extract(data, ocr=None)
                self.assertEqual((result.status, result.messages), ('failed', (message,)))


# --- ingest:8 — Acrobat's own display formatting is not a disagreement --------------------------------

FIELD_ROWS = {'withdrawal': (200, 640), 'bbps': (200, 610), 'dos': (200, 580), 'amount': (200, 550),
              'share': (200, 520), 'phone': (200, 490)}


def formatted_form(fields, *, broken: tuple = ()) -> bytes:
    """Text widgets: (name, stored /V, appearance text, format script or None), as Acrobat or pdf.js save them.
    The appearances of the fields named in ``broken`` are Flate streams cut short."""
    lines = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'),
             (72, 700, 'Colonoscopy quality measures')] + [(72, FIELD_ROWS[name][1] + 4, name + ':')
                                                            for name, *_ in fields]
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in lines)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA, 5: stream(content)}
    widgets, number = [], 11
    for name, stored, shown, script in fields:
        x, y = FIELD_ROWS[name]
        action = f'/AA << /F << /S /JavaScript /JS ({esc(script)}) >> >>' if script else ''
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Tx /T ({name}) /V ({esc(stored)}) {action} '
                           f'/Rect [{x} {y} {x + 200} {y + 18}] /F 4 /P 3 0 R /DA (/Helv 11 Tf 0 g) '
                           f'/AP << /N {number + 1} 0 R >> >>').encode()
        drawing = f'/Tx BMC q BT /Helv 11 Tf 0 g 2 4 Td ({esc(shown)}) Tj ET Q EMC'
        form = '/Type /XObject /Subtype /Form /BBox [0 0 200 18] /Resources << /Font << /Helv 4 0 R >> >>'
        if name in broken:
            cut = zlib.compress(drawing.encode('latin-1'))[:-6]
            objects[number + 1] = (f'<< {form} /Filter /FlateDecode /Length {len(cut)} >>\nstream\n'.encode()
                                   + cut + b'\nendstream')
        else:
            objects[number + 1] = stream(drawing, form)
        widgets.append(number)
        number += 2
    refs = ' '.join(f'{n} 0 R' for n in widgets)
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  f'/Contents 5 0 R /Annots [{refs}] >>').encode()
    objects[10] = (f'<< /Fields [{refs}] /NeedAppearances false /DA (/Helv 0 Tf 0 g) /DR << /Font << /Helv 4 0 R '
                   '>> >> >>').encode()
    return serialise(objects)


def mismatch(label: str) -> str:
    return (f'Page 1: form field "{label}" shows text that differs from its stored value; the stored value was '
            'read, so check it against the original.')


NUMBER_1 = 'AFNumber_Format(1, 0, 0, 0, "", true);'


class FieldFormatTests(unittest.TestCase):
    """ingest:8 — compare after applying the field's standard format; anything else stays flagged."""

    def test_standard_formats_are_display_formatting(self):
        fields = [('withdrawal', '14', '14.0', NUMBER_1), ('bbps', '8', '8', None),
                  ('dos', '10/21/26', '10/21/2026', 'AFDate_FormatEx("mm/dd/yyyy");'),
                  ('amount', '-1234.5', '($1,234.50)', 'AFNumber_Format(2, 0, 2, 0, "$", true);'),
                  ('share', '0.25', '25.0%', 'AFPercent_Format(1, 0);'),
                  ('phone', '5551234567', '(555) 123-4567', 'AFSpecial_Format(2);')]
        result = pdf_extract(formatted_form(fields), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        for line in ('withdrawal: 14', 'bbps: 8', 'dos: 10/21/26', 'amount: -1234.5', 'share: 0.25',
                     'phone: 5551234567'):
            self.assertIn(line, result.text)
        indexed = pdf_extract(formatted_form([('dos', '10/21/2026', '10/21/26', 'AFDate_Format(2);')]), ocr=None)
        self.assertEqual(indexed.status, 'ok')

    def test_an_appearance_that_cannot_be_read_is_named_as_unread(self):
        result = pdf_extract(formatted_form([('withdrawal', '14', '14.0', NUMBER_1)], broken=('withdrawal',)),
                             ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertIn('Page 1 has a form field or annotation whose text could not be read.', result.messages)
        self.assertNotIn(mismatch('withdrawal'), result.messages)
        self.assertIn('withdrawal: 14', result.text)

    def test_differences_a_format_does_not_explain_stay_flagged(self):
        cases = {'no format action': ('14', '41', None),
                 'a standard format, a different number': ('14', '41.0', NUMBER_1),
                 'a value the format cannot parse': ('fourteen', '14.0', NUMBER_1),
                 'a custom format script': ('14', 'Fourteen', 'event.value = "Fourteen";'),
                 'a standard call followed by more script': ('14', '14.0', NUMBER_1 + ' event.value = "41";'),
                 'a date format, a different date': ('10/21/26', '10/22/2026', 'AFDate_FormatEx("mm/dd/yyyy");'),
                 # Round 3 ingest:12: a time format explains its own rendering ('10/21/2026 14:30'), not another time.
                 'a time format, a different time': ('10/21/26 14:30', '10/21/2026 14:45',
                                                     'AFDate_FormatEx("mm/dd/yyyy HH:MM");')}
        for label, (stored, shown, script) in cases.items():
            with self.subTest(label):
                result = pdf_extract(formatted_form([('withdrawal', stored, shown, script)]), ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertIn(mismatch('withdrawal'), result.messages)


if __name__ == '__main__':
    unittest.main()
