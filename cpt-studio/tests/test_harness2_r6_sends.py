"""Refutation round 6, R6-SENDS (parity-1): what the access check's receipt says of an answer other than HTTP 200
(studio/management/commands/participant_access_check.py, _receipt; HARNESS.md 12.13, sends-1).

The adapters end their sentence for such an answer with "; the response body is retained." (studio/participants/
http.py post; studio/providers/corti.py _predict). That is true in the pipeline, which keeps the answer (ProviderRun,
ProviderExchange), and it was false in the access check's receipt: the command writes no row, and its receipt holds the
body's sha256 and not the body. Since round 5 (sends-1) the installer repeats the receipt's error to the operator, who
was told the vendor's answer was kept when nothing kept it, and to run the check again once the cause is known. Now the
receipt says that the access check keeps no copy of the response body, for Astra, Fable and Corti's coding call alike,
whether the sentence stands alone or inside the tool loop's "The tool loop stopped at exchange N: ...". Before that it
names the vendor's own error code, else its error type, when the body's "error" object gives one as 1 to 48 lowercase
letters and underscores, and never the vendor's message, which OpenAI's answer to a wrong key fills with part of the
key.

The answers are in the shapes the round-6 lens and its verifier fed the command (refute-harness-r6/parity,
verify-harness-r6/v3-parity-rest) - OpenAI's and Anthropic's error objects, and a body with none - with synthetic
values. Each message carries a marker that must never be printed. Every sentence is written out as the command must
print it. Offline: requests.Session is a fake session and the credentials are the suite's synthetic ones. The command
runs through tests.test_participants_access_check's own helper, which asserts that nothing is written to the database,
that no credential value is printed and that nothing printed says "retained".
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from tests import test_participants_access_check as access
from tests.test_participants_support import (FACTS_ARGUMENTS, OPENAI_KEY, FakeResponse, OfflineDatabaseTestCase,
                                             anthropic_env, astra_tool_call, fable_tool_use, openai_env, write_file)
from tests.test_providers import dotenv as corti_env, token_response

MARK = 'SYNTHETIC-R6-VENDOR-MESSAGE'
KEPT = "; the access check keeps no copy of the response body (its sha256 is the receipt's response_sha256)."
OPENAI_401 = json.dumps({'error': {'message': f'Incorrect API key provided: sk-proj-****0001. {MARK}',
                                   'type': 'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}}).encode()
OPENAI_429 = json.dumps({'error': {'message': f'You exceeded your current quota. {MARK}', 'type': 'insufficient_quota',
                                   'param': None, 'code': 'insufficient_quota'}}).encode()
ANTHROPIC_401 = json.dumps({'type': 'error', 'error': {'type': 'authentication_error',
                                                       'message': f'invalid x-api-key {MARK}'},
                            'request_id': 'req_synthetic_r6_401'}).encode()
ANTHROPIC_404 = json.dumps({'type': 'error', 'error': {'type': 'not_found_error',
                                                       'message': f'model: claude-fable-5-1 {MARK}'},
                            'request_id': 'req_synthetic_r6_404'}).encode()
ANTHROPIC_529 = json.dumps({'type': 'error', 'error': {'type': 'overloaded_error', 'message': f'Overloaded {MARK}'},
                            'request_id': 'req_synthetic_r6_529'}).encode()
CORTI_403 = json.dumps({'detail': f'tenant has no coding entitlement {MARK}'}).encode()
# The answer of round 5's capture (verify-harness-r5/v3-sends-rest, 'vendor_401'), which ops/test_install_r5_sends.py's
# VENDOR_401_RECEIPT records (its response_sha256): the installer's tests feed the installer that receipt.
ROUND_5_401 = json.dumps({'error': {'message': 'Incorrect API key provided (synthetic).',
                                    'type': 'invalid_request_error', 'param': None,
                                    'code': 'invalid_api_key'}}).encode()
INSTALLER_TESTS = Path(__file__).resolve().parents[1] / 'ops' / 'test_install_r5_sends.py'
LABELS = {'astra': 'OpenAI', 'fable': 'Anthropic', 'corti': 'Corti'}
DID_NOT_PASS = {'astra': 'The Astra access check did not pass: see the receipt.',
                'fable': 'The Fable access check did not pass: see the receipt.',
                'corti': 'The Corti access check did not pass: see the receipt.'}
HEADER = {'astra': 'x-request-id', 'fable': 'request-id', 'corti': 'X-Request-Id'}


def tool_turn(name, number):
    """A 200 answer asking for one tool call, as exchange ``number`` of ``name``'s loop."""
    call = (f'call_r6_{number}' if name == 'astra' else f'toolu_r6_{number}', 'cms_code_facts', FACTS_ARGUMENTS)
    body = astra_tool_call(call, number=number) if name == 'astra' else fable_tool_use(call, number=number)
    return FakeResponse(200, body, headers={HEADER[name]: f'req_r6_turn_{number}'})


