"""The reader on pypdf 6.21.4, round 4: each finding of the three-lens refutation of round 3's reader (ACCURACY-RESIDUALS.md
"pypdf 6.21.4 is taken", round 4), judged by what the document shows (interpretation 66), under round 3's rule (text that
cannot be read is never deleted) and this round's: no reading falls below the installed reader's where it read the
source right. The unread mark '[?]' is written for a glyph that cannot be read only where the row is a checklist row,
never where a check box's state governs it, and a box glyph's string of two characters is a box as one of one is.

Every document is synthetic and built in tests/support/pypdf_shapes.py from raw PDF syntax; nothing is read from disk.
The readings go through the real extraction child; the cost bound is pinned by a doubling test, in-process.
"""
from __future__ import annotations

import io
import tempfile
import time
import unittest
from unittest import mock

from pypdf import PdfReader

from studio.ingest import Limits, extract_document
from studio.ingest import pdffonts
from studio.ingest.pdf import (BOX_SLACK, _I3_Bands, _I4_lone_marks, _I4_may_hold, _I4_Readable, _ING_Rows, _Layer,
                               _placed_boxes, extract_pdf, unreadable_note)
from studio.ingest.pdfannots import Button, PageAnnotations
from studio.ingest.pdffonts import (PREDEFINED_CODE_SPACES, UNREAD, Codes, CodeSpace, box_glyphs, decode_plan,
                                    read_codes)
from tests.support import pypdf_shapes as shapes
from tests.test_ingest import FakeOcr
from tests.test_repairs_gi4_pypdf_r3 import assert_doubles
from tests.test_repairs_ingest_r2 import reading

PDF = 'application/pdf'
FFFD = '�'
FIELDS = 'Page 1 has PDF form fields; their values were read and added after the page text, labelled as form fields.'
ITEMS = ('Diabetes', 'Hypertension', 'Smoker', 'Asthma')


def extract(data: bytes, ocr=None):
    return extract_document(data, 'synthetic.pdf', PDF, ocr=ocr)


def in_process(data: bytes):
    with tempfile.TemporaryDirectory() as workdir:
        return extract_pdf(data, Limits(), None, time.monotonic() + 120, workdir)


def euc_box(code: str, y: int) -> str:
    return f'<{code}> Tj'


def mixed(one: dict, two: dict) -> bytes:
    """A ToUnicode of one-byte codes (``one``) and two-byte codes (``two``), each {code: text}, in the EUC layout."""
    def entries(pairs: dict, width: int) -> str:
        return '\n'.join(f'<{code:0{width}X}> <{text.encode("utf-16-be").hex().upper()}>'
                         for code, text in sorted(pairs.items()))
    return shapes.stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CMapName /Synthetic-UCS def\n'
                         '/CMapType 2 def\n2 begincodespacerange\n<00> <80>\n<A1A1> <FEFE>\nendcodespacerange\n'
                         f'{len(one)} beginbfchar\n{entries(one, 2)}\nendbfchar\n'
                         f'{len(two)} beginbfchar\n{entries(two, 4)}\nendbfchar\n'
                         'endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')


