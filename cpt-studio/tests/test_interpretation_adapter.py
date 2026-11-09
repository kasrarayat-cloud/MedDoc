"""The production Gemini adapter (Gemini migration slice S06; design/FINAL.md 5.4, 6.3, 11 and 15; design/contract.md
2.2; design/ADJUDICATION.md P-3, P-4 and P-5), in the participants' send-contract pattern (tests/test_participants_send):
the exact call, the key in the x-goog-api-key header only and never in the endpoint, every outcome arm of the one send,
the send deadline, a member's Stop before the send, the run of exactly one exchange, the envelope rules (modelVersion
exactly gemini-4-argon and first, one candidate, finishReason STOP, MAX_TOKENS refused, thought parts excluded), the
usage, model and id the vendor describe hook records, the classification of every failure (401, 403, the P-3 names,
quota and rate 429s, 5xx, a substituted model, a cut-off answer), replay by request sha256, the configured interpreter
and its settings, and no legacy import.

Offline and synthetic (tests/test_participants_support): every send goes to a fake session behind a guard that fails on
any real connection, and every key is fake. One fixture is real vendor output: the HTTP 429 body Google returned to the
trial's first attempt on 2026-11-09 (gemini-trial/archive/attempt1-20261109T0549Z/note8.4e985614a943.json, sha256
3edc6552..., its "body" field, byte for byte; it carries no key, and its request carried none either). Nothing is sent.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.test import SimpleTestCase, override_settings
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ProtocolError, ReadTimeoutError

from studio import interpretation
from studio.interpretation import adapter, prompt, read
from studio.interpretation.adapter import GeminiCredentials, GeminiInterpreter, load_gemini_credentials
from studio.interpretation.replay import ReplayInterpreter
from studio.participants import http as participants_http
from studio.participants import loop as participants_loop
from studio.participants import prompt as participant_prompt
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.providers.credentials import CredentialsError
from studio.types import PageSpan, ProviderRequest

from tests.test_interpretation_read import answer as synthetic_answer
from tests.test_participants_support import (FakeClock, FakeResponse, FakeSession, NetworkBlocked, OfflineTestCase,
                                             dotenv, write_file)

APP = Path(__file__).resolve().parent.parent
TRIAL_429 = APP / 'tests' / 'fixtures' / 'interpretation' / 'adapter' / 'trial-attempt1-note8-429.json'
TRIAL_429_SHA256 = '9d2e8b8931661721c9687eed047501068d9e52c01b49906fc4e2edb2e88e156a'
GEMINI_KEY = 'synthetic-gemini-key-NOT-A-REAL-KEY-0001'
MODEL_TEXT = 'SYNTHETIC-MODEL-TEXT-0001'  # model-written wording planted in an answer: never repeated in a refusal
NOTE = ('Synthetic colonoscopy note. Date of service: 03/14/2026.\n'
        'A 7 mm sessile polyp in the transverse colon was removed with a cold snare.\n'
        'Page two. No other polyp was removed.\n')
BREAK = NOTE.index('Page two')
PAGES = (PageSpan(page=1, start=0, end=BREAK), PageSpan(page=2, start=BREAK, end=len(NOTE)))
OTHER_NOTE = 'Synthetic upper endoscopy note. The scope reached the second portion of the duodenum.\n'
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent'
UNKNOWN = 'The outcome is unknown; reconcile it before any new attempt.'
USAGE = {'promptTokenCount': 5355, 'candidatesTokenCount': 9183, 'totalTokenCount': 14538,
         'promptTokensDetails': [{'modality': 'TEXT', 'tokenCount': 5355}],
         'candidatesTokensDetails': [{'modality': 'TEXT', 'tokenCount': 9183}]}


def gemini_env(**overrides) -> str:
    return dotenv(**{'GEMINI_API_KEY': GEMINI_KEY, **overrides})


def envelope(text='{"synthetic": true}', **changes) -> dict:
    """A 200 generateContent answer in the shape the trial's seven answers had (2026-11-09): one candidate whose one text
    part carries a thought signature, finishReason STOP, usageMetadata, modelVersion and responseId."""
    value = {'candidates': [{'content': {'parts': [{'text': text, 'thoughtSignature': 'c3ludGhldGljLXNpZ25hdHVyZQ=='}],
                                         'role': 'model'},
                             'finishReason': 'STOP', 'index': 0}],
             'usageMetadata': copy.deepcopy(USAGE), 'modelVersion': 'gemini-4-argon',
             'responseId': 'synthetic-response-0001'}
    value.update(changes)
    return value


def with_parts(*parts, finish='STOP', **changes) -> dict:
    value = envelope(**changes)
    value['candidates'][0]['content']['parts'] = list(parts)
    value['candidates'][0]['finishReason'] = finish
    return value


def encoded(value) -> bytes:
    return json.dumps(value).encode()


def error_body(code, status, *details, message='Synthetic error message.') -> bytes:
    return encoded({'error': {'code': code, 'message': message, 'status': status, 'details': list(details)}})


def error_info(reason) -> dict:
    return {'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': reason, 'domain': 'googleapis.com',
            'metadata': {'service': 'generativelanguage.googleapis.com'}}


def quota_failure(*violations) -> dict:
    return {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': list(violations)}


def violation(quota_id, metric='generativelanguage.googleapis.com/generate_content_paid_tier_requests', **extra):
    found = {'quotaMetric': metric, 'quotaDimensions': {'location': 'global', 'model': 'gemini-4-argon'}, **extra}
    if quota_id is not None:
        found['quotaId'] = quota_id
    return found


def retry_info(delay) -> dict:
    return {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': delay}


PER_MINUTE = 'GenerateRequestsPerMinutePerProjectPerModel'
PER_DAY = 'GenerateRequestsPerDayPerProjectPerModel'


def request_with(body: dict, **fields) -> ProviderRequest:
    values = dict(provider=adapter.NAME, adapter_version=adapter.ADAPTER_VERSION, body=body,
                  canonical_sha256=request_sha256(body), contexts=(NOTE,))
    values.update(fields)
    return ProviderRequest(**values)


class _Clocked(OfflineTestCase):
    """A fake clock for every module that reads one, and a protected credentials file."""

    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        for module in (participants_http, adapter, participants_loop):
            self.enterContext(mock.patch.object(module, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'gemini.env', gemini_env())
        self.raw = encoded(envelope())

    def make(self, session=None, **options):
        made = []

        def factory():
            made.append(session)
            return session
        return GeminiInterpreter(self.credentials, session_factory=factory, **options), made

    def ok(self, raw=None, **headers):
        return FakeResponse(200, self.raw if raw is None else raw, headers=headers)

    def assertNoKey(self, exchange, request=None):
        texts = [repr(exchange), exchange.error, exchange.endpoint]
        if request is not None:
            texts.append(canonical_body(request.body).decode())
        for text in texts:
            self.assertNotIn(GEMINI_KEY, text)

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
                         ('unknown', True, http_status, None, '', ENDPOINT, 'gemini-4-argon'))
        self.assertIn('The request may have reached Google', exchange.error)
        self.assertIn(UNKNOWN, exchange.error)
        self.assertIn(expect, exchange.error)


# --- the request ---------------------------------------------------------------------------------------------------------

class RequestTests(OfflineTestCase):
    def test_the_request_is_the_contracts_body_built_from_the_revision_alone(self):
        request = adapter.build_request(NOTE, PAGES, 'paste')
        self.assertEqual((request.provider, request.adapter_version), ('gemini', 'gemini-generate@cptstudio-1'))
        self.assertEqual(request.body, prompt.request_parts(prompt.framed(NOTE, PAGES, 'paste')))
        self.assertEqual(list(request.body), ['systemInstruction', 'contents', 'generationConfig'])
        self.assertEqual(request.canonical_sha256, hashlib.sha256(canonical_body(request.body)).hexdigest())
        self.assertEqual(request.contexts, (NOTE,))
        self.assertEqual(adapter.body_problem(request.body), '')
        self.assertNotIn('model', request.body)  # the URL names the model (contract 2.2)
        # building needs no credentials, settings or network: the interpreter's file does not exist
        interpreter = GeminiInterpreter(self.tmp / 'absent.env')
        self.assertEqual(interpreter.build_request(NOTE, PAGES, 'paste'), request)

    def test_the_constants_are_the_interpretation_labels(self):
        self.assertEqual((adapter.NAME, adapter.ADAPTER_VERSION, adapter.MODEL),
                         (interpretation.PROVIDER, interpretation.ADAPTER_VERSION, interpretation.MODEL))
        self.assertEqual(adapter.ENDPOINT, ENDPOINT)
        self.assertEqual((adapter.CONNECT_TIMEOUT_SECONDS, adapter.READ_TIMEOUT_SECONDS,
                          adapter.SEND_DEADLINE_SECONDS), (10, 300, 330))  # D12
        self.assertLessEqual(len(adapter.ENDPOINT), 200)  # ProviderRun.endpoint
        self.assertLessEqual(len(adapter.NAME), 20)  # ProviderRun.provider
        self.assertLessEqual(len(adapter.ADAPTER_VERSION), 40)  # ProviderRun.adapter_version

    def test_a_text_that_cannot_be_sent_is_never_built(self):
        cases = {'empty': ('', (), 'has no text to send'), 'blank': ('  \n ', (), 'has no text to send'),
                 'NUL': ('Synthetic\x00 note.', (), 'contains NUL characters'),
                 'pages that do not tile it': (NOTE, (PageSpan(page=1, start=0, end=5),),
                                               'its pages do not cover it exactly; nothing was sent')}
        for label, (text, pages, expect) in cases.items():
            with self.subTest(label), self.assertRaises(ProviderUnavailable) as caught:
                adapter.build_request(text, pages, 'paste')
            self.assertIn(expect, str(caught.exception))
        # the marker is the text's own sha256 prefix, so no real text contains it: pinned here, as the participants' is
        with mock.patch.object(participant_prompt, 'marker', return_value='DOCUMENT-0000000000000000'), \
                self.assertRaises(ProviderUnavailable) as caught:
            adapter.build_request(NOTE + ' DOCUMENT-0000000000000000', (), 'paste')
        self.assertIn('it contains its own framing marker; nothing was sent', str(caught.exception))
        for wrong in ((None, PAGES, 'paste', TypeError), (NOTE, 'pages', 'paste', TypeError),
                      (NOTE, PAGES, 'image', ValueError)):
            with self.subTest(wrong=wrong[-1].__name__), self.assertRaises(wrong[-1]):
                adapter.build_request(*wrong[:3])

    def test_a_request_over_the_limit_is_refused_never_truncated(self):
        size = len(canonical_body(adapter.build_request(NOTE, PAGES, 'paste').body))
        with self.assertRaises(ProviderUnavailable) as caught:
            adapter.build_request(NOTE, PAGES, 'paste', max_bytes=size - 1)
        self.assertIn(f'over the {size - 1:,}-byte limit; nothing was truncated or sent', str(caught.exception))
        self.assertEqual(len(canonical_body(adapter.build_request(NOTE, PAGES, 'paste', max_bytes=size).body)), size)

    def test_a_pdf_is_sent_as_its_extracted_text_with_no_original(self):
        request = adapter.build_request(NOTE, PAGES, 'pdf')
        framed = request.body['contents'][0]['parts'][0]['text']
        self.assertEqual(framed.split('\n')[0], 'Document: a PDF; only its extracted text is given.')
        self.assertNotIn(b'$original', canonical_body(request.body))
        self.assertEqual(list(inspect.signature(adapter.build_request).parameters),
                         ['text', 'pages', 'kind', 'max_bytes'])  # no original file can be passed (D12)


# --- the send contract ---------------------------------------------------------------------------------------------------

class SendTests(_Clocked):
    def send(self, *steps, deadline_s=330, request=None, client_request_id='', original_bytes=None, **options):
        session = FakeSession(*steps)
        interpreter, made = self.make(session, **options)
        if request is None:
            request = interpreter.build_request(NOTE, PAGES, 'paste')
        exchange = interpreter.send(request, deadline_s=deadline_s, client_request_id=client_request_id,
                                    original_bytes=original_bytes)
        self.assertNoKey(exchange, request)
        if made:
            self.assertTrue(session.closed)
        self.assertTrue(all(response.closed for response in session.responses))
        return exchange, session

    def test_success_keeps_the_exact_bytes_and_records_usage_model_and_id(self):
        raw = self.raw
        exchange, session = self.send(FakeResponse(200, chunks=[raw[:100], raw[100:]]))
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('succeeded', True, 200))
        self.assertEqual((exchange.response_bytes, exchange.response_sha256), (raw, hashlib.sha256(raw).hexdigest()))
        # the describe hook: usageMetadata as reported, modelVersion and responseId (FINAL 5.4)
        self.assertEqual((exchange.usage, exchange.usage_basis), (USAGE, 'provider_reported_tokens'))
        self.assertEqual((exchange.endpoint, exchange.requested_model, exchange.returned_model, exchange.response_id),
                         (ENDPOINT, 'gemini-4-argon', 'gemini-4-argon', 'synthetic-response-0001'))
        self.assertEqual((exchange.provider_request_id, exchange.error, exchange.latency_ms), ('', '', 0.0))
        self.assertEqual(len(session.calls), 1)

    def test_thinking_tokens_are_recorded_as_reported(self):
        usage = dict(USAGE, thoughtsTokenCount=1200, totalTokenCount=15738)
        exchange, _ = self.send(self.ok(encoded(envelope(usageMetadata=usage))))
        self.assertEqual(exchange.usage, usage)

    def test_the_call_is_exactly_the_contract(self):
        session = FakeSession(self.ok())
        interpreter, _ = self.make(session)
        request = interpreter.build_request(NOTE, PAGES, 'paste')
        interpreter.send(request, deadline_s=330, client_request_id='', original_bytes=None)
        (call,) = session.calls
        self.assertEqual(call, {'url': ENDPOINT, 'data': canonical_body(request.body),
                                'headers': {'x-goog-api-key': GEMINI_KEY, 'content-type': 'application/json'},
                                'timeout': (10, 300), 'allow_redirects': False, 'stream': True})
        self.assertEqual(hashlib.sha256(call['data']).hexdigest(), request.canonical_sha256)

    def test_the_key_travels_only_in_the_header_and_the_endpoint_never_carries_it(self):
        exchange, session = self.send(self.ok())
        (call,) = session.calls
        parts = urlsplit(call['url'])
        self.assertEqual((parts.query, parts.fragment, parts.username, parts.password), ('', '', None, None))
        self.assertNotIn(GEMINI_KEY, call['url'])
        self.assertNotIn(GEMINI_KEY.encode(), call['data'])
        self.assertEqual([name for name, value in call['headers'].items() if GEMINI_KEY in value], ['x-goog-api-key'])
        self.assertEqual(exchange.endpoint, ENDPOINT)  # ProviderRun.endpoint: never the key (hazard 23)
        for value in (adapter.ENDPOINT, GeminiInterpreter.endpoint):
            self.assertNotIn('key', urlsplit(value).query)
            self.assertNotIn('?', value)

    def test_a_key_the_vendor_echoes_is_kept_in_the_bytes_and_never_in_the_error(self):
        body = error_body(400, 'INVALID_ARGUMENT', error_info('API_KEY_INVALID'),
                          message=f'API key not valid: {GEMINI_KEY}')
        session = FakeSession(FakeResponse(400, body))
        interpreter, _ = self.make(session)
        exchange = interpreter.send(interpreter.build_request(NOTE, PAGES, 'paste'), deadline_s=60)
        self.assertEqual((exchange.outcome, exchange.response_bytes), ('failed', body))  # stored as received
        self.assertNotIn(GEMINI_KEY, exchange.error)
        self.assertNotIn(GEMINI_KEY, adapter.classify('failed', 400, body).why)

    def test_the_client_request_id_and_original_bytes_are_never_sent(self):
        request = adapter.build_request(NOTE, PAGES, 'pdf')
        exchange, session = self.send(self.ok(), request=request, client_request_id='cptstudio-never-sent-0001',
                                      original_bytes=b'%PDF-1.7 synthetic bytes, never sent')
        self.assertEqual(exchange.outcome, 'succeeded')
        (call,) = session.calls
        self.assertEqual(call['data'], canonical_body(request.body))
        self.assertNotIn('cptstudio-never-sent-0001', json.dumps(call['headers']))
        self.assertNotIn(b'%PDF', call['data'])
        self.assertEqual(set(call['headers']), {'x-goog-api-key', 'content-type'})

    def test_credentials_that_cannot_be_used_are_not_sent_and_open_no_session(self):
        cases = {'missing': (None, 'The Gemini credentials file does not exist.'),
                 'shared': (0o640, 'accessible to group or other users'),
                 'another key': (gemini_env(GEMINI_PROJECT='synthetic'), 'sets a key other than GEMINI_API_KEY.'),
                 'empty key': (gemini_env(GEMINI_API_KEY=''), 'GEMINI_API_KEY is empty or contains a space'),
                 'a space': (gemini_env(GEMINI_API_KEY='"two words"'), 'GEMINI_API_KEY is empty or contains a space'),
                 'twice': (gemini_env() + gemini_env(), 'GEMINI_API_KEY is set more than once'),
                 'no key': ('# synthetic comment only\n', 'GEMINI_API_KEY is missing from the Gemini credentials file'),
                 'an escape': ('GEMINI_API_KEY="synthetic\\nkey"\n', 'uses an escape sequence')}
        for label, (change, expect) in cases.items():
            self.credentials.unlink()
            if isinstance(change, int):
                write_file(self.credentials, gemini_env(), mode=change)
            elif change is not None:
                write_file(self.credentials, change)
            with self.subTest(label):
                exchange, session = self.send(self.ok())
                self.assertNotSent(exchange, expect, requested_model='gemini-4-argon')
                self.assertIn('No request was sent.', exchange.error)
                self.assertNotIn(str(self.credentials), exchange.error)
                self.assertEqual(session.calls, [])
            if self.credentials.exists():
                self.credentials.unlink()
            write_file(self.credentials, gemini_env())

    def test_a_symlinked_credentials_file_is_refused(self):
        link = self.tmp / 'linked.env'
        link.symlink_to(self.credentials)
        interpreter = GeminiInterpreter(link, session_factory=lambda: FakeSession(self.ok()))
        exchange = interpreter.send(interpreter.build_request(NOTE, PAGES, 'paste'), deadline_s=60)
        self.assertNotSent(exchange, 'is a symbolic link; it was refused')

    def test_credentials_are_read_at_send_time_by_the_participants_loader(self):
        self.credentials.unlink()
        session = FakeSession(self.ok())
        interpreter, made = self.make(session)
        request = interpreter.build_request(NOTE, PAGES, 'paste')
        self.assertNotSent(interpreter.send(request, deadline_s=60), 'credentials file does not exist')
        self.assertEqual(made, [])
        write_file(self.credentials, 'export GEMINI_API_KEY=' + GEMINI_KEY + '  # the loader allows a comment\n')
        self.assertEqual(interpreter.send(request, deadline_s=60).outcome, 'succeeded')
        self.assertEqual(session.calls[0]['headers']['x-goog-api-key'], GEMINI_KEY)
        loaded = load_gemini_credentials(self.credentials)
        self.assertEqual(loaded, GeminiCredentials(api_key=GEMINI_KEY))
        for text in (repr(loaded), str(loaded)):
            self.assertEqual(text, 'GeminiCredentials(api_key=<redacted>)')
        with self.assertRaises(CredentialsError) as caught:
            load_gemini_credentials('')
        self.assertEqual(str(caught.exception), 'No Gemini credentials file is configured.')

    def test_invalid_deadlines_send_nothing_and_open_no_session(self):
        interpreter, made = self.make(FakeSession())
        request = interpreter.build_request(NOTE, PAGES, 'paste')
        for deadline in (0, -1, float('nan'), float('inf'), True, '330', None):
            with self.subTest(deadline=deadline):
                self.assertNotSent(interpreter.send(request, deadline_s=deadline), 'deadline')
        self.assertEqual(made, [])
        for label, value in (('send_deadline', 0), ('connect_timeout', -1), ('read_timeout', float('nan')),
                             ('max_request_bytes', 0), ('max_response_bytes', True)):
            with self.subTest(option=label), self.assertRaises(ValueError):
                GeminiInterpreter(self.credentials, **{label: value})

    def test_the_send_deadline_bounds_every_caller(self):
        def slow_session():
            self.clock.advance(325)
            return session
        session = FakeSession(self.ok())
        interpreter = GeminiInterpreter(self.credentials, session_factory=slow_session)
        # the caller offers 600 s; 330 s is the most a send may take (D12), so 5 s are left, not 275
        interpreter.send(interpreter.build_request(NOTE, PAGES, 'paste'), deadline_s=600)
        self.assertEqual(session.calls[0]['timeout'], (5.0, 5.0))
        _, session = self.send(self.ok(), deadline_s=20, read_timeout=15)
        self.assertEqual(session.calls[0]['timeout'], (10, 15))

    def test_the_deadline_passing_before_the_post_is_not_sent(self):
        def slow_session():
            self.clock.advance(331)
            return session
        session = FakeSession(self.ok())
        interpreter = GeminiInterpreter(self.credentials, session_factory=slow_session)
        exchange = interpreter.send(interpreter.build_request(NOTE, PAGES, 'paste'), deadline_s=600)
        self.assertNotSent(exchange, 'The deadline passed before the request was sent; nothing was sent.',
                           requested_model='gemini-4-argon')
        self.assertEqual(session.calls, [])
        self.assertTrue(session.closed)

    def test_the_deadline_passing_while_the_answer_is_read_is_unknown(self):
        def late_chunk():
            self.clock.advance(400)
            return self.raw[50:]
        exchange, _ = self.send(FakeResponse(200, chunks=[self.raw[:50], late_chunk]))
        self.assertUnknown(exchange, 'the deadline passed while the response was being read', http_status=200)

    def test_a_connection_never_established_is_not_sent(self):
        path = '/v1beta/models/gemini-4-argon:generateContent'
        never = (requests.exceptions.ConnectTimeout(MaxRetryError(None, path, ConnectTimeoutError('synthetic'))),
                 requests.exceptions.ConnectionError(MaxRetryError(None, path,
                                                                   NewConnectionError(None, 'synthetic refusal'))))
        for failure in never:
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(failure)
                self.assertNotSent(exchange, f'Google could not be reached ({type(failure).__name__}); nothing was '
                                             'sent.', requested_model='gemini-4-argon')
                self.assertEqual(len(session.calls), 1)

    def test_failures_after_the_request_may_have_left_are_unknown_and_never_retried(self):
        path = '/v1beta/models/gemini-4-argon:generateContent'
        for failure in (requests.exceptions.ReadTimeout(ReadTimeoutError(None, path, 'Read timed out.')),
                        requests.exceptions.ConnectionError(ProtocolError('aborted', ConnectionResetError())),
                        requests.exceptions.ChunkedEncodingError('synthetic'), RuntimeError('synthetic')):
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(failure)
                self.assertUnknown(exchange, type(failure).__name__)
                self.assertEqual(len(session.calls), 1)

    def test_a_non_200_is_failed_with_its_body_kept_and_never_retried(self):
        trial = TRIAL_429.read_bytes()
        for status, body in ((429, trial), (500, error_body(500, 'INTERNAL')),
                             (400, error_body(400, 'INVALID_ARGUMENT')), (503, b'not json at all')):
            with self.subTest(status=status):
                exchange, session = self.send(FakeResponse(status, body))
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('failed', True, status))
                self.assertEqual((exchange.response_bytes, exchange.response_sha256),
                                 (body, hashlib.sha256(body).hexdigest()))
                self.assertEqual(exchange.error, f'Google answered HTTP {status}; the response body is retained.')
                # an error body states no usage, model or id (the trial's 429s carried no usage)
                self.assertEqual((exchange.usage, exchange.usage_basis, exchange.returned_model, exchange.response_id),
                                 ({}, '', '', ''))
                self.assertEqual(len(session.calls), 1)

    def test_a_redirect_is_failed_and_never_followed(self):
        exchange, session = self.send(FakeResponse(307, b'moved', headers={'Location': 'https://elsewhere.invalid/'}))
        self.assertEqual((exchange.outcome, exchange.http_status), ('failed', 307))
        self.assertIn('a redirect; it was not followed', exchange.error)
        self.assertEqual([call['url'] for call in session.calls], [ENDPOINT])

    def test_an_answer_over_the_cap_is_unknown_and_nothing_partial_is_kept(self):
        exchange, _ = self.send(FakeResponse(200, chunks=[b'x' * 1000, b'y' * 25]), max_response_bytes=1024)
        self.assertUnknown(exchange, 'the response exceeded 1,024 bytes', http_status=200)

    def test_a_body_this_adapter_never_builds_is_not_sent(self):
        good = adapter.build_request(NOTE, PAGES, 'paste').body
        bodies = {}

        def changed(label, change):
            body = copy.deepcopy(good)
            change(body)
            bodies[label] = body
        changed('a model field', lambda body: body.update(model='gemini-4-argon'))
        changed('tools', lambda body: body.update(tools=[{'googleSearch': {}}]))
        changed('safety settings', lambda body: body.update(safetySettings=[]))
        changed('thinking configured', lambda body: body['generationConfig'].update(thinkingConfig={'thinkingBudget': 0}))
        changed('another temperature', lambda body: body['generationConfig'].update(temperature=0.5))
        changed('no schema', lambda body: body['generationConfig'].pop('responseSchema'))
        changed('another schema', lambda body: body['generationConfig']['responseSchema'].update(type='ARRAY'))
        changed('other instructions', lambda body: body['systemInstruction']['parts'][0].update(text='Answer freely.'))
        changed('a second turn', lambda body: body['contents'].append({'role': 'user', 'parts': [{'text': 'More.'}]}))
        changed('a second part', lambda body: body['contents'][0]['parts'].append({'text': 'More.'}))
        changed('an unframed text', lambda body: body['contents'][0]['parts'][0].update(text=NOTE))
        changed('an original', lambda body: body['contents'][0]['parts'].insert(
            0, {'inlineData': {'$original_sha256': '0' * 64, '$original_bytes': 10}}))
        changed('another role', lambda body: body['contents'][0].update(role='model'))
        interpreter, made = self.make(FakeSession())
        for label, body in bodies.items():
            with self.subTest(label):
                self.assertNotSent(interpreter.send(request_with(body), deadline_s=330),
                                   'The request body is not one this adapter builds; nothing was sent.')
        self.assertEqual(made, [])

    def test_altered_foreign_or_oversized_requests_are_not_sent(self):
        interpreter, made = self.make(FakeSession())
        good = interpreter.build_request(NOTE, PAGES, 'paste')
        altered = copy.deepcopy(good.body)
        altered['contents'][0]['parts'][0]['text'] += ' Synthetic addition after hashing.'
        small, small_made = self.make(FakeSession(), max_request_bytes=20_000)
        cases = ((interpreter, request_with(altered, canonical_sha256=good.canonical_sha256),
                  'does not match its recorded hash'),
                 (interpreter, request_with(good.body, provider='fable'), 'different provider'),
                 (interpreter, request_with(good.body, adapter_version='gemini-generate@cptstudio-0'),
                  'different provider or adapter version'),
                 (small, good, 'over the 20,000-byte limit'))
        for target, request, expect in cases:
            with self.subTest(expect=expect):
                self.assertNotSent(target.send(request, deadline_s=330), expect, requested_model='')
        self.assertEqual(made + small_made, [])

    def test_usage_model_and_id_are_recorded_only_when_they_fit(self):
        cases = ({'modelVersion': 'm' * 101, 'responseId': 'i' * 141, 'usageMetadata': [1]},
                 {'modelVersion': 'has space', 'responseId': None, 'usageMetadata': None},
                 {'modelVersion': 7, 'responseId': 'id with space', 'usageMetadata': 'many'})
        for change in cases:
            with self.subTest(change=change):
                body = encoded(envelope(**change))
                exchange, _ = self.send(self.ok(body))
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('succeeded', body))  # unchanged
                self.assertEqual((exchange.returned_model, exchange.response_id, exchange.usage,
                                  exchange.usage_basis), ('', '', {}, ''))
        stated = encoded(envelope(modelVersion='another-model-1', responseId='x_1'))
        exchange, _ = self.send(self.ok(stated))
        self.assertEqual((exchange.returned_model, exchange.response_id), ('another-model-1', 'x_1'))  # as stated
        for body in (b'{"modelVersion":"a","modelVersion":"b"}', b'{"usageMetadata":{"promptTokenCount":NaN}}',
                     b'\xff', b'[]'):
            with self.subTest(body=body):
                exchange, _ = self.send(self.ok(body))
                self.assertEqual((exchange.outcome, exchange.usage, exchange.returned_model), ('succeeded', {}, ''))

    def test_the_network_guard_trips(self):
        """Positive control: an interpreter left to its real session factory hits the guard and sends nothing."""
        interpreter = GeminiInterpreter(self.credentials)
        exchange = interpreter.send(interpreter.build_request(NOTE, PAGES, 'paste'), deadline_s=60)
        self.assertEqual((exchange.outcome, exchange.sent), ('not_sent', False))
        self.assertIn('No HTTP session could be created (NetworkBlocked)', exchange.error)
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo('generativelanguage.googleapis.com', 443)
        self.assertEqual(self.network_attempts, ['requests.Session', 'socket.getaddrinfo'])
        self.network_attempts.clear()


class DescribeHookTests(_Clocked):
    """participants.http's vendor describe hook (FINAL 3.2): the default is the participants' own describe, unchanged; a
    hook's reading is kept only where it fits the record, and a hook can never change an outcome."""

    def post(self, vendor, response):
        session = FakeSession(response)
        return participants_http.post(vendor, lambda: session, 'https://synthetic.invalid/v1/generate', b'{}',
                                      {'content-type': 'application/json'}, deadline=self.clock() + 60,
                                      connect_timeout=10, read_timeout=30, max_response_bytes=1024 * 1024,
                                      requested_model='synthetic-model')

    def test_the_participants_describe_reads_nothing_of_a_gemini_answer_which_is_why_the_hook_exists(self):
        self.assertEqual(participants_http.describe(self.raw), ({}, '', ''))
        self.assertEqual(adapter.describe(self.raw), (USAGE, 'gemini-4-argon', 'synthetic-response-0001'))
        self.assertEqual(participants_http.described(adapter.VENDOR, self.raw), adapter.describe(self.raw))

    def test_a_vendor_with_no_hook_is_described_exactly_as_before(self):
        participant = encoded({'id': 'resp_synthetic', 'model': 'synthetic-model-1', 'usage': {'input_tokens': 3}})
        for vendor in (participants_http.Vendor(label='Synthetic', request_id_header='x-request-id'),
                       participants_http.Vendor('Synthetic', 'request-id', None)):
            with self.subTest(vendor=vendor):
                self.assertIsNone(vendor.describe)
                self.assertEqual(participants_http.described(vendor, participant),
                                 participants_http.describe(participant))
                exchange = self.post(vendor, FakeResponse(200, participant))
                self.assertEqual((exchange.usage, exchange.returned_model, exchange.response_id),
                                 ({'input_tokens': 3}, 'synthetic-model-1', 'resp_synthetic'))

    def test_a_hook_that_raises_or_answers_in_another_shape_records_nothing_and_changes_no_outcome(self):
        def raises(raw):
            raise RuntimeError('synthetic')
        hooks = (raises, lambda raw: None, lambda raw: ([1], 7, None), lambda raw: ({}, 'm' * 101, 'i' * 141),
                 lambda raw: ('usage', 'has space', 'id with space'), lambda raw: (1, 2))
        for hook in hooks:
            with self.subTest(hook=hook):
                vendor = participants_http.Vendor(label='Synthetic', request_id_header='', describe=hook)
                self.assertEqual(participants_http.described(vendor, self.raw), ({}, '', ''))
                exchange = self.post(vendor, FakeResponse(200, self.raw))
                self.assertEqual((exchange.outcome, exchange.response_bytes, exchange.usage, exchange.usage_basis,
                                  exchange.returned_model, exchange.response_id),
                                 ('succeeded', self.raw, {}, '', '', ''))
        kept = participants_http.Vendor('Synthetic', '', describe=lambda raw: ({'n': 1}, 'model-1', 'id-1'))
        self.assertEqual(participants_http.described(kept, b''), ({'n': 1}, 'model-1', 'id-1'))

    def test_a_body_whose_url_names_its_model_carries_no_model_field_and_the_participants_check_is_unchanged(self):
        body = adapter.build_request(NOTE, PAGES, 'paste').body
        participants_http.check_shape(body, adapter.MODEL, adapter.BODY_KEYS)  # no model field, as built
        for refused in (dict(body, model=adapter.MODEL), {key: value for key, value in body.items() if key != 'contents'},
                        None, []):
            with self.subTest(refused=type(refused).__name__), self.assertRaises(ProviderUnavailable):
                participants_http.check_shape(refused, adapter.MODEL, adapter.BODY_KEYS)
        # a vendor whose body names its model must still name this one, and a body with no model is still refused there
        keys = frozenset({'model', 'input'})
        participants_http.check_shape({'model': 'synthetic-1', 'input': []}, 'synthetic-1', keys)
        for refused in ({'model': 'synthetic-2', 'input': []}, {'input': []}, {'model': None, 'input': []}):
            with self.subTest(refused=refused), self.assertRaises(ProviderUnavailable):
                participants_http.check_shape(refused, 'synthetic-1', keys)


