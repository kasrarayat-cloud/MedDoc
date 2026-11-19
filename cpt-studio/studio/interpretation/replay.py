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

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 7.4 and 9.3; step 3b of its 8.1) adds ReplayInterpreterV2 beside v1's
ReplayInterpreter, which keeps every name and behaviour: the replay of BOTH of design v2's request kinds - pass 1
(purpose 'interpretation') and pass 2 (purpose 'appraisal') - each keyed by its own request's canonical sha256 in the
same folder, GEMINI_REPLAY_DIR/gemini/<request sha256>.json, and read exactly as a live answer of its kind is
(adapter.read_extraction, adapter.read_appraisal). Its requests are built, and refused, by adapter.InterpreterV2's own
code, so a replayed request of either kind takes the paths a live one takes. Both interpreters read a recording by one
code path (_Recordings).

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md 1.8; the interpreter is Claude Fable 5.2, D275) adds
ReplayInterpreterF beside them, for fable_adapter.InterpreterF's two request kinds: a recording is the raw SSE stream of
a complete 200 answer, GEMINI_REPLAY_DIR/anthropic/<request sha256>.sse (_Recordings takes the folder and the suffix
from its interpreter, so Gemini's stay GEMINI_REPLAY_DIR/gemini/<sha>.json), replayed with sent False, no usage, the
replay usage basis and the model and message id fable_adapter.describe reads. The replay applies the stream's end test
too (fable_adapter.complete): a recorded stream that did not reach its end replays as an unknown outcome with its
bytes, the path a live one takes (1.3), never as an answer.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from studio.interpretation import adapter, fable_adapter
from studio.participants import http
from studio.providers.base import FileRefused, read_regular_file, request_sha256
from studio.types import RawExchange

USAGE_BASIS = 'historical_replay_not_new_usage'
# AMENDMENT-2 1.8: a recorded stream that did not reach its end replays as the unknown outcome a live one records (1.3)
INCOMPLETE_RECORDING = ('The recorded answer stream ended before its end event. The outcome is unknown; reconcile it '
                        'before any new attempt.')


class _Recordings:
    """Reading one recording, for every replay interpreter alike: ``replay_dir`` and ``max_response_bytes`` are the
    interpreter's, and so are where its recordings are and how they are read (AMENDMENT-2 1.8): ``recording_folder``
    (the provider's folder under the replay directory), ``recording_suffix`` (.json for Gemini's raw answers, .sse for
    Fable's raw streams), ``vendor`` (whose describe hook reads the recording's model and id, and whose end test, when it
    names one, decides whether the recording is a whole answer) and ``requested_model``."""
    replay_dir: Path
    max_response_bytes: int
    recording_folder: str
    recording_suffix: str
    vendor: http.Vendor
    requested_model: str

    def recorded(self, sha256: str) -> RawExchange:
        """The recorded answer to the request whose canonical sha256 is ``sha256``, as a replayed exchange; not_sent, with
        why, when there is none to read; for a vendor with an end test, a recording that did not reach its end is an
        unknown outcome with its bytes kept (AMENDMENT-2 1.8), as a live stream that ended early is."""
        folder = self.replay_dir / self.recording_folder
        if not folder.is_dir():
            return http.not_sent('The replay directory is not available.', self.requested_model)
        try:
            raw = read_regular_file(folder / f'{sha256}{self.recording_suffix}', self.max_response_bytes)
        except FileRefused as exc:
            return http.not_sent(self._refusal(exc.reason), self.requested_model)
        _, returned_model, response_id = http.described(self.vendor, raw)
        ended = self.vendor.complete
        outcome, error = 'succeeded', ''
        if ended is not None and not _ended(ended, raw):
            outcome, error = 'unknown', INCOMPLETE_RECORDING
        return RawExchange(outcome=outcome, sent=False, response_bytes=raw,
                           response_sha256=hashlib.sha256(raw).hexdigest(), usage={}, usage_basis=USAGE_BASIS,
                           error=error, requested_model=self.requested_model, returned_model=returned_model,
                           response_id=response_id)

    def _refusal(self, reason: str) -> str:
        return {
            'missing': 'No recorded response for this request.',
            'symlink': 'The recorded response is a symbolic link; it was refused.',
            'not_regular': 'The recorded response is not a regular file.',
            'too_large': f'The recorded response is larger than {self.max_response_bytes:,} bytes.',
        }.get(reason, 'The recorded response cannot be read.')


def _ended(complete, raw: bytes) -> bool:
    """Whether a vendor's end test says a recording reached its stream's end; a test that raises says it did not."""
    try:
        return complete(raw) is True
    except Exception:  # noqa: BLE001 - a recording's bytes never raise out of a replay
        return False


class ReplayInterpreter(_Recordings, adapter.Interpreter):
    mode = 'replay'
    endpoint = ''  # a replay calls nothing
    recording_folder, recording_suffix, vendor = adapter.NAME, '.json', adapter.VENDOR

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


class ReplayInterpreterV2(_Recordings, adapter.InterpreterV2):
    """Design v2's replay interpreter: both request kinds (pass 1, 'interpretation'; pass 2, 'appraisal'), each answered
    by the recording keyed by its own request's canonical sha256 (FINAL-V2 7.4: replay works for pass 2 exactly as for
    pass 1), with nothing sent, no credentials and no network. Every refusal adapter.InterpreterV2 makes of a request -
    an invalid deadline, another provider or adapter version (v1's included), an altered or oversized body, a body of
    neither kind, a continuation, a member's Stop - is made before any recording is read."""
    mode = 'replay'
    endpoint = ''  # a replay calls nothing
    recording_folder, recording_suffix, vendor = adapter.NAME, '.json', adapter.VENDOR

    def __init__(self, replay_dir: Any, *, send_deadline: float = adapter.SEND_DEADLINE_SECONDS,
                 appraisal_send_deadline: float = adapter.APPRAISAL_SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = adapter.DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = adapter.DEFAULT_MAX_RESPONSE_BYTES) -> None:
        if not replay_dir:
            raise ValueError('A replay directory is required; an empty path would mean the working directory.')
        super().__init__(send_deadline=send_deadline, appraisal_send_deadline=appraisal_send_deadline,
                         max_request_bytes=max_request_bytes, max_response_bytes=max_response_bytes)
        self.replay_dir = Path(replay_dir)

    def _exchange(self, body: dict[str, Any], deadline: float, purpose: str) -> RawExchange:
        """The recording keyed by the sha256 of ``body`` in its stored form - the request's own, whichever its kind."""
        return self.recorded(request_sha256(body))


class ReplayInterpreterF(_Recordings, fable_adapter.InterpreterF):
    """AMENDMENT-2's replay interpreter (1.8): both of fable_adapter's request kinds (pass 1, 'interpretation'; pass 2,
    'appraisal'), each answered by the recording keyed by its own request's canonical sha256 -
    GEMINI_REPLAY_DIR/anthropic/<sha256>.sse, the raw stream of a complete 200 answer (fable_adapter.InterpreterF names
    the folder and the suffix) - with nothing sent, no credentials and no network. Every refusal
    fable_adapter.InterpreterF makes of a request - an invalid deadline, another provider or adapter version (Gemini's
    included), an altered or oversized body, a body of neither kind, a continuation, a member's Stop - is made before any
    recording is read; a recording that did not reach its end replays as an unknown outcome (_Recordings.recorded)."""
    mode = 'replay'
    endpoint = ''  # a replay calls nothing

    def __init__(self, replay_dir: Any, *, send_deadline: float = fable_adapter.SEND_DEADLINE_SECONDS,
                 appraisal_send_deadline: float = fable_adapter.APPRAISAL_SEND_DEADLINE_SECONDS,
                 max_request_bytes: int = fable_adapter.DEFAULT_MAX_REQUEST_BYTES,
                 max_response_bytes: int = fable_adapter.DEFAULT_MAX_RESPONSE_BYTES) -> None:
        if not replay_dir:
            raise ValueError('A replay directory is required; an empty path would mean the working directory.')
        super().__init__(send_deadline=send_deadline, appraisal_send_deadline=appraisal_send_deadline,
                         max_request_bytes=max_request_bytes, max_response_bytes=max_response_bytes)
        self.replay_dir = Path(replay_dir)

    def _exchange(self, body: dict[str, Any], deadline: float, purpose: str) -> RawExchange:
        """The recording keyed by the sha256 of ``body`` in its stored form - the request's own, whichever its kind."""
        return self.recorded(request_sha256(body))
