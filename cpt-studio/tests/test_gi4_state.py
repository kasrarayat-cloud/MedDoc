"""GI round 4 harness, H5: the state battery. Real stages, real persistence, on the test database (the throwaway
127.0.0.1:55461 locally, CI's disposable PostgreSQL there); the provider is an in-process stand-in that answers each
request with the live service's RETAINED answer to that exact request (tests/fixtures/gi4/regression/, synthetic), so
a request that rebuilds byte-identically is answered as it was, and every send is counted.

Pinned here, on the regression encounters h4-04 and on a synthetic colonoscopy report:
- a context recorded under an earlier context version is remade under the current one, and the upgrade's own predict
  never sends; only a member's Resume does;
- a Stop then a Resume sends the request once;
- an answered date sends one dated request, byte-identical to the one the live service sent, and an identical re-save
  sends nothing;
- an identical retained request is reused workspace-wide, never sent again;
- a decision carries exactly when its proposal's fingerprint is equal, and is invalidated with a recorded reason
  otherwise;
- a second-review offer stays member-asked: no stage queues one, and asking sends it once.
"""
import datetime as dt
import json
from unittest import mock

from django.test import TestCase, override_settings

from ops.gi4 import regression, replay
from studio import jobs, models, review
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from studio.types import RawExchange
from tests.support import factories as f

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DOCS = regression.load_fixtures()
H404 = DOCS['h4-04']
STORED = {r['service_date']: r['request_sha256'] for r in H404['runs']}  # None: the dateless primary
COLON = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
         'Date of service: 10/19/2026\nPlace of service: ambulatory surgical center (POS 24)\n'
         'Endoscopist: Synthetic Endoscopist, MD (fictional)\nFindings: The colonoscope was advanced to the cecum. A 6 mm '
         'polyp in the sigmoid colon was removed with a cold snare.\nImpression: One polyp removed.\n')


