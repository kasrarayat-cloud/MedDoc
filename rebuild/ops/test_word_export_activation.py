"""Focused counterexamples for the preserving Word export activation. No host acts."""
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
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


class RetainedStaticInventoryTests(unittest.TestCase):
    """Synthetic disk fixtures exercise acceptance and concrete refused changes."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.app = self.root / 'app'
        self.static = self.app / 'staticfiles'
        self.static.mkdir(parents=True)
        self.current = self.app / 'static/app.css'
        self.current.parent.mkdir()
        self.current.write_bytes(b'current synthetic CSS\n')
        (self.static / 'app.css').write_bytes(self.current.read_bytes())
        self.compiled = 'app.0123456789ab.css'
        (self.static / self.compiled).write_bytes(self.current.read_bytes())
        (self.static / 'staticfiles.json').write_text(json.dumps({'paths': {'app.css': self.compiled}}))
        self.css_name = 'app.39d54d0ccd1a.css'
        self.legacy_css = b'prior synthetic CSS\n'
        payloads = {self.css_name: self.legacy_css, self.css_name + '.gz': gzip.compress(self.legacy_css, mtime=0)}
        expected = {}
        for name, payload in payloads.items():
            path = self.static / name
            path.write_bytes(payload)
            path.chmod(0o644)
            expected[name] = {'directory': False, 'mode': 0o644, 'size': len(payload),
                              'sha256': hashlib.sha256(payload).hexdigest()}
        self.proof = {'complete': True, 'static_before': expected, 'static_after': expected}
        self.proof_bytes = json.dumps(self.proof).encode()
        self.identity = SimpleNamespace(static_sources=lambda: {'app.css': self.current})
        self.word = SimpleNamespace(checked_file=lambda path, *, private: self.proof_bytes)
        for name, value in (('APP', self.app), ('ROOT', self.root), ('PRIVATE', self.app / '.runtime'),
                            ('RETAINED_STATIC', expected),
                            ('RETAINED_STATIC_REPORT_SHA256', hashlib.sha256(self.proof_bytes).hexdigest())):
            context = patch.object(activation, name, value)
            context.start()
            self.addCleanup(context.stop)
        context = patch.object(activation.subprocess, 'check_output', return_value=self.legacy_css)
        self.git = context.start()
        self.addCleanup(context.stop)

    def inventory(self):
        return activation.static_inventory(self.identity, self.word)

    def test_current_assets_and_exact_retained_pair_remain_in_inventory(self):
        before = self.inventory()
        self.assertEqual(set(before), {'.', 'app.css', self.compiled, 'staticfiles.json',
                                      self.css_name, self.css_name + '.gz'})
        self.assertEqual(before, self.inventory())
        self.git.assert_called_with(['git', 'show', activation.RETAINED_STATIC_SOURCE], cwd=self.root)

    def test_unknown_third_historical_hash_is_not_authorized(self):
        (self.static / 'app.111111111111.css').write_bytes(self.legacy_css)
        with self.assertRaisesRegex(RuntimeError, 'outside the reviewed public asset set'):
            self.inventory()

    def test_changed_retained_bytes_and_mode_are_refused(self):
        path = self.static / self.css_name
        for replacement in (b'alter synthetic CSS\n', self.legacy_css + b'changed'):
            path.write_bytes(replacement)
            with self.assertRaisesRegex(RuntimeError, 'exact historical bytes or mode'):
                self.inventory()
        path.write_bytes(self.legacy_css)
        path.chmod(0o664)
        with self.assertRaisesRegex(RuntimeError, 'exact historical bytes or mode'):
            self.inventory()

    def test_gzip_is_pinned_even_when_it_decompresses_to_same_css(self):
        path = self.static / (self.css_name + '.gz')
        path.write_bytes(gzip.compress(self.legacy_css, mtime=1))
        self.assertEqual(gzip.decompress(path.read_bytes()), self.legacy_css)
        with self.assertRaisesRegex(RuntimeError, 'exact historical bytes or mode'):
            self.inventory()

    def test_report_hash_and_both_historical_inventory_entries_are_required(self):
        original = self.proof_bytes
        self.proof_bytes = original + b' '
        with self.assertRaisesRegex(RuntimeError, 'provenance report changed'):
            self.inventory()
        changed = json.loads(original)
        del changed['static_before'][self.css_name]
        self.proof_bytes = json.dumps(changed).encode()
        with patch.object(activation, 'RETAINED_STATIC_REPORT_SHA256', hashlib.sha256(self.proof_bytes).hexdigest()):
            with self.assertRaisesRegex(RuntimeError, 'not preserved by the historical recovery'):
                self.inventory()
        changed = json.loads(original)
        changed['static_after'][self.css_name]['mode'] = 0o666
        self.proof_bytes = json.dumps(changed).encode()
        with patch.object(activation, 'RETAINED_STATIC_REPORT_SHA256', hashlib.sha256(self.proof_bytes).hexdigest()):
            with self.assertRaisesRegex(RuntimeError, 'not preserved by the historical recovery'):
                self.inventory()

    def test_historical_git_source_is_an_independent_required_match(self):
        self.git.return_value = b'a different historical source\n'
        with self.assertRaisesRegex(RuntimeError, 'initial fresh implementation'):
            self.inventory()

    def test_unknown_symlink_and_hardlink_still_refuse(self):
        link = self.static / 'unreviewed.css'
        link.symlink_to(self.current)
        with self.assertRaisesRegex(RuntimeError, 'free of symlinks'):
            self.inventory()
        link.unlink()
        os.link(self.static / self.css_name, link)
        with self.assertRaisesRegex(RuntimeError, 'linked or oversized'):
            self.inventory()

    def test_current_manifest_and_source_guards_remain(self):
        original = self.current.read_bytes()
        self.current.write_bytes(b'changed source\n')
        with self.assertRaisesRegex(RuntimeError, 'current application source'):
            self.inventory()
        self.current.write_bytes(original)
        manifest = self.static / 'staticfiles.json'
        manifest.write_text(json.dumps({'paths': {'app.css': self.compiled, 'unexpected.js': 'extra.js'}}))
        with self.assertRaisesRegex(RuntimeError, 'installed OTP assets'):
            self.inventory()
        manifest.write_text(json.dumps({'paths': {'app.css': '../wrong.css'}}))
        with self.assertRaisesRegex(RuntimeError, 'unexpected path'):
            self.inventory()


if __name__ == '__main__':
    unittest.main()
