"""studio.fable.client and studio.fable.credentials (BUILD-SPEC 4.1): the request, the SDK call and every outcome, with
fake SDK stream objects (no network), the replay mode, and the strict credentials file."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import anthropic
from django.test import SimpleTestCase, override_settings

from studio.fable import BUSY, DECLINED, DOCUMENT, FAILED, HOLD, TOO_LONG, UNAVAILABLE, UNKNOWN
from studio.fable import client, credentials, prompts
from studio.fable.document import Document
from tests.support import coding as f

KEY = 'sk-ant-synthetic-key-never-sent'


def document():
    block = {'type': 'document', 'title': 'synthetic.pdf', 'citations': {'enabled': True},
             'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': 'JVBERi0xLjc='}}
    stored = {**block, 'source': {**block['source'], 'data': {'$original_sha256': 'ab' * 32, '$original_bytes': 8}}}
    return Document(kind='pdf', title='synthetic.pdf', data=b'%PDF-1.7', block=block, stored_block=stored,
                    sha256='ab' * 32, source_sha256='ab' * 32)


def request(effort='max'):
    return client.build_request(system=prompts.READER_SYSTEM, document=document(), instruction='Code this document.',
                                effort=effort)


class FakeResponse:
    """Enough of an HTTP response for the SDK's own error classes."""

    def __init__(self, status):
        self.status_code, self.headers, self.request = status, {'request-id': 'req_error'}, object()


def status_error(cls, status, error_type, message='synthetic error'):
    body = {'type': 'error', 'error': {'type': error_type, 'message': message}} if error_type else None
    return cls(f'Error code: {status}', response=FakeResponse(status), body=body)


class FakeMessage:
    def __init__(self, data):
        self.data = data

    def model_dump(self, mode='python'):
        assert mode == 'json'
        return self.data


class FakeStream:
    def __init__(self, answer):
        self.answer, self.request_id = answer, 'req_stream'

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if isinstance(self.answer, BaseException):
            raise self.answer
        return FakeMessage(self.answer)


class FakeSDK:
    def __init__(self, answer, made, **kwargs):
        self.kwargs, self.calls, self.closed = kwargs, [], False
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))
        self.answer = answer
        made.append(self)

    def stream(self, **params):
        self.calls.append(params)
        return FakeStream(self.answer)

    def close(self):
        self.closed = True


class CredentialsFile:
    def __init__(self, text, mode=0o600):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'anthropic.env'
        self.path.write_text(text)
        os.chmod(self.path, mode)


