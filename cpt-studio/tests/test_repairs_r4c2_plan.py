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


# --- plan:B: an unread extent label never lets a shallower prose landmark read the procedure incomplete --------------

def report(procedure, prose, label, findings='Findings: Normal.'):
    return HEADER + f'Procedure: {procedure}\n{prose}\n{label}\n{findings}\n'


COLON_PROSE = 'The colonoscope was inserted into the rectum and advanced.'
UPPER_PROSE = 'The endoscope was passed into the esophagus.'


def extent_of(text, slug):
    finding = detect.route(text, None).finding(slug)
    return finding.status, next((f.value for f in finding.facts if f.name == 'extent'), None), finding.missing


class PlanBUnreadExtentLabelTests(unittest.TestCase):
    """plan:B (high, declared misread; reported by the round-4c SECTIONS agent). ARCHITECTURE 5.3: an extent label
    ("Extent: cecum") is read only when what follows its landmark is punctuation, a cues.EXTENT_TAIL word, or (round 4c
    declared:11) a next cell that opens a listed report field. "Extent: Cecum | Scope: Olympus" is therefore unread, and
    the extent fell back to the shallower prose landmark ("inserted into the rectum"): a false "incomplete: rectum", the
    family incomplete and 45378 ready with an incomplete-procedure warning. An unread label that names a landmark deeper
    than every landmark read as reached now keeps that shallower landmark from reading the procedure incomplete: no
    extent is read (the family's extent clarification), for a colonoscopy and an upper endoscopy alike. The label's tail
    is still never read ("| Scope:" stays outside the closed list), so nothing newly reads an extent."""

    CLAIMED = report('Colonoscopy', COLON_PROSE, 'Extent: Cecum | Scope: Olympus')
    UNREAD = ('Extent: Cecum | Scope: Olympus CF-HQ190', 'Extent: Cecum\tScope: Olympus', 'Extent reached: Cecum | Instrument: Olympus',
              'Extent: Terminal ileum | Scope: Olympus', 'Furthest extent reached: cecum | Scope: Olympus',
              'Extent: Cecum (photo documented) | Scope: Olympus', 'Extent: Cecum | Scope: Olympus | Prep: good',
              'Extent: Cecum | Instrument: Olympus', '- Extent: Cecum | Scope: Olympus', 'Extent: Cecum  Endoscopist: Dr. Lee',
              'Extent: Cecum | Model: CF-HQ190 | Room: 3',
              # a listed next field ends what is read for a denial, as it ends the value (round 4c declared:11): its
              # answer is its own, so it neither doubts the landmark nor makes the label a denial
              'Extent: Cecum | Scope: Olympus | Complications: None', 'Extent: Cecum | Complications: None',
              'Extent: Cecum | Prep quality: Good | Complications: None', 'Extent: Cecum    Complications: none')

    def assert_held_extent(self, text, slug, code, cite):
        status, extent, missing = extent_of(text, slug)
        self.assertNotEqual(status, 'incomplete')
        self.assertIsNone(extent)
        self.assertIn('extent', missing)
        proposal = real(text, (code, cite))[0][code]
        self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))
        self.assertIn('extent', clarified(proposal))
        self.assertFalse(any(c.id == 'service.incomplete' for c in proposal.checks))

    def test_the_claimed_input_holds_the_extent(self):
        self.assert_held_extent(self.CLAIMED, 'gi.colonoscopy', '45378', 'Procedure: Colonoscopy')

    def test_other_unread_labels_hold_the_extent(self):
        for label in self.UNREAD:
            with self.subTest(label=label):
                self.assert_held_extent(report('Colonoscopy', COLON_PROSE, label), 'gi.colonoscopy', '45378',
                                        'Procedure: Colonoscopy')

    def test_the_upper_tract_sibling(self):
        for label in ('Extent: D2 | Scope: Olympus', 'Extent: Second part of the duodenum | Scope: Olympus GIF',
                      'Extent reached: duodenum | Endoscope: Olympus GIF'):
            with self.subTest(label=label):
                self.assert_held_extent(report('EGD', UPPER_PROSE, label), 'gi.egd', '43235', 'Procedure: EGD')

    def test_a_read_label_and_the_declared_unread_controls_are_unchanged(self):
        # a label read whole decides as before
        for label, extent in (('Extent: Cecum (photo documented) | Prep: good', 'cecum'), ('Extent: Cecum', 'cecum'),
                              ('Extent: Cecum; Scope: Olympus', 'cecum')):
            with self.subTest(label=label):
                self.assertEqual(extent_of(report('Colonoscopy', COLON_PROSE, label), 'gi.colonoscopy')[:2],
                                 ('performed', extent))
        # a label whose own words deny or doubt the landmark, or name an aim, is no unread extent: the prose decides as
        # before (round 4 routing:9, release:3)
        for label in ('Extent: Cecum not reached | Scope: Olympus', 'Intended extent: Cecum | Scope: Olympus',
                      'Extent: cecum (intended; not reached)', 'Extent: Cecum (intended) | Prep: good',
                      'Extent: cecum was the goal', 'Extent: Cecum | Reached: No', 'Extent: Cecum (attempted) | Scope: Olympus',
                      'Extent: Cecum? | Scope: Olympus', 'Extent: Cecum | Scope: Olympus; not reached',
                      'Extent: Cecum | Scope: Olympus, cecum not reached', 'Extent: Cecum | Scope: Olympus, aborted',
                      'Extent: Cecum, no photos | Complications: None', 'Extent: Cecum (hoped) | Scope: Olympus',
                      'Extent: Cecum (proposed) | Scope: Olympus', 'Extent: Cecum (sought) | Scope: Olympus',
                      'Extent: Cecum, wanted | Scope: Olympus'):
            with self.subTest(label=label):
                self.assertEqual(extent_of(report('Colonoscopy', COLON_PROSE, label), 'gi.colonoscopy')[:2],
                                 ('incomplete', 'incomplete: rectum'))
        self.assertEqual(extent_of(report('EGD', UPPER_PROSE, 'Extent: D2'), 'gi.egd')[:2],
                         ('performed', 'second part of duodenum'))

    def test_a_prose_landmark_that_reaches_the_expected_depth_still_decides(self):
        """Only an incomplete reading is withheld: a prose extent at the cecum stays the extent beside a deeper unread
        label, and a label shallower than the prose landmark changes nothing."""
        text = report('Colonoscopy', 'The colonoscope was advanced to the cecum.', 'Extent: Terminal ileum | Scope: Olympus')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', 'cecum'))
        text = report('Colonoscopy', 'The colonoscope was advanced to the transverse colon.',
                      'Extent: Rectum | Scope: Olympus')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))
        text = report('EGD', 'The endoscope was advanced to the duodenal bulb.', 'Extent: D2 | Scope: Olympus')
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('performed', 'duodenal bulb'))
        # an unread label short of the depth the procedure calls for agrees it was incomplete: the reading stays as it
        # was (an accepted residual: the shallower prose landmark names the extent)
        for procedure, prose, label, expected in (
                ('Colonoscopy', COLON_PROSE, 'Extent: Splenic flexure | Scope: Olympus', 'incomplete: rectum'),
                ('Colonoscopy', COLON_PROSE, 'Extent: Hepatic flexure | Scope: Olympus', 'incomplete: rectum'),
                ('EGD', UPPER_PROSE, 'Extent: stomach | Scope: Olympus', 'incomplete: esophagus')):
            text = report(procedure, prose, label)
            with self.subTest(label=label):
                self.assertEqual(extent_of(text, 'gi.egd' if procedure == 'EGD' else 'gi.colonoscopy')[:2],
                                 ('incomplete', expected))

    def test_only_a_label_that_speaks_for_this_report_withholds_it(self):
        """An unread label answered in the product's addendum speaks for this report, so it withholds the shallower
        landmark's incomplete reading; one in another facility's record never does (round 4c declared:3)."""
        parent = report('Colonoscopy', COLON_PROSE, 'Impression: Normal.')
        text = parent + '\n\nADDENDUM (revision 2, added 2026-10-22 10:00 UTC)\nFurthest extent reached: Cecum | Scope: Olympus\n'
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
        for label in ('Extent: Cecum | Scope: Olympus', 'Extent: Cecum | Complications: None'):
            text = report('Colonoscopy', 'The colonoscope was advanced to the splenic flexure.',
                          'Outside records:\n' + label)
            with self.subTest(label=label):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: splenic flexure'))

    def test_a_negation_earlier_in_the_labels_clause_keeps_the_base_reading(self):
        """Only a negation that sits inside the listed next field is that field's own; one earlier in the label's clause
        may speak of the extent ("Not reached, extent: Cecum | Complications: None"), so the label is not counted unread
        and the reading is the base's."""
        text = report('Colonoscopy', COLON_PROSE, 'Not reached, extent: Cecum | Complications: None')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))

    def test_a_documented_incompleteness_stays_incomplete(self):
        """An incompleteness stated in words is read as before; only the landmark that would name it is withheld."""
        text = report('Colonoscopy', 'The colonoscope was inserted into the rectum. The procedure was aborted because of '
                      'poor preparation.', 'Extent: Cecum | Scope: Olympus')
        status, extent, missing = extent_of(text, 'gi.colonoscopy')
        self.assertEqual(status, 'incomplete')
        self.assertNotEqual(extent, 'incomplete: rectum')


