"""Retained v17 failures/successes and constructed prospective v18 proposals."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from django.test import SimpleTestCase
from core import generation,semantic_generation as semantic
from core.tests import test_clinical_context_generation as legacy
from core.tests.test_semantic_generation import checker,inventory_api_facts

FIXTURES=Path(__file__).with_name('fixtures')
V18=semantic.SOURCE_GOVERNANCE_SCOPE_CONTRACT
digest=legacy.digest


class SourceGovernanceGenerationTests(SimpleTestCase):
    raw=legacy.ClinicalContextGenerationTests.raw
    rebase=legacy.ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads((FIXTURES/'tessa_source_governance_retained.json').read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}

    def proposal(self):
        # Constructed assignment only; no provider result or saved answer changes.
        proposal=deepcopy(self.responses['assigner',1])
        next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids'].append('f43')
        next(r for r in proposal['fields'] if r['key']=='cell_18')['fact_ids'].insert(0,'f42')
        return proposal

    def complete(self):
        # A separately labelled prospective extraction control. The original
        # extractor's affirmative f26 is preserved and tested as a held defect.
        raw=self.raw();next(f for f in raw['facts'] if f['id']=='f26')['polarity']='negated'
        return raw,self.proposal()

    def run_case(self,*,notes=None,raw=None,proposal=None,definitions=None,repair=None):
        notes=self.notes if notes is None else notes
        raw=self.raw() if raw is None else raw
        proposal=self.proposal() if proposal is None else proposal
        units,_=generation.source_units(notes,self.fields)
        extraction=inventory_api_facts(notes,units,raw['facts']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt,payload))
            self.assertTrue(instructions.endswith(semantic.SOURCE_GOVERNANCE_INSTRUCTIONS))
            self.assertIn('source_governance_inventory',payload)
            if role=='extractor':return deepcopy(extraction)
            selected=repair if attempt==2 and repair is not None else proposal
            if role=='checker':return checker(selected)
            return deepcopy(selected) if attempt==1 else {'fields':[r for r in selected['fields'] if r['key'] in payload['repair_keys']]}
        return semantic.run(notes,self.fields,definitions or self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V18),calls

    def held(self,answer):
        self.assertIn(answer['status'],('ambiguous','conflict'),answer['review_reasons'])
        self.assertEqual(answer['text'],'');self.assertFalse(answer['reviewed'])

    def changed(self,old,new):
        notes=self.notes.replace(old,new);self.assertNotEqual(notes,self.notes)
        raw=self.rebase(notes);next(f for f in raw['facts'] if f['id']=='f26')['polarity']='negated'
        return notes,raw

    def test_actual_v17_failure_and_success_replay_requests_and_answers_exactly(self):
        for name,count in [('tessa',{'conflict':20,'ambiguous':2,'missing':2}),('iris',{'supported':31,'missing':3})]:
            case=json.loads((FIXTURES/(name+'_source_governance_retained.json')).read_text());calls=[]
            def send(role,attempt,payload,schema,instructions):
                row=next(r for r in case['stages'] if (r['stage'],r['attempt'])==(role,attempt));calls.append((role,attempt))
                self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
                return deepcopy(row['output'])
            answers=semantic.run(case['notes'],case['fields'],case['definitions'],send,
                reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.SUPPORT_CLOSURE_SCOPE_CONTRACT)
            self.assertEqual(digest(answers),case['saved_answers_sha256'])
            self.assertEqual(Counter(a['status'] for a in answers.values()),count)
            self.assertEqual(len(calls),len(case['stages']))

    def test_unchanged_retained_extraction_keeps_real_polarity_mismatch(self):
        answers,calls=self.run_case()
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':21,'conflict':1,'missing':2},
            {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})
        self.held(answers['cell_12'])
        self.assertTrue(any('negation' in issue for issue in answers['cell_12']['review_reasons']))
        self.assertEqual(len(calls),5)

    def test_complete_constructed_proposal_preserves_all_requested_qualifications(self):
        raw,proposal=self.complete();answers,calls=self.run_case(raw=raw,proposal=proposal)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':22,'missing':2},
            {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})
        self.assertEqual(len(calls),3)
        for key,quote in [('cell_4','no professional services'),('cell_12','no longer taking omeprazole'),
                ('cell_15','compared with the initial examination today'),('cell_16','not established diagnoses'),
                ('cell_20','if symptoms worsen'),('cell_21','preceding day')]:
            self.assertIn(quote,answers[key]['text'])
        self.assertNotIn('omeprazole',answers['cell_11']['text'])

    def test_real_denial_headings_and_retractions_remain_held(self):
        for prefix in ('The following findings are denied:\n','All of the following statements are false:\n',
                'The following is hypothetical:\n'):
            notes=prefix+self.notes;raw=self.rebase(notes)
            next(f for f in raw['facts'] if f['id']=='f26')['polarity']='negated'
            answers,_=self.run_case(notes=notes,raw=raw)
            for key in ('cell_5','cell_15','cell_21'):self.held(answers[key])

    def test_omitted_source_support_cannot_pass(self):
        for identity,key in [('f8','cell_4'),('f18','cell_8'),('f26','cell_12'),('f30','cell_10'),
                ('f36','cell_15'),('f39','cell_16'),('f42','cell_17'),('f46','cell_20'),('f50','cell_21')]:
            raw,proposal=self.complete();raw['facts']=[f for f in raw['facts'] if f['id']!=identity]
            for row in proposal['fields']:row['fact_ids']=[value for value in row['fact_ids'] if value!=identity]
            answers,_=self.run_case(raw=raw,proposal=proposal)
            with self.subTest(identity=identity):self.held(answers[key])

    def test_unfamiliar_medicine_pronoun_and_sentence_layout_preserve_scope(self):
        for old,new in [('omeprazole','pantoprazole'),
                ('She is no longer taking omeprazole','They are no longer taking omeprazole'),
                ('. The earlier family-medicine visit described below','.\nThe earlier family-medicine visit described below')]:
            notes,raw=self.changed(old,new);answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(new=new):
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':22,'missing':2},
                    {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})

    def test_current_nonuse_requires_explicit_historical_support_request(self):
        raw,proposal=self.complete();definitions=deepcopy(self.definitions)
        definitions['cell_12']['meaning']='Historical medicine trial, its dates, response and stopping reason only.'
        self.held(self.run_case(raw=raw,proposal=proposal,definitions=definitions)[0]['cell_12'])
        next(row for row in proposal['fields'] if row['key']=='cell_11')['fact_ids'].append('f26')
        self.held(self.run_case(raw=raw,proposal=proposal)[0]['cell_11'])
        next(row for row in proposal['fields'] if row['key']=='cell_11')['fact_ids']=['f21']
        self.held(self.run_case(raw=raw,proposal=proposal)[0]['cell_11'])

    def test_current_nonuse_cannot_be_requested_by_a_prohibition(self):
        for tail in ('Current non-use must not be included.','Current non-use is not requested.',
                'This field does not include current non-use.','Exclude current non-use.',
                'Current non-use is included only if independently verified.'):
            raw,proposal=self.complete();definitions=deepcopy(self.definitions)
            definitions['cell_12']['meaning']=('Stopped historical medicine before the target encounter: '
                'name, dose, route, frequency, trial dates, response, stopping reason and outcome after stopping. '+tail)
            with self.subTest(tail=tail):self.held(self.run_case(raw=raw,proposal=proposal,definitions=definitions)[0]['cell_12'])

    def test_independently_worded_history_definitions_and_renamed_destinations(self):
        for meaning in ("Previous medication trial and its outcome, including the medicine's documented current non-use.",
                'Describe the prior treatment course with its response and explicit current cessation.',
                'History of discontinued therapy, including current non-use of that therapy and outcome after stopping.',
                'Discontinued medication: dose, name, explicit current non-use and response.'):
            raw,proposal=self.complete();definitions=deepcopy(self.definitions)
            definitions['cell_12']['meaning']=meaning
            answers,_=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
            with self.subTest(meaning=meaning):
                self.assertEqual(answers['cell_12']['status'],'supported',answers['cell_12']['review_reasons'])
        raw,proposal=self.complete();original_fields=self.fields
        try:
            rename=lambda key:'independent_'+key
            self.fields=[{**f,'key':rename(f['key'])} for f in self.fields]
            definitions={rename(k):{**d,'permitted_destination':{**d['permitted_destination'],'field_key':rename(k)}} for k,d in definitions.items()}
            for row in proposal['fields']:row['key']=rename(row['key'])
            answers,_=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
            self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':22,'missing':2})
        finally:self.fields=original_fields

    def test_current_nonuse_requires_the_selected_same_medicine_antecedent(self):
        notes,raw=self.changed('She is no longer taking omeprazole','She is no longer taking loratadine')
        self.held(self.run_case(notes=notes,raw=raw)[0]['cell_12'])
        raw,proposal=self.complete()
        next(row for row in proposal['fields'] if row['key']=='cell_12')['fact_ids'].remove('f24')
        self.held(self.run_case(raw=raw,proposal=proposal)[0]['cell_12'])
        for old,new in [('She stopped omeprazole','Her mother stopped omeprazole'),
                ('She is no longer taking omeprazole','She is no longer taking omeprazole according to an unverified report')]:
            notes,raw=self.changed(old,new)
            with self.subTest(new=new):self.held(self.run_case(notes=notes,raw=raw)[0]['cell_12'])

    def test_whole_account_qualification_and_integrity_are_positioned(self):
        for prefix,suffix in [
                ('Disregard all of the following clinical statements.\n',''),
                ('All clinical statements below are unverified.\n',''),
                ('Previous encounter:\nThe following clinical statements are unverified.\n',''),
                ('','\nAll the above statements are false.'),
                ('','\nNone of the foregoing clinical statements are true.'),
                ('','\nNone of the above clinical statements are not false.'),
                ('','\nEverything documented above belongs to a different patient.'),
                ('','\nThe above clinical account is unverified.'),
                ('','\nThe above clinical account is subject to unresolved verification.')]:
            notes=prefix+self.notes+suffix;raw=self.rebase(notes)
            next(f for f in raw['facts'] if f['id']=='f26')['polarity']='negated'
            answers,_=self.run_case(notes=notes,raw=raw)
            for key in ('cell_5','cell_15','cell_21'):
                with self.subTest(prefix=prefix,suffix=suffix,key=key):self.held(answers[key])
        for prefix,suffix in [
                ('Do not disregard all of the following clinical statements.\n',''),
                ('','\nAll the above statements are not false.'),
                ('','\nThe above clinical account is verified.'),
                ('Previous encounter:\nThe following clinical statements are unverified.\nCurrent encounter:\n',''),
                ('','\nMother\'s history:\nThe above clinical account is unverified.'),
                ('','\nPrevious encounter:\nThe above clinical account is unverified.')]:
            notes=prefix+self.notes+suffix;raw=self.rebase(notes)
            next(f for f in raw['facts'] if f['id']=='f26')['polarity']='negated'
            answers,_=self.run_case(notes=notes,raw=raw)
            with self.subTest(prefix=prefix,suffix=suffix):
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':22,'missing':2},
                    {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})

    def test_actual_prior_successes_remain_supported_prospectively(self):
        for filename,count in [('iris_source_governance_retained.json',{'supported':31,'missing':3}),
                ('elias_support_closure_retained.json',{'supported':18,'missing':2}),
                ('nadia_source_governance_retained.json',{'supported':16,'missing':2})]:
            case=json.loads((FIXTURES/filename).read_text());calls=[]
            def send(role,attempt,payload,schema,instructions):
                row=next(r for r in case['stages'] if (r['stage'],r['attempt'])==(role,attempt));calls.append((role,attempt))
                return deepcopy(row['output'])
            answers=semantic.run(case['notes'],case['fields'],case['definitions'],send,
                reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V18)
            self.assertEqual(Counter(a['status'] for a in answers.values()),count,
                {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})
            self.assertEqual(len(calls),len(case['stages']))
            if 'saved_text_status' in case:
                self.assertEqual({k:{q:a[q] for q in ('text','status')} for k,a in answers.items()},case['saved_text_status'])

    def test_actual_nadia_v14_requests_and_saved_answers_remain_exact(self):
        case=json.loads((FIXTURES/'nadia_source_governance_retained.json').read_text());calls=[]
        def send(role,attempt,payload,schema,instructions):
            row=next(r for r in case['stages'] if (r['stage'],r['attempt'])==(role,attempt));calls.append((role,attempt))
            self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
            return deepcopy(row['output'])
        answers=semantic.run(case['notes'],case['fields'],case['definitions'],send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.ENCOUNTER_SUPPORT_SCOPE_CONTRACT)
        self.assertEqual(digest(answers),case['saved_answers_sha256']);self.assertEqual(len(calls),3)

    def test_inverse_objective_destinations_keep_full_affirmative_scope(self):
        for meaning in ('The objective findings documented from examination or observation, including documented normal or absent findings. Leave blank if not documented.',
                'Objective observations recorded during examination, including positive and negative findings.'):
            raw,proposal=self.complete();definitions=deepcopy(self.definitions);definitions['cell_15']['meaning']=meaning
            answers,_=self.run_case(raw=raw,proposal=proposal,definitions=definitions)
            self.assertEqual(answers['cell_15']['status'],'supported',answers['cell_15']['review_reasons'])
        for tail in (' excluding abdominal findings.',' other than abdominal findings.',
                ' (orientation only).','; observations are not requested.',' if independently verified.'):
            definitions=deepcopy(self.definitions)
            definitions['cell_15']['meaning']='Objective findings from examination'+tail
            with self.subTest(tail=tail):self.held(self.run_case(raw=raw,proposal=proposal,definitions=definitions)[0]['cell_15'])
        definitions=deepcopy(self.definitions)
        definitions['cell_15'].update(meaning='Objective findings from examination.',answer_mode='atomic')
        self.held(self.run_case(raw=raw,proposal=proposal,definitions=definitions)[0]['cell_15'])

    def test_independent_negative_history_partitions_retain_complete_objects(self):
        text='He has no known history of inflammatory bowel disease or celiac disease and no prior abdominal surgery.'
        frame=semantic._governance_literal(text)
        self.assertIsNotNone(frame)
        self.assertEqual([text[start:end] for start,end in frame['parts']],
            ['no known history of inflammatory bowel disease or celiac disease','no prior abdominal surgery'])
        for tail in (' according to his mother',' but has a fever',' except for recent surgery',
                ' according to an unverified report',' yesterday only'):
            self.assertIsNone(semantic._governance_literal(text[:-1]+tail+'.'))

    def test_complete_followup_and_comparison_cannot_be_clipped_or_retimed(self):
        for identity,key,end_text in [('f46','cell_20',', with earlier contact'),('f36','cell_15',', compared with')]:
            raw,proposal=self.complete();fact=next(f for f in raw['facts'] if f['id']==identity)
            fact['value_span']['end']=self.notes.index(end_text,fact['value_span']['start'])
            self.held(self.run_case(raw=raw,proposal=proposal)[0][key])
        for old,new,key in [
                ('initial examination today','initial examination yesterday','cell_15'),
                ('stable and unchanged on repeat examination','not stable and unchanged on repeat examination','cell_15'),
                ('with earlier contact if symptoms worsen','with earlier contact if symptoms worsen according to an unverified report','cell_20'),
                ('moist without a visible lesion','moist without a visible lesion according to an unverified report','cell_15')]:
            notes,raw=self.changed(old,new)
            with self.subTest(new=new):self.held(self.run_case(notes=notes,raw=raw)[0][key])

    def test_pronoun_nonperformance_needs_unique_current_source_order(self):
        for old,new in [('Upper endoscopy is ordered','Upper endoscopy and colonoscopy are ordered'),
                ('Upper endoscopy is ordered','Colonoscopy is ordered'),
                ('Upper endoscopy is ordered','Mother\'s history:\n\nUpper endoscopy is ordered'),
                ('Upper endoscopy is ordered','Previous encounter:\n\nUpper endoscopy is ordered')]:
            notes,raw=self.changed(old,new)
            with self.subTest(new=new):self.held(self.run_case(notes=notes,raw=raw)[0]['cell_17'])
        notes,raw=self.changed('It was not performed today, and no upper-endoscopy results are available.',
            'It was not performed today. No upper-endoscopy results are available.')
        # A source split is not silently repaired into a fabricated exact span.
        fact=next(f for f in raw['facts'] if f['id']=='f42')
        fact['value_span']['end']=fact['value_span']['start']+len('It was not performed today')
        self.held(self.run_case(notes=notes,raw=raw)[0]['cell_17'])

    def test_dated_time_requires_source_date_and_treating_clinician(self):
        for old,new in [('47 minutes on 17 October 2026','47 minutes on 16 October 2026'),
                ('Dr. Voss personally spent','Dr. Hale personally spent'),
                ('Date of service: 17 October 2026','Date of service: unknown'),
                ('The 47 minutes exclude','The 49 minutes exclude')]:
            notes,raw=self.changed(old,new)
            with self.subTest(new=new):self.held(self.run_case(notes=notes,raw=raw)[0]['cell_21'])
        notes,raw=self.changed('Dr. Voss or from any physician','Dr. Hale or from any physician')
        self.held(self.run_case(notes=notes,raw=raw)[0]['cell_4'])

    def test_unparsed_negative_tail_cannot_become_an_affirmed_or_negative_claim(self):
        for new in ('She has not had a food impaction requiring an emergency intervention but has fever',
                'She has not had a food impaction requiring an emergency intervention according to her mother'):
            notes,raw=self.changed('She has not had a food impaction requiring an emergency intervention',new)
            for polarity in ('affirmed','negated'):
                changed=deepcopy(raw);next(f for f in changed['facts'] if f['id']=='f18')['polarity']=polarity
                with self.subTest(new=new,polarity=polarity):self.held(self.run_case(notes=notes,raw=changed)[0]['cell_8'])
