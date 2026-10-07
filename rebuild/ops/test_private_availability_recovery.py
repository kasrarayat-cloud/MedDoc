"""Focused invented-state controls; no host, DB, auth, provider or service actions."""
from contextlib import ExitStack, nullcontext, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ops import private_availability_recovery as act
from ops.test_repair_source_permissions import FictionalOS


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
        observer = verifier.publisher_source_admission.call_args.args[0]
        self.assertIsNot(observer, conn)
        with self.assertRaisesRegex(act.Refusal, 'publisher_observation_statement'):
            observer.execute('UPDATE core_servicehealth SET healthy=true')
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

    @staticmethod
    def publisher_observation(row):
        cursor = Mock()
        cursor.fetchall.return_value = [{'row': row, 'retained_transport_field': 'unchanged'}]
        conn = Mock()
        conn.execute.return_value = cursor
        proxy = act.publisher_observation_connection(conn)
        observed = proxy.execute("SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='backup'").fetchall()
        return observed, conn

    def test_publisher_json_trailing_fractional_zeros_use_identical_initial_and_reread_instants(self):
        row = {'created_at': '2026-10-06T02:00:00.12345+00:00',
               'computed_at': '2026-10-07T02:00:00.5+00:00',
               'published_at': '2026-10-07T02:00:00.6+00:00',
               'id': 'original', 'key': 'backup', 'condition': 'failure', 'severity': 'failure',
               'healthy': False, 'action': 'Preserve unhealthy state.', 'payload': {'exact': True},
               'expected_interval_seconds': 300}
        original = deepcopy(row)
        # The frozen initial parse expands fractional zeroes; raw JSON reread
        # strings differ even while all values and all eleven columns are stable.
        parsed = {**row, **{name: datetime.fromisoformat(row[name]).isoformat()
                            for name in ('created_at', 'computed_at', 'published_at')}}
        self.assertNotEqual(parsed, row)
        before, conn = self.publisher_observation(row)
        after, _ = self.publisher_observation(row)
        self.assertEqual(before, after)
        self.assertEqual(before[0]['row'], parsed)
        self.assertEqual(before[0]['retained_transport_field'], 'unchanged')
        self.assertEqual(set(before[0]['row']), set(row))
        self.assertEqual(row, original)
        self.assertEqual(conn.execute.call_count, 1)

    def test_publisher_timestamp_offsets_canonicalize_equal_instants_without_rounding(self):
        row = {'created_at': '2026-10-06T04:00:00.12345+02:00',
               'computed_at': '2026-10-07T01:00:00.000001-01:00',
               'published_at': datetime(2026, 10, 7, 2, 0, 0, 2, tzinfo=timezone.utc)}
        result, _ = self.publisher_observation(row)
        self.assertEqual(result[0]['row'], {
            'created_at': '2026-10-06T02:00:00.123450+00:00',
            'computed_at': '2026-10-07T02:00:00.000001+00:00',
            'published_at': '2026-10-07T02:00:00.000002+00:00'})

    def test_publisher_timestamp_adapter_preserves_real_microsecond_drift(self):
        row = {name: '2026-10-07T02:00:00.12345+00:00'
               for name in ('created_at', 'computed_at', 'published_at')}
        before, _ = self.publisher_observation(row)
        for name in row:
            changed = {**row, name: '2026-10-07T02:00:00.123451+00:00'}
            after, _ = self.publisher_observation(changed)
            self.assertNotEqual(before, after)

    def test_publisher_timestamp_adapter_rejects_naive_malformed_missing_and_non_time_values(self):
        row = {name: '2026-10-07T02:00:00+00:00'
               for name in ('created_at', 'computed_at', 'published_at')}
        for name in row:
            for value in ('2026-10-07T02:00:00', 'invalid', '', None, 0,
                          datetime(2026, 10, 7, 2, 0, 0)):
                with self.subTest(name=name, kind=type(value).__name__), self.assertRaisesRegex(
                        act.Refusal, 'publisher_observation_time'):
                    self.publisher_observation({**row, name: value})
            with self.subTest(missing=name), self.assertRaisesRegex(act.Refusal, 'publisher_observation_time'):
                self.publisher_observation({key: value for key, value in row.items() if key != name})

    def test_publisher_timestamp_adapter_keeps_non_time_drift_missing_and_extra_columns_visible(self):
        row = {name: '2026-10-07T02:00:00+00:00'
               for name in ('created_at', 'computed_at', 'published_at')}
        row.update(id='original', key='backup', healthy=False, action='failure',
                   condition='failure', severity='failure', payload={'exact': True}, expected_interval_seconds=300)
        before, _ = self.publisher_observation(row)
        for name, value in (('id', 'different'), ('key', 'different'), ('healthy', True),
                            ('action', 'different'), ('condition', 'different'), ('severity', 'different'),
                            ('payload', {'exact': False}), ('expected_interval_seconds', 301)):
            with self.subTest(name=name):
                after, _ = self.publisher_observation({**row, name: value})
                self.assertNotEqual(before, after)
        extra, _ = self.publisher_observation({**row, 'unlisted': 'must remain visible'})
        self.assertIn('unlisted', extra[0]['row'])
        missing, _ = self.publisher_observation({key: value for key, value in row.items() if key != 'healthy'})
        self.assertNotIn('healthy', missing[0]['row'])

    def test_publisher_timestamp_adapter_rejects_other_statement_and_non_row_transport(self):
        conn = Mock()
        proxy = act.publisher_observation_connection(conn)
        for statement in ('SELECT * FROM core_servicehealth', 'DELETE FROM core_servicehealth',
                          "SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='other'"):
            with self.assertRaisesRegex(act.Refusal, 'publisher_observation_statement'):
                proxy.execute(statement)
        conn.execute.assert_not_called()
        for item in (None, [], {'row': []}, {'row': None}, {}):
            conn.execute.return_value.fetchall.return_value = [item]
            with self.assertRaisesRegex(act.Refusal, 'publisher_observation_row'):
                proxy.execute("SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='backup'").fetchall()

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


