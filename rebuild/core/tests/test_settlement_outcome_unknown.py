"""What the worker records after a failure whose end it cannot see: RS-1, RS-2, RS-3, RS-5 and the adoption's commit.

A refutation of the residuals assessment (docs/rebuild/v1/residuals-assessment-20260929.md) found:

  * RS-1 (MEDIUM): settle()'s COMMIT is sent and its answer is lost (the connection dies with the COMMIT in flight). The
    handler reconnected, read Usage.exists() before the in-flight commit was visible, and recorded 'reconciliation' with
    "... nothing is charged until it is resolved" while the charge committed a moment later.
  * RS-2 (LOW): an exception from the handler's own first query left the job 'running', with a settled charge, until the
    stale sweep.
  * RS-3 (LOW, money): when absorbing a failed job's settled charge itself failed, the job ended 'failed' with the charge
    kept and its request key freed, so the same request was bought again.
  * RS-5 (LOW): a DatabaseError before adoption, in fixture (synthetic) mode, read 'Generation failed validation.'.

And one of the same class: the adoption's own COMMIT answer lost after it committed. The handler overwrote the committed
success with a platform failure and reversed the charge of a delivered output.

The lost COMMIT answer is made deterministic: the worker's COMMIT is replaced by one whose answer never arrives (an
OperationalError out of Django's commit(), as for a connection that died; the rollback that follows fails and Django
drops the connection and reconnects, as for a real lost answer). The transaction itself stays open on its own server connection, holding its row locks, as a COMMIT in flight
does, until a finisher thread decides it: after another backend waits for one of its locks (or 10 s) it commits it
(`landed`) or rolls it back. So the handler acts while the commit is genuinely in flight.

Real PostgreSQL; synthetic records; the provider is a fake (no network request).
"""
import threading
import time
from unittest.mock import patch

import psycopg
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection
from django.db.backends.postgresql.base import DatabaseWrapper
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import billing, generation
from core.jobs import deliverable, enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Encounter, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, User, Wallet
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import STORAGES
from core.tests.test_settlement_database_error import DEADLOCK, HELD, HeldSettlementFixture, failing_settlement

#: What the worker may say when it cannot know whether settlement committed: nothing about what was or was not charged.
UNKNOWN = 'The settlement outcome of this request is unknown; an administrator must reconcile it.'
UNRECORDED = 'The outcome of this request could not be recorded; an administrator must reconcile it.'
ABSORPTION_FAILED = ('The output could not be adopted, and its charge could not be reversed automatically; an administrator '
                     'must reconcile it.')
FIXTURE_VALIDATION = 'Generation failed validation.'


class LostConnection:
    """The worker's side of a connection whose COMMIT was sent and whose answer never came back."""

    def rollback(self):
        raise psycopg.OperationalError('synthetic: the connection is lost')

    def cursor(self, *args, **kwargs):
        raise psycopg.OperationalError('synthetic: the connection is lost')

    def close(self):
        pass


class CommitAnswerLost:
    """Once armed, the next outermost COMMIT of this process goes out and its answer is lost."""

    def __init__(self, landed):
        self.landed = landed
        self.armed = False
        self.fired = False
        self.waiter_seen = None
        self.thread = None

    def arm(self):
        self.armed = True

    def patched(self):
        real = DatabaseWrapper._commit
        harness = self

        def _commit(wrapper):
            if not harness.armed:
                return real(wrapper)
            harness.armed = False
            harness.fired = True
            in_flight = wrapper.connection  # the server connection, still inside the transaction and holding its locks
            wrapper.connection = LostConnection()
            harness.thread = threading.Thread(target=harness.finish, args=(in_flight,), daemon=True)
            harness.thread.start()
            raise OperationalError('synthetic: server closed the connection unexpectedly after the COMMIT was sent')
        return patch.object(DatabaseWrapper, '_commit', _commit)

    def finish(self, in_flight):
        pid = in_flight.info.backend_pid
        deadline = time.monotonic() + 10
        self.waiter_seen = False
        while time.monotonic() < deadline:
            # pg_locks is read live (pg_stat_activity would be a snapshot inside this transaction).
            if in_flight.execute('SELECT count(*) FROM pg_locks WHERE NOT granted AND %s = ANY(pg_blocking_pids(pid))',
                                 [pid]).fetchone()[0]:
                self.waiter_seen = True
                break
            time.sleep(0.02)
        if self.landed:
            in_flight.commit()
        else:
            in_flight.rollback()
        in_flight.close()

    def join(self, test):
        test.assertTrue(self.fired, 'the lost COMMIT answer was never simulated')
        self.thread.join(20)
        test.assertFalse(self.thread.is_alive())


