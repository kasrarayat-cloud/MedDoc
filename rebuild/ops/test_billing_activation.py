"""The billing-policy activator's static guards, proved against the real migration and repository."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_activator():
    spec = importlib.util.spec_from_file_location('activate_billing_policy', ROOT / 'scripts/activate-billing-policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationValidation(unittest.TestCase):
    def setUp(self):
        self.activator = load_activator()
        self.source = (ROOT / self.activator.MIGRATION_PATH).read_text()

    def test_real_migration_is_exactly_two_create_models(self):
        self.activator.validate_migration(self.source)

    def test_added_field_on_an_existing_table_is_refused(self):
        anchor = "migrations.CreateModel(\n            name='PlatformCost'"
        self.assertEqual(self.source.count(anchor), 1)
        mutated = self.source.replace(anchor, "migrations.AddField(model_name='usage',name='x',field=models.IntegerField()),\n        " + anchor)
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.activator.validate_migration(mutated)

    def test_run_sql_and_renamed_model_are_refused(self):
        mutated = self.source.replace("name='CostReconciliation'", "name='CostReconciliationX'")
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.activator.validate_migration(mutated)
        anchor = "    operations = ["
        self.assertEqual(self.source.count(anchor), 1)
        mutated = self.source.replace(anchor, anchor + "\n        migrations.RunSQL('SELECT 1'),")
        with self.assertRaises(RuntimeError):
            self.activator.validate_migration(mutated)

    def test_import_alias_that_rebinds_migrations_is_refused(self):
        mutated = self.source.replace('from django.db import migrations, models', 'from django.db import models\nfrom core import models as migrations')
        self.assertNotEqual(mutated, self.source)
        with self.assertRaises(RuntimeError):
            self.activator.validate_migration(mutated)
        mutated = self.source.replace('import uuid', 'import uuid\nimport core.billing as extra')
        with self.assertRaises(RuntimeError):
            self.activator.validate_migration(mutated)

    def test_import_time_code_is_refused_everywhere(self):
        anchor = "class Migration(migrations.Migration):"
        self.assertEqual(self.source.count(anchor), 1)
        vectors = [
            self.source.replace(anchor, "@print\n" + anchor),
            self.source.replace(anchor, anchor + "\n    print('side effect')"),
            self.source.replace(anchor, anchor + "\n    marker: int = __import__('os').getpid()"),
            self.source.replace("default=uuid.uuid4", "default=__import__('os').getpid", 1),
            self.source.replace("default=uuid.uuid4", "default=(lambda: 1)", 1),
            self.source.replace("default=uuid.uuid4", "default=uuid.uuid4()", 1).replace("import uuid", "import uuid\nimport os"),
            self.source.replace("'evidence_reference', ''", "'evidence_reference', [x for x in ()]", 1),
        ]
        for mutated in vectors:
            self.assertNotEqual(mutated, self.source)
            with self.assertRaises(RuntimeError):
                self.activator.validate_migration(mutated)

    def test_reachable_callables_under_allowed_roots_are_refused(self):
        vectors = [
            self.source.replace("default=uuid.uuid4", "default=django.core.management.call_command('shell', command='print(1)')", 1),
            self.source.replace("default=uuid.uuid4", "default=django.db.connection.ops.execute_sql_flush(['SELECT 1'])", 1),
            self.source.replace("default=uuid.uuid4", "default=models.signals.post_migrate.connect", 1),
            self.source.replace("default=uuid.uuid4", "default=settings.configure", 1),
            self.source.replace("default=uuid.uuid4", "default=uuid.uuid1", 1),
            self.source.replace("on_delete=django.db.models.deletion.PROTECT", "on_delete=django.db.models.deletion.CASCADE", 1),
            self.source.replace("models.CheckConstraint(", "models.Index(", 1),
        ]
        for mutated in vectors:
            self.assertNotEqual(mutated, self.source)
            with self.assertRaises(RuntimeError):
                self.activator.validate_migration(mutated)

    def test_expected_catalog_names_match_the_migration_constraints(self):
        import ast
        tree = ast.parse(self.source)
        declared = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'attr', '') in ('CheckConstraint', 'UniqueConstraint'):
                declared.add(ast.literal_eval({k.arg: k.value for k in node.keywords}['name']))
        expected = {name for rows in self.activator.EXPECTED_CONSTRAINTS.values() for name, kind, _ in rows if kind == 'c'}
        expected |= {name for rows in self.activator.EXPECTED_INDEXES.values() for name in rows if name == 'one_absorbed_failure_per_job'}
        self.assertEqual(declared, expected)
        targets = {target for rows in self.activator.EXPECTED_CONSTRAINTS.values() for _, kind, target in rows if kind == 'f'}
        self.assertEqual(targets, {'core_user', 'core_usage', 'core_job'})
        self.assertEqual(set(self.activator.EXPECTED_CONSTRAINTS), set(self.activator.NEW_TABLES))
        self.assertEqual(set(self.activator.EXPECTED_INDEXES), set(self.activator.NEW_TABLES))

    def test_new_table_columns_match_the_model_definitions(self):
        import ast
        tree = ast.parse(self.source)
        found = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'attr', '') == 'CreateModel':
                keywords = {k.arg: k.value for k in node.keywords}
                name = ast.literal_eval(keywords['name']).lower()
                columns = set()
                for field in keywords['fields'].elts:
                    field_name = ast.literal_eval(field.elts[0])
                    call = field.elts[1]
                    is_relation = getattr(call.func, 'attr', '') in ('ForeignKey', 'OneToOneField')
                    columns.add(field_name + '_id' if is_relation else field_name)
                found['core_' + name] = columns
        self.assertEqual(found, self.activator.NEW_TABLES)


class AllowedPaths(unittest.TestCase):
    def test_every_changed_path_since_the_running_release_is_declared(self):
        activator = load_activator()
        probe = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', activator.BASELINE + '^{commit}'], capture_output=True)
        if probe.returncode != 0:
            self.skipTest('Running-release commit is not available in this checkout (shallow clone).')
        changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', activator.BASELINE, 'HEAD'], text=True).split())
        self.assertEqual(sorted(changed - activator.ALLOWED), [])
        self.assertIn(activator.MIGRATION_PATH, activator.ALLOWED)
        self.assertIn(activator.DECL, activator.ALLOWED)


if __name__ == '__main__':
    unittest.main()
