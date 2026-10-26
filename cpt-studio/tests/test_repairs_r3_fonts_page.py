"""Regression tests for refutation round 3 ingest:9 and ingest:8: content a viewer does not show, and marks that
change what the page shows.

The extraction rule: content a viewer would show is read or reported, and content it would not show is excluded
with a message. Where whether something shows cannot be decided precisely (white text on the page, text painted
over by a later opaque fill, a clipping path too complex to follow, a markup annotation) the text is kept and the
result is partial with a specific message: never read as current silently, never dropped silently.

Every document is synthetic and built here from raw PDF syntax.
"""
from __future__ import annotations

import unittest

from studio.gi.detect import route
from tests.test_repairs_ingest_pdf import HELVETICA, serialise, serialise_again, stream
from tests.test_repairs_ingest_r2 import OFF_PAGE, SHOWN_LINE, UNSHOWN, esc, pdf_extract, placed_pdf

CLIPPED = 'Page 1 has text outside the area its clipping path or form box shows; that text was not extracted.'
STRUCK_TEXT = ('Page 1 has text struck through by a line drawn across it; it was read as written, so check it against '
               'the original.')
OBSCURED = ('Page 1 has text that a viewer may not show (white on the page, painted over, or clipped in a way that '
            'could not be checked); it was read, so check it against the original.')
SENTENCE = f'BT /F1 12 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET'
FORM = '/Type /XObject /Subtype /Form /Resources << /Font << /F1 4 0 R >> >>'


def form_pdf(content: str, form_content: str, bbox: str = '[0 0 612 792]', *, extra: dict | None = None,
             form_extra: str = '') -> bytes:
    """``content`` on the page, which may draw /Fx: a form with ``form_content`` and ``bbox``."""
    objects = {6: stream(form_content, f'{FORM} /BBox {bbox} {form_extra}')}
    objects.update(extra or {})
    return placed_pdf(content, resources='/XObject << /Fx 6 0 R >>', extra=objects)


def colonoscopy(text: str) -> str:
    return route(text, None).finding('gi.colonoscopy').status


