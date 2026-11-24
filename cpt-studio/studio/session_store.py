"""The site's session store (refutation round 1 of release 1, avail-0): Django's database store - the same django_session
table and rows, so the revision before release 1 keeps reading and writing it during the blue/green switch and after a
switch-back (RELEASE-1-SPEC 2.1, 6.3) - that also keeps which accounts each session names, in a side table
(studio.models.SessionAccountLink: session key, account, kind), so that ending one account's sessions costs that account's
own sessions and never the whole table.

How a session names an account (account_links): signed in as it (django.contrib.auth's SESSION_KEY), of the kind of the
door the session was opened at (request_meta.SESSION_DOOR: SIGNED_IN_ADMIN at the admin door, SIGNED_IN at the cpt door
or none - repair round 2, sessions-1), or waiting on it - a checked password waiting for its key at the admin door
(PENDING_SIGN_IN_KEY: PENDING) or a setup under way (SETUP_KEY: SETUP), each a dict naming the account in 'user'. An
account is read the way every reader of those keys reads it - the user model's primary key's to_python, as
django.contrib.auth.get_user and User.objects.get(pk=...) do - so one account is one link whatever spelling of its id a
session holds.

SessionStore, set as SESSION_ENGINE (cptstudio/settings.py):
  save()    writes the session and makes its links exactly what the saved data names, in one transaction. The session's
            own row is written first, so two saves of one session take its row lock in turn and the later one's links
            stand. create() saves through it, so cycle_key - login(), update_session_auth_hash - writes the new key with
            its links and then deletes the old key with its links: no live session is ever left unindexed.
  delete()  deletes the session and its links in one transaction (flush() and logout() delete through it).
  load()    refuses - an empty session, as for a key that is not in the table - a session whose data names an account
            that its links do not: such a row was written by something other than this store (the revision before release
            1, a direct write), and this release never signs anyone in with it, nor lets it wait on an account. So every
            session this release honours is indexed, and a session end_account_sessions cannot find is never one it
            honours (it is not assumed ended: it is refused).
  a new link beyond settings.SESSION_LIVE_PER_ACCOUNT live sessions of one account and kind ends that account's oldest of
            that kind (cap_account_sessions): one account's own sign-ins cannot grow the table without bound, a pending
            sign-in - made with a password alone - only ever ends an older pending sign-in, never a signed-in session,
            and one door's sign-ins never end a session of the other door (each door is its own kind). A pending sign-in
            that can still complete (pending_can_complete: no older than SECOND_FACTOR_PENDING_SECONDS by its own 'at',
            read as studio.second_factor.pending reads it) is never ended by the cap: it is kept and still counts toward
            the limit (repair round 2, sessions-0, secondfactor-1, regression-0), so someone holding the password alone
            never ends the operator's own sign-in between the password and the key. The bound this leaves on one
            account's live pending sessions: the limit, plus those made in the last SECOND_FACTOR_PENDING_SECONDS - each
            a right password at the admin door, which B1 never slows, so their number is bounded by nginx's cpt_signin
            zone (60 a minute and a burst of 40 per IPv4 address or IPv6 /64) and by what the web workers can hash in
            that time; the first cap after one can no longer complete ends it (and ending the account's sessions ends
            every one).
  the async methods run the synchronous ones (one implementation; this site's web is synchronous).

The lock order (repair round 2, records-0 and records-1): every store write that adds a link for an account, every delete
of a session that has links, and every end of an account's sessions (end_account_sessions, the cap) first takes the row
lock of each account involved (lock_accounts: SELECT ... FOR NO KEY UPDATE on the user rows, in id order) before any
session row is written or deleted - so every such transaction meets the account first, as a password change, which
updates the account's row before it ends the other sessions, already does; NO KEY UPDATE, so a row written with a foreign
key to the account (its KEY SHARE) is never blocked. Sessions are deleted in session key order.

end_account_sessions(account, keep_session_key=None)  studio.sessions.end_sessions: the account's live sessions read from
    its links, each one's data read again before it is deleted through the store, and the account's links whose session
    is gone, expired or no longer names it removed. The number ended.
prune_session_links(now=None)  the daily maintenance (studio.maintenance) and clear_expired: every link whose session is
    gone or expired removed. The number removed.

A link is a plain value, never a foreign key: the revision before release 1 deletes django_session rows (a sign-out) and
the installer deletes every one of them at a forward from it, and neither may be refused or need to know of this table.
The links such a delete leaves behind name a session that is gone; every reader re-checks the session itself, so they are
harmless, and the next end_account_sessions, cap or daily maintenance removes them. Ids only: a link holds a session key,
an account id, a fixed word and a time, never session data.
"""
from __future__ import annotations

