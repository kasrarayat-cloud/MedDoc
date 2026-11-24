"""Release 1, D3: processing copies and old rows cleaned up (studio.storage, studio.intake, studio.maintenance and the
worker's tick in studio.jobs).

- A stored file never outlives a failed upload: a failed read-back check removes it (storage.store_original), and so does
  anything that raises after the file was stored - inside the upload's transaction, or as the deferred constraint's
  IntegrityError that surfaces when it commits (intake.create_encounter). Two posts of one upload racing leave exactly one
  file, also when the first of them fails after storing its own.
- The orphan sweep removes a file no row names once it is over an hour old, and keeps every named file - the original
  and the converted PDF a Word document's viewer shows - every young file, and anything it does not understand; a dry run
  removes nothing; its output is counts only.
- The daily maintenance reports its counts in one SecurityEvent, runs once a day and the check of stored files once a
  week, under an advisory lock one process holds; the worker runs it on its tick, and a failing tick never stops it.

Synthetic data only, on originals and temporary folders of the tests' own; nothing reaches the network."""
from __future__ import annotations

import io
import itertools
import os
import tempfile
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import DatabaseError, IntegrityError, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import intake, jobs, maintenance, models, rate, storage
from studio.fable import document as fable_document
from tests.support import coding as f

HOUR = 60 * 60
OLD = time.time() - 3 * HOUR  # a moment the sweep's hour has long passed


def age(path, seconds=None):
    """Make ``path`` look last changed ``seconds`` ago (default: three hours)."""
    moment = OLD if seconds is None else time.time() - seconds
    os.utime(path, (moment, moment))
    return path


def stored_files(root) -> list:
    """Every regular file under ``root`` (relative paths, sorted)."""
    return sorted(str(path.relative_to(root)) for path in Path(root).rglob('*') if path.is_file())


class OriginalsCase:
    """Mixin: an originals directory of the test class's own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._originals = tempfile.TemporaryDirectory()
        cls.root = Path(cls._originals.name)
        cls._override = override_settings(ORIGINALS_DIR=cls.root)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._originals.cleanup()
        super().tearDownClass()

    def tearDown(self):
        for path in sorted(self.root.rglob('*'), reverse=True):  # each test starts on an empty store
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink()
        super().tearDown()


# --- a failed store and a failed upload leave no file ------------------------------------------------------------------

class StoreCleanUpTests(OriginalsCase, TestCase):
    def test_a_read_back_that_does_not_match_removes_the_file(self):
        ws = f.workspace()
        with mock.patch.object(storage, '_read_back', return_value=b'%PDF-1.7 changed on the way to the disk'):
            with self.assertRaises(storage.OriginalCorrupted):
                storage.store_original(ws.pk, f.PDF_BYTES, 'synthetic.pdf')
        self.assertEqual(stored_files(self.root), [])

    def test_a_read_back_that_fails_removes_the_file(self):
        ws = f.workspace()
        with mock.patch.object(storage, '_read_back', side_effect=OSError('synthetic read failure')):
            with self.assertRaises(OSError):
                storage.store_original(ws.pk, f.PDF_BYTES, 'synthetic.pdf')
        self.assertEqual(stored_files(self.root), [])

    def test_a_good_store_keeps_its_one_file(self):
        ws = f.workspace()
        name, digest, size = storage.store_original(ws.pk, f.PDF_BYTES, 'synthetic.pdf')
        self.assertEqual(stored_files(self.root), [name])
        self.assertEqual(storage.file_digest(storage.stored_path(name)), (size, digest))


class UploadCleanUpTests(OriginalsCase, TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.membership = models.Membership.objects.get(user=self.user)

    def upload(self, **kwargs):
        return intake.create_encounter(membership=self.membership, user=self.user, title='Synthetic upload',
                                       data=f.PDF_BYTES, filename='synthetic-upload.pdf', **kwargs)

    def test_a_failure_after_the_file_was_stored_leaves_none(self):
        failures = {
            'the original row': mock.patch.object(models.SourceFile.objects, 'create',
                                                  side_effect=DatabaseError('synthetic insert failure')),
            'the first round': mock.patch.object(jobs, 'start_round', side_effect=RuntimeError('synthetic')),
            'the audit row': mock.patch.object(intake.audit, 'record', side_effect=RuntimeError('synthetic')),
        }
        for label, patch in failures.items():
            with self.subTest(failure=label), patch:
                with self.assertRaises((DatabaseError, RuntimeError)):
                    self.upload()
                self.assertEqual(stored_files(self.root), [])
                self.assertFalse(models.Encounter.objects.exists())

    def test_an_upload_that_succeeds_keeps_its_file(self):
        encounter = self.upload()
        self.assertEqual(stored_files(self.root), [encounter.files.get().storage_name])


def _dangling_row_after(real):
    """jobs.start_round as intake calls it, then one AuditEvent naming a practice that does not exist: the deferred
    foreign key refuses it only when the upload's transaction commits, so the IntegrityError surfaces outside the
    transaction's block, after the file was stored."""
    def start_round(*args, **kwargs):
        round_ = real(*args, **kwargs)
        models.AuditEvent.objects.create(workspace_id=uuid.uuid4(), actor_kind='system', event='synthetic.dangling')
        return round_
    return start_round


