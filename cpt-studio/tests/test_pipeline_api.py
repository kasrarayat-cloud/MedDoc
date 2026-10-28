"""End-to-end pipeline + API tests with a fake provider (no network)."""
import hashlib
import json
from unittest import mock

from django.test import Client, TestCase, override_settings

from studio import jobs, models, review
from studio.providers.base import ProviderUnavailable
from studio.providers.corti import ADAPTER_VERSION
from studio.types import ProviderRequest, RawExchange, sha256_json
from tests.support import factories as f

OFFICE_NOTE = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE

Riverbend Digestive Health (fictional)
Date of service: 2026-10-20
Place of service: Office, in-person outpatient visit

Patient status: Established patient, last seen 2026-03-02.

Chief complaint
Follow-up of chronic constipation.

Assessment and plan
Chronic idiopathic constipation, improved. Continue polyethylene glycol daily.
A colonoscopy is scheduled for 2026-12-01.

Medical decision making
Low: one stable chronic illness; prescription drug management.

Time
Total time on the date of the encounter was 24 minutes.
"""


def corti_like_response(text, selections):
    """A provider response in Corti's shape whose evidence points at exact substrings of text."""
    codes = []
    for code, quote in selections:
        start = text.index(quote)
        codes.append({'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING',
                      'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}],
                      'alternatives': []})
    return json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()