class PlanB2UnreadLabelNarrowingTests(unittest.TestCase):
    """plan:B2 (the lead's narrowing of plan:B, its own weakest spot). plan:B withheld the extent beside a shallower
    landmark whenever an unread label named the expected depth, also where the document itself says that depth was not
    reached ("Extent: Cecum | Scope: Olympus" then "Cecum not reached.") or where the label's tail is a word no list
    reads ("Extent: Cecum (ambition) | Scope: Olympus"): the family read performed with the extent withheld, where
    51457929c read it incomplete, which the document says. The rule now fires only when no landmark beyond the one
    reached is denied in the family's own text (blocked, negated, cancelled, incomplete, or doubted by an unresolved
    negation), and only on a tail it can read as neutral: the label's own value is plain, and what leaves it unread is a
    next cell that opens an equipment, staff or room field (a closed list), or a listed report field whose own answer is
    a negation. Anything else keeps the base reading."""

    DENIALS = ('Cecum not reached.', 'The cecum could not be reached.', 'The colonoscope failed to reach the cecum.',
               'Cecal intubation was not achieved.', 'The transverse colon was not reached.',
               'The appendiceal orifice was not visualized.', 'Unable to reach the cecum because of a tortuous colon.',
               # a negated, cancelled or incomplete mention of the landmark
               'Cecal intubation was not performed.', 'Cecal intubation: not done.', 'No cecal intubation.',
               'Cecal intubation was aborted.', 'Cecal intubation was cancelled.')
    UNLISTED = ('Extent: Cecum (ambition) | Scope: Olympus', 'Extent: Cecum, Olympus scope', 'Extent: Cecum (adult scope)',
                'Extent - cecum, adult scope', 'Extent: Cecum | Ambition: cecum', 'Extent: Cecum | Comment: Olympus',
                'Extent: Cecum (ambition) | Complications: None', 'Extent: Cecum | Scope: Olympus | Aim: TI',
                'Extent: Cecum | Endoscopist: Dr.  Lee', 'Extent: Cecum | Scope: Olympus | Comment: cecum')
    # ordinary findings that name the landmark deny nothing: the claimed input stays fixed beside them
    FINDINGS = ('Findings: No polyps were seen in the cecum.', 'No polyps in the cecum.',
                'Findings: Normal mucosa. No masses or polyps.')

    def test_a_denial_in_the_familys_own_text_keeps_the_base_reading(self):
        for line in self.DENIALS:
            text = report('Colonoscopy', COLON_PROSE, 'Extent: Cecum | Scope: Olympus\n' + line)
            with self.subTest(line=line):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))
        text = report('EGD', UPPER_PROSE, 'Extent: D2 | Scope: Olympus\nThe second part of the duodenum was not reached.')
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('incomplete', 'incomplete: esophagus'))

    def test_an_unlisted_word_in_the_tail_keeps_the_base_reading(self):
        for label in self.UNLISTED:
            text = report('Colonoscopy', COLON_PROSE, label)
            with self.subTest(label=label):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))

    def test_only_a_denial_beyond_the_landmark_reached_keeps_it(self):
        """A doubt about a landmark at or above the one reached says nothing of the depth reached beyond it."""
        text = report('Colonoscopy', 'The colonoscope was advanced to the sigmoid colon.',
                      'Extent: Cecum | Scope: Olympus\nThe rectum could not be examined on retroflexion.')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))

    def test_the_claimed_input_stays_fixed_beside_ordinary_findings(self):
        for findings in self.FINDINGS:
            text = report('Colonoscopy', COLON_PROSE, 'Extent: Cecum | Scope: Olympus', findings)
            with self.subTest(findings=findings):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
                proposal = real(text, ('45378', 'Procedure: Colonoscopy'))[0]['45378']
                self.assertEqual(proposal.status, 'needs_clarification')
                self.assertIn('extent', clarified(proposal))


