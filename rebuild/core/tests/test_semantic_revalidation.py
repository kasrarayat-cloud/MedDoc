"""Retained synthetic recovery; all transports are explicitly offline fixtures."""
from collections import Counter
from copy import deepcopy
from contextlib import nullcontext
from decimal import Decimal
from datetime import date
import hashlib
import importlib
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,transaction
from django.test import SimpleTestCase,TestCase,override_settings
from django.utils import timezone

from core import ai_stages,generation,semantic_generation as semantic,semantic_revalidation as recovery,testing_authority,coding_service,corti_prediction,corti_coding
from core.models import AIStageReceipt,CodingRun,CodingContext,Code,CodeSet,CodingRelease,Department,Encounter,Job,Membership,Organization,Patient,Template,TemplateVersion,User,Usage

FIXTURE=Path(__file__).with_name('fixtures')/'rowan_objective_retained.json'

def case():
    return json.loads(FIXTURE.read_text())

def chain(data):
    outputs=[data[k] for k in ('extractor','assigner','checker','repair_assigner','repair_checker')]
    requests=[]
    def send(role,attempt,payload,schema,instructions):
        requests.append({'protocol':ai_stages.PROTOCOL,'stage':role,'attempt':attempt,
                         'payload':deepcopy(payload),'schema':schema,'instructions':instructions})
        return deepcopy(outputs[len(requests)-1])
    config={'semantic_fact_reference_contract':semantic.REFERENCE_INVENTORY_CONTRACT,
            'semantic_fact_scope_contract':semantic.LITERAL_SOURCE_SCOPE_CONTRACT}
    original=semantic.run(data['notes'],data['fields'],data['definitions'],send,
        reference_contract=config['semantic_fact_reference_contract'],scope_contract=config['semantic_fact_scope_contract'])
    return original,requests,outputs,config

def passing(proposal):
    return {'fields':[{'key':key,'verdict':'pass' if a['fact_ids'] else 'missing',
                      'fact_ids':a['fact_ids'],'reason':'Offline synthetic independent-check fixture.'}
                     for key,a in proposal['answers'].items()],'fact_findings':[]}

