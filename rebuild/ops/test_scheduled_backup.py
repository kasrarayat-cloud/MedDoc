from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
try:
    from . import scheduled_backup as s
except ImportError:
    import scheduled_backup as s


class ScheduledBackupTests(unittest.TestCase):
    """Isolated files and child fixtures; no provider, live DB, systemd or remote upload."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.monitor = self.root / 'monitor'
        self.destination = self.root / 'backups'
        self.monitor.mkdir(mode=0o700)
        self.destination.mkdir(mode=0o700)
        self.key = self.root / 'key'
        self.roles = self.root / 'roles'
        s.backup.write_private(self.key, Fernet.generate_key())
        s.backup.write_private(self.roles, b'{"synthetic":"not real credentials"}')
        for name, value in [('RUNTIME', self.root), ('MONITOR', self.monitor),
                            ('DESTINATION', self.destination), ('KEY', self.key), ('ROLES', self.roles)]:
            patcher = patch.object(s, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        free = patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * 1024**3))
        free.start()
        self.addCleanup(free.stop)
        self.run_id = '20260920T040000Z-aabbccdd'

    def child_success(self):
        folder = self.destination / self.run_id
        folder.mkdir(mode=0o700)
        cipher = Fernet(self.key.read_bytes()).encrypt(b'{"synthetic":"fixture only"}')
        self.summary = {'complete': True, 'run_id': self.run_id, 'database': 'quillmd_fresh',
                        'table_count': 35, 'row_count': 10, 'file_count': 1, 'file_bytes': 42,
                        'source_commit': 'a' * 40, 'encrypted': True,
                        'manifest_cipher_sha256': s.backup.digest(cipher)}
        s.backup.write_private(folder / 'summary.json', json.dumps(self.summary).encode())
        s.backup.write_private(folder / 'manifest.json.fernet', cipher)
        return SimpleNamespace(returncode=0, stdout=json.dumps(dict(self.summary, backup_directory=str(folder))).encode(),
                               stderr=b'synthetic ignored error-channel canary')

    def test_success_one_child_no_secrets_no_retention_or_remote_commands(self):
        child = self.child_success()
        with patch.object(s.subprocess, 'run', return_value=child) as runner:
            record, code = s.run_capture()
        self.assertEqual(code, 0)
        runner.assert_called_once()
        argv = runner.call_args.args[0]
        self.assertEqual(argv[2], 'backup')
        self.assertEqual(runner.call_args.kwargs['timeout'], s.TIMEOUT_SECONDS)
        self.assertEqual(set(runner.call_args.kwargs['env']), {'PATH', 'PYTHONDONTWRITEBYTECODE'})
        self.assertNotIn(self.key.read_text(), repr(runner.call_args))
        self.assertEqual(record['summary'], self.summary)
        self.assertFalse(record['offsite_verified'])
        self.assertFalse(record['restore_performed'])
        self.assertTrue(s.status()['healthy'])
        self.assertTrue((self.destination / self.run_id).exists())
        self.assertEqual(len(list(self.monitor.glob('20*.json'))), 1)
        for path in self.monitor.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_failure_preserves_last_success_and_never_emits_stderr(self):
        with patch.object(s.subprocess, 'run', return_value=self.child_success()):
            first, _ = s.run_capture()
        failure = SimpleNamespace(returncode=9, stdout=b'secret-like-provider-key', stderr=b'private clinical row')
        with patch.object(s.subprocess, 'run', return_value=failure):
            record, code = s.run_capture()
        self.assertEqual(code, 1)
        self.assertEqual(record['last_success_run_id'], first['last_success_run_id'])
        self.assertEqual(record['error'], 'backup_command_failed')
        self.assertFalse(s.status()['healthy'])
        self.assertEqual(len(list(self.monitor.glob('20*.json'))), 2)
        output = ''.join(p.read_text() for p in self.monitor.glob('*.json'))
        self.assertNotIn('secret-like', output)
        self.assertNotIn('clinical row', output)

    def test_timeout_retains_failure_and_does_not_retry(self):
        with patch.object(s.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['fixture'], 540,
                          output=b'secret-like-fixture', stderr=b'clinical-fixture')) as runner:
            record, code = s.run_capture()
        runner.assert_called_once()
        self.assertEqual((code, record['error']), (1, 'backup_timeout'))
        self.assertNotIn('secret-like', json.dumps(record))
        self.assertFalse(s.status()['healthy'])

    def test_low_disk_does_not_start_capture_or_delete_old_backup(self):
        old = self.destination / 'existing-preserved'; old.mkdir()
        with patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)), \
                patch.object(s.subprocess, 'run') as runner:
            record, code = s.run_capture()
        runner.assert_not_called()
        self.assertEqual((code, record['error']), (1, 'insufficient_free_space'))
        self.assertTrue(old.exists())

    def test_duplicate_capture_leaves_active_status_unchanged(self):
        s.atomic_status(self.monitor / 'latest.json', {'outcome': 'running', 'format': 1})
        original = (self.monitor / 'latest.json').read_bytes()
        lock = os.open(self.monitor / 'capture.lock', os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, lock)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(s.subprocess, 'run') as runner:
            record, code = s.run_capture()
        runner.assert_not_called()
        self.assertEqual((code, record['outcome']), (0, 'skipped'))
        self.assertEqual((self.monitor / 'latest.json').read_bytes(), original)

    def test_invalid_key_permissions_refuse_before_child(self):
        self.key.chmod(0o644)
        with patch.object(s.subprocess, 'run') as runner:
            record, code = s.run_capture()
        runner.assert_not_called()
        self.assertEqual((code, record['error']), (1, 'validation_or_capture_failed'))

    def test_invalid_lock_cannot_hide_failed_attempt_behind_previous_success(self):
        with patch.object(s.subprocess, 'run', return_value=self.child_success()):
            self.assertEqual(s.run_capture()[1], 0)
        original = (self.monitor / 'latest.json').read_bytes()
        lock = self.monitor / 'capture.lock'
        lock.chmod(0o644)
        with patch.object(s.subprocess, 'run') as runner:
            record, code = s.run_capture()
        runner.assert_not_called()
        self.assertEqual((code, record['outcome']), (1, 'failed'))
        self.assertEqual((self.monitor / 'latest.json').read_bytes(), original)
        self.assertEqual(len(list(self.monitor.glob('20*.json'))), 2)
        self.assertFalse(s.status()['healthy'])
        lock.chmod(0o600)
        # Correcting permissions alone must not manufacture a successful backup.
        self.assertFalse(s.status()['healthy'])
        self.assertEqual(s.status()['latest_outcome'], 'failed')
        with patch.object(s.subprocess, 'run', return_value=SimpleNamespace(returncode=0,
                  stdout=json.dumps(dict(self.summary, backup_directory=str(self.destination / self.run_id))).encode())):
            self.assertEqual(s.run_capture()[1], 0)
        self.assertTrue(s.status()['healthy'])

    def test_unopenable_lock_retains_failure_without_modifying_target(self):
        with patch.object(s.subprocess, 'run', return_value=self.child_success()):
            self.assertEqual(s.run_capture()[1], 0)
        lock = self.monitor / 'capture.lock'; lock.unlink()
        target = self.root / 'preserved-target'; target.write_text('untouched')
        lock.symlink_to(target)
        with patch.object(s.subprocess, 'run') as runner:
            record, code = s.run_capture()
        runner.assert_not_called()
        self.assertEqual((code, record['outcome']), (1, 'failed'))
        self.assertEqual(len(list(self.monitor.glob('20*.json'))), 2)
        self.assertEqual(target.read_text(), 'untouched')
        self.assertFalse(s.status()['healthy'])
        lock.unlink(); lock.touch(mode=0o600)
        self.assertFalse(s.status()['healthy'])

    def test_latest_symlink_refused_without_touching_target(self):
        target = self.root / 'untouched'; target.write_text('preserve')
        (self.monitor / 'latest.json').symlink_to(target)
        with patch.object(s.subprocess, 'run') as runner, self.assertRaises(RuntimeError):
            s.run_capture()
        runner.assert_not_called()
        self.assertEqual(target.read_text(), 'preserve')
        self.assertFalse(s.status()['healthy'])

    def test_child_success_needs_matching_real_encrypted_manifest(self):
        child = self.child_success()
        (self.destination / self.run_id / 'manifest.json.fernet').write_bytes(b'tampered')
        with patch.object(s.subprocess, 'run', return_value=child):
            record, code = s.run_capture()
        self.assertEqual((code, record['error']), (1, 'validation_or_capture_failed'))

    def test_stale_future_running_and_untrusted_status_are_unhealthy(self):
        current = datetime.now(timezone.utc)
        for timestamp, outcome in [(current - timedelta(hours=31), 'complete'),
                                   (current + timedelta(minutes=1), 'complete'), (current, 'running')]:
            s.atomic_status(self.monitor / 'latest.json', {'outcome': outcome,
                            'last_success_at': timestamp.isoformat(), 'last_success_run_id': self.run_id})
            self.assertFalse(s.status(current)['healthy'])
        s.atomic_status(self.monitor / 'latest.json', {'outcome': 'secret-like', 'error': 'private-value'})
        self.assertNotIn('secret-like', json.dumps(s.status()))
        self.assertNotIn('private-value', json.dumps(s.status()))

    def test_unit_has_no_swap_bounded_runtime_and_local_only_daily_timer(self):
        deploy = Path(__file__).resolve().parents[1] / 'deploy'
        unit = (deploy / 'quillmd-fresh-backup.service').read_text()
        timer = (deploy / 'quillmd-fresh-backup.timer').read_text()
        for line in ('User=claude', 'MemorySwapMax=0', 'MemoryMax=2G', 'TimeoutStartSec=600',
                     'NoNewPrivileges=true', 'ProtectSystem=strict', 'KillMode=control-group'):
            self.assertIn(line, unit)
        self.assertNotIn('EnvironmentFile', unit)
        self.assertIn('OnCalendar=*-*-* 04:30:00 UTC', timer)
        self.assertIn('Persistent=true', timer)
