"""Repair round 3 of release 1, builder s3's repairs (refute-r3/findings-round3.json), each pinned by its finding's own
input - through the real doors, with the real py_webauthn verification and the software authenticator of
tests.test_second_factor, and with real concurrency: every act is a thread with its own PostgreSQL connection in
autocommit, as production's two gunicorn workers are. A hold is a trigger (or a transaction of the test's own) that only
lengthens a hold the act already has; nothing in the code under test is patched, and PostgreSQL's own deadlock count is
asserted unchanged after every pair (tests.test_r1_repair_s2's helpers).

S3-1  cap-1, locks-0, regression-3, locks-1, locks-4: an act in flight outlived an end of the account's sessions. The
      key sign-in checked its key before it took the account's lock, and a server reset (or a sign-out everywhere)
      served in between left it a console session with no key; a key added during the reset survived it; a member's
      cpt-door sign-in racing an owner's access off stayed signed in. Now every act that opens a session or changes the
      account's credentials proves under the account's lock that what it stands on still holds
      (studio.sessions.act_still_stands) and refuses, changing nothing, when it does not: the key and recovery-code
      sign-ins, the recovery-code step-up, setup's key step, a key added or removed, the cpt door's sign-in and the
      account page's password change.

Synthetic accounts and sessions only."""
from __future__ import annotations

import io
import json
import threading
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.core.management import call_command
from django.db import connection, transaction
from django.test import Client, TransactionTestCase, override_settings

from studio import client_contract, models, second_factor, session_store, sessions
from tests.support import coding as f
from tests.test_frontend import PLAIN_STATIC
from tests.test_r1_repair_s2 import (OWN, WORKER_NAME, Call, Worker, assert_no_deadlock, deadlocks_counted,
                                     held_right_after_updating, held_right_after_writing, live_keys, server_errors,
                                     wait_of, wait_until)
from tests.test_second_factor import (ADMIN, PASSWORD, Authenticator, admin_client, enrolled_operator, options_of,
                                      password_step, reason_file, sign_in)

API = {client_contract.WSGI_KEY: client_contract.VERSION}
NEW_PASSWORD = 'synthetic s3 passphrase 6620 for the repair'
GATE = 7300316  # the advisory lock this module's own holds wait on (tests.test_r1_repair_s2 uses 7300215)


@contextmanager
def held_right_after_inserting_a_session(worker):
    """Hold ``worker``'s act right after its first INSERT of a django_session row (login()'s cycle_key at the cpt door),
    with every lock it holds then: an AFTER INSERT trigger firing only on that worker's connection waits on an advisory
    lock the test holds until release(). Nothing in the code under test is patched. Dropped afterwards."""
    assert WORKER_NAME.fullmatch(worker.name), worker.name
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_lock(%s)', [GATE])
        cursor.execute('CREATE OR REPLACE FUNCTION r3s3_gate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                       f"IF current_setting('application_name') = '{worker.name}' THEN "
                       f'PERFORM pg_advisory_lock_shared({GATE}); PERFORM pg_advisory_unlock_shared({GATE}); '
                       'END IF; RETURN NULL; END $$')
        cursor.execute('CREATE TRIGGER r3s3_gate AFTER INSERT ON django_session FOR EACH ROW '
                       'EXECUTE FUNCTION r3s3_gate()')
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
            cursor.execute('DROP TRIGGER IF EXISTS r3s3_gate ON django_session')
            cursor.execute('DROP FUNCTION IF EXISTS r3s3_gate()')


class Holder:
    """A transaction on a thread and connection of its own that takes ``take()``'s locks and keeps them until release():
    the third connection of the verifiers' queue schedules (an act holding the account, so the next ones queue)."""

    def __init__(self, name, take):
        self.held, self.let_go = threading.Event(), threading.Event()

        def hold():
            with transaction.atomic():
                take()
                self.held.set()
                self.let_go.wait(60)
        self.call = Call(name, hold)

    def __enter__(self):
        self.call.start()
        assert self.held.wait(30), 'the holder never took its locks'
        return self

    def release(self):
        self.let_go.set()

    def __exit__(self, *exc):
        self.release()
        self.call.join(60)
        assert self.call.error is None, self.call.error


def holding_the_account(user):
    return Holder('holder', lambda: session_store.lock_accounts([user.pk]))