from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends import db
from django.core.exceptions import ValidationError
from django.db import connections, router, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from . import request_meta

# the kinds of link (SessionAccountLink.kind, at most 12 characters): signed in at the cpt door (or at none), signed in at
# the admin door, a checked password waiting for its key, a setup under way
SIGNED_IN, SIGNED_IN_ADMIN, PENDING, SETUP = 'signed_in', 'signed_admin', 'pending', 'setup'
KINDS = (SIGNED_IN, SIGNED_IN_ADMIN, PENDING, SETUP)
# the session keys of an anonymous session that waits on an account (studio.sessions re-exports them; studio.second_factor
# reads and writes them by these names): a checked password waiting for its key, and a setup under way
PENDING_SIGN_IN_KEY, SETUP_KEY = 'cpt_2fa_pending', 'cpt_enrol'
WAITING_LINKS = ((PENDING, PENDING_SIGN_IN_KEY), (SETUP, SETUP_KEY))


def _link_model():
    from .models import SessionAccountLink  # at call time, as Django's own store imports its model
    return SessionAccountLink


def _session_model():
    return db.SessionStore.get_model_class()


def account_of(value) -> str | None:
    """The account id ``value`` names, as text in its one canonical spelling, or None when it names none: read with the
    user model's primary key's to_python, as django.contrib.auth.get_user and User.objects.get(pk=...) read it."""
    if value is None:
        return None
    try:
        pk = get_user_model()._meta.pk.to_python(value)
    except (ValidationError, TypeError, ValueError, OverflowError):
        return None
    return None if pk is None or pk == '' else str(pk)


def signed_in_kind(door) -> str:
    """The kind of link of a session signed in at ``door`` (its request_meta.SESSION_DOOR): the admin door's own kind,
    so the cap of one door's sign-ins never ends the other door's (repair round 2, sessions-1); SIGNED_IN at the cpt door
    or at none (a session the session policy ends at its next request)."""
    return SIGNED_IN_ADMIN if door == request_meta.ADMIN else SIGNED_IN


def account_links(data) -> frozenset:
    """{(kind, account)} of every way the session data ``data`` names an account (see the module)."""
    if not isinstance(data, dict):
        return frozenset()
    found = set()
    account = account_of(data.get(SESSION_KEY))
    if account is not None:
        found.add((signed_in_kind(data.get(request_meta.SESSION_DOOR)), account))
    for kind, name in WAITING_LINKS:
        state = data.get(name)
        if isinstance(state, dict):
            account = account_of(state.get('user'))
            if account is not None:
                found.add((kind, account))
    return frozenset(found)


def links_of_key(session_key) -> dict:
    """{(kind, account): link id} of the links of one session key."""
    rows = _link_model().objects.filter(session_key=session_key).values_list('pk', 'kind', 'account_id')
    return {(kind, str(account)): pk for pk, kind, account in rows}


def pending_can_complete(state, moment) -> bool:
    """Whether the pending sign-in ``state`` (a session's PENDING_SIGN_IN_KEY) can still complete at ``moment`` (whole
    seconds since the epoch) by its age, read exactly as studio.second_factor.pending reads it: a dict whose 'ref' is a
    string and whose 'at' - an int, never a bool - is no older than SECOND_FACTOR_PENDING_SECONDS and not in the future.
    (pending() also drops one whose failures, account or password no longer let it complete; this reads the age alone,
    so it never calls a pending sign-in dead that pending() would let complete.)"""
    if not isinstance(state, dict) or not isinstance(state.get('ref'), str):
        return False
    at = state.get('at')
    if not isinstance(at, int) or isinstance(at, bool):
        return False
    return 0 <= moment - at <= settings.SECOND_FACTOR_PENDING_SECONDS


