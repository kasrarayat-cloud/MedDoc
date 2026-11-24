"""Refutation round 1 of release 1, builder S's repairs (sessions by account, and bounded growth), each pinned by its
finding's own input (refute-int/findings-round1.json).

avail-0  ending one account's sessions read and decoded every live session of the site, and one member's own sign-ins
         made sessions without limit. Now the site's session store (studio.session_store) keeps which accounts each
         session names, end_sessions reads only the account's own, and one account holds at most
         SESSION_LIVE_PER_ACCOUNT live sessions of each kind.

The reproductions use only what existed before the repair - end_sessions, real sign-ins, the django_session table - so
they fail on the shipped code. Synthetic accounts and sessions only."""
from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import timedelta
from datetime import timezone as dt_timezone
from importlib import import_module
from pathlib import Path
from unittest import mock

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends import db as django_db_store
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.models import Session
from django.db import DatabaseError, connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import client_contract, maintenance, models, read_audit, request_meta, sessions
from studio.migrations import __path__ as MIGRATIONS
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

PASSWORD = 'synthetic-pass-123!'
NEW_PASSWORD = 'synthetic-new-pass-4567!'
ADDRESS = '203.0.113.7'  # the lens's own address (P9)


def store_class():
    return import_module(settings.SESSION_ENGINE).SessionStore


def signed_in_data(user, door=request_meta.CPT):
    """What a sign-in at ``door`` leaves in a session: django.contrib.auth's keys and this release's."""
    now = request_meta.epoch_seconds()
    return {SESSION_KEY: str(user.pk), BACKEND_SESSION_KEY: 'django.contrib.auth.backends.ModelBackend',
            HASH_SESSION_KEY: user.get_session_auth_hash(), request_meta.SESSION_DOOR: door,
            request_meta.SESSION_AUTH_AT: now, request_meta.SESSION_LAST_ACTIVE: now,
            request_meta.SESSION_SIGN_IN_REF: str(uuid.uuid4())}


def pending_data(operator):
    """What the admin door's checked password leaves in an anonymous session (studio.second_factor.begin)."""
    return {sessions.PENDING_SIGN_IN_KEY: {'user': str(operator.pk), 'at': request_meta.epoch_seconds(),
                                           'ref': str(uuid.uuid4()), 'next': '/ops/',
                                           'pw': operator.get_session_auth_hash()},
            request_meta.SESSION_SIGN_IN_REF: str(uuid.uuid4())}


def seed_live_sessions(user, count, *, linked=True, data=None):
    """``count`` live sessions signed in as ``user``, written straight into django_session as the lens's probe P2 wrote
    them (bulk, so no cap applies), each with its link when ``linked`` and the site's store keeps links: what one
    member's own sign-ins leave behind. Their keys."""
    encode = django_db_store.SessionStore().encode
    expire = timezone.now() + timedelta(hours=8)
    keys = [uuid.uuid4().hex + uuid.uuid4().hex[:8] for _ in range(count)]
    Session.objects.bulk_create([Session(session_key=key, session_data=encode(data or signed_in_data(user)),
                                         expire_date=expire) for key in keys], batch_size=2000)
    link = getattr(models, 'SessionAccountLink', None)
    if linked and link is not None:
        now = timezone.now()
        link.objects.bulk_create([link(session_key=key, account_id=user.pk, kind=link.SIGNED_IN, created_at=now)
                                  for key in keys], batch_size=2000)
    return keys


def store_session(data):
    """A session saved through the site's store, as every request saves one. Its key."""
    store = store_class()()
    store.update(data)
    store.create()
    return store.session_key


def live_keys_naming(user):
    """The keys of every live session signed in as ``user`` or waiting on it, read the slow way (the test's own)."""
    now = timezone.now()
    return {row.session_key for row in Session.objects.filter(expire_date__gt=now)
            if sessions.waits_on(row.get_decoded(), str(user.pk))}


class DecodeCounter:
    """Counts the session decodes made while it is active (every reader decodes through SessionBase.decode)."""

    def __enter__(self):
        self.count = 0
        real = SessionBase.decode

        def counting(store, data):
            self.count += 1
            return real(store, data)
        self._patch = mock.patch.object(SessionBase, 'decode', counting)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()


