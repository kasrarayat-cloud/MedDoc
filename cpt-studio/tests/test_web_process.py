"""Release 2: the web process (specification 2.4; R2-4, web WEB-1). Lane W adds its R2-5 to R2-8 tests to this module.

R2-4, the web loads no AI library. Release 1's web imported the Anthropic SDK at each new worker's first request -
cptstudio.urls, studio.api, studio.jobs, studio.fable.client, anthropic: 2,930 of its modules, about 1.5 s and 48 MiB a
worker - and never used it. studio.jobs now imports the sender only inside the three functions a worker's send runs
(_live_gate, _code and _send), and the worker's command loads it, and the SDK, at its start, so a release that cannot
load them stops there, never at a document.

Specification 2.4, nothing happens at import: gunicorn's master imports the web application once before it forks
(R2-5), so no module the web loads may open a database connection or start a thread at import. (That no process keeps
PHI beyond a request is a review rule, not a test.)

Each probe runs in a fresh interpreter - this Python, this tree, this environment - because this test process imported
the sender long ago (tests.support.coding does), so its own sys.modules says nothing about what the web loads. What the
web loads is cptstudio.wsgi and both hosts' URLconfs with every view module they name: what a worker holds by the end of
its first request, and from R2-5 what the master holds before the fork. The probe's tripwires refuse any database
connection (Django's and the driver's own) and record a thread start without starting it; and the probe counts the
process's own OS threads (/proc/self/task, what CPython 3.12's fork warning reads), which also sees a thread started
below threading.Thread.start (refutation round 1, import[1]). A control in the same probe proves that each trips.

Lane W (R2-5 to R2-9, D-R2-17), below lane F's tests. R2-5: importing cptstudio.wsgi - what gunicorn's master does once,
before it forks - also warms the web (cptstudio.warm): both URLconfs loaded and compiled, every page template compiled,
the static manifest, the hasher's library and the password rules, with nothing open and no thread; the settings file's
two hooks close every connection and freeze the loaded objects before the first fork, and open each worker's own
connection without ever stopping a worker. R2-6 and R2-8: the processes, their class and their recycling, pinned. R2-7:
only the web keeps its connections, with health checks. And a real gunicorn, with the release's own
deploy/gunicorn.conf.py on a free loopback port and this run's test database (synthetic data only, nothing beyond the
loopback): its four workers each hold their own connection before any request, keep it, replace one the database ended
without an error, answer every request while they are recycled, and start when the database does not answer; and every
life-cycle line it writes is one the installer keeps (R2-9). Each server is stopped by the process id this test
started, and its connections are told from every other session by the application name it gives them (PGAPPNAME).
"""
from __future__ import annotations

import ctypes
import functools
import http.client
import importlib.util
import json
import os
import random
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import OperationalError, connection
from django.test import SimpleTestCase

# The probe: tripwires first, then the step (argv[1]), then one line of JSON. Nothing in it reaches a database or the
# network: a connection attempt is refused before any socket opens.
IMPORT_PROBE = r'''
import json, os, sys, threading

opened, started = [], []


def refuse_django(self, *args, **kwargs):
    opened.append(f'django:{self.alias}')
    raise RuntimeError('a database connection was opened')


def refuse_driver(*args, **kwargs):
    opened.append('psycopg')
    raise RuntimeError('a database connection was opened')


def record_thread(self):
    started.append(self.name)  # recorded, never started


from django.db.backends.base import base as django_db_base
django_db_base.BaseDatabaseWrapper.connect = refuse_django
import psycopg
psycopg.connect = refuse_driver
psycopg.Connection.connect = classmethod(refuse_driver)
threading.Thread.start = record_thread

error = None
try:
    exec(sys.argv[1], {'__name__': '__probe__'})
except BaseException as exc:  # reported, never raised: the test reads the report
    error = f'{type(exc).__name__}: {exc}'

# the SDK's own packages (anthropic==2.11.0's transport is httpx2; httpx and httpcore are the family a release could
# bring back) and the sender
SDK = ('anthropic', 'httpx', 'httpx2', 'httpcore', 'pydantic', 'jiter', 'anyio')
MARKERS = ('cptstudio.wsgi', 'cptstudio.urls', 'cptstudio.urls_admin', 'studio.api', 'studio.jobs',
           'studio.management.commands.run_worker', 'studio.fable.client', 'anthropic')
print('PROBE ' + json.dumps({
    'error': error, 'opened': opened, 'started': started, 'threads': threading.active_count(),
    'os_threads': len(os.listdir('/proc/self/task')),
    'loaded': [name for name in MARKERS if name in sys.modules],
    'ai': sorted(name for name in sys.modules if name.split('.')[0] in SDK or name == 'studio.fable.client'),
}))
'''

DJANGO_SETUP_STEP = '''
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cptstudio.settings')
import django
django.setup()
'''
# What the web loads: the WSGI application, then both hosts' URLconfs as a first request resolves them (and as R2-5's
# warm-up does in the master).
WEB_IMPORT_STEP = '''
import cptstudio.wsgi
from django.conf import settings
from django.urls import get_resolver
from studio import hosts
for urlconf in (settings.ROOT_URLCONF, hosts.ADMIN_URLCONF):
    get_resolver(urlconf).reverse_dict
'''
JOBS_IMPORT_STEP = DJANGO_SETUP_STEP + 'import studio.jobs\n'
WORKER_IMPORT_STEP = DJANGO_SETUP_STEP + 'import studio.management.commands.run_worker\n'
# The control: after the web, a connection asked of Django, one asked of the driver, a thread through threading and a
# native one - each must trip.
TRIPWIRE_CONTROL_STEP = WEB_IMPORT_STEP + '''
import threading
import psycopg
from django.db import connection
for attempt in (connection.ensure_connection, lambda: psycopg.connect('')):
    try:
        attempt()
    except RuntimeError:
        pass
threading.Thread(target=print, name='lane-f-control').start()
import _thread, time
_thread.start_new_thread(time.sleep, (60,))
'''
WEB_MODULES = ('cptstudio.wsgi', 'cptstudio.urls', 'cptstudio.urls_admin', 'studio.api', 'studio.jobs')


@functools.cache
def import_probe(step: str) -> dict:
    """The report of a fresh interpreter that ran ``step`` under the tripwires."""
    done = subprocess.run([sys.executable, '-B', '-c', IMPORT_PROBE, step], cwd=settings.BASE_DIR, env=dict(os.environ),
                          capture_output=True, timeout=300)
    reports = [line for line in done.stdout.decode().splitlines() if line.startswith('PROBE ')]
    if done.returncode != 0 or len(reports) != 1:
        raise AssertionError(f'the probe did not report (exit {done.returncode}): {done.stderr.decode()[-3000:]}')
    return json.loads(reports[0][len('PROBE '):])


