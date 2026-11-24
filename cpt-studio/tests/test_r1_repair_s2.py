"""Repair round 2 of release 1, builder s2's repairs (refute-r2/findings-round2.json): the session store's cap, its doors,
its lock order and the session tag, each pinned by its finding's own input - through the real doors, with the real
py_webauthn verification and the software authenticator of tests.test_second_factor, and for the lock order with real
concurrency: two web workers are two threads, each with its own PostgreSQL connection in autocommit, as production's two
gunicorn workers are.

S2-1  sessions-0, secondfactor-1, regression-0: twenty password-only sign-ins at the admin door, made between the
      operator's password and key, ended the operator's own pending sign-in (the cap of pending sign-ins ended the
      oldest). Now the cap never ends a pending sign-in that can still complete; it still counts toward the limit.
S2-2  sessions-1, and secondfactor-1's dual-role half: for an operator who is also a member, twenty password-only sign-ins
      at the doctors' door ended the operator's console session (one signed-in kind for both doors). Now each door is
      its own kind.
S2-3  records-0, records-1: a password change deadlocked with a sign-out everywhere and with an owner turning access off,
      and a recovery-code sign-in with the console's password change: one request answered 500 ('deadlock detected').
      Now every store write that adds a link, every delete of a linked session and every end of an account's sessions
      takes the account's row lock first, and sessions are deleted in key order.
S2-4  the switchback-1 verifier: the session tag was 32 hex digits, which the customer scan's long_hex rule reads in every
      signed-in page and in the ping's answer. Now it is 128 bits in the form of a UUID.

Synthetic accounts and sessions only."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.crypto import salted_hmac

from studio import client_contract, models, request_meta, second_factor, session_store, sessions, throttle
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC
from tests.test_r1_repair_s import pending_data, signed_in_data, store_session
from tests.test_second_factor import (ADMIN, CPT, MOMENT, NOW, PASSWORD, Clock, admin_client, enrolled_operator,
                                      options_of, password_step, sign_in)

OWN = '203.0.113.10'  # the operator's own browser
OTHER = '198.51.100.66'  # someone holding the password alone
NEW_PASSWORD = 'synthetic s2 passphrase 4711 for the repair'
FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']  # the flood matrix's hundreds of sign-ins (see its test)


def pending_links(user):
    return models.SessionAccountLink.objects.filter(account_id=user.pk, kind=session_store.PENDING)


def live_pending_keys(user):
    """The keys of the live sessions with a checked password of ``user`` waiting for its key, read the slow way."""
    now = timezone.now()
    out = set()
    for row in Session.objects.filter(expire_date__gt=now):
        state = row.get_decoded().get(sessions.PENDING_SIGN_IN_KEY)
        if isinstance(state, dict) and state.get('user') == str(user.pk):
            out.add(row.session_key)
    return out


def kinds_of(session_key):
    return set(models.SessionAccountLink.objects.filter(session_key=session_key).values_list('kind', flat=True))


def signed_in_as(client, user):
    return client.session.get(SESSION_KEY) == str(user.pk)


def flood(user, count, *, host=ADMIN, address=OTHER):
    """``count`` right-password sign-ins at ``host``'s door, each from a fresh browser with no cookie."""
    for _ in range(count):
        thief = Client(HTTP_HOST=host, REMOTE_ADDR=address)
        answer = thief.post('/login/', {'username': user.get_username(), 'password': PASSWORD})
        assert answer.status_code == 302, (answer.status_code, answer.content[:200])


def known_device(user, authenticator):
    """The operator's own browser after an earlier sign-in with the key and a sign-out: it keeps its known-device
    cookie (studio.throttle; repair round 1, auth-0)."""
    own = admin_client(REMOTE_ADDR=OWN)
    done = sign_in(own, user, authenticator)
    assert (done.status_code, done['Location']) == (302, '/ops/'), done
    assert throttle.device_cookie_name() in own.cookies
    assert own.post('/logout/').status_code == 302 and not signed_in_as(own, user)
    return own


