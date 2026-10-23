"""Proposal providers (ARCHITECTURE 5.4): request building, credentials, every send
outcome, normalization of the retained synthetic responses, replay and the factory.

Nothing here reaches the network. Every test runs behind a guard that fails on
requests.Session construction, DNS lookups and socket connects (with a positive
control proving the guard trips), and every send uses an injected fake session.
All data is synthetic; credential values are fake.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ProtocolError, ReadTimeoutError

from studio.providers import (CortiProvider, CredentialsError, ProposalProvider, ProviderUnavailable, ReplayProvider,
                              canonical_body, get_provider, load_corti_credentials, normalizer_for, request_sha256)
from studio.providers import corti as corti_module
from studio.types import ProviderRequest

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'corti'
FIXTURE_SHA256 = {
    'taylor-reed.request.json': 'ad7eab6f2c3a95a0ea7e3a3d01345bb9762325a52d0b6d22e619386585fe5bd3',
    'taylor-reed.response.raw.json': '560b4c979bf734a3b6ad6cf2aafaeadfc67226e3c5463da0959bd80181e5dc7f',
    'taylor-reed.provenance.txt': '8c1f5740a21cbc0a717fab8ba4882592af4c483e1b66fbb6676762451ed9df9b',
    'rowan.response.raw.json': '205c8e586139407bf959d4f69420a41e0ebe1b50e972242f72d18e4e9cd12d86',
    'rowan.source.txt': '462613fe7482464d9cfdd73e0cf7dea28b532f7416e1e428aaa4a49143ef0f08',
}
# sha256 of the canonical encoding of the retained Taylor Reed request; a replay recording is keyed by it.
TAYLOR_REQUEST_SHA256 = '8a57be13cca8705673b80f4439884e4f699e183f2d37e84c48bcc962cf617e61'

CLIENT_ID = 'synthetic-client-id-0001'
CLIENT_SECRET = 'synthetic-client-secret-NOT-REAL-0001'
TENANT = 'synthetic-tenant'
TOKEN = 'synthetic.bearer-token_NOT.REAL~0001'
SECRETS = (CLIENT_ID, CLIENT_SECRET, TOKEN)
NOTE = ('Synthetic patient for software testing. Date of service: 2026-10-21. '
        'Colonoscopy performed to the cecum; a 6 mm polyp was removed by cold snare.')
SERVICE_DATE = date(2026, 10, 21)
TOKEN_URL = f'https://auth.us.corti.app/realms/{TENANT}/protocol/openid-connect/token'
CODING_URL = 'https://api.us.corti.app/v2/tools/coding/'


# --- offline harness --------------------------------------------------------------

class NetworkBlocked(AssertionError):
    """The guard tripped: a provider test reached the network layer."""


class OfflineTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.network_attempts = []
        patchers = {'requests.Session': mock.patch('requests.Session'),
                    'socket.getaddrinfo': mock.patch('socket.getaddrinfo'),
                    'socket.create_connection': mock.patch('socket.create_connection'),
                    'socket.connect': mock.patch.object(socket.socket, 'connect')}
        for name, patcher in patchers.items():
            patcher.start().side_effect = self._blocker(name)
            self.addCleanup(patcher.stop)
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _blocker(self, name):
        def block(*args, **kwargs):
            self.network_attempts.append(name)
            raise NetworkBlocked(f'{name} was reached; provider tests must stay offline.')
        return block

    def tearDown(self):
        self.assertEqual(self.network_attempts, [], 'A test reached the network layer.')
        super().tearDown()


class FakeResponse:
    def __init__(self, status=200, body=b'', *, chunks=None, headers=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.chunks = list(chunks) if chunks is not None else [body]
        self.closed = False

    def iter_content(self, chunk_size=1):
        for chunk in self.chunks:
            if isinstance(chunk, BaseException):
                raise chunk
            yield chunk() if callable(chunk) else chunk

    def close(self):
        self.closed = True


class FakeSession:
    """Plays scripted steps: a FakeResponse, an exception to raise, or a callable producing either."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []
        self.responses = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append({'url': url, **kwargs})
        if not self.steps:
            raise AssertionError('unexpected extra POST')
        step = self.steps.pop(0)
        step = step() if callable(step) else step
        if isinstance(step, BaseException):
            raise step
        self.responses.append(step)
        return step

    def close(self):
        self.closed = True


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def token_response(token=TOKEN, status=200):
    return FakeResponse(status, json.dumps({'access_token': token, 'token_type': 'Bearer', 'expires_in': 300}).encode())


def dotenv(**overrides) -> str:
    values = {'CORTI_CLIENT_ID': CLIENT_ID, 'CORTI_CLIENT_SECRET': CLIENT_SECRET,
              'CORTI_ENVIRONMENT': 'us', 'CORTI_TENANT_NAME': TENANT}
    values.update(overrides)
    return ''.join(f'{key}={value}\n' for key, value in values.items() if value is not None)


def write_file(path: Path, content, mode=0o600) -> Path:
    data = content.encode() if isinstance(content, str) else content
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
    os.chmod(path, mode)
    return path


def evidence(context_index, start, end, text):
    return {'contextIndex': context_index, 'start': start, 'end': end, 'text': text}


def quote(text, context_index=0, source=NOTE):
    start = source.index(text)
    return evidence(context_index, start, start + len(text), text)


def entry(code='45385', system='cpt', **fields):
    return {'system': system, 'code': code, 'display': 'untrusted provider wording', **fields}


def response(codes=(), candidates=(), **extra) -> bytes:
    return json.dumps({'codes': list(codes), 'candidates': list(candidates), **extra}).encode()


# --- request building -----------------------------------------------------------------

class RequestBuildingTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.provider = CortiProvider(self.tmp / 'never-read.env')
        self.small = CortiProvider(self.tmp / 'never-read.env', max_request_bytes=400)

    def test_body_without_a_service_date_is_the_proven_contract(self):
        request = self.provider.build_request(NOTE, None)
        self.assertEqual(request.body, {'system': ['icd10cm-outpatient', 'cpt'],
                                        'context': [{'type': 'text', 'text': NOTE}]})
        self.assertEqual(request.contexts, (NOTE,))
        self.assertEqual((request.provider, request.adapter_version), ('corti', 'corti-coding-v2@cptstudio-1'))

    def test_service_date_is_sent_as_a_second_text_context(self):
        request = self.provider.build_request(NOTE, SERVICE_DATE)
        self.assertEqual(request.body['context'],
                         [{'type': 'text', 'text': NOTE}, {'type': 'text', 'text': 'Date of service: 2026-10-21'}])
        self.assertEqual(request.contexts, (NOTE, 'Date of service: 2026-10-21'))

    def test_canonical_hash_is_sha256_of_sorted_compact_utf8_json(self):
        text = 'Synthetic café note — EGD performed.'
        request = self.provider.build_request(text, SERVICE_DATE)
        encoded = json.dumps(request.body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(request.canonical_sha256, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(canonical_body(request.body), encoded)
        self.assertIn('café note — EGD'.encode(), encoded)  # raw UTF-8, not \u escapes
        self.assertTrue(encoded.startswith(b'{"context":[{"text":'))

    def test_canonical_hash_is_stable_and_independent_of_key_order(self):
        first = self.provider.build_request(NOTE, SERVICE_DATE)
        second = self.provider.build_request(NOTE, SERVICE_DATE)
        self.assertEqual(first.canonical_sha256, second.canonical_sha256)
        reordered = {'context': [{'text': item['text'], 'type': item['type']} for item in first.body['context']],
                     'system': list(first.body['system'])}
        self.assertEqual(request_sha256(reordered), first.canonical_sha256)

    def test_every_input_change_changes_the_hash(self):
        base = self.provider.build_request(NOTE, SERVICE_DATE).canonical_sha256
        variants = {self.provider.build_request(NOTE + ' ', SERVICE_DATE).canonical_sha256,
                    self.provider.build_request(NOTE, date(2026, 10, 22)).canonical_sha256,
                    self.provider.build_request(NOTE, None).canonical_sha256}
        self.assertEqual(len(variants), 3)
        self.assertNotIn(base, variants)

    def test_retained_taylor_reed_request_is_rebuilt_exactly(self):
        retained = json.loads((FIXTURES / 'taylor-reed.request.json').read_bytes())
        request = self.provider.build_request(retained['context'][0]['text'], None)
        self.assertEqual(request.body, retained)
        independent = hashlib.sha256(json.dumps(retained, sort_keys=True, separators=(',', ':'),
                                                ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(request.canonical_sha256, independent)
        self.assertEqual(request.canonical_sha256, TAYLOR_REQUEST_SHA256)

    def _overhead(self):
        return len(canonical_body(self.small.build_request('x', None).body)) - 1

    def test_request_at_the_limit_is_built_and_one_byte_over_is_refused_not_truncated(self):
        room = self.small.max_request_bytes - self._overhead()
        at_limit = self.small.build_request('x' * room, None)
        self.assertEqual(len(canonical_body(at_limit.body)), 400)
        with self.assertRaises(ProviderUnavailable) as caught:
            self.small.build_request('x' * (room + 1), None)
        self.assertIn('401 bytes, over the 400-byte limit; nothing was truncated or sent', str(caught.exception))

    def test_the_limit_counts_utf8_bytes_not_characters(self):
        characters = (self.small.max_request_bytes - self._overhead()) // 2 + 1
        self.small.build_request('x' * characters, None)
        with self.assertRaises(ProviderUnavailable):
            self.small.build_request('é' * characters, None)

    def test_the_date_context_counts_toward_the_limit(self):
        room = self.small.max_request_bytes - self._overhead()
        self.small.build_request('x' * room, None)
        with self.assertRaises(ProviderUnavailable):
            self.small.build_request('x' * room, SERVICE_DATE)

    def test_unsendable_text_is_refused_before_anything_is_built(self):
        for text in ('', '   \n\t', 'Synthetic\x00note', 'Synthetic \ud800 note'):
            with self.subTest(text=repr(text)), self.assertRaises(ProviderUnavailable):
                self.provider.build_request(text, None)

    def test_wrong_input_types_are_programming_errors(self):
        for text, service_date in ((b'bytes', None), (None, None), (NOTE, datetime(2026, 10, 21, 9, 30)),
                                   (NOTE, '2026-10-21')):
            with self.subTest(text=type(text).__name__, service_date=repr(service_date)), self.assertRaises(TypeError):
                self.provider.build_request(text, service_date)

    def test_replay_builds_the_identical_body_and_hash(self):
        live = self.provider.build_request(NOTE, SERVICE_DATE)
        replayed = ReplayProvider(self.tmp).build_request(NOTE, SERVICE_DATE)
        self.assertEqual((replayed.body, replayed.canonical_sha256, replayed.contexts),
                         (live.body, live.canonical_sha256, live.contexts))
        self.assertEqual(replayed.provider, 'replay')

    def test_both_providers_satisfy_the_protocol(self):
        for provider, name, mode in ((self.provider, 'corti', 'live'), (ReplayProvider(self.tmp), 'replay', 'replay')):
            self.assertIsInstance(provider, ProposalProvider)
            self.assertEqual((provider.name, provider.mode, provider.adapter_version),
                             (name, mode, 'corti-coding-v2@cptstudio-1'))

    def test_constructor_refuses_nonsense_limits(self):
        for options in ({'connect_timeout': 0}, {'read_timeout': float('nan')}, {'max_request_bytes': 0},
                        {'max_response_bytes': True}, {'max_request_bytes': 1.5}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CortiProvider(self.tmp / 'x.env', **options)


# --- credentials -------------------------------------------------------------------------

class CredentialsTests(OfflineTestCase):
    VALID = ('# Synthetic Corti credentials for tests\n'
             f'CORTI_CLIENT_ID={CLIENT_ID}\n'
             f"export CORTI_CLIENT_SECRET='{CLIENT_SECRET}'\n"
             'CORTI_ENVIRONMENT = "us"  # region\n'
             '\n'
             f'CORTI_TENANT_NAME={TENANT} # inline comment\n')

    def write(self, content, mode=0o600, name='corti.env'):
        return write_file(self.tmp / name, content, mode)

    def assertRefused(self, path, expect=''):
        with self.assertRaises(CredentialsError) as caught:
            load_corti_credentials(path)
        error = caught.exception
        self.assertIsInstance(error, ProviderUnavailable)
        self.assertIsNone(error.__cause__)
        for text in (str(error), repr(error)):
            for secret in SECRETS:
                self.assertNotIn(secret, text)
            if path:
                self.assertNotIn(str(path), text)
        self.assertIn(expect, str(error))
        return str(error)

    def test_valid_file_with_comments_quotes_export_and_spacing(self):
        credentials = load_corti_credentials(self.write(self.VALID))
        self.assertEqual((credentials.client_id, credentials.client_secret, credentials.environment,
                          credentials.tenant), (CLIENT_ID, CLIENT_SECRET, 'us', TENANT))

    def test_crlf_line_endings_and_eu_are_accepted(self):
        credentials = load_corti_credentials(self.write(dotenv(CORTI_ENVIRONMENT='eu').replace('\n', '\r\n')))
        self.assertEqual((credentials.environment, credentials.client_secret), ('eu', CLIENT_SECRET))

    def test_unquoted_hash_without_preceding_space_is_part_of_the_value(self):
        credentials = load_corti_credentials(self.write(dotenv(CORTI_CLIENT_SECRET='abc#def-synthetic')))
        self.assertEqual(credentials.client_secret, 'abc#def-synthetic')

    def test_repr_and_str_redact_both_credential_values(self):
        credentials = load_corti_credentials(self.write(self.VALID))
        for text in (repr(credentials), str(credentials), f'{credentials}'):
            for secret in (CLIENT_ID, CLIENT_SECRET):
                self.assertNotIn(secret, text)
            self.assertIn("tenant='synthetic-tenant'", text)
            self.assertIn('client_secret=<redacted>', text)

    def test_missing_key(self):
        message = self.assertRefused(self.write(dotenv(CORTI_TENANT_NAME=None)), 'CORTI_TENANT_NAME is missing')
        self.assertNotIn(CLIENT_SECRET, message)

    def test_extra_or_lowercase_key(self):
        self.assertRefused(self.write(dotenv() + 'CORTI_REGION=us\n'), 'Line 5')
        lowered = dotenv().replace('CORTI_CLIENT_ID', 'corti_client_id')
        self.assertRefused(self.write(lowered, name='lower.env'), 'other than')

    def test_duplicate_key(self):
        self.assertRefused(self.write(dotenv() + 'CORTI_CLIENT_SECRET=second-synthetic-secret\n'),
                           'CORTI_CLIENT_SECRET is set more than once')

    def test_bad_environment(self):
        for index, value in enumerate(('ca', 'US', "'us '", '', 'us-east')):
            with self.subTest(value=value):
                self.assertRefused(self.write(dotenv(CORTI_ENVIRONMENT=value), name=f'env{index}.env'),
                                   'CORTI_ENVIRONMENT must be us or eu')

    def test_bad_tenant(self):
        for index, value in enumerate(('-leading', 'a' * 65, "'two words'", 'ten/ant', 'tenänt', '_x', '')):
            with self.subTest(value=value):
                self.assertRefused(self.write(dotenv(CORTI_TENANT_NAME=value), name=f'tenant{index}.env'),
                                   'CORTI_TENANT_NAME is not a valid tenant name')

    def test_tenant_length_boundary(self):
        for index, value in enumerate(('a', 'A' + 'b_-9' * 15 + 'xyz')):
            with self.subTest(length=len(value)):
                self.assertEqual(load_corti_credentials(
                    self.write(dotenv(CORTI_TENANT_NAME=value), name=f'ok{index}.env')).tenant, value)

    def test_empty_or_control_character_values(self):
        cases = (dotenv(CORTI_CLIENT_ID=''), dotenv(CORTI_CLIENT_SECRET="'   '"),
                 dotenv(CORTI_CLIENT_SECRET='synthetic\x01secret'))
        for index, content in enumerate(cases):
            with self.subTest(case=index):
                self.assertRefused(self.write(content, name=f'empty{index}.env'), 'empty or contains control')

    def test_a_bare_secret_line_is_refused_without_echoing_it(self):
        message = self.assertRefused(self.write(dotenv() + f'{CLIENT_SECRET}\n'), 'Line 5')
        self.assertIn('not a KEY=VALUE assignment', message)

    def test_quoting_errors(self):
        cases = {'unterminated': (f'CORTI_CLIENT_SECRET="{CLIENT_SECRET}', 'unterminated or malformed'),
                 'inner quote': (f'CORTI_CLIENT_SECRET="{CLIENT_SECRET}"tail"', 'unterminated or malformed'),
                 'escape': (f'CORTI_CLIENT_SECRET="{CLIENT_SECRET}\\n"', 'escapes are not supported')}
        for index, (label, (line, expect)) in enumerate(cases.items()):
            content = dotenv(CORTI_CLIENT_SECRET=None) + line + '\n'
            with self.subTest(label):
                self.assertRefused(self.write(content, name=f'quote{index}.env'), expect)

    def test_size_limit_is_32000_bytes(self):
        base = dotenv()
        exact = base + '#' * (32_000 - len(base) - 1) + '\n'
        self.assertEqual(len(exact.encode()), 32_000)
        load_corti_credentials(self.write(exact, name='exact.env'))
        self.assertRefused(self.write(exact + '#', name='over.env'), 'larger than 32,000 bytes')

    def test_permissions_must_be_owner_only(self):
        for mode in (0o640, 0o604, 0o620, 0o602, 0o660):
            with self.subTest(mode=oct(mode)):
                self.assertRefused(self.write(dotenv(), mode=mode, name=f'mode{mode:o}.env'),
                                   'accessible to group or other users')
        self.assertEqual(load_corti_credentials(self.write(dotenv(), mode=0o400, name='ro.env')).tenant, TENANT)

    def test_symlink_is_refused_even_to_a_valid_file(self):
        target = self.write(dotenv())
        link = self.tmp / 'link.env'
        link.symlink_to(target)
        self.assertRefused(link, 'symbolic link')

    def test_directory_fifo_missing_and_unconfigured_paths(self):
        directory = self.tmp / 'dir.env'
        directory.mkdir(mode=0o700)
        self.assertRefused(directory, 'not a regular file')
        fifo = self.tmp / 'fifo.env'
        os.mkfifo(fifo, 0o600)
        self.assertRefused(fifo, 'not a regular file')  # O_NONBLOCK: no hang waiting for a writer
        self.assertRefused(self.tmp / 'absent.env', 'does not exist')
        for unset in ('', None):
            self.assertRefused(unset, 'No Corti credentials file is configured')

    def test_non_utf8_content(self):
        self.assertRefused(self.write(dotenv().encode() + b'\xff\xfe'), 'not valid UTF-8')


# --- send ----------------------------------------------------------------------------------

class SendTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.enterContext(mock.patch.object(corti_module, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'corti.env', dotenv())
        self.raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()

    def send(self, *steps, deadline_s=180, request=None, **options):
        session = FakeSession(*steps)
        provider = CortiProvider(self.credentials, session_factory=lambda: session, **options)
        request = request or provider.build_request(NOTE, SERVICE_DATE)
        exchange = provider.send(request, deadline_s=deadline_s)
        self.assertNoSecrets(exchange)
        self.assertTrue(session.closed)
        self.assertTrue(all(item.closed for item in session.responses))
        return exchange, session

    def assertNoSecrets(self, exchange):
        text = repr(exchange)
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def assertNotSent(self, exchange, expect=''):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.usage), ('not_sent', False, None, None, '', {}))
        self.assertIn(expect, exchange.error)

    def assertUnknown(self, exchange, expect='', http_status=None):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256), ('unknown', True, http_status, None, ''))
        self.assertIn('outcome is unknown; reconcile it before any new attempt', exchange.error)
        self.assertIn(expect, exchange.error)

    def test_success_keeps_the_exact_bytes_and_their_sha256(self):
        raw = self.raw
        coding = FakeResponse(200, chunks=[raw[:1000], raw[1000:4000], raw[4000:]],
                              headers={'x-request-id': 'req-synthetic-0001'})
        exchange, session = self.send(token_response(), coding)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('succeeded', True, 200))
        self.assertEqual(exchange.response_bytes, raw)
        self.assertEqual(exchange.response_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(exchange.response_sha256, FIXTURE_SHA256['taylor-reed.response.raw.json'])
        self.assertEqual(exchange.usage, {'creditsConsumed': 0.019524})
        self.assertEqual(exchange.usage_basis, 'provider_reported_credits_not_usd')
        self.assertEqual(exchange.provider_request_id, 'req-synthetic-0001')
        self.assertEqual(exchange.error, '')
        self.assertEqual(exchange.latency_ms, 0.0)
        self.assertEqual(len(session.calls), 2)

    def test_calls_follow_the_proven_contract(self):
        session = FakeSession(token_response(), FakeResponse(200, self.raw))
        provider = CortiProvider(self.credentials, session_factory=lambda: session)
        request = provider.build_request(NOTE, SERVICE_DATE)
        provider.send(request, deadline_s=180)
        token_call, coding_call = session.calls
        self.assertEqual(token_call, {
            'url': TOKEN_URL,
            'data': {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                     'grant_type': 'client_credentials', 'scope': 'openid'},
            'headers': {'Accept': 'application/json'}, 'timeout': (10, 30), 'allow_redirects': False, 'stream': True})
        self.assertEqual(coding_call, {
            'url': CODING_URL, 'data': canonical_body(request.body),
            'headers': {'Authorization': f'Bearer {TOKEN}', 'Tenant-Name': TENANT,
                        'Content-Type': 'application/json', 'Accept': 'application/json'},
            'timeout': (10, 120), 'allow_redirects': False, 'stream': True})
        self.assertEqual(hashlib.sha256(coding_call['data']).hexdigest(), request.canonical_sha256)

    def test_eu_environment_changes_both_hosts(self):
        self.credentials.unlink()
        write_file(self.credentials, dotenv(CORTI_ENVIRONMENT='eu'))
        _, session = self.send(token_response(), FakeResponse(200, self.raw))
        self.assertEqual([call['url'] for call in session.calls],
                         [f'https://auth.eu.corti.app/realms/{TENANT}/protocol/openid-connect/token',
                          'https://api.eu.corti.app/v2/tools/coding/'])

    def test_token_refusal_is_not_sent(self):
        refusal = FakeResponse(401, b'{"error":"invalid_client","error_description":"synthetic"}')
        exchange, session = self.send(refusal)
        self.assertNotSent(exchange, 'Corti authentication was refused (HTTP 401); no coding request was sent.')
        self.assertEqual(len(session.calls), 1)

    def test_token_transport_failures_are_not_sent(self):
        for failure in (requests.exceptions.ReadTimeout('synthetic'), requests.exceptions.ConnectTimeout('synthetic'),
                        requests.exceptions.ConnectionError('synthetic'), RuntimeError('synthetic')):
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(failure)
                self.assertNotSent(exchange, f'Corti authentication failed ({type(failure).__name__})')
                self.assertEqual(len(session.calls), 1)

    def test_token_responses_without_a_usable_bearer_token_are_not_sent(self):
        bodies = (b'not json', b'[]', b'{"token_type":"Bearer"}', b'{"access_token":""}',
                  b'{"access_token":"has space"}', b'{"access_token":42}',
                  b'{"access_token":"' + TOKEN.encode() + b'","access_token":"other-synthetic-token"}')
        for body in bodies:
            with self.subTest(body=body):
                exchange, session = self.send(FakeResponse(200, body))
                self.assertNotSent(exchange, 'no usable bearer token')
                self.assertEqual(len(session.calls), 1)

    def test_oversized_or_broken_token_body_is_not_sent(self):
        for chunks in ([b'{' * (64 * 1024 + 1)], [b'{"access', requests.exceptions.ChunkedEncodingError('synthetic')]):
            with self.subTest(chunks=len(chunks)):
                exchange, session = self.send(FakeResponse(200, chunks=chunks))
                self.assertNotSent(exchange, 'authentication response could not be read')
                self.assertEqual(len(session.calls), 1)

    def test_token_redirect_is_not_followed(self):
        exchange, session = self.send(FakeResponse(302, b'', headers={'Location': 'https://elsewhere.invalid/'}))
        self.assertNotSent(exchange, 'HTTP 302')
        self.assertEqual(len(session.calls), 1)
        self.assertIs(session.calls[0]['allow_redirects'], False)

    def test_coding_connection_never_established_is_not_sent(self):
        never = (requests.exceptions.ConnectTimeout(MaxRetryError(None, '/v2/tools/coding/',
                                                                  ConnectTimeoutError('synthetic'))),
                 requests.exceptions.ConnectionError(MaxRetryError(None, '/v2/tools/coding/',
                                                                   NewConnectionError(None, 'synthetic refusal'))))
        for failure in never:
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(token_response(), failure)
                self.assertNotSent(exchange, 'could not be reached')
                self.assertEqual(len(session.calls), 2)

    def test_failures_after_the_request_may_have_left_are_unknown(self):
        may_have_left = (
            requests.exceptions.ReadTimeout(ReadTimeoutError(None, '/v2/tools/coding/', 'Read timed out.')),
            requests.exceptions.ConnectionError(ProtocolError('Connection aborted.', ConnectionResetError())),
            requests.exceptions.SSLError(MaxRetryError(None, '/v2/tools/coding/', ssl.SSLError('synthetic'))),
            requests.exceptions.ConnectionError('no recognisable cause'),
            RuntimeError('synthetic'),
        )
        for failure in may_have_left:
            with self.subTest(failure=type(failure).__name__):
                exchange, session = self.send(token_response(), failure)
                self.assertUnknown(exchange, type(failure).__name__)
                self.assertEqual(len(session.calls), 2)

    def test_server_error_is_failed_with_the_body_and_its_sha256(self):
        body = b'{"error":"synthetic upstream failure"}'
        exchange, session = self.send(token_response(), FakeResponse(500, body))
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('failed', True, 500))
        self.assertEqual(exchange.response_bytes, body)
        self.assertEqual(exchange.response_sha256, hashlib.sha256(body).hexdigest())
        self.assertIn('Corti answered HTTP 500; the response body is retained.', exchange.error)
        self.assertEqual((exchange.usage, exchange.usage_basis), ({}, ''))
        self.assertEqual(len(session.calls), 2)  # no retry

    def test_only_http_200_succeeds_and_an_empty_200_body_is_still_kept(self):
        for status in (201, 202, 204, 206):
            with self.subTest(status=status):
                exchange, _ = self.send(token_response(), FakeResponse(status, b'{"codes":[],"candidates":[]}'))
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('failed', True, status))
        exchange, _ = self.send(token_response(), FakeResponse(200, b''))
        self.assertEqual((exchange.outcome, exchange.response_bytes, exchange.response_sha256),
                         ('succeeded', b'', hashlib.sha256(b'').hexdigest()))

    def test_failed_response_still_reports_provider_usage(self):
        body = b'{"error":"synthetic","usageInfo":{"creditsConsumed":0}}'
        exchange, _ = self.send(token_response(), FakeResponse(422, body))
        self.assertEqual((exchange.outcome, exchange.usage, exchange.usage_basis),
                         ('failed', {'creditsConsumed': 0}, 'provider_reported_credits_not_usd'))

    def test_redirect_from_the_coding_endpoint_is_failed_and_not_followed(self):
        redirect = FakeResponse(307, b'<a>moved</a>', headers={'Location': 'https://elsewhere.invalid/v2/'})
        exchange, session = self.send(token_response(), redirect)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('failed', True, 307))
        self.assertIn('a redirect; it was not followed', exchange.error)
        self.assertEqual(exchange.response_bytes, b'<a>moved</a>')
        self.assertEqual([call['url'] for call in session.calls], [TOKEN_URL, CODING_URL])
        self.assertIs(session.calls[1]['allow_redirects'], False)

    def test_body_over_the_cap_is_unknown_and_nothing_partial_is_kept(self):
        coding = FakeResponse(200, chunks=[b'x' * 1000, b'y' * 25], headers={'X-Request-Id': 'req-synthetic-0002'})
        exchange, _ = self.send(token_response(), coding, max_response_bytes=1024)
        self.assertUnknown(exchange, 'the response exceeded 1,024 bytes', http_status=200)
        self.assertEqual(exchange.provider_request_id, 'req-synthetic-0002')

    def test_body_exactly_at_the_cap_succeeds(self):
        body = b'{"codes":[],"candidates":[]}'
        exchange, _ = self.send(token_response(), FakeResponse(200, body), max_response_bytes=len(body))
        self.assertEqual((exchange.outcome, exchange.response_bytes), ('succeeded', body))

    def test_body_read_error_is_unknown(self):
        coding = FakeResponse(200, chunks=[b'{"codes":', requests.exceptions.ChunkedEncodingError('synthetic')])
        exchange, _ = self.send(token_response(), coding)
        self.assertUnknown(exchange, 'ChunkedEncodingError', http_status=200)

    def test_invalid_deadlines_send_nothing_and_open_no_session(self):
        factory = mock.Mock()
        provider = CortiProvider(self.credentials, session_factory=factory)
        request = provider.build_request(NOTE, SERVICE_DATE)
        for deadline in (0, -1, float('nan'), float('inf'), True, '180', None):
            with self.subTest(deadline=deadline):
                self.assertNotSent(provider.send(request, deadline_s=deadline), 'deadline')
        factory.assert_not_called()

    def test_deadline_spent_during_authentication_is_not_sent(self):
        def slow_token():
            self.clock.advance(181)
            return token_response()
        exchange, session = self.send(slow_token)
        self.assertNotSent(exchange, 'the deadline passed while the response was being read')
        self.assertEqual(len(session.calls), 1)

    def test_deadline_reached_before_the_coding_request_is_not_sent(self):
        def token_at_deadline():
            self.clock.advance(180)
            return token_response()
        exchange, session = self.send(token_at_deadline)
        self.assertNotSent(exchange, 'The deadline passed before the coding request was sent')
        self.assertEqual(len(session.calls), 1)

    def test_deadline_passing_while_reading_the_body_is_unknown(self):
        def late_chunk():
            self.clock.advance(200)
            return b'"candidates":[]}'
        exchange, _ = self.send(token_response(), FakeResponse(200, chunks=[b'{"codes":[],', late_chunk]))
        self.assertUnknown(exchange, 'the deadline passed while the response was being read', http_status=200)

    def test_timeouts_are_clamped_to_the_remaining_deadline(self):
        def slow_token():
            self.clock.advance(175)
            return token_response()
        _, session = self.send(slow_token, FakeResponse(200, self.raw))
        self.assertEqual(session.calls[0]['timeout'], (10, 30))
        self.assertEqual(session.calls[1]['timeout'], (5.0, 5.0))
        _, session = self.send(token_response(), FakeResponse(200, self.raw), deadline_s=20, read_timeout=15)
        self.assertEqual([call['timeout'] for call in session.calls], [(10, 15), (10, 15)])

    def test_latency_measures_the_coding_call_only(self):
        def slow_token():
            self.clock.advance(7)
            return token_response()

        def slow_coding():
            self.clock.advance(2.5)
            return FakeResponse(200, chunks=[self.raw[:10], lambda: self.clock.advance(0.5) or self.raw[10:]])
        exchange, _ = self.send(slow_token, slow_coding)
        self.assertEqual(exchange.latency_ms, 3000.0)

    def test_credentials_are_read_at_send_time(self):
        path = self.tmp / 'later.env'
        factory = mock.Mock(side_effect=lambda: FakeSession(token_response(), FakeResponse(200, self.raw)))
        provider = CortiProvider(path, session_factory=factory)
        request = provider.build_request(NOTE, SERVICE_DATE)
        self.assertNotSent(provider.send(request, deadline_s=60),
                           'The Corti credentials file does not exist. No coding request was sent.')
        factory.assert_not_called()
        write_file(path, dotenv())
        self.assertEqual(provider.send(request, deadline_s=60).outcome, 'succeeded')
        factory.assert_called_once_with()

    def test_unprotected_credentials_never_reach_the_network(self):
        os.chmod(self.credentials, 0o644)
        factory = mock.Mock()
        provider = CortiProvider(self.credentials, session_factory=factory)
        exchange = provider.send(provider.build_request(NOTE, SERVICE_DATE), deadline_s=60)
        self.assertNotSent(exchange, 'accessible to group or other users')
        factory.assert_not_called()

    def test_altered_or_foreign_requests_are_not_sent(self):
        factory = mock.Mock()
        provider = CortiProvider(self.credentials, session_factory=factory, max_request_bytes=1000)
        altered = provider.build_request(NOTE, SERVICE_DATE)
        altered.body['context'][0]['text'] += ' Synthetic addition after hashing.'
        foreign = ReplayProvider(self.tmp).build_request(NOTE, SERVICE_DATE)
        big_body = {'system': ['icd10cm-outpatient', 'cpt'], 'context': [{'type': 'text', 'text': 'x' * 2000}]}
        oversize = ProviderRequest(provider='corti', adapter_version=corti_module.ADAPTER_VERSION, body=big_body,
                                   canonical_sha256=request_sha256(big_body), contexts=('x' * 2000,))
        cases = ((altered, 'does not match its recorded hash'), (foreign, 'different provider'),
                 (oversize, 'over the 1,000-byte limit'))
        for request, expect in cases:
            with self.subTest(expect=expect):
                self.assertNotSent(provider.send(request, deadline_s=60), expect)
        factory.assert_not_called()

    def test_session_factory_failure_is_not_sent(self):
        provider = CortiProvider(self.credentials, session_factory=mock.Mock(side_effect=RuntimeError('synthetic')))
        exchange = provider.send(provider.build_request(NOTE, SERVICE_DATE), deadline_s=60)
        self.assertNotSent(exchange, 'No HTTP session could be created (RuntimeError)')

    def test_request_id_is_kept_only_when_it_fits_the_record(self):
        cases = {None: '', 'req synthetic': '', 'r' * 121: '', 'r' * 120: 'r' * 120, 'ok-1:2/3': 'ok-1:2/3'}
        for header, expected in cases.items():
            with self.subTest(header=header):
                headers = {} if header is None else {'X-Request-Id': header}
                exchange, _ = self.send(token_response(), FakeResponse(200, self.raw, headers=headers))
                self.assertEqual(exchange.provider_request_id, expected)

    def test_usage_is_reported_only_when_the_provider_reported_it(self):
        cases = (b'{"codes":[],"candidates":[]}', b'{"codes":[],"candidates":[],"usageInfo":[1]}',
                 b'not json at all', b'{"codes":[],"candidates":[],"usageInfo":{"creditsConsumed":NaN}}')
        for body in cases:
            with self.subTest(body=body):
                exchange, _ = self.send(token_response(), FakeResponse(200, body))
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('succeeded', body))
                self.assertEqual((exchange.usage, exchange.usage_basis), ({}, ''))

    def test_response_bytes_are_kept_exactly_as_received(self):
        # The stored bytes are the provider's raw bytes (models.ProviderRun.response_bytes) and jobs.py
        # re-verifies their sha256 before normalizing, so nothing is rewritten, even an echoed token.
        body = b'{"error":"invalid token ' + TOKEN.encode() + b'"}\r\n'
        session = FakeSession(token_response(), FakeResponse(401, body))
        provider = CortiProvider(self.credentials, session_factory=lambda: session)
        exchange = provider.send(provider.build_request(NOTE, SERVICE_DATE), deadline_s=60)
        self.assertEqual((exchange.outcome, exchange.response_bytes), ('failed', body))
        self.assertEqual(exchange.response_sha256, hashlib.sha256(exchange.response_bytes).hexdigest())
        self.assertNotIn(TOKEN, exchange.error)

    def test_default_session_ignores_the_environment_and_never_retries_or_redirects(self):
        with mock.patch('requests.Session', wraps=requests.sessions.Session) as spy:
            session = corti_module.default_session()
        self.addCleanup(session.close)
        spy.assert_called_once_with()
        self.assertIs(session.trust_env, False)
        self.assertEqual(session.max_redirects, 0)
        adapter = session.get_adapter(CODING_URL)
        self.assertIsInstance(adapter, HTTPAdapter)
        self.assertEqual((adapter.max_retries.total, adapter.max_retries.read), (0, False))

    def test_the_network_guard_trips(self):
        """Positive control: without an injected session, send() hits the guard and sends nothing."""
        provider = CortiProvider(self.credentials)
        exchange = provider.send(provider.build_request(NOTE, SERVICE_DATE), deadline_s=60)
        self.assertNotSent(exchange, 'No HTTP session could be created (NetworkBlocked)')
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo('api.us.corti.app', 443)
        with self.assertRaises(NetworkBlocked):
            socket.create_connection(('127.0.0.1', 9))
        probe = socket.socket()
        self.addCleanup(probe.close)
        with self.assertRaises(NetworkBlocked):
            probe.connect(('127.0.0.1', 9))
        self.assertEqual(self.network_attempts,
                         ['requests.Session', 'socket.getaddrinfo', 'socket.create_connection', 'socket.connect'])
        self.network_attempts.clear()


