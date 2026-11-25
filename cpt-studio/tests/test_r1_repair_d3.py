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
