"""Provider-free guards for the combined admin-console and doctor/form private activation.

The act adds ONE table and moves BOTH public assets. Every guard here exists to make a
difference outside that declared delta refuse, and to stop a receipt describing an act
that did not happen.
"""
import copy
import inspect
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import types
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ops import source_module

ROOT = Path(__file__).resolve().parents[2]
c = source_module.load('admin_console_activation_tested', ROOT / 'scripts/activate-admin-console.py')

COLUMNS = [{'table_name': c.NEW_TABLE, 'column_name': name, 'ordinal_position': index}
           for index, name in enumerate(c.NEW_COLUMNS, start=1)]
BEFORE = {
    'tables': ['core_usage', 'django_migrations'],
    'rows': {'core_usage': {'rows': 17, 'sha256': 'current'},
             'django_migrations': {'rows': 30, 'sha256': 'current'}},
    'schema': [{'table_name': 'core_usage', 'column_name': 'id', 'ordinal_position': 1}],
    'constraints': [('core_usage', 'core_usage_pkey', 'p', '-', 'PRIMARY KEY (id)')],
    'indexes': [('core_usage', 'core_usage_pkey', 'CREATE UNIQUE INDEX ...')],
    'catalog': {'functions': ['current'], 'triggers': ['current']},
    'clinical': {'finalized': 18, 'encounters': 28},
    'storage': {'files': 'current', 'mail': 'current'},
    'static': 'current', 'unit_files': 'current', 'shared_configs': 'current',
    'preserved_operations': {'ticket': 'current'},
    'new_table_rows': None,
}
AFTER = copy.deepcopy(BEFORE)
AFTER['tables'] = ['core_servicehealth', 'core_usage', 'django_migrations']
AFTER['schema'] = BEFORE['schema'] + COLUMNS
AFTER['constraints'] = BEFORE['constraints'] + [
    (c.NEW_TABLE, 'service_health_interval_sane', 'c', '-', 'CHECK ((expected_interval_seconds >= 60))')]
AFTER['indexes'] = BEFORE['indexes'] + [(c.NEW_TABLE, 'core_servicehealth_pkey', 'CREATE UNIQUE INDEX ...')]
AFTER['new_table_rows'] = 0


class PinnedIdentity(unittest.TestCase):
    def test_driver_and_reviewed_migration_are_pinned_to_their_actual_bytes(self):
        self.assertEqual(c.sha((ROOT / c.DRIVER).read_bytes()), c.DRIVER_SHA256)
        self.assertEqual(c.sha((ROOT / c.MIGRATION_PATH).read_bytes()), c.MIGRATION_SHA256)
        self.assertEqual(c.BASELINE, 'e66d84abbb4cda663dc4489d175c71d477572fca')
        self.assertEqual(c.RUNNING_RELEASE, c.BASELINE)
        self.assertEqual(c.PREVIOUS_MIGRATION, '0017_reconciliation_evidence_kind')

    def test_the_declared_columns_are_exactly_the_migrations_own(self):
        source = (ROOT / c.MIGRATION_PATH).read_text()
        self.assertEqual(list(c.NEW_COLUMNS), [line.split("('", 1)[1].split("'", 1)[0]
                                               for line in source.splitlines()
                                               if line.strip().startswith("('") and 'models.' in line])
        self.assertIn("name='ServiceHealth'", source)
        self.assertNotIn('DeleteModel', source)
        self.assertNotIn('RemoveField', source)
        self.assertNotIn('AlterField', source)

    def test_inherited_receipt_name_is_renamed_and_the_rename_is_not_inert(self):
        self.assertIn(c.RESULT_PATTERN, (ROOT / c.DRIVER).read_text())
        self.assertIn(c.RESULT_PATTERN, inspect.getsource(c.t.main))
        self.assertTrue(c.t.re.fullmatch(c.RESULT_PATTERN, 'admin-console-activation-0123abcd.json'))
        self.assertIsNone(c.t.re.fullmatch(c.RESULT_PATTERN, 'typed-voice-activation-0123abcd.json'))
        self.assertTrue(c.t.re.fullmatch('[a-f0-9]{40}', 'a' * 40))
        self.assertIsNone(c.t.re.fullmatch('[a-f0-9]{40}', 'g' * 40))

    def test_the_inherited_entry_point_is_configured_to_this_adapter(self):
        self.assertIs(c.t.validate_changed, c.validate_changed)
        self.assertIs(c.t.verify_migrations, c.verify_migrations)
        self.assertIs(c.t.unchanged, c.unchanged)
        self.assertIs(c.t.snapshot, c.snapshot)
        self.assertIs(c.b.rows, c.rows)
        self.assertIs(c.a.receipt, c.receipt)
        self.assertEqual(c.t.SELF, c.SELF)
        self.assertEqual(c.b.MIGRATION, c.MIGRATION)
        self.assertEqual(c.b.MIGRATION_SHA256, c.MIGRATION_SHA256)
        self.assertEqual(c.a.CAPTURE_RUN, '20260921T043001Z-0a6f66da')

    def test_a_drifted_driver_or_an_inert_rename_refuses_to_load_at_all(self):
        """Load-time pins are load-bearing: prove the module REFUSES, not merely that the constant matches."""
        source = (ROOT / c.SELF).read_text()
        for mutated, label in ((source.replace(c.DRIVER_SHA256, 'f' * 64), 'driver bytes drifted'),
                               (source.replace(c.RESULT_PATTERN, 'a-pattern-the-driver-never-uses'),
                                'receipt rename would be inert')):
            self.assertNotEqual(mutated, source)
            module = types.ModuleType('admin_console_activation_refusal')
            module.__file__ = str(ROOT / c.SELF)
            with self.subTest(case=label), self.assertRaises(RuntimeError):
                exec(compile(mutated, str(ROOT / c.SELF), 'exec'), module.__dict__)

    def test_a_read_only_load_creates_no_private_evidence_directory(self):
        self.assertIn('--execute', inspect.getsource(c).rsplit('__main__', 1)[1])
        self.assertFalse((c.EVIDENCE / 'must-not-exist').exists())


