"""R-B: a DatabaseError raised from settle() inside core.jobs.run_one, and the administrator resolution of that state.

Residual 2 of the final default-path refutation on d9fa3249: run_one turns a DatabaseError from settle() into
reconciliation. These tests make the database itself fail settlement at four points of its one transaction:

  * its first statement (the job row lock), as a deadlock victim would;
  * the usage insert, after the wallet, ledger and reservation writes of the same transaction;
  * its last statement (the 'usage.settle' audit row);
  * COMMIT, through a deferred foreign-key violation, so the error comes from the commit itself.

The error is a real PostgreSQL error raised by the server (SQLSTATE 40P01 through RAISE, or a foreign-key violation at
commit), not a Python exception injected around the call, so the transaction is genuinely aborted and rolled back.

Asserted safe outcome: the job is held for reconciliation; its holds, the wallets, the ledger, the receipts and the
document are exactly as they were before settlement; nothing is adopted, delivered, charged or retried. Then the only
way out, the administrator's resolution (POST /console/jobs/<id>/resolve/), releases the holds, charges nothing and
records the provider cost QuillMD's own durable receipt evidences as the platform's cost, whatever the form carried.

Real PostgreSQL; synthetic records; the provider is a fake (no network request).
"""
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.db import connection

from core import billing
from core.jobs import deliverable, enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import (AuditEvent, Encounter, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, User,
                         Wallet)
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import AUDITABLE_RATES, PolicyFixture, STORAGES, fund

HELD = 'Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is resolved.'
DEADLOCK = "DO $$BEGIN RAISE EXCEPTION 'synthetic deadlock victim during settlement' USING ERRCODE = '40P01'; END$$"


def failing_settlement(stage):
    """core.jobs.settle, whose own transaction the DATABASE aborts at `stage`."""
    real = billing.settle
    settling = {}

    def wrapper(execute, sql, params, many, context):
        if stage == 'job lock' and sql.startswith('SELECT') and 'FROM "core_job"' in sql and 'FOR UPDATE' in sql:
            return execute(DEADLOCK, None, many, context)
        if stage == 'usage insert' and sql.startswith('INSERT INTO "core_usage"'):
            return execute(DEADLOCK, None, many, context)
        if stage in ('last statement', 'commit') and sql.startswith('INSERT INTO "core_auditevent"') and 'usage.settle' in (params or ()):
            if stage == 'last statement':
                return execute(DEADLOCK, None, many, context)
            result = execute(sql, params, many, context)
            # A deferred foreign-key violation: checked only when the transaction commits, so COMMIT itself fails.
            with connection.cursor() as cursor:
                cursor.execute('UPDATE core_reservation SET wallet_id=%s WHERE job_id=%s', [uuid.uuid4(), settling['job']])
            return result
        return execute(sql, params, many, context)

    def settle(job, *args, **kwargs):
        settling['job'] = job.pk
        with connection.execute_wrapper(wrapper):
            return real(job, *args, **kwargs)
    return settle


