"""Regressions for refutation round 2 over validation: status resolution and the same-day E/M rules.

Each class reproduces one confirmed finding (status:N or review:N in the round-2 triage). Where the exact input
reproduces through today's routing, it runs the real router, the real span reader and the engine; where it depends on
a routing defect repaired elsewhere, or on a routing feature not yet present (gi.other findings), the test states the
routing readings explicitly. Every over-correction finding has positive controls: a document that still justifies
the hold must keep it. Synthetic text only; pure functions.
"""
import json
from datetime import date

from django.test import SimpleTestCase

from studio.gi.context import extract_context
from studio.gi.detect import route
from studio.gi.profiles import DETECTED_FAMILIES, PROFILES
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, Fact, FamilyFinding, NormalizedResponse, PageSpan, ProviderCode,
                          RoutingResult, ServiceMention, Span, from_jsonable, to_jsonable)
from studio.validation import checks
from studio.validation.engine import ENGINE_VERSION, assess
from tests.test_validation import (EGD, EGD_LABEL, EM, MUE_INFO, MUE_ROWS, PFS_INFO, PFS_ROWS, EngineCase, Note,
                                   finding, pfs, selected, visit_context)

DOS = date(2026, 10, 21)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
SILENT_CUE = 'uncertain: no performance evidence in its sentence or section'
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {
    PFS_INFO.key: {**PFS_ROWS, ('43259', ''): pfs(base='43235'), ('45331', ''): pfs(base='45330'),
                   ('45330', ''): pfs(), ('91200', ''): pfs(days='XXX', mult='0')},
    MUE_INFO.key: MUE_ROWS})


def real(text, *picks):
    """picks: (code, evidence phrase, ...). Real routing, JSON round-tripped as the assess stage stores it, the real
    span reader and the engine. Returns (proposals by code, result)."""
    routing = from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, DOS)))))
    codes = []
    for index, (code, *phrases) in enumerate(picks):
        spans = tuple(EvidenceSpan(0, text.index(p), text.index(p) + len(p), p, True) for p in phrases)
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=spans,
                                  index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=routing,
                    normalized=NormalizedResponse('corti', 'corti-coding@1', codes=tuple(codes)),
                    reference=REFERENCE, service_date=DOS, provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals}, result


def check_of(item, check_id):
    found = [c for c in item.checks if c.id == check_id]
    return found[0] if found else None


def encounter_check(result, check_id):
    (found,) = [c for c in result.encounter_checks if c.id == check_id]
    return found


def placed(note, family, status, phrase, section, *cues):
    where = note.sentence(phrase)
    return ServiceMention(family=family, status=status, span=where, sentence=where, section=section, cues=cues)


class RealCase(SimpleTestCase):
    maxDiff = None

    def assertVisitReady(self, proposals, code='99214'):
        visit = proposals[code]
        self.assertEqual((visit.bucket, visit.status), ('selected', 'ready'), [c.detail for c in visit.checks])
        self.assertIsNone(check_of(visit, 'em.same_day_procedure'))
        self.assertNotIn('separate_em', [c.fact for c in visit.clarifications])

    def assertVisitHeld(self, proposals, phrase, code='99214'):
        visit = proposals[code]
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        self.assertIn(phrase, check_of(visit, 'em.same_day_procedure').detail)


# --- status:3 and review:1: a plan that only discusses a procedure is not a same-day procedure ---------------

OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: {cc}\n'
          'History of present illness: Intermittent heartburn for 8 weeks despite omeprazole. No dysphagia.\n'
          'Assessment: Gastroesophageal reflux disease, not controlled.\nPlan: {plan}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
VISIT_SENTENCE = 'Established patient office visit.'
ASSESSMENT_AND_PLAN = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                       'Chief complaint: Abdominal pain.\nAssessment and plan: {plan}\n'
                       'Medical decision making: moderate.\n'
                       'Time: Total time on the date of the encounter was 32 minutes.\n')
DISCUSSED = (
    # review:1, the claimant's five
    'Discussed colonoscopy; the patient will think about it.',
    'EGD versus empiric PPI trial; the patient prefers the PPI trial.',
    'Colonoscopy? Will decide after labs.',
    'Possible Crohn disease. Colonoscopy vs. CT enterography; decision at follow-up.',
    'Risks and benefits of colonoscopy were discussed.',
    # review:1, the verifier's own
    'Colonoscopy if needed.', 'Possible EGD.',
    'Flexible sigmoidoscopy versus colonoscopy; the patient will call to decide.',
    'Discussion of EGD; the patient prefers to wait.',
    'Trial of fiber supplementation. Discussed colonoscopy for persistent symptoms.',
    'Colonoscopy may be needed if cramping persists.', 'Upper endoscopy? Will reassess after the PPI trial.',
    # status:3 breadth
    'Possible colonoscopy.', 'Colonoscopy as needed.', 'EGD if needed.', 'Candidate for ERCP if cholangitis develops.',
    'Discussed colonoscopy; patient will call to schedule.', 'Colonoscopy versus CT colonography; patient to decide.',
    'Discussed colonoscopy today; the patient will think about it.',
)


