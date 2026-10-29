"""Unit tests for ops/verify_login.py: a loopback stand-in for CPT Studio's sign-in, session and sign-out views.

The stand-in follows studio/views.py login_view and logout_view and studio/api.py session (the contract test below
holds the tool's constants to those files): a CSRF cookie and a form token on GET /login/, the token and the cookie
checked on each POST with the Origin header, a redirect to "/" and a session cookie on a good sign-in (the CSRF cookie
rotated), the session served as JSON, 401 without one, and a sign-out that ends the session and deletes its cookie.
Each broken shape the tool must catch is a switch on it. Nothing leaves the loopback.

    cd cpt-studio && python3 -m unittest discover -s ops -p 'test_verify_login.py' -v
"""
import html
import importlib.util
import io
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, quote, quote_plus

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location('cpt_verify_login', HERE / 'verify_login.py')
vl = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_login'] = vl
_spec.loader.exec_module(vl)

USERNAME = 'demo-reviewer'
# Characters a form, a URL, HTML and JSON each encode differently, so every form of it is looked for in the outputs.
PASSWORD = 'Synthetic-demo pass&+%<>"\'é/=?-2026'
WORKSPACE = 'Gastroenterology'
EXPECTED = ['GET /login/', 'POST /login/', 'GET /api/session', 'POST /logout/', 'GET /api/session']
LOGIN_PAGE = ('<!doctype html><html><body class="login-body"><main class="login-card">{error}'
              '<form class="login-form" method="post" action="">{token}'
              '<input type="hidden" name="next" value="/">'
              '<label class="field-label">Username<input name="username" value="{username}"></label>'
              '<label class="field-label">Password<input name="password" type="password"></label>'
              '<button class="button primary" type="submit">Sign in</button></form></main></body></html>')


def account(**overrides):
    return {'password': PASSWORD, 'actor_kind': 'human', 'role': 'reviewer', 'can_review': True, 'workspace': WORKSPACE,
            'label': 'Demo reviewer (synthetic demonstration)', **overrides}


