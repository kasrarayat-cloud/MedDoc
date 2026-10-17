"""Retained fresh-case replay and explicitly synthetic future-stage responses.

The five historical replies below are immutable provider evidence. The synthetic
assigner/checker controls test pipeline behavior, not a claim that a paid model
has already returned those proposals. All tests use zero provider calls.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic
from core.tests.test_semantic_generation import assignments, checker, fact, span

FIXTURE = Path(__file__).with_name('fixtures') / 'nadia_semantic_retained.json'


class FreshClinicalSemanticsTests(SimpleTestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text())
        self.notes = self.case['notes']
        self.fields = self.case['fields']
        self.definitions = self.case['definitions']

    def facts(self, *, scope=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT, notes=None, edit=None):
        notes = self.notes if notes is None else notes
        units, _ = generation.source_units(notes, self.fields)
        original = {u['id']: u for u in generation.source_units(self.notes, self.fields)[0]}
        extracted = deepcopy(self.case['extractor'])
        if edit:
            edit(extracted)
        for row in extracted['facts']:
            refs = [row['value_span'], row['subject']['name_span'], row['timing']['span'], row['unit_span']]
            if row['scale']:
                refs.append(row['scale']['span'])
            for ref in filter(None, refs):
                matches = [u for u in units if u['quote'] == original[ref['source_unit_id']]['quote']]
                if not matches and len(units) == len(original):
                    matches = [u for u in units if u['id'] == ref['source_unit_id'] and ref['quote'] in u['quote']]
                ref['source_unit_id'] = (matches[0]['id'] if matches else
                    next(u['id'] for u in units if ref['quote'] in u['quote']))
        raw = semantic.resolve_source_references(notes, units, extracted,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        return semantic.validate_facts(notes, units, raw, scope_contract=scope,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def assign(self, proposed=None, *, facts=None, notes=None):
        return semantic._assign(self.notes if notes is None else notes, self.fields, self.definitions,
            self.facts() if facts is None else facts, self.synthetic_assignment() if proposed is None else proposed,
            scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def synthetic_assignment(self):
        proposal = deepcopy(self.case['assigner'])
        for row in proposal['fields']:
            if row['fact_ids']:
                row['status'] = 'supported'
            if row['key'] == 'cell_7':
                row['fact_ids'] = ['f12']
            if row['key'] == 'cell_14':
                row['fact_ids'] = ['f27', 'f28', 'f29', 'f30', 'f31', 'f32', 'f34']
        return proposal

    def test_exact_historical_source_and_all_five_provider_stages_keep_original_failure(self):
        self.assertEqual(hashlib.sha256(self.notes.encode()).hexdigest(), self.case['provenance']['source_sha256'])
        calls = []
        def send(role, attempt, payload, schema, instructions):
            calls.append((role, attempt))
            return deepcopy(self.case[('repair_' if attempt == 2 else '') + role])
        answers = semantic.run(self.notes, self.fields, self.definitions, send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,
            scope_contract=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        self.assertEqual(Counter(a['status'] for a in answers.values()),
            {'supported': 11, 'conflict': 4, 'ambiguous': 1, 'missing': 2})
        self.assertEqual(calls, [('extractor', 1), ('assigner', 1), ('checker', 1), ('assigner', 2), ('checker', 2)])
        self.assertTrue(all(not answers[key]['text'] for key in ('cell_7','cell_12','cell_13','cell_14','cell_15')))

    def test_new_contract_changes_validation_only_without_rewriting_extracted_evidence(self):
        before = self.facts(scope=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        after = self.facts()
        self.assertEqual({key for key, f in before.items() if f['issues']}, {'f23','f25','f26','f29'})
        self.assertFalse(any(f['issues'] for f in after.values()))
        for key in before:
            self.assertEqual({k:v for k,v in before[key].items() if k!='issues'},
                             {k:v for k,v in after[key].items() if k!='issues'})

    def test_unchanged_retained_assignment_still_holds_wrong_severity_and_incomplete_plan(self):
        answers = self.assign(deepcopy(self.case['assigner']))
        self.assertEqual(answers['cell_7']['status'], 'conflict')
        self.assertEqual(answers['cell_14']['status'], 'conflict')
        self.assertTrue(any('not performed today' in reason for reason in answers['cell_14']['review_reasons']))
        # Historical model ambiguity is not changed into a fabricated pass.
        self.assertEqual(answers['cell_13']['status'], 'ambiguous')

    def test_synthetic_future_proposals_produce_sixteen_supported_and_two_genuine_blanks(self):
        answers = self.assign()
        self.assertEqual(Counter(a['status'] for a in answers.values()), {'supported':16,'missing':2})
        self.assertEqual(answers['cell_7']['text'], '5 out of 10')
        self.assertEqual(answers['cell_16']['text'], '36')
        self.assertIn('about 15 minutes', answers['cell_6']['text'])
        self.assertIn('denies vomiting', answers['cell_8']['text'].lower())
        self.assertIn('lisinopril 10 mg orally once daily', answers['cell_9']['text'].lower())
        self.assertIn('Penicillin causes a rash', answers['cell_10']['text'])
        self.assertIn('The cause remains uncertain', answers['cell_13']['text'])
        self.assertIn('have not been established', answers['cell_13']['text'])
        for key in ('cell_14', 'cell_15'):
            self.assertIn('ordered for a later date', answers[key]['text'])
            self.assertIn('not performed today', answers[key]['text'])
        for key in ('cell_4','cell_11'):
            self.assertEqual(answers[key]['text'], '')
            self.assertFalse(answers[key]['fact_ids'])
        self.assertFalse(any(a['reviewed'] for a in answers.values()))

    def test_synthetic_targeted_repair_receives_type_options_and_every_local_omission(self):
        calls = []
        first = deepcopy(self.case['assigner'])
        for row in first['fields']:
            if row['fact_ids']:
                row['status'] = 'supported'
        complete = self.synthetic_assignment()
        def send(role, attempt, payload, schema, instructions):
            calls.append((role, attempt, deepcopy(payload)))
            self.assertTrue(instructions.endswith(semantic.CLINICAL_LITERAL_INSTRUCTIONS))
            if role == 'extractor':
                return deepcopy(self.case['extractor'])
            self.assertEqual(payload['atomic_measurement_options']['cell_7'],
                [{'fact_id':'f12', 'rendered_value':'5 out of 10'}])
            if role == 'assigner' and attempt == 1:
                return first
            if role == 'checker' and attempt == 1:
                # Even an incorrect independent pass cannot suppress local
                # type/completeness findings or the targeted repair stage.
                return checker(first)
            if role == 'assigner':
                self.assertEqual(set(payload['repair_keys']), {'cell_7','cell_14'})
                self.assertEqual(set(payload['local_assignment_findings']), {'cell_7','cell_14'})
                return {'fields':[row for row in complete['fields'] if row['key'] in payload['repair_keys']]}
            return checker(complete)
        answers = semantic.run(self.notes, self.fields, self.definitions, send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,
            scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
        self.assertEqual(len(calls),5)
        self.assertEqual(Counter(a['status'] for a in answers.values()), {'supported':16,'missing':2})
        for field in self.fields:
            semantic.validate_stored_answer(self.notes,field,self.definitions[field['key']],answers[field['key']])

    def test_pass_cannot_release_missing_negative_or_uncertainty(self):
        for key, omitted in (('cell_13','f25'),('cell_13','f26'),('cell_14','f29'),('cell_14','f30'),('cell_15','f29')):
            with self.subTest(key=key, omitted=omitted):
                proposed = self.synthetic_assignment()
                row = next(row for row in proposed['fields'] if row['key']==key)
                row['fact_ids'].remove(omitted)
                answers = self.assign(proposed)
                checks,bad = semantic._check(self.fields,self.facts(),checker(proposed))
                semantic._apply_check(answers,checks,bad)
                self.assertEqual(answers[key]['text'],'')
                self.assertTrue(any('clinical qualification' in reason for reason in answers[key]['review_reasons']))

    def test_unknown_foreign_quoted_retracted_or_unperformed_source_cannot_release_new_literals(self):
        for insertion in ('Other patient: Synthetic Other Person.', 'Patient: Synthetic Other Person.',
                'The next part belongs to John Smith.', 'The examination was not performed.',
                'The nurse was examined.', 'Quoted example:',
                'The findings above were copied from a different chart.', 'All these findings are incorrect.'):
            for position in ('before','after'):
                with self.subTest(insertion=insertion,position=position):
                    notes = (self.notes.replace('Examination\r\n',insertion+'\r\nExamination\r\n')
                        if position=='before' else self.notes+'\r\n'+insertion)
                    facts = self.facts(notes=notes)
                    for key in ('f23','f25','f26','f29'):
                        self.assertTrue(facts[key]['issues'],key)

    def test_missing_identity_cannot_be_replaced_by_model_patient_annotations(self):
        facts = self.facts(edit=lambda raw:raw.update(facts=[f for f in raw['facts'] if f['id']!='f1']))
        for key in ('f23','f25','f26','f29'):
            self.assertTrue(facts[key]['issues'])

    def test_diagnostic_noun_cannot_bind_an_arbitrary_named_or_foreign_subject(self):
        for owner in ('John Smith', 'The sibling', 'The mother', 'The clinician', 'His'):
            for predicate in ('established','diagnosed','confirmed'):
                with self.subTest(owner=owner,predicate=predicate):
                    phrase=f'{owner} diagnosis has not been {predicate}'
                    notes=self.notes.replace('Gallstones, cholecystitis and pancreatitis have not been established',phrase)
                    def edit(raw):
                        next(f for f in raw['facts'] if f['id']=='f26')['value_span']['quote']=phrase
                    facts=self.facts(notes=notes,edit=edit)
                    self.assertTrue(facts['f26']['issues'])
                    answer=self.assign(facts=facts,notes=notes)['cell_13']
                    self.assertEqual(answer['text'],'')
                    self.assertEqual(answer['status'],'conflict')

    def test_literal_qualification_must_keep_complete_value_and_polarity(self):
        for key,quote in (('f25','The cause'),('f26','Gallstones, cholecystitis and pancreatitis'),
                          ('f29','The ultrasound')):
            for mode in ('clip','positive','wrong_owner'):
                with self.subTest(key=key,mode=mode):
                    def edit(raw):
                        row=next(f for f in raw['facts'] if f['id']==key)
                        if mode=='clip': row['value_span']['quote']=quote
                        elif mode=='positive': row['polarity']='affirmed'
                        else: row['subject']['kind']='uncertain'
                    self.assertTrue(self.facts(edit=edit)[key]['issues'])

    def test_unknown_or_conditional_qualifications_stay_held(self):
        for original,replacement,key in (
            ('The cause remains uncertain.','The cause remains uncertain according to another patient.','f25'),
            ('have not been established.','have not been established unless prior records are counted.','f26'),
            ('The ultrasound was not performed today.','The ultrasound was not performed today unless the technician did it.','f29')):
            with self.subTest(replacement=replacement):
                self.assertTrue(self.facts(notes=self.notes.replace(original,replacement))[key]['issues'])

    def test_severity_requires_its_own_exact_scale_and_never_a_bare_narrative_number(self):
        facts=self.facts()
        for key in ('cell_6','cell_12','cell_13'):
            answers=self.assign(assignments(self.fields,{key:['f12']}))
            self.assertEqual(answers[key]['text'],'')
        wrong=deepcopy(facts['f12'])
        wrong['scale']=None
        self.assertIsNone(semantic._concise_score_phrase(self.notes,wrong,self.definitions['cell_7']))
        wrong=deepcopy(facts['f12']); wrong['polarity']='uncertain'
        self.assertIsNone(semantic._concise_score_phrase(self.notes,wrong,self.definitions['cell_7']))

    def test_omitted_competing_source_score_cannot_be_hidden_by_extractor_or_passing_checker(self):
        for phrase in ('The pain is rated 8 out of 10.', 'The pain score is 5 out of 100.'):
            with self.subTest(phrase=phrase):
                notes=self.notes.replace('The pain is rated 5 out of 10.', 'The pain is rated 5 out of 10. '+phrase)
                facts=self.facts(notes=notes)
                # No fact for the second source score: the source itself is
                # authoritative even when both model roles omit that fact.
                self.assertEqual([f['id'] for f in facts.values() if f['scale']],['f12'])
                proposed=self.synthetic_assignment()
                answers=self.assign(proposed,facts=facts,notes=notes)
                checks,bad=semantic._check(self.fields,facts,checker(proposed))
                semantic._apply_check(answers,checks,bad)
                self.assertEqual(answers['cell_7']['text'],'')
                self.assertIn('competing severity',answers['cell_7']['review_reasons'][0])

    def test_score_inventory_does_not_relabel_other_time_body_site_or_person_as_current_pain(self):
        for phrase in ('Yesterday the pain was rated 8 out of 10.',
                       'The left ankle pain is rated 8 out of 10.',
                       'The nurse pain score is 8 out of 10.',
                       'The pain is rated 8 out of 10 if walking.'):
            self.assertEqual(semantic._source_severity_measurements(phrase),[])

    def test_equivalent_word_and_numeric_scores_are_not_competing_measurements(self):
        notes=self.notes.replace('The pain is rated 5 out of 10.',
            'The pain is rated 5 out of 10. The pain is rated five out of ten.')
        facts=self.facts(notes=notes)
        raw=fact(notes,self.fields,'word_score','five',kind='measurement',concept='pain severity score',
            scale={'minimum':None,'maximum':'10','span':span(notes,'out of ten')})
        units,_=generation.source_units(notes,self.fields)
        extra=semantic.validate_facts(notes,units,{'facts':[raw]},scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
        self.assertFalse(extra['word_score']['issues'])
        facts.update(extra)
        answers=self.assign(facts=facts,notes=notes)
        self.assertEqual(answers['cell_7']['status'],'supported')
        self.assertEqual(answers['cell_7']['text'],'5 out of 10')

    def test_routine_vitals_do_not_invalidate_unrelated_clinical_qualifications(self):
        for phrase in ('Respiratory rate is 16 breaths per minute.', 'Heart rate is 72 bpm.',
                       'Oxygen saturation is 98 percent.', 'Weight is 64 kg.', 'Height is 168 cm.'):
            with self.subTest(phrase=phrase):
                notes=self.notes.replace('\r\nAssessment\r\n','\r\n'+phrase+'\r\nAssessment\r\n')
                facts=self.facts(notes=notes)
                raw=fact(notes,self.fields,'extra_vital',phrase.removesuffix('.'),concept='additional vital sign')
                units,_=generation.source_units(notes,self.fields)
                extra=semantic.validate_facts(notes,units,{'facts':[raw]},scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
                self.assertFalse(extra['extra_vital']['issues'])
                facts.update(extra)
                proposed=self.synthetic_assignment()
                next(row for row in proposed['fields'] if row['key']=='cell_12')['fact_ids'].append('extra_vital')
                answers=self.assign(proposed,facts=facts,notes=notes)
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
                self.assertIn(phrase.removesuffix('.'),answers['cell_12']['text'])
    def test_episode_minutes_cannot_be_selected_as_physician_time(self):
        raw=fact(self.notes,self.fields,'wrong_duration','15',kind='measurement',concept='total physician time',
            unit='minutes',unit_quote='minutes')
        units,_=generation.source_units(self.notes,self.fields)
        with self.assertRaises(ValidationError):
            semantic.validate_facts(self.notes,units,{'facts':[raw]},scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
        notes=self.notes.replace('about 15 minutes','15 minutes')
        raw=fact(notes,self.fields,'wrong_duration','15',kind='measurement',concept='total physician time',
            unit='minutes',unit_quote='minutes')
        units,_=generation.source_units(notes,self.fields)
        facts=semantic.validate_facts(notes,units,{'facts':[raw]},scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
        answers=self.assign(assignments(self.fields,{'cell_16':['wrong_duration']}),facts=facts,notes=notes)
        self.assertEqual(answers['cell_16']['text'],'')
        self.assertTrue(any('not explicitly documented physician time' in r for r in answers['cell_16']['review_reasons']))

    def test_new_validation_is_not_tied_to_patient_name_score_or_investigation(self):
        # Rebind exact references on a different synthetic source. These are
        # local fixture variations, never new provider output provenance.
        notes=self.notes.replace('Synthetic Nadia Fenwick','Synthetic Avery Quinn').replace('SYN-NF-1017','SYN-AQ-2208')
        notes=notes.replace('5 out of 10','7 out of 10').replace('ultrasound','MRI')
        def edit(raw):
            for row in raw['facts']:
                for ref in (row['value_span'],row['subject']['name_span']):
                    if ref:
                        ref['quote']=ref['quote'].replace('Synthetic Nadia Fenwick','Synthetic Avery Quinn')
                        ref['quote']=ref['quote'].replace('SYN-NF-1017','SYN-AQ-2208').replace('5 out of 10','7 out of 10').replace('ultrasound','MRI')
                if row['id']=='f12':row['value_span']['quote']='7'
        facts=self.facts(notes=notes,edit=edit)
        self.assertFalse(any(f['issues'] for f in facts.values()))
        answers=self.assign(facts=facts,notes=notes)
        self.assertEqual(answers['cell_0']['text'],'Synthetic Avery Quinn')
        self.assertEqual(answers['cell_7']['text'],'7 out of 10')
        self.assertIn('MRI was not performed today',answers['cell_15']['text'])
