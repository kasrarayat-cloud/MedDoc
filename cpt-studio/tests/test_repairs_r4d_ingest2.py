"""Regressions for refutation round 6, INGEST lens (repair round 4d, INGEST2).

Every rule here is hold-only: where a box's placement or state is in doubt, extraction writes the unread mark '[?]'
(routing holds the item), never a guessed state (contract-r4d section 1).

- extraction:1 (regression): in Word, a checked-box checklist in the adjacent table cell, in a text box anchored in or
  after an ordinary box-bulleted list, or a hidden checked paragraph, turned that list's bullets into '☐'. A table
  cell's boundary and a text box's boundary now end a list, and a paragraph Word does not show (its mark hidden, no
  visible text) writes no bullet and belongs to no list.
- extraction:0 (regression): an unchecked PDF box before a line that runs on into another column wrote '☐' where the
  next column sat on another baseline, its gap was padded with spaces, or its font gave no widths: '[?]' now.
- extraction:2, extraction:3 (regression): a pen tick, a field showing a value, a check box or a typed mark over a
  printed box is read where the box is drawn (inside its brackets, past leading spaces, on its own piece's baseline).
- extraction:4 (residual): two check boxes over one printed box, or one over several, are named as unread boxes, never
  as a position that could not be read.
- extraction:5 (over-hold): an unchecked box before an item whose line pypdf ends after it (its detail drawn later, on a
  line of its own) is '☐' again, as 4347acd and 9a9f403 read it.

Each document is synthetic, built here from raw WordprocessingML or raw PDF syntax, extracted with the sandboxed
extract_document, routed for real and assessed by the real engine.
"""
import unittest

from studio.gi import detect
from tests.support import docgen
from tests.test_repairs_r3_forms_docx import _escape, docx_result, level, note_paragraphs, numbering
from tests.test_repairs_r3_forms_pdf import (BIOPSY_ROW, FIELDS_NOTE, SNARE_ROW, Form, boxed_line, codes, extracted,
                                             text_line, widget_rect)
from tests.test_repairs_r4_ingest import OVERLAP, UNREAD, UNREAD_NOTE, held_unread
from tests.test_repairs_r4_ingest_docx import FORCEPS, IMPRESSION, NOTE_LINES, SNARE, unread_note
from tests.test_repairs_r4c_ingest_docx import CHECKED, SHADOWED, unread_in_lists
from tests.test_repairs_status_r2_routing import read


# --- extraction:1 -- Word box bullets: a list ends at a cell or text-box boundary -----------------------------------

def _run(text, hidden=False):
    rpr = '<w:rPr><w:vanish/></w:rPr>' if hidden else ''
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_escape(text)}</w:t></w:r>'


def _para(text, num=None, extra='', hidden=False, mark_hidden=None):
    """A paragraph: ``num`` its numbering (numId, ilvl 0); ``hidden`` w:vanish on its run and (unless ``mark_hidden``
    says otherwise) on its paragraph mark; ``extra`` runs before its text (a text box)."""
    mark = hidden if mark_hidden is None else mark_hidden
    rpr = '<w:rPr><w:vanish/></w:rPr>' if mark else ''
    numbered = f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>' if num is not None else ''
    ppr = f'<w:pPr>{numbered}{rpr}</w:pPr>' if numbered or rpr else ''
    return f'<w:p>{ppr}{extra}{_run(text, hidden) if text else ""}</w:p>'


def _cell(inner):
    return f'<w:tc><w:tcPr><w:tcW w:w="4680" w:type="dxa"/></w:tcPr>{inner}</w:tc>'


def _table(rows):
    body = ''.join('<w:tr>' + ''.join(_cell(c) for c in row) + '</w:tr>' for row in rows)
    return ('<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid><w:gridCol w:w="4680"/>'
            f'<w:gridCol w:w="4680"/></w:tblGrid>{body}</w:tbl>')


def _vml_box(inner):
    return ('<w:r><w:pict><v:shape style="position:absolute;margin-left:300pt;width:180pt;height:70pt">'
            f'<v:textbox><w:txbxContent>{inner}</w:txbxContent></v:textbox></v:shape></w:pict></w:r>')


def _wps_box(inner):
    """A floating text box as Word 2010+ saves it: a wps Choice with a VML Fallback, each holding the content."""
    choice = ('<w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" '
              'behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
              '<wp:positionH relativeFrom="column"><wp:posOffset>3810000</wp:posOffset></wp:positionH>'
              '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
              '<wp:extent cx="2286000" cy="889000"/><wp:wrapSquare wrapText="bothSides"/><wp:docPr id="1" '
              'name="Text Box 1"/><a:graphic><a:graphicData '
              'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp><wps:cNvSpPr '
              'txBox="1"/><wps:spPr/>'
              f'<wps:txbx><w:txbxContent>{inner}</w:txbxContent></wps:txbx><wps:bodyPr/></wps:wsp></a:graphicData>'
              '</a:graphic></wp:anchor></w:drawing>')
    fallback = _vml_box(inner)[len('<w:r>'):-len('</w:r>')]
    return (f'<w:r><mc:AlternateContent><mc:Choice Requires="wps">{choice}</mc:Choice>'
            f'<mc:Fallback>{fallback}</mc:Fallback></mc:AlternateContent></w:r>')


CHECKS = ('Consent signed', 'Time-out completed')


def _checks(title=False):
    return (_para('Pre-procedure checks:') if title else '') + ''.join(_para(item, 2) for item in CHECKS)


def _procedures():
    return ''.join(_para(item, 1) for item in (SNARE, FORCEPS))


def _document(body) -> bytes:
    """The round-6 note's head, then ``body``: numId 1 a Wingdings shadowed square (❑, a bullet or an empty box),
    numId 2 a Wingdings checked box (☑)."""
    head = note_paragraphs(NOTE_LINES[:4])
    return docgen.rewrite_zip(docgen.make_docx_from_body(head + body), {'word/numbering.xml': numbering(
        {0: level(0, 'bullet', SHADOWED, 'Wingdings'), 1: level(0, 'bullet', CHECKED, 'Wingdings')},
        {1: (0, ''), 2: (1, '')})})


def word_variants() -> dict:
    """The round-6 inputs (the claimant's and the verifier's shapes), and their controls."""
    v = {
        'table': _table([[_para('Pre-procedure checks'), _para('Procedures performed')], [_checks(), _procedures()]])
        + _para(IMPRESSION),
        'table swapped': _table([[_para('Procedures performed'), _para('Pre-procedure checks')],
                                 [_procedures(), _checks()]]) + _para(IMPRESSION),
        'hidden checked item': _para('Procedures performed:') + _procedures()
        + _para('Bowel preparation adequate', 2, hidden=True) + _para(IMPRESSION),
        'hidden checked item first': _para('Procedures performed:')
        + _para('Bowel preparation adequate', 2, hidden=True) + _procedures() + _para(IMPRESSION),
        # A list never runs into a cell, nor out of one, nor resumes under an id another list was given.
        'checklist right before a table': _checks() + _table([[_procedures(), _para('Sigmoid and descending colon')]])
        + _para(IMPRESSION),
        'checklist right after a table': _table([[_para('Sigmoid and descending colon'), _procedures()]]) + _checks()
        + _para(IMPRESSION),
        'checklist, then a table': _checks(title=True) + _table([[_para('Procedure'), _para('Site')],
                                                                [_procedures(), _para('Sigmoid and descending')]])
        + _para(IMPRESSION),
    }
    for kind, box in (('vml', _vml_box), ('wps', _wps_box)):
        v[f'text box in the first item ({kind})'] = (
            _para('Procedures performed:') + _para(SNARE, 1, extra=box(_checks(title=True))) + _para(FORCEPS, 1)
            + _para(IMPRESSION))
        v[f'text box after the list ({kind})'] = (
            _para('Procedures performed:') + _procedures() + _para(IMPRESSION, extra=box(_checks())))
        v[f'untitled text box in the first item ({kind})'] = (
            _para('Procedures performed:') + _para(SNARE, 1, extra=box(_checks())) + _para(FORCEPS, 1)
            + _para(IMPRESSION))
        v[f'text box in the last item ({kind})'] = (
            _para('Procedures performed:') + _para(SNARE, 1) + _para(FORCEPS, 1, extra=box(_checks()))
            + _para(IMPRESSION))
    return {name: _document(body) for name, body in v.items()}


