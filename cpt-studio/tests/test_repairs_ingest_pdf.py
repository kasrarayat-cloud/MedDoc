"""Regression tests for the PDF ingestion repairs (refutation round 1: ingest:0, 2, 3, 4, 8, 12).

Every document is synthetic and built here, from raw PDF syntax or with
reportlab, Pillow and pypdf; nothing is read from disk. Each class names the
finding it pins and carries positive controls showing that ordinary documents
still extract 'ok' with the same text.
"""
from __future__ import annotations

import io
import re
import tempfile
import textwrap
import time
import unittest
import zlib

import pypdf
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from studio.ingest import Limits, extract_document
from studio.ingest.pdf import extract_pdf
from tests.support import docgen
from tests.test_ingest import FakeOcr, page_texts

PDF = 'application/pdf'
OCR_NOTE = 'OCR can misread characters — check evidence against the original.'
HELVETICA = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
ZAPF = b'<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>'


# --- builders -----------------------------------------------------------------------

def serialise_again(data: bytes) -> bytes:
    """Rebuild a one-revision PDF from its objects after an in-place edit changed their lengths."""
    body = data[:data.rindex(b'xref\n')]
    objects = {int(match.group(1)): match.group(2)
               for match in re.finditer(rb'(\d+) 0 obj\n(.*?)\nendobj\n', body, re.S)}
    return serialise(objects)


def esc(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def serialise(objects: dict[int, bytes], root: int = 1) -> bytes:
    """A complete one-revision PDF from numbered object bodies, with an exact xref."""
    out = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n'
    size = max(objects) + 1
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    for number in range(1, size):
        out += b'%010d 00000 n \n' % offsets[number] if number in offsets else b'0000000000 65535 f \n'
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, root, xref)
    return bytes(out)


def stream(data: bytes | str, extra: str = '') -> bytes:
    raw = data.encode('latin-1') if isinstance(data, str) else data
    return f'<< {extra} /Length {len(raw)} >>\nstream\n'.encode() + raw + b'\nendstream'


def text_ops(lines) -> str:
    return '\n'.join(f'BT /F1 {size} Tf {x} {y} Td ({esc(text)}) Tj ET' for x, y, size, text in lines)


def one_page(content: str | bytes, *, annots: str = '', catalog: str = '', resources: str = '',
             extra_objects: dict[int, bytes] | None = None) -> bytes:
    """Objects 1-5: catalog, pages, page, Helvetica /F1, content. Extra objects from 6 up."""
    objects = {1: f'<< /Type /Catalog /Pages 2 0 R {catalog} >>'.encode(),
               2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> '
                   f'{resources} >> /Contents 5 0 R {annots} >>').encode(),
               4: HELVETICA,
               5: stream(content)}
    objects.update(extra_objects or {})
    return serialise(objects)


def extract(data: bytes, **kwargs):
    return extract_document(data, 'synthetic.pdf', PDF, **kwargs)


def in_process(data: bytes, limits: Limits | None = None, tools=None):
    with tempfile.TemporaryDirectory() as workdir:
        return extract_pdf(data, limits or Limits(), tools, time.monotonic() + 60, workdir)


# --- ingest:0 — filled form fields, FreeText annotations and XFA -----------------------

BANNER = 'SYNTHETIC TEST DOCUMENT - fictional patient - NOT FOR BILLING'
FORM_LABELS = [(72, 740, 9, BANNER), (72, 712, 14, 'Endoscopy unit - procedure form (fictional practice)'),
               (72, 680, 11, 'Date of service:'), (72, 650, 11, 'Procedure performed:'),
               (72, 620, 11, 'Finding / intervention:'), (72, 590, 11, 'Extent reached:'),
               (72, 560, 11, 'Biopsy taken:')]
FORM_VALUES = {'dos': ('2026-10-21', (200, 675, 560, 693)),
               'procedure': ('Colonoscopy, screening, to the cecum', (200, 645, 560, 663)),
               'intervention': ('7 mm sigmoid polyp removed with cold snare (polypectomy)', (200, 615, 590, 633)),
               'extent': ('Cecum - appendiceal orifice and ileocecal valve photographed', (200, 585, 590, 603))}
FORM_BLOCK = ('[PDF form fields on page 1]\n'
              'dos: 2026-10-21\n'
              'procedure: Colonoscopy, screening, to the cecum\n'
              'intervention: 7 mm sigmoid polyp removed with cold snare (polypectomy)\n'
              'extent: Cecum - appendiceal orifice and ileocecal valve photographed\n'
              'biopsy: checked')
FIELDS_NOTE = ('Page 1 has PDF form fields; their values were read and added after the page text, labelled as form '
               'fields.')
ANNOTATION_NOTE = ('Page 1 has text added as PDF annotations; it was read and added after the page text, labelled as '
                   'annotation text.')
XFA_NOTE = ('The PDF contains an XFA form; XFA content is not read, so form content that an XFA-capable viewer shows '
            'may be missing from the text.')


