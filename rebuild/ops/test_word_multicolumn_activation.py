"""Guards for the multi-column/mixed Word release activation.

The driver's schema expectation moved from a COUNT to a declared SET. These prove the new
expectation is real on both the normal and the recovery path, that historical callers keep the
behaviour they shipped with, and that refreshing a source pin did not revive a spent activator.
"""
import hashlib
import pathlib
import re
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADAPTER = ROOT / 'scripts/activate-word-multicolumn.py'
DRIVER = ROOT / 'scripts/activate-typed-voice.py'
DECL = ROOT / 'docs/foundation/mutations/20260921-quillmd-word-multicolumn-activation.md'


def load(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


class Fake:
    def __init__(self, tables):
        self._tables = list(tables)

    def tables(self):
        return self._tables


class DeclaredSchema(unittest.TestCase):
    def setUp(self):
        self.adapter = load(ADAPTER, '_wm_adapter_under_test')

    def test_the_declaration_is_pinned_and_parses_to_the_reviewed_schema(self):
        self.assertEqual(hashlib.sha256(DECL.read_bytes()).hexdigest(), self.adapter.DECL_SHA256)
        self.assertEqual(len(self.adapter.BASELINE_TABLES), 36)
        self.assertIn('core_servicehealth', self.adapter.BASELINE_TABLES)

    def test_the_declared_schema_is_the_historical_one_plus_exactly_the_reviewed_table(self):
        """⚠️ The expectation must come from the DECLARATION, not from the database under test."""
        driver = load(DRIVER, '_wm_driver_historical')
        self.assertEqual(len(driver.BASELINE_TABLES), 35)
        self.assertNotIn('core_servicehealth', driver.BASELINE_TABLES)
        self.assertEqual(self.adapter.BASELINE_TABLES - driver.BASELINE_TABLES, {'core_servicehealth'})
        self.assertEqual(driver.BASELINE_TABLES - self.adapter.BASELINE_TABLES, set())

    def test_the_declaration_block_cannot_drift_into_reading_prose_or_nothing(self):
        text = DECL.read_text()
        head = text.split(self.adapter.SCHEMA_MARKER)[0]
        for broken in (text.replace(self.adapter.SCHEMA_MARKER, ''),
                       head + self.adapter.SCHEMA_MARKER + '\n\n```text\n```\n',
                       head + self.adapter.SCHEMA_MARKER + '\n\n```text\nsee the table above\n```\n',
                       head + self.adapter.SCHEMA_MARKER + '\n\n  ```text\n  core_usage\n  ```\n'):
            with self.subTest(), self.assertRaises(RuntimeError):
                self.adapter.declared(self.adapter.SCHEMA_MARKER, broken)


class SchemaExpectationIsASetNotACount(unittest.TestCase):
    """The same object guards the normal path and the recovery path."""

    def setUp(self):
        self.driver = load(DRIVER, '_wm_driver_schema')
        self.adapter_tables = load(ADAPTER, '_wm_adapter_schema').BASELINE_TABLES

    def check(self, tables):
        self.driver.require_baseline_schema(Fake(tables))

    def test_the_historical_schema_still_succeeds_for_historical_callers(self):
        self.check(self.driver.BASELINE_TABLES)

    def test_the_current_schema_succeeds_once_the_adapter_supplies_it(self):
        self.driver.BASELINE_TABLES = self.adapter_tables
        self.check(self.adapter_tables)

    def test_a_missing_table_refuses(self):
        with self.assertRaises(RuntimeError):
            self.check(set(self.driver.BASELINE_TABLES) - {'core_usage'})

    def test_an_extra_table_refuses(self):
        with self.assertRaises(RuntimeError):
            self.check(set(self.driver.BASELINE_TABLES) | {'core_servicehealth'})

    def test_AN_INCORRECT_SET_OF_THE_SAME_COUNT_REFUSES(self):
        """⚠️ THE WHOLE POINT. `len(...) == 35` accepted this: one dropped, one added, count equal."""
        wrong = (set(self.driver.BASELINE_TABLES) - {'core_usage'}) | {'core_servicehealth'}
        self.assertEqual(len(wrong), len(self.driver.BASELINE_TABLES))
        with self.assertRaises(RuntimeError):
            self.check(wrong)

    def test_the_refusal_names_what_is_missing_and_what_is_unexpected(self):
        with self.assertRaises(RuntimeError) as raised:
            self.check((set(self.driver.BASELINE_TABLES) - {'core_usage'}) | {'core_servicehealth'})
        self.assertIn('core_usage', str(raised.exception))
        self.assertIn('core_servicehealth', str(raised.exception))


class OneExpectationOnBothPaths(unittest.TestCase):
    def test_the_normal_and_recovery_paths_share_one_expectation(self):
        source = DRIVER.read_text()
        self.assertEqual(source.count('BASELINE_TABLES = frozenset('), 1,
                         'the expectation must be declared exactly once')
        self.assertEqual(len(re.findall(r'^\s*require_baseline_schema\(old\)$', source, re.M)), 2,
                         'both the normal path and the recovery path must use it')
        # ⚠️ CODE LINES ONLY. The first version of this assertion searched the whole file and
        # matched the COMMENT that documents the defect — a probe whose pattern appears in the
        # searcher cannot return false, and here it could not return TRUE either.
        code = '\n'.join(line for line in source.splitlines()
                         if not line.lstrip().startswith('#'))
        self.assertNotIn('tables()) == 35', code, 'no count comparison may survive in code')
        self.assertNotIn('tables()) == 36', code, 'and it must not become another count')


class MigrationFrontier(unittest.TestCase):
    def test_the_adapter_selects_the_reviewed_frontier(self):
        adapter = load(ADAPTER, '_wm_adapter_migration')
        self.assertEqual(adapter.MIGRATION, '0018_servicehealth')

    def test_a_wrong_frontier_refuses(self):
        driver = load(DRIVER, '_wm_driver_migration')
        driver.MIGRATION = '0018_servicehealth'
        calls = {'plan': False}

        class Out:
            def __init__(self, frontier):
                self.frontier = frontier

            def __call__(self, command):
                statement = command[-1]
                if 'ORDER BY id DESC' in statement:
                    return self.frontier
                return '1'

        driver.b = types.SimpleNamespace(
            verify_migration_plan=lambda plan, applied: calls.__setitem__('plan', True),
            output=Out('0017_reconciliation_evidence_kind'))
        with self.assertRaises(RuntimeError):
            driver.verify_migrations(types.SimpleNamespace(PSQL=['psql']), 'plan')
        self.assertTrue(calls['plan'], 'the existing plan check must still run')
        driver.b.output = Out('0018_servicehealth')
        driver.verify_migrations(types.SimpleNamespace(PSQL=['psql']), 'plan')


class PinsAndSpentActivators(unittest.TestCase):
    def test_the_adapter_pins_the_driver_by_content(self):
        adapter = load(ADAPTER, '_wm_adapter_pin')
        self.assertEqual(hashlib.sha256(DRIVER.read_bytes()).hexdigest(), adapter.DRIVER_SHA256)

    def test_driver_source_drift_refuses(self):
        adapter = load(ADAPTER, '_wm_adapter_drift')
        with self.assertRaises(RuntimeError):
            adapter.pinned_module('scripts/activate-admin-console.py', adapter.DRIVER_SHA256, '_drifted')

    def test_dependent_pins_were_refreshed_to_the_actual_driver(self):
        actual = hashlib.sha256(DRIVER.read_bytes()).hexdigest()
        for path, label in ((ROOT / 'scripts/activate-typed-voice-generation.py', 'ASSET_READER_SHA256'),
                            (ROOT / 'scripts/activate-admin-console.py', 'DRIVER_SHA256')):
            with self.subTest(caller=path.name):
                found = re.search(label + r" = '([0-9a-f]{64})'", path.read_text())
                self.assertIsNotNone(found)
                self.assertEqual(found.group(1), actual)

    def test_refreshing_the_pin_did_not_make_the_spent_activator_reusable(self):
        """⚠️ A pin refresh is not a licence. The console activator must still be spent."""
        console = (ROOT / 'scripts/activate-admin-console.py').read_text()
        self.assertIn('The declared new table already exists.', console)
        self.assertIn('Shared source already carries the new migration before the advance.', console)


if __name__ == '__main__':
    unittest.main()
