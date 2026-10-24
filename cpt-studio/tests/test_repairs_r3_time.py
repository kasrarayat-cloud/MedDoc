"""Regressions for refutation round 3 over routing's time, history and today readings (the TIME repairs of round 3b).

Each class reproduces one confirmed finding (routing:N, validation:N or contract:N in the round-3 triage) from its
exact input, adds the variants the finding and its verifier list, and pins the positive controls an over-correction
would break. Routing runs for real, for the document's own service date and through the JSON round trip the pipeline
applies; the real validation engine assesses provider-shaped selections. Synthetic text only; pure functions.

The hold-only rule (round-3b contract, section 1) governs every new wording rule here: it may move a reading only to
uncertain. The exceptions are the regression repairs, which restore the reading an ordinary note had at 57b4b3747, and
the one release this round allows (a plan-section performance statement that says today, routing:26).
"""
import unittest

from studio.gi.detect import status_for_span
from tests.test_repairs_status_r2_routing import (HEADER, check, clarified, fact_value, family, read, ready, routed,
                                                  run_engine)

NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')
POSITIVE = ('performed', 'incomplete')
OFFICE_HEAD = HEADER + 'Place of service: Office (POS 11)\n'


def unproposed(result):
    return next(c for c in result.encounter_checks if c.id == 'services.unproposed')


# --- routing:0 ---------------------------------------------------------------------------------------------------

ROUTING0_FINDINGS = ('Findings: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold '
                     'snare.\n')
ROUTING0_POLYP = 'A 6 mm polyp was removed with a cold snare.'
ROUTING0_LINES = (
    'Colonoscopy with cold snare polypectomy for a positive FIT last month.',
    'Colonoscopy with cold snare polypectomy for iron deficiency anemia diagnosed last month.',
    'Colonoscopy with cold snare polypectomy for a colonic mass seen on CT last week.',
    'Colonoscopy with cold snare polypectomy for an abnormal CT done at an outside hospital.',
    'Colonoscopy with cold snare polypectomy for a mass found on a CT colonography performed elsewhere.',
    'Colonoscopy with cold snare polypectomy for anemia diagnosed last year.',
    'Colonoscopy with cold snare polypectomy for an abnormal CT the previous week.',
    'Colonoscopy with cold snare polypectomy for a polyp seen by her previous gastroenterologist.',
    'Colonoscopy with cold snare polypectomy today for a positive FIT last month.',
    'Colonoscopy with cold snare polypectomy for a positive CT colonography performed elsewhere.',
)
ROUTING0_VISITS = (
    'Established patient office visit to review a CT scan done last week.',
    'Established patient office visit today to review a CT scan done last week.',
    'Established patient office visit for anemia diagnosed last month.',
    'Established patient office visit to discuss a CT from an outside hospital.',
    'Established patient office visit for a positive FIT last month.',
)


