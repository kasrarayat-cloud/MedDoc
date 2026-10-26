"""Corti coding adapter: the proven direct-prediction contract (ARCHITECTURE 5.4).

One send() makes one token request and at most one coding request: no retries,
no redirects, no environment proxies or .netrc. The token response is never
stored or returned. An outcome is 'not_sent' only while the coding request
provably has not left; once it may have reached Corti, a missing or incomplete
response is 'unknown' (sent), never a failure that invites a resend.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from contextlib import suppress
from datetime import date, datetime
from time import monotonic
from typing import Callable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import MaxRetryError, NewConnectionError

from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode, ProviderRequest, RawExchange

from .base import ProviderUnavailable, canonical_body, not_sent, valid_deadline, verified_body
from .credentials import CortiCredentials, CredentialsError, load_corti_credentials

NAME = 'corti'
ADAPTER_VERSION = 'corti-coding-v2@cptstudio-1'
SYSTEMS = ('icd10cm-outpatient', 'cpt')
MAX_SELECTED = 64
MAX_INFORMATIONAL = 256  # candidate and alternative codes one response may list (bounded:5)
MAX_EVIDENCE = 1024  # evidence passages one response may cite, over every code, candidate and alternative (round 7)
DEFAULT_MAX_REQUEST_BYTES = 512_000
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
USAGE_BASIS = 'provider_reported_credits_not_usd'
TOKEN_URL = 'https://auth.{environment}.corti.app/realms/{tenant}/protocol/openid-connect/token'
CODING_URL = 'https://api.{environment}.corti.app/v2/tools/coding/'
# Authentication must not spend the coding call's budget; the rebuild's proven token bound.
TOKEN_READ_TIMEOUT_S = 30
MAX_TOKEN_RESPONSE_BYTES = 64 * 1024
CHUNK_BYTES = 64 * 1024
_BEARER_TOKEN = re.compile(r'[A-Za-z0-9\-._~+/]+=*')  # RFC 6750 b64token
_REQUEST_ID = re.compile(r'[\x21-\x7e]{1,120}')  # fits ProviderRun.provider_request_id
_SURROGATE = re.compile('[\ud800-\udfff]')


def build_coding_request(provider: str, adapter_version: str, text: str, service_date: Optional[date],
                         max_bytes: int) -> ProviderRequest:
    """The proven request body. Over ``max_bytes`` it is refused, never truncated."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a string.')
    if service_date is not None and (not isinstance(service_date, date) or isinstance(service_date, datetime)):
        raise TypeError('The service date must be a datetime.date or None.')
    if not text.strip():
        raise ProviderUnavailable('The document has no text to send; nothing was sent.')
    if '\x00' in text:
        raise ProviderUnavailable('The document text contains NUL characters; nothing was sent.')
    contexts = (text,) if service_date is None else (text, f'Date of service: {service_date.isoformat()}')
    body = {'system': list(SYSTEMS), 'context': [{'type': 'text', 'text': item} for item in contexts]}
    try:
        encoded = canonical_body(body)
    except UnicodeEncodeError:
        raise ProviderUnavailable('The document text cannot be encoded as UTF-8; nothing was sent.') from None
    if len(encoded) > max_bytes:
        raise ProviderUnavailable(f'The request would be {len(encoded):,} bytes, over the {max_bytes:,}-byte '
                                  'limit; nothing was truncated or sent.')
    return ProviderRequest(provider=provider, adapter_version=adapter_version, body=body,
                           canonical_sha256=hashlib.sha256(encoded).hexdigest(), contexts=contexts)


def default_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # no environment proxies, CA overrides or .netrc credentials
    session.max_redirects = 0
    session.mount('https://', HTTPAdapter(max_retries=0))
    return session


