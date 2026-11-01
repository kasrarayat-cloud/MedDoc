"""The reader on pypdf 6.21.4, round 3: each finding of the three-lens refutation of round 2's reader (ACCURACY-RESIDUALS.md
"pypdf 6.21.4 is taken", round 3), judged by what the document shows (interpretation 66), under the round's rule: text
that cannot be read is never dropped. Each character pypdf would have written for it (or each code of it that cannot be
read) is U+FFFD in its place, counted and named; alone in a box, or alone at the start of a checklist row, it is the
unread mark '[?]'; and nothing that marks it is ever read right to left.

Every document is synthetic and built in tests/support/pypdf_shapes.py from raw PDF syntax; nothing is read from disk.
The readings go through the real extraction child; each cost bound is pinned by a doubling test (the work, or the time,
of twice the input is at most about twice that of the input), in-process, so a regression fails in seconds rather than
at the child's deadline.
"""
from __future__ import annotations

import io
import random
import re
import tempfile
import time
import tracemalloc
import unicodedata
import unittest
from unittest import mock

from pypdf import PdfReader, _text_extraction
from pypdf._utils import is_char_neutral, is_char_rtl
from pypdf.generic import DecodedStreamObject

from studio.ingest import Limits, extract_document
from studio.ingest import pdfannots, pdffonts
from studio.ingest.pdf import (BOX_GAP_MAX, BOX_SLACK, _decoded, _I3_Bands, _I3_unclaimed, _I4_lone_marks, _Layer,
                               _placed_boxes, extract_pdf, unreadable_note)
from studio.ingest.pdfannots import Button, PageAnnotations
from studio.ingest.pdfcontent import OptionalContent, analyse_page, readings_for
from studio.ingest.pdffonts import SPACE, UNREAD, Transcript, read_codes
from tests.support import pypdf_shapes as shapes
from tests.test_repairs_ingest_r2 import reading

PDF = 'application/pdf'
FIELDS = 'Page 1 has PDF form fields; their values were read and added after the page text, labelled as form fields.'
ANNOTATION = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
              'annotation text.')
MISMATCH = ('Page 1: a text annotation shows text that differs from its stored text; the stored text was read, so '
            'check it against the original.')
FFFD = '�'


def extract(data: bytes):
    return extract_document(data, 'synthetic.pdf', PDF, ocr=None)


def in_process(data: bytes):
    """The reader in this process (pdf.extract_pdf, not the child), so that what it calls can be counted and timed."""
    with tempfile.TemporaryDirectory() as workdir:
        return extract_pdf(data, Limits(), None, time.monotonic() + 120, workdir)


def best(work, repeat: int = 3) -> float:
    """The shortest of ``repeat`` timings of ``work()``, in seconds (the least disturbed by other load)."""
    times = []
    for _ in range(repeat):
        started = time.perf_counter()
        work()
        times.append(time.perf_counter() - started)
    return min(times)


def assert_doubles(case, small, large, label: str, repeat: int = 3) -> None:
    """Twice the input costs at most about twice as much: under three times, with 50 ms allowed for timer noise (work
    that grows with the square of the input costs four times as much). ``small`` and ``large`` are the work on the
    input and on twice the input, timed in turn, ``repeat`` times each, the shortest of each kept, so that both see the
    same load."""
    fast, slow = in_turn((small, large), repeat)
    case.assertLess(slow, 3 * fast + 0.05, f'{label}: {fast:.3f} s, then {slow:.3f} s for twice the input')


def in_turn(works, repeat: int = 3) -> list[float]:
    """The shortest of ``repeat`` timings of each of ``works``, timed one after another in each round, in seconds."""
    times = [[] for _ in works]
    for _ in range(repeat):
        for index, work in enumerate(works):
            started = time.perf_counter()
            work()
            times[index].append(time.perf_counter() - started)
    return [min(each) for each in times]


