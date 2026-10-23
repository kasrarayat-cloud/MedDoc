"""The proposal-provider contract (ARCHITECTURE 5.4) and mechanics every adapter shares.

A provider turns canonical document text into a request, sends it at most once
per call, and normalizes the raw bytes it got back. It never decides what a
code means: validation does that, separately.
"""
from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import stat
from datetime import date
from typing import Optional, Protocol, runtime_checkable

from studio.types import NormalizedResponse, ProviderRequest, RawExchange

OUTCOMES = ('succeeded', 'failed', 'unknown', 'not_sent')


class ProviderUnavailable(Exception):
    """The provider cannot take this request. Nothing was sent."""


@runtime_checkable
class ProposalProvider(Protocol):
    name: str
    adapter_version: str
    mode: str  # live | replay

    def build_request(self, text: str, service_date: Optional[date]) -> ProviderRequest: ...

    def send(self, request: ProviderRequest, *, deadline_s: float) -> RawExchange: ...

    def normalize(self, request: ProviderRequest, response_bytes: bytes) -> NormalizedResponse: ...


def canonical_body(body: dict) -> bytes:
    """The exact bytes a request body is hashed as, and sent as."""
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def request_sha256(body: dict) -> str:
    return hashlib.sha256(canonical_body(body)).hexdigest()


def not_sent(error: str) -> RawExchange:
    return RawExchange(outcome='not_sent', sent=False, error=error)


def valid_deadline(deadline_s) -> bool:
    return (isinstance(deadline_s, (int, float)) and not isinstance(deadline_s, bool)
            and math.isfinite(deadline_s) and deadline_s > 0)


def verified_body(request: ProviderRequest, provider, max_bytes: int) -> bytes:
    """Re-encode the request and prove it is still the request that was hashed and recorded."""
    if request.provider != provider.name or request.adapter_version != provider.adapter_version:
        raise ProviderUnavailable(
            'This request was built for a different provider or adapter version; nothing was sent.')
    try:
        body = canonical_body(request.body)
    except (TypeError, ValueError):
        raise ProviderUnavailable('The request body is not encodable JSON; nothing was sent.') from None
    if hashlib.sha256(body).hexdigest() != request.canonical_sha256:
        raise ProviderUnavailable('The request body does not match its recorded hash; nothing was sent.')
    if len(body) > max_bytes:
        raise ProviderUnavailable(
            f'The request is {len(body):,} bytes, over the {max_bytes:,}-byte limit; nothing was truncated or sent.')
    return body


class FileRefused(Exception):
    """A file was not read. ``reason`` is a fixed code; the message never quotes file content."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason  # missing | symlink | not_regular | shared_permissions | too_large | unreadable


def read_regular_file(path, max_bytes: int, *, owner_only: bool = False) -> bytes:
    """Read a regular file that is not a symlink, refusing anything over ``max_bytes``.

    O_NONBLOCK keeps a FIFO from blocking the open; it is then refused as not regular.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise FileRefused('missing') from None
    except OSError as exc:
        raise FileRefused('symlink' if exc.errno == errno.ELOOP else 'unreadable') from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise FileRefused('not_regular')
        if owner_only and info.st_mode & 0o077:
            raise FileRefused('shared_permissions')
        chunks, size = [], 0  # bounded by the read itself, so a file growing after fstat is still caught
        while True:
            chunk = os.read(fd, max_bytes + 1 - size)
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > max_bytes:
                raise FileRefused('too_large')
            chunks.append(chunk)
    except OSError:
        raise FileRefused('unreadable') from None
    finally:
        os.close(fd)
