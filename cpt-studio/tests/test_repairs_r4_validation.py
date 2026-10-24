"""Regressions for refutation round 4 over validation (round 4b repairs).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
from studio.gi.profiles import PROFILES
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, check_of, real

OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{line}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
FLEX_LABEL = PROFILES['gi.flex_sig'].label
EGD_LABEL = PROFILES['gi.egd'].label
OTHER_LABEL = PROFILES['gi.other'].label


# --- validation:0: a hedge beside a stated act never releases the E/M (round 3b's discussion release reverted) ------

class Validation0DiscussionReleaseRevertedTests(Case):
    """validation:0 (critical, new defect from 7198dd0fc). A hedge about the diagnosis in the sentence that states a
    procedure as performed ("Flexible sigmoidoscopy was performed with biopsies, proctitis versus infection.") left
    routing's mention only its hedge cue, and the discussion-section release then read the procedure as merely weighed:
    the office E/M was ready and approvable beside a same-day procedure. The release is reverted (R3B-BASE reading): in
    an assessment, impression, examination, MDM or time section an uncertain mention that routing saw something in
    holds the E/M again."""

    HELD = (
        ('Impression: Flexible sigmoidoscopy was performed with biopsies, proctitis versus infection.', FLEX_LABEL),
        ('Assessment: Rectal bleeding. Rubber band ligation x3 was performed, ?fissure.', OTHER_LABEL),
        ('Physical examination: Anoscopy was performed and showed grade 2 internal hemorrhoids versus prolapse.',
         OTHER_LABEL),
        ('Physical examination: Abdomen soft. Anoscopy performed? Yes. Grade 2 internal hemorrhoids.', OTHER_LABEL),
        # the same day stated in words outside routing's TODAY list
        ('Impression: Flexible sigmoidoscopy was performed at this visit with biopsies, proctitis versus infection.',
         FLEX_LABEL),
        ('Assessment: Anoscopy was performed in the office and showed grade 2 internal hemorrhoids versus prolapse.',
         OTHER_LABEL),
        ('Assessment: Rectal bleeding. Rubber band ligation x3 was performed during this visit, ?fissure.',
         OTHER_LABEL),
        ('Assessment: EGD was performed at this visit with biopsies, ?Barrett esophagus.', EGD_LABEL),
    )

    def test_the_claimed_inputs_hold_the_visit(self):
        for line, label in self.HELD:
            with self.subTest(line=line):
                proposals, _ = real(OFFICE.format(line=line), ('99214', VISIT))
                self.assertVisitHeld(proposals, f'{label} is possibly performed on the same date')
                self.assertIsNone(check_of(proposals['99214'], 'em.same_day_coverage'))

    def test_a_question_in_the_mdm_line_holds_the_visit(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate; flexible sigmoidoscopy performed? yes, biopsies taken.\n'
                'Total time: 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT))
        self.assertVisitHeld(proposals, f'{FLEX_LABEL} is possibly performed on the same date')

    def test_the_round_3_over_hold_returns_with_the_revert(self):
        """Accepted (medium): a procedure only discussed or weighed under Assessment or Impression holds the E/M
        again, as at R3B-BASE. Under Plan it stays released (unchanged)."""
        for line in ('Assessment: GERD, not controlled. Possible EGD if symptoms persist.',
                     'Impression: GERD, not controlled; EGD if symptoms persist.'):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE.format(line=line), ('99214', VISIT))
                self.assertVisitHeld(proposals, f'{EGD_LABEL} is possibly performed on the same date')
        proposals, _ = real(OFFICE.format(line='Plan: Possible EGD if symptoms persist.'), ('99214', VISIT))
        self.assertVisitReady(proposals)
