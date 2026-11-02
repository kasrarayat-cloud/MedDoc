"""Fable: Anthropic Claude Fable 5.1 on the Messages API (HARNESS.md 1, 3, 4, 8, 11).

The request is POST https://api.anthropic.com/v1/messages with x-api-key, anthropic-version 2026-10-21 and
anthropic-workspace-id when one is configured. Its body asks claude-fable-5-1 for one JSON object in the reading schema
(output_config.format), at medium effort, within 16,000 output tokens. The revision's framed text is the only user
content; for a PDF its original goes before it as a base64 document block. Nothing else is sent (I5).

Never sent, because the API or the owner forbids them: thinking (always on for this model; a value is a 400),
temperature, top_p and top_k (400 on this API version), fallbacks (the owner forbids silent model substitution; I6) and
any beta header.

harness@2 (HARNESS.md 11.2): the body also offers CPT Studio's two reference tools (strict, tool_choice auto; a forced
tool_choice is a 400 on this model). A run is a tool loop (send_loop, loop.py): an answer asks for tools when it is a
message from claude-fable-5-1 itself, with no fallback, that stopped for tool_use with tool_use blocks (id, name, input).
The next request's messages are the previous messages - never edited - then an assistant turn whose content is that
answer's content array exactly as returned (thinking blocks with their signatures unchanged), then a user turn of one
tool_result per call carrying the result as a JSON string. The peer review (build_peer_request) is the same shape with
PEER_INSTRUCTIONS as the system prompt, the peer schema and two text blocks, the framed text and prompt.peer_document; no
original file is attached.

An answer is read only when it is a message from claude-fable-5-1 itself (I6), no server-side fallback took part
(a fallback content block, or a fallback entry in usage.iterations), and it stopped at end_turn. A max_tokens stop is
refused as truncated; a refusal stop is refused with its stop_details category; a tool_use stop is not a final answer.
Its text blocks, joined in order, are the reading (reading.py) or the peer review (peer.py); thinking blocks carry no
answer and are not read.

ADAPTER_VERSION_1 names the harness@1 request shape (no tools). Its stored runs are still read, exactly as before; a
request of that version is never sent.
"""
from __future__ import annotations

import base64
import copy
from time import monotonic
from typing import Callable, Optional

import requests

from studio.participants import http, loop, peer, prompt, reading
from studio.participants.credentials import CredentialsError, load_anthropic_credentials
from studio.providers.base import ProviderUnavailable, valid_deadline, verified_body
from studio.types import PageSpan, ParticipantReading, PeerReview, ProviderRequest, RawExchange

NAME = 'fable'
ADAPTER_VERSION = 'anthropic-messages@cptstudio-harness-2'  # @2: tools in the request, a run is a tool loop
ADAPTER_VERSION_1 = 'anthropic-messages@cptstudio-harness-1'  # stored harness@1 runs: read as before, never sent
READ_VERSIONS = (ADAPTER_VERSION, ADAPTER_VERSION_1)
MODEL = 'claude-fable-5-1'
ENDPOINT = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2026-10-21'
EFFORT = 'medium'
MAX_TOKENS = 16_000
FILE_PREFIX = ''  # a document block's data is the bare base64
DEFAULT_MAX_REQUEST_BYTES = 24 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
VENDOR = http.Vendor(label='Anthropic', request_id_header='request-id')
BODY_KEYS = frozenset({'model', 'max_tokens', 'system', 'messages', 'output_config', 'tools', 'tool_choice'})
ORIGINAL_PATH = ('messages', 0, 'content', 0, 'source', 'data')  # where a PDF's base64 data goes


def tools() -> list:
    """CPT Studio's reference tools (prompt.TOOLS) as strict Messages API tools."""
    return [{'name': tool['name'], 'description': tool['description'],
             'input_schema': copy.deepcopy(tool['parameters']), 'strict': True} for tool in prompt.TOOLS]


def _body(system: str, content: list, schema: dict) -> dict:
    return {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'system': system,
        'messages': [{'role': 'user', 'content': content}],
        'output_config': {'format': {'type': 'json_schema', 'schema': copy.deepcopy(schema)}, 'effort': EFFORT},
        'tools': tools(),
        'tool_choice': {'type': 'auto'},
    }


