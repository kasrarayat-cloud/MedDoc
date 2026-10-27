"""The documented-service inventory reads the same services from a Word document and a digital PDF as from the text.

Scanned (OCR) input is exercised in the image, where tesseract is installed (ARCHITECTURE 9); here an image-only PDF
without OCR tools must say its text was not read, never yield an inventory from nothing.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.ingest.extract import extract_document
from tests.support import docgen

DAY = date(2026, 10, 14)

LINES = [
    'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE',
    'Colonoscopy Report',
    'Date of service: 2026-10-14',
    'The colonoscope was advanced to the cecum and the examination was completed without interruption.',
    'A 7 mm sessile polyp in the hepatic flexure was removed with a cold snare.',
    'A separate 12 mm flat lesion in the rectum was sampled with cold biopsy forceps and was not removed.',
    'No tattoo or other submucosal injection was performed.',
]


def summary(text):
    facts = gi_context.extract_context(text)
    inv = services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=facts)
    out = set()
    for s in inv.services:
        out.add((s.family, s.status, s.completion))
        for a in s.acts:
            if a.status == 'performed':
                lesion = next((l for l in s.lesions if l.id == a.lesion), None)
                out.add((s.family, a.kind, lesion.anatomy if lesion else ''))
    return out


class FormatTests(SimpleTestCase):
    def setUp(self):
        self.expected = summary('\n'.join(LINES) + '\n')
        self.assertIn(('gi.colonoscopy', 'performed', 'complete'), self.expected)
        self.assertIn(('gi.colonoscopy', 'biopsy', 'rectum'), self.expected)
        self.assertIn(('gi.colonoscopy', 'snare', 'hepatic flexure'), self.expected)

    def test_word(self):
        data = docgen.make_docx(LINES)
        result = extract_document(data, 'synthetic.docx',
                                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertEqual(summary(result.text), self.expected)

    def test_digital_pdf(self):
        data = docgen.make_pdf(['\n'.join(LINES)])
        result = extract_document(data, 'synthetic.pdf', 'application/pdf')
        self.assertIn(result.status, ('ok', 'partial'), result.messages)
        self.assertEqual(summary(result.text), self.expected)

    def test_a_scan_without_ocr_is_not_read_into_services(self):
        data = docgen.make_scanned_pdf(['\n'.join(LINES)])
        result = extract_document(data, 'synthetic-scan.pdf', 'application/pdf', ocr=None)
        self.assertNotEqual(result.status, 'ok')
        self.assertTrue(result.messages)
        self.assertEqual({item for item in summary(result.text) if item[1] in ('performed', 'incomplete')}, set())
