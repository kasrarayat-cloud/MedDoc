"""Refutation round 2 of the core repair (2026-11-04): the customer reports, and the download check that is the install's
acceptance evidence (L3-1, L3-3, L3-6; the walk's half of L3-3, L3-5, L3-7, L3-9 and L3-10 is in the ops suites).

- Each real customer export - created through POST /api/encounters/<id>/reports and fetched through the customer
  download - is held by ops/verify_downloads.py to the operator view a platform operator with NO membership reads
  (GET /ops/api/encounters/<id>, as ops-agent reads it) and passes every check, file by file and through the tool's own
  driver over evidence recorded as the walk records it; the same genuine file with one fact changed fails the check that
  fact belongs to (L3-1: every genuine export failed checks the hand-written samples passed).
- A decided modifier is compared with what the operator view's decision records, and where the view records none the
  comparison could not run - never "none was chosen" (L3-3).
- An approval agent review took part in - the approver an agent, or an agent's reinstatement behind a human's approval
  (fidelity:8, the page's rule) - carries "Agent-executed synthetic review — not clinical approval" in both reports,
  draft and approved, TXT and CSV, beside the approver's own kind; a human's own approval carries it nowhere (L3-6).
- The walk's customer-vs-operator check (ops/verify_browser.cjs, run by node) judges the real customer payload against
  ops-agent's real operator view: the actions the customer is offered against what the server accepts from that
  customer - never the operator's own, which are none (L3-5) - and the approved export withheld when nothing is approved
  as the one documented readiness difference (L3-9).
- The committed verification samples are studio/reports.py's own bytes of the sample snapshots, and those snapshots
  have the shape customer_snapshot builds from a real encounter (SampleReportTests; SnapshotShapeTests); the tools'
  copies of the server's words and check ids are the server's (ConstantsTests).

DB-backed (CPT_STUDIO_TEST_DB_SUFFIX) except SampleReportTests and ConstantsTests; synthetic data only; nothing is sent.
The walk tests need node (as the CI job has).
"""
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase

from studio import customer_api, models, reports, review
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_cux_review import persist

ROOT = Path(reports.__file__).resolve().parents[1]
SAMPLES = ROOT / 'ops' / 'verification' / 'samples'
_spec = importlib.util.spec_from_file_location('cpt_r2_verify_downloads', ROOT / 'ops' / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_r2_verify_downloads'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

NOTE = 'Synthetic: agent-executed synthetic verification review (refutation round 2).'
VERIFY_BROWSER = ROOT / 'ops' / 'verify_browser.cjs'
WALK_NODE = r"""
const vb = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const data = JSON.parse(input);
  process.stdout.write(JSON.stringify(vb.checkCustomerVsOperator(data.cust, data.op)));
});
"""
KINDS = (('draft', 'txt'), ('draft', 'csv'), ('approved', 'txt'), ('approved', 'csv'))
MODIFIERS_CHECK = {'txt': 'items.modifiers', 'csv': 'csv.items.modifiers'}


def signed_in(user):
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    return client


def post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type='application/json')


def changed(text, old, new, count=1):
    """``text`` with ``old`` replaced once: it must occur exactly ``count`` times, and the edit must apply."""
    assert text.count(old) == count, f'expected {count} / measured {text.count(old)} of {old!r}'
    out = text.replace(old, new, 1)
    assert out != text, f'the edit of {old!r} did not apply'
    return out


def keys(value):
    """The key structure of a JSON value: a dict's keys with their values' structure, a list's elements' (merged)."""
    if isinstance(value, dict):
        return {key: keys(item) for key, item in value.items()}
    if isinstance(value, list):
        merged = {}
        for item in value:
            shape = keys(item)
            if isinstance(shape, dict):
                merged.update(shape)
        return [merged] if merged else []
    return None