class RetainedProposalTests(SimpleTestCase):
    def setUp(self):
        self.data=case();self.original,self.requests,self.outputs,self.config=chain(self.data)

    def proposal(self):
        return recovery.prepare(self.data['notes'],self.data['fields'],self.data['definitions'],
            self.requests,self.outputs,self.original,self.config)

    def test_new_local_proposal_preserves_prior_ambiguous_result_and_all_selected_facts(self):
        original=deepcopy(self.original);outputs=deepcopy(self.outputs)
        proposal=self.proposal()
        self.assertEqual(Counter(a['status'] for a in original.values()),{'supported':11,'ambiguous':1,'missing':2})
        self.assertEqual(Counter(a['status'] for a in proposal['answers'].values()),{'supported':12,'missing':2})
        self.assertEqual(proposal['answers']['cell_6']['fact_ids'],original['cell_6']['fact_ids'])
        self.assertIn('no rebound',proposal['answers']['cell_6']['text'].lower())
        self.assertEqual((self.original,self.outputs),(original,outputs))
        self.assertNotIn('independent_check',proposal['answers']['cell_6'])
        self.assertEqual(proposal['payload']['notes'],self.data['notes'])
        self.assertEqual(proposal['payload']['approved_definitions'],self.data['definitions'])
        self.assertEqual(proposal['payload']['retained_revalidation']['original_checks'],[outputs[2],outputs[4]])

    def test_old_checker_does_not_resolve_new_proposal_without_new_pass(self):
        p=self.proposal();e=SimpleNamespace(notes=self.data['notes'],template_version=SimpleNamespace(fields=self.data['fields']))
        old=recovery._finish(e,p,self.data['definitions'],self.outputs[4])
        self.assertEqual(old['cell_6']['status'],'ambiguous')
        new=recovery._finish(e,p,self.data['definitions'],passing(p))
        self.assertEqual(Counter(a['status'] for a in new.values()),{'supported':12,'missing':2})
        self.assertEqual(new['cell_12']['text'],'24')
        self.assertEqual(new['cell_0']['text'],'Synthetic Rowan Blake')
        self.assertTrue(all(not new[key]['text'] for key in ('cell_10','cell_11')))

    def test_original_request_or_answer_tampering_is_refused(self):
        self.requests[4]['payload']['notes']+=' changed'
        with self.assertRaises(ValidationError):self.proposal()
        self.original,self.requests,self.outputs,self.config=chain(self.data)
        self.original['cell_0']['text']='Other Patient'
        with self.assertRaises(ValidationError):self.proposal()

    def test_incorrect_or_incomplete_new_checker_stays_held(self):
        p=self.proposal();check=passing(p)
        check['fields'][6]['fact_ids']=[]
        e=SimpleNamespace(notes=self.data['notes'],template_version=SimpleNamespace(fields=self.data['fields']))
        result=recovery._finish(e,p,self.data['definitions'],check)
        self.assertEqual(result['cell_6']['status'],'ambiguous')
        check=passing(p);check['fact_findings']=[{'fact_id':'f20','verdict':'incorrect','reason':'Offline negative control.'}]
        self.assertEqual(recovery._finish(e,p,self.data['definitions'],check)['cell_6']['status'],'ambiguous')

    def test_one_call_quote_does_not_change_historical_pipeline(self):
        base={'mode':'fixture'}
        self.assertEqual(ai_stages.pipeline_config(base)['semantic_max_calls'],5)
        self.assertEqual(ai_stages.revalidation_config(base)['semantic_max_calls'],1)
        for bad in (None,'',False,'unknown'):
            with self.assertRaises(ValidationError):ai_stages.call_limit({'semantic_revalidation_contract':bad})

    def test_migration_preserves_full_historical_body_after_removing_new_arms(self):
        old=importlib.import_module('core.migrations.0026_semantic_stage_receipts').SEMANTIC_SQL
        new=importlib.import_module('core.migrations.0030_retained_semantic_revalidation')
        original=re.search(r'CREATE FUNCTION quillmd_ai_stage_guard\(\).*?\$\$;',old,re.S).group()
        self.assertEqual(new.REVALIDATION_REVERSE.strip(),original.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1))
        restored=new.REVALIDATION_SQL.strip()
        # Each addition wraps the unchanged legacy code in an explicit ELSE.
        for marker,end in (("  IF configuration ? 'semantic_revalidation_contract' THEN\n",'\n  END IF;'),):
            while marker in restored:
                start=restored.index(marker);otherwise=restored.index('\n  ELSE\n',start)
                closing=restored.index(end,otherwise)
                restored=restored[:start]+restored[otherwise+len('\n  ELSE\n'):closing]+restored[closing+len(end):]
        self.assertEqual(restored,new.REVALIDATION_REVERSE.strip())


@override_settings(SYNTHETIC_ONLY=True,AI_MODE='fixture',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',
    CODING_PROVIDER='corti',TESTING_AUTHORITY_MODE=testing_authority.MODE,TESTING_AUTHORITY_ID=testing_authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=testing_authority.AUTHORITY_SHA256)