class Status3PlanHedgeTests(RealCase):
    """status:3 — a hedged plan item or a chief-complaint reference does not hold the office E/M."""

    def test_the_claimed_input_is_ready(self):
        text = OFFICE.format(cc='Heartburn.', plan='Increase omeprazole to 40 mg twice daily. Possible EGD if symptoms '
                                                  'persist.')
        self.assertEqual(route(text, DOS).finding(EGD).status, 'uncertain')  # the reading the hold misread
        proposals, _ = real(text, ('99214', VISIT_SENTENCE))
        self.assertVisitReady(proposals)

    def test_plan_variants_are_ready(self):
        for plan in ('EGD as needed.', 'EGD if symptoms persist.', 'EGD pending insurance approval.',
                     'Possible EGD if symptoms persist.'):
            with self.subTest(plan=plan):
                proposals, _ = real(OFFICE.format(cc='Heartburn.', plan=plan), ('99214', VISIT_SENTENCE))
                self.assertVisitReady(proposals)

    def test_chief_complaint_references_are_ready(self):
        for cc in ('Follow-up after colonoscopy.', 'Here to discuss EGD results.', 'Colonoscopy results.',
                   'Post-colonoscopy follow-up.'):
            with self.subTest(cc=cc):
                proposals, _ = real(OFFICE.format(cc=cc, plan='Return in 3 months.'), ('99214', VISIT_SENTENCE))
                self.assertVisitReady(proposals)

    def test_a_pure_office_visit_still_reports_an_unproposed_e_m(self):
        """The second symptom: the same reading suppressed the possible-missed-E/M warning on a pure office visit."""
        _, result = real(OFFICE.format(cc='Heartburn.', plan='Possible EGD if symptoms persist.'))
        # engine @4: the documented-service reconciliation reports the visit, as services.unresolved
        unresolved = encounter_check(result, 'services.unresolved')
        self.assertEqual(unresolved.status, 'warn')
        self.assertIn('Unresolved: office / outpatient visit (documented as performed) has no supported proposal',
                      unresolved.detail)

    def test_controls_scheduled_and_planned_wording_stay_ready(self):
        for plan in ('Schedule EGD.', 'Consider EGD if no improvement.', 'EGD in 2024 was normal.'):
            with self.subTest(plan=plan):
                proposals, _ = real(OFFICE.format(cc='Heartburn.', plan=plan), ('99214', VISIT_SENTENCE))
                self.assertVisitReady(proposals)


