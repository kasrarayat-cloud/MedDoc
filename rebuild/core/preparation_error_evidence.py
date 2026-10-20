"""Private preparation error detail, separate from closed public failure metadata."""
import os
import re
from copy import deepcopy

from . import ai_stage_error_evidence as shared


CONTRACT = 'preparation-provider-error-evidence-v1'
POINTER_KEY = 'private_error_evidence'
ERROR_TYPES = frozenset({'invalid_request_error', 'authentication_error', 'permission_error',
    'not_found_error', 'request_too_large', 'rate_limit_error', 'api_error',
    'overloaded_error', 'billing_error', 'timeout_error'})


def _credentials():
    return tuple(os.getenv(name, '') for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY'))


def attribute(value, name):
    try:
        return getattr(value, name, None)
    except BaseException:
        return None


def public_request_id(value):
    """A bounded token ID must not expose a known key or embedded credential."""
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,140}', value):
        return ''
    redacted = shared._redact(value, _credentials())
    return value if redacted == value else ''


def build(exc, *, provider, receipt_id, role, stage, metadata):
    """Use only the existing shared cached-body sanitizer; never str(exc)/read().

    The caller persists metadata before invoking this best-effort projection.
    A diagnostic failure must not replace that original provider outcome.
    """
    evidence = shared.build(exc, provider=provider, stage_id=receipt_id,
        stage=role, attempt=1, credentials=_credentials())
    return {'contract': CONTRACT, 'sanitized': True, 'exact_raw_response': False,
        'role': role, 'failure_stage': stage, 'failure_metadata': deepcopy(metadata),
        'provider_evidence': evidence}


def public_projection(metadata, private):
    """Only fixed metadata can flow back from the private provider envelope."""
    result = dict(metadata)
    evidence = private['provider_evidence']
    if result['http_status'] is None:
        value = evidence.get('http_status')
        if type(value) is int and 100 <= value <= 599:
            result['http_status'] = value
    if not result['provider_request_id']:
        result['provider_request_id'] = public_request_id(evidence.get('provider_request_id'))
    error = evidence.get('provider_error')
    value = error.get('type') if type(error) is dict else None
    if result['provider_error_type'] == 'unestablished' and type(value) is str and value in ERROR_TYPES:
        result['provider_error_type'] = value
    return result
