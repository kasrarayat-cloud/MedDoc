"""The reader on pypdf 6.21.4, row by row of ACCURACY-RESIDUALS.md "pypdf 6.21.4" (interpretation 66: each reading is
judged by what the document shows, and equality with 6.21.2 is a safety net only where 6.21.2 read it right).

Every document is synthetic and built in tests/support/pypdf_shapes.py from raw PDF syntax; nothing is read from disk.
The documents go through the real extraction child, with OCR unavailable and with stand-in OCR tools, so the tests
see the statuses, notices and OCR routing an upload gets. Text pypdf cannot read as the font encodes it is never
returned as text, and never dropped (round 3 of the repair): each character pypdf would have written for it is U+FFFD
in its place, in a page's layer or in an appearance's text, counted and named (partial); the rest of the layer is read,
and a page left with no usable text layer goes to OCR or is named. A glyph that names no character alone in a typed
box is the unread mark '[?]', never an empty box.
"""
from __future__ import annotations

import re
import tempfile
import time
import unittest
from unittest import mock

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf._text_extraction import get_text_operands
from pypdf.generic._font import Font

from studio.ingest import Limits, extract_document
from studio.ingest import _child as child_module
from studio.ingest.pdf import (DAMAGED, LIMIT_REACHED, PASSWORD, SECTIONS_LOST, _ING_UNREAD_NOTE, extract_pdf,
                               unreadable_note)
from studio.ingest.pdfcontent import IDENTITY, ORIENTATIONS, _ING_glyphs
from studio.ingest.pdffonts import agl_text, decodes, pypdf_reads_by_number, undecodable, unread_in_boxes
from studio.ingest.text import INGEST_VERSION, caused_by, from_memory
from tests.support import pypdf_shapes as shapes
from tests.test_ingest import FakeOcr
from tests.test_repairs_ingest_r2 import reading, undecodable_note

PDF = 'application/pdf'
SHAPES = shapes.shapes()
NO_LAYER = 'Page {n} has no usable text layer and OCR is not available on this server.'
NO_TEXT = 'No text could be read from the PDF.'
INVALID = 'Page 1 contains characters the PDF does not encode as valid text; they are shown as \ufffd.'
UNREAD_BOX = _ING_UNREAD_NOTE.format(pages='Page 1', has='has')
ANNOTATION = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
              'annotation text.')
FIELDS = ('Page 1 has PDF form fields; their values were read and added after the page text, labelled as form '
          'fields.')
OCR_READ = 'Page {n} was read with OCR; OCR can misread characters \u2014 check evidence against the original.'
MOJIBAKE = set('\ufffd\u2612') | {chr(code) for code in range(0x3400, 0xA000)}  # what pypdf 6.21.4 wrote
WRONG = MOJIBAKE - {'\ufffd'}  # what pypdf wrote that is not a mark of text that could not be read


def unread_text(result, *pages) -> str:
    """The notice naming the text the reader could not read on ``pages``: as many characters as the result shows as
    U+FFFD (none of these documents holds another)."""
    return unreadable_note(list(pages), result.text.count('\ufffd'))


def extract(data: bytes, ocr=None):
    return extract_document(data, 'synthetic.pdf', PDF, ocr=ocr)


def body(text: str) -> str:
    """The text after the note's last printed line (the interventions it lists, or the labelled block)."""
    return text.split('Interventions:', 1)[1] if 'Interventions:' in text else text