def routing0_office(visit):
    return (OFFICE_HEAD + visit + '\nChief complaint: GI symptoms.\nAssessment: Stable.\n'
            'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


class Routing0TimeOfAnotherThingTests(unittest.TestCase):
    """routing:0 (critical, a regression from round 2b status:8). The relative-time and outside-place history cues
    ('last month', 'elsewhere'; 'ago' read the same way) attached to the service named beside a test, a result or a
    diagnosis: ordinary procedure lines and E/M visit statements read historical and their codes were excluded. A cue
    is the service's only when it tells the time of the service's own act; one that trails a test, a result or a
    diagnosis is that thing's, and an E/M visit statement is never demoted by the round-2b cues."""

    def test_the_procedure_lines_read_performed(self):
        for line in ROUTING0_LINES:
            text = HEADER + 'Procedure: ' + line + '\n' + ROUTING0_FINDINGS
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                status, cues = read(text, line)
                self.assertEqual(status, 'performed', cues)
                for evidence in (line, ROUTING0_POLYP):
                    proposals, _ = run_engine(text, [('45385', evidence)])
                    self.assertTrue(ready(proposals['45385']),
                                    (evidence, proposals['45385'].exclusion_reason, clarified(proposals['45385'])))

    def test_an_egd_line_for_a_diagnosis_reads_performed(self):
        line = 'EGD with biopsy for iron deficiency anemia diagnosed last month.'
        text = HEADER + 'Procedure: ' + line + '\nFindings: The gastroscope was advanced to the second part of the ' \
                                              'duodenum. Biopsies were taken from the antrum.\n'
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        proposals, _ = run_engine(text, [('43239', line)])
        self.assertTrue(ready(proposals['43239']), proposals['43239'].exclusion_reason)

    def test_an_office_visit_statement_is_never_demoted(self):
        for visit in ROUTING0_VISITS:
            text = routing0_office(visit)
            with self.subTest(visit=visit):
                status, cues = read(text, visit)
                self.assertEqual(status, 'performed', cues)
                proposals, result = run_engine(text, [('99214', visit)])
                self.assertTrue(ready(proposals['99214']), proposals['99214'].exclusion_reason)
                self.assertNotIn('Office / outpatient evaluation and management', unproposed(result).detail)

    def test_no_round_2b_cue_demotes_an_office_visit_statement(self):
        """Not even one no test precedes: the statement is the note's own visit (the round-3b brief)."""
        for visit in ('Established patient office visit following an emergency department stay last week.',
                      'Established patient office visit with records from another hospital.'):
            text = routing0_office(visit)
            with self.subTest(visit=visit):
                status, cues = read(text, visit)
                self.assertEqual(status, 'performed', cues)

    def test_the_services_own_history_stays_historical(self):
        for line in ('EGD was performed last month at an outside hospital.', 'She underwent EGD last year.',
                     'An EGD was done elsewhere.', 'Last month she underwent EGD.', 'EGD two years ago was normal.',
                     'Colonoscopy with polypectomy last year.', 'EGD was performed by her previous gastroenterologist.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, 'EGD' if 'EGD' in line else 'Colonoscopy')
                self.assertEqual(status, 'historical', cues)

    def test_a_cue_whose_owner_is_unclear_holds(self):
        """Neither the service's own act nor a test stands before the cue: held for clarification, never excluded
        and never performed."""
        for line in ('EGD for dysphagia last month.', 'Colonoscopy with removal of a sessile polyp two years ago.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, line.split()[0])
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(any(line.split()[-2] in c or 'ago' in c for c in cues), cues)

    def test_a_pre_existing_cue_after_a_test_holds_and_never_releases(self):
        """'ago' was read at 57b4b3747, so its exclusion is not a round-2b regression: after a test it now holds."""
        text = HEADER + 'Procedure: Colonoscopy with cold snare polypectomy for a positive FIT two weeks ago.\n'
        status, cues = read(text, 'Colonoscopy')
        self.assertEqual(status, 'uncertain', cues)

    def test_the_services_own_history_beside_today_holds(self):
        for line in ('EGD was performed today at an outside hospital.', 'Today she underwent EGD at an outside hospital.',
                     'EGD at an outside hospital today.', 'Today she underwent EGD last month.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, 'EGD')
                self.assertEqual(status, 'uncertain', cues)
        # a today marker of another service's group does not touch this one's history
        text = HEADER + 'Procedure: Colonoscopy today; she underwent EGD last year and colonoscopy today.\n'
        self.assertEqual(read(text, 'EGD')[0], 'historical')

    def test_a_symptoms_time_and_a_request_are_still_not_history(self):
        for line in ('Colonoscopy for rectal bleeding since last month.', 'Colonoscopy for bleeding that started two '
                     'weeks ago.', 'Colonoscopy for anemia noted over the last year.'):
            with self.subTest(line=line):
                self.assertEqual(family(HEADER + 'Procedure: ' + line + '\n', 'gi.colonoscopy'), 'performed')


# --- routing:26, validation:9, validation:1 ----------------------------------------------------------------------

def plan_office(plan, heading='Assessment and plan:'):
    return (OFFICE_HEAD + 'Established patient office visit.\nChief complaint: rectal bleeding.\n' + heading + ' ' + plan
            + '\nMedical decision making: moderate.\nTotal time on the date of the encounter was 32 minutes.\n')


VISIT = 'Established patient office visit.'
TIME = 'Total time on the date of the encounter was 32 minutes.'
PLAN_HEADINGS = ('Assessment and plan:', 'A/P:', 'Impression and plan:', 'Assessment/Plan:')


class Routing26PlanSectionTodayTests(unittest.TestCase):
    """routing:26 and validation:9 (over-holds). An explicit past-tense performance statement whose own clause says
    today ('was performed today') was held under 'Assessment and plan:' while the identical clause under 'Assessment:'
    was ready. The one release of round 3b: such a clause, with no modal, conditional, future or hedge in it, is not
    downgraded by its plan section. Anything short of that stays held (the routing:26 verifier's counterexamples)."""

    def test_the_claimed_banding_is_ready_and_the_visit_held(self):
        band = 'Rubber band ligation of an internal hemorrhoid was performed today as scheduled.'
        text = plan_office('Grade 2 internal hemorrhoids. ' + band)
        status, cues = read(text, band)
        self.assertEqual(status, 'performed', cues)
        self.assertIn('performed: was performed', cues)
        proposals, _ = run_engine(text, [('99214', VISIT), ('46221', band)])
        self.assertTrue(ready(proposals['46221']), clarified(proposals['46221']))
        visit = proposals['99214']
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', clarified(visit))
        self.assertIn('documented as performed on the same date', check(visit, 'em.same_day_procedure').detail)

    def test_the_variants_read_performed_under_every_plan_heading(self):
        for heading in PLAN_HEADINGS:
            for sentence, code in (
                    ('Rubber band ligation of an internal hemorrhoid was performed today.', '46221'),
                    ('Rubber band ligation of an internal hemorrhoid was performed this morning as planned.', '46221'),
                    ('Two internal hemorrhoids were ligated with rubber bands this afternoon.', '46221')):
                text = plan_office(sentence, heading)
                with self.subTest(heading=heading, sentence=sentence):
                    status, cues = read(text, sentence)
                    self.assertEqual(status, 'performed', cues)
                    proposals, _ = run_engine(text, [(code, sentence)])
                    self.assertTrue(ready(proposals[code]), clarified(proposals[code]))

    def test_a_procedure_reports_impression_and_plan(self):
        sentence = 'EGD was performed today with biopsies of the antrum.'
        text = (HEADER + 'Procedure: EGD with biopsy.\nFindings: The gastroscope was advanced to the second part of the '
                'duodenum. Biopsies were taken from the antrum.\nImpression and plan: ' + sentence + '\n')
        self.assertEqual(read(text, sentence)[0], 'performed')
        proposals, _ = run_engine(text, [('43239', sentence)])
        self.assertTrue(ready(proposals['43239']), clarified(proposals['43239']))
        sentence = 'Colonoscopy was performed today with cold snare polypectomy of a 5 mm polyp.'
        self.assertEqual(read(plan_office(sentence), sentence)[0], 'performed')

    def test_short_of_the_release_the_plan_section_still_holds(self):
        for sentence in ('Rubber band ligation can be performed today if bleeding persists.',
                         'Rubber band ligation performed today if the patient agrees.',
                         'Rubber band ligation was performed today if bleeding persisted.',
                         'Rubber band ligation was possibly performed today.',
                         'Rubber band ligation was performed today?',
                         'Rubber band ligation was performed today, pending the pathology.',
                         'Rubber band ligation was performed, and repeat banding may be done today.',
                         'Rubber band ligation was performed.',
                         'Rubber band ligation performed today.',  # the bare participle stays downgraded
                         'Rubber band ligation was performed; she was seen today.'):  # today in another clause
            text = plan_office(sentence)
            with self.subTest(sentence=sentence):
                status, cues = read(text, sentence)
                self.assertNotEqual(status, 'performed', cues)
                proposals, _ = run_engine(text, [('46221', sentence)])
                self.assertNotEqual(proposals['46221'].status, 'ready')

    def test_another_services_past_tense_does_not_release(self):
        text = plan_office('Colonoscopy performed today and EGD was performed.')
        status, cues = read(text, 'Colonoscopy')
        self.assertEqual(status, 'uncertain', cues)

    def test_a_history_section_is_not_released(self):
        sentence = 'Rubber band ligation of an internal hemorrhoid was performed today.'
        text = (OFFICE_HEAD + 'Established patient office visit.\nHistory of present illness: ' + sentence +
                '\nMedical decision making: moderate.\n')
        self.assertEqual(read(text, sentence)[0], 'uncertain')


class Validation1PlanDefaultTodayTests(unittest.TestCase):
    """validation:1 (critical). A procedure the Assessment and plan documents as done today with no explicit
    performance cue ('EGD this morning revealed a Schatzki ring, dilated to 18 mm') was excluded as planned by the
    plan section's default, and the E/M beside it was approved with no same-day check. A plan section's default may
    at most hold: a clause that says today is uncertain, never planned."""

    CASES = (('EGD this morning revealed a Schatzki ring, dilated to 18 mm.', '43249', 'gi.egd'),
             ('EGD today showed esophagitis; biopsies taken.', '43239', 'gi.egd'),
             ('Colonoscopy today: two polyps removed with cold snare.', '45385', 'gi.colonoscopy'))

    def test_the_claimed_input_and_variants_are_held_with_the_visit(self):
        for heading in PLAN_HEADINGS[:3]:
            for sentence, code, slug in self.CASES:
                text = plan_office(sentence + ' Start omeprazole.', heading)
                with self.subTest(heading=heading, sentence=sentence):
                    status, cues = read(text, sentence)
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertFalse(any(c.startswith('uncertain: no performance evidence') for c in cues), cues)
                    self.assertNotIn(family(text, slug), NOT_TODAY)
                    proposals, _ = run_engine(text, [('99213', TIME), (code, sentence)])
                    self.assertEqual((proposals[code].bucket, proposals[code].status),
                                     ('selected', 'needs_clarification'), proposals[code].exclusion_reason)
                    self.assertEqual(proposals['99213'].status, 'needs_clarification')
                    self.assertIn('separate_em', clarified(proposals['99213']))

    def test_a_plan_that_does_not_say_today_stays_planned(self):
        for plan in ('EGD next week.', 'EGD revealed a Schatzki ring.', 'Repeat colonoscopy in 3 years.'):
            text = plan_office(plan)
            with self.subTest(plan=plan):
                self.assertEqual(read(text, plan.split()[0] if plan[0] != 'R' else 'colonoscopy')[0], 'planned')
                proposals, _ = run_engine(text, [('99213', TIME)])
                self.assertTrue(ready(proposals['99213']), clarified(proposals['99213']))

    def test_a_hedged_or_discussed_plan_today_does_not_hold_the_visit(self):
        for plan in ('Possible EGD today if symptoms persist.', 'Discussed colonoscopy today; she will think about it.',
                     'Colonoscopy? Will decide today after labs.'):
            text = plan_office(plan)
            with self.subTest(plan=plan):
                proposals, _ = run_engine(text, [('99213', TIME)])
                self.assertTrue(ready(proposals['99213']), clarified(proposals['99213']))


# --- routing:8, routing:10 ---------------------------------------------------------------------------------------

EUS_INDICATION = 'Indication: A 2.4 cm pancreatic head mass on CT.\n'
EUS_LINE = 'EUS with fine-needle biopsy of the pancreatic head mass'
FUTURE_TAILS = ('next Tuesday.', 'in 2 wks.', 'in 6 mos.', 'in the coming weeks.', 'at her convenience.',
                'in November.', 'on November 3.', 'in early November.', 'after the holidays.', 'in two wks.',
                'on Tuesday.')  # the date of service, 2026-10-21, is a Wednesday


class Routing8UnlistedFutureTimeTests(unittest.TestCase):
    """routing:8 (critical, under). A future time after the service name that no listed cue reads left the procedure
    heading speaking: 'EUS with fine-needle biopsy ... next Tuesday' was a ready 43242 with an FNB fact. An unlisted
    time attached to the service holds it (never planned: the hold-only rule)."""

    def test_the_claimed_eus_lines_are_held(self):
        for tail in FUTURE_TAILS:
            line = f'{EUS_LINE} {tail}'
            text = HEADER + EUS_INDICATION + 'Procedure: ' + line + '\n'
            with self.subTest(tail=tail):
                self.assertEqual(family(text, 'gi.eus'), 'uncertain')
                self.assertNotEqual(fact_value(text, 'gi.eus', 'tissue_sampling'), 'FNB')
                status, cues = read(text, line)
                self.assertEqual(status, 'uncertain', cues)
                self.assertFalse(any(c.startswith('uncertain: no performance evidence') for c in cues), cues)
                proposals, _ = run_engine(text, [('43242', line)])
                self.assertNotEqual(proposals['43242'].status, 'ready')
                self.assertNotEqual(proposals['43242'].bucket, 'excluded')

    def test_every_heading_and_the_colonoscopy(self):
        for heading in ('Procedure:', 'Findings:', 'Technique:', 'Procedures performed:'):
            for tail in ('next Tuesday.', 'in 2 wks.', 'in 6 mos.', 'in November.', 'in the coming weeks.'):
                for line, slug, fact in ((f'EUS with fine-needle biopsy {tail}', 'gi.eus', 'tissue_sampling'),
                                         (f'Colonoscopy with cold snare polypectomy of the sigmoid polyp {tail}',
                                          'gi.colonoscopy', 'interventions')):
                    text = HEADER + heading + ' ' + line + '\n'
                    with self.subTest(heading=heading, line=line):
                        self.assertNotIn(family(text, slug), POSITIVE)
                        self.assertNotIn(family(text, slug), NOT_TODAY)
                        self.assertNotIn(fact_value(text, slug, fact) or '', ('FNB', 'cold snare'))

    def test_controls_stay_performed(self):
        for line in (f'{EUS_LINE} next to the pancreatic duct.', 'EUS with fine-needle biopsy on 2026-10-21.',
                     'Colonoscopy with polypectomy of the next polyp in the sigmoid colon.',
                     'Colonoscopy with polypectomy on Wednesday.', 'Colonoscopy with polypectomy in October.',
                     'Colonoscopy with polypectomy on 10/21.', 'Colonoscopy with polypectomy on October 21.',
                     'Colonoscopy with polypectomy today, two weeks after a positive FIT.',
                     'Colonoscopy for bleeding since November.', f'{EUS_LINE}.',
                     'Colonoscopy was performed as previously scheduled.',
                     'Colonoscopy with polypectomy performed on the previously tattooed polyp.',
                     'Bowel preparation was started the day before the colonoscopy.',
                     'Clear liquids were taken the day before the colonoscopy.',
                     'Aspirin was held for two weeks before the colonoscopy.',
                     'Colonoscopy with polypectomy for a positive FIT in November.',
                     'Colonoscopy was performed today, two weeks after her last visit.',
                     'Colonoscopy two weeks after a positive FIT.', 'Colonoscopy 3 days prior to surgery.',
                     'Colonoscopy two weeks before her hernia repair.'):
            slug = 'gi.eus' if line.startswith('EUS') else 'gi.colonoscopy'
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, slug), 'performed')

    def test_a_full_date_beyond_the_names_reach_still_holds_it(self):
        """A dated passage reads by its date; the name, beyond DATE_REACH of it, is held by the month."""
        line = f'{EUS_LINE} on November 3, 2026, once the inflammation settles.'
        text = HEADER + EUS_INDICATION + 'Procedure: ' + line + '\n'
        self.assertEqual(family(text, 'gi.eus'), 'uncertain')
        status, cues = read(text, 'EUS')
        self.assertEqual(status, 'uncertain', cues)
        self.assertEqual(read(text, line)[0], 'planned')

    def test_no_unlisted_time_holds_an_office_visit_statement(self):
        for visit in ('Established patient office visit two weeks after her hospital discharge.',
                      'Established patient office visit was completed two weeks after her hospital discharge.'):
            with self.subTest(visit=visit):
                status, cues = read(routing0_office(visit), visit)
                self.assertEqual(status, 'performed', cues)

    def test_a_listed_cue_still_decides(self):
        for line, status in (('EUS with fine-needle biopsy next week.', 'planned'),
                             ('EUS with fine-needle biopsy in 2 weeks.', 'planned'),
                             ('EUS with fine-needle biopsy tomorrow.', 'planned')):
            with self.subTest(line=line):
                self.assertEqual(read(HEADER + 'Procedure: ' + line + '\n', 'EUS')[0], status)


ASSESSMENT_HISTORY = (
    'She recently underwent EGD; the endoscope was advanced to the second part of the duodenum and the mucosa was normal.',
    'An EGD was performed two weeks prior; the endoscope was advanced to the second part of the duodenum and the mucosa '
    'was normal.',
    'An EGD was performed at her last visit; the endoscope was advanced to the second part of the duodenum and the mucosa '
    'was normal.',
    'An EGD was performed during her recent hospitalization; the endoscope was advanced to the second part of the duodenum '
    'and the mucosa was normal.')
REFLUX_VISIT = 'Established patient office visit for reflux.'


def reflux_office(line, lead='Assessment: '):
    return (OFFICE_HEAD + REFLUX_VISIT + '\n' + lead + line + '\nMedical decision making: moderate.\n'
            'Total time: 32 minutes.\n')


class Routing10UnlistedHistoryTests(unittest.TestCase):
    """routing:10 (critical, under). Undated history in words no listed cue reads ('recently underwent', 'two weeks
    prior', 'at her last visit', 'during her recent hospitalization') read performed in an office note: 43235 ready
    with the history sentence's extent and a false missed-service prompt. It is held, never excluded (no new
    exclusion is allowed): the code is not ready, no extent is read, and the visit stays held as possibly beside a
    same-day EGD."""

    def test_the_wordings_are_held_with_no_extent(self):
        for lead in ('Assessment: ', '', 'S: ', 'Impression: '):
            for line in ASSESSMENT_HISTORY:
                text = reflux_office(line, lead)
                act = line.split(';')[0]
                with self.subTest(lead=lead, line=act):
                    self.assertNotIn(family(text, 'gi.egd'), POSITIVE)
                    self.assertIsNone(fact_value(text, 'gi.egd', 'extent'))
                    status, cues = read(text, act)
                    self.assertEqual(status, 'uncertain', cues)
                    proposals, result = run_engine(text, [('99214', REFLUX_VISIT), ('43235', act)])
                    self.assertNotEqual(proposals['43235'].status, 'ready')
                    self.assertNotEqual(proposals['43235'].bucket, 'excluded')
                    self.assertIn('separate_em', clarified(proposals['99214']))
                    _, alone = run_engine(text, [('99214', REFLUX_VISIT)])
                    self.assertNotIn('Upper GI endoscopy (EGD, esophagoscopy, enteroscopy) is documented as performed',
                                     unproposed(alone).detail)

    def test_controls(self):
        for line in ('An EGD was performed last month; the mucosa was normal.',
                     'An EGD was performed two weeks ago; the mucosa was normal.'):
            text = reflux_office(line)
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.egd'), 'historical')
                proposals, _ = run_engine(text, [('99214', REFLUX_VISIT)])
                self.assertTrue(ready(proposals['99214']), clarified(proposals['99214']))
        text = reflux_office('She underwent EGD today; the endoscope was advanced to the second part of the duodenum.')
        self.assertEqual(read(text, 'She underwent EGD today')[0], 'performed')
        self.assertEqual(read(reflux_office('Recent EGD was normal.'), 'EGD')[0], 'historical')



# --- routing:13 --------------------------------------------------------------------------------------------------

STATUS13_LEAD = ('Findings: The colonoscope was advanced to the splenic flexure, where an obstructing mass was '
                 'biopsied. ')
PRIOR_EXAM_TAILS = ('On a prior exam the cecum was reached.', 'At her last procedure the cecum was reached.',
                    'Previously the scope reached the cecum.', 'Previously, the cecum was reached.',
                    'The cecum was reached on a prior exam.', 'On a previous study the cecum was reached.',
                    'At the index exam the cecum was reached.', 'Per the outside report the cecum was reached.',
                    'On prior exams the cecum was reached.', 'At her prior exam the scope reached the cecum.',
                    'Her most recent examination reached the cecum.')


def colon_report(tail):
    return HEADER + 'Procedure: Colonoscopy\n' + STATUS13_LEAD + tail + '\n'


class Routing13PriorExamWithoutAServiceNameTests(unittest.TestCase):
    """routing:13 (critical, under). A prior exam named without a service name ('On a prior exam', 'At her last
    procedure', 'Previously the scope ...') supplied today's extent: an incomplete colonoscopy became complete. No
    fact is read from a clause about another examination, named or not."""

    def test_the_claimed_tails_leave_the_colonoscopy_incomplete(self):
        for tail in PRIOR_EXAM_TAILS:
            text = colon_report(tail)
            with self.subTest(tail=tail):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: splenic flexure')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
                proposals, _ = run_engine(text, [('45380', 'where an obstructing mass was biopsied')])
                item = proposals['45380']
                self.assertIsNotNone(check(item, 'service.incomplete'))
                self.assertTrue(item.modifier_considerations)

    def test_other_facts_and_the_egd(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. On a prior exam '
                'a polyp was removed with a cold snare.\n')
        self.assertNotIn('cold snare', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        text = (HEADER + 'Procedure: EGD\nFindings: The gastroscope was advanced to the stomach. On a prior exam the '
                'second part of the duodenum was reached.\n')
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'incomplete: stomach')

    def test_controls_keep_todays_facts(self):
        for body in ('The cecum was reached, as on her prior exam.', 'Compared with her prior exam, the cecum was '
                     'reached.', 'The cecum was reached in this patient with no prior colonoscopy.',
                     'The cecum was reached today, unlike on her prior exam.',
                     'The colonoscope was advanced to the cecum; her prior exam was incomplete.',
                     'Prior exam notes were reviewed and the cecum was reached.'):
            text = HEADER + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'
            with self.subTest(body=body):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        text = (HEADER + 'Procedure: ERCP\nFindings: The duodenoscope was advanced to the papilla. Deep biliary '
                'cannulation was achieved. Previously placed biliary stent was removed and a new stent was placed.\n')
        self.assertEqual(fact_value(text, 'gi.ercp', 'cannulation'), 'successful')
        self.assertIn('stent', fact_value(text, 'gi.ercp', 'interventions') or '')



# --- routing:17, contract:5 --------------------------------------------------------------------------------------

SEPARATE_NOTE = (OFFICE_HEAD + 'Established patient office visit for rectal bleeding.\nProcedure: Flexible sigmoidoscopy '
                 'with biopsy.\nFindings: The sigmoidoscope was advanced to 40 cm. A biopsy was taken from the rectum.\n'
                 'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
SEPARATE_PICKS = [('99214', 'Established patient office visit for rectal bleeding.'),
                  ('45331', 'A biopsy was taken from the rectum.')]
STATEMENT = 'A significant, separately identifiable E/M service was {}.'


def separate_em(text):
    finding = routed(text).finding('gi.office_em')
    return next((f for f in finding.facts if f.name == 'separate_em'), None)


class Routing17SeparateEmAnotherEncounterTests(unittest.TestCase):
    """routing:17 (high, under). A separately identifiable E/M statement about another encounter in words not on the
    list ('yesterday', 'two days ago', 'last week', 'on 10/14', 'by the referring physician') was accepted, so 99214
    was ready beside a same-day flexible sigmoidoscopy with biopsy. Any time that is not the date of service, and any
    history cue that tells a time or another provider, means the statement is not documented."""

    def test_the_claimed_and_listed_statements_are_not_documented(self):
        for said in ('provided yesterday', 'provided two days ago', 'provided last week', 'provided on 10/14',
                     'documented by the referring physician', 'provided on October 14', 'provided 3 weeks ago',
                     'provided last month', 'provided earlier this week', 'provided by an outside gastroenterologist',
                     'provided 10/14', 'provided on Tuesday', 'provided at her last visit'):
            text = SEPARATE_NOTE + STATEMENT.format(said) + '\n'
            with self.subTest(said=said):
                self.assertIsNone(separate_em(text))
                proposals, _ = run_engine(text, SEPARATE_PICKS)
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposals['99214']))

    def test_the_round_2_addendum_with_a_month_and_day(self):
        text = (SEPARATE_NOTE + '\nADDENDUM (revision 2, added 2026-10-22 09:00 UTC)\nThe significant, separately '
                'identifiable E/M service was provided at the 10/14 consultation. Today was the usual pre-procedure '
                'assessment.\n')
        self.assertIsNone(separate_em(text))

    def test_statements_about_this_encounter_are_documented(self):
        for said in ('performed today', 'provided', 'provided on 10/21', 'provided on October 21',
                     'provided on Wednesday', 'provided on the date of service',
                     'provided, including review of outside records',
                     'provided for abdominal pain that began last week'):
            text = SEPARATE_NOTE + STATEMENT.format(said) + '\n'
            with self.subTest(said=said):
                fact = separate_em(text)
                self.assertIsNotNone(fact)
                self.assertEqual(fact.value, 'documented')
        self.assertIsNotNone(separate_em(SEPARATE_NOTE + 'On 2026-10-21 a significant, separately identifiable E/M '
                                                         'service was provided.\n'))


ATTESTATION_NOTE = (OFFICE_HEAD + 'Established patient office visit for rectal bleeding.\nMedical decision making: '
                    'Moderate.\nTotal time on the date of the encounter was 32 minutes.\nProcedure: Colonoscopy. The '
                    'colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp was biopsied with cold '
                    'forceps.\n')
ATTESTATION = 'I performed a significant, separately identifiable E/M service on the same day as the procedure.'
ATTESTATION_PICKS = [('99214', 'Total time on the date of the encounter was 32 minutes.'),
                     ('45380', 'A 6 mm sigmoid polyp was biopsied with cold forceps.')]


class Contract5UncheckedAttestationTests(unittest.TestCase):
    """contract:5 (high, under). An unchecked attestation box in front of the separately identifiable E/M sentence
    was accepted as the clinician's statement, releasing the same-day E/M hold. An unchecked box that governs the
    statement (FORMS' _unchecked_box / _unchecked_state), or one written after it on its line, means it is not
    documented."""

    def test_an_unchecked_box_is_not_a_statement(self):
        for line in ('\u2610 ' + ATTESTATION, '\u2610  ' + ATTESTATION, '\u25a1 ' + ATTESTATION, '[ ] ' + ATTESTATION,
                     '( ) ' + ATTESTATION, ATTESTATION + ' [ ]', ATTESTATION + ' \u2610',
                     'Modifier 25 attestation: \u2610 A significant, separately identifiable E/M service was '
                     'performed.', 'Separately identifiable E/M service was provided: not checked',
                     'Separately identifiable E/M service was provided: unchecked'):
            text = ATTESTATION_NOTE + line + '\n'
            with self.subTest(line=line):
                self.assertIsNone(separate_em(text))
                proposals, _ = run_engine(text, ATTESTATION_PICKS)
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposals['99214']))

    def test_a_checked_box_or_no_box_is_a_statement(self):
        for line in ('\u2612 ' + ATTESTATION, '[x] ' + ATTESTATION, ATTESTATION, ATTESTATION + ' [x]',
                     'Modifier 25 attestation: \u2612 A significant, separately identifiable E/M service was '
                     'performed.'):
            text = ATTESTATION_NOTE + line + '\n'
            with self.subTest(line=line):
                fact = separate_em(text)
                self.assertIsNotNone(fact)
                proposals, _ = run_engine(text, ATTESTATION_PICKS)
                self.assertNotIn('separate_em', clarified(proposals['99214']))



