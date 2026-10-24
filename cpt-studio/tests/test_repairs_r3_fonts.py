"""Regression tests for the symbol-font repairs of refutation round 3 (ingest:6, ingest:7, ingest:11, ingest:15).

Every document is synthetic and built here from raw PDF syntax or with python-docx; nothing is read from disk.
The check-box contract shared with routing: extraction writes every check box it recognises as ☐ (unchecked) or
☒ (checked), whatever box shape or encoding the font uses, and routing reads '☐ Biopsy' as negated.
"""
from __future__ import annotations

import unittest

from studio.ingest import symbols
from studio.ingest.pdffonts import composite_glyph
from tests.test_repairs_ingest_pdf import serialise
from tests.test_repairs_ingest_r2 import (PDF_NOTE, SYMBOL_DESCRIPTOR, WIDTHS, checklist_docx, composite_font,
                                          docx_extract, font_pdf, pdf_extract, reading, stream, to_unicode,
                                          undecodable_note)

UNCHECKED, CHECKED = '☐', '☒'


def wingdings_font(pairs=None, *, base: str = 'Wingdings-Regular', encoding: str = '') -> tuple[str, dict]:
    """A simple TrueType symbol font as Word writes it, with ``pairs`` as its ToUnicode (None: no ToUnicode)."""
    font = f'<< /Type /Font /Subtype /TrueType /BaseFont /{base} {WIDTHS} /FontDescriptor 8 0 R {encoding}'
    extra = {8: SYMBOL_DESCRIPTOR}
    if pairs is not None:
        font += ' /ToUnicode 7 0 R'
        extra[7] = to_unicode(pairs)
    return font + ' >>', extra


def box_line(code: str, label: str = ' Biopsy', y: int = 620):
    return [(y, code, label)]


# --- ingest:6 — every box a symbol font draws is a box, in every encoding ----------------------------

