"""Regressions for refutation round 3, validation:3: an office E/M whose evidence is its own history or plan
sentence. Real routing, the real span reader and the engine; synthetic text only.
"""
from datetime import date

from studio.gi.detect import route
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, check_of, encounter_check, real


# --- validation:3: an E/M's own HPI or plan is not dated by its section --------------------------------------------

V3 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint\nHeartburn.\n'
      'History of present illness\nIntermittent heartburn for 8 weeks despite omeprazole.\n'
      'Assessment and plan\nGERD, not controlled. Increase omeprazole to 40 mg twice daily.\n'
      'Counseling\nReviewed dietary triggers, head-of-bed elevation and weight loss with the patient.\n{extra}'
      'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
HPI = 'Intermittent heartburn for 8 weeks despite omeprazole.'
PLAN = 'Increase omeprazole to 40 mg twice daily.'


class Validation3EmSectionDefaultTests(Case):
    """validation:3 — an office E/M whose evidence is its own history or plan sentence is not excluded as historical or
    planned by the section default: routing's E/M reading (visit statement, MDM, time) decides."""

    def test_history_plan_and_counseling_evidence_is_ready(self):
        for evidence in ((HPI,), (PLAN,), ('GERD, not controlled.',),
                         ('Reviewed dietary triggers, head-of-bed elevation and weight loss with the patient.',),
                         (HPI, PLAN), (VISIT, HPI)):
            with self.subTest(evidence=evidence):
                proposals, result = real(V3.format(extra=''), ('99213', *evidence))
                visit = proposals['99213']
                self.assertReady(visit)
                status = check_of(visit, 'service.status')
                self.assertEqual(status.status, 'pass')
                self.assertNotIn('historical', status.detail)
                self.assertNotIn('planned', status.detail)
                self.assertEqual(encounter_check(result, 'services.unproposed').status, 'pass')

    def test_controls_a_cue_that_dates_the_e_m_is_never_its_evidence(self):
        # Engine @4: today's documented visit decides the code (interpretation 9: a passage about another time no
        # longer decides); a passage dated to another visit is never read as showing today's.
        text = V3.format(extra='Return office visit is scheduled for 2026-12-01.\n')
        proposals, _ = real(text, ('99213', 'Return office visit is scheduled for 2026-12-01.'))
        visit = proposals['99213']
        self.assertReady(visit)
        self.assertEqual((check_of(visit, 'evidence.support').status, visit.support['unrelated']), ('warn', [0]))
        self.assertIn('Established patient office visit.', [s['text'] for s in visit.support['source']])
        proposals, _ = real(text, ('99213', HPI, 'Return office visit is scheduled for 2026-12-01.'))
        self.assertEqual((proposals['99213'].support['supporting'], proposals['99213'].support['unrelated']), ([0], [1]))

    def test_controls_a_visit_statement_in_the_plan_keeps_its_reading(self):
        # The passage is itself a visit statement routing reads in the plan section: a later visit, not today's.
        # Engine @4: today's documented visit decides the code (interpretation 9), and the passage is never read as
        # showing it - CPT Studio selects the passages that do.
        for line in ('Follow-up office visit.', 'Office visit next spring.'):
            with self.subTest(line=line):
                proposals, _ = real(V3.format(extra=f'{line}\n'), ('99213', line))
                visit = proposals['99213']
                self.assertReady(visit)
                self.assertEqual((check_of(visit, 'evidence.support').status, visit.support['unrelated']),
                                 ('warn', [0]))
                self.assertIn('Established patient office visit.', [s['text'] for s in visit.support['source']])

    def test_with_no_e_m_documented_the_e_m_is_held_not_ready(self):
        text = (HEAD + 'Procedure: Colonoscopy\nHistory of present illness: Rectal bleeding for two weeks.\n'
                'Findings: The colonoscope was advanced to the cecum. Normal colon.\n')
        proposals, _ = real(text, ('99213', 'Rectal bleeding for two weeks.'))
        self.assertEqual((proposals['99213'].bucket, proposals['99213'].status), ('selected', 'needs_clarification'))

    def test_controls_a_procedure_code_citing_history_never_takes_it_as_its_evidence(self):
        # The rule is the E/M's alone: a colonoscopy code citing the HPI of a colonoscopy routing reads as performed
        # never takes the HPI as showing its act. Engine @4: the documented biopsy decides the code (interpretation 9),
        # and CPT Studio selects the passage that shows it.
        text = (HEAD + 'History of present illness: Rectal bleeding for two weeks.\nProcedure: Colonoscopy\n'
                'Findings: The colonoscope was advanced to the cecum. A 5 mm polyp was biopsied with cold forceps.\n')
        self.assertEqual(route(text, date(2026, 10, 21)).finding('gi.colonoscopy').status, 'performed')
        proposals, _ = real(text, ('45380', 'Rectal bleeding for two weeks.'))
        biopsy = proposals['45380']
        self.assertReady(biopsy)
        self.assertEqual((check_of(biopsy, 'evidence.support').status, biopsy.support['unrelated']), ('warn', [0]))
        self.assertEqual([s['text'] for s in biopsy.support['source']], ['A 5 mm polyp was biopsied with cold forceps.'])

    def test_controls_an_e_m_passage_read_performed_by_its_section_stays_the_evidence(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate.\nTime\nTotal time on the date of the encounter was 32 minutes.\n'
                'This time excludes separately reported services.\n')
        proposals, _ = real(text, ('99213', 'This time excludes separately reported services.'))
        visit = proposals['99213']
        self.assertReady(visit)
        # Engine @4: the documented visit is the status; the passage read performed by its section shows it.
        self.assertEqual(check_of(visit, 'service.status').detail,
                         'The office / outpatient visit is documented as performed.')
        self.assertEqual((check_of(visit, 'evidence.support').status, visit.support['supporting']), ('pass', [0]))
