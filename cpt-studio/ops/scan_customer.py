#!/usr/bin/env python3
"""Scan every customer surface of a running CPT Studio for what a customer must never be shown - and nothing else.

    python3 ops/scan_customer.py --base-url https://cpt.quillmd.com --credentials customer.json --out EVIDENCE_DIR
        [--encounter ID ...] [--all [--limit N]] [--operator-json DIR]

The owner directive of 2026-11-03 (section 2) keeps provider and model identities, usage, request ids, hashes, trace
links, retrieval logs and rule ids out of every customer screen, API response and download, enforced on the server
(cpt-studio/CORE-UX-DESIGN.md sections 5 and 7). This tool signs a CUSTOMER account in and makes only GET requests:

  GET /                         the customer page, and each same-origin script and stylesheet it loads: scanned whole
  GET /api/session              against the customer contract's session keys, scanned
  GET /api/encounters           the list, against the contract's list keys, scanned
  for each encounter named (--encounter, repeatable) or listed (--all, at most --limit, newest first):
    GET /api/encounters/<id>             against the contract (every key listed, nothing else), scanned
    GET <document.original_url>          its status and headers only: the document is the customer's own
    GET <reports[].download_url>         every customer report, scanned whole, with no X-Content-SHA256 header
    GET every /ops/ URL of it            each must answer 404 to this session
    GET /api/encounters/<id>/trace       must answer 404 (removed for everyone)
  POST /logout/ and GET /api/session     the session must then be refused (verify_login.py's sign-out proof)

Every body and header is scanned with ops/verification/customer-denylist.json (the walk ops/verify_browser.cjs and
ops/verify_downloads.py read the same list, and this module's tests run its vectors) and every payload is held to
ops/verification/customer-contract.json. A string that is a quotation of the encounter's own document is not scanned.
--operator-json DIR adds the operator view's own identifiers (run ids, request hashes, models, check ids ...): files
<encounter id>.json (GET /ops/api/encounters/<id>, read by an operator) and, optionally, <encounter id>.trace.json.

Sign-in and transport are ops/verify_login.py's: --credentials a private JSON file with top-level "username" and
"password" (or --username with --password-file), refused if a group or other user may read it; TLS verified; a plain
http base URL only on the loopback; no redirect followed; the password never printed or written. Stdlib only.

The evidence, OUT/scan-evidence.json (which must not exist yet), holds every request made (method, path, status), the
encounters scanned, every check and the hits (where and what matched, never a password). Exit 0 when every hard check
passed, 1 when any failed or the run stopped, 2 on a usage error before any request.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import re
import secrets
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_scan_customer_login', HERE / 'verify_login.py')
login = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('cpt_scan_customer_login', login)
_spec.loader.exec_module(login)

EVIDENCE_SCHEMA = 'cpt-studio-customer-scan@1'
EVIDENCE_NAME = 'scan-evidence.json'
DENYLIST = json.loads((HERE / 'verification' / 'customer-denylist.json').read_text(encoding='utf-8'))
CONTRACT = json.loads((HERE / 'verification' / 'customer-contract.json').read_text(encoding='utf-8'))
# ASCII-only and case-insensitive, as the walk's JavaScript reads the same patterns ('gi' without 'u'): Python's re.I
# alone would fold the long s and the Kelvin sign onto ASCII letters, which JavaScript does not.
FLAGS = re.ASCII | re.IGNORECASE
PATTERNS = [(p['id'], p['severity'], frozenset(p['surfaces']), re.compile(p['source'], FLAGS)) for p in DENYLIST['patterns']]
FORBIDDEN_KEYS = frozenset(DENYLIST['forbidden_keys'])
DENY_SHAPE = re.compile(DENYLIST['deny_value_shape'])
ISO_TIMESTAMP = re.compile(CONTRACT['iso_pattern'])
DATE_ONLY = re.compile(CONTRACT['date_pattern'])
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
# Response headers that carry no customer-facing wording (ops/verify_browser.cjs UNSCANNED_HEADERS).
UNSCANNED_HEADERS = frozenset({'set-cookie', 'date', 'etag', 'last-modified', 'content-length', 'content-security-policy',
                               'content-security-policy-report-only', 'strict-transport-security', 'permissions-policy',
                               'report-to', 'nel', 'expires', 'cache-control', 'vary', 'connection', 'keep-alive',
                               'transfer-encoding', 'content-encoding', 'accept-ranges', 'age'})
OPS_GET_PATHS = ('/ops/', '/ops/assets/ops.js', '/ops/api/encounters', '/ops/api/encounters/{id}',
                 '/ops/api/encounters/{id}/trace', '/ops/api/encounters/{id}/reports')
REMOVED_PATHS = ('/api/encounters/{id}/trace',)
MAX_HITS = 60


# --- the shared denylist (ops/verification/customer-denylist.json); ops/verify_browser.cjs is the same reader -------

@dataclass
class ScanContext:
    document_text: str = ''
    deny_values: list = field(default_factory=list)
    allowed: list = field(default_factory=list)


def scan_context(document_text: str = '', deny_values=(), allowed=()) -> ScanContext:
    text = document_text or ''
    values = sorted({value for value in deny_values if value and value not in text})
    allowed = sorted({item for item in [*DENYLIST['allowed'], *allowed] if item}, key=len, reverse=True)
    return ScanContext(text, values, allowed)


def _excerpt(text: str, at: int, length: int) -> str:
    start = max(0, at - 24)
    end = at + length + 24
    return ('…' if start else '') + re.sub(r'\s+', ' ', text[start:end]) + ('…' if end < len(text) else '')


def scan_text(text, ctx: ScanContext, surface: str, where: str = '', hits: list | None = None) -> list:
    """The hits of one string on one surface ({id, severity, surface, where, match}). A string that is a substring of
    the document text is a quotation of it and is not scanned (bundle text always is)."""
    hits = [] if hits is None else hits
    raw = text if isinstance(text, str) else ('' if text is None else str(text))
    if not raw.strip():
        return hits
    if surface != 'bundle' and ctx.document_text and raw in ctx.document_text:
        return hits
    cleaned = raw
    for allowed in ctx.allowed:
        cleaned = cleaned.replace(allowed, ' ')
    for pattern_id, severity, surfaces, regex in PATTERNS:
        if surface not in surfaces:
            continue
        for match in regex.finditer(cleaned):
            hits.append({'id': pattern_id, 'severity': severity, 'surface': surface, 'where': where,
                         'match': _excerpt(cleaned, match.start(), len(match.group()))})
    if surface != 'bundle':
        for value in ctx.deny_values:
            if value in cleaned:
                hits.append({'id': 'deny_value', 'severity': 'hard', 'surface': surface, 'where': where,
                             'match': f'{value[:14]}…'})
    return hits


def scan_json(value, ctx: ScanContext, where: str = '$', hits: list | None = None, surface: str = 'json') -> list:
    """Every string value and every key of a JSON value; a forbidden key is a hit by itself."""
    hits = [] if hits is None else hits
    if isinstance(value, str):
        return scan_text(value, ctx, surface, where, hits)
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_json(item, ctx, f'{where}[{index}]', hits, surface)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                hits.append({'id': 'forbidden_key', 'severity': 'hard', 'surface': surface, 'where': f'{where}.{key}',
                             'match': key})
            scan_text(key, ctx, surface, f'{where}.{key} (key)', hits)
            scan_json(item, ctx, f'{where}.{key}', hits, surface)
    return hits


def csv_rows(text: str) -> list:
    """RFC 4180 rows (quoted cells, doubled quotes, CR LF or LF), as ops/verify_browser.cjs csvRows reads them."""
    rows, row, cell, quoted, i = [], [], '', False, 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == '"' and text[i + 1:i + 2] == '"':
                cell += '"'
                i += 1
            elif ch == '"':
                quoted = False
            else:
                cell += ch
        elif ch == '"':
            quoted = True
        elif ch == ',':
            row.append(cell)
            cell = ''
        elif ch in '\r\n':
            if ch == '\r' and text[i + 1:i + 2] == '\n':
                i += 1
            row.append(cell)
            rows.append(row)
            row, cell = [], ''
        else:
            cell += ch
        i += 1
    if cell or row:
        row.append(cell)
        rows.append(row)
    return rows


def scan_file(text: str, ctx: ScanContext, name: str, fmt: str, hits: list | None = None) -> list:
    """A downloaded file, whole: a CSV cell by cell, a TXT line by line, any quoted passage that is the document's own
    text set aside (a report quotes the document)."""
    hits = [] if hits is None else hits
    if fmt == 'csv':
        for r, row in enumerate(csv_rows(text), start=1):
            for c, cell in enumerate(row, start=1):
                scan_text(cell, ctx, 'file', f'{name} row {r} cell {c}', hits)
        return hits
    for index, line in enumerate(re.split(r'\r?\n', text), start=1):
        rest = line
        for quoted in re.findall(r'"[^"]*"', line):
            if quoted[1:-1] in ctx.document_text:
                rest = rest.replace(quoted, '""', 1)
        if rest.strip() and rest.strip() in ctx.document_text:
            continue
        scan_text(rest, ctx, 'file', f'{name} line {index}', hits)
    return hits


def scan_headers(headers, ctx: ScanContext, where: str, hits: list | None = None) -> list:
    hits = [] if hits is None else hits
    items = headers.items() if isinstance(headers, dict) else headers
    for name, value in items:
        if name.lower() in UNSCANNED_HEADERS:
            continue
        scan_text(name, ctx, 'header', f'{where} header {name} (name)', hits)
        scan_text(str(value), ctx, 'header', f'{where} header {name}', hits)
    return hits


def harvest(value, dotted: str) -> list:
    """The strings at a dotted path ('a.b[]' takes each element of a.b, a numeric part indexes a list)."""
    nodes = [value]
    for part in dotted.split('.'):
        each = part.endswith('[]')
        key = part[:-2] if each else part
        found = []
        for node in nodes:
            if isinstance(node, list) and key.isdigit():
                nxt = node[int(key)] if int(key) < len(node) else None
            elif isinstance(node, dict):
                nxt = node.get(key)
            else:
                nxt = None
            if each:
                found.extend(nxt if isinstance(nxt, list) else [])
            elif nxt is not None:
                found.append(nxt)
        nodes = found
    return [node for node in nodes if isinstance(node, str)]


def deny_values_from(encounter: dict, trace: dict | None = None) -> list:
    """Every identifier the operator view (and its trace) holds that a customer surface must never carry:
    identifier-shaped (a digit or . : @ / - in it) and at least deny_value_min_length long."""
    paths = DENYLIST['deny_value_paths']
    values = [v for p in paths['encounter'] for v in harvest(encounter, p)]
    if trace:
        values += [v for p in paths['trace'] for v in harvest(trace, p)]
    return sorted({v for v in values if len(v) >= DENYLIST['deny_value_min_length'] and DENY_SHAPE.search(v)})


# --- the shared contract (ops/verification/customer-contract.json); ops/verify_browser.cjs shapeProblems ------------

def _kind(value) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, list):
        return 'a list'
    if isinstance(value, dict):
        return 'an object'
    return {int: 'number', float: 'number', str: 'string'}.get(type(value), type(value).__name__)


_SCALARS = {
    'string': lambda v: isinstance(v, str),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'boolean': lambda v: isinstance(v, bool),
    'any': lambda v: True,
    'date': lambda v: isinstance(v, str) and bool(DATE_ONLY.match(v)),
    'iso': lambda v: isinstance(v, str) and bool(ISO_TIMESTAMP.match(v)),
}
_MISSING = object()


def shape_problems(value, node, where: str = '$', out: list | None = None, types: dict | None = None) -> list:
    """The differences between a value and a contract node, each '<where>: <what>'; at most 60."""
    out = [] if out is None else out
    types = CONTRACT['types'] if types is None else types
    if len(out) >= 60:
        return out
    if isinstance(node, str):
        nullable = node.endswith('?')
        base = node[:-1] if nullable else node
        test = _SCALARS.get(base)
        if test is None:
            out.append(f'{where}: the contract names an unknown type {base}')
        elif value is None and (nullable or base == 'any'):
            pass
        elif value is _MISSING or not test(value):
            out.append(f'{where}: {"nothing" if value is _MISSING else _kind(value)} where the contract has {node}')
        return out
    if not isinstance(node, dict):
        out.append(f'{where}: the contract node is not understood')
        return out
    if 'ref' in node:
        if value is None and node.get('nullable'):
            return out
        if node['ref'] not in types:
            out.append(f'{where}: the contract names an unknown type {node["ref"]}')
            return out
        return shape_problems(value, types[node['ref']], where, out, types)
    if value is None and node.get('nullable'):
        return out
    if 'enum' in node:
        if isinstance(value, bool) or value not in node['enum']:  # the contract's enums are words, never booleans
            out.append(f'{where}: {json.dumps(value)} is not one of {"|".join(str(item) for item in node["enum"])}')
        return out
    if 'items' in node:
        if not isinstance(value, list):
            out.append(f'{where}: {_kind(value)} where the contract has a list')
        else:
            for index, item in enumerate(value):
                shape_problems(item, node['items'], f'{where}[{index}]', out, types)
        return out
    if 'map' in node:
        if not isinstance(value, dict):
            out.append(f'{where}: {_kind(value)} where the contract has an object')
        else:
            for key, item in value.items():
                shape_problems(item, node['map'], f'{where}.{key}', out, types)
        return out
    if isinstance(node.get('keys'), dict):
        if not isinstance(value, dict):
            out.append(f'{where}: {_kind(value)} where the contract has an object')
            return out
        for key, child in node['keys'].items():
            if key not in value:
                out.append(f'{where}.{key}: missing (the contract lists it)')
            else:
                shape_problems(value[key], child, f'{where}.{key}', out, types)
        for key in value:
            if key not in node['keys']:
                out.append(f'{where}.{key}: not in the customer contract')
        return out
    out.append(f'{where}: the contract node is not understood')
    return out


# --- checks ------------------------------------------------------------------------------------------------------

def check_scan(check_id: str, hits: list, what: str) -> list:
    hard = [h for h in hits if h['severity'] == 'hard']
    soft = [h for h in hits if h['severity'] != 'hard']

    def words(items):
        shown = [f'{h["id"]} at {h["where"]}: {json.dumps(h["match"], ensure_ascii=False)}' for h in items[:6]]
        return '; '.join(shown) + (f'; and {len(items) - 6} more' if len(items) > 6 else '')

    out = [login.check(check_id, 'hard', not hard, f'{len(hard)} hit(s) in {what}: {words(hard)}' if hard
                       else f'{what}: no provider, model, usage, id, hash, trace, rule-id or orchestration text')]
    if soft:
        out.append(login.check(f'{check_id}.wording', 'soft', False, f'{len(soft)} soft hit(s) in {what}: {words(soft)}'))
    return out


def check_contract(value, schema: str, check_id: str) -> dict:
    problems = shape_problems(value, CONTRACT[schema])
    return login.check(check_id, 'hard', not problems,
                       f'{len(problems)} difference(s) from the customer contract: {"; ".join(problems[:10])}' if problems
                       else f'the {schema} payload carries every key the contract lists and nothing else')


class _Assets(HTMLParser):
    """The scripts and stylesheets a page loads, and how many inline scripts it holds."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.assets, self.scripts, self.inline, self._in_script, self._script_text = [], 0, 0, False, ''

    def handle_starttag(self, tag, attrs):
        attrs = {name: value or '' for name, value in attrs}
        if tag == 'script':
            if attrs.get('src'):
                self.scripts += 1
                self.assets.append(attrs['src'])
            else:
                self._in_script, self._script_text = True, ''
        elif tag == 'link' and attrs.get('href') and set(attrs.get('rel', '').lower().split()) & {'stylesheet', 'modulepreload', 'preload'}:
            self.assets.append(attrs['href'])

    def handle_data(self, data):
        if self._in_script:
            self._script_text += data

    def handle_endtag(self, tag):
        if tag == 'script' and self._in_script:
            self._in_script = False
            if self._script_text.strip():
                self.inline += 1


