"""The service-date activator's static guards, proved against the real migration, models and repository."""
import ast
import importlib.util
from pathlib import Path
import subprocess
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
        changed |= set(subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--others', '--exclude-standard',
                                                '--', 'scripts', 'rebuild/ops', 'docs'], text=True).split())
        self.assertEqual(sorted(changed - activator.ALLOWED), [])

    def test_the_activation_declares_its_own_parts(self):
        activator = load_activator()
        for path in (activator.MIGRATION_PATH, activator.DECL, activator.SELF,
                     'rebuild/ops/test_service_date_activation.py', 'rebuild/core/coding.py'):
            self.assertIn(path, activator.ALLOWED)


if __name__ == '__main__':
    unittest.main()