class LiveTests(SimpleTestCase):
    def setUp(self):
        self.file = CredentialsFile(f'ANTHROPIC_API_KEY={KEY}\nANTHROPIC_WORKSPACE_ID=wrkspc_synthetic\n')
        self.addCleanup(self.file.folder.cleanup)
        self.made = []

    def send(self, answer, req=None):
        coder = client.LiveCoder(credentials_file=str(self.file.path), read_timeout=900,
                                 sdk=lambda **kwargs: FakeSDK(answer, self.made, **kwargs))
        return coder.send(req or request())

    def test_a_finished_message_succeeds_and_the_call_is_the_specified_one(self):
        message = f.message([f.text_block('done')])
        outcome = self.send(message)
        self.assertEqual((outcome.state, outcome.sent, outcome.http_status, outcome.failure_kind),
                         ('succeeded', True, 200, ''))
        self.assertEqual(outcome.response_bytes, client.canonical(message))
        self.assertEqual((outcome.returned_model, outcome.response_id, outcome.request_id),
                         ('claude-fable-5-2', message['id'], 'req_stream'))
        self.assertEqual(outcome.usage, message['usage'])
        self.assertFalse(outcome.fallback)
        sdk = self.made[0]
        self.assertEqual(sdk.kwargs['api_key'], KEY)
        self.assertEqual(sdk.kwargs['max_retries'], 0)
        self.assertEqual(sdk.kwargs['base_url'], 'https://api.anthropic.com')
        self.assertEqual(sdk.kwargs['default_headers'], {'anthropic-workspace-id': 'wrkspc_synthetic'})
        timeout = sdk.kwargs['timeout']
        self.assertIsInstance(timeout, anthropic.Timeout)
        self.assertEqual((timeout.connect, timeout.read, timeout.write, timeout.pool), (20, 900, 120, 20))
        call = sdk.calls[0]
        self.assertEqual((call['model'], call['max_tokens'], call['betas'], call['fallbacks'], call['output_config']),
                         ('claude-fable-5-2', 96_000, ['server-side-fallback-2026-07-01'], 'default',
                          {'effort': 'max'}))
        self.assertEqual(call['messages'][0]['content'][0]['source']['data'], 'JVBERi0xLjc=')  # the bytes are sent
        self.assertTrue(sdk.closed)
        self.assertNotIn(KEY, repr(outcome))

    def test_a_refusal_after_the_fallbacks_is_declined(self):
        message = f.message([f.text_block('partial')], stop='refusal', stop_details={'type': 'refusal',
                                                                                      'category': 'cyber'})
        outcome = self.send(message)
        self.assertEqual((outcome.state, outcome.failure_kind, outcome.error_type), ('failed', DECLINED, 'cyber'))

    def test_max_tokens_is_too_long(self):
        outcome = self.send(f.message([f.text_block('cut')], stop='max_tokens'))
        self.assertEqual((outcome.state, outcome.failure_kind), ('failed', TOO_LONG))

    def test_a_message_served_by_a_fallback_is_recorded_and_read_as_any_other(self):
        used = f.usage(iterations=[{'type': 'message', 'input_tokens': 100, 'output_tokens': 0},
                                   {'type': 'fallback_message', 'model': 'claude-opus-4-8', 'input_tokens': 100,
                                    'output_tokens': 50}])
        outcome = self.send(f.message([f.text_block('served')], used=used, model='claude-opus-4-8'))
        self.assertEqual((outcome.state, outcome.fallback, outcome.returned_model),
                         ('succeeded', True, 'claude-opus-4-8'))

    def test_a_400_refusal_of_the_document_is_document(self):
        outcome = self.send(status_error(anthropic.BadRequestError, 400, 'invalid_request_error',
                                         'The PDF is encrypted.'))
        self.assertEqual((outcome.state, outcome.sent, outcome.failure_kind, outcome.http_status, outcome.hold),
                         ('failed', True, DOCUMENT, 400, ''))
        self.assertEqual(outcome.error, 'invalid_request_error (HTTP 400): The PDF is encrypted.')
        self.assertEqual(json.loads(outcome.response_bytes)['error']['type'], 'invalid_request_error')
        self.assertEqual(outcome.request_id, 'req_error')

    def test_account_refusals_set_holds_and_busy_answers_do_not(self):
        cases = [(anthropic.AuthenticationError, 401, 'authentication_error', HOLD, 'auth'),
                 (anthropic.PaymentRequiredError, 402, 'billing_error', HOLD, 'quota'),
                 (anthropic.PermissionDeniedError, 403, 'permission_error', HOLD, 'permission'),
                 (anthropic.NotFoundError, 404, 'not_found_error', HOLD, 'refused'),
                 (anthropic.RateLimitError, 429, 'billing_error', HOLD, 'quota'),
                 (anthropic.RateLimitError, 429, None, HOLD, 'quota'),
                 (anthropic.RateLimitError, 429, 'rate_limit_error', BUSY, ''),
                 (anthropic.APIStatusError, 529, 'overloaded_error', BUSY, ''),
                 (anthropic.APIStatusError, 200, 'overloaded_error', BUSY, ''),  # an error event in the stream
                 (anthropic.InternalServerError, 500, 'api_error', FAILED, ''),
                 (anthropic.APIStatusError, 413, 'request_too_large', DOCUMENT, '')]
        for cls, status, error_type, kind, hold in cases:
            with self.subTest(status=status, error_type=error_type):
                outcome = self.send(status_error(cls, status, error_type))
                self.assertEqual((outcome.state, outcome.failure_kind, outcome.hold, outcome.http_status),
                                 ('failed', kind, hold, status))

    def test_a_timeout_a_lost_connection_or_anything_after_the_start_is_unknown(self):
        for error in (anthropic.APITimeoutError(request=object()), anthropic.APIConnectionError(request=object()),
                      RuntimeError('synthetic')):
            with self.subTest(error=type(error).__name__):
                outcome = self.send(error)
                self.assertEqual((outcome.state, outcome.sent, outcome.failure_kind), ('unknown', True, UNKNOWN))
                self.assertIn(type(error).__name__, outcome.error)

    def test_a_stream_that_ended_before_its_message_did_is_unknown(self):
        partial = f.message([f.text_block('half')], stop=None)
        outcome = self.send(partial)
        self.assertEqual((outcome.state, outcome.failure_kind), ('unknown', UNKNOWN))
        self.assertEqual(outcome.response_bytes, client.canonical(partial))

    def test_an_unusable_credentials_file_sends_nothing_and_names_no_value(self):
        for text, mode in ((f'ANTHROPIC_API_KEY={KEY}\n', 0o644), (f'OTHER={KEY}\n', 0o600), ('', 0o600)):
            with self.subTest(mode=oct(mode)):
                self.file = CredentialsFile(text, mode)
                self.addCleanup(self.file.folder.cleanup)
                outcome = self.send(f.message([f.text_block('x')]))
                self.assertEqual((outcome.state, outcome.sent, outcome.failure_kind), ('not_sent', False, UNAVAILABLE))
                self.assertNotIn(KEY, outcome.error)
                self.assertNotIn(str(self.file.path), outcome.error)
        self.assertEqual(self.made, [])

    def test_no_workspace_header_without_a_workspace(self):
        self.file = CredentialsFile(f'export ANTHROPIC_API_KEY="{KEY}"  # synthetic\n')
        self.addCleanup(self.file.folder.cleanup)
        self.send(f.message([f.text_block('x')]))
        self.assertIsNone(self.made[0].kwargs['default_headers'])


