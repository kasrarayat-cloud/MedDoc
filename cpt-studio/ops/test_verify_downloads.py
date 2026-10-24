"""Unit tests for ops/verify_downloads.py with tiny hand-made report files.

The fixtures follow the layout of studio/reports.py ('cpt-studio-report@1').

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_verify_downloads.py' -v
"""
import copy
import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_verify_downloads', HERE / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_downloads'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Colonoscopy to the cecum.\n'
        'Cold snare polypectomy of two transverse polyps.\n'
        'Cold forceps biopsy of a rectal lesion.\n'
        'Plan: upper endoscopy is scheduled next month.\n')
TEXT_SHA = hashlib.sha256(TEXT.encode()).hexdigest()
FILE_SHA = 'f' * 64
AGENT = 'CPT Studio review agent (automated agent)'
SNARE = 'Cold snare polypectomy of two transverse polyps.'
BIOPSY = 'Cold forceps biopsy of a rectal lesion.'
PLANNED = 'Plan: upper endoscopy is scheduled next month.'
LABELS = {'45': ('gi.colonoscopy', 'Colonoscopy', 'COLONOSCOPY'),
          '43': ('gi.egd', 'Upper GI endoscopy (EGD, esophagoscopy, enteroscopy)', 'UPPER GI ENDOSCOPY')}


def span(passage, **extra):
    start = TEXT.index(passage)
    return {'context_index': 0, 'start': start, 'end': start + len(passage), 'text': passage, 'exact': True,
            'page': 1, **extra}


def proposal(pid, code, bucket, status, passage, action=None, units=1):
    family, label, eyebrow = LABELS[code[:2]]
    decision = None if action is None else {
        'id': f'd-{pid}', 'proposal_id': pid, 'code': code, 'action': action, 'reviewer': AGENT,
        'reviewer_kind': 'agent', 'created_at': '2026-10-23T21:00:00+00:00'}
    state = {'approve': 'approved', 'reject': 'rejected', None: 'undecided'}[action]
    return {'id': pid, 'bucket': bucket, 'code': code, 'family': family, 'family_label': label, 'eyebrow': eyebrow,
            'status': status, 'units': units, 'evidence': [span(passage)], 'decision': decision,
            'decision_state': state}


def base_proposals():
    return [proposal('p-snare', '45385', 'selected', 'ready', SNARE, 'approve'),
            proposal('p-biopsy', '45380', 'selected', 'ready', BIOPSY, 'reject'),
            proposal('p-alt', '45378', 'alternative', 'informational', SNARE),
            proposal('p-egd', '43239', 'excluded', 'excluded', PLANNED)]


def api(proposals=None, reports=()):
    return {'id': 'enc-1',
            'revision': {'number': 1, 'text': TEXT, 'text_sha256': TEXT_SHA,
                         'source_file': {'name': 'note.txt', 'sha256': FILE_SHA}},
            'assessment': {'id': 'asm-1', 'proposals': proposals if proposals is not None else base_proposals()},
            'reports': list(reports)}


def listed_as(p, kind):
    return vd.expected_list(p, kind)


def evidence_line(s):
    return f'"{s["text"]}" [chars {s["start"]}–{s["end"]}, page 1]'


def txt_report(kind, proposals=None, *, headline=None, marker=True, agent_line=True, reviewer=AGENT,
               mutate_lines=None):
    """A TXT report laid out like reports.render_txt."""
    proposals = proposals if proposals is not None else base_proposals()
    lines = [headline or ('CPT STUDIO CODING REPORT — DRAFT — NOT REVIEWED' if kind == 'draft'
                          else 'CPT STUDIO CODING REPORT — REVIEWED'),
             'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS' if marker else 'Synthetic data']
    if agent_line:
        lines.append('Agent-executed synthetic review — not clinical approval')
    lines += ['Generated: 2026-10-23T21:00:00Z · format cpt-studio-report@1', 'Review status: complete', '',
              'ENCOUNTER, SOURCE AND REVISION', '  Encounter id: enc-1',
              '  Revision: 1 (uploaded file), recorded 2026-10-23T20:59:00Z',
              f'  Source file: note.txt · text/plain · 200 bytes · sha256 {FILE_SHA}',
              f'  Extracted text: {len(TEXT)} characters · sha256 {TEXT_SHA}']

    def numbered(wanted):
        out = []
        for n, p in enumerate([p for p in proposals if listed_as(p, kind) == wanted], start=1):
            out.append(f'  {n}. {p["code"]} · {p["family_label"]} · Ready for review · units {p["units"]}')
            if p['decision']:
                verb = {'approve': 'approved', 'reject': 'rejected'}[p['decision']['action']]
                out.append(f'     Decision: {verb} by {reviewer} (agent) at 2026-10-23T21:00:00Z')
            out.append('     Evidence:')
            out += [f'       - {evidence_line(s)}' for s in p['evidence']]
        return out or ['  None.']

    def bullets(wanted, suffix):
        return [f'  - {p["code"]} · {p["family_label"]} — {suffix}' for p in proposals
                if listed_as(p, kind) == wanted] or ['  None.']

    if kind == 'reviewed':
        lines += ['', 'APPROVED SELECTIONS', *numbered('approved')]
    lines += ['', 'REJECTED — EXCLUDED FROM APPROVED RESULTS', *bullets('rejected', f'rejected by {reviewer}')]
    if kind == 'draft':
        lines += ['', 'UNDECIDED — REVIEW NOT COMPLETE', *numbered('undecided')]
    lines += ['', 'EXCLUDED CANDIDATES', *bullets('excluded', 'Excluded: planned service'),
              '', 'ALTERNATIVES — PROVIDER CANDIDATES, NEVER SELECTED',
              *bullets('alternative', 'provider alternative, never selectable'),
              '', 'NOT VERIFIED', '  Standing limitations (every code):', '',
              'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS' if marker else '', '']
    if mutate_lines:
        lines = mutate_lines(lines)
    return '\n'.join(lines)


