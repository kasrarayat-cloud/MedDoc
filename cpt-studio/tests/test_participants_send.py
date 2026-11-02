"""The participants' send discipline (HARNESS.md 3, 6, 8; I8, I9), for Astra and Fable alike: the exact call, every
outcome arm (not_sent only while nothing can have left; unknown after; failed for a non-200 with its body kept;
succeeded for a 200), the original-file placeholder verified and expanded only at send time, what each exchange
records, and that no credential reaches an exchange, a stored body or an error. Offline and synthetic
(test_participants_support): every send goes to a fake session."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import socket
import ssl
from unittest import mock

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ProtocolError, ReadTimeoutError

from studio.participants import anthropic_fable, openai_astra
from studio.participants import http as participants_http
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.providers.base import canonical_body, request_sha256
from studio.types import ProviderRequest

from tests.test_participants_support import (ANTHROPIC_KEY, ANTHROPIC_WORKSPACE, CLIENT_REQUEST_ID, NOTE, OPENAI_KEY,
                                             OPENAI_PROJECT, ORIGINAL, PAGES, PDF, SECRETS, FakeClock, FakeResponse,
                                             FakeSession, NetworkBlocked, OfflineTestCase, anthropic_env,
                                             fixture_bytes, openai_env, write_file)

UNKNOWN = 'The outcome is unknown; reconcile it before any new attempt.'


class _SendContract:
    """Every arm of the send discipline for one vendor; the concrete classes below name the vendor."""
    module = None
    adapter_class = None
    fixture = ''
    vendor = ''
    request_id_header = ''
    other_request_id_header = ''

    def env(self, **overrides):
        raise NotImplementedError

    def expected_headers(self, optional=None):
        raise NotImplementedError

    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.enterContext(mock.patch.object(participants_http, 'monotonic', self.clock))
        self.enterContext(mock.patch.object(self.module, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'vendor.env', self.env())
        self.raw = fixture_bytes(self.fixture)

    # --- helpers -------------------------------------------------------------------

    def make(self, session=None, **options):
        made = []

        def factory():
            made.append(session)
            return session
        adapter = self.adapter_class(self.credentials, session_factory=factory, **options)
        return adapter, made

    def send(self, *steps, deadline_s=330, request=None, kind='paste', original_bytes=None,
             client_request_id=CLIENT_REQUEST_ID, **options):
        session = FakeSession(*steps)
        adapter, made = self.make(session, **options)
        if request is None:
            request = adapter.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None)
        exchange = adapter.send(request, deadline_s=deadline_s, client_request_id=client_request_id,
                                original_bytes=original_bytes)
        self.assertNoSecrets(exchange, request)
        if made:
            self.assertTrue(session.closed)
        self.assertTrue(all(response.closed for response in session.responses))
        return exchange, session

    def assertNoSecrets(self, exchange, request=None):
        texts = [repr(exchange), exchange.error]
        if request is not None:
            texts.append(canonical_body(request.body).decode())
        for text in texts:
            for secret in SECRETS:
                self.assertNotIn(secret, text)

    def assertNotSent(self, exchange, expect='', requested_model=None):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.usage, exchange.endpoint, exchange.returned_model,
                          exchange.response_id), ('not_sent', False, None, None, '', {}, '', '', ''))
        self.assertIn(expect, exchange.error)
        if requested_model is not None:
            self.assertEqual(exchange.requested_model, requested_model)

    def assertUnknown(self, exchange, expect='', http_status=None):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.endpoint, exchange.requested_model),
                         ('unknown', True, http_status, None, '', self.module.ENDPOINT, self.module.MODEL))
        self.assertIn(f'The request may have reached {self.vendor}', exchange.error)
        self.assertIn(UNKNOWN, exchange.error)
        self.assertIn(expect, exchange.error)

    @staticmethod
    def at(body, path):
        for key in path:
            body = body[key]
        return body

    def set(self, body, path, value):
        self.at(body, path[:-1])[path[-1]] = value

    def ok(self, **headers):
        return FakeResponse(200, self.raw, headers={self.request_id_header: 'req_synthetic_0001', **headers})

    # --- success and the exact call ------------------------------------------------------

    def test_success_keeps_the_exact_bytes_and_records_what_was_called_and_what_answered(self):
        raw = self.raw
        exchange, session = self.send(FakeResponse(200, chunks=[raw[:100], raw[100:1500], raw[1500:]],
                                                   headers={self.request_id_header: 'req_synthetic_0001'}))
        envelope = json.loads(raw)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('succeeded', True, 200))
        self.assertEqual(exchange.response_bytes, raw)
        self.assertEqual(exchange.response_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual((exchange.usage, exchange.usage_basis), (envelope['usage'], 'provider_reported_tokens'))
        self.assertEqual((exchange.endpoint, exchange.requested_model, exchange.returned_model, exchange.response_id,
                          exchange.provider_request_id),
                         (self.module.ENDPOINT, self.module.MODEL, self.module.MODEL, envelope['id'],
                          'req_synthetic_0001'))
        self.assertEqual((exchange.error, exchange.latency_ms), ('', 0.0))
        self.assertEqual(len(session.calls), 1)

    def test_the_call_is_exactly_the_contract(self):
        session = FakeSession(self.ok())
        adapter, _ = self.make(session)
        request = adapter.build_request(NOTE, PAGES, 'paste', None)
        adapter.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        (call,) = session.calls
        self.assertEqual(call, {'url': self.module.ENDPOINT, 'data': canonical_body(request.body),
                                'headers': self.expected_headers(), 'timeout': (10, 300), 'allow_redirects': False,
                                'stream': True})
        self.assertEqual(hashlib.sha256(call['data']).hexdigest(), request.canonical_sha256)

    def test_the_optional_identifier_header_is_sent_only_when_configured(self):
        optional, value = self.optional
        self.credentials.unlink()
        write_file(self.credentials, self.env(**{optional: value}))
        exchange, session = self.send(self.ok())
        self.assertEqual(exchange.outcome, 'succeeded')
        self.assertEqual(session.calls[0]['headers'], self.expected_headers(value))

    # --- the original ----------------------------------------------------------------------

    def test_a_pdf_original_is_verified_and_expanded_only_at_send_time(self):
        session = FakeSession(self.ok())
        adapter, _ = self.make(session)
        request = adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        stored = copy.deepcopy(request.body)
        exchange = adapter.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID, original_bytes=PDF)
        self.assertEqual(exchange.outcome, 'succeeded')
        self.assertEqual(request.body, stored)  # the stored body still names the original by sha256 and size
        self.assertEqual(request_sha256(request.body), request.canonical_sha256)
        sent = session.calls[0]['data']
        self.assertEqual(len(sent), participants_http.expanded_length(len(canonical_body(stored)),
                                                                      self.placeholder(stored), self.prefix))
        decoded = json.loads(sent)
        rendered = self.prefix + base64.b64encode(PDF).decode('ascii')
        self.assertEqual(self.at(decoded, self.module.ORIGINAL_PATH), rendered)
        self.assertNotIn('\n', rendered)
        expected = copy.deepcopy(stored)
        self.set(expected, self.module.ORIGINAL_PATH, rendered)
        self.assertEqual(decoded, expected)  # nothing else differs from the stored body
        self.assertNotIn(b'$original_sha256', sent)

    def test_an_original_that_does_not_match_the_request_is_not_sent(self):
        altered = bytearray(PDF)
        altered[10] ^= 1
        cases = ((bytes(altered), 'does not match the sha256 and size'), (PDF + b'\n', 'does not match'),
                 (PDF[:-1], 'does not match'), (None, 'names an original file, but none was given'),
                 (PDF.decode('latin-1'), 'not given as bytes'))
        for original_bytes, expect in cases:
            with self.subTest(expect=expect):
                exchange, session = self.send(self.ok(), kind='pdf', original_bytes=original_bytes)
                self.assertNotSent(exchange, expect, requested_model=self.module.MODEL)
                self.assertEqual(session.calls, [])

    def test_bytes_given_for_a_request_that_names_no_original_are_not_sent_along(self):
        session = FakeSession(self.ok())
        adapter, _ = self.make(session)
        request = adapter.build_request(NOTE, PAGES, 'docx', None)
        self.assertEqual(adapter.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID,
                                      original_bytes=PDF).outcome, 'succeeded')
        self.assertEqual(session.calls[0]['data'], canonical_body(request.body))

    def test_a_body_this_adapter_never_builds_is_not_sent(self):
        adapter, made = self.make(FakeSession())
        pdf = adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        holder = self.placeholder(pdf.body)
        bodies = {}
        bodies['an extra field'] = dict(copy.deepcopy(pdf.body), temperature=0)
        bodies['another model'] = dict(copy.deepcopy(pdf.body), model=self.module.MODEL + '-preview')
        moved = copy.deepcopy(pdf.body)
        self.set(moved, self.module.ORIGINAL_PATH, 'not here')
        self.text_part(moved)['text'] = holder
        bodies['a placeholder moved'] = moved
        twice = copy.deepcopy(pdf.body)
        self.text_part(twice)['extra'] = dict(holder)
        bodies['two placeholders'] = twice
        malformed = copy.deepcopy(pdf.body)
        self.set(malformed, self.module.ORIGINAL_PATH, dict(holder, **{'$original_name': 'report.pdf'}))
        bodies['a malformed placeholder'] = malformed
        expect = {'an extra field': 'is not one this adapter builds', 'another model': 'is not one this adapter builds',
                  'a placeholder moved': 'where this adapter never puts one',
                  'two placeholders': 'where this adapter never puts one',
                  'a malformed placeholder': 'placeholder is malformed'}
        for label, body in bodies.items():
            request = ProviderRequest(provider=pdf.provider, adapter_version=pdf.adapter_version, body=body,
                                      canonical_sha256=request_sha256(body), contexts=pdf.contexts)
            with self.subTest(label):
                exchange = adapter.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID,
                                        original_bytes=PDF)
                self.assertNotSent(exchange, expect[label])
        self.assertEqual(made, [])

    def test_altered_foreign_or_oversized_requests_are_not_sent(self):
        adapter, made = self.make(FakeSession(), max_request_bytes=60_000)
        altered = adapter.build_request(NOTE, PAGES, 'paste', None)
        self.text_part(altered.body)['text'] += ' Synthetic addition after hashing.'
        other = (FableParticipant if self.adapter_class is AstraParticipant else AstraParticipant)
        foreign = other(self.tmp / 'x.env').build_request(NOTE, PAGES, 'paste', None)
        good = adapter.build_request(NOTE, PAGES, 'paste', None)
        older = ProviderRequest(provider=good.provider, adapter_version=good.adapter_version[:-1] + '0', body=good.body,
                                canonical_sha256=good.canonical_sha256, contexts=good.contexts)
        big = adapter.build_request('x' * 50_000, (), 'paste', None)
        small, _ = self.make(FakeSession(), max_request_bytes=40_000)
        cases = ((adapter, altered, 'does not match its recorded hash'), (adapter, foreign, 'different provider'),
                 (adapter, older, 'different provider or adapter version'), (small, big, 'over the 40,000-byte limit'))
        for target, request, expect in cases:
            with self.subTest(expect=expect):
                exchange = target.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID,
                                       original_bytes=None)
                self.assertNotSent(exchange, expect, requested_model='')
        self.assertEqual(made, [])

    def test_a_pdf_too_large_once_expanded_is_not_sent(self):
        adapter, made = self.make(FakeSession())
        request = adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        stored = len(canonical_body(request.body))
        tight, made = self.make(FakeSession(), max_request_bytes=stored + 10)  # the stored body fits; the file cannot
        exchange = tight.send(request, deadline_s=330, client_request_id=CLIENT_REQUEST_ID, original_bytes=PDF)
        self.assertNotSent(exchange, f'over the {stored + 10:,}-byte limit; nothing was truncated or sent')
        self.assertEqual(made, [])

    # --- credentials, deadline, session ---------------------------------------------------

    def test_credentials_that_cannot_be_used_are_not_sent_and_open_no_session(self):
        cases = {'missing': (None, 'does not exist'), 'shared': (0o644, 'accessible to group or other users'),
                 'extra key': ('extra', 'sets a key other than'), 'empty key': ('empty', 'empty or contains')}
        for label, (change, expect) in cases.items():
            self.credentials.unlink()
            if change == 'extra':
                write_file(self.credentials, self.env() + 'SOMETHING_ELSE=synthetic\n')
            elif change == 'empty':
                write_file(self.credentials, self.env(**{self.required: ''}))
            elif change is not None:
                write_file(self.credentials, self.env(), mode=change)
            with self.subTest(label):
                exchange, session = self.send(self.ok())
                self.assertNotSent(exchange, expect, requested_model=self.module.MODEL)
                self.assertIn('No request was sent.', exchange.error)
                self.assertNotIn(str(self.credentials), exchange.error)
                self.assertEqual(session.calls, [])
            if not self.credentials.exists():
                write_file(self.credentials, self.env())

    def test_credentials_are_read_at_send_time(self):
        self.credentials.unlink()
        session = FakeSession(self.ok())
        adapter, made = self.make(session)
        request = adapter.build_request(NOTE, PAGES, 'paste', None)  # building needs no credentials
        self.assertNotSent(adapter.send(request, deadline_s=60, client_request_id=CLIENT_REQUEST_ID,
                                        original_bytes=None), 'credentials file does not exist')
        self.assertEqual(made, [])
        write_file(self.credentials, self.env())
        self.assertEqual(adapter.send(request, deadline_s=60, client_request_id=CLIENT_REQUEST_ID,
                                      original_bytes=None).outcome, 'succeeded')
        self.assertEqual(len(made), 1)

    def test_invalid_deadlines_send_nothing_and_open_no_session(self):
        adapter, made = self.make(FakeSession())
        request = adapter.build_request(NOTE, PAGES, 'paste', None)
        for deadline in (0, -1, float('nan'), float('inf'), True, '330', None):
            with self.subTest(deadline=deadline):
                self.assertNotSent(adapter.send(request, deadline_s=deadline, client_request_id=CLIENT_REQUEST_ID,
                                                original_bytes=None), 'deadline')
        self.assertEqual(made, [])

    def test_the_deadline_passing_before_the_post_is_not_sent(self):
        def slow_session():
            self.clock.advance(331)
            return session
        session = FakeSession(self.ok())
        adapter = self.adapter_class(self.credentials, session_factory=slow_session)
        exchange = adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=330,
                                client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertNotSent(exchange, 'The deadline passed before the request was sent; nothing was sent.',
                           requested_model=self.module.MODEL)
        self.assertEqual(session.calls, [])
        self.assertTrue(session.closed)

    def test_a_session_that_cannot_be_made_is_not_sent(self):
        adapter = self.adapter_class(self.credentials, session_factory=mock.Mock(side_effect=RuntimeError('synthetic')))
        exchange = adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=60,
                                client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertNotSent(exchange, 'No HTTP session could be created (RuntimeError)')

    # --- transport outcomes --------------------------------------------------------------

    def test_a_connection_never_established_is_not_sent(self):
        path = '/v1/' + self.module.ENDPOINT.rsplit('/', 1)[1]
        never = (requests.exceptions.ConnectTimeout(MaxRetryError(None, path, ConnectTimeoutError('synthetic'))),
                 requests.exceptions.ConnectionError(MaxRetryError(None, path,
                                                                   NewConnectionError(None, 'synthetic refusal'))))
        for failure in never:
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(failure)
                self.assertNotSent(exchange, f'{self.vendor} could not be reached ({type(failure).__name__}); '
                                             'nothing was sent.', requested_model=self.module.MODEL)
                self.assertEqual(len(session.calls), 1)

    def test_failures_after_the_request_may_have_left_are_unknown(self):
        path = '/v1/' + self.module.ENDPOINT.rsplit('/', 1)[1]
        may_have_left = (
            requests.exceptions.ReadTimeout(ReadTimeoutError(None, path, 'Read timed out.')),
            requests.exceptions.ConnectionError(ProtocolError('Connection aborted.', ConnectionResetError())),
            requests.exceptions.SSLError(MaxRetryError(None, path, ssl.SSLError('synthetic'))),
            requests.exceptions.ConnectionError('no recognisable cause'),
            requests.exceptions.ChunkedEncodingError('synthetic'),
            RuntimeError('synthetic'),
        )
        for failure in may_have_left:
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(failure)
                self.assertUnknown(exchange, type(failure).__name__)
                self.assertEqual(len(session.calls), 1)  # never retried

    def test_a_non_200_is_failed_with_its_body_and_sha256_kept(self):
        for status, body in ((500, b'{"error":{"message":"synthetic upstream failure"}}'),
                             (429, b'{"error":{"type":"rate_limit_error","message":"synthetic"}}'),
                             (400, b'{"type":"error","error":{"type":"invalid_request_error"}}'),
                             (529, b'not json at all')):
            with self.subTest(status=status):
                exchange, session = self.send(FakeResponse(status, body, headers={self.request_id_header: 'req_x'}))
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('failed', True, status))
                self.assertEqual((exchange.response_bytes, exchange.response_sha256),
                                 (body, hashlib.sha256(body).hexdigest()))
                self.assertEqual(exchange.error,
                                 f'{self.vendor} answered HTTP {status}; the response body is retained.')
                self.assertEqual((exchange.usage, exchange.usage_basis, exchange.returned_model, exchange.response_id),
                                 ({}, '', '', ''))
                self.assertEqual((exchange.endpoint, exchange.provider_request_id), (self.module.ENDPOINT, 'req_x'))
                self.assertEqual(len(session.calls), 1)  # no retry

    def test_a_failed_answer_still_reports_the_usage_it_states(self):
        body = json.dumps({'error': {'message': 'synthetic'}, 'usage': {'input_tokens': 12, 'output_tokens': 0}})
        exchange, _ = self.send(FakeResponse(422, body.encode()))
        self.assertEqual((exchange.outcome, exchange.usage, exchange.usage_basis),
                         ('failed', {'input_tokens': 12, 'output_tokens': 0}, 'provider_reported_tokens'))

    def test_only_http_200_succeeds_and_an_empty_200_body_is_still_kept(self):
        for status in (201, 202, 204, 206):
            with self.subTest(status=status):
                exchange, _ = self.send(FakeResponse(status, self.raw))
                self.assertEqual((exchange.outcome, exchange.http_status), ('failed', status))
        exchange, _ = self.send(FakeResponse(200, b''))
        self.assertEqual((exchange.outcome, exchange.response_bytes, exchange.response_sha256, exchange.usage),
                         ('succeeded', b'', hashlib.sha256(b'').hexdigest(), {}))

    def test_a_redirect_is_failed_and_never_followed(self):
        redirect = FakeResponse(307, b'<a>moved</a>', headers={'Location': 'https://elsewhere.invalid/v1/'})
        exchange, session = self.send(redirect)
        self.assertEqual((exchange.outcome, exchange.http_status), ('failed', 307))
        self.assertIn('a redirect; it was not followed', exchange.error)
        self.assertEqual([call['url'] for call in session.calls], [self.module.ENDPOINT])
        self.assertIs(session.calls[0]['allow_redirects'], False)

    def test_a_body_over_the_cap_is_unknown_and_nothing_partial_is_kept(self):
        response = FakeResponse(200, chunks=[b'x' * 1000, b'y' * 25], headers={self.request_id_header: 'req_cap'})
        exchange, _ = self.send(response, max_response_bytes=1024)
        self.assertUnknown(exchange, 'the response exceeded 1,024 bytes', http_status=200)
        self.assertEqual(exchange.provider_request_id, 'req_cap')

    def test_a_body_exactly_at_the_cap_succeeds(self):
        exchange, _ = self.send(FakeResponse(200, self.raw), max_response_bytes=len(self.raw))
        self.assertEqual((exchange.outcome, exchange.response_bytes), ('succeeded', self.raw))

    def test_a_body_read_error_is_unknown(self):
        response = FakeResponse(200, chunks=[self.raw[:50], requests.exceptions.ChunkedEncodingError('synthetic')])
        exchange, _ = self.send(response)
        self.assertUnknown(exchange, 'ChunkedEncodingError', http_status=200)

    def test_the_deadline_passing_while_the_body_is_read_is_unknown(self):
        def late_chunk():
            self.clock.advance(400)
            return self.raw[50:]
        exchange, _ = self.send(FakeResponse(200, chunks=[self.raw[:50], late_chunk]))
        self.assertUnknown(exchange, 'the deadline passed while the response was being read', http_status=200)

    def test_timeouts_are_clamped_to_the_remaining_deadline(self):
        def slow_session():
            self.clock.advance(325)
            return session
        session = FakeSession(self.ok())
        adapter = self.adapter_class(self.credentials, session_factory=slow_session)
        adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=330,
                     client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertEqual(session.calls[0]['timeout'], (5.0, 5.0))
        _, session = self.send(self.ok(), deadline_s=20, read_timeout=15)
        self.assertEqual(session.calls[0]['timeout'], (10, 15))

    def test_latency_measures_the_post_and_its_read_only(self):
        def slow_session():
            self.clock.advance(7)
            return session

        def slow_answer():
            self.clock.advance(2.5)
            return FakeResponse(200, chunks=[self.raw[:10], lambda: self.clock.advance(0.5) or self.raw[10:]])
        session = FakeSession(slow_answer)
        adapter = self.adapter_class(self.credentials, session_factory=slow_session)
        exchange = adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=330,
                                client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertEqual(exchange.latency_ms, 3000.0)

    def test_the_vendor_request_id_is_kept_only_from_its_own_header_and_when_it_fits(self):
        cases = {None: '', 'req synthetic': '', 'r' * 121: '', 'r' * 120: 'r' * 120,
                 'req_011CSynthetic': 'req_011CSynthetic'}
        for header, expected in cases.items():
            with self.subTest(header=header):
                headers = {} if header is None else {self.request_id_header: header}
                exchange, _ = self.send(FakeResponse(200, self.raw, headers=headers))
                self.assertEqual(exchange.provider_request_id, expected)
        exchange, _ = self.send(FakeResponse(200, self.raw, headers={self.other_request_id_header: 'req_other'}))
        self.assertEqual(exchange.provider_request_id, '')

    def test_model_id_and_usage_are_recorded_as_stated_and_only_when_they_fit(self):
        envelope = json.loads(self.raw)
        cases = ({'model': 'm' * 101, 'id': 'i' * 141, 'usage': [1]}, {'model': 'has space', 'id': None, 'usage': None},
                 {'model': 7, 'id': 'resp with space'})
        for change in cases:
            with self.subTest(change=change):
                body = json.dumps(dict(envelope, **change)).encode()
                exchange, _ = self.send(FakeResponse(200, body))
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('succeeded', body))
                self.assertEqual((exchange.returned_model, exchange.response_id), ('', ''))
                self.assertEqual((exchange.usage, exchange.usage_basis),
                                 (envelope['usage'], 'provider_reported_tokens') if 'usage' not in change else ({}, ''))
        stated = dict(envelope, model='another-model-1', id='x_1')
        exchange, _ = self.send(FakeResponse(200, json.dumps(stated).encode()))
        self.assertEqual((exchange.returned_model, exchange.response_id), ('another-model-1', 'x_1'))  # as stated
        for body in (b'{"model":"a","model":"b"}', b'{"usage":{"input_tokens":NaN}}', b'\xff'):
            with self.subTest(body=body):
                exchange, _ = self.send(FakeResponse(200, body))
                self.assertEqual((exchange.outcome, exchange.usage, exchange.returned_model), ('succeeded', {}, ''))

    def test_response_bytes_are_kept_exactly_even_when_they_echo_a_key(self):
        # The stored bytes are the vendor's raw bytes, exactly as received; an echoed key is the vendor's text, never
        # copied into the error. (Sent without send(): its repr check would find the echo in the kept bytes.)
        key = OPENAI_KEY if self.adapter_class is AstraParticipant else ANTHROPIC_KEY
        body = b'{"error":{"message":"Incorrect API key provided: ' + key.encode() + b'"}}\r\n'
        session = FakeSession(FakeResponse(401, body))
        adapter, _ = self.make(session)
        exchange = adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=60,
                                client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertEqual((exchange.outcome, exchange.response_bytes), ('failed', body))  # stored as received
        self.assertNotIn(key, exchange.error)


class AstraSendTests(_SendContract, OfflineTestCase):
    module = openai_astra
    adapter_class = AstraParticipant
    fixture = 'astra-colonoscopy.response.json'
    vendor = 'OpenAI'
    request_id_header = 'x-request-id'
    other_request_id_header = 'request-id'
    optional = ('OPENAI_PROJECT', OPENAI_PROJECT)
    required = 'OPENAI_API_KEY'
    prefix = 'data:application/pdf;base64,'

    def env(self, **overrides):
        return openai_env(**overrides)

    def expected_headers(self, optional=None):
        headers = {'Authorization': f'Bearer {OPENAI_KEY}', 'Content-Type': 'application/json',
                   'X-Client-Request-Id': CLIENT_REQUEST_ID}
        if optional is not None:
            headers['OpenAI-Project'] = optional
        return headers

    def placeholder(self, body):
        return body['input'][0]['content'][0]['file_data']

    def text_part(self, body):
        return body['input'][0]['content'][-1]

    def test_the_client_request_id_must_fit_what_openai_accepts(self):
        for value in ('', 'has space', 'x' * 513, None, 'café-id', 'line\nbreak', 42):
            with self.subTest(value=value):
                exchange, session = self.send(self.ok(), client_request_id=value)
                self.assertNotSent(exchange, 'The client request id must be 1 to 512 visible ASCII characters',
                                   requested_model='gpt-6-astra')
                self.assertEqual(session.calls, [])
        exchange, session = self.send(self.ok(), client_request_id='x' * 512)
        self.assertEqual(session.calls[0]['headers']['X-Client-Request-Id'], 'x' * 512)


class FableSendTests(_SendContract, OfflineTestCase):
    module = anthropic_fable
    adapter_class = FableParticipant
    fixture = 'fable-colonoscopy.response.json'
    vendor = 'Anthropic'
    request_id_header = 'request-id'
    other_request_id_header = 'x-request-id'
    optional = ('ANTHROPIC_WORKSPACE_ID', ANTHROPIC_WORKSPACE)
    required = 'ANTHROPIC_API_KEY'
    prefix = ''

    def env(self, **overrides):
        return anthropic_env(**overrides)

    def expected_headers(self, optional=None):
        headers = {'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2026-10-21', 'content-type': 'application/json'}
        if optional is not None:
            headers['anthropic-workspace-id'] = optional
        return headers

    def placeholder(self, body):
        return body['messages'][0]['content'][0]['source']['data']

    def text_part(self, body):
        return body['messages'][0]['content'][-1]

    def test_no_beta_header_and_no_forbidden_field_is_ever_sent(self):
        for kind, original_bytes in (('paste', None), ('pdf', PDF)):
            with self.subTest(kind=kind):
                exchange, session = self.send(self.ok(), kind=kind, original_bytes=original_bytes)
                self.assertEqual(exchange.outcome, 'succeeded')
                headers = {name.lower() for name in session.calls[0]['headers']}
                self.assertEqual(headers, {'x-api-key', 'anthropic-version', 'content-type'})
                sent = json.loads(session.calls[0]['data'])
                self.assertEqual(set(sent), {'model', 'max_tokens', 'system', 'messages', 'output_config', 'tools',
                                             'tool_choice'})
                for field in ('thinking', 'temperature', 'top_p', 'top_k', 'fallbacks'):
                    self.assertNotIn(f'"{field}"', session.calls[0]['data'].decode())

    def test_the_client_request_id_is_not_sent(self):
        exchange, session = self.send(self.ok(), client_request_id='cptstudio-never-sent-0001')
        self.assertEqual(exchange.outcome, 'succeeded')
        self.assertNotIn('cptstudio-never-sent-0001', json.dumps(session.calls[0]['headers']))
        self.assertNotIn(b'cptstudio-never-sent-0001', session.calls[0]['data'])


class SessionTests(OfflineTestCase):
    def test_the_default_session_ignores_the_environment_and_never_retries_or_redirects(self):
        with mock.patch('requests.Session', wraps=requests.sessions.Session) as spy:
            session = participants_http.default_session()
        self.addCleanup(session.close)
        spy.assert_called_once_with()
        self.assertIs(session.trust_env, False)
        self.assertEqual(session.max_redirects, 0)
        for url in (openai_astra.ENDPOINT, anthropic_fable.ENDPOINT):
            adapter = session.get_adapter(url)
            self.assertIsInstance(adapter, HTTPAdapter)
            self.assertEqual((adapter.max_retries.total, adapter.max_retries.read), (0, False))

    def test_the_network_guard_trips(self):
        """Positive control: an adapter left to its real session factory hits the guard and sends nothing."""
        credentials = write_file(self.tmp / 'openai.env', openai_env())
        for adapter in (AstraParticipant(credentials), FableParticipant(write_file(self.tmp / 'a.env',
                                                                                   anthropic_env()))):
            exchange = adapter.send(adapter.build_request(NOTE, PAGES, 'paste', None), deadline_s=60,
                                    client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
            self.assertEqual((exchange.outcome, exchange.sent), ('not_sent', False))
            self.assertIn('No HTTP session could be created (NetworkBlocked)', exchange.error)
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo('api.openai.com', 443)
        with self.assertRaises(NetworkBlocked):
            socket.create_connection(('127.0.0.1', 9))
        probe = socket.socket()
        self.addCleanup(probe.close)
        with self.assertRaises(NetworkBlocked):
            probe.connect(('127.0.0.1', 9))
        self.assertEqual(self.network_attempts, ['requests.Session', 'requests.Session', 'socket.getaddrinfo',
                                                 'socket.create_connection', 'socket.connect'])
        self.network_attempts.clear()