# --- S2-1: the cap never ends a pending sign-in that can still complete --------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class PendingSignInFloodTests(TestCase):
    """The finding's input: someone holding the operator's password alone signs in again and again at the admin door,
    each time from a fresh browser, while the operator's own sign-in waits for the key."""

    def test_the_findings_input_twenty_password_only_sign_ins_between_the_password_and_the_key(self):
        operator, authenticator = enrolled_operator('flooded-operator')
        own = admin_client(REMOTE_ADDR=OWN)
        first = password_step(own, operator)
        self.assertEqual((first.status_code, first['Location']), (302, '/login/second-factor'))
        pending_key = own.cookies[settings.SESSION_COOKIE_NAME].value
        options = options_of(own)  # the page asks for the challenge; the operator reaches for the key
        flood(operator, 20)
        self.assertTrue(Session.objects.filter(session_key=pending_key).exists())  # the operator's own sign-in is kept
        self.assertEqual(len(live_pending_keys(operator)), 21)  # none ended: each can still complete
        answer = own.post('/login/second-factor', {'credential': json.dumps(authenticator.assertion(options))})
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        self.assertTrue(signed_in_as(own, operator))
        self.assertEqual(own.get('/ops/').status_code, 200)

    @override_settings(PASSWORD_HASHERS=FAST_HASHER)
    def test_the_operator_signs_in_after_20_40_and_100_by_key_and_by_recovery_code_on_a_known_device_and_a_new_one(self):
        """Every pair of (way, device), each met by 20, 40 and 100 password-only sign-ins made between the operator's
        password and the key or code. The accounts are made under a fast hasher: what is tested is the cap, and the
        690 sign-ins of real Argon2 would add some 75 s to the suite (the finding's own input above runs it)."""
        for count in (20, 40, 100):
            for via in ('key', 'recovery'):
                for device in ('known', 'new'):
                    with self.subTest(count=count, via=via, device=device):
                        operator, authenticator = enrolled_operator(f'flood-{count}-{via}-{device}')
                        own = known_device(operator, authenticator) if device == 'known' else admin_client(
                            REMOTE_ADDR=OWN)
                        codes = second_factor.new_recovery_codes(operator) if via == 'recovery' else None
                        first = password_step(own, operator)
                        self.assertEqual((first.status_code, first['Location']), (302, '/login/second-factor'))
                        options = options_of(own) if via == 'key' else None
                        flood(operator, count)
                        self.assertEqual(len(live_pending_keys(operator)), count + 1)
                        if via == 'key':
                            answer = own.post('/login/second-factor',
                                              {'credential': json.dumps(authenticator.assertion(options))})
                        else:
                            answer = own.post('/login/recovery', {'code': codes[0]})
                        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
                        self.assertTrue(signed_in_as(own, operator))
                        self.assertEqual(own.get('/ops/').status_code, 200)
                        if via == 'recovery':
                            self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT - 1)

    @override_settings(SESSION_LIVE_PER_ACCOUNT=4)
    def test_only_pending_sign_ins_that_can_no_longer_complete_are_ended_beyond_the_limit(self):
        """The bound it leaves: the limit, plus the pending sign-ins made in the last SECOND_FACTOR_PENDING_SECONDS."""
        operator = f.user('bounded-operator')
        ops.grant(operator)
        window = settings.SECOND_FACTOR_PENDING_SECONDS

        def made(count):
            keys = []
            for _ in range(count):
                door = Client(HTTP_HOST=ADMIN, REMOTE_ADDR=OTHER)
                self.assertEqual(door.post('/login/', {'username': operator.username, 'password': PASSWORD})
                                 .status_code, 302)
                keys.append(door.cookies[settings.SESSION_COOKIE_NAME].value)
            return keys

        with Clock() as clock:
            early = made(9)
            self.assertEqual(live_pending_keys(operator), set(early))  # 9 > the limit of 4: all can still complete
            clock.advance(window + 1)
            middle = made(2)  # the early nine can no longer complete: beyond the limit they end
            self.assertEqual(live_pending_keys(operator), set(middle) | set(early[-2:]))
            clock.advance(window // 2)
            late = made(5)  # the middle two can still complete; the two early ones left are beyond the limit
            self.assertEqual(live_pending_keys(operator), set(middle) | set(late))
            self.assertLessEqual(len(live_pending_keys(operator)), settings.SESSION_LIVE_PER_ACCOUNT + 7)
            clock.advance(window + 1)
            last = made(1)  # every earlier one can no longer complete: the newest of them fill the limit
            self.assertEqual(live_pending_keys(operator), set(last) | set(late[-3:]))
        self.assertEqual(set(pending_links(operator).values_list('session_key', flat=True)), set(last) | set(late[-3:]))

    def test_a_pending_sign_in_is_kept_exactly_while_second_factor_pending_would_let_it_complete(self):
        """The cap reads a pending sign-in's age from its own 'at', as second_factor.pending reads it: one at exactly
        SECOND_FACTOR_PENDING_SECONDS is kept even when its link is older than that (a clock step), one a second older
        is ended - and the cap's reading agrees with pending()'s over every shape of 'at'."""
        operator = f.user('boundary-operator')
        ops.grant(operator)
        window = settings.SECOND_FACTOR_PENDING_SECONDS
        with Clock(), override_settings(SESSION_LIVE_PER_ACCOUNT=1):
            keys = {}
            for age in (window, window + 1):
                data = pending_data(operator)
                data[sessions.PENDING_SIGN_IN_KEY]['at'] = NOW - age
                keys[age] = store_session(data)
            pending_links(operator).update(created_at=MOMENT - timedelta(seconds=window + 5))
            newest = store_session(pending_data(operator))
            self.assertEqual(live_pending_keys(operator), {newest, keys[window]})
        factory = RequestFactory()
        shapes = [NOW - age for age in (-1, 0, 1, window - 1, window, window + 1, 10 * window)]
        shapes += [True, False, float(NOW), str(NOW), None, [NOW]]
        with Clock():
            for at in shapes:
                for ref in (str(uuid.uuid4()), None, 7):
                    state = {'user': str(operator.pk), 'at': at, 'ref': ref, 'next': '/ops/',
                             'pw': operator.get_session_auth_hash()}
                    request = factory.get('/login/second-factor', HTTP_HOST=ADMIN)
                    request.session = session_store.SessionStore()
                    request.session[sessions.PENDING_SIGN_IN_KEY] = dict(state)
                    with self.subTest(at=at, ref=ref):
                        self.assertEqual(second_factor.pending(request)[0] is not None,
                                         session_store.pending_can_complete(state, NOW))

    def test_a_flood_of_pending_sign_ins_that_can_still_complete_is_never_read_by_the_cap(self):
        """The cost the pending rule adds: the cap reads the limit's newest pending sign-ins and the older ones, never
        the young ones beyond the limit - however many a flood made, a new sign-in's cap decodes none of them."""
        from tests.test_r1_repair_s import DecodeCounter
        operator = f.user('flood-cost-operator')
        ops.grant(operator)
        for _ in range(200):
            store_session(pending_data(operator))
        with DecodeCounter() as decoded, CaptureQueriesContext(connection) as captured:
            store_session(pending_data(operator))
        self.assertEqual(decoded.count, 0)
        self.assertEqual(pending_links(operator).count(), 201)
        self.assertLess(len(captured), 20)


# --- S2-2: a signed-in session's kind names its door ---------------------------------------------------------------------

def member_operator(username, role=models.Membership.OWNER):
    """An operator with a grant and a key who is also a member of a practice: the admin door says an operator who is also
    a member is the operator there, and the doctors' door admits any account with an active membership on its password
    alone (B3)."""
    operator, authenticator = enrolled_operator(username)
    models.Membership.objects.create(user=operator, workspace=f.workspace(f'{username} practice'), role=role)
    return operator, authenticator


@override_settings(STORAGES=PLAIN_STATIC)
class DoorKindTests(TestCase):
    def console(self, operator, authenticator):
        """A console session: the operator's password, then the key."""
        browser = admin_client(REMOTE_ADDR=OWN)
        answer = sign_in(browser, operator, authenticator)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        self.assertEqual(browser.get('/ops/').status_code, 200)
        return browser

    def doctors(self, user):
        browser = Client(HTTP_HOST=CPT)
        self.assertEqual(browser.post('/login/', {'username': user.get_username(), 'password': PASSWORD}).status_code,
                         302)
        return browser

    def test_the_findings_input_twenty_password_only_sign_ins_at_the_doctors_door_leave_the_console_signed_in(self):
        operator, authenticator = member_operator('member-operator')
        console = self.console(operator, authenticator)
        flood(operator, 20, host=CPT)
        self.assertEqual(console.get('/ops/').status_code, 200)
        self.assertTrue(signed_in_as(console, operator))
        flood(operator, 20, host=CPT)  # forty: the doctors' door's own cap ends its own oldest, never the console
        self.assertEqual(console.get('/ops/').status_code, 200)
        links = models.SessionAccountLink.objects.filter(account_id=operator.pk)
        self.assertEqual(links.filter(kind=session_store.SIGNED_IN).count(), settings.SESSION_LIVE_PER_ACCOUNT)
        self.assertEqual(list(links.filter(kind=session_store.SIGNED_IN_ADMIN).values_list('session_key', flat=True)),
                         [console.session.session_key])

    @override_settings(SESSION_LIVE_PER_ACCOUNT=2)
    def test_each_door_caps_its_own_sign_ins_and_never_the_other_doors(self):
        operator, authenticator = member_operator('two-door-operator')
        doctors = self.doctors(operator)
        consoles = [self.console(operator, authenticator) for _ in range(3)]
        self.assertEqual([browser.get('/ops/').status_code == 200 for browser in consoles], [False, True, True])
        self.assertEqual(doctors.get('/api/session').status_code, 200)  # the console's cap never ends a doctors' session
        later = [self.doctors(operator) for _ in range(2)]
        self.assertNotEqual(doctors.get('/api/session').status_code, 200)  # the doctors' door's own oldest
        self.assertEqual([browser.get('/api/session').status_code for browser in later], [200, 200])
        self.assertEqual([browser.get('/ops/').status_code for browser in consoles[1:]], [200, 200])

    def test_the_kind_each_door_and_each_flow_writes(self):
        operator, authenticator = member_operator('kinds-operator')
        doctors = self.doctors(operator)
        self.assertEqual(kinds_of(doctors.session.session_key), {session_store.SIGNED_IN})
        console = self.console(operator, authenticator)
        self.assertEqual(kinds_of(console.session.session_key), {session_store.SIGNED_IN_ADMIN})
        codes = second_factor.new_recovery_codes(operator)
        recovered = admin_client(REMOTE_ADDR=OWN)
        password_step(recovered, operator)
        self.assertEqual(kinds_of(recovered.session.session_key), {session_store.PENDING})
        answer = recovered.post('/login/recovery', {'code': codes[0]})
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        self.assertEqual(kinds_of(recovered.session.session_key), {session_store.SIGNED_IN_ADMIN})
        before = console.session.session_key  # the console's password change: update_session_auth_hash's cycle_key
        changed = console.post('/account/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD,
                                             'new_password_again': NEW_PASSWORD})
        self.assertEqual((changed.status_code, changed['Location']), (302, '/account/?done=changed'))
        self.assertNotEqual(console.session.session_key, before)
        self.assertEqual(kinds_of(console.session.session_key), {session_store.SIGNED_IN_ADMIN})
        self.assertEqual(kinds_of(before), set())
        self.assertEqual(console.get('/ops/').status_code, 200)
        member = f.member(f.workspace('Synthetic practice s2 kinds'))  # the doctors' door's own change
        browser = self.doctors(member)
        before = browser.session.session_key
        changed = browser.post('/account/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD,
                                             'new_password_again': NEW_PASSWORD})
        self.assertEqual(changed.status_code, 302)
        self.assertEqual((kinds_of(browser.session.session_key), kinds_of(before)), ({session_store.SIGNED_IN}, set()))

    def test_setup_waits_as_its_own_kind_and_ends_signed_in_as_the_admin_doors(self):
        from tests.test_second_factor import Authenticator
        operator = f.user('s2-setup-operator')
        ops.grant(operator)
        operator.set_unusable_password()  # a fresh host's operator: setup sets the password
        operator.save()
        _token, code = second_factor.issue_setup_code(operator, 'Synthetic Person')
        browser = admin_client()
        started = browser.post('/login/enrol', {'step': 'code', 'code': code, 'new_password': NEW_PASSWORD,
                                                'new_password_again': NEW_PASSWORD})
        self.assertEqual((started.status_code, started['Location']), (303, '/login/enrol'))
        self.assertEqual(kinds_of(browser.session.session_key), {session_store.SETUP})
        options = options_of(browser, '/login/enrol/options')
        done = browser.post('/login/enrol', {'step': 'key', 'label': 'Synthetic key',
                                             'credential': json.dumps(Authenticator().register(options))})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(kinds_of(browser.session.session_key), {session_store.SIGNED_IN_ADMIN})
        self.assertEqual(browser.get('/ops/').status_code, 200)

    def test_a_session_whose_door_changes_has_its_link_moved_and_stays_signed_in(self):
        member = f.member(f.workspace())
        store = session_store.SessionStore()
        store.update(signed_in_data(member, request_meta.CPT))
        store.create()
        self.assertEqual(kinds_of(store.session_key), {session_store.SIGNED_IN})
        for door, kind in ((request_meta.ADMIN, session_store.SIGNED_IN_ADMIN), ('no-door', session_store.SIGNED_IN),
                           (None, session_store.SIGNED_IN), (request_meta.ADMIN, session_store.SIGNED_IN_ADMIN)):
            with self.subTest(door=door):
                store[request_meta.SESSION_DOOR] = door
                store.save()
                self.assertEqual(kinds_of(store.session_key), {kind})
                self.assertEqual(session_store.SessionStore(store.session_key).load()[SESSION_KEY], str(member.pk))
        self.assertEqual(sessions.end_sessions(member), 1)
        self.assertFalse(models.SessionAccountLink.objects.exists())

    def test_every_kind_fits_the_link_table_and_each_door_is_its_own(self):
        field = models.SessionAccountLink._meta.get_field('kind')
        self.assertFalse(field.choices)  # a new kind needs no migration
        self.assertEqual(len(set(session_store.KINDS)), 4)
        for kind in session_store.KINDS:
            with self.subTest(kind=kind):
                self.assertLessEqual(len(kind), field.max_length)
        self.assertEqual((session_store.SIGNED_IN, session_store.PENDING, session_store.SETUP),
                         (models.SessionAccountLink.SIGNED_IN, models.SessionAccountLink.PENDING,
                          models.SessionAccountLink.SETUP))
        self.assertEqual([session_store.signed_in_kind(door) for door in (request_meta.ADMIN, request_meta.CPT, None)],
                         [session_store.SIGNED_IN_ADMIN, session_store.SIGNED_IN, session_store.SIGNED_IN])


