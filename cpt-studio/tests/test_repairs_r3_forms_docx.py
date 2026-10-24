"""Regressions for refutation round 3, FORMS lens, Word side: check boxes recognised by structure.

- ingest:4 / contract:6: a w14:checkbox content control is written ☒ (w14:checked on) or ☐, whatever symbols its
  checked and unchecked states are set to;
- ingest:5: a list paragraph whose numbering bullet is a box glyph is written with ☐ or ☒ at its start.

Each document is synthetic, built here from python-docx with raw WordprocessingML for the controls and the
numbering part, extracted with the sandboxed extract_document, routed for real and assessed by the real engine.
The builders are shared with tests/test_repairs_r3_forms_routing.py.
"""
import unittest

from studio.ingest import extract_document
from tests.support import docgen
from tests.test_repairs_status_r2_routing import BOXED, read, run_engine
from tests.test_repairs_r3_forms_routing import outcome

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'


def docx_result(data: bytes):
    return extract_document(data, 'synthetic.docx', DOCX, ocr=None)


def docx_text(data: bytes) -> str:
    result = docx_result(data)
    if result.status != 'ok':
        raise AssertionError((result.status, result.messages))
    return result.text


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def paragraph(text: str, ppr: str = '') -> str:
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{_escape(text)}</w:t></w:r></w:p>'


def control(checked: bool, unchecked_state=('2610', 'MS Gothic'), checked_state=('2612', 'MS Gothic'),
            run_text=None, run_font=None, checked_xml=None, hidden=False, placeholder=False, sym=False) -> str:
    """A Word check-box content control as Word saves it: the states it is set to in w14:checkbox and the current
    state's glyph as its content (``run_text`` overrides the glyph; ``sym`` writes it as a w:sym)."""
    state = checked_state if checked else unchecked_state
    glyph = chr(int(state[0], 16)) if run_text is None else run_text
    font = run_font or state[1]
    checked_element = (f'<w14:checked w14:val="{1 if checked else 0}"/>' if checked_xml is None else checked_xml)
    flags = ('<w:showingPlcHdr/>' if placeholder else '')
    vanish = '<w:vanish/>' if hidden else ''
    if sym:
        content = (f'<w:r><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>{vanish}</w:rPr>'
                   f'<w:sym w:font="{font}" w:char="F0{state[0][-2:]}"/></w:r>')
    else:
        content = (f'<w:r><w:rPr><w:rFonts w:ascii="{font}" w:eastAsia="{font}" w:hAnsi="{font}"/>{vanish}</w:rPr>'
                   f'<w:t>{_escape(glyph)}</w:t></w:r>')
    return (f'<w:sdt><w:sdtPr><w:id w:val="-1"/>{flags}<w14:checkbox>{checked_element}'
            f'<w14:checkedState w14:val="{checked_state[0]}" w14:font="{checked_state[1]}"/>'
            f'<w14:uncheckedState w14:val="{unchecked_state[0]}" w14:font="{unchecked_state[1]}"/></w14:checkbox>'
            f'</w:sdtPr><w:sdtContent>{content}</w:sdtContent></w:sdt>')


def note_paragraphs(lines=None) -> str:
    return ''.join(paragraph(line) for line in (lines if lines is not None else BOXED.strip('\n').split('\n')))


def box_table_docx(rows, lines=None, after=(), **box) -> bytes:
    """``lines`` (default BOXED) as paragraphs, then a table: each cell is text or ('box', checked)."""
    def cell(value):
        if isinstance(value, tuple):
            return f'<w:tc><w:p>{control(value[1], **box)}</w:p></w:tc>'
        return f'<w:tc>{paragraph(value)}</w:tc>'
    table = '<w:tbl>' + ''.join('<w:tr>' + ''.join(cell(v) for v in row) + '</w:tr>' for row in rows) + '</w:tbl>'
    return docgen.make_docx_from_body(note_paragraphs(lines) + table + ''.join(paragraph(p) for p in after))


def paragraphs_docx(extra, lines=None) -> bytes:
    return docgen.make_docx_from_body(note_paragraphs(lines) + ''.join(paragraph(p) for p in extra))


def boxed_paragraphs_docx(items, **box) -> bytes:
    """One paragraph per (checked, label): the control, then a space and the label."""
    body = ''.join(f'<w:p>{control(checked, **box)}<w:r><w:t xml:space="preserve"> {_escape(label)}</w:t></w:r></w:p>'
                   for checked, label in items)
    return docgen.make_docx_from_body(note_paragraphs() + body)


if __name__ == '__main__':
    unittest.main()
