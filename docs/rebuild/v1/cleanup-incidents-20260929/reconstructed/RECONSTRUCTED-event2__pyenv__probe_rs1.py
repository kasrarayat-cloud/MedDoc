"""Evidence probe (not committed): what the worker records when settle()'s COMMIT lands after its answer is lost."""
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from core import billing
from core.jobs import enqueue, run_one
from core.models import AuditEvent, LedgerEntry, Reservation, Usage
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import STORAGES
from core.tests.test_settlement_database_error import HeldSettlementFixture
from core.tests.test_settlement_outcome_unknown import CommitAnswerLost


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class ProbeRS1(HeldSettlementFixture, TransactionTestCase):
    def test_probe(self):
        draft = self.draft()
        job = enqueue(draft, self.user)
        harness = CommitAnswerLost(landed=True)
        real = billing.settle
        def settle(*a, **k):
            harness.arm(); return real(*a, **k)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_probe_rs1')
        with harness.patched(), patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=settle):
            run_one(); harness.join(self)
        job.refresh_from_db()
        print('\nPROBE state:', job.state)
        print('PROBE error:', job.error)
        print('PROBE handler waited for the in-flight commit:', harness.waiter_seen)
        print('PROBE usage row exists:', Usage.objects.filter(job=job).exists())
        print('PROBE usage ledger debits:', sorted(str(e.amount) for e in LedgerEntry.objects.filter(job=job, kind='usage')))
        print('PROBE reservations:', sorted(Reservation.objects.filter(job=job).values_list('state', flat=True)))
        print('PROBE audit billing:', AuditEvent.objects.get(action='job.reconciliation', target=str(job.pk)).details['billing'])
