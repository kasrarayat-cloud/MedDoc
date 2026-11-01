"""Astra: OpenAI GPT-6 Astra on the Responses API (HARNESS.md 1, 3, 4, 8).

The request is POST https://api.openai.com/v1/responses with the key as a Bearer token, X-Client-Request-Id (the
caller's id for this attempt, which OpenAI logs) and OpenAI-Project when one is configured. Its body asks gpt-6-astra
for one JSON object in the reading schema (strict structured output), at medium reasoning effort, within 16,000 output
tokens, with store false. The revision's framed text is the only input; for a PDF its original goes before it as an
input_file (base64 data URL, filename original.pdf). Nothing else is sent (I5).

An answer is read only when its status is completed, it names gpt-6-astra as the model that answered (or a dated
snapshot of it, gpt-6-astra-YYYY-MM-DD: never another model; I6), and its message carries output text and no refusal.
An incomplete response is refused as truncated. Its output text is then read as the reading (reading.py).
"""
from __future__ import annotations

import base64
import copy
import re
from time import monotonic
from typing import Callable, Optional

import requests

from studio.participants import http, prompt, reading
from studio.participants.credentials import CredentialsError, load_openai_credentials
from studio.providers.base import ProviderUnavailable, valid_deadline, verified_body
from studio.types import PageSpan, ParticipantReading, ProviderRequest, RawExchange

NAME = 'astra'
ADAPTER_VERSION = 'openai-responses@cptstudio-harness-1'
MODEL = 'gpt-6-astra'
ENDPOINT = 'https://api.openai.com/v1/responses'
EFFORT = 'medium'
MAX_OUTPUT_TOKENS = 16_000
FILENAME = 'original.pdf'
FILE_PREFIX = 'data:application/pdf;base64,'
DEFAULT_MAX_REQUEST_BYTES = 24 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
VENDOR = http.Vendor(label='OpenAI', request_id_header='x-request-id')
BODY_KEYS = frozenset({'model', 'instructions', 'input', 'text', 'reasoning', 'max_output_tokens', 'store'})
ORIGINAL_PATH = ('input', 0, 'content', 0, 'file_data')  # where a PDF's file data goes
_CLIENT_REQUEST_ID = re.compile(r'[\x21-\x7e]{1,512}')  # OpenAI: ASCII, at most 512 characters
_SNAPSHOT = re.compile(re.escape(MODEL) + r'-[0-9]{4}-[0-9]{2}-[0-9]{2}')


def request_body(framed: str, original: Optional[dict]) -> dict:
    """The exact body, with a PDF's original as its placeholder (http.placeholder) until send time."""
    content = []
    if original is not None:
        content.append({'type': 'input_file', 'filename': FILENAME, 'file_data': original})
    content.append({'type': 'input_text', 'text': framed})
    return {
        'model': MODEL,
        'instructions': prompt.INSTRUCTIONS,
        'input': [{'role': 'user', 'content': content}],
        'text': {'format': {'type': 'json_schema', 'name': prompt.SCHEMA_NAME, 'schema': copy.deepcopy(prompt.SCHEMA),
                            'strict': True}},
        'reasoning': {'effort': EFFORT},
        'max_output_tokens': MAX_OUTPUT_TOKENS,
        'store': False,
    }


def answered_by_astra(model) -> bool:
    return isinstance(model, str) and (model == MODEL or _SNAPSHOT.fullmatch(model) is not None)


def _file_data(data: bytes) -> str:
    return FILE_PREFIX + base64.b64encode(data).decode('ascii')