def word_controls() -> dict:
    return {name: _document(body) for name, body in {
        'label cells': _table([[_para('Pre-procedure checks'), _checks()], [_para('Procedures performed'),
                                                                            _procedures()]]) + _para(IMPRESSION),
        'body lists': _checks(title=True) + _para('Procedures performed:') + _procedures() + _para(IMPRESSION),
        'one list in a cell': _table([[_para('Procedures performed'),
                                       _para(CHECKS[0], 2) + _procedures()]]) + _para(IMPRESSION),
        'one list in a text box': _para('Procedures performed:', extra=_wps_box(_para(CHECKS[0], 2) + _procedures()))
        + _para(IMPRESSION),
        'one list in the body': _para('Procedures performed:') + _para(CHECKS[0], 2) + _procedures()
        + _para(IMPRESSION),
        'hidden runs, mark shown': _para('Procedures performed:') + _procedures()
        + _para('Bowel preparation adequate', 2, hidden=True, mark_hidden=False) + _para(IMPRESSION),
    }.items()}


class Extraction1WordListBoundaryTests(unittest.TestCase):
    """A box bullet is a checklist's only when its own list shows a checked box; a list never runs across a table
    cell's or a text box's boundary, and a paragraph Word does not show belongs to no list."""

    def test_an_ordinary_list_beside_or_near_a_checklist_is_held(self):
        for name, data in word_variants().items():
            with self.subTest(name):
                result = docx_result(data)
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertNotIn(f'☐ {SNARE}', result.text)
                self.assertNotIn(f'☐ {FORCEPS}', result.text)
                self.assertIn(f'{UNREAD} {SNARE}', result.text)
                self.assertIn(f'{UNREAD} {FORCEPS}', result.text)
                self.assertIn(unread_in_lists(2) if 'hidden' not in name else unread_note(2), result.messages)
                for phrase in (SNARE, FORCEPS):
                    status, cues = read(result.text, phrase)
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertIn(detect.BOX_UNREAD, cues)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))

    def test_the_checklist_keeps_its_glyphs(self):
        for name, data in word_variants().items():
            if 'hidden' in name:
                continue
            with self.subTest(name):
                text = docx_result(data).text
                for item in CHECKS:
                    self.assertIn(f'☒ {item}', text)

    def test_a_paragraph_word_does_not_show_writes_no_bullet(self):
        for name in ('hidden checked item', 'hidden checked item first'):
            with self.subTest(name):
                result = docx_result(word_variants()[name])
                self.assertNotIn('☒', result.text)
                self.assertNotIn('Bowel preparation', result.text)
                self.assertIn('Not extracted from the document body: 1 run of hidden text.', result.messages)

    def test_a_hidden_mark_whose_text_shows_neither_checks_nor_negates(self):
        """A paragraph whose mark is hidden but whose text shows: Word runs its text on into the next paragraph and does
        not show its bullet as its own. A checked one does not make the next list a checklist; an unchecked one inside a
        checklist is written unread, never '☐'."""
        checked = _document(_para('Procedures performed:') + _procedures()
                            + _para('Bowel preparation adequate', 2, mark_hidden=True) + _para(IMPRESSION))
        result = docx_result(checked)
        self.assertIn(f'{UNREAD} {SNARE}', result.text)
        self.assertIn(f'{UNREAD} Bowel preparation adequate', result.text)
        self.assertNotIn('☒', result.text)
        self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))
        unchecked = _document(_para('Procedures performed:') + _para(CHECKS[0], 2)
                              + _para(SNARE, 1, mark_hidden=True) + _para(FORCEPS, 1) + _para(IMPRESSION))
        result = docx_result(unchecked)
        self.assertIn(f'{UNREAD} {SNARE}', result.text)
        self.assertNotIn(f'☐ {SNARE}', result.text)
        self.assertEqual(codes(result.text, ('45385', SNARE))[0], 'held')

    def test_a_paragraph_hidden_by_its_style_is_hidden(self):
        """The mark's w:vanish read through the paragraph style, as a run's is."""
        style = ('<w:style w:type="paragraph" w:styleId="Hidden"><w:name w:val="Hidden"/><w:rPr><w:vanish/></w:rPr>'
                 '</w:style>')
        body = (_para('Procedures performed:') + _procedures()
                + '<w:p><w:pPr><w:pStyle w:val="Hidden"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>'
                '</w:pPr><w:r><w:t>Bowel preparation adequate</w:t></w:r></w:p>' + _para(IMPRESSION))
        data = _document(body)
        import io
        import zipfile
        styles = zipfile.ZipFile(io.BytesIO(data)).read('word/styles.xml').decode('utf-8')
        data = docgen.rewrite_zip(data, {'word/styles.xml': styles.replace('</w:styles>', style + '</w:styles>')
                                         .encode('utf-8')})
        result = docx_result(data)
        self.assertNotIn('☒', result.text)
        self.assertIn(f'{UNREAD} {SNARE}', result.text)
        self.assertEqual(codes(result.text, ('45385', SNARE))[0], 'held')

    def test_a_deleted_paragraph_mark_is_read_as_accepted(self):
        """A paragraph whose mark is a tracked deletion (or moved away), read as accepted, runs on into the next: its
        checked bullet makes no list a checklist, and an unchecked one in a checklist is written unread."""
        for change in ('<w:del w:id="1" w:author="Reviewer" w:date="2026-10-21T00:00:00Z"/>',
                       '<w:moveFrom w:id="2" w:author="Reviewer" w:date="2026-10-21T00:00:00Z"/>'):
            with self.subTest(change[:10]):
                mark = (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr><w:rPr>{change}</w:rPr>'
                        '</w:pPr><w:r><w:t>Bowel preparation adequate</w:t></w:r></w:p>')
                result = docx_result(_document(_para('Procedures performed:') + _procedures() + mark
                                               + _para(IMPRESSION)))
                self.assertNotIn('☒', result.text)
                self.assertIn(f'{UNREAD} {SNARE}', result.text)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))

    def test_controls_read_as_before(self):
        """Positive controls: each list in its own row after a label cell, the body lists of round 5, and a checklist
        whose checked and unchecked items are one list (in a cell, a text box or the body) keep their readings; a
        paragraph whose runs are hidden but whose mark is shown is an empty item Word shows, bullet and all."""
        controls = word_controls()
        for name in ('label cells', 'body lists'):
            with self.subTest(name):
                result = docx_result(controls[name])
                self.assertIn(f'{UNREAD} {SNARE}', result.text)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))
        for name in ('one list in a cell', 'one list in a text box', 'one list in the body', 'hidden runs, mark shown'):
            with self.subTest(name):
                result = docx_result(controls[name])
                self.assertEqual(result.status, 'ok')
                self.assertIn(f'☐ {SNARE}', result.text)
                self.assertIn(f'☐ {FORCEPS}', result.text)
                self.assertEqual(codes(result.text, ('45385', SNARE))[0], 'excluded')


# --- extraction:0 -- an unchecked box before a line that runs on into another column ----------------------------------

SENTENCE = 'Cold snare polypectomy of the 6 mm sigmoid polyp was performed.'
ROW = 640
NO_WIDTHS = b'<< /Type /Font /Subtype /TrueType /BaseFont /SyntheticSans-NoWidths /Encoding /WinAnsiEncoding >>'
COURIER = b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>'


def _width(text, size=11, font='Helvetica'):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(text, font, size)


def column_row(mac_on=False, *, dy=0.0, right=None, pad='', lead='', font='F1', left_size=11, gap=30.0, one_bt=False,
               right_first=False, right_x=None, row_x=48.69, moderate_on=True, tail=None, za=None):
    """'Sedation:  [box] Moderate  [box] MAC' (each check box 4 pt before its word; Moderate checked) in a left
    column, and the next column's ``right`` lines ([(dy, text)], default the sentence at ``dy``) starting ``gap`` pt
    after 'MAC' ends. ``pad``/``lead``: spaces drawn after 'MAC' / before the next column's text in the same string;
    ``font``: the next column's font (MG: a TrueType font without /Widths); ``one_bt``: 'MAC' and the next column's
    first line drawn in one text object; ``right_first``: the next column drawn before the left one; ``right_x``: where
    the next column starts instead; ``row_x``: where the row of options starts; ``tail``: the operators that draw
    'MAC' and the next column, in one text object at MAC's place (instead of the lines above); ``za``: the font object
    named /ZA (default Zapf Dingbats)."""
    from tests.test_repairs_ingest_pdf import esc
    form = Form(NOTE_HEAD)
    form.objects[23] = NO_WIDTHS
    if za is not None:
        form.objects[6] = za
    x = row_x
    left = [text_line(x, ROW, 'Sedation:', size=left_size)]
    first = x + _width('Sedation:', left_size) + 8
    form.checkbox('Check Box1', (first, ROW - 3, first + 12, ROW + 9), moderate_on)
    left.append(text_line(first + 16, ROW, 'Moderate', size=left_size))
    second = first + 16 + _width('Moderate', left_size) + 10
    form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), mac_on)
    mac = second + 16
    start = mac + _width('MAC', left_size) + gap if right_x is None else right_x
    lines = right if right is not None else [(dy, SENTENCE)]
    ops = [f'BT /{font} 11 Tf {start} {ROW + d} Td ({esc(lead + t)}) Tj ET' for d, t in lines]
    if one_bt:
        d0, t0 = lines[0]
        left.append(f'BT /F1 {left_size} Tf {mac} {ROW} Td ({esc("MAC" + pad)}) Tj {start - mac} {d0} Td '
                    f'({esc(lead + t0)}) Tj ET')
        ops = ops[1:]
    elif tail is not None:
        left.append(f'BT /F1 {left_size} Tf {mac} {ROW} Td {tail} ET')
        ops = []
    else:
        left.append(f'BT /F1 {left_size} Tf {mac} {ROW} Td ({esc("MAC" + pad)}) Tj ET')
    for op in (ops + left if right_first else left + ops):
        form.line(op)
    form.line(text_line(48.69, ROW - 40, 'Tattoo:')).line(text_line(start, ROW - 40, 'Retrieval was complete.'))
    return form.build()