# --- avail-0: the cost of ending one account's sessions -----------------------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class EndSessionsCostTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.owner = f.member(self.ws, role=models.Membership.OWNER)
        self.reviewer = f.member(self.ws, role=models.Membership.REVIEWER)
        self.elsewhere = f.member(f.workspace('Another synthetic practice'))

    def test_ending_one_accounts_sessions_reads_that_accounts_sessions_and_no_other(self):
        mine = [store_session(signed_in_data(self.reviewer)) for _ in range(3)]
        others = seed_live_sessions(self.elsewhere, 600)  # the lens's input, scaled: another member's own sign-ins
        with DecodeCounter() as decoded:
            ended = sessions.end_sessions(self.reviewer)
        self.assertEqual(ended, 3)
        self.assertEqual(decoded.count, len(mine))  # each of the account's own read again once; none of the 600
        self.assertFalse(Session.objects.filter(session_key__in=mine).exists())
        self.assertEqual(Session.objects.filter(session_key__in=others).count(), 600)

    def test_an_owners_access_toggle_reads_the_colleagues_sessions_and_not_the_sites(self):
        """The finding's own path: the owner's POST /api/members/<id>/access {active: false}, which ends the colleague's
        sessions while it holds the practice's membership locks (api._set_member_access)."""
        client = Client()
        self.assertEqual(client.post('/login/', {'username': self.owner.username, 'password': PASSWORD},
                                     REMOTE_ADDR=ADDRESS).status_code, 302)
        colleague = Client()
        self.assertEqual(colleague.post('/login/', {'username': self.reviewer.username, 'password': PASSWORD},
                                        REMOTE_ADDR=ADDRESS).status_code, 302)
        seed_live_sessions(self.owner, 600)  # the owner's own inflated sessions (P4B's 28,800, scaled)
        with DecodeCounter() as decoded:
            answer = client.post(f'/api/members/{self.reviewer.pk}/access', '{"active": false}',
                                 content_type='application/json', HTTP_X_CPT_STUDIO_CLIENT=client_contract.VERSION)
        self.assertEqual(answer.status_code, 200, answer.content[:300])
        # the request's own session, and the colleague's one session read again before it ends: nothing else
        self.assertEqual(decoded.count, 2)
        self.assertNotEqual(colleague.get('/api/session').status_code, 200)


# --- avail-0: one account's own sign-ins are bounded ----------------------------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class AccountCapTests(TestCase):
    @override_settings(SESSION_LIVE_PER_ACCOUNT=5)
    def test_a_members_own_sign_ins_never_hold_more_than_the_cap_and_the_oldest_end(self):
        """P9's input: one member signs in again and again from one address with no cookie, every sign-in right."""
        member = f.member(f.workspace(), role=models.Membership.OWNER)
        browsers = []
        for _ in range(8):
            browser = Client()
            self.assertEqual(browser.post('/login/', {'username': member.username, 'password': PASSWORD},
                                          REMOTE_ADDR=ADDRESS).status_code, 302)
            browsers.append(browser)
        self.assertEqual(len(live_keys_naming(member)), 5)
        signed_in = [browser.get('/api/session').status_code == 200 for browser in browsers]
        self.assertEqual(signed_in, [False] * 3 + [True] * 5)  # the three oldest ended; the five newest kept

    def test_the_deployed_cap(self):
        self.assertEqual(settings.SESSION_LIVE_PER_ACCOUNT, 20)
        member = f.member(f.workspace())
        for _ in range(23):
            Client().force_login(member)
        self.assertEqual(len(live_keys_naming(member)), 20)

    @override_settings(SESSION_LIVE_PER_ACCOUNT=3)
    def test_a_pending_sign_in_ends_only_an_older_pending_one_never_a_signed_in_session(self):
        """A checked password alone makes a pending sign-in at the admin door: its cap is its own, so whoever holds an
        operator's password but not the key can never sign the operator out."""
        operator = f.user('capped-operator')
        signed = ops.admin_client(operator)  # signed in at the admin door, with the second factor
        signed_key = signed.session.session_key
        for _ in range(6):
            door = Client(HTTP_HOST=settings.ADMIN_HOST)
            self.assertEqual(door.post('/login/', {'username': operator.username, 'password': PASSWORD},
                                       REMOTE_ADDR=ADDRESS).status_code, 302)
        live = live_keys_naming(operator)
        self.assertIn(signed_key, live)
        self.assertEqual(len(live - {signed_key}), 3)  # the three newest pending sign-ins
        self.assertEqual(signed.get('/ops/').status_code, 200)


