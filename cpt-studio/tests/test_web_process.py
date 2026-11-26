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
connection (Django's and the driver's own) and record a thread start without starting it; a control in the same probe
proves that both trip.
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)

# The probe: tripwires first, then the step (argv[1]), then one line of JSON. Nothing in it reaches a database or the
# network: a connection attempt is refused before any socket opens.
PROBE = r'''
import json, sys, threading

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
    'loaded': [name for name in MARKERS if name in sys.modules],
    'ai': sorted(name for name in sys.modules if name.split('.')[0] in SDK or name == 'studio.fable.client'),
}))
'''

SETUP = '''
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cptstudio.settings')
import django
django.setup()
'''
# What the web loads: the WSGI application, then both hosts' URLconfs as a first request resolves them (and as R2-5's
# warm-up does in the master).
WEB = '''
import cptstudio.wsgi
from django.conf import settings
from django.urls import get_resolver
from studio import hosts
for urlconf in (settings.ROOT_URLCONF, hosts.ADMIN_URLCONF):
    get_resolver(urlconf).reverse_dict
'''
JOBS = SETUP + 'import studio.jobs\n'
WORKER = SETUP + 'import studio.management.commands.run_worker\n'
# The control: after the web, a connection asked of Django, one asked of the driver, and a thread - each must trip.
CONTROL = WEB + '''
import threading
import psycopg
from django.db import connection
for attempt in (connection.ensure_connection, lambda: psycopg.connect('')):
    try:
        attempt()
    except RuntimeError:
        pass
threading.Thread(target=print, name='lane-f-control').start()
'''
THE_WEB = ('cptstudio.wsgi', 'cptstudio.urls', 'cptstudio.urls_admin', 'studio.api', 'studio.jobs')


@functools.cache
def probe(step: str) -> dict:
    """The report of a fresh interpreter that ran ``step`` under the tripwires."""
    done = subprocess.run([sys.executable, '-B', '-c', PROBE, step], cwd=ROOT, env=dict(os.environ),
                          capture_output=True, timeout=300)
    reports = [line for line in done.stdout.decode().splitlines() if line.startswith('PROBE ')]
    if done.returncode != 0 or len(reports) != 1:
        raise AssertionError(f'the probe did not report (exit {done.returncode}): {done.stderr.decode()[-3000:]}')
    return json.loads(reports[0][len('PROBE '):])


class TheWebLoadsNoAiLibraryTests(SimpleTestCase):
    def test_the_web_holds_no_ai_library(self):
        web = probe(WEB)
        self.assertIsNone(web['error'])
        # the web was loaded, studio.jobs with it (studio.api imports it), so the absence below is the web's
        self.assertEqual([name for name in THE_WEB if name in web['loaded']], list(THE_WEB))
        self.assertEqual(web['ai'], [])

    def test_importing_the_jobs_module_leaves_the_sender_unloaded(self):
        jobs = probe(JOBS)
        self.assertIsNone(jobs['error'])
        self.assertIn('studio.jobs', jobs['loaded'])
        self.assertEqual(jobs['ai'], [])

    def test_the_worker_loads_the_sender_and_its_sdk_at_its_start(self):
        worker = probe(WORKER)
        self.assertIsNone(worker['error'])
        for name in ('studio.management.commands.run_worker', 'studio.fable.client', 'anthropic'):
            with self.subTest(name=name):
                self.assertIn(name, worker['loaded'])


class NothingHappensAtImportTests(SimpleTestCase):
    """Specification 2.4's two import rules, held for everything the web loads."""

    def test_the_web_opens_no_database_connection_at_import(self):
        web = probe(WEB)
        self.assertIsNone(web['error'])
        self.assertEqual(web['opened'], [])

    def test_the_web_starts_no_thread_at_import(self):
        web = probe(WEB)
        self.assertIsNone(web['error'])
        self.assertEqual(web['started'], [])
        self.assertEqual(web['threads'], 1)

    def test_the_probe_sees_a_connection_and_a_thread(self):
        # the positive control: the same tripwires, after the same import, catch each kind of act
        control = probe(CONTROL)
        self.assertIsNone(control['error'])
        self.assertEqual(control['opened'], ['django:default', 'psycopg'])
        self.assertEqual(control['started'], ['lane-f-control'])
