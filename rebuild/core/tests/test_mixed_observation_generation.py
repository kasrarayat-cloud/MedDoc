"""Retained fresh v15 failure; prospective proposals are constructed offline."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.tests import test_clinical_context_generation as legacy
from core.tests.test_clinical_context_generation import digest
from core.tests.test_semantic_generation import checker, inventory_api_facts

FIXTURE=Path(__file__).with_name('fixtures')/'elias_mixed_observation_retained.json'
V16=semantic.MIXED_OBSERVATION_SCOPE_CONTRACT

class MixedObservationGenerationTests(SimpleTestCase):
    raw=legacy.ClinicalContextGenerationTests.raw
    rebase=legacy.ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads(FIXTURE.read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}
        self.observation=next(f['value_span']['quote'] for f in self.responses['extractor',1]['facts'] if f['id']=='f22')

    def proposal(self):
        proposal=deepcopy(self.responses['assigner',1])
        next(r for r in proposal['fields'] if r['key']=='cell_12').update(status='supported',fact_ids=['f21','f22'])
        return proposal

    def run_case(self,*,notes=None,raw=None,proposal=None,definitions=None,fields=None):
        notes=self.notes if notes is None else notes
        fields=fields or self.fields
        units,_=generation.source_units(notes,fields)
        extraction=inventory_api_facts(notes,units,(raw or self.raw())['facts'])
        proposal=proposal or self.proposal();calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertIn('mixed_observation_inventory',payload)
            self.assertTrue(instructions.endswith(semantic.MIXED_OBSERVATION_INSTRUCTIONS))
            self.assertNotIn('Other uses of mixed are held.',instructions)
            if role=='extractor':return deepcopy(extraction)
            if role=='checker':return checker(proposal)
            return deepcopy(proposal) if attempt==1 else {'fields':[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]}
        return semantic.run(notes,fields,definitions or self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V16),calls

    def assert_held(self,answers,key='cell_12'):
        self.assertNotEqual(answers[key]['status'],'supported')
        self.assertEqual(answers[key]['text'],'')
        self.assertFalse(answers[key]['reviewed'])

    def test_retained_v15_all_five_requests_and_final_failure_replay_exactly(self):
        self.assertEqual(digest(self.notes),self.case['provenance']['source_sha256']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            row=next(r for r in self.case['stages'] if (r['stage'],r['attempt'])==(role,attempt))
            calls.append((role,attempt));self.assertNotIn('mixed_observation_inventory',payload)
            self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
            return deepcopy(row['output'])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.CLINICAL_CONTEXT_SCOPE_CONTRACT)
        self.assertEqual(digest(answers),self.case['saved_answers_sha256'])
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':17,'missing':2,'conflict':1})
        self.assertEqual(len(calls),5);self.assert_held(answers)

    def test_complete_current_observation_keeps_all_components(self):
        answers,calls=self.run_case()
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':18,'missing':2})
        self.assertEqual(len(calls),3);self.assertIn(self.observation,answers['cell_12']['text'])
        retained=next(f for f in answers['cell_12']['facts'] if f['id']=='f22')
        self.assertEqual((retained['polarity'],retained['issues']),('mixed',[]))
        semantic.validate_stored_answer(self.notes,next(f for f in self.fields if f['key']=='cell_12'),self.definitions['cell_12'],answers['cell_12'])

    def test_unfamiliar_anatomy_and_narrative_destination(self):
        replacement='His left wrist is mildly swollen, with preserved movement and no erythema or bruising'
        notes=self.notes.replace(self.observation,replacement).replace('Synthetic Elias Mercer','Synthetic Mara Voss')
        raw=self.rebase(notes);fields=deepcopy(self.fields);definitions=deepcopy(self.definitions);proposal=self.proposal()
        next(f for f in fields if f['key']=='cell_12').update(key='observed_findings',label='Findings recorded during examination')
        definition=definitions.pop('cell_12');definition['permitted_destination']['field_key']='observed_findings'
        definition['meaning']='Narrative examination findings and observations, retaining normal, present and absent findings.'
        definitions['observed_findings']=definition
        next(r for r in proposal['fields'] if r['key']=='cell_12')['key']='observed_findings'
        answers,_=self.run_case(notes=notes,raw=raw,proposal=proposal,definitions=definitions,fields=fields)
        self.assertEqual(answers['observed_findings']['status'],'supported')
        self.assertIn(replacement,answers['observed_findings']['text'])

    def test_omitted_or_clipped_observation_cannot_be_cleared_by_passing_checker(self):
        for quote in (None,'His abdomen is soft','no guarding or rebound',self.observation.removesuffix(' and no guarding or rebound')):
            raw=self.raw();proposal=self.proposal()
            if quote is None:
                raw['facts']=[f for f in raw['facts'] if f['id']!='f22']
                next(r for r in proposal['fields'] if r['key']=='cell_12')['fact_ids']=['f21']
            else:
                row=next(f for f in raw['facts'] if f['id']=='f22');start=self.notes.index(quote)
                row['value_span']={'start':start,'end':start+len(quote)}
            with self.subTest(quote=quote):self.assert_held(self.run_case(raw=raw,proposal=proposal)[0])

    def test_whole_observation_cannot_be_wholly_negated_or_uncertain(self):
        for polarity in ('negated','uncertain'):
            raw=self.raw();next(f for f in raw['facts'] if f['id']=='f22')['polarity']=polarity
            with self.subTest(polarity=polarity):self.assert_held(self.run_case(raw=raw)[0])

    def test_complete_literal_affirmed_observation_remains_supported(self):
        raw=self.raw();next(f for f in raw['facts'] if f['id']=='f22')['polarity']='affirmed'
        answers,_=self.run_case(raw=raw)
        self.assertEqual(answers['cell_12']['status'],'supported')
        self.assertIn(self.observation,answers['cell_12']['text'])

    def test_pure_negative_observation_does_not_invent_a_positive_component(self):
        replacement='His abdomen is without tenderness or guarding'
        notes=self.notes.replace(self.observation,replacement);raw=self.rebase(notes)
        next(f for f in raw['facts'] if f['id']=='f22')['polarity']='negated'
        answers,_=self.run_case(notes=notes,raw=raw)
        self.assertEqual(answers['cell_12']['status'],'supported',answers['cell_12']['review_reasons'])

    def test_plural_observation_objects_preserve_both_polarities(self):
        replacement='Her lungs are clear, with no wheezes or crackles'
        notes=self.notes.replace(self.observation,replacement)
        answers,_=self.run_case(notes=notes,raw=self.rebase(notes))
        self.assertEqual(answers['cell_12']['status'],'supported',answers['cell_12']['review_reasons'])
        self.assertIn(replacement,answers['cell_12']['text'])

    def test_attributed_observation_is_held_with_either_literal_polarity(self):
        replacement='His abdomen is soft, with mild tenderness and no guarding according to an unverified report'
        notes=self.notes.replace(self.observation,replacement)
        for polarity in ('affirmed','mixed'):
            raw=self.rebase(notes);next(f for f in raw['facts'] if f['id']=='f22')['polarity']=polarity
            with self.subTest(polarity=polarity):self.assert_held(self.run_case(notes=notes,raw=raw)[0])

    def test_other_person_or_encounter_and_uncertainty_remain_held(self):
        variants=["His mother's abdomen is soft, with mild tenderness and no guarding or rebound",
            'His abdomen is soft, but his mother has no guarding or rebound',
            'His abdomen is soft, while Morgan has no guarding or rebound',
            'His abdomen was soft, with mild tenderness and no guarding or rebound',
            'His abdomen is possibly soft, with mild tenderness and no guarding or rebound',
            'His abdomen is soft, with possible mild tenderness and no guarding or rebound',
            'His abdomen is soft, with mild tenderness and no guarding or rebound yesterday',
            'His abdomen is soft, with mild tenderness and no guarding or rebound tomorrow',
            'His abdomen is soft, with mild tenderness and no guarding or rebound assumed',
            'His abdomen is soft, with mild tenderness and no guarding according to an unverified report',
            'If his abdomen is soft, with mild tenderness and no guarding or rebound',
            'His abdomen is soft, with mild tenderness and no guarding or rebound?']
        for value in variants:
            notes=self.notes.replace(self.observation,value)
            with self.subTest(value=value):self.assert_held(self.run_case(notes=notes,raw=self.rebase(notes))[0])
        for heading in ("Mother's examination:",'Previous encounter:','Hypothetical example:'):
            notes=self.notes.replace(self.observation,heading+'\n\n'+self.observation)
            with self.subTest(heading=heading):self.assert_held(self.run_case(notes=notes,raw=self.rebase(notes))[0])

    def test_explicit_retraction_cannot_be_overridden_by_checker(self):
        notes=self.notes+'\n\nCorrection: The examination findings above belong to a different patient.'
        self.assert_held(self.run_case(notes=notes,raw=self.rebase(notes))[0])

    def test_approved_narrow_or_atomic_scope_does_not_acquire_composite_permission(self):
        variants=[{'answer_mode':'atomic'},{'meaning':'Physical examination: tenderness only.'},
            {'scope':{'subject':'patient','temporality':'current','polarity':'positive'}},
            {'scope':{'subject':'patient','temporality':'past','polarity':'any'}}]
        for change in variants:
            altered=deepcopy(self.definitions);altered['cell_12'].update(change)
            with self.subTest(change=change):self.assert_held(self.run_case(definitions=altered)[0])
