"""Regressions for round 4c-2, PLAN agent (routing: plan clauses, extents, denying labels).

Each class reproduces one item of round 4c-2 (plan:A, plan:A2, plan:B, plan:C) from its exact input, adds the variants
the item lists, and pins controls in both directions. Every rule here only holds: it moves a reading to uncertain with
a non-silent cue (and never newly excludes or releases), and every pinned release named in the items stays ready.

Routing runs for real, for the document's own service date and through the JSON round trip the pipeline applies; the
real validation engine assesses provider-shaped selections against in-memory references. Synthetic text only.
"""
import unittest

from studio.gi import detect
from tests.test_repairs_r3_sections import HEADER, NOT_TODAY, clarified, family, read, ready, run_engine
from tests.test_repairs_r3_validation_b import check_of, real

VISIT = 'Established patient office visit.'


def office(plan, heading='Assessment and plan:'):
    """The office-note frame of items-plan.txt (plan:A, plan:A2)."""
    return (HEADER + 'Place of service: Office (POS 11)\n' + VISIT + '\nChief complaint: Heartburn.\nHistory of present '
            'illness: Heartburn for 8 weeks.\n' + heading + ' ' + plan + '\nMedical decision making: moderate.\n')


def visit_of(text):
    return real(text, ('99214', VISIT))[0]['99214']


def held_for_a_same_day_procedure(proposal):
    """The E/M is held for a possible same-day procedure: needs clarification of the separately identifiable E/M,
    with the same-day procedure check warning."""
    same_day = check_of(proposal, 'em.same_day_procedure')
    return (proposal.status == 'needs_clarification' and 'separate_em' in clarified(proposal)
            and same_day is not None and same_day.status == 'warn')


def visit_ready(proposal):
    return ready(proposal) and check_of(proposal, 'em.same_day_procedure') is None


def mention_cues(text, slug, occurrence=0):
    finding = detect.route(text, None).finding(slug)
    return finding.mentions[occurrence].status, finding.mentions[occurrence].cues


# --- plan:A: a findings statement with a diagnostic hedge in a plan clause that says today ---------------------------

