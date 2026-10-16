"""Retained Rowan provider stages, prospective v11 rules, no inference calls."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation
from core import semantic_generation as semantic
from core.tests.test_semantic_generation import assignments, fact

FIXTURE = Path(__file__).with_name('fixtures') / 'rowan_semantic_retained.json'


class RowanSemanticValidationTests(SimpleTestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text())
        self.notes = self.case['notes']
        self.fields = self.case['fields']
        self.definitions = deepcopy(self.case['definitions'])
        self.units, _ = generation.source_units(self.notes, self.fields)
        self.raw_facts = semantic.resolve_source_references(self.notes, self.units,
            self.case['extractor'], reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)

    def prospective_definitions(self):
        # These explicit new-use definition corrections are not a validator
        # exception. The original atomic definitions stay in the fixture.
        definitions = deepcopy(self.definitions)
        for key in ('cell_4', 'cell_7', 'cell_13'):
            definitions[key]['answer_mode'] = 'narrative'
        return definitions

    def facts(self, scope=semantic.LITERAL_SOURCE_SCOPE_CONTRACT):
        return semantic.validate_facts(self.notes, self.units, self.raw_facts,
            scope_contract=scope, timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def run_retained(self, scope, definitions):
        stages = [('extractor', 1, 'extractor'), ('assigner', 1, 'assigner'),
                  ('checker', 1, 'checker'), ('assigner', 2, 'repair_assigner'),
                  ('checker', 2, 'repair_checker')]
        calls = []
        def send(role, attempt, payload, schema, instructions):
            expected_role, expected_attempt, name = stages[len(calls)]
            self.assertEqual((role, attempt), (expected_role, expected_attempt))
            calls.append((role, deepcopy(payload)))
            return deepcopy(self.case[name])
        answers = semantic.run(self.notes, self.fields, definitions, send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT, scope_contract=scope)
        for field in self.fields:
            semantic.validate_stored_answer(self.notes, field, definitions[field['key']], answers[field['key']])
        self.assertEqual(len(calls), 5)
        return answers, calls

    def test_original_exact_source_and_failure_are_preserved(self):
        self.assertEqual(hashlib.sha256(self.notes.encode()).hexdigest(),
            self.case['provenance']['source_sha256'])
        self.assertIn('\r\n', self.notes)
        answers, _ = self.run_retained(semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT, self.definitions)
        self.assertEqual(Counter(a['status'] for a in answers.values()),
            {'conflict': 11, 'ambiguous': 1, 'missing': 2})
        self.assertTrue(all(not answer['text'] for answer in answers.values()))

    def test_actual_trigger_is_local_pointer_negation_not_fictional_banner(self):
        governance = semantic._fact_governance(self.notes, self.units, {}, semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT)
        self.assertFalse(governance[3]); self.assertFalse(governance[4])
        self.assertFalse(generation.REFRAMED_SCOPE.search(self.notes))
        self.assertFalse(generation.QUOTED_SOURCE.search(self.notes))
        self.assertTrue(governance[8])
        self.assertEqual([u['quote'] for u in self.units if not generation._plain_pointer_only(u['quote'])],
            ['The cause of these symptoms has not been established.'])
        without_banner = self.notes.replace('FICTIONAL PATIENT FOR SOFTWARE TESTING ONLY\r\n\r\n', '')
        self.assertTrue(generation.negative_heading(without_banner))
        self.assertFalse(semantic._fact_governance(self.notes, self.units, {}, semantic.LITERAL_SOURCE_SCOPE_CONTRACT)[8])

    def test_retained_stages_yield_twelve_supported_and_two_missing_with_prospective_definitions(self):
        answers, calls = self.run_retained(semantic.LITERAL_SOURCE_SCOPE_CONTRACT, self.prospective_definitions())
        self.assertEqual(Counter(a['status'] for a in answers.values()), {'supported': 12, 'missing': 2})
        self.assertEqual(answers['cell_0']['text'], 'Synthetic Rowan Blake')
        self.assertEqual(answers['cell_12']['text'], '24')
        self.assertIn('Episodes last about 20 minutes', answers['cell_5']['text'])
        self.assertIn('for 10 days', answers['cell_5']['text'])
        self.assertIn('for three weeks', answers['cell_5']['text'])
        self.assertIn('Denies heartburn, constipation', answers['cell_5']['text'])
        self.assertIn('No rebound tenderness or guarding', answers['cell_6']['text'])
        self.assertIn('has not been established', answers['cell_7']['text'])
        self.assertIn('have not been diagnosed', answers['cell_7']['text'])
        self.assertIn('No medication was prescribed today', answers['cell_8']['text'])
        self.assertIn('Established patient', answers['cell_4']['text'])
        self.assertEqual(answers['cell_13']['text'], 'Office E/M selection is based on total physician time')
        self.assertEqual(answers['cell_10']['text'], '')
        self.assertEqual(answers['cell_11']['text'], '')
        self.assertFalse(any(a['reviewed'] for a in answers.values()))
        self.assertIn('local_literal_source_findings', calls[3][1])

    def test_atomic_approved_definitions_are_not_silently_reinterpreted(self):
        answers, _ = self.run_retained(semantic.LITERAL_SOURCE_SCOPE_CONTRACT, self.definitions)
        for key in ('cell_4', 'cell_7', 'cell_13'):
            self.assertEqual(answers[key]['status'], 'conflict')
            self.assertEqual(answers[key]['text'], '')

    def test_assessment_omission_is_held_even_when_independent_checker_passes(self):
        self.case['checker']['fields'] = [dict(row, verdict='pass') if row['key']=='cell_7' else row
            for row in self.case['checker']['fields']]
        self.case['repair_assigner'] = {'fields': [deepcopy(self.case['assigner']['fields'][7])]}
        self.case['repair_checker']['fields'] = [dict(row, verdict='pass') if row['key']=='cell_7' else row
            for row in self.case['repair_checker']['fields']]
        answers, _ = self.run_retained(semantic.LITERAL_SOURCE_SCOPE_CONTRACT, self.prospective_definitions())
        self.assertIn(answers['cell_7']['status'], ('conflict', 'ambiguous'))
        self.assertEqual(answers['cell_7']['text'], '')
        self.assertTrue(any('omits a documented diagnostic limitation' in r for r in answers['cell_7']['review_reasons']))

    def test_postfix_negation_cannot_be_clipped_or_relabelled_positive(self):
        for change in ('clip', 'positive', 'another-occurrence'):
            raw = deepcopy(self.raw_facts)
            selected = next(f for f in raw['facts'] if f['id']=='f24')
            if change=='clip': selected['value_span']['end'] -= len(' have not been diagnosed')
            elif change=='positive': selected['polarity']='affirmed'
            else:
                canonical = self.facts()['f24']
                outside = {'quote': canonical['evidence'][1]['quote'], 'start': 9999, 'end': 10090}
                self.assertFalse(semantic._retained_diagnostic_limit(canonical, outside))
                continue
            facts = semantic.validate_facts(self.notes, self.units, raw,
                scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
            self.assertTrue(facts['f24']['issues'], change)

    def test_literal_diagnostic_waiver_does_not_reassign_a_person_or_foreign_source(self):
        original = next(f for f in self.case['extractor']['facts'] if f['id']=='f24')['value_span']['quote']
        for replacement in ('The nurse has not been diagnosed', 'John Smith has not been diagnosed',
                            'According to another chart, GERD has not been diagnosed',
                            'The clinician has not been diagnosed', 'ABCD has not been diagnosed'):
            with self.subTest(replacement=replacement):
                notes = self.notes.replace(original, replacement)
                units,_ = generation.source_units(notes, self.fields)
                extracted = deepcopy(self.case['extractor'])
                extracted['facts'] = [f for f in extracted['facts'] if f['id'] in ('f1','f23','f24')]
                next(f for f in extracted['facts'] if f['id']=='f24')['value_span']['quote'] = replacement
                raw = semantic.resolve_source_references(notes, units, extracted,
                    reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
                facts = semantic.validate_facts(notes, units, raw, scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
                self.assertTrue(facts['f24']['issues'])
                answers = semantic._assign(notes, self.fields, self.prospective_definitions(), facts,
                    assignments(self.fields, {'cell_7':['f23','f24']}), scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
                self.assertEqual(answers['cell_7']['status'], 'conflict')
                self.assertEqual(answers['cell_7']['text'], '')

    def test_foreign_patient_and_quoted_headings_still_govern_literal_limits(self):
        anchor = 'The cause of these symptoms has not been established.'
        for prefix in ('Other patient: Synthetic Morgan Lane\r\n',
                       'Another patient name: Synthetic Morgan Lane\r\n',
                       'Different patient: Synthetic Morgan Lane\r\n',
                       "Another patient's assessment:\r\n", 'Quoted example:\r\n',
                       "Source from another patient's chart:\r\n", 'Assessment for another patient:\r\n'):
            with self.subTest(prefix=prefix):
                notes = self.notes.replace(anchor, prefix+anchor)
                units,_ = generation.source_units(notes, self.fields)
                extracted = deepcopy(self.case['extractor'])
                extracted['facts'] = [f for f in extracted['facts'] if f['id'] in ('f1','f23','f24')]
                # Rebind the fixture's exact quotations after the inserted
                # source heading; stale offsets must not manufacture the veto.
                for f in extracted['facts']:
                    for ref in (f['value_span'], f['subject']['name_span']):
                        ref['source_unit_id'] = next(u['id'] for u in units if ref['quote'] in u['quote'])
                raw = semantic.resolve_source_references(notes, units, extracted,
                    reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
                facts = semantic.validate_facts(notes, units, raw, scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
                for key in ('f23','f24'):
                    self.assertIn('Governing source context requires clinician review.', facts[key]['issues'])
                answers = semantic._assign(notes, self.fields, self.prospective_definitions(), facts,
                    assignments(self.fields, {'cell_7':['f23','f24']}), scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
                self.assertEqual(answers['cell_7']['status'], 'conflict')
                self.assertEqual(answers['cell_7']['text'], '')

    def test_twenty_minute_symptom_value_cannot_be_physician_time(self):
        raw = deepcopy(self.raw_facts)
        selected = next(f for f in raw['facts'] if f['id']=='f32')
        start = self.notes.index('20 minutes')
        selected['value_span']={'start':start,'end':start+2}
        selected['unit_span']={'start':start+3,'end':start+10}
        unit = next(u for u in self.units if u['start']<=start<u['end'])
        selected['source_unit_ids'] = [2, unit['id']]
        # The actual approximation itself is already protected.
        with self.assertRaises(ValidationError):
            semantic.validate_facts(self.notes, self.units, raw, scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        # Removing an approximation does not make a symptom duration into
        # physician time, even if the model gives it the desired concept label.
        notes = 'Episodes last 20 minutes. Total physician time on the date of service was 24 minutes.'
        fields = [self.fields[12]]
        definitions = {'cell_12':self.definitions['cell_12']}
        selected = fact(notes, fields, 'wrong_duration', '20', kind='measurement',
            concept='total physician time on date of service', unit='minutes', unit_quote='minutes')
        units,_=generation.source_units(notes,fields)
        facts=semantic.validate_facts(notes,units,{'facts':[selected]},scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        answers=semantic._assign(notes,fields,definitions,facts,assignments(fields,{'cell_12':['wrong_duration']}),
            scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        self.assertEqual(answers['cell_12']['status'], 'conflict')
        self.assertTrue(any('not explicitly documented physician time' in r for r in answers['cell_12']['review_reasons']))

    def test_genuine_governing_context_stays_held(self):
        for suffix in ('\r\nThe following findings are denied:\r\nEpigastric pain.',
                       '\r\nAll these statements are incorrect.',
                       '\r\nQuoted example: "The cause of these symptoms has not been established."',
                       '\r\nFamily history: epigastric pain.'):
            with self.subTest(suffix=suffix):
                notes = self.notes+suffix
                units,_=generation.source_units(notes, self.fields)
                facts = semantic.validate_facts(notes, units, self.raw_facts,
                    scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
                self.assertTrue(any('Governing source context' in issue for issue in facts['f1']['issues']))

    def test_competing_patient_identity_remains_held(self):
        notes = self.notes+'\r\nPatient: Synthetic Other Person.'
        units,_=generation.source_units(notes,self.fields)
        facts=semantic.validate_facts(notes,units,self.raw_facts,scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        finding=semantic.patient_name_check(notes,self.definitions['cell_0'],facts,['f1'])
        self.assertEqual(finding['verdict'],'ambiguous')
        self.assertEqual(finding['unrepresented_source_names'][0]['quote'],'Synthetic Other Person')

    def test_unsupported_answer_and_persisted_tampering_remain_rejected(self):
        answers,_=self.run_retained(semantic.LITERAL_SOURCE_SCOPE_CONTRACT,self.prospective_definitions())
        answers['cell_12']['text']='20'
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(self.notes,self.fields[12],self.prospective_definitions()['cell_12'],answers['cell_12'])
        raw=deepcopy(self.raw_facts)
        raw['facts'][0]['value_span']['end']=len(self.notes)+1
        with self.assertRaises(ValidationError):
            semantic.validate_facts(self.notes,self.units,raw,scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
