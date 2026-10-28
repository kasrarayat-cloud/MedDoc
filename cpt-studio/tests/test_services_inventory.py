"""The documented-service inventory (studio/gi/services.py): what the document says was done, read clause by clause.

Every text here is a fresh synthetic paraphrase. The expected readings are written in the tests, outside the reader,
and none is a sentence the reader recognises by its exact wording.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services

DAY = date(2026, 10, 14)


def inventory(text, day=DAY):
    facts = gi_context.extract_context(text)
    return services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def service(inv, family):
    found = inv.for_family(family)
    assert found, f'no {family} service in {[s.family for s in inv.services]}'
    return found[0]


def acts(svc, kind, status=None):
    return [a for a in svc.acts if a.kind == kind and (status is None or a.status == status)]


COLON_TWO_LESIONS = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Lower Endoscopy Report
Date of service: 2026-10-14
Proceduralist: Dr. Ana Fictional, MD
Technique
The colonoscope was passed to the cecum, which was identified by the appendiceal orifice. Withdrawal was careful.
Findings
1. A 6 mm flat polyp in the transverse colon was resected with a hot snare and sent in jar 1.
2. A distinct 15 mm sessile lesion in the sigmoid colon was sampled with cold biopsy forceps (jar 2). This lesion was
not resected and was not treated with a snare or ablation.
3. No further polyps were removed.
Impression
Transverse colon polyp removed; sigmoid lesion biopsied; referral for endoscopic resection will be arranged.
"""


class SeparateLesionsTests(SimpleTestCase):
    def test_two_lesions_two_acts_and_the_untreated_one_is_not_removed(self):
        inv = inventory(COLON_TWO_LESIONS)
        colon = service(inv, 'gi.colonoscopy')
        self.assertEqual(colon.status, 'performed')
        self.assertEqual(colon.completion, 'complete')
        self.assertEqual(len(colon.lesions), 2, [l.anatomy for l in colon.lesions])
        snares = acts(colon, 'snare', 'performed')
        biopsies = acts(colon, 'biopsy', 'performed')
        self.assertTrue(snares and biopsies)
        self.assertNotEqual(snares[0].lesion, biopsies[0].lesion)
        by_id = {l.id: l for l in colon.lesions}
        self.assertEqual(by_id[biopsies[0].lesion].anatomy, 'sigmoid colon')
        self.assertEqual(by_id[biopsies[0].lesion].disposition, 'sampled')
        self.assertEqual(by_id[snares[0].lesion].disposition, 'removed')
        # the untreated lesion's denied snare is about that lesion only: no conflict with the other lesion's snare
        self.assertEqual(inv.conflicts, ())

    def test_a_denial_of_further_acts_denies_nothing_documented(self):
        colon = service(inventory(COLON_TWO_LESIONS), 'gi.colonoscopy')
        self.assertFalse(any('No further' in a.evidence[0].text for a in colon.acts))

    def test_a_planned_resection_is_planned(self):
        colon = service(inventory(COLON_TWO_LESIONS), 'gi.colonoscopy')
        self.assertFalse(acts(colon, 'emr', 'performed'))


NEGATED_LIST = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Upper Endoscopy Report
Date of service: 2026-10-14
The gastroscope was introduced and advanced through the esophagus and stomach into the second part of the duodenum.
Two cold forceps biopsies were taken from the gastric body for histology.
Neither endoscopic ultrasound, needle aspiration, ERCP, banding, stent placement nor dilation was carried out at this
session.
"""


class NegationScopeTests(SimpleTestCase):
    def test_a_long_negated_list_negates_every_member(self):
        inv = inventory(NEGATED_LIST)
        self.assertEqual(service(inv, 'gi.egd').status, 'performed')
        for family in ('gi.eus', 'gi.ercp'):
            found = inv.for_family(family)
            self.assertTrue(all(s.status not in ('performed', 'incomplete') for s in found), (family, found))
        egd = service(inv, 'gi.egd')
        self.assertTrue(acts(egd, 'biopsy', 'performed'))
        self.assertFalse(acts(egd, 'dilation', 'performed'))
        self.assertFalse(acts(egd, 'band_ligation', 'performed'))

    def test_a_negated_negative_is_complete(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
                'Date of service: 2026-10-14\nThe colonoscope reached the cecum. The study was completed and was not '
                'terminated early or interrupted. A 5 mm polyp in the rectum was removed with a cold snare.\n')
        colon = service(inventory(text), 'gi.colonoscopy')
        self.assertEqual(colon.status, 'performed')
        self.assertEqual(colon.completion, 'complete')

    def test_a_discontinued_examination_is_incomplete(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
                'Date of service: 2026-10-14\nThe colonoscope was advanced to the hepatic flexure. The procedure was '
                'discontinued there because of solid stool; the cecum was not reached.\n')
        colon = service(inventory(text), 'gi.colonoscopy')
        self.assertEqual(colon.status, 'incomplete')
        self.assertEqual(colon.completion, 'incomplete')

    def test_an_unresected_lesion_does_not_make_the_examination_incomplete(self):
        colon = service(inventory(COLON_TWO_LESIONS), 'gi.colonoscopy')
        self.assertEqual(colon.completion, 'complete')

    def test_a_dilated_duct_is_a_finding_not_a_dilation(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nERCP Report\n'
                'Date of service: 2026-10-14\nThe common bile duct was dilated to 12 mm with two stones. A biliary '
                'sphincterotomy was performed and the stones were cleared with a balloon.\n')
        ercp = service(inventory(text), 'gi.ercp')
        self.assertFalse(acts(ercp, 'dilation'))
        self.assertTrue(acts(ercp, 'sphincterotomy', 'performed'))
        self.assertTrue(acts(ercp, 'stone_extraction', 'performed'))


CHECKLIST_CONFLICT = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy Procedure Note
Date of service: 2026-10-14
The cecum was intubated. A 7 mm polyp in the descending colon was removed by cold snare. The polyp site was not
marked; no India ink or other tattoo was injected.
Nursing record
Intra-procedure checklist charted by Lee Fictional RN: Tattoo [X] Performed [ ] Not performed.
"""