NOTE_HEAD = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'),
             (72, 720, 'Date of service: 2026-10-21'),
             (72, 700, 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.'),
             (72, 680, 'Findings: A 6 mm sigmoid polyp was seen.')]


def column_variants() -> dict:
    """Round 6's extraction:0 inputs and their neighbours: the next column on another baseline (as pypdf joins up to
    0.8 font sizes off, and a middle-aligned row between a wrapped cell's two lines), padded with spaces on either
    side, in a font that gives no widths, in one text object with the option, or drawn first."""
    v = {f'next column {dy:+} pt': dict(dy=dy) for dy in (-8.0, -5.0, -3.0, -2.0, -1.5, 1.5, 2.0, 3.0, 5.0, 8.0)}
    v.update({
        'middle-aligned row, wrapped cell': dict(right=[(6.5, 'Cold snare polypectomy of the 6 mm sigmoid'),
                                                        (-6.5, 'polyp was performed.')]),
        'wrapped cell drawn first': dict(right=[(6.5, 'Cold snare polypectomy of the 6 mm sigmoid'),
                                                (-6.5, 'polyp was performed.')], right_first=True),
        'left column in 9 pt, top-aligned': dict(left_size=9, dy=1.25),
        'MAC padded with 8 spaces': dict(pad=' ' * 8),
        'MAC padded with 3 spaces': dict(pad=' ' * 3, gap=12.0),
        'next column padded with 8 spaces': dict(lead=' ' * 8, gap=4.0),
        'next column in a font without widths': dict(font='MG'),
        'next column without widths, 2 pt lower': dict(font='MG', dy=-2.0),
        'one text object across baselines': dict(one_bt=True, dy=-2.0),
        'one text object, padded': dict(one_bt=True, pad=' ' * 8),
        # the options in the right column, drawn first; the sentence in the left column, drawn after them
        'next column drawn left of the option, after it': dict(row_x=400.0, right_x=48.69),
    })
    return v


