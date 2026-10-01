"""QUILLMD_MFA_REQUIRED_ALL: every sign-in needs a confirmed authenticator; staff can reset a clinician's.

Default off is today's behaviour: only administrators need one, and a clinician's enrolled device is ignored.
"""
from base64 import b32encode
from urllib.parse import parse_qs, urlsplit

from django.test import Client, TestCase, override_settings
from core.tests.surfaces import SurfaceClient
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, Department, Membership, Organization, User

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD = 'Synthetic-Only-4821!private'


def code(device):
    return str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class MfaFixture(TestCase):
    client_class = SurfaceClient
    def setUp(self):
        self.clinician = User.objects.create_user(username='mfa-clinician', email='mfa-clinician@synthetic.invalid',
                                                  password=PASSWORD, verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='MFA clinic'), name='MFA')
        Membership.objects.create(user=self.clinician, department=department, role='clinician')

    def sign_in(self, client, otp=''):
        return client.post('/login/', {'email': self.clinician.email, 'password': PASSWORD, 'otp': otp})

    def enrolled(self):
        return TOTPDevice.objects.create(user=self.clinician, name='Authenticator', confirmed=True)


class DefaultOffIsUnchanged(MfaFixture):
    def test_a_clinician_signs_in_with_a_password_even_with_a_device(self):
        self.enrolled()
        self.assertRedirects(self.sign_in(self.client), '/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertContains(SurfaceClient().get('/login/'), 'Authenticator code (administrators)')


@override_settings(QUILLMD_MFA_REQUIRED_ALL=True)
class EverySignInNeedsAnAuthenticator(MfaFixture):
    def test_without_a_device_the_password_leads_only_to_enrolment(self):
        response = self.sign_in(self.client)
        self.assertRedirects(response, '/mfa/', fetch_redirect_response=False)
        self.assertTrue(AuditEvent.objects.get(action='auth.login').details['mfa_enrolment_required'])
        for path in ('/', '/patients/', '/billing/', '/team/'):
            with self.subTest(path=path):
                self.assertRedirects(self.client.get(path), '/mfa/', fetch_redirect_response=False)
        page = self.client.get('/mfa/')
        self.assertContains(page, 'Every QuillMD account requires multi-factor authentication.')
        device = TOTPDevice.objects.get(user=self.clinician)
        # The manual key is the otpauth URI's own secret, grouped for typing.
        uri_secret = parse_qs(urlsplit(device.config_url).query)['secret'][0]
        manual = page.context['secret']
        self.assertEqual(manual.replace(' ', ''), uri_secret)
        self.assertEqual(manual.replace(' ', ''), b32encode(device.bin_key).decode().rstrip('='))
        self.assertTrue(all(len(group) == 4 for group in manual.split(' ')[:-1]))
        self.assertContains(page, manual)
        self.assertContains(page, 'otpauth://')
        self.assertRedirects(self.client.post('/mfa/', {'code': code(device)}), '/', fetch_redirect_response=False)
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_with_a_device_the_code_is_required_at_sign_in(self):
        device = self.enrolled()
        self.assertEqual(self.sign_in(self.client).status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.sign_in(self.client, '000000' if code(device) != '000000' else '111111').status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        # django_otp throttles a device after failures (1 s, 2 s, ...); clear that so the right code is judged.
        TOTPDevice.objects.filter(pk=device.pk).update(throttling_failure_count=0, throttling_failure_timestamp=None)
        self.assertRedirects(self.sign_in(self.client, code(device)), '/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertContains(SurfaceClient().get('/login/'), 'Authenticator code')
        self.assertNotContains(SurfaceClient().get('/login/'), 'Authenticator code (administrators)')

    def test_a_session_opened_before_the_switch_is_sent_to_verify(self):
        self.client.force_login(self.clinician)
        self.assertRedirects(self.client.get('/'), '/mfa/', fetch_redirect_response=False)


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_MFA_REQUIRED_ALL=True)
class StaffResetMfa(MfaFixture):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(username='mfa-admin', email='mfa-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.admin_device = TOTPDevice.objects.create(user=self.admin, name='Admin authenticator', confirmed=True)
        self.console = SurfaceClient()
        self.console.force_login(self.admin)
        session = self.console.session
        session['otp_device_id'] = self.admin_device.persistent_id
        session.save()
        self.reason = {'reason': 'Called the clinic main line; identity confirmed by the practice manager.', 'confirm': 'on'}

    def reset(self, account, data=None):
        return self.console.post(f'/console/accounts/{account.pk}/mfa-reset/', data if data is not None else self.reason)

    def test_reset_removes_devices_signs_out_and_forces_enrolment(self):
        device = self.enrolled()
        live = SurfaceClient()
        self.assertRedirects(self.sign_in(live, code(device)), '/', fetch_redirect_response=False)
        self.assertEqual(live.get('/').status_code, 200)
        self.assertContains(self.console.get(f'/console/accounts/{self.clinician.pk}/detail/'), 'Reset MFA')
        response = self.reset(self.clinician)
        self.assertRedirects(response, f'/console/accounts/{self.clinician.pk}/detail/', fetch_redirect_response=False)
        self.assertFalse(TOTPDevice.objects.filter(user=self.clinician).exists())
        # The session opened with the removed device is gone.
        self.assertRedirects(live.get('/'), '/login/?next=/', fetch_redirect_response=False)
        event = AuditEvent.objects.get(action='admin.mfa_reset')
        self.assertEqual((event.actor, event.target), (self.admin, str(self.clinician.pk)))
        self.assertEqual(event.details['devices_removed'], 1)
        self.assertTrue(event.details['sessions_invalidated'])
        self.assertIn('identity confirmed', event.details['reason'])
        # Next sign-in: password, then enrolment of a new authenticator.
        self.assertRedirects(self.sign_in(SurfaceClient()), '/mfa/', fetch_redirect_response=False)

    def test_reset_refuses_administrators_missing_reasons_and_non_staff(self):
        self.enrolled()
        self.assertEqual(self.reset(self.admin).status_code, 403)
        self.assertTrue(TOTPDevice.objects.filter(user=self.admin).exists())
        self.assertEqual(self.reset(self.clinician, {'reason': 'too short', 'confirm': 'on'}).status_code, 400)
        self.assertEqual(self.reset(self.clinician, {'reason': self.reason['reason']}).status_code, 400)
        self.assertTrue(TOTPDevice.objects.filter(user=self.clinician).exists())
        other = SurfaceClient()
        other.force_login(self.clinician)
        self.assertEqual(other.post(f'/console/accounts/{self.clinician.pk}/mfa-reset/', self.reason).status_code, 404)
        self.assertFalse(AuditEvent.objects.filter(action='admin.mfa_reset').exists())

    @override_settings(QUILLMD_MFA_REQUIRED_ALL=False)
    def test_reset_is_not_offered_while_the_setting_is_off(self):
        self.enrolled()
        self.assertNotContains(self.console.get(f'/console/accounts/{self.clinician.pk}/detail/'), 'Reset MFA')
        self.assertEqual(self.reset(self.clinician).status_code, 404)
        self.assertTrue(TOTPDevice.objects.filter(user=self.clinician).exists())
