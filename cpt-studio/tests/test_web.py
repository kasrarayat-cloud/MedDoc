"""The web plumbing's own boundaries (studio.views, studio.api): the health check is public and says the data mode - and,
since release 1 (B7), tells a request that came through nginx a digest of the build instead of the build; text the
database cannot store answers a JSON 400, never a 500; a title has such characters replaced; a sign-in with them fails
normally and is still counted for the throttle. Synthetic data only.

Moved from the earlier pipeline's suites (tests/test_pipeline_api.py and the round-1 refutation regressions,
tests/test_repairs_pipeline.py: security:2 and ingest:13) when lane E removed them; the assertions are unchanged.
"""
import hashlib

from django.test import Client, TestCase, override_settings

from studio import models, views
from tests.support import coding as f
from tests.test_frontend import PLAIN_STATIC


class HealthTests(TestCase):
    def test_health_is_public_and_reports_synthetic_mode(self):
        response = Client().get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data_mode'], 'synthetic-only')

    @override_settings(RELEASE_SHA='0123456789abcdef0123456789abcdef01234567')
    def test_through_nginx_the_health_check_names_a_digest_of_the_build_and_never_the_build(self):
        # B7: nginx sets X-Forwarded-For on every request it proxies; a probe of the web's own port carries none
        release = '0123456789abcdef0123456789abcdef01234567'
        digest = hashlib.sha256(('cpt-studio-release:' + release).encode()).hexdigest()[:16]
        for host in ('cpt.quillmd.com', 'admin.quillmd.com'):
            with self.subTest(host=host):
                proxied = Client(HTTP_HOST=host).get('/health/', HTTP_X_FORWARDED_FOR='203.0.113.9')
                self.assertEqual(proxied.status_code, 200)
                body = proxied.json()
                self.assertEqual(list(body), ['status', 'service', 'data_mode', 'release_digest', 'database'])
                self.assertEqual(body['release_digest'], digest)
                self.assertNotIn(release, proxied.content.decode())
                self.assertNotIn(release[:12], proxied.content.decode())
                direct = Client(HTTP_HOST=host).get('/health/').json()
                self.assertEqual(list(direct), ['status', 'service', 'data_mode', 'release', 'database'])
                self.assertEqual(direct['release'], release)
        self.assertEqual(views.release_digest(release), digest)
        self.assertEqual(len(views.release_digest('development-unrecorded')), 16)

    @override_settings(RELEASE_SHA='0123456789abcdef0123456789abcdef01234567', STORAGES=PLAIN_STATIC)
    def test_the_operator_sign_in_page_names_no_build(self):
        page = Client(HTTP_HOST='admin.quillmd.com').get('/login/')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('0123456789ab', page.content.decode())
        self.assertNotIn('release', page.content.decode())


class InputBoundaryTests(TestCase):
    """security:2 and ingest:13 - text the database cannot store answers a JSON 400, never a 500."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws)
        self.client.force_login(self.reviewer)

    def test_nul_in_pasted_text_is_refused_with_json(self):
        response = self.client.post('/api/encounters', {'text': 'Synthetic\x00 note.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('NUL', response.json()['error'])
        self.assertFalse(models.Encounter.objects.exists())

    def test_nul_in_title_is_removed(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': f.NOTE, 'title': 'a\x00b',
                                                            'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(models.Encounter.objects.get(pk=response.json()['id']).title, 'a b')

    @override_settings(STORAGES=PLAIN_STATIC)  # renders the login page; a fresh checkout has no static manifest
    def test_login_with_nul_in_username_fails_normally_and_is_counted(self):
        anonymous = Client(enforce_csrf_checks=False)
        response = anonymous.post('/login/', {'username': 'reviewer\x00', 'password': 'synthetic-pass-123!'})
        self.assertEqual(response.status_code, 400)
        attempt = models.LoginAttempt.objects.get()
        self.assertEqual(attempt.username, 'reviewer�')
        self.assertFalse(attempt.succeeded)