def lock_accounts(accounts) -> list:
    """Take the row lock of every account in ``accounts`` (ids, in any spelling account_of reads) in the caller's
    transaction: SELECT ... FOR NO KEY UPDATE on the user rows, in id order (see the module: the lock order). The ids
    locked (an id with no account locks nothing)."""
    ids = sorted({account for account in (account_of(value) for value in accounts) if account is not None})
    if not ids:
        return []
    model = get_user_model()
    using = router.db_for_write(model)
    no_key = connections[using].features.has_select_for_no_key_update
    return list(model._default_manager.using(using).select_for_update(no_key=no_key).filter(pk__in=ids)
                .order_by('pk').values_list('pk', flat=True))


def _live_sessions(now):
    return _session_model().objects.filter(expire_date__gt=now)


def sync_links(session_key, links, now=None) -> None:
    """Make the links of ``session_key`` exactly ``links`` ({(kind, account)}); a link that is new caps its account's
    sessions of its kind (accounts in id order). Called inside the transaction that saved the session, after its row was
    written (and after the save took the row lock of each account a new link names)."""
    current = links_of_key(session_key)
    stale = [pk for link, pk in current.items() if link not in links]
    if stale:
        _link_model().objects.filter(pk__in=stale).delete()
    new = sorted(link for link in links if link not in current)
    if not new:
        return
    now = now or timezone.now()
    model = _link_model()
    model.objects.bulk_create([model(session_key=session_key, kind=kind, account_id=account, created_at=now)
                               for kind, account in new], ignore_conflicts=True)
    for kind, account in sorted(new, key=lambda link: (link[1], link[0])):
        cap_account_sessions(account, kind, keep_session_key=session_key, now=now)


def _end_beyond_the_limit(session_keys, link, now) -> int:
    """End - in session key order - each of ``session_keys`` (live sessions beyond the cap's limit) whose data still
    names ``link`` ((kind, account)), except a pending sign-in that can still complete (pending_can_complete: kept), and
    remove the link of each whose data no longer names it. Inside the cap's transaction, which holds the account's row
    lock. The number ended."""
    if not session_keys:
        return 0
    kind, account = link
    data_of = {row.session_key: row.get_decoded()
               for row in _live_sessions(now).filter(session_key__in=session_keys)}
    moment = request_meta.epoch_seconds(now)
    ended, unlinked = 0, []
    for session_key in sorted(session_keys):
        data = data_of.get(session_key)
        if data is None or link not in account_links(data):
            unlinked.append(session_key)
        elif kind == PENDING and pending_can_complete(data.get(PENDING_SIGN_IN_KEY), moment):
            continue
        else:
            SessionStore(session_key=session_key)._delete_row_and_links(session_key)
            ended += 1
    if unlinked:
        _link_model().objects.filter(session_key__in=unlinked, account_id=account, kind=kind).delete()
    return ended


def cap_account_sessions(account, kind, *, keep_session_key=None, now=None) -> int:
    """End the oldest live sessions of ``account`` and ``kind`` beyond settings.SESSION_LIVE_PER_ACCOUNT, keeping
    ``keep_session_key`` (the session that made the new link) whatever its place, after taking the account's row lock
    (see the module); a link whose session is gone or expired is removed on the way. A pending sign-in that can still
    complete is never ended, and counts toward the limit: a pending link no older than SECOND_FACTOR_PENDING_SECONDS is
    not even read - its session's 'at' is never later than the link's created_at (studio.second_factor.begin writes it
    before the save that makes the link), so every pending sign-in that can still complete is among them - and an older
    one beyond the limit is ended only when its own 'at' says it can no longer complete. The number of sessions ended."""
    account = account_of(account)
    if account is None:
        return 0
    now = now or timezone.now()
    limit = max(1, settings.SESSION_LIVE_PER_ACCOUNT)
    model = _link_model()
    with transaction.atomic(using=router.db_for_write(model)):
        lock_accounts([account])
        live = Exists(_live_sessions(now).filter(session_key=OuterRef('session_key')))
        links = (model.objects.filter(account_id=account, kind=kind).exclude(session_key=keep_session_key)
                 .annotate(live=live).order_by('-created_at', '-pk'))
        room = limit - (0 if keep_session_key is None else 1)
        if kind == PENDING:
            since = now - timedelta(seconds=settings.SECOND_FACTOR_PENDING_SECONDS)
            if room > 0:
                room -= len(links.filter(live=True, created_at__gte=since).values_list('pk', flat=True)[:room])
            links = links.filter(created_at__lt=since)
        beyond, gone = [], []
        for pk, session_key, is_live in links.values_list('pk', 'session_key', 'live'):
            if not is_live:
                gone.append(pk)
            elif room > 0:
                room -= 1
            else:
                beyond.append(session_key)
        ended = _end_beyond_the_limit(beyond, (kind, account), now)
        if gone:
            model.objects.filter(pk__in=gone).delete()
    return ended


