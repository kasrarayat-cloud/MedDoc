"""Finite synthetic preparation proofs. No deletion, provider or admission grant."""
import json
import os
from pathlib import Path
import socket
import uuid
from decimal import Decimal
from unittest.mock import patch
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.management import call_command
from django.db import connection,transaction,DatabaseError
from django.test import TestCase,Client,override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from core import disposition as d,retention,models as m,jobs
from core.tests.test_retention_preservation import Fixture,ISOLATED

@override_settings(**ISOLATED)
class DispositionPreparation(Fixture,TestCase):
    def setUp(self):
        self.setup_records()
        network=patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden'))
        network.start();self.addCleanup(network.stop)
    def request(self):
        return d.submit(self.admin,self.scope[2].pk,'encounter',self.encounter.pk,'a'*64,uuid.uuid4())
    def plan(self):return d.prepare(self.admin,self.request().pk)
    def login(self,user=None,csrf=False):
        user=user or self.admin
        self.client=Client(enforce_csrf_checks=csrf)
        device=TOTPDevice.objects.create(user=user,name='Synthetic',confirmed=True)
        self.client.force_login(user);session=self.client.session;session['otp_device_id']=device.persistent_id;session.save()

    def test_proposal_and_review_are_immutable_review_only(self):
        plan=self.plan();self.assertFalse(plan.graph['deletion_authorized'])
        self.assertIn('policy_unset',plan.graph['blockers'])
        self.assertNotIn(self.encounter.notes,json.dumps(plan.graph))
        row=d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64)
        self.assertEqual(d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64).pk,row.pk)
        self.assertEqual(m.Encounter.objects.get(pk=self.encounter.pk).notes,self.encounter.notes)
        self.assertTrue(m.Template.objects.filter(pk=self.scope[4].pk).exists())

    def test_scope_self_review_suspension_and_conflicting_reuse_refuse(self):
        with self.assertRaises(ValidationError):d.submit(self.admin,self.other[2].pk,'encounter',self.encounter.pk,'a'*64,uuid.uuid4())
        with self.assertRaises(ValidationError):d.submit(self.admin,self.scope[2].pk,'global',self.encounter.pk,'a'*64,uuid.uuid4())
        with self.assertRaises(PermissionDenied):d.submit(self.scope[0],self.scope[2].pk,'patient',self.scope[3].pk,'a'*64,uuid.uuid4())
        request=self.request()
        self.assertEqual(d.submit(self.admin,request.department_id,request.scope,request.target_id,'a'*64,request.request_key).pk,request.pk)
        with self.assertRaises(ValidationError):d.submit(self.admin,request.department_id,request.scope,request.target_id,'b'*64,request.request_key)
        plan=d.prepare(self.admin,request.pk)
        with self.assertRaises(PermissionDenied):d.review(self.admin,plan.pk,plan.graph_sha256,'reviewed','b'*64)
        m.User.objects.filter(pk=self.second.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64)

    def test_changed_graph_or_digest_requires_new_plan(self):
        plan=self.plan()
        with self.assertRaises(ValidationError):d.review(self.second,plan.pk,'f'*64,'reviewed','b'*64)
        m.Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC CORRECTION',revision=1)
        with self.assertRaisesMessage(ValidationError,'graph changed'):d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64)
        self.assertFalse(m.DispositionReview.objects.exists())

    def test_unknown_model_edge_column_and_oversized_graph_refuse_atomically(self):
        request=self.request()
        for target in ('EDGES','COLUMNS'):
            with self.subTest(target=target),patch.object(d,target,{}),self.assertRaises(ValidationError):d.prepare(self.admin,request.pk)
        with patch.object(d,'LIMIT',1),self.assertRaises(ValidationError):d.prepare(self.admin,request.pk)
        self.assertFalse(m.DispositionPlan.objects.exists())

    def test_hold_archive_and_shared_source_remain_blocked(self):
        hold=self.hold();m.Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC CORRECTION')
        other=m.Encounter.objects.create(department=self.scope[2],patient=self.scope[3],template_version=self.encounter.template_version,
            created_by=self.scope[0],notes='SYNTHETIC OTHER',service_date=self.encounter.service_date)
        report=self.plan().graph
        for reason in ['active_hold','historical_preservation','preserved_evidence','shared_reference','immutable_evidence']:self.assertIn(reason,report['blockers'])
        retention.release_hold(self.second,hold.pk,'b'*64)
        report=self.plan().graph
        self.assertNotIn('active_hold',report['blockers']);self.assertIn('historical_preservation',report['blockers'])

    def test_terminal_job_receipt_and_late_reconciliation_remain_financial_blockers(self):
        job=m.Job.objects.create(encounter=self.encounter,user=self.scope[0],request_key='late',state='failed')
        m.ProviderReceipt.objects.create(job=job,provider='synthetic',provider_request_id='synthetic-receipt',
            actual_cost=Decimal('0.01'),simulated=True)
        report=self.plan().graph;self.assertIn('receipt_accounting_unresolved',report['blockers'])
        m.Job.objects.filter(pk=job.pk).update(state='reconciliation')
        report=self.plan().graph;self.assertIn('work_or_finance_unresolved',report['blockers'])
        self.assertEqual(len(report['nodes']['Job']),1)

    def test_held_funds_and_changed_shared_reference_are_part_of_plan(self):
        from core.billing import reserve
        job=m.Job.objects.create(encounter=self.encounter,user=self.scope[0],request_key='held')
        reserve(job,charge_limit=Decimal('0.25'))
        plan=self.plan();self.assertIn('funds_held',plan.graph['blockers'])
        m.Payment.objects.create(user=self.scope[0],wallet=job.reservations.get().wallet,amount_cents=100,status='pending')
        self.assertIn('financial_history_unresolved',self.plan().graph['blockers'])
        other=m.Encounter.objects.create(department=self.scope[2],patient=self.scope[3],template_version=self.encounter.template_version,
            created_by=self.scope[0],notes='SYNTHETIC SHARED',service_date=self.encounter.service_date)
        plan=d.prepare(self.admin,plan.request_id)
        self.assertTrue(plan.graph['nodes']['SharedEncounter'])
        m.Encounter.objects.filter(pk=other.pk).update(notes='SYNTHETIC SHARED CORRECTION')
        with self.assertRaises(ValidationError):d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64)

    def test_raw_sql_cannot_forge_self_review_or_mutate_evidence(self):
        plan=self.plan()
        with self.assertRaises(DatabaseError),transaction.atomic():
            m.DispositionReview.objects.create(plan=plan,decision='reviewed',graph_sha256=plan.graph_sha256,evidence_sha256='b'*64,created_by=self.admin)
        d.review(self.second,plan.pk,plan.graph_sha256,'reviewed','b'*64)
        for table in ('dispositionrequest','dispositionplan','dispositionreview'):
            for verb in ('UPDATE core_'+table+' SET created_at=now()','DELETE FROM core_'+table,'TRUNCATE core_'+table+' CASCADE'):
                with self.subTest(verb=verb),self.assertRaises(DatabaseError),transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute(verb)

    def test_migration_reverse_refuses_when_any_preparation_evidence_exists(self):
        from importlib import import_module
        self.plan()
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute(import_module('core.migrations.0028_disposition_preparation').REVERSE)

    def test_empty_guard_reverse_can_be_rolled_back_without_losing_catalog(self):
        from importlib import import_module
        from ops import integrity_contract
        class Rollback(Exception):pass
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(import_module('core.migrations.0028_disposition_preparation').REVERSE)
                raise Rollback()
        except Rollback:pass
        with connection.cursor() as cursor:
            cursor.execute(integrity_contract.CATALOG);rows=cursor.fetchall()
            cursor.execute(integrity_contract.CONTEXT);context=cursor.fetchall()
        self.assertTrue(integrity_contract.assess(rows,context,82)['passed'])

    def test_mfa_csrf_actual_forms_and_scope_errors(self):
        self.client.force_login(self.admin)
        self.assertIn(self.client.get('/console/disposition/').status_code,(302,404))
        self.login(csrf=True)
        with override_settings(ADMIN_SITE=True):
            page=self.client.get('/console/disposition/');self.assertEqual(page.status_code,200)
            payload={'action':'request','request-department':str(self.scope[2].pk),'request-scope':'encounter',
                'request-target':str(self.encounter.pk),'request-authority':'a'*64,'request-request_key':str(uuid.uuid4()),'request-confirmed':'on'}
            self.assertEqual(self.client.post('/console/disposition/',payload).status_code,403)
            payload['csrfmiddlewaretoken']=self.client.cookies[settings.CSRF_COOKIE_NAME].value
            bad={**payload,'request-department':str(self.other[2].pk)}
            self.assertEqual(self.client.post('/console/disposition/',bad).status_code,200);self.assertFalse(m.DispositionRequest.objects.exists())
            self.assertEqual(self.client.post('/console/disposition/',payload).status_code,302)
            plan=d.prepare(self.admin,m.DispositionRequest.objects.get().pk)
            page=self.client.get('/console/disposition/');self.assertContains(page,'Review only')
            self.assertNotContains(page,self.encounter.notes);self.assertNotContains(page,self.scope[3].display_name)
            if output:=os.getenv('QUILLMD_DISPOSITION_ARTIFACT_DIR'):
                Path(output).mkdir(parents=True,exist_ok=True);(Path(output)/'disposition-admin.html').write_bytes(page.content)
            self.login(self.second,csrf=True);self.client.get('/console/disposition/')
            review={'action':'review','review-plan':str(plan.pk),'review-graph_sha256':plan.graph_sha256,
                'review-decision':'reviewed','review-evidence':'b'*64,'review-confirmed':'on',
                'csrfmiddlewaretoken':self.client.cookies[settings.CSRF_COOKIE_NAME].value}
            self.assertEqual(self.client.post('/console/disposition/',review).status_code,302)
            self.assertEqual(m.DispositionReview.objects.get().created_by_id,self.second.pk)

    def test_restore_missing_target_never_admits(self):
        with self.assertRaises(ValidationError):d.prepare_restore(self.admin,uuid.uuid4(),'a'*64)
        instance=uuid.uuid4()
        with override_settings(RESTORE_QUARANTINE=True,RESTORE_INSTANCE_ID=str(instance)):
            with self.assertRaises(ValidationError):d.prepare_restore(self.admin,uuid.uuid4(),'a'*64)
            row=d.prepare_restore(self.admin,instance,'a'*64)
            self.assertTrue(row.report['quarantined']);self.assertFalse(row.report['admission_available'])
            self.assertFalse(row.report['journal_freshness_verified'])
            for verb in ('UPDATE core_restorepreparation SET created_at=now()','DELETE FROM core_restorepreparation','TRUNCATE core_restorepreparation CASCADE'):
                with self.assertRaises(DatabaseError),transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute(verb)

    def test_quarantine_blocks_direct_data_worker_cleanup_but_auth_health_and_review_survive(self):
        self.login();path=self.file()
        with override_settings(RESTORE_QUARANTINE=True,RESTORE_INSTANCE_ID=str(uuid.uuid4()),ADMIN_SITE=True):
            for route in (f'/api/encounters/{self.encounter.pk}/',f'/encounters/{self.encounter.pk}/export/',f'/templates/{self.scope[4].pk}/original/','/console/','/api/patients/'):
                self.assertEqual(self.client.get(route).status_code,503)
            with self.assertRaises(ValidationError):jobs.run_one()
            with self.assertRaises(ValidationError):call_command('worker',once=True)
            self.assertFalse(retention.cleanup_file(path));self.assertTrue(path.exists())
            self.assertEqual(self.client.get('/health/').status_code,200)
            self.assertNotEqual(self.client.get('/login/').status_code,503)
            self.assertEqual(self.client.get('/console/disposition/').status_code,200)
            page=self.client.get('/console/restore-preparation/');self.assertEqual(page.status_code,200)
            if output:=os.getenv('QUILLMD_DISPOSITION_ARTIFACT_DIR'):(Path(output)/'restore-admin.html').write_bytes(page.content)
