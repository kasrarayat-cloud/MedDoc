"""Failed sign-ins are classified in the audit trail, and only there (inventory 7A, F4, LOW).

Every failure wrote the same row — `auth.login_failed`, no actor, no target, `details: No credentials recorded` — so
an administrator could not tell a mistyped password from a stolen password meeting the authenticator, from probing for
addresses, from a suspended account being tried. The row now carries `reason` and, when the address reaches an
account, that account as its target (shown on the console's account page). The person signing in still reads ONE
sentence whatever the reason, and no row carries the address, the password or the code.
"""
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, User

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD = 'Synthetic-Only-sign-in-5531!'
GENERIC = 'Sign-in failed. Check your credentials, verification, and authenticator code.'


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, QUILLMD_MFA_REQUIRED_ALL=False,
                   STORAGES=STORAGES)
class FailedSignInClassification(TestCase):
    def setUp(self):
        now = timezone.now()
        self.doctor = User.objects.create_user(username='f4-doctor', email='f4-doctor@synthetic.invalid',
                                               password=PASSWORD, verified_at=now)
        self.unverified = User.objects.create_user(username='f4-new', email='f4-new@synthetic.invalid',
                                                   password=PASSWORD)
        self.suspended = User.objects.create_user(username='f4-off', email='f4-off@synthetic.invalid',
                                                  password=PASSWORD, verified_at=now, is_active=False)
        self.admin = User.objects.create_user(username='f4-admin', email='f4-admin@synthetic.invalid',
                                              password=PASSWORD, verified_at=now, is_staff=True)
        TOTPDevice.objects.create(user=self.admin, name='Admin', confirmed=True)
        self.bare_admin = User.objects.create_user(username='f4-bare', email='f4-bare@synthetic.invalid',
                                                   password=PASSWORD, verified_at=now, is_staff=True)

    def failed_sign_in(self, email, password=PASSWORD, otp=''):
        before = set(AuditEvent.objects.filter(action='auth.login_failed').values_list('pk', flat=True))
        client = Client()
        response = client.post('/login/', {'email': email, 'password': password, 'otp': otp})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, GENERIC)
        self.assertNotIn('_auth_user_id', client.session)
        rows = AuditEvent.objects.filter(action='auth.login_failed').exclude(pk__in=before)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertIsNone(row.actor_id)
        recorded = repr((row.target, row.details))
        for secret in (PASSWORD, email, 'wrong-password-for-f4', '000000'):
            self.assertNotIn(secret, recorded)
        return row

    def test_each_failure_records_its_reason_and_the_account_it_reached(self):
        cases = [
            ('nobody@synthetic.invalid', PASSWORD, '', 'unknown_account', ''),
            (self.doctor.email, 'wrong-password-for-f4', '', 'password', str(self.doctor.pk)),
            (self.suspended.email, PASSWORD, '', 'inactive', str(self.suspended.pk)),
            (self.unverified.email, PASSWORD, '', 'unverified', str(self.unverified.pk)),
            (self.admin.email, PASSWORD, '000000', 'authenticator', str(self.admin.pk)),
            (self.bare_admin.email, PASSWORD, '', 'authenticator_missing', str(self.bare_admin.pk)),
        ]
        for email, password, otp, reason, target in cases:
            with self.subTest(reason=reason):
                row = self.failed_sign_in(email, password, otp)
                self.assertEqual((row.details.get('reason'), row.target), (reason, target))
                self.assertEqual(row.details.get('details'), 'No credentials recorded')

    @override_settings(ADMIN_SITE=True)
    def test_a_clinician_on_the_administration_surface_is_not_an_administrator(self):
        row = self.failed_sign_in(self.doctor.email)
        self.assertEqual((row.details.get('reason'), row.target), ('not_administrator', str(self.doctor.pk)))

    def test_positive_control_a_correct_sign_in_writes_no_failure(self):
        client = Client()
        response = client.post('/login/', {'email': self.doctor.email, 'password': PASSWORD, 'otp': ''})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AuditEvent.objects.filter(action='auth.login_failed').exists())
