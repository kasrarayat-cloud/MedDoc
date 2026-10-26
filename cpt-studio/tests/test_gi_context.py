"""Encounter context (studio/gi/context.py). Pure functions, synthetic text only."""
import unittest
from pathlib import Path

from studio.gi.context import USER_NOTE, extract_context, merge_user_values
from studio.types import CONTEXT_FACTS, Fact

FIXTURES = Path(__file__).parent / 'fixtures' / 'gi'


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


class EvidenceIsExact:
    def assert_exact(self, text, facts):
        for fact in facts.values():
            for span in fact.evidence:
                self.assertEqual(text[span.start:span.end], span.text, fact.name)


class FixtureContextTests(EvidenceIsExact, unittest.TestCase):
    def facts(self, name):
        text = fixture(name)
        facts = extract_context(text)
        self.assertEqual(set(facts), set(CONTEXT_FACTS))
        self.assert_exact(text, facts)
        return facts

    def test_established_office_visit(self):
        facts = self.facts('01-office-established-time-mdm.txt')
        self.assertEqual(facts['service_date'], Fact('service_date', '2026-10-21', 'document', facts['service_date'].evidence))
        self.assertEqual([e.text for e in facts['service_date'].evidence], ['Date of service: 2026-10-21'])
        self.assertEqual((facts['setting'].value, facts['setting'].origin), ('office', 'document'))
        self.assertIn('Place of service: 11', [e.text for e in facts['setting'].evidence])
        self.assertEqual((facts['patient_status'].value, facts['patient_status'].origin), ('established', 'document'))

    def test_dates_in_plan_and_signature_are_not_the_service_date(self):
        facts = self.facts('01-office-established-time-mdm.txt')
        # 2026-11-04 (scheduled endoscopy) and 2026-04-15 (last visit) are documented but not labelled.
        self.assertEqual(facts['service_date'].value, '2026-10-21')
        self.assertEqual(len(facts['service_date'].evidence), 1)

    def test_us_date_and_new_patient(self):
        facts = self.facts('02-office-new-patient.txt')
        self.assertEqual(facts['service_date'].value, '2026-10-22')
        self.assertEqual(facts['service_date'].evidence[0].text, 'Visit date: 10/22/2026')
        self.assertEqual(facts['patient_status'].value, 'new')

    def test_month_name_date_and_hospital_outpatient(self):
        facts = self.facts('04-egd-balloon-dilation.txt')
        self.assertEqual(facts['service_date'].value, '2026-10-19')
        self.assertEqual(facts['service_date'].evidence[0].text, 'Procedure date: October 19, 2026')
        self.assertEqual(facts['setting'].value, 'hospital_outpatient')

    def test_place_of_service_codes(self):
        self.assertEqual(self.facts('05-colonoscopy-screening-cold-snare.txt')['setting'].value, 'asc')
        six = self.facts('06-colonoscopy-diagnostic-ileum.txt')
        self.assertEqual(six['setting'].value, 'hospital_outpatient')
        self.assertIn('POS: 22', [e.text for e in six['setting'].evidence])
        self.assertEqual(six['service_date'].value, '2026-10-21')

    def test_procedure_reports_do_not_document_patient_status(self):
        facts = self.facts('03-egd-cold-forceps-biopsy.txt')
        self.assertEqual(facts['patient_status'], Fact('patient_status', None, 'missing', (),
                                                       facts['patient_status'].note))
        self.assertTrue(facts['patient_status'].note)

    def test_missing_everything(self):
        facts = self.facts('16-office-missing-context.txt')
        for name in ('service_date', 'setting', 'patient_status'):
            self.assertEqual((facts[name].value, facts[name].origin, facts[name].evidence), (None, 'missing', ()))
        self.assertEqual((facts['billing_context'].value, facts['billing_context'].origin),
                         ('not_documented', 'missing'))

    def test_every_fixture_has_exact_evidence(self):
        for path in sorted(FIXTURES.glob('*.txt')):
            text = path.read_text(encoding='utf-8')
            self.assert_exact(text, extract_context(text))


