"""The web plumbing's own boundaries (studio.views, studio.api): the health check is public and says the data mode; text the
database cannot store answers a JSON 400, never a 500; a title has such characters replaced; a sign-in with them fails
normally and is still counted for the throttle. Synthetic data only.

Moved from the earlier pipeline's suites (tests/test_pipeline_api.py and the round-1 refutation regressions,
tests/test_repairs_pipeline.py: security:2 and ingest:13) when lane E removed them; the assertions are unchanged.
"""
from django.test import Client, TestCase, override_settings

from studio import models
from tests.support import coding as f
from tests.test_frontend import PLAIN_STATIC


class HealthTests(TestCase):
    def test_health_is_public_and_reports_synthetic_mode(self):
        response = Client().get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data_mode'], 'synthetic-only')


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
