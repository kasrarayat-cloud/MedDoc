"""The reader on pypdf 6.21.4, round 2: each finding of the four-lens refutation of round 1's reader (ACCURACY-RESIDUALS.md
"pypdf 6.21.4 is taken", round 2), judged by what the document shows (interpretation 66).

Every document is synthetic and built in tests/support/pypdf_shapes.py from raw PDF syntax; nothing is read from disk.
The readings go through the real extraction child (with OCR unavailable, and with stand-in OCR tools where the routing
to OCR matters); the cost findings are pinned by how often the reader works a font out, counted in-process, so a
regression fails in seconds rather than at the child's deadline.
"""
from __future__ import annotations

import tempfile
import time
import tracemalloc
import unittest
from unittest import mock

from pypdf import PdfReader
from pypdf.generic import ArrayObject, NameObject

from studio.ingest import Limits, extract_document
from studio.ingest import pdffonts
from studio.ingest.pdf import _ING_UNREAD_NOTE, UNREADABLE_TEXT, _decoded, extract_pdf
from tests.support import pypdf_shapes as shapes
from tests.test_ingest import FakeOcr
from tests.test_repairs_ingest_r2 import reading, undecodable_note

PDF = 'application/pdf'
UNREAD_BOX = _ING_UNREAD_NOTE.format(pages='Page 1', has='has')
UNREAD_TEXT = UNREADABLE_TEXT.format(pages='Page {n}', has='has')
UNREADABLE = 'Page {n} has a form field or annotation whose text could not be read.'
ANNOTATION = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
              'annotation text.')
FIELDS = ('Page {n} has PDF form fields; their values were read and added after the page text, labelled as form '
          'fields.')
BLOCK = ('Hypertension: checked\nDiabetes: not checked\nSmoker: checked\nAsthma: not checked\n'
         'Indication: Screening colonoscopy')
SNARE_TAIL = f'{shapes.PERFORMED}\n[?] {shapes.SNARE}'
CHECK_MARK = '<< /Type /Encoding /Differences [65 /mark] >>'


def extract(data: bytes, ocr=None):
    return extract_document(data, 'synthetic.pdf', PDF, ocr=ocr)


def body(text: str) -> str:
    return text.split('Interventions:', 1)[1] if 'Interventions:' in text else text


def in_process(data: bytes):
    """The reader in this process (pdf.extract_pdf, not the child), so that what it calls can be counted."""
    with tempfile.TemporaryDirectory() as workdir:
        return extract_pdf(data, Limits(), None, time.monotonic() + 120, workdir)


class BuiltInEncodingTests(unittest.TestCase):
    """F1, F2: a Type 1 program's built-in encoding decides where the font names no other encoding, also when pypdf
    6.21.4 cannot read the program (an unused name too long for a character): every code it names is read here, not
    pypdf's StandardEncoding guess; and a /Differences character is never looked up again as the code of a built-in
    'u' name."""

    def test_a_lost_program_reads_its_built_in_codes(self):
        """F1: digits and punctuation where the page shows 'Left knee 2026-10-21: biopsy.' was round 1's reading."""
        for bad in ('u' + 'F' * 20, 'uniFB01FB02', None):
            with self.subTest(bad=bad):
                result = extract(shapes.subset_rows(shapes.KNEE_ROWS, bad=bad))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertEqual(body(result.text), '\n' + '\n'.join(shapes.KNEE_ROWS))

    def test_differences_decide_over_a_lost_program(self):
        """F1, second symptom: /Differences [160 /x] over /BaseEncoding /WinAnsiEncoding is 'x', never the base's NBSP
        (an empty box, negated)."""
        font = shapes.builtin_font({160: 'u2612', 254: 'u' + 'F' * 20},
                                   encoding='<< /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [160 /x] >>')
        result = extract(shapes.with_font(shapes.performed_box('A0'), font))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith(f'[x] {shapes.SNARE}'), result.text)
        self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'performed')

    def test_a_differences_character_is_not_looked_up_as_a_built_in_code(self):
        """F2: code 201 is /Differences 'x'; the program names code 0x78 'u2610' (an empty box, by pypdf 6.21.4's
        number rule). The page shows '[x]': performed, never '[☐]' (negated)."""
        font = shapes.builtin_font({0x78: 'u2610', 0x41: 'A'}, encoding='<< /Type /Encoding /Differences [201 /x] >>')
        result = extract(shapes.with_font(shapes.performed_box('C9'), font))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith(f'[x] {shapes.SNARE}'), result.text)
        self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'performed')


