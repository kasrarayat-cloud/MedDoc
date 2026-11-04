"""Unit tests for ops/scan_customer.py: the shared denylist and contract readers, and a loopback stand-in for the customer
surface the scanner signs in to and reads.

The stand-in serves the synthetic samples ops/verification/samples/make_samples.py writes to the contract (the session,
the list, the encounter, its reports, the page and its one script), answers 404 on every /ops/ URL and on the removed
trace, and signs the session in and out as studio/views.py does (verify_login.py's tests hold that contract). Each leak
the scanner must catch is a switch on it. Nothing leaves the loopback.

    cd cpt-studio && python3 -B -m unittest discover -s ops -p 'test_verify_scan_customer.py' -v
"""
import importlib.util
import io
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_scan_customer', HERE / 'scan_customer.py')
sc = importlib.util.module_from_spec(_spec)
sys.modules['cpt_scan_customer'] = sc
_spec.loader.exec_module(sc)

SAMPLES = HERE / 'verification' / 'samples'
USERNAME, PASSWORD = 'review-agent', 'Synthetic-scan pass&+%<>"é-2026'


def sample(name: str) -> str:
    return (SAMPLES / name).read_bytes().decode('utf-8')


def sample_json(name: str):
    return json.loads(sample(name))


class SharedReaderTests(unittest.TestCase):
    def test_the_denylist_vectors_hold_in_this_reader_as_in_the_walk_s(self):
        ctx = sc.scan_context()
        self.assertGreaterEqual(len(sc.DENYLIST['vectors']), 30)
        for vector in sc.DENYLIST['vectors']:
            with self.subTest(text=vector['text']):
                self.assertEqual(sorted({hit['id'] for hit in sc.scan_text(vector['text'], ctx, vector['surface'])}), vector['hits'])

    def test_the_readers_are_ascii_only_as_javascript_reads_them(self):
        # Python's re.I alone folds the long s and the Kelvin sign onto s and k; JavaScript 'gi' does not
        ctx = sc.scan_context()
        self.assertEqual(sc.scan_text('\u017fha256', ctx, 'dom'), [])  # 'ſ' is no 's'
        self.assertEqual([h['id'] for h in sc.scan_text('Participants', ctx, 'dom')], ['participant'])
        self.assertEqual(sc.scan_text('toKens', ctx, 'dom'), [])  # 'K' (Kelvin) is no 'k'

    def test_the_customer_samples_hold_to_the_contract_and_each_difference_is_named(self):
        self.assertEqual(sc.shape_problems(sample_json('customer-encounter.json'), sc.CONTRACT['encounter']), [])
        self.assertEqual(sc.shape_problems(sample_json('customer-encounter-details.json'), sc.CONTRACT['encounter']), [])
        self.assertEqual(sc.shape_problems(sample_json('customer-session.json'), sc.CONTRACT['session']), [])
        enc = sample_json('customer-encounter.json')
        enc['codes'][0]['vendor'] = 'OpenAI'
        enc['codes'][0]['units'] = True
        del enc['readiness']['blockers']
        enc['state'] = 'needs_clarification'
        problems = sc.shape_problems(enc, sc.CONTRACT['encounter'])
        for want in ('$.codes[0].vendor: not in the customer contract', '$.codes[0].units: boolean where the contract has integer',
                     '$.readiness.blockers: missing (the contract lists it)', '$.state: "needs_clarification" is not one of'):
            self.assertTrue(any(problem.startswith(want) for problem in problems), (want, problems))
        session = sample_json('customer-session.json')
        session['provider_mode'] = 'live'
        session['user']['username'] = 'review-agent'
        self.assertEqual(sorted(sc.shape_problems(session, sc.CONTRACT['session'])),
                         ['$.provider_mode: not in the customer contract', '$.user.username: not in the customer contract'])

    def test_deny_values_are_the_operator_view_s_identifiers_never_a_plain_word(self):
        values = sc.deny_values_from(sample_json('operator-encounter.json'), sample_json('operator-trace.json'))
        for want in ('gpt-6-astra', 'claude-fable-5-1', 'evidence.exact', 'cpt-studio:provider@1', 'c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d',
                     'req_astra0123456789', 'chatcmpl-fable9876543210'):
            self.assertIn(want, values)
        for word in ('OpenAI', 'Corti', 'reviewed', 'units'):
            self.assertNotIn(word, values)
        self.assertEqual(sc.harvest({'a': [{'b': ['x1']}, {'b': ['y2']}]}, 'a[].b[]'), ['x1', 'y2'])
        self.assertEqual(sc.harvest({'f': [['n', 'h1'], ['m', 'h2']]}, 'f[].1'), ['h1', 'h2'])

    def test_files_are_scanned_cell_by_cell_and_line_by_line_with_the_document_s_own_quotations_set_aside(self):
        op = sample_json('operator-encounter.json')
        ctx = sc.scan_context(op['revision']['text'], sc.deny_values_from(op, sample_json('operator-trace.json')))
        for name in ('customer-report-approved.txt', 'customer-report-draft.txt', 'customer-report-approved.csv', 'customer-report-draft.csv'):
            self.assertEqual(sc.scan_file(sample(name), ctx, name, name.rsplit('.', 1)[1]), [], name)
        leaked = sample('customer-report-approved.csv').replace(',approved,', ',approved (gpt-6-astra),', 1)
        self.assertEqual(sorted({h['id'] for h in sc.scan_file(leaked, ctx, 'x.csv', 'csv')}), ['deny_value', 'model_id', 'provider_name'])
        self.assertEqual(sc.csv_rows('a,"b ""c"", d"\r\n1,2\n'), [['a', 'b "c", d'], ['1', '2']])
        self.assertEqual(sc.scan_headers([('Content-Security-Policy', "script-src 'sha256-x'")], ctx, 'GET /'), [])
        self.assertEqual(sorted({h['id'] for h in sc.scan_headers([('X-Content-SHA256', 'ab' * 32)], ctx, 'GET /x')}), ['long_hex', 'sha256'])


