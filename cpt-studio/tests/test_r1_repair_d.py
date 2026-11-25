"""Release 1, integrated refutation round 1, repair builder D: disposal, the ledger and the export.

- D1 (phileak-0, dataloss-0, and the command half of phileak-1 / dataloss-3): a disposal's reason leaves the database
  only as its digest - in every ledger entry and certificate, so in no receipt or log - while the DisposalEvent rows keep
  its text; a replay's own events name the digest; a ledger is read line by line on the newline alone; a person's name
  holding a line break is refused.
- D2 (dataloss-2): a real SIGTERM or SIGHUP while a statement after the commit waits on a lock is recorded 'failed' with
  its certificate, and the command still ends with 128 + the signal's number.
- D3 (failclosed-6): an export whose 'exported' DisposalEvent cannot be written is removed, and the command says nothing
  was kept; a copy that cannot be removed is said to remain.
- D4 (dataloss-4): a real SIGTERM at any line from the commit to the final DisposalEvent's INSERT leaves the run recorded
  'failed' with its certificate printed; at any line before the commit it destroys and records nothing, as before.
  (Round 2, repair d2, tests/test_r1_repair_d2.py: the stop signals are held from the block's last statement, so the
  with block's exit is on the commit's side, and a signal after the run's steps leaves its record as it stands.)

Synthetic practices only, on a test database and originals folders of the tests' own."""
from __future__ import annotations

import dis
import hashlib
import inspect
import io
import json
import os
import signal
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import psycopg
from django.core.management import CommandError, call_command
from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from studio import disposal, models, record_bundle, storage
from studio.management.commands import dispose as dispose_cmd
from tests import test_disposal as td
from tests.support import coding as f

Event = models.DisposalEvent
# the lens's reason (phileak-0): the misfiled-document case D1 is built for, naming the document's patient
PLAN_REASON = ('ZZ-REASON-MARKER Misfiled upload: the colonoscopy note of Jane Roe (DOB 1970-01-02) was uploaded to '
               'the wrong practice; destroy it the same day.\n')
# the lens's separators (dataloss-0), all three in one reason
SEPARATED_REASON = ('Synthetic: the practice ended its contract.\u2028It chose destruction in writing.\u2029Signed by '
                    'both.\u0085Filed the same day.')
REASON_WORDS = ('ZZ-REASON-MARKER', 'Jane Roe', '1970-01-02')


def digest_of(reason) -> str:
    """The digest a ledger and a certificate carry for ``reason`` as read from its file (stripped, as stored)."""
    return 'sha256:' + hashlib.sha256(reason.strip().encode('utf-8')).hexdigest()


def echoes(reason, output) -> list:
    """What of ``reason`` ``output`` repeats, read as the installer's guard reads it (ops/install.py reason_values and
    assert_no_secret): its whole text, and each of its lines of 12 characters or more."""
    text = reason.strip()
    parts = [text, *[line.strip() for line in text.splitlines() if len(line.strip()) >= 12]]
    return [part for part in parts if part in output] + [word for word in REASON_WORDS if word in output]


class ReasonCase(td.RepairCase):
    def destroy_practice(self, reason):
        """Practice A closed, planned and destroyed with ``reason`` (the same file for each step)."""
        self.seed()
        path = td.reason_file(self.scratch.name, reason)
        printed = {'close': self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                         '--reason-file', path),
                   'plan': self.command('--plan', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                        '--reason-file', path)}
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        printed['execute'], error = self.carry_out(plan)
        self.assertIsNone(error, printed['execute'])
        return printed

    def restore_older_backup(self):
        """What a restore from a backup older than the disposal brings back (tests.test_disposal.LedgerTests): practice A
        open with a document's rows and file and its memberships on - and none of the ledger's rows."""
        self.forget_the_ledger()
        models.Workspace.objects.filter(pk=self.ws.pk).update(closed_at=None)
        models.Membership.objects.filter(workspace=self.ws).update(active=True)
        revision = self.restore_document(self.a_note, 'R')
        return storage.stored_path(revision.source_file.storage_name)

    def assert_destroyed_again(self, stored):
        tomb = models.Encounter._base_manager.get(pk=self.a_note.pk)
        self.assertIsNotNone(tomb.destroyed_at)
        self.assertEqual((tomb.title, tomb.state), ('', disposal.TOMBSTONE_STATE))
        self.assertFalse(stored.exists())
        self.assertIsNotNone(models.Workspace.objects.get(pk=self.ws.pk).closed_at)
        self.assertFalse(models.Membership.objects.filter(workspace=self.ws, active=True).exists())