class Extraction0ColumnOnAnotherBaselineTests(unittest.TestCase):
    """An unchecked box before a text line that runs on into another column writes '[?]', whatever baseline the next
    column sits on, however its gap is padded, and whether or not its font gives widths: never '☐'."""

    def test_the_next_column_is_never_negated(self):
        import re
        for name, arguments in column_variants().items():
            with self.subTest(name):
                result = extracted(column_row(**arguments))
                self.assertIsNone(re.search(r'☐ MAC[^\n]', result.text), result.text)  # nothing it does not govern
                if name != 'wrapped cell drawn first':  # there pypdf ends the line at 'MAC': '☐ MAC' governs MAC alone
                    self.assertIn(f'{UNREAD} MAC', result.text)
                self.assertIn('☒ Moderate', result.text)
                self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_a_checked_last_option_keeps_its_glyph(self):
        for name in ('next column -2.0 pt', 'middle-aligned row, wrapped cell', 'MAC padded with 8 spaces',
                     'next column in a font without widths'):
            with self.subTest(name):
                text = extracted(column_row(True, **column_variants()[name])).text
                self.assertIn('☒ MAC', text)
                self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_controls_keep_their_glyphs(self):
        """The option alone on its line, the next column on a line of its own (beyond pypdf's join), and an option
        written word by word (a trailing space each, in Helvetica and in Courier) keep '☐'."""
        from tests.test_repairs_ingest_pdf import esc
        text = extracted(column_row(right=[])).text
        self.assertIn('Sedation: ☒ Moderate ☐ MAC', text)
        for name in ('next column -2.0 pt', 'middle-aligned row, wrapped cell', 'MAC padded with 8 spaces',
                     'next column in a font without widths', 'one text object across baselines'):
            with self.subTest(name):  # an unchecked first option: its line goes on with the next option's box
                text = extracted(column_row(**column_variants()[name], moderate_on=False)).text
                self.assertIn(f'Sedation: ☐ Moderate {UNREAD} MAC', text)
        text = extracted(column_row(dy=-14.0)).text  # (held by routing's own rule for a generic unchecked field)
        self.assertIn('Sedation: ☒ Moderate ☐ MAC\n', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        for font, name in (('F1', 'Helvetica'), ('ZA', 'Courier')):
            with self.subTest(font):
                form = Form(NOTE_HEAD)
                form.objects[6] = COURIER
                form.line(text_line(72, ROW, 'Interventions:'))
                box = 72 + _width('Interventions:') + 8
                form.checkbox('Check Box1', (box, ROW - 3, box + 12, ROW + 9), True)
                form.line(text_line(box + 16, ROW, 'Biopsy'))
                second = box + 16 + _width('Biopsy') + 10
                form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
                words = ['Cold ', 'snare ', 'polypectomy']
                strings = ' '.join(f'({esc(word)}) Tj' for word in words)
                form.line(f'BT /{font} 11 Tf {second + 16} {ROW} Td {strings} ET')
                text = extracted(form.build()).text
                self.assertIn('☐ Cold snare polypectomy', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')


# --- extraction:2 -- a tick over a printed box placed by its own piece, not its line's start ------------------------

def joined_tick(*, wrap, dy=6.0, tick=True, size=10):
    """'Details' in a left column at baseline 640 - dy, and 'Interventions: [ ] Cold snare polypectomy' in one text
    object at (150, 640): pypdf joins them into one line that starts at 'Details'. An ink tick over the '[ ]' only. The
    page is drawn through a form XObject (``wrap``) or by itself."""
    from tests.test_repairs_r4c_ingest_marks import annotate
    form = Form(NOTE_HEAD, wrap=wrap)
    form.line(text_line(72, ROW - dy, 'Details', size=size))
    form.line(text_line(150, ROW, 'Interventions: [ ] Cold snare polypectomy', size=size))
    x = 150 + _width('Interventions: ', size)
    if tick:
        annotate(form, 'tick', (x + 0.5, ROW - 2, x + 7.5, ROW + 9))
    return form.build()


def indented_tick(*, wrap, lead=4, tick=True, row='snare'):
    """A plain-text note in Courier 10, one string per line, the checklist indented inside its strings ('    [ ] Cold
    snare polypectomy'); an ink tick over the brackets of the snare's (or the biopsy's) box."""
    from tests.test_repairs_r4c_ingest_marks import annotate
    form = Form(NOTE_HEAD, wrap=wrap)
    form.objects[6] = COURIER
    form.line(text_line(72, 660, 'Interventions:', font='ZA', size=10))
    form.line(text_line(72, 650, ' ' * lead + '[ ] Biopsy', font='ZA', size=10))
    form.line(text_line(72, 640, ' ' * lead + '[ ] Cold snare polypectomy', font='ZA', size=10))
    x, y = 72 + 6 * lead, 640 if row == 'snare' else 650
    if tick:
        annotate(form, 'tick', (x + 1, y - 2, x + 12, y + 7.5))  # within its own 10 pt line
    return form.build()


class Extraction2TickOverABoxInsideItsLineTests(unittest.TestCase):
    """A pen tick over a printed box is placed where the box is drawn: by the piece that draws it (its own baseline,
    from its own start), not by the start of a line pypdf joined from another column, and past the whitespace its
    string opens with; on a page drawn through a form XObject and on the page itself."""

    def test_a_tick_over_a_box_inside_a_joined_line_is_unread(self):
        for wrap in (True, False):
            for dy in (2.0, 4.0, 6.0, 8.0):
                with self.subTest(wrap=wrap, dy=dy):
                    result = extracted(joined_tick(wrap=wrap, dy=dy))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    self.assertIn(f'Interventions: {UNREAD} Cold snare polypectomy', result.text)
                    self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_a_tick_over_an_indented_box_is_unread(self):
        for wrap in (True, False):
            for lead in (1, 4):
                with self.subTest(wrap=wrap, lead=lead):
                    result = extracted(indented_tick(wrap=wrap, lead=lead))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    self.assertIn(f'{UNREAD} Cold snare polypectomy', result.text)
                    self.assertIn('[ ] Biopsy', result.text)
                    self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_controls_without_a_tick_over_the_box(self):
        """No tick: the printed boxes read as before; a tick over the biopsy's box leaves the snare's printed box."""
        for wrap in (True, False):
            with self.subTest(wrap=wrap):
                text = extracted(joined_tick(wrap=wrap, tick=False)).text
                self.assertIn('Interventions: [ ] Cold snare polypectomy', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                text = extracted(indented_tick(wrap=wrap, tick=False)).text
                self.assertIn('    [ ] Cold snare polypectomy', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                text = extracted(indented_tick(wrap=wrap, row='biopsy')).text
                self.assertIn(f'{UNREAD} Biopsy', text)
                self.assertIn('    [ ] Cold snare polypectomy', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')


# --- extraction:3 -- a mark drawn inside a printed box ---------------------------------------------------------------

INSIDE = (74.9, SNARE_ROW - 3, 81.3, SNARE_ROW + 9)  # between the brackets of '[  ]' typed at x 72 in Helvetica 11


def inset(kind, printed='[  ]', checked_box=False):
    """'[  ] Biopsy' / '[  ] Cold snare polypectomy' (or Wingdings boxes, or a printed '[x]' snare) with a mark drawn
    inside the snare's box: a text field showing X or ✔, an ink tick, a checked or unchecked check box, a typed X."""
    from tests.test_repairs_r4c_ingest_marks import annotate, field_over_snare
    rect = INSIDE if printed in ('[  ]', '[x]') else (74.0, SNARE_ROW - 2, 80.5, SNARE_ROW + 8)
    if printed == '[ ]':
        rect = (74.4, SNARE_ROW - 3, 77.8, SNARE_ROW + 9)
    if kind in ('field X', 'field check', 'field empty'):
        value, glyph, font = {'field X': ('X', None, 'Helv'), 'field check': ('✔', '4', 'ZaDb'),
                              'field empty': ('', None, 'Helv')}[kind]
        return field_over_snare(printed, value, rect=rect, glyph=glyph, font=font)
    form = Form()
    if printed in ('[  ]', '[ ]', '[x]'):
        form.line(text_line(72, BIOPSY_ROW, f'{printed if printed != "[x]" else "[  ]"} Biopsy'))
        form.line(text_line(72, SNARE_ROW, f'{printed} Cold snare polypectomy'))
    else:
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed))
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', printed, checked=checked_box))
    if kind == 'tick':
        annotate(form, 'tick', rect)
    elif kind in ('check box on', 'check box off'):
        form.checkbox('Check Box1', rect, kind == 'check box on')
    elif kind == 'typed X':
        form.freetext(rect, 'X')
    elif kind == 'tick beside':
        annotate(form, 'tick', (98.0, SNARE_ROW - 2, 108.0, SNARE_ROW + 9))
    return form.build()


class Extraction3MarkInsideAPrintedBoxTests(unittest.TestCase):
    """A mark drawn inside a printed box is over it: a field showing a value or a pen tick leaves it unread; a check box
    or a typed mark whose state the printed box denies leaves it unread too (one that agrees keeps it)."""

    def test_a_mark_inside_the_brackets_holds_the_item(self):
        for printed in ('[  ]', '[ ]', 'wingdings', 'zapf'):
            for kind in ('field X', 'field check', 'tick', 'check box on', 'typed X'):
                with self.subTest(printed=printed, kind=kind):
                    result = extracted(inset(kind, printed))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    # the printed box unread (a check box tied beside the label keeps its own glyph after it)
                    self.assertRegex(result.text, r'\n\[\?\] ?(☒ )?Cold snare polypectomy')
                    self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_marks_that_agree_or_lie_beside_change_nothing(self):
        """Controls: an empty field, an unchecked check box inside an empty box, a checked one inside a printed '[x]'
        or a checked glyph, and a tick on the label beside the box: the printed boxes read as before."""
        for printed, kind, expected in (('[  ]', 'field empty', '[  ] Cold snare'),
                                        ('[  ]', 'check box off', '[  ] Cold'),
                                        ('wingdings', 'check box off', '☐ Cold'), ('[  ]', 'tick beside', '[  ] Cold'),
                                        ('[x]', 'check box on', '[x] Cold'), ('wingdings', 'tick beside', '☐ Cold')):
            with self.subTest(printed=printed, kind=kind):
                result = extracted(inset(kind, printed))
                self.assertNotIn(UNREAD_NOTE, result.messages)
                self.assertIn(expected, result.text)
        text = extracted(inset('check box on', 'wingdings', checked_box=True)).text
        self.assertIn('☒ Cold snare polypectomy', text)

    def test_a_check_box_straddling_two_printed_boxes_leaves_both_unread(self):
        """Two Wingdings boxes side by side ('☐☐ Biopsy': yes / no columns) and a checked check box starting inside the
        first and over the second: the second alone is under it by the widget geometry, but the first's drawn width
        reaches under it too and its printed state is denied, so neither is read as decided."""
        form = Form()
        form.line(f'BT /WD 11 Tf 72 {BIOPSY_ROW} Td <A8> Tj ET').line(f'BT /WD 11 Tf 84 {BIOPSY_ROW} Td <A8> Tj ET')
        form.line(text_line(102, BIOPSY_ROW, 'Biopsy'))
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', (80, BIOPSY_ROW - 3, 92, BIOPSY_ROW + 9), True)
        result = extracted(form.build())
        self.assertIn(UNREAD_NOTE, result.messages)
        self.assertNotIn(OVERLAP, result.messages)
        self.assertRegex(result.text, r'\[\?\] ?\[\?\] Biopsy')
        self.assertNotIn('☒', result.text.split('[PDF form')[0])

    def test_a_second_box_held_for_another_mark_still_makes_two_candidates(self):
        """The same straddling check box, with a pen tick over the first box (held for the tick already): the check box
        still lies over two boxes, so the box it would decide is unread too."""
        from tests.test_repairs_r4c_ingest_marks import annotate
        form = Form()
        form.line(f'BT /WD 11 Tf 72 {BIOPSY_ROW} Td <A8> Tj ET').line(f'BT /WD 11 Tf 84 {BIOPSY_ROW} Td <A8> Tj ET')
        form.line(text_line(102, BIOPSY_ROW, 'Biopsy'))
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', (80, BIOPSY_ROW - 3, 92, BIOPSY_ROW + 9), True)
        annotate(form, 'tick', (71, BIOPSY_ROW - 2, 78, BIOPSY_ROW + 8))
        result = extracted(form.build())
        self.assertRegex(result.text, r'\[\?\] ?\[\?\] Biopsy')
        self.assertNotIn('☒', result.text.split('[PDF form')[0])

    def test_a_box_held_already_is_not_named_again(self):
        """A check box over a box at a known place with an unread-position box on its row (OVERLAP, both held): the box
        held already under it adds no second note."""
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy [ ]'))
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True)
        result = extracted(form.build())
        self.assertIn(OVERLAP, result.messages)
        self.assertNotIn(UNREAD_NOTE, result.messages)
        self.assertIn(f'{UNREAD} Biopsy {UNREAD}', result.text)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True)  # and an ordinary check box over its own box
        result = extracted(form.build())
        self.assertIn(OVERLAP, result.messages)
        self.assertNotIn(UNREAD_NOTE, result.messages)
        self.assertIn(f'{UNREAD} Biopsy {UNREAD}', result.text)
        self.assertIn('☒ Cold snare polypectomy', result.text)


# --- extraction:5 -- an item's own detail on a line of its own does not hold the item -------------------------------

def detail_rows(*, joined=False, detail='Site: sigmoid colon', snare_detail='Size: 6 mm', next_column=None,
                biopsy_on=False):
    """'Interventions:', then '[box] Biopsy' and '[box] Cold snare polypectomy' (check boxes 4 pt before their items;
    the biopsy's ``biopsy_on``, the snare's checked), each item one string, with a detail 40 pt to its right on its
    baseline: drawn after all the items (pypdf puts each detail on a line of its own), or right after its item
    (``joined``: one line). ``next_column``: a sentence in the details' place instead of the biopsy's detail."""
    form = Form(NOTE_HEAD)
    rows = ((620, 'Biopsy', next_column or detail, biopsy_on), (600, 'Cold snare polypectomy', snare_detail, True))
    form.line(text_line(72, 640, 'Interventions:'))
    details = []
    for y, item, extra, on in rows:
        form.checkbox(f'Check Box{y}', (72, y - 3, 84, y + 9), on)
        form.line(text_line(88, y, item))
        op = text_line(88 + _width(item) + 40, y, extra) if extra else None
        if op and joined:
            form.line(op)
        elif op:
            details.append(op)
    for op in details:
        form.line(op)
    return form.build()


class Extraction5DetailOnItsOwnLineTests(unittest.TestCase):
    """An unchecked box before an item whose text line pypdf ends after it (the item one string, its detail drawn
    later and put on a line of its own) governs that item alone: '☐', as 4347acd and 9a9f403 read it."""

    def test_the_item_keeps_its_state(self):
        for detail in ('Site: sigmoid colon', 'Site: ____________', 'Site:', 'Jar: ____'):
            with self.subTest(detail=detail):
                text = extracted(detail_rows(detail=detail)).text
                self.assertIn('☐ Biopsy\n', text)
                self.assertIn('☒ Cold snare polypectomy\n', text)
                self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')

    def test_the_next_column_on_its_own_line_is_never_negated(self):
        text = extracted(detail_rows(next_column=SENTENCE)).text
        self.assertIn('☐ Biopsy\n', text)
        self.assertIn(f'\n{SENTENCE}', text)
        self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy of the 6 mm'))[0], 'excluded')

    def test_a_detail_joined_into_the_line_still_holds(self):
        """Control (the joined line: the detail is on the box's line, which may run on into another column): held, as
        before; and a checked box keeps its glyph."""
        text = extracted(detail_rows(joined=True)).text
        self.assertIn(f'{UNREAD} Biopsy', text)
        self.assertNotEqual(codes(text, ('45380', 'Biopsy'))[0], 'excluded')
        text = extracted(detail_rows(joined=True, next_column=SENTENCE)).text
        self.assertIn(f'{UNREAD} Biopsy', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy of the 6 mm'))[0], 'excluded')
        text = extracted(detail_rows(biopsy_on=True)).text
        self.assertIn('☒ Biopsy\n', text)

    def test_one_operator_with_more_than_one_string_still_measures_its_gaps(self):
        """The item and its detail shown by one TJ operator (one piece, several strings): the gap inside it is read as
        before, so the box is held; an item alone in a font that gives no widths is held as before (not measured)."""
        from tests.test_repairs_ingest_pdf import esc
        form = Form(NOTE_HEAD)
        form.line(text_line(72, 640, 'Interventions:'))
        form.checkbox('Check Box1', (72, 617, 84, 629), False)
        form.line(f'BT /F1 11 Tf 88 620 Td [({esc("Biopsy")}) -3600 ({esc("Site: sigmoid colon")})] TJ ET')
        text = extracted(form.build()).text
        self.assertIn(f'{UNREAD} Biopsy', text)
        form = Form(NOTE_HEAD)
        form.objects[23] = NO_WIDTHS
        form.line(text_line(72, 640, 'Interventions:'))
        form.checkbox('Check Box1', (72, 617, 84, 629), False)
        form.line(text_line(88, 620, 'Biopsy', font='MG'))
        form.line(text_line(88, 600, 'Cold snare polypectomy'))
        text = extracted(form.build()).text
        self.assertIn(f'{UNREAD} Biopsy', text)


# --- extraction:4 -- the page note names what is true about boxes under form check boxes -----------------------------

def _overlap_page(case, printed='wingdings'):
    """A checklist whose printed boxes each start a piece of page text (their positions are read), with form check
    boxes over them as ``case`` says."""
    form = Form()
    if case == 'one over a row of two':
        form.line(text_line(72, BIOPSY_ROW, 'Biopsy taken:'))
        for x, word in ((150, 'Yes'), (190, 'No')):
            form.line(boxed_line(x, BIOPSY_ROW, word, printed, gap=14))
        form.checkbox('Check Box1', (148, BIOPSY_ROW - 3, 215, BIOPSY_ROW + 9), True)
        form.line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy', printed, checked=True))
        return form.build()
    form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy', printed)).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy',
                                                                             printed))
    if case == 'two over one':
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True)
        form.checkbox('Check Box2', widget_rect(BIOPSY_ROW, 72), False)
    elif case == 'two over one, one field twice':
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True)
        form.checkbox('Check Box1 copy', widget_rect(BIOPSY_ROW), True)
    elif case == 'one over two rows':
        form.checkbox('Check Box1', (71, SNARE_ROW - 3, 83, BIOPSY_ROW + 9), True)
    form.checkbox('Check Box9', widget_rect(SNARE_ROW - 40), True)  # an unrelated check box elsewhere on the page
    return form.build()