class CutStringInAnAppearanceTests(unittest.TestCase):
    """TXT-1, n-1, n-2 (block): a string an appearance shows that its font cannot decode (an odd byte count in a
    two-byte CMap, one-byte text in a two-byte font) is not read as text: in the appearance's text, as the annotation
    or field reads it, each character pypdf would have written for it is U+FFFD in its place, named with its count
    (partial); never pypdf's mojibake (round 3 of the repair; rounds 1 and 2 left the whole annotation unread)."""

    NAMES = [name for name in SHAPES if name.startswith(('TXT-1 ', 'n-1 ', 'n-2 '))
             and 'FFFD' not in name and 'page 3' not in name]

    # Round 4 of the repair (R3-MEAN-3): a string in a CMap pypdf decodes with a codec is cut into codes by the CMap's
    # code space, so the codes before the cut are read and only the cut code is U+FFFD, as the installed reader read
    # them; a string of a two-byte font cut inside a code cannot be told from one-byte text, and stays unread.
    CODEC_CUT = {'n-1 stamp 90ms-RKSJ-H cut': '\u3042\ufffd', 'n-1 stamp GBK-EUC-H cut': '\u554a\ufffd'}

    def test_an_appearance_pypdf_cannot_decode_keeps_its_place_never_mojibake(self):
        self.assertEqual(len(self.NAMES), 16)
        for name in self.NAMES:
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual(result.status, 'partial')
                self.assertIn(result.messages[1:], ((ANNOTATION,), (FIELDS,)))
                self.assertEqual(result.messages[0], unread_text(result, 1))
                line = result.text.rsplit('\n', 1)[1]  # the annotation's text, or 'label: ' and the field's
                if name in self.CODEC_CUT:
                    self.assertEqual(line, self.CODEC_CUT[name])
                    continue
                self.assertRegex(line, '^([A-Za-z0-9]+: )?\ufffd+$')
                self.assertFalse(WRONG & set(result.text), result.text)

    def test_the_page_beside_it_and_a_page_layer_cut_the_same_way(self):
        """Page 3 draws the note in Helvetica, which pypdf reads as the PDF encodes it, and the cut string: the cut
        string is U+FFFD in its place, the note read and the page named (round 2 of the repair dropped the string;
        ingest@4 at first left all of page 3 unread)."""
        for ocr in (False, True):
            with FakeOcr() as fake:
                result = extract(SHAPES['n-1 page 2 stamp cut, page 3 layer cut'], ocr=fake.tools if ocr else None)
            self.assertEqual((result.status, result.messages, result.ocr_pages),
                             ('partial', (unread_text(result, 2, 3), ANNOTATION.replace('Page 1', 'Page 2')), ()))
            self.assertEqual([page.strip() for page in result.text.split('\n\n')],
                             [shapes.NOTE_TEXT, shapes.NOTE_TEXT, '[PDF annotation text on page 2]\n\ufffd\ufffd\ufffd',
                              shapes.NOTE_TEXT + '\n\ufffd\ufffd\ufffd'])

    def test_a_whole_string_in_the_same_font_is_read(self):
        result = extract(shapes.annotated(shapes.shown('004100420043')))
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION,)))
        self.assertTrue(result.text.endswith('[PDF annotation text on page 1]\nABC'), result.text)


class UnimplementedCMapTests(unittest.TestCase):
    """TXT-2 (block): text in a predefined CMap pypdf does not implement (it reads the bytes as UTF-16BE) is not read
    as text, whether the byte count is odd (6.21.2 refused it) or even (6.21.2 read mojibake): the page goes to OCR,
    or is named when there is none. The CMaps pypdf implements read as before."""

    def test_every_unimplemented_cmap_goes_to_ocr_never_mojibake(self):
        for cmap in shapes.UNIMPLEMENTED_CMAPS:
            for parity in ('odd', 'even'):
                with self.subTest(cmap=cmap, parity=parity):
                    data = SHAPES[f'TXT-2 {cmap} {parity}']
                    result = extract(data)
                    self.assertEqual((result.status, result.text, result.messages),
                                     ('failed', '', (NO_LAYER.format(n=1), NO_TEXT)))
                    with FakeOcr() as fake:
                        ocred = extract(data, ocr=fake.tools)
                    self.assertEqual((ocred.status, ocred.method, ocred.ocr_pages), ('ok', 'pdf-ocr', (1,)))
                    self.assertFalse(MOJIBAKE & set(ocred.text), ocred.text)

    def test_the_cmaps_pypdf_implements_read_their_text(self):
        for cmap in shapes.IMPLEMENTED_CMAPS:
            for parity in ('odd', 'even'):
                with self.subTest(cmap=cmap, parity=parity):
                    result = extract(SHAPES[f'TXT-2 {cmap} {parity}'])
                    self.assertEqual((result.status, result.messages, result.ocr_pages), ('ok', (), ()))
                    self.assertEqual([line.strip() for line in result.text.split('\n')],
                                     [line.strip() for line in shapes.CJK_TEXT])

    def test_the_producer_route_reportlab_cid_fonts(self):
        text = 'Synthetic cold snare polypectomy'  # an even count: 6.21.2 read it as mojibake
        for face, cmap in (('HYSMyeongJo-Medium', 'KSCms-UHC-H'), ('HeiseiMin-W3', '90msp-RKSJ-H'),
                           ('MSung-Light', 'B5pc-H')):
            with self.subTest(cmap):
                result = extract(shapes.reportlab_cjk(face, cmap, text))
                self.assertEqual((result.status, result.messages), ('failed', (NO_LAYER.format(n=1), NO_TEXT)))
        result = extract(shapes.reportlab_cjk('STSong-Light', 'GBK-EUC-H', text))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.startswith(text), result.text)