CSV_HEADER = ['report_kind', 'encounter_id', 'revision_number', 'text_sha256', 'assessment_id', 'item_list', 'code',
              'family', 'status', 'decision', 'reviewer', 'reviewer_kind', 'units', 'evidence',
              'modifier_considerations', 'synthetic']


def csv_rows(kind, proposals=None):
    proposals = proposals if proposals is not None else base_proposals()
    rows = []
    for p in proposals:
        decision = p['decision'] or {}
        evidence = ' | '.join(f'"{s["text"]}" [{s["start"]}-{s["end"]}, p1]' for s in p['evidence'])
        rows.append({'report_kind': kind, 'encounter_id': 'enc-1', 'revision_number': '1', 'text_sha256': TEXT_SHA,
                     'assessment_id': 'asm-1', 'item_list': listed_as(p, kind), 'code': p['code'],
                     'family': p['family'], 'status': p['status'], 'decision': decision.get('action', ''),
                     'reviewer': decision.get('reviewer', ''), 'reviewer_kind': decision.get('reviewer_kind', ''),
                     'units': str(p['units']), 'evidence': evidence, 'modifier_considerations': "'-59 considered",
                     'synthetic': 'SYNTHETIC — NOT FOR BILLING'})
    return rows


def csv_report(rows, header=CSV_HEADER):
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(column, '') for column in header] if isinstance(row, dict) else row)
    return buffer.getvalue()


class Workspace:
    """A temp evidence directory: report files, an evidence JSON and an API snapshot."""

    def __init__(self, files, snapshot=None, decisions=None, mutate=None, list_reports=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / 'gi-x').mkdir()
        downloads, reports = [], []
        for n, (kind, fmt, content) in enumerate(files):
            data = content.encode('utf-8')
            path = f'gi-x/{n}-{kind}.{fmt}'
            (self.dir / path).write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            downloads.append({'kind': kind, 'fmt': fmt, 'report_id': f'r{n}', 'path': path, 'size': len(data),
                              'sha256': sha, 'api_sha256': sha, 'header_sha256': sha})
            reports.append({'id': f'r{n}', 'sha256': sha})
        snapshot = api() if snapshot is None else snapshot
        if snapshot:
            snapshot = copy.deepcopy(snapshot)
            snapshot['reports'] = reports if list_reports else []
            (self.dir / 'gi-x' / 'api-final.json').write_text(json.dumps(snapshot), encoding='utf-8')
        self.evidence = {'documents': [{
            'id': 'gi-x', 'encounter_id': 'enc-1', 'api_snapshots': {'final': 'gi-x/api-final.json'},
            'decisions': decisions if decisions is not None else [
                {'proposal_id': 'p-snare', 'code': '45385', 'action': 'approve', 'http_status': 201},
                {'proposal_id': 'p-biopsy', 'code': '45380', 'action': 'reject', 'http_status': 201}],
            'downloads': downloads}]}
        if mutate:
            mutate(self)
        self.path = self.dir / 'evidence.json'
        self.path.write_text(json.dumps(self.evidence), encoding='utf-8')

    def run(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = vd.main(['--evidence', str(self.path), '--json-out', str(self.dir / 'results.json')])
        results = json.loads((self.dir / 'results.json').read_text(encoding='utf-8'))
        self.table = out.getvalue()
        self.tmp.cleanup()
        return code, results


def failed(results):
    return sorted({r['check'] for r in results if r['status'] == 'fail'})


def statuses(results, check):
    return [r['status'] for r in results if r['check'] == check]


def all_four(proposals=None):
    return [('draft', 'txt', txt_report('draft', proposals)), ('draft', 'csv', csv_report(csv_rows('draft', proposals))),
            ('reviewed', 'txt', txt_report('reviewed', proposals)),
            ('reviewed', 'csv', csv_report(csv_rows('reviewed', proposals)))]


class PassingTests(unittest.TestCase):
    def test_consistent_draft_and_reviewed_reports_pass(self):
        ws = Workspace(all_four())
        code, results = ws.run()
        self.assertEqual(failed(results), [])
        self.assertEqual([r for r in results if r['status'] != 'pass'], [])
        self.assertEqual(code, 0)
        self.assertIn('DOC', ws.table)

    def test_a_draft_lists_a_provisional_approval_as_undecided(self):
        _, results = Workspace(all_four()[:2]).run()
        self.assertEqual(statuses(results, 'list.undecided'), ['pass'])
        self.assertEqual(statuses(results, 'csv.items'), ['pass'])

    def test_reviewed_report_with_no_approved_selection(self):
        proposals = base_proposals()
        proposals[0] = proposal('p-snare', '45385', 'selected', 'ready', SNARE, 'reject')
        decisions = [{'proposal_id': 'p-snare', 'code': '45385', 'action': 'reject', 'http_status': 201}]
        files = [('reviewed', 'txt', txt_report('reviewed', proposals)),
                 ('reviewed', 'csv', csv_report(csv_rows('reviewed', proposals)))]
        code, results = Workspace(files, snapshot=api(proposals), decisions=decisions).run()
        self.assertEqual(failed(results), [])
        self.assertEqual(code, 0)
        self.assertIn('exactly none', [r['detail'] for r in results if r['check'] == 'approved.codes'][0])

    def test_family_sub_heading_inside_a_section_does_not_end_it(self):
        def sub_heading(lines):
            at = lines.index('APPROVED SELECTIONS')
            return lines[:at + 1] + ['', 'COLONOSCOPY'] + lines[at + 1:]
        code, results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=sub_heading))]).run()
        self.assertEqual(statuses(results, 'approved.codes'), ['pass'])

    def test_lf_or_fullwidth_leading_cell_is_only_a_warning(self):
        rows = csv_rows('reviewed')
        rows[0]['modifier_considerations'] = '＝1+1'
        code, results = Workspace([('reviewed', 'csv', csv_report(rows))]).run()
        self.assertEqual(statuses(results, 'csv.neutralised_extra'), ['warn'])
        self.assertEqual(code, 0)


