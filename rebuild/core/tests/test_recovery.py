"""Synthetic recovery tests: token reuse, session revocation and administrator MFA."""
from datetime import timedelta
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, Department, Invitation, LedgerEntry, Membership, Organization, User, Verification, Wallet
from core.security import digest, token


@override_settings(ADMIN_SITE=False, QUILLMD_EMAIL_MODE='file', EMAIL_BACKEND='core.email_backend.PrivateFileEmailBackend', STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class RecoveryTests(TestCase):
    password = 'Synthetic-account-before-4921!'
    replacement = 'Synthetic-account-after-82517!'

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = override_settings(EMAIL_FILE_PATH=Path(self.directory.name), QUILLMD_APP_BASE_URL='http://localhost:9130')
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.user = User.objects.create_user(username='recovery', email='recovery@synthetic.invalid', password=self.password, verified_at=timezone.now())

    def request_link(self, client=None):
        response = (client or self.client).post('/recovery/', {'email': self.user.email})
        self.assertContains(response, 'Private outbox only')
        self.assertNotContains(response, self.user.email)
        content = list(Path(self.directory.name).glob('*.log'))[-1].read_text()
        return re.search(r'http://localhost:9130(/recovery/confirm/[^\s]+/)', content).group(1)

    def new_password(self, **extra):
        return {'new_password1': self.replacement, 'new_password2': self.replacement, **extra}

    def test_email_handoff_has_no_token_or_referrer_and_clean_url_needs_its_session(self):
        link = self.request_link()
        raw = link.split('/')[-2]
        response = self.client.get(link + '?next=https://attacker.invalid/')
        self.assertContains(response, 'Continue to password form')
        self.assertNotContains(response, raw)
        self.assertNotContains(response, 'attacker.invalid')
        self.assertNotContains(response, 'new_password1')
        self.assertNotIn('Location', response)
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'referrerpolicy="no-referrer"')
        clean = response.context['continue_url']
        self.assertTrue(clean.startswith('/recovery/confirm/'))
        self.assertTrue(clean.endswith('/set-password/'))
        self.assertContains(Client().get(clean), 'Recovery link unavailable')
        self.assertContains(self.client.get(clean), 'Set a new password')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertFalse(AuditEvent.objects.filter(action='auth.password_recovered').exists())

    def test_expiry_and_account_status_are_rechecked_after_handoff(self):
        from core.recovery import recovery_token_generator
        clean = self.client.get(self.request_link()).context['continue_url']
        future = timezone.now().replace(tzinfo=None) + timedelta(minutes=31)
        with patch.object(recovery_token_generator, '_now', return_value=future):
            self.assertContains(self.client.get(clean), 'Recovery link unavailable')
        self.user.verified_at = None
        self.user.save(update_fields=['verified_at'])
        self.assertContains(self.client.get(clean), 'Recovery link unavailable')
        self.user.verified_at = timezone.now()
        self.user.is_active = False
        self.user.save(update_fields=['verified_at', 'is_active'])
        self.assertContains(self.client.get(clean), 'Recovery link unavailable')

    def test_password_change_after_handoff_invalidates_held_token(self):
        clean = self.client.get(self.request_link()).context['continue_url']
        self.user.set_password('Another-synthetic-password-729315!')
        self.user.save(update_fields=['password'])
        self.assertContains(self.client.get(clean), 'Recovery link unavailable')

    def test_confirm_post_requires_csrf_after_handoff(self):
        browser = Client(enforce_csrf_checks=True)
        clean = browser.get(self.request_link()).context['continue_url']
        self.assertContains(browser.get(clean), 'Set a new password')
        self.assertEqual(browser.post(clean, self.new_password()).status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    @override_settings(QUILLMD_TRUST_PROXY=True, QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=True,
                       QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED=True, SESSION_COOKIE_SECURE=True,
                       CSRF_COOKIE_SECURE=True, SECURE_SSL_REDIRECT=True,
                       SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_canonical_handoff_retains_no_referrer_and_strict_secure_cookies(self):
        from core.recovery import recovery_token_generator
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        raw = recovery_token_generator.make_token(self.user)
        response = self.client.get(f'/recovery/confirm/{uid}/{raw}/', secure=True,
            HTTP_HOST='app.quillmd.com', HTTP_X_QUILLMD_ACCOUNT='1', HTTP_X_FORWARDED_PROTO='https')
        self.assertContains(response, 'Continue to password form')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        session = response.cookies['quillmd_doctor_session']
        self.assertEqual(session['samesite'], 'Strict')
        self.assertTrue(session['secure'])
        self.assertTrue(session['httponly'])

    def test_raw_token_head_keeps_existing_redirect_behavior(self):
        response = self.client.head(self.request_link())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('/set-password/'))

    def test_recovery_invalidates_other_sessions_and_token_cannot_repeat(self):
        old_session = Client()
        old_session.force_login(self.user)
        link = self.request_link()
        response = self.client.get(link)
        self.assertContains(response, 'Continue to password form')
        clean_link = response.context['continue_url']
        self.assertTrue(clean_link.endswith('/set-password/'))
        self.assertNotIn(link.split('/')[-2], clean_link)
        self.assertContains(self.client.get(clean_link), 'Set a new password')
        self.assertRedirects(self.client.post(clean_link, self.new_password()), '/recovery/complete/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.replacement))
        self.assertEqual(old_session.get('/').status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(Client().get(link), 'Recovery link unavailable')
        event = AuditEvent.objects.get(action='auth.password_recovered')
        self.assertTrue(event.details['sessions_invalidated'])
        self.assertFalse(Wallet.objects.filter(user=self.user).exists())

    def test_same_token_open_in_two_sessions_cannot_change_password_twice(self):
        link = self.request_link()
        other = Client()
        first = self.client.get(link).context['continue_url']
        second = other.get(link).context['continue_url']
        self.assertEqual(self.client.post(first, self.new_password()).status_code, 302)
        self.assertContains(other.post(second, self.new_password(new_password1='Other-synthetic-password-8299!', new_password2='Other-synthetic-password-8299!')), 'Recovery link unavailable')
        self.assertEqual(AuditEvent.objects.filter(action='auth.password_recovered').count(), 1)

    def test_expired_or_disabled_account_link_refused(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        with patch.object(default_token_generator, '_now', return_value=timezone.now().replace(tzinfo=None) - timedelta(minutes=31)):
            raw = default_token_generator.make_token(self.user)
        self.assertContains(self.client.get(f'/recovery/confirm/{uid}/{raw}/'), 'Recovery link unavailable')
        valid = self.request_link()
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertContains(self.client.get(valid), 'Recovery link unavailable')

    def test_unknown_unverified_and_throttled_requests_share_response(self):
        unverified = User.objects.create_user(username='unverified', email='unverified@synthetic.invalid', password=self.password)
        for email in ('absent@synthetic.invalid', unverified.email):
            self.assertContains(self.client.post('/recovery/', {'email': email}), 'If this address is eligible')
        self.assertFalse(list(Path(self.directory.name).glob('*.log')))
        for _ in range(5):
            self.assertContains(self.client.post('/recovery/', {'email': self.user.email}), 'If this address is eligible')
        self.assertEqual(AuditEvent.objects.filter(action='auth.recovery_requested').count(), 3)

    def test_admin_reset_needs_current_mfa_and_login_still_requires_mfa(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        device = TOTPDevice.objects.create(user=self.user, confirmed=True, name='Synthetic authenticator')
        link = self.request_link()
        clean_link = self.client.get(link).context['continue_url']
        self.assertContains(self.client.post(clean_link, self.new_password()), 'This field is required')
        code = str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)
        self.assertEqual(self.client.post(clean_link, self.new_password(otp=code)).status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.replacement))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(self.client.post('/login/', {'email': self.user.email, 'password': self.replacement}), 'Sign-in failed')
        self.assertContains(self.client.post('/login/', {'email': self.user.email, 'password': self.replacement, 'otp': code}), 'Sign-in failed')
        self.assertTrue(AuditEvent.objects.get(action='auth.password_recovered').details['mfa_required'])

    def test_resend_invalidates_prior_verification_and_grants_once(self):
        user = User.objects.create_user(username='resend', email='resend@synthetic.invalid', password=self.password)
        old = token()
        Verification.objects.create(user=user, token_hash=digest(old), expires_at=timezone.now() + timedelta(hours=1))
        response = self.client.post('/verification/resend/', {'email': user.email})
        self.assertContains(response, 'Private outbox only')
        self.assertEqual(self.client.post(f'/verify/{old}/').status_code, 404)
        content = next(Path(self.directory.name).glob('*.log')).read_text()
        route = re.search(r'http://localhost:9130(/verify/[^\s]+/)', content).group(1)
        self.assertEqual(self.client.post(route).status_code, 302)
        self.assertEqual(self.client.post(route).status_code, 404)
        self.assertEqual(Wallet.objects.get(user=user, kind='promo').balance, 10)
        self.assertEqual(LedgerEntry.objects.filter(wallet__user=user, kind='welcome').count(), 1)

    def test_session_expiry_preserves_safe_destination_without_replaying_post(self):
        response = self.client.get('/patients/?q=synthetic')
        self.assertEqual(response['Location'], '/login/?next=/patients/')
        response = self.client.post('/login/', {'email': self.user.email, 'password': self.password, 'next': '/patients/'})
        self.assertEqual(response['Location'], '/patients/')
        for destination in ('https://attacker.invalid/', '//attacker.invalid/', '/\\attacker.invalid/', 'javascript:alert(1)'):
            self.client.logout()
            response = self.client.post('/login/', {'email': self.user.email, 'password': self.password, 'next': destination})
            self.assertEqual(response['Location'], '/')

    def test_recovery_post_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post('/recovery/', {'email': self.user.email}).status_code, 403)
        self.assertEqual(browser.post('/verification/resend/', {'email': self.user.email}).status_code, 403)

    def invitation(self):
        org = Organization.objects.create(name='Synthetic recovery scope')
        dept = Department.objects.create(organization=org, name='Synthetic X-ray')
        member = Membership.objects.create(user=self.user, department=dept, role='owner')
        raw = token()
        invite = Invitation.objects.create(email='invited@synthetic.invalid', department=dept, role='employee', invited_by=self.user, token_hash=digest(raw), expires_at=timezone.now()+timedelta(days=1))
        return invite, raw, member

    def acceptance(self):
        return {'email': 'invited@synthetic.invalid', 'password1': self.password, 'password2': self.password, 'synthetic_only': 'on'}

    def test_revoked_invitation_refuses_acceptance_and_is_visible(self):
        invite, raw, member = self.invitation()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(f'/team/invitations/{invite.pk}/revoke/').status_code, 302)
        self.assertContains(self.client.get('/team/'), 'Expired / revoked')
        self.assertEqual(Client().post(f'/invite/{raw}/', self.acceptance()).status_code, 404)
        self.assertFalse(User.objects.filter(email=invite.email).exists())
        self.assertEqual(AuditEvent.objects.filter(action='department.invitation_revoked').count(), 1)

    def test_inviter_losing_authority_invalidates_outstanding_invitation(self):
        invite, raw, member = self.invitation()
        member.active = False
        member.save(update_fields=['active'])
        self.assertEqual(Client().post(f'/invite/{raw}/', self.acceptance()).status_code, 403)
        self.assertFalse(User.objects.filter(email=invite.email).exists())
        invite.refresh_from_db()
        self.assertIsNone(invite.accepted_at)

    def test_foreign_department_cannot_revoke_invitation(self):
        invite, raw, member = self.invitation()
        outsider = User.objects.create_user(username='outsider', email='outsider@synthetic.invalid', verified_at=timezone.now())
        self.client.force_login(outsider)
        self.assertEqual(self.client.post(f'/team/invitations/{invite.pk}/revoke/').status_code, 404)