class Review1PlanDiscussionTests(RealCase):
    """review:1 — an office visit whose plan only discusses a procedure keeps its E/M approvable."""

    def test_discussion_phrasings_are_ready(self):
        for plan in DISCUSSED:
            with self.subTest(plan=plan):
                proposals, _ = real(ASSESSMENT_AND_PLAN.format(plan=plan), ('99214', VISIT_SENTENCE))
                self.assertVisitReady(proposals)

    def test_a_history_discussion_is_ready(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'History of present illness: A colonoscopy was discussed at the prior visit and she preferred to '
                'wait.\n'
                'Assessment and plan: Fiber supplementation.\nMedical decision making: moderate.\n'
                'Time: Total time on the date of the encounter was 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT_SENTENCE))
        self.assertVisitReady(proposals)

    def test_a_reinstated_e_m_is_not_gated_by_a_discussion(self):
        text = ASSESSMENT_AND_PLAN.format(plan='Discussed colonoscopy; the patient will think about it. '
                                               'Return in three months.')
        proposals, _ = real(text, ('99214', 'Return in three months.'))
        visit = proposals['99214']
        # Engine @4: today's documented visit decides the code (interpretation 9), so it is not excluded and needs no
        # reinstatement; the discussion still gates nothing, and the return-visit passage is never read as showing the
        # visit.
        self.assertVisitReady(proposals)
        self.assertEqual((check_of(visit, 'evidence.support').status, visit.support['unrelated']), ('warn', [0]))

    def test_controls_a_performance_statement_in_the_plan_still_holds(self):
        proposals, _ = real(ASSESSMENT_AND_PLAN.format(plan='EGD was performed today with biopsies of the antrum.'),
                            ('99214', VISIT_SENTENCE))
        self.assertVisitHeld(proposals, f'{EGD_LABEL} is ')

    def test_controls_an_unheaded_hedge_outside_a_plan_still_holds(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Possible EGD if the stricture is confirmed.\nMedical decision making: moderate.\n')
        proposals, _ = real(text, ('99214', VISIT_SENTENCE))
        self.assertVisitHeld(proposals, f'{EGD_LABEL} is possibly performed on the same date')

    def test_controls_a_doubted_procedure_line_still_holds(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Procedure: Colonoscopy to evaluate iron deficiency anemia.\nMedical decision making: moderate.\n'
                'Total time: 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT_SENTENCE))
        self.assertVisitHeld(proposals, 'Colonoscopy is ')

    def test_controls_an_assessment_section_hedge_still_holds(self):
        """Only plan, history and indication / chief-complaint sections are read as not today (ARCHITECTURE 5.3);
        an assessment section has no such default, so a hedge there stays a doubt about the service. Round 3b
        reversed this control and round 4 validation:0 restored it: the release let a hedge about the diagnosis
        release the E/M beside a procedure stated as performed."""
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Assessment: GERD; possible EGD if refractory.\nPlan: PPI.\nMedical decision making: moderate.\n')
        proposals, _ = real(text, ('99214', VISIT_SENTENCE))
        self.assertVisitHeld(proposals, f'{EGD_LABEL} is possibly performed on the same date')


class SameDayMentionRuleTests(EngineCase):
    """status:3 and review:1 at the validation layer: which routed mention of an 'uncertain' procedure family can
    speak for the date of service, read from routing's section and cues alone."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for dysphagia.',
                'Total time 32 minutes.', 'EGD line.')
    VISIT, TIME, LINE = 'Office visit: established patient seen for dysphagia.', 'Total time 32 minutes.', 'EGD line.'

    def visit_status(self, *mentions):
        self.statuses = {self.TIME: None}
        found = [finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                         facts={'em_basis': 'total time 32 minutes'}),
                 FamilyFinding(EGD, 'uncertain', tuple(mentions))]
        result = self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.TIME)), findings=found,
                                 ctx=visit_context())
        return self.proposal(result, '99213')

    def mention(self, section, *cues):
        return placed(self.NOTE, EGD, 'uncertain', self.LINE, section, *cues)

    def test_the_rule(self):
        downgrade = ('performed: was performed', 'section: plan (Assessment and plan)')
        cases = (
            ('plan', ('uncertain: Possible',), 'ready'),
            ('plan', ('uncertain: Discussed',), 'ready'),
            ('plan', downgrade, 'needs_clarification'),
            ('history', ('uncertain: was discussed',), 'ready'),
            ('history', ('performed: underwent', 'section: history (History of present illness)'),
             'needs_clarification'),
            ('indication', (SILENT_CUE,), 'ready'),
            ('indication', ('uncertain: ?',), 'ready'),
            ('other', (SILENT_CUE,), 'ready'),
            ('other', (), 'ready'),
            ('other', ('uncertain: Possible',), 'needs_clarification'),
            ('procedure', ("uncertain: section silent: 'to evaluate' follows the service name",
                           'section: procedure (Procedure)'), 'needs_clarification'),
            ('findings', ("uncertain: unresolved negation 'not' in its clause",), 'needs_clarification'),
            # round 4 validation:0 reverted round 3b's assessment-section release: a hedge in an assessment,
            # impression, exam or MDM section holds again (it may be about the diagnosis of a procedure stated as done)
            ('assessment', ('uncertain: possible',), 'needs_clarification'),
            ('impression', ('uncertain: possible',), 'needs_clarification'),
            ('exam', ('uncertain: Possible',), 'needs_clarification'),
            ('mdm', ('uncertain: versus',), 'needs_clarification'),
            ('assessment', ('uncertain: pending',), 'needs_clarification'),
            ('assessment', ('uncertain: aborted, with no statement whether the procedure had started',),
             'needs_clarification'),
            ('impression', ('uncertain: a cue validation does not read as a hedge',), 'needs_clarification'),
        )
        for section, cues, expected in cases:
            with self.subTest(section=section, cues=cues):
                visit = self.visit_status(self.mention(section, *cues))
                self.assertEqual(visit.status, expected, [c.detail for c in visit.checks])
                if expected == 'needs_clarification':
                    self.assertIn(f'{EGD_LABEL} is possibly performed on the same date',
                                  self.check(visit, 'em.same_day_procedure').detail)

    def test_any_mention_that_can_speak_for_today_holds(self):
        visit = self.visit_status(self.mention('plan', 'uncertain: Possible'),
                                  self.mention('other', 'uncertain: Possible'))
        self.assertEqual(visit.status, 'needs_clarification')

    def test_the_selected_code_arm_is_kept(self):
        """A selected procedural code whose own passage hedges holds the E/M, whatever its section."""
        self.statuses = {self.TIME: None, self.LINE: ('uncertain', ('uncertain: Possible',))}
        found = [finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                         facts={'em_basis': 'total time 32 minutes'}),
                 FamilyFinding(EGD, 'uncertain', (self.mention('plan', 'uncertain: Possible'),))]
        result = self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.TIME)),
                                 selected('43235', self.NOTE.span(self.LINE)), findings=found, ctx=visit_context())
        self.assertEqual(self.proposal(result, '99213').status, 'needs_clarification')


# --- status:4: a family routed only 'uncertain' is not established by another family's passage --------------

EUS_NOTE = (HEAD + 'Indication: Dysphagia. {indication}\nProcedure: EGD\n'
            'Findings: The endoscope was advanced to the second part of the duodenum. Normal EGD.\n{plan}')
ADVANCED = 'The endoscope was advanced to the second part of the duodenum.'


class Status4UncertainFamilyTests(RealCase):
    """status:4 — EUS named only as requested, questioned or possible: an EGD passage cannot make 43259 ready."""

    def test_the_claimed_input_and_its_variants_are_held(self):
        for indication in ('Pancreatic cyst on CT; EUS requested by the referring physician.',
                           'Pancreatic cyst (EUS?).', 'Pancreatic cyst on CT; possible EUS.'):
            with self.subTest(indication=indication):
                text = EUS_NOTE.format(indication=indication, plan='')
                proposals, _ = real(text, ('43259', ADVANCED))
                item = proposals['43259']
                self.assertNotEqual(item.status, 'ready')
                if route(text, DOS).finding('gi.eus').status != 'uncertain':  # integrated routing may read it planned
                    self.assertEqual(item.bucket, 'excluded')
                    continue
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                status = check_of(item, 'service.status')
                self.assertEqual(status.status, 'warn')
                self.assertIn('the document names Endoscopic ultrasound only as uncertain', status.detail)
                self.assertNotIn('documented as performed', status.detail)
                (asked,) = [c for c in item.clarifications if c.fact == 'performed_status']
                self.assertIn(ADVANCED, asked.reason)
                self.assertIn('EUS', asked.reason.split('only as uncertain', 1)[1])

    def test_citing_the_doubtful_mention_too_stays_held(self):
        proposals, _ = real(EUS_NOTE.format(indication='Pancreatic cyst (EUS?).', plan=''),
                            ('43259', 'Pancreatic cyst (EUS?).', ADVANCED))
        self.assertNotEqual(proposals['43259'].status, 'ready')

    def test_controls(self):
        proposals, _ = real(EUS_NOTE.format(indication='', plan=''), ('43259', ADVANCED))
        never = [c for c in proposals['43259'].clarifications if c.fact == 'performed_status']
        self.assertIn('never names', never[0].reason)
        proposals, _ = real(EUS_NOTE.format(indication='', plan='Plan: Will schedule EUS for the pancreatic cyst.\n'),
                            ('43259', ADVANCED), ('43235', ADVANCED))
        planned = proposals['43259']
        self.assertEqual((planned.bucket, planned.reinstatable), ('excluded', True))
        # The code's own EGD passage is not "Endoscopic ultrasound documented as performed elsewhere".
        self.assertNotIn('documented as performed elsewhere', planned.exclusion_reason)
        self.assertIn(ADVANCED, planned.exclusion_reason)
        self.assertEqual(proposals['43235'].status, 'ready')


class Status4ResolveStatusTests(EngineCase):
    """status:4 at the validation layer, with both a silent and a hedged routing cue."""

    NOTE = Note('Date of service: 2026-10-21', 'Indication: pancreatic cyst; EUS requested.',
                'The endoscope was advanced to the second part of the duodenum.')
    EUS_LINE = 'Indication: pancreatic cyst; EUS requested.'
    DONE = 'The endoscope was advanced to the second part of the duodenum.'

    def run_case(self, eus_status, *cues):
        self.statuses = {self.DONE: ('performed', ('performed: was advanced',))}
        egd = finding(EGD, 'performed', placed(self.NOTE, EGD, 'performed', self.DONE, 'findings', 'performed'),
                      facts={'extent': 'second part of the duodenum'})
        eus = finding('gi.eus', eus_status, placed(self.NOTE, 'gi.eus', eus_status, self.EUS_LINE, 'indication', *cues),
                      facts={'target': 'pancreatic cyst'})
        result = self.run_engine(self.NOTE, selected('43259', self.NOTE.span(self.DONE)), findings=[egd, eus])
        return self.proposal(result, '43259')

    def test_silent_and_hedged_uncertain_families_hold(self):
        for cues in ((SILENT_CUE,), ('uncertain: ?',)):
            with self.subTest(cues=cues):
                item = self.run_case('uncertain', *cues)
                self.assertEqual(item.status, 'needs_clarification')
                self.assertIn('only as uncertain', self.check(item, 'service.status').detail)
                self.assertIn(self.EUS_LINE, self.check(item, 'service.status').detail)
                self.assertEqual(item.rationale.count('Service status: not established as performed.'), 1)

    def test_a_performed_family_still_reads_performed(self):
        item = self.run_case('performed', 'performed')
        self.assertEqual((item.status, self.check(item, 'service.status').status), ('ready', 'pass'))

    def test_resolve_status_directly(self):
        own = checks.Reading('performed', ('performed: was advanced',), 'evidence', self.DONE)
        silent = checks.Reading('uncertain', (SILENT_CUE,), 'routing', self.EUS_LINE)
        outcome = checks.resolve_status([own, silent], detectable=True)
        self.assertEqual((outcome.state, outcome.reason, outcome.decisive, outcome.contrary),
                         ('uncertain', 'unestablished', own, silent))
        self.assertEqual(checks.resolve_status([own], detectable=True).reason, 'unnamed')
        self.assertEqual(checks.resolve_status([own, silent], detectable=False).state, 'performed')


# --- status:13: a code's own hedged passage is never dropped by another of its passages ----------------------

S13 = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. {findings}\n'
       'Plan: Repeat colonoscopy with biopsies if symptoms persist.\n')
CECUM = 'The colonoscope was advanced to the cecum.'
PLAN_HEDGE = 'Repeat colonoscopy with biopsies if symptoms persist.'


class Status13HedgedOwnPassageTests(RealCase):
    """status:13 — a performed passage beside a hedged passage of the same code holds the code, naming both."""

    def assertContested(self, item, positive, hedge):
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        status = check_of(item, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertIn(positive, status.detail)
        self.assertIn(hedge, status.detail)
        self.assertFalse(status.detail.startswith('No documentation establishes'), status.detail)
        (asked,) = [c for c in item.clarifications if c.fact == 'performed_status']
        self.assertIn(hedge, asked.reason)
        self.assertIn(positive, asked.reason)
        # engine @4: the question is the documented service's own (the biopsy it lacks or denies); the reason above
        # still names the performed and the hedged passage, both readings.
        self.assertRegex(asked.question, r'(?:45380 was|forceps biopsy) performed on the date of service')

    def test_the_claimed_input_in_either_order(self):
        text = S13.format(findings='The colon was normal. No biopsies were obtained.')
        for order in ((CECUM, PLAN_HEDGE), (PLAN_HEDGE, CECUM)):
            with self.subTest(order=order):
                proposals, _ = real(text, ('45380', *order))
                self.assertContested(proposals['45380'], CECUM, PLAN_HEDGE)

    def test_a_hedge_about_today_is_held(self):
        for hedge in ('It is unclear whether biopsies were taken.', 'Possible biopsy of the ascending colon?'):
            with self.subTest(hedge=hedge):
                text = S13.format(findings=f'A 5 mm cecal lesion was seen. {hedge}')
                proposals, _ = real(text, ('45380', CECUM, hedge))
                self.assertContested(proposals['45380'], CECUM, hedge)

    def test_control_a_negated_second_passage_is_flagged_and_held_never_excluded(self):
        """Round 1's rule (a contrary linked passage is named) is unchanged; engine @4 (ARCHITECTURE 5.10): the
        documented colonoscopy denies the biopsy 45380 accounts for, so the code is no longer ready - and since its own
        passages do not exclude it, it is held, never newly excluded."""
        text = S13.format(findings='The colon was normal. No biopsies were obtained.')
        proposals, _ = real(text, ('45380', CECUM, 'No biopsies were obtained.'))
        item = proposals['45380']
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        status = check_of(item, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertIn('the document states the forceps biopsy was not performed: “No biopsies were obtained.”',
                      status.detail)
        self.assertIn('Another linked passage reads as negated: “No biopsies were obtained.”', status.detail)
        self.assertIn('Held for the reviewer, not excluded.', status.detail)

    def test_control_a_single_performed_passage_is_ready(self):
        proposals, _ = real(S13.format(findings='The colon was normal.'), ('45378', CECUM))
        self.assertEqual(proposals['45378'].status, 'ready')


class Status13ResolveStatusTests(SimpleTestCase):
    def test_a_hedge_is_never_dropped_and_silence_is_not_a_hedge(self):
        positive = checks.Reading('performed', ('performed: was advanced',), 'evidence', CECUM)
        hedged = checks.Reading('uncertain', ('uncertain: if symptoms persist',), 'evidence', PLAN_HEDGE)
        silent = checks.Reading('uncertain', (SILENT_CUE,), 'evidence', 'The colon was normal.')
        routed = checks.Reading('performed', ('section: procedure (Procedure)',), 'routing', 'Colonoscopy')
        for readings in ([positive, hedged, routed], [hedged, positive, routed]):
            outcome = checks.resolve_status(readings, detectable=True)
            self.assertEqual((outcome.state, outcome.reason, outcome.decisive, outcome.contrary),
                             ('uncertain', 'contested', hedged, positive))
        self.assertEqual(checks.resolve_status([positive, silent, routed], detectable=True).state, 'performed')
        detail = checks.status_check(checks.resolve_status([positive, hedged, routed], detectable=True),
                                     'Colonoscopy').detail
        self.assertIn(f'“{CECUM}”', detail)
        self.assertIn(f'“{PLAN_HEDGE}”', detail)


# --- status:19: other GI services hold the E/M; coverage never claims more than routing covers ----------------

BANDING = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
           'Chief complaint: rectal bleeding.\n'
           'Procedure: Rubber band ligation of an internal hemorrhoid was performed today without complication.\n'
           'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


class Status19OtherServiceTests(EngineCase):
    """status:19 (a), per the shared contract: a routed gi.other finding counts as a same-day procedure under the
    rule applied to a detected procedure family. Routing does not emit gi.other at this commit, so the readings
    are stated explicitly."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for rectal bleeding.',
                'Total time 32 minutes.',
                'Procedure: Rubber band ligation of an internal hemorrhoid was performed today.')
    VISIT, TIME = 'Office visit: established patient seen for rectal bleeding.', 'Total time 32 minutes.'
    BAND = 'Procedure: Rubber band ligation of an internal hemorrhoid was performed today.'

    def run_case(self, status, section, *cues):
        self.statuses = {self.TIME: None}
        found = [finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                         facts={'em_basis': 'total time 32 minutes'}),
                 finding('gi.other', status, placed(self.NOTE, 'gi.other', status, self.BAND, section, *cues))]
        return self.run_engine(self.NOTE, selected('99214', self.NOTE.span(self.TIME)), findings=found,
                               ctx=visit_context())

    def test_a_performed_other_service_holds_the_visit(self):
        result = self.run_case('performed', 'procedure', 'performed: was performed')
        visit = self.proposal(result, '99214')
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertEqual([c.fact for c in visit.clarifications], ['separate_em'])
        self.assertIn('Other GI service is documented as performed on the same date',
                      self.check(visit, 'em.same_day_procedure').detail)
        self.assertEqual(visit.modifier_considerations, (checks.SEPARATE_EM_CONSIDERATION,))
        self.assertIn('Possible missed service: Other GI service',
                      self.encounter_check(result, 'services.unproposed').detail)
        self.assertEqual([entry['family'] for entry in result.unsupported], ['gi.other'])

    def test_an_uncertain_other_service_follows_the_mention_rule(self):
        cases = (('procedure', ("uncertain: unresolved negation 'not' in its clause",), 'needs_clarification'),
                 ('other', ('uncertain: Possible',), 'needs_clarification'),
                 ('plan', ('uncertain: Possible',), 'ready'),
                 ('other', (SILENT_CUE,), 'ready'),
                 ('indication', ('uncertain: ?',), 'ready'))
        for section, cues, expected in cases:
            with self.subTest(section=section, cues=cues):
                visit = self.proposal(self.run_case('uncertain', section, *cues), '99214')
                self.assertEqual(visit.status, expected)
                if expected != 'ready':
                    self.assertIn('Other GI service is possibly performed on the same date',
                                  self.check(visit, 'em.same_day_procedure').detail)

    def test_a_planned_other_service_does_not_hold_the_visit(self):
        visit = self.proposal(self.run_case('planned', 'plan', 'planned: scheduled'), '99214')
        self.assertEqual(visit.status, 'ready')
        self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])


