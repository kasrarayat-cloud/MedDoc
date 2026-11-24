"""The record of every read of PHI (release 1, C1; RELEASE-1-SPEC 3.3): one AccessRecord per view or download, written
BEFORE any byte of PHI is produced.

    record(request, *, view, workspace_id=None, encounter_ids=(), export_id=None, count=None, as_of=None, filters=None,
           reason='', outcome='served')
        writes one AccessRecord and answers it - or raises NotRecorded, and the caller serves nothing: a read whose row
        cannot be written answers 503 NOT_RECORDED with no PHI (fail closed; RELEASE-1-SPEC 2.2). An argument outside
        the contract (an unknown view kind, typed text in the filters) raises ValueError before anything is written.
        One exception, bounding what one session adds (refutation round 1 of release 1, avail-3): a served member.list
        read that repeats a served member.list row of the same sign-in, account, role, host, address, practice, count
        and filters written within READ_AUDIT_LIST_REPEAT_SECONDS, and on the same UTC day as the repeat (the day the
        console's reads page files a read under; refutation round 2, phi-3), writes no row of its own - it is counted
        on that row (AccessRecordRepeat: one more repeat, the latest time), in the same savepoint, and answers that row;
        a count that cannot be written refuses the read like any row. The list holds the whole practice with no paging,
        so the row and its count say exactly what was shown: the practice's documents at each read from as_of to the
        count's latest time, by that session, from that address, all on the row's own day. Every detail, view,
        download, report and bundle read, and every refused read, still writes its own row.
    detail_seen_recently(request, encounter_id)
        whether this sign-in already has a served member.detail row for the document within
        READ_AUDIT_DETAIL_DEDUPE_SECONDS: a poll (studio.request_meta.is_poll) then writes no new row (TEC-9 (4)); every
        other request records.
    phi_read(kind)
        marks a view as a read of PHI of that kind, for the route-coverage test (every route is marked or listed as
        reading none; TEC-9 (7)). It marks only: the view still calls record() itself, before it builds its answer.

The row holds ids, counts and fixed words (studio/audit.py's rule): the account (its id, kind and role), the host, the
kind of view, the practice, the documents or the report, the count and time of a list, its filter names and cursor, an
operator's reason, the outcome, and the request's client address, sign-in reference and request id
(studio.request_meta). Ids are plain values, never foreign keys, so the trail outlives the PHI it names.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from . import request_meta
from .models import AccessRecord, AccessRecordRepeat, Membership

# The kinds of read (C1's table, the reads page of its item 9, and D2's bundle).
MEMBER_LIST, MEMBER_DETAIL, MEMBER_INLINE, MEMBER_DOWNLOAD = 'member.list', 'member.detail', 'member.inline', 'member.download'
MEMBER_REPORT_DOWNLOAD, MEMBER_BUNDLE_DOWNLOAD = 'member.report_download', 'member.bundle_download'
OPS_LIST, OPS_WORKSPACE, OPS_SPENDING, OPS_ACTIVITY = 'ops.list', 'ops.workspace', 'ops.spending', 'ops.activity'
OPS_DETAIL, OPS_CONTENT_OPEN, OPS_ORIGINAL, OPS_READS = 'ops.detail', 'ops.content_open', 'ops.original', 'ops.reads'
VIEW_KINDS = (MEMBER_LIST, MEMBER_DETAIL, MEMBER_INLINE, MEMBER_DOWNLOAD, MEMBER_REPORT_DOWNLOAD, MEMBER_BUNDLE_DOWNLOAD,
              OPS_LIST, OPS_WORKSPACE, OPS_SPENDING, OPS_ACTIVITY, OPS_DETAIL, OPS_CONTENT_OPEN, OPS_ORIGINAL, OPS_READS)
SERVED, REFUSED = AccessRecord.SERVED, AccessRecord.REFUSED
OPERATOR_ROLE = 'operator'  # the actor_role of every ops.* read: the console is an operator's alone
NOT_RECORDED = 'This could not be recorded, so nothing was shown.'  # the 503's sentence
PHI_READ_ATTRIBUTE = 'phi_read_kind'
# A filter is a name and a value a page offers - ids, fixed words, cursors, counts - never text someone typed.
FILTER_NAME_RE = re.compile(r'[a-z][a-z0-9_]{0,39}')
FILTER_TEXT_CHARS, FILTER_ITEMS = 100, 200


class NotRecorded(Exception):
    """The read's AccessRecord could not be written: serve nothing (answer 503 NOT_RECORDED)."""


def _uuid(value, label):
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f'{label} must be a UUID.') from None


def _filter_value(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, str) and len(value) <= FILTER_TEXT_CHARS:
        return value
    raise ValueError('A filter value is an id, a fixed word, a cursor or a count (at most '
                     f'{FILTER_TEXT_CHARS} characters), never typed text.')


def _filters(filters) -> dict:
    if filters is None:
        return {}
    if not isinstance(filters, dict):
        raise ValueError('filters is a dict of filter names and values.')
    out = {}
    for name, value in filters.items():
        if not isinstance(name, str) or not FILTER_NAME_RE.fullmatch(name):
            raise ValueError('A filter name is a fixed lowercase word.')
        if isinstance(value, (list, tuple)):
            if len(value) > FILTER_ITEMS:
                raise ValueError(f'A filter holds at most {FILTER_ITEMS} values.')
            out[name] = [_filter_value(item) for item in value]
        else:
            out[name] = _filter_value(value)
    return out


