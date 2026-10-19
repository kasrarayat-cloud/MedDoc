"""Offline literal-reader contracts; source ownership is tested by integration."""
import re
from unittest import TestCase

from core.soap_clinical_literals import (
    assertion_frame, named_medication_trial, trial_temporally_bound, stopping_temporally_bound,
)


def nominal(value):
    # The reader supplies its own scope guard; this intentionally permissive
    # callback detects whether an unsafe object can bypass that guard.
    return bool(re.fullmatch(r'[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,7}', value))


class SoapClinicalLiteralTests(TestCase):
    trial = ('She previously took famotidine 10 mg by mouth each evening for heartburn '
             'from 22 September through 10 October 2026')
    statements = (
        ('It gave no meaningful relief', 'medication_response', 'negated'),
        ('The cause of the heartburn is not established', 'diagnostic_limit', 'negated'),
        ('gastroesophageal reflux disease is a possibility but is not diagnosed', 'uncertainty', 'uncertain'),
        ('Constipation is documented without an established subtype or cause', 'diagnostic_limit', 'negated'),
        ('Slow-transit constipation, outlet dysfunction, drug-induced constipation and irritable bowel syndrome '
         'are not diagnosed today', 'diagnostic_limit', 'negated'),
    )

    def test_complete_spans_and_required_polarities(self):
        for source, kind, polarity in self.statements:
            with self.subTest(source=source):
                text = '\t ' + source + '.\r\n'
                result = assertion_frame(text, nominal)
                self.assertEqual(result['kind'], kind)
                self.assertEqual(result['required_polarity'], polarity)
                self.assertEqual(result['required_subject'], 'patient')
                self.assertEqual([text[a:b] for a, b in result['values']], [source])

    def test_response_demands_immediate_named_trial(self):
        frame = assertion_frame('It gave no meaningful relief', nominal)
        self.assertEqual(frame['antecedent'], 'named_medication_trial')
        self.assertEqual(frame['antecedent_distance'], 1)
        self.assertEqual(frame['required_timing'], 'past')
        self.assertNotIn('medicine', frame)  # A pronoun cannot invent a name.
        self.assertEqual(named_medication_trial(self.trial + '.', r'\d+(?:\.\d+)?'), 'famotidine')

    def test_general_names_and_wording_without_a_medical_dictionary(self):
        trial = ('The patient previously tried zelunor citrate 2.5 mg orally once daily '
                 'for episodic discomfort from 4 March 2027 through 9 March 2027')
        self.assertEqual(named_medication_trial(trial, r'\d+(?:\.\d+)?'), 'zelunor citrate')
        for text in ('The cause of tingling has not been determined',
                     'Aural discomfort is a possibility but not diagnosed',
                     'Numbness is documented without an established cause or subtype',
                     'Condition alpha and condition beta are not diagnosed today'):
            with self.subTest(text=text):
                self.assertIsNotNone(assertion_frame(text, nominal))

    def test_nominal_callback_rejection_is_authoritative(self):
        for source, kind, _ in self.statements:
            if kind != 'medication_response':
                with self.subTest(source=source):
                    self.assertIsNone(assertion_frame(source, lambda value: False))

    def test_documented_condition_is_not_declared_absent(self):
        result = assertion_frame(self.statements[3][0], nominal)
        self.assertTrue(result['documented_object'])
        self.assertEqual(result['object'], 'Constipation')
        self.assertEqual(result['limits'], ['subtype', 'cause'])

    def test_no_prefix_or_suffix_qualification_can_disappear(self):
        for source, _, _ in self.statements:
            for prefix in ('Mother: ', 'For another patient, ', 'Yesterday, ', 'If true, ', 'Reportedly, ',
                           'Inaccurately, ', 'Seemingly, ', 'Falsely, ', 'In error, ',
                           'According to the hospital record, ', 'I suspect, ', '"'):
                with self.subTest(source=source, prefix=prefix):
                    self.assertIsNone(assertion_frame(prefix + source, nominal))
            for suffix in (' but this is unverified', ' unless symptoms recur', ' for another patient',
                           ' according to her mother', ' and fever is diagnosed', ' but is not confirmed',
                           '. Another statement follows', '"'):
                with self.subTest(source=source, suffix=suffix):
                    self.assertIsNone(assertion_frame(source + suffix, nominal))

    def test_qualified_nouns_and_nested_negatives_remain_unrecognized(self):
        for obj in ('reported heartburn', 'possible heartburn', 'her heartburn', 'mother',
                    'heartburn that resolved', 'prior heartburn', 'never heartburn', 'heartburn or fever',
                    'confirmed constipation', 'heartburn is real'):
            for text in (f'The cause of {obj} is not established',
                         f'{obj} is a possibility but is not diagnosed',
                         f'{obj} and nausea are not diagnosed today'):
                with self.subTest(text=text):
                    self.assertIsNone(assertion_frame(text, nominal))

    def test_affirmative_and_clipped_values_are_not_frames(self):
        for source in ('It gave meaningful relief', 'meaningful relief', 'It did not give no relief',
                       'The cause of heartburn is established', 'gastroesophageal reflux disease',
                       'gastroesophageal reflux disease is a possibility', 'Constipation is documented',
                       'subtype or cause', 'Slow-transit constipation and outlet dysfunction',
                       'Slow-transit constipation and outlet dysfunction are diagnosed today'):
            with self.subTest(source=source):
                self.assertIsNone(assertion_frame(source, nominal))

    def test_trial_rejects_other_owners_events_and_invalid_dates(self):
        for text in (self.trial.replace('She previously', 'Her mother previously'),
                     self.trial.replace('famotidine', 'another medicine'),
                     self.trial.replace('heartburn', 'heartburn but fever is confirmed'),
                     self.trial.replace('22 September', '31 September'),
                     self.trial.replace('22 September through 10 October 2026', '22 September 2027 through 10 October 2026'),
                     self.trial + ' but the report is withdrawn', self.trial + '. It helped',
                     self.trial.replace('10 mg', '-10 mg')):
            with self.subTest(text=text):
                self.assertIsNone(named_medication_trial(text, r'-?\d+(?:\.\d+)?'))

    def test_list_keeps_every_object_and_rejects_ambiguous_or_empty_items(self):
        source = self.statements[4][0]
        result = assertion_frame(source, nominal)
        self.assertEqual(len(result['objects']), 4)
        self.assertEqual(result['values'], [(0, len(source))])
        for text in ('Condition alpha or condition beta are not diagnosed today',
                     'Condition alpha, , condition beta are not diagnosed today',
                     'Condition alpha and are not diagnosed today'):
            with self.subTest(text=text):
                self.assertIsNone(assertion_frame(text, nominal))

    def test_semicolon_group_preserves_exact_child_spans_and_polarities(self):
        first, second = self.statements[1][0], self.statements[2][0]
        source = '\t ' + first + ';  ' + second + '.\r\n'
        group = assertion_frame(source, nominal)
        self.assertEqual(group['kind'], 'diagnostic_qualifications')
        self.assertEqual([source[a:b] for a, b in group['values']], [first, second])
        self.assertEqual([child['required_polarity'] for child in group['assertions']], ['negated', 'uncertain'])
        self.assertEqual(group['values'], [child['values'][0] for child in group['assertions']])
        self.assertNotIn('required_polarity', group)
        self.assertNotIn((2, len(source.rstrip()) - 1), group['values'])
        for index, child in enumerate(group['assertions']):
            expected = ('negated', 'uncertain')[index]
            self.assertNotEqual(child['required_polarity'], 'affirmed')
            self.assertNotEqual(child['required_polarity'], ('uncertain' if expected == 'negated' else 'negated'))

    def test_semicolon_group_rejects_any_unknown_or_qualified_clause(self):
        first, second = self.statements[1][0], self.statements[2][0]
        valid = first + '; ' + second
        for unknown in ('An additional statement was made', 'This report is withdrawn',
                        'It gave no meaningful relief', second + ' unless symptoms worsen',
                        second + ' for another patient', 'Reportedly, ' + second):
            for source in (unknown + '; ' + valid, first + '; ' + unknown + '; ' + second,
                           valid + '; ' + unknown):
                with self.subTest(source=source):
                    self.assertIsNone(assertion_frame(source, nominal))

    def test_semicolon_group_limits_count_and_retains_repeated_positions(self):
        statement = self.statements[1][0]
        for count in (2, 3, 4):
            source = '; '.join([statement] * count)
            result = assertion_frame(source, nominal)
            self.assertEqual(len(result['assertions']), count)
            self.assertEqual(len(set(result['values'])), count)
            self.assertEqual([source[a:b] for a, b in result['values']], [statement] * count)
        for source in ('; '.join([statement] * 5), statement + ';', ';' + statement,
                       statement + ';;' + statement, statement + '; \t ;' + statement):
            with self.subTest(source=source):
                self.assertIsNone(assertion_frame(source, nominal))

    def test_trial_range_uses_explicit_year_and_service_date(self):
        self.assertTrue(trial_temporally_bound(self.trial, '2026-10-18'))
        self.assertFalse(trial_temporally_bound(self.trial, '2026-10-09'))
        cases = (
            ('22 September 2026 through 10 October', '2026-10-18', True),
            ('22 September through 10 October 2026', '2026-10-18', True),
            ('22 September 2026 through 10 October 2026', '2026-10-18', True),
            ('21 October 2027 through 21 October 2027', '2027-10-21', True),
            ('22 October 2027 through 29 October 2027', '2027-10-21', False),
            ('22 October through 9 October 2027', '2027-10-21', False),
            ('22 October 2027 through 9 October', '2027-10-21', False),
            ('22 September through 10 October', '2026-10-18', False),
            ('20 December through 5 January 2027', '2027-01-06', False),
            ('20 December 2026 through 5 January', '2027-01-06', False),
            ('20 December 2026 through 5 January 2027', '2027-01-06', True),
            ('20 December 2027 through 5 January 2026', '2027-01-06', False),
        )
        for date_range, encounter, expected in cases:
            text = 'She previously took example 10 mg from ' + date_range + '.'
            with self.subTest(date_range=date_range, encounter=encounter):
                self.assertIs(trial_temporally_bound(text, encounter), expected)

    def test_trial_range_rejects_invalid_calendar_dates_and_malformed_ranges(self):
        for date_range, expected in (
                ('29 February through 1 March 2024', True),
                ('29 February 2024 through 1 March', True),
                ('29 February through 1 March 2025', False),
                ('29 February 2025 through 1 March', False),
                ('31 September through 10 October 2026', False),
                ('0 October through 10 October 2026', False),
                ('10 October 2026 through 12 Octember 2026', False),
                ('10 October 2026 to 12 October 2026', False),
                ('10 October 2026 through', False),
                ('through 10 October 2026', False),
                ('10 October 2026 through 12 October 2026 but the date is uncertain', False),
                ('10 October 2026 through 12 October 2026 from 1 January 2026 through 2 January 2026', False)):
            with self.subTest(date_range=date_range):
                self.assertIs(trial_temporally_bound('She previously took example from ' + date_range,
                    '2026-10-18'), expected)

    def test_trial_without_range_keeps_relative_history_but_needs_valid_service_date(self):
        historical = 'She previously took example 10 mg, one tablet daily.'
        self.assertTrue(trial_temporally_bound(historical, '2026-10-18'))
        for encounter in (None, '', 'unknown', '2026-02-29', '2026-13-01', '2026-1-01',
                          '18 October 2026', '2026-10-18T12:00:00'):
            for text in (historical, self.trial):
                with self.subTest(encounter=encounter, text=text):
                    self.assertFalse(trial_temporally_bound(text, encounter))
        for text in (historical + ' through 10 October 2026', historical + ' from unknown', None):
            self.assertFalse(trial_temporally_bound(text, '2026-10-18'))

    def stopping(self, date):
        return 'She stopped it on ' + date + ' because it was not helping and is no longer taking famotidine'

    def test_stopping_is_between_trial_end_and_service_date_not_necessarily_equal(self):
        for date, expected in (('10 October', True), ('11 October', True), ('18 October', True),
                               ('20 October', False), ('09 October', False), ('01 October', False),
                               ('10 October 2026', True), ('10 October 2027', False),
                               ('31 September 2026', False)):
            with self.subTest(date=date):
                self.assertIs(stopping_temporally_bound(self.stopping(date), self.trial, '2026-10-18'), expected)

    def test_stopping_year_requires_one_date_supported_by_the_source_bounds(self):
        cases = (
            ('20 December 2026 through 29 December 2026', '5 January', '2027-01-06', True),
            ('20 December 2026 through 29 December 2026', '30 December', '2027-01-06', True),
            ('20 December through 29 December', '5 January', '2027-01-06', False),
            ('20 December through 5 January 2027', '5 January', '2027-01-06', False),
            ('1 January 2026 through 2 January 2026', '10 October', '2027-12-31', False),
            ('1 January 2026 through 2 January 2026', '10 October 2026', '2027-12-31', True),
            ('1 February 2024 through 28 February 2024', '29 February', '2024-03-01', True),
            ('1 February 2025 through 28 February 2025', '29 February', '2025-03-01', False),
        )
        for date_range, stop, encounter, expected in cases:
            trial = 'She previously took famotidine 10 mg from ' + date_range
            with self.subTest(date_range=date_range, stop=stop, encounter=encounter):
                self.assertIs(stopping_temporally_bound(self.stopping(stop), trial, encounter), expected)

    def test_stopping_requires_valid_trial_range_service_date_and_complete_continuation(self):
        stopped = self.stopping('10 October')
        for trial in ('She previously took famotidine 10 mg',
                      self.trial.replace('22 September', '31 September'),
                      self.trial.replace('10 October 2026', '20 October 2026'), None):
            with self.subTest(trial=trial):
                self.assertFalse(stopping_temporally_bound(stopped, trial, '2026-10-18'))
        for text in (stopped + ' unless symptoms recur', 'Her mother ' + stopped,
                     stopped.replace('on 10 October', 'on an unknown date'),
                     'is no longer taking famotidine', None):
            with self.subTest(text=text):
                self.assertFalse(stopping_temporally_bound(text, self.trial, '2026-10-18'))
        for date in (None, '', 'unknown', '2026-02-29'):
            self.assertFalse(stopping_temporally_bound(stopped, self.trial, date))