class HiddenTextInFormsTests(unittest.TestCase):
    """ingest:9 — text a form draws is judged where it lands on the page, inside the form's box."""

    def test_text_a_form_draws_off_the_page_or_outside_its_box_is_excluded(self):
        cases = {'A: a page-sized form, text right of the page': (
                     'q /Fx Do Q', f'BT /F1 12 Tf 700 500 Td ({esc(UNSHOWN)}) Tj ET', '[0 0 612 792]', OFF_PAGE),
                 'A2: a page-sized form, text below the page': (
                     'q /Fx Do Q', f'BT /F1 12 Tf 72 -40 Td ({esc(UNSHOWN)}) Tj ET', '[0 0 612 792]', OFF_PAGE),
                 'B: text below its form box (the old crop box)': (
                     'q /Fx Do Q', f'BT /F1 12 Tf 72 50 Td ({esc(UNSHOWN)}) Tj ET', '[0 100 612 792]', CLIPPED)}
        for label, (content, form_content, bbox, message) in cases.items():
            with self.subTest(label):
                result = pdf_extract(form_pdf(content, form_content, bbox), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (message,)))
                self.assertEqual(result.text.strip(), SHOWN_LINE)
                self.assertEqual(colonoscopy(result.text), 'cancelled')

    def test_a_wrapped_cropped_page_keeps_its_cropped_text_out(self):
        # B2: a 612 x 692 page wraps a page cropped to [0 100 612 792]; the cut-off sentence lands at y = -50.
        content = (f'BT /F1 12 Tf 72 600 Td ({esc(SHOWN_LINE)}) Tj ET\n'
                   'q 1 0 0 1 0 -100 cm /Fx Do Q')
        objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 692] /Resources << /Font << /F1 4 0 R >> '
                       b'/XObject << /Fx 6 0 R >> >> /Contents 5 0 R >>'),
                   4: HELVETICA, 5: stream(content),
                   6: stream(f'BT /F1 12 Tf 72 50 Td ({esc(UNSHOWN)}) Tj ET', f'{FORM} /BBox [0 100 612 792]')}
        result = pdf_extract(serialise(objects), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (OFF_PAGE,)))
        self.assertEqual(result.text.strip(), SHOWN_LINE)

    def test_a_form_a_form_draws_off_the_page_is_excluded(self):
        # F: a page-sized form draws an inner form whose box lies wholly off the page.
        inner = stream(f'BT /F1 12 Tf 0 10 Td ({esc(UNSHOWN)}) Tj ET', f'{FORM} /BBox [0 0 500 30]')
        outer = stream('q 1 0 0 1 700 400 cm /Fy Do Q',
                       '/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /XObject << /Fy 7 0 R >> >>')
        data = placed_pdf('q /Fx Do Q', resources='/XObject << /Fx 6 0 R >>', extra={6: outer, 7: inner})
        result = pdf_extract(data, ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (OFF_PAGE,)))
        self.assertEqual(result.text.strip(), SHOWN_LINE)

    def test_a_nested_form_off_the_page_is_dropped_whole(self):
        # Its text has no font size, so it cannot be judged run by run: the form's box decides.
        inner = stream(f'BT /F1 0 Tf 0 10 Td ({esc(UNSHOWN)}) Tj ET', f'{FORM} /BBox [0 0 500 30]')
        outer = stream('q 1 0 0 1 700 400 cm /Fy Do Q',
                       '/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /XObject << /Fy 7 0 R >> >>')
        data = placed_pdf('q /Fx Do Q', resources='/XObject << /Fx 6 0 R >>', extra={6: outer, 7: inner})
        result = pdf_extract(data, ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (OFF_PAGE,)))
        self.assertEqual(result.text.strip(), SHOWN_LINE)

    def test_forms_past_the_reading_limit_are_neither_walked_nor_read(self):
        # pypdf enters at most its configured number of forms; the walk stops at the same count, so every form
        # pypdf reads was judged. Here each placement's text lies off the page.
        import pypdf

        from tests.test_repairs_ingest_r2 import in_process
        data = form_pdf('q /Fx Do Q\n' * 5, f'BT /F1 12 Tf 700 500 Td ({esc(UNSHOWN)}) Tj ET')
        with pypdf.apply_configuration(xform_maximum_invocations_per_extraction=3):
            result = in_process(data)
        self.assertNotIn('cold snare', result.text)
        self.assertEqual(result.status, 'partial')
        self.assertIn(OFF_PAGE, result.messages)
        self.assertIn('Page 1 draws more form objects than the extractor reads; the rest of its text was not read.',
                      result.messages)

    def test_one_form_placed_on_and_off_the_page(self):
        form = f'BT /F1 12 Tf 0 10 Td ({esc(UNSHOWN)}) Tj ET'
        result = pdf_extract(form_pdf('q 1 0 0 1 72 400 cm /Fx Do Q\nq 1 0 0 1 700 400 cm /Fx Do Q', form,
                                      '[0 0 500 30]'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (OFF_PAGE,)))
        self.assertEqual(result.text.count('cold snare polypectomy'), 1)
        both = pdf_extract(form_pdf('q 1 0 0 1 72 400 cm /Fx Do Q\nq 1 0 0 1 72 300 cm /Fx Do Q', form,
                                    '[0 0 500 30]'), ocr=None)
        self.assertEqual((both.status, both.messages), ('ok', ()))
        self.assertEqual(both.text.count('cold snare polypectomy'), 2)

    def test_text_a_form_shows_is_read(self):
        cases = {'a form placed onto the page by its matrix': (
                     'q /Fx Do Q', f'BT /F1 12 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET', '[0 0 612 792]',
                     '/Matrix [1 0 0 1 0 -100]'),
                 'text straddling its form box': (
                     'q /Fx Do Q', f'BT /F1 12 Tf 72 96 Td ({esc(UNSHOWN)}) Tj ET', '[0 100 612 792]', ''),
                 'a form inheriting the font of the page': (
                     'BT /F1 12 Tf ET q /Fx Do Q', f'BT 72 500 Td ({esc(UNSHOWN)}) Tj ET', '[0 0 612 792]', '')}
        for label, (content, form_content, bbox, form_extra) in cases.items():
            with self.subTest(label):
                result = pdf_extract(form_pdf(content, form_content, bbox, form_extra=form_extra), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)


    def test_text_in_forms_nested_past_the_walk_depth_is_named(self):
        # Thirteen nested forms: the innermost text is read by pypdf but lies past the depth this walks.
        extra, resources = {}, '/XObject << /Fx 6 0 R >>'
        for level in range(13):
            number = 6 + level
            if level == 12:
                extra[number] = stream(SENTENCE, f'{FORM} /BBox [0 0 612 792]')
            else:
                extra[number] = stream('q /Fy Do Q', '/Type /XObject /Subtype /Form /BBox [0 0 612 792] '
                                                     f'/Resources << /XObject << /Fy {number + 1} 0 R >> >>')
        result = pdf_extract(placed_pdf('q /Fx Do Q', resources=resources, extra=extra), ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertIn(OBSCURED, result.messages)
        self.assertIn('cold snare polypectomy', result.text)

    def test_each_font_measures_its_own_strings(self):
        # The same string in Helvetica, then in the wider Courier: measured with Helvetica's widths the tail
        # after it would start on the page; with Courier's it starts past the edge and is not shown.
        lead = 'Findings: the mucosa of the colon looked normal throughout.'
        content = (f'BT /F1 12 Tf 72 600 Td ({esc(lead)}) Tj ET\n'
                   f'BT /F2 12 Tf 210 500 Td ({esc(lead)}) Tj ({esc(UNSHOWN)}) Tj ET')
        data = placed_pdf(content, resources='/Font << /F1 4 0 R /F2 7 0 R >>',
                          extra={7: b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>'})
        data = data.replace(b'/Font << /F1 4 0 R >> /Font << /F1 4 0 R /F2 7 0 R >>', b'/Font << /F1 4 0 R /F2 7 0 R >>')
        result = pdf_extract(serialise_again(data), ocr=None)
        self.assertEqual(result.messages, (OFF_PAGE,))
        self.assertNotIn('cold snare', result.text)


class ClippedTextTests(unittest.TestCase):
    """ingest:9 — text wholly outside its clipping path is not shown: excluded and named."""

    def test_text_outside_its_clipping_path_is_excluded(self):
        cases = {'C: the verifier\'s 0 0 1 1 re W n': f'q 0 0 1 1 re W n {SENTENCE} Q',
                 'an even-odd rectangle elsewhere': f'q 72 600 400 30 re W* n {SENTENCE} Q',
                 'a rotated rectangle elsewhere': ('q 0.7071 0.7071 -0.7071 0.7071 300 650 cm 0 0 100 20 re W n '
                                                   f'0.7071 -0.7071 0.7071 0.7071 -671.75 -247.49 cm {SENTENCE} Q'),
                 'a curved clip elsewhere': f'q 300 650 m 300 700 400 700 400 650 c 400 600 300 600 300 650 c h W n '
                                            f'{SENTENCE} Q',
                 # Its bounds hold the sentence; the shape does not: the arms pass either side, the bar below.
                 'a U-shaped clip around it': ('q 20 400 m 600 400 l 600 600 l 580 600 l 580 420 l 40 420 l 40 600 l '
                                               f'20 600 l h W n {SENTENCE} Q'),
                 'a U with a curved bar around it': ('q 20 600 m 20 420 l 20 300 600 300 600 420 c 600 600 l 580 600 l '
                                                     f'580 420 l 580 380 40 380 40 420 c 40 600 l h W n {SENTENCE} Q'),
                 'two clips that do not meet': f'q 0 0 300 792 re W n 320 0 292 792 re W n {SENTENCE} Q',
                 # Two nested rectangles under the even-odd rule: the inner one is a hole, and the sentence is in it.
                 'the hole of an even-odd clip': f'q 20 300 580 400 re 40 450 540 120 re W* n {SENTENCE} Q'}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (CLIPPED,)))
                self.assertEqual(result.text.strip(), SHOWN_LINE)
                self.assertEqual(colonoscopy(result.text), 'cancelled')

    def test_text_inside_its_clipping_path_is_read(self):
        rounded = ('60 480 m 540 480 l 550 480 560 490 560 500 c 560 520 l 560 530 550 540 540 540 c 60 540 l '
                   '50 540 40 530 40 520 c 40 500 l 40 490 50 480 60 480 c h W n')
        cases = {'a rectangle that holds it': f'q 40 480 560 60 re W n {SENTENCE} Q',
                 'a rounded rectangle that holds it': f'q {rounded} {SENTENCE} Q',
                 'a rotated rectangle that holds it': f'q 1 0.02 -0.02 1 0 0 cm 30 470 580 80 re W n '
                                                      f'1 -0.02 0.02 1 0 0 cm {SENTENCE} Q',
                 'restored by Q before the text': f'q 0 0 1 1 re W n Q {SENTENCE}',
                 'a flipped page-margin clip, as Chrome writes it': (
                     f'q 0.24 0 0 -0.24 0 792 cm 118.75 118.75 2314.0626 3064.0626 re W* n '
                     f'4.1667 0 0 -4.1667 0 3300 cm {SENTENCE} Q'),
                 'text straddling the clip edge': f'q 0 490 300 30 re W n {SENTENCE} Q',
                 # Under the non-zero rule the same two rectangles fill the inner one too.
                 'the same rectangles under the non-zero rule': f'q 20 300 580 400 re 40 450 540 120 re W n '
                                                                f'{SENTENCE} Q'}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)

    def test_a_clipping_path_too_complex_to_follow_is_named(self):
        points = ' '.join(f'{40 + i} {470 + (i % 2)} l' for i in range(600))
        content = f'q 40 470 m {points} 640 560 l 40 560 l h W n {SENTENCE} Q'
        result = pdf_extract(placed_pdf(content), ocr=None)
        self.assertEqual((result.status, result.messages), ('partial', (OBSCURED,)))
        self.assertIn('cold snare polypectomy', result.text)