# --- routing:21 --------------------------------------------------------------------------------------------------

BLEEDING_VISIT = 'Established patient office visit for rectal bleeding.'


def history_office(assessment):
    return (OFFICE_HEAD + BLEEDING_VISIT + '\nAssessment: ' + assessment + '\nMedical decision making: moderate.\n'
            'Total time: 32 minutes.\n')


def other_finding(text):
    return routed(text).finding('gi.other')


def encounter_detail(result, check_id):
    return next(c for c in result.encounter_checks if c.id == check_id)


class Routing21OtherHistoryTests(unittest.TestCase):
    """routing:21 (medium, a regression from round 2b status:19). gi.other read history sentences in an office note
    as same-day procedures: the E/M was held, and false 'Possible missed service' and 'unsupported' warnings appeared.
    The 57b4b3747 reading (no gi.other) is restored for a performed clause that tells another time, a name led by a
    history word reads historical, and a colonoscopy report's own banding is that colonoscopy's."""

    def assert_no_same_day_other(self, text, visit='99214'):
        other = other_finding(text)
        self.assertTrue(other is None or other.status not in POSITIVE + ('uncertain',),
                        other and [(m.span.text, m.status, m.cues) for m in other.mentions])
        proposals, result = run_engine(text, [(visit, BLEEDING_VISIT)])
        self.assertNotIn('separate_em', clarified(proposals[visit]))
        self.assertNotIn('Other GI service', encounter_detail(result, 'services.unproposed').detail)
        self.assertNotIn('Other GI service', encounter_detail(result, 'services.unsupported').detail)

    def test_the_claimed_history_sentences(self):
        for sentence in ('Hemorrhoid banding was performed at her last visit with good relief.',
                         'Appendectomy was done as a child.', 'Liver biopsy was done in June and showed steatosis.',
                         'She underwent hemorrhoid banding two years prior with good relief.'):
            with self.subTest(sentence=sentence):
                self.assert_no_same_day_other(history_office(sentence))

    def test_a_name_led_by_a_history_word_reads_historical(self):
        for sentence in ('Prior hemorrhoid banding was performed with good relief.',
                         'Previous hemorrhoid banding was done with good relief.',
                         'Recent liver biopsy was performed and showed steatosis.', 'Remote appendectomy was done.',
                         'Status post hemorrhoidectomy was performed.'):
            text = history_office(sentence)
            with self.subTest(sentence=sentence):
                self.assertEqual(other_finding(text).status, 'historical')
                self.assert_no_same_day_other(text)

    def test_an_office_note_without_a_basis_stays_an_office_note(self):
        text = (OFFICE_HEAD + 'Established patient office visit for abdominal pain.\nChief complaint: abdominal pain.\n'
                'Assessment: Abdominal pain. Appendectomy was done as a child.\nPlan: Return in 3 months.\n')
        self.assertEqual(routed(text).document_kind, 'office_note')
        proposals, _ = run_engine(text, [('99213', 'Established patient office visit for abdominal pain.')])
        self.assertEqual(clarified(proposals['99213']), ['em_basis'])

    def test_a_colonoscopy_reports_banding_is_the_colonoscopys(self):
        for findings in ('The colonoscope was advanced to the cecum. Internal hemorrhoids were seen on retroflexion. '
                         'Banding of internal hemorrhoids was performed with three bands.',
                         'The colonoscope was advanced to the cecum. Rubber band ligation of an internal hemorrhoid was '
                         'performed.',
                         'Internal hemorrhoids were seen on retroflexion. Banding of internal hemorrhoids was performed.',
                         'Colonoscopy to the cecum. Banding of internal hemorrhoids was performed.'):
            text = HEADER + 'Procedure: Colonoscopy\nFindings: ' + findings + '\n'
            with self.subTest(findings=findings):
                self.assertIsNone(other_finding(text))
                proposals, result = run_engine(text, [('45398', findings.split('. ')[-1])])
                self.assertNotIn('Other GI service', encounter_detail(result, 'services.unproposed').detail)
                unsupported = encounter_detail(result, 'services.unsupported')
                self.assertNotEqual(unsupported.status, 'warn', unsupported.detail)
                self.assertNotIn('Other GI service', unsupported.detail)

    def test_controls_a_same_day_or_ambiguous_banding_still_holds_the_visit(self):
        for text in (history_office('Rubber band ligation of an internal hemorrhoid was performed today.'),
                     history_office('Hemorrhoid banding was performed with good relief.'),
                     # a time that is not history (a repeat to come) never releases the hold
                     history_office('Hemorrhoid banding was performed with a repeat banding in 6 wks.'),
                     history_office('Anoscopy was performed with banding to follow in 2 wks.'),
                     # a later time that is the procedure's own is no history either: it holds, never releases
                     history_office('Anoscopy was performed next Tuesday.'),
                     history_office('Hemorrhoid banding was done in December.'),
                     OFFICE_HEAD + BLEEDING_VISIT + '\nHistory: Colonoscopy in 2023 was normal.\nProcedure: Rubber band '
                     'ligation of an internal hemorrhoid was performed today.\nMedical decision making: moderate.\n'
                     'Total time: 32 minutes.\n'):
            with self.subTest(text=text.splitlines()[-4]):
                self.assertIn(other_finding(text).status, POSITIVE + ('uncertain',))
                proposals, _ = run_engine(text, [('99214', BLEEDING_VISIT)])
                self.assertIn('separate_em', clarified(proposals['99214']))