class ReasonDigestTests(ReasonCase, TestCase):
    """D1, phileak-0 and the command half of phileak-1 / dataloss-3: the reason's words reach no output of dispose or
    export_workspace - not the certificate (whose ledger line carried them into the installer's receipt and log), not
    the ledger - only its digest; the DisposalEvent rows keep the text."""

    def test_the_lenss_execute_certificate_and_ledger_hold_the_reasons_digest_never_its_words(self):
        # the lens's input: the plan's reason names the patient; execute is given a reason file of its own
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        own = td.reason_file(self.scratch.name, 'Ticket 4521: carry out the approved plan.\n')
        printed = {'close': self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                         '--reason-file', reason),
                   'plan': self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace',
                                        '--reason-file', reason)}
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        with td.installer_idle():
            printed['execute'], error = self.dispose_command(
                '--execute', '--plan', str(plan.pk), '--by', 'Ada Lovelace', '--approved-by', 'Grace Hopper',
                '--reason-file', own, '--authorization-ref', td.AUTH)
        self.assertIsNone(error, printed['execute'])
        printed['ledger'] = self.command('--ledger')
        for name, output in printed.items():
            with self.subTest(output=name):
                self.assertEqual(echoes(PLAN_REASON, output), [])
        digest = digest_of(PLAN_REASON)
        self.assertIn(f'Reason: {digest} (', printed['execute'])
        line = next(line for line in printed['execute'].splitlines() if line.startswith('Ledger line'))
        self.assertIn(f'"reason":"{digest}"', line)
        entries = disposal.read_ledger(printed['ledger'].split('\n'))
        self.assertEqual([entry['stage'] for entry in entries],
                         [Event.CLOSED, Event.PLANNED, disposal.COMMITTED, Event.COMPLETED])
        self.assertEqual({entry['reason'] for entry in entries}, {digest})
        # the rows keep the text (spec 3.1)
        self.assertEqual(set(Event.objects.values_list('reason', flat=True)), {PLAN_REASON.strip()})

    def test_a_failed_runs_certificate_holds_no_reason_words_either(self):
        # dataloss-3's second shape: the run fails after the commit (the practice's folder read-only) and its
        # certificate says what remains - with the reason only as its digest
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace', '--reason-file', reason)
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        with td.read_only(storage.workspace_folder(self.ws.pk)):
            output, error = self.carry_out(plan)
        self.assertIn('did not complete', error)
        self.assertIn('Files remaining, by storage name', output)
        self.assertEqual(echoes(PLAN_REASON, output + error), [])
        self.assertIn(f'Reason: {digest_of(PLAN_REASON)} (', output)
        self.assertEqual(Event.objects.get(stage=Event.FAILED).reason, PLAN_REASON.strip())

    def test_an_unrecorded_runs_certificate_holds_no_reason_words_either(self):
        # the run's final event cannot be written: its certificate, printed instead, is the record
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace', '--reason-file', reason)
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        real = Event.objects.create

        def create(**values):
            if values.get('stage') in (Event.COMPLETED, Event.FAILED):
                raise RuntimeError('synthetic: the final DisposalEvent cannot be written')
            return real(**values)
        with mock.patch.object(Event.objects, 'create', side_effect=create):
            output, error = self.carry_out(plan)
        self.assertIn('NOT RECORDED', output)
        self.assertEqual(echoes(PLAN_REASON, output + error), [])
        self.assertIn(f'Reason: {digest_of(PLAN_REASON)} (', output)

    def test_an_exports_output_and_ledger_entry_hold_only_its_reasons_digest(self):
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        printed = io.StringIO()
        call_command('export_workspace', '--workspace', str(self.ws.pk), '--out', str(Path(self.scratch.name) / 'out'),
                     '--by', 'Ada Lovelace', '--reason-file', reason, stdout=printed)
        ledger = self.command('--ledger')
        for output in (printed.getvalue(), ledger):
            self.assertEqual(echoes(PLAN_REASON, output), [])
        event = Event.objects.get(stage=Event.EXPORTED)
        self.assertEqual(event.reason, PLAN_REASON.strip())
        (entry,) = [entry for entry in disposal.read_ledger(ledger.split('\n')) if entry['id'] == str(event.pk)]
        self.assertEqual(entry['reason'], digest_of(PLAN_REASON))

    def test_a_replay_names_the_digest_it_replays_and_the_rows_it_writes_back_hold_it(self):
        self.destroy_practice(PLAN_REASON)
        ledger = self.ledger_file()
        lines = [line for line in ledger.read_text(encoding='utf-8').split('\n') if line]
        original = disposal.read_ledger(lines)
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assert_destroyed_again(stored)
        for text in (dry, output):
            self.assertEqual(echoes(PLAN_REASON, text), [])
        digest = digest_of(PLAN_REASON)
        replayed = Event.objects.filter(notes__startswith=f'replay={original[-1]["id"]};')
        self.assertEqual(sorted(replayed.values_list('stage', flat=True)), sorted([disposal.COMMITTED, Event.COMPLETED]))
        self.assertEqual(set(replayed.values_list('reason', flat=True)), {digest})  # the replay's own events
        for entry in original:  # written back from the ledger: the digest where the original held the text
            row = Event.objects.get(pk=entry['id'])
            self.assertEqual(row.reason, digest)
            self.assertEqual(disposal._entry(row), entry)
        again = {json.loads(line)['entry']['id']: line for line in self.command('--ledger').split('\n') if line}
        for line in lines:  # each written-back row's ledger line, MAC included, is the original's, byte for byte
            self.assertEqual(again[json.loads(line)['entry']['id']], line)


