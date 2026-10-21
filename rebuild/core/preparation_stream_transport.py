"""Prospective preparation SSE with an absolute deadline and private diagnostics.

Partial events are bounded, sanitized diagnostic projections, never a response
or an approval. The ordinary complete response remains independently retained.
"""
import asyncio
from collections import deque
import hashlib
import json
import time
import httpx

from asgiref.sync import async_to_sync, sync_to_async

from . import preparation_error_evidence as diagnostics


CONFIG_KEY = 'word_preparation_provider_transport'
TRANSPORT = 'anthropic-sse-wall-v1'
CONTRACT = 'preparation-provider-stream-evidence-v1'
POINTER_KEY = 'private_stream_evidence'
EVENT_WINDOW = 16
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RAW_EVENTS = frozenset(('message_start', 'message_delta', 'message_stop',
    'content_block_start', 'content_block_delta', 'content_block_stop'))
CUMULATIVE_COUNTERS = ('input_tokens', 'output_tokens',
    'cache_read_input_tokens', 'cache_creation_input_tokens')
OBSERVATION_CONTRACT = 'preparation-stream-observations-v1'
STOP_REASONS = frozenset(('end_turn', 'max_tokens', 'stop_sequence', 'tool_use',
    'pause_turn', 'refusal', 'model_context_window_exceeded'))


class PreparationStreamError(Exception):
    def __init__(self, reason, request_id=''):
        super().__init__('The bounded preparation stream did not complete.')
        self.local_reason = reason
        self.request_id = request_id


class CompleteStreamObservationError(Exception):
    """A complete provider message exists, but persistence/deadline failed."""
    def __init__(self, evidence):
        super().__init__('Complete preparation evidence could not be adopted.')
        self.complete_evidence = evidence


class TerminalStreamError(PreparationStreamError):
    def __init__(self, message, trace):
        super().__init__('deadline_or_close_after_message_stop', trace['provider_request_id'])
        self.message = message
        self.trace = trace


class _DeadlineBody(httpx.AsyncByteStream):
    """Check even ping-only chunks which the SDK deliberately does not yield."""
    def __init__(self, body, deadline):
        self.body = body
        self.deadline = deadline

    async def __aiter__(self):
        async for chunk in self.body:
            if time.monotonic() >= self.deadline:
                raise PreparationStreamError('deadline')
            await asyncio.sleep(0)  # Buffered chunks must not starve timeout cancellation.
            yield chunk

    async def aclose(self):
        await self.body.aclose()


def enabled(config):
    if config is None or CONFIG_KEY not in config:
        return False
    if (type(config[CONFIG_KEY]) is not str or config[CONFIG_KEY] != TRANSPORT
            or config.get('mode') != 'live' or config.get('provider') != 'anthropic'):
        raise ValueError('Unsupported explicit preparation provider transport.')
    return True


def validate_evidence(config, evidence):
    marked = enabled(config)
    present = any(k in evidence for k in ('provider_transport', 'stream_complete', 'stream_observation'))
    if marked:
        if (evidence.get('provider_transport') != TRANSPORT
                or evidence.get('stream_complete') is not True):
            raise ValueError('The complete preparation stream binding is missing.')
        observation = evidence.get('stream_observation')
        if (type(observation) is not dict or set(observation) != {
                'contract', 'terminal', 'cumulative_usage', 'terminal_declarations', 'final_delta_fields'}
                or observation['contract'] != OBSERVATION_CONTRACT
                or type(observation['terminal_declarations']) is not int
                or observation['terminal_declarations'] < 1):
            raise ValueError('The observed preparation stream contract is invalid.')
        terminal = observation['terminal']; usage = observation['cumulative_usage']
        fields = observation['final_delta_fields']
        if (type(terminal) is not dict or set(terminal) != {'stop_reason', 'stop_sequence'}
                or type(terminal['stop_reason']) is not str or terminal['stop_reason'] not in STOP_REASONS
                or not (terminal['stop_sequence'] is None or type(terminal['stop_sequence']) is str)
                or type(usage) is not dict or not {'input_tokens', 'output_tokens'} <= set(usage)
                or not set(usage) <= set(CUMULATIVE_COUNTERS)
                or any(type(value) is not int or value < 0 for value in usage.values())
                or type(fields) is not list or any(type(key) is not str for key in fields)
                or fields != sorted(set(fields))
                or not set(fields) <= {'stop_reason', 'stop_sequence'}):
            raise ValueError('The observed preparation stream fields are invalid.')
        raw = evidence.get('response')
        if type(raw) is not dict or type(raw.get('usage')) is not dict:
            raise ValueError('The original SDK snapshot is missing.')
        for key in ('stop_reason', 'stop_sequence'):
            # The SDK resets an omitted stop field to None. Preserve that
            # original snapshot; only the separately recorded observation can
            # carry the earlier explicit terminal declaration through replay.
            expected = terminal[key] if key in fields else None
            if raw.get(key) != expected:
                raise ValueError('The original SDK terminal snapshot differs.')
        if any(type(raw['usage'].get(key)) is not int or raw['usage'][key] != value for key, value in usage.items()):
            raise ValueError('The original SDK usage snapshot differs.')
        return terminal['stop_reason']
    elif present:
        raise ValueError('An unmarked preparation cannot adopt streaming evidence.')