def answered(name, status, body):
    """The steps of a check whose vendor answers ``status`` with ``body`` (Corti's after its token request)."""
    answer = FakeResponse(status, body, headers={HEADER[name]: f'req-r6-{status}'})
    return (token_response(), answer) if name == 'corti' else (answer,)


def installer_constant(name):
    """A string constant of the installer's round-5 tests, read with ast: nothing of ops/ is imported here."""
    tree = ast.parse(INSTALLER_TESTS.read_text(encoding='utf-8'))
    (value,) = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and [getattr(target, 'id', None) for target in node.targets] == [name]
                and isinstance(node.value, ast.Constant)]
    return value


class VendorAnswerReceiptTests(OfflineDatabaseTestCase):
    """The access check through the real command, its adapters and their session factories (requests.Session patched
    to a fake session), with tests.test_participants_access_check's own helpers: ``check`` (no database row, no
    credential value and nothing saying "retained" printed) and ``rows``."""

    rows = access.AccessCheckTests.rows
    check = access.AccessCheckTests.check

    def setUp(self):
        super().setUp()
        self.live = {'ASTRA_MODE': 'live', 'FABLE_MODE': 'live', 'PROVIDER_MODE': 'live',
                     'OPENAI_CREDENTIALS_FILE': str(write_file(self.tmp / 'openai.env', openai_env())),
                     'ANTHROPIC_CREDENTIALS_FILE': str(write_file(self.tmp / 'anthropic.env', anthropic_env())),
                     'CORTI_CREDENTIALS_FILE': str(write_file(self.tmp / 'corti.env', corti_env())),
                     'AUTHORIZATION_REF': access.AUTHORIZATION}

    def refused(self, name, steps, posted):
        """The receipt of a check whose answer was not 200, after ``posted`` POSTs; nothing of the message printed."""
        receipt, error, session = self.check(name, *steps)
        self.assertEqual(error, DID_NOT_PASS[name])
        self.assertEqual(len(session.calls), posted)  # never retried
        self.assertNotIn(MARK, json.dumps(receipt) + error)
        self.assertEqual((receipt['outcome'], receipt['sent'], receipt['reading']), ('failed', True, None))
        return receipt

    def test_a_refusal_says_the_check_keeps_no_copy_of_the_body_and_names_the_vendor_s_own_error(self):
        # parity-1's inputs: a revoked or wrong key (401), a model the account cannot use (404), a tenant refused (403)
        for name, status, body, said in (
                ('astra', 401, OPENAI_401, 'OpenAI answered HTTP 401 with the error code invalid_api_key; the access '
                                           "check keeps no copy of the response body (its sha256 is the receipt's "
                                           'response_sha256).'),
                ('fable', 401, ANTHROPIC_401, 'Anthropic answered HTTP 401 with the error type authentication_error; '
                                              'the access check keeps no copy of the response body (its sha256 is the '
                                              "receipt's response_sha256)."),
                ('fable', 404, ANTHROPIC_404, 'Anthropic answered HTTP 404 with the error type not_found_error; the '
                                              'access check keeps no copy of the response body (its sha256 is the '
                                              "receipt's response_sha256)."),
                ('corti', 403, CORTI_403, 'Corti answered HTTP 403; the access check keeps no copy of the response '
                                          "body (its sha256 is the receipt's response_sha256).")):
            with self.subTest(name=name, status=status):
                receipt = self.refused(name, answered(name, status, body), 2 if name == 'corti' else 1)
                self.assertEqual(receipt['error'], said)
                self.assertEqual((receipt['http_status'], receipt['request_id'], receipt['response_sha256']),
                                 (status, f'req-r6-{status}', hashlib.sha256(body).hexdigest()))
                self.assertNotIn('sk-proj-', json.dumps(receipt))  # the part of the key OpenAI's message quotes

    def test_the_installer_tests_are_fed_the_sentence_the_command_prints(self):
        # ops/test_install_r5_sends.py's VENDOR_401_RECEIPT is round 5's capture; its error is the command's for the
        # same answer, read here from that file and printed here by the command
        receipt = self.refused('astra', (FakeResponse(401, ROUND_5_401, headers={'x-request-id': 'req_401'}),), 1)
        self.assertEqual(receipt['response_sha256'], '2c6a3aa64330943275ed2cccfbefed0db3adc802c760cf758f06999e9b60e379')
        self.assertEqual(receipt['error'], installer_constant('VENDOR_401_ERROR'))
        self.assertEqual(receipt['error'], 'OpenAI answered HTTP 401 with the error code invalid_api_key; the access '
                                           "check keeps no copy of the response body (its sha256 is the receipt's "
                                           'response_sha256).')

    def test_the_clause_inside_the_tool_loop_s_sentence_is_the_access_check_s_too(self):
        for name, status, body, said in (
                ('astra', 429, OPENAI_429, 'The tool loop stopped at exchange 2: OpenAI answered HTTP 429 with the '
                                           'error code insufficient_quota; the access check keeps no copy of the '
                                           "response body (its sha256 is the receipt's response_sha256)."),
                ('fable', 529, ANTHROPIC_529, 'The tool loop stopped at exchange 2: Anthropic answered HTTP 529 with '
                                              'the error type overloaded_error; the access check keeps no copy of the '
                                              "response body (its sha256 is the receipt's response_sha256).")):
            with self.subTest(name=name):
                receipt = self.refused(name, (tool_turn(name, 1), *answered(name, status, body)), 2)
                self.assertEqual(receipt['error'], said)
                self.assertEqual(receipt['exchange_count'], 2)
                self.assertEqual([item['http_status'] for item in receipt['exchanges']], [200, status])
                # the sha256 the sentence points to is the answer it is about: the last exchange's
                self.assertEqual(receipt['response_sha256'], receipt['exchanges'][1]['response_sha256'])
                self.assertEqual(receipt['response_sha256'], hashlib.sha256(body).hexdigest())

    def test_every_answer_other_than_200_of_each_participant_says_so(self):
        # an empty body names no error; a redirect is said to be one and was not followed, as the adapters say
        for name in ('astra', 'fable', 'corti'):
            for status in (201, 204, 301, 307, 400, 401, 403, 404, 408, 413, 422, 429, 500, 502, 503, 529):
                with self.subTest(name=name, status=status):
                    receipt = self.refused(name, answered(name, status, b''), 2 if name == 'corti' else 1)
                    redirect = ' (a redirect; it was not followed)' if 300 <= status < 400 else ''
                    self.assertEqual(receipt['error'], f'{LABELS[name]} answered HTTP {status}{redirect}{KEPT}')
                    self.assertEqual(receipt['response_sha256'], hashlib.sha256(b'').hexdigest())

    def test_only_a_code_or_type_in_its_strict_shape_is_named_and_never_the_message(self):
        code, kind = ' with the error code ', ' with the error type '
        for body, named in (
                ({'error': {'code': 'model_not_found', 'type': 'invalid_request_error', 'message': MARK}},
                 code + 'model_not_found'),
                ({'error': {'code': None, 'type': 'invalid_request_error', 'message': MARK}},
                 kind + 'invalid_request_error'),
                ({'error': {'code': 'Invalid_API_Key', 'type': 'invalid_request_error'}},
                 kind + 'invalid_request_error'),  # a code in no such shape: the type, which is in it
                ({'error': {'code': 'a' * 48}}, code + 'a' * 48),
                ({'error': {'code': 'a' * 49}}, ''),
                ({'error': {'code': OPENAI_KEY, 'type': f'{OPENAI_KEY} {MARK}'}}, ''),
                ({'error': {'code': 'sk-proj-****0001'}}, ''),
                ({'error': {'code': 'error_401'}}, ''),
                ({'error': {'code': 'invalid api key'}}, ''),
                ({'error': {'code': 401}}, ''),
                ({'error': {'code': ['invalid_api_key']}}, ''),
                ({'error': {'code': ''}}, ''),
                ({'error': {'code': 'invalid_api_key\n'}}, ''),
                ({'error': {'code': 'invalіd_api_key'}}, ''),  # a Cyrillic letter that looks like an i
                ({'error': {'code': 'invalid_Key'}}, ''),  # the Kelvin sign, which a case-blind rule reads as k
                ({'error': {'message': MARK}}, ''),
                ({'error': 'invalid_api_key'}, ''),
                ({'code': 'invalid_api_key', 'type': 'error'}, ''),
                (['invalid_api_key'], ''),
                (f'<html>502 Bad Gateway {MARK}</html>', ''),
                ('{"error": {"code": "invalid_api_key", "code": "model_not_found"}}', ''),  # a repeated key: refused
                ('{"error": {"code": "invalid_api_key", "n": NaN}}', ''),  # a non-finite number: refused
                (b'\xff\xfe{"error": {"code": "invalid_api_key"}}', '')):  # not UTF-8
            raw = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
            with self.subTest(body=raw[:60]):
                receipt = self.refused('astra', answered('astra', 400, raw), 1)
                self.assertEqual(receipt['error'], f'OpenAI answered HTTP 400{named}{KEPT}')
                self.assertNotIn(OPENAI_KEY, json.dumps(receipt))

    def test_an_answer_not_read_whole_says_nothing_of_a_body(self):
        # The status was read and the body was cut: the outcome is unknown, no body's sha256 is recorded, and the
        # sentence, which never said the body was retained, says nothing of one (KEPT is said only in RETAINED's place)
        for name, posted in (('astra', 1), ('fable', 1), ('corti', 2)):
            with self.subTest(name=name):
                answer = FakeResponse(401, chunks=[b'{"error": {"code": "invalid_api_key"', OSError('synthetic cut')],
                                      headers={HEADER[name]: 'req-r6-cut'})
                receipt, error, session = self.check(name, *((token_response(), answer) if name == 'corti'
                                                             else (answer,)))
                self.assertEqual(error, DID_NOT_PASS[name])
                self.assertEqual(len(session.calls), posted)
                self.assertEqual((receipt['outcome'], receipt['http_status'], receipt['response_sha256']),
                                 ('unknown', 401, ''))
                self.assertIn('no complete response was read (OSError)', receipt['error'])
                self.assertNotIn('response body', receipt['error'])
                self.assertNotIn('invalid_api_key', receipt['error'])

    def test_a_corti_token_refusal_keeps_its_own_sentence(self):
        # Only the coding call's answer carries the adapters' clause; a refused token request sends no coding request
        receipt, error, session = self.check('corti', token_response(status=401))
        self.assertEqual(error, DID_NOT_PASS['corti'])
        self.assertEqual(len(session.calls), 1)
        self.assertEqual((receipt['outcome'], receipt['sent']), ('not_sent', False))
        self.assertEqual(receipt['error'], 'Corti authentication was refused (HTTP 401); no coding request was sent.')

    def test_the_longest_sentence_is_within_the_installer_s_bound(self):
        # The installer repeats a receipt's error only whole and only up to 300 characters (round 5, sends-1). The
        # longest this repair writes: Fable's label, at the last exchange a run may make (PARTICIPANT_MAX_EXCHANGES, 4),
        # a redirect, a 48-character error type.
        steps = (tool_turn('fable', 1), tool_turn('fable', 2), tool_turn('fable', 3),
                 *answered('fable', 308, json.dumps({'type': 'error', 'error': {'type': 'x' * 48}}).encode()))
        receipt = self.refused('fable', steps, 4)
        self.assertEqual(receipt['error'], 'The tool loop stopped at exchange 4: Anthropic answered HTTP 308 (a '
                                           'redirect; it was not followed) with the error type ' + 'x' * 48 + '; the '
                                           'access check keeps no copy of the response body (its sha256 is the '
                                           "receipt's response_sha256).")
        self.assertLessEqual(len(receipt['error']), 300)