class RequestTests(SimpleTestCase):
    def test_the_stored_request_replaces_the_data_and_names_the_request(self):
        req = request()
        self.assertEqual(req.params['messages'][0]['content'][0]['source']['data'], 'JVBERi0xLjc=')
        self.assertEqual(req.stored['messages'][0]['content'][0]['source']['data']['$original_bytes'], 8)
        self.assertNotIn('JVBERi0xLjc=', json.dumps(req.stored))
        self.assertEqual(req.sha256, request().sha256)  # deterministic
        self.assertNotEqual(req.sha256, request('high').sha256)
        self.assertEqual(req.input_bytes, 8 + len(prompts.READER_SYSTEM.encode()) + len(b'Code this document.'))
        self.assertEqual(req.stored['messages'][0]['content'][1], {'type': 'text', 'text': 'Code this document.'})


class ReplayTests(SimpleTestCase):
    def test_a_recorded_message_is_read_by_the_request_sha256_and_nothing_is_sent(self):
        req = request()
        with tempfile.TemporaryDirectory() as folder:
            message = f.message([f.text_block('replayed')])
            (Path(folder) / f'{req.sha256}.json').write_text(json.dumps(message))
            outcome = client.ReplayCoder(folder).send(req)
            missing = client.ReplayCoder(folder).send(request('low'))
        self.assertEqual((outcome.state, outcome.sent, outcome.message), ('succeeded', False, message))
        self.assertEqual((missing.state, missing.failure_kind), ('not_sent', UNAVAILABLE))
        self.assertEqual(client.ReplayCoder.endpoint, '')

    def test_the_mode_picks_the_coder(self):
        with override_settings(CODING_MODE='disabled'):
            self.assertIsNone(client.coder())
        with override_settings(CODING_MODE='live'):
            self.assertIsInstance(client.coder(), client.LiveCoder)
        with override_settings(CODING_MODE='replay', CODING_REPLAY_DIR='/nonexistent'):
            self.assertIsInstance(client.coder(), client.ReplayCoder)


class CredentialsTests(SimpleTestCase):
    def load(self, text, mode=0o600):
        file = CredentialsFile(text, mode)
        self.addCleanup(file.folder.cleanup)
        return credentials.load(str(file.path))

    def test_the_key_and_an_optional_workspace(self):
        found = self.load(f"ANTHROPIC_API_KEY='{KEY}'\n# comment\n\nANTHROPIC_WORKSPACE_ID=wrkspc_1\n")
        self.assertEqual((found.api_key, found.workspace_id), (KEY, 'wrkspc_1'))
        self.assertNotIn(KEY, repr(found))
        self.assertNotIn(KEY, str(found))

    def test_refused_files_and_lines(self):
        cases = [(f'ANTHROPIC_API_KEY={KEY}\n', 0o640), ('ANTHROPIC_WORKSPACE_ID=w\n', 0o600),
                 (f'ANTHROPIC_API_KEY={KEY}\nANTHROPIC_API_KEY={KEY}\n', 0o600),
                 (f'ANTHROPIC_API_KEY={KEY}\nOPENAI_API_KEY=x\n', 0o600), ('ANTHROPIC_API_KEY="a\\nb"\n', 0o600),
                 ('ANTHROPIC_API_KEY=has space\n', 0o600), (f'ANTHROPIC_API_KEY={KEY}\nANTHROPIC_WORKSPACE_ID=-x\n',
                                                            0o600),
                 ('not an assignment\n', 0o600), ('ANTHROPIC_API_KEY=' + 'k' * 33_000 + '\n', 0o600)]
        for text, mode in cases:
            with self.subTest(text=text[:40], mode=oct(mode)), self.assertRaises(credentials.CredentialsError) as caught:
                self.load(text, mode)
            self.assertNotIn(KEY, str(caught.exception))

    def test_a_symlink_a_missing_file_and_no_setting_are_refused(self):
        file = CredentialsFile(f'ANTHROPIC_API_KEY={KEY}\n')
        self.addCleanup(file.folder.cleanup)
        link = Path(file.folder.name) / 'link.env'
        link.symlink_to(file.path)
        for path in (str(link), str(Path(file.folder.name) / 'missing.env'), ''):
            with self.subTest(path=path), self.assertRaises(credentials.CredentialsError):
                credentials.load(path)