# --- the run (jobs._send's looped branch) -------------------------------------------------------------------------------

class RunTests(_Clocked):
    def run_loop(self, *steps, request=None, interpreter=None, **options):
        session = FakeSession(*steps)
        if interpreter is None:
            interpreter, made = self.make(session)
        else:
            made = []
        if request is None:
            request = interpreter.build_request(NOTE, PAGES, 'paste')
        recorded = []
        options.setdefault('deadline_s', 540)  # what jobs._send_loop passes today: PARTICIPANT_LOOP_DEADLINE_SECONDS
        with participants_loop.recording(recorded.append):
            outcome = interpreter.send_loop(request, client_request_id='cptstudio-run-0001', original_bytes=None,
                                            **options)
        self.assertNoKey(outcome.final, request)
        return outcome, session, made, recorded, request

    def test_the_run_is_one_exchange_recorded_as_turn_one(self):
        outcome, session, _, recorded, request = self.run_loop(self.ok())
        self.assertIsInstance(outcome, participants_loop.LoopOutcome)
        self.assertEqual((outcome.outcome, outcome.stopped, len(outcome.exchanges)), ('succeeded', False, 1))
        (exchange,) = outcome.exchanges
        self.assertEqual(recorded, [exchange])  # recorded as it ended (jobs._record_exchange)
        self.assertEqual((exchange.turn, exchange.request_body, exchange.request_sha256, exchange.outcome,
                          exchange.http_status, exchange.response_bytes, exchange.usage, exchange.response_id,
                          exchange.tool_calls),
                         (1, request.body, request.canonical_sha256, 'succeeded', 200, self.raw, USAGE,
                          'synthetic-response-0001', ()))
        final = outcome.final
        self.assertEqual((final.outcome, final.sent, final.http_status, final.response_bytes, final.usage,
                          final.usage_basis, final.endpoint, final.requested_model, final.returned_model,
                          final.response_id, final.error),
                         ('succeeded', True, 200, self.raw, USAGE, 'provider_reported_tokens', ENDPOINT,
                          'gemini-4-argon', 'gemini-4-argon', 'synthetic-response-0001', ''))
        self.assertEqual(len(session.calls), 1)

    def test_a_failed_run_is_one_exchange_and_never_retried(self):
        body = TRIAL_429.read_bytes()
        outcome, session, _, recorded, _ = self.run_loop(FakeResponse(429, body), FakeResponse(200, self.raw))
        self.assertEqual((outcome.outcome, outcome.final.http_status, outcome.final.response_bytes),
                         ('failed', 429, body))
        self.assertEqual(outcome.final.error, 'Google answered HTTP 429; the response body is retained.')
        self.assertEqual((len(outcome.exchanges), len(recorded), len(session.calls)), (1, 1, 1))

    def test_an_unknown_outcome_ends_the_run_there(self):
        outcome, session, _, recorded, _ = self.run_loop(requests.exceptions.ReadTimeout('synthetic'))
        self.assertEqual((outcome.outcome, outcome.final.sent, outcome.final.endpoint), ('unknown', True, ENDPOINT))
        self.assertEqual((len(outcome.exchanges), len(recorded), len(session.calls)), (1, 1, 1))

    def test_a_stop_before_the_send_sends_nothing(self):
        def raises():
            raise RuntimeError('synthetic lock check')
        cases = ((lambda: True, adapter.STOPPED_BEFORE),
                 (raises, 'CPT Studio could not check for a Stop before sending (RuntimeError); nothing was sent.'))
        for should_stop, expect in cases:
            with self.subTest(expect=expect):
                outcome, session, made, recorded, _ = self.run_loop(self.ok(), should_stop=should_stop)
                self.assertEqual((outcome.outcome, outcome.final.sent, outcome.stopped, outcome.exchanges, recorded),
                                 ('not_sent', False, True, (), []))
                self.assertEqual((outcome.final.error, outcome.final.requested_model), (expect, 'gemini-4-argon'))
                self.assertEqual((made, session.calls), ([], []))
        asked = mock.Mock(return_value=False)
        outcome, session, _, _, _ = self.run_loop(self.ok(), should_stop=asked)
        self.assertEqual((outcome.outcome, outcome.stopped, len(session.calls)), ('succeeded', False, 1))
        asked.assert_called_once_with()  # asked once, right before the send
        outcome, _, made, _, _ = self.run_loop(self.ok(), should_stop='yes')
        self.assertEqual((outcome.outcome, outcome.stopped, outcome.final.error, made),
                         ('not_sent', False, adapter.NOT_CALLABLE, []))

    def test_a_continuation_is_refused_before_anything_is_sent(self):
        carried = (participants_loop.ExchangeRecord(turn=1, request_body={}, request_sha256='0' * 64,
                                                    outcome='succeeded'),)
        outcome, session, made, recorded, _ = self.run_loop(self.ok(), carried=carried)
        self.assertEqual((outcome.outcome, outcome.exchanges, outcome.final.error, made, recorded),
                         ('not_sent', (), adapter.NOT_CONTINUED, [], []))

    def test_the_run_deadline_is_the_send_deadline(self):
        def slow_session():
            self.clock.advance(325)
            return session
        session = FakeSession(self.ok())
        interpreter = GeminiInterpreter(self.credentials, session_factory=slow_session)
        outcome, *_ = self.run_loop(interpreter=interpreter, deadline_s=540)
        self.assertEqual(outcome.outcome, 'succeeded')
        self.assertEqual(session.calls[0]['timeout'], (5.0, 5.0))  # 330 s, not the 540 s the caller offered

    def test_no_answer_asks_for_a_tool_and_the_executor_is_never_called(self):
        executor = mock.Mock(return_value=({'codes': []}, []))
        calling = encoded(with_parts({'functionCall': {'name': 'lookup_codes', 'args': {'codes': ['45385']}}}))
        outcome, session, _, _, request = self.run_loop(self.ok(calling), execute_tool=executor)
        self.assertEqual((outcome.outcome, len(outcome.exchanges), len(session.calls)), ('succeeded', 1, 1))
        executor.assert_not_called()
        refused = adapter.answer_text(request, calling)
        self.assertIsInstance(refused, read.Refusal)  # the reader refuses it; nothing acts on it
        self.assertIn('content other than text', refused.reason)

    def test_invalid_or_foreign_requests_are_refused_before_the_run(self):
        good = adapter.build_request(NOTE, PAGES, 'paste')
        cases = ((request_with(dict(copy.deepcopy(good.body), tools=[])), {'deadline_s': 330}, adapter.NOT_BUILT),
                 (request_with(good.body, provider='astra'), {'deadline_s': 330}, 'different provider'),
                 (good, {'deadline_s': 0}, adapter.INVALID_DEADLINE))
        for request, options, expect in cases:
            with self.subTest(expect=expect):
                outcome, session, made, recorded, _ = self.run_loop(self.ok(), request=request, **options)
                self.assertEqual((outcome.outcome, outcome.exchanges, recorded, made), ('not_sent', (), [], []))
                self.assertIn(expect, outcome.final.error)