class NoCharacterInABoxTests(unittest.TestCase):
    """F3, F4, F5 and the C3 rule: a glyph that names no character, or text that is not valid, alone in typed
    brackets is the unread mark '[?]' (held, named, partial), never '[]' (unchecked, negated), '[ ]' or '[�]' (a
    mark, affirmed): wherever the array holds the name, and whether its ToUnicode gives NUL, nothing, or U+FFFD."""

    def assert_unread(self, data: bytes, messages: tuple):
        result = extract(data)
        self.assertEqual((result.status, result.messages), ('partial', messages))
        self.assertTrue(result.text.endswith(SNARE_TAIL), result.text)
        self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'uncertain')

    def test_a_name_past_any_window_of_the_differences_array(self):
        """F3: /u20 (no character) after 4,096 items of /Differences: pypdf reads the whole array, and so does the
        reader. Round 1 read only the first 4,096 items, so pypdf's space reached the box: '[ ]', negated."""
        padded = '<< /Type /Encoding /Differences [' + ' '.join(['1 /space'] * 2048) + ' 65 /u20] >>'
        for encoding in (padded, '<< /Type /Encoding /Differences [65 /u20] >>'):
            with self.subTest(padded=encoding is padded):
                self.assert_unread(shapes.with_font(shapes.performed_box('41'), shapes.type3_mark(encoding)),
                                   (undecodable_note(1), UNREAD_BOX))

    def test_a_tounicode_that_gives_no_character(self):
        """F4, F3 (the box reads negated): a check mark whose ToUnicode gives <0000> (pdfkit for .notdef) or an
        empty destination, in a Type 3, a TrueType and an Identity-H font."""
        cases = {'Type 3, NUL': shapes.type3_mark(CHECK_MARK, shapes.one_byte_to_unicode([(0x41, '0000')])),
                 'Type 3, empty': shapes.type3_mark(CHECK_MARK, shapes.one_byte_to_unicode([(0x41, '')])),
                 'TrueType, NUL': shapes.truetype_mark('0000'), 'TrueType, empty': shapes.truetype_mark('')}
        for name, font in cases.items():
            with self.subTest(name):
                self.assert_unread(shapes.with_font(shapes.performed_box('41'), font),
                                   (undecodable_note(1), UNREAD_BOX))
        for destination in ('0000', ''):
            with self.subTest('Identity-H', destination=destination):
                self.assert_unread(shapes.with_font(shapes.performed_box('0041'), shapes.identity_mark(destination)),
                                   (undecodable_note(1), UNREAD_BOX))

    def test_a_tounicode_that_gives_u_fffd(self):
        """F5: libcairo's ToUnicode gives <FFFD> for a glyph with no character: alone in a box it is no mark."""
        for font, codes in ((shapes.truetype_mark('FFFD'), '41'), (shapes.identity_mark('FFFD'), '0041')):
            with self.subTest(codes):
                self.assert_unread(shapes.with_font(shapes.performed_box(codes), font), (UNREAD_BOX,))

    def test_a_padded_box_is_written_as_the_unread_mark_exactly(self):
        """'[ ' + an unread mark + ' ]' is '[?]', never '[ ? ]', which routing reads as a box that checks its item; in
        the layer and in a field's value."""
        content = (shapes.lines(shapes.NOTE[:4] + [shapes.PERFORMED]) + '\nBT /F1 11 Tf 72 620 Td ([ ) Tj /F2 11 Tf '
                   f'<41> Tj /F1 11 Tf ( ] {shapes.esc(shapes.SNARE)}) Tj ET')
        for destination in ('0000', 'FFFD'):
            with self.subTest(destination=destination):
                result = extract(shapes.with_font(content, shapes.truetype_mark(destination)))
                self.assertTrue(result.text.endswith(SNARE_TAIL), result.text)
                self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'uncertain')
        result = extract(shapes.field_page('/T (History) /V ' + shapes.utf16('[ � ] Hypertension')))
        self.assertTrue(result.text.endswith('History: [?] Hypertension'), result.text)
        self.assertEqual(reading(result.text, 'Hypertension'), 'uncertain')

    def test_in_a_field_value(self):
        """A field's value holding NUL or U+FFFD in its box: canonicalisation no longer removes the NUL before the
        block's guard sees it."""
        for char, messages in (('\x00', (undecodable_note(1), UNREAD_BOX, FIELDS.format(n=1))),
                               ('�', (UNREAD_BOX, FIELDS.format(n=1)))):
            with self.subTest(char=char):
                result = extract(shapes.field_page('/T (History) /V ' + shapes.utf16(f'[{char}] Hypertension')))
                self.assertEqual((result.status, result.messages), ('partial', messages))
                self.assertTrue(result.text.endswith('History: [?] Hypertension'), result.text)
                self.assertEqual(reading(result.text, 'Hypertension'), 'uncertain')


