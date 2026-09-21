"""Focused provider-free guards for the code-only compatibility activation."""
import copy
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from ops import source_module

ROOT = Path(__file__).resolve().parents[2]
c = source_module.load('colonoscopy_activation_tested', ROOT / 'scripts/activate-colonoscopy-compatibility.py')


class ColonoscopyActivationTests(unittest.TestCase):
    def test_measured_baseline_and_qualified_transports_are_pinned(self):
        self.assertEqual(c.BASELINE, c.RUNNING_RELEASE)
        self.assertEqual(c.BASELINE, '47374a9462dfe5bceb0947c831fc23e35a01e239')
        self.assertEqual(c.sha((ROOT / c.ADAPTER).read_bytes()), c.ADAPTER_SHA256)
        self.assertIs(c.b.run, c.a.run)
        self.assertIs(c.b.output, c.a.output)
        self.assertIs(c.b.rows, c.full_rows)

    def test_no_unreviewed_runtime_or_migration_is_accepted(self):
        paths = c.RUNTIME_ALLOWED | {c.DECL, 'docs/rebuild/colonoscopy-compatibility.md'}
        c.validate_changed(paths)
        for bad in (paths - {c.SELF}, paths - {c.DECL}, paths - {'rebuild/documents/engine.py'},
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
        self.assertEqual(source.count('unchanged(baseline,'), 2)


if __name__ == '__main__':
    unittest.main()
