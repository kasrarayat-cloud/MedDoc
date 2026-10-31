"""Regression tests for the symbol-font repairs of refutation round 3 (ingest:6, ingest:7, ingest:11, ingest:15).

Every document is synthetic and built here from raw PDF syntax or with python-docx; nothing is read from disk.
The check-box contract shared with routing: extraction writes every check box it recognises as ☐ (unchecked) or
☒ (checked), whatever box shape or encoding the font uses, and routing reads '☐ Biopsy' as negated.
"""
from __future__ import annotations

import io
import unittest

from pypdf import PdfReader
from pypdf._text_extraction import get_text_operands
from pypdf.generic._font import Font

from studio.ingest import symbols
from studio.ingest.pdfcontent import _ING_glyphs, IDENTITY, ORIENTATIONS
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


# --- ingest:11 — a symbol font's /Differences names the glyph each code draws ---------------------------

def zapf(differences: str = '', to_unicode_pairs=None) -> tuple[str, dict]:
    """The non-embedded Zapf Dingbats (viewers draw it by glyph name), re-encoded by ``differences``."""
    encoding = f'/Encoding << /Differences [{differences}] >>' if differences else ''
    extra = {}
    if to_unicode_pairs is not None:
        encoding += ' /ToUnicode 7 0 R'
        extra[7] = to_unicode(to_unicode_pairs)
    return f'<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats {encoding} >>', extra


class SymbolFontDifferencesTests(unittest.TestCase):
    """ingest:11 — the glyph a /Differences entry names is what the code shows (pdftotext and viewers agree):
    a74 is Zapf Dingbats' shadowed box, wherever it is encoded."""

    def extract(self, font, extra, code, label=' Biopsy'):
        return pdf_extract(font_pdf(font, box_line(code, label), extra=extra), ocr=None)

    def test_zapf_box_re_encoded_by_differences_is_an_unchecked_box(self):
        for label, (differences, code) in {'Differences [33 /a74]': ('33 /a74', '21'),
                                           'subset form [1 /a74]': ('1 /a74', '01'),
                                           'built-in code 0x6F (control)': ('', '6F')}.items():
            with self.subTest(label):
                result = self.extract(*zapf(differences), code)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_a_code_re_encoded_away_from_a_box_is_not_a_box(self):
        # [111 /a1]: code 0x6F, the built-in box, now draws the scissors a1 (U+2701); the page shows no box.
        result = self.extract(*zapf('111 /a1'), '6F')
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Interventions:\n✁ Biopsy'), result.text)
        self.assertNotEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_tounicode_beside_differences(self):
        cases = {'real Unicode U+274F (trusted)': [(0x21, '❏')],
                 'private-use echo U+F021': [(0x21, '')],
                 'Latin echo !': [(0x21, '!')],
                 'an entry for another code only (0x4A)': [(0x4A, 'X')],
                 # pypdf's encoding gives code 0x21 the character 'J' (its reading of a74); keyed through it, the
                 # map would hand 0x21 the trusted scissors of code 0x4A.
                 'a real-Unicode entry for another code only (0x4A)': [(0x4A, '✁')]}
        for label, pairs in cases.items():
            with self.subTest(label):
                result = self.extract(*zapf('33 /a74', pairs), '21')
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)

    def test_uni_glyph_names(self):
        cases = {'Wingdings uniF0A8': wingdings_font(None, encoding='/Encoding << /Differences [65 /uniF0A8] >>'),
                 'Zapf uni2610': zapf('65 /uni2610'), 'Zapf u2612': zapf('65 /u2612')}
        for label, (font, extra) in cases.items():
            with self.subTest(label):
                result = self.extract(font, extra, '41')
                self.assertEqual((result.status, result.messages), ('ok', ()))
                glyph = CHECKED if label.endswith('u2612') else UNCHECKED
                self.assertTrue(result.text.endswith(f'Interventions:\n{glyph} Biopsy'), result.text)

    def test_a_name_that_names_no_known_glyph_is_counted(self):
        # pypdf's own glyph list would read '.notdef' as '□' and 'a74' in another font as 'J'.
        for label, (font, extra) in {'Zapf g17': zapf('33 /g17'), 'Zapf .notdef': zapf('33 /.notdef'),
                                     'Wingdings a74': wingdings_font(None, encoding='/Encoding << /Differences '
                                                                                    '[33 /a74] >>')}.items():
            with self.subTest(label):
                result = self.extract(font, extra, '21', ' Mood')
                self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
                self.assertTrue(result.text.endswith('Interventions:\n Mood'), result.text)

    def test_built_in_glyph_names_read_the_right_glyphs(self):
        # Values from pdf.js's own Zapf Dingbats glyph list (an independent source): name -> character, as boxes.
        from studio.ingest.pdffonts import named_glyph
        zapf_table = symbols.SYMBOL_FONTS['zapfdingbats']
        for name, char in {'a1': '✁', 'a12': '☞', 'a71': '●', 'a74': UNCHECKED, 'a203': UNCHECKED,
                           'a75': UNCHECKED, 'a204': UNCHECKED, 'a20': '✔', 'a191': '➾'}.items():
            self.assertEqual(named_glyph(name, zapf_table), char, name)
        symbol_table = symbols.SYMBOL_FONTS['symbol']
        self.assertEqual(named_glyph('bullet', symbol_table), '•')
        self.assertEqual(named_glyph('alpha', symbol_table), 'α')
        for name in ('.notdef', 'a74.alt', 'g17', 'H', 'a74x'):
            self.assertIsNone(named_glyph(name, zapf_table), name)
        self.assertIsNone(named_glyph('a74', symbols.SYMBOL_FONTS['wingdings']))

    def test_symbol_glyph_names(self):
        font = '<< /Type /Font /Subtype /Type1 /BaseFont /Symbol /Encoding << /Differences [33 /bullet /alpha] >> >>'
        result = pdf_extract(font_pdf(font, [(620, '21', ' Cold snare polypectomy'), (600, '22', ' 2 mm')]),
                             ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Interventions:\n• Cold snare polypectomy\nα 2 mm'), result.text)


# --- ingest:15 — one malformed ToUnicode entry never fails the document ----------------------------------

INVALID_TEXT = 'Page 1 contains characters the PDF does not encode as valid text; they are shown as �.'


def raw_cmap(entries) -> bytes:
    """A ToUnicode CMap from (code hex, destination hex) pairs written as given (a lone surrogate included)."""
    body = '\n'.join(f'<{code}> <{dest}>' for code, dest in entries)
    return stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry '
                  '(Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic-UCS def\n/CMapType 2 def\n'
                  f'1 begincodespacerange\n<00> <FF>\nendcodespacerange\n{len(entries)} beginbfchar\n{body}\n'
                  'endbfchar\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')


