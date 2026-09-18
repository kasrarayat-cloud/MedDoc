import contextlib
import errno
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import service_launcher as launcher
except ImportError:
    import service_launcher as launcher


class ServiceBoundaryTests(unittest.TestCase):
    def identity(self, **changes):
        status = {name: '0000000000000000' for name in launcher.CAP_FIELDS}
        status.update(Uid='321 321 321 321', Gid='654 654 654 654', Groups='654', NoNewPrivs='1')
        status.update(changes)
        return status

    def account(self):
        return patch.object(launcher.pwd, 'getpwnam', return_value=SimpleNamespace(
            pw_uid=321, pw_gid=654, pw_shell='/usr/sbin/nologin'))

    def group(self):
        return patch.object(launcher.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=654))

    def test_operator_docker_group_or_saved_root_identity_refuses_start(self):
        with self.account(), self.group():
            self.assertEqual(launcher.check_identity(self.identity())['uid'], 321)
            for status in (self.identity(Groups='654 110'), self.identity(Uid='321 321 0 321'),
                           self.identity(Gid='654 654 654 0')):
                with self.subTest(status=status), self.assertRaises(launcher.BoundaryFailure):
                    launcher.check_identity(status)

    def test_any_inherited_or_bounding_capability_refuses_start(self):
        with self.account(), self.group():
            for name in launcher.CAP_FIELDS:
                with self.subTest(name=name), self.assertRaises(launcher.BoundaryFailure):
                    launcher.check_identity(self.identity(**{name: '0000000000000001'}))
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.check_identity(self.identity(NoNewPrivs='0'))

    def test_missing_or_unexpected_error_is_not_secret_denial_proof(self):
        for failure in (FileNotFoundError(errno.ENOENT, 'missing'), OSError(errno.EIO, 'unavailable')):
            with patch.object(launcher.os, 'open', side_effect=failure), self.assertRaises(launcher.BoundaryFailure):
                launcher.denied_open('/synthetic', os.O_RDONLY, 'synthetic_secret')
        with patch.object(launcher.os, 'open', side_effect=PermissionError(errno.EACCES, 'denied')):
            self.assertTrue(launcher.denied_open('/synthetic', os.O_RDONLY, 'synthetic_secret')['denied'])

    def test_accessible_secret_and_writable_source_refuse_without_altering_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'synthetic'
            original = b'SYNTHETIC not a secret\n'
            path.write_bytes(original)
            for flags in (os.O_RDONLY, os.O_WRONLY):
                with self.subTest(flags=flags), self.assertRaises(launcher.BoundaryFailure):
                    launcher.denied_open(path, flags, 'synthetic')
                self.assertEqual(path.read_bytes(), original)

    def test_read_only_mount_proves_write_denial_but_not_secret_read_denial(self):
        with patch.object(launcher.os, 'open', side_effect=OSError(errno.EROFS, 'read-only')):
            self.assertTrue(launcher.denied_open('/source', os.O_WRONLY, 'code_write')['denied'])
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.denied_open('/secret', os.O_RDONLY, 'secret')

    def test_socket_connection_is_used_and_missing_socket_is_inconclusive(self):
        with patch.object(launcher.socket, 'socket') as factory:
            client = factory.return_value.__enter__.return_value
            client.connect.side_effect = PermissionError(errno.EACCES, 'denied')
            self.assertTrue(launcher.denied_docker_socket()['denied'])
            client.connect.assert_called_once_with('/run/docker.sock')
            client.send.assert_not_called()
            client.sendall.assert_not_called()
            for failure in (None, FileNotFoundError(errno.ENOENT, 'missing')):
                client.connect.side_effect = failure
                with self.subTest(failure=failure), self.assertRaises(launcher.BoundaryFailure):
                    launcher.denied_docker_socket()

    def test_private_canary_roundtrip_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            result = launcher.writable_canary(path, os.getuid(), os.getgid())
            self.assertTrue(result['read_write_delete'])
            self.assertEqual(list(path.iterdir()), [])

    def test_state_symlink_or_group_readable_directory_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            actual = parent / 'actual'
            actual.mkdir(mode=0o700)
            link = parent / 'link'
            link.symlink_to(actual)
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.writable_canary(link, os.getuid(), os.getgid())
            actual.chmod(0o750)
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.writable_canary(actual, os.getuid(), os.getgid())
            self.assertEqual(list(actual.iterdir()), [])

    def test_environment_file_cannot_select_wrong_surface_or_state_root(self):
        environment = {'QUILLMD_SECRET_KEY': 'synthetic-test-value', 'QUILLMD_DB_PASSWORD': 'synthetic-test-value',
                       'QUILLMD_DB_USER': 'quillmd_runtime', 'QUILLMD_DB_NAME': 'quillmd_fresh',
                       'QUILLMD_RELEASE_SHA': 'a' * 40, 'QUILLMD_ADMIN_SITE': '1',
                       'QUILLMD_ENV_MANAGED': '0', 'QUILLMD_STATE_DIR': '/tmp/wrong'}
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        with patch.dict(os.environ, environment, clear=True):
            launcher.prepare_environment('doctor')
            self.assertEqual(os.environ['QUILLMD_ADMIN_SITE'], '0')
            self.assertEqual(os.environ['QUILLMD_ENV_MANAGED'], '1')
            self.assertEqual(os.environ['QUILLMD_STATE_DIR'], '/var/lib/quillmd')
            # The environment file cannot move parser workspaces off the encrypted state volume.
            self.assertEqual(os.environ['TMPDIR'], '/var/lib/quillmd/tmp')
            self.assertIsNone(launcher.tempfile.tempdir)
            os.environ['TMPDIR'] = '/tmp'
            launcher.prepare_environment('admin')
            self.assertEqual(os.environ['TMPDIR'], '/var/lib/quillmd/tmp')
            self.assertEqual(os.environ['QUILLMD_ADMIN_SITE'], '1')
            os.environ['QUILLMD_DB_USER'] = 'quillmd_fresh'
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.prepare_environment('worker')

    def test_command_allowlist_cannot_execute_supplied_program(self):
        with self.assertRaises(launcher.BoundaryFailure):
            launcher.fixed_command('/bin/sh')
        self.assertIn('127.0.0.1:9130', launcher.fixed_command('doctor'))
        self.assertIn('127.0.0.1:9131', launcher.fixed_command('admin'))
        self.assertEqual(launcher.fixed_command('worker')[-1], 'worker')

    def test_failure_never_executes_or_prints_raw_exception_payload(self):
        output = io.StringIO()
        with patch.object(launcher, 'probe', side_effect=RuntimeError('sensitive synthetic token')), \
             patch.object(launcher.os, 'execv') as execute, contextlib.redirect_stdout(output):
            self.assertEqual(launcher.main(['--surface', 'doctor']), 1)
        execute.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertFalse(report['passed'])
        self.assertEqual(report['check'], 'RuntimeError')
        self.assertNotIn('sensitive synthetic token', output.getvalue())

    def test_success_executes_same_process_fixed_command_after_proof(self):
        report = {'passed': True, 'pid': 123, 'mount_namespace': 'mnt:[456]'}
        calls = []
        class ExecSentinel(BaseException):
            pass
        def execute(*args):
            calls.append(('exec', args))
            raise ExecSentinel()
        with patch.object(launcher, 'probe', return_value=report), \
             patch.object(launcher, 'save_proof', side_effect=lambda *args: calls.append(('proof', args))), \
             patch.object(launcher.os, 'chdir'), patch.object(launcher.os, 'execv', side_effect=execute), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ExecSentinel):
            launcher.main(['--surface', 'doctor'])
        self.assertEqual([x[0] for x in calls], ['proof', 'exec'])
        command = launcher.fixed_command('doctor')
        self.assertEqual(calls[-1][1], (command[0], command))

    def test_proof_is_private_and_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(launcher, 'STATE', Path(temp)):
            proofs = Path(temp) / 'proofs'
            proofs.mkdir(mode=0o700)
            launcher.save_proof('doctor', {'passed': True})
            self.assertEqual((proofs / 'doctor.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((proofs / 'doctor.json').read_text()), {'passed': True})
            (proofs / 'worker.json').symlink_to(proofs / 'doctor.json')
            with self.assertRaises(launcher.BoundaryFailure):
                launcher.save_proof('worker', {'passed': False})
            self.assertEqual(json.loads((proofs / 'doctor.json').read_text()), {'passed': True})


if __name__ == '__main__':
    unittest.main()