class StubStudio:
    """CPT Studio's sign-in contract on 127.0.0.1, with switches for each broken shape; ``log`` holds every request
    it received (method, path, headers, body)."""

    def __init__(self, accounts=None, tls=None, **behaviour):
        self.accounts = accounts if accounts is not None else {USERNAME: account()}
        self.behaviour = {'login_redirect': '/', 'login_sets_session': True, 'session_status': None, 'session_json': {},
                          'session_username': None, 'logout_status': 302, 'logout_redirect': '/login/',
                          'logout_ends_session': True, 'logout_clears_cookie': True, 'echo_password': False,
                          'page': 'form', 'csrf_cookie': True, **behaviour}
        self.sessions, self.csrf, self.log = {}, set(), []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def do_GET(self):
                stub.handle(self, b'')

            def do_POST(self):
                length = int(self.headers.get('Content-Length') or 0)
                stub.handle(self, self.rfile.read(length))

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):  # a refused TLS handshake is expected in one test
                pass

        self.server = Server(('127.0.0.1', 0), Handler)
        if tls is not None:
            self.server.socket = tls.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'{"https" if tls else "http"}://127.0.0.1:{self.server.server_address[1]}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    # --- the views -------------------------------------------------------------------------------------------------

    def handle(self, request, body):
        cookies = {name: morsel.value for name, morsel in SimpleCookie(request.headers.get('Cookie', '')).items()}
        self.log.append({'method': request.command, 'path': request.path, 'headers': dict(request.headers.items()),
                         'body': body, 'cookies': cookies})
        route = (request.command, request.path)
        if route == ('GET', '/login/'):
            return self.login_page(request)
        if route == ('POST', '/login/'):
            return self.login(request, body, cookies)
        if route == ('GET', '/api/session'):
            return self.session(request, cookies)
        if route == ('POST', '/logout/'):
            return self.logout(request, body, cookies)
        return self.send(request, 404, b'not found')

    def send(self, request, status, body, headers=(), content_type='text/html; charset=utf-8'):
        request.send_response(status)
        request.send_header('Content-Type', content_type)
        request.send_header('Content-Length', str(len(body)))
        for name, value in headers:
            request.send_header(name, value)
        request.end_headers()
        request.wfile.write(body)

    def new_csrf(self):
        secret = secrets.token_hex(16)
        self.csrf.add(secret)
        return secret, ('Set-Cookie', f'cptstudio_csrf={secret}; Max-Age=31449600; Path=/; SameSite=Strict')

    def page(self, token, error='', username=''):
        field = f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">' if token else ''
        # django's templates escape what they echo
        return LOGIN_PAGE.format(error=f'<p class="form-error" role="alert">{html.escape(error)}</p>' if error else '',
                                 token=field, username=html.escape(username)).encode()

    def login_page(self, request):
        if self.behaviour['page'] == 'error':
            return self.send(request, 500, b'<h1>Server Error (500)</h1>')
        secret, header = self.new_csrf()
        token = secret if self.behaviour['page'] != 'no-token' else ''
        html = self.page(token) if self.behaviour['page'] != 'no-form' else b'<html><body>maintenance</body></html>'
        return self.send(request, 200, html, [header] if self.behaviour['csrf_cookie'] else [])

    def csrf_ok(self, request, form, cookies):
        token = (form.get('csrfmiddlewaretoken') or [request.headers.get('X-CSRFToken', '')])[0]
        return (request.headers.get('Origin') == self.base and cookies.get('cptstudio_csrf') in self.csrf
                and token == cookies.get('cptstudio_csrf'))

    def login(self, request, body, cookies):
        form = parse_qs(body.decode(), keep_blank_values=True)
        if not self.csrf_ok(request, form, cookies):
            return self.send(request, 403, b'<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>')
        username, password = form.get('username', [''])[0], form.get('password', [''])[0]
        user = self.accounts.get(username)
        if user is None or user['password'] != password:
            said = 'The username or password is not correct.'
            if self.behaviour['echo_password']:
                said += f' You typed {password}.'
            return self.send(request, 400, self.page(cookies.get('cptstudio_csrf'), said, username))
        headers = []
        if self.behaviour['login_sets_session']:
            sid = secrets.token_hex(16)
            self.sessions[sid] = username
            headers.append(('Set-Cookie', f'cptstudio_session={sid}; HttpOnly; Path=/; SameSite=Strict'))
        headers.append(self.new_csrf()[1])  # django's login() rotates the CSRF token
        return self.send(request, 302, b'', [('Location', self.behaviour['login_redirect']), *headers])

    def session(self, request, cookies):
        username = self.sessions.get(cookies.get('cptstudio_session'))
        if username is None:
            return self.send(request, 401, b'{"error": "Sign in to continue."}', content_type='application/json')
        user = self.accounts[username]
        data = {'user': {'id': 'u-1', 'username': self.behaviour['session_username'] or username, 'label': user['label'],
                         'actor_kind': user['actor_kind'], 'initials': 'DR'},
                'workspace': {'id': 'w-1', 'name': user['workspace'], 'subtitle': 'Synthetic demonstration workspace',
                              'category': {'slug': 'gastroenterology', 'name': 'Gastroenterology',
                                           'profiles_version': 'gi-profiles@3'}},
                'role': user['role'], 'can_review': user['can_review'], 'acknowledgement': '',
                'counts': {'documents': 3, 'queue': 1}, 'synthetic_only': True, 'provider_mode': 'live',
                'release': 'a' * 40, **self.behaviour['session_json']}
        status = self.behaviour['session_status'] or 200
        return self.send(request, status, json.dumps(data).encode(), content_type='application/json')

    def logout(self, request, body, cookies):
        form = parse_qs(body.decode(), keep_blank_values=True)
        if not self.csrf_ok(request, form, cookies):
            return self.send(request, 403, b'<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>')
        if self.behaviour['logout_ends_session']:
            self.sessions.pop(cookies.get('cptstudio_session'), None)
        headers = [('Location', self.behaviour['logout_redirect'])] if self.behaviour['logout_status'] == 302 else []
        if self.behaviour['logout_clears_cookie']:
            headers.append(('Set-Cookie', 'cptstudio_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; '
                                          'Path=/; SameSite=Strict'))
        return self.send(request, self.behaviour['logout_status'], b'', headers)


