"""Release 1, integrated refutation round 3, repair builder d3: the held stop's safe points, the daily run's locks, the
orphan sweep's record.

- D3-1 (disposal-0 and disposal-1): once the reason a stop signal is held is over - the row committed and printed -
  the stop acts at the next safe point. A plan's row printed, the stop ends the command there, before every file in
  scope is read and hashed again for the manifest's lines, and a stop that comes while they are read ends it at once
  (refute-r3/disposal/probes/test_plan_hold.py, refute-r3/verify/disposal-0). After a destruction's commit no statement
  of its steps is sent once a stop was kept: one landing between two statements - before the VACUUM is handed to
  psycopg, after a count returned - no longer lets the next statement run, and wait on another session's lock with the
  stop held (refute-r3/disposal/probes/test_vacuum_gap.py, refute-r3/verify/disposal-1); a statement the stop came just
  before, as it was handed to psycopg, is cancelled once it is in flight. Each through the command's own handlers, in
  this process, as tests.test_r1_repair_d2 runs them: one real signal sent with os.kill, at a moment an execute wrapper
  of the test's or a sys.settrace hook picks; nothing under test is patched (a file read is only observed).
- D3-2 (disposal-2, regression-0 and locks-2): the daily run's session cleanup - the dead links and the expired sessions,
  sign-in state - commits before the recorded transaction, so a returning member's sign-in, and the end of an account's
  sessions, no longer wait for the whole run: real concurrency, the daily run in a thread of its own while it hashes a
  backlog of names (refute-r3/disposal/probes/test_daily_stall.py, refute-r3/verify/locks-2, -disposal-2,
  -regression-0); its counts still go in the run's record.
- D3-3 (disposal-3): the orphan sweep command records what its removal did - after the removal, as the daily run does
  (maintenance.orphans_removed, naming the sweep's record) - whether a file went or a removal failed
  (refute-r3/verify/disposal-3).

Synthetic practices only, on a test database and originals folders of the tests' own."""
from __future__ import annotations

import io
import os
import re
import signal
import tempfile
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

import psycopg
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import connection, connections
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import disposal, maintenance, models, sessions, storage
from studio.management.commands import dispose as dispose_cmd
from tests import test_disposal as td
from tests import test_r1_repair_d2 as d2
from tests.support import coding as f

Event = models.DisposalEvent
MANIFEST_LINE = re.compile(r'^  [0-9a-f]{64}  ', re.M)
PSYCOPG_EXECUTE = psycopg.Cursor.execute.__code__
LOCK_SECONDS = 20  # how long another session holds the lock a statement would wait on: the stop held, at most


def other_session(**options):
    params = {key: value for key, value in connection.get_connection_params().items()
              if key not in ('cursor_factory', 'context')}
    return psycopg.connect(**params, **options)


class Holder:
    """Another session holding a table lock - taken at once, or by take() - released after LOCK_SECONDS, or when the
    test ends: what a concurrent ANALYZE, VACUUM or migration holds."""

    def __init__(self, test):
        self.session, self.released_at = other_session(), None
        self._timer = threading.Timer(LOCK_SECONDS, self.release)
        self._timer.daemon = True
        test.addCleanup(self.close)

    def take(self, sql):
        self.session.execute(sql)
        self._timer.start()

    def release(self):
        if self.released_at is None:
            self.released_at = time.monotonic()
            self.session.rollback()

    def close(self):
        self._timer.cancel()
        self.release()
        self.session.close()


# --- D3-1: the held stop's safe points (disposal-0 and disposal-1) ---------------------------------------------------------

