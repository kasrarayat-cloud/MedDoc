#!/usr/bin/env python3
"""Sign a HUMAN CPT Studio account in, read its session and sign it out again - and nothing else.

    python3 ops/verify_login.py --base-url https://cpt.quillmd.com --credentials reviewer.json \\
        --workspace Gastroenterology --out EVIDENCE_DIR

The login check for the doctor-demonstration reviewer (owner decisions 2026-10-28; session interpretation 40). The
account is a person's, so this check never uploads, reads an encounter, decides or exports: no synthetic approval is
ever attributed to a human account. It makes exactly these requests, in this order, follows no redirect, and asserts
its own request list:

  1. GET  /login/        the sign-in form, for its CSRF token (and the CSRF cookie the page sets)
  2. POST /login/        the form's own hidden fields with the credentials, as a browser posts the form; the answer
                         must redirect to the app ("/") and set a session cookie
  3. GET  /api/session   with that session: the account must be the credentials' username, a human account, a
                         reviewer, in an active membership (only an active one is served, and can_review is true only
                         for an active owner or reviewer), in the named workspace
  4. POST /logout/       with the CSRF token the sign-in rotated, as the app's sign-out form posts it; the answer
                         must redirect to /login/
  5. GET  /api/session   with the SAME session cookie, replayed: it must be refused (401), so the session ended on
                         the server and not only in this client

A step that fails ends the run there (a refused sign-in makes no further request), except that a session once set is
always signed out. The contract is studio/views.py login_view and logout_view, studio/api.py session (api_view
answers 401 without a session) and the cookie names in cptstudio/settings.py; the unit tests hold each to the source.

--credentials names a JSON file {"username": ..., "password": ...}: a regular file no group or other user may read or
write (mode 0600 or stricter); anything else is refused before any request. The password is never printed or
written, also where a server would echo it back. TLS is verified normally (the system trust store and the host
name); a plain http base URL is refused unless its host is the loopback (a local test server), so the password never
crosses a network in clear text.

The evidence, OUT/login-evidence.json (which must not exist yet), holds the requests made (method, path, status,
redirect target), the account as the session served it, and every check - never a password, cookie or token. Exit 0
when every hard check passed, 1 when any failed or the run stopped, 2 on a usage error before any request.
"""
from __future__ import annotations

import argparse
import html
import http.client
import ipaddress
import json
import os
import platform
import secrets
import ssl
import stat
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import quote, quote_plus, urlencode, urljoin, urlsplit

EVIDENCE_SCHEMA = 'cpt-studio-login-evidence@1'
EVIDENCE_NAME = 'login-evidence.json'
# cptstudio/settings.py SESSION_COOKIE_NAME and CSRF_COOKIE_NAME; the form field {% csrf_token %} renders.
SESSION_COOKIE = 'cptstudio_session'
CSRF_COOKIE = 'cptstudio_csrf'
CSRF_FIELD = 'csrfmiddlewaretoken'
LOGIN_PATH, LOGOUT_PATH, SESSION_PATH = '/login/', '/logout/', '/api/session'
EXPECTED_REQUESTS = (('GET', LOGIN_PATH), ('POST', LOGIN_PATH), ('GET', SESSION_PATH), ('POST', LOGOUT_PATH),
                     ('GET', SESSION_PATH))
HUMAN, REVIEWER = 'human', 'reviewer'  # studio/models.py User.HUMAN, Membership.REVIEWER
# A pass needs every one of these, each passing: a check that never ran is never a pass.
REQUIRED_CHECKS = ('login.form', 'login.redirect', 'session.read', 'session.username', 'session.actor_kind',
                   'session.role', 'session.membership_active', 'session.workspace', 'logout.redirect',
                   'logout.session_refused', 'requests.only_expected')
TIMEOUT_SECONDS = 30
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_CREDENTIALS_BYTES = 64 * 1024
USER_AGENT = 'cpt-studio-verify-login/1 (login-only check of a synthetic demonstration account)'
WITHHELD = '[password withheld]'


class UsageError(Exception):
    """A problem found before any request is made (exit 2)."""