class Extraction4OverlapWordingTests(unittest.TestCase):
    """Two form check boxes over one printed box, or one over several, leave those boxes unread (the declared hold)
    and name the page with the unread-box note: every position was read, so the page is never told a position could
    not be read."""

    def test_positions_read_are_never_reported_unread(self):
        for case in ('two over one', 'two over one, one field twice', 'one over a row of two', 'one over two rows'):
            for printed in ('wingdings', 'text font'):
                with self.subTest(case=case, printed=printed):
                    result = extracted(_overlap_page(case, printed))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertNotIn(OVERLAP, result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    self.assertIn(UNREAD, result.text)
                    if case == 'one over a row of two':
                        self.assertIn(f'Biopsy taken: {UNREAD} Yes', result.text)
                        self.assertEqual(codes(result.text, ('45380', 'Biopsy'))[0], 'held')
                    else:
                        held_unread(self, result.text, 'Biopsy')

    def test_a_position_not_read_still_names_the_overlap(self):
        """Controls: a check box over a box inside its line ('Biopsy [ ]') keeps OVERLAP, and one check box over one
        box at a known place says nothing."""
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [ ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False)
        result = extracted(form.build())
        self.assertIn(OVERLAP, result.messages)
        self.assertNotIn(UNREAD_NOTE, result.messages)
        form = Form(wrap=True)  # the page drawn through a form XObject: a check box reads no box's position there
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), True)
        result = extracted(form.build())
        self.assertIn(OVERLAP, result.messages)
        self.assertIn(f'{UNREAD} Biopsy', result.text)
        form = Form()
        form.line(boxed_line(72, BIOPSY_ROW, 'Biopsy')).line(boxed_line(72, SNARE_ROW, 'Cold snare polypectomy'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), True)
        result = extracted(form.build())
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertIn('☐ Biopsy\n☒ Cold snare polypectomy', result.text)


# --- verification of round 4d (high): the placement layer costs what the readings before it cost ---------------------

def stacked_boxes(count, *, step='0.01', tick=(500, 80, 510, 92)):
    """'Checklist:' then ``count`` typed '[ ]' boxes in one text object, each drawn 0.02 pt right of and ``step`` pt
    below the one before, so pypdf joins them into one line and one piece drawn on ``count`` baselines (``step`` None:
    every box in the one string that shows 'Checklist:', one operator); an ink tick at ``tick``, by default at the page
    foot, far from every box."""
    from tests.test_repairs_r4c_ingest_marks import annotate
    form = Form(NOTE_HEAD)
    if step is None:
        form.line(text_line(72, 600, 'Checklist:' + ' [ ]' * count, size=1))
    else:
        form.line('BT /F1 11 Tf 72 600 Td (Checklist:) Tj ' + f'0.02 -{step} Td ([ ]) Tj ' * count + 'ET')
    form.line(text_line(72, 200, 'Cold snare polypectomy of the sigmoid polyp was performed.'))
    annotate(form, 'tick', tick)
    return form.build()


