"""Round-3b validation repairs end to end: the real pipeline (extraction, routing, validation, review, reports) through
the JSON API with an in-process fake provider, no network. validation:0, 3, 4, 5, 7 and 8. Synthetic data only.
"""
from datetime import date, datetime, timezone

from django.test import TestCase, override_settings

from studio.models import ReferenceCodeFact, ReferenceSource
from tests.test_reports import section
from tests.test_repairs_pipeline import LIVE
from tests.test_repairs_status_r2_validation_api import MultiEvidenceApiCase

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-21\n'
OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: {cc}\n{body}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
VISIT, TIME = 'Established patient office visit.', 'Total time: 32 minutes.'


def xxx():
    return {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'}


@override_settings(**LIVE)
class RoundThreeValidationApiTests(MultiEvidenceApiCase, TestCase):
    def setUp(self):
        super().setUp()
        common = dict(publisher='CMS', url='https://www.cms.gov/synthetic',
                      retrieved_at=datetime(2026, 10, 23, tzinfo=timezone.utc), effective_start=date(2026, 10, 1),
                      effective_end=date(2026, 12, 31), license_note='synthetic', scope_note='synthetic')
        pfs = ReferenceSource.objects.create(key='cms-pfs-rvu26d', kind='cms-pfs', title='RVU26D synthetic',
                                             release='RVU26D', sha256='a' * 64, row_count=3, **common)
        for code in ('99213', '99214', '91010'):
            ReferenceCodeFact.objects.create(source=pfs, code=code, facts=xxx())

    def approve_ready(self, encounter_id):
        for item in self.detail(encounter_id)['assessment']['proposals']:
            if item['bucket'] == 'selected':
                action = 'approve' if 'approve' in item['allowed_actions'] else 'reject'
                self.assertEqual(self.decide(encounter_id, item['code'], action).status_code, 201)

    def test_validation0_a_findings_sentence_never_makes_a_gi_other_code_approvable(self):
        note = (HEAD + 'Procedure: Colonoscopy\nIndication: Average-risk screening.\nFindings: The colonoscope was '
                'advanced to the cecum. The colon was normal. Grade 2 internal hemorrhoids were seen on '
                'retroflexion.\nImpression: Internal hemorrhoids; banding may be considered at a later date.\n'
                'Plan: Repeat colonoscopy in 10 years.\n')
        encounter_id = self.run_note(note, ('45378', 'The colonoscope was advanced to the cecum.'),
                                     ('46221', 'Grade 2 internal hemorrhoids were seen on retroflexion.'))
        band = self.proposal(encounter_id, '46221')
        self.assertEqual((band['status'], band['allowed_actions']), ('needs_clarification', ['reject']))
        self.assertEqual(self.decide(encounter_id, '46221', 'approve').status_code, 409)
        self.approve_ready(encounter_id)
        approved = section(self.report_text(encounter_id, 'reviewed'), 'APPROVED SELECTIONS')
        self.assertIn('45378', approved)
        self.assertNotIn('46221', approved)

    def test_validation3_an_e_m_citing_its_hpi_is_approvable(self):
        note = OFFICE.format(cc='Heartburn.', body='History of present illness: Intermittent heartburn for 8 weeks '
                                                   'despite omeprazole.\nAssessment and plan: Increase omeprazole.')
        encounter_id = self.run_note(note, ('99213', 'Intermittent heartburn for 8 weeks despite omeprazole.'))
        visit = self.proposal(encounter_id, '99213')
        self.assertEqual((visit['bucket'], visit['allowed_actions']), ('selected', ['approve', 'reject']))
        self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 201)
        self.assertIn('99213', section(self.report_text(encounter_id, 'reviewed'), 'APPROVED SELECTIONS'))

    def test_validation4_an_e_m_citing_an_egd_hedge_is_approvable(self):
        note = OFFICE.format(cc='Heartburn.', body='Plan: Increase omeprazole to 40 mg twice daily. Possible EGD if '
                                                   'symptoms persist.')
        encounter_id = self.run_note(note, ('99214', TIME, 'Possible EGD if symptoms persist.'))
        self.assertEqual(self.proposal(encounter_id, '99214')['allowed_actions'], ['approve', 'reject'])
        self.assertEqual(self.decide(encounter_id, '99214', 'approve').status_code, 201)
        self.assertEqual(self.report(encounter_id, 'reviewed').status_code, 201)

    def test_validation5_a_banding_beside_a_selected_anoscopy_is_never_certified_as_proposed(self):
        note = OFFICE.format(cc='rectal bleeding.', body='Anoscopy was performed today.\nRubber band ligation x3 '
                                                         'completed today.')
        encounter_id = self.run_note(note, ('99213', TIME), ('46600', 'Anoscopy was performed today.'))
        missed = ('[WARN] services.unproposed — Performed services without a proposal: Possible missed service: '
                  'Other GI service (“Rubber band ligation x3”)')
        self.assertIn(missed, self.report_text(encounter_id))
        self.approve_ready(encounter_id)
        reviewed = self.report_text(encounter_id, 'reviewed')
        self.assertIn(missed, reviewed)
        self.assertNotIn('[PASS] services.unproposed', reviewed)

    def test_validation7_a_manometry_coded_xxx_does_not_hold_the_visit(self):
        note = OFFICE.format(cc='dysphagia.', body='Esophageal manometry was performed today.')
        encounter_id = self.run_note(note, ('99213', VISIT), ('91010', 'Esophageal manometry was performed today.'))
        visit = self.proposal(encounter_id, '99213')
        self.assertEqual(visit['allowed_actions'], ['approve', 'reject'])
        self.assertNotIn('em.same_day_procedure', [c['id'] for c in visit['checks']])
        self.approve_ready(encounter_id)
        approved = section(self.report_text(encounter_id, 'reviewed'), 'APPROVED SELECTIONS')
        self.assertIn('99213', approved)
        self.assertIn('91010', approved)

    def test_validation8_an_assessment_discussion_does_not_hold_the_visit(self):
        note = OFFICE.format(cc='Heartburn.', body='Assessment: Gastroesophageal reflux disease, not controlled. '
                                                   'Discussed EGD; the patient will think about it.')
        encounter_id = self.run_note(note, ('99214', VISIT))
        self.assertEqual(self.proposal(encounter_id, '99214')['allowed_actions'], ['approve', 'reject'])
        self.assertEqual(self.decide(encounter_id, '99214', 'approve').status_code, 201)
        self.assertEqual(self.report(encounter_id, 'reviewed').status_code, 201)
