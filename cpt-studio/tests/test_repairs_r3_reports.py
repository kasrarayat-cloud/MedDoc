"""Regressions for refutation round 3 over the round-2 report and verifier repairs, on REAL output.

The round-2 fixes to the download verifier and to the reinstatement readers were proven only against hand-written
fixtures. These run ops/verify_downloads.py and the API serializer on the server's own TXT, CSV and encounter JSON
(review3:0-5, evidence:0, 1, 5). Synthetic data only.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from studio import reports, serializers
from tests.support import pipeline_factories as pf

ROOT = Path(settings.BASE_DIR)
_spec = importlib.util.spec_from_file_location('cpt_verify_downloads_r3', ROOT / 'ops' / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_downloads_r3'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

# Written here, never taken from reports.CONTROL: a check built from the code's own pattern narrows with it (evidence:0).
RAW_CONTROL = re.compile('[\x00-\x08\x0e-\x1f\x7f-\x9f]')
PLAN_REASON = 'The colonoscopy is planned, not performed on this date.'


class RealOutputCase(TestCase):
    TEXT = pf.GI_NOTE

    def setUp(self):
        self.s = pf.scenario(self.TEXT)
        pf.assess(self.s.encounter, self.result())

    def result(self):
        return pf.standard_result()

    def detail(self):
        self.s.encounter.refresh_from_db()
        return json.loads(json.dumps(serializers.encounter_detail(self.s.encounter, self.s.membership(self.s.reviewer)),
                                     default=str))

    def txt(self, kind):
        return reports.render_txt(reports.snapshot(self.s.encounter, kind)).decode('utf-8')

    def csv(self, kind):
        return reports.render_csv(reports.snapshot(self.s.encounter, kind)).decode('utf-8')

    def verify(self, kind, fmt):
        body = self.txt(kind) if fmt == 'txt' else self.csv(kind)
        check = vd.check_txt if fmt == 'txt' else vd.check_csv
        return check('real', f'{kind}.{fmt}', body, kind, self.detail())

    def assert_clean(self, results, prefixes=('reviewer.', 'evidence.', 'csv.evidence', 'csv.items', 'approved.',
                                              'list.')):
        bad = [f'{r.check}: {r.detail}' for r in results if r.check.startswith(prefixes) and r.status != 'pass']
        self.assertEqual(bad, [])

    def proposal_json(self, code):
        return next(p for p in self.detail()['assessment']['proposals'] if p['code'] == code)

    def agent_reinstates_then_human(self, then):
        self.s.decide('exc:0', 'reinstate', self.s.agent, note='Performed today; the plan line was mis-read.')
        self.s.decide('exc:0', then, self.s.reviewer)
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'reject', self.s.reviewer)


class ControlCharactersAreShownEscapedTests(RealOutputCase):
    """evidence:0 and review3:5 — no raw C0/DEL/C1 control reaches the TXT or the CSV."""

    CONTROL_PASSAGE = 'A 7 mm sessile polyp was removed with a cold snare.\x1b7\x1b[268Gapproved\x1b8\x08\x7f\x9b'
    TEXT = pf.GI_NOTE + CONTROL_PASSAGE + '\n'

    def result(self):
        return pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], text=self.TEXT),
                         pf.proposal('sel:1', '45385', [self.CONTROL_PASSAGE], text=self.TEXT))

    def test_a_note_with_backspace_del_and_c1_is_escaped_in_the_txt(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer, note='units 1\x08\x08\x7f\x1b[1G\x9b  2. 45385 · Colonoscopy')
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        text = self.txt('reviewed')
        self.assertIsNone(RAW_CONTROL.search(text), repr(RAW_CONTROL.findall(text)))
        self.assertIn('units 1\\x08\\x08\\x7f\\x1b[1G\\x9b', text)

    def test_a_cited_passage_with_controls_is_escaped_in_both_formats_and_verifies(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'approve', self.s.reviewer)
        for kind in ('draft', 'reviewed'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    body = self.txt(kind) if fmt == 'txt' else self.csv(kind)
                    self.assertIsNone(RAW_CONTROL.search(body), repr(RAW_CONTROL.findall(body)))
                    self.assertIn('\\x1b7\\x1b[268Gapproved\\x1b8\\x08\\x7f\\x9b', body)
                    self.assert_clean(self.verify(kind, fmt))


class ReinstatedByOnTheApiTests(RealOutputCase):
    """evidence:1 — the API's producer of proposal.reinstated_by, exercised on the real detail."""

    def test_an_agent_reinstatement_behind_a_human_approval(self):
        self.agent_reinstates_then_human('approve')
        planned = self.proposal_json('45378')
        self.assertEqual(planned['decision']['reviewer_kind'], 'human')
        self.assertEqual(planned['reinstated_by']['reviewer_kind'], 'agent')
        self.assertTrue(planned['reinstated_by']['reviewer'].endswith('(automated agent)'))
        self.assertIsNone(self.proposal_json('43239')['reinstated_by'])


