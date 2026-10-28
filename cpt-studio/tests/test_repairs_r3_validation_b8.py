"""Regressions for refutation round 3, validation:8, as round 4 left them.

Round 3b released the office E/M when a procedure was only hedged under Assessment, Impression, an examination or MDM
section (engine.DISCUSSION_SECTIONS with checks.hedges_only and checks.says_today_near). Round 4 validation:0 showed the
release also fired for a procedure stated as performed whose sentence hedges the diagnosis ("Flexible sigmoidoscopy
was performed with biopsies, proctitis versus infection."), because routing keeps only the hedge cue there. The release
and its helpers were reverted to the R3B-BASE reading, so the round-3 over-hold (medium) returns: these inputs hold the
E/M again. The round-4 regressions are in tests/test_repairs_r4_validation.py. Real routing, the real span reader and
the engine; synthetic text only.
"""
from datetime import date

from studio.gi.detect import route
from studio.validation import checks
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, encounter_check, real


V8 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: Heartburn.\n'
      '{line}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
EGD_HELD = 'Upper GI endoscopy (EGD, esophagoscopy, POEM) is '


class Validation8AssessmentHedgeTests(Case):
    """validation:8 after the round-4 revert: a procedure discussed, weighed or conditioned under Assessment,
    Impression, an examination or MDM section holds the E/M (the accepted over-hold). Under Plan it does not."""

    # round 3b's released inputs, held again
    HELD_AGAIN = (
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

    def test_round_3b_s_released_inputs_hold_the_visit_again(self):
        for line in self.HELD_AGAIN:
            with self.subTest(line=line):
                text = V8.format(line=line)
                self.assertEqual(route(text, date(2026, 10, 21)).finding('gi.egd').status, 'uncertain')
                proposals, _ = real(text, ('99214', VISIT))
                self.assertVisitHeld(proposals, EGD_HELD)

    def test_an_mdm_discussion_holds_the_visit_again(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate; EGD versus empiric PPI trial was discussed.\n'
                'Total time: 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT))
        self.assertVisitHeld(proposals, EGD_HELD)

    def test_the_second_symptom_returns_with_the_hold(self):
        # On a possible procedure day an unproposed E/M is not reported as missed (as at R3B-BASE).
        _, result = real(V8.format(line='Assessment: GERD; possible EGD if refractory.'))
        unproposed = encounter_check(result, 'services.unproposed')
        self.assertEqual((unproposed.status, unproposed.detail), ('info', checks.VISIT_NOT_MISSED))

    def test_controls_a_plan_hedge_stays_released(self):
        proposals, _ = real(V8.format(line='Plan: GERD, not controlled. Possible EGD if symptoms persist.'),
                            ('99214', VISIT))
        self.assertVisitReady(proposals)

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
                self.assertVisitHeld(proposals, EGD_HELD)
