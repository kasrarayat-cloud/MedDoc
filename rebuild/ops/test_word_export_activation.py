"""Focused counterexamples for the preserving Word export activation. No host acts."""
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]
activation = source_module.load('word_export_activation_tested', ROOT / 'scripts/activate-word-export.py')


class WordExportActivationTests(unittest.TestCase):
    def valid_paths(self):
        return activation.PREMERGED_PATHS | {activation.SELF, activation.DECL}

    def test_full_payload_includes_previously_merged_runtime_helpers(self):
        # The activator compares the actual historical Git range on the host.
        # A shallow CI checkout has no such commits; unit tests exercise the
        # allowlist guard without pretending that history is available there.
        measured = activation.PREMERGED_PATHS
        for name in ('private_mail.py', 'private_storage.py', 'source_module.py'):
            self.assertIn('rebuild/ops/' + name, measured)
        self.assertIn('rebuild/documents/service.py', measured)
        activation.validate_changed(self.valid_paths())

    def test_unreviewed_code_and_omitted_declaration_refuse(self):
        for bad in (self.valid_paths() | {'rebuild/core/generation.py'},
                    self.valid_paths() - {activation.DECL},
                    self.valid_paths() - {'rebuild/documents/service.py'}):
            with self.subTest(paths=sorted(bad)), self.assertRaises(RuntimeError):
                activation.validate_changed(bad)

    def test_forbidden_schema_or_sandbox_refuses_even_if_allowlisted(self):
        for path in ('rebuild/core/migrations/0015_undeclared.py', 'rebuild/documents/sdk_word/Program.cs',
                     'rebuild/documents/sdk_sandbox.py', 'rebuild/deploy/quillmd-fresh-doctor.service',
                     'rebuild/quillmd/settings.py', 'rebuild/static/app.css'):
            with self.subTest(path=path), patch.object(activation, 'ALLOWED', activation.ALLOWED | {path}):
                with self.assertRaises(RuntimeError):
                    activation.validate_changed(self.valid_paths() | {path})

    def test_release_stamp_replacement_preserves_all_other_bytes(self):
        original = ('# protected synthetic fixture\nQUILLMD_RELEASE_SHA=' + activation.RUNNING_RELEASE
                    + '\nINTEGRATION_KEY=synthetic-not-a-key\nQUILLMD_PATIENT_DATA=disabled\n').encode()
        updated = activation.updated_environment(original, 'a' * 40)
        self.assertEqual(updated, original.replace(activation.RUNNING_RELEASE.encode(), b'a' * 40))
        for invalid in (original + b'QUILLMD_RELEASE_SHA=' + b'b' * 40 + b'\n',
                        original.replace(activation.RUNNING_RELEASE.encode(), b'b' * 40),
                        original.replace(b'QUILLMD_RELEASE_SHA=', b'#QUILLMD_RELEASE_SHA=')):
            with self.assertRaises(RuntimeError):
                activation.updated_environment(invalid, 'a' * 40)
        with self.assertRaises(RuntimeError):
            activation.updated_environment(original, 'short')

    def test_every_database_column_is_hashed_without_normalization(self):
        example = b'{"id":1,"notes":"synthetic note","export_sha256":"retained"}\n'
        with patch.object(activation.subprocess, 'check_output', return_value=example) as query:
            result = activation.fingerprints(['core_encounter', 'core_auditevent'])
        self.assertEqual(result['core_encounter'], {'rows': 1, 'sha256': hashlib.sha256(example).hexdigest()})
        for call in query.call_args_list:
            self.assertIn('to_jsonb(t)', call.args[0][-1])
            self.assertNotIn("-'", call.args[0][-1])
            self.assertNotIn('WHERE', call.args[0][-1])

    def test_unapplied_or_wrong_plan_output_cannot_look_like_no_migrations(self):
        applied = '[X] contenttypes.0001_initial\n[X] core.' + activation.CURRENT_MIGRATION + '\n'
        activation.verify_migration_plan(applied)
        for invalid in ('', applied + '[ ] core.0015_unreviewed\n',
                        'Planned operations:\ncore.0015_unreviewed\n',
                        '[X] contenttypes.0001_initial\n'):
            with self.subTest(plan=invalid), self.assertRaises(RuntimeError):
                activation.verify_migration_plan(invalid)

    def test_prior_report_change_or_deletion_refuses_new_report_does_not(self):
        before = {'first': {'sha256': 'a' * 64, 'bytes': 100}}
        self.assertTrue(activation.retained_unchanged(before, {**before, 'second': {'sha256': 'b' * 64}}))
        self.assertFalse(activation.retained_unchanged(before, {}))
        self.assertFalse(activation.retained_unchanged(before, {'first': {'sha256': 'b' * 64, 'bytes': 100}}))

    def test_loader_reads_changed_source_with_unchanged_size_and_mtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'helper.py'
            path.write_text('VALUE = "first"\n')
            with patch.object(activation, 'ROOT', root):
                original = activation.load('word_activation_source_probe', 'helper.py')
                stamp = path.stat().st_mtime_ns
                path.write_text('VALUE = "other"\n')
                os.utime(path, ns=(stamp, stamp))
                changed = activation.load('word_activation_source_probe', 'helper.py')
            self.assertEqual(original.VALUE, 'first')
            self.assertEqual(changed.VALUE, 'other')

    def test_no_executing_migration_static_install_or_advance_command(self):
        tree = ast.parse((ROOT / 'scripts/activate-word-export.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'run']
        strings = [[item.value for item in ast.walk(call) if isinstance(item, ast.Constant)
                    and isinstance(item.value, str)] for call in calls]
        for arguments in strings:
            self.assertNotIn('collectstatic', arguments)
            self.assertNotIn('migrate', arguments)
            self.assertNotIn('--ff-only', arguments)
        self.assertNotIn('install_artifact', [node.func.attr for node in ast.walk(tree)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)])


if __name__ == '__main__':
    unittest.main()
