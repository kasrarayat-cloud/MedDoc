"""Round-3b seams with TIME's routing (the orchestrator's forwarded items): validation:1 and validation:9.

TIME's integrated routing adds the cue detect.PLAN_TODAY ('uncertain: its clause says today, so its plan section does
not make it planned'): a plan-section passage whose clause says today is no longer read planned by its section, only
held. This worktree does not carry TIME's commits, so the routing readings are stated explicitly, with the cue
contract's exact string (and a guard that the integrated constant equals it). Synthetic text only; pure functions.
"""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi.profiles import PROFILES
from studio.validation import checks
from tests.test_repairs_r3_validation_b import HEAD, real
from tests.test_repairs_status_r2_validation import SILENT_CUE, placed
from tests.test_validation import EGD, EM, EngineCase, Note, finding, selected, visit_context

PLAN_TODAY = 'uncertain: its clause says today, so its plan section does not make it planned'
AP = 'section: plan (Assessment and plan)'
EGD_LABEL = PROFILES[EGD].label


class PlanTodayCueContractTests(SimpleTestCase):
    def test_the_cue_validation_reads_is_routing_s(self):
        self.assertEqual(checks.PLAN_TODAY_CUE, PLAN_TODAY)
        # Active once TIME's routing is integrated: the constant there must be the contract's string.
        self.assertEqual(getattr(detect, 'PLAN_TODAY', PLAN_TODAY), PLAN_TODAY)


class Validation1PlanTodayHoldsTheVisitTests(EngineCase):
    """validation:1 with the E/M selected alone: a routed procedure whose plan-section passage says today (PLAN_TODAY)
    can speak for the date of service, so the routed family alone holds the E/M; plan hedges stay released."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for dysphagia.',
                'Total time 32 minutes.', 'EGD this morning revealed a Schatzki ring, dilated to 18 mm.')
    VISIT, TIME = 'Office visit: established patient seen for dysphagia.', 'Total time 32 minutes.'
    LINE = 'EGD this morning revealed a Schatzki ring, dilated to 18 mm.'

    def visit_for(self, status, *cues, section='plan'):
        self.statuses = {self.TIME: None}
        found = [finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                         facts={'em_basis': 'total time 32 minutes'}),
                 finding(EGD, status, placed(self.NOTE, EGD, status, self.LINE, section, *cues))]
        result = self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.TIME)), findings=found,
                                 ctx=visit_context())
        return self.proposal(result, '99213')

    def test_a_plan_passage_that_says_today_holds_the_visit(self):
        visit = self.visit_for('uncertain', PLAN_TODAY, AP)
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        self.assertIn(f'{EGD_LABEL} is possibly performed on the same date',
                      self.check(visit, 'em.same_day_procedure').detail)

    def test_controls_plan_hedges_and_plan_defaults_stay_released(self):
        for status, cues in (('uncertain', ('uncertain: Possible',)), ('uncertain', ('uncertain: Discussed',)),
                             ('planned', (AP,)), ('uncertain', (SILENT_CUE,))):
            with self.subTest(cues=cues):
                visit = self.visit_for(status, *cues)
                self.assertEqual(visit.status, 'ready', [c.detail for c in visit.checks])
        # wherever routing writes the cue, the passage's clause says today: held, fail-closed
        visit = self.visit_for('uncertain', PLAN_TODAY, 'section: history (History of present illness)',
                               section='history')
        self.assertEqual(visit.status, 'needs_clarification')


class Validation3PlanTodayIsTheVisitsOwnPlanTests(EngineCase):
    """The validation:3 rule at TIME's PLAN_TODAY reading: an E/M code citing its own plan sentence that says today
    ("Start omeprazole today.") is not held by that section default; routing's E/M reading decides."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for heartburn.',
                'Total time 32 minutes.', 'Start omeprazole 40 mg today.')
    VISIT, TIME, PLAN = 'Office visit: established patient seen for heartburn.', 'Total time 32 minutes.', \
        'Start omeprazole 40 mg today.'

    def visit_for(self, plan_reading):
        self.statuses = {self.TIME: None, self.PLAN: plan_reading}
        found = [finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                         facts={'em_basis': 'total time 32 minutes'})]
        result = self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.PLAN)), findings=found,
                                 ctx=visit_context())
        return self.proposal(result, '99213')

    def test_a_plan_sentence_that_says_today_is_silent_for_the_e_m(self):
        visit = self.visit_for(('uncertain', (PLAN_TODAY, AP)))
        self.assertEqual((visit.bucket, visit.status), ('selected', 'ready'), [c.detail for c in visit.checks])
        self.assertEqual(self.check(visit, 'service.status').status, 'pass')

    def test_controls_a_hedge_in_the_plan_still_holds_the_e_m(self):
        visit = self.visit_for(('uncertain', ('uncertain: Possible',)))
        self.assertEqual(visit.status, 'needs_clarification')


