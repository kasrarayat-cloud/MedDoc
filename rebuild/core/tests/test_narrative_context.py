"""Narrative coverage regressions; staged fixtures do not establish model quality.

Live acceptance must still exercise the unchanged source notes and inspect Word.
These tests prove grounded complete answers, bounded omission repair, and holds
without broadening a narrow approved destination or changing historical proofs.
"""
from copy import deepcopy

from django.test import SimpleTestCase

from core import semantic_generation as semantic
from documents.semantic_preparation_roles import default_definitions
from .test_semantic_generation import (
    NOTES, WRIST_NOTES, FixtureSender, alex_case, assignments, checker, fact,
    wrist_reference_case,
)


class NarrativeContextTests(SimpleTestCase):
    def test_complete_history_and_atomic_values_coexist_under_unchanged_definitions(self):
        for notes, factory, history_quote, symptom, score in (
            (NOTES, alex_case, 'left ankle pain after stepping off a curb yesterday', 'Left ankle pain', 3),
            (WRIST_NOTES, wrist_reference_case, 'right wrist pain after lifting a heavy box two days ago', 'Right wrist pain', 6),
        ):
            with self.subTest(notes=notes):
                fields, definitions, facts, assigned = factory()
                before = deepcopy((fields, definitions))
                facts.append(fact(notes, fields, 'complete_history', history_quote, kind='history'))
                if notes == NOTES:
                    facts.append(fact(notes, fields, 'severity_text', 'rates the pain as 3 out of 10', kind='history'))
                    ids = ['complete_history', 'severity_text', 'head_injury']
                else:
                    ids = ['complete_history', 'f8']
                next(row for row in assigned['fields'] if row['key'] == 'cell_2')['fact_ids'] = ids
                sender = FixtureSender(facts, assigned)
                answers = semantic.run(notes, fields, definitions, sender,
                    reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
                self.assertEqual((fields, definitions), before)
                self.assertEqual(answers['cell_1']['text'], symptom)
                self.assertEqual(answers['cell_4']['value'], score)
                self.assertIn(history_quote, answers['cell_2']['text'].lower())
                self.assertIn('out of ten' if score == 6 else 'out of 10', answers['cell_2']['text'])
                self.assertNotIn('Synthetic Alex Morgan', answers['cell_2']['text'])
                self.assertEqual(len(sender.calls), 3)
                for field in fields:
                    answer = answers[field['key']]
                    self.assertEqual(answer['status'], 'supported')
                    semantic.validate_stored_answer(notes, field, definitions[field['key']], answer)
                    for evidence in answer['evidence']:
                        self.assertEqual(notes[evidence['start']:evidence['end']], evidence['quote'])

    def test_history_omission_repair_adds_existing_context_without_changing_other_fields(self):
        fields, definitions, facts, assigned = wrist_reference_case()
        next(row for row in assigned['fields'] if row['key'] == 'cell_2')['fact_ids'] = ['f3']
        checked = checker(assigned, verdicts={'cell_2': 'omission'})
        finding = next(row for row in checked['fields'] if row['key'] == 'cell_2')
        finding.update(fact_ids=['f2', 'f3', 'f8'], reason='The history omits its complaint and documented severity.')
        complete = deepcopy(assigned)
        next(row for row in complete['fields'] if row['key'] == 'cell_2')['fact_ids'] = ['f2', 'f3', 'f8']
        repair = {'fields': [row for row in complete['fields'] if row['key'] == 'cell_2']}
        sender = FixtureSender(facts, assigned, checked, repaired=repair, rechecked=checker(complete))
        answers = semantic.run(WRIST_NOTES, fields, definitions, sender,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        self.assertEqual([call[:2] for call in sender.calls],
            [('extractor', 1), ('assigner', 1), ('checker', 1), ('assigner', 2), ('checker', 2)])
        self.assertEqual(sender.calls[3][2]['repair_keys'], ['cell_2'])
        self.assertEqual(answers['cell_2']['text'],
            'Right wrist pain; After lifting a heavy box two days ago; The pain is six out of ten')
        self.assertEqual(answers['cell_2']['fact_ids'], ['f2', 'f3', 'f8'])
        for key in answers.keys() - {'cell_2'}:
            self.assertEqual(answers[key]['text'], sender.calls[2][2]['proposed_answers'][key]['text'])
        self.assertEqual(answers['cell_4']['value'], 6)

    def plan_case(self):
        notes = 'Plan: Follow-up in one week.'
        fields = [{'key': key, 'label': label, 'locator': {'cell': index}}
            for index, (key, label) in enumerate((('management', 'Plan'), ('interval', 'Review interval')))]
        definitions = default_definitions(fields)
        for key, mode, meaning in (
            ('management', 'narrative', 'The documented management action and timing.'),
            ('interval', 'atomic', 'Only the requested relative review interval.'),
        ):
            definitions[key].update(version=2, answer_mode=mode, meaning=meaning)
            definitions[key]['scope']['temporality'] = 'future'
        facts = [fact(notes, fields, 'interval', 'in one week', kind='follow_up',
                      timing='future', timing_quote='in one week')]
        return notes, fields, definitions, facts

    def test_plan_action_and_interval_remain_distinct_values_with_exact_evidence(self):
        notes, fields, definitions, facts = self.plan_case()
        facts.append(fact(notes, fields, 'action', 'Follow-up in one week', kind='plan',
                          timing='future', timing_quote='in one week'))
        sender = FixtureSender(facts, assignments(fields, {'management': ['action'], 'interval': ['interval']}))
        answers = semantic.run(notes, fields, definitions, sender)
        self.assertEqual(answers['management']['text'], 'Follow-up in one week')
        self.assertEqual(answers['interval']['text'], 'In one week')
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])

    def test_missing_extracted_action_cannot_be_invented_by_bounded_assignment_repair(self):
        notes, fields, definitions, facts = self.plan_case()
        assigned = assignments(fields, {'management': ['interval'], 'interval': ['interval']})
        checked = checker(assigned, verdicts={'management': 'omission'})
        next(row for row in checked['fields'] if row['key'] == 'management')['reason'] = 'The documented action is missing from the fact inventory.'
        complete = assignments(fields, {'interval': ['interval']})
        repaired = {'fields': [row for row in complete['fields'] if row['key'] == 'management']}
        sender = FixtureSender(facts, assigned, checked, repaired=repaired, rechecked=checker(complete))
        answers = semantic.run(notes, fields, definitions, sender)
        self.assertEqual(len(sender.calls), 5)
        self.assertEqual((answers['management']['text'], answers['management']['value'], answers['management']['status']),
                         ('', None, 'ambiguous'))
        self.assertIn('no grounded fact resolved it', ' '.join(answers['management']['review_reasons']))
        self.assertEqual(answers['interval']['text'], 'In one week')
        self.assertEqual(len(answers['management']['facts']), 1)

    def test_narrow_mechanism_definition_still_accepts_only_its_documented_event(self):
        notes = 'Shoulder discomfort after moving furniture yesterday.'
        fields = [{'key': 'mechanism', 'label': 'Mechanism', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['mechanism']['meaning'] = 'Only the documented precipitating event and its timing.'
        facts = [fact(notes, fields, 'event', 'after moving furniture yesterday', kind='history')]
        answers = semantic.run(notes, fields, definitions,
            FixtureSender(facts, assignments(fields, {'mechanism': ['event']})))
        self.assertEqual(answers['mechanism']['text'], 'After moving furniture yesterday')
        self.assertEqual(answers['mechanism']['status'], 'supported')
