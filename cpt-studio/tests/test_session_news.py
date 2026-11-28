"""Integrated refutation round 1, I1-13 (session-0): the pages outside the app tell this browser's app tabs they were
reached (studio/static/studio/session_news.js), so the ends made there wipe every app tab's page memory (R2-18).

"Sign out everywhere" on the account page (the app links to it), and another member's sign-in that lands there (a
password that must change), were ends no app tab heard: login.html and account_security.html carried no script, so
another tab kept release 2's kept copies, its hints and the worker made ready ahead until its next input or its idle
deadline. Both pages now load session_news.js with defer (the site's policy, script-src 'self'); the account page names
its session in data-session, as the app's shell does. The script posts on the app's own channel at load and when the
everywhere form is sent, in the shapes app.js already acts on (tests/frontend/app.test.cjs: the I1-13 node tests).

SessionNewsBrowserTests drives the live application in Chromium (tests/frontend/session_news_browser.cjs): its own
templates, sessions and policy, its static files collected with the manifest storage the image builds with and served
by WhiteNoise in its own middleware. It is skipped where node or Playwright is not installed, the reason beginning
'no Playwright at' (as ops/test_viewer_speed.cjs's). CPT_STUDIO_LIVE_PORTS ('first-last') keeps the live server to a
range of ports, else the system gives one. Synthetic data only; nothing beyond 127.0.0.1.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.test import Client, LiveServerTestCase, TestCase, override_settings
from django.utils import timezone

from studio import models
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC

ROOT = Path(settings.BASE_DIR)
PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
SCRIPT = '<script defer src="/static/studio/session_news.js"></script>'
DRIVER = ROOT / 'tests' / 'frontend' / 'session_news_browser.cjs'
SESSION_TAG = re.compile(r'<body class="login-body" data-session="([0-9a-f-]*)">')


def signed_in(user):
    client = Client()
    answer = client.post('/login/', {'username': user.get_username(), 'password': PASSWORD})
    assert answer.status_code == 302, answer.status_code
    return client


@override_settings(STORAGES=PLAIN_STATIC)
class SessionNewsPagesTests(TestCase):
    """Both pages load the script with defer; the account page names the session its request is in, the sign-in page
    none - the tag the app's shell and the session ping give the same session."""

    def setUp(self):
        self.ws = f.workspace()
        self.member = f.member(self.ws)

    def tag_of(self, client):
        return client.post('/session/activity', HTTP_X_CPT_POLL='1').json()['session']

    def test_the_sign_in_page_loads_the_script_and_names_no_session(self):
        page = Client().get('/login/').content.decode()
        self.assertEqual(page.count(SCRIPT), 1)
        self.assertIn('<body class="login-body">', page)
        self.assertNotIn('data-session', page)

    def test_the_account_page_loads_the_script_and_names_its_own_session(self):
        client = signed_in(self.member)
        page = client.get('/account/').content.decode()
        self.assertEqual(page.count(SCRIPT), 1)
        self.assertEqual(page.count('id="everywhereForm"'), 1)  # the form the script tells the tabs about
        tag = SESSION_TAG.search(page)
        self.assertIsNotNone(tag)
        self.assertRegex(tag.group(1), r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        self.assertEqual(tag.group(1), self.tag_of(client), 'the tag the ping gives the same session')
        shell = client.get('/').content.decode()
        self.assertIn(f'data-session="{tag.group(1)}"', shell, 'the tag the app\'s shell carries')
        # another sign-in of the same account is another session, with another tag
        other = signed_in(self.member)
        self.assertNotEqual(SESSION_TAG.search(other.get('/account/').content.decode()).group(1), tag.group(1))

    def test_a_forced_password_change_lands_on_an_account_page_that_names_that_session(self):
        forced = f.member(self.ws)
        models.User.objects.filter(pk=forced.pk).update(password_change_required_at=timezone.now())
        client = Client()
        landed = client.post('/login/', {'username': forced.get_username(), 'password': PASSWORD}, follow=True)
        self.assertEqual(landed.redirect_chain[-1][0], '/account/?required=1')
        page = landed.content.decode()
        self.assertEqual(page.count(SCRIPT), 1)
        self.assertEqual(SESSION_TAG.search(page).group(1), self.tag_of(client))

    def test_the_script_is_plain_and_self_contained(self):
        source = (ROOT / 'studio' / 'static' / 'studio' / 'session_news.js').read_text(encoding='utf-8')
        for unsafe in ('eval(', 'new Function', 'innerHTML', 'document.write', 'insertAdjacentHTML', 'fetch(', 'http'):
            self.assertNotIn(unsafe, source)
        self.assertIn("'cpt-studio-session'", source)  # app.js SESSION_CHANNEL
        app = (ROOT / 'studio' / 'static' / 'studio' / 'app.js').read_text(encoding='utf-8')
        self.assertIn("const SESSION_CHANNEL = 'cpt-studio-session';", app)


class _TheSiteItself(WSGIHandler):
    """The live server's static files served by the site itself - WhiteNoise in its middleware, under its own headers -
    as deployed, not by the test server's own static handler."""

    def __init__(self, application):
        super().__init__()


def _playwright() -> str:
    return os.environ.get('CPT_VERIFY_PLAYWRIGHT') or '/opt/meddoc-pro/node_modules/playwright'  # as ops/walk.cjs reads it


def _live_port() -> int:
    """The first free port of CPT_STUDIO_LIVE_PORTS ('first-last'), else 0 (the system gives one)."""
    asked = re.fullmatch(r'(\d+)-(\d+)', os.environ.get('CPT_STUDIO_LIVE_PORTS', ''))
    if not asked:
        return 0
    for port in range(int(asked.group(1)), int(asked.group(2)) + 1):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    raise RuntimeError(f'no free port in {asked.group(0)}')


class SessionNewsBrowserTests(LiveServerTestCase):
    """In Chromium: an app tab with a PDF open, its copy kept and a worker waiting, given no input, while another tab
    of the same browser is outside the app (tests/frontend/session_news_browser.cjs)."""

    host = '127.0.0.1'
    static_handler = _TheSiteItself

    @classmethod
    def setUpClass(cls):
        if shutil.which('node') is None:
            raise unittest.SkipTest('no Playwright at any path: node is not installed')
        if not (Path(_playwright()) / 'package.json').exists():
            raise unittest.SkipTest(f'no Playwright at {_playwright()}')
        cls.port = _live_port()
        cls._tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        root = Path(cls._tmp.name)
        cls._settings = override_settings(STATIC_ROOT=root / 'static', ORIGINALS_DIR=root / 'originals')
        cls._settings.enable()
        call_command('collectstatic', interactive=False, verbosity=0)  # the manifest storage, as the image is built
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._settings.disable()
        cls._tmp.cleanup()

    def synthetic_pdf(self) -> bytes:
        """A two-page synthetic PDF the viewer can draw (the dev preview's own maker)."""
        made = subprocess.run(
            ['node', '-e', "process.stdout.write(require(process.argv[1]).syntheticPdf([['SYNTHETIC TEST DOCUMENT - "
             "FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Session news check (fictional).'], ['Page two (fictional).']]))",
             str(ROOT / 'ops' / 'dev_preview_server.cjs')], capture_output=True, timeout=60, check=True)
        self.assertTrue(made.stdout.startswith(b'%PDF-'))
        return made.stdout

    def run_driver(self, document, member, other, *experiments):
        env = {**os.environ, 'SESSION_NEWS_MEMBER': member.get_username(), 'SESSION_NEWS_OTHER': other.get_username(),
               'SESSION_NEWS_PASSWORD': PASSWORD}
        done = subprocess.run(['node', str(DRIVER), self.live_server_url, str(document.pk), *experiments], cwd=ROOT,
                              env=env, capture_output=True, text=True, timeout=600, check=False)
        lines = done.stdout.splitlines()
        self.assertIn('DONE', lines, done.stdout[-3000:] + done.stderr[-3000:])
        return {line.split(' ', 2)[1]: json.loads(line.split(' ', 2)[2]) for line in lines if line.startswith('RESULT ')}

    def test_every_end_made_outside_the_app_wipes_an_app_tab_given_no_input(self):
        ws = f.workspace('Synthetic session news practice')
        member = f.member(ws)
        other = f.member(ws)  # another member of the practice, whose password must change
        models.User.objects.filter(pk=other.pk).update(password_change_required_at=timezone.now())
        document = f.encounter(ws, member, title='Synthetic session news note')
        f.upload(document, member, data=self.synthetic_pdf(), filename='synthetic-session-news.pdf')
        r.write_round(document)
        found = self.run_driver(document, member, other)
        print(f'SESSION-NEWS {json.dumps(found, sort_keys=True)}', flush=True)
        wiped = {'copies': 1, 'zeroed': True, 'kept': 0, 'hints': 0, 'waited': True, 'waiting': False}

        # the control: the account page of the tab's own session, then the sign-in page while still signed in - the tab
        # asks the server once (the sign-in page names no session), stays, and keeps everything
        own = found['own-account']
        kept = {'url': f'/#doc/{document.pk}', 'kept': 1, 'waiting': True, 'gone': False}
        self.assertEqual((own['after_account']['reports'], own['after_account']['pings'], own['after_account']['tab']),
                         (0, [], kept), 'its own session\'s account page: nothing asked, nothing wiped')
        self.assertEqual((own['after_login']['reports'], own['after_login']['pings'], own['after_login']['tab']),
                         (0, ['1'], kept))
        self.assertEqual(own['session'], 200)

        # "Sign out everywhere": the tab of that session leaves at once, before asking anything, wiped
        everywhere = found['everywhere']
        self.assertIsNotNone(everywhere['report'], 'sign out everywhere: the app tab was not wiped')
        self.assertEqual({key: everywhere['report'][key] for key in wiped}, wiped)
        self.assertEqual(everywhere['pings_before_wipe'], 0, 'it heard its own session signed out: no question asked')
        self.assertLess(everywhere['wiped_ms'], 10000)
        self.assertEqual((everywhere['two'], everywhere['one'], everywhere['session']), ('/login/', '/login/', 401))

        # another member whose password must change signs in there: the tab asks, meets their session, is wiped
        other_member = found['other-member']
        self.assertEqual(other_member['after_login']['reports'], 0)
        self.assertEqual(other_member['two'], '/account/?required=1')
        self.assertIsNotNone(other_member['report'], 'another member\'s sign-in: the app tab was not wiped')
        self.assertEqual({key: other_member['report'][key] for key in wiped}, wiped)

        # the sessions ended with no page of this browser's: nothing heard; then the sign-in page: asked, 401, wiped
        elsewhere = found['ended-elsewhere']
        self.assertEqual((elsewhere['ended'], elsewhere['session']), (302, 401))
        self.assertEqual((elsewhere['before_login']['reports'], elsewhere['before_login']['tab']['kept']), (0, 1))
        self.assertIsNotNone(elsewhere['report'], 'the sign-in page after an end elsewhere: the app tab was not wiped')
        self.assertEqual({key: elsewhere['report'][key] for key in wiped}, wiped)

        for name, result in found.items():
            self.assertEqual(result['errors'], [], name)
