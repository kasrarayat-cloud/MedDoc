"""The verification samples (ops/verification/samples) are what make_samples.py writes, and hold to the contracts the tools
verify: the customer samples to customer-contract.json, every quoted offset to the document text. The four customer
report samples are studio/reports.py's own bytes of make_samples' report snapshots, written and pinned by the Django
suite (tests/test_cux_r2_reports.py SampleReportTests; refutation round 2, L3-1), never by a grammar of the generator's
own. The walk's node tests and the download and scanner tests all read these files, so a stale or self-contradictory
sample would make every one of them prove the wrong thing.

    cd cpt-studio && python3 -B -m unittest discover -s ops/verification -p 'test_samples.py' -v
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / 'samples'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module while the class is built
    spec.loader.exec_module(module)
    return module


make = load('cpt_make_samples', SAMPLES / 'make_samples.py')
scan = load('cpt_samples_scan_customer', HERE.parent / 'scan_customer.py')


def sample_json(name):
    return json.loads((SAMPLES / name).read_bytes().decode('utf-8'))


class SampleTests(unittest.TestCase):
    def test_the_committed_samples_are_the_generator_s(self):
        stale = [name for name, content in make.outputs().items() if (SAMPLES / name).read_bytes() != content.encode('utf-8')]
        self.assertEqual(stale, [], 'run python3 -B ops/verification/samples/make_samples.py and commit what it writes')
        self.assertEqual(make.main(['--check']), 0)
        # the report samples are the server renderer's (tests/test_cux_r2_reports.py), never this generator's text
        self.assertEqual(set(make.REPORT_FILES) & set(make.outputs()), set())
        for name in make.REPORT_FILES:
            self.assertTrue((SAMPLES / name).is_file(), name)
        snapshots = sample_json('customer-report-snapshots.json')
        self.assertEqual(sorted(snapshots), ['approved', 'draft', 'generated'])
        self.assertTrue(sample_json('customer-report-snapshots.json')['approved']['agent_review'])

    def test_the_customer_samples_hold_to_the_customer_contract(self):
        for name, schema in (('customer-encounter.json', 'encounter'), ('customer-encounter-details.json', 'encounter'),
                             ('customer-session.json', 'session')):
            with self.subTest(name=name):
                self.assertEqual(scan.shape_problems(sample_json(name), scan.CONTRACT[schema]), [])

    def test_every_offset_quotes_the_document_and_the_document_is_marked_synthetic(self):
        text = (SAMPLES / 'document.txt').read_bytes().decode('utf-8')
        self.assertTrue(text.startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL'))
        op = sample_json('operator-encounter.json')
        self.assertEqual(op['revision']['text'], text)
        spans = [s for p in op['assessment']['proposals'] for s in p['evidence']]
        spans += [s for p in op['assessment']['proposals'] for s in (p['support'] or {}).get('source', [])]
        for enc in (sample_json('customer-encounter.json'), sample_json('customer-encounter-details.json')):
            self.assertEqual(enc['document']['text'], text)
            spans += [q for code in enc['codes'] for q in code['why']['quotes']]
            spans += [enc['service_date']['document_quote']]
        for span in spans:
            self.assertEqual(text[span['start']:span['end']], span['text'])

    def test_the_customer_samples_carry_nothing_a_customer_must_not_see(self):
        op = sample_json('operator-encounter.json')
        ctx = scan.scan_context(op['revision']['text'], scan.deny_values_from(op, sample_json('operator-trace.json')))
        for name in ('customer-encounter.json', 'customer-encounter-details.json', 'customer-session.json'):
            self.assertEqual(scan.scan_json(sample_json(name), ctx), [], name)
        for name in ('customer-report-approved.txt', 'customer-report-draft.txt', 'customer-report-approved.csv', 'customer-report-draft.csv',
                     'customer-page.html', 'customer-page-details.html'):
            text = (SAMPLES / name).read_bytes().decode('utf-8')
            self.assertEqual(scan.scan_file(text, ctx, name, 'csv' if name.endswith('.csv') else 'txt'), [], name)
        # and the operator view, served to a customer, would not pass: the scan is not vacuous over these samples
        self.assertGreater(len(scan.scan_json(op, ctx)), 20)


if __name__ == '__main__':
    unittest.main()
