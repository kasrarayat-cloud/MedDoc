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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from studio.gi.detect import status_for_span
from studio.ingest import Limits, extract_document
from studio.ingest import docx as docx_ingest
from tests.support import docgen

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


if __name__ == '__main__':
    unittest.main()