def request_body(framed: str, original: Optional[dict]) -> dict:
    """The exact first-reading body, with a PDF's original as its placeholder (http.placeholder) until send time."""
    content = []
    if original is not None:
        content.append({'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                       'data': original}})
    content.append({'type': 'text', 'text': framed})
    return _body(prompt.INSTRUCTIONS, content, prompt.SCHEMA)


def peer_request_body(framed: str, document: str) -> dict:
    """The exact peer-review body: the framed text and the peer document, and no original file (HARNESS.md 11.1)."""
    return _body(prompt.PEER_INSTRUCTIONS, [{'type': 'text', 'text': framed}, {'type': 'text', 'text': document}],
                 prompt.PEER_SCHEMA)


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
                 session_factory: Optional[Callable[[], requests.Session]] = None, max_exchanges: int = 4,
                 exchange_read_timeout: float = 240, loop_deadline: float = 540,
                 max_tool_result_bytes: int = 256 * 1024):
        for label, seconds in (('connect_timeout', connect_timeout), ('read_timeout', read_timeout),
                               ('exchange_read_timeout', exchange_read_timeout), ('loop_deadline', loop_deadline)):
            if not valid_deadline(seconds):
                raise ValueError(f'{label} must be a positive number of seconds.')
        for label, limit in (('max_request_bytes', max_request_bytes), ('max_response_bytes', max_response_bytes),
                             ('max_exchanges', max_exchanges), ('max_tool_result_bytes', max_tool_result_bytes)):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'{label} must be a positive integer.')
        self.credentials_path = credentials_path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.session_factory = session_factory or http.default_session
        self.max_exchanges = max_exchanges
        self.exchange_read_timeout = exchange_read_timeout
        self.loop_deadline = loop_deadline
        self.max_tool_result_bytes = max_tool_result_bytes

    def build_request(self, text: str, pages: tuple[PageSpan, ...], kind: str,
                      original: Optional[dict]) -> ProviderRequest:
        return http.build_request(NAME, ADAPTER_VERSION, text, pages, kind, original, max_bytes=self.max_request_bytes,
                                  make_body=request_body, file_prefix=FILE_PREFIX)

    def build_peer_request(self, text: str, pages: tuple[PageSpan, ...], kind: str, own: ParticipantReading,
                           peers: dict, cpt_studio: dict, frozen) -> ProviderRequest:
        return peer.build_request(NAME, ADAPTER_VERSION, text, pages, kind, own, peers, cpt_studio, frozen,
                                  max_bytes=self.max_request_bytes, make_body=peer_request_body)

    def read(self, request: ProviderRequest, response_bytes: bytes, refs_retrieved=frozenset()) -> ParticipantReading:
        return read_response(request, response_bytes, refs_retrieved)

    def read_peer(self, request: ProviderRequest, response_bytes: bytes, refs_retrieved=frozenset()) -> PeerReview:
        return read_peer(request, response_bytes, refs_retrieved)

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
             original_bytes: Optional[bytes]) -> RawExchange:
        """Exactly one exchange (HARNESS.md 8). ``client_request_id`` is not sent: Anthropic documents no such header
        (the vendor's request-id is kept). A harness@2 run is a tool loop (send_loop): an answer to this one exchange
        that stops for tool_use is not a final answer, and its reading is refused."""
        if not valid_deadline(deadline_s):
            return http.not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        deadline = monotonic() + deadline_s
        try:
            verified_body(request, self, self.max_request_bytes)
            http.check_shape(request.body, MODEL, BODY_KEYS)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc))
        return self._post(request.body, deadline=deadline, read_timeout=self.read_timeout,
                          original_bytes=original_bytes)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
                  original_bytes: Optional[bytes], execute_tool) -> loop.LoopOutcome:
        """The run's tool loop (loop.run): at most max_exchanges exchanges within the loop deadline (``deadline_s``,
        never more than loop_deadline), each read within exchange_read_timeout clamped to the time left.
        ``client_request_id`` is not sent (see send)."""
        def post(turn: int, body: dict, deadline: float) -> RawExchange:
            return self._post(body, deadline=deadline, read_timeout=self.exchange_read_timeout,
                              original_bytes=original_bytes)

        return loop.run(self, request, post=post, parse_turn=parse_turn, follow_up=follow_up,
                        execute_tool=execute_tool, deadline_s=deadline_s, longest_s=self.loop_deadline,
                        max_exchanges=self.max_exchanges, max_tool_result_bytes=self.max_tool_result_bytes,
                        max_request_bytes=self.max_request_bytes, body_keys=BODY_KEYS)

    def _post(self, body: dict, *, deadline: float, read_timeout: float, original_bytes) -> RawExchange:
        """One exchange of a verified stored body: the original re-verified and expanded, the credentials read, one
        POST under http.post's discipline."""
        try:
            expanded = http.expand_original(body, ORIGINAL_PATH, original_bytes, _document_data)
            data = http.sendable(expanded, self.max_request_bytes, with_original=expanded is not body)
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
                         connect_timeout=self.connect_timeout, read_timeout=read_timeout,
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


