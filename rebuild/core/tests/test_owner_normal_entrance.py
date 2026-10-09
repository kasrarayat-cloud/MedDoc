"""Fresh normal HTTPS browsers use the actual private gate; isolated test DB."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

from core.models import AuditEvent
from core import preview_access as preview
from core.tests.test_preview_access import SETTINGS, GATE_USER, GATE_PASSWORD

EDGE = {'HTTP_HOST': 'app.quillmd.com', 'HTTP_X_QUILLMD_PREVIEW': '1', 'secure': True}


@override_settings(**SETTINGS, QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=True)
class OwnerNormalEntranceTests(TestCase):
    def get(self, path='/', client=None, **extra):
        return (client or self.client).get(path, **{**EDGE, **extra})

    def start(self, path='/', client=None):
        response = self.get(path, client=client)
        self.assertEqual(response.status_code, 302)
        location = urlsplit(response['Location'])
        self.assertEqual(location.path, preview.SIGN_IN)
        self.assertFalse(location.netloc)
        flow = parse_qs(location.query)['flow'][0]
        self.assertRegex(flow, r'^[a-f0-9]{32}$')
        return flow

    def post(self, path, data, client=None, **extra):
        return (client or self.client).post(path, data, **{**EDGE, **extra})

    def login(self, flow, client=None):
        return self.post(preview.SIGN_IN, {'username': GATE_USER, 'password': GATE_PASSWORD,
                                         'flow': flow}, client=client)

    def test_fresh_doctor_and_admin_browser_reach_same_origin_signin_only(self):
        for destination in ('/', '/console/services/', '/login/'):
            browser = Client()
            flow = self.start(destination, browser)
            page = self.get(preview.SIGN_IN + '?flow=' + flow, browser)
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, 'name="password"')
            self.assertContains(page, 'name="csrfmiddlewaretoken"')
            self.assertNotContains(page, 'Workspace health')
            self.assertNotContains(page, 'Your reviewed answers')
            key = browser.cookies[preview.COOKIE].value
            self.assertNotIn('grant', SessionStore(session_key=key))
            admitted = self.login(flow, browser)
            self.assertEqual(admitted['Location'], destination)
            self.assertNotEqual(browser.cookies[preview.COOKIE].value, key)
            app = self.get(destination, browser)
            if destination == '/login/':
                self.assertEqual(app.status_code, 200)
                self.assertContains(app, 'name="password"')
            else:
                self.assertEqual(app.status_code, 302)
                self.assertEqual(urlsplit(app['Location']).path, '/login/')

    def test_unknown_or_expired_grants_can_signin_again_without_replaying_writes(self):
        self.client.cookies[preview.COOKIE] = 'a' * 32
        flow = self.start('/encounters/synthetic-record/')
        self.assertEqual(self.get(preview.SIGN_IN + '?flow=' + flow).status_code, 200)
        store = SessionStore(session_key=self.client.cookies[preview.COOKIE].value)
        self.assertNotIn('grant', store)
        key = self.client.cookies[preview.COOKIE].value
        response = self.post('/encounters/synthetic-record/finalize/', {'reviewed': 'on'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.cookies[preview.COOKIE].value, key)
        self.assertNotIn('grant', SessionStore(session_key=key))

    def test_api_and_mutations_without_grants_create_no_access_sessions(self):
        for method, path, extra in [('get', '/api/patients/', {}),
                                    ('get', '/', {'HTTP_ACCEPT': 'application/json'}),
                                    ('post', '/login/', {}),
                                    ('post', '/encounters/new/', {}),
                                    ('delete', '/templates/synthetic/', {})]:
            browser = Client()
            before = Session.objects.count()
            response = getattr(browser, method)(path, **{**EDGE, **extra})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(Session.objects.count(), before)
            self.assertNotIn(preview.COOKIE, browser.cookies)

    def test_normal_gate_retains_real_csrf_and_same_origin_requirement(self):
        browser = Client(enforce_csrf_checks=True)
        flow = self.start('/console/services/', browser)
        self.get(preview.SIGN_IN + '?flow=' + flow, browser)
        fields = {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': flow}
        self.assertEqual(self.post(preview.SIGN_IN, fields, browser).status_code, 403)
        from django.conf import settings
        fields['csrfmiddlewaretoken'] = browser.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(self.post(preview.SIGN_IN, fields, browser,
                                  HTTP_ORIGIN='https://outside.invalid').status_code, 403)
        admitted = self.post(preview.SIGN_IN, fields, browser, HTTP_ORIGIN='https://app.quillmd.com')
        self.assertEqual(admitted.status_code, 302)
        cookie = admitted.cookies[preview.COOKIE]
        self.assertTrue(cookie['secure']); self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax'); self.assertFalse(cookie['domain'])

    def test_credentials_and_browser_bound_flow_are_still_required(self):
        flow = self.start('/invite/synthetic-owner-capability/')
        page = self.get(preview.SIGN_IN + '?flow=' + flow)
        self.assertNotContains(page, 'synthetic-owner-capability')
        self.assertEqual(self.login(flow, Client()).status_code, 400)
        failed = self.post(preview.SIGN_IN, {'username': GATE_USER,
                           'password': 'synthetic-wrong-value', 'flow': flow})
        self.assertEqual(failed.status_code, 200)
        store = SessionStore(session_key=self.client.cookies[preview.COOKIE].value)
        self.assertNotIn('grant', store)
        self.assertEqual(AuditEvent.objects.filter(action='preview.login_failed').count(), 1)
        self.assertEqual(self.login(flow)['Location'], '/invite/synthetic-owner-capability/')

    def test_disabled_wrong_host_tls_or_marker_do_not_expose_entrance(self):
        for changes in ({'HTTP_HOST': 'app.quillmd.com:443'},
                        {'HTTP_X_QUILLMD_PREVIEW': ''}, {'secure': False}):
            response = self.get(preview.SIGN_IN, **changes)
            self.assertEqual(response.status_code, 503)
        with override_settings(QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=False):
            self.assertEqual(self.get(preview.SIGN_IN).status_code, 503)
        with patch.object(preview, 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', False):
            self.assertEqual(self.get(preview.SIGN_IN).status_code, 503)

    def test_head_entrance_has_same_flow_without_exposing_application(self):
        response = self.client.head('/', **EDGE)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response['Location']).path, preview.SIGN_IN)
        self.assertFalse(response.content)