class CutStringInThePageTests(unittest.TestCase):
    """TXT-7, n-3 and the page layer: a cut string in the page's own text is not read as text, so pypdf's U+FFFD, and
    whatever a ToUnicode entry for code FFFD turns it into (a checked box, 'X'), never reaches the text: each character
    pypdf would have written for it is U+FFFD in its place, counted and named, and the rest of the layer, in fonts pypdf
    reads as the PDF encodes them, is read (round 2 of the repair: the operator, not the page, is the unit; round 3: it
    keeps its place, never dropped)."""

    NAMES = [name for name in SHAPES if name.startswith(('TXT-7 ', 'n-3 ', 'page layer '))]

    def test_the_cut_string_keeps_its_place_and_is_named_and_the_page_read(self):
        self.assertEqual(len(self.NAMES), 9)
        for name in self.NAMES:
            for ocr in (False, True):
                with self.subTest(name, ocr=ocr), FakeOcr() as fake:
                    result = extract(SHAPES[name], ocr=fake.tools if ocr else None)
                    self.assertEqual((result.status, result.messages, result.ocr_pages),
                                     ('partial', (unread_text(result, 1),), ()))
                    self.assertRegex(result.text.strip(), '^' + re.escape(shapes.NOTE_TEXT) + '\n\ufffd+$')
                    self.assertNotIn('\u2612', result.text)

    def test_the_page_beside_keeps_its_text_and_the_unreadable_string_is_marked(self):
        """Page 2's note is read; the cut string, or the lines in a CMap pypdf does not implement, are U+FFFD in their
        places: as many as pypdf would have written (the cut string's two whole codes and the cut byte; each line's
        bytes read two a character)."""
        cjk = shapes.composite('HYSMyeongJo-Medium', encoding='/KSCms-UHC-H', descendant=8, descriptor=9,
                               ordering='Korea1', cid_type='CIDFontType0', cid_to_gid='')
        for label, data, marked in (
                ('cut string', shapes.beside_plain_page('BT /F2 11 Tf 72 600 Td <00410042FF> Tj ET',
                                                        shapes.identity_font()), ['\ufffd' * 3]),
                ('unimplemented CMap', shapes.beside_plain_page(shapes.lines(shapes.CJK_TEXT, top=600, font='/F2'), cjk),
                 ['\ufffd' * -(-len(line) // 2) for line in shapes.CJK_TEXT])):
            with self.subTest(label):
                result = extract(data)
                self.assertEqual((result.status, result.messages), ('partial', (unread_text(result, 2),)))
                self.assertEqual(result.text.count(shapes.NOTE_TEXT), 2)
                self.assertEqual(result.text.replace(shapes.NOTE_TEXT, '').split(), marked)


class ReplacementCharacterNoticeTests(unittest.TestCase):
    """n-4, n-5: U+FFFD in what a page returns is named however it got there (a ToUnicode, a value stream that is not
    UTF-8, a literal one); a failed result returns no text, so it never carries that notice."""

    def test_u_fffd_in_the_block_is_named(self):
        names = [name for name in SHAPES if name.startswith('n-5 ')] + ['TXT-1 stamp ToUnicode gives FFFD']
        for name in names:
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual(result.status, 'ok')
                self.assertIn('\ufffd', result.text)
                self.assertEqual(result.messages[0], INVALID)

    def test_a_failed_result_carries_no_invalid_text_notice(self):
        for name in ('n-4 only glyph, ToUnicode gives FFFD', 'n-4 only cut high', 'n-4 only cut low'):
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('failed', (NO_LAYER.format(n=1), NO_TEXT)))


class GlyphNameTests(unittest.TestCase):
    """TXT-3 (block), TXT-8, TXT-9, TXT-10: a glyph name reads as the Adobe Glyph List specification says, in the
    encoding's own precedence. A name standing for no character (a control or private-use code, a noncharacter, a
    form outside the specification) is counted and dropped, and alone in typed brackets it is the unread mark."""

    def test_a_mark_no_reader_can_name_is_unread_never_an_empty_box(self):
        names = ['TXT-3 /uniF00C', 'TXT-3 /uF00C', 'TXT-3 /uni0001', 'TXT-3 /uni0000',
                 'TXT-3 control: ToUnicode gives U+F00C', 'TXT-9 /u20 in brackets', 'TXT-9 /u78 in brackets']
        for name in names:
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('partial', (undecodable_note(1), UNREAD_BOX)))
                self.assertEqual(body(result.text), f'\n[?] {shapes.SNARE}')
                self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'uncertain')

    def test_names_the_glyph_list_reads(self):
        expected = {'TXT-3 control: a real check mark /uni2713': f'\n[\u2713] {shapes.SNARE}',
                    'AGL control: /uni2610 in Differences': f'\n\u2610 {shapes.SNARE}',
                    # the dictionary's /WinAnsiEncoding decides over the program's built-in encoding
                    'TXT-8 built-in /u2610 under WinAnsi': f'\nA {shapes.SNARE}',
                    'TXT-8 pre-existing: built-in /uni2610 under WinAnsi': f'\nA {shapes.SNARE}',
                    # /Differences decides over the built-in encoding: the page shows an empty box
                    'TXT-8 built-in /u2612, Differences /uni2610': f'\n\u2610 {shapes.SNARE}',
                    # a /Differences name is not looked up again as a ToUnicode code
                    'TXT-8 double lookup /uni0041': f'\nA {shapes.SNARE}',
                    'TXT-8 double lookup /uni0058': f'\nX {shapes.SNARE}'}
        for name, text in expected.items():
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertEqual(body(result.text), text)
        self.assertEqual(reading(extract(SHAPES['TXT-8 built-in /u2612, Differences /uni2610']).text,
                                 'Cold snare polypectomy'), 'negated')

    def test_names_that_stand_for_no_character_are_counted(self):
        for name in ('TXT-9 /u261', 'TXT-9 /u0x41', 'TXT-9 /u+41', 'TXT-9 /u4_1', 'TXT-10 /uni0000', 'TXT-10 /u0000',
                     'TXT-10 /u0', 'TXT-10 /uFFFF'):
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
                self.assertEqual(body(result.text), '\n Biopsy of a sessile polyp')

    def test_in_annotation_text_too(self):
        result = extract(SHAPES['box guard: FreeText Contents with a private-use mark'])
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.text.endswith(f'[PDF annotation text on page 1]\n[?] {shapes.SNARE}'), result.text)
        self.assertIn(UNREAD_BOX, result.messages)
        self.assertNotEqual(reading(result.text, 'Cold snare polypectomy'), 'negated')

    def test_the_glyph_list_rules(self):
        self.assertEqual([agl_text(name) for name in ('A', 'uni2610', 'uni00410042', 'u1F5F9', 'u2610')],
                         ['A', '\u2610', 'AB', '\U0001f5f9', '\u2610'])
        # the specification's section 2: up to the first period, '_' components ('uni0041.alt' is 'A')
        self.assertEqual([agl_text(name) for name in ('uni0041.alt', 'uni2610_uni2612', 'u2610.001', 'A.sc')],
                         ['A', '\u2610\u2612', '\u2610', 'A'])
        for name in ('u20', 'u261', 'uni261', 'uni00e9', 'u0x41', 'u+41', 'u4_1', 'uniD800', 'u110000', '.alt',
                     'u' + 'F' * 20):
            with self.subTest(name):
                self.assertIsNone(agl_text(name))
        self.assertTrue(pypdf_reads_by_number('uniF00C') and pypdf_reads_by_number('u20'))
        self.assertFalse(pypdf_reads_by_number('udieresis') or pypdf_reads_by_number('A'))
        self.assertTrue(all(undecodable(char) for char in '\x00\x01\uf00c\uffff\ufffe\ufdd0\U0010fffe'))
        self.assertFalse(any(undecodable(char) for char in 'A \t\n\u2610\ufffd'))

    def test_the_box_guard(self):
        self.assertEqual(unread_in_boxes(['[', None, ']']), {1})
        self.assertEqual(unread_in_boxes(['(', ' ', None, None, ' ', ')']), {2})
        self.assertEqual(unread_in_boxes(['[', None, 'x', ']']), set())
        self.assertEqual(unread_in_boxes(['[', None, '\n', ']']), set())
        self.assertEqual(unread_in_boxes([None, ']', '[', 'A', None, ']']), set())


