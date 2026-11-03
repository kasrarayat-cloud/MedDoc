"""Refutation round 4, R4-SENDS: the installation-wide provider lock in the participant access check's tool loop, and
the condition that makes the lock check ask about THIS database session (HARNESS.md 2, 11.2 and 12.7 "Recording a
participant's exchanges"; I8).

- sends-1: the access check (manage.py participant_access_check, which the installer runs once the new pair's worker
  runs) takes the same lock as the pipeline's sends (_single_flight) and runs the same tool loop, but it sent every
  later exchange without asking whether its database session still held the lock - the defect round 3 repaired in the
  worker's loop (jobs._send_loop). Its session is idle for the whole loop (up to 330 s), so a database restart,
  pg_terminate_backend, a network reset or the server's idle timeout ended it, and with it the lock, and exchange 2
  went out while another session - the worker's - could take the lock and send: two provider sends at once. Its unlock
  then met the ended session and the command raised, so no receipt was printed although the vendor had answered. Now
  its loop asks before each later exchange, through jobs._holds_provider_lock, and sends nothing more when the session
  no longer holds the lock or the question fails; its unlock tolerates the ended session, so the receipt says what was
  sent and the check fails by its outcome.
- sends-2, falsegreen-1: jobs._holds_provider_lock asks whether THIS session holds the lock (pid = pg_backend_pid()),
  and only a race pinned that condition: a mutant asking whether ANY session holds it passed the suite in most runs.
  Pinned here on the check itself and through the access check's loop, with another session holding the lock when the
  loop asks; the worker's loop is pinned so in tests.test_harness2_r3_sends LockedSessionTests, beside sends-3
  (_finish_loop's fallback never records a replayed run as sent).

Synthetic data only; offline (requests.Session is a fake session, the suite's synthetic key); the lock is PostgreSQL's
real advisory lock on the test cluster. No test transaction wraps the command, as none wraps it in its one-shot
container, so its session really ends: the client side of its socket is shut down, or the server ends the idle session
itself; no process is signalled.
"""
import json
import time
from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase, override_settings

from studio import jobs
from studio.management.commands import participant_access_check
from tests.test_harness2_r3_sends import end_session_by_server, end_session_by_socket, lock_free_elsewhere
from tests.test_participants_access_check import AUTHORIZATION
from tests.test_participants_support import (FACTS_ARGUMENTS, SECRETS, FakeResponse, FakeSession, OfflineMixin,
                                             astra_tool_call, fixture_bytes, openai_env, write_file)
from tests.test_pipeline_api import _OtherSession

DID_NOT_PASS = 'The Astra access check did not pass: see the receipt.'


def taken_and_kept(other, wait=5.0):
    """Whether ``other`` takes the installation-wide provider lock within ``wait`` seconds - once an ended session's
    backend has let it go - and keeps it (released when the test ends)."""
    deadline = time.monotonic() + wait
    while not other.try_lock():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def ended_and_replaced():
    """The access check's session ends (the client side of its socket is shut down) and Django drops it, so the next
    query opens another session, as transaction.atomic does after a rollback that fails: a session that never took the
    lock."""
    end_session_by_socket()
    connection.close()