def _record_usage(usage, observed, request_id):
    # The SDK overwrites its snapshot with each cumulative observation. Check
    # the observations first: a later smaller value cannot erase billed usage.
    # Optional missing/None fields mean no update, never a reset to zero.
    for key in CUMULATIVE_COUNTERS:
        value = usage.get(key)
        if value is None:
            continue
        if (type(value) is not int or value < 0
                or key in observed and value < observed[key]):
            raise PreparationStreamError('contradictory_usage', request_id)
        observed[key] = value


class _Observations:
    def __init__(self):
        self.usage = {}; self.terminal = None; self.declarations = 0; self.final_fields = []

    def observe(self, kind, value):
        if type(value) is not dict or value.get('type', kind) != kind:
            raise PreparationStreamError('malformed_stream')
        usage = (value.get('message', {}).get('usage') if kind == 'message_start' else value.get('usage'))
        if type(usage) is not dict:
            raise PreparationStreamError('unestablished_usage')
        required = ('input_tokens', 'output_tokens') if kind == 'message_start' else ('output_tokens',)
        if any(type(usage.get(key)) is not int or usage[key] < 0 for key in required):
            raise PreparationStreamError('unestablished_usage')
        _record_usage(usage, self.usage, '')
        if kind == 'message_start':return
        delta = value.get('delta')
        if type(delta) is not dict:raise PreparationStreamError('malformed_stream')
        self.final_fields = sorted(set(delta) & {'stop_reason', 'stop_sequence'})
        if 'stop_reason' in delta:
            reason = delta['stop_reason']
            if reason is None:
                # Explicit null after a declaration is a retraction, unlike an
                # omitted field on a documented usage-only update.
                if self.terminal is not None:raise PreparationStreamError('contradictory_terminal')
            else:
                if type(reason) is not str or reason not in STOP_REASONS:
                    raise PreparationStreamError('malformed_stream')
                sequence = delta.get('stop_sequence', self.terminal[1] if self.terminal else None)
                if sequence is not None and type(sequence) is not str:
                    raise PreparationStreamError('malformed_stream')
                current = (reason, sequence)
                if self.terminal is not None and current != self.terminal:
                    raise PreparationStreamError('contradictory_terminal')
                self.terminal = current; self.declarations += 1
        if ('stop_sequence' in delta and self.terminal is not None
                and delta['stop_sequence'] != self.terminal[1]):
            raise PreparationStreamError('contradictory_terminal')

    def document(self):
        return {'contract': OBSERVATION_CONTRACT,
            'terminal': dict(zip(('stop_reason', 'stop_sequence'), self.terminal)) if self.terminal else None,
            'cumulative_usage': dict(self.usage), 'terminal_declarations': self.declarations,
            'final_delta_fields': self.final_fields}


class _ObservedEvent:
    """Validate only when the SDK dispatches JSON, before its type coercion.

    The SDK selects its own recognized names. Ignored future events and pings
    remain ignored, while every dispatched alias must agree with data.type.
    """
    def __init__(self, event, observations):
        self.original = event; self.observations = observations

    def __getattr__(self, key):
        return getattr(self.original, key)

    def json(self):
        if self.event == 'error':
            return self.original.json()  # Preserve the existing SDK error/sanitizer path.
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:raise PreparationStreamError('ambiguous_usage_json')
                result[key] = value
            return result
        def nonfinite(value):raise PreparationStreamError('ambiguous_usage_json')
        value = json.loads(self.data, object_pairs_hook=unique, parse_constant=nonfinite)
        if type(value) is not dict or value.get('type', self.event) != self.event:
            raise PreparationStreamError('event_type_mismatch')
        if self.event in ('message_start', 'message_delta'):
            self.observations.observe(self.event, value)
        return value