class TheWebLoadsNoAiLibraryTests(SimpleTestCase):
    def test_the_web_holds_no_ai_library(self):
        web = import_probe(WEB_IMPORT_STEP)
        self.assertIsNone(web['error'])
        # the web was loaded, studio.jobs with it (studio.api imports it), so the absence below is the web's
        self.assertEqual([name for name in WEB_MODULES if name in web['loaded']], list(WEB_MODULES))
        self.assertEqual(web['ai'], [])

    def test_importing_the_jobs_module_leaves_the_sender_unloaded(self):
        jobs = import_probe(JOBS_IMPORT_STEP)
        self.assertIsNone(jobs['error'])
        self.assertIn('studio.jobs', jobs['loaded'])
        self.assertEqual(jobs['ai'], [])

    def test_the_worker_loads_the_sender_and_its_sdk_at_its_start(self):
        worker = import_probe(WORKER_IMPORT_STEP)
        self.assertIsNone(worker['error'])
        for name in ('studio.management.commands.run_worker', 'studio.fable.client', 'anthropic'):
            with self.subTest(name=name):
                self.assertIn(name, worker['loaded'])


class NothingHappensAtImportTests(SimpleTestCase):
    """Specification 2.4's two import rules, held for everything the web loads."""

    def test_the_web_opens_no_database_connection_at_import(self):
        web = import_probe(WEB_IMPORT_STEP)
        self.assertIsNone(web['error'])
        self.assertEqual(web['opened'], [])

    def test_the_web_starts_no_thread_at_import(self):
        web = import_probe(WEB_IMPORT_STEP)
        self.assertIsNone(web['error'])
        self.assertEqual(web['started'], [])
        self.assertEqual(web['threads'], 1)
        self.assertEqual(web['os_threads'], 1)  # a thread started below threading.Thread.start too

    def test_the_probe_sees_a_connection_and_a_thread(self):
        # the positive control: the same tripwires, after the same import, catch each kind of act
        control = import_probe(TRIPWIRE_CONTROL_STEP)
        self.assertIsNone(control['error'])
        self.assertEqual(control['opened'], ['django:default', 'psycopg'])
        self.assertEqual(control['started'], ['lane-f-control'])
        self.assertEqual(control['os_threads'], 2)  # the recorded thread never starts; the native one does


# --- Lane W: the web's process (R2-5 to R2-9, D-R2-17) --------------------------------------------------------------

GUNICORN_CONF = Path(settings.BASE_DIR) / 'deploy' / 'gunicorn.conf.py'
# The loopback ports a real gunicorn of this module may listen on (this host's lane W range; never the live site's 9150
# or 9151): each is checked free first, and one taken meanwhile is skipped. CPT_STUDIO_GUNICORN_PORTS ('first-last')
# keeps a run to another range of this host's.
_LANE_W_PORTS_ASKED = re.fullmatch(r'(\d+)-(\d+)', os.environ.get('CPT_STUDIO_GUNICORN_PORTS', ''))
GUNICORN_TEST_PORTS = (range(int(_LANE_W_PORTS_ASKED.group(1)), int(_LANE_W_PORTS_ASKED.group(2)) + 1)
                       if _LANE_W_PORTS_ASKED else range(9400, 9450))
# The line a step prints for lane W's probes, beside the tripwire probe's own PROBE line
LANE_W_REPORT = 'LANE-W '
# Release 1's access line (RELEASE-1-SPEC A2), which release 2 keeps byte for byte
RELEASE_1_ACCESS_FORMAT = ('%(t)s %({x-forwarded-for}i)s "%(m)s %(U)s %(H)s" %(s)s %(B)s %(M)sms '
                           '%({x-request-id}i)s %({x-cpt-actor}o)s')


def gunicorn_settings() -> dict:
    """deploy/gunicorn.conf.py's names, as gunicorn reads the file: executed as Python."""
    namespace = {'__name__': 'lane_w_gunicorn_conf'}
    exec(compile(GUNICORN_CONF.read_text(encoding='utf-8'), str(GUNICORN_CONF), 'exec'), namespace)  # noqa: S102
    return namespace


@functools.cache
def lane_w_probe(step: str, tripwires: bool = True, database: str = '') -> tuple:
    """(lane F's tripwire report, or None without ``tripwires``; the LANE-W report ``step`` printed, or None) of a fresh
    interpreter - this Python, this tree - that ran ``step``. Its environment is this process's without CPT_STUDIO_WEB,
    since only cptstudio.wsgi may set it, and names ``database`` when given (a step that connects for real)."""
    environment = {name: value for name, value in os.environ.items() if name != 'CPT_STUDIO_WEB'}
    if database:
        environment['CPT_STUDIO_DB_NAME'] = database
    code = [IMPORT_PROBE, step] if tripwires else [step]
    done = subprocess.run([sys.executable, '-B', '-c', *code], cwd=settings.BASE_DIR, env=environment,
                          capture_output=True, timeout=300)
    lines = done.stdout.decode().splitlines()
    probes = [json.loads(line[len('PROBE '):]) for line in lines if line.startswith('PROBE ')]
    reports = [json.loads(line[len(LANE_W_REPORT):]) for line in lines if line.startswith(LANE_W_REPORT)]
    if done.returncode != 0 or len(probes) != int(tripwires) or len(reports) > 1:
        raise AssertionError(f'the probe did not report (exit {done.returncode}): {done.stderr.decode()[-3000:]}')
    return (probes[0] if probes else None), (reports[0] if reports else None)