# --- S2-3: every transaction that adds or ends an account's sessions meets the account first ------------------------------

GATE = 7300215  # the advisory lock a held request waits on (this module's own number)
WORKER_NAME = re.compile(r'r2s2-[a-z]+')


class Worker(threading.Thread):
    """One request, ``send()``, on a thread and database connection of its own - a second web worker - whose
    application_name is the thread's name; its answer's status and Location, or the exception it raised."""

    def __init__(self, name, send):
        super().__init__(name=f'r2s2-{name}', daemon=True)
        assert WORKER_NAME.fullmatch(self.name), self.name
        self.send = send
        self.status = self.location = self.error = None

    def run(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('application_name', %s, false)", [self.name])
            answer = self.send()
            self.status, self.location = answer.status_code, answer.get('Location')
        except BaseException as exc:  # noqa: BLE001 - the test reports it
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            connection.close()


class ServerErrors(logging.Handler):
    """Every error django.request logs (a 500), as its exception's class and first line."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.seen = []

    def emit(self, record):
        exc = record.exc_info[1] if record.exc_info else None
        text = str(exc) if exc is not None else record.getMessage()
        self.seen.append(f'{type(exc).__name__ if exc is not None else "-"}: {text.splitlines()[0] if text else ""}')


@contextmanager
def server_errors():
    handler = ServerErrors()
    logger = logging.getLogger('django.request')
    logger.addHandler(handler)
    try:
        yield handler.seen
    finally:
        logger.removeHandler(handler)


def wait_of(worker):
    """(wait_event_type, wait_event) of ``worker``'s backend, or (None, None)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE application_name = %s '
                       'AND datname = current_database()', [worker.name])
        row = cursor.fetchone()
    return tuple(row) if row else (None, None)


