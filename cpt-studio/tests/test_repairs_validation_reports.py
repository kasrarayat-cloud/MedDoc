"""Regressions for the refutation pass over validation, review and reports (round 1).

Each test reproduces a confirmed finding's input and asserts the corrected
behaviour. Synthetic data only.
"""
import re
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import models, reports, review
from studio.gi.profiles import family_for_code
from studio.reference.store import InMemoryReferenceLookup
from studio.validation import checks
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE, ApiHarness
from tests.test_validation import (COLON, EGD, EGD_LABEL, EM, MUE_INFO, MUE_ROWS, PFS_INFO, PFS_ROWS, EngineCase, Note, finding,
                                   mention, pfs, selected, listed, visit_context)
from tests.test_reports import APPROVED, parse_csv, section

SILENT = ('uncertain', ('uncertain: no performance evidence in its sentence or section',))
HEDGED = ('uncertain', ('uncertain: if symptoms persist',))


class OwnEvidenceDecidesTests(EngineCase):
    """status:4 — a hedged passage of the code's own is never overridden by the family being performed."""

    NOTE = Note('Date of service: 2026-10-21', 'Procedure: Colonoscopy performed to the cecum.',
                'Plan: Repeat colonoscopy with biopsies if symptoms persist.')
    DONE = 'Procedure: Colonoscopy performed to the cecum.'
    PLAN = 'Plan: Repeat colonoscopy with biopsies if symptoms persist.'

    def run_case(self, reading):
        self.statuses = {self.PLAN: reading}
        found = finding(COLON, 'performed', mention(self.NOTE, COLON, 'performed', self.DONE, 'performed'),
                        facts={'extent': 'cecum'})
        return self.proposal(self.run_engine(self.NOTE, selected('45380', self.NOTE.span(self.PLAN)),
                                             findings=[found]), '45380')

    def test_hedged_own_evidence_holds_the_code(self):
        item = self.run_case(HEDGED)
        self.assertEqual(item.status, 'needs_clarification')
        self.assertEqual([c.fact for c in item.clarifications], ['performed_status'])
        self.assertEqual(self.check(item, 'service.status').status, 'warn')
        self.assertIn('if symptoms persist', item.clarifications[0].reason)

    def test_silent_own_evidence_lets_routing_decide(self):
        self.assertEqual(self.run_case(SILENT).status, 'ready')


class FamilyOfTheEvidenceTests(EngineCase):
    """status:5 — a positive passage about another service cannot establish the code's family."""

    NOTE = Note('Date of service: 2026-10-21', 'Procedure: EGD',
                'Findings: The endoscope was advanced to the second part of the duodenum. Normal EGD.',
                'Plan: Will schedule EUS for the pancreatic cyst.')
    ADVANCED = 'The endoscope was advanced to the second part of the duodenum.'
    PLANNED = 'Plan: Will schedule EUS for the pancreatic cyst.'

    def egd(self):
        return finding(EGD, 'performed', mention(self.NOTE, EGD, 'performed', 'Normal EGD.', 'performed'),
                       facts={'extent': 'second part of the duodenum'})

    def test_family_documented_only_as_planned_excludes_the_code(self):
        self.statuses = {self.ADVANCED: 'performed'}
        eus = finding('gi.eus', 'planned', mention(self.NOTE, 'gi.eus', 'planned', self.PLANNED, 'planned: will schedule'))
        item = self.proposal(self.run_engine(self.NOTE, selected('43259', self.NOTE.span(self.ADVANCED)),
                                             findings=[self.egd(), eus]), '43259')
        self.assertEqual(item.bucket, 'excluded')
        self.assertTrue(item.reinstatable)
        self.assertIn('Documented as planned', item.exclusion_reason)
        self.assertIn(self.ADVANCED, item.exclusion_reason)
        routing = self.check(item, 'routing.family')
        self.assertEqual(routing.status, 'warn')
        self.assertIn('only as planned', routing.detail)

    def test_family_the_document_never_names_is_held(self):
        self.statuses = {self.ADVANCED: 'performed'}
        item = self.proposal(self.run_engine(self.NOTE, selected('43259', self.NOTE.span(self.ADVANCED)),
                                             findings=[self.egd()]), '43259')
        self.assertEqual(item.status, 'needs_clarification')
        performed = [c for c in item.clarifications if c.fact == 'performed_status']
        self.assertEqual(len(performed), 1)
        self.assertIn('never names', performed[0].reason)

    def test_a_named_family_still_reads_performed(self):
        self.statuses = {self.ADVANCED: 'performed'}
        item = self.proposal(self.run_engine(self.NOTE, selected('43239', self.NOTE.span(self.ADVANCED)),
                                             findings=[self.egd()]), '43239')
        self.assertEqual(item.status, 'ready')