class BoxStringTests(unittest.TestCase):
    """R3-MEAN-1: a box glyph that cannot be read whose string holds two characters to pypdf (the box and a space, the
    box and an ideographic space, a glyph-index box and its font's space glyph, the box drawn twice for bold) is a box
    as one of one character is: round 3 wrote U+FFFD twice and read every unchecked item as affirmed history."""

    def test_two_characters_of_a_box_are_its_unread_mark(self):
        for name, shown in (('alone', euc_box),
                            ('a space', lambda code, y: f'<{code}20> Tj'),
                            ('an ideographic space', lambda code, y: f'<{code}A1A1> Tj'),
                            ('drawn twice', lambda code, y: f'<{code}> Tj 1 0 0 1 72.3 {y} Tm <{code}> Tj')):
            with self.subTest(name):
                result = extract(shapes.box_rows(shown))
                self.assertEqual(result.status, 'partial')
                self.assertIn('\n[?] Diabetes\n[?] Hypertension\n[?] Smoker\n[?] Asthma', result.text)
                self.assertEqual([reading(result.text, item) for item in ITEMS], ['uncertain'] * 4)

    def test_glyph_index_boxes_read_alike_alone_or_with_their_space(self):
        """Glyph indices name no character, so a glyph-index box cannot be told from a bullet: it is the unread mark
        only where its list shows a box that can be read (here a ZapfDingbats row), with or without its space glyph;
        else U+FFFD in its place and the item as listed, as the installed reader left it (the glyph dropped)."""
        for name, shown in (('alone', lambda code, y: f'<{shapes.GLYPH_BOXES[code]}> Tj'),
                            ('a space glyph', lambda code, y: f'<{shapes.GLYPH_BOXES[code]}0003> Tj')):
            with self.subTest(name):
                bare = extract(shapes.box_rows(shown, shapes.glyph_index_font()))
                self.assertNotIn('[?]', bare.text)
                self.assertEqual([reading(bare.text, item) for item in ITEMS], ['historical'] * 4)
                listed = extract(shapes.box_rows(shown, shapes.glyph_index_font(), readable=True))
                self.assertIn('\n[?] Diabetes\n[?] Hypertension\n[?] Smoker\n[?] Asthma\n☐Allergies', listed.text)
                self.assertEqual([reading(listed.text, item) for item in ITEMS], ['uncertain'] * 4)
                self.assertEqual(reading(listed.text, 'Allergies'), 'negated')

    def test_which_glyphs_are_a_box(self):
        euc = {'/Subtype': '/Type0', '/Encoding': pdffonts.NameObject('/EUC-H')}
        font = pdffonts.DictionaryObject({pdffonts.NameObject(key): pdffonts.NameObject(value)
                                          for key, value in euc.items()})
        for strings, expected in (([b'\xa2\xa2'], True), ([b'\xa2\xa2 '], True), ([b'\xa2\xa2\xa1\xa1'], True),
                                  ([b'\xa2\xa2', b'\xa2\xa2'], True),  # drawn twice
                                  ([b'\xa2\xa3'], False),  # the filled square: a bullet as often as a box
                                  ([b'\xa1\xa6'], False),  # the katakana middle dot: a bullet
                                  ([b'\xa2\xa2A'], False), ([b'\xa1\xa1'], False), ([b'\xa2'], False)):
            with self.subTest(strings=strings):
                self.assertEqual(box_glyphs(font, strings), expected)
        jis = pdffonts.DictionaryObject({pdffonts.NameObject('/Encoding'): pdffonts.NameObject('/H')})
        self.assertTrue(box_glyphs(jis, [b'\x22\x22']))  # JIS X 0208 row 2 cell 2, written as row and cell
        self.assertFalse(box_glyphs(pdffonts.DictionaryObject(), [b'\x22\x22']))