class DescriptorSourceGateTests(unittest.TestCase):
    def setUp(self):
        native_os = FictionalOS(os.getuid(), os.getgid())
        self.enterContext(patch.object(act, 'os', native_os))
        self.enterContext(patch.object(act.source_files, 'os', native_os))

    def fixture(self, root):
        root.chmod(0o755)
        operator = root / '.worktrees/operator'
        operator.mkdir(parents=True)
        files = {name: b'Fictional checked operator bytes.\n' for name in act.ALLOWED}
        files.update({'rebuild/ops/legacy_model_activation.py': b'Fictional unchanged primitive.\n',
                      'rebuild/public.py': b'Fictional compatible application.\n',
                      'scripts/check-citation.sh': b'_RA_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/runs-api.sh"\n. "$_RA_LIB"\n[ "$FIXTURE" = "checked" ] || exit 41\n',
                      'scripts/lib/runs-api.sh': b'FIXTURE=checked\n'})
        installed = {'rebuild/public.py': files['rebuild/public.py']}
        for tree, population in ((operator, files), (root, installed)):
            for name, raw in population.items():
                path = tree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                for parent in (path.parent, *path.parent.parents):
                    parent.chmod(0o755)
                    if parent == root:
                        break
                path.write_bytes(raw)
                path.chmod(0o644)
        canary = root / 'private.env'
        canary.write_bytes(b'PRIVATE-FICTIONAL-CANARY-MUST-NOT-BE-READ')
        canary.chmod(0o600)
        contract = {'approved_source_paths': sorted(act.ALLOWED)}
        declaration_commit = '9' * 40
        def git(tree, *args):
            population = files if tree == operator else installed
            if args == ('rev-parse', 'HEAD'):
                return (TARGET if tree == operator else act.INSTALLED).encode()
            if args[0] in ('status', 'merge-base'):
                return b''
            if args[0] == 'diff':
                return ('\n'.join(sorted(act.ALLOWED)) + '\n').encode()
            if args[0] == 'branch':
                return b'main'
            if args == ('rev-parse', 'origin/main'):
                return TARGET.encode()
            if args[0] == 'ls-files':
                if '--stage' in args:
                    separator = '\0' if '-z' in args else '\n'
                    return ''.join('100644 ' + 'a' * 40 + ' 0\t' + name + separator for name in population).encode()
                return ('\n'.join(population) + '\n').encode()
            if args[0] == 'log':
                return declaration_commit.encode()
            if args[0] == 'show':
                return population[args[-1].split(':', 1)[1]]
            raise AssertionError(args)
        stack = ExitStack()
        for module in (act, act.source_files):
            stack.enter_context(patch.object(module, 'ROOT', root))
            stack.enter_context(patch.object(module, 'SOURCE', operator))
        stack.enter_context(patch.object(act.old, 'git', side_effect=git))
        stack.enter_context(patch.object(act, 'FROZEN_OPERATOR', act.sha(files['rebuild/ops/legacy_model_activation.py'])))
        stack.enter_context(patch.object(act, 'FROZEN_VERIFIER', act.sha(b'fictional frozen verifier')))
        stack.enter_context(patch.object(act, 'contract_from_bytes', return_value=contract))
        stack.enter_context(patch.dict(os.environ, RULED_MUTATION_DECLARATION=act.DECL,
                                      RULED_MUTATION_DECL_COMMIT=declaration_commit))
        return stack, operator, files, installed, canary, contract

    def test_fixture_public_parents_are_explicit_under_private_process_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            previous = os.umask(0o077)
            try:
                stack, operator, files, installed, canary, contract = self.fixture(Path(temporary))
            finally:
                os.umask(previous)
            for tree, population in ((operator, files), (Path(temporary), installed)):
                for relative in population:
                    path = tree / relative
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                    for parent in (path.parent, *path.parent.parents):
                        self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)
                        if parent == Path(temporary):
                            break
            self.assertEqual(stat.S_IMODE(canary.stat().st_mode), 0o600)
            with stack, patch.object(act.source_files, 'sealed_citation') as citation, \
                 patch.object(act, 'protected', return_value=b'fictional frozen verifier'):
                act.source_gate(TARGET, contract)
                self.assertEqual(citation.call_count, 3)

    def test_all_operator_and_public_installed_bytes_are_admitted_before_sealed_citations_and_private_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            stack, operator, files, installed, _, contract = self.fixture(Path(temporary))
            calls = []
            native_reader = act.operator_source_bytes
            def read(relative, *args, **kwargs):
                calls.append(('source', relative))
                return native_reader(relative, *args, **kwargs)
            def cite(top, library, target):
                self.assertEqual(top, files['scripts/check-citation.sh'])
                self.assertEqual(library, files['scripts/lib/runs-api.sh'])
                self.assertEqual(len([entry for entry in calls if entry[0] == 'source']), len(files) + len(installed))
                self.assertNotIn(('private', None), calls)
                calls.append(('citation', target))
            def private(*args):
                self.assertEqual([entry[1] for entry in calls if entry[0] == 'citation'], [TARGET, act.PREPARED, act.INSTALLED])
                calls.append(('private', None))
                return b'fictional frozen verifier'
            with stack, patch.object(act, 'operator_source_bytes', side_effect=read), \
                 patch.object(act.source_files, 'sealed_citation', side_effect=cite), \
                 patch.object(act, 'protected', side_effect=private):
                self.assertEqual(act.source_gate(TARGET, contract)['changed_paths'], sorted(act.ALLOWED))
            self.assertEqual(calls[-1], ('private', None))

    def test_leaf_symlink_private_leaf_swap_and_parent_link_never_read_canary_or_reach_citation(self):
        for kind in ('leaf-link', 'private-leaf', 'parent-link'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                stack, operator, _, _, canary, contract = self.fixture(Path(temporary))
                public = operator / act.SELF
                if kind == 'parent-link':
                    parent = public.parent
                    parent.rename(parent.with_name('old-ops'))
                    parent.symlink_to(canary.parent, target_is_directory=True)
                else:
                    public.unlink()
                    if kind == 'leaf-link':
                        public.symlink_to(canary)
                    else:
                        canary.replace(public)
                protected_inode = (public if kind == 'private-leaf' else canary).stat().st_ino
                native_read = os.read
                def guard(fd, count):
                    self.assertNotEqual(os.fstat(fd).st_ino, protected_inode, 'private canary bytes read')
                    return native_read(fd, count)
                with stack, patch.object(act.source_files.os, 'read', side_effect=guard), \
                     patch.object(act.source_files, 'sealed_citation') as citation, \
                     patch.object(act, 'protected') as private:
                    with self.assertRaises((OSError, act.Refusal)):
                        act.source_gate(TARGET, contract)
                    citation.assert_not_called()
                    private.assert_not_called()

    def test_source_byte_or_declaration_mismatch_refuses_before_private_evidence_or_citation(self):
        for kind in ('public-bytes', 'declaration'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                stack, operator, _, _, _, contract = self.fixture(Path(temporary))
                if kind == 'public-bytes':
                    (operator / 'rebuild/public.py').write_bytes(b'unreviewed bytes')
                with stack, patch.object(act.source_files, 'sealed_citation') as citation, \
                     patch.object(act, 'protected') as private:
                    if kind == 'declaration':
                        act.contract_from_bytes.return_value = {'different': True}
                    with self.assertRaises(act.Refusal):
                        act.source_gate(TARGET, contract)
                    citation.assert_not_called()
                    private.assert_not_called()

    def test_helper_source_binding_or_native_identity_mismatch_refuses_before_git_or_private_read(self):
        for kind in ('source', 'identity'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                stack, operator, _, _, _, contract = self.fixture(Path(temporary))
                with stack, patch.object(act.source_files, 'sealed_citation') as citation, \
                     patch.object(act, 'protected') as private:
                    if kind == 'source':
                        act.source_files.SOURCE = operator.parent / 'other'
                    else:
                        self.enterContext(patch.object(act.os, 'getuid', return_value=0))
                    with self.assertRaisesRegex(act.Refusal, 'native_source_binding'):
                        act.source_gate(TARGET, contract)
                    act.old.git.assert_not_called()
                    citation.assert_not_called()
                    private.assert_not_called()

    def test_citation_executes_sealed_checked_buffers_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            stack, operator, files, _, _, contract = self.fixture(Path(temporary))
            revisions = []
            def checked_command(argv, cwd=None, pass_fds=()):
                (operator / 'scripts/check-citation.sh').write_bytes(b'exit 77\n')
                (operator / 'scripts/lib/runs-api.sh').write_bytes(b'exit 88\n')
                self.assertEqual(cwd, operator)
                self.assertEqual(len(pass_fds), 2)
                for fd in pass_fds:
                    with self.assertRaises(OSError):
                        os.write(fd, b'unchecked bytes')
                self.assertEqual(os.pread(pass_fds[1], 65536, 0), files['scripts/lib/runs-api.sh'])
                result = subprocess.run(argv, cwd=cwd, pass_fds=pass_fds, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                revisions.append(argv[-1])
                return result.stdout
            with stack, patch.object(act.source_files, 'command', side_effect=checked_command), \
                 patch.object(act, 'protected', return_value=b'fictional frozen verifier'):
                act.source_gate(TARGET, contract)
            self.assertEqual(revisions, [TARGET, act.PREPARED, act.INSTALLED])

    def test_descriptor_reader_uses_explicit_source_not_helpers_default_and_refuses_leaf_read_race(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'public.py'
            source.write_bytes(b'checked public bytes')
            source.chmod(0o644)
            with patch.object(act.source_files, 'SOURCE', root / 'wrong-default'):
                self.assertEqual(act.operator_source_bytes('public.py', tree=root), b'checked public bytes')
            native_read = act.source_files.bytes_at
            def race(fd, maximum=32 * 1024 ** 2):
                raw = native_read(fd, maximum)
                source.unlink()
                source.write_bytes(b'changed same-length!')
                source.chmod(0o644)
                return raw
            with patch.object(act.source_files, 'bytes_at', side_effect=race):
                with self.assertRaisesRegex(act.Refusal, 'public_source_descriptor_refused'):
                    act.operator_source_bytes('public.py', tree=root)


if __name__ == '__main__':
    unittest.main()
