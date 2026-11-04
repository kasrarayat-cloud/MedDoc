"""Unit tests for the customer-report path of ops/verify_downloads.py (cpt-studio-customer-report@1).

Over the synthetic samples ops/verification/samples/make_samples.py writes to the contract (CORE-UX-DESIGN.md section 5):
each check passes on the samples and fails on the defect it exists for. The comparison source is the OPERATOR view of
the encounter (operator-encounter.json), never the customer API the walk's browser read. Offline; no server.

    cd cpt-studio && python3 -B -m unittest discover -s ops -p 'test_customer_verify_downloads.py' -v
"""
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_customer_verify_downloads', HERE / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_customer_verify_downloads'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

SAMPLES = HERE / 'verification' / 'samples'
AGENT = 'CPT Studio review agent (automated agent)'


def sample(name: str) -> str:
    return (SAMPLES / name).read_bytes().decode('utf-8')  # as downloaded: a CSV keeps its CR LF


def operator() -> dict:
    return json.loads(sample('operator-encounter.json'))


def trace() -> dict:
    return json.loads(sample('operator-trace.json'))


def failed(results) -> list:
    return sorted({r.check for r in results if r.status == 'fail'})


def txt(kind: str, text: str | None = None, api: dict | None = None):
    return vd.check_customer_txt('d', f'{kind}.txt', sample(f'customer-report-{kind}.txt') if text is None else text, kind,
                                 operator() if api is None else api, trace(), AGENT)


def csv(kind: str, text: str | None = None, api: dict | None = None):
    return vd.check_customer_csv('d', f'{kind}.csv', sample(f'customer-report-{kind}.csv') if text is None else text, kind,
                                 operator() if api is None else api, trace())


class SampleTests(unittest.TestCase):
    def test_each_sample_report_passes_every_check_against_the_operator_view(self):
        for kind in ('approved', 'draft'):
            for check, results in (('txt', txt(kind)), ('csv', csv(kind))):
                with self.subTest(kind=kind, fmt=check):
                    self.assertEqual([(r.check, r.status, r.detail) for r in results if r.status != 'pass'], [])
                    names = {r.check for r in results}
                    for owed in ('format', 'scan.file'):
                        self.assertIn(owed, names)
        self.assertIn('items.approver', {r.check for r in txt('approved')})
        self.assertIn('csv.items.approver', {r.check for r in csv('approved')})
        self.assertIn('items.status', {r.check for r in txt('draft')})

    def test_the_truth_is_the_operator_view_s_approved_items_in_the_contract_s_order(self):
        truth = vd.customer_truth(operator(), 'approved')
        self.assertEqual([(t['number'], t['code'], t['units'], t['modifiers'], t['approver_kind']) for t in truth],
                         [(1, '45380', '1', (), 'agent'), (2, '45385', '1', ('XS',), 'agent')])
        self.assertEqual([t['code'] for t in vd.customer_truth(operator(), 'draft')], ['45380', '45385'])
        undecided = operator()
        undecided['assessment']['proposals'][0]['decision'] = None
        self.assertEqual([t['code'] for t in vd.customer_truth(undecided, 'approved')], ['45385'])
        self.assertEqual(vd.customer_truth(undecided, 'draft')[0]['status'], 'ready')


