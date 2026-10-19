"""Versioned encounter permission, distinct from event time and coding authority."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from documents import component_contracts as cc, semantic_preparation_roles as roles
from core import component_review as editor, semantic_preparation as workflow
from core import source_assertion_generation as generation, source_assertion_graph as graph
from core import source_assertion_coding as coding
from core.tests import test_source_assertion_graph as fixtures


def topic_case(*, current=True, past=True, contract=cc.ENCOUNTER_CONTRACT, encounter_scope='all_documented',
               subject='patient', encounter='past', event_time='past', polarity='negated'):
    present = 'Today the patient denies nausea.'
    historical = 'At the prior visit on 21 May 2026, '+('her sister' if subject == 'other' else 'the patient')+' denied vomiting.'
    notes = 'Patient: Synthetic Ada Vale'+ ('\n'+present if current else '')+ ('\n'+historical if past else '')
    fields, definitions = fixtures.definitions(('All documented symptom negatives',))
    definition = definitions['field0']
    definition.update(meaning='All documented symptom negatives, preserving their ownership and time.',
                      scope={'subject':'patient','temporality':'any','polarity':'negative'})
    definition['component_contract'] = cc.fixture_for(fields[0], definition, contract)
    if contract == cc.ENCOUNTER_CONTRACT:
        definition['component_contract']['components'][0]['encounter_scope'] = encounter_scope
    facts = [fixtures.fact(notes,'f0','Synthetic Ada Vale',kind='identity')]
    assertions = [fixtures.assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',
                  identity_role='patient_name',consumer_role='none')]
    picks, roots = [], []
    for identifier, text, who, when, enc, pol, nominal in (
        ('current',present,'patient','current','current','negated','nausea'),
        ('past',historical,subject,event_time,encounter,polarity,'vomiting')):
        if not (current if identifier=='current' else past): continue
        fact = fixtures.fact(notes,'f_'+identifier,text,subject=who,timing=when,polarity=pol)
        fact['timing']['span'] = fixtures.ref(notes,'21 May 2026' if identifier=='past' else 'Today')
        if who == 'other': fact['subject']['name_span'] = fixtures.ref(notes,'her sister')
        facts.append(fact)
        assertions.append(fixtures.assertion(notes,identifier,[fact['id']],text,subject=who,
            temporality=when,encounter=enc,polarity=pol,consumer_ref=fixtures.ref(notes,nominal),
            qualifier_refs=[fixtures.ref(notes,text)]))
        picks.append(fact['id']);roots.append(identifier)
    return [notes, fields, definitions, fixtures.extraction(notes,facts,assertions),
            fixtures.assignments(fields,{'field0':picks},{'field0':roots})]


def coding_run(result):
    interpretation = result['interpretation']; identity = interpretation['identity']
    inputs = {k:identity[k] for k in ('patient_id','encounter_id','department_id','service_date','template_version_id')}
    inputs.update(notes=interpretation['notes'],answers=result['answers'],source_interpretation=interpretation,
        patient_identity={'display_name':identity['patient_display_name'],'reference':identity['patient_reference']},
        template={'fields_sha256':graph.digest(interpretation['fields']),
                  'definitions_sha256':graph.digest(interpretation['definitions'])})
    return N(inputs=inputs,config={'clinical_source_contract':coding.CONTRACT})


class ComponentEncounterScopeTests(SimpleTestCase):
    def assert_replay(self, case, result):
        self.assertTrue(graph.same(generation.restore(case[0],result['interpretation']),result['answers']))
        graph.validate_interpretation(case[0],result['interpretation'])
        for field in case[1]:
            generation.validate_stored_answer(case[0],field,case[2][field['key']],
                result['answers'][field['key']],result['interpretation'])

    def test_one_open_topic_accepts_documented_current_past_or_both_without_optional_parts(self):
        for current,past in ((True,True),(True,False),(False,True)):
            case=topic_case(current=current,past=past); result,calls=fixtures.run_case(case)
            answer=result['answers']['field0']
            self.assertEqual(answer['status'],'supported')
            self.assertEqual(answer['text'],'; '.join(f['value_span']['quote'] for f in case[3]['facts'][1:]))
            self.assertEqual(len(answer['components']),1)
            self.assertEqual(len(calls),3)
            self.assertEqual(case[2]['field0']['component_contract']['components'][0]['required'],True)
            self.assert_replay(case,result)

    def test_truly_undocumented_topic_is_missing(self):
        case=topic_case(current=False,past=False);result,_=fixtures.run_case(case)
        self.assertEqual(result['answers']['field0']['status'],'missing')
        self.assert_replay(case,result)

    def test_current_never_accepts_past_and_past_never_accepts_current(self):
        for requested,current,past,accepted in (
                ('current',True,False,True),('current',False,True,False),('current',True,True,False),
                ('past',False,True,True),('past',True,False,False),('past',True,True,False)):
            case=topic_case(current=current,past=past,encounter_scope=requested)
            result,_=fixtures.run_case(case)
            self.assertEqual(result['answers']['field0']['status']=='supported',accepted)
            self.assert_replay(case,result)

    def test_other_owner_unknown_future_encounter_and_wrong_event_or_polarity_stay_held(self):
        for change in ({'subject':'other'},{'subject':'uncertain'},{'encounter':'unknown'},
                       {'encounter':'future'},{'event_time':'current'},{'event_time':'future'},
                       {'event_time':'unspecified'},{'polarity':'affirmed'},{'polarity':'uncertain'}):
            case=topic_case(**change)
            with self.subTest(change=change):
                result,_=fixtures.run_case(case)
                self.assertNotEqual(result['answers']['field0']['status'],'supported')
                self.assert_replay(case,result)

    def test_independent_wrong_time_or_negation_verdict_cannot_be_overridden(self):
        for verdict,reason in (('incorrect','Past encounter claim is incorrect.'),('unknown','Negation is not established.')):
            case=topic_case()
            def disagree(value,*_):
                next(a for a in value['assertions'] if a['id']=='past').update(verdict=verdict,reason=reason)
            result,_=fixtures.run_case(case,disagree)
            self.assertNotEqual(result['answers']['field0']['status'],'supported')
            self.assert_replay(case,result)

    def test_clipped_date_or_negation_does_not_become_complete(self):
        for clip in ('the patient denied vomiting.','vomiting'):
            case=topic_case(); case[3]['facts'][-1]['value_span']=fixtures.ref(case[0],clip)
            result,_=fixtures.run_case(case)
            answer=result['answers']['field0']
            self.assertNotEqual(answer['status'],'supported')
            self.assertIn('omitted_literal_qualifier',[r['code'] for r in answer['route_diagnostics']['holds']])
            self.assertIn('past_encounter_time_omitted',[r['code'] for r in answer['route_diagnostics']['holds']])
            self.assert_replay(case,result)

    def test_past_date_reference_still_required_when_not_duplicated_as_qualifier(self):
        case=topic_case();case[3]['assertions'][-1]['qualifier_refs']=[fixtures.ref(case[0],'denied')]
        case[3]['facts'][-1]['value_span']=fixtures.ref(case[0],'the patient denied vomiting.')
        result,_=fixtures.run_case(case)
        self.assertIn('past_encounter_time_omitted',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])
        case=topic_case();case[3]['facts'][-1]['timing']['span']=None
        result,_=fixtures.run_case(case)
        self.assertIn('past_encounter_time_unestablished',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])

    def test_source_omission_and_required_sibling_are_not_waived(self):
        case=topic_case();case[4]['fields'][0]['components'][0]['fact_ids']=['f_current']
        case[4]['fields'][0]['components'][0]['predicate_assertion_ids']=['current']
        def omission(value,*_):
            value['components'][0].update(verdict='omission',cause='extraction',reason='Documented prior denial omitted.')
            value['fields'][0].update(verdict='unknown',cause='extraction',reason='The complete topic is not covered.')
        result,calls=fixtures.run_case(case,omission)
        self.assertNotEqual(result['answers']['field0']['status'],'supported');self.assertEqual(len(calls),3)
        case=topic_case(current=True,past=False)
        extra=deepcopy(case[2]['field0']['component_contract']['components'][0]);extra.update(id='other',meaning='Another requested value.')
        case[2]['field0']['component_contract']['components'].append(extra)
        case[4]['fields'][0]['components'].append({'id':'other','disposition':'missing','fact_ids':[],
            'predicate_assertion_ids':[],'relationship_ids':[]})
        result,_=fixtures.run_case(case)
        self.assertIn('partial_component_coverage',[h['code'] for h in result['answers']['field0']['route_diagnostics']['holds']])

    def test_current_encounter_future_event_keeps_literal_plan_and_remains_noncoding(self):
        notes='Patient: Synthetic Ada Vale\nA scan is planned for tomorrow if symptoms persist.'
        fields,defs=fixtures.definitions(('Future plan',));d=defs['field0']
        d['scope']['temporality']='future';d['component_contract']=cc.fixture_for(fields[0],d,cc.ENCOUNTER_CONTRACT)
        d['component_contract']['components'][0]['encounter_scope']='all_documented'
        phrase=notes.splitlines()[-1]
        facts=[fixtures.fact(notes,'f0','Synthetic Ada Vale',kind='identity'),
               fixtures.fact(notes,'f1',phrase,timing='future')]
        assertions=[fixtures.assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
            fixtures.assertion(notes,'a1',['f1'],phrase,kind='context',consumer_role='none',temporality='future',certainty='conditional',
                qualifier_refs=[fixtures.ref(notes,phrase)])]
        case=[notes,fields,defs,fixtures.extraction(notes,facts,assertions),fixtures.assignments(fields,{'field0':['f1']})]
        result,_=fixtures.run_case(case)
        self.assertEqual(result['answers']['field0']['text'],phrase)
        self.assertEqual(result['answers']['field0']['status'],'supported')
        self.assertEqual(coding.inventory(coding_run(result))['items'],[])
        self.assert_replay(case,result)

    def test_clinical_past_permission_never_grants_current_coding_authority(self):
        case=topic_case(current=False,past=True)
        case[2]['field0']['scope']['polarity']='positive'
        case[2]['field0']['component_contract']['components'][0]['scope']['polarity']='positive'
        # Construct a differently worded positive historical condition with its
        # own exact retained references, not a relabelled negative assertion.
        phrase='At the prior visit on 21 May 2026, the patient reported vomiting.'
        old=case[0].splitlines()[-1];case[0]=case[0].replace(old,phrase)
        f=case[3]['facts'][-1];f.update(polarity='affirmed',value_span=fixtures.ref(case[0],phrase))
        a=case[3]['assertions'][-1];a.update(polarity='affirmed',predicate_refs=[fixtures.ref(case[0],phrase)],
            qualifier_refs=[fixtures.ref(case[0],phrase)],consumer_ref=fixtures.ref(case[0],'vomiting'))
        case[3]=fixtures.extraction(case[0],case[3]['facts'],case[3]['assertions'])
        result,_=fixtures.run_case(case);self.assertEqual(result['answers']['field0']['status'],'supported')
        inventory=coding.inventory(coding_run(result))
        self.assertEqual(inventory['items'],[])
        self.assertEqual(inventory['unresolved'],[])
        self.assertEqual([r['assertion_id'] for r in inventory['excluded']],['past'])

    def test_v1_routing_and_prompt_constants_remain_historical(self):
        for past,expected in ((True,'ambiguous'),(False,'supported')):
            case=topic_case(past=past,contract=cc.CONTRACT);result,_=fixtures.run_case(case)
            self.assertEqual(result['answers']['field0']['status'],expected)
            self.assert_replay(case,result)
            for text in (generation.EXTRACT_INSTRUCTIONS,generation.ASSIGN_INSTRUCTIONS,generation.CHECK_INSTRUCTIONS):
                self.assertEqual(generation.instructions_for(case[2],text),text)
        case=topic_case()
        self.assertTrue(generation.instructions_for(case[2],generation.CHECK_INSTRUCTIONS).endswith(
            generation.ENCOUNTER_SCOPE_INSTRUCTIONS))

    def test_retained_scope_tampering_changes_interpretation_and_restore_fails(self):
        case=topic_case();result,_=fixtures.run_case(case);bad=deepcopy(result['interpretation'])
        bad['definitions']['field0']['component_contract']['components'][0]['encounter_scope']='current'
        bad['sha256']=graph.digest({k:v for k,v in bad.items() if k!='sha256'})
        with self.assertRaises(ValidationError):generation.restore(case[0],bad)


class ComponentEncounterPreparationTests(SimpleTestCase):
    def prep(self, contract=cc.ENCOUNTER_CONTRACT):
        from core.tests.test_component_review import ComponentReviewPureTests
        prep,field,actor=ComponentReviewPureTests().make()
        if contract==cc.ENCOUNTER_CONTRACT:prep.config[cc.CONFIG_KEY]=contract
        for response in (prep.proposal,prep.checker):
            d=response['fields'][0]['definition'];d['component_contract']=cc.fixture_for(field,d,contract)
        return prep,field,actor

    def test_schema_requires_closed_encounter_scope_for_both_independent_roles(self):
        for role in ('proposer','checker'):
            schema=roles.role_schema(role,4,component_contract=cc.ENCOUNTER_CONTRACT)
            contract=schema['properties']['fields']['items']['properties']['definition']['properties']['component_contract']
            self.assertEqual(contract['properties']['contract']['enum'],[cc.ENCOUNTER_CONTRACT])
            part=contract['properties']['components']['items']
            self.assertIn('encounter_scope',part['required']);self.assertFalse(part['additionalProperties'])
            self.assertEqual(part['properties']['encounter_scope']['enum'],list(cc.ENCOUNTER_SCOPES))
            text=roles.role_instructions(role,4,component_contract=cc.ENCOUNTER_CONTRACT)
            self.assertIn('one complete topic component',text)
            self.assertIn('independently of scope.temporality',text)

    def test_required_scope_and_v1_shape_do_not_accept_unknown_or_silent_upgrade(self):
        case=topic_case();field=case[1][0];d=case[2]['field0']
        self.assertIs(cc.validate(field,d),d['component_contract'])
        for change in (lambda c:c.pop('encounter_scope'),lambda c:c.update(encounter_scope='any'),
                       lambda c:c.update(encounter_scope=True),lambda c:c.update(required=False)):
            bad=deepcopy(d);change(bad['component_contract']['components'][0])
            with self.assertRaises(roles.DefinitionError):cc.validate(field,bad)
        bad=deepcopy(d);bad['component_contract']['contract']=cc.CONTRACT
        with self.assertRaises(roles.DefinitionError):cc.validate(field,bad)
        for contract in ('unknown',None,False):
            with self.assertRaises(roles.DefinitionError):cc.configured({'semantic_definition_version':4,cc.CONFIG_KEY:contract})
        self.assertEqual(cc.configured({'semantic_definition_version':4}),cc.CONTRACT)

    def test_stage_uses_pinned_v2_schema_instructions_and_rejects_contract_downgrade(self):
        prep,field,_=self.prep()
        def send(**kw):
            self.assertEqual(kw['config'][cc.CONFIG_KEY],cc.ENCOUNTER_CONTRACT)
            self.assertIn(cc.ENCOUNTER_CONTRACT,kw['instructions'])
            return deepcopy(kw['fixture_output'])
        with patch('core.semantic_preparation.ai_stages.execute_stage',side_effect=send):
            for role in ('proposer','checker'):
                result=workflow._call_role(prep,role)
                self.assertEqual(result['fields'][0]['definition']['component_contract']['contract'],cc.ENCOUNTER_CONTRACT)
        response=deepcopy(prep.proposal);response['fields'][0]['definition']['component_contract']=cc.fixture(field,response['fields'][0]['definition'])
        with patch('core.semantic_preparation.ai_stages.execute_stage',return_value=response):
            with self.assertRaises(roles.DefinitionError):workflow._call_role(prep,'proposer')
        with self.assertRaises(roles.DefinitionError):workflow._require_definition_version(prep.proposal,4,cc.CONTRACT)

    def test_editor_roundtrip_explicit_scope_without_question_destination_or_version_change(self):
        from core.tests.test_component_review import editor_post
        prep,field,actor=self.prep();d=workflow.corrected_definitions(prep)[field['key']]
        for scope in cc.ENCOUNTER_SCOPES:
            post=editor_post(prep,field,d,actor);post['part_0_encounter_scope']=scope
            changed=editor.posted_definition(prep,field,d,post)
            roles.validate_definitions([field],{field['key']:changed})
            expected=deepcopy(d);expected['component_contract']['components'][0]['encounter_scope']=scope
            self.assertEqual(changed,expected)
        for mutate in (lambda p:p.pop('part_0_encounter_scope'),lambda p:p.appendlist('part_0_encounter_scope','past')):
            post=editor_post(prep,field,d,actor);mutate(post)
            with self.assertRaises(ValidationError):editor.posted_definition(prep,field,d,post)
        self.assertEqual(editor.parts_for(field,d)[-1]['encounter_scope'],'')

    def test_old_editor_retains_exact_v1_and_rejects_injected_new_control(self):
        from core.tests.test_component_review import editor_post
        prep,field,actor=self.prep(cc.CONTRACT);d=workflow.corrected_definitions(prep)[field['key']]
        post=editor_post(prep,field,d,actor)
        self.assertEqual(editor.posted_definition(prep,field,d,post),d)
        post['part_0_encounter_scope']='all_documented'
        with self.assertRaises(ValidationError):editor.posted_definition(prep,field,d,post)

    def test_draft_and_summary_bind_and_display_encounter_scope_separately(self):
        prep,field,actor=self.prep();token=editor.token_for(prep,actor,field['key'])
        before=workflow.approval_binding(prep)
        prep.proposal['fields'][0]['definition']['component_contract']['components'][0]['encounter_scope']='all_documented'
        self.assertNotEqual(workflow.approval_binding(prep),before)
        with self.assertRaises(ValidationError):editor.verify_token(prep,actor,field['key'],token)
        contract=prep.proposal['fields'][0]['definition']['component_contract']
        text=render_to_string('template_review_components.html',{'component_contract':contract})
        self.assertIn('this encounter and documented past encounters',text)
        self.assertIn('Timing:',text)