class BulletAndWidgetTests(unittest.TestCase):
    """R3-MEAN-2: round 3 wrote '[?]' for any lone glyph that cannot be read at the start of a line: bullets under a
    procedure list held every procedure, and printed boxes under check boxes lost the check boxes' exact states."""

    def test_a_bullet_that_cannot_be_read_is_no_box(self):
        for name, data in (('/EUC-H, one text object', shapes.bullet_rows('A1A6', shapes.euc_font())),
                           ('/EUC-H, separate strings', shapes.bullet_rows('A1A6', shapes.euc_font(), separate=True)),
                           ('glyph index', shapes.bullet_rows('0B2C', shapes.glyph_index_font())),
                           ('glyph index, separate', shapes.bullet_rows('0B2C', shapes.glyph_index_font(),
                                                                         separate=True))):
            with self.subTest(name):
                result = extract(data)
                self.assertNotIn('[?]', result.text)
                for item in shapes.PROCEDURES:
                    self.assertIn(item, result.text)
                self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'performed')
                self.assertEqual(reading(result.text, 'Biopsy'), 'performed')

    def test_a_heading_ends_the_list_a_box_shows_in(self):
        """A checklist whose boxes can be read, then a heading and a bulleted procedure list whose bullets cannot
        be read: the list of boxes ends at the heading, so the bullets are no boxes and the procedures read performed."""
        font = shapes.glyph_index_font()
        rows = ['BT /F3 11 Tf 1 0 0 1 72 704 Tm (o) Tj /F1 11 Tf 1 0 0 1 90 704 Tm (Diabetes) Tj ET',
                'BT /F3 11 Tf 1 0 0 1 72 686 Tm (n) Tj /F1 11 Tf 1 0 0 1 90 686 Tm (Hypertension) Tj ET',
                f'BT /F1 11 Tf 72 668 Td ({shapes.PERFORMED}) Tj ET']
        rows += [f'BT /F2 11 Tf 1 0 0 1 72 {650 - 18 * index} Tm <0B2C> Tj /F1 11 Tf 1 0 0 1 84 {650 - 18 * index} Tm '
                 f'({item}) Tj ET' for index, item in enumerate(shapes.PROCEDURES)]
        objects = {6: font[0], **{key: value for key, value in font.items() if key}, 10: shapes.ZAPF}
        result = extract(shapes.page_pdf(shapes.lines(shapes.INTAKE, top=740, step=18) + '\n' + '\n'.join(rows),
                                         fonts='/F1 4 0 R /F2 6 0 R /F3 10 0 R', extra=objects))
        self.assertNotIn('[?]', result.text)
        self.assertEqual(reading(result.text, 'Cold snare polypectomy'), 'performed')
        self.assertEqual(reading(result.text, 'Diabetes'), 'negated')

    def test_check_boxes_over_printed_boxes_that_cannot_be_read(self):
        for name, data in (('/EUC-H', shapes.widget_rows('A2A2', shapes.euc_font())),
                           ('glyph index', shapes.widget_rows('2610', shapes.glyph_index_font()))):
            with self.subTest(name):
                result = extract(data)
                self.assertNotIn('[?]', result.text)
                self.assertIn(f'{FFFD} ☒ Hypertension\n{FFFD} ☐ Diabetes\n{FFFD} ☒ Smoker\n{FFFD} ☐ Asthma', result.text)
                layer = result.text[:result.text.index('[PDF form fields')]
                self.assertEqual([reading(layer, item) for item in ('Hypertension', 'Diabetes', 'Smoker', 'Asthma')],
                                 ['historical', 'negated', 'historical', 'negated'])

    def test_a_check_box_on_the_row_makes_it_a_checklist_row(self):
        """A check box on a row (here one tied to nothing) makes it a checklist row: a glyph that cannot be read at
        its start is the unread mark; a check box tied to the row's label governs it instead."""
        starts = {0: (72.0, 704.0, True), 2: (90.0, 704.0, True)}
        text = f'{UNREAD} Diabetes'
        widget = mock.Mock(rect=(400.0, 702.0, 410.0, 712.0))
        self.assertEqual(_I4_lone_marks(text, starts, {}, {}, [widget]), {0: (1, '[?]')})
        self.assertEqual(_I4_lone_marks(text, starts, {}, {}, []), {})
        self.assertEqual(_I4_lone_marks(text, starts, {}, {2: (2, '\u2610 ')}, [widget]), {})  # tied: it governs
        self.assertEqual(_I4_lone_marks(f'\u2612 Smoker\n{text}', {9: starts[0], 11: starts[2]}, {}, {}, []),
                         {9: (10, '[?]')})  # another row of its list shows a box

    def test_text_under_a_check_box_is_not_beside_it(self):
        bands = _I3_Bands([(72.0, 700.0, 77.5, 715.0)])
        self.assertFalse(bands.beside((72.0, 703.0, 83.0, 714.0)))  # the printed box under it
        self.assertTrue(bands.beside((90.0, 703.0, 101.0, 714.0)))  # left of it: beside it
        self.assertTrue(bands.meets(703.0, 714.0))
        self.assertFalse(_I3_Bands([(72.0, 600.0, 77.5, 610.0)]).beside((72.0, 703.0, 83.0, 714.0)))  # another row
        many = _I3_Bands([(72.0 + 0.001 * index, 700.0, 77.0, 715.0) for index in range(1000)])
        self.assertTrue(many.beside((72.0 - BOX_SLACK, 703.0, 83.0, 714.0)))  # more than can be read: as beside