# --- a loopback stand-in for the customer surface ------------------------------------------------------------------

class StubSite:
    """The customer surface on 127.0.0.1, from the samples; ``leak`` switches on each broken shape."""

    def __init__(self, **leak):
        self.leak = leak
        self.sessions, self.log = set(), []
        self.encounter = sample_json('customer-encounter.json')
        self.id = self.encounter['id']
        self.reports = {r['id']: sample(f'customer-report-{r["kind"]}.{r["fmt"]}') for r in self.encounter['reports']}
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                stub.handle(self, b'')

            def do_POST(self):
                stub.handle(self, self.rfile.read(int(self.headers.get('Content-Length') or 0)))

        class Server(ThreadingHTTPServer):
            daemon_threads = True

        self.server = Server(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def send(self, request, status, body, content_type='application/json', headers=()):
        data = body if isinstance(body, bytes) else (json.dumps(body) if not isinstance(body, str) else body).encode('utf-8')
        request.send_response(status)
        request.send_header('Content-Type', content_type)
        request.send_header('Content-Length', str(len(data)))
        for name, value in headers:
            request.send_header(name, value)
        request.end_headers()
        request.wfile.write(data)

    def handle(self, request, body):
        cookies = {name: morsel.value for name, morsel in SimpleCookie(request.headers.get('Cookie', '')).items()}
        self.log.append((request.command, request.path))
        signed = cookies.get('cptstudio_session') in self.sessions
        route = (request.command, request.path)
        if route == ('GET', '/login/'):
            token = secrets.token_hex(16)
            page = ('<html><body><form class="login-form" method="post" action="">'
                    f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}"><input name="username">'
                    '<input name="password" type="password"><button type="submit">Sign in</button></form></body></html>')
            return self.send(request, 200, page, 'text/html', [('Set-Cookie', f'cptstudio_csrf={token}; Path=/')])
        if route == ('POST', '/login/'):
            form = {key: values[0] for key, values in parse_qs(body.decode()).items()}
            if form.get('username') != USERNAME or form.get('password') != PASSWORD:
                return self.send(request, 200, '<p class="form-error">Wrong.</p>', 'text/html')
            session = secrets.token_hex(16)
            self.sessions.add(session)
            return self.send(request, 302, b'', 'text/html', [('Location', '/'), ('Set-Cookie', f'cptstudio_session={session}; Path=/')])
        if route == ('POST', '/logout/'):
            self.sessions.discard(cookies.get('cptstudio_session'))
            return self.send(request, 302, b'', 'text/html', [('Location', '/login/'),
                                                              ('Set-Cookie', 'cptstudio_session=""; Max-Age=0; Path=/')])
        if not signed:
            return self.send(request, 401, {'error': 'Sign in to continue.'})
        if route == ('GET', '/'):
            scripts = '<script defer src="/static/studio/app.js"></script>' + ('<script src="/static/studio/ops.js"></script>' if self.leak.get('two_scripts') else '')
            return self.send(request, 200, f'<!doctype html><html><head><link rel="stylesheet" href="/static/studio/styles.css">{scripts}</head>'
                                           '<body><main id="main"></main></body></html>', 'text/html')
        if route == ('GET', '/static/studio/app.js'):
            code = "const api = path => fetch(path); const token = readCookie('cptstudio_csrf');"
            return self.send(request, 200, code + (" const LABEL = 'Corti';" if self.leak.get('bundle_name') else ''), 'text/javascript')
        if route in (('GET', '/static/studio/styles.css'), ('GET', '/static/studio/ops.js')):
            return self.send(request, 200, 'main { margin: 0; }', 'text/css')
        if route == ('GET', '/api/session'):
            session = sample_json('customer-session.json')
            if self.leak.get('session_mode'):
                session['provider_mode'] = 'live'
            return self.send(request, 200, session)
        if route == ('GET', '/api/encounters'):
            row = {'id': self.id, 'title': self.encounter['title'], 'state': 'reviewed', 'state_label': 'Reviewed', 'service_date': '2026-11-03',
                   'date_conflict': False, 'open_details': 0, 'created_at': self.encounter['created_at'], 'kind': 'paste'}
            return self.send(request, 200, {'encounters': [row]})
        if route == ('GET', f'/api/encounters/{self.id}/original') and self.leak.get('original'):
            headers = [('X-Content-SHA256', 'cd' * 32)] if self.leak.get('original_hash') else []
            return self.send(request, 200, b'%PDF-1.4 synthetic ' + b'0' * (3 * 1024 * 1024), 'application/pdf', headers)
        if route == ('GET', f'/api/encounters/{self.id}'):
            enc = json.loads(json.dumps(self.encounter))
            if self.leak.get('original'):
                enc['document'].update(kind='upload', name='note.pdf', media_type='application/pdf', size=3 * 1024 * 1024 + 19,
                                       original_url=f'/api/encounters/{self.id}/original')
            if self.leak.get('vendor_key'):
                enc['codes'][0]['vendor'] = 'OpenAI'
            if self.leak.get('run_id'):
                enc['codes'][0]['summary'] = 'Read in run c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d.'
            return self.send(request, 200, enc)
        if request.command == 'GET' and request.path.startswith('/api/reports/') and request.path.endswith('/download'):
            report = request.path.split('/')[3]
            text = self.reports.get(report)
            if text is None:
                return self.send(request, 404, {'error': 'Not found.'})
            headers = [('X-Content-SHA256', 'ab' * 32)] if self.leak.get('hash_header') else []
            return self.send(request, 200, text.replace('LIMITATIONS', 'PROVIDER USAGE\n  corti\n\nLIMITATIONS') if self.leak.get('report_leak') else text,
                             'text/plain', headers)
        if request.command == 'GET' and request.path.startswith('/ops/'):
            if self.leak.get('ops_open'):
                return self.send(request, 200, {'harness': {'participants': [{'name': 'astra', 'model': 'gpt-6-astra'}]}})
            return self.send(request, 404, {'error': 'Not found.'})
        if route == ('GET', f'/api/encounters/{self.id}/trace'):
            return self.send(request, 200 if self.leak.get('trace_open') else 404, {'error': 'Not found.'})
        return self.send(request, 404, {'error': 'Not found.'})