class _ObservedDecoder:
    """One installed-SDK client seam; original SSE names/data remain untouched."""
    def __init__(self, decoder, observations):
        self.decoder = decoder; self.observations = observations

    async def aiter_bytes(self, iterator):
        async for event in self.decoder.aiter_bytes(iterator):
            yield _ObservedEvent(event, self.observations)


class _Trace:
    def __init__(self):
        self.started = time.monotonic()
        self.request_id = ''
        self.status = None
        self.count = 0
        self.first = []
        self.last = deque(maxlen=EVENT_WINDOW)
        self.digest = hashlib.sha256()
        self.complete = False
        self.reason = 'unestablished'
        self.observation = None

    def event(self, event):
        # Derived SDK text events duplicate raw deltas; message_stop's message
        # snapshot is not the raw stop event. Preserve its actual type only.
        value = event.model_dump(mode='json')
        if event.type == 'message_stop':
            value = {'type': 'message_stop'}
        elif event.type == 'content_block_stop':
            value = {'type': 'content_block_stop', 'index': event.index}
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode()
        self.digest.update(len(raw).to_bytes(8, 'big') + raw)
        row = {'type': event.type, 'bytes': len(raw),
               'sha256': hashlib.sha256(raw).hexdigest()}
        self.count += 1
        if len(self.first) < EVENT_WINDOW:
            self.first.append(row)
        else:
            self.last.append(row)

    def document(self):
        return {'contract': CONTRACT, 'transport': TRANSPORT,
            'stream_http_status': self.status, 'provider_request_id': self.request_id,
            'elapsed_ms': max(0, int((time.monotonic() - self.started) * 1000)),
            'stream_complete': self.complete, 'local_transport_reason': self.reason,
            'complete_observation': self.observation,
            'event_count': self.count, 'event_chain_sha256': self.digest.hexdigest(),
            'first_events': self.first, 'last_events': list(self.last),
            'events_omitted': self.count - len(self.first) - len(self.last),
            'sanitized': True, 'exact_raw_response': False,
            'partial_events_are_not_an_adoptable_response': True}


async def _observe(observer, phase, document, pending):
    # A synchronous filesystem/ORM callback cannot be preempted. Shield its
    # task but let cancellation unwind/close HTTP immediately. The caller joins
    # pending work AFTER closure and BEFORE the receipt's failure path returns.
    task = asyncio.create_task(sync_to_async(observer, thread_sensitive=True)(phase, document))
    pending.append(task)
    try:
        return await asyncio.shield(task)
    finally:
        if task.done():pending.remove(task)


