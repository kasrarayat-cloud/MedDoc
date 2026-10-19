"""Source-bound time support, independent of provider citations or code selection."""
from datetime import date
from django.test import SimpleTestCase
from core import coding_engine, corti_semantics as time


class SoapCodingTimeTests(SimpleTestCase):
    note = (
        'Patient: Synthetic Ada Tern\nService date: 21 October 2027\n'
        'Treating clinician: Dr. Mira Cole\nS\n'
        'Ada is a 47-year-old woman attending an established-patient, in-person visit '
        'in a U.S. gastroenterology office.\nP\n'
        "Office E/M selection is based on the treating physician's total time on the service date. "
        'Dr. Cole personally spent 33 minutes on 21 October 2027: five minutes reviewing '
        'the available records, 22 minutes obtaining the history, performing the examination '
        'and counseling the patient, and six minutes placing the laboratory order and '
        'documenting the visit. All three activities were performed by the physician on '
        'the encounter date. The 33 minutes exclude four minutes of staff intake work and '
        'seven minutes of physician record review performed on the preceding day. '
        'Time for any separately reported service is also excluded from the total.')

    def support(self, note=None):
        note = self.note if note is None else note
        return (time.office_time_facts(note, contract=coding_engine.SOAP_SOURCE_CONTRACT),
            time.office_service_eligibility(note, date(2027, 10, 21),
                contract=coding_engine.SOAP_SOURCE_CONTRACT))

    def test_complete_account_has_eight_exact_source_facts_without_clinician_confirmation(self):
        facts, errors = self.support()
        self.assertEqual(errors, [])
        self.assertEqual(facts['status'], 'documented', facts)
        self.assertEqual({f['key'] for f in facts['facts']}, set(time.REQUIRED_TIME_FACTS))
        self.assertFalse(facts['clinician_confirmed'])
        self.assertEqual(next(f['value'] for f in facts['facts'] if f['key']=='time_minutes'), 33)
        for row in facts['facts']:
            self.assertEqual(self.note[row['start']:row['end']], row['quote'])
        self.assertEqual(time.citation_adequacy([], facts['facts'])['status'], 'insufficient_for_time_review')

    def test_old_contract_keeps_its_missing_facts_and_profile(self):
        old = time.office_time_facts(self.note, contract=coding_engine.PROSPECTIVE_SOURCE_CONTRACT)
        self.assertEqual(old['status'], 'requires_clarification')
        self.assertEqual([r['key'] for r in old['facts']], ['patient_status'])
        self.assertNotEqual(coding_engine.source_profile(coding_engine.SOAP_SOURCE_CONTRACT),
            coding_engine.source_profile(coding_engine.PROSPECTIVE_SOURCE_CONTRACT))

    def test_complete_work_list_and_sum_are_required(self):
        for changed in (
            self.note.replace('22 minutes obtaining', '21 minutes obtaining'),
            self.note.replace('placing the laboratory order', 'performing the laboratory test'),
            self.note.replace('placing the laboratory order', 'placing the laboratory order for her mother'),
            self.note.replace('placing the laboratory order', 'performing an unknown activity'),
            self.note.replace('Dr. Cole personally spent', 'The staff personally spent'),
            self.note.replace('Dr. Cole personally spent', 'Dr. Other personally spent'),
            self.note.replace('on 21 October 2027:', 'on 20 October 2027:'),
        ):
            with self.subTest(changed=changed):
                facts, errors = self.support(changed)
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_service_date_aliases_are_checked_against_each_other_and_saved_date(self):
        for changed in (
            self.note.replace('Service date: 21 October 2027', 'Service date: 20 October 2027'),
            self.note.replace('Service date: 21 October 2027', 'Service date: 31 February 2027'),
            'Date of service: 20 October 2027\n'+self.note,
        ):
            with self.subTest(changed=changed):
                facts, errors = self.support(changed)
                self.assertTrue(errors)
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_attendance_setting_requires_the_complete_owned_affirmative_frame(self):
        for before, after in (
            ('Ada is a', 'Beatrice is a'),
            ('Ada is a', 'Perhaps Ada is a'),
            ('gastroenterology office', 'possible office'),
            ('gastroenterology office', 'post office'),
            ('gastroenterology office', 'astrology office'),
            ('woman attending', 'woman possibly attending'),
            ('gastroenterology office.', 'gastroenterology office, but the visit was cancelled.'),
        ):
            with self.subTest(after=after):
                facts, errors = self.support(self.note.replace(before, after))
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_scope_retractions_and_uncertain_or_disconnected_exclusions_remain_held(self):
        for changed in (
            self.note.replace('\nP\n', '\nMother\nP\n'),
            self.note.replace('\nP\n', '\nPrevious visit\nP\n'),
            self.note+' The above physician time is incorrect.',
            self.note.replace('service is also excluded', 'service is not excluded'),
            self.note.replace('service is also excluded from the total.',
                'service is also excluded from the total unless it was performed.'),
            self.note.replace('Time for any separately', 'The patient reports feeling comfortable. Time for any separately'),
            self.note.replace('The 33 minutes exclude', 'The 32 minutes exclude'),
        ):
            with self.subTest(changed=changed):
                facts, errors = self.support(changed)
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_singular_and_plural_exclusions_do_not_change_the_total(self):
        for phrase in ('separately reported service', 'separately reported services'):
            facts, errors = self.support(self.note.replace('separately reported service', phrase))
            self.assertEqual(errors, [])
            self.assertEqual(facts['status'], 'documented')
            self.assertEqual(next(r['value'] for r in facts['facts'] if r['key']=='time_minutes'), 33)
        start = self.note.index('The 33 minutes exclude')
        for service in ('service', 'services'):
            facts, errors = self.support(self.note[:start]+'The total excludes staff time and separately reported '+service+'.')
            self.assertEqual(facts['status'], 'documented', facts)
            self.assertEqual(errors, [])

    def test_spelled_and_decimal_exclusion_totals_are_bound_without_rounding(self):
        for total, action in (('thirty-two', 'exclude'), ('33.5', 'exclude'),
                ('33.000000000000000000001', 'exclude'), ('32', 'does not count')):
            with self.subTest(total=total, action=action):
                facts, errors = self.support(self.note.replace('The 33 minutes exclude', 'The '+total+' minutes '+action))
                self.assertTrue(facts['status'] != 'documented' or errors)
        for total in ('thirty-three', '33.0'):
            facts, errors = self.support(self.note.replace('The 33 minutes exclude', 'The '+total+' minutes exclude'))
            self.assertEqual(facts['status'], 'documented', facts)
            self.assertEqual(errors, [])
