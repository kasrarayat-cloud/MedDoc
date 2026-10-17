"""Actual v18 receipts stay exact; v19 checker proposals are constructed offline."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from core import generation,semantic_generation as semantic
from core.tests import test_clinical_context_generation as legacy
digest=semantic.digest
from core.tests.test_semantic_generation import checker,inventory_api_facts

V19=semantic.SCOPED_DENIAL_SCOPE_CONTRACT


class ScopedDenialGenerationTests(SimpleTestCase):
    raw=legacy.ClinicalContextGenerationTests.raw
    rebase=legacy.ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads((Path(__file__).with_name('fixtures')/'tessa_denial_components_retained.json').read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}

    def proposal(self):
        # Constructed passing assignment/checker controls, never a claim that
        # the actual retained checker or saved clinical answer passed.
        result=deepcopy(self.responses['assigner',1])
        later={r['key']:r for r in self.responses['assigner',2]['fields']}
        result['fields']=[deepcopy(later.get(r['key'],r)) for r in result['fields']]
        next(r for r in result['fields'] if r['key']=='cell_8')['status']='supported'
        return result

    def run_case(self,*,notes=None,raw=None,proposal=None,definitions=None,scope=V19):
        notes=self.notes if notes is None else notes
        raw=self.raw() if raw is None else raw
        proposal=self.proposal() if proposal is None else proposal
        units,_=generation.source_units(notes,self.fields)
        extraction=inventory_api_facts(notes,units,raw['facts']);calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt,payload))
            if scope==V19:
                self.assertTrue(instructions.endswith(semantic.SCOPED_DENIAL_INSTRUCTIONS))
                self.assertIn('scoped_denial_inventory',payload)
            if role=='extractor':return deepcopy(extraction)
            if role=='checker':return checker(proposal)
            return deepcopy(proposal) if attempt==1 else {'fields':[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]}
        return semantic.run(notes,self.fields,definitions or self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=scope),calls

    def held(self,answer):
        self.assertIn(answer['status'],('ambiguous','conflict'),answer['review_reasons'])
        self.assertEqual(answer['text'],'');self.assertFalse(answer['reviewed'])

    def replacement(self,identity,text):
        old=next(f for f in self.raw()['facts'] if f['id']==identity)['value_span']
        notes=self.notes[:old['start']]+text+self.notes[old['end']:]
        raw=self.rebase(notes)
        fact=next(f for f in raw['facts'] if f['id']==identity)
        self.assertEqual(notes[fact['value_span']['start']:fact['value_span']['end']],text)
        return notes,raw

    def test_actual_v18_all_five_requests_and_saved_answers_are_exact(self):
        calls=[]
        def send(role,attempt,payload,schema,instructions):
            row=next(r for r in self.case['stages'] if (r['stage'],r['attempt'])==(role,attempt))
            self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
            calls.append((role,attempt));return deepcopy(row['output'])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.SOURCE_GOVERNANCE_SCOPE_CONTRACT)
        self.assertEqual(digest(answers),self.case['saved_answers_sha256'])
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':21,'conflict':1,'missing':2})
        self.assertEqual(len(calls),5)

    def test_original_checker_conflict_is_not_waived_prospectively(self):
        def send(role,attempt,payload,schema,instructions):return deepcopy(self.responses[role,attempt])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V19)
        self.held(answers['cell_8'])

    def test_unchanged_actual_extraction_and_constructed_checker_complete_all_fields(self):
        answers,calls=self.run_case()
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':22,'missing':2},
            {k:a['review_reasons'] for k,a in answers.items() if a['status'] not in ('supported','missing')})
        self.assertEqual(len(calls),3)
        self.assertIn('difficulty initiating a swallow',answers['cell_8']['text'])
        self.assertIn('difficulty swallowing liquids',answers['cell_8']['text'])
        self.assertIn('food impaction requiring an emergency intervention',answers['cell_8']['text'])
        self.assertIn('bread or meat',answers['cell_6']['text'])
        self.assertEqual(next(f for f in calls[1][2]['facts'] if f['id']=='f16')['issues'],[])

    def test_unfamiliar_complete_nominal_complements_and_plain_lists(self):
        for text in ('She denies difficulty initiating urination and trouble tolerating solid food',
                'They report no discomfort moving an ankle, pain lifting a knee, or difficulty swallowing liquids',
                'The patient denies chills, fever, or nausea'):
            with self.subTest(text=text):
                notes,raw=self.replacement('f16',text);answers,_=self.run_case(notes=notes,raw=raw)
                self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
                self.assertIn(text,answers['cell_8']['text'])

    def test_complete_negative_body_does_not_require_duplicated_subject(self):
        for text,prefix in [('She denies difficulty initiating a swallow','She '),
                ('They report no trouble tolerating solid food','They report '),
                ('He denies nighttime awakening to pass stool and fever','He ')]:
            notes,raw=self.replacement('f16',text)
            next(f for f in raw['facts'] if f['id']=='f16')['value_span']['start']+=len(prefix)
            answers,_=self.run_case(notes=notes,raw=raw)
            self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
            self.assertIn(text[len(prefix):].casefold(),answers['cell_8']['text'].casefold())

    def test_denial_destination_requires_affirmative_unrestricted_intent(self):
        for meaning in ('Documented symptom negatives excluding swallowing difficulty.',
                'Documented symptom negatives only about fever.','Do not include symptom negatives.',
                'Documented absence of vomiting only.','Denied symptoms other than swallowing problems.',
                'Documented current medicines.'):
            definitions=deepcopy(self.definitions);definitions['cell_8']['meaning']=meaning
            answers,_=self.run_case(definitions=definitions);self.held(answers['cell_8'])
        for meaning in ('Record all explicitly denied symptoms as documented.',
                'Documented negative symptoms.','Description of the history of present illness.',
                'Document current symptom negatives.','Document all current symptom negatives.',
                'Summarize all documented symptom negatives.'):
            definitions=deepcopy(self.definitions);definitions['cell_8']['meaning']=meaning
            answers,_=self.run_case(definitions=definitions)
            self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])

    def test_complete_predicate_body_cannot_bypass_restricted_topic_scope(self):
        for meaning in ('Description of the documented urinary symptoms and fluid intake, including documented absence as well as presence.',
                'Documented GI symptoms and pertinent negatives (fever), including documented absence.',
                'Documented renal symptoms and pertinent negatives (difficulty swallowing, vomiting), including documented absence.'):
            with self.subTest(meaning=meaning):
                raw=self.raw();next(f for f in raw['facts'] if f['id']=='f16')['value_span']['start']+=len('She ')
                definitions=deepcopy(self.definitions);definitions['cell_8']['meaning']=meaning
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                answers,_=self.run_case(raw=raw,definitions=definitions,proposal=proposal)
                self.held(answers['cell_8'])

    def test_reviewed_topic_relevance_keeps_whole_literals_and_all_objects(self):
        text='She denies difficulty swallowing, painful swallowing, vomiting blood, black stool, blood in the stool and unintended weight loss'
        meaning='Documented digestive symptoms and pertinent negatives (dysphagia, odynophagia, hematemesis, melena, hematochezia, unintentional weight loss), including documented absence.'
        notes,raw=self.replacement('f16',text);proposal=self.proposal()
        next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
        definitions=deepcopy(self.definitions);definitions['cell_8']['meaning']=meaning
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
        self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
        self.assertEqual(answers['cell_8']['text'],text)
        for changed in (meaning.replace('dysphagia','acute dysphagia'),
                meaning.replace('dysphagia, odynophagia, hematemesis, melena, hematochezia, unintentional weight loss','melena'),
                meaning.replace('digestive','renal')):
            with self.subTest(meaning=changed):
                definitions['cell_8']['meaning']=changed
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.held(answers['cell_8'])
        # One relevant object creates an obligation, not permission to render
        # the unrequested remainder or silently drop the complete extraction.
        definitions['cell_8']['meaning']=meaning.replace('dysphagia, odynophagia, hematemesis, melena, hematochezia, unintentional weight loss','melena')
        next(r for r in proposal['fields'] if r['key']=='cell_8').update(fact_ids=[],status='missing')
        raw['facts']=[f for f in raw['facts'] if f['id']!='f16']
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
        self.held(answers['cell_8'])
        self.assertTrue(any('reported_absence' in reason for reason in answers['cell_8']['review_reasons']))

    def test_single_negative_keeps_ordinary_atomic_and_narrow_topic_scope(self):
        cases=[('She reports no fever','no fever','Fever','atomic'),
            ('She reports no fever','no fever','Document fever.','atomic'),
            ('She reports no chest pain','no chest pain','Current chest pain','atomic'),
            ('She reports no fever','no fever','Documented absence of fever only.','narrative'),
            ('She reports no fever','no fever','Documented GI symptoms and pertinent negatives (fever), including documented absence.','narrative'),
            ('She reports no fever and cough','no fever','Document fever.','atomic')]
        for text,value,meaning,mode in cases:
            with self.subTest(text=text,meaning=meaning):
                notes,raw=self.replacement('f16',text)
                fact=next(f for f in raw['facts'] if f['id']=='f16')
                fact['value_span']['start']+=text.index(value)
                fact['value_span']['end']=fact['value_span']['start']+len(value)
                definitions=deepcopy(self.definitions)
                definitions['cell_8'].update(meaning=meaning,answer_mode=mode)
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
                self.assertEqual(answers['cell_8']['text'].casefold(),value)

    def test_narrow_negatives_cannot_drop_complements_or_widen_atomic_topics(self):
        for text,value,meaning,mode in [
                ('She denies difficulty initiating urination','urination','Urination','atomic'),
                ('She reports no chest pain','no chest pain','Current pain','atomic'),
                ('She reports no difficulty swallowing','no difficulty swallowing','Documented GI symptoms and pertinent negatives (dysphagia), including documented absence.','atomic'),
                ('She reports no fever and cough','no fever','Document all current symptom negatives.','narrative'),
                ('She reports no fever and cough','no fever and cough','Document fever.','narrative')]:
            with self.subTest(text=text,meaning=meaning):
                notes,raw=self.replacement('f16',text)
                fact=next(f for f in raw['facts'] if f['id']=='f16')
                fact['value_span']['start']+=text.index(value)
                fact['value_span']['end']=fact['value_span']['start']+len(value)
                definitions=deepcopy(self.definitions);definitions['cell_8'].update(meaning=meaning,answer_mode=mode)
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.held(answers['cell_8'])

    def test_exact_prenominal_modifier_class_preserves_narrow_negatives(self):
        for topic in ('persistent fever','recurrent nausea','intermittent fever','constant pain',
                'intermittent chest pain','palpable lump','prolonged bleeding','intense pain','purple rash',
                'faint wheezing','yellow sputum'):
            with self.subTest(topic=topic):
                text='She reports no '+topic+' and cough';value='no '+topic
                notes,raw=self.replacement('f16',text)
                fact=next(f for f in raw['facts'] if f['id']=='f16')
                fact['value_span']['start']+=len('She reports ')
                fact['value_span']['end']=fact['value_span']['start']+len(value)
                definitions=deepcopy(self.definitions)
                definitions['cell_8'].update(meaning='Document '+topic+'.',answer_mode='atomic')
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
                self.assertEqual(answers['cell_8']['text'].casefold(),value)

    def test_modifier_composition_cannot_hide_qualifiers_predicates_or_drop_scope(self):
        for text,value,topic in [
                ('She reports no persistent fever and cough','no persistent fever','fever'),
                ('She reports no possible persistent fever and cough','no possible persistent fever','possible persistent fever'),
                ('She reports no apparent fever and cough','no apparent fever','apparent fever'),
                ('She reports no unconfirmed recurrent fever and cough','no unconfirmed recurrent fever','unconfirmed recurrent fever'),
                ('She reports no patient fever and cough','no patient fever','patient fever'),
                ('She reports no persistent fever occurs daily and cough','no persistent fever','persistent fever'),
                ('She reports no persistent fever according to her mother and cough','no persistent fever','persistent fever'),
                ('She reports no prolonged bleeding and cough','no prolonged bleeding','bleeding'),
                ('She reports no purple rash and cough','no purple rash','rash'),
                ('She reports no suspected palpable lump and cough','no suspected palpable lump','suspected palpable lump'),
                ('She reports no alleged palpable lump and cough','no alleged palpable lump','alleged palpable lump'),
                ('She reports no fever caused rash and cough','no fever caused rash','fever caused rash'),
                ('She reports no intense pain, develops nausea','no intense pain','intense pain')]:
            with self.subTest(text=text,topic=topic):
                notes,raw=self.replacement('f16',text)
                fact=next(f for f in raw['facts'] if f['id']=='f16')
                fact['value_span']['start']+=len('She reports ')
                fact['value_span']['end']=fact['value_span']['start']+len(value)
                definitions=deepcopy(self.definitions);definitions['cell_8'].update(meaning='Document '+topic+'.',answer_mode='atomic')
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.held(answers['cell_8'])

    def test_modified_objects_keep_exact_topic_and_primary_domain_intersection(self):
        for topic in ('persistent fever','persistent abdominal pain'):
            with self.subTest(topic=topic):
                text='She reports no '+topic;notes,_=self.replacement('f16',text)
                # This constructed scope control has only this denial. The
                # retained case's separate impaction absence otherwise also
                # belongs in an unrestricted negative narrative.
                impaction=next(f for f in self.raw()['facts'] if f['id']=='f17')['value_span']
                notes=notes.replace(self.notes[impaction['start']:impaction['end']]+'.','')
                retained=self.raw();retained['facts']=[f for f in retained['facts'] if f['id']!='f17']
                with patch.object(self,'raw',return_value=retained):raw=self.rebase(notes)
                proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
                definitions=deepcopy(self.definitions)
                listed='Documented GI symptoms and pertinent negatives ('+topic+'), including documented absence.'
                for meaning in ('Document all current symptom negatives.',listed,
                        'Describe the documented bowel habits, associated digestive symptoms and food intake, including documented absence as well as presence.'):
                    definitions['cell_8']['meaning']=meaning
                    answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                    self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
                    self.assertEqual(answers['cell_8']['text'],text)
                for meaning in (listed.replace('persistent ',''),listed.replace('persistent','recurrent'),
                        listed.replace('GI','renal')):
                    definitions['cell_8']['meaning']=meaning
                    answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                    self.held(answers['cell_8'])
                definitions['cell_8']['meaning']=listed
                next(r for r in proposal['fields'] if r['key']=='cell_8').update(status='missing',fact_ids=[])
                raw['facts']=[f for f in raw['facts'] if f['id']!='f16']
                answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
                self.held(answers['cell_8'])
        # A recognized modifier does not move a different organ's symptom
        # into GI, and a clinical topic relation cannot erase modifiers.
        for topic,requested in (('persistent chest pain','persistent chest pain'),
                ('persistent difficulty swallowing','persistent dysphagia')):
            notes,raw=self.replacement('f16','She reports no '+topic)
            definitions=deepcopy(self.definitions)
            definitions['cell_8']['meaning']='Documented GI symptoms and pertinent negatives ('+requested+'), including documented absence.'
            proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
            answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
            self.held(answers['cell_8'])

    def test_approved_topic_suffix_syntax_never_drops_the_requested_property(self):
        notes,raw=self.replacement('f16','She reports no persistent fever')
        definitions=deepcopy(self.definitions)
        meaning='Documented GI symptoms and pertinent negatives (persistent fever and appetite change), including documented absence.'
        definitions['cell_8']['meaning']=meaning
        proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
        self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
        self.assertEqual(answers['cell_8']['text'],'She reports no persistent fever')
        for changed in (meaning.replace('persistent fever','fever'),meaning.replace('persistent','recurrent')):
            definitions['cell_8']['meaning']=changed
            answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
            self.held(answers['cell_8'])
        notes,raw=self.replacement('f16','She reports no appetite')
        definitions['cell_8']['meaning']='Documented GI symptoms and pertinent negatives (appetite change), including documented absence.'
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
        self.held(answers['cell_8'])

    def test_unfamiliar_bowel_history_intent_has_finite_associated_topic_scope(self):
        text='She denies blood in the stool, black stools, fever, vomiting, nighttime awakening to pass stool and unintentional weight loss'
        notes,raw=self.replacement('f16',text);proposal=self.proposal()
        next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
        definitions=deepcopy(self.definitions)
        meaning='Describe the documented bowel habits, associated digestive symptoms and food intake, including documented absence as well as presence.'
        definitions['cell_8']['meaning']=meaning
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal)
        self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])
        for changed in (meaning.replace('bowel habits','urinary symptoms'),meaning.replace('associated digestive','cardiac')):
            definitions['cell_8']['meaning']=changed
            answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal);self.held(answers['cell_8'])
        definitions['cell_8']['meaning']=meaning
        notes,raw=self.replacement('f16',text+' and chest pain')
        answers,_=self.run_case(notes=notes,raw=raw,definitions=definitions,proposal=proposal);self.held(answers['cell_8'])

    def test_backward_denial_references_keep_owner_and_integrity_scope(self):
        for suffix in ('The reported symptom denials above are false.',
                'The reported symptom denials above are unverified.',
                'It is uncertain whether the symptom denials above are not false.',
                'The reported symptom denials above are not false but all clinical statements are false.'):
            with self.subTest(suffix=suffix):
                notes=self.notes+'\n'+suffix
                answers,_=self.run_case(notes=notes,raw=self.rebase(notes));self.held(answers['cell_8'])
        for suffix in ('The reported symptom denials above are not false.',
                "Her mother's symptom denials above are false.",
                'Previous encounter:\nThe reported symptom denials above are false.',
                "The prior encounter's symptom denials above are false."):
            with self.subTest(suffix=suffix):
                notes=self.notes+'\n'+suffix
                answers,_=self.run_case(notes=notes,raw=self.rebase(notes))
                self.assertEqual(answers['cell_8']['status'],'supported',answers['cell_8']['review_reasons'])

    def test_qualified_nested_attributed_and_shifted_predicates_stay_held(self):
        for text in ('She denies difficulty initiating urination but has fever',
                'She denies trouble tolerating solid food, feels unwell',
                'She denies difficulty initiating urination according to an unverified report',
                'She denies possible trouble tolerating solid food',
                'She denies that her mother has trouble tolerating solid food',
                'No one established whether she denies difficulty initiating urination',
                'She denies trouble tolerating solid food except on weekends',
                'She denies difficulty initiating urination yesterday',
                'She no trouble tolerating solid food',
                'She reports denies difficulty initiating urination'):
            with self.subTest(text=text):
                notes,raw=self.replacement('f16',text);answers,_=self.run_case(notes=notes,raw=raw)
                self.held(answers['cell_8'])

    def test_clipped_annotated_or_atomic_absences_cannot_replace_full_denial(self):
        for mode in ('clipped','affirmed','uncertain','past','other','atomic'):
            raw=self.raw();definitions=deepcopy(self.definitions);proposal=self.proposal();fact=next(f for f in raw['facts'] if f['id']=='f16')
            if mode=='clipped':fact['value_span']['start']+=len('She denies ')
            elif mode in ('affirmed','uncertain'):fact['polarity']=mode
            elif mode=='past':fact['timing']['kind']='past'
            elif mode=='other':fact['subject']['kind']='other'
            else:
                definitions['cell_8']['answer_mode']='atomic'
                next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f16']
            with self.subTest(mode=mode):
                answers,_=self.run_case(raw=raw,definitions=definitions,proposal=proposal);self.held(answers['cell_8'])

    def test_missing_extraction_or_selection_retains_explicit_source_gap(self):
        for remove in (False,True):
            raw=self.raw();proposal=self.proposal()
            next(r for r in proposal['fields'] if r['key']=='cell_8')['fact_ids']=['f17']
            if remove:raw['facts']=[f for f in raw['facts'] if f['id']!='f16']
            answers,_=self.run_case(raw=raw,proposal=proposal);self.held(answers['cell_8'])
            self.assertTrue(any('reported_absence' in reason for reason in answers['cell_8']['review_reasons']))

    def test_foreign_prior_and_retracted_denials_are_not_patient_negatives(self):
        for prefix in ('Mother:\n','Previous encounter:\n'):
            span=next(f for f in self.raw()['facts'] if f['id']=='f16')['value_span']
            notes=self.notes[:span['start']]+prefix+self.notes[span['start']:span['end']]+'.\nCurrent patient:\n'+self.notes[span['end']+1:]
            raw=self.rebase(notes);answers,_=self.run_case(notes=notes,raw=raw);self.held(answers['cell_8'])
        notes=self.notes+'\nAll the above clinical statements are false.'
        answers,_=self.run_case(notes=notes,raw=self.rebase(notes));self.held(answers['cell_8'])

    def test_complete_historical_encounter_contrast_keeps_both_components(self):
        proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_9')['fact_ids'].append('f11')
        answers,calls=self.run_case(proposal=proposal)
        self.assertEqual(answers['cell_9']['status'],'supported',answers['cell_9']['review_reasons'])
        self.assertIn('outside primary-care visit, not a previous visit with Dr. Voss or this GI group',answers['cell_9']['text'])
        self.assertEqual(next(f for f in calls[1][2]['facts'] if f['id']=='f11')['issues'],[])

    def test_unfamiliar_contrast_actor_and_complete_denial_across_units(self):
        notes=self.notes.replace('Voss','Quinn').replace('primary-care','primary care')
        raw=self.rebase(notes);proposal=self.proposal()
        next(r for r in proposal['fields'] if r['key']=='cell_9')['fact_ids'].append('f11')
        answers,_=self.run_case(notes=notes,raw=raw,proposal=proposal)
        self.assertEqual(answers['cell_9']['status'],'supported',answers['cell_9']['review_reasons'])
        span=next(f for f in self.raw()['facts'] if f['id']=='f16')['value_span']
        text='She denies trouble tolerating solid food. She denies difficulty initiating urination'
        notes=self.notes[:span['start']]+text+self.notes[span['end']:]
        raw=self.rebase(notes)
        # Only the first new sentence has an extracted fact. The second one
        # cannot disappear simply because the checker passes that selection.
        answers,_=self.run_case(notes=notes,raw=raw);self.held(answers['cell_8'])

    def test_intervening_treatment_chain_is_complete_and_same_actor_and_medicine(self):
        proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_9')['fact_ids'].append('f11')
        notes=self.notes.replace('Nora Hale','Evan Finch').replace('Dr. Hale','Dr. Finch').replace('omeprazole','lansoprazole')
        answers,_=self.run_case(notes=notes,raw=self.rebase(notes),proposal=proposal)
        self.assertEqual(answers['cell_9']['status'],'supported',answers['cell_9']['review_reasons'])
        for original,replacement in (
                ('Dr. Hale recommended','Dr. Corwin recommended'),
                ('She is no longer taking omeprazole','She is no longer taking loratadine'),
                ('It partially reduced her heartburn','It possibly reduced her heartburn')):
            with self.subTest(replacement=replacement):
                notes=self.notes.replace(original,replacement)
                answers,_=self.run_case(notes=notes,raw=self.rebase(notes),proposal=proposal)
                self.held(answers['cell_9'])

    def test_contrast_clipping_polarity_current_scope_and_wrong_clinician_stay_held(self):
        for mode in ('clipped','affirmed','negated','current','wrong_actor','qualified','restricted'):
            raw=self.raw();notes=self.notes;definitions=deepcopy(self.definitions);proposal=self.proposal()
            next(r for r in proposal['fields'] if r['key']=='cell_9')['fact_ids'].append('f11')
            fact=next(f for f in raw['facts'] if f['id']=='f11')
            if mode=='clipped':fact['value_span']['end']=fact['value_span']['start']+len('This was an outside primary-care visit')
            elif mode in ('affirmed','negated'):fact['polarity']=mode
            elif mode=='current':definitions['cell_9']['scope']['temporality']='current'
            elif mode=='restricted':definitions['cell_9']['meaning']='Prior outside encounter date only.'
            else:
                old=notes[fact['value_span']['start']:fact['value_span']['end']]
                replacement=old.replace('Dr. Voss','Dr. Corwin') if mode=='wrong_actor' else old+' according to an unverified report'
                notes,raw=self.replacement('f11',replacement)
            with self.subTest(mode=mode):
                answers,_=self.run_case(notes=notes,raw=raw,proposal=proposal,definitions=definitions);self.held(answers['cell_9'])

    def test_intervening_encounter_reference_and_narrow_contrast_are_held(self):
        proposal=self.proposal();next(r for r in proposal['fields'] if r['key']=='cell_9')['fact_ids'].append('f11')
        start=next(f for f in self.raw()['facts'] if f['id']=='f11')['value_span']['start']
        for text in ('Her mother had a primary-care visit yesterday. ',
                'Today she saw another doctor for a current visit. ',
                'Yesterday she attended this GI clinic. ',
                'She returned to this GI practice yesterday. ',
                'Her mother returned here yesterday. ',
                'She mentioned another appointment here. ',
                'The earlier visit reference is unverified. '):
            notes=self.notes[:start]+text+self.notes[start:]
            answers,_=self.run_case(notes=notes,raw=self.rebase(notes),proposal=proposal);self.held(answers['cell_9'])
        for meaning in ('Distinction of outside visit dates alone.',
                'Distinguish the outside practice name; omit encounter relationship to this GI group.'):
            definitions=deepcopy(self.definitions);definitions['cell_9']['meaning']=meaning
            answers,_=self.run_case(proposal=proposal,definitions=definitions);self.held(answers['cell_9'])