class MarkTests(unittest.TestCase):
    """RTL-1, the class: what marks text that could not be read is never right to left, in pypdf or after it."""

    def test_no_mark_is_read_right_to_left(self):
        # pypdf 6.21.4 reverses the neutral characters after a right-to-left one (_text_extraction.get_display_str):
        # U+FDD7, round 2's mark, is in its U+FB1D-U+FDFF right-to-left range
        self.assertTrue(is_char_rtl('﷗'))
        specials = _text_extraction.CUSTOM_RTL_SPECIAL_CHARS  # what pypdf reads as neutral besides its own ranges
        for char in (UNREAD, FFFD, '[', ']'):
            with self.subTest(hex(ord(char))):
                self.assertFalse(is_char_rtl(char))
                # left to right, as the installed reader's U+FFFD and mojibake were: it ends any right-to-left run
                # before it, so the punctuation after it is never reversed
                self.assertFalse(is_char_neutral(char, specials))
        # SPACE, a space in an operator the reader reads itself, is neutral, as the space it stands for is
        self.assertFalse(is_char_rtl(SPACE))
        self.assertTrue(is_char_neutral(SPACE, specials))
        self.assertFalse(is_char_rtl('?'))
        self.assertEqual(unicodedata.bidirectional(FFFD), 'ON')  # what the result holds: a neutral, never R or AL

    def test_the_notice_counts_what_stands_in_the_texts_place(self):
        """The notice counts the characters written in the text's place (as many as pypdf would have written there),
        never the text: two bytes of a CMap pypdf does not implement are one character to it."""
        self.assertEqual(unreadable_note([1], 15),
                         'Page 1 has text in a font or encoding this server cannot read as the PDF encodes it; 15 '
                         'characters stand in its place as \ufffd, or as the unread mark [?] in a box, so check the '
                         'original.')
        self.assertEqual(unreadable_note([1, 2], 1),
                         'Pages 1-2 have text in a font or encoding this server cannot read as the PDF encodes it; 1 '
                         'character stands in its place as \ufffd, or as the unread mark [?] in a box, so check the '
                         'original.')

    def test_the_internal_marks_never_reach_a_result(self):
        for data in (shapes.label_rows(), shapes.negation('euc'), shapes.box_glyph_rows(), shapes.answer_rows()):
            result = extract(data)
            self.assertFalse({UNREAD, SPACE} & set(result.text), result.text)

    def test_the_transcript_codes(self):
        """A space is SPACE, never ' ' (pypdf would measure that code by the font's space width); no code is a
        surrogate (two would pair into one character); codes are given once."""
        transcript = Transcript()
        shown = transcript.show([UNREAD, ' ', 'A', UNREAD], 0)
        self.assertEqual(len(shown), 8)
        self.assertNotIn(' ', transcript.codes)
        self.assertEqual(shown[:2], shown[6:8])
        transcript.next = 0xD7FF
        transcript.code('x')
        self.assertEqual(transcript.next, 0xE000)
        self.assertEqual(transcript.show(['A'], 5)[2:], bytes.fromhex('01000102'))  # widths 1 and 4: 5 units