class FailingTests(unittest.TestCase):
    def assert_fails(self, files, *checks, **kw):
        code, results = Workspace(files, **kw).run()
        self.assertEqual(code, 1)
        for check in checks:
            self.assertIn(check, failed(results), [r for r in results if r['status'] == 'fail'])
        return results

    def reviewed_txt_with(self, edit):
        return [('reviewed', 'txt', txt_report('reviewed', mutate_lines=edit))]

    def test_file_changed_after_download(self):
        def tamper(ws):
            path = ws.dir / ws.evidence['documents'][0]['downloads'][0]['path']
            path.write_bytes(path.read_bytes().replace(b'units 1', b'units 2'))
        self.assert_fails([('reviewed', 'txt', txt_report('reviewed'))], 'sha256.sha256', 'sha256.api_sha256',
                          'sha256.listing', 'approved.codes', mutate=tamper)

    def test_api_returned_a_different_sha(self):
        def other(ws):
            ws.evidence['documents'][0]['downloads'][0]['api_sha256'] = '0' * 64
        self.assert_fails([('draft', 'txt', txt_report('draft'))], 'sha256.api_sha256', mutate=other)

    def test_rejected_code_itemised_in_approved_selections(self):
        def leak(lines):
            at = lines.index('APPROVED SELECTIONS')
            return lines[:at + 1] + ['  2. 45380 · Colonoscopy · Ready for review · units 1'] + lines[at + 1:]
        self.assert_fails(self.reviewed_txt_with(leak), 'approved.codes')

    def test_approved_code_missing_from_approved_selections(self):
        def drop(lines):
            return [line for line in lines if not line.startswith('  1. 45385')]
        self.assert_fails(self.reviewed_txt_with(drop), 'approved.codes')

    def test_approved_units_must_match(self):
        def units(lines):
            return [line.replace('units 1', 'units 3') if line.startswith('  1. 45385') else line for line in lines]
        self.assert_fails(self.reviewed_txt_with(units), 'approved.codes')

    def test_non_approved_code_mentioned_in_approved_prose_is_a_warning(self):
        def prose(lines):
            at = lines.index('APPROVED SELECTIONS')
            return lines[:at + 3] + ['     Rationale: reported instead of 45380 for the same lesion.'] + lines[at + 3:]
        code, results = Workspace(self.reviewed_txt_with(prose)).run()
        self.assertEqual(statuses(results, 'approved.mentions_others'), ['warn'])
        self.assertEqual(statuses(results, 'approved.codes'), ['pass'])

    def test_draft_must_not_have_approved_selections(self):
        def add(lines):
            return lines[:9] + ['', 'APPROVED SELECTIONS', '  1. 45385 · Colonoscopy · units 1'] + lines[9:]
        self.assert_fails([('draft', 'txt', txt_report('draft', mutate_lines=add))], 'approved.section')

    def test_draft_headline_must_say_draft_not_reviewed(self):
        self.assert_fails([('draft', 'txt', txt_report('draft', headline='CPT STUDIO CODING REPORT'))], 'headline')

    def test_reviewed_headline_must_not_say_draft(self):
        txt = txt_report('reviewed', headline='CPT STUDIO CODING REPORT — DRAFT — NOT REVIEWED')
        self.assert_fails([('reviewed', 'txt', txt)], 'headline')

    def test_txt_without_synthetic_marker(self):
        self.assert_fails([('reviewed', 'txt', txt_report('reviewed', marker=False))], 'marker.synthetic')

    def test_agent_review_must_be_labelled(self):
        self.assert_fails([('reviewed', 'txt', txt_report('reviewed', agent_line=False))], 'reviewer.agent_label')

    def test_reviewer_must_be_named(self):
        self.assert_fails([('draft', 'txt', txt_report('draft', reviewer='a reviewer'))], 'reviewer.identity')

    def test_rejected_code_missing_from_the_rejected_section(self):
        def drop(lines):
            return [line for line in lines if not line.startswith('  - 45380')]
        self.assert_fails(self.reviewed_txt_with(drop), 'list.rejected')

    def test_excluded_and_alternative_sections_are_exact(self):
        def swap(lines):
            return [line.replace('43239', '43235').replace('45378', '45384') for line in lines]
        self.assert_fails(self.reviewed_txt_with(swap), 'list.excluded', 'list.alternative')

    def test_draft_undecided_section_is_exact(self):
        def drop(lines):
            return [line for line in lines if not line.startswith('  1. 45385')]
        self.assert_fails([('draft', 'txt', txt_report('draft', mutate_lines=drop))], 'list.undecided')

    def test_approved_evidence_missing_from_txt(self):
        def drop(lines):
            return [line for line in lines if SNARE not in line]
        self.assert_fails(self.reviewed_txt_with(drop), 'evidence.present')

    def test_printed_offsets_must_quote_the_revision_text(self):
        s = span(SNARE)

        def shift(lines):
            return [line.replace(f'[chars {s["start"]}–{s["end"]}', f'[chars {s["start"] + 1}–{s["end"]}')
                    for line in lines]
        self.assert_fails(self.reviewed_txt_with(shift), 'evidence.offsets', 'evidence.present')

    def test_revision_must_be_cited(self):
        def uncite(lines):
            return [line.replace(TEXT_SHA, 'unknown').replace('Revision: 1', 'Revision: 7') for line in lines]
        self.assert_fails(self.reviewed_txt_with(uncite), 'cites.revision.text_sha256', 'cites.revision.number')

    def test_unneutralised_formula_cells(self):
        rows = csv_rows('reviewed')
        for row, value in zip(rows, ('=HYPERLINK("x")', '@SUM(1)', '\tx', '+1')):
            row['modifier_considerations'] = value
        results = self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.neutralised')
        detail = [r['detail'] for r in results if r['check'] == 'csv.neutralised'][0]
        self.assertEqual(detail.count('row '), 4)

    def test_item_list_inconsistent_with_the_decision(self):
        rows = csv_rows('reviewed')
        rows[1]['item_list'] = 'approved'
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.items', 'csv.approved_codes')

    def test_draft_csv_must_not_call_a_provisional_approval_approved(self):
        rows = csv_rows('draft')
        rows[0]['item_list'] = 'approved'
        self.assert_fails([('draft', 'csv', csv_report(rows))], 'csv.items')

    def test_decision_column_inconsistent(self):
        rows = csv_rows('reviewed')
        rows[0]['decision'] = 'reject'
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.items')

    def test_units_column_inconsistent(self):
        rows = csv_rows('reviewed')
        rows[0]['units'] = '2'
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.items')

    def test_csv_evidence_offsets_must_quote_the_revision_text(self):
        rows = csv_rows('reviewed')
        s = span(SNARE)
        rows[0]['evidence'] = f'"{SNARE}" [{s["start"] + 1}-{s["end"] + 1}, p1]'
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.evidence.offsets', 'csv.evidence.present')

    def test_csv_evidence_missing(self):
        rows = csv_rows('reviewed')
        rows[0]['evidence'] = ''
        rows[3]['evidence'] = ''
        results = self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.evidence.present')
        self.assertEqual(statuses(results, 'csv.evidence.present_other'), ['warn'])

    def test_csv_without_synthetic_marker(self):
        rows = csv_rows('reviewed')
        for row in rows:
            row['synthetic'] = 'synthetic'
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'marker.synthetic')

    def test_csv_missing_a_proposal_row(self):
        self.assert_fails([('reviewed', 'csv', csv_report(csv_rows('reviewed')[:3]))], 'csv.items')

    def test_csv_row_for_an_unknown_code(self):
        rows = csv_rows('reviewed') + [dict(csv_rows('reviewed')[2], code='45390')]
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.items')

    def test_ragged_csv(self):
        text = csv_report(csv_rows('reviewed')) + '"reviewed","approved"\r\n'
        self.assert_fails([('reviewed', 'csv', text)], 'csv.parse')

    def test_csv_without_an_item_list_column(self):
        header = [('state' if c == 'item_list' else c) for c in CSV_HEADER]
        rows = [{('state' if k == 'item_list' else k): v for k, v in r.items()} for r in csv_rows('reviewed')]
        self.assert_fails([('reviewed', 'csv', csv_report(rows, header))], 'csv.parse')

    def test_csv_report_kind_must_match_the_request(self):
        self.assert_fails([('reviewed', 'csv', csv_report(csv_rows('draft')))], 'csv.kind')

    def test_csv_constants_must_name_this_encounter_and_revision(self):
        rows = csv_rows('reviewed')
        rows[2]['encounter_id'] = 'enc-2'
        rows[0]['text_sha256'] = '0' * 64
        self.assert_fails([('reviewed', 'csv', csv_report(rows))], 'csv.encounter_id', 'csv.text_sha256')

    def test_missing_download_file(self):
        def remove(ws):
            (ws.dir / ws.evidence['documents'][0]['downloads'][0]['path']).unlink()
        self.assert_fails([('draft', 'txt', txt_report('draft'))], 'file', mutate=remove)

    def test_recorded_decision_that_did_not_persist(self):
        decisions = [{'proposal_id': 'p-biopsy', 'code': '45380', 'action': 'approve', 'http_status': 201}]
        self.assert_fails([('draft', 'txt', txt_report('draft'))], 'decisions.persisted', decisions=decisions)

    def test_api_span_claimed_exact_but_not_equal_to_the_text(self):
        proposals = base_proposals()
        proposals[0]['evidence'][0]['text'] = 'Cold snare polypectomy of three polyps.'
        self.assert_fails([('draft', 'txt', txt_report('draft'))], 'api.evidence.exact',
                          'api.ready_has_exact_evidence', snapshot=api(proposals))

    def test_snapshot_for_another_encounter(self):
        snapshot = api()
        snapshot['id'] = 'enc-2'
        self.assert_fails([('draft', 'txt', txt_report('draft'))], 'api.snapshot.encounter', snapshot=snapshot)