# --- the envelope (FINAL 5.4) -------------------------------------------------------------------------------------------

class EnvelopeTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.request = adapter.build_request(NOTE, PAGES, 'paste')

    def refused(self, value, expect) -> read.Refusal:
        raw = value if isinstance(value, (bytes, type(None), str)) else encoded(value)
        result = adapter.answer_text(self.request, raw)
        self.assertIsInstance(result, read.Refusal)
        self.assertEqual(result.stage, 'envelope')
        self.assertEqual(result.reason, f'{read.REFUSED}{expect}.')
        for named in ('gemini', 'google', 'argon', MODEL_TEXT.lower()):
            self.assertNotIn(named, result.reason.lower())
        return result

    def test_the_answer_is_the_text_parts_that_are_not_thinking_joined_in_order(self):
        value = with_parts({'text': f'{MODEL_TEXT} planning the answer', 'thought': True},
                           {'text': '{"part": ', 'thoughtSignature': 'c2ln'},
                           {'thoughtSignature': 'c2lnbmF0dXJlLW9ubHk='},
                           {'text': '1', 'thought': False},
                           {'text': f'{MODEL_TEXT} more thinking', 'thought': True},
                           {'text': '}'})
        self.assertEqual(adapter.answer_text(self.request, encoded(value)), '{"part": 1}')
        self.assertEqual(adapter.answer_text(self.request, encoded(envelope('{"synthetic": true}'))),
                         '{"synthetic": true}')

    def test_the_answer_text_is_what_the_reader_reads(self):
        text = json.dumps(synthetic_answer())
        answer = adapter.answer_text(self.request, encoded(envelope(text)))
        self.assertEqual(answer, text)
        parsed = read.read(answer)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed, synthetic_answer())

    def test_the_model_is_checked_before_anything_else(self):
        broken = with_parts({'functionCall': {'name': 'x'}}, finish='MAX_TOKENS', modelVersion='gemini-4-argon-001')
        broken['candidates'].append(copy.deepcopy(broken['candidates'][0]))
        broken['promptFeedback'] = {'blockReason': 'SAFETY'}
        self.refused(broken, 'the response names a model other than the one requested')
        for model in ('Gemini-4-Argon', 'gemini-4-argon ', 'models/gemini-4-argon', 'gemini-4-argon-latest',
                      'gemini-5-argon'):
            with self.subTest(model=model):
                self.refused(envelope(modelVersion=model), 'the response names a model other than the one requested')
        absent = envelope()
        del absent['modelVersion']
        for value in (absent, envelope(modelVersion=None), envelope(modelVersion=''), envelope(modelVersion=['x'])):
            with self.subTest(value=value.get('modelVersion', 'absent')):
                self.refused(value, 'the response does not name the model that answered')

    def test_the_finish_reason_must_be_stop(self):
        self.refused(with_parts({'text': '{}'}, finish='MAX_TOKENS'), 'the answer was cut off at the output limit')
        for finish in ('SAFETY', 'RECITATION', 'OTHER', 'MALFORMED_FUNCTION_CALL', 'FINISH_REASON_UNSPECIFIED'):
            with self.subTest(finish=finish):
                self.refused(with_parts({'text': '{}'}, finish=finish), f'the answer stopped for {finish}, not at its end')
        for finish in (None, '', 7):
            with self.subTest(finish=finish):
                self.refused(with_parts({'text': '{}'}, finish=finish),
                             'the answer stopped for no stated reason, not at its end')
        long = 'stopped because ' + 'x' * 60
        self.refused(with_parts({'text': '{}'}, finish=long),
                     f'the answer stopped for a value of {len(long):,} characters, not repeated, not at its end')

    def test_exactly_one_candidate(self):
        two = envelope()
        two['candidates'].append(copy.deepcopy(two['candidates'][0]))
        self.refused(two, 'the response holds 2 candidate answers, not exactly one')
        absent = envelope()
        del absent['candidates']
        for value in (absent, envelope(candidates=[]), envelope(candidates='x'), envelope(candidates=None)):
            with self.subTest(candidates=value.get('candidates', 'absent')):
                self.refused(value, 'the response holds no candidate answer')
        self.refused(envelope(candidates=['x']), 'the candidate answer is not a JSON object')

    def test_a_blocked_request_is_refused(self):
        blocked = envelope(promptFeedback={'blockReason': 'PROHIBITED_CONTENT'})
        del blocked['candidates']
        self.refused(blocked, 'the request was blocked (PROHIBITED_CONTENT)')
        self.refused(envelope(promptFeedback={'blockReason': 'SAFETY', 'safetyRatings': []}),
                     'the request was blocked (SAFETY)')
        self.assertEqual(adapter.answer_text(self.request, encoded(envelope(promptFeedback={'safetyRatings': []}))),
                         '{"synthetic": true}')  # feedback with no block reason blocks nothing

    def test_parts_that_are_not_text_are_refused(self):
        for field in ('functionCall', 'executableCode', 'codeExecutionResult', 'inlineData', 'fileData',
                      'functionResponse'):
            with self.subTest(field=field):
                self.refused(with_parts({'text': '{}'}, {field: {}}),
                             'part 2 of the answer carries content other than text (a function call, code or file '
                             'data), which this request never asks for')
        self.refused(with_parts('text'), 'part 1 of the answer is not a JSON object')
        self.refused(with_parts({'text': '{}', 'thought': 'yes'}),
                     'part 1 of the answer says whether it is thinking in a malformed way')
        self.refused(with_parts({'text': 7}), 'part 1 of the answer has text that is not a string')
        for parts in ((), ({'text': f'{MODEL_TEXT}', 'thought': True},), ({'thoughtSignature': 'c2ln'},)):
            with self.subTest(parts=parts):
                self.refused(with_parts(*parts), 'the answer carries no text outside its thinking')
        missing = envelope()
        del missing['candidates'][0]['content']
        self.refused(missing, 'the answer has no list of parts')
        not_an_object = envelope()
        not_an_object['candidates'][0]['content'] = 'x'
        self.refused(not_an_object, 'the answer has no list of parts')

    def test_a_response_that_is_not_strict_json_is_refused(self):
        cases = ((b'not json', 'the response is not valid JSON (Expecting value at character 0)'),
                 (b'{"modelVersion":"gemini-4-argon","modelVersion":"gemini-4-argon"}',
                  'the response repeats a JSON object key, so its meaning is ambiguous'),
                 (b'\xff', 'the response is not valid UTF-8'), (b'[]', 'the response is not a JSON object'),
                 (None, 'there are no response bytes'), ('{"modelVersion": "gemini-4-argon"}',
                                                         'there are no response bytes'))
        for raw, expect in cases:
            with self.subTest(raw=raw):
                self.refused(raw, expect)

    def test_an_answer_is_read_only_as_the_version_that_recorded_it(self):
        raw = encoded(envelope())
        expect = 'it was recorded by another adapter or adapter version, which this reader does not read'
        for request in (request_with(self.request.body, provider='fable'),
                        request_with(self.request.body, adapter_version='gemini-generate@cptstudio-2'),
                        SimpleNamespace(), None):
            with self.subTest(request=request):
                result = adapter.answer_text(request, raw)
                self.assertEqual(result.reason, f'{read.REFUSED}{expect}.')
        self.assertEqual(GeminiInterpreter('/nonexistent').read(self.request, raw), '{"synthetic": true}')

    def test_a_stored_answer_is_read_again_with_no_request_and_no_credentials(self):
        raw = encoded(envelope())
        with mock.patch.object(adapter, 'load_gemini_credentials', side_effect=AssertionError('read a key')), \
                mock.patch.object(participants_http, 'post', side_effect=AssertionError('sent')):
            self.assertEqual(adapter.answer_text(self.request, raw), adapter.answer_text(self.request, bytes(raw)))
            self.assertEqual(adapter.classify('succeeded', 200, raw).kind, adapter.ANSWERED)


