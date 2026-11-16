"""The interpreter's connector for Claude Fable 5.2 on the Anthropic Messages API, for both passes (docs/gemini-migration/
AMENDMENT-2.md section 1, as its refutation revised it, AMEND2-REFUTATIONS.md CONN-1 to CONN-7; DECISIONS D275, D278):
how a request of either pass is built, sent once as a stream, read into one answer, and classified.

WHERE AND WHY HERE (1.1). This kept module sits beside adapter.py, outside contract/ and engine/, because its stream
reader holds event-name constants the new packages' word-list rule refuses. It imports participants.http,
participants.reading, participants.credentials and participants.loop, providers.base, the contract builders and
readers, studio.types and adapter.py's shared pieces (NotBuilt and its effects, AppraisalRequest, _same_request,
_document, _unframed, the one-exchange helpers and the Classification dataclass: one copy each); adapter.py, the
dormant Gemini adapter, is not edited. Nothing here imports studio.gi, studio.validation or studio.candidates (D17),
reads Django settings at import, or touches the database.

THE REQUEST (1.2). ADAPTER_VERSION_V3 (anthropic-messages@cptstudio-interp-1) has two request kinds, named by the
ProviderRun.purpose its run records: EXTRACTION, pass 1 - the body contract/extract_prompt.request_parts_fable builds
from the framed revision (the user turn is the framed document alone, D1), with its one system block cached (7.2) -
and APPRAISAL, pass 2 - the body contract/appraise_prompt.request_parts_fable builds from 2.4's user turn, with
output_config.format a json_schema over appraise_schema.LOCAL_SCHEMA. Both bodies have exactly BODY_KEYS: model
claude-fable-5-2, max_tokens MAX_TOKENS, stream true, output_config.effort high, system and messages. Never sent:
thinking (always on for this model; omitting it is adaptive), temperature, top_p, top_k, an assistant prefill, tools,
tool_choice, stop_sequences, metadata, fallbacks and any anthropic-beta header (D275: no fallback model), a member
value, a filename, a participant's output (D1) or the PDF original (D12). A body is sent only when it is exactly one
of the two kinds as the builders write it (body_kind), so nothing rides along. The headers are set at send time and
never stored: x-api-key (the existing Anthropic credential, read at send time by participants.credentials, never
printed), anthropic-version API_VERSION (part of what ADAPTER_VERSION_V3 names, 8.4 [R:replay-R8]),
content-type application/json, and anthropic-workspace-id when the credential file names one.

THE SEND (1.3). One exchange per run (InterpreterF.send_loop: participants.loop.run with max_exchanges 1, no tool
executor called, a member's Stop asked once right before the send, a continuation refused), one participants.http.post
under its discipline (no retry, no redirect, no proxies, a watched socket, the deadline checked per 64 KiB chunk, a
capped read). VENDOR names the stream's end test (``complete``): a 200 whose stream did not reach message_stop or an
error event, or whose read stopped early (a connection reset or a broken chunk, the deadline, the byte cap), is
recorded 'unknown' with the bytes read so far and no usage - never read, never priced as a whole answer
[R:connector-CONN-6][R:connector-CONN-2][R:connector-CONN-3].

THE STREAM (1.4). ``assemble`` reads the raw SSE bytes into one answer, purely: strict UTF-8 lines, events separated by
one empty line, comments skipped, one optional event: line and exactly one data: line per event (strict JSON, its type
the event's name); pings skipped anywhere, an unknown event type skipped and counted; message_start first and once (or
an error event), naming the model; text, thinking and redacted_thinking blocks only, each opened at the next index,
fed only its own deltas and closed; message_delta once after every block closed (stop reason, the refusal's category as
one word, the usage merged over message_start's); message_stop last; an error event ends the stream wherever it comes.
``describe`` gives the usage only for a stream that reached message_delta and ended with message_stop: a cut, early or
error-ended stream records none [R:connector-CONN-3].

THE ENVELOPE (1.4, 1.6). ``answer_text`` reads an answer only as ADAPTER_VERSION_V3 recorded it, only when the stream
names exactly claude-fable-5-2 (checked first of everything it says, D13; D275: no fallback model, so a fallback block or
a fallback usage iteration is refused too), when it stopped at end_turn and carries a text block. Pass 1's text must
be one JSON object, alone or alone in one fence (participants.reading.sole_object: JSON mode constrains nothing); pass
2's goes to contract/appraise_read as it stands (structured outputs constrain it). Each refusal is contract/
extract_read's at stage 'envelope', in CPT Studio's words: it repeats nothing the model wrote and names no provider or
model (D22).

CLASSIFICATION (1.5). ``classify`` keeps adapter.classify's contract and precedence with Anthropic's vocabulary: for a
200 stream, a model signal first (HOLD model, whatever follows), then an error event (its type decides, so an
error-first stream is never a model hold [R:connector-CONN-4]), then a stream that does not assemble (FAILED), then the
stop reason (end_turn ANSWERED, max_tokens TOO_LONG, refusal HOLD declined, anything else FAILED); for a non-200 body,
a hold its error type names, then the hold its status names, then a rate limit (only rate_limit_error: any other 429
holds as quota, D39's fail-closed reading), then the failures. interpretation.holds records the hold and decides
whether it is request-bound [R:connector-CONN-1].
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from string import Formatter
from time import monotonic
from types import MappingProxyType
from typing import Any, Callable, Optional, Union

import requests

from studio import interpretation
from studio.interpretation import adapter
from studio.interpretation.contract import appraise_prompt, appraise_read, claims, extract_prompt, extract_read, segment
from studio.participants import http, loop, reading
from studio.participants.credentials import CredentialsError, load_anthropic_credentials
from studio.providers.base import ProviderUnavailable, canonical_body, valid_deadline, verified_body
from studio.types import PageSpan, ProviderRequest, RawExchange

# --- the names (1.1) -----------------------------------------------------------------------------------------------

NAME = interpretation.PROVIDER_V3  # ProviderRun.provider: 'anthropic'
MODEL = interpretation.MODEL_V3  # 'claude-fable-5-2' (D275, D13: an answer is read only when Anthropic reports it)
ADAPTER_VERSION_V3 = interpretation.ADAPTER_VERSION_V3  # 'anthropic-messages@cptstudio-interp-1': both request kinds
READ_VERSIONS = (ADAPTER_VERSION_V3,)  # the adapter versions whose stored answers this module reads
READ_MODELS: Mapping[str, tuple[str, ...]] = MappingProxyType({ADAPTER_VERSION_V3: (MODEL,)})  # 1.6
ENDPOINT = 'https://api.anthropic.com/v1/messages'
# Its own constant and part of what ADAPTER_VERSION_V3 names (8.4 [R:replay-R8]): a test pins it to
# interpretation.API_VERSION_V3, never to the Fable participant's, so a changed anthropic-version is a new adapter version.
API_VERSION = '2026-10-21'
EFFORT = 'high'  # D275
MAX_TOKENS = 128000  # both passes (section 3; D278: sized for INTERPRET_MAX_CHARS' 20,000 characters)
BODY_KEYS = frozenset({'model', 'max_tokens', 'stream', 'output_config', 'system', 'messages'})
EXTRACTION = interpretation.PURPOSE  # 'interpretation': pass 1, its run's ProviderRun.purpose
APPRAISAL = interpretation.APPRAISAL_PURPOSE  # 'appraisal': pass 2
PURPOSES = (EXTRACTION, APPRAISAL)
KEY_HEADER, VERSION_HEADER, WORKSPACE_HEADER = 'x-api-key', 'anthropic-version', 'anthropic-workspace-id'
CONNECT_TIMEOUT_SECONDS = 10
# 1.12: 128,000 output tokens at 100 tokens per second plus 40 s; the read timeout bounds each wait for a byte and never
# cuts before the deadline. The configured interpreters read settings.INTERPRETER_* and APPRAISER_* (both 1,320 s).
READ_TIMEOUT_SECONDS = 1320
SEND_DEADLINE_SECONDS = 1320
APPRAISAL_READ_TIMEOUT_SECONDS = 1320
APPRAISAL_SEND_DEADLINE_SECONDS = 1320
DEFAULT_MAX_REQUEST_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # 1.12: settings.INTERPRETER_MAX_RESPONSE_BYTES, the raw stream's cap

# The shared pieces of adapter.py, one copy each (1.2): the NotBuilt refusal and its effects, the appraisal request.
NotBuilt = adapter.NotBuilt
AppraisalRequest = adapter.AppraisalRequest
Classification = adapter.Classification
Check = adapter.Check
UNBUILT, REFUSED, NOT_BUILT_EFFECTS = adapter.UNBUILT, adapter.REFUSED, adapter.NOT_BUILT_EFFECTS
NOT_BUILT = adapter.NOT_BUILT
UNPINNED_V3 = ('An instruction, a schema or a table of this version no longer matches its pin, so no request of this '
               'version can be checked; nothing was sent.')

# --- classification's words (1.5) --------------------------------------------------------------------------------------

ANSWERED, FAILED, TOO_LONG, HOLD = adapter.ANSWERED, adapter.FAILED, adapter.TOO_LONG, adapter.HOLD  # the same kinds
KINDS = (ANSWERED, FAILED, TOO_LONG, HOLD)
# InterpreterHold.reason (studio.models.InterpreterHold's constants; holds.REASONS holds them with the dormant adapter's)
AUTH, PERMISSION, QUOTA, MODEL_HOLD = adapter.AUTH, adapter.PERMISSION, adapter.QUOTA, adapter.MODEL_HOLD
REFUSED_HOLD, DECLINED = 'refused', 'declined'
HOLD_REASONS = (AUTH, PERMISSION, QUOTA, MODEL_HOLD, REFUSED_HOLD, DECLINED)
# Anthropic's error types (an error body's or an error event's error.type) and the hold each sets; any other type,
# rate_limit_error and request_too_large among them, fails the attempt only (1.5's table)
HOLD_TYPES: Mapping[str, str] = MappingProxyType({
    'authentication_error': AUTH, 'billing_error': QUOTA, 'permission_error': PERMISSION,
    'not_found_error': PERMISSION, 'invalid_request_error': REFUSED_HOLD})
RATE_LIMIT_TYPE, TOO_LARGE_TYPE = 'rate_limit_error', 'request_too_large'
# 1.5: a status sets a hold only when the body names none (401, 402, 403, 404; any other 4xx but 413 and 429 is the
# 'refused' hold; a 429 that names no rate_limit_error is the quota hold, D39)
HOLD_STATUSES: Mapping[int, str] = MappingProxyType({401: AUTH, 402: QUOTA, 403: PERMISSION, 404: PERMISSION})
END_TURN, CUT_OFF, DECLINE = 'end_turn', 'max_tokens', 'refusal'  # the stop reasons that are not a failure
# The table's word for each row (1.5's second column), for an operator and the harness: what the effect means here.
ANSWERED_WORD, TOO_LONG_WORD, HOLD_WORD = 'answered', 'too long', 'hold'
REFUSED_WORD, RETRY_LATER_WORD, UNKNOWN_WORD = 'refused', 'retry later', 'unknown'
WORDS = (ANSWERED_WORD, TOO_LONG_WORD, HOLD_WORD, REFUSED_WORD, RETRY_LATER_WORD, UNKNOWN_WORD)
_TYPE = re.compile(r'[a-z][a-z_]{0,39}')  # an error type or a refusal category kept as InterpreterHold.vendor_status
_MESSAGE_ID = re.compile(r'[\x21-\x7e]{1,140}')  # fits ProviderRun.response_id

# --- the stream's grammar (1.4) ----------------------------------------------------------------------------------------

MESSAGE_START, MESSAGE_DELTA, MESSAGE_STOP = 'message_start', 'message_delta', 'message_stop'
BLOCK_START, BLOCK_DELTA, BLOCK_STOP = 'content_block_start', 'content_block_delta', 'content_block_stop'
ERROR, PING = 'error', 'ping'
COUNTED = frozenset({MESSAGE_START, MESSAGE_DELTA, MESSAGE_STOP, BLOCK_START, BLOCK_DELTA, BLOCK_STOP, ERROR})
TEXT_BLOCK, THINKING_BLOCK, REDACTED_BLOCK, FALLBACK_BLOCK = 'text', 'thinking', 'redacted_thinking', 'fallback'
# the deltas each readable block takes; any other delta type (citations_delta, input_json_delta, ...) is refused
BLOCK_DELTAS: Mapping[str, frozenset[str]] = MappingProxyType({
    TEXT_BLOCK: frozenset({'text_delta'}), THINKING_BLOCK: frozenset({'thinking_delta', 'signature_delta'}),
    REDACTED_BLOCK: frozenset()})
_DELTA_FIELDS: Mapping[str, str] = MappingProxyType({
    'text_delta': 'text', 'thinking_delta': 'thinking', 'signature_delta': 'signature'})
FALLBACK_PREFIX = 'fallback'  # a usage.iterations entry whose type starts with it says a fallback served the turn
# stream codes (assemble's), each in CPT Studio's words
BYTES, UTF8, JSON, MODEL_CODE, CONTENT, INCOMPLETE = 'bytes', 'utf8', 'json', 'model', 'content', 'incomplete'


def _words(value: object, limit: int = 40) -> str:
    """A value the vendor states (a stop reason, a type, a category), as participants.reading.vendor_word names one."""
    return reading.vendor_word(value, limit)


@dataclass(frozen=True)
class Stream:
    """One answer stream, read (1.4). ``model`` and ``message_id``: message_start's, as stated ('' when it states none
    that fits); ``usage``: message_start's usage with message_delta's merged over it field by field (Anthropic's
    message_delta usage is cumulative) - final only when ``final_usage``; ``stop_reason`` and ``refusal_category``
    (stop_details.category, one vendor word, never the explanation): message_delta's, '' when none; ``texts``: each text
    block's text, in order; ``blocks``: every block's type, in order; ``error_type``: an error event's error.type as
    stated ('' when none or not a string), ``errored`` whether one ended the stream and ``error_after_start`` whether
    message_start came before it; ``unknown_events``: the events of types this reader does not know, skipped (kept for
    the operator; Anthropic documents that new event types may appear)."""
    model: str = ''
    message_id: str = ''
    usage: Mapping[str, Any] = MappingProxyType({})
    final_usage: bool = False
    stop_reason: str = ''
    refusal_category: str = ''
    texts: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()
    error_type: str = ''
    errored: bool = False
    error_after_start: bool = False
    unknown_events: int = 0

    @property
    def text(self) -> str:
        """The answer text: the text blocks, joined in order."""
        return ''.join(self.texts)


@dataclass(frozen=True)
class _Event:
    name: str  # the event: line's value, '' when the event has none
    data: dict[str, Any]
    kind: str  # data['type']


class _Scan:
    """What one pass over the stream found (``_scan``): the facts ``assemble``, ``complete``, ``describe``,
    ``classify`` and ``answer_text`` read, so every reader of the bytes reads them by one implementation. ``framing``:
    rule 1's refusal (code, why), after which nothing more is read; ``failure``: the first refusal of rules 2-6; ``model``:
    the model signal of rule 3 and 1.6 ('' when none; whatever follows, it decides first); ``ended``: the end event that
    closed the stream ('' when none: the stream stopped before its end)."""

    def __init__(self) -> None:
        self.framing: tuple[str, str] = ('', '')
        self.inside = False  # the bytes end inside an event
        self.failure: tuple[str, str] = ('', '')
        self.model_why = ''
        self.ended = ''
        self.started = False
        self.first_counted = ''
        self.model = ''
        self.message_id = ''
        self.usage: dict[str, Any] = {}
        self.delta = False
        self.stop_reason = ''
        self.refusal_category = ''
        self.texts: list[str] = []
        self.blocks: list[str] = []
        self.open: Optional[int] = None  # the index of the open block
        self.error_type = ''
        self.errored = False
        self.error_after_start = False
        self.unknown_events = 0

    def fail(self, code: str, why: str) -> None:
        if not self.failure[0]:
            self.failure = (code, why)

    def hold_model(self, why: str) -> None:
        if not self.model_why:
            self.model_why = why

    @property
    def complete(self) -> bool:
        """Whether the bytes end, after rule 1's parse, with message_stop or an error event (and nothing after it but
        skipped events)."""
        return not self.framing[0] and bool(self.ended) and not self.inside

    @property
    def final_usage(self) -> bool:
        """Whether the usage is Anthropic's final one: message_delta arrived and the stream ended with message_stop."""
        return self.complete and self.ended == MESSAGE_STOP and self.delta

    def stream(self) -> Stream:
        return Stream(model=self.model, message_id=self.message_id, usage=MappingProxyType(dict(self.usage)),
                      final_usage=self.final_usage, stop_reason=self.stop_reason,
                      refusal_category=self.refusal_category, texts=tuple(self.texts), blocks=tuple(self.blocks),
                      error_type=self.error_type, errored=self.errored, error_after_start=self.error_after_start,
                      unknown_events=self.unknown_events)


