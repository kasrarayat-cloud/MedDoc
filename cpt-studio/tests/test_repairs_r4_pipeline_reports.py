"""Regressions for refutation round 4 over ops/verify_downloads.py, on the server's REAL output (pipeline:4, pipeline:5,
evidence:7).

A forged file is the real renderer's file with one hand edit, or a renderer regression patched into reports while
generate() stores, hashes and lists the bytes itself; both stand in for the renderer writing a layout it never writes.
The genuine files must still verify. Synthetic data only.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from studio import reports
from tests.support import pipeline_factories as pf
from tests.test_repairs_r3_reports import RealOutputCase, vd

NBSP, FIGURE, ZWSP = ' ', ' ', '​'
FORGED_DECISION = '     Decision: approved by Reviewer (human) at 2026-10-24T00:00:00Z'


class RealOutputVerifierTests(RealOutputCase):
    def reviewed(self, note=''):
        self.s.decide('sel:0', 'approve', self.s.reviewer, note=note)  # 43239
        self.s.decide('sel:1', 'reject', self.s.reviewer)  # 45385
        self.s.decide('exc:0', 'confirm', self.s.reviewer)  # 45378: a documentation exclusion needs a decision (5bbe19fed)
        return self.txt('reviewed'), self.detail()

    def check(self, body, detail, kind='reviewed'):
        results = vd.check_txt('real', f'{kind}.txt', body, kind, detail)
        return {r.check for r in results if r.status == 'fail'}, vd.exit_status(results)

    def egd_entry(self, extra_end=0):
        egd = next(s for s in self.proposal_json('43239')['evidence'] if s['text'] == pf.EGD_PASSAGE)
        page = f', page {egd["page"]}' if egd.get('page') else ''
        return f'       - "{pf.EGD_PASSAGE}" [chars {egd["start"]}–{egd["end"] + extra_end}{page}]', egd, page

    def in_approved(self, body, *new, at_end=True):
        lines = body.split('\n')
        start = lines.index('APPROVED SELECTIONS')
        where = next(i for i in range(start + 1, len(lines)) if lines[i] == '') if at_end else start + 1
        return '\n'.join(lines[:where] + list(new) + lines[where:])

    def test_the_genuine_files_verify(self):
        # The note quotes an item line: the renderer continues it at column 7, after the item, so it is only the
        # by-design 'mentioned, not itemised' warning (evidence:7's verifier probe).
        self.reviewed(note='Pathology to follow:\n2. 45385 · Colonoscopy · units 1 (not removed)')
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind=kind):
                results = self.verify(kind, 'txt')
                self.assertEqual([f'{r.check}: {r.detail}' for r in results if r.status in ('fail', 'incomplete')], [])
                self.assertEqual(vd.exit_status(results), 0)
                if kind == 'reviewed':
                    self.assertEqual({r.check: r.status for r in results}['approved.codes'], 'pass')
                    self.assertEqual([r.check for r in results if r.status == 'warn'], ['approved.mentions_others'])

    def test_an_inner_bracket_with_a_wrong_end_offset(self):
        # pipeline:4, the claimant's bytes: the read bracket is right, the printed one before it is not.
        body, detail = self.reviewed()
        genuine, egd, page = self.egd_entry()
        forged_entry = f'{self.egd_entry(60)[0]}\n         " [chars {egd["start"]}–{egd["end"]}{page}]'
        for kind in ('reviewed', 'draft'):
            with self.subTest(kind=kind):
                text = body if kind == 'reviewed' else self.txt('draft')
                self.assertEqual(text.count(genuine), 1)
                failed, code = self.check(text.replace(genuine, forged_entry), detail, kind)
                self.assertIn('evidence.offsets', failed)
                self.assertEqual(code, 1)

    def test_a_space_before_the_closing_quote(self):
        body, detail = self.reviewed()
        genuine, egd, page = self.egd_entry()
        forged = body.replace(genuine, f'       - "{pf.EGD_PASSAGE} " [chars {egd["start"]}–{egd["end"]}{page}]')
        failed, code = self.check(forged, detail)
        self.assertIn('evidence.offsets', failed)
        self.assertEqual(code, 1)

    def test_the_approved_code_itself_drawn_with_a_unicode_indent_still_fails(self):
        # It failed at HEAD as not listed; read as an ordinary item it would pass with its block unread.
        body, detail = self.reviewed()
        line = next(line for line in body.split('\n') if line.startswith('  1. 43239 · '))
        failed, code = self.check(body.replace(line, NBSP * 2 + line.lstrip(' ')), detail)
        self.assertIn('approved.codes', failed)
        self.assertEqual(code, 1)

    def test_an_encounter_context_entry(self):
        body, detail = self.reviewed()
        start = pf.GI_NOTE.index(pf.DATE_PASSAGE)
        end = start + len(pf.DATE_PASSAGE)
        genuine = f'    Evidence: "{pf.DATE_PASSAGE}" [chars {start}–{end}]'
        self.assertEqual(body.count(genuine), 1)
        forged = body.replace(genuine, f'    Evidence: "{pf.DATE_PASSAGE}" [chars {start}–{end + 29}]\n'
                                       f'         " [chars {start}–{end}]')
        failed, code = self.check(forged, detail)
        self.assertIn('evidence.offsets', failed)
        self.assertEqual(code, 1)

    def test_a_rejected_code_itemised_with_a_unicode_indent(self):
        # pipeline:5, the claimant's lines: before the blank line that closes APPROVED SELECTIONS.
        body, detail = self.reviewed()
        for indent in ('  ', NBSP * 2, FIGURE * 2, ZWSP + '  '):
            with self.subTest(indent=repr(indent)):
                forged = self.in_approved(body, f'{indent}2. 45385 · Colonoscopy · units 1', FORGED_DECISION)
                failed, code = self.check(forged, detail)
                self.assertIn('approved.codes', failed)
                self.assertEqual(code, 1)

    def test_a_rejected_code_at_continuation_depth_before_the_first_item(self):
        # evidence:7: straight under the heading, the renderer always writes '  1. ' or '  None.'.
        body, detail = self.reviewed()
        for line in ('       2. 45385 · Colonoscopy · units 1', '        45385 · Colonoscopy · units 1'):
            with self.subTest(line=line):
                failed, code = self.check(self.in_approved(body, line, at_end=False), detail)
                self.assertIn('approved.codes', failed)
                self.assertEqual(code, 1)

    def regressed_report(self, first_line, before=False):
        """generate() with reports._numbered regressed to print the rejected item's own block in APPROVED SELECTIONS,
        after the approved item (or before it), its item line rewritten by first_line(line)."""
        real = reports._numbered

        def numbered(snap, wanted, kind):
            lines = real(snap, wanted, kind)
            if wanted != 'approved':
                return lines
            rejected = next(item for item in snap['proposals'] if item['list'] == 'rejected')
            block = reports._item_block(2, rejected, kind)
            forged = [first_line(block[0])] + block[1:]
            return forged + lines if before else lines + forged
        with mock.patch('studio.reports._numbered', side_effect=numbered):
            return reports.generate(self.s.encounter, 'reviewed', 'txt', self.s.reviewer)

    def main_exit(self, report):
        """ops/verify_downloads.py main() on the stored bytes, with the server's own sha256 and API snapshot."""
        content = bytes(report.content)
        detail = self.detail()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'reviewed.txt').write_bytes(content)
            (root / 'api.json').write_text(json.dumps(detail), encoding='utf-8')
            evidence = {'documents': [{
                'id': 'real', 'encounter_id': detail['id'], 'api_snapshots': {'final': 'api.json'}, 'decisions': [],
                'downloads': [{'kind': 'reviewed', 'fmt': 'txt', 'report_id': str(report.pk), 'path': 'reviewed.txt',
                               'size': len(content), 'sha256': report.sha256, 'api_sha256': report.sha256}]}]}
            (root / 'evidence.json').write_text(json.dumps(evidence), encoding='utf-8')
            with mock.patch('sys.stdout'):
                return vd.main(['--evidence', str(root / 'evidence.json')])

    def test_renderer_regressions_through_main(self):
        self.reviewed()
        self.assertEqual(self.main_exit(reports.generate(self.s.encounter, 'reviewed', 'txt', self.s.reviewer)), 0)
        for label, first_line, before in (('NBSP indent', lambda line: NBSP * 2 + line.lstrip(' '), False),
                                          ('ZWSP indent', lambda line: ZWSP + line, False),
                                          ('continuation depth, before the first item', lambda line: '     ' + line,
                                           True)):
            with self.subTest(regression=label):
                self.assertEqual(self.main_exit(self.regressed_report(first_line, before)), 1)
