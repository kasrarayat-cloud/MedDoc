"""Independent provider-stage storage/accounting; every transport is an offline fixture."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import DatabaseError,transaction
from django.test import TestCase,override_settings
from django.utils import timezone
from core import ai_stages,generation,semantic_generation,semantic_preparation
from core.billing import welcome_credit
from core.jobs import enqueue,run_one
from core.models import AIStageReceipt,Encounter,Patient,ProviderReceipt,Usage,Reservation,PlatformCost
from core.security import private_path
from core.tests import test_semantic_preparation as preparation_fixture
from core.tests.test_semantic_generation import NOTES,alex_case,declared_api_facts,checker


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',ADMIN_SITE=False,
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class IndependentStageTests(TestCase):
    def setUp(self):
        preparation_fixture.DefinitionPreparationDatabaseTests.setUp(self)
        welcome_credit(self.user)
        prep=semantic_preparation.create_preparation(self.source,self.user)
        self.assertTrue(semantic_preparation.run_one());prep.refresh_from_db()
        self.assertEqual(prep.state,'review',prep.error_code)
        definitions=semantic_preparation.corrected_definitions(prep)
        _,wanted,_,_=alex_case()
        for field, desired in zip(self.source.fields,wanted.values()):
            definitions[field['key']]['meaning']=desired['meaning']
            definitions[field['key']]['scope']=desired['scope']
        prep=semantic_preparation.correct(prep.pk,self.user,0,definitions,list(definitions),'Compared every original question and its exact destination.')
        self.version=semantic_preparation.approve(prep.pk,self.user,prep.revision,prep.inventory['inventory_sha256'],[f['key'] for f in self.source.fields],True)
        patient=Patient.objects.create(department=self.department,display_name='Synthetic Alex',reference='synthetic',created_by=self.user)
        self.encounter=Encounter.objects.create(department=self.department,patient=patient,template_version=self.version,
            created_by=self.user,service_date=timezone.localdate(),notes=NOTES)

    def live_config(self):
        return {**generation.configuration(),'mode':'live','model':'synthetic-model','input_rate':'1','cached_rate':'0.1','output_rate':'1'}

    def provider(self,failure=None,scripted=False):
        count=0
        def respond(payload,schema,instructions,config,maximum,timeout,on_response):
            nonlocal count
            count+=1
            if failure=='unknown' and count==2:raise TimeoutError('offline fixture')
            role='extractor' if 'source_units' in payload and 'facts' not in payload else 'assigner' if 'extracted_facts' in payload else 'checker'
            # Workflow payloads are retained independently; use the explicit role from schema shape.
            props=schema['properties']
            role='extractor' if 'facts' in props else 'checker' if 'fact_findings' in props else 'assigner'
            parsed=__import__('core.semantic_generation',fromlist=['fixture_stage']).fixture_stage(role,payload)
            if scripted:
                _,_,facts,assigned=alex_case()
                key_map={old['key']:new['key'] for old,new in zip(alex_case()[0],self.version.fields)}
                assigned['fields']=[{**row,'key':key_map[row['key']]} for row in assigned['fields']]
                parsed=declared_api_facts(NOTES,payload['source_units'],facts,
                    payload.get('reference_contract',semantic_generation.LEGACY_REFERENCE_CONTRACT)) if role=='extractor' else assigned if role=='assigner' else checker(assigned)
            response=SimpleNamespace(id='msg_stage_'+str(count),_request_id='req_stage_'+str(count),model='synthetic-model',
                model_dump=lambda **kw:{'id':'msg_stage_'+str(count),'output':parsed,'usage':{'input_tokens':10,'output_tokens':0}})
            if failure=='duplicate':response.id='msg_replayed';response._request_id='req_replayed'
            on_response(response)
            if failure=='meter' and count==2:raise AttributeError('offline malformed meter')
            text='invalid json' if failure=='known' and count==2 else json.dumps(parsed)
            rates=generation.cost_rates(generation.rates(config),Decimal('0.00001'),Decimal('0'))
            return response,Decimal('0.00001'),{'input_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0,'output_tokens':0},rates,text,True
        return respond

    def test_three_independent_stages_aggregate_once_and_replay_is_observation(self):
        job=enqueue(self.encounter,self.user,config=self.live_config())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider()) as provider:
            self.assertTrue(run_one());self.assertFalse(run_one())
        job.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(job.state,'succeeded',job.error);self.assertEqual(provider.call_count,3)
        self.assertEqual(job.ai_stage_receipts.count(),3);self.assertEqual(Usage.objects.get(job=job).actual_cost,Decimal('0.00003'))
        self.assertEqual(ProviderReceipt.objects.get(job=job).provider_request_id,'')
        self.assertTrue(all(a['status']=='missing' and a['text']=='' for a in self.encounter.answers.values()))
        self.assertEqual(enqueue(self.encounter,self.user,config=self.live_config()).pk,job.pk)
        self.assert_audit()
        for receipt in job.ai_stage_receipts.all():
            self.assertEqual(hashlib.sha256(private_path(receipt.result_path).read_bytes()).hexdigest(),receipt.result_sha256)
            with self.assertRaises(DatabaseError),transaction.atomic():AIStageReceipt.objects.filter(pk=receipt.pk).update(actual_cost=99)

    def test_later_known_invalid_response_retains_both_costs_and_is_absorbed(self):
        job=enqueue(self.encounter,self.user,config=self.live_config())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider('known')):run_one()
        job.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(job.state,'failed',job.error);self.assertEqual(job.ai_stage_receipts.count(),2)
        self.assertEqual(Usage.objects.get(job=job).actual_cost,Decimal('0.00002'))
        self.assertEqual(PlatformCost.objects.get(job=job,kind='absorbed_failure').amount,Decimal('0.00002'))
        self.assertEqual(self.encounter.answers,{})
        self.assert_audit()
        self.assertEqual(list(job.ai_stage_receipts.order_by('created_at').values_list('state',flat=True)),['succeeded','failed'])

    def test_later_unknown_send_keeps_earlier_cost_and_hold_without_aggregate(self):
        job=enqueue(self.encounter,self.user,config=self.live_config())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider('unknown')):run_one()
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation',job.error)
        rows=list(job.ai_stage_receipts.order_by('created_at'));self.assertEqual(rows[0].actual_cost,Decimal('0.00001'))
        self.assertEqual(rows[1].state,'unknown');self.assertIsNone(rows[1].actual_cost)
        self.assertFalse(Usage.objects.filter(job=job).exists());self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertTrue(Reservation.objects.filter(job=job,state='held').exists());self.assertFalse(run_one())
        report=self.assert_audit()
        self.assertEqual([str(row['id']) for row in report['unresolved_jobs']],[str(job.pk)])
        self.assertEqual(report['rows'],[])

    def test_generated_missing_review_and_manual_decision_are_distinct(self):
        job=enqueue(self.encounter,self.user);run_one();self.encounter.refresh_from_db()
        self.client.force_login(self.user)
        post={'revision':self.encounter.revision}
        for field in self.version.fields:post['answer_'+field['key']]='';post['reviewed_'+field['key']]='on'
        response=self.client.post(f'/encounters/{self.encounter.pk}/save/',post)
        self.assertEqual(response.status_code,302);self.encounter.refresh_from_db()
        self.assertTrue(all(a['status']=='missing' and a.get('semantic_review_mode')!='manual' for a in self.encounter.answers.values()))
        first=self.version.fields[0]['key'];post['revision']=self.encounter.revision;post['answer_'+first]='Alex Morgan'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',post).status_code,302)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers[first]['semantic_review_mode'],'manual')
        self.assertEqual(len(self.encounter.answers[first]['semantic_edit_history']),1)

    def test_concealed_invalid_generated_text_cannot_be_silently_cleared(self):
        from core.semantic_review import displayed_answer,save_answer
        from core.semantic_generation import CONTRACT,definition_digest
        field=self.version.fields[0];definition=self.version.semantic_definitions[field['key']]
        previous={'text':'Alex Morgan','status':'supported','evidence':[],'facts':[], 'fact_ids':[], 'separator':'; ',
            'evidence_contract':CONTRACT,'source_sha256':hashlib.sha256(NOTES.encode()).hexdigest(),
            'definition_sha256':definition_digest(definition),'semantic_proof_sha256':'corrupt'}
        shown=displayed_answer(self.encounter,field,previous,self.version.semantic_definitions)
        self.assertEqual(shown['text'],'');self.assertEqual(shown['status'],'conflict')
        with self.assertRaises(ValidationError):save_answer(self.encounter,field,previous,'',self.user,True,False,1,self.version.semantic_definitions)
        blank=save_answer(self.encounter,field,previous,'',self.user,True,True,1,self.version.semantic_definitions)
        self.assertEqual(blank['status'],'left_blank');self.assertEqual(blank['semantic_edit_history'][0]['previous'],previous)

    def assert_audit(self):
        from core.management.commands.audit_billing import audit_report
        from django.db import connection
        from ops.backup_restore import invariant_counts
        report=audit_report();self.assertTrue(report['all_checks_pass'],report)
        def query(sql):
            with connection.cursor() as cursor:cursor.execute(sql);return cursor.fetchall()
        self.assertTrue(all(value==0 for value in invariant_counts(query).values()))
        return report

    def test_raw_response_identifiers_survive_malformed_usage_and_identity_replay(self):
        for failure in ('meter','duplicate'):
            with self.subTest(failure=failure):
                e=Encounter.objects.create(department=self.encounter.department,patient=self.encounter.patient,
                    template_version=self.version,created_by=self.user,service_date=self.encounter.service_date,notes=NOTES)
                job=enqueue(e,self.user,config=self.live_config())
                with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider(failure)):
                    run_one()
                job.refresh_from_db();self.assertEqual(job.state,'reconciliation',job.error)
                second=list(job.ai_stage_receipts.order_by('created_at'))[1]
                self.assertEqual(second.state,'unknown');self.assertTrue(second.result_path)
                raw=json.loads(private_path(second.result_path).read_text())
                self.assertTrue(raw['provider_request_id']);self.assertTrue(raw['provider_resource_id'])
                if failure=='meter':
                    self.assertEqual(second.provider_request_id,'req_stage_2')
                    self.assertEqual(second.provider_resource_id,'msg_stage_2')
                self.assertFalse(Usage.objects.filter(job=job).exists())

    def test_scripted_narrative_reaches_concise_review_finalization_and_word_download(self):
        original=private_path(self.template.original_path).read_bytes()
        job=enqueue(self.encounter,self.user,config=self.live_config())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider(scripted=True)):run_one()
        job.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(job.state,'succeeded',job.error)
        self.assertEqual([a['text'] for a in self.encounter.answers.values()][4],'3')
        self.assertNotIn('came in because',self.encounter.answers[self.version.fields[0]['key']]['text'])
        self.assert_audit();self.client.force_login(self.user)
        response=self.client.get(f'/encounters/{self.encounter.pk}/status/')
        self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['latest_job']['stages']),3)
        post={'revision':self.encounter.revision}
        for field in self.version.fields:
            post['answer_'+field['key']]=self.encounter.answers[field['key']]['text'];post['reviewed_'+field['key']]='on'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',post).status_code,302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/finalize/',{'revision':self.encounter.revision,'reviewed':'on'}).status_code,302)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.status,'finalized')
        download=self.client.get(f'/encounters/{self.encounter.pk}/export/')
        self.assertEqual(download.status_code,200);data=b''.join(download.streaming_content)
        from docx import Document
        from io import BytesIO
        result=Document(BytesIO(data));text='\n'.join(c.text for t in result.tables for row in t.rows for c in row.cells)
        self.assertIn('Synthetic Alex Morgan',text);self.assertIn('Pain score0 to 10',text);self.assertIn('in one week',text)
        self.assertEqual(private_path(self.template.original_path).read_bytes(),original)

    def test_sponsored_stage_total_keeps_user_charge_zero_and_backup_accepts_exact_chain(self):
        from core.models import User,Department,Membership,Template,TemplateVersion,LedgerEntry,TestingReservation
        from core import testing_authority
        from django.db import connection
        from ops.backup_restore import _SEMANTIC_STANDING_USAGE_INVARIANT
        with override_settings(AI_PROVIDER='anthropic',AI_MODEL='synthetic-model',AI_INPUT_RATE='1',AI_OUTPUT_RATE='1',AI_CACHED_RATE='0.1',TESTING_AUTHORITY_MODE=testing_authority.MODE,TESTING_AUTHORITY_ID=testing_authority.AUTHORITY_ID,
                               TESTING_AUTHORITY_SHA256=testing_authority.AUTHORITY_SHA256):
            actor=User.objects.create_user(pk=testing_authority.ENROLLED_ACTOR,username='standing-stage-doctor',email='standing-stage@synthetic.invalid',verified_at=timezone.now())
            department=Department.objects.create(pk=testing_authority.ACTORS[testing_authority.ENROLLED_ACTOR],organization=self.org,name='Synthetic standing stage clinic')
            Membership.objects.create(user=actor,department=department,role='clinician')
            template=Template.objects.create(department=department,name='Standing synthetic blank',format='docx',original_name='blank.docx',
                original_path=self.template.original_path,sha256=self.template.sha256,created_by=actor)
            source=TemplateVersion.objects.create(template=template,number=1,fields=self.source.fields,created_by=actor)
            prep=semantic_preparation.create_preparation(source,actor);semantic_preparation.run_one();prep.refresh_from_db()
            self.assertEqual(prep.state,'review',prep.error_code)
            version=semantic_preparation.approve(prep.pk,actor,prep.revision,prep.inventory['inventory_sha256'],[f['key'] for f in source.fields],True)
            patient=Patient.objects.create(department=department,display_name='Synthetic standing patient',reference='standing',created_by=actor)
            e=Encounter.objects.create(department=department,patient=patient,template_version=version,created_by=actor,service_date=timezone.localdate(),notes=NOTES)
            job=enqueue(e,actor,config=self.live_config())
            with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),patch.object(ai_stages,'_response',side_effect=self.provider()):run_one()
            job.refresh_from_db();self.assertEqual(job.state,'succeeded',job.error)
            usage=Usage.objects.get(job=job);self.assertEqual(usage.charged_cost,0);self.assertEqual(usage.actual_cost,Decimal('0.00003'))
            self.assertFalse(LedgerEntry.objects.filter(job=job).exists());self.assertFalse(Reservation.objects.filter(job=job).exists())
            self.assertEqual(TestingReservation.objects.get(job=job).state,'settled');self.assert_audit()
            # A read-only CTE presents a tampered snapshot to the actual backup
            # predicate; neither immutable receipt nor any historical row changes.
            for key,value in [('provider','anthropic:synthetic-model'),('units',{'protocol':ai_stages.PROTOCOL,'stages':[]})]:
                override=json.dumps({key:value})
                sql='WITH core_usage AS (SELECT (jsonb_populate_record(NULL::public.core_usage,to_jsonb(original)||%s::jsonb)).* FROM public.core_usage original) '+_SEMANTIC_STANDING_USAGE_INVARIANT.replace('%','%%')
                with connection.cursor() as cursor:cursor.execute(sql,[override]);self.assertEqual(cursor.fetchone()[0],1)