# --- avail-0: every session this release honours is indexed -------------------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class IndexCompletenessTests(TestCase):
    def assert_index_exact(self):
        """Every live session's accounts are among its links, and every link names a live session that names it."""
        from studio import session_store
        now = timezone.now()
        live = {row.session_key: session_store.account_links(row.get_decoded())
                for row in Session.objects.filter(expire_date__gt=now)}
        links = {}
        for row in models.SessionAccountLink.objects.all():
            links.setdefault(row.session_key, set()).add((row.kind, str(row.account_id)))
        for key, named in live.items():
            self.assertLessEqual(set(named), links.get(key, set()), 'a live session is not indexed')
        for key, linked in links.items():
            self.assertIn(key, live, 'a link names a session that is gone')
            self.assertLessEqual(linked, set(live[key]), 'a link names an account its session does not')

    def test_every_flow_of_the_release_leaves_each_live_session_indexed(self):
        member = f.member(f.workspace())
        first, second = Client(), Client()
        for browser in (first, second):  # login(): cycle_key, then the save that signs in
            self.assertEqual(browser.post('/login/', {'username': member.username, 'password': PASSWORD})
                             .status_code, 302)
        self.assert_index_exact()
        before = first.session.session_key
        changed = first.post('/account/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD,
                                           'new_password_again': NEW_PASSWORD})
        self.assertEqual(changed.status_code, 302, changed.content[:300])  # update_session_auth_hash: cycle_key
        self.assertNotEqual(first.session.session_key, before)
        self.assertEqual(first.get('/api/session').status_code, 200)  # kept, under its new key
        self.assertNotEqual(second.get('/api/session').status_code, 200)  # ended
        self.assertEqual(live_keys_naming(member), {first.session.session_key})
        self.assert_index_exact()
        operator = f.user('indexed-operator')
        ops.grant(operator)
        door = Client(HTTP_HOST=settings.ADMIN_HOST)
        self.assertEqual(door.post('/login/', {'username': operator.username, 'password': PASSWORD}).status_code, 302)
        self.assertEqual(door.session[sessions.PENDING_SIGN_IN_KEY]['user'], str(operator.pk))
        console = ops.admin_client(operator)
        self.assert_index_exact()
        self.assertEqual(console.post('/logout/everywhere').status_code, 302)
        self.assertEqual(live_keys_naming(operator), set())  # the pending sign-in waited on the account: ended too
        self.assertEqual(first.post('/logout/').status_code, 302)
        self.assertEqual(live_keys_naming(member), set())
        self.assert_index_exact()
        self.assertFalse(models.SessionAccountLink.objects.exists())

    def test_cycle_key_moves_every_link_to_the_new_key(self):
        operator = f.user('cycled-operator')
        store = store_class()()
        store.update({**signed_in_data(operator, request_meta.ADMIN), **pending_data(operator),
                      sessions.SETUP_KEY: {'claim': str(uuid.uuid4()), 'token': str(uuid.uuid4()),
                                           'user': str(operator.pk)}})
        store.create()
        old = store.session_key
        store.cycle_key()
        self.assertNotEqual(store.session_key, old)
        self.assertFalse(models.SessionAccountLink.objects.filter(session_key=old).exists())
        self.assertEqual(set(models.SessionAccountLink.objects.filter(session_key=store.session_key)
                             .values_list('kind', flat=True)), {'signed_in', 'pending', 'setup'})
        self.assert_index_exact()


