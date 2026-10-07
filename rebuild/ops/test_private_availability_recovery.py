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
from ops.test_repair_source_permissions import FictionalOS, stat_copy


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
                    'admission': {'allowed_deltas': {'publisher': {'healthy': False,
                        'current_full_row': {'healthy': False}, 'publication': {'invocation': 'a' * 32}}}},
                    'units': {'stopped': True},
                    'external_acknowledgement': {'loaded_state': {'fictional': 'exact'}}, 'storage_admission': {'passed': True}}
        host = SimpleNamespace(state=Mock(return_value={'MainPID': '0', 'ActiveState': 'inactive'}),
                               service=Mock(), worker_configuration=Mock(return_value={'actual_provider_model_verified': False}))
        contract = {'original_policy': {'original_receipts': {'original': 'unchanged'}},
                    'external_configuration_ack': {'qualified': True}, 'installation_qualified': True,
                    'publisher_alignment': act.PUBLISHER_ALIGNMENT, 'ruled_time_budget': act.RULED_BUDGET}
        stack = ExitStack()
        stack.enter_context(patch.object(act, 'OUTPUT', root / 'exclusive-result'))
        stack.enter_context(patch.object(act, 'ATTEMPT', root / 'exclusive-attempt'))
        stack.enter_context(patch.object(act, 'existing_operation_locks', return_value=nullcontext()))
        alignment = {'selected_row_sha256': act.sha(act.encode({'healthy': False})),
                     'selected_comparison_row_sha256': act.sha(act.encode({'healthy': False})),
                     'selected_invocation': 'a' * 32}
        stack.enter_context(patch.object(act, 'aligned_publication_exclusion', return_value=nullcontext(alignment)))
        stack.enter_context(patch.dict(os.environ, {'RULED_ACT_MAX_SECS': '1200'}))
        stack.enter_context(patch.object(act, 'readiness', return_value=prepared))
        stack.enter_context(patch.object(act, 'stopped_scope', return_value=prepared['units']))
        stack.enter_context(patch.object(act.old, 'snapshot', return_value=current))
        stack.enter_context(patch.object(act, 'loaded_external_state', return_value={'fictional': 'exact'}))
        stack.enter_context(patch.object(act, 'forward_source'))
        stack.enter_context(patch.object(act, 'storage_admission', return_value={'passed': True}))
        stack.enter_context(patch.object(act, 'boundary', return_value={'fictional': 'boundary'}))
        stack.enter_context(patch.object(act, 'completion_unit_provenance', return_value={'fictional': 'measured'}))
        stack.enter_context(patch.object(act, 'direct_health', return_value=[]))
        # This wholly invented pipeline exercises preservation/failure ordering,
        # not the unqualified native authorization or actual installation.
        stack.enter_context(patch.object(act, 'NATIVE_APPROVAL_PROTOCOL_QUALIFIED', True))
        stack.enter_context(patch.object(act, 'INSTALLATION_QUALIFIED', True))
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