class PlacementLayerCostTests(unittest.TestCase):
    """Where printed boxes are drawn is read once per piece and baseline: a piece of page text drawn on thousands of
    baselines (each operator a hundredth of a point lower) costs about what the same boxes on one baseline cost, and
    a page under the limits is never failed for memory."""

    def _placement_time(self, data):
        import gc
        import time

        from studio.ingest import pdf as pdf_module
        from tests.test_repairs_r4_ingest import placement_inputs
        layer, annotations = placement_inputs(data)
        best = text = None
        for _ in range(3):  # the best of three, each after a collection: a timing, not the collector's
            gc.collect()
            started = time.monotonic()
            text = pdf_module._placed_boxes(layer, annotations)[0]
            elapsed = time.monotonic() - started
            best = elapsed if best is None else min(best, elapsed)
        return best, text

    def test_a_piece_on_many_baselines_costs_what_one_baseline_costs(self):
        """Against the same boxes in one string (one operator, one baseline): drawn by an operator each on one
        baseline, or on a baseline each."""
        one, text = self._placement_time(stacked_boxes(1000, step=None))
        self.assertEqual(text.count('[ ]'), 1000)
        flat, text = self._placement_time(stacked_boxes(1000, step='0'))
        self.assertEqual(text.count('[ ]'), 1000)
        self.assertLess(flat, 3 * one + 0.1, (flat, one))
        many, text = self._placement_time(stacked_boxes(1000))
        self.assertEqual(text.count('[ ]'), 1000)  # the tick is far from every box
        self.assertLess(many, 3 * one + 0.1, (many, one))
        # a tick over the band those baselines fill: too many rows to read, so every printed box on the page is unread
        crossed, text = self._placement_time(stacked_boxes(1000, tick=(200, 591, 210, 598)))
        self.assertEqual(text.count(UNREAD), 1000)
        self.assertLess(crossed, 3 * one + 0.1, (crossed, one))

    def test_the_page_is_read_within_the_limits(self):
        result = extracted(stacked_boxes(3000))
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertEqual(result.text.count('[ ]'), 3000)

    def test_too_many_boxes_under_one_mark_leave_every_printed_box_unread(self):
        """The bound is the boxes a mark may lie over, counted per piece: a tick over a line pypdf joined from another
        column whose piece holds more than _ING_MAX_SCAN typed boxes leaves every printed box on the page unread (the
        snare's row too); one whose piece holds fewer leaves those boxes alone unread."""
        from tests.test_repairs_r4c_ingest_marks import annotate
        for count, snare in ((66, f'{UNREAD} Cold snare polypectomy'), (40, '[ ] Cold snare polypectomy')):
            with self.subTest(count=count):
                form = Form(NOTE_HEAD)
                form.line(text_line(72, ROW - 2, 'Details', size=5))
                form.line(text_line(150, ROW, 'Interventions: ' + ' '.join(['[ ]'] * count), size=5))
                form.line(text_line(72, 600, '[ ] Cold snare polypectomy'))
                x = 150 + _width('Interventions: ', 5)
                annotate(form, 'tick', (x + 0.2, ROW - 0.5, x + 4.5, ROW + 5))  # above the line start's baseline
                result = extracted(form.build())
                self.assertIn(UNREAD_NOTE, result.messages)
                self.assertEqual(result.text.count(UNREAD), count + (count == 66))
                self.assertIn(snare, result.text)

    def test_a_mark_left_of_a_line_is_not_over_the_boxes_inside_it(self):
        """Control: a pen tick in the margin, left of where a line starts, on its baseline, is over none of the boxes
        inside that line's piece of text (they lie right of where it draws)."""
        from tests.test_repairs_r4c_ingest_marks import annotate
        form = Form(NOTE_HEAD)
        form.line(text_line(72, 620, 'Biopsy [ ]')).line(text_line(72, 600, 'Cold snare polypectomy [ ]'))
        annotate(form, 'tick', (40, 597, 52, 609))
        result = extracted(form.build())
        self.assertNotIn(UNREAD_NOTE, result.messages)
        self.assertIn('Biopsy [ ]\nCold snare polypectomy [ ]', result.text)


# --- verification of round 4d (critical): glyphs are read where a TJ's numbers and strings of spaces draw them -------

TJ_SHAPES = {'a TJ number': '[-2400 ({})] TJ', 'a string of spaces': '[(    ) ({})] TJ',
             'spaces and a number': '[(  ) -1200 ({})] TJ'}


def tj_indented(shape, *, wrap, tick=True, row='snare'):
    """A plain-text checklist in Courier 10 whose rows are indented inside their TJ by ``shape`` (TJ_SHAPES: each puts
    the snare's '[' at x 96, where pdf.js draws it); an ink tick over the snare's (or the biopsy's) brackets; the page
    drawn through a form XObject (``wrap``) or by itself."""
    from tests.test_repairs_ingest_pdf import esc
    from tests.test_repairs_r4c_ingest_marks import annotate
    form = Form(NOTE_HEAD, wrap=wrap)
    form.objects[6] = COURIER
    form.line(text_line(72, 660, 'Interventions:', font='ZA', size=10))
    for y, item in ((650, 'Biopsy'), (640, 'Cold snare polypectomy')):
        form.line(f'BT /ZA 10 Tf 72 {y} Td ' + TJ_SHAPES[shape].format(esc('[ ] ' + item)) + ' ET')
    if tick:
        y = 640 if row == 'snare' else 650
        annotate(form, 'tick', (97, y - 2, 108, y + 7.5))
    return form.build()


def _shown_field(form, rect, value):
    """A text field whose appearance shows ``value``."""
    from tests.test_repairs_ingest_pdf import esc, stream
    ap = form.add(stream(f'/Tx BMC q BT /Helv 10 Tf 0 g 1 2 Td ({esc(value)}) Tj ET Q EMC',
                         f'/Type /XObject /Subtype /Form /BBox [0 0 {rect[2] - rect[0]} {rect[3] - rect[1]}] '
                         '/Resources << /Font << /Helv 4 0 R >> >>').decode('latin-1'))
    form.annots.append(form.add('<< /Type /Annot /Subtype /Widget /FT /Tx /T (Text1) '
                                f'/Rect [{" ".join(map(str, rect))}] /F 4 /P 3 0 R /DA (/Helv 10 Tf 0 g) '
                                f'/V ({esc(value)}) /AP << /N {ap} 0 R >> >>'))
    form.fields.append(form.annots[-1])


def tj_inset(kind, *, wrap=False, shape='a TJ number'):
    """'[  ] Biopsy' / '[  ] Cold snare polypectomy' in Helvetica 11, each drawn right of its operator by a TJ number
    ([-1000 (...)] TJ: pdf.js puts the snare's '[' at x 83) or by a string of three spaces, with a mark inside the
    snare's brackets: a text field showing X, an ink tick, a checked check box, a typed X, or none."""
    from tests.test_repairs_ingest_pdf import esc
    from tests.test_repairs_r4c_ingest_marks import annotate
    form = Form(NOTE_HEAD, wrap=wrap)
    op = '[-1000 ({})] TJ' if shape == 'a TJ number' else '[(   ) ({})] TJ'
    form.line(text_line(72, 640, 'Interventions:'))
    for y, item in ((BIOPSY_ROW, 'Biopsy'), (SNARE_ROW, 'Cold snare polypectomy')):
        form.line(f'BT /F1 11 Tf 72 {y} Td ' + op.format(esc('[  ] ' + item)) + ' ET')
    x = 72 + (11.0 if shape == 'a TJ number' else 3 * _width(' '))
    rect = (round(x + 2.9, 2), SNARE_ROW - 3, round(x + 9.3, 2), SNARE_ROW + 9)
    if kind == 'field X':
        _shown_field(form, rect, 'X')
    elif kind == 'tick':
        annotate(form, 'tick', rect)
    elif kind == 'check box on':
        form.checkbox('Check Box1', rect, True)
    elif kind == 'typed X':
        form.freetext(rect, 'X')
    return form.build()


def _next_column_tails():
    """'MAC' and the next column's sentence in one text object, the sentence moved 33 pt right by a TJ number (or 22 pt
    by a number after a string of spaces), as pdf.js draws it: a column gap the text layer does not show."""
    from tests.test_repairs_ingest_pdf import esc
    return {'a TJ number': f'(MAC) Tj [-3000 ({esc(SENTENCE)})] TJ',
            'a string of spaces, then a number': f'(MAC) Tj [(    ) -2000 ({esc(SENTENCE)})] TJ',
            'both in TJs': f'[(MAC)] TJ [-3000 ({esc(SENTENCE)})] TJ'}