def private_file(directory, data, mode=0o600, name='credentials.json'):
    path = Path(directory) / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(data if isinstance(data, str) else json.dumps(data))
    os.chmod(path, mode)
    return path


def forms_of(password):
    return {password, quote(password, safe=''), quote_plus(password), json.dumps(password)[1:-1],
            json.dumps(password, ensure_ascii=False)[1:-1]}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix='cpt-verify-login-'))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.credentials = private_file(self.dir, {'username': USERNAME, 'password': PASSWORD})
        # every connection this test makes is to the loopback (the stand-in), or it is refused
        connect = socket.socket.connect

        def loopback_only(sock, address, *args, **kwargs):
            if sock.family != socket.AF_UNIX and address[0] not in ('127.0.0.1', '::1', 'localhost'):
                raise AssertionError(f'a connection off the loopback was attempted: {address!r}')
            return connect(sock, address, *args, **kwargs)
        patcher = mock.patch.object(socket.socket, 'connect', loopback_only)
        patcher.start()
        self.addCleanup(patcher.stop)
        # ... and no name is looked up off the loopback either (a refused URL never reaches a resolver)
        lookup = socket.getaddrinfo

        def loopback_lookup(host, *args, **kwargs):
            if host not in ('127.0.0.1', '::1', 'localhost'):
                raise AssertionError(f'a name lookup off the loopback was attempted: {host!r}')
            return lookup(host, *args, **kwargs)
        resolver = mock.patch.object(socket, 'getaddrinfo', loopback_lookup)
        resolver.start()
        self.addCleanup(resolver.stop)

    def stub(self, **kwargs):
        stub = StubStudio(**kwargs)
        self.addCleanup(stub.close)
        return stub

    def run_tool(self, base, credentials=None, workspace=WORKSPACE, out=None):
        out = out or self.dir / 'evidence'
        argv = ['--base-url', base, '--credentials', str(credentials or self.credentials), '--workspace', workspace,
                '--out', str(out)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = vl.main(argv)
            except SystemExit as exc:  # argparse
                code = exc.code
        path = out / vl.EVIDENCE_NAME
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        return code, stdout.getvalue(), stderr.getvalue(), (json.loads(text) if text else None), text

    def failed(self, evidence):
        return [item['id'] for item in evidence['checks'] if item['status'] == 'fail']

    def requests(self, stub):
        return [f'{entry["method"]} {entry["path"]}' for entry in stub.log]

    def assert_no_password(self, *texts, password=PASSWORD):
        for text in texts:
            for form in forms_of(password):
                self.assertNotIn(form, text)


class SignInTests(Base):
    def test_a_human_reviewer_is_signed_in_read_and_signed_out_with_exactly_five_requests(self):
        stub = self.stub()
        code, out, err, evidence, text = self.run_tool(stub.base)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(evidence['result'], 'pass')
        self.assertEqual(self.failed(evidence), [])
        self.assertEqual([item['id'] for item in evidence['checks'] if item['severity'] == 'hard'], list(vl.REQUIRED_CHECKS))
        # what the server received is exactly the five requests, no redirect followed, and what the evidence lists
        self.assertEqual(self.requests(stub), EXPECTED)
        self.assertEqual([f'{r["method"]} {r["path"]}' for r in evidence['requests']], EXPECTED)
        self.assertEqual([r['status'] for r in evidence['requests']], [200, 302, 200, 302, 401])
        # the password went once, in the sign-in form, and nowhere else
        login = stub.log[1]
        self.assertEqual(parse_qs(login['body'].decode())['password'], [PASSWORD])
        self.assertEqual(parse_qs(login['body'].decode())['username'], [USERNAME])
        self.assertEqual(sorted(parse_qs(login['body'].decode())), ['csrfmiddlewaretoken', 'next', 'password', 'username'])
        for entry in stub.log[:1] + stub.log[2:]:
            self.assert_no_password(entry['body'].decode(), json.dumps(entry['headers']), entry['path'])
        # the session read and the sign-out used the session the sign-in set; the proof replays that same cookie only
        sid = stub.log[2]['cookies']['cptstudio_session']
        self.assertEqual(stub.log[3]['cookies']['cptstudio_session'], sid)
        self.assertEqual(stub.log[4]['cookies'], {'cptstudio_session': sid})
        self.assertNotIn(sid, stub.sessions)
        # the sign-out posted the CSRF token the sign-in rotated, from the same origin
        self.assertNotEqual(stub.log[3]['cookies']['cptstudio_csrf'], stub.log[1]['cookies']['cptstudio_csrf'])
        self.assertEqual(parse_qs(stub.log[3]['body'].decode())['csrfmiddlewaretoken'], [stub.log[3]['cookies']['cptstudio_csrf']])
        self.assertEqual({entry['headers'].get('Origin') for entry in stub.log if entry['method'] == 'POST'}, {stub.base})
        # the evidence names the account as served and holds no password, cookie or token
        self.assertEqual(evidence['session']['user'], {'username': USERNAME, 'label': 'Demo reviewer (synthetic demonstration)',
                                                       'actor_kind': 'human'})
        self.assertEqual((evidence['session']['role'], evidence['session']['workspace']['name']), ('reviewer', WORKSPACE))
        self.assertEqual(evidence['credentials'], {'username': USERNAME, 'file_mode': '0600'})
        self.assert_no_password(out, err, text)
        for entry in stub.log:
            for value in entry['cookies'].values():
                self.assertNotIn(value, text + out + err)
        self.assertEqual(oct((self.dir / 'evidence' / vl.EVIDENCE_NAME).stat().st_mode & 0o777), '0o600')
        self.assertIn('login demo-reviewer at http://127.0.0.1', out)

    def test_each_hard_check_fails_on_the_broken_server_shape_it_exists_for(self):
        cases = [
            ('the sign-in page fails', {'page': 'error'}, ['login.form'], EXPECTED[:1]),
            ('no sign-in form', {'page': 'no-form'}, ['login.form'], EXPECTED[:1]),
            ('no CSRF token in the form', {'page': 'no-token'}, ['login.form'], EXPECTED[:1]),
            ('no CSRF cookie', {'csrf_cookie': False}, ['login.form'], EXPECTED[:1]),
            ('the sign-in redirects elsewhere', {'login_redirect': '/login/?next=/'}, ['login.redirect'], EXPECTED),
            ('the sign-in redirects off the site', {'login_redirect': 'https://elsewhere.invalid/'}, ['login.redirect'], EXPECTED),
            ('the sign-in sets no session', {'login_sets_session': False}, ['login.redirect'], EXPECTED[:2]),
            ('an agent account', {'accounts': {USERNAME: account(actor_kind='agent')}}, ['session.actor_kind'], EXPECTED),
            ('an owner', {'accounts': {USERNAME: account(role='owner')}}, ['session.role'], EXPECTED),
            ('a viewer', {'accounts': {USERNAME: account(role='viewer', can_review=False)}},
             ['session.role', 'session.membership_active'], EXPECTED),
            ('another workspace', {'accounts': {USERNAME: account(workspace='Cardiology')}}, ['session.workspace'], EXPECTED),
            ('another account in the session', {'session_username': 'someone-else'}, ['session.username'], EXPECTED),
            ('no active membership (404)', {'session_status': 404},
             ['session.read', 'session.username', 'session.actor_kind', 'session.role', 'session.membership_active',
              'session.workspace'], EXPECTED),
            ('the sign-out does not redirect', {'logout_status': 200}, ['logout.redirect'], EXPECTED),
            ('the sign-out redirects elsewhere', {'logout_redirect': '/'}, ['logout.redirect'], EXPECTED),
            ('the session outlives the sign-out', {'logout_ends_session': False}, ['logout.session_refused'], EXPECTED),
        ]
        for label, behaviour, failing, requests in cases:
            with self.subTest(label):
                stub = self.stub(**behaviour)
                code, out, err, evidence, text = self.run_tool(stub.base, out=self.dir / label.replace(' ', '-'))
                self.assertEqual(code, 1, out + err)
                self.assertEqual(evidence['result'], 'fail')
                self.assertEqual(self.failed(evidence), failing)
                self.assertEqual(self.requests(stub), requests)
                self.assert_no_password(out, err, text)

    def test_a_refused_sign_in_makes_no_further_request_and_never_echoes_the_password(self):
        stub = self.stub(echo_password=True)
        wrong = PASSWORD + '-wrong'
        credentials = private_file(self.dir, {'username': USERNAME, 'password': wrong}, name='wrong.json')
        code, out, err, evidence, text = self.run_tool(stub.base, credentials=credentials)
        self.assertEqual(code, 1)
        self.assertEqual(self.failed(evidence), ['login.redirect'])
        self.assertEqual(self.requests(stub), EXPECTED[:2])
        reason = next(item['reason'] for item in evidence['checks'] if item['id'] == 'login.redirect')
        # the server put the password in its page; the evidence quotes the page with the password withheld
        self.assertIn(f'You typed {vl.WITHHELD}', reason)
        self.assert_no_password(out, err, text, password=wrong)

    def test_a_session_left_by_a_failed_read_is_still_signed_out(self):
        stub = self.stub(session_json={'user': 'not an object'})
        code, out, err, evidence, text = self.run_tool(stub.base)
        self.assertEqual(code, 1)
        self.assertEqual(self.requests(stub), EXPECTED)
        self.assertEqual(stub.sessions, {})
        self.assertIn('session.username', self.failed(evidence))

    def test_the_cli_runs_as_a_script(self):
        stub = self.stub()
        guard = ('import socket,sys,runpy;c=socket.socket.connect\n'
                 'def g(s,a,*r,**k):\n'
                 '    assert s.family==socket.AF_UNIX or a[0] in ("127.0.0.1","::1"), a\n'
                 '    return c(s,a,*r,**k)\n'
                 'socket.socket.connect=g;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")')
        proc = subprocess.run([sys.executable, '-I', '-c', guard, str(HERE / 'verify_login.py'), '--base-url', stub.base,
                               '--credentials', str(self.credentials), '--workspace', WORKSPACE, '--out', str(self.dir / 'cli')],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.requests(stub), EXPECTED)
        self.assert_no_password(proc.stdout, proc.stderr, (self.dir / 'cli' / vl.EVIDENCE_NAME).read_text())


class RefusedBeforeAnyRequestTests(Base):
    def assert_refused(self, code, err, stub, evidence, pattern):
        self.assertEqual(code, 2)
        self.assertRegex(err, pattern)
        self.assertEqual(stub.log, [])
        self.assertIsNone(evidence)

    def test_a_credentials_file_a_group_or_other_user_may_read_or_write_is_refused(self):
        stub = self.stub()
        for mode in (0o640, 0o604, 0o644, 0o660, 0o606, 0o620, 0o602, 0o610, 0o601, 0o666):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.credentials, mode)
                code, out, err, evidence, _ = self.run_tool(stub.base)
                self.assert_refused(code, err, stub, evidence, r'has mode 0\d{3}: a group or other user may read or write it')
                self.assert_no_password(out, err)
        for mode in (0o600, 0o400):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.credentials, mode)
                out = self.dir / f'ok-{mode:o}'
                self.assertEqual(self.run_tool(stub.base, out=out)[0], 0)

    def test_a_credentials_file_that_is_not_the_expected_json_is_refused_without_quoting_it(self):
        stub = self.stub()
        secret = 'not-json ' + PASSWORD
        for label, data in (('not JSON', secret), ('a list', [USERNAME, PASSWORD]), ('no password', {'username': USERNAME}),
                            ('an empty username', {'username': '', 'password': PASSWORD}),
                            ('a numeric password', {'username': USERNAME, 'password': 12345678})):
            with self.subTest(label):
                path = private_file(self.dir, data, name=f'{label.replace(" ", "-")}.json')
                code, out, err, evidence, _ = self.run_tool(stub.base, credentials=path)
                self.assert_refused(code, err, stub, evidence, r'credentials file')
                self.assert_no_password(out, err)
        directory = self.dir / 'a-directory'
        directory.mkdir(mode=0o700)
        code, out, err, evidence, _ = self.run_tool(stub.base, credentials=directory)
        self.assert_refused(code, err, stub, evidence, r'not a regular file')
        code, out, err, evidence, _ = self.run_tool(stub.base, credentials=self.dir / 'missing.json')
        self.assert_refused(code, err, stub, evidence, r'cannot open the credentials file')

    def test_plain_http_off_the_loopback_and_odd_base_urls_are_refused(self):
        stub = self.stub()
        for index, base in enumerate(('http://cpt.quillmd.com', 'http://203.0.113.7:8000', 'ftp://127.0.0.1/', 'https://',
                                      'not a url', 'https://user:pw@cpt.quillmd.com', 'https://cpt.quillmd.com:99999')):
            with self.subTest(base):
                code, out, err, evidence, _ = self.run_tool(base, out=self.dir / f'refused-{index}')
                self.assert_refused(code, err, stub, evidence, r'--base-url|plain http')

    def test_an_existing_evidence_file_or_an_empty_workspace_is_refused(self):
        stub = self.stub()
        out = self.dir / 'used'
        out.mkdir()
        (out / vl.EVIDENCE_NAME).write_text('{}')
        code, _, err, _, _ = self.run_tool(stub.base, out=out)
        self.assertEqual(code, 2)
        self.assertIn('already holds', err)
        code, _, err, _, _ = self.run_tool(stub.base, workspace='  ')
        self.assertEqual((code, stub.log), (2, []))