class UnseenTextTests(unittest.TestCase):
    """ingest:9 — white text on the page, or text an opaque fill painted later covers, may not be shown: kept,
    named, partial."""

    def test_white_or_covered_text_is_named(self):
        cases = {'D: white text': f'1 1 1 rg {SENTENCE}',
                 'white text, DeviceGray': f'1 g {SENTENCE}',
                 'white text, CMYK': f'0 0 0 0 k {SENTENCE}',
                 'white text, an RGB colour space': f'/DeviceRGB cs 1 1 1 sc {SENTENCE}',
                 'white stroked text': f'1 1 1 RG 1 Tr {SENTENCE}',
                 'E: a white rectangle painted after it': f'{SENTENCE} 1 1 1 rg 60 490 500 30 re f',
                 'a black bar painted after it': f'{SENTENCE} 0 g 60 490 500 30 re f',
                 'a cover drawn with four sides': f'{SENTENCE} 1 g 60 490 m 560 490 l 560 520 l 60 520 l h f',
                 'a cover over one word': f'{SENTENCE} 1 g 140 495 60 20 re f',
                 'a cover over the band every glyph inks': f'{SENTENCE} 1 g 60 500.5 500 8 re f',
                 'an opaque image painted after it': f'{SENTENCE} q 500 0 0 30 60 490 cm /Im0 Do Q',
                 'a cover inside a form': f'{SENTENCE} q /Cv Do Q',
                 'a pattern fill painted after it (its opacity unknown)': f'{SENTENCE} /Pattern cs /P0 scn '
                                                                          '60 490 500 30 re f',
                 'invisible text over nothing': f'3 Tr {SENTENCE}',
                 'invisible clipping text over nothing': f'7 Tr {SENTENCE}',
                 'transparent text over nothing': f'/Clear gs {SENTENCE}',
                 'zero-size text': f'BT /F1 0 Tf 72 500 Td ({esc(UNSHOWN)}) Tj ET',
                 'text flattened by its matrix': f'BT /F1 12 Tf 1 0 0 0 72 500 Tm ({esc(UNSHOWN)}) Tj ET'}
        cover_form = stream('1 g 60 490 500 30 re f', '/Type /XObject /Subtype /Form /BBox [0 0 612 792]')
        image = stream(b'\xff' * 4, '/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray '
                                    '/BitsPerComponent 8')
        for label, content in cases.items():
            with self.subTest(label):
                data = placed_pdf(content, resources='/XObject << /Im0 6 0 R /Cv 7 0 R >> /ExtGState << /Clear << '
                                                     '/ca 0 /CA 0 >> >>', extra={6: image, 7: cover_form})
                result = pdf_extract(data, ocr=None)
                self.assertEqual((result.status, result.messages), ('partial', (OBSCURED,)))
                self.assertIn('cold snare polypectomy', result.text)

    def test_text_a_viewer_shows_is_read_without_a_message(self):
        cases = {'white text on a dark band': f'0 0 0.4 rg 60 490 500 30 re f 1 1 1 rg {SENTENCE}',
                 'white text on an image': f'q 500 0 0 30 60 490 cm /Im0 Do Q 1 g {SENTENCE}',
                 'white text in a form on a dark band': f'0.2 g 60 490 500 30 re f q /Wt Do Q',
                 'light grey text': f'0.9 g {SENTENCE}',
                 'invisible text over its scan (OCR layer)': f'q 500 0 0 30 60 490 cm /Im0 Do Q 3 Tr {SENTENCE}',
                 'invisible text under its scan (drawn first)': f'3 Tr {SENTENCE} 0 Tr q 500 0 0 30 60 490 cm /Mk Do Q',
                 'invisible text over glyph outlines': f'0 g 72 498 m 548 498 l 548 508 l 72 508 l h f 3 Tr {SENTENCE}',
                 'a faint watermark': f'/Faint gs 0.5 g {SENTENCE}',
                 'a white box beside the text': f'{SENTENCE} 1 g 72 440 400 30 re f',
                 'a white answer box right after the line': f'{SENTENCE} 1 g 560 490 40 30 re f',
                 # The label ends at x = 548.18; the box starts 0.2 pt before it, as in a real blank form.
                 'a white answer box touching the end of the line': f'{SENTENCE} 1 g 548 490 52 30 re f',
                 'an underline drawn as a fill': f'{SENTENCE} 0 g 72 497 480 1 re f',
                 'a rule through the descenders': f'{SENTENCE} 0 g 72 498 480 0.6 re f',
                 'a translucent highlight': f'{SENTENCE} /Half gs 1 1 0 rg 60 490 500 30 re f',
                 'a multiply highlight': f'{SENTENCE} /Mult gs 1 1 0 rg 60 490 500 30 re f',
                 'a stroked box around it': f'{SENTENCE} 0 G 2 w 60 490 500 30 re S',
                 'a masked image painted after it': f'{SENTENCE} q 500 0 0 30 60 490 cm /Mk Do Q',
                 'text drawn again after a cover': f'1 g 60 490 500 30 re f 0 g {SENTENCE}'}
        white_form = stream(f'1 g {SENTENCE}', f'{FORM} /BBox [0 0 612 792]')
        image = stream(b'\x80' * 4, '/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray '
                                    '/BitsPerComponent 8')
        mask = stream(b'\x80' * 4, '/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray '
                                   '/BitsPerComponent 8 /SMask 6 0 R')
        resources = ('/XObject << /Im0 6 0 R /Wt 7 0 R /Mk 8 0 R >> /ExtGState << /Half << /ca 0.4 >> '
                     '/Mult << /BM /Multiply >> /Faint << /ca 0.15 >> >>')
        for label, content in cases.items():
            with self.subTest(label):
                data = placed_pdf(content, resources=resources, extra={6: image, 7: white_form, 8: mask})
                result = pdf_extract(data, ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)


