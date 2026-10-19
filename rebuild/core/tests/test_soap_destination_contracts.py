"""Bounded destination contracts, independent of patient-specific answers.

These tests exercise prospective contract recognition and routing only. The
caller still proves ownership, literal coverage, timing and complete answers.
"""
from copy import deepcopy
import unittest

from core.soap_destination_contracts import (
    complete_denial_destination,
    complete_exam_destination,
    restricted_exam_destination,
    historical_medicine_with_current_nonuse,
    restricted_support_destination,
    support_obligation_requested,
)


def definition(meaning, *, subject='patient', temporality='any', polarity='any'):
    return {
        'meaning': meaning, 'value_type': 'text', 'answer_mode': 'narrative',
        'scope': {'subject': subject, 'temporality': temporality, 'polarity': polarity},
    }


DENIAL = ('All documented symptom negatives (symptoms documented as absent), '
          'each with its exact documented scope.')
EXAM = 'The complete documented examination, including both positive and negative findings.'
HISTORICAL = ('A stopped historical medicine as documented: dose, route, frequency, indication, '
              'dates, response, stopping reason and explicit statement of non-use now. '
              'Restricted to medicine used before the target encounter; documented absence is allowed.')
INVESTIGATION = ('Investigation ordered, its evaluation purpose, intended collection timing, '
                 'and the actual collection, performance and result status today.')
INCLUDED_TIME = ('The documented E/M selection basis, total physician time, service date '
                 'and each included activity with its minutes.')
EXCLUSIONS = ('Excluded staff time and prior-day physician time with minutes, any separately '
              'reported service exclusion, and procedure status today.')