def acroform_pdf(*, checked: bool = True, flags: int = 4, value_override: dict | None = None,
                 appearance_override: dict | None = None, need_appearances: str = 'false',
                 rect_override: dict | None = None) -> bytes:
    """Labels in the content stream; the values only in widget annotations (/V plus an /AP drawing it)."""
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R /AcroForm 10 0 R >>',
               2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               4: HELVETICA,
               5: stream(text_ops(FORM_LABELS)),
               6: ZAPF}
    widgets, number = [], 11
    for name, (value, rect) in FORM_VALUES.items():
        stored = (value_override or {}).get(name, value)
        shown = (appearance_override or {}).get(name, value)
        rect = (rect_override or {}).get(name, rect)
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Tx /T ({name}) /V ({esc(stored)}) '
                           f'/Rect [{rect[0]} {rect[1]} {rect[2]} {rect[3]}] /F {flags} /P 3 0 R '
                           f'/DA (/Helv 11 Tf 0 g) /AP << /N {number + 1} 0 R >> >>').encode()
        objects[number + 1] = stream(f'/Tx BMC q BT /Helv 11 Tf 0 g 2 4 Td ({esc(shown)}) Tj ET Q EMC',
                                     f'/Type /XObject /Subtype /Form /BBox [0 0 {width} {height}] '
                                     f'/Resources << /Font << /Helv 4 0 R >> >>')
        widgets.append(number)
        number += 2
    state = '/Yes' if checked else '/Off'
    objects[number] = (f'<< /Type /Annot /Subtype /Widget /FT /Btn /T (biopsy) /V {state} /AS {state} '
                       f'/Rect [200 555 214 569] /F {flags} /P 3 0 R /MK << /CA (4) >> /DA (/ZaDb 0 Tf 0 g) '
                       f'/AP << /N << /Yes {number + 1} 0 R /Off {number + 2} 0 R >> >> >>').encode()
    objects[number + 1] = stream('q BT /ZaDb 12 Tf 0 g 1.5 2.5 Td (4) Tj ET Q',
                                 '/Type /XObject /Subtype /Form /BBox [0 0 14 14] '
                                 '/Resources << /Font << /ZaDb 6 0 R >> >>')
    objects[number + 2] = stream('', '/Type /XObject /Subtype /Form /BBox [0 0 14 14]')
    widgets.append(number)
    refs = ' '.join(f'{n} 0 R' for n in widgets)
    objects[3] = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  f'/Contents 5 0 R /Annots [{refs}] >>').encode()
    objects[10] = (f'<< /Fields [{refs}] /NeedAppearances {need_appearances} /DA (/Helv 0 Tf 0 g) '
                   f'/DR << /Font << /Helv 4 0 R /ZaDb 6 0 R >> >> >>').encode()
    return serialise(objects)


REPORT_LINES = [(72, 740, 9, BANNER), (72, 712, 14, 'Colonoscopy report (fictional practice)'),
                (72, 684, 11, 'Date of service: 2026-10-21'),
                (72, 666, 11, 'Procedure: Colonoscopy, diagnostic, to the cecum.'),
                (72, 648, 11, 'Indication: change in bowel habit.'),
                (72, 630, 11, 'Findings: normal mucosa throughout. No polyps seen on withdrawal.'),
                (72, 612, 11, 'Impression: normal colonoscopy to the cecum.')]
ADDENDUM = ('Addendum (corrected by endoscopist): a 4 mm descending colon polyp was removed '
            'with cold snare polypectomy; impression amended.')


def freetext_pdf(*, flags: int = 4, rect: str = '72 540 542 580', contents: str = ADDENDUM,
                 subtype: str = 'FreeText', popup_note: str = '', appearance: bool = True, annot_extra: str = '',
                 catalog: str = '', extra_objects: dict[int, bytes] | None = None) -> bytes:
    """A typed report plus one annotation (object 6) whose appearance (object 7) draws ADDENDUM over two lines."""
    note = f' /T (Synthetic reviewer) /Contents ({esc(popup_note)})' if popup_note else ''
    body = f'/Contents ({esc(contents)})' if subtype == 'FreeText' else note
    ap = '/AP << /N 7 0 R >>' if appearance else ''
    objects = {6: (f'<< /Type /Annot /Subtype /{subtype} /Rect [{rect}] /F {flags} /P 3 0 R {body} {annot_extra} '
                   f'/DA (/Helv 10 Tf 0 0 1 rg) {ap} >>').encode(),
               7: stream('q BT /Helv 10 Tf 0 0 1 rg 2 26 Td (' + esc(ADDENDUM[:80]) + ') Tj 0 -13 Td ('
                         + esc(ADDENDUM[80:]) + ') Tj ET Q',
                         '/Type /XObject /Subtype /Form /BBox [0 0 470 40] /Resources << /Font << /Helv 4 0 R >> >>')}
    objects.update(extra_objects or {})
    return one_page(text_ops(REPORT_LINES), annots='/Annots [6 0 R]', catalog=catalog, extra_objects=objects)


XDP = ('<?xml version="1.0" encoding="UTF-8"?><xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'
       '<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data><form1>'
       '<dos>2026-10-21</dos><procedure>Colonoscopy to the cecum</procedure>'
       '<intervention>7 mm sigmoid polyp removed with cold snare polypectomy</intervention>'
       '</form1></xfa:data></xfa:datasets></xdp:xdp>')
XFA_SHELL = [(72, 740, 11, 'Please wait...'),
             (72, 716, 10, 'If this message is not eventually replaced by the proper contents of the document, '
                            'your PDF'),
             (72, 702, 10, 'viewer may not be able to display this type of document.')]


def xfa_pdf(needs_rendering: bool = True) -> bytes:
    flag = '/NeedsRendering true' if needs_rendering else ''
    return one_page(text_ops(XFA_SHELL), catalog=f'/AcroForm 6 0 R {flag}',
                    extra_objects={6: b'<< /Fields [] /XFA 7 0 R >>', 7: stream(XDP)})


