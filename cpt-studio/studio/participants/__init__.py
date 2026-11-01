"""The harness's independent participants (HARNESS.md): Astra (OpenAI ``gpt-6-astra``) and Fable (Anthropic
``claude-fable-5-1``). Corti stays in studio.providers and is unchanged.

A participant is configured on its own (CPT_STUDIO_ASTRA_MODE, CPT_STUDIO_FABLE_MODE: disabled | replay | live), so one
unavailable blocks only its own stage (I10). Its model and endpoint are constants of its adapter, never settings, and no
vendor fallback is ever requested (I6).

The contract every adapter implements (``Participant``):
- ``build_request(text, pages, kind, original)`` is pure and needs no credentials (the web container calls it). It
  returns a ProviderRequest whose ``contexts`` is ``(text,)`` - the revision text the reading's quotes are located in -
  and whose body names a PDF original by sha256 and size, never its bytes (HARNESS.md 3).
- ``send(request, *, deadline_s, client_request_id, original_bytes)`` reads the credentials at send time, expands the
  original after re-verifying its sha256, makes exactly one attempt with no retry and no redirect, and returns a
  RawExchange: 'not_sent' only while the request provably has not left, 'unknown' for anything after that, 'failed'
  for a non-200 (body kept), 'succeeded' for a 200. It fills endpoint, requested_model, returned_model, response_id,
  provider_request_id and usage (as reported, with its basis).
- ``read(request, response_bytes)`` turns the stored raw bytes into a ParticipantReading (studio.types), refusing the
  whole reading when the vendor refused or truncated, when another model answered, or when the JSON breaks the schema
  or its bounds; it locates every quote in ``request.contexts[0]``.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol, runtime_checkable

from studio.types import PageSpan, ParticipantReading, ProviderRequest, RawExchange

PARTICIPANTS = ('astra', 'fable')  # their stages run in this order, after predict (HARNESS.md 2)
MODES = ('disabled', 'replay', 'live')
LABELS = {'astra': 'Astra', 'fable': 'Fable'}
VENDORS = {'astra': 'OpenAI', 'fable': 'Anthropic'}


@runtime_checkable
class Participant(Protocol):
    name: str
    adapter_version: str
    mode: str  # 'live' | 'replay'
    requested_model: str
    endpoint: str

    def build_request(self, text: str, pages: tuple[PageSpan, ...], kind: str,
                      original: Optional[dict]) -> ProviderRequest: ...

    def send(self, request: ProviderRequest, *, deadline_s: float, client_request_id: str,
             original_bytes: Optional[bytes]) -> RawExchange: ...

    def read(self, request: ProviderRequest, response_bytes: bytes) -> ParticipantReading: ...


def participant_mode(name: str) -> str:
    from django.conf import settings

    if name not in PARTICIPANTS:
        raise ValueError(f'Unknown participant {name!r}.')
    return settings.ASTRA_MODE if name == 'astra' else settings.FABLE_MODE


def configured() -> tuple[str, ...]:
    """The participants this installation runs, in stage order; () when none is (then the pipeline is Corti's alone)."""
    return tuple(name for name in PARTICIPANTS if participant_mode(name) != 'disabled')


def get_participant(name: str) -> Optional[Participant]:
    """The configured adapter, or None when the participant is disabled. Misconfiguration raises ProviderUnavailable."""
    mode = participant_mode(name)
    if mode == 'disabled':
        return None
    from studio.participants import registry

    return registry.build(name, mode)


def reader_for(provider: str, adapter_version: str) -> Callable[[ProviderRequest, bytes], ParticipantReading]:
    """The reader for a stored run of ``provider`` recorded by ``adapter_version``. It needs no credentials, and reads a
    response only as the adapter version that recorded it; anything else raises ProviderUnavailable."""
    from studio.participants import registry

    return registry.reader(provider, adapter_version)