class SameDayProcedureTests(EngineCase):
    """status:10 — an E/M beside a same-day procedure outside the profiles is held like any other."""

    NOTE = Note('Date of service: 2026-10-21',
                'Office visit: established patient seen for rectal bleeding. Total time 32 minutes.',
                'Procedure: Rubber band ligation of an internal hemorrhoid was performed today.')
    VISIT = 'Office visit: established patient seen for rectal bleeding.'
    TIME = 'Total time 32 minutes.'
    BAND = 'Procedure: Rubber band ligation of an internal hemorrhoid was performed today.'

    def run_case(self, code, reference):
        self.statuses = {self.BAND: 'performed', self.TIME: None}
        visit = finding(EM, 'performed', mention(self.NOTE, EM, 'performed', self.VISIT, 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        result = self.run_engine(self.NOTE, selected('99214', self.NOTE.span(self.TIME)),
                                 selected(code, self.NOTE.span(self.BAND)), findings=[visit], ctx=visit_context(),
                                 reference=reference)
        return self.proposal(result, '99214')

    @staticmethod
    def reference(extra_pfs=None):
        return InMemoryReferenceLookup([PFS_INFO, MUE_INFO],
                                       {PFS_INFO.key: {**PFS_ROWS, **(extra_pfs or {})}, MUE_INFO.key: MUE_ROWS})

    def test_unprofiled_procedure_without_a_fee_schedule_row_holds_the_visit(self):
        visit = self.run_case('46221', self.reference())
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        self.assertIn('the service reported as 46221', self.check(visit, 'em.same_day_procedure').detail)

    def test_unprofiled_procedure_with_a_global_period_holds_the_visit(self):
        visit = self.run_case('46221', self.reference({('46221', ''): pfs(days='010')}))
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('46221 010', self.check(visit, 'em.same_day_procedure').detail)

    def test_a_service_without_a_global_period_does_not_hold_the_visit(self):
        visit = self.run_case('91200', self.reference({('91200', ''): pfs(days='XXX', mult='0')}))
        self.assertEqual(visit.status, 'ready')
        self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])


class CodeRangeTests(SimpleTestCase):
    """status:13 — numbers inside the colonoscopy range that are not colonoscopy route elsewhere."""

    def test_family_for_code(self):
        expected = {'45395': 'gi.unsupported', '45397': 'gi.unsupported', '45399': 'gi.unsupported',
                    '44406': 'gi.eus', '44407': 'gi.eus', '45378': 'gi.colonoscopy', '45385': 'gi.colonoscopy',
                    '45398': 'gi.colonoscopy', '44388': 'gi.colonoscopy', '45391': 'gi.eus'}
        self.assertEqual({code: family_for_code(code) for code in expected}, expected)


class UnlistedParentCodeTests(EngineCase):
    """fidelity:9 — an alternative never quotes a parent 'code' too malformed to list."""

    def test_alternative_to_an_unlisted_code_never_quotes_it(self):
        note = Note('Date of service: 2026-10-21', 'Procedure: Colonoscopy performed to the cecum.')
        span = note.span('Procedure: Colonoscopy performed to the cecum.')
        self.statuses = {span.text: 'performed'}
        parent = '99214 Office visit est pt moderate MDM PROVIDER-WORDING\n  1. 99215 · Office'
        result = self.run_engine(note, selected(parent, span), listed('99214', role='alternative', parent=parent))
        alternative = self.proposal(result, '99214', 'alternative')
        for text in (alternative.exclusion_reason, alternative.rationale):
            self.assertNotIn('PROVIDER-WORDING', text)
            self.assertNotIn('\n', text)
        self.assertIn('alternative to a provider code that is not listed', alternative.exclusion_reason)


