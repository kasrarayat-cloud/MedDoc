"""ops/verify_passages.py on a small synthetic PDF made with reportlab: no CMS file is needed (CI has none)."""
import copy
import hashlib
import importlib.util
import io
import json
import logging
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.reference import passages

_SPEC = importlib.util.spec_from_file_location('cpt_verify_passages',
                                               Path(__file__).resolve().parents[1] / 'ops' / 'verify_passages.py')
verify = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify)

PAGES = [['SYNTHETIC REFERENCE DOCUMENT - NOT A CMS FILE', 'Notice: synthetic text for tests only.'],
         ['Rule 1. A synthetic rule that stays on', 'one page and ends here.',
          'Rule 2. A synthetic rule that runs on past'],
         ['the end of its page and ends here.', 'Rule 3. Left out on purpose.']]


def synthetic_pdf(pages=PAGES) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter, invariant=1)
    for lines in pages:
        for number, line in enumerate(lines):
            pdf.drawString(72, 720 - 16 * number, line)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def data_for(pdf: bytes) -> dict:
    return {
        'source': {'key': 'synthetic-passages', 'kind': 'cms-ncci-policy-manual', 'publisher': 'Synthetic',
                   'title': 'Synthetic test document', 'release': 'S1', 'url': 'https://example.invalid/s.pdf',
                   'sha256': hashlib.sha256(pdf).hexdigest(), 'retrieved_at': '2026-11-01T21:30:00Z',
                   'effective_start': '2026-01-01', 'effective_end': '2026-12-31',
                   'license_note': 'Notice in the file: "Notice: synthetic text for tests only." Synthetic.',
                   'scope_note': 'Rule 3 ("Rule 3. Left out") is not imported.'},
        'passages': [
            {'passage_key': 'rule-01', 'section': 'Synthetic, rule 1', 'page': '2', 'topic': 'ncci.endoscopy',
             'topic_value': '1', 'text': 'Rule 1. A synthetic rule that stays on one page and ends here.'},
            {'passage_key': 'rule-02', 'section': 'Synthetic, rule 2', 'page': '2-3', 'topic': 'ncci.endoscopy',
             'topic_value': '2',
             'text': 'Rule 2. A synthetic rule that runs on past the end of its page and ends here.'},
        ],
        'excluded': [{'topic': 'ncci.endoscopy', 'topic_value': '3', 'section': 'Synthetic, rule 3', 'page': '3',
                      'anchor': 'Rule 3. Left out on purpose.', 'reason': 'Left out to test the anchor check.'}],
    }


class VerifyPassagesTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        self.pdf_bytes = synthetic_pdf()
        self.pdf = self.tmp / 'synthetic.pdf'
        self.pdf.write_bytes(self.pdf_bytes)

    def write(self, data, name='data.json') -> Path:
        path = self.tmp / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
        return path

    def run_verify(self, *pairs) -> tuple[int, str]:
        out = io.StringIO()
        argv = [item for data, pdf in pairs for item in ('--data', str(data), '--pdf', str(pdf))]
        return verify.main(argv, out=out), out.getvalue()

    def changed(self, mutate) -> Path:
        data = copy.deepcopy(data_for(self.pdf_bytes))
        mutate(data)
        return self.write(data)

    def test_the_synthetic_data_file_is_one_the_importer_accepts(self):
        passages.parse_data(data_for(self.pdf_bytes), 'synthetic.json')

    def test_every_check_passes_and_prints_expected_against_measured(self):
        status, output = self.run_verify((self.write(data_for(self.pdf_bytes)), self.pdf))
        self.assertEqual(status, 0, output)
        sha = hashlib.sha256(self.pdf_bytes).hexdigest()
        for line in (f'  sha256    expected {sha} / measured {sha}', '  passages  expected 2 / verified 2',
                     '  excluded  expected 1 / located 1', '  quotes    expected 2 / located 2',
                     '1 data files: 1 passed, 0 failed, 0 could not be checked'):
            self.assertIn(line, output.splitlines())

    def test_each_kind_of_mismatch_fails(self):
        cases = {
            'an edited word': (lambda d: d['passages'][0].update(text='Rule 1. A synthetic rule that stay on one page '
                                                                         'and ends here.'),
                               'passage rule-01: not found on page 2'),
            'another page': (lambda d: d['passages'][0].update(page='3'), 'passage rule-01: not found on page 3'),
            'a range for one page': (lambda d: d['passages'][0].update(page='1-2'),
                                     'passage rule-01: found on a single page of 1-2'),
            'a range cut short': (lambda d: d['passages'][1].update(page='2'), 'passage rule-02: not found on page 2'),
            'a page past the end': (lambda d: d['passages'][0].update(page='4'),
                                    'is not a page or range of this 3-page'),
            'uncollapsed text': (lambda d: d['passages'][0].update(text='Rule 1.  A synthetic rule'),
                                 'not whitespace-collapsed'),
            'a missing anchor': (lambda d: d['excluded'][0].update(anchor='Rule 4. Absent.'),
                                 'anchor not found on page 3'),
            'a quote not in the file': (lambda d: d['source'].update(scope_note='"Rule 9" is absent.'),
                                        "quoted note text not in the PDF: 'Rule 9'"),
        }
        for label, (mutate, message) in cases.items():
            with self.subTest(label):
                status, output = self.run_verify((self.changed(mutate), self.pdf))
                self.assertEqual(status, 1, output)
                self.assertIn(message, output)
                self.assertIn('0 passed, 1 failed', output)

    def test_another_file_fails_on_its_sha256_and_nothing_else_is_checked(self):
        other = self.tmp / 'other.pdf'
        other.write_bytes(synthetic_pdf(PAGES[:2]))
        status, output = self.run_verify((self.write(data_for(self.pdf_bytes)), other))
        self.assertEqual(status, 1)
        self.assertIn('the PDF is not the file the data file names; nothing else was checked', output)
        self.assertNotIn('passages  expected', output)

    def test_one_failing_file_among_several_fails_the_run(self):
        good = self.write(data_for(self.pdf_bytes), 'good.json')
        empty = self.write(dict(data_for(self.pdf_bytes), passages=[]), 'empty.json')
        wrong = self.changed(lambda d: d['passages'][1].update(text='Rule 2. Not in the file.'))
        status, output = self.run_verify((good, self.pdf), (empty, self.pdf), (wrong, self.pdf))
        self.assertEqual(status, 1)
        self.assertIn('3 data files: 2 passed, 1 failed, 0 could not be checked', output)

    def test_what_cannot_be_checked_exits_2(self):
        not_a_pdf = self.tmp / 'not.pdf'
        not_a_pdf.write_bytes(b'plain synthetic bytes')
        named_bytes = dict(data_for(self.pdf_bytes)['source'],
                           sha256=hashlib.sha256(not_a_pdf.read_bytes()).hexdigest())
        cases = {
            'missing pdf': ((self.write(data_for(self.pdf_bytes), 'a.json'), self.tmp / 'absent.pdf'),
                            'cannot read the PDF'),
            'invalid json': ((self.write('{"source": ', 'b.json'), self.pdf), 'cannot read the data file'),
            'wrong layout': ((self.write({'source': {}, 'passages': 'x', 'excluded': []}, 'c.json'), self.pdf),
                             'cannot read the data file'),
            'not a pdf': ((self.write(dict(data_for(self.pdf_bytes), source=named_bytes), 'd.json'), not_a_pdf),
                          'cannot check: the PDF could not be read'),
        }
        pypdf_log = logging.getLogger('pypdf')  # its warnings about the bytes that are not a PDF are expected here
        self.addCleanup(pypdf_log.setLevel, pypdf_log.level)
        pypdf_log.setLevel(logging.CRITICAL)
        for label, (pair, message) in cases.items():
            with self.subTest(label):
                status, output = self.run_verify(pair)
                self.assertEqual(status, 2, output)
                self.assertIn(message, output)
                self.assertIn('0 passed, 0 failed, 1 could not be checked', output)
        with mock.patch.dict(sys.modules, {'pypdf': None}):
            status, output = self.run_verify((self.write(data_for(self.pdf_bytes)), self.pdf))
        self.assertEqual(status, 2)
        self.assertIn('pypdf is not available', output)

    def test_data_and_pdf_must_come_in_pairs(self):
        out = io.StringIO()
        status = verify.main(['--data', 'a.json', '--data', 'b.json', '--pdf', 'a.pdf'], out=out)
        self.assertEqual(status, 2)
        self.assertIn('2 --data but 1 --pdf', out.getvalue())

    def test_the_script_and_the_importer_collapse_whitespace_alike(self):
        sample = ' a\tb\n\nc d e \r\n f　g  '
        self.assertEqual(verify.collapse(sample), passages.collapse(sample))
        self.assertEqual(verify.collapse(sample), 'a b c d e f g')