class ConflictTests(SimpleTestCase):
    def test_a_nursing_checkbox_against_the_physician_is_kept_as_a_conflict(self):
        inv = inventory(CHECKLIST_CONFLICT)
        self.assertEqual(len(inv.conflicts), 1, inv.conflicts)
        conflict = inv.conflicts[0]
        self.assertEqual(conflict.subject, 'tattoo')
        roles = {(side.role, side.status) for side in conflict.sides}
        self.assertIn(('nursing', 'performed'), roles)
        self.assertIn(('physician', 'negated'), roles)

    def test_different_sites_are_not_a_conflict(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper Endoscopy Report\n'
                'Date of service: 2026-10-14\nThe scope reached the second portion of the duodenum. Biopsies were '
                'taken from the antrum. The duodenum looked normal and was not biopsied.\n')
        self.assertEqual(inventory(text).conflicts, ())


class TimeTests(SimpleTestCase):
    def test_history_and_plan_do_not_make_today_s_service_another_time(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
                'Date of service: 2026-10-14\nPrior colonoscopy in 2021 removed an adenoma. Today the colonoscope was '
                'advanced to the cecum and a 4 mm rectal polyp was taken with cold forceps. Pathology is pending. '
                'Repeat colonoscopy is planned in 2029.\n')
        colon = service(inventory(text), 'gi.colonoscopy')
        self.assertEqual(colon.status, 'performed')
        self.assertTrue(acts(colon, 'biopsy', 'performed'))
        self.assertFalse(acts(colon, 'snare', 'performed'))  # the 2021 removal is history


class EvaluationAndManagementTests(SimpleTestCase):
    def test_a_sparse_note_is_a_visit_with_its_missing_facts(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nGastroenterology clinic\n'
                'Seen for heartburn that wakes the patient at night. Abdomen benign.\nImpression: reflux.\n'
                'Plan: trial of a proton pump inhibitor.\n')
        em = service(inventory(text, day=None), 'gi.office_em')
        self.assertEqual(em.status, 'performed')
        self.assertEqual(set(em.uncertainty), {'setting', 'patient_status', 'em_basis'})

    def test_routine_preprocedure_work_is_not_a_separate_visit(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
                'Date of service: 2026-10-14\nThe routine preprocedure history update and consent were completed; no '
                'separate evaluation and management service was documented today. The colonoscope reached the '
                'cecum and a 5 mm cecal polyp was removed with a cold snare.\n')
        inv = inventory(text)
        visits = inv.for_family('gi.office_em')
        self.assertTrue(all(v.status not in ('performed', 'incomplete') for v in visits), visits)


class ContextConflictTests(SimpleTestCase):
    def test_a_member_date_unlike_the_document_s_is_a_conflict(self):
        text = 'Visit date: 2026-10-14\nOffice visit.'
        merged = gi_context.merge_user_values(gi_context.extract_context(text), {'service_date': '2001-02-03'})
        self.assertEqual(merged['service_date'].origin, 'conflict')
        self.assertIsNone(merged['service_date'].value)
        self.assertIn('2001-02-03', merged['service_date'].note)
        self.assertIn('2026-10-14', merged['service_date'].note)

    def test_a_member_date_supplies_a_missing_one_and_may_agree(self):
        text = 'Office visit with no date.'
        merged = gi_context.merge_user_values(gi_context.extract_context(text), {'service_date': '2026-10-14'})
        self.assertEqual((merged['service_date'].origin, merged['service_date'].value), ('user', '2026-10-14'))
        text = 'Date of service: 2026-10-14\nOffice visit.'
        merged = gi_context.merge_user_values(gi_context.extract_context(text), {'service_date': '2026-10-14'})
        self.assertEqual(merged['service_date'].value, '2026-10-14')

    def test_a_day_month_year_date_is_read(self):
        facts = gi_context.extract_context('Patient X | Service date 9 November 2026 | Clinician Y')
        # P2DN's fix round, rule N7: read (the member's answer agrees with it) and asked, as the installed revision sent
        # no day-first date; this pin had it documented
        self.assertEqual((facts['service_date'].origin, facts['service_date'].value), ('missing', None))
        self.assertEqual(gi_context._date_readings(facts['service_date'].evidence), {'2026-11-09'})


class ValidationTests(SimpleTestCase):
    def test_the_inventory_validates_and_a_broken_passage_is_reported(self):
        inv = inventory(COLON_TWO_LESIONS)
        self.assertEqual(services.validate(inv, COLON_TWO_LESIONS), ())
        self.assertTrue(services.validate(inv, COLON_TWO_LESIONS.replace('hot snare', 'HOT SNARE')))