class RetainedProvider:
    """The Corti adapter's request builder, and an answer from the retained runs: the stored response of the run whose
    request is byte-identical; any other request is answered with no codes (and counted as new)."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self):
        self.answers = {r['request_sha256']: json.dumps(r['response']).encode() for doc in DOCS.values()
                        for r in doc['runs'] if r['request_sha256'] and r['response'] is not None}
        self.sent = []

    def build_request(self, text, service_date):
        return build_coding_request(self.name, self.adapter_version, text, service_date, 10 ** 7)

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        data = self.answers.get(request.canonical_sha256, b'{"codes": [], "candidates": []}')
        import hashlib
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.01}, usage_basis='provider_reported_credits_not_usd')


def seed_reference(codes):
    """The replay's synthetic reference rows (ops/gi4/replay.py) for ``codes``, under the h4 assessments' sources."""
    for source in H404['reference_sources']:
        row = models.ReferenceSource.objects.create(
            key=source['key'], kind=source['kind'], publisher=source['publisher'], title=source['title'][:200],
            release=source['release'], url=source['url'], sha256=source['sha256'],
            retrieved_at=dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc),
            effective_start=dt.date.fromisoformat(source['effective_start']),
            effective_end=dt.date.fromisoformat(source['effective_end']), license_note=source['license_note'],
            scope_note=source['scope_note'], row_count=len(codes))
        for code in codes:
            models.ReferenceCodeFact.objects.create(source=row, code=code, facts=dict(
                replay.PFS_ROW if source['kind'] == 'cms-pfs' else replay.MUE_ROW))


@override_settings(**LIVE)
class StateBatteryTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = RetainedProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed_reference(('43251', '45378', '43239', '45385', '99204', '99213'))

    # --- helpers ---
    def upload(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def run_one(self, kind):
        job = jobs.claim_next()
        self.assertEqual(job.kind, kind)
        jobs.run_job(job)

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    def answer(self, encounter_id, value):
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': value})
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()

    def no_review2(self, encounter_id):
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           purpose=models.ProviderRun.SECOND_REVIEW).exists())

    def proposal(self, encounter_id, code):
        return next(p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code)

    # --- the battery ---
    def test_an_answered_date_sends_one_identical_request_and_a_resave_sends_nothing(self):
        encounter_id = self.upload(H404['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # the dateless primary, byte-identical to the live one
        self.answer(encounter_id, '2026-10-19')
        self.assertEqual(self.provider.sent, [STORED[None], STORED['2026-10-19']])
        self.answer(encounter_id, '2026-10-19')  # an identical re-save
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.proposal(encounter_id, '43251')['status'], 'ready')
        self.no_review2(encounter_id)

    def test_a_retained_request_is_reused_workspace_wide(self):
        first = self.upload(H404['text'])
        self.drain()
        second = self.upload(H404['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # sent once for both encounters
        run = models.ProviderRun.objects.get(encounter_id=second)
        self.assertEqual((run.state, run.sent, run.request_sha256), (models.ProviderRun.SUCCEEDED, False, STORED[None]))
        self.assertEqual(run.reused_from.encounter_id, models.Encounter.objects.get(pk=first).pk)

    def test_a_decision_carries_exactly_when_its_fingerprint_is_equal(self):
        encounter_id = self.upload(H404['text'])
        self.drain()
        self.answer(encounter_id, '2026-10-19')
        item = self.proposal(encounter_id, '43251')
        self.assertIn('approve', item['allowed_actions'])
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': item['id'], 'action': 'approve',
                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
        self.assertEqual(response.status_code, 201, response.content)
        approved = models.Decision.objects.get(encounter_id=encounter_id)
        self.answer(encounter_id, '2026-10-19')  # identical re-save: same fingerprint, the decision carries
        carried = models.Decision.objects.get(carried_from=approved)
        self.assertEqual(carried.proposal_fingerprint, approved.proposal_fingerprint)
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision=approved).exists())
        sends = len(self.provider.sent)
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'hospital_outpatient'})
        self.assertEqual(response.status_code, 201, response.content)  # a context change 43251 does not depend on
        self.drain()
        again = models.Decision.objects.get(carried_from=carried)  # its fingerprint is equal: the decision carries
        self.assertEqual(again.proposal_fingerprint, carried.proposal_fingerprint)
        removed, _ = models.ReferenceCodeFact.objects.filter(code='43251', source__kind='cms-pfs').delete()
        self.assertEqual(removed, 1)  # the fee-schedule row 43251's checks read is gone: a check changes
        self.answer(encounter_id, '2026-10-19')  # the same date again: a re-assessment, nothing to send
        self.assertEqual(len(self.provider.sent), sends)
        self.assertFalse(models.Decision.objects.filter(carried_from=again).exists())
        invalidation = models.DecisionInvalidation.objects.get(decision=again)
        self.assertTrue(invalidation.reason.strip())
        now = models.Proposal.objects.get(pk=self.proposal(encounter_id, '43251')['id'])
        self.assertNotEqual(now.fingerprint, again.proposal_fingerprint)

    def test_an_earlier_context_version_is_remade_and_the_upgrades_predict_never_sends(self):
        earlier = jobs.EARLIER_CONTEXT_VERSIONS[-1]
        labels = {'CONTEXT_VERSION': earlier, 'EARLIER_CONTEXT_VERSIONS': jobs.EARLIER_CONTEXT_VERSIONS[:-1]}
        dated = {name: fact for name, fact in __import__('studio.gi.context', fromlist=['x']).extract_context(
            H404['text']).items()}
        from studio.types import Fact
        dated['service_date'] = Fact('service_date', '2026-10-19', 'document', (), '')
        encounter_id = self.upload(H404['text'])
        with mock.patch.multiple(jobs, **labels):  # the earlier rules read the date as documented, and send it
            self.run_one(models.Job.EXTRACT)
            with mock.patch('studio.gi.context.extract_context', return_value=dated):
                self.run_one(models.Job.ANALYZE)
            self.run_one(models.Job.PREDICT)
        self.assertEqual(self.provider.sent, [STORED['2026-10-19']])
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.current_context.version, earlier)
        self.drain()  # the swap: this code reads the queued assess, remakes the context, and the upgrade's predict stops
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'missing')
        self.assertTrue(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.remade').exists())
        self.assertEqual(self.provider.sent, [STORED['2026-10-19']])  # nothing sent by the upgrade's predict
        response = self.post(f'/api/encounters/{encounter_id}/resume')  # only a member's Resume sends
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED['2026-10-19'], STORED[None]])

    def test_stop_then_resume_sends_once(self):
        encounter_id = self.upload(H404['text'])
        self.run_one(models.Job.EXTRACT)
        self.run_one(models.Job.ANALYZE)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.drain()
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])

    def test_a_second_review_offer_stays_member_asked(self):
        encounter_id = self.upload(COLON)  # the stand-in answers this request with no codes: the service is unresolved
        self.drain()
        self.no_review2(encounter_id)  # no stage queued one
        offer = self.detail(encounter_id)['second_review']
        self.assertTrue(offer['available'], offer)
        sends = len(self.provider.sent)
        response = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)  # asked: sent once
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           purpose=models.ProviderRun.SECOND_REVIEW).count(), 1)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)
