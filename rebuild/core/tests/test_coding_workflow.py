"""Synthetic coding workflow boundaries; no provider or live database access.

The coding engine and provider configuration are isolated collaborators here.
Their source/terminology and receipt checks have separate dedicated tests.
"""
import copy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core import coding_service as service
from core.coding_provider import CodingUnknown, CodingNotSent
from core.models import (AuditEvent, CodeSet, CodingContext, CodingDecision, CodingRelease,
                         CodingRun, Department, Encounter, Job, Membership, Organization,
                         Patient, Template, TemplateVersion, User)

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
RESULT = {'suggestions': [{'id': 'finding', 'system': 'ICD-10-CM', 'code': 'R11.0',
          'description': 'Synthetic fixture nausea', 'evidence': 'The patient reports nausea.',
          'explanation': 'Synthetic workflow fixture', 'instructions': [], 'eligible': True}],
          'questions': [], 'excluded': [], 'global_blockers': []}


def selection_boundary(run, value):
    if type(value) is not dict or set(value) != {'selected_ids', 'overrides'}:
        raise ValidationError('Invalid selection fixture.')
    ids = value['selected_ids']
    if any(k not in {r['id'] for r in run.result['suggestions']} for k in ids) or len(ids) != len(set(ids)):
        raise ValidationError('Unknown selection fixture.')
    return {'selected_ids': sorted(ids), 'overrides': copy.deepcopy(value['overrides'])}


