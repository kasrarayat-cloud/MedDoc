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


class PreparationReferenceTests(unittest.TestCase):
    def references(self, rows):
        return b.file_references(lambda statement: [('core_aistagereceipt',)] if statement.startswith('SELECT to_regclass') else rows.get(
            next(kind for kind, text in b.FILE_QUERIES+b.SEMANTIC_FILE_QUERIES if text == statement), []))

    def test_all_preparation_artifacts_are_included_alongside_legacy_files(self):
        kinds = b.PREPARATION_FILE_KINDS | {'original', 'export', 'audio', 'receipt'}
        rows = {kind: [(kind + '/synthetic.bin', 'a' * 64)] for kind in kinds}
        seen = []
        def query(statement):
            seen.append(statement)
            if statement.startswith('SELECT to_regclass'):return [('core_aistagereceipt',)]
            return next(rows[kind] for kind, text in b.FILE_QUERIES+b.SEMANTIC_FILE_QUERIES if statement == text)
        references = b.file_references(query)
        self.assertEqual(seen, ["SELECT to_regclass('public.core_aistagereceipt')"]+[statement for _, statement in b.FILE_QUERIES+b.SEMANTIC_FILE_QUERIES])
        self.assertEqual(set(references), {kind + '/synthetic.bin' for kind in kinds})
        for kind in b.PREPARATION_FILE_KINDS:
            self.assertEqual(references[kind + '/synthetic.bin']['expected_sha256'], 'a' * 64)

    def test_current_approved_and_historical_refs_share_bytes_without_losing_provenance(self):
        row = ('prepared/synthetic.docx', 'a' * 64)
        references = self.references({'approved_prepared': [row], 'candidate': [row],
                                      'candidate_history': [row, row]})
        self.assertEqual(set(references), {row[0]})
        self.assertEqual(references[row[0]]['kinds'],
                         ['approved_prepared', 'candidate', 'candidate_history', 'candidate_history'])

    def test_conflicting_current_and_historical_hashes_are_not_deduplicated_away(self):
        with self.assertRaisesRegex(RuntimeError, 'Conflicting database file hashes'):
            self.references({'candidate': [('prepared/synthetic.docx', 'a' * 64)],
                             'candidate_history': [('prepared/synthetic.docx', 'b' * 64)]})

    def test_unhashed_legacy_audio_keeps_its_semantics_and_gains_any_known_hash(self):
        path = 'synthetic/shared.bin'
        self.assertEqual(self.references({'audio': [(path, '')]})[path]['expected_sha256'], '')
        self.assertEqual(self.references({'audio': [(path, '')],
            'preparation_response': [(path, 'b' * 64)]})[path]['expected_sha256'], 'b' * 64)

    def test_every_new_reference_needs_a_complete_canonical_hash(self):
        for kind in b.PREPARATION_FILE_KINDS:
            for value in ('', None, 'a' * 63, 'A' * 64, 'a' * 65, 'x' * 64, 123):
                with self.subTest(kind=kind, digest=value), self.assertRaises(RuntimeError):
                    self.references({kind: [('prepared/synthetic.docx', value)]})

    def test_invalid_history_or_partial_pair_sentinels_cannot_be_copied(self):
        for kind in b.PREPARATION_FILE_KINDS:
            for path in ('../invalid-preparation-reference', '../invalid-candidate-history',
                         '../secret', '/secret', 'a//b', 'a\\b', ''):
                with self.subTest(kind=kind, path=path), self.assertRaises(RuntimeError):
                    self.references({kind: [(path, 'a' * 64)]})

    def test_no_file_for_unwritten_or_unknown_responses_is_invented(self):
        self.assertEqual(self.references({}), {})


