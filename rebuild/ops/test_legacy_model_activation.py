"""Refusal/preservation proofs using invented bytes; no installed state access."""
from contextlib import nullcontext, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import errno
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    from ops import legacy_model_activation as act
except ImportError:
    import legacy_model_activation as act


def environment():
    return (('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n') +
            'QUILLMD_AI_MODE=live\nQUILLMD_AI_PROVIDER=anthropic\nQUILLMD_DATA_MODE=synthetic\n'
            'QUILLMD_PREVIEW_AUTH_ENABLED=1\nQUILLMD_APP_BASE_URL=https://app.quillmd.com:9443\n'
            'QUILLMD_AI_MODEL=gpt-4.1-mini\nQUILLMD_AI_INPUT_RATE=0.4\n'
            'QUILLMD_AI_OUTPUT_RATE=1.6\nQUILLMD_AI_CACHED_RATE=0.1\n'
            'QUILLMD_AI_MODEL=claude-sonnet-4-6\nQUILLMD_AI_INPUT_RATE=3\n'
            'QUILLMD_AI_OUTPUT_RATE=15\nQUILLMD_AI_CACHED_RATE=0.3\n'
            'FICTIONAL_SECRET="literal $value #quoted"\n# retain this exact comment\n').encode()


def qualification():
    value = {'format': 1, 'source_sha': act.BASELINE, 'qualified_for_legacy_config_demo': True,
             'model': 'claude-sonnet-5-5', 'provider': 'anthropic', 'request_profile': dict(act.PROFILE),
             'rates': dict(act.MODEL_VALUES), 'unsafe_findings': 0,
             'outcomes': {name: True for name in act.OUTCOMES},
             'candidate_install': False, 'patient_admission': False, 'public_launch': False}
    request = {'method': 'POST', 'url': 'https://api.anthropic.com/v1/messages',
               'body_json': {'model': 'claude-sonnet-5-5', 'max_tokens': 6000,
                             'system': 'Fictional source mapping only', 'messages': [{'role': 'user', 'content': 'fiction'}],
                             'output_config': {'format': {'type': 'json_schema', 'schema': {'type': 'object'}}}}}
    response = {'status_code': 200, 'request_id': 'req_fictional',
                'body_json': {'model': 'claude-sonnet-5-5', 'id': 'msg_fictional',
                              'stop_reason': 'end_turn', 'usage': {'input_tokens': 2, 'output_tokens': 1}}}
    evidence = {name: b'{"fictional":true}\n' for name in act.EVIDENCE_ROLES}
    evidence.update(request=act.encode(request), response=act.encode(response))
    return value, evidence, request, response


class EnvironmentPreservation(unittest.TestCase):
    def test_all_duplicate_occurrences_and_unrelated_literal_bytes(self):
        original = environment()
        updated, report = act.render(original, act.BASELINE)
        self.assertEqual(report['assignment_counts'], {key: 2 for key in act.MODEL_VALUES})
        self.assertEqual(updated.count(b'QUILLMD_AI_MODEL="claude-sonnet-5-5"\n'), 2)
        self.assertIn(b'FICTIONAL_SECRET="literal $value #quoted"\n# retain this exact comment\n', updated)
        self.assertIn(('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n').encode(), updated)

    def test_gate_profile_model_serialization_and_missing_assignment_refuse(self):
        original = environment()
        unsafe = [original.replace(b'AUTH_ENABLED=1', b'AUTH_ENABLED=0'),
                  original + b'QUILLMD_V3_GENERATION_BATCHES=1\n',
                  original.replace(b'claude-sonnet-4-6', b'claude-sonnet-5-5'),
                  original.replace(b'QUILLMD_AI_CACHED_RATE=', b'OTHER_CACHED_RATE='), original[:-1]]
        for raw in unsafe:
            with self.subTest(raw_sha256=act.sha(raw)), self.assertRaises(act.Refusal):
                act.render(raw, act.BASELINE)
        with self.assertRaises(act.Refusal):
            act.render(original, 'abbreviated')

    def test_rollback_recovers_exact_original_population_and_only_safe_source_stamp(self):
        original = environment()
        target = '1' * 40
        changed, _ = act.render(original, target)
        self.assertEqual(act.restore_environment(original, changed, act.BASELINE), original)
        recovered = act.restore_environment(original, changed, target)
        self.assertIn(b'QUILLMD_AI_MODEL=gpt-4.1-mini\n', recovered)
        self.assertIn(b'QUILLMD_AI_MODEL=claude-sonnet-4-6\n', recovered)
        self.assertEqual(recovered.replace(('QUILLMD_RELEASE_SHA="' + target + '"\n').encode(),
                                           ('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n').encode()), original)
        with self.assertRaises(act.Refusal):
            act.restore_environment(original, changed.replace(b'$value', b'$intervening'), target)


