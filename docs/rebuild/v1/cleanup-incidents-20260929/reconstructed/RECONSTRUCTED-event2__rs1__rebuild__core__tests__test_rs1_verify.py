"""RS-1 independent reproduction: settle()'s COMMIT waits at the deferred FK check for an account lock, the worker's
socket drops while it waits, and the server finishes the commit after the lock is released.

Scratch copy only. Synthetic records; the provider is a fake; no network.
"""
import json
import os
import socket
import threading
import time
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import billing
from core.jobs import deliverable, enqueue, public_error, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, User, Wallet
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import STORAGES
from core.tests.test_retention_flow_locks import in_thread
from core.tests.test_settlement_database_error import HELD, HeldSettlementFixture

OUT = os.environ.get('RS1_OUT', '/dev/null')


def wait_for(predicate, timeout=20, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class InDoubtSettlementCommit(HeldSettlementFixture, TransactionTestCase):

    def activity(self, pid):
        with connection.cursor() as cursor:
            cursor.execute('SELECT state, wait_event_type, wait_event, query FROM pg_stat_activity WHERE pid=%s', [pid])
            return cursor.fetchone()

    def usage_visible(self, job_pk):
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM core_usage WHERE job_id=%s', [job_pk])
            return cursor.fetchone()[0]

    def waiting_job_updates(self, exclude_pid):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pid, wait_event_type, left(query,80) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND pid<>%s "
                           "AND wait_event_type='Lock' AND query LIKE 'UPDATE \"core_job\"%%'", [exclude_pid])
            return cursor.fetchall()

    def wallets(self):
        return {w.kind: (str(w.balance), str(w.reserved)) for w in Wallet.objects.filter(pk__in=[self.promo.pk, self.paid.pk])}

    def run_case(self, drop, label):
        with connection.cursor() as cursor:
            cursor.execute('SHOW client_connection_check_interval')
            check_interval = cursor.fetchone()[0]
        wallets_before_enqueue = self.wallets()
        draft = self.draft()
        job = enqueue(draft, self.user)
        before = self.snapshot(job)
        wallets_after_enqueue = self.wallets()
        user_pk = self.user.pk
        state = {}
        timeline = []
        blocker_ready, release_blocker = threading.Event(), threading.Event()
        t0 = time.monotonic()

        def mark(what):
            timeline.append((round(time.monotonic() - t0, 4), what))

        def blocker():
            try:
                with transaction.atomic():
                    User.objects.select_for_update().get(pk=user_pk)  # as admin_account / recovery completion lock the account
                    mark('blocker holds User FOR UPDATE')
                    blocker_ready.set()
                    release_blocker.wait(60)
                mark('blocker committed (account lock released)')
            finally:
                connections.close_all()

        def hook(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('INSERT INTO "core_auditevent"') and 'usage.settle' in (params or ()):
                mark('settle executed its last statement (usage.settle audit)')
                thread = threading.Thread(target=blocker, daemon=True)
                thread.start()
                state['blocker'] = thread
                assert blocker_ready.wait(15)
            return result

        real = billing.settle

        def settle(job_arg, *args, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()')
                state['pid'] = cursor.fetchone()[0]
            state['fd'] = connection.connection.fileno()
            try:
                with connection.execute_wrapper(hook):
                    value = real(job_arg, *args, **kwargs)
                mark('settle returned normally')
                return value
            except BaseException as error:
                mark(f'settle raised {type(error).__name__}: {str(error)[:120]}')
                raise

        def logger(execute, sql, params, many, context):
            if 'FROM "core_usage"' in sql and sql.startswith('SELECT'):
                mark('handler/worker reads core_usage (known=...exists())')
            if sql.startswith('UPDATE "core_job"'):
                mark('worker UPDATE core_job issued: ' + sql[:60])
            result = execute(sql, params, many, context)
            if sql.startswith('UPDATE "core_job"'):
                mark('worker UPDATE core_job returned')
            return result

        def worker():
            with connection.execute_wrapper(logger):
                return run_one()

        result = adopted_live_result(draft.notes, draft.template_version.fields, f'req_rs1_{label}')
        with patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=settle):
            thread, outcome = in_thread(worker)
            assert wait_for(lambda: 'pid' in state and blocker_ready.is_set()), 'blocker never took the account lock'
            waiting = wait_for(lambda: (a := self.activity(state['pid'])) and a[1] == 'Lock' and a[3].strip().upper() == 'COMMIT' and a)
            mark(f'worker backend {state["pid"]} waiting: {waiting}')
            with connection.cursor() as cursor:
                cursor.execute('SELECT locktype, mode, granted FROM pg_locks WHERE pid=%s AND NOT granted', [state['pid']])
                waited_locks = cursor.fetchall()
            if drop:
                sock = socket.socket(fileno=os.dup(state['fd']))
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                mark('SHUT_RDWR on the worker libpq socket')
            samples = []
            end = time.monotonic() + 1.5
            while time.monotonic() < end:
                samples.append({'t': round(time.monotonic() - t0, 3), 'usage_visible': self.usage_visible(job.pk),
                                'old_backend': self.activity(state['pid']),
                                'job_updates_waiting': self.waiting_job_updates(state['pid'])})
                time.sleep(0.25)
            release_blocker.set()
            mark('release_blocker set')
            thread.join(60)
            state['blocker'].join(30)
        self.assertFalse(thread.is_alive())
        job.refresh_from_db()
        usage = Usage.objects.filter(job=job).first()
        report = audit_report()
        record = {
            'label': label, 'drop': drop, 'client_connection_check_interval': check_interval,
            'run_one_outcome': {k: (repr(v) if k == 'error' else v) for k, v in outcome.items()},
            'waited_locks_at_commit': waited_locks,
            'timeline': timeline, 'samples': samples,
            'job_state': job.state, 'job_error': job.error, 'public_error': public_error(job),
            'request_key_freed': ':failed:' in (job.request_key or ''),
            'usage': {'exists': bool(usage), 'charged_cost': str(usage.charged_cost) if usage else None,
                      'actual_cost': str(usage.actual_cost) if usage else None},
            'reservations': sorted(Reservation.objects.filter(job=job).values_list('state', flat=True)),
            'ledger_for_job': sorted((e.kind, str(e.amount)) for e in LedgerEntry.objects.filter(job=job)),
            'wallets_before_enqueue': wallets_before_enqueue, 'wallets_after_enqueue': wallets_after_enqueue,
            'wallets_now': self.wallets(),
            'snapshot_equals_before_settlement': self.snapshot(job) == before,
            'receipt': bool(ProviderReceipt.objects.filter(job=job).exists()),
            'platform_costs': sorted((p.kind, str(p.amount)) for p in PlatformCost.objects.filter(job=job)),
            'audit': [(e.action, e.details.get('billing'), e.details.get('charged'), e.details.get('error_class'))
                      for e in AuditEvent.objects.filter(target=str(job.pk)).order_by('created_at', 'pk')],
            'deliverable': deliverable(job),
            'audit_all_checks_pass': report['all_checks_pass'],
            'in_unresolved_jobs': job.pk in [row['id'] for row in report['unresolved_jobs']],
            'in_unsettled_receipts': job.pk in [row['job_id'] for row in report['unsettled_provider_receipts']],
        }
        return job, record

    def resolve(self, job):
        admin = User.objects.create_user(username=f'resolver{job.pk}@synthetic.invalid', email=f'resolver{job.pk}@synthetic.invalid',
                                         verified_at=timezone.now(), is_staff=True)
        device = TOTPDevice.objects.create(user=admin, name='Synthetic authenticator', confirmed=True)
        client = Client()
        client.force_login(admin)
        session = client.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        response = client.post(f'/console/jobs/{job.pk}/resolve/', {'outcome': 'release_no_cost', 'evidence_note': 'Synthetic lookup'})
        job.refresh_from_db()
        return {'status': response.status_code, 'job_state': job.state, 'job_error': job.error,
                'wallets_now': self.wallets(),
                'platform_costs': sorted((p.kind, str(p.amount)) for p in PlatformCost.objects.filter(job=job)),
                'ledger_for_job': sorted((e.kind, str(e.amount)) for e in LedgerEntry.objects.filter(job=job)),
                'audit_all_checks_pass': audit_report()['all_checks_pass']}

    def test_in_doubt_commit(self):
        records = []
        for i in range(3):
            job, record = self.run_case(drop=True, label=f'drop{i}')
            if job.state == 'reconciliation':
                record['resolution'] = self.resolve(job)
            records.append(record)
        job, record = self.run_case(drop=False, label='control')
        records.append(record)
        with open(OUT, 'w') as handle:
            json.dump(records, handle, indent=1, default=str)
