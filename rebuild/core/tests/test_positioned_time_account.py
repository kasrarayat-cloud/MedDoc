"""Prospective source-owned time accounts; no provider or database is used."""
from datetime import date
from unittest import TestCase

from core import corti_semantics as time


class PositionedTimeAccountTests(TestCase):
    note = (
        'Patient: Synthetic Ada Tern\nDate of service: 5 November 2026\n'
        'Treating physician: Dr. Maya Chen\nSubjective\n'
        'Ada is a 52-year-old woman attending an in-person gastroenterology office visit in the United States. '
        'She is an established patient. Episodes last 12 minutes. '
        "These episode lengths describe the symptom, not the time spent on today's visit.\n"
        'Plan\nFollow up in four weeks, or sooner if symptoms worsen. '
        'Office E/M selection is based on total physician time on the date of service. '
        'Dr. Chen spent 28 minutes on 5 November 2026: four minutes reviewing records, '
        '19 minutes evaluating and counseling Ada, and five minutes placing the order and documenting the visit. '
        'The physician performed all of that work on the service date. '
        'Seven minutes of staff intake are outside that total. '
        'Three minutes of physician record review done on 4 November 2026 are also excluded. '
        'There were no separately billed services, and no time for separately billed work is included in the 28 minutes.')

    def support(self, note=None, contract=None):
        note = self.note if note is None else note
        contract = time.SHARED_TIME_CONTRACT if contract is None else contract
        return (time.office_time_facts(note, contract=contract),
                time.office_service_eligibility(note, date(2026, 11, 5), contract=contract))

    def assert_documented(self, note):
        facts, errors = self.support(note)
        self.assertEqual(errors, [], errors)
        self.assertEqual(facts['status'], 'documented', facts)
        self.assertEqual({row['key'] for row in facts['facts']}, set(time.REQUIRED_TIME_FACTS))
        self.assertFalse(facts['clinician_confirmed'])
        for row in facts['facts']:
            self.assertEqual(note[row['start']:row['end']], row['quote'])
        return facts

    def assert_held(self, note):
        facts, errors = self.support(note)
        self.assertTrue(facts['status'] != 'documented' or errors, (facts, errors))

    def test_whole_account_records_allocations_and_distinct_excluded_components(self):
        for note in (self.note, self.note.replace('\n', '\r\n')):
            with self.subTest(crlf='\r\n' in note):
                facts = self.assert_documented(note)
                account, = facts['time_accounts']
                self.assertEqual(account['minutes'], 28)
                self.assertEqual(account['date'], '2026-11-05')
                self.assertEqual([item['minutes'] for item in account['allocations']], [4, 19, 5])
                self.assertEqual([item['minutes'] for item in account['excluded_components']], [7, 3, None])
                self.assertEqual(account['excluded_components'][1]['date'], '2026-11-04')
                self.assertTrue(all(item['polarity'] == 'excluded' for item in account['excluded_components']))
                for item in account['excluded_components']:
                    evidence = item['source_evidence']
                    self.assertEqual(note[evidence['start']:evidence['end']], evidence['quote'])

    def test_source_bound_names_counts_and_allowed_activity_combinations_generalize(self):
        for before, after in (
            ('Ada Tern', 'Iris Vale'), ('Maya Chen', 'Nora Shah'),
            ('four minutes reviewing records', '4 minutes reviewing records'),
            ('evaluating and counseling Ada', 'examining and counseling Ada'),
            ('placing the order', 'entering the imaging order'),
        ):
            note = self.note.replace(before, after)
            if before == 'Ada Tern':
                note = note.replace('Ada ', 'Iris ').replace('counseling Ada,', 'counseling Iris,')
            if before == 'Maya Chen':
                note = note.replace('Dr. Chen', 'Dr. Shah')
            with self.subTest(after=after):
                self.assert_documented(note)

    def test_wrong_allocations_actors_recipients_dates_and_unrecognized_work_hold(self):
        for before, after in (
            ('four minutes reviewing', 'five minutes reviewing'),
            ('19 minutes evaluating', '18 minutes evaluating'),
            ('Dr. Chen spent', 'Dr. Vale spent'),
            ('Dr. Chen spent', 'The nurse spent'),
            ('counseling Ada', 'counseling Iris'),
            ('on 5 November 2026:', 'on 4 November 2026:'),
            ('on 5 November 2026:', 'on 6 November 2026:'),
            ('reviewing records', 'performing the ordered test'),
            ('placing the order', 'collecting the sample'),
            ('evaluating and counseling Ada', 'counseling Ada'),
            ('staff intake are outside', 'staff intake are included in'),
            ('4 November 2026 are also excluded', '5 November 2026 are also excluded'),
            ('4 November 2026 are also excluded', '6 November 2026 are also excluded'),
            ('4 November 2026 are also excluded', '32 November 2026 are also excluded'),
            ('included in the 28 minutes', 'included in the 29 minutes'),
        ):
            with self.subTest(after=after):
                self.assert_held(self.note.replace(before, after))

    def test_real_retractions_uncertain_work_and_service_denials_hold(self):
        for extra in (
            'The above physician time is incorrect.',
            'The recorded time was copied from a prior visit.',
            'These activities were performed by staff.',
            'These activities were performed yesterday.',
            'These activities may have been performed on the service date.',
            'The physician did not evaluate the patient.',
            'The visit was cancelled.',
            'The 28 minutes include seven minutes of staff intake.',
            'The total includes separately billed work.',
            'Dr. Chen additionally spent 12 minutes today.',
            'The total may be incorrect.',
            '28 minutes were actually staff intake.',
            '28 minutes were performed yesterday.',
            'The physician performed all of that work on 4 November 2026.',
        ):
            with self.subTest(extra=extra):
                self.assert_held(self.note+' '+extra)

    def test_complete_predicates_and_adjacent_account_are_required(self):
        for before, after in (
            ('outside that total.', 'outside that total unless needed.'),
            ('are also excluded.', 'are also excluded, but included if necessary.'),
            ('included in the 28 minutes.', 'included in the 28 minutes unless billed.'),
            ('performed all of that work', 'possibly performed all of that work'),
            ('The physician performed', 'Another physician performed'),
            ('Seven minutes of staff intake', '\n\nSeven minutes of staff intake'),
            ('Seven minutes of staff intake', 'Her sister: Seven minutes of staff intake'),
        ):
            with self.subTest(after=after):
                self.assert_held(self.note.replace(before, after))

    def test_current_actor_denials_and_incompatible_service_modalities_hold(self):
        for extra in (
            'The physician never saw Ada.', 'The physician was not present.',
            'The physician has never seen Ada.', 'The physician never attended the visit.',
            'Dr. Chen never met Ada.', 'Ada was not seen by Dr. Chen.',
            'The treating physician was absent.', 'The physician did not participate in this visit.',
            'There was no physician participation in this visit.',
            'The physician might not have been present.',
            'This was a telephone visit.', 'This was a video visit.',
            'The encounter was conducted by video.', 'This visit might have been by telephone.',
            'Dr. Chen evaluated Ada by telephone.', 'Ada was evaluated by video.',
        ):
            with self.subTest(extra=extra):
                self.assert_held(self.note+' '+extra)

    def test_actor_and_encounter_predicates_keep_foreign_and_prior_scope(self):
        for extra in ('The physician never saw Ada.', 'The physician was not present.',
                      'This was a telephone visit.', 'This was a video visit.'):
            for heading in ('Mother:', 'Previous encounter:', 'Prior encounter on 4 November 2026:'):
                with self.subTest(extra=extra, heading=heading):
                    self.assert_documented(self.note+'\n'+heading+'\n'+extra)
        for extra in (
            'Her mother never saw Ada.', 'Dr. Lena Moss never saw Ada.',
            'The physician did not see Iris Vale.', 'The patient was not seen by Dr. Lena Moss.',
            'The physician was present.', 'The physician was not absent.',
            'This was not a telephone visit.', 'This was not a video visit.',
            'The physician had never seen Ada before this visit.',
            'A telephone follow-up visit is planned in four weeks.',
        ):
            with self.subTest(extra=extra):
                self.assert_documented(self.note+' '+extra)

    def test_saved_service_date_and_policy_pair_must_match(self):
        self.assertTrue(time.office_service_eligibility(self.note, date(2026, 11, 6), contract=time.SHARED_TIME_CONTRACT))
        self.assertEqual(time.time_contract({'clinical_source_contract': 'source-bound-clinical-coding-v9',
            'cpt_time_source_contract': time.SHARED_TIME_CONTRACT}), time.SHARED_TIME_CONTRACT)
        with self.assertRaises(ValueError):
            time.time_contract({'clinical_source_contract': 'source-bound-clinical-coding-v9'})
        self.assert_held(self.note.replace('Date of service: 5 November 2026\n', ''))
        for contract in ('source-bound-clinical-coding-v7', 'source-bound-clinical-coding-v8'):
            with self.assertRaises(ValueError):
                time.time_contract({'clinical_source_contract': contract, 'cpt_time_source_contract': time.SHARED_TIME_CONTRACT})
        self.assertEqual(time.time_contract({'clinical_source_contract': 'source-bound-clinical-coding-v7',
            'cpt_time_source_contract': time.DOCUMENTED_TIME_CONTRACT}), time.DOCUMENTED_TIME_CONTRACT)

