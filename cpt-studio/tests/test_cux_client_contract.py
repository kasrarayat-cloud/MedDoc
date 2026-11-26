"""Core repair (2026-11-03), decision (l): the customer page's client contract (studio/client_contract.py). A customer API
call that does not name the current page build - a tab left open on the previous release - is answered 409
client_outdated before the view runs; a download (a browser navigation) and the operator console are outside it; every
copy of the value (the server's, the page's app.js, ops/verify_login.py's and the walk's, ops/walk.cjs, and the contract
file the tools read, ops/verification/customer-contract.json) is the same one.

The fix pass's line identity (FIX-SPEC section 1) made the build customer-2026-11-21; the second fix pass (FIX-SPEC-2
section 5) made the build of 2026-11-22: an Undo names the decision it undoes and a download names the round shown, so
a page of the build before it would post an Undo the server refuses and a download that names no round. Its copies
landed in two lanes - the server's and the contract file's (G1), the page's and the tools' (G2) - so in a tree holding
only some of them OneValueTests failed, naming the copy that differed, until both were merged. Release 1
(RELEASE-1-SPEC 3.6) made it the build of 2026-11-24, every copy in one commit, so a tab opened before its install was
told to reload instead of meeting the new API. Release 2 (RELEASE-2-SPEC R2-24 and section 7, D-R2-3) makes it
customer-2026-11-26, every copy in one commit: release 1's page would read a page of a list as the whole list, so it is
told to reload on every list call, and release 1's build is named nowhere in this tree but here, where it is refused
(the old value left in one copy fails that test)."""
from __future__ import annotations

import importlib.util
import os
import re
import uuid
from pathlib import Path

from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from studio import client_contract
from tests.support import coding as f

ROOT = Path(__file__).resolve().parents[1]
# release 2 (RELEASE-2-SPEC R2-24, D-R2-3): the build every copy names
CURRENT_BUILD = 'customer-2026-11-26'
# release 1's build (RELEASE-1-SPEC 3.6): what a page left open across release 2's switch sends. This module is the only
# file of the tree that names it (OneValueTests.test_the_build_before_this_one_is_named_nowhere_else).
RELEASE_1_BUILD = 'customer-2026-11-24'
# A later page's cursor as a list's `next` gives it (RELEASE-2-SPEC R2-19: the console's format, a UTC time to the
# microsecond and an id, studio.console.CURSOR_RE)
LATER_PAGE_CURSOR = '20261126T101500.123456Z~0b7f3a52-9c1e-4d2a-8f61-2a9e5d0c4b17'
# Generated or installed trees inside cpt-studio/ that are not the tree's own files
NOT_THE_TREES_OWN_FILES = {'.git', '__pycache__', 'node_modules', 'staticfiles', '.venv', 'venv'}
# RELEASE-2-SPEC section 7: every file that holds a copy of the value
VERSION_COPIES = ('studio/client_contract.py', 'studio/static/studio/app.js', 'ops/verify_login.py', 'ops/walk.cjs',
          'ops/scan_customer.py', 'ops/verification/customer-contract.json', 'tests/test_frontend.py',
          'tests/test_api_customer.py', 'tests/test_stale_actions.py', 'tests/frontend/app.test.cjs',
          'ops/test_verify_login.py', 'ops/test_walk.cjs', 'ops/verification/test_contract_v2.py', 'API.md',
          'CORE-UX-DESIGN.md', 'ops/INSTALL.md', 'studio/api.py', 'studio/customer.py', 'ops/dev_preview_server.cjs')


def without_contract(client):
    client.defaults.pop(client_contract.WSGI_KEY, None)
    return client


class ContractTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws)

    def signed_in(self, **defaults):
        client = Client(**defaults)
        client.force_login(self.reviewer)
        return client

    def test_the_current_page_build_is_served(self):
        self.assertEqual(self.signed_in().get('/api/session').status_code, 200)

    def test_a_call_naming_no_build_or_another_is_told_to_reload(self):
        for client in (without_contract(self.signed_in()),
                       self.signed_in(**{client_contract.WSGI_KEY: 'customer-2026-10-23'}),
                       self.signed_in(**{client_contract.WSGI_KEY: ''})):
            for method, path in (('get', '/api/session'), ('get', '/api/encounters'),
                                 ('post', '/api/encounters')):
                with self.subTest(path=path, header=client.defaults.get(client_contract.WSGI_KEY)):
                    response = getattr(client, method)(path)
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json(), client_contract.OUTDATED)

    def test_release_1_s_page_is_told_to_reload_on_every_list_call(self):
        # R2-24: release 1's page would read a page of a list as the whole list, so whatever list it asks for - any
        # list, a later page - is answered 409 before the view runs, and reads nothing (the search is lane S's route)
        client = self.signed_in(**{client_contract.WSGI_KEY: RELEASE_1_BUILD})
        for path in ('/api/session', '/api/encounters', '/api/encounters?list=documents', '/api/encounters?list=queue',
                     '/api/encounters?list=recent', f'/api/encounters?list=documents&before={LATER_PAGE_CURSOR}'):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual((response.status_code, response.json()), (409, client_contract.OUTDATED))

    def test_sign_in_is_asked_first(self):
        self.assertEqual(without_contract(Client()).get('/api/session').status_code, 401)

    def test_a_download_is_a_navigation_and_outside_the_contract(self):
        client = without_contract(self.signed_in())
        # the views run (and answer their own 404 for a report or document that is not there), never 409
        self.assertEqual(client.get(f'/api/reports/{uuid.uuid4()}/download').status_code, 404)
        self.assertEqual(client.get(f'/api/encounters/{uuid.uuid4()}/original').status_code, 404)

    def test_the_operator_console_is_outside_the_contract(self):
        # a member who is no operator is answered the operator gate's 404, never the contract's 409
        self.assertEqual(without_contract(self.signed_in()).get('/ops/').status_code, 404)