class Status19CoverageTests(RealCase):
    """status:19 (b): the coverage checks are scoped to what routing recognises, and an office E/M says that a
    same-day procedure outside the recognised families is not detected."""

    def test_the_claimed_input_carries_no_false_coverage_pass(self):
        proposals, result = real(BANDING, ('99214', VISIT_SENTENCE))
        for check in result.encounter_checks:
            self.assertNotIn(check.detail, ('Every performed service has a selected proposal.',
                                            'No performed service falls outside the GI profiles.'))
        # The integrated routing emits gi.other for the banding (shared contract): the visit is held. Asserted, not
        # branched on, so a routing change fails here instead of silently retiring the coverage assertions (round 3
        # evidence:0); those now run unconditionally in Status19CoverageLiveTests.
        self.assertIsNotNone(route(BANDING, DOS).finding('gi.other'))
        self.assertVisitHeld(proposals, 'Other GI service is ')
        self.assertIsNone(check_of(proposals['99214'], 'em.same_day_coverage'))
        self.assertEqual(encounter_check(result, 'services.unsupported').status, 'warn')
        self.assertIn('Other GI service', encounter_check(result, 'services.unproposed').detail)

    def test_a_held_visit_carries_no_coverage_line(self):
        text = BANDING.replace('Rubber band ligation of an internal hemorrhoid was performed today without '
                               'complication.', 'Flexible sigmoidoscopy. The sigmoidoscope was advanced to 40 cm. A '
                                                'biopsy was taken from the rectum.')
        proposals, _ = real(text, ('99214', VISIT_SENTENCE), ('45331', 'A biopsy was taken from the rectum.'))
        self.assertEqual(proposals['99214'].status, 'needs_clarification')
        self.assertIsNone(check_of(proposals['99214'], 'em.same_day_coverage'))

    def test_a_found_service_outside_the_profiles_still_warns(self):
        # gi-profiles@3 profiles motility (91010 is gi.motility); a hydrogen breath test is still outside every profile
        text = HEAD + 'Hydrogen breath test performed today.\n'
        _, result = real(text, ('91065', 'Hydrogen breath test performed today.'))
        self.assertEqual(encounter_check(result, 'services.unsupported').status, 'warn')


