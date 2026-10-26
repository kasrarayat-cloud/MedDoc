"""Replay of recorded Corti responses, for tests and development only (ARCHITECTURE 5.4).

A replayed run can never present as live output: it is stored with provider
'replay', sends nothing and reports no new usage. Requests are built and
responses normalized by the Corti adapter's own code, so a recording is keyed by
the canonical hash a live request for the same input carries.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Optional

from studio.types import NormalizedResponse, ProviderRequest, RawExchange

from .base import FileRefused, ProviderUnavailable, not_sent, read_regular_file, valid_deadline, verified_body
from .corti import (ADAPTER_VERSION, DEFAULT_MAX_REQUEST_BYTES, DEFAULT_MAX_RESPONSE_BYTES, build_coding_request,
                    normalize_coding_response)

USAGE_BASIS = 'historical_replay_not_new_usage'


class ReplayProvider:
    name = 'replay'
    adapter_version = ADAPTER_VERSION
    mode = 'replay'

    def __init__(self, replay_dir, *, max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES):
        if not replay_dir:
            raise ValueError('A replay directory is required; an empty path would mean the working directory.')
        self.replay_dir = Path(replay_dir)
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes

    def build_request(self, text: str, service_date: Optional[date]) -> ProviderRequest:
        return build_coding_request(self.name, self.adapter_version, text, service_date, self.max_request_bytes)

    def normalize(self, request: ProviderRequest, response_bytes: bytes) -> NormalizedResponse:
        return normalize_coding_response(self.name, request, response_bytes)

    def send(self, request: ProviderRequest, *, deadline_s: float) -> RawExchange:
        if not valid_deadline(deadline_s):
            return not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        try:
            verified_body(request, self, self.max_request_bytes)  # proves the hash, which names the recording
        except ProviderUnavailable as exc:
            return not_sent(str(exc))
        if not self.replay_dir.is_dir():
            return not_sent('The replay directory is not available.')
        try:
            raw = read_regular_file(self.replay_dir / f'{request.canonical_sha256}.json', self.max_response_bytes)
        except FileRefused as exc:
            return not_sent(self._refusal(exc.reason))
        return RawExchange(outcome='succeeded', sent=False, response_bytes=raw,
                           response_sha256=hashlib.sha256(raw).hexdigest(), usage={}, usage_basis=USAGE_BASIS)

    def _refusal(self, reason: str) -> str:
        return {
            'missing': 'No recorded response for this request.',
            'symlink': 'The recorded response is a symbolic link; it was refused.',
            'not_regular': 'The recorded response is not a regular file.',
            'too_large': f'The recorded response is larger than {self.max_response_bytes:,} bytes.',
        }.get(reason, 'The recorded response cannot be read.')