def wait_until(predicate, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@contextmanager
def held_right_after_deleting(session_key, worker):
    """Hold ``worker``'s request right after it deletes the row of ``session_key``, with every lock it holds then: an
    AFTER DELETE trigger on django_session, firing only on that worker's connection and only for that row, waits on an
    advisory lock the test holds until release(). Nothing in the code under test is patched: the trigger only lengthens
    a hold the request already has (as the records verifiers' gate did). Dropped afterwards."""
    assert re.fullmatch(r'[a-z0-9]{32}', session_key), session_key
    assert WORKER_NAME.fullmatch(worker.name), worker.name
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_lock(%s)', [GATE])
        cursor.execute('CREATE OR REPLACE FUNCTION r2s2_gate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                       f"IF current_setting('application_name') = '{worker.name}' THEN "
                       f'PERFORM pg_advisory_lock_shared({GATE}); PERFORM pg_advisory_unlock_shared({GATE}); '
                       'END IF; RETURN NULL; END $$')
        cursor.execute('CREATE TRIGGER r2s2_gate AFTER DELETE ON django_session FOR EACH ROW '
                       f"WHEN (OLD.session_key = '{session_key}') EXECUTE FUNCTION r2s2_gate()")
    released = []

    def release():
        if not released:
            released.append(True)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [GATE])
    try:
        yield release
    finally:
        release()
        with connection.cursor() as cursor:
            cursor.execute('DROP TRIGGER IF EXISTS r2s2_gate ON django_session')
            cursor.execute('DROP FUNCTION IF EXISTS r2s2_gate()')


