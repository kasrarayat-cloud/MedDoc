"""Offline controls for the locked pre-install backup and restore check, and the report the installer verifies.

The installed tool is never run: a fake runner writes what backup_restore.py writes (the run directory, its
summary and encrypted manifest; the restore directory and its verification record) and prints what it prints.
"""
from contextlib import contextmanager, redirect_stdout
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import install_rebuild_release as installer
from ops import legacy_model_activation as legacy
from ops import activation_exclusion
from ops import rebuild_release_backup as backup

BASE = '67acb2628b84c2be25f379a15168aa802350c060'
RUN = '20261031T200000Z-0a1b2c3d'
RESTORE = 'a1b2c3d4e5f60718'


def write_private(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


class FakeTool:
    """What ops/backup_restore.py writes and prints; failures are programmable per action."""

    def __init__(self):
        self.calls = []
        self.fail = set()
        self.retained = False
        self.leftover = False

    def summary(self, directory):
        return {'complete': True, 'run_id': RUN, 'database': 'quillmd_fresh', 'table_count': 48,
                'row_count': 232947, 'file_count': 1291, 'file_bytes': 51234567, 'source_commit': BASE,
                'encrypted': True, 'manifest_cipher_sha256': backup.sha(b'encrypted manifest')}

    def __call__(self, argv, **options):
        self.calls.append(argv)
        if argv[0] == 'docker':
            return subprocess.CompletedProcess(argv, 0, b'0123abcd\n' if self.leftover else b'', b'')
        action = argv[3]
        if action in self.fail:
            return subprocess.CompletedProcess(argv, 1, b'', b'Backup/restore refused or failed.\n')
        output = Path(argv[argv.index('--output') + 1])
        if action == 'backup':
            directory = output / RUN
            directory.mkdir(mode=0o700)
            write_private(directory / 'manifest.json.fernet', b'encrypted manifest')
            summary = self.summary(directory)
            write_private(directory / 'summary.json', json.dumps(summary, indent=2).encode() + b'\n')
            return subprocess.CompletedProcess(argv, 0, json.dumps({'backup_directory': str(directory),
                                                                    **summary}).encode(), b'')
        directory = output / ('restore-' + RESTORE)
        directory.mkdir(mode=0o700)
        result = {'run_id': RESTORE, 'container': 'quillmd-restore-' + RESTORE, 'complete': True,
                  'started_at_utc': '2026-10-31T20:30:00+00:00', 'provider_actions': 0, 'stage': 'complete',
                  'table_count': 48, 'row_count': 232947, 'file_count': 1291, 'all_table_hashes_match': True,
                  'all_file_hashes_match': True, 'decrypted_files_written': 0,
                  'restore_database_on_tmpfs_without_swap': True, 'invariants': {'users': 3},
                  'enabled_custom_triggers': 7, 'network': 'none', 'published_ports': 0, 'workers_started': 0,
                  'provider_credentials_copied': False, 'backup_run_id': RUN,
                  'finished_at_utc': '2026-10-31T20:31:00+00:00', 'container_retained': self.retained}
        write_private(directory / 'verification.json', json.dumps(result, indent=2).encode() + b'\n')
        return subprocess.CompletedProcess(argv, 0, json.dumps({'restore_directory': str(directory),
                                                                **result}).encode(), b'')


class BackupStepTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.addCleanup(self.temporary.cleanup)
        umask = os.umask(0o022)
        os.umask(umask)
        self.addCleanup(os.umask, umask)
        self.tool = FakeTool()
        self.locked = []

        @contextmanager
        def locks():
            self.locked.append('held')
            try:
                yield
            finally:
                self.locked.append('released')
        engine = SimpleNamespace(prior=SimpleNamespace(legacy=SimpleNamespace(operation_locks=locks)))
        self.installer = SimpleNamespace(load_engine=lambda: engine, LOCK_FILES=installer.LOCK_FILES,
                                         reason=installer.reason, write_result=installer.write_result)
        held = patch.object(backup, 'held_locks', return_value=[{'path': 'x', 'device_inode': '08:02:1'}])
        held.start()
        self.addCleanup(held.stop)

    def args(self, **changes):
        values = dict(output=self.root / 'attempt-01', report=self.root / 'report.json',
                      key_file=Path('/opt/meddoc-pro/rebuild/.runtime/backup-secrets/k.key'),
                      database_credentials=Path('/opt/meddoc-pro/rebuild/.runtime/db-role-secrets/r.json'))
        values.update(changes)
        return SimpleNamespace(**values)

    def execute(self, **changes):
        return backup.execute(self.args(**changes), self.installer, runner=self.tool)

    def test_the_summary_contract_is_the_scheduled_capture_s(self):
        from ops import scheduled_backup
        self.assertEqual(backup.SUMMARY_KEYS, scheduled_backup.SUMMARY_KEYS)
        self.assertEqual(backup.KEY, scheduled_backup.KEY)
        self.assertEqual(backup.ROLES, scheduled_backup.ROLES)

    def test_the_locks_are_the_engine_s_own(self):
        self.assertEqual(installer.LOCK_FILES[:4], ('legacy-model-activation.lock', *legacy.LOCKS))
        publication = Path(activation_exclusion.LOCK_PATH).relative_to(Path(activation_exclusion.RUNTIME))
        self.assertEqual(installer.LOCK_FILES[4], publication.as_posix())

    def test_commands_pass_credentials_by_path_and_write_no_bytecode(self):
        args = self.args()
        first, second = backup.commands(args.output, args.key_file, args.database_credentials, '/x/' + RUN)
        self.assertEqual(first, [str(backup.PYTHON), '-B', str(backup.TOOL), 'backup', '--source', str(backup.APP),
                                 '--output', str(args.output / 'backup'), '--key-file', str(args.key_file),
                                 '--database-credentials', str(args.database_credentials)])
        self.assertEqual(second[3:5], ['restore-check', '--backup'])
        self.assertNotIn('-I', first + second)
        self.assertEqual(backup.CHILD_ENV['PYTHONDONTWRITEBYTECODE'], '1')

    def test_a_complete_step_holds_the_locks_throughout_and_its_report_verifies(self):
        report = self.execute()
        self.assertTrue(report['complete'], report)
        self.assertEqual(self.locked, ['held', 'released'])
        self.assertEqual([call[3] if call[0] != 'docker' else 'docker' for call in self.tool.calls],
                         ['backup', 'restore-check', 'docker'])
        finished = dt.datetime.fromisoformat(report['finished_at'])
        facts = backup.verify_report(self.root / 'report.json', base=BASE, now=finished + dt.timedelta(minutes=5),
                                     max_age=dt.timedelta(hours=12))
        self.assertEqual((facts['run_id'], facts['restore_run_id'], facts['table_count']), (RUN, RESTORE, 48))
        self.assertEqual(facts['report_sha256'], backup.sha((self.root / 'report.json').read_bytes()))
        for kwargs in ({'base': '0' * 40, 'now': finished}, {'base': BASE, 'now': finished + dt.timedelta(hours=13)},
                       {'base': BASE, 'now': finished - dt.timedelta(minutes=1)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(backup.Refusal):
                backup.verify_report(self.root / 'report.json', max_age=dt.timedelta(hours=12), **kwargs)

    def test_the_report_is_refused_once_its_backup_is_no_longer_intact(self):
        self.execute()
        finished = dt.datetime.fromisoformat(json.loads((self.root / 'report.json').read_text())['finished_at'])
        run = self.root / 'attempt-01/backup' / RUN

        def verify():
            return backup.verify_report(self.root / 'report.json', base=BASE, now=finished,
                                        max_age=dt.timedelta(hours=12))
        verify()
        write_private(run / 'INCOMPLETE', b'killed\n')
        with self.assertRaises(backup.Refusal):
            verify()
        (run / 'INCOMPLETE').unlink()
        (run / 'manifest.json.fernet').chmod(0o644)
        with self.assertRaises(backup.Refusal):
            verify()
        (run / 'manifest.json.fernet').chmod(0o600)
        (self.root / 'report.json').chmod(0o640)
        with self.assertRaises(backup.Refusal):
            verify()

    def test_failures_leave_an_incomplete_report_and_stop_at_once(self):
        cases = [({'backup'}, False, False, 'backup_command_failed', 1),
                 ({'restore-check'}, False, False, 'restore_check_failed', 2),
                 (set(), True, False, 'restore_complete', 2),
                 (set(), False, True, 'drill_container_absent', 3)]
        for fail, retained, leftover, label, calls in cases:
            with self.subTest(label=label):
                self.tearDown_case()
                self.tool.fail, self.tool.retained, self.tool.leftover = fail, retained, leftover
                report = self.execute()
                self.assertFalse(report['complete'])
                self.assertEqual(report['failure'], label)
                self.assertEqual(len(self.tool.calls), calls)
                self.assertEqual(self.locked[-1], 'released')
                with self.assertRaises(backup.Refusal):
                    backup.verify_report(self.root / 'report.json', base=BASE, now=backup.now_utc(),
                                         max_age=dt.timedelta(hours=12))

    def tearDown_case(self):
        for path in sorted(self.root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            path.chmod(0o700) if path.is_dir() else None
            path.rmdir() if path.is_dir() else path.unlink()
        self.tool = FakeTool()
        self.locked = []

    def test_a_timed_out_child_is_a_failure_not_a_wait(self):
        def runner(argv, **options):
            raise subprocess.TimeoutExpired(argv, options['timeout'])
        report = backup.execute(self.args(), self.installer, runner=runner)
        self.assertEqual((report['complete'], report['failure'], report['backup']['timed_out']),
                         (False, 'backup_command_failed', True))

    def test_preflight_refuses_reused_or_public_paths_and_credentials_inside_the_output(self):
        fake = SimpleNamespace(reason=installer.reason, pinned_bytes=lambda: {}, locks_free=lambda: {},
                               outside_scheduled_windows=lambda moment: 'ok')
        rows = {row['check']: row['passed'] for row in backup.preflight(self.args(), fake)}
        self.assertTrue(all(rows.values()), rows)
        (self.root / 'attempt-01').mkdir(mode=0o700)
        public = self.root / 'public'
        public.mkdir()
        public.chmod(0o755)
        rows = {row['check']: row['passed'] for row in backup.preflight(
            self.args(report=public / 'report.json',
                      key_file=self.root / 'attempt-01/inside.key'), fake)}
        self.assertEqual((rows['new_private_output'], rows['new_private_report'], rows['credential_paths_only']),
                         (False, False, False))

    def test_the_command_without_execute_runs_only_the_preflight(self):
        fake = SimpleNamespace(reason=installer.reason, pinned_bytes=lambda: {}, locks_free=lambda: {},
                               outside_scheduled_windows=lambda moment: 'ok')
        argv = ['--output', str(self.root / 'attempt-01'), '--report', str(self.root / 'report.json')]
        with patch.object(backup, 'installer', return_value=fake), patch.object(backup, 'execute') as execute, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(backup.main(argv), 0)
        execute.assert_not_called()
        plan = json.loads(output.getvalue())
        self.assertFalse(plan['execute'])
        self.assertIn(str(backup.KEY), plan['backup_command'])


if __name__ == '__main__':
    unittest.main()
