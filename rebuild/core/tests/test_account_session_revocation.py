"""Account suspension must revoke old sessions, including unused cookies."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import threading
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.tokens import default_token_generator
from django.apps import apps
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from core.tests.surfaces import SurfaceClient
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, User


@override_settings(ADMIN_SITE=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AccountSessionRevocation(TestCase):
    client_class = SurfaceClient
    password = 'Synthetic-session-preserved-password-29471!'

    def setUp(self):
        self.user = User.objects.create_user(
            username='suspension-user', email='suspension@synthetic.invalid',
            password=self.password, verified_at=timezone.now())
        self.admin = User.objects.create_user(
            username='suspension-admin', email='suspension-admin@synthetic.invalid',
            is_staff=True, verified_at=timezone.now())
        self.device = TOTPDevice.objects.create(user=self.admin, confirmed=True)
        self.client.force_login(self.admin)
        session = self.client.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()
        self.old_browser = SurfaceClient()
        self.old_browser.force_login(self.user)
        self.assertEqual(self.old_browser.get('/api/patients/').status_code, 200)

    def access(self, active):
        response = self.client.post(f'/console/accounts/{self.user.pk}/',
                                    {'active': 'on'} if active else {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/console/')

    def test_suspended_cookie_stays_revoked_after_reactivation_without_intervening_use(self):
        self.access(False)
        self.assertTrue(AuditEvent.objects.filter(action='admin.account_access',
                                                  details__sessions_invalidated=True).exists())
        self.access(True)
        # The old browser deliberately made no request during suspension.
        self.assertEqual(self.old_browser.get('/api/patients/').status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        fresh_browser = SurfaceClient()
        response = fresh_browser.post('/login/', {'email': self.user.email, 'password': self.password})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(fresh_browser.get('/api/patients/').status_code, 200)

    def test_saved_active_state_does_not_revoke_existing_session(self):
        self.access(True)
        self.assertEqual(self.old_browser.get('/api/patients/').status_code, 200)

    def test_existing_password_hash_sessions_remain_valid_before_any_suspension(self):
        self.assertEqual(self.user.get_session_auth_hash(),
                         AbstractBaseUser._get_session_auth_hash(self.user))
        self.user.refresh_from_db()
        self.assertEqual(self.user.session_version, 0)

    def test_session_created_from_stale_user_after_suspension_cannot_revive(self):
        stale_user = User.objects.get(pk=self.user.pk)
        self.access(False)
        late_browser = SurfaceClient()
        late_browser.force_login(stale_user)
        self.access(True)
        self.assertEqual(late_browser.get('/api/patients/').status_code, 302)

    def test_secret_rotation_fallback_does_not_resurrect_revoked_session(self):
        from django.conf import settings
        old_secret = settings.SECRET_KEY
        self.access(False)
        self.access(True)
        with override_settings(SECRET_KEY='synthetic-rotated-secret-for-revocation',
                               SECRET_KEY_FALLBACKS=[old_secret]):
            self.assertEqual(self.old_browser.get('/api/patients/').status_code, 302)

    def test_second_suspension_revokes_sessions_issued_after_first_reactivation(self):
        self.access(False)
        self.access(True)
        self.user.refresh_from_db()
        second_browser = SurfaceClient()
        second_browser.force_login(self.user)
        self.assertEqual(second_browser.get('/api/patients/').status_code, 200)
        self.access(False)
        self.access(False)
        self.access(True)
        self.assertEqual(second_browser.get('/api/patients/').status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.session_version, 2)

    def test_secret_rotation_preserves_current_version_session(self):
        from django.conf import settings
        old_secret = settings.SECRET_KEY
        self.access(False)
        self.access(True)
        self.user.refresh_from_db()
        current_browser = SurfaceClient()
        current_browser.force_login(self.user)
        with override_settings(SECRET_KEY='synthetic-rotated-secret-for-positive-control',
                               SECRET_KEY_FALLBACKS=[old_secret]):
            self.assertEqual(current_browser.get('/api/patients/').status_code, 200)

    def test_suspension_revokes_unused_password_recovery_link(self):
        raw = default_token_generator.make_token(self.user)
        url = f'/recovery/confirm/{urlsafe_base64_encode(force_bytes(self.user.pk))}/{raw}/'
        self.access(False)
        self.access(True)
        browser = SurfaceClient()
        response = browser.get(url)
        self.assertContains(response, 'Recovery link unavailable')

    def test_suspension_revokes_already_open_recovery_flow(self):
        raw = default_token_generator.make_token(self.user)
        url = f'/recovery/confirm/{urlsafe_base64_encode(force_bytes(self.user.pk))}/{raw}/'
        browser = SurfaceClient()
        clean_url = browser.get(url)['Location']
        self.access(False)
        self.access(True)
        response = browser.post(clean_url, {
            'new_password1': 'Rejected-synthetic-password-493710!',
            'new_password2': 'Rejected-synthetic-password-493710!',
        })
        self.assertContains(response, 'Recovery link unavailable')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_reactivated_user_can_request_and_use_fresh_recovery_link(self):
        self.access(False)
        self.access(True)
        browser = SurfaceClient()
        with patch('core.recovery.deliver_account_email') as delivery:
            self.assertEqual(browser.post('/recovery/', {'email': self.user.email}).status_code, 200)
        delivery.assert_called_once()
        raw = delivery.call_args.args[4]
        clean_url = browser.get('/recovery/confirm/' + raw + '/')['Location']
        replacement = 'Fresh-synthetic-password-after-reactivation-9428!'
        response = browser.post(clean_url, {'new_password1': replacement, 'new_password2': replacement})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/recovery/complete/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(replacement))

    def test_migration_initializer_revokes_preexisting_suspended_account_only(self):
        # Represent an account paused by the prior application, which had no
        # session generation. The saved browser must stay revoked after resume.
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        migration = importlib.import_module('core.migrations.0016_user_session_version')
        migration.revoke_preexisting_suspended_accounts(apps, SimpleNamespace(connection=connection))
        self.user.refresh_from_db()
        self.assertEqual(self.user.session_version, 1)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.session_version, 0)
        self.access(True)
        self.assertEqual(self.old_browser.get('/api/patients/').status_code, 302)


@override_settings(ADMIN_SITE=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ConcurrentAccountSuspension(TransactionTestCase):
    client_class = SurfaceClient
    password = AccountSessionRevocation.password
    setUp = AccountSessionRevocation.setUp

    def test_two_concurrent_suspensions_serialize_one_transition_and_revoke_cookie(self):
        self.assertEqual(connection.vendor, 'postgresql')
        browsers = [SurfaceClient(), SurfaceClient()]
        for browser in browsers:
            browser.force_login(self.admin)
            session = browser.session
            session['otp_device_id'] = self.device.persistent_id
            session.save()
        barrier = threading.Barrier(2)

        def suspend(browser):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return browser.post(f'/console/accounts/{self.user.pk}/', {}).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(suspend, browsers))
        self.assertEqual(results, [302, 302])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.session_version, 1)
        self.assertEqual(AuditEvent.objects.filter(action='admin.account_access',
                                                   details__sessions_invalidated=True).count(), 1)
        AccountSessionRevocation.access(self, True)
        self.assertEqual(self.old_browser.get('/api/patients/').status_code, 302)
