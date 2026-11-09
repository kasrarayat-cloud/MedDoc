"""The production Gemini adapter (design/FINAL.md 5.4, 6.3 and 11; design/contract.md 2.2; design/ADJUDICATION.md P-3 to
P-5; DECISIONS D11-D14): how one interpretation request is built, sent once, and its envelope read and classified.

THE REQUEST (contract 2.2; D1, D12). POST ENDPOINT - the URL names the model, gemini-4-argon, so the body carries none -
with the body interpretation.prompt.request_parts builds from the framed revision text: exactly systemInstruction,
contents and generationConfig. Nothing else is sent: no member value, filename or reading (D1), no tool, no thinking or
safety setting, and no PDF original (D12: the extracted text only). Building is pure and needs no credentials: the web
may build a request; only the worker, which mounts the key, sends one.

THE KEY (D14). It is read at send time from its protected file by participants.credentials' own loader and rules (a
regular file that is not a symlink, readable by its owner only, parsed strictly as data; GEMINI_API_KEY once, and no other
key) and travels ONLY in the x-goog-api-key header. The URL is a constant, so ProviderRun.endpoint never carries the key
(hazard 23), and no error, repr or record names it.

THE SEND. One POST under the participants' discipline (participants.http.post: no retry, no redirect, no environment
proxies or .netrc, a watched socket, capped reads, the deadline checked per chunk; not_sent only while the request
provably has not left, unknown after that, failed for a non-200 with its body kept, succeeded for a 200), with connect
10 s, read 300 s and a send deadline of 330 s that no caller's deadline can stretch (D12). ``send_loop`` is the run the
pipeline makes (jobs._send's looped branch): participants.loop.run with exactly one exchange, so the exchange is recorded
as turn 1 as a participant's are, and an orphan is settled by the same rule (jobs.may_have_reached_vendor). A member's
Stop is asked once, right before the request is sent: a Stop, or a check that cannot be made, sends nothing. Gemini is
offered no tool, so no answer is ever read as asking for one, and the pipeline's tool executor is never called.

THE ENVELOPE (FINAL 5.4; D13), checked by ``answer_text`` before interpretation.read sees anything, in this order:
strict JSON (participants.reading.strict_json); modelVersion exactly MODEL, checked first of everything the response
says, anything else refused and never read; no promptFeedback.blockReason; exactly one candidate; finishReason STOP
(MAX_TOKENS is refused as cut off, C5); no part carrying anything but text (a function call, code or file data was never
asked for). The answer text is the candidate's text parts, joined in order, without the parts marked ``thought: true``.
Each refusal is interpretation.read's Refusal at stage ``envelope``, in CPT Studio's own words: it repeats nothing the
model wrote, and it names no provider or model (D22), since the run already records both.

WHAT AN EXCHANGE RECORDS: the vendor describe hook (``describe``, given to participants.http.post through VENDOR) reads
usageMetadata (prompt, candidates, thoughts and total tokens, as reported), modelVersion as the returned model and
responseId (at most 140 characters) - participants.http.describe reads the top level and would record all three empty.
Google's response carries no request-id header, so provider_request_id stays ''.

CLASSIFICATION (``classify``; FINAL 11.1 as ADJUDICATION P-3, P-4 and P-5 amend it): what a definite outcome means for
the installation. interpretation.holds records and releases the hold this names (InterpreterHold.reason is one of
HOLD_REASONS); this module only reads the response.

Nothing here imports studio.gi, studio.validation or studio.candidates (D17), reads Django settings at import, or
touches the database. ``get_interpreter`` is the one place settings are read, at call time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Optional, Union

import requests

from studio import interpretation
from studio.interpretation import prompt, read
from studio.participants import credentials as participant_credentials
from studio.participants import http, loop, reading
from studio.providers.base import ProviderUnavailable, valid_deadline, verified_body
from studio.providers.credentials import CredentialsError
from studio.types import PageSpan, ProviderRequest, RawExchange

NAME = interpretation.PROVIDER  # ProviderRun.provider: 'gemini'
ADAPTER_VERSION = interpretation.ADAPTER_VERSION  # 'gemini-generate@cptstudio-1'
READ_VERSIONS = (ADAPTER_VERSION,)  # the adapter versions whose stored answers this module reads
MODEL = interpretation.MODEL  # 'gemini-4-argon' (D13)
ENDPOINT = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
KEY_HEADER = 'x-goog-api-key'
CREDENTIAL_KEY = 'GEMINI_API_KEY'
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 300
SEND_DEADLINE_SECONDS = 330  # settings.INTERPRETER_SEND_DEADLINE_SECONDS; below the stale-stage sweep (600 s)
# A request is the instructions, the schema and the framed text (the size bound, settings.INTERPRET_MAX_CHARS, refuses a
# long document before one is built); an answer is at most 32,768 output tokens. Both are refused over these, never cut.
DEFAULT_MAX_REQUEST_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
BODY_KEYS = frozenset(prompt.BODY_KEYS)

# --- what a response says, and what each refusal is ----------------------------------------------------------------------

STOP = 'STOP'
MAX_TOKENS = 'MAX_TOKENS'
# Fields of a response part that carry content other than text: none was asked for (D12, one exchange and text only).
CONTENT_FIELDS = frozenset({'inlineData', 'fileData', 'functionCall', 'functionResponse', 'executableCode',
                            'codeExecutionResult'})
_RESPONSE_ID = re.compile(r'[\x21-\x7e]{1,140}')  # fits ProviderRun.response_id


def describe(raw) -> tuple[dict, str, str]:
    """(usage, model, id) as a generateContent response states them - usageMetadata as reported, modelVersion and
    responseId - each {} or '' when the response states none that fits the record (participants.http.described applies
    the same rules again to whatever a hook returns). A refused request's error body states none of them. It never
    raises: what a response says never changes its outcome."""
    try:
        envelope = reading.strict_json(raw)
    except Exception:  # noqa: BLE001 - JSONRefused, or bytes that are not bytes: the body states nothing usable
        return {}, '', ''
    if not isinstance(envelope, dict):
        return {}, '', ''
    usage, model, response_id = envelope.get('usageMetadata'), envelope.get('modelVersion'), envelope.get('responseId')
    return (usage if isinstance(usage, dict) else {}, reading.recorded_model(model),
            response_id if isinstance(response_id, str) and _RESPONSE_ID.fullmatch(response_id) else '')


# Errors name the vendor as the participants' do (OpenAI, Anthropic); the run records it, and no customer surface reads a
# run's error (D22). The response carries no request-id header, so none is named.
VENDOR = http.Vendor(label='Google', request_id_header='', describe=describe)


# --- the key -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class GeminiCredentials:
    api_key: str

    def __repr__(self):
        return 'GeminiCredentials(api_key=<redacted>)'

    __str__ = __repr__


def load_gemini_credentials(path) -> GeminiCredentials:
    """The key from its protected file (D14: one line ``GEMINI_API_KEY=<key>``), by participants.credentials' own loader
    and rules, with GEMINI_API_KEY its one key: a regular file, not a symlink, readable by its owner only, at most
    32,000 bytes of UTF-8, parsed strictly as data (never sourced, interpolated or escape-decoded), the key set exactly
    once and no other key, and its value visible ASCII with no space, since it goes into a header. CredentialsError
    otherwise; no message, repr or exception chain carries the value, a line of the file or its path."""
    values = participant_credentials._load(path, 'Gemini', (CREDENTIAL_KEY,))  # the loader's own rules, one key
    return GeminiCredentials(api_key=values[CREDENTIAL_KEY])


# --- the request --------------------------------------------------------------------------------------------------------

def build_request(text: str, pages, kind: str, *, max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> ProviderRequest:
    """The interpretation request for one revision (contract 2.2; D1, D12): its text framed by prompt.framed - through
    participants.http.framed_text, so a text that cannot be framed, is empty or holds NUL raises ProviderUnavailable and
    nothing is built or sent - and the body prompt.request_parts builds from it. Pure: no settings, credentials or
    network. Refused over ``max_bytes``, never truncated. Its contexts are ``(text,)``, the revision text the answer's
    passages are located in. It takes no original file: none is sent (D12)."""
    framed = http.framed_text(text, pages, kind, prompt.framed)
    return http.finished_request(NAME, ADAPTER_VERSION, prompt.request_parts(framed), text, max_bytes=max_bytes)


NOT_BUILT = 'The request body is not one this adapter builds; nothing was sent.'
UNPINNED = ('The instructions or the response schema no longer match their pinned version, so no request of this '
            'version can be checked; nothing was sent.')


def body_problem(body) -> str:
    """'' when ``body`` is exactly a body this adapter builds: prompt.request_parts of the framed document its user turn
    carries, so its instructions, schema and generation settings are this version's byte for byte and nothing rides
    along (no model, tool, thinking or safety field, no second turn, no original, no other user text). Otherwise why
    not, in CPT Studio's words."""
    try:
        framed = body['contents'][0]['parts'][0]['text']
        if isinstance(framed, str) and body == prompt.request_parts(framed):
            return ''
    except RuntimeError:  # prompt.check_pins: a changed prompt or schema with no new version
        return UNPINNED
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return NOT_BUILT