class CortiProvider:
    name = NAME
    adapter_version = ADAPTER_VERSION
    mode = 'live'

    def __init__(self, credentials_path, *, connect_timeout: float = 10, read_timeout: float = 120,
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
        self.session_factory = session_factory or default_session

    def build_request(self, text: str, service_date: Optional[date]) -> ProviderRequest:
        return build_coding_request(self.name, self.adapter_version, text, service_date, self.max_request_bytes)

    def normalize(self, request: ProviderRequest, response_bytes: bytes) -> NormalizedResponse:
        return normalize_coding_response(self.name, request, response_bytes)

    def send(self, request: ProviderRequest, *, deadline_s: float) -> RawExchange:
        if not valid_deadline(deadline_s):
            return not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        deadline = monotonic() + deadline_s
        try:
            body = verified_body(request, self, self.max_request_bytes)
        except ProviderUnavailable as exc:
            return not_sent(str(exc))
        try:
            credentials = load_corti_credentials(self.credentials_path)
        except CredentialsError as exc:
            return not_sent(f'{exc} No coding request was sent.')
        try:
            session = self.session_factory()
        except Exception as exc:
            return not_sent(f'No HTTP session could be created ({type(exc).__name__}); nothing was sent.')
        try:
            token = self._authenticate(session, credentials, deadline)
            return self._predict(session, credentials, token, body, deadline)
        except _NotSent as exc:
            return not_sent(str(exc))
        finally:
            with suppress(Exception):
                session.close()

    def _timeouts(self, deadline: float, read_cap: float) -> Optional[tuple[float, float]]:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        return min(self.connect_timeout, remaining), min(read_cap, remaining)

    def _authenticate(self, session, credentials: CortiCredentials, deadline: float) -> str:
        """An access token. Every failure here is before the coding request, so it raises _NotSent."""
        timeouts = self._timeouts(deadline, min(TOKEN_READ_TIMEOUT_S, self.read_timeout))
        if timeouts is None:
            raise _NotSent('The deadline passed before Corti authentication; nothing was sent.')
        url = TOKEN_URL.format(environment=credentials.environment, tenant=credentials.tenant)
        form = {'client_id': credentials.client_id, 'client_secret': credentials.client_secret,
                'grant_type': 'client_credentials', 'scope': 'openid'}
        try:
            response = session.post(url, data=form, headers={'Accept': 'application/json'}, timeout=timeouts,
                                    allow_redirects=False, stream=True)
        except Exception as exc:
            raise _NotSent(f'Corti authentication failed ({type(exc).__name__}); '
                           'no coding request was sent.') from None
        try:
            status = response.status_code
            raw = _read_capped(response, MAX_TOKEN_RESPONSE_BYTES, deadline)
        except Exception as exc:
            raise _NotSent(f'The Corti authentication response could not be read ({_describe(exc)}); '
                           'no coding request was sent.') from None
        finally:
            with suppress(Exception):
                response.close()
        if status != 200:
            raise _NotSent(f'Corti authentication was refused (HTTP {status}); no coding request was sent.')
        token = _access_token(raw)
        if token is None:
            raise _NotSent('Corti authentication returned no usable bearer token; no coding request was sent.')
        return token

    def _predict(self, session, credentials: CortiCredentials, token: str, body: bytes,
                 deadline: float) -> RawExchange:
        timeouts = self._timeouts(deadline, self.read_timeout)
        if timeouts is None:
            raise _NotSent('The deadline passed before the coding request was sent; nothing was sent.')
        headers = {'Authorization': f'Bearer {token}', 'Tenant-Name': credentials.tenant,
                   'Content-Type': 'application/json', 'Accept': 'application/json'}
        started = monotonic()
        try:
            response = session.post(CODING_URL.format(environment=credentials.environment), data=body,
                                    headers=headers, timeout=timeouts, allow_redirects=False, stream=True)
        except Exception as exc:
            if _never_connected(exc):
                raise _NotSent(f'The Corti coding service could not be reached ({type(exc).__name__}); '
                               'nothing was sent.') from None
            return _unknown(exc, started)
        status, request_id = None, ''
        try:
            status = response.status_code
            request_id = _request_id(response.headers)
            raw = _read_capped(response, self.max_response_bytes, deadline)
        except Exception as exc:
            return _unknown(exc, started, status, request_id)
        finally:
            with suppress(Exception):
                response.close()
        latency = _elapsed_ms(started)
        usage = _usage(raw)
        error = ''
        if status != 200:
            redirect = ' (a redirect; it was not followed)' if 300 <= status < 400 else ''
            error = f'Corti answered HTTP {status}{redirect}; the response body is retained.'
        return RawExchange(outcome='succeeded' if status == 200 else 'failed', sent=True, http_status=status,
                           response_bytes=raw, response_sha256=hashlib.sha256(raw).hexdigest(),
                           latency_ms=latency, usage=usage, usage_basis=USAGE_BASIS if usage else '',
                           provider_request_id=request_id, error=error)


class _NotSent(Exception):
    """Raised inside send() while the coding request provably has not been written."""


class _BodyError(Exception):
    """A response body could not be read completely. The message is ours, never the provider's."""


def _never_connected(exc: Exception) -> bool:
    """True only when the TCP connection itself failed, so no request byte can have left."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    if not isinstance(exc, requests.exceptions.ConnectionError):
        return False
    cause = exc.args[0] if exc.args else None
    return isinstance(cause, MaxRetryError) and isinstance(cause.reason, NewConnectionError)


def _unknown(exc: Exception, started: float, status: Optional[int] = None, request_id: str = '') -> RawExchange:
    return RawExchange(outcome='unknown', sent=True, http_status=status, latency_ms=_elapsed_ms(started),
                       provider_request_id=request_id,
                       error=f'The coding request may have reached Corti, but no complete response was read '
                             f'({_describe(exc)}). The outcome is unknown; reconcile it before any new attempt.')


def _describe(exc: Exception) -> str:
    return str(exc) if isinstance(exc, _BodyError) else type(exc).__name__


def _read_capped(response, cap: int, deadline: float) -> bytes:
    chunks, size = [], 0
    for chunk in response.iter_content(CHUNK_BYTES):
        size += len(chunk)
        if size > cap:
            raise _BodyError(f'the response exceeded {cap:,} bytes')
        if monotonic() > deadline:
            raise _BodyError('the deadline passed while the response was being read')
        chunks.append(chunk)
    return b''.join(chunks)


def _elapsed_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 3)


def _request_id(headers) -> str:
    value = headers.get('X-Request-Id')
    return value if isinstance(value, str) and _REQUEST_ID.fullmatch(value) else ''


def _access_token(raw: bytes) -> Optional[str]:
    try:
        parsed = _strict_json(raw)
    except _JSONRefused:
        return None
    token = parsed.get('access_token') if isinstance(parsed, dict) else None
    return token if isinstance(token, str) and _BEARER_TOKEN.fullmatch(token) else None


def _usage(raw: bytes) -> dict:
    try:
        parsed = _strict_json(raw)
    except _JSONRefused:
        return {}
    usage = parsed.get('usageInfo') if isinstance(parsed, dict) else None
    return usage if isinstance(usage, dict) else {}


# --- strict JSON -------------------------------------------------------------------

class _JSONRefused(ValueError):
    pass


def _strict_json(raw: bytes):
    """Parse UTF-8 JSON, refusing what Python would otherwise accept silently or PostgreSQL
    could not store: duplicate keys, NaN/Infinity, overflowing numbers, NUL, unpaired surrogates."""
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise _JSONRefused('it is not valid UTF-8') from None
    try:
        value = json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_no_constant,
                           parse_float=_finite_float)
        unstorable = _unstorable(value)
    except _JSONRefused:
        raise
    except json.JSONDecodeError as exc:
        raise _JSONRefused(f'it is not valid JSON ({exc.msg} at character {exc.pos})') from None
    except (ValueError, RecursionError):
        raise _JSONRefused('it is not valid JSON') from None
    if unstorable:
        raise _JSONRefused('it contains NUL or unpaired surrogate characters')
    return value


def _entries(parsed: dict):
    """Every object entry of a parsed response that may cite evidence: its codes and candidates, and each one's
    alternatives (what _ResponseReader reads; a malformed entry is skipped here as there)."""
    for entry in parsed['codes'] + parsed['candidates']:
        if isinstance(entry, dict):
            yield entry
            alternatives = entry.get('alternatives')
            if isinstance(alternatives, list):
                yield from (alternative for alternative in alternatives if isinstance(alternative, dict))


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _JSONRefused('it repeats a JSON object key, so its meaning is ambiguous')
        result[key] = value
    return result


def _no_constant(name):
    raise _JSONRefused('it contains a non-finite number')


def _finite_float(literal: str) -> float:
    value = float(literal)
    if not math.isfinite(value):
        raise _JSONRefused('it contains a number too large to represent')
    return value


def _unstorable(value) -> bool:
    if isinstance(value, str):
        return '\x00' in value or _SURROGATE.search(value) is not None
    if isinstance(value, dict):
        return any(_unstorable(key) or _unstorable(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_unstorable(item) for item in value)
    return False


# --- normalization -------------------------------------------------------------------

def normalize_coding_response(provider: str, request: ProviderRequest, response_bytes) -> NormalizedResponse:
    """CPT-labelled codes (selected, candidate, alternative) and other systems as internal context.

    Nothing is promoted or merged: roles stay as the provider gave them, duplicates
    stay separate, and every evidence span's exactness is computed, never assumed.
    A response is only read as the provider and adapter version that recorded it,
    so a replayed response can never come out labelled as live output.
    """
    def refused(*reasons):
        return NormalizedResponse(provider=provider, adapter_version=ADAPTER_VERSION, refused=True,
                                  problems=tuple(f'The provider response was not used: {reason}.' for reason in reasons))

    if (request.provider, request.adapter_version) != (provider, ADAPTER_VERSION):
        return refused(f'it was recorded for {request.provider!r} with adapter {request.adapter_version!r}, '
                       f'not {provider!r} with {ADAPTER_VERSION!r}')
    if not isinstance(response_bytes, (bytes, bytearray)):
        return refused('there are no response bytes')
    try:
        parsed = _strict_json(bytes(response_bytes))
    except _JSONRefused as exc:
        return refused(str(exc))
    if not isinstance(parsed, dict):
        return refused('it is not a JSON object')
    missing = [f"it has no '{key}' list" for key in ('codes', 'candidates') if not isinstance(parsed.get(key), list)]
    if missing:
        return refused(*missing)
    if len(parsed['codes']) > MAX_SELECTED:
        return refused(f'it selects {len(parsed["codes"])} codes, more than the {MAX_SELECTED} this adapter accepts')
    # Candidates and every nested alternative become informational proposals, persisted and served row by row: an
    # uncapped list inside the 4 MiB response held the assess stage past its deadline in the worker (round 6
    # bounded:5: 70,000 candidates, 68 s in persist_assessment). The retained responses list 14 to 16.
    informational = len(parsed['candidates']) + sum(
        len(entry['alternatives']) for entry in parsed['codes'] + parsed['candidates']
        if isinstance(entry, dict) and isinstance(entry.get('alternatives'), list))
    if informational > MAX_INFORMATIONAL:
        return refused(f'it lists {informational} candidate and alternative codes, more than the '
                       f'{MAX_INFORMATIONAL} this adapter accepts')
    # Every evidence passage of every code, candidate and nested alternative is read in the assess stage: tens of
    # thousands of exact spans inside the 4 MiB response exhausted its memory after the request was sent (round 7
    # bounded:2). Refused whole and named by count, never truncated: dropping a passage could change a code's status
    # without the reviewer. The retained responses cite 32 to 45 passages in all.
    cited = sum(len(entry['evidences']) for entry in _entries(parsed) if isinstance(entry.get('evidences'), list))
    if cited > MAX_EVIDENCE:
        return refused(f'it cites {cited} evidence passages, more than the {MAX_EVIDENCE} this adapter accepts')
    reader = _ResponseReader(request.contexts)
    for role, key in (('selected', 'codes'), ('candidate', 'candidates')):
        for index, entry in enumerate(parsed[key]):
            reader.entry(role, f'{key}[{index}]', index, entry)
    return NormalizedResponse(provider=provider, adapter_version=ADAPTER_VERSION, codes=tuple(reader.cpt),
                              internal_context=tuple(reader.other), problems=tuple(reader.problems))


class _ResponseReader:
    """Collects entries in provider order; drops malformed ones with a problem naming where they were."""

    def __init__(self, contexts):
        self.contexts = tuple(contexts)
        self.cpt: list[ProviderCode] = []
        self.other: list[ProviderCode] = []
        self.problems: list[str] = []

    def entry(self, role: str, where: str, index: int, entry) -> None:
        if not isinstance(entry, dict):
            self.problems.append(f'{where} is not an object; it was dropped.')
            return
        system, code = entry.get('system'), _code(entry.get('code'))
        if not isinstance(system, str) or not system.strip():
            self.problems.append(f'{where} has no system label; it was dropped.')
            return
        if code is None:
            self.problems.append(f'{where} has no code; it was dropped.')
            return
        target = self.cpt if system.lower() == 'cpt' else self.other
        target.append(ProviderCode(role=role, system=system, code=code, display=_display(entry),
                                   evidence=self.evidence(where, entry), index=index))
        self.alternatives(where, entry, system, code, target)

    def alternatives(self, where: str, entry: dict, system: str, parent: str, target: list) -> None:
        alternatives = entry.get('alternatives')
        if alternatives is None:
            return
        if not isinstance(alternatives, list):
            self.problems.append(f'{where}.alternatives is not a list; it was dropped.')
            return
        for index, alternative in enumerate(alternatives):
            here = f'{where}.alternatives[{index}]'
            if not isinstance(alternative, dict):
                self.problems.append(f'{here} is not an object; it was dropped.')
                continue
            code = _code(alternative.get('code'))
            if code is None:
                self.problems.append(f'{here} has no code; it was dropped.')
                continue
            declared = alternative.get('system')
            if declared is not None and (not isinstance(declared, str) or declared.lower() != system.lower()):
                self.problems.append(f'{here} declares a system different from its parent; it was dropped.')
                continue
            target.append(ProviderCode(role='alternative', system=system, code=code, display=_display(alternative),
                                       evidence=self.evidence(here, alternative), parent_code=parent, index=index))

    def evidence(self, where: str, entry: dict) -> tuple[EvidenceSpan, ...]:
        raw = entry.get('evidences')
        if raw is None:
            return ()
        if not isinstance(raw, list):
            self.problems.append(f'{where}.evidences is not a list; it was dropped.')
            return ()
        spans = []
        for index, item in enumerate(raw):
            fields = item if isinstance(item, dict) else {}
            context_index, start, end, text = (fields.get(key) for key in ('contextIndex', 'start', 'end', 'text'))
            if not (all(type(value) is int for value in (context_index, start, end)) and isinstance(text, str)):
                self.problems.append(f'{where}.evidences[{index}] is malformed; it was dropped.')
                continue
            spans.append(EvidenceSpan(context_index=context_index, start=start, end=end, text=text,
                                      exact=_exact(self.contexts, context_index, start, end, text)))
        return tuple(spans)


def _code(value) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _display(entry: dict) -> str:
    display = entry.get('display')
    return display if isinstance(display, str) else ''


def _exact(contexts: tuple, context_index: int, start: int, end: int, text: str) -> bool:
    # Explicit bounds: Python would happily read a negative index from the other end.
    if not 0 <= context_index < len(contexts):
        return False
    source = contexts[context_index]
    return 0 <= start < end <= len(source) and source[start:end] == text