# --- plan:D: an extent label whose own sentence denies its landmark is never read as reached ------------------------

D_PROSE = 'The colonoscope was advanced to the transverse colon.'


class PlanDDeniedExtentLabelTests(unittest.TestCase):
    """plan:D (high, declared extent label misread, at the base and on plan:B's head). ARCHITECTURE 5.3 reads an extent
    label only when what follows its landmark is plain. "Extent: cecum; not reached" was read as the cecum reached
    (gi.colonoscopy performed, extent 'cecum', 45378 ready with no extent or incomplete check): the ";" ends both the
    label's value (_plain_tail) and the landmark's clause, so the denial after it is never seen. A label whose own
    sentence, past ";" or "," too, denies or doubts its landmark (a negation no finding, complication, other-act or
    qualifier exception explains, a clause cue that is no performance cue, an aim word) is no longer read as reached:
    the shallower prose landmark reads the procedure incomplete, as the line says, or no extent is read. A denial that
    names a deeper landmark or retroflexion ("; TI not intubated") is that one's; a finding denied there ("; no polyps")
    denies nothing; and a full stop or a next report field ends what is read."""

    # plan:D2: only a reach denial (the closed list, _P2_REACH_DENIAL) keeps this reading; the other denials, doubts and
    # aims this list held before ("; ?", "; intended", "; no appendiceal orifice seen", "; aborted", "; appendiceal
    # orifice not seen", "; was not seen", "; no view of the cecum due to poor prep") withhold the extent instead
    # (PlanD2ReachDenialTests.NOT_A_REACH_DENIAL): still never read as reached
    DENIED = ('Extent: cecum; not reached', 'Extent: cecum; not visualized', 'Extent: cecum; not intubated',
              'Extent: cecum; not achieved', 'Extent: cecum; never reached', 'Extent: cecum; unable to intubate',
              'Extent: cecum; was not visualized', 'Extent: cecum; reached: no', 'Extent reached: cecum; not reached',
              '- Extent: cecum; NOT REACHED', 'Extent: terminal ileum; not intubated',
              # a reach denial with its reason, before or after it
              'Extent: cecum; not reached due to poor prep', 'Extent: cecum; not reached, prep poor',
              'Extent: cecum; prep poor, not reached', 'Extent: cecum; prep inadequate, cecum not visualized',
              'Extent: cecum; not reached (poor prep)', 'Extent: cecum; reached: no, biopsies taken',
              # the reason first, with no separator before the denial
              'Extent: cecum; due to poor prep not reached', 'Extent: cecum; poor prep so not reached',
              'Extent: cecum; prep poor therefore not visualized', 'Extent: cecum; patient discomfort, so not reached',
              'Extent: cecum; because of the prep, never reached')
    # read before this item already (the value runs on past these separators), and still not read
    ALREADY = ('Extent: cecum, not reached', 'Extent: cecum - not reached', 'Extent: cecum | not reached',
               'Extent: cecum (not reached)', 'Extent: cecum, aborted')
    # a positive or unrelated rest of the sentence: read as the base reads it
    READ = ('Extent: cecum; photo documented.', 'Extent: cecum; no polyps', 'Extent: cecum; no complications',
            'Extent: cecum; TI not intubated', 'Extent: cecum; retroflexion not performed', 'Extent: cecum. No polyps.',
            'Extent: cecum; complications: none', 'Extent: cecum; was reached easily',
            'Extent: cecum. Repeat colonoscopy in 3 years.', 'Extent: cecum; retroflexion was not possible',
            'Extent: cecum | Prep quality: fair; repeat in 1 year')

    def test_the_claimed_input_is_no_complete_extent(self):
        text = report('Colonoscopy', D_PROSE, 'Extent: cecum; not reached')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))
        proposal = real(text, ('45378', 'Procedure: Colonoscopy'))[0]['45378']
        self.assertEqual({c.id: c.status for c in proposal.checks}.get('service.incomplete'), 'warn')
        # with no prose landmark, no extent is read: the family's extent clarification asks for it
        text = report('Colonoscopy', '', 'Extent: cecum; not reached').replace('Colonoscopy\n\n', 'Colonoscopy\n')
        self.assertIsNone(extent_of(text, 'gi.colonoscopy')[1])
        self.assertIn('extent', clarified(real(text, ('45378', 'Procedure: Colonoscopy'))[0]['45378']))

    def test_every_denial_after_the_separator(self):
        for label in self.DENIED + self.ALREADY:
            text = report('Colonoscopy', D_PROSE, label)
            with self.subTest(label=label):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))

    def test_the_upper_tract_and_a_depth_label(self):
        text = report('EGD', UPPER_PROSE, 'Extent: D2; not reached')
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('incomplete', 'incomplete: esophagus'))
        text = report('EGD', UPPER_PROSE, 'Extent: D2; duodenum not intubated')  # a shallower landmark denied
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('incomplete', 'incomplete: esophagus'))
        text = report('EGD', UPPER_PROSE, 'Extent: D2; D3 not reached')  # a deeper one: D2 stands
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('performed', 'second part of duodenum'))
        text = HEADER + 'Procedure: Flexible sigmoidoscopy\nDepth of insertion: 40 cm; not reached\nFindings: Normal.\n'
        self.assertIsNone(extent_of(text, 'gi.flex_sig')[1])
        text = HEADER + 'Procedure: Flexible sigmoidoscopy\nDepth of insertion: 40 cm; photo documented.\nFindings: Normal.\n'
        self.assertEqual(extent_of(text, 'gi.flex_sig')[1], '40 cm')

    def test_a_positive_or_unrelated_rest_reads_as_the_base_reads_it(self):
        for label in self.READ:
            text = report('Colonoscopy', D_PROSE, label)
            with self.subTest(label=label):
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', 'cecum'))
        text = report('Colonoscopy', D_PROSE, 'Extent: Cecum | Prep quality: Good | Withdrawal time: 9 min')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', 'cecum'))  # round 4c declared:11

    def test_an_addendum_answer_is_read_the_same_way(self):
        parent = (HEADER + 'Procedure: Colonoscopy\nIndication: Positive FIT.\nFindings: A 6 mm sigmoid polyp was removed with '
                  'a cold snare.\nPlan: Repeat colonoscopy in 5 years.\n\n\nADDENDUM (revision 2, added 2026-10-22 10:00 UTC)\n')
        self.assertIsNone(extent_of(parent + 'Furthest extent reached: cecum; not reached.\n', 'gi.colonoscopy')[1])
        self.assertEqual(extent_of(parent + 'Furthest extent reached: cecum.\n', 'gi.colonoscopy')[1], 'cecum')

    def test_a_denying_label_also_denies_for_the_unread_label_rule(self):
        """plan:B2: a second label that denies the cecum in its own sentence keeps the base reading."""
        text = report('Colonoscopy', COLON_PROSE, 'Extent: Cecum | Scope: Olympus\nExtent: cecum; not reached')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))