def finished_or_waiting(act):
    """Whether ``act`` (a Worker or a Call) has finished, or waits on a lock."""
    return (getattr(act, 'status', None) is not None or getattr(act, 'done', False)
            or getattr(act, 'error', None) is not None or wait_of(act)[0] == 'Lock')


def waits_on_a_lock(act):
    return wait_until(lambda: wait_of(act)[0] == 'Lock', timeout=30)


def console_status(browser):
    return browser.get('/ops/').status_code


def pending_ref(browser):
    """The pending sign-in's reference (its LoginAttempt's) in ``browser``'s session."""
    return browser.session[second_factor.PENDING]['ref']


def outcome_of(ref):
    return models.LoginAttempt.objects.get(sign_in_ref=ref).outcome


def events_of(user):
    """The account's security events in the order they were written (their ids are UUIDs, in no order)."""
    return list(models.SecurityEvent.objects.filter(subject_id=user.pk).order_by('created_at')
                .values_list('event', flat=True))


class RaceCase(TransactionTestCase):
    """The race tests' shared checks: no trigger of this module or of s2's outlives a test."""

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'r3s3%%' OR tgname LIKE 'r2s2%%'")
            self.assertEqual(cursor.fetchone()[0], 0)
        super().tearDown()

    def finish(self, *acts):
        for act in acts:
            act.join(90)
        self.assertFalse(any(act.is_alive() for act in acts))

    def ready_key_sign_in(self, username):
        """An operator with one key, its password checked in a browser (the pending sign-in) and a valid assertion:
        (the account, the browser, the pending sign-in's reference, the key step)."""
        operator, authenticator = enrolled_operator(username)
        browser = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        self.assertEqual(password_step(browser, operator)['Location'], '/login/second-factor')
        ref = pending_ref(browser)
        credential = json.dumps(authenticator.assertion(options_of(browser)))
        return operator, browser, ref, Worker('key', lambda: browser.post('/login/second-factor',
                                                                          {'credential': credential}))

    def assert_key_sign_in_refused(self, operator, browser, ref, key):
        """What an end of the account's sessions served before the key step's commit leaves: the key step refused - its
        redirect to the sign-in page, or 400 when its answer met its session gone (Django's SessionInterrupted) - its
        attempt still pending (never signed_in), no console session for the account, and the console closed to it."""
        self.assertIsNone(key.error)
        self.assertIn((key.status, key.location), {(302, '/login/?reason=key'), (400, None)})
        self.assertEqual(outcome_of(ref), models.LoginAttempt.SECOND_FACTOR_PENDING)
        self.assertFalse(models.SessionAccountLink.objects.filter(account_id=operator.pk,
                                                                  kind=session_store.SIGNED_IN_ADMIN).exists())
        self.assertNotEqual(console_status(browser), 200)


