"""Offline support shared by the participant adapter suites (HARNESS.md 3, 4, 8). It defines no tests.

Every participant test runs behind a guard that fails on requests.Session construction, DNS lookups and socket
connects (a positive control in test_participants_send proves the guard trips), and every send uses a fake session:
injected, or returned by a patched requests.Session where the real session factory is under test. All data is
synthetic (tests/fixtures/participants/README.md) and every credential value is fake.

The tool-loop answers (astra_tool_call, fable_tool_use) are built in code in the vendors' documented shapes: a Responses
API answer whose output holds a reasoning item with its encrypted content and function_call items (call_id, name,
arguments as a JSON string); a Messages API answer that stopped for tool_use, holding a thinking block with its
signature and tool_use blocks (id, name, input). Their ids carry "synthetic" and none is vendor output.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase
from requests.structures import CaseInsensitiveDict

from studio.types import PageSpan

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'participants'
FIXTURE_SHA256 = {
    'colonoscopy.note.txt': '9436025908574d0e062d54bc450521b378f013a55f4530fab1457a234b9c3d67',
    'astra-colonoscopy.response.json': 'f544bc0a2b76299c4f9b367d028411f3cc2b710c75daa17d43e59f7451a781e1',
    'fable-colonoscopy.response.json': 'c8884bd5da425fed5186c934ddecb8fd58b5e48115874e3e4ff384c0653ce34c',
}
NOTE = (FIXTURES / 'colonoscopy.note.txt').read_bytes().decode('utf-8')
PAGE_BREAK = 343  # page 2 of the note starts here (README)
PAGES = (PageSpan(page=1, start=0, end=PAGE_BREAK), PageSpan(page=2, start=PAGE_BREAK, end=len(NOTE)))
# Synthetic bytes standing in for a PDF original: the adapters never parse it, they verify and encode it.
PDF = b'%PDF-1.7\n% synthetic test bytes, not a real document\n' + bytes(range(256)) * 3
ORIGINAL = {'sha256': hashlib.sha256(PDF).hexdigest(), 'bytes': len(PDF)}

OPENAI_KEY = 'sk-proj-synthetic-NOT-A-REAL-KEY-0001'
OPENAI_PROJECT = 'proj_synthetic0001'
ANTHROPIC_KEY = 'sk-ant-api03-synthetic-NOT-A-REAL-KEY-0001'
ANTHROPIC_WORKSPACE = 'wrkspc_synthetic0001'
SECRETS = (OPENAI_KEY, ANTHROPIC_KEY)
CLIENT_REQUEST_ID = 'cptstudio-run-00000000-0000-4000-8000-000000000001'


class NetworkBlocked(AssertionError):
    """The guard tripped: a participant test reached the network layer."""


class OfflineMixin:
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
            raise NetworkBlocked(f'{name} was reached; participant tests must stay offline.')
        return block

    def tearDown(self):
        self.assertEqual(self.network_attempts, [], 'A test reached the network layer.')
        super().tearDown()


class OfflineTestCase(OfflineMixin, SimpleTestCase):
    pass


class OfflineDatabaseTestCase(OfflineMixin, TestCase):
    pass


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
    """Plays scripted steps (a FakeResponse, an exception to raise, or a callable producing either) and records every
    POST. It also takes what default_session() sets on a real session, so it can stand in for requests.Session()."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []
        self.responses = []
        self.mounted = {}
        self.closed = False

    def mount(self, prefix, adapter):
        self.mounted[prefix] = adapter

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


def write_file(path: Path, content, mode=0o600) -> Path:
    data = content.encode() if isinstance(content, str) else content
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
    os.chmod(path, mode)
    return path


def dotenv(**values) -> str:
    return ''.join(f'{key}={value}\n' for key, value in values.items() if value is not None)


def openai_env(**overrides) -> str:
    return dotenv(**{'OPENAI_API_KEY': OPENAI_KEY, **overrides})


def anthropic_env(**overrides) -> str:
    return dotenv(**{'ANTHROPIC_API_KEY': ANTHROPIC_KEY, **overrides})


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def astra_envelope() -> dict:
    return json.loads(fixture_bytes('astra-colonoscopy.response.json'))


def fable_envelope() -> dict:
    return json.loads(fixture_bytes('fable-colonoscopy.response.json'))


def fixture_reading() -> dict:
    """The reading both fixtures carry, parsed."""
    return json.loads(astra_envelope()['output'][1]['content'][0]['text'])


def astra_with(answer, **fields) -> bytes:
    """The Astra fixture with its output text replaced by ``answer`` (a dict is encoded) and top-level fields set."""
    envelope = astra_envelope()
    envelope['output'][1]['content'][0]['text'] = answer if isinstance(answer, str) else json.dumps(answer)
    envelope.update(fields)
    return json.dumps(envelope).encode()


def fable_with(answer, **fields) -> bytes:
    """The Fable fixture with its text block replaced by ``answer`` (a dict is encoded) and top-level fields set."""
    envelope = fable_envelope()
    envelope['content'][1]['text'] = answer if isinstance(answer, str) else json.dumps(answer)
    envelope.update(fields)
    return json.dumps(envelope).encode()