# --- plan:D2: plan:D's refusal reads a shallower landmark incomplete only on a reach denial --------------------------

D2_TECH = 'Technique: The colonoscope was inserted into the rectum and advanced without difficulty.'
FLEX = 'Flexible sigmoidoscopy'


def flex_report(prose, label):
    return HEADER + f'Procedure: {FLEX}\n' + (prose + '\n' if prose else '') + label + '\nFindings: Normal.\n'


def held_for_the_extent(text, code, cite):
    """The code is held for the family's extent clarification, with no incomplete-procedure check."""
    proposal = real(text, (code, cite))[0][code]
    return (proposal.status == 'needs_clarification' and 'extent' in clarified(proposal)
            and check_of(proposal, 'service.incomplete') is None)


class PlanD2ReachDenialTests(unittest.TestCase):
    """plan:D2 (the lead's narrowing of plan:D, its own d2 over-hold). plan:D refuses to read an extent label as reached
    when its own sentence denies, doubts or aims at its landmark; the shallower prose landmark then decided the extent.
    "Technique: The colonoscope was inserted into the rectum and advanced without difficulty. / Extent: cecum; no biopsies
    taken." so read gi.colonoscopy incomplete, extent 'incomplete: rectum', 45378 ready with service.incomplete warn: a
    complete colonoscopy reported as stopped at the rectum, where 51457929c read the cecum. A refused label now lets a
    shallower landmark decide only when its own sentence states that the landmark was not reached - a closed list of
    reach denials (_P2_REACH_DENIAL: not reached, not visualized / visualised, not intubated, not achieved, could not be
    advanced / reached, unable to advance / reach / intubate, failed to reach / advance, short of, reached: no, and their
    word orders after a reason), whose subject and object are the landmark (_P2_reach_names_the_landmark). With any other
    denial, doubt or aim word, a refused label deeper than the deepest landmark reached withholds the extent: the
    family's extent clarification asks for it, never incomplete - the outcome of plan:B's unread label. A denial of the
    landmark elsewhere in the family's text still decides (plan:B2's guard). A flexible sigmoidoscopy's refused depth
    label never lets another value decide either: there plan:D had let the prose's "30 cm" release 45330, which the base
    held for its conflicting values."""

    # no reach denial: withheld; the family reads performed, as the base reads it
    NOT_A_REACH_DENIAL = ('no biopsies taken', 'prep not adequate', 'prep fair?', 'consent not signed', 'biopsy intended',
                          'patient declined further advancement', 'polypectomy not performed', 'bleeding not seen',
                          'no further advancement', '?', 'intended', 'no appendiceal orifice seen',
                          'appendiceal orifice not seen', 'was not seen', 'no view of the cecum due to poor prep',
                          'hemostasis not achieved', 'not visualized well', 'possibly not reached', 'probably not reached',
                          'not reached?', 'may not have been reached', 'attempted', 'not achieved hemostasis', 'incomplete',
                          'unsuccessful', 'failed', 'due to poor prep possibly not reached', 'polyp: not reached',
                          'reached: no biopsies taken')
    # ... and these, which the base already reads incomplete by their own words (an act that failed, "aborted"): the
    # family keeps that reading, the extent is withheld
    NOT_A_REACH_DENIAL_INCOMPLETE = ('aborted', 'unable to reach the lesion', 'the cecal lesion could not be reached',
                                     'lesion could not be reached', 'due to a lesion that could not be reached',
                                     'unable to reach the polyp for resection', 'failed to advance the guidewire',
                                     'unable to advance to the lesion')
    # the closed list: plan:D's reading stands, incomplete at the shallower prose landmark
    REACH_DENIAL = ('not reached', 'not visualized', 'not visualised', 'not intubated', 'not achieved',
                    'could not be advanced', 'could not be reached', 'unable to advance', 'unable to reach',
                    'unable to intubate', 'failed to reach', 'failed to advance', 'never reached', 'was not visualized',
                    'reached: no', 'did not reach the cecum', 'cannot be reached', 'has not been reached',
                    "couldn't be reached", 'cecal intubation not achieved', 'scope could not be advanced',
                    'cecum was not reached', 'unable to advance further', 'not reached at all',
                    'not reached despite position changes', 'owing to looping not reached', 'short of the cecum',
                    'stopped short of the cecum', 'unable to advance the scope', 'cecum: not reached',
                    'could not be advanced beyond the transverse colon', 'unable to advance past the hepatic flexure',
                    # the reason first, after it, or in its own segment
                    'due to poor prep not reached', 'poor prep so not reached', 'prep poor therefore not visualized',
                    'patient discomfort, so not reached', 'because of the prep, never reached',
                    'not reached due to poor prep', 'not reached (poor prep)', 'prep inadequate, cecum not visualized',
                    'not intubated - poor prep', 'not reached, prep poor', 'prep poor, not reached',
                    'reached: no, biopsies taken')

    def test_the_claimed_input_is_held_for_the_extent(self):
        text = report('Colonoscopy', D2_TECH, 'Extent: cecum; no biopsies taken.')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
        self.assertTrue(held_for_the_extent(text, '45378', 'Procedure: Colonoscopy'))
        # without the prose line: the same hold, as on plan:D
        text = report('Colonoscopy', '', 'Extent: cecum; no biopsies taken.').replace('Colonoscopy\n\n', 'Colonoscopy\n')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
        self.assertTrue(held_for_the_extent(text, '45378', 'Procedure: Colonoscopy'))

    def test_no_reach_denial_withholds_the_extent(self):
        for prose in (D2_TECH, D_PROSE, COLON_PROSE):
            for rest in self.NOT_A_REACH_DENIAL:
                with self.subTest(prose=prose, rest=rest):
                    text = report('Colonoscopy', prose, 'Extent: cecum; ' + rest)
                    self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
            for rest in self.NOT_A_REACH_DENIAL_INCOMPLETE:
                with self.subTest(prose=prose, rest=rest):
                    text = report('Colonoscopy', prose, 'Extent: cecum; ' + rest)
                    self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', None))
        text = report('Colonoscopy', D_PROSE, 'Extent: cecum; prep fair?')
        self.assertTrue(held_for_the_extent(text, '45378', 'Procedure: Colonoscopy'))

    def test_a_reach_denial_keeps_plan_d_reading(self):
        for rest in self.REACH_DENIAL:
            with self.subTest(rest=rest):
                text = report('Colonoscopy', D_PROSE, 'Extent: cecum; ' + rest)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))
        for rest in ('not reached', 'unable to advance', 'due to poor prep not reached', 'short of the cecum'):
            with self.subTest(rest=rest, prose='rectum'):
                text = report('Colonoscopy', COLON_PROSE, 'Extent: cecum; ' + rest)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))
        # a plain or positive rest is still read as the base reads it, "short of" with no landmark too
        for rest in ('photo documented.', 'no polyps', 'short of breath', 'TI not intubated'):
            with self.subTest(rest=rest):
                text = report('Colonoscopy', D_PROSE, 'Extent: cecum; ' + rest)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', 'cecum'))

    def test_the_upper_tract(self):
        for label in ('Extent: D2; no biopsies taken', 'Extent: D2; consent not signed',
                      'Extent: second part of the duodenum; intended'):
            with self.subTest(label=label):
                text = report('EGD', UPPER_PROSE, label)
                self.assertEqual(extent_of(text, 'gi.egd')[:2], ('performed', None))
                self.assertTrue(held_for_the_extent(text, '43239', 'Procedure: EGD'))
        for label in ('Extent: D2; not reached', 'Extent: D2; unable to advance', 'Extent: D2; duodenum not intubated'):
            with self.subTest(label=label):
                self.assertEqual(extent_of(report('EGD', UPPER_PROSE, label), 'gi.egd')[:2], ('incomplete', 'incomplete: esophagus'))

    def test_a_label_short_of_the_expected_depth(self):
        # a shallower prose landmark never decides against a refused label, short of the cecum or not
        text = report('Colonoscopy', COLON_PROSE, 'Extent: transverse colon; no biopsies taken')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
        text = report('Colonoscopy', COLON_PROSE, 'Extent: transverse colon; not reached')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))
        # a deeper prose landmark still does, and one as deep as the label's
        for label in ('Extent: sigmoid colon; no biopsies taken', 'Extent: transverse colon; no biopsies taken'):
            with self.subTest(label=label):
                text = report('Colonoscopy', D_PROSE, label)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))

    def test_a_landmark_that_is_no_label_is_not_doubted(self):
        """Only an extent label plan:D refuses withholds: a bare landmark before such a rest reads as the base reads it."""
        for line in ('Cecum; prep fair?', 'Cecum; no biopsies taken'):
            with self.subTest(line=line):
                self.assertEqual(extent_of(report('Colonoscopy', D_PROSE, line), 'gi.colonoscopy')[:2],
                                 ('incomplete', 'incomplete: transverse colon'))

    def test_a_denial_in_the_familys_own_text_still_decides(self):
        for prose, label in ((COLON_PROSE + '\nThe cecum was not reached.', 'Extent: cecum; no biopsies taken'),
                             (COLON_PROSE, 'Extent: cecum; no biopsies taken\nCecum not reached.'),
                             (COLON_PROSE + '\nThe cecum could not be reached.', 'Extent: cecum; prep fair?')):
            with self.subTest(prose=prose, label=label):
                self.assertEqual(extent_of(report('Colonoscopy', prose, label), 'gi.colonoscopy')[:2],
                                 ('incomplete', 'incomplete: rectum'))

    # a denial in the segment that names a deeper landmark, retroflexion or a passage of the ileocecal valve is that
    # one's: the label is read as the base reads it (the cecum reached; the family's status is the base's own reading)
    THEIRS = ('unable to intubate the TI', 'never reached the TI', 'could not intubate the terminal ileum',
              'failed to intubate the TI due to looping', 'no TI intubation', 'unable to retroflex',
              'unable to perform retroflexion', 'unable to intubate the ileocecal valve', 'could not pass the IC valve',
              "ileocecal valve couldn't be traversed", 'IC valve not intubated', 'prep poor, unable to intubate the TI')

    def test_a_deeper_landmarks_own_segment_is_its_own(self):
        for rest in self.THEIRS:
            with self.subTest(rest=rest):
                text = report('Colonoscopy', D_PROSE, 'Extent: cecum; ' + rest)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[1], 'cecum')
        # a reach denial in a segment of its own before it still denies the label
        for rest in ('not reached; TI not intubated', 'not reached, unable to intubate the TI',
                     'cecum not reached - TI not seen', 'not reached; unable to retroflex'):
            with self.subTest(rest=rest):
                text = report('Colonoscopy', D_PROSE, 'Extent: cecum; ' + rest)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))
        # a terminal ileum label's own denial of passing the valve is its own: incomplete at the prose landmark
        text = report('Colonoscopy', D_PROSE, 'Extent: terminal ileum; unable to intubate the ileocecal valve')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: transverse colon'))
        # the D2 label is read (the base's own reading: "unable to advance" reads the procedure incomplete)
        text = report('EGD', UPPER_PROSE, 'Extent: D2; unable to advance to D3')
        self.assertEqual(extent_of(text, 'gi.egd')[:2], ('incomplete', 'incomplete: second part of duodenum'))

    def test_a_denial_beyond_the_labels_landmark_elsewhere_decides_nothing(self):
        """The guard reads only denials of a landmark up to the doubted label's own: "TI not intubated." does not say
        the cecum was not reached."""
        for prose, label in ((COLON_PROSE, 'Extent: cecum; no biopsies taken\nTI not intubated.'),
                             (COLON_PROSE, 'Extent: cecum; no biopsies taken; TI not intubated'),
                             (COLON_PROSE, 'Extent: cecum; prep fair?\nThe terminal ileum was not intubated.'),
                             # the scope stood at the valve: a passage of it denied is the terminal ileum's
                             (COLON_PROSE, 'Extent: cecum; prep fair?\nUnable to intubate the ileocecal valve.'),
                             (D_PROSE, 'Extent: cecum; no biopsies taken\nThe ileocecal valve could not be traversed.')):
            with self.subTest(label=label):
                text = report('Colonoscopy', prose, label)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
                self.assertTrue(held_for_the_extent(text, '45378', 'Procedure: Colonoscopy'))
        for denial in ('The cecum was not reached.', 'The ileocecal valve was not reached; unable to intubate the IC valve.'):
            with self.subTest(denial=denial):
                text = report('Colonoscopy', COLON_PROSE, 'Extent: cecum; prep fair?\n' + denial)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))
        # a denial of a landmark no deeper than the one reached says nothing of the label's: the extent is withheld (the
        # family's status is the base's own reading of that sentence)
        text = report('Colonoscopy', D_PROSE + '\nThe sigmoid colon was not reached on the first pass.',
                      'Extent: cecum; no biopsies taken')
        self.assertIsNone(extent_of(text, 'gi.colonoscopy')[1])
        # without the label the base reads a terminal ileum not intubated as the procedure incomplete, as before
        text = report('Colonoscopy', COLON_PROSE, 'The terminal ileum was not intubated.')
        self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('incomplete', 'incomplete: rectum'))

    def test_the_two_rules_agree(self):
        """plan:B's unread label and plan:D2's refused one read the same, and hold 45378 the same way."""
        for label in ('Extent: Cecum | Scope: Olympus', 'Extent: cecum; no biopsies taken'):
            with self.subTest(label=label):
                text = report('Colonoscopy', COLON_PROSE, label)
                self.assertEqual(extent_of(text, 'gi.colonoscopy')[:2], ('performed', None))
                self.assertTrue(held_for_the_extent(text, '45378', 'Procedure: Colonoscopy'))

    def test_an_addendum_answer(self):
        parent = (HEADER + 'Procedure: Colonoscopy\nIndication: Positive FIT.\nFindings: The colonoscope was advanced to the '
                  'transverse colon. A 6 mm sigmoid polyp was removed with a cold snare.\nPlan: Repeat colonoscopy in 5 '
                  'years.\n\n\nADDENDUM (revision 2, added 2026-10-22 10:00 UTC)\n')
        self.assertEqual(extent_of(parent + 'Furthest extent reached: cecum; no biopsies taken.\n', 'gi.colonoscopy')[:2],
                         ('performed', None))
        self.assertEqual(extent_of(parent + 'Furthest extent reached: cecum; not reached.\n', 'gi.colonoscopy')[:2],
                         ('incomplete', 'incomplete: transverse colon'))
        self.assertEqual(extent_of(parent + 'Furthest extent reached: cecum.\n', 'gi.colonoscopy')[:2], ('performed', 'cecum'))

    def test_a_flexible_sigmoidoscopy_depth_label(self):
        cite = 'Procedure: ' + FLEX
        # another value never decides beside a refused depth label: plan:D released 45330 here, the base held it
        for label in ('Depth of insertion: 40 cm; no biopsies taken', 'Depth of insertion: 40 cm; not reached'):
            with self.subTest(label=label):
                text = flex_report('The scope was advanced to 30 cm.', label)
                self.assertIsNone(extent_of(text, 'gi.flex_sig')[1])
                self.assertTrue(held_for_the_extent(text, '45330', cite))
        # the same value as the label's: read as the base reads it
        text = flex_report('The scope was advanced to 40 cm.', 'Depth of insertion: 40 cm; no biopsies taken')
        self.assertEqual(extent_of(text, 'gi.flex_sig')[1], '40 cm')
        # a landmark reached beside it: withheld unless the label's own sentence denies the depth
        for label in ('Depth of insertion: 40 cm; no biopsies taken', 'Extent: descending colon; no biopsies taken'):
            with self.subTest(label=label):
                text = flex_report('The scope was advanced to the sigmoid colon.', label)
                self.assertIsNone(extent_of(text, 'gi.flex_sig')[1])
                self.assertTrue(held_for_the_extent(text, '45330', cite))
        for label in ('Depth of insertion: 40 cm; not reached', 'Extent: descending colon; not reached'):
            with self.subTest(label=label):
                text = flex_report('The scope was advanced to the sigmoid colon.', label)
                self.assertEqual(extent_of(text, 'gi.flex_sig')[1], 'sigmoid colon')
        text = flex_report('The scope was advanced to the sigmoid colon.', 'Extent: descending colon.')
        self.assertEqual(extent_of(text, 'gi.flex_sig')[1], 'descending colon')


