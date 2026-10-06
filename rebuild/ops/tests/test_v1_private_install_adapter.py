"""Provider/DB/host-free fault controls for the new preserving installation door."""
import copy
from contextlib import ExitStack, nullcontext
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import v1_private_install_adapter as a
from ops import v1_private_install_preparation as p
from ops import v1_install_catalog as catalog
from ops import v1_install_participants as participants
from ops import v1_private_install_runtime as runtime

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
                             (self.migration_plan(False).replace('[ ] core.0038_', '[X] core.0038_'), False),
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
            def __init__(self): self.events, self.applied, self.errors, self.checkpoints = [], False, [], []
            def event(self, name):
                self.events.append(name)
                if name == fail: raise RuntimeError('retained simulated original failure')
            def validate_live(self, *args): self.event('live source/PR/CI/state validation')
            def create_unused_evidence(self, *args): self.event('unused evidence')
            def checkpoint(self, result):
                self.checkpoints.append(copy.deepcopy(result))
                self.event('checkpoint:' + result.get('stage', 'unknown'))
            def record_failure(self, error, scope):
                self.errors.append((scope, error))
                return {'kind': type(error).__name__, 'sealed_original_sha256': p.sha(str(error).encode())}
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
        self.assertEqual(str(backend.errors[0][1]), 'retained simulated original failure')
        self.assertEqual(backend.checkpoints[-1]['failure_evidence']['sealed_original_sha256'],
                         p.sha(b'retained simulated original failure'))
        self.assertFalse(backend.checkpoints[-1]['complete'])

    def runtime_backend(self, directory):
        backend = object.__new__(runtime.Backend)
        backend.state = Path(directory)
        backend.declaration = {'target': 'a' * 40}
        backend.source = ROOT
        backend.failure = 0
        from ops.backup_restore import write_private
        backend.identity = SimpleNamespace(private_write=lambda path, value:
            write_private(path, json.dumps(value, sort_keys=True).encode()))
        return backend

    def test_protected_original_failure_retains_cause_exit_stdout_stderr_and_seals_summary(self):
        credential = 'synthetic-test-secret-never-print'
        with tempfile.TemporaryDirectory() as directory:
            backend = self.runtime_backend(directory)
            try:
                raise subprocess.CalledProcessError(37, ['fixed-migrate', credential],
                    output=b'first retained migration step\n', stderr=(credential + '\noriginal migration refusal\n').encode())
            except subprocess.CalledProcessError as error:
                proof = backend.record_failure(error, 'activation')
            self.assertEqual(proof['returncode'], 37)
            self.assertNotIn(credential, json.dumps(proof))
            for name, expected in (('stdout', b'first retained migration step\n'),
                                   ('stderr', (credential + '\noriginal migration refusal\n').encode())):
                record = proof['material'][name]
                self.assertEqual((Path(directory) / record['relative']).read_bytes(), expected)
                self.assertEqual(record['sha256'], p.sha(expected)); self.assertFalse(record['truncated'])
                self.assertEqual((Path(directory) / record['relative']).stat().st_mode & 0o777, 0o600)
            trace = (Path(directory) / proof['material']['traceback']['relative']).read_text()
            self.assertIn('CalledProcessError', trace); self.assertIn('37', trace)
            self.assertIn(credential, trace)
            raw = b'large retained stderr' * 30
            with patch.object(runtime, 'FAILURE_MATERIAL_LIMIT', 17):
                oversized = backend.record_failure(subprocess.CalledProcessError(9, ['fixed'], stderr=raw), 'failure_stop')
            record = oversized['material']['stderr']
            self.assertTrue(record['truncated']); self.assertEqual(record['bytes'], len(raw))
            self.assertEqual(record['sha256'], p.sha(raw)); self.assertEqual(record['retained_bytes'], 17)

    def test_actual_migration_failure_output_is_captured_instead_of_discarded(self):
        backend = object.__new__(runtime.Backend)
        backend.driver = SimpleNamespace(b=SimpleNamespace(management=lambda *args: ['fixed-managed', *args]))
        with patch.object(runtime.subprocess, 'run', side_effect=subprocess.CalledProcessError(
                11, ['fixed-managed'], output=b'original stdout', stderr=b'original stderr')) as runner:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                backend.migrate(p.LEAF)
        self.assertEqual(caught.exception.returncode, 11)
        self.assertEqual(caught.exception.stdout, b'original stdout')
        self.assertEqual(caught.exception.stderr, b'original stderr')
        self.assertEqual(runner.call_args.kwargs['stdout'], subprocess.PIPE)
        self.assertEqual(runner.call_args.kwargs['stderr'], subprocess.PIPE)

    def test_activation_generic_error_keeps_original_child_exit_and_secondary_stop_failure_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = self.backend()
            recorder = self.runtime_backend(directory)
            backend.record_failure = recorder.record_failure
            def migrate(leaf):
                raise subprocess.CalledProcessError(37, ['fixed-managed-migrate'],
                    output=b'original migration stdout\n', stderr=b'retained simulated original failure\n')
            backend.migrate = migrate
            original_stop = backend.stop
            stop_count = 0
            def stop():
                nonlocal stop_count
                stop_count += 1
                if stop_count == 2:
                    raise subprocess.CalledProcessError(73, ['fixed-stop'], stderr=b'separate original stop failure\n')
                original_stop()
            backend.stop = stop
            with self.assertRaisesRegex(RuntimeError, 'inspect retained original evidence'):
                a.activate(backend, self.declaration, self.schema_bytes, self.sources, self.evidence, self.catalog_bytes)
            final = backend.checkpoints[-1]
            self.assertFalse(final['complete']); self.assertFalse(final['failure_services_stopped'])
            self.assertEqual(final['failure_evidence']['returncode'], 37)
            self.assertEqual(final['stop_failure_evidence']['returncode'], 73)
            first = final['failure_evidence']['material']['stderr']['relative']
            second = final['stop_failure_evidence']['material']['stderr']['relative']
            self.assertNotEqual(first, second)
            self.assertEqual((Path(directory) / first).read_bytes(), b'retained simulated original failure\n')
            self.assertEqual((Path(directory) / second).read_bytes(), b'separate original stop failure\n')

    def exclusion_case(self, *, fault=None, publisher_active=True, restoration_fault=False, body_error=False):
        """Exercise the actual runtime with inert transport/spawn/lock methods."""
        from ops import activation_exclusion as exclusion
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        backend = self.runtime_backend(directory.name)
        prior = {participants.TIMERS[0]: 'active', participants.TIMERS[1]: 'inactive', participants.TIMERS[2]: 'active'}
        states, actions, saved = dict(prior), [], []
        publisher = {'ActiveState': 'active' if publisher_active else 'inactive', 'UnitFileState': 'enabled'}
        backend.driver = SimpleNamespace(b=SimpleNamespace(output=lambda command: states[command[2]]))
        def unit_state(*args): return dict(publisher)
        def systemctl(operation, timer):
            actions.append((operation, timer))
            publisher['ActiveState'] = 'active' if operation == 'start' else 'inactive'
            if fault == 'publisher_stop' and operation == 'stop':
                raise RuntimeError('retained original publisher partial stop')
        backend.lineage = SimpleNamespace(unit_state=unit_state, systemctl=systemctl,
            PUBLISHER_TIMER='quillmd-fresh-operations-publisher.timer')
        backend.stop = lambda: actions.append(('stop', 'fixed-private-surfaces'))
        backend.assert_stopped = lambda: None
        original_write = backend.identity.private_write
        def writer(path, value):
            saved.append((path.name, copy.deepcopy(value)))
            original_write(path, value)
            if fault == 'pause_write' and path.name == 'timer-pause.json':
                raise RuntimeError('retained original partial marker write')
        backend.identity.private_write = writer
        def action(operation, units, **kwargs):
            actions.append((operation, tuple(units)))
            for timer in units:
                if restoration_fault and operation == 'start' and timer == participants.TIMERS[0]:
                    raise RuntimeError('retained original first timer restoration refusal')
                states[timer] = 'active' if operation == 'start' else 'inactive'
                if fault == 'timers_stop' and len(units) == 3:
                    raise RuntimeError('retained original partial timer stop')
        watchdog = SimpleNamespace(wait=lambda **kwargs: None)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {'ops.install_operations_publisher': SimpleNamespace(
                scope=lambda: None, published_row=lambda: {'revision': 1})}))
            stack.enter_context(patch.object(runtime, 'PARTICIPANT_LOCKS', ()))
            stack.enter_context(patch.object(exclusion, 'bind_runtime'))
            stack.enter_context(patch.object(exclusion, 'drain_publisher'))
            stack.enter_context(patch.object(exclusion, 'hold', return_value=nullcontext()))
            stack.enter_context(patch.object(exclusion, 'note_timer_paused', side_effect=(
                RuntimeError('retained original publisher marker failure') if fault == 'publisher_marker' else None)))
            stack.enter_context(patch.object(exclusion, 'clear_timer_pause'))
            stack.enter_context(patch.object(exclusion, 'spawn_bootstrap_watchdog', side_effect=(
                RuntimeError('retained original publisher spawn failure') if fault == 'publisher_spawn' else None),
                return_value=watchdog))
            stack.enter_context(patch.object(participants, 'start_identity', return_value='123'))
            stack.enter_context(patch.object(participants, 'spawn', side_effect=(
                RuntimeError('retained original participant spawn failure') if fault == 'timer_spawn' else None),
                return_value=watchdog))
            stack.enter_context(patch.object(participants, 'action', side_effect=action))
            error = None
            try:
                with backend.exclude_publication():
                    actions.append(('entered', 'body'))
                    if body_error:
                        raise RuntimeError('retained original body migration refusal')
            except BaseException as caught:
                error = caught
        return {'error': error, 'prior': prior, 'states': states, 'actions': actions,
                'publisher': publisher, 'saved': saved, 'directory': Path(directory.name)}

    def test_inactive_publisher_refuses_before_any_pause_and_leaves_exact_prior_timers(self):
        result = self.exclusion_case(publisher_active=False)
        self.assertIsInstance(result['error'], ValueError)
        self.assertEqual(result['actions'], []); self.assertEqual(result['saved'], [])
        self.assertEqual(result['states'], result['prior'])

    def test_every_partial_pause_failure_restores_prior_states_synchronously_while_owner_alive(self):
        for fault in ('pause_write', 'timer_spawn', 'timers_stop', 'publisher_marker', 'publisher_spawn', 'publisher_stop'):
            with self.subTest(fault=fault):
                result = self.exclusion_case(fault=fault)
                self.assertIsInstance(result['error'], RuntimeError)
                self.assertIn('retained original', str(result['error']))
                self.assertEqual(result['states'], result['prior'])
                self.assertEqual(result['publisher']['ActiveState'], 'active')
                self.assertIn('timers-restored.json', [name for name, _ in result['saved']])
                self.assertNotIn(('entered', 'body'), result['actions'])

    def test_restore_failure_attempts_other_timers_preserves_first_cause_and_never_claims_complete(self):
        result = self.exclusion_case(restoration_fault=True, body_error=True)
        self.assertEqual(str(result['error']), 'retained original body migration refusal')
        self.assertIn(('start', (participants.TIMERS[2],)), result['actions'])
        self.assertEqual(result['states'][participants.TIMERS[2]], 'active')
        self.assertEqual(result['states'][participants.TIMERS[1]], 'inactive')
        self.assertNotIn('timers-restored.json', [name for name, _ in result['saved']])
        self.assertIn('timer-restoration-failures.json', [name for name, _ in result['saved']])
        traces = [path.read_text() for path in result['directory'].glob('*traceback.bin')]
        self.assertTrue(any('retained original body migration refusal' in raw for raw in traces))
        self.assertTrue(any('retained original first timer restoration refusal' in raw for raw in traces))

    def test_success_restores_prior_states_and_failure_of_restoration_cannot_be_green(self):
        result = self.exclusion_case()
        self.assertIsNone(result['error']); self.assertEqual(result['states'], result['prior'])
        self.assertIn('timers-restored.json', [name for name, _ in result['saved']])
        result = self.exclusion_case(restoration_fault=True)
        self.assertIsInstance(result['error'], ValueError)
        self.assertNotIn('timers-restored.json', [name for name, _ in result['saved']])

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
        # The normal door is intentionally host-scoped. Supply its canonical
        # retained-worktree identity even on GitHub's /home/runner source copy;
        # the source reader remains mocked, and no installed state is accessed.
        retained = module.ROOT / '.worktrees/prepared-cli-contract'
        with patch.object(module, 'SOURCE', retained), \
                patch.object(module, 'git', side_effect=['a'*40, '']) as git, \
                patch.object(module, 'source_file', return_value=prepared) as source, \
                patch.object(module, 'catalog_file') as catalog_reader, \
                patch.object(module, 'live_source') as installed_reader:
            with self.assertRaisesRegex(ValueError, 'prepared, not frozen'):
                module.validate_source('a'*40, 'docs/foundation/mutations/prepared.json')
            self.assertEqual(git.call_count, 2)
            source.assert_called_once_with('docs/foundation/mutations/prepared.json', 'a'*40)
            catalog_reader.assert_not_called(); installed_reader.assert_not_called()

    def test_ci_or_unretained_source_and_short_revision_refuse_before_any_source_or_installed_reader(self):
        spec = importlib.util.spec_from_file_location('v1_install_unretained_source', ROOT / 'scripts/activate-v1-private-install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        cases = [(Path('/home/runner/work/MedDoc/MedDoc'), 'a'*40),
                 (module.ROOT / 'rebuild', 'a'*40),
                 (module.ROOT / '.worktrees/prepared-cli-contract', 'a'*8)]
        for source_path, target in cases:
            with self.subTest(source=str(source_path), target=target), \
                    patch.object(module, 'SOURCE', source_path), patch.object(module, 'git') as git, \
                    patch.object(module, 'source_file') as source, patch.object(module, 'catalog_file') as catalog_reader, \
                    patch.object(module, 'live_source') as installed_reader, \
                    self.assertRaisesRegex(ValueError, 'full revision and its retained target worktree'):
                module.validate_source(target, 'docs/foundation/mutations/prepared.json')
            git.assert_not_called(); source.assert_not_called()
            catalog_reader.assert_not_called(); installed_reader.assert_not_called()

    def test_catalog_receipt_is_hash_named_private_evidence_and_cannot_read_an_arbitrary_secret_path(self):
        spec = importlib.util.spec_from_file_location('v1_install_catalog_receipt', ROOT / 'scripts/activate-v1-private-install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        from ops import backup_restore
        identity = {'sha256': p.sha(self.catalog_bytes)}
        with patch.object(backup_restore, 'read_private', return_value=self.catalog_bytes) as reader:
            self.assertEqual(module.catalog_file(identity), self.catalog_bytes)
            self.assertEqual(reader.call_args.args[0], module.CATALOG_EVIDENCE / (identity['sha256'] + '.json'))
            for record in (None, {}, {'sha256': 'a' * 40},
                           {**identity, 'path': '/opt/meddoc-pro/rebuild/.env'}):
                with self.subTest(record=record), self.assertRaises(ValueError): module.catalog_file(record)
            self.assertEqual(reader.call_count, 1)
            with patch.object(backup_restore, 'read_private', return_value=b'changed retained evidence'):
                with self.assertRaises(ValueError): module.catalog_file(identity)

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