class DeclaredSourceScope(unittest.TestCase):
    def paths(self):
        return c.RUNTIME_ALLOWED | {c.DECL, c.SCREENSHOTS + '01-overview.jpg',
                                    c.SCREENSHOTS + 'README.md', 'docs/rebuild/admin-console-acceptance.md'}

    def test_the_reviewed_combined_diff_is_accepted(self):
        c.validate_changed(self.paths())

    def test_every_undeclared_or_missing_change_refuses(self):
        good = self.paths()
        for bad in (good - {c.SELF}, good - {c.DECL}, good - {c.MIGRATION_PATH},
                    good - {'rebuild/static/app.js'}, good - {'rebuild/static/app.css'},
                    good - {c.OPS_TEST}, good - {'rebuild/core/admin_console.py'},
                    good | {'rebuild/core/migrations/0019_other.py'},
                    good | {'rebuild/static/vendor.js'},
                    good | {'rebuild/ops/backup_restore.py'},
                    good | {'rebuild/ops/private_storage.py'},
                    good | {'.github/workflows/test.yml'},
                    good | {'rebuild/deploy/quillmd-fresh-worker.service'},
                    good | {'rebuild/core/billing.py'},
                    good | {c.SCREENSHOTS + 'evil.sh'},
                    good | {'docs/rebuild/../outside.md'}, good | {'/absolute'}):
            with self.subTest(missing_or_extra=sorted(bad ^ good)), self.assertRaises(RuntimeError):
                c.validate_changed(bad)

    def test_each_narrow_guard_refuses_even_when_the_general_allowlist_would_not(self):
        """Widen the allowlist so the general check cannot fire, and prove each narrow guard alone.

        Without this the narrow guards are untested: the general check refuses these paths first,
        so a mutation that removes a narrow guard leaves the suite green.
        """
        for extra in ('rebuild/ops/backup_restore.py', 'rebuild/ops/private_storage.py',
                      'rebuild/core/migrations/0019_other.py', 'rebuild/static/vendor.js',
                      '.github/workflows/test.yml', 'rebuild/deploy/quillmd-fresh-worker.service',
                      'deploy/quillmd-fresh-admin.service'):
            widened = c.RUNTIME_ALLOWED | {extra}
            with self.subTest(path=extra), patch.object(c, 'RUNTIME_ALLOWED', widened), \
                 self.assertRaises(RuntimeError):
                c.validate_changed(self.paths() | {extra})
        # Positive control: the widening itself does not make everything refuse.
        with patch.object(c, 'RUNTIME_ALLOWED', c.RUNTIME_ALLOWED | {'rebuild/core/harmless.py'}):
            c.validate_changed(self.paths() | {'rebuild/core/harmless.py'})

    def test_the_declared_scope_matches_the_real_diff_of_the_reviewed_branch(self):
        def git(*command):
            done = subprocess.run(['git', *command], cwd=ROOT, capture_output=True, text=True, timeout=60)
            return done.stdout if done.returncode == 0 else ''
        committed = set(git('diff', '--name-only', c.BASELINE, 'HEAD').split())
        if not committed:
            self.skipTest('Baseline is not reachable from this checkout.')
        working = {line[3:] for line in git('status', '--porcelain', '--untracked-files=all').splitlines()}
        c.validate_changed(committed | working)


