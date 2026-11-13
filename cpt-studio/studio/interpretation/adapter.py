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
10 s, read 480 s and a send deadline of 510 s that no caller's deadline can stretch (D12 as D49 sets them). ``send_loop`` is the run the
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

CLASSIFICATION (``classify``; FINAL 11.1 as ADJUDICATION P-3, P-4 and P-5 amend it, and FINAL-V2 amendment 1's A11):
what a definite outcome means for the installation. interpretation.holds records and releases the hold this names
(InterpreterHold.reason is one of HOLD_REASONS); this module only reads the response. One classifier serves both of
design v2's passes (FINAL-V2 7.4): it reads the response alone, never which request it answered.

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 2.4, 2.5, 7.3-7.5, as AMENDMENT-1.md 7.3 and A11 amend them; step 3b of
its 8.1) adds its adapter beside v1's, in the section ``design v2`` at the end of this module, under v2 names:
ADAPTER_VERSION_V2 (gemini-generate@cptstudio-2) with TWO request kinds, named by ProviderRun.purpose - EXTRACTION
(pass 1, gemini-events@2: contract/extract_prompt's body) and APPRAISAL (pass 2, gemini-appraisal@1: contract/
appraise_prompt's body, built from the revision plus pass 1's STORED response bytes, read through the same envelope
and contract/extract_read, with the claim bound checked before any body is built: 7.4 door 0). The envelope rules,
the model pin, the key, the one exchange and the classifier above are SHARED by both kinds and by v1; each kind has
its own read timeout and send deadline (pass 2 at D49's 480 and 510 s: settings.APPRAISER_*). A request that cannot
be built is NotBuilt - ``refused: unbuilt`` with contract/extract_prompt's Unframed reason (never participants.http.
framed_text's sentence, which names a label collision a page-cover failure), or TOO_LONG for a claim set over its
bound - and nothing is sent. The answers are read with contract/extract_read and contract/appraise_read, whose
Refusal is design v2's. HTTP 402 holds as quota (A11).

v1's surface - build_request, body_problem, Interpreter, GeminiInterpreter, answer_text and get_interpreter - keeps
every name, signature and behaviour: jobs.py calls it until step 5b switches (FINAL-V2 8.0), and v1's tests read it
for good, edited by no step (5.0). This module no longer imports v1's ``prompt`` or ``read`` (FINAL-V2 5.7): the v1
surface alone reaches them, at call time (_v1_prompt, _v1_read), so importing the module loads neither, and design
v2's section executes no line of either and no line of the v1 surface (tests/v2/test_adapter.py traces both).

Nothing here imports studio.gi, studio.validation or studio.candidates (D17), reads Django settings at import, or
touches the database. ``get_interpreter`` and ``get_interpreter_v2`` are the places settings are read, at call time.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic
from types import ModuleType
from typing import Any, Callable, Optional, Union

import requests

from studio import interpretation
from studio.interpretation.contract import appraise_prompt, appraise_read, claims, extract_prompt, extract_read, segment
from studio.participants import credentials as participant_credentials
from studio.participants import http, loop, reading
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256, valid_deadline, verified_body
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
# D49 (the S17 refutation, finding 19): a unary answer arrives whole, so the read timeout bounds its generation. A cut-off
# answer of 32,768 output tokens at the slowest measured rate (82.4 tok/s, FRESH-2) needs about 398 s, and D25's p99 STOP
# answer at the size bound (27,378 tokens) about 332 s: at 300 s both were recorded UNKNOWN (an operator's reconcile, a
# paid resend) instead of TOO_LONG or read. 480 s covers them; the send deadline keeps D12's 30 s above it.
READ_TIMEOUT_SECONDS = 480
SEND_DEADLINE_SECONDS = 510  # settings.INTERPRETER_SEND_DEADLINE_SECONDS; below the stale-stage sweep (600 s)
# A request is the instructions, the schema and the framed text (the size bound, settings.INTERPRET_MAX_CHARS, refuses a
# long document before one is built); an answer is at most 32,768 output tokens. Both are refused over these, never cut.
DEFAULT_MAX_REQUEST_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# The request body's three keys: v1's prompt.BODY_KEYS, which both of design v2's bodies keep exactly (contract/
# extract_prompt and contract/appraise_prompt; tests/v2/test_adapter.py pins the three equal).
BODY_KEYS = frozenset(extract_prompt.BODY_KEYS)

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


# --- v1's prompt and read, at call time (FINAL-V2 5.7) -------------------------------------------------------------------

def _v1_prompt() -> ModuleType:
    """v1's prompt module (retired whole, FINAL-V2 5.0), imported when the v1 surface builds or checks a v1 request -
    never at this module's import, and never by design v2's section."""
    from studio.interpretation import prompt

    return prompt


def _v1_read() -> ModuleType:
    """v1's read module (retired whole, FINAL-V2 5.0), imported when the v1 surface refuses a v1 envelope - never at
    this module's import, and never by design v2's section."""
    from studio.interpretation import read

    return read


# --- the request --------------------------------------------------------------------------------------------------------

def build_request(text: str, pages, kind: str, *, max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> ProviderRequest:
    """The interpretation request for one revision (contract 2.2; D1, D12): its text framed by prompt.framed - through
    participants.http.framed_text, so a text that cannot be framed, is empty or holds NUL raises ProviderUnavailable and
    nothing is built or sent - and the body prompt.request_parts builds from it. Pure: no settings, credentials or
    network. Refused over ``max_bytes``, never truncated. Its contexts are ``(text,)``, the revision text the answer's
    passages are located in. It takes no original file: none is sent (D12)."""
    prompt = _v1_prompt()
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
    prompt = _v1_prompt()
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

    def read(self, request: ProviderRequest, response_bytes) -> Union[str, Any]:  # Any: v1's read.Refusal (_v1_read)
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

def answer_text(request: ProviderRequest, response_bytes) -> Union[str, Any]:  # Any: v1's read.Refusal (_v1_read)
    """The answer text of a stored generateContent answer, for interpretation.read - or the Refusal (stage
    ``envelope``) of all of it, by the rules of the module docstring. Read only as the adapter version that recorded it.
    Pure: no settings, credentials or network, so a stored answer is read again with no new request."""
    read = _v1_read()
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
# one too (HOLD_STATUSES), and HTTP 402 sets the quota hold: a payment failure, fail-closed, since Google is not
# documented to send it (FINAL-V2 amendment 1, A11 and 7.3). Any other refusal - a 400 INVALID_ARGUMENT without one of
# these, say - fails the attempt only.
HOLD_NAMES = {'API_KEY_INVALID': AUTH, 'API_KEY_EXPIRED': AUTH, 'UNAUTHENTICATED': AUTH,
              'BILLING_DISABLED': QUOTA,
              'API_KEY_SERVICE_BLOCKED': PERMISSION, 'SERVICE_DISABLED': PERMISSION, 'PERMISSION_DENIED': PERMISSION,
              'FAILED_PRECONDITION': PERMISSION}
HOLD_STATUSES = {401: AUTH, 402: QUOTA, 403: PERMISSION}
# The sentence of a hold set by its HTTP status alone where the hold's own sentence would say more than the response
# did: a bare 402 says a payment is required, not that billing is disabled.
_STATUS_WHY = {402: 'payment'}
_PRIORITY = (AUTH, QUOTA, PERMISSION)  # several names: the key itself first, then billing, then access
ERROR_INFO = 'type.googleapis.com/google.rpc.ErrorInfo'
QUOTA_FAILURE = 'type.googleapis.com/google.rpc.QuotaFailure'
RETRY_INFO = 'type.googleapis.com/google.rpc.RetryInfo'
RESOURCE_EXHAUSTED = 'RESOURCE_EXHAUSTED'
MAX_VIOLATIONS = 20  # recorded on the hold; the run keeps the whole body
_STATUS = re.compile(r'[A-Z][A-Z_]{0,39}')  # fits InterpreterHold.vendor_status
_REASON = re.compile(r'[A-Z][A-Z0-9_]{0,63}')
_DELAY = re.compile(r'[0-9]{1,12}(?:\.[0-9]{1,9})?s')  # a google.protobuf.Duration in JSON: "7824s", "1.5s"
_LIMIT = re.compile(r'[0-9]{1,19}')  # an int64 in JSON: ASCII digits, no sign, space or exponent
_INT64_MAX = 2 ** 63 - 1


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
    status (P-3): API_KEY_INVALID, API_KEY_EXPIRED, UNAUTHENTICATED or 401 is a HOLD (auth); BILLING_DISABLED or 402 a
    HOLD (quota: a payment failure; 402 by FINAL-V2 amendment 1's A11, fail-closed, whatever its body says);
    API_KEY_SERVICE_BLOCKED, SERVICE_DISABLED, PERMISSION_DENIED, FAILED_PRECONDITION or 403 a HOLD (permission).
    Then a 429, or RESOURCE_EXHAUSTED, by its QuotaFailure violations' quotaId or quotaMetric (P-4):
    FAILED, with RetryInfo kept, only when there is at least one violation and every one is a per-minute quota on a
    paid tier stating a limit above 0; any daily quota, a limit of 0 - which Google's JSON states by leaving quotaValue
    out - or one left out or unreadable, a free-tier quota (gemini-4-argon has none: billing is not enabled), a window
    the violation does not name, or NO violation at all is a HOLD (quota). The last is fail-closed and measured: on
    2026-11-10 the project's monthly spending cap was exhausted, and Google answered 429 RESOURCE_EXHAUSTED with only a
    message and no QuotaFailure, which this rule had read as a per-minute rate limit - so every later upload was sent
    and refused again, where an exhausted quota must stop requests. Everything else - a 400 INVALID_ARGUMENT with none
    of those names, a 404, a 5xx, an unread redirect, a body that is not JSON - is FAILED."""
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
    by_name = (_first_hold(HOLD_NAMES.get(reason) for reason in error['reasons'])
               or HOLD_NAMES.get(error['status'], ''))
    by_status, status_why = ((HOLD_STATUSES.get(status, ''), _STATUS_WHY.get(status, '')) if status is not None
                             else ('', ''))
    hold = by_name or by_status
    if hold:
        sentence = _HOLD_WHY[hold if by_name else status_why or hold]
        return Classification(HOLD, hold=hold, why=sentence.format(said=said), **found)
    if status == 429 or error['status'] == RESOURCE_EXHAUSTED:
        violations = error['violations']
        if not violations:
            return Classification(HOLD, hold=QUOTA, why=_HOLD_WHY['quota-unstated'].format(said=said), **found)
        if not all(_rate_only(violation) for violation in violations):
            return Classification(HOLD, hold=QUOTA, why=_HOLD_WHY['quota-window'].format(said=said), **found)
        later = f' It may be tried again after {error["retry_delay"]}.' if error['retry_delay'] else ''
        return Classification(FAILED, why=f'A rate limit refused this attempt{said}.{later}', **found)
    return Classification(FAILED, why=f'The request failed{said}; this attempt is over.', **found)


_HOLD_WHY = {
    AUTH: 'The key was refused{said}: every request would be refused until an operator acts.',
    PERMISSION: 'The key may not use the model or the service{said}: every request would be refused until an operator '
                'acts.',
    QUOTA: 'Billing is not enabled for the key{said}: every request would be refused until an operator acts.',
    'payment': 'A payment is required for the key{said}: every request would be refused until an operator acts.',
    'quota-window': 'A daily, zero or unbilled quota was exhausted{said}: every request would be refused until an '
                    'operator acts.',
    'quota-unstated': 'A quota or spending limit was exhausted{said} and no per-minute limit was named: every request '
                      'would be refused until an operator acts.',
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
    is stated and above 0. A daily quota, a free-tier quota (the model has none: billing is not enabled), a window the
    violation does not name, or a limit that is 0, left out or unreadable is not. The window and the tier are read from
    quotaId and quotaMetric alike, without '_' and '-' (a metric names them in snake_case: 'per_minute', 'free_tier')."""
    quota_id, metric = violation.get('quotaId'), violation.get('quotaMetric')
    names = ' '.join(value for value in (quota_id, metric) if isinstance(value, str)).lower()
    names = names.replace('_', '').replace('-', '')
    if 'perday' in names or 'perminute' not in names or 'freetier' in names:
        return False
    return _stated_limit(violation.get('quotaValue')) > 0


def _stated_limit(value) -> int:
    """A violation's quotaValue as the whole number it states, or 0. It is an int64 (google.rpc.QuotaFailure.Violation
    quota_value, a plain proto3 scalar), so Google's JSON gives it as a string of digits ("1000") and leaves it out when
    it is 0: the trial's recorded 429 says "limit: 0" four times, and none of its violations has a quotaValue. A missing,
    null, signed, fractional, boolean or out-of-range value states no limit above 0."""
    if type(value) is int:
        number = value
    elif isinstance(value, str) and _LIMIT.fullmatch(value):
        number = int(value)
    else:
        return 0
    return number if 0 < number <= _INT64_MAX else 0


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
                                 read_timeout=settings.INTERPRETER_READ_TIMEOUT_SECONDS, **limits)
    if mode == 'replay':
        if not settings.GEMINI_REPLAY_DIR:
            raise ProviderUnavailable('Replay interpretation needs CPT_STUDIO_GEMINI_REPLAY_DIR.')
        from studio.interpretation.replay import ReplayInterpreter

        return ReplayInterpreter(settings.GEMINI_REPLAY_DIR, **limits)
    raise ValueError(f'No interpreter exists for mode {mode!r}; expected disabled, live or replay.')


# ======================================================================================================================
# === design v2 (FINAL-V2 2.4, 2.5, 7.3-7.5, as AMENDMENT-1 7.3 and A11 amend them; step 3b of 8.1): the adapter of
# === gemini-generate@cptstudio-2 and its two request kinds. Everything below executes contract/, participants/,
# === providers/ and the shared rules above (the envelope, the classifier, the key, VENDOR, the one-exchange helpers) -
# === never v1's prompt or read, and no line of the v1 surface (build_request, body_problem, Interpreter,
# === GeminiInterpreter, answer_text, get_interpreter, _v1_prompt, _v1_read): tests/v2/test_adapter.py traces it.
# ======================================================================================================================
#
# THE TWO KINDS (FINAL-V2 7.4). A request of ADAPTER_VERSION_V2 is one of two kinds, named by the ProviderRun.purpose
# its run records: EXTRACTION, pass 1 - contract/extract_prompt.build_request of the revision text, its pages and its
# kind (D1: nothing else); APPRAISAL, pass 2 - contract/appraise_prompt.build_request of the same revision and pass 1's
# answer as read from its STORED response bytes, with the check findings of that answer (DECISIONS D206), so the
# request is a pure function of the revision text, the stored bytes and the versions, never of a member value
# [R:MO-5], and replay and reuse work for it as for pass 1. Both bodies have v1's three keys and nothing else; the URL
# names the model, as v1's does (D13).
#
# NOT BUILT. A request that cannot be built is NotBuilt, and nothing is sent: ``refused: unbuilt`` (1.2 rule 8) when
# the text cannot be framed - the reason is contract/extract_prompt's Unframed value, from its Unbuilt (hand-offs
# 1a:R2, 2a#5, 2a:R2), never participants.http.framed_text's sentence - or holds NUL, or cannot be encoded, or is over
# the byte limit, or when the stored first reading does not answer this revision's pass-1 request or cannot be read;
# TOO_LONG when pass 2's claim set is over claims.CLAIM_BOUND (1.8; 7.4 door 0; 7.5), refused before any body is built
# (appraise_prompt.build_request raises OverBound before it writes the user turn) and asserted again here.
#
# THE SEND. One exchange of a verified body, as v1's (no retry, no tool, a member's Stop asked once right before the
# send), within the purpose's send deadline and read timeout: pass 1 at D49's 510 and 480 s (settings.INTERPRETER_*),
# pass 2 at the same values (settings.APPRAISER_*; 7.4 [R:MO-3]). A body is sent only when it is exactly one of the two
# kinds as this adapter builds it (body_kind): instructions, schema and generation settings this version's byte for
# byte under the pins of 2.5, and nothing riding along.
#
# THE ENVELOPE AND THE CLASSIFIER are the shared rules above, for both kinds: modelVersion exactly MODEL and first, no
# block reason, exactly one candidate, finishReason STOP (MAX_TOKENS is TOO_LONG), text parts only, thinking excluded;
# a refusal is contract/extract_read's Refusal at stage 'envelope'. A HOLD - auth, permission, quota (a bare 429 and a
# 402 included) or a substituted model - stops every request of either pass (interpretation.holds).

ADAPTER_VERSION_V2 = interpretation.ADAPTER_VERSION_V2  # 'gemini-generate@cptstudio-2': both request kinds
READ_VERSIONS_V2 = (ADAPTER_VERSION_V2,)  # the adapter versions whose stored answers design v2's readers read
EXTRACTION = interpretation.PURPOSE  # 'interpretation': pass 1 (gemini-events@2), its run's ProviderRun.purpose
APPRAISAL = interpretation.APPRAISAL_PURPOSE  # 'appraisal': pass 2 (gemini-appraisal@1), its run's ProviderRun.purpose
PURPOSES = (EXTRACTION, APPRAISAL)
# FINAL-V2 7.4 [R:MO-3]: pass 2 takes D49's deadlines, as pass 1 (READ_TIMEOUT_SECONDS and SEND_DEADLINE_SECONDS above):
# a cut-off answer of 32,768 tokens at the slowest measured rate (82.4 tokens per second) needs about 398 s, inside the
# read, so it is recorded TOO_LONG, never UNKNOWN. settings.APPRAISER_READ_TIMEOUT_SECONDS and
# APPRAISER_SEND_DEADLINE_SECONDS; the appraise stage's 560 s (settings.JOB_DEADLINE_SECONDS) covers the send.
APPRAISAL_READ_TIMEOUT_SECONDS = 480
APPRAISAL_SEND_DEADLINE_SECONDS = 510

# --- a request that is not built -------------------------------------------------------------------------------------

UNBUILT = 'unbuilt'  # the not-sent run's refusal when no request could be built (1.2 rule 8; jobs.UNBUILT's value)
UNFRAMED_REASONS = tuple(reason.value for reason in extract_prompt.Unframed)  # marker, label, pages, empty
NUL, ENCODING, SIZE, STORED, CLAIMS = 'nul', 'encoding', 'size', 'stored', 'claims'
NOT_BUILT_REASONS = UNFRAMED_REASONS + (NUL, ENCODING, SIZE, STORED, CLAIMS)
_UNFRAMED_WHY = {
    extract_prompt.Unframed.MARKER: 'it contains its own framing marker',
    extract_prompt.Unframed.LABEL: ('it contains a unit label of its own (an [S followed by a number and ]), which '
                                    'could not be told from the labels the framed text adds'),
    extract_prompt.Unframed.PAGES: 'its pages do not cover it exactly, or a page number cannot be shown',
    extract_prompt.Unframed.EMPTY: 'it holds no text to send',
}
UNFRAMED_MESSAGE = 'The document text cannot be framed: {why}; nothing was sent.'
NUL_MESSAGE = 'The document text contains NUL characters; nothing was sent.'
ENCODING_MESSAGE = 'The document text cannot be encoded as UTF-8; nothing was sent.'
STORED_OTHER = ("The stored first reading answers another request than this revision's; no appraisal request was "
                'built and nothing was sent.')
STORED_REFUSED = ('The stored first reading could not be read (stage {stage}); no appraisal request was built and '
                  'nothing was sent.')
CLAIMS_MESSAGE = ('The appraisal would carry {count:,} claims, more than the {bound:,} one request may carry; no '
                  'request was built and nothing was sent.')
NO_CHECK = ('An appraisal request is built from the findings of the checks on the stored answer (DECISIONS D206); no '
            'check was given.')
UNPINNED_V2 = ('An instruction, a schema or a table of design v2 no longer matches its pin, so no request of this '
               'version can be checked; nothing was sent.')


class NotBuilt(ProviderUnavailable):
    """No request of design v2 is built, so nothing is sent; the stage records a not-sent run with ``effect`` as its
    refusal and str() as its error. ``effect``: UNBUILT, or TOO_LONG for a pass-2 claim set over claims.CLAIM_BOUND
    (7.4 door 0; 7.5: never re-sent for a member). ``reason``: one of NOT_BUILT_REASONS - an extract_prompt.Unframed
    value when the text cannot be framed (``unframed``), NUL, ENCODING, SIZE, STORED (the stored first reading answers
    another request, or cannot be read: ``refusal`` is then its Refusal, when it was read) or CLAIMS (``claims`` is the
    count). The sentence is CPT Studio's: it names no provider or model and repeats no document or model text."""

    def __init__(self, message: str, *, reason: str, effect: str = UNBUILT, claims: Optional[int] = None,
                 refusal: Optional[extract_read.Refusal] = None) -> None:
        if reason not in NOT_BUILT_REASONS or effect not in (UNBUILT, TOO_LONG) or (effect == TOO_LONG) != (
                reason == CLAIMS):
            raise ValueError('A request that is not built is unbuilt for a reason of NOT_BUILT_REASONS, or too long '
                             'for its claims.')
        super().__init__(message)
        self.reason = reason
        self.effect = effect
        self.claims = claims
        self.refusal = refusal

    @property
    def unframed(self) -> str:
        """The extract_prompt.Unframed value a ``refused: unbuilt`` run records, or '' for any other reason."""
        return self.reason if self.reason in UNFRAMED_REASONS else ''


def _unframed(reason: extract_prompt.Unframed) -> NotBuilt:
    return NotBuilt(UNFRAMED_MESSAGE.format(why=_UNFRAMED_WHY[reason]), reason=reason.value)


def _document(text: object, pages: object) -> tuple[PageSpan, ...]:
    """The revision's pages as a tuple, after the checks v1's adapter made of every document (participants.http's
    framed_text): TypeError when the text is not a str or the pages are not PageSpans; NotBuilt (NUL) for a text
    holding NUL. What contract/extract_prompt refuses (unframed) it names itself, by its own reason."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a string.')
    if not isinstance(pages, (tuple, list)) or not all(isinstance(page, PageSpan) for page in pages):
        raise TypeError('The pages must be a sequence of PageSpan.')
    if '\x00' in text:
        raise NotBuilt(NUL_MESSAGE, reason=NUL)
    return tuple(pages)


def _finished(body: dict[str, Any], text: str, max_bytes: int) -> ProviderRequest:
    """The ProviderRequest of a built body (http.finished_request: its canonical sha256, contexts ``(text,)``), refused
    when it cannot be encoded or is over ``max_bytes`` - never truncated."""
    try:
        canonical_body(body)
    except UnicodeEncodeError:
        raise NotBuilt(ENCODING_MESSAGE, reason=ENCODING) from None
    try:
        return http.finished_request(NAME, ADAPTER_VERSION_V2, body, text, max_bytes=max_bytes)
    except ProviderUnavailable as exc:  # the body encodes, so only the byte limit is left
        raise NotBuilt(str(exc), reason=SIZE) from None


# --- the two request kinds --------------------------------------------------------------------------------------------

def build_extraction_request(text: str, pages: Sequence[PageSpan], kind: str, *,
                             max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> ProviderRequest:
    """Pass 1's request for one revision (gemini-events@2; FINAL-V2 2.1, 1.2 rule 8): contract/extract_prompt's body of
    the revision text, its pages and its kind - nothing else (D1) - as a ProviderRequest of ADAPTER_VERSION_V2 whose
    contexts are ``(text,)``. Pure: no settings, credentials or network. NotBuilt when it cannot be built (the module's
    section notes); TypeError for a text or pages of the wrong type, ValueError for an unknown kind, RuntimeError when a
    pin of 2.5 does not match (contract/extract_prompt.check_pins: nothing is built under an unpinned object)."""
    spans = _document(text, pages)
    try:
        body = extract_prompt.build_request(text, spans, kind)
    except extract_prompt.Unbuilt as exc:
        raise _unframed(exc.reason) from None
    return _finished(body, text, max_bytes)


Check = Callable[[str, tuple[PageSpan, ...], extract_read.ReadAnswer], Any]


@dataclass(frozen=True)
class AppraisalRequest:
    """Pass 2's request and what it was built from, for the stage, appraise_read and settle: ``request``, the
    ProviderRequest sent (ADAPTER_VERSION_V2; its canonical_sha256 is request_sha256 of its body, the appraise key's
    source, 7.4 [R:MO-5]); ``built``, contract/appraise_prompt's Request (the claim set, the framed document, the user
    turn, the indistinct groups); ``answer``, pass 1's answer as read from its stored bytes; ``findings``, the checks'
    findings over it, as the check returned them; ``unit_count``, the revision's units (contract/segment.py)."""
    request: ProviderRequest
    built: appraise_prompt.Request
    answer: extract_read.ReadAnswer
    findings: Any
    unit_count: int


def build_appraisal_request(text: str, pages: Sequence[PageSpan], kind: str, extraction: ProviderRequest,
                            extraction_bytes: object, *, check: Check,
                            max_bytes: int = DEFAULT_MAX_REQUEST_BYTES) -> AppraisalRequest:
    """Pass 2's request for one revision (gemini-appraisal@1; FINAL-V2 2.4, 7.4), built from the revision plus pass 1's
    STORED answer: ``extraction`` is the request that answer was recorded for and ``extraction_bytes`` its response
    bytes as stored. In order:
    1. pass 1's request is built again from the revision (build_extraction_request) and ``extraction`` must be it, byte
       for byte (provider, adapter version, body and sha256), so the stored answer is this revision's under this
       version (STORED otherwise);
    2. the stored answer is read: the shared envelope, then contract/extract_read under its pin (read_extraction); a
       Refusal is STORED, with the Refusal kept;
    3. ``check(text, pages, answer)`` gives the findings of the checks on that answer (DECISIONS D206: contract/checks,
       step 3a), which contract/appraise_prompt takes as its required keyword - so the findings are always those of the
       answer read here;
    4. contract/appraise_prompt.build_request builds the claim set and refuses it over claims.CLAIM_BOUND before it
       writes the user turn or the body (OverBound): TOO_LONG, with the count (7.4 door 0; 7.5);
    5. the claim set is checked against the bound again, and the body becomes a ProviderRequest (ENCODING, SIZE).
    Pure: the request is a function of the revision text, its pages and kind, the stored bytes and the versions, never
    of a member value (7.4 [R:MO-5]), given a check that is a pure function too. NotBuilt as above; TypeError for wrong
    types or a check that is not callable; RuntimeError when a pin does not match."""
    spans = _document(text, pages)
    if not callable(check):
        raise TypeError(NO_CHECK)
    own = build_extraction_request(text, spans, kind, max_bytes=max_bytes)
    if not _same_request(extraction, own):
        raise NotBuilt(STORED_OTHER, reason=STORED)
    unit_count = len(segment.units(text, spans))
    answer = read_extraction(extraction, extraction_bytes, unit_count)
    if isinstance(answer, extract_read.Refusal):
        raise NotBuilt(STORED_REFUSED.format(stage=answer.stage), reason=STORED, refusal=answer)
    findings = check(text, spans, answer)
    try:
        built = appraise_prompt.build_request(text, spans, kind, answer, findings=findings)
    except appraise_prompt.OverBound as exc:
        raise _over_bound(exc.count) from None
    except appraise_prompt.Unbuilt as exc:  # not reached: pass 1's request was framed from this same text in step 1
        raise _unframed(exc.reason) from None
    if claims.over_bound(built.claim_set):  # refused by appraise_prompt before its body; never sent if it were not
        raise _over_bound(len(built.claim_set.claims))
    return AppraisalRequest(_finished(built.body, text, max_bytes), built, answer, findings, unit_count)


def _over_bound(count: int) -> NotBuilt:
    return NotBuilt(CLAIMS_MESSAGE.format(count=count, bound=claims.CLAIM_BOUND), reason=CLAIMS, effect=TOO_LONG,
                    claims=count)


def _same_request(given: object, expected: ProviderRequest) -> bool:
    """Whether ``given`` is ``expected`` byte for byte: provider, adapter version, recorded sha256, and a body whose
    canonical sha256 is that sha256."""
    try:
        return (getattr(given, 'provider', None) == expected.provider
                and getattr(given, 'adapter_version', None) == expected.adapter_version
                and getattr(given, 'canonical_sha256', None) == expected.canonical_sha256
                and isinstance(getattr(given, 'body', None), dict)
                and request_sha256(getattr(given, 'body')) == expected.canonical_sha256)
    except (TypeError, ValueError):  # a body that is not JSON
        return False


# --- the answers: the shared envelope, then contract/'s readers ------------------------------------------------------

STORED_VERSION = 'it was recorded by another adapter or adapter version, which this reader does not read'
OTHER_KIND = 'it answers a request of another kind than the one this reader reads'
OTHER_APPRAISAL = ('it answers another appraisal request than the one built again for this revision, so its verdicts '
                   'would be read against claims they did not answer')


def answer_text_v2(request: ProviderRequest, response_bytes: object) -> Union[str, extract_read.Refusal]:
    """The answer text of a stored generateContent answer to a request of design v2 - or the Refusal (contract/
    extract_read's, stage ``envelope``) of all of it: the shared envelope rules of the module docstring, the same for
    both kinds. Read only as an adapter version of READ_VERSIONS_V2 recorded it. Pure: no settings, credentials or
    network, so a stored answer is read again with no new request."""
    if (getattr(request, 'provider', None) != NAME
            or getattr(request, 'adapter_version', None) not in READ_VERSIONS_V2):
        return extract_read.refuse('envelope', STORED_VERSION)
    text, code, why = _envelope(response_bytes)
    return extract_read.refuse('envelope', why) if code else text


def read_extraction(request: ProviderRequest, response_bytes: object,
                    unit_count: int) -> Union[extract_read.ReadAnswer, extract_read.Refusal]:
    """Pass 1's stored answer, read: ``request`` must be a pass-1 request of READ_VERSIONS_V2 (body_kind), then the
    shared envelope (answer_text_v2), then contract/extract_read.read with the revision's ``unit_count``. The Refusal of
    the whole answer otherwise. RuntimeError when a pin does not match."""
    if (getattr(request, 'provider', None) != NAME
            or getattr(request, 'adapter_version', None) not in READ_VERSIONS_V2):
        return extract_read.refuse('envelope', STORED_VERSION)
    if body_kind(getattr(request, 'body', None))[0] != EXTRACTION:
        return extract_read.refuse('envelope', OTHER_KIND)
    answer = answer_text_v2(request, response_bytes)
    if isinstance(answer, extract_read.Refusal):
        return answer
    return extract_read.read(answer, unit_count)


def read_appraisal(appraisal: AppraisalRequest, request: ProviderRequest,
                   response_bytes: object) -> Union[appraise_read.ReadAppraisal, extract_read.Refusal]:
    """Pass 2's answer, read against the claims it answered: ``request`` is the request the answer was recorded for (the
    run's), which must be ``appraisal.request`` byte for byte - a verdict is never read against a claim set it did not
    answer (FINAL-V2 3.2.4 [R:MO-5]) - then the shared envelope, then contract/appraise_read.read with the claim set and
    the revision's unit count. The Refusal of the whole answer otherwise."""
    if (getattr(request, 'provider', None) != NAME
            or getattr(request, 'adapter_version', None) not in READ_VERSIONS_V2):
        return extract_read.refuse('envelope', STORED_VERSION)
    if not _same_request(request, appraisal.request):
        return extract_read.refuse('envelope', OTHER_APPRAISAL)
    answer = answer_text_v2(request, response_bytes)
    if isinstance(answer, extract_read.Refusal):
        return answer
    return appraise_read.read(answer, appraisal.built.claim_set, appraisal.unit_count)


# --- which kind a body is --------------------------------------------------------------------------------------------

def body_kind(body: Any) -> tuple[str, str]:
    """(EXTRACTION or APPRAISAL, '') when ``body`` is exactly a body of that kind as this adapter builds it -
    contract/extract_prompt.request_parts of the framed document its one user turn carries, or
    contract/appraise_prompt's request_parts of a user turn holding a framed document, then the cards, then the
    claims (2.4) - so its instructions, schema and generation settings are this version's byte for byte and nothing
    rides along (no model, tool, thinking or safety field, no second turn, no original, no other user text).
    Otherwise ('', why not, in CPT Studio's words): UNPINNED_V2 when a pin of 2.5 does not match, else NOT_BUILT."""
    try:
        turn = body['contents'][0]['parts'][0]['text']
    except (KeyError, IndexError, TypeError):
        return '', NOT_BUILT
    if not isinstance(turn, str):
        return '', NOT_BUILT
    try:
        try:
            if body == extract_prompt.request_parts(turn):
                return EXTRACTION, ''
        except ValueError:  # not a framed document alone: it may be pass 2's turn
            pass
        if _appraisal_document(turn) is not None and body == appraise_prompt.request_parts(turn):
            return APPRAISAL, ''
    except RuntimeError:  # a pin: a changed instruction, schema or table with no new version (2.5)
        return '', UNPINNED_V2
    return '', NOT_BUILT


def _appraisal_document(turn: str) -> Optional[str]:
    """The framed document a pass-2 user turn opens with, when the turn has 2.4's form - the document as pass 1 frames
    it, a blank line, the cards under claims.CARDS_HEADING, a blank line and the claims under claims.CLAIMS_HEADING, no
    other blank line - else None. The framed document ends at the END marker line of its BEGIN line's mark: a text
    holding its own mark is never framed (extract_prompt.unframed), so the first such line ends it. RuntimeError when a
    pin of pass 1 does not match (extract_prompt.request_parts)."""
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
    try:
        extract_prompt.request_parts(document)
    except ValueError:  # what precedes the cards is not a document extract_prompt.framed gives
        return None
    return document


# --- the interpreters -------------------------------------------------------------------------------------------------

class InterpreterV2:
    """What design v2's live and replay interpreters share: both request kinds, their readers, and every refusal each
    makes about a request before anything is sent or replayed, so a replayed request takes the paths a live one takes.
    ``send_deadlines`` maps each purpose to its send deadline (EXTRACTION: settings.INTERPRETER_SEND_DEADLINE_SECONDS,
    APPRAISAL: settings.APPRAISER_SEND_DEADLINE_SECONDS; D49's 510 s each). A subclass gives ``mode``, ``endpoint`` (the
    URL it calls, '' for none) and ``_exchange``."""
    name = NAME
    adapter_version = ADAPTER_VERSION_V2
    requested_model = MODEL
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
        ``client_request_id`` is not sent (Google documents no such header) and ``original_bytes`` never are (D12)."""
        if not valid_deadline(deadline_s):
            return http.not_sent(INVALID_DEADLINE)
        problem, purpose = self._problem(request)
        if problem:
            return http.not_sent(problem)
        deadline = monotonic() + min(deadline_s, self.send_deadlines[purpose])
        return self._exchange(request.body, deadline, purpose)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str = '',
                  original_bytes: Optional[bytes] = None, execute_tool: Optional[Callable[..., Any]] = None,
                  should_stop: Optional[Callable[[], bool]] = None, carried: Sequence[Any] = ()) -> loop.LoopOutcome:
        """The run (jobs._send's looped branch), as v1's: participants.loop.run with exactly one exchange, within
        ``deadline_s`` and never more than the purpose's send deadline, recorded as turn 1. Refused before anything is
        sent - not_sent, no exchange recorded - for an invalid deadline, a request this interpreter does not send, a
        continuation (``carried``: there is none of one exchange) or a Stop check that is not callable. ``should_stop``
        is asked once, right before the request is sent: a Stop, or a check that raises, ends the run there, not sent
        and ``stopped``. No tool is offered: ``execute_tool`` is never called, and no answer is read as asking for one.
        A failed exchange - a bare 429 included - ends the run: it is never sent again (no automatic retry, D11)."""
        if not valid_deadline(deadline_s):
            return _refused(INVALID_DEADLINE)
        problem, purpose = self._problem(request)
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

        def post(turn: int, body: dict[str, Any], deadline: float) -> RawExchange:
            kind, problem = body_kind(body)
            return http.not_sent(problem, MODEL) if problem else self._exchange(body, deadline, kind)

        return loop.run(self, request, post=post, parse_turn=_no_tool_calls, follow_up=_no_follow_up,
                        execute_tool=_no_tools, deadline_s=deadline_s, longest_s=self.send_deadlines[purpose],
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


class GeminiInterpreterV2(InterpreterV2):
    """Design v2's live interpreter: one POST to ENDPOINT, the key read at send time, each purpose's own read timeout
    (``read_timeouts``: EXTRACTION settings.INTERPRETER_READ_TIMEOUT_SECONDS, APPRAISAL settings.
    APPRAISER_READ_TIMEOUT_SECONDS; D49's 480 s each)."""
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
        """One POST of a verified stored body: its exact canonical bytes, the key read now, nothing else, read within
        the purpose's read timeout."""
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
                         connect_timeout=self.connect_timeout, read_timeout=self.read_timeouts[purpose],
                         max_response_bytes=self.max_response_bytes, requested_model=MODEL)


def get_interpreter_v2(mode: Optional[str] = None) -> Optional[InterpreterV2]:
    """Design v2's configured interpreter (settings.GEMINI_MODE, or ``mode``), for step 5b's switch: None when it is
    disabled - nothing is sent, and the stage pauses - else the live or the replay interpreter, each purpose with its
    own settings (pass 1: INTERPRETER_SEND_DEADLINE_SECONDS and INTERPRETER_READ_TIMEOUT_SECONDS; pass 2:
    APPRAISER_SEND_DEADLINE_SECONDS and APPRAISER_READ_TIMEOUT_SECONDS, D49's, FINAL-V2 7.4 [R:MO-3]).
    Misconfiguration raises ProviderUnavailable; an unknown mode is a programming error (ValueError). Settings are read
    here, at call time, never at import."""
    from django.conf import settings

    mode = settings.GEMINI_MODE if mode is None else mode
    if mode == 'disabled':
        return None
    send_deadline = settings.INTERPRETER_SEND_DEADLINE_SECONDS
    appraisal_send_deadline = settings.APPRAISER_SEND_DEADLINE_SECONDS
    if mode == 'live':
        if not settings.GEMINI_CREDENTIALS_FILE:
            raise ProviderUnavailable('Live interpretation needs CPT_STUDIO_GEMINI_CREDENTIALS_FILE.')
        return GeminiInterpreterV2(settings.GEMINI_CREDENTIALS_FILE,
                                   connect_timeout=settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS,
                                   read_timeout=settings.INTERPRETER_READ_TIMEOUT_SECONDS,
                                   appraisal_read_timeout=settings.APPRAISER_READ_TIMEOUT_SECONDS,
                                   send_deadline=send_deadline, appraisal_send_deadline=appraisal_send_deadline)
    if mode == 'replay':
        if not settings.GEMINI_REPLAY_DIR:
            raise ProviderUnavailable('Replay interpretation needs CPT_STUDIO_GEMINI_REPLAY_DIR.')
        from studio.interpretation.replay import ReplayInterpreterV2

        return ReplayInterpreterV2(settings.GEMINI_REPLAY_DIR, send_deadline=send_deadline,
                                   appraisal_send_deadline=appraisal_send_deadline)
    raise ValueError(f'No design v2 interpreter exists for mode {mode!r}; expected disabled, live or replay.')