def changed(reading: dict, **fields) -> dict:
    """A deep copy of ``reading`` with top-level fields replaced."""
    result = copy.deepcopy(reading)
    result.update(fields)
    return result


def service(index=1, **fields) -> dict:
    item = {'id': f's{index}', 'family': 'colonoscopy', 'status': 'performed', 'description': '', 'anatomy': '',
            'extent': '', 'technique': '', 'lesions': [], 'provider_role': '', 'evidence': []}
    item.update(fields)
    return item


def code(value='45385', **fields) -> dict:
    item = {'code': value, 'modifiers': [], 'units': 1, 'service_ids': ['s1'], 'basis': '', 'evidence': [],
            'confidence': 'high'}
    item.update(fields)
    return item


def empty_reading(**fields) -> dict:
    reading = {'date_of_service': {'value': '', 'evidence': []}, 'services': [], 'codes': [], 'not_coded': [],
               'clarifications': [], 'extraction_issues': [], 'references_used': []}
    reading.update(fields)
    return reading


# --- the tool loop (HARNESS.md 11.2) ---------------------------------------------------------------------------------

ASTRA_TOOL_USAGE = {'input_tokens': 2500, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 120,
                    'output_tokens_details': {'reasoning_tokens': 64}, 'total_tokens': 2620}
FABLE_TOOL_USAGE = {'input_tokens': 2700, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0,
                    'output_tokens': 140, 'output_tokens_details': {'thinking_tokens': 80}, 'service_tier': 'standard'}
FACTS_ARGUMENTS = {'codes': ['45385'], 'date_of_service': '2026-10-21'}
PASSAGES_ARGUMENTS = {'topic': 'ncci_endoscopy_rules', 'codes': ['45385', '45380']}


def astra_tool_call(*calls, number=1, model='gpt-6-astra', usage=None, reasoning=None, envelope=None) -> bytes:
    """A completed Responses API answer from ``model`` that asks for function calls: a reasoning item carrying its
    encrypted content, then one function_call per (call_id, name, arguments); arguments that are not a str are
    JSON-encoded. ``envelope`` sets top-level fields."""
    output = [reasoning if reasoning is not None else
              {'type': 'reasoning', 'id': f'rs_synthetic_tool_{number:04d}', 'summary': [],
               'encrypted_content': f'gAAAAB-synthetic-encrypted-reasoning-{number:04d}=='}]
    for index, (call_id, name, arguments) in enumerate(calls, start=1):
        output.append({'type': 'function_call', 'id': f'fc_synthetic_{number:02d}_{index:02d}', 'call_id': call_id,
                       'name': name, 'arguments': arguments if isinstance(arguments, str) else json.dumps(arguments),
                       'status': 'completed'})
    body = {'id': f'resp_synthetic_tool_{number:04d}', 'object': 'response', 'created_at': 1793000000 + number,
            'status': 'completed', 'error': None, 'incomplete_details': None, 'model': model, 'output': output,
            'usage': copy.deepcopy(ASTRA_TOOL_USAGE if usage is None else usage)}
    body.update(envelope or {})
    return json.dumps(body).encode()


def fable_tool_use(*calls, number=1, model='claude-fable-5-1', usage=None, thinking=None, envelope=None) -> bytes:
    """A Messages API answer from ``model`` that stopped for tool_use: a thinking block with its signature, then one
    tool_use block per (id, name, input). ``envelope`` sets top-level fields."""
    content = [thinking if thinking is not None else
               {'type': 'thinking', 'thinking': f'Synthetic reasoning {number}.',
                'signature': f'synthetic-signature-{number:04d}'}]
    for call_id, name, arguments in calls:
        content.append({'type': 'tool_use', 'id': call_id, 'name': name, 'input': arguments})
    body = {'id': f'msg_synthetic_tool_{number:04d}', 'type': 'message', 'role': 'assistant', 'model': model,
            'content': content, 'stop_reason': 'tool_use', 'stop_sequence': None, 'stop_details': None,
            'usage': copy.deepcopy(FABLE_TOOL_USAGE if usage is None else usage)}
    body.update(envelope or {})
    return json.dumps(body).encode()


class FakeExecutor:
    """The caller's tool executor: records every call and answers from ``answers`` ({tool: (result, refs)} or a
    callable taking (name, arguments)), or a default result naming the tool and its codes, with one ref per code."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def __call__(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        answer = self.answers.get(name) if isinstance(self.answers, dict) else self.answers
        if callable(answer):
            return answer(name, arguments)
        if answer is not None:
            return answer
        refs = [f'fact:cms-pfs-rvu26d:{item}:status' for item in arguments.get('codes', [])]
        return {'tool': name, 'facts': [{'ref': ref, 'value': 'A'} for ref in refs], 'release': 'RVU26D'}, refs


def canonical(value) -> str:
    """A tool result as the loop sends it: canonical JSON."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
