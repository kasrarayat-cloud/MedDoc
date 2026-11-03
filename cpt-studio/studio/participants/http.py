"""The participants' one send discipline (HARNESS.md 3, 8), modelled exactly on Corti's (studio/providers/corti.py).

One send makes at most one POST: no retries, no redirects, no environment proxies or .netrc, connect and read timeouts
clamped to the remaining deadline, the deadline checked after every 64 KiB chunk read, the response capped, and the
exact raw bytes and their sha256 kept for a 200 and a non-200 alike. An outcome is 'not_sent' only while the request
provably has not left: an invalid deadline, a request that fails its own verification, an original file that does not
match the request, credentials that cannot be used, the deadline passing before the POST, or a connection that was
never established - on the default session, one whose TCP connect or TLS handshake never completed (refused, cut by the
connect timeout or the deadline, or a certificate the check refuses), since a watched connection is handed to the
exchange's watch before any byte of the request is written (refutation round 2, sends-r2-2). Once the request may have
reached the vendor, a missing or incomplete response is 'unknown' (sent), never a failure that invites a resend; a
non-200 is 'failed' with its body kept; a 200 is 'succeeded'.

Every read is bounded by the time the exchange has left (HTTP-TRICKLE, found by the part B integration agent): a read
timeout bounds each wait for a byte, never the whole read, so a response trickling in a byte at a time - its status
line, a header or its body - could hold an exchange past the loop's deadline and the stale-stage sweep. The default
session's connections are watched (_Watch): at the exchange's deadline the socket is shut down, whatever read is
blocked on it returns at once, and the outcome is 'unknown' (sent) - never a partial body taken for the answer.

Every exchange records what was called and what answered (HARNESS.md 6): the endpoint only when the request may have
reached it, the model the verified request names, and the model, id and usage the response body states, as stated.

A PDF original travels by reference (HARNESS.md 3). The stored request body holds {"$original_sha256": hex,
"$original_bytes": n} where the vendor's file data goes, and the request's sha256 is of that stored form. At send time
the given bytes are re-verified against both and only then expanded into the vendor's file block. A tool loop
(loop.py) sends every exchange through post() and re-verifies and expands the original on each exchange that carries
its placeholder.
"""
from __future__ import annotations

import contextvars
import copy
import dataclasses
import hashlib
import re
import socket
import threading
from contextlib import suppress
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Optional, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import MaxRetryError, NewConnectionError

from studio.participants import prompt
from studio.participants.reading import recorded_model, strict_json
from studio.providers import base
from studio.providers.base import ProviderUnavailable, canonical_body
from studio.types import PageSpan, ProviderRequest, RawExchange

CHUNK_BYTES = 64 * 1024
USAGE_BASIS = 'provider_reported_tokens'
ORIGINAL_SHA256, ORIGINAL_BYTES = '$original_sha256', '$original_bytes'
_SHA256 = re.compile(r'[0-9a-f]{64}')
_REQUEST_ID = re.compile(r'[\x21-\x7e]{1,120}')  # fits ProviderRun.provider_request_id
_RESPONSE_ID = re.compile(r'[\x21-\x7e]{1,140}')  # fits ProviderRun.response_id


@dataclass(frozen=True)
class Vendor:
    label: str  # how errors name the vendor
    request_id_header: str  # the response header carrying the vendor's own request id


def default_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # no environment proxies, CA overrides or .netrc credentials
    session.max_redirects = 0
    for prefix in ('https://', 'http://'):  # the vendors are https; every send keeps one discipline
        session.mount(prefix, _WatchedAdapter(max_retries=0))
    return session


# --- every read bounded by the time left (HTTP-TRICKLE) -------------------------------------------------------------

_WATCH: contextvars.ContextVar = contextvars.ContextVar('studio.participants.http.watch', default=None)


