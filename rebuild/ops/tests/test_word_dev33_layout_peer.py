"""Matching/wrong local peer controls; no renderer, document or QA connection."""
import ast
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import struct
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[3]
LITERAL = ROOT / 'rebuild/ops/fixtures/word_dev33_layout_peer.source'
peer = types.ModuleType('dev33_layout_peer_test_literal')
peer.__file__ = str(LITERAL)
exec(compile(LITERAL.read_bytes(), str(LITERAL), 'exec'), peer.__dict__)


class ExpectedRendererPeer(unittest.TestCase):
    def setUp(self):
        self.record = {'pid': 456789, 'uid': 1000, 'start_ticks': 22}
        self.observed = (456789, 1000, 1000)
        self.endpoint = Path('/tmp/not-launched-dev33/layout.sock')
        self.meta = types.SimpleNamespace(st_uid=1000, st_mode=stat.S_IFSOCK | 0o666)
        self.server = Mock(pid=self.record['pid']);self.server.poll.return_value = None
        self.stream = MagicMock()
        self.stream.__enter__.return_value = self.stream
        self.stream.getsockopt.return_value = struct.pack('3i', *self.observed)
        self.plan = {'layout_server_identity': {**self.record, 'socket': str(self.endpoint),
                     'socket_uid': 1000, 'os_peer_authenticated': True},
                     'layout_service_uid': '1000', 'layout_socket': str(self.endpoint)}

    def binding(self, identities=None, socket_meta=None, client_uid=1000):
        with patch.object(peer, 'process_identity', side_effect=identities or [self.record, self.record]), \
             patch.object(peer.os, 'getuid', return_value=client_uid), \
             patch.object(peer.Path, 'lstat', return_value=socket_meta or self.meta), \
             patch.object(peer.Path, 'is_symlink', return_value=False), \
             patch.object(peer.socket, 'socket', return_value=self.stream) as factory:
            result = peer.bind_server(self.server, self.endpoint)
        self.assertEqual(factory.call_count, 1)
        self.stream.settimeout.assert_called_once_with(5)
        self.stream.connect.assert_called_once_with(str(self.endpoint))
        return result

    def test_matching_pid_uid_socket_and_start_time_are_bound(self):
        result = self.binding()
        self.assertEqual(result['pid'], self.record['pid'])
        self.assertEqual(result['uid'], self.record['uid'])
        self.assertEqual(result['start_ticks'], self.record['start_ticks'])
        self.assertEqual(result['socket'], str(self.endpoint))
        self.assertTrue(result['os_peer_authenticated'])
        self.assertEqual(result['document_requests'], 0)
        self.assertEqual(result['provider_calls'], 0)

    def test_wrong_expected_peer_uid_refuses(self):
        self.stream.getsockopt.return_value = struct.pack('3i', self.record['pid'], 1001, 1001)
        with self.assertRaisesRegex(ValueError, 'peer UID differs'):
            self.binding()

    def test_foreign_peer_pid_refuses_even_when_uid_matches(self):
        self.stream.getsockopt.return_value = struct.pack('3i', self.record['pid']+1, 1000, 1000)
        with self.assertRaisesRegex(ValueError, 'not the recorded renderer'):
            self.binding()

    def test_socket_owner_refuses_even_when_peer_matches(self):
        with self.assertRaisesRegex(ValueError, 'peer UID differs'):
            self.binding(socket_meta=types.SimpleNamespace(st_uid=1001, st_mode=stat.S_IFSOCK))

    def test_pid_reuse_during_authentication_refuses(self):
        with self.assertRaisesRegex(ValueError, 'PID/owner changed'):
            self.binding(identities=[self.record, {**self.record, 'start_ticks': 23}])

    def test_normal_client_with_different_owner_refuses_before_socket(self):
        with self.assertRaisesRegex(ValueError, 'different owners'):
            self.binding(client_uid=1001)
        self.stream.connect.assert_not_called()

    def test_exited_server_refuses_before_identity_or_socket(self):
        self.server.poll.return_value = 1
        with patch.object(peer, 'process_identity') as identity, patch.object(peer.socket, 'socket') as factory:
            with self.assertRaisesRegex(ValueError, 'exited before'):
                peer.bind_server(self.server, self.endpoint)
        identity.assert_not_called(); factory.assert_not_called()

    def test_server_exit_after_authentication_refuses(self):
        self.server.poll.side_effect = [None, 1]
        with self.assertRaisesRegex(ValueError, 'exited during'):
            self.binding()

    def test_non_socket_endpoint_refuses_before_connection(self):
        with self.assertRaisesRegex(ValueError, 'not a socket'):
            self.binding(socket_meta=types.SimpleNamespace(st_uid=1000, st_mode=stat.S_IFREG | 0o600))
        self.stream.connect.assert_not_called()

    def test_malformed_os_credentials_refuse(self):
        self.stream.getsockopt.return_value = b'bad'
        with self.assertRaises(struct.error):
            self.binding()

    def bound(self, identities=None, settings=None):
        with patch.object(peer, 'process_identity', side_effect=identities or [self.record, self.record]), \
             patch.object(peer.Path, 'is_symlink', return_value=False), \
             patch.object(peer.Path, 'lstat', return_value=self.meta), \
             patch.object(peer.socket, 'socket', return_value=self.stream):
            return peer.verify_inner(self.plan, settings) if settings is not None else peer.verify_bound(self.plan)

    def test_same_recorded_process_and_exact_inner_settings_pass(self):
        self.bound()
        self.stream.settimeout.assert_called_once_with(5)
        self.stream.connect.assert_called_once_with(str(self.endpoint))
        self.stream.getsockopt.assert_called_once_with(peer.socket.SOL_SOCKET, peer.socket.SO_PEERCRED, 12)

    def test_same_uid_replacement_peer_is_denied_while_recorded_process_is_alive(self):
        self.stream.getsockopt.return_value = struct.pack('3i', self.record['pid']+1, 1000, 1000)
        with self.assertRaisesRegex(ValueError, 'not the recorded renderer'):
            self.bound()

    def test_start_time_change_during_reauthentication_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'PID/owner changed'):
            self.bound(identities=[self.record, {**self.record, 'start_ticks': 23}])

    def test_inner_settings_cannot_hide_same_uid_replacement_peer(self):
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET=str(self.endpoint), QUILLMD_LAYOUT_SERVICE_UID='1000')
        self.stream.getsockopt.return_value = struct.pack('3i', self.record['pid']+1, 1000, 1000)
        with self.assertRaisesRegex(ValueError, 'not the recorded renderer'):
            self.bound(settings=settings)

    def test_malformed_credentials_during_reauthentication_refuse(self):
        self.stream.getsockopt.return_value = b'bad'
        with self.assertRaises(struct.error):
            self.bound()

    def test_empty_inner_uid_original_failure_remains_denied(self):
        self.plan['layout_service_uid'] = ''
        with self.assertRaisesRegex(ValueError, 'Inner QA UID/socket differs'):
            self.bound()

    def test_foreign_inner_uid_is_denied(self):
        self.plan['layout_service_uid'] = '1001'
        with self.assertRaisesRegex(ValueError, 'Inner QA UID/socket differs'):
            self.bound()

    def test_foreign_inner_socket_is_denied(self):
        self.plan['layout_socket'] = '/tmp/another/layout.sock'
        with self.assertRaisesRegex(ValueError, 'Inner QA UID/socket differs'):
            self.bound()

    def test_unsigned_peer_record_cannot_be_used(self):
        self.plan['layout_server_identity']['os_peer_authenticated'] = False
        with self.assertRaisesRegex(ValueError, 'No recorded OS peer'):
            self.bound()

    def test_changed_recorded_server_identity_is_denied(self):
        with patch.object(peer, 'process_identity', return_value={**self.record, 'start_ticks': 24}):
            with self.assertRaisesRegex(ValueError, 'PID/owner changed'):
                peer.verify_bound(self.plan)

    def test_applied_inner_settings_are_recorded_only_when_exact(self):
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET=str(self.endpoint), QUILLMD_LAYOUT_SERVICE_UID='1000')
        with patch.object(peer, 'verify_bound') as bound:
            actual = peer.verify_inner(self.plan, settings)
        bound.assert_called_once_with(self.plan)
        self.assertEqual(actual['uid'], '1000')
        self.assertEqual(actual['socket'], str(self.endpoint))
        self.assertEqual(actual['server_identity'], self.plan['layout_server_identity'])

    def test_applied_empty_uid_original_configuration_remains_denied(self):
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET=str(self.endpoint), QUILLMD_LAYOUT_SERVICE_UID='')
        with patch.object(peer, 'verify_bound'), self.assertRaisesRegex(ValueError, 'Applied inner QA UID/socket differs'):
            peer.verify_inner(self.plan, settings)

    def test_applied_foreign_socket_configuration_remains_denied(self):
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET='/tmp/foreign.sock', QUILLMD_LAYOUT_SERVICE_UID='1000')
        with patch.object(peer, 'verify_bound'), self.assertRaisesRegex(ValueError, 'Applied inner QA UID/socket differs'):
            peer.verify_inner(self.plan, settings)


