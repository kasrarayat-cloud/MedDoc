"""Fable: Anthropic Claude Fable 5.1 on the Messages API (HARNESS.md 1, 3, 4, 8).

The request is POST https://api.anthropic.com/v1/messages with x-api-key, anthropic-version 2026-10-21 and
anthropic-workspace-id when one is configured. Its body asks claude-fable-5-1 for one JSON object in the reading schema
(output_config.format), at medium effort, within 16,000 output tokens. The revision's framed text is the only user
content; for a PDF its original goes before it as a base64 document block. Nothing else is sent (I5).

Never sent, because the API or the owner forbids them: thinking (always on for this model; a value is a 400),
temperature, top_p and top_k (400 on this API version), fallbacks (the owner forbids silent model substitution; I6) and
any beta header.

An answer is read only when it is a message from claude-fable-5-1 itself (I6), no server-side fallback took part
(a fallback content block, or a fallback entry in usage.iterations), and it stopped at end_turn. A max_tokens stop is
refused as truncated; a refusal stop is refused with its stop_details category. Its text blocks, joined in order, are
the reading (reading.py); thinking blocks carry no answer and are not read.
"""
from __future__ import annotations

import base64
import copy
from time import monotonic
from typing import Callable, Optional

import requests

from studio.participants import http, prompt, reading
from studio.participants.credentials import CredentialsError, load_anthropic_credentials
from studio.providers.base import ProviderUnavailable, valid_deadline, verified_body
from studio.types import PageSpan, ParticipantReading, ProviderRequest, RawExchange

NAME = 'fable'
ADAPTER_VERSION = 'anthropic-messages@cptstudio-harness-1'
MODEL = 'claude-fable-5-1'
ENDPOINT = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2026-10-21'
EFFORT = 'medium'
MAX_TOKENS = 16_000
FILE_PREFIX = ''  # a document block's data is the bare base64
DEFAULT_MAX_REQUEST_BYTES = 24 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
VENDOR = http.Vendor(label='Anthropic', request_id_header='request-id')
BODY_KEYS = frozenset({'model', 'max_tokens', 'system', 'messages', 'output_config'})
ORIGINAL_PATH = ('messages', 0, 'content', 0, 'source', 'data')  # where a PDF's base64 data goes


def request_body(framed: str, original: Optional[dict]) -> dict:
    """The exact body, with a PDF's original as its placeholder (http.placeholder) until send time."""
    content = []
    if original is not None:
        content.append({'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                       'data': original}})
    content.append({'type': 'text', 'text': framed})
    return {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'system': prompt.INSTRUCTIONS,
        'messages': [{'role': 'user', 'content': content}],
        'output_config': {'format': {'type': 'json_schema', 'schema': copy.deepcopy(prompt.SCHEMA)}, 'effort': EFFORT},
    }


def _document_data(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


class FableParticipant:
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
        """``client_request_id`` is not sent: Anthropic documents no such header (the vendor's request-id is kept)."""
        if not valid_deadline(deadline_s):
            return http.not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        deadline = monotonic() + deadline_s
        try:
            verified_body(request, self, self.max_request_bytes)
            http.check_shape(request.body, MODEL, BODY_KEYS)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc))
        try:
            data = http.sendable(http.expand_original(request.body, ORIGINAL_PATH, original_bytes, _document_data),
                                 self.max_request_bytes)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc), MODEL)
        try:
            credentials = load_anthropic_credentials(self.credentials_path)
        except CredentialsError as exc:
            return http.not_sent(f'{exc} No request was sent.', MODEL)
        headers = {'x-api-key': credentials.api_key, 'anthropic-version': API_VERSION,
                   'content-type': 'application/json'}
        if credentials.workspace_id is not None:
            headers['anthropic-workspace-id'] = credentials.workspace_id
        return http.post(VENDOR, self.session_factory, ENDPOINT, data, headers, deadline=deadline,
                         connect_timeout=self.connect_timeout, read_timeout=self.read_timeout,
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


def read_response(request: ProviderRequest, response_bytes) -> ParticipantReading:
    """The reading in a stored Messages API answer. Read only as the adapter version that recorded it; refused whole
    when another model or a fallback answered, the answer was cut off or refused, or the reading breaks its schema or
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
    if model != MODEL:  # I6: checked before anything else the response says
        named = f'model {reading.named(model)}' if isinstance(model, str) else 'no model'
        return refused(f'it names {named} as the model that answered, not {MODEL}', returned)
    if envelope.get('type') != 'message':
        return refused('the response is not a message', returned)
    content = envelope.get('content')
    if not isinstance(content, list):
        return refused('the response has no content list', returned)
    if _fell_back(content, envelope.get('usage')):
        return refused('a server-side fallback took part in the answer, which this adapter never asks for', returned)
    stop = envelope.get('stop_reason')
    if stop == 'max_tokens':
        return refused('the response was cut off at the output limit', returned)
    if stop == 'refusal':
        details = envelope.get('stop_details')
        category = details.get('category') if isinstance(details, dict) else None
        named = f'category {reading.quoted(category, 60)}' if isinstance(category, str) and category.strip() \
            else 'no category was given'
        return refused(f'the model refused ({named})', returned)
    if stop != 'end_turn':
        return refused(f'it stopped for {reading.quoted(stop, 40) if isinstance(stop, str) else "no stated reason"}, '
                       'not at the end of its turn', returned)
    texts = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            if not isinstance(block.get('text'), str):
                return refused('a text block of the response has no text', returned)
            texts.append(block['text'])
    if not texts:
        return refused('the response carries no text block', returned)
    contexts = request.contexts
    source = contexts[0] if isinstance(contexts, (tuple, list)) and contexts else None
    return reading.read(''.join(texts), source, provider=NAME, adapter_version=ADAPTER_VERSION,
                        requested_model=MODEL, returned_model=returned)


def _fell_back(content: list, usage) -> bool:
    """A fallback content block marks a switch to another model; a fallback entry in usage.iterations says one served
    the turn (it is the served-by signal: a sticky turn carries no block)."""
    if any(isinstance(block, dict) and block.get('type') == 'fallback' for block in content):
        return True
    iterations = usage.get('iterations') if isinstance(usage, dict) else None
    return isinstance(iterations, list) and any(
        isinstance(entry, dict) and isinstance(entry.get('type'), str) and entry['type'].startswith('fallback')
        for entry in iterations)