class GlyphNameSuffixTests(unittest.TestCase):
    """F4 (AGL): a 'uni'/'u' name with a suffix or ligature components reads by the Adobe Glyph List specification
    (section 2): up to the first period, '_' components. Round 1 dropped them ('6 characters that do not map')."""

    NAMES = '128 /uni2610.alt /uni2612.alt /uni2611.ss01 /u2610.001 /uni2610_uni2612 /uni2612.sc'
    LABELS = ['Hypertension', 'Diabetes', 'Smoker', 'Asthma', 'Allergies', 'Consent']
    BOXES = ['☐', '☒', '☑', '☐', '☐☒', '☒']

    def page(self, brackets: bool) -> bytes:
        rows = '\n'.join(
            f'BT /F1 11 Tf 72 {600 - 18 * index} Td ({"[" if brackets else ""}) Tj /F2 11 Tf <{0x80 + index:02X}> Tj '
            f'/F1 11 Tf ({"]" if brackets else ""} {label}) Tj ET' for index, label in enumerate(self.LABELS))
        return shapes.with_font(shapes.lines(shapes.NOTE[:4] + ['Medical history:']) + '\n' + rows,
                                {0: shapes.differences_font(self.NAMES)})

    def test_the_names_read_as_the_specification_says(self):
        for brackets in (True, False):
            with self.subTest(brackets=brackets):
                result = extract(self.page(brackets))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                rows = [f'[{box}] {label}' if brackets else f'{box} {label}'
                        for box, label in zip(self.BOXES, self.LABELS)]
                self.assertTrue(result.text.endswith('Medical history:\n' + '\n'.join(rows)), result.text)
                self.assertEqual(reading(result.text, 'Hypertension'), 'negated')
                self.assertNotEqual(reading(result.text, 'Diabetes'), 'negated')


class UnicodeCMapTests(unittest.TestCase):
    """CL-1: a composite font under a UTF-16 CMap pypdf does not list (MuPDF's /UniKS-UTF16-H and -V) is read: pypdf
    reads its bytes as UTF-16BE, which is what such a CMap encodes. Round 1 refused it, losing the whole page."""

    def test_a_page_in_a_utf16_cmap_reads_its_text(self):
        for cmap in ('/UniKS-UTF16-H', '/UniKS-UTF16-V'):
            with self.subTest(cmap):
                result = extract(shapes.korean_page(cmap))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertEqual(body(result.text), '\n' + shapes.KOREAN)

    def test_an_appearance_in_it_shows_its_stored_text(self):
        """No false notice that the FreeText shows other text than its /Contents."""
        result = extract(shapes.korean_free_text())
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION,)))
        self.assertTrue(result.text.endswith('Reviewer note: ' + shapes.KOREAN), result.text)

    def test_the_codec_rules(self):
        self.assertEqual([pdffonts.composite_codec({'/Encoding': NameObject(name)}) for name in (
            '/UniKS-UTF16-H', '/UniJIS2004-UTF16-V', '/UniKS-UCS2-H', '/UniJIS-UTF8-H', '/UniJIS-UTF32-H', '/EUC-H')],
            ['utf-16-be', 'utf-16-be', 'utf-16-be', None, None, None])


class EmbeddedCMapTests(unittest.TestCase):
    """CL-2: a composite font whose /Encoding is an embedded CMap of two-byte codes, with a ToUnicode (fpdf2's CID-keyed
    CFF fonts), is read through a copy with the Identity CMap: its ToUnicode gives every code, below 0x100 or not.
    pypdf reads such a font one byte a code, right only by accident below 0x100; round 1 refused it."""

    def test_the_text_reads_as_its_tounicode_gives_it(self):
        for text in ('Plan: repeat colonoscopy in 5 years; pathology to follow.',
                     'Extended: ' + ''.join(chr(code) for code in range(0x100, 0x100 + 300))):
            with self.subTest(len(text)):
                result = extract(shapes.embedded_cmap_page(text))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertEqual(body(result.text), '\n' + text)

    def test_the_copy_measures_by_code(self):
        """The copy's /W gives each code its CID's width (a space 250, the rest 500), so pypdf measures the text as the
        font draws it."""
        reader = PdfReader(__import__('io').BytesIO(shapes.embedded_cmap_page('ab a')))
        font = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        copy = pdffonts._identity_copy(font, font['/Encoding'].get_object())
        self.assertEqual(copy['/Encoding'], '/Identity-H')
        widths = copy['/DescendantFonts'][0]['/W']
        self.assertEqual([float(width) for width in widths[1]], [500.0, 500.0, 250.0])  # codes 1-3: a, b, space
        self.assertIsInstance(widths[1], ArrayObject)
        self.assertEqual(int(widths[0]), 1)