# --- S3-1: no sign-in or key change outlives an end of the account's sessions -----------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class KeySignInAgainstAnEndOfSessionsTests(RaceCase):
    """cap-1, locks-0, regression-3: the admin door's key sign-in with an end of the account's sessions served between
    its key check (verify_key, its own transaction) and its sign-in's transaction."""

    def test_the_reset_served_while_the_key_check_holds_its_key_row(self):
        """cap-1 and locks-0's gate: the key step held right after verify_key's UPDATE of its key row; the server's
        reset takes the account and waits on that row; then the key step is let go. The shipped code: the reset
        removed the key and ended the pending session, then the sign-in completed - 302 /ops/, and GET /ops/ answered
        200 with no key on the account."""
        operator, browser, ref, key = self.ready_key_sign_in('s3-reset-key-row')
        reset = Call('reset', lambda: second_factor.reset(operator, 'Synthetic Person'))
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_writing('studio_secondfactorcredential', 'UPDATE', 'user_id',
                                                                 operator.pk, key) as release:
            key.start()
            self.assertTrue(wait_until(lambda: wait_of(key) == ('Lock', 'advisory')), 'the key step never held')
            reset.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(reset)), 'the reset neither finished nor waited')
            release()
            self.finish(key, reset)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((reset.done, reset.error), (True, None))
        self.assertEqual(second_factor.active_keys(operator).count(), 0)
        self.assert_key_sign_in_refused(operator, browser, ref, key)

    def test_the_reset_queued_first_on_the_account_and_the_key_step_behind_it(self):
        """cap-1's T2, locks-0's queue and regression-3, with no trigger: a third connection holds the account; the
        reset queues on it, then the key step - its key check already committed - queues behind the reset; the holder
        lets go."""
        operator, browser, ref, key = self.ready_key_sign_in('s3-reset-queue')
        reset = Call('reset', lambda: second_factor.reset(operator, 'Synthetic Person'))
        before = deadlocks_counted()
        with server_errors() as errors, holding_the_account(operator) as holder:
            reset.start()
            self.assertTrue(waits_on_a_lock(reset), 'the reset never queued on the account')
            key.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(key)), 'the key step neither finished nor waited')
            self.assertEqual(models.SecondFactorCredential.objects.get(user=operator).sign_count, 1)  # its check done
            holder.release()
            self.finish(key, reset)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((reset.done, reset.error), (True, None))
        self.assertEqual(second_factor.active_keys(operator).count(), 0)
        self.assert_key_sign_in_refused(operator, browser, ref, key)

    def test_the_ruled_act_queued_first_on_the_account(self):
        """cap-1's T4: the queue schedule with the reset made by the ruled act itself (reset_second_factor)."""
        operator, browser, ref, key = self.ready_key_sign_in('s3-reset-ruled-act')
        reason = reason_file(self, 'Synthetic ruled act for a test: the operator reported the key lost.')
        reset = Call('ruledact', lambda: call_command('reset_second_factor', username=operator.get_username(),
                                                      reason_file=reason, by='Synthetic Person',
                                                      stdout=io.StringIO()))
        before = deadlocks_counted()
        with server_errors() as errors, holding_the_account(operator) as holder:
            reset.start()
            self.assertTrue(waits_on_a_lock(reset), 'the ruled act never queued on the account')
            key.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(key)), 'the key step neither finished nor waited')
            holder.release()
            self.finish(key, reset)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((reset.done, reset.error), (True, None))
        self.assertEqual(models.SecurityEvent.objects.filter(event='second_factor.reset', subject_id=operator.pk)
                         .count(), 1)
        self.assert_key_sign_in_refused(operator, browser, ref, key)

    def test_the_key_removed_on_the_console_while_the_key_check_holds_its_row(self):
        """The key sign-in's own proof: the key it verified is still active under the account's lock. The operator's
        console (signed in with a second key) removes the first key while another browser's key step with it is held
        inside its key check; a removal ends no session, so only that proof refuses the sign-in. The shipped code
        signed in with the removed key."""
        operator, browser, ref, key = self.ready_key_sign_in('s3-key-removed')
        first = models.SecondFactorCredential.objects.get(user=operator)
        own = Client(HTTP_HOST=ADMIN, raise_request_exception=False, REMOTE_ADDR=OWN)
        second = Authenticator()
        models.SecondFactorCredential.objects.create(user=operator, rp_id=settings.WEBAUTHN_RP_ID, label='Second key',
                                                     credential_id=second.id, public_key=second.public_key(),
                                                     transports=['usb'])
        self.assertEqual(sign_in(own, operator, second)['Location'], '/ops/')
        remove = Worker('remove', lambda: own.post('/ops/security', {'action': 'remove', 'key': str(first.pk)}))
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_writing('studio_secondfactorcredential', 'UPDATE', 'user_id',
                                                                 operator.pk, key) as release:
            key.start()
            self.assertTrue(wait_until(lambda: wait_of(key) == ('Lock', 'advisory')), 'the key step never held')
            remove.start()
            self.assertTrue(waits_on_a_lock(remove), 'the removal never waited on the key row')
            release()
            self.finish(key, remove)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((remove.status, remove.location, remove.error), (303, '/ops/security?done=removed', None))
        self.assertEqual(list(second_factor.active_keys(operator).values_list('label', flat=True)), ['Second key'])
        self.assertIsNone(key.error)
        self.assertEqual((key.status, key.location), (302, '/login/?reason=key'))  # its pending session still stands
        self.assertEqual(outcome_of(ref), models.LoginAttempt.SECOND_FACTOR_PENDING)
        self.assertNotEqual(console_status(browser), 200)
        self.assertEqual(console_status(own), 200)  # the console that removed it is untouched

    def test_a_sign_out_everywhere_served_while_the_key_check_holds_its_key_row(self):
        """locks-0's variant: the operator's own console posts sign out everywhere while another browser's key step is
        held inside its key check. The shipped code: sessions_ended 2, then that browser answered 302 /ops/ and its
        GET /ops/ 200."""
        operator, browser, ref, key = self.ready_key_sign_in('s3-everywhere-key-row')
        own = Client(HTTP_HOST=ADMIN, raise_request_exception=False, REMOTE_ADDR=OWN)
        # the console's own sign-in, with the same software key (its counter moves on)
        authenticator = Authenticator()
        models.SecondFactorCredential.objects.create(user=operator, rp_id=settings.WEBAUTHN_RP_ID, label='Second key',
                                                     credential_id=authenticator.id,
                                                     public_key=authenticator.public_key(), transports=['usb'])
        self.assertEqual(sign_in(own, operator, authenticator)['Location'], '/ops/')
        everywhere = Worker('everywhere', lambda: own.post('/logout/everywhere'))
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_writing('studio_secondfactorcredential', 'UPDATE', 'user_id',
                                                                 operator.pk, key) as release:
            key.start()
            self.assertTrue(wait_until(lambda: wait_of(key) == ('Lock', 'advisory')), 'the key step never held')
            everywhere.start()
            everywhere.join(60)
            self.assertEqual((everywhere.status, everywhere.location, everywhere.error), (302, '/login/', None))
            release()
            self.finish(key)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual(second_factor.active_keys(operator).count(), 2)  # a sign-out removes no key
        self.assert_key_sign_in_refused(operator, browser, ref, key)
        self.assertNotEqual(console_status(own), 200)
        self.assertEqual(live_keys(operator), set())