class RequestFailed(Exception):
    """A request that got no complete HTTP answer (a connection, TLS or timeout error)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def check(check_id: str, severity: str, ok: bool, reason: str) -> dict:
    status = 'pass' if ok else ('fail' if severity == 'hard' else 'warn')
    return {'id': check_id, 'severity': severity, 'status': status, 'reason': reason}


# --- inputs -----------------------------------------------------------------------------------------------------------

def is_loopback(host: str) -> bool:
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def origin_of(base_url: str) -> str:
    """The base URL's origin (scheme, host and a non-default port), as a browser sends it in Origin."""
    parts = urlsplit(base_url)
    if parts.scheme not in ('https', 'http') or not parts.hostname:
        raise UsageError(f'--base-url must be an http(s) URL with a host: {base_url}')
    if parts.username is not None or parts.password is not None:
        raise UsageError('--base-url must not carry a user name or password')
    try:
        port = parts.port
    except ValueError:
        raise UsageError(f'--base-url has an invalid port: {base_url}') from None
    host = parts.hostname
    if parts.scheme == 'http' and not is_loopback(host):
        raise UsageError('a plain http --base-url is refused unless its host is the loopback: the password would '
                         'cross the network in clear text')
    netloc = f'[{host}]' if ':' in host else host
    if port is not None and port != {'https': 443, 'http': 80}[parts.scheme]:
        netloc += f':{port}'
    return f'{parts.scheme}://{netloc}'