# --- the interpreters ---------------------------------------------------------------------------------------------------

INVALID_DEADLINE = 'The send deadline must be a positive number of seconds; nothing was sent.'
NOT_CALLABLE = 'The Stop check given is not callable; nothing was sent.'
NOT_CONTINUED = ('Nothing was sent: an interpretation is one exchange, so there is no stopped run to continue, and none '
                 'is sent again.')
STOPPED_BEFORE = 'Stopped by a workspace member before the request was sent; nothing was sent.'
STOP_UNCHECKED = 'CPT Studio could not check for a Stop before sending ({error}); nothing was sent.'
NO_TOOLS = 'CPT Studio offers no tool to this request.'


class Interpreter:
    """What the live and the replay interpreter share: the request each builds and every refusal each makes about a
    request before anything is sent or replayed, so a replayed request takes the paths a live one takes. A subclass
    gives ``mode``, ``endpoint`` (the URL it calls, '' for none) and ``_exchange``."""
    name = NAME
    adapter_version = ADAPTER_VERSION
    requested_model = MODEL
    mode = ''
    endpoint = ''

    def __init__(self, *, send_deadline: float = SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES):
        if not valid_deadline(send_deadline):
            raise ValueError('send_deadline must be a positive number of seconds.')
        for label, limit in (('max_request_bytes', max_request_bytes), ('max_response_bytes', max_response_bytes)):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'{label} must be a positive integer.')
        self.send_deadline = send_deadline
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes

    def build_request(self, text: str, pages: tuple[PageSpan, ...], kind: str) -> ProviderRequest:
        return build_request(text, pages, kind, max_bytes=self.max_request_bytes)

    def read(self, request: ProviderRequest, response_bytes) -> Union[str, read.Refusal]:
        """The answer text of a stored answer, or the Refusal of the envelope (answer_text)."""
        return answer_text(request, response_bytes)

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str = '',
             original_bytes: Optional[bytes] = None) -> RawExchange:
        """Exactly one exchange within ``deadline_s``, never more than the send deadline. ``client_request_id`` is not
        sent (Google documents no such header) and ``original_bytes`` never are (D12): neither changes the request."""
        if not valid_deadline(deadline_s):
            return http.not_sent(INVALID_DEADLINE)
        deadline = monotonic() + min(deadline_s, self.send_deadline)
        problem = self._problem(request)
        if problem:
            return http.not_sent(problem)
        return self._exchange(request.body, deadline)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str = '',
                  original_bytes: Optional[bytes] = None, execute_tool: Optional[Callable] = None,
                  should_stop: Optional[Callable[[], bool]] = None, carried=()) -> loop.LoopOutcome:
        """The run (jobs._send's looped branch): participants.loop.run with exactly one exchange, within ``deadline_s``
        and never more than the send deadline, recorded as turn 1. Refused before anything is sent - not_sent, no
        exchange recorded - for an invalid deadline, a request this adapter does not build, a continuation (``carried``:
        there is none of one exchange) or a Stop check that is not callable. ``should_stop`` is asked once, right before
        the request is sent: a Stop, or a check that raises, ends the run there, not sent and ``stopped``. Gemini is
        offered no tool: ``execute_tool`` is never called, and no answer is read as asking for a tool call."""
        if not valid_deadline(deadline_s):
            return _refused(INVALID_DEADLINE)
        problem = self._problem(request)
        if problem:
            return _refused(problem)
        if carried:
            return _refused(NOT_CONTINUED, MODEL)
        if should_stop is not None:
            if not callable(should_stop):
                return _refused(NOT_CALLABLE, MODEL)
            halt = _halt(should_stop)
            if halt:
                return loop.LoopOutcome(final=http.not_sent(halt, MODEL), exchanges=(), stopped=True)

        def post(turn: int, body: dict, deadline: float) -> RawExchange:
            problem = body_problem(body)
            return http.not_sent(problem, MODEL) if problem else self._exchange(body, deadline)

        return loop.run(self, request, post=post, parse_turn=_no_tool_calls, follow_up=_no_follow_up,
                        execute_tool=_no_tools, deadline_s=deadline_s, longest_s=self.send_deadline, max_exchanges=1,
                        max_tool_result_bytes=1, max_request_bytes=self.max_request_bytes, body_keys=BODY_KEYS)

    def _problem(self, request: ProviderRequest) -> str:
        """Why ``request`` is not sent - another provider's or adapter version's, altered since it was hashed, over the
        size limit, or a body this adapter never builds - or ''."""
        try:
            verified_body(request, self, self.max_request_bytes)
        except ProviderUnavailable as exc:
            return str(exc)
        return body_problem(request.body)

    def _exchange(self, body: dict, deadline: float) -> RawExchange:
        raise NotImplementedError


