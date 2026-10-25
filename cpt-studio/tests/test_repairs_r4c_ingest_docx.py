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


if __name__ == '__main__':
    unittest.main()
