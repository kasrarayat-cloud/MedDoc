"""Provider-free guards for the combined admin-console and doctor/form private activation.

The act adds ONE table and moves BOTH public assets. Every guard here exists to make a
difference outside that declared delta refuse, and to stop a receipt describing an act
that did not happen.
"""
import copy
import inspect
import json
import os
import shutil
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
        return c.RUNTIME_ALLOWED | {c.DECL, c.RESUME_DECL, c.SCREENSHOTS + '01-overview.jpg',
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
        # A resume baseline is post-migration and legitimate; losing the table never is.
        c.unchanged(copy.deepcopy(AFTER), copy.deepcopy(AFTER))
        with self.assertRaises(RuntimeError):
            c.unchanged(copy.deepcopy(AFTER), dict(copy.deepcopy(AFTER), new_table_rows=None))

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


class StaticAuthentication(unittest.TestCase):
    """The inherited allowlist is single-use; these pin what replaced it."""

    HASHED = 'app.aaaaaaaaaaaa.css'
    OLDER = 'app.bbbbbbbbbbbb.css'
    HISTORIC = 'app.cccccccccccc.css'

    def build(self):
        base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base, True)
        root = base / 'staticfiles'
        root.mkdir(mode=0o755)
        source = base / 'src'
        source.mkdir(mode=0o755)
        (source / 'app.css').write_bytes(b'body{}')
        payload = {'app.css': b'body{}', self.HASHED: b'body{}', self.HASHED + '.gz': b'gz',
                   self.OLDER: b'older', self.OLDER + '.gz': b'oldgz', self.HISTORIC: b'historic'}
        for name, data in payload.items():
            (root / name).write_bytes(data); (root / name).chmod(0o644)
        (root / 'staticfiles.json').write_bytes(json.dumps({'paths': {'app.css': self.HASHED}}).encode())
        (root / 'staticfiles.json').chmod(0o644)
        digest = {n: c.sha(d) for n, d in payload.items()}
        retained = {n: {'kind': 'file', 'mode': 0o644, 'size': len(payload[n]), 'sha256': digest[n]}
                    for n in (self.OLDER, self.OLDER + '.gz')}
        historic = {self.HISTORIC: {'mode': 0o644, 'size': len(payload[self.HISTORIC]),
                                    'sha256': digest[self.HISTORIC]}}
        identity = SimpleNamespace(static_sources=lambda: {'app.css': source / 'app.css'})
        return base, root, identity, retained, historic

    def run_inventory(self, base, identity, retained, historic, **over):
        with patch.object(c, 'APP', base), patch.object(c.t, 'STATIC_INPUTS', {'app.css'}), \
             patch.dict(c.LOADED, {'old': SimpleNamespace(RETAINED_STATIC=dict(historic))}, clear=False), \
             patch.object(c, 'recorded_static', return_value=dict(retained, **over.pop('extra', {}))):
            return c.authenticated_static_inventory(identity, None)

    def test_a_population_every_object_of_which_is_accounted_for_is_accepted(self):
        base, root, identity, retained, historic = self.build()
        rows = self.run_inventory(base, identity, retained, historic)
        self.assertEqual(set(rows), {'.', 'staticfiles.json', 'app.css', self.HASHED,
                                     self.HASHED + '.gz', self.OLDER, self.OLDER + '.gz', self.HISTORIC})

    def test_a_directory_no_manifest_entry_explains_refuses(self):
        base, root, identity, retained, historic = self.build()
        (root / 'sub').mkdir(mode=0o755)
        with self.assertRaises(RuntimeError):
            self.run_inventory(base, identity, retained, historic)

    def test_an_object_no_recorded_transition_installed_refuses(self):
        base, root, identity, retained, historic = self.build()
        (root / 'app.dddddddddddd.css').write_bytes(b'stranger')
        (root / 'app.dddddddddddd.css').chmod(0o644)
        with self.assertRaises(RuntimeError) as caught:
            self.run_inventory(base, identity, retained, historic)
        self.assertIn('no recorded transition installed', str(caught.exception))

    def test_a_retained_object_whose_bytes_or_mode_drifted_refuses(self):
        for mutate, label in (
                (lambda root: (root / self.OLDER).write_bytes(b'tampered'), 'bytes changed'),
                (lambda root: (root / self.OLDER).chmod(0o600), 'mode changed')):
            base, root, identity, retained, historic = self.build()
            mutate(root)
            with self.subTest(case=label), self.assertRaises(RuntimeError):
                self.run_inventory(base, identity, retained, historic)

    def test_a_recorded_object_that_is_not_a_compiled_form_of_an_input_refuses(self):
        base, root, identity, retained, historic = self.build()
        (root / 'unrelated.txt').write_bytes(b'x'); (root / 'unrelated.txt').chmod(0o644)
        extra = {'unrelated.txt': {'kind': 'file', 'mode': 0o644, 'size': 1, 'sha256': c.sha(b'x')}}
        with self.assertRaises(RuntimeError) as caught:
            self.run_inventory(base, identity, retained, historic, extra=extra)
        self.assertIn('previously compiled form', str(caught.exception))

    def test_the_inherited_constant_keeps_full_authority_over_what_it_names(self):
        base, root, identity, retained, historic = self.build()
        (root / self.HISTORIC).write_bytes(b'rewritten-history')
        with self.assertRaises(RuntimeError) as caught:
            self.run_inventory(base, identity, retained, historic)
        self.assertIn('historically retained', str(caught.exception))

    def test_a_manifest_that_does_not_match_the_reviewed_inputs_refuses(self):
        """Isolated: the manifest is internally valid, so ONLY the reviewed-input set can refuse."""
        base, root, identity, retained, historic = self.build()
        other, hashed = 'other.css', 'other.aaaaaaaaaaaa.css'
        (base / 'src' / other).write_bytes(b'x')
        for name in (other, hashed):
            (root / name).write_bytes(b'x'); (root / name).chmod(0o644)
        (root / 'staticfiles.json').write_bytes(
            json.dumps({'paths': {'app.css': self.HASHED, other: hashed}}).encode())
        (root / 'staticfiles.json').chmod(0o644)
        identity = SimpleNamespace(static_sources=lambda: {'app.css': base / 'src' / 'app.css',
                                                           other: base / 'src' / other})
        with self.assertRaises(RuntimeError) as caught:
            self.run_inventory(base, identity, retained, historic)
        self.assertIn('reviewed application', str(caught.exception))

    def test_a_wrongly_permissioned_current_asset_refuses(self):
        """Isolated: this asset is in the manifest set, so no retained comparison can catch it."""
        base, root, identity, retained, historic = self.build()
        (root / self.HASHED).chmod(0o600)
        with self.assertRaises(RuntimeError) as caught:
            self.run_inventory(base, identity, retained, historic)
        self.assertIn('operator-owned, regular, unlinked and correctly moded', str(caught.exception))

    def test_a_collected_source_that_differs_from_the_application_refuses(self):
        base, root, identity, retained, historic = self.build()
        (root / 'app.css').write_bytes(b'body{different}')
        with self.assertRaises(RuntimeError):
            self.run_inventory(base, identity, retained, historic)

    def test_it_does_not_delegate_to_the_entry_points_reader(self):
        """Non-vacuity pin: the caller compares the two, so delegating makes that a tautology."""
        base, root, identity, retained, historic = self.build()
        with patch.object(c.t, 'static_inventory') as peer:
            self.run_inventory(base, identity, retained, historic)
        peer.assert_not_called()
        self.assertIsNot(c.authenticated_static_inventory, c.t.static_inventory)
        self.assertNotIn('t.static_inventory', inspect.getsource(c.authenticated_static_inventory))

    def test_the_prior_receipt_is_pinned_by_content(self):
        source = inspect.getsource(c.recorded_static)
        self.assertIn('PRIOR_TRANSITION_SHA256', source)
        self.assertIn("receipt.get('complete') is True", source)
        with patch.object(c.Path, 'read_bytes', return_value=b'{"complete": true}'), \
             self.assertRaises(RuntimeError):
            c.recorded_static()

    def test_the_loader_replaces_that_reader_on_the_qualified_helper_and_nothing_else(self):
        self.assertIs(c.a.load, c.load)
        self.assertIs(c.b.load, c.load)
        old = SimpleNamespace(static_inventory='original')
        other = SimpleNamespace(static_inventory='original')
        with patch.object(c, '_inherited_load', side_effect=[old, other]):
            self.assertIs(c.load('old', 'scripts/activate-word-export.py', 'a' * 40), old)
            self.assertIs(c.load('word', 'scripts/activate-word-beta.py', 'a' * 40), other)
        self.assertIs(old.static_inventory, c.authenticated_static_inventory)
        self.assertEqual(other.static_inventory, 'original')
        self.assertIs(c.LOADED['old'], old)


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
             patch.object(c.b, 'output', side_effect=[c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '0',
                                                      '1', ','.join(sorted(c.NEW_PERMISSIONS))]):
            c.verify_migrations(self.old, self.advance())
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ['management', 'migrate', 'core', c.MIGRATION, '--noinput'])
        self.assertEqual([call.kwargs.get('applied') for call in plan_check.call_args_list], [False, True])
        self.assertTrue(c.STATE['migration_performed'])

    def test_the_apply_is_refused_when_its_own_preconditions_fail(self):
        for values, label in (([('0019_other')], 'frontier already moved'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '2', '1', '0'], 'duplicate history row'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '0', '0'], 'existing history lost'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '3'], 'new table not empty'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '0', '0',
                                ','.join(sorted(c.NEW_PERMISSIONS))], 'no ContentType written'),
                              ([c.PREVIOUS_MIGRATION, 'applied-plan', '1', '1', '0', '1',
                                'add_servicehealth'], 'permissions incomplete')):
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


