"""The site's session store (refutation round 1 of release 1, avail-0): Django's database store - the same django_session
table and rows, so the revision before release 1 keeps reading and writing it during the blue/green switch and after a
switch-back (RELEASE-1-SPEC 2.1, 6.3) - that also keeps which accounts each session names, in a side table
(studio.models.SessionAccountLink: session key, account, kind), so that ending one account's sessions costs that account's
own sessions and never the whole table.

How a session names an account (account_links): signed in as it (django.contrib.auth's SESSION_KEY: kind SIGNED_IN), or
waiting on it - a checked password waiting for its key at the admin door (PENDING_SIGN_IN_KEY: PENDING) or a setup under
way (SETUP_KEY: SETUP), each a dict naming the account in 'user'. An account is read the way every reader of those keys
reads it - the user model's primary key's to_python, as django.contrib.auth.get_user and User.objects.get(pk=...) do -
so one account is one link whatever spelling of its id a session holds.

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
            that kind (cap_account_sessions): one account's own sign-ins cannot grow the table without bound, and a pending
            sign-in - made with a password alone - only ever ends an older pending sign-in, never a signed-in session.
  the async methods run the synchronous ones (one implementation; this site's web is synchronous).

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

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends import db
from django.core.exceptions import ValidationError
from django.db import router, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

SIGNED_IN, PENDING, SETUP = 'signed_in', 'pending', 'setup'  # the kinds of link (SessionAccountLink.kind)
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


def account_links(data) -> frozenset:
    """{(kind, account)} of every way the session data ``data`` names an account (see the module)."""
    if not isinstance(data, dict):
        return frozenset()
    found = set()
    account = account_of(data.get(SESSION_KEY))
    if account is not None:
        found.add((SIGNED_IN, account))
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


def _live_sessions(now):
    return _session_model().objects.filter(expire_date__gt=now)


def sync_links(session_key, links, now=None) -> None:
    """Make the links of ``session_key`` exactly ``links`` ({(kind, account)}); a link that is new caps its account's
    sessions of its kind. Called inside the transaction that saved the session, after its row was written."""
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
    for kind, account in new:
        cap_account_sessions(account, kind, keep_session_key=session_key, now=now)


def _end_if_named(session_key, link, now) -> bool:
    """Delete the live session ``session_key`` through the store when its data still names ``link`` ((kind, account));
    else remove that link of it. Whether a session was ended."""
    kind, account = link
    session = _live_sessions(now).filter(session_key=session_key).first()
    if session is not None and link in account_links(session.get_decoded()):
        SessionStore(session_key=session_key).delete()
        return True
    _link_model().objects.filter(session_key=session_key, account_id=account, kind=kind).delete()
    return False


def cap_account_sessions(account, kind, *, keep_session_key=None, now=None) -> int:
    """End the oldest live sessions of ``account`` and ``kind`` beyond settings.SESSION_LIVE_PER_ACCOUNT, keeping
    ``keep_session_key`` (the session that made the new link) whatever its place; a link whose session is gone or expired
    is removed on the way. The number of sessions ended."""
    now = now or timezone.now()
    limit = max(1, settings.SESSION_LIVE_PER_ACCOUNT)
    live = _live_sessions(now).filter(session_key=OuterRef('session_key'))
    rows = (_link_model().objects.filter(account_id=account, kind=kind).annotate(live=Exists(live))
            .order_by('-created_at', '-pk').values_list('pk', 'session_key', 'live'))
    kept = 1 if keep_session_key is not None else 0
    ended, gone = 0, []
    for pk, session_key, is_live in rows:
        if session_key == keep_session_key:
            continue
        if not is_live:
            gone.append(pk)
        elif kept < limit:
            kept += 1
        elif _end_if_named(session_key, (kind, account), now):
            ended += 1
    if gone:
        _link_model().objects.filter(pk__in=gone).delete()
    return ended


def end_account_sessions(account, keep_session_key=None, now=None) -> int:
    """End every live session that names ``account`` - signed in as it or waiting on it - except ``keep_session_key``,
    reading only that account's links (see the module): its live sessions in one query, each one's data read again,
    each deleted through the store, in one transaction; then the account's links whose session is gone, expired or no
    longer names it are removed. The number ended."""
    account = account_of(account)
    if account is None:
        return 0
    now = now or timezone.now()
    links = _link_model().objects.filter(account_id=account)
    with transaction.atomic(using=router.db_for_write(_link_model())):
        keys = set(links.values_list('session_key', flat=True)) - {keep_session_key}
        ended, stale = 0, []
        for session in _live_sessions(now).filter(session_key__in=keys):
            if any(linked == account for _, linked in account_links(session.get_decoded())):
                SessionStore(session_key=session.session_key).delete()
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
            super().save(must_create=must_create)
            sync_links(self.session_key, self._cpt_links)

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        with transaction.atomic(using=self._using()):
            super().delete(session_key)
            _link_model().objects.filter(session_key=session_key).delete()

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