class Console:
    def console(self):
        admin = User.objects.create_user(username=f'resolver-{time.monotonic_ns()}@synthetic.invalid',
                                         email=f'resolver-{time.monotonic_ns()}@synthetic.invalid',
                                         verified_at=timezone.now(), is_staff=True)
        device = TOTPDevice.objects.create(user=admin, name='Synthetic authenticator', confirmed=True)
        client = Client()
        client.force_login(admin)
        session = client.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        return admin, client

    def resolve(self, job, form):
        admin, console = self.console()
        response = console.post(f'/console/jobs/{job.pk}/resolve/', form)
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertIn(':failed:', job.request_key)
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
        self.assertFalse(deliverable(job))
        return admin


OUTCOMES = ({'outcome': 'release_no_cost', 'evidence_note': 'Provider console lookup for the stored request id'},
            {'outcome': 'absorb_platform_failure', 'actual_cost': '0.05',
             'evidence_note': 'Provider console lookup for the stored request id'})


def wallets(*pks):
    return {(w.pk, w.balance, w.reserved) for w in Wallet.objects.filter(pk__in=pks)}


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class SettlementCommitAnswerLost(HeldSettlementFixture, Console, TransactionTestCase):
    """RS-1. RED on 61c5cc8f: the landed case read 'reconciliation' with HELD ('... nothing is charged until it is
    resolved') while the usage row, the ledger debits and the settled holds of the same commit existed."""

    def settle_with_lost_answer(self, landed):
        draft = self.draft()
        before_enqueue = wallets(self.promo.pk, self.paid.pk)
        job = enqueue(draft, self.user)
        before = self.snapshot(job)
        harness = CommitAnswerLost(landed)
        real = billing.settle

        def settle(*args, **kwargs):
            harness.arm()
            return real(*args, **kwargs)
        result = adopted_live_result(draft.notes, draft.template_version.fields, f'req_lost_{landed}_{draft.pk.hex[:8]}')
        with harness.patched(), patch('core.jobs.generation.generate', return_value=result) as provider, \
                patch('core.jobs.settle', side_effect=settle):
            self.assertTrue(run_one())
            harness.join(self)
            self.assertFalse(run_one())  # never retried automatically
            self.assertEqual(provider.call_count, 1)
        # The handler acted while the COMMIT was still in flight: it waited for the lost transaction's lock.
        self.assertTrue(harness.waiter_seen)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', UNKNOWN))
        self.assertNotIn(':failed:', job.request_key)
        self.assertFalse(deliverable(job))
        self.assertEqual(self.snapshot(job)['document'], before['document'])
        self.assertFalse(PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        event = AuditEvent.objects.get(action='job.reconciliation', target=str(job.pk))
        self.assertEqual((event.details['billing'], event.details['error_class']), ('uncertain', 'OperationalError'))
        self.assertFalse(AuditEvent.objects.filter(target=str(job.pk), action__in=['job.succeeded', 'job.failed']).exists())
        report = audit_report()
        self.assertTrue(report['all_checks_pass'])
        self.assertIn(job.pk, [row['id'] for row in report['unresolved_jobs']])
        return job, before, before_enqueue

    def test_a_commit_that_landed_after_its_answer_was_lost_is_held_as_unknown_and_resolved_from_the_ledger(self):
        for form in OUTCOMES:
            with self.subTest(outcome=form['outcome']):
                job, before, before_enqueue = self.settle_with_lost_answer(landed=True)
                usage = Usage.objects.get(job=job)  # the commit landed: the customer is charged right now
                self.assertEqual(-sum(e.amount for e in LedgerEntry.objects.filter(job=job, kind='usage')), usage.charged_cost)
                self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})
                admin = self.resolve(job, form)
                # Resolved from what committed: the charge is reversed exactly once, and no hold is released twice.
                self.assertEqual(wallets(self.promo.pk, self.paid.pk), before_enqueue)
                self.assertEqual(sum(e.amount for e in LedgerEntry.objects.filter(job=job, kind='absorbed')), usage.charged_cost)
                cost = PlatformCost.objects.get(job=job, kind='absorbed_failure')
                self.assertEqual(cost.amount, usage.actual_cost)
                self.assertEqual(cost.recorded_by, admin)
                self.assertFalse(AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).exists())
                report = audit_report()
                self.assertTrue(report['all_checks_pass'])
                self.assertEqual(report['unresolved_jobs'], [])

    def test_a_commit_that_did_not_land_after_its_answer_was_lost_is_held_as_unknown_and_resolved_from_the_ledger(self):
        for form in OUTCOMES:
            with self.subTest(outcome=form['outcome']):
                job, before, before_enqueue = self.settle_with_lost_answer(landed=False)
                self.assertEqual(self.snapshot(job), before)  # nothing committed: the holds are still held
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.resolve(job, form)
                self.assertEqual(wallets(self.promo.pk, self.paid.pk), before_enqueue)
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
                receipt = ProviderReceipt.objects.get(job=job)
                cost = PlatformCost.objects.get(job=job, kind='absorbed_failure')
                self.assertEqual(cost.amount, receipt.actual_cost)
                self.assertTrue(cost.evidence_reference.startswith(f'receipt:{receipt.pk} '))
                report = audit_report()
                self.assertTrue(report['all_checks_pass'])
                self.assertEqual(report['unresolved_jobs'], [])

    def test_a_settlement_the_server_refused_at_commit_is_still_established(self):
        """Narrowness: a COMMIT the server answered with an error (a deferred foreign-key violation) rolled back, and the
        connection survived to say so. That outcome is established, and the job still says nothing was charged."""
        job, before = self.generation_failing_at('commit')
        self.assert_held_for_reconciliation(job, before, 'IntegrityError')
        self.assertEqual(job.error, HELD)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class AdoptionCommitAnswerLost(HeldSettlementFixture, TransactionTestCase):
    """The adoption's COMMIT answer lost. RED on 61c5cc8f: a committed success was overwritten as a platform failure and
    the delivered output's charge reversed."""

    def adopt_with_lost_answer(self, landed):
        draft = self.draft()
        job = enqueue(draft, self.user)
        harness = CommitAnswerLost(landed)
        real = generation.adoption

        def adoption(*args, **kwargs):
            harness.arm()
            return real(*args, **kwargs)
        result = adopted_live_result(draft.notes, draft.template_version.fields, f'req_adopt_{landed}')
        with harness.patched(), patch('core.jobs.generation.generate', return_value=result), \
                patch('core.jobs.generation.adoption', side_effect=adoption):
            self.assertTrue(run_one())
            harness.join(self)
        self.assertTrue(harness.waiter_seen)
        job.refresh_from_db()
        draft.refresh_from_db()
        return job, draft

    def test_an_adoption_that_committed_before_its_answer_was_lost_stays_succeeded_and_charged(self):
        job, draft = self.adopt_with_lost_answer(landed=True)
        self.assertEqual(job.state, 'succeeded')
        self.assertTrue(deliverable(job))
        self.assertEqual(draft.status, 'review')
        self.assertTrue(draft.answers)
        usage = Usage.objects.get(job=job)
        self.assertEqual(-sum(e.amount for e in LedgerEntry.objects.filter(job=job, kind='usage')), usage.charged_cost)
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        self.assertFalse(PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists())
        self.assertTrue(AuditEvent.objects.filter(action='job.succeeded', target=str(job.pk)).exists())
        self.assertFalse(AuditEvent.objects.filter(action__in=['job.failed', 'usage.absorbed'], target=str(job.pk)).exists())
        event = AuditEvent.objects.get(action='job.error_after_commit', target=str(job.pk))
        self.assertEqual((event.details['state'], event.details['error_class']), ('succeeded', 'OperationalError'))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_an_adoption_that_did_not_commit_is_a_platform_failure_absorbed(self):
        before = wallets(self.promo.pk, self.paid.pk)
        job, draft = self.adopt_with_lost_answer(landed=False)
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('platform_failure: '), job.error)
        self.assertEqual(draft.answers, {})
        self.assertFalse(deliverable(job))
        self.assertEqual(wallets(self.promo.pk, self.paid.pk), before)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Usage.objects.get(job=job).actual_cost)
        self.assertTrue(audit_report()['all_checks_pass'])


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class HandlerFailures(HeldSettlementFixture, Console, TransactionTestCase):

    def unusable_output(self, armed=None):
        def adoption(*args, **kwargs):
            if armed is not None:
                armed['armed'] = True
            raise ValidationError('synthetic: the provider output cannot be adopted')
        return adoption

    def test_a_handler_whose_first_statement_loses_the_connection_holds_the_job(self):
        """RS-2. The settlement committed, the output could not be adopted, and the server ended the connection at the
        handler's first statement. RED on 61c5cc8f: OperationalError out of run_one, the job left 'running' with the charge
        committed until the stale sweep. Now the handler reconnects and holds the job, asserting nothing."""
        self.addCleanup(connection.close)
        before_enqueue = wallets(self.promo.pk, self.paid.pk)
        draft = self.draft()
        job = enqueue(draft, self.user)
        armed = {}
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_handler_first_statement')

        def wrapper(execute, sql, params, many, context):
            if armed.get('armed') and not armed.get('fired'):
                armed['fired'] = sql
                return execute('SELECT pg_terminate_backend(pg_backend_pid())', None, many, context)
            return execute(sql, params, many, context)
        with patch('core.jobs.generation.generate', return_value=result), \
                patch('core.jobs.generation.adoption', side_effect=self.unusable_output(armed)), connection.execute_wrapper(wrapper):
            self.assertTrue(run_one())
        self.assertTrue(armed.get('fired'))
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', UNRECORDED))
        self.assertNotIn(':failed:', job.request_key)
        self.assertFalse(deliverable(job))
        usage = Usage.objects.get(job=job)  # settled before the failure: the charge stands until an administrator resolves it
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        event = AuditEvent.objects.get(action='job.reconciliation', target=str(job.pk))
        self.assertEqual(event.details['billing'], 'uncertain')
        self.resolve(job, OUTCOMES[0])
        self.assertEqual(wallets(self.promo.pk, self.paid.pk), before_enqueue)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, usage.actual_cost)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_connection_lost_outside_a_transaction_is_repaired_before_the_handler_reads(self):
        """RS-2, where it is possible. The server ended the connection at the worker's autocommit write of the result path
        (after the receipt committed, before settlement). Django closes a broken connection only at a request boundary,
        so every later statement on it failed. RED on 61c5cc8f: OperationalError ('the connection is closed') out of run_one
        at the handler's first query, the job left 'running'. Now the handler repairs the connection first and records what
        is established: settlement never ran, so nothing is charged, and the job is held with its receipt."""
        self.addCleanup(connection.close)
        draft = self.draft()
        job = enqueue(draft, self.user)
        before = self.snapshot(job)
        armed = {}

        def wrapper(execute, sql, params, many, context):
            if not armed.get('fired') and sql.startswith('UPDATE "core_job" SET "result_path"'):
                armed['fired'] = sql
                return execute('SELECT pg_terminate_backend(pg_backend_pid())', None, many, context)
            return execute(sql, params, many, context)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_autocommit_lost')
        with patch('core.jobs.generation.generate', return_value=result), connection.execute_wrapper(wrapper):
            self.assertTrue(run_one())
        self.assertTrue(armed.get('fired'))
        self.assert_held_for_reconciliation(job, before, 'OperationalError')

    def test_a_reversal_the_database_refuses_keeps_the_job_held_with_its_request_key(self):
        """RS-3. The output could not be adopted and the database refused the absorption's ledger write. RED on 61c5cc8f:
        'failed', still charged, key freed, and the same request queued, held and charged again."""
        before_enqueue = wallets(self.promo.pk, self.paid.pk)
        draft = self.draft()
        job = enqueue(draft, self.user)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_absorb_refused')

        def refuse_absorption(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "core_ledgerentry"') and 'absorbed' in (params or ()):
                return execute(DEADLOCK, None, many, context)
            return execute(sql, params, many, context)
        with patch('core.jobs.generation.generate', return_value=result) as provider, \
                patch('core.jobs.generation.adoption', side_effect=self.unusable_output()), connection.execute_wrapper(refuse_absorption):
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', ABSORPTION_FAILED))
        self.assertNotIn(':failed:', job.request_key)
        usage = Usage.objects.get(job=job)
        self.assertEqual(-sum(e.amount for e in LedgerEntry.objects.filter(job=job, kind='usage')), usage.charged_cost)
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        self.assertFalse(PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists())
        self.assertEqual(AuditEvent.objects.get(action='usage.absorb_failed', target=str(job.pk)).details['error_class'], 'OperationalError')
        self.assertEqual(AuditEvent.objects.get(action='job.reconciliation', target=str(job.pk)).details['billing'], 'platform_failure')
        # The same request is not bought twice: the held key still answers it, nothing new is queued, held or sent.
        jobs_before, holds_before = Job.objects.count(), Reservation.objects.count()
        again = enqueue(draft, self.user)
        self.assertEqual((again.pk, again.reused), (job.pk, True))
        self.assertEqual((Job.objects.count(), Reservation.objects.count()), (jobs_before, holds_before))
        with patch('core.jobs.generation.generate', return_value=result):
            self.assertFalse(run_one())
        self.assertEqual(provider.call_count, 1)
        self.resolve(job, OUTCOMES[0])
        self.assertEqual(wallets(self.promo.pk, self.paid.pk), before_enqueue)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, usage.actual_cost)
        report = audit_report()
        self.assertTrue(report['all_checks_pass'])
        self.assertEqual(report['unresolved_jobs'], [])


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, AI_MODE='fixture')
class FixtureFailures(HeldSettlementFixture, TransactionTestCase):
    """RS-5, in fixture (synthetic) mode, where no provider cost can exist."""

    def test_a_database_error_is_named_as_one_not_as_a_validation_failure(self):
        """RED on 61c5cc8f: 'Generation failed validation.' for a settlement the database refused."""
        draft = self.draft()
        job = enqueue(draft, self.user)
        with patch('core.jobs.settle', side_effect=failing_settlement('job lock')):
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertNotIn('validation', job.error)
        self.assertIn('platform database error (OperationalError)', job.error)
        self.assertIn(':failed:', job.request_key)  # established: nothing settled, and synthetic generation costs nothing
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        event = AuditEvent.objects.get(action='job.failed', target=str(job.pk))
        self.assertEqual((event.details['billing'], event.details['error_class']), ('fixture', 'OperationalError'))

    def test_a_validation_failure_is_still_named_as_one(self):
        draft = self.draft()
        job = enqueue(draft, self.user)
        with patch('core.jobs.generation.generate', side_effect=ValidationError('synthetic: selections refused')):
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', FIXTURE_VALIDATION))
        self.assertIn(':failed:', job.request_key)

    def test_a_settlement_whose_commit_answer_was_lost_keeps_its_request_key(self):
        """A charge may exist (the settlement may have committed): the key is not freed and nothing is claimed."""
        draft = self.draft()
        job = enqueue(draft, self.user)
        harness = CommitAnswerLost(landed=True)
        real = billing.settle

        def settle(*args, **kwargs):
            harness.arm()
            return real(*args, **kwargs)
        with harness.patched(), patch('core.jobs.settle', side_effect=settle):
            self.assertTrue(run_one())
            harness.join(self)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', UNKNOWN))
        self.assertNotIn(':failed:', job.request_key)
        self.assertTrue(Usage.objects.filter(job=job, simulated=True).exists())
        self.assertFalse(Encounter.objects.get(pk=draft.pk).answers)