class OptionRowTests(unittest.TestCase):
    """Measured after the round's first repair (no reading below the installed reader's): a glyph that cannot be read
    before an item whose options are check boxes tied to 'Yes' and 'No' on its row (a bullet in a fillable form,
    '・ Diabetes: ☐ Yes ☒ No') was the unread mark, and the unread glyph made each unchecked option '[?]' as text
    beside it: every item held, where the installed reader (its mojibake, or nothing, in the glyph's place) read each
    by its options. The row's own boxes govern it, and text beyond a piece that can be read is no option's label."""

    ORDER = ('Hypertension', 'Diabetes', 'Smoker', 'Asthma')

    def test_a_glyph_before_an_item_whose_options_are_check_boxes(self):
        expected = ['historical', 'negated', 'historical', 'negated']  # FORM_ROWS: Yes for Hypertension and Smoker
        for printed in (False, True):  # check boxes tied to the options' words, or the options' boxes printed
            control = extract(shapes.yes_no_rows(None, None, printed=printed))
            self.assertEqual([reading(control.text, item) for item in self.ORDER], expected)
            rows = control.text.split('applies):\n', 1)[1].split('\n\n', 1)[0]  # '- Hypertension: ☒ Yes ☐ No' ...
            for name, code, font, separate in (('/EUC-H bullet', 'A1A6', shapes.euc_font(), False),
                                               ('/EUC-H bullet, separate', 'A1A6', shapes.euc_font(), True),
                                               ('glyph-index bullet', '0B2C', shapes.glyph_index_font(), False),
                                               ('/EUC-H box', 'A2A2', shapes.euc_font(), False)):
                with self.subTest(name, printed=printed):
                    result = extract(shapes.yes_no_rows(code, font, separate=separate, printed=printed))
                    self.assertNotIn('[?]', result.text)
                    if not separate:
                        self.assertIn(rows.replace('- ', f'{FFFD} '), result.text)
                    self.assertEqual([reading(result.text, item) for item in self.ORDER], expected)

    def test_the_rows_own_boxes_govern_it(self):
        text = f'{UNREAD} Diabetes: Yes No'
        starts = {0: (72.0, 704.0, True), 2: (84.0, 704.0, True)}
        widget = mock.Mock(rect=(200.0, 703.0, 211.0, 714.0))
        options = {12: (12, '☐ '), 16: (16, '☒ ')}  # the options' glyphs, written before 'Yes' and 'No'
        self.assertEqual(_I4_lone_marks(text, starts, {}, options, [widget]), {})
        self.assertEqual(_I4_lone_marks(text, starts, {}, options, [widget], [(72.0, 704.0)]), {})  # a box shape too
        self.assertEqual(_I4_lone_marks(text, starts, {}, {}, [widget]), {0: (1, '[?]')})  # a check box tied to nothing
        alone = f'{UNREAD}\nDiabetes: Yes No'  # the glyph on a line of its own: its label's line is the row's
        self.assertEqual(_I4_lone_marks(alone, starts, {}, {12: (12, '☐ ')}, [widget]), {})
        self.assertEqual(_I4_lone_marks(alone, starts, {}, {}, [widget]), {0: (2, '[?] ')})

    def test_text_beyond_a_piece_that_can_be_read_is_no_label(self):
        yes = (200.0, 703.0, 211.0, 714.0)
        row = _I4_Readable(f'{UNREAD} Diabetes: Yes',
                           _ING_Rows([(704.0, 72.0, 0, None), (704.0, 84.0, 2, None), (704.0, 215.0, 12, None)]))
        self.assertEqual(row.left_of(yes), 84.0)  # the bullet's piece cannot be read: 'Diabetes:' is the nearest
        self.assertIsNone(row.left_of((60.0, 703.0, 70.0, 714.0)))
        self.assertFalse(_I4_may_hold((72.0, 703.0, 77.5, 714.0), yes, 84.0))  # 'Diabetes:' between: no option's label
        box = (72.0, 703.0, 83.0, 714.0)
        self.assertTrue(_I4_may_hold((40.0, 703.0, 60.0, 714.0), box, None))  # nothing that can be read between
        self.assertTrue(_I4_may_hold((40.0, 703.0, 60.0, 714.0), box, 10.0))  # what can be read lies further left
        self.assertTrue(_I4_may_hold((90.0, 703.0, 100.0, 714.0), box, None))  # right of it: before its piece
        self.assertTrue(_I4_may_hold((150.0, 703.0, 160.0, 714.0), box, 10.0))  # or running on from its piece
        self.assertFalse(_I4_may_hold((72.5, 703.0, 82.5, 714.0), box, None))  # under it: its own printed box

    def test_boxes_beside_text_that_cannot_be_read_cost_a_bisection_each(self):
        """Each button asks for the nearest piece that can be read on its left once (a bisection a row), beside the
        bounded scan of the unread text on its rows it always made: twice the rows, about twice the time."""
        def placed(rows: int):
            text = '\n'.join(f'{UNREAD} Item: Yes No' for _ in range(rows))
            pieces, buttons, boxes = [], [], []
            for index in range(rows):
                y, start = 100.0 + 20 * index, index * 15
                pieces += [(start, (72.0, y, True)), (start + 2, (84.0, y, True)), (start + 8, (215.0, y, True)),
                           (start + 12, (275.0, y, True))]
                buttons += [Button((200.0, y - 1, 211.0, y + 10), False, False, 'Yes', 2 * index),
                            Button((260.0, y - 1, 271.0, y + 10), True, False, 'No', 2 * index + 1)]
                boxes += [(72.0 - 3 * k, y - 1, 77.5 - 3 * k, y + 10) for k in range(8)]  # unread text on its left
            layer = _Layer(text=text, pieces=tuple(pieces))
            return lambda: _placed_boxes(layer, PageAnnotations(widgets=buttons), boxes)
        assert_doubles(self, placed(1500), placed(3000), 'buttons beside text that cannot be read')


