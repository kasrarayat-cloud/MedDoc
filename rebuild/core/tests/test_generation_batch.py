"""Finite batch proofs. Every provider response is simulated; no clinical/model qualification."""
import copy
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from unittest import expectedFailure
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import generation as g, generation_batch as b, batch_jobs as jobs
from core.models import (TemplateVersion, Encounter, Job, Reservation, Usage, ProviderReceipt,
    GenerationBatch, GenerationBatchPart, GenerationBatchEvent, GenerationBatchResponse, Wallet)
from core.security import private_path
from .test_v3_ordinary_notes import LIVE, field
from .test_word_v3_workflow import V3Fixture, build_questionnaire, part_text

SETTINGS = dict(LIVE, V3_GENERATION_BATCHES=True, V3_HISTORY_CONTEXT=False)


def manifest(fields, source='a'*64, *, synthetic=False):
    return {'contract':b.CONSTRAINTS,'source_sha256':source,'fields_sha256':b.digest(fields),
        'coverage':'complete','provenance':'synthetic_fixture' if synthetic else 'reviewed_assisted',
        'evidence_sha256':'1'*64,'instruction_references':[],'rules':[]}


def sample(count=101, notes=None):
    fields=[field(f'q{i:03d}',f'Question {i:03d}') for i in range(count)]
    for i,f in enumerate(fields):f['locator']['slot']=f'b/tbl[0]/tr[{i}]/tc[1]/p[0]'
    version=SimpleNamespace(pk=uuid.uuid4(),contract='v3',fields=fields,review_requirements=[],
        template=SimpleNamespace(sha256='a'*64),generation_constraints=manifest(fields))
    return SimpleNamespace(pk=uuid.uuid4(),revision=0,template_version=version,
        notes=notes or '\n'.join(f'Question {i:03d}: documented {i:03d}.' for i in range(count)))


def response(plan, ordinal, *, selections=None, model=g.SONNET_5, stop='end_turn'):
    wanted=plan['parts'][ordinal-1]['field_ids']
    unit_by_label={g.tab_source_value(u['quote'],g.recognized_labels(plan['asked'],plan['context_labels']))[0]:u['id']
                   for u in plan['units'] if g.tab_source_value(u['quote'],g.recognized_labels(plan['asked'],plan['context_labels']))}
    labels={f['key']:g.question_key(f['label']) for f in plan['asked']}
    body={'fields':[{'key':k,'unit_ids':(selections or {}).get(k,[unit_by_label[labels[k]]] if labels[k] in unit_by_label else []),
                     'conflict':False} for k in wanted]}
    return {'id':'msg_'+str(uuid.uuid4()),'model':model,'stop_reason':stop,
            'content':[{'type':'text','text':json.dumps(body)}],
            'usage':{'input_tokens':100,'output_tokens':100,'cache_read_input_tokens':0,'cache_creation_input_tokens':0}}