class LedgerLineTests(ReasonCase, TestCase):
    """D1, dataloss-0: a genuine ledger replays whatever its reasons hold - U+2028, U+2029, U+0085 - read line by line on
    the newline alone; and a ledger written before this repair, whose lines hold such a reason's text raw, replays too."""

    def test_the_lenss_ledger_whose_reason_holds_line_separators_replays_after_a_restore(self):
        self.destroy_practice(SEPARATED_REASON)
        ledger = self.ledger_file()
        text = ledger.read_text(encoding='utf-8')
        self.assertFalse({'\u2028', '\u2029', '\u0085'} & set(text))  # the digest: nothing of the reason is in it
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assertIn('Ledger rows restored: 4', output)
        self.assert_destroyed_again(stored)

    def test_a_ledger_holding_a_reasons_separators_raw_is_read_on_the_newline_alone(self):
        # a ledger as the integration head wrote it (before the digest): each entry's reason is the row's text, raw in
        # its line (json.dumps with ensure_ascii=False), its MAC over that entry - genuine, and cut by str.splitlines()
        self.destroy_practice(SEPARATED_REASON)
        texts = {str(pk): reason for pk, reason in Event.objects.values_list('pk', 'reason')}
        old = []
        for line in self.ledger_file().read_text(encoding='utf-8').split('\n'):
            if line:
                entry = json.loads(line)['entry']
                entry['reason'] = texts[entry['id']]
                old.append(json.dumps({'entry': entry, 'mac': disposal._mac(entry)}, sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False))
        ledger = Path(self.scratch.name) / 'ledger-before-the-repair.jsonl'
        ledger.write_text('\n'.join(old), encoding='utf-8')
        written = ledger.read_text(encoding='utf-8')
        self.assertTrue({'\u2028', '\u2029', '\u0085'} <= set(written))  # the control: raw in the file
        self.assertGreater(len(written.splitlines()), len(old))  # the control: splitlines() cuts the genuine lines
        self.assertEqual(len(disposal.read_ledger(written.split('\n'))), len(old))
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assert_destroyed_again(stored)
        replayed = Event.objects.filter(notes__startswith='replay=')
        self.assertEqual(set(replayed.values_list('reason', flat=True)), {digest_of(SEPARATED_REASON)})
        self.assertNotIn('\u2028', output)


class OneLineNameTests(SimpleTestCase):
    """D1's check of every other output: a name person() accepts is printed in every certificate and ledger line. A
    line break in it used to become a space; it is refused - every character str.splitlines() breaks a line at."""

    BREAKS = '\n\x0b\x0c\r\x1c\x1d\x1e\x85\u2028\u2029'  # in code point order

    def test_a_name_holding_a_line_break_is_refused(self):
        for ch in self.BREAKS:
            with self.subTest(ch=ascii(ch)):
                with self.assertRaisesMessage(disposal.Refused, '--by is one line'):
                    disposal.person(f'Ada{ch}Lovelace')
                with self.assertRaisesMessage(disposal.Refused, '--approved-by is one line'):
                    disposal.two_people('Grace Hopper', f'Ada Lovelace{ch}')

    def test_the_refused_characters_are_exactly_pythons_line_breaks(self):
        found = ''.join(chr(code) for code in range(0x110000) if not 0xD800 <= code <= 0xDFFF
                        and disposal.breaks_a_line(chr(code)))
        self.assertEqual(found, self.BREAKS)

    def test_other_white_space_is_still_one_space_and_names_pass(self):
        self.assertEqual(disposal.person('Ada\tLovelace  '), 'Ada Lovelace')
        self.assertEqual(disposal.two_people('Ada Lovelace', 'Grace Hopper'), ('Ada Lovelace', 'Grace Hopper'))


# --- D2: a real stop signal while a statement after the commit waits on a lock -------------------------------------------

