"""Provider-free contracts for prospective installation preparation, never host-action tests."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from ops import v1_private_install_preparation as p

ROOT = Path(__file__).resolve().parents[3]


class PrivateV1PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema_bytes = (ROOT / 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract.json').read_bytes()
        cls.schema = json.loads(cls.schema_bytes)
        paths = p.REQUIRED_SOURCE | {
            'rebuild/core/migrations/' + name + '.py'
            for name in {**cls.schema['baseline_prefix_sha256'], **cls.schema['forward_migration_sha256']}}
        cls.sources = {name: (ROOT / name).read_bytes() for name in paths}
        cls.target = 'a' * 40
        cls.declaration = {'format': 'quillmd-private-v1-preparation-v1', 'baseline': p.BASELINE,
            'target': cls.target, 'schema_sha256': p.SCHEMA_SHA256,
            'source_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in cls.sources.items()},
            'data_mode': 'synthetic', 'payment_mode': 'test', 'public_maintenance': True, 'cpt_enabled': False}
        cls.evidence = {'ci': [{'workflow': name, 'head_sha': cls.target, 'status': 'completed',
            'conclusion': 'success', 'run_id': i + 1, 'attempt': 1} for i, name in enumerate(sorted(p.WORKFLOWS))],
            'source_refutation': {'target': cls.target, 'complete': True, 'clinical_unsafe': 0, 'word_unsafe': 0},
            'ai_mode': 'fixture', 'isolated_state': True}

    def test_fixture_exception_is_separate_has_no_installed_units_or_execution_authority(self):
        evidence = {**self.evidence, 'word': {'overall_total': 60, 'overall_pass': 0, 'eligible_overall': 53}}
        result = p.plan(self.declaration, self.schema_bytes, self.sources, evidence, destination='isolated_fixture_demo')
        self.assertEqual(result['private_units'], [])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['installed_mutation_performed'])
        self.assertEqual(len(result['forward_migrations']), 19)
        for changes in ({'ai_mode': 'live'}, {'isolated_state': False},
                        {'source_refutation': {'target': self.target, 'complete': True, 'clinical_unsafe': 1, 'word_unsafe': 0}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                p.plan(self.declaration, self.schema_bytes, self.sources, {**evidence, **changes},
                       destination='isolated_fixture_demo')

    def installed_evidence(self):
        return {**copy.deepcopy(self.evidence), 'exact_merged_pr': {'target': self.target, 'base': 'main', 'merged': True},
            'word': {'target': self.target, 'overall_total': 60, 'overall_pass': 54, 'holdout_total': 20,
                     'holdout_pass': 18, 'eligible_overall': 60, 'family_protocol_passed': True,
                     'safety_protocol_passed': True, 'manual_recovery_counted_as_automatic': False},
            'generation': {'target': self.target, 'requested_model': p.MODEL, 'returned_model': p.MODEL,
                           'ordinary_field_contract': p.CONTRACT, 'usefulness_qualified': True, 'unsafe_answers': 0},
            'populated_upgrade': {'migration_sha256': self.schema['forward_migration_sha256'], 'passed': True}}

    def test_current_fifty_three_maximum_and_manual_recovery_cannot_satisfy_installed_gate(self):
        for changes in ({'overall_pass': 53}, {'eligible_overall': 53}, {'overall_total': 53},
                        {'holdout_total': 19}, {'holdout_pass': 17}, {'overall_pass': 61},
                        {'family_protocol_passed': False}, {'safety_protocol_passed': False},
                        {'manual_recovery_counted_as_automatic': True}):
            evidence = self.installed_evidence(); evidence['word'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                p.plan(self.declaration, self.schema_bytes, self.sources, evidence, destination='installed_qualified_v1')
        result = p.plan(self.declaration, self.schema_bytes, self.sources, self.installed_evidence(),
                        destination='installed_qualified_v1')
        self.assertEqual(result['private_units'], list(p.UNITS))
        self.assertFalse(result['execution_authorized'])
        self.assertIn('No automatic old-source checkout', result['rollback'])

    def test_exact_source_prefix_graph_and_synthetic_boundary_cannot_be_relabelled(self):
        for changes in ({'target': 'a' * 8}, {'baseline': 'b' * 40}, {'data_mode': 'real'},
                        {'payment_mode': 'live'}, {'public_maintenance': False}, {'cpt_enabled': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                p.source_contract({**self.declaration, **changes}, self.schema_bytes, self.sources)
        for name in ('0001_initial', '0037_transcript_redaction_boundary'):
            path = 'rebuild/core/migrations/' + name + '.py'
            sources = {**self.sources, path: self.sources[path] + b'\n# altered\n'}
            declaration = copy.deepcopy(self.declaration)
            declaration['source_sha256'][path] = p.sha(sources[path])
            with self.subTest(name=name), self.assertRaises(ValueError):
                p.source_contract(declaration, self.schema_bytes, sources)
        extra = 'rebuild/core/migrations/0038_unreviewed.py'
        sources = {**self.sources, extra: b'# omitted migration'}
        declaration = copy.deepcopy(self.declaration); declaration['source_sha256'][extra] = p.sha(sources[extra])
        with self.assertRaises(ValueError): p.source_contract(declaration, self.schema_bytes, sources)

    def test_exact_citation_model_usefulness_and_merged_install_checks_are_separate(self):
        for field, value in (('head_sha', 'b' * 40), ('conclusion', 'failure'), ('status', 'queued'), ('attempt', 2)):
            evidence = self.installed_evidence(); evidence['ci'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.plan(self.declaration, self.schema_bytes, self.sources, evidence, destination='installed_qualified_v1')
        for field, value in (('returned_model', 'claude-sonnet-4-6'), ('usefulness_qualified', False), ('unsafe_answers', 1)):
            evidence = self.installed_evidence(); evidence['generation'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.plan(self.declaration, self.schema_bytes, self.sources, evidence, destination='installed_qualified_v1')
        evidence = self.installed_evidence(); evidence.pop('exact_merged_pr')
        with self.assertRaises(ValueError):
            p.plan(self.declaration, self.schema_bytes, self.sources, evidence, destination='installed_qualified_v1')

    def inventories(self):
        digest = p.sha(b'synthetic historical rows')
        before = {'core_columns': self.schema['baseline_core_columns'],
            'core_rows': {name: {'rows': 1, 'sha256': digest} for name in self.schema['baseline_core_columns']},
            'files': {'exports/historical.docx': {'sha256': p.sha(b'historical export'), 'bytes': 17}},
            'unrelated_services': {'other-tenant': {'container': 'unchanged', 'mounts': ['unchanged']}}}
        after = {'core_columns': self.schema['candidate_core_columns'],
            'projection_columns': self.schema['baseline_core_columns'], 'old_core_rows': before['core_rows'],
            'new_core_rows': {name: {'rows': 0, 'sha256': p.sha(b'')} for name in self.schema['new_core_tables']},
            'files': before['files'], 'unrelated_services': before['unrelated_services']}
        return copy.deepcopy(before), copy.deepcopy(after)

    def test_old_financial_columns_files_new_table_population_and_cotenants_are_preserved(self):
        before, after = self.inventories()
        result = p.preserve_stopped_inventory(self.schema_bytes, before, after)
        self.assertEqual((result['old_core_tables_preserved'], result['new_core_tables_empty']), (29, 24))
        mutations = [lambda a: a['projection_columns']['core_ledgerentry'].remove('amount'),
                     lambda a: a['old_core_rows']['core_wallet'].update(sha256=p.sha(b'changed balance')),
                     lambda a: a['files']['exports/historical.docx'].update(sha256=p.sha(b'changed download')),
                     lambda a: a['new_core_rows']['core_retentionhold'].update(rows=1),
                     lambda a: a['unrelated_services']['other-tenant'].update(mounts=[])]
        for mutation in mutations:
            before, after = self.inventories(); mutation(after)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                p.preserve_stopped_inventory(self.schema_bytes, before, after)
        for files in ({'exports/historical.docx': {'sha256': 'unbound', 'bytes': 17}},
                      {'../historical.docx': {'sha256': p.sha(b'historical export'), 'bytes': 17}},
                      {'exports/historical.docx': {'sha256': p.sha(b'historical export'), 'bytes': True}}):
            before, after = self.inventories(); before['files'] = after['files'] = files
            with self.subTest(files=files), self.assertRaises(ValueError):
                p.preserve_stopped_inventory(self.schema_bytes, before, after)
