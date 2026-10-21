"""Adversarial literal rendering, full-check and immutable-reload boundaries."""
from copy import deepcopy
import unittest
from uuid import uuid4
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from core import source_assertion_graph as graph
from core import source_assertion_generation as generation
from core.tests.test_source_assertion_graph import (
    IDENTITY, ref, fact, assertion, extraction, definitions, assignments, checker, base_case, run_case,
)


def stated_time_case(*, separately_reported=True, closed=True):
    """Constructed independent clinical total and typed E/M account claims."""
    extra=('Service date: 14 June 2027.\n'
           'Established outpatient office evaluation using time.\n'
           'Nora is a physician.\n'
           'Nora spent 33 minutes on this service date.\n'
           'Nora reviewed records for 5 minutes.\n'
           'Nora evaluated the patient for 22 minutes.\n'
           'Nora documented for 6 minutes.\n'
           'Staff time is excluded from this total.')
    if separately_reported:
        extra+='\nSeparately reported procedure time is excluded from this total.'
    notes,fields,defs,raw,_=base_case(extra)
    from documents.component_contracts import fixture
    definition=defs['field0']
    definition.update(meaning='Stated physician minutes',value_type='integer',answer_mode='atomic',
        scope={'subject':'clinician','temporality':'current','polarity':'any'})
    definition['component_contract']=fixture(fields[0],definition)
    raw['facts'].append(fact(notes,'ftime','33',subject='clinician',kind='measurement'))
    day=ref(notes,'14 June 2027')
    for identifier,role,value,quote,subject in (
        ('setting','service_setting','outpatient_office','outpatient office','patient'),
        ('status','patient_status','established','Established','patient'),
        ('basis','em_basis','time','using time','patient'),
        ('clinician','clinician_role','physician','Nora is a physician.','clinician')):
        raw['assertions'].append(assertion(notes,identifier,[],quote,kind='context',
            subject=subject,consumer_role=role,consumer_value=value))
    specs=[('total','time_total','Nora spent 33 minutes on this service date.','33','clinician','none'),
        ('w1','time_work','Nora reviewed records for 5 minutes.','5','clinician','none'),
        ('w2','time_work','Nora evaluated the patient for 22 minutes.','22','clinician','none'),
        ('w3','time_work','Nora documented for 6 minutes.','6','clinician','none'),
        ('staff','time_exclusion','Staff time is excluded from this total.',None,'staff','staff')]
    if separately_reported:
        specs.append(('separate','time_exclusion','Separately reported procedure time is excluded from this total.',None,'clinician','separately_reported'))
    relations=[]
    for identifier,role,quote,quantity,performer,exclusion in specs:
        unit=ref(notes,quote)['source_unit_id']
        local=lambda value:{'quote':value,'source_unit_id':unit,'occurrence':1}
        actor='Staff' if performer=='staff' else 'procedure' if identifier=='separate' else 'Nora'
        time={'performer':performer,'performer_ref':local(actor),'date_ref':day,
            'quantity_ref':local(quantity) if quantity else None,'unit_ref':local('minutes') if quantity else None,
            'exclusion':exclusion}
        raw['assertions'].append(assertion(notes,identifier,['ftime'] if identifier=='total' else [],quote,
            subject='clinician',kind=role,consumer_role=role,time=time,source_unit_ids=[unit,day['source_unit_id']]))
        if identifier!='total':
            relations.append({'id':'r_'+identifier,'kind':'account_includes' if role=='time_work' else 'account_excludes',
                'source_assertion_id':'total','target_assertion_ids':[identifier],'evidence_refs':[ref(notes,quote)]})
    owner=next(a for a in raw['assertions'] if a['id']=='total')
    account={'id':'account','owner_assertion_id':'total','date_ref':day,
        'total_ref':owner['time']['quantity_ref'],'unit_ref':owner['time']['unit_ref'],
        'included_assertion_ids':['w1','w2','w3'],'excluded_assertion_ids':['staff']+(['separate'] if separately_reported else []),
        'overlap_assertion_ids':[],'closed':closed}
    raw=extraction(notes,raw['facts'],raw['assertions'],relations,[account])
    return [notes,fields,defs,raw,assignments(fields,{'field0':['ftime']},{'field0':['total']})]


def office_time_result(result):
    from core import source_assertion_coding as coding
    interpretation=result['interpretation'];identity=interpretation['identity']
    inputs={key:identity[key] for key in ('patient_id','encounter_id','department_id','service_date','template_version_id')}
    inputs.update(notes=interpretation['notes'],answers=result['answers'],source_interpretation=interpretation,
        patient_identity={'display_name':identity['patient_display_name'],'reference':identity['patient_reference']},
        template={'fields_sha256':graph.digest(interpretation['fields']),'definitions_sha256':graph.digest(interpretation['definitions'])})
    return coding.office_time_facts(SimpleNamespace(inputs=inputs,config={'clinical_source_contract':coding.CONTRACT}))