def _events(raw: object) -> tuple[list[_Event], tuple[str, str], bool]:
    """Rule 1: the events the bytes hold, in order, rule 1's refusal ('', '' when none), and whether the bytes end
    inside an event. The bytes are strict UTF-8, line by line (a \\n byte is never inside a UTF-8 sequence, so what came
    before a bad line is still read: the model a stream named is never lost to a later byte); a line ends with \\n (a
    \\r\\n is read as \\n); an empty line ends an event; a line opening with ':' is a comment; an event has at most one
    event: line and exactly one data: line, whose value is strict JSON - an object with a string type that equals the
    event: line's value when one is given - and no other field. What follows the last \\n, and an event no empty line
    ends, is not an event: the stream stopped inside it (a UTF-8 sequence cut in two included)."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        return [], (BYTES, 'there are no response bytes'), False
    events: list[_Event] = []
    lines = bytes(raw).split(b'\n')
    pending: dict[str, list[str]] = {}
    for number, encoded in enumerate(lines[:-1], start=1):  # the last piece follows the last \n: unterminated
        try:
            line = encoded.decode('utf-8')
        except UnicodeDecodeError:
            return events, (UTF8, f'line {number:,} of the answer stream is not valid UTF-8'), False
        if line.endswith('\r'):
            line = line[:-1]
        if not line:
            if pending:
                event, why = _event(pending)
                if event is None:
                    return events, (JSON, f'event {len(events) + 1:,} of the answer stream {why}'), False
                events.append(event)
                pending = {}
            continue
        if line.startswith(':'):
            continue  # a comment
        field, colon, value = line.partition(':')
        if not colon or field not in ('event', 'data'):
            return events, (JSON, f'line {number:,} of the answer stream is not an event or data line'), False
        if value.startswith(' '):
            value = value[1:]
        if field in pending:
            return events, (JSON, f'line {number:,} of the answer stream repeats its event\'s {field} line'), False
        pending[field] = [value]
    return events, ('', ''), bool(pending) or bool(lines[-1])


def _event(fields: dict[str, list[str]]) -> tuple[Optional[_Event], str]:
    """One event of rule 1, or (None, why it is refused)."""
    if 'data' not in fields:
        return None, 'has no data line'
    try:
        data = reading.strict_json_text(fields['data'][0])
    except reading.JSONRefused as exc:
        return None, f'has data that {exc}'
    if not isinstance(data, dict) or not isinstance(data.get('type'), str) or not data['type']:
        return None, 'has data that is not an object naming its type'
    name = fields['event'][0] if 'event' in fields else ''
    if 'event' in fields and name != data['type']:
        return None, 'names another type than its data'
    return _Event(name=name, data=data, kind=data['type']), ''


def _fell_back(usage: object) -> bool:
    """Whether a usage object carries a usage.iterations entry whose type starts with 'fallback': the served-by signal
    of a fallback (anthropic_fable._fell_back's rule; a fallback content block is the other half, read per block)."""
    iterations = usage.get('iterations') if isinstance(usage, dict) else None
    return isinstance(iterations, list) and any(
        isinstance(entry, dict) and isinstance(entry.get('type'), str) and entry['type'].startswith(FALLBACK_PREFIX)
        for entry in iterations)


_OTHER_MODEL = 'the answer stream names a model other than the one requested'
_NO_MODEL = 'the answer stream does not name the model that answered'
_FALLBACK = 'a fallback took part in the answer, which this request never asks for'
_AFTER_END = 'the answer stream goes on after its end'


def _scan(raw: object) -> _Scan:
    """One pass over the stream (rules 1-7 of 1.4 and the model signals of 1.6), recording the first refusal of each
    kind without stopping at it - so the precedence of 1.5 is read over the whole stream rule 1 can parse."""
    found = _Scan()
    events, found.framing, found.inside = _events(raw)
    for event in events:
        if found.ended:  # rule 6 and 7: the stream has ended; a skipped event after it is harmless
            if event.kind in COUNTED:
                found.fail(CONTENT, _AFTER_END)
            elif event.kind != PING:
                found.unknown_events += 1
            continue
        if event.kind == PING:
            continue
        if event.kind not in COUNTED:
            found.unknown_events += 1  # rule 2: skipped and counted
            continue
        if not found.first_counted:
            found.first_counted = event.kind
            if event.kind not in (MESSAGE_START, ERROR):  # rule 3: it names no model (P-5's "or none")
                found.hold_model(_NO_MODEL)
        _step(found, event)
    if not found.ended and not found.framing[0]:
        found.fail(INCOMPLETE, 'the answer stream ended before its end event')
    elif found.inside and not found.framing[0]:
        found.fail(CONTENT, _AFTER_END)  # the bytes go on past the end event and stop inside another
    return found


def _step(found: _Scan, event: _Event) -> None:
    data = event.data
    if event.kind == ERROR:  # rule 7: it ends the stream wherever it comes; its message is never kept
        error = data.get('error')
        kind = error.get('type') if isinstance(error, dict) else None
        found.error_type = kind if isinstance(kind, str) else ''
        found.errored, found.error_after_start, found.ended = True, found.started, ERROR
        return
    if event.kind == MESSAGE_START:
        _message_start(found, data)
        return
    if not found.started:
        found.fail(CONTENT, f'the answer stream sends {event.kind} before message_start')
        return
    if event.kind == BLOCK_START:
        _block_start(found, data)
    elif event.kind == BLOCK_DELTA:
        _block_delta(found, data)
    elif event.kind == BLOCK_STOP:
        index = data.get('index')
        if found.open is None or type(index) is not int or index != found.open:
            found.fail(CONTENT, 'the answer stream closes a block that is not the open one')
        else:
            found.open = None
    elif event.kind == MESSAGE_DELTA:
        _message_delta(found, data)
    elif event.kind == MESSAGE_STOP:
        if not found.delta:
            found.fail(CONTENT, 'the answer stream ends with no message_delta')
        found.ended = MESSAGE_STOP


def _message_start(found: _Scan, data: dict[str, Any]) -> None:
    message = data.get('message')
    message = message if isinstance(message, dict) else {}
    model = message.get('model')  # 1.6: checked before anything else the answer says
    if not isinstance(model, str) or not model:
        found.hold_model(_NO_MODEL)
    elif model not in READ_MODELS[ADAPTER_VERSION_V3]:
        found.hold_model(_OTHER_MODEL)
    usage = message.get('usage')
    if _fell_back(usage):
        found.hold_model(_FALLBACK)
    if found.started:
        found.fail(CONTENT, 'the answer stream starts its message twice')
        return
    found.started = True
    found.model = reading.recorded_model(model)
    message_id = message.get('id')
    found.message_id = message_id if isinstance(message_id, str) and _MESSAGE_ID.fullmatch(message_id) else ''
    found.usage = dict(usage) if isinstance(usage, dict) else {}
    if message.get('type') != 'message' or message.get('role') != 'assistant' or message.get('content') != []:
        found.fail(CONTENT, 'the answer stream does not start an empty assistant message')


def _block_start(found: _Scan, data: dict[str, Any]) -> None:
    block, index = data.get('content_block'), data.get('index')
    stated = block.get('type') if isinstance(block, dict) else None
    kind = stated if isinstance(stated, str) else ''
    if kind == FALLBACK_BLOCK:  # 1.6: a fallback block holds, whatever follows
        found.hold_model(_FALLBACK)
    if found.delta:
        found.fail(CONTENT, 'the answer stream opens a block after message_delta')
        return
    if found.open is not None or type(index) is not int or index != len(found.blocks):
        found.fail(CONTENT, 'the answer stream opens a block out of order')
        return
    if not isinstance(block, dict) or kind not in BLOCK_DELTAS:
        found.fail(CONTENT, f'the answer carries a block of type {_words(stated)}, which this request never asks for')
        return
    if kind == TEXT_BLOCK:
        citations = block.get('citations')
        if not isinstance(block.get('text'), str) or citations not in (None, []):
            found.fail(CONTENT, 'the answer carries a text block that is not plain text')
            return
        found.texts.append(block['text'])
    elif kind == THINKING_BLOCK and any(not isinstance(block[name], str) for name in ('thinking', 'signature')
                                          if name in block):
        found.fail(CONTENT, 'the answer carries a malformed thinking block')
        return
    found.blocks.append(kind)
    found.open = index


def _block_delta(found: _Scan, data: dict[str, Any]) -> None:
    delta, index = data.get('delta'), data.get('index')
    if found.open is None or type(index) is not int or index != found.open:
        found.fail(CONTENT, 'the answer stream sends a delta to a block that is not open')
        return
    kind = delta.get('type') if isinstance(delta, dict) else None
    block = found.blocks[found.open]
    if not isinstance(delta, dict) or kind not in BLOCK_DELTAS[block]:
        found.fail(CONTENT, f'the answer stream sends a delta of type {_words(kind)} to a {block} block')
        return
    value = delta.get(_DELTA_FIELDS[kind])
    if not isinstance(value, str):
        found.fail(CONTENT, f'the answer stream sends a {kind} that carries no string')
        return
    if block == TEXT_BLOCK:
        found.texts[-1] += value  # thinking and signatures are kept in the bytes, never read


def _message_delta(found: _Scan, data: dict[str, Any]) -> None:
    usage, delta = data.get('usage'), data.get('delta')
    if _fell_back(usage):
        found.hold_model(_FALLBACK)
    if found.delta:
        found.fail(CONTENT, 'the answer stream sends message_delta twice')
        return
    if found.open is not None:
        found.fail(CONTENT, 'the answer stream ends its message with a block open')
        return
    if not isinstance(delta, dict):
        found.fail(CONTENT, 'the answer stream sends a message_delta with no delta')
        return
    found.delta = True
    stop = delta.get('stop_reason')
    found.stop_reason = stop if isinstance(stop, str) else ''
    details = delta.get('stop_details')
    category = details.get('category') if isinstance(details, dict) else None
    found.refusal_category = _words(category) if isinstance(category, str) and category.strip() else ''
    if isinstance(usage, dict):
        found.usage = {**found.usage, **usage}  # cumulative: message_delta's fields replace message_start's


def assemble(raw: object) -> tuple[Optional[Stream], str, str]:
    """(the answer stream, '', '') when the bytes are one stream under 1.4's rules - an error-ended stream included
    (``errored``: its error type is its outcome, by 1.5's precedence) - or (None, code, why it is not), ``why`` in CPT
    Studio's words. The codes: bytes, utf8 and json (rule 1), model (rule 3 and 1.6: another model or none, a fallback;
    it decides first, whatever follows), content (rules 2-6), incomplete (no end event). Pure."""
    found = _scan(raw)
    if found.model_why:
        return None, MODEL_CODE, found.model_why
    if found.errored:
        return found.stream(), '', ''
    if found.framing[0]:
        return None, found.framing[0], found.framing[1]
    if found.failure[0]:
        return None, found.failure[0], found.failure[1]
    return found.stream(), '', ''


def complete(raw: object) -> bool:
    """participants.http's end test (Vendor.complete): True exactly when the bytes end, after rule 1's parse, with
    message_stop or an error event (nothing after it but skipped events); an end of the bytes anywhere else - a stream
    stopped mid-way, an event left unterminated, a cut UTF-8 sequence - is incomplete. It never raises."""
    try:
        return _scan(raw).complete
    except Exception:  # noqa: BLE001 - what a response says never raises into the send discipline
        return False


def describe(raw: object) -> tuple[dict[str, Any], str, str]:
    """(usage, model, id) as an answer stream states them: message_start's model and message id, and the usage merged
    over message_delta's - only when a message_delta arrived and the stream ended with message_stop (Anthropic's usage
    is final there); a stream that was cut, ended early or ended by an error event records none, its message_start
    usage staying readable in its kept bytes [R:connector-CONN-3]. An error body (a non-200) states none of them. It
    never raises (participants.http.described's contract)."""
    try:
        found = _scan(raw)
    except Exception:  # noqa: BLE001 - what a response says never changes its outcome
        return {}, '', ''
    return (dict(found.usage) if found.final_usage else {}), found.model, found.message_id


VENDOR = http.Vendor(label='Anthropic', request_id_header='request-id', describe=describe, complete=complete)


# --- the request (1.2) --------------------------------------------------------------------------------------------------

def _finished(body: dict[str, Any], text: str, max_bytes: int) -> ProviderRequest:
    """The ProviderRequest of a built body under this module's NAME and ADAPTER_VERSION_V3 (http.finished_request: its
    canonical sha256, contexts ``(text,)``; adapter._finished's rules), refused when it cannot be encoded or is over
    ``max_bytes`` - never truncated."""
    try:
        canonical_body(body)
    except UnicodeEncodeError:
        raise NotBuilt(adapter.ENCODING_MESSAGE, reason=adapter.ENCODING) from None
    try:
        return http.finished_request(NAME, ADAPTER_VERSION_V3, body, text, max_bytes=max_bytes)
    except ProviderUnavailable as exc:  # the body encodes, so only the byte limit is left
        raise NotBuilt(str(exc), reason=adapter.SIZE) from None


def build_extraction_request(text: str, pages: Sequence[PageSpan], kind: str, *,
                             max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> ProviderRequest:
    """Pass 1's request for one revision (gemini-events@3; 1.2): contract/extract_prompt.request_parts_fable of the
    revision framed by extract_prompt.framed - its text, pages and kind, nothing else (D1) - as a ProviderRequest of
    ADAPTER_VERSION_V3 whose contexts are ``(text,)``. adapter.build_extraction_request's steps: NotBuilt when the text
    cannot be framed (extract_prompt's Unframed reason), holds NUL, cannot be encoded or is over the byte limit;
    TypeError for a text or pages of the wrong type, ValueError for an unknown kind, RuntimeError when a pin does not
    match (extract_prompt.check_pins_fable). Pure: no settings, credentials or network."""
    spans = adapter._document(text, pages)
    framed = extract_prompt.framed(text, spans, kind)
    if framed is None:
        reason = extract_prompt.unframed(text, spans)
        if reason is None:  # framed() returns None exactly when unframed() names a reason
            raise RuntimeError('framed() refused a text unframed() accepts; nothing is built.')
        raise adapter._unframed(reason)
    return _finished(extract_prompt.request_parts_fable(framed), text, max_bytes)


def build_appraisal_request(text: str, pages: Sequence[PageSpan], kind: str, extraction: ProviderRequest,
                            extraction_bytes: object, *, check: Check,
                            max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> AppraisalRequest:
    """Pass 2's request for one revision (gemini-appraisal@2; 1.2), built from the revision plus pass 1's STORED answer,
    by adapter.build_appraisal_request's five steps: (1) pass 1's request built again and ``extraction`` must be it byte
    for byte (STORED otherwise); (2) the stored answer read by this module's envelope and contract/extract_read (a
    Refusal is STORED with effect REFUSED and the Refusal kept, D229); (3) ``check`` gives the findings; (4) contract/
    appraise_prompt's Fable request is built, its claim set refused over claims.CLAIM_BOUND_V3 before its body is
    written (OverBound: TOO_LONG with the count; 1.9 door 0); (5) the bound checked again and the body made a
    ProviderRequest (ENCODING, SIZE). Pure, given a pure check."""
    spans = adapter._document(text, pages)
    if not callable(check):
        raise TypeError(adapter.NO_CHECK)
    own = build_extraction_request(text, spans, kind, max_bytes=max_bytes)
    if not adapter._same_request(extraction, own):
        raise NotBuilt(adapter.STORED_OTHER, reason=adapter.STORED)
    unit_count = len(segment.units(text, spans))
    answer = read_extraction(extraction, extraction_bytes, unit_count)
    if isinstance(answer, extract_read.Refusal):
        raise NotBuilt(adapter.STORED_REFUSED.format(stage=answer.stage), reason=adapter.STORED,
                       effect=adapter.REFUSED, refusal=answer)
    findings = check(text, spans, answer)
    try:
        built = appraise_prompt.build_request_fable(text, spans, kind, answer, findings=findings)
    except appraise_prompt.OverBound as exc:
        raise _over_bound(exc.count) from None
    except appraise_prompt.Unbuilt as exc:  # not reached: pass 1's request was framed from this same text in step 1
        raise adapter._unframed(exc.reason) from None
    count = len(built.claim_set.claims)
    if count > claims.CLAIM_BOUND_V3:  # refused by appraise_prompt before its body; never sent if it were not
        raise _over_bound(count)
    return AppraisalRequest(_finished(built.body, text, max_bytes), built, answer, findings, unit_count)


def _over_bound(count: int) -> NotBuilt:
    return NotBuilt(adapter.CLAIMS_MESSAGE.format(count=count, bound=claims.CLAIM_BOUND_V3), reason=adapter.CLAIMS,
                    effect=adapter.TOO_LONG, claims=count)


def body_kind(body: Any) -> tuple[str, str]:
    """(EXTRACTION or APPRAISAL, '') when ``body`` is exactly a body of that kind as the builders write it (1.2):
    http.check_shape first (exactly BODY_KEYS, model claude-fable-5-2), then contract/extract_prompt.request_parts_fable
    of the framed document its one user turn carries, or contract/appraise_prompt.request_parts_fable of a user turn of
    2.4's form (the framed document - checked by extract_prompt._is_framed, so no Gemini pin is read - then the cards,
    then the claims, each one line as claims.py writes it: adapter._card_ids and adapter._claim_lines). So the
    instruction, the schema, the effort, the output maximum and the cache marker are this version's byte for byte, and
    nothing rides along. Otherwise ('', why not): UNPINNED_V3 when a pin does not match, else NOT_BUILT."""
    try:
        http.check_shape(body, MODEL, BODY_KEYS)
        turn = body['messages'][0]['content'][0]['text']
    except (ProviderUnavailable, KeyError, IndexError, TypeError):
        return '', NOT_BUILT
    if not isinstance(turn, str):
        return '', NOT_BUILT
    try:
        if extract_prompt._is_framed(turn):
            return (EXTRACTION, '') if body == extract_prompt.request_parts_fable(turn) else ('', NOT_BUILT)
        if _appraisal_document(turn) is not None and body == appraise_prompt.request_parts_fable(turn):
            return APPRAISAL, ''
    except RuntimeError:  # a pin: a changed instruction, schema or table with no new version
        return '', UNPINNED_V3
    except (TypeError, ValueError):
        return '', NOT_BUILT
    return '', NOT_BUILT


def _appraisal_document(turn: str) -> Optional[str]:
    """The framed document a pass-2 user turn opens with, when the turn has 2.4's form (adapter._appraisal_document's
    rules: the framed document up to its END marker line, a blank line, the cards under claims.CARDS_HEADING, a blank
    line, the claims under claims.CLAIMS_HEADING, no other blank line, every card one card and every claim one claim
    as claims.py writes them) - with the framed document checked by extract_prompt._is_framed - else None."""
    lines = turn.split('\n')
    if len(lines) < 3:
        return None
    begin, tail = lines[2], ' BEGIN>>>'
    if begin[:3] != '<<<' or begin[-len(tail):] != tail:
        return None
    end = begin[:-len(tail)] + ' END>>>'
    if end not in lines:
        return None
    at = lines.index(end)
    document, rest = '\n'.join(lines[:at + 1]), lines[at + 1:]
    if rest[:2] != ['', claims.CARDS_HEADING] or '' not in rest[2:]:
        return None
    gap = rest.index('', 2)
    if rest[gap + 1:gap + 2] != [claims.CLAIMS_HEADING] or '' in rest[gap + 2:]:
        return None
    cards = adapter._card_ids(rest[2:gap])
    if cards is None or not _claim_lines(rest[gap + 2:], cards):
        return None
    return document if extract_prompt._is_framed(document) else None


def _template_texts() -> tuple[tuple[str, ...], ...]:
    """adapter._template_texts' pieces, read under gemini-appraisal@2 - the label a Fable pass-2 request's claims are
    built under (appraise_prompt.build_request_fable; AMENDMENT-2 8.1) - so a claim rendered from a sentence only @2
    has (DECISIONS D292's U3: "In session X the endoscope itself reached anatomy Y.") is one of claims.py's sentences
    here, as every @1 sentence is under @1 (the a2b integration: step f2-2's request R3; refute-f3s-r2 F1). Read at
    each call, as adapter's is."""
    found = []
    for template_id in claims.TemplateId:
        pieces = ['']
        sentence = claims.template(template_id, interpretation.APPRAISAL_VERSION_V3)
        for literal, field, _spec, _conversion in Formatter().parse(sentence):
            pieces[-1] += literal
            if field is not None:
                pieces.append('')
        found.append(tuple(pieces))
    return tuple(found)


def _claim_lines(lines: Sequence[str], cards: frozenset[str]) -> bool:
    """adapter._claim_lines' rule (adapter.py is not edited: AMENDMENT-2 section 9) over gemini-appraisal@2's
    sentences (``_template_texts``): every line is one claim as appraise_prompt.claim_line writes it - claims.
    CLAIM_LINE of the claim ids K1, K2, ... in order, about a card ``cards`` lists or the document, citing unit ids,
    and a sentence that is one of claims.py's @2 templates with each field filled."""
    templates = _template_texts()
    for number, line in enumerate(lines, start=1):
        claim = f'{adapter._CLAIM_LETTER}{number}'
        head, _, after = claims.CLAIM_LINE.format(claim=claim, card=adapter._FIELD, units=adapter._NEXT_FIELD,
                                                  sentence=adapter._LAST_FIELD).partition(adapter._FIELD)
        after_card, _, after = after.partition(adapter._NEXT_FIELD)
        after_units, _, tail = after.partition(adapter._LAST_FIELD)
        if not after_card or not after_units or not line.startswith(head):
            return False
        card_end = line.find(after_card, len(head))
        units_end = line.find(after_units, card_end + len(after_card)) if card_end >= 0 else -1
        start, stop = units_end + len(after_units), len(line) - len(tail)
        if units_end < 0 or start > stop or not line.endswith(tail):
            return False
        card, sentence = line[len(head):card_end], line[start:stop]
        units = adapter._unit_ids(line[card_end + len(after_card):units_end])
        if (units is None or (card not in cards and card != claims.DOCUMENT_CARD)
                or not any(adapter._fills(sentence, texts) for texts in templates)
                or claims.CLAIM_LINE.format(claim=claim, card=card, units=claims.units_phrase(units),
                                            sentence=sentence) != line):
            return False
    return True


# --- the answers: the envelope, then contract/'s readers (1.4) ------------------------------------------------------------

STORED_VERSION = adapter.STORED_VERSION
OTHER_KIND = adapter.OTHER_KIND
OTHER_APPRAISAL = adapter.OTHER_APPRAISAL
ERROR_ENDED = 'the answer stream ended with an error ({kind}), so it carries no answer'
NOT_AT_END = 'the answer stopped for {reason}, not at the end of its turn'
CUT_OFF_WHY = 'the reading reached its output limit before it was complete'
DECLINED_WHY = 'the model declined to answer ({category})'
NO_TEXT = 'the answer carries no text block'


def _envelope(raw: object) -> tuple[str, str, str]:
    """(answer text, '', '') of a usable answer, or ('', code, why it is refused): the model first (1.6), then an
    error event, then the stream's own rules, then the stop reason, then a text block."""
    found = _scan(raw)
    if found.model_why:
        return '', MODEL_CODE, found.model_why
    if found.errored:
        return '', ERROR, ERROR_ENDED.format(kind=_words(found.error_type) if found.error_type else 'no type named')
    if found.framing[0]:
        return '', found.framing[0], found.framing[1]
    if found.failure[0]:
        return '', found.failure[0], found.failure[1]
    if found.stop_reason == CUT_OFF:
        return '', CUT_OFF, CUT_OFF_WHY
    if found.stop_reason == DECLINE:
        return '', DECLINE, DECLINED_WHY.format(category=_category(found.refusal_category))
    if found.stop_reason != END_TURN:
        return '', 'stop', NOT_AT_END.format(reason=_words(found.stop_reason) if found.stop_reason
                                             else 'no stated reason')
    if not found.texts:
        return '', 'no_text', NO_TEXT
    return ''.join(found.texts), '', ''


def _category(category: str) -> str:
    return f'category {category}' if category else 'no category was given'


def answer_text(request: ProviderRequest, raw: object, purpose: str) -> Union[str, extract_read.Refusal]:
    """The answer text of a stored answer stream to a request of ADAPTER_VERSION_V3 - or contract/extract_read's
    Refusal (stage 'envelope') of all of it - in 1.4's order: the request is this provider's and version's; the model is
    exactly claude-fable-5-2 with no fallback (checked first of everything the answer says, D13, D275); the stream
    assembles; it stopped at end_turn; it carries a text block. The text is the text blocks joined in order; for pass 1
    (``purpose`` EXTRACTION) it must then be one JSON object, alone or alone in one fence (participants.reading.
    sole_object); pass 2's (APPRAISAL) is returned as it stands. Pure: a stored answer is read again with no request.
    ValueError for another purpose."""
    if purpose not in PURPOSES:
        raise ValueError(f'An answer is read for one of {", ".join(PURPOSES)}.')
    if getattr(request, 'provider', None) != NAME or getattr(request, 'adapter_version', None) not in READ_VERSIONS:
        return extract_read.refuse('envelope', STORED_VERSION)
    text, code, why = _envelope(raw)
    if code:
        return extract_read.refuse('envelope', why)
    if purpose == EXTRACTION:
        text, why = reading.sole_object(text)
        if why:
            return extract_read.refuse('envelope', why)
    return text


def read_extraction(request: ProviderRequest, response_bytes: object,
                    unit_count: int) -> Union[extract_read.ReadAnswer, extract_read.Refusal]:
    """Pass 1's stored answer, read: ``request`` a pass-1 request of READ_VERSIONS (body_kind), then the envelope
    (answer_text), then contract/extract_read.read with the revision's ``unit_count``. The Refusal of the whole answer
    otherwise; RuntimeError when a pin does not match."""
    if getattr(request, 'provider', None) != NAME or getattr(request, 'adapter_version', None) not in READ_VERSIONS:
        return extract_read.refuse('envelope', STORED_VERSION)
    if body_kind(getattr(request, 'body', None))[0] != EXTRACTION:
        return extract_read.refuse('envelope', OTHER_KIND)
    answer = answer_text(request, response_bytes, EXTRACTION)
    if isinstance(answer, extract_read.Refusal):
        return answer
    # AMENDMENT-2 4.3.1 and 8.1 (D275's slot rule): a Fable answer is read under gemini-events@3, so an overfilled
    # slot is an item-level finding (slot_overfull), never S1's refusal of the whole answer (the a2b integration)
    return extract_read.read(answer, unit_count, version=interpretation.INTERPRETATION_VERSION_V3)


def read_appraisal(appraisal: AppraisalRequest, request: ProviderRequest,
                   response_bytes: object) -> Union[appraise_read.ReadAppraisal, extract_read.Refusal]:
    """Pass 2's answer, read against the claims it answered: ``request`` (the run's) must be ``appraisal.request`` byte
    for byte (a verdict is never read against a claim set it did not answer), then the envelope, then contract/
    appraise_read.read with the claim set and the revision's unit count. The Refusal of the whole answer otherwise."""
    if getattr(request, 'provider', None) != NAME or getattr(request, 'adapter_version', None) not in READ_VERSIONS:
        return extract_read.refuse('envelope', STORED_VERSION)
    if not adapter._same_request(request, appraisal.request):
        return extract_read.refuse('envelope', OTHER_APPRAISAL)
    answer = answer_text(request, response_bytes, APPRAISAL)
    if isinstance(answer, extract_read.Refusal):
        return answer
    # AMENDMENT-2 8.1-8.2: read under the label the request's claims were built under, gemini-appraisal@2 (the a2b
    # integration)
    return appraise_read.read(answer, appraisal.built.claim_set, appraisal.unit_count,
                              version=interpretation.APPRAISAL_VERSION_V3)


# --- classification (1.5) ---------------------------------------------------------------------------------------------

_HOLD_WHY: Mapping[str, str] = MappingProxyType({
    AUTH: 'The key was refused{said}: every request would be refused until an operator acts.',
    PERMISSION: 'The key may not use the model or the service{said}: every request would be refused until an operator '
                'acts.',
    QUOTA: 'A payment is required for the key{said}: every request would be refused until an operator acts.',
    'quota-unnamed': 'A quota or spending limit was exhausted{said} and no rate limit was named: every request would be '
                     'refused until an operator acts.',
    REFUSED_HOLD: 'Requests of this version were refused as invalid{said}: every request would be refused until an '
                  'operator acts.',
})
_STREAM_ERROR = 'an error event in the answer stream'
# how a FAILED row's sentence ends: 'retry later' (a transient failure) or 'refused' (this attempt is over); word()
RETRY_LATER_TAIL, OVER_TAIL = 'it may be tried again later.', 'this attempt is over.'


def classify(outcome: str, http_status: object, response_bytes: object) -> Optional[Classification]:
    """What a run's definite outcome means (ProviderRun.state with its HTTP status and response bytes; 1.5): None for
    an outcome that is not definite - 'unknown' (reconciled, 6.9) or 'not_sent' - or not an outcome at all.

    'succeeded' (a 200 stream, or a replayed recording of one), in 1.5's precedence: (1) a message_start naming another
    model or none, a fallback block, a fallback usage iteration, or a stream whose first counted event is neither
    message_start nor error - HOLD model, whatever follows (P-5); (2) an error event, wherever it comes: its error.type
    decides by the rows below, so an error before any message_start (an overload as the stream opened) is FAILED, never
    HOLD model [R:connector-CONN-4]; (3) a stream that does not assemble - FAILED; (4) the stop reason: end_turn with a
    text block ANSWERED (with none FAILED), max_tokens TOO_LONG (C5: never re-sent for a member), refusal HOLD declined
    (D275: never re-asked of another model; holds.request_bound blocks its request after the release), anything else
    FAILED.

    'failed' (a non-200, its body kept), the body's named error before the HTTP status, in adapter.classify's
    precedence (holds by name, then holds by status, then the 429 rule, then the failures): a hold the error type names
    (authentication_error auth; billing_error quota, the payment sentence; permission_error and not_found_error
    permission; invalid_request_error refused), else the hold the status names (401 auth, 402 quota, 403 and 404
    permission, any other 4xx but 413 and 429 refused), else rate_limit_error FAILED (retry later; D11: no automatic
    retry), else any other 429 HOLD quota (D39: a 429 is a rate limit only when Anthropic says so by its error type),
    else request_too_large or 413 FAILED (refused: that request only), else FAILED (retry later: overloaded_error,
    api_error, timeout_error, any other type, a 5xx, an unread redirect)."""
    status = http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None
    if outcome == 'succeeded':
        return _classify_stream(status, response_bytes)
    if outcome != 'failed':
        return None
    return _by_error(_error_type(response_bytes), status, stream=False)


def _classify_stream(status: Optional[int], raw: object) -> Classification:
    found = _scan(raw)
    if found.model_why:
        return Classification(HOLD, hold=MODEL_HOLD, http_status=status,
                              why=f'The answer was not read: {found.model_why}. No further request is sent until an '
                                  'operator releases the hold.')
    if found.errored:
        return _by_error(found.error_type, status, stream=True)
    if found.framing[0] or found.failure[0]:
        why = found.framing[1] if found.framing[0] else found.failure[1]
        return Classification(FAILED, http_status=status, why=f'The answer was not read: {why}; {OVER_TAIL}')
    if found.stop_reason == END_TURN:
        if found.texts:
            return Classification(ANSWERED, http_status=status)
        return Classification(FAILED, http_status=status, why=f'The answer was not read: {NO_TEXT}; {OVER_TAIL}')
    if found.stop_reason == CUT_OFF:  # [R:truth-T7]: the output limit, never "the document is too long"
        return Classification(TOO_LONG, http_status=status,
                              why='The answer was not read: the reading reached its output limit before it was '
                                  'complete.')
    if found.stop_reason == DECLINE:
        category = found.refusal_category
        return Classification(HOLD, hold=DECLINED, http_status=status,
                              vendor_status=category if _TYPE.fullmatch(category) else '',
                              why=f'The answer was not read: the model declined to answer ({_category(category)}), '
                                  'and nothing was asked of another model. No further request is sent until an operator '
                                  'releases the hold, and this request is not sent again.')
    reason = _words(found.stop_reason) if found.stop_reason else 'no stated reason'
    return Classification(FAILED, http_status=status,
                          why=f'The answer was not read: it stopped for {reason}, not at the end of its turn; '
                              f'{OVER_TAIL}')


def _error_type(raw: object) -> str:
    """The error type an error body names ({"type": "error", "error": {"type": ...}}), as stated, else ''."""
    try:
        body = reading.strict_json(raw)
    except Exception:  # noqa: BLE001 - not JSON, or not bytes: classified by its HTTP status alone
        return ''
    error = body.get('error') if isinstance(body, dict) and body.get('type') == 'error' else None
    kind = error.get('type') if isinstance(error, dict) else None
    return kind if isinstance(kind, str) else ''


def _by_error(kind: str, status: Optional[int], *, stream: bool) -> Classification:
    """1.5's rows for a named error type and an HTTP status, in adapter.classify's precedence: a hold the type names,
    then a hold the status names (401, 402, 403, 404, and any other 4xx but 413 and 429), then rate_limit_error
    (FAILED, retry later), then any other 429 (HOLD quota: a 429 is a rate limit only when Anthropic says so, D39), then
    request_too_large or 413 (FAILED, refused), then anything else (FAILED, retry later). ``stream``: an error event of a
    200 stream, whose status names nothing."""
    where = _STREAM_ERROR if stream else (f'HTTP {status}' if status is not None else 'no HTTP status')
    said = f' ({where}{", " + _words(kind) if kind else ""})'
    vendor_status = kind if _TYPE.fullmatch(kind) else ''
    code = status if not stream and status is not None else 0  # the status rows read a non-200's status only
    hold = HOLD_TYPES.get(kind, '') or HOLD_STATUSES.get(code, '')
    if not hold and 400 <= code < 500 and code not in (413, 429):
        hold = REFUSED_HOLD
    if hold:
        return Classification(HOLD, hold=hold, http_status=status, vendor_status=vendor_status,
                              why=_HOLD_WHY[hold].format(said=said))
    if kind == RATE_LIMIT_TYPE:
        return Classification(FAILED, http_status=status, vendor_status=vendor_status,
                              why=f'A rate limit refused this attempt{said}; {RETRY_LATER_TAIL}')
    if code == 429:
        return Classification(HOLD, hold=QUOTA, http_status=status, vendor_status=vendor_status,
                              why=_HOLD_WHY['quota-unnamed'].format(said=said))
    if kind == TOO_LARGE_TYPE or code == 413:
        return Classification(FAILED, http_status=status, vendor_status=vendor_status,
                              why=f'The request was refused as too large{said}; {OVER_TAIL}')
    return Classification(FAILED, http_status=status, vendor_status=vendor_status,
                          why=f'The request failed{said}; {RETRY_LATER_TAIL}')


def request_bound(http_status: object, response_bytes: object) -> bool:
    """Whether the hold this answer sets is request-bound (1.5 [R:connector-CONN-1]): the answer began as a 200 stream
    (or a replayed recording of one, which has no status) and says something about that request rather than about the
    account, the version or the model - a decline (stop_reason refusal), or an error event after message_start whose
    type sets a hold. A model signal is about the model, and an error before message_start or an error body about the
    account or the version: neither is request-bound. interpretation.holds reads it for a recorded hold."""
    if isinstance(http_status, bool) or http_status not in (200, None):
        return False
    found = _scan(response_bytes)
    if found.model_why:
        return False
    if found.errored:
        return found.error_after_start and found.error_type in HOLD_TYPES
    return not found.framing[0] and not found.failure[0] and found.stop_reason == DECLINE


def word(effect: str, verdict: Optional[Classification] = None) -> str:
    """1.5's word for an outcome (its second column): ``effect`` is interpretation.holds' (or this module's kind) and
    ``verdict`` the classification it came from. A FAILED row is 'retry later' when the attempt failed for a transient
    reason (a rate limit, an overload or any other named error, a 5xx, an unread redirect) and 'refused' otherwise (the
    answer was not read, or the request was refused as too large); '-' for nothing sent."""
    if effect == ANSWERED:
        return ANSWERED_WORD
    if effect == TOO_LONG:
        return TOO_LONG_WORD
    if effect == HOLD:
        return HOLD_WORD
    if effect == 'unknown':
        return UNKNOWN_WORD
    if effect == FAILED and verdict is not None:
        return RETRY_LATER_WORD if verdict.why.endswith(RETRY_LATER_TAIL) else REFUSED_WORD
    return '-'


# --- the interpreters (1.3) -------------------------------------------------------------------------------------------

class InterpreterF:
    """What the live and the replay Fable interpreters share (adapter.InterpreterV2's structure, kept): both request
    kinds, their readers, and every refusal each makes about a request before anything is sent or replayed, so a
    replayed request takes the paths a live one takes. ``send_deadlines`` maps each purpose to its send deadline.
    ``api_version`` is the anthropic-version a run of this interpreter sends and records (scope.api_version, 1.2
    [R:replay-R8]). ``recording_folder`` and ``recording_suffix`` name where interpretation/replay.py finds a recording
    of this interpreter's requests (GEMINI_REPLAY_DIR/anthropic/<request sha256>.sse; 1.8). A subclass gives ``mode``,
    ``endpoint`` (the URL it calls, '' for none) and ``_exchange``."""
    name = NAME
    adapter_version = ADAPTER_VERSION_V3
    requested_model = MODEL
    api_version = API_VERSION
    vendor = VENDOR
    recording_folder = NAME
    recording_suffix = '.sse'
    mode = ''
    endpoint = ''

    def __init__(self, *, send_deadline: float = SEND_DEADLINE_SECONDS,
                 appraisal_send_deadline: float = APPRAISAL_SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES) -> None:
        for label, seconds in (('send_deadline', send_deadline), ('appraisal_send_deadline', appraisal_send_deadline)):
            if not valid_deadline(seconds):
                raise ValueError(f'{label} must be a positive number of seconds.')
        for label, limit in (('max_request_bytes', max_request_bytes), ('max_response_bytes', max_response_bytes)):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'{label} must be a positive integer.')
        self.send_deadlines: dict[str, float] = {EXTRACTION: send_deadline, APPRAISAL: appraisal_send_deadline}
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes

    def build_extraction_request(self, text: str, pages: Sequence[PageSpan], kind: str) -> ProviderRequest:
        return build_extraction_request(text, pages, kind, max_bytes=self.max_request_bytes)

    def build_appraisal_request(self, text: str, pages: Sequence[PageSpan], kind: str, extraction: ProviderRequest,
                                extraction_bytes: object, *, check: Check) -> AppraisalRequest:
        return build_appraisal_request(text, pages, kind, extraction, extraction_bytes, check=check,
                                       max_bytes=self.max_request_bytes)

    def read_extraction(self, request: ProviderRequest, response_bytes: object,
                        unit_count: int) -> Union[extract_read.ReadAnswer, extract_read.Refusal]:
        return read_extraction(request, response_bytes, unit_count)

    def read_appraisal(self, appraisal: AppraisalRequest, request: ProviderRequest,
                       response_bytes: object) -> Union[appraise_read.ReadAppraisal, extract_read.Refusal]:
        return read_appraisal(appraisal, request, response_bytes)

    def purpose(self, request: ProviderRequest) -> str:
        """The purpose of ``request`` - EXTRACTION or APPRAISAL - when this interpreter would send it, else ''."""
        problem, purpose = self._problem(request)
        return '' if problem else purpose

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str = '',
             original_bytes: Optional[bytes] = None) -> RawExchange:
        """Exactly one exchange within ``deadline_s``, never more than the purpose's send deadline. Refused before
        anything is sent for an invalid deadline or a request this interpreter does not send (_problem).
        ``client_request_id`` is not sent (Anthropic documents no such header) and ``original_bytes`` never are (D12)."""
        if not valid_deadline(deadline_s):
            return http.not_sent(adapter.INVALID_DEADLINE)
        problem, purpose = self._problem(request)
        if problem:
            return http.not_sent(problem)
        deadline = monotonic() + min(deadline_s, self.send_deadlines[purpose])
        return self._exchange(request.body, deadline, purpose)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str = '',
                  original_bytes: Optional[bytes] = None, execute_tool: Optional[Callable[..., Any]] = None,
                  should_stop: Optional[Callable[[], bool]] = None, carried: Sequence[Any] = ()) -> loop.LoopOutcome:
        """The run (jobs._send's looped branch), adapter.InterpreterV2.send_loop's structure: participants.loop.run with
        exactly one exchange, within ``deadline_s`` and never more than the purpose's send deadline, recorded as turn 1.
        Refused before anything is sent - not_sent, no exchange recorded - for an invalid deadline, a request this
        interpreter does not send, a continuation (``carried``: there is none of one exchange) or a Stop check that is
        not callable. ``should_stop`` is asked once, right before the request is sent: a Stop, or a check that raises,
        ends the run there, not sent and ``stopped``. No tool is offered: ``execute_tool`` is never called, and no answer
        is read as asking for one. A failed or unknown exchange ends the run: it is never sent again (D11)."""
        if not valid_deadline(deadline_s):
            return adapter._refused(adapter.INVALID_DEADLINE)
        problem, purpose = self._problem(request)
        if problem:
            return adapter._refused(problem)
        if carried:
            return adapter._refused(adapter.NOT_CONTINUED, MODEL)
        if should_stop is not None:
            if not callable(should_stop):
                return adapter._refused(adapter.NOT_CALLABLE, MODEL)
            halt = adapter._halt(should_stop)
            if halt:
                return loop.LoopOutcome(final=http.not_sent(halt, MODEL), exchanges=(), stopped=True)

        def post(turn: int, body: dict[str, Any], deadline: float) -> RawExchange:
            kind, problem = body_kind(body)
            return http.not_sent(problem, MODEL) if problem else self._exchange(body, deadline, kind)

        return loop.run(self, request, post=post, parse_turn=adapter._no_tool_calls, follow_up=adapter._no_follow_up,
                        execute_tool=adapter._no_tools, deadline_s=deadline_s, longest_s=self.send_deadlines[purpose],
                        max_exchanges=1, max_tool_result_bytes=1, max_request_bytes=self.max_request_bytes,
                        body_keys=BODY_KEYS)

    def _problem(self, request: ProviderRequest) -> tuple[str, str]:
        """(why ``request`` is not sent, '') - another provider's or adapter version's, altered since it was hashed,
        over the size limit, or a body of neither kind - or ('', its purpose)."""
        try:
            verified_body(request, self, self.max_request_bytes)
        except ProviderUnavailable as exc:
            return str(exc), ''
        purpose, problem = body_kind(request.body)
        return problem, purpose

    def _exchange(self, body: dict[str, Any], deadline: float, purpose: str) -> RawExchange:
        raise NotImplementedError


