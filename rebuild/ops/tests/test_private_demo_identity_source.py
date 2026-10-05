"""Literal new-demo identity runner controls; no account/DB/mail/service action."""
import ast
import contextlib
import copy
from io import StringIO
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import textwrap
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

    def test_replayed_invitation_post_reaches_view_with_same_client_csrf(self):
        # Minimal settings and middleware live in a child, leaving the parent
        # test process's configured settings/application state untouched.
        script = textwrap.dedent(r"""
            import ast, json, re, socket, sys
            from pathlib import Path
            from types import SimpleNamespace
            from django.conf import settings
            settings.configure(SECRET_KEY='offline-synthetic-csrf-control',
                ALLOWED_HOSTS=['testserver'], ROOT_URLCONF=__name__,
                MIDDLEWARE=['django.middleware.csrf.CsrfViewMiddleware'],
                INSTALLED_APPS=[], USE_I18N=False, DEBUG=False)
            import django
            django.setup()
            from django.db.backends.base.base import BaseDatabaseWrapper
            def forbidden(*args, **kwargs):
                raise AssertionError('Unexpected DB/network operation')
            socket.socket.connect = forbidden
            BaseDatabaseWrapper.ensure_connection = forbidden
            from django.http import HttpResponse
            from django.middleware.csrf import get_token
            from django.test import Client
            from django.urls import path
            visits = []
            def login(request):
                visits.append('login')
                return HttpResponse('<input name="csrfmiddlewaretoken" value="' + get_token(request) + '">')
            def closed(request):
                visits.append('closed')
                return HttpResponse(status=404)
            def positive(request):
                visits.append('positive')
                return HttpResponse(status=200)
            urlpatterns = [path('login/', login),
                path('invite/closed-synthetic-token/', closed),
                path('synthetic-positive/', positive)]
            class Served:
                def __init__(self): self.records = []
                def client(self): return Client(enforce_csrf_checks=True)
                def expect(self, client, port, path, status, method='GET', data=None, label=None):
                    assert port == 9160
                    response = client.post(path, data or {}) if method == 'POST' else client.get(path)
                    self.records.append(response.status_code)
                    assert response.status_code == status
                    return response.content
            def require(value, reason):
                assert value, reason
            source = Path(sys.argv[1])
            tree = ast.parse(source.read_text())
            main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
            functions = [node for node in main.body if isinstance(node, ast.FunctionDef) and node.name in ('csrf', 'post')]
            assert len(functions) == 2
            trial = next(node for node in ast.walk(main) if isinstance(node, ast.Try)
                and any(isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                    and any(key.arg == 'label' and isinstance(key.value, ast.Constant)
                        and key.value.value == 'invitation_replay_denied' for key in item.value.keywords)
                    for item in node.body))
            index = next(i for i, item in enumerate(trial.body)
                if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                and any(key.arg == 'label' and isinstance(key.value, ast.Constant)
                    and key.value.value == 'invitation_replay_denied' for key in item.value.keywords))
            replay = trial.body[index + 1:index + 3]
            def context():
                scope = {'re': re, 'auth': SimpleNamespace(require=require), 'confidential': [],
                    'served': Served(), 'route': '/invite/closed-synthetic-token/'}
                exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), scope)
                return scope
            visits.clear(); scope = context()
            try:
                exec(compile('post(served.client(), route, {}, 404)', '<original-empty-post>', 'exec'), scope)
            except AssertionError:
                pass
            else:
                raise AssertionError('Original invalid POST incorrectly reached expected404')
            assert scope['served'].records == [403] and visits == []
            visits.clear(); scope = context()
            exec(compile(ast.Module(body=replay, type_ignores=[]), str(source), 'exec'), scope)
            assert scope['served'].records == [200, 404] and visits == ['login', 'closed']
            visits.clear(); scope = context(); client = scope['served'].client()
            token = scope['csrf'](client, '/login/')
            scope['post'](client, '/synthetic-positive/', {'csrfmiddlewaretoken': token}, 200)
            assert scope['served'].records == [200, 200] and visits == ['login', 'positive']
            print(json.dumps({'original_invalid_post': 403, 'corrected_replay': [200, 404],
                'independent_positive': [200, 200]}))
        """)
        result = subprocess.run([sys.executable, '-B', '-c', script, str(SOURCE)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'original_invalid_post': 403,
            'corrected_replay': [200, 404], 'independent_positive': [200, 200]})

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