class PreservationComparison(unittest.TestCase):
    def test_the_declared_new_table_is_tolerated_and_nothing_else_is(self):
        c.unchanged(BEFORE, copy.deepcopy(AFTER))
        c.unchanged(BEFORE, copy.deepcopy(BEFORE))
        for key in ('rows', 'clinical', 'catalog', 'storage', 'static', 'unit_files',
                    'shared_configs', 'preserved_operations'):
            after = copy.deepcopy(AFTER); after[key] = 'modified'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.unchanged(BEFORE, after)

    def test_a_change_to_an_existing_table_is_never_excused_by_the_new_one(self):
        cases = {
            'existing column dropped': lambda s: s.__setitem__('schema', COLUMNS),
            'existing column altered': lambda s: s.__setitem__(
                'schema', [{'table_name': 'core_usage', 'column_name': 'id', 'ordinal_position': 2}] + COLUMNS),
            'constraint added elsewhere': lambda s: s['constraints'].append(
                ('core_usage', 'sneaky', 'c', '-', 'CHECK (true)')),
            'constraint removed': lambda s: s.__setitem__('constraints', s['constraints'][1:]),
            'index added elsewhere': lambda s: s['indexes'].append(('core_usage', 'sneaky', 'CREATE INDEX ...')),
            'existing table dropped': lambda s: s.__setitem__('tables', ['core_servicehealth', 'core_usage']),
            'second new table': lambda s: s.__setitem__('tables', s['tables'] + ['core_other']),
        }
        for name, mutate in cases.items():
            after = copy.deepcopy(AFTER); mutate(after)
            with self.subTest(case=name), self.assertRaises(RuntimeError):
                c.unchanged(BEFORE, after)

    def test_the_new_table_must_stay_empty_and_keep_its_declared_shape(self):
        for name, after in (
                ('rows written', dict(copy.deepcopy(AFTER), new_table_rows=1)),
                ('column missing', {**copy.deepcopy(AFTER), 'schema': BEFORE['schema'] + COLUMNS[:-1]}),
                ('column renamed', {**copy.deepcopy(AFTER),
                                    'schema': BEFORE['schema'] + [dict(COLUMNS[0], column_name='other')] + COLUMNS[1:]}),
                ('column reordered', {**copy.deepcopy(AFTER),
                                      'schema': BEFORE['schema'] + [dict(row, ordinal_position=row['ordinal_position'] + 1)
                                                                    for row in COLUMNS]})):
            with self.subTest(case=name), self.assertRaises(RuntimeError):
                c.unchanged(BEFORE, after)
        with self.assertRaises(RuntimeError):
            c.unchanged(dict(copy.deepcopy(BEFORE), new_table_rows=0), copy.deepcopy(AFTER))

    def test_an_unjudged_snapshot_component_refuses_rather_than_passing_silently(self):
        for shape in (dict(copy.deepcopy(AFTER), extra='unreviewed'),
                      {k: v for k, v in copy.deepcopy(AFTER).items() if k != 'catalog'}):
            with self.subTest(keys=sorted(shape)), self.assertRaises(RuntimeError):
                c.unchanged(BEFORE, shape)
                c.unchanged(shape, shape)

    def test_row_fingerprints_exclude_only_the_new_table_and_its_own_history_row(self):
        old = SimpleNamespace(PSQL=['psql'], tables=Mock(return_value=['core_usage', c.NEW_TABLE, 'django_migrations']))
        with patch.object(c.subprocess, 'check_output', return_value=b'{"a": 1}\n') as query:
            self.assertEqual(sorted(c.rows(old)), ['core_usage', 'django_migrations'])
        statements = [call.args[0][-1] for call in query.call_args_list]
        self.assertEqual(len(statements), 2)
        self.assertNotIn(c.NEW_TABLE, ' '.join(statements))
        self.assertIn("WHERE NOT (app='core' AND name='" + c.MIGRATION + "')",
                      [s for s in statements if 'django_migrations' in s][0])
        self.assertNotIn('WHERE', [s for s in statements if 'core_usage' in s][0])


