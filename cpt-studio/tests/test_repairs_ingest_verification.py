"""Positive control for the ingestion repairs: the ten synthetic verification documents
(ops/verification) still extract with the status and method their manifest expects.

The generator renders each delivery in memory; nothing is written to the
repository. This host may have no OCR, so the scanned delivery is read with
the executable OCR stand-ins from tests.test_ingest (the plumbing is real).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

from studio.ingest import extract_document, extract_paste
from tests.test_ingest import FakeOcr

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION = ROOT / 'ops' / 'verification'
MEDIA = {'pdf': 'application/pdf', 'scanned-pdf': 'application/pdf', 'txt': 'text/plain',
         'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def _generator():
    spec = importlib.util.spec_from_file_location('cpt_verification_generate_ingest', VERIFICATION / 'generate.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


class VerificationDocumentExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generate = _generator()
        cls.manifest = json.loads((VERIFICATION / 'manifest.json').read_text(encoding='utf-8'))

    def deliver(self, doc: dict) -> tuple[bytes, str]:
        data, text = self.generate.read_source(VERIFICATION, doc)
        fmt = doc['delivery']['format']
        return self.generate.RENDERERS[fmt](data, text, f'{doc["id"]} {doc["title"]} (synthetic)'), text

    def test_every_document_extracts_as_its_manifest_expects(self):
        self.assertEqual(len(self.manifest['documents']), 10)
        with FakeOcr() as fake:
            for doc in self.manifest['documents']:
                with self.subTest(doc['id']):
                    rendered, source = self.deliver(doc)
                    fmt = doc['delivery']['format']
                    expected = doc['expected_extraction']
                    if fmt == 'paste':
                        result = extract_paste(rendered.decode('utf-8'))
                    else:
                        result = extract_document(rendered, doc['delivery']['file'], MEDIA[fmt],
                                                  ocr=fake.tools if fmt == 'scanned-pdf' else None)
                    self.assertIn(result.status, expected['status_in'], result.messages)
                    self.assertIn(result.method, expected['method_in'])
                    if expected.get('ocr_pages_nonempty'):
                        self.assertTrue(result.ocr_pages)
                    if fmt != 'scanned-pdf':
                        self.assertEqual(result.messages, ())
                    match = expected.get('text_matches_source')
                    if match == 'exact':
                        self.assertEqual(result.text.rstrip(), source.rstrip())
                    elif match == 'whitespace':
                        self.assertEqual(normalized(result.text), normalized(source))


if __name__ == '__main__':
    unittest.main()