class AstraParticipant:
    name = NAME
    adapter_version = ADAPTER_VERSION
    mode = 'live'
    requested_model = MODEL
    endpoint = ENDPOINT

    def __init__(self, credentials_path, *, connect_timeout: float = 10, read_timeout: float = 300,
                 max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
                 session_factory: Optional[Callable[[], requests.Session]] = None):
        for label, seconds in (('connect_timeout', connect_timeout), ('read_timeout', read_timeout)):
            if not valid_deadline(seconds):
                raise ValueError(f'{label} must be a positive number of seconds.')
        for label, limit in (('max_request_bytes', max_request_bytes), ('max_response_bytes', max_response_bytes)):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'{label} must be a positive integer.')
        self.credentials_path = credentials_path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.session_factory = session_factory or http.default_session

    def build_request(self, text: str, pages: tuple[PageSpan, ...], kind: str,
                      original: Optional[dict]) -> ProviderRequest:
        return http.build_request(NAME, ADAPTER_VERSION, text, pages, kind, original, max_bytes=self.max_request_bytes,
                                  make_body=request_body, file_prefix=FILE_PREFIX)

    def read(self, request: ProviderRequest, response_bytes: bytes) -> ParticipantReading:
        return read_response(request, response_bytes)

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
             original_bytes: Optional[bytes]) -> RawExchange:
        if not valid_deadline(deadline_s):
            return http.not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        deadline = monotonic() + deadline_s
        try:
            verified_body(request, self, self.max_request_bytes)
            http.check_shape(request.body, MODEL, BODY_KEYS)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc))
        if not isinstance(client_request_id, str) or not _CLIENT_REQUEST_ID.fullmatch(client_request_id):
            return http.not_sent('The client request id must be 1 to 512 visible ASCII characters; nothing was sent.',
                                 MODEL)
        try:
            data = http.sendable(http.expand_original(request.body, ORIGINAL_PATH, original_bytes, _file_data),
                                 self.max_request_bytes)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc), MODEL)
        try:
            credentials = load_openai_credentials(self.credentials_path)
        except CredentialsError as exc:
            return http.not_sent(f'{exc} No request was sent.', MODEL)
        headers = {'Authorization': f'Bearer {credentials.api_key}', 'Content-Type': 'application/json',
                   'X-Client-Request-Id': client_request_id}
        if credentials.project is not None:
            headers['OpenAI-Project'] = credentials.project
        return http.post(VENDOR, self.session_factory, ENDPOINT, data, headers, deadline=deadline,
                         connect_timeout=self.connect_timeout, read_timeout=self.read_timeout,
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


def read_response(request: ProviderRequest, response_bytes) -> ParticipantReading:
    """The reading in a stored Responses API answer. Read only as the adapter version that recorded it; refused whole
    when the response is not completed, another model answered, the model refused, or the reading breaks its schema or
    bounds - and then none of it, its codes included, is read."""
    def refused(reason: str, returned: str = '') -> ParticipantReading:
        return reading.refusal(NAME, ADAPTER_VERSION, MODEL, returned, reason)

    if (request.provider, request.adapter_version) != (NAME, ADAPTER_VERSION):
        return refused(f'it was recorded for {request.provider!r} with adapter {request.adapter_version!r}, '
                       f'not {NAME!r} with {ADAPTER_VERSION!r}')
    if not isinstance(response_bytes, (bytes, bytearray, memoryview)):
        return refused('there are no response bytes')
    try:
        envelope = reading.strict_json(response_bytes)
    except reading.JSONRefused as exc:
        return refused(f'the response {exc}')
    if not isinstance(envelope, dict):
        return refused('the response is not a JSON object')
    model = envelope.get('model')
    returned = reading.recorded_model(model)
    if not answered_by_astra(model):  # I6: checked before anything else the response says
        named = f'model {reading.named(model)}' if isinstance(model, str) else 'no model'
        return refused(f'it names {named} as the model that answered, not {MODEL}', returned)
    status = envelope.get('status')
    if status == 'incomplete':
        return refused(_incomplete(envelope.get('incomplete_details')), returned)
    if status != 'completed':
        return refused(f'its status is {reading.quoted(status, 40)}, not completed', returned)
    output = envelope.get('output')
    if not isinstance(output, list):
        return refused('the response has no output list', returned)
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue  # reasoning items carry no answer
        if item.get('status') == 'incomplete':
            return refused('the response was cut off at the output limit', returned)
        content = item.get('content')
        if not isinstance(content, list):
            return refused('a message in the response has no content list', returned)
        for part in content:
            kind = part.get('type') if isinstance(part, dict) else None
            if kind == 'refusal':
                return refused(f'the model refused: {reading.quoted(part.get("refusal"))}', returned)
            if kind == 'output_text':
                if not isinstance(part.get('text'), str):
                    return refused('an output text part of the response has no text', returned)
                texts.append(part['text'])
    if not texts:
        return refused('the response carries no output text', returned)
    contexts = request.contexts
    source = contexts[0] if isinstance(contexts, (tuple, list)) and contexts else None
    return reading.read(''.join(texts), source, provider=NAME, adapter_version=ADAPTER_VERSION,
                        requested_model=MODEL, returned_model=returned)


def _incomplete(details) -> str:
    reason = details.get('reason') if isinstance(details, dict) else None
    if reason == 'max_output_tokens':
        return 'the response was cut off at the output limit'
    if isinstance(reason, str) and reason.strip():
        return f'the response is incomplete ({reading.quoted(reason, 60)})'
    return 'the response is incomplete'