def load_credentials(path: Path) -> tuple[str, str, int]:
    """(username, password, file mode) from a private JSON file, checked on the descriptor that is read."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0))
    except OSError as exc:
        raise UsageError(f'cannot open the credentials file {path}: {exc.strerror}') from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise UsageError(f'the credentials file {path} is not a regular file')
        mode = stat.S_IMODE(info.st_mode)
        if mode & 0o077:
            raise UsageError(f'the credentials file {path} has mode {mode:04o}: a group or other user may read or write '
                             'it; make it private (chmod 600) and keep it so')
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_CREDENTIALS_BYTES:
                raise UsageError(f'the credentials file {path} is over {MAX_CREDENTIALS_BYTES} bytes')
            chunks.append(chunk)
    finally:
        os.close(fd)
    try:
        data = json.loads(b''.join(chunks).decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise UsageError(f'the credentials file {path} is not a JSON object') from None  # never its content
    if not isinstance(data, dict) or not all(isinstance(data.get(key), str) and data[key] for key in ('username', 'password')):
        raise UsageError(f'the credentials file {path} must hold a non-empty "username" and "password"')
    return data['username'], data['password'], mode


class Secret:
    """Every form in which a password could reach an output (as typed, form- and URL-encoded, HTML-escaped, inside
    a JSON string), replaced wherever text leaves this process."""

    def __init__(self, password: str):
        forms = {password, quote(password, safe=''), quote_plus(password), html.escape(password),
                 html.escape(password, quote=False), json.dumps(password)[1:-1],
                 json.dumps(password, ensure_ascii=False)[1:-1]}
        self.forms = sorted((form for form in forms if form), key=len, reverse=True)

    def scrub(self, value):
        if isinstance(value, str):
            for form in self.forms:
                value = value.replace(form, WITHHELD)
            return value
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, dict):
            return {self.scrub(key): self.scrub(item) for key, item in value.items()}
        return value

    def found_in(self, text: str) -> bool:
        return any(form in text for form in self.forms)


# --- HTTP -----------------------------------------------------------------------------------------------------------

class Response:
    def __init__(self, status: int, location: str | None, set_cookies: list[str], content_type: str, body: bytes):
        self.status, self.location, self.set_cookies, self.content_type, self.body = (
            status, location, set_cookies, content_type, body)

    def json(self):
        try:
            return json.loads(self.body.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return None


class Transport:
    """One connection per request, never a redirect followed. Every request is listed before it is made, so the
    list is every request this check made, answered or not."""

    def __init__(self, origin: str, timeout: float = TIMEOUT_SECONDS):
        parts = urlsplit(origin)
        self.https = parts.scheme == 'https'
        self.host, self.port = parts.hostname, parts.port
        self.timeout = timeout
        # Verified normally: CERT_REQUIRED, the host name checked, the system trust store.
        self.tls = ssl.create_default_context() if self.https else None
        self.requests: list[dict] = []

    def send(self, method: str, path: str, *, headers: dict, body: bytes | None = None) -> Response:
        entry = {'method': method, 'path': path, 'status': None, 'location': None, 'at': utc_now()}
        self.requests.append(entry)
        if self.https:
            connection = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=self.tls)
        else:
            connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request(method, path, body=body, headers={'User-Agent': USER_AGENT, **headers})
            answer = connection.getresponse()
            data = answer.read(MAX_BODY_BYTES + 1)
            entry['status'] = answer.status
            entry['location'] = answer.getheader('Location')
            if len(data) > MAX_BODY_BYTES:
                raise RequestFailed(f'{method} {path}: the answer is over {MAX_BODY_BYTES} bytes')
            return Response(answer.status, entry['location'], answer.msg.get_all('Set-Cookie') or [],
                            answer.getheader('Content-Type') or '', data)
        except (OSError, http.client.HTTPException) as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
            raise RequestFailed(f'{method} {path}: {entry["error"]}') from None
        finally:
            connection.close()


def apply_cookies(jar: dict, set_cookies: list[str]) -> set:
    """Apply Set-Cookie headers to ``jar`` (name -> value); returns the names a header deleted (an empty value, a
    zero or negative Max-Age, or an Expires in the past, as django's delete_cookie writes)."""
    deleted = set()
    now = datetime.now(timezone.utc)
    for header in set_cookies:
        cookie = SimpleCookie()
        try:
            cookie.load(header)
        except CookieError:
            continue
        for name, morsel in cookie.items():
            gone = morsel.value == ''
            try:
                gone = gone or (morsel['max-age'] != '' and int(morsel['max-age']) <= 0)
            except ValueError:
                pass
            try:
                gone = gone or (morsel['expires'] != '' and parsedate_to_datetime(morsel['expires']) <= now)
            except (TypeError, ValueError):
                pass
            if gone:
                jar.pop(name, None)
                deleted.add(name)
            else:
                jar[name] = morsel.value
    return deleted


def cookie_header(jar: dict) -> str:
    return '; '.join(f'{name}={value}' for name, value in jar.items())


class _Page(HTMLParser):
    """The forms on a page (their attributes and inputs) and the text of any .form-error element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.errors = [], []
        self._form, self._error_depth = None, 0

    def handle_starttag(self, tag, attrs):
        attrs = {name: value if value is not None else '' for name, value in attrs}
        if tag == 'form':
            self._form = {'attrs': attrs, 'inputs': []}
            self.forms.append(self._form)
        elif tag == 'input' and self._form is not None:
            self._form['inputs'].append(attrs)
        if self._error_depth:
            self._error_depth += 1
        elif 'form-error' in attrs.get('class', '').split():
            self._error_depth = 1
            self.errors.append('')

    def handle_endtag(self, tag):
        if tag == 'form':
            self._form = None
        if self._error_depth:
            self._error_depth -= 1

    def handle_data(self, data):
        if self._error_depth:
            self.errors[-1] += data


def read_page(body: bytes) -> _Page:
    page = _Page()
    page.feed(body.decode('utf-8', 'replace'))
    page.close()
    return page


def login_form(page: _Page, origin: str) -> tuple[list | None, list]:
    """(the form's hidden fields in order, problems) for the page's one sign-in form (form.login-form)."""
    forms = [form for form in page.forms if 'login-form' in form['attrs'].get('class', '').split()]
    if len(forms) != 1:
        return None, [f'{len(forms)} sign-in forms (form.login-form) on the page, not one']
    form = forms[0]
    problems = []
    if form['attrs'].get('method', '').lower() != 'post':
        problems.append('the sign-in form does not post')
    target = urljoin(f'{origin}{LOGIN_PATH}', form['attrs'].get('action', ''))
    if target != f'{origin}{LOGIN_PATH}':
        problems.append(f'the sign-in form posts to {target}, not {LOGIN_PATH}')
    fields = {item.get('name'): item for item in form['inputs'] if item.get('name')}
    hidden = [(item['name'], item.get('value', '')) for item in form['inputs']
              if item.get('type', '').lower() == 'hidden' and item.get('name')]
    if not dict(hidden).get(CSRF_FIELD):
        problems.append(f'no CSRF token ({CSRF_FIELD}) in the form')
    if 'username' not in fields:
        problems.append('no username field')
    if fields.get('password', {}).get('type', '').lower() != 'password':
        problems.append('no password field')
    return hidden, problems


# --- the checks ------------------------------------------------------------------------------------------------------

def session_checks(status: int | None, data, username: str, workspace: str) -> list[dict]:
    """The account the session serves: the credentials' username, a human account, a reviewer, an active
    membership (studio/api.py session serves only an active one; serializers.session_json's can_review is
    Membership.can_review, true only for an active owner or reviewer), in the named workspace."""
    read = status == 200 and isinstance(data, dict)
    data = data if read else {}
    user = data.get('user') if isinstance(data.get('user'), dict) else {}
    space = data.get('workspace') if isinstance(data.get('workspace'), dict) else {}
    unread = '' if read else ' (no session was read)'
    return [
        check('session.read', 'hard', read, f'GET {SESSION_PATH} answered HTTP {status}'
              + ('' if read else ', not 200 with a JSON object')),
        check('session.username', 'hard', read and user.get('username') == username,
              f'username {json.dumps(user.get("username"))}; signed in as {json.dumps(username)}{unread}'),
        check('session.actor_kind', 'hard', read and user.get('actor_kind') == HUMAN,
              f'actor kind {json.dumps(user.get("actor_kind"))}; a {HUMAN} account is expected{unread}'),
        check('session.role', 'hard', read and data.get('role') == REVIEWER,
              f'role {json.dumps(data.get("role"))}; {REVIEWER} is expected{unread}'),
        check('session.membership_active', 'hard', read and data.get('can_review') is True,
              f'the session was served for an active membership only, and can_review is {json.dumps(data.get("can_review"))} '
              f'(true only for an active owner or reviewer){unread}'),
        check('session.workspace', 'hard', read and space.get('name') == workspace,
              f'workspace {json.dumps(space.get("name"))}; {json.dumps(workspace)} is expected{unread}'),
        check('session.synthetic_only', 'soft', read and data.get('synthetic_only') is True,
              f'synthetic_only {json.dumps(data.get("synthetic_only"))}'),
    ]


def account_view(data) -> dict | None:
    """What the evidence keeps of the session: the account and its workspace, nothing else."""
    if not isinstance(data, dict):
        return None
    user = data.get('user') if isinstance(data.get('user'), dict) else {}
    space = data.get('workspace') if isinstance(data.get('workspace'), dict) else {}
    category = space.get('category') if isinstance(space.get('category'), dict) else {}
    return {'user': {key: user.get(key) for key in ('username', 'label', 'actor_kind')},
            'workspace': {'name': space.get('name'), 'category': category.get('slug')},
            'role': data.get('role'), 'can_review': data.get('can_review'),
            'synthetic_only': data.get('synthetic_only'), 'provider_mode': data.get('provider_mode'),
            'release': data.get('release')}


def request_list_check(made: list[dict], signed_in: bool) -> dict:
    """The requests made are the expected ones in order (a prefix where the run stopped), and all five once a
    session was set, so it was signed out and the sign-out proven."""
    pairs = [(item['method'], item['path']) for item in made]
    prefix = tuple(pairs) == EXPECTED_REQUESTS[:len(pairs)]
    complete = len(pairs) == len(EXPECTED_REQUESTS)
    listed = ', '.join(f'{method} {path}' for method, path in pairs) or 'none'
    if not prefix:
        reason = f'requests made: {listed}; not the expected {", ".join(f"{m} {p}" for m, p in EXPECTED_REQUESTS)}'
    elif signed_in and not complete:
        reason = f'requests made: {listed}; a session was set, so all {len(EXPECTED_REQUESTS)} were owed (sign-out and its proof)'
    else:
        reason = f'requests made: {listed}; no other request'
    return check('requests.only_expected', 'hard', prefix and (complete or not signed_in), reason)


def result_of(checks: list[dict], run_error: str | None) -> str:
    passed = {item['id'] for item in checks if item['status'] == 'pass'}
    failed = any(item['status'] == 'fail' for item in checks)
    return 'pass' if not run_error and not failed and all(name in passed for name in REQUIRED_CHECKS) else 'fail'


def _headers(origin: str, accept: str, cookies: str = '', form: bool = False, referer: str = '') -> dict:
    headers = {'Accept': accept}
    if cookies:
        headers['Cookie'] = cookies
    if form:  # a same-origin form post, as the browser makes it (django's CSRF check reads Origin first)
        headers.update({'Content-Type': 'application/x-www-form-urlencoded', 'Origin': origin, 'Referer': referer})
    return headers


def sign_in_and_out(transport: Transport, origin: str, username: str, password: str, workspace: str) -> dict:
    """The five requests and their checks: {'checks', 'session', 'signed_in', 'error'}."""
    checks, jar, out = [], {}, {'session': None, 'signed_in': False, 'error': None}
    try:
        page = transport.send('GET', LOGIN_PATH, headers=_headers(origin, 'text/html'))
        apply_cookies(jar, page.set_cookies)
        hidden, problems = login_form(read_page(page.body), origin) if page.status == 200 else (None, [])
        if page.status != 200:
            problems = [f'GET {LOGIN_PATH} answered HTTP {page.status}']
        if CSRF_COOKIE not in jar:
            problems.append(f'no CSRF cookie ({CSRF_COOKIE}) was set')
        checks.append(check('login.form', 'hard', not problems, '; '.join(problems)
                            or f'the sign-in form, its CSRF token and the {CSRF_COOKIE} cookie'))
        if problems:
            return {**out, 'checks': checks}

        fields = hidden + [('username', username), ('password', password)]
        answer = transport.send('POST', LOGIN_PATH, body=urlencode(fields).encode('utf-8'), headers=_headers(
            origin, 'text/html', cookie_header(jar), form=True, referer=f'{origin}{LOGIN_PATH}'))
        apply_cookies(jar, answer.set_cookies)
        session = jar.get(SESSION_COOKIE)
        target = urljoin(f'{origin}{LOGIN_PATH}', answer.location) if answer.location else None
        redirected = answer.status in (302, 303) and target == f'{origin}/'
        said = '' if redirected else ' '.join(' '.join(read_page(answer.body).errors).split())
        checks.append(check('login.redirect', 'hard', redirected and bool(session),
                            f'POST {LOGIN_PATH} answered HTTP {answer.status}'
                            + (f', redirecting to {target}' if target else ', with no redirect')
                            + ('' if redirected else f' (the app, {origin}/, is expected)')
                            + ('; a session cookie was set' if session else '; no session cookie was set')
                            + (f'; the page said: {said}' if said else '')))
        if not session:
            return {**out, 'checks': checks}
        out['signed_in'] = True

        try:  # whatever happens reading the session, the session is signed out
            reply = transport.send('GET', SESSION_PATH, headers=_headers(origin, 'application/json', cookie_header(jar)))
            data = reply.json()
            checks.extend(session_checks(reply.status, data, username, workspace))
            out['session'] = account_view(data) if reply.status == 200 else None
        except Exception as exc:  # noqa: BLE001 - recorded, and the sign-out below still runs
            out['error'] = str(exc) if isinstance(exc, RequestFailed) else f'{type(exc).__name__}: {exc}'
        out['error'] = sign_out(transport, origin, jar, session, checks) or out['error']
    except RequestFailed as exc:
        out['error'] = str(exc)
    return {**out, 'checks': checks}


def sign_out(transport: Transport, origin: str, jar: dict, session: str, checks: list) -> str | None:
    """POST /logout/ with the CSRF token the sign-in rotated, then GET /api/session with the session cookie the
    sign-in set, replayed: it must be refused. Returns the first request error, if any."""
    error = None
    try:
        answer = transport.send('POST', LOGOUT_PATH, body=urlencode([(CSRF_FIELD, jar.get(CSRF_COOKIE, ''))]).encode(),
                                headers=_headers(origin, 'text/html', cookie_header(jar), form=True, referer=f'{origin}/'))
        deleted = apply_cookies(jar, answer.set_cookies)
        target = urljoin(f'{origin}{LOGOUT_PATH}', answer.location) if answer.location else None
        checks.append(check('logout.redirect', 'hard', answer.status in (302, 303) and target == f'{origin}{LOGIN_PATH}',
                            f'POST {LOGOUT_PATH} answered HTTP {answer.status}'
                            + (f', redirecting to {target}' if target else ', with no redirect')
                            + f' ({origin}{LOGIN_PATH} is expected)'))
        checks.append(check('logout.cookie_cleared', 'soft', SESSION_COOKIE in deleted,
                            f'the sign-out {"deleted" if SESSION_COOKIE in deleted else "did not delete"} the session cookie'))
    except RequestFailed as exc:
        error = str(exc)
        checks.append(check('logout.redirect', 'hard', False, error))
    try:
        probe = transport.send('GET', SESSION_PATH, headers=_headers(origin, 'application/json', f'{SESSION_COOKIE}={session}'))
        checks.append(check('logout.session_refused', 'hard', probe.status == 401,
                            f'the session cookie the sign-in set, replayed after the sign-out: GET {SESSION_PATH} answered '
                            f'HTTP {probe.status} ({"refused: the session ended on the server" if probe.status == 401 else "401 is expected"})'))
    except RequestFailed as exc:
        error = error or str(exc)
        checks.append(check('logout.session_refused', 'hard', False, str(exc)))
    return error


# --- the run ---------------------------------------------------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base-url', required=True, help='the CPT Studio origin, e.g. https://cpt.quillmd.com')
    parser.add_argument('--credentials', required=True, type=Path, help='a private JSON file {"username", "password"}')
    parser.add_argument('--workspace', required=True, help='the workspace name the session must report')
    parser.add_argument('--out', required=True, type=Path, help=f'the evidence directory (gets {EVIDENCE_NAME})')
    return parser.parse_args(argv)


def write_evidence(path: Path, evidence: dict, secret: Secret) -> None:
    text = json.dumps(secret.scrub(evidence), indent=2) + '\n'
    if secret.found_in(text):  # a form the scrub cannot see through: write nothing that holds it
        text = json.dumps({'schema': EVIDENCE_SCHEMA, 'run_id': evidence['run_id'], 'result': 'fail',
                           'run_error': 'the evidence would have held the password; it was not written'}, indent=2) + '\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_CLOEXEC', 0), 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(text)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        origin = origin_of(args.base_url)
        if not args.workspace.strip():
            raise UsageError('--workspace must name the workspace')
        username, password, mode = load_credentials(args.credentials)
        evidence_path = args.out / EVIDENCE_NAME
        if evidence_path.exists():
            raise UsageError(f'{args.out} already holds {EVIDENCE_NAME}; use a fresh --out directory')
    except UsageError as exc:
        print(f'verify_login: {exc}', file=sys.stderr)
        return 2
    secret = Secret(password)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    started = utc_now()
    transport = Transport(origin)
    try:
        outcome = sign_in_and_out(transport, origin, username, password, args.workspace)
    except Exception as exc:  # noqa: BLE001 - a defect of this check: recorded (scrubbed), and the run fails
        outcome = {'checks': [], 'session': None, 'signed_in': None, 'error': f'{type(exc).__name__}: {exc}'}
    checks = outcome['checks'] + [request_list_check(transport.requests, outcome['signed_in'] is not False)]
    evidence = {
        'schema': EVIDENCE_SCHEMA, 'run_id': f'login-{started.replace("-", "").replace(":", "").replace(".", "")}-'
                                            f'{secrets.token_hex(4)}',
        'started_at': started, 'finished_at': utc_now(), 'base_url': origin, 'synthetic_only': True,
        'tool': {'python': platform.python_version(),
                 'transport': 'https: certificate and host name verified (system trust store)' if transport.https
                 else 'http to the loopback (a local test server)'},
        'credentials': {'username': username, 'file_mode': f'{mode:04o}'},
        'expected': {'username': username, 'actor_kind': HUMAN, 'role': REVIEWER, 'workspace': args.workspace,
                     'requests': [f'{method} {path}' for method, path in EXPECTED_REQUESTS]},
        'requests': transport.requests, 'session': outcome['session'], 'checks': checks,
        'run_error': outcome['error'], 'result': result_of(checks, outcome['error']),
    }
    write_evidence(evidence_path, evidence, secret)
    failed = [item['id'] for item in checks if item['status'] == 'fail']
    print(secret.scrub(f'login {username} at {origin}: {evidence["result"]}'
                       + (f' [{", ".join(failed)}]' if failed else '')
                       + (f' (run stopped: {outcome["error"]})' if outcome['error'] else '')))
    print(f'evidence: {evidence_path}')
    return 0 if evidence['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