class FontBuildTests(unittest.TestCase):
    """TXT-4, parser-03, parser-04, TXT-6: a font pypdf 6.21.4 no longer builds (a /BaseEncoding that is not a name,
    /W entries that are not widths, a built-in encoding name too long for a character) is read as its dictionary
    encodes it, as 6.21.2 and other readers read it, never as a U+FFFD for every byte."""

    def test_the_text_reads_as_its_encoding_says(self):
        expected = {'TXT-4 /BaseEncoding array': '\nPolypectomy of a sessile polyp',
                    'TXT-4 /BaseEncoding dictionary': '\nPolypectomy of a sessile polyp',
                    'TXT-4 /BaseEncoding indirect array': '\nPolypectomy of a sessile polyp',
                    'TXT-4 /BaseEncoding array with Differences': '\nBssessment: benign mucosa',
                    'TXT-4 symbol font /BaseEncoding array': '\n\u2741\u2742\u2743\u2744\u2745\u2746\u2747',
                    'TXT-4 /W literal string': '\nABC', 'TXT-4 /W hex string': '\nABC', 'TXT-4 /W name': '\nABC',
                    'indirect /W width': '\nABC',  # 6.21.2 failed on it and left the page unread
                    'TXT-6 font unused': '\nPolypectomy of a sessile polyp'}
        for name, text in expected.items():
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages, body(result.text)), ('ok', (), text))

    def test_a_field_drawn_in_such_a_font_shows_its_value(self):
        result = extract(SHAPES['parser-03 /BaseEncoding font in a field appearance'])
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS,)))
        self.assertTrue(result.text.endswith('[PDF form fields on page 1]\nField: Value'), result.text)

    def test_a_font_pypdf_cannot_build_is_unread_text_in_its_place(self):
        """pypdf draws the text of a font it cannot build in a stand-in font that reads every byte as U+FFFD, under
        either version: that text cannot be read, so it is U+FFFD in its place, a character for each byte, counted and
        named (round 3: never dropped); the note beside it, in Helvetica, is read."""
        for name, count in (('unbuildable: a composite font whose descendant is no dictionary', 6),
                            ('unbuildable: a simple font whose descriptor is no dictionary', 30)):
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], count),)))
                self.assertEqual(result.text.strip(), shapes.NOTE_TEXT + '\n' + '\ufffd' * count)

    def test_a_built_in_name_that_is_no_character_is_counted(self):
        result = extract(SHAPES['TXT-6 font used'])
        self.assertEqual((result.status, result.messages), ('ok', (undecodable_note(1),)))
        self.assertEqual(body(result.text), '\nPolypectomy of a sessile polyp\nA')


