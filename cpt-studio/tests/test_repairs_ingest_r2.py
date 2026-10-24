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
import unittest

import docx
import pypdf
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pypdf.generic._font import Font

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


if __name__ == '__main__':
    unittest.main()
