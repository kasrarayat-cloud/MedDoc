"""Regressions for refutation round 5, INGEST lens, Word side (repair round 4c).

- extraction:2 (regression): one checked-box bullet anywhere in the document turned every box-shaped bullet of an
  ordinary list into '☐', so the performed services listed there were excluded. Whether a box bullet is a checklist's
  is now decided per list (a run of consecutive box-bulleted paragraphs): '☐' only where the list's own bullets show a
  checked box, else the unread mark '[?]' (held);
- extraction:5 (cost): the white-text check walked every ancestor of every white run (88 s for a 70 KB document); each
  element's verdict is now read once.

Each document is synthetic, built here from raw WordprocessingML, extracted with the sandboxed extract_document (or in
process where only extraction is timed), routed for real and assessed by the real engine.
"""
import time
import unittest

from studio.gi import detect
from tests.support import docgen
from tests.test_repairs_r3_forms_docx import docx_result, level, note_paragraphs, numbering, numpr, paragraph
from tests.test_repairs_r3_forms_pdf import codes
from tests.test_repairs_r4_ingest_docx import FORCEPS, IMPRESSION, NOTE_LINES, SNARE, unread_note
from tests.test_repairs_status_r2_routing import read

CHECKED, SHADOWED, WHITE_SQUARE, LIBRARY = '', '', '', ''


def unread_in_lists(count):
    """The note when other lists of the document do show checked box bullets."""
    lists = 'a list that shows' if count == 1 else 'lists that show'
    return (f'The document has {count} list item{"" if count == 1 else "s"} whose bullet is a box, in {lists} no checked '
            f'box bullet; {"it was" if count == 1 else "they were"} written as unread ([?]), so check the original.')


def with_checks(box=SHADOWED, font='Wingdings', *, checks_first=True, checked=CHECKED, checked_font='Wingdings',
                one_list=False):
    """The round-5 note: 'Pre-procedure checks:' with two items bulleted ☑ (numId 2), 'Procedures performed:' with the
    snare and forceps items bulleted ``box`` (numId 1), then the impression. ``one_list``: one heading, the four items
    on consecutive paragraphs."""
    checks = ('' if one_list else paragraph('Pre-procedure checks:')) + ''.join(
        paragraph(item, numpr(2)) for item in ('Consent signed', 'Time-out completed'))
    procedures = ('' if one_list else paragraph('Procedures performed:')) + ''.join(
        paragraph(item, numpr(1)) for item in (SNARE, FORCEPS))
    body = note_paragraphs(NOTE_LINES[:4] + (['Procedures performed:'] if one_list else []))
    body += checks + procedures if checks_first else procedures + checks
    body += paragraph(IMPRESSION)
    return docgen.rewrite_zip(docgen.make_docx_from_body(body), {'word/numbering.xml': numbering(
        {0: level(0, 'bullet', box, font), 1: level(0, 'bullet', checked, checked_font)}, {1: (0, ''), 2: (1, '')})})