class CompositeEncodingTests(unittest.TestCase):
    """TXT-5: a composite font whose /Encoding is a CMap stream or a dictionary (no CMap pypdf implements) on page 2 no
    longer fails the whole document (pdffonts.kind raised TypeError outside the page's guard): that page has no usable
    text layer, and page 1 is read."""

    def test_one_page_never_fails_the_document(self):
        for name in [name for name in SHAPES if name.startswith('TXT-5 ')]:
            with self.subTest(name):
                result = extract(SHAPES[name])
                # page 2 holds only text no code of which can be read: U+FFFD in its places, so no usable text layer
                self.assertEqual((result.status, result.messages),
                                 ('partial', (NO_LAYER.format(n=2), unreadable_note([2], 78))))
                pages = [page.strip() for page in result.text.split('\n\n')]
                self.assertEqual((pages[0], set(pages[1]) - {'\n'}, pages[1].count('\ufffd')),
                                 (shapes.NOTE_TEXT, {'\ufffd'}, 78))
                with FakeOcr() as fake:
                    ocred = extract(SHAPES[name], ocr=fake.tools)
                self.assertEqual((ocred.status, ocred.ocr_pages), ('ok', (2,)))


class ParserTests(unittest.TestCase):
    """parser-08 to parser-11, and the parked documentation's pypdf-1."""

    LAST = 'Cold snare polypectomy of a 6 mm sigmoid polyp, retrieved.'

    def test_decode_parms_that_are_not_a_dictionary_on_filters_that_take_none(self):
        """parser-08: pypdf 6.21.4 ignores them and the stream decodes to its end: not damage."""
        for name in [name for name in SHAPES if name.startswith('parser-08 ') and 'Flate' not in name]:
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith(self.LAST), result.text)
        result = extract(SHAPES['parser-08 control: Flate with a number'])  # a predictor may be lost: named, as 6.21.2
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.messages[0].startswith('Page 1 is damaged'), result.messages)

    def test_encryption_key_lengths(self):
        """parser-09: a file no empty password opens whose key length the standard does not allow is named as damaged
        (6.21.2), not password-protected. parser-10: a file that opens with the empty password is read."""
        for name in ('parser-09 V1 R2 /Length 129', 'parser-09 V1 R2 /Length 1024'):
            with self.subTest(name):
                self.assertEqual(extract(SHAPES[name]).messages, (DAMAGED,))
        for name in ('parser-10 RC4 /Length 129', 'parser-10 RC4 /Length 41', 'parser-10 control: RC4 /Length 128'):
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith(self.LAST), result.text)
        self.assertEqual(extract(shapes.rc4_encrypted(128, key_bits=40)).messages, (PASSWORD,))

    def test_ccitt_content_without_height_shows_nothing(self):
        """parser-11: pypdf 6.21.4 decodes it (to bytes that draw nothing); the page's own text is all it shows."""
        for name in ('parser-11 form', 'parser-11 content stream'):
            with self.subTest(name):
                result = extract(SHAPES[name])
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertEqual(result.text.strip(), shapes.NOTE_TEXT)

    def test_a_non_numeric_td_reads_the_strings_where_they_are_drawn(self):
        """pypdf-1: the operator is ignored, so the second string is drawn right after the first, as joined."""
        result = extract(SHAPES['pypdf-1 non-numeric TD'])
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertEqual(body(result.text), '\nCold snare polypectomyof the sigmoid polyp.')

    def test_a_memory_failure_reported_as_a_read_error_is_named_as_memory(self):
        """parser-07: pypdf 6.21.4 turns MemoryError inside a dictionary into PdfReadError ('Error reading PDF
        file.')."""
        error = PdfReadError('Error reading PDF file.')
        error.__cause__ = MemoryError()
        self.assertTrue(from_memory(error) and caused_by(error, MemoryError))
        self.assertFalse(from_memory(PdfReadError('Error reading PDF file.')))
        with mock.patch.object(child_module, 'parse', side_effect=error):
            result = child_module.guarded_parse(b'%PDF-', 'pdf', Limits(), None, time.monotonic() + 60, '/nonexistent')
        self.assertEqual((result.status, result.messages), ('failed', (child_module.MEMORY,)))
        with mock.patch('pypdf.PdfReader', side_effect=error), tempfile.TemporaryDirectory() as workdir, \
                self.assertRaises(MemoryError):
            extract_pdf(SHAPES['parser-10 control: RC4 /Length 128'], Limits(), None, time.monotonic() + 60, workdir)


