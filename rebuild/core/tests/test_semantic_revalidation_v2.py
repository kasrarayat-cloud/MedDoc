"""Corrected independent request, using retained synthetic evidence and offline checks only."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from core import ai_stages, semantic_generation as semantic, semantic_revalidation as recovery, testing_authority
from core.models import AIStageReceipt, Job, Usage
from core.tests import test_semantic_revalidation as historical_tests
from core.tests.test_semantic_revalidation import FIXTURE, case, chain


def failed_fixture():
    return json.loads(FIXTURE.with_name('rowan_revalidation_v1_failed.json').read_text())


class CorrectedRequestTests(SimpleTestCase):
    def setUp(self):
        self.data=case();self.original,self.requests,self.outputs,self.config=chain(self.data)

    def proposal(self,contract):
        return recovery.prepare(self.data['notes'],self.data['fields'],self.data['definitions'],
            self.requests,self.outputs,self.original,self.config,contract=contract)

    def test_actual_failed_v1_request_remains_byte_identical(self):
        fixture=failed_fixture();p=self.proposal(recovery.CONTRACT)
        p['payload']['retained_revalidation']['binding']=fixture['binding']
        envelope={'protocol':ai_stages.PROTOCOL,'stage':recovery.STAGE,'attempt':1,
            'payload':p['payload'],'schema':p['schema'],'instructions':p['instructions'],
            'max_output_tokens':ai_stages.GENERATION_MAX_OUTPUT_TOKENS,
            'timeout_seconds':ai_stages.GENERATION_TIMEOUT_SECONDS}
        self.assertEqual(hashlib.sha256(ai_stages.encode(envelope)).hexdigest(),fixture['request_sha256'])
        self.assertIn('prior_findings',p['payload'])
        self.assertEqual(p['payload']['retained_revalidation']['original_checks'],[self.outputs[2],self.outputs[4]])

    def test_v2_is_current_evidence_with_recomputed_obligations_and_historical_hashes_only(self):
        p=self.proposal(recovery.INDEPENDENT_CONTRACT);payload=p['payload']
        self.assertEqual(payload['notes'],self.data['notes'])
        self.assertEqual(payload['approved_definitions'],self.data['definitions'])
        self.assertEqual(payload['facts'],list(p['facts'].values()))
        self.assertEqual(payload['proposed_answers'],semantic._answer_preview(p['answers']))
        self.assertEqual(Counter(a['status'] for a in p['answers'].values()),{'supported':12,'missing':2})
        self.assertTrue(all(not f['issues'] for f in payload['facts']))
        self.assertEqual(payload['approved_patient_name_destinations'],['cell_0'])
        for key in ('observation_qualifier_inventory','consent_qualifier_inventory','local_patient_name_findings'):
            self.assertIn(key,payload)
        forbidden=('prior_findings','original_checks','original_assignments','checker_findings')
        def walk(value):
            if isinstance(value,dict):
                self.assertFalse(set(value).intersection(forbidden))
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(payload)
        self.assertEqual(payload['retained_revalidation']['original_requests_sha256'],
                         [semantic.digest(r) for r in self.requests])
        self.assertEqual(payload['retained_revalidation']['original_outputs_sha256'],
                         [semantic.digest(r) for r in self.outputs])
        self.assertIn(recovery.INDEPENDENT_CONTRACT,p['instructions'])

    def test_actual_new_checker_failure_is_not_reinterpreted_by_v2(self):
        p=self.proposal(recovery.INDEPENDENT_CONTRACT)
        e=SimpleNamespace(notes=self.data['notes'],template_version=SimpleNamespace(fields=self.data['fields']))
        answers=recovery._finish(e,p,self.data['definitions'],failed_fixture()['check'])
        self.assertEqual(Counter(a['status'] for a in answers.values()),{'supported':9,'ambiguous':3,'missing':2})
        for key in ('cell_5','cell_6','cell_9'):self.assertEqual(answers[key]['status'],'ambiguous')

    def test_unknown_contracts_or_changed_source_fail_before_new_proposal(self):
        for contract in (None,False,'','future-check-v3'):
            with self.subTest(contract=contract),self.assertRaises(ValidationError):self.proposal(contract)
        for suffix in ('\r\nThe findings above belong to John Smith.',
                       '\r\nThe physical examination was not performed.'):
            self.data['notes']=case()['notes']+suffix
            with self.assertRaises(ValidationError):self.proposal(recovery.INDEPENDENT_CONTRACT)

    def test_two_contracts_each_quote_one_call_and_default_remains_v1(self):
        self.assertEqual(ai_stages.revalidation_config({'mode':'fixture'})['semantic_revalidation_contract'],recovery.CONTRACT)
        for contract in recovery.CONTRACTS:
            config=ai_stages.revalidation_config({'mode':'fixture'},contract=contract)
            self.assertEqual(ai_stages.call_limit(config),1)
        self.assertEqual(getattr(settings,'SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS',()),())

    def test_migration_preserves_previous_v1_function_and_reverses_exactly(self):
        old=importlib.import_module('core.migrations.0030_retained_semantic_revalidation').REVALIDATION_SQL
        module=importlib.import_module('core.migrations.0031_retained_semantic_revalidation_v2')
        self.assertEqual(module.REVALIDATION_REVERSE,old)
        new=module.REVALIDATION_SQL
        start=new.index("  IF configuration->>'semantic_revalidation_contract'='retained-facts-independent-check-v2' THEN\n")
        end=new.index("  IF configuration ? 'semantic_revalidation_contract' THEN\n",start)
        restored=new[:start]+new[end:]
        restored=restored.replace("(configuration->>'semantic_revalidation_contract') IS NULL OR configuration->>'semantic_revalidation_contract' NOT IN ('retained-facts-independent-check-v1','retained-facts-independent-check-v2')",
            "configuration->>'semantic_revalidation_contract' IS DISTINCT FROM 'retained-facts-independent-check-v1'",1)
        self.assertEqual(restored,old)


@override_settings(SYNTHETIC_ONLY=True,AI_MODE='fixture',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',
    CODING_PROVIDER='corti',TESTING_AUTHORITY_MODE=testing_authority.MODE,
    TESTING_AUTHORITY_ID=testing_authority.AUTHORITY_ID,TESTING_AUTHORITY_SHA256=testing_authority.AUTHORITY_SHA256)
class CorrectedLifecycleTests(TestCase):
    # Reuse the original complete receipt/Corti fixture construction without
    # inheriting (and therefore repeating) the historical lifecycle campaign.
    setUp=historical_tests.RetainedLifecycleTests.setUp
    request=historical_tests.RetainedLifecycleTests.request
    execute=historical_tests.RetainedLifecycleTests.execute

    def failed_v1(self):
        offered,job=self.request();self.execute(job,failed_fixture()['check'])
        self.assertEqual(job.state,'failed',job.error)
        return offered,job

    def admit_v2(self):
        setting=override_settings(SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS=(str(self.parent.pk),))
        setting.enable();self.addCleanup(setting.disable)

    def test_v2_requires_distinct_admission_and_completed_failed_v1(self):
        offered,prior=self.failed_v1()
        self.assertFalse(recovery.offer(self.e,self.user)['available'])
        self.admit_v2();offered,job=self.request()
        self.assertIn('v2',offered['reason'])
        self.assertEqual(job.config['semantic_revalidation_contract'],recovery.INDEPENDENT_CONTRACT)
        binding=job.config['semantic_revalidation']['prior_revalidation']
        row=prior.ai_stage_receipts.get()
        self.assertEqual(binding['job_id'],str(prior.pk))
        self.assertEqual(binding['result_sha256'],prior.result_sha256)
        self.assertEqual(binding['request_sha256'],row.request_sha256)
        self.assertEqual(binding['response_sha256'],row.result_sha256)
        self.assertEqual(binding['config_sha256'],semantic.digest(prior.config))
        self.assertEqual(binding['usage_id'],str(Usage.objects.get(job=prior).pk))
        self.assertEqual(binding['actual_cost'],'0.000000000000')
        self.assertNotEqual(job.request_key,prior.request_key)
        self.assertEqual(prior.ai_stage_receipts.count(),1)

    def test_nonzero_cost_binding_uses_fixed_decimal_without_altering_accounting(self):
        _,prior=self.failed_v1();checked,row=recovery._checked_result(prior)
        usage=Usage.objects.get(job=prior)
        # Only serialization is varied in this constructed control. The actual
        # fixture receipt/usage remains zero and is never edited in storage.
        for cost in (Decimal('0.067914000000'),Decimal('0.000000001000')):
            with self.subTest(cost=str(cost)):
                row.actual_cost=cost;usage.actual_cost=cost
                aggregate=(cost,usage.units,usage.rates,usage.provider,'',usage.simulated)
                with patch.object(recovery,'_checked_result',return_value=(checked,row)),\
                     patch.object(Usage.objects,'filter',return_value=[usage]),\
                     patch.object(ai_stages,'aggregate',return_value=aggregate):
                    binding=recovery._predecessor(self.e,self.user,self.parent.pk,self.run_source.pk)
                self.assertEqual(binding['actual_cost'],format(cost,'f'))
                self.assertNotIn('E',binding['actual_cost'])
        self.assertEqual(Usage.objects.get(job=prior).actual_cost,0)

    def test_missing_or_unsent_predecessor_refuses_before_billable_stage(self):
        self.admit_v2();self.assertFalse(recovery.offer(self.e,self.user)['available'])
        with override_settings(SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS=()):
            _,prior=self.request();self.execute(prior,unknown=True)
        self.assertFalse(recovery.offer(self.e,self.user)['available'])

    def test_new_hold_preserves_all_originals_and_both_attempts_stay_consumed(self):
        old_offer,prior=self.failed_v1();original_path=prior.result_path;original_sha=prior.result_sha256
        self.admit_v2();offered,job=self.request();send,derive=self.execute(job,failed_fixture()['check'])
        self.assertEqual(job.state,'failed');self.assertEqual(send.call_count,1);derive.assert_not_called()
        self.assertEqual(job.ai_stage_receipts.get().state,'succeeded')
        self.assertEqual(Usage.objects.filter(job=job).count(),1)
        self.assertEqual(self.e.answers,self.original)
        prior.refresh_from_db();self.assertEqual((prior.result_path,prior.result_sha256),(original_path,original_sha))
        self.assertEqual(recovery.enqueue(self.e,self.user,old_offer['display_token'],0).pk,prior.pk)
        self.assertEqual(recovery.enqueue(self.e,self.user,offered['display_token'],0).pk,job.pk)
        job.request_key='failed:'+str(job.pk);job.save(update_fields=['request_key'])
        self.assertEqual(recovery.enqueue(self.e,self.user,offered['display_token'],0).pk,job.pk)
        self.assertFalse(recovery.offer(self.e,self.user)['available'])
        with self.assertRaises(ValidationError):recovery.validate_completed(job,self.original)

    def test_isolated_passing_check_has_completed_proof_and_derives_without_new_corti(self):
        self.failed_v1();self.admit_v2();_,job=self.request()
        errors=[]
        def database_trace(execute,sql,params,many,context):
            try:return execute(sql,params,many,context)
            except DatabaseError as exc:errors.append(str(exc));raise
        with patch('core.corti_prediction.execute') as corti,connection.execute_wrapper(database_trace):
            self.execute(job,real_derivative=True)
        corti.assert_not_called();self.assertEqual(job.state,'succeeded',job.error+repr(errors))
        self.assertTrue(recovery.validate_completed(job,self.e.answers))
        self.assertEqual(Counter(a['status'] for a in self.e.answers.values()),{'supported':12,'missing':2})
        self.assertFalse(any(a.get('reviewed') for a in self.e.answers.values()))
        from core import coding_recovery
        derived=self.e.coding_runs.get(config__mode='retained_live')
        self.assertEqual(coding_recovery.source_for(derived).pk,self.run_source.pk)

    def test_stale_revision_or_saved_edit_never_sends_v2(self):
        self.failed_v1();self.admit_v2();_,job=self.request()
        self.e.revision+=1;self.e.save(update_fields=['revision'])
        with patch.object(ai_stages,'execute_stage') as send:recovery.run(job)
        send.assert_not_called();job.refresh_from_db();self.assertEqual(job.state,'failed')

    def test_sql_rejects_another_v2_job_even_without_existing_v2_receipt(self):
        self.failed_v1();self.admit_v2();_,job=self.request()
        forged=Job.objects.create(encounter=self.e,user=self.user,kind='generation',state='running',revision=0,
            request_key='offline-forged-distinct-v2',config=deepcopy(job.config))
        for target in (forged,job):
            if target.state!='running':target.state='running';target.save(update_fields=['state'])
            with self.assertRaisesRegex(DatabaseError,'distinct v2'),transaction.atomic():
                AIStageReceipt.objects.create(job=target,stage=recovery.STAGE,attempt=1,config=target.config,
                    request_path='receipts/'+'c'*48+'.json',request_sha256='c'*64,
                    provider=target.config['provider'],requested_model=target.config['model'],quote_maximum=0,simulated=True)

    def test_sql_refuses_changed_predecessor_result_binding(self):
        self.failed_v1();self.admit_v2();offer=recovery.offer(self.e,self.user)
        shown=recovery.signing.loads(offer['display_token'],salt=recovery.SALT)
        original=recovery._new_config(self.e,self.user,shown['binding'],contract=recovery.INDEPENDENT_CONTRACT)
        for key in ('result_sha256','request_sha256','response_sha256','config_database_md5','usage_id'):
            config=deepcopy(original)
            config['semantic_revalidation']['prior_revalidation'][key]='0'*64
            with self.subTest(key=key),self.assertRaisesRegex(DatabaseError,'distinct v2'),transaction.atomic():
                job=Job.objects.create(encounter=self.e,user=self.user,kind='generation',state='running',revision=0,
                    request_key='offline-forged-binding',config=config)
                AIStageReceipt.objects.create(job=job,stage=recovery.STAGE,attempt=1,config=config,
                    request_path='receipts/'+'c'*48+'.json',request_sha256='c'*64,
                    provider=config['provider'],requested_model=config['model'],quote_maximum=0,simulated=True)
