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
import unittest

import docx
import pypdf
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pypdf.generic._font import Font
from reportlab.lib.pagesizes import letter
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

    def test_no_glyph_on_a_row_holding_another_button(self):
        rows = [('Check Box1', 'Biopsy', False, (72, 618, 84, 630), (90, 620, 'Biopsy')),
                ('Check Box2', 'Cold snare', True, (200, 618, 212, 630), (218, 620, 'Cold snare'))]
        result = pdf_extract(box_form(rows), ocr=None)
        self.assertNotIn('☐', result.text)
        self.assertNotIn('☒', result.text)
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


if __name__ == '__main__':
    unittest.main()