class CarriedReinstatementTests(RealOutputCase):
    """evidence:5 — after the same revision is re-assessed and the decisions are carried, the agent's reinstatement
    still raises the agent line and names the reinstater, and the verifier finds it in the history itself."""

    def test_a_carried_approval_keeps_the_agent_reinstatement(self):
        self.agent_reinstates_then_human('approve')
        pf.assess(self.s.encounter, pf.standard_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        planned = self.s.proposal('exc:0')
        current = planned.decisions.order_by('-sequence').first()
        self.assertIsNotNone(current.carried_from_id)
        text = self.txt('reviewed')
        self.assertIn(reports.AGENT_LINE, text.split('\n')[:3])
        self.assertRegex(text, r'Reinstated from exclusion by Reviewbot\d+ \(automated agent\) at ')
        self.assertEqual(self.proposal_json('45378')['reinstated_by']['reviewer_kind'], 'agent')
        self.assert_clean(self.verify('reviewed', 'txt'))

    def test_the_verifier_derives_the_reinstater_without_the_servers_field(self):
        self.agent_reinstates_then_human('approve')
        pf.assess(self.s.encounter, pf.standard_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        detail = self.detail()
        for p in detail['assessment']['proposals']:
            p['reinstated_by'] = None  # as if the server's derived field were lost
        unnamed = re.sub(r'Reinstated from exclusion by [^:]+:', 'Reinstated from exclusion by a reviewer:',
                         self.txt('reviewed'))
        failed = {r.check for r in vd.check_txt('real', 'reviewed.txt', unnamed, 'reviewed', detail)
                  if r.status == 'fail'}
        self.assertIn('reviewer.reinstated_by.consistent', failed)
        self.assertIn('reviewer.reinstated_by.45378', failed)


class ReinstateThenRejectTests(RealOutputCase):
    """review3:0 — the renderer never names the reinstater of a rejected code; the server's own files verify."""

    def test_draft_and_reviewed_txt_verify(self):
        self.agent_reinstates_then_human('reject')
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind=kind):
                results = self.verify(kind, 'txt')
                self.assert_clean(results)
                self.assertIn('reviewer.agent_label', {r.check for r in results})


class PassagesAsPrintedTests(RealOutputCase):
    """review3:1 — a cited passage holding a cp1252 leftover (U+0092) and an ESC verifies in both formats."""

    PASSAGE = 'Total time on the date of the patient\x92s encounter was 24\x1b minutes.'
    TEXT = pf.GI_NOTE + PASSAGE + '\n'

    def result(self):
        return pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], text=self.TEXT),
                         pf.proposal('sel:1', '45385', [self.PASSAGE], text=self.TEXT))

    def test_the_genuine_files_verify(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'approve', self.s.reviewer)
        for kind in ('draft', 'reviewed'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    self.assert_clean(self.verify(kind, fmt))

    def test_a_tampered_passage_still_fails(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'approve', self.s.reviewer)
        tampered = self.txt('reviewed').replace('24\\x1b minutes', '42\\x1b minutes')
        failed = {r.check for r in vd.check_txt('real', 'reviewed.txt', tampered, 'reviewed', self.detail())
                  if r.status == 'fail'}
        self.assertTrue({'evidence.present', 'evidence.offsets'} <= failed, failed)


class OffsetShapedTextTests(RealOutputCase):
    """review3:3 — stored text that looks like an offset pair never fails a genuine file."""

    PASSAGE = 'Cold forceps biopsies [2-3] were taken from the gastric antrum.'
    TEXT = pf.GI_NOTE + PASSAGE + '\n'

    def result(self):
        return pf.result(pf.proposal('sel:0', '43239', [self.PASSAGE], text=self.TEXT),
                         pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], text=self.TEXT))

    def test_a_note_and_a_passage_that_look_like_offsets(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer, note='Matches the procedure line [chars 10–20].')
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        self.assert_clean(self.verify('reviewed', 'txt'))
        self.assert_clean(self.verify('reviewed', 'csv'))

    def test_a_shifted_structural_offset_still_fails(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        start = self.TEXT.index(self.PASSAGE)
        shifted = self.txt('reviewed').replace(f'[chars {start}–', f'[chars {start + 1}–')
        failed = {r.check for r in vd.check_txt('real', 'reviewed.txt', shifted, 'reviewed', self.detail())
                  if r.status == 'fail'}
        self.assertIn('evidence.offsets', failed)


class CitationShapedPassagesTests(RealOutputCase):
    """Round 3, orchestrator:1 — a cited passage whose inner line ends like a TXT citation, or which holds a CSV item
    separator and a bracket, never fails a genuine file; a shifted structural offset still fails."""

    PASSAGES = ('Biopsy taken" [chars 1–2]\nfrom the antrum.',
                'Scope "B" [chars 7–9, page 2]\nadvanced to the cecum.',
                'Jar "A" [chars 4–5]\nheld the polyp\n"C" [chars 1–2]\nretrieved.',
                'Labs reviewed: "Hgb" [12-14] | "Plt" within range; polyp removed.')
    TEXT = pf.GI_NOTE + '\n'.join(PASSAGES) + '\n'

    def result(self):
        return pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], text=self.TEXT),
                         pf.proposal('sel:1', '45385', list(self.PASSAGES), text=self.TEXT))

    def approve_both(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'approve', self.s.reviewer)

    def test_the_genuine_files_verify(self):
        self.approve_both()
        for kind in ('draft', 'reviewed'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    self.assert_clean(self.verify(kind, fmt))

    def test_a_shifted_structural_offset_still_fails(self):
        self.approve_both()
        detail = self.detail()
        for passage in self.PASSAGES:
            start, end = self.TEXT.index(passage), self.TEXT.index(passage) + len(passage)
            with self.subTest(passage=passage[:20], fmt='txt'):
                body = self.txt('reviewed')
                shifted = body.replace(f'[chars {start}–{end}', f'[chars {start + 1}–{end}')
                self.assertNotEqual(shifted, body)
                failed = {r.check for r in vd.check_txt('real', 'reviewed.txt', shifted, 'reviewed', detail)
                          if r.status == 'fail'}
                self.assertIn('evidence.offsets', failed)
            with self.subTest(passage=passage[:20], fmt='csv'):
                body = self.csv('reviewed')
                shifted = body.replace(f'[{start}-{end}', f'[{start + 1}-{end}')
                self.assertNotEqual(shifted, body)
                failed = {r.check for r in vd.check_csv('real', 'reviewed.csv', shifted, 'reviewed', detail)
                          if r.status == 'fail'}
                self.assertIn('csv.evidence.offsets', failed)