class Extraction2BoxBulletsPerListTests(unittest.TestCase):
    def test_a_checked_list_elsewhere_leaves_an_ordinary_list_held(self):
        for label, kwargs in (('checks first', {}), ('checks after', dict(checks_first=False)),
                              ('white square', dict(box=WHITE_SQUARE)),
                              ('a literal checked box', dict(checked='☑', checked_font='Segoe UI Symbol'))):
            with self.subTest(label):
                result = docx_result(with_checks(**kwargs))
                self.assertEqual((result.status, result.messages), ('ok', (unread_in_lists(2),)))
                self.assertIn(f'Procedures performed:\n[?] {SNARE}\n[?] {FORCEPS}\n', result.text)
                self.assertIn('☒ Consent signed\n☒ Time-out completed', result.text)
                for phrase in (SNARE, FORCEPS):
                    status, cues = read(result.text, phrase)
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertIn(detect.BOX_UNREAD, cues)
                self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('held', 'held'))

    def test_a_checklist_with_both_states_in_one_run_is_still_read(self):
        """The ☑ and ❑ items of one list, under two numbering definitions on consecutive paragraphs (round 3 ingest:5),
        and the same with the checked items after the unchecked ones."""
        for checks_first in (True, False):
            with self.subTest(checks_first=checks_first):
                result = docx_result(with_checks(checks_first=checks_first, one_list=True))
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn(f'☐ {SNARE}\n☐ {FORCEPS}', result.text)
                self.assertEqual(codes(result.text, ('45385', SNARE))[0], 'excluded')

    def test_without_a_checked_list_the_note_is_as_before(self):
        body = (note_paragraphs(NOTE_LINES) + ''.join(paragraph(item, numpr(1)) for item in (SNARE, FORCEPS))
                + paragraph(IMPRESSION))
        data = docgen.rewrite_zip(docgen.make_docx_from_body(body), {'word/numbering.xml': numbering(
            {0: level(0, 'bullet', SHADOWED, 'Wingdings')}, {1: (0, '')})})
        result = docx_result(data)
        self.assertEqual((result.status, result.messages), ('ok', (unread_note(2),)))

    def test_an_ordinary_bullet_beside_a_checked_list_is_unchanged(self):
        """Positive control: the library square (an ordinary bullet in Wingdings) is no box, whatever else the document
        holds."""
        result = docx_result(with_checks(box=LIBRARY))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn(f'Procedures performed:\n{SNARE}\n{FORCEPS}\n', result.text)
        self.assertEqual(codes(result.text, ('45385', SNARE), ('45380', FORCEPS)), ('ready', 'ready'))


# --- extraction:5 -- the white-text check on deeply nested text ------------------------------------------------------

WHITE = '<w:rPr><w:color w:val="FFFFFF"/></w:rPr>'
SHADING = '<w:shd w:val="clear" w:color="auto" w:fill="1F3864"/>'


def nested(depth, runs, *, run_properties=WHITE, outer_cell='', inner_paragraph='', box=False):
    """``runs`` runs of 'a ' (50 to a paragraph) in a table nested ``depth`` deep, as Word writes nested tables."""
    run = f'<w:r>{run_properties}<w:t xml:space="preserve">a </w:t></w:r>'
    ppr = f'<w:pPr>{inner_paragraph}</w:pPr>' if inner_paragraph else ''
    inner = ''.join(f'<w:p>{ppr}' + run * 50 + '</w:p>' for _ in range(runs // 50))
    if box:
        inner = ('<w:p><w:r><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>'
                 + inner + '</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>')
    for level_ in range(depth):
        tcpr = f'<w:tcPr>{outer_cell}</w:tcPr>' if outer_cell and level_ == depth - 1 else '<w:tcPr/>'
        inner = (f'<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid><w:tr><w:tc>{tcpr}{inner}<w:p/>'
                 '</w:tc></w:tr></w:tbl>')
    body = note_paragraphs(NOTE_LINES[:2]) + inner
    return docgen.make_docx_from_body(body)


def in_process(data):
    from studio.ingest.docx import extract_docx
    from studio.ingest.extract import Limits
    started = time.monotonic()
    result = extract_docx(data, Limits())
    return time.monotonic() - started, result


class Extraction5WhiteTextCostTests(unittest.TestCase):
    def test_white_runs_deep_in_tables_cost_what_black_runs_cost(self):
        black_time, black = in_process(nested(80, 10_000, run_properties=''))
        white_time, white = in_process(nested(80, 10_000))
        self.assertEqual(black.text, white.text)
        self.assertEqual(white.status, 'partial')
        self.assertIn('white text with nothing shaded behind it, 10000 runs', ' '.join(white.messages))
        self.assertLess(white_time, 3 * black_time + 1.0, (white_time, black_time))

    def test_what_is_painted_behind_is_read_through_every_level(self):
        """The verdict read once per element is the walk's: shading on the outermost cell or on the innermost paragraph,
        or a text box, anywhere above the runs, keeps white text ok; none leaves it named."""
        for label, kwargs, status in (('the outermost cell shaded', dict(outer_cell=SHADING), 'ok'),
                                      ('the paragraph shaded', dict(inner_paragraph=SHADING), 'ok'),
                                      ('in a text box', dict(box=True), 'ok'), ('nothing behind', {}, 'partial')):
            with self.subTest(label):
                _, result = in_process(nested(6, 100, **kwargs))
                self.assertEqual(result.status, status, result.messages)


if __name__ == '__main__':
    unittest.main()
