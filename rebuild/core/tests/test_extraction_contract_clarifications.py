"""Constructed producer-contract boundaries; no retained clinical fixtures."""
from copy import deepcopy
import unittest

from django.core.exceptions import ValidationError

from core import source_assertion_graph as graph
from core import source_assertion_generation as generation
from core.clinical_validation_diagnostics import SourceAssertionValidationError
from core.tests.test_source_assertion_graph import (
    IDENTITY, assertion, base_case, checker, extraction, fact, ref,
)


class ExtractionContractClarificationTests(unittest.TestCase):
    def test_complete_compound_qualified_and_ranged_values_remain_literal(self):
        for notes, quote, kind in (
            ('A 37-year-old adult attended.', '37-year-old', 'identity'),
            ('Weight was approximately 68 kg.', 'approximately 68 kg', 'measurement'),
            ('Symptoms lasted 3 to 5 days.', '3 to 5 days', 'finding'),
            ('Walking distance was over 200 metres.', 'over 200 metres', 'finding'),
        ):
            with self.subTest(quote=quote):
                raw = fact(notes, 'f1', quote, kind=kind)
                before = deepcopy(raw)
                result = graph.validate_literal_facts(notes, graph.units_for(notes), [raw])['f1']
                self.assertEqual(result['value_evidence']['quote'], quote)
                self.assertIsNone(result['unit'])
                self.assertIsNone(result['unit_span'])
                self.assertEqual(raw, before)

    def test_contained_or_hyphenated_unit_metadata_still_refuses(self):
        notes = 'A 37-year-old adult attended.'
        for quote in ('37-year-old', '37'):
            with self.subTest(quote=quote):
                raw = fact(notes, 'f1', quote, kind='identity')
                raw.update(unit='year', unit_span=ref(notes, 'year'))
                with self.assertRaises(SourceAssertionValidationError) as caught:
                    graph.validate_literal_facts(notes, graph.units_for(notes), [raw])
                self.assertEqual(caught.exception.code, 'unit_not_attached')
                self.assertEqual(caught.exception.messages,
                                 ['Source assertion graph: unit_not_attached'])
                self.assertIsInstance(caught.exception, ValidationError)

    def test_separate_attached_units_keep_existing_literal_rules(self):
        for notes, value, unit in (
            ('Weight was 68 kg.', '68', 'kg'),
            ('Temperature was 36 degrees celsius.', '36', 'celsius'),
        ):
            with self.subTest(notes=notes):
                raw = fact(notes, 'f1', value, kind='measurement')
                raw.update(unit=unit, unit_span=ref(notes, unit))
                result = graph.validate_literal_facts(notes, graph.units_for(notes), [raw])['f1']
                self.assertEqual(result['unit'], unit)
                self.assertEqual(notes[result['unit_span']['start']:result['unit_span']['end']], unit)
        notes = 'Weight was 68; another reading was 79 kg.'
        raw = fact(notes, 'f1', '68', kind='measurement')
        raw.update(unit='kg', unit_span=ref(notes, 'kg'))
        with self.assertRaisesRegex(ValidationError, 'unit_not_attached'):
            graph.validate_literal_facts(notes, graph.units_for(notes), [raw])

    def test_approximate_range_signed_and_fractional_fragments_still_refuse(self):
        for notes, quote in (
            ('Weight was approximately 68 kg.', '68'),
            ('Weight was 68 to 79 kg.', '68'),
            ('Weight was 68 to 79 kg.', '79'),
            ('Change was -3 units.', '3'),
            ('Change was 1.5 units.', '5'),
        ):
            with self.subTest(notes=notes, quote=quote):
                raw = fact(notes, 'f1', quote, kind='measurement')
                with self.assertRaises(ValidationError):
                    graph.validate_literal_facts(notes, graph.units_for(notes), [raw])

    def test_every_fact_still_requires_exactly_one_owner(self):
        notes, _, _, raw, _ = base_case()
        duplicate = deepcopy(raw)
        second = deepcopy(duplicate['assertions'][1])
        second['id'] = 'another-owner'
        duplicate['assertions'].append(second)
        duplicate = extraction(notes, duplicate['facts'], duplicate['assertions'])
        with self.assertRaisesRegex(ValidationError, 'fact_multiple_assertions'):
            graph.compile_graph(notes, duplicate)
        unowned = deepcopy(raw)
        unowned['assertions'][1]['fact_ids'] = []
        with self.assertRaisesRegex(ValidationError, 'unassigned_fact_assertion'):
            graph.compile_graph(notes, unowned)

    def test_owner_subject_time_and_polarity_disagreements_still_refuse(self):
        notes, _, _, raw, _ = base_case()
        for key, value in (('subject', 'clinician'), ('timing', 'past'), ('polarity', 'negated')):
            bad = deepcopy(raw)
            if key == 'polarity':
                bad['facts'][1][key] = value
            else:
                bad['facts'][1][key]['kind'] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    ValidationError, 'fact_assertion_disagreement'):
                graph.compile_graph(notes, bad)

    def test_separate_past_and_current_negative_claims_preserve_both(self):
        notes = 'Earlier nausea resolved; no nausea now.'
        old = fact(notes, 'past-fact', 'Earlier nausea resolved', timing='past')
        current = fact(notes, 'current-fact', 'no nausea now', polarity='negated')
        assertions = [
            assertion(notes, 'past', ['past-fact'], 'Earlier nausea resolved',
                      temporality='past', consumer_ref=ref(notes, 'nausea')),
            assertion(notes, 'current', ['current-fact'], 'no nausea now',
                      polarity='negated', qualifier_refs=[ref(notes, 'no')],
                      consumer_ref=ref(notes, 'nausea', occurrence=2)),
        ]
        relations = [{'id': 'separate-claims', 'kind': 'independent_of',
                      'source_assertion_id': 'past', 'target_assertion_ids': ['current'],
                      'evidence_refs': [ref(notes, notes)]}]
        raw = extraction(notes, [old, current], assertions, relations)
        compiled = graph.compile_graph(notes, raw)
        self.assertEqual(compiled['fact_assertions'],
                         {'past-fact': 'past', 'current-fact': 'current'})
        self.assertEqual(compiled['facts']['past-fact']['timing']['kind'], 'past')
        self.assertEqual(compiled['facts']['current-fact']['timing']['kind'], 'current')
        self.assertEqual(compiled['facts']['current-fact']['polarity'], 'negated')
        self.assertEqual(compiled['relationships']['separate-claims']['kind'], 'independent_of')

    def test_invalid_extraction_cannot_reach_assigner_or_checker(self):
        notes, fields, definitions, raw, _ = base_case('A 37-year-old adult attended.')
        age = fact(notes, 'age', '37-year-old', kind='identity')
        age.update(unit='year', unit_span=ref(notes, 'year'))
        raw['facts'].append(age)
        raw['assertions'].append(assertion(notes, 'age-owner', ['age'], '37-year-old',
                                           kind='context', consumer_role='none'))
        raw = extraction(notes, raw['facts'], raw['assertions'])
        calls = []
        def send(role, attempt, payload, schema, instructions):
            calls.append((role, attempt))
            self.assertEqual(role, 'extractor')
            self.assertIn('exactly equal', instructions)
            return deepcopy(raw)
        with self.assertRaisesRegex(ValidationError, 'unit_not_attached'):
            generation.run(notes, fields, definitions, send, identity=IDENTITY)
        self.assertEqual(calls, [('extractor', 1)])

    def test_clarified_schema_reaches_the_same_three_stage_pipeline(self):
        notes, fields, definitions, raw, assigned = base_case()
        calls = []
        def send(role, attempt, payload, schema, instructions):
            calls.append((role, attempt))
            if role == 'extractor':
                props = schema['properties']['facts']['items']['properties']
                self.assertIn('already contains the unit', props['unit']['description'])
                self.assertIn('single owner assertion', props['polarity']['description'])
                self.assertIn('never a fact ID', instructions)
                return deepcopy(raw)
            if role == 'assigner':
                return deepcopy(assigned)
            return checker(payload['graph'], fields, definitions, assigned)
        result = generation.run(notes, fields, definitions, send, identity=IDENTITY)
        self.assertEqual(calls, [('extractor', 1), ('assigner', 1), ('checker', 1)])
        self.assertEqual(result['answers']['field0']['text'], 'She reports heartburn.')
        self.assertEqual(generation.restore(notes, result['interpretation']), result['answers'])