class _Watch:
    """One exchange's deadline over the sockets it connects. post() holds one for each exchange; a watched connection
    (the default session's) hands it its socket once connected - the connect timeout, clamped to the time left, bounds
    the connection and its TLS handshake - and at the deadline every socket handed over is shut down, so whatever read
    is blocked on it returns at once. The timer starts with the first socket and is cancelled and joined when the
    exchange ends (disarm), so no socket is touched after it. A socket handed over once the deadline has passed - the
    connection took the time that was left - is shut down and refused before the request is written (``unsent``):
    nothing left, so the outcome is not_sent, never an unknown outcome a member must reconcile.

    It also counts the watched connections the exchange began (``connecting``, before the TCP connect) and the sockets
    handed over: a connection that began and never handed its socket over failed in its TCP connect or its TLS
    handshake - refused, cut by the connect timeout (clamped to the time left) or by the deadline, or refused by the
    certificate check - before any byte of the request was written (``never_connected``; refutation round 2,
    sends-r2-2: such a failure surfaced as a read timeout or an SSL error and was taken for one after the request may
    have left)."""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.fired = False
        self.unsent = False
        self.began = 0  # watched connections the exchange began
        self.handed = 0  # sockets a watched connection handed over, once connected
        self._sockets = []
        self._timer = None
        self._done = False
        self._lock = threading.Lock()

    def connecting(self) -> None:
        """A watched connection begins (its TCP connect, then for https its TLS handshake): counted, so a connection
        that never hands its socket over is known never to have been established."""
        with self._lock:
            self.began += 1

    @property
    def never_connected(self) -> bool:
        """Whether a watched connection began and none was ever handed over: its TCP connect or TLS handshake never
        completed, so no byte of the request was written. False for a session whose connections are not watched (it
        begins none), whose failures keep the rules for a request that may have left."""
        with self._lock:
            return self.began > 0 and self.handed == 0

    def watch(self, sock) -> None:
        """Watch a connection's socket; a watched connection calls it once connected, before the request is written."""
        with self._lock:
            if self._done:
                return
            if self.fired or monotonic() >= self.deadline:
                self.fired = self.unsent = True
                _shutdown(sock)
                raise ConnectionAbortedError('the deadline passed before the request was sent')
            self.handed += 1
            self._sockets.append(sock)
            if self._timer is None:
                self._timer = threading.Timer(max(0.0, self.deadline - monotonic()), self._fire)
                self._timer.daemon = True
                self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            if self._done:
                return
            self.fired = True
            for sock in self._sockets:
                _shutdown(sock)

    def disarm(self) -> bool:
        """End the watch: nothing is shut down after this. Whether the deadline had already cut the exchange."""
        with self._lock:
            self._done = True
            self._sockets = []
            timer, fired = self._timer, self.fired
        if timer is not None:
            timer.cancel()
            timer.join()
        return fired

    def __enter__(self) -> '_Watch':
        self._token = _WATCH.set(self)
        return self

    def __exit__(self, *exc) -> bool:
        _WATCH.reset(self._token)
        self.disarm()
        return False


def _shutdown(sock) -> None:
    """Shut a connected socket down for both directions, which wakes a read blocked on it. The base socket's own
    method: an SSL socket's shutdown() would also drop its SSL object under the reader."""
    with suppress(Exception):
        socket.socket.shutdown(sock, socket.SHUT_RDWR)


def _watched(connection_class):
    class Watched(connection_class):
        def connect(self) -> None:
            watch = _WATCH.get()
            if watch is not None:
                watch.connecting()
            super().connect()
            if watch is not None:
                watch.watch(self.sock)
    Watched.__name__ = Watched.__qualname__ = f'Watched{connection_class.__name__}'
    return Watched


class _WatchedHTTPPool(HTTPConnectionPool):
    ConnectionCls = _watched(HTTPConnection)


class _WatchedHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _watched(HTTPSConnection)


class _WatchedAdapter(HTTPAdapter):
    """requests' adapter whose connections hand their sockets to the exchange's watch (_Watch)."""

    def init_poolmanager(self, *args, **kwargs) -> None:
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {'http': _WatchedHTTPPool, 'https': _WatchedHTTPSPool}


# --- the request ---------------------------------------------------------------------

def build_request(name: str, adapter_version: str, text: str, pages: Sequence[PageSpan], kind: str,
                  original: Optional[dict], *, max_bytes: int, make_body: Callable[[str, Optional[dict]], dict],
                  file_prefix: str) -> ProviderRequest:
    """A participant's request from the revision alone (HARNESS.md 3): its text framed with [Page N] lines and, for a
    PDF only, its original named by sha256 and size. Over ``max_bytes`` once the original is expanded it is refused,
    never truncated. Content that cannot be sent raises ProviderUnavailable; wrong argument types are programming
    errors (TypeError, ValueError)."""
    framed = framed_text(text, pages, kind, prompt.framed_document)
    holder = placeholder(original) if kind == 'pdf' else None  # only a PDF's original is attached (prompt.KINDS)
    return finished_request(name, adapter_version, make_body(framed, holder), text, max_bytes=max_bytes,
                            holder=holder, file_prefix=file_prefix)