class CodecCodeTests(unittest.TestCase):
    """R3-MEAN-3 and R3-CAP-1: a codec string is cut into codes by its CMap's code space, so a code cut short at the
    end, a byte that starts no code, or a one-byte code the codec cannot decode alone (0x80 under the GB and Big Five
    CMaps, 0xFD-0xFF under GBpc-EUC-H) is the only code unread, never the lead byte of the next code; round 3 wrote the
    whole string as U+FFFD, or read the next code out of step. The installed reader's text, the code named."""

    def test_codes_of_a_string_its_codec_cannot_decode_whole(self):
        for codes, face, ordering, cmap, tail in (
                (b'No biopsy was taken.'.hex() + 'b0', 'STSong-Light', 'GB1', '/GBK-EUC-H', 'No biopsy was taken.�'),
                (b'No biopsy'.hex() + 'ff' + b' was taken.'.hex(), 'STSong-Light', 'GB1', '/GBK-EUC-H',
                 'No biopsy� was taken.'),
                ('a46ab87ac3e8c0cbac64' + '80' + b'Biopsy: not taken.'.hex(), 'MSung-Light', 'CNS1', '/ETen-B5-H',
                 '大腸鏡檢查�Biopsy: not taken.'),
                ('a46ab87ac3e8c0cbac64' + '80' + 'b5b2aa47a5bfb160', 'MSung-Light', 'CNS1', '/ETenms-B5-H',
                 '大腸鏡檢查�結果正常'),
                ('bde1b3a6beb5bcecb2e9' + '80' + b'Biopsy: not taken.'.hex(), 'STSong-Light', 'GB1', '/GB-EUC-H',
                 '结肠镜检查�Biopsy: not taken.'),
                ('b0e6c8a8cbf9d3d0' + 'fd' + b' 2026'.hex(), 'STSong-Light', 'GB1', '/GBpc-EUC-H', '版权所有� 2026')):
            with self.subTest(cmap=cmap, tail=tail):
                result = extract(shapes.cjk_codec_page(cmap, codes, face, ordering))
                self.assertEqual((result.status, result.messages), ('partial', (unreadable_note([1], 1),)))
                self.assertTrue(result.text.endswith('\n' + tail), result.text)
                for item in ('biopsy', 'Biopsy'):
                    if item in tail:
                        self.assertEqual(reading(result.text, item), 'negated')
        self.assertEqual(read_codes(b'\x80B', 'cp950', {}), [None, 'B'])
        self.assertEqual(read_codes(b'\x80\xa5\xbf', 'cp950', {}), [None, '正'])
        self.assertEqual(read_codes(b'\xfd\xd5\xfd', 'gb2312', {}), [None, '正'])
        self.assertEqual(read_codes(b'\x81\x30\x81\x30A', 'gb18030', {}), ['\x80', 'A'])  # a four-byte code

    def test_the_code_spaces_are_adobes(self):
        self.assertEqual(PREDEFINED_CODE_SPACES['/GBpc-EUC-H'].ranges,
                         ((1, 0x00, 0x80), (1, 0xFD, 0xFF), (2, 0xA1A1, 0xFCFE)))
        self.assertEqual(PREDEFINED_CODE_SPACES['/90ms-RKSJ-V'].ranges,
                         ((1, 0x00, 0x80), (1, 0xA0, 0xDF), (2, 0x8140, 0x9FFC), (2, 0xE040, 0xFCFC)))
        space = CodeSpace(((1, 0x00, 0x80), (2, 0x8140, 0x9FFC)))
        self.assertEqual(space.split(b'A\x81\x40\x81\x30\xff'),
                         [(b'A', True), (b'\x81\x40', True), (b'\x81', False), (b'0', True), (b'\xff', False)])
        self.assertFalse(CodeSpace.valid(2, 0x8140, 0x9F3F))  # a second byte that falls: no rectangle
        self.assertFalse(CodeSpace.valid(5, 0, 1))


