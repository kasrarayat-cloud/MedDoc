"""The web as ops/install.py configures it in live mode: CORTI_CREDENTIALS_FILE names the worker's credentials path,
and the file is not there, because only the worker mounts it.

Pre-install review, 2026-10-26: the installer gave the web no path, so get_provider() raised there, a setting or
billing change re-predicted, and the worker re-sent a failed or not-sent request (ARCHITECTURE 5.4 says it never
does). The pipeline suites patch get_provider for the web and the worker alike, so none of them could see it. Here
only the worker's send is stubbed; the web calls the real get_provider(). Synthetic data only; no network.
"""
import json
from unittest import mock

from django.test import Client, TestCase, override_settings

from studio import models
from studio.providers.corti import CortiProvider
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE

# ops/install.py CREDENTIALS_IN_CONTAINER: the worker's mount point. Nothing exists there in a test.
WORKER_CREDENTIALS_PATH = '/run/cpt-studio/corti-credentials.env'


class FailingCorti(CortiProvider):
    """The real adapter (its name, version and request bytes) with only the send stubbed, and failing."""

    def __init__(self):
        super().__init__(WORKER_CREDENTIALS_PATH)
        self.requests = []

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        return RawExchange(outcome='failed', sent=True, http_status=503, error='Service unavailable (synthetic).')


@override_settings(**LIVE, CORTI_CREDENTIALS_FILE=WORKER_CREDENTIALS_PATH)
class WebWithTheWorkersCredentialsPathTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.worker = FailingCorti()

    def work(self):
        with mock.patch('studio.jobs.get_provider', return_value=self.worker):
            drain()

    def test_setting_and_billing_changes_after_a_failed_send_recheck_and_send_nothing(self):
        response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        self.work()
        self.assertEqual(len(self.worker.requests), 1)
        for body in ({'billing_context': 'facility'}, {'setting': 'office'}):
            response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(body),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            self.work()
        self.assertEqual(len(self.worker.requests), 1)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual(encounter.current_assessment.provider_run.state, models.ProviderRun.FAILED)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
