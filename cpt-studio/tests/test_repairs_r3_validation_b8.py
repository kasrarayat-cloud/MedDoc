"""Regressions for refutation round 3, validation:8: a hedge outside a section that documents performance does not
hold the E/M. Real routing, the real span reader and the engine; synthetic text only.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi.detect import SILENT, route
from studio.types import FamilyFinding, ServiceMention, Span
from studio.validation import checks
from tests.test_repairs_status_r2_validation import placed
from tests.test_validation import EGD, EM, EngineCase, Note, finding, selected, visit_context
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, encounter_check, real


# --- validation:8: a hedge outside a section that documents performance does not hold the E/M ---------------------

V8 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: Heartburn.\n'
      '{line}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')


class Validation8AssessmentHedgeTests(Case):
    """validation:8 — a procedure discussed, weighed or conditioned under Assessment, Impression, an examination or
    MDM section does not hold the E/M, as under Plan. A doubt about today's service, a clause that says today, an
    explicit performance statement, and any hedge in a procedure, findings, technique or unheaded section still do."""

    RELEASED = (
        'Assessment: Gastroesophageal reflux disease, not controlled. Discussed EGD; the patient will think about it.',
        'Assessment: GERD. EGD versus empiric PPI trial; the patient prefers the PPI trial.',
        'Assessment: GERD, not controlled. Possible EGD if symptoms persist.',
        'Impression: GERD, not controlled; EGD if symptoms persist.',
        'Physical examination: Abdomen soft. Possible EGD candidate.',
        'Diagnosis: GERD. Possible EGD if symptoms persist.',
        'Clinical impression: GERD; possible EGD.',
        'Summary: GERD; EGD versus PPI trial.',
        'Assessment:\n1. GERD.\n2. Possible EGD if symptoms persist.',
        'Assessment: Risks and benefits of EGD were discussed; the patient will decide at the next visit.',
        'Assessment: GERD; possible EGD if refractory.',
    )

    def test_the_claimed_inputs_are_ready(self):
        for line in self.RELEASED:
            with self.subTest(line=line):
                text = V8.format(line=line)
                self.assertEqual(route(text, date(2026, 10, 21)).finding('gi.egd').status, 'uncertain')
                proposals, _ = real(text, ('99214', VISIT))
                self.assertVisitReady(proposals)

    def test_an_mdm_discussion_is_ready(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate; EGD versus empiric PPI trial was discussed.\n'
                'Total time: 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT))
        self.assertVisitReady(proposals)

    def test_the_second_symptoms_follow(self):
        text = V8.format(line='Assessment: GERD; possible EGD if refractory.')
        _, result = real(text)
        unproposed = encounter_check(result, 'services.unproposed')
        self.assertEqual(unproposed.status, 'warn')
        self.assertIn('Possible missed service: Office / outpatient evaluation and management', unproposed.detail)

    def test_controls_still_held(self):
        held = (
            'Assessment: Dysphagia. EGD pending NPO status.',  # a doubt: pending
            'Assessment: Dysphagia. EGD aborted.',  # a doubt: an abort that does not say whether it started
            'Assessment: Dysphagia. Possible EGD later today.',  # its clause says today
            'Assessment: EGD was performed today with biopsies of the antrum.',  # a performance statement
            'Procedure: Possible EGD.',  # a procedure section
        )
        unheaded = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                    'Possible EGD if the stricture is confirmed.\nMedical decision making: moderate.\n')  # fail-closed
        for text in [V8.format(line=line) for line in held] + [unheaded]:
            with self.subTest(text=text):
                proposals, _ = real(text, ('99214', VISIT))
                self.assertVisitHeld(proposals, 'Upper GI endoscopy (EGD, esophagoscopy, enteroscopy) is ')


class Validation8HedgeCueTests(SimpleTestCase):
    """checks.hedges_only, the inverted reading: only cues that quote routing's own hedge words are hedges."""

    def test_routing_s_hedges(self):
        for cue in ('uncertain: ?', 'uncertain: versus', 'uncertain: vs.', 'uncertain: if symptoms persist',
                    'uncertain: as needed', 'uncertain: unclear whether', 'uncertain: candidate for',
                    'uncertain: Possible', 'uncertain: possible', 'uncertain: Discussed', 'uncertain: Consent for',
                    'uncertain: were discussed', 'uncertain: may be needed'):
            with self.subTest(cue=cue):
                self.assertTrue(checks.hedges_only((cue,)))
        self.assertTrue(checks.hedges_only(('uncertain: if symptoms persist', 'uncertain: Possible')))

    def test_anything_else_is_not_a_hedge(self):
        for cues in (('uncertain: pending',), ('uncertain: Pending',),
                     ('uncertain: aborted, with no statement whether the procedure had started',),
                     ("uncertain: unresolved negation 'not' in its clause",),
                     ("uncertain: part of the passage is denied ('no EGD?')",),
                     ('uncertain: dated 10/21; service date not established',),
                     ('uncertain: Possible', 'uncertain: pending'), ('uncertain: versus', 'negated: not done'),
                     ('uncertain: versus', 'planned: if needed'),  # only an 'uncertain:' cue is a hedge
                     ('uncertain: versus EGD today',), ('performed: was performed',), (), (SILENT,)):
            with self.subTest(cues=cues):
                self.assertFalse(checks.hedges_only(cues))


class Validation8TodayReachTests(EngineCase):
    """"Today" is read near the mention (checks.TODAY_REACH, as routing reads a clause), so a long sentence with many
    mentions is never scanned in full once per mention."""

    def visit_for(self, line):
        note = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for dysphagia.',
                    'Total time 32 minutes.', line)
        self.statuses = {'Total time 32 minutes.': None}
        visit = finding(EM, 'performed', placed(note, EM, 'performed', 'Office visit: established patient seen for '
                                                                       'dysphagia.', 'other', 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        start = note.offset(line)
        egd = ServiceMention(family=EGD, status='uncertain', span=Span(start + 9, start + 12, 'EGD'),
                             sentence=Span(start, start + len(line), line), section='assessment',
                             cues=('uncertain: Possible',))
        result = self.run_engine(note, selected('99213', note.span('Total time 32 minutes.')),
                                 findings=[visit, FamilyFinding(EGD, 'uncertain', (egd,))], ctx=visit_context())
        return self.proposal(result, '99213')

    def test_today_near_the_mention_holds_and_far_from_it_does_not(self):
        near = 'Possible EGD later today.'
        far = 'Possible EGD; ' + 'the family discussed diet and weight at length; ' * 8 + 'labs today.'
        self.assertGreater(far.index('today'), 12 + checks.TODAY_REACH)
        self.assertEqual(self.visit_for(near).status, 'needs_clarification')
        self.assertEqual(self.visit_for(far).status, 'ready')