class TlsTests(Base):
    """TLS is verified normally: an untrusted certificate or another host's ends the run before any HTTP request (so
    before the password is sent); the same server, its certificate trusted, passes."""

    @classmethod
    def setUpClass(cls):
        if shutil.which('openssl') is None:
            raise unittest.SkipTest('openssl is needed to make a test certificate')
        cls.certs = Path(tempfile.mkdtemp(prefix='cpt-verify-login-tls-'))
        for name, san in (('loopback', 'IP:127.0.0.1'), ('elsewhere', 'DNS:elsewhere.invalid')):
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-subj', '/CN=cpt-test',
                            '-addext', f'subjectAltName={san}', '-keyout', str(cls.certs / f'{name}.key'),
                            '-out', str(cls.certs / f'{name}.pem')], check=True, capture_output=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.certs, True)

    def tls_stub(self, name):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.certs / f'{name}.pem', self.certs / f'{name}.key')
        return self.stub(tls=context)

    def test_an_untrusted_certificate_ends_the_run_before_any_request(self):
        stub = self.tls_stub('loopback')
        with mock.patch.dict(os.environ, {'SSL_CERT_FILE': str(self.certs / 'elsewhere.pem')}):
            code, out, err, evidence, text = self.run_tool(stub.base)
        self.assertEqual(code, 1)
        self.assertEqual(stub.log, [])
        self.assertIn('CERTIFICATE_VERIFY_FAILED', evidence['run_error'])
        self.assertEqual([(r['method'], r['path'], r['status']) for r in evidence['requests']], [('GET', '/login/', None)])
        self.assertEqual(evidence['checks'][-1]['id'], 'requests.only_expected')
        self.assert_no_password(out, err, text)

    def test_a_certificate_for_another_host_ends_the_run(self):
        stub = self.tls_stub('elsewhere')
        with mock.patch.dict(os.environ, {'SSL_CERT_FILE': str(self.certs / 'elsewhere.pem')}):
            code, out, err, evidence, text = self.run_tool(stub.base)
        self.assertEqual((code, stub.log), (1, []))
        self.assertIn('CERTIFICATE_VERIFY_FAILED', evidence['run_error'])

    def test_the_same_server_with_its_certificate_trusted_passes(self):
        stub = self.tls_stub('loopback')
        with mock.patch.dict(os.environ, {'SSL_CERT_FILE': str(self.certs / 'loopback.pem')}):
            code, out, err, evidence, text = self.run_tool(stub.base)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.requests(stub), EXPECTED)
        self.assertTrue(evidence['tool']['transport'].startswith('https: certificate and host name verified'))