class FormBlockTests(unittest.TestCase):
    """R3-MEAN-4: a page whose readable text is too short for a layer (its other text in a CMap pypdf does not
    implement) kept no form-field block: with no OCR the document failed with no text, and OCR replaced the block, so
    the exact 'Biopsy: checked' was lost. The block is read without the page's fonts: it stays, with or without OCR."""

    def test_the_block_stays_without_ocr(self):
        result = extract(shapes.short_form('/Yes'))
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.text.endswith('\n\n[PDF form fields on page 1]\nBiopsy: checked'), result.text)
        self.assertEqual(result.messages, ('Page 1 has no usable text layer and OCR is not available on this server.',
                                           unreadable_note([1], 16), FIELDS))
        self.assertEqual(reading(result.text, 'Biopsy'), 'uncertain')

    def test_the_block_stays_after_ocr(self):
        with FakeOcr() as fake:
            result = extract(shapes.short_form('/Yes'), fake.tools)
        self.assertEqual((result.status, result.method, result.ocr_pages), ('ok', 'pdf-ocr', (1,)))
        self.assertEqual(result.text, 'Synthetic OCR text for page 1: cecum reached, cold snare polypectomy.\n\n'
                                      '[PDF form fields on page 1]\nBiopsy: checked')
        self.assertIn(FIELDS, result.messages)

    def test_a_page_with_no_block_still_has_no_usable_layer(self):
        result = extract(shapes.with_font('BT /F1 11 Tf 72 740 Td (Form) Tj ET\nBT /F2 11 Tf 72 700 Td <B8A1BABA> Tj '
                                          'ET', shapes.euc_font()))
        self.assertEqual((result.status, result.text), ('failed', ''))


class PredefinedCMapTests(unittest.TestCase):
    """R3-CAP-2: a predefined CMap pypdf does not implement, with a ToUnicode: pypdf reads two bytes a code as
    UTF-16BE, which is the CMap's own split of a string of two-byte codes, so the ToUnicode gives each code exactly (the
    installed reader's text); round 3 wrote every character as U+FFFD, and a page of nothing else failed. A string of
    one- and two-byte codes is read code by code by the CMap's code space."""

    def test_two_byte_codes_read_by_the_tounicode(self):
        text = '大腸内視鏡検査：正常。'
        codes = text.encode('euc_jp')
        jis = bytes(byte & 0x7F for byte in codes)
        pairs = [(int.from_bytes(jis[index:index + 2], 'big'), char) for index, char in zip(range(0, 22, 2), text)]
        for cmap, data in (('/H', shapes.predefined_with_tounicode('/H', jis.hex(), pairs)),
                           ('/V', shapes.predefined_with_tounicode('/V', jis.hex(), pairs)),
                           ('/EUC-H', shapes.predefined_with_tounicode(
                               '/EUC-H', codes.hex(), [(code | 0x8080, char) for code, char in pairs]))):
            with self.subTest(cmap):
                result = extract(data)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('\n' + text), result.text)

    def test_one_and_two_byte_codes_read_code_by_code(self):
        text = 'Polyp 6 mm \u5207\u9664\u3002'
        codes = text.encode('euc_jp')
        one = {byte: chr(byte) for byte in set(b'Polyp 6 mm ')}
        two = {0xC0DA: '\u5207', 0xBDFC: '\u9664', 0xA1A3: '\u3002'}
        result = extract(shapes.predefined_with_tounicode('/EUC-H', codes.hex(), (), to_unicode_body=mixed(one, two)))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + text), result.text)
        del two[0xA1A3]
        missing = extract(shapes.predefined_with_tounicode('/EUC-H', codes.hex(), (), to_unicode_body=mixed(one, two)))
        self.assertEqual((missing.status, missing.messages), ('partial', (unreadable_note([1], 1),)))
        self.assertTrue(missing.text.endswith('\nPolyp 6 mm \u5207\u9664' + FFFD), missing.text)

    def test_identity_without_its_direction(self):
        """/Identity, which names no CMap, is what some producers write for Identity-H: with a ToUnicode its two-byte
        codes are read as pypdf reads them (the installed reader's text); round 3 left a page of it with no text."""
        line = 'Findings: one 6 mm sessile polyp; removed. Biopsy: not taken.'
        font = shapes.composite(encoding='/Identity', descendant=8, descriptor=9, to_unicode_ref='/ToUnicode 7 0 R')
        font[7] = shapes.to_unicode(pairs=[(ord(char), char) for char in sorted(set(line))])
        result = extract(shapes.with_font(shapes.lines(shapes.NOTE) + f'\nBT /F2 11 Tf 72 600 Td '
                                          f'<{line.encode("utf-16-be").hex()}> Tj ET', font))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + line), result.text)

    def test_without_a_tounicode_the_text_stays_unread(self):
        result = extract(shapes.cjk_codec_page('/H', '4267304b', 'Ryumin-Light', 'Japan1'))
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.text.endswith('\n' + FFFD * 2), result.text)


