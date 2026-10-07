"""Focused invented-state controls; no host, DB, auth, provider or service actions."""
from contextlib import ExitStack, nullcontext, redirect_stdout
from copy import deepcopy
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ops import private_availability_recovery as act


TARGET = '8' * 40


def environment():
    return ('QUILLMD_RELEASE_SHA="' + act.INSTALLED + '"\n'
            'QUILLMD_AI_MODE=live\nQUILLMD_AI_PROVIDER=anthropic\nQUILLMD_AI_MODEL=claude-sonnet-5-5\n'
            'QUILLMD_AI_INPUT_RATE=2\nQUILLMD_AI_OUTPUT_RATE=10\nQUILLMD_AI_CACHED_RATE=0.20\n'
            'QUILLMD_PREVIEW_AUTH_ENABLED=1\nQUILLMD_APP_BASE_URL=https://app.quillmd.com:9443\n'
            'FICTIONAL_SECRET="$literal # preserve these bytes"\n# keep original comment\n').encode()


def metadata(raw, inode):
    return {'uid': 0, 'gid': 0, 'mode': 0o644, 'device': 2050, 'inode': inode,
            'sha256': hashlib.sha256(raw).hexdigest()}


def population():
    previous = b'[Unit]\nDescription=Fictional co-tenant\n[Service]\nWorkingDirectory=/fictional/old\nExecStart=/usr/bin/false\n'
    following = previous.replace(b'/fictional/old', b'/fictional/new')
    old = {'database': {'tables': {'fictional': {'rows': 212, 'sha256': 'a' * 64}},
                        'catalog': {}, 'invariants': {}, 'pending_jobs': 0, 'held': 0, 'referenced_files': {}},
           'files': {'original': {'sha256': 'c' * 64}}, 'mail': {}, 'static': {'asset': {'sha256': 'd' * 64}},
           'configuration': {act.EXTERNAL_UNIT: metadata(previous, 100), '/unrelated': {'exact': True}}}
    current = deepcopy(old)
    current['database']['tables']['fictional']['rows'] = 213
    current['configuration'][act.EXTERNAL_UNIT] = metadata(following, 101)
    return old, current, previous, following


def evidence(path, raw):
    path.write_bytes(raw)
    path.chmod(0o600)
    return {'path': str(path), 'sha256': act.sha(raw)}