class StructureLimitTests(unittest.TestCase):
    """parser-01, 02, 05, 06: pypdf 6.21.4 stops at 2,000,000 cross-reference stream entries and page-dictionary
    entries. A document past them is named as past a limit (or as having too many pages, when it has), never read
    with objects silently missing, nor called damaged. Each document takes a few seconds to read."""

    def test_cross_reference_entries(self):
        for where in ('hybrid', 'one'):
            with self.subTest(where):
                result = extract(shapes.xref_limit(where))
                self.assertEqual((result.status, result.messages), ('failed', (LIMIT_REACHED,)))
        result = extract(shapes.xref_limit('hybrid', shapes.XREF_LIMIT))  # at the limit: read, the annotation too
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION,)))
        self.assertTrue(result.text.endswith('Follow up colonoscopy in three years per synthetic plan.'))

    def test_page_entries(self):
        result = extract(shapes.page_entries(40, 52_000))
        self.assertEqual((result.status, result.messages), ('failed', (LIMIT_REACHED,)))
        result = extract(shapes.page_entries(41, 48_800))
        self.assertEqual((result.status, result.messages), ('failed', ('The PDF has 41 pages; the limit is 40.',)))

    def test_a_cross_reference_section_left_out_is_named(self):
        """A /XRefStm pypdf cannot read (here: it points at no stream) is left out with a warning: the objects it lists
        may be missing, so the result says so and is partial."""
        data = shapes.xref_limit('hybrid', 20)
        data = data.replace(b'/XRefStm ', b'/XRefStm 1', 1)  # an offset that is no cross-reference stream
        result = extract(data)
        self.assertEqual(result.status, 'partial')
        self.assertIn(SECTIONS_LOST, result.messages)