@override_settings(STORAGES=PLAIN_STATIC)
class KeyAddedAgainstTheResetTests(RaceCase):
    """locks-1: a key added on /ops/security while the server's reset runs."""

    def console(self, username):
        operator, key = enrolled_operator(username)
        browser = admin_client(raise_request_exception=False)
        self.assertEqual(sign_in(browser, operator, key)['Location'], '/ops/')
        spare = Authenticator()
        credential = json.dumps(spare.register(options_of(browser, '/ops/security', action='options')))
        add = Worker('add', lambda: browser.post('/ops/security', {'action': 'add', 'label': 'Spare key',
                                                                   'credential': credential}))
        return operator, browser, spare, add

    def assert_no_key_left(self, operator, spare):
        """The reset's result stands: no active key, and the spare key signs nobody in."""
        self.assertEqual(list(second_factor.active_keys(operator).values_list('label', flat=True)), [])
        again = admin_client(raise_request_exception=False)
        self.assertEqual(password_step(again, operator)['Location'], '/login/second-factor')
        self.assertEqual(again.post('/login/second-factor/options').status_code, 409)  # no key to sign with
        self.assertNotEqual(console_status(again), 200)
        self.assertFalse(models.SessionAccountLink.objects.filter(account_id=operator.pk,
                                                                  kind=session_store.SIGNED_IN_ADMIN).exists())

    def test_the_add_held_right_after_its_insert_while_the_reset_runs(self):
        """Schedule (a): the add held right after its INSERT of the new key. The shipped add took no lock: the reset
        waited on nothing, removed the old key, and the spare key committed after it and signed in to the console."""
        operator, browser, spare, add = self.console('s3-add-insert')
        reset = Call('reset', lambda: second_factor.reset(operator, 'Synthetic Person'))
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_writing('studio_secondfactorcredential', 'INSERT', 'user_id',
                                                                 operator.pk, add) as release:
            add.start()
            self.assertTrue(wait_until(lambda: wait_of(add) == ('Lock', 'advisory')), 'the add never held')
            reset.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(reset)), 'the reset neither finished nor waited')
            release()
            self.finish(add, reset)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertIsNone(add.error)
        self.assertEqual((reset.done, reset.error), (True, None))
        self.assert_no_key_left(operator, spare)
        # served first, the add's key was stored - and the reset removed it with the other
        self.assertEqual(models.SecondFactorCredential.objects.filter(user=operator, removed_at__isnull=False).count(),
                         2)

    def test_the_reset_served_whole_while_the_add_is_held_at_its_challenge(self):
        """Schedule (b): the add held at its challenge's single use (before the key is even checked); the reset runs to
        completion meanwhile; then the add is let go. The shipped add re-read nothing and stored its key after the
        reset."""
        operator, browser, spare, add = self.console('s3-add-challenge')
        challenge = models.OneTimeToken.objects.get(user=operator, purpose=second_factor.CHALLENGE_PURPOSE,
                                                    used_at__isnull=True)
        reset = Call('reset', lambda: second_factor.reset(operator, 'Synthetic Person'))
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_updating('studio_onetimetoken', challenge.pk, add) as release:
            add.start()
            self.assertTrue(wait_until(lambda: wait_of(add) == ('Lock', 'advisory')), 'the add never held')
            reset.start()
            reset.join(60)
            self.assertEqual((reset.done, reset.error), (True, None))
            release()
            self.finish(add)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertIsNone(add.error)
        self.assertEqual(add.status, 400)  # refused: its session was ended by the reset
        self.assertFalse(models.SecondFactorCredential.objects.filter(credential_id=spare.id).exists())  # never stored
        self.assert_no_key_left(operator, spare)