# --- classification (FINAL 11.1; ADJUDICATION P-3, P-4, P-5) ------------------------------------------------------------

class ClassificationTests(SimpleTestCase):
    def assertKind(self, result, kind, hold=''):
        self.assertIsInstance(result, adapter.Classification)
        self.assertEqual((result.kind, result.hold), (kind, hold))
        for named in ('gemini', 'google', 'argon'):
            self.assertNotIn(named, result.why.lower())
        if kind != adapter.ANSWERED:
            self.assertTrue(result.why.endswith('.'))
        return result

    def test_the_trials_recorded_429_is_a_quota_hold(self):
        raw = TRIAL_429.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), TRIAL_429_SHA256)
        error = json.loads(raw)['error']
        self.assertEqual((error['code'], error['status']), (429, 'RESOURCE_EXHAUSTED'))
        result = self.assertKind(adapter.classify('failed', 429, raw), adapter.HOLD, adapter.QUOTA)
        # PerDay and PerMinute violations together, all on the free tier: a hold (ADJUDICATION P-4)
        self.assertEqual(result.violations, tuple(error['details'][1]['violations']))
        self.assertEqual([item['quotaId'] for item in result.violations],
                         ['GenerateRequestsPerDayPerProjectPerModel-FreeTier',
                          'GenerateRequestsPerMinutePerProjectPerModel-FreeTier',
                          'GenerateContentInputTokensPerModelPerMinute-FreeTier',
                          'GenerateContentInputTokensPerModelPerDay-FreeTier'])
        self.assertEqual((result.http_status, result.vendor_status, result.error_reasons, result.retry_delay),
                         (429, 'RESOURCE_EXHAUSTED', (), '7824s'))
        self.assertEqual(result.why, 'A daily, zero or unbilled quota was exhausted (HTTP 429, RESOURCE_EXHAUSTED): '
                                     'every request would be refused until an operator acts.')

    def test_a_per_minute_rate_refusal_fails_the_attempt_and_keeps_its_retry_info(self):
        raw = error_body(429, 'RESOURCE_EXHAUSTED',
                         quota_failure(violation(PER_MINUTE, quotaValue='1000'),
                                       violation('GenerateContentPaidTierInputTokensPerModelPerMinute')),
                         retry_info('17s'))
        result = self.assertKind(adapter.classify('failed', 429, raw), adapter.FAILED)
        self.assertEqual((result.retry_delay, len(result.violations), result.vendor_status),
                         ('17s', 2, 'RESOURCE_EXHAUSTED'))
        self.assertEqual(result.why, 'A rate limit refused this attempt (HTTP 429, RESOURCE_EXHAUSTED). It may be tried '
                                     'again after 17s.')

    def test_a_daily_zero_unbilled_or_unnamed_quota_is_a_hold(self):
        cases = {'a daily quota': [violation(PER_DAY)],
                 'a daily quota among per-minute ones': [violation(PER_MINUTE), violation(PER_DAY),
                                                         violation(PER_MINUTE)],
                 'a limit of 0 (string)': [violation(PER_MINUTE, quotaValue='0')],
                 'a limit of 0 (number)': [violation(PER_MINUTE, quotaValue=0)],
                 'a free-tier quota': [violation(PER_MINUTE + '-FreeTier')],
                 'a free-tier metric': [violation(PER_MINUTE,
                                                  metric='generativelanguage.googleapis.com/'
                                                         'generate_content_free_tier_requests')],
                 'a window it does not name': [violation('GenerateRequestsPerProjectPerModel')],
                 'no quota id, a metric with no window': [violation(None)]}
        for label, violations in cases.items():
            with self.subTest(label):
                raw = error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(*violations), retry_info('60s'))
                result = self.assertKind(adapter.classify('failed', 429, raw), adapter.HOLD, adapter.QUOTA)
                self.assertEqual((result.violations, result.retry_delay), (tuple(violations), '60s'))

    def test_a_429_with_no_quota_detail_fails_the_attempt(self):
        for raw in (error_body(429, 'RESOURCE_EXHAUSTED'), error_body(429, 'RESOURCE_EXHAUSTED', quota_failure()),
                    error_body(429, 'RESOURCE_EXHAUSTED', retry_info('5s')), b'<html>Too many requests</html>', b''):
            with self.subTest(raw=raw[:40]):
                self.assertKind(adapter.classify('failed', 429, raw), adapter.FAILED)
        self.assertEqual(adapter.classify('failed', 429, error_body(429, 'RESOURCE_EXHAUSTED', retry_info('5s')))
                         .retry_delay, '5s')
        for delay in ('5 seconds', '5', '-5s', 5, None):
            with self.subTest(delay=delay):
                raw = error_body(429, 'RESOURCE_EXHAUSTED', retry_info(delay))
                self.assertEqual(adapter.classify('failed', 429, raw).retry_delay, '')  # only the Duration form

    def test_every_p3_name_sets_its_hold_as_an_error_info_reason_and_as_a_status(self):
        expected = {'API_KEY_INVALID': 'auth', 'API_KEY_EXPIRED': 'auth', 'UNAUTHENTICATED': 'auth',
                    'API_KEY_SERVICE_BLOCKED': 'permission', 'SERVICE_DISABLED': 'permission',
                    'PERMISSION_DENIED': 'permission', 'FAILED_PRECONDITION': 'permission', 'BILLING_DISABLED': 'quota'}
        self.assertEqual(adapter.HOLD_NAMES, expected)  # ADJUDICATION P-3's list, exactly
        for name, hold in expected.items():
            with self.subTest(name=name, as_='ErrorInfo reason'):
                raw = error_body(400, 'INVALID_ARGUMENT', error_info(name))
                result = self.assertKind(adapter.classify('failed', 400, raw), adapter.HOLD, hold)
                self.assertEqual((result.error_reasons, result.vendor_status), ((name,), 'INVALID_ARGUMENT'))
                self.assertIn(name, result.why)
            with self.subTest(name=name, as_='error.status'):
                result = self.assertKind(adapter.classify('failed', 400, error_body(400, name)), adapter.HOLD, hold)
                self.assertEqual(result.vendor_status, name)

    def test_several_names_hold_for_the_key_first_then_billing_then_access(self):
        cases = ((403, 'PERMISSION_DENIED', ('SERVICE_DISABLED', 'API_KEY_INVALID'), 'auth'),
                 (403, 'PERMISSION_DENIED', ('SERVICE_DISABLED', 'BILLING_DISABLED'), 'quota'),
                 (403, 'PERMISSION_DENIED', ('BILLING_DISABLED',), 'quota'),  # the reason before the HTTP status
                 (429, 'RESOURCE_EXHAUSTED', ('API_KEY_EXPIRED',), 'auth'),  # before any quota reading
                 (401, 'UNAUTHENTICATED', ('SERVICE_DISABLED',), 'permission'))
        for status, vendor, reasons, hold in cases:
            with self.subTest(reasons=reasons):
                raw = error_body(status, vendor, *(error_info(reason) for reason in reasons))
                self.assertKind(adapter.classify('failed', status, raw), adapter.HOLD, hold)

    def test_http_401_and_403_hold_whatever_the_body(self):
        for status, hold in ((401, 'auth'), (403, 'permission')):
            for raw in (b'<html>denied</html>', b'', error_body(status, 'SOMETHING_ELSE'), b'{"error": "x"}'):
                with self.subTest(status=status, raw=raw[:30]):
                    result = self.assertKind(adapter.classify('failed', status, raw), adapter.HOLD, hold)
                    self.assertEqual(result.http_status, status)

    def test_a_400_invalid_argument_without_those_names_fails_the_attempt_only(self):
        for raw in (error_body(400, 'INVALID_ARGUMENT'), error_body(400, 'INVALID_ARGUMENT', error_info('OTHER_REASON')),
                    error_body(400, 'INVALID_ARGUMENT', error_info('api_key_invalid')),  # not the API's own form
                    b'not json'):
            with self.subTest(raw=raw[:60]):
                self.assertKind(adapter.classify('failed', 400, raw), adapter.FAILED)
        self.assertEqual(adapter.classify('failed', 400, error_body(400, 'INVALID_ARGUMENT')).why,
                         'The request failed (HTTP 400, INVALID_ARGUMENT); this attempt is over.')

    def test_server_errors_and_everything_else_fail_the_attempt(self):
        for status, raw in ((500, error_body(500, 'INTERNAL')), (503, error_body(503, 'UNAVAILABLE')),
                            (504, error_body(504, 'DEADLINE_EXCEEDED')), (404, error_body(404, 'NOT_FOUND')),
                            (502, b'<html>Bad Gateway</html>'), (307, b''), (None, b'')):
            with self.subTest(status=status):
                result = self.assertKind(adapter.classify('failed', status, raw), adapter.FAILED)
                self.assertEqual(result.http_status, status)
        self.assertEqual(adapter.classify('failed', 502, b'<html>').why, 'The request failed (HTTP 502); this attempt is '
                                                                           'over.')
        self.assertEqual(adapter.classify('failed', None, b'').why, 'The request failed (no HTTP status); this attempt '
                                                                     'is over.')

    def test_the_list_form_of_an_error_body_is_read_too(self):
        raw = encoded([{'error': {'code': 403, 'status': 'PERMISSION_DENIED',
                                  'details': [error_info('API_KEY_SERVICE_BLOCKED')]}}])
        result = self.assertKind(adapter.classify('failed', 403, raw), adapter.HOLD, adapter.PERMISSION)
        self.assertEqual(result.error_reasons, ('API_KEY_SERVICE_BLOCKED',))

    def test_a_200_is_classified_by_its_envelope(self):
        self.assertKind(adapter.classify('succeeded', 200, encoded(envelope())), adapter.ANSWERED)
        self.assertKind(adapter.classify('succeeded', None, encoded(envelope())), adapter.ANSWERED)  # a replayed one
        # P-5: an answer of another model, or naming none, is never read and holds the installation
        absent = envelope()
        del absent['modelVersion']
        for value in (envelope(modelVersion='gemini-4-argon-001'), absent):
            with self.subTest(model=value.get('modelVersion')):
                result = self.assertKind(adapter.classify('succeeded', 200, encoded(value)), adapter.HOLD,
                                         adapter.MODEL_HOLD)
                self.assertIn('No further request is sent until an operator releases the hold.', result.why)
        # C5: cut off at the output limit
        result = self.assertKind(adapter.classify('succeeded', 200, encoded(with_parts({'text': '{'}, finish='MAX_TOKENS'))),
                                 adapter.TOO_LONG)
        self.assertEqual(result.why, 'The answer was cut off at the output limit: the document is too long to be read '
                                     'in one piece.')
        for value in (with_parts({'text': '{}'}, finish='SAFETY'), b'not json', with_parts({'functionCall': {}})):
            with self.subTest(value=str(value)[:40]):
                raw = value if isinstance(value, bytes) else encoded(value)
                self.assertKind(adapter.classify('succeeded', 200, raw), adapter.FAILED)

    def test_outcomes_that_are_not_definite_are_not_classified(self):
        for outcome in ('unknown', 'not_sent', 'reserved', 'sending', 'cancelled', '', None):
            with self.subTest(outcome=outcome):
                self.assertIsNone(adapter.classify(outcome, None, b''))

    def test_violations_beyond_the_recorded_number_still_decide(self):
        many = [violation(PER_MINUTE)] * 25 + [violation(PER_DAY)]
        raw = error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(*many))
        result = self.assertKind(adapter.classify('failed', 429, raw), adapter.HOLD, adapter.QUOTA)
        self.assertEqual(result.violations, tuple(many[:adapter.MAX_VIOLATIONS]))
        self.assertKind(adapter.classify('failed', 429, error_body(429, 'RESOURCE_EXHAUSTED',
                                                                   quota_failure(*many[:25]))), adapter.FAILED)

    def test_vendor_words_are_kept_only_in_the_form_the_api_gives_them(self):
        raw = error_body(400, 'invalid argument with spaces', error_info('reason with spaces'), error_info('X' * 65))
        result = self.assertKind(adapter.classify('failed', 400, raw), adapter.FAILED)
        self.assertEqual((result.vendor_status, result.error_reasons), ('', ()))
        self.assertEqual(adapter.classify('failed', 400, error_body(400, 'A' * 41)).vendor_status, '')
        self.assertEqual(adapter.classify('failed', 400, error_body(400, 'A' * 40)).vendor_status, 'A' * 40)

    def test_the_hold_reasons_are_the_hold_tables_own(self):
        from studio.models import InterpreterHold

        self.assertEqual((adapter.AUTH, adapter.PERMISSION, adapter.QUOTA, adapter.MODEL_HOLD),
                         (InterpreterHold.AUTH, InterpreterHold.PERMISSION, InterpreterHold.QUOTA,
                          InterpreterHold.MODEL))
        reason = InterpreterHold._meta.get_field('reason').max_length
        self.assertTrue(all(len(hold) <= reason for hold in adapter.HOLD_REASONS))
        self.assertEqual(InterpreterHold._meta.get_field('vendor_status').max_length, 40)  # _STATUS keeps at most 40


