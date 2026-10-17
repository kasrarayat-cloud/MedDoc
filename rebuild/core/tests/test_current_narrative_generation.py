"""Actual held v15 replies and explicitly constructed prospective v16 proposals."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.tests import test_clinical_context_generation as legacy
from core.tests.test_clinical_context_generation import digest
from core.tests.test_semantic_generation import checker, inventory_api_facts

FIXTURE=Path(__file__).with_name('fixtures')/'iris_current_narrative_retained.json'
V16=semantic.MIXED_OBSERVATION_SCOPE_CONTRACT

class CurrentNarrativeGenerationTests(SimpleTestCase):
    raw=legacy.ClinicalContextGenerationTests.raw
    rebase=legacy.ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads(FIXTURE.read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}

    def complete_proposal(self):
        raw=self.raw();proposal=deepcopy(self.responses['assigner',1])
        def set_value(fact,quote):
            start=self.notes.index(quote);fact['value_span']={'start':start,'end':start+len(quote)}
        # Constructed fresh-extraction alternatives; these are NOT repaired
        # provider output and never become runtime-authored facts.
        set_value(next(f for f in raw['facts'] if f['id']=='f21'),'reviewed and reconciled')
        orientation=deepcopy(next(f for f in raw['facts'] if f['id']=='f29'))
        orientation.update(id='f54',concept='orientation');set_value(orientation,'oriented')
        raw['facts'].append(orientation)
        activities=deepcopy(next(f for f in raw['facts'] if f['id']=='f51'))
        activities.update(id='f55',concept='included_physician_activities')
        set_value(activities,'four minutes reviewing the chart before the visit, 22 minutes directly with the patient obtaining history, examining and counseling her, and six minutes entering orders and documenting the visit')
        raw['facts'].append(activities)
        next(r for r in proposal['fields'] if r['key']=='cell_26')['fact_ids']=['f54','f36']
        next(r for r in proposal['fields'] if r['key']=='cell_33')['fact_ids']=['f55']
        return raw,proposal

    def run_case(self,*,notes=None,raw=None,proposal=None,definitions=None,checks=None):
        notes=self.notes if notes is None else notes
        raw=raw or self.raw();proposal=proposal or deepcopy(self.responses['assigner',1])
        units,_=generation.source_units(notes,self.fields)
        extraction=inventory_api_facts(notes,units,raw['facts']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertIn('medication_antecedent_inventory',payload)
            self.assertIn('atomic_status_inventory',payload)
            if role=='extractor':return deepcopy(extraction)
            if role=='checker':return checker(proposal,verdicts=checks)
            return deepcopy(proposal) if attempt==1 else {'fields':[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]}
        answers=semantic.run(notes,self.fields,definitions or self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V16)
        return answers,calls

    def changed_source(self,old,new,values):
        notes=self.notes.replace(old,new);self.assertNotEqual(notes,self.notes)
        raw=self.rebase(notes)
        units,_=generation.source_units(notes,self.fields)
        for identity,quote in values.items():
            fact=next(f for f in raw['facts'] if f['id']==identity)
            start=notes.index(quote)
            fact['value_span']={'start':start,'end':start+len(quote)}
            # Rebind every explicit annotation, including the complete value,
            # so a scope refusal cannot accidentally be a stale-span refusal.
            refs=[fact['value_span'],fact['subject']['name_span'],fact['timing']['span'],fact['unit_span']]
            fact['source_unit_ids']=sorted({u['id'] for u in units for ref in refs if ref and u['start']<=ref['start']<ref['end']<=u['end']})
        return notes,raw

    def test_retained_v15_all_requests_and_actual_held_answers_replay_exactly(self):
        self.assertEqual(digest(self.notes),self.case['provenance']['source_sha256']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            row=next(r for r in self.case['stages'] if (r['stage'],r['attempt'])==(role,attempt))
            calls.append((role,attempt))
            self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
            return deepcopy(row['output'])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.CLINICAL_CONTEXT_SCOPE_CONTRACT)
        self.assertEqual(digest(answers),self.case['saved_answers_sha256'])
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':23,'conflict':6,'ambiguous':2,'missing':3})
        self.assertEqual(len(calls),5)

    def test_constructed_complete_extraction_preserves_approved_content(self):
        raw,proposal=self.complete_proposal();answers,calls=self.run_case(raw=raw,proposal=proposal)
        failures={k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')}
        self.assertEqual(failures,{})
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':31,'missing':3})
        self.assertEqual(len(calls),3)
        self.assertIn('trial of an over-the-counter antacid ended last month',answers['cell_8']['text'])
        self.assertIn('no longer taking that antacid',answers['cell_8']['text'])
        self.assertEqual(answers['cell_9']['text'],'Reviewed and reconciled')
        self.assertEqual(answers['cell_10']['text'],'She has never smoked')
        self.assertEqual(answers['cell_11']['text'],'Does not use alcohol')
        self.assertNotIn('distress',answers['cell_26']['text'])
        self.assertNotIn('exclude',answers['cell_33']['text'])
        self.assertNotIn('selection',answers['cell_33']['text'])
        facts={f['id']:f for f in answers['cell_8']['facts']}
        self.assertEqual(facts['f18']['timing']['kind'],'past')
        self.assertEqual(facts['f19']['timing']['kind'],'current')

    def test_missing_atomic_status_stays_held_with_passing_checker(self):
        answers,_=self.run_case()
        self.assertEqual(answers['cell_9']['status'],'conflict')
        self.assertEqual(answers['cell_9']['text'],'')

    def test_absent_required_status_atom_is_an_extraction_gap(self):
        raw,proposal=self.complete_proposal();raw['facts']=[f for f in raw['facts'] if f['id']!='f21']
        next(r for r in proposal['fields'] if r['key']=='cell_9').update(fact_ids=[],status='missing')
        answers,_=self.run_case(raw=raw,proposal=proposal)
        # The independent checker can classify an empty extraction gap as
        # ambiguous; either held status must remain distinct from undocumented.
        self.assertIn(answers['cell_9']['status'],('conflict','ambiguous'))
        self.assertEqual(answers['cell_9']['text'],'')
        self.assertTrue(any('requested atomic status' in reason for reason in answers['cell_9']['review_reasons']))

    def test_status_completeness_requires_relevant_current_owned_source(self):
        old='Medications were reviewed and reconciled in the EHR today'
        variants=[('',None),
            ('Allergies were reviewed and reconciled in the EHR today',None),
            ("Mother's history:\n\n"+old,None),('Previous encounter:\n\n'+old,None),
            ('Medications were reviewed and reconciled yesterday',None),
            ('Medication records of her mother were reviewed and reconciled today',None),
            (old,'Documented status of allergy review and reconciliation in the EHR.')]
        for source,meaning in variants:
            notes=self.notes.replace(old+'.',source+'.' if source else '')
            original=self.responses;self.responses=deepcopy(original)
            self.responses['extractor',1]['facts']=[f for f in self.responses['extractor',1]['facts'] if f['id']!='f21']
            try:raw=self.rebase(notes)
            finally:self.responses=original
            proposal=deepcopy(self.responses['assigner',1])
            next(r for r in proposal['fields'] if r['key']=='cell_9').update(fact_ids=[],status='missing')
            definitions=deepcopy(self.definitions)
            if meaning:definitions['cell_9']['meaning']=meaning
            answers,_=self.run_case(notes=notes,raw=raw,proposal=proposal,definitions=definitions)
            with self.subTest(source=source,meaning=meaning):self.assertEqual(answers['cell_9']['status'],'missing',answers['cell_9']['review_reasons'])

    def test_status_predicate_qualification_cannot_be_clipped(self):
        old='Medications were reviewed and reconciled in the EHR today'
        source='Medication records were reviewed and reconciled only in part in the electronic health record today'
        notes,raw=self.changed_source(old,source,{'f21':'reviewed and reconciled'})
        answers,_=self.run_case(notes=notes,raw=raw)
        self.assertEqual(answers['cell_9']['status'],'conflict')
        self.assertTrue(any('only in part' in reason for reason in answers['cell_9']['review_reasons']))

    def test_unfamiliar_explicit_status_wording_retains_its_extracted_atom(self):
        old='Medications were reviewed and reconciled in the EHR today'
        source='Medication records have been reviewed and reconciled in the electronic health record today'
        notes,raw=self.changed_source(old,source,{'f21':'reviewed and reconciled'})
        answers,_=self.run_case(notes=notes,raw=raw)
        self.assertEqual(answers['cell_9']['status'],'supported',answers['cell_9']['review_reasons'])
        self.assertEqual(answers['cell_9']['text'],'Reviewed and reconciled')

    def test_missing_orientation_and_whole_general_substitution_stay_held(self):
        raw,proposal=self.complete_proposal()
        for ids in (['f36'],['f29','f36']):
            changed=deepcopy(proposal)
            next(r for r in changed['fields'] if r['key']=='cell_26')['fact_ids']=ids
            answers,_=self.run_case(raw=raw,proposal=changed)
            with self.subTest(ids=ids):
                self.assertEqual(answers['cell_26']['status'],'conflict')
                self.assertEqual(answers['cell_26']['text'],'')

    def test_narrow_orientation_scope_retains_component_without_general_observation(self):
        raw,proposal=self.complete_proposal();definitions=deepcopy(self.definitions)
        definitions['cell_26']['meaning']='Neurologic examination findings (orientation only).'
        for ids,expected in ((['f54'],True),(['f29'],False),(['f36'],False)):
            changed=deepcopy(proposal)
            next(r for r in changed['fields'] if r['key']=='cell_26')['fact_ids']=ids
            answers,_=self.run_case(raw=raw,proposal=changed,definitions=definitions)
            with self.subTest(ids=ids):self.assertEqual(answers['cell_26']['status']=='supported',expected,answers['cell_26']['review_reasons'])

    def test_complete_mixed_regional_observations_preserve_literals(self):
        raw,proposal=self.complete_proposal()
        for fact in raw['facts']:
            if fact['id'] in ('f29','f31','f33','f34','f35','f36'):fact['polarity']='mixed'
        answers,_=self.run_case(raw=raw,proposal=proposal)
        for key in ('cell_19','cell_21','cell_23','cell_24','cell_25','cell_26'):
            self.assertEqual(answers[key]['status'],'supported',(key,answers[key]['review_reasons']))

    def test_reported_absence_unfamiliar_words_preserve_full_predicate(self):
        old=next(f['value_span']['quote'] for f in self.responses['extractor',1]['facts'] if f['id']=='f14')
        for new in ('The patient denies chest discomfort or breathlessness','She denies chills',
                'She reports no chills, wheezes or crackles','She denies nausea, vomiting, or bleeding'):
            notes,raw=self.changed_source(old,new,{'f14':new})
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(new=new):
                self.assertEqual(answers['cell_4']['status'],'supported')
                self.assertIn(new,answers['cell_4']['text'])

    def test_reported_absence_cannot_hide_predicate_shift_or_qualification(self):
        old=next(f['value_span']['quote'] for f in self.responses['extractor',1]['facts'] if f['id']=='f14')
        variants=['She reports no nausea and has fever','She reports no nausea except after meals',
            'She reports no nausea tomorrow','She reports no nausea and Morgan has fever',
            'She reports no absence of nausea','She denies not having nausea',
            'She reports no fever and experiences chest pain','She denies fever and endorses nausea',
            'She reports no fever and feels unwell','She reports no fever or experiences chest pain',
            'She reports no fever, experiences chest pain','She denies fever, endorses nausea',
            'She reports no fever, feels unwell','She reports no nausea despite ongoing vomiting',
            'She denies fever, yet feels nauseated','She reports no nausea, vomiting occurs daily',
            'She reports no nausea, vomiting occurs','She reports no nausea or developed vomiting']
        for new in variants:
            notes,raw=self.changed_source(old,new,{'f14':new})
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(new=new):self.assertNotEqual(answers['cell_4']['status'],'supported')

    def test_negative_only_destination_cannot_accept_mixed_reported_predicates(self):
        old=next(f['value_span']['quote'] for f in self.responses['extractor',1]['facts'] if f['id']=='f14')
        variants=[('She reports no fever, nausea or vomiting',True),
            ('She reports no fever and experiences chest pain',False),
            ('She denies fever and endorses nausea',False),('She reports no fever and feels unwell',False),
            ('She reports no fever, experiences chest pain',False),('She denies fever, endorses nausea',False),
            ('She reports no fever, feels unwell',False)]
        for new,supported in variants:
            notes,raw=self.changed_source(old,new,{'f14':new});definitions=deepcopy(self.definitions)
            definitions['cell_17']['meaning']='Documented absent symptoms at this encounter.'
            definitions['cell_17']['scope']['polarity']='negative'
            proposal=deepcopy(self.responses['assigner',1])
            next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids']=['f14']
            answers,_=self.run_case(notes=notes,raw=raw,proposal=proposal,definitions=definitions)
            with self.subTest(new=new):self.assertEqual(answers['cell_17']['status']=='supported',supported)

    def test_lifetime_absence_keeps_historical_fact_metadata(self):
        old='She has never had abdominal surgery';new='They have never undergone knee surgery'
        notes,raw=self.changed_source(old,new,{'f16':new})
        answers,_=self.run_case(notes=notes,raw=raw)
        self.assertEqual(answers['cell_6']['status'],'supported')
        self.assertEqual(next(f for f in answers['cell_6']['facts'] if f['id']=='f16')['timing']['kind'],'past')

    def test_lifetime_negative_cannot_absorb_positive_predicate(self):
        old='She has never had abdominal surgery'
        for new in ('She has never smoked and drinks alcohol','She has never smoked, drinks alcohol',
                'She has never had abdominal surgery, drinks alcohol',
                'She has never had abdominal surgery despite a prior appendectomy'):
            notes,raw=self.changed_source(old,new,{'f16':new})
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(new=new):self.assertNotEqual(answers['cell_6']['status'],'supported')

    def test_social_partial_cannot_drop_qualifiers_or_bare_predicate(self):
        old='She has never smoked and does not use alcohol or recreational drugs'
        variants=[('She has never smoked and does not use alcohol except at celebrations','does not use alcohol'),
            ('She has never smoked and does not use alcohol or recreational drugs currently','does not use alcohol'),
            *[(old+' '+qualifier,'does not use alcohol') for qualifier in ('every weekend','each weekend','more than once a month','often')],
            (old,'alcohol'),(old,'does not use')]
        for new,selected in variants:
            notes=self.notes if new==old else self.notes.replace(old,new)
            raw=self.raw() if new==old else self.rebase(notes)
            fact=next(f for f in raw['facts'] if f['id']=='f23');start=notes.index(selected)
            fact['value_span']={'start':start,'end':start+len(selected)}
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(new=new,selected=selected):self.assertNotEqual(answers['cell_11']['status'],'supported')

    def test_complete_social_predicate_retains_documented_frequency(self):
        old='She has never smoked and does not use alcohol or recreational drugs'
        for qualifier in ('every weekend','each weekend','more than once a month','often','currently'):
            new=old+' '+qualifier;selected='does not use alcohol or recreational drugs '+qualifier
            notes,raw=self.changed_source(old,new,{'f23':selected,'f24':selected})
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(qualifier=qualifier):
                self.assertEqual(answers['cell_11']['status'],'supported',answers['cell_11']['review_reasons'])
                self.assertIn(qualifier,answers['cell_11']['text'])

    def test_current_cessation_requires_selected_unique_historical_antecedent(self):
        raw,proposal=self.complete_proposal()
        for omitted in ('f18','f19'):
            changed=deepcopy(proposal)
            row=next(r for r in changed['fields'] if r['key']=='cell_8')
            row['fact_ids']=[i for i in row['fact_ids'] if i!=omitted]
            answers,_=self.run_case(raw=raw,proposal=changed)
            self.assertNotEqual(answers['cell_8']['status'],'supported')
            self.assertEqual(answers['cell_8']['text'],'')

    def test_unrelated_past_care_does_not_gain_current_medication_scope(self):
        raw,proposal=self.complete_proposal()
        next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids'].append('f15')
        answers,_=self.run_case(raw=raw,proposal=proposal)
        self.assertEqual(answers['cell_8']['status'],'conflict')

    def test_unique_unfamiliar_trial_remains_past_supporting_current_cessation(self):
        old='A two-week trial of an over-the-counter antacid ended last month; she is no longer taking that antacid'
        prior='A short trial with magnesium finished last week';current='she is no longer using that medicine'
        notes,raw=self.changed_source(old,prior+'; '+current,{'f18':prior,'f19':current})
        timing=next(f for f in raw['facts'] if f['id']=='f18')['timing'];start=notes.index('last week')
        timing['span']={'start':start,'end':start+len('last week')}
        answers,_=self.run_case(notes=notes,raw=raw)
        self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
        self.assertIn(prior,answers['cell_8']['text']);self.assertIn(current.casefold(),answers['cell_8']['text'].casefold())

    def test_ambiguous_or_unlinked_trial_cannot_enter_current_medications(self):
        old='A two-week trial of an over-the-counter antacid ended last month; she is no longer taking that antacid'
        cases=[('A trial of antacid and psyllium ended last month','she is no longer taking that medicine'),
            ('A two-week trial of an over-the-counter antacid ended last month','she is no longer taking antacid'),
            ('A two-week trial of an over-the-counter antacid ended last month','she was no longer taking that antacid'),
            ('A two-week trial of an over-the-counter antacid ended last month','she will no longer be taking that antacid'),
            ('A two-week trial of an over-the-counter antacid ended last month','her mother is no longer taking that antacid')]
        for prior,current in cases:
            notes,raw=self.changed_source(old,prior+'; '+current,{'f18':prior,'f19':current})
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(current=current,prior=prior):self.assertNotEqual(answers['cell_8']['status'],'supported')

    def test_new_literals_and_antecedent_require_current_patient_source_section(self):
        examples=[('She has never had abdominal surgery','cell_6'),
            ('A two-week trial of an over-the-counter antacid ended last month; she is no longer taking that antacid','cell_8')]
        for source,key in examples:
            for heading in ("Mother's history:",'Previous encounter:','Hypothetical example:'):
                values=({'f16':source} if key=='cell_6' else dict(zip(('f18','f19'),source.split('; '))))
                notes,raw=self.changed_source(source,heading+'\n\n'+source,values)
                answers,_=self.run_case(notes=notes,raw=raw)
                with self.subTest(key=key,heading=heading):self.assertNotEqual(answers[key]['status'],'supported')