class ApprovedTxtTests(unittest.TestCase):
    def assert_fails(self, mutate, wanted, kind='approved'):
        text = sample(f'customer-report-{kind}.txt')
        mutated = mutate(text)
        self.assertNotEqual(mutated, text, 'the mutation did not apply')
        got = failed(txt(kind, mutated))
        for check in wanted:
            self.assertIn(check, got, f'{check} not failed; failed {got}')
        return got

    def test_an_item_that_is_not_an_approved_code_fails(self):
        line = '  3. 45378 · units 1\n     Approved by CPT Studio review agent (automated agent) at 2026-11-03T22:05:00Z\n'
        self.assert_fails(lambda t: t.replace('\nLIMITATIONS', f'{line}\nLIMITATIONS'), ['items.items'])

    def test_a_missing_approved_code_fails(self):
        self.assert_fails(lambda t: t[:t.index('  2. 45385')] + '\n' + t[t.index('LIMITATIONS'):], ['items.items'])

    def test_units_and_modifiers_are_the_persisted_ones(self):
        self.assert_fails(lambda t: t.replace('  1. 45380 · units 1', '  1. 45380 · units 2'), ['items.units'])
        self.assert_fails(lambda t: t.replace(' · modifier XS', ''), ['items.modifiers'])
        self.assert_fails(lambda t: t.replace(' · modifier XS', ' · modifiers 59, XS'), ['items.modifiers'])
        self.assert_fails(lambda t: t.replace('  1. 45380 · units 1', '  1. 45380 · units 1 · modifier 59'), ['items.modifiers'])

    def test_the_approver_its_time_and_the_agent_label_are_the_persisted_decision_s(self):
        self.assert_fails(lambda t: t.replace('Approved by CPT Studio review agent (automated agent) at 2026-11-03T22:05:00Z',
                                              'Approved by Dr Synthetic at 2026-11-03T22:05:00Z'), ['items.approver'])
        self.assert_fails(lambda t: t.replace('at 2026-11-03T22:05:30Z', 'at 2026-11-03T23:05:30Z'), ['items.approver'])
        self.assert_fails(lambda t: t.replace('     Agent-executed synthetic review — not clinical approval\n', '', 1), ['items.approver'])

    def test_every_quotation_is_exact_on_its_page_and_a_passage_held_as_support(self):
        self.assert_fails(lambda t: t.replace('characters 256–329', 'characters 257–330'), ['items.evidence.exact', 'items.evidence.support'])
        self.assert_fails(lambda t: t.replace('[page 1, characters 256–329]', '[page 2, characters 256–329]'), ['items.evidence.exact'])
        cecum = operator()['routing']['families'][0]['mentions'][0]['span']
        self.assert_fails(lambda t: t.replace('Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." [page 1, characters 256–329]',
                                              f'Quote: "{cecum["text"]}" [page 1, characters {cecum["start"]}–{cecum["end"]}]'), ['items.evidence.support'])
        self.assert_fails(lambda t: t.replace(' [page 1, characters 256–329]', ' [page 1]'), ['items.evidence.exact'])
        got = self.assert_fails(lambda t: t.replace('     Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." [page 1, characters 256–329]\n', ''),
                                ['items.quoted'])
        self.assertNotIn('items.evidence.exact', got)

    def test_the_evidence_cpt_studio_recorded_for_the_matched_act_is_support_while_it_is_performed_or_incomplete(self):
        # the wiring report's item 1 (2026-11-04): customer reports quote CPT Studio's own evidence for the matched act
        # first (customer_api._quotes); only for an act the code's support names, stored performed or incomplete
        api = operator()
        text = api['revision']['text']
        passage = 'Procedure: Colonoscopy with polyp removal.'
        start = text.index(passage)
        span = {'text': passage, 'start': start, 'end': start + len(passage)}
        api['assessment']['services'] = {'services': [{'id': 'S1', 'family': 'colonoscopy', 'acts': [
            {'id': 'act-1', 'kind': 'removal', 'status': 'performed', 'evidence': [span]}]}]}
        line = '     Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." [page 1, characters 256–329]\n'
        report = sample('customer-report-approved.txt')
        self.assertEqual(report.count(line), 1)
        report = report.replace(line, f'     Quote: "{passage}" [page 1, characters {span["start"]}–{span["end"]}]\n' + line)
        self.assertEqual(failed(txt('approved', report, api=api)), [])
        self.assertEqual([s['start'] for s in vd.allowed_passages(api['assessment']['proposals'][0], text, vd.act_index(api))[0]],
                         [256, start, 256])  # support.source, the act's own evidence, the supporting passage
        for status, outcome in (('incomplete', []), ('not_performed', ['items.evidence.support']),
                                ('planned', ['items.evidence.support']), (None, ['items.evidence.support'])):
            with self.subTest(status=status):
                other = json.loads(json.dumps(api))
                other['assessment']['services']['services'][0]['acts'][0]['status'] = status
                self.assertEqual(failed(txt('approved', report, api=other)), outcome)
        self.assertEqual(failed(txt('approved', report)), ['items.evidence.support'])  # no recorded reading
        other = json.loads(json.dumps(api))
        other['assessment']['services']['services'][0]['acts'][0]['id'] = 'act-2'  # an act the support does not name
        self.assertEqual(failed(txt('approved', report, api=other)), ['items.evidence.support'])

    def test_a_quotation_found_unrelated_is_never_one(self):
        api = operator()
        support = api['assessment']['proposals'][0]['support']
        support.update(unrelated=[0], supporting=[], source=[])
        self.assertIn('items.evidence.support', failed(txt('approved', api=api)))

    def test_banner_format_headline_and_header_fields(self):
        self.assert_fails(lambda t: t.rstrip('\n').rsplit('\n', 1)[0] + '\n', ['marker.synthetic'])
        self.assert_fails(lambda t: t.replace('cpt-studio-customer-report@1', 'cpt-studio-report@4'), ['format'])
        self.assert_fails(lambda t: t.replace('CPT STUDIO — APPROVED CODES', 'CPT STUDIO — SUGGESTED CODES — NOT APPROVED'), ['headline'])
        self.assert_fails(lambda t: t.replace('Encounter: Synthetic colonoscopy (two lesions)', 'Encounter: Another encounter'), ['header.encounter'])
        self.assert_fails(lambda t: t.replace('Date of service: 2026-11-03', 'Date of service: 2026-11-02'), ['header.date_of_service'])
        self.assert_fails(lambda t: t.replace('Generated by: CPT Studio review agent (automated agent)\n', ''), ['header.generated'])
        self.assertEqual({r.check: r.status for r in txt('approved', sample('customer-report-approved.txt').replace('Generated at: 2026-11-03T22:10:00Z', 'Generated at: today'))}['header.generated_iso'], 'warn')
        self.assert_fails(lambda t: t.replace('Encounter:', '  7. 45378 · units 1\nEncounter:'), ['items.outside_section'])

    def test_another_layout_of_the_same_content_reads_the_same_and_its_defects_still_fail(self):
        # the format fixes what a report says, not how each line is laid out: headings in any case, ")" numbering,
        # "1 unit", "Units:" and "Modifier:" fields, "Approved by:" with a space-separated UTC time, bullet quotations with
        # "(p. N, chars S-E)", bullet limitations
        text = sample('customer-report-approved.txt')
        for old, new in (('\nAPPROVED CODES\n', '\nApproved codes\n'), ('  1. 45380 · units 1', '  1) 45380 — 1 unit'),
                         ('  2. 45385 · units 1 · modifier XS', '  2) 45385 — Units: 1 — Modifier: XS'),
                         ('Approved by CPT Studio review agent (automated agent) at 2026-11-03T22:05:00Z', 'Approved by: CPT Studio review agent (automated agent) on 2026-11-03 22:05:00 UTC'),
                         ('Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." [page 1, characters 256–329]',
                          '- "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." (p. 1, chars 256-329)'),
                         ('\nLIMITATIONS\n', '\nLimitations\n'), ('  - CPT descriptions', '  • CPT descriptions')):
            self.assertEqual(text.count(old), 1, old)
            text = text.replace(old, new)
        self.assertEqual([(r.check, r.detail) for r in txt('approved', text) if r.status not in ('pass',)], [])
        parsed = vd.parse_customer_txt(text)
        self.assertEqual([(i.code, i.units, i.modifiers, i.approver_kind) for i in parsed['items']], [('45380', '1', (), 'agent'), ('45385', '1', ('XS',), 'agent')])
        self.assertEqual(len(parsed['limitations']), 3)
        self.assertIn('items.units', failed(txt('approved', text.replace('  1) 45380 — 1 unit', '  1) 45380 — 2 units'))))
        self.assertIn('items.modifiers', failed(txt('approved', text.replace('Modifier: XS', 'Modifier: 59'))))
        self.assertIn('items.evidence.exact', failed(txt('approved', text.replace('chars 256-329', 'chars 256-330'))))
        self.assertIn('items.approver', failed(txt('approved', text.replace('on 2026-11-03 22:05:00 UTC', 'on 2026-11-03 22:06:00 UTC'))))
        # numbering and order: an approved export in another order is a warning, a gap in its numbering a failure
        swapped = text[:text.index('  1) 45380')] + text[text.index('  2) 45385'):text.index('\nLimitations')] + text[text.index('  1) 45380'):text.index('  2) 45385')] + text[text.index('\nLimitations'):]
        swapped = swapped.replace('  2) 45385', '  1) 45385', 1).replace('  1) 45380', '  2) 45380', 1)
        statuses = {r.check: r.status for r in txt('approved', swapped)}
        self.assertEqual((statuses['items.items'], statuses['items.order']), ('pass', 'warn'))
        self.assertIn('items.items', failed(txt('approved', text.replace('  2) 45385', '  3) 45385'))))

    def test_the_negative_scan_reads_every_line(self):
        api = operator()
        for line in ('Read by Astra (OpenAI, gpt-6-astra).', f'Request sha256: {api["provider_runs"][0]["request_sha256"]}',
                     'Tokens: 2,100 in, 420 out', 'Rule evidence.exact passed', f'Run {api["provider_runs"][1]["id"]}'):
            with self.subTest(line=line):
                self.assert_fails(lambda t, line=line: t.replace('\nLIMITATIONS', f'\n{line}\n\nLIMITATIONS'), ['scan.file'])

    def test_a_passage_that_spans_lines_is_read_whole(self):
        api = operator()
        passage = 'COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.\nCOL-2: a 9 mm sigmoid colon polyp was removed with a cold snare.'
        start = api['revision']['text'].index(passage)
        api['assessment']['proposals'][0]['evidence'] = [{'context_index': 0, 'start': start, 'end': start + len(passage), 'text': passage, 'exact': True, 'page': 1}]
        api['assessment']['proposals'][0]['support'] = {}
        text = sample('customer-report-approved.txt').replace(
            'Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." [page 1, characters 256–329]',
            'Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.\n       COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare." '
            f'[page 1, characters {start}–{start + len(passage)}]')
        results = txt('approved', text, api)
        self.assertEqual(failed(results), [])
        quote = vd.parse_customer_txt(text)['items'][0].quotes[0]
        self.assertEqual((quote['text'], quote['start'], quote['end'], quote['page']), (passage, start, start + len(passage), 1))

    def test_a_code_not_approved_named_outside_the_items_is_a_warning(self):
        api = operator()
        api['assessment']['proposals'][0]['decision'] = None
        text = sample('customer-report-approved.txt')
        text = text[:text.index('  1. 45380')] + '  1. 45385' + text[text.index('  2. 45385') + len('  2. 45385'):]
        text = text.replace('\nLIMITATIONS', '\n  Note: 45380 is not approved.\n\nLIMITATIONS')
        results = txt('approved', text, api)
        self.assertEqual({r.check: r.status for r in results}['approved.only'], 'warn')