class DeclaredBookkeeping(unittest.TestCase):
    """A CreateModel migration also writes a ContentType and four permissions."""

    def test_the_row_universes_are_symmetric_so_one_filter_serves_both(self):
        old = SimpleNamespace(PSQL=['psql'], tables=Mock(return_value=[
            'auth_permission', 'core_usage', c.NEW_TABLE, 'django_content_type', 'django_migrations']))
        with patch.object(c.subprocess, 'check_output', return_value=b'{"a": 1}\n') as query:
            self.assertEqual(sorted(c.rows(old)),
                             ['auth_permission', 'core_usage', 'django_content_type', 'django_migrations'])
        statements = {call.args[0][-1].split('FROM "')[1].split('"')[0]: call.args[0][-1]
                      for call in query.call_args_list}
        self.assertNotIn(c.NEW_TABLE, ' '.join(statements.values()))
        self.assertIn("name='" + c.MIGRATION + "'", statements['django_migrations'])
        self.assertIn("model='" + c.NEW_MODEL + "'", statements['django_content_type'])
        self.assertIn('content_type_id NOT IN', statements['auth_permission'])
        self.assertNotIn('WHERE', statements['core_usage'])

    def test_every_bookkeeping_filter_names_the_new_model_and_nothing_wider(self):
        for table, clause in c.BOOKKEEPING.items():
            with self.subTest(table=table):
                self.assertIn(c.NEW_MODEL if table != 'django_migrations' else c.MIGRATION, clause)
                self.assertTrue(clause.startswith('WHERE'))
        self.assertEqual(set(c.BOOKKEEPING), {'django_migrations', 'django_content_type', 'auth_permission'})
        self.assertEqual(sorted(c.NEW_PERMISSIONS),
                         sorted('%s_%s' % (verb, c.NEW_MODEL) for verb in ('add', 'change', 'delete', 'view')))

    def test_the_added_bookkeeping_must_be_exactly_the_models_own(self):
        good = ['1', ','.join(sorted(c.NEW_PERMISSIONS))]
        with patch.object(c.b, 'output', side_effect=list(good)):
            c.check_new_bookkeeping(SimpleNamespace(PSQL=['psql']))
        for values, label in ((['0', good[1]], 'no ContentType'), (['2', good[1]], 'two ContentTypes'),
                              (['1', 'add_servicehealth'], 'a permission missing'),
                              (['1', good[1] + ',extra_servicehealth'], 'an extra permission')):
            with self.subTest(case=label), patch.object(c.b, 'output', side_effect=values), \
                 self.assertRaises(RuntimeError):
                c.check_new_bookkeeping(SimpleNamespace(PSQL=['psql']))

    def test_the_apply_asserts_the_bookkeeping_before_it_is_believed(self):
        self.assertIn('check_new_bookkeeping(old)', inspect.getsource(c.verify_migrations))
        self.assertIn('check_new_bookkeeping(old)', inspect.getsource(c.verify_resume_migrations))


