"""Core repair (2026-11-03), decision (l): the customer page's client contract (studio/client_contract.py). A customer API
call that does not name the current page build - a tab left open on the previous release - is answered 409
client_outdated before the view runs; a download (a browser navigation) and the operator's API are outside it; every
copy of the value (the server's, the page's, the tools') is the same one."""
from __future__ import annotations

import importlib.util
import re
import uuid
from pathlib import Path

from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from studio import client_contract
from tests.support import factories as f

ROOT = Path(__file__).resolve().parents[1]


def without_contract(client):
    client.defaults.pop(client_contract.WSGI_KEY, None)
    return client


class ContractTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))

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

    def test_sign_in_is_asked_first(self):
        self.assertEqual(without_contract(Client()).get('/api/session').status_code, 401)

    def test_a_download_is_a_navigation_and_outside_the_contract(self):
        client = without_contract(self.signed_in())
        # the views run (and answer their own 404 for a report or document that is not there), never 409
        self.assertEqual(client.get(f'/api/reports/{uuid.uuid4()}/download').status_code, 404)
        self.assertEqual(client.get(f'/api/encounters/{uuid.uuid4()}/original').status_code, 404)

    def test_the_operator_api_is_outside_the_contract(self):
        # a member who is no operator is answered the operator gate's 404, never the contract's 409
        self.assertEqual(without_contract(self.signed_in()).get('/ops/api/session').status_code, 404)


class OneValueTests(SimpleTestCase):
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
        walk = (ROOT / 'ops' / 'verify_browser.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADERS = {{ '{client_contract.HEADER}': '{client_contract.VERSION}' }};", walk)
        # every direct customer API call the walk makes names it (downloads and the page's own assets excepted)
        for match in re.finditer(r"request\.(?:get|post)\(`\$\{(?:ctx\.)?base\}(/api/[^`]*)`[^\n]*", walk):
            with self.subTest(match.group(1)):
                self.assertIn('CLIENT_HEADERS', match.group(0))