@override_settings(**SETTINGS)
class BatchContract(SimpleTestCase):
    def test_request_hash_survives_database_json_key_order(self):
        plan=b.plan_for(sample(),g.configuration())
        stored=json.loads(json.dumps(plan,sort_keys=True))
        self.assertEqual(b.digest(b.request(stored,1)),plan['parts'][0]['request_sha256'])

    def test_old_single_request_limit_and_bounded_complete_plan(self):
        for count, sizes in ((99,[99]),(100,[100]),(101,[100,1]),(198,[100,98]),(559,[100,100,100,100,100,59])):
            e=sample(count)
            plan=b.plan_for(e,g.configuration())
            self.assertEqual([len(p['field_ids']) for p in plan['parts']],sizes)
            if count>100:
                with self.assertRaisesMessage(ValidationError,'supported limits'):g.maximum_cost(e.notes,e.template_version.fields)
            for ordinal, part in enumerate(plan['parts'],1):
                wire=b.request(plan,ordinal);payload=json.loads(wire['messages'][0]['content'])
                self.assertEqual(payload['source_units'],plan['units'])
                self.assertEqual(payload['full_catalogue'],e.template_version.fields)
                self.assertEqual(payload['requested_field_ids'],part['field_ids'])
                self.assertEqual(b.digest(wire),part['request_sha256'])
            self.assertEqual(Decimal(plan['maximum_charge']),sum(Decimal(p['maximum_charge']) for p in plan['parts']))
        with self.assertRaisesMessage(ValidationError,'eight'):b.plan_for(sample(801),g.configuration())

    def test_group_and_unknown_rule_admission_are_not_silent_splits(self):
        e=sample()
        for f in e.template_version.fields:f['locator']['slot']='b/tbl[0]/tr[0]/tc[1]/p[0]'
        e.template_version.generation_constraints=manifest(e.template_version.fields)
        with self.assertRaisesMessage(ValidationError,'indivisible'):b.plan_for(e,g.configuration())
        e=sample();e.template_version.generation_constraints=None
        with self.assertRaisesMessage(ValidationError,'rules have not'):b.plan_for(e,g.configuration())
        with override_settings(V3_GENERATION_BATCHES=False):
            with self.assertRaisesMessage(ValidationError,'disabled'):b.plan_for(sample(),g.configuration())
        with override_settings(AI_MODEL='claude-sonnet-4-6'):
            with self.assertRaisesMessage(ValidationError,'exact native'):b.plan_for(sample(),g.configuration())

    def test_exact_subset_union_and_actual_model_are_required(self):
        plan=b.plan_for(sample(),g.configuration());raw=response(plan,1)
        b.parse_part(plan,1,raw)
        for mutate in (lambda v:v['fields'].pop(),lambda v:v['fields'].append(v['fields'][0]),
                       lambda v:v['fields'][0].update(key='foreign'),lambda v:v['fields'][0].update(unit_ids=[9999])):
            changed=copy.deepcopy(raw);body=json.loads(changed['content'][0]['text']);mutate(body)
            changed['content'][0]['text']=json.dumps(body)
            with self.assertRaises(ValidationError):b.parse_part(plan,1,changed)
        for key,value in (('model','claude-sonnet-4-6'),('stop_reason','max_tokens')):
            changed={**raw,key:value}
            with self.assertRaises(ValidationError):b.parse_part(plan,1,changed)
        with self.assertRaises(ValidationError):b.assemble(plan,[raw])
        answers,_=b.assemble(plan,[raw,response(plan,2)])
        self.assertEqual(len(answers),101)
        self.assertTrue(all(a['status']=='supported' for a in answers.values()))

    def test_cross_part_repeated_questions_and_global_rules_keep_full_scope(self):
        e=sample();fs=e.template_version.fields
        fs[0]['label']=fs[-1]['label']='Pain'
        e.notes='Pain: yes.';e.template_version.generation_constraints=manifest(fs)
        plan=b.plan_for(e,g.configuration())
        answers,_=b.assemble(plan,[response(plan,1),response(plan,2)])
        for f in (fs[0],fs[-1]):self.assertNotEqual(answers[f['key']]['status'],'supported')
        e=sample();m=e.template_version.generation_constraints
        m['instruction_references']=[{'id':'rule','part':'word/document.xml','slot':'b/p[0]','sha256':'2'*64}]
        m['rules']=[{'kind':'max_active_groups','source_id':'rule','maximum':1,
                     'groups':[[{'key':'q000','values':['documented 000.']}],[{'key':'q100','values':['documented 100.']}]]}]
        plan=b.plan_for(e,g.configuration())
        with self.assertRaisesMessage(ValidationError,'maximum selection'):b.assemble(plan,[response(plan,1),response(plan,2)])

    def test_unique_priorities_and_full_source_guards_cannot_be_split_away(self):
        e=sample();m=e.template_version.generation_constraints
        m['instruction_references']=[{'id':'rule','part':'word/document.xml','slot':'b/p[0]','sha256':'2'*64}]
        m['rules']=[{'kind':'unique_values','source_id':'rule','keys':['q000','q100'],'allowed_values':['1','2','3']}]
        b.constraints(e.template_version)
        with self.assertRaisesMessage(ValidationError,'priority'):b.validate_constraints(m,{'q000':{'text':'1'},'q100':{'text':'1'}})
        b.validate_constraints(m,{'q000':{'text':'1'},'q100':{'text':'2'}})
        for notes,label in (('Family history:\nQuestion 000: documented finding.','Question 000'),
                ('Consent obtained: yes.\nConsent was withdrawn.','Consent obtained')):
            with self.subTest(notes=notes):
                e=sample(notes=notes);e.template_version.fields[0]['label']=label
                e.template_version.generation_constraints=manifest(e.template_version.fields)
                plan=b.plan_for(e,g.configuration());selected={'q000':[plan['units'][-1 if label=='Question 000' else 0]['id']]}
                answers,_=b.assemble(plan,[response(plan,1,selections=selected),response(plan,2)])
                self.assertNotEqual(answers['q000']['status'],'supported')

    @expectedFailure
    def test_known_existing_single_field_side_gap_is_not_clinical_acceptance(self):
        # Preserved failed acceptance: unchanged single-field validator accepts
        # this too (runtime11). Batching does not establish clinical relevance.
        # Keep default-off; this blocker needs a separately reviewed source fix.
        e=sample(notes='The patient has left knee pain.')
        e.template_version.fields[0]['label']='Right knee'
        e.template_version.generation_constraints=manifest(e.template_version.fields)
        plan=b.plan_for(e,g.configuration())
        answers,_=b.assemble(plan,[response(plan,1,selections={'q000':[1]}),response(plan,2)])
        self.assertNotEqual(answers['q000']['status'],'supported')

    def test_signing_fields_stay_visible_in_catalogue_and_are_never_requested(self):
        e=sample(102);e.template_version.fields[-1]['kind']='signature'
        e.template_version.generation_constraints=manifest(e.template_version.fields)
        plan=b.plan_for(e,g.configuration())
        self.assertEqual(len(plan['fields']),102);self.assertEqual(sum(len(p['field_ids']) for p in plan['parts']),101)
        answers,_=b.assemble(plan,[response(plan,1),response(plan,2)])
        self.assertEqual(len(answers),102);self.assertEqual(answers['q101']['text'],'')

    def test_actual_compiled_requests_are_fully_covered_by_aggregate_charge(self):
        for geo in ('','us'):
            with override_settings(AI_INFERENCE_GEO=geo):
                config=g.configuration();plan=b.plan_for(sample(),config);rate=g.rates(config)
                total=Decimal(0)
                for ordinal,part in enumerate(plan['parts'],1):
                    wire=b.request(plan,ordinal);size=len(json.dumps(wire).encode())
                    self.assertEqual(part['input_token_bound'],size+12000)
                    self.assertEqual(wire['model'],g.SONNET_5)
                    exact=(Decimal(size+12000)*rate['input_per_million']+Decimal(wire['max_tokens'])*rate['output_per_million'])/1000000
                    if geo=='us':exact*=g.US_INFERENCE_MULTIPLIER
                    self.assertGreaterEqual(Decimal(part['maximum_cost']),exact)
                    self.assertEqual(Decimal(part['maximum_charge']),Decimal(part['maximum_cost'])*Decimal('1.5'))
                    total+=Decimal(part['maximum_charge'])
                self.assertEqual(total,Decimal(plan['maximum_charge']))