class CompleteNarrativeContractsTests(unittest.TestCase):
    def test_observed_complete_denials(self):
        self.assertTrue(complete_denial_destination(definition(DENIAL, polarity='negative')))

    def test_complete_denial_synonyms(self):
        for meaning in (
            'List all reported denied symptoms, retaining the original scope of every symptom.',
            'The full pertinent negatives as documented.',
            'Record all documented negative symptoms, each with the exact scope.',
        ):
            with self.subTest(meaning=meaning):
                self.assertTrue(complete_denial_destination(definition(meaning)))

    def test_denial_topic_mentions_cannot_broaden_narrow_destinations(self):
        for meaning in (
            'Only symptom negatives concerning shortness of breath.',
            DENIAL + ' Exclude palpitations.',
            'All documented symptom negatives except the respiratory findings.',
            'All documented symptom negatives, each with its exact documented scope or a summary.',
            'All documented symptom negatives. Do not include the full list.',
        ):
            with self.subTest(meaning=meaning):
                self.assertFalse(complete_denial_destination(definition(meaning)))

    def test_observed_complete_exam(self):
        self.assertTrue(complete_exam_destination(definition(EXAM)))

    def test_complete_exam_synonyms(self):
        for meaning in (
            'Record the full physical exam findings, including normal and abnormal findings.',
            'All current examination observations, retaining negative and positive observations.',
            'The complete objective findings from physical examination.',
        ):
            with self.subTest(meaning=meaning):
                self.assertTrue(complete_exam_destination(definition(meaning)))

    def test_exam_topic_mentions_cannot_broaden_narrow_destinations(self):
        for meaning in (
            'Complete respiratory examination findings.',
            'The complete documented examination, including positive findings only.',
            EXAM + ' Omit normal cardiovascular observations.',
            'The complete documented examination except the neurological findings.',
            'The complete documented examination, including abnormal findings.',
        ):
            with self.subTest(meaning=meaning):
                self.assertFalse(complete_exam_destination(definition(meaning)))

    def test_restrictive_exam_wording_vetoes_broad_fallback(self):
        for suffix in ('Omit normal bowel sounds.', 'Do not include normal bowel sounds.',
                       'Positive observations alone.', 'Negative findings are optional.',
                       'Ignore the cardiovascular findings.', 'Retain abnormal findings only.'):
            with self.subTest(suffix=suffix):
                self.assertTrue(restricted_exam_destination(definition('Physical exam findings. '+suffix)))
        self.assertFalse(restricted_exam_destination(definition(EXAM)))
        self.assertFalse(restricted_exam_destination(definition('Physical exam findings. Leave blank if not documented.')))

    def test_narrative_capability_respects_typed_scope(self):
        for helper, meaning in ((complete_denial_destination, DENIAL), (complete_exam_destination, EXAM)):
            for patch in (
                {'answer_mode': 'atomic'}, {'value_type': 'number'},
                {'scope': {'subject': 'other', 'temporality': 'any', 'polarity': 'any'}},
                {'scope': {'subject': 'patient', 'temporality': 'past', 'polarity': 'any'}},
                {'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'positive'}},
            ):
                with self.subTest(helper=helper.__name__, patch=patch):
                    d = definition(meaning)
                    d.update(patch)
                    self.assertFalse(helper(d))

    def test_labels_never_override_the_approved_meaning(self):
        d = definition('Only the respiratory findings.')
        d['label'] = EXAM
        self.assertFalse(complete_exam_destination(d))
        d = definition('Only the gastrointestinal symptoms.')
        d['label'] = DENIAL
        self.assertFalse(complete_denial_destination(d))

    def test_observed_historical_medicine_requests_current_nonuse(self):
        self.assertTrue(historical_medicine_with_current_nonuse(definition(HISTORICAL, temporality='past')))

    def test_historical_medicine_synonyms(self):
        for meaning in (
            'The discontinued medication trial: name, dosage, route, trial dates, benefit and current non-use.',
            'A prior treatment course: indication, response, reason for stopping, documented nonuse now.',
            'A past therapy: dose and current cessation. Documented absence is acceptable.',
        ):
            with self.subTest(meaning=meaning):
                self.assertTrue(historical_medicine_with_current_nonuse(definition(meaning, temporality='past')))

    def test_past_medicine_does_not_implicitly_request_current_status(self):
        for meaning in (
            'A stopped historical medicine: dose, route, dates and response.',
            'A stopped medicine: dose, response and current non-use only if relevant.',
            'A stopped medicine: dose, response and non-use now. Exclude current medicine status.',
            'A stopped medicine: dose, response and non-use now. Never report a medication absence.',
            'A stopped medicine: dose, response and the current medications.',
        ):
            with self.subTest(meaning=meaning):
                self.assertFalse(historical_medicine_with_current_nonuse(definition(meaning, temporality='past')))

    def test_current_medicine_or_wrong_owner_does_not_use_past_exception(self):
        for subject, temporality, polarity in (
            ('patient', 'current', 'any'), ('patient', 'any', 'any'),
            ('other', 'past', 'any'), ('patient', 'past', 'positive'),
        ):
            self.assertFalse(historical_medicine_with_current_nonuse(
                definition(HISTORICAL, subject=subject, temporality=temporality, polarity=polarity)))


class SupportObligationContractsTests(unittest.TestCase):
    def requested(self, meaning, kind, source):
        return support_obligation_requested(definition(meaning), kind, source)

    def test_investigation_contract_retains_complete_test_status(self):
        meaning = INVESTIGATION + ' Retain documented not-yet-done or not-resulted status.'
        for source in (
            'No urine specimen was obtained today',
            'The thyroid function test was not performed at this encounter',
            'No laboratory result is available today',
        ):
            with self.subTest(source=source):
                self.assertIs(self.requested(meaning, 'nonperformance', source), True)
        self.assertIs(self.requested(meaning, 'nonperformance', 'No procedure was performed today'), False)

    def test_complete_investigation_contract_requires_the_source_order(self):
        for source in (
            'I ordered a urine culture to evaluate for urinary infection, with collection planned tomorrow',
            'A thyroid function test was ordered to assess thyroid disease, with collection planned next week',
        ):
            with self.subTest(source=source):
                self.assertIs(self.requested(INVESTIGATION, 'investigation_order', source), True)
                self.assertIs(self.requested(EXCLUSIONS, 'investigation_order', source), False)
                self.assertIs(self.requested(INCLUDED_TIME, 'investigation_order', source), False)

    def test_partial_or_restricted_investigation_contract_cannot_route_order_as_known(self):
        source = 'I ordered a urine culture to evaluate for urinary infection, with collection planned tomorrow'
        for meaning in (
            'Investigation ordered, actual collection, performance and result status today.',
            'Investigation ordered, its evaluation purpose, actual collection, performance and result status today.',
            'Investigation ordered, intended collection timing, actual collection, performance and result status today.',
            INVESTIGATION+' Exclude the order.',
            'Test names only.',
        ):
            with self.subTest(meaning=meaning):
                self.assertIsNone(self.requested(meaning, 'investigation_order', source))

    def test_procedure_contract_does_not_require_unrelated_test_status(self):
        self.assertIs(self.requested(EXCLUSIONS, 'nonperformance', 'No surgery was performed today'), True)
        self.assertIs(self.requested(EXCLUSIONS, 'nonperformance', 'No specimen was collected today'), False)
        self.assertIs(self.requested(EXCLUSIONS, 'nonperformance', 'The blood test was not performed today'), False)

    def test_synonymous_complete_support_lists(self):
        investigation = ('Tests planned, evaluation purpose, intended performance timing, '
                         'collection status, actual performance status and results status at this encounter.')
        self.assertIs(self.requested(investigation, 'linked_nonperformance', 'The tests have no results today'), True)
        time = ('Evaluation and management selection basis, total clinician time, date of service, '
                'included activities with their minutes.')
        self.assertIs(self.requested(time, 'physician_time_basis', 'Selection used physician time'), True)
        self.assertIs(self.requested(time, 'physician_time_exclusions', 'Staff time is excluded'), False)
        self.assertIs(self.requested('Procedural performance status at this encounter.',
                                    'nonperformance', 'No operation was performed today'), True)

    def test_included_time_field_does_not_inherit_exclusions(self):
        for kind in ('physician_time_basis', 'physician_time_activities', 'physician_time_qualification'):
            self.assertIs(self.requested(INCLUDED_TIME, kind, 'All physician time occurred on the service date'), True)
        self.assertIs(self.requested(INCLUDED_TIME, 'physician_time_exclusions',
                                    'Excluded six minutes of staff work and eight minutes from yesterday'), False)

    def test_exclusions_field_does_not_inherit_included_time(self):
        self.assertIs(self.requested(EXCLUSIONS, 'physician_time_exclusions',
                                    'Excluded six minutes of staff work and eight minutes from yesterday'), True)
        for kind in ('physician_time_basis', 'physician_time_activities', 'physician_time_qualification'):
            self.assertIs(self.requested(EXCLUSIONS, kind, 'The physician spent 27 minutes today'), False)
        self.assertIs(self.requested('Time exclusions and procedure status today.',
                                    'physician_time_exclusions', 'Staff time is excluded'), True)

    def test_combined_contract_keeps_all_declared_obligations(self):
        combined = ', '.join(x.rstrip('.') for x in (INVESTIGATION, INCLUDED_TIME, EXCLUSIONS)) + '.'
        for kind, source in (
            ('investigation_order', 'I ordered a urine culture to evaluate for urinary infection, with collection planned tomorrow'),
            ('nonperformance', 'No laboratory sample was obtained today'),
            ('linked_nonperformance', 'The test was not performed today'),
            ('nonperformance', 'No procedure occurred during this encounter'),
            ('physician_time_basis', 'Time determined the selection basis'),
            ('physician_time_activities', 'The clinician spent 27 minutes today'),
            ('physician_time_exclusions', 'This total excludes staff time'),
            ('physician_time_qualification', 'All physician time occurred today'),
        ):
            with self.subTest(kind=kind, source=source):
                self.assertIs(self.requested(combined, kind, source), True)

    def test_partial_contract_does_not_remove_legacy_obligations(self):
        for meaning in (
            'Investigation ordered, evaluation purpose and intended collection timing.',
            'Investigation ordered, actual collection and performance status.',
            'Investigation ordered and result status today.',
            'E/M selection basis and total physician time.',
            'The total physician time and included activities with minutes.',
            'Excluded staff time and procedure status today.',
            'Separately reported service exclusion.',
            'Excluded staff time and prior-day physician time with minutes.',
        ):
            with self.subTest(meaning=meaning):
                self.assertIsNone(self.requested(meaning, 'nonperformance', 'No procedure occurred today'))
                self.assertIsNone(self.requested(meaning, 'physician_time_exclusions', 'Staff time is excluded'))

    def test_explicit_restrictions_or_unknown_tails_cannot_remove_checks(self):
        for meaning in (
            INVESTIGATION.rstrip('.') + ' only.',
            INVESTIGATION + ' Exclude procedures.',
            INVESTIGATION + ' Do not include the results.',
            INCLUDED_TIME.rstrip('.') + ', excluding staff time.',
            INCLUDED_TIME.rstrip('.') + ', optional exclusions.',
            EXCLUSIONS + ' Include anything useful.',
            'Only procedure status today.',
            'Procedure status today, except the operation.',
            'Excluded activities and procedure status today.',
        ):
            with self.subTest(meaning=meaning):
                self.assertIsNone(self.requested(meaning, 'nonperformance', 'No test was performed today'))
                self.assertIsNone(self.requested(meaning, 'physician_time_exclusions', 'Staff time is excluded'))

    def test_explicit_support_prohibition_veto_is_distinct_from_requested_exclusions(self):
        for suffix in ('Exclude results.', 'Do not include result status.',
                       'Retain collection only.', 'Omit the actual performance status.'):
            with self.subTest(suffix=suffix):
                self.assertTrue(restricted_support_destination(definition(INVESTIGATION+' '+suffix)))
        self.assertTrue(restricted_support_destination(definition(INCLUDED_TIME+' Omit the service date.')))
        self.assertTrue(restricted_support_destination(definition('Procedure status today only.')))
        for meaning in (EXCLUSIONS, INCLUDED_TIME, INVESTIGATION,
                        INVESTIGATION+' Retain documented not-yet-done or not-resulted status.',
                        'Only the selected medication history.'):
            self.assertFalse(restricted_support_destination(definition(meaning)))

    def test_unknown_source_domain_keeps_existing_completeness(self):
        self.assertIsNone(self.requested(INVESTIGATION, 'nonperformance', 'It was not done today'))
        self.assertIsNone(self.requested(EXCLUSIONS, 'linked_nonperformance', 'It is still pending'))

    def test_source_unit_with_both_domains_remains_whole_in_each_requested_domain(self):
        source = 'No test or procedure was performed today'
        self.assertIs(self.requested(INVESTIGATION, 'nonperformance', source), True)
        self.assertIs(self.requested(EXCLUSIONS, 'nonperformance', source), True)

    def test_every_coordinated_object_must_be_classified_before_excluding_a_domain(self):
        for source in (
            'No blood test or endoscopy was performed today',
            'No endoscopy or blood test was performed today',
            'No blood test, biopsy or procedure was performed today',
            'No blood test was performed today and no endoscopy was performed today',
            'No procedure result is available today',
            'No test was performed today but the endoscopy was also not done',
        ):
            with self.subTest(source=source):
                self.assertIsNone(self.requested('Procedure status today.', 'nonperformance', source))
                self.assertIsNone(self.requested(INVESTIGATION, 'nonperformance', source))

    def test_unrecognized_obligation_is_untouched(self):
        self.assertIsNone(self.requested(INCLUDED_TIME, 'patient_identity_ambiguity', 'Another patient'))
        self.assertIsNone(self.requested(INVESTIGATION, 'conditional_plan', 'If symptoms worsen, call'))

    def test_wrong_mode_scope_and_label_cannot_narrow_obligations(self):
        good = definition(INVESTIGATION)
        for patch in (
            {'answer_mode': 'atomic'}, {'value_type': 'person_name'},
            {'scope': {'subject': 'other', 'temporality': 'any', 'polarity': 'any'}},
            {'scope': {'subject': 'patient', 'temporality': 'past', 'polarity': 'any'}},
            {'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'negative'}},
            {'meaning': 'Unrecognized meaning', 'label': INVESTIGATION},
        ):
            d = deepcopy(good)
            d.update(patch)
            self.assertIsNone(support_obligation_requested(d, 'nonperformance', 'No procedure occurred today'))


if __name__ == '__main__':
    unittest.main()
