"""Complete time exclusions must not hide a second source proposition."""
from unittest import TestCase

from core.clinical_assertions_v4 import strict_exclusion


class StrictSoapTimeExclusionTests(TestCase):
    def test_current_and_retained_complete_exclusions(self):
        examples = (
            'The 33 minutes exclude four minutes of staff intake work and seven minutes of physician record review performed on the preceding day.',
            'Time for any separately reported service is also excluded from the total.',
            'The 23 minutes exclude four minutes of staff intake work and six minutes of physician record review performed on the preceding day',
            'The total also excludes any time for separately reported services.',
            'The 32 minutes exclude eight minutes of staff rooming and three minutes of physician preparation on the preceding day.',
            'The 37 minutes exclude nine minutes of nursing rooming work and five minutes of physician record review performed on the preceding day.',
            'The 47 minutes exclude eight minutes of staff intake work and six minutes of physician record review performed on the preceding day.',
            'They also exclude time for separately reported services.',
            'This total excludes clinical staff time and time for separately reported services.',
            'This total does not include clinical staff time and time for separately reported services.',
            'This total excludes nursing time and separately billed procedures.',
            'The total excludes time spent on an additional separately reported service.',
            'The total excludes staff time.',
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertTrue(strict_exclusion(text))

    def test_complete_active_passive_and_explicit_negative_frames(self):
        for text in (
            'This total does not count time for separately reported services.',
            'Time for separately reported services is excluded from this total.',
            'I excluded all time for separately reported services from the total.',
            'Clinical staff time and separately billed procedures were excluded from the total.',
            'These minutes exclude nursing time.',
            'Those minutes exclude staff time, physician preparation on the prior day, and time for separately reported services.',
        ):
            with self.subTest(text=text):
                self.assertTrue(strict_exclusion(text))

    def test_common_time_units_and_number_words_remain_complete_objects(self):
        for amount in ('4', 'four', 'twenty-five', 'thirty two', '0.5'):
            for unit in ('minute', 'minutes', 'min', 'mins', 'hour', 'hours', 'hr', 'hrs', 'seconds', 'secs'):
                text = f'The total excludes {amount} {unit} of staff intake work.'
                with self.subTest(text=text):
                    self.assertTrue(strict_exclusion(text))

    def test_explicit_total_reference_uses_only_the_account_binders_minutes(self):
        for text in ('The 99 hours exclude staff time.', 'The 34 mins exclude staff time.',
                     'Those hours exclude staff time.', 'These seconds exclude staff time.'):
            with self.subTest(text=text):
                self.assertFalse(strict_exclusion(text))

    def test_mismatched_or_unsupported_total_never_gets_a_bound_exclusion(self):
        from core import generation
        from core.clinical_source_context import source_context, time_blocks, SOAP_ASSERTION_PROFILE
        header = ('Patient: Synthetic Ada Tern\nDate of service: 21 October 2027\n'
                  'Treating clinician: Dr. Mira Cole\nP\n')
        basis = "Office E/M selection is based on the treating physician's total time on the service date"
        total = ('Dr. Cole personally spent 34 minutes on 21 October 2027: '
                 '30 minutes examining the patient and four minutes documenting')
        for reference, expected in (('34 minutes', True), ('33 minutes', False),
                                    ('99 hours', False), ('34 mins', False),
                                    ('45.5 minutes', False), ('thirty two minutes', False)):
            notes = header + basis + '. ' + total + '. The ' + reference + ' exclude staff time.'
            units, _ = generation.source_units(notes, [])
            context = source_context(notes, units, profile=SOAP_ASSERTION_PROFILE)
            bound = [row for row in time_blocks(notes, units, context)
                     if row['kind'] == 'exclusion' and row['binding_valid']]
            with self.subTest(reference=reference):
                self.assertEqual(bool(bound), expected)

    def test_newly_demonstrated_false_release_sentences_are_not_exemptions(self):
        for text in (
            'The total excludes staff time and cannot be used.',
            'The total excludes staff time; it is for another patient.',
            'The total excludes staff time, is not valid.',
        ):
            with self.subTest(text=text):
                self.assertFalse(strict_exclusion(text))

    def test_unparsed_continuation_rejects_all_exclusion_frames(self):
        frames = (
            'The total excludes staff time',
            'They also exclude time for separately reported services',
            'Time for separately reported services is excluded from this total',
            'I excluded all time for separately reported services from the total',
        )
        tails = (
            ' and cannot be used', ' but belongs to another patient',
            ' and represents yesterday', ', is not valid',
            '; it is for another patient', ' and requires confirmation',
            ' unless the chart is corrected', ' because the total is inaccurate',
            ' which was entered in error', ' pending verification',
            ' and staff time is uncertain', ' and nursing time belongs to another visit',
            '. The total has been withdrawn', '\nThe total is uncertain',
        )
        for frame in frames:
            for tail in tails:
                with self.subTest(frame=frame, tail=tail):
                    self.assertFalse(strict_exclusion(frame + tail + '.'))

    def test_qualification_cannot_hide_within_an_excluded_object(self):
        for text in (
            'The total excludes four minutes of staff time and six minutes that are invalid.',
            'The total excludes clinical staff time and physician record review performed for another patient.',
            'The total excludes staff time except five minutes.',
            'The total excludes some nine minutes of staff rooming.',
            'The total excludes neither clinical staff time nor separately reported services.',
            'The total excludes staff time and includes separately reported services.',
            'The total excludes staff time and unknown work.',
            'The total excludes meals.',
            'The total excludes travel.',
        ):
            with self.subTest(text=text):
                self.assertFalse(strict_exclusion(text))

    def test_no_prefix_attribution_incomplete_list_or_reversed_polarity(self):
        for text in (
            'If confirmed, the total excludes staff time.',
            'The patient reports that the total excludes staff time.',
            'Another patient: the total excludes staff time.',
            'The total does not exclude staff time.',
            'The total includes staff time.',
            'The total excludes staff time and.',
            'The total excludes staff time,',
            'The total excludes.',
            'The total excludes staff time..',
        ):
            with self.subTest(text=text):
                self.assertFalse(strict_exclusion(text))
