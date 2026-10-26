"""Regressions for refutation round 4, INGEST lens: what covers a PDF page's text is named, also past the work budgets.

- extraction:4: an opaque FreeText or form-field appearance laid over text (a white-out correction, an empty or filled
  text field with a white background) is named like an opaque Square: partial, with the cover-up message;
- evidence:6: past MAX_PAINT_CHECKS (a page's own covers, and annotation covers) and MAX_SHAPE_CHECKS (clipping paths)
  the page is named, never read as if nothing covered or clipped its text.

Every document is synthetic and built here from raw PDF syntax.
"""
import unittest
from unittest import mock

from studio.ingest import pdfcontent
from tests.test_repairs_ingest_pdf import HELVETICA, esc, in_process, serialise, stream
from tests.test_repairs_ingest_r2 import SHOWN_LINE, UNSHOWN, pdf_extract, placed_pdf
from tests.test_repairs_r3_fonts_page import MARKED, OBSCURED, SENTENCE
from tests.test_repairs_r3_forms_pdf import codes

BIOPSY = 'A cold forceps biopsy was taken from the polyp.'
RECT = (70, 391, 308.94, 406)
ANNOTATION_NOTE = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
                   'annotation text.')
FIELDS_NOTE = ('Page 1 has PDF form fields; their values were read and added after the page text, labelled as form '
               'fields.')
REPORT = [(72, 720, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (72, 700, 'Date of service: 2026-10-21'),
          (72, 680, 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.'),
          (72, 660, 'Findings: A 6 mm sigmoid polyp was seen.'), (72, 395, BIOPSY)]


def covered_report(kind, *, rect=RECT, contents='Biopsy deferred.'):
    """The report with one annotation of ``kind`` whose appearance paints a white box over ``rect`` (and draws
    ``contents`` in it where the kind shows text)."""
    width, height = round(rect[2] - rect[0], 2), round(rect[3] - rect[1], 2)
    r = ' '.join(map(str, rect))
    shown = f' BT /Helv 10 Tf 0 g 2 4 Td ({esc(contents)}) Tj ET' if contents else ''
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in REPORT)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', 4: HELVETICA,
               5: stream(content)}
    form = f'/Type /XObject /Subtype /Form /BBox [0 0 {width} {height}] /Resources << /Font << /Helv 4 0 R >> >>'
    if kind == 'square':
        objects[7] = stream(f'1 g 0 0 {width} {height} re f', form)
        objects[6] = f'<< /Type /Annot /Subtype /Square /Rect [{r}] /F 4 /IC [1 1 1] /AP << /N 7 0 R >> >>'.encode()
    elif kind == 'freetext':
        objects[7] = stream(f'q 1 g 0 0 {width} {height} re f Q{shown}', form)
        text = f'({esc(contents)})' if contents else '()'
        objects[6] = (f'<< /Type /Annot /Subtype /FreeText /Rect [{r}] /F 4 /Contents {text} /DA (/Helv 10 Tf 0 g) '
                      '/AP << /N 7 0 R >> >>').encode()
    elif kind == 'field':
        objects[7] = stream(f'q 1 g 0 0 {width} {height} re f Q /Tx BMC{shown} EMC', form)
        value = f'/V ({esc(contents)})' if contents else ''
        objects[6] = (f'<< /Type /Annot /Subtype /Widget /FT /Tx /T (Comments) {value} /Rect [{r}] /F 4 /P 3 0 R '
                      '/MK << /BG [1] >> /DA (/Helv 10 Tf 0 g) /AP << /N 7 0 R >> >>').encode()
        objects[1] = b'<< /Type /Catalog /Pages 2 0 R /AcroForm 8 0 R >>'
        objects[8] = b'<< /Fields [6 0 R] /NeedAppearances false /DR << /Font << /Helv 4 0 R >> >> >>'
    objects[3] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R /Annots [6 0 R] >>')
    return serialise(objects)