class GlyphsPastTJNumbersTests(unittest.TestCase):
    """An operator's first glyph that draws is read where the TJ's numbers and the strings of spaces before it put it,
    never at the operator's own place: a mark over a printed box indented that way is over it, and the next column a
    TJ number moves past a column gap is never governed by the unchecked box before the last option."""

    def test_a_tick_over_a_box_indented_inside_its_tj_is_unread(self):
        for shape in TJ_SHAPES:
            for wrap in (True, False):
                with self.subTest(shape=shape, wrap=wrap):
                    result = extracted(tj_indented(shape, wrap=wrap))
                    self.assertEqual(result.status, 'partial', result.messages)
                    self.assertIn(UNREAD_NOTE, result.messages)
                    self.assertIn(f'{UNREAD} Cold snare polypectomy', result.text)
                    self.assertIn('[ ] Biopsy', result.text)
                    self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')

    def test_a_mark_inside_a_box_moved_right_holds_the_item(self):
        for shape in ('a TJ number', 'a string of spaces'):
            for kind in ('field X', 'tick', 'check box on', 'typed X'):
                for wrap in (False, True):
                    with self.subTest(shape=shape, kind=kind, wrap=wrap):
                        result = extracted(tj_inset(kind, wrap=wrap, shape=shape))
                        self.assertEqual(result.status, 'partial', result.messages)
                        self.assertRegex(result.text, r'\n *\[\?\] ?(☒ )?Cold snare polypectomy')
                        self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_controls_without_a_mark_over_the_box(self):
        """No mark, or a tick over the other row's box: the snare's printed box reads as before."""
        for shape in TJ_SHAPES:
            for wrap in (True, False):
                with self.subTest(shape=shape, wrap=wrap):
                    text = extracted(tj_indented(shape, wrap=wrap, tick=False)).text
                    self.assertIn('[ ] Cold snare polypectomy', text)
                    self.assertNotIn(UNREAD, text)
                    self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                    text = extracted(tj_indented(shape, wrap=wrap, row='biopsy')).text
                    self.assertIn(f'{UNREAD} Biopsy', text)
                    self.assertIn('[ ] Cold snare polypectomy', text)
                    self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
        for shape in ('a TJ number', 'a string of spaces'):
            with self.subTest(shape=shape, kind='none'):
                result = extracted(tj_inset('none', shape=shape))
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertIn('[  ] Cold snare polypectomy', result.text)

    def test_the_next_column_a_tj_number_moves_is_never_negated(self):
        import re
        for name, tail in _next_column_tails().items():
            with self.subTest(name):
                result = extracted(column_row(tail=tail))
                self.assertIsNone(re.search(r'☐ MAC[^\n]', result.text), result.text)
                self.assertIn(f'{UNREAD} MAC', result.text)
                self.assertIn('☒ Moderate', result.text)
                self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                text = extracted(column_row(True, tail=tail)).text  # a checked option keeps its glyph
                self.assertIn('☒ MAC', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_a_word_space_after_the_option_is_not_a_column_gap(self):
        """Control: the sentence a word space after 'MAC' (a TJ number of one space's width) is on the option's line:
        the unchecked box keeps its glyph there, as before."""
        from tests.test_repairs_ingest_pdf import esc
        for number in (-278, -500):
            with self.subTest(number=number):
                text = extracted(column_row(tail=f'(MAC) Tj [{number} ({esc(SENTENCE)})] TJ')).text
                self.assertIn('Sedation: ☒ Moderate ☐ MAC', text)

    def test_a_column_gap_is_not_shrunk_by_whitespace_the_next_string_closes_with(self):
        """A TJ number of 0.7 em before a sentence that ends with a space: the gap the glyphs show is 0.7 em (only
        whitespace a string opens with may be the word space before it)."""
        from tests.test_repairs_ingest_pdf import esc
        text = extracted(column_row(tail=f'(MAC) Tj [-700 ({esc(SENTENCE + " ")})] TJ')).text
        self.assertIn(f'{UNREAD} MAC', text)
        self.assertNotEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_an_option_written_word_by_word_with_opening_spaces_keeps_its_glyph(self):
        """Control: in Courier, words each drawn by a string that opens with two spaces: one of them is a word space,
        the other 0.6 em, no column gap; the unchecked box keeps '☐'."""
        from tests.test_repairs_ingest_pdf import esc
        form = Form(NOTE_HEAD)
        form.objects[6] = COURIER
        form.line(text_line(72, ROW, 'Interventions:'))
        box = 72 + _width('Interventions:') + 8
        form.checkbox('Check Box1', (box, ROW - 3, box + 12, ROW + 9), True)
        form.line(text_line(box + 16, ROW, 'Biopsy'))
        second = box + 16 + _width('Biopsy') + 10
        form.checkbox('Check Box2', (second, ROW - 3, second + 12, ROW + 9), False)
        strings = ' '.join(f'({esc(word)}) Tj' for word in ('Cold', '  snare', '  polypectomy'))
        form.line(f'BT /ZA 11 Tf {second + 16} {ROW} Td {strings} ET')
        text = extracted(form.build()).text
        self.assertIn('☐ Cold  snare  polypectomy', text)


# --- verification of round 4d (critical): padding inside one string, and a next column the page cannot measure --------

def _padded_tails():
    """(the /ZA font, the operators that draw 'MAC' and the next column at MAC's place): one string padded with
    spaces, no-break spaces or word spacing, a later string of the line padded inside, or the next column in a font
    without widths in MAC's text object (pypdf reports it at the text object's last move, where MAC's ink starts)."""
    from tests.test_repairs_ingest_pdf import esc
    one = lambda pad, prefix='': f'{prefix}({esc("MAC" + pad + SENTENCE)}) Tj'  # noqa: E731
    return {'Helvetica, 25 spaces': (None, one(' ' * 25)), 'Helvetica, 4 spaces': (None, one(' ' * 4)),
            'Courier, 12 spaces': (COURIER, one(' ' * 12, '/ZA 11 Tf ')),
            'Courier, 3 spaces': (COURIER, one(' ' * 3, '/ZA 11 Tf ')),
            'no-break spaces': (None, one('\xa0' * 4)), 'word spacing 3, 3 spaces': (None, one(' ' * 3, '3 Tw ')),
            'word spacing 3, 2 spaces': (None, one(' ' * 2, '3 Tw ')),
            'one space, word spacing 40': (None, one(' ', '40 Tw ') + ' 0 Tw'),
            'a trailing space at word spacing 40, then a string': (None, f'40 Tw (MAC ) Tj 0 Tw ({esc(SENTENCE)}) Tj'),
            # negative word spacing never widens the word space allowed: the gap is at least what it was
            'word spacing -0.8, 4 spaces': (None, one(' ' * 4, '-0.8 Tw ') + ' 0 Tw'),
            'a trailing space at word spacing -2, then a TJ number': (
                None, f'-2 Tw (MAC ) Tj 0 Tw [-650 ({esc(SENTENCE)})] TJ'),
            'a later string padded inside': (None, f'(MAC) Tj ({esc(" was given" + " " * 8 + SENTENCE)}) Tj'),
            'no widths, after a TJ number': (None, f'[(MAC) -3000] TJ /MG 11 Tf ({esc(SENTENCE)}) Tj'),
            'no widths, right after MAC': (None, f'(MAC ) Tj /MG 11 Tf ({esc(SENTENCE)}) Tj')}


class PaddingInsideAStringTests(unittest.TestCase):
    """The gap padding shows inside one string (less one whitespace glyph, a word space) is a gap between the glyphs
    drawn, and a next column set in a font the page does not measure is text the box cannot be sure it governs: an
    unchecked box before 'MAC' writes '[?]', never '☐' before the other column."""

    def test_the_next_column_after_padding_or_unmeasured_is_never_negated(self):
        import re
        for name, (za, tail) in _padded_tails().items():
            with self.subTest(name):
                result = extracted(column_row(tail=tail, za=za))
                self.assertIsNone(re.search(r'☐ MAC[^\n]', result.text), result.text)
                self.assertIn(f'{UNREAD} MAC', result.text)
                self.assertIn('☒ Moderate', result.text)
                self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                text = extracted(column_row(True, tail=tail, za=za)).text  # a checked option keeps its glyph
                self.assertIn('☒ MAC', text)
                self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_a_next_column_in_a_font_the_page_does_not_have_is_unread(self):
        """The next column in MAC's text object set in a font the page's resources do not hold: pypdf draws it in its
        stand-in font, U+FFFD for every byte, so the page's text layer is not read at all (cpt-studio-ingest@4,
        ACCURACY-RESIDUALS.md "pypdf 6.21.4"): the page has no usable text layer, and goes to OCR or is named. Until
        ingest@3 the layer was read with '[?] MAC' and the column as U+FFFD; '☐ MAC' was never written."""
        from studio.ingest import extract_document
        from tests.test_ingest import FakeOcr
        from tests.test_repairs_ingest_pdf import esc
        data = column_row(tail=f'[(MAC) -3000] TJ /XX 11 Tf ({esc(SENTENCE)}) Tj')
        result = extracted(data)
        self.assertEqual((result.status, result.text), ('failed', ''))
        self.assertEqual((result.messages[0], result.messages[-1]),
                         ('Page 1 has no usable text layer and OCR is not available on this server.',
                          'No text could be read from the PDF.'))
        with FakeOcr() as fake:
            ocred = extract_document(data, 'synthetic.pdf', 'application/pdf', ocr=fake.tools)
        self.assertEqual((ocred.status, ocred.ocr_pages), ('ok', (1,)))
        self.assertNotIn('☐ MAC', ocred.text)
        self.assertNotIn('\ufffd', ocred.text)

    def test_word_spaces_inside_the_string_keep_the_glyph(self):
        """Controls: padding no wider than 0.6 em past one word space at its own width (two extra Helvetica spaces,
        one extra Courier space, one space at word spacing 3), and a measured string after a font change with no gap,
        keep '☐ MAC'."""
        from tests.test_repairs_ingest_pdf import esc
        for name, za, tail in (('Helvetica, 3 spaces', None, f'({esc("MAC   sedation given")}) Tj'),
                               ('2 no-break spaces', None, f'({esc("MAC" + chr(0xa0) * 2 + "sedation given")}) Tj'),
                               ('a space and a no-break space', None, f'({esc("MAC " + chr(0xa0) + "sedation")}) Tj'),
                               ('Courier, 2 spaces', COURIER, f'/ZA 11 Tf ({esc("MAC  sedation given")}) Tj'),
                               ('word spacing 3, one space', None, f'3 Tw ({esc("MAC sedation given")}) Tj 0 Tw'),
                               ('measured, after a font change', None, f'(MAC ) Tj /F1 11 Tf ({esc("sedation")}) Tj')):
            with self.subTest(name):
                text = extracted(column_row(tail=tail, za=za)).text
                self.assertIn('Sedation: ☒ Moderate ☐ MAC', text)

    def test_an_item_and_its_detail_in_one_padded_string(self):
        """The item's own detail padded inside its string ('Biopsy        Site: sigmoid colon') cannot be told from
        another column: held (a declared over-hold); two spaces are a word space and keep '☐'; checked keeps '☒'."""
        from tests.test_repairs_ingest_pdf import esc
        for spaces, on, expected, outcome in ((8, False, f'{UNREAD} Biopsy', 'held'),
                                              (2, False, '☐ Biopsy', 'excluded'), (8, True, '☒ Biopsy', 'ready')):
            with self.subTest(spaces=spaces, on=on):
                form = Form(NOTE_HEAD)
                form.line(text_line(72, 640, 'Interventions:'))
                form.checkbox('Check Box1', (72, 617, 84, 629), on)
                form.line(f'BT /F1 11 Tf 88 620 Td ({esc("Biopsy" + " " * spaces + "Site: sigmoid colon")}) Tj ET')
                text = extracted(form.build()).text
                self.assertIn(expected, text)
                self.assertEqual(codes(text, ('45380', 'Biopsy'))[0], outcome)


# --- verification of round 4d, extraction:2 neighbour: a printed box drawn after a font change with no move --------

def stale_row(*, printed='wingdings', on=False, mark='tick', wrap=False):
    """'1. ', a printed box and ' Cold snare polypectomy' in one text object, the box and the label set after font
    changes with no move: pypdf reports the box's piece where '1. ' begins (72), though it is drawn after it. A mark
    on the box as drawn (a tick, a field showing X, a checked check box), on the label, or none; the page drawn
    through a form XObject (``wrap``) or by itself."""
    from tests.test_repairs_r3_forms_pdf import PRINTED
    from tests.test_repairs_r4c_ingest_marks import annotate
    font, off, on_code = PRINTED[printed]
    form = Form(NOTE_HEAD, wrap=wrap)
    form.line(text_line(72, 640, 'Interventions:'))
    form.line(f'BT /F1 11 Tf 72 620 Td (2. ) Tj /{font} 11 Tf <{off}> Tj /F1 11 Tf ( Biopsy) Tj ET')
    form.line(f'BT /F1 11 Tf 72 600 Td (1. ) Tj /{font} 11 Tf <{on_code if on else off}> Tj /F1 11 Tf '
              '( Cold snare polypectomy) Tj ET')
    x = 72 + _width('1. ')
    width = _width('o', font='ZapfDingbats') if printed == 'zapf' else 11.0
    on_box = (round(x + 1.5, 2), 597, round(x + width - 1.5, 2), 609)
    if mark == 'tick':
        annotate(form, 'tick', on_box)
    elif mark == 'field X':
        _shown_field(form, on_box, 'X')
    elif mark == 'check box on':
        form.checkbox('Check Box1', on_box, True)
    elif mark == 'label':
        annotate(form, 'tick', (round(x + width + 20, 2), 597, round(x + width + 40, 2), 609))
    return form.build()


class BoxAfterAFontChangeTests(unittest.TestCase):
    """A printed box that starts a piece no operator placed (a font change with no move after '1. ') is not where
    pypdf reports it: it lies somewhere right of where its text object was last moved to, so a mark over it as drawn
    leaves it unread (9a9f403 held this on a page drawn through a form XObject; HEAD excluded it)."""

    def test_a_mark_over_the_box_as_drawn_holds_the_item(self):
        for printed in ('wingdings', 'zapf', 'text font'):
            for mark in ('tick', 'field X', 'check box on'):
                for wrap in (False, True):
                    with self.subTest(printed=printed, mark=mark, wrap=wrap):
                        result = extracted(stale_row(printed=printed, mark=mark, wrap=wrap))
                        self.assertEqual(result.status, 'partial', result.messages)
                        self.assertIn(f'1. {UNREAD} Cold snare polypectomy', result.text)
                        if not (wrap and mark == 'check box on'):  # there every printed box is lost to check boxes
                            self.assertIn('☐ Biopsy', result.text)
                        self.assertNotEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')

    def test_controls_without_a_mark(self):
        for printed in ('wingdings', 'text font'):
            for wrap in (False, True):
                with self.subTest(printed=printed, wrap=wrap):
                    text = extracted(stale_row(printed=printed, mark=None, wrap=wrap)).text
                    self.assertIn('1. ☐ Cold snare polypectomy', text)
                    self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'excluded')
                    text = extracted(stale_row(printed=printed, on=True, mark=None, wrap=wrap)).text
                    self.assertIn('1. ☒ Cold snare polypectomy', text)
                    self.assertEqual(codes(text, ('45385', 'Cold snare polypectomy'))[0], 'ready')

    def test_a_box_placed_by_its_own_move_keeps_its_place(self):
        """Controls: a box placed by a Td after '1. ' (its piece is reported where it is drawn), and rows drawn with
        the ' operator (a move to the next line, then the box): a tick on the label, right of the box, is over no
        box."""
        from tests.test_repairs_r4c_ingest_marks import annotate
        form = Form(NOTE_HEAD)
        form.line(text_line(72, 640, 'Interventions:'))
        for y, label in ((620, 'Biopsy'), (600, 'Cold snare polypectomy')):
            form.line(f'BT /F1 11 Tf 72 {y} Td (1. ) Tj 14 0 Td /WD 11 Tf <A8> Tj /F1 11 Tf 16 0 Td ({label}) Tj ET')
        annotate(form, 'tick', (140, 597, 160, 609))
        text = extracted(form.build()).text
        self.assertIn('1. ☐ Cold snare polypectomy', text)
        form = Form(NOTE_HEAD)
        form.line(text_line(72, 640, 'Interventions:'))
        form.line("BT 20 TL /WD 11 Tf 72 640 Td <A8> ' /F1 11 Tf 16 0 Td (Biopsy) Tj /WD 11 Tf <A8> ' "
                  "/F1 11 Tf 16 0 Td (Cold snare polypectomy) Tj ET")  # the second box at (88, 600), by its ' alone
        annotate(form, 'tick', (120, 597, 140, 609))
        text = extracted(form.build()).text
        self.assertIn('☐ Cold snare polypectomy', text)
        self.assertNotIn(UNREAD, text)

    def test_a_mark_on_the_label_holds_a_box_whose_place_is_not_read(self):
        """The declared cost of reading it: a tick on the label, right of a box no operator placed, may lie over the
        box, so the box is unread (held), never read as decided."""
        result = extracted(stale_row(mark='label'))
        self.assertIn(f'1. {UNREAD} Cold snare polypectomy', result.text)
        self.assertEqual(codes(result.text, ('45385', 'Cold snare polypectomy'))[0], 'held')


if __name__ == '__main__':
    unittest.main()
