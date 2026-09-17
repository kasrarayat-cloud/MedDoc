"""Synthetic recovery guards only; no Docker, database or service actions."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/resume-word-beta.py'
spec = importlib.util.spec_from_file_location('word_recovery_tested', SOURCE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class WordRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_exact_recovery_diff_refuses_schema_sdk_units_or_unrelated_changes(self):
        recovery.validate_changes(recovery.ALLOWED_CHANGES)
        for extra in ('rebuild/core/migrations/0012_unreviewed.py', 'rebuild/core/views.py',
                      'rebuild/documents/sdk_word/Adapter/WmAdapter.cs',
                      'rebuild/deploy/quillmd-fresh-doctor.service', 'docs/unreviewed.md'):
            with self.subTest(extra=extra), self.assertRaises(RuntimeError):
                recovery.validate_changes(recovery.ALLOWED_CHANGES | {extra})
        with self.assertRaises(RuntimeError):
            recovery.validate_changes(recovery.ALLOWED_CHANGES - {'rebuild/quillmd/static_storage.py'})

    def test_authentic_failed_report_and_exact_partial_stage_required(self):
        report = {'target': recovery.BROKEN_RELEASE, 'previous_head': 'synthetic-baseline',
                  'complete': False, 'provider_calls': 0, 'stage': 'applying_three_json_columns',
                  'failure_kind': 'RuntimeError', 'failure_services_stopped': True,
                  'database_after_all_columns': {str(i): {} for i in range(33)},
                  'storage_before': {'files': {}, 'mail': {}},
                  'artifact': {'manifest_sha256': recovery.MANIFEST_SHA},
                  'schema_before': ['before'], 'schema_after': ['after']}
        word = SimpleNamespace(BASELINE='synthetic-baseline', unique_json=json.loads, check_schema=Mock())
        data = json.dumps(report).encode()
        with patch.object(recovery, 'FAILED_REPORT_SHA', recovery.digest(data)):
            self.assertEqual(recovery.validate_failed_report(word, data), report)
            word.check_schema.assert_called_once_with(['before'], ['after'])
            with self.assertRaises(RuntimeError): recovery.validate_failed_report(word, data+b' ')
        for key, value in [('complete', True), ('stage', 'starting_and_verifying_private_services'),
                           ('provider_calls', 1), ('failure_services_stopped', False)]:
            changed = {**report, key: value}; data = json.dumps(changed).encode()
            with self.subTest(key=key), patch.object(recovery, 'FAILED_REPORT_SHA', recovery.digest(data)), self.assertRaises(RuntimeError):
                recovery.validate_failed_report(word, data)

    def test_partial_audit_binds_environment_without_exposing_credentials(self):
        env = b'EXAMPLE_SYNTHETIC_VALUE=fixture-only\n'
        audit = {'complete': True, 'main_head': recovery.BROKEN_RELEASE,
                 'failed_report_sha256': recovery.FAILED_REPORT_SHA, 'word_env_keys_present': False,
                 'provider_calls': 0, 'all33_old_row_hashes_match': True,
                 'all33_post_schema_table_hashes_match': True, 'schema_matches_declared_after': True,
                 'all_files_mail_identical': True, 'private_env_sha256': recovery.digest(env)}
        data = json.dumps(audit).encode(); word = SimpleNamespace(unique_json=json.loads)
        with patch.object(recovery, 'PARTIAL_AUDIT_SHA', recovery.digest(data)):
            recovery.validate_partial_audit(word, data, env)
            with self.assertRaises(RuntimeError): recovery.validate_partial_audit(word, data, env+b'CHANGED=1\n')
            with self.assertRaises(RuntimeError): recovery.validate_partial_audit(word, data+b' ', env)

    def static_fixture(self):
        root = self.root / 'staticfiles'; root.mkdir(mode=0o755); root.chmod(0o755)
        bad = root / recovery.BAD_ASSET; bad.write_bytes(b'synthetic deterministic gzip'); bad.chmod(0o664)
        css = root / 'app.css'; css.write_bytes(b'body { color: black; }'); css.chmod(0o644)
        return root, bad, css

    def test_only_observed_asset_mode_may_change_and_all_content_is_preserved(self):
        root, bad, css = self.static_fixture()
        with patch.object(recovery, 'APP', self.root), patch.object(recovery, 'BAD_ASSET_SHA', recovery.digest(bad.read_bytes())):
            before = recovery.static_inventory(before=True)
            bad.chmod(0o644)
            after = recovery.static_inventory(before=False)
            recovery.compare_static(before, after)
            css.write_bytes(b'body { color: red; }')
            changed = recovery.static_inventory(before=False)
            with self.assertRaises(RuntimeError): recovery.compare_static(before, changed)

    def test_static_links_extra_permission_exceptions_and_content_tampering_refused(self):
        root, bad, css = self.static_fixture()
        with patch.object(recovery, 'APP', self.root), patch.object(recovery, 'BAD_ASSET_SHA', recovery.digest(bad.read_bytes())):
            css.chmod(0o664)
            with self.assertRaises(RuntimeError): recovery.static_inventory(before=True)
            css.chmod(0o644); css.unlink(); css.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError): recovery.static_inventory(before=True)
            css.unlink(); bad.write_bytes(b'changed gzip')
            with self.assertRaises(RuntimeError): recovery.static_inventory(before=True)

    def test_postmigration_full_column_or_file_changes_fail_preservation_gate(self):
        failed = {'schema_after': ['synthetic schema'], 'database_after_all_columns': {'all-columns': 'hash'},
                  'database_before': {'normalized': 'hash'}, 'storage_before': {'files': {'old.docx': 'hash'}, 'mail': {}},
                  'retained_reports_before': {'old-report': 'hash'}}
        word = SimpleNamespace(schema=Mock(return_value=failed['schema_after']), check_new_defaults=Mock(),
                               fingerprints=Mock(side_effect=[failed['database_after_all_columns'], failed['database_before']]),
                               retained_reports=Mock(return_value=failed['retained_reports_before']),
                               STATE=self.root, UNITS=[])
        storage = SimpleNamespace(inventory=lambda path: failed['storage_before'][path.name])
        recovery.verify_preserved(word, storage, failed)
        word.fingerprints=Mock(return_value={'changed-new-column': 'hash'})
        with self.assertRaises(RuntimeError): recovery.verify_preserved(word, storage, failed)
        word.fingerprints=Mock(side_effect=[failed['database_after_all_columns'], failed['database_before']])
        storage.inventory=lambda path: {'changed-file': 'hash'}
        with self.assertRaises(RuntimeError): recovery.verify_preserved(word, storage, failed)

    def test_stopped_guard_refuses_running_service_or_pending_job(self):
        word = SimpleNamespace(UNITS=['one-private-unit'], PSQL=['synthetic-psql'])
        with patch.object(recovery, 'output', side_effect=['inactive', '0', '0']): recovery.stopped(word)
        for replies in (['active'], ['inactive', '123'], ['inactive', '0', '1']):
            with self.subTest(replies=replies), patch.object(recovery, 'output', side_effect=replies), self.assertRaises(RuntimeError):
                recovery.stopped(word)

    def test_publication_failure_stops_services_and_keeps_recovery_lock(self):
        lock = self.root / 'recovery.lock'; lock.write_bytes(b'synthetic lock')
        result = self.root / 'result.json'; backlink = self.root / 'backlink.json'
        identity = SimpleNamespace(private_write=Mock(side_effect=[None, OSError('synthetic disk failure'), None]))
        word = SimpleNamespace(checked_file=Mock(return_value=b'synthetic complete result'), systemd=Mock())
        with self.assertRaises(OSError):
            recovery.publish_result(identity, word, 'synthetic helper', result, lock, backlink, {'complete': True})
        word.systemd.assert_called_once_with('stop', 'synthetic helper')
        self.assertTrue(lock.exists())
        marker = identity.private_write.call_args.args
        self.assertEqual(marker[0].name, 'result-publication-failure.json')
        self.assertFalse(marker[1]['complete'])
        self.assertTrue(marker[1]['failure_services_stopped'])


if __name__ == '__main__':
    unittest.main()
