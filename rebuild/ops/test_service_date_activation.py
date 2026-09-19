"""The service-date activator's static guards, proved against the real migration, models and repository."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

try:
    from . import source_module
except ImportError:
    import source_module

from exercised import requires_distinct, requires_input

ROOT = Path(__file__).resolve().parents[2]


def load_activator():
    return source_module.load('activate_service_date', ROOT / 'scripts/activate-service-date.py')


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


# The activation happened and shipped as this merge, so its range is now a historical fact.
# ⚠️ THE SELF-MAINTAINING CONDITION THIS CLASS FIRST CARRIED DID NOT FIRE. It skipped only when a migration later
# than 0014 existed — but main moved on while 0014 stayed the newest, so the guard kept comparing a fixed BASELINE
# against a MOVING HEAD and began failing on work that had nothing to do with this activation. A guard keyed on the
# wrong signal is a guard that goes off at the wrong time, which is how people learn to ignore it.
ACTIVATED = '5f8050df5e79c0d7948185850914f1c161fcbc1f'


class AllowedPaths(unittest.TestCase):
    def test_every_path_this_activation_shipped_was_declared(self):
        activator = load_activator()
        for commit in (activator.BASELINE, ACTIVATED):
            if subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', commit + '^{commit}'],
                              capture_output=True).returncode:
                self.skipTest('The activation range is not available in this checkout (shallow clone).')
        changed = set(subprocess.check_output(
            ['git', '-C', str(ROOT), 'diff', '--name-only', activator.BASELINE, ACTIVATED], text=True).split())
        requires_input(changed != set(),
                       'a non-empty diff between the baseline and the activated merge — an empty range would '
                       'make this comparison pass while proving nothing about what shipped')
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
        """The first version of this check was `any(is None) or all(is not None)` — true for every input.

        It passed because it was only ever fed UNIFORM inputs: both up, or both down. The
        discriminating case — one of each — is the whole point of the check and was never tried.
        This test now calls the activator's OWN predicate rather than a copy that can drift from it.
        """
        up = {'release': self.activator.RUNNING_RELEASE, 'data_mode': 'synthetic-only'}
        cases = [([None, None], True), ([up, up], True), ([None, up], False), ([up, None], False)]
        requires_distinct([sorted(map(repr, health)) for health, _ in cases],
                          'health inputs that actually differ in shape — uniform inputs cannot tell a '
                          'working agreement check from a tautology')
        requires_input(any(expected is False for _, expected in cases),
                       'at least one input the check must REFUSE, or it is only ever asked to say yes')
        for health, expected in cases:
            with self.subTest(health=[type(a).__name__ for a in health]):
                self.assertEqual(self.activator.surfaces_agree(health), expected)

    def test_a_service_answering_an_unexplained_release_is_refused(self):
        running = self.activator.RUNNING_RELEASE
        cases = [(None, True),
                 ({'release': running, 'data_mode': 'synthetic-only'}, True),
                 ({'release': 'something-else', 'data_mode': 'synthetic-only'}, False),
                 ({'release': running, 'data_mode': 'real'}, False)]
        requires_input(any(expected is False for _, expected in cases),
                       'at least one answer the check must REFUSE')
        for answer, expected in cases:
            with self.subTest(answer=answer):
                self.assertEqual(self.activator.answer_acceptable(answer, running), expected)
