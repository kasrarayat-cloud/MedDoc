"""The recording-limit activator's static guards, proved against the real migration, models and repository."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_activator():
    spec = importlib.util.spec_from_file_location('activate_recording_limit', ROOT / 'scripts/activate-recording-limit.py')
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
        for mutated in (self.source + b'\n# reviewed?\n', self.source.replace(b"'absorbed_over_limit'", b"'absorbed_over_limitX'", 1),
                        self.source.replace(b'migrations.RemoveConstraint(', b'migrations.RunSQL("SELECT 1"),\n        migrations.RemoveConstraint(', 1)):
            with self.subTest(size=len(mutated)), self.assertRaises(RuntimeError):
                self.activator.validate_migration(mutated)

    def test_the_operation_list_is_checked_independently_of_the_pin(self):
        activator = load_activator()
        activator.MIGRATION_SHA256 = activator.sha(self.source.replace(b"name='usage_charge_at_most_multiplier'", b"name='usage_charge_any'"))
        with self.assertRaises(RuntimeError):
            activator.validate_migration(self.source.replace(b"name='usage_charge_at_most_multiplier'", b"name='usage_charge_any'"))


class CatalogPins(unittest.TestCase):
    def setUp(self):
        self.activator = load_activator()
        self.models = (ROOT / 'rebuild/core/models.py').read_text()

    def test_every_pinned_definition_belongs_to_a_model_constraint(self):
        for table, name in list(self.activator.DEFINITIONS_AFTER) + [self.activator.NEW_INDEX[:2]]:
            self.assertIn(f"name='{name}'", self.models)
        self.assertIn('absorbed_over_limit', self.activator.DEFINITIONS_AFTER[('core_platformcost', 'platform_cost_kind_known')])
        self.assertIn('charged_cost <= (actual_cost * 1.5)', self.activator.DEFINITIONS_AFTER[('core_usage', 'usage_charge_at_most_multiplier')])
        self.assertIn('charged_cost = (actual_cost * 1.5)', self.activator.DEFINITIONS_BEFORE[('core_usage', 'exact_usage_multiplier')])
        self.assertIn("over_limit_delta=models.DecimalField(max_digits=24,decimal_places=12", self.models.replace(' ', ''))

    def test_catalog_checks_accept_exactly_the_declared_change(self):
        a = self.activator
        base = [('core_job', 'core_job_pkey', 'p', '-', 'PRIMARY KEY (id)')]
        before = base + [(t, n, 'c', '-', d) for (t, n), d in a.DEFINITIONS_BEFORE.items()]
        after = base + [(t, n, 'c', '-', d) for (t, n), d in a.DEFINITIONS_AFTER.items()]
        indexes_before = [('core_job', 'core_job_pkey', 'CREATE UNIQUE INDEX core_job_pkey ON public.core_job USING btree (id)')]
        indexes_after = indexes_before + [a.NEW_INDEX]
        a.check_before(before)
        a.check_catalog(sorted(before), sorted(after), indexes_before, sorted(indexes_after))
        wrong = [row if row[1] != 'usage_charge_at_most_multiplier' else row[:4] + ('CHECK ((charged_cost >= (0)::numeric))',) for row in after]
        for bad in (wrong, after + [('core_job', 'extra_check', 'c', '-', 'CHECK (true)')]):
            with self.subTest(rows=len(bad)), self.assertRaises(RuntimeError):
                a.check_catalog(sorted(before), sorted(bad), indexes_before, sorted(indexes_after))
        with self.assertRaises(RuntimeError):
            a.check_catalog(sorted(before), sorted(after), indexes_before, sorted(indexes_after + [('core_job', 'extra', 'CREATE INDEX extra ON public.core_job USING btree (id)')]))

    def test_schema_check_accepts_only_the_new_column(self):
        a = self.activator
        before = [{'table_name': 'core_job', 'column_name': 'id', 'data_type': 'uuid'}]
        after = before + [dict(a.NEW_COLUMN)]
        a.check_schema(before, after)
        for bad in (before + [dict(a.NEW_COLUMN, is_nullable='YES')], after + [{'table_name': 'core_job', 'column_name': 'x', 'data_type': 'text'}]):
            with self.subTest(rows=len(bad)), self.assertRaises(RuntimeError):
                a.check_schema(before, bad)


# The activation happened and shipped as this merge, so its range is now a historical fact. Comparing against a
# moving HEAD would turn this guard into a test that fails on the next unrelated commit — which says nothing about
# whether this activation declared what it shipped.
ACTIVATED = '5f673a3b2cc5c99d68f08f34fba43b4883403583'


class AllowedPaths(unittest.TestCase):
    def test_every_path_this_activation_shipped_was_declared(self):
        activator = load_activator()
        for commit in (activator.BASELINE, ACTIVATED):
            if subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', commit + '^{commit}'], capture_output=True).returncode:
                self.skipTest('The activation range is not available in this checkout (shallow clone).')
        changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', activator.BASELINE, ACTIVATED], text=True).split())
        self.assertNotEqual(changed, set())
        self.assertEqual(sorted(changed - activator.ALLOWED), [])
        for path in (activator.MIGRATION_PATH, activator.DECL, activator.SELF, 'rebuild/ops/test_recording_limit_activation.py'):
            self.assertIn(path, activator.ALLOWED)


if __name__ == '__main__':
    unittest.main()