# --- plan:E: a held performance statement outranks another encounter's mention in the family aggregate ---------------

def e_office(lines):
    return (HEADER + 'Place of service: Office (POS 11)\n' + VISIT + '\nChief complaint: Heartburn.\nHistory of present '
            'illness: Heartburn for 8 weeks.\n' + lines + '\nMedical decision making: moderate.\n')


class PlanEHeldStatementRankingTests(unittest.TestCase):
    """plan:E (high, declared ranking). ARCHITECTURE 5.3: a family's status ranks what its mentions say of today's
    service (incomplete, cancelled, negated today, uncertain) before what they say of other encounters (never before,
    historical, planned). "Assessment and plan: EGD was performed with biopsies. Repeat EGD in 3 months." read gi.egd
    PLANNED and 99214 ready, although without the repeat sentence gi.egd is uncertain and the E/M held: both plan
    mentions say no today, so both were 'away', and _aggregate's last step ranked the elsewhere statuses (planned,
    historical, negated) with nothing left to outrank them. An explicit performance statement held by its section (an
    uncertain reading carrying a 'performed:' cue other than the E/M documentation's, or plan:A2's hedged-statement hold)
    is today's possible service (5.6 counts it for the E/M hold), so it now ranks before those other-encounter statuses
    in a procedure family's aggregate: uncertain, exactly as without the other mention. The E/M family is not read so."""

    HELD = ('Assessment and plan: EGD was performed with biopsies. Repeat EGD in 3 months.',
            'Plan: EGD was performed with biopsies. Repeat EGD in 3 months.',
            'Assessment and plan: Repeat EGD in 3 months. EGD was performed with biopsies.',
            'Assessment and plan: EGD was performed with biopsies. EGD in 3 months to reassess.',
            'Assessment and plan: EGD was performed with biopsies. Prior EGD in 2019 was normal.',
            'Assessment and plan: EGD was performed with biopsies, eosinophilic esophagitis versus reflux. Repeat EGD in 3 '
            'months.',
            'Indication: EGD was performed and showed a stricture.\nAssessment and plan: Repeat EGD in 3 months.')
    READY = ('Assessment and plan: Repeat EGD in 3 months.', 'Assessment and plan: Discussed EGD; will schedule.',
             'Assessment and plan: EGD in 2024 was normal. Repeat EGD in 3 months.',
             'Assessment and plan: Prior EGD was performed and showed Barrett esophagus. Repeat EGD in 3 years.',
             'Assessment and plan: EGD was performed in 2024 and showed Barrett esophagus. Repeat EGD in 3 years.',
             'Assessment and plan: Possible EGD if symptoms persist. Repeat EGD in 3 months.',
             'Past medical history: EGD was performed and showed Barrett esophagus.\nAssessment and plan: Repeat EGD in 3 '
             'years.',
             'Assessment and plan: Possible EGD today if symptoms persist. Repeat EGD in 3 months.',
             'Assessment and plan: Discussed colonoscopy today; she will think about it. Colonoscopy in 3 years.')

    def test_the_claimed_input_reads_as_without_the_repeat(self):
        with_repeat = e_office(self.HELD[0])
        without = e_office('Assessment and plan: EGD was performed with biopsies.')
        self.assertEqual(family(with_repeat, 'gi.egd'), 'uncertain')
        self.assertEqual(family(without, 'gi.egd'), 'uncertain')
        self.assertTrue(held_for_a_same_day_procedure(visit_of(with_repeat)))
        self.assertTrue(held_for_a_same_day_procedure(visit_of(without)))

    def test_the_variants_hold_the_visit(self):
        for plan in self.HELD:
            text = e_office(plan)
            with self.subTest(plan=plan):
                self.assertEqual(family(text, 'gi.egd'), 'uncertain')
                self.assertTrue(held_for_a_same_day_procedure(visit_of(text)), plan)

    def test_other_sections_and_other_other_encounter_mentions(self):
        text = e_office('History of present illness: Colonoscopy was performed this morning and showed polyps. Prior '
                        'colonoscopy in 2019 showed polyps.\nAssessment and plan: Fiber.')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
        self.assertTrue(held_for_a_same_day_procedure(visit_of(text)))
        text = e_office('Assessment and plan: Colonoscopy was completed. No further colonoscopy is needed.')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
        self.assertTrue(held_for_a_same_day_procedure(visit_of(text)))

    def test_the_controls_and_the_pinned_releases_stay_ready(self):
        for plan in self.READY:
            text = e_office(plan)
            with self.subTest(plan=plan):
                self.assertTrue(visit_ready(visit_of(text)), plan)

    def test_the_controls_keep_their_family_reading(self):
        """With no held performance statement, the aggregate ranks as before; a denial of today's service still wins."""
        for plan, expected in (('Assessment and plan: Repeat EGD in 3 months.', 'planned'),
                               ('Assessment and plan: Possible EGD if symptoms persist. Repeat EGD in 3 months.', 'planned'),
                               ('Assessment and plan: Discussed EGD; will schedule.', 'uncertain'),
                               ('Assessment and plan: Prior EGD was performed and showed Barrett esophagus. Repeat EGD in 3 '
                                'years.', 'historical'),
                               ('Assessment and plan: EGD was performed with biopsies. No EGD was done today.', 'negated'),
                               # a history section's statement reads historical, its performance cue kept: not held
                               ('Past medical history: EGD was performed and showed Barrett esophagus.\nAssessment and plan: '
                                'Repeat EGD in 3 years.', 'historical')):
            with self.subTest(plan=plan):
                self.assertEqual(family(e_office(plan), 'gi.egd'), expected)

    def test_the_e_m_family_is_not_ranked_so(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nPlan: Office visit was '
                'performed. Follow-up office visit in 3 months.\n')
        self.assertEqual(family(text, 'gi.office_em'), 'planned')

    def test_the_repeat_itself_stays_planned_and_its_code_excluded(self):
        text = e_office(self.HELD[0])
        self.assertEqual(read(text, 'Repeat EGD in 3 months.')[0], 'planned')
        self.assertEqual(run_engine(text, [('43235', 'Repeat EGD in 3 months.')])['43235'].bucket, 'excluded')
        proposal = run_engine(text, [('43239', 'EGD was performed with biopsies.')])['43239']
        self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))