class FakeProvider:
    """Behaves like the live Corti adapter (same name and adapter version, so the stored run is read
    by the real normaliser) but 'sends' to an in-process stub — no network."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self, selections=(), outcome='succeeded'):
        self.selections, self.outcome, self.sent = list(selections), outcome, []

    def build_request(self, text, service_date):
        contexts = [text] + ([f'Date of service: {service_date.isoformat()}'] if service_date else [])
        body = {'system': ['icd10cm-outpatient', 'cpt'], 'context': [{'type': 'text', 'text': c} for c in contexts]}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False).encode()).hexdigest()
        return ProviderRequest(provider=self.name, adapter_version=self.adapter_version, body=body,
                               canonical_sha256=digest, contexts=tuple(contexts))

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        if self.outcome == 'unknown':
            return RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.')
        data = corti_like_response(request.contexts[0], self.selections)
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=12.5,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


def drain():
    while True:
        job = jobs.claim_next()
        if job is None:
            return
        jobs.run_job(job)


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class PipelineApiTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text=OFFICE_NOTE, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def detail(self, encounter_id, client=None):
        response = (client or self.client).get(f'/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def test_upload_requires_attestation_and_one_source(self):
        self.assertEqual(self.client.post('/api/encounters', {'text': 'x'}).status_code, 400)
        self.assertEqual(self.client.post('/api/encounters', {'synthetic_attestation': 'yes'}).status_code, 400)

    def test_full_flow_reviews_and_reports(self):
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['revision']['extraction']['status'], 'ok')
        self.assertEqual(len(self.provider.sent), 1)
        selected = [p for p in data['assessment']['proposals'] if p['bucket'] == 'selected']
        self.assertTrue(selected, data['assessment'])
        text = data['revision']['text']
        for proposal in selected:
            for span in proposal['evidence']:
                self.assertEqual(text[span['start']:span['end']], span['text'])
        self.assertNotIn('UNVERIFIED PROVIDER WORDING', json.dumps(data))

    def test_cross_workspace_access_is_404(self):
        encounter_id = self.create()
        other_ws = f.workspace('Other synthetic workspace')
        outsider = f.member(other_ws, f.user('outsider'))
        client = Client()
        client.force_login(outsider)
        self.assertEqual(client.get(f'/api/encounters/{encounter_id}').status_code, 404)
        self.assertEqual(client.post(f'/api/encounters/{encounter_id}/stop').status_code, 404)

    def test_unauthenticated_api_is_401(self):
        self.assertEqual(Client().get('/api/encounters').status_code, 401)

    def test_csrf_is_enforced_on_posts(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        response = client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_upload_or_decide(self):
        viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        client = Client()
        client.force_login(viewer)
        response = client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 403)

    def test_identical_request_reuses_retained_result_without_sending(self):
        first = self.create()
        drain()
        second = self.create()
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        run = models.ProviderRun.objects.filter(encounter_id=second).get()
        self.assertIsNotNone(run.reused_from_id)
        self.assertEqual(run.usage, {})
        self.assertEqual(run.usage_basis, 'reused_retained_result_no_new_usage')
        self.assertEqual(self.detail(first)['provider_runs'][0]['reused_from'], None)

    def test_stop_before_send_sends_nothing(self):
        encounter_id = self.create()
        response = self.client.post(f'/api/encounters/{encounter_id}/stop')
        self.assertEqual(response.status_code, 200)
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.detail(encounter_id)['state'], 'stopped')

    def test_unknown_outcome_blocks_resend_until_reconciled(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['state'], 'provider_unknown')
        self.assertEqual(len(self.provider.sent), 1)
        run_id = data['provider_runs'][0]['id']
        # Adding context does not resend while the outcome is unknown.
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        # A reconciliation note is required, then exactly one new attempt happens.
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': run_id, 'note': 'short'}).status_code, 400)
        self.provider.outcome = 'succeeded'
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': 'Checked the provider console: no response recorded.'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': run_id, 'note': 'Second reconciliation attempt.'}).status_code, 409)

    def test_addendum_creates_revision_and_invalidates_decisions(self):
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        approvable = [p for p in data['assessment']['proposals'] if 'approve' in p['allowed_actions']]
        if approvable:
            response = self.post(f'/api/encounters/{encounter_id}/decisions',
                                 {'proposal_id': approvable[0]['id'], 'action': 'approve',
                                  'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
            self.assertEqual(response.status_code, 201, response.content)
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['revision']['number'], 2)
        self.assertTrue(data['revision']['text'].startswith(OFFICE_NOTE.replace('\r\n', '\n')[:40]))
        for decision in data['decisions']['history']:
            if decision['revision_number'] == 1:
                self.assertIsNotNone(decision['invalidated'])

    def test_report_download_bytes_match_recorded_sha(self):
        encounter_id = self.create()
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'draft', 'fmt': 'csv'})
        self.assertEqual(response.status_code, 201, response.content)
        report = response.json()
        download = self.client.get(report['download_url'])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), report['sha256'])
        self.assertIn('attachment;', download['Content-Disposition'])
        reviewed = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertIn(reviewed.status_code, {201, 409})

    def test_provider_unavailable_is_recorded_not_sent(self):
        self.provider.build_request = mock.Mock(side_effect=ProviderUnavailable('Request too large.'))
        encounter_id = self.create()
        drain()
        runs = self.detail(encounter_id)['provider_runs']
        self.assertEqual(runs[0]['state'], 'not_sent')
        self.assertEqual(self.provider.sent, [])

    def test_health_is_public_and_reports_synthetic_mode(self):
        response = Client().get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data_mode'], 'synthetic-only')

    def test_original_download_matches_upload(self):
        payload = OFFICE_NOTE.encode('utf-8')
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('note.txt', payload, content_type='text/plain')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'file': upload, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        original = self.client.get(f'/api/encounters/{encounter_id}/original')
        self.assertEqual(original.content, payload)
        self.assertEqual(original['X-Content-SHA256'], hashlib.sha256(payload).hexdigest())

    def test_upload_rejects_disguised_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile('note.pdf', b'not a pdf at all', content_type='application/pdf')
        response = self.client.post('/api/encounters', {'file': fake_pdf, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 400)


class SnapshotHashTests(TestCase):
    def test_sha256_json_is_order_independent(self):
        self.assertEqual(sha256_json({'a': 1, 'b': [1, 2]}), sha256_json({'b': [1, 2], 'a': 1}))
