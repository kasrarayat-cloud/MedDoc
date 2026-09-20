import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
try:
    from . import backup_restore as b
except ImportError:
    import backup_restore as b


class BackupSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.cipher = Fernet(Fernet.generate_key())

    def test_private_write_refuses_existing_destination(self):
        dest = self.root / 'key'
        b.write_private(dest, b'synthetic')
        with self.assertRaises(FileExistsError):
            b.write_private(dest, b'replacement')
        self.assertEqual(dest.read_bytes(), b'synthetic')
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)

    def test_private_file_symlink_refused(self):
        dest = self.root / 'key'
        b.write_private(dest, b'synthetic')
        link = self.root / 'link'
        link.symlink_to(dest)
        with self.assertRaises(RuntimeError):
            b.read_private(link)

    def test_world_readable_key_refused(self):
        dest = self.root / 'key'
        b.write_private(dest, Fernet.generate_key())
        dest.chmod(0o644)
        with self.assertRaises(RuntimeError):
            b.key_at(dest)

    def test_path_traversal_and_noncanonical_paths_refused(self):
        for name in ('../secret', '/secret', 'one/../secret', 'a//b', 'a\\b', ''):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                b.safe_relative(name)

    def test_media_symlink_outside_root_refused(self):
        (self.root / 'out').symlink_to('/etc/passwd')
        with self.assertRaises(RuntimeError):
            b.file_data(self.root, 'out')

    def object(self):
        plain = b'synthetic original bytes'
        encrypted = self.cipher.encrypt(plain)
        path = self.root / 'object'
        b.write_private(path, encrypted)
        return path, {'cipher_sha256': b.digest(encrypted), 'sha256': b.digest(plain), 'size': len(plain)}

    def test_ciphertext_tamper_refused(self):
        path, metadata = self.object()
        path.write_bytes(path.read_bytes()[:-3] + b'abc')
        with self.assertRaises(RuntimeError):
            b.decrypt_checked(path, metadata, self.cipher)

    def test_wrong_key_refused(self):
        path, metadata = self.object()
        with self.assertRaises(InvalidToken):
            b.decrypt_checked(path, metadata, Fernet(Fernet.generate_key()))

    def test_authenticated_wrong_object_not_accepted(self):
        path, metadata = self.object()
        replacement = self.cipher.encrypt(b'different authenticated data')
        path.write_bytes(replacement)
        metadata['cipher_sha256'] = b.digest(replacement)
        with self.assertRaises(RuntimeError):
            b.decrypt_checked(path, metadata, self.cipher)

    def test_incomplete_backup_refused_before_decrypt(self):
        b.write_private(self.root / 'INCOMPLETE', b'failed')
        with self.assertRaises(RuntimeError):
            b.load_backup(self.root, self.cipher)

    def test_duplicate_restore_paths_refused(self):
        row = {'path': 'originals/synthetic.docx', 'object': 'objects/' + 'a' * 64 + '.fernet'}
        manifest = {'format': 1, 'complete': True, 'database': b.SOURCE_DATABASE,
                    'files': [row, row], 'image_id': 'sha256:' + 'a' * 64}
        b.write_private(self.root / 'manifest.json.fernet', self.cipher.encrypt(json.dumps(manifest).encode()))
        with self.assertRaises(RuntimeError):
            b.load_backup(self.root, self.cipher)

    def test_restore_check_writes_no_decrypted_documents_and_never_swaps(self):
        import inspect
        source = inspect.getsource(b.restore)
        self.assertNotIn("/ 'files'", source)
        self.assertEqual(source.count('write_private('), 1)
        self.assertIn("write_private(restored / 'verification.json'", source)
        self.assertIn("'--memory', '768m', '--memory-swap', '768m'", source)
        self.assertIn("'--tmpfs', '/var/lib/postgresql/data:", source)
        self.assertIn('decrypted_files_written=0', source)
        # The tmpfs/no-swap evidence is measured from HostConfig, where docker lists --tmpfs mounts, not written as a literal.
        self.assertIn("host_config.get('Tmpfs')", source)
        self.assertIn("host_config.get('MemorySwap') == host_config.get('Memory')", source)
        self.assertIn('restore_database_on_tmpfs_without_swap=on_tmpfs_without_swap', source)

    def test_backup_never_writes_the_database_dump_to_a_temporary_file(self):
        import inspect
        source = inspect.getsource(b.backup)
        self.assertNotIn('tempfile', source)
        self.assertNotIn('TemporaryFile', source)
        self.assertIn('plain = run([', source)

    def test_restore_cleanup_rejects_other_container(self):
        metadata = {'Config': {'Labels': {b.LABEL: 'another-run'}},
                    'HostConfig': {'NetworkMode': 'none', 'PortBindings': {}}}
        with patch.object(b, 'inspect_container', return_value=metadata), patch.object(b, 'run') as execute:
            with self.assertRaises(RuntimeError):
                b.remove_owned_restore('unrelated', 'this-run')
            execute.assert_not_called()

    def test_restore_cleanup_rejects_published_port(self):
        metadata = {'Config': {'Labels': {b.LABEL: 'this-run'}},
                    'HostConfig': {'NetworkMode': 'bridge', 'PortBindings': {'5432/tcp': []}}}
        with patch.object(b, 'inspect_container', return_value=metadata), patch.object(b, 'run') as execute:
            with self.assertRaises(RuntimeError):
                b.remove_owned_restore('quillmd-restore-this-run', 'this-run')
            execute.assert_not_called()