class AvailabilityRecoveryTests(unittest.TestCase):
    def test_default_has_no_installed_reads_or_actions(self):
        out = StringIO()
        with patch.object(act, 'load_contract', side_effect=AssertionError('must not read')), \
             patch.object(act.old, 'modules', side_effect=AssertionError('must not import runtime')), redirect_stdout(out):
            self.assertEqual(act.main([]), 0)
        value = json.loads(out.getvalue())
        self.assertFalse(value['execution_performed'])
        self.assertFalse(value['installed_state_accessed'])
        self.assertEqual(value['provider_calls'], 0)

    def test_release_only_configuration_keeps_every_unrelated_byte_and_value(self):
        raw = environment()
        updated = act.release_only_environment(raw, TARGET)
        self.assertEqual(updated.replace(TARGET.encode(), act.INSTALLED.encode()), raw)
        for broken in (raw + b'QUILLMD_RELEASE_SHA=' + act.INSTALLED.encode() + b'\n',
                       raw.replace(b'claude-sonnet-5-5', b'claude-sonnet-4-6'),
                       raw.replace(b'QUILLMD_PREVIEW_AUTH_ENABLED=1', b'QUILLMD_PREVIEW_AUTH_ENABLED=0'),
                       raw.replace(b'QUILLMD_AI_MODE=live', b'QUILLMD_AI_MODE=fixture'),
                       raw.replace(b'QUILLMD_AI_OUTPUT_RATE=10', b'QUILLMD_AI_OUTPUT_RATE=15')):
            with self.subTest(broken=act.sha(broken)), self.assertRaises(act.Refusal):
                act.release_only_environment(broken, TARGET)

    def test_external_transition_rejects_every_non_working_directory_change(self):
        _, _, before, after = population()
        self.assertEqual(act.working_directory_transition(before, after),
                         {'old_working_directory': '/fictional/old', 'new_working_directory': '/fictional/new'})
        for broken in (after.replace(b'/usr/bin/false', b'/usr/bin/true'),
                       after + b'WorkingDirectory=/second\n',
                       after.replace(b'WorkingDirectory=', b' WorkingDirectory='),
                       after.replace(b'/fictional/new', b'/fictional/%h'),
                       after.replace(b'[Service]', b'[Other]')):
            with self.subTest(broken=act.sha(broken)), self.assertRaises(act.Refusal):
                act.working_directory_transition(before, broken)

    def test_missing_approval_can_report_independent_readonly_facts_but_never_green(self):
        original, current, _, _ = population()
        report = {'current_database_fingerprint': current['database']}
        pending = act.compare_population({'expected_population': original}, current, report,
                                          {'qualified': False}, allow_pending=True)
        self.assertEqual(pending['status'], 'RED')
        self.assertTrue(pending['current_metadata_is_not_approval'])
        self.assertEqual(act.compare_population({'expected_population': original}, current, report,
                         {'qualified': True, 'fabricated_approval': True}, allow_pending=True)['status'], 'RED')
        with self.assertRaisesRegex(act.Refusal, 'authorization_protocol_unqualified'):
            act.compare_population({'expected_population': original}, current, report, {'qualified': False})
        for name in ('files', 'mail', 'static', 'database', 'configuration'):
            broken = deepcopy(current)
            broken[name]['unlisted'] = 'changed'
            with self.subTest(name=name), self.assertRaises(act.Refusal):
                act.compare_population({'expected_population': original}, broken, report,
                                        {'qualified': False}, allow_pending=True)

    def test_reviewed_approval_gate_binds_original_current_bytes_and_both_provenance_artifacts(self):
        original, current, previous, following = population()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = evidence(root / 'old-unit', previous)
            after = evidence(root / 'new-unit', following)
            authorization = evidence(root / 'existing-authorization', b'{"fictional_existing_authorization":true}')
            installation = evidence(root / 'existing-installation', b'{"fictional_existing_installation":true}')
            # This fixture tests linkage only. It is not native approval qualification.
            proof = {'complete': True, 'existing_deployment_authorization_verified': True,
                     'native_root_installation_verified': True, 'unit_path': act.EXTERNAL_UNIT,
                     'old_unit_sha256': before['sha256'], 'new_unit_sha256': after['sha256'],
                     'approved_working_directory': '/fictional/new',
                     'authorization_evidence': authorization, 'installation_evidence': installation}
            receipt = evidence(root / 'proof', act.encode(proof))
            ack = {'qualified': True, 'unit_path': act.EXTERNAL_UNIT,
                   'old_metadata': original['configuration'][act.EXTERNAL_UNIT],
                   'new_metadata': current['configuration'][act.EXTERNAL_UNIT],
                   'old_bytes_path': before['path'], 'new_bytes_path': after['path'],
                   'approval_protocol': 'existing-approved-root-deployment-v1',
                   'approval_path': receipt['path'], 'approval_sha256': receipt['sha256'],
                   'authorization_evidence': authorization, 'installation_evidence': installation}
            # Real code must refuse even an internally consistent invented envelope.
            with self.assertRaisesRegex(act.Refusal, 'authorization_protocol_unqualified'):
                act.acknowledge_configuration(original['configuration'], current['configuration'], ack)
            with patch.object(act, 'NATIVE_APPROVAL_PROTOCOL_QUALIFIED', True):
                value = act.acknowledge_configuration(original['configuration'], current['configuration'], ack)
            self.assertFalse(value['unit_mutated_by_this_act'])
            for name, val in (('qualified', False), ('approval_sha256', '0' * 64),
                              ('unit_path', '/etc/systemd/system/foreign.service'),
                              ('new_metadata', original['configuration'][act.EXTERNAL_UNIT])):
                with self.subTest(name=name), patch.object(act, 'NATIVE_APPROVAL_PROTOCOL_QUALIFIED', True), self.assertRaises(act.Refusal):
                    act.acknowledge_configuration(original['configuration'], current['configuration'], {**ack, name: val})
            Path(authorization['path']).write_bytes(b'changed authorization')
            with patch.object(act, 'NATIVE_APPROVAL_PROTOCOL_QUALIFIED', True), self.assertRaisesRegex(act.Refusal, 'provenance_artifact'):
                act.acknowledge_configuration(original['configuration'], current['configuration'], ack)

    def test_loaded_state_is_exact_and_foreign_unit_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            values = {'WorkingDirectory': '/fictional/new', 'FragmentPath': act.EXTERNAL_UNIT,
                      'DropInPaths': '', 'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
                      'UnitFileState': 'enabled', 'NeedDaemonReload': 'no', 'User': 'fictional-app',
                      'Group': 'fictional-app', 'InvocationID': 'a' * 32, 'MainPID': '100',
                      'ExecMainStartTimestampMonotonic': '200'}
            proof = {'loaded_state': values, 'approved_working_directory': '/fictional/new',
                     'approved_user': 'fictional-app', 'approved_group': 'fictional-app'}
            receipt = evidence(Path(temp) / 'proof', act.encode(proof))
            ack = {'qualified': True, 'loaded_state': values, 'approval_path': receipt['path'],
                   'approval_sha256': receipt['sha256']}
            host = SimpleNamespace(helper=Mock(return_value=act.encode(values)))
            self.assertEqual(act.loaded_external_state(host, ack), values)
            code = host.helper.call_args.args[0]
            self.assertIn("'show'", code)
            for action in ("'start'", "'stop'", "'reload'", "'daemon-reload'"):
                self.assertNotIn(action, code)
            for name, changed in (('WorkingDirectory', '/other'), ('DropInPaths', '/override'),
                                   ('NeedDaemonReload', 'yes'), ('MainPID', '101'), ('User', 'root')):
                host.helper.return_value = act.encode({**values, name: changed})
                with self.subTest(name=name), self.assertRaises(act.Refusal):
                    act.loaded_external_state(host, ack)

    def test_source_readability_refuses_private_or_symlinked_payload_without_chmod(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp)
            tree.chmod(0o755)
            source = tree / 'rebuild/ops/new.py'
            source.parent.mkdir(parents=True, mode=0o755)
            source.parent.chmod(0o755)
            source.parent.parent.chmod(0o755)
            source.write_text('fictional public source')
            source.chmod(0o644)
            def index(tree, *args):
                if '--stage' in args:
                    return b'100644 ' + b'a' * 40 + b' 0\trebuild/ops/new.py\n'
                return b'rebuild/ops/new.py\n'
            with patch.object(act.old, 'git', side_effect=index):
                act.source_readability(tree)
                source.chmod(0o600)
                with self.assertRaisesRegex(act.Refusal, 'source_readability'):
                    act.source_readability(tree)
                self.assertEqual(source.stat().st_mode & 0o777, 0o600)
                source.chmod(0o644)
                source.parent.chmod(0o700)
                with self.assertRaisesRegex(act.Refusal, 'source_traversability'):
                    act.source_readability(tree)
                self.assertEqual(source.parent.stat().st_mode & 0o777, 0o700)
                source.parent.chmod(0o755)
                target = tree / 'retained.py'
                target.write_text('fictional retained source')
                target.chmod(0o644)
                source.unlink()
                source.symlink_to(target)
                with self.assertRaisesRegex(act.Refusal, 'source_readability'):
                    act.source_readability(tree)
                self.assertTrue(source.is_symlink())

    def test_git_forward_has_explicit_public_umask_and_rechecks_source(self):
        result = SimpleNamespace(returncode=0, stdout=b'fictional forward', stderr=b'')
        with patch.object(act.subprocess, 'run', return_value=result) as run, \
             patch.object(act.old, 'git', side_effect=[TARGET.encode(), b'']), \
             patch.object(act, 'source_readability') as readable:
            act.forward_source(TARGET)
        self.assertEqual(run.call_args.kwargs['umask'], 0o022)
        self.assertEqual(run.call_args.args[0], ['git', '-C', str(act.ROOT), 'merge', '--ff-only', TARGET])
        readable.assert_called_once_with(act.ROOT)

    def fixture_recovery(self, root):
        original, current, _, _ = population()
        cipher = SimpleNamespace(encrypt=lambda value: b'fictional-cipher:' + act.sha(value).encode())
        prepared = {'original': {'before': original, 'expected_population': original, 'backup': {'original': True}},
                    'before': current, 'environment': environment(), 'cipher': cipher, 'backup': {'coverage': 'original'},
                    'admission': {'allowed_deltas': {'publisher': {'healthy': False}}}, 'units': {'stopped': True},
                    'external_acknowledgement': {'loaded_state': {'fictional': 'exact'}}, 'storage_admission': {'passed': True}}
        host = SimpleNamespace(state=Mock(return_value={'MainPID': '0', 'ActiveState': 'inactive'}),
                               service=Mock(), worker_configuration=Mock(return_value={'actual_provider_model_verified': False}))
        contract = {'original_policy': {'original_receipts': {'original': 'unchanged'}},
                    'external_configuration_ack': {'qualified': True}, 'installation_qualified': True}
        stack = ExitStack()
        stack.enter_context(patch.object(act, 'OUTPUT', root / 'exclusive-result'))
        stack.enter_context(patch.object(act, 'ATTEMPT', root / 'exclusive-attempt'))
        stack.enter_context(patch.object(act, 'existing_operation_locks', return_value=nullcontext()))
        stack.enter_context(patch.object(act, 'readiness', return_value=prepared))
        stack.enter_context(patch.object(act, 'stopped_scope', return_value=prepared['units']))
        stack.enter_context(patch.object(act.old, 'snapshot', return_value=current))
        stack.enter_context(patch.object(act, 'loaded_external_state', return_value={'fictional': 'exact'}))
        stack.enter_context(patch.object(act, 'forward_source'))
        stack.enter_context(patch.object(act, 'storage_admission', return_value={'passed': True}))
        stack.enter_context(patch.object(act, 'boundary', return_value={'fictional': 'boundary'}))
        stack.enter_context(patch.object(act, 'direct_health', return_value=[]))
        # This wholly invented pipeline exercises preservation/failure ordering,
        # not the unqualified native authorization or actual installation.
        stack.enter_context(patch.object(act, 'NATIVE_APPROVAL_PROTOCOL_QUALIFIED', True))
        return stack, prepared, host, contract

    def test_pending_preflight_writes_no_outputs_or_marker_and_never_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stack, prepared, host, contract = self.fixture_recovery(root)
            prepared['external_acknowledgement'] = {'status': 'RED', 'reason': 'approval_missing'}
            with stack:
                result = act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                    exclusion=SimpleNamespace(bind_runtime=Mock(), hold=lambda _: nullcontext()), env_writer=None, preflight=True)
                self.assertFalse(result['complete'])
                self.assertTrue(result['independent_checks_complete'])
                self.assertFalse(act.OUTPUT.exists())
                self.assertFalse(act.ATTEMPT.exists())
                host.service.assert_not_called()

    def test_recovery_order_preserves_original_proof_and_leaves_campaign_unconsumed(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, prepared, host, contract = self.fixture_recovery(Path(temp))
            with stack:
                env_writer = SimpleNamespace(replace_environment=Mock())
                result = act.complete_recovery(TARGET, contract, {'operator_commit': TARGET}, host=host, backup=None,
                    storage=None, exclusion=SimpleNamespace(bind_runtime=Mock(), hold=lambda _: nullcontext()), env_writer=env_writer)
                self.assertTrue(result['complete'])
                self.assertFalse(result['actual_provider_model_verified'])
                self.assertEqual(host.service.call_args_list, [unittest.mock.call('start', unit) for unit in act.old.UNITS])
                final = json.loads((act.OUTPUT / 'complete.json').read_bytes())
                self.assertEqual(final['original_before'], prepared['original']['before'])
                self.assertFalse(final['acceptance_started'])
                self.assertEqual(final['provider_calls'], 0)
                self.assertEqual((act.OUTPUT / 'complete.json').stat().st_mode & 0o777, 0o600)

    def test_before_marker_race_has_fixed_evidence_no_source_or_service_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, prepared, host, contract = self.fixture_recovery(Path(temp))
            with stack, patch.object(act.old, 'snapshot', return_value={'unknown': True}), \
                 patch.object(act, 'forward_source') as forward:
                with self.assertRaisesRegex(act.Refusal, 'failed_preserving_evidence'):
                    act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                        exclusion=SimpleNamespace(bind_runtime=Mock(), hold=lambda _: nullcontext()), env_writer=None)
                self.assertFalse(act.ATTEMPT.exists())
                forward.assert_not_called()
                host.service.assert_not_called()
                failure = json.loads((act.OUTPUT / 'failed.json').read_bytes())
                self.assertEqual(failure['refusal_label'], 'availability_before_marker_race')
                self.assertFalse(failure['mutation_started'])

    def test_failure_after_first_web_start_attempts_every_private_stop_and_retains_unknown_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, prepared, host, contract = self.fixture_recovery(Path(temp))
            def action(kind, unit):
                if kind == 'start':
                    raise RuntimeError('DO-NOT-RETAIN-FICTIONAL-SECRET')
            host.service.side_effect = action
            with stack:
                with self.assertRaises(act.Refusal):
                    act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                        exclusion=SimpleNamespace(bind_runtime=Mock(), hold=lambda _: nullcontext()),
                        env_writer=SimpleNamespace(replace_environment=Mock()))
                failure = (act.OUTPUT / 'failed.json').read_bytes()
                self.assertNotIn(b'DO-NOT-RETAIN', failure)
                parsed = json.loads(failure)
                self.assertEqual(parsed['refusal_label'], 'availability_protected_operation_failure')
                self.assertEqual(set(parsed['fail_stop']), set(act.old.UNITS))
                self.assertTrue(act.ATTEMPT.exists())

    def test_fixed_old_refusal_labels_are_kept_and_arbitrary_messages_are_suppressed(self):
        self.assertEqual(act.safe_failure_label(act.old.Refusal('pending_or_unknown_provider_work')),
                         'pending_or_unknown_provider_work')
        self.assertEqual(act.safe_failure_label(RuntimeError('literal key')), 'availability_protected_operation_failure')
        self.assertEqual(act.safe_failure_label(act.Refusal('not-a-fixed-label secret')),
                         'availability_protected_operation_failure')

    def test_actual_execute_gate_cannot_be_opened_by_future_declaration_flags_or_fake_proof(self):
        with patch.object(act, 'readiness', side_effect=AssertionError('must not read state')), \
             patch.object(act, 'existing_operation_locks', side_effect=AssertionError('must not create/open locks')):
            with self.assertRaisesRegex(act.Refusal, 'authorization_protocol_unqualified'):
                act.complete_recovery(TARGET, {'installation_qualified': True,
                    'external_configuration_ack': {'qualified': True, 'fabricated': True}}, {},
                    host=None, backup=None, storage=None, exclusion=None, env_writer=None)
        with patch.object(act, 'load_contract', side_effect=AssertionError('must not read authority/state')):
            with self.assertRaisesRegex(act.Refusal, 'authorization_protocol_unqualified'):
                act.main(['--execute', '--operator-commit', TARGET])

    def test_startup_wait_retries_only_connection_readiness_and_never_policy_refusal(self):
        import httpx
        with patch.object(act, 'direct_health', side_effect=[httpx.ConnectError('fictional'), ['ready']]) as health, \
             patch.object(act.time, 'sleep'):
            self.assertEqual(act.await_direct_health(TARGET), ['ready'])
            self.assertEqual(health.call_count, 2)
        with patch.object(act, 'direct_health', side_effect=act.Refusal('availability_direct_health_contract')) as health:
            with self.assertRaisesRegex(act.Refusal, 'direct_health_contract'):
                act.await_direct_health(TARGET)
            self.assertEqual(health.call_count, 1)

    def test_qualified_database_adapter_uses_readonly_transaction_and_no_auth_or_driver(self):
        import psycopg
        original = {'fictional': 'original capture'}
        baseline = {'fictional': 'baseline'}
        original_rows = {'core_servicehealth': {'rows': [b'fictional COPY row\n'], 'columns': ['key']}}
        table_map = {'core_servicehealth': {'rows': 1, 'sha256': 'a' * 64}, 'django_session': {'rows': 212}}
        publisher = {'all_eleven_columns_accounted_for': True, 'current_full_row': {'healthy': False}}
        verifier = SimpleNamespace(original_continuation_capture=Mock(return_value=(original, baseline, {'tables': table_map}, original_rows)),
            current_copy_tables=Mock(return_value=({'fictional': 'current'}, {'core_servicehealth': ['key']}, table_map)),
            row_mapping=Mock(return_value={'backup': {'key': b'backup'}}),
            publisher_source_admission=Mock(return_value=publisher),
            continuation_rows_admission=Mock(return_value={'publisher': publisher}),
            continuation_database_fingerprint=Mock(return_value={'all': 'fingerprints'}),
            continuation_authentication=Mock(side_effect=AssertionError('authentication forbidden')),
            main=Mock(side_effect=AssertionError('driver forbidden')))
        conn = Mock()
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        conn.execute.return_value.fetchone.return_value = {'current_user': 'quillmd_backup',
            'current_database': 'quillmd_fresh', 'read_only': 'on'}
        backup = SimpleNamespace(source_options=Mock(return_value={'dbname': 'fictional-owned-test'}),
            key_at=Mock(return_value=SimpleNamespace(decrypt=lambda _: b'QUILLMD_SECRET_KEY=fictional-only\n'
                b'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME=fictional\n'
                b'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD=fictional-only-password\n')))
        with patch.object(psycopg, 'connect', return_value=conn) as connect, \
             patch.object(act, 'protected', return_value=b'fictional cipher'):
            report = act.database_admission({'original_policy': {}}, original, verifier, backup)
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(conn.execute.call_args_list[0].args,
                         ('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY',))
        self.assertIsNone(verifier.continuation_rows_admission.call_args.args[6])
        self.assertEqual(report['allowed_deltas']['publisher'], publisher)
        self.assertEqual(report['current_database_fingerprint'], {'all': 'fingerprints'})
        verifier.continuation_authentication.assert_not_called()
        verifier.main.assert_not_called()
        for flags in ({'current_user': 'runtime', 'current_database': 'quillmd_fresh', 'read_only': 'on'},
                      {'current_user': 'quillmd_backup', 'current_database': 'foreign', 'read_only': 'on'},
                      {'current_user': 'quillmd_backup', 'current_database': 'quillmd_fresh', 'read_only': 'off'}):
            conn.execute.return_value.fetchone.return_value = flags
            with patch.object(psycopg, 'connect', return_value=conn), \
                 patch.object(act, 'protected', return_value=b'fictional cipher'), self.assertRaises(act.Refusal):
                act.database_admission({'original_policy': {}}, original, verifier, backup)

    def test_original_publisher_and_session_policy_must_equal_prepared_qualified_git_policy(self):
        raw = b'<!-- legacy-model-contract -->\n```json\n' + act.encode({'execution_qualified': True,
            'continuation_contract': {'qualified': True, 'publisher_admission_policy': {'qualified': True,
                'source_sha256': {'fictional': 'a' * 64}}, 'health_session': {'fictional': 'unchanged'}}}) + b'```\n'
        with patch.object(act.old, 'git', return_value=raw) as git:
            actual = act.original_qualified_policy()
        self.assertEqual(git.call_args.args, (act.SOURCE, 'show', act.PREPARED + ':' + act.old.DECL))
        self.assertEqual(actual['health_session'], {'fictional': 'unchanged'})
        with patch.object(act.old, 'git', return_value=raw.replace(b'"execution_qualified":true', b'"execution_qualified":false')):
            with self.assertRaisesRegex(act.Refusal, 'original_qualification'):
                act.original_qualified_policy()


if __name__ == '__main__':
    unittest.main()