class WingdingsBoldBoxTests(unittest.TestCase):
    """ingest:6 — Wingdings 0x70 (U+1F790 BOLD WHITE SQUARE) is the same drawn box in every encoding."""

    def test_docx_wingdings_p_in_every_encoding_is_an_unchecked_box(self):
        for label, segments in {'typed p': [('p', 'Wingdings'), (' Biopsy', None)],
                                'w:sym F070': [('SYM', 'Wingdings', 'F070'), (' Biopsy', None)],
                                'private-use U+F070': [('', 'Wingdings'), (' Biopsy', None)]}.items():
            with self.subTest(label):
                result = docx_extract(checklist_docx(segments))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_pdf_wingdings_0x70_in_every_encoding_is_an_unchecked_box(self):
        for label, pairs in {'Word private-use ToUnicode U+F070': [(0x70, '')],
                             'no ToUnicode': None,
                             'Latin-echo ToUnicode p': [(0x70, 'p')],
                             'converter ToUnicode U+1F790': [(0x70, '\U0001f790')]}.items():
            with self.subTest(label):
                font, extra = wingdings_font(pairs)
                result = pdf_extract(font_pdf(font, box_line('70'), extra=extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_converter_unicode_for_the_other_white_square_weights_is_a_box(self):
        # A converter's Unicode 7 ToUnicode for Wingdings 0xA8 (U+1F78E) and 0x6F (U+1F78F), and the heavier
        # weights Wingdings 2 draws (U+1F791-U+1F793): each is a white square, so each is an unchecked box.
        for char in ('\U0001f78e', '\U0001f78f', '\U0001f790', '\U0001f791', '\U0001f792', '\U0001f793'):
            with self.subTest(hex(ord(char))):
                font, extra = wingdings_font([(0xA8, char)])
                result = pdf_extract(font_pdf(font, box_line('A8'), extra=extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_every_box_shaped_glyph_of_the_symbol_fonts_is_mapped(self):
        """The box glyphs of each table, from an independent Unicode mapping of the fonts (Wingdings, Wingdings 2,
        Webdings: Microsoft's own glyph names; Zapf Dingbats: Adobe's zdingbat table)."""
        boxes = {('wingdings', 0x6F): UNCHECKED, ('wingdings', 0x70): UNCHECKED, ('wingdings', 0x71): UNCHECKED,
                 ('wingdings', 0x72): UNCHECKED, ('wingdings', 0xA8): UNCHECKED, ('wingdings', 0x78): CHECKED,
                 ('wingdings', 0xFD): CHECKED, ('wingdings', 0xFE): CHECKED,
                 ('wingdings2', 0x51): CHECKED, ('wingdings2', 0x52): CHECKED, ('wingdings2', 0x53): CHECKED,
                 ('wingdings2', 0x54): CHECKED, ('wingdings2', 0xA3): UNCHECKED, ('wingdings2', 0xA4): UNCHECKED,
                 ('wingdings2', 0xA5): UNCHECKED, ('wingdings2', 0xA6): UNCHECKED,
                 ('webdings', 0x63): UNCHECKED,
                 ('zapfdingbats', 0x6F): UNCHECKED, ('zapfdingbats', 0x70): UNCHECKED,
                 ('zapfdingbats', 0x71): UNCHECKED, ('zapfdingbats', 0x72): UNCHECKED}
        for (font, code), glyph in boxes.items():
            with self.subTest(font=font, code=hex(code)):
                self.assertEqual(symbols.SYMBOL_FONTS[font].get(code), glyph)
        for char in ('\U0001f78e', '\U0001f78f', '\U0001f790', '\U0001f791', '\U0001f792', '\U0001f793', '⬜'):
            self.assertEqual(symbols.as_box(char), UNCHECKED, hex(ord(char)))
        self.assertEqual(symbols.as_box('\U0001f5f5'), CHECKED)

    def test_filled_squares_and_other_glyphs_are_not_boxes(self):
        # A filled square is a bullet as often as a box; a target or a square holding a dot is neither state.
        for char in ('■', '◼', '▪', '\U0001f794', '▣', '\U0001f796', '⏹'):
            with self.subTest(hex(ord(char))):
                self.assertNotIn(symbols.as_box(char), (UNCHECKED, CHECKED))

    def test_wingdings_2_and_webdings_boxes_in_pdf(self):
        for base, code, glyph in (('Wingdings2', 'A4', UNCHECKED), ('Wingdings2', 'A6', UNCHECKED),
                                  ('Wingdings2', '51', CHECKED), ('Webdings', '63', UNCHECKED)):
            with self.subTest(base=base, code=code):
                font, extra = wingdings_font(None, base=base)
                result = pdf_extract(font_pdf(font, box_line(code), extra=extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith(f'Interventions:\n{glyph} Biopsy'), result.text)


# --- ingest:7 — a composite symbol font's Latin echo is its code ---------------------------------------

def composite_pdf(base: str, cmap, lines) -> bytes:
    font, extra = composite_font(to_unicode_ref='/ToUnicode 7 0 R', base=base)
    extra[7] = to_unicode(cmap, code_bytes=2)
    return font_pdf(font, lines, extra=extra)


class CompositeLatinEchoTests(unittest.TestCase):
    """ingest:7 — a Type0 Wingdings whose ToUnicode echoes the Latin-1 code (as a browser prints a page styled in
    Wingdings) reads its boxes through the font's table, as the simple-font Latin echo already does."""

    def test_composite_wingdings_latin_echo_reads_both_boxes(self):
        data = composite_pdf('ABCDEF+Wingdings-Regular', [(0x0003, '¨'), (0x0004, 'þ')],
                             [(620, '0004', ' Cold snare polypectomy'), (600, '0003', ' Biopsy')])
        result = pdf_extract(data, ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Interventions:\n☒ Cold snare polypectomy\n☐ Biopsy'), result.text)
        self.assertEqual(reading(result.text, 'Biopsy'), 'negated')
        self.assertNotEqual(reading(result.text, 'Cold snare polypectomy'), 'negated')

    def test_composite_echo_of_other_box_codes(self):
        for base, echo, glyph in (('ABCDEF+Wingdings-Regular', 'p', UNCHECKED), ('ABCDEF+Wingdings-Regular', 'o', UNCHECKED),
                                  ('ABCDEF+Wingdings2', 'T', CHECKED), ('ABCDEF+ZapfDingbats', 'o', UNCHECKED)):
            with self.subTest(base=base, echo=echo):
                result = pdf_extract(composite_pdf(base, [(0x0003, echo)], [(620, '0003', ' Biopsy')]), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith(f'Interventions:\n{glyph} Biopsy'), result.text)

    def test_a_latin_echo_with_no_glyph_in_the_table_is_counted(self):
        result = pdf_extract(composite_pdf('ABCDEF+Wingdings-Regular', [(0x0003, 'J')], [(620, '0003', ' Mood')]),
                             ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
        self.assertTrue(result.text.endswith('Interventions:\n Mood'), result.text)

    def test_composite_symbol_font_keeps_its_latin_characters_unread(self):
        # Symbol draws real Latin-1 characters ('×' is Symbol 0xB4, not 0xD7, which draws '⋅'): a Latin-1
        # character from its ToUnicode is not an echo, so it is never re-read through the Symbol table.
        result = pdf_extract(composite_pdf('ABCDEF+SymbolMT', [(0x0003, '×')], [(620, '0003', ' 2 cm')]),
                             ocr=None)
        self.assertNotIn('⋅', result.text)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))

    def test_zapf_dingbats_undefined_codes_are_counted_not_read_as_letters(self):
        # Zapf Dingbats has no glyph at 0xF0 or 0xFF; pypdf's table fills them with 'ð' and 'ÿ'.
        self.assertFalse(symbols.SYMBOL_FONTS['zapfdingbats'].latin)
        self.assertTrue(symbols.SYMBOL_FONTS['symbol'].latin)
        result = pdf_extract(font_pdf('<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>',
                                      [(620, 'F0', ' Biopsy'), (600, 'FF', ' Tattoo')]), ocr=None)
        self.assertNotIn('ð', result.text)
        self.assertNotIn('ÿ', result.text)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(2),)))

    def test_composite_glyph_reads_an_echo_only_through_a_table_without_latin_glyphs(self):
        trusted = frozenset({'¨', '×'})
        self.assertEqual(composite_glyph('¨', trusted, symbols.SYMBOL_FONTS['wingdings']), UNCHECKED)
        self.assertIsNone(composite_glyph('×', trusted, symbols.SYMBOL_FONTS['symbol']))
        self.assertIsNone(composite_glyph('¨', frozenset(), symbols.SYMBOL_FONTS['wingdings']))  # not its map's


if __name__ == '__main__':
    unittest.main()
