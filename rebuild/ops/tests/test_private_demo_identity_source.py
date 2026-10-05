"""Literal new-demo identity runner controls; no account/DB/mail/service action."""
import ast
import contextlib
import copy
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import private_mail, private_storage

SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/private_demo_identity.source'


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


class DemoIdentityLiteralTests(unittest.TestCase):
    def setUp(self):
        self.runner = runpy.run_path(str(SOURCE))

    def test_default_is_prepared_without_database_network_or_secret_read(self):
        output = StringIO()
        with patch.object(sys, 'argv', ['identity']), contextlib.redirect_stdout(output), \
                patch('socket.socket.connect', side_effect=AssertionError('unexpected network')):
            self.runner['main']()
        result = json.loads(output.getvalue())
        self.assertTrue(result['prepared_only']); self.assertEqual(result['provider_requests'], 0)
        self.assertEqual(result['external_messages'], 0)

    def test_execution_without_exact_prospective_identity_refuses_before_importing_application(self):
        with patch.object(sys, 'argv', ['identity', '--execute']), self.assertRaisesRegex(RuntimeError, 'Complete prospective'):
            self.runner['main']()

    def test_literal_health_gate_accepts_actual_synthetic_surfaces_and_refuses_wrong_identity(self):
        # Compile only the real health response and literal predicate: no app,
        # database, HTTP or credentials are needed to reproduce this refusal.
        tree = ast.parse(SOURCE.read_text())
        gates = [node.args[0] for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
                 and node.args[1].value == 'surface_health_differs']
        self.assertEqual(len(gates), 1)
        predicate = compile(ast.Expression(gates[0]), str(SOURCE), 'eval')
        views = SOURCE.parents[2] / 'core/views.py'
        functions = [copy.deepcopy(node) for node in ast.parse(views.read_text()).body
                     if isinstance(node, ast.FunctionDef) and node.name in ('health', 'health_data_mode')]
        self.assertEqual({node.name for node in functions}, {'health', 'health_data_mode'})
        for node in functions:
            node.decorator_list = []
        release = '7a6d733e9fdd5c4feb353bcc520034e50e5af8e2'
        for surface in ('doctor', 'admin'):
            context = {'settings': SimpleNamespace(SYNTHETIC_ONLY=True, ADMIN_SITE=surface == 'admin',
                                                    RELEASE_SHA=release), 'JsonResponse': lambda value: value}
            exec(compile(ast.Module(body=functions, type_ignores=[]), str(views), 'exec'), context)
            actual = context['health'](None)
            scope = {'health': actual, 'surface': surface, 'args': SimpleNamespace(expected_commit=release)}
            self.assertTrue(eval(predicate, scope))
            for changed in ({**actual, 'data_mode': mode} for mode in ('synthetic', 'real', 'live')):
                self.assertFalse(eval(predicate, {**scope, 'health': changed}))
            for changed in ({**actual, 'release': '0' * 40}, {**actual, 'surface': 'foreign'},
                            {**actual, 'status': 'failed'}, {**actual, 'extra': True}):
                self.assertFalse(eval(predicate, {**scope, 'health': changed}))

    def test_raw_token_routes_are_not_written_to_http_records(self):
        safe = self.runner['safe_route']
        self.assertEqual(safe('/invite/Synthetic-token-do-not-retain/'), '/invite/[redacted]/')
        self.assertEqual(safe('/recovery/confirm/synthetic-uid/synthetic-token/'),
                         '/recovery/confirm/[redacted]/[redacted]/')
        self.assertEqual(safe('/patients/'), '/patients/')

    def test_original_fault_retains_hash_but_redacts_all_known_secret_material(self):
        original = b'Original synthetic URL /invite/synthetic-raw-token/ password=synthetic-password cookie=synthetic-session'
        safe = self.runner['scrub'](original, ['/invite/synthetic-raw-token/', 'synthetic-raw-token',
                                              'synthetic-password', 'synthetic-session'])
        self.assertNotIn(b'synthetic-raw-token', safe); self.assertNotIn(b'synthetic-password', safe)
        self.assertNotIn(b'synthetic-session', safe); self.assertIn(b'Original synthetic URL', safe)
        self.assertEqual(len(self.runner['sha'](original)), 64)

    def test_existing_record_level_matcher_binds_own_record_in_same_file_append_collision(self):
        own = 'identity-own@synthetic.quillmd.invalid'; other = 'identity-other@synthetic.quillmd.invalid'
        token = 'own-synthetic-token-at-least-16'; wrong = 'foreign-synthetic-token-at-least-16'
        def record(address, raw):
            return f'To: {address}\nSubject: Synthetic invitation\n\nhttp://127.0.0.1:9160/invite/{raw}/\n'.encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'mail'; root.mkdir(mode=0o700)
            path = root / 'synthetic.log'; path.write_bytes(record(other, wrong))
            read = Path.read_bytes
            before = self.runner['mail_snapshot'](root, read, require)
            path.write_bytes(path.read_bytes() + private_storage.RECORD_SEPARATOR + record(own, token))
            binding = lambda kind, email: ({'expect_sha256': self.runner['sha'](token.encode())}, None)
            route, notes = self.runner['selected_route'](private_storage, private_mail, binding, 'invite', own,
                before, root, read, require)
            require(route == '/invite/' + token + '/', 'own bound route differs')
            self.assertTrue(notes['token_bound']); self.assertEqual(notes['records_for_others'], 1)
            wrong_binding = lambda kind, email: ({'expect_sha256': self.runner['sha'](wrong.encode())}, None)
            with self.assertRaisesRegex(RuntimeError, 'own_record_mail_binding_refused:token_not_bound'):
                self.runner['selected_route'](private_storage, private_mail, wrong_binding, 'invite', own,
                    before, root, read, require)

    def test_stale_or_multiple_own_messages_and_false_recovery_verifier_refuse(self):
        own = 'identity-own@synthetic.quillmd.invalid'; token = 'own-synthetic-token-at-least-16'
        record = f'To: {own}\n\n/invite/{token}/\n'.encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'mail'; root.mkdir(mode=0o700)
            path = root / 'synthetic.log'; path.write_bytes(record)
            read = Path.read_bytes
            binding = lambda kind, email: ({'expect_sha256': self.runner['sha'](token.encode())}, lambda value: False)
            with self.assertRaisesRegex(RuntimeError, 'own_recovery_verifier_refused'):
                self.runner['selected_route'](private_storage, private_mail, binding, 'invite', own, {}, root, read, require)
            before = self.runner['mail_snapshot'](root, read, require)
            with self.assertRaisesRegex(RuntimeError, 'own_changed_mail_not_unique_or_bounded'):
                self.runner['selected_route'](private_storage, private_mail, binding, 'invite', own, before, root, read, require)
            path.write_bytes(record + private_storage.RECORD_SEPARATOR + record)
            with self.assertRaisesRegex(RuntimeError, 'more_than_one_record'):
                self.runner['selected_route'](private_storage, private_mail, binding, 'invite', own, before, root, read, require)


if __name__ == '__main__':
    unittest.main()