class Validation9StatedAsPerformedWordingTests(SimpleTestCase):
    """validation:9's wording (forwarded): a passage that states the act but is held because of its section never
    reads "No documentation establishes that ... was performed", and its section cue is cited."""

    STATED = checks.Reading('uncertain', ('performed: was performed', 'performed: performed today', AP), 'evidence',
                            'Rubber band ligation of an internal hemorrhoid was performed today as scheduled.')

    def test_the_hold_says_where_the_act_was_stated(self):
        outcome = checks.resolve_status([self.STATED])
        detail = checks.status_check(outcome, 'the service reported as 46221').detail
        self.assertNotIn('No documentation establishes', detail)
        self.assertIn('The linked passage states the service reported as 46221 as performed under Assessment and plan',
                      detail)
        self.assertIn(f'(cue “{AP}”, linked passage)', detail)
        self.assertIn('confirm it was performed on the date of service', detail)
        question = checks.performed_clarification(outcome, 'the service reported as 46221', 'gi.other', 'sel:0')
        self.assertEqual(question.reason, detail)

    def test_routing_s_statement_and_a_section_without_a_heading(self):
        routed = checks.Reading('uncertain', ('performed: was performed', 'section: plan'), 'routing',
                                'EGD was performed.')
        detail = checks.status_check(checks.resolve_status([routed]), EGD_LABEL).detail
        expected = (f'Routing states {EGD_LABEL} as performed under its plan section: “EGD was performed.” (cue '
                    '“section: plan”, routing); confirm it was performed')
        self.assertTrue(detail.startswith(expected), detail)

    def test_controls_other_holds_keep_their_wording(self):
        hedge = checks.Reading('uncertain', ('uncertain: Possible',), 'evidence', 'Possible banding.')
        detail = checks.status_check(checks.resolve_status([hedge]), 'the service reported as 46221').detail
        self.assertTrue(detail.startswith('No documentation establishes'), detail)
        self.assertIn('(cue “uncertain: Possible”, linked passage)', detail)
        doubted = checks.Reading('uncertain', ("uncertain: unresolved negation 'not' in its clause",
                                               'performed: was performed', AP), 'evidence', 'X.')
        self.assertIn("(cue “uncertain: unresolved negation 'not' in its clause”",
                      checks.status_check(checks.resolve_status([doubted]), 'X').detail)

    def test_through_real_routing(self):
        text = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n'
                'Assessment and plan: Colonoscopy was performed with cold snare polypectomy of a 5 mm polyp.\n')
        stated = 'Colonoscopy was performed with cold snare polypectomy of a 5 mm polyp.'
        proposals, _ = real(text, ('45385', stated))
        status = next(c for c in proposals['45385'].checks if c.id == 'service.status')
        self.assertEqual(proposals['45385'].status, 'needs_clarification')
        self.assertIn('states Colonoscopy as performed under Assessment and plan', status.detail)
        self.assertNotIn('No documentation establishes', status.detail)