class AccessCheckLockTests(OfflineMixin, TransactionTestCase):
    """sends-1 (I8): the access check's tool loop asks, before each later exchange, whether its database session
    still holds the provider lock _single_flight took, as the pipeline's loop does, and sends nothing more when it does
    not."""

    def setUp(self):
        super().setUp()
        # whatever a test leaves of the command's session, the flush after it and the next test start on a fresh one
        self.addCleanup(connection.close)
        self.openai = write_file(self.tmp / 'openai.env', openai_env())
        self.other = _OtherSession(self)  # the worker's session, or a second worker's
        # a session an earlier test ended lets the lock go only once its backend has exited
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0), 'an earlier test left the provider lock held')

    def rows(self):
        return {model.__name__: model.objects.count() for model in apps.get_app_config('studio').get_models()}

    def check(self, end=None, then=None):
        """Run the access check for Astra: exchange 1 asks cms_code_facts, which the command's own executor answers;
        ``end`` then ends the command's database session, and ``then`` runs once it has (another session takes the
        lock, say); exchange 2 would be the final reading. Returns what each exchange saw."""
        seen = {}

        def exchange_1():
            seen['lock free elsewhere during exchange 1'] = lock_free_elsewhere(self.other)
            return FakeResponse(200, astra_tool_call(('call_access_1', 'cms_code_facts', FACTS_ARGUMENTS)),
                                headers={'x-request-id': 'req_turn_1'})

        def exchange_2():  # never sent once the session that took the lock has ended
            seen['lock free elsewhere during exchange 2'] = lock_free_elsewhere(self.other)
            return FakeResponse(200, fixture_bytes('astra-colonoscopy.response.json'),
                                headers={'x-request-id': 'req_turn_2'})
        session = FakeSession(exchange_1, exchange_2)
        real_tool = participant_access_check._local_tool

        def tool(name, arguments):
            result = real_tool(name, arguments)
            seen['tool answered'] = True
            if end is not None:
                end()
            if then is not None:
                seen['then'] = then()
            return result
        live = {'ASTRA_MODE': 'live', 'OPENAI_CREDENTIALS_FILE': str(self.openai), 'AUTHORIZATION_REF': AUTHORIZATION}
        out, err = StringIO(), StringIO()
        before = self.rows()
        with override_settings(**live), mock.patch('requests.Session', return_value=session), \
                mock.patch.object(participant_access_check, '_local_tool', tool):
            try:
                call_command('participant_access_check', participant='astra', stdout=out, stderr=err)
                seen['raised'] = None
            except Exception as exc:  # noqa: BLE001 - the command's own refusal, or what met the ended session
                text = str(exc).strip()
                seen['raised'] = (type(exc).__name__, text.splitlines()[0][:120] if text else '')
        seen['posted'] = len(session.calls)
        printed = out.getvalue() + err.getvalue()
        for secret in SECRETS:
            self.assertNotIn(secret, printed)
        seen['receipt'] = json.loads(out.getvalue()) if out.getvalue().strip() else None
        connection.close()  # read back on a fresh session
        self.assertEqual(self.rows(), before, 'the access check wrote to the database')
        return seen

    def assert_stopped_after_exchange_1(self, seen, error):
        """Exchange 1 was sent under the lock, exchange 2 never was, and the receipt of what was sent is printed: the
        check fails by its outcome, with CPT Studio's own sentence for why the loop stopped (``error()``)."""
        self.assertFalse(seen['lock free elsewhere during exchange 1'])  # the command's session held the lock
        self.assertTrue(seen['tool answered'])
        self.assertEqual(seen['posted'], 1, 'exchange 2 was sent after the session that held the provider lock ended')
        self.assertNotIn('lock free elsewhere during exchange 2', seen)
        self.assertEqual(seen['raised'], ('CommandError', DID_NOT_PASS))
        receipt = seen['receipt']
        self.assertIsNotNone(receipt, 'no receipt was printed, although the vendor answered exchange 1')
        self.assertEqual((receipt['outcome'], receipt['sent'], receipt['error'], receipt['reading'],
                          receipt['exchange_count']), ('failed', True, error(), None, 1))
        (exchange,) = receipt['exchanges']
        self.assertEqual((exchange['turn'], exchange['outcome'], exchange['request_id'], exchange['tool_calls']),
                         (1, 'succeeded', 'req_turn_1', [{'call_id': 'call_access_1', 'tool': 'cms_code_facts'}]))

    @staticmethod
    def unchecked():
        """The receipt's sentence when the question itself fails on the ended session."""
        return participant_access_check.LOCK_UNCHECKED.format(error='OperationalError', number=1, plural='')

    def test_a_session_ended_after_exchange_1_sends_nothing_more_and_its_receipt_is_printed(self):
        seen = self.check(end=end_session_by_socket)
        self.assert_stopped_after_exchange_1(seen, self.unchecked)
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0))  # the lock ended with the session that took it

    def test_a_session_the_server_ended_while_idle_sends_nothing_more(self):
        seen = self.check(end=end_session_by_server)
        self.assert_stopped_after_exchange_1(seen, self.unchecked)
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0))

    def test_a_lock_another_session_holds_is_not_this_session_s(self):
        # sends-2 and falsegreen-1 through the access check's loop: its session is replaced by one that never took the
        # lock, and another session takes the lock and keeps it before the loop asks. Asking whether ANY session holds
        # the lock would send exchange 2 beside that session's send.
        seen = self.check(end=ended_and_replaced, then=lambda: taken_and_kept(self.other))
        self.assertTrue(seen['then'])  # the other session held the lock when the loop asked
        self.assert_stopped_after_exchange_1(seen, lambda: jobs.LOOP_LOCK_LOST_MESSAGE.format(number=1, plural=''))
        self.assertTrue(self.other.unlock())
        self.assertTrue(lock_free_elsewhere(self.other))  # the command's sessions hold nothing

    def test_control_a_session_that_holds_the_lock_throughout_runs_the_whole_loop(self):
        seen = self.check()
        self.assertEqual((seen['lock free elsewhere during exchange 1'], seen['lock free elsewhere during exchange 2']),
                         (False, False))  # the command held the lock for the whole loop
        self.assertEqual((seen['posted'], seen['raised']), (2, None))
        receipt = seen['receipt']
        self.assertEqual((receipt['outcome'], receipt['error'], receipt['exchange_count'],
                          receipt['reading']['refused']), ('succeeded', '', 2, False))
        self.assertTrue(lock_free_elsewhere(self.other))  # released by the command's own unlock


