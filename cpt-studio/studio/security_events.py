"""Security acts that belong to no workspace (release 1; RELEASE-1-SPEC 3.3): an operator granted or revoked, a second
factor enrolled, reset or failed, a sign-in delay cleared, a password changed or expired unused, holds released, the
daily maintenance's counts. AuditEvent needs a workspace (ORG-4 (d)); a SecurityEvent names one only when there is one.

    record(event, *, actor=None, actor_label='', subject=None, workspace_id=None, request=None, **data)

writes one SecurityEvent and answers it. ``event`` is a fixed dotted name ('signin.throttled'); ``actor`` and
``subject`` are accounts (or their ids); ``actor_label`` names the person behind a server act (a ruled act's --by), never
a role; ``data`` holds ids, counts and fixed words only - an id becomes its string, a time its ISO form, and anything
longer than DATA_TEXT_CHARS or of another type is refused. The request's client, sign-in reference and request id are
recorded from ``request``, or from the request being served (studio.request_meta); a server act records none. A write
that fails raises: the act that needed the record does not go ahead without it.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import uuid
from decimal import Decimal

from . import request_meta
from .models import SecurityEvent

EVENT_RE = re.compile(r'[a-z][a-z0-9_]*(\.[a-z0-9_]+)+')
EVENT_CHARS = 60  # SecurityEvent.event
LABEL_CHARS = 120  # SecurityEvent.actor_label
DATA_NAME_RE = re.compile(r'[a-z][a-z0-9_]{0,59}')
DATA_TEXT_CHARS, DATA_ITEMS, DATA_DEPTH = 200, 500, 3


def _id(value, label):
    """An account (or anything with a pk) or an id, as a UUID; None for None."""
    if value is None:
        return None
    value = getattr(value, 'pk', value)
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f'{label} is an account or an id.') from None


def _plain(value, depth=0):
    """``value`` as JSON of ids, counts and fixed words, or ValueError."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('A security event holds finite numbers only.')
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, str):
        if len(value) > DATA_TEXT_CHARS:
            raise ValueError(f'A security event holds ids, counts and fixed words: text of at most {DATA_TEXT_CHARS} '
                             'characters.')
        return value
    if depth >= DATA_DEPTH:
        raise ValueError(f'A security event\'s data nests at most {DATA_DEPTH} levels.')
    if isinstance(value, (list, tuple)):
        if len(value) > DATA_ITEMS:
            raise ValueError(f'A list in a security event holds at most {DATA_ITEMS} items.')
        return [_plain(item, depth + 1) for item in value]
    if isinstance(value, dict):
        return {_name(name): _plain(item, depth + 1) for name, item in value.items()}
    raise ValueError(f'A security event cannot hold a {type(value).__name__}.')


def _name(name):
    if not isinstance(name, str) or not DATA_NAME_RE.fullmatch(name):
        raise ValueError('A name in a security event\'s data is a fixed lowercase word.')
    return name


def record(event, *, actor=None, actor_label='', subject=None, workspace_id=None, request=None, **data):
    """Write one SecurityEvent (see the module) and answer it."""
    if not isinstance(event, str) or len(event) > EVENT_CHARS or not EVENT_RE.fullmatch(event):
        raise ValueError('A security event is a fixed dotted lowercase name, such as signin.throttled.')
    if not isinstance(actor_label, str) or len(actor_label) > LABEL_CHARS or request_meta.UNSTORABLE.search(actor_label):
        raise ValueError(f'actor_label is a person\'s name of at most {LABEL_CHARS} characters.')
    return SecurityEvent.objects.create(
        event=event, actor_id=_id(actor, 'actor'), actor_label=actor_label, subject_id=_id(subject, 'subject'),
        workspace_id=_id(workspace_id, 'workspace_id'), data={_name(name): _plain(value) for name, value in data.items()},
        **request_meta.request_fields(request))
