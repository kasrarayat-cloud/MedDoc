"""The development corpus read from other formats (tests/corpus/services): every document, written as a digital PDF
whose lines wrap where a PDF writer wraps them, documents the same services, acts, lesions, conflicts and attributions
as its text, apart from the differences recorded, each with its reason, in format_known_differences.json. A sample is
also read from a scanned copy with real OCR wherever tesseract and pdftoppm are installed (CI installs them, and so
does the image). The expected readings are the text's own: nothing here is written into the reader.
"""
import json
from datetime import date
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.ingest import DETECT, ocr_available
from studio.ingest.extract import extract_document
from tests.support import docgen

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'services'
KNOWN = CORPUS / 'format_known_differences.json'
PDF_LINES_PER_PAGE = 44
SCAN_LINES_PER_PAGE = 34
# Documents whose scan is read with real OCR here: an EGD whose biopsy list carries a negation, an incomplete
# colonoscopy (poor preparation), a complete screening colonoscopy "not discontinued", and an ERCP with a stent and a
# brushing: negation, completed versus discontinued, and acts and lesions across wrapped lines.
SCAN_SAMPLE = ('svc-08-egd-multisite-biopsy-list-negation', 'svc-22-colo-incomplete-poor-prep',
               'svc-24-colo-screening-complete-not-discontinued', 'svc-33-ercp-biliary-stent-brushing')


def reading(text: str) -> set:
    """What the documented-service reader reads in ``text``, as comparable items."""
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    inv = services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)
    items = {('service_date', str(day))}
    for s in inv.services:
        items.add(('service', s.family, s.status, s.completion, s.included_in or ''))
        for a in s.acts:
            lesion = next((l for l in s.lesions if l.id == a.lesion), None)
            items.add(('act', s.family, a.kind, a.status, a.role, lesion.anatomy if lesion else '',
                       ','.join(sorted(a.anatomy))))
    for c in inv.conflicts:
        service = inv.service(c.service)
        items.add(('conflict', service.family if service else '', c.subject))
    items |= {('attribution', a.role) for a in inv.attributions}
    return items


def pages(text: str, width: int, per_page: int) -> list[str]:
    """The text's wrapped lines on pages of ``per_page`` lines; a page holding only blank lines is never written (it
    would have no text layer, which is a different test)."""
    lines = docgen._wrapped(text.rstrip('\n'), width)
    chunks = ['\n'.join(lines[i:i + per_page]) for i in range(0, len(lines), per_page)]
    return [chunk for chunk in chunks if chunk.strip()]


def diff(base: set, got: set) -> dict:
    return {'missing': sorted('|'.join(map(str, x)) for x in base - got),
            'extra': sorted('|'.join(map(str, x)) for x in got - base)}


def recorded(fmt: str, name: str) -> dict:
    entry = json.loads(KNOWN.read_text(encoding='utf-8'))[fmt].get(name, {})
    return {'missing': sorted(entry.get('missing', [])), 'extra': sorted(entry.get('extra', []))}


class DigitalPdfCorpusTests(SimpleTestCase):
    def test_every_document_reads_the_same_from_a_digital_pdf(self):
        documents = sorted((CORPUS / 'documents').glob('svc-*.txt'))
        self.assertEqual(len(documents), 43)
        for path in documents:
            with self.subTest(path.stem):
                text = path.read_text(encoding='utf-8')
                data = docgen.make_pdf(pages(text, docgen.PDF_LINE_CHARS, PDF_LINES_PER_PAGE))
                result = extract_document(data, 'corpus.pdf', 'application/pdf')
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertEqual(diff(reading(text), reading(result.text)), recorded('pdf', path.stem),
                                 'a PDF reading changed: a new difference is a regression; a recorded one that '
                                 'disappeared must be removed from format_known_differences.json')

    def test_every_recorded_difference_has_its_reason(self):
        known = json.loads(KNOWN.read_text(encoding='utf-8'))
        for fmt in ('pdf', 'scan'):
            for name, entry in known[fmt].items():
                self.assertTrue((CORPUS / 'documents' / f'{name}.txt').exists(), name)
                self.assertTrue(entry.get('reason', '').strip(), f'{fmt} {name}')


@skipUnless(ocr_available(), 'tesseract and pdftoppm are not installed on this host')
class ScannedCorpusSampleTests(SimpleTestCase):
    def test_a_sample_reads_the_same_from_a_scan(self):
        for name in SCAN_SAMPLE:
            with self.subTest(name):
                text = (CORPUS / 'documents' / f'{name}.txt').read_text(encoding='utf-8')
                data = docgen.make_scanned_pdf(pages(text, docgen.SCAN_LINE_CHARS, SCAN_LINES_PER_PAGE))
                result = extract_document(data, 'corpus-scan.pdf', 'application/pdf', ocr=DETECT)
                self.assertEqual((result.status, result.method), ('ok', 'pdf-ocr'), result.messages)
                self.assertEqual(diff(reading(text), reading(result.text)), recorded('scan', name))