class PlanSafePointTests(d2.HoldCase):
    """disposal-0: `dispose --plan` of a document with several files, and one real signal once its 'planned' row has
    committed - the lens's and the verifier's trigger - or while the manifest's lines are read again. The files read
    (storage.file_digest) are counted, not changed: at the head every file in scope was hashed a second time with the
    stop held, so a practice's plan outlasted docker stop's 10 s."""

    FILES = 4

    def plan_with(self, label, *, signal_at=None, ctrl_c=False):
        """`dispose --plan --encounter` of a new document of FILES files, with one real signal (SIGTERM, or Ctrl-C
        under Python's own handler) right after the plan's row INSERT returned (signal_at None), or as the n-th file
        is read again after it: (status, out, err, the plan, the files read after the row, the signal's moment)."""
        enc = self.document(label, files=self.FILES)
        signum = signal.SIGINT if ctrl_c else signal.SIGTERM
        state = {'row': False, 'after': 0, 'sent': None}
        real = storage.file_digest

        def read(path):
            if state['row']:
                state['after'] += 1
                if signal_at is not None and state['after'] == signal_at and state['sent'] is None:
                    state['sent'] = time.monotonic()
                    os.kill(os.getpid(), signum)
            return real(path)

        def after_the_row(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('INSERT INTO "studio_disposalevent"') and not state['row']:
                state['row'] = True
                if signal_at is None:
                    state['sent'] = time.monotonic()
                    os.kill(os.getpid(), signum)  # the command's handler takes it here: held (plan() held it)
            return result

        reason = td.reason_file(self.scratch.name, 'Synthetic: misfiled.')
        with mock.patch.object(storage, 'file_digest', side_effect=read), connection.execute_wrapper(after_the_row):
            status, out, err = self.dispose('--plan', '--encounter', str(enc.pk), '--by', 'Synthetic Operator',
                                            '--reason-file', reason, ctrl_c=ctrl_c)
        plan = self.events_of(enc).get(stage=Event.PLANNED)
        return status, out, err, plan, state['after'], state['sent']

    def assert_plan_printed(self, plan, out):
        self.assertIn(f'Plan {plan.pk} for document', out)
        self.assertIn(f'manifest sha256 {plan.manifest_digest}', out)
        self.assertNotIn('ZZ-TITLE-MARKER', out)

    def test_disposal_0_a_stop_once_the_plans_row_committed_ends_the_command_before_its_files_are_read_again(self):
        status, out, err, plan, read_after, sent = self.plan_with('plan row committed')
        self.assertIsNotNone(sent)  # the control: the signal went once the row's INSERT had returned
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_plan_printed(plan, out)
        self.assertIn(dispose_cmd.HELD_TEXT, err)
        self.assertEqual(read_after, 0)  # the head read every file in scope again first (FILES)
        self.assertIsNone(MANIFEST_LINE.search(out))
        self.assertEqual(plan.files['files'], self.FILES)

    def test_a_ctrl_c_once_the_plans_row_committed_ends_it_there_too(self):
        status, out, err, plan, read_after, sent = self.plan_with('plan row ctrl-c', ctrl_c=True)
        self.assertIsNotNone(sent)
        self.assertEqual(status, 'KeyboardInterrupt', err[-800:])
        self.assert_plan_printed(plan, out)
        self.assertEqual(read_after, 0)

    def test_a_stop_while_the_manifest_is_read_again_ends_the_command_at_once(self):
        for ctrl_c, expected in ((False, 128 + signal.SIGTERM), (True, 'KeyboardInterrupt')):
            with self.subTest(ctrl_c=ctrl_c):
                status, out, err, plan, read_after, sent = self.plan_with(f'manifest read ctrl-c={ctrl_c}',
                                                                          signal_at=2, ctrl_c=ctrl_c)
                self.assertIsNotNone(sent)
                self.assertEqual(status, expected, err[-800:])
                self.assert_plan_printed(plan, out)
                self.assertEqual(read_after, 2)  # the file under way was the last one read: never held to the end
                self.assertNotIn(dispose_cmd.HELD_TEXT, err)  # raised where the command was, as before any commit
                self.assertIsNone(MANIFEST_LINE.search(out))


class StatementSafePointTests(d2.HoldCase):
    """disposal-1: `dispose --execute` of a planned document, another session holding a lock one statement after the
    commit waits for (released after LOCK_SECONDS), and one real SIGTERM between two statements of a step - just before
    the VACUUM is handed to psycopg, after the first count returned - or as the VACUUM is handed over, past the safe
    point's own check. At the head each was held until the lock went: the next statement was sent anyway."""

    def run_with(self, label, lock, *, fire):
        """The run of a new document's plan; ``lock`` (the holder's statement) taken before the run, or once the
        VACUUM returned (lock_after_vacuum); ``fire``: an execute wrapper's moment ('before vacuum', 'after count 1')
        or a sys.settrace hook's ('psycopg vacuum'). (status, out, err, the final event, seconds from the signal to the
        command's end, whether the lock was still held when it ended)."""
        enc = self.document(label)
        plan = self.plan(enc)
        holder, state = Holder(self), {'sent': None, 'vacuumed': False, 'counts': 0}
        before_run, after_vacuum = lock
        if before_run:
            holder.take(before_run)

        def send():
            state['sent'] = time.monotonic()
            os.kill(os.getpid(), signal.SIGTERM)

        def test_wrapper(execute, sql, params, many, context):  # outside the command's own wrapper
            if fire == 'before vacuum' and sql.startswith('VACUUM') and state['sent'] is None:
                send()  # nothing in flight: the head kept it and sent the VACUUM all the same
            counting = state['vacuumed'] and sql.startswith('SELECT COUNT(*)')
            result = execute(sql, params, many, context)
            if sql.startswith('VACUUM'):
                state['vacuumed'] = True
                if after_vacuum:
                    holder.take(after_vacuum)
            if counting:
                state['counts'] += 1
                if fire == 'after count 1' and state['counts'] == 1 and state['sent'] is None:
                    send()  # the count returned, the next not yet sent
            return result

        tracer = None
        if fire == 'psycopg vacuum':
            def accept(frame, event):
                if event == 'call' and frame.f_code is PSYCOPG_EXECUTE \
                        and str(frame.f_locals.get('query', '')).startswith('VACUUM'):
                    state['sent'] = time.monotonic()
                    return True
                return False
            tracer, fired = d2.one_signal(accept)
        with connection.execute_wrapper(test_wrapper):
            status, out, err = self.execute(plan, tracer=tracer)
        ended = time.monotonic()
        still_held = holder.released_at is None
        holder.close()
        self.assertIsNotNone(state['sent'], 'the signal was never sent')
        return status, out, err, self.final_of(enc), ended - state['sent'], still_held

    def assert_not_held(self, status, out, final, seconds, still_held, problem):
        self.assertLess(seconds, 5, f'the stop was held {seconds:.1f} s')
        self.assertTrue(still_held, 'the run waited for the lock to be released')
        self.assertEqual(status, 128 + signal.SIGTERM)
        self.assert_names_only_what_committed(out)
        self.assertEqual(final.stage, Event.FAILED)
        self.assertIn(problem, final.counts['problems'])
        self.assertEqual(final.counts['rows_destroyed'], 'yes')
        self.assertEqual(final.files['remaining'], 0)  # the files went before the steps it stopped

    def test_disposal_1_a_stop_just_before_the_vacuum_is_handed_over_sends_no_vacuum(self):
        status, out, err, final, seconds, still_held = self.run_with(
            'vacuum gap', ('LOCK TABLE studio_encounter IN SHARE UPDATE EXCLUSIVE MODE', None), fire='before vacuum')
        self.assert_not_held(status, out, final, seconds, still_held, 'vacuum: Stopped')
        self.assertIn('vacuum=not run', final.notes)  # never sent (the head: 'vacuum=done', after the lock went)
        self.assertNotIn('remaining', final.counts)  # the counts step was skipped

    def test_disposal_1_a_stop_after_a_count_returned_sends_no_further_count(self):
        status, out, err, final, seconds, still_held = self.run_with(
            'count gap', (None, 'LOCK TABLE studio_sourcefile IN ACCESS EXCLUSIVE MODE'), fire='after count 1')
        self.assert_not_held(status, out, final, seconds, still_held, 'counts: Stopped')
        self.assertIn('vacuum=done', final.notes)
        self.assertNotIn('remaining', final.counts)

    def test_a_stop_as_the_vacuum_is_handed_to_psycopg_is_cancelled_once_it_is_in_flight(self):
        status, out, err, final, seconds, still_held = self.run_with(
            'vacuum hand-off', ('LOCK TABLE studio_encounter IN SHARE UPDATE EXCLUSIVE MODE', None),
            fire='psycopg vacuum')
        self.assert_not_held(status, out, final, seconds, still_held, 'vacuum: Stopped')
        self.assertIn('vacuum=failed', final.notes)  # it was sent: cancelled, it ended on an error


class StatementSafePointUnitTests(SimpleTestCase):
    """before_statement itself: a kept stop raised and the statement never handed over; the connection named only while
    one is."""

    def setUp(self):
        self.hold = disposal.StopSignalHold()
        self.hold.reset(armed=True)

    def test_a_kept_stop_is_raised_and_the_statement_never_sent(self):
        stop, sent = dispose_cmd.Stopped(signal.SIGTERM), []
        self.hold.hold()
        self.assertTrue(self.hold.keep(stop))
        with mock.patch.object(disposal, 'connection'):
            with self.assertRaises(dispose_cmd.Stopped) as raised:
                self.hold.before_statement(lambda *args: sent.append(args), 'SELECT 1', None, False, {})
        self.assertIs(raised.exception, stop)
        self.assertEqual(sent, [])
        self.assertIsNone(self.hold.sending)
        self.assertIs(self.hold.pending, stop)  # still kept: the command acts on it at its next safe point

    def test_without_a_stop_the_statement_runs_and_names_its_connection_while_it_does(self):
        seen = []
        with mock.patch.object(disposal, 'connection') as fake:
            result = self.hold.before_statement(lambda *args: seen.append(self.hold.sending) or 'answer', 'SELECT 1',
                                                None, False, {})
        self.assertEqual((result, seen), ('answer', [fake.connection]))
        self.assertIsNone(self.hold.sending)


# --- D3-2: the daily run's session cleanup commits first (disposal-2, regression-0, locks-2) -------------------------------

CPT = 'cpt.quillmd.com'
PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
NAMES = 4000  # unmatched names to hash: the recorded transaction stays open for seconds while a sign-in comes


@override_settings(STORAGES=d2.PLAIN)
class DailySignInTests(TransactionTestCase):
    """A member whose earlier session at the cpt door expired (its link left for the daily run), a backlog of NAMES
    unmatched sign-in names 35 days old, maintenance.run_daily() - the worker's call - in a thread and a connection of
    its own, and, once another session sees it hashing those names, the member signs in again through /login/, or the
    account's sessions are ended (a password change's, sign out everywhere's). At the head each waited on the dead link
    the run had deleted until the whole run committed."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name) / 'originals'
        root.mkdir(mode=0o700)
        work = Path(folder.name) / 'work'
        work.mkdir(mode=0o700)
        override = override_settings(ORIGINALS_DIR=root)
        override.enable()
        self.addCleanup(override.disable)
        patcher = mock.patch('tempfile.gettempdir', return_value=str(work))
        patcher.start()
        self.addCleanup(patcher.stop)

    def sign_in(self, user):
        client = Client(HTTP_HOST=CPT, REMOTE_ADDR='198.51.100.7')
        return client.post('/login/', {'username': user.get_username(), 'password': PASSWORD}).status_code, client

    def returning_member(self, *, live=False):
        """A member whose last session at the cpt door expired yesterday - its link dead, left for the daily run - and
        with ``live`` one more session signed in before it (first: a later sign-in's cap removes a dead link). (the
        member, the expired session's key)."""
        user = f.member(f.workspace('Synthetic practice r1repd3 daily'))
        if live:
            self.assertEqual(self.sign_in(user)[0], 302)
        status, client = self.sign_in(user)
        self.assertEqual(status, 302)
        key = client.cookies[settings.SESSION_COOKIE_NAME].value
        Session.objects.filter(session_key=key).update(expire_date=timezone.now() - timedelta(days=1))
        self.assertEqual(models.SessionAccountLink.objects.filter(session_key=key).count(), 1)  # the dead link
        return user, key

    def backlog(self):
        models.LoginAttempt.objects.bulk_create(
            [models.LoginAttempt(username=f'r1repd3-typed-{number}@example.invalid', client='192.0.2.10',
                                 succeeded=False) for number in range(NAMES)], batch_size=2000)
        models.LoginAttempt.objects.filter(username__startswith='r1repd3-typed-').update(
            created_at=timezone.now() - timedelta(days=35))

    def during_the_daily_run(self, act):
        """``act()`` once another session sees the daily run hash names: (its answer, its seconds, how long before the
        daily run's end it ended, the run's counts)."""
        times, found = {}, {}

        def daily():
            try:
                found['counts'] = maintenance.run_daily()
            finally:
                times['daily_end'] = time.monotonic()
                connections.close_all()

        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            own = cursor.fetchone()[0]
        watcher, worker = other_session(autocommit=True), threading.Thread(target=daily)
        try:
            worker.start()
            deadline, hashing = time.monotonic() + 120, False
            while worker.is_alive() and time.monotonic() < deadline and not hashing:
                hashing = watcher.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND pid <> %s AND query LIKE 'UPDATE \"studio_loginattempt\"%%'", [own]).fetchone()[0] > 0
                time.sleep(0.005)
            self.assertTrue(hashing, 'the daily run was never seen hashing names')
            started = time.monotonic()
            answer = act()
            ended = time.monotonic()
        finally:
            worker.join(300)
            watcher.close()
        self.assertIn('counts', found)
        return answer, ended - started, times['daily_end'] - ended, found['counts']

    def assert_not_waiting(self, seconds, before_the_end):
        self.assertLess(seconds, 3, f'it took {seconds:.2f} s')
        self.assertGreater(before_the_end, 0.5, 'it ended only as the daily run committed')

    def test_disposal_2_a_returning_members_sign_in_never_waits_for_the_daily_run(self):
        user, old_key = self.returning_member()
        self.backlog()
        status, seconds, before_the_end, counts = self.during_the_daily_run(lambda: self.sign_in(user)[0])
        self.assertEqual(status, 302)
        self.assert_not_waiting(seconds, before_the_end)
        self.assertGreaterEqual(counts['session_links_pruned'], 1)  # the dead link: pruned, and counted in the record
        self.assertEqual(counts['signin_names_hashed'], NAMES)
        daily = models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT).data
        self.assertEqual((daily['session_links_pruned'], daily['sessions_cleared'], daily['failed']),
                         (counts['session_links_pruned'], counts['sessions_cleared'], []))
        self.assertFalse(models.SessionAccountLink.objects.filter(session_key=old_key).exists())
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())

    def test_regression_0_ending_an_accounts_sessions_never_waits_for_the_daily_run(self):
        user, _ = self.returning_member(live=True)  # the live session is the one the end of its sessions ends
        self.backlog()
        ended, seconds, before_the_end, _ = self.during_the_daily_run(lambda: sessions.end_sessions(user))
        self.assertEqual(ended, 1)
        self.assert_not_waiting(seconds, before_the_end)
        self.assertFalse(models.SessionAccountLink.objects.filter(account_id=user.pk).exists())

    def test_a_failing_session_step_is_named_in_the_record_and_the_others_still_run(self):
        user, old_key = self.returning_member()
        with mock.patch.object(maintenance, 'clear_expired_sessions', side_effect=RuntimeError('synthetic')), \
                self.assertLogs('studio.maintenance', 'ERROR') as logged:
            counts = maintenance.run_daily()
        self.assertIn('the daily maintenance step sessions_cleared failed (RuntimeError)',
                      [record.getMessage() for record in logged.records])
        daily = models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT).data
        self.assertEqual((daily['failed'], counts['failed']), (['sessions_cleared'], ['sessions_cleared']))
        self.assertNotIn('sessions_cleared', daily)
        self.assertEqual(daily['session_links_pruned'], 1)  # the step before it committed, and is counted
        self.assertFalse(models.SessionAccountLink.objects.filter(session_key=old_key).exists())
        self.assertTrue(Session.objects.filter(session_key=old_key).exists())  # the failed step's: left as it was


