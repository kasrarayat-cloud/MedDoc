"""Unit tests for ops/scan_customer.py: the shared denylist and contract readers, and a loopback stand-in for the customer
surface the scanner signs in to and reads.

The stand-in serves synthetic payloads of the Fable coding build's customer contract (ops/verification/
customer-contract.json; built here - the session, the list, an encounter with its quotes, its original and view, its
exports, the page and its one script), answers 404 on every /ops/ URL and on every removed one, and signs the session in
and out as studio/views.py does (verify_login.py's tests hold that contract). Each leak the scanner must catch is a
switch on it. Nothing leaves the loopback.

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
import unittest.mock
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

USERNAME, PASSWORD = 'review-agent', 'Synthetic-scan pass&+%<>"é-2026'
ENCOUNTER_ID = 'f6000000-0000-4000-8000-0000000000a1'
DRAFT_ID, APPROVED_ID = 'f6000000-0000-4000-8000-0000000000d1', 'f6000000-0000-4000-8000-0000000000d2'
QUOTE = 'Cold forceps biopsies were taken from the gastric antrum.'


def session_json() -> dict:
    return {'user': {'id': 'fa000000-0000-4000-8000-000000000001', 'label': 'Review agent', 'initials': 'RA',
                     'actor_kind': 'agent'},
            'workspace': {'id': 'fa000000-0000-4000-8000-000000000002', 'name': 'Gastroenterology'},
            'role': 'reviewer', 'can_review': True,
            'acknowledgement': 'I read the whole source document. This synthetic review is not clinical approval.',
            'counts': {'documents': 1, 'queue': 0}}


def encounter_json() -> dict:
    """A synthetic encounter as the customer API serves it: one code approved, its quote cited from the document."""
    base = f'/api/encounters/{ENCOUNTER_ID}/original'
    return {
        'id': ENCOUNTER_ID, 'title': 'Synthetic EGD with biopsy', 'created_at': '2026-11-20T07:10:00Z',
        'updated_at': '2026-11-20T07:55:00Z', 'state': 'reviewed', 'state_label': 'Reviewed',
        'permissions': {'can_review': True},
        'document': {'name': 'synthetic-egd.pdf', 'media_type': 'application/pdf', 'size': 1673, 'kind': 'upload',
                     'original_url': base, 'view_url': f'{base}?view=1', 'view_media_type': 'application/pdf',
                     'converted': False},
        'context': {'service_date': '2026-11-02', 'insurance': 'medicare'},
        'progress': {'phase': 'done', 'busy': False, 'started_at': '2026-11-20T07:31:05Z',
                     'finished_at': '2026-11-20T07:38:40Z', 'server_time': '2026-11-20T08:10:00Z', 'message': '',
                     'can_stop': False, 'can_resume': False, 'can_retry': False, 'error': None},
        'round': {'number': 1, 'trigger': 'upload', 'finished_at': '2026-11-20T07:38:40Z'},
        'codes': [{'code': '43239', 'units': 1, 'modifiers': [], 'status': 'ready', 'status_label': 'Ready for approval',
                   'reason': 'Biopsies were taken during the upper endoscopy (page 1).',
                   'second_check': {'agrees': True, 'reason': 'The biopsy is documented on page 1.'},
                   'question': None, 'quotes': [{'text': QUOTE, 'page': 1}],
                   'decision': {'action': 'approve', 'by': 'Review agent', 'at': '2026-11-20T07:52:10Z', 'note': ''},
                   'allowed_actions': ['revoke']}],
        'questions': [], 'answers': [], 'notes': [],
        'readiness': {'draft': True, 'approved': True, 'blockers': []},
        'reports': [{'id': DRAFT_ID, 'kind': 'draft', 'fmt': 'txt', 'filename': 'synthetic-egd-draft.txt',
                     'generated_at': '2026-11-20T07:53:00Z', 'download_url': f'/api/reports/{DRAFT_ID}/download',
                     'current': True},
                    {'id': APPROVED_ID, 'kind': 'approved', 'fmt': 'csv', 'filename': 'synthetic-egd-approved.csv',
                     'generated_at': '2026-11-20T07:54:00Z', 'download_url': f'/api/reports/{APPROVED_ID}/download',
                     'current': True}],
        'activity': [{'at': '2026-11-20T07:52:10Z', 'text': 'Review agent approved 43239.'}]}


EXPORTS = {
    DRAFT_ID: ('SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\nCPT STUDIO — CODES — DRAFT, NOT APPROVED\n'
               'Encounter: Synthetic EGD with biopsy\n\n43239 x1 - Ready for approval\n'
               '  Biopsies were taken during the upper endoscopy (page 1).\n'
               f'  Quote (page 1): "{QUOTE}"\nLimitations\n  The coding review can be wrong.\n'
               'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\n'),
    APPROVED_ID: ('"kind","code","units","modifiers","status","reason","quotes","decision","decided_by","decided_at"\r\n'
                  '"banner","SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS","","","","","","","",""\r\n'
                  f'"code","43239","1","","ready","Biopsies were taken (page 1).","{QUOTE} (page 1)","approved",'
                  '"Review agent","2026-11-20T07:52:10Z"\r\n'),
}


class SharedReaderTests(unittest.TestCase):
    def test_the_denylist_vectors_hold_in_this_reader_as_in_the_walk_s(self):
        ctx = sc.scan_context()
        self.assertGreaterEqual(len(sc.DENYLIST['vectors']), 20)
        for vector in sc.DENYLIST['vectors']:
            with self.subTest(text=vector['text']):
                self.assertEqual(sorted({hit['id'] for hit in sc.scan_text(vector['text'], ctx, vector['surface'])}), vector['hits'])

    def test_the_readers_are_ascii_only_as_javascript_reads_them(self):
        # Python's re.I alone folds the long s and the Kelvin sign onto s and k; JavaScript 'gi' does not
        ctx = sc.scan_context()
        self.assertEqual(sc.scan_text('\u017fha256', ctx, 'dom'), [])  # 'ſ' is no 's'
        self.assertEqual(sorted({h['id'] for h in sc.scan_text('sha256', ctx, 'dom')}), ['sha256'])  # the control
        self.assertEqual(sc.scan_text('to\u212aens', ctx, 'dom'), [])  # the Kelvin sign is no 'k'
        self.assertTrue(sc.scan_text('tokens', ctx, 'dom'))  # the control

    def test_the_payloads_hold_to_the_contract_and_each_difference_is_named(self):
        self.assertEqual(sc.shape_problems(encounter_json(), sc.CONTRACT['encounter']), [])
        self.assertEqual(sc.shape_problems(session_json(), sc.CONTRACT['session']), [])
        enc = encounter_json()
        enc['codes'][0]['vendor'] = 'Anthropic'
        enc['codes'][0]['units'] = True
        del enc['readiness']['blockers']
        enc['state'] = 'needs_clarification'
        problems = sc.shape_problems(enc, sc.CONTRACT['encounter'])
        for want in ('$.codes[0].vendor: not in the customer contract', '$.codes[0].units: boolean where the contract has integer',
                     '$.readiness.blockers: missing (the contract lists it)', '$.state: "needs_clarification" is not one of'):
            self.assertTrue(any(problem.startswith(want) for problem in problems), (want, problems))
        session = session_json()
        session['provider_mode'] = 'live'
        session['user']['username'] = 'review-agent'
        self.assertEqual(sorted(sc.shape_problems(session, sc.CONTRACT['session'])),
                         ['$.provider_mode: not in the customer contract', '$.user.username: not in the customer contract'])

    def test_deny_values_are_identifier_shaped_and_read_by_the_denylists_paths(self):
        self.assertEqual(sc.harvest({'a': [{'b': ['x1']}, {'b': ['y2']}]}, 'a[].b[]'), ['x1', 'y2'])
        self.assertEqual(sc.harvest({'f': [['n', 'h1'], ['m', 'h2']]}, 'f[].1'), ['h1', 'h2'])
        paths = {'encounter': ['runs[].id', 'runs[].model'], 'trace': ['calls[].request_id']}
        view = {'runs': [{'id': 'c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d', 'model': 'claude-fable-5-2'},
                         {'id': 'short', 'model': 'Corti'}]}
        with unittest.mock.patch.dict(sc.DENYLIST, {'deny_value_paths': paths}):
            values = sc.deny_values_from(view, {'calls': [{'request_id': 'req_fable0123456789'}]})
        self.assertEqual(values, ['c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d', 'claude-fable-5-2', 'req_fable0123456789'])
        self.assertEqual(sc.deny_values_from(view), [])  # the build's own denylist names no path: nothing is harvested

    def test_files_are_scanned_cell_by_cell_and_line_by_line_with_the_document_s_own_quotations_set_aside(self):
        ctx = sc.scan_context(sc.quotations(encounter_json()))
        self.assertEqual(ctx.document_text, QUOTE)
        for report in encounter_json()['reports']:
            self.assertEqual(sc.scan_file(EXPORTS[report['id']], ctx, report['filename'], report['fmt']), [], report['id'])
        csv_text = EXPORTS[APPROVED_ID]
        self.assertEqual(csv_text.count(',"approved",'), 1)
        leaked = csv_text.replace(',"approved",', ',"approved (claude-fable-5-2)",', 1)
        self.assertLessEqual({'model_id', 'provider_name'}, {h['id'] for h in sc.scan_file(leaked, ctx, 'x.csv', 'csv')})
        # a quotation of the document is set aside only while it is one: the same words outside quotes are scanned
        self.assertEqual(sc.scan_file(f'"{QUOTE}"', ctx, 'q.txt', 'txt'), [])
        self.assertEqual(sc.csv_rows('a,"b ""c"", d"\r\n1,2\n'), [['a', 'b "c", d'], ['1', '2']])
        self.assertEqual(sc.scan_headers([('Content-Security-Policy', "script-src 'sha256-x'")], ctx, 'GET /'), [])
        self.assertEqual(sorted({h['id'] for h in sc.scan_headers([('X-Content-SHA256', 'ab' * 32)], ctx, 'GET /x')}), ['long_hex', 'sha256'])


# --- a loopback stand-in for the customer surface ------------------------------------------------------------------

class StubSite:
    """The customer surface on 127.0.0.1, from the synthetic payloads; ``leak`` switches on each broken shape."""

    def __init__(self, **leak):
        self.leak = leak
        self.sessions, self.log = set(), []
        self.encounter = encounter_json()
        self.id = self.encounter['id']
        self.reports = dict(EXPORTS)
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
            scripts = '<script defer src="/static/studio/app.js"></script>' + ('<script src="/static/studio/extra.js"></script>' if self.leak.get('two_scripts') else '')
            return self.send(request, 200, f'<!doctype html><html><head><link rel="stylesheet" href="/static/studio/styles.css">{scripts}</head>'
                                           '<body><main id="main"></main></body></html>', 'text/html')
        if route == ('GET', '/static/studio/app.js'):
            code = "const api = path => fetch(path); const token = readCookie('cptstudio_csrf');"
            return self.send(request, 200, code + (" const LABEL = 'Claude';" if self.leak.get('bundle_name') else ''), 'text/javascript')
        if route in (('GET', '/static/studio/styles.css'), ('GET', '/static/studio/extra.js')):
            return self.send(request, 200, 'main { margin: 0; }', 'text/css')
        if route == ('GET', '/api/session'):
            session = session_json()
            if self.leak.get('session_mode'):
                session['provider_mode'] = 'live'
            return self.send(request, 200, session)
        if route == ('GET', '/api/encounters'):
            row = {'id': self.id, 'title': self.encounter['title'], 'state': 'reviewed', 'state_label': 'Reviewed',
                   'service_date': '2026-11-02', 'insurance': 'medicare', 'created_at': self.encounter['created_at'],
                   'kind': 'upload'}
            return self.send(request, 200, {'encounters': [row]})
        if route in (('GET', f'/api/encounters/{self.id}/original'), ('GET', f'/api/encounters/{self.id}/original?view=1')):
            headers = [('X-Content-SHA256', 'cd' * 32)] if self.leak.get('original_hash') else []
            return self.send(request, 200, b'%PDF-1.4 synthetic ' + b'0' * (3 * 1024 * 1024), 'application/pdf', headers)
        if route == ('GET', f'/api/encounters/{self.id}'):
            enc = json.loads(json.dumps(self.encounter))
            if self.leak.get('vendor_key'):
                enc['codes'][0]['vendor'] = 'Anthropic'
            if self.leak.get('run_id'):
                enc['codes'][0]['reason'] = 'Read in run c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d.'
            return self.send(request, 200, enc)
        if request.command == 'GET' and request.path.startswith('/api/reports/') and request.path.endswith('/download'):
            report = request.path.split('/')[3]
            text = self.reports.get(report)
            if text is None:
                return self.send(request, 404, {'error': 'Not found.'})
            headers = [('X-Content-SHA256', 'ab' * 32)] if self.leak.get('hash_header') else []
            # the TXT export leaks (the CSV has no Limitations line); the leak case expects scan.file to fail on it
            leaked = text.replace('\nLimitations', '\nUSAGE\n  claude-fable-5-2: 12,000 tokens\n\nLimitations', 1) if self.leak.get('report_leak') else text
            return self.send(request, 200, leaked, 'text/plain', headers)
        if request.command == 'GET' and request.path.startswith('/ops/'):
            if self.leak.get('ops_open') and request.path == f'/ops/encounters/{self.id}':
                return self.send(request, 200, '<h1>Runs</h1><p>reader claude-fable-5-2</p>', 'text/html')
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
        for check in (f'original.{short}', f'view.{short}', f'report.{short}.draft.txt', f'report.{short}.approved.csv'):
            self.assertEqual(statuses.get(check), 'pass', check)
        self.assertEqual(evidence['encounters'], [{'id': site.id, 'status': 200, 'operator_view': False, 'reports': 2}])
        # every operator page and every removed URL was asked for, and answered 404
        asked = {path for method, path in site.log if method == 'GET'}
        for template in sc.OPS_GET_PATHS + sc.REMOVED_PATHS:
            self.assertIn(template.format(id=site.id), asked)
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
                code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(**leak))
                self.assertEqual(code, 1, printed)
                failed = {item['id'] for item in evidence['checks'] if item['status'] == 'fail'}
                for check in wanted:
                    self.assertIn(check.format(short=site.id[:8]), failed, (leak, sorted(failed)))

    def test_an_uploaded_original_and_its_view_are_read_for_their_headers_only_whatever_their_size(self):
        code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID)
        self.assertEqual(code, 0, printed)
        statuses = {c['id']: c['status'] for c in evidence['checks']}
        self.assertEqual((statuses[f'original.{ENCOUNTER_ID[:8]}'], statuses[f'view.{ENCOUNTER_ID[:8]}']), ('pass', 'pass'))
        # a source hash on the original's download (and so on its view) is a customer-facing hash
        code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(original_hash=True))
        self.assertEqual(code, 1)
        wheres = [h['where'] for h in evidence['hits']['header'] if h['id'] == 'long_hex']
        self.assertTrue(any(where.endswith('/original header X-Content-SHA256') for where in wheres), wheres)
        self.assertTrue(any('?view=1' in where for where in wheres), wheres)

    def test_the_operator_view_s_identifiers_are_looked_for_when_the_denylist_names_their_paths(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        (folder / f'{ENCOUNTER_ID}.json').write_text(json.dumps({'runs': [{'id': 'c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d'}]}))
        with unittest.mock.patch.dict(sc.DENYLIST, {'deny_value_paths': {'encounter': ['runs[].id'], 'trace': []}}):
            code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, '--operator-json', str(folder),
                                                       site=StubSite(run_id=True))
            self.assertEqual(code, 1)
            hits = evidence['hits']['json']
            self.assertTrue(any(hit['id'] == 'deny_value' for hit in hits), hits)
            self.assertEqual(evidence['encounters'][0]['operator_view'], True)
            clean, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, '--operator-json', str(folder))
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