class MigrationPhases(unittest.TestCase):
    def setUp(self):
        c.STATE.update(migration_checks=0, migration_performed=False)
        self.addCleanup(c.STATE.update, migration_checks=0, migration_performed=False)
        self.old = SimpleNamespace(PSQL=['psql'])
        self.plan = '[X] core.0016_user_session_version\n[X] core.' + c.PREVIOUS_MIGRATION
        # The reviewed migration genuinely exists under this checkout and genuinely does not
        # exist under an empty one, so the phase discriminator is exercised, never simulated.
        self.advanced = patch.object(c, 'ROOT', ROOT)
        empty = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, empty)
        self.before_advance = patch.object(c, 'ROOT', Path(empty))
        self.assertTrue((ROOT / c.MIGRATION_PATH).exists())
        self.assertFalse((Path(empty) / c.MIGRATION_PATH).exists())

    def test_before_the_advance_the_new_migration_must_be_absent_everywhere(self):
        with self.before_advance, patch.object(c.b, 'output', side_effect=[c.PREVIOUS_MIGRATION, '1', '0']):
            c.verify_migrations(self.old, self.plan)
        c.STATE.update(migration_checks=0)
        with self.advanced, patch.object(c.b, 'output') as output, self.assertRaises(RuntimeError):
            c.verify_migrations(self.old, self.plan)
        output.assert_not_called()

    def test_a_pending_or_unparsable_plan_refuses_before_any_query(self):
        for bad in (self.plan + '\n[ ] core.' + c.MIGRATION, self.plan.replace('[X] core.0016', '[ ] core.0016'),
                    self.plan + '\nunparsed', self.plan + '\n[X] core.' + c.PREVIOUS_MIGRATION):
            c.STATE.update(migration_checks=0)
            with self.subTest(plan=bad), self.before_advance, \
                 patch.object(c.b, 'output') as output, self.assertRaises(RuntimeError):
                c.verify_migrations(self.old, bad)
            output.assert_not_called()

    def test_a_moved_frontier_or_missing_history_refuses_before_the_advance(self):
        for values in (['0018_unexpected'], [c.PREVIOUS_MIGRATION, '0'], [c.PREVIOUS_MIGRATION, '2'],
                       [c.PREVIOUS_MIGRATION, '1', '1']):
            c.STATE.update(migration_checks=0)
            with self.subTest(values=values), self.before_advance, \
                 patch.object(c.b, 'output', side_effect=values), self.assertRaises(RuntimeError):
                c.verify_migrations(self.old, self.plan)

    def advance(self):
        c.STATE.update(migration_checks=1)
        return self.plan + '\n[ ] core.' + c.MIGRATION

    def test_the_second_call_applies_exactly_the_one_reviewed_migration(self):
        # validate_migration is deliberately NOT mocked: the real sha pin must accept the real bytes.
        with self.advanced, patch.object(c.b, 'run') as run, \
             patch.object(c.b, 'management', side_effect=lambda *x: ['management', *x]), \
             patch.object(c.b, 'verify_migration_plan') as plan_check, \
             patch.object(c.b, 'output', side_effect=[c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '0']):
            c.verify_migrations(self.old, self.advance())
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ['management', 'migrate', 'core', c.MIGRATION, '--noinput'])
        self.assertEqual([call.kwargs.get('applied') for call in plan_check.call_args_list], [False, True])
        self.assertTrue(c.STATE['migration_performed'])

    def test_the_apply_is_refused_when_its_own_preconditions_fail(self):
        for values, label in (([('0019_other')], 'frontier already moved'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '2', '1', '0'], 'duplicate history row'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '0', '0'], 'existing history lost'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '3'], 'new table not empty')):
            c.STATE.update(migration_checks=1, migration_performed=False)
            with self.subTest(case=label), self.advanced, patch.object(c.b, 'run'), \
                 patch.object(c.b, 'management', side_effect=lambda *x: ['management', *x]), \
                 patch.object(c.b, 'verify_migration_plan'), \
                 patch.object(c.b, 'output', side_effect=values), self.assertRaises(RuntimeError):
                c.verify_migrations(self.old, self.advance())

    def test_a_third_verification_or_a_repeat_apply_refuses_before_acting(self):
        """The plan here WOULD satisfy the apply, so only the phase guard itself can refuse it."""
        plan = self.plan + '\n[ ] core.' + c.MIGRATION
        for checks, performed, label in ((1, True, 'the migration already ran'),
                                         (2, False, 'a third verification')):
            c.STATE.update(migration_checks=checks, migration_performed=performed)
            with self.subTest(case=label), self.advanced, patch.object(c.b, 'run') as run, \
                 patch.object(c.b, 'verify_migration_plan'), patch.object(c.b, 'validate_migration'), \
                 patch.object(c.b, 'management', side_effect=lambda *x: ['management', *x]), \
                 patch.object(c.b, 'output') as output, self.assertRaises(RuntimeError):
                c.verify_migrations(self.old, plan)
            run.assert_not_called()
            output.assert_not_called()