class PlanAFindingsTodayTests(unittest.TestCase):
    """plan:A (high, declared misread). ARCHITECTURE 5.3: in a plan section any clause that says today holds
    (PLAN_TODAY), and validation (5.6) counts such a plan mention as a same-day procedure for the E/M hold. "EGD today
    showed esophagitis versus reflux." released the E/M although "EGD today showed esophagitis." holds it: the hedge
    about the FINDING decided the reading, and round 4c's validation:3 arm (4e2dc449b) adds PLAN_TODAY only beside a
    performance cue. A plan clause that says today and states the procedure's own result (a reporting verb straight
    after the service name: _REPORTING, the verbs the continuation reader already reads as reporting what the
    procedure found) now carries PLAN_TODAY too. The pinned hedged or discussed plans name no result and stay ready."""

    CLAIMED = ('EGD today showed esophagitis versus reflux.', 'EGD today revealed esophagitis versus reflux.',
               'EGD this morning showed esophagitis versus reflux.')
    # the other reporting verbs, the other hedges, the other plan headings and today forms, names between the service
    # and its verb, and a today word elsewhere in the clause (each of them held without the hedge at the base)
    VARIANTS = (('Assessment and plan:', 'EGD today demonstrated esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD today found esophagitis vs reflux.'),
                ('Assessment and plan:', 'EGD today noted esophagitis vs. reflux.'),
                ('Assessment and plan:', 'EGD today disclosed esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD today identified esophagitis, ?eosinophilic esophagitis.'),
                ('Assessment and plan:', 'EGD today documented esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD this afternoon shows esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD today reveals esophagitis, unclear whether reflux.'),
                ('Assessment and plan:', 'EGD today demonstrates esophagitis versus reflux.'),
                ('Plan:', 'EGD today showed esophagitis versus reflux.'),
                ('A/P:', 'EGD today showed esophagitis versus reflux.'),
                ('Impression and plan:', 'EGD this morning revealed esophagitis versus reflux.'),
                ('Assessment and plan:', "Today's EGD showed esophagitis versus reflux."),
                ('Assessment and plan:', 'EGD (today) showed esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD, today, showed esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD with biopsies today showed esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD w/ biopsies this morning revealed esophagitis versus reflux.'),
                ('Assessment and plan:', 'EGD and colonoscopy today showed esophagitis versus colitis.'),
                ('Assessment and plan:', 'EGD showed esophagitis versus reflux, reviewed with her today.'),
                ('Assessment and plan:', '1. EGD today showed esophagitis versus reflux.'),
                ('Assessment and plan:', '- EGD today showed esophagitis versus reflux.'),
                ('Assessment and plan:', 'Upper endoscopy today showed esophagitis versus reflux.'))
    # round 3 validation:1, round 2 review:1 and round 4c validation:3: hedged, conditioned or discussed plans that
    # name no result of the procedure keep the visit approvable (pinned elsewhere too; repeated here as controls)
    PINNED_READY = ('Possible EGD today if symptoms persist.', 'Discussed colonoscopy today; she will think about it.',
                    'Colonoscopy? Will decide today after labs.',
                    'Discussed colonoscopy today; the patient will think about it.',
                    'Possible EGD if symptoms persist.', 'EGD versus empiric PPI trial.',
                    'Discussed colonoscopy; patient will call to schedule.')
    # the hedge is the service's own and the reporting verb is another test's; and the no-today residual the item says
    # to leave as it is
    CONTROLS_READY = ('EGD versus PPI trial today, as the barium study showed a ring.',
                      'Possible EGD today, as the barium study showed a ring.',
                      'Possible EGD today for dysphagia; she will decide.',
                      'EGD today for dysphagia versus PPI trial; she will decide.',
                      # the verb is read only in the service's own clause (", and this ..." opens another)
                      'Possible colonoscopy today, and this morning revealed a ring on the barium study.',
                      'EGD showed esophagitis versus reflux.', 'EGD revealed esophagitis versus reflux.')

    def assert_held(self, text, slug='gi.egd'):
        status, cues = mention_cues(text, slug)
        self.assertEqual(status, 'uncertain', cues)
        self.assertIn(detect.PLAN_TODAY, cues)
        # the hedge stays the reading's first cue: never a bare section default for validation (checks.section_default)
        self.assertNotEqual(cues[0], detect.PLAN_TODAY, cues)
        self.assertTrue(held_for_a_same_day_procedure(visit_of(text)), text)

    def test_the_claimed_lines_hold_the_visit(self):
        for plan in self.CLAIMED:
            with self.subTest(plan=plan):
                self.assert_held(office(plan))
                self.assertEqual(mention_cues(office(plan), 'gi.egd')[1][0], 'uncertain: versus')

    def test_the_variants_hold_the_visit(self):
        for heading, plan in self.VARIANTS:
            with self.subTest(heading=heading, plan=plan):
                self.assert_held(office(plan, heading))

    def test_the_line_cited_by_its_own_code_is_held_never_ready_or_excluded(self):
        for plan in self.CLAIMED:
            text = office(plan)
            with self.subTest(plan=plan):
                status, cues = read(text, plan)
                self.assertEqual(status, 'uncertain', cues)
                proposal = run_engine(text, [('43239', plan)])['43239']
                self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))

    def test_a_repeat_planned_beside_it_no_longer_plans_the_family(self):
        """At the base the hedged line beside "Repeat EGD in 8 weeks." left the EGD family planned (its unhedged
        version reads uncertain); PLAN_TODAY is a doubt about today's service, so the plan cannot outrank it."""
        text = office('EGD today showed esophagitis versus reflux. Repeat EGD in 8 weeks.')
        self.assertEqual(family(text, 'gi.egd'), 'uncertain')
        self.assertTrue(held_for_a_same_day_procedure(visit_of(text)))
        # the repeat itself stays planned, and its code stays excluded
        self.assertEqual(read(text, 'Repeat EGD in 8 weeks.')[0], 'planned')
        self.assertEqual(run_engine(text, [('43235', 'Repeat EGD in 8 weeks.')])['43235'].bucket, 'excluded')

    def test_the_pinned_releases_and_the_controls_stay_ready(self):
        for plan in self.PINNED_READY + self.CONTROLS_READY:
            text = office(plan)
            with self.subTest(plan=plan):
                self.assertTrue(visit_ready(visit_of(text)), plan)
                finding = detect.route(text, None).finding('gi.egd') or detect.route(text, None).finding(
                    'gi.colonoscopy')
                self.assertFalse(any(detect.PLAN_TODAY in m.cues for m in finding.mentions), plan)

    def test_each_clause_is_read_for_its_own_today_word(self):
        """Two plan sentences in one note, one saying today: only that one carries PLAN_TODAY, in either order."""
        for plan, held_slug, free_slug in (
                ('EGD showed esophagitis versus reflux. Colonoscopy today showed colitis versus ischemia.',
                 'gi.colonoscopy', 'gi.egd'),
                ('Colonoscopy today showed colitis versus ischemia. EGD showed esophagitis versus reflux.',
                 'gi.colonoscopy', 'gi.egd')):
            text = office(plan)
            with self.subTest(plan=plan):
                self.assertIn(detect.PLAN_TODAY, mention_cues(text, held_slug)[1])
                self.assertNotIn(detect.PLAN_TODAY, mention_cues(text, free_slug)[1])

    def test_a_cited_passage_is_read_over_all_its_clauses(self):
        """As the plan arms read a cited passage: any of its clauses may say today ("...; reviewed with her today."), and
        the hedged sentence then reads as its unhedged twin does; the mention, whose own clause says no today, is left."""
        for plan in ('EGD showed esophagitis versus reflux; reviewed with her today.',
                     'EGD showed esophagitis; reviewed with her today.'):
            text = office(plan)
            with self.subTest(plan=plan):
                status, cues = read(text, plan)
                self.assertEqual(status, 'uncertain')
                self.assertIn(detect.PLAN_TODAY, cues)
                self.assertNotIn(detect.PLAN_TODAY, mention_cues(text, 'gi.egd')[1])

    def test_an_e_m_mention_never_carries_it(self):
        """The rule is a procedure's, as round 4c's validation:3 arm is: an E/M documentation mention keeps its own
        reading even where its span quotes the procedure (an MDM line), while the procedure's mention is held."""
        text = (HEADER + 'Place of service: Office (POS 11)\n' + VISIT + '\nAssessment and plan: MDM: EGD today showed '
                'esophagitis versus reflux, moderate.\n')
        em = detect.route(text, None).finding('gi.office_em')
        mdm = [m for m in em.mentions if m.span.text.startswith('MDM')]
        self.assertEqual(len(mdm), 1)
        self.assertNotIn(detect.PLAN_TODAY, mdm[0].cues)
        self.assertIn(detect.PLAN_TODAY, mention_cues(text, 'gi.egd')[1])

    def test_only_a_plan_section_carries_it(self):
        """Outside a plan section a hedge already counts for the same-day check (round 4 validation:0), and a history
        or indication section has its own defaults: no PLAN_TODAY is added there."""
        for heading in ('Assessment:', 'History of present illness:', 'Indication:'):
            text = office('EGD today showed esophagitis versus reflux.', heading)
            with self.subTest(heading=heading):
                self.assertNotIn(detect.PLAN_TODAY, mention_cues(text, 'gi.egd')[1])


