"""Who sent a request, from where, through which door and in which sign-in: the request's own facts that release 1's
records carry (RELEASE-1-SPEC 3.3; C1, B1, A2). Ids, addresses and fixed words only - never a typed name, a path's
query or anything a member wrote.

    client_address(request)  the client's address (views._client, moved here unchanged; views keeps the alias)
    client_key(request)      the address a throttle counts by: an IPv4 address, or an IPv6 address's /64 prefix
    request_id(request)      the X-Request-ID nginx sets ($request_id: 32 hex characters), or ''
    sign_in_ref(request)     the sign-in reference the session carries (SESSION_SIGN_IN_REF), or None
    host_kind(request)       'admin' on admin.quillmd.com, else 'cpt'
    is_poll(request)         whether the page marked the request as a poll (X-CPT-Poll: 1), which is not activity

The session keys below are the contract between the lanes (RELEASE-1-SPEC section 5): the doors write them at sign-in
(Lane 2), the session policy reads them (studio.sessions), the console's gate reads the door and the second factor
(studio.second_factor), and the records read the sign-in reference. Their timestamps are whole seconds since the epoch
(epoch_seconds), read from django.utils.timezone.now, which tests patch.

SessionPolicyMiddleware binds each request while it runs (bound), so a record written without a request in hand - an
audit row, a security event - can still carry the request's client, sign-in reference and request id (request_fields).
Outside a request (the worker, a management command) nothing is bound and those fields stay empty.
"""
from __future__ import annotations

import contextlib
import contextvars
import ipaddress
import re
import uuid

from django.conf import settings
from django.utils import timezone

from . import hosts

CPT, ADMIN = 'cpt', 'admin'  # the two hosts, and the two doors a session is opened at
SESSION_DOOR = 'cpt_door'  # CPT or ADMIN: where the session was signed in
SESSION_SECOND_FACTOR_AT = 'cpt_2fa_at'  # when the second factor was last presented (the admin door only)
SESSION_AUTH_AT = 'cpt_auth_at'  # when the session was signed in (B5's cap)
SESSION_LAST_ACTIVE = 'cpt_last_active'  # the last activity the person made (B5's idle limit)
SESSION_SIGN_IN_REF = 'cpt_sign_in_ref'  # the sign-in's reference: its LoginAttempt's sign_in_ref, never the session key
SESSION_KEYS = (SESSION_DOOR, SESSION_SECOND_FACTOR_AT, SESSION_AUTH_AT, SESSION_LAST_ACTIVE, SESSION_SIGN_IN_REF)
POLL_HEADER = 'X-CPT-Poll'  # the page's polls send it as '1' (B5: a poll is not activity; C1: a poll's reads repeat less)
REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
REQUEST_ID_RE = re.compile(r'[0-9a-f]{32}')
# What a PostgreSQL text column cannot hold (NUL) or UTF-8 cannot encode (a lone surrogate): such a character in an
# address is replaced, so a record is never refused for it (api.UNSTORABLE's own set).
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')

_request = contextvars.ContextVar('studio.request_meta.request', default=None)


def client_address(request) -> str:
    # Behind the loopback proxy the real client is in X-Forwarded-For, which
    # nginx REPLACES with $remote_addr; never trust it otherwise.
    if settings.SECURE_PROXY_SSL_HEADER:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        if forwarded:
            return forwarded[:64]
    return request.META.get('REMOTE_ADDR', '')[:64]


def client_key(request) -> str:
    """The address a throttle or a limit counts by (B1): an IPv4 address as it is; an IPv6 address by its /64 prefix
    ('2001:db8:1:2::/64'), so a guesser rotating through one subscriber's network is one key; an IPv4-mapped IPv6
    address as its IPv4 address. A value that is no address (it never is behind nginx) is replaced by its keyed hash, so
    a key is always an address, a prefix or a hash - never text a client chose (studio.rate refuses anything else)."""
    address = client_address(request)
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        from .rate import key_hash  # here, not at the top: this module needs no model; never taken behind nginx
        return key_hash('client:' + UNSTORABLE.sub('\ufffd', address))
    if parsed.version == 6:
        if parsed.ipv4_mapped is not None:
            return str(parsed.ipv4_mapped)
        return f'{ipaddress.IPv6Address(int(parsed) >> 64 << 64)}/64'
    return str(parsed)


def request_id(request) -> str:
    """The request id nginx sets on every proxied request (X-Request-ID: $request_id, 32 hex characters; A2), lowercase,
    or '' when the request carries none or anything else - so a record and the edge's access log name the same id."""
    value = request.META.get(REQUEST_ID_HEADER, '')
    if not isinstance(value, str) or len(value) != 32 or not value.isascii():
        return ''
    value = value.lower()
    return value if REQUEST_ID_RE.fullmatch(value) else ''


def sign_in_ref(request):
    """The sign-in reference the request's session carries (a UUID; it leads to the sign-in's LoginAttempt row and is
    never the session key), or None: no session, no reference, or a value that is not a UUID."""
    session = getattr(request, 'session', None)
    if session is None:
        return None
    value = session.get(SESSION_SIGN_IN_REF)
    if not value or not isinstance(value, (str, uuid.UUID)):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def host_kind(request) -> str:
    """ADMIN on the admin host (admin.quillmd.com, studio.hosts' own reading of the Host header), else CPT."""
    return ADMIN if hosts.is_admin_host(request) else CPT


def is_poll(request) -> bool:
    """Whether the page marked the request as a poll (X-CPT-Poll: 1): the document poll and the refresh on visibility or
    reconnect (B5), which never count as the person's activity."""
    return request.headers.get(POLL_HEADER) == '1'


def epoch_seconds(moment=None) -> int:
    """A session timestamp as the session keys hold it: whole seconds since the epoch, of ``moment`` or of now."""
    return int((moment or timezone.now()).timestamp())


@contextlib.contextmanager
def bound(request):
    """Make ``request`` the current request while the block runs (SessionPolicyMiddleware binds every request)."""
    token = _request.set(request)
    try:
        yield request
    finally:
        _request.reset(token)


def current_request():
    """The request being served (bound), or None outside a request."""
    return _request.get()


def request_fields(request=None) -> dict:
    """{'client', 'sign_in_ref', 'request_id'} of ``request``, or of the current request when none is given: what an
    audit row or a security event records of the request that caused it. Empty values outside a request."""
    request = request if request is not None else current_request()
    if request is None:
        return {'client': '', 'sign_in_ref': None, 'request_id': ''}
    return {'client': UNSTORABLE.sub('\ufffd', client_address(request)), 'sign_in_ref': sign_in_ref(request),
            'request_id': request_id(request)}
