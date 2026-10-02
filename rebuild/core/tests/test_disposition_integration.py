"""Synthetic counterexamples for recovered preparation, not disposal authority."""
import copy
import json
import uuid
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings
from core import disposition as d, models as m
from core.tests.test_retention_preservation import Fixture, ISOLATED


@override_settings(**ISOLATED)
class RecoveredBoundaries(Fixture, TestCase):
    def setUp(self):
        self.setup_records()

    def proposal(self):
        return d.submit(self.admin, self.scope[2].pk, 'encounter', self.encounter.pk, 'a'*64, uuid.uuid4())

    def batch(self, *, state='failed', child_state='failed'):
        part = {'field_ids': ['synthetic'], 'request_sha256': 'c'*64, 'maximum_charge': '0'}
        plan = {'parts': [part]}
        batch = m.GenerationBatch.objects.create(encounter=self.encounter, user=self.scope[0], admission_key=uuid.uuid4(),
            revision=self.encounter.revision, plan=plan, plan_sha256=d.digest(plan), maximum_charge=0, state=state)
        job = m.Job.objects.create(encounter=self.encounter, user=self.scope[0], request_key='synthetic:'+str(batch.pk),
            revision=self.encounter.revision, kind='generation_part', state=child_state,
            config={'generation_part': {'batch_id': str(batch.pk), 'plan_sha256': batch.plan_sha256, 'ordinal': 1}})
        child = m.GenerationBatchPart.objects.create(batch=batch, job=job, ordinal=1, **part)
        return batch, child

    def test_known_batch_schema_is_supported_without_weakening_unknown_schema_refusal(self):
        d.check_catalog()
        with patch.dict(d.COLUMNS, {'GenerationBatch': []}), self.assertRaises(ValidationError):
            d.check_catalog()

    def test_terminal_batch_keeps_late_child_and_immutable_response_in_graph(self):
        batch, part = self.batch(child_state='reconciliation')
        response = m.GenerationBatchResponse.objects.create(part=part, result_path='receipts/synthetic.json',
            result_sha256='d'*64, model='synthetic', stop_reason='end_turn')
        # Isolate graph coverage from the separately demonstrated old catalog refusal.
        with patch.object(d, 'check_catalog'):
            plan = d.prepare(self.admin, self.proposal().pk)
        self.assertEqual([r['id'] for r in plan.graph['nodes'].get('GenerationBatch', [])], [str(batch.pk)])
        self.assertEqual([r['id'] for r in plan.graph['nodes'].get('GenerationBatchPart', [])], [str(part.pk)])
        self.assertEqual([r['id'] for r in plan.graph['nodes'].get('GenerationBatchResponse', [])], [str(response.pk)])
        self.assertIn('receipts/synthetic.json', plan.graph['storage_keys'])
        self.assertIn('work_or_finance_unresolved', plan.graph['blockers'])
        self.assertFalse(plan.graph['deletion_authorized'])

    def test_late_batch_event_invalidates_review_snapshot(self):
        batch, part = self.batch()
        with patch.object(d, 'check_catalog'):
            plan = d.prepare(self.admin, self.proposal().pk)
            m.GenerationBatchEvent.objects.create(batch=batch, part=part, kind='synthetic_late_result', event_key=str(uuid.uuid4()))
            with self.assertRaisesMessage(ValidationError, 'graph changed'):
                d.review(self.second, plan.pk, plan.graph_sha256, 'reviewed', 'b'*64)

    def test_restore_quarantine_rejects_direct_mapping_and_batch_workers(self):
        from core import mapping_jobs, batch_jobs
        with override_settings(RESTORE_QUARANTINE=True):
            for worker in (mapping_jobs.run_one, batch_jobs.run_one):
                with self.subTest(worker=worker.__module__), self.assertRaisesMessage(ValidationError, 'quarantined'):
                    worker()

    def test_quarantine_preserves_preview_authentication_and_public_css(self):
        from core.tests.test_preview_access import SETTINGS, EDGE
        with override_settings(**dict(SETTINGS, RESTORE_QUARANTINE=True)):
            response = self.client.get('/preview/sign-in/', **EDGE)
            self.assertEqual(response.status_code, 200)
        inner = lambda request: HttpResponse('synthetic public css')
        with override_settings(RESTORE_QUARANTINE=True):
            self.assertEqual(d.RestoreQuarantineMiddleware(inner)(RequestFactory().get('/static/app.css')).status_code, 200)
            self.assertEqual(d.RestoreQuarantineMiddleware(inner)(RequestFactory().get('/encounters/')).status_code, 503)

    def test_database_refuses_false_restore_journal_and_mismatched_target_claims(self):
        selected = uuid.uuid4()
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(selected)):
            valid = d.prepare_restore(self.admin, selected, 'a'*64)
        for change in ('journal', 'target', 'backup', 'typed_bool'):
            report = copy.deepcopy(valid.report)
            if change == 'journal': report['journal_freshness_verified'] = True
            elif change == 'target': report['target']['instance_id'] = str(uuid.uuid4())
            elif change == 'backup': report['backup_sha256'] = 'b'*64
            else: report['quarantined'] = 'true'
            with self.subTest(change=change), self.assertRaises(DatabaseError), transaction.atomic():
                m.RestorePreparation.objects.create(instance_id=selected, target=valid.target, backup_sha256='a'*64,
                    report=report, report_sha256=d.digest(report), created_by=self.admin)

    def test_database_refuses_plan_for_another_scope_or_string_authority(self):
        request = self.proposal()
        with patch.object(d, 'check_catalog'):
            valid = d.graph(request)
        for change in ('target', 'department', 'scope', 'typed_bool'):
            value = copy.deepcopy(valid)
            if change == 'typed_bool': value['deletion_authorized'] = 'false'
            else: value[{'target':'target_id', 'department':'department_id', 'scope':'scope'}[change]] = str(uuid.uuid4())
            with self.subTest(change=change), self.assertRaises(DatabaseError), transaction.atomic():
                m.DispositionPlan.objects.create(request=request, graph=value, graph_sha256=d.digest(value), created_by=self.admin)

    def test_proposals_preserve_signatures_consent_accounts_finance_and_existing_audit(self):
        from django.apps import apps
        from core.security import audit
        m.Encounter.objects.filter(pk=self.encounter.pk).update(
            answers={'signature': {'text': 'SYNTHETIC SIGNATURE', 'reviewed': True}},
            template_review={'consent': {'decision': 'reviewed', 'quote': 'SYNTHETIC CONSENT'}})
        audit(self.scope[0], 'synthetic.consent_recorded', self.encounter.pk, decision='synthetic-consented')
        models = [model for model in apps.get_app_config('core').get_models()
                  if model.__name__ not in d.PREPARATION | {'AuditEvent'}]
        before = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        audits = list(m.AuditEvent.objects.order_by('pk').values())
        plan = d.prepare(self.admin, self.proposal().pk)
        d.review(self.second, plan.pk, plan.graph_sha256, 'reviewed', 'b'*64)
        self.assertEqual(before, {model.__name__: list(model.objects.order_by('pk').values()) for model in models})
        self.assertEqual(audits, list(m.AuditEvent.objects.filter(pk__in=[r['id'] for r in audits]).order_by('pk').values()))
        self.assertNotIn('SYNTHETIC SIGNATURE', json.dumps(plan.graph))
        self.assertNotIn('SYNTHETIC CONSENT', json.dumps(plan.graph))


from core.tests.test_generation_batch import BatchFixture, SETTINGS


@override_settings(**SETTINGS)
class QuarantinedAdoption(BatchFixture, TestCase):
    def recorded(self):
        from core import batch_jobs
        batch = self.admit()
        _, call = self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            batch_jobs.run_one()
            batch_jobs.run_one()
        return batch

    def test_direct_recorded_adoption_refuses_quarantine(self):
        from core import batch_jobs
        batch = self.recorded()
        with override_settings(RESTORE_QUARANTINE=True), self.assertRaisesMessage(ValidationError, 'quarantined'):
            batch_jobs.finish(batch.pk)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers, {})

    def test_admin_recorded_recovery_refuses_quarantine(self):
        from core import batch_jobs
        batch = self.recorded()
        batch.state = 'reconciliation'
        batch.save(update_fields=['state'])
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        with override_settings(RESTORE_QUARANTINE=True), self.assertRaisesMessage(ValidationError, 'quarantined'):
            batch_jobs.recover_recorded(batch.pk, self.user)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers, {})
