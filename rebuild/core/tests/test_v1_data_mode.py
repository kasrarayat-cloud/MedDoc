"""QUILLMD_DATA_MODE: synthetic stays exactly as it was; real refuses to start half-configured.

Each refusal is proved twice: once against the pure check (fast, every variant), and once by
importing the real settings module in a fresh interpreter, which is what a service start does.
No database, provider, payment or email request leaves these tests.
"""
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.forms import EncounterForm, PatientForm, RegisterForm, UploadForm, VoiceForm
from core.models import Department, Membership, Organization, Patient, User
from quillmd import application_profile as profile

REBUILD = Path(__file__).resolve().parents[2]
ALLOWED = ['localhost', '127.0.0.1', 'testserver', 'app.quillmd.com', 'admin.quillmd.com']
#: A complete, safe real-mode environment. Every refusal below is this minus one requirement.
COMPLETE_REAL = {'QUILLMD_DATA_MODE': 'real', 'QUILLMD_HTTPS': '1', 'QUILLMD_REGISTRATION': 'invite',
                 'QUILLMD_EMAIL_MODE': 'resend', 'QUILLMD_PREVIEW_AUTH_ENABLED': '0',
                 'QUILLMD_MFA_REQUIRED_ALL': '1', 'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com'}
PRIVATE_VALUE = 'SYNTHETIC-PRIVATE-VALUE-never-printed-0001'
#: (setting the refusal must name, change applied to COMPLETE_REAL; None deletes the variable)
REFUSALS = [
    ('QUILLMD_HTTPS', {'QUILLMD_HTTPS': '0'}),
    ('QUILLMD_HTTPS', {'QUILLMD_HTTPS': None}),
    ('QUILLMD_REGISTRATION', {'QUILLMD_REGISTRATION': 'open'}),
    ('QUILLMD_REGISTRATION', {'QUILLMD_REGISTRATION': None}),
    ('QUILLMD_EMAIL_MODE', {'QUILLMD_EMAIL_MODE': 'file'}),
    ('QUILLMD_EMAIL_MODE', {'QUILLMD_EMAIL_MODE': None}),
    ('QUILLMD_EMAIL_MODE', {'QUILLMD_EMAIL_MODE': 'smtp'}),
    ('QUILLMD_PREVIEW_AUTH_ENABLED', {'QUILLMD_PREVIEW_AUTH_ENABLED': '1'}),
    ('QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME', {'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': PRIVATE_VALUE}),
    ('QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD', {'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': PRIVATE_VALUE}),
    ('QUILLMD_MFA_REQUIRED_ALL', {'QUILLMD_MFA_REQUIRED_ALL': '0'}),
    ('QUILLMD_MFA_REQUIRED_ALL', {'QUILLMD_MFA_REQUIRED_ALL': None}),
    ('QUILLMD_DEEPGRAM_MIP_OPT_OUT', {'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'false'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': None}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'http://app.quillmd.com'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://localhost'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://127.0.0.1:9130'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://testserver'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com/billing'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://someone:secret@app.quillmd.com'}),
    ('QUILLMD_APP_BASE_URL', {'QUILLMD_APP_BASE_URL': 'https://unlisted.example'}),
]


def environment(changes, base=COMPLETE_REAL):
    env = dict(base)
    for name, value in changes.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def problems(env):
    """The check as settings.py calls it: computed values derived from `env` exactly as settings derives them."""
    https = env.get('QUILLMD_HTTPS', '0') == '1'
    return profile.real_mode_problems(env, allowed_hosts=ALLOWED, session_cookie_secure=https, csrf_cookie_secure=https,
                                      email_mode=env.get('QUILLMD_EMAIL_MODE', 'file'),
                                      app_base_url=env.get('QUILLMD_APP_BASE_URL', 'http://localhost:9130'))


def start(env, expression='{"synthetic": s.SYNTHETIC_ONLY, "mode": s.QUILLMD_DATA_MODE}'):
    """Import the settings module the way a service start does, in a clean interpreter."""
    base = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': 'synthetic-settings-check',
            'QUILLMD_DB_PASSWORD': 'unused-synthetic-check', 'PATH': os.environ.get('PATH', '')}
    return subprocess.run([sys.executable, '-B', '-c', f'import json; from quillmd import settings as s; print(json.dumps({expression}))'],
                          cwd=REBUILD, env={**base, **env}, capture_output=True, text=True, timeout=30)


def refusal_items(stderr):
    match = re.search(r'QuillMD refuses to start: (.*)\.$', stderr.strip().splitlines()[-1])
    return match.group(1).split('; ') if match else []


