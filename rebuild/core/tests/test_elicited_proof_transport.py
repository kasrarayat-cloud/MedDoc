"""Field-bound transport of the existing closed elicited-report proof; no sends."""
import copy
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import offered, relation_body
from .test_v3_literal_facts import FIXTURE, fields
from .test_v3_ordinary_notes import LIVE, field


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class ElicitedProofTransport(SimpleTestCase):
    def setUp(self):
        self.target = next(f for f in fields() if f['key'] == 'v3_25')
        self.quote = next(row['quote'] for row in FIXTURE['cases'] if row['key'] == self.target['key'])

    def bound(self, notes=None, catalogue=None):
        notes = self.quote if notes is None else notes
        catalogue = [self.target] if catalogue is None else catalogue
        asked, context, _ = g.v3_generation_fields(catalogue)
        units = g.source_units(notes, asked, context_labels=context)[0]
        picks = {f['key']: [self.quote] for f in asked}
        selections = r.FieldSelections.model_validate(relation_body(notes, catalogue, picks))
        records = r.records(notes, catalogue, context, units, selections, g.SONNET_5)
        reading = g.governance_for(notes, catalogue)[11]['preceding']
        evidence = [{k: u[k] for k in ('quote', 'start', 'end')} for u in units if u['quote'] == self.quote]
        return reading, evidence, records

    def assert_held(self, notes, target, quote):
        answer = offered(notes, [target], {target['key']: [quote]})[target['key']]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), answer)
        stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
        stored.update(status='supported', text=quote)
        page = g.as_currently_governed(g.governance_for(notes, [target]), notes, {**target, **stored})
        self.assertEqual((page['status'], page['text']), ('conflict', ''))
        self.assertEqual(g.governed_decisions(notes, [target], {target['key']: stored}), [target['label']])

    def test_successful_read_returns_selected_proof_without_mutating_parent(self):
        reading, evidence, records = self.bound()
        marker = {('an unrelated question', 777)}
        reading['_literal_elicited'] = marker
        result = r.read(reading, self.target['label'], evidence, records[self.target['key']],
                        text=self.quote, field_key=self.target['key'])
        self.assertTrue(result['valid'])
        self.assertEqual(result['elicited_ids'], {u['id'] for u in reading['units']})
        self.assertIs(reading['_literal_elicited'], marker)
        self.assertEqual(marker, {('an unrelated question', 777)})
        answer = offered(self.quote, [self.target], {self.target['key']: [self.quote]})[self.target['key']]
        self.assertEqual((answer['status'], answer['text']), ('supported', self.quote))
        self.assertEqual(answer['evidence'], evidence)
        page = g.as_currently_governed(g.governance_for(self.quote, [self.target]), self.quote,
                                      {**self.target, **answer})
        self.assertEqual((page['status'], page['text']), ('supported', self.quote))
        self.assertEqual(g.governed_decisions(self.quote, [self.target], {self.target['key']: answer}), [])

    def test_another_destination_cannot_borrow_cached_or_previously_read_proof(self):
        unrelated = field('unrelated', 'What physical illness affects relationships?')
        unrelated['context'] = 'Clinical report'
        catalogue = [self.target, unrelated]
        reading, evidence, records = self.bound(catalogue=catalogue)
        reading['_literal_elicited'] = {(g.question_key(unrelated['label']), 1)}
        good = r.read(reading, self.target['label'], evidence, records[self.target['key']],
                      field_key=self.target['key'])
        self.assertTrue(good['valid'])
        bad = r.read(reading, unrelated['label'], evidence, records[unrelated['key']],
                     field_key=unrelated['key'])
        self.assertEqual(bad['elicited_ids'], set())
        self.assertEqual(reading['_literal_elicited'], {(g.question_key(unrelated['label']), 1)})
        self.assert_held(self.quote, unrelated, self.quote)

    def test_a_refusal_after_literal_read_returns_no_proof(self):
        reading, evidence, records = self.bound()
        record = records[self.target['key']]
        for changes in ({'text': 'Altered report.'}, {'field_key': 'not-this-field'}):
            with self.subTest(changes=changes):
                result = r.read(reading, self.target['label'], evidence, record, **changes)
                self.assertFalse(result['valid'])
                self.assertEqual(result['elicited_ids'], set())
        for record in (None, 'invalid-signature'):
            with self.subTest(record=record):
                result = r.read(reading, self.target['label'], evidence, record,
                                field_key=self.target['key'])
                self.assertFalse(result['valid'])
                self.assertEqual(result['elicited_ids'], set())

    def test_reviewed_syntax_union_cannot_supply_omitted_literal_proof(self):
        reading, evidence, records = self.bound()
        reading['_literal_elicited'] = {(g.question_key(self.target['label']), 1)}
        with patch('core.v3_literal_facts.complete_ids', return_value=set()), \
                patch('core.reviewed_source.complete_ids', return_value={1}):
            result = r.read(reading, self.target['label'], evidence, records[self.target['key']],
                            field_key=self.target['key'])
            self.assertTrue(result['valid'])
            self.assertEqual(result['syntax_ids'], {1})
            self.assertEqual(result['elicited_ids'], set())
            self.assert_held(self.quote, self.target, self.quote)

    def test_relation_floors_require_explicit_successful_read_proof(self):
        reading, evidence, records = self.bound()
        unit = reading['units'][0]
        label = g.question_key(self.target['label'])
        reading['_literal_elicited'] = {(label, unit['id'])}
        causes = g.v3_relation_causes(reading, unit, label, {unit['id']}, self.target['key'])
        self.assertIn('other_person', [flag for _, flag in causes])
        self.assertIn('syntax_incomplete', [flag for _, flag in causes])
        result = r.read(reading, label, evidence, records[self.target['key']], field_key=self.target['key'])
        self.assertTrue(result['valid'])
        self.assertEqual(g.v3_relation_causes(reading, unit, label, {unit['id']}, self.target['key'],
                                            elicited=unit['id'] in result['elicited_ids']), [])

    def test_foreign_conditional_uncertain_and_temporal_sources_stay_held(self):
        for quote in (self.quote.replace('the patient said', 'the father said'),
                      self.quote.replace('the patient said', 'the doctor said'),
                      self.quote.replace('When asked', 'If asked'),
                      self.quote.replace('staff also confirm', 'staff might confirm'),
                      self.quote.replace('staff also confirm', 'staff will confirm'),
                      self.quote.replace('the patient said', 'I said'),
                      self.quote.replace('knows about', 'might know about')):
            with self.subTest(quote=quote): self.assert_held(quote, self.target, quote)
        temporal = copy.deepcopy(self.target)
        temporal['source_questions'][0]['question'] += ' What happened before treatment?'
        temporal['context'] += ' What happened before treatment?'
        self.assert_held(self.quote, temporal, self.quote)

    def test_full_source_unresolved_or_contrary_relation_is_not_dischargeable(self):
        tail = 'The patient denies making that report.'
        notes = self.quote + '\n' + tail
        for relation in ('unresolved', 'contrary', 'qualifier'):
            with self.subTest(relation=relation):
                answer = offered(notes, [self.target], {self.target['key']: [self.quote]},
                                 overrides={(self.target['key'], tail): relation})[self.target['key']]
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
                stored.update(status='supported', text=self.quote)
                self.assertEqual(g.governed_decisions(notes, [self.target],
                                                      {self.target['key']: stored}), [self.target['label']])
