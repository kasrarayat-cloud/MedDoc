"""Isolated worker and ledger failure boundaries. No external provider calls."""
import threading
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import billing
from core.jobs import enqueue, mark_stale, run_one
from core.models import AuditEvent, CostReconciliation, Job, LedgerEntry, Payment, PlatformCost, ProviderReceipt, Reservation, Usage
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import PolicyFixture, STORAGES, fund


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ReconciliationWalletLockOrder(PolicyFixture, TransactionTestCase):
    def test_payment_and_absorption_complete_without_a_deadlock(self):
        self.race_absorption('payment')

    def test_release_and_absorption_complete_without_a_deadlock(self):
        self.race_absorption('release')

    def race_absorption(self, trigger):
        fund(self.paid, Decimal('2'), 'payment:synthetic-initial')
        usage = self.settled(Decimal('7'), maximum=Decimal('8'))
        blocker = Job.objects.create(encounter=self.encounter, user=self.user, request_key='synthetic-blocker')
        billing.reserve(blocker, charge_limit=Decimal('1'))
        row = billing.reconcile_usage(usage, Decimal('8'), 'SYNTHETIC-LOCK-ORDER', self.user)
        self.assertEqual(row.ledger_status, 'pending_funds')
        job = usage.job
        job.state = 'failed'
        job.error = 'platform_failure: synthetic post-settlement interruption'
        job.save(update_fields=['state', 'error'])
        payment = Payment.objects.create(user=self.user, wallet=self.paid, amount_cents=100,
                                         stripe_session='cs_test_lock_order')
        session = {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd',
                   'amount_total': 100, 'metadata': {'payment_id': str(payment.pk)},
                   'payment_intent': 'pi_test_lock_order', 'mode': 'payment'}
        applying = threading.Event()
        job_locked = threading.Event()
        original_apply = billing.apply_pending_reconciliations
        outcomes = {}

        def apply_after_job_is_locked(*args, **kwargs):
            applying.set()
            if not job_locked.wait(10):
                raise AssertionError('Absorption did not acquire its job lock')
            return original_apply(*args, **kwargs)

        def absorb():
            if not applying.wait(10):
                raise AssertionError('Payment did not reach pending reconciliation')
            with transaction.atomic():
                Job.objects.select_for_update().get(pk=job.pk)
                job_locked.set()
                billing.absorb_failed_job(job)

        def run(name, operation):
            close_old_connections()
            try:
                operation()
            except BaseException as error:
                outcomes[name] = (type(error).__name__, str(error))
            finally:
                connections.close_all()

        with patch('core.billing.apply_pending_reconciliations', side_effect=apply_after_job_is_locked):
            operation = (lambda: billing.credit_payment(payment, session)) if trigger == 'payment' else (lambda: billing.release(blocker))
            threads = [threading.Thread(target=run, args=(trigger, operation)),
                       threading.Thread(target=run, args=('absorption', absorb))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(15)
        self.assertTrue(all(not thread.is_alive() for thread in threads), 'Concurrent operations did not finish')
        self.assertEqual(outcomes, {})
        self.assertFalse(AuditEvent.objects.filter(action='usage.reconciliation_apply_failed').exists(),
                         'A database deadlock was swallowed and recorded as reconciliation failure')
        row.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(row.ledger_status, 'absorbed')
        self.assertEqual(payment.status, 'paid' if trigger == 'payment' else 'pending')
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('3') if trigger == 'payment' else Decimal('2')))
        self.assertEqual(LedgerEntry.objects.filter(kind='payment').count(), 2 if trigger == 'payment' else 1)
        self.assertEqual(LedgerEntry.objects.filter(kind='absorbed').count(), 2)
        self.assertEqual(PlatformCost.objects.filter(kind='absorbed_failure').count(), 1)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ReconciliationAfterCommit(PolicyFixture, TransactionTestCase):
    def setup_payment(self):
        usage = self.settled(Decimal('0.5'), maximum=Decimal('1'))
        row = billing.reconcile_usage(usage, Decimal('1'), 'SYNTHETIC-COMMIT', self.user)
        payment = Payment.objects.create(user=self.user, wallet=self.paid, amount_cents=100,
                                         stripe_session='cs_test_commit')
        session = {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd',
                   'amount_total': 100, 'metadata': {'payment_id': str(payment.pk)},
                   'payment_intent': 'pi_test_commit', 'mode': 'payment'}
        return row, payment, session

    def test_outer_rollback_discards_pending_application_and_payment(self):
        row, payment, session = self.setup_payment()
        with patch('core.billing.apply_pending_reconciliations') as pending:
            with self.assertRaisesRegex(RuntimeError, 'synthetic rollback'):
                with transaction.atomic():
                    billing.credit_payment(payment, session)
                    pending.assert_not_called()
                    raise RuntimeError('synthetic rollback')
            pending.assert_not_called()
        payment.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(row.ledger_status, 'pending_funds')
        self.assertFalse(LedgerEntry.objects.filter(kind__in=['payment', 'reconciliation']).exists())
        self.assertEqual(self.balances(), (Decimal('9.25'), Decimal('0')))

    def test_callback_observes_durable_payment_and_failure_stays_pending(self):
        row, payment, session = self.setup_payment()
        original = billing.apply_pending_reconciliations
        observed = []

        def after_commit(*args, **kwargs):
            observed.append((connection.in_atomic_block, Payment.objects.get(pk=payment.pk).status))
            return original(*args, **kwargs)

        with patch('core.billing.apply_pending_reconciliations', side_effect=after_commit), \
                patch('core.billing.apply_additional_debit', side_effect=ValidationError('Synthetic temporary failure')):
            with transaction.atomic():
                billing.credit_payment(payment, session)
                self.assertEqual(observed, [])
        self.assertEqual(observed, [(False, 'paid')])
        row.refresh_from_db()
        self.assertEqual(row.ledger_status, 'pending_funds')
        self.assertEqual(self.balances(), (Decimal('9.25'), Decimal('1')))
        self.assertEqual(AuditEvent.objects.filter(action='usage.reconciliation_apply_failed').count(), 1)
        self.assertEqual([r.pk for r in billing.apply_pending_reconciliations(wallet=self.paid)], [row.pk])
        self.assertEqual(billing.apply_pending_reconciliations(wallet=self.paid), [])
        self.assertEqual(self.balances(), (Decimal('9.25'), Decimal('0.25')))
        self.assertEqual(LedgerEntry.objects.filter(kind='payment').count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(kind='reconciliation').count(), 1)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class InterruptedWorkerEvidence(PolicyFixture, TestCase):
    """BaseException models process interruption, not a live worker SIGKILL test."""

    def interruption(self, boundary, expected_receipts, expected_usage, expected_held):
        job = enqueue(self.encounter, self.user)
        result = adopted_live_result(self.encounter.notes, self.encounter.template_version.fields,
                                     'req_interrupted_' + boundary, Decimal('0.1'))
        provider_patch = patch('core.jobs.generation.generate', return_value=result)
        point = {'before_response': 'core.jobs.generation.generate',
                 'after_receipt': 'core.jobs.private_path',
                 'after_settlement': 'core.jobs.generation.validated'}[boundary]
        with provider_patch, patch(point, side_effect=SystemExit('synthetic interruption')):
            with self.assertRaises(SystemExit):
                run_one()
        job.refresh_from_db()
        self.assertEqual(job.state, 'running')
        self.assertEqual(ProviderReceipt.objects.filter(job=job).count(), expected_receipts)
        self.assertEqual(Usage.objects.filter(job=job).count(), expected_usage)
        self.assertEqual(Reservation.objects.filter(job=job, state='held').exists(), expected_held)
        before = list(LedgerEntry.objects.order_by('pk').values_list('pk', 'amount'))
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
        mark_stale()
        mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation')
        self.assertEqual(AuditEvent.objects.filter(action='job.reconciliation', target=str(job.pk)).count(), 1)
        with patch('core.jobs.generation.generate') as provider:
            self.assertFalse(run_one())
            provider.assert_not_called()
        self.assertEqual(list(LedgerEntry.objects.order_by('pk').values_list('pk', 'amount')), before)
        self.assertEqual(Reservation.objects.filter(job=job, state='held').exists(), expected_held)

    def test_interruption_before_response_keeps_hold_without_automatic_retry(self):
        self.interruption('before_response', 0, 0, True)

    def test_interruption_after_receipt_keeps_provider_evidence_and_hold(self):
        self.interruption('after_receipt', 1, 0, True)

    def test_interruption_after_settlement_does_not_charge_or_release_again(self):
        self.interruption('after_settlement', 1, 1, False)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ReconciliationEvidenceImmutability(PolicyFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.usage = self.settled(Decimal('0.5'), maximum=Decimal('1'))
        self.row = billing.reconcile_usage(self.usage, Decimal('0.4'), 'SYNTHETIC-IMMUTABILITY', self.user)

    def test_queryset_cannot_rewrite_recorded_provider_evidence(self):
        for change in [{'evidence_reference': 'REPLACED'}, {'reconciled_cost': Decimal('0.3')},
                       {'evidence_sha256': 'a' * 64}, {'note': 'Rewritten history'},
                       {'provider_credit_applied': Decimal('1')}, {'discount_applied': Decimal('1')},
                       {'charge_delta': Decimal('0')}, {'over_limit_delta': Decimal('1')},
                       {'created_at': timezone.now()}]:
            with self.subTest(change=change), self.assertRaises(DatabaseError), transaction.atomic():
                CostReconciliation.objects.filter(pk=self.row.pk).update(**change)
        self.row.refresh_from_db()
        self.assertEqual(self.row.evidence_reference, 'SYNTHETIC-IMMUTABILITY')
        self.assertEqual(self.row.reconciled_cost, Decimal('0.4'))

    def test_queryset_cannot_delete_recorded_provider_evidence(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            CostReconciliation.objects.filter(pk=self.row.pk).delete()
        self.assertTrue(CostReconciliation.objects.filter(pk=self.row.pk).exists())

    def test_existing_ledger_status_update_remains_allowed(self):
        self.row.ledger_status = 'absorbed'
        self.row.save(update_fields=['ledger_status'])
        self.row.refresh_from_db()
        self.assertEqual(self.row.ledger_status, 'absorbed')
        self.assertEqual(self.row.evidence_reference, 'SYNTHETIC-IMMUTABILITY')
