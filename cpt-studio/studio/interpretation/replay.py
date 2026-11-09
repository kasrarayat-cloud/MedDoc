"""Replay of recorded Gemini answers, for tests and development only (design/FINAL.md 3.1; as participants/replay.py).

A replayed exchange sends nothing and reports no new usage: ``sent`` is False, the usage basis is
'historical_replay_not_new_usage', and its endpoint is '' because nothing was called. The request is built by the live
adapter's own code (adapter.Interpreter), so a recording is keyed by the canonical sha256 a live request for the same
revision carries - GEMINI_REPLAY_DIR/gemini/<request sha256>.json, the raw body of a 200 answer - and it is read
exactly as a live answer is (adapter.answer_text, then interpretation.read). The returned model and the response id are
those the recording states (adapter.describe).

Every refusal a live send makes about the request itself is made here too - an invalid deadline, a request of another
provider or adapter version, one altered since it was hashed or over the size limit, a body the adapter never builds, a
continuation, a member's Stop before the send - so a replayed request takes the paths a live one takes; credentials and
the network are never involved.

A replayed run carries the live adapter's provider and version, with mode 'replay'. Where reuse matches a retained
answer by provider, adapter version, request sha256 and mode, a replayed answer is never taken for a live one.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from studio.interpretation import adapter
from studio.participants import http
from studio.providers.base import FileRefused, read_regular_file, request_sha256
from studio.types import RawExchange

USAGE_BASIS = 'historical_replay_not_new_usage'


class ReplayInterpreter(adapter.Interpreter):
    mode = 'replay'
    endpoint = ''  # a replay calls nothing

    def __init__(self, replay_dir, *, send_deadline: float = adapter.SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = adapter.DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = adapter.DEFAULT_MAX_RESPONSE_BYTES):
        if not replay_dir:
            raise ValueError('A replay directory is required; an empty path would mean the working directory.')
        super().__init__(send_deadline=send_deadline, max_request_bytes=max_request_bytes,
                         max_response_bytes=max_response_bytes)
        self.replay_dir = Path(replay_dir)

    def _exchange(self, body: dict, deadline: float) -> RawExchange:
        """The recording keyed by the sha256 of ``body`` in its stored form - the request's own, for the one exchange."""
        return self.recorded(request_sha256(body))

    def recorded(self, sha256: str) -> RawExchange:
        """The recorded answer to the request whose canonical sha256 is ``sha256``, as a replayed exchange; not_sent, with
        why, when there is none to read."""
        folder = self.replay_dir / adapter.NAME
        if not folder.is_dir():
            return http.not_sent('The replay directory is not available.', adapter.MODEL)
        try:
            raw = read_regular_file(folder / f'{sha256}.json', self.max_response_bytes)
        except FileRefused as exc:
            return http.not_sent(self._refusal(exc.reason), adapter.MODEL)
        _, returned_model, response_id = http.described(adapter.VENDOR, raw)
        return RawExchange(outcome='succeeded', sent=False, response_bytes=raw,
                           response_sha256=hashlib.sha256(raw).hexdigest(), usage={}, usage_basis=USAGE_BASIS,
                           requested_model=adapter.MODEL, returned_model=returned_model, response_id=response_id)

    def _refusal(self, reason: str) -> str:
        return {
            'missing': 'No recorded response for this request.',
            'symlink': 'The recorded response is a symbolic link; it was refused.',
            'not_regular': 'The recorded response is not a regular file.',
            'too_large': f'The recorded response is larger than {self.max_response_bytes:,} bytes.',
        }.get(reason, 'The recorded response cannot be read.')