class OperatorUnitTests(unittest.TestCase):
    """CL-3, F1 (block): text pypdf cannot read as the PDF encodes it costs the operator that shows it, dropped and
    named, never the page: the rest of the page's layer, in fonts pypdf reads as the PDF encodes them, and its
    labelled form-field block (read from /V and /AS, without any font) are read, and the page is not sent to OCR."""

    def test_a_line_in_an_unimplemented_cmap_beside_correct_lines(self):
        """CL-3: ReportLab's CIDFont shape, one ASCII line under /EUC-H below a note in Helvetica."""
        for ocr in (False, True):
            with self.subTest(ocr=ocr), FakeOcr() as fake:
                result = extract(shapes.cid_line_page(), ocr=fake.tools if ocr else None)
                self.assertEqual((result.status, result.messages, result.ocr_pages),
                                 ('partial', (UNREAD_TEXT.format(n=1),), ()))
                self.assertEqual(result.text.strip(), shapes.NOTE_TEXT)

    def test_a_form_page_keeps_its_labelled_block(self):
        """F1 (block): one footer line in a font pypdf cannot build (/Widths holding a name), a font the resources
        do not hold, or an odd-length Identity-H string: the check boxes' exact states and the field's value stay."""
        for name, footer, font in (('unbuildable font', '(Form 12-B rev 3)', shapes.UNBUILDABLE_WIDTHS),
                                   ('missing font', '(Form 12-B rev 3)', None),
                                   ('odd-length Identity-H', '<0046006F0072006D0020003100>', shapes.identity_font())):
            for ocr in (False, True):
                with self.subTest(name, ocr=ocr), FakeOcr() as fake:
                    result = extract(shapes.live_form(footer, font), ocr=fake.tools if ocr else None)
                    self.assertEqual((result.status, result.messages, result.ocr_pages),
                                     ('partial', (UNREAD_TEXT.format(n=1), FIELDS.format(n=1)), ()))
                    self.assertTrue(result.text.endswith('[PDF form fields on page 1]\n' + BLOCK), result.text)
                    self.assertIn('Medical history (form check boxes):', result.text)
                    self.assertEqual(reading(result.text, 'Diabetes', 1), 'negated')

    def test_an_unchecked_box_beside_text_that_could_not_be_read_is_unsure(self):
        """The box's own label is dropped (unread): the next piece within its reach, 'Biopsy taken', may not be its
        label, so the unchecked box is written as the unread mark before it (an empty box there would negate the
        biopsy): held, named; its state stays in the block."""
        result = extract(shapes.box_beside_unread())
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.messages, (UNREAD_TEXT.format(n=1), FIELDS.format(n=1)))
        self.assertIn('[?] Biopsy taken', result.text)
        self.assertTrue(result.text.endswith('[PDF form fields on page 1]\nConsent: not checked'), result.text)
        self.assertEqual(reading(result.text, 'Biopsy'), 'uncertain')

    def test_the_form_page_after_a_cover_page(self):
        result = extract(shapes.live_form('(Form 12-B rev 3)', shapes.UNBUILDABLE_WIDTHS, pages=2))
        self.assertEqual((result.status, result.messages), ('partial', (UNREAD_TEXT.format(n=2), FIELDS.format(n=2))))
        self.assertTrue(result.text.endswith('[PDF form fields on page 2]\n' + BLOCK), result.text)