class ServiceDateTests(EvidenceIsExact, unittest.TestCase):
    def test_conflicting_dates_are_a_conflict_with_all_evidence(self):
        text = 'Date of service: 2026-10-21\nProcedure date: 10/22/2026\nFindings: normal.'
        fact = extract_context(text)['service_date']
        self.assertEqual((fact.value, fact.origin), (None, 'conflict'))
        self.assertEqual([e.text for e in fact.evidence], ['Date of service: 2026-10-21', 'Procedure date: 10/22/2026'])
        self.assertIn('2026-10-21', fact.note)
        self.assertIn('2026-10-22', fact.note)

    def test_the_same_date_in_two_formats_is_one_value(self):
        text = 'DOS: 10/21/2026\nEncounter date: October 21, 2026'
        fact = extract_context(text)['service_date']
        self.assertEqual((fact.value, fact.origin, len(fact.evidence)), ('2026-10-21', 'document', 2))

    def test_dates_in_plan_or_history_sections_are_ignored(self):
        text = ('Chief complaint: reflux.\nPlan\nColonoscopy scheduled.\nProcedure date: 2026-11-04\n'
                'Past surgical history\nDate of procedure: 2019-05-02 (colonoscopy)')
        fact = extract_context(text)['service_date']
        self.assertEqual((fact.value, fact.origin), (None, 'missing'))

    def test_qualified_dates_describe_other_encounters(self):
        for line in ('Previous procedure date: 2019-05-01', 'Next visit date: 2026-12-01',
                     'Procedure date: 2026-11-04 (scheduled)', 'Prior DOS: 2025-01-02'):
            self.assertEqual(extract_context(line)['service_date'].origin, 'missing', line)

    def test_invalid_calendar_date_is_not_a_service_date(self):
        fact = extract_context('Date of service: 2026-02-30')['service_date']
        self.assertEqual((fact.value, fact.origin), (None, 'missing'))
        self.assertEqual([e.text for e in fact.evidence], ['Date of service: 2026-02-30'])
        self.assertIn('not a valid calendar date', fact.note)

    def test_unlabelled_dates_are_not_read(self):
        fact = extract_context('Seen on 2026-10-21 for follow-up. Signed 2026-10-21 17:40.')['service_date']
        self.assertEqual(fact.origin, 'missing')

    def test_label_must_be_a_whole_word(self):
        self.assertEqual(extract_context('KUDOS: 10/21/2026')['service_date'].origin, 'missing')


class SettingTests(unittest.TestCase):
    def setting(self, text):
        return extract_context(text)['setting']

    def test_pos_codes(self):
        expected = {'11': 'office', '22': 'hospital_outpatient', '19': 'hospital_outpatient', '24': 'asc',
                    '21': 'inpatient', '23': 'emergency', '02': 'telehealth', '10': 'telehealth'}
        for code, value in expected.items():
            fact = self.setting(f'Place of service: {code}')
            self.assertEqual((fact.value, fact.origin), (value, 'document'), code)
            self.assertEqual(fact.evidence[0].text, f'Place of service: {code}')

    def test_unrecognised_pos_code_is_not_guessed(self):
        fact = self.setting('POS 12')
        self.assertEqual((fact.value, fact.origin), (None, 'missing'))
        self.assertEqual([e.text for e in fact.evidence], ['POS 12'])
        self.assertIn('12', fact.note)

    def test_conflicting_settings(self):
        fact = self.setting('Place of service: Office\nPOS: 22')
        self.assertEqual((fact.value, fact.origin), (None, 'conflict'))
        self.assertEqual(len(fact.evidence), 2)

    def test_explicit_phrases(self):
        self.assertEqual(self.setting('Telehealth visit by secure video.').value, 'telehealth')
        self.assertEqual(self.setting('Seen in the emergency department overnight.').value, 'emergency')
        self.assertEqual(self.setting('Inpatient consultation requested by the hospitalist.').value, 'inpatient')

    def test_future_or_historical_settings_are_not_this_encounter(self):
        for text in ('Plan\nColonoscopy at the ambulatory surgery center next week.',
                     'Colonoscopy will be done at the hospital outpatient endoscopy unit.',
                     'History of present illness\nShe was seen in the office in April.',
                     'Follow-up office visit in 3 months.',
                     'No office visit was needed.'):
            self.assertEqual(self.setting(text).origin, 'missing', text)

    def test_outpatient_alone_is_not_a_setting(self):
        self.assertEqual(self.setting('Outpatient procedure.').origin, 'missing')