# --- the tool loop's vendor half (loop.py) ------------------------------------------------------------------------------

def parse_turn(response_bytes) -> loop.Turn:
    """What one answer asks for. Tool calls only when it is a message from claude-fable-5-1 itself, with no fallback,
    that stopped for tool_use and holds tool_use blocks; anything else is final, for the reader to read or refuse
    (another model's, a fallback's or a refused answer is never acted on; I6)."""
    try:
        envelope = reading.strict_json(response_bytes)
    except reading.JSONRefused:
        return loop.FINAL
    if not isinstance(envelope, dict) or envelope.get('model') != MODEL or envelope.get('type') != 'message':
        return loop.FINAL
    content = envelope.get('content')
    if not isinstance(content, list) or not all(isinstance(block, dict) for block in content):
        return loop.FINAL
    if _fell_back(content, envelope.get('usage')) or envelope.get('stop_reason') != 'tool_use':
        return loop.FINAL
    calls = tuple(loop.Call(call_id=block.get('id'), name=block.get('name'), arguments=block.get('input'),
                            arguments_error='' if isinstance(block.get('input'), dict) else loop.NOT_AN_OBJECT)
                  for block in content if block.get('type') == 'tool_use')
    return loop.Turn(calls=calls, items=tuple(content)) if calls else loop.FINAL


def follow_up(body: dict, turn: loop.Turn, outputs: tuple) -> dict:
    """The next exchange's body: this one's, its messages extended - never edited - by an assistant turn holding the
    answer's content array exactly as returned (thinking blocks with their signatures unchanged) and a user turn of one
    tool_result per call, in the order asked, each carrying its result as a JSON string."""
    following = dict(body)
    following['messages'] = [*body['messages'], {'role': 'assistant', 'content': list(turn.items)},
                             {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': call_id,
                                                           'content': output} for call_id, output in outputs]}]
    return following


# --- reading a stored answer -------------------------------------------------------------------------------------------

def read_response(request: ProviderRequest, response_bytes, refs_retrieved=frozenset()) -> ParticipantReading:
    """The reading in a stored Messages API answer. Read only as the adapter version that recorded it (a harness@1 run
    exactly as before); refused whole when another model or a fallback answered, the answer was cut off, refused or
    stopped for tool_use, or the reading breaks its schema or bounds - and then none of it, its codes included, is read.
    ``refs_retrieved``: the refs this run's own tool calls returned (references_used is checked against them)."""
    refs = reading.retrieved_refs(refs_retrieved)
    version = request.adapter_version
    if request.provider != NAME or version not in READ_VERSIONS:
        return reading.refusal(NAME, ADAPTER_VERSION, MODEL, '',
                               f'it was recorded for {request.provider!r} with adapter {version!r}, '
                               f'not {NAME!r} with {ADAPTER_VERSION!r}')
    text, returned, why = _answer(response_bytes)
    if why:
        return reading.refusal(NAME, version, MODEL, returned, why)
    return reading.read(text, _source(request), provider=NAME, adapter_version=version, requested_model=MODEL,
                        returned_model=returned, refs_retrieved=refs)