# How a process reads its database connection settings, for the steps below
CONNECTION_SETTINGS_REPORT = r'''
import json, os
from django.conf import settings
lane_w_database = settings.DATABASES['default']
print('LANE-W ' + json.dumps({'kept': [lane_w_database['CONN_MAX_AGE'], lane_w_database['CONN_HEALTH_CHECKS']],
                              'web': os.environ.get('CPT_STUDIO_WEB'),
                              'connect_timeout': lane_w_database.get('OPTIONS', {}).get('connect_timeout')}))
'''
# R2-5: what gunicorn's master holds once it has imported cptstudio.wsgi, and nothing else (R2-7's settings with it)
WARMED_WEB_STEP = r'''
import json, os, sys
import cptstudio.wsgi
from django.conf import settings
from django.contrib.auth.hashers import get_hashers
from django.contrib.auth.password_validation import get_default_password_validators
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import connections
from django.template import engines
from django.urls import get_resolver
from django.utils.functional import empty
from studio import hosts

lane_w_database = settings.DATABASES['default']
print('LANE-W ' + json.dumps({
    'resolvers': [get_resolver(urlconf)._populated for urlconf in (settings.ROOT_URLCONF, hosts.ADMIN_URLCONF)],
    'templates': sorted(str(name) for name in engines['django'].engine.template_loaders[0].get_template_cache),
    'manifest': staticfiles_storage._wrapped is not empty,
    'argon2': 'argon2' in sys.modules,
    'hashers': get_hashers.cache_info().currsize,
    'validators': get_default_password_validators.cache_info().currsize,
    'open': sorted(alias for alias in connections if connections[alias].connection is not None),
    'kept': [lane_w_database['CONN_MAX_AGE'], lane_w_database['CONN_HEALTH_CHECKS']],
    'connect_timeout': lane_w_database.get('OPTIONS', {}).get('connect_timeout'),
    'web': os.environ.get('CPT_STUDIO_WEB'),
    'os_threads': len(os.listdir('/proc/self/task')),  # the kernel's count: a thread below threading.Thread too
}))
'''
# R2-7: the worker's command as the worker starts it (deploy/entrypoint.sh: python manage.py run_worker) and any other
# management command (python manage.py check): manage.py run as the main module, as python runs it, then the report.
# The worker's command is loaded, never run (help).
MANAGE_STEP = '''
import runpy, sys
sys.argv = {argv!r}
runpy.run_path('manage.py', run_name='__main__')
'''
WORKER_SETTINGS_STEP = MANAGE_STEP.format(argv=['manage.py', 'help', 'run_worker']) + CONNECTION_SETTINGS_REPORT
COMMAND_SETTINGS_STEP = MANAGE_STEP.format(argv=['manage.py', 'check']) + CONNECTION_SETTINGS_REPORT
# R2-5: the release's when_ready hook in a master that loaded the web and then held a real connection to the test
# database - as an import that broke rule 2.4 would leave it - the moment before its first fork
WHEN_READY_STEP = r'''
import gc, json, os
import cptstudio.wsgi
from django.db import connection, connections
connection.ensure_connection()
before = {'open': connection.connection is not None, 'frozen': gc.get_freeze_count()}
lane_w_conf = {}
exec(compile(open('deploy/gunicorn.conf.py').read(), 'deploy/gunicorn.conf.py', 'exec'), lane_w_conf)
lane_w_conf['when_ready'](None)
lane_w_open = sorted(alias for alias in connections if connections[alias].connection is not None)
print('LANE-W ' + json.dumps({'before': before, 'frozen': gc.get_freeze_count(), 'open': lane_w_open,
                              'os_threads': len(os.listdir('/proc/self/task'))}))
'''


class TheMasterLoadsAndWarmsTheWebTests(SimpleTestCase):
    """R2-5, in a fresh interpreter under lane F's tripwires: importing cptstudio.wsgi alone - what gunicorn's master
    does, once, before it forks - leaves both URLconfs loaded and compiled, every page template compiled, the static
    manifest, the hasher's library and the password rules loaded, no connection open and no thread but the interpreter's
    own."""

    def warmed(self) -> tuple:
        probe, report = lane_w_probe(WARMED_WEB_STEP)
        self.assertIsNone(probe['error'])
        self.assertIsNotNone(report)
        return probe, report

    def test_both_hosts_urlconfs_are_loaded_and_compiled_before_any_request(self):
        probe, report = self.warmed()
        self.assertEqual(report['resolvers'], [True, True])  # the doctors' host, then the admin host
        self.assertEqual([name for name in ('cptstudio.urls', 'cptstudio.urls_admin') if name in probe['loaded']],
                         ['cptstudio.urls', 'cptstudio.urls_admin'])

    def test_every_page_template_is_compiled_into_the_cache_requests_read(self):
        _, report = self.warmed()
        folder = Path(settings.BASE_DIR) / 'studio' / 'templates'
        expected = sorted(path.relative_to(folder).as_posix() for path in folder.rglob('*.html'))
        self.assertGreater(len(expected), 10)
        self.assertEqual(report['templates'], expected)

    def test_the_manifest_the_hashers_library_and_the_password_rules_are_loaded(self):
        _, report = self.warmed()
        self.assertEqual((report['manifest'], report['argon2'], report['hashers'], report['validators']),
                         (True, True, 1, 1))

    def test_no_connection_is_open_and_no_thread_but_the_interpreters_runs(self):
        probe, report = self.warmed()
        # the kernel's count as well as threading's: a thread started below threading.Thread.start (_thread, or a C
        # library's pthread_create) passes the tripwire and threading.active_count(), and is held at every fork
        self.assertEqual((probe['opened'], probe['started'], probe['threads'], report['os_threads'], report['open']),
                         ([], [], 1, 1, []))


class GunicornHooksTests(SimpleTestCase):
    """R2-5: deploy/gunicorn.conf.py's two hooks."""

    databases = {'default'}

    def test_when_ready_closes_every_connection_and_freezes_the_loaded_objects(self):
        _, report = lane_w_probe(WHEN_READY_STEP, tripwires=False, database=connection.settings_dict['NAME'])
        self.assertIs(report['before']['open'], True)  # the control: a connection was open when the hook ran
        self.assertEqual(report['open'], [])
        self.assertEqual(report['os_threads'], 1)  # and the hook started no thread, of any kind, before the forks
        self.assertGreater(report['frozen'] - report['before']['frozen'], 10_000)

    def test_a_database_that_does_not_answer_never_stops_a_worker_from_starting(self):
        with mock.patch.object(connection, 'ensure_connection', side_effect=OperationalError('synthetic')) as asked:
            gunicorn_settings()['post_worker_init'](mock.Mock())
        asked.assert_called_once_with()


class GunicornSettingsTests(SimpleTestCase):
    """R2-5, R2-6 and R2-8: the release's processes, their class, their recycling, and the bounds that stay."""

    def test_four_sync_processes_without_threads_and_the_bounds_the_installer_is_sized_on(self):
        found = gunicorn_settings()
        self.assertEqual((found['workers'], found['worker_class'], found.get('threads', 1)), (4, 'sync', 1))
        # the installer's drain is sized on the timeout (ops/install.py DRAIN_MIN_SECONDS)
        self.assertEqual((found['timeout'], found['graceful_timeout'], found['keepalive']), (120, 30, 5))

    def test_the_application_is_loaded_once_in_the_master(self):
        self.assertIs(gunicorn_settings()['preload_app'], True)

    def test_a_worker_is_recycled_after_ten_thousand_requests_or_so(self):
        found = gunicorn_settings()
        self.assertEqual((found['max_requests'], found['max_requests_jitter']), (10_000, 1_000))

    def test_the_request_limits_the_heartbeat_folder_and_the_access_line_stay(self):
        found = gunicorn_settings()
        self.assertEqual((found['limit_request_line'], found['limit_request_fields'], found['limit_request_field_size'],
                          found['worker_tmp_dir'], found['accesslog'], found['errorlog']),
                         (4094, 64, 8190, '/dev/shm', '-', '-'))
        self.assertEqual(found['access_log_format'], RELEASE_1_ACCESS_FORMAT)

    def test_reading_the_file_loads_no_django(self):
        # gunicorn reads it before it loads the application: an import of Django here could read the settings before
        # cptstudio.wsgi marks the process as the web's (R2-7)
        done = subprocess.run([sys.executable, '-B', '-c', 'import json, sys\nexec(compile(open(sys.argv[1]).read(), '
                               'sys.argv[1], "exec"), {})\nprint(json.dumps(sorted(name for name in sys.modules if '
                               'name.split(".")[0] == "django")))', str(GUNICORN_CONF)],
                              capture_output=True, timeout=120, check=False)
        self.assertEqual(done.returncode, 0, done.stderr.decode()[-2000:])
        self.assertEqual(json.loads(done.stdout.decode().splitlines()[-1]), [])


