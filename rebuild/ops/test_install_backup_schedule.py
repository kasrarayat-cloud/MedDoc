"""Pure installer checks: temporary files, fake systemd; no host mutation or database."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import install_backup_schedule as s
except ImportError:
    import install_backup_schedule as s


class BackupInstallerTests(unittest.TestCase):
    def setUp(self):
        initial_umask = os.umask(0o077)
        os.umask(initial_umask)
        self.addCleanup(os.umask, initial_umask)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # CI has no VPS service account. Model its identity using the owner of
        # these isolated fixtures; root_action separately models the root helper.
        actor = self.root.stat()
        fixture_actor = SimpleNamespace(pw_uid=actor.st_uid, pw_gid=actor.st_gid)
        def fixture_account(name):
            self.assertEqual(name, 'claude')
            return fixture_actor
        account = patch.object(s.pwd, 'getpwnam', side_effect=fixture_account)
        account.start()
        self.addCleanup(account.stop)
        self.app = self.root / 'rebuild'
        self.systemd = self.root / 'systemd'
        self.monitor = self.app / '.runtime/backup-monitor'
        self.evidence = self.app / '.runtime/evidence'
        for directory in (self.systemd, self.monitor, self.evidence):
            directory.mkdir(parents=True, mode=0o700)
        (self.app / '.runtime').chmod(0o700)
        self.hashes = {}
        for relative in s.SOURCES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(('SYNTHETIC REVIEWED ' + relative).encode())
            self.hashes[relative] = s.digest(target)
        (self.systemd / 'unrelated.service').write_text('PRESERVE ME')
        for name, value in [('ROOT', self.root), ('APP', self.app), ('SYSTEMD', self.systemd),
                            ('MONITOR', self.monitor), ('EVIDENCE', self.evidence)]:
            item = patch.object(s, name, value)
            item.start()
            self.addCleanup(item.stop)
        self.real_metadata = s.metadata
        def fixture_metadata(path):
            value = self.real_metadata(path)
            # Test process has no root rights. Model only systemd-owned fixture files.
            if path.is_relative_to(self.systemd):
                value.update(uid=0, gid=0)
            return value
        item = patch.object(s, 'metadata', side_effect=fixture_metadata)
        item.start()
        self.addCleanup(item.stop)
        self.calls = []
        self.capture_mode = 'success'
        self.main_status = '0'
        self.commit = 'a' * 40
        self.timer_active = False
        self.extra_delta = False

    def inventory(self):
        return {'units': {str(path.relative_to(self.systemd)): s.metadata(path)
                          for path in self.systemd.rglob('*')},
                'configuration': {'synthetic-protected-config': 'unchanged'},
                'processes': {'unrelated-running-service': 'unchanged'}}

    def payload(self, action):
        return {'action': action, 'hashes': self.hashes, 'commit': self.commit, 'baseline': self.inventory()}

    def install_fixtures(self):
        for name in s.UNITS:
            target = self.systemd / name
            target.write_bytes((self.app / 'deploy' / name).read_bytes())
            target.chmod(0o644)

    def fake_command(self, argv, timeout=40):
        self.calls.append(argv)
        if argv[:2] == ['systemctl', 'show']:
            name = argv[2]
            if '--property=LoadState' in argv:
                return b'not-found\n'
            if '--property=FragmentPath' in argv:
                return (str(self.systemd / name) + '\n').encode()
            if '--property=DropInPaths' in argv:
                return b'\n'
            if '--property=ActiveState' in argv:
                return b'active\n' if self.timer_active else b'inactive\n'
            if '--property=Result,ExecMainStatus' in argv:
                return ('Result=success\nExecMainStatus=' + self.main_status + '\n').encode()
        if argv == ['systemctl', 'start', s.SERVICE]:
            self.assertEqual(timeout, 620)
            if self.capture_mode == 'command-failure':
                raise RuntimeError('SYNTHETIC PRIVATE STDERR SHOULD NEVER APPEAR')
            if self.capture_mode != 'no-new-attempt':
                result = {'outcome': 'complete' if self.capture_mode == 'success' else 'failed',
                          'summary': {'complete': True, 'source_commit': self.commit}}
                s.write_private(self.monitor / '20260920T130000Z-abcdef01.json', result)
        if argv == ['systemctl', 'enable', s.TIMER]:
            directory = self.systemd / 'timers.target.wants'
            directory.mkdir(mode=0o755, exist_ok=True)
            directory.chmod(0o755)
            (self.systemd / s.LINK).symlink_to(self.systemd / s.TIMER)
            if self.extra_delta:
                (self.systemd / 'unrelated.service').write_text('CHANGED BY FAKE SYSTEMD')
        if argv == ['systemctl', 'start', s.TIMER]:
            self.timer_active = True
        if argv == ['systemctl', 'is-active', s.TIMER]:
            return b'active\n'
        if argv == ['systemctl', 'is-enabled', s.TIMER]:
            return b'enabled\n'
        if argv == ['systemctl', 'disable', '--now', s.TIMER]:
            self.timer_active = False
            (self.systemd / s.LINK).unlink(missing_ok=True)
        return b''

    def execute(self, payload):
        with patch.object(s.os, 'getuid', return_value=0), patch.object(s.os, 'fchown'), \
             patch.object(s, 'baseline', side_effect=self.inventory), \
             patch.object(s, 'command', side_effect=self.fake_command):
            return s.root_action(payload)

    def test_install_writes_exact_two_root_owned_units_and_never_starts_any_service(self):
        before = self.payload('install')
        result = self.execute(before)
        self.assertTrue(result['success'])
        self.assertEqual(set(self.inventory()['units']) - set(before['baseline']['units']), set(s.UNITS))
        self.assertEqual((self.systemd / 'unrelated.service').read_text(), 'PRESERVE ME')
        self.assertIn(['systemctl', 'daemon-reload'], self.calls)
        self.assertFalse(any(c[:2] in (['systemctl', 'start'], ['systemctl', 'enable']) for c in self.calls))
        for name in s.UNITS:
            self.assertEqual(s.metadata(self.systemd / name)['mode'], 0o644)
            self.assertEqual(s.digest(self.systemd / name), self.hashes['rebuild/deploy/' + name])

    def test_existing_target_and_symlink_refuse_without_replacement(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                path = self.systemd / s.SERVICE
                if symlink:
                    path.symlink_to(self.systemd / 'unrelated.service')
                else:
                    path.write_text('existing backup implementation')
                original = s.metadata(path)
                result = self.execute(self.payload('install'))
                self.assertFalse(result['success'])
                self.assertEqual(s.metadata(path), original)
                self.assertFalse((self.systemd / s.TIMER).exists())
                path.unlink()

    def test_source_drift_and_baseline_drift_refuse_before_changes(self):
        payload = self.payload('install')
        target = self.root / s.INSTALLER
        original = target.read_bytes()
        target.write_bytes(b'drift')
        with self.assertRaisesRegex(RuntimeError, 'Source drift'):
            self.execute(payload)
        target.write_bytes(original)
        (self.systemd / 'unrelated.service').write_text('operator changed file after baseline')
        with self.assertRaisesRegex(RuntimeError, 'Host changed'):
            self.execute(payload)
        self.assertFalse((self.systemd / s.SERVICE).exists())

    def test_successful_activation_requires_new_capture_before_only_timer_enable(self):
        self.install_fixtures()
        s.write_private(self.monitor / '20260919T010000Z-aabbccdd.json', {'outcome': 'complete'})
        result = self.execute(self.payload('activate'))
        self.assertTrue(result['success'])
        self.assertEqual(result['capture_attempt'], '20260920T130000Z-abcdef01.json')
        self.assertEqual(result['capture_attempt_sha256'], s.digest(self.monitor / result['capture_attempt']))
        self.assertLess(self.calls.index(['systemctl', 'start', s.SERVICE]),
                        self.calls.index(['systemctl', 'enable', s.TIMER]))
        self.assertEqual([c for c in self.calls if c[:2] == ['systemctl', 'start']],
                         [['systemctl', 'start', s.SERVICE], ['systemctl', 'start', s.TIMER]])
        self.assertTrue((self.monitor / '20260919T010000Z-aabbccdd.json').exists())

    def test_no_new_failed_and_nonzero_capture_never_enable_timer_or_reuse_old_success(self):
        self.install_fixtures()
        s.write_private(self.monitor / '20260919T010000Z-aabbccdd.json', {'outcome': 'complete'})
        for mode, status in [('no-new-attempt', '0'), ('failed-attempt', '0'), ('command-failure', '0'), ('success', '9')]:
            with self.subTest(mode=mode, status=status):
                self.capture_mode, self.main_status = mode, status
                self.calls = []
                result = self.execute(self.payload('activate'))
                self.assertFalse(result['success'])
                self.assertTrue(result['timer_stopped_disabled'])
                self.assertNotIn(['systemctl', 'enable', s.TIMER], self.calls)
                self.assertIn(['systemctl', 'disable', '--now', s.TIMER], self.calls)
                self.assertNotIn('PRIVATE STDERR', json.dumps(result))
                (self.monitor / '20260920T130000Z-abcdef01.json').unlink(missing_ok=True)

    def test_unrelated_delta_fails_and_rolls_back_only_new_timer(self):
        self.install_fixtures()
        self.extra_delta = True
        result = self.execute(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertTrue(result['timer_stopped_disabled'])
        rollback = [c for c in self.calls if c[1] in ('stop', 'disable')]
        self.assertEqual(rollback, [['systemctl', 'disable', '--now', s.TIMER]])
        self.assertTrue(all((self.systemd / name).exists() for name in s.UNITS))
        self.assertTrue((self.monitor / '20260920T130000Z-abcdef01.json').exists())

    def test_installed_hash_or_effective_override_refuses_activation(self):
        self.install_fixtures()
        (self.systemd / s.SERVICE).write_bytes(b'changed service')
        result = self.execute(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertNotIn(['systemctl', 'start', s.SERVICE], self.calls)

    def test_helper_has_pinned_existing_image_and_only_systemd_write_mount(self):
        argv = s.helper_command()
        self.assertIn('--pull=never', argv)
        self.assertIn('--log-driver=none', argv)
        self.assertIn(s.IMAGE, argv)
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        mounts = [argv[i + 1] for i, item in enumerate(argv) if item == '--mount']
        self.assertEqual(mounts, ['type=bind,src=/,dst=/host,readonly',
                                  'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system'])
        self.assertNotIn('python:3-slim', argv)

    def test_activation_plan_rejects_receipt_from_different_revision(self):
        self.install_fixtures()
        receipt = {'action': 'install', 'success': True, 'commit': 'b' * 40, 'hashes': self.hashes}
        s.write_private(self.monitor / 'installation.json', receipt)
        with patch.object(sys, 'argv', ['installer', '--action', 'activate', '--expected-commit', self.commit]), \
             patch.object(s, 'reviewed_source', return_value=self.hashes), \
             patch.object(s, 'baseline', side_effect=self.inventory), \
             patch.object(s, 'command', side_effect=self.fake_command):
            with self.assertRaisesRegex(RuntimeError, 'installation receipt required'):
                s.main()
        self.assertNotIn(['systemctl', 'start', s.SERVICE], self.calls)

    def test_helper_timeout_records_failure_without_claiming_capture_or_rollback(self):
        with patch.object(sys, 'argv', ['installer', '--execute', '--expected-commit', self.commit]), \
             patch.object(s, 'reviewed_source', return_value=self.hashes), \
             patch.object(s, 'baseline', side_effect=self.inventory), \
             patch.object(s, 'command', side_effect=self.fake_command), \
             patch.object(s.subprocess, 'run', side_effect=subprocess.TimeoutExpired(
                 ['fixture-helper'], 900, output=b'PRIVATE OUTPUT', stderr=b'PRIVATE ERROR')) as child, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(s.main(), 1)
        child.assert_called_once()
        results = list(self.evidence.glob('*-result.json'))
        self.assertEqual(len(results), 1)
        result = json.loads(results[0].read_bytes())
        self.assertFalse(result['success'])
        self.assertIn('unverified', result['error'])
        self.assertNotIn('timer_stopped_disabled', result)
        self.assertNotIn('PRIVATE', results[0].read_text() + output.getvalue())
        self.assertEqual(len(list(self.evidence.glob('*-before.json'))), 1)
        self.assertFalse((self.monitor / 'installation.json').exists())

    def test_reviewed_source_rejects_changed_file_and_wrong_declaration(self):
        def git_output(argv, timeout=40):
            if 'rev-parse' in argv:
                return self.commit.encode()
            if 'branch' in argv:
                return b'main'
            if 'show' in argv:
                relative = argv[-1].split(':', 1)[1]
                return (self.root / relative).read_bytes()
            if 'image' in argv:
                return s.IMAGE.encode()
            return b''
        with patch.object(s, 'command', side_effect=git_output):
            self.assertEqual(s.reviewed_source(self.commit), self.hashes)
            with patch.dict(s.os.environ, {'RULED_MUTATION_DECLARATION': 'wrong.md'}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'overnight ruled-mutation'):
                    s.reviewed_source(self.commit, mutation=True)
        with patch.object(s, 'command', side_effect=lambda argv, timeout=40:
                          b'wrong source' if 'show' in argv else git_output(argv, timeout)):
            with self.assertRaisesRegex(RuntimeError, 'Source differs'):
                s.reviewed_source(self.commit)


if __name__ == '__main__':
    unittest.main()