class RestoreReadinessSurvivesThePostgresInitRace(unittest.TestCase):
    """The postgres entrypoint answers pg_isready from a TEMPORARY server while it runs initdb, then stops it. A restore that
    trusts that answer meets the handover: exactly how the 2026-09-18T11:09Z restore failed (container up 11:09:07, gone
    11:09:09), with no reason recorded."""

    class Runner:
        def __init__(self, marker_after=0):
            self.calls, self.marker_after = 0, marker_after

        def __call__(self, args, **kwargs):
            import subprocess as sp
            self.calls += 1
            if args[1] == 'logs':
                seen = self.calls > self.marker_after
                return sp.CompletedProcess(args, 0, b'ready to accept connections\n' + (b.READY_MARKER if seen else b''), b'')
            if 'pg_isready' in args:
                return sp.CompletedProcess(args, 0, b'', b'')          # the temporary init server answers too
            return sp.CompletedProcess(args, 0, b'1\n', b'')

    def test_a_ready_answer_without_the_completion_marker_is_not_ready(self):
        runner = self.Runner(marker_after=10**6)
        self.assertFalse(b.restore_ready('quillmd-restore-test', runner=runner))

    def test_ready_once_the_entrypoint_reports_init_complete_and_a_statement_answers(self):
        self.assertTrue(b.restore_ready('quillmd-restore-test', runner=self.Runner(marker_after=0)))

    def test_not_ready_when_the_server_cannot_answer_a_statement(self):
        import subprocess as sp

        def runner(args, **kwargs):
            if args[1] == 'logs':
                return sp.CompletedProcess(args, 0, b.READY_MARKER, b'')
            if 'pg_isready' in args:
                return sp.CompletedProcess(args, 0, b'', b'')
            return sp.CompletedProcess(args, 1, b'', b'FATAL: the database system is shutting down')

        self.assertFalse(b.restore_ready('quillmd-restore-test', runner=runner))

    def test_the_restore_waits_for_readiness_before_it_restores_and_records_the_failing_stage(self):
        import ast
        source = Path(b.__file__).read_text()
        body = source[source.index('def restore('):source.index('def main(')]
        self.assertLess(body.index('restore_ready('), body.index("'restoring_the_dump'"))
        self.assertLess(body.index("'restoring_the_dump'"), body.index("'pg_restore'"))
        self.assertIn("result['failed_stage'] = result.get('stage')", body)
        self.assertIn("result['error_class'] = type(failure).__name__", body)
        # The failing command's own output is never recorded: a database error can quote row data.
        self.assertNotIn('stderr.decode', body)
        ast.parse(source)


class RestoreCleanupFailureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.manifest = dict(image_id='sha256:' + 'a' * 64, dump={}, files=[],
                             tables={'synthetic': {'rows': 2, 'sha256': 'b' * 64}},
                             invariants={'wallet_bounds': 0}, run_id='synthetic-backup')
        self.args = SimpleNamespace(key_file='synthetic-key', backup=self.root,
                                    output=self.root, keep_container=False)
        for name, replacement in (
            ('key_at', {'return_value': object()}),
            ('load_backup', {'return_value': (self.root, self.manifest)}),
            ('decrypt_checked', {'return_value': b'synthetic dump'}),
            ('run', {'return_value': self.manifest['image_id'].encode()}),
            ('restore_ready', {'return_value': True}),
            ('fingerprint', {'return_value': self.manifest['tables']}),
            ('invariant_counts', {'return_value': self.manifest['invariants']}),
            ('restore_query', {'return_value': [{'count': 8}]}),
            ('inspect_container', {'return_value': {'Mounts': [], 'HostConfig': {
                'Tmpfs': {'/var/lib/postgresql/data': 'rw'}, 'ReadonlyRootfs': True,
                'Memory': 768, 'MemorySwap': 768, 'NetworkMode': 'none', 'PortBindings': {}}}}),
            ('remove_owned_restore', {'side_effect': RuntimeError('private-cleanup-canary')}),
        ):
            patch.object(b, name, **replacement).start()
        self.addCleanup(patch.stopall)

    def evidence(self):
        return json.loads(next(self.root.glob('restore-*/verification.json')).read_text())

    def test_successful_comparison_with_failed_cleanup_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
            b.restore(self.args)
        evidence = self.evidence()
        self.assertFalse(evidence['complete'])
        self.assertTrue(evidence['data_verification_complete'])
        self.assertTrue(evidence['cleanup_failed'])
        self.assertTrue(evidence['container_retained'])
        self.assertEqual(evidence['failed_stage'], 'cleaning_the_isolated_database')
        self.assertNotIn('canary', json.dumps(evidence))

    def test_primary_restore_failure_survives_cleanup_failure(self):
        with patch.object(b, 'fingerprint', side_effect=ValueError('primary synthetic failure')):
            with self.assertRaisesRegex(ValueError, 'primary synthetic failure'):
                b.restore(self.args)
        evidence = self.evidence()
        self.assertFalse(evidence['complete'])
        self.assertEqual(evidence['error_class'], 'ValueError')
        self.assertEqual(evidence['failed_stage'], 'restoring_the_dump')
        self.assertTrue(evidence['cleanup_failed'])
        self.assertTrue(evidence['container_retained'])
        self.assertNotIn('canary', json.dumps(evidence))


if __name__ == '__main__':
    unittest.main()
