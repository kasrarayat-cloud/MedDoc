"""Round-4b validation repairs end to end: the real pipeline (extraction, routing, validation, review, reports) through
the JSON API with an in-process fake provider, no network. Only holds and the draft report are asserted here: a held
code offers reject alone and its approval is refused, which does not depend on how review treats an excluded code.
Synthetic data only.
"""
from datetime import date, datetime, timezone

from django.test import TestCase, override_settings

from studio.models import ReferenceCodeFact, ReferenceSource
from tests.test_repairs_pipeline import LIVE
from tests.test_repairs_status_r2_validation_api import MultiEvidenceApiCase

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-21\n'
OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{body}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
VISIT = 'Established patient office visit.'


def row(global_days):
    return {'status': 'A', 'global_days': global_days, 'mult_proc': '0', 'endo_base': None, 'pctc': '0'}


@override_settings(**LIVE)
class RoundFourValidationApiTests(MultiEvidenceApiCase, TestCase):
    def setUp(self):
        super().setUp()
        common = dict(publisher='CMS', url='https://www.cms.gov/synthetic',
                      retrieved_at=datetime(2026, 10, 23, tzinfo=timezone.utc), effective_start=date(2026, 10, 1),
                      effective_end=date(2026, 12, 31), license_note='synthetic', scope_note='synthetic')
        pfs = ReferenceSource.objects.create(key='cms-pfs-rvu26d', kind='cms-pfs', title='RVU26D synthetic',
                                             release='RVU26D', sha256='b' * 64, row_count=5, **common)
        for code, days in (('99213', 'XXX'), ('99214', 'XXX'), ('91010', 'XXX'), ('91122', 'XXX'), ('46221', '010')):
            ReferenceCodeFact.objects.create(source=pfs, code=code, facts=row(days))

    def assertHeld(self, encounter_id, code):
        item = self.proposal(encounter_id, code)
        self.assertEqual((item['status'], item['allowed_actions']), ('needs_clarification', ['reject']))
        self.assertEqual(self.decide(encounter_id, code, 'approve').status_code, 409)

    def test_validation0_a_hedged_diagnosis_beside_a_stated_procedure_holds_the_visit(self):
        note = OFFICE.format(body='Impression: Flexible sigmoidoscopy was performed with biopsies, proctitis versus '
                                  'infection.')
        self.assertHeld(self.run_note(note, ('99214', VISIT)), '99214')

    def test_validation1_a_test_code_citing_a_banding_sentence_holds_the_visit(self):
        line = 'Anorectal manometry was performed today, followed by rubber band ligation of two columns.'
        encounter_id = self.run_note(OFFICE.format(body=line), ('99213', VISIT), ('91122', line))
        self.assertHeld(encounter_id, '99213')
        self.assertIn('[WARN] em.same_day_procedure', self.report_text(encounter_id))

    def test_validation2_a_healed_banding_site_never_makes_46221_approvable(self):
        note = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Chief complaint: follow-up after hemorrhoid banding.\nFindings: Banding sites well healed.\n'
                'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
        self.assertHeld(self.run_note(note, ('46221', 'Banding sites well healed.')), '46221')

    def test_validation3_a_visit_statement_worded_as_performed_never_makes_46221_approvable(self):
        visit = 'Established patient office visit was performed today.'
        note = (HEAD + f'Place of service: Office (POS 11)\n{visit}\nChief complaint: rectal bleeding.\n'
                'Procedure: Anoscopy - patient declined.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
        self.assertHeld(self.run_note(note, ('46221', visit)), '46221')

    def test_release7_a_banding_after_the_chief_complaint_holds_the_visit(self):
        note = OFFICE.format(body='Chief complaint: Rectal bleeding.\nTwo internal hemorrhoids were banded today without '
                                  'complication.')
        self.assertHeld(self.run_note(note, ('99214', VISIT)), '99214')

    def test_validation8_the_draft_report_names_an_excluded_code_outside_the_profiles(self):
        plan = 'Rubber band ligation of the internal hemorrhoids.'
        encounter_id = self.run_note(OFFICE.format(body=f'Plan: {plan}'), ('99213', VISIT), ('46221', plan))
        text = self.report_text(encounter_id)
        self.assertIn('[WARN] services.unsupported — Services outside the GI profiles: Selected without a GI profile in '
                      'this release, excluded by its documented status (a reviewer may reinstate it): Other GI service '
                      '(46221).', text)
        self.assertNotIn('No selected code or detected service falls outside the GI profiles', text)