# --- plan:A2: an explicit performance statement with a diagnostic hedge, with no today word ---------------------------

class PlanA2HedgedPerformanceTests(unittest.TestCase):
    """plan:A2 (high, declared reading). ARCHITECTURE 5.3: in a plan section an explicit performance is held; 5.6: inside
    plan, history and indication / chief-complaint sections an explicit performance statement that routing downgraded
    for its section counts as a same-day procedure for the E/M hold. "Anoscopy was performed and showed grade 2 internal
    hemorrhoids versus prolapse." under Assessment and plan released the E/M: the hedge outranks the performance cue in
    _cue_reading, so validation's plan-section branch saw neither a 'performed:' cue nor PLAN_TODAY (with "today" round
    4c's validation:3 arm adds PLAN_TODAY). Such a reading now carries a hold cue whose prefix validation already counts
    there (checks._VAL_OTHER_STATED_CUE, the stated-act holds of 5.6) wherever the statement without its hedge would
    count: a plan section (no today; with today PLAN_TODAY as before), an indication / chief-complaint section, and a
    history section whose clause says today. The labels _cue_reading keeps are unchanged."""

    CLAIMED = ('Anoscopy was performed and showed grade 2 internal hemorrhoids versus prolapse.',
               'EGD was performed with biopsies, eosinophilic esophagitis versus reflux.',
               'Flexible sigmoidoscopy was performed, proctitis versus infection.')
    VARIANTS = (('Plan:', 'Anoscopy was performed and showed grade 2 internal hemorrhoids versus prolapse.'),
                ('A/P:', 'EGD was performed with biopsies, eosinophilic esophagitis vs reflux.'),
                ('Assessment and plan:', 'Colonoscopy was completed and showed colitis, ?ischemia.'),
                ('Assessment and plan:', 'EGD was performed with biopsies, unclear whether eosinophilic esophagitis.'),
                ('Assessment and plan:', 'Rubber band ligation was performed, ?fissure.'),
                ('Assessment and plan:', '1. Flexible sigmoidoscopy was performed, proctitis versus infection.'),
                # the same statement where its section, unhedged, also counts: an indication or chief complaint, and
                # a history section whose clause says today
                ('Indication:', 'Colonoscopy was performed and showed colitis versus ischemia.'),
                ('Indication:', 'Colonoscopy was performed today and showed colitis versus ischemia.'),
                ('Chief complaint:', 'Colonoscopy was performed and showed colitis versus ischemia.'),
                ('History of present illness:', 'Colonoscopy was performed this morning and showed colitis versus ischemia.'),
                ('History of present illness:', 'EGD was performed today, eosinophilic esophagitis versus reflux.'))
    # a history section that does not say today reads historical without the hedge, which validation does not count
    CONTROLS_READY = (('History of present illness:', 'Colonoscopy was performed and showed colitis versus ischemia.'),
                      ('History of present illness:', 'EGD was performed with biopsies, eosinophilic esophagitis versus reflux.'),
                      # the pinned releases: no performance statement
                      ('Plan:', 'Possible EGD if symptoms persist.'),
                      ('Assessment and plan:', 'EGD versus empiric PPI trial.'),
                      ('Assessment and plan:', 'Possible EGD today if symptoms persist.'),
                      ('Assessment and plan:', 'Discussed colonoscopy today; she will think about it.'),
                      ('Assessment and plan:', 'Risks and benefits of colonoscopy were discussed.'))

    def stated(self, text):
        """The hold cues of every routed procedure mention that carry the stated-act prefix validation counts."""
        from studio.validation import checks
        result = detect.route(text, None)
        return [c for f in result.findings if f.family != 'gi.office_em' for m in f.mentions for c in m.cues
                if c.startswith(checks._VAL_OTHER_STATED_CUE)]

    def test_the_claimed_lines_hold_the_visit(self):
        for plan in self.CLAIMED:
            text = office(plan)
            with self.subTest(plan=plan):
                self.assertTrue(held_for_a_same_day_procedure(visit_of(text)), plan)
                self.assertEqual(self.stated(text), [detect._P2_HEDGED_STATEMENT])

    def test_the_variants_and_the_sibling_sections_hold_the_visit(self):
        for heading, plan in self.VARIANTS:
            text = office(plan, heading)
            with self.subTest(heading=heading, plan=plan):
                self.assertTrue(held_for_a_same_day_procedure(visit_of(text)), plan)
                self.assertEqual(self.stated(text), [detect._P2_HEDGED_STATEMENT])

    def test_the_hedge_still_decides_and_is_the_first_cue(self):
        """Hold-only: the reading stays uncertain, its first cue the hedge (never a 'performed:' cue, so checks.restated
        and resolve_status read it as before), and no PLAN_TODAY where no clause says today (round 4c validation:3)."""
        text = office(self.CLAIMED[0])
        status, cues = read(text, self.CLAIMED[0])
        self.assertEqual(status, 'uncertain')
        self.assertEqual(cues[0], 'uncertain: versus')
        self.assertFalse(any(c.startswith('performed:') for c in cues), cues)
        self.assertNotIn(detect.PLAN_TODAY, cues)
        self.assertEqual(cues[1:], (detect._P2_HEDGED_STATEMENT, 'section: plan (Assessment and plan)'))

    def test_an_e_m_mention_never_carries_it(self):
        """A visit statement is no procedure: its own reading under a plan heading keeps its hedge, as round 4c's
        validation:3 test keeps it ("Plan: Established patient visit was performed today, ?IBS.")."""
        text = office('Established patient visit was performed, ?IBS.', 'Plan:')
        visit = [m for m in detect.route(text, None).finding('gi.office_em').mentions
                 if m.span.text.startswith('Established patient visit')]
        self.assertEqual(len(visit), 1)
        self.assertNotIn(detect._P2_HEDGED_STATEMENT, visit[0].cues)

    def test_a_code_citing_the_statement_stays_held(self):
        for plan, code in zip(self.CLAIMED, ('46600', '43239', '45330')):
            text = office(plan)
            with self.subTest(plan=plan):
                proposal = run_engine(text, [(code, plan)])[code]
                self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))

    def test_the_cue_is_counted_by_its_prefix_and_states_no_today(self):
        from studio.validation import checks
        self.assertTrue(detect._P2_HEDGED_STATEMENT.startswith(checks._VAL_OTHER_STATED_CUE))
        self.assertTrue(checks._VAL_routing_holds((detect._P2_HEDGED_STATEMENT,)))
        self.assertFalse(checks.says_today_in_plan((detect._P2_HEDGED_STATEMENT,)))
        self.assertNotIn('today', detect._P2_HEDGED_STATEMENT)

    def test_the_controls_stay_ready(self):
        for heading, plan in self.CONTROLS_READY:
            text = office(plan, heading)
            with self.subTest(heading=heading, plan=plan):
                self.assertEqual(self.stated(text), [])
                self.assertTrue(visit_ready(visit_of(text)), plan)

    def test_outside_those_sections_nothing_is_added(self):
        """Outside plan, history and indication sections a hedge already counts for the same-day check (round 4
        validation:0), so the reading is left exactly as it was."""
        for heading in ('Assessment:', 'Impression:'):
            text = office(self.CLAIMED[0], heading)
            with self.subTest(heading=heading):
                self.assertEqual(self.stated(text), [])
                self.assertTrue(held_for_a_same_day_procedure(visit_of(text)))


if __name__ == '__main__':
    unittest.main()