class IncompleteTests(unittest.TestCase):
    def test_no_api_snapshot_fails_closed_with_status_two(self):
        code, results = Workspace([('draft', 'txt', txt_report('draft'))], snapshot={}).run()
        self.assertEqual(code, 2)
        self.assertEqual(statuses(results, 'api.snapshot'), ['incomplete'])

    def test_report_missing_from_the_api_listing_is_incomplete(self):
        code, results = Workspace([('draft', 'txt', txt_report('draft'))], list_reports=False).run()
        self.assertEqual(code, 2)
        self.assertEqual(statuses(results, 'sha256.listing'), ['incomplete'])

    def test_no_downloads_is_incomplete(self):
        code, _ = Workspace([]).run()
        self.assertEqual(code, 2)


class UnitTests(unittest.TestCase):
    def test_code_tokens_ignore_ids_hashes_offsets_and_quoted_passages(self):
        text = ('45385 units 1 SYN-GI-12345 2026-10-23 ' + 'a' * 64 + ' 11111111-1111-4111-8111-111111111111 '
                '0398T 45378-53 [chars 10234–10290] [10234-10290, p1] "biopsy at 12345 cm"')
        self.assertEqual(vd.code_tokens(text, ['biopsy at 12345 cm']), {'45385', '0398T', '45378'})

    def test_neutralisation_is_undone_only_for_formula_characters(self):
        self.assertEqual(vd.undo_neutralisation("'=1+1"), '=1+1')
        self.assertEqual(vd.undo_neutralisation("'＝1"), '＝1')
        self.assertEqual(vd.undo_neutralisation("'quoted"), "'quoted")
        self.assertEqual(vd.undo_neutralisation("'"), "'")

    def test_item_list_normalisation(self):
        self.assertEqual(vd.norm_list(' Alternatives '), 'alternative')
        self.assertEqual(vd.norm_list('approved'), 'approved')

    def test_expected_list_mirrors_the_report_rules(self):
        approve = {'action': 'approve'}
        self.assertEqual(vd.expected_list({'bucket': 'selected', 'decision': approve}, 'reviewed'), 'approved')
        self.assertEqual(vd.expected_list({'bucket': 'selected', 'decision': approve}, 'draft'), 'undecided')
        self.assertEqual(vd.expected_list({'bucket': 'selected', 'decision': {'action': 'reject'}}, 'draft'),
                         'rejected')
        self.assertEqual(vd.expected_list({'bucket': 'selected', 'decision': None}, 'draft'), 'undecided')
        self.assertEqual(vd.expected_list({'bucket': 'excluded', 'decision': None}, 'reviewed'), 'excluded')
        self.assertEqual(vd.expected_list({'bucket': 'excluded', 'decision': {'action': 'reinstate'}}, 'draft'),
                         'undecided')
        self.assertEqual(vd.expected_list({'bucket': 'alternative', 'decision': approve}, 'reviewed'), 'alternative')

    def test_code_point_slice_rejects_bad_offsets(self):
        self.assertEqual(vd.cp_slice('a\U0001F600b', 1, 2), '\U0001F600')
        for start, end in ((2, 1), (-1, 2), (0, 99), ('0', 1), (True, 2), (1, 1)):
            self.assertIsNone(vd.cp_slice('abc', start, end))

    def test_header_block_stops_at_the_first_blank_line(self):
        self.assertEqual(vd.header_block('\nA\nB\n\nC DRAFT\n'), 'A\nB')

    def test_exit_status_orders_fail_over_incomplete(self):
        R = vd.Result
        self.assertEqual(vd.exit_status([R('a', '-', 'c', 'pass'), R('a', '-', 'c', 'warn')]), 0)
        self.assertEqual(vd.exit_status([R('a', '-', 'c', 'incomplete')]), 2)
        self.assertEqual(vd.exit_status([R('a', '-', 'c', 'incomplete'), R('a', '-', 'c', 'fail')]), 1)