@override_settings(STORAGES=PLAIN_STATIC)
class LockOrderRaceTests(TransactionTestCase):
    """The findings' inputs, each with the schedule its verifier paused it at: two requests on two connections, the
    first held right after it deleted a session's row (holding that row and whatever it took before), the second sent
    while it is held and run until it waits on a lock; then the first is let go. Each pair completes with no 500."""

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'r2s2%%'")
            self.assertEqual(cursor.fetchone()[0], 0)
        super().tearDown()

    def browser(self, user, host=CPT):
        client = Client(HTTP_HOST=host, raise_request_exception=False)
        self.assertEqual(client.post('/login/', {'username': user.get_username(), 'password': PASSWORD}).status_code,
                         302)
        return client

    @staticmethod
    def change(client):
        return lambda: client.post('/account/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD,
                                                 'new_password_again': NEW_PASSWORD})

    @staticmethod
    def met_first_by_the_shipped_ender(by_key):
        """The two sessions in the order the shipped end_account_sessions met them (its query had no order): the one it
        met first changes the password, as in the finding, so the shipped code deadlocks on this schedule."""
        return list(Session.objects.filter(expire_date__gt=timezone.now(), session_key__in=list(by_key))
                    .values_list('session_key', flat=True))

    def race(self, first, held_key, second):
        with server_errors() as errors, held_right_after_deleting(held_key, first) as release:
            first.start()
            self.assertTrue(wait_until(lambda: wait_of(first) == ('Lock', 'advisory')), 'the first never reached the hold')
            second.start()
            self.assertTrue(wait_until(lambda: second.status is not None or wait_of(second)[0] == 'Lock'),
                            'the second request neither finished nor waited on a lock')
            release()
            first.join(60)
            second.join(60)
        self.assertFalse(first.is_alive() or second.is_alive())
        return errors

    def assertChangeAnswered(self, change):  # noqa: N802 - an assertion, named as unittest's are
        """The password change was answered: 302 to the account page, or 400 when the act served after it (a sign-out
        everywhere, an access off) ended its new session before its own answer could save it - Django's
        SessionInterrupted, as at 3048931b (the records-0 verifier); the change itself was made either way."""
        self.assertIsNone(change.error)
        self.assertIn((change.status, change.location), {(302, '/account/?done=changed'), (400, None)})

    def test_a_password_change_and_a_sign_out_everywhere_at_once(self):
        """records-0: the change is held right after deleting the other session's row; the other session's sign-out
        everywhere is sent meanwhile. The shipped code: the ender deleted the changer's own session first and waited on
        the other, while the change, holding the other, waited on its own: 'deadlock detected', one 500."""
        member = f.member(f.workspace('Synthetic practice s2 sign-out'))
        clients = [self.browser(member), self.browser(member)]
        by_key = {client.cookies[settings.SESSION_COOKIE_NAME].value: client for client in clients}
        changer_key, other_key = self.met_first_by_the_shipped_ender(by_key)
        change = Worker('change', self.change(by_key[changer_key]))
        ender = Worker('ender', lambda: by_key[other_key].post('/logout/everywhere'))
        errors = self.race(change, other_key, ender)
        self.assertEqual(errors, [])
        self.assertChangeAnswered(change)
        self.assertEqual((ender.status, ender.location, ender.error), (302, '/login/', None))
        member.refresh_from_db()
        self.assertTrue(member.check_password(NEW_PASSWORD))
        self.assertEqual(live_keys(member), set())  # served after the change, the sign-out ended its new key too
        self.assertEqual(sorted(models.SecurityEvent.objects.filter(subject_id=member.pk).values_list('event', flat=True)),
                         ['password.changed', 'sessions.ended_everywhere'])

    def test_a_password_change_and_an_owner_turning_access_off_at_once(self):
        """records-0's second pair: the owner's access off holds the practice's membership locks when it ends the
        member's sessions (api._set_member_access), while the change writes its audit rows, whose foreign keys reach
        the practice and the account: no cycle, and both are served."""
        practice = f.workspace('Synthetic practice s2 toggle')
        member = f.member(practice)
        owner = f.member(practice, role=models.Membership.OWNER)
        clients = [self.browser(member), self.browser(member)]
        owners = self.browser(owner)
        by_key = {client.cookies[settings.SESSION_COOKIE_NAME].value: client for client in clients}
        changer_key, other_key = self.met_first_by_the_shipped_ender(by_key)
        change = Worker('change', self.change(by_key[changer_key]))
        toggle = Worker('toggle', lambda: owners.post(f'/api/members/{member.pk}/access', json.dumps({'active': False}),
                                                      content_type='application/json',
                                                      **{client_contract.WSGI_KEY: client_contract.VERSION}))
        errors = self.race(change, other_key, toggle)
        self.assertEqual(errors, [])
        self.assertChangeAnswered(change)
        self.assertEqual((toggle.status, toggle.error), (200, None))
        member.refresh_from_db()
        self.assertTrue(member.check_password(NEW_PASSWORD))
        self.assertFalse(models.Membership.objects.get(user=member, workspace=practice).active)
        self.assertEqual(sorted(models.AuditEvent.objects.filter(workspace=practice).values_list('event', flat=True)),
                         ['member.access_off', 'member.password_changed'])
        self.assertEqual(live_keys(member), set())

    def test_a_recovery_code_sign_in_and_the_consoles_password_change_at_once(self):
        """records-1: the recovery is held right after login()'s cycle_key deleted the pending sign-in's row; the
        console's password change is sent meanwhile. The shipped code: the recovery held that row and then waited on the
        account's row (last_login), which the change held while it waited on that row: 'deadlock detected'."""
        operator, authenticator = enrolled_operator('s2-race-operator')
        codes = second_factor.new_recovery_codes(operator)
        console = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        answer = sign_in(console, operator, authenticator)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        waiting = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        first = password_step(waiting, operator)
        self.assertEqual((first.status_code, first['Location']), (302, '/login/second-factor'))
        pending_key = waiting.cookies[settings.SESSION_COOKIE_NAME].value
        recover = Worker('recover', lambda: waiting.post('/login/recovery', {'code': codes[0]}))
        change = Worker('change', self.change(console))
        errors = self.race(recover, pending_key, change)
        self.assertEqual(errors, [])
        self.assertEqual((change.status, change.location, change.error), (302, '/account/?done=changed', None))
        self.assertEqual((recover.status, recover.location, recover.error), (302, '/ops/', None))
        operator.refresh_from_db()
        self.assertTrue(operator.check_password(NEW_PASSWORD))
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT - 1)
        events = set(models.SecurityEvent.objects.filter(subject_id=operator.pk).values_list('event', flat=True))
        self.assertLessEqual({'password.changed', 'second_factor.recovery_used'}, events)
        self.assertNotEqual(waiting.get('/ops/').status_code, 200)  # a sign-in made with the old password does not last
        self.assertEqual(console.get('/ops/').status_code, 200)