@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class StopSignalDuringAStatementTests(TransactionTestCase):
    """D2, dataloss-2: the lens's run - one document planned, `dispose --execute` in this process under the command's own
    handlers, and when its VACUUM (ANALYZE) starts another session holds a lock it waits for, as an autovacuum or an
    ANALYZE would. Once the VACUUM is seen waiting (pg_stat_activity, never a timer), a real SIGTERM or SIGHUP goes to
    the main thread. The statement is cancelled, the run is recorded 'failed' with its certificate, and the command ends
    with 128 + the signal's number. The control: Ctrl-C (SIGINT), which psycopg always cancelled for. Since round 2
    (repair d2) the signal is held from the commit on and the VACUUM ended by a cancel request, so it ends on an error
    result, read as one: _vacuum reports it failed (vacuum=failed), where the interrupt raised through it used to leave it
    'not run'."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        override = override_settings(ORIGINALS_DIR=Path(folder.name) / 'originals')
        override.enable()
        self.addCleanup(override.disable)
        self.ws = f.workspace('Synthetic stop-signal practice')
        self.member = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.member, title='ZZ-TITLE-MARKER vacuum')
        f.upload(self.enc, self.member, data=f.PDF_BYTES + b' vacuum', filename='zz-file-marker.pdf')

    def session(self, **options):
        params = {key: value for key, value in connection.get_connection_params().items()
                  if key not in ('cursor_factory', 'context')}
        return psycopg.connect(**params, **options)

    def interrupted_during_the_vacuum(self, signum):
        """(exit, what was printed, stderr, the run's final DisposalEvent or None, whether the signal went)."""
        plan = disposal.plan(disposal.document_scope(self.enc.pk), by='Synthetic Operator', reason='Synthetic: misfiled.')
        names = list(models.SourceFile.objects.filter(encounter=self.enc).values_list('storage_name', flat=True))
        with connection.cursor() as cursor:  # no timeout ends the wait: only the signal, or the lock's release
            cursor.execute('SET lock_timeout = 0')
            cursor.execute('SET statement_timeout = 0')
        holder, watcher = self.session(), self.session(autocommit=True)
        main, sent, done = threading.get_ident(), [], threading.Event()

        def signal_once_it_waits():
            deadline = time.monotonic() + 90
            while not done.is_set() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = "
                    "'Lock' AND query LIKE 'VACUUM (ANALYZE)%'").fetchone()[0]
                if waiting:
                    sent.append(signum)
                    signal.pthread_kill(main, signum)
                    return
                time.sleep(0.02)
            holder.rollback()  # never seen waiting: the lock goes, so the run cannot hang

        watching = threading.Thread(target=signal_once_it_waits, daemon=True)

        def lock_first(execute, sql, params, many, context):
            if sql.startswith('VACUUM') and watching.ident is None:
                holder.execute('LOCK TABLE studio_sourcefile IN SHARE UPDATE EXCLUSIVE MODE')  # held until rollback
                watching.start()
            return execute(sql, params, many, context)

        late = []  # a signal after the command put its handlers back is recorded here, never fatal to the run
        before = {number: signal.signal(number, lambda n, frame: late.append(n))
                  for number in (signal.SIGTERM, signal.SIGHUP)}
        before[signal.SIGINT] = signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl-C, as in a terminal
        out, err, code = io.StringIO(), io.StringIO(), None
        try:
            with td.installer_idle(), connection.execute_wrapper(lock_first):
                call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                             '--approved-by', 'Synthetic Approver', '--authorization-ref', td.AUTH, stdout=out,
                             stderr=err)
        except SystemExit as exc:
            code = exc.code
        except KeyboardInterrupt:
            code = 'KeyboardInterrupt'
        finally:
            done.set()
            if watching.ident is not None:
                watching.join(timeout=120)
            holder.rollback()
            holder.close()
            watcher.close()
            for number, handler in before.items():
                signal.signal(number, handler)
        connection.close()  # the run's own connection, as it was left: a fresh one reads what was recorded
        self.assertEqual(late, [])
        final = Event.objects.filter(stage__in=(Event.COMPLETED, Event.FAILED)).first()
        left = [name for name in names if storage.stored_path(name).exists()]
        self.assertEqual(left, [])  # the files went before the VACUUM began
        return code, out.getvalue(), err.getvalue(), final, sent

    def assert_recorded(self, signum, expected_exit, raised_as):
        code, printed, errors, final, sent = self.interrupted_during_the_vacuum(signum)
        self.assertEqual(sent, [signum])  # the control: the signal went while the VACUUM waited
        self.assertEqual(code, expected_exit)
        self.assertEqual(sorted(Event.objects.values_list('stage', flat=True)),
                         sorted([Event.PLANNED, disposal.COMMITTED, Event.FAILED]))
        self.assertIsNotNone(final)
        self.assertEqual(final.counts['problems'], [f'vacuum: {raised_as}'])
        self.assertIsInstance(final.counts['audit_rows_kept'], int)  # the count after the interrupt ran
        self.assertIn('vacuum=failed', final.notes)  # cancelled (round 2): it ended on an error
        self.assertTrue(printed.startswith('CPT Studio destruction: NOT COMPLETE'), printed[:200])
        self.assertIn(f'Disposal {final.pk} (failed)', printed)
        self.assertIn(dispose_cmd.INTERRUPTED_TEXT, errors)
        self.assertNotIn('ZZ-TITLE-MARKER', printed)

    def test_a_real_sigterm_while_the_vacuum_waits_on_a_lock(self):
        self.assert_recorded(signal.SIGTERM, 128 + signal.SIGTERM, 'Stopped')

    def test_a_real_sighup_while_the_vacuum_waits_on_a_lock(self):
        self.assert_recorded(signal.SIGHUP, 128 + signal.SIGHUP, 'Stopped')

    def test_control_ctrl_c_while_the_vacuum_waits_on_a_lock(self):
        self.assert_recorded(signal.SIGINT, 'KeyboardInterrupt', 'KeyboardInterrupt')


# --- D3: an export whose record cannot be written ------------------------------------------------------------------------