class HoldsProviderLockTests(TransactionTestCase):
    """sends-2, falsegreen-1: jobs._holds_provider_lock answers for THIS database session (pid = pg_backend_pid()) and
    the provider lock's key alone. A lock another session holds - a second worker's, or the access check's - is not
    this session's, nor is another advisory lock this session holds."""

    def setUp(self):
        super().setUp()
        self.other = _OtherSession(self)
        # a session an earlier test ended lets the lock go only once its backend has exited
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0), 'an earlier test left the provider lock held')

    def this_session(self, sql, params):
        """Take an advisory lock on this test's own session; it is released when the test ends."""
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT {sql}', params)
            self.assertTrue(cursor.fetchone()[0])
        release = sql.replace('pg_try_advisory_lock', 'pg_advisory_unlock')

        def unlock():
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT {release}', params)
        self.addCleanup(unlock)

    def test_a_lock_another_session_holds_is_not_this_session_s(self):
        # this session has taken no lock (pg_locks lists every database's locks on the cluster: only the pid tells
        # this session's apart)
        self.assertFalse(jobs._holds_provider_lock())
        self.assertTrue(self.other.try_lock())
        try:
            self.assertFalse(jobs._holds_provider_lock(), "another session's provider lock was read as this session's")
        finally:
            self.assertTrue(self.other.unlock())

    def test_this_session_s_own_provider_lock_and_no_other(self):
        key = jobs.PROVIDER_LOCK_KEY
        high, low = key >> 32, key & 0xFFFFFFFF
        for label, sql, params in (
                ('another key, the same high half', 'pg_try_advisory_lock(%s)', [key ^ 1]),
                ('another key, the same low half', 'pg_try_advisory_lock(%s)', [key ^ (1 << 40)]),
                ('the two halves as a pair of int4 keys (objsubid 2)', 'pg_try_advisory_lock(%s, %s)', [high, low])):
            with self.subTest(label):
                self.this_session(sql, params)
                self.assertFalse(jobs._holds_provider_lock())
        self.this_session('pg_try_advisory_lock(%s)', [key])
        self.assertTrue(jobs._holds_provider_lock())
        self.assertFalse(self.other.try_lock())  # and no other session can take it meanwhile