class DraftTxtTests(unittest.TestCase):
    def test_the_draft_lists_every_suggested_code_with_its_status_and_only_decided_modifiers(self):
        api = operator()
        api['assessment']['proposals'][1]['decision'] = None  # 45385 undecided: Ready for review, no modifier
        text = sample('customer-report-draft.txt').replace('  2. 45385 · units 1 · modifier XS · Approved', '  2. 45385 · units 1 · Ready for review')
        self.assertEqual(failed(txt('draft', text, api)), [])
        self.assertIn('items.modifiers', failed(txt('draft', text.replace('  2. 45385 · units 1 · Ready for review', '  2. 45385 · units 1 · modifier XS · Ready for review'), api)))
        self.assertIn('items.status', failed(txt('draft', text.replace('· Ready for review', '· Approved'), api)))
        self.assertIn('items.items', failed(txt('draft', text[:text.index('  2. 45385')] + '\n' + text[text.index('LIMITATIONS'):], api)))

    def test_a_draft_never_reads_as_the_approved_export(self):
        text = sample('customer-report-draft.txt')
        self.assertIn('headline', failed(txt('draft', text.replace('CPT STUDIO — SUGGESTED CODES — NOT APPROVED', 'CPT STUDIO — APPROVED CODES'))))
        self.assertIn('codes.section', failed(txt('draft', text.replace('\nSUGGESTED CODES — NOT APPROVED\n', '\nAPPROVED CODES\n'))))
        self.assertIn('items.evidence.support', failed(txt('draft', text.replace('Quote: "COL-1: a 4 mm', 'Quote: "COL-1: a 5 mm'))))