class SourceAssertionGenerationTests(unittest.TestCase):
    def measurement_case(self, phrase='Weight is 71 kg.', value='71', unit='kg', scale=None, *, labelled=True):
        case=list(base_case(phrase))
        fields,defs=definitions(('Weight' if scale is None else 'Score',))
        case[1:3]=fields,defs
        component=defs['field0']['component_contract']['components'][0]
        component.update(value_type='number',unit_requirement='documented')
        if labelled:
            defs['field0']['component_contract']['rendering']='labelled'
            component['label']=fields[0]['label']
        f=fact(case[0],'f2',value,kind='measurement')
        if unit is not None:f.update(unit=unit,unit_span=ref(case[0],unit))
        if scale is not None:f['scale']={**scale,'span':ref(case[0],scale['span'])}
        case[3]['facts'].append(f)
        case[3]['assertions'].append(assertion(case[0],'a2',['f2'],phrase))
        case[3]=extraction(case[0],case[3]['facts'],case[3]['assertions'])
        case[4]=assignments(fields,{'field0':['f2']})
        return case

    def test_documented_measurement_keeps_exact_display_unit_and_typed_number(self):
        for labelled in (True,False):
            case=self.measurement_case(labelled=labelled)
            result,calls=run_case(case)
            answer=result['answers']['field0']
            self.assertEqual(answer['status'],'supported')
            self.assertEqual(answer['text'],('Weight: ' if labelled else '')+'71 kg')
            self.assertEqual(answer['components'][0]['value'],71)
            self.assertEqual(answer['facts'][0]['value_evidence']['quote'],'71')
            self.assertEqual(len(calls),3)
            self.assertEqual(generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation']),answer)

    def test_documented_score_keeps_own_scale_without_inventing_a_unit(self):
        for expression,minimum,maximum in (('7/10',None,10),('7 out of 10',None,10),
                ('7 on a 0 to 10 scale',0,10),('7 using a 10-point scale',None,10)):
            case=self.measurement_case('Score is '+expression+'.','7',None,
                {'minimum':minimum,'maximum':maximum,'span':expression})
            result,_=run_case(case)
            answer=result['answers']['field0']
            self.assertEqual(answer['status'],'supported')
            self.assertEqual(answer['text'],'Score: '+expression)
            self.assertEqual(answer['components'][0]['value'],7)
            generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation'])
            bad=deepcopy(case);bad[3]['facts'][-1]['scale']['maximum']=11
            with self.assertRaises(ValidationError):run_case(bad)

    def test_atomic_numeric_documented_unit_holds_until_matching_printed_contract(self):
        case=self.measurement_case(labelled=False)
        d=case[2]['field0'];d.update(value_type='number',answer_mode='atomic')
        result,_=run_case(case)
        answer=result['answers']['field0']
        self.assertNotEqual(answer['status'],'supported')
        self.assertEqual(answer['candidate_text'],'71 kg')
        self.assertIn('numeric_documented_presentation_conflict',[r['code'] for r in answer['route_diagnostics']['holds']])
        case[1][0]['label']='Weight (kg)'
        d['unit']='kg'
        component=d['component_contract']['components'][0]
        component.update(question_quote='Weight (kg)',unit='kg',unit_requirement='printed')
        result,_=run_case(case)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        self.assertEqual(result['answers']['field0']['text'],'71')

    def test_documented_unit_cannot_be_omitted_or_borrowed(self):
        case=self.measurement_case('Weight is 71 while a different weight is 82 kg.')
        with self.assertRaisesRegex(ValidationError,'unit_not_attached'):run_case(case)
        case=self.measurement_case()
        case[3]['facts'][-1].update(unit=None,unit_span=None)
        answer=run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'],'supported')
        self.assertIn('component_unit_unestablished',[r['code'] for r in answer['route_diagnostics']['holds']])

    def test_physical_number_requires_literal_numeric_rendering_without_conversion(self):
        from documents.engine import answer_constraint_error
        for value in ('6','six'):
            case=self.measurement_case('Weight is '+value+' kg.',value,labelled=False)
            field=case[1][0];field['label']='Weight kg'
            field['answer_constraints']={'version':1,'data_type':'number','unit':'kg'}
            definition=case[2]['field0'];definition.update(value_type='number',answer_mode='atomic',unit='kg')
            definition['component_contract']['components'][0].update(question_quote='Weight kg',unit='kg',unit_requirement='printed')
            result,_=run_case(case);answer=result['answers']['field0']
            self.assertEqual(answer['components'][0]['value'],6)
            self.assertEqual(answer['components'][0]['text'],value)
            if value=='6':
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],'6')
                self.assertIsNone(answer_constraint_error(field,answer['text']))
            else:
                self.assertNotEqual(answer['status'],'supported')
                self.assertEqual(answer['candidate_text'],'six')
                self.assertIn('field_value_type',[r['code'] for r in answer['route_diagnostics']['holds']])
                reason=next(r for r in answer['route_diagnostics']['holds'] if r['code']=='field_value_type')
                self.assertEqual(reason['assertion_ids'],['a2'])
                self.assertEqual(reason['fact_ids'],['f2'])
                self.assertEqual([r['quote'] for r in reason['evidence']],['six'])
                self.assertEqual(reason['checker_reason'],'')
                self.assertEqual(reason['validation_errors'],[{'code':'answer_document_constraint',
                    'messages':['Weight kg: enter a number in kg.']}])
                self.assertFalse(result['interpretation']['adjudication']['holds'])
                with self.assertRaises(ValidationError) as raised:
                    generation.validate_value(definition,'six',field)
                self.assertEqual(raised.exception.code,'answer_document_constraint')
            self.assertEqual(generation.validate_stored_answer(case[0],field,definition,answer,result['interpretation']),answer)

    def test_text_destination_preserves_spoken_measurement_and_physical_choice_constraints(self):
        case=self.measurement_case('Weight is six kg.','six')
        case[1][0]['answer_constraints']={'version':1,'data_type':'text'}
        result,_=run_case(case);answer=result['answers']['field0']
        self.assertEqual(answer['status'],'supported')
        self.assertEqual(answer['text'],'Weight: six kg')
        self.assertEqual(answer['components'][0]['value'],6)
        generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation'])
        definition={'value_type':'text'}
        field={'label':'Original choice','answer_constraints':{'version':1,'data_type':'choice','options':['Yes','No']}}
        self.assertEqual(generation.validate_value(definition,'Yes',field),'Yes')
        with self.assertRaises(ValidationError) as raised:
            generation.validate_value(definition,'yes',field)
        self.assertEqual(raised.exception.code,'answer_document_constraint')
        field['answer_constraints']['version']=True
        with self.assertRaises(ValidationError) as raised:
            generation.validate_value(definition,'Yes',field)
        self.assertEqual(raised.exception.code,'answer_document_constraint')

    def test_component_validation_retains_origin_as_local_source_bound_detail(self):
        case=self.measurement_case('Weight is heavy kg.','heavy')
        result,_=run_case(case)
        answer=result['answers']['field0']
        reason=next(r for r in answer['route_diagnostics']['holds'] if r['code']=='component_value_type')
        self.assertEqual(reason['validation_errors'][0]['code'],'answer_numeric_type')
        self.assertEqual(reason['assertion_ids'],['a2'])
        self.assertEqual(reason['fact_ids'],['f2'])
        self.assertEqual([r['quote'] for r in reason['evidence']],['heavy'])
        self.assertEqual(reason['checker_reason'],'')
        self.assertFalse(result['interpretation']['adjudication']['holds'])
        generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation'])

    def test_explicit_past_destination_accepts_only_established_requested_event_scope(self):
        phrase='At the visit on 2 October 2026, the patient reported ankle discomfort.'
        case=list(base_case(phrase))
        fields,defs=definitions(('Previous visit symptoms',));case[1:3]=fields,defs
        defs['field0']['scope']['temporality']='past'
        defs['field0']['component_contract']['components'][0]['scope']['temporality']='past'
        f=fact(case[0],'f2',phrase,timing='past')
        f['timing']['span']=ref(case[0],'2 October 2026')
        case[3]['facts'].append(f)
        case[3]['assertions'].append(assertion(case[0],'a2',['f2'],phrase,encounter='past',temporality='past'))
        case[3]=extraction(case[0],case[3]['facts'],case[3]['assertions'])
        case[4]=assignments(fields,{'field0':['f2']})
        answer=run_case(case)[0]['answers']['field0']
        self.assertEqual(answer['status'],'supported')
        self.assertEqual(answer['text'],phrase)
        for encounter in ('unknown','future'):
            bad=deepcopy(case);bad[3]['assertions'][-1]['encounter']=encounter
            self.assertNotEqual(run_case(bad)[0]['answers']['field0']['status'],'supported')
        for requested in ('current','any'):
            bad=deepcopy(case);bad[2]['field0']['component_contract']['components'][0]['scope']['temporality']=requested
            self.assertNotEqual(run_case(bad)[0]['answers']['field0']['status'],'supported')

    def test_documented_clinical_total_is_separate_from_em_account_qualification(self):
        for closed in (False,True):
            case=stated_time_case(separately_reported=False,closed=closed)
            for absent in (False,True):
                with self.subTest(closed=closed,absent_account=absent):
                    variant=deepcopy(case)
                    if absent:variant[3]['time_accounts']=[]
                    result,calls=run_case(variant)
                    self.assertEqual(result['answers']['field0']['text'],'33')
                    self.assertEqual(result['answers']['field0']['status'],'supported')
                    self.assertEqual(len(calls),3)
                    self.assertEqual(office_time_result(result)['status'],'needs_detail')
                    generation.validate_stored_answer(variant[0],variant[1][0],variant[2]['field0'],result['answers']['field0'],result['interpretation'])
                    if not closed and not absent:
                        holds=result['interpretation']['adjudication']['holds']
                        self.assertTrue(any(h.get('consumer_scope')=='office_em' and h.get('time_account_ids')==['account'] for h in holds))
        complete,_=run_case(stated_time_case())
        self.assertEqual(office_time_result(complete)['status'],'documented')

    def test_source_total_contradiction_retraction_and_dependency_still_hold(self):
        case=stated_time_case(separately_reported=False,closed=False)
        for verdict in ('unknown','contradiction','incorrect'):
            def mutate(check,*_):
                next(r for r in check['assertions'] if r['id']=='total').update(verdict=verdict,reason='The total assertion is not established.')
            result,calls=run_case(case,mutate)
            self.assertNotEqual(result['answers']['field0']['status'],'supported')
            self.assertEqual(len(calls),3)
        for kind in ('retracts','validity_dependency'):
            variant=deepcopy(case)
            variant[3]['relationships'].append({'id':'governing','kind':kind,'source_assertion_id':'staff',
                'target_assertion_ids':['total'],'evidence_refs':next(a for a in variant[3]['assertions'] if a['id']=='staff')['predicate_refs']})
            def govern(check,*_):
                if kind=='validity_dependency':
                    next(r for r in check['assertions'] if r['id']=='staff').update(verdict='unknown',reason='Governing source is unresolved.')
            result,_=run_case(variant,govern)
            self.assertNotEqual(result['answers']['field0']['status'],'supported')

    def test_account_checker_disagreement_remains_em_only_and_never_retries(self):
        case=stated_time_case()
        for verdict in ('unknown','contradiction','incorrect'):
            def mutate(check,*_):
                check['time_accounts'][0].update(verdict=verdict,reason='Billing account qualification needs review.')
            result,calls=run_case(case,mutate)
            self.assertEqual(result['answers']['field0']['text'],'33')
            self.assertEqual(office_time_result(result)['status'],'needs_detail')
            self.assertEqual(len(calls),3)

    def test_confirmed_open_account_does_not_block_a_clinical_assignment_repair(self):
        for account_verdict,expected_calls in (('confirmed',5),('unknown',3)):
            notes,fields,defs,raw,good=stated_time_case(separately_reported=False,closed=False)
            empty=assignments(fields,{'field0':[]});calls=[]
            def send(role,attempt,payload,*_):
                calls.append((role,attempt))
                if role=='extractor':return deepcopy(raw)
                chosen=empty if attempt==1 else good
                if role=='assigner':return deepcopy(chosen)
                value=checker(payload['graph'],fields,defs,chosen)
                value['time_accounts'][0].update(verdict=account_verdict,
                    reason='' if account_verdict=='confirmed' else 'Account interpretation is unknown.')
                if attempt==1:
                    value['components'][0].update(verdict='omission',cause='assignment',fact_ids=['ftime'],reason='Documented total omitted.')
                    value['fields'][0].update(verdict='omission',cause='assignment',reason='Documented total omitted.')
                return value
            result=generation.run(notes,fields,defs,send,identity=IDENTITY)
            self.assertEqual(len(calls),expected_calls)
            self.assertEqual(office_time_result(result)['status'],'needs_detail')
            if account_verdict=='confirmed':self.assertEqual(result['answers']['field0']['text'],'33')
            else:self.assertNotEqual(result['answers']['field0']['status'],'supported')

    def labelled_case(self):
        case=list(base_case('Age: 38\nCountry: U.K.'))
        notes,fields,defs,raw,_=case
        d=defs['field0'];d['meaning']='Encounter details: Age; Country.'
        components=[]
        for identifier,label,kind,value,number in (('age','Age','integer','38',2),('country','Country','text','U.K.',3)):
            component={**deepcopy(d['component_contract']['components'][0]),'id':identifier,
                'label':label,'meaning':'Documented '+label,'value_type':kind}
            components.append(component)
            raw['facts'].append(fact(notes,'f'+str(number),value,kind='identity'))
            raw['assertions'].append(assertion(notes,'a'+str(number),['f'+str(number)],value,kind='identity',consumer_role='none'))
        d['component_contract'].update(rendering='labelled',components=components)
        case[3]=extraction(notes,raw['facts'],raw['assertions'])
        case[4]={'fields':[{'key':'field0','separator':'; ','components':[
            {'id':'age','disposition':'supported','fact_ids':['f2'],'predicate_assertion_ids':['a2'],'relationship_ids':[]},
            {'id':'country','disposition':'supported','fact_ids':['f3'],'predicate_assertion_ids':['a3'],'relationship_ids':[]}]}]}
        return case

    def test_labels_are_exact_approved_order_and_values_keep_source_bytes(self):
        case=self.labelled_case()
        result,_=run_case(case)
        self.assertEqual(result['answers']['field0']['text'],'Age: 38; Country: U.K.')
        swapped=deepcopy(case)
        swapped[3]['facts'].reverse();swapped[3]['assertions'].reverse()
        self.assertEqual(run_case(swapped)[0]['answers']['field0']['text'],'Age: 38; Country: U.K.')
        case[2]['field0']['component_contract']['components'][0]['label']='New arbitrary label'
        with self.assertRaises(ValidationError):run_case(case)

    def test_missing_sibling_preserves_documented_candidate_but_never_complete(self):
        case=self.labelled_case()
        case[4]['fields'][0]['components'][1].update(disposition='missing',fact_ids=[],predicate_assertion_ids=[])
        result,_=run_case(case)
        answer=result['answers']['field0']
        self.assertEqual(answer['text'],'')
        self.assertEqual(answer['candidate_text'],'Age: 38')
        self.assertIn('partial_component_coverage',[h['code'] for h in answer['route_diagnostics']['holds']])
        self.assertEqual(answer['components'][1]['disposition'],'missing')
        def fake_full(check,*_):check['fields'][0].update(verdict='supported',cause='none',reason='')
        with self.assertRaisesRegex(ValidationError,'partial_field_supported'):run_case(case,fake_full)

    def test_numeric_unit_mismatch_cannot_relabel_source(self):
        case=list(base_case('Weight: 42 pounds.'))
        fields,defs=definitions(('Weight (kg)',));case[1:3]=fields,defs
        d=defs['field0'];d.update(value_type='number',answer_mode='atomic',unit='kg')
        component=d['component_contract']['components'][0]
        component.update(value_type='number',unit='kg',unit_requirement='printed')
        f=fact(case[0],'f2','42',kind='measurement');f.update(unit='pounds',unit_span=ref(case[0],'pounds'))
        case[3]['facts'].append(f);case[3]['assertions'].append(assertion(case[0],'a2',['f2'],'42 pounds',kind='clinical'))
        case[3]=extraction(case[0],case[3]['facts'],case[3]['assertions'])
        case[4]=assignments(fields,{'field0':['f2']})
        result,_=run_case(case)
        self.assertIn('component_unit_mismatch',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])
        self.assertEqual(result['answers']['field0']['candidate_text'],'42')

    def test_numeric_fragment_and_scale_remain_hard_guards(self):
        for phrase,value in (('Measurement: -3 units.','3'),('Measurement: 1.5 units.','5'),
                             ('Measurement: twenty-one units.','one'),('Measurement: 1/2 units.','1')):
            with self.subTest(phrase=phrase):
                case=list(base_case(phrase))
                f=fact(case[0],'f2',value,kind='measurement')
                case[3]['facts'].append(f)
                case[3]['assertions'].append(assertion(case[0],'a2',['f2'],phrase))
                raw=extraction(case[0],case[3]['facts'],case[3]['assertions'])
                if '/' in phrase:
                    # Decimal 1 is a literal fragment; a numeric destination cannot
                    # discard a source ratio, even though its local number is real.
                    fields,defs=definitions(('Score',));defs['field0'].update(value_type='number',answer_mode='atomic')
                    defs['field0']['component_contract']['components'][0]['value_type']='number'
                    case=[case[0],fields,defs,raw,assignments(fields,{'field0':['f2']})]
                    result,_=run_case(case)
                    self.assertNotEqual(result['answers']['field0']['status'],'supported')
                else:
                    with self.assertRaises(ValidationError):graph.compile_graph(case[0],raw)

    def test_calendar_and_choice_do_not_silently_normalize(self):
        d={'value_type':'date'}
        with self.assertRaises(ValidationError):generation.validate_value(d,'31 February 2027')
        self.assertEqual(generation.validate_value(d,'14 June 2027'),'14 June 2027')
        with self.assertRaises(ValidationError):generation.validate_value({'value_type':'choice','choices':['Yes','No']},'yes')
        self.assertEqual(generation.validate_value({'value_type':'text','answer_mode':'atomic'},'She has nausea.'),'She has nausea.')

    def test_permitted_assignment_repair_is_exactly_five_calls(self):
        notes,fields,defs,raw,good=base_case()
        initial=assignments(fields,{'field0':[]})
        calls=[]
        def send(role,attempt,payload,*_):
            calls.append((role,attempt))
            if role=='extractor':return deepcopy(raw)
            assigned=initial if attempt==1 else good
            if role=='assigner':return deepcopy(assigned)
            checked=checker(payload['graph'],fields,defs,assigned)
            if attempt==1:
                checked['components'][0].update(verdict='omission',cause='assignment',fact_ids=['f1'],reason='Existing symptom fact omitted.')
                checked['fields'][0].update(verdict='omission',cause='assignment',reason='Existing symptom fact omitted.')
            return checked
        result=generation.run(notes,fields,defs,send,identity=IDENTITY)
        self.assertEqual(len(calls),5)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        self.assertEqual([r[:2] for r in generation.raw_outputs(result['interpretation'])],calls)
        generation.restore(notes,result['interpretation'])

    def test_missing_extractor_content_and_semantic_conflict_never_retry_assignment(self):
        for verdict,cause in (('omission','extraction'),('unknown','interpretation'),('conflict','interpretation')):
            with self.subTest(verdict=verdict):
                def check(value,*_):
                    value['components'][0].update(verdict=verdict,cause=cause,fact_ids=[],reason='Source premise needs review.')
                    value['fields'][0].update(verdict=verdict,cause=cause,reason='Source premise needs review.')
                result,calls=run_case(base_case(),check)
                self.assertEqual(len(calls),3)
                self.assertNotEqual(result['answers']['field0']['status'],'supported')

    def test_checker_cannot_clear_unknown_component_or_omit_it(self):
        case=self.labelled_case()
        def fake(check,*_):check['components'].pop()
        with self.assertRaises(ValidationError):run_case(case,fake)
        case[4]['fields'][0]['components'][0]['disposition']='unknown'
        def false(check,*_):check['components'][0].update(verdict='supported',cause='none')
        with self.assertRaises(ValidationError):run_case(case,false)

    def test_current_order_can_retain_checked_future_collection_attachment(self):
        case=list(base_case('I ordered a test; collection is tomorrow.'))
        notes=case[0]
        case[3]['facts'] += [fact(notes,'f2','I ordered a test',kind='plan'),
                             fact(notes,'f3','collection is tomorrow',timing='future',kind='plan')]
        case[3]['facts'][-1]['timing']['span']=ref(notes,'tomorrow')
        case[3]['assertions'] += [assertion(notes,'a2',['f2'],'I ordered a test',consumer_role='order_placed'),
            assertion(notes,'a3',['f3'],'collection is tomorrow',temporality='future',consumer_role='collection')]
        edge={'id':'r1','kind':'qualifies','source_assertion_id':'a3','target_assertion_ids':['a2'],
              'evidence_refs':[ref(notes,'I ordered a test; collection is tomorrow.')]}
        case[3]=extraction(notes,case[3]['facts'],case[3]['assertions'],[edge])
        case[4]=assignments(case[1],{'field0':['f2','f3']},{'field0':['a2']})
        case[4]['fields'][0]['components'][0]['relationship_ids']=['r1']
        result,_=run_case(case)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        self.assertEqual(result['answers']['field0']['text'],'I ordered a test; collection is tomorrow')
        case[4]['fields'][0]['components'][0]['relationship_ids']=[]
        self.assertNotEqual(run_case(case)[0]['answers']['field0']['status'],'supported')

    def test_reload_rederives_after_outer_hash_is_resigned(self):
        case=self.labelled_case();result,_=run_case(case)
        for mutate in (lambda i:i['graph']['facts']['f2']['value_evidence'].update(quote='99'),
                       lambda i:i['adjudication']['checked']['fields']['field0'].update(verdict='missing'),
                       lambda i:i['attempts'][0]['assignment']['fields'][0]['components'][0].update(fact_ids=['f3']),
                       lambda i:i['identity'].update(patient_display_name='Wrong Patient')):
            with self.subTest(mutation=mutate):
                changed=deepcopy(result['interpretation']);mutate(changed)
                changed['sha256']=graph.digest({k:v for k,v in changed.items() if k!='sha256'})
                with self.assertRaises(ValidationError):generation.restore(case[0],changed)
        changed=deepcopy(result['answers']['field0']);changed['text']='Age: 99; Country: U.K.'
        changed['semantic_proof_sha256']=graph.digest({k:v for k,v in changed.items() if k!='semantic_proof_sha256'})
        with self.assertRaises(ValidationError):generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],changed,result['interpretation'])

    def test_attributed_review_does_not_change_source_proof(self):
        case=base_case();result,_=run_case(case)
        answer=deepcopy(result['answers']['field0'])
        answer.update(reviewed=True,reviewed_by=str(uuid4()),review_revision=2)
        self.assertEqual(generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation']),answer)
        answer['review_revision']=True
        with self.assertRaises(ValidationError):generation.validate_stored_answer(case[0],case[1][0],case[2]['field0'],answer,result['interpretation'])

    def test_complete_attributed_family_history_can_qualify_patient_order(self):
        case=list(base_case('A test was ordered because her mother has thyroid disease.'))
        notes=case[0]
        order=fact(notes,'f2','A test was ordered',kind='plan')
        family=fact(notes,'f3','her mother has thyroid disease',subject='other',kind='history')
        family['subject']['name_span']=ref(notes,'her mother')
        case[3]['facts'] += [order,family]
        case[3]['assertions'] += [assertion(notes,'a2',['f2'],'A test was ordered',consumer_role='order_placed'),
            assertion(notes,'a3',['f3'],'her mother has thyroid disease',subject='other',consumer_role='family_history')]
        edge={'id':'r1','kind':'qualifies','source_assertion_id':'a3','target_assertion_ids':['a2'],
              'evidence_refs':[ref(notes,'because her mother has thyroid disease')]}
        case[3]=extraction(notes,case[3]['facts'],case[3]['assertions'],[edge])
        case[4]=assignments(case[1],{'field0':['f2','f3']},{'field0':['a2']})
        case[4]['fields'][0]['components'][0]['relationship_ids']=['r1']
        result,_=run_case(case)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        self.assertIn('her mother',result['answers']['field0']['text'])
        case[3]['facts'][-1]['value_span']=ref(notes,'thyroid disease')
        result,_=run_case(case)
        self.assertIn('attachment_attribution_omitted',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])

    def test_staff_exclusion_retains_actor_and_date_without_patient_relabel(self):
        case=list(base_case('The physician total is 28 minutes.\nExcluded: 6 minutes of staff intake on 13 June 2027.'))
        notes=case[0]
        total=fact(notes,'f2','The physician total is 28 minutes.',subject='clinician')
        excluded=fact(notes,'f3','Excluded: 6 minutes of staff intake on 13 June 2027.',subject='other',timing='past')
        excluded['subject']['name_span']=ref(notes,'staff')
        excluded['timing']['span']=ref(notes,'13 June 2027')
        case[3]['facts'] += [total,excluded]
        case[3]['assertions'] += [assertion(notes,'a2',['f2'],'The physician total is 28 minutes.',subject='clinician'),
            assertion(notes,'a3',['f3'],'Excluded: 6 minutes of staff intake on 13 June 2027.',subject='other',temporality='past',
                kind='time_exclusion',consumer_role='time_exclusion',time={'performer':'staff','performer_ref':ref(notes,'staff'),
                    'date_ref':ref(notes,'13 June 2027'),'quantity_ref':ref(notes,'6'),'unit_ref':ref(notes,'minutes',1),
                    'exclusion':'prior_date'})]
        # The repeated unit ref is explicitly bound to the exclusion's unit.
        exclusion_unit=ref(notes,'Excluded: 6 minutes of staff intake on 13 June 2027.')['source_unit_id']
        case[3]['assertions'][-1]['time']['unit_ref']['source_unit_id']=exclusion_unit
        case[2]['field0']['scope']['subject']='clinician'
        case[2]['field0']['component_contract']['components'][0]['scope']['subject']='clinician'
        edge={'id':'r1','kind':'account_excludes','source_assertion_id':'a2','target_assertion_ids':['a3'],
              'evidence_refs':[ref(notes,'Excluded: 6 minutes of staff intake on 13 June 2027.')]}
        case[3]=extraction(notes,case[3]['facts'],case[3]['assertions'],[edge])
        case[4]=assignments(case[1],{'field0':['f2','f3']},{'field0':['a2']})
        case[4]['fields'][0]['components'][0]['relationship_ids']=['r1']
        result,_=run_case(case)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        case[3]['facts'][-1]['value_span']=ref(notes,'6 minutes')
        result,_=run_case(case)
        self.assertIn('time_exclusion_literal_omitted',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])

    def test_governing_evidence_visible_and_facts_stored_only_once(self):
        case=list(base_case('This source attribution remains unknown.'))
        case[3]['unit_coverage'][-1]['disposition']='unknown'
        result,_=run_case(case)
        answer=result['answers']['field0']
        self.assertEqual([f['id'] for f in answer['facts']],['f1'])
        self.assertEqual(len(result['interpretation']['graph']['facts']),2)
        self.assertIn('This source attribution remains unknown.',[e['quote'] for e in answer['evidence']])
        self.assertTrue(all('_' not in reason for reason in answer['review_reasons']))
        self.assertTrue(answer['route_diagnostics']['first_reason']['rule'].startswith(graph.CONTRACT))

    def test_service_date_and_documented_patient_name_are_hard_identity_bindings(self):
        case=list(base_case('Service date: 15 June 2027'))
        notes=case[0]
        case[3]['facts'].append(fact(notes,'f2','15 June 2027',kind='identity'))
        case[3]['assertions'].append(assertion(notes,'a2',['f2'],'15 June 2027',kind='identity',consumer_role='service_date'))
        case[3]=extraction(notes,case[3]['facts'],case[3]['assertions'])
        result,_=run_case(case)
        self.assertIn('source_service_date_mismatch',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])
        case=list(base_case());case[2]['field0']['patient_name_requirement']='documented'
        result,_=run_case(case)
        self.assertIn('patient_name_omitted',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])
        case[4]=assignments(case[1],{'field0':['f0','f1']})
        self.assertEqual(run_case(case)[0]['answers']['field0']['status'],'supported')


