"""The participants' tool loop (HARNESS.md 11.2): one participant phase is one run of at most max_exchanges HTTP
exchanges, in which the model may call CPT Studio's two reference tools and is given their results.

Every exchange is sent under the one send discipline (http.post: no retry, no redirect, no environment proxies or
.netrc, capped reads, the deadline checked per chunk), its read timeout clamped to the time the loop has left. A PDF
original is re-verified and expanded on every exchange that carries its placeholder, and every exchange is recorded with
its request in stored form (the placeholder unexpanded) and that form's sha256. The vendor modules say what an answer
asks for (``parse_turn``) and how the next request passes it back with the tool results (``follow_up``): append-only,
every item exactly as returned, so reasoning and thinking items travel back unchanged.

How a loop ends:
- 'not_sent' only when the first exchange provably never left. A loop refused before it starts (an invalid deadline or
  client request id, no tool executor, a request that fails its verification or is not one the adapter builds) is
  'not_sent' with no exchange recorded; every exchange the loop starts is recorded, sent or not.
- 'unknown' when an exchange's outcome is unknown. The loop stops there and nothing is retried.
- 'failed' when an exchange failed (its body kept), when a later exchange could not be sent, when the participant still
  asks for tools after the last exchange allowed ("the tool-call limit was reached"), when it asks for tool calls CPT
  Studio cannot answer, or when the loop's deadline passes before its tool calls are answered. Nothing more is sent.
- 'succeeded' only when the last exchange is the final answer: one that asks for no tool call. The reader then reads or
  refuses it exactly as a single answer (another model's answer, a refusal or a cut-off answer is final, never acted on).

Tool calls are executed by the caller's ``execute_tool(name, arguments) -> (result, refs)`` (the pipeline passes CPT
Studio's CMS tool executor). An unknown tool, arguments that do not fit the tool's parameters, an executor that raises or
returns anything but (dict, list of str), and a result that is not JSON PostgreSQL can store become the result
{"error": <CPT Studio's own sentence>}; a result over the size limit becomes {"error": "the result is too large; ask for
fewer codes"}, never a truncated one. An error result carries no refs: none of them reached the participant.

The loop's final RawExchange is its last exchange's, with these run-level exceptions: ``usage`` is summed over the
exchanges (summed_usage; one exchange keeps its own, with its own basis), ``latency_ms`` is the exchanges' latencies
added up, ``sent`` says whether any exchange may have reached the vendor, ``endpoint`` is the URL any exchange called and
``error`` says why the loop ended. The ids (vendor request id, response id, returned model) are the last exchange's.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Optional, Sequence

from studio.participants import http, prompt, reading
from studio.providers.base import ProviderUnavailable, canonical_body, valid_deadline, verified_body
from studio.types import ProviderRequest, RawExchange

MAX_TOOL_CALLS = 64  # tool calls one answer may ask for at once; more are not answered and the loop fails
LOOP_USAGE_BASIS = 'provider_reported_tokens_summed_over_exchanges'
TOOL_LIMIT = 'the tool-call limit was reached'
TOO_LARGE = 'the result is too large; ask for fewer codes'
UNKNOWN_TOOL = ('CPT Studio has no tool by that name; its tools are '
                + ' and '.join(tool['name'] for tool in prompt.TOOLS) + '.')
NOT_JSON = 'The arguments are not valid JSON.'
NOT_AN_OBJECT = 'The arguments are not a JSON object.'
TOOL_FAILED = 'CPT Studio could not run this tool call.'
_TOOLS = {tool['name']: tool for tool in prompt.TOOLS}
_CALL_ID = re.compile(r'[\x21-\x7e]{1,120}')  # fits ToolCall.call_id
_TOOL_CHARS = 40  # ToolCall.tool


@dataclass(frozen=True)
class Call:
    """One tool call an answer asks for, as the vendor module read it."""
    call_id: object  # as given; the loop answers only a visible-ASCII id of at most 120 characters
    name: object  # as given
    arguments: object  # the parsed object, or what was given when it is not one
    arguments_error: str = ''  # why the arguments are not a usable object ('' when they are)


@dataclass(frozen=True)
class Turn:
    """What one answer asks for: ``calls`` () for a final answer. ``items``: what the next request passes back exactly
    as returned (the Responses API's output items, the Messages API's content blocks)."""
    calls: tuple = ()
    items: tuple = ()


FINAL = Turn()


@dataclass(frozen=True)
class ToolCallRecord:
    """A tool call as CPT Studio executed it (models.ToolCall): ``result`` is exactly what the participant was given
    (its canonical JSON is what ``result_sha256`` hashes) and ``refs`` every reference that result returned."""
    call_id: str
    tool: str  # the tool's name; '' when the name asked for is not a string of 1 to 40 characters
    arguments: object
    result: dict
    result_sha256: str
    refs: tuple[str, ...] = ()
    executed_at: Optional[datetime] = None


@dataclass(frozen=True)
class ExchangeRecord:
    """One HTTP exchange of the loop (models.ProviderExchange): the request in stored form and its sha256, and the
    response exactly as received."""
    turn: int  # 1-based
    request_body: dict
    request_sha256: str
    outcome: str  # succeeded | failed | unknown | not_sent
    http_status: Optional[int] = None
    response_bytes: Optional[bytes] = None
    response_sha256: str = ''
    latency_ms: Optional[float] = None
    usage: dict = field(default_factory=dict)
    provider_request_id: str = ''
    response_id: str = ''
    error: str = ''
    tool_calls: tuple[ToolCallRecord, ...] = ()
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass(frozen=True)
class LoopOutcome:
    final: RawExchange
    exchanges: tuple[ExchangeRecord, ...] = ()

    @property
    def outcome(self) -> str:
        return self.final.outcome

    @property
    def refs_retrieved(self) -> frozenset:
        """Every ref this run's own tool results returned to the participant (reading.read's ``refs_retrieved``)."""
        return frozenset(ref for exchange in self.exchanges for call in exchange.tool_calls for ref in call.refs)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run(adapter, request: ProviderRequest, *, post: Callable[[int, dict, float], RawExchange],
        parse_turn: Callable[[bytes], Turn], follow_up: Callable[[dict, Turn, tuple], dict],
        execute_tool, deadline_s, longest_s: float, max_exchanges: int, max_tool_result_bytes: int,
        max_request_bytes: int, body_keys: frozenset, client_error: str = '') -> LoopOutcome:
    """The loop for ``request`` (built by ``adapter``). ``post(turn, body, deadline)`` sends one exchange of a stored
    body under http.post's discipline and never raises once it has begun to send; ``deadline_s`` is the caller's,
    never more than ``longest_s``; ``client_error``, when not '', refuses the loop before it starts."""
    model = adapter.requested_model
    if not valid_deadline(deadline_s):
        return _refused('The loop deadline must be a positive number of seconds; nothing was sent.')
    deadline = monotonic() + min(deadline_s, longest_s)
    if not callable(execute_tool):
        return _refused('No tool executor was given; nothing was sent.')
    try:
        verified_body(request, adapter, max_request_bytes)
        http.check_shape(request.body, model, body_keys)
    except ProviderUnavailable as exc:
        return _refused(str(exc))
    if client_error:
        return _refused(client_error, model)
    records, raws = [], []
    body, sha256, number = request.body, request.canonical_sha256, 0
    while True:
        number += 1
        started = _now()
        raw = _attempt(post, number, body, deadline, model)
        finished = _now()
        turn = _turn(parse_turn, raw)
        answered, end = (), None
        problem = _unanswerable(turn.calls)
        if raw.outcome != 'succeeded':
            end = _stopped(raw, number)
        elif not turn.calls:
            end = ('succeeded', '')
        elif problem:
            end = ('failed', f'The participant asked for tool calls CPT Studio cannot answer ({problem}); nothing more '
                             'was sent.')
        elif number >= max_exchanges:
            end = ('failed', f'The participant still asked for tool calls after {number} '
                             f'exchange{"s" if number != 1 else ""}, the most one run may make: {TOOL_LIMIT}. Nothing '
                             'more was sent.')
        elif monotonic() >= deadline:
            end = ('failed', "The loop's deadline passed before the participant's tool calls were answered; nothing "
                             'more was sent.')
        else:
            answered, complete = _answer(turn.calls, execute_tool, deadline, max_tool_result_bytes)
            if not complete:
                end = ('failed', "The loop's deadline passed while CPT Studio was answering the participant's tool "
                                 'calls; nothing more was sent.')
        records.append(ExchangeRecord(
            turn=number, request_body=body, request_sha256=sha256, outcome=raw.outcome, http_status=raw.http_status,
            response_bytes=raw.response_bytes, response_sha256=raw.response_sha256, latency_ms=raw.latency_ms,
            usage=raw.usage, provider_request_id=raw.provider_request_id, response_id=raw.response_id,
            error=raw.error, tool_calls=tuple(record for record, _ in answered), started_at=started,
            finished_at=finished))
        raws.append(raw)
        if end is None:
            try:
                following = follow_up(body, turn, tuple((record.call_id, output) for record, output in answered))
                http.check_shape(following, model, body_keys)
                following_sha256 = hashlib.sha256(canonical_body(following)).hexdigest()
            except Exception as exc:  # CPT Studio's own code: nothing of the next exchange has left
                end = ('failed', f'CPT Studio could not build exchange {number + 1} ({type(exc).__name__}); nothing '
                                 'more was sent.')
            else:
                body, sha256 = following, following_sha256
        if end is not None:
            return LoopOutcome(final=_final(raws, *end), exchanges=tuple(records))


def _refused(error: str, requested_model: str = '') -> LoopOutcome:
    return LoopOutcome(final=http.not_sent(error, requested_model), exchanges=())


def _attempt(post, number: int, body: dict, deadline: float, model: str) -> RawExchange:
    try:
        return post(number, body, deadline)
    except Exception as exc:  # the adapter's own preparation: http.post never raises, so no byte has left
        return http.not_sent(f'CPT Studio could not prepare exchange {number} ({type(exc).__name__}); nothing was '
                             'sent.', model)


def _turn(parse_turn, raw: RawExchange) -> Turn:
    if raw.outcome != 'succeeded':
        return FINAL
    try:
        turn = parse_turn(raw.response_bytes)
    except Exception:  # an answer the vendor module cannot read asks for nothing: the reader refuses it, with why
        return FINAL
    return turn if isinstance(turn, Turn) else FINAL


def _stopped(raw: RawExchange, number: int) -> tuple[str, str]:
    """(outcome, error) of a loop whose exchange ``number`` did not succeed."""
    if raw.outcome == 'not_sent':
        if number == 1:
            return 'not_sent', raw.error
        return 'failed', (f'The tool loop stopped at exchange {number}, which was not sent: {raw.error} The earlier '
                          'exchanges were sent, so this run failed.')
    if number == 1:
        return raw.outcome, raw.error
    return raw.outcome, f'The tool loop stopped at exchange {number}: {raw.error}'


def _unanswerable(calls: tuple) -> str:
    """Why CPT Studio cannot answer these calls (each needs its own usable id), or ''."""
    if not calls:
        return ''
    if len(calls) > MAX_TOOL_CALLS:
        return f'{len(calls):,} calls at once, more than the {MAX_TOOL_CALLS} one answer may ask for'
    ids = [call.call_id for call in calls]
    if not all(isinstance(item, str) and _CALL_ID.fullmatch(item) for item in ids):
        return 'a call has no usable call id'
    if len(set(ids)) != len(ids):
        return 'two calls share one call id'
    return ''


def _answer(calls: tuple, execute_tool, deadline: float, max_bytes: int) -> tuple[tuple, bool]:
    """((ToolCallRecord, output) of each call answered, whether every call was answered before the deadline)."""
    answered = []
    for call in calls:
        if monotonic() >= deadline:
            return tuple(answered), False
        answered.append(_execute(call, execute_tool, max_bytes))
    return tuple(answered), True


def _execute(call: Call, execute_tool, max_bytes: int) -> tuple[ToolCallRecord, str]:
    executed_at = _now()
    tool = _TOOLS.get(call.name) if isinstance(call.name, str) else None
    refs = ()
    if tool is None:
        result = {'error': UNKNOWN_TOOL}
    elif call.arguments_error:
        result = {'error': call.arguments_error}
    elif reading.schema_error(call.arguments, tool['parameters'], 'the arguments'):
        result = {'error': _misfit(tool)}
    else:
        result, refs = _run(execute_tool, call.name, call.arguments)
    encoded = _encoded(result)
    if encoded is None:
        result, refs, encoded = {'error': TOOL_FAILED}, (), _encoded({'error': TOOL_FAILED})
    elif len(encoded) > max_bytes:
        result, refs, encoded = {'error': TOO_LARGE}, (), _encoded({'error': TOO_LARGE})
    label = call.name if isinstance(call.name, str) and 0 < len(call.name) <= _TOOL_CHARS else ''
    return (ToolCallRecord(call_id=call.call_id, tool=label, arguments=call.arguments, result=json.loads(encoded),
                           result_sha256=hashlib.sha256(encoded).hexdigest(), refs=refs, executed_at=executed_at),
            encoded.decode('utf-8'))


def _run(execute_tool, name: str, arguments: dict) -> tuple[dict, tuple]:
    """The executor's (result, refs), or the error result when it raises or returns anything but (dict, [str])."""
    failed = ({'error': TOOL_FAILED}, ())
    try:
        returned = execute_tool(name, copy.deepcopy(arguments))
    except Exception:
        return failed
    if not isinstance(returned, (tuple, list)) or len(returned) != 2:
        return failed
    result, refs = returned
    if not isinstance(result, dict) or not isinstance(refs, (list, tuple)) or not all(
            isinstance(ref, str) for ref in refs) or _encoded(list(refs)) is None:
        return failed
    return result, tuple(refs)