class RightToLeftTests(unittest.TestCase):
    """RTL-1 (blocking): round 2 drew text it could not read as U+FDD7, which pypdf reads right to left, so the typed
    box after it, on the same row or the next line, came out reversed (' ) (', '> <', ')-('): no box, its item read as
    affirmed. The page's typed boxes read as typed; the labels are U+FFFD."""

    def test_typed_boxes_after_labels_that_cannot_be_read(self):
        for name, data in (('label left of the row', shapes.label_rows()),
                           ('one text object', shapes.label_rows(one_object=True)),
                           ('label on the line after', shapes.label_rows(label_after=True))):
            with self.subTest(name):
                result = extract(data)
                self.assertEqual((result.status, result.messages),
                                 ('partial', (unreadable_note([1], result.text.count(FFFD)),)))
                for _, item in shapes.INTAKE_ROWS:
                    self.assertIn(item, result.text)
                self.assertNotIn(') (', result.text)
                self.assertEqual([reading(result.text, item) for item in ('Diabetes', 'Smoker', 'Asthma')],
                                 ['negated'] * 3)
                self.assertEqual(reading(result.text, 'Hypertension'), 'historical')

    def test_right_to_left_words_in_an_operator_read_here_keep_their_order(self):
        """Hebrew words in a font whose embedded one-byte CMap's ToUnicode does not give one code: the reader reads
        the operator itself, its spaces SPACE, and the words come out in the order pypdf writes them when it reads
        the whole operator (the installed reader: 'ז והד גבא' and its guess 'h' after them). SPACE read left to
        right ended each word's run, so the words came out in the wrong order ('גבא והד ז')."""
        hebrew = {ord(latin): chr(0x05D0 + index) for index, latin in enumerate('abcdefgh')}
        whole = extract(shapes.one_byte_cmap_page('abc def gh', glyphs=hebrew))
        self.assertEqual((whole.status, whole.messages), ('ok', ()))
        self.assertTrue(whole.text.endswith('\nחז והד גבא'), whole.text)  # as pypdf reads it, right to left
        cut = extract(shapes.one_byte_cmap_page('abc def gh', glyphs=hebrew, missing='h'))
        self.assertEqual((cut.status, cut.messages), ('partial', (unreadable_note([1], 1),)))
        self.assertTrue(cut.text.endswith('\nז והד גבא' + FFFD), cut.text)

    def test_answers_in_parentheses(self):
        result = extract(shapes.answer_rows())
        self.assertIn('H. pylori\n���\n(-)\nStool occult blood\n����\n(+)', result.text)

    def test_a_typed_box_round_a_mark_that_cannot_be_read(self):
        """'(' + a mark that cannot be read + ') Hypertension': the unread mark '(?)', its space kept (round 2 reversed
        ') ' and wrote '(?)Hypertension')."""
        content = shapes.lines(shapes.NOTE) + '\nBT /F1 11 Tf 72 600 Td (\\() Tj /F2 11 Tf (Xx) Tj /F1 11 Tf (\\) Hypertension) Tj ET'
        result = extract(shapes.with_font(content, shapes.euc_font()))
        self.assertTrue(result.text.endswith('\n(?) Hypertension'), result.text)
        self.assertEqual(reading(result.text, 'Hypertension'), 'uncertain')


class NeverDroppedTests(unittest.TestCase):
    """DROP-NEG-1: round 2 dropped an operator it could not read, so 'Biopsy was ' + 'not ' (unread) + 'taken.' read
    'Biopsy was taken.': performed. Each character pypdf would have written for 'not ' is U+FFFD in its place: the
    sentence never closes up, and routing holds the biopsy (the installed reader's U+FFFD and mojibake held it too).
    The same for a word in a glyph-index font (no ToUnicode), which the installed reader and round 2 dropped as glyphs
    that name no character: 'Biopsy was taken.', performed, at status ok."""

    def test_a_negation_that_cannot_be_read_keeps_its_place(self):
        for kind, count in (('euc', 2), ('missing', 4), ('odd', 4), ('glyphs', 4)):
            with self.subTest(kind):
                result = extract(shapes.negation(kind))
                self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], count),)))
                self.assertTrue(result.text.endswith('\nBiopsy was ' + FFFD * count + 'taken.'), result.text)
                self.assertEqual(reading(result.text, 'Biopsy'), 'uncertain')

    def test_glyph_index_text_in_an_appearance_is_never_read_as_letters(self):
        """A stamp whose appearance draws glyph indices (no ToUnicode): the installed reader and round 2 read
        pypdf's UTF-16BE reading of them, 'QRW', letters the stamp does not show, at status ok. Each is U+FFFD in
        its place, named."""
        result = extract(shapes.annotated('BT /F9 10 Tf 2 4 Td <005100520057> Tj ET',
                                          font=shapes.composite(descendant=23, descriptor=24)))
        self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], 3), ANNOTATION)))
        self.assertTrue(result.text.endswith('[PDF annotation text on page 1]\n' + FFFD * 3), result.text)

    def test_a_glyph_index_piece_is_kept_in_place(self):
        """The layer reader's guard: text pypdf wrote in a glyph-index font (the page walk transcribes it, so none
        reaches the layer reader so far) is unread text in its place, counted, never glyphs dropped."""
        reader = PdfReader(io.BytesIO(shapes.negation('glyphs')))
        font = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        drawn = ((), None, False, True)
        layer = _decoded([('Biopsy was ', (72.0, 600.0, True), None, None, drawn),
                          ('QRW\x03', (130.0, 600.0, True), font, None, drawn),
                          ('taken.', (150.0, 600.0, True), None, None, drawn)])
        self.assertEqual((layer.text, layer.unread, layer.undecodable), ('Biopsy was ' + UNREAD * 4 + 'taken.', 4, 0))

    def test_an_adjustment_pypdf_reads_as_a_space_stays_one(self):
        """A TJ adjustment of half a space or more between strings that cannot be read is a space, as pypdf writes
        one between the strings it reads; a smaller one is none."""
        for adjustment, between in ((-600, ' '), (-50, '')):
            with self.subTest(adjustment=adjustment):
                content = (shapes.lines(shapes.NOTE) + f'\nBT /F1 11 Tf 72 600 Td (Biopsy was ) Tj /F2 11 Tf '
                           f'[(no) {adjustment} (t )] TJ /F1 11 Tf (taken.) Tj ET')
                result = extract(shapes.with_font(content, shapes.euc_font()))
                self.assertTrue(result.text.endswith(f'\nBiopsy was {FFFD}{between}{FFFD}taken.'), result.text)


