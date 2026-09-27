"""Per-client rate limits behind the trusted proxy.

Behind the loopback proxy every request arrives from 127.0.0.1, so a limit keyed on REMOTE_ADDR is one
bucket for the whole platform: five sign-ups or forty sign-in attempts from anybody locked out everybody.
With QUILLMD_TRUST_PROXY the key is the right-most X-Forwarded-For entry, the one our proxy wrote.
"""
from pathlib import Path
import tempfile

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.models import LoginAttempt, User
from core.security import client_address, digest

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PROXY = '127.0.0.1'


def request(forwarded=None, remote=PROXY):
    extra = {'REMOTE_ADDR': remote}
    if forwarded is not None:
        extra['HTTP_X_FORWARDED_FOR'] = forwarded
    return RequestFactory().post('/login/', **extra)


class ClientAddress(SimpleTestCase):
    @override_settings(QUILLMD_TRUST_PROXY=False)
    def test_without_trusted_proxy_the_forwarded_header_is_never_read(self):
        self.assertEqual(client_address(request('203.0.113.9')), PROXY)
        self.assertEqual(client_address(request()), PROXY)

    @override_settings(QUILLMD_TRUST_PROXY=True)
    def test_the_right_most_entry_is_the_client_and_everything_left_of_it_is_ignored(self):
        self.assertEqual(client_address(request('203.0.113.9')), '203.0.113.9')
        self.assertEqual(client_address(request('10.9.8.7, 203.0.113.9')), '203.0.113.9')
        self.assertEqual(client_address(request('198.51.100.1,  203.0.113.9 ')), '203.0.113.9')
        self.assertEqual(client_address(request('2001:DB8::1')), '2001:db8::1')

    @override_settings(QUILLMD_TRUST_PROXY=True)
    def test_an_unusable_entry_falls_back_to_the_shared_proxy_bucket(self):
        """Fail toward the STRICTER shared bucket, never toward a fresh one per garbage value."""
        for forwarded in (None, '', 'unknown', '203.0.113.9, not-an-ip', '203.0.113.9,', '203.0.113.9:443'):
            with self.subTest(forwarded=forwarded):
                self.assertEqual(client_address(request(forwarded)), PROXY)


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, QUILLMD_REGISTRATION='open', STORAGES=STORAGES,
                   QUILLMD_EMAIL_MODE='file', EMAIL_BACKEND='core.email_backend.PrivateFileEmailBackend')
class RegistrationBucketsFollowTheForwardedClient(TestCase):
    """Registration is the smallest limit (5 per address per 10 minutes), so it shows buckets fastest."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        mail = override_settings(EMAIL_FILE_PATH=Path(directory.name), QUILLMD_APP_BASE_URL='http://localhost:9130')
        mail.enable()
        self.addCleanup(mail.disable)
        self.count = 0

    def register(self, forwarded):
        self.count += 1
        password = 'Synthetic-Only-4821!private'
        return self.client.post('/register/', {'email': f'bucket{self.count}@synthetic.invalid', 'first_name': 'Synthetic',
                                               'last_name': 'Bucket', 'password1': password, 'password2': password,
                                               'synthetic_only': 'on'},
                                REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=forwarded)

    @override_settings(QUILLMD_TRUST_PROXY=True)
    def test_two_forwarded_clients_do_not_share_a_bucket(self):
        for _ in range(5):
            self.assertEqual(self.register('198.51.100.7').status_code, 302)
        self.assertEqual(self.register('198.51.100.7').status_code, 429)
        self.assertEqual(self.register('198.51.100.8').status_code, 302, 'a second client was locked out by the first')

    @override_settings(QUILLMD_TRUST_PROXY=True)
    def test_a_spoofed_left_most_entry_does_not_escape_the_limit(self):
        for number in range(5):
            self.assertEqual(self.register(f'10.0.0.{number}, 198.51.100.7').status_code, 302)
        for number in range(5, 8):
            with self.subTest(spoofed=f'10.0.0.{number}'):
                self.assertEqual(self.register(f'10.0.0.{number}, 198.51.100.7').status_code, 429)
        self.assertEqual(User.objects.count(), 5)

    @override_settings(QUILLMD_TRUST_PROXY=False)
    def test_without_trusted_proxy_every_forwarded_client_shares_remote_addr_as_before(self):
        for _ in range(5):
            self.assertEqual(self.register('198.51.100.7').status_code, 302)
        self.assertEqual(self.register('198.51.100.8').status_code, 429)


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_TRUST_PROXY=True)
class EveryAddressLimitUsesTheSameKey(TestCase):
    """Login, recovery and verification-resend key on the same client address as registration."""

    def test_login_recovery_and_resend_record_the_forwarded_client(self):
        forwarded = {'REMOTE_ADDR': PROXY, 'HTTP_X_FORWARDED_FOR': '10.1.1.1, 198.51.100.44'}
        self.client.post('/login/', {'email': 'nobody@synthetic.invalid', 'password': 'Synthetic-Only-4821!'}, **forwarded)
        self.client.post('/recovery/', {'email': 'nobody@synthetic.invalid'}, **forwarded)
        self.client.post('/verification/resend/', {'email': 'nobody@synthetic.invalid'}, **forwarded)
        for prefix in ('login-ip:', 'recovery-ip:', 'verification-resend-ip:'):
            with self.subTest(prefix=prefix):
                self.assertTrue(LoginAttempt.objects.filter(key=digest(prefix + '198.51.100.44')).exists())
                self.assertFalse(LoginAttempt.objects.filter(key=digest(prefix + PROXY)).exists())
                self.assertFalse(LoginAttempt.objects.filter(key=digest(prefix + '10.1.1.1')).exists())
