"""GI round 4, package PD, the H5 state rows: real stages, real persistence, on the test database (the throwaway
127.0.0.1:55461 locally, CI's disposable PostgreSQL there), with the H5 battery's in-process stand-in provider (it
answers a request byte-identical to one the live service sent with that retained answer, any other with no codes, and
counts every send).

- h4-01 ("Date seen: 10/26/2026", read now as the evidence of the date asked): the dateless primary is the stored one; a
  member's 1998-01-01 is held and sends nothing; 2026-10-26 sends the stored dated request once; an identical re-save
  sends nothing.
- rule (a), a synthetic report whose installed reading sends 2026-10-18 while "Date performed: 10/19/2026" stands beside
  it: the primary request is now dateless (the cost of the ask: one dateless request), 2026-10-19 is held and sends
  nothing, 2026-10-18 sends one dated request, byte-identical to the one installed sent, and a re-save sends nothing.
Every document is synthetic.
"""
import json

from django.test import TestCase, override_settings
from unittest import mock

from studio import jobs, models
from studio.gi.context import is_member_conflict
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from tests.support import factories as f
from tests.test_gi4_state import DOCS, LIVE, RetainedProvider, seed_reference

H401 = DOCS['h4-01']
STORED = {r['service_date']: r['request_sha256'] for r in H401['runs'] if r['request_sha256']}
X_Y = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\nDate of service: '
       '10/18/2026\nDate performed: 10/19/2026\nPlace of service: ambulatory surgical center (POS 24)\nEndoscopist: '
       'Synthetic Endoscopist, MD (fictional)\nFindings: The colonoscope was advanced to the cecum. A 6 mm polyp in the '
       'sigmoid colon was removed with a cold snare.\nSigned: Synthetic Endoscopist, MD (fictional), 10/19/2026\n')


def request_sha(text, day):
    import datetime as dt
    return build_coding_request('corti', ADAPTER_VERSION, text, dt.date.fromisoformat(day) if day else None,
                                10 ** 7).canonical_sha256


@override_settings(**LIVE)
class WideDateStateTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = RetainedProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed_reference(('99204', '45385', '45378'))

    def upload(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def answer(self, encounter_id, value):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context',
                                        data=json.dumps({'service_date': value}), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()

    def service_date(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id).current_context.facts['service_date']

    def test_h4_01_takes_only_the_date_it_states(self):
        encounter_id = self.upload(H401['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # the dateless primary, byte-identical to the live one
        fact = self.service_date(encounter_id)
        self.assertEqual((fact['origin'], [e['text'] for e in fact['evidence']]), ('missing', ['Date seen: 10/26/2026']))
        self.answer(encounter_id, '1998-01-01')  # held: no date it could carry, nothing built or sent
        self.assertEqual(self.provider.sent, [STORED[None]])
        self.assertTrue(is_member_conflict(self.service_date(encounter_id)))
        self.answer(encounter_id, '2026-10-26')
        self.assertEqual(self.provider.sent, [STORED[None], STORED['2026-10-26']])
        self.answer(encounter_id, '2026-10-26')  # an identical re-save
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.service_date(encounter_id)['origin'], 'user')

    def test_rule_a_asks_and_takes_only_the_installed_date(self):
        encounter_id = self.upload(X_Y)
        self.drain()
        self.assertEqual(self.provider.sent, [request_sha(X_Y, None)])  # asked: the primary carries no date
        fact = self.service_date(encounter_id)
        self.assertEqual(fact['origin'], 'conflict')
        self.assertTrue(fact['note'].startswith('The document also states “Date performed: 10/19/2026”'))
        self.answer(encounter_id, '2026-10-19')  # the wide label's date: held, nothing sent
        self.assertEqual(len(self.provider.sent), 1)
        self.assertTrue(is_member_conflict(self.service_date(encounter_id)))
        self.answer(encounter_id, '2026-10-18')  # installed's own date: one dated request, as installed sent it
        self.assertEqual(self.provider.sent, [request_sha(X_Y, None), request_sha(X_Y, '2026-10-18')])
        self.answer(encounter_id, '2026-10-18')
        self.assertEqual(len(self.provider.sent), 2)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())