def reportlab_form(fill: dict | None, biopsy: str | None) -> bytes:
    """A reportlab AcroForm (blank), optionally filled with pypdf as a viewer's save would."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter, invariant=1)
    for x, y, size, text in FORM_LABELS:
        canvas.setFont('Helvetica', size)
        canvas.drawString(x, y, text)
    for name, (_, rect) in FORM_VALUES.items():
        canvas.acroForm.textfield(name=name, x=rect[0], y=rect[1], width=rect[2] - rect[0],
                                  height=rect[3] - rect[1], value='', borderWidth=0, fontSize=10)
    canvas.acroForm.checkbox(name='biopsy', x=200, y=555, size=14, checked=False, buttonStyle='check')
    canvas.showPage()
    canvas.save()
    if fill is None:
        return buffer.getvalue()
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(buffer.getvalue())))
    writer.update_page_form_field_values(writer.pages[0], fill, auto_regenerate=False)
    if biopsy:
        writer.update_page_form_field_values(writer.pages[0], {'biopsy': biopsy}, auto_regenerate=False)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class PdfFormAndAnnotationTests(unittest.TestCase):
    """ingest:0 — what a form or an annotation shows is read, or the result says it was not."""

    def test_filled_acroform_values_are_read_into_a_labelled_block(self):
        result = extract(acroform_pdf(), ocr=None)
        self.assertEqual((result.status, result.method, result.ocr_pages), ('ok', 'pdf-text', ()))
        self.assertTrue(result.text.endswith('Biopsy taken:\n\n' + FORM_BLOCK), result.text)
        self.assertEqual(result.messages, (FIELDS_NOTE,))
        self.assertEqual(len(result.pages), 1)

    def test_unchecked_box_is_read_as_not_checked(self):
        result = extract(acroform_pdf(checked=False), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertTrue(result.text.endswith('biopsy: not checked'), result.text)

    def test_check_box_without_appearance_states_reads_its_value(self):
        for value, expected in (('/Yes', 'biopsy: checked'), ('/Off', 'biopsy: not checked')):
            with self.subTest(value=value):
                data = acroform_pdf().replace(b'/V /Yes /AS /Yes', b'/V ' + value.encode())
                data = re.sub(rb'/AP << /N << /Yes \d+ 0 R /Off \d+ 0 R >> >>', b'', data)
                self.assertNotIn(b'/AS', data)
                result = extract(serialise_again(data), ocr=None)
                self.assertTrue(result.text.endswith(expected), result.text)

    def test_reportlab_form_filled_by_pypdf_is_read(self):
        fill = {name: value for name, (value, _) in FORM_VALUES.items()}
        result = extract(reportlab_form(fill, '/Yes'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        for value, _ in FORM_VALUES.values():
            self.assertIn(value, result.text)
        self.assertIn('biopsy: checked', result.text)

    def test_blank_form_lists_only_its_box_state(self):
        result = extract(reportlab_form(None, None), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertTrue(result.text.endswith('Biopsy taken:\n\n[PDF form fields on page 1]\nbiopsy: not checked'),
                        result.text)

    def test_hidden_widgets_are_not_read_and_are_named(self):
        for flags in (2, 32, 6):  # Hidden, NoView, Hidden plus Print
            with self.subTest(flags=flags):
                result = extract(acroform_pdf(flags=flags), ocr=None)
                self.assertEqual(result.status, 'ok')
                self.assertNotIn('2026-10-21', result.text)
                self.assertNotIn('[PDF form fields', result.text)
                self.assertEqual(result.messages, ('Page 1 has hidden form fields or annotations; their text was '
                                                   'not extracted.',))

    def test_widget_outside_the_page_is_not_read(self):
        rects = {name: (700, 700, 900, 720) for name in FORM_VALUES}
        result = extract(acroform_pdf(rect_override=rects), ocr=None)
        self.assertNotIn('Colonoscopy, screening', result.text)
        self.assertIn('biopsy: checked', result.text)

    def test_value_that_differs_from_what_the_field_shows_is_partial(self):
        result = extract(acroform_pdf(appearance_override={'procedure': 'Colonoscopy cancelled before sedation'}),
                         ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertIn('procedure: Colonoscopy, screening, to the cecum', result.text)
        self.assertIn('Page 1: form field "procedure" shows text that differs from its stored value; the stored '
                      'value was read, so check it against the original.', result.messages)

    def test_need_appearances_trusts_the_stored_value(self):
        result = extract(acroform_pdf(appearance_override={'procedure': 'stale appearance'},
                                      need_appearances='true'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))

    def test_freetext_annotation_is_read_once(self):
        result = extract(freetext_pdf(), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION_NOTE,)))
        self.assertTrue(result.text.endswith('\n\n[PDF annotation text on page 1]\n' + ADDENDUM), result.text)
        self.assertEqual(result.text.count('cold snare polypectomy'), 1)

    def test_hidden_or_off_page_freetext_is_not_read(self):
        for kwargs in ({'flags': 2}, {'rect': '700 700 900 760'}, {'rect': '72 540 72 580'}):
            with self.subTest(**kwargs):
                result = extract(freetext_pdf(**kwargs), ocr=None)
                self.assertNotIn('polypectomy', result.text)
                self.assertNotIn('[PDF annotation', result.text)

    def test_stamp_whose_appearance_draws_text_is_read(self):
        result = extract(freetext_pdf(subtype='Stamp'), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertIn('[PDF annotation text on page 1]\n' + ADDENDUM[:80] + '\n' + ADDENDUM[80:], result.text)

    def test_rich_text_only_freetext_is_read(self):
        markup = (f'<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml"><p dir="ltr">{ADDENDUM[:80]}'
                  f'<span style="color:#0000FF">{ADDENDUM[80:]}</span></p></body>')
        result = extract(freetext_pdf(contents='', appearance=False, annot_extra=f'/RC ({esc(markup)})'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (ANNOTATION_NOTE,)))
        self.assertTrue(result.text.endswith('[PDF annotation text on page 1]\n' + ADDENDUM), result.text)

    def test_comment_notes_are_counted_not_read(self):
        result = extract(freetext_pdf(subtype='Text', popup_note='Polypectomy was not done.', appearance=False),
                         ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertNotIn('Polypectomy was not done', result.text)
        self.assertEqual(result.messages, ('Comment text in PDF annotations is not extracted (22 characters).',))

    def test_a_page_of_form_fields_alone_starts_with_its_block(self):
        data = acroform_pdf().replace(b'/Contents 5 0 R /Annots', b'/Annots')
        result = extract(serialise_again(data), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
        self.assertEqual(result.text, FORM_BLOCK)

    def test_hidden_layer_inside_an_appearance_is_not_read(self):
        appearance = ('q BT /Helv 10 Tf 0 0 1 rg 2 26 Td (Reviewed: no polyp seen.) Tj ET '
                      '/OC /oc9 BDC BT /Helv 10 Tf 2 13 Td (Draft: cold snare polypectomy done.) Tj ET EMC Q')
        data = freetext_pdf(subtype='Stamp', catalog='/OCProperties << /OCGs [9 0 R] /D << /OFF [9 0 R] >> >>',
                            extra_objects={9: b'<< /Type /OCG /Name (Draft) >>',
                                           7: stream(appearance, '/Type /XObject /Subtype /Form /BBox [0 0 470 40] '
                                                     '/Resources << /Font << /Helv 4 0 R >> /Properties << '
                                                     '/oc9 9 0 R >> >>')})
        result = extract(data, ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertIn('[PDF annotation text on page 1]\nReviewed: no polyp seen.', result.text)
        self.assertNotIn('polypectomy', result.text)
        self.assertIn(LAYER_NOTE, result.messages)

    def test_appearance_in_a_hidden_layer_draws_nothing(self):
        data = freetext_pdf(subtype='Stamp', catalog='/OCProperties << /OCGs [9 0 R] /D << /OFF [9 0 R] >> >>',
                            extra_objects={9: b'<< /Type /OCG /Name (Draft) >>',
                                           7: stream('BT /Helv 10 Tf 2 13 Td (Draft: cold snare polypectomy.) Tj ET',
                                                     '/Type /XObject /Subtype /Form /BBox [0 0 470 40] /OC 9 0 R '
                                                     '/Resources << /Font << /Helv 4 0 R >> >>')})
        result = extract(data, ocr=None)
        self.assertNotIn('polypectomy', result.text)
        self.assertNotIn('[PDF annotation', result.text)

    def test_dynamic_xfa_form_is_partial(self):
        for needs_rendering in (True, False):
            with self.subTest(needs_rendering=needs_rendering):
                result = extract(xfa_pdf(needs_rendering), ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertEqual(result.messages, (XFA_NOTE,))

    def test_flattened_form_control_is_unchanged(self):
        lines = list(FORM_LABELS) + [(rect[0] + 2, rect[1] + 4, 11, value) for value, rect in FORM_VALUES.values()]
        result = extract(one_page(text_ops(lines)), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        for value, _ in FORM_VALUES.values():
            self.assertIn(value, result.text)
        self.assertNotIn('[PDF', result.text)


# --- ingest:2 — the page tree, not the declared /Count ------------------------------------

THREE_PAGES = ['SYNTHETIC TEST DOCUMENT - NOT A REAL PATIENT. Endoscopy unit procedure record. Date of service '
               '2026-10-20.',
               'Colonoscopy was advanced to the cecum. A 6 mm sessile polyp in the sigmoid colon was removed with '
               'cold snare polypectomy.',
               'ERCP was performed. A biliary sphincterotomy was done and common bile duct stones were extracted.']
FORTY_ONE = [f'SYNTHETIC page {n} of a synthetic record, routine filler text.' for n in range(1, 41)] + [
    'SYNTHETIC page 41. ERCP was performed with biliary stent placement.']


def text_pdf(pages: list[str], *, encrypt: bool) -> bytes:
    data = docgen.make_pdf(pages)
    if not encrypt:
        return data
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password='', owner_password='synthetic-owner', algorithm='RC4-128')
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def patch_count(data: bytes, old: int, new: int) -> bytes:
    """Rewrite the root /Count in place (same length, so every xref offset stays valid)."""
    assert len(str(old)) == len(str(new))
    pattern = re.compile(rb'/Count ' + str(old).encode() + rb'(?!\d)')
    assert len(pattern.findall(data)) == 1, 'expected exactly one /Count to patch'
    patched = pattern.sub(b'/Count ' + str(new).encode(), data)
    assert len(patched) == len(data) and patched != data
    return patched


class PdfPageCountTests(unittest.TestCase):
    """ingest:2 — a /Count that disagrees with the page tree fails; the page limit counts real pages."""

    def test_understated_count_fails_encrypted_or_not(self):
        for encrypt in (True, False):
            with self.subTest(encrypt=encrypt):
                data = patch_count(text_pdf(THREE_PAGES, encrypt=encrypt), 3, 1)
                result = extract(data, ocr=None)
                self.assertEqual((result.status, result.text), ('failed', ''))
                self.assertEqual(result.messages,
                                 ('The PDF is damaged: its page count says 1 page but its page tree holds 3 pages.',))

    def test_page_limit_applies_to_the_page_tree(self):
        for encrypt in (True, False):
            with self.subTest(encrypt=encrypt):
                result = extract(patch_count(text_pdf(FORTY_ONE, encrypt=encrypt), 41, 40), ocr=None)
                self.assertEqual(result.status, 'failed')
                self.assertEqual(result.messages, ('The PDF is damaged: its page count says 40 pages but its page '
                                                   'tree holds 41 pages.',))
                honest = extract(text_pdf(FORTY_ONE, encrypt=encrypt), ocr=None)
                self.assertEqual(honest.messages, ('The PDF has 41 pages; the limit is 40.',))

    def test_honest_encrypted_pdf_reads_every_page(self):
        result = extract(text_pdf(THREE_PAGES, encrypt=True), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertEqual([text.strip() for text in page_texts(result)],
                         ['\n'.join(textwrap.wrap(page, docgen.PDF_LINE_CHARS)) for page in THREE_PAGES])

    def test_overstated_count_fails(self):
        data = patch_count(text_pdf(THREE_PAGES, encrypt=True), 3, 5)
        self.assertEqual(extract(data, ocr=None).messages,
                         ('The PDF is damaged: its page count says 5 pages but its page tree holds 3 pages.',))


# --- ingest:3 — a page-sized image beside a short text layer ----------------------------------

STAMP = 'Received via secure e-fax 2026-10-21 14:32 UTC - Page 1 of 1'
SCAN_NOTE = ('Page {n} is mostly covered by an image and has only a short text layer (for example a stamp or a fax '
             'header), so it may be a scan; OCR is not available on this server, so the image was not read.')
TYPED = 'Office visit, established patient. Total time 25 minutes. Plan: colonoscopy reviewed.'


def scan_page(kind: str, pixels: tuple[int, int], *, stamp: str = STAMP, bands: int = 1,
              placed: tuple[float, float, float, float] = (0, 0, 612, 792)) -> bytes:
    """A letter page painted with a white 'scan' of ``pixels`` (one image, bands, or inline), plus a stamp line."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter, invariant=1)
    x, y, width, height = placed
    image = Image.new('L', pixels, 255)
    if kind == 'inline':
        canvas.drawInlineImage(image, x, y, width=width, height=height)
    else:
        band = -(-pixels[1] // bands)
        for index in range(bands):
            top, bottom = index * band, min(pixels[1], (index + 1) * band)
            piece = image if bands == 1 else image.crop((0, top, pixels[0], bottom))
            canvas.drawImage(ImageReader(piece), x, y + height - bottom / pixels[1] * height, width=width,
                             height=(bottom - top) / pixels[1] * height)
    if stamp:
        canvas.setFont('Helvetica', 8)
        canvas.drawString(36, 778, stamp)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


SCAN_SHAPES = {'96 dpi single image': ('xobject', (816, 1056), 1),
               '300 dpi in nine bands': ('xobject', (2550, 3300), 9),
               'inline image': ('inline', (1700, 2200), 1)}


class PdfScanBesideStampTests(unittest.TestCase):
    """ingest:3 — decided by the page area images cover, not by one image's pixel count."""

    def test_scan_with_a_stamp_is_not_read_without_ocr(self):
        for name, (kind, pixels, bands) in SCAN_SHAPES.items():
            with self.subTest(name):
                alone = extract(scan_page(kind, pixels, bands=bands), ocr=None)
                self.assertEqual((alone.status, alone.text), ('failed', ''))
                self.assertEqual(alone.messages, (SCAN_NOTE.format(n=1), 'No text could be read from the PDF.'))
                mixed = extract(docgen.concat_pdfs([docgen.make_pdf([TYPED]), scan_page(kind, pixels, bands=bands)]),
                                ocr=None)
                self.assertEqual((mixed.status, mixed.method, mixed.ocr_pages), ('partial', 'pdf-text', ()))
                self.assertEqual(mixed.messages, (SCAN_NOTE.format(n=2),))
                self.assertEqual([text.strip() for text in page_texts(mixed)], [TYPED, STAMP])

    def test_scan_with_a_stamp_is_read_with_ocr(self):
        with FakeOcr() as fake:
            for name, (kind, pixels, bands) in SCAN_SHAPES.items():
                with self.subTest(name):
                    result = extract(scan_page(kind, pixels, bands=bands), ocr=fake.tools)
                    self.assertEqual((result.status, result.method, result.ocr_pages), ('ok', 'pdf-ocr', (1,)))
                    self.assertEqual(result.text, 'Synthetic OCR text for page 1: cecum reached, cold snare '
                                                  'polypectomy.\n')
                    self.assertEqual(result.messages, (f'Page 1 was read with OCR; {OCR_NOTE}',
                                                       'Page 1 is mostly covered by an image and has only a short '
                                                       'text layer, so it was read with OCR instead.'))

    def test_failed_ocr_keeps_the_stamp_and_is_partial(self):
        recognise = 'if [ "$page" = "page 2" ]; then exit 3; fi\n' + FakeOcr.RECOGNISE
        with FakeOcr(recognise=recognise) as fake:
            result = extract(docgen.concat_pdfs([docgen.make_pdf([TYPED]), scan_page('xobject', (816, 1056))]),
                             ocr=fake.tools)
        self.assertEqual((result.status, result.method, result.ocr_pages), ('partial', 'pdf-text', ()))
        self.assertEqual([text.strip() for text in page_texts(result)], [TYPED, STAMP])
        self.assertEqual(result.messages, ('Page 2 is mostly covered by an image and has only a short text layer, '
                                           'and OCR could not read it (tesseract exited with status 3).',))

    def test_truncated_scan_read_with_ocr_is_damaged(self):
        buffer = io.BytesIO()
        Image.new('L', (850, 1100), 255).save(buffer, format='JPEG', quality=90)
        jpeg = buffer.getvalue()

        def scan(data: bytes) -> bytes:
            return one_page('q 612 0 0 792 0 0 cm /Im1 Do Q', resources='/XObject << /Im1 6 0 R >>', extra_objects={
                6: (b'<< /Type /XObject /Subtype /Image /Width 850 /Height 1100 /ColorSpace /DeviceGray '
                    b'/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n' % len(data) + data
                    + b'\nendstream')})

        damaged = 'Page 1 is damaged: part of its content could not be decoded, so its text may be incomplete or wrong.'
        with FakeOcr() as fake:
            for label, data, expected in (('whole', jpeg, ('ok', ())),
                                          ('bytes after the end marker', jpeg + b'SEFT' * 2000, ('ok', ())),
                                          ('cut by a third', jpeg[:len(jpeg) * 2 // 3], ('partial', (damaged,))),
                                          ('cut before the end marker', jpeg[:-2], ('partial', (damaged,)))):
                with self.subTest(label):
                    result = extract(scan(data), ocr=fake.tools)
                    self.assertEqual(result.ocr_pages, (1,))
                    self.assertEqual((result.status, result.messages[1:]), expected)

    def test_unstamped_scan_is_still_a_page_without_a_text_layer(self):
        result = extract(scan_page('xobject', (816, 1056), stamp=''), ocr=None)
        self.assertEqual(result.messages, ('Page 1 has no usable text layer and OCR is not available on this server.',
                                           'No text could be read from the PDF.'))

    def test_stretched_low_resolution_background_is_not_a_scan(self):
        for pixels in ((1, 1), (100, 100)):
            with self.subTest(pixels=pixels):
                buffer = io.BytesIO()
                canvas = Canvas(buffer, pagesize=letter, invariant=1)
                canvas.drawImage(ImageReader(Image.new('L', pixels, 230)), 0, 0, width=612, height=792)
                canvas.setFont('Helvetica', 8)
                canvas.drawString(36, 778, STAMP)
                canvas.showPage()
                canvas.save()
                result = extract(buffer.getvalue(), ocr=None)
                self.assertEqual((result.status, result.messages, result.text.strip()), ('ok', (), STAMP))

    def test_text_page_with_a_photo_or_a_logo_is_unchanged(self):
        text = 'Colonoscopy report. Cecum reached. One 5 mm polyp removed with cold snare from the sigmoid colon.'
        for pixels, placed in (((300, 200), (72, 600, 150, 100)), ((800, 600), (72, 300, 288, 216))):
            with self.subTest(pixels=pixels):
                buffer = io.BytesIO()
                canvas = Canvas(buffer, pagesize=letter, invariant=1)
                canvas.drawString(72, 720, text)
                canvas.drawImage(ImageReader(Image.new('L', pixels, 255)), *placed)
                canvas.showPage()
                canvas.save()
                result = extract(buffer.getvalue(), ocr=None)
                self.assertEqual((result.status, result.messages, result.text.strip()), ('ok', (), text))

    def test_page_sized_image_under_a_full_text_layer_is_named_not_partial(self):
        body = ' '.join(['Synthetic searchable scan text: colonoscopy to the cecum, cold snare polypectomy.'] * 4)
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=letter, invariant=1)
        canvas.drawImage(ImageReader(Image.new('L', (816, 1056), 255)), 0, 0, width=612, height=792)
        for number, line in enumerate(textwrap.wrap(body, docgen.PDF_LINE_CHARS)):
            canvas.drawString(36, 740 - 14 * number, line)
        canvas.showPage()
        canvas.save()
        result = extract(buffer.getvalue(), ocr=None)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.messages, ('Page 1 combines a text layer with a large image; only the text layer was '
                                           'read, so check the text against the original if the image holds text.',))


# --- ingest:4 — a damaged compressed content stream ------------------------------------------

PAGE1_LINES = ['SYNTHETIC TEST DOCUMENT - NOT A REAL PATIENT', 'Gastroenterology procedure report',
               'Date of service: 2026-10-20. Setting: hospital outpatient department.',
               'Indication: iron deficiency anemia, surveillance after prior adenoma.']
PAGE2_LINES = ['Procedures performed today:', '1. EGD with cold forceps biopsy of the gastric antrum.',
               '2. Colonoscopy to the cecum with cold snare polypectomy, ascending colon.',
               '3. Hot snare polypectomy of a 14 mm sigmoid polyp.',
               '4. Submucosal tattoo injection at the sigmoid polypectomy site.',
               '5. Retroflexion in the rectum performed; withdrawal time 11 minutes.']
DAMAGED_NOTE = ('Page 2 is damaged: part of its content could not be decoded, so its text may be incomplete or '
                'wrong.')


def page_content(lines: list[str]) -> bytes:
    ops = ['BT', '/F1 11 Tf', '14 TL', '72 720 Td'] + [f'({esc(line)}) Tj T*' for line in lines] + ['ET']
    return ('\n'.join(ops) + '\n').encode('latin-1')


def flate_pdf(page2_stream: bytes, level: int = 6) -> bytes:
    """Two pages; page 2's content is ``page2_stream`` declared as FlateDecode, /Length its real length."""
    first = zlib.compress(page_content(PAGE1_LINES), level)
    page = ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> '
            '/Contents {} 0 R >>')
    return serialise({1: b'<< /Type /Catalog /Pages 2 0 R >>',
                      2: b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
                      3: page.format(5).encode(), 4: page.format(6).encode(),
                      5: b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(first) + first + b'\nendstream',
                      6: (b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(page2_stream) + page2_stream
                          + b'\nendstream'),
                      7: HELVETICA})


