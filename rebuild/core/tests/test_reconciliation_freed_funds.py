"""Synthetic funded-ledger regressions; no external payment or provider calls."""
from decimal import Decimal

from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings

from core import billing
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Job, LedgerEntry, Reservation
from core.tests.test_billing_policy import AUDITABLE_RATES, PolicyFixture, STORAGES, fund


class FreedFundsFixture(PolicyFixture):
    def waiting_adjustment(self, held=False):
        fund(self.paid, Decimal('3'), 'payment:freed-funds')
        usage = self.settled(Decimal('7'), maximum=Decimal('8'), key='waiting-usage')
        if held:
            second = Job.objects.create(encounter=self.encounter, user=self.user, request_key='held-usage')
            billing.reserve(second, charge_limit=Decimal('2'))
        else:
            second = self.settled(Decimal('1'), key='credited-usage')
        row = billing.reconcile_usage(usage, Decimal('8'), 'SYNTHETIC-PENDING', self.user)
        self.assertEqual(row.ledger_status, 'pending_funds')
        self.assertEqual(row.charge_delta, Decimal('1.5'))
        return row, second

    def complete(self, job):
        usage = billing.settle(job, Decimal('0.2'),
                               {'input_tokens': 200, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0},
                               AUDITABLE_RATES, 'anthropic:synthetic-model', 'req_freed', provider_resource_id='msg_freed')
        job.state = 'succeeded'
        job.save(update_fields=['state'])
        return usage


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ReconciliationFreedFunds(FreedFundsFixture, TestCase):
    def assert_applied_once(self, row, expected_paid):
        row.refresh_from_db()
        self.assertEqual(row.ledger_status, 'applied')
        self.assertEqual(self.balances(), (Decimal('0'), expected_paid))
        self.assertEqual(LedgerEntry.objects.filter(job=row.usage.job, kind='reconciliation').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='usage.reconciliation_applied', target=str(row.usage.job_id)).count(), 1)
        self.assertEqual(billing.apply_pending_reconciliations(wallet=self.paid), [])
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_successful_settlement_resumes_adjustment_using_unused_paid_hold(self):
        row, job = self.waiting_adjustment(held=True)
        with self.captureOnCommitCallbacks(execute=True):
            usage = self.complete(job)
        self.assertEqual(usage.charged_cost, Decimal('0.3'))
        self.assert_applied_once(row, Decimal('0.7'))

    def test_provider_credit_back_resumes_an_earlier_adjustment(self):
        row, usage = self.waiting_adjustment()
        with self.captureOnCommitCallbacks(execute=True):
            billing.reconcile_usage(usage, Decimal('0.5'), 'SYNTHETIC-CREDIT-BACK', self.user)
        self.assert_applied_once(row, Decimal('0.25'))

    def test_platform_failure_reversal_resumes_an_earlier_adjustment(self):
        row, usage = self.waiting_adjustment()
        job = usage.job
        job.state = 'failed'
        job.error = 'platform_failure: synthetic failure'
        job.save(update_fields=['state', 'error'])
        with self.captureOnCommitCallbacks(execute=True):
            billing.absorb_failed_job(job)
        self.assert_applied_once(row, Decimal('1'))


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class FreedFundsCommitBoundary(FreedFundsFixture, TransactionTestCase):
    def test_outer_rollback_does_not_apply_adjustment_or_release_settlement_hold(self):
        row, job = self.waiting_adjustment(held=True)
        with self.assertRaisesRegex(RuntimeError, 'synthetic rollback'):
            with transaction.atomic():
                self.complete(job)
                row.refresh_from_db()
                self.assertEqual(row.ledger_status, 'pending_funds')
                raise RuntimeError('synthetic rollback')
        row.refresh_from_db()
        self.assertEqual(row.ledger_status, 'pending_funds')
        self.assertEqual(self.balances(), (Decimal('0'), Decimal('2.5')))
        self.assertEqual(Reservation.objects.get(job=job).state, 'held')
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertTrue(audit_report()['all_checks_pass'])