class StruckTextTests(unittest.TestCase):
    """ingest:8, the same marks drawn in the page's own content: a line across the middle of the glyphs (a
    browser's line-through, ReportLab's <strike>, a Word strikethrough) strikes the text through; it is kept,
    named and partial, never read as current with no limitation."""

    def test_text_struck_through_is_named(self):
        cases = {'a line-through drawn after the text, as a thin fill': f'{SENTENCE} 0 g 72 503 476 0.8 re f',
                 'a stroked line drawn after it': f'{SENTENCE} 0 G 0.8 w 72 503.4 m 548 503.4 l S',
                 'a strike line drawn first': f'0 G 0.8 w 72 503.4 m 548 503.4 l S {SENTENCE}',
                 'a line through one word': f'{SENTENCE} 0 g 140 503 40 0.8 re f',
                 'a red strike line': f'{SENTENCE} 1 0 0 rg 72 503 476 0.8 re f',
                 'a strike drawn by a form': f'{SENTENCE} q /Sk Do Q'}
        strike_form = stream('0 g 72 503 476 0.8 re f', '/Type /XObject /Subtype /Form /BBox [0 0 612 792]')
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content, resources='/XObject << /Sk 6 0 R >>', extra={6: strike_form}),
                                     ocr=None)
                self.assertEqual((result.status, result.messages), ('partial', (STRUCK_TEXT,)))
                self.assertIn('cold snare polypectomy', result.text)

    def test_lines_that_do_not_strike_the_text(self):
        cases = {'an underline': f'{SENTENCE} 0 g 72 498 476 0.8 re f',
                 'an underline drawn first': f'0 g 72 498 476 0.8 re f {SENTENCE}',
                 'an overline': f'{SENTENCE} 0 g 72 511 476 0.8 re f',
                 'a rule between lines': f'{SENTENCE} 0 G 0.5 w 72 515 m 548 515 l S',
                 'a ruled line drawn first, running past the text': f'0 G 0.5 w 0 503.4 m 612 503.4 l S {SENTENCE}',
                 'a vertical line across it': f'{SENTENCE} 0 G 0.5 w 300 480 m 300 530 l S',
                 'a tick through one letter': f'{SENTENCE} 0 g 72 503 5 0.8 re f',
                 'a box drawn around it': f'{SENTENCE} 0 G 0.5 w 66 494 488 22 re S',
                 'a thick translucent highlight': f'{SENTENCE} /Half gs 1 1 0 rg 60 497 500 14 re f'}
        for label, content in cases.items():
            with self.subTest(label):
                result = pdf_extract(placed_pdf(content, resources='/ExtGState << /Half << /ca 0.4 >> >>'), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('cold snare polypectomy', result.text)

    def test_reportlab_decorations(self):
        import io

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
        styles = getSampleStyleSheet()

        def built(flowables) -> bytes:
            buffer = io.BytesIO()
            SimpleDocTemplate(buffer, pagesize=letter, invariant=1).build(flowables)
            return buffer.getvalue()

        lead = Paragraph('Procedure: Colonoscopy to the cecum.', styles['Normal'])
        struck = pdf_extract(built([lead, Paragraph('<strike>Biopsy of the polyp was taken.</strike>',
                                                    styles['Normal'])]), ocr=None)
        self.assertEqual((struck.status, struck.messages), ('partial', (STRUCK_TEXT,)))
        for label, flowables in {
                'underlined': [lead, Paragraph('<u>Biopsy of the polyp was taken.</u>', styles['Normal'])],
                'a table grid': [Table([['Procedure', 'Colonoscopy'], ['Biopsy', 'taken, cold forceps']],
                                       style=TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                                                         ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))]}.items():
            with self.subTest(label):
                result = pdf_extract(built(flowables), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))