def page_assets(body: bytes) -> _Assets:
    parser = _Assets()
    parser.feed(body.decode('utf-8', 'replace'))
    parser.close()
    return parser


class Scanner:
    """The signed-in customer session and what it reads; every request is listed by the transport before it is made."""

    def __init__(self, transport, origin: str, jar: dict):
        self.transport, self.origin, self.jar = transport, origin, jar
        self.checks, self.hits = [], {'json': [], 'header': [], 'file': [], 'bundle': []}

    def get(self, where: str, accept: str = 'application/json', read_body: bool = True):
        return self.transport.send('GET', where, headers=login._headers(self.origin, accept, login.cookie_header(self.jar)),
                                   read_body=read_body)

    def bundle(self, ctx: ScanContext) -> None:
        page = self.get('/', 'text/html')
        self.checks.append(login.check('bundle.read', 'hard', page.status == 200, f'GET / answered HTTP {page.status}'))
        if page.status != 200:
            return
        scan_text(page.body.decode('utf-8', 'replace'), ctx, 'bundle', 'GET /', self.hits['bundle'])
        assets = page_assets(page.body)
        foreign = []
        for address in dict.fromkeys(assets.assets):
            parts = urlsplit(address)
            if parts.scheme or parts.netloc:
                if f'{parts.scheme}://{parts.netloc}' != self.origin:
                    foreign.append(address)
                    continue
            where = parts.path + (f'?{parts.query}' if parts.query else '')
            asset = self.get(where, '*/*')
            if asset.status != 200:
                self.checks.append(login.check('bundle.read', 'hard', False, f'GET {where} answered HTTP {asset.status}'))
                continue
            scan_text(asset.body.decode('utf-8', 'replace'), ctx, 'bundle', f'GET {where}', self.hits['bundle'])
        self.checks.append(login.check('bundle.one_script', 'hard', assets.scripts == 1 and assets.inline == 0 and not foreign,
                                       f'{assets.scripts} script(s) loaded by the customer page, {assets.inline} inline'
                                       + (f'; from another origin: {", ".join(foreign)}' if foreign else '')))

    def json_get(self, where: str, ctx: ScanContext):
        answer = self.get(where)
        scan_headers(answer.headers, ctx, f'GET {where}', self.hits['header'])
        data = answer.json()
        if data is None:
            scan_text(answer.body.decode('utf-8', 'replace'), ctx, 'json', f'GET {where} (not JSON)', self.hits['json'])
        else:
            scan_json(data, ctx, f'GET {where}', self.hits['json'])
        return answer, data

    def encounter(self, encounter_id: str, operator_dir: Path | None) -> dict:
        short = encounter_id[:8]
        operator, trace = None, None
        if operator_dir is not None:
            path = operator_dir / f'{encounter_id}.json'
            if path.is_file():
                operator = json.loads(path.read_text(encoding='utf-8'))
            traced = operator_dir / f'{encounter_id}.trace.json'
            if traced.is_file():
                trace = json.loads(traced.read_text(encoding='utf-8'))
        probe = scan_context()
        answer = self.get(f'/api/encounters/{encounter_id}')
        data = answer.json()
        text = ((operator or {}).get('revision') or {}).get('text') or ((data or {}).get('document') or {}).get('text') or ''
        ctx = scan_context(text, deny_values_from(operator, trace) if operator else (), [urlsplit(self.origin).hostname or ''])
        scan_headers(answer.headers, ctx, f'GET /api/encounters/{encounter_id}', self.hits['header'])
        record = {'id': encounter_id, 'status': answer.status, 'operator_view': operator is not None, 'reports': 0}
        if answer.status != 200 or not isinstance(data, dict):
            self.checks.append(login.check(f'encounter.{short}.read', 'hard', False, f'GET /api/encounters/{encounter_id} answered HTTP {answer.status}'))
            return record
        scan_json(data, ctx, f'GET /api/encounters/{encounter_id}', self.hits['json'])
        self.checks.append(check_contract(data, 'encounter', f'customer.contract.{short}'))
        original = (data.get('document') or {}).get('original_url')
        if isinstance(original, str) and original.startswith('/'):
            got = self.get(original, '*/*', read_body=False)  # its headers: the document itself is the customer's own
            scan_headers(got.headers, ctx, f'GET {original}', self.hits['header'])
            self.checks.append(login.check(f'original.{short}', 'hard', got.status == 200, f'GET {original} answered HTTP {got.status}'))
        for report in data.get('reports') or []:
            url = report.get('download_url') if isinstance(report, dict) else None
            if not (isinstance(url, str) and url.startswith('/api/reports/')):
                self.checks.append(login.check(f'report.{short}.url', 'hard', False, f'a report with no customer download URL: {json.dumps(url)}'))
                continue
            got = self.get(url, '*/*')
            record['reports'] += 1
            scan_headers(got.headers, ctx, f'GET {url}', self.hits['header'])
            hashed = any(name.lower() == 'x-content-sha256' for name, _ in got.headers)
            self.checks.append(login.check(f'report.{short}.{report.get("kind")}.{report.get("fmt")}', 'hard', got.status == 200 and not hashed,
                                           f'GET {url} answered HTTP {got.status}' + ('; it carries X-Content-SHA256' if hashed else '')))
            if got.status == 200:
                scan_file(got.body.decode('utf-8', 'replace'), ctx, f'{report.get("kind")}.{report.get("fmt")}', report.get('fmt', 'txt'), self.hits['file'])
        wrong = []
        for template in OPS_GET_PATHS + REMOVED_PATHS:
            where = template.format(id=encounter_id)
            got = self.get(where)
            scan_text(got.body.decode('utf-8', 'replace'), probe if got.status == 404 else ctx, 'json', f'GET {where} ({got.status})', self.hits['json'])
            if got.status != 404:
                wrong.append(f'GET {where} -> {got.status}')
        self.checks.append(login.check(f'authorization.{short}', 'hard', not wrong, '; '.join(wrong)
                                       or f'{len(OPS_GET_PATHS) + len(REMOVED_PATHS)} operator and removed URL(s), each 404 to the customer'))
        return record


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base-url', required=True, help='the CPT Studio origin, e.g. https://cpt.quillmd.com')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--credentials', type=Path, help='a private JSON file with top-level "username" and "password"')
    source.add_argument('--password-file', type=Path, help='a private file holding only the password (with --username)')
    parser.add_argument('--username', help='the account signed in with --password-file')
    parser.add_argument('--encounter', action='append', default=[], help='an encounter id to scan (repeatable)')
    parser.add_argument('--all', action='store_true', help='scan every encounter the list serves (at most --limit)')
    parser.add_argument('--limit', type=int, default=50, help='the most encounters --all scans (default 50)')
    parser.add_argument('--operator-json', type=Path, help='a directory of operator encounter JSON (<id>.json, <id>.trace.json)')
    parser.add_argument('--out', required=True, type=Path, help=f'the evidence directory (gets {EVIDENCE_NAME})')
    return parser.parse_args(argv)


