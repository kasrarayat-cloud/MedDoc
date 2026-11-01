"""GI round 4, package PO, H5: the offers PO adds stay member-asked. Real stages and persistence on the test database
(the throwaway 127.0.0.1:55461 locally, CI's disposable PostgreSQL there); the provider is H5's in-process stand-in that
answers each request with the live service's RETAINED answer to that exact request (tests/test_gi4_state.py), and every
send is counted.

On h4-02 (PO-1: routing reads both families only silently) and h4-05 (PO-2: the EUS passage is history only by a section
that runs on across unread headings): the assessment offers the second review, no stage queues or sends one, asking
sends exactly one bounded request with the agreed date, and a second ask is refused. Every document is synthetic.
"""
import json
from unittest import mock

from django.test import TestCase, override_settings

from ops.gi4 import regression
from studio import jobs, models
from tests.support import factories as f
from tests.test_gi4_state import LIVE, RetainedProvider, seed_reference

DOCS = regression.load_fixtures()


@override_settings(**LIVE)
class MemberAskedOfferTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = RetainedProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed_reference(('43235', '43239', '45330', '45331', '43259', '43237'))

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

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    def offered(self, encounter_id):
        items = self.detail(encounter_id)['assessment']['completeness']['unresolved_items']
        return sorted([u['family'], u['reason'], u['second_review']] for u in items)

    def asked_once(self, encounter_id, items, day):
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           purpose=models.ProviderRun.SECOND_REVIEW).exists())
        offer = self.detail(encounter_id)['second_review']
        self.assertTrue(offer['available'], offer)
        self.assertEqual(sorted(offer['items']), sorted(items))
        sends = len(self.provider.sent)
        self.drain()  # nothing is queued, so draining sends nothing
        self.assertEqual(len(self.provider.sent), sends)
        response = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)  # asked: sent once
        run = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose=models.ProviderRun.SECOND_REVIEW)
        self.assertEqual(run.service_date.isoformat(), day)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)

    def test_h402_po1_offer_is_member_asked(self):
        encounter_id = self.upload(DOCS['h4-02']['text'])
        self.drain()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-21'})
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(self.offered(encounter_id), [['gi.egd', 'no_proposal', True],
                                                      ['gi.flex_sig', 'not_covered', True]])
        self.asked_once(encounter_id, ['upper endoscopy (documented as performed) has no supported proposal',
                                       'forceps biopsy at the rectosigmoid in the flexible sigmoidoscopy'], '2026-10-21')

    def test_h405_po2_offer_is_member_asked(self):
        encounter_id = self.upload(DOCS['h4-05']['text'])
        self.drain()
        self.assertEqual(self.offered(encounter_id), [['gi.eus', 'no_proposal', True]])
        self.asked_once(encounter_id, ['endoscopic ultrasound (documented as performed) has no supported proposal'],
                        '2026-10-15')