class Extraction4OpaqueAnnotationCoversTests(unittest.TestCase):
    def test_a_square_cover_is_named(self):
        """The control the finding compares with (round 3 ingest:8)."""
        result = pdf_extract(covered_report('square'), ocr=None)
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(MARKED, result.messages)

    def test_a_freetext_white_out_is_named(self):
        for contents, notes in (('Biopsy deferred.', (MARKED, ANNOTATION_NOTE)), ('', (MARKED,))):
            with self.subTest(contents=contents):
                result = pdf_extract(covered_report('freetext', contents=contents), ocr=None)
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertEqual(result.messages, notes)
                self.assertIn(BIOPSY, result.text)  # read as written, and named

    def test_a_text_field_over_the_text_is_named(self):
        for contents, notes in (('', (MARKED,)), ('Biopsy deferred.', (MARKED, FIELDS_NOTE))):
            with self.subTest(contents=contents):
                result = pdf_extract(covered_report('field', contents=contents), ocr=None)
                self.assertEqual(result.status, 'partial', result.messages)
                self.assertEqual(result.messages, notes)
                self.assertIn(BIOPSY, result.text)

    def test_the_covered_biopsy_is_still_read_and_coded(self):
        """The remedy is the named, partial page; the code itself is assessed as before."""
        text = pdf_extract(covered_report('freetext'), ocr=None).text
        self.assertEqual(codes(text, ('45380', 'A cold forceps biopsy was taken'))[0], 'ready')

    def test_white_boxes_away_from_the_text_cover_nothing(self):
        away = (70, 300, 308.94, 315)
        for kind, notes in (('freetext', (ANNOTATION_NOTE,)), ('field', (FIELDS_NOTE,))):
            with self.subTest(kind=kind):
                result = pdf_extract(covered_report(kind, rect=away), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', notes))


# --- evidence:6 -- past the work budgets the page is named --------------------------------------------------------

STACK = ' '.join('BT /F1 3 Tf 400 200 Td (o) Tj ET' for _ in range(20))  # many runs over one spot
U_CLIP = 'q 20 400 m 600 400 l 600 600 l 580 600 l 580 420 l 40 420 l 40 600 l 20 600 l h W n'  # SENTENCE in its notch


class Evidence6WorkBudgetTests(unittest.TestCase):
    """Each arm of 870c425d6's 'past the work budgets the page is named, never silently read', in process with the
    budget patched low; each control within the budget reads as before."""

    def test_past_the_paint_budget_a_later_cover_is_named(self):
        fills = ' '.join(f'0 g 398 {199 - n * 0.2:.1f} 6 0.1 re f' for n in range(5))
        data = placed_pdf(f'{STACK} {fills} {SENTENCE} 1 1 1 rg 60 490 500 30 re f')
        with mock.patch.object(pdfcontent, 'MAX_PAINT_CHECKS', 50):
            result = in_process(data)
        self.assertEqual((result.status, result.messages), ('partial', (OBSCURED,)))
        self.assertIn(UNSHOWN, result.text)

    def test_past_the_shape_budget_clipped_text_is_named(self):
        runs = ' '.join(f'BT /F1 8 Tf {60 + 25 * n} 405 Td (x) Tj ET' for n in range(20))
        data = placed_pdf(f'{U_CLIP} {runs} {SENTENCE} Q')
        with mock.patch.object(pdfcontent, 'MAX_SHAPE_CHECKS', 100):
            result = in_process(data)
        self.assertEqual((result.status, result.messages), ('partial', (OBSCURED,)))
        self.assertIn(UNSHOWN, result.text)

    def test_past_the_paint_budget_an_annotation_cover_is_named(self):
        # The first square lies beside the stack (near it in the page's index, covering none of it), the second over
        # the sentence: examining the stack spends the budget before the second is looked at.
        squares = {6: b'<< /Type /Annot /Subtype /Square /Rect [404 196 420 212] /F 4 /IC [1 1 1] >>',
                   7: b'<< /Type /Annot /Subtype /Square /Rect [60 490 560 520] /F 4 /IC [1 1 1] >>'}
        data = placed_pdf(f'{STACK} {SENTENCE}', page_extra='/Annots [6 0 R 7 0 R]', extra=squares)
        with mock.patch.object(pdfcontent, 'MAX_PAINT_CHECKS', 10):
            result = in_process(data)
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertIn(OBSCURED, result.messages)
        self.assertIn(UNSHOWN, result.text)

    def test_within_the_budgets_the_same_pages_read_as_before(self):
        """Controls: unpatched, the covers are found (named as covered) and the U clip excludes the sentence."""
        fills = ' '.join(f'0 g 398 {199 - n * 0.2:.1f} 6 0.1 re f' for n in range(5))
        result = in_process(placed_pdf(f'{STACK} {fills} {SENTENCE} 1 1 1 rg 60 490 500 30 re f'))
        self.assertEqual((result.status, result.messages), ('partial', (OBSCURED,)))
        runs = ' '.join(f'BT /F1 8 Tf {60 + 25 * n} 405 Td (x) Tj ET' for n in range(20))
        result = in_process(placed_pdf(f'{U_CLIP} {runs} {SENTENCE} Q'))
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertNotIn(UNSHOWN, result.text)
        self.assertIn(SHOWN_LINE, result.text)


if __name__ == '__main__':
    unittest.main()