def local_peer(endpoint, ready):
    """A bounded test-only listener; consumes no bytes or document frames."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.settimeout(10)
        listener.bind(endpoint)
        listener.listen()
        ready.send(True)
        ready.close()
        for _ in range(8):
            try:
                stream, _ = listener.accept()
            except socket.timeout:
                return
            stream.close()


class ActualLocalPeer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qml-peer-')
        self.endpoint = Path(self.temp.name) / 'sock'
        self.children = []
        self.addCleanup(self.clean)

    def clean(self):
        for child in self.children:
            if child.is_alive():
                child.terminate()
            child.join(2)
            if child.is_alive():
                child.kill()
                child.join(2)
            self.assertFalse(child.is_alive())
        self.temp.cleanup()

    def start(self):
        context = multiprocessing.get_context('fork')
        parent, child_pipe = context.Pipe(duplex=False)
        child = context.Process(target=local_peer, args=(str(self.endpoint), child_pipe))
        self.children.append(child)
        child.start()
        child_pipe.close()
        try:
            self.assertTrue(parent.poll(5), 'Bounded local peer start did not complete.')
            self.assertTrue(parent.recv())
        finally:
            parent.close()
        return types.SimpleNamespace(pid=child.pid, poll=lambda: child.exitcode), child

    def plan(self, server):
        identity = peer.bind_server(server, self.endpoint)
        self.assertEqual(identity['uid'], os.getuid())
        return {'layout_server_identity': identity, 'layout_service_uid': str(identity['uid']),
                'layout_socket': str(self.endpoint)}

    def test_real_recorded_peer_passes_bound_and_inner_checks_without_document_bytes(self):
        server, child = self.start()
        plan = self.plan(server)
        peer.verify_bound(plan)
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET=str(self.endpoint), QUILLMD_LAYOUT_SERVICE_UID=plan['layout_service_uid'])
        actual = peer.verify_inner(plan, settings)
        self.assertEqual(actual['server_identity']['pid'], child.pid)
        self.assertEqual(actual['provider_calls'], 0)

    def test_real_same_uid_path_replacement_refuses_while_original_stays_alive(self):
        server, original = self.start()
        plan = self.plan(server)
        self.endpoint.unlink()  # Only this test's owned temporary socket.
        _, replacement = self.start()
        self.assertNotEqual(original.pid, replacement.pid)
        self.assertTrue(original.is_alive())
        with self.assertRaisesRegex(ValueError, 'not the recorded renderer'):
            peer.verify_bound(plan)
        settings = types.SimpleNamespace(QUILLMD_LAYOUT_SOCKET=str(self.endpoint), QUILLMD_LAYOUT_SERVICE_UID=plan['layout_service_uid'])
        with self.assertRaisesRegex(ValueError, 'not the recorded renderer'):
            peer.verify_inner(plan, settings)
        self.assertTrue(original.is_alive())


class ExactSupportedLayoutPreparation(unittest.TestCase):
    def setUp(self):
        literal = ROOT / 'rebuild/ops/fixtures/word_dev33_mixed_consolidation.source'
        self.adapter = types.ModuleType('dev33_supported_metadata_test')
        exec(compile(literal.read_bytes(), str(literal), 'exec'), self.adapter.__dict__)
        self.original_raw = (ROOT / 'docs/rebuild/v1/word-dev33-final-plan-prepared-20261004.json').read_bytes()
        self.original = json.loads(self.original_raw)
        self.derivative_raw = (ROOT / 'docs/rebuild/v1/word-dev33-supported-layout-plan-prepared-20261004.json').read_bytes()
        self.derivative = json.loads(self.derivative_raw)

    def test_derivative_retains_every_original_preparation_value_and_separate_hash(self):
        self.assertEqual(hashlib.sha256(self.original_raw).hexdigest(), self.adapter.ORIGINAL_PREPARED_SHA)
        self.assertEqual(hashlib.sha256(self.derivative_raw).hexdigest(), self.adapter.PREPARED_SHA)
        self.adapter.validate_derivative(self.derivative, self.original)
        self.assertEqual(hashlib.sha256(LITERAL.read_bytes()).hexdigest(), self.adapter.PEER_SHA)

    def test_changed_fixed_threshold_denominator_or_original_member_refuses(self):
        for key in ('thresholds', 'eligible_dev', 'records', 'unchanged_helpers', 'packets'):
            with self.subTest(key=key):
                mutant = copy.deepcopy(self.derivative)
                mutant[key] = []
                with self.assertRaises(self.adapter.IntegrityError):
                    self.adapter.validate_derivative(mutant, self.original)

    def test_exact_driver_copies_bind_before_qa_and_preserve_scorer_and_profile_functions(self):
        current = ROOT / 'docs/rebuild/v1/word-eval/dev33-supported-layout-preparation-v3-20261004'
        originals = {
            'dev_application_gate_v2.py': ROOT / 'docs/rebuild/v1/word-eval/dev-d01-d03-7907ae5a-20261004/dev_application_gate_v2.py.source',
            'dev_application_gate_native_v1.py': ROOT / 'docs/rebuild/v1/word-eval/native-dev-application-preparation-20261004/dev_application_gate_native_v1.py.source',
            'fixed_render_checker.py': ROOT / 'docs/rebuild/v1/word-eval/application-adapter-20261004/fixed_render_checker.py.source',
        }
        for name, row in self.derivative['supported_layout_driver_sources'].items():
            # CI validates tracked literal bytes; the actual supervisor still
            # authenticates the separately declared protected execution paths.
            raw = (current / (name + '.source')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
            if name.startswith('run_'):
                text = raw.decode()
                self.assertLess(text.index("peer_record=peer_namespace['bind_server']"), text.index("command=['python3'"))
                self.assertEqual(text.count("write(out/'plan.json',preparation)"), 1)
            elif name.startswith('dev_'):
                original_ast = ast.parse(originals[name].read_bytes())
                current_ast = ast.parse(raw)
                original_functions = {node.name: ast.dump(node) for node in original_ast.body if isinstance(node, ast.FunctionDef)}
                current_functions = {node.name: ast.dump(node) for node in current_ast.body if isinstance(node, ast.FunctionDef)}
                self.assertEqual(original_functions, current_functions)
                cls = next(node for node in current_ast.body if isinstance(node, ast.ClassDef) and node.name == 'ApplicationGate')
                uid = [kw for kw in cls.decorator_list[0].keywords[0].value.keywords if kw.arg == 'QUILLMD_LAYOUT_SERVICE_UID']
                self.assertEqual(len(uid), 1)
                self.assertEqual(ast.dump(uid[0].value), ast.dump(ast.parse("plan['layout_service_uid']", mode='eval').body))
            else:
                self.assertEqual(hashlib.sha256(raw).hexdigest(), self.adapter.CHECKER_SHA)
                original_functions = {n.name: ast.dump(n) for n in ast.parse(originals[name].read_bytes()).body if isinstance(n, ast.FunctionDef)}
                current_functions = {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
                self.assertEqual(original_functions, current_functions)


if __name__ == '__main__':
    unittest.main()