@override_settings(STORAGES=PLAIN_STATIC)
class UnindexedSessionTests(TestCase):
    """A session row whose data names an account with no link - the revision before release 1 writes such rows, as
    does anything that bypasses the store - is never honoured: so end_sessions, which finds sessions by their links,
    never leaves one it cannot find signed in."""

    def test_a_session_written_without_its_link_signs_no_one_in(self):
        member = f.member(f.workspace())
        unlinked = seed_live_sessions(member, 1, linked=False)[0]
        linked = seed_live_sessions(member, 1, linked=True)[0]
        answers = {}
        for name, key in (('unlinked', unlinked), ('linked', linked)):
            browser = Client()
            browser.cookies[settings.SESSION_COOKIE_NAME] = key
            answers[name] = browser.get('/api/session').status_code
        self.assertEqual(answers, {'unlinked': 401, 'linked': 200})  # the control: the same data with its link
        self.assertEqual(sessions.end_sessions(member), 1)

    def test_a_pending_sign_in_written_without_its_link_waits_on_no_one(self):
        operator = f.user('unlinked-operator')
        key = seed_live_sessions(operator, 1, linked=False, data=pending_data(operator))[0]
        self.assertEqual(store_class()(key).load(), {})
        self.assertEqual(store_class()(store_session(pending_data(operator))).load()[sessions.PENDING_SIGN_IN_KEY]
                         ['user'], str(operator.pk))  # the control: saved through the store

    def test_an_account_id_in_another_spelling_is_indexed_and_ended(self):
        """django.contrib.auth reads the signed-in id with the primary key's to_python, so an upper-case spelling signs
        the account in: the index reads it the same way, and so does end_sessions."""
        member = f.member(f.workspace())
        key = store_session({**signed_in_data(member), SESSION_KEY: str(member.pk).upper()})
        self.assertEqual(live_keys_naming(member), {key})
        self.assertEqual(sessions.end_sessions(member), 1)
        self.assertFalse(Session.objects.filter(session_key=key).exists())


# --- avail-0: what the revision before release 1 and the installer leave behind is harmless -------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class StaleLinkTests(TestCase):
    def test_a_sign_out_by_the_revision_before_release_1_leaves_a_link_nothing_trusts(self):
        member = f.member(f.workspace())
        browser = Client()
        browser.force_login(member)
        key = browser.session.session_key
        django_db_store.SessionStore(key).delete()  # the older revision's own store: nothing refuses it
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertTrue(models.SessionAccountLink.objects.filter(session_key=key).exists())
        self.assertEqual(sessions.end_sessions(member), 0)  # a link is never taken for a session
        self.assertFalse(models.SessionAccountLink.objects.filter(session_key=key).exists())

    def test_the_installers_delete_of_every_session_leaves_links_nothing_trusts(self):
        members = [f.member(f.workspace()) for _ in range(2)]
        for member in members:
            Client().force_login(member)
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM django_session')  # a forward from a revision before release 1
        self.assertEqual(models.SessionAccountLink.objects.count(), 2)
        again = Client()
        again.force_login(members[0])
        self.assertEqual(again.get('/api/session').status_code, 200)
        self.assertEqual([sessions.end_sessions(member) for member in members], [1, 0])
        self.assertFalse(models.SessionAccountLink.objects.exists())

    def test_the_revision_before_release_1_keeps_its_sessions_on_the_new_schema(self):
        member = f.member(f.workspace())
        old = django_db_store.SessionStore()
        old.update(signed_in_data(member))
        old.create()  # its own store, which writes no link
        self.assertEqual(django_db_store.SessionStore(old.session_key).load()[SESSION_KEY], str(member.pk))
        old['counted'] = 1
        old.save()
        old.cycle_key()
        self.assertEqual(django_db_store.SessionStore(old.session_key).load()['counted'], 1)
        old.flush()
        self.assertFalse(Session.objects.exists())

    def test_both_stores_read_each_others_session_data(self):
        """The site's store keeps Django's class name, so its key salt and its encoding are the older revision's."""
        data = {'synthetic': 'value'}
        self.assertEqual(store_class()().decode(django_db_store.SessionStore().encode(data)), data)
        self.assertEqual(django_db_store.SessionStore().decode(store_class()().encode(data)), data)


@override_settings(STORAGES=PLAIN_STATIC)
class MaintenanceLinkTests(TestCase):
    def test_the_daily_maintenance_removes_links_whose_session_is_gone_or_expired(self):
        from studio import session_store
        member = f.member(f.workspace())
        keys = [store_session(signed_in_data(member)) for _ in range(3)]
        Session.objects.filter(session_key=keys[0]).delete()  # gone, as an older revision or the installer leaves it
        Session.objects.filter(session_key=keys[1]).update(expire_date=timezone.now() - timedelta(minutes=1))
        with tempfile.TemporaryDirectory() as scratch, override_settings(ORIGINALS_DIR=Path(scratch) / 'originals'), \
                mock.patch('tempfile.gettempdir', return_value=scratch):
            counts = maintenance.run_daily()
        self.assertEqual(counts['session_links_pruned'], 2)
        self.assertEqual(models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT).data['session_links_pruned'], 2)
        self.assertEqual(list(models.SessionAccountLink.objects.values_list('session_key', flat=True)), [keys[2]])
        self.assertEqual(session_store.prune_session_links(), 0)


