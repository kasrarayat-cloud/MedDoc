"""Account-only HTTPS boundary; isolated database and synthetic credentials."""
import re
from datetime import timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, Membership, User
from core.preview_access import COOKIE, KIND, safe_destination

GATE_USER = 'obsolete-synthetic-preview'
GATE_PASSWORD = 'Obsolete-synthetic-gate-only-8492!'
SETTINGS = {
    'ADMIN_SITE': False, 'QUILLMD_TRUST_PROXY': True,
    'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED': True,
    'QUILLMD_PREVIEW_AUTH_ENABLED': True,  # Obsolete configuration cannot restore the gate.
    'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': True,
    'QUILLMD_PREVIEW_ORIGIN': 'https://app.quillmd.com:9443',
    'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': GATE_USER,
    'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': GATE_PASSWORD,
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    'SESSION_COOKIE_SECURE': True, 'CSRF_COOKIE_SECURE': True, 'CSRF_TRUSTED_ORIGINS': [],
    'STORAGES': {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
}
EDGE = {'HTTP_HOST': 'app.quillmd.com', 'HTTP_X_QUILLMD_ACCOUNT': '1', 'secure': True}


class SafeAccountDestinationTests(SimpleTestCase):
    def test_only_local_application_locations_can_resume(self):
        for path in ('/', '/invite/synthetic-token/', '/recovery/confirm/abc/123-xyz/',
                     '/encounters/abc/?tab=coding', '/patients/?q=Synthetic%20Patient'):
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
class DirectAccountAccessTests(TestCase):
    password = 'Synthetic-individual-account-8492!'

    def setUp(self):
        self.user = User.objects.create_user(username='synthetic-individual',
            email='synthetic-individual@example.invalid', password=self.password,
            verified_at=timezone.now())

    def get(self, path, client=None, **extra):
        return (client or self.client).get(path, **{**EDGE, **extra})

    def post(self, path, data, client=None, **extra):
        return (client or self.client).post(path, data, **{**EDGE, **extra})

    def login(self, client=None, **data):
        return self.post('/login/', {'email': self.user.email, 'password': self.password, **data}, client=client)

    def test_fresh_browser_enters_account_login_and_password_is_unchanged(self):
        original_hash = self.user.password
        response = self.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response['Location']).path, '/login/')
        page = self.get(response['Location'])
        for expected in ('name="email"', 'name="password"'):
            self.assertContains(page, expected)
        for forbidden in ('Private preview', 'name="username"', GATE_USER, GATE_PASSWORD, 'name="flow"'):
            self.assertNotContains(page, forbidden)
        self.assertNotIn(COOKIE, self.client.cookies)
        self.assertEqual(self.login()['Location'], '/')
        self.assertEqual(self.get('/').status_code, 200)
        self.assertNotIn(COOKIE, self.client.cookies)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_hash)
        self.assertEqual(AuditEvent.objects.filter(action='auth.login').count(), 1)
        self.assertFalse(AuditEvent.objects.filter(action__startswith='preview.').exists())

    def test_empty_invalid_or_disabled_shared_configuration_cannot_block_account_login(self):
        for config in (
            {'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': '', 'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': ''},
            {'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': 'invalid:old-name', 'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': 'short\n'},
            {'QUILLMD_PREVIEW_AUTH_ENABLED': False},
            {'QUILLMD_PREVIEW_ORIGIN': 'https://obsolete.invalid:9443'},
        ):
            browser = Client()
            with self.subTest(config_names=sorted(config)), override_settings(**config):
                self.assertEqual(self.get('/login/', browser).status_code, 200)
                self.assertEqual(self.login(browser).status_code, 302)
                self.assertEqual(self.get('/', browser).status_code, 200)
                self.assertNotIn(COOKIE, browser.cookies)

    def test_wrong_unknown_inactive_and_unverified_accounts_cannot_authenticate(self):
        unverified = User.objects.create_user(username='synthetic-unverified',
            email='unverified@example.invalid', password=self.password)
        disabled = User.objects.create_user(username='synthetic-disabled',
            email='disabled@example.invalid', password=self.password, verified_at=timezone.now(), is_active=False)
        for email, password in ((self.user.email, 'Wrong-synthetic-only-value!'),
                 ('absent@example.invalid', self.password),
                 (unverified.email, self.password), (disabled.email, self.password)):
            browser = Client()
            with self.subTest(email=email):
                response = self.post('/login/', {'email': email, 'password': password}, browser)
                self.assertContains(response, 'Sign-in failed')
                self.assertNotContains(response, password)
                self.assertNotIn('_auth_user_id', browser.session)
                self.assertEqual(urlsplit(self.get('/', browser)['Location']).path, '/login/')
        self.assertEqual(AuditEvent.objects.filter(action='auth.login_failed').count(), 4)
        self.assertNotIn(self.password, str(list(AuditEvent.objects.values('action', 'target', 'details'))))

    def test_existing_atomic_account_throttle_refuses_ninth_attempt(self):
        for _ in range(8):
            self.assertContains(self.post('/login/', {'email': self.user.email,
                'password': 'Wrong-synthetic-only-value!'}), 'Sign-in failed')
        self.assertContains(self.login(), 'Too many sign-in attempts')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(AuditEvent.objects.filter(action='auth.login').exists())

    def test_old_preview_cookie_neither_grants_access_nor_changes_retained_session(self):
        obsolete = SessionStore()
        obsolete['kind'] = KIND
        obsolete['grant'] = {'fingerprint': 'obsolete', 'issued': 1, 'seen': 1}
        obsolete.save()
        original = Session.objects.get(pk=obsolete.session_key).session_data
        self.client.cookies[COOKIE] = obsolete.session_key
        response = self.get('/')
        self.assertEqual(urlsplit(response['Location']).path, '/login/')
        self.assertEqual(response.cookies[COOKIE]['max-age'], 0)
        self.assertEqual(Session.objects.get(pk=obsolete.session_key).session_data, original)
        self.assertEqual(self.login()['Location'], '/')
        self.assertEqual(self.get('/').status_code, 200)
        self.assertEqual(Session.objects.get(pk=obsolete.session_key).session_data, original)

    def test_copied_account_cookie_in_obsolete_cookie_cannot_revoke_or_grant_authority(self):
        account_browser = Client()
        account_browser.force_login(self.user)
        key = account_browser.cookies[settings.SESSION_COOKIE_NAME].value
        original = Session.objects.get(pk=key).get_decoded()
        outsider = Client()
        outsider.cookies[COOKIE] = key
        self.assertEqual(urlsplit(self.get('/', outsider)['Location']).path, '/login/')
        for path in ('/preview/sign-in/', '/preview/sign-out/'):
            self.assertEqual(self.get(path, outsider)['Location'], '/login/')
        self.assertEqual(Session.objects.get(pk=key).get_decoded(), original)
        account_browser.cookies[COOKIE] = key
        self.assertEqual(self.get('/preview/sign-out/', account_browser)['Location'], '/login/')
        self.assertEqual(self.get('/', account_browser).status_code, 200)
        self.assertEqual(Session.objects.get(pk=key).get_decoded(), original)

    def test_legacy_links_ignore_flow_next_credentials_and_never_loop(self):
        for path in ('/preview/sign-in/', '/preview/sign-out/'):
            for query in ('', '?flow=' + 'f' * 32, '?next=https://outside.invalid/',
                          '?next=/preview/sign-in/&flow=%0d%0aLocation:https://outside.invalid'):
                with self.subTest(path=path, query=query):
                    response = self.get(path + query)
                    self.assertEqual(response.status_code, 303)
                    self.assertEqual(response['Location'], '/login/')
                    self.assertEqual(self.get(response['Location']).status_code, 200)
            response = self.post(path, {'username': GATE_USER, 'password': GATE_PASSWORD,
                'next': 'https://outside.invalid/', 'flow': 'f' * 32})
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response['Location'], '/login/')
            self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(AuditEvent.objects.filter(action__startswith='preview.').exists())

    def test_anonymous_pages_apis_and_downloads_are_account_protected(self):
        identifier = '00000000-0000-0000-0000-000000000001'
        for path in ('/', '/doctor-guide/', '/api/patients/', f'/api/encounters/{identifier}/',
                 f'/templates/{identifier}/original/', f'/templates/{identifier}/preparation/',
                 f'/templates/{identifier}/preparation/preview/original/',
                 f'/encounters/{identifier}/export/', '/console/services/'):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response['Location']).path, '/login/')
        response = self.post(f'/encounters/{identifier}/finalize/', {'reviewed': 'on'})
        self.assertEqual(response['Location'], '/login/?next=/')

    def test_doctor_cannot_use_admin_console_and_signup_creates_nothing(self):
        self.login()
        self.assertEqual(self.get('/console/services/').status_code, 404)
        count = User.objects.count()
        for browser in (self.client, Client()):
            self.assertEqual(self.get('/register/', browser).status_code, 404)
            self.assertEqual(self.post('/register/', {'email': 'new@example.invalid',
                'password1': self.password, 'password2': self.password, 'synthetic_only': 'on'}, browser).status_code, 404)
        self.assertEqual(User.objects.count(), count)
        self.assertEqual(self.client.get('/register/', HTTP_HOST='localhost:9130').status_code, 404)

    def test_known_files_apis_and_revoked_membership_remain_tenant_protected_on_normal_https(self):
        from core.tests.test_security import SyntheticFixture
        from core.security import private_path
        factory = SyntheticFixture()
        own = factory.make_scope('direct-visible')
        sibling = factory.make_scope('direct-sibling', organization=own[1])
        foreign = factory.make_scope('direct-foreign')
        Membership.objects.create(user=self.user, department=own[2], role='clinician')
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            for scope in (own, sibling, foreign):
                template, encounter, blob = scope[4], scope[5], scope[-1]
                original = private_path(template.original_path)
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(blob)
                encounter.status = 'finalized'
                encounter.export_path = template.original_path
                encounter.export_sha256 = template.sha256
                encounter.save()
                for path in (f'/templates/{template.pk}/original/', f'/encounters/{encounter.pk}/export/'):
                    self.assertEqual(urlsplit(self.get(path, Client())['Location']).path, '/login/')
            self.assertEqual(self.login().status_code, 302)
            patients = self.get('/api/patients/').json()['patients']
            self.assertEqual([item['id'] for item in patients], [str(own[3].pk)])
            for path in (f'/templates/{own[4].pk}/original/', f'/encounters/{own[5].pk}/export/'):
                response = self.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), own[-1])
            for scope in (sibling, foreign):
                for path in (f'/templates/{scope[4].pk}/original/',
                             f'/encounters/{scope[5].pk}/export/', f'/api/encounters/{scope[5].pk}/'):
                    self.assertEqual(self.get(path).status_code, 404)
            Membership.objects.filter(user=self.user, department=own[2]).update(active=False)
            self.assertEqual(self.get('/api/patients/').json()['patients'], [])
            self.assertEqual(self.get(f'/encounters/{own[5].pk}/export/').status_code, 404)

    def test_administrator_requires_current_mfa_and_cannot_replay_code(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        device = TOTPDevice.objects.create(user=self.user, confirmed=True, name='Synthetic authenticator')
        for otp in ('', 'bad'):
            self.assertContains(self.login(otp=otp), 'Sign-in failed')
            self.assertNotIn('_auth_user_id', self.client.session)
        # The real TOTP cooldown remains active after failed codes. Advance
        # its clock rather than disabling the limiter or resetting the device.
        elapsed = timezone.now() + timedelta(seconds=5)
        with patch('django_otp.models.timezone.now', return_value=elapsed), \
             patch('django_otp.plugins.otp_totp.models.time.time', return_value=elapsed.timestamp()):
            code = str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)
            self.assertEqual(self.login(otp=code)['Location'], '/')
        self.assertEqual(self.get('/console/services/').status_code, 200)
        other = Client()
        with patch('django_otp.models.timezone.now', return_value=elapsed), \
             patch('django_otp.plugins.otp_totp.models.time.time', return_value=elapsed.timestamp()):
            self.assertContains(self.login(other, otp=code), 'Sign-in failed')
        self.assertNotIn('_auth_user_id', other.session)

    def test_login_and_logout_require_real_csrf_and_canonical_origin(self):
        browser = Client(enforce_csrf_checks=True)
        page = self.get('/login/', browser)
        token = re.search(r'name="csrfmiddlewaretoken" value="([A-Za-z0-9]+)"', page.content.decode()).group(1)
        data = {'email': self.user.email, 'password': self.password}
        self.assertEqual(self.post('/login/', data, browser).status_code, 403)
        for origin in ('https://outside.invalid', 'https://app.quillmd.com:9443'):
            self.assertEqual(self.post('/login/', {**data, 'csrfmiddlewaretoken': token}, browser,
                HTTP_ORIGIN=origin).status_code, 403)
        self.assertEqual(self.post('/login/', {**data, 'csrfmiddlewaretoken': token}, browser,
            HTTP_ORIGIN='https://app.quillmd.com').status_code, 302)
        self.assertEqual(self.get('/logout/', browser).status_code, 405)
        self.assertEqual(self.post('/logout/', {}, browser).status_code, 403)
        logout_page = self.get('/', browser)
        logout_token = re.search(r'name="csrfmiddlewaretoken" value="([A-Za-z0-9]+)"', logout_page.content.decode()).group(1)
        response = self.post('/logout/', {'csrfmiddlewaretoken': logout_token}, browser,
            HTTP_ORIGIN='https://app.quillmd.com')
        self.assertEqual(response['Location'], '/login/')
        self.assertEqual(self.get('/login/', browser).status_code, 200)
        self.assertEqual(urlsplit(self.get('/', browser)['Location']).path, '/login/')
        self.assertEqual(AuditEvent.objects.filter(action='auth.logout').count(), 1)

    def test_login_next_cannot_reintroduce_legacy_gate_or_open_redirect(self):
        for destination in ('https://outside.invalid/', '//outside.invalid/', '/\\outside.invalid/',
                            '/%2foutside.invalid/', '/%5coutside.invalid/', '/preview/sign-in/',
                            '/preview/sign-in/?flow=' + 'f' * 32, '/preview/sign-out/'):
            with self.subTest(destination=destination):
                browser = Client()
                response = self.login(browser, next=destination)
                self.assertEqual(response['Location'], '/')

    def test_expired_invitation_and_csrf_failure_do_not_disclose_capability(self):
        raw = 'synthetic-secret-capability-not-for-logs'
        self.assertEqual(self.get('/invite/' + raw + '/').status_code, 404)
        checked = Client(enforce_csrf_checks=True)
        with self.assertLogs('django.security.csrf', level='WARNING') as captured:
            response = self.post('/invite/' + raw + '/', {}, checked)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(raw, '\n'.join(captured.output))
        self.assertNotContains(response, raw, status_code=403)
        self.assertIsNone(captured.records[0].request)