# --- replay by request sha256 -------------------------------------------------------------------------------------------

class ReplayTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.tmp / 'gemini'
        self.folder.mkdir(mode=0o700)
        self.replay = ReplayInterpreter(self.tmp)

    def record(self, request, raw, mode=0o600):
        return write_file(self.folder / f'{request.canonical_sha256}.json', raw, mode)

    def test_replay_reads_the_recording_keyed_by_the_request_sha256(self):
        live = GeminiInterpreter(self.tmp / 'absent.env')
        request = self.replay.build_request(NOTE, PAGES, 'paste')
        self.assertEqual(request, live.build_request(NOTE, PAGES, 'paste'))  # the live adapter's own request
        raw = encoded(envelope())
        self.record(request, raw)
        exchange = self.replay.send(request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.usage, exchange.usage_basis, exchange.endpoint,
                          exchange.requested_model, exchange.returned_model, exchange.response_id),
                         ('succeeded', False, None, raw, hashlib.sha256(raw).hexdigest(), {},
                          'historical_replay_not_new_usage', '', 'gemini-4-argon', 'gemini-4-argon',
                          'synthetic-response-0001'))
        self.assertEqual((self.replay.name, self.replay.adapter_version, self.replay.mode, self.replay.endpoint),
                         ('gemini', 'gemini-generate@cptstudio-1', 'replay', ''))
        self.assertEqual(self.network_attempts, [])

    def test_each_request_reads_its_own_recording(self):
        first = self.replay.build_request(NOTE, PAGES, 'paste')
        second = self.replay.build_request(OTHER_NOTE, (), 'txt')
        self.assertNotEqual(first.canonical_sha256, second.canonical_sha256)
        self.record(first, encoded(envelope('{"which": 1}')))
        self.record(second, encoded(envelope('{"which": 2}')))
        for request, expected in ((first, '{"which": 1}'), (second, '{"which": 2}')):
            with self.subTest(expected=expected):
                exchange = self.replay.send(request, deadline_s=5)
                self.assertEqual(adapter.answer_text(request, exchange.response_bytes), expected)

    def test_a_missing_or_unsafe_recording_is_not_sent(self):
        request = self.replay.build_request(NOTE, PAGES, 'paste')
        exchange = self.replay.send(request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.error, exchange.requested_model),
                         ('not_sent', False, 'No recorded response for this request.', 'gemini-4-argon'))
        target = write_file(self.tmp / 'elsewhere.json', encoded(envelope()))
        (self.folder / f'{request.canonical_sha256}.json').symlink_to(target)
        self.assertEqual(self.replay.send(request, deadline_s=5).error,
                         'The recorded response is a symbolic link; it was refused.')
        (self.folder / f'{request.canonical_sha256}.json').unlink()
        self.record(request, b'x' * 2048)
        small = ReplayInterpreter(self.tmp, max_response_bytes=1024)
        self.assertEqual(small.send(request, deadline_s=5).error, 'The recorded response is larger than 1,024 bytes.')
        self.assertEqual(ReplayInterpreter(self.tmp / 'absent').send(request, deadline_s=5).error,
                         'The replay directory is not available.')
        with self.assertRaises(ValueError):
            ReplayInterpreter('')

    def test_replay_makes_the_refusals_a_live_send_makes_before_reading_anything(self):
        good = self.replay.build_request(NOTE, PAGES, 'paste')
        tools = request_with(dict(copy.deepcopy(good.body), tools=[]))
        self.record(tools, encoded(envelope()))  # a recording exists for it: still never read
        altered = copy.deepcopy(good.body)
        altered['contents'][0]['parts'][0]['text'] += ' Synthetic addition.'
        cases = ((tools, 5, adapter.NOT_BUILT),
                 (request_with(altered, canonical_sha256=good.canonical_sha256), 5, 'does not match its recorded hash'),
                 (request_with(good.body, provider='fable'), 5, 'different provider'),
                 (good, 0, adapter.INVALID_DEADLINE))
        for request, deadline, expect in cases:
            with self.subTest(expect=expect):
                exchange = self.replay.send(request, deadline_s=deadline)
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('not_sent', None))
                self.assertIn(expect, exchange.error)

    def test_a_replayed_run_is_one_exchange_and_a_stop_before_it_reads_nothing(self):
        request = self.replay.build_request(NOTE, PAGES, 'paste')
        raw = encoded(envelope())
        self.record(request, raw)
        recorded = []
        with participants_loop.recording(recorded.append):
            outcome = self.replay.send_loop(request, deadline_s=540, client_request_id='run', original_bytes=None)
        self.assertEqual((outcome.outcome, outcome.final.sent, outcome.final.endpoint, outcome.final.usage_basis,
                          outcome.final.response_bytes, len(outcome.exchanges)),
                         ('succeeded', False, '', 'historical_replay_not_new_usage', raw, 1))
        self.assertEqual((recorded[0].turn, recorded[0].request_sha256), (1, request.canonical_sha256))
        with mock.patch.object(ReplayInterpreter, 'recorded', side_effect=AssertionError('read')):
            stopped = self.replay.send_loop(request, deadline_s=540, should_stop=lambda: True)
        self.assertEqual((stopped.outcome, stopped.stopped, stopped.exchanges), ('not_sent', True, ()))

    def test_a_replayed_answer_is_read_as_a_live_one(self):
        request = self.replay.build_request(NOTE, PAGES, 'paste')
        text = json.dumps(synthetic_answer())
        self.record(request, encoded(envelope(text)))
        exchange = self.replay.send(request, deadline_s=5)
        self.assertEqual(adapter.classify(exchange.outcome, exchange.http_status, exchange.response_bytes).kind,
                         adapter.ANSWERED)
        self.assertEqual(read.read(self.replay.read(request, exchange.response_bytes)), synthetic_answer())