@override_settings(ADMIN_SITE=False, SYNTHETIC_ONLY=True, STORAGES=STORAGES)
class CodingWorkflow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='coding-workflow', email='coding@synthetic.invalid', verified_at=timezone.now())
        self.org = Organization.objects.create(name='Synthetic coding workflow')
        self.dept = Department.objects.create(organization=self.org, name='Synthetic office')
        Membership.objects.create(user=self.user, department=self.dept, role='clinician')
        patient = Patient.objects.create(department=self.dept, display_name='Synthetic Nia Reed', reference='CODING-FIXTURE', created_by=self.user)
        template = Template.objects.create(department=self.dept, name='Synthetic coding form', format='pdf',
            original_name='synthetic.pdf', original_path='originals/synthetic.pdf', sha256='a'*64, created_by=self.user)
        version = TemplateVersion.objects.create(template=template, number=1, fields=[{'key':'finding','label':'Finding'}], created_by=self.user)
        self.e = Encounter.objects.create(department=self.dept, patient=patient, template_version=version,
            created_by=self.user, notes='The patient reports nausea.', answers={'finding':{'text':'Nausea'}},
            status='review', revision=2, service_date=date(2026, 10, 1))
        self.release = CodeSet.objects.create(system='ICD-10-CM', version='SYNTHETIC-WORKFLOW',
            effective_from=date(2026, 10, 1), effective_until=date(2027, 9, 30), source_url='https://synthetic.invalid/codes', sha256='b'*64)
        CodingRelease.objects.create(release=self.release, index=[], tabular={}, digest='c'*64)
        CodingContext.objects.create(encounter=self.e, updated_by=self.user,
            data={**service.CONTEXT_DEFAULTS, 'setting':'outpatient_office'})
        for target, kwargs in [
            ('core.coding_provider.configuration', {'return_value': {'provider':'synthetic-test'}}),
            ('core.coding_engine.generate', {'side_effect': lambda _: copy.deepcopy(RESULT)}),
            ('core.coding_engine.validate_selection', {'side_effect': selection_boundary}),
            ('core.coding_service.cpt_status', {'return_value': {'available':False}}),
        ]:
            mocked = patch(target, **kwargs); value = mocked.start(); self.addCleanup(mocked.stop)
            if target.endswith('.generate'): self.generate = value
        self.client.force_login(self.user)
        self.url = f'/encounters/{self.e.pk}/coding/'

    def complete(self):
        run = service.ensure_run(self.e, self.user)
        self.assertTrue(service.run_one()); run.refresh_from_db()
        self.assertEqual(run.state, 'succeeded')
        return run

    def approve(self, run):
        return service.approve(run, self.user, run.input_digest, service.selection_digest(run))

    def test_read_only_poll_never_creates_run_context_approval_or_audit(self):
        before = (CodingRun.objects.count(), CodingContext.objects.count(), CodingDecision.objects.count(), AuditEvent.objects.count())
        for _ in range(2):
            response = self.client.get(self.url+'status/', HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(response.json()['state'], 'unrequested')
            self.assertIn('data-coding-panel', response.json()['html'])
        self.assertEqual(before, (CodingRun.objects.count(), CodingContext.objects.count(), CodingDecision.objects.count(), AuditEvent.objects.count()))
        self.generate.assert_not_called()

    def test_same_saved_input_is_one_run_and_one_worker_execution(self):
        first = service.ensure_run(self.e, self.user, automatic=True)
        self.assertEqual(service.ensure_run(self.e, self.user).pk, first.pk)
        self.assertTrue(service.run_one()); self.assertFalse(service.run_one())
        self.assertEqual(service.ensure_run(self.e, self.user).pk, first.pk)
        self.assertEqual(CodingRun.objects.count(), 1); self.generate.assert_called_once()

    def test_finalized_explicit_request_does_not_mutate_clinical_record(self):
        self.e.status='finalized'; self.e.finalized_at=timezone.now(); self.e.finalized_by=self.user
        self.e.export_path='exports/synthetic.pdf'; self.e.export_sha256='e'*64; self.e.save()
        before=Encounter.objects.filter(pk=self.e.pk).values().get()
        self.assertIsNone(service.ensure_run(self.e, self.user, automatic=True))
        run=self.complete(); decision=self.approve(run)
        self.assertEqual(before, Encounter.objects.filter(pk=self.e.pk).values().get())
        self.assertEqual(decision.selections, run.selection)

    def test_new_engine_version_retains_failed_zero_send_run_and_requests_once(self):
        self.e.status='finalized'; self.e.finalized_at=timezone.now(); self.e.finalized_by=self.user
        self.e.export_path='exports/synthetic.pdf'; self.e.export_sha256='e'*64; self.e.save()
        clinical_before=Encounter.objects.filter(pk=self.e.pk).values().get()
        with patch('core.coding_engine.CONTRACT', 'us-outpatient-index-tabular-v1'):
            self.generate.side_effect=CodingNotSent('Coding request exceeds its byte limit; nothing was truncated or sent.')
            old=service.ensure_run(self.e,self.user);service.run_one();old.refresh_from_db()
        old_before=CodingRun.objects.filter(pk=old.pk).values().get()
        self.assertEqual(old.state,'failed');self.assertEqual(old.requests,[]);self.assertEqual(old.actual_cost,0)
        self.assertIn('This coding stage exceeds',old.error)
        self.assertNotIn('provider availability',old.error)
        view=service.snapshot(self.e,self.user)
        self.assertEqual(view['state'],'stale');self.assertTrue(view['can_request']);self.assertFalse(view['can_approve'])
        response=self.client.post(self.url+'request/', {'display_token':view['display_token']}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200)
        current=CodingRun.objects.exclude(pk=old.pk).get()
        self.assertNotEqual(current.input_digest,old.input_digest)
        self.assertEqual(current.inputs['engine_contract'],'us-outpatient-index-tabular-v4')
        self.assertEqual(service.ensure_run(self.e,self.user).pk,current.pk)
        self.assertEqual(CodingRun.objects.count(),2)
        self.assertEqual(old_before,CodingRun.objects.filter(pk=old.pk).values().get())
        self.assertEqual(clinical_before,Encounter.objects.filter(pk=self.e.pk).values().get())
        self.assertEqual(CodingDecision.objects.count(),0)
        self.assertEqual(CodingContext.objects.get(encounter=self.e).data,{**service.CONTEXT_DEFAULTS,'setting':'outpatient_office'})

    def test_corrected_engine_requires_explicit_finalized_request_and_retains_charged_failure(self):
        self.e.status='finalized'; self.e.finalized_at=timezone.now(); self.e.finalized_by=self.user
        self.e.export_path='exports/synthetic.pdf'; self.e.export_sha256='e'*64; self.e.save()
        clinical_before=Encounter.objects.filter(pk=self.e.pk).values().get()
        receipt={'stage':'concepts','attempt':1,'state':'failed','sent':True,
                 'actual_cost':'0.0123','envelope':{},'request_sha256':'b'*64}
        def invalid(run):
            run.requests=[receipt]; run.actual_cost=Decimal('0.0123')
            run.save(update_fields=['requests','actual_cost'])
            raise ValidationError('Synthetic invalid provider response')
        with patch('core.coding_engine.CONTRACT','us-outpatient-index-tabular-v2'):
            self.generate.side_effect=invalid
            old=service.ensure_run(self.e,self.user); self.assertTrue(service.run_one())
            self.assertEqual(service.ensure_run(self.e,self.user).pk,old.pk)
            self.assertFalse(service.run_one())
        old_before=CodingRun.objects.filter(pk=old.pk).values().get()
        self.assertEqual(old_before['state'],'failed')
        self.assertEqual(old_before['actual_cost'],Decimal('0.0123'))
        self.assertIsNone(service.ensure_run(self.e,self.user,automatic=True))
        self.assertEqual(CodingRun.objects.count(),1)
        view=service.snapshot(self.e,self.user)
        self.assertEqual(view['state'],'stale'); self.assertTrue(view['can_request'])
        self.assertFalse(view['can_approve'])
        response=self.client.post(self.url+'request/',{'display_token':view['display_token']},HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200)
        current=CodingRun.objects.exclude(pk=old.pk).get()
        self.assertEqual(current.inputs['engine_contract'],'us-outpatient-index-tabular-v4')
        self.assertEqual(current.inputs,{**old_before['inputs'],'engine_contract':'us-outpatient-index-tabular-v4'})
        self.assertEqual(service.ensure_run(self.e,self.user).pk,current.pk)
        self.assertEqual(CodingRun.objects.count(),2)
        self.assertEqual(old_before,CodingRun.objects.filter(pk=old.pk).values().get())
        self.assertEqual(clinical_before,Encounter.objects.filter(pk=self.e.pk).values().get())
        self.assertEqual(CodingDecision.objects.count(),0)
        self.generate.assert_called_once()

    def test_draft_empty_and_active_clinical_job_are_ineligible(self):
        for field, value in [('status','draft'), ('notes',' '), ('answers',{})]:
            original=getattr(self.e,field); setattr(self.e,field,value); self.e.save(update_fields=[field])
            self.assertIsNone(service.ensure_run(self.e,self.user))
            setattr(self.e,field,original); self.e.save(update_fields=[field])
        Job.objects.create(encounter=self.e,user=self.user,request_key='synthetic-active',state='running')
        self.assertIsNone(service.ensure_run(self.e,self.user)); self.generate.assert_not_called()

    def test_worker_holds_active_clinical_job_then_refuses_changed_snapshot(self):
        run=service.ensure_run(self.e,self.user)
        job=Job.objects.create(encounter=self.e,user=self.user,request_key='synthetic-overlap',state='queued')
        self.assertFalse(service.run_one())
        job.state='succeeded';job.save(update_fields=['state'])
        self.e.notes += ' Additional saved detail.';self.e.save(update_fields=['notes'])
        self.assertTrue(service.run_one());run.refresh_from_db()
        self.assertEqual(run.state,'failed');self.assertEqual(run.actual_cost,0);self.generate.assert_not_called()

    def test_staleness_covers_answer_revision_date_context_and_reference(self):
        run=self.complete()
        original=copy.deepcopy(self.e.answers)
        for field, value in [('answers',{'finding':{'text':'Updated'}}),('revision',3),('service_date',date(2026,10,2))]:
            before=getattr(self.e,field);setattr(self.e,field,value);self.e.save(update_fields=[field])
            self.assertEqual(service.snapshot(self.e,self.user)['state'],'stale')
            with self.assertRaises(ValidationError):self.approve(run)
            setattr(self.e,field,before);self.e.save(update_fields=[field])
        row=CodingContext.objects.get(encounter=self.e);row.data['patient_status']='new';row.save()
        with self.assertRaises(ValidationError):self.approve(run)
        row.data['patient_status']='unknown';row.save()
        extra=CodeSet.objects.create(system='ICD-10-CM',version='SYNTHETIC-REVISED',effective_from=self.release.effective_from,
            effective_until=self.release.effective_until,source_url='https://synthetic.invalid/new',sha256='d'*64)
        CodingRelease.objects.create(release=extra,digest='f'*64)
        with self.assertRaises(ValidationError):self.approve(run)
        self.assertEqual(self.e.answers,original)

    def test_context_reversion_displays_matching_run_and_token_remains_usable(self):
        first=self.complete()
        service.update_context(self.e,self.user,{'setting':'outpatient_office','patient_status':'new'})
        service.update_context(self.e,self.user,{'setting':'outpatient_office'})
        view=service.snapshot(self.e,self.user)
        self.assertEqual(view['run'].pk,first.pk)
        response=self.client.post(self.url+'context/', {'display_token':view['display_token'],'context':{'setting':'outpatient_office'}},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(CodingRun.objects.count(),2)

    def test_approval_binds_all_selections_and_is_idempotent(self):
        run=self.complete();old=service.selection_digest(run)
        run=service.update_selection(run,self.user,{'selected_ids':[],'overrides':{}},run.selection_revision)
        with self.assertRaises(ValidationError):service.approve(run,self.user,run.input_digest,old)
        decision=self.approve(run)
        self.assertEqual(self.approve(run).pk,decision.pk)
        self.assertEqual(decision.selections,{'selected_ids':[],'overrides':{}})
        with self.assertRaises(ValidationError):service.update_selection(run,self.user,{'selected_ids':['finding'],'overrides':{}},run.selection_revision)
        self.assertEqual(CodingDecision.objects.count(),1)

    def test_selection_revision_and_signed_display_refuse_old_tabs(self):
        run=self.complete();view=service.snapshot(self.e,self.user)
        service.update_selection(run,self.user,{'selected_ids':[],'overrides':{}},run.selection_revision)
        response=self.client.post(self.url+f'runs/{run.pk}/approve/',{'display_token':view['display_token'],
            'input_digest':run.input_digest,'selection_digest':view['selection_digest']},content_type='application/json')
        self.assertEqual(response.status_code,409);self.assertEqual(CodingDecision.objects.count(),0)
        with self.assertRaises(ValidationError):service.update_selection(run,self.user,{'selected_ids':['finding'],'overrides':{}},0)

    def test_selective_approval_counts_persist_and_questions_remain_open(self):
        result=copy.deepcopy(RESULT)
        result['suggestions'].append({**result['suggestions'][0], 'id':'second'})
        result['questions']=[{'system':'CPT','question':'Confirm the E/M basis.','blocking':True},
                             {'system':'ICD-10-CM','question':'Clarify another symptom.','blocking':False}]
        self.generate.side_effect=lambda _:copy.deepcopy(result)
        run=service.ensure_run(self.e,self.user);service.run_one();run.refresh_from_db()
        pending=service.snapshot(self.e,self.user)
        self.assertEqual(pending['summary'],{'approved':0,'awaiting_review':2,'not_included':0,'unresolved_questions':2})
        run=service.update_selection(run,self.user,{'selected_ids':['finding'],'overrides':{}},run.selection_revision)
        self.assertEqual(service.snapshot(self.e,self.user)['summary']['awaiting_review'],2)
        decision=self.approve(run)
        before=(CodingRun.objects.count(),CodingDecision.objects.count(),AuditEvent.objects.count())
        for _ in range(2):
            view=service.snapshot(self.e,self.user)
            self.assertEqual(view['summary'],{'approved':1,'awaiting_review':0,'not_included':1,'unresolved_questions':2})
            self.assertEqual(view['decision'].pk,decision.pk)
            self.assertEqual(view['state_label'],'Selections approved; questions remain')
            self.assertEqual({s['id'] for s in view['suggestions'] if s['selected']},set(decision.selections['selected_ids']))
            response=self.client.get(self.url+'status/',HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code,200)
            html=response.json()['html']
            for text in ['1 approved selection','0 suggestions awaiting review','2 unresolved questions',
                         '1 not included','Reviewed; not included','questions below remain unresolved']:
                self.assertIn(text,html)
            self.assertNotIn('to review</span>',html)
            self.assertNotIn('data-coding-form="approval"',html)
        self.assertEqual(before,(CodingRun.objects.count(),CodingDecision.objects.count(),AuditEvent.objects.count()))
        run.refresh_from_db();self.assertEqual(run.state,'needs_detail')
        self.generate.assert_called_once()

    def test_excluding_every_suggestion_is_a_reviewed_decision_not_pending_work(self):
        run=self.complete()
        run=service.update_selection(run,self.user,{'selected_ids':[],'overrides':{}},run.selection_revision)
        self.approve(run)
        view=service.snapshot(self.e,self.user)
        self.assertEqual(view['summary'],{'approved':0,'awaiting_review':0,'not_included':1,'unresolved_questions':0})
        self.assertEqual(view['state_label'],'Selections approved')

    def test_earlier_approval_never_counts_toward_a_changed_saved_revision(self):
        run=self.complete();decision=self.approve(run)
        for field,value in [('revision',3),('service_date',date(2026,10,2)),
                            ('answers',{'finding':{'text':'Changed saved answer'}})]:
            original=getattr(self.e,field);setattr(self.e,field,value);self.e.save(update_fields=[field])
            view=service.snapshot(self.e,self.user)
            self.assertEqual(view['state'],'stale')
            self.assertFalse(view['current']);self.assertIsNone(view['decision'])
            self.assertEqual(view['historical_decision'].pk,decision.pk)
            self.assertEqual(view['summary'],{'approved':0,'awaiting_review':0,'not_included':0,'unresolved_questions':0})
            html=self.client.get(self.url+'status/',HTTP_ACCEPT='application/json').json()['html']
            self.assertIn('This approval does not cover the current saved revision.',html)
            self.assertNotIn('data-coding-summary',html)
            setattr(self.e,field,original);self.e.save(update_fields=[field])
        self.e.revision+=1;self.e.save(update_fields=['revision'])
        self.complete()
        current=service.snapshot(self.e,self.user)
        self.assertIsNone(current['decision']);self.assertIsNone(current['historical_decision'])
        self.assertEqual(current['summary']['approved'],0)
        self.assertEqual(current['summary']['awaiting_review'],1)
        self.assertEqual(CodingDecision.objects.get(pk=decision.pk).selections,decision.selections)

    def test_tenant_actor_role_and_methods_are_scoped(self):
        run=self.complete();view=service.snapshot(self.e,self.user)
        other=User.objects.create_user(username='other-coding',email='other@synthetic.invalid',verified_at=timezone.now())
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url+'status/',HTTP_ACCEPT='application/json').status_code,404)
        with self.assertRaises(PermissionDenied):service.ensure_run(self.e,other)
        Membership.objects.create(user=other,department=self.dept,role='assistant')
        with self.assertRaises(PermissionDenied):self.approve_as(run,other)
        with self.assertRaises(ValidationError):service.verify_display(self.e,other,view['display_token'],run)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url+'request/').status_code,405)

    def approve_as(self,run,user):
        return service.approve(run,user,run.input_digest,service.selection_digest(run))

    def test_required_global_details_block_approval_but_cpt_only_does_not_block_icd(self):
        for blocker, questions, allowed in [(['Identity mismatch'],[],False),([], [{'system':'CPT','blocking':True}],True)]:
            self.e.revision+=1;self.e.save(update_fields=['revision'])
            self.generate.side_effect=lambda _,b=blocker,q=questions:{**copy.deepcopy(RESULT),'global_blockers':b,'questions':q}
            run=service.ensure_run(self.e,self.user);service.run_one();run.refresh_from_db()
            if allowed:self.approve(run)
            else:
                with self.assertRaises(ValidationError):self.approve(run)

    def test_unresolved_diagnosis_questions_are_not_reported_as_legitimate_empty(self):
        for system, expected in [('ICD-10-CM', 'needs_detail'), ('CPT', 'empty')]:
            self.e.revision+=1;self.e.save(update_fields=['revision'])
            self.generate.side_effect=lambda _,s=system:{'suggestions':[], 'questions':[{'system':s,'question':'Clarify fixture detail','blocking':False}], 'excluded':[], 'global_blockers':[]}
            run=service.ensure_run(self.e,self.user);service.run_one();run.refresh_from_db()
            self.assertEqual(service.snapshot(self.e,self.user)['state'],expected)
            self.assertEqual(run.actual_cost,0)

    def test_name_answers_are_source_positioned_and_independent_of_model_extraction(self):
        fields=[{'key':'name','label':'Patient name:'},{'key':'sign','label':'Clinician full name'},
                        {'key':'full','label':'Full name'},{'key':'other','label':'Name of patient'},
                        {'key':'cell_1','label':"What is the patient's full name?"},
                        {'key':'cell_0','label':"What is the referring physician's full name?"}]
        version=TemplateVersion.objects.create(template=self.e.template_version.template,number=2,fields=fields,created_by=self.user)
        self.e.template_version=version
        self.e.answers={'name':{'text':'Synthetic Different Person'},'sign':{'text':'Synthetic Clinician'},
                        'full':{'text':'Synthetic Alias'},'other':{'text':' '},
                        'cell_1':{'text':'Synthetic Third Identity'},'cell_0':{'text':'Synthetic Referrer'}}
        self.e.save(update_fields=['answers','template_version'])
        self.assertTrue(service.snapshot(self.e,self.user)['identity_review_available'])
        self.assertFalse(CodingRun.objects.filter(encounter=self.e).exists())
        run=service.ensure_run(self.e,self.user)
        self.assertEqual(run.inputs['patient_name_answers'],[
            {'key':'name','label':'Patient name:','text':'Synthetic Different Person'},
            {'key':'full','label':'Full name','text':'Synthetic Alias'},
            {'key':'cell_1','label':"What is the patient's full name?",'text':'Synthetic Third Identity'}])
        self.assertEqual(run.inputs['patient_identity']['display_name'],'Synthetic Nia Reed')
        self.assertEqual(run.input_digest,service.digest({'inputs':run.inputs,'context':run.context,'releases':run.releases}))

    def test_processing_errors_show_safe_actionable_reason_without_raw_exception(self):
        self.generate.side_effect=ValidationError('Coding evidence does not exactly occur in the saved source note.')
        run=service.ensure_run(self.e,self.user);service.run_one();run.refresh_from_db()
        self.assertIn('does not exactly occur',run.error);self.assertIn('administrator',run.error)
        self.assertNotIn('synthetic-secret',service.failure_message(RuntimeError('synthetic-secret'),False))
        self.assertNotIn('synthetic-secret',service.failure_message(CodingNotSent('synthetic-secret'),False))

    def test_evidence_context_requires_exact_saved_quote_and_synthetic_identity_attestation(self):
        with self.assertRaises(ValidationError):service.update_context(self.e,self.user,{'time_evidence':'Invented time evidence'})
        with override_settings(SYNTHETIC_ONLY=False),self.assertRaises(ValidationError):
            service.update_context(self.e,self.user,{'identity_review_reason':'Reviewed fixture alias'})
        with self.assertRaises(ValidationError):service.update_context(self.e,self.user,{'time_same_day':1})
        with self.assertRaises(ValidationError):service.update_context(self.e,self.user,{'unexpected':'value'})
        self.assertEqual(CodingRun.objects.count(),0)

    def test_unknown_provider_outcome_keeps_receipts_and_never_retries(self):
        receipt={'stage':'concepts','attempt':1,'state':'unknown','actual_cost':None,'envelope':{},'request_sha256':'a'*64}
        def uncertain(run):
            run.requests=[receipt];run.actual_cost=None;run.save(update_fields=['requests','actual_cost'])
            raise CodingUnknown('Synthetic unresolved request')
        self.generate.side_effect=uncertain
        run=service.ensure_run(self.e,self.user);self.assertTrue(service.run_one());run.refresh_from_db()
        self.assertEqual(run.state,'uncertain');self.assertIsNone(run.actual_cost);self.assertEqual(run.requests,[receipt])
        self.assertEqual(service.ensure_run(self.e,self.user).pk,run.pk);self.assertFalse(service.run_one())
        self.generate.assert_called_once()

    def test_known_failed_stage_cost_is_not_erased(self):
        receipt={'stage':'concepts','attempt':1,'state':'failed','actual_cost':'0.0123','envelope':{},'request_sha256':'b'*64}
        def fail(run):
            run.requests=[receipt];run.actual_cost=Decimal('0.0123');run.save(update_fields=['requests','actual_cost'])
            raise ValidationError('Synthetic bad response')
        self.generate.side_effect=fail
        run=service.ensure_run(self.e,self.user);service.run_one();run.refresh_from_db()
        self.assertEqual(run.state,'failed');self.assertEqual(run.actual_cost,Decimal('0.0123'));self.assertEqual(run.requests,[receipt])

    def test_interrupted_worker_exposes_uncertain_result_without_resend(self):
        run=service.ensure_run(self.e,self.user)
        run.state='running';run.started_at=timezone.now()-timedelta(minutes=16)
        run.requests=[{'stage':'concepts','attempt':1,'state':'sending','envelope':{},'request_sha256':'a'*64}];run.save()
        self.assertFalse(service.run_one());run.refresh_from_db()
        self.assertEqual(run.state,'uncertain');self.generate.assert_not_called()

    def test_missing_reference_creates_honest_non_sent_state(self):
        with patch('core.coding_service.release_snapshot',return_value=[]):
            run=service.ensure_run(self.e,self.user)
            self.assertEqual(run.state,'needs_detail');self.assertEqual(run.actual_cost,0)
            self.assertEqual(service.snapshot(self.e,self.user)['state'],'terminology_unavailable')
            self.assertFalse(service.run_one());self.generate.assert_not_called()

    def test_duplicate_json_fields_and_forged_display_are_refused(self):
        for payload in ['{"display_token":"a","display_token":"b"}', '{"display_token":"forged"}', '{"display_token":NaN}']:
            response=self.client.post(self.url+'request/',payload,content_type='application/json')
            self.assertEqual(response.status_code,409)
        self.assertEqual(CodingRun.objects.count(),0)

    def test_database_preserves_finished_execution_and_approval(self):
        run=self.complete();decision=self.approve(run)
        for mutation in [lambda:CodingRun.objects.filter(pk=run.pk).update(state='queued'),
                         lambda:CodingRun.objects.filter(pk=run.pk).update(inputs={}),
                         lambda:CodingDecision.objects.filter(pk=decision.pk).update(selections={})]:
            with self.assertRaises(DatabaseError),transaction.atomic():mutation()

    def test_received_unmetered_interruption_is_uncertain_and_retains_raw_response(self):
        run=service.ensure_run(self.e,self.user)
        run.state='running';run.started_at=timezone.now()-timedelta(minutes=16)
        receipt={'stage':'concepts','attempt':1,'state':'received','sent':True,'actual_cost':None,
                 'raw_response':{'synthetic':'retained'},'envelope':{},'request_sha256':'a'*64}
        run.requests=[receipt];run.save()
        self.assertFalse(service.run_one());run.refresh_from_db()
        self.assertEqual(run.state,'uncertain');self.assertEqual(run.requests,[receipt])
        self.assertIsNone(run.actual_cost);self.generate.assert_not_called()

    def test_saved_replacement_displays_its_authoritative_description_and_instructions(self):
        result=copy.deepcopy(RESULT)
        replacement={'code':'SYN02','system':'ICD-10-CM','description':'Synthetic replacement descriptor',
                     'instructions':[{'text':'Synthetic replacement instruction'}]}
        result['candidates']={'finding':[replacement]}
        self.generate.side_effect=lambda _:result
        run=self.complete()
        service.update_selection(run,self.user,{'selected_ids':['finding'],
            'overrides':{'finding':{'code':'SYN02','reason':'Synthetic documented correction'}}},1)
        display=service.snapshot(self.e,self.user)
        row=display['suggestions'][0]
        self.assertEqual(row['code'],'SYN02');self.assertEqual(row['description'],replacement['description'])
        self.assertEqual(row['instructions'],replacement['instructions'])
        self.assertEqual(row['original_code'],'R11.0')
        self.assertTrue(display['can_approve'])

    def test_database_cannot_change_approved_selections_or_their_revision(self):
        run=self.complete();self.approve(run)
        for values in [{'selection':{'selected_ids':[],'overrides':{}},'selection_revision':2},
                       {'selection_revision':2}]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                CodingRun.objects.filter(pk=run.pk).update(**values)
        run.refresh_from_db();self.assertEqual(run.selection_revision,1)
        self.assertEqual(service.snapshot(self.e,self.user)['state'],'approved')

    def test_committed_save_hook_queues_once_and_does_not_change_document(self):
        from core.coding_hooks import after_saved_document
        before=Encounter.objects.filter(pk=self.e.pk).values().get()
        with self.captureOnCommitCallbacks(execute=True):
            after_saved_document(self.e.pk,self.user.pk)
            after_saved_document(self.e.pk,self.user.pk)
            self.assertEqual(CodingRun.objects.count(),0)
        self.assertEqual(CodingRun.objects.count(),1)
        self.assertEqual(before,Encounter.objects.filter(pk=self.e.pk).values().get())