class UnreadBoxGlyphTests(unittest.TestCase):
    """DROP-BOX-1: a box glyph drawn in a font pypdf cannot read, alone at the start of a checklist row: round 2 dropped
    it, leaving each item bare (affirmed). It is the unread mark, on its item's line: held."""

    def test_a_box_glyph_that_cannot_be_read_is_the_unread_mark(self):
        for name, data in (('ReportLab rows', shapes.box_glyph_rows()), ('one text object',
                                                                         shapes.box_glyph_rows(one_object=True))):
            with self.subTest(name):
                result = extract(data)
                self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], 4),)))
                self.assertIn('\n[?] Diabetes\n[?] Hypertension\n[?] Smoker\n[?] Asthma', result.text)
                for item in ('Diabetes', 'Hypertension', 'Smoker', 'Asthma'):
                    self.assertEqual(reading(result.text, item), 'uncertain')

    def test_only_a_lone_glyph_at_the_start_of_a_row(self):
        """Round 4 (R3-MEAN-1, R3-MEAN-2) reads these rows only as checklist rows: here the glyph is drawn where an
        operator whose glyphs are a box shape starts (its origin among the box glyphs), which round 3 assumed of every
        lone glyph; tests/test_repairs_gi4_pypdf_r4.py pins the rest."""
        boxes = [(72.0, 704.0)]
        starts = {0: (72.0, 704.0, True), 2: (90.0, 704.0, True)}
        self.assertEqual(_I4_lone_marks(f'{UNREAD}\nDiabetes', starts, {}, {}, [], boxes), {0: (2, '[?] ')})
        self.assertEqual(_I4_lone_marks(f'{UNREAD} Diabetes', {0: (72.0, 704.0, True)}, {}, {}, [], boxes),
                         {0: (1, '[?]')})
        self.assertEqual(_I4_lone_marks(f'  {UNREAD}\tDiabetes', {2: (72.0, 704.0, True)}, {}, {}, [], boxes),
                         {2: (3, '[?]')})
        for text, where in ((f'Biopsy {UNREAD} taken', {}),  # not the start of its row
                            (f'{UNREAD}{UNREAD}{UNREAD} Diabetes', {}),  # three glyphs: a word, not a mark
                            (f'{UNREAD} ( ) Diabetes', {}),  # a box of its own follows
                            (f'{UNREAD}Diabetes', {}),  # no padding: part of a word
                            (f'{UNREAD}\nDiabetes', {0: (72.0, 704.0, True), 2: (90.0, 686.0, True)}),  # another row
                            (f'{UNREAD}\nDiabetes', {0: (72.0, 704.0, True), 2: (60.0, 704.0, True)}),  # left of it
                            (f'{UNREAD}\nDiabetes', {0: (72.0, 704.0, True),
                                                     2: (72.0 + BOX_GAP_MAX + 1, 704.0, True)}),  # too far
                            (f'{UNREAD}\nDiabetes', {})):  # where they are drawn is not known
            with self.subTest(repr(text), where=where):
                self.assertEqual(_I4_lone_marks(text, where, {}, {}, [], boxes), {})