async def _complete(client, envelope, deadline, observer):
    trace = _Trace()
    started = False
    stopped = False
    delta_seen = False
    blocks = {}
    message = None
    original_error = None
    accumulated_bytes = 0
    pending = []
    timeout_scope = None
    observations = _Observations()
    original_decoder = client._make_sse_decoder
    client._make_sse_decoder = lambda: _ObservedDecoder(original_decoder(), observations)
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PreparationStreamError('deadline')
        body = dict(envelope)
        if body.pop('stream', None) is not True:
            raise PreparationStreamError('missing_stream_request_binding')
        # HTTPX timeouts remain bounded inactivity limits. This outer timeout
        # cancels the actual awaited open/read, including streams of only pings.
        timeout_scope = asyncio.timeout(remaining)
        async with timeout_scope:
            async with client:
                async with client.messages.stream(**body, timeout=remaining) as stream:
                    trace.status = stream.response.status_code
                    trace.request_id = diagnostics.public_request_id(stream.request_id)
                    if type(trace.status) is not int or trace.status != 200:
                        raise PreparationStreamError('invalid_stream_status', trace.request_id)
                    stream.response.stream = _DeadlineBody(stream.response.stream, deadline)
                    await _observe(observer, 'headers', trace.document(), pending)
                    async for event in stream:
                        if time.monotonic() >= deadline:
                            raise PreparationStreamError('deadline', trace.request_id)
                        if event.type not in RAW_EVENTS:
                            continue
                        trace.event(event)
                        # Bound individual events and accumulated content
                        # incrementally, without serializing a growing snapshot
                        # on every token. Final response size is checked once.
                        value = event.model_dump(mode='json')
                        if event.type == 'content_block_delta':
                            delta = value.get('delta', {})
                            for key, item in delta.items():
                                if key == 'type':
                                    continue
                                if isinstance(item, str):
                                    accumulated_bytes += len(json.dumps(item, ensure_ascii=False).encode()) - 2
                        elif event.type == 'content_block_start':
                            accumulated_bytes += len(json.dumps(value.get('content_block'), ensure_ascii=False).encode())
                        if (accumulated_bytes > MAX_RESPONSE_BYTES
                                or len(json.dumps(value, ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES):
                            raise PreparationStreamError('response_size_limit', trace.request_id)
                        kind = event.type
                        if kind == 'message_start':
                            if started or event.message.content or event.message.stop_reason is not None:
                                raise PreparationStreamError('malformed_stream', trace.request_id)
                            usage = event.message.usage
                            if any(type(getattr(usage, key, None)) is not int or getattr(usage, key) < 0
                                   for key in ('input_tokens', 'output_tokens')):
                                raise PreparationStreamError('unestablished_usage', trace.request_id)
                            started = True
                        elif not started or stopped:
                            raise PreparationStreamError('malformed_stream', trace.request_id)
                        elif kind == 'content_block_start':
                            index = event.index
                            if type(index) is not int or index != len(blocks) or delta_seen:
                                raise PreparationStreamError('malformed_stream', trace.request_id)
                            blocks[index] = False
                        elif kind in ('content_block_delta', 'content_block_stop'):
                            index = event.index
                            if type(index) is not int or index not in blocks or blocks[index] or delta_seen:
                                raise PreparationStreamError('malformed_stream', trace.request_id)
                            if kind == 'content_block_stop':
                                blocks[index] = True
                        elif kind == 'message_delta':
                            if (not all(blocks.values())
                                    or type(event.usage.output_tokens) is not int or event.usage.output_tokens < 0):
                                raise PreparationStreamError('malformed_stream', trace.request_id)
                            delta_seen = True
                        elif kind == 'message_stop':
                            if (not delta_seen or not all(blocks.values())
                                    or observations.terminal is None):
                                raise PreparationStreamError('malformed_stream', trace.request_id)
                            snapshot = stream.current_message_snapshot
                            expected = dict(zip(('stop_reason', 'stop_sequence'), observations.terminal))
                            if (any(getattr(snapshot, key) != (expected[key] if key in observations.final_fields else None)
                                    for key in expected)
                                    or any(getattr(snapshot.usage, key, None) != value
                                           for key, value in observations.usage.items())):
                                raise PreparationStreamError('contradictory_terminal_snapshot', trace.request_id)
                            stopped = True
                        if stopped:
                            message = stream.current_message_snapshot
                            trace.complete = True
                            trace.observation = observations.document()
                            if len(message.model_dump_json().encode()) > MAX_RESPONSE_BYTES:
                                raise PreparationStreamError('response_size_limit', trace.request_id)
                            trace.reason = 'message_stop'
                            break  # Do not wait for EOF/pings after the terminal event.
                    if not stopped:
                        raise PreparationStreamError('unexpected_eof', trace.request_id)
        if time.monotonic() >= deadline:
            raise PreparationStreamError('deadline', trace.request_id)
        return message, trace.document()
    except TimeoutError as exc:
        if not (timeout_scope is not None and timeout_scope.expired()) and time.monotonic() < deadline:
            original_error = exc
            trace.reason = 'transport_or_callback_exception'
            if message is not None:
                raise TerminalStreamError(message, trace.document()) from exc
            raise
        original_error = PreparationStreamError('deadline', trace.request_id)
        trace.reason = 'deadline'
        if message is not None:
            raise TerminalStreamError(message, trace.document()) from None
        raise original_error from None
    except BaseException as exc:
        original_error = exc
        trace.reason = (exc.local_reason if isinstance(exc, PreparationStreamError)
                        else 'cancelled' if isinstance(exc, asyncio.CancelledError)
                        else 'transport_or_callback_exception')
        if message is not None:
            raise TerminalStreamError(message, trace.document()) from exc
        raise
    finally:
        # On success the synchronous caller persists this trace with the final
        # response. On failure preserve partial diagnostics without masking the
        # actual provider/local exception or turning uncertainty into free usage.
        try:
            if not client.is_closed():
                try:await client.close()
                except BaseException:
                    if message is not None:
                        raise TerminalStreamError(message, trace.document()) from None
                    if original_error is None:raise
        finally:
            client._make_sse_decoder = original_decoder
            for task in pending:
                try:await task
                except BaseException:pass
            if original_error is not None:
                try:
                    await _observe(observer, 'partial', trace.document(), [])
                except BaseException:
                    pass


def complete(client, envelope, deadline, observer):
    return async_to_sync(_complete)(client, envelope, deadline, observer)
