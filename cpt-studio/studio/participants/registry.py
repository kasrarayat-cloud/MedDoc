"""Which adapter serves a configured participant, and which reader reads a stored run (HARNESS.md 8).

``build`` is the only place the participant adapters read Django settings; nothing here touches settings at import
time, and nothing reads a credential: a live adapter reads its file at send time, in the worker that mounts it.
``reader`` needs no settings at all.
"""
from __future__ import annotations

from typing import Callable

from studio.participants import PARTICIPANTS, anthropic_fable, openai_astra
from studio.participants.replay import ReplayParticipant
from studio.providers.base import ProviderUnavailable
from studio.types import ParticipantReading, ProviderRequest

_ADAPTERS = {openai_astra.NAME: openai_astra.AstraParticipant, anthropic_fable.NAME: anthropic_fable.FableParticipant}
_CREDENTIALS = {openai_astra.NAME: ('OPENAI_CREDENTIALS_FILE', 'Astra'),
                anthropic_fable.NAME: ('ANTHROPIC_CREDENTIALS_FILE', 'Fable')}
_READERS = {(openai_astra.NAME, openai_astra.ADAPTER_VERSION): openai_astra.read_response,
            (anthropic_fable.NAME, anthropic_fable.ADAPTER_VERSION): anthropic_fable.read_response}


def build(name: str, mode: str):
    """The adapter for participant ``name`` in ``mode`` ('live' or 'replay'). Misconfiguration raises
    ProviderUnavailable; an unknown participant or mode is a programming error (ValueError)."""
    from django.conf import settings

    if name not in PARTICIPANTS:
        raise ValueError(f'Unknown participant {name!r}.')
    if mode == 'live':
        setting, label = _CREDENTIALS[name]
        path = getattr(settings, setting)
        if not path:
            raise ProviderUnavailable(f'Live {label} needs CPT_STUDIO_{setting}.')
        return _ADAPTERS[name](path, connect_timeout=settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS,
                               read_timeout=settings.PARTICIPANT_READ_TIMEOUT_SECONDS,
                               max_request_bytes=settings.PARTICIPANT_MAX_REQUEST_BYTES,
                               max_response_bytes=settings.PARTICIPANT_MAX_RESPONSE_BYTES)
    if mode == 'replay':
        if not settings.PARTICIPANT_REPLAY_DIR:
            raise ProviderUnavailable('Replay participant mode needs CPT_STUDIO_PARTICIPANT_REPLAY_DIR.')
        return ReplayParticipant(name, settings.PARTICIPANT_REPLAY_DIR,
                                 max_request_bytes=settings.PARTICIPANT_MAX_REQUEST_BYTES,
                                 max_response_bytes=settings.PARTICIPANT_MAX_RESPONSE_BYTES)
    raise ValueError(f'No adapter exists for participant mode {mode!r}; expected live or replay.')


def reader(provider: str, adapter_version: str) -> Callable[[ProviderRequest, bytes], ParticipantReading]:
    """The reader for a stored run, by the provider and adapter version that recorded it; ProviderUnavailable for any
    other pair, so a response is only ever read as the version that recorded it."""
    try:
        return _READERS[(provider, adapter_version)]
    except (KeyError, TypeError):
        raise ProviderUnavailable(f'No participant reader exists for provider {provider!r} with adapter '
                                  f'{adapter_version!r}.') from None
