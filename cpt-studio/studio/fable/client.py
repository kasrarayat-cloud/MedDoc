"""One coding request and its outcome (BUILD-SPEC 4.1), through Anthropic's official SDK (anthropic==2.11.0).

The request streams the final message (``client.beta.messages.stream(...)`` then ``get_final_message()``) from
claude-fable-5-2 at max_tokens 96,000 and the configured effort, with the server-side fallbacks in their ``default``
form. The SDK client retries nothing (max_retries=0: no paid request is ever sent again automatically) and its timeout
is anthropic.Timeout (the SDK's transport is httpx2; httpx is never imported).

The outcome of one send:
- a final message: ``succeeded``, or ``failed`` with stop reason ``refusal`` (DECLINED: the whole fallback chain
  declined) or ``max_tokens`` (TOO_LONG); a message served by a fallback model (a ``fallback_message`` entry in
  usage.iterations) is recorded as such (``fallback``) and read like any other;
- an HTTP error, or an error event in the stream (any status): ``failed`` with the status and the error type - an
  account refusal sets a hold (HOLD), a rate limit or an overload is BUSY, the API's refusal of the document DOCUMENT;
- a timeout, a lost connection or anything else once the request has started, or a stream that ended before its
  message did: ``unknown`` - it may have reached the vendor and been billed;
- nothing sent (the credentials file refused, no recording): ``not_sent``, UNAVAILABLE.

Modes (settings.CODING_MODE): ``live`` calls the API with the key read from settings.ANTHROPIC_CREDENTIALS_FILE at send
time (never logged, stored or put in a message); ``replay`` reads a recorded final message from
settings.CODING_REPLAY_DIR/<request sha256>.json and calls nothing; ``disabled`` (the default) has no coder.

The spend check's input (BUILD-SPEC 3.2, FIX-SPEC 4): live, a request's input tokens are counted before it is sent by
the API's free token count (``client.beta.messages.count_tokens`` with the same model, system, messages, output_config
and betas; nothing is generated or billed, and the SDK client retries nothing), LiveCoder.count_input_tokens; when the
count fails for any reason it is None and nothing is sent (studio.jobs fails the round busy, for a human retry). A
request may bill every attempt it makes: the requested model's and, with server-side fallbacks, each fallback's
(Request.attempts; the ``default`` form retries a declined request once, on the model recommended for its refusal
category), and the spend check counts them all.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import anthropic
from django.conf import settings

from . import BUSY, DECLINED, DOCUMENT, FAILED, HOLD, TOO_LONG, UNAVAILABLE, UNKNOWN
from . import credentials as fable_credentials

log = logging.getLogger(__name__)

MODEL = 'claude-fable-5-2'
MAX_TOKENS = 96_000
BETAS = ('server-side-fallback-2026-07-01',)
FALLBACKS = 'default'
BASE_URL = 'https://api.anthropic.com'
ENDPOINT = f'{BASE_URL}/v1/messages'
WORKSPACE_HEADER = 'anthropic-workspace-id'
CONNECT_SECONDS, WRITE_SECONDS, POOL_SECONDS = 20, 120, 20
COUNT_READ_SECONDS = 60  # the token count's own read timeout: it answers with a number, not a stream
COUNT_KEYS = ('model', 'system', 'messages', 'output_config', 'betas')  # what count_tokens takes of a request
LIVE, REPLAY, DISABLED = 'live', 'replay', 'disabled'
SUCCEEDED_STATE, FAILED_STATE, UNKNOWN_STATE, NOT_SENT_STATE = 'succeeded', 'failed', 'unknown', 'not_sent'
FINISHED_STOPS = ('end_turn', 'stop_sequence')
TOO_LONG_STOPS = ('max_tokens', 'model_context_window_exceeded')
# InterpreterHold.reason of an account refusal (3.3): 401, 402, 403 and 404 (whatever the body), the account error
# types under any other status, and a 429 that is not a rate limit (a spend or quota limit).
AUTH, PERMISSION, QUOTA, REFUSED = 'auth', 'permission', 'quota', 'refused'
HOLD_STATUS = {401: AUTH, 402: QUOTA, 403: PERMISSION, 404: REFUSED}
HOLD_TYPE = {'authentication_error': AUTH, 'permission_error': PERMISSION, 'billing_error': QUOTA}
RATE_LIMIT_TYPE, OVERLOADED_TYPE = 'rate_limit_error', 'overloaded_error'
DOCUMENT_TYPES = ('invalid_request_error', 'request_too_large')


def canonical(value: Any) -> bytes:
    """The exact bytes a request or an answer is hashed and stored as."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


