"""Focused provider-free guards for the typed/voice activation and public static transition."""
import copy
import inspect
import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from ops import source_module

ROOT = Path(__file__).resolve().parents[2]
c = source_module.load('typed_voice_activation_tested', ROOT / 'scripts/activate-typed-voice.py')


class TypedVoiceActivationTests(unittest.TestCase):
    def test_measured_baseline_and_qualified_transports_are_pinned(self):
        self.assertEqual(c.BASELINE, '08e40870f18ca4e79b0cc2b27d6b09ba48f911a7')
        self.assertEqual(c.RUNNING_RELEASE, 'cf3905346d1b72d29cf602b98853f4017294afb5')
        self.assertEqual(c.sha((ROOT / c.ADAPTER).read_bytes()), c.ADAPTER_SHA256)
        self.assertIs(c.b.run, c.a.run)
        self.assertIs(c.b.output, c.a.output)
        self.assertIs(c.b.rows, c.full_rows)

    def test_no_unreviewed_runtime_or_migration_is_accepted(self):
        paths = c.RUNTIME_ALLOWED | {c.DECL, 'docs/rebuild/typed-voice.md'}
        c.validate_changed(paths)
        for bad in (paths - {c.SELF}, paths - {c.DECL}, paths - {'rebuild/templates/encounter_detail.html'},
                    paths | {'rebuild/core/migrations/0018_new.py'}, paths | {'rebuild/core/billing.py'},
                    paths | {'rebuild/ops/automatic_offsite.py'}, paths | {'rebuild/quillmd/settings.py'},
                    paths | {'docs/rebuild/../outside.md'}, paths | {'/absolute'}):
            with self.subTest(paths=bad), self.assertRaises(RuntimeError):
                c.validate_changed(bad)

    def test_full_rows_never_omit_later_finance_or_existing_migrations(self):
        old = SimpleNamespace(tables=Mock(return_value=['core_usage', 'core_costreconciliation', 'django_migrations']),
                              fingerprints=Mock(return_value={'current': 'full_rows'}))
        self.assertEqual(c.full_rows(old), {'current': 'full_rows'})
        old.fingerprints.assert_called_once_with(['core_usage', 'core_costreconciliation', 'django_migrations'])

    def test_every_stopped_state_component_must_remain_identical(self):
        before = {'rows': {'core_usage': {'rows': 17, 'sha256': 'current'},
                           'core_costreconciliation': {'rows': 1, 'sha256': 'new_authentic_evidence'}},
                  'schema': ['current0017'], 'constraints': ['current'], 'indexes': ['current'],
                  'catalog': {'triggers': 'current'}, 'clinical': {'finalized': 18},
                  'storage': {'files': 'current', 'mail': 'current'}, 'static': 'current',
                  'unit_files': 'current', 'shared_configs': 'current',
                  'preserved_operations': {'ticket': 'current', 'ledger': 'current', 'timer': 'current'}}
        c.unchanged(before, copy.deepcopy(before))
        for key in before:
            after = copy.deepcopy(before); after[key] = 'modified'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.unchanged(before, after)
        with self.assertRaises(RuntimeError):
            c.unchanged(before, dict(before, extra='unreviewed'))

    def test_only_already_applied_exact_migration_frontier_is_allowed(self):
        old = SimpleNamespace(PSQL=['fixture-psql'])
        plan = '[X] core.0016_user_session_version\n[X] core.0017_reconciliation_evidence_kind'
        with patch.object(c.b, 'output', side_effect=[c.MIGRATION, '1']):
            c.verify_migrations(old, plan)
        for bad in (plan.replace('[X] core.0017', '[ ] core.0017'), plan + '\n[ ] core.0018_other',
                    plan + '\n[X] core.0017_reconciliation_evidence_kind', plan + '\nunparsed'):
            with self.subTest(plan=bad), patch.object(c.b, 'output') as output, self.assertRaises(RuntimeError):
                c.verify_migrations(old, bad)
            output.assert_not_called()
        for values in (['0018_other'], [c.MIGRATION, '0'], [c.MIGRATION, '2']):
            with patch.object(c.b, 'output', side_effect=values), self.assertRaises(RuntimeError):
                c.verify_migrations(old, plan)

    def test_checkout_umask_is_child_only_and_role_exec_keeps_bytecode_guard(self):
        command = ['git', 'merge', '--ff-only', 'a' * 40]
        with patch.object(c.a, '_original_run') as run, patch.object(c.a.os, 'umask') as umask:
            c.b.run(command, env={'ONLY': 'preserved'})
            run.assert_called_once_with(command, env={'ONLY': 'preserved', 'PYTHONDONTWRITEBYTECODE': '1'}, umask=0o022)
            umask.assert_not_called()
        with patch.object(c.a, '_original_run') as run:
            c.b.run(['synthetic-command'], env={'ONLY': 'preserved'})
            self.assertNotIn('umask', run.call_args.kwargs)
            self.assertEqual(run.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')

    def test_stamp_changes_only_release_and_refuses_wrong_running_release(self):
        original = b'SYNTHETIC_OTHER=retained\nQUILLMD_RELEASE_SHA=' + c.RUNNING_RELEASE.encode() + b'\n'
        expected = b'SYNTHETIC_OTHER=retained\nQUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"\n'
        self.assertEqual(c.b.updated_environment(original, 'a' * 40), expected)
        with self.assertRaises(RuntimeError):
            c.b.updated_environment(original.replace(c.RUNNING_RELEASE.encode(), b'b' * 40), 'a' * 40)

    def test_historical_capture_does_not_freeze_operation_or_reconciliation_counts(self):
        import psycopg
        manifest = {'run_id': c.a.CAPTURE_RUN,
                    'tables': {'core_usage': {'rows': 15, 'sha256': 'old'},
                               'core_costreconciliation': {'rows': 0, 'sha256': 'empty'}},
                    'files': [{'path': 'retained', 'sha256': 'filehash', 'size': 8}]}
        actual = {'core_usage': {'rows': 17, 'sha256': 'later'},
                  'core_costreconciliation': {'rows': 1, 'sha256': 'authenticated_later'}}
        backup = SimpleNamespace(source_options=Mock(return_value={}), fingerprint=Mock(return_value=actual),
                                 invariant_counts=Mock(return_value={'usage_multiplier': 0}))
        storage = {'retained': {'sha256': 'filehash', 'size': 8}}
        with patch.object(psycopg, 'connect', return_value=MagicMock()), patch.object(c.a, 'BACKUP_COMPARISONS', []):
            c.assert_retained_capture(manifest, {'backup': backup}, storage)
            report = c.a.BACKUP_COMPARISONS[0]
            self.assertFalse(report['all_current_table_hashes_match_capture'])
            self.assertFalse(report['fresh_capture_performed'])
            self.assertEqual(report['current_table_fingerprints'], actual)
        with patch.object(psycopg, 'connect') as connect, self.assertRaises(RuntimeError):
            c.assert_retained_capture(manifest, {'backup': backup}, {'retained': {'sha256': 'changed', 'size': 8}})
        connect.assert_not_called()
        backup.invariant_counts.return_value = {'usage_multiplier': 1}
        with patch.object(psycopg, 'connect', return_value=MagicMock()), self.assertRaises(RuntimeError):
            c.assert_retained_capture(manifest, {'backup': backup}, storage)

    def test_source_gate_refuses_concurrent_main_or_dirty_target_before_actions(self):
        with patch.object(c, 'SOURCE', c.ROOT / '.worktrees' / 'synthetic'), \
             patch.object(c.Path, 'resolve', lambda path: path), \
             patch.object(c.b, 'output', return_value=' M rebuild/documents/engine.py'), \
             patch.object(c.b, 'run') as run, self.assertRaises(RuntimeError):
            c.verify_source('a' * 40)
        run.assert_not_called()
        with patch.object(c, 'SOURCE', c.ROOT / '.worktrees' / 'synthetic'), \
             patch.object(c.Path, 'resolve', lambda path: path), \
             patch.object(c.b, 'output', return_value=''), \
             patch.object(c.b, 'git', return_value='advanced_concurrent_main'), \
             patch.object(c.b, 'run') as run, self.assertRaises(RuntimeError):
            c.verify_source('a' * 40)
        run.assert_not_called()

    def test_code_only_path_stops_before_advance_and_never_runs_migrate(self):
        source = inspect.getsource(c.main)
        self.assertLess(source.index("word.systemd('stop', helper)"), source.index("b.run(['git', 'merge', '--ff-only'"))
        self.assertNotIn("management('migrate'", source)
        self.assertIn("declaration.read_bytes() == b.blob(args.target, DECL) == b.blob(commit, DECL)", source)
        self.assertIn('scripts/check-citation.sh', source)
        self.assertIn("identity.verify_live(args.target, storage)", source)
        self.assertIn("except BaseException as error", source)
        self.assertEqual(source.count("word.systemd('stop', helper)"), 2)
        self.assertEqual(source.count('unchanged(baseline,'), 3)


class PublicStaticTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def assets(self, name, css=b'old css', js=b'old js'):
        root = self.root / name
        root.mkdir(mode=0o755)
        inputs = {}
        manifest = {'paths': {}, 'version': '1.1', 'hash': 'fixture'}
        for source, data in [('app.css', css), ('app.js', js),
                             ('django_otp/css/login.css', b'otp login'),
                             ('otp_totp/css/qrcode.css', b'otp style'),
                             ('otp_totp/js/qrcode.js', b'otp script')]:
            path = root / source
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            for parent in path.parents:
                if parent == root.parent:
                    break
                parent.chmod(0o755)
            path.write_bytes(data)
            path.chmod(0o644)
            compiled = str(Path(source).with_suffix('')) + '.' + hashlib.md5(data).hexdigest()[:12] + Path(source).suffix
            (root / compiled).write_bytes(data)
            (root / compiled).chmod(0o644)
            inputs[source] = path
            manifest['paths'][source] = compiled
        manifest['hash'] = hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12]
        (root / 'staticfiles.json').write_text(json.dumps(manifest))
        (root / 'staticfiles.json').chmod(0o644)
        return root, inputs

    def test_real_file_transition_retains_old_hashes_and_publishes_new_exact_sources(self):
        old, _ = self.assets('old')
        new, inputs = self.assets('new', css=b'new css', js=b'new js')
        before = c.static_inventory(old)
        staged = c.validate_staged_static(new, inputs)
        c.retain_static(old, self.root / 'prior.tar', before)
        after = c.install_static(old, new, before, staged)
        self.assertEqual((old / 'app.css').read_bytes(), b'new css')
        self.assertEqual((old / 'app.js').read_bytes(), b'new js')
        old_hashes = [name for name in before if name.startswith('app.') and name not in ('app.css', 'app.js')]
        self.assertEqual(len(old_hashes), 2)
        for name in old_hashes:
            self.assertEqual(before[name], after[name])
        with c.tarfile.open(self.root / 'prior.tar') as archive:
            self.assertEqual(archive.extractfile('app.css').read(), b'old css')
            self.assertTrue(all(member.isfile() and not Path(member.name).is_absolute() for member in archive))
        self.assertEqual((self.root / 'prior.tar').stat().st_mode & 0o777, 0o600)

    def test_changed_old_hash_or_otp_asset_is_not_replaceable(self):
        old, _ = self.assets('old')
        new, inputs = self.assets('new')
        before, staged = c.static_inventory(old), c.validate_staged_static(new, inputs)
        for name in ('otp_totp/js/qrcode.js', next(name for name in before if name.startswith('app.') and name.endswith('.css') and name != 'app.css')):
            changed = copy.deepcopy(staged)
            changed[name]['sha256'] = 'changed'
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                c.static_delta(before, changed)

    def test_malformed_or_unbound_manifest_refuses_before_install(self):
        root, inputs = self.assets('source')
        manifest_path = root / 'staticfiles.json'
        original = json.loads(manifest_path.read_bytes())
        for bad in ('../outside.css', '/outside.css', 'app.000000000000.css', 'app.css'):
            value = copy.deepcopy(original)
            value['paths']['app.css'] = bad
            manifest_path.write_text(json.dumps(value))
            with self.subTest(path=bad), self.assertRaises(RuntimeError):
                c.validate_staged_static(root, inputs)
        manifest_path.write_text(json.dumps(original))
        (root / 'unknown.txt').write_text('not an approved public asset')
        (root / 'unknown.txt').chmod(0o644)
        with self.assertRaises(RuntimeError):
            c.validate_staged_static(root, inputs)

    def test_links_and_unsafe_ownership_modes_refuse(self):
        root, _ = self.assets('source')
        target = root / 'app.css'
        original = target.read_bytes()
        target.unlink()
        target.symlink_to(root / 'app.js')
        with self.assertRaises(RuntimeError):
            c.static_inventory(root)
        target.unlink()
        os.link(root / 'app.js', target)
        with self.assertRaises(RuntimeError):
            c.static_inventory(root)
        target.unlink()
        target.write_bytes(original)
        target.chmod(0o666)
        with self.assertRaises(RuntimeError):
            c.static_inventory(root)

    def test_concurrent_target_change_refuses_without_publication(self):
        old, _ = self.assets('old')
        new, inputs = self.assets('new', css=b'new css')
        before, staged = c.static_inventory(old), c.validate_staged_static(new, inputs)
        (old / 'app.js').write_bytes(b'concurrent actor')
        with self.assertRaises(RuntimeError):
            c.install_static(old, new, before, staged)
        self.assertEqual((old / 'app.css').read_bytes(), b'old css')

    def test_stage_drift_and_directory_expansion_refuse(self):
        old, _ = self.assets('old')
        new, inputs = self.assets('new', css=b'new css')
        before, staged = c.static_inventory(old), c.validate_staged_static(new, inputs)
        (new / 'app.css').write_bytes(b'changed after validation')
        with self.assertRaises(RuntimeError):
            c.install_static(old, new, before, staged)
        extra = copy.deepcopy(staged)
        extra['unapproved'] = dict(staged['.'])
        with self.assertRaises(RuntimeError):
            c.static_delta(before, extra)

    def test_interrupted_publication_retains_old_manifest_hashes_and_cleans_temporary_file(self):
        old, _ = self.assets('old')
        new, inputs = self.assets('new', css=b'new css')
        before, staged = c.static_inventory(old), c.validate_staged_static(new, inputs)
        replace = os.replace
        def interrupted(source, target):
            if target.name == 'staticfiles.json':
                raise OSError('isolated interruption before manifest publication')
            return replace(source, target)
        with patch.object(c.os, 'replace', side_effect=interrupted), self.assertRaises(OSError):
            c.install_static(old, new, before, staged)
        after = c.static_inventory(old)
        self.assertEqual(after['staticfiles.json'], before['staticfiles.json'])
        for name in before:
            if name.startswith('app.') and name not in ('app.css', 'app.js'):
                self.assertEqual(after[name], before[name])
        self.assertEqual(list(old.rglob('.typed-voice-*')), [])


if __name__ == '__main__':
    unittest.main()
