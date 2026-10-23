"""Proposal providers (ARCHITECTURE 5.4).

``get_provider`` is the only place this package reads Django settings; nothing
here touches settings at import time.
"""
from __future__ import annotations

from functools import partial
from typing import Callable, Optional

from studio.types import NormalizedResponse, ProviderRequest

from .base import OUTCOMES, ProposalProvider, ProviderUnavailable, canonical_body, request_sha256
from .corti import CortiProvider, normalize_coding_response
from .credentials import CortiCredentials, CredentialsError, load_corti_credentials
from .replay import ReplayProvider

MODES = ('disabled', 'replay', 'live')

__all__ = ['MODES', 'OUTCOMES', 'CortiCredentials', 'CortiProvider', 'CredentialsError', 'ProposalProvider',
           'ProviderUnavailable', 'ReplayProvider', 'canonical_body', 'get_provider', 'load_corti_credentials',
           'normalizer_for', 'request_sha256']


def get_provider(mode: Optional[str] = None) -> Optional[ProposalProvider]:
    """The configured provider, or None when sending is disabled. Misconfiguration raises."""
    from django.conf import settings

    mode = settings.PROVIDER_MODE if mode is None else mode
    if mode == 'disabled':
        return None
    if mode == 'live':
        if not settings.CORTI_CREDENTIALS_FILE:
            raise ProviderUnavailable('Live provider mode needs CPT_STUDIO_CORTI_CREDENTIALS_FILE.')
        return CortiProvider(settings.CORTI_CREDENTIALS_FILE,
                             connect_timeout=settings.PROVIDER_CONNECT_TIMEOUT_SECONDS,
                             read_timeout=settings.PROVIDER_READ_TIMEOUT_SECONDS,
                             max_request_bytes=settings.PROVIDER_MAX_REQUEST_BYTES,
                             max_response_bytes=settings.PROVIDER_MAX_RESPONSE_BYTES)
    if mode == 'replay':
        if not settings.REPLAY_DIR:
            raise ProviderUnavailable('Replay provider mode needs CPT_STUDIO_REPLAY_DIR.')
        return ReplayProvider(settings.REPLAY_DIR, max_request_bytes=settings.PROVIDER_MAX_REQUEST_BYTES,
                              max_response_bytes=settings.PROVIDER_MAX_RESPONSE_BYTES)
    raise ValueError(f'Unknown provider mode {mode!r}; expected one of {", ".join(MODES)}.')


def normalizer_for(provider: str) -> Callable[[ProviderRequest, bytes], NormalizedResponse]:
    """The normalizer for a stored run of ``provider``. It needs no credentials or replay
    directory, and reads a response only as the provider and adapter version that recorded it."""
    if provider not in (CortiProvider.name, ReplayProvider.name):
        raise ProviderUnavailable(f'No normalizer exists for provider {provider!r}.')
    return partial(normalize_coding_response, provider)