def end_account_sessions(account, keep_session_key=None, now=None) -> int:
    """End every live session that names ``account`` - signed in as it or waiting on it - except ``keep_session_key``,
    reading only that account's links (see the module): the account's row lock first, then its live sessions in one
    query, each one's data read again, each deleted through the store in session key order, in one transaction; then
    the account's links whose session is gone, expired or no longer names it are removed. The number ended."""
    account = account_of(account)
    if account is None:
        return 0
    now = now or timezone.now()
    model = _link_model()
    links = model.objects.filter(account_id=account)
    with transaction.atomic(using=router.db_for_write(model)):
        lock_accounts([account])
        keys = set(links.values_list('session_key', flat=True)) - {keep_session_key}
        ended, stale = 0, []
        for session in _live_sessions(now).filter(session_key__in=keys).order_by('session_key'):
            if any(linked == account for _, linked in account_links(session.get_decoded())):
                SessionStore(session_key=session.session_key)._delete_row_and_links(session.session_key)
                ended += 1
            else:
                stale.append(session.session_key)
        if stale:
            links.filter(session_key__in=stale).delete()
        # the account's links whose session is gone or expired (the kept session is live: never here)
        links.exclude(Exists(_live_sessions(now).filter(session_key=OuterRef('session_key')))).delete()
    return ended


def prune_session_links(now=None) -> int:
    """Remove every link whose session is gone or expired (the daily maintenance). The number removed."""
    now = now or timezone.now()
    live = _live_sessions(now).filter(session_key=OuterRef('session_key'))
    return _link_model().objects.exclude(Exists(live)).delete()[0]


class SessionStore(db.SessionStore):
    """Django's database store, with the links of every session it writes (see the module)."""

    _cpt_links = frozenset()

    def create_model_instance(self, data):
        self._cpt_links = account_links(data)  # exactly what this save writes
        return super().create_model_instance(data)

    def _using(self):
        return router.db_for_write(self.model)

    def save(self, must_create=False):
        if self.session_key is None:
            return self.create()
        with transaction.atomic(using=self._using()):
            # the accounts a new link names are locked before the session's row is written (the lock order)
            named = account_links(self._get_session(no_load=must_create))
            adding = named if must_create or not named else named - set(links_of_key(self.session_key))
            lock_accounts(account for _, account in adding)
            super().save(must_create=must_create)
            sync_links(self.session_key, self._cpt_links)

    def _delete_row_and_links(self, session_key):
        """Delete the session's row and its links, in the caller's transaction (which holds the accounts' row locks)."""
        super().delete(session_key)
        _link_model().objects.filter(session_key=session_key).delete()

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        with transaction.atomic(using=self._using()):
            # the accounts its links name are locked before its row is deleted (the lock order): cycle_key's delete of
            # the old key in a sign-in, whose last_login update comes after it, meets the account first
            lock_accounts(account for _, account in links_of_key(session_key))
            self._delete_row_and_links(session_key)

    def load(self):
        session = self._get_session_from_db()
        if session is None:
            return {}
        data = self.decode(session.session_data)
        named = account_links(data)
        if named and not named <= set(links_of_key(session.session_key)):
            self._session_key = None  # written by something other than this store: refused, as a key not in the table
            return {}
        return data

    @classmethod
    def clear_expired(cls):
        super().clear_expired()
        prune_session_links()

    async def aload(self):
        return await sync_to_async(self.load)()

    async def acreate(self):
        return await sync_to_async(self.create)()

    async def asave(self, must_create=False):
        return await sync_to_async(self.save)(must_create)

    async def adelete(self, session_key=None):
        return await sync_to_async(self.delete)(session_key)

    @classmethod
    async def aclear_expired(cls):
        return await sync_to_async(cls.clear_expired)()