class QualificationRefusals(unittest.TestCase):
    def test_positive_control_and_independent_raw_model_response_checks(self):
        value, evidence, _, response = qualification()
        self.assertEqual(act.validate_qualification(value, evidence)['response_model'], 'claude-sonnet-5-5')
        for field, bad in (('model', 'claude-sonnet-4-6'), ('stop_reason', 'max_tokens')):
            changed = deepcopy(response)
            changed['body_json'][field] = bad
            with self.subTest(field=field), self.assertRaises(act.Refusal):
                act.validate_qualification(value, {**evidence, 'response': act.encode(changed)})

    def test_newer_profile_corpus_receipt_or_missing_workflow_cannot_qualify_legacy(self):
        value, evidence, request, _ = qualification()
        for changes in ({'max_tokens': 20000}, {'thinking': {'type': 'adaptive'}},
                        {'output_config': {'format': {'type': 'json_schema'}, 'effort': 'medium'}}):
            changed = deepcopy(request)
            changed['body_json'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(act.Refusal):
                act.validate_qualification(value, {**evidence, 'request': act.encode(changed)})
        for changed in ({**value, 'unsafe_findings': False}, {**value, 'candidate_install': True},
                        {**value, 'outcomes': {**value['outcomes'], 'voice': False}},
                        {**value, 'source_sha': '2' * 40}):
            with self.assertRaises(act.Refusal):
                act.validate_qualification(changed, evidence)

    def test_protected_evidence_hash_failure_refuses_before_parsing(self):
        with patch.object(act, 'protected', return_value=b'fictional bytes'), self.assertRaises(act.Refusal):
            act.read_qualification(act.RUNTIME / 'fictional.json', '0' * 64)


class OperatorBoundary(unittest.TestCase):
    def test_default_plan_does_not_read_installed_state(self):
        with patch.object(act, 'protected') as secret, patch.object(act, 'command') as command, \
                patch.object(act, 'modules') as modules, patch('sys.stdout', new=StringIO()):
            self.assertEqual(act.main([]), 0)
            secret.assert_not_called()
            command.assert_not_called()
            modules.assert_not_called()

    def test_systemctl_allowlist_refuses_database_public_timer_and_other_verb(self):
        host = act.Host(Mock())
        host.helper = Mock()
        for action, unit in (('restart', act.UNITS[0]), ('stop', 'quillmd-fresh-database.service'),
                             ('start', 'nginx.service'), ('stop', 'quillmd-fresh-backup.timer')):
            with self.assertRaises(act.Refusal):
                host.service(action, unit)
        host.helper.assert_not_called()

    def test_failed_state_read_and_stop_do_not_skip_other_units(self):
        host = Mock()
        stopped = []
        def state(unit):
            if unit == act.UNITS[0]:
                raise OSError('fictional state failure')
            return {'ActiveState': 'inactive' if unit in stopped else 'active',
                    'MainPID': '0' if unit in stopped else '12'}
        def service(action, unit):
            if unit == act.UNITS[0]:
                raise OSError('fictional stop failure')
            stopped.append(unit)
        host.state.side_effect, host.service.side_effect = state, service
        result = act.best_effort_private_stop(host)
        self.assertEqual(host.service.call_args_list, [unittest.mock.call('stop', unit) for unit in act.UNITS])
        self.assertEqual(stopped, list(act.UNITS[1:]))
        self.assertFalse(result[act.UNITS[0]]['stopped_verified'])
        self.assertTrue(all(result[unit]['stopped_verified'] for unit in act.UNITS[1:]))

    def test_static_root_mode_change_is_detected_and_root_symlink_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'static'
            root.mkdir(mode=0o755)
            root.joinpath('app.css').write_bytes(b'fictional css')
            before = act.inventory(root)
            root.chmod(0o777)
            after = act.inventory(root)
            self.assertEqual(before['app.css'], after['app.css'])
            self.assertNotEqual(before['.'], after['.'])
            alias = Path(temporary) / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(act.Refusal):
                act.inventory(alias)

    def test_actual_configuration_helper_includes_security_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = str(Path(temporary) / 'host')
            roots = [Path(prefix) / relative for relative in ('etc/systemd/system', 'etc/nginx', 'etc/ssh')]
            for root in roots:
                root.mkdir(parents=True, mode=0o755)
            caddy = Path(prefix) / 'opt/meddoc-pro/Caddyfile'
            caddy.parent.mkdir(parents=True)
            caddy.write_bytes(b'fictional caddy')
            host = act.Host(Mock())
            def fake_helper(code, timeout):
                output = StringIO()
                with redirect_stdout(output):
                    exec(compile(code.replace('/host', prefix), '<fictional-read-only-helper>', 'exec'), {})
                return output.getvalue().encode()
            host.helper = fake_helper
            before = host.configuration()
            roots[1].chmod(0o777)
            after = host.configuration()
            key = next(key for key in before if key.endswith('/etc/nginx'))
            self.assertEqual(before[key]['mode'], 0o755)
            self.assertEqual(after[key]['mode'], 0o777)
            self.assertNotEqual(before, after)
            roots[2].rename(roots[2].with_name('ssh-original'))
            roots[2].symlink_to(roots[2].with_name('ssh-original'), target_is_directory=True)
            with self.assertRaises(SystemExit):
                host.configuration()

    def test_simple_unit_start_waits_for_new_pid_proof_but_never_retries_bad_policy(self):
        expected = {'fictional_unit': {'MainPID': '12'}}
        with patch.object(act, 'service_boundary', side_effect=[act.Refusal('same_pid_boundary_proof'), expected]) as boundary, \
                patch.object(act.time, 'sleep'):
            self.assertEqual(act.await_service_boundary(Mock(), Mock(), act.BASELINE), expected)
            self.assertEqual(boundary.call_count, 2)
        with patch.object(act, 'service_boundary', side_effect=act.Refusal('private_unit_source_identity')) as boundary, \
                self.assertRaises(act.Refusal):
            act.await_service_boundary(Mock(), Mock(), act.BASELINE)
        self.assertEqual(boundary.call_count, 1)

    def test_http_startup_wait_is_read_only_and_contract_failure_stops_immediately(self):
        import httpx
        with patch.object(act, 'health', side_effect=[httpx.ConnectError('fictional startup'), []]) as health, \
                patch.object(act.time, 'sleep'):
            self.assertEqual(act.await_health(act.BASELINE), [])
            self.assertEqual(health.call_count, 2)
        with patch.object(act, 'health', side_effect=act.Refusal('public_maintenance')) as health, \
                self.assertRaises(act.Refusal):
            act.await_health(act.BASELINE)
        self.assertEqual(health.call_count, 1)

    def test_unrelated_main_passenger_refuses_before_any_act(self):
        source = act.ROOT / '.worktrees/fictional-operator'
        commit = '3' * 40
        def fake_git(tree, *args):
            if args == ('rev-parse', 'HEAD'):
                return commit.encode()
            if args[:2] == ('status', '--porcelain'):
                return b''
            if args[:2] == ('merge-base', '--is-ancestor'):
                return b''
            if args[:2] == ('diff', '--name-only'):
                return (act.SELF + '\n' + act.DECL + '\nrebuild/core/generation.py\n').encode()
            raise AssertionError('refusal failed to stop before downstream operation')
        with patch.object(act, 'SOURCE', source), patch.object(Path, 'resolve', return_value=source), \
                patch.object(act, 'git', side_effect=fake_git), self.assertRaises(act.Refusal):
            act.source_gate(commit, {}, executing=True)

    def test_population_drift_during_drain_never_writes_environment_or_advances_main(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            raw = environment()
            host = Mock()
            host.state.return_value = {'ActiveState': 'inactive', 'MainPID': '0'}
            backup = Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'FICTIONAL_CIPHERTEXT:' + value
            storage = Mock()
            storage.inventory.return_value = {}
            exclusion = Mock()
            exclusion.hold.return_value = nullcontext()
            writer = Mock()
            units = {unit: {'MainPID': str(index + 1), 'ExecMainStartTimestampMonotonic': '1'}
                     for index, unit in enumerate(act.UNITS)}
            args = SimpleNamespace(operator_commit='4' * 40, backup_directory=runtime / 'fictional-backup')
            contract = {'environment_before_sha256': act.sha(raw), 'backup_manifest_sha256': '0' * 64}
            with patch.object(act, 'RUNTIME', runtime), patch.object(act, 'protected', return_value=raw), \
                    patch.object(act, 'health'), patch.object(act, 'service_boundary', return_value=units), \
                    patch.object(act, 'verify_backup', return_value={}), patch.object(act, 'database', return_value={}), \
                    patch.object(act, 'snapshot', side_effect=[{'population': 'before'}, {'population': 'drifted'}]), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=act.BASELINE.encode()) as git, \
                    patch('sys.stdout', new=StringIO()), self.assertRaises(act.Refusal):
                act.execute(args, contract, {}, {'shared_head': act.BASELINE}, host=host, backup=backup,
                            storage=storage, exclusion=exclusion, env_writer=writer)
            writer.replace_environment.assert_not_called()
            self.assertEqual(host.service.call_args_list, [unittest.mock.call('stop', unit) for unit in act.UNITS])
            self.assertFalse(any(call.args[1:2] == ('merge',) for call in git.call_args_list))
            failure = list(runtime.glob('legacy-model-demo-*/failed.json'))
            self.assertEqual(len(failure), 1)
            self.assertFalse(json.loads(failure[0].read_bytes())['complete'])

    def test_activation_enospc_failure_evidence_cannot_leave_new_services_active(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            target = '4' * 40
            original = environment()
            updated, report = act.render(original, target)
            current = [original]
            states = {unit: {'ActiveState': 'active', 'MainPID': str(index + 1),
                             'ExecMainStartTimestampMonotonic': '1'} for index, unit in enumerate(act.UNITS)}
            old_units = deepcopy(states)
            host = Mock()
            def state(unit):
                return dict(states[unit]) if unit in states else {'ActiveState': 'inactive', 'MainPID': '0'}
            def service(action, unit):
                states[unit] = {'ActiveState': 'inactive' if action == 'stop' else 'active',
                                'MainPID': '0' if action == 'stop' else str(11 + act.UNITS.index(unit)),
                                'ExecMainStartTimestampMonotonic': '2'}
            host.state.side_effect, host.service.side_effect = state, service
            host.effective_worker.return_value = {'values': report['values']}
            backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'FICTIONAL_CIPHER:' + value
            storage.inventory.return_value = {}
            exclusion.hold.return_value = nullcontext()
            writer.replace_environment.side_effect = lambda path, before, after: current.__setitem__(0, after)
            original_write = act.write_new
            def write(path, raw):
                if path.name.startswith('failed'):
                    raise OSError(errno.ENOSPC, 'fictional full evidence volume')
                original_write(path, raw)
            args = SimpleNamespace(operator_commit=target, backup_directory=runtime / 'fictional-backup')
            contract = {'environment_before_sha256': act.sha(original), 'backup_manifest_sha256': '0' * 64}
            with patch.object(act, 'RUNTIME', runtime), patch.object(act, 'protected', side_effect=lambda *args: current[0]), \
                    patch.object(act, 'write_new', side_effect=write), patch.object(act, 'health'), patch.object(act, 'await_health'), \
                    patch.object(act, 'service_boundary', return_value=old_units), \
                    patch.object(act, 'await_service_boundary', side_effect=lambda *args: deepcopy(states)), \
                    patch.object(act, 'verify_backup', return_value={}), patch.object(act, 'database', return_value={}), \
                    patch.object(act, 'snapshot', side_effect=[{'population': 1}, {'population': 1}, {'population': 1}, {'population': 2}]), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=target.encode()), patch('sys.stdout', new=StringIO()), \
                    self.assertRaises(act.Refusal):
                act.execute(args, contract, {}, {'shared_head': act.BASELINE}, host=host, backup=backup,
                            storage=storage, exclusion=exclusion, env_writer=writer)
            self.assertEqual(current[0], updated)
            self.assertTrue(all(value['ActiveState'] == 'inactive' and value['MainPID'] == '0' for value in states.values()))
            self.assertEqual(sum(call.args[0] == 'stop' for call in host.service.call_args_list), 6)

    def test_rollback_enospc_failure_evidence_still_invokes_independent_fail_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            directory = runtime / 'legacy-model-demo-fictional'
            directory.mkdir(mode=0o700)
            target = '4' * 40
            original = environment()
            updated, _ = act.render(original, target)
            host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.decrypt.side_effect = lambda value: value
            exclusion.hold.return_value = nullcontext()
            host.state.return_value = {'ActiveState': 'inactive', 'MainPID': '0'}
            writer.replace_environment.side_effect = OSError('fictional restore failure')
            original_write = act.write_new
            def write(path, raw):
                if path.name == 'failed.json':
                    raise OSError(errno.ENOSPC, 'fictional full evidence volume')
                original_write(path, raw)
            def read(path, *args):
                return original if path.name == 'environment-before.fernet' else updated
            args = SimpleNamespace(operator_commit=target, activation_directory=directory)
            with patch.object(act, 'RUNTIME', runtime), patch.object(act, 'protected', side_effect=read), \
                    patch.object(act, 'write_new', side_effect=write), patch.object(act, 'snapshot', return_value={}), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=target.encode()), \
                    patch.object(act, 'best_effort_private_stop', return_value={}) as stop, \
                    self.assertRaises(act.Refusal):
                act.rollback(args, {}, host=host, backup=backup, storage=storage, exclusion=exclusion, env_writer=writer)
            stop.assert_called_once_with(host)


if __name__ == '__main__':
    unittest.main()