if __name__ == '__main__':
    unittest.main()


HUMAN = 'Reviewer One'


def with_history(doc, reinstated=None):
    """doc['decisions']['history'] as the API carries it, in sequence order: a reinstate before the decision it led to."""
    entries = []
    for p in doc['assessment']['proposals']:
        if p['id'] in (reinstated or {}):
            reviewer, kind = reinstated[p['id']]
            entries.append({'id': f'r-{p["id"]}', 'proposal_id': p['id'], 'code': p['code'], 'action': 'reinstate',
                            'reviewer': reviewer, 'reviewer_kind': kind, 'carried_from': None, 'invalidated': None})
        if p.get('decision'):
            entries.append({'carried_from': None, **p['decision'], 'invalidated': None})
    doc['decisions'] = {'history': entries}
    return doc


def human(p, action):
    p['decision'] = {'id': f'd-{p["id"]}', 'proposal_id': p['id'], 'code': p['code'], 'action': action,
                     'reviewer': HUMAN, 'reviewer_kind': 'human', 'created_at': '2026-10-23T21:00:00+00:00'}
    p['decision_state'] = {'approve': 'approved', 'reject': 'rejected'}[action]
    return p


class Round2VerifierTests(unittest.TestCase):
    """Refutation round 2 over the verifier (review:2, review:4, review:5)."""

    def test_a_numbered_line_inside_a_note_is_not_an_item(self):
        def note_with_numbered_line(lines):
            at = lines.index('APPROVED SELECTIONS') + 2
            return lines[:at] + ['     Note: as discussed', '         2. 45380 · Colonoscopy · units 1'] + lines[at:]
        _, results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=note_with_numbered_line))]).run()
        self.assertEqual(statuses(results, 'approved.codes'), ['pass'])

    def test_a_placeholder_row_carries_nothing_but_the_files_identity(self):
        identity = {'report_kind': 'draft', 'encounter_id': 'enc-1', 'revision_number': '1', 'text_sha256': TEXT_SHA,
                    'assessment_id': 'asm-1', 'item_list': 'none', 'synthetic': 'SYNTHETIC — NOT FOR BILLING'}
        clean = Workspace([('draft', 'csv', csv_report([identity]))], snapshot=api([]), decisions=[]).run()[1]
        self.assertEqual(statuses(clean, 'csv.placeholder'), ['pass'])
        forged = {**identity, 'code': '45385', 'decision': 'approve', 'reviewer': AGENT, 'evidence': '"x" [0-1]'}
        results = Workspace([('draft', 'csv', csv_report([forged]))], snapshot=api([]), decisions=[]).run()[1]
        self.assertEqual(statuses(results, 'csv.placeholder'), ['fail'])

    def test_an_agent_reinstatement_needs_the_agent_label_and_the_named_reinstater(self):
        proposals = base_proposals()
        human(proposals[0], 'approve'); human(proposals[1], 'reject'); human(proposals[3], 'approve')
        proposals[3]['reinstated_by'] = {'reviewer': 'Reviewbot (automated agent)', 'reviewer_kind': 'agent'}
        decisions = [{'proposal_id': p['id'], 'code': p['code'], 'action': p['decision']['action'], 'http_status': 201}
                     for p in proposals if p['decision']]
        snapshot = with_history(api(proposals), reinstated={'p-egd': ('Reviewbot (automated agent)', 'agent')})
        bare = txt_report('reviewed', proposals, agent_line=False, reviewer=HUMAN)
        results = Workspace([('reviewed', 'txt', bare)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertIn('reviewer.agent_label', failed(results))
        self.assertIn('reviewer.reinstated_by.43239', failed(results))

        def named(lines):
            at = next(i for i, line in enumerate(lines) if line.startswith('  2. 43239')) + 1
            return lines[:at] + ['     Reinstated from exclusion by Reviewbot (automated agent) at 2026-10-23T21:00:00Z: '
                                 'planned'] + lines[at:]
        labelled = txt_report('reviewed', proposals, agent_line=True, reviewer=HUMAN, mutate_lines=named)
        results = Workspace([('reviewed', 'txt', labelled)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(statuses(results, 'reviewer.agent_label'), ['pass'])
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.43239'), ['pass'])


AGENT_R = 'Reviewbot (automated agent)'


def reinstated_block(code, reviewer=AGENT_R):
    """Insert the renderer's reinstater line right under a code's item line."""
    def mutate(lines):
        at = next(i for i, line in enumerate(lines) if re.match(rf'^  \d+\. {code} · ', line)) + 1
        who = f'by {reviewer} at 2026-10-23T21:00:00Z' if reviewer else 'by a reviewer'
        return lines[:at] + [f'     Reinstated from exclusion {who}: planned'] + lines[at:]
    return mutate


def doc_with(text, proposals):
    """An encounter JSON over a custom revision text (for passages TEXT does not hold)."""
    doc = api(proposals)
    doc['revision'] = {**doc['revision'], 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
    return doc


def span_in(text, passage, page=1):
    start = text.index(passage)
    return {'context_index': 0, 'start': start, 'end': start + len(passage), 'text': passage, 'exact': True,
            'page': page}


class Round3VerifierTests(unittest.TestCase):
    """Refutation round 3 over the round-2 verifier repairs (review3:0-4, evidence:5, 6, 9)."""

    def agent_reinstated(self, *excluded_codes, then='approve'):
        """base proposals, where each listed excluded code was reinstated by the agent and then decided by a human."""
        proposals = base_proposals()
        human(proposals[0], 'approve')
        human(proposals[1], 'reject')
        extra = []
        for n, code in enumerate(excluded_codes):
            p = proposals[3] if n == 0 else proposal(f'p-ex{n}', code, 'excluded', 'excluded', PLANNED)
            human(p, then)
            p['reinstated_by'] = {'reviewer': AGENT_R, 'reviewer_kind': 'agent'}
            if n:
                extra.append(p)
        proposals += extra
        reinstated = {p['id']: (AGENT_R, 'agent') for p in proposals if p.get('reinstated_by')}
        return proposals, with_history(api(proposals), reinstated=reinstated)

    def test_a_forged_item_at_any_shallow_column_is_counted(self):
        # review3:2 — only column 2 used to count, so a rejected code itemised at another indent passed.
        for indent in (0, 1, 3, 4, 5, 6):
            def forge(lines, indent=indent):
                at = lines.index('APPROVED SELECTIONS') + 1
                return lines[:at] + [' ' * indent + '2. 45380 · Colonoscopy · units 1'] + lines[at:]
            with self.subTest(indent=indent):
                results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=forge))]).run()[1]
                self.assertEqual(statuses(results, 'approved.codes'), ['fail'])

    def test_a_forged_item_with_any_marker_is_counted(self):
        # orchestrator:3 — only '2.' and '-', '*', '•' counted, so a rejected code itemised in APPROVED SELECTIONS
        # as '2)', '(2)', '#2', '+', '‣', '–' (or with no marker) passed with only a warning.
        for marker in ('2) ', '(2) ', '#2 ', '+ ', '‣ ', '– ', '2.) ', 'ii. ', 'b) ', ''):
            def forge(lines, marker=marker):
                at = lines.index('APPROVED SELECTIONS') + 1
                return lines[:at] + ['  ' + marker + '45380 · Colonoscopy · units 1'] + lines[at:]
            with self.subTest(marker=marker):
                results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=forge))]).run()[1]
                self.assertEqual(statuses(results, 'approved.codes'), ['fail'])

    def test_a_note_at_the_renderers_continuation_depth_is_not_an_item(self):
        # evidence:9 — the renderer continues a note at column 7 (reports.CONTINUATION), not 9.
        def note(lines):
            at = lines.index('APPROVED SELECTIONS') + 2
            return lines[:at] + ['     Note: Checked against the pathology report:', '       1. 45385 benign',
                                 '       2. 45380 sigmoid polyp, not removed'] + lines[at:]
        results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=note))]).run()[1]
        self.assertEqual(statuses(results, 'approved.codes'), ['pass'])

    def test_a_reinstated_code_that_was_then_rejected_passes(self):
        # review3:0 — the renderer never names the reinstater of a rejected code; its own files must pass.
        proposals, snapshot = self.agent_reinstated('43239', then='reject')
        files = [('draft', 'txt', txt_report('draft', proposals, reviewer=HUMAN)),
                 ('reviewed', 'txt', txt_report('reviewed', proposals, reviewer=HUMAN))]
        decisions = [{'proposal_id': p['id'], 'code': p['code'], 'action': p['decision']['action'], 'http_status': 201}
                     for p in proposals if p['decision']]
        code, results = Workspace(files, snapshot=snapshot, decisions=decisions).run()
        self.assertEqual([r for r in results if r['check'].startswith('reviewer.') and r['status'] == 'fail'], [])
        self.assertEqual(statuses(results, 'reviewer.agent_label'), ['pass', 'pass'])

    def test_the_reinstater_must_be_named_in_its_own_block(self):
        # review3:4 — with two codes reinstated by the same agent, naming one used to satisfy both.
        proposals, snapshot = self.agent_reinstated('43239', '45388')
        decisions = [{'proposal_id': p['id'], 'code': p['code'], 'action': p['decision']['action'], 'http_status': 201}
                     for p in proposals if p['decision']]
        one_named = txt_report('reviewed', proposals, reviewer=HUMAN, mutate_lines=lambda lines: reinstated_block(
            '45388', reviewer=None)(reinstated_block('43239')(lines)))
        results = Workspace([('reviewed', 'txt', one_named)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.43239'), ['pass'])
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.45388'), ['fail'])
        both = txt_report('reviewed', proposals, reviewer=HUMAN, mutate_lines=lambda lines: reinstated_block(
            '45388')(reinstated_block('43239')(lines)))
        results = Workspace([('reviewed', 'txt', both)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.45388'), ['pass'])

    def test_the_agent_named_elsewhere_does_not_name_the_reinstater(self):
        # evidence:6 — an audit line naming the agent must not satisfy an item block that says 'by a reviewer'.
        proposals, snapshot = self.agent_reinstated('43239')
        decisions = [{'proposal_id': p['id'], 'code': p['code'], 'action': p['decision']['action'], 'http_status': 201}
                     for p in proposals if p['decision']]

        def audit_but_unnamed(lines):
            lines = reinstated_block('43239', reviewer=None)(lines)
            at = lines.index('NOT VERIFIED')
            return lines[:at] + ['AUDIT — DECISION HISTORY', f'  - 2026-10-23T21:00:00Z · 43239 · reinstate · {AGENT_R}'
                                 ' · revision 1 · this assessment', ''] + lines[at:]
        text = txt_report('reviewed', proposals, reviewer=HUMAN, mutate_lines=audit_but_unnamed)
        results = Workspace([('reviewed', 'txt', text)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(statuses(results, 'reviewer.agent_label'), ['pass'])
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.43239'), ['fail'])

    def test_a_carried_reinstatement_is_derived_from_history(self):
        # evidence:5 — the reinstater is found in decisions.history through the carry, and the JSON's own
        # proposal.reinstated_by must agree with it.
        proposals = base_proposals()
        human(proposals[0], 'approve')
        human(proposals[1], 'reject')
        egd = human(proposals[3], 'approve')
        egd['decision']['carried_from'] = 'a-old'
        egd['reinstated_by'] = {'reviewer': AGENT_R, 'reviewer_kind': 'agent'}
        snapshot = api(proposals)
        snapshot['decisions'] = {'history': [
            {'id': 'r-old', 'proposal_id': 'p-old', 'code': '43239', 'action': 'reinstate', 'reviewer': AGENT_R,
             'reviewer_kind': 'agent', 'carried_from': None, 'invalidated': None},
            {'id': 'a-old', 'proposal_id': 'p-old', 'code': '43239', 'action': 'approve', 'reviewer': HUMAN,
             'reviewer_kind': 'human', 'carried_from': None, 'invalidated': None},
            *[{'carried_from': None, **p['decision'], 'invalidated': None} for p in proposals if p['decision']]]}
        decisions = [{'proposal_id': p['id'], 'code': p['code'], 'action': p['decision']['action'], 'http_status': 201}
                     for p in proposals if p['decision']]
        named = txt_report('reviewed', proposals, reviewer=HUMAN, mutate_lines=reinstated_block('43239'))
        results = Workspace([('reviewed', 'txt', named)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(failed(results), [])
        unnamed = txt_report('reviewed', proposals, reviewer=HUMAN, mutate_lines=reinstated_block('43239', None))
        results = Workspace([('reviewed', 'txt', unnamed)], snapshot=snapshot, decisions=decisions).run()[1]
        self.assertEqual(statuses(results, 'reviewer.reinstated_by.43239'), ['fail'])
        lost = copy.deepcopy(snapshot)
        next(p for p in lost['assessment']['proposals'] if p['id'] == 'p-egd')['reinstated_by'] = None
        results = Workspace([('reviewed', 'txt', unnamed)], snapshot=lost, decisions=decisions).run()[1]
        self.assertIn('reviewer.reinstated_by.consistent', failed(results))
        self.assertIn('reviewer.reinstated_by.43239', failed(results))

    def test_offsets_are_read_only_at_evidence_positions(self):
        # review3:3 — stored text that looks like an offset pair never fails a genuine file.
        def note(lines):
            at = lines.index('APPROVED SELECTIONS') + 2
            return lines[:at] + ['     Note: Matches the procedure line [chars 10–20].'] + lines[at:]
        results = Workspace([('reviewed', 'txt', txt_report('reviewed', mutate_lines=note))]).run()[1]
        self.assertEqual(statuses(results, 'evidence.offsets'), ['pass'])
        text = TEXT + 'Cold forceps biopsies [2-3] were taken from the gastric antrum.\n'
        passage = 'Cold forceps biopsies [2-3] were taken from the gastric antrum.'
        proposals = base_proposals()
        proposals[0]['evidence'] = [span_in(text, passage)]
        rows = csv_rows('reviewed', proposals)
        results = Workspace([('reviewed', 'csv', csv_report(rows))], snapshot=doc_with(text, proposals)).run()[1]
        self.assertEqual(statuses(results, 'csv.evidence.offsets'), ['pass'])
        shifted = [{**row, 'evidence': row['evidence'].replace(f'[{span_in(text, passage)["start"]}-',
                                                               f'[{span_in(text, passage)["start"] + 1}-')}
                   for row in rows]
        results = Workspace([('reviewed', 'csv', csv_report(shifted))], snapshot=doc_with(text, proposals)).run()[1]
        self.assertEqual(statuses(results, 'csv.evidence.offsets'), ['fail'])

    def test_passages_are_compared_as_the_renderer_prints_them(self):
        # review3:1 — the TXT shows C0/DEL/C1 controls as \xNN; so does the CSV now (review3:5).
        passage = 'Total time on the date of the patient\x92s encounter was 24\x1b[1G minutes.'
        text = TEXT + passage + '\n'
        proposals = base_proposals()
        proposals[0]['evidence'] = [span_in(text, passage)]
        shown = passage.replace('\x92', '\\x92').replace('\x1b', '\\x1b')

        def as_rendered(lines):
            return [line.replace(passage, shown) for line in lines]
        doc = doc_with(text, proposals)
        genuine = txt_report('reviewed', proposals, mutate_lines=as_rendered)
        rows = [{**row, 'evidence': row['evidence'].replace(passage, shown)} for row in csv_rows('reviewed', proposals)]
        results = Workspace([('reviewed', 'txt', genuine), ('reviewed', 'csv', csv_report(rows))], snapshot=doc).run()[1]
        self.assertEqual([r for r in results if r['check'].startswith(('evidence.', 'csv.evidence'))
                          and r['status'] != 'pass'], [])
        raw = txt_report('reviewed', proposals)  # the raw control characters, as no genuine file prints them
        results = Workspace([('reviewed', 'txt', raw)], snapshot=doc).run()[1]
        self.assertIn('evidence.present', failed(results))