class Status19CoverageLiveTests(RealCase):
    """Round 3 evidence:0 — the status:19 (b) coverage lines, pinned unconditionally on inputs whose same-day procedure
    routing does not detect: a plain office visit with no procedure line (routing growth cannot change it), and an
    office note whose infrared coagulation routing's gi.other form rule does not name (asserted, so a routing change
    fails loudly instead of switching branches)."""

    PLAIN = OFFICE.format(cc='Heartburn.', plan='Return in 3 months.')
    INFRARED = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Chief complaint: rectal bleeding.\n'
                'Procedure: Infrared coagulation of two internal hemorrhoids was performed today without '
                'complication.\n'
                'Medical decision making: moderate.\nTotal time: 32 minutes.\n')

    def test_the_coverage_lines_where_no_same_day_procedure_is_detected(self):
        for text in (self.PLAIN, self.INFRARED):
            with self.subTest(text=text[:200]):
                self.assertEqual([f.family for f in route(text, DOS).findings], ['gi.office_em'])
                proposals, result = real(text, ('99214', VISIT_SENTENCE))
                visit = proposals['99214']
                self.assertEqual((visit.bucket, visit.status), ('selected', 'ready'))
                coverage = check_of(visit, 'em.same_day_coverage')
                self.assertEqual(coverage, checks.SAME_DAY_COVERAGE_CHECK)
                self.assertEqual(coverage.status, 'not_verified')
                self.assertIn('not verified', coverage.detail)
                self.assertIn('hemorrhoid banding', coverage.detail)
                unproposed = encounter_check(result, 'services.unproposed')
                self.assertEqual((unproposed.status, unproposed.detail), ('pass', checks.UNPROPOSED_PASS))
                self.assertIn('not verified', unproposed.detail)
                unsupported = encounter_check(result, 'services.unsupported')
                self.assertEqual((unsupported.status, unsupported.detail), ('not_verified', checks.UNSUPPORTED_NONE))
                for slug in DETECTED_FAMILIES:
                    self.assertIn(PROFILES[slug].label, unsupported.detail)
                    if PROFILES[slug].procedure:
                        self.assertIn(PROFILES[slug].label, coverage.detail)
                for check in result.encounter_checks:
                    self.assertNotIn(check.detail, ('Every performed service has a selected proposal.',
                                                    'No performed service falls outside the GI profiles.'))