class UploadCommitTests(OriginalsCase, TransactionTestCase):
    """Real commits: the deferred constraints are checked as the upload's transaction commits, and two threads race."""

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.membership = models.Membership.objects.get(user=self.user)

    def upload(self, **kwargs):
        return intake.create_encounter(membership=self.membership, user=self.user, title='Synthetic upload',
                                       data=f.PDF_BYTES, filename='synthetic-upload.pdf', **kwargs)

    def test_an_integrity_error_at_commit_leaves_no_file(self):
        with mock.patch.object(jobs, 'start_round', side_effect=_dangling_row_after(jobs.start_round)):
            with self.assertRaises(IntegrityError):
                self.upload()
        self.assertEqual(stored_files(self.root), [])
        self.assertFalse(models.Encounter.objects.exists())

    def race(self, *, first_fails):
        """Two threads post one upload attempt (one client key) at the same moment; with ``first_fails``, the first of
        them to store its file fails right after it (its original's row cannot be written). Each thread's result."""
        key, barrier, lock = uuid.uuid4(), threading.Barrier(2), threading.Lock()
        results, created = [], {'calls': 0}
        real_create, real_row = intake._create, models.SourceFile.objects.create

        def synced(*args):
            barrier.wait(timeout=20)  # both are past every check before either inserts
            return real_create(*args)

        def row(**kwargs):
            with lock:
                created['calls'] += 1
                first = created['calls'] == 1
            if first and first_fails:
                raise DatabaseError('synthetic: the first upload fails after storing its file')
            return real_row(**kwargs)

        def post():
            try:
                results.append(('made', self.upload(client_key=key).pk))
            except intake.DuplicateUpload as exc:
                results.append(('duplicate', exc.encounter.pk))
            except DatabaseError as exc:
                results.append(('failed', str(exc)))
            finally:
                connection.close()
        with mock.patch.object(intake, '_create', side_effect=synced), \
                mock.patch.object(models.SourceFile.objects, 'create', side_effect=row):
            threads = [threading.Thread(target=post) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
        return sorted(results)

    def test_two_posts_of_one_upload_racing_leave_exactly_one_file(self):
        results = self.race(first_fails=False)
        encounter = models.Encounter.objects.get()
        self.assertEqual(results, [('duplicate', encounter.pk), ('made', encounter.pk)])
        self.assertEqual(stored_files(self.root), [encounter.files.get().storage_name])

    def test_when_the_first_of_two_racing_posts_fails_after_storing_its_file_one_file_is_left(self):
        results = self.race(first_fails=True)
        encounter = models.Encounter.objects.get()
        self.assertEqual([kind for kind, _ in results], ['failed', 'made'])
        self.assertEqual(results[1], ('made', encounter.pk))
        self.assertEqual(stored_files(self.root), [encounter.files.get().storage_name])


# --- the orphan sweep ---------------------------------------------------------------------------------------------------

class SweepTests(OriginalsCase, TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        encounter = f.encounter(self.ws, self.user)
        revision = f.upload(encounter, self.user)
        self.original = revision.source_file.storage_name
        converted, digest, _ = storage.store_original(self.ws.pk, b'%PDF-1.7 synthetic conversion %%EOF', 'converted.pdf')
        models.CodingRound.objects.create(encounter=encounter, revision=revision, number=1, trigger='upload',
                                          context={}, view_pdf_storage_name=converted, view_pdf_sha256=digest)
        self.converted = converted
        self.orphan, _, _ = storage.store_original(self.ws.pk, b'%PDF-1.7 an upload that failed %%EOF', 'orphan.pdf')
        self.young, _, _ = storage.store_original(self.ws.pk, b'%PDF-1.7 an upload in progress %%EOF', 'young.pdf')
        for name in (self.original, self.converted, self.orphan):
            age(storage.stored_path(name))  # three hours old: only the young file is younger than the sweep's hour
        folder = storage.workspace_folder(self.ws.pk)
        (folder / 'not-a-file').mkdir()
        (self.root / 'stray-at-the-root.txt').write_text('synthetic')
        (self.root / 'not-a-practice').mkdir()
        age(self.root / 'stray-at-the-root.txt')

    def test_a_dry_run_counts_and_removes_nothing(self):
        before = stored_files(self.root)
        counts = maintenance.sweep_orphan_files()
        self.assertEqual(counts, {'folders': 1, 'files': 4, 'named': 2, 'orphans': 1, 'young': 1, 'deleted': 0,
                                  'unexpected': 3, 'failed': 0})
        self.assertEqual(stored_files(self.root), before)

    def test_the_sweep_removes_an_old_orphan_and_keeps_named_young_and_unexpected_entries(self):
        counts = maintenance.sweep_orphan_files(delete=True)
        self.assertEqual((counts['orphans'], counts['deleted'], counts['named'], counts['young']), (1, 1, 2, 1))
        left = stored_files(self.root)
        self.assertNotIn(self.orphan, left)
        for kept in (self.original, self.converted, self.young, 'stray-at-the-root.txt'):
            with self.subTest(kept=kept):
                self.assertIn(kept, left)  # a converted PDF is a named file: never an orphan
        self.assertTrue((storage.workspace_folder(self.ws.pk) / 'not-a-file').is_dir())
        self.assertTrue((self.root / 'not-a-practice').is_dir())

    def test_the_command_prints_counts_only_and_a_deleting_run_is_recorded(self):
        dry = io.StringIO()
        call_command('sweep_orphan_files', stdout=dry)
        self.assertIn('dry run, nothing removed', dry.getvalue())
        self.assertFalse(models.SecurityEvent.objects.filter(event=maintenance.SWEPT_EVENT).exists())
        out = io.StringIO()
        call_command('sweep_orphan_files', '--delete', stdout=out)
        for text in (dry.getvalue(), out.getvalue()):
            for name in (self.original, self.converted, self.orphan, self.young):
                self.assertNotIn(name.split('/')[1], text)  # never a file's name
        event = models.SecurityEvent.objects.get(event=maintenance.SWEPT_EVENT)
        self.assertEqual((event.data['deleted'], event.data['orphans'], event.data['named']), (1, 1, 2))
        self.assertNotIn(self.orphan, stored_files(self.root))


class WorkFolderTests(TestCase):
    def test_stale_conversion_folders_go_and_young_ones_and_links_stay(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            old = root / f'{fable_document.WORK_PREFIX}old'
            young = root / f'{fable_document.WORK_PREFIX}young'
            other = root / 'someone-elses-folder'
            for folder in (old, young, other):
                folder.mkdir()
                (folder / 'part').write_text('synthetic')
            target = root / 'target'
            target.mkdir()
            (target / 'part').write_text('synthetic')
            link = root / f'{fable_document.WORK_PREFIX}link'
            link.symlink_to(target, target_is_directory=True)
            for path in (old, other, target):
                age(path)
            self.assertEqual(jobs.remove_stale_work_dirs(older_than=HOUR, root=root), 1)
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             sorted([young.name, other.name, target.name, link.name]))
            self.assertTrue((target / 'part').exists())  # a link is never followed
            self.assertEqual(jobs.remove_stale_work_dirs(root=root), 1)  # the worker's start: every one
            self.assertFalse(young.exists())
            self.assertTrue(other.exists() and link.is_symlink())


# --- the daily maintenance ----------------------------------------------------------------------------------------------

class DailyTests(OriginalsCase, TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ws = f.workspace()
        self.owner = f.user('owner-a')
        models.Membership.objects.create(user=self.owner, workspace=self.ws, role=models.Membership.OWNER)

    def attempt(self, username, days_ago):
        row = models.LoginAttempt.objects.create(username=username, client='192.0.2.10', succeeded=False)
        models.LoginAttempt.objects.filter(pk=row.pk).update(created_at=self.now - timedelta(days=days_ago))
        return row.pk

    def seed(self, scratch):
        Session.objects.create(session_key='lane4expired' + 'x' * 20, session_data='', expire_date=self.now - timedelta(days=1))
        Session.objects.create(session_key='lane4live' + 'y' * 23, session_data='', expire_date=self.now + timedelta(days=1))
        key = str(uuid.uuid4())
        for start in (self.now - timedelta(days=2), self.now - timedelta(minutes=5)):
            models.RateWindow.objects.create(scope='bundle.member', key=key, window_start=start, count=3, last_at=start)
        ids = {'unknown_old': [self.attempt('someone@example.invalid', 35), self.attempt('someone@example.invalid', 40)],
               'known_old': self.attempt('OWNER-A', 35),  # the account's own name, typed in capitals: kept
               'unknown_recent': self.attempt('a-typo-from-yesterday', 1),
               'hashed_old': self.attempt(maintenance.hashed_signin_name('already-hashed'), 50),
               'ancient': self.attempt('owner-a', 7 * 366)}
        orphan, _, _ = storage.store_original(self.ws.pk, b'%PDF-1.7 a failed upload %%EOF', 'orphan.pdf')
        age(storage.stored_path(orphan))
        stale = Path(scratch) / f'{fable_document.WORK_PREFIX}stale'
        stale.mkdir()
        age(stale)
        return ids, orphan, stale

    def test_the_daily_maintenance_reports_its_counts(self):
        with tempfile.TemporaryDirectory() as scratch, mock.patch('tempfile.gettempdir', return_value=scratch):
            ids, orphan, stale = self.seed(scratch)
            counts = maintenance.run_daily(self.now)
            self.assertFalse(stale.exists())
        expected = {'sessions_cleared': 1, 'rate_windows_pruned': 1, 'signin_names_hashed': 2, 'work_dirs_removed': 1,
                    'login_attempts_pruned': 1, 'sweep_orphans': 1, 'sweep_deleted': 1, 'sweep_named': 0,
                    'sweep_young': 0, 'sweep_failed': 0}
        event = models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT)
        for name, value in expected.items():
            with self.subTest(count=name):
                self.assertEqual(event.data[name], value)
                self.assertEqual(counts[name], value)
        self.assertEqual(event.data['failed'], [])
        self.assertEqual(list(Session.objects.values_list('session_key', flat=True)), ['lane4live' + 'y' * 23])
        self.assertEqual(models.RateWindow.objects.count(), 1)
        names = dict(models.LoginAttempt.objects.values_list('pk', 'username'))
        for pk in ids['unknown_old']:
            self.assertEqual(names[pk], maintenance.hashed_signin_name('someone@example.invalid'))
        self.assertEqual(names[ids['known_old']], 'OWNER-A')
        self.assertEqual(names[ids['unknown_recent']], 'a-typo-from-yesterday')
        self.assertEqual(names[ids['hashed_old']], maintenance.hashed_signin_name('already-hashed'))
        self.assertNotIn(ids['ancient'], names)  # past the retention (D25: six years)
        self.assertNotIn(orphan, stored_files(self.root))

    def test_a_failing_step_is_named_and_the_others_still_run(self):
        with tempfile.TemporaryDirectory() as scratch, mock.patch('tempfile.gettempdir', return_value=scratch), \
                mock.patch.object(maintenance, 'prune_rate_windows', side_effect=DatabaseError('synthetic')):
            self.seed(scratch)
            maintenance.run_daily(self.now)
        event = models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT)
        self.assertEqual(event.data['failed'], ['rate_windows_pruned'])
        self.assertNotIn('rate_windows_pruned', event.data)
        self.assertEqual((event.data['signin_names_hashed'], event.data['sweep_deleted']), (2, 1))

    def test_a_hashed_name_is_the_throttle_key_of_the_name_and_holds_no_text(self):
        hashed = maintenance.hashed_signin_name('Someone@Example.invalid')
        self.assertEqual(hashed, 'hash:' + rate.key_hash('signin-user:someone@example.invalid'))
        self.assertNotIn('someone', hashed.lower())
        self.assertLessEqual(len(hashed), models.LoginAttempt._meta.get_field('username').max_length)
        self.assertRaises(ValidationError, models.User(username=hashed).full_clean, exclude=['password'])


class DueTests(OriginalsCase, TestCase):
    def test_the_maintenance_runs_once_a_day_and_the_check_once_a_week(self):
        now = timezone.now()
        with tempfile.TemporaryDirectory() as scratch, mock.patch('tempfile.gettempdir', return_value=scratch):
            first = maintenance.run_due(now)
            self.assertTrue(first['locked'] and first['daily'] is not None and first['verified'] is not None)
            self.assertEqual(maintenance.run_due(now + timedelta(hours=1)),
                             {'daily': None, 'verified': None, 'locked': False})  # nothing due: no lock taken
            next_day = maintenance.run_due(now + timedelta(hours=25))
            self.assertTrue(next_day['daily'] is not None and next_day['verified'] is None)
            next_week = maintenance.run_due(now + timedelta(days=8))
            self.assertTrue(next_week['daily'] is not None and next_week['verified'] is not None)
        self.assertEqual(models.SecurityEvent.objects.filter(event=maintenance.DAILY_EVENT).count(), 3)
        self.assertEqual(models.SecurityEvent.objects.filter(event=maintenance.VERIFIED_EVENT).count(), 2)

    def test_a_process_that_cannot_take_the_lock_runs_nothing(self):
        default = connections['default']
        holder = type(default)(dict(default.settings_dict), alias='lane4-lock-holder')
        try:
            with holder.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(%s)', [maintenance.LOCK_KEY])
            self.assertEqual(maintenance.run_due(), {'daily': None, 'verified': None, 'locked': False})
            self.assertFalse(models.SecurityEvent.objects.filter(event__startswith='maintenance.').exists())
        finally:
            holder.close()
        with tempfile.TemporaryDirectory() as scratch, mock.patch('tempfile.gettempdir', return_value=scratch):
            self.assertTrue(maintenance.run_due()['locked'])  # released with its session: the next tick runs it

    def test_the_hourly_part_of_a_tick_runs_once_an_hour(self):
        state, clock = {}, iter([0, 0, 30, 3700, 3700])
        with mock.patch.object(jobs, 'remove_stale_work_dirs', return_value=0) as removed, \
                mock.patch.object(maintenance, 'run_due', return_value={}):
            for _ in range(3):
                maintenance.tick(state, clock=lambda: next(clock))
        self.assertEqual(removed.call_count, 2)
        removed.assert_called_with(older_than=maintenance.STALE_WORK_DIR_SECONDS)


# --- the weekly check of stored files ------------------------------------------------------------------------------------

class VerifyTests(OriginalsCase, TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.files = []
        for index in range(3):
            encounter = f.encounter(self.ws, self.user, title=f'Synthetic {index}')
            self.files.append(f.upload(encounter, self.user, data=f.PDF_BYTES + bytes([index])).source_file)

    def test_clean_files_pass_and_the_command_succeeds(self):
        out = io.StringIO()
        call_command('verify_originals', '--all', stdout=out)
        self.assertIn('checked 3, ok 3, mismatch 0, missing 0, unreadable 0', out.getvalue())
        event = models.SecurityEvent.objects.get(event=maintenance.VERIFIED_EVENT)
        self.assertEqual(event.data, {'checked': 3, 'ok': 3, 'mismatch': 0, 'missing': 0, 'unreadable': 0})

    def test_a_changed_or_missing_file_writes_a_security_event_with_ids_only(self):
        changed, missing, fine = self.files
        storage.stored_path(changed.storage_name).write_bytes(b'%PDF-1.7 not what was uploaded %%EOF')
        storage.stored_path(missing.storage_name).unlink()
        with self.assertRaises(CommandError):
            call_command('verify_originals', '--all', stdout=io.StringIO())
        events = {event.data['problem']: event for event in
                  models.SecurityEvent.objects.filter(event=maintenance.MISMATCH_EVENT)}
        self.assertEqual(set(events), {'mismatch', 'missing'})
        for problem, row in (('mismatch', changed), ('missing', missing)):
            event = events[problem]
            self.assertEqual(event.data, {'problem': problem, 'kind': 'original', 'encounter': str(row.encounter_id),
                                          'record': str(row.pk)})
            self.assertEqual(event.workspace_id, self.ws.pk)
        summary = models.SecurityEvent.objects.get(event=maintenance.VERIFIED_EVENT)
        self.assertEqual(summary.data, {'checked': 3, 'ok': 1, 'mismatch': 1, 'missing': 1, 'unreadable': 0})
        self.assertNotIn(fine.storage_name, str(list(models.SecurityEvent.objects.values_list('data', flat=True))))


# --- the worker's tick ------------------------------------------------------------------------------------------------------

class WorkerTickTests(TransactionTestCase):
    def run_worker(self, tick):
        calls = []
        clock = itertools.count(0, 100).__next__  # every reading of the clock is 100 s after the last

        def recorded(state, *, clock):
            calls.append(dict(state))
            return tick(state, len(calls))
        deadline = time.monotonic() + 30

        def should_stop():
            return len(calls) >= 2 or time.monotonic() > deadline
        # the worker's start removes every conversion folder of the system's temporary folder, which a full suite's
        # modules share while they run side by side: patched out here (WorkFolderTests proves the clean-up itself)
        with mock.patch.object(maintenance, 'tick', side_effect=recorded), \
                mock.patch.object(jobs, 'remove_stale_work_dirs', return_value=0):
            jobs.work(should_stop, poll_seconds=0.05, threads=1, clock=clock)
        return calls

    def test_the_worker_runs_the_maintenance_on_its_tick_and_keeps_its_state(self):
        def tick(state, number):
            state['ticks'] = number
        calls = self.run_worker(tick)
        self.assertEqual(calls[:2], [{}, {'ticks': 1}])

    def test_a_failing_maintenance_tick_never_stops_the_worker(self):
        def tick(state, number):
            if number == 1:
                raise DatabaseError('synthetic: the maintenance failed')
        with self.assertLogs('studio.jobs', level='ERROR') as logs:
            calls = self.run_worker(tick)
        self.assertEqual(len(calls), 2)  # the next tick ran
        self.assertTrue(any('the maintenance tick failed' in line for line in logs.output))
