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
from tests.test_repairs_r3_forms_pdf import codes
from tests.test_repairs_r4_ingest_docx import FORCEPS, IMPRESSION, NOTE_LINES, SNARE, unread_note
from tests.test_repairs_r4c_ingest_docx import CHECKED, SHADOWED, unread_in_lists
from tests.test_repairs_status_r2_routing import read

UNREAD = '[?]'


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


if __name__ == '__main__':
    unittest.main()