class PdfDamagedStreamTests(unittest.TestCase):
    """ingest:4 — a stream that does not decode completely makes its page partial, never silently short."""

    full = zlib.compress(page_content(PAGE2_LINES), 6)

    def test_truncated_stream_that_still_yields_text_is_partial(self):
        result = extract(flate_pdf(self.full[:91]), ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertIn(DAMAGED_NOTE, result.messages)
        self.assertEqual(page_texts(result)[1].strip(), 'Procedures performed today:')

    def test_every_truncation_point_is_reported(self):
        for level in (0, 1, 6, 9):
            whole = zlib.compress(page_content(PAGE2_LINES), level)
            for cut in range(1, len(whole)):  # a cut inside the trailing checksum is damage too
                with self.subTest(level=level, cut=cut):
                    result = in_process(flate_pdf(whole[:cut], level))
                    self.assertNotEqual(result.status, 'ok')
                    self.assertTrue(any(message.startswith('Page 2') for message in result.messages))

    def test_in_place_damage_is_reported(self):
        whole = self.full
        zeroed = whole[:90] + bytes(len(whole) - 90)
        self.assertEqual(len(zeroed), len(whole))
        intact = page_texts(in_process(flate_pdf(whole)))[1]
        for label, damaged in [('zero-filled tail', zeroed)] + [
                (f'flip at {k}', whole[:k] + bytes([whole[k] ^ 0x5A]) + whole[k + 1:]) for k in range(len(whole))]:
            with self.subTest(label):
                result = in_process(flate_pdf(damaged))
                # A flip that lands only in the padding bits after the last block changes nothing.
                if result.status == 'ok':
                    self.assertEqual(page_texts(result)[1], intact)

    def test_intact_streams_are_ok(self):
        for level in (0, 1, 6, 9):
            with self.subTest(level=level):
                result = extract(flate_pdf(zlib.compress(page_content(PAGE2_LINES), level)), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn('Retroflexion in the rectum performed', result.text)

    def test_damaged_object_stream_is_reported(self):
        self.assertEqual(extract(objstm_pdf(), ocr=None).status, 'ok')  # control: an intact object stream
        for cut in (4, 30):
            with self.subTest(cut=cut):
                result = extract(objstm_pdf(truncate=cut), ocr=None)
                self.assertNotEqual(result.status, 'ok')
                self.assertIn('The PDF is damaged: a compressed block of its objects could not be decoded completely, '
                              'so text may be missing or wrong.', result.messages)

    def test_forms_past_the_reading_limit_are_reported(self):
        data = one_page('q /Fx Do Q\n' * 5_100, resources='/XObject << /Fx 6 0 R >>', extra_objects={
            6: stream('BT /F1 9 Tf 72 700 Td (x) Tj ET', '/Type /XObject /Subtype /Form /BBox [0 0 612 792] '
                                                       '/Resources << /Font << /F1 4 0 R >> >>')})
        result = in_process(data)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.messages, ('Page 1 draws more form objects than the extractor reads; the rest of its '
                                           'text was not read.',))
        self.assertEqual(in_process(data.replace(b'q /Fx Do Q\n' * 5_100, b'q /Fx Do Q\n' * 50)).status, 'ok')

    def test_trailing_bytes_after_a_complete_stream_are_accepted(self):
        result = extract(flate_pdf(self.full + b'\r'), ocr=None)
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_content_array_entry_that_is_not_a_stream_is_reported(self):
        page = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                b'/Contents [5 0 R 6 0 R] >>')
        objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', 3: page,
                   4: HELVETICA, 5: stream(text_ops(REPORT_LINES))}
        result = extract(serialise(objects | {6: b'<< /Synthetic (not a content stream) >>'}), ocr=None)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.messages, ('Page 1 is damaged: part of its content could not be decoded, so its text '
                                           'may be incomplete or wrong.',))
        intact = extract(serialise(objects | {6: stream('BT /F1 9 Tf 72 500 Td (Second part.) Tj ET')}), ocr=None)
        self.assertEqual((intact.status, intact.messages), ('ok', ()))

    def test_damaged_form_xobject_is_reported(self):
        form = zlib.compress(page_content(PAGE2_LINES))[:80]
        data = one_page('q /Fx Do Q', resources='/XObject << /Fx 6 0 R >>', extra_objects={
            6: (b'<< /Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                b'/Filter /FlateDecode /Length %d >>\nstream\n' % len(form) + form + b'\nendstream')})
        result = extract(data, ocr=None)
        self.assertNotEqual(result.status, 'ok')
        self.assertIn('Page 1 is damaged: part of its content could not be decoded, so its text may be incomplete '
                      'or wrong.', result.messages)


def objstm_pdf(truncate: int = 0) -> bytes:
    """One page whose catalog, page tree, page and font sit in a Flate object stream, with an xref stream."""
    inner = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                 b'/Contents 5 0 R >>'),
             4: HELVETICA}
    header, bodies, offset = [], [], 0
    for number, body in inner.items():
        header.append(f'{number} {offset}')
        bodies.append(body + b' ')
        offset += len(body) + 1
    head = (' '.join(header) + ' ').encode()
    packed = zlib.compress(head + b''.join(bodies))
    packed = packed[:len(packed) - truncate]
    out = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = {5: len(out)}
    out += obj(5, text_stream(b'Colonoscopy to the cecum; a 7 mm polyp was removed with cold snare polypectomy.'))
    offsets[6] = len(out)
    out += obj(6, b'<< /Type /ObjStm /N 4 /First %d /Filter /FlateDecode /Length %d >>\nstream\n'
               % (len(head), len(packed)) + packed + b'\nendstream')
    offsets[7] = len(out)
    rows = bytes([0]) + (0).to_bytes(4, 'big') + (65535).to_bytes(2, 'big')
    rows += b''.join(bytes([2]) + (6).to_bytes(4, 'big') + index.to_bytes(2, 'big') for index in range(4))
    rows += b''.join(bytes([1]) + offsets[n].to_bytes(4, 'big') + (0).to_bytes(2, 'big') for n in (5, 6, 7))
    out += obj(7, b'<< /Type /XRef /Size 8 /W [1 4 2] /Root 1 0 R /Length %d >>\nstream\n' % len(rows) + rows
               + b'\nendstream')
    out += b'startxref\n%d\n%%%%EOF\n' % offsets[7]
    return bytes(out)


# --- ingest:8 — truncated inside an incremental update -----------------------------------------

def obj(number: int, body: bytes) -> bytes:
    return b'%d 0 obj\n' % number + body + b'\nendobj\n'


def text_stream(text: bytes) -> bytes:
    content = b'BT /F1 11 Tf 72 720 Td (' + text + b') Tj ET'
    return b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream'


def page_dict(contents: int) -> bytes:
    return (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> '
            b'/Contents %d 0 R >>' % contents)


def revision1(text: bytes) -> tuple[bytes, int]:
    data, offsets = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n', {}
    for number, body in ((1, b'<< /Type /Catalog /Pages 2 0 R >>'), (2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
                         (3, page_dict(4)), (4, text_stream(text)), (5, HELVETICA)):
        offsets[number] = len(data)
        data += obj(number, body)
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(b'%010d 00000 n \n' % offsets[n] for n in range(1, 6))
    data += b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % xref
    return data, xref


def add_page_update(base: bytes, previous_xref: int, text: bytes) -> bytes:
    data, offsets = base, {}
    for number, body in ((2, b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>'), (6, page_dict(7)),
                         (7, text_stream(text))):
        offsets[number] = len(data)
        data += obj(number, body)
    xref = len(data)
    data += (b'xref\n0 1\n0000000000 65535 f \n2 1\n%010d 00000 n \n6 2\n%010d 00000 n \n%010d 00000 n \n'
             % (offsets[2], offsets[6], offsets[7]))
    data += b'trailer\n<< /Size 8 /Root 1 0 R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n' % (previous_xref, xref)
    return data


def replace_content_update(base: bytes, previous_xref: int, text: bytes) -> bytes:
    offset = len(base)
    data = base + obj(4, text_stream(text))
    xref = len(data)
    data += b'xref\n0 1\n0000000000 65535 f \n4 1\n%010d 00000 n \n' % offset
    data += b'trailer\n<< /Size 6 /Root 1 0 R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n' % (previous_xref, xref)
    return data


UNFINISHED = ('The PDF is incomplete: it ends with data after its last end-of-file marker, such as an unfinished '
              'update. Upload the complete file.')
VISIT = b'Synthetic GI office visit: established patient seen for reflux follow-up today.'
PROCEDURE = b'Procedure today: colonoscopy to the cecum; 6 mm transverse polyp removed by cold snare.'


class PdfIncrementalTruncationTests(unittest.TestCase):
    """ingest:8 — a file cut inside its last update is not read as the earlier revision."""

    def setUp(self):
        self.rev1, self.xref1 = revision1(VISIT)
        self.full = add_page_update(self.rev1, self.xref1, PROCEDURE)

    def test_complete_file_reads_both_pages(self):
        result = extract(self.full, ocr=None)
        self.assertEqual((result.status, len(result.pages)), ('ok', 2))
        self.assertIn('cold snare', result.text)

    def test_cut_inside_the_update_fails(self):
        cases = {'40 bytes before the end': self.full[:-40],
                 "after the update's xref keyword": self.full[:self.full.rindex(b'xref\n0 1') + 4],
                 'inside the new content stream': self.full[:self.full.index(b'cold snare') + 4],
                 'half-way through the update': self.full[:len(self.rev1) + (len(self.full) - len(self.rev1)) // 2]}
        for label, data in cases.items():
            with self.subTest(label):
                result = extract(data, ocr=None)
                self.assertEqual((result.status, result.text, result.messages), ('failed', '', (UNFINISHED,)))

    def test_every_cut_point_inside_the_update_fails(self):
        # Keep at least one byte of the update; only the final line feed may go.
        for cut in range(len(self.rev1) + 1, len(self.full) - 1):
            with self.subTest(cut=cut):
                self.assertEqual(in_process(self.full[:cut]).status, 'failed')

    def test_reverted_correction_is_not_read_silently(self):
        old = b'Impression: colonoscopy with cold snare polypectomy of a 6 mm polyp performed today.'
        new = b'Impression: CORRECTED - colonoscopy cancelled before insertion; no polypectomy performed.'
        base, xref = revision1(old)
        edited = replace_content_update(base, xref, new)
        self.assertEqual(extract(edited, ocr=None).text.strip(), new.decode())
        self.assertEqual(extract(edited[:-30], ocr=None).messages, (UNFINISHED,))

    def test_end_marker_appended_after_a_cut_update_fails(self):
        cut = self.full[:self.full.rindex(b'startxref')]
        for appended in (b'%%EOF\n', b'\n%%EOF'):
            with self.subTest(appended=appended):
                self.assertEqual(extract(cut + appended, ocr=None).messages,
                                 ('The PDF is incomplete: its last revision has no cross-reference pointer '
                                  '(startxref), so only an earlier revision could be read. Upload the complete file.',))

    def test_trailing_whitespace_and_nul_padding_are_accepted(self):
        for tail in (b'', b'\r\n', b'\n\n', b'\x00' * 32, b' \t\x0c'):
            with self.subTest(tail=tail):
                result = extract(self.full + tail, ocr=None)
                self.assertEqual((result.status, len(result.pages)), ('ok', 2))

    def test_cut_exactly_at_the_earlier_revision_is_that_revision(self):
        result = extract(self.full[:len(self.rev1)], ocr=None)
        self.assertEqual((result.status, len(result.pages)), ('ok', 1))


# --- ingest:12 — optional content hidden by default ---------------------------------------------

SHOWN = 'Colonoscopy cancelled before sedation; patient will reschedule.'
HIDDEN = 'Colonoscopy was performed to the cecum; a 7 mm polyp was removed with cold snare.'
LAYER_NOTE = ('Page 1 has text in a layer that is hidden by default (optional content); that text was not '
              'extracted.')


def layered_pdf(default: str | None, *, hidden_text: bool = True, form: bool = False, ocmd: str = '',
                tr3: bool = False) -> bytes:
    """One page; HIDDEN sits in /OC /oc1 (marked content, or a form XObject carrying /OC)."""
    content = f'BT /F1 12 Tf 72 720 Td ({SHOWN}) Tj ET\n'
    if tr3:
        content += 'BT 3 Tr /F1 12 Tf 72 680 Td (Invisible OCR layer: biopsy of the antrum was taken.) Tj ET\n'
    if hidden_text and form:
        content += 'q /Fx Do Q\n'
    elif hidden_text:
        content += f'/OC /oc1 BDC\nBT /F1 12 Tf 72 700 Td ({HIDDEN}) Tj ET\nEMC\n'
    target = '7 0 R' if ocmd else '6 0 R'
    ocprops = f'/OCProperties << /OCGs [6 0 R] /D {default} >>' if default else ''
    extra = {6: b'<< /Type /OCG /Name (Superseded draft) >>'}
    if ocmd:
        extra[7] = f'<< /Type /OCMD /OCGs [6 0 R] {ocmd} >>'.encode()
    resources = f'/Properties << /oc1 {target} >>'
    if form:
        extra[8] = stream(f'BT /F1 12 Tf 72 700 Td ({HIDDEN}) Tj ET',
                          f'/Type /XObject /Subtype /Form /BBox [0 0 612 792] /OC {target} '
                          f'/Resources << /Font << /F1 4 0 R >> >>')
        resources += ' /XObject << /Fx 8 0 R >>'
    return one_page(content, catalog=ocprops, resources=resources, extra_objects=extra)


class PdfOptionalContentTests(unittest.TestCase):
    """ingest:12 — text in a layer that is off by default is not current documentation."""

    def test_layer_off_by_default_is_excluded_and_named(self):
        for default in ('<< /Order [6 0 R] /OFF [6 0 R] >>', '<< /BaseState /OFF /Order [6 0 R] >>'):
            with self.subTest(default=default):
                result = extract(layered_pdf(default), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (LAYER_NOTE,)))
                self.assertEqual(result.text.strip(), SHOWN)

    def test_form_xobject_in_a_hidden_layer_is_excluded(self):
        result = extract(layered_pdf('<< /OFF [6 0 R] >>', form=True), ocr=None)
        self.assertEqual((result.text.strip(), result.messages), (SHOWN, (LAYER_NOTE,)))

    def test_membership_dictionary_policies(self):
        cases = {'/P /AnyOn': False, '/P /AllOff': True, '/VE [/Not 6 0 R]': True, '/VE [/And 6 0 R]': False}
        for policy, shown in cases.items():
            with self.subTest(policy=policy):
                result = extract(layered_pdf('<< /OFF [6 0 R] >>', ocmd=policy), ocr=None)
                self.assertEqual(HIDDEN in result.text, shown)

    def test_layers_that_are_on_are_read(self):
        for default in ('<< /Order [6 0 R] /ON [6 0 R] >>', '<< /Order [6 0 R] >>', None):
            with self.subTest(default=default):
                result = extract(layered_pdf(default), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', ()))
                self.assertIn(HIDDEN, result.text)

    def test_invisible_ocr_text_is_still_read(self):
        result = extract(layered_pdf('<< /OFF [6 0 R] >>', tr3=True), ocr=None)
        self.assertIn('Invisible OCR layer: biopsy of the antrum was taken.', result.text)
        self.assertNotIn(HIDDEN, result.text)

    def test_annotation_in_a_hidden_layer_is_not_read(self):
        result = extract(freetext_pdf(annot_extra='/OC 9 0 R', catalog='/OCProperties << /OCGs [9 0 R] /D << '
                                      '/OFF [9 0 R] >> >>', extra_objects={9: b'<< /Type /OCG /Name (Draft) >>'}),
                         ocr=None)
        self.assertNotIn('polypectomy', result.text)
        self.assertEqual(result.messages, ('Page 1 has hidden form fields or annotations; their text was not '
                                           'extracted.',))


if __name__ == '__main__':
    unittest.main()
