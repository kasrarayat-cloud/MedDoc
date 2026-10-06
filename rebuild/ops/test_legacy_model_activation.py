"""Refusal/preservation proofs using invented bytes; no installed state access."""
from contextlib import nullcontext
from copy import deepcopy
from io import StringIO
import json
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


if __name__ == '__main__':
    unittest.main()
