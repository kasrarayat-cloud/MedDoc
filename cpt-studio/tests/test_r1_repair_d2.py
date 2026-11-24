"""Release 1, integrated refutation round 2, repair builder d2: the stop signal in disposal, and the daily maintenance's
record (D2-1 here; D2-2 follows).

- D2-1 (disposal-0 to disposal-4, one class): from the moment a transaction that destroys or records begins to commit
  until the command's next safe point, a stop signal - SIGTERM, SIGHUP or Ctrl-C - is held by the command's own handler
  (studio.disposal.STOP_SIGNAL_HOLD), never raised: the commit and the run's record go to their end, every certificate
  and ledger line printed names only what committed, and the command ends with the signal's status. After a
  destruction's commit the statement in flight is cancelled and the steps left are skipped, so a stop is not held long.
  Each finding's own input, through the command's handler - one real signal, sent with os.kill at a moment a
  sys.settrace hook picks; nothing in studio, Django or psycopg is patched - in this process, as call_command runs the
  command, in autocommit (TransactionTestCase: real COMMITs); the run's connection is closed afterwards, as the process's
  exit closes it, so what is read next is what committed. Then the class: close's commit, a plan's row, a replay's
  ledger rows and its next entry, a statement waiting on a lock after the commit, the files step, a signal after the
  run's steps, and the hold itself.

Synthetic practices only, on a test database and originals folders of the tests' own."""
from __future__ import annotations

import inspect
import io
import json
import os
import re
import signal
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from unittest import mock

import psycopg
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.models import Session
from django.core.management import CommandError, call_command
from django.db import connection, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.postgresql.base import DatabaseWrapper as PostgresWrapper
from django.db.models.query import QuerySet
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone
from psycopg import _connection_base, _cursor_base

from studio import disposal, jobs, maintenance, models, storage
from studio.management.commands import dispose as dispose_cmd
from tests import test_disposal as td
from tests.support import coding as f

Event = models.DisposalEvent
NAMED = re.compile(r'(?:Disposal|DisposalEvent) ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) \((\w+)\)')
LEDGER_LINE = re.compile(r'^Ledger line \(dispose --replay-ledger\): (\{.*\})$', re.M)
BLOCK_EXIT = transaction.Atomic.__exit__.__code__
DESTROY = disposal.destroy.__code__
STATEMENT_GEN = _cursor_base.BaseCursor._maybe_prepare_gen.__code__
COMMAND_GEN = _connection_base.BaseConnection._exec_command.__code__
CREATE = QuerySet.create.__code__


def source_line(function, text) -> int:
    """The line of ``function`` holding ``text`` (exactly one)."""
    lines, start = inspect.getsourcelines(function)
    found = [start + index for index, line in enumerate(lines) if text in line]
    assert len(found) == 1, (function, text, found)
    return found[0]


# psycopg 3.3: the line a cursor's statement generator runs once its statement was sent (send_query returned) and its
# result not yet read - where the lens's and the verifier's signals landed (disposal-0) - and the line _exec_command
# runs once it sent a COMMIT (disposal-1)
STATEMENT_SENT = source_line(_cursor_base.BaseCursor._maybe_prepare_gen, 'maybe_add_to_cache')
COMMAND_SENT = source_line(_connection_base.BaseConnection._exec_command, 'yield from generators.execute(self.pgconn)')
AFTER_POP = source_line(transaction.Atomic.__exit__, 'if connection.savepoint_ids:')  # disposal-2's line 230


def under_block_exit(frame, opener) -> bool:
    """Whether ``frame`` runs inside the Atomic.__exit__ of a block the function of code ``opener`` opened."""
    while frame is not None:
        if frame.f_code is BLOCK_EXIT:
            return frame.f_back is not None and frame.f_back.f_code is opener
        frame = frame.f_back
    return False


def called_from(frame, code, depth=4) -> bool:
    """Whether one of the ``depth`` frames above ``frame`` runs ``code``."""
    for _ in range(depth):
        frame = frame.f_back
        if frame is None:
            return False
        if frame.f_code is code:
            return True
    return False


