"""Astra: OpenAI GPT-6 Astra on the Responses API (HARNESS.md 1, 3, 4, 8, 11).

The request is POST https://api.openai.com/v1/responses with the key as a Bearer token, X-Client-Request-Id (the
caller's id for this attempt, which OpenAI logs) and OpenAI-Project when one is configured. Its body asks gpt-6-astra
for one JSON object in the reading schema (strict structured output), at medium reasoning effort, within 16,000 output
tokens, with store false. The revision's framed text is the only input; for a PDF its original goes before it as an
input_file (base64 data URL, filename original.pdf). Nothing else is sent (I5).

harness@2 (HARNESS.md 11.2): the body also offers CPT Studio's two reference tools as strict functions (tool_choice
auto) and asks for the reasoning items' encrypted content, because with store false nothing is kept at OpenAI between
exchanges. A run is a tool loop (send_loop, loop.py): an answer asks for tools when it is a completed answer from
gpt-6-astra whose output holds function_call items (call_id, name, arguments as a JSON string), and the next request's
input is the previous input, then every output item of that answer exactly as returned (reasoning items included), then
one function_call_output per call carrying the result as a JSON string. Each exchange's X-Client-Request-Id is its own:
the caller's id on the first exchange and '<id>-<turn>' on each later one. The peer review (build_peer_request) is the
same shape with PEER_INSTRUCTIONS, the peer schema (named prompt.PEER_SCHEMA_NAME) and two text inputs, the framed text
and prompt.peer_document; no original file is attached.

An answer is read only when its status is completed, it names gpt-6-astra as the model that answered (or a dated
snapshot of it, gpt-6-astra-YYYY-MM-DD: never another model; I6), and its message carries output text and no refusal.
An incomplete response is refused as truncated, and a harness@2 answer that still asks for tool calls is not a final
answer. Its output text is then read as the reading (reading.py) or the peer review (peer.py).

ADAPTER_VERSION_1 names the harness@1 request shape (no tools). Its stored runs are still read, exactly as before; a
request of that version is never sent.
"""
from __future__ import annotations

import base64
import copy
import re
from time import monotonic
from typing import Callable, Optional

import requests

from studio.participants import http, loop, peer, prompt, reading
from studio.participants.credentials import CredentialsError, load_openai_credentials
from studio.providers.base import ProviderUnavailable, valid_deadline, verified_body
from studio.types import PageSpan, ParticipantReading, PeerReview, ProviderRequest, RawExchange

NAME = 'astra'
ADAPTER_VERSION = 'openai-responses@cptstudio-harness-2'  # @2: tools in the request, a run is a tool loop
ADAPTER_VERSION_1 = 'openai-responses@cptstudio-harness-1'  # stored harness@1 runs: read as before, never sent
READ_VERSIONS = (ADAPTER_VERSION, ADAPTER_VERSION_1)
MODEL = 'gpt-6-astra'
ENDPOINT = 'https://api.openai.com/v1/responses'
EFFORT = 'medium'
MAX_OUTPUT_TOKENS = 16_000
FILENAME = 'original.pdf'
FILE_PREFIX = 'data:application/pdf;base64,'
DEFAULT_MAX_REQUEST_BYTES = 24 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
VENDOR = http.Vendor(label='OpenAI', request_id_header='x-request-id')
BODY_KEYS = frozenset({'model', 'instructions', 'input', 'text', 'reasoning', 'max_output_tokens', 'store', 'tools',
                       'tool_choice', 'include'})
ORIGINAL_PATH = ('input', 0, 'content', 0, 'file_data')  # where a PDF's file data goes
CLIENT_REQUEST_ID_CHARS = 512  # OpenAI: ASCII, at most 512 characters
_CLIENT_REQUEST_ID = re.compile(r'[\x21-\x7e]{1,512}')
_SNAPSHOT = re.compile(re.escape(MODEL) + r'-[0-9]{4}-[0-9]{2}-[0-9]{2}')


def tools() -> list:
    """CPT Studio's reference tools (prompt.TOOLS) as strict Responses API functions."""
    return [{'type': 'function', 'name': tool['name'], 'description': tool['description'],
             'parameters': copy.deepcopy(tool['parameters']), 'strict': True} for tool in prompt.TOOLS]


def _body(instructions: str, content: list, schema_name: str, schema: dict) -> dict:
    return {
        'model': MODEL,
        'instructions': instructions,
        'input': [{'role': 'user', 'content': content}],
        'text': {'format': {'type': 'json_schema', 'name': schema_name, 'schema': copy.deepcopy(schema),
                            'strict': True}},
        'reasoning': {'effort': EFFORT},
        'max_output_tokens': MAX_OUTPUT_TOKENS,
        'store': False,
        'tools': tools(),
        'tool_choice': 'auto',
        'include': ['reasoning.encrypted_content'],
    }