# --- normalization ----------------------------------------------------------------------------

def oracle_exact(contexts, item) -> bool:
    """The exactness rule restated for the test: in-range context, 0 <= start < end <= len, equal text."""
    context_index, start, end, text = item['contextIndex'], item['start'], item['end'], item['text']
    if context_index < 0 or context_index >= len(contexts):
        return False
    source = contexts[context_index]
    return start >= 0 and end <= len(source) and start < end and source[start:end] == text


class NormalizeTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.provider = CortiProvider(self.tmp / 'never-read.env')
        self.request = self.provider.build_request(NOTE, SERVICE_DATE)

    def normalize(self, raw, request=None):
        return self.provider.normalize(request or self.request, raw)

    def assertEvidenceMatchesOracle(self, result, parsed, contexts):
        expected = {}
        for role, key in (('selected', 'codes'), ('candidate', 'candidates')):
            for index, item in enumerate(parsed[key]):
                expected[(role, item['code'], None, index)] = item.get('evidences', [])
                for alt_index, alternative in enumerate(item.get('alternatives', [])):
                    expected[('alternative', alternative['code'], item['code'], alt_index)] = \
                        alternative.get('evidences', [])
        actual = {(code.role, code.code, code.parent_code, code.index): code.evidence
                  for code in result.codes + result.internal_context}
        self.assertEqual(set(actual), set(expected))
        for key, spans in actual.items():
            raw_spans = expected[key]
            self.assertEqual([(s.context_index, s.start, s.end, s.text) for s in spans],
                             [(e['contextIndex'], e['start'], e['end'], e['text']) for e in raw_spans], key)
            self.assertEqual([s.exact for s in spans], [oracle_exact(contexts, e) for e in raw_spans], key)
        return sum(len(spans) for spans in actual.values())

    def test_retained_fixture_bytes_are_unchanged(self):
        readme = (FIXTURES / 'README.md').read_text()
        for name, sha in FIXTURE_SHA256.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), sha)
                self.assertIn(f'| `{name}` |', readme)
                self.assertIn(sha, readme)
        self.assertIn(FIXTURE_SHA256['taylor-reed.response.raw.json'],
                      (FIXTURES / 'taylor-reed.provenance.txt').read_text())

    def test_taylor_reed_retained_response(self):
        retained = json.loads((FIXTURES / 'taylor-reed.request.json').read_bytes())
        request = self.provider.build_request(retained['context'][0]['text'], None)
        raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        result = self.normalize(raw, request)
        self.assertEqual(result.problems, ())
        self.assertEqual((result.provider, result.adapter_version), ('corti', 'corti-coding-v2@cptstudio-1'))
        self.assertEqual([(c.code, c.index) for c in result.codes if c.role == 'selected'], [('99213', 2)])
        candidates = [c.code for c in result.codes if c.role == 'candidate']
        self.assertEqual(candidates, ['1036F', 'G9903', 'G8754', '99204', 'G8752', 'G8753', '99203', 'G8755',
                                      '99214', 'G8420', '3074F'])
        self.assertEqual([c.index for c in result.codes if c.role == 'candidate'], list(range(11)))
        # Category II and HCPCS G-codes stay provider codes; validation is what excludes them.
        self.assertTrue({'1036F', '3074F', 'G9903', 'G8754', 'G8420'} <= set(candidates))
        self.assertEqual({c.system for c in result.codes}, {'cpt'})
        self.assertNotIn('alternative', {c.role for c in result.codes})
        self.assertEqual([(c.role, c.code, c.parent_code, c.index) for c in result.internal_context], [
            ('selected', 'R12', None, 0), ('alternative', 'K21.9', 'R12', 0), ('alternative', 'K30', 'R12', 1),
            ('alternative', 'K92.2', 'R12', 2), ('selected', 'K59.00', None, 1),
            ('alternative', 'K59.04', 'K59.00', 0), ('alternative', 'K59.09', 'K59.00', 1)])
        self.assertEqual({c.system for c in result.internal_context}, {'icd10cm-outpatient'})
        selected = next(c for c in result.codes if c.role == 'selected')
        self.assertEqual(selected.display, '+PR OFFICE OUTPATIENT VISIT 15 MINUTES')  # untrusted, diagnostics only
        total = self.assertEvidenceMatchesOracle(result, json.loads(raw), request.contexts)
        self.assertEqual(total, 32)
        self.assertTrue(all(s.exact for c in result.codes + result.internal_context for s in c.evidence))

    def test_rowan_retained_response(self):
        source = (FIXTURES / 'rowan.source.txt').read_bytes().decode()
        request = self.provider.build_request(source, date(2026, 10, 16))
        raw = (FIXTURES / 'rowan.response.raw.json').read_bytes()
        result = self.normalize(raw, request)
        self.assertEqual(result.problems, ())
        self.assertEqual([(c.code, c.index) for c in result.codes if c.role == 'selected'],
                         [('G8754', 2), ('99213', 3), ('G8752', 4)])
        self.assertEqual([c.code for c in result.codes if c.role == 'candidate'],
                         ['1036F', 'G9903', '99204', '99203', '99214', '99284', 'G8753', 'G8420', 'G8755', '93000'])
        self.assertEqual([(c.role, c.code, c.parent_code) for c in result.internal_context], [
            ('selected', 'R10.13', None), ('alternative', 'R10.10', 'R10.13'), ('alternative', 'R10.816', 'R10.13'),
            ('selected', 'R14.0', None), ('alternative', 'K31.89', 'R14.0'), ('alternative', 'K63.89', 'R14.0')])
        total = self.assertEvidenceMatchesOracle(result, json.loads(raw), request.contexts)
        self.assertEqual(total, 45)

    def test_offsets_bind_to_the_exact_text_that_was_sent(self):
        source = (FIXTURES / 'rowan.source.txt').read_bytes().decode()
        raw = (FIXTURES / 'rowan.response.raw.json').read_bytes()
        parsed = json.loads(raw)
        # The same note with CRLF folded to LF: every span after the first line break moves.
        folded = self.provider.build_request(source.replace('\r\n', '\n'), date(2026, 10, 16))
        result = self.normalize(raw, folded)
        self.assertEvidenceMatchesOracle(result, parsed, folded.contexts)
        flags = [s.exact for c in result.codes + result.internal_context for s in c.evidence]
        self.assertEqual(flags.count(True), 0)
        # Every span shifted by one character is no longer exact.
        for item in parsed['codes'] + parsed['candidates']:
            for span in item['evidences']:
                span['start'] += 1
                span['end'] += 1
        shifted = self.normalize(json.dumps(parsed).encode(), self.provider.build_request(source, date(2026, 10, 16)))
        self.assertFalse(any(s.exact for c in shifted.codes + shifted.internal_context for s in c.evidence))

    def test_date_context_evidence_uses_context_index_1(self):
        date_span = evidence(1, 0, 27, 'Date of service: 2026-10-21')
        result = self.normalize(response([entry(evidences=[date_span])]))
        self.assertEqual([(s.context_index, s.exact) for s in result.codes[0].evidence], [(1, True)])
        without_date = self.provider.build_request(NOTE, None)
        self.assertFalse(self.normalize(response([entry(evidences=[date_span])]), without_date).codes[0].evidence[0].exact)

    def test_evidence_out_of_bounds_is_kept_but_never_exact(self):
        end = len(NOTE)
        tail = NOTE[-6:-1]
        spans = [quote('Colonoscopy performed to the cecum'),  # the one exact span
                 evidence(0, end - 3, end + 5, NOTE[end - 3:]),  # past the end of the text
                 evidence(0, end, end + 1, ''),  # starts at the end
                 evidence(2, 0, 4, 'Synt'),  # context that was never sent
                 evidence(-1, 0, 4, 'Date'),  # negative index would read the date context
                 evidence(0, -6, -1, tail),  # negative offsets would slice from the end
                 evidence(0, 10, 10, ''),  # empty span
                 evidence(0, 12, 4, NOTE[4:12]),  # inverted span
                 evidence(0, 0, 9, 'synthetic')]  # wrong case: not the same text
        result = self.normalize(response([entry(evidences=spans)]))
        self.assertEqual(result.problems, ())
        self.assertEqual([s.exact for s in result.codes[0].evidence], [True] + [False] * 8)

    def test_malformed_evidence_is_dropped_with_a_problem(self):
        good = quote('6 mm polyp')
        malformed = [42, 'text', {'contextIndex': '0', 'start': 0, 'end': 4, 'text': 'Synt'},
                     {'contextIndex': 0, 'start': 0.0, 'end': 4, 'text': 'Synt'},
                     {'contextIndex': True, 'start': 0, 'end': 4, 'text': 'Date'},  # a bool is not an index
                     {'contextIndex': 0, 'start': 0, 'end': 4}, {'contextIndex': 0, 'start': 0, 'end': 4, 'text': None}]
        result = self.normalize(response([entry(evidences=[good] + malformed)]))
        self.assertEqual([(s.text, s.exact) for s in result.codes[0].evidence], [('6 mm polyp', True)])
        self.assertEqual(result.problems, tuple(f'codes[0].evidences[{i}] is malformed; it was dropped.'
                                                for i in range(1, 8)))
        not_a_list = self.normalize(response([entry(evidences={'contextIndex': 0})]))
        self.assertEqual(not_a_list.codes[0].evidence, ())
        self.assertEqual(not_a_list.problems, ('codes[0].evidences is not a list; it was dropped.',))

    def test_unusable_documents_yield_problems_and_no_codes(self):
        cases = {
            b'': 'it is not valid JSON',
            b'\xff\xfe{}': 'it is not valid UTF-8',
            '﻿{"codes":[],"candidates":[]}'.encode(): 'it is not valid JSON',
            b'[]': 'it is not a JSON object',
            b'{"codes":[],"candidates":[],"codes":[{"system":"cpt","code":"45385"}]}': 'repeats a JSON object key',
            b'{"codes":[{"system":"cpt","code":"45385","x":NaN}],"candidates":[]}': 'non-finite number',
            b'{"codes":[],"candidates":[],"usageInfo":{"creditsConsumed":1e999}}': 'too large to represent',
            b'{"codes":[{"system":"cpt","code":"4538\\u0000"}],"candidates":[]}': 'NUL or unpaired surrogate',
            b'{"codes":[{"system":"cpt","code":"\\ud800"}],"candidates":[]}': 'NUL or unpaired surrogate',
            b'[' * 200_000 + b']' * 200_000: 'it is not valid JSON',
            b'{"codes":[' + b'9' * 5000 + b'],"candidates":[]}': 'it is not valid JSON',
        }
        for raw, expect in cases.items():
            with self.subTest(raw=raw[:40]):
                result = self.normalize(raw)
                self.assertEqual((result.codes, result.internal_context), ((), ()))
                self.assertEqual(len(result.problems), 1)
                self.assertTrue(result.problems[0].startswith('The provider response was not used: '))
                self.assertIn(expect, result.problems[0])
        self.assertEqual(self.normalize(None).problems, ('The provider response was not used: there are no '
                                                         'response bytes.',))

    def test_both_lists_are_required(self):
        cpt = entry(evidences=[quote('cold snare')])
        cases = {'no candidates': ({'codes': [cpt]}, ["it has no 'candidates' list"]),
                 'no codes': ({'candidates': [cpt]}, ["it has no 'codes' list"]),
                 'codes not a list': ({'codes': {'0': cpt}, 'candidates': []}, ["it has no 'codes' list"]),
                 'neither': ({'usageInfo': {}}, ["it has no 'codes' list", "it has no 'candidates' list"])}
        for label, (document, reasons) in cases.items():
            with self.subTest(label):
                result = self.normalize(json.dumps(document).encode())
                self.assertEqual((result.codes, result.internal_context), ((), ()))
                self.assertEqual(result.problems, tuple(f'The provider response was not used: {r}.' for r in reasons))

    def test_at_most_64_selected_codes(self):
        accepted = self.normalize(response([entry(f'{45300 + i}') for i in range(64)]))
        self.assertEqual((len(accepted.codes), accepted.problems), (64, ()))
        refused = self.normalize(response([entry(f'{45300 + i}') for i in range(65)]))
        self.assertEqual((refused.codes, refused.internal_context), ((), ()))
        self.assertEqual(refused.problems, ('The provider response was not used: it selects 65 codes, more than '
                                            'the 64 this adapter accepts.',))

    def test_only_cpt_labelled_entries_become_codes(self):
        entries = [entry('45385', 'cpt'), entry('45380', 'CPT'), entry('43239', 'Cpt'), entry('K63.5', 'icd10cm-outpatient'),
                   entry('G0121', 'HCPCS'), entry('45378', 'cpt2'), entry('45378', ' cpt')]
        result = self.normalize(response(entries))
        self.assertEqual([(c.system, c.code) for c in result.codes], [('cpt', '45385'), ('CPT', '45380'), ('Cpt', '43239')])
        self.assertEqual([(c.system, c.code, c.role) for c in result.internal_context],
                         [('icd10cm-outpatient', 'K63.5', 'selected'), ('HCPCS', 'G0121', 'selected'),
                          ('cpt2', '45378', 'selected'), (' cpt', '45378', 'selected')])

    def test_entries_without_a_system_or_code_are_dropped_with_problems(self):
        entries = ['45385', {'code': '45385'}, {'system': '', 'code': '45385'}, {'system': 5, 'code': '45385'},
                   {'system': 'cpt'}, {'system': 'cpt', 'code': '   '}, {'system': 'cpt', 'code': 45385}]
        result = self.normalize(response(candidates=entries))
        self.assertEqual((result.codes, result.internal_context), ((), ()))
        self.assertEqual(result.problems, (
            'candidates[0] is not an object; it was dropped.', 'candidates[1] has no system label; it was dropped.',
            'candidates[2] has no system label; it was dropped.', 'candidates[3] has no system label; it was dropped.',
            'candidates[4] has no code; it was dropped.', 'candidates[5] has no code; it was dropped.',
            'candidates[6] has no code; it was dropped.'))

    def test_codes_are_stripped_but_otherwise_verbatim_and_duplicates_stay_separate(self):
        result = self.normalize(response([entry(' 45385 '), entry('45385'), entry('1036f'), entry('45385-59')],
                                         [entry('45385')]))
        self.assertEqual([(c.role, c.code, c.index) for c in result.codes], [
            ('selected', '45385', 0), ('selected', '45385', 1), ('selected', '1036f', 2), ('selected', '45385-59', 3),
            ('candidate', '45385', 0)])

    def test_roles_are_never_promoted_or_merged(self):
        result = self.normalize(response([], [entry('45385', evidences=[quote('cold snare')])]))
        self.assertEqual([(c.role, c.code) for c in result.codes], [('candidate', '45385')])
        self.assertFalse(any(c.role == 'selected' for c in result.codes))

    def test_nested_alternatives(self):
        alternatives = [{'code': '45380', 'display': 'x', 'evidences': [quote('6 mm polyp')]},
                        {'code': '45384', 'system': 'CPT'},
                        {'code': 'K63.5', 'system': 'icd10cm-outpatient'},
                        'junk', {'display': 'no code'}, {'code': '45381', 'system': 7}]
        result = self.normalize(response([entry('45385', alternatives=alternatives),
                                          entry('K63.5', 'icd10cm-outpatient', alternatives=[{'code': 'D12.6'}])]))
        self.assertEqual([(c.role, c.system, c.code, c.parent_code, c.index) for c in result.codes], [
            ('selected', 'cpt', '45385', None, 0), ('alternative', 'cpt', '45380', '45385', 0),
            ('alternative', 'cpt', '45384', '45385', 1)])
        self.assertEqual([s.exact for s in result.codes[1].evidence], [True])
        self.assertEqual([(c.role, c.code, c.parent_code) for c in result.internal_context],
                         [('selected', 'K63.5', None), ('alternative', 'D12.6', 'K63.5')])
        self.assertEqual(result.problems, (
            'codes[0].alternatives[2] declares a system different from its parent; it was dropped.',
            'codes[0].alternatives[3] is not an object; it was dropped.',
            'codes[0].alternatives[4] has no code; it was dropped.',
            'codes[0].alternatives[5] declares a system different from its parent; it was dropped.'))
        broken = self.normalize(response([entry('45385', alternatives={'code': '45380'})]))
        self.assertEqual(([c.code for c in broken.codes], broken.problems),
                         (['45385'], ('codes[0].alternatives is not a list; it was dropped.',)))

    def test_display_is_kept_only_as_untrusted_text(self):
        result = self.normalize(response([entry(display=None), entry(display=['x']), entry(display='As given')]))
        self.assertEqual([c.display for c in result.codes], ['', '', 'As given'])

    def test_a_response_is_read_only_as_the_provider_and_adapter_that_recorded_it(self):
        raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        replayed = ReplayProvider(self.tmp).build_request(NOTE, SERVICE_DATE)
        older = ProviderRequest(provider='corti', adapter_version='corti-coding-v1@cptstudio-0', body=self.request.body,
                                canonical_sha256=self.request.canonical_sha256, contexts=self.request.contexts)
        for request, recorded in ((replayed, "'replay' with adapter 'corti-coding-v2@cptstudio-1'"),
                                  (older, "'corti' with adapter 'corti-coding-v1@cptstudio-0'")):
            with self.subTest(recorded=recorded):
                result = self.normalize(raw, request)
                self.assertEqual((result.provider, result.codes, result.internal_context), ('corti', (), ()))
                self.assertEqual(result.problems, (f'The provider response was not used: it was recorded for '
                                                   f"{recorded}, not 'corti' with 'corti-coding-v2@cptstudio-1'.",))

    def test_normalizer_for_a_stored_run_matches_the_provider_and_survives_a_json_round_trip(self):
        raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        stored = json.loads(json.dumps({'body': self.request.body, 'contexts': list(self.request.contexts)}))
        rebuilt = ProviderRequest(provider='corti', adapter_version=corti_module.ADAPTER_VERSION, body=stored['body'],
                                  canonical_sha256=self.request.canonical_sha256, contexts=tuple(stored['contexts']))
        self.assertEqual(normalizer_for('corti')(rebuilt, raw), self.provider.normalize(self.request, raw))
        replay = ReplayProvider(self.tmp)
        replayed = replay.build_request(NOTE, SERVICE_DATE)
        self.assertEqual(normalizer_for('replay')(replayed, raw), replay.normalize(replayed, raw))
        self.assertEqual(normalizer_for('replay')(self.request, raw).codes, ())  # a live run is not a replay
        for unknown in ('astra', 'Corti', ''):
            with self.subTest(unknown=unknown), self.assertRaises(ProviderUnavailable):
                normalizer_for(unknown)

    def test_replay_shares_the_normalizer(self):
        raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        replay = ReplayProvider(self.tmp)
        live = self.normalize(raw)
        replayed = replay.normalize(replay.build_request(NOTE, SERVICE_DATE), raw)
        self.assertEqual(replayed.provider, 'replay')
        self.assertEqual((replayed.codes, replayed.internal_context, replayed.problems),
                         (live.codes, live.internal_context, live.problems))