@dataclass(frozen=True)
class Request:
    params: dict  # the keyword arguments of client.beta.messages.stream, the document's data included
    stored: dict  # the same with the document's base64 replaced (ProviderRun.request_body)
    sha256: str  # of canonical(stored): the request's identity, and its replay key
    attempts: int  # the attempts one send of it may bill: the requested model's and each fallback's (FIX-SPEC 4)


def fallback_attempts(fallbacks) -> int:
    """How many attempts the server-side ``fallbacks`` parameter may add after the requested model's own: the
    ``default`` form retries a declined request once, on the model recommended for its refusal category
    (refusals-and-fallback: "for categories with no recommended fallback, the refusal stands"); a list tries each model
    it names in turn; none adds none. ValueError for anything else, so a new form is counted before it is sent."""
    if fallbacks is None:
        return 0
    if fallbacks == 'default':
        return 1
    if isinstance(fallbacks, (list, tuple)):
        return len(fallbacks)
    raise ValueError(f'{fallbacks!r} is not a fallbacks value the spend check can count')


def build_request(*, system: str, document, instruction: str, effort: str) -> Request:
    """The request for one read of ``document`` (studio.fable.document.Document)."""
    def body(block):
        return {'model': MODEL, 'max_tokens': MAX_TOKENS, 'system': system,
                'messages': [{'role': 'user', 'content': [block, {'type': 'text', 'text': instruction}]}],
                'output_config': {'effort': effort}, 'betas': list(BETAS), 'fallbacks': FALLBACKS}
    stored = body(document.stored_block)
    return Request(params=body(document.block), stored=stored, sha256=hashlib.sha256(canonical(stored)).hexdigest(),
                   attempts=1 + fallback_attempts(FALLBACKS))


def count_params(request: Request) -> dict:
    """The token count's keyword arguments for ``request``: its model, system, messages (the document included),
    output_config and betas - count_tokens takes no max_tokens and no fallbacks."""
    return {key: request.params[key] for key in COUNT_KEYS if key in request.params}


@dataclass(frozen=True)
class Outcome:
    state: str  # succeeded | failed | unknown | not_sent (ProviderRun's)
    sent: bool
    failure_kind: str = ''  # studio.fable's kinds; '' when succeeded
    http_status: Optional[int] = None
    error_type: str = ''  # the API's error type, or the refusal category
    hold: str = ''  # the InterpreterHold reason this outcome sets, or ''
    message: Optional[dict] = None  # the final message as JSON
    response_bytes: bytes = b''  # the final message JSON, or the error body, as stored
    request_id: str = ''
    returned_model: str = ''
    response_id: str = ''
    usage: dict = field(default_factory=dict)
    fallback: bool = False  # served by a fallback model
    stop_reason: str = ''
    latency_ms: Optional[float] = None
    error: str = ''  # for the operator; never a credential


def message_outcome(message: dict, *, sent: bool, latency_ms: Optional[float] = None, request_id: str = '') -> Outcome:
    """The outcome of a final message (``sent`` False for a replay, which called nothing)."""
    usage = message.get('usage') if isinstance(message.get('usage'), dict) else {}
    iterations = usage.get('iterations') if isinstance(usage.get('iterations'), list) else []
    fallback = any(isinstance(item, dict) and item.get('type') == 'fallback_message' for item in iterations)
    stop = message.get('stop_reason')
    common = dict(sent=sent, http_status=200 if sent else None, message=message, response_bytes=canonical(message),
                  request_id=(request_id or '')[:120], returned_model=str(message.get('model') or '')[:100],
                  response_id=str(message.get('id') or '')[:140], usage=usage, fallback=fallback,
                  stop_reason=stop if isinstance(stop, str) else '', latency_ms=latency_ms)
    if stop in FINISHED_STOPS:
        return Outcome(state=SUCCEEDED_STATE, **common)
    if stop == 'refusal':
        details = message.get('stop_details') if isinstance(message.get('stop_details'), dict) else {}
        category = details.get('category') if isinstance(details.get('category'), str) else ''
        return Outcome(state=FAILED_STATE, failure_kind=DECLINED, error_type=category,
                       error=f'The answer was declined (stop reason refusal{", " + category if category else ""}).',
                       **common)
    if stop in TOO_LONG_STOPS:
        return Outcome(state=FAILED_STATE, failure_kind=TOO_LONG,
                       error=f'The answer stopped at its output limit (stop reason {stop}).', **common)
    if stop is None and sent:
        return Outcome(state=UNKNOWN_STATE, failure_kind=UNKNOWN,
                       error='The stream ended before the message did; what the vendor billed is not known.', **common)
    return Outcome(state=FAILED_STATE, failure_kind=FAILED,
                   error=f'The answer ended with stop reason {stop!r}, which the coding step does not read.', **common)


