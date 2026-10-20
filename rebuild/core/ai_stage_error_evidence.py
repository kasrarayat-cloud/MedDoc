"""Bounded, sanitized exception evidence; never logs or reads a request body."""
import hashlib
import json
import re


CONTRACT = 'ai-stage-error-evidence-v1'
MAX_BODY_BYTES = 65536
MAX_TEXT_CHARS = 8192
REDACTED = '[REDACTED]'
_HEADERS = re.compile(
    r'(?i)\b(authorization|proxy-authorization|x-api-key|api[_-]key|access[_-]token)'
    r'([\"\']?\s*[=:]\s*[\"\']?)(?:(?:bearer|basic)\s+)?[^\s\"\',;}]+')
_BEARER = re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+')
_KEY = re.compile(r'\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{12,}')


def _attribute(value, name, default=None):
    try:
        return getattr(value, name, default)
    except Exception:
        return default


def _redact(text, credentials):
    for secret in sorted((x for x in credentials if isinstance(x, str) and x), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return _KEY.sub(REDACTED, _BEARER.sub(REDACTED, _HEADERS.sub(lambda m: m[1] + m[2] + REDACTED, text)))


def _text(value, credentials):
    if not isinstance(value, str):
        return None
    return _redact(value, credentials)[:MAX_TEXT_CHARS]


def build(exc, *, provider, stage_id, stage, attempt, credentials=()):
    """Project already available SDK error metadata, with no network or str(exc).

    Only cached response bytes or an already parsed SDK body are inspected. The
    result is explicitly sanitized evidence, never an exact raw response. Error
    messages stay in this private envelope, never its public audit projection.
    """
    credentials = tuple(credentials)
    name = _redact(type(exc).__name__, credentials)
    name = name if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', name) else 'Exception'
    status = _attribute(exc, 'status_code')
    status = status if type(status) is int and 100 <= status <= 599 else None
    response = _attribute(exc, 'response')
    if status is None:
        status = _attribute(response, 'status_code')
        status = status if type(status) is int and 100 <= status <= 599 else None
    request_id = _attribute(exc, 'request_id')
    if not isinstance(request_id, str) and response is not None:
        headers = _attribute(response, 'headers')
        if headers is not None:
            try:
                request_id = headers.get('request-id') or headers.get('x-request-id')
            except Exception:
                request_id = None
    if isinstance(request_id, str):
        request_id = _redact(request_id, credentials)
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,140}', request_id):
            request_id = None
    else:
        request_id = None
    result = {
        'contract': CONTRACT, 'sanitized': True, 'exact_raw_response': False,
        'provider': provider, 'stage_id': str(stage_id), 'stage': stage, 'attempt': attempt,
        'exception_class': name, 'http_status': status, 'provider_request_id': request_id,
        'delivery_outcome': 'unknown', 'actual_cost': None,
        'body_source': None, 'body_bytes': None, 'body_sha256': None,
        'body_retention': 'unavailable', 'provider_error': None,
    }
    # httpx.Response.content reads only an already consumed in-memory body;
    # ResponseNotRead is caught. Never call read(), json(), iter_*() or an API.
    raw = _attribute(response, 'content') if response is not None else None
    if isinstance(raw, bytes):
        result.update(body_source='cached_http_response', body_bytes=len(raw),
                      body_sha256=hashlib.sha256(raw).hexdigest())
        if len(raw) > MAX_BODY_BYTES:
            result['body_retention'] = 'omitted_oversize'
            return result
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            result['body_retention'] = 'omitted_non_json'
            return result
    else:
        body = _attribute(exc, 'body')
        if not isinstance(body, dict):
            return result
        try:
            size = 0
            for part in json.JSONEncoder(ensure_ascii=False, allow_nan=False).iterencode(body):
                size += len(part.encode())
                if size > MAX_BODY_BYTES:
                    break
        except (ValueError, TypeError, RecursionError, UnicodeError):
            result['body_retention'] = 'omitted_invalid_parsed_body'
            return result
        result['body_source'] = 'sdk_parsed_body'
        if size > MAX_BODY_BYTES:
            result['body_bytes_lower_bound'] = size
            result['body_retention'] = 'omitted_oversize'
            return result
        result['body_bytes'] = size
    if not isinstance(body, dict):
        result['body_retention'] = 'omitted_non_object'
        return result
    error = body.get('error', body)
    if not isinstance(error, dict):
        result['body_retention'] = 'omitted_unrecognized_error'
        return result
    allowed = {k: _text(error.get(k), credentials) for k in ('type', 'message', 'code', 'param')}
    result['provider_error'] = {k: v for k, v in allowed.items() if v is not None}
    result['body_retention'] = 'sanitized_error_projection'
    result['truncated_fields'] = [k for k in allowed if isinstance(error.get(k), str)
                                 and len(_redact(error[k], credentials)) > MAX_TEXT_CHARS]
    return result