@override_settings(STORAGES=PLAIN_STATIC)
class AsyncStoreTests(TestCase):
    def test_the_async_methods_keep_the_links_and_refuse_the_unindexed(self):
        member = f.member(f.workspace())
        store = store_class()()
        store.update(signed_in_data(member))
        async_to_sync(store.asave)()
        key = store.session_key
        self.assertTrue(models.SessionAccountLink.objects.filter(session_key=key).exists())
        self.assertEqual(async_to_sync(store_class()(key).aload)()[SESSION_KEY], str(member.pk))
        async_to_sync(store.acycle_key)()
        self.assertTrue(models.SessionAccountLink.objects.filter(session_key=store.session_key).exists())
        self.assertFalse(models.SessionAccountLink.objects.filter(session_key=key).exists())
        async_to_sync(store.adelete)()
        self.assertFalse(models.SessionAccountLink.objects.exists())
        unlinked = seed_live_sessions(member, 1, linked=False)[0]
        self.assertEqual(async_to_sync(store_class()(unlinked).aload)(), {})


class StoreContractTests(SimpleTestCase):
    def test_the_migration_is_judged_safe_by_the_installers_own_gate(self):
        sys.path.insert(0, str(Path(MIGRATIONS[0]).parents[1] / 'ops'))
        import install
        verdicts = install.migration_safety(Path(MIGRATIONS[0]))
        self.assertTrue(all(verdict['safe'] for verdict in verdicts.values()), verdicts)
        self.assertIn('SessionAccountLink: a new table no older revision reads',
                      verdicts['0018_r1_availability']['why'])

    def test_the_store_the_site_runs_is_the_one_end_sessions_accepts(self):
        from studio import second_factor, session_store
        self.assertEqual(settings.SESSION_ENGINE, 'studio.session_store')
        self.assertEqual(sessions.SESSION_STORES, ('studio.session_store',))
        self.assertEqual((session_store.SIGNED_IN, session_store.PENDING, session_store.SETUP),
                         (models.SessionAccountLink.SIGNED_IN, models.SessionAccountLink.PENDING,
                          models.SessionAccountLink.SETUP))
        self.assertEqual((second_factor.PENDING, second_factor.ENROLMENT),
                         (sessions.PENDING_SIGN_IN_KEY, sessions.SETUP_KEY))
        self.assertEqual(session_store.SessionStore.__qualname__, django_db_store.SessionStore.__qualname__)
        for engine in ('django.contrib.sessions.backends.db', 'django.contrib.sessions.backends.cached_db'):
            with self.subTest(engine=engine), self.settings(SESSION_ENGINE=engine):
                with self.assertRaises(sessions.Refused):
                    sessions.end_sessions(mock.Mock(pk=uuid.uuid4()))


# --- avail-3: the read records - bounded growth per session, and the reads page on an index -----------------------------

from tests.test_read_audit import TITLE_MARKER, ReadCase, member_client  # noqa: E402 - the read records' own fixtures

LIST = '/api/encounters'