class EmbeddedCMapTests(unittest.TestCase):
    """R3-CAP-3: an embedded CMap of one- and two-byte codes (the RKSJ layout), or one that uses a predefined CMap,
    with a ToUnicode: pypdf reads one byte a code, which is the CMap's own split of a string of one-byte codes, so their
    ToUnicode gives each exactly (the installed reader's text); a two-byte code is read by the ToUnicode too. Round 3
    read no such CMap: every character U+FFFD, a page of nothing else failed."""

    LINE = 'Findings: one 6 mm sessile polyp; removed. Biopsy: not taken.'

    def page(self, font: dict, codes: bytes) -> bytes:
        return shapes.with_font(shapes.lines(shapes.NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{codes.hex()}> Tj ET', font)

    def test_mixed_code_lengths(self):
        pairs = [(ord(char), char) for char in sorted(set(self.LINE))]
        result = extract(self.page(shapes.embedded_cmap_font(shapes.MIXED_CODES, pairs), self.LINE.encode()))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + self.LINE), result.text)
        self.assertEqual(reading(result.text, 'Biopsy'), 'negated')
        kanji = '大腸内視鏡'.encode('cp932')
        two = [(int.from_bytes(kanji[index:index + 2], 'big'), char) for index, char in zip(range(0, 10, 2), '大腸内視鏡')]
        mixed = extract(self.page(shapes.embedded_cmap_font(shapes.MIXED_CODES, pairs + two, code_bytes=2),
                                  b'Polyp ' + kanji))
        self.assertEqual((mixed.status, mixed.messages), ('ok', ()))
        self.assertTrue(mixed.text.endswith('\nPolyp 大腸内視鏡'), mixed.text)

    def test_a_cmap_that_uses_a_predefined_one(self):
        pairs = [(ord(char), char) for char in sorted(set(self.LINE))]
        for name, cmap, extra in (('usecmap', '/Identity-H usecmap\n', ''),
                                  ('usecmap and ranges', '/Identity-H usecmap\n1 begincodespacerange\n<0000> <FFFF>\n'
                                                         'endcodespacerange\n1 begincidrange\n<0020> <007E> 32\n'
                                                         'endcidrange\n', ''),
                                  ('/UseCMap', '', '/UseCMap /Identity-H')):
            with self.subTest(name):
                font = shapes.embedded_cmap_font(cmap, pairs, code_bytes=2, extra=extra)
                result = extract(self.page(font, self.LINE.encode('utf-16-be')))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertTrue(result.text.endswith('\n' + self.LINE), result.text)
        # it uses a CMap that is not a predefined one, which is not read here: its ToUnicode's code space reads it
        used = shapes.embedded_cmap_font('/Synthetic-Other usecmap\n', pairs, code_bytes=2)
        result = extract(self.page(used, self.LINE.encode('utf-16-be')))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + self.LINE), result.text)

    def test_a_one_byte_cmap_whose_tounicode_lacks_codes_that_are_their_own_characters(self):
        """No reading below the installed reader's: where every code the ToUnicode gives is its own character (a
        simple font's text converted by Ghostscript), a code it does not give (the space, the digits, punctuation) is
        read as pypdf reads it, its own ASCII character; round 3 wrote U+FFFD for each."""
        text = 'Prior colonoscopy 2019-03-04: no biopsy.'
        result = extract(shapes.one_byte_cmap_page(text, missing=' 0123456789-:.'))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n' + text), result.text)
        hebrew = {ord(latin): chr(0x05D0 + index) for index, latin in enumerate('abcdefgh')}
        other = extract(shapes.one_byte_cmap_page('abc def gh', glyphs=hebrew, missing=' '))
        self.assertEqual(other.status, 'partial')  # its codes are not its characters: no code is guessed