def walk_judged(cust, op):
    """{check id: (status, reason)} of ops/verify_browser.cjs checkCustomerVsOperator over a customer payload and an
    operator view, as the walk judges them (node runs the file)."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the walk checks need it')
    done = subprocess.run([node, '-e', WALK_NODE, str(VERIFY_BROWSER)], input=json.dumps({'cust': cust, 'op': op}),
                          capture_output=True, text=True, timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    return {item['id']: (item['status'], item['reason']) for item in json.loads(done.stdout)}


def with_modifiers(view, persisted):
    """The operator view as serializers._decision_json serves it once it carries each decision's chosen modifier
    (refutation round 2, L3-3, the overlay owner's half): ``persisted`` maps a proposal id to Decision.modifiers."""
    view = copy.deepcopy(view)
    for proposal in view['assessment']['proposals']:
        if proposal.get('decision') and 'modifiers' not in proposal['decision']:
            proposal['decision']['modifiers'] = list(persisted.get(proposal['id'], []))
    return view


class ExportCase(TestCase):
    def payload(self, s, user):
        response = signed_in(user).get(f'/api/encounters/{s.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def decide(self, s, user, code, action, modifiers=()):
        doc = self.payload(s, user)
        proposal_id = next(item['id'] for item in doc['codes'] if item['code'] == code)
        body = {'proposal_id': proposal_id, 'action': action, 'note': NOTE}
        if action == 'approve':
            body.update(acknowledgement=review.ACKNOWLEDGEMENTS[user.actor_kind], modifiers=list(modifiers))
        response = post(signed_in(user), f'/api/encounters/{s.encounter.pk}/decisions', body)
        self.assertEqual(response.status_code, 201, response.content)
        return {'proposal_id': proposal_id, 'code': code, 'action': action, 'http_status': 201}

    def exports(self, s, user, kinds=KINDS):
        """{(kind, fmt): (report row, downloaded bytes)} - each made and downloaded by ``user`` as the page does."""
        client = signed_in(user)
        out = {}
        for kind, fmt in kinds:
            made = post(client, f'/api/encounters/{s.encounter.pk}/reports', {'kind': kind, 'fmt': fmt})
            self.assertEqual(made.status_code, 201, made.content)
            got = client.get(made.json()['download_url'])
            self.assertEqual(got.status_code, 200)
            out[(kind, fmt)] = (made.json(), got.content)
        return out

    def operator(self, s):
        """A client of a platform operator with a grant and no membership, as ops-agent is (CORE-UX-DESIGN.md 9)."""
        name = f'ops-agent-r2-{str(s.encounter.pk)[:8]}'
        user = models.User.objects.filter(username=name).first() or f.user(name, actor_kind=models.User.AGENT)
        return ops.client(user)

    def operator_view(self, s):
        client = self.operator(s)
        view = client.get(f'/ops/api/encounters/{s.encounter.pk}')
        trace = client.get(f'/ops/api/encounters/{s.encounter.pk}/trace')
        self.assertEqual((view.status_code, trace.status_code), (200, 200))
        view = view.json()
        self.assertFalse(view['permissions']['can_review'])  # the operator's own permissions allow nothing
        return view, trace.json()

    def persisted_modifiers(self, s):
        s.encounter.refresh_from_db()
        current = review.current_decisions(s.encounter.current_assessment)
        return {str(decision.proposal_id): list(decision.modifiers or []) for decision in current.values()}

    def judged(self, files, view, trace, by):
        """{(kind, fmt): [(check, status, detail) of every result that is not a pass]}."""
        out = {}
        for (kind, fmt), (_, data) in files.items():
            text = data.decode('utf-8')
            results = (vd.check_customer_txt('cux-r2', f'{kind}.{fmt}', text, kind, view, trace, by) if fmt == 'txt'
                       else vd.check_customer_csv('cux-r2', f'{kind}.{fmt}', text, kind, view, trace))
            self.assertIn('format', {r.check for r in results})
            out[(kind, fmt)] = [(r.check, r.status, r.detail) for r in results if r.status != 'pass']
        return out

    def checked_view(self, s, files, by):
        """The operator view the reports are held to. Where the served view says which modifier each decision chose
        (serializers._decision_json, the overlay owner's half of L3-3), it is used as served and must say what the rows
        hold; where it does not yet, every report naming a decided code is first shown to fail closed on exactly that -
        the modifiers could not be verified, never "none chosen" - and the view is then read with the persisted values."""
        view, trace = self.operator_view(s)
        persisted = self.persisted_modifiers(s)
        decisions = [p['decision'] for p in view['assessment']['proposals'] if p.get('decision')]
        served = {d['proposal_id']: d['modifiers'] for d in decisions if 'modifiers' in d}
        self.assertEqual(served, {key: persisted[key] for key in served})  # what the view says is what the rows hold
        if len(served) == len(decisions):
            return view, trace
        for (kind, fmt), bad in self.judged(files, view, trace, by).items():
            unknown = any(item['modifiers'] is vd.UNKNOWN for item in vd.customer_truth(view, kind))
            self.assertEqual([(check, status) for check, status, _ in bad],
                             [(MODIFIERS_CHECK[fmt], 'incomplete')] if unknown else [], (kind, fmt, bad))
        return with_modifiers(view, persisted), trace

    def assert_all_pass(self, files, view, trace, by):
        for key, bad in self.judged(files, view, trace, by).items():
            self.assertEqual(bad, [], key)

    def failing(self, kind, fmt, text, view, trace, by):
        results = (vd.check_customer_txt('cux-r2', f'{kind}.{fmt}', text, kind, view, trace, by) if fmt == 'txt'
                   else vd.check_customer_csv('cux-r2', f'{kind}.{fmt}', text, kind, view, trace))
        return sorted({r.check for r in results if r.status == 'fail'})


class GenuineExportTests(ExportCase):
    """L3-1 and L3-3: the genuine exports pass, and a genuine export with one fact changed fails that fact's check."""

    def setUp(self):
        super().setUp()
        self.s = persist('pair')
        self.undecided = self.exports(self.s, self.s.agent, kinds=(('draft', 'txt'), ('draft', 'csv')))
        self.undecided_view = self.operator_view(self.s)  # the operator view the undecided drafts were made from
        self.decisions = [self.decide(self.s, self.s.agent, '45380', 'approve'),
                          self.decide(self.s, self.s.agent, '45385', 'approve', ['XS'])]
        self.files = self.exports(self.s, self.s.agent)
        self.by = self.s.agent.label()

    def test_every_genuine_export_passes_every_check_against_the_operator_view(self):
        self.assert_all_pass(self.undecided, *self.undecided_view, self.by)  # nothing decided: no modifier to compare
        view, trace = self.checked_view(self.s, self.files, self.by)
        self.assert_all_pass(self.files, view, trace, self.by)
        texts = {key: data.decode('utf-8') for key, (_, data) in self.files.items()}
        lines = texts[('approved', 'txt')].splitlines()
        self.assertEqual((lines[0], lines[1], lines[-1]), (reports.SYNTHETIC_LINE, reports.CUSTOMER_HEADLINES['approved'],
                                                           reports.SYNTHETIC_LINE))
        self.assertIn('2. 45385 — units 1 — modifiers: XS', texts[('approved', 'txt')])

    def test_the_tool_s_own_driver_passes_the_genuine_downloads_recorded_as_the_walk_records_them(self):
        view, trace = self.checked_view(self.s, self.files, self.by)
        customer, operator = signed_in(self.s.agent), self.operator(self.s)
        listing = {item['id']: item for item in operator.get(f'/ops/api/encounters/{self.s.encounter.pk}/reports')
                   .json()['reports']}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'cux').mkdir()
            records = []
            for (kind, fmt), (row, data) in self.files.items():
                path = root / 'cux' / f'{kind}.{fmt}'
                path.write_bytes(data)
                again = customer.get(row['download_url'])
                stored = operator.get(f'/ops/api/reports/{row["id"]}/download')
                self.assertEqual((again.status_code, stored.status_code), (200, 200))
                records.append({'kind': kind, 'fmt': fmt, 'audience': 'customer', 'path': f'cux/{kind}.{fmt}',
                                'size': len(data), 'report_id': row['id'], 'sha256': hashlib.sha256(data).hexdigest(),
                                'refetch_sha256': hashlib.sha256(again.content).hexdigest(),
                                'header_sha256': again.headers.get('X-Content-SHA256'),
                                'operator_sha256': listing[row['id']]['sha256'],
                                'operator_audience': listing[row['id']]['audience'],
                                'operator_download_sha256': hashlib.sha256(stored.content).hexdigest(),
                                'operator_header_sha256': stored.headers.get('X-Content-SHA256')})
            api = root / 'api'
            api.mkdir()
            (api / f'{self.s.encounter.pk}.json').write_text(json.dumps(view), encoding='utf-8')
            (api / f'{self.s.encounter.pk}.trace.json').write_text(json.dumps(trace), encoding='utf-8')
            evidence = {'schema': 'cpt-studio-browser-evidence@2', 'session': {'user': {'label': self.by}},
                        'documents': [{'id': 'cux-r2', 'encounter_id': str(self.s.encounter.pk),
                                       'decisions': self.decisions, 'downloads': records}]}
            (root / 'evidence.json').write_text(json.dumps(evidence), encoding='utf-8')
            with redirect_stdout(StringIO()) as printed:
                code = vd.main(['--evidence', str(root / 'evidence.json'), '--api-dir', str(api),
                                '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text(encoding='utf-8'))
        self.assertEqual([r for r in results if r['status'] != 'pass'], [], printed.getvalue()[-3000:])
        self.assertEqual(code, 0)
        self.assertEqual(len({r['report'] for r in results if r['check'] == 'scan.file'}), 4)

    def test_a_genuine_export_with_one_fact_changed_fails_the_check_of_that_fact(self):
        view, trace = self.checked_view(self.s, self.files, self.by)
        text = {key: data.decode('utf-8') for key, (_, data) in self.files.items()}
        agent, line = self.by, reports.AGENT_LINE
        approved_txt, draft_txt = text[('approved', 'txt')], text[('draft', 'txt')]
        approved_csv, draft_csv = text[('approved', 'csv')], text[('draft', 'csv')]
        block = approved_txt[approved_txt.index('2. 45385'):approved_txt.index('\nLimitations')]
        cases = [
            ('approved', 'txt', changed(approved_txt, '45385 — units 1 — modifiers: XS', '45385 — units 1 — modifiers: none'),
             'items.modifiers'),
            ('approved', 'txt', changed(approved_txt, '45380 — units 1 —', '45380 — units 2 —'), 'items.units'),
            ('approved', 'txt', changed(approved_txt, f'Approved by {agent} (agent) at', f'Approved by {agent} (human) at', 2),
             'items.approver'),
            ('approved', 'txt', changed(approved_txt, f'Approved by {agent} (agent)', 'Approved by Dr Synthetic (human)', 2),
             'items.approver'),
            ('approved', 'txt', changed(approved_txt, f'\n   {line}\n', '\n', 2), 'items.agent_label'),
            ('approved', 'txt', changed(approved_txt, f'{reports.CUSTOMER_HEADLINES["approved"]}\n{line}\n',
                                        f'{reports.CUSTOMER_HEADLINES["approved"]}\n'), 'header.agent_label'),
            ('approved', 'txt', changed(approved_txt, 'characters 270–345', 'characters 271–346'), 'items.evidence.exact'),
            ('approved', 'txt', changed(approved_txt, f'{reports.SYNTHETIC_LINE}\n', '', 2), 'marker.synthetic'),
            ('approved', 'txt', changed(approved_txt, '\nLimitations', '\n3. 45378 — units 1 — modifiers: none\nLimitations'),
             'items.items'),
            ('approved', 'txt', changed(approved_txt, block, ''), 'items.items'),
            ('approved', 'txt', changed(approved_txt, '\nLimitations\n', '\nLimitations\n3. 45378 — units 1 — modifiers: none\n'),
             'items.outside_section'),
            ('approved', 'csv', changed(approved_csv, '"45385","1","XS"', '"45385","1",""'), 'csv.items.modifiers'),
            ('approved', 'csv', changed(approved_csv, '"agent","2026', '"human","2026', 2), 'csv.items.approver'),
            ('approved', 'csv', changed(approved_csv, f'"{line}"', '""', 2), 'csv.items.agent_label'),
            ('approved', 'csv', changed(approved_csv, '"270","345"', '"271","346"'), 'csv.items.evidence.exact'),
            ('approved', 'csv', changed(approved_csv, '"' + '","'.join([reports.SYNTHETIC_LINE] + [''] * 16) + '"\r\n', '', 2),
             'csv.synthetic_marker'),
            ('draft', 'txt', changed(draft_txt, '45385 — Approved —', '45385 — Ready for review —'), 'items.status'),
            ('draft', 'txt', changed(draft_txt, f'\n   {line}\n', '\n', 2), 'items.agent_label'),
            ('draft', 'txt', changed(draft_txt, '45385 — Approved — units 1 — modifiers: XS',
                                     '45385 — Approved — units 1 — modifiers: 59'), 'items.modifiers'),
            ('draft', 'csv', changed(draft_csv, '"approved","","",""', f'"approved","{agent}","agent","2026-11-04T00:00:00+00:00"', 2),
             'csv.approval_cells'),
            ('draft', 'csv', changed(draft_csv, f'"{line}"', '""', 2), 'csv.items.agent_label'),
        ]
        for kind, fmt, mutated, check in cases:
            with self.subTest(kind=kind, fmt=fmt, check=check):
                self.assertIn(check, self.failing(kind, fmt, mutated, view, trace, self.by))

    def test_a_decided_modifier_the_operator_view_does_not_record_is_never_read_as_none(self):
        view, trace = self.operator_view(self.s)
        bare = copy.deepcopy(view)
        for proposal in bare['assessment']['proposals']:
            if proposal.get('decision'):
                proposal['decision'].pop('modifiers', None)
        approved_csv = self.files[('approved', 'csv')][1].decode('utf-8')
        dropped = changed(approved_csv, '"45385","1","XS"', '"45385","1",""')
        for text in (approved_csv, dropped):  # neither the right file nor the wrong one can be judged: cannot verify
            results = {r.check: r.status for r in vd.check_customer_csv('cux-r2', 'approved.csv', text, 'approved', bare, trace)}
            self.assertEqual(results['csv.items.modifiers'], 'incomplete')
        self.assertEqual(vd.customer_truth(bare, 'approved')[1]['modifiers'], vd.UNKNOWN)
        recorded = with_modifiers(bare, self.persisted_modifiers(self.s))
        self.assertEqual(vd.customer_truth(recorded, 'approved')[1]['modifiers'], ('XS',))
        self.assertIn('csv.items.modifiers', self.failing('approved', 'csv', dropped, recorded, trace, self.by))


class AgentLabelTests(ExportCase):
    """L3-6: one approval carries one label in every export, beside the approver's own kind."""

    def texts(self, files):
        return {key: data.decode('utf-8') for key, (_, data) in files.items()}

    def rows(self, text):
        import csv
        import io
        return [row for row in csv.DictReader(io.StringIO(text)) if row['report_format'] == reports.CUSTOMER_FORMAT]

    def test_an_agent_s_approvals_are_labelled_in_the_draft_and_the_approved_export(self):
        s = persist('pair')
        self.decide(s, s.agent, '45380', 'approve')
        self.decide(s, s.agent, '45385', 'approve', ['XS'])
        files = self.exports(s, s.agent)
        text = self.texts(files)
        for kind in ('draft', 'approved'):
            rows = self.rows(text[(kind, 'csv')])
            self.assertEqual({(row['code'], row['review_label']) for row in rows},
                             {('45380', reports.AGENT_LINE), ('45385', reports.AGENT_LINE)}, kind)
            approval = {(row['approved_by'], row['approver_kind']) for row in rows}
            self.assertEqual(approval, {(s.agent.label(), 'agent')} if kind == 'approved' else {('', '')}, kind)
            lines = text[(kind, 'txt')].splitlines()
            self.assertEqual(lines[2], reports.AGENT_LINE)  # the header says it
            self.assertEqual(lines.count(f'   {reports.AGENT_LINE}'), 2, kind)  # and each approval does
        self.assertEqual(text[('approved', 'txt')].count(f'   Approved by {s.agent.label()} (agent) at '), 2)
        view, trace = self.checked_view(s, files, s.agent.label())
        self.assert_all_pass(files, view, trace, s.agent.label())

    def test_a_human_s_approval_of_an_agent_s_reinstatement_is_labelled_with_the_human_kind(self):
        # one rule everywhere (customer_api.agent_approval, L3-6): a person's approval is the person's, with no agent
        # label, even where an agent reinstated the code (who reinstated it stays in the record, not in the label)
        s = persist('denied')
        self.decide(s, s.agent, '45385', 'reinstate')
        self.decide(s, s.reviewer, '45378', 'reject')
        self.decide(s, s.reviewer, '45385', 'approve')
        codes = {code['code']: code for code in self.payload(s, s.reviewer)['codes']}
        self.assertEqual((codes['45385']['sub_label'], codes['45385']['decision']['by_kind']), ('', 'human'))
        files = self.exports(s, s.reviewer)
        text = self.texts(files)
        (approved,) = self.rows(text[('approved', 'csv')])
        self.assertEqual((approved['code'], approved['approved_by'], approved['approver_kind'], approved['review_label']),
                         ('45385', s.reviewer.label(), 'human', ''))
        self.assertEqual({(row['code'], row['review_label']) for row in self.rows(text[('draft', 'csv')])},
                         {('45378', ''), ('45385', '')})
        txt = text[('approved', 'txt')]
        self.assertIn(f'   Approved by {s.reviewer.label()} (human) at ', txt)
        self.assertNotIn(reports.AGENT_LINE, txt)
        self.assertNotIn(reports.AGENT_LINE, text[('draft', 'txt')])
        view, trace = self.checked_view(s, {key: files[key] for key in (('approved', 'txt'), ('approved', 'csv'))},
                                        s.reviewer.label())
        self.assertEqual(next(p for p in view['assessment']['proposals'] if p['code'] == '45385')['reinstated_by']['reviewer_kind'],
                         'agent')
        self.assert_all_pass({key: files[key] for key in (('approved', 'txt'), ('approved', 'csv'))}, view, trace,
                             s.reviewer.label())
        # the draft's quotations are the page's ("Why this code?", the overlay owner's half of L3-7); its labels,
        # statuses, codes and units are this repair's
        for (kind, fmt), bad in self.judged({key: files[key] for key in (('draft', 'txt'), ('draft', 'csv'))}, view, trace,
                                            s.reviewer.label()).items():
            prefix = 'items' if fmt == 'txt' else 'csv.items'
            owned = {f'{prefix}.items', f'{prefix}.status', f'{prefix}.units', f'{prefix}.agent_label', 'header.agent_label',
                     'csv.approval_cells', 'csv.synthetic_marker', 'marker.synthetic', 'format'}
            self.assertEqual([item for item in bad if item[0] in owned], [], (kind, fmt))
        # the label is the export's statement: an agent label put on this person's approval fails the check
        approved_csv = text[('approved', 'csv')]
        row = next(line for line in approved_csv.split('\r\n') if '"45385"' in line)
        self.assertTrue(row.endswith(',""'), row)
        forged = changed(approved_csv, row, row[:-3] + f',"{reports.AGENT_LINE}"')
        self.assertIn('csv.items.agent_label', self.failing('approved', 'csv', forged, view, trace, s.reviewer.label()))

    def test_a_human_s_own_approvals_carry_no_agent_label_anywhere(self):
        s = persist('pair')
        self.decide(s, s.reviewer, '45380', 'approve')
        self.decide(s, s.reviewer, '45385', 'approve', ['XS'])
        files = self.exports(s, s.reviewer)
        for key, value in self.texts(files).items():
            self.assertNotIn(reports.AGENT_LINE, value, key)
            self.assertNotIn('agent-executed', value.lower(), key)
        view, trace = self.checked_view(s, files, s.reviewer.label())
        self.assert_all_pass(files, view, trace, s.reviewer.label())
        approved_csv = self.texts(files)[('approved', 'csv')]
        row = approved_csv.split('\r\n')[2]  # the header, the banner, then 45380's row: its review_label is empty
        self.assertTrue(row.endswith(',""'), row)
        forged = changed(approved_csv, row, row[:-3] + f',"{reports.AGENT_LINE}"')  # a human's approval labelled an agent's
        self.assertIn('csv.items.agent_label', self.failing('approved', 'csv', forged, view, trace, s.reviewer.label()))


class WalkJudgesTheRealSiteTests(ExportCase):
    """The walk's customer-vs-operator check over the real customer payload and ops-agent's real operator view."""

    def judged(self, s, user):
        cust = self.payload(s, user)
        view, _ = self.operator_view(s)
        served = walk_judged(cust, view)
        if not all('modifiers' in p['decision'] for p in view['assessment']['proposals'] if p.get('decision')):
            view = with_modifiers(view, self.persisted_modifiers(s))
        return cust, served, walk_judged(cust, view)

    def test_the_actions_offered_are_judged_by_what_the_server_accepts_from_the_customer(self):
        s = persist('pair')
        cust, served, judged = self.judged(s, s.agent)
        self.assertEqual([code['allowed_actions'] for code in cust['codes']], [['approve', 'reject'], ['approve', 'reject']])
        self.assertEqual(served['customer.codes.actions'][0], 'pass', served['customer.codes.actions'])
        self.assertEqual([k for k, (status, _) in judged.items() if status != 'pass'], [])
        self.decide(s, s.agent, '45380', 'approve')
        self.decide(s, s.agent, '45385', 'approve', ['XS'])
        cust, served, judged = self.judged(s, s.agent)
        self.assertEqual([code['allowed_actions'] for code in cust['codes']], [['revoke'], ['revoke']])
        view, _ = self.operator_view(s)
        self.assertEqual([p['allowed_actions'] for p in view['assessment']['proposals']], [[], []])  # the operator's own: none
        self.assertEqual(judged['customer.codes.actions'][0], 'pass', judged['customer.codes.actions'])
        self.assertEqual([k for k, (status, _) in judged.items() if status != 'pass'], [])
        # a modifier the served view does not record is never read as none (L3-3): the check could not run
        if not all('modifiers' in p['decision'] for p in view['assessment']['proposals'] if p.get('decision')):
            self.assertEqual(served['customer.codes.units_modifiers'][0], 'fail')
            self.assertIn('cannot verify', served['customer.codes.units_modifiers'][1])
        # a viewer is offered nothing, and an offer to one would be judged wrong
        viewer = self.payload(s, s.viewer)
        self.assertEqual([code['allowed_actions'] for code in viewer['codes']], [[], []])
        self.assertEqual(walk_judged(viewer, with_modifiers(view, self.persisted_modifiers(s)))['customer.codes.actions'][0], 'pass')
        viewer['codes'][0]['allowed_actions'] = ['revoke']
        self.assertEqual(walk_judged(viewer, with_modifiers(view, self.persisted_modifiers(s)))['customer.codes.actions'][0], 'fail')

    def test_nothing_approved_withholds_the_approved_export_as_the_one_documented_difference(self):
        s = persist('pair')
        self.decide(s, s.reviewer, '45380', 'reject')
        self.decide(s, s.reviewer, '45385', 'reject')
        cust, _, judged = self.judged(s, s.reviewer)
        view, _ = self.operator_view(s)
        self.assertEqual((view['readiness']['reviewed'], cust['readiness']['approved'], cust['readiness']['blockers']),
                         (True, False, [customer_api.NONE_APPROVED]))
        self.assertEqual(judged['customer.readiness'][0], 'pass', judged['customer.readiness'])
        self.assertEqual([k for k, (status, _) in judged.items() if status != 'pass'], [])

    def test_a_human_s_approval_of_an_agent_s_reinstatement_is_judged_by_the_page_s_rule(self):
        s = persist('denied')
        self.decide(s, s.agent, '45385', 'reinstate')
        self.decide(s, s.reviewer, '45378', 'reject')
        self.decide(s, s.reviewer, '45385', 'approve')
        _, _, judged = self.judged(s, s.reviewer)
        for check in ('customer.codes.status', 'customer.codes.decision', 'customer.codes.actions', 'customer.readiness',
                      'customer.codes.units_modifiers'):
            self.assertEqual(judged[check][0], 'pass', (check, judged[check]))


class ConstantsTests(SimpleTestCase):
    """The tools' copies of the server's words, columns and check ids are the server's own."""

    def test_the_walk_and_the_download_check_name_what_the_server_names(self):
        source = VERIFY_BROWSER.read_text(encoding='utf-8')

        def constant(name):
            found = re.findall(rf"^const {name} = '([^']*)';", source, re.M)
            self.assertEqual(len(found), 1, name)
            return found[0]

        self.assertEqual(constant('NOT_FINAL_BLOCKER'), review.NOT_FINAL_BLOCKER)
        self.assertEqual(constant('SAME_DAY_EM_GATE'), review.SAME_DAY_EM_GATE)
        self.assertEqual(constant('SAME_DAY_PROCEDURE'), review.SAME_DAY_PROCEDURE)
        vocabulary = json.loads((ROOT / 'ops' / 'verification' / 'customer-contract.json').read_text(encoding='utf-8'))['vocabulary']
        self.assertEqual(vocabulary['none_approved_blocker'], customer_api.NONE_APPROVED)
        self.assertEqual(vocabulary['agent_sub_label'], customer_api.AGENT_SUB_LABEL)
        self.assertEqual(customer_api.AGENT_SUB_LABEL, reports.AGENT_LINE)
        self.assertEqual(vd.AGENT_SUB_LABEL, reports.AGENT_LINE)
        self.assertEqual(vd.CUSTOMER_CSV_COLUMNS, reports.CUSTOMER_CSV_COLUMNS)
        self.assertEqual(vd.CUSTOMER_FORMAT, reports.CUSTOMER_FORMAT)
        self.assertEqual(vd.CUSTOMER_STATUS_LABELS, customer_api.STATUS_LABELS)


class SnapshotShapeTests(ExportCase):
    """The committed report snapshots (make_samples.report_snapshots) have the shape customer_snapshot builds."""

    def test_the_sample_snapshots_have_the_real_snapshot_s_shape(self):
        s = persist('pair')
        self.decide(s, s.agent, '45380', 'approve')
        self.decide(s, s.agent, '45385', 'approve', ['XS'])
        sample = json.loads((SAMPLES / 'customer-report-snapshots.json').read_text(encoding='utf-8'))
        for kind in ('draft', 'approved'):
            real = json.loads(json.dumps(reports.customer_snapshot(s.encounter, kind)))
            self.assertEqual(keys(sample[kind]), keys(real), kind)
        self.assertEqual(set(sample['generated']), {'at', 'by'})


class SampleReportTests(SimpleTestCase):
    """The committed customer report samples (ops/verification/samples/customer-report-*) are studio/reports.py's own
    bytes of the committed snapshots, so ops/verify_downloads.py's offline suite reads the grammar the server writes.
    CPT_STUDIO_WRITE_SAMPLES=1 writes them."""

    def test_the_committed_report_samples_are_the_renderer_s_own_bytes(self):
        snapshots = json.loads((SAMPLES / 'customer-report-snapshots.json').read_text(encoding='utf-8'))
        rendered = {f'customer-report-{kind}.{fmt}': reports.CUSTOMER_RENDERERS[fmt](snapshots[kind], snapshots['generated'])
                    for kind in ('approved', 'draft') for fmt in ('txt', 'csv')}
        if os.environ.get('CPT_STUDIO_WRITE_SAMPLES') == '1':
            for name, content in rendered.items():
                (SAMPLES / name).write_bytes(content)
        stale = [name for name, content in rendered.items() if (SAMPLES / name).read_bytes() != content]
        self.assertEqual(stale, [], 'run CPT_STUDIO_WRITE_SAMPLES=1 manage.py test tests.test_cux_r2_reports.SampleReportTests')
        spec = importlib.util.spec_from_file_location('cpt_r2_make_samples', SAMPLES / 'make_samples.py')
        make = importlib.util.module_from_spec(spec)
        sys.modules['cpt_r2_make_samples'] = make
        spec.loader.exec_module(make)
        self.assertEqual(set(rendered), set(make.REPORT_FILES))
        self.assertFalse(set(make.REPORT_FILES) & set(make.outputs()), 'the stdlib generator writes no report text')