class OnlyTheWebKeepsItsConnectionsTests(SimpleTestCase):
    """R2-7: settings.DATABASES as each process reads it, each in a fresh interpreter whose environment has no
    CPT_STUDIO_WEB - as the installer starts every container (ops/test_install_r2web.py) - so the web's own entry point
    is what marks the web."""

    def test_the_web_keeps_its_connection_for_an_hour_and_checks_it(self):
        probe, report = lane_w_probe(WARMED_WEB_STEP)
        self.assertIsNone(probe['error'])
        self.assertEqual((report['kept'], report['connect_timeout'], report['web']), ([3600, True], 5, '1'))

    def test_the_worker_keeps_sixty_seconds_and_no_check(self):
        probe, report = lane_w_probe(WORKER_SETTINGS_STEP)
        self.assertIsNone(probe['error'])
        self.assertIn('studio.management.commands.run_worker', probe['loaded'])
        self.assertEqual((report['kept'], report['connect_timeout'], report['web']), ([60, False], None, None))

    def test_a_management_command_keeps_sixty_seconds_and_no_check(self):
        probe, report = lane_w_probe(COMMAND_SETTINGS_STEP)
        self.assertIsNone(probe['error'])
        self.assertEqual((report['kept'], report['connect_timeout'], report['web']), ([60, False], None, None))


# --- a real gunicorn with the release's settings ---------------------------------------------------------------------

_PR_SET_PDEATHSIG = 1
try:
    _LANE_W_PRCTL = ctypes.CDLL(None, use_errno=True).prctl
except (OSError, AttributeError):  # not Linux: a server is still stopped by its test's own cleanup
    _LANE_W_PRCTL = None


def _stop_with_the_test_process():
    """A test server's preexec_fn: the kernel sends it SIGTERM if the test process ends first (Linux), so no server is
    left holding the test database or a port."""
    if _LANE_W_PRCTL is not None:
        _LANE_W_PRCTL(_PR_SET_PDEATHSIG, int(signal.SIGTERM), 0, 0, 0)


def free_test_port(exclude=()) -> int:
    """A port of GUNICORN_TEST_PORTS that 127.0.0.1 can bind now, in a random order."""
    ports = [port for port in GUNICORN_TEST_PORTS if port not in exclude]
    random.shuffle(ports)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    raise AssertionError('no loopback port of GUNICORN_TEST_PORTS is free')


