"""The service-date activator's static guards, proved against the real migration, models and repository."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_activator():
    spec = importlib.util.spec_from_file_location('activate_service_date', ROOT / 'scripts/activate-service-date.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationValidation(unittest.TestCase):
    def setUp(self):
        self.activator = load_activator()
        self.source = (ROOT / self.activator.MIGRATION_PATH).read_bytes()

    def test_the_real_migration_is_exactly_the_reviewed_one(self):
        self.activator.validate_migration(self.source)

    def test_any_other_bytes_are_refused_even_a_comment(self):
        for mutated in (self.source + b'\n# reviewed?\n',
                        self.source.replace(b"name='service_date'", b"name='service_day'", 1),
                        self.source.replace(b'migrations.AddField(', b'migrations.RunSQL("SELECT 1"),\n        migrations.AddField(', 1)):
            with self.subTest(size=len(mutated)), self.assertRaises(RuntimeError):
                self.activator.validate_migration(mutated)

    def repin(self, mutated):
        """Check the structural guards independently of the byte pin, which would otherwise refuse first."""
        activator = load_activator()
        activator.MIGRATION_SHA256 = activator.sha(mutated)
        return activator

    def test_the_operation_list_is_checked_independently_of_the_pin(self):
        mutated = self.source.replace(b"migrations.RunPython(adopt_recorded_date, keep_the_dates)",
                                      b"migrations.RunPython(keep_the_dates, keep_the_dates)")
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.repin(mutated).validate_migration(mutated)

    def test_dropping_the_backfill_entirely_is_refused_independently_of_the_pin(self):
        """A migration that adds the column and never fills it would leave every encounter without a date of service."""
        mutated = self.source.replace(b"        migrations.RunPython(adopt_recorded_date, keep_the_dates),\n", b'')
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.repin(mutated).validate_migration(mutated)

    def test_a_dependency_on_another_migration_is_refused_independently_of_the_pin(self):
        mutated = self.source.replace(b'0013_recording_charge_limit', b'0012_billing_policy')
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.repin(mutated).validate_migration(mutated)


class ColumnPin(unittest.TestCase):
    def setUp(self):
        self.activator = load_activator()
        self.models = (ROOT / 'rebuild/core/models.py').read_text()

    def test_the_pinned_column_matches_the_model_field(self):
        self.assertIn('service_date=models.DateField()', self.models.replace(' ', ''))
        self.assertEqual(self.activator.NEW_COLUMN['is_nullable'], 'NO')
        self.assertIsNone(self.activator.NEW_COLUMN['column_default'])
        self.assertEqual(self.activator.NEW_COLUMN['data_type'], 'date')

    def test_schema_check_accepts_only_the_new_column(self):
        a = self.activator
        before = [{'table_name': 'core_job', 'column_name': 'id', 'data_type': 'uuid'}]
        after = before + [dict(a.NEW_COLUMN)]
        a.check_schema(before, after)
        for bad in (before + [dict(a.NEW_COLUMN, is_nullable='YES')],
                    before + [dict(a.NEW_COLUMN, column_default="'2026-01-01'::date")],
                    after + [{'table_name': 'core_job', 'column_name': 'x', 'data_type': 'text'}]):
            with self.subTest(rows=len(bad)), self.assertRaises(RuntimeError):
                a.check_schema(before, bad)

    def test_the_new_column_is_dropped_from_the_comparable_fingerprint_of_its_own_table_only(self):
        a = self.activator
        self.assertEqual(a.NEW_COLUMN['table_name'], 'core_encounter')
        source = (ROOT / 'scripts/activate-service-date.py').read_text()
        self.assertIn("if comparable and table == NEW_COLUMN['table_name']", source)
        self.assertIn("to_jsonb(t) - '", source)


class OneRuleForBothReaders(unittest.TestCase):
    """The activation ships a selection rule; if a second reader grows its own copy, this catches it."""

    def test_no_reader_selects_a_release_by_todays_date(self):
        coding = (ROOT / 'rebuild/core/coding.py').read_text()
        views = (ROOT / 'rebuild/core/views.py').read_text()
        self.assertIn('effective_from__lte=encounter.service_date', coding)
        self.assertIn('effective_until__gte=encounter.service_date', coding)
        for source, name in ((coding, 'coding.py'), (views, 'views.py')):
            self.assertNotIn('effective_until__gte=timezone.localdate()', source, name)
            self.assertNotIn('effective_until<timezone.localdate()', source.replace(' ', ''), name)
        self.assertEqual(views.count('applicable_releases'), 2)  # the import and its single use

    def test_the_effective_period_is_expressed_once(self):
        tree = ast.parse((ROOT / 'rebuild/core/coding.py').read_text())
        uses = [node for node in ast.walk(tree) if isinstance(node, ast.keyword) and node.arg in
                ('effective_from__lte', 'effective_until__gte')]
        self.assertEqual(len(uses), 2, 'The effective-period filter must exist exactly once, as one pair of bounds.')


# This activation's allow-list describes the tree it ships, which is only meaningful while 0014 is the newest
# migration. Once later work lands, pin the range to the merge that activated this one, as the recording-limit
# test does, rather than comparing against a moving HEAD.
class AllowedPaths(unittest.TestCase):
    def newest_migration(self):
        return sorted(p.name for p in (ROOT / 'rebuild/core/migrations').glob('0*.py'))[-1]

    def test_every_changed_path_since_the_running_release_is_declared(self):
        activator = load_activator()
        if not self.newest_migration().startswith('0014_'):
            self.skipTest('A later migration exists; pin this activation to the merge that shipped it.')
        if subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', activator.BASELINE + '^{commit}'], capture_output=True).returncode:
            self.skipTest('Running-release commit is not available in this checkout (shallow clone).')
        changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', activator.BASELINE, 'HEAD'], text=True).split())
        # Scoped to the directories this activation adds files to. A bare 'docs' also sweeps up
        # docs/preflight-reports/, which is untracked by design and which the act's own
        # retained_reports() sanctions — two guards in one act must not disagree about the same files.
        changed |= set(subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--others', '--exclude-standard',
                                                '--', 'scripts', 'rebuild/ops', 'rebuild/core',
                                                'docs/foundation/mutations', 'docs/rebuild'], text=True).split())
        self.assertEqual(sorted(changed - activator.ALLOWED), [])

    def test_the_activation_declares_its_own_parts(self):
        """Its own migration, declaration, activator and this file. The rest of the range is whatever it ships."""
        activator = load_activator()
        for path in (activator.MIGRATION_PATH, activator.DECL, activator.SELF,
                     'rebuild/ops/test_service_date_activation.py'):
            self.assertIn(path, activator.ALLOWED)

    def test_the_declaration_it_names_exists(self):
        activator = load_activator()
        self.assertTrue((ROOT / activator.DECL).is_file(), activator.DECL)


if __name__ == '__main__':
    unittest.main()


class TheNarrowRoleWrapperAdmitsTheImportAndNothingElse(unittest.TestCase):
    """The FY2027 import runs through with_db_role.py so it is not the one write using the superuser."""

    def run_wrapper(self, command):
        import json as json_module
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credentials = root / 'roles.json'
            credentials.write_text(json_module.dumps({'database': 'quillmd_fresh', 'roles': {
                'migrator': {'name': 'synthetic_migrator', 'password': 'synthetic'},
                'backup': {'name': 'synthetic_backup', 'password': 'synthetic'}}}))
            credentials.chmod(0o600)
            source = root / 'source'
            source.mkdir()
            (source / 'manage.py').write_text('import sys\nprint("REACHED", *sys.argv[1:])\n')
            return subprocess.run([sys.executable, str(ROOT / 'rebuild/ops/with_db_role.py'),
                                   '--credentials', str(credentials), '--source', str(source),
                                   '--role', 'migrator', '--', *command],
                                  capture_output=True, text=True, timeout=60, env=dict(os.environ))

    def test_the_verified_terminology_import_is_admitted(self):
        result = self.run_wrapper(['import_terminology', '--system', 'ICD-10-CM'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REACHED import_terminology --system ICD-10-CM', result.stdout)

    def test_the_migration_commands_still_work(self):
        self.assertIn('REACHED migrate', self.run_wrapper(['migrate', 'core']).stdout)

    def test_a_worker_or_provider_command_is_still_refused(self):
        for command in (['worker'], ['shell'], ['seed_private'], ['verify_live'], ['runserver']):
            with self.subTest(command=command[0]):
                result = self.run_wrapper(command)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('REACHED', result.stdout)

    def test_the_allow_list_is_exactly_these_four(self):
        source = (ROOT / 'rebuild/ops/with_db_role.py').read_text()
        self.assertIn("('migrate', 'showmigrations', 'check', 'import_terminology')", source)


class TheTreeHeadAndTheRunningReleaseAreDifferentFacts(unittest.TestCase):
    """The refused act advanced main and died before rewriting the release line, so the two diverged."""

    def setUp(self):
        self.activator = load_activator()
        self.source = (ROOT / 'scripts/activate-service-date.py').read_text()

    def test_the_two_are_separate_constants(self):
        self.assertNotEqual(self.activator.BASELINE, self.activator.RUNNING_RELEASE)
        self.assertEqual(self.activator.BASELINE, '475a59259203b04072e35cb9270f39a3b0005906')
        self.assertEqual(self.activator.RUNNING_RELEASE, '5f673a3b2cc5c99d68f08f34fba43b4883403583')

    def test_the_release_line_it_replaces_is_the_running_one_not_the_tree_head(self):
        self.assertIn("old_line = ('QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE)", self.source)
        self.assertNotIn("old_line = ('QUILLMD_RELEASE_SHA=' + BASELINE)", self.source)

    def test_both_surfaces_must_agree_about_being_up(self):
        """The first version of this check was `any(is None) or all(is not None)` — true for every input."""
        def agree(health):
            return all(a is None for a in health) or all(a is not None for a in health)
        self.assertTrue(agree([None, None]))
        self.assertTrue(agree([{'release': 'x'}, {'release': 'x'}]))
        self.assertFalse(agree([None, {'release': 'x'}]), 'one surface up and one down must be refused')
        self.assertIn('all(answer is None for answer in health) or all(answer is not None for answer in health)',
                      self.source)

    def test_a_service_answering_an_unexplained_release_is_refused(self):
        def acceptable(answer, running):
            return answer is None or (answer.get('release') == running and answer.get('data_mode') == 'synthetic-only')
        running = self.activator.RUNNING_RELEASE
        self.assertTrue(acceptable(None, running))
        self.assertTrue(acceptable({'release': running, 'data_mode': 'synthetic-only'}, running))
        self.assertFalse(acceptable({'release': 'something-else', 'data_mode': 'synthetic-only'}, running))
        self.assertFalse(acceptable({'release': running, 'data_mode': 'real'}, running))
