"""The release-2 bench (RELEASE-2-SPEC R2-2, R2-3's requests part, R2-32's records, correctness, nothing-left-behind,
walk, blue/green and plans parts): one round of measurements of ONE tree, run through that tree's own Django.

    cd <tree>/cpt-studio && $PY -B manage.py test <this folder> --pattern bench_run.py --noinput

with the test recipe's environment (test-env.sh, CPT_STUDIO_TEST_DB_SUFFIX, CPT_STUDIO_STATE_DIR, TMPDIR) and:
- BENCH_TAG    the tree's name in the outputs (A, B, A2 ...), BENCH_ROUND its round number;
- BENCH_OUT    an absolute folder outside every tree: the round's output file, raw logs and the lock live there;
- BENCH_PARTS  a comma list from PARTS below;
- BENCH_PORTS  the port range the bench may listen on, "9300-9349" (each port is checked free before use);
- optional: BENCH_PROFILES (P0,P1,P2,P3), BENCH_CONTEXTS (3), BENCH_P3_CORES (two cpus for taskset),
  BENCH_PAUSE_ROUNDS (7), BENCH_OTHER_TREE (blue/green's second tree), BENCH_PLAYWRIGHT.
`python3 bench_run.py --help` drives the protocol (trees in order A B A B A B) instead of running one round.

It refuses, BEFORE the test runner can create a database, unless the database is the throwaway server (host 127.0.0.1,
port 55461 - never 55451, live's), the test database's name starts test_cptstudio_, CODING_MODE is disabled and every
server it starts listens on loopback. Chromium runs with every host but 127.0.0.1 unresolvable, and any blocked request
fails the run. Time limits are inside Python, never an outer `timeout`. One output file per tree, round and parts,
never overwritten; a lock file stops two benches overlapping. Nothing here sends anything to any provider: the walk's
worker codes with a fake coder that answers synthetic messages (bench_worker.py), and the requests part records requests
instead of sending them.

Instruments that lied in the measure area's prototype, and the rule each gave:
- a server answering 500 still gave timings, so every status is asserted (one unexpected status makes a round INVALID);
- CDP counted cached worker scripts, so the server-side log (proxy.cjs, gunicorn's access log) is the truth for counts;
- Runtime.queryObjects(ArrayBuffer.prototype) always answered 0, so heap snapshots are used;
- CDP's CPU throttling does not slow workers, so profile P3 confines Chromium to two cores with taskset.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import http.client
import json
import os
import platform
import re
import secrets
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import benchdata as bd  # noqa: E402  (bytes at import, Django only inside its functions)

PARTS = ('cold', 'pause', 'server', 'queries', 'open', 'lists', 'office', 'load', 'records', 'left-behind', 'correct',
         'walk', 'bluegreen', 'plans', 'requests')
PROFILES = ('P0', 'P1', 'P2', 'P3')
DB_HOST, DB_PORT, LIVE_PORT = '127.0.0.1', '55461', '55451'
TEST_PREFIX = 'test_cptstudio_'
MARKER_WORD = 'zqxbenchmarkerword'  # typed into the search; must appear in no URL, header, log line or record
ACCESS_FORMAT = '%(p)s %(D)s %(m)s %(U)s %(q)s %(s)s %(B)s %({x-request-id}i)s'
PLAYWRIGHT = os.environ.get('BENCH_PLAYWRIGHT', '/opt/meddoc-pro/node_modules/playwright')
SLOW_STATUS_OK = {200, 201, 204, 302, 303, 304}
# judge[8]: the left-behind and correctness flows' own ends answer 401 (the sessions ended), 404 (access ended) and
# 499 (a request the page left); every 5xx stays unexpected, so a 500 there makes the round INVALID
GATE_STATUS_OK = frozenset(SLOW_STATUS_OK | {401, 404, 499})
# bench[2]: the typical server search - every bench title holds this word, so its first page fills at once; a word
# with fewer than 51 matches walks the whole practice, which is the no-match case (R2-20)
TYPICAL_WORD = 'note'


# --- pure helpers: no Django, no database (ops/test_bench.py tests these) ---------------------------------------------

def refusals(db: dict, coding_mode: str, base_urls=()) -> list[str]:
    """Why the bench must not run against these settings; empty when it may. ``db`` is Django's DATABASES['default']
    (its TEST name is what the runner will create); ``base_urls`` are the addresses the bench will serve on."""
    why = []
    if str(db.get('HOST', '')) != DB_HOST:
        why.append(f'the database host is not {DB_HOST}')
    port = str(db.get('PORT', ''))
    if port == LIVE_PORT:
        why.append(f'the database port is {LIVE_PORT}, live\'s')
    elif port != DB_PORT:
        why.append(f'the database port is not {DB_PORT}')
    name = str((db.get('TEST') or {}).get('NAME') or db.get('NAME') or '')
    if not name.startswith(TEST_PREFIX):
        why.append(f'the test database name does not start {TEST_PREFIX}')
    if coding_mode != 'disabled':
        why.append('CODING_MODE is not disabled')
    for url in base_urls:
        if not re.fullmatch(r'http://127\.0\.0\.1:\d{2,5}', str(url)):
            why.append(f'a base URL is not loopback: {url}')
    return why


def parse_ports(text: str) -> range:
    match = re.fullmatch(r'\s*(\d{4,5})\s*-\s*(\d{4,5})\s*', text or '')
    if not match:
        raise ValueError('BENCH_PORTS must be a range such as 9300-9349')
    low, high = int(match.group(1)), int(match.group(2))
    if not 1024 <= low <= high <= 65535 or high - low > 200:
        raise ValueError('BENCH_PORTS must be a range of at most 200 ports above 1023')
    return range(low, high + 1)


class PortPool:
    """Ports from the allowed range, each checked free by binding it on 127.0.0.1, never handed out twice in a run."""

    def __init__(self, ports: range):
        self.ports, self.used = ports, set()

    def take(self) -> int:
        for port in self.ports:
            if port in self.used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                except OSError:
                    continue
            self.used.add(port)
            return port
        raise RuntimeError(f'no free port left in {self.ports.start}-{self.ports.stop - 1}')


def out_name(tag: str, round_no: int, parts, profiles=None) -> str:
    """The round's file name: tag, round, parts, and the profiles when a part group named its own (open@P0)."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,15}', tag or ''):
        raise ValueError('BENCH_TAG must be a short name such as A or B2')
    if profiles is not None and not all(p in PROFILES for p in profiles):
        raise ValueError(f'profiles must be some of {PROFILES}')
    suffix = f'@{"+".join(profiles)}' if profiles else ''
    return f'{tag}-r{int(round_no)}-{"+".join(parts)}{suffix}.json'


def claim_output(out: Path, tag: str, round_no: int, parts, profiles=None) -> Path:
    """The round's output file, which must not exist yet: a round is never overwritten."""
    target = Path(out) / out_name(tag, round_no, parts, profiles)
    if target.exists():
        raise FileExistsError(f'{target.name} exists; a round is never overwritten')
    return target


def lock_free(path: Path) -> bool:
    """Whether no bench holds the lock at ``path`` now (taken and released at once)."""
    handle = take_lock(path)
    if handle is None:
        return False
    handle.close()
    return True


def take_lock(path: Path):
    """An exclusive lock held for the process's life; None when another bench holds it."""
    handle = open(path, 'a+')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(f'{os.getpid()}\n')
    handle.flush()
    return handle


@contextlib.contextmanager
def recorded_round(result: dict, target: Path, close):
    """The round's file is written whatever happens (``close`` first: the load and the password file); a round that
    aborts outside its parts - the seed, collectstatic, a server that never starts - records the abort as an error, so
    its own file is INVALID (records[1]) and the driver runs it again."""
    try:
        yield
    except BaseException as exc:
        result['errors'].append({'part': 'round', 'error': f'{type(exc).__name__}: {exc}'[:2000]})
        raise
    finally:
        close()
        target.write_text(json.dumps(result, indent=1, default=str))


def host_state() -> dict:
    """The host a round ran on (protocol[4]): its boot, uptime, kernel and swap in use, so a session's A can be shown to
    share the recorded A's boot (a reboot separated release 1's rounds more than load did)."""
    out = {'kernel': platform.release()}
    try:
        out['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        out['boot_id'] = None
    try:
        out['uptime_s'] = round(float(Path('/proc/uptime').read_text().split()[0]), 1)
    except (OSError, ValueError, IndexError):
        out['uptime_s'] = None
    try:
        info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
        out['swap_used_mb'] = round((int(info['SwapTotal'].split()[0]) - int(info['SwapFree'].split()[0])) / 1024)
    except (OSError, KeyError, ValueError):
        out['swap_used_mb'] = None
    return out


def median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def percentile(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return round(values[min(len(values) - 1, int(round(q * (len(values) - 1))))], 1)


def smaps(pid: int) -> dict:
    out = {}
    try:
        with open(f'/proc/{pid}/smaps_rollup') as handle:
            for line in handle:
                m = re.match(r'(Rss|Pss|Private_Dirty|Private_Clean):\s+(\d+) kB', line)
                if m:
                    out[m.group(1)] = round(int(m.group(2)) / 1024, 1)
    except OSError:
        pass
    return out


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def bench_digest() -> str:
    """The bench's own sha256: every file of this folder, by name and content."""
    h = hashlib.sha256()
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.cjs', '.json'):
            h.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return h.hexdigest()


def statuses_unexpected(lines, allowed=frozenset(SLOW_STATUS_OK)) -> dict:
    """{status: count} of the access-log or proxy lines whose status is not one the flows expect."""
    bad = {}
    for status in lines:
        if int(status) not in allowed:
            bad[str(status)] = bad.get(str(status), 0) + 1
    return bad


# --- the refusal, before the test runner creates any database ---------------------------------------------------------

def _django_settings():
    try:
        from django.conf import settings
        return settings if settings.configured else None
    except ImportError:
        return None


_SETTINGS = _django_settings()
if _SETTINGS is not None:  # bench[7]: BENCH_PARTS set or not, before the test runner can create any database
    _why = refusals(_SETTINGS.DATABASES['default'], getattr(_SETTINGS, 'CODING_MODE', ''))
    if _why:
        raise RuntimeError('bench refused: ' + '; '.join(_why))


# --- processes --------------------------------------------------------------------------------------------------------

class Env:
    """What every server of this round is started with: the tree, the throwaway database, loopback ports."""

    def __init__(self, tree: Path, raw: Path, db_name: str, ports: PortPool, static: Path, originals: Path):
        self.tree, self.raw, self.db_name, self.ports = tree, raw, db_name, ports
        self.static, self.originals = static, originals

    def environ(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith('BENCH_GC_LOG')}
        env.update({'DJANGO_SETTINGS_MODULE': 'bench_settings', 'PYTHONPATH': f'{self.tree}:{HERE}',
                    'PYTHONDONTWRITEBYTECODE': '1', 'BENCH_DB': self.db_name, 'BENCH_STATIC': str(self.static),
                    'BENCH_ORIGINALS': str(self.originals)})
        env.update({k: str(v) for k, v in extra.items()})
        return env


class Web:
    """The tree's gunicorn, with its own deploy/gunicorn.conf.py and command-line overrides only."""

    def __init__(self, env: Env, label: str, *extra, gc_log: Path | None = None, tree: Path | None = None,
                 static: Path | None = None):
        self.env, self.label = env, label
        self.tree = tree or env.tree
        self.port = env.ports.take()
        self.base = f'http://127.0.0.1:{self.port}'
        if refusals({'HOST': DB_HOST, 'PORT': DB_PORT, 'TEST': {'NAME': env.db_name}}, 'disabled', [self.base]):
            raise RuntimeError('bench refused: a server would not be loopback')
        self.log = env.raw / f'access-{label}.log'
        self.err_path = env.raw / f'gunicorn-{label}.err'
        self.err = open(self.err_path, 'ab')
        extra_env = {'BENCH_GC_LOG': gc_log} if gc_log else {}
        if static is not None:
            extra_env['BENCH_STATIC'] = static
        environ = env.environ(**extra_env)
        environ['PYTHONPATH'] = f'{self.tree}:{HERE}'
        self.proc = subprocess.Popen(
            [sys.executable, '-B', '-m', 'gunicorn', '-c', 'deploy/gunicorn.conf.py',
             '--bind', f'127.0.0.1:{self.port}', '--access-logfile', str(self.log), '--access-logformat', ACCESS_FORMAT,
             '--error-logfile', str(self.err_path), *extra, 'cptstudio.wsgi'],
            cwd=self.tree, env=environ, stdout=self.err, stderr=self.err, start_new_session=True)
        self.wait_ready()

    def wait_ready(self, limit=60.0):
        deadline = time.time() + limit
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f'gunicorn {self.label} exited {self.proc.returncode}; see {self.err_path}')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=1):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError(f'gunicorn {self.label} did not listen within {limit} s')
        # every worker forked and past its own start (a lazily loading tree imports Django in each worker)
        stable, last = 0, -1
        while time.time() < deadline and stable < 8:
            count = len(self.pids())
            stable = stable + 1 if count == last and count > 0 else 0
            last = count
            time.sleep(0.25)
        time.sleep(1.0)

    def pids(self) -> list[int]:
        got = subprocess.run(['pgrep', '-P', str(self.proc.pid)], capture_output=True, text=True).stdout.split()
        return [int(p) for p in got]

    def lines(self) -> list[dict]:
        out = []
        if self.log.exists():
            for line in self.log.read_text().splitlines():
                parts = line.split(' ')
                if len(parts) >= 8:
                    out.append({'pid': int(parts[0].strip('<>')), 'ms': int(parts[1]) / 1000, 'method': parts[2],
                                'path': parts[3], 'query': parts[4], 'status': int(parts[5]),
                                'bytes': int(parts[6]) if parts[6].isdigit() else 0, 'rid': parts[7]})
        return out

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(40)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(10)
        self.err.close()