class HeldSettlementFixture(PolicyFixture):
    STAGES = ('job lock', 'usage insert', 'last statement', 'commit')

    def setUp(self):
        super().setUp()
        fund(self.paid, Decimal('5'), 'payment:settlement-db-error')

    def snapshot(self, job):
        encounter = Encounter.objects.get(pk=job.encounter_id)
        return {
            'wallets': sorted((str(w.pk), w.balance, w.reserved) for w in Wallet.objects.all()),
            'reservations': sorted((str(r.pk), str(r.wallet_id), r.amount, r.state) for r in Reservation.objects.filter(job=job)),
            'ledger': sorted((str(e.pk), e.amount) for e in LedgerEntry.objects.all()),
            'document': (json.dumps(encounter.answers, sort_keys=True), encounter.notes, encounter.status, encounter.revision,
                         json.dumps(encounter.template_review, sort_keys=True)),
            'usage': Usage.objects.count(), 'platform_costs': PlatformCost.objects.count(),
        }

    def assert_held_for_reconciliation(self, job, before, error_class, cost=Decimal('0.1')):
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', HELD))
        self.assertNotIn(':failed:', job.request_key)  # not freed: the same request cannot be bought twice meanwhile
        self.assertEqual(self.snapshot(job), before)
        self.assertEqual(ProviderReceipt.objects.get(job=job).actual_cost, cost)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertFalse(PlatformCost.objects.filter(job=job).exists())
        self.assertFalse(deliverable(job))
        event = AuditEvent.objects.get(action='job.reconciliation', target=str(job.pk))
        self.assertEqual((event.details['billing'], event.details['error_class']), ('uncertain', error_class))
        self.assertFalse(AuditEvent.objects.filter(target=str(job.pk), action__in=['usage.settle', 'job.succeeded']).exists())
        report = audit_report()
        self.assertTrue(report['all_checks_pass'])
        self.assertIn(job.pk, [row['id'] for row in report['unresolved_jobs']])
        self.assertIn(job.pk, [row['job_id'] for row in report['unsettled_provider_receipts']])

    def draft(self):
        return Encounter.objects.create(department=self.encounter.department, patient=self.encounter.patient,
                                        template_version=self.encounter.template_version, created_by=self.user,
                                        notes=self.encounter.notes, service_date=self.encounter.service_date)

    def generation_failing_at(self, stage):
        draft = self.draft()
        job = enqueue(draft, self.user)
        before = self.snapshot(job)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_settle_' + stage.replace(' ', '_'))
        with patch('core.jobs.generation.generate', return_value=result) as provider, \
                patch('core.jobs.settle', side_effect=failing_settlement(stage)):
            self.assertTrue(run_one())
            self.assertEqual(provider.call_count, 1)
            # Never retried automatically: the next worker pass finds nothing to send.
            self.assertFalse(run_one())
            self.assertEqual(provider.call_count, 1)
        return job, before


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class SettlementFailsAtTheDatabase(HeldSettlementFixture, TransactionTestCase):
    def test_generation_held_for_reconciliation_at_every_stage(self):
        for stage in self.STAGES:
            with self.subTest(stage=stage):
                job, before = self.generation_failing_at(stage)
                self.assert_held_for_reconciliation(job, before, 'IntegrityError' if stage == 'commit' else 'OperationalError')

    def test_transcription_held_for_reconciliation_and_notes_untouched(self):
        job = Job.objects.create(encounter=self.encounter, user=self.user, kind='transcription', request_key='settle-db-transcription',
                                 config={'mode': 'live', 'charge_limit': '0.5'})
        billing.reserve(job, charge_limit=Decimal('0.5'))
        before = self.snapshot(job)
        outcome = ('Synthetic transcript: no chest pain.', Decimal('0.1'), {'duration_seconds': '12'}, AUDITABLE_RATES,
                   'deepgram:nova-3-medical', 'req_settle_transcription', False)
        with patch('core.jobs.transcribe', return_value=outcome), patch('core.jobs.settle', side_effect=failing_settlement('usage insert')):
            self.assertTrue(run_one())
        self.assert_held_for_reconciliation(job, before, 'OperationalError')

    def test_an_error_after_the_settlement_committed_is_absorbed_never_charged(self):
        """The other shape of a DatabaseError 'from settle()': the settlement committed and the error surfaced afterwards
        (a connection lost with the commit acknowledgement). The usage row exists, so run_one classifies the job as a
        platform failure and absorbs it: the charge is reversed, the provider cost is the platform's, nothing is adopted."""
        from django.db import OperationalError
        promo, paid = Wallet.objects.get(pk=self.promo.pk), Wallet.objects.get(pk=self.paid.pk)
        before_enqueue = {(promo.pk, promo.balance, promo.reserved), (paid.pk, paid.balance, paid.reserved)}
        draft = self.draft()
        job = enqueue(draft, self.user)
        document = self.snapshot(job)['document']

        def committed_then_failed(*args, **kwargs):
            billing.settle(*args, **kwargs)
            raise OperationalError('synthetic: connection lost after the commit was acknowledged')
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_settle_after_commit')
        with patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=committed_then_failed):
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('platform_failure: '), job.error)
        self.assertEqual({(w.pk, w.balance, w.reserved) for w in Wallet.objects.filter(pk__in=[self.promo.pk, self.paid.pk])}, before_enqueue)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Usage.objects.get(job=job).actual_cost)
        self.assertEqual(self.snapshot(job)['document'], document)
        self.assertFalse(deliverable(job))
        self.assertTrue(audit_report()['all_checks_pass'])

    def lose_the_connection_during_settlement(self, reconnect):
        """The server ends the worker's connection at settle's usage insert (pg_terminate_backend, as an operator or a
        database restart would). With `reconnect` False the server stays unreachable for the handler's next query."""
        from core.tests.test_retention_flow_locks import in_thread
        draft = self.draft()
        job = enqueue(draft, self.user)
        before = self.snapshot(job)
        real = billing.settle
        port = connection.settings_dict['PORT']

        def terminated(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "core_usage"'):
                if not reconnect:
                    context['connection'].settings_dict['PORT'] = '1'  # nothing listens there: the next connect fails
                return execute('SELECT pg_terminate_backend(pg_backend_pid())', None, many, context)
            return execute(sql, params, many, context)

        def settle(*args, **kwargs):
            with connection.execute_wrapper(terminated):
                return real(*args, **kwargs)
        result = adopted_live_result(draft.notes, draft.template_version.fields, f'req_settle_connection_{reconnect}')
        try:
            with patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=settle):
                thread, outcome = in_thread(run_one)
                thread.join(60)
        finally:
            connection.settings_dict['PORT'] = port
        self.assertFalse(thread.is_alive())
        return job, before, outcome

    def test_a_connection_terminated_during_settlement_is_held_for_reconciliation(self):
        """Django closes the broken connection when its rollback fails and the handler reconnects: the same outcome."""
        job, before, outcome = self.lose_the_connection_during_settlement(reconnect=True)
        self.assertEqual(outcome, {'value': True})
        self.assert_held_for_reconciliation(job, before, 'OperationalError')

    def test_an_unreachable_database_after_the_termination_waits_for_the_stale_sweep(self):
        """The handler cannot even read the usage table, so the exception leaves run_one (the worker process exits;
        systemd Restart=on-failure restarts it) with the job still 'running' and everything else untouched. The stale sweep
        then holds it for reconciliation: nothing was charged, adopted or released."""
        from core.jobs import mark_stale
        job, before, outcome = self.lose_the_connection_during_settlement(reconnect=False)
        self.assertIn('error', outcome)
        self.assertIn(type(outcome['error']).__name__, ('InterfaceError', 'OperationalError'))
        job.refresh_from_db()
        self.assertEqual(job.state, 'running')
        self.assertEqual(self.snapshot(job), before)
        self.assertTrue(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
        mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation')
        self.assertEqual(self.snapshot(job), before)
        self.assertFalse(deliverable(job))


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class ResolvingASettlementHeldByADatabaseError(HeldSettlementFixture, TransactionTestCase):
    """The administrator's resolution of the state above. RED on 8e3dcfd0: the resolution ignored the durable receipt, so
    'release_no_cost' recorded 'no provider cost evidenced' and no platform cost for a request QuillMD's own receipt shows the
    provider completed and metered, and 'absorb_platform_failure' recorded whatever amount was typed. The batch resolution
    (core.batch_jobs.resolve_view) and the settled-usage branch of this one already treat the durable record as authoritative."""

    def console(self):
        admin = User.objects.create_user(username='resolver@synthetic.invalid', email='resolver@synthetic.invalid',
                                         verified_at=timezone.now(), is_staff=True)
        device = TOTPDevice.objects.create(user=admin, name='Synthetic authenticator', confirmed=True)
        client = Client()
        client.force_login(admin)
        session = client.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        return admin, client

    def resolve(self, form):
        promo, paid = Wallet.objects.get(pk=self.promo.pk), Wallet.objects.get(pk=self.paid.pk)
        before_enqueue = {(promo.pk, promo.balance, promo.reserved), (paid.pk, paid.balance, paid.reserved)}
        job, before = self.generation_failing_at('usage insert')
        document = before['document']
        admin, console = self.console()
        response = console.post(f'/console/jobs/{job.pk}/resolve/', form)
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertIn(':failed:', job.request_key)
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'released'})
        # Nothing charged: both wallets are exactly as they were before the request was queued.
        self.assertEqual({(w.pk, w.balance, w.reserved) for w in Wallet.objects.filter(pk__in=[self.promo.pk, self.paid.pk])}, before_enqueue)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertEqual(self.snapshot(job)['document'], document)
        self.assertFalse(deliverable(job))
        receipt = ProviderReceipt.objects.get(job=job)
        cost = PlatformCost.objects.get(job=job, kind='absorbed_failure')
        self.assertEqual(cost.amount, receipt.actual_cost)
        self.assertTrue(cost.evidence_reference.startswith(f'receipt:{receipt.pk} '), cost.evidence_reference)
        self.assertEqual(cost.recorded_by, admin)
        self.assertNotIn('no provider cost', job.error)
        report = audit_report()
        self.assertTrue(report['all_checks_pass'])
        self.assertEqual(report['unresolved_jobs'], [])
        self.assertEqual(Decimal(report['platform_costs']['totals_by_kind']['absorbed_failure']), receipt.actual_cost)
        return job

    def test_release_records_the_receipts_cost_as_the_platforms(self):
        self.resolve({'outcome': 'release_no_cost', 'evidence_note': 'Provider console lookup for the stored request id'})

    def test_absorb_records_the_receipts_cost_whatever_the_form_carried(self):
        self.resolve({'outcome': 'absorb_platform_failure', 'actual_cost': '0.05',
                      'evidence_note': 'Provider console lookup for the stored request id'})