class OneValueTests(SimpleTestCase):
    def test_the_build_is_the_second_fix_pass_build(self):
        self.assertEqual(client_contract.VERSION, CURRENT_BUILD)

    def test_the_test_package_acts_as_the_current_page(self):
        self.assertEqual(Client().defaults[client_contract.WSGI_KEY], client_contract.VERSION)
        self.assertEqual(RequestFactory().defaults[client_contract.WSGI_KEY], client_contract.VERSION)
        self.assertEqual(client_contract.WSGI_KEY, 'HTTP_X_CPT_STUDIO_CLIENT')

    def test_every_copy_is_the_server_s(self):
        app = (ROOT / 'studio' / 'static' / 'studio' / 'app.js').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADER = '{client_contract.HEADER}';", app)
        self.assertIn(f"const CLIENT_VERSION = '{client_contract.VERSION}';", app)
        self.assertRegex(app, r"\[CLIENT_HEADER\]: CLIENT_VERSION")  # api() sends it on every call
        spec = importlib.util.spec_from_file_location('cux_contract_verify_login', ROOT / 'ops' / 'verify_login.py')
        login = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(login)
        self.assertEqual((login.CLIENT_HEADER, login.CLIENT_VERSION), (client_contract.HEADER, client_contract.VERSION))
        walk = (ROOT / 'ops' / 'walk.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADERS = {{ '{client_contract.HEADER}': '{client_contract.VERSION}' }};", walk)
        contract = (ROOT / 'ops' / 'verification' / 'customer-contract.json').read_text(encoding='utf-8')
        self.assertIn(client_contract.VERSION, contract)  # the contract the scanner and the walk read names its build
        # every direct customer API call the walk makes names it: its JSON reader (getJson, which every polled read goes
        # through) and each call written with an /api/ path (downloads and the page's own assets excepted)
        reader = re.search(r'async function getJson\(page, ctx, where\) \{\n[^\n]*request\.get\([^\n]*', walk)
        self.assertIsNotNone(reader)
        self.assertIn('...CLIENT_HEADERS', reader.group(0))
        direct = list(re.finditer(r'request\.(?:get|post)\(`[^`]*(/api/[^`]*)`[^\n]*', walk))
        self.assertTrue(direct)
        for match in direct:
            with self.subTest(match.group(1)):
                self.assertIn('CLIENT_HEADERS', match.group(0))

    def test_every_copy_the_release_lists_names_this_build(self):
        # RELEASE-2-SPEC section 7's table, file by file: the server, the page, the tools, the tests and the documents
        # (the image ships no ops/: deploy/.dockerignore)
        shipped_ops = (ROOT / 'ops').is_dir()
        for name in VERSION_COPIES:
            if name.startswith('ops/') and not shipped_ops:
                continue
            with self.subTest(copy=name):
                self.assertIn(client_contract.VERSION, (ROOT / name).read_text(encoding='utf-8'))

    def test_the_build_before_this_one_is_named_nowhere_else(self):
        # one value everywhere (R2-24): a copy left at release 1's value - in code, a test or a document - fails here;
        # a sentence about release 1 names its build by date ("the build of 2026-11-24"), as release 1 did for its own
        here = Path(__file__).resolve()
        needle = RELEASE_1_BUILD.encode('ascii')
        found, seen = [], set()
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(name for name in dirs if name not in NOT_THE_TREES_OWN_FILES)
            for name in files:
                path = Path(folder) / name
                seen.add(path.relative_to(ROOT).as_posix())
                if path.resolve() != here and needle in path.read_bytes():
                    found.append(path.relative_to(ROOT).as_posix())
        # the walk read the tree (the page and the server among it), so an empty list is the tree's
        self.assertLessEqual({'studio/static/studio/app.js', 'studio/client_contract.py', 'API.md'}, seen)
        self.assertEqual(found, [])