# --- the configured interpreter and its settings -------------------------------------------------------------------------

class ConfiguredTests(SimpleTestCase):
    def test_the_configured_interpreter_for_each_mode(self):
        with override_settings(GEMINI_MODE='disabled'):
            self.assertIsNone(adapter.get_interpreter())
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE=''):
            with self.assertRaisesMessage(ProviderUnavailable,
                                          'Live interpretation needs CPT_STUDIO_GEMINI_CREDENTIALS_FILE.'):
                adapter.get_interpreter()
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/nonexistent/gemini.env'):
            live = adapter.get_interpreter()  # the file is read at send time, never here
        self.assertIsInstance(live, GeminiInterpreter)
        self.assertEqual((live.mode, live.endpoint, live.credentials_path, live.connect_timeout, live.read_timeout,
                          live.send_deadline), ('live', ENDPOINT, '/nonexistent/gemini.env', 10, 300, 330))
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=''):
            with self.assertRaisesMessage(ProviderUnavailable, 'Replay interpretation needs CPT_STUDIO_GEMINI_REPLAY_DIR.'):
                adapter.get_interpreter()
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent/recordings'):
            replayed = adapter.get_interpreter()
        self.assertIsInstance(replayed, ReplayInterpreter)
        self.assertEqual((replayed.mode, replayed.endpoint, replayed.replay_dir, replayed.send_deadline),
                         ('replay', '', Path('/nonexistent/recordings'), 330))
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/x.env'):
            self.assertIsNone(adapter.get_interpreter('disabled'))  # an explicit mode wins
        with self.assertRaises(ValueError):
            adapter.get_interpreter('bogus')

    def test_the_settings_the_pipeline_reads(self):
        from studio import jobs

        self.assertEqual(settings.GEMINI_MODE, 'disabled')  # the default: nothing is sent
        self.assertEqual(settings.INTERPRETER_SEND_DEADLINE_SECONDS, adapter.SEND_DEADLINE_SECONDS)
        interpret = settings.JOB_DEADLINE_SECONDS['interpret']
        self.assertEqual(interpret, 380)
        # FINAL 6.3: the send and its recording fit the stage, and the stage ends before the stale-stage sweep
        self.assertLess(settings.INTERPRETER_SEND_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS, interpret)
        self.assertLess(interpret, settings.STALE_RUNNING_SECONDS)
        self.assertEqual((settings.INTERPRET_MAX_CHARS, settings.INTERPRET_MAX_PAGES), (30_000, 40))
        self.assertEqual(len(interpretation.JOB_KIND), 9)
        source = (APP / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
        # the form the installer's tests pin a credentials setting by (ops/test_install_harness.py)
        self.assertIn("GEMINI_CREDENTIALS_FILE = _env('GEMINI_CREDENTIALS_FILE', '')", source)
        literals = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    literals[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    pass
        self.assertEqual((literals['INTERPRETER_SEND_DEADLINE_SECONDS'], literals['INTERPRET_MAX_CHARS'],
                          literals['INTERPRET_MAX_PAGES'], literals['JOB_DEADLINE_SECONDS']['interpret']),
                         (330, 30_000, 40, 380))

    def run_settings(self, **environment):
        script = 'import cptstudio.settings as s\nprint(s.GEMINI_MODE)\n'
        env = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1',
               'CPT_STUDIO_SECRET_KEY': 'synthetic-settings-check-only', **environment}
        return subprocess.run([sys.executable, '-c', script], cwd=APP, env=env, capture_output=True, text=True,
                              timeout=60)

    def test_the_mode_is_validated_when_the_settings_load(self):
        for mode in ('disabled', 'replay', 'live'):
            with self.subTest(mode=mode):
                completed = self.run_settings(CPT_STUDIO_GEMINI_MODE=mode)
                self.assertEqual((completed.returncode, completed.stdout.strip()), (0, mode), completed.stderr)
        completed = self.run_settings()
        self.assertEqual((completed.returncode, completed.stdout.strip()), (0, 'disabled'), completed.stderr)
        for mode in ('bogus', 'LIVE', 'Live', ' live', ''):
            with self.subTest(mode=mode):
                completed = self.run_settings(CPT_STUDIO_GEMINI_MODE=mode)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn('RuntimeError: CPT_STUDIO_GEMINI_MODE must be disabled, replay or live.',
                              completed.stderr)

    def test_importing_the_adapter_never_reads_settings(self):
        script = ('import studio.interpretation.adapter, studio.interpretation.replay, studio.participants.pricing\n'
                  'from django.conf import settings\n'
                  'assert not settings.configured, "importing the interpreter configured settings"\n')
        environment = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'}
        completed = subprocess.run([sys.executable, '-c', script], cwd=APP, env=environment, capture_output=True,
                                   text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)


# --- no legacy reader (D17) ---------------------------------------------------------------------------------------------

class NoLegacyImportTests(SimpleTestCase):
    MODULES = ('adapter', 'replay')

    def imported(self, path: Path) -> list[str]:
        found = []
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                found += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                found.append(base)
                found += [f'{base}.{alias.name}' for alias in node.names]
            elif isinstance(node, ast.Call) and ast.unparse(node.func) in ('importlib.import_module', '__import__'):
                found.append(ast.unparse(node.args[0]) if node.args else '')
        return found

    def test_an_ast_scan_finds_no_legacy_reader_database_or_pipeline_import(self):
        for module in self.MODULES:
            with self.subTest(module=module):
                imports = self.imported(APP / 'studio' / 'interpretation' / f'{module}.py')
                self.assertIn('studio.interpretation', ' '.join(imports))  # positive control: the scan sees imports
                forbidden = [name for name in imports
                             if re.match(r"""['"]?studio\.(gi|validation|candidates|jobs|models|review)\b""", name)]
                self.assertEqual(forbidden, [])
                self.assertEqual([name for name in imports if name.split('.')[-1] == 'gi'], [])

    def test_a_fresh_interpreter_loads_no_legacy_module(self):
        code = ('import sys\nimport studio.interpretation.adapter, studio.interpretation.replay\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                    + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        loaded = completed.stdout.strip().split(',')
        self.assertIn('studio.interpretation.replay', loaded)
        self.assertEqual([name for name in loaded
                          if re.match(r'studio\.(gi|validation|candidates|jobs|models|review)\b', name)], [])