class BatchFixture(V3Fixture):
    def setUp(self):
        super().setUp()
        deny=patch('socket.socket.connect',side_effect=AssertionError('Network denied'));deny.start();self.addCleanup(deny.stop)
        self.template,first=self.uploaded(data=build_questionnaire(101),name='Synthetic large batch')
        self.version=TemplateVersion.objects.create(template=self.template,number=2,fields=first.fields,contract='v3',
            generation_constraints=manifest(first.fields,self.template.sha256),created_by=self.user)
        self.confirm(self.template,self.version)
        self.notes='\n'.join(f"{f['label']}: documented {i:03d}." for i,f in enumerate(self.version.fields))
        self.new_encounter(self.version,self.notes)
        self.encounter=Encounter.objects.latest('created_at')

    def admit(self):
        page=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertIsNotNone(page.context['generation_max_charge'])
        result=self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'revision':self.encounter.revision,'usage_quote':page.context['usage_quote']})
        self.assertEqual(result.status_code,302)
        return GenerationBatch.objects.get(encounter=self.encounter)

    def fake(self,batch,fail_at=0):
        calls=[]
        def call(**kw):
            calls.append(kw)
            # All reservation rows exist before even the first mocked send.
            self.assertEqual(batch.parts.count(),2)
            if len(calls)==fail_at:raise TimeoutError('synthetic uncertain middle request')
            raw=response(batch.plan,len(calls))
            obj=SimpleNamespace(**{k:v for k,v in raw.items() if k not in ('content','usage')},
                content=[SimpleNamespace(**c) for c in raw['content']],usage=SimpleNamespace(**raw['usage']),
                _request_id='request_'+str(uuid.uuid4()))
            obj.model_dump=lambda **_kw:raw
            return obj
        return calls,call


