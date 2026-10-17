"""Prospective v15 source fidelity; retained v13 replies remain immutable.

Fresh replies here are constructed offline proposals, not provider predictions.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import difflib
import json
from pathlib import Path
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.clinical_source_context import source_context, clinician_matches, owned_current
from core.tests.test_semantic_generation import checker, inventory_api_facts, span

FIXTURE=Path(__file__).with_name('fixtures')/'elias_clinical_retained.json'
V15=semantic.CLINICAL_CONTEXT_SCOPE_CONTRACT


def digest(value):
    return hashlib.sha256((value if isinstance(value,str) else json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)).encode()).hexdigest()


class ClinicalContextGenerationTests(SimpleTestCase):
    def setUp(self):
        self.case=json.loads(FIXTURE.read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
        self.responses={(r['stage'],r['attempt']):r['output'] for r in self.case['stages']}

    def raw(self,notes=None):
        notes=self.notes if notes is None else notes
        units,_=generation.source_units(notes,self.fields)
        return semantic.resolve_source_references(notes,units,deepcopy(self.responses['extractor',1]),reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)

    def proposal(self):
        result=deepcopy(self.responses['assigner',1])
        for key,ids in [('cell_2',['f11']),('cell_4',['f10']),('cell_9',['f14']),('cell_14',['f29'])]:
            next(r for r in result['fields'] if r['key']==key)['fact_ids']+=ids
        return result

    def rebase(self,notes, replacements=()):
        """Move retained source spans by their literal text after fixture edits."""
        raw=self.raw(); units,_=generation.source_units(notes,self.fields)
        old_units,_=generation.source_units(self.notes,self.fields)
        changes=difflib.SequenceMatcher(None,self.notes,notes,autojunk=False).get_opcodes()
        def position(value,end=False):
            for tag,a,b,c,d in changes:
                if a<=value<=b:
                    if tag=='equal':return c+value-a
                    if value==a:return c
                    if value==b:return d
                    return d if end else c
            raise AssertionError('Unmapped fixture offset')
        def shifted(old):
            if old is None:return None
            start,end=position(old['start']),position(old['end'],True)
            while start<end and notes[start].isspace():start+=1
            return {'start':start,'end':end}
        for f in raw['facts']:
            previous=f['value_span']
            whole=any(previous['start']==u['start'] and self.notes[previous['start']:previous['end']].removesuffix('.')==u['quote'].removesuffix('.') for u in old_units)
            for obj,key in ((f,'value_span'),(f['subject'],'name_span'),(f['timing'],'span'),(f,'unit_span')):
                obj[key]=shifted(obj[key])
            if whole:
                unit=next(u for u in units if u['start']<=f['value_span']['start']<u['end'])
                f['value_span']={'start':unit['start'],'end':unit['end']-(1 if unit['quote'].endswith('.') else 0)}
            if f['scale']: f['scale']['span']=shifted(f['scale']['span'])
            refs=[f['value_span'],f['subject']['name_span'],f['timing']['span'],f['unit_span']]
            f['source_unit_ids']=sorted({u['id'] for u in units for ref in refs if ref and u['start']<=ref['start']<ref['end']<=u['end']})
        return raw

    def run_case(self,raw=None,proposal=None,notes=None,definitions=None):
        notes=self.notes if notes is None else notes
        units,_=generation.source_units(notes,self.fields)
        extraction=inventory_api_facts(notes,units,(raw or self.raw())['facts'])
        proposal=proposal or self.proposal()
        calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertIn('clinical_context_inventory',payload)
            self.assertTrue(instructions.endswith(semantic.CLINICAL_CONTEXT_INSTRUCTIONS))
            if role=='extractor':return deepcopy(extraction)
            if role=='checker':return checker(proposal)
            return deepcopy(proposal) if attempt==1 else {'fields':[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]}
        answers=semantic.run(notes,self.fields,definitions or self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V15)
        return answers,calls

    def test_retained_v13_requests_and_complete_answers_are_exact(self):
        self.assertEqual(digest(self.notes),self.case['provenance']['source_sha256'])
        calls=[]
        def send(role,attempt,payload,schema,instructions):
            row=next(r for r in self.case['stages'] if (r['stage'],r['attempt'])==(role,attempt))
            calls.append((role,attempt))
            self.assertEqual({k:digest(v) for k,v in [('payload',payload),('schema',schema),('instructions',instructions)]},row['request_digests'])
            return deepcopy(row['output'])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT)
        self.assertEqual(digest(answers),self.case['saved_answers_sha256'])
        self.assertEqual(len(calls),5)

    def test_retained_v14_does_not_gain_new_permissions(self):
        def send(role,attempt,payload,schema,instructions):
            self.assertNotIn('clinical_context_inventory',payload)
            self.assertNotIn(semantic.CLINICAL_CONTEXT_INSTRUCTIONS,instructions)
            return deepcopy(self.responses[role,attempt])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=semantic.ENCOUNTER_SUPPORT_SCOPE_CONTRACT)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'conflict':2,'missing':2})
        self.assertEqual([key for key,a in answers.items() if a['status']=='conflict'],['cell_13','cell_17'])

    def test_complete_current_source_preserves_all_approved_content(self):
        answers,calls=self.run_case()
        self.assertEqual(len(calls),3)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':18,'missing':2})
        for key,fragments in {'cell_2':['previously saw this same clinician'], 'cell_9':['no longer taking psyllium','famotidine 20 mg'], 'cell_13':['remains uncertain','neither has been established','No definitive underlying disease'], 'cell_14':['No procedure was performed','neither test was performed'], 'cell_17':['37 minutes','six minutes','24 minutes','seven minutes','nine minutes of nursing','five minutes of physician record review performed on the preceding day','separately reported services']}.items():
            for fragment in fragments:self.assertIn(fragment.casefold(),answers[key]['text'].casefold())
        self.assertNotIn('no longer taking',answers['cell_6']['text'])
        self.assertNotIn('psyllium',answers['cell_15']['text'])
        self.assertNotIn('f36',answers['cell_17']['fact_ids'])
        self.assertTrue(all(not a['reviewed'] for a in answers.values()))

    def test_absent_extracted_qualifications_cannot_be_invented_by_passing_checker(self):
        for identity,key in [('f11','cell_2'),('f14','cell_9'),('f24','cell_13'),('f25','cell_13'),('f26','cell_13'),('f29','cell_14'),('f35','cell_17'),('f37','cell_17'),('f38','cell_17')]:
            raw=self.raw();raw['facts']=[f for f in raw['facts'] if f['id']!=identity]
            proposal=self.proposal()
            for row in proposal['fields']:row['fact_ids']=[i for i in row['fact_ids'] if i!=identity]
            with self.subTest(identity=identity):
                answers,_=self.run_case(raw,proposal)
                self.assertEqual(answers[key]['status'],'conflict')
                self.assertEqual(answers[key]['text'],'')

    def test_partial_values_and_numeric_siblings_do_not_supply_whole_support(self):
        for identity,quote,key in [('f35','37','cell_17'),('f37','nine minutes','cell_17'),('f25','Infectious and inflammatory causes','cell_13'),('f14','psyllium','cell_9')]:
            raw=self.raw();row=next(f for f in raw['facts'] if f['id']==identity)
            start=self.notes.index(quote,row['value_span']['start']);row['value_span']={'start':start,'end':start+len(quote)}
            with self.subTest(identity=identity):self.assertEqual(self.run_case(raw)[0][key]['status'],'conflict')

    def test_wrong_metadata_subject_timing_and_polarity_remain_held(self):
        for identity,key in [('f14','cell_9'),('f24','cell_13'),('f25','cell_13'),('f29','cell_14'),('f35','cell_17'),('f37','cell_17')]:
            for mutation in ('subject','timing'):
                raw=self.raw();row=next(f for f in raw['facts'] if f['id']==identity)
                if mutation=='subject':
                    row['subject']={'kind':'other','name_span':span(self.notes,'Synthetic Elias Mercer')}
                    if 2 not in row['source_unit_ids']:row['source_unit_ids'].append(2)
                else:row['timing']['kind']='past'
                with self.subTest(identity=identity,mutation=mutation):self.assertEqual(self.run_case(raw)[0][key]['status'],'conflict')
        for identity,key in [('f14','cell_9'),('f24','cell_13'),('f29','cell_14')]:
            raw=self.raw();next(f for f in raw['facts'] if f['id']==identity)['polarity']='affirmed'
            self.assertEqual(self.run_case(raw)[0][key]['status'],'conflict')

    def test_foreign_and_historical_sections_persist_across_blank_lines(self):
        for heading in ("Mother's medical history:",'History of the sibling:','Historical consultation:','Previous encounter:','Future visit:','Copied record:'):
            notes=self.notes.replace('A - Assessment',heading+'\n\nA - Assessment')
            raw=self.rebase(notes)
            with self.subTest(heading=heading):
                answers,_=self.run_case(raw,notes=notes)
                self.assertEqual(answers['cell_13']['status'],'conflict')
                self.assertEqual(answers['cell_17']['status'],'conflict')
                self.assertFalse(any(r['field_key'] in ('cell_13','cell_17') for r in semantic._clinical_context_inventory(notes,self.definitions)))

    def test_clinician_and_deictic_total_require_independent_source_binding(self):
        for before,after in [('Dr. Farrow personally','Dr. Corwin personally'),('The 37 minutes exclude','The 47 minutes exclude')]:
            notes=self.notes.replace(before,after);raw=self.rebase(notes,[(before,after),('Farrow','Corwin')] if 'Corwin' in after else [(before,after)])
            for f in raw['facts']:
                if f['id'] in ('f35','f36','f37','f38'):f['subject']={'kind':'patient','name_span':None}
            with self.subTest(after=after):self.assertEqual(self.run_case(raw,notes=notes)[0]['cell_17']['status'],'conflict')

    def test_generalized_people_terms_and_template_preserve_literal_source(self):
        replacements=[('Synthetic Elias Mercer','Synthetic Amira Quinn'),('Leena Farrow','Hana Bisset'),('Dr. Farrow','Dr. Bisset'),('gastrointestinal','neurology'),('GI clinic','neurology clinic'),('psyllium','methylcellulose'),('famotidine','omeprazole'),('Infectious and inflammatory causes','Medication-related and autoimmune conditions'),('The cause remains uncertain','The etiology is unclear')]
        notes=self.notes
        for before,after in replacements:notes=notes.replace(before,after)
        raw=self.rebase(notes,replacements)
        definitions=deepcopy(self.definitions)
        definitions['cell_13']['meaning']='Clinical impression, preserving evaluated symptoms, uncertainty and diagnostic exclusions.'
        definitions['cell_17']['meaning']='The evaluation and management selection basis with total physician time and all documented activities and exclusions.'
        answers,_=self.run_case(raw,notes=notes,definitions=definitions)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':18,'missing':2})
        self.assertIn('autoimmune conditions remain possibilities; neither has been established',answers['cell_13']['text'])

    def test_owner_and_time_reset_independently_and_past_medical_history_is_current_documentation(self):
        prefix='Patient: Synthetic Mira Lane\nTreating clinician: Dr. Mara Voss\n'
        text='The cause remains uncertain.'
        for middle,expected in [("Mother's history:\nCurrent encounter:\nA - Assessment\n",False),('Previous visit:\nPatient: Synthetic Mira Lane\nA - Assessment\n',False),('Past medical history:\nA - Assessment\n',True),("Mother's history:\nPrevious visit:\nCurrent patient: Synthetic Mira Lane\nA - Assessment\n",True)]:
            notes=prefix+middle+text; units,_=generation.source_units(notes,[]);context=source_context(notes,units)
            self.assertEqual(owned_current(context,units[-1]),expected)
            self.assertTrue(clinician_matches(context,'Voss'))
            self.assertFalse(clinician_matches(context,'Other'))

    def test_atomic_and_unrelated_approved_fields_acquire_no_obligations(self):
        definitions=deepcopy(self.definitions)
        for key in ('cell_2','cell_9','cell_13','cell_14','cell_17'):definitions[key]['answer_mode']='atomic'
        self.assertFalse(semantic._clinical_context_inventory(self.notes,definitions))

    def test_temporality_polarity_and_explicit_narrow_meanings_limit_completeness(self):
        for key,change in [('cell_13',{'meaning':'Clinical assessment: confirmed diagnoses only.'}),('cell_14',{'meaning':'Investigations: ordered tests only.'}),('cell_9',{'meaning':'Current medicines, names only.'}),('cell_13',{'scope':{'subject':'patient','temporality':'past','polarity':'any'}}),('cell_14',{'scope':{'subject':'patient','temporality':'future','polarity':'any'}}),('cell_9',{'scope':{'subject':'patient','temporality':'current','polarity':'affirmed'}})]:
            definitions=deepcopy(self.definitions);definitions[key].update(change)
            with self.subTest(key=key,change=change):self.assertFalse(any(row['field_key']==key for row in semantic._clinical_context_inventory(self.notes,definitions)))

    def test_paraphrased_qualifications_require_complete_values_and_cannot_disappear(self):
        variants=[('The total also excludes any time for separately reported services.',after,'f38','cell_17') for after in ('Time for separately reported services is excluded from this total.','This total does not count time for separately reported services.','I excluded all time for separately reported services from the total.','They also exclude time for separately reported services.')]
        variants += [('He is no longer taking psyllium.','He has stopped taking psyllium.','f14','cell_9'),('Infectious and inflammatory causes remain possibilities; neither has been established.','Infectious and inflammatory causes are possible; neither has been established.','f25','cell_13'),('No procedure was performed during this encounter.',"No procedure took place at today's visit.",'f29','cell_14')]
        for before,after,identity,key in variants:
            notes=self.notes.replace(before,after);raw=self.rebase(notes)
            with self.subTest(after=after):
                answers,_=self.run_case(raw,notes=notes)
                self.assertEqual(answers[key]['status'],'supported',answers[key]['review_reasons'])
                self.assertIn(after.removesuffix('.'),answers[key]['text'])
                if identity=='f14':
                    affirmed=deepcopy(raw);next(f for f in affirmed['facts'] if f['id']==identity)['polarity']='affirmed'
                    self.assertEqual(self.run_case(affirmed,notes=notes)[0][key]['status'],'supported')
                raw['facts']=[f for f in raw['facts'] if f['id']!=identity];proposal=self.proposal()
                for r in proposal['fields']:r['fact_ids']=[f for f in r['fact_ids'] if f!=identity]
                self.assertEqual(self.run_case(raw,proposal,notes)[0][key]['status'],'conflict')

    def test_unrecognized_qualification_cues_still_prevent_false_green_omissions(self):
        for before,after,identity,key in [('The total also excludes any time for separately reported services.','Separately reported services did not count toward the total.','f38','cell_17'),('He is no longer taking psyllium.','The patient discontinued using psyllium.','f14','cell_9'),('Infectious and inflammatory causes remain possibilities; neither has been established.','Infection or inflammation might explain the symptoms, but this is not established.','f25','cell_13'),('No procedure was performed during this encounter.','No procedures happened today.','f29','cell_14')]:
            notes=self.notes.replace(before,after);raw=self.rebase(notes);raw['facts']=[f for f in raw['facts'] if f['id']!=identity];proposal=self.proposal()
            for r in proposal['fields']:r['fact_ids']=[f for f in r['fact_ids'] if f!=identity]
            with self.subTest(after=after):self.assertEqual(self.run_case(raw,proposal,notes)[0][key]['status'],'conflict')

    def test_retractions_reassignments_and_retiming_hold_the_referenced_current_account(self):
        variants=[
            ('Retraction: The assessment and physician time are erroneous and must not be used.',('cell_13','cell_17')),
            ('The stated 37 minutes were for the appointment yesterday, not today.',('cell_17',)),
            ('The assessment and time account refer to his mother.',('cell_13','cell_17')),
            ('These physician time entries concern yesterday.',('cell_17',)),
            ('The assessment belongs to a family member.',('cell_13',)),
            ('Disregard the above assessment and time calculation.',('cell_13','cell_17')),
            ('The assessment and time figures pertain to a different visit.',('cell_13','cell_17')),
            ('The time total is wrong.',('cell_17',)),
            ('That total actually belongs to yesterday’s appointment.',('cell_17',)),
            ('The total includes the nine minutes of nursing rooming work.',('cell_17',)),
            ('The last paragraph is about a different patient.',('cell_17',)),
            ('The physician time needs a substantial qualification.',('cell_17',)),
            ('The assessment has an unresolved qualification.',('cell_13',)),
            ('The assessment is wrong but the time total is not wrong.',('cell_13',)),
            ('The last paragraph is wrong but the assessment is wrong.',('cell_13','cell_17')),
            ('Do not disregard the above assessment and time calculation; the assessment is wrong.',('cell_13',)),
        ]
        for suffix,keys in variants:
            notes=self.notes+'\n\n'+suffix
            with self.subTest(suffix=suffix):
                answers,_=self.run_case(self.rebase(notes),notes=notes)
                for key in keys:self.assertEqual(answers[key]['status'],'conflict')
                if keys==('cell_17',):self.assertEqual(answers['cell_13']['status'],'supported')

    def test_unrelated_foreign_or_historical_correction_does_not_retract_current_account(self):
        for suffix in (
                "The assessment of his mother was erroneous.", "His mother's prior assessment was incorrect.",
                "Yesterday's other clinician's time was incorrect.",
                "Mother's history:\n\nRetraction: The assessment and physician time are erroneous and must not be used.",
                "Previous visit:\n\nRetraction: The assessment and physician time are erroneous and must not be used.",
                "Mother's history:\n\nThe above assessment was incorrect.",
                "The assessment and physician time are not erroneous.", "The assessment does not belong to his mother.",
                "Do not disregard the above assessment and time calculation.", "The time total is not wrong.",
                "The assessment does not pertain to a different visit.",
                "The assessment and time account do not refer to his mother.",
                "The assessment is not wrong and the time total is not wrong.",
                "The assessment is not wrong but for his mother the time total is wrong.",
                "The physician time is not wrong but during a previous encounter the assessment was wrong.",
                "The stated physician time was not copied from an earlier encounter.",
                "The total fluid intake is wrong.", "The total symptom score belongs to yesterday's appointment."):
            notes=self.notes+'\n\n'+suffix
            with self.subTest(suffix=suffix):
                answers,_=self.run_case(self.rebase(notes),notes=notes)
                self.assertEqual(answers['cell_13']['status'],'supported',answers['cell_13']['review_reasons'])
                self.assertEqual(answers['cell_17']['status'],'supported',answers['cell_17']['review_reasons'])

    def test_mixed_account_predicates_bind_each_negation_to_its_own_subject(self):
        for suffix,held,retained in (
                ('The assessment is not wrong but the time total is wrong.','cell_17','cell_13'),
                ('The time total is not wrong but the assessment is wrong.','cell_13','cell_17'),
                ('The assessment is wrong but the time total is not wrong.','cell_13','cell_17'),
                ('The time total is wrong whereas the assessment is not wrong.','cell_17','cell_13'),
                ('The assessment is not wrong; the time total has an unresolved qualification.','cell_17','cell_13'),
                ('Do not disregard the above assessment and time calculation; the assessment is wrong.','cell_13','cell_17'),
                ('Disregard the assessment; the time total is not wrong.','cell_13','cell_17'),
                ('The assessment is not wrong but now the time total is wrong.','cell_17','cell_13'),
                ('The time total is not wrong but on reconsideration the assessment is wrong.','cell_13','cell_17'),
                ('The assessment is not wrong but after checking the time total has an unresolved qualification.','cell_17','cell_13')):
            notes=self.notes+'\n\n'+suffix
            with self.subTest(suffix=suffix):
                answers,_=self.run_case(self.raw(),notes=notes)
                self.assertEqual(answers[held]['status'],'conflict')
                self.assertEqual(answers[retained]['status'],'supported',answers[retained]['review_reasons'])

    def test_unknown_outer_qualification_cannot_be_discarded_for_embedded_integrity(self):
        for suffix,held,retained in (
                ('It is false that the time total is not wrong.','cell_17','cell_13'),
                ('It is uncertain whether the assessment is not wrong.','cell_13','cell_17'),
                ('Depending on verification, the time total is not wrong.','cell_17','cell_13'),
                ('After assuming the time total is not wrong.','cell_17','cell_13'),
                ('Following verification the assessment is not wrong.','cell_13','cell_17'),
                ('Without confirmation, the assessment is not wrong.','cell_13','cell_17'),
                ('It is false that his mother confirmed the time total is not wrong.','cell_17','cell_13'),
                ("It is uncertain whether yesterday's account proves the assessment is not wrong.",'cell_13','cell_17')):
            notes=self.notes+'\n\n'+suffix
            with self.subTest(suffix=suffix):
                answers,_=self.run_case(self.raw(),notes=notes)
                self.assertEqual(answers[held]['status'],'conflict')
                self.assertEqual(answers[retained]['status'],'supported',answers[retained]['review_reasons'])

    def test_account_qualification_does_not_erase_global_or_unresolved_source_scope(self):
        for suffix in (
                'Following rejection of all earlier findings, the assessment is not wrong.',
                'Following verification the assessment is not wrong; all earlier findings are invalid.',
                'Following a hypothetical example, the assessment is not wrong.',
                'Following those statements, the assessment is not wrong.'):
            notes=self.notes+'\n\n'+suffix
            with self.subTest(suffix=suffix):
                answers,_=self.run_case(self.raw(),notes=notes)
                self.assertEqual(answers['cell_13']['status'],'conflict')
                self.assertEqual(answers['cell_17']['status'],'conflict')

    def test_negated_copy_before_time_account_does_not_change_source_owner(self):
        notes=self.notes.replace('Office E/M selection', 'The stated physician time was not copied from an earlier encounter.\nOffice E/M selection')
        raw=self.rebase(notes)
        # Insertion exactly at a retained value's start must move that value,
        # rather than make the newly inserted integrity sentence its evidence.
        basis=next(f for f in raw['facts'] if f['id']=='f34')
        basis['value_span']=span(notes,'Office E/M selection is based on total physician time on the date of service')
        units,_=generation.source_units(notes,self.fields)
        refs=[basis['value_span'],basis['subject']['name_span'],basis['timing']['span'],basis['unit_span']]
        basis['source_unit_ids']=sorted({u['id'] for u in units for ref in refs if ref and u['start']<=ref['start']<ref['end']<=u['end']})
        answers,_=self.run_case(raw,notes=notes)
        self.assertEqual(answers['cell_17']['status'],'supported',answers['cell_17']['review_reasons'])
        context=source_context(notes,units)
        for unit in units:
            if 'Office E/M selection' in unit['quote'] or 'Dr. Farrow personally spent' in unit['quote']:
                self.assertTrue(owned_current(context,unit))

    def test_treating_clinician_headers_obey_their_source_owner_and_encounter(self):
        for section in ("Mother's history:", 'Previous encounter:'):
            notes=('Patient: Synthetic Mira Lane\nTreating clinician: Dr. Mara Voss\n'
                +section+'\nTreating clinician: Dr. Quinn\nCurrent patient: Synthetic Mira Lane\n'
                'Treating clinician: Dr. Dana Stone\n')
            context=source_context(notes)
            self.assertTrue(clinician_matches(context,'Voss'))
            self.assertTrue(clinician_matches(context,'Stone'))
            self.assertFalse(clinician_matches(context,'Quinn'))

    def test_separate_paragraph_exclusion_cannot_disappear(self):
        notes=self.notes+'\n\nThe total excludes time spent on an additional separately reported service.'
        answers,_=self.run_case(self.rebase(notes),notes=notes)
        self.assertEqual(answers['cell_17']['status'],'conflict')
        self.assertEqual(answers['cell_13']['status'],'supported')


class StructuredClinicalContextTests(SimpleTestCase):
    """Exact CRLF synthetic heldout source, approved definitions and test replies."""
    run_case=ClinicalContextGenerationTests.run_case
    rebase=ClinicalContextGenerationTests.rebase

    def setUp(self):
        self.case=json.loads((FIXTURE.parent/'iris_clinical_constructed.json').read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))

    def raw(self):return deepcopy(self.case['raw'])
    def proposal(self):return deepcopy(self.case['proposal'])

    def test_complete_exact_source_and_approved_template_have_thirty_one_supported_three_missing(self):
        self.assertEqual(digest(self.notes),self.case['provenance']['source_sha256'])
        self.assertIn('\r\n',self.notes)
        answers,calls=self.run_case()
        self.assertEqual(len(calls),3)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':31,'missing':3})
        self.assertEqual([k for k,a in answers.items() if a['status']=='missing'],['cell_0','cell_15','cell_16'])
        self.assertEqual(answers['cell_29']['text'],'Heartburn')
        self.assertEqual((answers['cell_31']['text'],answers['cell_32']['text']),('22','32'))
        self.assertIn('if symptoms persist',answers['cell_30']['text'])
        self.assertIn('no specimen was obtained',answers['cell_30']['text'])
        self.assertIn('no longer taking that antacid',answers['cell_8']['text'])
        self.assertNotIn('separately reported services',answers['cell_33']['text'])

    def test_missing_summary_current_cessation_or_complete_nonperformance_stays_held(self):
        for identity,key in [('q12','cell_8'),('q19','cell_18'),('q31','cell_30'),('q32','cell_30')]:
            raw=self.raw();raw['facts']=[f for f in raw['facts'] if f['id']!=identity];proposal=self.proposal()
            for row in proposal['fields']:row['fact_ids']=[f for f in row['fact_ids'] if f!=identity]
            with self.subTest(identity=identity):self.assertEqual(self.run_case(raw,proposal)[0][key]['status'],'conflict')

    def test_pointer_denial_is_not_a_ros_summary_permission(self):
        before='There are no additional findings beyond the heartburn described above.'
        for after in ('The findings described above are incorrect.','There are no valid findings described above.'):
            notes=self.notes.replace(before,after)
            with self.subTest(after=after):
                answers,_=self.run_case(self.rebase(notes),notes=notes)
                self.assertNotEqual(answers['cell_18']['status'],'supported')
                self.assertNotEqual(answers['cell_4']['status'],'supported')

    def test_compound_cessation_cannot_change_owner_or_historical_section(self):
        before='A two-week trial of an over-the-counter antacid ended last month; she is no longer taking that antacid.'
        for after in ("Her mother's two-week trial of an over-the-counter antacid ended last month; she is no longer taking that antacid.",'Previous encounter:\r\n'+before+'\r\nCurrent encounter:'):
            notes=self.notes.replace(before,after)
            with self.subTest(after=after):self.assertEqual(self.run_case(self.rebase(notes),notes=notes)[0]['cell_8']['status'],'conflict')

    def test_new_literal_negatives_do_not_accept_foreign_subject_past_timing_or_clipped_values(self):
        for identity,key in [('q9','cell_6'),('q19','cell_18'),('q20','cell_19'),('q22','cell_21'),('q25','cell_24'),('q32','cell_30')]:
            for mode in ('subject','timing','clipped'):
                raw=self.raw();f=next(f for f in raw['facts'] if f['id']==identity)
                if mode=='subject':
                    f['subject']={'kind':'other','name_span':span(self.notes,'Synthetic Iris Vale')}
                    if 2 not in f['source_unit_ids']:f['source_unit_ids'].append(2)
                elif mode=='timing':f['timing']['kind']='past'
                else:
                    value=self.notes[f['value_span']['start']:f['value_span']['end']];start=f['value_span']['start']+value.rfind(' ')+1
                    f['value_span']={'start':start,'end':f['value_span']['end']}
                with self.subTest(identity=identity,mode=mode):self.assertEqual(self.run_case(raw)[0][key]['status'],'conflict')

    def test_hypothetical_or_wrong_day_plan_cannot_gain_conditional_plan_permission(self):
        for before,after in [('Upper endoscopy is requested for a later date if symptoms persist.','If this were a real patient, upper endoscopy might be requested.'),('Plan\r\n','Previous visit:\r\nPlan\r\n')]:
            notes=self.notes.replace(before,after)
            with self.subTest(after=after):self.assertEqual(self.run_case(self.rebase(notes),notes=notes)[0]['cell_30']['status'],'conflict')
