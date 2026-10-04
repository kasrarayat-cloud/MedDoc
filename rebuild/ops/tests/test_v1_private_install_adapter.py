"""Provider/DB/host-free fault controls for the new preserving installation door."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ops import v1_private_install_adapter as a
from ops import v1_private_install_preparation as p
from ops import v1_install_catalog as catalog
from ops import v1_install_participants as participants

ROOT = Path(__file__).resolve().parents[3]


class PrivateV1InstallAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Delegate existing gate fixture construction without importing a test
        # class into module scope (which would duplicate CI method identities).
        from ops.tests import test_v1_private_install_preparation as fixture
        fixture.PrivateV1PreparationTests.setUpClass()
        source = fixture.PrivateV1PreparationTests()
        cls.schema_bytes, cls.schema = source.schema_bytes, source.schema
        cls.sources = {**source.sources, **{path: (ROOT / path).read_bytes() for path in a.CATALOG_SOURCES}}
        cls.declaration = copy.deepcopy(source.declaration)
        cls.declaration['source_sha256'] = {path: p.sha(raw) for path, raw in cls.sources.items()}
        cls.evidence = source.installed_evidence()
        cls.before = cls.inventory(sorted(set(cls.schema['baseline_core_columns']) | a.NONCORE))
        cls.after = cls.inventory(sorted(set(cls.schema['candidate_core_columns']) | a.NONCORE))
        cls.after.update(old_rows=cls.before['rows'], old_columns=cls.before['columns'],
            new_core_rows={name: {'rows': 0, 'sha256': p.sha(b'')} for name in cls.schema['new_core_tables']},
            new_noncore_rows={'django_migrations': sorted([['core', name] for name in cls.schema['forward_migration_sha256']]),
                             'django_content_type': [['core', 'newmodel']],
                             'auth_permission': [['core', 'newmodel', 'view_newmodel', 'Can view new model']]})
        paths = a.CATALOG_SOURCES | {'rebuild/core/migrations/' + name + '.py'
            for name in {**cls.schema['baseline_prefix_sha256'], **cls.schema['forward_migration_sha256']}}
        cls.contract = {'format': 'quillmd-v1-postgresql-upgrade-contract-v1', 'baseline': p.BASELINE,
            'source_sha256': {path: p.sha(cls.sources[path]) for path in paths}, 'schema_sha256': p.sha(cls.schema_bytes),
            'before': a.schema_catalog(cls.before, owner='quillmd_owner'),
            'after': a.schema_catalog(cls.after, owner='quillmd_owner'),
            'new_permissions': cls.after['new_noncore_rows']['auth_permission'],
            'new_content_types': cls.after['new_noncore_rows']['django_content_type']}
        cls.catalog_bytes = json.dumps(cls.contract, sort_keys=True).encode()

    @staticmethod
    def inventory(tables):
        return {'tables': tables, 'schema': [{'table_name': name, 'column_name': 'id'} for name in tables],
            'constraints': [['core_wallet', 'wallet_check', 'c', '-', 'CHECK (balance >= 0)']], 'indexes': [],
            'catalog': {'functions': [{'owner': 'quillmd_owner', 'name': 'guard()', 'acl': '{quillmd_owner=X/quillmd_owner}',
                'security_definer': False, 'config': None, 'definition': 'original guard definition'}], 'triggers': []},
            'columns': {name: ['id'] for name in tables}, 'rows': {name: {'rows': 1, 'sha256': p.sha(name.encode())} for name in tables},
            'storage': {'files': {'exports/historical.docx': {'sha256': p.sha(b'historical bytes'), 'size': 16}}, 'mail': {}},
            'unit_files': {'private-doctor': 'unchanged'}, 'shared_configs': {'maintenance': 'unchanged'},
            'protected': 'unchanged unrelated tenant identities', 'operations': {'policy': 'expired, unchanged'},
            'unresolved_jobs': 0, 'held_reservations': 0}

    def test_absent_different_or_incomplete_catalog_refuses_before_any_backend_action(self):
        backend = self.backend()
        for raw in (b'', b'{}', json.dumps({**self.contract, 'before': {'tables': self.before['tables']}}).encode()):
            with self.subTest(raw=raw[:20]), self.assertRaises((ValueError, KeyError)):
                a.activate(backend, self.declaration, self.schema_bytes, self.sources, self.evidence, raw)
            self.assertEqual(backend.events, [])
        changed = copy.deepcopy(self.contract); changed['source_sha256']['rebuild/core/models.py'] = '0' * 64
        with self.assertRaises(ValueError): a.validate_catalog_contract(json.dumps(changed).encode(), self.sources, self.schema_bytes)

    def test_unmet_word_generation_or_citation_gates_cannot_reach_credentials_or_services(self):
        for key, change in (('word', {'overall_pass': 53}), ('generation', {'returned_model': 'claude-sonnet-4-6'}),
                            ('source_refutation', {'word_unsafe': 1})):
            evidence = copy.deepcopy(self.evidence); evidence[key].update(change)
            backend = self.backend()
            with self.subTest(key=key), self.assertRaises(ValueError):
                a.activate(backend, self.declaration, self.schema_bytes, self.sources, evidence, self.catalog_bytes)
            self.assertEqual(backend.events, [])

    def migration_plan(self, applied):
        return '\n'.join('[%s] core.%s' % ('X' if applied or name in self.schema['baseline_prefix_sha256'] else ' ', name)
                         for name in {**self.schema['baseline_prefix_sha256'], **self.schema['forward_migration_sha256']})

    def test_exact_forward_graph_and_no_extra_pending_migration(self):
        a.verify_migration_plan(self.migration_plan(False), self.schema, applied=False)
        a.verify_migration_plan(self.migration_plan(True), self.schema, applied=True)
        for raw, applied in ((self.migration_plan(False) + '\n[ ] auth.unreviewed', False),
                             (self.migration_plan(False).replace('[ ] core.0037_', '[X] core.0037_'), False),
                             (self.migration_plan(False), True)):
            with self.subTest(raw=raw[-80:]), self.assertRaises(ValueError):
                a.verify_migration_plan(raw, self.schema, applied=applied)

    def test_every_old_row_column_file_guard_privilege_and_noncore_addition_remains_bound(self):
        a.validate_transition(self.before, self.after, self.schema, self.contract, owner='quillmd_owner')
        changes = [lambda x: x['old_rows']['core_wallet'].update(sha256=p.sha(b'wrong balance')),
                   lambda x: x['old_columns']['core_job'].append('dropped historical value'),
                   lambda x: x['storage']['files']['exports/historical.docx'].update(sha256=p.sha(b'changed bytes')),
                   lambda x: x['catalog']['functions'][0].update(definition='weakened guard'),
                   lambda x: x['catalog']['functions'][0].update(owner='intruder'),
                   lambda x: x['catalog']['functions'][0].update(acl='{public=X/quillmd_owner}'),
                   lambda x: x['new_noncore_rows']['auth_permission'].append(['core','encounter','view_encounter','extra']),
                   lambda x: x['new_core_rows']['core_retentionhold'].update(rows=1),
                   lambda x: x.update(unresolved_jobs=1), lambda x: x.update(held_reservations=1),
                   lambda x: x.update(protected='changed tenant')]
        for change in changes:
            before, after = copy.deepcopy(self.before), copy.deepcopy(self.after); change(after)
            with self.subTest(change=change), self.assertRaises(ValueError):
                a.validate_transition(before, after, self.schema, self.contract, owner='quillmd_owner')

    def backend(self, fail=None):
        case = self
        class Backend:
            schema_owner = 'quillmd_owner'
            def __init__(self): self.events, self.applied = [], False
            def event(self, name):
                self.events.append(name)
                if name == fail: raise RuntimeError('retained simulated original failure')
            def validate_live(self, *args): self.event('live source/PR/CI/state validation')
            def create_unused_evidence(self, *args): self.event('unused evidence')
            def checkpoint(self, result): self.event('checkpoint:' + result.get('stage', 'unknown'))
            def exclude_publication(self):
                backend = self
                class Exclusion:
                    def __enter__(self): backend.event('acquire participant exclusion')
                    def __exit__(self, *args): backend.event('restore exact prior timers')
                return Exclusion()
            def stop(self): self.event('stop only private doctor/admin/worker')
            def assert_stopped(self): self.event('prove stopped')
            def snapshot(self, before=None):
                self.event('stopped complete inventory')
                return copy.deepcopy(case.after if before is not None else case.before)
            def retain_recovery(self, before): self.event('retain source/env/static/encrypted current capture')
            def advance_source(self, target): self.event('ff exact source')
            def migration_plan(self): return case.migration_plan(self.applied)
            def migrate(self, leaf): self.event('migrate only reviewed leaf'); self.applied = True
            def retain_transition(self, *args): self.event('retain both original inventories')
            def install_assets_and_environment(self): self.event('reviewed static/environment delta')
            def verify_installed_stopped(self, *args): self.event('old rows/files checked again before restart')
            def start_and_verify(self, *args): self.event('bounded structural doctor/admin/worker verification')
            def verify_publication_restored(self): self.event('new unit and scheduled timer invocation proof')
        return Backend()

    def test_success_and_failure_have_real_phase_order_and_no_automatic_restore(self):
        backend = self.backend()
        outcome = a.activate(backend, self.declaration, self.schema_bytes, self.sources, self.evidence, self.catalog_bytes)
        self.assertTrue(outcome['complete']); self.assertEqual(outcome['provider_calls'], 0)
        self.assertLess(backend.events.index('retain source/env/static/encrypted current capture'), backend.events.index('ff exact source'))
        self.assertLess(backend.events.index('old rows/files checked again before restart'),
                        backend.events.index('bounded structural doctor/admin/worker verification'))
        backend = self.backend(fail='migrate only reviewed leaf')
        with self.assertRaises(RuntimeError):
            a.activate(backend, self.declaration, self.schema_bytes, self.sources, self.evidence, self.catalog_bytes)
        self.assertEqual(backend.events.count('stop only private doctor/admin/worker'), 2)
        self.assertNotIn('reviewed static/environment delta', backend.events)
        self.assertNotIn('bounded structural doctor/admin/worker verification', backend.events)
        self.assertEqual(backend.events.count('ff exact source'), 1)

    def test_participant_recovery_is_fixed_scoped_and_retains_managed_helper_lifecycle(self):
        record = {'target': 'a'*40, 'pid': 123, 'start': '456', 'prior_active': list(participants.TIMERS)}
        participants.validate(record)
        for bad in (list(participants.PRIVATE_UNITS), ['unrelated.service'], [participants.TIMERS[0]] * 2):
            with self.subTest(bad=bad), self.assertRaises(ValueError): participants.validate({**record, 'prior_active': bad})
        directory = participants.STATE_ROOT / record['target']
        with patch.object(participants.managed_helper, 'run_helper') as runner:
            participants.action('stop', participants.TIMERS, directory=directory)
            args, kwargs = runner.call_args
            self.assertIn('--network=none', args[0]); self.assertIn('--log-driver=none', args[0])
            self.assertIn('type=bind,src=/,dst=/host,readonly', args[0]); self.assertEqual(kwargs['timeout'], 200)
            for timer in participants.TIMERS: self.assertIn(timer.encode(), kwargs['input'])
            self.assertNotIn(b'email', kwargs['input'])
            with self.assertRaises(ValueError): participants.action('start', ('unrelated.service',), directory=directory)
            self.assertEqual(runner.call_count, 1)

    def test_catalog_identifier_and_stream_fingerprints_preserve_exact_bytes(self):
        for bad in ('core_job;DROP TABLE core_job', '../core_job', '"core_job"', ''):
            with self.subTest(bad=bad), self.assertRaises(ValueError): catalog.identifier(bad)
        self.assertEqual(catalog.stream_hash([b'row1\nro', b'w2\n']), {'rows': 2, 'sha256': p.sha(b'row1\nrow2\n')})

    def test_prepared_declaration_refuses_before_any_installed_or_external_access(self):
        spec = importlib.util.spec_from_file_location('v1_install_cli_contract', ROOT / 'scripts/activate-v1-private-install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        prepared = json.dumps({'format': 'quillmd-v1-private-install-declaration-v1', 'status': 'prepared', 'baseline': p.BASELINE}).encode()
        with patch.object(module, 'git', side_effect=['a'*40, '']), patch.object(module, 'source_file', return_value=prepared):
            with self.assertRaisesRegex(ValueError, 'prepared, not frozen'):
                module.validate_source('a'*40, 'docs/foundation/mutations/prepared.json')

    def test_normal_merged_declaration_uses_ancestor_exact_blob_without_an_impossible_self_sha(self):
        spec = importlib.util.spec_from_file_location('v1_install_normal_declaration', ROOT / 'scripts/activate-v1-private-install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        relative = 'docs/foundation/mutations/prospective.json'
        with patch.dict(os.environ, {'RULED_MUTATION_DECLARATION': str(ROOT / relative),
                                    'RULED_MUTATION_DECL_COMMIT': 'b'*40}), \
                patch.object(module.subprocess, 'run') as ancestry, \
                patch.object(module.subprocess, 'check_output', return_value=b'exact frozen declaration'), \
                patch.object(module, 'source_file', return_value=b'exact frozen declaration'):
            module.normal_declaration('a'*40, relative)
            self.assertEqual(ancestry.call_args.args[0], ['git', 'merge-base', '--is-ancestor', 'b'*40, 'a'*40])
            with patch.object(module, 'source_file', return_value=b'changed declaration'), self.assertRaises(ValueError):
                module.normal_declaration('a'*40, relative)
