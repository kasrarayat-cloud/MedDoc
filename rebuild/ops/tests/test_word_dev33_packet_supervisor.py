"""Pure mocked envelope controls; no database/renderer/corpus execution."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
LITERAL = ROOT / 'rebuild/ops/fixtures/word_dev33_packet_supervisor.source'
supervisor = types.ModuleType('dev33_supervisor_test_literal')
supervisor.__file__ = str(LITERAL)
exec(compile(LITERAL.read_bytes(), str(LITERAL), 'exec'), supervisor.__dict__)


class Envelope(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.driver_dir = self.base / 'drivers'
        self.driver_dir.mkdir()
        self.driver = self.driver_dir / 'run_dev_application_gate_v2.py'
        self.driver.write_text('reviewed test-only mocked driver bytes\n')
        self.helper_hash = supervisor.digest(self.driver)
        self.source = self.base / 'source'; self.source.mkdir()
        self.source_commit = 'a' * 40
        self.inventory = {'rebuild/core/views.py': 'b' * 64}
        self.seal = {'source_commit': self.source_commit}
        self.packet = {'packet': 'P02', 'identities': ['D03', 'D04', 'D05']}
        self.args = types.SimpleNamespace(source=self.source, seal=self.base / 'seal.json',
            seal_sha256='c' * 64, prepared_plan=self.base / 'plan.json', packet='P02', output=self.base / 'out')
        self.database = 'quillmd_qa_sol_ops_dev3372345'
        self.batch = self.driver_dir / ('dev-application-' + self.source_commit[:12] + '-123')
        self.child = Mock(pid=72345, returncode=None)
        self.child.poll.side_effect = lambda: self.child.returncode
        self.driver_module = types.SimpleNamespace(database_presence=Mock(side_effect=self.database_receipt))
        self.adapter = types.SimpleNamespace(verified_source=Mock(return_value=self.inventory))
        self.pid = {'pid': 72345, 'ppid': 1, 'pgid': 72345, 'start_ticks': 999, 'state': 'S'}
        self.returncode = 0
        self.make_batch = True
        self.child.wait.side_effect = self.finish
        supervisor.ACTIVE_OUTPUT = None

    def database_receipt(self, source, name):
        return {'verified': True, 'requested_database': name, 'checked_names': [name, 'test_' + name],
                'present': [], 'all_absent': True, 'provider_calls': 0}

    def finish(self, timeout=None):
        if self.make_batch:
            self.batch.mkdir(exist_ok=True)
            supervisor.retain(self.batch / 'plan.json', {'database_name': self.database,
                'records': [{'development_id': i} for i in self.packet['identities']]})
            supervisor.retain(self.batch / 'partial-summary.json', {'actual_test_exit': self.returncode,
                'results': {i: {'automatic_success': self.returncode == 0} for i in self.packet['identities']}})
            (self.batch / 'retained-original-failure.log').write_text('unchanged original evidence\n')
        self.child.returncode = self.returncode
        return self.returncode

    def run_envelope(self, **overrides):
        configured = (self.source, self.adapter, {}, self.seal, self.packet, self.driver,
                      {str(self.driver): self.helper_hash}, self.inventory)
        patches = {'configuration': Mock(return_value=configured), 'OWNED': self.base,
                   'load_literal': Mock(return_value=self.driver_module), 'layout_containers': Mock(return_value=[]),
                   'pid_record': Mock(side_effect=lambda pid: self.pid if self.child.returncode is None else None),
                   'record_descendants': Mock(), 'same_process': Mock(side_effect=lambda record: self.child.returncode is None)}
        patches.update(overrides)
        with contextlib.ExitStack() as stack:
            for name, value in patches.items():
                stack.enter_context(patch.object(supervisor, name, value))
            self.popen = stack.enter_context(patch.object(supervisor.subprocess, 'Popen', return_value=self.child))
            stack.enter_context(patch.object(supervisor.os, 'write', return_value=1))
            self.kill = stack.enter_context(patch.object(supervisor.os, 'kill'))
            self.killpg = stack.enter_context(patch.object(supervisor.os, 'killpg'))
            with contextlib.redirect_stdout(io.StringIO()):
                return supervisor.execute(self.args)

    def receipt(self):
        return json.loads((self.args.output / 'outer-result.json').read_text())

    def test_default_is_prepared_without_reads_processes_or_database(self):
        with patch.object(supervisor, 'execute') as execute, patch.object(supervisor, 'digest') as digest:
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(supervisor.main([]), 0)
        execute.assert_not_called(); digest.assert_not_called()
        result = json.loads(stream.getvalue())
        self.assertEqual(result['database_connections'], 0)
        self.assertEqual(result['children_started'], 0)
        self.assertFalse(result['gate_pass'])

    def test_actual_child_and_independent_teardown_and_every_raw_file_are_bound(self):
        self.assertEqual(self.run_envelope(), 0)
        receipt = self.receipt()
        self.assertEqual(receipt['actual_outer_child_exit'], 0)
        self.assertTrue(receipt['teardown_verified'])
        self.assertFalse(receipt['gate_pass'])
        batch_receipt = json.loads((self.batch / 'outer-result.json').read_text())
        self.assertEqual(receipt['retained_outer_receipt_sha256'], supervisor.digest(self.batch / 'outer-result.json'))
        manifest = json.loads((self.batch / 'raw-evidence-manifest.json').read_text())
        self.assertEqual(batch_receipt['raw_evidence_manifest_sha256'], supervisor.digest(self.batch / 'raw-evidence-manifest.json'))
        for name, value in manifest['files'].items():
            self.assertEqual(supervisor.digest(self.batch / name), value)
        self.assertIn('retained-original-failure.log', manifest['files'])
        self.assertIn('independent-teardown.json', manifest['files'])
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.driver_module.database_presence.call_count, 2)
        self.assertEqual(self.popen.call_args.kwargs['pass_fds'].__len__(), 1)

    def test_product_failure_is_preserved_with_healthy_teardown(self):
        self.returncode = 1
        self.assertEqual(self.run_envelope(), 1)
        self.assertEqual(self.receipt()['actual_outer_child_exit'], 1)
        self.assertTrue(self.receipt()['teardown_verified'])
        self.assertFalse(self.receipt()['gate_pass'])

    def test_child_exception_preserves_original_traceback_no_success(self):
        self.child.wait.side_effect = RuntimeError('retained concrete original supervisor failure')
        self.make_batch = False
        def stop(child, known):
            child.returncode = -15
            return [{'group': child.pid, 'signal': 15}]
        self.assertEqual(self.run_envelope(stop_owned=stop), 2)
        failure = self.args.output / 'original-supervisor-failure.txt'
        self.assertIn('retained concrete original supervisor failure', failure.read_text())
        self.assertEqual(self.receipt()['original_failure_sha256'], supervisor.digest(failure))
        self.assertEqual(failure.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.receipt()['actual_outer_child_exit'], -15)
        self.assertFalse(self.receipt()['teardown_verified'])

    def test_missing_result_directory_is_incomplete_not_false_product_pass(self):
        self.make_batch = False
        self.assertEqual(self.run_envelope(), 2)
        self.assertIsNone(self.receipt()['batch'])
        self.assertFalse(self.receipt()['gate_pass'])

    def test_actual_outer_deadline_is_retained_and_bounded_reap_used(self):
        self.make_batch = False
        stop = Mock(side_effect=lambda child, known: setattr(child, 'returncode', -2) or [])
        with patch.object(supervisor.time, 'monotonic', side_effect=[0, 1261, 1261]):
            self.assertEqual(self.run_envelope(stop_owned=stop), 2)
        stop.assert_called_once()
        self.child.wait.assert_not_called()
        self.assertTrue(self.receipt()['timed_out'])
        self.assertEqual(self.receipt()['actual_outer_child_exit'], -2)
        self.assertFalse(self.receipt()['teardown_verified'])

    def test_surviving_recorded_pid_blocks_healthy_result(self):
        def stop(child, known):
            return []
        self.assertEqual(self.run_envelope(same_process=Mock(return_value=True), stop_owned=stop), 2)
        self.assertFalse(self.receipt()['teardown_verified'])
        self.assertFalse(json.loads((self.args.output / 'independent-teardown.json').read_text())['all_recorded_pids_absent'])

    def test_database_remaining_blocks_healthy_result(self):
        def catalog(source, name):
            receipt = self.database_receipt(source, name)
            if self.child.returncode is not None:
                receipt.update(all_absent=False, present=['test_' + name])
            return receipt
        self.driver_module.database_presence.side_effect = catalog
        self.assertEqual(self.run_envelope(), 2)
        self.assertFalse(self.receipt()['teardown_verified'])

    def test_containers_remaining_block_success_without_deleting_them(self):
        self.assertEqual(self.run_envelope(layout_containers=Mock(side_effect=[[], ['owned-container\tquillmd-layout-id']])), 2)
        self.assertFalse(self.receipt()['teardown_verified'])
        self.kill.assert_not_called(); self.killpg.assert_not_called()

    def test_foreign_prior_layout_prevents_any_child(self):
        with self.assertRaisesRegex(ValueError, 'Another layout renderer'):
            self.run_envelope(layout_containers=Mock(return_value=['prior\tquillmd-layout-old']))
        self.popen.assert_not_called()

    def test_prior_database_is_not_released_and_original_refusal_retained(self):
        self.driver_module.database_presence.side_effect = lambda source, name: {
            **self.database_receipt(source, name), 'all_absent': False, 'present': [name]}
        self.make_batch = False
        def stop(child, known):
            child.returncode = -2
            return []
        self.assertEqual(self.run_envelope(stop_owned=stop), 2)
        self.assertIn('Task database/socket already exists', (self.args.output / 'original-supervisor-failure.txt').read_text())
        self.assertEqual(self.receipt()['actual_outer_child_exit'], -2)

    def test_changed_source_after_child_blocks_success(self):
        self.adapter.verified_source.return_value = {'rebuild/core/views.py': 'd' * 64}
        self.assertEqual(self.run_envelope(), 2)
        self.assertFalse(self.receipt()['source_unchanged'])

    def test_foreign_packet_output_is_preserved_and_refused(self):
        original_finish = self.finish
        def foreign(timeout=None):
            outcome = original_finish(timeout)
            plan = json.loads((self.batch / 'plan.json').read_text())
            plan['records'][0]['development_id'] = 'D40'
            (self.batch / 'plan.json').write_text(json.dumps(plan))
            return outcome
        self.child.wait.side_effect = foreign
        self.assertEqual(self.run_envelope(), 2)
        self.assertIn('Driver output identity differs', (self.args.output / 'original-finalization-failure.txt').read_text())
        self.assertTrue((self.batch / 'retained-original-failure.log').exists())
        self.assertFalse((self.batch / 'outer-result.json').exists())

    def test_duplicate_new_output_directories_are_retained_as_incomplete(self):
        original_finish = self.finish
        extra = self.driver_dir / ('dev-application-' + self.source_commit[:12] + '-999')
        def duplicated(timeout=None):
            extra.mkdir()
            return original_finish(timeout)
        self.child.wait.side_effect = duplicated
        self.assertEqual(self.run_envelope(), 2)
        self.assertEqual(set(self.receipt()['new_output_candidates']), {str(extra), str(self.batch)})
        self.assertTrue(self.batch.is_dir()); self.assertTrue(extra.is_dir())
        self.assertFalse((self.batch / 'outer-result.json').exists())

    def test_foreign_symlink_output_is_refused_before_evidence_write(self):
        foreign = self.base / 'foreign'; foreign.mkdir()
        sentinel = foreign / 'sentinel'; sentinel.write_text('retained foreign original')
        def linked(timeout=None):
            self.batch.symlink_to(foreign, target_is_directory=True)
            self.child.returncode = 0
            return 0
        self.child.wait.side_effect = linked
        self.assertEqual(self.run_envelope(), 2)
        self.assertIn('not the owned normal driver directory', (self.args.output / 'original-finalization-failure.txt').read_text())
        self.assertEqual(list(foreign.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), 'retained foreign original')

    def test_existing_envelope_is_never_overwritten(self):
        self.assertEqual(self.run_envelope(), 0)
        prior = (self.batch / 'outer-result.json').read_bytes()
        with self.assertRaises(ValueError):
            supervisor.capture_raw(self.batch, self.source_commit)
        self.assertEqual((self.batch / 'outer-result.json').read_bytes(), prior)

    def test_raw_symlink_is_refused_without_removing_original(self):
        batch = self.base / 'raw'; batch.mkdir()
        (batch / 'outside-link').symlink_to(self.driver)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            supervisor.capture_raw(batch, self.source_commit)
        self.assertTrue(self.driver.is_file())
        self.assertTrue((batch / 'outside-link').is_symlink())

    def test_dependency_inventory_binds_code_native_library_and_metadata(self):
        deps = self.base / 'deps'; deps.mkdir()
        for name, text in [('module.py', 'code'), ('libpdfium.so', 'native'), ('version.json', 'metadata')]:
            (deps / name).write_text(text)
        (deps / '__pycache__').mkdir()
        (deps / '__pycache__' / 'module.pyc').write_bytes(b'non-source cache')
        expected = {name: supervisor.digest(deps / name) for name in ('module.py', 'libpdfium.so', 'version.json')}
        self.assertEqual(supervisor.dependency_inventory(deps), expected)
        (deps / 'new_runtime.py').write_text('new transitive code')
        self.assertNotEqual(supervisor.dependency_inventory(deps), expected)

    def test_checker_dependency_symlink_is_refused(self):
        deps = self.base / 'deps'; deps.mkdir()
        (deps / 'module.py').symlink_to(self.driver)
        with self.assertRaisesRegex(ValueError, 'dependency contains a symlink'):
            supervisor.dependency_inventory(deps)

    def test_configuration_refuses_missing_inputs_before_catalog_or_process(self):
        args = types.SimpleNamespace(source=None, seal=None, seal_sha256=None, prepared_plan=None,
                                     packet=None, output=None)
        with patch.object(supervisor.sys, 'executable', supervisor.PY), patch.object(supervisor, 'load_literal') as load:
            with self.assertRaisesRegex(ValueError, 'exact source/seal/packet'):
                supervisor.configuration(args)
        load.assert_not_called()

    def test_reviewed_supervisor_can_be_bound_separately_from_runtime_commit(self):
        supervisor.validate_supervisor_seal({'root_exclusive_db_renderer_grant': True,
                                            'supervisor_sha256': supervisor.digest(LITERAL)})

    def test_missing_grant_is_refused_even_with_matching_supervisor(self):
        with self.assertRaisesRegex(ValueError, 'resource handoff'):
            supervisor.validate_supervisor_seal({'supervisor_sha256': supervisor.digest(LITERAL)})

    def test_changed_or_missing_reviewed_supervisor_hash_refuses(self):
        for value in ('f' * 64, None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'supervisor bytes changed'):
                supervisor.validate_supervisor_seal({'root_exclusive_db_renderer_grant': True,
                                                     'supervisor_sha256': value})

    def test_internal_foreign_driver_refuses_before_pipe_or_exec(self):
        with patch.object(supervisor.os, 'read') as read, patch.object(supervisor.os, 'execv') as execute:
            with self.assertRaisesRegex(ValueError, 'Foreign internal driver'):
                supervisor.main(['--inner-launch', '99', '--driver', '/tmp/foreign.py', 'S', 'a'*40, '--freeze', 'seal'])
        read.assert_not_called(); execute.assert_not_called()

    def test_internal_changed_reviewed_driver_refuses_before_pipe_or_exec(self):
        with patch.object(supervisor, 'OWNED', self.base), patch.object(supervisor.os, 'read') as read, \
             patch.object(supervisor.os, 'execv') as execute:
            with self.assertRaisesRegex(ValueError, 'reviewed normal bytes'):
                supervisor.main(['--inner-launch', '99', '--driver', str(self.driver), 'S', 'a'*40, '--freeze', 'seal'])
        read.assert_not_called(); execute.assert_not_called()


class RecordedProcessBoundaries(unittest.TestCase):
    def test_recycled_pid_is_never_signalled(self):
        child = Mock(); child.poll.return_value = 0
        record = {'pid': 700, 'pgid': 700, 'start_ticks': 1}
        with patch.object(supervisor, 'pid_record', return_value={'pid': 700, 'start_ticks': 2}), \
             patch.object(supervisor.os, 'killpg') as killpg, patch.object(supervisor.os, 'kill') as kill:
            self.assertEqual(supervisor.stop_owned(child, {700: record}), [])
        killpg.assert_not_called(); kill.assert_not_called()

    def test_bounded_escalation_reaps_recorded_group(self):
        child = Mock(); child.returncode = None
        child.poll.side_effect = lambda: child.returncode
        record = {'pid': 700, 'pgid': 700, 'start_ticks': 1}
        clock = [0.0]
        def wait(timeout):
            clock[0] += timeout
            if clock[0] >= 20:
                child.returncode = -9
                return -9
            raise subprocess.TimeoutExpired('owned', timeout)
        child.wait.side_effect = wait
        with patch.object(supervisor, 'same_process', side_effect=lambda r: child.returncode is None), \
             patch.object(supervisor.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(supervisor.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)), \
             patch.object(supervisor.os, 'killpg') as killpg, patch.object(supervisor.os, 'kill') as kill:
            actions = supervisor.stop_owned(child, {700: record}, 20)
        self.assertEqual([a['signal'] for a in actions], [signal.SIGINT, signal.SIGTERM, signal.SIGKILL])
        self.assertLessEqual(clock[0], 20)
        self.assertEqual(killpg.call_count, 3); kill.assert_not_called()

    def test_unreaped_child_is_explicit_failure(self):
        child = Mock(); child.poll.return_value = None
        with patch.object(supervisor, 'same_process', return_value=False):
            with self.assertRaisesRegex(ValueError, 'did not reap'):
                supervisor.stop_owned(child, {})


if __name__ == '__main__':
    unittest.main()