class EncounterTimeParticipantScopeTests(unittest.TestCase):
    @staticmethod
    def encounter_case(case):
        from documents.component_contracts import CHOICE_CONTRACT
        case = deepcopy(case)
        definition = case[2]['field0']
        definition['scope']['subject'] = 'encounter'
        contract = definition['component_contract']
        contract['contract'] = CHOICE_CONTRACT
        for component in contract['components']:
            component['scope']['subject'] = 'encounter'
            component.update(encounter_scope='all_documented', choices=[], option_quote=None)
        return case

    @classmethod
    def staff_case(cls):
        phrase = 'Staff spent 6 minutes on intake, excluded from the physician total.'
        case = list(base_case(phrase))
        fields, defs = definitions(('Staff time excluded from the encounter',))
        case[1:3] = fields, defs
        notes = case[0]
        value = fact(notes, 'f2', phrase, subject='other')
        value['subject']['name_span'] = ref(notes, 'Staff')
        time = {'performer':'staff', 'performer_ref':ref(notes, 'Staff'),
                'date_ref':None, 'quantity_ref':ref(notes, '6'),
                'unit_ref':ref(notes, 'minutes'), 'exclusion':'staff'}
        claim = assertion(notes, 'a2', ['f2'], phrase, subject='other',
            kind='time_exclusion', consumer_role='time_exclusion', time=time)
        case[3]['facts'].append(value)
        case[3]['assertions'].append(claim)
        case[3] = extraction(notes, case[3]['facts'], case[3]['assertions'])
        case[4] = assignments(fields, {'field0':['f2']}, {'field0':['a2']})
        return cls.encounter_case(case)

    def test_encounter_component_retains_typed_clinician_time_without_relabelling(self):
        case = self.encounter_case(stated_time_case())
        result, calls = run_case(case)
        self.assertEqual(result['answers']['field0']['status'], 'supported')
        self.assertEqual(len(calls), 3)
        self.assertEqual(result['interpretation']['graph']['assertions']['total']['subject'], 'clinician')
        self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])

    def test_encounter_component_retains_typed_staff_exclusion_without_patient_relabelling(self):
        case = self.staff_case()
        result, _ = run_case(case)
        answer = result['answers']['field0']
        self.assertEqual(answer['status'], 'supported')
        self.assertIn('Staff spent 6 minutes', answer['text'])
        self.assertIn('excluded from the physician total', answer['text'])
        self.assertEqual(result['interpretation']['graph']['assertions']['a2']['subject'], 'other')

    def test_admission_requires_matching_typed_role_performer_and_bound_source(self):
        case = self.staff_case()
        compiled = graph.compile_graph(case[0], case[3])
        claim = compiled['assertions']['a2']
        definition = case[2]['field0']
        component = definition['component_contract']['components'][0]
        self.assertTrue(generation._component_scope_matches(claim, definition, component))
        for update in ({'kind':'clinical'}, {'consumer_role':'family_history'},
                       {'consumer_role':'none'}, {'subject':'uncertain'}, {'time':None}):
            bad = deepcopy(claim); bad.update(update)
            with self.subTest(update=update):
                self.assertFalse(generation._component_scope_matches(bad, definition, component))
        for performer in ('patient', 'other', 'unknown', 'clinician'):
            bad = deepcopy(claim); bad['time']['performer'] = performer
            with self.subTest(performer=performer):
                self.assertFalse(generation._component_scope_matches(bad, definition, component))
        for evidence in (None, {}, {'quote':'Staff', 'source_unit_id':9999},
                         {'quote':'', 'source_unit_id':claim['source_unit_ids'][0]}):
            bad = deepcopy(claim); bad['time']['performer_ref'] = evidence
            with self.subTest(evidence=evidence):
                self.assertFalse(generation._component_scope_matches(bad, definition, component))

    def test_all_four_explicit_clinician_time_roles_use_the_same_admission(self):
        case = self.encounter_case(stated_time_case())
        claim = graph.compile_graph(case[0], case[3])['assertions']['total']
        definition = case[2]['field0']; component = definition['component_contract']['components'][0]
        for role in ('time_total', 'time_work', 'time_exclusion', 'time_qualification'):
            value = deepcopy(claim); value.update(kind=role, consumer_role=role)
            with self.subTest(role=role):
                self.assertTrue(generation._component_scope_matches(value, definition, component))
        value = deepcopy(claim); value['time']['performer'] = 'staff'
        self.assertFalse(generation._component_scope_matches(value, definition, component))

    def test_legacy_scope_and_other_destination_owners_do_not_gain_permission(self):
        from documents.component_contracts import CONTRACT
        case = self.encounter_case(stated_time_case())
        claim = graph.compile_graph(case[0], case[3])['assertions']['total']
        definition = case[2]['field0']; component = definition['component_contract']['components'][0]
        old = deepcopy(definition); old['component_contract']['contract'] = CONTRACT
        self.assertFalse(generation._component_scope_matches(claim, old, component))
        self.assertFalse(generation._scope_matches(claim, component['scope']))
        for subject in ('patient', 'other'):
            c = deepcopy(component); c['scope']['subject'] = subject
            self.assertFalse(generation._component_scope_matches(claim, definition, c))

    def test_time_polarity_and_encounter_restrictions_still_apply(self):
        case = self.encounter_case(stated_time_case())
        claim = graph.compile_graph(case[0], case[3])['assertions']['total']
        definition = case[2]['field0']; component = deepcopy(definition['component_contract']['components'][0])
        component['encounter_scope'] = 'current'
        for update in ({'encounter':'unknown'}, {'encounter':'future'}, {'encounter':'past'},
                       {'temporality':'past'}, {'temporality':'future'}):
            bad = deepcopy(claim); bad.update(update)
            self.assertFalse(generation._component_scope_matches(bad, definition, component))
        component['scope']['polarity'] = 'positive'
        for polarity in ('negated', 'uncertain', 'mixed'):
            bad = deepcopy(claim); bad['polarity'] = polarity
            self.assertFalse(generation._component_scope_matches(bad, definition, component))

    def test_compiler_and_independent_source_checker_remain_gates(self):
        case = self.staff_case()
        bad = deepcopy(case)
        bad[3]['assertions'][-1]['time']['performer_ref'] = None
        with self.assertRaisesRegex(ValidationError, 'time_performer_evidence'):
            graph.compile_graph(bad[0], bad[3])
        def unresolved(check, *_):
            next(x for x in check['assertions'] if x['id']=='a2').update(
                verdict='unknown', reason='The source owner is unresolved.')
        held, _ = run_case(case, unresolved)
        self.assertNotEqual(held['answers']['field0']['status'], 'supported')