class ReceiptHonesty(unittest.TestCase):
    def setUp(self):
        self.addCleanup(c.STATE.update, migration_performed=False)

    def base(self):
        return {'baseline': c.BASELINE, 'target': 'a' * 40, 'migration_performed': False,
                'existing_schema_indexes_constraints_catalog_unchanged': True}

    def test_a_receipt_reports_whether_the_migration_actually_ran(self):
        c.STATE.update(migration_performed=False)
        self.assertIs(c.receipt(self.base())['migration_performed'], False)
        c.STATE.update(migration_performed=True)
        written = c.receipt(self.base())
        self.assertIs(written['migration_performed'], True)
        self.assertEqual(written['declared_migration'], c.MIGRATION)
        self.assertEqual(written['declared_migration_sha256'], c.MIGRATION_SHA256)
        self.assertEqual(written['activation_adapter'], c.SELF)
        self.assertEqual(written['pinned_driver'], c.DRIVER)
        self.assertIs(written['fresh_backup_or_restore_performed'], False)

    def test_the_inherited_unqualified_schema_claim_never_survives_into_a_receipt(self):
        written = c.receipt(self.base())
        self.assertNotIn('existing_schema_indexes_constraints_catalog_unchanged', written)
        self.assertIs(written['existing_schema_indexes_constraints_catalog_unchanged_apart_from_declared_new_table'],
                      True)
        self.assertIn(c.NEW_TABLE, written['declared_schema_delta'])
        self.assertIn("'migration_performed': False", inspect.getsource(c.t.main))

    def test_a_document_that_is_not_an_activation_receipt_is_left_alone(self):
        self.assertEqual(c.receipt({'target': 'a' * 40}), {'target': 'a' * 40})


class InheritedActPreserved(unittest.TestCase):
    def test_the_act_still_gates_on_citation_declaration_and_co_tenants(self):
        source = inspect.getsource(c.t.main)
        self.assertIn('scripts/check-citation.sh', source)
        self.assertIn('scripts/check-cotenants.sh', source)
        self.assertIn("declaration.read_bytes() == b.blob(args.target, DECL) == b.blob(commit, DECL)", source)
        self.assertLess(source.index("word.systemd('stop', helper)"),
                        source.index("b.run(['git', 'merge', '--ff-only'"))
        self.assertLess(source.index("b.run(['git', 'merge', '--ff-only'"), source.index('collect_static(stage)'))
        self.assertIn("identity.verify_live(args.target, storage)", source)
        self.assertIn("worker_after['kernel_start_utc'] > worker_before['kernel_start_utc']", source)

    def test_both_public_assets_travel_through_one_retained_transition(self):
        self.assertEqual(c.t.STATIC_INPUTS, {'app.css', 'app.js', 'django_otp/css/login.css',
                                             'otp_totp/css/qrcode.css', 'otp_totp/js/qrcode.js'})
        self.assertIn('set(inputs) == STATIC_INPUTS', inspect.getsource(c.t.validate_staged_static))
        self.assertIn("{name + suffix for name in ('app.css', 'app.js')", inspect.getsource(c.t.static_delta))
        act = inspect.getsource(c.t.main)
        self.assertEqual(act.count('collect_static(stage)'), 1)
        self.assertIn('retain_static', act)
        self.assertIn('old_immutable_assets_retained', act)

    def test_the_source_gate_also_authenticates_the_pinned_driver(self):
        with patch.object(c, '_inherited_verify_source', return_value={'changed'}), \
             patch.object(c.b, 'blob', side_effect=['different bytes', 'different bytes']), \
             self.assertRaises(RuntimeError):
            c.verify_source('a' * 40)
        with patch.object(c, '_inherited_verify_source', return_value={'changed'}) as inherited, \
             patch.object(c.b, 'blob', return_value=(ROOT / c.DRIVER).read_bytes()):
            self.assertEqual(c.verify_source('a' * 40), {'changed'})
        inherited.assert_called_once_with('a' * 40)


if __name__ == '__main__':
    unittest.main()