def read_peer(request: ProviderRequest, response_bytes, refs_retrieved=frozenset()) -> PeerReview:
    """The peer review in a stored answer to a peer-review request (peer.py): refused whole for every reason a reading
    is, and when the request is not a peer review this adapter version builds. The frozen inputs and the question ids
    are read from the request's own body."""
    refs = reading.retrieved_refs(refs_retrieved)
    if (request.provider, request.adapter_version) != (NAME, ADAPTER_VERSION):
        return peer.refusal(NAME, ADAPTER_VERSION, MODEL, '',
                            f'it was recorded for {request.provider!r} with adapter {request.adapter_version!r}, '
                            f'not {NAME!r} with {ADAPTER_VERSION!r}')
    listed = peer.request_inputs(request, _peer_document)
    if isinstance(listed, str):
        return peer.refusal(NAME, ADAPTER_VERSION, MODEL, '', listed)
    question_ids, frozen = listed
    text, returned, why = _answer(response_bytes)
    if why:
        return peer.refusal(NAME, ADAPTER_VERSION, MODEL, returned, why, frozen)
    return peer.read(text, _source(request), provider=NAME, adapter_version=ADAPTER_VERSION, requested_model=MODEL,
                     returned_model=returned, question_ids=question_ids, frozen_inputs=frozen, refs_retrieved=refs)


def _source(request: ProviderRequest):
    contexts = request.contexts
    return contexts[0] if isinstance(contexts, (tuple, list)) and contexts else None


def _peer_document(body) -> Optional[str]:
    """The peer document of a peer-review body this adapter builds, or None for any other body."""
    if not isinstance(body, dict) or set(body) != BODY_KEYS or body['model'] != MODEL \
            or body['system'] != prompt.PEER_INSTRUCTIONS:
        return None
    if body['output_config'] != {'format': {'type': 'json_schema', 'schema': prompt.PEER_SCHEMA}, 'effort': EFFORT}:
        return None
    (message,) = body['messages']
    content = message['content']
    if message.get('role') != 'user' or len(content) != 2 or [block.get('type') for block in content] != [
            'text', 'text']:
        return None
    return content[1]['text']


def _answer(response_bytes) -> tuple[str, str, str]:
    """(text, returned model, '') of a usable answer, or ('', returned model, why it is refused); harness@1's checks in
    harness@1's order (a tool_use stop is refused as any stop other than end_turn is)."""
    if not isinstance(response_bytes, (bytes, bytearray, memoryview)):
        return '', '', 'there are no response bytes'
    try:
        envelope = reading.strict_json(response_bytes)
    except reading.JSONRefused as exc:
        return '', '', f'the response {exc}'
    if not isinstance(envelope, dict):
        return '', '', 'the response is not a JSON object'
    model = envelope.get('model')
    returned = reading.recorded_model(model)
    if model != MODEL:  # I6: checked before anything else the response says
        named = f'model {reading.named(model)}' if isinstance(model, str) else 'no model'
        return '', returned, f'it names {named} as the model that answered, not {MODEL}'
    if envelope.get('type') != 'message':
        return '', returned, 'the response is not a message'
    content = envelope.get('content')
    if not isinstance(content, list):
        return '', returned, 'the response has no content list'
    if _fell_back(content, envelope.get('usage')):
        return '', returned, 'a server-side fallback took part in the answer, which this adapter never asks for'
    stop = envelope.get('stop_reason')
    if stop == 'max_tokens':
        return '', returned, 'the response was cut off at the output limit'
    if stop == 'refusal':
        details = envelope.get('stop_details')
        category = details.get('category') if isinstance(details, dict) else None
        named = f'category {reading.quoted(category, 60)}' if isinstance(category, str) and category.strip() \
            else 'no category was given'
        return '', returned, f'the model refused ({named})'
    if stop != 'end_turn':
        return '', returned, (f'it stopped for {reading.quoted(stop, 40) if isinstance(stop, str) else "no stated reason"}, '
                              'not at the end of its turn')
    texts = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            if not isinstance(block.get('text'), str):
                return '', returned, 'a text block of the response has no text'
            texts.append(block['text'])
    if not texts:
        return '', returned, 'the response carries no text block'
    return ''.join(texts), returned, ''


def _fell_back(content: list, usage) -> bool:
    """A fallback content block marks a switch to another model; a fallback entry in usage.iterations says one served
    the turn (it is the served-by signal: a sticky turn carries no block)."""
    if any(isinstance(block, dict) and block.get('type') == 'fallback' for block in content):
        return True
    iterations = usage.get('iterations') if isinstance(usage, dict) else None
    return isinstance(iterations, list) and any(
        isinstance(entry, dict) and isinstance(entry.get('type'), str) and entry['type'].startswith('fallback')
        for entry in iterations)