class PreparationCaptureTests(unittest.TestCase):
    """Real encrypted files with a DB-snapshot/pg_dump fixture, never a live DB."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        (self.source / 'core').mkdir(parents=True)
        (self.source / 'core/models.py').write_text('# synthetic source\n')
        (self.source / '.runtime').mkdir(mode=0o700)
        self.media = self.root / 'state/files'
        self.media.mkdir(parents=True)
        self.destination = self.root / 'backups'
        self.key = self.root / 'key'
        b.write_private(self.key, Fernet.generate_key())
        self.cipher = b.key_at(self.key)
        self.args = SimpleNamespace(source=self.source, output=self.destination, key_file=self.key)
        self.statements = []
        self.rows = {}
        self.snapshot_exported = False
        self.committed = False
        owner = self
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, statement):
                owner.statements.append(statement)
                if statement == 'SELECT pg_export_snapshot()':
                    owner.snapshot_exported = True
                    return SimpleNamespace(fetchone=lambda: ('synthetic-snapshot',))
                if statement == 'COMMIT': owner.committed = True
                if statement.startswith('SELECT to_regclass'):return SimpleNamespace(fetchall=lambda: [('core_aistagereceipt',)])
                if statement in {text for _, text in b.FILE_QUERIES+b.SEMANTIC_FILE_QUERIES}:
                    if not owner.snapshot_exported:
                        raise AssertionError('References queried outside exported snapshot')
                    return SimpleNamespace(fetchall=lambda: owner.rows.get(statement, []))
                return SimpleNamespace(fetchall=lambda: [])
        try:
            from . import private_storage
        except ImportError:
            import private_storage
        for target, name, options in [
                (b.psycopg, 'connect', {'return_value': Connection()}),
                (b, 'source_options', {'return_value': {'password': 'synthetic-only', 'user': 'synthetic-backup'}}),
                (b, 'inspect_container', {'return_value': {'Id': 'synthetic-container', 'Image': 'sha256:'+'a'*64,
                    'State': {'Running': True}, 'HostConfig': {'PortBindings':
                        {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}}}}),
                (b, 'fingerprint', {'return_value': {'synthetic': {'rows': 1, 'sha256': 'b'*64}}}),
                (b, 'invariant_counts', {'return_value': {'wallet_bounds': 0}}),
                (private_storage, 'state_root', {'return_value': self.media.parent})]:
            patcher = patch.object(target, name, **options)
            patcher.start()
            self.addCleanup(patcher.stop)
        def run(args, **kwargs):
            if args[0] == 'git': return b'c' * 40 + b'\n'
            self.assertIn('--snapshot=synthetic-snapshot', args)
            return b'synthetic encrypted database snapshot'
        runner = patch.object(b, 'run', side_effect=run)
        self.run = runner.start()
        self.addCleanup(runner.stop)

    def add_reference(self, kind, path, data):
        target = self.media / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        statement = next(text for row_kind, text in b.FILE_QUERIES+b.SEMANTIC_FILE_QUERIES if kind == row_kind)
        self.rows.setdefault(statement, []).append((path, b.digest(data)))

    def backup_directory(self):
        return next(self.destination.iterdir())

    def test_capture_authenticates_each_new_kind_from_the_same_readonly_snapshot(self):
        from contextlib import redirect_stdout
        from io import StringIO
        for kind in b.PREPARATION_FILE_KINDS:
            self.add_reference(kind, kind + '/synthetic.bin', ('synthetic ' + kind).encode())
        with redirect_stdout(StringIO()): b.backup(self.args)
        root, manifest = b.load_backup(self.backup_directory(), self.cipher)
        self.assertTrue(self.committed)
        self.assertLess(self.statements.index('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY'),
                        self.statements.index('SELECT pg_export_snapshot()'))
        self.assertEqual({kind for row in manifest['files'] for kind in row['kinds']}, b.PREPARATION_FILE_KINDS)
        self.assertEqual(len(manifest['files']), len(b.PREPARATION_FILE_KINDS))
        for row in manifest['files']:
            self.assertEqual(b.decrypt_checked(root / row['object'], row, self.cipher),
                             (self.media / row['path']).read_bytes())
        self.assertEqual(b.decrypt_checked(root / 'database.dump.fernet', manifest['dump'], self.cipher),
                         b'synthetic encrypted database snapshot')

    def test_missing_historical_file_leaves_incomplete_capture_without_dump_or_commit(self):
        self.add_reference('candidate_history', 'prepared/history.docx', b'synthetic historical bytes')
        (self.media / 'prepared/history.docx').unlink()
        with self.assertRaises(FileNotFoundError): b.backup(self.args)
        folder = self.backup_directory()
        self.assertTrue((folder / 'INCOMPLETE').exists())
        self.assertFalse((folder / 'manifest.json.fernet').exists())
        self.assertFalse((folder / 'database.dump.fernet').exists())
        self.assertFalse(self.committed)
        self.assertFalse(any('pg_dump' in call.args[0] for call in self.run.call_args_list))

    def test_tampered_prepared_file_is_rejected_before_dump_and_completion(self):
        self.add_reference('approved_prepared', 'prepared/approved.docx', b'approved synthetic bytes')
        (self.media / 'prepared/approved.docx').write_bytes(b'tampered synthetic bytes')
        with self.assertRaisesRegex(RuntimeError, 'database integrity hash'): b.backup(self.args)
        self.assertTrue((self.backup_directory() / 'INCOMPLETE').exists())
        self.assertFalse(self.committed)

    def test_late_response_change_keeps_capture_incomplete_even_after_dump(self):
        self.add_reference('preparation_response', 'preparation-receipts/response.json', b'synthetic response')
        original = b.file_data
        calls = []
        def changing(root, path):
            calls.append(path)
            return original(root, path) if len(calls) == 1 else b'changed after encryption'
        with patch.object(b, 'file_data', side_effect=changing):
            with self.assertRaisesRegex(RuntimeError, 'changed during snapshot'): b.backup(self.args)
        folder = self.backup_directory()
        self.assertTrue((folder / 'database.dump.fernet').exists())
        self.assertTrue((folder / 'INCOMPLETE').exists())
        self.assertFalse((folder / 'manifest.json.fernet').exists())
        self.assertFalse(self.committed)


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