def request_body(framed: str, original: Optional[dict]) -> dict:
    """The exact first-reading body, with a PDF's original as its placeholder (http.placeholder) until send time."""
    content = []
    if original is not None:
        content.append({'type': 'input_file', 'filename': FILENAME, 'file_data': original})
    content.append({'type': 'input_text', 'text': framed})
    return _body(prompt.INSTRUCTIONS, content, prompt.SCHEMA_NAME, prompt.SCHEMA)


def peer_request_body(framed: str, document: str) -> dict:
    """The exact peer-review body: the framed text and the peer document, and no original file (HARNESS.md 11.1)."""
    return _body(prompt.PEER_INSTRUCTIONS, [{'type': 'input_text', 'text': framed},
                                            {'type': 'input_text', 'text': document}],
                 prompt.PEER_SCHEMA_NAME, prompt.PEER_SCHEMA)


def turn_client_request_id(client_request_id: str, turn: int) -> str:
    """The X-Client-Request-Id of exchange ``turn`` of a loop: the caller's id on the first, '<id>-<turn>' after, so
    every request's id is its own (OpenAI asks for one per request)."""
    return client_request_id if turn == 1 else f'{client_request_id}-{turn}'


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
        """Exactly one exchange (HARNESS.md 8). A harness@2 run is a tool loop (send_loop): an answer to this one
        exchange that asks for tool calls is not a final answer, and its reading is refused."""
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
        return self._post(request.body, deadline=deadline, read_timeout=self.read_timeout,
                          client_request_id=client_request_id, original_bytes=original_bytes)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
                  original_bytes: Optional[bytes], execute_tool) -> loop.LoopOutcome:
        """The run's tool loop (loop.run): at most max_exchanges exchanges within the loop deadline (``deadline_s``,
        never more than loop_deadline), each read within exchange_read_timeout clamped to the time left."""
        longest = CLIENT_REQUEST_ID_CHARS - len(f'-{self.max_exchanges}')
        client_error = ''
        if not isinstance(client_request_id, str) or not _CLIENT_REQUEST_ID.fullmatch(client_request_id) \
                or len(client_request_id) > longest:
            client_error = (f'The client request id must be 1 to {longest} visible ASCII characters (each later '
                            'exchange appends its turn number); nothing was sent.')

        def post(turn: int, body: dict, deadline: float) -> RawExchange:
            return self._post(body, deadline=deadline, read_timeout=self.exchange_read_timeout,
                              client_request_id=turn_client_request_id(client_request_id, turn),
                              original_bytes=original_bytes)

        return loop.run(self, request, post=post, parse_turn=parse_turn, follow_up=follow_up,
                        execute_tool=execute_tool, deadline_s=deadline_s, longest_s=self.loop_deadline,
                        max_exchanges=self.max_exchanges, max_tool_result_bytes=self.max_tool_result_bytes,
                        max_request_bytes=self.max_request_bytes, body_keys=BODY_KEYS, client_error=client_error)

    def _post(self, body: dict, *, deadline: float, read_timeout: float, client_request_id: str,
              original_bytes) -> RawExchange:
        """One exchange of a verified stored body: the original re-verified and expanded, the credentials read, one
        POST under http.post's discipline."""
        try:
            expanded = http.expand_original(body, ORIGINAL_PATH, original_bytes, _file_data)
            data = http.sendable(expanded, self.max_request_bytes, with_original=expanded is not body)
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
                         connect_timeout=self.connect_timeout, read_timeout=read_timeout,
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


# --- the tool loop's vendor half (loop.py) ------------------------------------------------------------------------------

def parse_turn(response_bytes) -> loop.Turn:
    """What one answer asks for. Tool calls only when it is a completed answer from gpt-6-astra whose output holds
    function_call items and no refusal or cut-off message; anything else is final, for the reader to read or refuse
    (another model's or a refused answer is never acted on; I6)."""
    try:
        envelope = reading.strict_json(response_bytes)
    except reading.JSONRefused:
        return loop.FINAL
    if (not isinstance(envelope, dict) or not answered_by_astra(envelope.get('model'))
            or envelope.get('status') != 'completed'):
        return loop.FINAL
    output = envelope.get('output')
    if not isinstance(output, list) or not all(isinstance(item, dict) for item in output):
        return loop.FINAL
    calls = []
    for item in output:
        if item.get('type') == 'message' and _stops(item):
            return loop.FINAL
        if item.get('type') == 'function_call':
            calls.append(_call(item))
    return loop.Turn(calls=tuple(calls), items=tuple(output)) if calls else loop.FINAL


def _stops(message: dict) -> bool:
    """A message that was cut off or carries a refusal: the answer is final, whatever else it asks for."""
    content = message.get('content')
    return message.get('status') == 'incomplete' or (isinstance(content, list) and any(
        isinstance(part, dict) and part.get('type') == 'refusal' for part in content))