class NulValueTests(unittest.TestCase):
    """NUL-VALUE-1: a stored value or /Contents of only a NUL (a terminator) names no character: the appearance, which
    viewers draw, is read (round 2 counted the NUL as text, wrote the field empty and named a disagreement); a NUL that
    ends a value is a terminator, not a glyph that does not map (round 2 named one)."""

    def test_the_appearance_shows_what_a_nul_value_does_not(self):
        for kind, tail, notice in (('field', '[PDF form fields on page 1]\nIndication: Screening colonoscopy', FIELDS),
                                   ('control', '[PDF form fields on page 1]\nIndication: Screening colonoscopy', FIELDS),
                                   ('terminated', '[PDF form fields on page 1]\nIndication: Screening colonoscopy',
                                    FIELDS),
                                   ('free text', '[PDF annotation text on page 1]\nReviewer note: polyp removed',
                                    ANNOTATION)):
            with self.subTest(kind):
                result = extract(shapes.nul_value(kind))
                self.assertEqual((result.status, result.messages), ('ok', (notice,)))
                self.assertTrue(result.text.endswith(tail), result.text)

    def test_contents_that_name_no_character_give_way_to_the_rich_text(self):
        """/Contents of only U+0001 names no character, so the stored text is the rich text (/RC), as when /Contents
        is empty; the appearance, which shows another text, is named as differing from it."""
        result = extract(shapes.nul_value('control free text'))
        self.assertEqual((result.status, result.messages), ('partial', (ANNOTATION, MISMATCH)))
        self.assertTrue(result.text.endswith('[PDF annotation text on page 1]\nReviewer note: biopsy taken'),
                        result.text)

    def test_a_nul_in_a_box_is_still_the_unread_mark(self):
        result = extract(shapes.field_page('/T (History) /V ' + shapes.utf16('[\x00] Hypertension')))
        self.assertTrue(result.text.endswith('History: [?] Hypertension'), result.text)


