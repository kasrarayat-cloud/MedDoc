"""v14 completeness: immutable retained v13 replies and authored offline repairs.

Constructed stage responses are test proposals, never claimed provider output.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.tests.test_semantic_generation import fact, inventory_api_facts, checker, span

FIXTURE=Path(__file__).with_name('fixtures')/'nadia_supporting_retained.json'
V14=semantic.ENCOUNTER_SUPPORT_SCOPE_CONTRACT
V13=semantic.CLINICAL_LITERAL_SCOPE_CONTRACT

class EncounterSupportingFactsTests(SimpleTestCase):
    def setUp(self):
        self.case=json.loads(FIXTURE.read_text())
        self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))

    def raw(self,complete=False,notes=None):
        notes=self.notes if notes is None else notes
        units,_=generation.source_units(notes,self.fields)
        raw=semantic.resolve_source_references(notes,units,deepcopy(self.case['extractor']),reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        if complete:
            for identity,marker in (('support_work','Total physician time'),('support_exclusions','This total')):
                unit=next(u for u in units if u['quote'].startswith(marker))
                raw['facts'].append(fact(notes,self.fields,identity,unit['quote'].removesuffix('.'),kind='other',
                    polarity='negated' if 'does not include' in unit['quote'] else 'affirmed'))
        return raw

    def facts(self,raw=None,scope=V14,notes=None):
        notes=self.notes if notes is None else notes
        units,_=generation.source_units(notes,self.fields)
        return semantic.validate_facts(notes,units,self.raw(notes=notes) if raw is None else raw,scope_contract=scope,timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def proposal(self,complete=False):
        p=deepcopy(self.case['assigner'])
        if complete:
            next(r for r in p['fields'] if r['key']=='cell_5')['fact_ids'].append('f7')
            next(r for r in p['fields'] if r['key']=='cell_17')['fact_ids']+=['support_work','support_exclusions']
        return p

    def assign(self,raw=None,proposal=None,scope=V14,notes=None,definitions=None):
        notes=self.notes if notes is None else notes
        return semantic._assign(notes,self.fields,definitions or self.definitions,self.facts(raw,scope,notes),proposal or self.proposal(),scope_contract=scope,timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)

    def test_retained_v13_stage_replies_preserve_historical_sixteen_and_two(self):
        self.assertEqual(hashlib.sha256(self.notes.encode()).hexdigest(),self.case['provenance']['source_sha256'])
        calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertNotIn('encounter_support_inventory',payload)
            self.assertNotIn(semantic.ENCOUNTER_SUPPORT_INSTRUCTIONS,instructions)
            return deepcopy(self.case[role])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V13)
        self.assertEqual(calls,[('extractor',1),('assigner',1),('checker',1)])
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
        for key,expected in self.case['saved_answers'].items():
            self.assertEqual({k:answers[key][k] for k in expected},expected)

    def test_v14_unchanged_retained_assignment_holds_both_incomplete_narratives(self):
        answers=self.assign()
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':14,'conflict':2,'missing':2})
        self.assertIn('eight months ago',' '.join(answers['cell_5']['review_reasons']))
        self.assertIn('including review',' '.join(answers['cell_17']['review_reasons']))
        self.assertIn('This total excludes',' '.join(answers['cell_17']['review_reasons']))
        self.assertEqual(answers['cell_16']['text'],'36')
        before=self.assign(scope=V13)
        for key in set(answers)-{'cell_5','cell_17'}:
            self.assertEqual((answers[key]['text'],answers[key]['status']),(before[key]['text'],before[key]['status']))

    def test_synthetic_complete_extraction_and_selection_preserves_standalone_support(self):
        raw=self.raw(complete=True)
        self.assertFalse({k:f['issues'] for k,f in self.facts(raw).items() if f['issues']})
        answers=self.assign(raw,self.proposal(True))
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
        self.assertIn('same gastroenterologist eight months ago',answers['cell_5']['text'])
        self.assertIn('established patient',answers['cell_5']['text'])
        self.assertIn('36 minutes, including review of available records, obtaining history, performing the examination, counseling and documentation',answers['cell_17']['text'])
        self.assertIn('excludes clinical staff time and time for separately reported services',answers['cell_17']['text'])
        self.assertIn('based on total physician time',answers['cell_17']['text'])
        self.assertEqual(answers['cell_16']['text'],'36')
        self.assertIn('15 minutes',answers['cell_6']['text'])
        self.assertFalse(any(a['reviewed'] for a in answers.values()))

    def test_synthetic_repair_can_select_existing_history_but_not_invent_time_facts(self):
        calls=[]
        repaired=self.proposal()
        next(r for r in repaired['fields'] if r['key']=='cell_5')['fact_ids'].append('f7')
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertEqual(len(payload['encounter_support_inventory']),3)
            self.assertTrue(instructions.endswith(semantic.ENCOUNTER_SUPPORT_INSTRUCTIONS))
            if role=='extractor': return deepcopy(self.case['extractor'])
            if role=='checker': return checker(repaired if attempt==2 else self.proposal())
            if attempt==1: return self.proposal()
            self.assertEqual(set(payload['repair_keys']),{'cell_5','cell_17'})
            self.assertEqual(set(payload['local_assignment_findings']),{'cell_5','cell_17'})
            return {'fields':[r for r in repaired['fields'] if r['key'] in payload['repair_keys']]}
        answers=semantic.run(self.notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V14)
        self.assertEqual(calls,[('extractor',1),('assigner',1),('checker',1),('assigner',2),('checker',2)])
        self.assertEqual(answers['cell_5']['status'],'supported')
        self.assertEqual(answers['cell_17']['status'],'conflict')
        self.assertEqual(answers['cell_17']['text'],'')

    def test_synthetic_fresh_three_stage_response_includes_support_without_extra_calls(self):
        units,_=generation.source_units(self.notes,self.fields)
        extraction=inventory_api_facts(self.notes,units,self.raw(True)['facts'])
        proposal=self.proposal(True)
        calls=[]
        def send(role,attempt,payload,schema,instructions):
            calls.append((role,attempt))
            self.assertEqual(len(payload['encounter_support_inventory']),3)
            return deepcopy({'extractor':extraction,'assigner':proposal,'checker':checker(proposal)}[role])
        answers=semantic.run(self.notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V14)
        self.assertEqual(len(calls),3)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})

    def test_approved_definition_controls_obligations_without_label_guessing(self):
        for key,change in (
            ('cell_5',{'scope':{'subject':'encounter','temporality':'current','polarity':'any'}}),
            ('cell_5',{'answer_mode':'atomic'}),('cell_5',{'meaning':'The current visit setting only.'}),
            ('cell_5',{'meaning':'The patient status: new or established only.'}),
            ('cell_17',{'meaning':'The E/M selection basis only, without supporting activities.'}),
            ('cell_17',{'meaning':'The current symptoms.'}),
            ('cell_17',{'scope':{'subject':'other','temporality':'any','polarity':'any'}})):
            definitions=deepcopy(self.definitions); definitions[key].update(change)
            with self.subTest(key=key,change=change):
                self.assertFalse(any(o['field_key']==key for o in semantic._encounter_support_inventory(self.notes,definitions)))
        self.assertFalse(any(o['field_key'] in ('cell_12','cell_16') for o in semantic._encounter_support_inventory(self.notes,self.definitions)))

    def test_partial_or_evidence_only_support_cannot_repay_obligation(self):
        for identity,quote in (('f7','eight months ago'),('f7','seen by this same gastroenterologist'),('support_work','documentation'),('support_exclusions','clinical staff time')):
            raw=self.raw(True); row=next(r for r in raw['facts'] if r['id']==identity)
            start=self.notes.index(quote,row['value_span']['start']); row['value_span']={'start':start,'end':start+len(quote)}
            answer=self.assign(raw,self.proposal(True))['cell_5' if identity=='f7' else 'cell_17']
            with self.subTest(identity=identity,quote=quote):
                self.assertEqual(answer['status'],'conflict')
                self.assertTrue(any('encounter support' in r for r in answer['review_reasons']))
        p=self.proposal(); next(r for r in p['fields'] if r['key']=='cell_17')['fact_ids'].append('f35')
        self.assertEqual(self.assign(proposal=p)['cell_17']['status'],'conflict')

    def test_wrong_subject_or_timing_cannot_repay_support(self):
        for identity in ('f7','support_work','support_exclusions'):
            for mode in ('foreign_subject','wrong_timing'):
                raw=self.raw(True); row=next(r for r in raw['facts'] if r['id']==identity)
                if mode=='foreign_subject':
                    row['subject']['kind']='other'
                    row['subject']['name_span']=span(self.notes,'Synthetic Nadia Fenwick')
                    if 2 not in row['source_unit_ids']: row['source_unit_ids'].append(2)
                else: row['timing']['kind']='future'
                with self.subTest(identity=identity,mode=mode):
                    self.assertEqual(self.assign(raw,self.proposal(True))['cell_5' if identity=='f7' else 'cell_17']['status'],'conflict')

    def test_inventory_general_paraphrases_and_clinicians_preserve_source(self):
        for history in ('Established patient; previously seen by the same physician six weeks ago.','This is an established patient who had been seen by this same neurologist two years ago.','Established patient: last seen by same clinician three months ago.'):
            for total,basis in (
                ('Total physician time: 42 minutes, including chart review, examination and counseling.','Time-based E/M selection.'),
                ('Total clinician time today is 28 minutes; spent on history and documentation.','E/M selection: time-based.'),
                ('The physician spent 32 minutes today, including examination and counseling.','Evaluation and management level was based on clinician time.')):
                notes='Patient: Synthetic Taylor Reed\nVisit: In-person office consultation. '+history+'\n\n'+total+' This total excludes nursing time and separately billed procedures. '+basis
                inventory=semantic._encounter_support_inventory(notes,self.definitions)
                with self.subTest(history=history,total=total,basis=basis):
                    self.assertEqual(Counter(o['kind'] for o in inventory),{'patient_status_history':1,'physician_time_activities':1,'physician_time_exclusions':1})
                    for obligation in inventory:
                        s=obligation['source']; self.assertEqual(notes[s['start']:s['end']],s['quote'])

    def test_unrelated_history_exclusions_and_foreign_patient_are_not_added(self):
        original=semantic._encounter_support_inventory(self.notes,self.definitions)
        for suffix in ('\n\nPast surgery eight years ago. The surgeon reviewed the scar.',
            '\n\nFamily history: the sibling is an established patient who was seen by this same physician two months ago.',
            '\n\nSymptoms last 15 minutes. This total excludes meals.',
            '\n\nTotal nursing time was 12 minutes, including observations. This total excludes travel.',
            '\n\nAnother patient: Established patient; previously seen by the same physician six weeks ago. Total physician time: 42 minutes, including chart review. This total excludes staff time. Time-based E/M selection.'):
            with self.subTest(suffix=suffix):
                self.assertEqual(semantic._encounter_support_inventory(self.notes+suffix,self.definitions),original)
        foreign=self.notes+'\n\nPatient: Synthetic Other Person\nEstablished patient; previously seen by the same physician six weeks ago.'
        foreign_inventory=semantic._encounter_support_inventory(foreign,self.definitions)
        self.assertEqual([o for o in foreign_inventory if o['kind']!='patient_identity_ambiguity'],original)
        self.assertEqual({o['field_key'] for o in foreign_inventory if o['kind']=='patient_identity_ambiguity'},{'cell_5','cell_17'})

    def test_deictic_exclusion_needs_adjacent_total_in_same_paragraph(self):
        for gap in ('\n\n',' Other consultation took five minutes. ',' Nursing time was 20 minutes. '):
            notes='Total physician time: 36 minutes, including counseling.'+gap+'This total excludes staff time. Time-based E/M selection.'
            self.assertFalse(any(o['kind']=='physician_time_exclusions' for o in semantic._encounter_support_inventory(notes,self.definitions)))

    def test_separate_values_cover_same_occurrence_but_no_missing_words_or_foreign_copy(self):
        raw=self.raw(True)
        original=next(r for r in raw['facts'] if r['id']=='support_work')
        raw['facts'].remove(original)
        quotes=('Total physician time on the date of service was 36 minutes',
            'including review of available records, obtaining history, performing the examination, counseling and documentation')
        for index,quote in enumerate(quotes):
            raw['facts'].append(fact(self.notes,self.fields,'work_'+str(index),quote,kind='other'))
        proposal=self.proposal(True)
        row=next(r for r in proposal['fields'] if r['key']=='cell_17')
        row['fact_ids'].remove('support_work'); row['fact_ids']+=['work_0','work_1']
        self.assertEqual(self.assign(raw,proposal)['cell_17']['status'],'supported')
        # The number's evidence cannot cover the omitted activity connector.
        raw['facts'][-1]['value_span']['start']+=len('including ')
        self.assertEqual(self.assign(raw,proposal)['cell_17']['status'],'conflict')
        facts=self.facts(self.raw(True))
        obligation=next(o for o in semantic._encounter_support_inventory(self.notes,self.definitions) if o['kind']=='physician_time_activities')
        moved=deepcopy(facts['support_work'])
        moved['value_evidence']['start']+=len(self.notes)
        moved['value_evidence']['end']+=len(self.notes)
        self.assertFalse(semantic._encounter_support_covered(self.notes,obligation,[moved]))

    def test_complete_current_status_composite_keeps_past_clause(self):
        raw=self.raw(True)
        row=next(r for r in raw['facts'] if r['id']=='f6')
        unit=next(u for u in generation.source_units(self.notes,self.fields)[0] if u['id']==7)
        row['value_span']={'start':unit['start'],'end':unit['end']-1}
        proposal=self.proposal(True)
        next(r for r in proposal['fields'] if r['key']=='cell_5')['fact_ids'].remove('f7')
        answer=self.assign(raw,proposal)['cell_5']
        self.assertEqual(answer['status'],'supported')
        self.assertIn('eight months ago',answer['text'])

    def test_negative_exclusion_paraphrase_requires_complete_literal_and_negated_polarity(self):
        notes=self.notes.replace('This total excludes','This total does not include')
        raw=self.raw(True,notes)
        answers=self.assign(raw,self.proposal(True),notes=notes)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
        self.assertIn('This total does not include clinical staff time',answers['cell_17']['text'])
        row=next(r for r in raw['facts'] if r['id']=='support_exclusions')
        row['polarity']='affirmed'
        self.assertEqual(self.assign(raw,self.proposal(True),notes=notes)['cell_17']['status'],'conflict')
        # Historical v13 cannot acquire the new literal admission.
        self.assertTrue(self.facts(raw,scope=V13,notes=notes)['support_exclusions']['issues'] or
            self.assign(raw,self.proposal(True),scope=V13,notes=notes)['cell_13']['status']!='supported')

    def test_varied_same_clinicians_and_past_intervals_preserve_complete_answers(self):
        for replacements in ((('gastroenterology','cardiology'),('gastroenterologist','cardiologist'),('eight months','six weeks')),
                (('gastroenterology','neurology'),('gastroenterologist','neurologist'),('eight months','two years'))):
            with self.subTest(replacements=replacements):
                self.setUp()
                content=json.dumps(self.case)
                for original,replacement in replacements: content=content.replace(original,replacement)
                self.case=json.loads(content)
                self.notes,self.fields,self.definitions=(self.case[k] for k in ('notes','fields','definitions'))
                answers=self.assign(self.raw(True),self.proposal(True))
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
                self.assertIn(replacements[-1][-1]+' ago',answers['cell_5']['text'])

    def test_repeated_same_identity_header_cannot_erase_support_obligations(self):
        original=semantic._encounter_support_inventory(self.notes,self.definitions)
        for header in ('Patient: Synthetic Nadia Fenwick','Patient name: Synthetic Nadia Fenwick',
                'PATIENT FULL NAME: synthetic nadia fenwick'):
            notes=self.notes+'\n\n'+header
            with self.subTest(header=header):
                self.assertEqual(semantic._encounter_support_inventory(notes,self.definitions),original)
                answers=self.assign(notes=notes)
                for key in ('cell_5','cell_17'):
                    self.assertEqual(answers[key]['status'],'conflict')
                    self.assertTrue(any('encounter support' in r for r in answers[key]['review_reasons']))

    def test_distinct_identity_sections_never_borrow_foreign_support_or_choose_first_header(self):
        original=semantic._encounter_support_inventory(self.notes,self.definitions)
        foreign=('Patient: Synthetic Taylor Reed\nEstablished patient; previously seen by the same physician six weeks ago. '
            'Total physician time: 42 minutes, including chart review. This total excludes nursing time. Time-based E/M selection.')
        trailing=self.notes+'\n\n'+foreign
        inventory=semantic._encounter_support_inventory(trailing,self.definitions)
        self.assertEqual([o for o in inventory if o['kind']!='patient_identity_ambiguity'],original)
        for notes in (trailing,foreign+'\n\n'+self.notes):
            with self.subTest(primary_first=notes==trailing):
                unresolved=[o for o in semantic._encounter_support_inventory(notes,self.definitions) if o['kind']=='patient_identity_ambiguity']
                self.assertEqual({o['field_key'] for o in unresolved},{'cell_5','cell_17'})
                self.assertTrue(all(not semantic._encounter_support_covered(notes,o,[]) for o in unresolved))
        returned=trailing+'\n\nPatient: Synthetic Nadia Fenwick\nEstablished patient; previously seen by the same physician six weeks ago.'
        returned_inventory=semantic._encounter_support_inventory(returned,self.definitions)
        self.assertEqual(Counter(o['kind'] for o in returned_inventory),{'patient_identity_ambiguity':2,'patient_status_history':2,'physician_time_activities':1,'physician_time_exclusions':1})

    def test_full_pipeline_checker_pass_never_overrides_repeated_or_foreign_header_holds(self):
        original_raw=self.raw()
        for position in ('before','after'):
            for identity in ('Synthetic Nadia Fenwick','Synthetic Taylor Reed'):
                header='Patient: '+identity+'\n\n'
                notes=header+self.notes if position=='before' else self.notes+'\n\n'+header
                shift=len(header) if position=='before' else 0
                units,_=generation.source_units(notes,self.fields)
                raw=deepcopy(original_raw)
                for f in raw['facts']:
                    refs=[f['value_span'],f['subject']['name_span'],f['timing']['span'],f['unit_span']]
                    if f['scale']: refs.append(f['scale']['span'])
                    for ref in filter(None,refs):
                        ref['start']+=shift; ref['end']+=shift
                    f['source_unit_ids']=sorted({u['id'] for ref in filter(None,refs) for u in units if u['start']<=ref['start']<ref['end']<=u['end']})
                extraction=inventory_api_facts(notes,units,raw['facts'])
                calls=[]
                def send(role,attempt,payload,schema,instructions):
                    calls.append((role,attempt))
                    if role=='extractor': return extraction
                    if role=='checker': return checker(self.proposal())
                    proposal=self.proposal()
                    if attempt==2:
                        self.assertTrue({'cell_5','cell_17'} <= set(payload['repair_keys']))
                        proposal['fields']=[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]
                    return proposal
                with self.subTest(position=position,identity=identity):
                    answers=semantic.run(notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V14)
                    self.assertEqual(len(calls),5)
                    for key in ('cell_5','cell_17'):
                        self.assertEqual(answers[key]['status'],'conflict')
                        self.assertEqual(answers[key]['text'],'')
                    self.assertNotEqual(answers['cell_0']['status'],'supported')
                    if identity!='Synthetic Nadia Fenwick':
                        for key in ('cell_5','cell_17'):
                            self.assertTrue(any('ownership unresolved' in reason for reason in answers[key]['review_reasons']))

    def test_full_pipeline_support_preserving_definition_qualifiers_do_not_waive_holds(self):
        for suffix in (' Do not omit supporting source facts.',
                ' Include supporting history only when documented.',
                ' Include supporting details without inferring billing eligibility.'):
            definitions=deepcopy(self.definitions)
            for key in ('cell_5','cell_17'): definitions[key]['meaning']+=suffix
            calls=[]
            def send(role,attempt,payload,schema,instructions):
                calls.append((role,attempt))
                if role=='extractor': return deepcopy(self.case['extractor'])
                if role=='checker': return checker(self.proposal())
                proposal=self.proposal()
                if attempt==2:
                    self.assertEqual(set(payload['repair_keys']),{'cell_5','cell_17'})
                    proposal['fields']=[r for r in proposal['fields'] if r['key'] in payload['repair_keys']]
                return proposal
            with self.subTest(suffix=suffix):
                answers=semantic.run(self.notes,self.fields,definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V14)
                self.assertEqual(len(calls),5)
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':14,'conflict':2,'missing':2})
                for key in ('cell_5','cell_17'):
                    self.assertTrue(any('encounter support' in r for r in answers[key]['review_reasons']))

    def test_full_pipeline_foreign_heading_does_not_require_or_admit_its_support(self):
        for heading in ('Mother','Another patient','Family history:','Sibling','Aunt','Grandmother',
                'Friend','Spouse','Child','Patient Synthetic Other Person',
                "Mother's history",'Mother history','Sibling visit','Previous encounter','Historical visit'):
            notes=self.notes+'\n\n'+heading+'\n\nEstablished patient; previously seen by the same physician six weeks ago.'
            raw=self.raw(True,notes)
            raw['facts'].append(fact(notes,self.fields,'foreign_history',
                'previously seen by the same physician six weeks ago',kind='history',
                timing='past',timing_quote='six weeks ago'))
            units,_=generation.source_units(notes,self.fields)
            extraction=inventory_api_facts(notes,units,raw['facts'])
            original=semantic._encounter_support_inventory(self.notes,self.definitions)
            self.assertEqual(semantic._encounter_support_inventory(notes,self.definitions),original)
            baseline=None
            for scope,pick_foreign in ((V13,False),(V14,False),(V14,True)):
                proposal=self.proposal(True)
                if pick_foreign:
                    next(r for r in proposal['fields'] if r['key']=='cell_5')['fact_ids'].append('foreign_history')
                def send(role,attempt,payload,schema,instructions):
                    if role=='extractor': return deepcopy(extraction)
                    if role=='checker': return checker(proposal)
                    result=deepcopy(proposal)
                    if attempt==2:
                        result['fields']=[r for r in result['fields'] if r['key'] in payload['repair_keys']]
                    return result
                with self.subTest(heading=heading,scope=scope,pick_foreign=pick_foreign):
                    answers=semantic.run(notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=scope)
                    if pick_foreign:
                        self.assertEqual(answers['cell_5']['status'],'conflict')
                        self.assertEqual(answers['cell_5']['text'],'')
                        self.assertTrue(any('foreign patient or relative section' in r for r in answers['cell_5']['review_reasons']))
                    else:
                        actual=(answers['cell_5']['status'],answers['cell_5']['text'])
                        if scope==V13: baseline=actual
                        self.assertEqual(actual,baseline)
                        self.assertNotIn('six weeks ago',answers['cell_5']['text'])
                        if heading!='Family history:':
                            self.assertEqual(answers['cell_5']['status'],'supported')
                            self.assertIn('eight months ago',answers['cell_5']['text'])

    def test_explicit_patient_header_resumes_support_after_foreign_heading(self):
        notes=('Patient: Synthetic Taylor Reed\n\nMother\n\n'
            'Established patient; previously seen by the same physician six weeks ago.\n\n'
            'Patient: Synthetic Taylor Reed\n'
            'Established patient; previously seen by the same physician two years ago.')
        inventory=semantic._encounter_support_inventory(notes,self.definitions)
        self.assertEqual(len(inventory),1)
        self.assertIn('two years ago',inventory[0]['source']['quote'])

    def test_negated_narrowing_instructions_preserve_support_obligations(self):
        for suffix in (' Do not answer without supporting details.',
                ' Do not limit the answer to the E/M selection basis only.',
                ' Never return only the E/M selection basis.'):
            definitions=deepcopy(self.definitions)
            for key in ('cell_5','cell_17'): definitions[key]['meaning']+=suffix
            with self.subTest(suffix=suffix):
                self.assertEqual(len(semantic._encounter_support_inventory(self.notes,definitions)),3)
                answers=self.assign(definitions=definitions)
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':14,'conflict':2,'missing':2})

    def test_restriction_on_another_destination_does_not_remove_support(self):
        definitions=deepcopy(self.definitions)
        definitions['cell_5']['meaning']+=' Omit supporting activities.'
        definitions['cell_17']['meaning']+=' Omit prior encounter history.'
        self.assertEqual(len(semantic._encounter_support_inventory(self.notes,definitions)),3)
        answers=self.assign(definitions=definitions)
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':14,'conflict':2,'missing':2})

    def test_time_support_can_belong_to_unnamed_clinician_with_exact_current_source(self):
        for negative in (False,True):
            notes=self.notes.replace('This total excludes','This total does not include') if negative else self.notes
            raw=self.raw(True,notes)
            for row in raw['facts']:
                if row['id'] in ('support_work','support_exclusions'):
                    row['subject']['kind']='clinician'
            with self.subTest(negative=negative):
                facts=self.facts(raw,notes=notes)
                self.assertFalse(facts['support_work']['issues'])
                self.assertFalse(facts['support_exclusions']['issues'])
                answers=self.assign(raw,self.proposal(True),notes=notes)
                self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':16,'missing':2})
                self.assertIn('clinical staff time',answers['cell_17']['text'])
                self.assertEqual(answers['cell_16']['text'],'36')
                wrong=deepcopy(raw)
                for row in wrong['facts']:
                    if row['id'] in ('support_work','support_exclusions'):
                        row['subject']['name_span']=span(notes,'Synthetic Nadia Fenwick')
                        row['source_unit_ids'].append(2)
                self.assertEqual(self.assign(wrong,self.proposal(True),notes=notes)['cell_17']['status'],'conflict')
        raw=self.raw(True)
        next(r for r in raw['facts'] if r['id']=='f7')['subject']['kind']='clinician'
        self.assertEqual(self.assign(raw,self.proposal(True))['cell_5']['status'],'conflict')

    def test_historical_physician_time_is_neither_required_nor_accepted_for_current_basis(self):
        work='Total physician time on the date of service was 42 minutes, including counseling and documentation'
        exclusion='This total excludes clinical staff time'
        basis='Office E/M selection is based on total physician time'
        for heading in ('Previous encounter','Historical visit','Prior consultation notes','Earlier office visit'):
            notes=self.notes+'\n\n'+heading+'\n\n'+work+'. '+exclusion+'. '+basis+'.'
            raw=self.raw(True,notes)
            for identity,quote in (('old_work',work),('old_exclusion',exclusion)):
                raw['facts'].append(fact(notes,self.fields,identity,quote,kind='other',
                    occurrence=1 if identity=='old_exclusion' else 0))
            units,_=generation.source_units(notes,self.fields)
            extraction=inventory_api_facts(notes,units,raw['facts'])
            self.assertEqual(semantic._encounter_support_inventory(notes,self.definitions),
                semantic._encounter_support_inventory(self.notes,self.definitions))
            for scope,pick_old in ((V13,False),(V14,False),(V14,True)):
                proposal=self.proposal(True)
                if pick_old:
                    next(r for r in proposal['fields'] if r['key']=='cell_17')['fact_ids']+=['old_work','old_exclusion']
                def send(role,attempt,payload,schema,instructions):
                    if role=='extractor': return deepcopy(extraction)
                    if role=='checker': return checker(proposal)
                    result=deepcopy(proposal)
                    if attempt==2: result['fields']=[r for r in result['fields'] if r['key'] in payload['repair_keys']]
                    return result
                with self.subTest(heading=heading,scope=scope,pick_old=pick_old):
                    answers=semantic.run(notes,self.fields,self.definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=scope)
                    if pick_old:
                        self.assertEqual(answers['cell_17']['status'],'conflict')
                        self.assertEqual(answers['cell_17']['text'],'')
                        self.assertTrue(any('non-current encounter section' in r for r in answers['cell_17']['review_reasons']))
                    else:
                        self.assertEqual(answers['cell_17']['status'],'supported')
                        self.assertIn('36 minutes',answers['cell_17']['text'])
                        self.assertNotIn('42 minutes',answers['cell_17']['text'])

    def test_section_owner_and_time_require_independent_explicit_resets(self):
        history='Established patient; previously seen by the same physician six weeks ago.'
        prefix='Patient: Synthetic Taylor Reed\n\n'
        for blocked in ("Mother's history","The mother's medical history","Her mother's visit",'Sibling visit','History for the mother'):
            for reset in ('','Current encounter\n\n'):
                notes=prefix+blocked+'\n\n'+reset+history
                self.assertEqual(semantic._encounter_support_inventory(notes,self.definitions),[])
            notes=prefix+blocked+'\n\nPatient: Synthetic Taylor Reed\n\n'+history
            self.assertEqual(len(semantic._encounter_support_inventory(notes,self.definitions)),1)
        for blocked in ('Previous encounter','Historical visit','Prior consultation records','Upcoming visit','Past encounters','Visit six months ago'):
            for reset in ('','Patient: Synthetic Taylor Reed\n\n','Examination\n\n'):
                notes=prefix+blocked+'\n\n'+reset+history
                self.assertEqual(semantic._encounter_support_inventory(notes,self.definitions),[])
            for reset in ('Current encounter','Present visit',"Today's consultation",'Current patient: Synthetic Taylor Reed'):
                notes=prefix+blocked+'\n\n'+reset+'\n\n'+history
                inventory=semantic._encounter_support_inventory(notes,self.definitions)
                self.assertEqual(len(inventory),1)
                self.assertIn('six weeks ago',inventory[0]['source']['quote'])
        for reset in ('Current encounter\n\nPatient: Synthetic Taylor Reed',
                'Patient: Synthetic Taylor Reed\n\nCurrent encounter',
                'Current patient: Synthetic Taylor Reed'):
            notes=prefix+"Mother's history\n\nPrevious encounter\n\n"+reset+'\n\n'+history
            self.assertEqual(len(semantic._encounter_support_inventory(notes,self.definitions)),1)

    def test_past_medical_history_is_not_a_different_encounter_header(self):
        notes=('Patient: Synthetic Taylor Reed\n\nPast medical history\n\n'
            'Hypertension.\n\nExamination\n\n'
            'Total physician time: 36 minutes, including counseling and documentation. '
            'This total excludes clinical staff time. Time-based E/M selection.')
        inventory=semantic._encounter_support_inventory(notes,self.definitions)
        self.assertEqual(Counter(o['kind'] for o in inventory),{'physician_time_activities':1,'physician_time_exclusions':1})

    def test_combined_explicit_status_only_scope_accepts_status_and_rejects_extra_history(self):
        for meaning in ('The visit setting and patient status only.',
                'The patient status and visit setting only.',
                'Only the visit setting and the patient status.',
                'The visit setting & patient status only.'):
            definitions=deepcopy(self.definitions)
            definitions['cell_5']['meaning']=meaning
            raw=self.raw(True)
            units,_=generation.source_units(self.notes,self.fields)
            extraction=inventory_api_facts(self.notes,units,raw['facts'])
            for add_history in (False,True):
                proposal=self.proposal(True)
                if not add_history:
                    next(r for r in proposal['fields'] if r['key']=='cell_5')['fact_ids'].remove('f7')
                def send(role,attempt,payload,schema,instructions):
                    if role=='extractor': return deepcopy(extraction)
                    if role=='checker': return checker(proposal)
                    result=deepcopy(proposal)
                    if attempt==2: result['fields']=[r for r in result['fields'] if r['key'] in payload['repair_keys']]
                    return result
                with self.subTest(meaning=meaning,add_history=add_history):
                    answers=semantic.run(self.notes,self.fields,definitions,send,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=V14)
                    self.assertEqual(answers['cell_5']['status'],'conflict' if add_history else 'supported')
                    if add_history:
                        self.assertTrue(any('approved narrative excludes' in r for r in answers['cell_5']['review_reasons']))
                    else:
                        self.assertIn('established patient',answers['cell_5']['text'])
                        self.assertNotIn('eight months ago',answers['cell_5']['text'])
                        foreign_notes=self.notes+'\n\nPatient: Synthetic Taylor Reed'
                        foreign=self.assign(self.raw(True,foreign_notes),proposal,notes=foreign_notes,definitions=definitions)
                        self.assertEqual(foreign['cell_5']['status'],'conflict')
        # A composite fact cannot hide the explicitly excluded history, even
        # if its metadata calls the whole established-status sentence current.
        row=next(r for r in raw['facts'] if r['id']=='f6')
        unit=next(u for u in units if u['id']==7)
        row['value_span']={'start':unit['start'],'end':unit['end']-1}
        self.assertEqual(self.assign(raw,proposal,definitions=definitions)['cell_5']['status'],'conflict')

    def test_explicit_basis_only_scope_rejects_support_without_weakening_broad_meaning(self):
        definitions=deepcopy(self.definitions)
        definitions['cell_17']['meaning']='The E/M selection basis only, without supporting activities.'
        raw=self.raw(True)
        full=self.proposal(True)
        narrow=deepcopy(full)
        next(r for r in narrow['fields'] if r['key']=='cell_17')['fact_ids']=['f36']
        self.assertEqual(self.assign(raw,narrow,definitions=definitions)['cell_17']['status'],'supported')
        self.assertEqual(self.assign(raw,full,definitions=definitions)['cell_17']['status'],'conflict')
        self.assertEqual(self.assign(raw,full)['cell_17']['status'],'supported')
        self.assertEqual(self.assign(raw,narrow)['cell_17']['status'],'conflict')