# --- ingest:8 — annotations that strike, redact or cover the text under them --------------------------

MARKED = ('Page 1 has strike-out, redaction or cover-up marks added as PDF annotations; the text under them was read '
          'as written, so check it against the original.')
DRAWN = ('Page 1 has handwriting, drawings or stamps added as PDF annotations; they are not text, so check the '
         'original.')
STRUCK = 'Biopsy of the polyp was taken with cold forceps.'
MARKUP_NOTE = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'),
               (72, 720, 'Date of service: 2026-10-21'), (72, 700, 'Procedure: Colonoscopy.'),
               (72, 680, 'Technique: The colonoscope was advanced to the cecum.'),
               (72, 660, 'Findings: A 6 mm sigmoid polyp was seen.'), (72, 640, STRUCK)]


def markup_pdf(annotation: str, appearance: str | None, *, rect=(70, 636, 340, 652), resources: str = '',
               extra: dict | None = None) -> bytes:
    """MARKUP_NOTE in Helvetica 11; one annotation (``annotation`` holds its /Subtype and keys) over the last line,
    drawn by ``appearance`` (a form over the annotation's rectangle) or, when None, by the viewer from its keys."""
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    content = '\n'.join(f'BT /F1 11 Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, text in MARKUP_NOTE)
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                   b'/Contents 5 0 R /Annots [7 0 R] >>'),
               4: HELVETICA, 5: stream(content)}
    ap = ''
    if appearance is not None:
        objects[8] = stream(appearance, f'/Type /XObject /Subtype /Form /BBox [0 0 {width} {height}] '
                                        f'/Resources << {resources} >>')
        ap = '/AP << /N 8 0 R >>'
    quads = f'{rect[0]} {rect[3]} {rect[2]} {rect[3]} {rect[0]} {rect[1]} {rect[2]} {rect[1]}'
    objects[7] = (f'<< /Type /Annot {annotation} /Rect [{rect[0]} {rect[1]} {rect[2]} {rect[3]}] '
                  f'/QuadPoints [{quads}] /F 4 /P 3 0 R {ap} >>').encode()
    objects.update(extra or {})
    return serialise(objects)