# --- routing:22 --------------------------------------------------------------------------------------------------

def same_day_office(body):
    return (OFFICE_HEAD + BLEEDING_VISIT + '\n' + body + '\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')


class Routing22OtherSameDayFormsTests(unittest.TestCase):
    """routing:22 (medium, under). Same-day procedures the structural gi.other rule did not see ('hemorrhoids were
    banded', a subject with commas, 'Anoscopy: grade 2 ...', 'we banded', 'I&D') left the E/M ready with no same-day
    check. Each is read by its form, never by a list of names, and only ever adds a hold."""

    CLAIMED = ('Two internal hemorrhoids were banded today without complication.',
               'Rubber band ligation of internal hemorrhoids, columns 1 and 2, was performed today.',
               'Anoscopy: grade 2 internal hemorrhoids, no fissure.', 'Today we banded two internal hemorrhoids.',
               'I&D of a perianal abscess was performed today.')
    VARIANTS = ('Banding of the right anterior, right posterior and left lateral hemorrhoid columns was performed today.',
                'Procedure: Two internal hemorrhoids were banded today without complication.',
                'Internal hemorrhoids were banded x3 today.', 'RBL x2 performed today.',
                'Procedure: After informed consent was obtained, the patient was placed in the left lateral position. '
                'Two internal hemorrhoid columns were ligated with rubber bands.',
                'Physical exam: Rectal: normal tone. Anoscopy: grade 2 internal hemorrhoids.',
                'A perianal abscess was incised and drained today.')

    def test_the_claimed_and_variant_procedures_hold_the_visit(self):
        for body in self.CLAIMED + self.VARIANTS:
            text = same_day_office(body)
            with self.subTest(body=body):
                other = other_finding(text)
                self.assertIsNotNone(other)
                self.assertIn(other.status, POSITIVE + ('uncertain',))
                self.assertFalse(any(c.startswith('uncertain: no performance evidence')
                                     for m in other.mentions for c in m.cues))
                proposals, _ = run_engine(text, [('99214', BLEEDING_VISIT)])
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposals['99214']))

    def test_nothing_done_today_names_no_procedure(self):
        for body in ('No hemorrhoids were banded today.', 'Hemorrhoids were not banded.',
                     'The bile duct was dilated on MRCP.', 'Banding, if needed, was performed.',
                     'Two internal hemorrhoids were banded at her last visit.', 'She was seen for banding.',
                     'Anoscopy: deferred to the next visit.', 'Anoscopy: patient declined.'):
            text = same_day_office(body)
            with self.subTest(body=body):
                other = other_finding(text)
                self.assertTrue(other is None or other.status not in POSITIVE + ('uncertain',),
                                other and [(m.span.text, m.status, m.cues) for m in other.mentions])
                proposals, _ = run_engine(text, [('99214', BLEEDING_VISIT)])
                self.assertTrue(ready(proposals['99214']), clarified(proposals['99214']))

    def test_a_detected_procedures_own_act_is_never_other(self):
        for text in (HEADER + 'Procedure: EGD\nFindings: The gastroscope was advanced to the duodenum. Grade 3 '
                              'esophageal varices. Three columns were banded.\n',
                     HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Two '
                              'internal hemorrhoids were banded on retroflexion.\n',
                     HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Anoscopy: '
                              'normal.\n',
                     # a findings label is read only in an office note (a document with E/M documentation)
                     HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n'
                              'Impression: Anoscopy: small internal hemorrhoids.\n'):
            with self.subTest(text=text.splitlines()[-1][:60]):
                self.assertIsNone(other_finding(text))