class BillingAndPatientStatusTests(unittest.TestCase):
    def test_billing_only_from_explicit_statements(self):
        self.assertEqual(extract_context('Billing context: professional')['billing_context'].value, 'professional')
        self.assertEqual(extract_context('Claim type: facility (UB-04)')['billing_context'].value, 'facility')
        self.assertEqual(extract_context('Billed on a CMS-1500 claim.')['billing_context'].value, 'professional')
        for text in ('A professional interpreter was used.', 'The facility was clean.', ''):
            fact = extract_context(text)['billing_context']
            self.assertEqual((fact.value, fact.origin), ('not_documented', 'missing'), text)

    def test_billing_conflict(self):
        fact = extract_context('Billing: professional\nFacility claim submitted.')['billing_context']
        self.assertEqual((fact.value, fact.origin), (None, 'conflict'))

    def test_patient_status_negation_and_conflict(self):
        self.assertEqual(extract_context('This is not a new patient.')['patient_status'].origin, 'missing')
        fact = extract_context('New patient consultation.\nEstablished patient.')['patient_status']
        self.assertEqual((fact.value, fact.origin), (None, 'conflict'))
        self.assertEqual(extract_context('New to this practice.')['patient_status'].value, 'new')

    def test_patient_status_in_plan_is_ignored(self):
        text = 'Plan\nReturn as an established patient in 6 months.'
        self.assertEqual(extract_context(text)['patient_status'].origin, 'missing')


class MergeUserValuesTests(unittest.TestCase):
    def setUp(self):
        self.text = fixture('01-office-established-time-mdm.txt')
        self.facts = extract_context(self.text)

    def test_user_value_overrides_as_metadata(self):
        merged = merge_user_values(self.facts, {'service_date': '2026-10-22', 'billing_context': 'facility'})
        self.assertEqual(merged['service_date'], Fact('service_date', '2026-10-22', 'user', (), USER_NOTE))
        self.assertEqual(merged['billing_context'], Fact('billing_context', 'facility', 'user', (), USER_NOTE))
        self.assertEqual(merged['setting'], self.facts['setting'])
        self.assertEqual(self.facts['service_date'].value, '2026-10-21')  # input untouched

    def test_empty_values_keep_the_document(self):
        merged = merge_user_values(self.facts, {'service_date': '', 'setting': '   '})
        self.assertEqual(merged, self.facts)

    def test_user_value_resolves_a_conflict(self):
        facts = extract_context('Date of service: 2026-10-21\nDOS: 2026-10-22')
        merged = merge_user_values(facts, {'service_date': '2026-10-22'})
        self.assertEqual((merged['service_date'].value, merged['service_date'].origin), ('2026-10-22', 'user'))

    def test_invalid_input_is_refused(self):
        for values in ({'service_date': '2026-02-30'}, {'service_date': '10/21/2026'}, {'setting': 'home'},
                       {'billing_context': 'not_documented'}, {'patient_status': 'returning'},
                       {'specialty': 'gi'}, {'setting': None}, {'setting': 11}):
            with self.assertRaises(ValueError, msg=values):
                merge_user_values(self.facts, values)

    def test_patient_status_and_setting_values(self):
        merged = merge_user_values(self.facts, {'patient_status': 'new', 'setting': 'telehealth'})
        self.assertEqual((merged['patient_status'].value, merged['patient_status'].origin), ('new', 'user'))
        self.assertEqual(merged['setting'].value, 'telehealth')


if __name__ == '__main__':
    unittest.main()
