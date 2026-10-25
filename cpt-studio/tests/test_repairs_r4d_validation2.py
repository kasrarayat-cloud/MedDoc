"""Regressions for refutation round 6 over validation (round 4d repairs, VALIDATION2).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
from datetime import date

from tests.test_repairs_r3_validation_b import HEAD, Case, check_of, encounter_check, real

DAY = date(2026, 10, 21)
FOLLOW_UP = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
             'Chief complaint: follow-up after hemorrhoid banding.\nFindings: {line}\nMedical decision making: moderate.\n'
             'Total time: 32 minutes.\n')
BANDING = HEAD + 'Procedure: Hemorrhoid banding\nIndication: Bleeding internal hemorrhoids.\nFindings: {find}\n'
OFFICE_PROCEDURE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                    'Chief complaint: follow-up after hemorrhoid banding.\nProcedure: {line}\n'
                    'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


# --- validation:3: "we" after a time or condition clause states no act of today -------------------------------------

class Validation3TemporalLeadTests(Case):
    """validation:3 (critical, regression against 9a9f403). 'When she presented with bleeding, we banded two columns, and
    today they look healed.' made 46221 READY in a follow-up office note: round 5 validation:2's comma arm accepted any
    lead ending in a comma, so a time or condition clause - or a phrase naming no listed occasion ('At that time,',
    'Back then,', 'On referral,') - introduced a banding that was done at an earlier encounter. Such a lead now introduces
    nothing (hold-only): it opens with a time or condition conjunction, holds a subject or an auxiliary of its own, or
    is a comma-ended phrase that opens with neither a listed introductory word nor 'in'."""

    LEADS = ('When she presented with bleeding,', 'When she was seen in clinic,', 'While she was in the hospital,',
             'Once the bleeding started,', 'At that time,', 'At the time,', 'Back then,', 'On referral,',
             'At her consultation,', 'If she bled,', 'On presentation,', 'After she presented with bleeding,',
             'Whenever she bled,', 'Until she was referred,', 'Since she bled,', 'As soon as she bled,',
             # an introductory word, then a time clause of its own in the same lead
             'Then once the bleeding started', 'Subsequently, once the bleeding started,', 'Then, if needed,',
             # an introductory word naming another occasion by its event
             'During her consultation,', 'Following her referral,', 'During her hospitalization,')

    def test_the_claimed_leads_hold_the_banding_in_a_follow_up_note(self):
        for lead in self.LEADS:
            line = f'{lead} we banded two columns, and today they look healed.'
            with self.subTest(lead=lead):
                proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line), ('99213', 'Total time: 32 minutes.'))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')
                self.assertNotIn('Documented as performed', check_of(proposals['46221'], 'service.status').detail)

    def test_the_claimed_leads_hold_under_a_procedure_heading_and_in_a_banding_report(self):
        for lead in ('When she presented with bleeding,', 'At that time,', 'On presentation,', 'If she bled,'):
            line = f'{lead} we banded two columns, and today they look healed.'
            with self.subTest(lead=lead, layout='office procedure heading'):
                proposals, _ = real(OFFICE_PROCEDURE.format(line=line), ('46221', line))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')
            line = f'{lead} we banded two columns.'
            with self.subTest(lead=lead, layout='banding report'):
                proposals, _ = real(BANDING.format(find=line), ('46221', line))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')

    def test_controls_an_introductory_phrase_of_today_s_procedure_still_states_the_act(self):
        for line in ('In the left lateral position, we banded two columns today.',
                     'After informed consent, we banded the right posterior column today.',
                     'Using the McGivney ligator, we banded two columns today.',
                     'Under direct anoscopic visualization, we banded the left lateral column today.',
                     'This morning, we banded two columns.', 'Today, we banded two columns.',
                     'Today we banded two internal hemorrhoids.'):
            with self.subTest(line=line):
                proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line))
                self.assertReady(proposals['46221'])
        for line in ('After informed consent, we banded the right posterior column.',
                     'With the patient in the left lateral position we banded the left lateral column.',
                     'In the left lateral position, we banded the right posterior column.'):
            with self.subTest(line=line, layout='banding report'):
                proposals, _ = real(BANDING.format(find=line), ('46221', line))
                self.assertReady(proposals['46221'])