class ReleaseGunicorn:
    """A real gunicorn: ``config`` (the release's deploy/gunicorn.conf.py unless a test gives another) serving ``app``
    on a free loopback port of GUNICORN_TEST_PORTS, against this run's test database (unless ``environment`` says
    otherwise), with ``options`` after the settings file on gunicorn's command line, which lets them override it. Its
    output - the access and the error log - goes to a file under TMPDIR. Its database sessions carry an application name
    of its own (PGAPPNAME, which the driver's libpq reads), so the database tells them from every other session. It is
    stopped by the process id it was started as, never by a name, and the kernel stops it if the test process dies
    first."""

    def __init__(self, test, *options, config=GUNICORN_CONF, app='cptstudio.wsgi', environment=None, exclude=(),
                 separate=False):
        self.test, self.options, self.config, self.app = test, options, config, app
        self.environment, self.exclude = dict(environment or {}), set(exclude)
        # stdout (gunicorn's access log) and stderr (its error log, and what the application writes there) each in a
        # file of its own, as Docker keeps them apart, instead of one file holding both
        self.separate, self.errlog = separate, None
        self.name = f'lane-w-gunicorn-{uuid.uuid4().hex[:12]}'
        folder = tempfile.TemporaryDirectory(prefix='lane-w-gunicorn-')
        test.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.process = self.port = self.log = None
        test.addCleanup(self.stop)  # runs before the folder's cleanup: cleanups run last in, first out

    def launch(self, attempt):
        self.port = free_test_port(self.exclude)
        self.exclude.add(self.port)
        self.log = self.folder / f'gunicorn-{attempt}.log'
        environment = {name: value for name, value in os.environ.items() if name != 'CPT_STUDIO_WEB'}
        environment.update({'PYTHONDONTWRITEBYTECODE': '1', 'PGAPPNAME': self.name,
                            'DJANGO_SETTINGS_MODULE': 'cptstudio.settings',
                            'CPT_STUDIO_DB_NAME': connection.settings_dict['NAME'], **self.environment})
        self.errlog = self.folder / f'gunicorn-{attempt}.err' if self.separate else None
        errors_to = self.errlog if self.errlog else Path(os.devnull)
        with self.log.open('wb') as output, errors_to.open('wb') as errors:
            self.process = subprocess.Popen(
                [sys.executable, '-B', '-m', 'gunicorn', '-c', str(self.config), '--bind', f'127.0.0.1:{self.port}',
                 *self.options, self.app], cwd=settings.BASE_DIR, env=environment, stdout=output,
                stderr=errors if self.errlog else subprocess.STDOUT, start_new_session=True,
                preexec_fn=_stop_with_the_test_process)

    def start(self, booted=4, timeout=180):
        """Started, with ``booted`` workers booted; a port taken between its check and the bind is left for another."""
        for attempt in range(4):
            self.launch(attempt)
            deadline = time.monotonic() + timeout
            while self.process.poll() is None and time.monotonic() < deadline:
                if self.text().count('Booting worker with pid: ') >= booted:
                    return self
                time.sleep(0.05)
            if self.process.poll() is None:
                self.test.fail(f'gunicorn did not boot {booted} workers in {timeout} s: {self.text()[-3000:]}')
            if 'Connection in use' not in self.text():
                self.test.fail(f'gunicorn exited ({self.process.returncode}): {self.text()[-3000:]}')
        self.test.fail('no loopback port could be bound')

    def run_to_exit(self, timeout=180) -> int:
        """Started and waited for: a server that cannot start ends itself; its exit code."""
        self.launch(0)
        try:
            return self.process.wait(timeout)
        except subprocess.TimeoutExpired:
            self.test.fail(f'gunicorn did not end in {timeout} s: {self.text()[-3000:]}')

    def stop(self, timeout=60):
        """SIGTERM to the master this test started, as Docker stops the web; its exit code. Then none of its database
        sessions is left."""
        if self.process is None:
            return None
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)  # its group: the master this test started and its workers
                self.process.wait(timeout)
        self.until_sessions(0)
        return self.process.returncode

    def text(self) -> str:
        """All its output, both streams."""
        return ''.join(self.streams())

    def streams(self) -> tuple:
        """(stdout, stderr) as written; with the streams not kept apart, everything is in the first."""
        def read(path):
            return path.read_text(encoding='utf-8', errors='replace') if path else ''
        return read(self.log), read(self.errlog)

    def until_text(self, needle, timeout=60) -> str:
        deadline = time.monotonic() + timeout
        while needle not in self.text():
            if time.monotonic() > deadline:
                self.test.fail(f'{needle!r} never appeared: {self.text()[-3000:]}')
            time.sleep(0.05)
        return self.text()

    def workers(self) -> list:
        """The process ids of this master's workers that are alive now, in their boot order."""
        alive = []
        for pid in map(int, re.findall(r'Booting worker with pid: (\d+)', self.text())):
            try:
                stat = Path(f'/proc/{pid}/stat').read_text()
            except OSError:
                continue
            fields = stat[stat.rindex(')') + 2:].split()
            if fields[0] not in ('Z', 'X') and int(fields[1]) == self.process.pid:
                alive.append(pid)
        return alive

    def sessions(self) -> list:
        """The process ids of the database sessions this server holds (by its application name), in order."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT pid FROM pg_stat_activity WHERE application_name = %s ORDER BY pid', [self.name])
            return [row[0] for row in cursor.fetchall()]

    def until_sessions(self, count, timeout=60) -> list:
        deadline = time.monotonic() + timeout
        found = self.sessions()
        while len(found) != count and time.monotonic() < deadline:
            time.sleep(0.05)
            found = self.sessions()
        return found

    def get(self, path='/health/') -> int:
        client = http.client.HTTPConnection('127.0.0.1', self.port, timeout=60)
        try:
            client.request('GET', path, headers={'Host': 'localhost'})
            response = client.getresponse()
            response.read()
            return response.status
        finally:
            client.close()

    def many(self, clients, each, path='/health/') -> list:
        """``clients`` threads at once, each sending ``each`` requests one after another: every answer's status (an
        error's class name for a request that got none)."""
        answers, lock = [], threading.Lock()

        def run():
            for _ in range(each):
                try:
                    status = self.get(path)
                except (OSError, http.client.HTTPException) as error:
                    status = type(error).__name__
                with lock:
                    answers.append(status)
        threads = [threading.Thread(target=run, name=f'lane-w-client-{index}') for index in range(clients)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return answers


class RealGunicornTests(SimpleTestCase):
    """The release's own settings file, served by a real gunicorn on a loopback port (ReleaseGunicorn): four sync
    workers forked from a master that preloaded and warmed the application, against this run's test database."""

    databases = {'default'}

    def assertAllAnswered(self, answers, count, status=200):
        self.assertEqual((len(answers), sorted({str(answer) for answer in answers})), (count, [str(status)]))

    def test_four_workers_forked_from_a_warmed_master_each_open_their_own_connection_before_any_request(self):
        server = ReleaseGunicorn(self).start()
        # four sessions, one per worker: a connection the master held at the fork would be shared instead (then one)
        self.assertEqual(len(server.until_sessions(4)), 4)
        self.assertEqual(len(server.workers()), 4)
        self.assertNotIn(' HTTP/1.1" ', server.text())  # and no request was made
        # the master loaded the application before its first fork: the hasher's library, which only the warm-up loads,
        # is mapped in the master's own memory (a master that does not preload never imports Django)
        self.assertIn('_argon2_cffi_bindings', Path(f'/proc/{server.process.pid}/maps').read_text())
        # one thread each, by the kernel's count: the master forks its first four workers from a single thread, and no
        # worker starts one (a thread in the master at a fork leaves its locks held, with no owner, in the worker); the
        # recycling test below counts the master again after its replacements' forks
        self.assertEqual([len(os.listdir(f'/proc/{pid}/task')) for pid in (server.process.pid, *server.workers())],
                         [1] * 5)
        self.assertEqual(server.stop(), 0)

    def test_the_workers_keep_their_connections_and_replace_one_the_database_ended_without_an_error(self):
        server = ReleaseGunicorn(self).start()
        first = server.until_sessions(4)
        self.assertEqual(len(first), 4)
        self.assertAllAnswered(server.many(8, 4), 32)
        self.assertEqual(server.sessions(), first)  # the same four connections, kept across the requests
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FILTER (WHERE pg_terminate_backend(pid)) FROM pg_stat_activity '
                           'WHERE application_name = %s', [server.name])
            self.assertEqual(cursor.fetchone()[0], 4)
        self.assertEqual(server.until_sessions(0), [])  # the database ended all four
        self.assertAllAnswered(server.many(8, 4), 32)  # every request answered, none an error
        again = server.sessions()
        self.assertTrue(1 <= len(again) <= 4 and not set(again) & set(first), (first, again))
        self.assertEqual(server.stop(), 0)

    def test_every_request_is_answered_while_the_workers_are_recycled(self):
        server = ReleaseGunicorn(self, '--max-requests', '15', '--max-requests-jitter', '3').start()
        self.assertAllAnswered(server.many(8, 40), 320)
        self.assertGreaterEqual(server.text().count('Autorestarting worker after current request.'), 10)
        self.assertEqual(len(server.until_sessions(4)), 4)  # each replacement opened its own; none was left behind
        # every replacement is a fork of this master (R2-8): after the recycles it still holds one thread by the
        # kernel's count, as at boot (a thread it started after its first forks would be held at each later fork;
        # refutation round 2). An end-of-run sample: a master thread that ended before it is not seen
        self.assertEqual(len(os.listdir(f'/proc/{server.process.pid}/task')), 1)
        self.assertEqual(server.stop(), 0)

    def test_the_workers_start_and_answer_when_the_database_does_not(self):
        closed = free_test_port()  # nothing listens there, so the database's connection is refused at once
        unreachable = {'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': str(closed)}
        server = ReleaseGunicorn(self, environment=unreachable, exclude={closed}).start()
        self.assertAllAnswered(server.many(4, 2), 8, status=503)  # /health/ reports the database, and nothing hangs
        self.assertEqual(len(server.workers()), 4)
        self.assertNotIn('exited with code', server.text())
        self.assertEqual(server.stop(), 0)

    def test_the_workers_answer_soon_when_the_database_accepts_and_never_answers(self):
        # a socket that listens and never accepts: the kernel completes each connection and nothing ever answers, as a
        # hung database does. The web's own connect timeout (settings.DATABASES) ends every wait for it - each worker's
        # connection at its start, which gunicorn never times out, and each request's - so /health/ reports the
        # database long before gunicorn's or nginx's timeouts
        silent = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(silent.close)
        for port in random.sample(list(GUNICORN_TEST_PORTS), len(GUNICORN_TEST_PORTS)):
            try:
                silent.bind(('127.0.0.1', port))
                break
            except OSError:
                continue
        else:  # never listen() unbound: the kernel would bind every interface (refutation round 2)
            self.fail('no loopback port of GUNICORN_TEST_PORTS is free')
        silent.listen(16)
        port = silent.getsockname()[1]
        hung = {'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': str(port)}
        server = ReleaseGunicorn(self, environment=hung, exclude={port}).start()
        started = time.monotonic()
        self.assertAllAnswered(server.many(4, 1), 4, status=503)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(server.stop(), 0)

    def test_a_database_lost_while_requests_run_or_restarted_answers_503_never_500(self):
        # integrated refutation round 1, avail-0 (I1-15; studio.db_unavailable): a member signed in at a real web, four
        # clients reading the API's session, list, document and view at once. The database ends the web's connections
        # five times while requests run, then refuses every connection for 2.5 s, as a restart does - faults made on the
        # database itself, on this run's own test database and this web's own sessions (its application name) alone.
        # Every answer is 200 or 503 (Django's HTML 500 before), a 503 the API's fail-closed JSON with Retry-After, and
        # the web answers 200 again once the database does
        from studio import client_contract, read_audit
        from studio.models import Membership
        from tests.support import coding as f
        ws = f.workspace('Synthetic restart practice')
        member = f.member(ws, role=Membership.OWNER)
        document = f.encounter(ws, member, title='Synthetic restart note')
        f.upload(document, member)
        server = ReleaseGunicorn(self).start()
        self.assertEqual(len(server.until_sessions(4)), 4)

        def call(method, path, body=None, headers=None):
            client = http.client.HTTPConnection('127.0.0.1', server.port, timeout=60)
            try:
                client.request(method, path, body=body, headers={'Host': 'localhost', **(headers or {})})
                answer = client.getresponse()
                return answer.status, dict(answer.getheaders()), answer.read()
            finally:
                client.close()
        _, headers, _ = call('GET', '/login/')
        csrf = re.search(r'cptstudio_csrf=([^;]+)', headers['Set-Cookie']).group(1)
        form = urllib.parse.urlencode({'username': member.get_username(), 'password': 'synthetic-pass-123!',
                                       'csrfmiddlewaretoken': csrf})
        status, headers, _ = call('POST', '/login/', form, {'Content-Type': 'application/x-www-form-urlencoded',
                                                             'Cookie': f'cptstudio_csrf={csrf}'})
        self.assertEqual(status, 302)
        cookie = f"cptstudio_session={re.search(r'cptstudio_session=([^;]+)', headers['Set-Cookie']).group(1)}"
        asked = {'Cookie': cookie, client_contract.HEADER: client_contract.VERSION}
        paths = ('/api/session', '/api/encounters', f'/api/encounters/{document.pk}',
                 f'/api/encounters/{document.pk}/original?view=1')
        self.assertEqual([call('GET', path, headers=asked)[0] for path in paths], [200, 200, 200, 200])
        answers, lock, running = [], threading.Lock(), threading.Event()
        running.set()

        def client_loop(index):
            turn = index
            while running.is_set():
                path = paths[turn % len(paths)]
                turn += 1
                try:
                    status, headers, body = call('GET', path, headers=asked)
                except (OSError, http.client.HTTPException) as error:
                    status, headers, body = type(error).__name__, {}, b''
                with lock:
                    answers.append((time.monotonic(), path, status, headers.get('Content-Type', ''),
                                    headers.get('Retry-After', ''), body))
        clients = [threading.Thread(target=client_loop, args=(index,), name=f'lane-w-db-client-{index}', daemon=True)
                   for index in range(4)]
        # the restart is made from a session of the server's own maintenance database: PostgreSQL refuses to close a
        # database to new connections from a session of that database
        import psycopg
        conf = connection.settings_dict
        name = connection.ops.quote_name(conf['NAME'])
        maintenance = psycopg.connect(host=conf['HOST'], port=conf['PORT'], user=conf['USER'],
                                      password=conf['PASSWORD'], dbname='postgres', autocommit=True)
        self.addCleanup(maintenance.close)

        def end_the_webs_connections():
            with connection.cursor() as cursor:
                cursor.execute('SELECT count(*) FILTER (WHERE pg_terminate_backend(pid)) FROM pg_stat_activity '
                               'WHERE application_name = %s', [server.name])
        outage = back = None
        for client in clients:
            client.start()
        try:
            time.sleep(0.5)
            for _ in range(5):  # ended while requests run
                end_the_webs_connections()
                time.sleep(0.3)
            maintenance.execute(f'ALTER DATABASE {name} ALLOW_CONNECTIONS false')  # a restart: refused for 2.5 s
            outage = time.monotonic()
            end_the_webs_connections()
            time.sleep(2.5)
        finally:
            maintenance.execute(f'ALTER DATABASE {name} ALLOW_CONNECTIONS true')
            back = time.monotonic()
            time.sleep(1.5)
            running.clear()
            for client in clients:
                client.join(60)
        statuses = sorted({str(answer[2]) for answer in answers})
        self.assertEqual(statuses, ['200', '503'], f'{len(answers)} answers')
        in_the_outage = [answer for answer in answers if outage + 0.2 < answer[0] < back]
        self.assertTrue(in_the_outage and all(answer[2] == 503 for answer in in_the_outage),
                        [answer[:3] for answer in in_the_outage][:12])
        # a 503 is the lost database's (studio.db_unavailable: Retry-After), or the read record's own fail-closed answer
        # when the loss lands on the record's write (studio.api._recorded, as before): the same JSON, no PDF byte
        kinds = {'Retry-After': 0, 'the record\'s own': 0}
        for _, path, status, kind, retry, body in answers:
            if status == 503:
                self.assertIn(retry, ('5', ''), path)
                self.assertEqual((kind, json.loads(body)),
                                 ('application/json', {'error': read_audit.NOT_RECORDED, 'details': {}}), path)
                self.assertNotIn(b'%PDF', body)
                kinds['Retry-After' if retry else 'the record\'s own'] += 1
        self.assertTrue(all(answer[4] == '5' for answer in in_the_outage), 'the outage: the lost database\'s 503 alone')
        self.assertEqual([call('GET', path, headers=asked)[0] for path in paths], [200, 200, 200, 200])
        print(f'{LANE_W_REPORT}I1-15 answers {len(answers)}: '
              f'{json.dumps({key: sum(1 for answer in answers if str(answer[2]) == key) for key in statuses})}; '
              f'in the outage {len(in_the_outage)} (503); 503 kinds {json.dumps(kinds)}', flush=True)
        self.assertEqual(server.stop(), 0)


