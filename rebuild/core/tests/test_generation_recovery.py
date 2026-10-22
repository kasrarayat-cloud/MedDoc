"""Ordinary, explicit same-document recovery; all provider transports are mocked."""
from copy import deepcopy
from decimal import Decimal
import json
import os
import threading
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from anthropic import BadRequestError
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import close_old_connections,connections,transaction
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from core import ai_stages,generation,generation_recovery as recovery
from core.jobs import enqueue,run_one
from core.live_results import result_snapshot
from core.models import AuditEvent,Encounter,Job,Reservation,Usage,Wallet,CodingRun,CodeSet,CodingRelease
from core.security import private_path
from core.tests.test_billing_policy import fund,STORAGES

OLD_RELEASE='d0df64d9a15407990e6f62096c837bbeb8742f8a'
NEW_RELEASE='c'*40
NEW_TRANSPORT='anthropic-nullable-singleton-arrays-v1'


class RecoveryFixture:
    def setUp(self):
        from core.tests.test_source_assertion_worker import SourceAssertionWorkerTests
        SourceAssertionWorkerTests.setUp(self)
        fund(Wallet.objects.get(user=self.user,kind='paid'),Decimal('1000'),'payment:offline-recovery')
        self.original_pipeline=ai_stages.pipeline_config
        self.old=self.reject(self.encounter)
        self.original_job=deepcopy(Job.objects.filter(pk=self.old.pk).values().get())
        self.original_stage=deepcopy(self.old.ai_stage_receipts.values().get())
        self.original_reservations=list(Reservation.objects.filter(job=self.old).values())

    def config(self):
        return {**generation.configuration(),'mode':'live','provider':'anthropic','model':'claude-sonnet-5-5',
            'input_rate':'2','cached_rate':'0.2','output_rate':'10','discount_rate':'0'}

    def prospective(self,config):
        return {**self.original_pipeline(config),recovery.TRANSPORT_KEY:NEW_TRANSPORT}

    def historical_pipeline(self,config):
        # Reconstruct the actual predecessor protocol; current queues now opt in.
        value=self.original_pipeline(config)
        value.pop(recovery.TRANSPORT_KEY,None)
        return value

    def reject(self,encounter,*,status=400,error_type='invalid_request_error',message='The compiled grammar is too large. Simplify the tool schema.',network=False):
        with override_settings(RELEASE_SHA=OLD_RELEASE),patch.object(ai_stages,'pipeline_config',side_effect=self.historical_pipeline):
            job=enqueue(encounter,self.user,config=self.config())
        if network:exception=TimeoutError('offline transport uncertainty')
        else:
            response=httpx.Response(status,request=httpx.Request('POST','https://synthetic.invalid/messages'),
                headers={'request-id':'req_offlineRejected'+job.pk.hex},json={'error':{'type':error_type,'message':message}})
            exception=BadRequestError('offline rejection',response=response,body=response.json())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=exception) as provider:
            self.assertTrue(run_one());self.assertEqual(provider.call_count,1)
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation')
        self.assertIsNone(job.ai_stage_receipts.get().actual_cost);return job

    def token(self):
        return recovery.offer(self.encounter,self.user,self.prospective(self.config()))

    def complete_successor(self,*,fail_checker=False):
        from core import source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import checker
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):new=self.retry()
        calls=[];assigned=None
        def response(payload,schema,instructions,config,maximum,timeout,on_response):
            nonlocal assigned
            role=('extractor','assigner','checker')[len(calls)];calls.append(role)
            if role=='extractor':
                # This synthetic source contains no clinical facts. All blank
                # answers stay genuinely undocumented; nothing is promoted.
                parsed={'contract':graph.CONTRACT,'facts':[],'assertions':[],'relationships':[],
                    'time_accounts':[],'unit_coverage':[{'source_unit_id':u['id'],'disposition':'nonclinical',
                    'assertion_ids':[],'affected_assertion_ids':[]}for u in payload['source_units']]}
            elif role=='assigner':
                parsed={'fields':[{'key':f['key'],'separator':'; ','components':[
                    {'id':c['id'],'disposition':'missing','fact_ids':[],'predicate_assertion_ids':[],'relationship_ids':[]}
                    for c in payload['approved_definitions'][f['key']]['component_contract']['components']]}
                    for f in payload['fields']]};assigned=parsed
            else:parsed=checker(payload['graph'],payload['fields'],payload['approved_definitions'],assigned)
            usage={'input_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0,'output_tokens':0}
            from core.clinical_schema_transport import encode
            text='invalid JSON'if fail_checker and role=='checker'else json.dumps(encode(schema,parsed))
            value=SimpleNamespace(id='msg_offlineRecovery'+new.pk.hex+role,_request_id='req_offlineRecovery'+new.pk.hex+role,
                model=config['model'],model_dump=lambda **kw:{'id':'msg_offlineRecovery'+new.pk.hex+role,
                    'content':[{'type':'text','text':text}],'usage':usage,'stop_reason':'end_turn'})
            on_response(value);cost=Decimal('0.00002')
            rates=generation.cost_rates(generation.rates(config),cost,Decimal('0'))
            return value,cost,usage,rates,text,True
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=response),patch('core.coding_hooks.after_saved_document'):
            self.assertTrue(run_one())
        new.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(new.state,'failed'if fail_checker else'succeeded',new.error);self.assertEqual(calls,['extractor','assigner','checker'])
        if fail_checker:
            self.assertEqual(self.encounter.answers,{});return new
        self.assertTrue(all(a['status']=='missing'and not a['text']for a in self.encounter.answers.values()))
        return new

    def unchanged(self):
        self.assertEqual(Job.objects.filter(pk=self.old.pk).values().get(),self.original_job)
        self.assertEqual(self.old.ai_stage_receipts.values().get(),self.original_stage)
        self.assertEqual(list(Reservation.objects.filter(job=self.old).values()),self.original_reservations)
        self.assertFalse(Usage.objects.filter(job=self.old).exists())

    def retry(self,token=None):
        return enqueue(self.encounter,self.user,config=self.config(),expected_revision=self.encounter.revision,
            recovery_token=self.token() if token is None else token)


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',ADMIN_SITE=False,TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',STORAGES=STORAGES,RELEASE_SHA=NEW_RELEASE)
class GenerationRecoveryTests(RecoveryFixture,TestCase):
    def test_retained_rejection_is_not_automatically_retried_or_cost_reconciled(self):
        self.assertIsNotNone(recovery.rejection(self.old))
        self.assertIsNone(recovery.offer(self.encounter,self.user,self.historical_pipeline(self.config())))
        self.assertEqual(enqueue(self.encounter,self.user,config=self.config()).pk,self.old.pk)
        self.assertTrue(result_snapshot(self.encounter,[self.old])['pending']);self.unchanged()

    def test_one_explicit_changed_request_reuses_same_source_and_retains_originals(self):
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            token=self.token();self.assertIsNotNone(token)
            new=self.retry(token);again=self.retry(token)
        self.assertNotEqual(new.pk,self.old.pk);self.assertEqual(again.pk,new.pk)
        self.assertTrue(again.reused);self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2)
        self.assertEqual(new.revision,self.old.revision);self.assertTrue(recovery.linked(self.old,new))
        self.assertEqual(new.config['semantic_max_calls'],5);self.assertEqual(Decimal(new.config['semantic_maximum_cost']),Decimal('8.15'))
        self.assertEqual(new.config['semantic_source_sha256'],self.old.config['semantic_source_sha256'])
        self.assertTrue(result_snapshot(self.encounter,[new,self.old])['pending']);self.unchanged()
        # After this real linked job ends, the original remains a financial hold,
        # but may no longer lock ordinary source review and completion.
        Job.objects.filter(pk=new.pk).update(state='succeeded',finished_at=timezone.now())
        new.refresh_from_db();self.assertFalse(result_snapshot(self.encounter,[new,self.old])['pending'])
        self.assertEqual(enqueue(self.encounter,self.user,config=self.config()).pk,new.pk);self.unchanged()

    def test_ordinary_https_endpoint_requires_explicit_form_and_current_signed_offer(self):
        config=self.config();new_config=self.prospective(config)
        quote=signing.dumps({'user':str(self.user.pk),'encounter':str(self.encounter.pk),'revision':self.encounter.revision,
            'config':config,'generation_config':new_config},salt='usage-quote')
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            token=self.token()
            response=self.client.post(f'/encounters/{self.encounter.pk}/generation/retry-rejected/',
                {'revision':str(self.encounter.revision),'recovery_token':token,'usage_quote':quote},HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200,response.content);self.assertFalse(response.json()['reused'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2);self.unchanged()

    def test_page_offers_separate_explicit_retry_while_normal_controls_stay_locked(self):
        config=self.config()
        with patch('core.generation.configuration',return_value=config),patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            response=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['pending_job'])
        self.assertIsNotNone(response.context['generation_recovery_offer'])
        self.assertContains(response,'data-generation-recovery-form')
        self.assertContains(response,f'/encounters/{self.encounter.pk}/generation/retry-rejected/')
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),1);self.unchanged()

    def test_saving_again_cannot_buy_another_five_calls_while_original_cost_is_unresolved(self):
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):new=self.retry()
        Job.objects.filter(pk=new.pk).update(state='failed',finished_at=timezone.now())
        response=self.client.post(f'/encounters/{self.encounter.pk}/notes/',
            {'revision':str(self.encounter.revision),'notes':self.encounter.notes})
        self.assertEqual(response.status_code,302);self.encounter.refresh_from_db()
        with self.assertRaises(ValidationError):enqueue(self.encounter,self.user,config=self.config())
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2);self.unchanged()

    def test_completed_successor_reaches_compact_approval_and_downloaded_Word(self):
        from core.document_review import review_token
        from docx import Document
        new=self.complete_successor();before=deepcopy(self.encounter.answers)
        post={'intent':'approve','review_token':review_token(self.encounter,self.user,self.version.semantic_definitions)}
        for field in self.version.fields:
            post['answer_'+field['key']]=before[field['key']]['text'];post['decision_'+field['key']]='keep'
        with patch('core.coding_hooks.after_saved_document'):
            response=self.client.post(f'/encounters/{self.encounter.pk}/review/',post)
        self.assertEqual(response.status_code,302,response.content);self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status,'finalized');self.assertEqual(self.encounter.answers,before)
        self.assertTrue(self.encounter.export_path)
        doc=Document(private_path(self.encounter.export_path))
        self.assertTrue(all(not row.cells[1].text for row in doc.tables[0].rows))
        self.assertTrue(recovery.linked(self.old,new));self.unchanged()

    def test_coding_enqueue_and_global_claim_skip_only_verified_historical_rejection(self):
        from core import coding_service as service
        self.complete_successor();self.assertTrue(service.eligible(self.encounter))
        blocked=Encounter.objects.create(department=self.department,patient=self.patient,template_version=self.version,
            created_by=self.user,service_date=self.encounter.service_date,notes=self.encounter.notes)
        Job.objects.create(encounter=blocked,user=self.user,request_key='offline-coding-busy',state='queued')
        skipped=CodingRun.objects.create(encounter=blocked,user=self.user,input_digest='0'*64,state='queued')
        release=CodeSet.objects.create(system='ICD-10-CM',version='SYNTHETIC-RECOVERY-ONLY',effective_from=self.encounter.service_date,
            effective_until=self.encounter.service_date,source_url='https://synthetic.invalid/fixture',sha256='1'*64)
        CodingRelease.objects.create(release=release,index=[],tabular={},digest='2'*64)
        result={'suggestions':[],'questions':[],'excluded':[],
            'global_blockers':[{'reason':'This fixture has no source identity or diagnosis; clinical holds remain.'}]}
        with patch('core.coding_dispatch.configuration',return_value={'provider':'synthetic-test'}),patch('core.coding_dispatch.generate',return_value=result)as dispatch:
            run=service.ensure_run(self.encounter,self.user);self.assertIsNotNone(run);self.assertEqual(run.state,'queued')
            self.assertTrue(service.run_one())
        run.refresh_from_db();skipped.refresh_from_db()
        self.assertEqual(dispatch.call_count,1);self.assertEqual(dispatch.call_args.args[0].pk,run.pk)
        self.assertEqual(skipped.state,'queued');self.assertEqual(run.state,'needs_detail')
        self.assertEqual(run.result['global_blockers'],result['global_blockers']);self.unchanged()

    def test_unlinked_unknown_remains_blocking_for_compact_review_and_coding(self):
        from core import coding_service as service
        from core.document_review import review_token
        self.encounter.status='review';self.encounter.answers={'synthetic':{'text':'Test-only unvalidated placeholder'}}
        self.encounter.save(update_fields=['status','answers'])
        self.assertFalse(service.eligible(self.encounter))
        response=self.client.post(f'/encounters/{self.encounter.pk}/review/',{'intent':'approve',
            'review_token':review_token(self.encounter,self.user,self.version.semantic_definitions)})
        self.assertEqual(response.status_code,409)
        self.assertContains(response,'pending generation or transcription',status_code=409)
        self.assertFalse(self.encounter.export_path);self.unchanged()

    def test_failed_three_stage_successor_never_reoffers_or_breaks_document_get(self):
        token=self.token();new=self.complete_successor(fail_checker=True)
        self.assertEqual(new.ai_stage_receipts.count(),3)
        self.assertIsNone(self.token())
        config=self.config()
        with patch('core.generation.configuration',return_value=config),patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            page=self.client.get(f'/encounters/{self.encounter.pk}/')
            again=self.retry(token)
        self.assertEqual(page.status_code,200);self.assertIsNone(page.context['generation_recovery_offer'])
        self.assertEqual(again.pk,new.pk);self.assertTrue(again.reused)
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2);self.unchanged()

    def test_missing_forged_expired_or_wrong_actor_offer_never_creates_a_job(self):
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            token=self.token()
            for bad in ('',token+'changed'):
                with self.subTest(bad=bad),self.assertRaises(ValidationError):self.retry(bad)
            with patch('django.core.signing.time.time',return_value=9999999999),self.assertRaises(ValidationError):self.retry(token)
            value=signing.loads(token,salt=recovery.SALT);value['actor']='00000000-0000-0000-0000-000000000001'
            with self.assertRaises(ValidationError):self.retry(signing.dumps(value,salt=recovery.SALT))
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),1);self.unchanged()

    def test_changed_source_definitions_provider_rates_and_same_release_remain_blocked(self):
        token=self.token();self.assertIsNotNone(token)
        with override_settings(RELEASE_SHA=OLD_RELEASE):self.assertIsNone(self.token())
        for change in ({'input_rate':'3'},{'model':'other-model'},{'provider':'openai'}):
            with self.subTest(change=change):self.assertIsNone(recovery.offer(self.encounter,self.user,self.prospective({**self.config(),**change})))
        self.encounter.notes+=' Changed source.';self.assertIsNone(self.token());self.encounter.notes=self.encounter.notes[:-16]
        self.unchanged()

    def test_corrupt_private_error_or_duplicate_audit_is_not_terminal_rejection(self):
        proof=recovery.rejection(self.old);event=AuditEvent.objects.get(pk=proof['error_audit'])
        path=private_path(event.details['evidence_path']);raw=path.read_bytes();path.write_bytes(raw+b' ')
        self.assertIsNone(recovery.rejection(self.old));path.write_bytes(raw)
        AuditEvent.objects.create(actor=self.user,department=self.department,organization=self.department.organization,
            action=event.action,target=event.target,details=event.details)
        self.assertIsNone(recovery.rejection(self.old));self.unchanged()

    def test_security_denials_network_unknown_and_authentication_errors_stay_held(self):
        cases=[{'status':401},{'status':403},{'network':True},{'error_type':'authentication_error'}]
        for case in cases:
            encounter=Encounter.objects.create(department=self.department,patient=self.patient,template_version=self.version,
                created_by=self.user,service_date=self.encounter.service_date,notes=self.encounter.notes)
            job=self.reject(encounter,**case)
            with self.subTest(case=case):
                self.assertIsNone(recovery.rejection(job));self.assertTrue(recovery.pending_jobs([job]))

    def test_machine_rejection_does_not_guess_from_provider_message_words(self):
        encounter=Encounter.objects.create(department=self.department,patient=self.patient,template_version=self.version,
            created_by=self.user,service_date=self.encounter.service_date,notes=self.encounter.notes)
        job=self.reject(encounter,message='An invalid request was rejected.')
        self.assertIsNotNone(recovery.rejection(job))
        self.assertEqual(enqueue(encounter,self.user,config=self.config()).pk,job.pk)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(),1)

    def test_cumulative_stage_count_and_exposure_are_stricter_than_new_job_quote(self):
        from types import SimpleNamespace
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):new=self.retry()
        with transaction.atomic():
            recovery.enforce_stage_budget(new,[],Decimal('1.63'))
            rows=[SimpleNamespace(quote_maximum=Decimal('1'),actual_cost=Decimal('0.1'))for _ in range(4)]
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(new,rows,Decimal('0.01'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(new,[],Decimal('8.15'))
            # A metered cost above its quote counts in full; it is not hidden by
            # choosing the lower estimate or by the old unknown cost being null.
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(new,[SimpleNamespace(quote_maximum=Decimal('1'),actual_cost=Decimal('8'))],Decimal('0.01'))
        self.unchanged()

    def test_stage_budget_refusal_precedes_new_receipt_retention_and_provider_send(self):
        from core import source_assertion_graph as graph
        new=self.retry();new.state='running';new.save(update_fields=['state'])
        with patch.object(recovery,'enforce_stage_budget',side_effect=ai_stages.StageNotSent('Offline exhausted exposure'))as budget,\
            patch.object(ai_stages,'retain')as retain,patch.object(ai_stages,'_response')as send,\
            patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}):
            with self.assertRaises(ai_stages.StageNotSent):
                ai_stages.execute_stage(job=new,stage='extractor',payload={},schema=graph.extraction_schema(),
                    instructions='Source constraints unchanged.',config=new.config)
            self.assertEqual(budget.call_count,1);retain.assert_not_called();send.assert_not_called()
        self.assertEqual(new.ai_stage_receipts.count(),0);self.unchanged()

    def test_forged_successor_metadata_without_application_audit_does_not_unlock_original(self):
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):new=self.retry()
        with patch.object(AuditEvent.objects,'filter') as events:
            events.return_value.exists.return_value=False
            # Supplying no retained error audit also fails closed.
            events.return_value.__iter__.return_value=iter([])
            self.assertFalse(recovery.linked(self.old,new))
        self.unchanged()


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',ADMIN_SITE=False,TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',STORAGES=STORAGES,RELEASE_SHA=NEW_RELEASE)
class RecoverySingleflightTests(RecoveryFixture,TransactionTestCase):
    def test_two_explicit_requests_serialize_on_encounter_to_one_new_job(self):
        token=self.token();barrier=threading.Barrier(2);ids=[];errors=[]
        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                job=enqueue(self.encounter,self.user,config=self.config(),expected_revision=0,recovery_token=token)
                ids.append(job.pk)
            except Exception as exc:errors.append(type(exc).__name__+':'+str(exc))
            finally:connections.close_all()
        threads=[threading.Thread(target=attempt)for _ in range(2)]
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            for thread in threads:thread.start()
            for thread in threads:thread.join(timeout=30)
        self.assertFalse(any(t.is_alive()for t in threads));self.assertEqual(errors,[])
        self.assertEqual(len(ids),2);self.assertEqual(len(set(ids)),1)
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2);self.unchanged()