# --- review:0 at the validation layer: a reinstatable same-day procedure is named on the E/M ------------------

class Review0EngineTests(EngineCase):
    """review:0 — every selected (or reinstatable) E/M lists the excluded, reinstatable procedural selections that
    would make it a procedure day, and each such procedure says so; review gates approval on them."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for rectal bleeding.',
                'Total time 32 minutes.', 'Rubber band ligation of an internal hemorrhoid is scheduled for 2026-11-03.',
                'Return office visit is scheduled for 2026-12-01.')
    VISIT, TIME = 'Office visit: established patient seen for rectal bleeding.', 'Total time 32 minutes.'
    BAND = 'Rubber band ligation of an internal hemorrhoid is scheduled for 2026-11-03.'
    RETURN = 'Return office visit is scheduled for 2026-12-01.'

    def run_case(self, *codes, visit_facts=None, extra=()):
        self.statuses = {self.TIME: None, self.BAND: ('planned', ('planned: scheduled',)),
                         self.RETURN: ('planned', ('planned: scheduled',))}
        visit = FamilyFinding(EM, 'performed', (placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),),
                              facts=(Fact('em_basis', 'total time 32 minutes', 'document'),) + tuple(visit_facts or ()))
        return self.run_engine(self.NOTE, *codes, findings=[visit, *extra], ctx=visit_context())

    def test_the_visit_and_the_procedure_name_each_other(self):
        result = self.run_case(selected('99213', self.NOTE.span(self.TIME)),
                               selected('46221', self.NOTE.span(self.BAND)))
        visit, band = self.proposal(result, '99213'), self.proposal(result, '46221')
        self.assertEqual((visit.status, band.bucket, band.reinstatable), ('ready', 'excluded', True))
        gate = self.check(visit, 'em.same_day_if_reinstated')
        self.assertEqual(gate.status, 'warn')
        self.assertIn('46221', gate.detail)
        self.assertIn('separately identifiable E/M', gate.detail)
        marker = self.check(band, 'review.same_day_em')
        self.assertEqual(marker.status, 'warn')
        self.assertIn('99213', marker.detail)
        self.assertEqual(self.check(band, 'review.reinstatement').status, 'pass')

    def test_both_directions_an_excluded_visit_is_gated_too(self):
        result = self.run_case(selected('99213', self.NOTE.span(self.RETURN)),
                               selected('46221', self.NOTE.span(self.BAND)))
        visit = self.proposal(result, '99213')
        self.assertEqual(visit.bucket, 'excluded')
        self.assertEqual(self.check(visit, 'em.same_day_if_reinstated').status, 'warn')
        self.assertEqual(self.check(self.proposal(result, '46221'), 'review.same_day_em').status, 'warn')

    def test_nothing_is_listed_when_nothing_would_gate(self):
        no_global = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {
            PFS_INFO.key: {**PFS_ROWS, ('91200', ''): pfs(days='XXX', mult='0')}, MUE_INFO.key: MUE_ROWS})
        statement = Span(self.NOTE.offset(self.VISIT), self.NOTE.offset(self.VISIT) + len(self.VISIT), self.VISIT)
        documented = Fact('separate_em', 'documented', 'document', (statement,))
        cases = {
            'not procedural': (dict(codes=(selected('99213', self.NOTE.span(self.TIME)),
                                           selected('91200', self.NOTE.span(self.BAND)))), no_global),
            'separate E/M documented': (dict(codes=(selected('99213', self.NOTE.span(self.TIME)),
                                                    selected('46221', self.NOTE.span(self.BAND))),
                                             visit_facts=(documented,)), None),
            'not reinstatable': (dict(codes=(selected('99213', self.NOTE.span(self.TIME)),
                                             selected('46221', self.NOTE.span(self.BAND, exact=False)))), None),
        }
        for name, (kwargs, reference) in cases.items():
            with self.subTest(name):
                codes = kwargs.pop('codes')
                self.statuses = {}
                if reference is not None:
                    self.statuses = {self.TIME: None, self.BAND: ('planned', ('planned: scheduled',))}
                    visit = FamilyFinding(EM, 'performed',
                                          (placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),),
                                          facts=(Fact('em_basis', 'total time 32 minutes', 'document'),))
                    result = self.run_engine(self.NOTE, *codes, findings=[visit], ctx=visit_context(),
                                             reference=reference)
                else:
                    result = self.run_case(*codes, **kwargs)
                visit = self.proposal(result, '99213')
                self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_if_reinstated'])
                for item in result.proposals:
                    self.assertFalse([c for c in item.checks if c.id == 'review.same_day_em'], item.code)

    def test_an_already_held_visit_lists_nothing(self):
        done = finding('gi.colonoscopy', 'performed',
                       placed(self.NOTE, 'gi.colonoscopy', 'performed', self.VISIT, 'procedure', 'performed: x'),
                       facts={'extent': 'cecum'})
        result = self.run_case(selected('99213', self.NOTE.span(self.TIME)),
                               selected('46221', self.NOTE.span(self.BAND)), extra=(done,))
        visit = self.proposal(result, '99213')
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_if_reinstated'])
        # Nor is the procedure marked: on a procedure day reinstating it changes nothing for the E/M.
        self.assertFalse([c for c in self.proposal(result, '46221').checks if c.id == 'review.same_day_em'])


# --- status:1, the validation-side guard: an excluded procedure stated as done still holds the E/M ------------

S1 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit for rectal bleeding.\n'
      'History of present illness: Two weeks of intermittent bright red blood per rectum. Prior flexible '
      'sigmoidoscopy in 2022 was normal.\nProcedure: Flexible sigmoidoscopy to evaluate rectal bleeding.\n'
      'Findings: The sigmoidoscope was advanced to 40 cm. A biopsy was taken from the rectum.\n'
      'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


class Status1GuardRealTests(RealCase):
    """status:1's exact input. The main fix is routing's aggregation (another agent); at this commit routing still
    reads the family historical and excludes 45331, and the guard alone keeps the same-day E/M held."""

    def test_the_claimed_input_holds_the_visit(self):
        proposals, _ = real(S1, ('99214', 'Established patient office visit for rectal bleeding.'),
                            ('45331', 'A biopsy was taken from the rectum.'))
        self.assertVisitHeld(proposals, 'Flexible sigmoidoscopy is ')


class Status1GuardTests(EngineCase):
    """The guard at the validation layer, with constructed routing: an excluded procedural selection whose own
    passage states the act explicitly ('performed:' cue) while its reading was made negative elsewhere (by the
    family's document-level status) counts as possibly performed for the E/M hold. A passage routing read as not
    today because of its own section, date or wording does not."""

    NOTE = Note('Date of service: 2026-10-21', 'Established patient office visit for rectal bleeding.',
                'Total time 32 minutes.', 'Prior flexible sigmoidoscopy in 2022 was normal.',
                'Flexible sigmoidoscopy to evaluate rectal bleeding.', 'A biopsy was taken from the rectum.')
    VISIT, TIME = 'Established patient office visit for rectal bleeding.', 'Total time 32 minutes.'
    PRIOR = 'Prior flexible sigmoidoscopy in 2022 was normal.'
    LINE = 'Flexible sigmoidoscopy to evaluate rectal bleeding.'
    BIOPSY = 'A biopsy was taken from the rectum.'

    def visit_for(self, biopsy_reading, code='45331', reference=REFERENCE):
        self.statuses = {self.TIME: None, self.BIOPSY: biopsy_reading}
        visit = finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        # Round 4d validation:6: a hedged mention outside plan, history and indication sections of a family not read
        # as done holds the E/M on its own (ARCHITECTURE 5.6), so the constructed procedure line sits in an indication
        # section here: these tests isolate the guard (an excluded code stated as done), not that rule.
        flex = finding('gi.flex_sig', 'historical',
                       placed(self.NOTE, 'gi.flex_sig', 'historical', self.PRIOR, 'history',
                              'historical: 2022 is before the service date', 'historical: Prior'),
                       placed(self.NOTE, 'gi.flex_sig', 'uncertain', self.LINE, 'indication',
                              "uncertain: section silent: 'to evaluate' follows the service name",
                              'section: indication (Indication)'),
                       facts={'extent': '40 cm'})
        result = self.run_engine(self.NOTE, selected('99214', self.NOTE.span(self.TIME)),
                                 selected(code, self.NOTE.span(self.BIOPSY)), findings=[visit, flex],
                                 ctx=visit_context(), reference=reference)
        self.assertEqual(self.proposal(result, code).bucket, 'excluded')
        return self.proposal(result, '99214')

    def test_a_passage_stated_as_done_holds_the_visit(self):
        for status in ('historical', 'planned', 'negated', 'cancelled'):
            with self.subTest(status=status):
                visit = self.visit_for((status, ('performed: was taken', f'{status}: from the family')))
                self.assertEqual(visit.status, 'needs_clarification')
                self.assertIn('separate_em', [c.fact for c in visit.clarifications])
                self.assertIn('Flexible sigmoidoscopy is possibly performed on the same date',
                              self.check(visit, 'em.same_day_procedure').detail)

    def test_controls_a_passage_read_as_not_today_on_its_own_does_not(self):
        for reading in (('historical', ('performed: underwent', 'section: history (History of present illness)')),
                        ('historical', ('historical: 2019 is before the service date',)),
                        ('planned', ('planned: scheduled',)),
                        ('negated', ('negated: an unchecked box',)),
                        ('cancelled', ('section: procedure (Procedure)', 'cancelled: the procedure was cancelled'))):
            with self.subTest(reading=reading):
                visit = self.visit_for(reading)
                self.assertEqual(visit.status, 'ready', [c.detail for c in visit.checks])
                self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])

    def test_controls_a_code_that_is_not_procedural_does_not(self):
        visit = self.visit_for(('historical', ('performed: was taken', 'historical: from the family')), code='91200')
        self.assertEqual(visit.status, 'ready', [c.detail for c in visit.checks])


class EngineVersionTests(SimpleTestCase):
    def test_the_engine_version_is_bumped_once(self):
        # @4: the documented-service inventory decides the codes it matches (ARCHITECTURE 5.9-5.11)
        self.assertEqual(ENGINE_VERSION, 'cpt-studio-validation@4')
