"""Actual retained Rowan extraction, prospective v12, and no provider calls."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic

FIXTURE = Path(__file__).with_name('fixtures') / 'rowan_objective_retained.json'


class ObjectiveNegationTests(SimpleTestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text())
        self.notes = self.case['notes']
        self.fields = self.case['fields']
        self.definitions = self.case['definitions']

    def facts(self, scope=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT, notes=None, edits=None):
        notes = self.notes if notes is None else notes
        units, _ = generation.source_units(notes, self.fields)
        original_units = {u['id']: u for u in generation.source_units(self.notes, self.fields)[0]}
        extracted = deepcopy(self.case['extractor'])
        # Modified-source controls independently rebind exact retained quotes.
        # Never preserve stale offsets merely to obtain a refusal.
        if edits:
            edits(extracted)
        for fact in extracted['facts']:
            spans = [fact['value_span'], fact['subject']['name_span'],
                     fact['timing']['span'], fact['unit_span']]
            if fact['scale']:
                spans.append(fact['scale']['span'])
            for span in spans:
                if span:
                    original = original_units[span['source_unit_id']]
                    matching = [unit for unit in units if unit['quote'] == original['quote']]
                    span['source_unit_id'] = (matching[0]['id'] if matching else
                        next(unit['id'] for unit in units if span['quote'] in unit['quote']))
        raw = semantic.resolve_source_references(notes, units, extracted,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        return semantic.validate_facts(notes, units, raw, scope_contract=scope,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def run_retained(self, scope):
        names = iter(('extractor', 'assigner', 'checker', 'repair_assigner', 'repair_checker'))
        calls = []
        def send(role, attempt, payload, schema, instructions):
            name = next(names)
            calls.append(name)
            return deepcopy(self.case[name])
        answers = semantic.run(self.notes, self.fields, self.definitions, send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT, scope_contract=scope)
        self.assertEqual(len(calls), 5)
        for field in self.fields:
            semantic.validate_stored_answer(self.notes, field, self.definitions[field['key']], answers[field['key']])
        return answers

    def test_actual_v11_failure_is_preserved(self):
        self.assertEqual(hashlib.sha256(self.notes.encode()).hexdigest(), self.case['provenance']['source_sha256'])
        self.assertIn('\r\n', self.notes)
        facts = self.facts(semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        self.assertEqual({key for key, fact in facts.items() if fact['issues']}, {'f20', 'f22'})
        self.assertIn('This additional negative phrase needs complete, unqualified clinical source binding.', facts['f20']['issues'])
        self.assertIn('The proposed negation is not explicitly grounded in its source clause.', facts['f22']['issues'])
        answers = self.run_retained(semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        self.assertEqual(Counter(answer['status'] for answer in answers.values()), {'supported': 11, 'ambiguous': 1, 'missing': 2})
        self.assertEqual(answers['cell_6']['text'], '')

    def test_v12_releases_only_complete_owned_examination_negatives(self):
        before = self.facts(semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        after = self.facts()
        self.assertFalse(any(fact['issues'] for fact in after.values()))
        self.assertEqual(after['f20']['value_evidence']['quote'], 'in no acute distress')
        self.assertEqual(after['f22']['value_evidence']['quote'], 'There is no rebound tenderness or guarding')
        for key in before:
            self.assertEqual({k: v for k, v in before[key].items() if k != 'issues'},
                             {k: v for k, v in after[key].items() if k != 'issues'})
        self.assertEqual(before['f35']['value_evidence'], after['f35']['value_evidence'])

    def test_held_independent_verdict_is_not_manufactured_into_a_pass(self):
        answers = self.run_retained(semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        self.assertEqual(answers['cell_6']['status'], 'ambiguous')
        self.assertEqual(answers['cell_6']['text'], '')
        self.assertEqual(answers['cell_6']['independent_check']['verdict'], 'ambiguous')
        self.assertFalse(any(answer['reviewed'] for answer in answers.values()))
        self.assertEqual(Counter(answer['status'] for answer in answers.values()), {'supported': 11, 'ambiguous': 1, 'missing': 2})

    def test_wrong_patient_quoted_unknown_and_competing_contexts_stay_held(self):
        for insertion in ('Other patient: Synthetic Morgan Lane\r\n',
                          'Patient: Synthetic Morgan Lane\r\n',
                          'Quoted example:\r\n',
                          'The following findings concern John Smith.\r\n',
                          'The nurse was examined.\r\n',
                          'This paragraph describes a possible future examination.\r\n'):
            with self.subTest(insertion=insertion):
                notes = self.notes.replace('The patient is alert', insertion+'The patient is alert')
                facts = self.facts(notes=notes)
                self.assertTrue(facts['f20']['issues'])
                self.assertTrue(facts['f22']['issues'])

    def test_an_objective_heading_cannot_erase_prior_foreign_attribution(self):
        for prefix in ("John Smith's examination:\r\n",
                       'Examination of John Smith:\r\n',
                       'The next examination describes John Smith.\r\n',
                       'The subsequent physical exam describes John Smith.\r\n',
                       'The remaining findings concern the nurse.\r\n',
                       'The next part belongs to John Smith.\r\n',
                       'The following examination describes John Smith.\r\n',
                       'The examination below describes John Smith.\r\n',
                       'The objective section describes John Smith, not the patient.\r\n',
                       'The examination was not performed.\r\n',
                       'Examination from the training vignette follows.\r\n'):
            with self.subTest(prefix=prefix):
                facts = self.facts(notes=self.notes.replace('O - Objective', prefix+'O - Objective'))
                self.assertTrue(facts['f20']['issues'])
                self.assertTrue(facts['f22']['issues'])

    def test_unperformed_or_unknown_examination_suffix_cannot_be_omitted(self):
        for suffix in ('The examination was not performed.',
                       'These observations describe an illustration.',
                       'The nurse was examined instead of the patient.'):
            notes = self.notes.replace('A - Assessment', suffix+'\r\nA - Assessment')
            facts = self.facts(notes=notes)
            self.assertTrue(facts['f20']['issues'])
            self.assertTrue(facts['f22']['issues'])

    def test_later_attribution_retraction_or_unperformed_statement_is_not_omittable(self):
        for suffix in ('The physical findings above were copied from another patient.',
                       'Those examination findings were retracted.',
                       'The examination was not performed.',
                       'The abdomen findings belong to John Smith.',
                       'The patient has rebound tenderness.'):
            facts = self.facts(notes=self.notes+'\r\n'+suffix)
            self.assertTrue(facts['f20']['issues'])
            self.assertTrue(facts['f22']['issues'])

    def test_missing_or_unrepresented_patient_identity_cannot_release_negatives(self):
        def omit_identity(extracted):
            extracted['facts'] = [fact for fact in extracted['facts'] if fact['kind'] != 'identity']
        facts = self.facts(edits=omit_identity)
        self.assertTrue(facts['f20']['issues'])
        self.assertTrue(facts['f22']['issues'])
        facts = self.facts(notes=self.notes+'\r\nPatient: Synthetic Morgan Lane.')
        self.assertTrue(facts['f20']['issues'])
        self.assertTrue(facts['f22']['issues'])

    def test_negatives_require_objective_context_and_literal_unqualified_source(self):
        for notes in (self.notes.replace('O - Objective', 'Example findings'),
                      self.notes.replace('O - Objective', 'P - Plan'),
                      self.notes.replace('The patient is alert and in no acute distress.',
                                         'The patient is alert and in no acute distress according to his brother.'),
                      self.notes.replace('There is no rebound tenderness or guarding.',
                                         'There is no rebound tenderness or guarding unless the patient moves.'),
                      self.notes.replace('There is no rebound tenderness or guarding.',
                                         'There is no rebound tenderness or guarding, except on palpation.')):
            with self.subTest(notes=notes):
                facts = self.facts(notes=notes)
                self.assertTrue(facts['f20']['issues'] or facts['f22']['issues'])
                self.assertTrue(facts['f22']['issues'])

    def test_selected_negative_cannot_be_clipped_relabelled_or_reowned(self):
        for key, mode in (('f20', 'positive'), ('f22', 'positive'), ('f22', 'clip'),
                          ('f20', 'other'), ('f22', 'other')):
            with self.subTest(key=key, mode=mode):
                def edit(extracted):
                    fact = next(f for f in extracted['facts'] if f['id'] == key)
                    if mode == 'positive':
                        fact['polarity'] = 'affirmed'
                    elif mode == 'clip':
                        fact['value_span']['quote'] = 'rebound tenderness or guarding'
                    else:
                        fact['subject']['kind'] = 'uncertain'
                self.assertTrue(self.facts(edits=edit)[key]['issues'])

    def test_source_wide_denial_and_quotes_still_govern_new_negatives(self):
        for suffix in ('\r\nAll these findings are incorrect.',
                       '\r\nQuoted example: "The patient is alert and in no acute distress."'):
            facts = self.facts(notes=self.notes+suffix)
            for key in ('f20', 'f22'):
                self.assertIn('Governing source context requires clinician review.', facts[key]['issues'])