class CsvTests(unittest.TestCase):
    def test_columns_format_constants_and_neutralised_cells(self):
        text = sample('customer-report-approved.csv')
        self.assertIn('csv.columns', failed(csv('approved', text.replace('evidence_start', 'evidence_begin'))))
        self.assertIn('format', failed(csv('approved', text.replace('cpt-studio-customer-report@1,Synthetic', 'cpt-studio-report@4,Synthetic', 1))))
        self.assertIn('csv.constants', failed(csv('approved', text.replace(',2026-11-03,1,45380', ',2026-11-02,1,45380'))))
        self.assertIn('csv.neutralised', failed(csv('approved', text.replace('The colonoscopy documents removal of the 4 mm', '=HYPERLINK("x")'))))
        self.assertEqual({r.check: r.status for r in csv('approved', '\r\n'.join(text.splitlines()[1:-1]) + '\r\n')}['csv.synthetic_marker'], 'warn')

    def test_the_rows_are_the_approved_items_with_their_units_modifiers_approver_and_evidence(self):
        text = sample('customer-report-approved.csv')
        rows = text.split('\r\n')
        extra = rows[2].replace(',1,45380,', ',3,45378,')
        self.assertIn('csv.items.items', failed(csv('approved', text.replace(rows[2], rows[2] + '\r\n' + extra))))
        self.assertIn('csv.items.units', failed(csv('approved', text.replace(',1,45380,1,', ',1,45380,2,'))))
        self.assertIn('csv.items.modifiers', failed(csv('approved', text.replace(',2,45385,1,XS,', ',2,45385,1,59;XS,'))))
        self.assertIn('csv.items.approver', failed(csv('approved', text.replace(',agent,2026-11-03T22:05:00+00:00,', ',human,2026-11-03T22:05:00+00:00,'))))
        self.assertIn('csv.items.evidence.exact', failed(csv('approved', text.replace(',1,256,329', ',1,256,330'))))
        self.assertIn('csv.groups', failed(csv('approved', text.replace(rows[2], rows[2] + '\r\n' + rows[2].replace(',1,45380,1,', ',1,45380,2,')))))
        self.assertIn('csv.items.quoted', failed(csv('approved', text.replace('COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.,1,256,329', ',,,'))))

    def test_a_draft_has_no_approval_cell_and_statuses_as_the_view_implies(self):
        text = sample('customer-report-draft.csv')
        self.assertEqual(failed(csv('draft', text)), [])
        self.assertIn('csv.approval_cells', failed(csv('draft', text.replace(',approved,,,,', ',approved,CPT Studio review agent (automated agent),agent,2026-11-03T22:05:00+00:00,', 1))))
        self.assertIn('csv.items.status', failed(csv('draft', text.replace(',approved,,,,', ',needs_detail,,,,', 1))))
        self.assertEqual(failed(csv('draft', text.replace(',approved,,,,', ',Approved,,,,'))), [], 'a status label reads as its key')