def _encoded(value) -> Optional[bytes]:
    """The canonical JSON a tool result is sent as, or None when it is not JSON data PostgreSQL can store (NaN or
    Infinity, NUL, lone surrogates, an object that is not JSON). What is recorded is this JSON parsed back, so the
    record is exactly what the participant was given."""
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                             allow_nan=False).encode('utf-8')
        reading.strict_json(encoded)  # refuses NUL and lone surrogates, as every stored answer is
    except (TypeError, ValueError, RecursionError):
        return None
    return encoded


def _misfit(tool: dict) -> str:
    parameters = tool['parameters']
    choices = [f'{name} is one of {", ".join(schema["enum"])}' for name, schema in parameters['properties'].items()
               if 'enum' in schema]
    return (f'The arguments do not fit {tool["name"]}, which takes exactly these fields: '
            f'{", ".join(parameters["required"])}' + (f' ({"; ".join(choices)})' if choices else '') + '.')


def _final(raws: list, outcome: str, error: str) -> RawExchange:
    last = raws[-1]
    usage, basis = _usage(raws)
    latencies = [raw.latency_ms for raw in raws if raw.latency_ms is not None]
    return RawExchange(outcome=outcome, sent=any(raw.sent for raw in raws), http_status=last.http_status,
                       response_bytes=last.response_bytes, response_sha256=last.response_sha256,
                       latency_ms=round(sum(latencies), 3) if latencies else None, usage=usage, usage_basis=basis,
                       provider_request_id=last.provider_request_id, error=error,
                       endpoint=next((raw.endpoint for raw in raws if raw.endpoint), ''),
                       requested_model=next((raw.requested_model for raw in reversed(raws) if raw.requested_model), ''),
                       returned_model=last.returned_model, response_id=last.response_id)