def _call(item: dict) -> loop.Call:
    arguments = item.get('arguments')
    if not isinstance(arguments, str):
        return loop.Call(call_id=item.get('call_id'), name=item.get('name'), arguments=arguments,
                         arguments_error=loop.NOT_AN_OBJECT)
    try:
        parsed = reading.strict_json_text(arguments)
    except reading.JSONRefused:
        return loop.Call(call_id=item.get('call_id'), name=item.get('name'), arguments=arguments,
                         arguments_error=loop.NOT_JSON)
    return loop.Call(call_id=item.get('call_id'), name=item.get('name'), arguments=parsed,
                     arguments_error='' if isinstance(parsed, dict) else loop.NOT_AN_OBJECT)


def follow_up(body: dict, turn: loop.Turn, outputs: tuple) -> dict:
    """The next exchange's body: this one's, its input extended - never edited - by every output item of the answer
    exactly as returned (reasoning items with their encrypted content included) and one function_call_output per
    call, in the order asked, each carrying its result as a JSON string."""
    following = dict(body)
    following['input'] = [*body['input'], *turn.items,
                          *({'type': 'function_call_output', 'call_id': call_id, 'output': output}
                            for call_id, output in outputs)]
    return following


# --- reading a stored answer -------------------------------------------------------------------------------------------

def read_response(request: ProviderRequest, response_bytes, refs_retrieved=frozenset()) -> ParticipantReading:
    """The reading in a stored Responses API answer. Read only as the adapter version that recorded it (a harness@1
    run exactly as before); refused whole when the response is not completed, another model answered, the model
    refused, a harness@2 answer still asks for tool calls, or the reading breaks its schema or bounds - and then none
    of it, its codes included, is read. ``refs_retrieved``: the refs this run's own tool calls returned (references_used
    is checked against them)."""
    refs = reading.retrieved_refs(refs_retrieved)
    version = request.adapter_version
    if request.provider != NAME or version not in READ_VERSIONS:
        return reading.refusal(NAME, ADAPTER_VERSION, MODEL, '',
                               f'it was recorded for {request.provider!r} with adapter {version!r}, '
                               f'not {NAME!r} with {ADAPTER_VERSION!r}')
    text, returned, why = _answer(response_bytes, tools=version == ADAPTER_VERSION)
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
    text, returned, why = _answer(response_bytes, tools=True)
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
            or body['instructions'] != prompt.PEER_INSTRUCTIONS:
        return None
    if body['text'] != {'format': {'type': 'json_schema', 'name': prompt.PEER_SCHEMA_NAME,
                                   'schema': prompt.PEER_SCHEMA, 'strict': True}}:
        return None
    (message,) = body['input']
    content = message['content']
    if message.get('role') != 'user' or len(content) != 2 or [part.get('type') for part in content] != [
            'input_text', 'input_text']:
        return None
    return content[1]['text']


def _answer(response_bytes, *, tools: bool) -> tuple[str, str, str]:
    """(output text, returned model, '') of a usable answer, or ('', returned model, why it is refused). The checks and
    their order are harness@1's; ``tools`` (harness@2) also refuses an answer that still asks for tool calls."""
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
    if not answered_by_astra(model):  # I6: checked before anything else the response says
        named = f'model {reading.named(model)}' if isinstance(model, str) else 'no model'
        return '', returned, f'it names {named} as the model that answered, not {MODEL}'
    status = envelope.get('status')
    if status == 'incomplete':
        return '', returned, _incomplete(envelope.get('incomplete_details'))
    if status != 'completed':
        return '', returned, f'its status is {reading.quoted(status, 40)}, not completed'
    output = envelope.get('output')
    if not isinstance(output, list):
        return '', returned, 'the response has no output list'
    texts, asks = [], False
    for item in output:
        if isinstance(item, dict) and item.get('type') == 'function_call':
            asks = True
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue  # reasoning items and tool calls carry no answer
        if item.get('status') == 'incomplete':
            return '', returned, 'the response was cut off at the output limit'
        content = item.get('content')
        if not isinstance(content, list):
            return '', returned, 'a message in the response has no content list'
        for part in content:
            kind = part.get('type') if isinstance(part, dict) else None
            if kind == 'refusal':
                return '', returned, f'the model refused: {reading.quoted(part.get("refusal"))}'
            if kind == 'output_text':
                if not isinstance(part.get('text'), str):
                    return '', returned, 'an output text part of the response has no text'
                texts.append(part['text'])
    if tools and asks:
        return '', returned, 'the response still asks for tool calls, so it is not a final answer'
    if not texts:
        return '', returned, 'the response carries no output text'
    return ''.join(texts), returned, ''


def _incomplete(details) -> str:
    reason = details.get('reason') if isinstance(details, dict) else None
    if reason == 'max_output_tokens':
        return 'the response was cut off at the output limit'
    if isinstance(reason, str) and reason.strip():
        return f'the response is incomplete ({reading.quoted(reason, 60)})'
    return 'the response is incomplete'