@override_settings(STORAGES=PLAIN_STATIC)
class MemberSignInAgainstAnAccessOffTests(RaceCase):
    """locks-4: an owner turns a member's access off (the member's only practice: C4 item 2, the person is signed out
    everywhere) while the member signs in at the cpt door with the right password."""

    def practice(self, label):
        practice = f.workspace(f'Synthetic practice s3 {label}')
        member = f.member(practice)
        owner = f.member(practice, role=models.Membership.OWNER)
        owners = Client(raise_request_exception=False, REMOTE_ADDR='10.40.0.1')
        self.assertEqual(owners.post('/login/', {'username': owner.username, 'password': PASSWORD}).status_code, 302)
        row = models.Membership.objects.get(user=member, workspace=practice)
        browser = Client(raise_request_exception=False, REMOTE_ADDR='10.40.0.2')
        browser.get('/login/')
        toggle = Worker('toggle', lambda: owners.post(f'/api/members/{member.pk}/access', json.dumps({'active': False}),
                                                      content_type='application/json', **API))
        signin = Worker('signin', lambda: browser.post('/login/', {'username': member.username, 'password': PASSWORD}))
        return practice, member, owners, row, browser, toggle, signin

    def assert_signed_out_for_good(self, practice, member, owners, browser):
        """No session of the member lives, the browser is signed out, and access turned on again brings nothing back."""
        self.assertEqual(live_keys(member), set())
        self.assertNotEqual(browser.session.get(SESSION_KEY), str(member.pk))
        self.assertEqual(browser.get('/api/encounters', **API).status_code, 401)
        on = owners.post(f'/api/members/{member.pk}/access', json.dumps({'active': True}),
                         content_type='application/json', **API)
        self.assertEqual(on.status_code, 200)
        self.assertEqual(browser.get('/api/encounters', **API).status_code, 401)

    def test_the_access_off_held_after_its_membership_update_and_the_sign_in_sent_meanwhile(self):
        """The finding's schedule (A): the access off held right after its UPDATE of the membership; the sign-in sent
        meanwhile. The shipped sign-in read the membership active, waited on the account in login(), and stayed signed
        in after the access off ended the member's sessions (sessions_ended 0); its session worked again once access
        was turned back on."""
        practice, member, owners, row, browser, toggle, signin = self.practice('access off first')
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_updating('studio_membership', row.pk, toggle) as release:
            toggle.start()
            self.assertTrue(wait_until(lambda: wait_of(toggle) == ('Lock', 'advisory')), 'the access off never held')
            signin.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(signin)), 'the sign-in neither finished nor waited')
            release()
            self.finish(toggle, signin)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((toggle.status, toggle.error), (200, None))
        self.assertEqual((signin.status, signin.error), (400, None))  # refused: the access off was served first
        event = models.AuditEvent.objects.get(workspace=practice, event='member.access_off')
        self.assertEqual(event.data['sessions_ended'], 0)  # nothing to end: the sign-in made no session
        attempt = models.LoginAttempt.objects.filter(username=member.username).order_by('-pk').first()
        self.assertEqual((attempt.outcome, attempt.succeeded), (models.LoginAttempt.NO_ACCESS, False))
        self.assert_signed_out_for_good(practice, member, owners, browser)

    def test_the_sign_in_held_inside_its_session_write_and_the_access_off_sent_meanwhile(self):
        """The verifier's schedule C: the sign-in held right after its first django_session INSERT (login(), past its
        checks); the access off sent meanwhile. The shipped access off ran to completion while the sign-in was held
        (sessions_ended 0), and the sign-in stayed signed in. Now the sign-in holds the account there: the access off
        waits for it, and then ends its session."""
        practice, member, owners, row, browser, toggle, signin = self.practice('sign-in first')
        before = deadlocks_counted()
        with server_errors() as errors, held_right_after_inserting_a_session(signin) as release:
            signin.start()
            self.assertTrue(wait_until(lambda: wait_of(signin) == ('Lock', 'advisory')), 'the sign-in never held')
            toggle.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(toggle)), 'the access off neither ended nor waited')
            release()
            self.finish(toggle, signin)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((toggle.status, toggle.error), (200, None))
        self.assertIsNone(signin.error)
        # signed in first (302) - or its answer met its session ended by the access off served after it (400,
        # SessionInterrupted): either way the access off ended that sign-in
        self.assertIn((signin.status, signin.location), {(302, '/'), (400, None)})
        event = models.AuditEvent.objects.get(workspace=practice, event='member.access_off')
        self.assertEqual(event.data['sessions_ended'], 1)
        self.assert_signed_out_for_good(practice, member, owners, browser)