# --- D3-3: the orphan sweep command records what its removal did (disposal-3) ---------------------------------------------

@override_settings(STORAGES=d2.PLAIN)
class SweepRemovalRecordTests(TransactionTestCase):
    """The verifier's input: one orphan file two hours old in a practice's folder - its removal failing (the folder
    0500, so unlink is refused) or not - and `sweep_orphan_files --delete`."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / 'originals'
        self.root.mkdir(mode=0o700)
        override = override_settings(ORIGINALS_DIR=self.root)
        override.enable()
        self.addCleanup(override.disable)

    def orphan(self, *, removable=True):
        folder = self.root / str(uuid.uuid4())
        folder.mkdir(mode=0o700)
        path = folder / str(uuid.uuid4())
        path.write_bytes(b'synthetic orphan bytes')
        past = time.time() - 2 * 3600
        os.utime(path, (past, past))
        if not removable:
            folder.chmod(0o500)
            self.addCleanup(folder.chmod, 0o700)
        return path

    def sweep(self):
        out = io.StringIO()
        call_command('sweep_orphan_files', '--delete', stdout=out)
        return out.getvalue()

    def records(self):
        swept = models.SecurityEvent.objects.get(event=maintenance.SWEPT_EVENT)
        removed = models.SecurityEvent.objects.get(event=maintenance.SWEEP_REMOVED_EVENT)
        return swept, removed

    def test_disposal_3_a_removal_that_failed_is_recorded_as_failed(self):
        path = self.orphan(removable=False)
        out = self.sweep()
        swept, removed = self.records()
        self.assertEqual(swept.data['orphans'], 1)
        self.assertEqual(removed.data, {'swept': str(swept.pk), 'sweep_deleted': 0, 'sweep_failed': 1, 'failed': []})
        self.assertGreaterEqual(removed.created_at, swept.created_at)
        self.assertTrue(path.exists())
        self.assertIn('deleted 0', out)
        self.assertIn('failed 1', out)
        self.assertNotIn(path.name, out)

    def test_a_removal_that_succeeded_is_recorded_as_done_and_reads_otherwise(self):
        path = self.orphan()
        self.sweep()
        swept, removed = self.records()
        self.assertEqual(removed.data, {'swept': str(swept.pk), 'sweep_deleted': 1, 'sweep_failed': 0, 'failed': []})
        self.assertFalse(path.exists())

    def test_a_removal_record_the_database_refuses_is_logged_and_undoes_nothing(self):
        path = self.orphan()
        with d2.security_events_refused(f"NEW.event = '{maintenance.SWEEP_REMOVED_EVENT}'"):
            with self.assertLogs('studio.maintenance', 'ERROR') as logged:
                out = self.sweep()
        self.assertIn("the record of the orphan sweep's removed files could not be written (ProgrammingError)",
                      [record.getMessage() for record in logged.records])
        self.assertFalse(path.exists())
        self.assertIn('deleted 1', out)
        self.assertEqual(models.SecurityEvent.objects.get(event=maintenance.SWEPT_EVENT).data['orphans'], 1)
        self.assertFalse(models.SecurityEvent.objects.filter(event=maintenance.SWEEP_REMOVED_EVENT).exists())

    def test_a_removal_that_raised_is_recorded_by_name_and_raised_again(self):
        self.orphan()
        with mock.patch.object(storage, 'sync_folder', side_effect=OSError('synthetic')), \
                self.assertLogs('studio.maintenance', 'ERROR') as logged, self.assertRaises(OSError):
            self.sweep()
        self.assertIn("the orphan sweep's removal failed (OSError)", [record.getMessage() for record in logged.records])
        swept, removed = self.records()
        self.assertEqual(removed.data, {'swept': str(swept.pk), 'failed': ['orphan_sweep']})
