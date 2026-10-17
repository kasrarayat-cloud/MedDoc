"""Retained v16 bytes and constructed v17 supporting-fact proposals."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from django.test import SimpleTestCase
from core import generation,semantic_generation as semantic
from core.tests import test_clinical_context_generation as legacy
from core.tests.test_clinical_context_generation import digest
from core.tests.test_semantic_generation import checker,inventory_api_facts

FIXTURES=Path(__file__).with_name('fixtures')
V17=semantic.SUPPORT_CLOSURE_SCOPE_CONTRACT


class SupportClosureGenerationTests(SimpleTestCase):
    raw=legacy.ClinicalContextGenerationTests.raw
    rebase=legacy.ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads((FIXTURES/'iris_support_closure_retained.json').read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}

    def prospective(self):
        # Retained extractor facts stay exact. Only this proposal/checker is
        # constructed offline; v17 never rewrites the original annotation.
        raw=self.raw()
        proposal=deepcopy(self.responses['assigner',1])
        for row in proposal['fields']:
            if row['key'] in ('cell_4','cell_17'):row['fact_ids']=['f5','f7','f8','f9']
            if row['fact_ids']:row['status']='supported'
        return raw,proposal

    def run_case(self,*,notes=None,raw=None,proposal=None,definitions=None,repair=None):
        notes=self.notes if notes is None else notes
        base_raw,base_proposal=self.prospective();raw=base_raw if raw is None else raw
        proposal=base_proposal if proposal is None else proposal
        units,_=generation.source_units(notes,self.fields)
        extraction=inventory_api_facts(notes,units,raw['facts']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt,payload))
            self.assertTrue(instructions.endswith(semantic.SUPPORT_CLOSURE_INSTRUCTIONS))
            self.assertIn('stable_state_inventory',payload)
            if role=='extractor':return deepcopy(extraction)
            self.assertIn('shared_predicate_options',payload)
            current=repair if repair is not None and attempt==2 else proposal
            if role=='checker':return checker(current)
            return deepcopy(current) if attempt==1 else {'fields':[r for r in current['fields'] if r['key'] in payload['repair_keys']]}
        answers=semantic.run(notes,self.fields,definitions or self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V17)
        return answers,calls

    def changed(self,old,new,values):
        notes=self.notes.replace(old,new);self.assertNotEqual(notes,self.notes)
        raw=self.rebase(notes);next(f for f in raw['facts'] if f['id']=='f8')['polarity']='affirmed'
        units,_=generation.source_units(notes,self.fields)
        for identity,quote in values.items():
            fact=next(f for f in raw['facts'] if f['id']==identity);start=notes.index(quote)
            fact['value_span']={'start':start,'end':start+len(quote)}
            refs=[fact['value_span'],fact['subject']['name_span'],fact['timing']['span'],fact['unit_span']]
            fact['source_unit_ids']=sorted({u['id'] for u in units for ref in refs if ref and u['start']<=ref['start']<ref['end']<=u['end']})
        return notes,raw

    def held(self,answer):
        self.assertIn(answer['status'],('ambiguous','conflict'),answer['review_reasons'])
        self.assertEqual(answer['text'],'');self.assertFalse(answer['reviewed'])

    def test_actual_v16_iris_and_successful_elias_requests_and_answers_replay_exactly(self):
        for name,count in [('iris',{'supported':27,'ambiguous':4,'missing':3}),('elias',{'supported':18,'missing':2})]:
            case=json.loads((FIXTURES/(name+'_support_closure_retained.json')).read_text());calls=[]
            def send(role,attempt,payload,schema,instructions):
                row=next(r for r in case['stages'] if (r['stage'],r['attempt'])==(role,attempt));calls.append((role,attempt))
                self.assertNotIn('stable_state_inventory',payload)
                self.assertNotIn('shared_predicate_options',payload)
                self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
                return deepcopy(row['output'])
            answers=semantic.run(case['notes'],case['fields'],case['definitions'],send,
                reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.MIXED_OBSERVATION_SCOPE_CONTRACT)
            with self.subTest(name=name):
                self.assertEqual(digest(answers),case['saved_answers_sha256'])
                self.assertEqual(Counter(a['status'] for a in answers.values()),count)
                self.assertEqual(len(calls),5)

    def test_complete_constructed_extraction_and_assignments_preserve_all_approved_content(self):
        answers,calls=self.run_case()
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':31,'missing':3},
            {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})
        self.assertEqual(len(calls),3)
        for key in ('cell_4','cell_17'):self.assertIn('Swallowing and appetite are unchanged',answers[key]['text'])
        self.assertEqual(answers['cell_11']['text'],'Does not use alcohol')
        self.assertEqual(answers['cell_12']['text'],'Does not use recreational drugs')
        options=calls[1][2]['shared_predicate_options']['cell_12'];self.assertEqual(len(options),1)
        self.assertTrue(options[0]['derived_from_shared_predicate'])
        self.assertEqual([s['quote'] for s in options[0]['source_spans']],['does not use ','recreational drugs'])
        self.assertEqual(next(f for f in answers['cell_12']['facts'] if f['id']=='f20')['value_evidence']['quote'],
            'does not use alcohol or recreational drugs')
        field=next(f for f in self.fields if f['key']=='cell_12')
        semantic.validate_stored_answer(self.notes,field,self.definitions['cell_12'],answers['cell_12'])

    def test_clipped_stability_and_missing_extraction_stay_held(self):
        raw,proposal=self.prospective()
        for absent in (False,True):
            changed=deepcopy(raw);selection=deepcopy(proposal)
            if absent:
                changed['facts']=[f for f in changed['facts'] if f['id']!='f8']
                for row in selection['fields']:row['fact_ids']=[i for i in row['fact_ids'] if i!='f8']
            else:
                fact=next(f for f in changed['facts'] if f['id']=='f8')
                fact['value_span']['end']=fact['value_span']['start']+len('Swallowing')
            answers,_=self.run_case(raw=changed,proposal=selection)
            for key in ('cell_4','cell_17'):self.held(answers[key])

    def test_omission_requires_complete_selected_support_even_with_passing_checker(self):
        raw,proposal=self.prospective()
        for row in proposal['fields']:row['fact_ids']=[i for i in row['fact_ids'] if i!='f8']
        answers,_=self.run_case(raw=raw,proposal=proposal)
        for key in ('cell_4','cell_17'):
            self.held(answers[key]);self.assertTrue(any('documented current state' in r for r in answers[key]['review_reasons']))
        _,complete=self.prospective();answers,calls=self.run_case(raw=raw,proposal=proposal,repair=complete)
        self.assertEqual(len(calls),5)
        for key in ('cell_4','cell_17'):self.assertEqual(answers[key]['status'],'supported')

    def test_unfamiliar_stability_objects_and_definition_preserve_state_not_normality(self):
        old='Swallowing and appetite are unchanged';new='Sleep and energy remain stable'
        notes,raw=self.changed(old,new,{'f8':new});definitions=deepcopy(self.definitions)
        definitions['cell_17']['meaning']='Documented sleep and energy symptoms and current state.'
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions)
        for key in ('cell_4','cell_17'):
            self.assertEqual(answers[key]['status'],'supported',answers[key]['review_reasons'])
            self.assertIn(new,answers[key]['text']);self.assertNotIn('normal',answers[key]['text'])
        new='Severe abdominal pain remains unchanged'
        notes,raw=self.changed(old,new,{'f8':new})
        for polarity in ('affirmed','negated'):
            next(f for f in raw['facts'] if f['id']=='f8')['polarity']=polarity
            answers,_=self.run_case(notes=notes,raw=raw)
            for key in ('cell_4','cell_17'):
                self.assertEqual(answers[key]['status'],'supported',answers[key]['review_reasons'])
                self.assertIn(new,answers[key]['text']);self.assertNotIn('normal',answers[key]['text'])

    def test_stability_cannot_drop_qualification_or_change_owner_day_or_polarity(self):
        old='Swallowing and appetite are unchanged'
        for new in ('Swallowing and appetite are unchanged according to an unverified report',
                'Swallowing and appetite are unchanged except during meals',
                'Swallowing and appetite are unchanged today but were worse yesterday'):
            notes,raw=self.changed(old,new,{'f8':old});answers,_=self.run_case(notes=notes,raw=raw)
            for key in ('cell_4','cell_17'):self.held(answers[key])
        for prefix in ("Mother's history:\n\n",'Previous encounter:\n\n'):
            notes,raw=self.changed(old,prefix+old,{'f8':old});answers,_=self.run_case(notes=notes,raw=raw)
            for key in ('cell_4','cell_17'):self.held(answers[key])
        for polarity in ('negative','positive'):
            definitions=deepcopy(self.definitions);definitions['cell_17']['scope']['polarity']=polarity
            raw,proposal=self.prospective()
            next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids']=['f8']
            self.held(self.run_case(raw=raw,proposal=proposal,definitions=definitions)[0]['cell_17'])
        definitions=deepcopy(self.definitions);definitions['cell_17']['meaning']='Documented absence of swallowing or appetite symptoms.'
        self.held(self.run_case(definitions=definitions)[0]['cell_17'])

    def test_excluded_state_objects_do_not_create_narrative_permission_or_obligation(self):
        raw,proposal=self.prospective()
        next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids']=['f8']
        for meaning in ('Documented current symptoms excluding swallowing and appetite.',
                'Documented current symptoms other than swallowing and appetite.',
                'Documented current symptoms apart from swallowing and appetite.',
                'Swallowing and appetite are excluded from the documented current symptoms.',
                'Except for swallowing and appetite, document current symptoms.'):
            definitions=deepcopy(self.definitions);definitions['cell_17']['meaning']=meaning
            answers,calls=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
            with self.subTest(meaning=meaning):
                self.held(answers['cell_17'])
                self.assertFalse(any(r['field_key']=='cell_17' for r in calls[0][2]['stable_state_inventory']))

    def test_current_shared_absence_accepts_unspecified_but_not_past_or_future_annotation(self):
        for timing in ('current','unspecified','past','future'):
            raw,_=self.prospective()
            for f in raw['facts']:
                if f['id'] in ('f19','f20'):f['timing']['kind']=timing
            answers,_=self.run_case(raw=raw)
            for key in ('cell_11','cell_12'):
                if timing in ('current','unspecified'):self.assertEqual(answers[key]['status'],'supported',answers[key]['review_reasons'])
                else:self.held(answers[key])

    def test_specific_stability_topic_requires_complete_scope_but_omission_stays_held(self):
        definitions=deepcopy(self.definitions)
        definitions['cell_17']['meaning']='Documented appetite symptoms and current state.'
        for selected in (['f8'],['f5']):
            raw,proposal=self.prospective()
            next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids']=selected
            answers,calls=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
            self.held(answers['cell_17'])
            self.assertTrue(any(r['field_key']=='cell_17' for r in calls[0][2]['stable_state_inventory']))
        definitions['cell_17']['meaning']='Documented current symptoms excluding swallowing and appetite.'
        answers,calls=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
        self.assertEqual(answers['cell_17']['status'],'supported',answers['cell_17']['review_reasons'])
        self.assertFalse(any(r['field_key']=='cell_17' for r in calls[0][2]['stable_state_inventory']))

    def test_shared_frequency_is_retained_and_clipped_first_object_stays_held(self):
        old='She has never smoked and does not use alcohol or recreational drugs'
        for qualifier in ('every weekend','more than once a month','currently','often'):
            new=old+' '+qualifier
            notes,raw=self.changed(old,new,{'f20':'does not use alcohol or recreational drugs '+qualifier})
            answers,_=self.run_case(notes=notes,raw=raw)
            self.held(answers['cell_11'])
            self.assertEqual(answers['cell_12']['status'],'supported',answers['cell_12']['review_reasons'])
            self.assertEqual(answers['cell_12']['text'],'Does not use recreational drugs '+qualifier)

    def test_shared_projection_preserves_unfamiliar_objects_and_explicit_meaning(self):
        old='She has never smoked and does not use alcohol or recreational drugs'
        new='She has never smoked and does not consume coffee or herbal stimulants'
        notes,raw=self.changed(old,new,{'f19':'does not consume coffee','f20':'does not consume coffee or herbal stimulants'})
        definitions=deepcopy(self.definitions)
        definitions['cell_11']['meaning']='Documented coffee consumption including non-use.'
        definitions['cell_12']['meaning']='Documented herbal stimulant consumption including non-use.'
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions)
        self.assertEqual(answers['cell_11']['text'],'Does not consume coffee')
        self.assertEqual(answers['cell_12']['text'],'Does not consume herbal stimulants')

    def test_shared_object_scope_cannot_use_another_object_or_atomic_projection(self):
        raw,proposal=self.prospective()
        next(r for r in proposal['fields'] if r['key']=='cell_12')['fact_ids']=['f19']
        self.held(self.run_case(raw=raw,proposal=proposal)[0]['cell_12'])
        definitions=deepcopy(self.definitions);definitions['cell_12']['answer_mode']='atomic'
        answers,calls=self.run_case(definitions=definitions)
        self.held(answers['cell_12']);self.assertNotIn('cell_12',calls[1][2]['shared_predicate_options'])
        definitions=deepcopy(self.definitions)
        definitions['cell_12']['meaning']='Documented recreational drug use only, excluding alcohol.'
        self.held(self.run_case(definitions=definitions)[0]['cell_12'])
        definitions['cell_12']['meaning']='Documented recreational drug use only.'
        self.assertEqual(self.run_case(definitions=definitions)[0]['cell_12']['text'],'Does not use recreational drugs')

    def test_excluded_mentions_do_not_become_the_requested_shared_object(self):
        meanings=['Documented non-prescription medicine use other than recreational drugs.',
            'Documented non-prescription medicine use apart from recreational drugs.',
            'Documented non-prescription medicine use except for recreational drugs.',
            'Recreational drugs are excluded from documented medicine use.',
            'Documented alcohol history, with recreational drug use omitted.',
            'Except for recreational drugs, document non-prescription medicine use.']
        for meaning in meanings:
            definitions=deepcopy(self.definitions);definitions['cell_12']['meaning']=meaning
            answers,calls=self.run_case(definitions=definitions)
            with self.subTest(meaning=meaning):
                self.held(answers['cell_12'])
                self.assertEqual(calls[1][2]['shared_predicate_options']['cell_12'],[])

    def test_foreign_historical_qualified_or_changed_predicate_never_projects(self):
        old='She has never smoked and does not use alcohol or recreational drugs'
        for new in ("Mother's history:\n\n"+old,'Previous encounter:\n\n'+old,
                old+' according to an unverified report',old+' except on weekends',
                old+' but uses opioids',old+' and drinks wine'):
            notes,raw=self.changed(old,new,{'f19':'does not use alcohol','f20':'does not use alcohol or recreational drugs'})
            answers,calls=self.run_case(notes=notes,raw=raw)
            for key in ('cell_11','cell_12'):self.held(answers[key])
            self.assertEqual(calls[1][2]['shared_predicate_options']['cell_12'],[])

    def test_multiple_requested_objects_preserve_full_negative_source(self):
        definitions=deepcopy(self.definitions)
        definitions['cell_12']['meaning']='Documented alcohol or recreational drug use including documented absence.'
        answers,calls=self.run_case(definitions=definitions)
        self.assertEqual(answers['cell_12']['text'],'Does not use alcohol or recreational drugs')
        self.assertEqual(calls[1][2]['shared_predicate_options']['cell_12'],[])