def hold_reason(status: Optional[int], error_type: str) -> str:
    """The hold an error sets (3.3), or ''."""
    if status in HOLD_STATUS:
        return HOLD_STATUS[status]
    if error_type in HOLD_TYPE:
        return HOLD_TYPE[error_type]
    if status == 429 and error_type != RATE_LIMIT_TYPE:
        return QUOTA
    return ''


def status_outcome(exc: anthropic.APIStatusError, *, latency_ms: Optional[float] = None,
                   request_id: str = '') -> Outcome:
    """The outcome of an HTTP error, or of an error event inside the stream (its status is then the stream's)."""
    status = exc.status_code
    error_type = exc.type if isinstance(exc.type, str) else ''
    hold = hold_reason(status, error_type)
    if hold:
        kind = HOLD
    elif error_type in (RATE_LIMIT_TYPE, OVERLOADED_TYPE) or status in (429, 529):
        kind = BUSY
    elif status == 413 or (status == 400 and error_type in DOCUMENT_TYPES):
        kind = DOCUMENT
    else:
        kind = FAILED
    body = exc.body
    data = canonical(body) if isinstance(body, (dict, list)) else (str(body).encode('utf-8') if body else b'')
    detail = exc.api_message if isinstance(exc.api_message, str) else ''
    error = f'{error_type or "error"} (HTTP {status})' + (f': {detail[:300]}' if detail else '')
    return Outcome(state=FAILED_STATE, sent=True, failure_kind=kind, http_status=status, error_type=error_type,
                   hold=hold, response_bytes=data, request_id=(exc.request_id or request_id or '')[:120],
                   latency_ms=latency_ms, error=error)


def unknown_outcome(exc: BaseException, *, sent: bool = True, latency_ms: Optional[float] = None,
                    request_id: str = '') -> Outcome:
    """The outcome of a send that ended in ``exc`` after it started: unknown (or, when it could have sent nothing -
    a replay - not sent)."""
    if not sent:
        return _not_sent(f'{type(exc).__name__}: the replay failed; nothing was sent.')
    return Outcome(state=UNKNOWN_STATE, sent=True, failure_kind=UNKNOWN, latency_ms=latency_ms,
                   request_id=(request_id or '')[:120],
                   error=f'{type(exc).__name__}: the request may have reached the vendor; its outcome is not known.')


def _not_sent(error: str) -> Outcome:
    return Outcome(state=NOT_SENT_STATE, sent=False, failure_kind=UNAVAILABLE, error=error)