class UnreadableCMapTests(unittest.TestCase):
    """An embedded CMap that cannot be read (a section never closed, no code space: R2-COST-A's shape) is read by its
    font's ToUnicode's code space, which PDF 32000-1 9.10.3 requires to be consistent with the encoding: the 'A' the
    ToUnicode gives <0041>, the installed reader's text (round 3 left it unread); with no code space there, unread."""

    def test_the_tounicode_gives_the_codes(self):
        result = extract(shapes.shared_cmap_fonts(2, unclosed=4096))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\nA\nA'), result.text)
        space = b'1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n'
        document = shapes.shared_cmap_fonts(2, unclosed=4096)
        self.assertEqual(document.count(space), 1)  # the ToUnicode's: blanked in place, every offset kept
        spaceless = document.replace(space, b' ' * len(space))
        result = extract(spaceless)
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.text.endswith(FFFD), result.text)


class ManyCMapTests(unittest.TestCase):
    """COST-MANYCMAP-1: each font carrying its own embedded CMap (a megabyte each when inflated) cost a read of it, with
    no bound on the document: 800 such fonts in 2.5 MB ran to the 240 s deadline. A document reads at most
    MAX_DOCUMENT_CMAP_BYTES of embedded CMaps; past it, a font whose CMap was not read is text that cannot be read."""

    def test_the_cmaps_a_document_reads_are_bounded(self):
        size = 900 << 10  # each under MAX_EMBEDDED_CMAP_BYTES, so each one read is parsed
        spent = {}
        for count in (12, 24):
            reader = PdfReader(io.BytesIO(shapes.many_cmaps(count, size)))
            readings = pdffonts.FontReadings()
            fonts = [font.get_object() for name, font in reader.pages[0]['/Resources']['/Font'].items()
                     if name != '/F1']
            for font in fonts:
                readings.plan(font)
            spent[count] = readings.cache[pdffonts._CMAP_SPENT][0]
            self.assertLessEqual(spent[count], pdffonts.MAX_DOCUMENT_CMAP_BYTES + size + 4096, spent)
        self.assertEqual(spent[12], spent[24])
        small, large = shapes.many_cmaps(12, size), shapes.many_cmaps(24, size)
        assert_doubles(self, lambda: in_process(small), lambda: in_process(large), 'many embedded CMaps', 2)
        result = in_process(large)  # past the bound, each font is read by its ToUnicode's code space
        self.assertEqual((result.status, result.text.rsplit('\n', 1)[1].replace(' ', '')), ('ok', 'A' * 24))
        result = in_process(shapes.many_cmaps(4, 4096))
        self.assertEqual((result.status, result.text.rsplit('\n', 1)[1].replace(' ', '')), ('ok', 'AAAA'))  # read


class PlanTests(unittest.TestCase):
    def test_codes_plans(self):
        reader = PdfReader(io.BytesIO(shapes.predefined_with_tounicode('/H', '3B6E', [(0x3B6E, '查')])))
        font = reader.pages[0]['/Resources']['/Font']['/F2'].get_object()
        plan = decode_plan(font)
        self.assertIsInstance(plan, Codes)
        self.assertEqual((plan.width, plan.texts), (2, {0x3B6E: '查'}))
        self.assertTrue(plan.whole(b'\x3b\x6e'))
        self.assertFalse(plan.whole(b'\x3b\x6e\x21\x21'))  # a code the ToUnicode does not give
        self.assertEqual(plan.read(b'\x3b\x6e\x21\x21\x80'), ['查', None, None])

    def test_codes_that_pypdf_would_pair_into_one_character(self):
        """Two two-byte codes that UTF-16BE pairs into one character (a high and a low surrogate: EUC-H D8A1 and
        DCA1, two kanji) are not read whole by pypdf (its reading is one character the ToUnicode does not give): each
        is read code by code by the ToUnicode."""
        data = shapes.predefined_with_tounicode('/EUC-H', 'd8a1dca1', [(0xD8A1, '\u8b58'), (0xDCA1, '\u5f10')])
        result = extract(data)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertTrue(result.text.endswith('\n\u8b58\u5f10'), result.text)
        reader = PdfReader(io.BytesIO(data))
        plan = decode_plan(reader.pages[0]['/Resources']['/Font']['/F2'].get_object())
        self.assertFalse(plan.whole(bytes.fromhex('d8a1dca1')))
        self.assertTrue(plan.whole(bytes.fromhex('dca1d8a1')))


if __name__ == '__main__':
    unittest.main()