class DocumentedUnitParticipantTests(unittest.TestCase):
    @staticmethod
    def time_case(*, full_text=False, context=False):
        case = EncounterTimeParticipantScopeTests.encounter_case(stated_time_case())
        definition = case[2]['field0']
        definition.update(value_type='text', answer_mode='narrative')
        component = definition['component_contract']['components'][0]
        component.update(value_type='text', unit_requirement='documented')
        total = next(a for a in case[3]['assertions'] if a['id']=='total')
        quantity = next(f for f in case[3]['facts'] if f['id']=='ftime')
        if full_text:
            quantity.update(kind='finding', value_span=ref(case[0], 'Nora spent 33 minutes on this service date.'))
        if context:
            date = fact(case[0], 'fdate', '14 June 2027', subject='clinician', kind='identity')
            case[3]['facts'].append(date)
            total['fact_ids'].append('fdate')
            case[4]['fields'][0]['components'][0]['fact_ids'].append('fdate')
        return case

    def test_owned_scalar_time_keeps_exact_unit_without_mutating_fact(self):
        for quantity in ('33', 'thirty-three'):
            case = self.time_case()
            if quantity != '33':
                # Reconstruct every source reference rather than moving offsets.
                notes, fields, defs, raw, assigned = case
                notes = notes.replace('33', quantity)
                raw['facts'] = [fact(notes, f['id'], quantity if f['id']=='ftime' else f['value_span']['quote'],
                    subject=f['subject']['kind'], kind=f['kind']) for f in raw['facts']]
                raw['assertions'] = [deepcopy(a) for a in raw['assertions']]
                for a in raw['assertions']:
                    a['predicate_refs'] = [ref(notes, r['quote'].replace('33', quantity)) for r in a['predicate_refs']]
                    if a['time'] is not None and a['time']['quantity_ref'] is not None:
                        r = a['time']['quantity_ref']; a['time']['quantity_ref'] = {**r, 'quote':r['quote'].replace('33', quantity)}
                case = [notes, fields, defs, extraction(notes, raw['facts'], raw['assertions'], raw['relationships'], raw['time_accounts']), assigned]
                case[3]['time_accounts'][0]['total_ref']['quote'] = quantity
            before = deepcopy(case)
            result, _ = run_case(case)
            answer = result['answers']['field0']
            self.assertEqual(answer['status'], 'supported')
            self.assertEqual(answer['text'], quantity+' minutes')
            self.assertIsNone(answer['facts'][0]['unit'])
            self.assertEqual(case, before)
            self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])

    def test_context_date_does_not_invent_a_measurement_unit(self):
        case = self.time_case(context=True)
        result, _ = run_case(case)
        answer = result['answers']['field0']
        self.assertEqual(answer['status'], 'supported')
        self.assertEqual(answer['text'], '33 minutes; 14 June 2027')
        self.assertEqual(answer['facts'][-1]['value_evidence']['quote'], '14 June 2027')
        self.assertIsNone(answer['facts'][-1]['unit'])

    def test_full_literal_time_and_staff_exclusion_already_retain_owned_units(self):
        cases = [self.time_case(full_text=True), EncounterTimeParticipantScopeTests.staff_case()]
        cases[1][2]['field0']['component_contract']['components'][0]['unit_requirement'] = 'documented'
        for case in cases:
            result, _ = run_case(case)
            answer = result['answers']['field0']
            self.assertEqual(answer['status'], 'supported')
            self.assertEqual(answer['text'], case[3]['facts'][-1]['value_span']['quote'])
            self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])

    def test_numeric_missing_unattached_and_foreign_units_stay_held(self):
        # The graph compiler allows source refs within an assertion's units;
        # the rendering fallback must additionally bind this exact quantity.
        reference = stated_time_case()
        work = next(a for a in reference[3]['assertions'] if a['id']=='w1')
        for update in ({'quantity_ref':None, 'unit_ref':None},
                       {'quantity_ref':work['time']['quantity_ref']},
                       {'unit_ref':work['time']['unit_ref']}):
            case = self.time_case()
            total = next(a for a in case[3]['assertions'] if a['id']=='total')
            total['time'].update(update)
            for name in ('quantity_ref', 'unit_ref'):
                if total['time'][name] is not None:
                    unit = total['time'][name]['source_unit_id']
                    if unit not in total['source_unit_ids']: total['source_unit_ids'].append(unit)
            case[3] = extraction(case[0], case[3]['facts'], case[3]['assertions'], [], [])
            answer = run_case(case)[0]['answers']['field0']
            self.assertNotEqual(answer['status'], 'supported')
            self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_same_statement_unattached_unit_stays_held(self):
        old = 'Staff spent 6 minutes on intake, excluded from the physician total.'
        phrase = 'Staff spent 6 while another activity took 9 minutes, excluded from the physician total.'
        case = EncounterTimeParticipantScopeTests.staff_case()
        notes = case[0].replace(old, phrase)
        value = fact(notes, 'f2', phrase, subject='other')
        value['subject']['name_span'] = ref(notes, 'Staff')
        claim = assertion(notes, 'a2', ['f2'], phrase, subject='other',
            kind='time_exclusion', consumer_role='time_exclusion', time={
                'performer':'staff', 'performer_ref':ref(notes, 'Staff'), 'date_ref':None,
                'quantity_ref':ref(notes, '6'), 'unit_ref':ref(notes, 'minutes'), 'exclusion':'staff'})
        case[0] = notes
        case[3] = extraction(notes, case[3]['facts'][:-1]+[value], case[3]['assertions'][:-1]+[claim])
        case[2]['field0']['component_contract']['components'][0]['unit_requirement'] = 'documented'
        answer = run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_full_time_text_cannot_borrow_another_measurements_unit(self):
        case = self.time_case(full_text=True)
        total = next(a for a in case[3]['assertions'] if a['id']=='total')
        other = next(a for a in case[3]['assertions'] if a['id']=='w1')
        total['time']['unit_ref'] = deepcopy(other['time']['unit_ref'])
        total['source_unit_ids'].extend(i for i in other['source_unit_ids'] if i not in total['source_unit_ids'])
        case[3] = extraction(case[0], case[3]['facts'], case[3]['assertions'], [], [])
        answer = run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_printed_unit_policy_does_not_use_time_fallback(self):
        case = self.time_case()
        case[1][0]['label'] = 'Stated minutes'
        component = case[2]['field0']['component_contract']['components'][0]
        component.update(question_quote='Stated minutes', unit='minutes', unit_requirement='printed')
        answer = run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_legacy_component_unit_behavior_is_unchanged(self):
        from documents.component_contracts import fixture
        case = self.time_case(context=True)
        definition = case[2]['field0']
        definition['scope']['subject'] = 'clinician'
        definition['component_contract'] = fixture(case[1][0], definition)
        definition['component_contract']['components'][0]['unit_requirement'] = 'documented'
        answer = run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertEqual([h['code'] for h in answer['route_diagnostics']['holds']],
                         ['component_unit_unestablished', 'component_unit_unestablished'])

    def test_bare_number_cannot_escape_required_unit_by_changing_fact_kind(self):
        for kind in ('measurement', 'finding', 'identity'):
            case = self.time_case()
            next(f for f in case[3]['facts'] if f['id']=='ftime')['kind'] = kind
            total = next(a for a in case[3]['assertions'] if a['id']=='total')
            total['time'].update(quantity_ref=None, unit_ref=None)
            case[3] = extraction(case[0], case[3]['facts'], case[3]['assertions'])
            answer = run_case(case)[0]['answers']['field0']
            self.assertNotEqual(answer['status'], 'supported')
            self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    @staticmethod
    def staff_phrase_case(phrase, *, quantity=None, unit=None, performer='Staff', date=None, kind='finding'):
        original = 'Staff spent 6 minutes on intake, excluded from the physician total.'
        case = EncounterTimeParticipantScopeTests.staff_case()
        notes = case[0].replace(original, phrase)
        value = fact(notes, 'f2', phrase, subject='other', kind=kind)
        value['subject']['name_span'] = ref(notes, performer)
        claim = assertion(notes, 'a2', ['f2'], phrase, subject='other',
            kind='time_exclusion', consumer_role='time_exclusion', time={
                'performer':'staff', 'performer_ref':ref(notes, performer),
                'date_ref':ref(notes, date) if date else None,
                'quantity_ref':ref(notes, quantity) if quantity else None,
                'unit_ref':ref(notes, unit) if unit else None, 'exclusion':'staff'})
        case[0] = notes
        case[3] = extraction(notes, case[3]['facts'][:-1]+[value], case[3]['assertions'][:-1]+[claim])
        case[2]['field0']['component_contract']['components'][0]['unit_requirement'] = 'documented'
        return case

    def test_full_time_quantity_with_omitted_pair_cannot_become_context(self):
        for phrase in ('Staff spent 6 on intake, excluded from the physician total.',
                       'Staff spent six on intake, excluded from the physician total.',
                       'Staff spent 6minutes on intake, excluded from the physician total.',
                       'Staff spent 6 while another activity took 9 minutes, excluded from the physician total.'):
            for kind in ('finding', 'history', 'identity', 'measurement'):
                case = self.staff_phrase_case(phrase, kind=kind)
                result, _ = run_case(case)
                answer = result['answers']['field0']
                self.assertNotEqual(answer['status'], 'supported')
                self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])
                self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])

    def test_whole_time_phrase_never_borrows_a_second_quantitys_pair(self):
        phrase = 'Staff spent 6 while another activity took 9 minutes, excluded from the physician total.'
        case = self.staff_phrase_case(phrase, quantity='9', unit='minutes')
        answer = run_case(case)[0]['answers']['field0']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_source_bound_performer_and_calendar_numbers_are_context(self):
        phrase = 'Team One spent 6 minutes on intake on 14 June 2027, excluded from the physician total.'
        case = self.staff_phrase_case(phrase, quantity='6', unit='minutes', performer='Team One', date='14 June 2027')
        name = fact(case[0], 'fperformer', 'Team One', subject='other', kind='identity')
        name['subject']['name_span'] = ref(case[0], 'Team One')
        identity = assertion(case[0], 'performer_identity', ['fperformer'], 'Team One', subject='other',
            kind='identity', identity_role='other_name', consumer_role='none')
        case[3] = extraction(case[0], case[3]['facts']+[name], case[3]['assertions']+[identity])
        result, _ = run_case(case)
        answer = result['answers']['field0']
        self.assertEqual(answer['status'], 'supported')
        self.assertEqual(answer['text'], phrase)
        self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])
        def unresolved(check, *_):
            next(row for row in check['assertions'] if row['id']=='performer_identity').update(
                verdict='unknown', reason='The performer identity is not established.')
        held = run_case(case, unresolved)[0]['answers']['field0']
        self.assertNotEqual(held['status'], 'supported')
        self.assertIn('component_unit_unestablished', [h['code'] for h in held['route_diagnostics']['holds']])
        bad = self.staff_phrase_case('Staff spent 6 on intake, excluded from the physician total.', date='6')
        held = run_case(bad)[0]['answers']['field0']
        self.assertIn('component_unit_unestablished', [h['code'] for h in held['route_diagnostics']['holds']])

    def test_broad_performer_or_date_reference_cannot_mask_a_time_quantity(self):
        phrase = 'Staff spent six on intake, excluded from the physician total.'
        for key in ('performer_ref', 'date_ref'):
            case = self.staff_phrase_case(phrase)
            case[3]['assertions'][-1]['time'][key] = ref(case[0], phrase)
            answer = run_case(case)[0]['answers']['field0']
            self.assertNotEqual(answer['status'], 'supported')
            self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])

    def test_non_time_context_count_is_not_retagged_as_a_time_measurement(self):
        phrase = 'Reviewed 3 records.'
        case = list(base_case(phrase))
        case[3]['facts'].append(fact(case[0], 'f2', phrase))
        case[3]['assertions'].append(assertion(case[0], 'a2', ['f2'], phrase, kind='context', consumer_role='none'))
        case[3] = extraction(case[0], case[3]['facts'], case[3]['assertions'])
        case[4] = assignments(case[1], {'field0':['f2']}, {'field0':['a2']})
        case = EncounterTimeParticipantScopeTests.encounter_case(case)
        case[2]['field0']['component_contract']['components'][0]['unit_requirement'] = 'documented'
        answer = run_case(case)[0]['answers']['field0']
        self.assertEqual(answer['status'], 'supported')
        self.assertEqual(answer['text'], phrase)

    def test_unsupported_time_fractions_magnitudes_and_numeric_glyphs_stay_held(self):
        for expression in ('half', 'a quarter', '½', 'a hundred', 'one thousand',
                           'a million', 'point five', 'decimal six', '⅓', 'Ⅳ', '²', '四'):
            phrase = 'Staff spent '+expression+' on intake, excluded from the physician total.'
            case = self.staff_phrase_case(phrase)
            before = deepcopy(case)
            result, _ = run_case(case)
            answer = result['answers']['field0']
            self.assertNotEqual(answer['status'], 'supported')
            self.assertIn('component_unit_unestablished', [h['code'] for h in answer['route_diagnostics']['holds']])
            self.assertEqual(case, before)
            self.assertEqual(generation.restore(case[0], result['interpretation']), result['answers'])

    def test_known_quantity_unit_and_nonquantity_time_context_remain_supported(self):
        for quantity in ('6.5', 'six'):
            phrase = 'Staff spent '+quantity+' minutes on intake, excluded from the physician total.'
            case = self.staff_phrase_case(phrase, quantity=quantity, unit='minutes')
            answer = run_case(case)[0]['answers']['field0']
            self.assertEqual(answer['status'], 'supported')
            self.assertEqual(answer['text'], phrase)
        # 'point' is not itself a quantitative amount; the existing numeric
        # components in 'point five' are held without inventing a conversion.
        phrase = 'Staff time is excluded at this point.'
        case = self.staff_phrase_case(phrase)
        self.assertEqual(run_case(case)[0]['answers']['field0']['status'], 'supported')