def docker_stamped(text: str, first: int = 0) -> bytes:
    """``text`` as `docker logs --timestamps` gives one stream of it: each line Docker read - it splits at a line feed
    only - after a time of its own, in order from ``first`` nanoseconds."""
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(f'2026-11-26T10:00:00.{first + index:09d}Z {line}' for index, line in enumerate(lines)).encode()


@functools.cache
def lane_w_installer():
    """ops/install.py, loaded from this tree as a module of its own, or None in a tree without ops/ (the image ships
    without it)."""
    path = Path(settings.BASE_DIR) / 'ops' / 'install.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('lane_w_install', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# gunicorn's own error-log line (its glogging format): the time, the process id, the level, the message
GUNICORN_LINE = re.compile(r'\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}\] \[\d+\] \[[A-Z]+\] (?P<message>.*)')
# gunicorn's access line, in the release's format (RELEASE_1_ACCESS_FORMAT): it starts with the request's time
ACCESS_LINE = re.compile(r'\[\d\d/[A-Z][a-z]{2}/\d{4}:\d\d:\d\d:\d\d [+-]\d{4}\] ')
# The one message of gunicorn's that is not a life-cycle fact: the head of a crashed worker's traceback, whose lines can
# carry an error's text and are dropped with it; what the arbiter then writes - the exit code and the reason - is kept
CRASH_REPORT = 'Exception in worker process'
# Every life-cycle shape the installer's kept pattern names, each of which the runs below must write (their control)
LIFE_CYCLE_SHAPES = (r'Starting gunicorn [\d.]+$', r'Listening at: http://0\.0\.0\.0:8000 \(\d+\)$',
                     'Using worker: sync$', r'Booting worker with pid: \d+$', r'Handling signal: term$',
                     r'Worker exiting \(pid: \d+\)$', 'Shutting down: Master$',
                     r'Worker \(pid:\d+\) was sent SIGKILL! Perhaps out of memory\?$',
                     r'WORKER TIMEOUT \(pid:\d+\)$', r'Autorestarting worker after current request\.$',
                     r'Worker \(pid:\d+\) exited with code 1$', r'Worker \(pid:\d+\) exited with code 1\.$',
                     r'Worker \(pid:\d+\) exited with code 3$', r'Reason: Worker failed to boot\.$',
                     r'Worker \(pid:\d+\) exited with code 4$', r'Reason: App failed to load\.$')