# --- replay -----------------------------------------------------------------------------------------

class ReplayTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.replay = ReplayProvider(self.tmp)
        self.raw = (FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        retained = json.loads((FIXTURES / 'taylor-reed.request.json').read_bytes())
        self.request = self.replay.build_request(retained['context'][0]['text'], None)

    def record(self, request, raw, mode=0o600):
        return write_file(self.tmp / f'{request.canonical_sha256}.json', raw, mode)

    def test_recorded_response_replays_without_new_usage(self):
        self.assertEqual(self.request.canonical_sha256, TAYLOR_REQUEST_SHA256)
        self.record(self.request, self.raw)
        exchange = self.replay.send(self.request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('succeeded', False, None))
        self.assertEqual(exchange.response_bytes, self.raw)
        self.assertEqual(exchange.response_sha256, FIXTURE_SHA256['taylor-reed.response.raw.json'])
        self.assertEqual((exchange.usage, exchange.usage_basis), ({}, 'historical_replay_not_new_usage'))
        self.assertEqual((exchange.provider_request_id, exchange.latency_ms, exchange.error), ('', None, ''))
        self.assertIn(b'"usageInfo":{"creditsConsumed":0.019524}', exchange.response_bytes)  # history, not new usage

    def test_recording_is_keyed_by_the_hash_a_live_request_carries(self):
        live = CortiProvider(self.tmp / 'never-read.env').build_request(NOTE, SERVICE_DATE)
        self.record(live, self.raw)
        exchange = self.replay.send(self.replay.build_request(NOTE, SERVICE_DATE), deadline_s=5)
        self.assertEqual(exchange.outcome, 'succeeded')

    def test_missing_recording_is_not_sent(self):
        exchange = self.replay.send(self.request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.response_bytes), ('not_sent', False, None))
        self.assertEqual(exchange.error, 'No recorded response for this request.')

    def test_unavailable_directory_is_not_sent(self):
        exchange = ReplayProvider(self.tmp / 'absent').send(self.request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.error), ('not_sent', 'The replay directory is not available.'))

    def test_an_empty_directory_setting_never_means_the_working_directory(self):
        for empty in ('', None):
            with self.subTest(empty=empty), self.assertRaises(ValueError):
                ReplayProvider(empty)

    def test_symlinked_or_oversized_recordings_are_refused(self):
        target = write_file(self.tmp / 'elsewhere.json', self.raw)
        (self.tmp / f'{self.request.canonical_sha256}.json').symlink_to(target)
        exchange = self.replay.send(self.request, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.error),
                         ('not_sent', 'The recorded response is a symbolic link; it was refused.'))
        (self.tmp / 'small').mkdir()
        small = ReplayProvider(self.tmp / 'small', max_response_bytes=100)
        write_file(self.tmp / 'small' / f'{self.request.canonical_sha256}.json', self.raw)
        exchange = small.send(small.build_request(self.request.contexts[0], None), deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.error),
                         ('not_sent', 'The recorded response is larger than 100 bytes.'))

    def test_altered_foreign_or_undated_requests_are_not_replayed(self):
        self.record(self.request, self.raw)
        altered = copy.deepcopy(self.request)
        altered.body['context'][0]['text'] += ' altered'
        foreign = CortiProvider(self.tmp / 'never-read.env').build_request(self.request.contexts[0], None)
        for request, deadline, expect in ((altered, 5, 'does not match its recorded hash'),
                                          (foreign, 5, 'different provider'),
                                          (self.request, 0, 'deadline')):
            with self.subTest(expect=expect):
                exchange = self.replay.send(request, deadline_s=deadline)
                self.assertEqual(exchange.outcome, 'not_sent')
                self.assertIn(expect, exchange.error)