class CurrentOwnerBoundaryTests(unittest.TestCase):
    def fixture(self, root):
        """Entirely fictional linked receipts; never create a real owner decision."""
        root.chmod(0o700)
        pins = deepcopy(act.CURRENT_OWNER_PINS)
        unit_raw = b'[Service]\nWorkingDirectory=' + pins['new_working_directory'].encode() + b'\n'
        pins['current_unit_sha256'] = act.sha(unit_raw)
        pins['original_metadata']['sha256'] = act.sha(b'fictional original')
        files = []
        for index, path in enumerate(pins['added_files']):
            pins['added_files'][path] = act.sha(('fictional unit ' + str(index)).encode())
            files.append({'path': path, 'sha256': pins['added_files'][path],
                          'metadata': [2050, 10 + index, 0, 0, 0o644, 20, 30, 40]})
        links = []
        for path, target in pins['added_links'].items():
            fixture_path = root / path[1:]; fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.symlink_to(target)
            info = stat_copy(fixture_path.lstat(), st_uid=0, st_gid=0)
            links.append({'path': path, 'target': target, 'metadata': act.full_native_metadata(info)})
        product = {'Id': 'voiceassistmain-product.service', 'WorkingDirectory': pins['new_working_directory'],
            'FragmentPath': act.EXTERNAL_UNIT, 'DropInPaths': '', 'LoadState': 'loaded', 'ActiveState': 'active',
            'SubState': 'running', 'UnitFileState': 'enabled', 'NeedDaemonReload': 'no', 'User': 'voiceassistmain',
            'Group': 'voiceassistmain', 'InvocationID': 'a' * 32, 'MainPID': '123',
            'ExecMainStartTimestamp': 'Wed 2026-10-07 02:00:00 UTC', 'ExecMainStartTimestampMonotonic': '1000'}
        added = []
        for name in ('voiceassist-restaurant-tajrish-20261007-retention.service',
                     'voiceassist-restaurant-tajrish-20261007-retention.timer', 'voiceassistmain-restaurant-voice.service'):
            row = {'Id': name, 'FragmentPath': '/etc/systemd/system/' + name, 'DropInPaths': '',
                'LoadState': 'loaded', 'NeedDaemonReload': 'no', 'UnitFileState': 'enabled',
                'ActiveState': 'active', 'SubState': 'waiting' if name.endswith('.timer') else 'running'}
            if name.endswith('retention.service'):
                row.update(UnitFileState='static', ActiveState='inactive', SubState='dead')
            if name.endswith('.service'):
                row.update(User='voiceassistmain', Group='voiceassistmain',
                    WorkingDirectory='/home/voiceassistmain/VoiceAssistMain' if name.endswith('retention.service') else '/')
            added.append(row)
        parsed = {'manifest': {'source_sha256': pins['source_sha256'], 'installation_id': pins['installation_id'],
                             'release_root': pins['new_working_directory']},
            'installation': {'source_sha256': pins['source_sha256'], 'installation_id': pins['installation_id'],
                'release_root': pins['new_working_directory'], 'main_pid': 123, 'installed': True,
                'calls_started': 0, 'provider_writes': 0, 'nginx_changed': False}}
        pins['manifest']['sha256'] = act.sha(act.encode(parsed['manifest']))
        parsed['installation']['manifest_sha256'] = pins['manifest']['sha256']
        pins['installation']['sha256'] = act.sha(act.encode(parsed['installation']))
        binding = {name: {**pins[name], 'device': 2050, 'inode': 20, 'uid': 0, 'gid': 0, 'mode': '0o644',
                         'size': 20, 'mtime_ns': 30, 'ctime_ns': 40} for name in parsed}
        binding.update(observed_current_source_sha256=pins['source_sha256'], receipt_matches_same_loaded_pid=True)
        product_record = {'path': act.EXTERNAL_UNIT, 'sha256': pins['current_unit_sha256'],
                          'metadata': [2050, 9, 0, 0, 0o644, len(unit_raw), 30, 40]}
        export = {'bounded_collection_complete': True, 'measured_native_checks_complete': True,
            'native_administrator': True, 'missing': [], 'original_baseline_immutable': True,
            'approval_lineage_assessment': 'unassessed', 'service_actions': 0, 'provider_calls': 0,
            'collected_at_utc': '2026-10-07T02:00:00+00:00', 'records': [],
            'original_release': pins['old_working_directory'], 'expected_current_source_sha256': pins['source_sha256'],
            'original_and_observed_unit_evidence': {'original_immutable_unit': {'sha256': pins['original_metadata']['sha256']},
                'observed_current_unit': product_record, 'no_bytes_change_outside_original_working_directory_line': True,
                'original_baseline_replaced': False, 'observed_current_release': pins['new_working_directory']},
            'same_loaded_state': product, 'native_host_proof': {'fictional': 'native identity'},
            'additional_configuration_evidence': {'exact_added_files': files, 'exact_added_enablement_links': links,
                'loaded_states': added, 'template_loaded_state_not_claimed': True}, 'installation_binding': binding}
        pins['native_evidence'] = evidence(root / 'fictional-v15.json', act.encode(export))
        review = {'exports': {'v15': {**pins['native_evidence'], 'collected_at_utc': export['collected_at_utc'], 'record_count': 0}},
            'adjudication': {'current_authorization_verified': False, 'current_source_installation_and_unit_identity_established': True}}
        pins['independent_review'] = evidence(root / 'fictional-review.json', act.encode(review))
        before = {act.EXTERNAL_UNIT: pins['original_metadata'], '/unrelated': {'unchanged': True}}
        current = {act.EXTERNAL_UNIT: act.export_configuration_metadata(product_record),
            **{item['path']: act.export_configuration_metadata(item) for item in files},
            **{item['path']: act.export_configuration_metadata(item, link=True) for item in links},
            '/unrelated': {'unchanged': True}}
        boundary = {'before': {act.EXTERNAL_UNIT: pins['original_metadata']},
                    'after': {k: v for k, v in current.items() if k != '/unrelated'}}
        ack = {'approval_protocol': act.CURRENT_OWNER_PROTOCOL, 'unit_path': act.EXTERNAL_UNIT, 'qualified': True,
               'boundary_sha256': act.sha(act.encode(boundary)),
               'native_evidence': pins['native_evidence'], 'independent_review': pins['independent_review']}
        reply = evidence(root / 'owner-current-configuration-preservation-message-v1.txt', b'Fictional explicit owner response')
        decision = {'format': 1, 'protocol': act.CURRENT_OWNER_PROTOCOL,
            'decision': 'authorize_exact_current_preservation_boundary', 'boundary_sha256': ack['boundary_sha256'],
            'native_evidence': pins['native_evidence'], 'independent_review': pins['independent_review'],
            'owner_reply_evidence': reply, 'historical_deployment_authorization_verified': False,
            'current_owner_preservation_authorized': True, 'original_baseline_replaced': False,
            'voiceassistmain_changes_authorized': False}
        decision_path = root / 'owner-current-configuration-preservation-decision-v1.json'
        ack['owner_decision_evidence'] = evidence(decision_path, act.encode(decision))
        stack = ExitStack()
        stack.enter_context(patch.object(act, 'CURRENT_OWNER_PINS', pins))
        stack.enter_context(patch.object(act, 'OWNER_EVIDENCE_ROOT', root))
        stack.enter_context(patch.object(act, 'OWNER_DECISION_PATH', decision_path))
        public = {act.EXTERNAL_UNIT: unit_raw, **{item['path']: ('fictional unit ' + str(index)).encode()
            for index, item in enumerate(files)}, **{pins[name]['path']: act.encode(parsed[name]) for name in parsed}}
        return stack, before, current, ack, export, decision, public

    def test_exact_seven_preservation_requires_separate_source_gate_and_owner_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, before, current, ack, _, _, _ = self.fixture(Path(temp))
            with stack:
                with self.assertRaisesRegex(act.Refusal, 'current_owner_protocol_unqualified'):
                    act.acknowledge_configuration(before, current, ack)
                with patch.object(act, 'CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED', True):
                    result = act.acknowledge_configuration(before, current, ack)
                self.assertTrue(result['qualified']); self.assertTrue(result['current_owner_preservation_authorized'])
                self.assertFalse(result['historical_deployment_authorization_verified'])
                self.assertEqual(result['configuration_deltas']['before'][act.EXTERNAL_UNIT], before[act.EXTERNAL_UNIT])
                self.assertEqual(len(result['configuration_deltas']['after']), 7)
                self.assertFalse(act.NATIVE_APPROVAL_PROTOCOL_QUALIFIED)

    def test_extra_missing_metadata_changed_or_preexisting_additions_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, before, current, ack, _, _, _ = self.fixture(Path(temp))
            changes = [lambda b, c: c.update(extra={'unapproved': True}),
                lambda b, c: c.pop(next(iter(act.CURRENT_OWNER_PINS['added_links']))),
                lambda b, c: c[act.EXTERNAL_UNIT].update(inode=999),
                lambda b, c: c[act.EXTERNAL_UNIT].update(sha256='0' * 64),
                lambda b, c: b.update({next(iter(act.CURRENT_OWNER_PINS['added_files'])): {'preexisting': True}}),
                lambda b, c: b[act.EXTERNAL_UNIT].update(inode=888),
                lambda b, c: c['/unrelated'].update(unchanged=False)]
            with stack:
                for index, change in enumerate(changes):
                    b, c = deepcopy(before), deepcopy(current); change(b, c)
                    with self.subTest(index=index), self.assertRaises(act.Refusal):
                        act.owner_boundary_configuration(b, c, ack)

    def test_pending_seven_delta_preflight_cannot_infer_approval_from_root_export(self):
        with tempfile.TemporaryDirectory() as temp:
            stack, before, current, ack, _, _, _ = self.fixture(Path(temp))
            original, following, _, _ = population(); original['configuration'] = before; following['configuration'] = current
            with stack:
                result = act.compare_population({'expected_population': original}, following,
                    {'current_database_fingerprint': following['database']}, ack, allow_pending=True)
            self.assertEqual(result['status'], 'RED'); self.assertFalse(result['qualified'])
            self.assertFalse(result['historical_deployment_authorization_verified'])
            self.assertFalse(result['current_owner_preservation_authorized'])

    def test_forged_scope_historical_approval_rejection_and_reply_drift_refuse(self):
        for key, value in (('decision', 'reject'), ('boundary_sha256', '0' * 64),
                ('historical_deployment_authorization_verified', True), ('current_owner_preservation_authorized', False),
                ('voiceassistmain_changes_authorized', True), ('original_baseline_replaced', True), ('format', True)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                stack, before, current, ack, _, decision, _ = self.fixture(Path(temp))
                decision[key] = value
                p = Path(ack['owner_decision_evidence']['path']); p.write_bytes(act.encode(decision))
                ack['owner_decision_evidence']['sha256'] = act.sha(p.read_bytes())
                with stack, patch.object(act, 'CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED', True), \
                     self.assertRaisesRegex(act.Refusal, 'decision_scope'):
                    act.acknowledge_configuration(before, current, ack)
        with tempfile.TemporaryDirectory() as temp:
            stack, before, current, ack, _, decision, _ = self.fixture(Path(temp))
            Path(decision['owner_reply_evidence']['path']).write_bytes(b'Changed or withdrawn fictional reply')
            with stack, patch.object(act, 'CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED', True), \
                 self.assertRaisesRegex(act.Refusal, 'reply_hash'):
                act.acknowledge_configuration(before, current, ack)

    def test_export_and_review_drift_or_wrong_pins_refuse(self):
        for name in ('native_evidence', 'independent_review', 'boundary_sha256'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                stack, before, current, ack, _, _, _ = self.fixture(Path(temp))
                if name == 'boundary_sha256': ack[name] = '0' * 64
                else: Path(ack[name]['path']).write_bytes(b'changed retained proof')
                with stack, self.assertRaises(act.Refusal): act.owner_boundary_configuration(before, current, ack)

    def native_context(self, root, export, public, fault=None):
        class FictionalRootOS:
            def __getattr__(self, name): return getattr(os, name)
            def stat(self, *args, **kwargs): return stat_copy(os.stat(*args, **kwargs), st_uid=0, st_gid=0)
        stack = ExitStack()
        stack.enter_context(patch.object(act, 'CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED', True))
        stack.enter_context(patch.object(act, 'native_boundary_identity', return_value=export['native_host_proof']))
        states = {row['Id']: row for row in [export['same_loaded_state'], *export['additional_configuration_evidence']['loaded_states']]}
        def observe(name, properties):
            value = deepcopy(states[name])
            if fault == 'unit_state' and name.endswith('retention.timer'): value['UnitFileState'] = 'disabled'
            if fault == 'unit_reload': value['NeedDaemonReload'] = 'yes'
            if fault == 'product_invocation' and name == 'voiceassistmain-product.service': value['InvocationID'] = 'b' * 32
            if fault == 'restaurant_activity' and name.endswith('retention.service'): value.update(ActiveState='activating', SubState='start')
            self.assertNotIn('MainPID', properties) if name != 'voiceassistmain-product.service' else None
            return value
        stack.enter_context(patch.object(act, 'owner_unit_state', side_effect=observe))
        real_open = act.source_files.open_root
        stack.enter_context(patch.object(act.source_files, 'open_root', side_effect=lambda _: real_open(root)))
        stack.enter_context(patch.object(act, 'os', FictionalRootOS()))
        def record(fd, path, digest, metadata):
            raw = public[path]
            if fault == 'working_directory' and path == act.EXTERNAL_UNIT: raw = raw.replace(b'WorkingDirectory=', b'WorkingDirectory=/incompatible/')
            if fault == 'manifest' and path == act.CURRENT_OWNER_PINS['manifest']['path']:
                value = json.loads(raw); value['source_sha256'] = '0' * 64; raw = act.encode(value)
            if fault == 'installation' and path == act.CURRENT_OWNER_PINS['installation']['path']:
                value = json.loads(raw); value['installation_id'] = 'wrong'; raw = act.encode(value)
            return raw
        reader = stack.enter_context(patch.object(act, 'owner_public_record', side_effect=record))
        return stack, reader

    def test_native_boundary_reads_manifest_receipt_all_seven_paths_and_only_three_added_units(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); stack, _, _, ack, export, _, public = self.fixture(root)
            native, reader = self.native_context(root, export, public, 'restaurant_activity')
            with stack, native:
                result = act.loaded_external_state(None, ack)
            self.assertEqual(len(result['configuration']), 7)
            self.assertEqual({c.args[1] for c in reader.call_args_list}, set(public))
            self.assertEqual(len(result['additional_unit_configuration']), 3)
            self.assertTrue(all('MainPID' not in row and 'InvocationID' not in row for row in result['additional_unit_configuration'].values()))

    def test_native_wrong_unit_state_invocation_working_directory_manifest_installation_and_link_refuse(self):
        for fault in ('unit_state', 'unit_reload', 'product_invocation', 'working_directory', 'manifest', 'installation', 'link'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); stack, _, _, ack, export, _, public = self.fixture(root)
                if fault == 'link':
                    link = root / next(iter(act.CURRENT_OWNER_PINS['added_links']))[1:]
                    link.unlink(); link.symlink_to('/wrong/target')
                native, _ = self.native_context(root, export, public, fault)
                with stack, native, self.assertRaises(act.Refusal): act.loaded_external_state(None, ack)

    def test_declaration_and_execute_share_one_source_installation_qualification_constant(self):
        raw = (act.SOURCE / act.DECL).read_bytes()
        marker = b'<!-- private-availability-contract -->\n```json\n'
        head, tail = raw.split(marker, 1); body, end = tail.split(b'\n```', 1); contract = json.loads(body)
        with patch.object(act, 'original_qualified_policy', return_value=contract['original_policy']):
            self.assertFalse(act.contract_from_bytes(raw)['installation_qualified'])
            contract['installation_qualified'] = True
            qualified = head + marker + act.encode(contract) + b'\n```' + end
            with self.assertRaisesRegex(act.Refusal, 'prospective_scope'): act.contract_from_bytes(qualified)
            with patch.object(act, 'INSTALLATION_QUALIFIED', True):
                self.assertTrue(act.contract_from_bytes(qualified)['installation_qualified'])
            with patch.object(act, 'CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED', True), \
                 self.assertRaisesRegex(act.Refusal, 'authorization_protocol_unqualified'):
                act.complete_recovery(TARGET, contract, {}, host=None, backup=None, storage=None, exclusion=None, env_writer=None)

    def test_native_public_reader_rejects_bad_metadata_links_bytes_and_same_bytes_path_swap(self):
        class FictionalRootOS:
            def __getattr__(self, name): return getattr(os, name)
            def fstat(self, fd): return stat_copy(os.fstat(fd), st_uid=0, st_gid=0)
        for fault in ('none', 'private_mode', 'hardlink', 'symlink', 'bytes', 'path_swap'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); file = root / act.EXTERNAL_UNIT[1:]
                file.parent.mkdir(parents=True); file.write_bytes(b'fictional public unit'); file.chmod(0o644)
                pins = deepcopy(act.CURRENT_OWNER_PINS); pins['current_unit_sha256'] = act.sha(file.read_bytes())
                expected = act.full_native_metadata(stat_copy(file.stat(), st_uid=0, st_gid=0))
                if fault == 'private_mode': file.chmod(0o600)
                if fault == 'hardlink': os.link(file, file.with_name('another-link'))
                if fault == 'symlink': file.unlink(); file.symlink_to(file.with_name('another-link'))
                if fault == 'bytes':
                    file.write_bytes(b'different source bytes')
                    expected = act.full_native_metadata(stat_copy(file.stat(), st_uid=0, st_gid=0))
                real_read = act.source_files.bytes_at
                def read(fd, maximum):
                    raw = real_read(fd, maximum)
                    if fault == 'path_swap':
                        other = file.with_name('replacement'); other.write_bytes(raw); other.chmod(0o644)
                        os.replace(other, file)
                    return raw
                with patch.object(act, 'os', FictionalRootOS()), patch.object(act, 'CURRENT_OWNER_PINS', pins), \
                     patch.object(act.source_files, 'bytes_at', side_effect=read) as reader, \
                     act.source_files.open_root(root) as fd:
                    if fault == 'none':
                        self.assertEqual(act.owner_public_record(fd, act.EXTERNAL_UNIT, pins['current_unit_sha256'], expected),
                                         b'fictional public unit')
                    else:
                        with self.assertRaises((act.Refusal, act.source_files.Refusal, OSError)):
                            act.owner_public_record(fd, act.EXTERNAL_UNIT, pins['current_unit_sha256'], expected)
                        if fault in ('private_mode', 'hardlink', 'symlink'): reader.assert_not_called()


class NaturalPublisherSequencingTests(unittest.TestCase):
    def test_frozen_id_spelling_admits_selected_row_but_real_row_drift_refuses(self):
        _, observed = self.observations()
        native = observed['row']
        alignment = {'selected_row_sha256': act.sha(act.encode(native)),
            'selected_comparison_row_sha256': act.sha(act.encode(act.selected_publisher_comparison_row(native))),
            'selected_invocation': 'b' * 32}
        for fault in (None, 'id', 'computed_at', 'payload'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                stack, prepared, host, contract = AvailabilityRecoveryTests().fixture_recovery(Path(temp))
                admitted = act.selected_publisher_comparison_row(native)
                if fault == 'id': admitted['id'] = '2'
                elif fault == 'computed_at': admitted['computed_at'] = '2026-10-07T02:05:00.123451+00:00'
                elif fault == 'payload': admitted['payload'] = {'changed': 'actual field'}
                prepared['admission']['allowed_deltas']['publisher'] = {
                    'current_full_row': admitted, 'publication': {'invocation': 'b'*32}}
                with stack, patch.object(act, 'aligned_publication_exclusion', return_value=nullcontext(alignment)):
                    if fault:
                        with self.assertRaisesRegex(act.Refusal, 'admitted_selected_publication_identity'):
                            act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                                exclusion=SimpleNamespace(bind_runtime=Mock()), env_writer=None, preflight=True)
                    else:
                        result = act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                            exclusion=SimpleNamespace(bind_runtime=Mock()), env_writer=None, preflight=True)
                        self.assertTrue(result['complete'])
                    self.assertFalse(act.OUTPUT.exists()); self.assertFalse(act.ATTEMPT.exists())
                    host.service.assert_not_called()

    def test_comparison_only_bigint_spelling_preserves_all_eleven_fields(self):
        _, observed = self.observations()
        native = observed['row']; original = deepcopy(native)
        expected = {**native, 'id': '1'}
        self.assertEqual(act.selected_publisher_comparison_row(native), expected)
        self.assertEqual(native, original)
        self.assertNotEqual(act.sha(act.encode(native)), act.sha(act.encode(expected)))
        for field in act.PUBLISHER_ROW_FIELDS:
            changed = deepcopy(native)
            changed[field] = 2 if field == 'id' else {'changed': field}
            self.assertNotEqual(act.sha(act.encode(act.selected_publisher_comparison_row(changed))),
                                act.sha(act.encode(expected)))
        maximum = {**native, 'id': (1 << 63) - 1}
        self.assertEqual(act.selected_publisher_comparison_row(maximum)['id'], str((1 << 63) - 1))

    def test_bool_float_text_missing_extra_and_non_bigint_ids_refuse(self):
        _, observed = self.observations()
        for value in (True, False, 1.0, '1', '01', '-1', None, 0, -1, 1 << 63):
            with self.subTest(value=value), self.assertRaisesRegex(act.Refusal, 'comparison_id'):
                act.selected_publisher_comparison_row({**observed['row'], 'id': value})
        for row in ({key: value for key, value in observed['row'].items() if key != 'payload'},
                    {**observed['row'], 'extra': 'unexplained'}):
            with self.assertRaisesRegex(act.Refusal, 'comparison_id'):
                act.selected_publisher_comparison_row(row)

    def observations(self):
        row = {'id': 1, 'created_at': '2026-09-30T00:00:00+00:00', 'key': 'backup',
            'condition': 'expired', 'severity': 'error', 'healthy': False, 'action': 'renew',
            'payload': {'fictional': 'retained input'}, 'computed_at': '2026-10-07T02:00:00+00:00',
            'published_at': '2026-10-07T02:00:00.200000+00:00', 'expected_interval_seconds': 300}
        unit = {'ActiveState': 'failed', 'SubState': 'failed', 'MainPID': '0', 'LoadState': 'loaded',
            'FragmentPath': '/etc/systemd/system/' + act.PUBLISHER, 'DropInPaths': '',
            'NeedDaemonReload': 'no', 'InvocationID': 'a' * 32, 'Result': 'exit-code',
            'ExecMainStatus': '1', 'ExecMainStartTimestamp': 'Wed 2026-10-07 02:00:00 UTC',
            'ExecMainExitTimestamp': 'Wed 2026-10-07 02:00:01 UTC'}
        timer = {'ActiveState': 'active', 'SubState': 'waiting', 'LoadState': 'loaded',
            'UnitFileState': 'enabled', 'FragmentPath': '/etc/systemd/system/' + act.PUBLISHER_TIMER,
            'DropInPaths': '', 'NeedDaemonReload': 'no'}
        before = {'row': row, 'unit': unit, 'timer': timer, 'journal': [], 'coherent_unit': True}
        after = deepcopy(before)
        after['row'].update(computed_at='2026-10-07T02:05:00.123450+00:00',
                            published_at='2026-10-07T02:05:00.200000+00:00')
        after['unit'].update(InvocationID='b' * 32, ExecMainStartTimestamp='Wed 2026-10-07 02:05:00 UTC',
                             ExecMainExitTimestamp='Wed 2026-10-07 02:05:01 UTC')
        after['journal'] = [('b' * 32, 'Published backup status: expired (error).')]
        return before, after

    def test_natural_unhealthy_publication_is_verified_without_changing_health(self):
        before, after = self.observations()
        deferred = deepcopy(after)
        deferred['row'] = deepcopy(before['row'])
        observe = Mock(side_effect=[before, deferred, after])
        with patch.object(act.time, 'sleep') as sleep:
            result = act.await_natural_publication({'publisher_alignment': act.PUBLISHER_ALIGNMENT}, observe)
        self.assertTrue(result['publication']['publication_verified'])
        self.assertFalse(result['publication']['backup_healthy'])
        self.assertEqual(result['publication']['exit']['status'], '1')
        self.assertEqual(observe.call_count, 3)
        sleep.assert_called_once_with(1)

    def test_real_identity_source_invocation_and_journal_faults_refuse(self):
        before, after = self.observations()
        changes = [lambda v: v['row'].update(id=2), lambda v: v['row'].update(expected_interval_seconds=301),
            lambda v: v['row'].update(extra='unknown'), lambda v: v.update(journal=[]),
            lambda v: v['row'].update(computed_at='2026-10-07T02:05:10+00:00'),
            lambda v: v['unit'].update(InvocationID='bad'), lambda v: v['unit'].update(ExecMainStatus='0'),
            lambda v: v['journal'].append(('b' * 32, 'CommandError fictional'))]
        for index, change in enumerate(changes):
            wrong = deepcopy(after); change(wrong)
            with self.subTest(index=index), self.assertRaises((act.Refusal, act.publisher_judge.VerificationFailure)):
                act.await_natural_publication({'publisher_alignment': act.PUBLISHER_ALIGNMENT},
                                               Mock(side_effect=[before, wrong]))

    def test_running_to_completed_to_waiting_transition_selects_only_stable_boundary(self):
        before, after = self.observations()
        running = deepcopy(after)
        running['unit'].update(ActiveState='activating', SubState='start', MainPID='123')
        running['timer']['SubState'] = 'running'
        completed_running = deepcopy(after); completed_running['timer']['SubState'] = 'running'
        observe = Mock(side_effect=[before, running, completed_running, after, after])
        with patch.object(act.time, 'sleep') as sleep:
            selected = act.await_natural_publication({'publisher_alignment': act.PUBLISHER_ALIGNMENT}, observe)
        self.assertEqual(selected['timer']['SubState'], 'waiting')
        self.assertEqual(observe.call_count, 4)
        self.assertEqual(sleep.call_count, 2)
        with patch.object(act, 'existing_operation_locks', return_value=nullcontext()), \
             patch.object(act, 'storage_admission', return_value={}), \
             patch.object(act, 'publisher_unit_sources', return_value={'same': True}), \
             patch.object(act, 'publisher_observer', return_value=observe), \
             patch.object(act, 'await_natural_publication', return_value=selected):
            with act.aligned_publication_exclusion(TARGET, {}, None,
                    SimpleNamespace(hold=lambda _: nullcontext()), SimpleNamespace(remaining=Mock())) as proof:
                self.assertEqual(proof['selected_invocation'], 'b' * 32)
                self.assertEqual(proof['selected_row_sha256'], act.sha(act.encode(selected['row'])))
                self.assertEqual(proof['selected_comparison_row_sha256'],
                                 act.sha(act.encode({**selected['row'], 'id': '1'})))
        self.assertEqual(observe.call_count, 5)

    def test_natural_wait_uses_monotonic_deadline_and_does_not_retry_full_admission(self):
        before, after = self.observations()
        clock = [0]
        def sleep(seconds): clock[0] += seconds
        with patch.object(act.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(act.time, 'sleep', side_effect=sleep), \
             patch.object(act, 'readiness', side_effect=AssertionError('no admission retry')):
            observe = Mock(return_value=before)
            with self.assertRaisesRegex(act.Refusal, 'natural_publication_timeout'):
                act.await_natural_publication({'publisher_alignment': act.PUBLISHER_ALIGNMENT}, observe)
            self.assertEqual(clock[0], 360)
            self.assertEqual(observe.call_count, 361)
        count = [0]
        def slow_observe():
            count[0] += 1
            if count[0] == 2:
                clock[0] = 361
                return after
            return before
        clock[0] = 0
        with patch.object(act.time, 'monotonic', side_effect=lambda: clock[0]), \
             self.assertRaisesRegex(act.Refusal, 'natural_publication_timeout'):
            act.await_natural_publication({'publisher_alignment': act.PUBLISHER_ALIGNMENT},
                slow_observe)

    def test_operation_locks_precede_natural_tick_and_publication_hold_covers_admission(self):
        from contextlib import contextmanager
        events = []
        @contextmanager
        def scope(name):
            events.append(name + ':enter')
            try: yield
            finally: events.append(name + ':exit')
        _, selected = self.observations()
        selected['publication'] = {'invocation': 'b' * 32}
        budget = SimpleNamespace(remaining=Mock())
        with patch.object(act, 'existing_operation_locks', side_effect=lambda: scope('four-input-locks')), \
             patch.object(act, 'storage_admission', return_value={'passed': True}), \
             patch.object(act, 'publisher_unit_sources', return_value={'two': 'exact public units'}), \
             patch.object(act, 'publisher_observer', return_value=lambda: selected), \
             patch.object(act, 'await_natural_publication', side_effect=lambda *a: events.append('natural-tick') or selected):
            exclusion = SimpleNamespace(hold=lambda owner: scope('publication-hold'))
            with act.aligned_publication_exclusion(TARGET, {}, None, exclusion, budget) as proof:
                events.append('full-admission')
                self.assertEqual(proof['selected_invocation'], 'b' * 32)
                self.assertEqual(proof['manual_publications'], 0)
        self.assertEqual(events, ['four-input-locks:enter', 'natural-tick', 'publication-hold:enter',
                                 'full-admission', 'publication-hold:exit', 'four-input-locks:exit'])

    def test_any_selected_component_or_public_unit_drift_refuses_before_admission(self):
        _, selected = self.observations(); selected['publication'] = {'invocation': 'b' * 32}
        for name in ('row', 'unit', 'timer', 'journal', 'unit_source'):
            current = deepcopy(selected)
            if name == 'journal': current[name].append(('b' * 32, 'additional'))
            elif name != 'unit_source': current[name]['unexpected'] = True
            sources = [{'same': True}, {'changed': True}] if name == 'unit_source' else [{'same': True}] * 2
            with self.subTest(name=name), patch.object(act, 'existing_operation_locks', return_value=nullcontext()), \
                 patch.object(act, 'storage_admission', return_value={}), \
                 patch.object(act, 'publisher_unit_sources', side_effect=sources), \
                 patch.object(act, 'publisher_observer', return_value=lambda: current), \
                 patch.object(act, 'await_natural_publication', return_value=selected), \
                 self.assertRaises(act.Refusal):
                with act.aligned_publication_exclusion(TARGET, {}, None,
                        SimpleNamespace(hold=lambda _: nullcontext()), SimpleNamespace(remaining=Mock())):
                    self.fail('must not reach admission')

    def test_each_publisher_poll_opens_fresh_readonly_snapshot_with_only_owned_reads(self):
        import psycopg
        _, selected = self.observations()
        conns = [Mock(), Mock()]
        for conn in conns:
            conn.__enter__ = Mock(return_value=conn); conn.__exit__ = Mock(return_value=False)
            conn.execute.return_value.fetchone.return_value = {'current_user': 'quillmd_backup',
                'current_database': 'quillmd_fresh', 'read_only': 'on'}
            conn.execute.return_value.fetchall.return_value = [{'row': selected['row']}]
        def properties(unit, names):
            return selected['timer'] if unit == act.PUBLISHER_TIMER else selected['unit']
        raw = act.encode({'_SYSTEMD_INVOCATION_ID': 'b' * 32, 'MESSAGE': selected['journal'][0][1]})
        backup = SimpleNamespace(source_options=Mock(return_value={'dbname': 'fictional'}))
        with patch.object(psycopg, 'connect', side_effect=conns) as connect, \
             patch.object(act, 'own_unit_properties', side_effect=properties) as show, \
             patch.object(act.old, 'command', return_value=raw) as command:
            observe = act.publisher_observer(backup)
            self.assertEqual(observe(), observe())
        self.assertEqual(connect.call_count, 2)
        self.assertTrue(all(call.kwargs['connect_timeout'] == 10 for call in connect.call_args_list))
        for conn in conns:
            self.assertEqual([c.args[0] for c in conn.execute.call_args_list], [
                'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY', "SET LOCAL timezone='UTC'",
                "SET LOCAL statement_timeout='10s'",
                "SELECT current_user,current_database(),current_setting('transaction_read_only') AS read_only",
                "SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='backup'"])
        self.assertEqual({c.args[0] for c in show.call_args_list}, {act.PUBLISHER, act.PUBLISHER_TIMER})
        self.assertTrue(all(c.args[0][:3] == ['journalctl', '-u', act.PUBLISHER] for c in command.call_args_list))

    def test_native_completion_preserves_legacy_map_and_requires_measured_stable_uuid(self):
        legacy = {unit: {'ActiveState': 'active', 'SubState': 'running', 'MainPID': str(100 + index),
            'FragmentPath': '/etc/systemd/system/' + unit, 'DropInPaths': '', 'UnitFileState': 'enabled',
            'ExecMainStartTimestampMonotonic': str(200 + index)} for index, unit in enumerate(act.old.UNITS)}
        original = deepcopy(legacy)
        measured = {unit: {**state, 'InvocationID': str(index + 1) * 32, 'NeedDaemonReload': 'no'}
                    for index, (unit, state) in enumerate(legacy.items())}
        host = SimpleNamespace(state=lambda unit: legacy[unit])
        with patch.object(act, 'own_unit_properties', side_effect=lambda unit, _: measured[unit]):
            self.assertEqual(act.completion_unit_provenance(host, legacy), measured)
        self.assertEqual(legacy, original)
        for field, value in (('InvocationID', ''), ('NeedDaemonReload', 'yes'), ('MainPID', '999')):
            wrong = deepcopy(measured); wrong[act.old.UNITS[0]][field] = value
            with self.subTest(field=field), patch.object(act, 'own_unit_properties', side_effect=lambda unit, _: wrong[unit]), \
                 self.assertRaises(act.Refusal):
                act.completion_unit_provenance(host, legacy)
        first = measured[act.old.UNITS[0]]
        with patch.object(act, 'own_unit_properties', side_effect=[first, {**first, 'InvocationID': 'f' * 32}]), \
             self.assertRaisesRegex(act.Refusal, 'observation_race'):
            act.completion_unit_provenance(host, legacy)

    def test_owned_public_unit_sources_refuse_private_mode_link_content_and_path_swap(self):
        class FictionalRootOS:
            def __getattr__(self, name): return getattr(os, name)
            def fstat(self, fd): return stat_copy(os.fstat(fd), st_uid=0, st_gid=0)
        for fault in ('none', 'private_mode', 'hardlink', 'symlink', 'content', 'path_swap'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); root.chmod(0o755)
                pins = {act.PUBLISHER: act.sha(b'fictional service'), act.PUBLISHER_TIMER: act.sha(b'fictional timer')}
                for name, raw in ((act.PUBLISHER, b'fictional service'), (act.PUBLISHER_TIMER, b'fictional timer')):
                    (root / name).write_bytes(raw); (root / name).chmod(0o644)
                file = root / act.PUBLISHER
                if fault == 'private_mode': file.chmod(0o600)
                if fault == 'hardlink': os.link(file, root / 'another-link')
                if fault == 'symlink': file.unlink(); file.symlink_to(root / act.PUBLISHER_TIMER)
                if fault == 'content': file.write_bytes(b'different actual source')
                real_open_root, real_bytes = act.source_files.open_root, act.source_files.bytes_at
                def bytes_at(fd, maximum):
                    raw = real_bytes(fd, maximum)
                    if fault == 'path_swap':
                        replacement = root / 'replacement'; replacement.write_bytes(raw); replacement.chmod(0o644)
                        os.replace(replacement, file)
                    return raw
                with patch.object(act, 'os', FictionalRootOS()), \
                     patch.object(act.source_files, 'open_root', side_effect=lambda _: real_open_root(root)), \
                     patch.object(act, 'PUBLISHER_UNIT_PINS', pins), \
                     patch.object(act.source_files, 'bytes_at', side_effect=bytes_at) as read:
                    if fault == 'none':
                        proof = act.publisher_unit_sources()
                        self.assertEqual({name: value['sha256'] for name, value in proof.items()}, pins)
                    else:
                        with self.assertRaises((act.Refusal, act.source_files.Refusal, OSError)):
                            act.publisher_unit_sources()
                        if fault in ('private_mode', 'hardlink', 'symlink'): read.assert_not_called()

    def test_explicit_outer_budget_and_stage_elapsed_time_refuse_insufficient_time(self):
        contract = {'ruled_time_budget': act.RULED_BUDGET}
        for value in ('', '1199', '1200.0', '3600'):
            with self.subTest(value=value), patch.dict(os.environ, {'RULED_ACT_MAX_SECS': value}), \
                 self.assertRaisesRegex(act.Refusal, 'explicit_ruled_time_budget'):
                act.RuledBudget(contract)
        clock = [0]
        with patch.dict(os.environ, {'RULED_ACT_MAX_SECS': '1200'}), \
             patch.object(act.time, 'monotonic', side_effect=lambda: clock[0]):
            budget = act.RuledBudget(contract)
            with self.assertRaisesRegex(act.Refusal, 'stage_time_budget'):
                with budget.stage('full_readiness', 270): clock[0] = 91
            clock[0] = 931
            with self.assertRaisesRegex(act.Refusal, 'budget_remaining'): budget.remaining(270)

    def test_failed_full_admission_or_selected_row_mismatch_has_no_outputs_or_actions(self):
        for mismatch in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                stack, prepared, host, contract = AvailabilityRecoveryTests().fixture_recovery(Path(temp))
                if mismatch: prepared['admission']['allowed_deltas']['publisher']['current_full_row']['changed'] = True
                with stack, patch.object(act, 'readiness', side_effect=None if mismatch else act.Refusal('meaningful_failure'),
                                         return_value=prepared) as readiness, self.assertRaises(act.Refusal):
                    try:
                        act.complete_recovery(TARGET, contract, {}, host=host, backup=None, storage=None,
                            exclusion=SimpleNamespace(bind_runtime=Mock()), env_writer=None)
                    finally:
                        readiness.assert_called_once()
                        self.assertFalse(act.OUTPUT.exists()); self.assertFalse(act.ATTEMPT.exists())
                        host.service.assert_not_called()


if __name__ == '__main__':
    unittest.main()