# The one line release 2's web writes when its application cannot load (cptstudio/wsgi.py): gunicorn's master loads it
# before gunicorn writes a line of its own (preload_app), so without it such a web's output keeps nothing
WEB_LOAD_FAILED = 'CPT Studio web: the application could not be loaded.'


class TheInstallerKeepsARealRunsLifeCycleTests(SimpleTestCase):
    """R2-9's acceptance: every life-cycle line real runs of the release's settings write is one the installer keeps
    (ops/install.py ids_only_lines over KEPT_LOG_FORMATS['web'], as keep_container_log reads a web's output), and no
    line of another shape is kept. The runs, with the release's settings file: of four workers one killed as the kernel
    kills for memory and one aborted, then all of them recycled, then stopped as Docker stops a web; a worker that
    stopped answering, timed out. Two more, each a settings file that is the release's own with one change: a worker
    that fails to boot (the release's own post_worker_init swallows every failure, so only a changed hook can), and an
    earlier revision's web, which loads the application in each worker (preload_app off), that cannot load it - the
    only web that writes 'Reason: App failed to load.'. And release 2's own web, its settings file unchanged, when its
    application cannot load in gunicorn's master: the settings refuse their environment, or the warm-up fails."""

    databases = {'default'}

    def wrapped_settings(self, after: str) -> Path:
        folder = tempfile.TemporaryDirectory(prefix='lane-w-settings-')
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'gunicorn.conf.py'
        path.write_text(f'exec(compile(open({str(GUNICORN_CONF)!r}).read(), {str(GUNICORN_CONF)!r}, "exec"))\n{after}',
                        encoding='utf-8')
        return path

    def killed_aborted_and_recycled(self) -> tuple:
        server = ReleaseGunicorn(self, '--max-requests', '6', '--max-requests-jitter', '0', separate=True).start()
        # every worker has opened its connection, so each has its signal handlers, and none is being recycled: no
        # request has been made yet
        self.assertEqual(len(server.until_sessions(4)), 4)
        killed, aborted = server.workers()[:2]
        os.kill(killed, signal.SIGKILL)  # a worker of the master this test started
        server.until_text(f'Worker (pid:{killed}) was sent SIGKILL!')
        os.kill(aborted, signal.SIGABRT)
        server.until_text(f'Worker (pid:{aborted}) exited with code 1.')
        answers = server.many(4, 8)  # then the workers are recycled
        self.assertEqual((len(answers), set(answers)), (32, {200}))
        self.assertEqual(server.stop(), 0)
        return server.streams()

    def timed_out(self) -> tuple:
        # a timeout well above the idle heartbeat (half of it), so a loaded host never times out a worker this test has
        # not stopped
        server = ReleaseGunicorn(self, '--workers', '1', '--timeout', '6', separate=True).start(booted=1)
        hung, = server.workers()
        # it has answered, so its heartbeat runs (gunicorn 23 times a worker out only after its first heartbeat)
        self.assertEqual(server.get(), 200)
        os.kill(hung, signal.SIGSTOP)  # it stops answering its master, as a request that hangs does
        server.until_text(f'Worker (pid:{hung}) was sent SIGKILL!')
        self.assertIn(f'WORKER TIMEOUT (pid:{hung})', server.text())
        self.assertEqual(server.stop(), 0)
        return server.streams()

    def failed_to_boot(self) -> tuple:
        server = ReleaseGunicorn(self, config=self.wrapped_settings(
            'workers = 1\n\n\ndef post_worker_init(worker):\n    raise RuntimeError("a worker that cannot start")\n'),
            separate=True)
        self.assertEqual(server.run_to_exit(), 3)
        return server.streams()

    def failed_to_load(self) -> tuple:
        server = ReleaseGunicorn(self, config=self.wrapped_settings('workers = 1\npreload_app = False\n'),
                                 app='cptstudio.wsgi:lane_w_no_such_application', separate=True)
        self.assertEqual(server.run_to_exit(), 4)
        return server.streams()

    def test_every_life_cycle_line_of_real_runs_is_kept_and_no_line_of_another_shape(self):
        install = lane_w_installer()
        if install is None:
            self.skipTest('this tree has no ops/install.py (the image ships without ops/)')
        runs = [self.killed_aborted_and_recycled(), self.timed_out(), self.failed_to_boot(), self.failed_to_load()]
        # each run's stdout and stderr as Docker keeps them, apart, each line with a time of its own (the run, then the
        # stream, then the line): every line of a kept shape, whichever stream the run wrote it to, must be kept - so a
        # life-cycle line written to stdout, where it is never kept (installer-0), fails this test
        streams, bodies, expected = ([], []), [], []
        for run, pair in enumerate(runs):
            for stream, text in enumerate(pair):
                lines = text.split('\n')
                if lines and lines[-1] == '':
                    lines.pop()
                for number, line in enumerate(lines):
                    # the container binds 0.0.0.0:8000 (the settings file's own bind), which the kept pattern names;
                    # these runs bind a loopback port
                    body = re.sub(r'Listening at: http://127\.0\.0\.1:\d+ \(', 'Listening at: http://0.0.0.0:8000 (', line)
                    stamp = f'2026-11-26T10:{run:02d}:{stream:02d}.{number:09d}Z'
                    streams[stream].append(f'{stamp} {body}')
                    bodies.append(body)
                    message = GUNICORN_LINE.fullmatch(body)
                    if (message and message['message'] != CRASH_REPORT) or ACCESS_LINE.match(body):
                        expected.append((stamp, body))
        kept, dropped = install.ids_only_lines('web', *('\n'.join(lines).encode() for lines in streams))
        self.assertEqual([line.split(' ', 1)[1] for line in kept], [body for _, body in sorted(expected)])
        self.assertEqual(dropped, len(bodies) - len(expected))
        expected = [body for _, body in sorted(expected)]
        messages = [GUNICORN_LINE.fullmatch(body)['message'] for body in expected if GUNICORN_LINE.fullmatch(body)]
        for shape in LIFE_CYCLE_SHAPES:
            with self.subTest(shape=shape):
                self.assertTrue([message for message in messages if re.match(shape, message)])
        self.assertTrue([body for body in expected
                         if ACCESS_LINE.match(body) and '"GET /health/ HTTP/1.1" 200 ' in body])
        self.assertTrue([body for body in bodies if body not in expected])  # and the runs wrote lines that are dropped

    def release_web_that_cannot_load(self, environment) -> tuple:
        """(stdout, stderr) of the release's settings file unchanged, whose application fails in gunicorn's master
        (preload_app) before gunicorn writes a line: gunicorn exits 1."""
        server = ReleaseGunicorn(self, environment=environment, separate=True)
        self.assertEqual(server.run_to_exit(timeout=60), 1)  # it exits within seconds; one that serves never does
        return server.streams()

    def test_release_2s_web_that_cannot_load_its_application_keeps_one_fixed_line(self):
        install = lane_w_installer()
        if install is None:
            self.skipTest('this tree has no ops/install.py (the image ships without ops/)')
        shadow = tempfile.TemporaryDirectory(prefix='lane-w-argon2-')
        self.addCleanup(shadow.cleanup)
        (Path(shadow.name) / 'argon2.py').write_text("raise ImportError('lane W test: no hasher library')\n",
                                                    encoding='utf-8')
        # and one that raises Exception itself, of no narrower class: a catch narrowed to the classes of the runs above
        # would pass them and keep nothing here (cptstudio/wsgi.py catches Exception; refutation round 2)
        other = tempfile.TemporaryDirectory(prefix='lane-w-argon2-')
        self.addCleanup(other.cleanup)
        (Path(other.name) / 'argon2.py').write_text("raise Exception('lane W test: the warm-up cannot load')\n",
                                                   encoding='utf-8')
        runs = {
            # the settings refuse their environment (a relative state folder), inside get_wsgi_application
            'settings refused': {'CPT_STUDIO_STATE_DIR': 'relative/state'},
            # the warm-up fails after the application is built: its 'import argon2' finds a module that raises
            'warm-up failed': {'PYTHONPATH': shadow.name},
            # any other exception the load raises
            'warm-up failed, any exception': {'PYTHONPATH': other.name},
        }
        for what, environment in runs.items():
            with self.subTest(what=what):
                out, err = self.release_web_that_cannot_load(environment)
                streams = (docker_stamped(out), docker_stamped(err, 10 ** 6))  # Docker keeps stdout and stderr apart
                kept, dropped = install.ids_only_lines('web', *streams)
                # exactly the one fixed line, from stderr - never the error's text, which gunicorn or the traceback
                # writes after it
                self.assertEqual([line.split(' ', 1)[1] for line in kept], [WEB_LOAD_FAILED])
                self.assertIn(WEB_LOAD_FAILED, err.split('\n'))
                self.assertEqual(dropped, sum(len(stream.decode().splitlines()) for stream in streams) - 1)
                self.assertGreater(dropped, 0)

    def test_a_request_cannot_write_a_kept_line_into_a_serving_webs_kept_log(self):
        # gunicorn's access log, on stdout, writes a request's path decoded and unescaped: a line feed (%0A) starts a
        # line of the request's own after Docker's own time, and a carriage return, a file separator or a line
        # separator (%0D, %1C, %E2%80%A8) - a line break to str.splitlines, none to Docker - one after a time the request
        # chose. The fixed line (refutation round 2) and, since integrated refutation round 1 (installer-0), every line
        # of the web but its access lines are kept from stderr alone, and a kept line is one Docker entry: so neither
        # the fixed line nor a life-cycle line (a memory kill, a worker boot, a boot failure, free text after a signal)
        # nor a django.request line a request writes is kept, and every real line still is.
        install = lane_w_installer()
        if install is None:
            self.skipTest('this tree has no ops/install.py (the image ships without ops/)')
        forged = [WEB_LOAD_FAILED,
                  '[2026-11-26 10:00:01 +0000] [1] [ERROR] Worker (pid:21) was sent SIGKILL! Perhaps out of memory?',
                  '[2026-11-26 10:00:01 +0000] [1] [INFO] Booting worker with pid: 4242',
                  '[2026-11-26 10:00:01 +0000] [1] [ERROR] Reason: Worker failed to boot.',
                  '[2026-11-26 10:00:01 +0000] [1] [ERROR] Worker (pid:21) exited with code 3',
                  '[2026-11-26 10:00:01 +0000] [1] [INFO] Handling signal: janedoe19570412',
                  'Not Found: /login']
        chosen = '2026-11-26T09:00:00.000000000Z '  # before the web started
        server = ReleaseGunicorn(self, separate=True).start()
        for line in forged:
            quoted, stamped = urllib.parse.quote(line, safe=''), urllib.parse.quote(chosen + line, safe='')
            for path in (f'/x%0A{quoted}%0Ay', *(f'/x{cut}{stamped}{cut}y' for cut in ('%0D', '%1C', '%E2%80%A8'))):
                with self.subTest(path=path):
                    self.assertTrue(400 <= server.get(path) < 500)
        self.assertEqual(server.stop(), 0)
        out, err = server.streams()
        stdout, stderr = docker_stamped(out), docker_stamped(err, 10 ** 6)

        def kept(*streams):
            return [line.split(' ', 1)[1] for line in install.ids_only_lines('web', *streams)[0]]
        # the control: the %0A requests did write each line, alone in a Docker entry of its own, into stdout - read as
        # stderr, each is kept once
        control = kept(b'', stdout)
        self.assertEqual([control.count(line) for line in forged], [1] * len(forged))
        shown = install.ids_only_lines('web', stdout, stderr)[0]
        for line in forged:
            with self.subTest(forged=line):
                self.assertNotIn(line, [kept_line.split(' ', 1)[1] for kept_line in shown])
        self.assertFalse([line for line in shown if line.startswith(chosen.strip())])  # no time the requests chose
        # and every real line is: the four workers' boot, from stderr, and the server's own life cycle
        bodies = [line.split(' ', 1)[1] for line in shown]
        self.assertEqual(sum('Booting worker with pid: ' in body for body in bodies), 4)
        self.assertEqual(sum(bool(re.search(r'\] Starting gunicorn [\d.]+$', body)) for body in bodies), 1)
        self.assertEqual(sum(bool(re.search(r'\] Shutting down: Master$', body)) for body in bodies), 1)
        # the real boot lines as gunicorn wrote them to stderr (Django's escaped 'Not Found:' lines of the forging
        # requests carry the words too, as text inside one line, never as a line of their own)
        booted = [line for line in err.split('\n') if (message := GUNICORN_LINE.fullmatch(line))
                  and message['message'].startswith('Booting worker with pid: ')]
        self.assertEqual(len(booted), 4)
