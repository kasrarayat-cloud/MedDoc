"""Private preview boundary tests; isolated database and synthetic values only."""
import re
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.models import AuditEvent, User
from core.preview_access import ABSOLUTE_SECONDS, COOKIE, FLOW_SECONDS, IDLE_SECONDS, KIND, safe_destination


GATE_USER = 'synthetic-preview'
GATE_PASSWORD = 'Synthetic-preview-only-8492!'
SETTINGS = {
    'ADMIN_SITE': False,
    'QUILLMD_PREVIEW_AUTH_ENABLED': True,
    'QUILLMD_PREVIEW_ORIGIN': 'https://app.quillmd.com:9443',
    'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com:9443',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': GATE_USER,
    'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': GATE_PASSWORD,
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    'STORAGES': {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
}
EDGE = {'HTTP_HOST': 'app.quillmd.com:9443', 'HTTP_X_QUILLMD_PREVIEW': '1', 'secure': True}


class SafePreviewDestinationTests(SimpleTestCase):
    def test_only_local_application_locations_can_resume(self):
        for path in ('/', '/invite/synthetic-token/', '/recovery/confirm/abc/123-xyz/', '/encounters/abc/?tab=coding', '/patients/?q=Synthetic%20Patient'):
            with self.subTest(path=path):
                self.assertTrue(safe_destination(path))
        for path in ('https://outside.invalid/', '//outside.invalid/', '/\\outside.invalid/',
                     '/%5coutside.invalid/', '/%2foutside.invalid/', '/%252foutside.invalid/',
                     '/https%3aoutside.invalid/', '/%0aSet-Cookie:bad', '/%250dnext',
                     '/a/../b', '/%2e%2e/b', '/foo#fragment', '/foo bar', '/foo\x7f',
                     '/foo%C2%85', '/foo\u0085', '/foo%zz', '/foo%20bar', '/patients/?q=raw space',
                     '/' + 'x' * 2048, '/%252525252foutside.invalid/'):
            with self.subTest(path=path):
                self.assertFalse(safe_destination(path))


@override_settings(**SETTINGS)
class PreviewAccessTests(TestCase):
    def get(self, path, client=None, **extra):
        return (client or self.client).get(path, **{**EDGE, **extra})

    def post(self, path, data, client=None, **extra):
        return (client or self.client).post(path, data, **{**EDGE, **extra})

    def start(self, path='/health/', client=None):
        response = self.get(path, client=client)
        self.assertEqual(response.status_code, 302)
        parsed = urlsplit(response['Location'])
        self.assertEqual(parsed.path, '/preview/sign-in/')
        handle = parse_qs(parsed.query)['flow'][0]
        self.assertRegex(handle, r'^[a-f0-9]{32}$')
        return handle

    def login(self, flow='', client=None):
        return self.post('/preview/sign-in/', {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': flow}, client=client)

    def store(self, client=None):
        return SessionStore(session_key=(client or self.client).cookies[COOKIE].value)

    def test_original_capability_is_server_side_and_resumes_after_form_login(self):
        destination = '/invite/synthetic-capability-original/'
        handle = self.start(destination)
        original_key = self.client.cookies[COOKIE].value
        page = self.get('/preview/sign-in/?flow=' + handle)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'synthetic-capability-original')
        self.assertNotContains(page, destination)
        self.assertContains(page, 'name="flow"')
        response = self.login(handle)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], destination)
        self.assertNotEqual(self.client.cookies[COOKIE].value, original_key)
        self.assertFalse(Session.objects.filter(session_key=original_key).exists())
        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/')
        self.assertFalse(cookie['domain'])
        self.assertEqual(self.get('/health/').status_code, 200)
        # Gate access grants no individual application session.
        self.assertNotIn('quillmd_doctor_session', self.client.cookies)
        self.assertEqual(self.get('/').status_code, 302)
        audit = str(list(AuditEvent.objects.values('action', 'target', 'details')))
        for secret in (GATE_USER, GATE_PASSWORD, destination, handle, original_key):
            self.assertNotIn(secret, audit)

    def test_tabs_keep_distinct_destinations_and_used_handle_cannot_repeat(self):
        first = self.start('/invite/synthetic-first/')
        second = self.start('/recovery/confirm/synthetic/second/')
        self.assertNotEqual(first, second)
        self.assertEqual(self.login(second)['Location'], '/recovery/confirm/synthetic/second/')
        self.assertEqual(self.login(first)['Location'], '/invite/synthetic-first/')
        self.assertEqual(self.login(first).status_code, 400)

    def test_flow_is_bound_to_original_preview_cookie(self):
        handle = self.start('/invite/synthetic-bound/')
        stranger = Client()
        response = self.login(handle, client=stranger)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('grant', self.store(stranger))

    def test_pending_flows_are_bounded_and_expire(self):
        handles = [self.start('/invite/synthetic-' + str(i) + '/') for i in range(9)]
        self.assertEqual(len(self.store()['flows']), 8)
        self.assertEqual(self.login(handles[0]).status_code, 400)
        store = self.store()
        pending = store['flows']
        pending[handles[-1]]['created'] -= FLOW_SECONDS + 1
        store['flows'] = pending
        store.save()
        self.assertEqual(self.login(handles[-1]).status_code, 400)

    def test_wrong_credentials_do_not_create_grant_and_do_not_reflect_password(self):
        handle = self.start()
        response = self.post('/preview/sign-in/', {'username': GATE_USER, 'password': 'synthetic-wrong-value', 'flow': handle})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'username or password is incorrect')
        self.assertNotContains(response, 'synthetic-wrong-value')
        self.assertNotIn('grant', self.store())
        self.assertEqual(AuditEvent.objects.filter(action='preview.login_failed').count(), 1)

    def test_signin_and_error_pages_preserve_origin_only_referrers_for_browser_forms(self):
        handle = self.start('/invite/synthetic-referrer-capability/')
        responses = (
            self.get('/preview/sign-in/?flow=' + handle),
            self.post('/preview/sign-in/', {'username': GATE_USER, 'password': 'synthetic-wrong-value', 'flow': handle}),
            self.get('/preview/sign-in/?flow=' + '0' * 32),
        )
        for response in responses:
            self.assertEqual(response['Referrer-Policy'], 'strict-origin')
            self.assertNotContains(response, 'synthetic-referrer-capability', status_code=response.status_code)

    def test_actual_atomic_rate_limit_refuses_ninth_attempt_and_separates_verified_client_ips(self):
        handle = self.start()
        for _ in range(8):
            response = self.post('/preview/sign-in/', {'username': GATE_USER, 'password': 'synthetic-wrong-value', 'flow': handle}, HTTP_X_REAL_IP='192.0.2.1')
            self.assertEqual(response.status_code, 200)
        response = self.post('/preview/sign-in/', {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': handle}, HTTP_X_REAL_IP='192.0.2.1')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '600')
        self.assertNotIn('grant', self.store())
        response = self.post('/preview/sign-in/', {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': handle}, HTTP_X_REAL_IP='192.0.2.2')
        self.assertEqual(response.status_code, 302)

    def test_credential_rotation_idle_and_absolute_expiry_revoke_gate_only(self):
        self.login()
        with override_settings(QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD='Rotated-synthetic-only-12345!'):
            self.assertEqual(self.get('/health/').status_code, 302)
        self.login()
        for field, age in (('seen', IDLE_SECONDS + 1), ('issued', ABSOLUTE_SECONDS + 1)):
            store = self.store()
            grant = store['grant']; grant[field] -= age; store['grant'] = grant; store.save()
            self.assertEqual(self.get('/health/').status_code, 302)
            self.login()

    def test_marker_host_tls_and_disabled_gate_fail_closed(self):
        for extra in ({'HTTP_X_QUILLMD_PREVIEW': ''}, {'HTTP_HOST': 'localhost:9130'},
                      {'HTTP_HOST': 'app.quillmd.com'}, {'secure': False}):
            with self.subTest(extra=extra):
                self.assertEqual(self.get('/health/', **extra).status_code, 403)
        self.assertEqual(self.client.get('/health/', HTTP_HOST='app.quillmd.com:9443', secure=True).status_code, 403)
        with override_settings(QUILLMD_PREVIEW_AUTH_ENABLED=False):
            self.assertEqual(self.get('/health/').status_code, 503)
            # Rollback restores the independent Basic edge before disabling this
            # form gate; that edge has no form marker and retains app behavior.
            self.assertEqual(self.client.get('/health/', HTTP_HOST='app.quillmd.com:9443', secure=True).status_code, 200)

    def test_loopback_behavior_is_unchanged_and_preview_routes_do_not_work_there(self):
        self.assertEqual(self.client.get('/health/', HTTP_HOST='127.0.0.1:9130').status_code, 200)
        self.assertEqual(self.client.get('/preview/sign-in/', HTTP_HOST='127.0.0.1:9130').status_code, 403)
        with override_settings(ADMIN_SITE=True):
            self.assertEqual(self.client.get('/health/', HTTP_HOST='127.0.0.1:9131').status_code, 200)
            self.assertEqual(self.get('/health/').status_code, 503)

    def test_api_files_webhook_and_unsafe_requests_cannot_skip_gate(self):
        response = self.get('/api/patients/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'private_preview_access_required')
        self.assertEqual(self.post('/billing/webhook/', {}).status_code, 403)
        self.assertEqual(self.post('/recovery/', {'email': 'synthetic-only@invalid.example'}).status_code, 403)
        response = self.get('/templates/00000000-0000-0000-0000-000000000001/original/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.get('/static/app.js').status_code, 302)

    def test_copied_account_cookie_is_not_modified_or_deleted_by_preview_login_logout(self):
        user = User.objects.create_user(username='synthetic-account', email='synthetic-account@example.invalid', verified_at=timezone.now())
        self.client.force_login(user)
        app_key = self.client.cookies['quillmd_doctor_session'].value
        original = Session.objects.get(pk=app_key).session_data
        self.client.cookies[COOKIE] = app_key
        self.login()
        self.assertNotEqual(self.client.cookies[COOKIE].value, app_key)
        self.assertEqual(Session.objects.get(pk=app_key).session_data, original)
        response = self.post('/preview/sign-out/', {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.cookies['quillmd_doctor_session'].value, app_key)
        self.assertEqual(Session.objects.get(pk=app_key).session_data, original)

    def test_logout_invalidates_copied_preview_cookie(self):
        self.login()
        copied = self.client.cookies[COOKIE].value
        self.assertEqual(self.post('/preview/sign-out/', {}).status_code, 302)
        self.client.cookies[COOKIE] = copied
        self.assertEqual(self.get('/health/').status_code, 302)

    def test_csrf_is_real_and_wrong_origin_or_missing_token_is_refused(self):
        checked = Client(enforce_csrf_checks=True)
        handle = self.start(client=checked)
        page = self.get('/preview/sign-in/?flow=' + handle, client=checked)
        token = re.search(r'name="csrfmiddlewaretoken" value="([A-Za-z0-9]+)"', page.content.decode()).group(1)
        data = {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': handle}
        response = self.post('/preview/sign-in/', data, client=checked, HTTP_ORIGIN='https://app.quillmd.com:9443')
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'This form expired', status_code=403)
        response = self.post('/preview/sign-in/', {**data, 'csrfmiddlewaretoken': token}, client=checked, HTTP_ORIGIN='https://outside.invalid')
        self.assertEqual(response.status_code, 403)
        response = self.post('/preview/sign-in/', {**data, 'csrfmiddlewaretoken': token}, client=checked, HTTP_ORIGIN='https://app.quillmd.com:9443')
        self.assertEqual(response.status_code, 302)

    def test_expired_or_unknown_invitation_is_friendly_but_still_404(self):
        self.login()
        response = self.get('/invite/used-or-expired-synthetic-token/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Invitation link unavailable', status_code=404)
        self.assertContains(response, 'Account sign-in', status_code=404)

    def test_csrf_warning_does_not_log_original_capability(self):
        self.login()
        checked = Client(enforce_csrf_checks=True)
        checked.cookies = self.client.cookies.copy()
        with self.assertLogs('django.security.csrf', level='WARNING') as captured:
            response = self.post('/invite/synthetic-secret-capability-not-for-logs/', {}, client=checked)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('synthetic-secret-capability-not-for-logs', '\n'.join(captured.output))
        self.assertIsNone(captured.records[0].request)
        self.assertIsNone(captured.records[0].exc_info)

    def test_csrf_retry_preserves_only_the_bound_opaque_flow(self):
        checked = Client(enforce_csrf_checks=True)
        destination = '/invite/synthetic-csrf-retry-capability/'
        handle = self.start(destination, client=checked)
        self.get('/preview/sign-in/?flow=' + handle, client=checked)
        data = {'username': GATE_USER, 'password': GATE_PASSWORD, 'flow': handle}
        failed = self.post('/preview/sign-in/', data, client=checked, HTTP_ORIGIN='https://app.quillmd.com:9443')
        self.assertEqual(failed.status_code, 403)
        self.assertContains(failed, 'href="/preview/sign-in/?flow=' + handle + '"', status_code=403)
        self.assertNotContains(failed, 'synthetic-csrf-retry-capability', status_code=403)
        retry = self.get('/preview/sign-in/?flow=' + handle, client=checked)
        token = re.search(r'name="csrfmiddlewaretoken" value="([A-Za-z0-9]+)"', retry.content.decode()).group(1)
        succeeded = self.post('/preview/sign-in/', {**data, 'csrfmiddlewaretoken': token}, client=checked, HTTP_ORIGIN='https://app.quillmd.com:9443')
        self.assertEqual(succeeded.status_code, 302)
        self.assertEqual(succeeded['Location'], destination)
        unbound = 'f' * 32
        failed = self.post('/preview/sign-in/', {**data, 'flow': unbound}, client=checked, HTTP_ORIGIN='https://app.quillmd.com:9443')
        self.assertEqual(failed.status_code, 403)
        self.assertNotContains(failed, unbound, status_code=403)