@override_settings(**SETTINGS)
class BatchWorkflow(BatchFixture,TestCase):
    def test_authenticated_whole_form_workflow_has_no_partial_adoption(self):
        batch=self.admit();calls,call=self.fake(batch)
        initial=Reservation.objects.filter(job__generation_part__batch=batch,state='held')
        self.assertEqual(sum(initial.values_list('amount',flat=True),Decimal(0)),batch.maximum_charge)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            self.assertTrue(jobs.run_one());self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
            self.assertTrue(jobs.pending(self.encounter))
            self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',{'revision':0}).status_code,409)
            self.assertTrue(jobs.run_one());self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
            from core.admin_console import processing_health,live_generation_queue_row
            self.assertEqual(processing_health()['verdict'],'Whole-form validation pending')
            self.assertIn('2 staged',live_generation_queue_row(True)['value'])
            self.assertEqual(live_generation_queue_row(False)['severity'],'warning')
            self.assertTrue(jobs.run_one());self.assertFalse(jobs.run_one())
            self.assertEqual(provider.return_value.messages.create.call_count,2)
        batch.refresh_from_db();self.assertEqual(batch.state,'succeeded',batch.error)
        self.encounter.refresh_from_db();self.assertEqual(len(self.encounter.answers),101)
        self.assertTrue(all(a['status']=='supported' for a in self.encounter.answers.values()))
        page=self.client.get(f'/encounters/{self.encounter.pk}/');self.assertEqual(len(page.context['jobs']),1)
        post={'revision':self.encounter.revision}
        for key,answer in self.encounter.answers.items():post['answer_'+key]=answer['text'];post['reviewed_'+key]='on'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',post).status_code,302)
        self.encounter.refresh_from_db()
        self.client.post(f'/encounters/{self.encounter.pk}/finalize/',{'revision':self.encounter.revision,'reviewed':'on'})
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.status,'finalized')
        download=self.client.get(f'/encounters/{self.encounter.pk}/export/');self.assertEqual(download.status_code,200)
        result=b''.join(download.streaming_content)
        self.assertEqual(hashlib.sha256(result).hexdigest(),self.encounter.export_sha256)
        for i in range(101):self.assertIn(f'documented {i:03d}.',part_text(result))
        self.assertEqual(Usage.objects.filter(job__generation_part__batch=batch).count(),2)
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())

    def test_interrupted_second_call_keeps_unknown_hold_and_never_retries(self):
        batch=self.admit();calls,call=self.fake(batch,fail_at=2)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            self.assertTrue(jobs.run_one());self.assertTrue(jobs.run_one())
            self.assertFalse(jobs.run_one());self.assertFalse(jobs.run_one())
            self.assertEqual(len(calls),2)
        batch.refresh_from_db();self.assertEqual(batch.state,'reconciliation')
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
        self.assertTrue(Reservation.objects.filter(job__generation_part__batch=batch,job__generation_part__ordinal=2,state='held').exists())
        self.assertEqual(batch.events.filter(kind='send_intent').count(),2)
        self.assertEqual(batch.parts.get(ordinal=1).job.state,'failed')

    def test_insufficient_funds_rolls_back_all_children_and_duplicate_quote_is_one_admission(self):
        config,_=jobs.quote(self.encounter,g.configuration())
        original=jobs.reserve;held=[]
        def exhaust(job,**kwargs):
            if held:raise ValidationError('synthetic funds exhausted')
            original(job,**kwargs);held.append(job.pk)
            self.assertTrue(Reservation.objects.filter(job=job,state='held').exists())
        with patch('core.batch_jobs.reserve',side_effect=exhaust):
            with self.assertRaises(ValidationError):jobs.enqueue(self.encounter,self.user,config)
        self.assertFalse(GenerationBatch.objects.exists());self.assertFalse(Job.objects.exists());self.assertFalse(Reservation.objects.exists())
        first=jobs.enqueue(self.encounter,self.user,config);second=jobs.enqueue(self.encounter,self.user,config)
        self.assertEqual(first.pk,second.pk);self.assertTrue(second.reused);self.assertEqual(Job.objects.count(),2)

    def test_plan_and_attempt_records_are_immutable_in_database(self):
        batch=self.admit();part=batch.parts.first()
        for model,pk,change in ((GenerationBatch,batch.pk,{'plan':{}}),(GenerationBatchPart,part.pk,{'field_ids':[]}),
                                (Job,part.job_id,{'request_key':'replacement-attempt'})):
            with self.subTest(model=model.__name__),self.assertRaises(DatabaseError),transaction.atomic():
                model.objects.filter(pk=pk).update(**change)
        row=batch.events.get(kind='admitted')
        with self.assertRaises(DatabaseError),transaction.atomic():GenerationBatchEvent.objects.filter(pk=row.pk).delete()

    def test_missing_and_long_answers_use_authenticated_review_without_inventing_missing(self):
        fs=self.version.fields
        # The earlier unpunctuated repeated fragment was correctly held by the
        # unchanged run-on guard; its first result is retained in runtime05.
        long='The patient reports '+', '.join(['daily aching discomfort']*80)+'.'
        self.encounter.notes='\n'.join(f"{f['label']}: {long if i==2 else 'documented '+str(i)+'.'}" for i,f in enumerate(fs) if i!=0)
        self.encounter.save(update_fields=['notes']);batch=self.admit();calls,call=self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            for _ in range(3):self.assertTrue(jobs.run_one())
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers[fs[0]['key']]['status'],'missing')
        self.assertEqual(self.encounter.answers[fs[0]['key']]['text'],'')
        self.assertEqual(self.encounter.answers[fs[2]['key']]['text'],long)
        # Existing whole-note context correctly retains the preceding short
        # answer as a visible hold; record the clinician's explicit completion.
        preceding=self.encounter.answers[fs[1]['key']]
        self.assertEqual(preceding['status'],'conflict')
        self.assertEqual(preceding['held_candidate']['text'],'documented 1.')
        post={'revision':self.encounter.revision}
        for key,answer in self.encounter.answers.items():
            post['answer_'+key]=answer['text'];post['reviewed_'+key]='on'
            if not answer['text']:post['blank_'+key]='on'
        post['answer_'+fs[1]['key']]='documented 1.';post.pop('blank_'+fs[1]['key'])
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',post).status_code,302)
        self.encounter.refresh_from_db()
        self.client.post(f'/encounters/{self.encounter.pk}/finalize/',{'revision':self.encounter.revision,'reviewed':'on'})
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.status,'finalized')
        out=self.client.get(f'/encounters/{self.encounter.pk}/export/')
        self.assertEqual(out.status_code,200);text=part_text(b''.join(out.streaming_content))
        self.assertIn(long,text);self.assertIn('documented 1.',text);self.assertNotIn('documented 0.',text)
        self.assertEqual(len(calls),2)

    def test_all_recorded_interruption_requires_explicit_local_recovery_with_no_resend(self):
        batch=self.admit();calls,call=self.fake(batch);original=jobs.store_response
        def interrupt(batch,part,raw,receipt):
            original(batch,part,raw,receipt)
            if part.ordinal==2:raise SystemExit('synthetic worker exit after durable response')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            self.assertTrue(jobs.run_one())
            with patch('core.batch_jobs.store_response',side_effect=interrupt),self.assertRaises(SystemExit):jobs.run_one()
            self.assertEqual(len(calls),2)
            part=batch.parts.get(ordinal=2)
            Job.objects.filter(pk=part.job_id).update(started_at=timezone.now()-timedelta(minutes=6))
            jobs.mark_stale();batch.refresh_from_db();self.assertEqual(batch.state,'reconciliation')
            self.assertFalse(jobs.run_one());self.assertEqual(batch.parts.filter(response__isnull=False).count(),2)
            with self.assertRaisesMessage(Exception,'administrator'):jobs.recover_recorded(batch.pk,self.user)
            self.user.is_staff=True;self.user.save(update_fields=['is_staff'])
            self.assertTrue(jobs.recover_recorded(batch.pk,self.user));self.assertEqual(len(calls),2)
        batch.refresh_from_db();self.assertEqual(batch.state,'succeeded')
        self.assertEqual(Usage.objects.filter(job__generation_part__batch=batch).count(),2)
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())
        self.encounter.refresh_from_db();self.assertEqual(len(self.encounter.answers),101)

    def test_cancel_before_send_and_fresh_quote_after_success_never_duplicate_attempt(self):
        batch=self.admit();job=batch.parts.first().job
        jobs.cancel_child(job,self.user);batch.refresh_from_db();self.assertEqual(batch.state,'cancelled')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())
        self.assertFalse(jobs.run_one())
        config,_=jobs.quote(self.encounter,g.configuration());next_job=jobs.enqueue(self.encounter,self.user,config)
        second=next_job.generation_part.batch;calls,call=self.fake(second)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            for _ in range(3):self.assertTrue(jobs.run_one())
            fresh,_=jobs.quote(self.encounter,g.configuration())
            reused=jobs.enqueue(self.encounter,self.user,fresh)
            self.assertEqual(reused.pk,next_job.pk);self.assertTrue(reused.reused)
            self.assertFalse(jobs.run_one());self.assertEqual(len(calls),2)
        self.assertEqual(GenerationBatch.objects.count(),2)

    def test_model_change_after_staging_refunds_known_part_and_never_sends_second(self):
        batch=self.admit();calls,call=self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            self.assertTrue(jobs.run_one())
            with override_settings(V3_GENERATION_BATCHES=False):self.assertTrue(jobs.run_one())
            self.assertEqual(len(calls),1)
        batch.refresh_from_db();self.assertEqual(batch.state,'failed')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
        from core.models import PlatformCost
        self.assertTrue(PlatformCost.objects.filter(job=batch.parts.get(ordinal=1).job,kind='absorbed_failure').exists())

    def test_unknown_attempt_admin_resolution_consumes_identity_and_preserves_financial_history(self):
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        from core.management.commands.audit_billing import audit_report
        batch=self.admit();calls,call=self.fake(batch,fail_at=2)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            jobs.run_one();jobs.run_one()
            child=batch.parts.get(ordinal=2).job;identity=child.request_key
            request=RequestFactory().post('/console/jobs/resolve/',{'outcome':'release_no_cost',
                'evidence_note':'Synthetic provider console evidence: request not charged'})
            request.user=self.user;request.session={};request._messages=FallbackStorage(request)
            with self.assertRaisesMessage(Exception,'administrator'):jobs.resolve_view(request,child.pk)
            self.user.is_staff=True;self.user.save(update_fields=['is_staff'])
            self.assertEqual(jobs.resolve_view(request,child.pk).status_code,302)
            self.assertEqual(jobs.resolve_view(request,child.pk).status_code,409)
            self.assertFalse(jobs.run_one());self.assertEqual(len(calls),2)
        child.refresh_from_db();self.assertEqual(child.request_key,identity);self.assertEqual(child.state,'failed')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())
        report=audit_report();self.assertTrue(report['all_checks_pass'],report)

    def test_complete_constraints_guard_page_save_and_forced_stored_finalization(self):
        fs=self.version.fields;m=manifest(fs,self.template.sha256)
        m['instruction_references']=[{'id':'rule','part':'word/document.xml','slot':'b/p[0]','sha256':'2'*64}]
        m['rules']=[{'kind':'max_active_groups','source_id':'rule','maximum':1,
            'groups':[[{'key':fs[0]['key'],'values':['selected']}],[{'key':fs[-1]['key'],'values':['selected']}]]}]
        version=TemplateVersion.objects.create(template=self.template,number=3,fields=fs,contract='v3',
            generation_constraints=m,created_by=self.user);self.confirm(self.template,version)
        self.encounter.template_version=version;self.encounter.save(update_fields=['template_version'])
        batch=self.admit();calls,call=self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            for _ in range(3):jobs.run_one()
        self.encounter.refresh_from_db();post={'revision':self.encounter.revision}
        for key,answer in self.encounter.answers.items():post['answer_'+key]=answer['text'];post['reviewed_'+key]='on'
        for f in (fs[0],fs[-1]):post['answer_'+f['key']]='selected'
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/',post).status_code,409)
        self.encounter.refresh_from_db();self.assertNotEqual(self.encounter.answers[fs[0]['key']]['text'],'selected')
        forced=copy.deepcopy(self.encounter.answers)
        for f in fs:
            a=forced[f['key']];a.update(reviewed=True,reviewed_by=str(self.user.pk))
            if f in (fs[0],fs[-1]):a.update(text='selected',status='edited',edited_by=str(self.user.pk))
        Encounter.objects.filter(pk=self.encounter.pk).update(answers=forced)
        page=self.client.get(f'/encounters/{self.encounter.pk}/');self.assertIn('maximum selection',page.context['batch_constraint_error'])
        self.client.post(f'/encounters/{self.encounter.pk}/finalize/',{'revision':self.encounter.revision,'reviewed':'on'})
        self.encounter.refresh_from_db();self.assertNotEqual(self.encounter.status,'finalized');self.assertEqual(self.encounter.export_path,'')

    def test_result_reference_survives_cleanup_and_corruption_blocks_whole_adoption(self):
        from core.retention import cleanup_file
        batch=self.admit();calls,call=self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            jobs.run_one();jobs.run_one()
            part=batch.parts.select_related('job','response').get(ordinal=1)
            artifact=private_path(part.response.result_path)
            self.assertFalse(cleanup_file(artifact,encounter_id=self.encounter.pk));self.assertTrue(artifact.exists())
            with self.assertRaises(DatabaseError),transaction.atomic():GenerationBatchResponse.objects.filter(part=part).update(result_sha256='f'*64)
            with self.assertRaises(DatabaseError),transaction.atomic():Job.objects.filter(pk=part.job_id).update(result_path='receipts/replaced.json')
            artifact.write_bytes(b'corrupted synthetic result')
            self.assertTrue(jobs.run_one());self.assertEqual(len(calls),2)
        batch.refresh_from_db();self.assertEqual(batch.state,'failed')
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())

    def test_unreadable_metering_keeps_raw_response_and_http_identity_with_unknown_hold(self):
        batch=self.admit();calls,call=self.fake(batch);http_ids=[]
        def unreadable(**kw):
            result=call(**kw);raw=result.model_dump();raw['usage']['input_tokens']='unknown'
            result.usage.input_tokens='unknown';result.model_dump=lambda **_:raw
            http_ids.append(result._request_id);return result
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=unreadable
            self.assertTrue(jobs.run_one());self.assertFalse(jobs.run_one());self.assertEqual(len(calls),1)
        batch.refresh_from_db();self.assertEqual(batch.state,'reconciliation')
        part=batch.parts.select_related('job','response').get(ordinal=1)
        self.assertEqual(part.job.provider_request_id,http_ids[0]);self.assertTrue(part.job.provider_resource_id)
        recorded=json.loads(private_path(part.response.result_path).read_bytes())
        self.assertEqual(recorded['provider_request_id'],http_ids[0])
        self.assertEqual(recorded['provider_output']['usage']['input_tokens'],'unknown')
        self.assertFalse(Usage.objects.filter(job=part.job).exists());self.assertFalse(ProviderReceipt.objects.filter(job=part.job).exists())
        self.assertTrue(part.job.reservations.filter(state='held').exists())
        self.assertEqual(batch.parts.get(ordinal=2).job.state,'cancelled')