def live_keys(user):
    """The keys of every live session that names ``user``, read the slow way."""
    now = timezone.now()
    return {row.session_key for row in Session.objects.filter(expire_date__gt=now)
            if sessions.waits_on(row.get_decoded(), str(user.pk))}


LOCK = re.compile(r'FROM "studio_user" .*FOR NO KEY UPDATE')
SESSION_WRITE = re.compile(r'^\s*(INSERT INTO|UPDATE|DELETE FROM) "django_session"')
SESSION_DELETE = re.compile(r'^\s*DELETE FROM "django_session" WHERE')
# the sessions an end takes, locked in key order before any is deleted (session_store._delete_sessions_in_key_order)
SESSIONS_LOCKED = re.compile(r'^SELECT "django_session"\."session_key"(?: AS "session_key")? FROM "django_session" '
                             r'WHERE .* ORDER BY (?:1|"django_session"\."session_key") ASC FOR UPDATE$')


def deleted_keys(found):
    """The session keys the DELETE statements of ``found`` name, in statement order."""
    return [key for sql in found if SESSION_DELETE.search(sql) for key in re.findall(r"'([0-9a-z]{32})'", sql)]


def statements(function):
    with CaptureQueriesContext(connection) as captured:
        function()
    return [query['sql'] for query in captured.captured_queries]