STRIKE_LINE = '1 0 0 RG 1.2 w 0 8 m 270 8 l S'
WHITE_FILL = '1 1 1 rg 0 0 270 16 re f'
BLACK_FILL = '0 g 0 0 270 16 re f'


class MarkupAnnotationTests(unittest.TestCase):
    """ingest:8 — a struck-through, redacted or covered sentence is never read as current with no limitation."""

    def test_marks_that_change_what_the_page_says_are_named_and_partial(self):
        cases = {'(a) StrikeOut with its line': ('/Subtype /StrikeOut /C [1 0 0]', STRIKE_LINE),
                 '(b) a white Square over the sentence': ('/Subtype /Square /IC [1 1 1] /C [1 1 1]', WHITE_FILL),
                 '(c) Redact with a black overlay': ('/Subtype /Redact /IC [0 0 0]', BLACK_FILL),
                 'a black Polygon over the sentence': ('/Subtype /Polygon /IC [0 0 0] /Vertices [70 636 340 636 '
                                                       '340 652 70 652]', BLACK_FILL)}
        for label, (annotation, appearance) in cases.items():
            with self.subTest(label):
                result = pdf_extract(markup_pdf(annotation, appearance), ocr=None)
                self.assertEqual((result.status, result.messages), ('partial', (MARKED, DRAWN)))
                self.assertIn(STRUCK, result.text)

    def test_marks_viewers_draw_without_an_appearance(self):
        cases = {'StrikeOut': '/Subtype /StrikeOut /C [1 0 0]', 'Redact': '/Subtype /Redact /IC [0 0 0]',
                 'a filled Square': '/Subtype /Square /IC [1 1 1]', 'a filled Circle': '/Subtype /Circle /IC [0 0 0]'}
        for label, annotation in cases.items():
            with self.subTest(label):
                result = pdf_extract(markup_pdf(annotation, None, rect=(60, 600, 360, 690) if 'Circle' in label
                                                else (70, 636, 340, 652)), ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertIn(MARKED, result.messages)
                self.assertIn(STRUCK, result.text)

    def test_drawings_that_leave_the_text_readable_are_only_noted(self):
        gstate = '/ExtGState << /Mul << /BM /Multiply >> >>'
        cases = {'Ink with the same line': ('/Subtype /Ink', STRIKE_LINE, ''),
                 'a multiply Highlight': ('/Subtype /Highlight /C [1 1 0]', '/Mul gs 1 1 0 rg 0 0 270 16 re f', gstate),
                 'an Underline': ('/Subtype /Underline', '0 0 1 RG 0 1 m 270 1 l S', ''),
                 'a Square drawn as a border': ('/Subtype /Square /C [1 0 0]', '1 0 0 RG 2 w 1 1 268 14 re S', ''),
                 'a translucent Square': ('/Subtype /Square /IC [1 1 1] /CA 0.3', WHITE_FILL, ''),
                 'a Circle drawn as a border': ('/Subtype /Circle /C [1 0 0]',
                                                '1 0 0 RG 135 0 m 270 0 270 16 135 16 c 0 16 0 0 135 0 c S', '')}
        for label, (annotation, appearance, resources) in cases.items():
            with self.subTest(label):
                result = pdf_extract(markup_pdf(annotation, appearance, resources=resources), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (DRAWN,)))
                self.assertIn(STRUCK, result.text)

    def test_a_filled_square_away_from_the_text_covers_nothing(self):
        result = pdf_extract(markup_pdf('/Subtype /Square /IC [1 1 1]', WHITE_FILL, rect=(70, 100, 340, 116)),
                             ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (DRAWN,)))

    def test_a_filled_circle_covers_only_its_ellipse(self):
        # The circle's rectangle reaches over the end of the sentence; the ellipse inside it does not.
        # The sentence ends at x = 305.6: the rectangle overlaps it by 25 pt, the inscribed one not at all.
        result = pdf_extract(markup_pdf('/Subtype /Circle /IC [0 0 0]', None, rect=(280, 450, 480, 650)), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_a_hidden_mark_is_not_shown(self):
        data = markup_pdf('/Subtype /StrikeOut /C [1 0 0]', STRIKE_LINE).replace(b'/F 4 /P 3 0 R', b'/F 2 /P 3 0 R')
        result = pdf_extract(serialise_again(data), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_a_struck_line_on_a_page_read_with_ocr_is_still_named(self):
        from tests.test_ingest import FakeOcr
        image = stream(b'\xff' * 4, '/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray '
                                    '/BitsPerComponent 8')
        data = markup_pdf('/Subtype /StrikeOut /C [1 0 0]', STRIKE_LINE)
        # Replace the typed note by a full-page scan: the page is read with OCR.
        data = data.replace(b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R',
                            b'/Resources << /XObject << /Im0 9 0 R >> >> /Contents 10 0 R')
        objects_pdf = serialise_again(data[:data.rindex(b'xref\n')] + b'9 0 obj\n' + image + b'\nendobj\n10 0 obj\n'
                                      + stream('q 612 0 0 792 0 0 cm /Im0 Do Q') + b'\nendobj\n'
                                      + data[data.rindex(b'xref\n'):])
        with FakeOcr() as fake:
            result = pdf_extract(objects_pdf, ocr=fake.tools)
        self.assertEqual(result.method, 'pdf-ocr')
        self.assertEqual(result.status, 'partial')
        self.assertIn(MARKED, result.messages)


if __name__ == '__main__':
    unittest.main()