@override_settings(**SETTINGS)
class BatchConcurrency(BatchFixture,TransactionTestCase):
    def test_two_workers_and_cancellation_cannot_duplicate_started_child(self):
        batch=self.admit();calls,call=self.fake(batch);entered=Event();leave=Event()
        def paused(**kw):
            entered.set()
            if not leave.wait(10):raise AssertionError('test worker did not release')
            return call(**kw)
        def worker():
            connections.close_all()
            try:return jobs.run_one()
            finally:connections.close_all()
        with patch('anthropic.Anthropic') as provider,ThreadPoolExecutor(max_workers=1) as pool:
            provider.return_value.messages.create.side_effect=paused
            result=pool.submit(worker)
            try:
                self.assertTrue(entered.wait(10));self.assertFalse(jobs.run_one())
                from core.jobs import CancellationRefused
                with self.assertRaises(CancellationRefused):jobs.cancel_child(batch.parts.first().job,self.user)
            finally:leave.set()
            self.assertTrue(result.result(timeout=10))
            provider.return_value.messages.create.side_effect=call
            self.assertTrue(jobs.run_one());self.assertTrue(jobs.run_one());self.assertFalse(jobs.run_one())
        batch.refresh_from_db();self.assertEqual(batch.state,'succeeded');self.assertEqual(len(calls),2)
        self.assertEqual(batch.events.filter(kind='send_intent').count(),2)