class DownloadTests(unittest.TestCase):
    def download(self, kind, fmt, data: bytes, **extra) -> dict:
        digest = hashlib.sha256(data).hexdigest()
        return {'kind': kind, 'fmt': fmt, 'audience': 'customer', 'path': f'cux/{kind}-{fmt}.{fmt}', 'size': len(data),
                'report_id': f'r-{kind}-{fmt}', 'sha256': digest, 'refetch_sha256': digest, 'header_sha256': None,
                'operator_sha256': digest, 'operator_audience': 'customer', 'operator_download_sha256': digest,
                'operator_header_sha256': digest, **extra}

    def test_the_bytes_are_the_customer_re_fetch_s_and_the_operator_s_and_carry_no_hash_header(self):
        data = sample('customer-report-approved.txt').encode('utf-8')
        ok = self.download('approved', 'txt', data)
        self.assertEqual(failed(vd.check_customer_hashes('d', 'approved.txt', data, ok)), [])
        for change, check in (({'header_sha256': 'a' * 64}, 'header.no_hash'), ({'operator_sha256': None}, 'sha256.operator_sha256'),
                              ({'refetch_sha256': 'b' * 64}, 'sha256.refetch_sha256'), ({'operator_audience': 'operator'}, 'audience'),
                              ({'operator_download_sha256': 'c' * 64}, 'sha256.operator_download_sha256'), ({'size': 3}, 'size')):
            with self.subTest(change=change):
                self.assertIn(check, failed(vd.check_customer_hashes('d', 'approved.txt', data, {**ok, **change})))

    def write_evidence(self, root: Path, snapshots: dict, downloads=None) -> Path:
        (root / 'cux').mkdir()
        for name in ('operator-encounter.json', 'operator-trace.json', 'customer-encounter.json'):
            (root / 'cux' / name).write_text(sample(name), encoding='utf-8')
        records = []
        for kind in ('draft', 'approved'):
            for fmt in ('txt', 'csv'):
                data = sample(f'customer-report-{kind}.{fmt}').encode('utf-8')
                (root / 'cux' / f'{kind}-{fmt}.{fmt}').write_bytes(data)
                records.append(self.download(kind, fmt, data))
        doc = {'id': 'cux-01', 'encounter_id': operator()['id'], 'decisions': [], 'downloads': records if downloads is None else downloads, **snapshots}
        evidence = {'schema': 'cpt-studio-browser-evidence@2', 'session': {'user': {'label': AGENT}}, 'documents': [doc]}
        path = root / 'evidence.json'
        path.write_text(json.dumps(evidence), encoding='utf-8')
        return path

    def test_main_checks_every_customer_download_against_the_operator_snapshot_the_evidence_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = self.write_evidence(root, {'operator_snapshots': {'final': 'cux/operator-encounter.json', 'trace': 'cux/operator-trace.json'},
                                                  'customer_snapshots': {'final': 'cux/customer-encounter.json'}})
            out = io.StringIO()
            with redirect_stdout(out):
                code = vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            self.assertEqual([r for r in results if r['status'] != 'pass'], [])
            self.assertEqual(code, 0, out.getvalue()[-2000:])
            snapshot = next(r for r in results if r['check'] == 'api.snapshot')
            self.assertTrue(snapshot['detail'].endswith('cux/operator-encounter.json'))
            self.assertEqual(len({(r['report'], r['check']) for r in results if r['check'] == 'scan.file'}), 4)

    def test_the_customer_snapshot_is_never_the_source_of_truth_and_api_dir_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = self.write_evidence(root, {'customer_snapshots': {'final': 'cux/customer-encounter.json'}})
            out = io.StringIO()
            with redirect_stdout(out):
                code = vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            self.assertEqual(code, 2, 'no operator view: the content checks could not run')
            self.assertEqual(next(r['status'] for r in results if r['check'] == 'api.snapshot'), 'incomplete')
            self.assertTrue(all(r['status'] == 'incomplete' for r in results if r['check'] == 'content.vs.operator'))
            api_dir = root / 'api'
            api_dir.mkdir()
            (api_dir / f'{operator()["id"]}.json').write_text(sample('operator-encounter.json'), encoding='utf-8')
            (root / 'downloads.json').unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(vd.main(['--evidence', str(evidence), '--api-dir', str(api_dir), '--json-out', str(root / 'downloads.json')]), 0)

    def test_a_customer_report_recorded_as_an_operator_download_or_of_an_unknown_kind_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = sample('customer-report-approved.txt').encode('utf-8')
            records = [{**self.download('approved', 'txt', data), 'audience': None}, {**self.download('reviewed', 'txt', data)}]
            evidence = self.write_evidence(root, {'operator_snapshots': {'final': 'cux/operator-encounter.json'}}, downloads=records)
            for record, name in zip(records, ('approved-txt.txt', 'approved-txt.txt')):
                record['path'] = f'cux/{name}'
            payload = json.loads(evidence.read_text())
            payload['documents'][0]['downloads'] = records
            evidence.write_text(json.dumps(payload))
            with redirect_stdout(io.StringIO()):
                vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            fails = {(r['report'], r['check']) for r in results if r['status'] == 'fail'}
            self.assertIn(('approved.txt', 'audience.recorded'), fails)
            self.assertIn(('reviewed.txt', 'format'), fails)


if __name__ == '__main__':
    unittest.main()