class PureCheckTests(unittest.TestCase):
    def test_the_request_list_is_a_prefix_of_the_five_and_all_five_once_a_session_was_set(self):
        made = lambda *pairs: [{'method': m, 'path': p} for m, p in pairs]  # noqa: E731
        five = list(vl.EXPECTED_REQUESTS)
        self.assertEqual(vl.request_list_check(made(*five), True)['status'], 'pass')
        self.assertEqual(vl.request_list_check(made(*five[:2]), False)['status'], 'pass')
        self.assertEqual(vl.request_list_check(made(), False)['status'], 'pass')
        for label, pairs, signed_in in (('a session never signed out', five[:3], True),
                                        ('a redirect followed', five[:2] + [('GET', '/')] + five[2:], True),
                                        ('a sixth request', five + [('GET', '/api/encounters')], True),
                                        ('out of order', [five[0], five[2]], False),
                                        ('a decision posted', five[:3] + [('POST', '/api/encounters/x/decisions')], True)):
            with self.subTest(label):
                self.assertEqual(vl.request_list_check(made(*pairs), signed_in)['status'], 'fail')

    def test_a_pass_needs_every_required_check_present_and_passing(self):
        full = [vl.check(name, 'hard', True, '') for name in vl.REQUIRED_CHECKS]
        self.assertEqual(vl.result_of(full, None), 'pass')
        self.assertEqual(vl.result_of(full, 'GET /login/: timed out'), 'fail')
        self.assertEqual(vl.result_of(full + [vl.check('logout.cookie_cleared', 'soft', False, '')], None), 'pass')
        for name in vl.REQUIRED_CHECKS:
            with self.subTest(missing=name):
                self.assertEqual(vl.result_of([item for item in full if item['id'] != name], None), 'fail')

    def test_the_session_checks_read_the_account_as_served(self):
        data = {'user': {'username': USERNAME, 'actor_kind': 'human'}, 'workspace': {'name': WORKSPACE}, 'role': 'reviewer',
                'can_review': True, 'synthetic_only': True}
        statuses = lambda status, body: {c['id']: c['status'] for c in vl.session_checks(status, body, USERNAME, WORKSPACE)}  # noqa: E731
        self.assertEqual(set(statuses(200, data).values()), {'pass'})
        self.assertEqual(statuses(200, {**data, 'can_review': 'true'})['session.membership_active'], 'fail')
        self.assertEqual(statuses(200, {**data, 'workspace': {'name': WORKSPACE.lower()}})['session.workspace'], 'fail')
        self.assertEqual(statuses(401, data)['session.read'], 'fail')
        self.assertEqual(statuses(200, [data])['session.actor_kind'], 'fail')

    def test_cookies_are_set_replaced_and_deleted_as_django_writes_them(self):
        jar = {}
        vl.apply_cookies(jar, ['cptstudio_csrf=abc; expires=Thu, 28 Oct 2027 10:00:00 GMT; Max-Age=31449600; Path=/; SameSite=Strict',
                               'cptstudio_session=s1; HttpOnly; Path=/; SameSite=Strict'])
        self.assertEqual(jar, {'cptstudio_csrf': 'abc', 'cptstudio_session': 's1'})
        deleted = vl.apply_cookies(jar, ['cptstudio_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Strict'])
        self.assertEqual((jar, deleted), ({'cptstudio_csrf': 'abc'}, {'cptstudio_session'}))

    def test_the_origin_is_what_a_browser_sends(self):
        self.assertEqual(vl.origin_of('https://cpt.quillmd.com/x/y?z'), 'https://cpt.quillmd.com')
        self.assertEqual(vl.origin_of('https://CPT.quillmd.com:443/'), 'https://cpt.quillmd.com')
        self.assertEqual(vl.origin_of('http://127.0.0.1:8123'), 'http://127.0.0.1:8123')
        self.assertEqual(vl.origin_of('http://[::1]:8123'), 'http://[::1]:8123')
        self.assertEqual(vl.origin_of('http://localhost:80'), 'http://localhost')

    def test_the_scrub_withholds_every_form_of_the_password(self):
        secret = vl.Secret(PASSWORD)
        for form in forms_of(PASSWORD):
            self.assertEqual(secret.scrub(f'[{form}]'), f'[{vl.WITHHELD}]')
        nested = secret.scrub({'a': [f'x{PASSWORD}y', {'b': quote_plus(PASSWORD)}], PASSWORD: 1})
        self.assertNotIn(PASSWORD, json.dumps(nested, ensure_ascii=False))