def first_index(found, pattern):
    return next((index for index, sql in enumerate(found) if pattern.search(sql)), None)


def seeded(user, count, *, descending):
    """``count`` live sessions signed in as ``user``, with their links, written in one statement in key order - or in
    the reverse of it - so the table holds them in an order the test chose. Their keys, in key order."""
    keys = sorted(uuid.uuid4().hex for _ in range(count))
    encode = session_store.SessionStore().encode
    expire = timezone.now() + timedelta(hours=8)
    order = list(reversed(keys)) if descending else keys
    Session.objects.bulk_create([Session(session_key=key, session_data=encode(signed_in_data(user)), expire_date=expire)
                                 for key in order])
    now = timezone.now()
    models.SessionAccountLink.objects.bulk_create([models.SessionAccountLink(
        session_key=key, account_id=user.pk, kind=session_store.SIGNED_IN, created_at=now) for key in order])
    return keys


@override_settings(STORAGES=PLAIN_STATIC)
class LockOrderStatementTests(TestCase):
    """The order itself, statement by statement: the account's row lock comes before any session row is written or
    deleted, and sessions are deleted in key order whatever plan the database chooses."""

    def assert_locked_before(self, found, pattern):
        """The account's row lock was taken, before the first statement ``pattern`` matches."""
        lock, write = first_index(found, LOCK), first_index(found, pattern)
        self.assertIsNotNone(lock, 'no account row lock was taken')
        self.assertIsNotNone(write, 'no session row was written or deleted')
        self.assertLess(lock, write)

    def assert_ends_in_key_order(self, found, keys):
        """``keys`` - and no other session - were locked in key order and then deleted in one statement, after it."""
        taken, deleted = first_index(found, SESSIONS_LOCKED), first_index(found, SESSION_DELETE)
        self.assertIsNotNone(taken, 'the sessions were not locked in key order before they were deleted')
        self.assertIsNotNone(deleted, 'no session was deleted')
        self.assertLess(taken, deleted)
        self.assertEqual(re.findall(r"'([0-9a-z]{32})'", found[taken]), sorted(keys))
        self.assertEqual(sorted(deleted_keys(found)), sorted(keys))
        self.assertEqual(sum(1 for sql in found if SESSION_DELETE.search(sql)), 1)  # however many they are

    def test_a_store_write_that_adds_a_link_takes_the_accounts_lock_before_the_sessions_row(self):
        member = f.member(f.workspace())
        found = statements(lambda: store_session(signed_in_data(member)))
        self.assert_locked_before(found, SESSION_WRITE)
        key = store_session(signed_in_data(member))
        store = session_store.SessionStore(key)
        store.load()
        store['counted'] = 1
        self.assertIsNone(first_index(statements(store.save), LOCK))  # a save that adds no link takes none
        store[sessions.PENDING_SIGN_IN_KEY] = pending_data(member)[sessions.PENDING_SIGN_IN_KEY]
        found = statements(store.save)  # a link added to a session already written
        self.assert_locked_before(found, SESSION_WRITE)

    def test_a_delete_of_a_linked_session_and_a_sign_ins_cycle_key_take_the_lock_before_the_old_row(self):
        operator = f.user('s2-cycle-operator')
        key = store_session(pending_data(operator))
        store = session_store.SessionStore(key)
        store.load()
        store.pop(sessions.PENDING_SIGN_IN_KEY)  # complete_sign_in drops the pending state before login()'s cycle_key
        found = statements(store.cycle_key)
        self.assert_locked_before(found, re.compile(r'DELETE FROM "django_session"'))
        anonymous = store_session({'synthetic': 1})
        self.assertIsNone(first_index(statements(session_store.SessionStore(anonymous).delete), LOCK))

    def test_ending_an_accounts_sessions_locks_first_and_deletes_in_key_order_whatever_the_plan(self):
        member = f.member(f.workspace())
        for scan in ('index', 'sequential'):
            with self.subTest(scan=scan):
                keys = seeded(member, 8, descending=True)
                if scan == 'sequential':
                    with connection.cursor() as cursor:
                        cursor.execute('SET LOCAL enable_indexscan = off')
                        cursor.execute('SET LOCAL enable_bitmapscan = off')
                found = statements(lambda: self.assertEqual(sessions.end_sessions(member), 8))
                self.assert_locked_before(found, SESSIONS_LOCKED)  # the account, then the sessions in key order
                self.assert_ends_in_key_order(found, keys)

    @override_settings(SESSION_LIVE_PER_ACCOUNT=3)
    def test_the_cap_locks_first_and_ends_in_key_order(self):
        member = f.member(f.workspace())
        keys = seeded(member, 6, descending=False)  # the cap meets them newest first: the reverse of key order
        found = statements(lambda: store_session(signed_in_data(member)))
        self.assert_locked_before(found, SESSION_WRITE)
        self.assert_ends_in_key_order(found, keys[:4])  # the oldest four; the two newest fill the limit