def _role(user, view, workspace_id) -> str:
    """The actor's role for this read: OPERATOR_ROLE for a console read, else their membership's role in the practice
    read (one indexed lookup), or '' when they hold none there - a refused read of another practice's document."""
    if view.startswith('ops.'):
        return OPERATOR_ROLE
    if workspace_id is None:
        return ''
    return Membership.objects.filter(user_id=user.pk, workspace_id=workspace_id).values_list(
        'role', flat=True).first() or ''


def record(request, *, view, workspace_id=None, encounter_ids=(), export_id=None, count=None, as_of=None,
           filters=None, reason='', outcome=SERVED):
    """Write the AccessRecord of one read of PHI by ``request``'s signed-in account, before the read is served; the row,
    or NotRecorded (serve nothing). Arguments outside the contract raise ValueError and write nothing."""
    if view not in VIEW_KINDS:
        raise ValueError(f'Not a kind of read: {view!r}.')
    if outcome not in (SERVED, REFUSED):
        raise ValueError('outcome is served or refused.')
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        raise ValueError('A read is recorded for a signed-in account only.')
    if isinstance(encounter_ids, (str, bytes)) or not hasattr(encounter_ids, '__iter__'):
        raise ValueError('encounter_ids is a list of document ids.')
    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
        raise ValueError('count is a whole number, at least 0.')
    if as_of is not None and not isinstance(as_of, dt.datetime):
        raise ValueError('as_of is a time.')
    if not isinstance(reason, str):
        raise ValueError('reason is text.')
    fields = dict(
        host=request_meta.host_kind(request), view=view, actor_id=user.pk, actor_kind=user.actor_kind,
        workspace_id=None if workspace_id is None else _uuid(workspace_id, 'workspace_id'),
        encounter_ids=[str(_uuid(item, 'An encounter id')) for item in encounter_ids],
        export_id=None if export_id is None else _uuid(export_id, 'export_id'),
        count=count, as_of=as_of, filters=_filters(filters), reason=reason, outcome=outcome)
    try:
        with transaction.atomic():  # a savepoint: a failed write leaves the caller's transaction usable for its 503
            fields.update(request_meta.request_fields(request))  # reads the session: inside, so its failure refuses too
            fields['actor_role'] = _role(user, view, fields['workspace_id'])
            repeated = _counted_list_repeat(fields)
            if repeated is not None:
                return repeated
            return AccessRecord.objects.create(**fields)
    except Exception as exc:  # noqa: BLE001 - whatever stopped the write, the read is not served
        raise NotRecorded(NOT_RECORDED) from exc


def _counted_list_repeat(fields):
    """The served member.list row the read ``fields`` repeats (see the module), with this repeat counted on it, or None
    when the read is no such repeat and writes its own row."""
    if fields['view'] != MEMBER_LIST or fields['outcome'] != SERVED or fields.get('sign_in_ref') is None:
        return None
    now = timezone.now()
    # only a record of this repeat's own UTC day: the day the console's reads page files a read under (its ?day= is a
    # UTC day, read on created_at), so each day's page holds every list read made that day (refutation round 2, phi-3)
    day = now.astimezone(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = max(now - timedelta(seconds=settings.READ_AUDIT_LIST_REPEAT_SECONDS), day)
    first = (AccessRecord.objects.filter(
        actor_id=fields['actor_id'], sign_in_ref=fields['sign_in_ref'], view=MEMBER_LIST, outcome=SERVED,
        actor_role=fields['actor_role'], host=fields['host'], client=fields.get('client', ''),
        workspace_id=fields['workspace_id'], count=fields['count'], filters=fields['filters'],
        created_at__gte=since, created_at__lte=now)
        .order_by('-created_at', '-pk').first())
    if first is None:
        return None
    quote = connection.ops.quote_name
    table = quote(AccessRecordRepeat._meta.db_table)
    record, repeats, last_at = (quote(AccessRecordRepeat._meta.get_field(name).column)
                                for name in ('record_id', 'repeats', 'last_at'))
    with connection.cursor() as cursor:  # one statement: two repeats at the same moment are both counted
        cursor.execute(f'INSERT INTO {table} ({record}, {repeats}, {last_at}) VALUES (%s, 1, %s) '
                       f'ON CONFLICT ({record}) DO UPDATE SET {repeats} = {table}.{repeats} + 1, '
                       f'{last_at} = GREATEST({table}.{last_at}, EXCLUDED.{last_at})', [first.pk, now])
    return first


def detail_seen_recently(request, encounter_id) -> bool:
    """Whether this sign-in (its sign-in reference) already has a served member.detail row for ``encounter_id`` within
    READ_AUDIT_DETAIL_DEDUPE_SECONDS - so a poll of a document being coded writes at most one row a minute."""
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return False
    since = timezone.now() - timedelta(seconds=settings.READ_AUDIT_DETAIL_DEDUPE_SECONDS)
    return AccessRecord.objects.filter(
        actor_id=user.pk, sign_in_ref=request_meta.sign_in_ref(request), view=MEMBER_DETAIL, outcome=SERVED,
        created_at__gte=since, encounter_ids__contains=[str(_uuid(encounter_id, 'encounter_id'))]).exists()


def phi_read(kind):
    """Mark a view as a read of PHI of ``kind`` (one of VIEW_KINDS), for the route-coverage test; it changes nothing
    else. Outer decorators that use functools.wraps carry the mark."""
    if kind not in VIEW_KINDS:
        raise ValueError(f'Not a kind of read: {kind!r}.')

    def mark(view):
        setattr(view, PHI_READ_ATTRIBUTE, kind)
        return view
    return mark


def read_kind(view):
    """The kind a view was marked with by phi_read, or None."""
    return getattr(view, PHI_READ_ATTRIBUTE, None)
