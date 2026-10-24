"""Regressions for refutation round 3, validation:4: only a hedge about the code's own service contests it.
Real routing, the real span reader and the engine; synthetic text only.
"""
from django.test import SimpleTestCase

from studio.validation import checks
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, check_of, real


# --- validation:4: only a hedge about the code's own service contests it -------------------------------------

OFFICE_PLAN = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
               'Chief complaint: Heartburn.\n'
               'History of present illness: Intermittent heartburn for 8 weeks despite omeprazole. No dysphagia.\n'
               'Assessment: {assessment}\nPlan: {plan}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
TIME = 'Total time: 32 minutes.'
POLYP = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
COLONOSCOPY_AP = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. ' + POLYP + '\n'
                  '{tail}\n')


class Validation4ContestedOwnServiceTests(Case):
    """validation:4 — a hedge about a different service (another procedure, a diagnosis), or a performance statement
    downgraded only by its section, does not contest a code another of its passages shows as performed."""

    def test_an_e_m_citing_the_plan_hedge_of_an_egd(self):
        for plan, evidence in (('Increase omeprazole to 40 mg twice daily. Possible EGD if symptoms persist.',
                                (TIME, 'Possible EGD if symptoms persist.')),
                               ('EGD versus empiric PPI trial; the patient prefers the PPI trial.',
                                (VISIT, 'EGD versus empiric PPI trial; the patient prefers the PPI trial.'))):
            with self.subTest(plan=plan):
                text = OFFICE_PLAN.format(assessment='Gastroesophageal reflux disease, not controlled.', plan=plan)
                proposals, _ = real(text, ('99214', *evidence))
                visit = proposals['99214']
                self.assertReady(visit)
                status = check_of(visit, 'service.status')
                self.assertEqual(status.status, 'warn')
                self.assertIn(f'Another linked passage reads as uncertain: “{evidence[1]}”', status.detail)

    def test_an_e_m_citing_a_diagnostic_question(self):
        text = OFFICE_PLAN.format(assessment='Epigastric pain; rule out celiac disease?', plan='PPI.')
        proposals, _ = real(text, ('99213', TIME, 'Epigastric pain; rule out celiac disease?'))
        self.assertReady(proposals['99213'])

    def test_a_procedure_code_citing_its_performance_restated_in_the_plan(self):
        restatements = (('Assessment and plan: Colonoscopy with cold snare polypectomy was performed today. Repeat '
                         'colonoscopy in 5 years.', 'Colonoscopy with cold snare polypectomy was performed today.'),
                        ('Plan: Polypectomy completed today; await pathology.',
                         'Polypectomy completed today; await pathology.'))
        for tail, restated in restatements:
            with self.subTest(restated=restated):
                proposals, _ = real(COLONOSCOPY_AP.format(tail=tail), ('45385', POLYP, restated))
                item = proposals['45385']
                self.assertReady(item)
                self.assertEqual(check_of(item, 'service.status').status, 'pass')

    def test_controls_a_hedge_about_the_code_s_own_service_still_contests(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate.\nTotal time: approximately 30 minutes?\n')
        proposals, _ = real(text, ('99214', VISIT, 'Total time: approximately 30 minutes?'))
        self.assertEqual(proposals['99214'].status, 'needs_clarification')
        hedges = (('Plan: Repeat colonoscopy if symptoms persist.', 'Repeat colonoscopy if symptoms persist.'),
                  ('A 5 mm cecal lesion was seen?', 'A 5 mm cecal lesion was seen?'))
        for tail, hedge in hedges:
            with self.subTest(hedge=hedge):
                proposals, _ = real(COLONOSCOPY_AP.format(tail=tail), ('45385', POLYP, hedge))
                item = proposals['45385']
                self.assertEqual(item.status, 'needs_clarification')
                self.assertIn('A passage that hedges holds the code', check_of(item, 'service.status').detail)

    def test_controls_a_hedge_alone_still_holds(self):
        text = OFFICE_PLAN.format(assessment='GERD.', plan='Possible EGD if symptoms persist.')
        proposals, _ = real(text, ('99214', 'Possible EGD if symptoms persist.'))
        self.assertEqual(proposals['99214'].status, 'needs_clarification')
        self.assertIn('performed_status', [c.fact for c in proposals['99214'].clarifications])


class Validation4ResolveStatusTests(SimpleTestCase):
    """validation:4 at the resolve_status level, with the engine's flag stated explicitly."""

    POSITIVE = checks.Reading('performed', ('performed: office E/M documentation (E/M time)',), 'evidence', TIME)
    OTHER = checks.Reading('uncertain', ('uncertain: if symptoms persist',), 'evidence',
                           'Possible EGD if symptoms persist.', other_service=True)
    RESTATED = checks.Reading('uncertain', ('performed: was performed', 'section: plan (Plan)'), 'evidence',
                              'Colonoscopy was performed today.')
    OWN = checks.Reading('uncertain', ('uncertain: ?',), 'evidence', 'Biopsies were taken?')

    def test_only_a_hedge_about_the_code_s_own_service_contests(self):
        outcome = checks.resolve_status([self.POSITIVE, self.OTHER])
        self.assertEqual((outcome.state, outcome.decisive, outcome.contrary), ('performed', self.POSITIVE, self.OTHER))
        self.assertIn('Another linked passage reads as uncertain: “Possible EGD if symptoms persist.”',
                      checks.status_check(outcome, 'Office / outpatient evaluation and management').detail)
        outcome = checks.resolve_status([self.RESTATED, self.POSITIVE])
        self.assertEqual((outcome.state, outcome.decisive, outcome.contrary), ('performed', self.POSITIVE, None))
        outcome = checks.resolve_status([self.POSITIVE, self.OTHER, self.OWN])
        self.assertEqual((outcome.state, outcome.reason, outcome.decisive), ('uncertain', 'contested', self.OWN))

    def test_a_downgraded_statement_with_any_other_cue_is_a_hedge(self):
        doubted = checks.Reading('uncertain', ("uncertain: unresolved negation 'not' in its clause",
                                               'performed: was performed', 'section: plan (Plan)'), 'evidence', 'X.')
        self.assertFalse(checks.restated(doubted))
        self.assertTrue(checks.restated(self.RESTATED))
        outcome = checks.resolve_status([self.POSITIVE, doubted])
        self.assertEqual((outcome.state, outcome.reason), ('uncertain', 'contested'))

    def test_a_hedge_alone_holds_whatever_it_is_about(self):
        for hedge in (self.OTHER, self.RESTATED):
            with self.subTest(hedge=hedge.passage):
                outcome = checks.resolve_status([hedge])
                self.assertEqual((outcome.state, outcome.reason, outcome.decisive), ('uncertain', 'hedged', hedge))