class ScanRunTests(unittest.TestCase):
    def run_scan(self, *extra, site=None, credentials=None):
        site = site or StubSite()
        self.addCleanup(site.close)
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        if credentials is None:
            credentials = Path(folder) / 'customer.json'
            credentials.write_text(json.dumps({'username': USERNAME, 'password': PASSWORD}))
            os.chmod(credentials, 0o600)
        out = Path(folder) / 'out'
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = sc.main(['--base-url', site.base, '--credentials', str(credentials), '--out', str(out), *extra])
        evidence = json.loads((out / sc.EVIDENCE_NAME).read_text()) if (out / sc.EVIDENCE_NAME).exists() else None
        return code, evidence, stdout.getvalue() + stderr.getvalue(), site

    def statuses(self, evidence):
        return {item['id']: item['status'] for item in evidence['checks']}

    def test_a_clean_customer_surface_passes_with_get_requests_only_and_the_session_is_signed_out(self):
        code, evidence, printed, site = self.run_scan('--all')
        self.assertEqual(code, 0, printed)
        self.assertEqual(evidence['result'], 'pass')
        self.assertTrue(evidence['only_get_beyond_sign_in_and_out'])
        self.assertEqual([m for m, _ in site.log if m == 'POST'], ['POST', 'POST'])  # sign-in, sign-out
        statuses = self.statuses(evidence)
        short = site.id[:8]
        for check in ('session.contract', 'customer.list_contract', f'customer.contract.{short}', f'authorization.{short}', 'bundle.one_script',
                      'scan.json', 'scan.header', 'scan.file', 'scan.bundle', 'logout.session_refused'):
            self.assertEqual(statuses.get(check), 'pass', check)
        self.assertEqual(evidence['encounters'], [{'id': site.id, 'status': 200, 'operator_view': False, 'reports': 4}])
        self.assertNotIn(PASSWORD, json.dumps(evidence))
        self.assertNotIn(PASSWORD, printed)

    def test_each_leak_fails_the_check_it_exists_for(self):
        cases = [
            ({'vendor_key': True}, ['scan.json', 'customer.contract.{short}']),
            ({'ops_open': True}, ['authorization.{short}', 'scan.json']),
            ({'trace_open': True}, ['authorization.{short}']),
            ({'hash_header': True}, ['report.{short}.draft.txt', 'scan.header']),
            ({'report_leak': True}, ['scan.file']),
            ({'bundle_name': True}, ['scan.bundle']),
            ({'two_scripts': True}, ['bundle.one_script']),
            ({'session_mode': True}, ['session.contract']),
        ]
        for leak, wanted in cases:
            with self.subTest(leak=leak):
                code, evidence, printed, site = self.run_scan('--encounter', sample_json('customer-encounter.json')['id'], site=StubSite(**leak))
                self.assertEqual(code, 1, printed)
                failed = {item['id'] for item in evidence['checks'] if item['status'] == 'fail'}
                for check in wanted:
                    self.assertIn(check.format(short=site.id[:8]), failed, (leak, sorted(failed)))

    def test_an_uploaded_original_is_read_for_its_headers_only_whatever_its_size(self):
        enc_id = sample_json('customer-encounter.json')['id']
        code, evidence, printed, site = self.run_scan('--encounter', enc_id, site=StubSite(original=True))
        self.assertEqual(code, 0, printed)
        self.assertEqual({c['id']: c['status'] for c in evidence['checks']}[f'original.{enc_id[:8]}'], 'pass')
        # a source hash on the original's download is a customer-facing hash
        code, evidence, printed, site = self.run_scan('--encounter', enc_id, site=StubSite(original=True, original_hash=True))
        self.assertEqual(code, 1)
        self.assertTrue(any(h['id'] == 'long_hex' and 'original' in h['where'] for h in evidence['hits']['header']), evidence['hits']['header'])

    def test_the_operator_view_s_identifiers_are_looked_for_when_given(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        enc_id = sample_json('customer-encounter.json')['id']
        (folder / f'{enc_id}.json').write_text(sample('operator-encounter.json'))
        (folder / f'{enc_id}.trace.json').write_text(sample('operator-trace.json'))
        code, evidence, printed, _ = self.run_scan('--encounter', enc_id, '--operator-json', str(folder), site=StubSite(run_id=True))
        self.assertEqual(code, 1)
        hits = evidence['hits']['json']
        self.assertTrue(any(hit['id'] == 'deny_value' for hit in hits), hits)
        self.assertEqual(evidence['encounters'][0]['operator_view'], True)
        clean, evidence, printed, _ = self.run_scan('--encounter', enc_id, '--operator-json', str(folder))
        self.assertEqual(clean, 0, printed)

    def test_usage_errors_are_refused_before_any_request(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        loose = folder / 'loose.json'
        loose.write_text(json.dumps({'username': USERNAME, 'password': PASSWORD}))
        os.chmod(loose, 0o644)
        site = StubSite()
        code, evidence, printed, _ = self.run_scan(site=site, credentials=loose)
        self.assertEqual((code, evidence), (2, None))
        self.assertIn('mode 0644', printed)
        self.assertEqual(site.log, [])
        code, evidence, printed, _ = self.run_scan('--encounter', 'not-an-id')
        self.assertEqual((code, evidence), (2, None))
        self.assertIn('not an encounter id', printed)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(sc.main(['--base-url', 'http://example.com', '--credentials', str(loose), '--out', str(folder / 'o')]), 2)
        self.assertIn('plain http', stderr.getvalue())

    def test_a_refused_sign_in_scans_nothing(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        wrong = folder / 'wrong.json'
        wrong.write_text(json.dumps({'username': USERNAME, 'password': 'not-the-password'}))
        os.chmod(wrong, 0o600)
        code, evidence, printed, site = self.run_scan(credentials=wrong)
        self.assertEqual(code, 1)
        self.assertEqual([path for _, path in site.log], ['/login/', '/login/'])
        self.assertEqual({item['id']: item['status'] for item in evidence['checks']}, {'login.signed_in': 'fail'})


if __name__ == '__main__':
    unittest.main()
