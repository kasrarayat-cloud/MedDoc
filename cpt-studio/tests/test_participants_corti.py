"""Corti's exchange records the coding URL it called, environment included (HARNESS.md 6), on every outcome that may
have reached it, and none when the coding request provably never left. Corti's request body, its hash and its
normalization are unchanged (I1): the proven Taylor Reed request still hashes as recorded. Offline and synthetic."""
from __future__ import annotations

import json
from datetime import date

import requests
from urllib3.exceptions import MaxRetryError, NewConnectionError

from studio.providers import CortiProvider
from studio.providers import corti as corti_module

from tests.test_participants_support import FakeResponse, FakeSession, OfflineTestCase, write_file
from tests.test_providers import FIXTURES as CORTI_FIXTURES
from tests.test_providers import NOTE, SERVICE_DATE, TAYLOR_REQUEST_SHA256, dotenv, token_response

CODING = {'us': 'https://api.us.corti.app/v2/tools/coding/', 'eu': 'https://api.eu.corti.app/v2/tools/coding/'}


class CortiEndpointTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.raw = (CORTI_FIXTURES / 'taylor-reed.response.raw.json').read_bytes()

    def send(self, *steps, environment='us'):
        credentials = self.tmp / f'corti-{environment}-{len(list(self.tmp.iterdir()))}.env'
        write_file(credentials, dotenv(CORTI_ENVIRONMENT=environment))
        session = FakeSession(*steps)
        provider = CortiProvider(credentials, session_factory=lambda: session)
        return provider.send(provider.build_request(NOTE, SERVICE_DATE), deadline_s=180), session

    def test_the_url_called_is_recorded_on_every_outcome_that_may_have_reached_it(self):
        for environment in ('us', 'eu'):
            cases = {'succeeded': FakeResponse(200, self.raw), 'failed': FakeResponse(500, b'{}'),
                     'unknown': requests.exceptions.ReadTimeout('synthetic')}
            for outcome, step in cases.items():
                with self.subTest(environment=environment, outcome=outcome):
                    exchange, session = self.send(token_response(), step, environment=environment)
                    self.assertEqual((exchange.outcome, exchange.sent), (outcome, True))
                    self.assertEqual(exchange.endpoint, CODING[environment])
                    self.assertEqual(session.calls[1]['url'], exchange.endpoint)
                    self.assertEqual((exchange.requested_model, exchange.returned_model, exchange.response_id),
                                     ('', '', ''))  # Corti's API names no model and returns no object id

    def test_a_read_failure_after_the_request_left_records_it_too(self):
        response = FakeResponse(200, chunks=[self.raw[:10], requests.exceptions.ChunkedEncodingError('synthetic')])
        exchange, _ = self.send(token_response(), response)
        self.assertEqual((exchange.outcome, exchange.http_status, exchange.endpoint),
                         ('unknown', 200, CODING['us']))

    def test_nothing_is_recorded_when_the_coding_request_never_left(self):
        never = requests.exceptions.ConnectionError(MaxRetryError(None, '/v2/tools/coding/',
                                                                  NewConnectionError(None, 'synthetic refusal')))
        for label, steps in (('never connected', (token_response(), never)),
                             ('authentication refused', (FakeResponse(401, b'{}'),))):
            with self.subTest(label):
                exchange, _ = self.send(*steps)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.endpoint), ('not_sent', False, ''))

    def test_the_request_and_its_hash_are_unchanged(self):
        retained = json.loads((CORTI_FIXTURES / 'taylor-reed.request.json').read_bytes())
        request = CortiProvider(self.tmp / 'never-read.env').build_request(retained['context'][0]['text'], None)
        self.assertEqual((request.body, request.canonical_sha256), (retained, TAYLOR_REQUEST_SHA256))
        self.assertEqual(corti_module.ADAPTER_VERSION, 'corti-coding-v2@cptstudio-1')
        dated = CortiProvider(self.tmp / 'never-read.env').build_request(NOTE, date(2026, 10, 21))
        self.assertEqual(dated.body, {'system': ['icd10cm-outpatient', 'cpt'],
                                      'context': [{'type': 'text', 'text': NOTE},
                                                  {'type': 'text', 'text': 'Date of service: 2026-10-21'}]})
