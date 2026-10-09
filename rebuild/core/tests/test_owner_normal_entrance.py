"""Fresh and stale-cookie browsers reach only ordinary account sign-in."""
from urllib.parse import urlsplit
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from core.models import AuditEvent
from core import preview_access as preview
from core.tests.test_preview_access import SETTINGS, EDGE


@override_settings(**SETTINGS)
class OwnerNormalEntranceTests(TestCase):
    def get(self, path='/', client=None, **extra):
        return (client or self.client).get(path, **{**EDGE, **extra})

    def test_fresh_doctor_admin_and_legacy_links_reach_account_login_without_grant_session(self):
        for destination in ('/', '/console/services/', '/login/', '/preview/sign-in/?flow=' + 'f' * 32):
            browser = Client()
            before = Session.objects.count()
            response = self.get(destination, browser)
            if destination != '/login/':
                self.assertIn(response.status_code, (302, 303))
                self.assertEqual(urlsplit(response['Location']).path, '/login/')
                response = self.get(response['Location'], browser)
            self.assertContains(response, 'name="email"')
            self.assertContains(response, 'name="password"')
            for forbidden in ('Private preview', 'name="flow"', 'name="username"'):
                self.assertNotContains(response, forbidden)
            self.assertNotIn(preview.COOKIE, browser.cookies)
            self.assertEqual(Session.objects.count(), before)
            self.assertFalse(AuditEvent.objects.filter(action__startswith='preview.').exists())

    def test_unknown_preview_cookie_cannot_authorize_protected_route(self):
        for cookie in ('a' * 32, 'unknown', 'A' * 32):
            browser = Client()
            browser.cookies[preview.COOKIE] = cookie
            response = self.get('/encounters/synthetic-record/', browser)
            self.assertEqual(urlsplit(response['Location']).path, '/login/')
            self.assertEqual(response.cookies[preview.COOKIE]['max-age'], 0)
            self.assertEqual(self.get('/login/', browser).status_code, 200)
            self.assertNotIn('_auth_user_id', browser.session)

    def test_head_entrance_redirects_to_account_login_and_has_no_body(self):
        response = self.client.head('/', **EDGE)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response['Location']).path, '/login/')
        self.assertFalse(response.content)