def surrogate_font(dest: str = 'D83D') -> tuple[str, dict]:
    """Word's Wingdings shape, whose ToUnicode also maps the unused code 0x4A to a lone surrogate."""
    return (f'<< /Type /Font /Subtype /TrueType /BaseFont /AAAAAA+Wingdings-Regular {WIDTHS} /FontDescriptor 8 0 R '
            '/ToUnicode 7 0 R >>', {8: SYMBOL_DESCRIPTOR, 7: raw_cmap([('A8', 'F0A8'), ('4A', dest)])})


class MalformedSymbolCmapTests(unittest.TestCase):
    """ingest:15 — a lone surrogate in a symbol font's ToUnicode is read as a text font's would be."""

    def test_lone_surrogate_for_an_unused_code(self):
        for dest in ('D83D', 'DE00'):
            with self.subTest(dest):
                font, extra = surrogate_font(dest)
                result = pdf_extract(font_pdf(font, box_line('A8'), extra=extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'negated')

    def test_a_font_only_listed_or_drawn_on_a_later_page_does_not_fail_the_others(self):
        font, extra = surrogate_font()
        listed = pdf_extract(font_pdf(font, [], extra=extra), ocr=None)
        self.assertEqual((listed.status, listed.messages), ('ok', ()))
        self.assertTrue(listed.text.endswith('Interventions:'), listed.text)
        objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R 11 0 R] /Count 2 >>'}
        objects.update({3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                            b'>> >> /Contents 5 0 R >>'), 4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                        5: stream('BT /F1 11 Tf 72 700 Td (Procedure: Colonoscopy to the cecum.) Tj ET'),
                        6: font.encode(), 7: extra[7], 8: extra[8],
                        11: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                             b'/F2 6 0 R >> >> /Contents 12 0 R >>'),
                        12: stream('BT /F1 11 Tf 72 700 Td (Interventions:) Tj ET\n'
                                   'BT /F2 11 Tf 72 680 Td <A8> Tj /F1 11 Tf ( Biopsy) Tj ET')})
        result = pdf_extract(serialise(objects), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn('Procedure: Colonoscopy to the cecum.', result.text)
        self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy'), result.text)

    def test_a_drawn_lone_surrogate_is_replaced_and_named(self):
        font, extra = surrogate_font()
        result = pdf_extract(font_pdf(font, box_line('A8') + [(600, '4A', ' Mood')], extra=extra), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (INVALID_TEXT,)))
        self.assertTrue(result.text.endswith('Interventions:\n☐ Biopsy\n� Mood'), result.text)

    def test_a_symbol_font_that_cannot_be_copied_is_counted_never_read_as_letters(self):
        from unittest import mock

        from studio.ingest import pdffonts
        from tests.test_repairs_ingest_r2 import in_process
        font, extra = wingdings_font(None)  # read as its own encoding, code 0xA8 would show '¤'
        with mock.patch.object(pdffonts, '_copy_widths', side_effect=ValueError('synthetic failure')):
            result = in_process(font_pdf(font, box_line('A8'), extra=extra))
        self.assertNotIn('¤', result.text)
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
        self.assertTrue(result.text.endswith('Interventions:\n Biopsy'), result.text)