class ListRepeatTests(ReadCase):
    """The finding's input: one member's GET /api/encounters again and again. One session listing the same practice's
    list again within READ_AUDIT_LIST_REPEAT_SECONDS adds no row: its record counts the repeats and the latest time."""

    def lists(self):
        return self.rows(view=read_audit.MEMBER_LIST)

    def at(self, start, seconds):
        return mock.patch.object(timezone, 'now', return_value=start + timedelta(seconds=seconds))

    def test_one_session_listing_again_and_again_is_one_record_with_a_count(self):
        start = timezone.now()
        for second in range(0, 50, 10):  # five reads in 40 seconds
            with self.at(start, second):
                self.assertEqual(self.member.get(LIST).status_code, 200)
        (first,) = self.lists()
        repeat = models.AccessRecordRepeat.objects.get(record_id=first.pk)
        self.assertEqual((repeat.repeats, repeat.last_at, first.as_of), (4, start + timedelta(seconds=40), start))
        # what an auditor reads: who, the practice, how many rows, from when to when, how many times
        self.assertEqual((first.actor_id, first.workspace_id, first.count, first.outcome),
                         (self.reviewer.pk, self.ws.pk, self.ws.encounters.count(), read_audit.SERVED))
        with self.at(start, 61):  # past the window: a record of its own
            self.member.get(LIST)
        self.assertEqual(len(self.lists()), 2)

    def test_anything_new_in_a_list_read_is_a_record_of_its_own(self):
        start = timezone.now()
        with self.at(start, 0):
            self.member.get(LIST)
        with self.at(start, 1):
            member_client(self.reviewer).get(LIST)  # another session of the same person
            self.member.get(LIST, REMOTE_ADDR='198.51.100.9')  # the same session from another address
            member_client(self.viewer).get(LIST)  # another person
        f.encounter(self.ws, self.reviewer, title=f'{TITLE_MARKER} one more synthetic note')
        with self.at(start, 2):
            self.member.get(LIST)  # the practice's list changed: another count
        self.assertEqual(len(self.lists()), 5)
        self.assertFalse(models.AccessRecordRepeat.objects.exists())

    def test_every_detail_view_and_download_read_still_writes_its_own_record(self):
        start = timezone.now()
        reads = self.reads()
        for second in range(3):
            with self.at(start, second):
                for kind, url in reads.items():
                    self.assertEqual(self.member.get(url).status_code, 200, kind)
        for kind in reads:
            with self.subTest(kind=kind):
                self.assertEqual(len(self.rows(view=kind)), 1 if kind == read_audit.MEMBER_LIST else 3)

    def test_a_repeat_whose_count_cannot_be_written_serves_nothing(self):
        self.assertEqual(self.member.get(LIST).status_code, 200)

        class CountFails:
            ops = connection.ops

            def cursor(self):
                raise DatabaseError('synthetic count failure')
        with mock.patch.object(read_audit, 'connection', CountFails()):
            answer = self.member.get(LIST)
        self.assertEqual((answer.status_code, answer.json()['error']), (503, read_audit.NOT_RECORDED))
        self.assertNotIn(TITLE_MARKER.encode(), answer.content)
        self.assertEqual(self.member.get(LIST).status_code, 200)  # the control: counted again
        self.assertEqual(models.AccessRecordRepeat.objects.get().repeats, 1)


@override_settings(STORAGES=PLAIN_STATIC)
class ReadsPageIndexTests(TestCase):
    """The finding's other half: the console's reads page read the whole table unfiltered, by kind and by day. Each of
    its views now reads an index, a rare kind's included."""

    def window_query(self, path):
        with CaptureQueriesContext(connection) as seen:
            self.assertEqual(self.ops.get(path).status_code, 200)
        found = [item['sql'] for item in seen.captured_queries if 'FROM "studio_accessrecord"' in item['sql']
                 and 'ORDER BY "studio_accessrecord"."created_at" DESC' in item['sql'] and 'LIMIT 101' in item['sql']]
        self.assertEqual(len(found), 1, path)
        return found[0]

    def plan(self, sql):
        with connection.cursor() as cursor:
            cursor.execute('EXPLAIN ' + sql)
            return '\n'.join(row[0] for row in cursor.fetchall())

    def test_every_view_of_the_reads_page_reads_an_index_not_the_table(self):
        ws = f.workspace()
        member = f.member(ws)
        kinds = [read_audit.MEMBER_LIST] * 19 + [read_audit.MEMBER_DETAIL]
        models.AccessRecord.objects.bulk_create([models.AccessRecord(
            host='cpt', view=kinds[index % 20], actor_id=member.pk, actor_kind='human', actor_role='reviewer',
            workspace_id=ws.pk, count=3, outcome=read_audit.SERVED) for index in range(20_000)], batch_size=5000)
        operator = f.user('reads-auditor')
        self.ops = ops.admin_client(operator)
        self.ops.get('/ops/activity/reads')  # an ops.reads row: the rare kind
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_accessrecord')
        newest = models.AccessRecord.objects.order_by('-created_at', '-pk')[150]
        cursor_text = f'{newest.created_at.astimezone(dt_timezone.utc):%Y%m%dT%H%M%S.%fZ}~{newest.pk}'
        today = timezone.now().date().isoformat()
        for query in ('', '?kind=member.list', '?kind=ops.reads', f'?day={today}', '?day=2001-01-01',
                      f'?kind=ops.reads&day={today}', f'?before={cursor_text}'):
            with self.subTest(query=query):
                plan = self.plan(self.window_query('/ops/activity/reads' + query))
                self.assertNotIn('Seq Scan on studio_accessrecord', plan)
                self.assertIn('studio_access', plan)