# --- factory --------------------------------------------------------------------------------------------

class GetProviderTests(OfflineTestCase):
    def test_disabled_mode_has_no_provider(self):
        self.assertIsNone(get_provider('disabled'))
        with override_settings(PROVIDER_MODE='disabled'):
            self.assertIsNone(get_provider())

    def test_live_mode_builds_corti_from_settings_without_reading_credentials(self):
        path = str(self.tmp / 'not-yet-created.env')
        with override_settings(CORTI_CREDENTIALS_FILE=path, PROVIDER_CONNECT_TIMEOUT_SECONDS=7,
                               PROVIDER_READ_TIMEOUT_SECONDS=99, PROVIDER_MAX_REQUEST_BYTES=1234,
                               PROVIDER_MAX_RESPONSE_BYTES=5678):
            provider = get_provider('live')
        self.assertIsInstance(provider, CortiProvider)
        self.assertEqual((provider.credentials_path, provider.connect_timeout, provider.read_timeout,
                          provider.max_request_bytes, provider.max_response_bytes), (path, 7, 99, 1234, 5678))

    def test_replay_mode_and_the_settings_default(self):
        with override_settings(PROVIDER_MODE='replay', REPLAY_DIR=str(self.tmp)):
            provider = get_provider()
        self.assertIsInstance(provider, ReplayProvider)
        self.assertEqual(provider.replay_dir, self.tmp)

    def test_missing_configuration_raises(self):
        with override_settings(CORTI_CREDENTIALS_FILE=''), self.assertRaises(ProviderUnavailable):
            get_provider('live')
        with override_settings(REPLAY_DIR=''), self.assertRaises(ProviderUnavailable):
            get_provider('replay')
        with self.assertRaises(ValueError):
            get_provider('LIVE')

    def test_importing_the_package_never_reads_settings(self):
        script = ('import studio.providers\n'
                  'from django.conf import settings\n'
                  'assert not settings.configured, "importing studio.providers configured settings"\n')
        environment = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'}
        completed = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parent.parent,
                                   env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