@contextmanager
def exported_rows_fail(body):
    """A BEFORE INSERT trigger on studio_disposalevent for stage 'exported' whose function's body is ``body``: the
    verifier's faults, made at the database - no code under test is patched. Dropped afterwards, on a fresh connection
    (the fault may have ended the old one)."""
    name = 'r1repd_exported_fault'
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {body} '
                       'RETURN NEW; END $$')
        cursor.execute(f"CREATE TRIGGER {name} BEFORE INSERT ON studio_disposalevent FOR EACH ROW WHEN "
                       f"(NEW.stage = 'exported') EXECUTE FUNCTION {name}()")
    try:
        yield
    finally:
        connection.close()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER IF EXISTS {name} ON studio_disposalevent')
            cursor.execute(f'DROP FUNCTION IF EXISTS {name}()')


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class UnrecordedExportTests(TransactionTestCase):
    """D3, failclosed-6: export_workspace writes a whole practice's copy, then its 'exported' DisposalEvent. When that
    row cannot be written - the database refuses it, goes away, or Ctrl-C comes while it is written - the copy is
    removed as a half-written one is, and the command says nothing was kept; when the copy cannot be removed, it says a
    copy may remain. In autocommit, as the command runs."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        override = override_settings(ORIGINALS_DIR=self.root / 'originals')
        override.enable()
        self.addCleanup(override.disable)
        self.ws, other = f.workspace('Synthetic A'), f.workspace('Synthetic B')
        for ws in (self.ws, other):
            user = f.member(ws)
            enc = f.encounter(ws, user, title='ZZ-TITLE-MARKER export')
            f.upload(enc, user, data=f.PDF_BYTES + b' ZZ-TEXT-MARKER ' + str(ws.pk).encode(), filename='zz-file-marker.pdf')
        self.reason = td.reason_file(self.root, 'Synthetic: the practice ended its contract and asked for its data.')
        self.originals = td.folder_digests(self.ws.pk)
        (self.root / 'exports').mkdir(mode=0o700)

    def export(self, name='export'):
        """(the export folder, stdout, stderr, what ended the command or None)."""
        out, printed, errors, raised = self.root / 'exports' / name, io.StringIO(), io.StringIO(), None
        try:
            call_command('export_workspace', '--workspace', str(self.ws.pk), '--out', str(out), '--by',
                         'Synthetic Operator', '--reason-file', self.reason, stdout=printed, stderr=errors)
        except (CommandError, KeyboardInterrupt) as exc:
            raised = exc
        return out, printed.getvalue(), errors.getvalue(), raised

    def assert_nothing_kept(self, out, printed, raised):
        self.assertFalse(os.path.lexists(out))
        self.assertEqual(os.listdir(self.root / 'exports'), [])
        connection.close()  # a fresh connection reads what was recorded
        self.assertFalse(Event.objects.filter(stage=Event.EXPORTED).exists())
        self.assertEqual(td.folder_digests(self.ws.pk), self.originals)  # the export only read the originals
        for marker in ('ZZ-TITLE-MARKER', 'ZZ-TEXT-MARKER', 'zz-file-marker'):
            self.assertNotIn(marker, printed + str(raised))

    def test_control_an_export_with_its_record(self):
        out, printed, errors, raised = self.export()
        self.assertIsNone(raised)
        event = Event.objects.get(stage=Event.EXPORTED)
        self.assertEqual(event.manifest_digest, hashlib.sha256((out / 'manifest.json').read_bytes()).hexdigest())
        self.assertIn(f'DisposalEvent {event.pk} (exported)', printed)

    def test_the_lenss_export_whose_record_the_database_refuses_keeps_nothing(self):
        with exported_rows_fail("RAISE EXCEPTION 'synthetic: the exported record is refused';"):
            out, printed, errors, raised = self.export()
        self.assertIsInstance(raised, CommandError)
        self.assertIn("The export's DisposalEvent could not be written (", str(raised))
        self.assertIn('nothing was kept', str(raised))
        self.assert_nothing_kept(out, printed, raised)

    def test_an_export_whose_database_goes_away_at_the_record_keeps_nothing(self):
        with exported_rows_fail('PERFORM pg_terminate_backend(pg_backend_pid());'):
            out, printed, errors, raised = self.export()
        self.assertIsInstance(raised, CommandError)
        self.assertIn('(OperationalError), so the export was removed: nothing was kept', str(raised))
        self.assert_nothing_kept(out, printed, raised)

    def test_ctrl_c_while_the_record_is_written_keeps_nothing_and_goes_on(self):
        # a real SIGINT once pg_stat_activity shows the row's INSERT running (its trigger sleeps)
        watcher, main, sent, done = None, threading.get_ident(), [], threading.Event()

        def interrupt_once_it_runs():
            deadline = time.monotonic() + 90
            while not done.is_set() and time.monotonic() < deadline:
                running = watcher.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND state = 'active' AND "
                    "query LIKE 'INSERT INTO \"studio_disposalevent\"%'").fetchone()[0]
                if running:
                    sent.append(True)
                    signal.pthread_kill(main, signal.SIGINT)
                    return
                time.sleep(0.02)

        params = {key: value for key, value in connection.get_connection_params().items()
                  if key not in ('cursor_factory', 'context')}
        watcher = psycopg.connect(**params, autocommit=True)
        watching = threading.Thread(target=interrupt_once_it_runs, daemon=True)
        before = signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl-C, as in a terminal

        def start_watching(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "studio_disposalevent"') and watching.ident is None:
                watching.start()
            return execute(sql, params, many, context)
        try:
            with exported_rows_fail('PERFORM pg_sleep(60);'), connection.execute_wrapper(start_watching):
                out, printed, errors, raised = self.export()
        finally:
            done.set()
            if watching.ident is not None:
                watching.join(timeout=120)
            watcher.close()
            signal.signal(signal.SIGINT, before)
        self.assertEqual(sent, [True])  # the control: the signal went while the row was written
        self.assertIsInstance(raised, KeyboardInterrupt)  # it goes on as an interrupt
        self.assertIn("Interrupted (KeyboardInterrupt) while the export's DisposalEvent was written: the export was "
                      'removed, and nothing was kept', errors)
        self.assert_nothing_kept(out, printed, raised)

    def test_a_copy_that_cannot_be_removed_is_said_to_remain(self):
        # the record is refused, and one folder of the copy cannot be emptied (made read-only as the row is written)
        made = []

        def lock_a_folder(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "studio_disposalevent"') and not made:
                folder = next((self.root / 'exports' / 'export' / 'documents').iterdir()) / 'original'
                os.chmod(folder, 0o500)
                made.append(folder)
            return execute(sql, params, many, context)
        try:
            with exported_rows_fail("RAISE EXCEPTION 'synthetic: refused';"), connection.execute_wrapper(lock_a_folder):
                out, printed, errors, raised = self.export()
        finally:
            for folder in made:
                os.chmod(folder, 0o700)
        self.assertIsInstance(raised, CommandError)
        self.assertIn('could not be written (', str(raised))
        self.assertIn("its folder could not be removed: a complete or partial copy of the practice's data may remain",
                      str(raised))
        self.assertNotIn('nothing was kept', str(raised))
        self.assertTrue(out.exists())  # what the sentence says
        self.assertTrue(any(path.is_file() for path in out.rglob('*')))
        record_bundle.discard_export(out)  # the person's clean-up, once the folder can be emptied
        self.assertFalse(Event.objects.filter(stage=Event.EXPORTED).exists())

    def test_a_failed_export_that_cannot_be_removed_is_said_to_remain(self):
        # a failure inside export_practice (as tests.test_bundles fails it), while one of its folders cannot be emptied
        made = []

        def failing_trail(workspace):
            folder = next((self.root / 'exports' / 'export' / 'documents').iterdir()) / 'original'
            os.chmod(folder, 0o500)
            made.append(folder)
            raise RuntimeError('synthetic: the audit trail cannot be read')
        try:
            with mock.patch.object(record_bundle, '_audit_trail', side_effect=failing_trail):
                out, printed, errors, raised = self.export()
        finally:
            for folder in made:
                os.chmod(folder, 0o700)
        self.assertIsInstance(raised, CommandError)
        self.assertIn('The export failed (RuntimeError), and its folder could not be removed', str(raised))
        self.assertTrue(out.exists())
        record_bundle.discard_export(out)
        self.assertFalse(os.path.lexists(out))
        self.assertFalse(Event.objects.filter(stage=Event.EXPORTED).exists())


# --- D4: a stop signal at any line between the commit and the run's record ---------------------------------------------

SWEPT = (disposal.destroy, disposal._attempt, disposal._run, disposal._record, disposal._event_fields)


def line_of(function, text) -> int:
    """The line of ``function`` holding ``text`` (exactly one)."""
    lines, start = inspect.getsourcelines(function)
    found = [start + index for index, line in enumerate(lines) if text in line]
    assert len(found) == 1, (function.__name__, text, found)
    return found[0]


def loop_lines(function) -> set:
    """The lines of ``function`` holding a loop - here every one is a comprehension's, inlined in its frame (PEP 709).
    The sweep takes such a line at its first line event only: a line event a loop's backward jump causes is where
    CPython 3.12's line instrumentation raises an exception a trace hook throws at an offset the enclosing handlers do
    not cover, so a with block's __exit__ never runs - which a real signal at that jump does not do (it is handled at
    the jump, inside the handlers' range: measured on CPython 3.12.3, 30 real signals of 30 during such a loop ran the
    with block's __exit__)."""
    return {instruction.positions.lineno for instruction in dis.get_instructions(function)
            if instruction.opname == 'FOR_ITER'}  # a loop's head (a with or except block's cleanup jumps back too)