class OneByteCMapTests(unittest.TestCase):
    """CAP-R2-1: a composite font whose /Encoding is an embedded CMap of one-byte codes (Ghostscript's OneByteIdentityH)
    with a ToUnicode is read, one byte a code, by its ToUnicode (round 2 read no two-byte-free CMap: the page failed, or
    went to OCR); a code its ToUnicode does not give is U+FFFD, never pypdf's StandardEncoding guess."""

    NOTE = '[x] Consent signed    [ ] Allergies    [x] Hypertension'

    def test_the_text_reads_as_its_tounicode_gives_it(self):
        for offset in (0, 3):
            with self.subTest(offset=offset):
                result = extract(shapes.one_byte_cmap_page(self.NOTE, cid_offset=offset))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('\n' + self.NOTE), result.text)
        self.assertEqual(reading(result.text, 'Allergies'), 'negated')

    def test_widths_by_code_where_the_cids_are_not_the_codes(self):
        reader = PdfReader(io.BytesIO(shapes.one_byte_cmap_page('a 1', cid_offset=3)))
        font = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        copy = pdffonts._one_byte_copy(font, font['/Encoding'].get_object())
        widths = copy['/DescendantFonts'][0]['/W']
        self.assertEqual([(int(widths[index]), [float(width) for width in widths[index + 1]])
                          for index in range(0, len(widths), 2)], [(32, [250.0]), (49, [600.0]), (97, [500.0])])
        reader = PdfReader(io.BytesIO(shapes.one_byte_cmap_page('a 1')))
        font = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        self.assertIsNone(pdffonts._one_byte_copy(font, font['/Encoding'].get_object()))  # each code its own CID

    def test_the_text_is_measured_by_its_codes_widths(self):
        """Its widths are given by code (through the CMap's CIDs), so pypdf measures the line as the font draws it:
        'mm' drawn 1 pt past its end closes up with it, as on the page. Measured by the widths of the CIDs that
        equal its codes, the line seemed 12 pt wider than the font draws it, and a space came between them."""
        text = '1 2 3 4 5 6 7 8 9'
        width = (9 * 600 + 8 * 250) / 1000 * 11
        result = extract(shapes.one_byte_cmap_page(text, cid_offset=3,
                                                   after=f'BT /F1 11 Tf {72 + width + 1:.2f} 600 Td (mm) Tj ET'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + text + 'mm'), result.text)

    def test_a_code_the_tounicode_does_not_give(self):
        """Round 4: where every code the ToUnicode gives is its own character (as here), a code it does not give is
        read as pypdf reads it, its own ASCII character (the installed reader's reading); RightToLeftTests pins the
        other case, a code missing from a ToUnicode that gives other characters, which stays U+FFFD."""
        result = extract(shapes.one_byte_cmap_page('Biopsy taken: no', missing='n'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\nBiopsy taken: no'), result.text)


class CodecGapTests(unittest.TestCase):
    """CAP-R2-2: a code Python's codec for a predefined CMap lacks no longer costs the line: the CMap's own wider
    reading reads it (GBK-EUC-H's A8BF by GB 18030, as MuPDF and pdf.js read it), or that code alone is U+FFFD and
    named (ETen-B5-H's C8A1, which no codec here reads as the CMap does); the rest of the line is read. A string cut
    inside a code is not read code by code: its codes cannot be told apart (each character pypdf would write is
    U+FFFD), never mojibake."""

    def test_the_line_is_read_and_only_the_code_named(self):
        result = extract(shapes.cjk_codec_page('/GBK-EUC-H', 'bde1b3a6beb5bcecb2e920d5fdb3a320a8bf2035206d6d'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n结肠镜检查 正常 ǹ 5 mm'), result.text)
        result = extract(shapes.cjk_codec_page('/ETen-B5-H', 'b5b2b87ac3e8c0cbac6420a5bfb16020c8a12035206d6d',
                                               'MSung-Light', 'CNS1'))
        self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], 1),)))
        self.assertTrue(result.text.endswith('\n結腸鏡檢查 正常 � 5 mm'), result.text)

    def test_a_cut_string_is_read_code_by_code(self):
        """Round 4 (R3-MEAN-3): a string is cut into codes by its CMap's code space, so a code cut short at the end or
        a byte that starts no code is the only code unread (the installed reader's reading); round 3 wrote every
        character of such a string as U+FFFD. An odd-length UTF-16BE string still cannot be told apart."""
        result = extract(shapes.cjk_codec_page('/GBK-EUC-H', 'bde1b3a6beb5bcecb2e9b5'))
        self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], 1),)))
        self.assertTrue(result.text.endswith('\n结肠镜检查' + FFFD), result.text)
        self.assertEqual(read_codes(bytes.fromhex('b0a1b5'), 'gbk', {}), ['啊', None])  # cut at the end
        self.assertEqual(read_codes(bytes.fromhex('b020b0a1'), 'gbk', {}), [None, ' ', '啊'])  # no code continues
        self.assertIsNone(read_codes(bytes.fromhex('00410042ff'), 'utf-16-be', {}))  # odd UTF-16BE
        self.assertEqual(read_codes(bytes.fromhex('41a8bfb0a1'), 'gbk', {}), ['A', 'ǹ', '啊'])
        self.assertEqual(read_codes(bytes.fromhex('41c8a1b5b2'), 'cp950', {}), ['A', None, '結'])


