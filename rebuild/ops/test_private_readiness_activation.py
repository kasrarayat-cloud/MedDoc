"""Focused guards for preserving security activation; no host mutations."""
import copy
import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]
activation = source_module.load('private_readiness_activation_tested', ROOT / 'scripts/activate-private-readiness.py')


class PrivateReadinessActivationTests(unittest.TestCase):
    def paths(self):
        return activation.RUNTIME_ALLOWED | {activation.DECL, 'docs/rebuild/private-readiness-20260920.md'}

    def test_only_scoped_target_and_declared_schema_are_admitted(self):
        activation.validate_changed(self.paths())
        for changed in (self.paths() - {activation.DECL}, self.paths() - {activation.MIGRATION_PATH},
                        self.paths() | {'rebuild/quillmd/settings.py'},
                        self.paths() | {'rebuild/core/migrations/0017_unreviewed.py'},
                        self.paths() | {'docs/rebuild/../outside.md'}):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                activation.validate_changed(changed)

    def test_measured_prior_operations_delta_excludes_app_and_schema(self):
        import subprocess
        actual = set(subprocess.check_output(['git', 'diff', '--name-only', activation.RUNNING_RELEASE,
                         activation.BASELINE, '--', 'rebuild'], cwd=ROOT, text=True).splitlines())
        self.assertEqual(actual, activation.BASELINE_OPERATION_PATHS)
        self.assertFalse(any(name.startswith(('rebuild/core/', 'rebuild/quillmd/', 'rebuild/templates/')) for name in actual))

    def test_release_stamp_changes_no_configuration_bytes(self):
        for ending in (b'\n', b'\r\n', b''):
            before = b'SYNTHETIC_CREDENTIAL="retain-exactly"\nexport QUILLMD_RELEASE_SHA = "' + activation.RUNNING_RELEASE.encode() + b'"' + ending
            after = activation.updated_environment(before, 'a' * 40)
            self.assertEqual(after, b'SYNTHETIC_CREDENTIAL="retain-exactly"\nQUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"' + ending)
        for before in (b'OTHER=one\n', b'QUILLMD_RELEASE_SHA=wrong\n',
                       (b'QUILLMD_RELEASE_SHA=' + activation.RUNNING_RELEASE.encode() + b'\n') * 2):
            with self.assertRaises(RuntimeError):
                activation.updated_environment(before, 'a' * 40)

    def plan(self, pending):
        return '[X] core.' + activation.PREVIOUS_MIGRATION + '\n[' + (' ' if pending else 'X') + ']  core.' + activation.MIGRATION

    def test_only0016_may_be_pending(self):
        activation.verify_migration_plan(self.plan(True), applied=False)
        activation.verify_migration_plan(self.plan(False), applied=True)
        for plan in (self.plan(False), self.plan(True) + '\n[ ] core.0017_wrong',
                     self.plan(True) + '\nwarning', self.plan(True) + '\n[X] core.' + activation.MIGRATION):
            with self.assertRaises(RuntimeError):
                activation.verify_migration_plan(plan, applied=False)

    def test_migration_bytes_pinned(self):
        source = (ROOT / activation.MIGRATION_PATH).read_bytes()
        activation.validate_migration(source)
        with self.assertRaises(RuntimeError):
            activation.validate_migration(source + b'\n# unreviewed\n')

    def test_all_private_units_must_stop(self):
        with patch.object(activation, 'output', side_effect=['inactive', '0'] * 3) as query:
            activation.stopped()
        self.assertEqual(query.call_count, 6)
        for values in (['active'], ['inactive', '42'], ['inactive', '0', 'failed']):
            with patch.object(activation, 'output', side_effect=values), self.assertRaises(RuntimeError):
                activation.stopped()

    def test_unreadable_source_refuses_before_snapshot_lock_or_service_stop(self):
        target = 'a' * 40
        helper = 'sha256:' + 'b' * 64
        arguments = SimpleNamespace(target=target, backup_report='synthetic-proof',
                                    backup_directory=None, result='unused', execute=True)
        word = SimpleNamespace(
            checked_file=lambda path, **kw: (b'QUILLMD_RELEASE_SHA=' + activation.RUNNING_RELEASE.encode() + b'\n'
                                            if path.name == '.env' else json.dumps({'helper_image': helper}).encode()),
            systemd=Mock(), expected_inputs=Mock(return_value={}), verify_artifact=Mock())
        identity = SimpleNamespace(verify_live=Mock(return_value={}), private_write=Mock(),
                                   source_readability=Mock(side_effect=RuntimeError('unreadable installed source')))
        old = SimpleNamespace(tables=lambda: list(range(35)), PSQL=['synthetic-psql'], worker_process=Mock(return_value={}))
        modules = {'old': old, 'word': word, 'identity': identity, 'storage': SimpleNamespace(),
                   'previous': SimpleNamespace(protected=Mock(return_value={})),
                   'billing': SimpleNamespace(SDK_RELEASE='retained', PIN='retained'),
                   'backup': SimpleNamespace(), 'env': SimpleNamespace()}

        def git(*args):
            if args == ('rev-parse', 'HEAD'): return activation.BASELINE
            if args == ('branch', '--show-current'): return 'main'
            if args == ('rev-parse', 'origin/main'): return target
            if args[0] == 'status': return ''
            if args[:2] == ('diff', '--name-only'):
                return '\n'.join(activation.BASELINE_OPERATION_PATHS if args[2] == activation.RUNNING_RELEASE else self.paths())
            raise AssertionError(args)

        def output(command, **kwargs):
            if command[0] == 'gh': return json.dumps([{'merged_at': 'synthetic-date', 'merge_commit_sha': target, 'base': {'ref': 'main'}}])
            if command[0] == 'docker': return helper
            if command[0] == 'synthetic-psql':
                return activation.PREVIOUS_MIGRATION if 'SELECT name' in command[-1] else '0'
            raise AssertionError(command)

        with patch.object(activation.argparse.ArgumentParser, 'parse_args', return_value=arguments), \
             patch.object(activation, 'SOURCE', activation.ROOT / '.worktrees' / 'synthetic-refutation'), \
             patch.object(activation, 'git', side_effect=git), patch.object(activation, 'run'), \
             patch.object(activation, 'output', side_effect=output), \
             patch.object(activation, 'blob', side_effect=lambda target, name: (ROOT / name).read_bytes()), \
             patch.object(activation, 'load', side_effect=lambda name, relative, target: modules[name]), \
             patch.object(activation, 'health', return_value={}), \
             patch.object(activation, 'backup_evidence', return_value=({}, {})), \
             patch.object(activation, 'snapshot') as snapshot:
            with self.assertRaisesRegex(RuntimeError, 'unreadable installed source'):
                activation.main()
        identity.source_readability.assert_called_once_with(helper)
        snapshot.assert_not_called()
        identity.private_write.assert_not_called()
        word.systemd.assert_not_called()

    def snapshots(self):
        before = {'schema': [{'table_name': 'core_user', 'column_name': 'existing', 'ordinal_position': 12}],
                  'constraints': [('old_table', 'old_check', 'c', '-', 'CHECK (true)')],
                  'indexes': ['unchanged-index'], 'catalog': {'functions': ['immutable'], 'triggers': ['immutable']},
                  'rows': {'core_user': {'sha256': 'old-data'}}, 'storage': {'original': 'hash'},
                  'unit_files': {'unit': 'hash'}}
        after = copy.deepcopy(before)
        after['schema'].append({'table_name': 'core_user', 'column_name': 'session_version',
            'ordinal_position': 13, 'data_type': 'bigint', 'udt_name': 'int8', 'is_nullable': 'NO',
            'column_default': None, 'numeric_precision': 64, 'numeric_scale': 0})
        after['constraints'].append(('core_user', 'core_user_session_version_check', 'c', '-', 'CHECK ((session_version >= 0))'))
        return before, after

    def test_exact_additive_column_check_and_unchanged_state_pass(self):
        activation.validate_after(*self.snapshots())

    def test_changed_old_field_catalog_file_index_or_other_state_refuses(self):
        before, after = self.snapshots()
        for key in ('rows', 'storage', 'unit_files', 'catalog', 'indexes'):
            wrong = copy.deepcopy(after); wrong[key] = ['changed']
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                activation.validate_after(before, wrong)
        wrong = copy.deepcopy(after); wrong['schema'][0]['column_name'] = 'changed'
        with self.assertRaises(RuntimeError):
            activation.validate_after(before, wrong)

    def test_wrong_new_type_default_nullability_constraint_or_extra_delta_refuses(self):
        before, after = self.snapshots()
        for key, value in (('column_default', '0'), ('data_type', 'text'), ('is_nullable', 'YES'),
                           ('numeric_precision', 32), ('ordinal_position', 44)):
            wrong = copy.deepcopy(after); wrong['schema'][-1][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                activation.validate_after(before, wrong)
        for checks in (after['constraints'][:-1], after['constraints'] + [after['constraints'][-1]],
                       after['constraints'] + [('extra', 'extra', 'c', '-', 'CHECK (true)')]):
            wrong = copy.deepcopy(after); wrong['constraints'] = checks
            with self.assertRaises(RuntimeError):
                activation.validate_after(before, wrong)

    def test_existing_rows_project_only_new_user_column_and_exact_migration(self):
        old = SimpleNamespace(tables=lambda: ['core_user', 'core_encounter', 'django_migrations'], PSQL=['synthetic-psql'])
        with patch.object(activation.subprocess, 'check_output', return_value=b'{"immutable":"row"}\n') as query:
            actual = activation.rows(old, exclude_new=True)
        statements = [call.args[0][-1] for call in query.call_args_list]
        self.assertIn("to_jsonb(t) - 'session_version'", statements[0])
        self.assertNotIn('session_version', statements[1])
        self.assertIn("name='0016_user_session_version'", statements[2])
        self.assertEqual(actual['core_user']['rows'], 1)

    def test_session_generation_matches_initial_active_and_inactive_account_policy(self):
        old = SimpleNamespace(PSQL=['synthetic-psql'])
        with patch.object(activation, 'output', return_value='0') as query:
            activation.verify_session_versions(old)
        self.assertIn('CASE WHEN is_active THEN 0 ELSE 1 END', query.call_args.args[0][-1])
        with patch.object(activation, 'output', return_value='1'), self.assertRaises(RuntimeError):
            activation.verify_session_versions(old)

    def test_baseline_backup_reader_is_retained_when_target_repairs_cleanup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reader.py'; path.write_text('qualified = True\n')
            before = path.read_bytes()
            with patch.object(activation, 'ROOT', Path(directory)), patch.object(activation, 'blob', side_effect=lambda target, name: before if target == activation.BASELINE else b'qualified = False\n'):
                module = activation.load('backup', 'reader.py', 'a' * 40)
                self.assertTrue(module.qualified)
                with self.assertRaises(RuntimeError):
                    activation.load('word', 'reader.py', 'a' * 40)

    def restore_result(self):
        report = {'complete': True, 'all_table_hashes_match': True, 'all_file_hashes_match': True,
                  'restore_database_on_tmpfs_without_swap': True, 'network': 'none', 'published_ports': 0,
                  'workers_started': 0, 'provider_actions': 0, 'decrypted_files_written': 0,
                  'provider_credentials_copied': False, 'container_retained': False,
                  'invariants': {'one': 0}, 'backup_run_id': activation.RESTORED_RUN}
        return {'complete': True, 'independent_key_restore_verified': True, 'backup_run_id': activation.RESTORED_RUN,
                'manifest_cipher_sha256': activation.RESTORED_MANIFEST_SHA256, 'exact_temporary_container_absent': True,
                'live_fernet_key_used': False, 'original_plaintext_used': False, 'isolated_restore': report}

    def check_result(self, result):
        raw = json.dumps(result).encode()
        with patch.object(activation, 'RESTORE_RESULT_SHA256', activation.sha(raw)):
            return activation.validate_restore_result(raw)

    def test_complete_independent_proof_and_nested_invariants_required(self):
        proof = self.restore_result()
        self.check_result(proof)
        for key, value in (('live_fernet_key_used', True), ('exact_temporary_container_absent', False), ('independent_key_restore_verified', False)):
            wrong = copy.deepcopy(proof); wrong[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.check_result(wrong)
        for key, value in (('cleanup_failed', True), ('invariants', {}), ('invariants', {'one': 1}), ('provider_actions', 1)):
            wrong = copy.deepcopy(proof); wrong['isolated_restore'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.check_result(wrong)
        with self.assertRaises(RuntimeError):
            activation.validate_restore_result(json.dumps(proof).encode())

    def test_retained_rollback_source_requires_safe_paths_and_security_forward_repair(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as bundle:
            data = b'# synthetic source\n'; member = tarfile.TarInfo('rebuild/manage.py'); member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
        result = activation.retained_source_manifest(stream.getvalue())
        self.assertEqual(result['commit'], activation.BASELINE)
        self.assertIn('never restore the database or run older auth code', ' '.join(result['recovery_policy']))


if __name__ == '__main__':
    unittest.main()