def traced(on_line):
    """A sys.settrace hook calling ``on_line(name, line, occurrence)`` for every line event of SWEPT's functions."""
    codes, seen = {function.__code__: function.__name__ for function in SWEPT}, {}

    def local(frame, event, arg):
        if event == 'line':
            key = (codes[frame.f_code], frame.f_lineno)
            seen[key] = seen.get(key, 0) + 1
            on_line(*key, seen[key])
        return local

    def tracer(frame, event, arg):
        return local if frame.f_code in codes else None
    return tracer


class StopSignalSweepTests(td.RepairCase, TestCase):
    """D4, dataloss-4: the lens's probe - a real SIGTERM through the command's own handler, sent with os.kill from a
    trace hook at a chosen line (nothing in studio.disposal patched) - at EVERY line event of destroy, _attempt, _run,
    _record and _event_fields between the destruction's commit and the run's final INSERT: each run ends recorded
    'failed' with its certificate printed (or, at the INSERT itself, with the certificate saying its event may not have
    been written), the 'committed' row standing either way. And at every line event of destroy before the commit: the
    transaction rolls back, nothing is destroyed or recorded, nothing is printed - an interrupt before the commit does
    what it did - the line event of the with block's exit included, where the interrupt comes before Django's __exit__
    ran (destroy's guard closes the block; DestroyBlockExitTests has the real-signal case).

    Round 2 (repair d2, disposal-0 to disposal-4) moved the line between the two: the block's last statement holds the
    stop signals (disposal.STOP_SIGNAL_HOLD), so from the with block's exit on the commit and the run's record go to
    their end. A signal that comes before the steps after the commit is recorded 'failed', named as the problem of the
    step it stopped ('files: Stopped'); one that comes after them changes nothing in the record - written as it stands,
    'completed' here - and the command says it held the signal; either way its certificate is printed, it names only
    rows that exist (never "may not have been written": the INSERT is not interrupted), and the command ends with 143."""

    def one_document(self, number):
        enc = f.encounter(self.ws, self.reviewer, title=f'ZZ-TITLE-MARKER sweep {number}')
        f.upload(enc, self.reviewer, data=f.PDF_BYTES + f' sweep {number}'.encode(), filename='zz-file-marker.pdf')
        plan = disposal.plan(disposal.document_scope(enc.pk), by='Synthetic Operator', reason='Synthetic: misfiled.')
        return enc, plan

    def run_plan(self, plan, tracer):
        out, err, code = io.StringIO(), io.StringIO(), None
        with td.installer_idle():
            sys.settrace(tracer)
            try:
                call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                             '--approved-by', 'Synthetic Approver', '--authorization-ref', td.AUTH, stdout=out, stderr=err)
            except SystemExit as exc:
                code = exc.code
            finally:
                sys.settrace(None)
        self.errors = err.getvalue()
        return code, out.getvalue()

    def points(self):
        """(before the commit, between the commit and the final INSERT): the line events of an uninterrupted run - the
        commit's side beginning just after the block's last statement, which holds the stop signals (round 2)."""
        events = []
        _, plan = self.one_document('recorded')
        code, printed = self.run_plan(plan, traced(lambda *event: events.append(event)))
        self.assertIsNone(code, printed)
        loops = {function.__name__: loop_lines(function) for function in SWEPT}
        events = [event for event in events if event[2] == 1 or event[1] not in loops[event[0]]]
        hold = events.index(('destroy', line_of(disposal.destroy, "marks['committing'] = STOP_SIGNAL_HOLD.hold()"), 1))
        insert = events.index(('_record', line_of(disposal._record, 'DisposalEvent.objects.create(**values)'), 1))
        return [event for event in events[:hold + 1] if event[0] == 'destroy'], events[hold + 1:insert + 1]

    def interrupted_at(self, point, number):
        enc, plan = self.one_document(number)
        fired = []

        def on_line(*event):
            if event == point and not fired:
                fired.append(event)
                os.kill(os.getpid(), signal.SIGTERM)  # the command's handler takes it here: held, or raised
        code, printed = self.run_plan(plan, traced(on_line))
        self.assertEqual(fired, [point])
        self.assertEqual(code, 128 + signal.SIGTERM)
        events = Event.objects.filter(encounter_ids__contains=[str(enc.pk)])
        return enc, events, printed

    def test_a_sigterm_at_any_line_between_the_commit_and_the_record_is_recorded(self):
        _, after = self.points()
        self.assertGreaterEqual(len(after), 10)
        steps = after.index(('destroy', line_of(disposal.destroy, '_after_commit(scope, outcome)'), 1))
        for number, point in enumerate(after):
            with self.subTest(point=point):
                enc, events, printed = self.interrupted_at(point, number)
                committed = events.get(stage=disposal.COMMITTED)  # the record that stands whatever follows
                self.assertIn(f'DisposalEvent {committed.pk} (committed)', printed)
                final = events.get(stage__in=(Event.COMPLETED, Event.FAILED))  # never "may not have been written"
                self.assertIn(f'Disposal {final.pk} ({final.stage})', printed)
                self.assertNotIn('NOT RECORDED', printed)
                if after.index(point) <= steps:  # before the steps after the commit: they stop, and say why
                    self.assertEqual(final.stage, Event.FAILED)
                    self.assertEqual(final.counts['problems'], ['files: Stopped'])
                else:  # after them: the record as it stands, and the signal held to the end
                    self.assertEqual(final.stage, Event.COMPLETED)
                    self.assertIn(dispose_cmd.HELD_TEXT, self.errors)
                self.assertNotIn('ZZ-TITLE-MARKER', printed)

    def test_a_sigterm_at_any_line_before_the_commit_destroys_and_records_nothing(self):
        before, _ = self.points()
        self.assertGreaterEqual(len(before), 10)
        for number, point in enumerate(before):
            with self.subTest(point=point):
                enc, events, printed = self.interrupted_at(point, f'before {number}')
                self.assertFalse(events.exclude(stage=Event.PLANNED).exists())
                self.assertIsNone(models.Encounter._base_manager.get(pk=enc.pk).destroyed_at)
                source = models.SourceFile.objects.get(encounter=enc)
                self.assertTrue(storage.stored_path(source.storage_name).exists())
                self.assertEqual(printed, '')

    def test_a_ctrl_c_right_after_the_final_insert_never_writes_it_twice(self):
        # the final INSERT runs, and the interrupt comes before create() returns: whether it was written is not known
        # to the run, which must not send it again (outcome.recording) - the certificate says it may not have been
        enc, plan = self.one_document('twice')
        inserts = []

        def interrupt_after_the_final_insert(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith('INSERT INTO "studio_disposalevent"'):
                inserts.append(sql)
                if len(inserts) == 2:  # the first is the 'committed' row, the second the run's final one
                    raise KeyboardInterrupt
            return result
        out = io.StringIO()
        with td.installer_idle(), connection.execute_wrapper(interrupt_after_the_final_insert):
            with self.assertRaises(KeyboardInterrupt):
                call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                             '--approved-by', 'Synthetic Approver', '--authorization-ref', td.AUTH, stdout=out)
        events = Event.objects.filter(encounter_ids__contains=[str(enc.pk)])
        self.assertEqual(len(inserts), 2)
        self.assertEqual(events.filter(stage__in=(Event.COMPLETED, Event.FAILED)).count(), 1)
        self.assertIn('NOT RECORDED (its DisposalEvent may not have been written', out.getvalue())


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class DestroyBlockExitTests(TransactionTestCase):
    """D4's class, the commit's own start: a real SIGTERM, through the command's handler, handled as destroy's atomic
    block's __exit__ is entered - before its first line, so before it began the commit (the trace hook sends it at that
    call: where CPython checks for a signal on entering a function). The block was left open: the 'committed' and
    'failed' rows were written into that open transaction, which the process's exit rolled back, and the certificate
    printed - "whether the rows were destroyed is not known" - named a DisposalEvent that never existed. Round 1 made
    destroy's guard close the block itself (rolled back, nothing destroyed). Round 2 (repair d2, disposal-2: one line
    later in __exit__ the same ghost came back) holds the stop signals from the block's last statement on: the commit
    goes to its end, and the run is recorded 'failed' - its steps after the commit stopped before the first one, so the
    document's file is left, named, for a new plan - with a certificate naming only rows that exist, nothing left open.
    In autocommit, as the command runs."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        override = override_settings(ORIGINALS_DIR=Path(folder.name) / 'originals')
        override.enable()
        self.addCleanup(override.disable)
        ws = f.workspace('Synthetic block-exit practice')
        member = f.member(ws)
        self.enc = f.encounter(ws, member, title='ZZ-TITLE-MARKER block exit')
        f.upload(self.enc, member, data=f.PDF_BYTES + b' block exit', filename='zz-file-marker.pdf')

    def test_a_sigterm_as_the_block_exit_is_entered_is_held_to_the_runs_record(self):
        plan = disposal.plan(disposal.document_scope(self.enc.pk), by='Synthetic Operator', reason='Synthetic.')
        name = models.SourceFile.objects.get(encounter=self.enc).storage_name
        exit_code, fired = transaction.Atomic.__exit__.__code__, []

        def at_the_exit(frame, event, arg):
            if (event == 'call' and frame.f_code is exit_code and not fired and frame.f_back is not None
                    and frame.f_back.f_code is disposal.destroy.__code__):
                fired.append(True)
                os.kill(os.getpid(), signal.SIGTERM)  # taken here, before __exit__'s first line: held
            return None
        out, code = io.StringIO(), None
        with td.installer_idle():
            sys.settrace(at_the_exit)
            try:
                call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                             '--approved-by', 'Synthetic Approver', '--authorization-ref', td.AUTH, stdout=out)
            except SystemExit as exc:
                code = exc.code
            finally:
                sys.settrace(None)
        self.assertEqual(fired, [True])
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertFalse(connection.in_atomic_block)  # no transaction left open for a record to vanish with
        self.assertEqual(connection.atomic_blocks, [])
        connection.close()  # what the process's exit does: what follows is what committed
        self.assertEqual(sorted(Event.objects.values_list('stage', flat=True)),
                         sorted([Event.PLANNED, disposal.COMMITTED, Event.FAILED]))
        committed, failed = Event.objects.get(stage=disposal.COMMITTED), Event.objects.get(stage=Event.FAILED)
        self.assertIsNotNone(models.Encounter._base_manager.get(pk=self.enc.pk).destroyed_at)
        self.assertEqual((failed.counts['problems'], failed.files['remaining_names']), (['files: Stopped'], [name]))
        self.assertTrue(storage.stored_path(name).exists())  # left for a new plan, and named
        for pk, stage in ((committed.pk, 'committed'), (failed.pk, 'failed')):
            self.assertIn(f'{pk} ({stage})', out.getvalue())
        self.assertNotIn('NOT RECORDED', out.getvalue())