class SavedSnapshotComparison(unittest.TestCase):
    def saved(self, snapshot):
        return json.loads(json.dumps(snapshot))

    def test_a_json_reloaded_baseline_compares_with_a_live_one(self):
        c.unchanged_saved_snapshot(self.saved(BEFORE), copy.deepcopy(AFTER))
        c.unchanged(BEFORE, copy.deepcopy(AFTER))

    def test_normalising_the_wire_shape_does_not_hide_a_real_change(self):
        for key in ('constraints', 'indexes'):
            after = copy.deepcopy(AFTER)
            after[key] = [tuple(['core_usage', 'renamed'] + list(r)[2:]) for r in BEFORE[key]] + after[key][1:]
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.unchanged_saved_snapshot(self.saved(BEFORE), after)
        after = copy.deepcopy(AFTER); after['clinical'] = {'finalized': 17, 'encounters': 28}
        with self.assertRaises(RuntimeError):
            c.unchanged_saved_snapshot(self.saved(BEFORE), after)

    def test_the_normaliser_preserves_order_inside_a_row(self):
        """It fixes tuple-vs-list and NOTHING else; two rows with the same fields transposed differ."""
        self.assertEqual(c.wire(('a', 'b', 'c')), ['a', 'b', 'c'])
        self.assertNotEqual(c.wire(('a', 'b')), c.wire(('b', 'a')))
        self.assertEqual(c.wire({'k': ('x', ('y', 'z'))}), {'k': ['x', ['y', 'z']]})
        self.assertEqual(c.wire(('a', 'b')), c.wire(['a', 'b']))
        after = copy.deepcopy(AFTER)
        row = list(BEFORE['constraints'][0])
        after['constraints'] = [tuple([row[1], row[0]] + row[2:])] + after['constraints'][1:]
        with self.assertRaises(RuntimeError):
            c.unchanged_saved_snapshot(self.saved(BEFORE), after)

    def test_reordering_is_a_difference_and_is_never_sorted_away(self):
        """The normaliser fixes tuple-vs-list ONLY. Sorting would let a reshuffle pass."""
        for key in ('constraints', 'indexes', 'schema'):
            after = copy.deepcopy(AFTER)
            kept = [r for r in after[key] if (r['table_name'] if key == 'schema' else r[0]) != c.NEW_TABLE]
            new_rows = [r for r in after[key] if (r['table_name'] if key == 'schema' else r[0]) == c.NEW_TABLE]
            if len(kept) < 2:
                kept = kept + kept
            after[key] = list(reversed(kept)) + new_rows
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.unchanged_saved_snapshot(self.saved(BEFORE), after)

    def test_both_comparators_are_the_same_tolerance(self):
        self.assertIn('compare(before, after', inspect.getsource(c.unchanged))
        self.assertIn('compare(before, after', inspect.getsource(c.unchanged_saved_snapshot))

    def test_a_resume_baseline_is_accepted_and_a_disappearance_is_not(self):
        resumed = copy.deepcopy(AFTER)
        c.unchanged(resumed, copy.deepcopy(AFTER))
        with self.assertRaises(RuntimeError):
            c.unchanged(resumed, copy.deepcopy(BEFORE))