class Proxy:
    def __init__(self, env: Env, upstream: int, label: str, host_header: str = ''):
        self.port, self.control = env.ports.take(), env.ports.take()
        self.base = f'http://127.0.0.1:{self.port}'
        self.log = env.raw / f'proxy-{label}.jsonl'
        cmd = ['node', str(HERE / 'proxy.cjs'), '--listen', str(self.port), '--upstream', str(upstream), '--control',
               str(self.control), '--log', str(self.log)]
        if host_header:
            cmd += ['--host-header', host_header]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        line = self.proc.stdout.readline().decode()
        if not line.startswith('proxy up'):
            raise RuntimeError('the proxy did not start')

    def call(self, method, path, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.control, timeout=30)
        c.request(method, path, body=json.dumps(body) if body is not None else None,
                  headers={'Content-Type': 'application/json'})
        answer = json.loads(c.getresponse().read())
        c.close()
        return answer

    def entries(self, since=0):
        return self.call('GET', f'/log?since={since}')['entries']

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)


class Member:
    """A signed-in member over plain HTTP, as the page is: cookies, the CSRF header, the tree's own client header (read
    from the tree being measured, never written here), and an X-Request-ID on every request."""

    def __init__(self, base: str, username: str, password: str, client: tuple[str, str]):
        self.base = base
        self.host, self.port = '127.0.0.1', int(base.rsplit(':', 1)[1])
        self.cookies, self.client = {}, client
        page = self.req('GET', '/login/')
        if page['status'] != 200:
            raise RuntimeError(f'GET /login/ answered {page["status"]}')
        token = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page['body']).group(1).decode()
        form = urllib.parse.urlencode({'csrfmiddlewaretoken': token, 'username': username, 'password': password,
                                       'next': '/'})
        r = self.req('POST', '/login/', body=form, headers={'Content-Type': 'application/x-www-form-urlencoded',
                                                             'Referer': f'{base}/login/', 'Origin': base})
        if r['status'] not in (302, 303):
            raise RuntimeError(f'sign-in answered {r["status"]}')

    def req(self, method, path, body=None, headers=None, api=False, rid=None, timeout=120):
        c = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        h = {'Host': f'127.0.0.1:{self.port}', 'Accept-Encoding': 'identity',
             'X-Request-ID': rid or secrets.token_hex(16)}
        if self.cookies:
            h['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if api:
            h[self.client[0]] = self.client[1]
        if method not in ('GET', 'HEAD') and 'cptstudio_csrf' in self.cookies:
            h['X-CSRFToken'] = self.cookies['cptstudio_csrf']
            h.setdefault('Origin', self.base)
        h.update(headers or {})
        t = time.perf_counter()
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        ms = (time.perf_counter() - t) * 1000
        for k, v in r.getheaders():
            if k.lower() == 'set-cookie':
                name, _, value = v.split(';', 1)[0].partition('=')
                self.cookies[name.strip()] = value.strip()
        c.close()
        return {'status': r.status, 'body': data, 'ms': ms, 'headers': dict(r.getheaders()), 'rid': h['X-Request-ID']}


def get(base: str, path: str, timeout=60) -> dict:
    port = int(base.rsplit(':', 1)[1])
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    t = time.perf_counter()
    c.request('GET', path, headers={'Host': f'127.0.0.1:{port}', 'X-Request-ID': secrets.token_hex(16)})
    r = c.getresponse()
    body = r.read()
    out = {'status': r.status, 'ms': (time.perf_counter() - t) * 1000, 'body': body, 'headers': dict(r.getheaders())}
    c.close()
    return out


# --- the act server: bench.cjs asks the test process to change its own throwaway database mid-flow --------------------

class Acts:
    """POST /act {"name": ..., ...} on 127.0.0.1. Each act runs in this thread's own connection to the bench's test
    database, so the web sees it at once. Nothing here can reach another database: the connection is the test
    runner's."""

    TRIGGER = 'bench_refuse_access'

    def __init__(self, port: int, bench):
        self.port, self.bench = port, bench
        handler = self._handler()
        from http.server import ThreadingHTTPServer
        self.server = ThreadingHTTPServer(('127.0.0.1', port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _handler(self):
        from http.server import BaseHTTPRequestHandler
        acts = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                from django.db import connection
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                try:
                    answer = {'ok': True, **(acts.run(body) or {})}
                    code = 200
                except Exception as exc:  # the flow reads the failure; the act changed nothing it did not finish
                    answer, code = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'[:300]}, 500
                finally:
                    connection.close()
                data = json.dumps(answer, default=str).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        return Handler

    def run(self, body):
        from django.db import connection
        from django.utils import timezone
        from studio import models
        name = body.get('name')
        docs = self.bench.docs_by_label
        if name == 'records':  # rows written after the row count `since`, oldest first (ids, never content)
            rows = models.AccessRecord.objects.order_by('created_at', 'id').values(
                'view', 'encounter_ids', 'count', 'filters', 'request_id', 'created_at', 'outcome', 'sign_in_ref')
            since = int(body.get('since') or 0)
            out = list(rows[since:])
            for row in out:
                row['created_at'] = row['created_at'].timestamp() * 1000
            return {'rows': out, 'total': since + len(out)}
        if name == 'count':
            return {'total': models.AccessRecord.objects.count(),
                    'repeats': sum(models.AccessRecordRepeat.objects.values_list('repeats', flat=True))}
        if name == 'reconvert':
            spec = next(s for s in bd.RICH if s['label'] == body['doc'])
            bd.reconvert(models.Encounter.objects.get(pk=docs[body['doc']]['id']), spec)
            return {'number': spec['renumber']}
        if name == 'membership':
            models.Membership.objects.filter(user__username=body['user']).update(active=bool(body['active']))
            return {}
        if name == 'destroy':
            models.Encounter.objects.filter(pk=docs[body['doc']]['id']).update(
                destroyed_at=timezone.now() if body.get('on', True) else None)
            return {}
        if name == 'close':
            models.Workspace.objects.filter(memberships__user__username=body['user']).update(
                closed_at=timezone.now() if body.get('on', True) else None)
            return {}
        if name == 'end_sessions':  # every session of the bench database ends (the flow signs in again after)
            with connection.cursor() as cur:
                cur.execute('DELETE FROM django_session')
            return {}
        if name == 'refuse':  # a trigger refusing the insert of one view's access row; view '' drops it
            with connection.cursor() as cur:
                cur.execute(f'DROP TRIGGER IF EXISTS {self.TRIGGER} ON studio_accessrecord')
                cur.execute(f'DROP TRIGGER IF EXISTS {self.TRIGGER}_repeat ON studio_accessrecordrepeat')
                cur.execute(f'DROP FUNCTION IF EXISTS {self.TRIGGER}()')
                cur.execute(f'DROP FUNCTION IF EXISTS {self.TRIGGER}_repeat()')
                view = body.get('view') or ''
                if view:
                    if not re.fullmatch(r'member\.[a-z_]+', view):
                        raise ValueError('view')
                    cur.execute(f"CREATE FUNCTION {self.TRIGGER}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                                f"IF NEW.view = '{view}' THEN RAISE EXCEPTION 'bench refuses %', NEW.view; END IF; "
                                f"RETURN NEW; END $$")
                    cur.execute(f'CREATE TRIGGER {self.TRIGGER} BEFORE INSERT ON studio_accessrecord '
                                f'FOR EACH ROW EXECUTE FUNCTION {self.TRIGGER}()')
                    if view == 'member.list':  # a list read repeated within 60 s is recorded by its repeat counter
                        cur.execute(f"CREATE FUNCTION {self.TRIGGER}_repeat() RETURNS trigger LANGUAGE plpgsql AS $$ "
                                    f"BEGIN RAISE EXCEPTION 'bench refuses a list repeat'; END $$")
                        cur.execute(f'CREATE TRIGGER {self.TRIGGER}_repeat BEFORE INSERT OR UPDATE ON '
                                    f'studio_accessrecordrepeat FOR EACH ROW EXECUTE FUNCTION {self.TRIGGER}_repeat()')
            return {'view': body.get('view') or ''}
        raise ValueError(f'unknown act {name!r}')

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


# --- the data a round needs -------------------------------------------------------------------------------------------

NEEDS = {
    'cold': {'n100'}, 'pause': {'n100'}, 'server': {'n100', 'n1500', 'n18000'}, 'queries': {'n51', 'n5000', 'n100'},
    'open': {'n100'}, 'lists': {'n100', 'n1500', 'n18000'}, 'office': {'n101', 'n5000'}, 'load': {'n100'},
    'records': {'n100', 'n1500'}, 'left-behind': {'n100', 'n1500'}, 'correct': {'n100', 'n1500'}, 'walk': set(),
    'bluegreen': {'n100'}, 'plans': set(), 'requests': set()}
SIZES, RICH_IN, seed = bd.SIZES, bd.RICH_IN, bd.seed


# --- one round --------------------------------------------------------------------------------------------------------

try:
    from django.test import TransactionTestCase
except ImportError:  # the protocol driver (python3 bench_run.py) needs no Django
    TransactionTestCase = object


class Bench(TransactionTestCase):
    """One round: BENCH_PARTS of the tree this process runs in, written to BENCH_OUT/<tag>-r<round>-<parts>.json."""

    def test_bench(self):
        from django.conf import settings
        from django.db import connection
        from django.test import override_settings
        why = refusals(connection.settings_dict, settings.CODING_MODE)
        if why:
            self.fail('bench refused: ' + '; '.join(why))
        tag, round_no = os.environ.get('BENCH_TAG', ''), int(os.environ.get('BENCH_ROUND', '1'))
        parts = [p for p in os.environ.get('BENCH_PARTS', '').split(',') if p]
        unknown = [p for p in parts if p not in PARTS]
        if not parts or unknown:
            self.fail(f'BENCH_PARTS must name some of {",".join(PARTS)}; unknown: {unknown}')
        out = Path(os.environ.get('BENCH_OUT', ''))
        tree = Path(settings.BASE_DIR).resolve()
        if not out.is_absolute() or tree in out.resolve().parents or out.resolve() == tree:
            self.fail('BENCH_OUT must be an absolute folder outside the tree')
        out.mkdir(parents=True, exist_ok=True)
        self.lock = take_lock(out / 'bench.lock')
        if self.lock is None:
            self.fail('another bench holds the lock')
        self.profiles = [p for p in os.environ.get('BENCH_PROFILES', ','.join(PROFILES)).split(',') if p]
        named = self.profiles if os.environ.get('BENCH_GROUP_PROFILES') == '1' else None
        try:
            target = claim_output(out, tag, round_no, parts, named)
        except (FileExistsError, ValueError) as exc:
            self.fail(str(exc))
        self.raw = out / 'raw' / target.stem
        self.raw.mkdir(parents=True)
        self.raw.chmod(0o700)
        self.ports = PortPool(parse_ports(os.environ.get('BENCH_PORTS', '')))
        self.contexts = int(os.environ.get('BENCH_CONTEXTS', '3'))
        from studio import client_contract
        self.client = (client_contract.HEADER, client_contract.VERSION)  # the measured tree's own, read at run time
        self.password = secrets.token_urlsafe(24)
        self.password_file = self.raw / 'password'
        self.password_file.write_text(self.password)
        self.password_file.chmod(0o600)
        self.tree = tree
        result = {'tag': tag, 'round': round_no, 'parts': parts, 'tree': str(tree), 'at': utc(),
                  'revision': read_revision(tree), 'files': tree_hashes(tree), 'bench_sha256': bench_digest(),
                  'versions': versions(), 'host': host_state(), 'load_before': os.getloadavg(), 'metrics': {},
                  'checks': {}, 'controls': {},
                  'errors': [], 'unexpected_statuses': {}, 'console_errors': [], 'blocked_requests': []}
        self.result = result
        sampling = threading.Event()

        def sample_load():  # the load through the round, every 5 s: a spike between before and after is still seen
            while not sampling.wait(5):
                result.setdefault('load_samples', []).append(round(os.getloadavg()[0], 2))
        sampler = threading.Thread(target=sample_load, daemon=True)
        sampler.start()
        originals = self.raw / 'originals'
        originals.mkdir(mode=0o700)

        def close():
            sampling.set()
            result['load_after'] = os.getloadavg()
            result['load_max'] = max([result['load_before'][0], result['load_after'][0],
                                      *result.get('load_samples', [])])
            result['swap_used_mb_after'] = host_state()['swap_used_mb']
            self.password_file.unlink(missing_ok=True)
        with recorded_round(result, target, close):
            with override_settings(ORIGINALS_DIR=originals):
                need = set().union(*(NEEDS[p] for p in parts))
                started = time.time()
                self.data = seed(need, self.password)
                result['seed_s'] = round(time.time() - started, 1)
                result['rows'] = {name: d['rows'] for name, d in self.data.items()}
                self.docs = self.data.get(RICH_IN, {}).get('docs', [])
                self.docs_by_label = {d['label']: d for d in self.docs}
                static = self.raw / 'static'
                self.env = Env(tree, self.raw, connection.settings_dict['NAME'], self.ports, static, originals)
                subprocess.run([sys.executable, '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=tree,
                               env=self.env.environ(), check=True, stdout=subprocess.DEVNULL, timeout=300)
                result['static'] = static_weights(static)
                self.metric('static.app_js_gz', result['static']['studio/app.js']['gz_bytes'])
                self.metric('static.styles_gz', result['static']['studio/styles.css']['gz_bytes'])
                self.docs_file = self.raw / 'docs.json'
                self.docs_file.write_text(json.dumps(bd.docs_json(self.data, self.client, MARKER_WORD)))
                acts_port = self.ports.take()
                self.acts = Acts(acts_port, self)
                self.acts_port = acts_port
                connection.close()
                try:
                    for part in parts:
                        began = time.time()
                        try:
                            getattr(self, 'part_' + part.replace('-', '_'))()
                        except Exception as exc:  # recorded: a part that failed makes its rows INVALID, never a pass
                            result['errors'].append({'part': part, 'error': f'{type(exc).__name__}: {exc}'[:2000]})
                        result.setdefault('part_s', {})[part] = round(time.time() - began, 1)
                finally:
                    self.acts.stop()
        print(f'\nbench: wrote {target}', flush=True)

    # -- helpers -------------------------------------------------------------------------------------------------------

    def metric(self, name, values):
        values = values if isinstance(values, list) else [values]
        self.result['metrics'].setdefault(name, []).extend(v for v in values if v is not None)

    def check(self, name, ok, **detail):
        self.result['checks'][name] = {'ok': bool(ok), **detail}

    def control(self, name, ok, **detail):
        self.result['controls'][name] = {'ok': bool(ok), **detail}

    def unexpected(self, statuses, where):
        for status, n in statuses_unexpected(statuses).items():
            key = f'{where}:{status}'
            self.result['unexpected_statuses'][key] = self.result['unexpected_statuses'].get(key, 0) + n

    def member(self, base, name='n100'):
        return Member(base, self.data[name]['username'], self.password, self.client)

    def warm(self, web: Web, rounds_per_worker=2, limit=60.0):
        """Every worker has served ``rounds_per_worker`` requests (a lazily loading tree's first request is its
        slowest)."""
        workers = max(1, len(web.pids()))
        deadline = time.time() + limit
        while time.time() < deadline:
            served = {}
            for line in web.lines():
                served[line['pid']] = served.get(line['pid'], 0) + 1
            if len(served) >= workers and min(served.values()) >= rounds_per_worker:
                return
            threads = [threading.Thread(target=get, args=(web.base, '/login/')) for _ in range(workers * 2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

    # -- cold: first requests, recycling, garbage collection, the database ending connections, memory ------------------

    def part_cold(self):
        out = {}
        # (1) the first request of a fresh worker, recycled one at a time, any route: >= 12 lifetimes
        web = Web(self.env, 'cold-recycle', '--max-requests', '6', '--max-requests-jitter', '0')
        try:
            for _ in range(6 * 16):
                r = get(web.base, '/login/')
                self.unexpected([r['status']], 'cold')
                time.sleep(0.05)
            time.sleep(0.5)
        finally:
            web.stop()
        per = {}
        for line in web.lines():
            per.setdefault(line['pid'], []).append(line['ms'])
        firsts = [v[0] for v in per.values() if len(v) >= 2]
        out['first_request_ms'] = firsts
        self.metric('cold.first_request.ms', firsts)
        self.metric('cold.first_request.lifetimes', len(firsts))
        # (2) four first requests at once after a start (the tree's own worker count)
        web = Web(self.env, 'cold-four')
        try:
            got = [None] * 4
            def one(i):
                got[i] = get(web.base, '/login/')
            threads = [threading.Thread(target=one, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.unexpected([g['status'] for g in got], 'cold')
            out['four_at_once_ms'] = [round(g['ms'], 1) for g in got]
            self.metric('cold.four_at_once.ms', out['four_at_once_ms'])
            out['workers'] = len(web.pids())
        finally:
            web.stop()
        # (3) two closed-loop clients, recycling every 200 requests: the slowest of 2,000
        web = Web(self.env, 'cold-loop', '--max-requests', '200', '--max-requests-jitter', '0')
        try:
            lat, errors = [], []
            def loop():
                for _ in range(1000):
                    try:
                        r = get(web.base, '/login/', timeout=30)
                        lat.append(r['ms'])
                        if r['status'] != 200:
                            errors.append(r['status'])
                    except Exception as exc:
                        errors.append(type(exc).__name__)
            threads = [threading.Thread(target=loop) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            out['closed_loop'] = {'n': len(lat), 'slowest_ms': round(max(lat), 1) if lat else None,
                                  'p99_ms': percentile(lat, 0.99), 'errors': len(errors)}
            self.metric('cold.closed_loop.slowest_ms', out['closed_loop']['slowest_ms'])
            self.metric('cold.closed_loop.errors', len(errors))
        finally:
            web.stop()
        # (4) the longest garbage-collection pause in 600 mixed requests per worker, from each worker's start (its first
        # requests included): four clients at once, each 100 times session, detail and list, as the web area measured
        gc_log = self.raw / 'gc.log'
        web = Web(self.env, 'cold-gc', gc_log=gc_log)
        try:
            ready_at = time.time()
            m = self.member(web.base)
            enc = self.docs_by_label['text-4p']['id']
            statuses = []
            def client():
                for _ in range(100):
                    for path in ('/api/session', f'/api/encounters/{enc}', '/api/encounters'):
                        statuses.append(m.req('GET', path, api=True)['status'])
            threads = [threading.Thread(target=client) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.unexpected(statuses, 'cold')
            workers = set(web.pids())
            pauses = [line.split() for line in gc_log.read_text().splitlines() if line.strip()]
            mine = [float(p[2]) for p in pauses if int(p[0]) in workers and float(p[3]) >= ready_at]
            full = [float(p[2]) for p in pauses if int(p[0]) in workers and float(p[3]) >= ready_at and p[1] == '2']
            per_worker = len(statuses) / max(1, len(workers))
            out['gc'] = {'requests': len(statuses), 'per_worker': round(per_worker), 'collections_over_1ms': len(mine),
                         'full_collections': len(full), 'max_pause_ms': round(max(mine), 1) if mine else 0.0}
            self.metric('cold.gc.max_pause_ms', out['gc']['max_pause_ms'])
            # (5) memory per worker and of every process after the standard flow (the n100 practice's reads)
            mem = {pid: smaps(pid) for pid in [web.proc.pid, *web.pids()]}
            workers = [mem[p] for p in web.pids()]
            out['memory_after_standard_flow'] = {'master': mem[web.proc.pid], 'workers': workers}
            self.metric('cold.memory.worker_pss', [w.get('Pss') for w in workers])
            self.metric('cold.memory.worker_rss', [w.get('Rss') for w in workers])
            self.metric('cold.memory.total_pss', round(sum(v.get('Pss', 0) for v in mem.values()), 1))
        finally:
            web.stop()
        # (6) the database ends every web connection: every worker holds one (concurrent signed-in reads until each
        # worker's pid served one), pg_terminate_backend ends them all, then the next reads reach every worker
        web = Web(self.env, 'cold-dbend')
        try:
            self.warm(web)
            m = self.member(web.base)
            workers = set(web.pids())
            def burst(n):
                got = []
                threads = [threading.Thread(target=lambda: got.append(m.req('GET', '/api/session', api=True)['status']))
                           for _ in range(n)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                return got
            for _ in range(10):
                burst(len(workers) * 2)
                served = {line['pid'] for line in web.lines() if line['path'] == '/api/session'}
                if workers <= served:
                    break
            ended = terminate_web_backends(self.env.db_name)
            answers = []
            for _ in range(3):
                answers += burst(len(workers) * 2)
            out['db_end'] = {'workers': len(workers), 'backends_ended': ended, 'answers': answers}
            self.metric('cold.db_end.errors', sum(1 for s in answers if s >= 500))
        finally:
            web.stop()
        self.result['cold'] = out

    # -- pause: a detail 62 s after the last request, each round its own session ---------------------------------------

    def part_pause(self):
        rounds = int(os.environ.get('BENCH_PAUSE_ROUNDS', '7'))
        web = Web(self.env, 'pause')
        try:
            self.warm(web)
            enc = self.docs_by_label['text-4p']['id']
            samples = []
            for _ in range(rounds):
                m = self.member(web.base)
                for path in ('/api/session', f'/api/encounters/{enc}'):
                    m.req('GET', path, api=True)
                time.sleep(62)
                got = {}
                def one(name, path, api):  # an open's three requests at once, as release 1's page sends them
                    got[name] = m.req('GET', path, api=api)
                threads = [threading.Thread(target=one, args=a) for a in (
                    ('session', '/api/session', True), ('detail', f'/api/encounters/{enc}', True),
                    ('view', f'/api/encounters/{enc}/original?view=1', False))]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                self.unexpected([g['status'] for g in got.values()], 'pause')
                samples.append(round(got['detail']['ms'], 1))
            self.metric('pause.detail.ms', samples)
            self.result['pause'] = {'detail_ms': samples}
        finally:
            web.stop()

    # -- server: warm server times and bodies, one worker --------------------------------------------------------------

    def part_server(self):
        out = {}
        web = Web(self.env, 'server', '--workers', '1')
        try:
            self.warm(web)
            for name in ('n100', 'n1500', 'n18000'):
                m = self.member(web.base, name)
                if name == 'n18000':
                    before_big = smaps(web.pids()[0])
                for _ in range(2):
                    m.req('GET', '/api/encounters', api=True)
                reps = {'n100': 15, 'n1500': 9, 'n18000': 5}[name]
                lists = [m.req('GET', '/api/encounters', api=True) for _ in range(reps)]
                self.unexpected([r['status'] for r in lists], 'server')
                session = [m.req('GET', '/api/session', api=True) for _ in range(9)]
                self.unexpected([r['status'] for r in session], 'server')
                rows = json.loads(lists[-1]['body'])
                size = SIZES[name]
                out[name] = {'rows_first_answer': len(rows.get('encounters', [])), 'next': rows.get('next'),
                             'total': rows.get('total'), 'list_ms': median([r['ms'] for r in lists]),
                             'bytes': len(lists[-1]['body']), 'session_ms': median([r['ms'] for r in session])}
                self.metric(f'server.list.ms.{size}', [round(r['ms'], 1) for r in lists])
                self.metric(f'server.list.bytes.{size}', len(lists[-1]['body']))
                self.metric(f'server.session.ms.{size}', [round(r['ms'], 1) for r in session])
                if name == 'n18000':  # the server search (release 2), answered 404 or 405 by a tree without it
                    probe = m.req('POST', '/api/encounters/search',
                                  body=json.dumps({'text': TYPICAL_WORD, 'before': None}),
                                  headers={'Content-Type': 'application/json'}, api=True)
                    out['search_status'] = probe['status']
                    if probe['status'] == 200:
                        typical = [m.req('POST', '/api/encounters/search', body=json.dumps({'text': TYPICAL_WORD,
                                   'before': None}), headers={'Content-Type': 'application/json'}, api=True)
                                   for _ in range(9)]
                        none = [m.req('POST', '/api/encounters/search', body=json.dumps({'text': MARKER_WORD,
                                'before': None}), headers={'Content-Type': 'application/json'}, api=True)
                                for _ in range(5)]
                        self.unexpected([r['status'] for r in typical + none], 'server')
                        self.metric('server.search.ms.18000', [round(r['ms'], 1) for r in typical])
                        self.metric('server.search_nomatch.ms.18000', [round(r['ms'], 1) for r in none])
            after_big = smaps(web.pids()[0])
            out['worker_around_18000'] = {'before': before_big, 'after': after_big}
            retained = round(after_big.get('Pss', 0) - before_big.get('Pss', 0), 1)
            self.metric('server.worker.retained_after_18000', retained)
            m = self.member(web.base)
            details, views = [], {}
            for d in self.docs:
                m.req('GET', f'/api/encounters/{d["id"]}', api=True)
                det = [m.req('GET', f'/api/encounters/{d["id"]}', api=True) for _ in range(4)]
                self.unexpected([r['status'] for r in det], 'server')
                details += [r['ms'] for r in det]
                if d['label'].startswith('control-held'):
                    continue
                v = [m.req('GET', f'/api/encounters/{d["id"]}/original?view=1') for _ in range(4)]
                self.unexpected([r['status'] for r in v], 'server')
                views[d['label']] = {'bytes': len(v[-1]['body']), 'ms': median([r['ms'] for r in v]),
                                     'cache_control': v[-1]['headers'].get('Cache-Control'),
                                     'etag': v[-1]['headers'].get('ETag')}
            out['detail_ms'] = median(details)
            out['view'] = views
            self.metric('server.detail.ms', [round(x, 1) for x in details])
            index = [m.req('GET', '/') for _ in range(9)]
            self.unexpected([r['status'] for r in index], 'server')
            out['index_ms'] = median([r['ms'] for r in index])
            self.metric('server.index.ms', [round(r['ms'], 1) for r in index])
            out['health'] = health_release(web.base)
            out['asset_names'] = sorted(set(re.findall(rb'/static/[A-Za-z0-9_./-]+', index[-1]['body'])))
            out['asset_names'] = [a.decode() for a in out['asset_names']]
            mem = smaps(web.pids()[0]) if web.pids() else {}
            out['worker_after'] = mem
        finally:
            web.stop()
        self.result['server'] = out

    # -- queries: statements per request, in this process, with the tree's own views -----------------------------------

    def part_queries(self):
        from django.db import connection
        from django.test import Client
        from django.test.utils import CaptureQueriesContext, override_settings
        from studio import request_meta
        from tests.support import operator as ops
        out = {}
        with override_settings(STATIC_ROOT=self.raw / 'static'):
            def client_for(name):
                c = Client(HTTP_HOST='cpt.quillmd.com', HTTP_X_REQUEST_ID='0' * 32)
                c.force_login(self.data[name]['user'])
                ops.mark_signed_in(c, door=request_meta.CPT)
                return c

            def count(c, method, path, **extra):
                with CaptureQueriesContext(connection) as q:
                    if method == 'GET':
                        r = c.get(path, **extra)
                    else:
                        r = c.post(path, data=extra.pop('data'), content_type='application/json', **extra)
                return r, [x['sql'] for x in q.captured_queries]

            api = {f'HTTP_{self.client[0].upper().replace("-", "_")}': self.client[1]}
            for name in ('n51', 'n5000'):  # one page and more (R2-19: 50 a page), so a later page and a COUNT
                c = client_for(name)
                size = SIZES[name]
                r, first = count(c, 'GET', '/api/encounters', **api)
                answer = r.json() if r.status_code == 200 else {}
                self.unexpected([r.status_code], 'queries')
                out[f'list_first.{size}'] = classify(first)
                r, repeat = count(c, 'GET', '/api/encounters', **api)
                out[f'list_repeat.{size}'] = classify(repeat)
                if answer.get('next'):
                    r, later = count(c, 'GET', f'/api/encounters?list=documents&before={answer["next"]}', **api)
                    self.unexpected([r.status_code], 'queries')
                    out[f'list_later.{size}'] = classify(later)
                r, search = count(c, 'POST', '/api/encounters/search',
                                  data=json.dumps({'text': 'note', 'before': None}), **api)
                if r.status_code == 200:
                    out[f'search.{size}'] = classify(search)
                out[f'search_status.{size}'] = r.status_code
            c = client_for('n100')
            enc = self.docs_by_label['text-4p']['id']
            for label, method, path, extra in (
                    ('shell', 'GET', '/', {}), ('session', 'GET', '/api/session', api),
                    ('detail', 'GET', f'/api/encounters/{enc}', api),
                    ('detail_again', 'GET', f'/api/encounters/{enc}', api),
                    ('poll', 'GET', f'/api/encounters/{enc}', {**api, 'HTTP_X_CPT_POLL': '1'}),
                    ('view', 'GET', f'/api/encounters/{enc}/original?view=1', {'HTTP_X_CPT_POLL': '1'})):
                r, sql = count(c, method, path, **extra)
                self.unexpected([r.status_code], 'queries')
                out[label] = classify(sql)
                if label == 'view' and r.get('ETag'):
                    r2, sql2 = count(c, 'GET', path, HTTP_IF_NONE_MATCH=r['ETag'], HTTP_X_CPT_POLL='1')
                    out['view_held'] = {**classify(sql2), 'status': r2.status_code}
        for key, value in out.items():
            if isinstance(value, dict) and 'total' in value:
                self.metric(f'queries.{key}', value['total'])
                self.metric(f'queries.{key}.builder', value['builder'])
        self.result['queries'] = out

    # -- load: throughput, and a session read behind two sign-ins and one report PDF -----------------------------------

    def part_load(self):
        from concurrent.futures import ThreadPoolExecutor
        out = {}
        web = Web(self.env, 'load')
        try:
            self.warm(web)
            m = self.member(web.base)
            paths = [f'/api/encounters/{self.docs_by_label[x]["id"]}'
                     for x in ('text-2p', 'text-4p', 'text-10p', 'word-3p')]
            serial = [m.req('GET', paths[i % 4], api=True) for i in range(24)]
            self.unexpected([r['status'] for r in serial], 'load')
            out['serial_detail_ms'] = median([r['ms'] for r in serial])
            for k in (10, 20):
                n = 40 * max(1, k // 5)
                started = time.perf_counter()
                with ThreadPoolExecutor(k) as pool:
                    got = list(pool.map(lambda i: m.req('GET', paths[i % 4], api=True), range(n)))
                wall = time.perf_counter() - started
                self.unexpected([r['status'] for r in got], 'load')
                lat = [r['ms'] for r in got]
                out[f'detail_{k}'] = {'req_per_s': round(n / wall, 1), 'p50': percentile(lat, 0.5),
                                      'p95': percentile(lat, 0.95)}
                self.metric(f'load.detail{k}.rps', out[f'detail_{k}']['req_per_s'])
                self.metric(f'load.detail{k}.p95', out[f'detail_{k}']['p95'])
            alone = [m.req('GET', '/api/session', api=True)['ms'] for _ in range(9)]
            out['session_alone_ms'] = median(alone)
            behind = []
            reports = [d for d in self.docs if d['kind'] != 'text']
            for d in reports:
                statuses = []
                def sign_in():
                    try:
                        self.member(web.base)
                        statuses.append(302)
                    except Exception as exc:
                        statuses.append(str(exc)[:60])
                def report():
                    r = m.req('POST', f'/api/encounters/{d["id"]}/reports', api=True,
                              body=json.dumps({'kind': 'draft', 'fmt': 'pdf', 'round': 1}),
                              headers={'Content-Type': 'application/json'})
                    statuses.append(r['status'])
                busy = [threading.Thread(target=sign_in), threading.Thread(target=sign_in),
                        threading.Thread(target=report)]
                for t in busy:
                    t.start()
                time.sleep(0.03)
                probe = m.req('GET', '/api/session', api=True)
                for t in busy:
                    t.join()
                behind.append(round(probe['ms'], 1))
                self.unexpected([probe['status']] + [s for s in statuses if isinstance(s, int)], 'load')
                if any(not isinstance(s, int) for s in statuses):
                    self.result['errors'].append({'part': 'load', 'error': f'busy request failed: {statuses}'})
            out['session_behind_ms'] = behind
            self.metric('load.session_behind.ms', behind)
            self.metric('load.session_behind.p95', percentile(behind, 0.95))
            out['workers'] = len(web.pids())
        finally:
            web.stop()
        self.result['load'] = out

    # -- requests (R2-3): what the coder is sent, as hashes, for fixed synthetic documents -----------------------------

    def part_requests(self):
        from unittest import mock
        from django.conf import settings
        from studio import jobs, models
        from studio.fable import client as fable_client
        from tests.support import coding as f, rounds as r
        rows = []
        ws = f.workspace('Bench requests')
        user = f.member(ws)
        cases = [('pdf-text', dict(data=bd.text_pdf(2, 101, 1), filename='a.pdf', media_type='application/pdf')),
                 ('pdf-scan', dict(data=bd.scan_pdf(1, 104, 4, dpi=60), filename='s.pdf',
                                   media_type='application/pdf')),
                 ('text', dict(data=b'SYNTHETIC NOTE polyp removed by cold snare.', filename='n.txt',
                               media_type='text/plain')),
                 ('paste', None)]
        for label, upload in cases:
            enc = f.encounter(ws, user, service_date='2026-11-02', insurance='medicare', title=f'Case {label}')
            rev = f.upload(enc, user, **upload) if upload else f.paste(enc, user)
            jobs.start_round(enc, rev, models.CodingRound.UPLOAD, user)
            fake = f.FakeCoder(reader=f.succeeded(r.reader_message(r.READER)),
                               checker=f.succeeded(r.checker_message(r.CHECKER)))
            with mock.patch.object(fable_client, 'coder', return_value=fake):
                jobs.run_job(jobs.claim_next())
            for role, request in fake.calls:  # bench[3]: every byte the coder is sent but its effort, and the effort
                rows.append(request_row(label, role, request.params, request.attempts, fable_client.canonical))
        self.result['requests'] = rows
        self.result['requests_effort'] = settings.CODING_EFFORT  # the tree's own setting (R2-33: 'high' in B)
        self.check('requests.recorded', len(rows) >= 8, rows=len(rows))

    # -- the browser parts ---------------------------------------------------------------------------------------------

    def browser(self, flow, profile, *, size='n100', label=None, allowed=frozenset(SLOW_STATUS_OK), limit=1800,
                web_args=(), extra=(), timing=True):
        """One bench.cjs flow against a fresh web and proxy of this tree; its metrics, checks and controls are merged
        into the round. Every answer's status is checked against ``allowed`` at the server side."""
        label = label or f'{flow}-{size}-{profile}'
        web = Web(self.env, label, *web_args)
        proxy = Proxy(self.env, web.port, label)
        out = self.raw / f'browser-{label}.json'
        try:
            self.warm(web)
            cmd = ['node', str(HERE / 'bench.cjs'), '--flow', flow, '--profile', profile, '--base', proxy.base,
                   '--control', str(proxy.control), '--act', str(self.acts_port), '--docs', str(self.docs_file),
                   '--password-file', str(self.password_file), '--out', str(out), '--playwright', PLAYWRIGHT,
                   '--contexts', str(self.contexts), '--size', size, *extra]
            if profile == 'P3':
                cores = os.environ.get('BENCH_P3_CORES') or idlest_cores(2)
                self.result.setdefault('p3_cores', []).append(cores)
                cmd = ['taskset', '-c', cores, *cmd]
            env = {**os.environ, 'TMPDIR': os.environ.get('TMPDIR', str(self.raw))}
            started = time.time()
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=limit, env=env)
            (self.raw / f'browser-{label}.log').write_text(
                done.stdout[-20000:] + '\n--- stderr\n' + done.stderr[-20000:])
            data = json.loads(out.read_text()) if out.exists() else {'errors': ['no output'], 'metrics': {}}
            data['_rc'], data['_s'] = done.returncode, round(time.time() - started, 1)
            if done.returncode:
                self.result['errors'].append({'part': flow, 'error': f'bench.cjs {label} exit {done.returncode}: '
                                                                     f'{done.stderr[-600:]}'})
            entries = proxy.entries()
            data['_proxy_entries'] = len(entries)
            self.unexpected([e['status'] for e in entries if (e['method'], e['url'], e['status']) not in EXPECTED_EXTRA
                             and e['status'] not in allowed], label)
            for name, values in data.get('metrics', {}).items():
                self.metric(name, values)
            self.result['checks'].update({f'{k}': v for k, v in data.get('checks', {}).items()})
            self.result['controls'].update(data.get('controls', {}))
            errors = data.get('consoleErrors', []) + data.get('pageErrors', [])
            if timing:
                self.result['console_errors'] += errors
            else:  # kept, by flow: the gate flows plant faults whose console errors are expected
                self.result.setdefault('gate_console_errors', {})[label] = errors[:50]
            self.result['blocked_requests'] += data.get('blocked', [])
            for message in data.get('errors', []):
                self.result['errors'].append({'part': flow, 'error': f'{label}: {message}'})
            if data.get('unfinished'):
                self.result.setdefault('unfinished', []).extend(f'{label}: {u}' for u in data['unfinished'])
            self.result.setdefault('browsers', []).append({'label': label, 'chromium': data.get('chromium'),
                                                          's': data['_s'], 'rc': done.returncode})
            return data, entries, web.lines()
        finally:
            proxy.stop()
            web.stop()

    def part_open(self):
        for profile in self.profiles:
            data, entries, lines = self.browser('open', profile)
            if profile == 'P0':
                acts = data.get('actions', [])
                door = {}
                for kind in ('later', 'back', 'signin'):
                    found = [a for a in acts if a.get('kind') == kind]
                    if found:
                        req = found[0].get('requests') if kind != 'signin' else found[0].get('list')
                        door[kind] = [r[:2] if isinstance(r, list) else r.split(' ')[:2] for r in (req or [])]
                self.result['front_door'] = door
            self.headers_audit(entries, f'open-{profile}')
            barcodes = [(a['label'], a['number'], (a.get('barcode') or {}).get('number'))
                        for a in data.get('actions', [])
                        if a.get('firstPage') is not None and a.get('label') in self.docs_by_label]
            self.result.setdefault('barcodes', []).extend(barcodes)
        bad = [b for b in self.result.get('barcodes', []) if b[1] != b[2]]
        self.check('correct.barcode_every_open', not bad and bool(self.result.get('barcodes')), mismatches=bad[:20],
                   opens=len(self.result.get('barcodes', [])))

    def part_lists(self):
        for size in ('n100', 'n1500', 'n18000'):
            for profile in [p for p in self.profiles if p in ('P0', 'P1')]:
                self.browser('lists', profile, size=size, limit=2400)
        if 'P2' in self.profiles:
            self.browser('lists', 'P2', size='n100')

    def part_office(self):
        office = {}
        for size in ('n101', 'n5000'):
            data, entries, lines = self.browser('office', 'P0', size=size)
            office[SIZES[size]] = data.get('office')
        office['vhost_zones'] = vhost_zones(self.tree)
        self.result['office'] = office

    # -- records (M4): every read served is recorded, once, before its pixels; fail closed; no marker anywhere ---------

    def part_records(self):
        from studio import models
        judged, pages = {}, {}
        for size in ('n100', 'n1500'):
            since = models.AccessRecord.objects.count()
            repeats_before = dict(models.AccessRecordRepeat.objects.values_list('record_id', 'repeats'))
            data, entries, lines = self.browser('records', 'P0', size=size, label=f'records-{size}', timing=False)
            rows = list(models.AccessRecord.objects.order_by('created_at', 'id').values(
                'view', 'encounter_ids', 'count', 'filters', 'request_id', 'created_at', 'outcome',
                'sign_in_ref')[since:])
            for row in rows:
                row['created_at'] = row['created_at'].timestamp() * 1000
                row['sign_in_ref'] = str(row['sign_in_ref'])
            repeats_after = dict(models.AccessRecordRepeat.objects.values_list('record_id', 'repeats'))
            added = sum(n - repeats_before.get(k, 0) for k, n in repeats_after.items())
            judged[size] = judge_records(entries, rows, added, data.get('actions', []), data.get('lists', []),
                                         docs=self.docs_by_label)
            # records[2]: each flow's own hover result, ANDed below as the other checks are (browser() kept the last)
            judged[size]['hover'] = data.get('checks', {}).get('records.hover') or {'ok': False, 'missing': True}
            pages[size] = data.get('markerPage')  # records[4]: what the page itself held after the marker was typed
            if size == 'n100':
                records_n100_rule(judged[size])
        for check in ('records.equation', 'records.polls', 'records.openings', 'records.list_ids',
                      'records.inline_before_pixels', 'records.hover'):  # named whole, as acceptance.json names them
            parts = {size: judged[size][check.split('.', 1)[1]] for size in judged}
            self.check(check, all(p['ok'] for p in parts.values()), sizes=parts)
        self.browser('fail-closed', 'P0', label='fail-closed', allowed=frozenset(SLOW_STATUS_OK | {503}), timing=False)
        ok, detail = marker_audit(self.raw, MARKER_WORD, pages)
        self.check('records.marker', ok, **detail)
        self.result['records'] = judged

    def part_left_behind(self):
        data, entries, lines = self.browser('left-behind', 'P0', label='left-behind', allowed=GATE_STATUS_OK,
                                            timing=False)
        self.headers_audit(entries, 'left-behind')

    def part_correct(self):
        self.browser('correct', 'P0', label='correct', allowed=GATE_STATUS_OK, timing=False)

    # -- walk (M9): the tree's own walk over its web, its worker (a fake coder) and the admin host ---------------------

    def part_walk(self):
        from studio import models
        ws, user = bd.practice('walk', 3, self.password, seed=3)
        models.User.objects.filter(pk=user.pk).update(actor_kind='agent')
        docs = self.raw / 'walk-docs'
        docs.mkdir(mode=0o700)
        head = ('Date of service: 2026-11-02.', 'The colonoscopy to the cecum was complete.')
        (docs / 'a-note-2p.pdf').write_bytes(bd.text_pdf(2, 201, 11, head=head))
        (docs / 'b-note.txt').write_text('SYNTHETIC NOTE - NOT A REAL PATIENT\nDate of service: 2026-11-02\n'
                                         'The colonoscopy to the cecum was complete.\n'
                                         'The polyp was removed by cold snare and retrieved.\n')
        (docs / 'c-scan-2p.pdf').write_bytes(bd.walk_scan())
        (docs / 'd-quotes-3p.pdf').write_bytes(bd.text_pdf(3, 204, 14, head=head, span=True))
        creds = self.raw / 'walk-credentials.json'
        creds.write_text(json.dumps({'username': user.username, 'password': self.password}))
        creds.chmod(0o600)
        web = Web(self.env, 'walk')
        admin = Proxy(self.env, web.port, 'walk-admin', host_header='admin.quillmd.com')
        log = open(self.raw / 'walk-worker.log', 'wb')
        worker = subprocess.Popen([sys.executable, '-B', str(HERE / 'bench_worker.py')], cwd=self.tree,
                                  env=self.env.environ(), stdout=log, stderr=log, start_new_session=True)
        out = self.raw / 'walk-out'
        try:
            time.sleep(3)
            started = time.time()
            done = subprocess.run(['node', str(self.tree / 'ops' / 'walk.cjs'), '--base-url', web.base, '--admin-url',
                                   admin.base, '--credentials', str(creds), '--docs', str(docs), '--out', str(out),
                                   '--allow-live-provider', '--service-date', '2026-11-02', '--insurance', 'medicare',
                                   '--deadline-seconds', '300', '--workspace', ws.name],
                                  capture_output=True, text=True, timeout=1800,
                                  env={**os.environ, 'CPT_VERIFY_PLAYWRIGHT': PLAYWRIGHT})
            (self.raw / 'walk.log').write_text(done.stdout[-30000:] + '\n--- stderr\n' + done.stderr[-30000:])
            evidence = json.loads((out / 'evidence.json').read_text()) if (out / 'evidence.json').exists() else {}
            run_checks = evidence.get('run_checks', [])
            # a check is passed or skipped by design (scan.files: the walk leaves report wording to scan_customer.py)
            documents = [{'file': d.get('file') or d.get('name'), 'result': d.get('result'),
                          'checks': len(d.get('checks', [])),
                          'skipped': [c.get('id') for c in d.get('checks', []) if c.get('status') == 'skip'],
                          'failed': [c.get('id') for c in d.get('checks', [])
                                     if c.get('status') not in ('pass', 'skip')]}
                         for d in evidence.get('documents', [])]
            failed = [c.get('id') for c in run_checks if c.get('status') not in ('pass', 'skip')]
            self.check('walk.passes', done.returncode == 0 and not failed and len(documents) == 4
                       and all(not d['failed'] for d in documents), exit=done.returncode, run_failed=failed,
                       documents=documents, seconds=round(time.time() - started, 1))
        finally:
            worker.send_signal(signal.SIGTERM)
            try:
                worker.wait(30)
            except subprocess.TimeoutExpired:
                os.killpg(worker.pid, signal.SIGKILL)
            log.close()
            admin.stop()
            web.stop()
            creds.unlink(missing_ok=True)

    # -- blue/green (M12): one open page's upstream flipped between the two releases; release 1's web on this schema ---

    def part_bluegreen(self):
        other = Path(os.environ.get('BENCH_OTHER_TREE', '')).resolve() / 'cpt-studio'
        if not (other / 'manage.py').exists():
            raise RuntimeError('BENCH_OTHER_TREE must name the other release\'s tree (the folder holding cpt-studio/)')
        other_static = self.raw / 'static-other'
        subprocess.run([sys.executable, '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=other,
                       env={**self.env.environ(BENCH_STATIC=other_static), 'PYTHONPATH': f'{other}:{HERE}'},
                       check=True, stdout=subprocess.DEVNULL, timeout=300)
        mine = Web(self.env, 'bluegreen-mine')
        theirs = Web(self.env, 'bluegreen-other', tree=other, static=other_static)
        proxy = Proxy(self.env, theirs.port, 'bluegreen')
        out = self.raw / 'browser-bluegreen.json'
        try:
            self.warm(mine)
            self.warm(theirs)
            cmd = ['node', str(HERE / 'bench.cjs'), '--flow', 'bluegreen', '--profile', 'P0', '--base', proxy.base,
                   '--control', str(proxy.control), '--act', str(self.acts_port), '--docs', str(self.docs_file),
                   '--password-file', str(self.password_file), '--out', str(out), '--playwright', PLAYWRIGHT,
                   '--size', 'n100', '--web-mine', str(mine.port), '--web-other', str(theirs.port)]
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            (self.raw / 'browser-bluegreen.log').write_text(
                done.stdout[-20000:] + '\n--- stderr\n' + done.stderr[-20000:])
            data = json.loads(out.read_text()) if out.exists() else {'errors': ['no output']}
            self.result['checks'].update(data.get('checks', {}))
            for message in data.get('errors', []):
                self.result['errors'].append({'part': 'bluegreen', 'error': message})
            ok, detail = self.x3(theirs, other)
            self.check('bluegreen.x3', ok, **detail)
        finally:
            proxy.stop()
            theirs.stop()
            mine.stop()

    def x3(self, theirs: Web, other: Path):
        """The other tree's web on THIS tree's schema: sign-in, list, detail, view, upload, decision, report, sign-out
        and the operator pages answer as that tree's own (the statuses its own pages expect), and its list query's plan
        is recorded. Meaningful when this tree carries migrations the other does not (release 2's 0019-0021)."""
        mine_migrations = {p.name for p in (self.tree / 'studio' / 'migrations').glob('0*.py')}
        theirs_migrations = {p.name for p in (other / 'studio' / 'migrations').glob('0*.py')}
        extra = sorted(mine_migrations - theirs_migrations)
        m = Member(theirs.base, self.data['n100']['username'], self.password, read_client(other))
        doc = self.docs_by_label['text-4p']['id']
        got = {'shell': m.req('GET', '/')['status'], 'session': m.req('GET', '/api/session', api=True)['status'],
               'list': m.req('GET', '/api/encounters', api=True)['status'],
               'detail': m.req('GET', f'/api/encounters/{doc}', api=True)['status'],
               'view': m.req('GET', f'/api/encounters/{doc}/original?view=1')['status']}
        boundary = 'benchboundary'
        fields = {'title': 'X3 upload', 'service_date': '2026-11-02', 'insurance': 'medicare',
                  'synthetic_attestation': 'yes', 'client_key': str(uuid.uuid4())}
        upload = ''.join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                         for k, v in fields.items())
        upload += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="x3.txt"\r\n'
                   f'Content-Type: text/plain\r\n\r\nSYNTHETIC NOTE - NOT A REAL PATIENT\r\n--{boundary}--\r\n')
        got['upload'] = m.req('POST', '/api/encounters', body=upload.encode(), api=True,
                              headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})['status']
        session = json.loads(m.req('GET', '/api/session', api=True)['body'] or b'{}')
        detail = json.loads(m.req('GET', f'/api/encounters/{doc}', api=True)['body'] or b'{}')
        ready = [c for c in (detail.get('codes') or []) if c.get('status') == 'ready' and not c.get('decision')]
        got['decision'] = m.req('POST', f'/api/encounters/{doc}/decisions', api=True, headers={
            'Content-Type': 'application/json'}, body=json.dumps({
                'round': (detail.get('round') or {}).get('number'), 'line': ready[0]['line'] if ready else None,
                'code': ready[0]['code'] if ready else None, 'action': 'approve',
                'acknowledgement': session.get('acknowledgement')}))['status']
        got['report'] = m.req('POST', f'/api/encounters/{doc}/reports', api=True, headers={
            'Content-Type': 'application/json'}, body=json.dumps({'kind': 'draft', 'fmt': 'pdf', 'round': 1}))['status']
        got['operator_page'] = get_with_host(theirs.base, '/ops/', 'admin.quillmd.com')['status']
        got['signout'] = m.req('POST', '/logout/')['status']
        expected = {'shell': {200}, 'session': {200}, 'list': {200}, 'detail': {200}, 'view': {200}, 'upload': {201},
                    'decision': {201}, 'report': {200, 201}, 'operator_page': {302}, 'signout': {302, 303}}
        wrong = {k: v for k, v in got.items() if v not in expected.get(k, {v})}
        return not wrong and not any(v >= 500 for v in got.values()), {'statuses': got, 'wrong': wrong,
                                                                      'migrations_beyond_the_other': extra}

    # -- plans (M14): the changed reads at 18,000 documents, 36,000 runs and 200,000 access records --------------------

    def part_plans(self):
        out = {'release_2_indexes': release2_index_names(self.tree)}
        live = plans_seed(self.password, documents=101, runs_per=3, records=2000, name='plans-live')
        out['index_build_live_ms'] = rebuild_indexes(out['release_2_indexes'])
        big = plans_seed(self.password, documents=18000, runs_per=2, records=200000, name='plans-big')
        out['index_build_big_ms'] = rebuild_indexes(out['release_2_indexes'])
        out['insert_wait'] = insert_during_build(out['release_2_indexes'], big)
        out['reads'] = explain_changed_reads(self, big)
        seq = [r for r in out['reads'] if r['seq_scans']]
        slow = [r for r in out['reads'] if r['ms'] > 20]
        self.check('plans.no_seq_scan', bool(out['reads']) and not seq,
                   scans=[(r['read'], r['seq_scans']) for r in seq])
        self.check('plans.reads_20ms', bool(out['reads']) and not slow, slow=[(r['read'], r['ms']) for r in slow])
        builds = out['index_build_big_ms'] | {f'live:{k}': v for k, v in out['index_build_live_ms'].items()}
        self.check('plans.index_build', bool(out['release_2_indexes'])
                   and all(v <= 2000 for v in out['index_build_big_ms'].values())
                   and all(v <= 100 for v in out['index_build_live_ms'].values()), builds=builds)
        self.check('plans.insert_wait', bool(out['insert_wait'])
                   and all(w['insert_ms'] <= w['build_ms'] + 100 for w in out['insert_wait']), waits=out['insert_wait'])
        out['live'] = live['counts']
        out['big'] = big['counts']
        self.result['plans'] = out

    def headers_audit(self, entries, where):
        """Every non-static 200 or 304 is no-store; no answer header holds a stored file's sha256 or its first 16 hex;
        an /api/ ETag is absent or a quoted UUID (spec 2.2, R2-24, R2-32)."""
        digests = set()
        for spec in bd.RICH:
            files = bd.rich_files(spec)
            for part in (files['data'], files['view']):
                if part:
                    full = hashlib.sha256(part).hexdigest()
                    digests |= {full, full[:16]}
        not_no_store, hashed, bad_etag = [], [], []
        for e in entries:
            path = e['url'].split('?', 1)[0]
            headers = {k.lower(): (v if isinstance(v, str) else ','.join(v))
                       for k, v in e.get('resHeaders', {}).items()}
            if e['status'] in (200, 304) and not path.startswith('/static/') and 'no-store' not in headers.get(
                    'cache-control', ''):
                not_no_store.append(f'{e["method"]} {path} {e["status"]}')
            for name, value in headers.items():
                if any(d in value.lower() for d in digests):
                    hashed.append(f'{path} {name}')
            tag = headers.get('etag')
            if path.startswith('/api/') and tag and not re.fullmatch(
                    r'(W/)?"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"', tag):
                bad_etag.append(f'{path} {tag[:20]}')
        prior = self.result['checks'].get('left.no_store', {'ok': True, 'missing': []})
        self.check('left.no_store', prior['ok'] and not not_no_store, missing=(prior['missing'] + not_no_store)[:20])
        prior = self.result['checks'].get('left.no_hash_header', {'ok': True, 'found': []})
        self.check('left.no_hash_header', prior['ok'] and not hashed and not bad_etag,
                   found=(prior['found'] + hashed + bad_etag)[:20])


EXPECTED_EXTRA = set()  # (method, url, status) answers a flow expects beyond the allowed statuses


# --- module helpers ---------------------------------------------------------------------------------------------------

def idlest_cores(n: int, seconds: float = 1.5) -> str:
    """The ``n`` CPUs with the most idle time over ``seconds`` (profile P3 confines Chromium to them; a shared host's
    busy cores would measure the other work, not the page)."""
    def sample():
        out = {}
        for line in Path('/proc/stat').read_text().splitlines():
            m = re.match(r'cpu(\d+)\s+(.*)', line)
            if m:
                values = [int(v) for v in m.group(2).split()]
                out[int(m.group(1))] = (values[3] + values[4], sum(values))
        return out
    first = sample()
    time.sleep(seconds)
    second = sample()
    idle = {cpu: (second[cpu][0] - first[cpu][0]) / max(1, second[cpu][1] - first[cpu][1])
            for cpu in second if cpu in first}
    return ','.join(str(cpu) for cpu in sorted(sorted(idle, key=idle.get, reverse=True)[:n]))


def utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def read_revision(tree: Path) -> str:
    for candidate in (tree.parent / 'REVISION', tree / 'REVISION'):
        if candidate.exists():
            return candidate.read_text().strip()
    try:
        return subprocess.run(['git', '-C', str(tree), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                              timeout=20).stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


def tree_hashes(tree: Path) -> dict:
    names = ('studio/static/studio/app.js', 'studio/static/studio/styles.css', 'cptstudio/settings.py',
             'deploy/gunicorn.conf.py', 'cptstudio/wsgi.py', 'deploy/nginx/cpt-quillmd-https.conf')
    return {name: sha256_file(tree / name) for name in names}


def versions() -> dict:
    out = {'python': platform.python_version()}
    for module in ('django', 'gunicorn', 'psycopg'):
        try:
            out[module] = __import__(module).__version__
        except Exception:
            out[module] = None
    try:
        out['node'] = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=20).stdout.strip()
        out['playwright'] = json.loads((Path(PLAYWRIGHT) / 'package.json').read_text())['version']
    except Exception:
        pass
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SHOW server_version')
            out['postgresql'] = cur.fetchone()[0]
    except Exception:
        out['postgresql'] = None
    return out


def static_weights(static: Path) -> dict:
    """WhiteNoise's compressed files of app.js and styles.css as collectstatic wrote them (the hashed names)."""
    out = {}
    manifest = json.loads((static / 'staticfiles.json').read_text())['paths']
    for name in ('studio/app.js', 'studio/styles.css'):
        hashed = manifest.get(name)
        gz = static / f'{hashed}.gz' if hashed else None
        out[name] = {'hashed': hashed, 'gz_bytes': gz.stat().st_size if gz and gz.exists() else None,
                     'bytes': (static / hashed).stat().st_size if hashed and (static / hashed).exists() else None}
    return out


def terminate_web_backends(db_name: str) -> int:
    """pg_terminate_backend for every other connection to the bench's OWN test database (never another database)."""
    from django.db import connection
    if not db_name.startswith(TEST_PREFIX):
        raise RuntimeError('refused: not a test database')
    with connection.cursor() as cur:
        cur.execute('SELECT count(*) FROM (SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                    'WHERE datname = %s AND pid <> pg_backend_pid()) t', [db_name])
        ended = cur.fetchone()[0]
    connection.close()
    return ended


def health_release(base: str):
    try:
        return json.loads(get(base, '/health/')['body'])
    except Exception:
        return None


def classify(statements: list[str]) -> dict:
    """A request's statements by what they serve: the list builder's own (the document tables), the read record, the
    rate counter, and the rest (session, sign-in, membership)."""
    out = {'total': len(statements), 'builder': 0, 'record': 0, 'rate': 0, 'other': 0}
    for sql in statements:
        s = sql.lower()
        if 'studio_ratewindow' in s:
            out['rate'] += 1
        elif 'studio_accessrecord' in s or s.startswith(('savepoint', 'release savepoint', 'rollback to savepoint')):
            out['record'] += 1
        elif re.search(r'studio_(encounter|codinground|sourcefile|sourcerevision)\b', s):
            out['builder'] += 1
        else:
            out['other'] += 1
    return out


def vhost_zones(tree: Path) -> dict:
    """The front door's limit_req zones and their bursts, read from the tree's own vhost file."""
    text = (tree / 'deploy' / 'nginx' / 'cpt-quillmd-https.conf').read_text()
    zones = {m.group(2): {'key': m.group(1), 'rate': m.group(3)} for m in
             re.finditer(r'limit_req_zone\s+\$(\S+)\s+zone=(\w+):\S+\s+rate=(\S+?);', text)}
    for m in re.finditer(r'limit_req\s+zone=(\w+)\s+burst=(\d+)', text):
        zones.setdefault(m.group(1), {})['burst'] = int(m.group(2))
    key_map = r'map\s+"\$cpt_exempt:\$request_method \$uri"\s+\$(\w+)\s*\{(.*?)\}'
    maps = {m.group(1): m.group(2) for m in re.finditer(key_map, text, re.S)}
    return {'zones': zones, 'maps': maps}


# --- the gate parts' judgements and probes (records, markers, the other tree, plans) ----------------------------------

UUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def request_row(case: str, role: str, params: dict, attempts: int, canonical) -> dict:
    """One request the coder was sent, as the coder row compares it (bench[3], D-R2-44): the sha256 of its exact
    parameters (the document's bytes included) with output_config.effort taken out, and that effort beside it, so
    release 1 at 'max' and R2-33's 'high' are compared byte for byte on everything else."""
    rest = json.loads(canonical(params))
    effort = (rest.get('output_config') or {}).pop('effort', None)
    return {'case': case, 'role': role, 'params_sha256': hashlib.sha256(canonical(rest)).hexdigest()[:16],
            'effort': effort, 'attempts': attempts}


def read_kind(method: str, url: str):
    """The access row a served request writes, by its method and path (studio.read_audit.VIEW_KINDS), or None."""
    path, _, query = url.partition('?')
    if (method == 'GET' and path == '/api/encounters') or (method == 'POST' and path == '/api/encounters/search'):
        return 'member.list'
    if method == 'GET' and re.fullmatch(rf'/api/encounters/{UUID_RE}', path):
        return 'member.detail'
    if method == 'GET' and re.fullmatch(rf'/api/encounters/{UUID_RE}/original', path):
        return 'member.inline' if 'view=1' in query.split('&') else 'member.download'
    return None


def records_n100_rule(judged: dict) -> dict:
    """At the practice of 100 the records flow opens four documents and downloads three files (records[8]): a kind
    with no answer is a failure, never a vacuous pass of the equation."""
    judged['openings']['ok'] = judged['openings']['ok'] and len(judged['openings']['opens']) == 4
    kinds = judged['equation']['kinds']
    judged['equation']['ok'] = judged['equation']['ok'] and all(
        kinds[k]['answers'] > 0 for k in ('member.list', 'member.detail', 'member.inline', 'member.download'))
    return judged


def judge_records(entries: list, rows: list, repeats_added: int, actions: list, lists: list, docs=None) -> dict:
    """The records part's exact gates over one flow: ``entries`` the proxy's log (each with its X-Request-ID),
    ``rows`` the access rows written meanwhile, ``repeats_added`` the counted repeats added meanwhile, ``actions`` and
    ``lists`` what the page did and the list answers it received (each with the request id the proxy gave it), and
    ``docs`` the rich documents by label (their ids and barcode numbers)."""
    rid = lambda e: (e.get('reqHeaders') or {}).get('x-request-id', '')
    served = [e for e in entries if e['status'] in (200, 304) and read_kind(e['method'], e['url'])]
    by_rid = {}
    for row in rows:
        by_rid.setdefault(row['request_id'], []).append(row)
    out = {}
    kinds, polls = {}, []
    for kind in ('member.list', 'member.detail', 'member.inline', 'member.download'):
        mine = [e for e in served if read_kind(e['method'], e['url']) == kind]
        polled = [e for e in mine if kind == 'member.detail' and (e.get('reqHeaders') or {}).get('x-cpt-poll') == '1']
        polls += polled
        plain = [e for e in mine if e not in polled]
        rows_k = [r for r in rows if r['view'] == kind and r['outcome'] != 'refused']
        if kind == 'member.list':
            ok = len(mine) == len(rows_k) + repeats_added
        else:
            ok = all(len([r for r in by_rid.get(rid(e), []) if r['view'] == kind]) == 1 for e in plain) and \
                len([r for r in rows_k if r['request_id'] not in {rid(e) for e in polled}]) == len(plain)
        kinds[kind] = {'answers': len(mine), 'polls': len(polled), 'rows': len(rows_k), 'ok': ok}
    answered = {rid(e) for e in served}
    orphans = [r['view'] for r in rows if r['request_id'] not in answered and r['outcome'] != 'refused']
    out['equation'] = {'ok': all(k['ok'] for k in kinds.values()) and not orphans, 'kinds': kinds, 'orphans': orphans,
                       'repeats_added': repeats_added}
    # records[7]: release 1 (read_audit.detail_seen_recently) writes a poll's row only when this sign-in has no served
    # member.detail row of the document - the open's own included - within 60 s before it on the same UTC day
    poll_rids = {rid(e) for e in polls}
    details = sorted((r for r in rows if r['view'] == 'member.detail' and r['outcome'] == 'served'),
                     key=lambda r: r['created_at'])
    same_day = lambda q, r: q['created_at'] // 86400000 == r['created_at'] // 86400000  # noqa: E731
    crowded = [round(r['created_at'] - q['created_at']) for i, r in enumerate(details) if r['request_id'] in poll_rids
               for q in details[:i] if (q['sign_in_ref'], q['encounter_ids']) == (r['sign_in_ref'], r['encounter_ids'])
               and same_day(q, r) and r['created_at'] - q['created_at'] < 60000]
    out['polls'] = {'ok': not crowded, 'poll_answers': len(polls),
                    'poll_rows': sum(1 for r in rows if r['request_id'] in poll_rids), 'crowded_ms': crowded[:10]}
    opens, late = [], []
    for a in actions:
        if a.get('kind') != 'records-open':
            continue
        written = [r for item in a.get('rids', []) for r in by_rid.get(item[3], [])]
        detail = sum(1 for r in written if r['view'] == 'member.detail')
        inline = sum(1 for r in written if r['view'] == 'member.inline')
        library_failed = a.get('mode') == 'frame' and a.get('label') != 'text-note'
        # records[5]: the opening's rows name the document opened, and what was drawn is that document (its barcode)
        doc = (docs or {}).get(a.get('label')) or {}
        mine = [r for r in written if r['view'] in ('member.detail', 'member.inline')]
        named = bool(doc) and all(r['encounter_ids'] == [doc.get('id')] for r in mine)
        drawn = a.get('firstPage') is None or (a.get('barcode') or {}).get('number') == doc.get('number')
        opens.append({'label': a.get('label'), 'detail': detail, 'inline': inline, 'named': named, 'drawn': drawn,
                      'ok': named and drawn and detail == 1 and (inline == 1 or (library_failed and inline == 2))})
        pixels = a.get('canvasEpoch')
        for r in written:
            if r['view'] == 'member.inline' and pixels and r['created_at'] > pixels:
                late.append({'label': a.get('label'), 'row_after_pixels_ms': round(r['created_at'] - pixels, 1)})
    out['openings'] = {'ok': all(o['ok'] for o in opens), 'opens': opens}
    out['inline_before_pixels'] = {'ok': not late, 'late': late}
    mismatches = []
    seen_ids = [r['encounter_ids'] for r in rows if r['view'] == 'member.list']
    sent = {rid(e): e['url'] for e in served}

    def wanted(answer):  # records[6], R2-21: {list, before} of the request the proxy saw; a search's cursor its body's
        path, _, query = (sent.get(answer.get('rid') or '') or '').partition('?')
        if path == '/api/encounters/search':
            return {'list': 'search', 'before': answer.get('before')}
        q = urllib.parse.parse_qs(query)
        return {'list': q.get('list', ['documents'])[0], 'before': q.get('before', [None])[0]}
    for answer in lists:
        written = [r for r in by_rid.get(answer.get('rid') or '', []) if r['view'] == 'member.list']
        if written:
            if written[0]['encounter_ids'] != answer.get('ids') or written[0]['count'] != len(answer.get('ids') or []) \
                    or written[0].get('filters') != wanted(answer):
                mismatches.append({'path': answer.get('path'), 'served': len(answer.get('ids') or []),
                                   'named': len(written[0]['encounter_ids'] or [])})
        elif not (repeats_added and answer.get('ids') in seen_ids):
            mismatches.append({'path': answer.get('path'), 'served': len(answer.get('ids') or []), 'named': None})
    out['list_ids'] = {'ok': bool(lists) and not mismatches, 'answers': len(lists), 'mismatches': mismatches[:10]}
    return out


def marker_in_files(raw: Path, word: str) -> dict:
    """{file: True} for each of the round's server-side logs that holds the marker: every URL and header the proxy saw
    (every cookie but the server's own, records[4]), every gunicorn line."""
    return {path.name: True for pattern in ('proxy-*.jsonl', 'access-*.log', 'gunicorn-*.err')
            for path in raw.glob(pattern) if word in path.read_text(errors='replace')}


def marker_in_pages(pages: dict | None) -> dict:
    """{page-<size>: where} for each records flow whose page held the marker (its URLs, history, window name, Web
    Storage, cookies, Cache API or IndexedDB names: bench.cjs pageMarkerHits), and 'never read' for a flow that did not
    read its page, so it fails instead of passing vacuously (records[4])."""
    found = {}
    for size, hits in (pages or {}).items():
        if hits is None or hits:
            found[f'page-{size}'] = 'never read' if hits is None else hits[:10]
    return found


def marker_audit(raw: Path, word: str, pages: dict | None = None):
    """(ok, where): the marker typed into the search appears in no URL or header the proxy saw, no gunicorn line, no
    access row or security event, and nowhere the page itself kept it (the bench's own inputs are not scanned)."""
    from studio import models
    found = {**marker_in_files(raw, word), **marker_in_pages(pages)}
    rows = models.AccessRecord.objects.filter(filters__icontains=word).count() + \
        models.AccessRecord.objects.filter(reason__icontains=word).count()
    events = sum(1 for data in models.SecurityEvent.objects.values_list('data', flat=True)
                 if word in json.dumps(data))
    if rows:
        found['access_records'] = rows
    if events:
        found['security_events'] = events
    return not found, {'found': found}


def read_client(tree: Path) -> tuple[str, str]:
    """Another tree's client header and version, read from its own studio/client_contract.py (never written here)."""
    text = (tree / 'studio' / 'client_contract.py').read_text()
    header = re.search(r"^HEADER = '([^']+)'", text, re.M).group(1)
    return header, re.search(r"^VERSION = '([^']+)'", text, re.M).group(1)


def get_with_host(base: str, path: str, host: str) -> dict:
    port = int(base.rsplit(':', 1)[1])
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
    c.request('GET', path, headers={'Host': host, 'X-Request-ID': secrets.token_hex(16)})
    r = c.getresponse()
    r.read()
    c.close()
    return {'status': r.status}


def release2_index_names(tree: Path) -> list[str]:
    """The indexes this tree's migrations after 0018 add (release 2's 0019-0021), by the names they give them."""
    names = set()
    for path in sorted((tree / 'studio' / 'migrations').glob('00*.py')):
        if int(path.name[:4]) >= 19:
            names |= set(re.findall(r"name=['\"](studio_[a-z0-9_]+)['\"]", path.read_text()))
    return sorted(names)


def plans_seed(password: str, *, documents: int, runs_per: int, records: int, name: str) -> dict:
    """A practice of ``documents`` (a round each), ``runs_per`` coding runs per round and ``records`` access rows, as
    bulk data in the bench's throwaway database."""
    from django.db import connection
    from studio import jobs, models
    ws, user = bd.practice(name, documents, password, seed=documents)
    rounds = list(models.CodingRound.objects.filter(encounter__workspace=ws).values_list('id', 'encounter_id',
                                                                                         'revision_id'))
    purposes = list(jobs.PURPOSES)
    models.ProviderRun.objects.bulk_create(
        [models.ProviderRun(encounter_id=e, revision_id=rv, provider='anthropic', adapter_version='bench@1',
                            request_body={}, contexts=[], state=models.ProviderRun.SUCCEEDED,
                            purpose=purposes[k % len(purposes)], scope={'round': str(r)})
         for r, e, rv in rounds for k in range(runs_per)], batch_size=5000)
    with connection.cursor() as cur:
        cur.execute("INSERT INTO studio_accessrecord (id, created_at, host, view, actor_id, actor_kind, actor_role, "
                    "workspace_id, encounter_ids, filters, reason, outcome, client, request_id) "
                    "SELECT gen_random_uuid(), now() - (g * interval '1 second'), 'cpt', 'member.detail', %s, 'human', "
                    "'reviewer', %s, '[]'::jsonb, '{}'::jsonb, '', 'served', '', '' FROM generate_series(1, %s) g",
                    [user.pk, ws.pk, records])
        cur.execute('ANALYZE')
        counts = {}
        for table in ('studio_encounter', 'studio_providerrun', 'studio_codinground', 'studio_accessrecord'):
            cur.execute(f'SELECT count(*) FROM {table}')
            counts[table] = cur.fetchone()[0]
    return {'ws': ws, 'user': user, 'round': rounds[len(rounds) // 2], 'counts': counts}


def rebuild_indexes(names: list) -> dict:
    """{index: ms}: each index dropped and built again by its own definition (pg_indexes), at the database's size
    now."""
    from django.db import connection
    out = {}
    with connection.cursor() as cur:
        for name in names:
            cur.execute('SELECT indexdef FROM pg_indexes WHERE indexname = %s', [name])
            row = cur.fetchone()
            if not row:
                out[name] = None
                continue
            cur.execute(f'DROP INDEX "{name}"')
            started = time.perf_counter()
            cur.execute(row[0])
            out[name] = round((time.perf_counter() - started) * 1000, 1)
    return out


def insert_during_build(names: list, big: dict) -> list:
    """For each index: build it in a transaction (as a migration does: its SHARE lock held until the commit) while an
    insert into its table starts 20 ms in; the insert's wait and the build's time, in ms."""
    from django.db import connection, connections, transaction
    from studio import models
    out = []
    with connection.cursor() as cur:
        cur.execute('SELECT indexname, tablename, indexdef FROM pg_indexes WHERE indexname = ANY(%s)', [list(names)])
        found = cur.fetchall()
    enc_id, rev_id = big['round'][1], big['round'][2]
    inserts = {
        'studio_encounter': lambda: models.Encounter.objects.create(workspace=big['ws'], title='Bench insert',
                                                                    created_by=big['user']),
        'studio_providerrun': lambda: models.ProviderRun.objects.create(
            encounter_id=enc_id, revision_id=rev_id, provider='anthropic', adapter_version='bench@1', request_body={},
            contexts=[], purpose='coding_reader', scope={'round': str(big['round'][0])}),
        'studio_codinground': lambda: models.CodingRound.objects.create(
            encounter_id=enc_id, revision_id=rev_id, number=900 + len(out), trigger='retry', context={}, state='done')}
    for name, table, definition in found:
        with connection.cursor() as cur:
            cur.execute(f'DROP INDEX "{name}"')
        timing = {}

        def build():
            started = time.perf_counter()
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(definition)
                timing['build_ms'] = round((time.perf_counter() - started) * 1000, 1)
            connections.close_all()

        def insert():
            time.sleep(0.02)
            started = time.perf_counter()
            inserts[table]()
            timing['insert_ms'] = round((time.perf_counter() - started) * 1000, 1)
            connections.close_all()
        threads = [threading.Thread(target=build), threading.Thread(target=insert)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        out.append({'index': name, 'table': table, **timing})
    return out


def explain_changed_reads(bench, big: dict) -> list:
    """EXPLAIN (ANALYZE, BUFFERS) of every statement the changed reads send to the three tables, at the bulk size: the
    list, queue and search pages and the counts (through the tree's own views), the round lookups and the sweeps."""
    from django.db import connection
    from django.test import Client
    from django.test.utils import CaptureQueriesContext, override_settings
    from studio import jobs, models, operator, request_meta
    from tests.support import operator as ops
    captured = []

    def capture(label, call):
        try:
            with CaptureQueriesContext(connection) as q:
                call()
        except Exception as exc:
            captured.append((label, None, f'{type(exc).__name__}: {exc}'[:200]))
            return
        for item in q.captured_queries:
            sql = item['sql']
            if sql.lstrip().upper().startswith('SELECT') and re.search(r'studio_(encounter|providerrun|codinground)\b',
                                                                       sql):
                captured.append((label, sql, None))
    with override_settings(STATIC_ROOT=bench.raw / 'static'):
        c = Client(HTTP_HOST='cpt.quillmd.com', HTTP_X_REQUEST_ID='0' * 32)
        c.force_login(big['user'])
        ops.mark_signed_in(c, door=request_meta.CPT)
        api = {f'HTTP_{bench.client[0].upper().replace("-", "_")}': bench.client[1]}
        capture('list page', lambda: c.get('/api/encounters?list=documents', **api))
        capture('queue page', lambda: c.get('/api/encounters?list=queue', **api))
        capture('search', lambda: c.post('/api/encounters/search',
                                         data=json.dumps({'text': TYPICAL_WORD, 'before': None}),
                                         content_type='application/json', **api))
        capture('counts', lambda: c.get('/api/session', **api))
    round_ = models.CodingRound.objects.get(pk=big['round'][0])
    capture('awaiting_reconcile', lambda: jobs.awaiting_reconcile(round_))
    capture('reused', lambda: jobs._reused(round_, jobs.PURPOSES[0]))
    capture('abandoned_outcome', lambda: jobs.abandoned_outcome(round_))
    capture('sweeps', lambda: jobs.mark_stale())
    capture('round_runs', lambda: operator.round_runs(round_))
    out = []
    for label, sql, error in captured:
        if error:
            out.append({'read': label, 'error': error, 'ms': 0, 'seq_scans': []})
            continue
        with connection.cursor() as cur:
            cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql)
            plan = cur.fetchone()[0][0]

        def walk(node):
            yield node
            for child in node.get('Plans', []):
                yield from walk(child)
        nodes = list(walk(plan['Plan']))
        out.append({'read': label, 'sql': sql[:160], 'ms': round(plan['Execution Time'] + plan['Planning Time'], 2),
                    'seq_scans': sorted({n.get('Relation Name') for n in nodes if n['Node Type'] == 'Seq Scan'
                                         and n.get('Relation Name') in ('studio_encounter', 'studio_providerrun',
                                                                        'studio_codinground')}),
                    'indexes': sorted({n['Index Name'] for n in nodes if 'Index Name' in n})})
    return out


# --- the protocol: trees in a declared, interleaved order -------------------------------------------------------------

def bench_host_quiet(load1: float, load5: float, max_load: float, max_load_5: float) -> bool:
    """The driver starts a run only when the 1-minute load is at most max_load and the 5-minute at most max_load_5. On a
    host whose other work comes in waves, a 5-minute bound of 8 starts runs minutes into each quiet window; the judge's
    own rule (no load sample above 8 during the run) is what makes a round valid, whatever the start."""
    return load1 <= max_load and load5 <= max_load_5


def driver(argv=None) -> int:
    """Run rounds in order, one part group at a time: for each group, every TAG:ROUND of --order in turn, so the trees
    being compared are interleaved in time. Each run is `manage.py test` inside its own tree, with this folder's
    bench_run.py; nothing is run when the recipe's database settings would be refused."""
    import argparse
    parser = argparse.ArgumentParser(description=driver.__doc__)
    parser.add_argument('--tree', action='append', required=True, help='TAG=<folder that holds cpt-studio/>')
    parser.add_argument('--order', required=True, help='TAG:ROUND,TAG:ROUND,... e.g. A:1,B:1,A:2,B:2,A:3,B:3')
    parser.add_argument('--group', action='append', required=True,
                        help='a comma list of parts run together, optionally with its own profiles: open@P0, '
                             'lists@P1+P2')
    parser.add_argument('--out', required=True)
    parser.add_argument('--ports', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--profiles', default=','.join(PROFILES))
    parser.add_argument('--max-load', type=float, default=4.0,
                        help='before each run, wait (up to --wait-minutes) until the 1-minute load is at most this and '
                             'the 5-minute load at most --max-load-5')
    parser.add_argument('--max-load-5', type=float, default=8.0,
                        help='the 5-minute load bound for a start (higher: sooner after a wave of other work)')
    parser.add_argument('--wait-minutes', type=int, default=90)
    parser.add_argument('--retries', type=int, default=2,
                        help='a round whose load passed 8 (the judge\'s INVALID) is run again as round + 100, '
                             'this often')
    args = parser.parse_args(argv)
    trees = dict(item.split('=', 1) for item in args.tree)
    order = [(tag, int(n)) for tag, n in (item.split(':') for item in args.order.split(','))]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    parse_ports(args.ports)
    db = {'HOST': os.environ.get('CPT_STUDIO_DB_HOST'), 'PORT': os.environ.get('CPT_STUDIO_DB_PORT'),
          'TEST': {'NAME': f'{TEST_PREFIX}{os.environ.get("CPT_STUDIO_TEST_DB_SUFFIX", "")}'}}
    why = refusals(db, os.environ.get('CPT_STUDIO_CODING_MODE', 'disabled'))
    if why or not os.environ.get('CPT_STUDIO_TEST_DB_SUFFIX'):
        print('refused: ' + '; '.join(why or ['CPT_STUDIO_TEST_DB_SUFFIX is not set']), file=sys.stderr)
        return 2
    import judge  # the judge's own validity rule (no Django): the driver keeps and runs again by it
    controls = json.loads((HERE / 'acceptance.json').read_text()).get('controls', [])
    log = open(out / 'protocol.log', 'a')
    status = 0
    for spec in args.group:
        group, _, own = spec.partition('@')
        profiles = own.split('+') if own else None
        for tag, first_round in order:
            tree = Path(trees[tag]).resolve() / 'cpt-studio'
            attempt, busy, rc, valid = 0, 0, 0, False
            while attempt <= args.retries:
                round_no = first_round + 100 * attempt
                written = out / out_name(tag, round_no, group.split(','), profiles)
                if written.exists():  # a resumed protocol: a round measured before is kept as it is, never run again
                    why = judge.attempt_reasons(written.name, json.loads(written.read_text()), controls)
                    log.write(f'{utc()} {tag}:{round_no} {spec} measured before, '
                              f'{"valid" if not why else "INVALID: " + why[0]}; kept, not run again\n')
                    log.flush()
                    if not why:
                        valid = True
                        break
                    attempt += 1
                    continue
                waited = 0
                while (not bench_host_quiet(*os.getloadavg()[:2], args.max_load, args.max_load_5) and
                       waited < args.wait_minutes * 60) or not lock_free(out / 'bench.lock'):
                    time.sleep(30)
                    waited += 30
                env = {**os.environ, 'BENCH_TAG': tag, 'BENCH_ROUND': str(round_no), 'BENCH_PARTS': group,
                       'BENCH_OUT': str(out), 'BENCH_PORTS': args.ports,
                       'BENCH_PROFILES': ','.join(profiles) if profiles else args.profiles,
                       'BENCH_GROUP_PROFILES': '1' if profiles else '0'}
                line = f'{utc()} {tag}:{round_no} {spec} load={os.getloadavg()[0]:.2f} waited={waited}s'
                print(line, flush=True)
                log.write(line + '\n')
                log.flush()
                run_log = out / f'run-{tag}-r{round_no}-{spec.replace(",", "+")}.log'
                with open(run_log, 'w') as handle:
                    done = subprocess.run([args.python, '-B', 'manage.py', 'test', str(HERE), '--pattern',
                                           'bench_run.py', '--noinput'], cwd=tree, env=env, stdout=handle,
                                          stderr=subprocess.STDOUT, timeout=4 * 3600)
                if not written.exists() and 'another bench holds the lock' in run_log.read_text() and busy < 50:
                    busy += 1  # another bench took the lock first: nothing was measured, the same round is run again
                    log.write(f'{utc()} {tag}:{round_no} {spec} the lock was held by another bench; waiting\n')
                    log.flush()
                    continue
                rc = done.returncode
                data = json.loads(written.read_text()) if written.exists() else None
                peak = (data or {}).get('load_max', 99)
                why = ([f'exit {rc}'] if rc else []) + (judge.attempt_reasons(written.name, data, controls)
                                                         if data is not None else ['no round file'])
                log.write(f'{utc()} {tag}:{round_no} {spec} exit {rc} load_max={peak}\n')
                log.flush()
                if not why:
                    valid = True
                    break
                log.write(f'{utc()} {tag}:{round_no} {spec} INVALID (exit {rc}, load {peak}; {why[0][:160]}); '
                          f'{"run again" if attempt < args.retries else "no retries left"}\n')
                log.flush()
                attempt += 1
            # protocol[0]: a round still INVALID with every retry spent fails the driver, whatever its exit code
            status = status or rc or (0 if valid else 3)
    log.close()
    return status


if __name__ == '__main__':
    sys.exit(driver())