class RetainedLifecycleTests(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        setting=override_settings(MEDIA_ROOT=Path(directory.name));setting.enable();self.addCleanup(setting.disable)
        self.data=case()
        self.user=User.objects.create_user(id='5f4d1a3d-eeb6-4207-b1df-4597dc696e82',username='offline-revalidation',verified_at=timezone.now())
        org=Organization.objects.create(name='Offline synthetic recovery')
        department=Department.objects.create(id='46a5abdd-36f1-41f0-968f-8c09c39d9daa',name='Offline test',organization=org)
        Membership.objects.create(user=self.user,department=department,role='clinician')
        template=Template.objects.create(department=department,name='Offline Rowan fixture',format='docx',original_name='offline.docx',
            original_path='offline.docx',sha256='a'*64,created_by=self.user)
        version=TemplateVersion.objects.create(template=template,number=1,fields=self.data['fields'],created_by=self.user)
        patient=Patient.objects.create(department=department,display_name='Synthetic Rowan Blake',reference='SYN-RB-1016',created_by=self.user)
        self.e=Encounter.objects.create(department=department,patient=patient,template_version=version,created_by=self.user,
            notes=self.data['notes'],service_date=date(2026,10,16),status='review')
        config=ai_stages.pipeline_config(generation.configuration())
        config.update(semantic_template_version=str(version.pk),semantic_source_sha256=hashlib.sha256(self.e.notes.encode()).hexdigest(),
            semantic_definitions_sha256=semantic.digest(self.data['definitions']),semantic_fact_reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,
            semantic_fact_scope_contract=semantic.LITERAL_SOURCE_SCOPE_CONTRACT)
        self.parent=Job.objects.create(encounter=self.e,user=self.user,kind='generation',state='running',revision=0,
            request_key='offline-original',config=config)
        outputs=[self.data[k] for k in ('extractor','assigner','checker','repair_assigner','repair_checker')];count=0
        def send(role,attempt,payload,schema,instructions):
            nonlocal count
            output=outputs[count];count+=1
            return ai_stages.execute_stage(job=self.parent,stage=role,attempt=attempt,payload=payload,schema=schema,
                                          instructions=instructions,config=config,fixture_output=output)
        answers=semantic.run(self.e.notes,version.fields,self.data['definitions'],send,
            reference_contract=config['semantic_fact_reference_contract'],scope_contract=config['semantic_fact_scope_contract'])
        path,sha=ai_stages.retain({'contract':semantic.CONTRACT,'answers':answers,
            'stages':[str(pk) for pk in self.parent.ai_stage_receipts.order_by('created_at','pk').values_list('pk',flat=True)]})
        self.parent.result_path=path;self.parent.result_sha256=sha;self.parent.state='succeeded';self.parent.finished_at=timezone.now();self.parent.save()
        self.e.answers=answers;self.e.save();self.original=deepcopy(answers)
        # Tiny synthetic reference tests local persistence, not official coverage.
        from core.coding_terminology import parse_reference,reference_digest
        release=CodeSet.objects.create(system='ICD-10-CM',version='SYNTHETIC-UNIT-FY2027',effective_from=date(2026,10,1),
            effective_until=date(2027,9,30),sha256='b'*64,source_url='https://www.cms.gov/synthetic-unit-reference')
        rows={'R10.13':'Epigastric pain','R14.0':'Abdominal distension (gaseous)'}
        for code,description in rows.items():Code.objects.create(release=release,code=code,description=description)
        parsed=parse_reference('<ICD10CM.index><version>2027</version><letter><mainTerm><title>Pain</title><term><title>epigastric</title><code>R10.13</code></term></mainTerm><mainTerm><title>Bloating</title><code>R14.0</code></mainTerm></letter></ICD10CM.index>',
            '<ICD10CM.tabular><version>2027</version><chapter><name>unit</name><section id="unit"><diag><name>R10.13</name><desc>Epigastric pain</desc></diag><diag><name>R14.0</name><desc>Abdominal distension (gaseous)</desc></diag></section></chapter></ICD10CM.tabular>',rows)
        CodingRelease.objects.create(release=release,index=parsed['index'],tabular=parsed['tabular'],digest=reference_digest(parsed))
        CodingContext.objects.create(encounter=self.e,data={'setting':'outpatient_office','patient_status':'established','em_basis':'time'},updated_by=self.user)
        inputs,context,releases,key=coding_service.input_snapshot(self.e)
        self.run_source=CodingRun(encounter=self.e,user=self.user,input_digest=key,inputs=inputs,context=context,releases=releases,
            config={'provider':'corti','mode':'live'},state='needs_detail',result={'offline':True},actual_cost=Decimal('0'))
        from core.tests.test_coding_output_live import controlled_receipt,bind_request
        receipt,_=controlled_receipt(self.e.notes)
        body=(FIXTURE.parent/'rowan_corti_live_response.json').read_bytes().decode()
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),'205c8e586139407bf959d4f69420a41e0ebe1b50e972242f72d18e4e9cd12d86')
        receipt['raw_response']['body']=body;receipt['response_sha256']=hashlib.sha256(body.encode()).hexdigest()
        self.run_source.requests=[receipt];bind_request(self.run_source)
        self.run_source.result=corti_coding.retained_result(self.run_source,corti_prediction.payload(self.run_source),
            json.loads(body),receipt['response_sha256'])
        self.run_source.save()
        admitted=override_settings(SEMANTIC_REVALIDATION_ORIGIN_JOB_IDS=(str(self.parent.pk),));admitted.enable();self.addCleanup(admitted.disable)
        # The reviewed-definition boundary is separately tested. Here the real
        # retained Rowan definitions isolate recovery/storage/receipt behavior.
        definitions=patch('core.word_contract.require_generation',return_value=self.data['definitions']);definitions.start();self.addCleanup(definitions.stop)

    def request(self):
        offered=recovery.offer(self.e,self.user)
        self.assertTrue(offered['available'],offered)
        job=recovery.enqueue(self.e,self.user,offered['display_token'],self.e.revision)
        return offered,job

    def execute(self,job,output=None,unknown=False,real_derivative=False):
        job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
        real=ai_stages.execute_stage
        def one(**kwargs):
            p,_=recovery._bound_proposal(job)
            if unknown:raise ai_stages.StageNotSent('Offline before-send refusal.')
            return real(**kwargs,fixture_output=output or passing(p))
        # The coding derivative's own evidence binding has a separate suite;
        # no prediction transport may be reached by this lifecycle fixture.
        with patch.object(ai_stages,'execute_stage',side_effect=one) as send,(nullcontext() if real_derivative else patch('core.coding_recovery.derive',return_value=SimpleNamespace(pk='offline-derived'))) as derive:
            recovery.run(job)
        job.refresh_from_db();self.e.refresh_from_db()
        return send,derive

    def test_one_new_checker_adopts_without_manual_edit_or_changing_original(self):
        offered,job=self.request();send,derive=self.execute(job)
        self.assertEqual(job.state,'succeeded',job.error);self.assertEqual(send.call_count,1);derive.assert_called_once()
        self.assertEqual(job.ai_stage_receipts.count(),1);self.assertEqual(self.parent.ai_stage_receipts.count(),5)
        self.assertEqual(Counter(a['status'] for a in self.e.answers.values()),{'supported':12,'missing':2})
        self.assertFalse(any(a.get('semantic_review_mode')=='manual' or a.get('reviewed') for a in self.e.answers.values()))
        self.assertEqual(self.e.template_review,{})
        self.assertTrue(recovery.validate_completed(job,self.e.answers))
        self.assertEqual(recovery._read(self.parent.result_path,self.parent.result_sha256)['answers'],self.original)
        self.assertEqual(Usage.objects.get(job=job).actual_cost,0)
        again=recovery.enqueue(self.e,self.user,offered['display_token'],self.e.revision)
        self.assertEqual(again.pk,job.pk);self.assertTrue(again.reused)
        self.assertEqual(job.ai_stage_receipts.count(),1)

    def test_checker_hold_preserves_original_and_cannot_be_resubmitted(self):
        offered,job=self.request();send,derive=self.execute(job,self.data['repair_checker'])
        self.assertEqual(job.state,'failed');derive.assert_not_called()
        self.assertEqual(self.e.answers,self.original);self.assertTrue(job.result_path)
        self.assertEqual(recovery.enqueue(self.e,self.user,offered['display_token'],0).pk,job.pk)
        self.assertEqual(job.ai_stage_receipts.count(),1)

    def test_stale_or_saved_manual_edit_refuses_before_stage(self):
        offered,job=self.request()
        changed=deepcopy(self.e.answers);changed['cell_0']['text']='Edited after request';self.e.answers=changed;self.e.save()
        with patch.object(ai_stages,'execute_stage') as send:recovery.run(job)
        send.assert_not_called();job.refresh_from_db();self.e.refresh_from_db()
        self.assertEqual(job.state,'failed');self.assertEqual(self.e.answers,changed)
        self.assertEqual(recovery.enqueue(self.e,self.user,offered['display_token'],0).pk,job.pk)

    def test_db_guard_rejects_a_second_checker_and_extractor_for_recovery(self):
        offered,job=self.request();self.execute(job)
        row=job.ai_stage_receipts.get();job.state='running';job.save(update_fields=['state'])
        for stage in (recovery.STAGE,'extractor'):
            with self.assertRaises(DatabaseError),transaction.atomic():
                AIStageReceipt.objects.create(job=job,stage=stage,attempt=1,config=job.config,
                    request_path='receipts/'+'c'*48+'.json',request_sha256='c'*64,
                    provider=job.config['provider'],requested_model=job.config['model'],quote_maximum=0,simulated=True)

    def test_corrupt_corti_receipt_refuses_before_quote_or_new_checker(self):
        self.run_source.requests[0]['response_sha256']='0'*64
        before=Job.objects.count()
        with patch.object(ai_stages,'execute_stage') as send,patch.object(CodingRun.objects,'get',return_value=self.run_source):
            offered=recovery.offer(self.e,self.user)
        self.assertFalse(offered['available']);self.assertEqual(Job.objects.count(),before);send.assert_not_called()

    def test_released_active_key_does_not_restore_consumed_recovery(self):
        offered,job=self.request();self.execute(job,self.data['repair_checker'])
        job.request_key='failed:'+str(job.pk);job.save(update_fields=['request_key'])
        again=recovery.enqueue(self.e,self.user,offered['display_token'],0)
        self.assertEqual(again.pk,job.pk);self.assertTrue(again.reused)
        self.assertEqual(Job.objects.filter(config__semantic_revalidation_contract=recovery.CONTRACT).count(),1)

    def test_wrong_actor_or_stale_revision_token_cannot_create_request(self):
        offered=recovery.offer(self.e,self.user)
        self.e.revision=1;self.e.save(update_fields=['revision'])
        with self.assertRaises(ValidationError):recovery.enqueue(self.e,self.user,offered['display_token'],0)
        self.assertFalse(Job.objects.filter(config__semantic_revalidation_contract=recovery.CONTRACT).exists())

    def test_actual_retained_corti_response_derives_with_zero_new_coding_operations(self):
        from core import coding_recovery,coding_output
        from core.tests.test_coding_output_live import BUNDLE
        original_requests=deepcopy(self.run_source.requests);original_result=deepcopy(self.run_source.result)
        offered,job=self.request()
        with patch.object(corti_prediction,'execute') as coding_send:
            self.execute(job,real_derivative=True)
        coding_send.assert_not_called()
        self.assertEqual(job.state,'succeeded',job.error)
        derived=CodingRun.objects.filter(encounter=self.e,config__mode='retained_live').get()
        self.assertEqual(derived.requests,[]);self.assertEqual(derived.actual_cost,0)
        self.assertEqual(coding_recovery.source_for(derived).pk,self.run_source.pk)
        self.run_source.refresh_from_db()
        self.assertEqual(self.run_source.requests,original_requests);self.assertEqual(self.run_source.result,original_result)
        # Isolated synthetic finalization state for the output boundary; no user approval is claimed.
        self.e.status='finalized';self.e.save(update_fields=['status'])
        raw=BUNDLE.read_bytes()
        with override_settings(CORTI_OUTPUT_REFERENCE_FILE=str(BUNDLE),CORTI_OUTPUT_REFERENCE_SHA256=hashlib.sha256(raw).hexdigest()):
            assessment=coding_output.live_assessment(self.e,derived)
        self.assertEqual(assessment['selection']['code'],'99213')
        self.assertEqual(assessment['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertFalse(next(r for r in derived.result['suggestions'] if r['code']=='99213')['eligible'])
        self.assertTrue(all(not r['eligible'] for r in derived.result['suggestions'] if r['code'] in ('G8752','G8754')))

    def test_nonclinician_cannot_offer_or_submit_another_actors_check(self):
        offered=recovery.offer(self.e,self.user)
        manager=User.objects.create_user(username='offline-manager',email='offline-manager@synthetic.invalid',verified_at=timezone.now())
        Membership.objects.create(user=manager,department=self.e.department,role='manager')
        self.assertFalse(recovery.offer(self.e,manager)['available'])
        with self.assertRaises(PermissionDenied):recovery.enqueue(self.e,manager,offered['display_token'],0)
        self.assertFalse(Job.objects.filter(config__semantic_revalidation_contract=recovery.CONTRACT).exists())