def _usage(raws: list) -> tuple[dict, str]:
    if len(raws) == 1:
        return raws[0].usage, raws[0].usage_basis
    reported = [raw.usage for raw in raws if raw.usage]
    if reported:
        return summed_usage(reported), LOOP_USAGE_BASIS
    bases = {raw.usage_basis for raw in raws}
    return {}, bases.pop() if len(bases) == 1 else ''


_UNSUMMABLE = object()


def summed_usage(usages: Sequence[dict]) -> dict:
    """Usage summed over exchanges, key by key in the order keys first appear: a whole-number count (an int that is not
    a bool) is added up, a nested object is summed the same way, and any other value is kept only where every exchange
    stating it states the same one (a service tier, say). Each exchange keeps its own usage exactly as reported."""
    keys = []
    for usage in usages:
        keys.extend(key for key in usage if key not in keys)
    summed = {}
    for key in keys:
        value = _merged([usage[key] for usage in usages if key in usage])
        if value is not _UNSUMMABLE:
            summed[key] = value
    return summed


def _merged(values: list):
    if all(type(value) is int for value in values):
        return sum(values)
    if all(isinstance(value, dict) for value in values):
        return summed_usage(values)
    first = values[0]
    if all(type(value) is type(first) and value == first for value in values):
        return copy.deepcopy(first)
    return _UNSUMMABLE
