"""Provider-free classification checks; amounts retain the existing ledger policy."""
import json
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from core.billing import reconcile_usage
from core.forms import ReconciliationForm
from core.management.commands.audit_billing import audit_report
from core.models import CostReconciliation, LedgerEntry, Usage
from core.tests.test_billing_policy import PolicyFixture, STORAGES


class EvidenceTypeForm(SimpleTestCase):
    def test_administrator_must_classify_new_evidence_explicitly(self):
        base={'reconciled_cost':'0.5','evidence_reference':'SYNTHETIC-REPORT'}
        for kind in [None, '', 'unclassified', 'other']:
            data=dict(base)
            if kind is not None:data['evidence_kind']=kind
            self.assertFalse(ReconciliationForm(data).is_valid())
        for kind in ['provider_report','invoice']:
            self.assertTrue(ReconciliationForm(dict(base,evidence_kind=kind)).is_valid())


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class EvidenceClassification(PolicyFixture,TestCase):
    def record(self,kind=None,reference='INV-LOOKING-SYNTHETIC-EXPORT'):
        usage=self.settled(Decimal('0.5'))
        arguments={} if kind is None else {'evidence_kind':kind}
        row=reconcile_usage(usage,Decimal('0.5'),reference,self.user,**arguments)
        return Usage.objects.get(pk=usage.pk),row,audit_report()

    def test_provider_report_is_not_relabelled_as_an_invoice(self):
        usage,row,report=self.record('provider_report')
        self.assertTrue(report['all_checks_pass'])
        self.assertTrue(report['rows'][0]['provider_evidence_reconciled'])
        self.assertFalse(report['rows'][0]['invoice_reconciled'])
        self.assertEqual(report['rows'][0]['reconciliation']['evidence_kind'],'provider_report')
        self.assertEqual(report['invoice_reconciliation']['invoice_rows'],0)
        self.assertEqual(report['invoice_reconciliation']['provider_report_rows'],1)
        self.assertIn('not invoice reconciled',usage.invoice_status)
        self.client.force_login(self.user)
        for url in ['/billing/',f'/billing/jobs/{usage.job_id}/']:
            page=self.client.get(url)
            self.assertContains(page,'Provider-reported actual')
            self.assertContains(page,'not invoice reconciled')
            self.assertNotContains(page,'Invoice-reconciled actual')

    def test_invoice_is_counted_only_with_explicit_classification(self):
        usage,row,report=self.record('invoice',reference='SYNTHETIC-PROVIDER-INVOICE')
        self.assertTrue(report['all_checks_pass'])
        self.assertTrue(report['rows'][0]['invoice_reconciled'])
        self.assertTrue(report['rows'][0]['provider_evidence_reconciled'])
        self.assertEqual(report['invoice_reconciliation']['invoice_rows'],1)
        self.assertEqual(report['invoice_reconciliation']['provider_report_rows'],0)
        self.assertIn('Invoice-reconciled actual',usage.invoice_status)
        self.assertIn('no account-wide or whole-invoice reconciliation',report['invoice_reconciliation']['scope'])

    def test_legacy_api_default_preserves_unknown_status_and_money(self):
        usage,row,report=self.record()
        self.assertEqual(row.evidence_kind,'unclassified')
        self.assertTrue(report['rows'][0]['reconciliation_recorded'])
        self.assertFalse(report['rows'][0]['provider_evidence_reconciled'])
        self.assertFalse(report['rows'][0]['invoice_reconciled'])
        self.assertEqual(report['invoice_reconciliation']['unclassified_rows'],1)
        self.assertIn('invoice status unknown',usage.invoice_status)
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('0')))
        self.assertEqual(usage.actual_cost,Decimal('0.5'))
        self.assertEqual(usage.charged_cost,Decimal('0.75'))

    def test_unknown_kind_is_refused_before_any_adjustment(self):
        usage=self.settled(Decimal('0.5'))
        before=list(LedgerEntry.objects.values_list('pk','amount'))
        with self.assertRaises(ValidationError):
            reconcile_usage(usage,Decimal('0.4'),'SYNTHETIC',self.user,evidence_kind='unknown')
        self.assertFalse(CostReconciliation.objects.exists())
        self.assertEqual(before,list(LedgerEntry.objects.values_list('pk','amount')))

    def test_recorded_classification_cannot_be_rewritten(self):
        usage,row,report=self.record('provider_report')
        with self.assertRaises(DatabaseError),transaction.atomic():
            CostReconciliation.objects.filter(pk=row.pk).update(evidence_kind='invoice')
        row.refresh_from_db()
        self.assertEqual(row.evidence_kind,'provider_report')
        self.assertEqual(row.evidence_reference,'INV-LOOKING-SYNTHETIC-EXPORT')

    def test_duplicate_or_corrected_evidence_does_not_apply_again(self):
        usage,row,report=self.record('provider_report')
        before=list(LedgerEntry.objects.values_list('pk','amount'))
        for amount,reference,kind in [('0.5',row.evidence_reference,'provider_report'),('0.4','SYNTHETIC-CORRECTED','invoice')]:
            with self.assertRaises(ValidationError):
                reconcile_usage(usage,Decimal(amount),reference,self.user,evidence_kind=kind)
        self.assertEqual(CostReconciliation.objects.count(),1)
        self.assertEqual(before,list(LedgerEntry.objects.values_list('pk','amount')))

    def test_database_refuses_unsupported_kind(self):
        usage=self.settled(Decimal('0.5'))
        with self.assertRaises(IntegrityError),transaction.atomic():
            CostReconciliation.objects.create(usage=usage,reconciled_cost=Decimal('0.5'),
                evidence_reference='SYNTHETIC',recorded_by=self.user,charge_delta=0,
                ledger_status='applied',evidence_kind='unsupported')
        self.assertFalse(CostReconciliation.objects.exists())


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class EvidenceKindMigration(PolicyFixture,TransactionTestCase):
    def test_existing_evidence_is_preserved_as_unclassified(self):
        usage=self.settled(Decimal('0.5'))
        row=reconcile_usage(usage,Decimal('0.4'),'INV-LEGACY-UNCLASSIFIED',self.user)
        ledger_before=list(LedgerEntry.objects.order_by('pk').values_list('pk','amount','kind','key','balance_after'))
        before_target=[('core','0016_user_session_version')]
        after_target=[('core','0017_reconciliation_evidence_kind')]
        try:
            MigrationExecutor(connection).migrate(before_target)
            with connection.cursor() as cursor:
                cursor.execute('SELECT to_jsonb(r) FROM core_costreconciliation r WHERE id=%s',[row.pk])
                before=cursor.fetchone()[0]
                if isinstance(before,str):before=json.loads(before)
            self.assertNotIn('evidence_kind',before)
            MigrationExecutor(connection).migrate(after_target)
            with connection.cursor() as cursor:
                cursor.execute('SELECT to_jsonb(r) FROM core_costreconciliation r WHERE id=%s',[row.pk])
                after=cursor.fetchone()[0]
                if isinstance(after,str):after=json.loads(after)
            self.assertEqual(after.pop('evidence_kind'),'unclassified')
            self.assertEqual(after,before)
            self.assertEqual(ledger_before,list(LedgerEntry.objects.order_by('pk').values_list('pk','amount','kind','key','balance_after')))
            self.assertFalse(Usage.objects.get(pk=usage.pk).reconciliation.invoice_reconciled)
        finally:
            # Back to the WHOLE schema, not just 0017: stopping at 0017 left every later migration's tables and
            # columns missing for the TransactionTestCases that run after this one (Payment.livemode, 0020, made
            # it visible in test_worker_financial_reliability).
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