class GeminiInterpreter(Interpreter):
    """The live interpreter: one POST to ENDPOINT, the key read at send time."""
    mode = 'live'
    endpoint = ENDPOINT

    def __init__(self, credentials_path, *, connect_timeout: float = CONNECT_TIMEOUT_SECONDS,
                 read_timeout: float = READ_TIMEOUT_SECONDS, send_deadline: float = SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
                 session_factory: Optional[Callable[[], requests.Session]] = None):
        super().__init__(send_deadline=send_deadline, max_request_bytes=max_request_bytes,
                         max_response_bytes=max_response_bytes)
        for label, seconds in (('connect_timeout', connect_timeout), ('read_timeout', read_timeout)):
            if not valid_deadline(seconds):
                raise ValueError(f'{label} must be a positive number of seconds.')
        self.credentials_path = credentials_path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.session_factory = session_factory or http.default_session

    def _exchange(self, body: dict, deadline: float) -> RawExchange:
        """One POST of a verified stored body: its exact canonical bytes, the key read now, nothing else."""
        try:
            data = http.sendable(body, self.max_request_bytes, with_original=False)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc), MODEL)
        try:
            credentials = load_gemini_credentials(self.credentials_path)
        except CredentialsError as exc:
            return http.not_sent(f'{exc} No request was sent.', MODEL)
        headers = {KEY_HEADER: credentials.api_key, 'content-type': 'application/json'}
        return http.post(VENDOR, self.session_factory, ENDPOINT, data, headers, deadline=deadline,
                         connect_timeout=self.connect_timeout, read_timeout=self.read_timeout,
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


def _refused(error: str, requested_model: str = '') -> loop.LoopOutcome:
    return loop.LoopOutcome(final=http.not_sent(error, requested_model), exchanges=())


def _halt(should_stop) -> str:
    """Why nothing is sent for a member's Stop, or ''. A check that raises stops it too (CPT Studio never sends without
    knowing), in CPT Studio's own sentence, never the exception's text."""
    try:
        stop = should_stop()
    except Exception as exc:  # noqa: BLE001 - the database, a lost provider lock: nothing is sent without knowing
        return STOP_UNCHECKED.format(error=type(exc).__name__)
    return STOPPED_BEFORE if stop else ''


def _no_tool_calls(response_bytes) -> loop.Turn:
    """Gemini is offered no tool, so no answer asks for one: every answer is final, for answer_text to read or refuse."""
    return loop.FINAL


def _no_follow_up(body: dict, turn: loop.Turn, outputs: tuple) -> dict:
    raise RuntimeError('An interpretation is one exchange; there is no next request.')


def _no_tools(name, arguments) -> tuple[dict, tuple]:
    return {'error': NO_TOOLS}, ()


# --- the envelope (FINAL 5.4) -------------------------------------------------------------------------------------------

def answer_text(request: ProviderRequest, response_bytes) -> Union[str, read.Refusal]:
    """The answer text of a stored generateContent answer, for interpretation.read - or the Refusal (stage
    ``envelope``) of all of it, by the rules of the module docstring. Read only as the adapter version that recorded it.
    Pure: no settings, credentials or network, so a stored answer is read again with no new request."""
    if (getattr(request, 'provider', None) != NAME
            or getattr(request, 'adapter_version', None) not in READ_VERSIONS):
        return read.refuse('envelope', 'it was recorded by another adapter or adapter version, which this reader does '
                                       'not read')
    text, code, why = _envelope(response_bytes)
    return read.refuse('envelope', why) if code else text


def _envelope(raw) -> tuple[str, str, str]:
    """(answer text, '', '') of a usable answer, or ('', code, why it is refused). The codes: bytes, json, model,
    blocked, candidates, max_tokens, finish, content, no_text."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        return '', 'bytes', 'there are no response bytes'
    try:
        envelope = reading.strict_json(raw)
    except reading.JSONRefused as exc:
        return '', 'json', f'the response {exc}'
    if not isinstance(envelope, dict):
        return '', 'json', 'the response is not a JSON object'
    model = envelope.get('modelVersion')  # D13: checked before anything else the response says
    if not isinstance(model, str) or not model:
        return '', 'model', 'the response does not name the model that answered'
    if model != MODEL:
        return '', 'model', 'the response names a model other than the one requested'
    feedback = envelope.get('promptFeedback')
    blocked = feedback.get('blockReason') if isinstance(feedback, dict) else None
    if blocked not in (None, ''):
        return '', 'blocked', f'the request was blocked ({_word(blocked)})'
    candidates = envelope.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        return '', 'candidates', 'the response holds no candidate answer'
    if len(candidates) != 1:
        return '', 'candidates', f'the response holds {len(candidates):,} candidate answers, not exactly one'
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return '', 'candidates', 'the candidate answer is not a JSON object'
    finish = candidate.get('finishReason')
    if finish == MAX_TOKENS:
        return '', 'max_tokens', 'the answer was cut off at the output limit'
    if finish != STOP:
        reason = _word(finish) if isinstance(finish, str) and finish else 'no stated reason'
        return '', 'finish', f'the answer stopped for {reason}, not at its end'
    content = candidate.get('content')
    parts = content.get('parts') if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return '', 'content', 'the answer has no list of parts'
    texts = []
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            return '', 'content', f'part {index + 1} of the answer is not a JSON object'
        if CONTENT_FIELDS & set(part):
            return '', 'content', (f'part {index + 1} of the answer carries content other than text (a function call, '
                                   'code or file data), which this request never asks for')
        thought = part.get('thought', False)
        if not isinstance(thought, bool):
            return '', 'content', f'part {index + 1} of the answer says whether it is thinking in a malformed way'
        if 'text' in part and not isinstance(part['text'], str):
            return '', 'content', f'part {index + 1} of the answer has text that is not a string'
        if thought or 'text' not in part:
            continue  # thinking is never the answer; a part with no text (a signature alone) adds none
        texts.append(part['text'])
    if not texts:
        return '', 'no_text', 'the answer carries no text outside its thinking'
    return ''.join(texts), '', ''


def _word(value) -> str:
    """A reason the vendor states (a finish or block reason), as participants.reading.vendor_word names one."""
    return reading.vendor_word(value, 40)


# --- classification (FINAL 11.1; ADJUDICATION P-3, P-4, P-5) -----------------------------------------------------------

ANSWERED = 'answered'  # a 200 whose envelope is usable: read on (interpretation.read decides the rest)
FAILED = 'failed'  # a definite failure of this attempt: no hold, no automatic retry; the recorded retry door (11.3)
TOO_LONG = 'too_long'  # cut off at the output limit (MAX_TOKENS): refused, and never released for a member's paid retry (C5)
HOLD = 'hold'  # an installation-wide interpreter hold, released only by the recorded operator command (11.2)
KINDS = (ANSWERED, FAILED, TOO_LONG, HOLD)
# InterpreterHold.reason (studio.models.InterpreterHold's constants; a test pins them equal)
AUTH, PERMISSION, QUOTA, MODEL_HOLD = 'auth', 'permission', 'quota', 'model'
HOLD_REASONS = (AUTH, PERMISSION, QUOTA, MODEL_HOLD)
# P-3: an error.status or a google.rpc.ErrorInfo reason that sets the hold, and the hold it sets. HTTP 401 and 403 set
# one too (HOLD_STATUSES). Any other refusal - a 400 INVALID_ARGUMENT without one of these, say - fails the attempt only.
HOLD_NAMES = {'API_KEY_INVALID': AUTH, 'API_KEY_EXPIRED': AUTH, 'UNAUTHENTICATED': AUTH,
              'BILLING_DISABLED': QUOTA,
              'API_KEY_SERVICE_BLOCKED': PERMISSION, 'SERVICE_DISABLED': PERMISSION, 'PERMISSION_DENIED': PERMISSION,
              'FAILED_PRECONDITION': PERMISSION}
HOLD_STATUSES = {401: AUTH, 403: PERMISSION}
_PRIORITY = (AUTH, QUOTA, PERMISSION)  # several names: the key itself first, then billing, then access
ERROR_INFO = 'type.googleapis.com/google.rpc.ErrorInfo'
QUOTA_FAILURE = 'type.googleapis.com/google.rpc.QuotaFailure'
RETRY_INFO = 'type.googleapis.com/google.rpc.RetryInfo'
RESOURCE_EXHAUSTED = 'RESOURCE_EXHAUSTED'
MAX_VIOLATIONS = 20  # recorded on the hold; the run keeps the whole body
_STATUS = re.compile(r'[A-Z][A-Z_]{0,39}')  # fits InterpreterHold.vendor_status
_REASON = re.compile(r'[A-Z][A-Z0-9_]{0,63}')
_DELAY = re.compile(r'[0-9]{1,12}(?:\.[0-9]{1,9})?s')  # a google.protobuf.Duration in JSON: "7824s", "1.5s"


@dataclass(frozen=True)
class Classification:
    """What one definite Gemini outcome means for the installation (FINAL 11.1; ADJUDICATION P-3 to P-5). Everything
    but ``why`` is read from the response as received: ``vendor_status`` (error.status), ``error_reasons`` (the
    google.rpc.ErrorInfo reasons), ``violations`` (the google.rpc.QuotaFailure violations, at most MAX_VIOLATIONS) and
    ``retry_delay`` (google.rpc.RetryInfo.retryDelay, as "60s"), each kept only when it has the shape the API gives it.
    ``why`` is CPT Studio's sentence; like a refusal, it names no provider or model."""
    kind: str  # one of KINDS
    hold: str = ''  # one of HOLD_REASONS when kind is HOLD, else ''
    http_status: Optional[int] = None
    vendor_status: str = ''
    error_reasons: tuple = ()
    violations: tuple = ()
    retry_delay: str = ''
    why: str = ''


def classify(outcome: str, http_status, response_bytes) -> Optional[Classification]:
    """What a run's definite outcome means (ProviderRun.state with its http_status and response bytes): None for an
    outcome that is not definite - 'unknown' (reconciled, 6.9) or 'not_sent' - or not an outcome at all.

    'succeeded' (a 200, or a replayed recording of one) is read by the envelope rules: ANSWERED when usable; a model
    other than MODEL, or none named, is a HOLD (model, P-5), so an answer that is never read is not paid for again and
    again; MAX_TOKENS is TOO_LONG (C5); any other refusal is FAILED.

    'failed' (a non-200, its body kept): by the error body's ErrorInfo reasons, then its error.status, then the HTTP
    status (P-3): API_KEY_INVALID, API_KEY_EXPIRED, UNAUTHENTICATED or 401 is a HOLD (auth); BILLING_DISABLED a HOLD
    (quota); API_KEY_SERVICE_BLOCKED, SERVICE_DISABLED, PERMISSION_DENIED, FAILED_PRECONDITION or 403 a HOLD
    (permission). Then a 429, or RESOURCE_EXHAUSTED, by its QuotaFailure violations (P-4): FAILED, with RetryInfo kept,
    only when there are none or every one is a per-minute quota above zero on a paid tier; any daily quota, a limit of
    0, a free-tier quota (gemini-4-argon has none: billing is not enabled) or a window the violation does not name is a
    HOLD (quota). Everything else - a 400 INVALID_ARGUMENT with none of those names, a 404, a 5xx, an unread redirect,
    a body that is not JSON - is FAILED."""
    if outcome == 'succeeded':
        status = http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None
        _, code, why = _envelope(response_bytes)
        if not code:
            return Classification(ANSWERED, http_status=status)
        if code == 'model':
            return Classification(HOLD, hold=MODEL_HOLD, http_status=status,
                                  why=f'The answer was not read: {why}. No further request is sent until an operator '
                                      'releases the hold.')
        if code == 'max_tokens':
            return Classification(TOO_LONG, http_status=status,
                                  why='The answer was cut off at the output limit: the document is too long to be '
                                      'read in one piece.')
        return Classification(FAILED, http_status=status, why=f'The answer was not read: {why}.')
    if outcome != 'failed':
        return None
    status = http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None
    error = _error(response_bytes)
    named = f'HTTP {status}' if status is not None else 'no HTTP status'
    stated = ', '.join(dict.fromkeys(item for item in (error['status'], *error['reasons']) if item))
    said = f' ({named}{", " + stated if stated else ""})'
    found = dict(http_status=status, vendor_status=error['status'], error_reasons=error['reasons'],
                 violations=error['violations'][:MAX_VIOLATIONS], retry_delay=error['retry_delay'])
    hold = (_first_hold(HOLD_NAMES.get(reason) for reason in error['reasons'])
            or HOLD_NAMES.get(error['status']) or HOLD_STATUSES.get(status))
    if hold:
        return Classification(HOLD, hold=hold, why=_HOLD_WHY[hold].format(said=said), **found)
    if status == 429 or error['status'] == RESOURCE_EXHAUSTED:
        violations = error['violations']
        if violations and not all(_rate_only(violation) for violation in violations):
            return Classification(HOLD, hold=QUOTA, why=_HOLD_WHY['quota-window'].format(said=said), **found)
        later = f' It may be tried again after {error["retry_delay"]}.' if error['retry_delay'] else ''
        return Classification(FAILED, why=f'A rate limit refused this attempt{said}.{later}', **found)
    return Classification(FAILED, why=f'The request failed{said}; this attempt is over.', **found)


_HOLD_WHY = {
    AUTH: 'The key was refused{said}: every request would be refused until an operator acts.',
    PERMISSION: 'The key may not use the model or the service{said}: every request would be refused until an operator '
                'acts.',
    QUOTA: 'Billing is not enabled for the key{said}: every request would be refused until an operator acts.',
    'quota-window': 'A daily, zero or unbilled quota was exhausted{said}: every request would be refused until an '
                    'operator acts.',
}


def _first_hold(holds) -> str:
    found = {hold for hold in holds if hold}
    return next((hold for hold in _PRIORITY if hold in found), '')


def _error(raw) -> dict:
    """The parts of a google.rpc error body this module reads, each as received and kept only when it has the shape the
    API gives it; all empty for a body that is not one (not strict JSON, say)."""
    found = {'status': '', 'reasons': (), 'violations': (), 'retry_delay': ''}
    try:
        body = reading.strict_json(raw)
    except Exception:  # noqa: BLE001 - not JSON, or not bytes: classified by its HTTP status alone
        return found
    if isinstance(body, list) and len(body) == 1:  # the list form some Google endpoints answer with
        body = body[0]
    error = body.get('error') if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return found
    status = error.get('status')
    found['status'] = status if isinstance(status, str) and _STATUS.fullmatch(status) else ''
    details = error.get('details')
    details = [item for item in details if isinstance(item, dict)] if isinstance(details, list) else []
    reasons, violations = [], []
    for detail in details:
        kind = detail.get('@type')
        if kind == ERROR_INFO:
            reason = detail.get('reason')
            if isinstance(reason, str) and _REASON.fullmatch(reason) and reason not in reasons:
                reasons.append(reason)
        elif kind == QUOTA_FAILURE and isinstance(detail.get('violations'), list):
            violations += [item for item in detail['violations'] if isinstance(item, dict)]
        elif kind == RETRY_INFO and not found['retry_delay']:
            delay = detail.get('retryDelay')
            found['retry_delay'] = delay if isinstance(delay, str) and _DELAY.fullmatch(delay) else ''
    found['reasons'] = tuple(reasons)
    found['violations'] = tuple(violations)  # every one decides; classify records the first MAX_VIOLATIONS
    return found


def _rate_only(violation: dict) -> bool:
    """Whether a QuotaFailure violation refuses only this attempt (P-4): a per-minute quota, on a paid tier, whose limit
    is not 0. A daily quota, a limit of 0, a free-tier quota (the model has none: billing is not enabled) or a window the
    violation does not name is not."""
    quota_id, metric = violation.get('quotaId'), violation.get('quotaMetric')
    names = ' '.join(value for value in (quota_id, metric) if isinstance(value, str)).lower()
    if 'perday' in names or 'perminute' not in names:
        return False
    if 'freetier' in names or 'free_tier' in names:
        return False
    return violation.get('quotaValue') not in (0, '0')


# --- the configured interpreter -----------------------------------------------------------------------------------------

def get_interpreter(mode: Optional[str] = None) -> Optional[Interpreter]:
    """The configured interpreter (settings.GEMINI_MODE, or ``mode``): None when it is disabled - nothing is sent, and the
    interpret stage pauses (FINAL 11.2) - else the live or the replay interpreter. Misconfiguration raises
    ProviderUnavailable (a caller inside a web request must catch it, as it would get_provider's); an unknown mode is a
    programming error (ValueError). The only place this module reads settings, at call time."""
    from django.conf import settings

    mode = settings.GEMINI_MODE if mode is None else mode
    if mode == 'disabled':
        return None
    limits = {'send_deadline': settings.INTERPRETER_SEND_DEADLINE_SECONDS}
    if mode == 'live':
        if not settings.GEMINI_CREDENTIALS_FILE:
            raise ProviderUnavailable('Live interpretation needs CPT_STUDIO_GEMINI_CREDENTIALS_FILE.')
        return GeminiInterpreter(settings.GEMINI_CREDENTIALS_FILE,
                                 connect_timeout=settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS,
                                 read_timeout=settings.PARTICIPANT_READ_TIMEOUT_SECONDS, **limits)
    if mode == 'replay':
        if not settings.GEMINI_REPLAY_DIR:
            raise ProviderUnavailable('Replay interpretation needs CPT_STUDIO_GEMINI_REPLAY_DIR.')
        from studio.interpretation.replay import ReplayInterpreter

        return ReplayInterpreter(settings.GEMINI_REPLAY_DIR, **limits)
    raise ValueError(f'No interpreter exists for mode {mode!r}; expected disabled, live or replay.')