# --- pypdf 6.21.4 writes the replacement character itself for a string it cannot decode -------------------

IDENTITY_CMAP = ('1 begincodespacerange <0000> <FFFF> endcodespacerange\n'
                 '1 beginbfrange <0000> <FFFF> <0000> endbfrange\n')
GIVES_REPLACEMENT_CMAP = ('1 begincodespacerange <0000> <FFFF> endcodespacerange\n'
                          '1 beginbfchar <0058> <FFFD> endbfchar\n1 beginbfrange <0041> <0050> <0041> endbfrange\n')


def two_byte_pdf(show: str, *, cmap: str = IDENTITY_CMAP, form: str = '') -> bytes:
    """A page of ordinary text, then ``show`` in a two-byte font; a form XObject on the page draws ``form``."""
    lines = ('BT /F2 11 Tf 72 720 Td (Colonoscopy with cold snare polypectomy of a sigmoid polyp was done.) Tj ET\n'
             'BT /F2 11 Tf 72 700 Td (The remaining colon and rectum appeared normal throughout the study.) Tj ET\n')
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font '
                   b'<< /F1 4 0 R /F2 8 0 R >> /XObject << /Fm1 9 0 R >> >> >>'),
               4: (b'<< /Type /Font /Subtype /Type0 /BaseFont /AAAAAA+Arial /Encoding /Identity-H /DescendantFonts '
                   b'[6 0 R] /ToUnicode 7 0 R >>'),
               5: stream(lines + f'BT /F1 11 Tf 72 680 Td {show} ET\n' + ('/Fm1 Do\n' if form else '')),
               6: (b'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /AAAAAA+Arial /DW 500 /CIDSystemInfo '
                   b'<< /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> >>'),
               7: stream(cmap),
               8: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
               9: stream(f'BT /F1 11 Tf 72 660 Td {form} ET', '/Type /XObject /Subtype /Form /BBox [0 0 612 792] '
                         '/Resources << /Font << /F1 4 0 R >> >>')}
    return serialise(objects)


class UndecodableStringTests(unittest.TestCase):
    """An odd byte count in a two-byte font: pypdf writes U+FFFD, and the page still says its text is not valid."""

    def test_a_cut_string_is_shown_and_named(self):
        for show, read in (('<00410042FF> Tj', 'AB�'), ('<0041004241> Tj', 'AB�'),
                           ('<0041004200> Tj', 'AB�'), ('[<00410042FF> -100 <0043>] TJ', 'AB� C'),
                           ('[<0041004241> -100 <0043>] TJ', 'AB� C')):
            with self.subTest(show):
                result = pdf_extract(two_byte_pdf(show), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (INVALID_TEXT,)))
                self.assertTrue(result.text.endswith('study.\n' + read), result.text)

    def test_a_cut_string_in_a_form_is_named(self):
        for form in ('<00410042FF> Tj', '<0041004241> Tj'):
            with self.subTest(form):
                result = pdf_extract(two_byte_pdf('<004100420043> Tj', form=form), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (INVALID_TEXT,)))
                self.assertTrue(result.text.endswith('ABC\nAB�'), result.text)

    def test_a_font_that_gives_the_replacement_character_is_named_too(self):
        result = pdf_extract(two_byte_pdf('<004100580042> Tj', cmap=GIVES_REPLACEMENT_CMAP), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (INVALID_TEXT,)))
        self.assertTrue(result.text.endswith('A�B'), result.text)

    def test_a_whole_string_is_not_named(self):
        result = pdf_extract(two_byte_pdf('<004100420043> Tj'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('study.\nABC'), result.text)

    def test_the_glyph_reader_decodes_as_pypdf_does(self):
        reader = PdfReader(io.BytesIO(two_byte_pdf('<004100420043> Tj')))
        font = Font.from_font_resource(reader.pages[0]['/Resources']['/Font']['/F1'].get_object())
        for string in (b'\x00A\x00B\xff', b'\x00A\x00B\x41', b'\x00A\x00', b'\xd8\x00\x41\xff\xff', b'\xdc\x00\x00A',
                       b'\x00A'):
            with self.subTest(string):
                text = get_text_operands([string], list(IDENTITY), list(IDENTITY), font, ORIENTATIONS)[0]
                self.assertEqual(''.join(glyph[0] for glyph in _ING_glyphs(font, string)), text)


if __name__ == '__main__':
    unittest.main()