class ProfileParsing(SimpleTestCase):
    def test_defaults_are_todays_behaviour(self):
        self.assertEqual(profile.choice({}, 'QUILLMD_DATA_MODE', profile.DATA_MODES, 'synthetic'), 'synthetic')
        self.assertEqual(profile.choice({}, 'QUILLMD_REGISTRATION', profile.REGISTRATION_MODES, 'open'), 'open')
        self.assertEqual(profile.choice({}, 'QUILLMD_STRIPE_MODE', profile.STRIPE_MODES, 'test'), 'test')
        self.assertFalse(profile.flag({}, 'QUILLMD_MFA_REQUIRED_ALL'))
        self.assertEqual(profile.welcome_credit({}), Decimal('10'))
        # `NAME=` in an environment file is unset, not an unknown value.
        self.assertEqual(profile.choice({'QUILLMD_DATA_MODE': ' '}, 'QUILLMD_DATA_MODE', profile.DATA_MODES, 'synthetic'), 'synthetic')

    def test_an_unrecognised_value_refuses_instead_of_selecting_a_mode(self):
        for name, allowed, value in [('QUILLMD_DATA_MODE', profile.DATA_MODES, 'REAL'),
                                     ('QUILLMD_DATA_MODE', profile.DATA_MODES, 'production'),
                                     ('QUILLMD_REGISTRATION', profile.REGISTRATION_MODES, 'closed'),
                                     ('QUILLMD_STRIPE_MODE', profile.STRIPE_MODES, 'Live'),
                                     ('QUILLMD_DEEPGRAM_SMART_FORMAT', profile.BOOLEAN_WORDS, '1')]:
            with self.subTest(name=name, value=value), self.assertRaisesRegex(profile.ProfileError, name):
                profile.choice({name: value}, name, allowed, allowed[0])
        for value in ('yes', 'true', '2'):
            with self.subTest(flag=value), self.assertRaises(profile.ProfileError):
                profile.flag({'QUILLMD_MFA_REQUIRED_ALL': value}, 'QUILLMD_MFA_REQUIRED_ALL')

    def test_welcome_credit_is_exact_bounded_and_in_whole_cents(self):
        self.assertEqual(profile.welcome_credit({'QUILLMD_WELCOME_CREDIT': '12.50'}), Decimal('12.50'))
        self.assertEqual(profile.welcome_credit({'QUILLMD_WELCOME_CREDIT': '0'}), Decimal('0'))
        for value in ('-1', '10.001', 'NaN', 'Infinity', '500.01', 'ten', '1e9'):
            with self.subTest(value=value), self.assertRaises(profile.ProfileError):
                profile.welcome_credit({'QUILLMD_WELCOME_CREDIT': value})
        self.assertEqual(profile.dollars(Decimal('10')), '$10')
        self.assertEqual(profile.dollars(Decimal('12.5')), '$12.50')


class RealModeRequirements(SimpleTestCase):
    def test_the_complete_profile_has_no_problem(self):
        self.assertEqual(problems(COMPLETE_REAL), [])

    def test_each_missing_or_unsafe_requirement_is_named(self):
        for expected, change in REFUSALS:
            with self.subTest(expected=expected, change=change):
                found = problems(environment(change))
                self.assertTrue(found)
                self.assertTrue(all(expected in line or 'COOKIE_SECURE' in line for line in found), found)
                self.assertTrue(any(line.startswith(expected) for line in found), found)
                self.assertFalse(any(PRIVATE_VALUE in line for line in found))

    def test_secure_cookies_are_checked_as_computed(self):
        """The cookie flags are passed in from settings, so a future derivation that drops them still refuses."""
        found = profile.real_mode_problems(COMPLETE_REAL, allowed_hosts=ALLOWED, session_cookie_secure=False, csrf_cookie_secure=False,
                                           email_mode='resend', app_base_url='https://app.quillmd.com')
        self.assertEqual([line.split()[0] for line in found], ['SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE'])

    def test_the_values_settings_will_use_are_checked_not_a_tidied_copy(self):
        """settings.py does not strip QUILLMD_EMAIL_MODE or QUILLMD_APP_BASE_URL: 'resend ' selects the FILE
        backend and a padded origin fails every emailed link. Both must refuse at start, not pass and fail later."""
        for name, value in (('QUILLMD_EMAIL_MODE', 'resend '), ('QUILLMD_APP_BASE_URL', ' https://app.quillmd.com')):
            with self.subTest(name=name):
                self.assertTrue(any(line.startswith(name) for line in problems(environment({name: value}))))
                result = start(environment({name: value}))
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any(item.startswith(name) for item in refusal_items(result.stderr)), result.stderr[-300:])