@override_settings(STORAGES=PLAIN_STATIC)
class TheClassOtherActsTests(RaceCase):
    """The class's other acts: each opens a session or changes the account's credentials, and each met a sign-out
    everywhere served after its request loaded its session. The schedule is the verifiers' queue: a third connection
    holds the account; the sign-out everywhere queues on it; the act queues behind; the holder lets go."""

    def queued_behind_a_sign_out_everywhere(self, user, everywhere, act):
        before = deadlocks_counted()
        with server_errors() as errors, holding_the_account(user) as holder:
            everywhere.start()
            self.assertTrue(waits_on_a_lock(everywhere), 'the sign-out everywhere never queued on the account')
            act.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(act)), 'the act neither finished nor waited')
            holder.release()
            self.finish(everywhere, act)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((everywhere.status, everywhere.location, everywhere.error), (302, '/login/', None))
        self.assertIsNone(act.error)

    def operator_with_a_console(self, username):
        operator, authenticator = enrolled_operator(username)
        own = admin_client(raise_request_exception=False, REMOTE_ADDR=OWN)
        self.assertEqual(sign_in(own, operator, authenticator)['Location'], '/ops/')
        return operator, authenticator, own

    def test_a_recovery_code_sign_in_behind_a_sign_out_everywhere(self):
        """The shipped recovery sign-in took the account and then used its code: queued behind the sign-out everywhere,
        it found its code still unused and signed in after the end of the account's sessions (GET /ops/ 200)."""
        operator, _authenticator, own = self.operator_with_a_console('s3-recovery-everywhere')
        codes = second_factor.new_recovery_codes(operator)
        waiting = admin_client(raise_request_exception=False)
        self.assertEqual(password_step(waiting, operator)['Location'], '/login/second-factor')
        ref = pending_ref(waiting)
        failures = second_factor.attempts_left(operator)
        recover = Worker('recover', lambda: waiting.post('/login/recovery', {'code': codes[0]}))
        everywhere = Worker('everywhere', lambda: own.post('/logout/everywhere'))
        self.queued_behind_a_sign_out_everywhere(operator, everywhere, recover)
        self.assertIn((recover.status, recover.location), {(302, '/login/?reason=key'), (400, None)})
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT)  # none used
        self.assertNotIn('second_factor.recovery_used', events_of(operator))
        self.assertEqual(second_factor.attempts_left(operator), failures)  # no failure counted: the code was right
        self.assertEqual(outcome_of(ref), models.LoginAttempt.SECOND_FACTOR_PENDING)
        self.assertNotEqual(console_status(waiting), 200)
        self.assertEqual(live_keys(operator), set())

    def test_a_recovery_code_step_up_behind_a_sign_out_everywhere(self):
        """The shipped step-up used its code and then saved its session inside the transaction: the session's row was
        gone, so the save raised and the answer was a server error (500)."""
        operator, authenticator, own = self.operator_with_a_console('s3-step-up-everywhere')
        codes = second_factor.new_recovery_codes(operator)
        other = admin_client(raise_request_exception=False)
        self.assertEqual(sign_in(other, operator, authenticator)['Location'], '/ops/')
        step_up = Worker('stepup', lambda: other.post('/login/recovery', {'code': codes[0], 'next': '/ops/people'}))
        everywhere = Worker('everywhere', lambda: own.post('/logout/everywhere'))
        self.queued_behind_a_sign_out_everywhere(operator, everywhere, step_up)
        self.assertIn((step_up.status, step_up.location), {(302, '/login/?reason=key'), (400, None)})
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT)
        self.assertNotEqual(console_status(other), 200)

    def test_setups_key_step_behind_a_sign_out_everywhere(self):
        """An operator with a console session and a setup under way in another browser (a setup code issued on the
        server; setup's first step ended the account's other sessions, and the console signed in again since). The
        shipped key step's claim outlived the sign-out everywhere, which revokes no setup claim: it stored its key and
        signed in after the end (GET /ops/ 200)."""
        operator, authenticator = enrolled_operator('s3-setup-everywhere')
        _token, code = second_factor.issue_setup_code(operator, 'Synthetic Person')
        setup = admin_client(raise_request_exception=False)
        started = setup.post('/login/enrol', {'step': 'code', 'code': code, 'new_password': NEW_PASSWORD,
                                              'new_password_again': NEW_PASSWORD})
        self.assertEqual((started.status_code, started['Location']), (303, '/login/enrol'))
        own = admin_client(raise_request_exception=False, REMOTE_ADDR=OWN)
        self.assertEqual(sign_in(own, operator, authenticator, password=NEW_PASSWORD)['Location'], '/ops/')
        first = Authenticator()
        credential = json.dumps(first.register(options_of(setup, '/login/enrol/options')))
        finish = Worker('finish', lambda: setup.post('/login/enrol', {'step': 'key', 'label': 'Synthetic key',
                                                                      'credential': credential}))
        everywhere = Worker('everywhere', lambda: own.post('/logout/everywhere'))
        self.queued_behind_a_sign_out_everywhere(operator, everywhere, finish)
        self.assertEqual(finish.status, 400)  # refused (the setup expired) - or its session gone (SessionInterrupted)
        self.assertFalse(models.SecondFactorCredential.objects.filter(credential_id=first.id).exists())
        self.assertNotIn('second_factor.enrolled', events_of(operator))
        self.assertEqual(models.OneTimeToken.objects.filter(user=operator, purpose=second_factor.SETUP_CLAIM_PURPOSE,
                                                            used_at__isnull=False).count(), 0)  # the claim unused
        self.assertNotEqual(console_status(setup), 200)
        self.assertEqual(live_keys(operator), set())

    def test_a_password_change_behind_a_sign_out_everywhere(self):
        """B4: the member's password change on /account/ in one browser, a sign-out everywhere in another. The shipped
        change set the password after the end of the account's sessions, and its update_session_auth_hash wrote its
        ended session again under a new key: that browser stayed signed in."""
        member = f.member(f.workspace('Synthetic practice s3 change'))
        changer = Client(raise_request_exception=False)
        other = Client(raise_request_exception=False)
        for browser in (changer, other):
            self.assertEqual(browser.post('/login/', {'username': member.username, 'password': PASSWORD}).status_code,
                             302)
        change = Worker('change', lambda: changer.post('/account/', {'current_password': PASSWORD,
                                                                     'new_password': NEW_PASSWORD,
                                                                     'new_password_again': NEW_PASSWORD}))
        everywhere = Worker('everywhere', lambda: other.post('/logout/everywhere'))
        self.queued_behind_a_sign_out_everywhere(member, everywhere, change)
        self.assertEqual(change.status, 400)  # refused: its session had ended
        member.refresh_from_db()
        self.assertTrue(member.check_password(PASSWORD))  # unchanged
        self.assertNotIn('password.changed', events_of(member))
        self.assertEqual(live_keys(member), set())
        self.assertNotEqual(changer.get('/account/').status_code, 200)

    def test_a_key_removed_by_a_session_a_sign_out_everywhere_ends(self):
        """A key removal from a console session while that session's sign-out everywhere (from the operator's own other
        browser) is served. The shipped removal took no account lock: held on the key rows, it removed a key after the
        sign-out everywhere had ended the session it came from. Now the removal takes the account first: served
        before the sign-out everywhere, or refused."""
        operator, authenticator, own = self.operator_with_a_console('s3-remove-everywhere')
        spare = Authenticator()
        models.SecondFactorCredential.objects.create(user=operator, rp_id=settings.WEBAUTHN_RP_ID, label='Spare key',
                                                     credential_id=spare.id, public_key=spare.public_key(),
                                                     transports=['usb'])
        other = admin_client(raise_request_exception=False)
        self.assertEqual(sign_in(other, operator, authenticator)['Location'], '/ops/')
        spare_row = models.SecondFactorCredential.objects.get(credential_id=spare.id)
        remove = Worker('remove', lambda: other.post('/ops/security', {'action': 'remove', 'key': str(spare_row.pk)}))
        everywhere = Worker('everywhere', lambda: own.post('/logout/everywhere'))
        keys = Holder('keys', lambda: list(models.SecondFactorCredential.objects.select_for_update()
                                            .filter(user=operator)))
        before = deadlocks_counted()
        with server_errors() as errors, keys:
            remove.start()
            self.assertTrue(waits_on_a_lock(remove), 'the removal never waited on the key rows')
            everywhere.start()
            self.assertTrue(wait_until(lambda: finished_or_waiting(everywhere)), 'the sign-out never ended or waited')
            keys.release()
            self.finish(remove, everywhere)
        assert_no_deadlock(self, before)
        self.assertEqual(errors, [])
        self.assertEqual((everywhere.status, everywhere.error), (302, None))
        self.assertIsNone(remove.error)
        events = [event for event in events_of(operator)
                  if event in ('second_factor.key_removed', 'sessions.ended_everywhere')]
        self.assertIn(events, (['second_factor.key_removed', 'sessions.ended_everywhere'],
                               ['sessions.ended_everywhere']))  # removed by a live session, or refused
        if events == ['sessions.ended_everywhere']:
            self.assertTrue(second_factor.active_keys(operator).filter(pk=spare_row.pk).exists())
        self.assertEqual(live_keys(operator), set())