def run(transport, origin: str, username: str, password: str, encounters: list, every: bool, limit: int,
        operator_dir: Path | None) -> dict:
    """The sign-in, the scans and the sign-out: {'checks', 'hits', 'encounters', 'signed_in', 'error'}."""
    jar, out = {}, {'checks': [], 'hits': {}, 'encounters': [], 'signed_in': False, 'error': None}
    try:
        page = transport.send('GET', login.LOGIN_PATH, headers=login._headers(origin, 'text/html'))
        login.apply_cookies(jar, page.set_cookies)
        hidden, problems = login.login_form(login.read_page(page.body), origin) if page.status == 200 else (None, [f'GET {login.LOGIN_PATH} answered HTTP {page.status}'])
        if problems:
            out['checks'].append(login.check('login.form', 'hard', False, '; '.join(problems)))
            return out
        fields = hidden + [('username', username), ('password', password)]
        answer = transport.send('POST', login.LOGIN_PATH, body=urlencode(fields).encode('utf-8'), headers=login._headers(
            origin, 'text/html', login.cookie_header(jar), form=True, referer=f'{origin}{login.LOGIN_PATH}'))
        login.apply_cookies(jar, answer.set_cookies)
        session = jar.get(login.SESSION_COOKIE)
        out['checks'].append(login.check('login.signed_in', 'hard', answer.status in (302, 303) and bool(session),
                                         f'POST {login.LOGIN_PATH} answered HTTP {answer.status}' + ('' if session else '; no session cookie was set')))
        if not session:
            return out
        out['signed_in'] = True
        scanner = Scanner(transport, origin, jar)
        try:
            base = scan_context(allowed=[urlsplit(origin).hostname or ''])
            scanner.bundle(base)
            reply, data = scanner.json_get(login.SESSION_PATH, base)
            scanner.checks.append(check_contract(data, 'session', 'session.contract') if reply.status == 200
                                  else login.check('session.contract', 'hard', False, f'GET {login.SESSION_PATH} answered HTTP {reply.status}'))
            listed, rows = scanner.json_get('/api/encounters', base)
            scanner.checks.append(check_contract(rows, 'list', 'customer.list_contract') if listed.status == 200
                                  else login.check('customer.list_contract', 'hard', False, f'GET /api/encounters answered HTTP {listed.status}'))
            named = list(dict.fromkeys(encounters))
            if every and isinstance(rows, dict):
                named += [row.get('id') for row in rows.get('encounters') or [] if isinstance(row, dict) and row.get('id') not in named][:max(0, limit)]
            for encounter_id in named:
                if not (isinstance(encounter_id, str) and UUID.match(encounter_id)):
                    scanner.checks.append(login.check('encounter.id', 'hard', False, f'not an encounter id: {json.dumps(encounter_id)}'))
                    continue
                out['encounters'].append(scanner.encounter(encounter_id, operator_dir))
            if not named:
                scanner.checks.append(login.check('encounters.scanned', 'soft', False, 'no encounter was named or listed, so none was scanned'))
        except Exception as exc:  # noqa: BLE001 - recorded; the sign-out below still runs
            out['error'] = str(exc) if isinstance(exc, login.RequestFailed) else f'{type(exc).__name__}: {exc}'
        out['checks'].extend(scanner.checks)
        for surface, what in (('json', 'the customer API bodies'), ('header', 'the customer response headers'),
                              ('file', 'the customer report downloads'), ('bundle', 'the served page and bundle')):
            out['checks'].extend(check_scan(f'scan.{surface}', scanner.hits[surface], what))
            out['hits'][surface] = scanner.hits[surface][:MAX_HITS]
        out['error'] = login.sign_out(transport, origin, jar, session, out['checks']) or out['error']
    except login.RequestFailed as exc:
        out['error'] = str(exc)
    return out


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        origin = login.origin_of(args.base_url)
        if args.password_file is not None:
            if not (args.username or '').strip():
                raise login.UsageError('--password-file needs --username, the account it signs in')
            username, password, mode = login.load_password_file(args.password_file, args.username)
        else:
            if args.username is not None:
                raise login.UsageError('--username goes with --password-file; a --credentials file names its own account')
            username, password, mode = login.load_credentials(args.credentials)
        bad = [item for item in args.encounter if not UUID.match(item)]
        if bad:
            raise login.UsageError(f'not an encounter id (a lowercase UUID): {", ".join(bad)}')
        if args.limit < 0:
            raise login.UsageError('--limit must not be negative')
        if args.operator_json is not None and not args.operator_json.is_dir():
            raise login.UsageError(f'--operator-json {args.operator_json} is not a directory')
        evidence_path = args.out / EVIDENCE_NAME
        if evidence_path.exists():
            raise login.UsageError(f'{args.out} already holds {EVIDENCE_NAME}; use a fresh --out directory')
    except login.UsageError as exc:
        print(f'scan_customer: {exc}', file=sys.stderr)
        return 2
    secret = login.Secret(password)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    started = login.utc_now()
    transport = login.Transport(origin)
    try:
        outcome = run(transport, origin, username, password, args.encounter, args.all, args.limit, args.operator_json)
    except Exception as exc:  # noqa: BLE001 - a defect of this tool: recorded (scrubbed), and the run fails
        outcome = {'checks': [], 'hits': {}, 'encounters': [], 'signed_in': None, 'error': f'{type(exc).__name__}: {exc}'}
    failed = [item['id'] for item in outcome['checks'] if item['status'] == 'fail']
    result = 'pass' if not outcome['error'] and not failed and outcome['checks'] else 'fail'
    posts = [item for item in transport.requests if item['method'] != 'GET']
    unexpected = [item for item in posts if item['path'] not in (login.LOGIN_PATH, login.LOGOUT_PATH)]
    evidence = {
        'schema': EVIDENCE_SCHEMA,
        'run_id': f'scan-{started.replace("-", "").replace(":", "").replace(".", "")}-{secrets.token_hex(4)}',
        'started_at': started, 'finished_at': login.utc_now(), 'base_url': origin, 'synthetic_only': True,
        'tool': {'python': platform.python_version()}, 'credentials': {'username': username, 'file_mode': f'{mode:04o}'},
        'requests': transport.requests, 'only_get_beyond_sign_in_and_out': not unexpected,
        'encounters': outcome['encounters'], 'checks': outcome['checks'], 'hits': outcome['hits'],
        'run_error': outcome['error'], 'result': result if not unexpected else 'fail',
    }
    login.write_evidence(evidence_path, evidence, secret)
    print(secret.scrub(f'customer scan of {origin} as {username}: {evidence["result"]}'
                       + (f' [{", ".join(failed)}]' if failed else '')
                       + (f' (run stopped: {outcome["error"]})' if outcome['error'] else '')))
    print(f'evidence: {evidence_path}')
    return 0 if evidence['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
