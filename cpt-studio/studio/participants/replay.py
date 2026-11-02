"""Replay of recorded participant answers, for tests and development only (HARNESS.md 8).

A replayed exchange sends nothing and reports no new usage: sent is False, the usage basis is
'historical_replay_not_new_usage', and its endpoint is '' because nothing was called. Requests are built and answers
read by the live adapter's own code, so a recording is keyed by the canonical hash a live request for the same input
carries - PARTICIPANT_REPLAY_DIR/<participant>/<request sha256>.json - and is read exactly as a live answer would be.

A replayed tool loop (send_loop, HARNESS.md 11.2) runs loop.run with the live adapter's parse_turn and follow_up, so
each exchange's request is the one the live loop would make, and each exchange replays the recording keyed by THAT
exchange's stored-request sha256: with the same recordings and the same tool results, a replayed loop is deterministic,
exchange by exchange. A loop whose recording for a later exchange is missing fails there, as a live loop whose later
exchange cannot be sent does. A replayed loop's usage is {} with the replay basis, never summed as new usage.

The refusals a live send makes about the request itself are made here too (an invalid deadline, a request that
fails its verification or is not one the adapter builds, an original that does not match the request - re-verified on
every exchange of a loop that carries it), so a replayed request takes the paths a live one takes; credentials and the
network are never involved.

A replayed run carries the live adapter's provider and version. Where reuse matches a retained answer by provider,
adapter version and request sha256, a replayed answer (this usage basis) is not a live one and must not stand in for
one.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from studio.participants import PARTICIPANTS, anthropic_fable, http, loop, openai_astra, peer
from studio.providers.base import (FileRefused, ProviderUnavailable, read_regular_file, request_sha256, valid_deadline,
                                   verified_body)
from studio.types import ParticipantReading, PeerReview, ProviderRequest, RawExchange

USAGE_BASIS = 'historical_replay_not_new_usage'
_LIVE = {openai_astra.NAME: openai_astra, anthropic_fable.NAME: anthropic_fable}


class ReplayParticipant:
    mode = 'replay'
    endpoint = ''  # a replay calls nothing

    def __init__(self, name: str, replay_dir, *, max_request_bytes: int = 24 * 1024 * 1024,
                 max_response_bytes: int = 4 * 1024 * 1024, max_exchanges: int = 4, loop_deadline: float = 540,
                 max_tool_result_bytes: int = 256 * 1024):
        if name not in PARTICIPANTS:
            raise ValueError(f'Unknown participant {name!r}.')
        if not replay_dir:
            raise ValueError('A replay directory is required; an empty path would mean the working directory.')
        if not valid_deadline(loop_deadline):
            raise ValueError('loop_deadline must be a positive number of seconds.')
        for label, limit in (('max_exchanges', max_exchanges), ('max_tool_result_bytes', max_tool_result_bytes)):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'{label} must be a positive integer.')
        self.live = _LIVE[name]
        self.name = name
        self.adapter_version = self.live.ADAPTER_VERSION
        self.requested_model = self.live.MODEL
        self.replay_dir = Path(replay_dir)
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.max_exchanges = max_exchanges
        self.loop_deadline = loop_deadline
        self.max_tool_result_bytes = max_tool_result_bytes

    def build_request(self, text, pages, kind, original) -> ProviderRequest:
        return http.build_request(self.name, self.adapter_version, text, pages, kind, original,
                                  max_bytes=self.max_request_bytes, make_body=self.live.request_body,
                                  file_prefix=self.live.FILE_PREFIX)

    def build_peer_request(self, text, pages, kind, own, peers, cpt_studio, frozen) -> ProviderRequest:
        return peer.build_request(self.name, self.adapter_version, text, pages, kind, own, peers, cpt_studio, frozen,
                                  max_bytes=self.max_request_bytes, make_body=self.live.peer_request_body)

    def read(self, request: ProviderRequest, response_bytes: bytes, refs_retrieved=frozenset()) -> ParticipantReading:
        return self.live.read_response(request, response_bytes, refs_retrieved)

    def read_peer(self, request: ProviderRequest, response_bytes: bytes, refs_retrieved=frozenset()) -> PeerReview:
        return self.live.read_peer(request, response_bytes, refs_retrieved)

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
             original_bytes) -> RawExchange:
        if not valid_deadline(deadline_s):
            return http.not_sent('The send deadline must be a positive number of seconds; nothing was sent.')
        try:
            verified_body(request, self, self.max_request_bytes)  # proves the hash, which names the recording
            http.check_shape(request.body, self.requested_model, self.live.BODY_KEYS)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc))
        try:
            http.verify_original(request.body, self.live.ORIGINAL_PATH, original_bytes)
        except ProviderUnavailable as exc:
            return http.not_sent(str(exc), self.requested_model)
        return self._recorded(request.canonical_sha256)

    def send_loop(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str, original_bytes,
                  execute_tool) -> loop.LoopOutcome:
        """The live loop's exchanges, each replayed from the recording keyed by its own stored request's sha256."""
        def post(turn: int, body: dict, deadline: float) -> RawExchange:
            try:
                http.check_shape(body, self.requested_model, self.live.BODY_KEYS)
                http.verify_original(body, self.live.ORIGINAL_PATH, original_bytes)
            except ProviderUnavailable as exc:
                return http.not_sent(str(exc), self.requested_model)
            return self._recorded(request_sha256(body))

        return loop.run(self, request, post=post, parse_turn=self.live.parse_turn, follow_up=self.live.follow_up,
                        execute_tool=execute_tool, deadline_s=deadline_s, longest_s=self.loop_deadline,
                        max_exchanges=self.max_exchanges, max_tool_result_bytes=self.max_tool_result_bytes,
                        max_request_bytes=self.max_request_bytes, body_keys=self.live.BODY_KEYS)

    def _recorded(self, sha256: str) -> RawExchange:
        folder = self.replay_dir / self.name
        if not folder.is_dir():
            return http.not_sent('The replay directory is not available.', self.requested_model)
        try:
            raw = read_regular_file(folder / f'{sha256}.json', self.max_response_bytes)
        except FileRefused as exc:
            return http.not_sent(self._refusal(exc.reason), self.requested_model)
        _, returned_model, response_id = http.describe(raw)
        return RawExchange(outcome='succeeded', sent=False, response_bytes=raw,
                           response_sha256=hashlib.sha256(raw).hexdigest(), usage={}, usage_basis=USAGE_BASIS,
                           requested_model=self.requested_model, returned_model=returned_model,
                           response_id=response_id)

    def _refusal(self, reason: str) -> str:
        return {
            'missing': 'No recorded response for this request.',
            'symlink': 'The recorded response is a symbolic link; it was refused.',
            'not_regular': 'The recorded response is not a regular file.',
            'too_large': f'The recorded response is larger than {self.max_response_bytes:,} bytes.',
        }.get(reason, 'The recorded response cannot be read.')