class RealModeRefusesToStart(SimpleTestCase):
    def test_default_start_is_synthetic(self):
        result = start({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'synthetic': True, 'mode': 'synthetic'})

    def test_complete_real_profile_starts_real(self):
        result = start(COMPLETE_REAL, '{"synthetic": s.SYNTHETIC_ONLY, "mode": s.QUILLMD_DATA_MODE, "secure": [s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE], "mfa": s.QUILLMD_MFA_REQUIRED_ALL, "registration": s.QUILLMD_REGISTRATION, "mip": s.QUILLMD_DEEPGRAM_MIP_OPT_OUT}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'synthetic': False, 'mode': 'real', 'secure': [True, True], 'mfa': True,
                                                     'registration': 'invite', 'mip': 'true'})

    def test_every_refusal_stops_the_settings_import(self):
        for expected, change in REFUSALS:
            with self.subTest(expected=expected, change=change):
                result = start(environment(change))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)
                items = refusal_items(result.stderr)
                self.assertTrue(any(item.startswith(expected) for item in items), result.stderr[-400:])
                self.assertNotIn(PRIVATE_VALUE, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_an_unknown_data_mode_refuses(self):
        for value in ('REAL', 'live', 'production'):
            with self.subTest(value=value):
                result = start({'QUILLMD_DATA_MODE': value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('QUILLMD_DATA_MODE must be one of: synthetic, real.', result.stderr)


class HealthReportsRealMode(SimpleTestCase):
    @override_settings(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')
    def test_real_mode_reports_real(self):
        self.assertEqual(self.client.get('/health/').json()['data_mode'], 'real')

    @override_settings(SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='synthetic')
    def test_synthetic_mode_is_unchanged(self):
        self.assertEqual(self.client.get('/health/').json()['data_mode'], 'synthetic-only')


ISOLATED = dict(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
                STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                          'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
REAL = dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')


@override_settings(**ISOLATED)
class RealModeRemovesSyntheticAttestationsAndCopy(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='real-mode', email='real-mode@clinic.invalid', verified_at=timezone.now())
        self.department = Department.objects.create(organization=Organization.objects.create(name='Real mode'), name='Real mode')
        Membership.objects.create(user=self.user, department=self.department, role='clinician')

    def test_attestations_are_required_in_synthetic_mode_and_absent_in_real_mode(self):
        for mode, present in ((dict(SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='synthetic'), True), (REAL, False)):
            with self.subTest(mode=mode['QUILLMD_DATA_MODE']), override_settings(**mode):
                self.assertEqual('synthetic_only' in RegisterForm().fields, present)
                self.assertEqual('synthetic_only' in PatientForm(user=self.user).fields, present)
                self.assertEqual('synthetic_only' in EncounterForm(user=self.user).fields, present)
                # A template must be a BLANK form in either mode; that statement is not a synthetic one.
                self.assertEqual(UploadForm(user=self.user).fields['synthetic_only'].label, 'This is a blank form with no patient data.')
                self.assertEqual('synthetic' in VoiceForm().fields['consent'].label, present)

    def test_a_real_patient_is_created_without_the_synthetic_statement(self):
        self.client.force_login(self.user)
        data = {'department': self.department.pk, 'display_name': 'Patient One', 'reference': 'P-1'}
        self.client.post('/patients/', data)
        self.assertFalse(Patient.objects.exists(), 'synthetic mode still requires the attestation')
        with override_settings(**REAL):
            self.assertEqual(self.client.post('/patients/', data).status_code, 302)
        self.assertTrue(Patient.objects.filter(reference='P-1').exists())

    def test_banner_and_synthetic_copy_disappear_in_real_mode(self):
        self.assertContains(self.client.get('/login/'), 'Use synthetic patient information.')
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'), 'environment-banner')
        with override_settings(**REAL):
            self.assertNotContains(self.client.get('/'), 'environment-banner')
            self.assertNotContains(self.client.get('/patients/'), 'synthetic', status_code=200)
            # 'Synthetic fixture' on this page describes QUILLMD_AI_MODE (the answer generator), not the data;
            # the data-mode copy is the patient prompt.
            page = self.client.get('/encounters/new/').content.decode()
            self.assertIn('A document needs a patient first.', page)
            self.assertNotIn('synthetic patient', page)
            self.assertNotIn('fictional', page)
            self.client.logout()
            for path in ('/login/', '/recovery/', '/verification/resend/'):
                with self.subTest(path=path):
                    self.assertNotIn('synthetic', self.client.get(path).content.decode().lower())