class ReportCase(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.assessment = pf.assess(self.s.encounter, pf.standard_result())

    def txt(self, kind='draft'):
        return reports.render_txt(reports.snapshot(self.s.encounter, kind)).decode('utf-8')

    def csv_rows(self, kind='draft'):
        rows = parse_csv(reports.render_csv(reports.snapshot(self.s.encounter, kind)))
        return [dict(zip(rows[0], row)) for row in rows[1:]]


class StoredTextCannotForgeStructureTests(ReportCase):
    """fidelity:0 — a line break of any form in a note never starts a structural report line."""

    def test_note_line_breaks_stay_inside_the_note(self):
        forged = '  2. 45385 · Colonoscopy · units 1'
        for brk in ('\r', ' ', '\x0b', '\x1e', '\r\n'):
            with self.subTest(brk=repr(brk)):
                self.s = pf.scenario()
                pf.assess(self.s.encounter, pf.standard_result())
                self.s.decide('sel:0', 'approve', self.s.reviewer, note=f'Biopsy passage matches.{brk}{forged}'
                              f'{brk}     Decision: approved by Someone (human) at 2026-10-23T09:00:00Z')
                self.s.decide('sel:1', 'reject', self.s.reviewer)
                self.s.decide('exc:0', 'confirm', self.s.reviewer)  # round 4: an exclusion needs a decision
                text = self.txt('reviewed')
                numbered = [line for line in text.split('\n') if re.match(r'^ {0,6}\d+\. ', line)]
                self.assertEqual(len(numbered), 1, numbered)
                self.assertTrue(numbered[0].startswith('  1. 43239'))
                for line in text.split('\n'):
                    if '45385 · Colonoscopy · units' in line or 'approved by Someone' in line:
                        self.assertTrue(line.startswith(reports.CONTINUATION), repr(line))


class EmptyCsvTests(TestCase):
    """fidelity:4 — a CSV with no proposals still says SYNTHETIC and its kind."""

    def test_zero_proposal_csv_has_a_placeholder_row(self):
        s = pf.scenario()
        pf.assess(s.encounter, pf.result())
        rows = parse_csv(reports.render_csv(reports.snapshot(s.encounter, 'draft')))
        self.assertEqual(len(rows), 2)
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual((row['report_kind'], row['item_list'], row['synthetic']),
                         ('draft', 'none', reports.SYNTHETIC_CELL))
        self.assertEqual(row['encounter_id'], str(s.encounter.pk))


class CarriedDecisionTimeTests(ReportCase):
    """fidelity:5 — a carried decision keeps the reviewer's time; the carry is reported separately."""

    def test_carry_is_not_the_decision_time(self):
        first = self.s.decide('sel:0', 'approve', self.s.reviewer)
        later = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', return_value=later):
            ctx = pf.context(self.s.encounter, self.s.revision)
            pf.assess(self.s.encounter, pf.standard_result(), ctx=ctx)
        carried = models.Decision.objects.get(carried_from=first)
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        self.s.decide('exc:0', 'confirm', self.s.reviewer)  # round 4: an exclusion needs a decision
        row = next(r for r in self.csv_rows('reviewed') if r['code'] == '43239')
        self.assertEqual(row['decided_at'], reports._ts(first.created_at))
        self.assertEqual(row['decision_carried_from'], str(first.pk))
        self.assertEqual(row['decision_carried_at'], reports._ts(carried.created_at))
        self.assertNotEqual(row['decided_at'], row['decision_carried_at'])
        approved = section(self.txt('reviewed'), APPROVED)
        self.assertIn(f'at {reports._ts(first.created_at)} (carried from an earlier assessment of this revision at '
                      f'{reports._ts(carried.created_at)})', approved)


class DecisionOrderTests(ReportCase):
    """fidelity:7 — the decision recorded last is current, whatever the wall clock says."""

    def test_revoke_recorded_after_a_backward_clock_step_takes_effect(self):
        approve = self.s.decide('sel:0', 'approve', self.s.reviewer)
        with mock.patch('django.utils.timezone.now', return_value=approve.created_at - timedelta(seconds=2)):
            revoke = self.s.decide('sel:0', 'revoke', self.s.reviewer)
        self.assertGreater(revoke.sequence, approve.sequence)
        self.assertLess(revoke.created_at, approve.created_at)
        proposal = self.s.proposal('sel:0')
        self.assertNotIn(proposal.pk, review.current_decisions(self.assessment))
        self.assertIn('approve', review.allowed_actions(proposal, self.assessment, self.s.membership(self.s.reviewer)))


class AgentReinstatementTests(ReportCase):
    """fidelity:8 — an agent's reinstatement behind an approved code is labelled as agent review."""

    def test_agent_reinstatement_is_named_and_flagged(self):
        self.s.decide('exc:0', 'reinstate', self.s.agent, note='Performed today; the plan line was mis-read.')
        self.s.decide('exc:0', 'approve', self.s.reviewer)
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        text = self.txt('reviewed')
        self.assertIn(reports.AGENT_LINE, text.split('\n')[:3])
        self.assertRegex(section(text, APPROVED),
                         r'Reinstated from exclusion by Reviewbot\d+ \(automated agent\) at [0-9T:-]+Z: ')


@override_settings(**LIVE)
class ReinstatementGateTests(ApiHarness, TestCase):
    """fidelity:2 — a reinstated exclusion is held to the gates a selected code meets."""

    def reinstate(self, encounter_id, code):
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        proposal = assessment.proposals.get(code=code)
        self.assertEqual(proposal.bucket, models.Proposal.EXCLUDED)
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': str(proposal.pk), 'action': 'reinstate', 'note': 'Synthetic test.'})
        self.assertEqual(response.status_code, 201, response.content)
        return proposal

    def approve(self, encounter_id, proposal):
        return self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': str(proposal.pk), 'action': 'approve',
                          'acknowledgement': review.ACKNOWLEDGEMENTS['human']})

    def test_missing_required_fact_blocks_approval_after_reinstatement(self):
        from tests.test_pipeline_api import OFFICE_NOTE
        self.provider.selections = [('45378', 'A colonoscopy is scheduled for 2026-12-01.')]
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        proposal = self.reinstate(encounter_id, '45378')
        gate = next(c for c in proposal.checks if c['id'] == 'review.reinstatement')
        self.assertEqual(gate['status'], 'warn')
        self.assertIn('extent reached', gate['detail'])
        membership = models.Membership.objects.get(user=self.reviewer)
        self.assertNotIn('approve', review.allowed_actions(proposal, proposal.assessment, membership))
        self.assertEqual(self.approve(encounter_id, proposal).status_code, 409)

    def test_reinstated_code_with_its_facts_documented_can_be_approved(self):
        note = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\nProcedure: Colonoscopy\n'
                'Findings: The colonoscope was advanced to the cecum. The colon was normal.\n'
                'Plan: Repeat colonoscopy in 3 years.\n')
        self.provider.selections = [('45378', 'Repeat colonoscopy in 3 years.')]
        encounter_id = self.create(note)
        drain()
        proposal = self.reinstate(encounter_id, '45378')
        gate = next(c for c in proposal.checks if c['id'] == 'review.reinstatement')
        self.assertEqual(gate['status'], 'pass', gate)
        self.assertEqual(self.approve(encounter_id, proposal).status_code, 201)