class CostTests(unittest.TestCase):
    """R2-COST-A, R2-COST-D, R2-MEM-B, R2-COST-E, R2-COST-G and the new work itself: each bound is pinned by doubling
    its input (the work, or the time, of twice the input is at most about twice that of the input)."""

    @staticmethod
    def cmap(sections: int, unclosed: bool) -> DecodedStreamObject:
        stream = DecodedStreamObject()
        body = ('1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n'
                + '1 begincidchar\n<0041> 1\nendcidchar\n' * sections + ('begincidchar\n<0042> 2\n' if unclosed else ''))
        stream.set_data(body.encode('ascii'))
        return stream

    @staticmethod
    def openers(size: int) -> DecodedStreamObject:
        stream = DecodedStreamObject()
        stream.set_data(b'begincidchar\n' * (size // 13))
        return stream

    def test_an_embedded_cmap_is_read_in_one_pass(self):
        """R2-COST-A: a lazy back-referencing pattern scanned to the end of the data from every unclosed section: a
        1 MiB CMap of them ran to the 240 s deadline. Read keyword by keyword, a malformed CMap costs one pass."""
        small, large = self.openers(48 * 1024), self.openers(96 * 1024)
        assert_doubles(self, lambda: pdffonts._cmap_layout(small), lambda: pdffonts._cmap_layout(large),
                       'unclosed CMap sections')
        for unclosed in (False, True):
            with self.subTest(unclosed=unclosed):
                small, large = self.cmap(8000, unclosed), self.cmap(16000, unclosed)
                self.assertEqual(pdffonts._cmap_layout(small) is None, unclosed)
                assert_doubles(self, lambda: pdffonts._cmap_layout(small), lambda: pdffonts._cmap_layout(large),
                               'embedded CMap')
        whole = self.openers(pdffonts.MAX_EMBEDDED_CMAP_BYTES)
        self.assertLess(best(lambda: self.assertIsNone(pdffonts._cmap_layout(whole)), 1), 0.5)
        # round 4: a CMap that cannot be read is read by its ToUnicode's code space (PDF 32000-1 9.10.3), here two
        # bytes a code, so each font's <0041> is the 'A' its ToUnicode gives, as the installed reader read it
        result = in_process(shapes.shared_cmap_fonts(3, unclosed=500_000))
        self.assertEqual((result.status, result.text.count(FFFD)), ('ok', 0))
        self.assertTrue(result.text.endswith('\nA\nA\nA'), result.text)

    def test_a_shared_cmap_is_read_once(self):
        """R2-COST-G: every font dictionary sharing an embedded CMap read it again (900 of them: 217 s). Doubling the
        dictionaries leaves one read."""
        for count in (10, 20):
            with self.subTest(count=count), \
                    mock.patch.object(pdffonts, '_cmap_layout', wraps=pdffonts._cmap_layout) as layouts, \
                    mock.patch.object(pdffonts, '_by_code', wraps=pdffonts._by_code) as matched:
                result = in_process(shapes.shared_cmap_fonts(count))
                self.assertEqual((result.status, result.text.count('\nA')), ('ok', count))
                self.assertEqual((layouts.call_count, matched.call_count), (1, 1))

    def test_a_shared_tounicode_is_marked_once(self):
        """R2-MEM-B: every font dictionary sharing a ToUnicode with an empty destination kept its own marked copy of it
        (48 of 32 MiB: past the memory limit). One copy a ToUnicode: doubling the dictionaries adds no copy."""
        reader = PdfReader(io.BytesIO(shapes.shared_marked_fonts(6, 1000)))
        readings = readings_for(reader)
        fonts = [font.get_object() for font in reader.pages[0]['/Resources']['/Font'].values()][1:]
        copies = [readings.reading(font)[0] for font in fonts]
        self.assertTrue(all(copy is not None for copy in copies))
        self.assertEqual(len({id(copy['/ToUnicode']) for copy in copies}), 1)
        peaks = []
        for count in (4, 8):
            data = shapes.shared_marked_fonts(count, 1 << 20)
            tracemalloc.start()
            try:
                result = in_process(data)
                peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()
            self.assertEqual(result.text.count('Polyp k'), count)
        self.assertLess(peaks[1] - peaks[0], 1 << 20, peaks)  # four more dictionaries: less than one more copy

    def test_widgets_beside_unread_text_cost_a_bisection_each(self):
        """R2-COST-D: every widget was compared with every unread operator's box (30,000 by 100,000: the deadline).
        A widget asks the boxes' bands once, by bisection."""
        rng = random.Random(20261101)
        boxes = [(0.0, y, 1.0, y + rng.uniform(0, 12)) for y in (rng.uniform(0, 700) for _ in range(500))]
        bands = _I3_Bands(boxes)
        for _ in range(500):
            y0 = rng.uniform(-20, 720)
            y1 = y0 + rng.uniform(0, 15)
            brute = any(box[1] - BOX_SLACK <= y1 and y0 <= box[3] + BOX_SLACK for box in boxes)
            self.assertEqual(bands.meets(y0, y1), brute)
        self.assertFalse(_I3_Bands([]).meets(0, 10))

        def placed(widgets: int, unread: int):
            buttons = [Button((72.0 + index % 60 * 8, 600.0, 80.0 + index % 60 * 8, 608.0), False, False, '', 1)
                       for index in range(widgets)]
            boxes = [(72.0, 60.0 + index % 400, 80.0, 64.0 + index % 400) for index in range(unread)]
            return lambda: _placed_boxes(_Layer(), PageAnnotations(widgets=buttons), boxes)
        assert_doubles(self, placed(1500, 6000), placed(3000, 12000), 'widgets beside unread text')

    def test_a_long_value_is_squeezed_once(self):
        """R2-COST-E: each widget squeezed the field's value character by character in Python (4,000 widgets of a
        350,000-character value: the deadline). The value is read and squeezed once a field, in one regular
        expression pass; the shared appearance is read once; one notice names the field."""
        totals = {}
        for widgets in (20, 40):
            with mock.patch.object(pdfannots, 'squeezed', wraps=pdfannots.squeezed) as squeezed, \
                    mock.patch.object(pdfannots, 'visible_form', wraps=pdfannots.visible_form) as appearances:
                result = in_process(shapes.long_value_widgets(widgets, 50_000))
            totals[widgets] = sum(len(call.args[0]) for call in squeezed.call_args_list)
            self.assertEqual(appearances.call_count, 1)
            self.assertEqual(result.messages.count(
                'Page 1: form field "Notes" shows text that differs from its stored value; the stored value was read, '
                'so check it against the original.'), 1)
        self.assertLess(totals[20], 50_000 + 20 * 100, totals)  # the value once, the appearance's text once
        self.assertLess(totals[40] - totals[20], 50_000, totals)
        for char in ('\x00', '\x1f', '\x7f', '\x9f', '\ue000', '\uf8ff', '\ufdd0', '\ufffe', '\U0001fffe', '\U000efffe',
                     '\U000f0000', '\U0010ffff', ' ', '\u2003', '\n'):
            self.assertEqual(pdfannots.squeezed('a' + char + 'b'), 'ab')
        self.assertEqual(pdfannots.squeezed('a\ufffd\u2610b'), 'a\ufffd\u2610b')
        text = ('Indication:screening;prepadequate;withdrawal8minutes.' * 20_000)[:1_000_000]
        whitespace = re.compile(r'\s+')
        squeezing, removing = in_turn((lambda: pdfannots.squeezed(text), lambda: whitespace.sub('', text)))
        self.assertLess(squeezing, 3 * removing + 0.01)

    def test_lone_marks_are_found_in_one_pass(self):
        small = '☐ Asthma\n' + (f'{UNREAD} Diabetes\n' * 20_000) + UNREAD * 40_000
        large = '☐ Asthma\n' + (f'{UNREAD} Diabetes\n' * 40_000) + UNREAD * 80_000
        self.assertEqual(len(_I4_lone_marks(small, {}, {}, {}, [])), 20_000)  # a list one box glyph of which shows
        assert_doubles(self, lambda: _I4_lone_marks(small, {}, {}, {}, []),
                       lambda: _I4_lone_marks(large, {}, {}, {}, []), 'lone marks')

        def unclaimed(count: int):
            marks = {10 * index: (10 * index + 1, '[?]') for index in range(count)}
            edits = {10 * index + 5: (10 * index + 6, 'x') for index in range(count)}
            return lambda: self.assertEqual(len(_I3_unclaimed(marks, edits)), count)
        assert_doubles(self, unclaimed(4000), unclaimed(8000), 'lone marks beside other readings')

    def test_transcription_grows_with_the_operators(self):
        """Each transcribed operator is a few operations in what pypdf reads; operators that draw the same text as wide
        share them (350,000 unread 'AB' strings held 1,066 MiB before: one object an operation each)."""
        small, large = shapes.unread_operators(3000), shapes.unread_operators(6000)
        self.assertEqual(in_process(small).status, 'failed')  # nothing on the page can be read: no usable layer
        assert_doubles(self, lambda: in_process(small), lambda: in_process(large), 'transcription', 2)
        for data, count in ((small, 3000), (large, 6000)):
            reader = PdfReader(io.BytesIO(data))
            operations = analyse_page(reader.pages[0], reader, OptionalContent(reader.trailer['/Root'])).operations
            shown = [operation for operation in operations if operation[1] in (b'Tj', b'Tf')]
            # each operator's own Tf, then the transcription's Tf, Tj and Tf: three objects for them all
            self.assertEqual((len(shown), len({id(operation) for operation in shown})), (4 * count, count + 3))


if __name__ == '__main__':
    unittest.main()