class LiveCoder:
    """The live API. ``sdk``: the SDK client class (tests pass a fake with its constructor and stream shape)."""
    mode, endpoint = LIVE, ENDPOINT

    def __init__(self, *, credentials_file: Optional[str] = None, read_timeout: Optional[float] = None,
                 sdk: Optional[Callable[..., Any]] = None):
        self.credentials_file = credentials_file
        self.read_timeout = read_timeout
        self.sdk = sdk or anthropic.Anthropic

    def client(self):
        """A fresh SDK client for one send, the key read now; CredentialsError when the file is refused."""
        path = self.credentials_file if self.credentials_file is not None else settings.ANTHROPIC_CREDENTIALS_FILE
        found = fable_credentials.load(path)
        read = self.read_timeout if self.read_timeout is not None else settings.CODING_READ_TIMEOUT_SECONDS
        return self.sdk(api_key=found.api_key, base_url=BASE_URL, max_retries=0,
                        timeout=anthropic.Timeout(connect=CONNECT_SECONDS, read=read, write=WRITE_SECONDS,
                                                  pool=POOL_SECONDS),
                        default_headers={WORKSPACE_HEADER: found.workspace_id} if found.workspace_id else None)

    def count_input_tokens(self, request: Request) -> Optional[int]:
        """The input tokens of ``request`` by the API's free token count (POST /v1/messages/count_tokens), or None when
        it cannot be counted - the credentials refused, an error of any kind, an answer that is not a whole positive
        number - in which case nothing is sent (FIX-SPEC 4). Never raises; logs only the error's type."""
        try:
            sdk = self.client()
        except Exception as exc:  # noqa: BLE001 - the credentials file refused or the client not made: nothing is sent
            log.warning('the token count of a coding request was not made (%s); nothing is sent', type(exc).__name__)
            return None
        try:
            counted = sdk.beta.messages.count_tokens(
                **count_params(request),
                timeout=anthropic.Timeout(connect=CONNECT_SECONDS, read=COUNT_READ_SECONDS, write=WRITE_SECONDS,
                                          pool=POOL_SECONDS))
        except Exception as exc:  # noqa: BLE001 - a count that failed bills nothing; the send is not made
            log.warning('the token count of a coding request failed (%s); nothing is sent', type(exc).__name__)
            return None
        finally:
            closing = getattr(sdk, 'close', None)
            if callable(closing):
                try:
                    closing()
                except Exception:  # noqa: BLE001 - the count is already in hand
                    log.warning('the SDK client could not be closed')
        tokens = getattr(counted, 'input_tokens', None)
        if type(tokens) is int and tokens > 0:
            return tokens
        log.warning('the token count of a coding request answered no whole number of tokens; nothing is sent')
        return None

    def send(self, request: Request) -> Outcome:
        try:
            sdk = self.client()
        except fable_credentials.CredentialsError as exc:
            return _not_sent(str(exc))
        except Exception as exc:  # noqa: BLE001 - nothing was sent; the type alone is recorded
            return _not_sent(f'The SDK client could not be made ({type(exc).__name__}); nothing was sent.')
        started, request_id = time.monotonic(), ''

        def latency():
            return round((time.monotonic() - started) * 1000, 1)
        try:
            with sdk.beta.messages.stream(**request.params) as stream:
                request_id = getattr(stream, 'request_id', '') or ''
                message = stream.get_final_message()
            data = message.model_dump(mode='json')
        except anthropic.APIStatusError as exc:
            return status_outcome(exc, latency_ms=latency(), request_id=request_id)
        except anthropic.APIConnectionError as exc:  # a timeout included
            return unknown_outcome(exc, latency_ms=latency(), request_id=request_id)
        except Exception as exc:  # noqa: BLE001 - the request had started: it may have reached the vendor
            log.warning('a coding request ended with %s; its outcome is unknown', type(exc).__name__)
            return unknown_outcome(exc, latency_ms=latency(), request_id=request_id)
        finally:
            closing = getattr(sdk, 'close', None)
            if callable(closing):
                try:
                    closing()
                except Exception:  # noqa: BLE001 - the answer is already in hand
                    log.warning('the SDK client could not be closed')
        if not isinstance(data, dict):
            return unknown_outcome(TypeError('the final message is not an object'), latency_ms=latency(),
                                   request_id=request_id)
        return message_outcome(data, sent=True, latency_ms=latency(), request_id=request_id)


class ReplayCoder:
    """Recorded final messages, keyed by the request's sha256; calls nothing and sends nothing."""
    mode, endpoint = REPLAY, ''

    def __init__(self, directory: str):
        self.directory = directory

    def send(self, request: Request) -> Outcome:
        if not self.directory:
            return _not_sent('No replay directory is configured; nothing was sent.')
        path = Path(self.directory) / f'{request.sha256}.json'
        try:
            message = json.loads(path.read_bytes())
        except FileNotFoundError:
            return _not_sent('No recorded answer exists for this request; nothing was sent.')
        except (OSError, ValueError):
            return _not_sent('The recorded answer for this request could not be read; nothing was sent.')
        if not isinstance(message, dict):
            return _not_sent('The recorded answer for this request is not a message; nothing was sent.')
        return message_outcome(message, sent=False)


def coder(mode: Optional[str] = None):
    """The coder of ``mode`` (settings.CODING_MODE by default), or None when coding is disabled."""
    mode = mode or settings.CODING_MODE
    if mode == LIVE:
        return LiveCoder()
    if mode == REPLAY:
        return ReplayCoder(settings.CODING_REPLAY_DIR)
    return None
