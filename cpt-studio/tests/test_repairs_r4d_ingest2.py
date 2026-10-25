"""Regressions for refutation round 6, INGEST lens (repair round 4d, INGEST2).

Every rule here is hold-only: where a box's placement or state is in doubt, extraction writes the unread mark '[?]'
(routing holds the item), never a guessed state (contract-r4d section 1).

- extraction:1 (regression): in Word, a checked-box checklist in the adjacent table cell, in a text box anchored in or
  after an ordinary box-bulleted list, or a hidden checked paragraph, turned that list's bullets into '☐'. A table
  cell's boundary and a text box's boundary now end a list, and a paragraph Word does not show (its mark hidden, no
  visible text) writes no bullet and belongs to no list.

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


# --- extraction:1 -- Word box bullets: a list ends at a cell or text-box boundary --------------------------------------

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
               right_first=False, right_x=None, row_x=48.69, moderate_on=True):
    """'Sedation:  [box] Moderate  [box] MAC' (each check box 4 pt before its word; Moderate checked) in a left
    column, and the next column's ``right`` lines ([(dy, text)], default the sentence at ``dy``) starting ``gap`` pt
    after 'MAC' ends. ``pad``/``lead``: spaces drawn after 'MAC' / before the next column's text in the same string;
    ``font``: the next column's font (MG: a TrueType font without /Widths); ``one_bt``: 'MAC' and the next column's
    first line drawn in one text object; ``right_first``: the next column drawn before the left one; ``right_x``: where
    the next column starts instead; ``row_x``: where the row of options starts."""
    from tests.test_repairs_ingest_pdf import esc
    form = Form(NOTE_HEAD)
    form.objects[23] = NO_WIDTHS
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


if __name__ == '__main__':
    unittest.main()