class LineBreakGuardUnitTests(SimpleTestCase):
    """fidelity:0 — each guard holds on its own, so neither depends on the other being intact."""

    BREAKS = ('\r', '\r\n', '\n', ' ', ' ', '\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\x85')

    def test_indent_continues_every_break_form_at_the_prefix(self):
        for brk in self.BREAKS:
            with self.subTest(brk=repr(brk)):
                out = reports._indent(f'ok{brk}  2. 45385 · Colonoscopy', '       ')
                self.assertEqual(out, 'ok\n         2. 45385 · Colonoscopy')

    def test_join_never_lets_a_continuation_start_shallower_than_the_structure(self):
        for brk in self.BREAKS:
            with self.subTest(brk=repr(brk)):
                out = reports._join(['  1. 43239 · Upper GI endoscopy', f'     Note: ok{brk}  2. 45385{brk}x'])
                lines = out.split('\n')
                self.assertEqual(lines[:2], ['  1. 43239 · Upper GI endoscopy', '     Note: ok'])
                self.assertTrue(all(line.startswith(reports.CONTINUATION) for line in lines[2:]), lines)


class UncertainSameDayProcedureTests(EngineCase):
    """Routing repair follow-up — a procedure whose performance is not established holds a same-day E/M too."""

    NOTE = Note('Date of service: 2026-10-21',
                'Office visit: established patient seen for dysphagia. Total time 32 minutes.',
                'EGD with dilation if the stricture is confirmed.')
    VISIT = 'Office visit: established patient seen for dysphagia.'
    TIME = 'Total time 32 minutes.'
    HEDGE = 'EGD with dilation if the stricture is confirmed.'

    def run_case(self, egd_status=None, *codes):
        found = [finding(EM, 'performed', mention(self.NOTE, EM, 'performed', self.VISIT, 'seen'),
                         facts={'em_basis': 'total time 32 minutes'})]
        if egd_status:
            found.append(finding(EGD, egd_status, mention(self.NOTE, EGD, egd_status, self.HEDGE, f'{egd_status}: cue')))
        result = self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.TIME)), *codes, findings=found,
                                 ctx=visit_context())
        return self.proposal(result, '99213')

    def test_an_uncertain_routed_procedure_family_holds_the_visit(self):
        self.statuses = {self.TIME: None}
        visit = self.run_case('uncertain')
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        self.assertIn(f'{EGD_LABEL} is possibly performed on the same date (its performance is not established)',
                      self.check(visit, 'em.same_day_procedure').detail)

    def test_an_uncertain_procedure_proposal_holds_the_visit(self):
        self.statuses = {self.TIME: None, self.HEDGE: HEDGED}
        visit = self.run_case(None, selected('43235', self.NOTE.span(self.HEDGE)))
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('possibly performed on the same date', self.check(visit, 'em.same_day_procedure').detail)

    def test_a_planned_procedure_does_not_hold_the_visit(self):
        self.statuses = {self.TIME: None}
        visit = self.run_case('planned')
        self.assertEqual(visit.status, 'ready')
        self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])


