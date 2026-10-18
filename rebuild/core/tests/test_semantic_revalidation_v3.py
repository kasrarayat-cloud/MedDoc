"""V3 current-source recheck: historical receipts stay distinct and immutable."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import importlib
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from core import ai_stages, coding_recovery, coding_service, generation, semantic_generation as semantic, semantic_revalidation as recovery, testing_authority
from core.models import AIStageReceipt, CodingContext, CodingDecision, CodingRun, Job, Usage
from core.tests import test_semantic_revalidation as historical


def complete_case():
    """Small synthetic current proposal; no retained clinical artifact is copied."""
    from core.tests.test_semantic_generation import fact, assignments, checker, inventory_api_facts
    from documents.semantic_preparation_roles import default_definitions
    follow='Follow-up is planned in two weeks to review symptoms, with earlier contact if symptoms persist'
    notes='Patient: Synthetic Rowan Blake\nHistory\nHe reports mild wrist pain.\nPlan\n'+follow+'.'
    fields=[{'key':f'cell_{i}','kind':'text','label':label,'locator':{'cell':i}}
        for i,label in enumerate(('Patient name','Current concern','Plan and follow-up','Preferred pharmacy'))]
    definitions=default_definitions(fields)
    definitions['cell_2'].update(version=2,answer_mode='narrative')
    facts=[fact(notes,fields,'name','Synthetic Rowan Blake',kind='identity',name_quote='Synthetic Rowan Blake'),
        fact(notes,fields,'pain','He reports mild wrist pain',name_quote='Synthetic Rowan Blake'),
        fact(notes,fields,'follow',follow,kind='follow_up',timing='future',name_quote='Synthetic Rowan Blake')]
    units,_=generation.source_units(notes,fields)
    assigned=assignments(fields,{'cell_0':['name'],'cell_1':['pain'],'cell_2':['follow']})
    repaired={'fields':deepcopy(assigned['fields'][:3])}
    return {'notes':notes,'fields':fields,'definitions':definitions,
        'extractor':inventory_api_facts(notes,units,facts),'assigner':assigned,
        'checker':checker(assigned,verdicts={f'cell_{i}':'omission' for i in range(3)}),
        'repair_assigner':repaired,'repair_checker':checker(assigned)}


class CompleteSourceProposalTests(SimpleTestCase):
    def setUp(self):
        self.data=complete_case()
        self.original,self.requests,self.outputs,self.config=historical.chain(self.data)

    def proposal(self):
        return recovery.prepare(self.data['notes'],self.data['fields'],self.data['definitions'],
            self.requests,self.outputs,self.original,self.config,contract=recovery.COMPLETE_SOURCE_CONTRACT)

    def test_proposal_uses_current_scope_and_exact_old_selections_without_prior_verdicts(self):
        before=deepcopy((self.original,self.requests,self.outputs,self.config))
        p=self.proposal();payload=p['payload']
        self.assertEqual(payload['fact_scope_contract'],semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT)
        self.assertEqual(payload['notes'],self.data['notes'])
        self.assertEqual(payload['approved_definitions'],self.data['definitions'])
        self.assertEqual(payload['proposed_answers'],semantic._answer_preview(p['answers']))
        selected={r['key']:r['fact_ids'] for r in self.outputs[1]['fields']}
        selected.update({r['key']:r['fact_ids'] for r in self.outputs[3]['fields']})
        self.assertEqual({k:a['fact_ids'] for k,a in p['answers'].items()},selected)
        self.assertEqual(before,(self.original,self.requests,self.outputs,self.config))
        forbidden={'prior_findings','original_checks','original_assignments','checker_findings','prior_revalidation'}
        def walk(value):
            if isinstance(value,dict):
                self.assertFalse(set(value)&forbidden)
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(payload)
        for key in ('clinical_context_inventory','source_governance_inventory','scoped_denial_inventory'):
            self.assertIn(key,payload)
        self.assertEqual(payload['retained_revalidation']['original_requests_sha256'],
            [semantic.digest(row) for row in self.requests])
        self.assertEqual(payload['retained_revalidation']['original_outputs_sha256'],
            [semantic.digest(row) for row in self.outputs])
        self.assertTrue(p['instructions'].endswith(semantic.COMPLETE_ASSERTION_INSTRUCTIONS+recovery.COMPLETE_SOURCE_INSTRUCTIONS))
        self.assertNotIn('independent_check',p['answers']['cell_0'])

    def test_historical_byte_contracts_stay_separate(self):
        data=historical.case();original,requests,outputs,config=historical.chain(data)
        expected=[]
        for contract in (recovery.CONTRACT,recovery.INDEPENDENT_CONTRACT):
            p=recovery.prepare(data['notes'],data['fields'],data['definitions'],
                requests,outputs,original,config,contract=contract)
            self.assertEqual(p['payload']['fact_scope_contract'],semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
            expected.append(semantic.digest(p))
        self.proposal()
        for contract,digest in zip((recovery.CONTRACT,recovery.INDEPENDENT_CONTRACT),expected):
            self.assertEqual(semantic.digest(recovery.prepare(data['notes'],data['fields'],data['definitions'],
                requests,outputs,original,config,contract=contract)),digest)

    def test_new_checker_omission_or_incorrect_fact_is_not_cleared(self):
        p=self.proposal();encounter=SimpleNamespace(notes=self.data['notes'],template_version=SimpleNamespace(fields=self.data['fields']))
        check=historical.passing(p);key=next(k for k,a in p['answers'].items() if a['fact_ids'])
        next(row for row in check['fields'] if row['key']==key)['verdict']='omission'
        self.assertNotEqual(recovery._finish(encounter,p,self.data['definitions'],check)[key]['status'],'supported')
        check=historical.passing(p)
        check['fact_findings']=[{'fact_id':p['answers'][key]['fact_ids'][0],'verdict':'incorrect','reason':'Synthetic new independent finding.'}]
        self.assertNotEqual(recovery._finish(encounter,p,self.data['definitions'],check)[key]['status'],'supported')

    def test_changed_original_request_or_answers_cannot_create_current_proposal(self):
        self.requests[4]['payload']['notes']+=' Changed source.'
        with self.assertRaises(ValidationError):self.proposal()
        self.original,self.requests,self.outputs,self.config=historical.chain(self.data)
        self.original['cell_0']['text']='A different patient'
        with self.assertRaises(ValidationError):self.proposal()

    def test_v3_binding_has_no_invented_predecessor(self):
        e=SimpleNamespace(pk='encounter',patient_id='patient',revision=0,template_version_id='template',notes='Source.')
        parent=SimpleNamespace(pk='original',result_sha256='a'*64,config={'semantic_definitions_sha256':'b'*64})
        with patch.object(recovery,'_predecessor',side_effect=AssertionError('No invented predecessor')):
            binding=recovery._binding(e,SimpleNamespace(pk='actor'),parent,{'answers':{}},[],'current-context',contract=recovery.COMPLETE_SOURCE_CONTRACT)
        self.assertEqual(len(binding),14)
        self.assertEqual(binding['parent_run_id'],'current-context')
        self.assertEqual(binding['target_scope_contract'],semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT)
        self.assertNotIn('prior_revalidation',binding)
        self.assertEqual(getattr(settings,'SEMANTIC_REVALIDATION_V3_ORIGIN_JOB_IDS',()),())
        self.assertEqual(ai_stages.call_limit(ai_stages.revalidation_config({'mode':'fixture'},contract=recovery.COMPLETE_SOURCE_CONTRACT)),1)

    def test_migration_preserves_every_prior_sql_byte_and_reverse(self):
        old=importlib.import_module('core.migrations.0031_retained_semantic_revalidation_v2').REVALIDATION_SQL
        module=importlib.import_module('core.migrations.0033_retained_semantic_revalidation_v3')
        self.assertEqual(module.REVALIDATION_REVERSE,old)
        new=module.REVALIDATION_SQL
        start=new.index("  IF configuration->>'semantic_revalidation_contract'='retained-facts-independent-check-v3' THEN\n")
        end=new.index("  ELSIF configuration ? 'semantic_revalidation_contract' THEN\n",start)
        restored=new[:start]+new[end:].replace('  ELSIF configuration', '  IF configuration',1)
        restored=restored.replace("'retained-facts-independent-check-v2','retained-facts-independent-check-v3'", "'retained-facts-independent-check-v2'",1)
        self.assertEqual(restored,old)


@override_settings(SYNTHETIC_ONLY=True,AI_MODE='fixture',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',
    CODING_PROVIDER='corti',TESTING_AUTHORITY_MODE=testing_authority.MODE,
    TESTING_AUTHORITY_ID=testing_authority.AUTHORITY_ID,TESTING_AUTHORITY_SHA256=testing_authority.AUTHORITY_SHA256)
class CompleteSourceLifecycleTests(TestCase):
    request=historical.RetainedLifecycleTests.request
    execute=historical.RetainedLifecycleTests.execute
    source_coding_config={'provider':'corti','mode':'live',
        'context_review_contract':coding_recovery.CONTEXT_CONTRACT,
        'clinical_source_contract':'source-bound-clinical-coding-v4'}

    def coding_receipt(self):
        # This small source has no provider-selected codes. It tests the real
        # durable revalidation lineage without attaching Rowan's spans to a
        # different note or making a new provider call.
        body=json.dumps({'codes':[], 'candidates':[]})
        return {'state':'succeeded','sent':True,'simulated':False,
            'raw_response':{'body':body,'redacted':False},
            'response_sha256':hashlib.sha256(body.encode()).hexdigest()}

    def setUp(self):
        with patch.object(historical,'case',side_effect=complete_case):
            historical.RetainedLifecycleTests.setUp(self)
        admitted=override_settings(SEMANTIC_REVALIDATION_V3_ORIGIN_JOB_IDS=(str(self.parent.pk),))
        admitted.enable();self.addCleanup(admitted.disable)

    def test_direct_original_has_one_new_checker_and_no_v1_or_v2_predecessor(self):
        _,job=self.request()
        self.assertEqual(job.config['semantic_revalidation_contract'],recovery.COMPLETE_SOURCE_CONTRACT)
        self.assertNotIn('prior_revalidation',job.config['semantic_revalidation'])
        self.assertFalse(Job.objects.filter(config__semantic_revalidation_contract__in=(recovery.CONTRACT,recovery.INDEPENDENT_CONTRACT)).exists())
        send,derive=self.execute(job)
        self.assertEqual(job.state,'succeeded',job.error)
        self.assertEqual(send.call_count,1);derive.assert_called_once()
        self.assertTrue(recovery.validate_completed(job,self.e.answers))
        self.assertEqual(self.parent.ai_stage_receipts.count(),5)
        self.assertEqual(job.ai_stage_receipts.count(),1)
        self.assertEqual(Usage.objects.filter(job=job).count(),1)
        self.assertFalse(any(a.get('reviewed') for a in self.e.answers.values()))

    def test_checker_hold_is_retained_and_request_key_release_cannot_retry(self):
        offered,job=self.request();p,_=recovery._bound_proposal(job)
        check=historical.passing(p);check['fields'][0]['verdict']='omission'
        send,derive=self.execute(job,check)
        self.assertEqual(job.state,'failed');self.assertEqual(send.call_count,1);derive.assert_not_called()
        self.assertEqual(self.e.answers,self.original)
        job.request_key='failed:'+str(job.pk);job.save(update_fields=['request_key'])
        self.assertEqual(recovery.enqueue(self.e,self.user,offered['display_token'],0).pk,job.pk)
        self.assertFalse(recovery.offer(self.e,self.user)['available'])

    def test_sql_refuses_duplicate_v3_job_before_any_provider_receipt(self):
        _,job=self.request()
        forged=Job.objects.create(encounter=self.e,user=self.user,kind='generation',state='running',revision=0,
            request_key='offline-forged-v3',config=deepcopy(job.config))
        for target in (job,forged):
            if target.state!='running':target.state='running';target.save(update_fields=['state'])
            with self.assertRaisesRegex(DatabaseError,'One v3'),transaction.atomic():
                AIStageReceipt.objects.create(job=target,stage=recovery.STAGE,attempt=1,config=target.config,
                    request_path='receipts/'+'c'*48+'.json',request_sha256='c'*64,
                    provider=target.config['provider'],requested_model=target.config['model'],quote_maximum=0,simulated=True)

    def test_sql_refuses_wrong_scope_source_actor_revision_and_extra_predecessor(self):
        offered=recovery.offer(self.e,self.user)
        self.assertTrue(offered['available'],offered)
        shown=recovery.signing.loads(offered['display_token'],salt=recovery.SALT)
        original=recovery._new_config(self.e,self.user,shown['binding'],contract=recovery.COMPLETE_SOURCE_CONTRACT)
        for key,value in (('target_scope_contract',semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT),
                ('source_sha256','0'*64),('actor_id','00000000-0000-0000-0000-000000000000'),
                ('revision',1),('prior_revalidation',{})):
            config=deepcopy(original);config['semantic_revalidation'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(DatabaseError,'One v3'),transaction.atomic():
                job=Job.objects.create(encounter=self.e,user=self.user,kind='generation',state='running',revision=0,
                    request_key=recovery._key(self.parent.pk,recovery.COMPLETE_SOURCE_CONTRACT),config=config)
                AIStageReceipt.objects.create(job=job,stage=recovery.STAGE,attempt=1,config=config,
                    request_path='receipts/'+'c'*48+'.json',request_sha256='c'*64,
                    provider=config['provider'],requested_model=config['model'],quote_maximum=0,simulated=True)

    def test_saved_edit_or_revision_change_refuses_before_checker(self):
        _,job=self.request()
        self.e.revision+=1;self.e.save(update_fields=['revision'])
        with patch.object(ai_stages,'execute_stage') as send:recovery.run(job)
        send.assert_not_called();self.e.refresh_from_db()
        self.assertEqual(self.e.answers,self.original)

    def test_current_context_and_original_prediction_survive_real_v3_derivation(self):
        before=CodingRun.objects.values().get(pk=self.run_source.pk)
        row=CodingContext.objects.get(encounter=self.e)
        row.data={**row.data,'identity_review_reason':'Explicit synthetic identity reviewed in this context.'}
        row.save()
        inputs,context,releases,key=coding_service.input_snapshot(self.e)
        parent=coding_recovery.reuse_for_context(self.e,self.user,inputs,context,releases,key)
        self.assertIsNotNone(parent)
        parent_before=CodingRun.objects.values().get(pk=parent.pk)
        offered,job=self.request()
        self.assertEqual(offered['parent_run_id'],str(parent.pk))
        send,_=self.execute(job,real_derivative=True)
        self.assertEqual(job.state,'succeeded',job.error)
        self.assertEqual(send.call_count,1)
        derived=CodingRun.objects.exclude(pk__in=[parent.pk,self.run_source.pk]).get()
        self.assertEqual(derived.config['clinical_source_contract'],'source-bound-clinical-coding-v5')
        self.assertEqual(derived.config['retained_prediction']['source_run_id'],str(parent.pk))
        self.assertEqual(derived.requests,[]);self.assertEqual(derived.actual_cost,0)
        self.assertEqual(derived.context,parent.context)
        self.assertEqual(coding_recovery.source_for(derived).pk,self.run_source.pk)
        self.assertEqual(CodingRun.objects.values().get(pk=self.run_source.pk),before)
        self.assertEqual(CodingRun.objects.values().get(pk=parent.pk),parent_before)
        self.assertFalse(CodingDecision.objects.filter(run=derived).exists())
