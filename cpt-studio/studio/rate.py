"""Bounded counters (release 1; RELEASE-1-SPEC 3.3): refused sign-in attempts per minute (B1), the report, upload and
bundle limits (C5, D2), wrong current passwords (B4) and second-factor attempts (B2), counted in RateWindow rows.

    hit(scope, key, *, window_seconds)  one more hit in (scope, key)'s current window, in ONE atomic statement
                                        (INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING), so hits made at the same
                                        moment never lose a count; answers the window's count after this hit
    count(scope, key, *, since)         the hits of (scope, key) in the windows that start at or after ``since``
    key_hash(text)                      ``text`` as a keyed hash (django.utils.crypto.salted_hmac, SHA-256, keyed by
                                        SECRET_KEY): how a typed name becomes a key

Windows are fixed: each starts at a whole multiple of ``window_seconds`` since the epoch, so a burst across a boundary
can reach twice a limit within one window's length; a limit counted here is an outer bound, never the only control.
A hit is written in the caller's transaction: a counter that must outlive a refusal is hit outside any transaction the
refusal rolls back.

A key is one of four forms, and anything else is refused (ValueError): a key_hash (64 hex characters), an account's or
practice's id (a UUID), an IPv4 address, or an IPv6 /64 prefix (studio.request_meta.client_key gives the last two). So a
raw typed name - a username, an e-mail address, a password typed in the wrong box - can never become a stored key.
"""
from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import datetime, timezone as dt_timezone

from django.db import connection
from django.db.models import Sum
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import RateWindow

SCOPE_RE = re.compile(r'[a-z][a-z0-9_.:-]{0,39}')  # a fixed word naming what is counted (RateWindow.scope holds 40)
HASH_RE = re.compile(r'[0-9a-f]{64}')
KEY_SALT = 'studio.rate.key_hash'
KEY_REFUSED = ('A rate key is a key_hash, an id, an IPv4 address or an IPv6 /64 prefix - never typed text; hash a typed '
               'name with rate.key_hash first.')


def key_hash(text) -> str:
    """A keyed hash of ``text`` (64 hex characters) to count a typed name by: the same text always gives the same key, and
    the key never holds the text."""
    return salted_hmac(KEY_SALT, str(text), algorithm='sha256').hexdigest()


def _scope(scope) -> str:
    if not isinstance(scope, str) or not SCOPE_RE.fullmatch(scope):
        raise ValueError('A rate scope is a fixed lowercase word of at most 40 characters.')
    return scope


def _key(key) -> str:
    """``key`` in its one canonical form, or ValueError (KEY_REFUSED)."""
    if isinstance(key, uuid.UUID):
        return str(key)
    if not isinstance(key, str) or not key or len(key) > 128:
        raise ValueError(KEY_REFUSED)
    if HASH_RE.fullmatch(key):
        return key
    try:
        if str(uuid.UUID(key)) == key:
            return key
    except ValueError:
        pass
    try:
        if ipaddress.ip_address(key).version == 4 and str(ipaddress.ip_address(key)) == key:
            return key
    except ValueError:
        pass
    try:
        network = ipaddress.ip_network(key)  # strict: a /64 with host bits set is not a prefix
        if network.version == 6 and network.prefixlen == 64 and str(network) == key:
            return key
    except ValueError:
        pass
    raise ValueError(KEY_REFUSED)


def _window_seconds(window_seconds) -> int:
    if isinstance(window_seconds, bool) or not isinstance(window_seconds, int) or window_seconds < 1:
        raise ValueError('A rate window is a whole number of seconds, at least 1.')
    return window_seconds


def window_start(window_seconds, moment=None) -> datetime:
    """The start of the fixed window of ``window_seconds`` that holds ``moment`` (now by default)."""
    epoch = int((moment or timezone.now()).timestamp())
    return datetime.fromtimestamp(epoch - epoch % _window_seconds(window_seconds), tz=dt_timezone.utc)


def hit(scope, key, *, window_seconds, now=None) -> int:
    """Count one hit of ``key`` under ``scope`` in the window of ``window_seconds`` that holds ``now`` (the current one by
    default); the window's count after it. One statement inserts the window's row or adds one to it, so two hits at the
    same moment are both counted. A caller that read its own moment first passes it, so the hit lands in the window that
    caller counted (repair round 3: throttle.reserve)."""
    scope, key = _scope(scope), _key(key)
    now = now or timezone.now()
    start = window_start(window_seconds, now)
    quote = connection.ops.quote_name
    table = quote(RateWindow._meta.db_table)
    column = {name: quote(RateWindow._meta.get_field(name).column)
              for name in ('scope', 'key', 'window_start', 'count', 'last_at')}
    sql = (f'INSERT INTO {table} ({column["scope"]}, {column["key"]}, {column["window_start"]}, {column["count"]}, '
           f'{column["last_at"]}) VALUES (%s, %s, %s, 1, %s) '
           f'ON CONFLICT ({column["scope"]}, {column["key"]}, {column["window_start"]}) DO UPDATE SET '
           f'{column["count"]} = {table}.{column["count"]} + 1, '
           f'{column["last_at"]} = GREATEST({table}.{column["last_at"]}, EXCLUDED.{column["last_at"]}) '
           f'RETURNING {column["count"]}')
    with connection.cursor() as cursor:
        cursor.execute(sql, [scope, key, start, now])
        return cursor.fetchone()[0]


def count(scope, key, *, since) -> int:
    """The hits of ``key`` under ``scope`` in every window that starts at or after ``since``."""
    total = RateWindow.objects.filter(scope=_scope(scope), key=_key(key), window_start__gte=since).aggregate(
        total=Sum('count'))['total']
    return total or 0