class FormWithoutResourcesTests(unittest.TestCase):
    """F2 (resourceless form): pypdf reads no text from a form XObject without resources of its own (a flattened
    field's /DR-reliant appearance, pdf-lib's flatten): no U+FFFD or mojibake can come of it, so it does not make the
    page unread (round 1: the whole page), and the reader gives it no resources of its parent's (which made pypdf read
    its text in a stand-in font, U+FFFD for every byte, when the page also held a font the reader copies)."""

    def test_the_page_reads_as_pypdf_reads_it(self):
        for symbol_font in (False, True):
            with self.subTest(symbol_font=symbol_font):
                result = extract(shapes.flattened_field(symbol_font=symbol_font))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('Medical history:\n[X] Hypertension\n[ ] Diabetes\nIndication:', result.text)
                self.assertNotIn('�', result.text)
                self.assertEqual(reading(result.text, 'Diabetes'), 'negated')

    def test_a_form_with_resources_of_its_own(self):
        """With its own font it is read; with resources that do not hold its font, its text is unread and named."""
        result = extract(shapes.flattened_field(own_resources='/Font << /Helv 4 0 R >>'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('Indication:\nScreening colonoscopy'), result.text)
        result = extract(shapes.flattened_field(own_resources='/ProcSet [/PDF /Text]'))
        self.assertEqual((result.status, result.messages), ('partial', (UNREAD_TEXT.format(n=1),)))
        self.assertNotIn('�', result.text)


class StructureLimitInFontTests(unittest.TestCase):
    """LIMIT-1: a font past pypdf's array element limit (100,000) is a font whose text cannot be read: the appearance
    or the line that shows it is unread and named, the rest of the document is read, and the document never fails on
    it ('stopped unexpectedly (LimitReachedError)' was round 1's result). A font only listed is no reason not to read
    the page (pypdf itself failed on it: the installed reader left the page unread)."""

    def test_an_annotation_appearance(self):
        result = extract(shapes.over_the_limit('annotation'))
        self.assertEqual((result.status, result.messages), ('partial', (ANNOTATION, UNREADABLE.format(n=1))))
        self.assertTrue(result.text.endswith('[PDF annotation text on page 1]\nPolyp'), result.text)

    def test_the_page_itself(self):
        for where in ('page', 'descendants'):
            with self.subTest(where):
                result = extract(shapes.over_the_limit(where))
                self.assertEqual((result.status, result.messages), ('partial', (UNREAD_TEXT.format(n=1),)))
                self.assertEqual(result.text.strip(), shapes.NOTE_TEXT)
        result = extract(shapes.over_the_limit('unused'))
        self.assertEqual((result.status, result.messages, result.text), ('ok', (), shapes.NOTE_TEXT))


class CostTests(unittest.TestCase):
    """COST-1, COST-2, MEM-1: what the reader works out about a font is worked out once a document, and what it keeps
    of a page's glyphs is only the text it writes."""

    def test_a_font_is_judged_once_not_per_string(self):
        """COST-1: 3,000 strings in a font whose /BaseFont is 200,000 characters: its decode plan and kind are worked
        out once (round 1 classified the font again for every string: minutes on such a file)."""
        data = shapes.long_base_font(200_000, 3000)
        with mock.patch.object(pdffonts, 'decode_plan', wraps=pdffonts.decode_plan) as plans, \
                mock.patch.object(pdffonts, 'kind', wraps=pdffonts.kind) as kinds:
            result = in_process(data)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + 'A' * 3000), result.text[-80:])
        self.assertLessEqual(plans.call_count, 2)  # the composite font, and Helvetica
        self.assertLessEqual(kinds.call_count, 4)

    def test_a_font_program_is_parsed_once_a_document(self):
        """COST-2: 16 fonts sharing one 512 KiB Type 1 program, on 3 pages and 20 annotation appearances: its built-in
        encoding is parsed once, and each font read once (round 1: per font, per page and per appearance)."""
        data = shapes.shared_program(16, 3, 20, 512 * 1024)
        with mock.patch.object(pdffonts, '_program_names', wraps=pdffonts._program_names) as parses, \
                mock.patch.object(pdffonts, 'font_reading', wraps=pdffonts.font_reading) as readings:
            result = in_process(data)
        self.assertEqual(result.status, 'ok')
        self.assertTrue(result.text.endswith('\nn19'), result.text[-80:])
        self.assertEqual(parses.call_count, 1)
        self.assertLessEqual(readings.call_count, 17)  # the 16 fonts and Helvetica

    def test_dropped_glyphs_are_not_kept(self):
        """MEM-1: a page of a million glyphs that name no character holds no entry per glyph while its layer is read
        (round 1 kept one for each, about 8 bytes a glyph: two thirds more memory on the largest pages)."""
        drawn = ((), None, False, True)
        pieces = [('Medical history: ', (72.0, 700.0, True), None, None, drawn),
                  ('' * 1_000_000, (72.0, 680.0, True), None, None, drawn),
                  ('[] Hypertension', (72.0, 660.0, True), None, None, drawn)]
        tracemalloc.start()
        try:
            layer = _decoded(pieces)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual((layer.text, layer.undecodable, layer.marks),
                         ('Medical history: [?] Hypertension', 1_000_001, 1))
        self.assertLess(peak, 1_000_000)


if __name__ == '__main__':
    unittest.main()