class ContractTests(unittest.TestCase):
    """The tool's constants and the views' behaviour it relies on are the server's own."""

    def read(self, *parts):
        return (ROOT.joinpath(*parts)).read_text(encoding='utf-8')

    def test_cookie_names_and_the_csrf_field(self):
        settings = self.read('cptstudio', 'settings.py')
        self.assertIn(f"SESSION_COOKIE_NAME = '{vl.SESSION_COOKIE}'", settings)
        self.assertIn(f"CSRF_COOKIE_NAME = '{vl.CSRF_COOKIE}'", settings)
        self.assertIn("CSRF_TRUSTED_ORIGINS = ['https://cpt.quillmd.com']", settings)
        self.assertNotIn('CSRF_USE_SESSIONS', settings)  # the token is the cookie's, so GET /login/ writes no row
        self.assertNotIn('SESSION_SAVE_EVERY_REQUEST', settings)
        login = self.read('studio', 'templates', 'studio', 'login.html')
        for fragment in ('<form class="login-form" method="post" action="">{% csrf_token %}',
                         '<input type="hidden" name="next" value="{{ next }}">', '<input name="username" ',
                         '<input name="password" type="password" ', '<p class="form-error" role="alert">{{ error }}</p>'):
            self.assertIn(fragment, login)

    def test_the_sign_in_sign_out_and_session_views(self):
        views = self.read('studio', 'views.py')
        for fragment in ("    next_url = request.POST.get('next') or request.GET.get('next') or '/'",
                         '            if user is not None and user.memberships.filter(active=True).exists():\n'
                         '                login(request, user)\n                return redirect(next_url)',
                         "    if request.method != 'POST':\n        return HttpResponseNotAllowed(['POST'])\n"
                         "    logout(request)\n    return redirect('/login/')"):
            self.assertIn(fragment, views)
        api = self.read('studio', 'api.py')
        self.assertIn("            return JsonResponse({'error': 'Sign in to continue.'}, status=401)", api)
        self.assertIn('@require_GET\n@api_view\ndef session(request):\n    membership = active_membership(request.user)', api)
        serializers = self.read('studio', 'serializers.py')
        self.assertIn("            'actor_kind': user.actor_kind, 'initials': _initials(user)}", serializers)
        self.assertIn("        'role': membership.role, 'can_review': membership.can_review,", serializers)
        self.assertIn("        'workspace': {'id': str(workspace.pk), 'name': workspace.name,", serializers)
        models = self.read('studio', 'models.py')
        self.assertIn("    HUMAN, AGENT = 'human', 'agent'", models)
        self.assertIn("    OWNER, REVIEWER, VIEWER = 'owner', 'reviewer', 'viewer'", models)
        self.assertIn('        return self.active and self.role in {self.OWNER, self.REVIEWER}', models)
        self.assertIn("        memberships = memberships.filter(workspace_id=workspace_id)", self.read('studio', 'access.py'))
        self.assertIn("    memberships = Membership.objects.select_related('workspace', 'workspace__category').filter(user=user, active=True)",
                      self.read('studio', 'access.py'))

    def test_the_tool_never_turns_tls_verification_off(self):
        source = (HERE / 'verify_login.py').read_text(encoding='utf-8')
        for weakening in ('CERT_NONE', 'check_hostname', '_create_unverified_context', 'verify_mode'):
            self.assertNotIn(weakening, source)
        self.assertIn('ssl.create_default_context()', source)


if __name__ == '__main__':
    unittest.main()