class FableInterpreter(InterpreterF):
    """The live interpreter: one POST to ENDPOINT, the key read at send time (1.11: CPT Studio's existing Anthropic
    credential, settings.ANTHROPIC_CREDENTIALS_FILE), each purpose's own read timeout (``read_timeouts``)."""
    mode = 'live'
    endpoint = ENDPOINT

    def __init__(self, credentials_path: Any, *, connect_timeout: float = CONNECT_TIMEOUT_SECONDS,
                 read_timeout: float = READ_TIMEOUT_SECONDS,
                 appraisal_read_timeout: float = APPRAISAL_READ_TIMEOUT_SECONDS,
                 send_deadline: float = SEND_DEADLINE_SECONDS,
                 appraisal_send_deadline: float = APPRAISAL_SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
                 session_factory: Optional[Callable[[], requests.Session]] = None) -> None:
        super().__init__(send_deadline=send_deadline, appraisal_send_deadline=appraisal_send_deadline,
                         max_request_bytes=max_request_bytes, max_response_bytes=max_response_bytes)
        for label, seconds in (('connect_timeout', connect_timeout), ('read_timeout', read_timeout),
                               ('appraisal_read_timeout', appraisal_read_timeout)):
            if not valid_deadline(seconds):
                raise ValueError(f'{label} must be a positive number of seconds.')
        self.credentials_path = credentials_path
        self.connect_timeout = connect_timeout
        self.read_timeouts: dict[str, float] = {EXTRACTION: read_timeout, APPRAISAL: appraisal_read_timeout}
        self.session_factory: Callable[[], requests.Session] = session_factory or http.default_session

    def _exchange(self, body: dict[str, Any], deadline: float, purpose: str) -> RawExchange:
        """One POST of a verified stored body: the body verified again as a body of ``purpose`` (body_kind), its exact
        canonical bytes, the key read now, nothing else; read within the purpose's read timeout."""
        kind, problem = body_kind(body)
        if problem or kind != purpose:
            return http.not_sent(problem or NOT_BUILT, MODEL)
        try:
            data = http.sendable(body, self.max_request_bytes, with_original=False)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc), MODEL)
        try:
            credentials = load_anthropic_credentials(self.credentials_path)
        except CredentialsError as exc:
            return http.not_sent(f'{exc} No request was sent.', MODEL)
        headers = {KEY_HEADER: credentials.api_key, VERSION_HEADER: API_VERSION, 'content-type': 'application/json'}
        if credentials.workspace_id is not None:
            headers[WORKSPACE_HEADER] = credentials.workspace_id
        return http.post(VENDOR, self.session_factory, ENDPOINT, data, headers, deadline=deadline,
                         connect_timeout=self.connect_timeout, read_timeout=self.read_timeouts[purpose],
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


def get_interpreter_v2(mode: Optional[str] = None) -> Optional[InterpreterF]:
    """The configured Fable interpreter (settings.GEMINI_MODE, the interpreter's mode setting whatever its provider, or
    ``mode``; 1.11): None when it is disabled - nothing is sent, and the stage pauses - else the live or the replay
    interpreter, each purpose with its own settings (pass 1: INTERPRETER_SEND_DEADLINE_SECONDS and
    INTERPRETER_READ_TIMEOUT_SECONDS; pass 2: APPRAISER_SEND_DEADLINE_SECONDS and APPRAISER_READ_TIMEOUT_SECONDS; the
    stream's cap INTERPRETER_MAX_RESPONSE_BYTES). Live needs settings.ANTHROPIC_CREDENTIALS_FILE, replay
    settings.GEMINI_REPLAY_DIR (its anthropic/ folder); misconfiguration raises ProviderUnavailable; an unknown mode is a
    programming error (ValueError). Settings are read here, at call time, never at import."""
    from django.conf import settings  # type: ignore[import-untyped]

    mode = settings.GEMINI_MODE if mode is None else mode
    if mode == 'disabled':
        return None
    limits: dict[str, Any] = {'send_deadline': settings.INTERPRETER_SEND_DEADLINE_SECONDS,
                              'appraisal_send_deadline': settings.APPRAISER_SEND_DEADLINE_SECONDS,
                              'max_response_bytes': settings.INTERPRETER_MAX_RESPONSE_BYTES}
    if mode == 'live':
        if not settings.ANTHROPIC_CREDENTIALS_FILE:
            raise ProviderUnavailable('Live interpretation needs CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE.')
        return FableInterpreter(settings.ANTHROPIC_CREDENTIALS_FILE,
                                connect_timeout=settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS,
                                read_timeout=settings.INTERPRETER_READ_TIMEOUT_SECONDS,
                                appraisal_read_timeout=settings.APPRAISER_READ_TIMEOUT_SECONDS, **limits)
    if mode == 'replay':
        if not settings.GEMINI_REPLAY_DIR:
            raise ProviderUnavailable('Replay interpretation needs CPT_STUDIO_GEMINI_REPLAY_DIR.')
        from studio.interpretation.replay import ReplayInterpreterF

        return ReplayInterpreterF(settings.GEMINI_REPLAY_DIR, **limits)
    raise ValueError(f'No interpreter exists for mode {mode!r}; expected disabled, live or replay.')