# --- routing:19, validation:10 -----------------------------------------------------------------------------------

class Routing19StoredSizeTests(unittest.TestCase):
    """routing:19 and validation:10 (medium). Every ServiceMention carried a copy of its whole sentence, so the routing
    JSON grew as (mentions in a sentence) x (sentence length): the round-2b ScaleTests input (140 KB) gave 320 MB, and
    storing it killed the test PostgreSQL backend. A mention stores its sentence when that is short, else its clause,
    else the part of its clause within CLAUSE_REACH of it: bounded per mention, and it always holds the mention."""

    @staticmethod
    def stored(text):
        import json
        from studio.gi.detect import route
        from studio.types import to_jsonable
        result = route(text)
        return result, len(json.dumps(to_jsonable(result)))

    def assert_mentions_hold_their_spans(self, text, result):
        for finding in result.findings:
            for m in finding.mentions:
                self.assertEqual(text[m.sentence.start:m.sentence.end], m.sentence.text)
                self.assertTrue(m.sentence.start <= m.span.start < m.span.end <= m.sentence.end)

    def test_the_scale_input_stores_a_bounded_result(self):
        import time
        text = HEADER + 'Findings: ' + ' '.join(['colonoscopy: \u2610 biopsy of the sigmoid colon \u2612 cold snare '
                                                 'polypectomy |'] * 2000)
        started = time.monotonic()
        result, size = self.stored(text)
        self.assertLess(time.monotonic() - started, 20)
        self.assertLess(size, 20 * len(text), size)
        self.assertEqual(result.finding('gi.colonoscopy').status, 'performed')
        self.assert_mentions_hold_their_spans(text, result)

    def test_many_mentions_in_one_sentence_store_linearly(self):
        """A mention every 27 characters, all in one sentence: twice the mentions store about twice as much (it was
        four times: 6.9 MB, 27 MB, 108 MB for 500, 1000, 2000), within a bound per character of text."""
        sizes = {}
        for count in (500, 1000, 2000):
            text = HEADER + 'Colonoscopy was performed, ' * count
            with self.subTest(count=count):
                result, sizes[count] = self.stored(text)
                self.assertLess(sizes[count], 40 * len(text), sizes[count])
                self.assert_mentions_hold_their_spans(text, result)
        self.assertLess(sizes[2000] / sizes[1000], 2.2)
        self.assertLess(sizes[1000] / sizes[500], 2.2)

    def test_a_wrapped_run_of_short_lines_stores_a_bounded_result(self):
        """The orchestrator's case (from the SECTIONS repair, whose soft wrap joins more lines): about 50,000 characters
        of short lines, each cut on a function word, with a service name every ~500 characters, form one wrapped
        sentence. At d05326ef5 its 98 mentions stored 5,077,711 characters (101x the text); a bounded window stores
        about 83,000."""
        import time
        from studio.gi.sections import layout
        for first in ('findings', 'Findings'):
            lines = []
            while sum(len(line) + 1 for line in lines) < 50000:
                lines.append('colonoscopy was performed and the' if len(lines) % 16 == 0
                             else f'{first} were reviewed with the')
            text = HEADER + 'Findings: ' + '\n'.join(lines) + ' cecum.\n'
            with self.subTest(first=first):
                started = time.monotonic()
                result, size = self.stored(text)
                self.assertLess(time.monotonic() - started, 20)
                lay = layout(text)
                mentions = [m for f in result.findings for m in f.mentions]
                whole = sum(e - s for s, e in (lay.sentence_for(m.span.start, m.span.end) for m in mentions))
                self.assertGreater(whole, 50 * len(text))  # the shape: whole sentences would store quadratically
                self.assertLess(size, 5 * len(text), size)
                self.assert_mentions_hold_their_spans(text, result)

    def test_a_short_sentence_is_stored_whole_and_a_long_one_by_its_clause(self):
        line = 'Rubber band ligation of an internal hemorrhoid was performed today without complication.'
        result, _ = self.stored(OFFICE_HEAD + BLEEDING_VISIT + '\n' + line + '\n')
        self.assertEqual(result.finding('gi.other').mentions[0].sentence.text, line)
        filler = ' '.join(['the mucosa of the rectum looked normal'] * 40)
        text = HEADER + 'Findings: ' + filler + '; colonoscopy was performed to the cecum; ' + filler + '.\n'
        result, _ = self.stored(text)
        (mention,) = result.finding('gi.colonoscopy').mentions
        self.assertEqual(mention.sentence.text, 'colonoscopy was performed to the cecum;')

    def test_a_routing_reading_still_cites_the_mention(self):
        text = HEADER + 'Findings: ' + ' '.join(['the colonoscopy and the egd were discussed with the family at length'] * 60)
        proposals, _ = run_engine(text, [('45378', 'colonoscopy')])
        status = check(proposals['45378'], 'service.status')
        self.assertIn('colonoscopy', status.detail)


if __name__ == '__main__':
    unittest.main()
