"""Pure syntax boundaries: recognizing an order never authorizes its use."""
from copy import deepcopy
from unittest import TestCase

from core.clinical_assertions_v4 import family_history_order_frame
from core.order_event_roles import order_event_frame


class OrderEventRoleTests(TestCase):
    passive = ('A veloran marker test is ordered for collection at a laboratory '
               'after this visit as part of the tremor evaluation')
    active = 'I ordered a zephran assay to evaluate for pallor, with collection planned tomorrow'
    family = 'I ordered a urine culture for family history of renal disease, with collection planned tomorrow'

    def assert_frame(self, source, placement, event, test, indication):
        frame = order_event_frame(source)
        self.assertIsNotNone(frame)
        self.assertEqual([source[a:b] for a, b in frame['values']],
                         [source.strip().removesuffix('.').strip()])
        for key, expected in [('order_placement', placement), ('future_event', event)]:
            a, b = frame['roles'][key]
            self.assertEqual(source[a:b], expected)
        for key, expected in [('test', test), ('indication', indication)]:
            a, b = frame[key]
            self.assertEqual(source[a:b], expected)
        self.assertEqual(frame['required_subject'], 'patient')
        self.assertEqual(frame['required_polarity'], 'affirmed')
        self.assertEqual(frame['required_section'], 'plan')
        self.assertEqual(frame['allowed_timings'], ('current', 'future'))
        self.assertNotIn('required_timing', frame)
        self.assertNotIn('performed', frame)
        return frame

    def test_passive_exact_whole_value_and_distinct_event_roles(self):
        frame = self.assert_frame('  '+self.passive+'.\r\n', 'A veloran marker test is ordered',
            'collection at a laboratory after this visit', 'A veloran marker test', 'tremor')
        self.assertEqual(frame['kind'], 'investigation_order')

    def test_active_exact_whole_value_and_future_collection(self):
        self.assert_frame(self.active, 'I ordered a zephran assay', 'collection planned tomorrow',
                          'a zephran assay', 'pallor')

    def test_active_optional_for_and_have_preserve_literal_spans(self):
        text = self.active.replace('I ordered', 'I have ordered').replace('evaluate for', 'evaluate')
        self.assert_frame(text, 'I have ordered a zephran assay', 'collection planned tomorrow',
                          'a zephran assay', 'pallor')

    def test_collection_and_performance_future_forms(self):
        for text in (self.active.replace('tomorrow', 'after this visit'),
                     self.active.replace('collection', 'performance'),
                     self.passive.replace('collection', 'performance')):
            with self.subTest(text=text):
                frame = order_event_frame(text)
                self.assertIsNotNone(frame)
                start, end = frame['roles']['future_event']
                self.assertIn(text[start:end].split()[0], ('collection', 'performance'))

    def test_no_test_or_disease_vocabulary_is_required(self):
        for test, indication in [('quendar assay', 'zular syndrome'),
                                 ('a serum alpha-marker test', 'episodic hand tremor'),
                                 ('an unfamiliar specimen examination', 'novel marker elevation')]:
            with self.subTest(test=test, indication=indication):
                text = f'I ordered {test} to evaluate {indication}, with collection planned tomorrow'
                self.assert_frame(text, 'I ordered '+test, 'collection planned tomorrow', test, indication)

    def test_family_history_delegates_old_grammar_without_mutation(self):
        for text in (self.family, self.family.replace('I ordered a urine culture', 'A serum assay is ordered'),
                     self.family.replace('I ordered', 'I have ordered').replace('tomorrow', 'after this visit')):
            with self.subTest(text=text):
                old = family_history_order_frame(text)
                frozen = deepcopy(old)
                frame = order_event_frame(text)
                self.assertEqual(old, frozen)
                self.assertEqual(family_history_order_frame(text), frozen)
                self.assertEqual(old['required_timing'], 'current')
                self.assertEqual({k: v for k, v in frame.items() if k not in ('roles', 'allowed_timings')},
                                 {k: v for k, v in old.items() if k != 'required_timing'})
                self.assertEqual(frame['roles']['future_event'], old['collection'])
                start, end = frame['roles']['order_placement']
                self.assertEqual(text[start:end], text.split(' for family history')[0])

    def test_future_ordering_and_historical_placement_are_not_two_event_permission(self):
        for text in (self.passive.replace('is ordered', 'will be ordered'),
                     self.passive.replace('is ordered', 'was ordered'),
                     self.passive.replace('is ordered', 'may be ordered'),
                     self.passive.replace('is ordered', 'is not ordered'),
                     self.active.replace('I ordered', 'I will order'),
                     self.active.replace('I ordered', 'I previously ordered'),
                     self.active.replace('I ordered', 'I might order'),
                     self.active.replace('I ordered', 'I did not order')):
            with self.subTest(text=text):
                self.assertIsNone(order_event_frame(text))

    def test_qualifying_prefixes_quotes_and_multisentence_input_refuse(self):
        for prefix in ('Yesterday, ', 'Reportedly, ', 'Apparently, ', 'If needed, ',
                       'The patient reports that ', 'Her mother said ', '"', '“', 'P\n'):
            for base in (self.active, self.passive, self.family):
                with self.subTest(prefix=prefix, base=base):
                    self.assertIsNone(order_event_frame(prefix+base))
        self.assertIsNone(order_event_frame(self.active+'. This order is withdrawn.'))

    def test_unknown_retraction_attribution_and_condition_tails_refuse(self):
        for suffix in (' unless symptoms resolve', ' but this is withdrawn', ' according to her mother',
                       ' for another patient', ' with an unfamiliar qualification', ' if needed',
                       ' and the result is normal', ' and this was performed today', '"', '”'):
            for base in (self.active, self.passive, self.family):
                with self.subTest(suffix=suffix, base=base):
                    self.assertIsNone(order_event_frame(base+suffix))

    def test_nominal_slots_cannot_hide_qualification_owner_or_predicate(self):
        for phrase in ('possible pallor', 'pallor for her mother', 'her pallor', 'pallor or fever',
                       'pallor with unknown cause', 'pallor is unconfirmed', 'pallor after yesterday',
                       'reported pallor', 'pallor reportedly resolved', 'pallor pending confirmation'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(order_event_frame(self.active.replace('pallor', phrase)))
        for phrase in ('her test', 'test for another patient', 'previously ordered test',
                       'unverified test', 'test according to the mother', 'test and imaging', 'test 123'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(order_event_frame(self.active.replace('a zephran assay', phrase)))

    def test_required_future_event_and_complete_value_cannot_be_clipped(self):
        for text in ('a zephran assay', 'collection planned tomorrow',
                     self.active.split(',')[0], self.passive.split(' as part')[0],
                     self.active.replace('tomorrow', 'today'),
                     self.active.replace('planned tomorrow', 'completed today'),
                     self.passive.replace('after this visit', 'during this visit'),
                     self.passive.replace('after this visit', 'at an unknown time')):
            with self.subTest(text=text):
                self.assertIsNone(order_event_frame(text))

    def test_nominal_length_and_punctuation_bounds(self):
        for phrase in ('', 'one two three four five six seven eight nine', 'pallor; fever',
                       'pallor: resolved', 'pallor/fever', 'pallor\nand fever'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(order_event_frame(self.active.replace('pallor', phrase)))
        self.assertIsNotNone(order_event_frame(self.active.replace('pallor', 'one two three four five six seven eight')))

    def test_invalid_input_types_and_empty_values_refuse(self):
        for value in (None, True, 7, [], {}, '', '   ', '.', '..'):
            with self.subTest(value=value):
                self.assertIsNone(order_event_frame(value))

    def test_internal_whitespace_and_case_keep_offsets(self):
        text = ' \tI  ORDERED a Zephran assay to evaluate for Pallor, with collection planned tomorrow.  '
        self.assert_frame(text, 'I  ORDERED a Zephran assay', 'collection planned tomorrow',
                          'a Zephran assay', 'Pallor')

    def test_frame_has_no_owner_destination_or_truth_claim(self):
        frame = order_event_frame(self.active)
        self.assertEqual(set(frame), {'kind', 'values', 'test', 'indication', 'roles',
            'required_subject', 'required_polarity', 'required_section', 'allowed_timings'})
        self.assertEqual(len(frame['values']), 1)

    def test_passive_subject_boundary_cannot_absorb_source_governor_prefix(self):
        for prefix in ('Assume ', 'Pretend ', 'Last week ', 'Suppose ', 'Imagine ',
                       'For illustration ', 'The clinician assumes ', 'If true ',
                       'Historically ', 'Next month '):
            for base in (self.passive, self.family.replace('I ordered a urine culture',
                                                          'A urine culture is ordered')):
                with self.subTest(prefix=prefix, base=base):
                    self.assertIsNone(order_event_frame(prefix+base))
        # A bare passive nominal has no explicit boundary; it remains outside
        # this new permission even though a similarly named active object is safe.
        self.assertIsNone(order_event_frame(self.passive.removeprefix('A ')))
        self.assertIsNotNone(order_event_frame(self.active.replace('a zephran assay', 'quendar assay')))

    def test_article_led_governors_cannot_hide_inside_test_or_indication(self):
        for qualifier in ('assumed', 'pretended', 'supposed', 'imagined', 'fictitious',
                          'fictional', 'counterfactual', 'simulated', 'last week',
                          'two weeks ago', 'former', 'old', 'past', 'future', 'cancelled'):
            variants = (
                self.passive.replace('A veloran marker test', 'A '+qualifier+' veloran marker test'),
                self.active.replace('a zephran assay', 'a '+qualifier+' zephran assay'),
                self.active.replace('pallor', qualifier+' pallor'),
                self.family.replace('a urine culture', 'a '+qualifier+' urine culture'),
                self.family.replace('renal disease', qualifier+' renal disease'),
            )
            for text in variants:
                with self.subTest(qualifier=qualifier, text=text):
                    self.assertIsNone(order_event_frame(text))

    def test_new_family_permission_does_not_change_old_reader(self):
        for text in (
                self.family.replace('a urine culture', 'a last week urine culture'),
                self.family.replace('renal disease', 'imagined renal disease'),
                self.family.replace('I ordered a urine culture', 'Last week A urine culture is ordered'),
                self.family.replace('I ordered a urine culture', 'Urine culture is ordered')):
            with self.subTest(text=text):
                old = family_history_order_frame(text)
                self.assertIsNotNone(old)
                frozen = deepcopy(old)
                self.assertIsNone(order_event_frame(text))
                self.assertEqual(family_history_order_frame(text), frozen)
                self.assertEqual(old['required_timing'], 'current')

    def test_passive_articles_and_unfamiliar_nouns_keep_whole_roles(self):
        for article, noun in [('A', 'quendar assay'), ('An', 'unfamiliar marker test'),
                              ('The', 'zephran specimen examination')]:
            text = self.passive.replace('A veloran marker test', article+' '+noun)
            with self.subTest(text=text):
                self.assert_frame(text, article+' '+noun+' is ordered',
                    'collection at a laboratory after this visit', article+' '+noun, 'tremor')
