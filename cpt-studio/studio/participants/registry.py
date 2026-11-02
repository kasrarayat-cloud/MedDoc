"""Which adapter serves a configured participant, and which reader reads a stored run (HARNESS.md 8, 11).

``build`` is the only place the participant adapters read Django settings; nothing here touches settings at import
time, and nothing reads a credential: a live adapter reads its file at send time, in the worker that mounts it.
``reader`` and ``peer_reader`` need no settings at all.
"""
from __future__ import annotations

from typing import Callable

from studio.participants import PARTICIPANTS, anthropic_fable, openai_astra
from studio.participants.replay import ReplayParticipant
from studio.providers.base import ProviderUnavailable
from studio.types import ParticipantReading, PeerReview

_ADAPTERS = {openai_astra.NAME: openai_astra.AstraParticipant, anthropic_fable.NAME: anthropic_fable.FableParticipant}
_CREDENTIALS = {openai_astra.NAME: ('OPENAI_CREDENTIALS_FILE', 'Astra'),
                anthropic_fable.NAME: ('ANTHROPIC_CREDENTIALS_FILE', 'Fable')}
# A stored first reading is read by the version that recorded it: harness@2's, or harness@1's exactly as before.
_READERS = {(module.NAME, version): module.read_response
            for module in (openai_astra, anthropic_fable) for version in module.READ_VERSIONS}
# Only harness@2 has a peer review (HARNESS.md 11.1).
_PEER_READERS = {(module.NAME, module.ADAPTER_VERSION): module.read_peer for module in (openai_astra, anthropic_fable)}


def build(name: str, mode: str):
    """The adapter for participant ``name`` in ``mode`` ('live' or 'replay'). Misconfiguration raises
    ProviderUnavailable; an unknown participant or mode is a programming error (ValueError)."""
    from django.conf import settings

    if name not in PARTICIPANTS:
        raise ValueError(f'Unknown participant {name!r}.')
    loop_limits = {'max_exchanges': settings.PARTICIPANT_MAX_EXCHANGES,
                   'loop_deadline': settings.PARTICIPANT_LOOP_DEADLINE_SECONDS,
                   'max_tool_result_bytes': settings.PARTICIPANT_MAX_TOOL_RESULT_BYTES}
    if mode == 'live':
        setting, label = _CREDENTIALS[name]
        path = getattr(settings, setting)
        if not path:
            raise ProviderUnavailable(f'Live {label} needs CPT_STUDIO_{setting}.')
        return _ADAPTERS[name](path, connect_timeout=settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS,
                               read_timeout=settings.PARTICIPANT_READ_TIMEOUT_SECONDS,
                               max_request_bytes=settings.PARTICIPANT_MAX_REQUEST_BYTES,
                               max_response_bytes=settings.PARTICIPANT_MAX_RESPONSE_BYTES,
                               exchange_read_timeout=settings.PARTICIPANT_EXCHANGE_READ_TIMEOUT_SECONDS, **loop_limits)
    if mode == 'replay':
        if not settings.PARTICIPANT_REPLAY_DIR:
            raise ProviderUnavailable('Replay participant mode needs CPT_STUDIO_PARTICIPANT_REPLAY_DIR.')
        return ReplayParticipant(name, settings.PARTICIPANT_REPLAY_DIR,
                                 max_request_bytes=settings.PARTICIPANT_MAX_REQUEST_BYTES,
                                 max_response_bytes=settings.PARTICIPANT_MAX_RESPONSE_BYTES, **loop_limits)
    raise ValueError(f'No adapter exists for participant mode {mode!r}; expected live or replay.')


def reader(provider: str, adapter_version: str) -> Callable[..., ParticipantReading]:
    """The reader for a stored first-reading run, by the provider and adapter version that recorded it (harness@2's, or
    harness@1's, read exactly as before); ProviderUnavailable for any other pair, so a response is only ever read as the
    version that recorded it. It is called as ``reader(request, response_bytes)`` or with the refs the run's own tool
    calls returned, ``reader(request, response_bytes, refs_retrieved)``."""
    try:
        return _READERS[(provider, adapter_version)]
    except (KeyError, TypeError):
        raise ProviderUnavailable(f'No participant reader exists for provider {provider!r} with adapter '
                                  f'{adapter_version!r}.') from None


def peer_reader(provider: str, adapter_version: str) -> Callable[..., PeerReview]:
    """The reader for a stored peer-review run (HARNESS.md 11.1), called as ``peer_reader(request, response_bytes,
    refs_retrieved)``; ProviderUnavailable for any pair but a harness@2 participant's."""
    try:
        return _PEER_READERS[(provider, adapter_version)]
    except (KeyError, TypeError):
        raise ProviderUnavailable(f'No peer-review reader exists for provider {provider!r} with adapter '
                                  f'{adapter_version!r}.') from None