class ForwardRepair(unittest.TestCase):
    def failed(self, **over):
        base = {'complete': False, 'target': c.FAILED_TARGET, 'baseline': c.BASELINE,
                'served_before': c.RUNNING_RELEASE, 'stage': 'advance_stopped_source_ff_only',
                'failure_kind': 'RuntimeError', 'failure_services_stopped': True,
                'provider_calls': 0, 'migration_performed': True, 'declared_migration': c.MIGRATION,
                'state_directory': str(c.EVIDENCE / ('activation-state-' + c.FAILED_TARGET[:12]))}
        base.update(over)
        return json.dumps(base).encode()

    def test_only_the_exact_pinned_failure_is_resumable(self):
        data = self.failed()
        with patch.object(c, 'FAILED_RECEIPT_SHA256', c.sha(data)):
            c.validate_failed_receipt(data)
            for over, label in (({'complete': True}, 'a completed act'),
                                ({'stage': 'collect_and_install_source_bound_public_assets'}, 'a later stage'),
                                ({'migration_performed': False}, 'no migration applied'),
                                ({'provider_calls': 1}, 'a provider call'),
                                ({'failure_services_stopped': False}, 'services left running'),
                                ({'target': 'b' * 40}, 'another target'),
                                ({'static_transition': {}}, 'assets already moved'),
                                ({'state_directory': '/tmp/elsewhere'}, 'a moved state directory')):
                bad = self.failed(**over)
                with self.subTest(case=label), patch.object(c, 'FAILED_RECEIPT_SHA256', c.sha(bad)), \
                     self.assertRaises(RuntimeError):
                    c.validate_failed_receipt(bad)
        with self.assertRaises(RuntimeError):
            c.validate_failed_receipt(data)          # the content pin itself

    def resume_source(self, changed, head=None, origin=None, dirty=''):
        """Drive verify_resume_source for real, with only the repository answers stubbed.

        The worktree layout is built in a temporary directory rather than assumed, so this
        runs identically on a developer host and on a plain CI checkout.
        """
        target = 'c' * 40
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        source = root / '.worktrees' / 'repair'
        (source / 'scripts').mkdir(parents=True)
        (source / c.DRIVER).write_bytes((ROOT / c.DRIVER).read_bytes())
        answers = {('rev-parse', 'HEAD'): head or c.FAILED_TARGET,
                   ('rev-parse', 'origin/main'): origin or target,
                   ('branch', '--show-current'): 'main',
                   ('status', '--porcelain', '--untracked-files=no'): dirty,
                   ('diff', '--name-only', c.FAILED_TARGET, target): '\n'.join(sorted(changed))}
        blobs = {c.SELF: Path(c.__file__).read_bytes(), c.DRIVER: (ROOT / c.DRIVER).read_bytes()}
        with patch.object(c, 'ROOT', root), patch.object(c, 'SOURCE', source.resolve()), \
             patch.object(c.b, 'git', side_effect=lambda *a: answers[a]), \
             patch.object(c.b, 'output', return_value=''), patch.object(c.b, 'run'), \
             patch.object(c.b, 'blob', side_effect=lambda _sha, path: blobs[path]):
            return c.verify_resume_source(target)

    def test_the_repair_refuses_to_run_outside_a_worktree(self):
        """Positive control for the harness above: the shared tree itself is not a repair tree."""
        with patch.object(c, 'SOURCE', c.ROOT), self.assertRaises(RuntimeError):
            self.resume_source_in_place()

    def resume_source_in_place(self):
        with patch.object(c.b, 'git', return_value=''), patch.object(c.b, 'output', return_value=''), \
             patch.object(c.b, 'run'):
            return c.verify_resume_source('c' * 40)

    def test_the_repair_may_change_only_three_paths(self):
        """Behavioural, not a source grep: a disabling prefix leaves the text intact."""
        self.assertEqual(c.RESUME_PATHS, {c.SELF, c.OPS_TEST, c.RESUME_DECL})
        self.assertEqual(self.resume_source(c.RESUME_PATHS), c.RESUME_PATHS)
        for bad, label in ((c.RESUME_PATHS | {'rebuild/core/views.py'}, 'an application file'),
                           (c.RESUME_PATHS | {'rebuild/core/migrations/0019_x.py'}, 'another migration'),
                           (c.RESUME_PATHS | {'rebuild/static/app.css'}, 'a public asset'),
                           (c.RESUME_PATHS - {c.RESUME_DECL}, 'no repair declaration'),
                           (c.RESUME_PATHS - {c.SELF}, 'no activator change')):
            with self.subTest(case=label), self.assertRaises(RuntimeError):
                self.resume_source(bad)

    def test_the_repair_refuses_a_moved_shared_tree(self):
        for over, label in (({'head': 'd' * 40}, 'shared main no longer at the failed target'),
                            ({'origin': 'e' * 40}, 'origin/main is not the repair target'),
                            ({'dirty': ' M rebuild/core/views.py'}, 'shared tree dirty')):
            with self.subTest(case=label), self.assertRaises(RuntimeError):
                self.resume_source(c.RESUME_PATHS, **over)

    def test_the_repair_never_replays_the_migration_and_keeps_every_gate(self):
        source = inspect.getsource(c.resume_failed)
        self.assertNotIn("management('migrate'", source)
        self.assertIn('verify_resume_migrations', source)
        self.assertIn('scripts/check-citation.sh', source)
        self.assertIn('scripts/check-cotenants.sh', source)
        self.assertIn("declaration == SOURCE / RESUME_DECL", source)
        self.assertIn('unchanged_saved_snapshot', source)
        self.assertIn("len(old.tables()) == 36", source)
        self.assertLess(source.index('if not args.execute'), source.index('create_static_stage'))
        self.assertLess(source.index('create_static_stage'), source.index('replace_environment'))
        self.assertLess(source.index('replace_environment'), source.index("systemd('start'"))

    def test_the_resume_refuses_a_still_running_original_and_a_used_result_path(self):
        source = inspect.getsource(c.resume_failed)
        self.assertIn('os.kill(lock_value', source)
        self.assertIn('Original activation process is still present', source)
        self.assertIn('not any(p.exists() or p.is_symlink() for p in (result_path, state))', source)
        self.assertIn("lock_value.get('target') == FAILED_TARGET", source)


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