class GlyphReaderParityTests(unittest.TestCase):
    """_ING_glyphs measures each string as pypdf 6.21.4 decodes it: U+FFFD for a string its CMap cannot decode."""

    def test_the_glyph_reader_decodes_as_pypdf_does(self):
        data = shapes.with_font(shapes.lines(shapes.NOTE), shapes.identity_font())
        reader = PdfReader(__import__('io').BytesIO(data))
        font_dict = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        font = Font.from_font_resource(font_dict)
        for string in (b'\x00A\x00B\xff', b'\x00A\x00B\x41', b'\x00A\x00', b'\xd8\x00\x41\xff\xff', b'\xdc\x00\x00A',
                       b'\x00A'):
            with self.subTest(string):
                text = get_text_operands([string], list(IDENTITY), list(IDENTITY), font, ORIENTATIONS)[0]
                self.assertEqual(''.join(font.character_map.get(char, char) for char in text),
                                 ''.join(glyph[0] for glyph in _ING_glyphs(font, string)))
                self.assertEqual(decodes(font_dict, string), len(string) % 2 == 0)


class EngineTests(unittest.TestCase):
    def test_a_new_upload_records_the_new_reading(self):
        result = extract(shapes.page_pdf(shapes.lines(shapes.NOTE)))
        self.assertEqual(result.engine, {'ingest': 'cpt-studio-ingest@4', 'pypdf': '6.21.4'})
        self.assertEqual(INGEST_VERSION, 'cpt-studio-ingest@4')


if __name__ == '__main__':
    unittest.main()