# --- S2-4: the session tag carries nothing the customer scan reads --------------------------------------------------------

TAG_FORM = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
SURFACES = ('dom', 'json', 'header', 'file', 'bundle')


class TaggedRequest:
    """What session_tag reads of a request: its session's sign-in reference."""

    def __init__(self, ref):
        self.session = {request_meta.SESSION_SIGN_IN_REF: ref}


@override_settings(STORAGES=PLAIN_STATIC)
class SessionTagTests(TestCase):
    """The verifier's input: release 1's own signed-in page and the activity ping's answer, read by the customer scan
    (ops/scan_customer.py, as the suite loads it: tests.support.rounds.scan_customer), which the shipped tag failed with
    a long_hex hit on data-session (scan.bundle). The scanner and its denylist are unchanged."""

    def test_a_signed_in_page_and_the_pings_answer_carry_nothing_the_customer_scan_reads(self):
        scan = r.scan_customer()
        context = scan.scan_context()
        member = f.member(f.workspace())
        browser = Client()
        self.assertEqual(browser.post('/login/', {'username': member.username, 'password': PASSWORD}).status_code, 302)
        page = browser.get('/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        tag = re.search(r'<body[^>]* data-session="([^"]*)"', html).group(1)
        self.assertRegex(tag, TAG_FORM)
        self.assertEqual(scan.scan_text(html, context, 'bundle', 'GET /'), [])  # the scan's own reading of the page
        self.assertEqual(scan.scan_text(tag, context, 'dom', 'body[data-session]'), [])  # the walk's, of the attribute
        ping = browser.post('/session/activity')
        self.assertEqual(ping.status_code, 200)
        self.assertEqual(ping.json()['session'], tag)  # one tag for the session: the page compares them as strings
        self.assertEqual(scan.scan_json(ping.json(), context, 'POST /session/activity'), [])
        self.assertEqual(scan.scan_text(ping.content.decode(), context, 'json', 'POST /session/activity (text)'), [])
        other = Client()
        self.assertEqual(other.post('/login/', {'username': member.username, 'password': PASSWORD}).status_code, 302)
        self.assertNotEqual(other.post('/session/activity').json()['session'], tag)  # another sign-in, another tag

    def test_the_tag_keeps_its_128_bits_and_no_rule_of_the_denylist_reads_any_tag(self):
        scan = r.scan_customer()
        context = scan.scan_context()
        tags = set()
        for _ in range(3000):
            ref = uuid.uuid4()
            tag = sessions.session_tag(TaggedRequest(str(ref)))
            self.assertRegex(tag, TAG_FORM)
            self.assertEqual(uuid.UUID(tag).hex,
                             salted_hmac(sessions.SESSION_TAG_SALT, str(ref), algorithm='sha256').hexdigest()[:32])
            for surface in SURFACES:
                for text in (tag, f'<body data-session="{tag}">', json.dumps({'session': tag})):
                    hits = scan.scan_text(text, context, surface, 'tag')
                    if hits:
                        self.fail(f'{surface}: {hits}')
            tags.add(tag)
        self.assertEqual(len(tags), 3000)
        self.assertEqual(sessions.session_tag(TaggedRequest(None)), '')
        self.assertEqual(sessions.session_tag(TaggedRequest('not a reference')), '')