def framed_text(text: str, pages: Sequence[PageSpan], kind: str, frame: Callable) -> str:
    """``frame(text, pages, kind)`` (prompt.framed_document, or its peer-review form) after the checks every
    participant request makes of the revision: content that cannot be sent raises ProviderUnavailable, wrong argument
    types raise TypeError or ValueError."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a string.')
    if not isinstance(pages, (tuple, list)) or not all(isinstance(page, PageSpan) for page in pages):
        raise TypeError('The pages must be a sequence of PageSpan.')
    if kind not in prompt.KINDS:
        raise ValueError(f'Unknown document kind {kind!r}; expected one of {", ".join(prompt.KINDS)}.')
    if not text.strip():
        raise ProviderUnavailable('The document has no text to send; nothing was sent.')
    if '\x00' in text:
        raise ProviderUnavailable('The document text contains NUL characters; nothing was sent.')
    framed = frame(text, tuple(pages), kind)
    if framed is None:
        reason = ('it contains its own framing marker' if prompt.marker(text) in text
                  else 'its pages do not cover it exactly')
        raise ProviderUnavailable(f'The document text cannot be framed: {reason}; nothing was sent.')
    return framed


def finished_request(name: str, adapter_version: str, body: dict, text: str, *, max_bytes: int,
                     holder: Optional[dict] = None, file_prefix: str = '') -> ProviderRequest:
    """The ProviderRequest for a built ``body`` whose quotes are located in ``text``: refused over ``max_bytes``
    once a PDF original (``holder``) is expanded, never truncated."""
    try:
        encoded = canonical_body(body)
    except UnicodeEncodeError:
        raise ProviderUnavailable('The document text cannot be encoded as UTF-8; nothing was sent.') from None
    size = len(encoded) if holder is None else expanded_length(len(encoded), holder, file_prefix)
    if size > max_bytes:
        with_file = ' with its original file' if holder is not None else ''
        raise ProviderUnavailable(f'The request{with_file} would be {size:,} bytes, over the {max_bytes:,}-byte limit; '
                                  'nothing was truncated or sent.')
    return ProviderRequest(provider=name, adapter_version=adapter_version, body=body,
                           canonical_sha256=hashlib.sha256(encoded).hexdigest(), contexts=(text,))


def placeholder(original) -> dict:
    """The stored stand-in for a PDF original: its sha256 and size, never its bytes."""
    if not isinstance(original, dict) or set(original) != {'sha256', 'bytes'}:
        raise TypeError("A PDF's original must be given as {'sha256': <hex>, 'bytes': <size>}.")
    sha256, size = original['sha256'], original['bytes']
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise ValueError("The original's sha256 must be 64 lowercase hexadecimal characters.")
    if type(size) is not int or size <= 0:
        raise ValueError("The original's size must be a positive whole number of bytes.")
    return {ORIGINAL_SHA256: sha256, ORIGINAL_BYTES: size}


def expanded_length(stored_length: int, holder: dict, file_prefix: str) -> int:
    """The canonical body's length once the placeholder is replaced by the JSON string ``file_prefix`` + base64."""
    return (stored_length - len(canonical_body(holder))
            + len(file_prefix) + 4 * ((holder[ORIGINAL_BYTES] + 2) // 3) + 2)


def check_shape(body, model: str, keys: frozenset) -> None:
    """A verified body is still one this adapter builds: exactly its fields, naming its model (HARNESS.md 8: the model
    is a code constant, and nothing else - no sampling, thinking or fallback field - can ride along)."""
    if not isinstance(body, dict) or set(body) != keys or body.get('model') != model:
        raise ProviderUnavailable('The request body is not one this adapter builds (its fields or its model differ); '
                                  'nothing was sent.')


def verify_original(body: dict, path: tuple, original_bytes) -> Optional[bytes]:
    """The original's bytes when the body names one, re-verified against its sha256 and size; None when it names none
    (any bytes given are then not sent). Raises ProviderUnavailable - nothing is sent - when the body names an original
    anywhere but ``path`` (where this vendor's file data goes), names it malformed, or the bytes do not match."""
    found = list(_placeholders(body))
    if not found:
        return None
    if len(found) != 1 or found[0][0] != path:
        raise ProviderUnavailable('The request names an original file where this adapter never puts one; '
                                  'nothing was sent.')
    holder = found[0][1]
    if (set(holder) != {ORIGINAL_SHA256, ORIGINAL_BYTES} or not isinstance(holder[ORIGINAL_SHA256], str)
            or type(holder[ORIGINAL_BYTES]) is not int):
        raise ProviderUnavailable("The request's original-file placeholder is malformed; nothing was sent.")
    if original_bytes is None:
        raise ProviderUnavailable('The request names an original file, but none was given; nothing was sent.')
    if not isinstance(original_bytes, (bytes, bytearray, memoryview)):
        raise ProviderUnavailable('The original file was not given as bytes; nothing was sent.')
    data = bytes(original_bytes)
    if len(data) != holder[ORIGINAL_BYTES] or hashlib.sha256(data).hexdigest() != holder[ORIGINAL_SHA256]:
        raise ProviderUnavailable('The original file does not match the sha256 and size the request names; '
                                  'nothing was sent.')
    return data


def expand_original(body: dict, path: tuple, original_bytes, render: Callable[[bytes], str]) -> dict:
    """The body to send: the stored body with its one placeholder replaced by ``render(original bytes)`` once they are
    verified (verify_original), or the stored body itself when it names no original."""
    data = verify_original(body, path, original_bytes)
    if data is None:
        return body
    expanded = copy.deepcopy(body)  # the strings are shared, not copied
    parent = expanded
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = render(data)
    return expanded


def _placeholders(body):
    """(path, node) of every object in ``body`` that carries a placeholder key, in no particular order."""
    pending = [((), body)]
    while pending:
        path, node = pending.pop()
        if isinstance(node, dict):
            if ORIGINAL_SHA256 in node or ORIGINAL_BYTES in node:
                yield path, node
                continue
            pending.extend((path + (key,), value) for key, value in node.items())
        elif isinstance(node, list):
            pending.extend((path + (index,), value) for index, value in enumerate(node))


def sendable(body: dict, max_bytes: int, *, with_original: bool = True) -> bytes:
    """The exact bytes sent: the canonical encoding (studio.providers.base) of the expanded body, refused over the
    limit, never truncated. ``with_original``: whether an original file was expanded into it (the message says so)."""
    data = canonical_body(body)
    if len(data) > max_bytes:
        with_file = ' with its original file' if with_original else ''
        raise ProviderUnavailable(f'The request{with_file} is {len(data):,} bytes, over the '
                                  f'{max_bytes:,}-byte limit; nothing was truncated or sent.')
    return data


# --- the exchange --------------------------------------------------------------------

def not_sent(error: str, requested_model: str = '') -> RawExchange:
    """base.not_sent, naming the model a verified request asks for ('' until the request is verified)."""
    return dataclasses.replace(base.not_sent(error), requested_model=requested_model)


def post(vendor: Vendor, session_factory: Callable[[], requests.Session], url: str, body: bytes, headers: dict, *,
         deadline: float, connect_timeout: float, read_timeout: float, max_response_bytes: int,
         requested_model: str) -> RawExchange:
    """The one POST of a send, under the discipline above."""
    try:
        session = session_factory()
    except Exception as exc:
        return not_sent(f'No HTTP session could be created ({type(exc).__name__}); nothing was sent.', requested_model)
    try:
        timeouts = _timeouts(deadline, connect_timeout, read_timeout)
        if timeouts is None:
            return not_sent('The deadline passed before the request was sent; nothing was sent.', requested_model)
        started = monotonic()
        with _Watch(deadline) as watch:
            try:
                response = session.post(url, data=body, headers=headers, timeout=timeouts, allow_redirects=False,
                                        stream=True)
            except Exception as exc:
                if watch.disarm() and watch.unsent:
                    return not_sent('The deadline passed before the request was sent; nothing was sent.',
                                    requested_model)
                if watch.never_connected:  # asked before the rules for a request that may have left: none was written
                    if monotonic() >= deadline:  # the clamped connect timeout: the connection took the time left
                        return not_sent('The deadline passed before the request was sent; nothing was sent.',
                                        requested_model)
                    return not_sent(f'{vendor.label} could not be reached ({type(exc).__name__}); nothing was sent.',
                                    requested_model)
                if watch.fired:
                    return _unknown(vendor, _BodyError(DEADLINE_READING), started, url, requested_model)
                if _never_connected(exc):
                    return not_sent(f'{vendor.label} could not be reached ({type(exc).__name__}); nothing was sent.',
                                    requested_model)
                return _unknown(vendor, exc, started, url, requested_model)
            status, request_id = None, ''
            try:
                status = response.status_code
                request_id = _request_id(response.headers, vendor.request_id_header)
                raw = _read_capped(response, max_response_bytes, deadline)
                if watch.disarm():  # the deadline cut the read: what was read is not the whole answer
                    raise _BodyError(DEADLINE_READING)
            except Exception as exc:
                if watch.disarm():
                    exc = _BodyError(DEADLINE_READING)
                return _unknown(vendor, exc, started, url, requested_model, status, request_id)
            finally:
                with suppress(Exception):
                    response.close()
        latency = _elapsed_ms(started)
        usage, returned_model, response_id = describe(raw)
        error = ''
        if status != 200:
            redirect = ' (a redirect; it was not followed)' if isinstance(status, int) and 300 <= status < 400 else ''
            error = f'{vendor.label} answered HTTP {status}{redirect}; the response body is retained.'
        return RawExchange(outcome='succeeded' if status == 200 else 'failed', sent=True, http_status=status,
                           response_bytes=raw, response_sha256=hashlib.sha256(raw).hexdigest(), latency_ms=latency,
                           usage=usage, usage_basis=USAGE_BASIS if usage else '', provider_request_id=request_id,
                           error=error, endpoint=url, requested_model=requested_model,
                           returned_model=returned_model, response_id=response_id)
    finally:
        with suppress(Exception):
            session.close()


def describe(raw: bytes) -> tuple[dict, str, str]:
    """(usage, model, id) as a response body states them, each {} or '' when it states none that fits the record. Both
    vendors put all three at the top level. It never raises: what a response says never changes its outcome."""
    try:
        parsed = strict_json(raw)
    except Exception:  # JSONRefused, or bytes that are not bytes: either way the body states nothing usable
        return {}, '', ''
    if not isinstance(parsed, dict):
        return {}, '', ''
    usage, model, response_id = parsed.get('usage'), parsed.get('model'), parsed.get('id')
    return (usage if isinstance(usage, dict) else {}, recorded_model(model),
            response_id if isinstance(response_id, str) and _RESPONSE_ID.fullmatch(response_id) else '')


class _BodyError(Exception):
    """A response body could not be read completely. The message is ours, never the vendor's."""


def _timeouts(deadline: float, connect_timeout: float, read_timeout: float) -> Optional[tuple[float, float]]:
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None
    return min(connect_timeout, remaining), min(read_timeout, remaining)


def _never_connected(exc: Exception) -> bool:
    """True only when the TCP connection itself failed, so no request byte can have left."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    if not isinstance(exc, requests.exceptions.ConnectionError):
        return False
    cause = exc.args[0] if exc.args else None
    return isinstance(cause, MaxRetryError) and isinstance(cause.reason, NewConnectionError)


def _unknown(vendor: Vendor, exc: Exception, started: float, url: str, requested_model: str,
             status: Optional[int] = None, request_id: str = '') -> RawExchange:
    return RawExchange(outcome='unknown', sent=True, http_status=status, latency_ms=_elapsed_ms(started),
                       provider_request_id=request_id, endpoint=url, requested_model=requested_model,
                       error=f'The request may have reached {vendor.label}, but no complete response was read '
                             f'({_describe(exc)}). The outcome is unknown; reconcile it before any new attempt.')


def _describe(exc: Exception) -> str:
    return str(exc) if isinstance(exc, _BodyError) else type(exc).__name__


DEADLINE_READING = 'the deadline passed while the response was being read'


def _read_capped(response, cap: int, deadline: float) -> bytes:
    chunks, size = [], 0
    for chunk in response.iter_content(CHUNK_BYTES):
        size += len(chunk)
        if size > cap:
            raise _BodyError(f'the response exceeded {cap:,} bytes')
        if monotonic() > deadline:
            raise _BodyError(DEADLINE_READING)
        chunks.append(chunk)
    return b''.join(chunks)


def _elapsed_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 3)


def _request_id(headers, name: str) -> str:
    value = headers.get(name)
    return value if isinstance(value, str) and _REQUEST_ID.fullmatch(value) else ''