def locked_elsewhere(user):
    """Whether another connection finds ``user``'s account row locked (SELECT ... FOR NO KEY UPDATE NOWAIT)."""
    found = []

    def probe():
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute('SELECT 1 FROM studio_user WHERE id = %s FOR NO KEY UPDATE NOWAIT', [str(user.pk)])
            found.append(False)
        except Exception:  # noqa: BLE001 - LockNotAvailable
            found.append(True)
    probing = Call('probe', probe)
    probing.start()
    probing.join(30)
    return found == [True]


@override_settings(STORAGES=PLAIN_STATIC)
class ActStillStandsTests(TransactionTestCase):
    """The helper itself: it takes the account's lock, proves the request's own session when the session names the
    account, and refuses to run outside a transaction."""

    def test_outside_a_transaction_it_raises(self):
        member = f.member(f.workspace('Synthetic practice s3 helper'))
        request = type('Request', (), {'session': session_store.SessionStore()})()
        with self.assertRaises(RuntimeError):
            sessions.act_still_stands(request, member)

    def test_it_proves_a_session_that_names_the_account_and_only_such_a_session(self):
        from tests.test_r1_repair_s import pending_data, signed_in_data, store_session
        member = f.member(f.workspace('Synthetic practice s3 helper rows'))
        other = f.member(f.workspace('Synthetic practice s3 helper other'))
        named = session_store.SessionStore(store_session(signed_in_data(member)))
        named.load()
        waiting = session_store.SessionStore(store_session(pending_data(member)))
        waiting.load()
        elsewhere = session_store.SessionStore(store_session(signed_in_data(other)))
        elsewhere.load()
        anonymous = session_store.SessionStore()
        anonymous['synthetic'] = 1
        request = type('Request', (), {})()
        for store, expect in ((named, True), (waiting, True), (elsewhere, True), (anonymous, True)):
            request.session = store
            with self.subTest(session=store.session_key), transaction.atomic():
                self.assertEqual(sessions.act_still_stands(request, member), expect)
        sessions.end_sessions(member)  # deletes the rows of the two that name the member
        for store, expect in ((named, False), (waiting, False), (elsewhere, True), (anonymous, True)):
            request.session = store
            with self.subTest(after='end', session=store.session_key), transaction.atomic():
                self.assertEqual(sessions.act_still_stands(request, member), expect)
                self.assertEqual(sessions.act_still_stands(request, member, models.User.objects.none()), False)
        request.session = anonymous
        with transaction.atomic():
            self.assertTrue(sessions.act_still_stands(request, member, models.User.objects.filter(pk=member.pk)))
            self.assertTrue(locked_elsewhere(member))  # the account's row is held until this transaction ends
        self.assertFalse(locked_elsewhere(member))

    def test_a_session_that_names_the_account_with_no_row_does_not_stand(self):
        member = f.member(f.workspace('Synthetic practice s3 helper no row'))
        unsaved = session_store.SessionStore()
        unsaved[SESSION_KEY] = str(member.pk)
        request = type('Request', (), {'session': unsaved})()
        with transaction.atomic():
            self.assertFalse(sessions.act_still_stands(request, member))
