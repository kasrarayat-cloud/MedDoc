"""Pages read by position (keyset), not by number - the customer's paged lists and search (release 2, RELEASE-2-SPEC
R2-19, R2-20) and the operator console's pages alike.

A page holds rows newest first: created_at descending, then id descending (created_at never changes: auto_now_add). The
next page holds the rows strictly older than the last row shown, so rows arriving meanwhile never repeat a row or skip one
(refutation r1 of the console, money-6). Its cursor names that last row as `<UTC time to the microsecond>~<id>`: a time and
an id only, read with a strict pattern, and a position, never an authority - every query is scoped by the caller's own
practice (or the operator's grant), so another practice's cursor shows nothing of it.

    CURSOR_RE                                  the cursor's pattern
    cursor_of(created_at, pk)                  the cursor of a row
    parse(raw, *, integer_pk=False)            (time, id) of a cursor, or None when it cannot be read
    older_than(queryset, raw, *, integer_pk=False)
                                               (the queryset's rows older than the cursor, the cursor); the queryset as
                                               it is with no cursor (the newest page); (None, '') for an unreadable one

The console's helpers moved here unchanged from studio/console.py (CURSOR_RE, cursor_of, _older_than), which keeps its
names delegating, so the console changes no behaviour (R2-19).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone as dt_timezone

from django.db.models import Q

CURSOR_RE = re.compile(r'(\d{8}T\d{6}\.\d{6}Z)~([0-9a-f-]{1,36})')
CURSOR_TIME = '%Y%m%dT%H%M%S.%fZ'


def cursor_of(created_at, pk) -> str:
    """The cursor of the row made at ``created_at`` with id ``pk``: the position a next page starts after."""
    return f'{created_at.astimezone(dt_timezone.utc):%Y%m%dT%H%M%S.%fZ}~{pk}'


def parse(raw, *, integer_pk=False):
    """(the UTC time, the id) a cursor names - an integer id with ``integer_pk``, else a UUID - or None when ``raw`` is
    not a cursor (not text, not CURSOR_RE in full, or a time or an id that does not read)."""
    match = CURSOR_RE.fullmatch(raw) if isinstance(raw, str) else None
    if not match:
        return None
    try:
        moment = datetime.strptime(match.group(1), CURSOR_TIME).replace(tzinfo=dt_timezone.utc)
        key = int(match.group(2)) if integer_pk else uuid.UUID(match.group(2))
    except (ValueError, TypeError):
        return None
    return moment, key


def older_than(queryset, raw, *, integer_pk=False):
    """(``queryset`` limited to the rows older than the cursor ``raw``, the cursor); the whole queryset with no cursor
    (the newest page); (None, '') when the cursor cannot be read."""
    if not raw:
        return queryset, ''
    position = parse(raw, integer_pk=integer_pk)
    if position is None:
        return None, ''
    moment, key = position
    # the bound on created_at alone lets an index start the scan at the cursor (refutation round 1 of release 1, avail-3
    # and avail-5): the same rows, read from the cursor rather than from the newest row down
    return (queryset.filter(created_at__lte=moment).filter(Q(created_at__lt=moment) | Q(created_at=moment, pk__lt=key)),
            raw)