def one_signal(accept, *, watch=(), signum=signal.SIGTERM):
    """(tracer, fired): a sys.settrace hook sending ONE real ``signum`` to this process with os.kill - the command's own
    handler takes it - at the first trace event accept(frame, event) is true for: every function's 'call' event, and
    the 'line' events of the frames whose code is in ``watch``."""
    fired, watch = [], set(watch)

    def tracer(frame, event, arg):
        if fired:
            return None
        if accept(frame, event):
            fired.append((frame.f_code.co_name, frame.f_lineno, event))
            os.kill(os.getpid(), signum)
            return None
        return tracer if frame.f_code in watch else None
    return tracer, fired


def after_arming(arm, fire):
    """An accept() for one_signal: true at the first event fire(frame, event) accepts once arm(frame, event) was."""
    armed = []

    def accept(frame, event):
        if not armed:
            if arm(frame, event):
                armed.append(True)
            return False
        return fire(frame, event)
    return accept


def statement_sent(frame, event) -> bool:
    return event == 'line' and frame.f_code is STATEMENT_GEN and frame.f_lineno == STATEMENT_SENT


def at_block_exit(opener, point, *, signum=signal.SIGTERM):
    """(tracer, fired): ONE real signal at ``point`` of the Atomic.__exit__ of the block ``opener`` (a code) opened -
    ('call', 0, 1) its call event, ('line', line, n) the n-th line event of that line."""
    fired, seen = [], {}

    def fire():
        fired.append(point)
        os.kill(os.getpid(), signum)

    def local(frame, event, arg):
        if fired:
            return None
        if event == 'line':
            seen[frame.f_lineno] = seen.get(frame.f_lineno, 0) + 1
            if point == ('line', frame.f_lineno, seen[frame.f_lineno]):
                fire()
                return None
        return local

    def tracer(frame, event, arg):
        if fired or event != 'call' or frame.f_code is not BLOCK_EXIT or frame.f_back is None \
                or frame.f_back.f_code is not opener:
            return None
        if point[0] == 'call':
            fire()
            return None
        return local
    return tracer, fired


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class HoldCase(TransactionTestCase):
    """One synthetic practice and its member; `dispose` run in this process with the command's own handlers."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        override = override_settings(ORIGINALS_DIR=Path(self.scratch.name) / 'originals')
        override.enable()
        self.addCleanup(override.disable)
        self.ws = f.workspace('Synthetic stop-hold practice')
        self.member = f.member(self.ws)

    def document(self, label, files=1):
        enc = f.encounter(self.ws, self.member, title=f'ZZ-TITLE-MARKER {label}')
        for number in range(files):
            f.upload(enc, self.member, data=f.PDF_BYTES + f' {label} {number}'.encode(), filename='zz-file-marker.pdf')
        return enc

    def plan(self, enc):
        return disposal.plan(disposal.document_scope(enc.pk), by='Synthetic Operator', reason='Synthetic: misfiled.')

    def dispose(self, *argv, tracer=None, ctrl_c=False):
        """`dispose <argv>` (the installer's idle answer given): (the status the one-shot ends with - 0, a CommandError's
        returncode, a SystemExit's code, or 'KeyboardInterrupt' -, stdout, stderr). ``ctrl_c``: Python's own SIGINT
        handler in place, as in a terminal. The run's connection is closed afterwards, as the process's exit closes it:
        what is read next is what committed."""
        out, err, status = io.StringIO(), io.StringIO(), 0
        before = signal.signal(signal.SIGINT, signal.default_int_handler if ctrl_c else signal.SIG_IGN)
        try:
            with td.installer_idle():
                if tracer is not None:
                    sys.settrace(tracer)
                try:
                    call_command('dispose', *argv, stdout=out, stderr=err)
                except SystemExit as exc:
                    status = exc.code
                except CommandError as exc:
                    status = exc.returncode
                    err.write(f'CommandError: {exc}')
                except KeyboardInterrupt:
                    status = 'KeyboardInterrupt'
                finally:
                    sys.settrace(None)
        finally:
            signal.signal(signal.SIGINT, before)
        connection.close()
        return status, out.getvalue(), err.getvalue()

    def execute(self, plan, **options):
        return self.dispose('--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator', '--approved-by',
                            'Synthetic Approver', '--authorization-ref', td.AUTH, **options)

    def assert_names_only_what_committed(self, out):
        """Every DisposalEvent the output names exists, at the stage it names; every ledger line it prints verifies and
        is one of the ledger's (dispose --ledger); nothing is said to be unrecorded; no title is printed."""
        named = NAMED.findall(out)
        self.assertTrue(named, out[:400])
        for pk, stage in named:
            self.assertTrue(Event.objects.filter(pk=pk, stage=stage).exists(), f'{stage} {pk} is named, never committed')
        ledger = {json.loads(line)['entry']['id'] for line in disposal.ledger_lines()}
        for line in LEDGER_LINE.findall(out):
            (entry,) = disposal.read_ledger([line])
            self.assertIn(entry['id'], ledger)
        self.assertNotIn('NOT RECORDED', out)
        self.assertNotIn('ZZ-TITLE-MARKER', out)

    def events_of(self, enc):
        return Event.objects.filter(encounter_ids__contains=[str(enc.pk)])

    def final_of(self, enc):
        return self.events_of(enc).get(stage__in=(Event.COMPLETED, Event.FAILED))

    def assert_held_to_the_record(self, enc, status, out, err):
        """A signal held from the commit on, before the steps after it: destroyed, recorded 'committed' and 'failed'
        (the steps stopped before the first, its file left and named), printed, ended with 143."""
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_names_only_what_committed(out)
        self.assertIsNotNone(models.Encounter._base_manager.get(pk=enc.pk).destroyed_at)
        self.assertEqual(sorted(self.events_of(enc).values_list('stage', flat=True)),
                         sorted([Event.PLANNED, disposal.COMMITTED, Event.FAILED]))
        failed = self.final_of(enc)
        self.assertEqual((failed.counts['rows_destroyed'], failed.counts['problems']), ('yes', ['files: Stopped']))
        for name in failed.files['remaining_names']:
            self.assertTrue(storage.stored_path(name).exists())  # left, and named for the new plan
        self.assertIn(f'Disposal {failed.pk} (failed)', out)


class FindingInputTests(HoldCase):
    """The five findings' inputs (refute-r2/disposal and refute-r2/verify/disposal-<n>), each through the command's own
    handler."""

    def test_disposal_0_a_signal_as_a_statement_after_the_commit_was_sent_is_recorded(self):
        arms = {'vacuum': lambda frame: frame.f_code is disposal._vacuum.__code__,
                'counts': lambda frame: frame.f_code is disposal.row_counts.__code__
                and frame.f_back.f_code.co_name == 'counts',
                'audit': lambda frame: frame.f_code is disposal._event_fields.__code__}
        for arm, armed_by in arms.items():
            with self.subTest(arm=arm):
                enc = self.document(f'sent {arm}')
                tracer, fired = one_signal(after_arming(lambda frame, event: event == 'call' and armed_by(frame),
                                                        statement_sent), watch={STATEMENT_GEN})
                status, out, err = self.execute(self.plan(enc), tracer=tracer)
                self.assertEqual(len(fired), 1)
                self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
                self.assert_names_only_what_committed(out)
                final = self.final_of(enc)
                self.assertIn(f'Disposal {final.pk} ({final.stage})', out)
                if arm == 'audit':  # after the run's steps: its record as it stands, the signal held to the end
                    self.assertEqual(final.stage, Event.COMPLETED)
                    self.assertIn(dispose_cmd.HELD_TEXT, err)
                else:
                    self.assertEqual(final.stage, Event.FAILED)
                    self.assertIn(f'{arm}: Stopped', final.counts['problems'])

    def test_disposal_1_a_signal_once_the_commit_was_sent_is_held_to_the_runs_record(self):
        enc = self.document('commit sent')
        tracer, fired = one_signal(after_arming(
            lambda frame, event: event == 'call' and frame.f_code is BLOCK_EXIT and frame.f_back.f_code is DESTROY,
            lambda frame, event: (event == 'line' and frame.f_code is COMMAND_GEN and frame.f_lineno == COMMAND_SENT
                                  and frame.f_locals.get('command') == b'COMMIT')), watch={COMMAND_GEN})
        status, out, err = self.execute(self.plan(enc), tracer=tracer)
        self.assertEqual(len(fired), 1)
        self.assert_held_to_the_record(enc, status, out, err)

    def destroy_exit_points(self):
        """Every trace event of destroy's Atomic.__exit__ in an uninterrupted run: its call, then each line event."""
        seen, counts = [('call', 0, 1)], {}

        def local(frame, event, arg):
            if event == 'line':
                counts[frame.f_lineno] = counts.get(frame.f_lineno, 0) + 1
                seen.append(('line', frame.f_lineno, counts[frame.f_lineno]))
            return local

        def tracer(frame, event, arg):
            if event == 'call' and frame.f_code is BLOCK_EXIT and frame.f_back is not None \
                    and frame.f_back.f_code is DESTROY:
                return local
            return None
        status, out, err = self.execute(self.plan(self.document('points')), tracer=tracer)
        self.assertEqual(status, 0, err[-800:])
        return seen

    def test_disposal_2_a_signal_at_any_point_of_the_blocks_exit_is_held_to_the_runs_record(self):
        points = self.destroy_exit_points()
        self.assertIn(('line', AFTER_POP, 1), points)  # the lens's line 230, and its 237 with every other line
        self.assertGreaterEqual(len(points), 10)
        for number, point in enumerate(points):
            with self.subTest(point=point):
                enc = self.document(f'exit {number}')
                tracer, fired = at_block_exit(DESTROY, point)
                status, out, err = self.execute(self.plan(enc), tracer=tracer)
                self.assertEqual(fired, [point])
                self.assert_held_to_the_record(enc, status, out, err)

    def test_disposal_3_a_signal_as_autocommit_comes_back_leaves_the_failed_row_committed(self):
        targets = {'django set_autocommit': BaseDatabaseWrapper.set_autocommit.__code__,
                   'backend _set_autocommit': PostgresWrapper._set_autocommit.__code__,
                   'psycopg set_autocommit': psycopg.Connection.set_autocommit.__code__}
        for label, code in targets.items():
            with self.subTest(at=label):
                enc = self.document(label)
                tracer, fired = one_signal(lambda frame, event, code=code: (
                    event == 'call' and frame.f_code is code and under_block_exit(frame, DESTROY)))
                status, out, err = self.execute(self.plan(enc), tracer=tracer)
                self.assertEqual(len(fired), 1)
                self.assert_held_to_the_record(enc, status, out, err)
                failed = self.final_of(enc)
                self.assertIn(failed.pk, [uuid.UUID(json.loads(line)['entry']['id']) for line in disposal.ledger_lines()])


class ReplayHoldTests(HoldCase):
    """disposal-4: a ledger replay of two documents after a restore, and a signal at the first entry's commit."""

    def destroyed_then_restored(self, count=2):
        with connection.cursor() as cursor:  # this ledger holds these disposals only
            cursor.execute('DELETE FROM studio_disposalevent')
        docs = [self.document(f'replay {number}') for number in range(count)]
        with td.installer_idle():
            for enc in docs:
                event, _ = disposal.execute(str(self.plan(enc).pk), by='Synthetic Operator',
                                            approved_by='Synthetic Approver', authorization_ref=td.AUTH)
                self.assertEqual(event.stage, Event.COMPLETED)
        ledger = Path(self.scratch.name) / f'ledger-{uuid.uuid4().hex}.jsonl'
        ledger.write_text('\n'.join(disposal.ledger_lines()) + '\n', encoding='utf-8')
        with connection.cursor() as cursor:  # the restored backup predates every ledger row
            cursor.execute('DELETE FROM studio_disposalevent')
        files = []
        for number, enc in enumerate(docs):
            models.Encounter._base_manager.filter(pk=enc.pk).update(title=f'ZZ-TITLE-MARKER restored {number}',
                                                                    destroyed_at=None, state='reviewed')
            revision = f.upload(models.Encounter._base_manager.get(pk=enc.pk), self.member,
                                data=f.PDF_BYTES + f' restored {number}'.encode(), filename='zz-file-marker.pdf')
            files.append(storage.stored_path(revision.source_file.storage_name))
        return docs, files, ledger

    def replay(self, ledger, **options):
        return self.dispose('--replay-ledger', str(ledger), '--execute', '--by', 'Synthetic Operator', '--approved-by',
                            'Synthetic Approver', '--authorization-ref', td.AUTH, **options)

    def assert_untouched(self, enc, path):
        tomb = models.Encounter._base_manager.get(pk=enc.pk)
        self.assertIsNone(tomb.destroyed_at)
        self.assertTrue(tomb.title.startswith('ZZ-TITLE-MARKER'))
        self.assertTrue(models.SourceFile._base_manager.filter(encounter_id=enc.pk).exists())
        self.assertTrue(path.exists())

    def assert_finished_by_a_second_replay(self, docs, files, ledger):
        status, out, err = self.replay(ledger)
        self.assertEqual(status, 0, err[-800:])
        for enc, path in zip(docs, files):
            self.assertIsNotNone(models.Encounter._base_manager.get(pk=enc.pk).destroyed_at)
            self.assertFalse(path.exists())

    def test_disposal_4_a_signal_at_the_first_entrys_commit_stops_the_replay_once_it_is_recorded(self):
        commit = BaseDatabaseWrapper.commit.__wrapped__.__code__  # Django's commit(), as Atomic.__exit__ calls it
        for name, signum, expected in (('SIGTERM', signal.SIGTERM, 128 + signal.SIGTERM),
                                       ('Ctrl-C', signal.SIGINT, 'KeyboardInterrupt')):
            with self.subTest(signal=name):
                docs, files, ledger = self.destroyed_then_restored()
                tracer, fired = one_signal(lambda frame, event: (
                    event == 'call' and frame.f_code is commit and under_block_exit(frame, DESTROY)), signum=signum)
                status, out, err = self.replay(ledger, tracer=tracer, ctrl_c=signum == signal.SIGINT)
                self.assertEqual(len(fired), 1)
                self.assertEqual(status, expected, err[-800:])
                self.assert_names_only_what_committed(out)
                first = Event.objects.filter(encounter_ids__contains=[str(docs[0].pk)], notes__startswith='replay=')
                self.assertEqual(sorted(first.values_list('stage', flat=True)), sorted([disposal.COMMITTED, Event.FAILED]))
                self.assertIsNotNone(models.Encounter._base_manager.get(pk=docs[0].pk).destroyed_at)
                self.assertTrue(files[0].exists())  # its steps stopped before the first: left, and named
                self.assertEqual(first.get(stage=Event.FAILED).files['remaining_names'],
                                 [str(files[0].relative_to(storage.root_path()))])
                self.assert_untouched(docs[1], files[1])  # the next entry was never begun
                self.assertFalse(Event.objects.filter(encounter_ids__contains=[str(docs[1].pk)],
                                                      notes__startswith='replay=').exists())
                self.assertIn('it was interrupted after its commit', err)
                self.assertIn('1 later entry was not attempted', err)
                self.assert_finished_by_a_second_replay(docs, files, ledger)

    def test_a_signal_at_the_commit_of_the_ledgers_rows_stops_the_replay_before_its_first_entry(self):
        docs, files, ledger = self.destroyed_then_restored()
        lines = [line for line in ledger.read_text(encoding='utf-8').split('\n') if line]
        tracer, fired = at_block_exit(disposal.replay.__code__, ('line', AFTER_POP, 1))
        status, out, err = self.replay(ledger, tracer=tracer)
        self.assertEqual(fired, [('line', AFTER_POP, 1)])
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assertIn(f'Ledger rows restored: {len(lines)}', out)
        self.assertEqual(Event.objects.count(), len(lines))  # committed, as the report says
        for enc, path in zip(docs, files):
            self.assert_untouched(enc, path)
        self.assertIn('it was interrupted before its run was recorded; no entry was carried out again before it', err)
        self.assert_finished_by_a_second_replay(docs, files, ledger)

    def test_a_signal_while_an_entry_is_recorded_stops_the_replay_before_the_next_entry(self):
        docs, files, ledger = self.destroyed_then_restored()
        tracer, fired = one_signal(after_arming(
            lambda frame, event: event == 'call' and frame.f_code is CREATE
            and called_from(frame, disposal._record.__code__), statement_sent), watch={STATEMENT_GEN})
        status, out, err = self.replay(ledger, tracer=tracer)  # the first entry's final INSERT, once it was sent
        self.assertEqual(len(fired), 1)
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_names_only_what_committed(out)
        first = Event.objects.filter(encounter_ids__contains=[str(docs[0].pk)], notes__startswith='replay=')
        self.assertEqual(sorted(first.values_list('stage', flat=True)), sorted([disposal.COMMITTED, Event.COMPLETED]))
        self.assertFalse(files[0].exists())
        self.assert_untouched(docs[1], files[1])
        self.assertIn('it was interrupted before its run was recorded; 1 ledger entry was carried out again before it',
                      err)
        self.assert_finished_by_a_second_replay(docs, files, ledger)


class HeldClassTests(HoldCase):
    """The class beyond the five inputs: every transaction the command commits that destroys or records."""

    def session(self, **options):
        params = {key: value for key, value in connection.get_connection_params().items()
                  if key not in ('cursor_factory', 'context')}
        return psycopg.connect(**params, **options)

    def test_a_signal_at_the_commit_that_closes_a_practice_is_held_until_it_is_printed(self):
        reason = td.reason_file(self.scratch.name)
        tracer, fired = at_block_exit(disposal.close.__code__, ('line', AFTER_POP, 1))
        status, out, err = self.dispose('--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                                        '--reason-file', reason, tracer=tracer)
        self.assertEqual(fired, [('line', AFTER_POP, 1)])
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        closed = Event.objects.get(stage=Event.CLOSED, workspace_id=self.ws.pk)
        self.assertIsNotNone(models.Workspace.objects.get(pk=self.ws.pk).closed_at)
        self.assertIn(f'DisposalEvent {closed.pk} (closed)', out)
        self.assertIn(dispose_cmd.HELD_TEXT, err)

    def test_a_signal_as_a_plans_row_is_written_is_held_until_the_plan_is_printed(self):
        enc = self.document('plan row')
        reason = td.reason_file(self.scratch.name, 'Synthetic: misfiled.')
        tracer, fired = one_signal(after_arming(
            lambda frame, event: event == 'call' and frame.f_code is CREATE and called_from(frame, disposal.plan.__code__),
            statement_sent), watch={STATEMENT_GEN})
        status, out, err = self.dispose('--plan', '--encounter', str(enc.pk), '--by', 'Synthetic Operator',
                                        '--reason-file', reason, tracer=tracer)
        self.assertEqual(len(fired), 1)
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        plan = self.events_of(enc).get(stage=Event.PLANNED)
        self.assertIn(f'Plan {plan.pk} for document {enc.pk}', out)
        self.assertIn(f'manifest sha256 {plan.manifest_digest}', out)
        self.assertIn(dispose_cmd.HELD_TEXT, err)

    def test_the_files_step_stops_at_the_next_file(self):
        enc = self.document('three files', files=3)
        names = sorted(models.SourceFile.objects.filter(encounter=enc).values_list('storage_name', flat=True))
        tracer, fired = one_signal(lambda frame, event: event == 'call' and frame.f_code is storage.delete_stored.__code__)
        status, out, err = self.execute(self.plan(enc), tracer=tracer)
        self.assertEqual(len(fired), 1)
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_names_only_what_committed(out)
        failed = self.final_of(enc)
        self.assertEqual((failed.stage, failed.counts['problems']), (Event.FAILED, ['files: Stopped']))
        self.assertEqual((failed.files['deleted'], failed.files['remaining']), (1, 2))  # the one under way, and no more
        left = [name for name in names if storage.stored_path(name).exists()]
        self.assertEqual(left, failed.files['remaining_names'])

    def test_a_signal_after_the_runs_steps_leaves_its_record_as_it_stands(self):
        enc = self.document('after the steps')
        tracer, fired = one_signal(after_arming(
            lambda frame, event: event == 'call' and frame.f_code is CREATE
            and called_from(frame, disposal._record.__code__), statement_sent), watch={STATEMENT_GEN})
        status, out, err = self.execute(self.plan(enc), tracer=tracer)  # the final INSERT, once it was sent
        self.assertEqual(len(fired), 1)
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_names_only_what_committed(out)
        final = self.final_of(enc)
        self.assertEqual(final.stage, Event.COMPLETED)
        self.assertTrue(out.startswith('CPT Studio destruction certificate'), out[:200])
        self.assertIn(dispose_cmd.HELD_TEXT, err)
        self.assertNotIn(dispose_cmd.INTERRUPTED_TEXT, err)  # nothing is left to finish

    def test_a_count_waiting_on_a_lock_after_the_commit_is_cancelled_and_the_stop_is_not_held_long(self):
        enc = self.document('lock')
        plan = self.plan(enc)
        holder, watcher = self.session(), self.session(autocommit=True)
        main, done, timing = threading.get_ident(), threading.Event(), {}

        def stop_once_it_waits():
            deadline = time.monotonic() + 60
            while not done.is_set() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = "
                    "'Lock' AND query LIKE 'SELECT COUNT(*)%'").fetchone()[0]
                if waiting:
                    timing['sent'] = time.monotonic()
                    signal.pthread_kill(main, signal.SIGTERM)
                    break
                time.sleep(0.02)
            done.wait(30)  # the lock stays until the command has ended - 30 s at most, so a hold that lasts ends
            holder.rollback()

        watching = threading.Thread(target=stop_once_it_waits, daemon=True)

        def lock_once_vacuumed(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('VACUUM') and watching.ident is None:  # the counts come next: one of them must wait
                holder.execute('LOCK TABLE studio_sourcefile IN ACCESS EXCLUSIVE MODE')
                watching.start()
            return result
        try:
            with connection.execute_wrapper(lock_once_vacuumed):
                status, out, err = self.execute(plan)
            timing['ended'] = time.monotonic()
        finally:
            done.set()
            if watching.ident is not None:
                watching.join(timeout=60)
            holder.rollback()
            holder.close()
            watcher.close()
        self.assertIn('sent', timing)  # the control: the signal went while a count waited on the lock
        held = timing['ended'] - timing['sent']
        self.assertLess(held, 10, f'the stop was held {held:.1f} s')
        self.assertEqual(status, 128 + signal.SIGTERM, err[-800:])
        self.assert_names_only_what_committed(out)
        final = self.final_of(enc)
        self.assertEqual(final.stage, Event.FAILED)
        self.assertIn('counts: Stopped', final.counts['problems'])


class HoldUnitTests(SimpleTestCase):
    """The hold itself, and what the command installs."""

    def tearDown(self):
        disposal.STOP_SIGNAL_HOLD.reset(armed=False)
        super().tearDown()

    def test_unarmed_it_holds_nothing(self):
        hold = disposal.STOP_SIGNAL_HOLD
        hold.reset(armed=False)
        self.assertTrue(hold.hold())
        self.assertFalse(hold.keep(dispose_cmd.Stopped(signal.SIGTERM)))
        hold.safe_point()  # nothing kept: nothing raised

    def test_armed_it_keeps_the_first_signal_from_a_hold_to_the_next_safe_point(self):
        hold, first, second = disposal.STOP_SIGNAL_HOLD, dispose_cmd.Stopped(signal.SIGTERM), KeyboardInterrupt()
        hold.reset(armed=True)
        self.assertFalse(hold.keep(first))  # before a commit: raised where the command is
        hold.hold()
        self.assertTrue(hold.keep(first))
        self.assertTrue(hold.keep(second))
        self.assertIs(hold.pending, first)
        with self.assertRaises(dispose_cmd.Stopped) as raised:
            hold.safe_point()
        self.assertIs(raised.exception, first)
        self.assertFalse(hold.keep(second))  # after the safe point: raised again, until the next hold
        hold.safe_point()

    def test_the_command_takes_ctrl_c_only_from_pythons_own_handler(self):
        before = signal.getsignal(signal.SIGINT)
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            with dispose_cmd.stop_signals_raise():
                self.assertIs(signal.getsignal(signal.SIGINT), signal.SIG_IGN)  # an ignored Ctrl-C stays ignored
                self.assertIs(signal.getsignal(signal.SIGTERM), dispose_cmd._stop)
                self.assertTrue(disposal.STOP_SIGNAL_HOLD.armed)
            signal.signal(signal.SIGINT, signal.default_int_handler)
            with dispose_cmd.stop_signals_raise():
                self.assertIs(signal.getsignal(signal.SIGINT), dispose_cmd._stop)
            self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)
            self.assertFalse(disposal.STOP_SIGNAL_HOLD.armed)
        finally:
            signal.signal(signal.SIGINT, before)