# --- plan:C: a line listed under a denying label is held whatever it names --------------------------------------------

C_FINDINGS = 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n'
C_POLYP = 'Cold snare polypectomy of the 6 mm sigmoid polyp.'
LISTED_UNDER = 'uncertain: listed under '


def c_note(lines):
    return HEADER + C_FINDINGS + lines + '\n'


class PlanCDenyingLabelTests(unittest.TestCase):
    """plan:C (high, declared misread). ARCHITECTURE 5.3: a service listed under a label that denies performance
    ("Procedures not performed:"), or under a verbless denying heading ("Cancelled procedures:"), is held. The label was
    read (detect._denying_label_above) only for a SERVICE mention, through _later_denial; a line that names an
    intervention ("Cold snare polypectomy of the 6 mm sigmoid polyp.") was read by its section default, performed, and
    45385 citing it was ready. Every performed reading of a line under a denying label - read exactly as
    _denying_label_above reads it - is now held (uncertain, "listed under '<label>', a label that denies performance",
    a doubt), whatever it names; a service mention keeps its denial reading; nothing is newly negated or excluded. A
    denying label led by a box of any state ("[ ] Procedures not performed:") is read as one too, for every reader of
    the label: an unchecked one may be an unselected option, so holding what is listed under it is the safe reading."""

    HELD = (('Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('Procedures not performed:\n- ' + C_POLYP, C_POLYP, '45385'),
            ('Not done:\n' + C_POLYP, C_POLYP, '45385'),
            ('Procedure(s) not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('1. Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('Procedures not performed today:\n' + C_POLYP, C_POLYP, '45385'),
            ('Procedures not performed:\nBiopsy of the antrum.', 'Biopsy of the antrum.', '45380'),
            ('Procedures not performed:\nBiopsy.\n' + C_POLYP, C_POLYP, '45385'),
            ('Procedures not performed:\n' + C_POLYP + '\nImpression: Sigmoid polyp.', C_POLYP, '45385'),
            ('Procedures not performed:\nCold snare polypectomy was performed.', 'Cold snare polypectomy was performed.',
             '45385'),
            ('Cancelled procedures:\nCold snare polypectomy was performed.', 'Cold snare polypectomy was performed.',
             '45385'),
            ('Procedures not performed:\n☑ ' + C_POLYP, C_POLYP, '45385'),
            ('☐ Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('☒ Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('[ ] Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'),
            ('[x] Procedures not performed:\n- ' + C_POLYP, C_POLYP, '45385'),
            ('[?] Procedures not performed:\n' + C_POLYP, C_POLYP, '45385'))

    def assert_held(self, text, cite, code):
        status, cues = read(text, cite)
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(cues[0].startswith(LISTED_UNDER), cues)
        self.assertFalse(any(c.startswith('uncertain: no performance evidence') for c in cues), cues)
        proposal = run_engine(text, [(code, cite)])[code]
        self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))

    def test_the_claimed_line_and_its_variants_are_held(self):
        for lines, cite, code in self.HELD:
            with self.subTest(lines=lines):
                self.assert_held(c_note(lines), cite, code)

    def test_a_service_under_the_label_keeps_its_denial_reading(self):
        text = c_note('Procedures not performed:\nEGD.')
        status, cues = read(text, 'EGD.')
        self.assertEqual(status, 'uncertain')
        self.assertTrue(cues[0].startswith('uncertain: section silent:'), cues)
        # and with its own performance cue, or under a box-led label, it is held too, never performed
        for lines in ('Procedures not performed:\nEGD was performed.', '☐ Procedures not performed:\nEGD.'):
            text = c_note(lines)
            with self.subTest(lines=lines):
                self.assertEqual(read(text, 'EGD')[0], 'uncertain')
                self.assertNotIn(family(text, 'gi.egd'), ('performed', 'incomplete') + NOT_TODAY)

    def test_never_newly_negated_or_excluded(self):
        """An unchecked item under the label stays negated (the box contract), as at the base; nothing else is."""
        text = c_note('Procedures not performed:\n☐ ' + C_POLYP)
        self.assertEqual(read(text, C_POLYP)[0], 'negated')
        for lines, cite, code in self.HELD:
            text = c_note(lines)
            with self.subTest(lines=lines):
                self.assertNotEqual(run_engine(text, [(code, cite)])[code].bucket, 'excluded')

    def test_the_list_ends_where_the_label_reader_ends_it(self):
        """A blank line, another label or another section ends what is listed under the label; a line on the label's
        own line, a non-denying label and an unlabelled line read as before."""
        for lines in ('Procedures not performed:\n\n' + C_POLYP, 'Procedures not performed:\nBiopsy.\nInterventions:\n' + C_POLYP,
                      'Procedures not performed:\nBiopsy.\nImpression: ' + C_POLYP, 'Interventions:\n' + C_POLYP, C_POLYP,
                      'Procedures performed:\n' + C_POLYP):
            text = c_note(lines)
            with self.subTest(lines=lines):
                self.assertFalse(read(text, C_POLYP)[1][0].startswith(LISTED_UNDER), read(text, C_POLYP))
        text = c_note('Procedures not performed: ' + C_POLYP)
        self.assertEqual(read(text, C_POLYP)[0], 'uncertain')  # its own clause's negation, as at the base

    def test_the_hold_is_a_doubt_that_the_section_evidence_cannot_outrank(self):
        """A service stated performed under the label contradicts the family's section evidence elsewhere: the family is
        never performed through the heading alone (round 4b's lesson: a hold that replaces a denial counts as doubt)."""
        text = HEADER + 'Procedure: EGD\nFindings: Normal.\nProcedures not performed:\nEGD was performed.\n'
        status, cues = read(text, 'EGD was performed.')
        self.assertEqual(status, 'uncertain')
        self.assertTrue(cues[0].startswith(LISTED_UNDER), cues)
        self.assertNotIn(family(text, 'gi.egd'), ('performed', 'incomplete'))

    def test_an_e_m_documentation_line_is_never_held_by_it(self):
        text = (HEADER + 'Place of service: Office (POS 11)\n' + VISIT + '\nMedical decision making:\nNot performed:\n'
                'Moderate complexity.\n')
        status, cues = read(text, 'Moderate complexity.')
        self.assertEqual(status, 'performed', cues)

    def test_the_family_and_its_other_lines_are_unchanged(self):
        text = c_note('Procedures not performed:\n' + C_POLYP)
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertEqual(read(text, 'The colonoscope was advanced to the cecum.')[0], 'performed')
        self.assertTrue(ready(run_engine(text, [('45378', 'The colonoscope was advanced to the cecum.')])['45378']))


if __name__ == '__main__':
    unittest.main()