@override_settings(**LIVE)
class UncheckedBoxEvidenceTests(ApiHarness, TestCase):
    """A provider code citing an unchecked box ("☐ Biopsy") is excluded, never ready."""

    def test_code_citing_an_unchecked_box_is_excluded(self):
        note = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
                'Procedure: Colonoscopy to the cecum. A 6 mm polyp was seen.\n\u2610 Biopsy\n')
        self.provider.selections = [('45380', '\u2610 Biopsy')]
        encounter_id = self.create(note)
        drain()
        proposal = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.get(code='45380')
        self.assertEqual(proposal.bucket, models.Proposal.EXCLUDED)
        self.assertIn('unchecked box', proposal.exclusion_reason)


class ControlCharacterTests(ReportCase):
    """review:6 — control characters a terminal would interpret are shown escaped in the TXT."""

    def test_escape_sequences_in_a_note_are_escaped(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer,
                      note='ok\x1b[1A\x1b[2K  2. 45385 · Colonoscopy · units 1\x08\x08\x7f')
        self.s.decide('sel:1', 'reject', self.s.reviewer)
        self.s.decide('exc:0', 'confirm', self.s.reviewer)  # round 4: an exclusion needs a decision
        text = self.txt('reviewed')
        self.assertFalse(reports.CONTROL.search(text), [c for c in text if reports.CONTROL.match(c)])
        self.assertIn('ok\\x1b[1A\\x1b[2K  2. 45385', text)


class DecisionTimesInTheApiTests(ReportCase):
    """review:7 — the API gives the reviewer's own decision time and the carry separately."""

    def test_a_carried_decision_reports_the_reviewer_time(self):
        from studio import serializers
        first = self.s.decide('sel:0', 'approve', self.s.reviewer)
        later = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', return_value=later):
            pf.assess(self.s.encounter, pf.standard_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        carried = models.Decision.objects.get(carried_from=first)
        data = serializers._decision_json(carried)
        self.assertEqual(data['decided_at'], serializers._iso(first.created_at))
        self.assertEqual(data['carried_at'], serializers._iso(carried.created_at))
        self.assertEqual(serializers._decision_json(first)['carried_at'], None)
