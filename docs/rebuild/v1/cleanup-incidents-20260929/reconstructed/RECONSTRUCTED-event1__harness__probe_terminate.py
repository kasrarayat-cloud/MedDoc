from unittest.mock import patch
from django.db import connection
from django.test import TransactionTestCase, override_settings
from core import billing
from core.jobs import enqueue, run_one
from core.models import AuditEvent, Job, ProviderReceipt, Usage, Reservation
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import STORAGES
from core.tests.test_settlement_database_error import HeldSettlementFixture
from core.tests.test_retention_flow_locks import in_thread

@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class Probe(HeldSettlementFixture, TransactionTestCase):
    def test_probe(self):
        draft = self.draft(); job = enqueue(draft, self.user); before = self.snapshot(job)
        real = billing.settle
        seen = []
        def terminated(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "core_usage"'):
                try:
                    return execute('SELECT pg_terminate_backend(pg_backend_pid())', None, many, context)
                except Exception as e:
                    seen.append(repr(e)[:200]); raise
            return execute(sql, params, many, context)
        def settle(*a, **k):
            with connection.execute_wrapper(terminated):
                return real(*a, **k)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_probe')
        with patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=settle):
            thread, outcome = in_thread(run_one); thread.join(60)
        job.refresh_from_db()
        print('\nPROBE outcome', outcome)
        print('PROBE seen', seen)
        print('PROBE job', job.state, '|', job.error)
        print('PROBE audit', list(AuditEvent.objects.filter(target=str(job.pk)).values_list('action', 'details')))
        print('PROBE unchanged', self.snapshot(job) == before, 'receipt', ProviderReceipt.objects.filter(job=job).exists(), 'usage', Usage.objects.filter(job=job).exists())
