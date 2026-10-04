"""Finite source controls for the single reviewed 0038 predicate expansion."""
import ast
import hashlib
import importlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError
from ops import integrity_contract
from ops import capture_v1_install_schema
from ops import v1_private_install_adapter as adapter
from ops import v1_private_install_preparation as preparation

ROOT = Path(__file__).resolve().parents[2]
NAME = '0038_reinspection_confirmation_guard'


def literal(name, variable):
    tree = ast.parse((ROOT / 'core/migrations' / (name + '.py')).read_text())
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == variable for target in node.targets))


class ReinspectionMigrationSource(unittest.TestCase):
    def test_capture_and_renewed_preparation_bind_the_exact_twenty_member_source(self):
        repository = ROOT.parent
        raw = (repository / capture_v1_install_schema.SCHEMA).read_bytes()
        schema = json.loads(raw)
        old = json.loads((repository / 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract.json').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), capture_v1_install_schema.SCHEMA_SHA256)
        self.assertEqual(capture_v1_install_schema.LEAF, NAME)
        self.assertEqual(capture_v1_install_schema.FORWARD_MIGRATIONS, 20)
        self.assertEqual(capture_v1_install_schema.DATABASE, 'quillmd_qa_sol_installcontract38_1004')
        self.assertEqual(schema['candidate_core_migration'], NAME)
        self.assertEqual(schema['baseline_prefix_sha256'], old['baseline_prefix_sha256'])
        self.assertEqual(schema['baseline_core_columns'], old['baseline_core_columns'])
        self.assertEqual(schema['candidate_core_columns'], old['candidate_core_columns'])
        self.assertEqual({name: value for name, value in schema['forward_migration_sha256'].items() if name != NAME},
                         old['forward_migration_sha256'])
        self.assertEqual(schema['forward_migration_sha256'][NAME],
                         hashlib.sha256((ROOT / 'core/migrations' / (NAME + '.py')).read_bytes()).hexdigest())
        self.assertEqual(preparation.LEAF, NAME)
        self.assertEqual(preparation.SCHEMA_SHA256, capture_v1_install_schema.SCHEMA_SHA256)
        self.assertEqual((repository / preparation.SCHEMA_PATH).read_bytes(), raw)

    def test_catalog_capture_refuses_a_newer_foreign_or_ambiguous_leaf_before_migration(self):
        for nodes in ([('core', '0037_transcript_redaction_boundary')], [('core', NAME), ('core', '0037_transcript_redaction_boundary')],
                      [], [('auth', '0001_initial')]):
            graph = SimpleNamespace(leaf_nodes=lambda: nodes)
            with self.subTest(nodes=nodes), self.assertRaisesRegex(ValueError, 'Actual core migration leaf differs'):
                capture_v1_install_schema.require_declared_core_leaf(graph, preparation.LEAF)
        graph = SimpleNamespace(leaf_nodes=lambda: [('core', preparation.LEAF), ('auth', '0001_initial')])
        capture_v1_install_schema.require_declared_core_leaf(graph, preparation.LEAF)

    def test_the_only_forward_sql_change_is_the_exact_reinspection_predicate(self):
        previous = literal('0031_previous_release_mapping_writes', 'GATE')
        expected = previous.replace("v.contract='v3' AND NOT EXISTS",
                                    "(v.contract='v3' OR v.import_manifest ? 'reinspection') AND NOT EXISTS")
        self.assertEqual(previous.count("v.contract='v3' AND NOT EXISTS"), 1)
        self.assertEqual(literal(NAME, 'GATE'), expected)
        self.assertEqual(expected.count('CREATE OR REPLACE FUNCTION'), 1)
        for forbidden in ('CREATE TRIGGER', 'ALTER TABLE', 'DROP ', 'UPDATE core_', 'INSERT INTO', 'DELETE FROM'):
            self.assertNotIn(forbidden, expected)

    def test_latest_function_body_is_bound_without_changing_trigger_membership(self):
        body = re.fullmatch(r'CREATE OR REPLACE FUNCTION quillmd_encounter_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;',
                            literal(NAME, 'GATE'), re.S)[1]
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),
                         integrity_contract.FUNCTION_SHA256['quillmd_encounter_guard'])
        self.assertEqual(len(integrity_contract.GUARDS), 111)
        self.assertEqual(len(integrity_contract.FUNCTION_SHA256), 28)

    def test_reverse_checks_evidence_before_restoring_the_historical_body(self):
        module = importlib.import_module('core.migrations.' + NAME)
        self.assertEqual(module.Migration.dependencies, [('core', '0037_transcript_redaction_boundary')])
        operations = module.Migration.operations
        self.assertEqual([type(op) for op in operations], [migrations.RunSQL, migrations.RunPython])
        self.assertEqual(operations[0].reverse_sql, literal('0031_previous_release_mapping_writes', 'GATE'))
        self.assertIs(operations[1].reverse_code, module.preserve_reinspection_review)
        self.assertIs(operations[1].code, migrations.RunPython.noop)

    def test_reverse_refuses_any_marker_on_the_actual_alias_and_reports_only_a_count(self):
        module = importlib.import_module('core.migrations.' + NAME)
        for count in (1, 3):
            objects = Mock()
            query = objects.using.return_value.filter.return_value
            query.count.return_value = count
            apps = Mock(); apps.get_model.return_value = SimpleNamespace(objects=objects)
            editor = SimpleNamespace(connection=SimpleNamespace(alias='owned_synthetic'))
            with self.subTest(count=count), self.assertRaisesRegex(IrreversibleError, f'{count} mapping version'):
                module.preserve_reinspection_review(apps, editor)
            apps.get_model.assert_called_once_with('core', 'TemplateVersion')
            objects.using.assert_called_once_with('owned_synthetic')
            objects.using.return_value.filter.assert_called_once_with(import_manifest__has_key='reinspection')
            query.count.assert_called_once_with()

    def test_reverse_without_reinspection_evidence_performs_no_write(self):
        module = importlib.import_module('core.migrations.' + NAME)
        objects = Mock(); objects.using.return_value.filter.return_value.count.return_value = 0
        apps = Mock(); apps.get_model.return_value = SimpleNamespace(objects=objects)
        module.preserve_reinspection_review(apps, SimpleNamespace(connection=SimpleNamespace(alias='owned_synthetic')))
        self.assertEqual(len(objects.mock_calls), 3)

    def test_historical_nineteen_migration_install_contract_refuses_the_added_guard(self):
        repository = ROOT.parent
        schema_bytes = (repository / 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract.json').read_bytes()
        schema = json.loads(schema_bytes)
        paths = preparation.REQUIRED_SOURCE | {
            'rebuild/core/migrations/' + name + '.py'
            for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
        extra = 'rebuild/core/migrations/' + NAME + '.py'
        sources = {path: (repository / path).read_bytes() for path in paths | {extra}}
        declaration = {'format': 'quillmd-private-v1-preparation-v1', 'baseline': preparation.BASELINE,
            'target': 'a' * 40, 'schema_sha256': preparation.SCHEMA_SHA256,
            'source_sha256': {name: preparation.sha(raw) for name, raw in sources.items()},
            'data_mode': 'synthetic', 'payment_mode': 'test', 'public_maintenance': True, 'cpt_enabled': False}
        with self.assertRaisesRegex(ValueError, 'Reviewed schema source changed'):
            preparation.source_contract(declaration, schema_bytes, sources)
        self.assertEqual(len(schema['forward_migration_sha256']), 19)
        self.assertEqual(schema['candidate_core_migration'], '0037_transcript_redaction_boundary')

    def test_retained_catalog_refuses_changed_function_source_until_actual_renewal(self):
        repository = ROOT.parent
        directory = repository / 'docs/rebuild/v1/private-synthetic-install-preparation-20261004'
        schema_bytes = (directory / 'schema-contract.json').read_bytes()
        schema = json.loads(schema_bytes)
        paths = adapter.CATALOG_SOURCES | {
            'rebuild/core/migrations/' + name + '.py'
            for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
        sources = {path: (repository / path).read_bytes() for path in paths}
        # The tracked receipt intentionally does not embed its 575490-byte raw
        # catalog. This simulated envelope isolates the receipt's actual source
        # witness; CI never reads the protected raw artifact or calls it a full
        # catalog qualification.
        receipt = json.loads((directory / 'postgresql-catalog-capture.json').read_bytes())
        simulated = {'format': 'quillmd-v1-postgresql-upgrade-contract-v1',
            'baseline': preparation.BASELINE, 'schema_sha256': receipt['schema_sha256'],
            'source_sha256': receipt['source_sha256'], 'before': {}, 'after': {},
            'new_permissions': [], 'new_content_types': []}
        with self.assertRaisesRegex(ValueError, 'different source bytes'):
            adapter.validate_catalog_contract(json.dumps(simulated).encode(), sources, schema_bytes)

    def test_renewed_capture_receipt_binds_current_catalog_sources_and_retains_the_old_identity(self):
        repository = ROOT.parent
        directory = repository / 'docs/rebuild/v1/private-synthetic-install-preparation-20261004'
        current = json.loads((directory / 'postgresql-catalog-capture-0038.json').read_bytes())
        previous = json.loads((directory / 'postgresql-catalog-capture.json').read_bytes())
        schema_bytes = (repository / preparation.SCHEMA_PATH).read_bytes()
        schema = json.loads(schema_bytes)
        paths = adapter.CATALOG_SOURCES | {
            'rebuild/core/migrations/' + name + '.py'
            for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
        sources = {path: (repository / path).read_bytes() for path in paths}
        self.assertEqual(len(paths), 42)
        self.assertEqual(current['source_sha256'], {path: preparation.sha(raw) for path, raw in sources.items()})
        self.assertEqual(current['schema_sha256'], preparation.sha(schema_bytes))
        self.assertEqual(current['forward_migration_count'], 20)
        self.assertEqual(current['full_catalog_items']['after'], {'functions': 28, 'triggers': 111})
        self.assertEqual((current['actual_child_exit'], current['actual_outer_exit']), (0, 0))
        self.assertTrue(current['database_destroyed'])
        self.assertEqual(current['database_catalog_count'], 0)
        self.assertEqual(current['remaining_connections'], 0)
        self.assertNotEqual(current['schema_sha256'], previous['schema_sha256'])
        self.assertNotEqual(current['raw_contract']['sha256'], previous['raw_contract']['sha256'])
        # This deliberately incomplete envelope exercises the old identity
        # refusal only. A receipt and this test never replace reading the raw
        # complete catalog through the normal installer.
        simulated = {'format': 'quillmd-v1-postgresql-upgrade-contract-v1',
            'baseline': preparation.BASELINE, 'schema_sha256': previous['schema_sha256'],
            'source_sha256': previous['source_sha256'], 'before': {}, 'after': {},
            'new_permissions': [], 'new_content_types': []}
        with self.assertRaisesRegex(ValueError, 'Catalog contract identity differs'):
            adapter.validate_catalog_contract(json.dumps(simulated).encode(), sources, schema_bytes)
