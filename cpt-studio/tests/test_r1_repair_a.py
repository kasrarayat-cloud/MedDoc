"""Release 1, repair round 1, builder A: the records, the second factor and the console (refutation of the integrated
release, findings failclosed-0 to -5 and -7, bypass-0, phileak-3, auth-0, auth-1 and auth-2). Synthetic data only.

A1  A security act whose SecurityEvent cannot be written does not happen. PostgreSQL itself refuses the record - a
    BEFORE INSERT trigger that raises, or a CHECK (false) NOT VALID constraint - and nothing in the code under test is
    patched; the tests are TransactionTestCases, so every write autocommits as it does in production (no
    ATOMIC_REQUESTS). Each act is shown not to have happened, then to happen with its record once the record can be
    written (the non-vacuity control).
A2  The console's activity list shows no CPT code and no line of any document: the document's own page keeps them
    closed until a reason is given (C2), and the list spans every practice. What the list shows otherwise stays.
A3  Second-factor failures sent with the account's own known-device cookie are counted apart from every other request's,
    so someone holding the operator's password alone cannot use up the attempts of the operator's own browser: its key,
    its recovery codes and its step-up keep working. Each pending sign-in keeps its own limit.
A4  The signed-in pages of the second factor - the recovery codes setup ends on, and the step-up's key and recovery code
    pages - arm the console's idle timer (ops_session.js) as every console page does: the sign-out form, and the
    session's seconds on the body.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase, override_settings

from studio import audit, console, models, rate, second_factor, throttle
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import (ADMIN, CPT, MOMENT, PASSWORD, Authenticator, Clock, add_key, enrolled_operator,
                                      key_step, options_of, password_step)

SECURITY_EVENT_TABLE = models.SecurityEvent._meta.db_table
AUDIT_EVENT_TABLE = models.AuditEvent._meta.db_table
REFUSAL_PREFIX = 'r1repa_'
A1_NEW_PASSWORD = 'a new password only the member knows'
A1_REASON = 'Synthetic ruled act for a test: the act needs its record.'


# --- the database's refusal -------------------------------------------------------------------------------------------

@contextmanager
def refused_rows(table, where=None):
    """While the block runs, PostgreSQL refuses every new row of ``table`` - only the rows matching the SQL condition
    ``where`` over NEW, when it is given - with a BEFORE INSERT trigger that raises. Dropped afterwards, always."""
    name = f'{REFUSAL_PREFIX}refuse_{table}'
    condition = f' WHEN ({where})' if where else ''
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                       f"BEGIN RAISE EXCEPTION 'r1repa: % refused', TG_TABLE_NAME; END $$")
        cursor.execute(f'CREATE TRIGGER {name} BEFORE INSERT ON {table} FOR EACH ROW{condition} '
                       f'EXECUTE FUNCTION {name}()')
    try:
        yield
    finally:
        _settled_connection()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER IF EXISTS {name} ON {table}')
            cursor.execute(f'DROP FUNCTION IF EXISTS {name}()')


@contextmanager
def refused_by_check(table):
    """While the block runs, every new row of ``table`` breaks a CHECK (false) constraint (NOT VALID: the rows already
    there are not checked). Dropped afterwards, always."""
    name = f'{REFUSAL_PREFIX}check_{table}'
    with connection.cursor() as cursor:
        cursor.execute(f'ALTER TABLE {table} ADD CONSTRAINT {name} CHECK (false) NOT VALID')
    try:
        yield
    finally:
        _settled_connection()
        with connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}')


def _settled_connection():
    if connection.connection is not None and connection.needs_rollback:
        connection.rollback()


def refusals_left():
    """Every trigger, constraint or function of these tests still in the database (empty after every test)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'r1repa_%%' "
                       "UNION ALL SELECT conname FROM pg_constraint WHERE conname LIKE 'r1repa_%%' "
                       "UNION ALL SELECT proname FROM pg_proc WHERE proname LIKE 'r1repa_%%'")
        return sorted(row[0] for row in cursor.fetchall())


def security_events(name):
    return models.SecurityEvent.objects.filter(event=name).count()


def a1_reason_file(test):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    path = Path(folder.name) / 'reason.txt'
    path.write_text(A1_REASON, encoding='utf-8')
    return str(path)


def member_signed_in(user):
    """A browser signed in as ``user`` through the doctors' door, whose server errors come back as answers."""
    client = Client(HTTP_HOST=CPT, raise_request_exception=False)
    answer = client.post('/login/', {'username': user.get_username(), 'password': PASSWORD})
    assert answer.status_code == 302, answer.content[:300]
    return client


def a1_account_change(client, new=A1_NEW_PASSWORD):
    return client.post('/account/', {'current_password': PASSWORD, 'new_password': new, 'new_password_again': new})


def live_sessions_of(user):
    return sum(1 for row in Session.objects.all() if row.get_decoded().get('_auth_user_id') == str(user.pk))


def setup_operator(username):
    """A human operator with a grant, no usable password and a live setup code: (the account, the token, the code)."""
    operator = f.user(username)
    ops.grant(operator)
    operator.set_unusable_password()
    operator.save()
    token, code = second_factor.issue_setup_code(operator, 'Synthetic Person')
    return operator, token, code


def setup_first_step(client, code, password=A1_NEW_PASSWORD):
    return client.post('/login/enrol', {'step': 'code', 'code': code, 'new_password': password,
                                        'new_password_again': password})


def setup_key_step(client, authenticator, label='Blue key'):
    options = options_of(client, '/login/enrol/options')
    return client.post('/login/enrol', {'step': 'key', 'label': label,
                                        'credential': json.dumps(authenticator.register(options))})


def armed_name_delay(username, failures=8):
    key = throttle.user_key(username)
    for _ in range(failures):
        rate.hit(throttle.FAIL_USER, key, window_seconds=throttle.MINUTE)
    return key


@override_settings(STORAGES=PLAIN_STATIC)
class ActWithItsRecordTests(TransactionTestCase):
    """A1 (failclosed-0 to -5 and -7): the act and its record are one transaction."""

    def tearDown(self):
        self.assertEqual(refusals_left(), [])
        super().tearDown()

    def refused_answer(self, refusal, send):
        """``send()``'s answer while ``refusal`` holds: a server error, logged by Django as one."""
        with self.assertLogs('django.request', level='ERROR'), refusal:
            answer = send()
        self.assertEqual(answer.status_code, 500)
        return answer

    # --- B4: the account page (failclosed-0) --------------------------------------------------------------------------

    def test_a_password_change_whose_record_is_refused_changes_nothing(self):
        ws = f.workspace('Synthetic practice A1')
        member = f.member(ws)
        me, other = member_signed_in(member), member_signed_in(member)
        refusals = {
            'the security event, by a trigger': lambda: refused_rows(SECURITY_EVENT_TABLE),
            'the security event, by a constraint': lambda: refused_by_check(SECURITY_EVENT_TABLE),
            'the practice\'s audit row alone': lambda: refused_rows(AUDIT_EVENT_TABLE,
                                                                     "NEW.event = 'member.password_changed'"),
        }
        for label, refusal in refusals.items():
            with self.subTest(label):
                self.refused_answer(refusal(), lambda: a1_account_change(me))
                member.refresh_from_db()
                self.assertTrue(member.check_password(PASSWORD), 'the old password still signs in')
                self.assertFalse(member.check_password(A1_NEW_PASSWORD), 'the new password was not set')
                self.assertIsNone(member.password_changed_at)
                self.assertEqual(live_sessions_of(member), 2, 'no session was ended')
                self.assertEqual((me.get('/account/').status_code, other.get('/account/').status_code), (200, 200))
                self.assertEqual(security_events('password.changed'), 0)
                self.assertFalse(models.AuditEvent.objects.filter(event='member.password_changed').exists())
        # the control: with the records written, the change is made, recorded, and ends the other session
        done = a1_account_change(me)
        self.assertEqual((done.status_code, done['Location']), (302, '/account/?done=changed'))
        member.refresh_from_db()
        self.assertTrue(member.check_password(A1_NEW_PASSWORD))
        self.assertEqual(security_events('password.changed'), 1)
        self.assertEqual(models.AuditEvent.objects.filter(event='member.password_changed').count(), 1)
        self.assertEqual(live_sessions_of(member), 1)

    def test_an_operator_s_password_change_on_the_console_needs_its_record_too(self):
        operator = f.user('a1-operator-account')
        client = ops.admin_client(operator, raise_request_exception=False)  # a fresh second factor: no step-up needed
        self.refused_answer(refused_rows(SECURITY_EVENT_TABLE), lambda: a1_account_change(client))
        operator.refresh_from_db()
        self.assertTrue(operator.check_password(PASSWORD))
        self.assertIsNone(operator.password_changed_at)
        self.assertEqual(security_events('password.changed'), 0)
        self.assertEqual(a1_account_change(client).status_code, 302)
        self.assertEqual(security_events('password.changed'), 1)

    # --- B1 step 8: the ruled act clear_signin_failures (failclosed-1) ------------------------------------------------

    def test_clearing_a_delay_or_an_address_whose_record_is_refused_clears_nothing(self):
        user = f.user('a1-delayed-doctor')
        name_key = armed_name_delay(user.username)
        address = '203.0.113.77'
        for _ in range(8):
            rate.hit(throttle.FAIL_CLIENT, address, window_seconds=throttle.MINUTE)
        before = sorted(models.RateWindow.objects.values_list('scope', 'key', 'count'))
        for which in ({'username': user.username}, {'address': address}):
            with self.subTest(**which):
                raised = None
                with refused_rows(SECURITY_EVENT_TABLE):
                    try:
                        call_command('clear_signin_failures', reason_file=a1_reason_file(self), by='Jane Synthetic',
                                     stdout=io.StringIO(), **which)
                    except Exception as exc:  # noqa: BLE001 - judged below, after what the act left behind
                        raised = exc
                self.assertEqual(sorted(models.RateWindow.objects.values_list('scope', 'key', 'count')), before,
                                 'nothing was cleared')
                self.assertEqual(security_events('signin.delay_cleared') + security_events('signin.address_cleared'), 0)
                # the act failed, in a fixed sentence and the error's type: never the database's text, which can quote
                # the row
                self.assertIsInstance(raised, CommandError)
                self.assertRegex(str(raised), r'^The database refused the act or its record \(\w+\); '
                                              r'nothing was cleared and nothing was recorded\.$')
        # the control: with the record written, each act clears and is recorded once
        call_command('clear_signin_failures', username=user.username, reason_file=a1_reason_file(self),
                     by='Jane Synthetic', stdout=io.StringIO())
        self.assertFalse(models.RateWindow.objects.filter(key=name_key).exists())
        call_command('clear_signin_failures', address=address, reason_file=a1_reason_file(self), by='Jane Synthetic',
                     stdout=io.StringIO())
        self.assertFalse(models.RateWindow.objects.filter(key=address).exists())
        self.assertEqual((security_events('signin.delay_cleared'), security_events('signin.address_cleared')), (1, 1))

    # --- B2 item 6: the keys page (failclosed-2 and -3) ---------------------------------------------------------------

    def test_a_key_added_whose_record_is_refused_is_not_stored_and_its_challenge_is_spent(self):
        operator = f.user('a1-operator-add')
        add_key(operator, Authenticator(), 'Key A')
        client = ops.admin_client(operator, raise_request_exception=False)
        spare = Authenticator()
        answer = json.dumps(spare.register(options_of(client, '/ops/security', action='options')))
        self.refused_answer(refused_rows(SECURITY_EVENT_TABLE),
                            lambda: client.post('/ops/security', {'action': 'add', 'label': 'Spare key',
                                                                  'credential': answer}))
        self.assertFalse(models.SecondFactorCredential.objects.filter(credential_id=spare.id).exists())
        self.assertEqual(second_factor.active_keys(operator).count(), 1)
        self.assertEqual(security_events('second_factor.key_added'), 0)
        # the challenge went with the refused answer: the same answer again stores nothing
        replay = client.post('/ops/security', {'action': 'add', 'label': 'Spare key', 'credential': answer})
        self.assertEqual(replay.status_code, 400)
        self.assertIn(second_factor.NO_CHALLENGE, replay.content.decode())
        self.assertFalse(models.SecondFactorCredential.objects.filter(credential_id=spare.id).exists())
        # the control: a new challenge, the record written - the key is stored, with its record
        added = client.post('/ops/security', {'action': 'add', 'label': 'Spare key', 'credential': json.dumps(
            spare.register(options_of(client, '/ops/security', action='options')))})
        self.assertEqual((added.status_code, added['Location']), (303, '/ops/security?done=added'))
        self.assertEqual(second_factor.active_keys(operator).count(), 2)
        self.assertEqual(security_events('second_factor.key_added'), 1)

    def test_a_key_removed_whose_record_is_refused_stays(self):
        operator = f.user('a1-operator-remove')
        first = add_key(operator, Authenticator(), 'Key A')
        add_key(operator, Authenticator(), 'Key B')
        client = ops.admin_client(operator, raise_request_exception=False)
        key = second_factor.active_keys(operator).get(credential_id=first.id)
        self.refused_answer(refused_by_check(SECURITY_EVENT_TABLE),
                            lambda: client.post('/ops/security', {'action': 'remove', 'key': str(key.pk)}))
        key.refresh_from_db()
        self.assertEqual((key.removed_at, key.removed_reason), (None, ''))
        self.assertEqual(second_factor.active_keys(operator).count(), 2)
        self.assertEqual(security_events('second_factor.key_removed'), 0)
        removed = client.post('/ops/security', {'action': 'remove', 'key': str(key.pk)})
        self.assertEqual((removed.status_code, removed['Location']), (303, '/ops/security?done=removed'))
        self.assertEqual(second_factor.active_keys(operator).count(), 1)
        self.assertEqual(security_events('second_factor.key_removed'), 1)

    # --- B2 item 3: setup with a code (failclosed-4 and -5) -----------------------------------------------------------

    def test_setup_s_first_step_whose_record_is_refused_uses_no_code_and_sets_no_password(self):
        operator, token, code = setup_operator('a1-operator-setup-code')
        elsewhere = Client(HTTP_HOST=CPT)
        elsewhere.force_login(operator)  # a session of the account that a finished first step ends
        client = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        self.refused_answer(refused_rows(SECURITY_EVENT_TABLE), lambda: setup_first_step(client, code))
        operator.refresh_from_db()
        token.refresh_from_db()
        self.assertFalse(operator.has_usable_password(), 'no password was set')
        self.assertIsNone(token.used_at, 'the setup code was not used up')
        self.assertFalse(models.OneTimeToken.objects.filter(purpose=second_factor.SETUP_CLAIM_PURPOSE).exists())
        self.assertEqual(live_sessions_of(operator), 1, 'no session was ended')
        self.assertEqual(security_events('password.changed'), 0)
        self.assertEqual(client.post('/login/enrol/options').status_code, 403)  # this browser holds no setup
        # the control: the same code, the record written - the step is done once, recorded
        started = setup_first_step(client, code)
        self.assertEqual((started.status_code, started['Location']), (303, '/login/enrol'))
        operator.refresh_from_db()
        self.assertTrue(operator.check_password(A1_NEW_PASSWORD))
        self.assertEqual(security_events('password.changed'), 1)
        self.assertEqual(live_sessions_of(operator), 0)

    def test_setup_s_key_step_whose_record_is_refused_stores_no_key_and_makes_no_code(self):
        operator, _token, code = setup_operator('a1-operator-setup-key')
        client = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        self.assertEqual(setup_first_step(client, code).status_code, 303)
        key = Authenticator()
        answer = self.refused_answer(refused_rows(SECURITY_EVENT_TABLE, "NEW.event = 'second_factor.enrolled'"),
                                     lambda: setup_key_step(client, key))
        self.assertNotIn('<li>', answer.content.decode())
        self.assertFalse(models.SecondFactorCredential.objects.filter(user=operator).exists())
        self.assertFalse(models.SecondFactorRecoveryCode.objects.filter(user=operator).exists())
        claim = models.OneTimeToken.objects.get(purpose=second_factor.SETUP_CLAIM_PURPOSE)
        self.assertIsNone(claim.used_at, 'the setup can still be finished')
        self.assertIsNone(client.session.get('_auth_user_id'), 'not signed in')
        self.assertFalse(models.LoginAttempt.objects.exists())
        self.assertEqual(security_events('second_factor.enrolled'), 0)
        # the control: the setup is finished with a new challenge, signed in, its ten codes shown once
        done = setup_key_step(client, key)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.content.decode().count('<li>'), settings.RECOVERY_CODE_COUNT)
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT)
        self.assertEqual(client.session.get('_auth_user_id'), str(operator.pk))
        self.assertEqual(security_events('second_factor.enrolled'), 1)

    # --- B2 item 2.7: a recovery code (failclosed-7) ------------------------------------------------------------------

    def test_a_recovery_code_whose_record_is_refused_is_not_used_up(self):
        operator = f.user('a1-operator-recovery')
        ops.grant(operator)
        add_key(operator)
        codes = second_factor.new_recovery_codes(operator)
        client = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
        self.assertEqual(password_step(client, operator).status_code, 302)
        self.refused_answer(refused_rows(SECURITY_EVENT_TABLE),
                            lambda: client.post('/login/recovery', {'code': codes[0]}))
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT)
        self.assertIsNone(client.session.get('_auth_user_id'))
        self.assertEqual(models.LoginAttempt.objects.get().outcome, models.LoginAttempt.SECOND_FACTOR_PENDING)
        self.assertEqual(security_events('second_factor.recovery_used'), 0)
        # the control: the same code, the record written, signs in once
        used = client.post('/login/recovery', {'code': codes[0]})
        self.assertEqual((used.status_code, used['Location']), (302, '/ops/'))
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT - 1)
        self.assertEqual(models.LoginAttempt.objects.get().outcome, models.LoginAttempt.SIGNED_IN)
        self.assertEqual(security_events('second_factor.recovery_used'), 1)

    def test_a_recovery_code_at_the_step_up_whose_record_is_refused_is_not_used_up(self):
        operator = f.user('a1-operator-step-up')
        add_key(operator)
        codes = second_factor.new_recovery_codes(operator)
        client = ops.admin_client(operator, raise_request_exception=False)
        self.refused_answer(refused_rows(SECURITY_EVENT_TABLE),
                            lambda: client.post('/login/recovery', {'code': codes[0], 'next': '/ops/security'}))
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT)
        self.assertEqual(security_events('second_factor.recovery_used'), 0)
        used = client.post('/login/recovery', {'code': codes[0], 'next': '/ops/security'})
        self.assertEqual((used.status_code, used['Location']), (302, '/ops/security'))
        self.assertEqual(second_factor.recovery_codes_left(operator), settings.RECOVERY_CODE_COUNT - 1)
        self.assertEqual(security_events('second_factor.recovery_used'), 1)


# --- A2: the activity list (bypass-0, phileak-3) ----------------------------------------------------------------------

A2_CODES = ('45385', '45380')


@override_settings(STORAGES=PLAIN_STATIC)
class ActivityListWithoutContentTests(TestCase):
    """A2: a decided code and its line are a document's content (its page shows them only with a content grant), so the
    activity list - every practice's events, read with no reason - shows neither, for this release's decisions and for
    an earlier version's answered details alike."""

    def setUp(self):
        self.ws = f.workspace('Synthetic practice A2')
        self.member = f.member(self.ws)
        self.encounter = f.encounter(self.ws, self.member, title='ZZ-TITLE-A2')
        self.decided = audit.record(self.ws, 'decision.recorded', encounter=self.encounter, actor=self.member,
                                    decision=str(uuid.uuid4()), round=str(uuid.uuid4()), number=1, action='approve',
                                    line='L7', code=A2_CODES[0])
        # an earlier version's answered detail, as it was written then: its code and the member's answer
        self.answered = audit.record(self.ws, 'detail.answered', encounter=self.encounter, actor=self.member,
                                     fact='ZZ-FACT-A2', family='synthetic', code=A2_CODES[1], value='ZZ-ANSWER-A2',
                                     answer=str(uuid.uuid4()))

    def test_the_list_shows_no_code_and_no_line_and_keeps_the_rest(self):
        client = ops.admin_client(f.user('a2-operator'))
        for address in ('/ops/activity', '/ops/activity?kind=decisions', f'/ops/activity?workspace={self.ws.pk}',
                        f'/ops/activity?kind=decisions&workspace={self.ws.pk}'):
            with self.subTest(address):
                answer = client.get(address)
                self.assertEqual(answer.status_code, 200)
                body = answer.content.decode()
                self.assertIn(str(self.encounter.pk)[:8], body, 'the document is listed by its reference')
                self.assertIn('number 1', body, 'what the row shows otherwise stays')
                for marker in A2_CODES + ('line L7', 'code ' + A2_CODES[0], 'ZZ-ANSWER-A2', 'ZZ-TITLE-A2'):
                    self.assertFalse(marker in body, f'{marker!r} is on the list')
        self.assertFalse(models.AccessRecord.objects.filter(view='ops.content_open').exists(), 'no grant was asked')

    def test_each_event_keeps_its_other_details(self):
        self.assertEqual(console.describe(self.decided)['details'], 'number 1')
        self.assertEqual(console.describe(self.answered)['details'], '')
        changed = audit.record(self.ws, 'operator.role_changed', actor=self.member, user=str(self.member.pk),
                               username='synthetic-person', requested_by='Ticket 4417',
                               **{'from': 'reviewer', 'to': 'owner'})
        self.assertEqual(console.describe(changed)['details'],
                         'username synthetic-person · from reviewer · to owner · requested_by Ticket 4417')
        self.assertNotIn('line', console.DETAIL_KEYS)
        self.assertNotIn('code', console.DETAIL_KEYS)


# --- A3: the operator's own device keeps its second factor (auth-0) ---------------------------------------------------

A3_OWN, A3_THIEF = '203.0.113.10', '198.51.100.7'


def a3_browser(address, device=None):
    """A browser at the admin host from ``address``, holding the known-device cookie ``device`` when given."""
    client = Client(HTTP_HOST=ADMIN, REMOTE_ADDR=address)
    if device is not None:
        client.cookies[throttle.device_cookie_name()] = device
    return client


@override_settings(STORAGES=PLAIN_STATIC)
class OwnDeviceSecondFactorTests(TestCase):
    """A3: the per-account count of second-factor failures is two counts - the account's own known devices', and every
    other request's. The window is SECOND_FACTOR_PENDING_SECONDS, fixed; the clock is the tests' own."""

    def setUp(self):
        self.operator, self.key = enrolled_operator('a3-operator')
        self.window = settings.SECOND_FACTOR_PENDING_SECONDS

    def own_device(self):
        """The operator's ordinary sign-in from the usual address, then a sign-out: the known-device cookie it set."""
        own = a3_browser(A3_OWN)
        answer = key_step(own, self.key) if password_step(own, self.operator).status_code == 302 else None
        self.assertEqual((answer.status_code, answer.get('Location')), (302, '/ops/'))
        device = own.cookies[throttle.device_cookie_name()].value
        own.post('/logout/')
        return device

    def fill_the_account_count(self):
        """What the holder of the password alone does in a window: the password, then empty answers until the pending
        sign-in is dropped. Every one of them is a failure of its pending sign-in."""
        thief = a3_browser(A3_THIEF)
        self.assertEqual(password_step(thief, self.operator).status_code, 302)
        answers = [thief.post('/login/second-factor', {'credential': ''})
                   for _ in range(settings.SECOND_FACTOR_ATTEMPTS)]
        self.assertEqual([item.status_code for item in answers[:-1]], [400] * (settings.SECOND_FACTOR_ATTEMPTS - 1))
        self.assertEqual((answers[-1].status_code, answers[-1].get('Location')), (302, '/login/?reason=key'))
        return thief

    def test_the_operator_s_own_device_signs_in_with_its_key_window_after_window(self):
        with Clock(MOMENT) as clock:
            device = self.own_device()
            for window in range(1, 4):
                clock.moment = MOMENT + timedelta(seconds=self.window * window + 1)
                self.fill_the_account_count()
                clock.advance(60)
                own = a3_browser(A3_OWN, device)
                self.assertEqual(password_step(own, self.operator).status_code, 302)
                options = own.post('/login/second-factor/options')
                self.assertEqual(options.status_code, 200, f'window {window}: the operator\'s own key is refused')
                signed = own.post('/login/second-factor',
                                  {'credential': json.dumps(self.key.assertion(options.json()))})
                self.assertEqual((signed.status_code, signed.get('Location')), (302, '/ops/'), f'window {window}')
                own.post('/logout/')
                # every other request still shares the count the password's holder used up: a browser with no cookie
                stranger = a3_browser(A3_THIEF)
                self.assertEqual(password_step(stranger, self.operator).status_code, 302)
                self.assertEqual(stranger.post('/login/second-factor/options').status_code, 429)
        outcomes = sorted(models.LoginAttempt.objects.values_list('outcome', flat=True))
        self.assertEqual(outcomes.count(models.LoginAttempt.SIGNED_IN), 4)
        self.assertEqual(outcomes.count(models.LoginAttempt.SECOND_FACTOR_FAILED), 3, 'each pending sign-in its limit')

    def test_the_operator_s_own_recovery_code_works_too(self):
        codes = second_factor.new_recovery_codes(self.operator)
        with Clock(MOMENT) as clock:
            device = self.own_device()
            clock.moment = MOMENT + timedelta(seconds=self.window + 1)
            self.fill_the_account_count()
            own = a3_browser(A3_OWN, device)
            password_step(own, self.operator)
            used = own.post('/login/recovery', {'code': codes[0]})
            self.assertEqual((used.status_code, used.get('Location')), (302, '/ops/'))
            self.assertEqual(second_factor.recovery_codes_left(self.operator), settings.RECOVERY_CODE_COUNT - 1)

    def test_the_signed_in_operator_steps_up_with_the_key_too(self):
        with Clock(MOMENT) as clock:
            own = a3_browser(A3_OWN)
            password_step(own, self.operator)
            self.assertEqual(key_step(own, self.key).get('Location'), '/ops/')  # signed in, the device cookie set
            # the next window, the key older than the step-up allows, and the count filled by the password's holder
            clock.moment = MOMENT + timedelta(seconds=self.window + 61)
            self.fill_the_account_count()
            self.assertEqual(own.post('/ops/security', {'action': 'options'}).json()['error'], 'step_up')
            options = own.post('/login/second-factor/options')
            self.assertEqual(options.status_code, 200, 'the signed-in operator can present the key')
            back = own.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options.json())),
                                                     'next': '/ops/security'})
            self.assertEqual((back.status_code, back.get('Location')), (302, '/ops/security'))
            self.assertEqual(own.post('/ops/security', {'action': 'options'}).status_code, 200)

    def test_the_two_counts_are_apart_both_ways_and_the_device_s_own_still_limits(self):
        with Clock(MOMENT) as clock:
            device = self.own_device()
            clock.moment = MOMENT + timedelta(seconds=self.window + 1)
            own = a3_browser(A3_OWN, device)
            password_step(own, self.operator)
            for _ in range(settings.SECOND_FACTOR_ATTEMPTS):
                key_step(own, self.key, origin='https://x.example')  # wrong answers from the operator's own browser
            again = a3_browser(A3_OWN, device)
            password_step(again, self.operator)
            self.assertEqual(again.post('/login/second-factor/options').status_code, 429, 'the device\'s own limit')
            elsewhere = a3_browser(A3_THIEF)
            password_step(elsewhere, self.operator)
            self.assertEqual(elsewhere.post('/login/second-factor/options').status_code, 200,
                             'the other count is apart')

    def test_a_cookie_of_another_account_or_a_forged_one_counts_with_every_other_request(self):
        doctor = f.member(f.workspace('Synthetic practice A3'))
        others = {'another account\'s cookie': throttle.device_cookie_value(doctor.pk),
                  'a forged cookie': throttle.device_cookie_value(self.operator.pk)[:-2] + 'xx',
                  'no cookie': None}
        with Clock(MOMENT + timedelta(seconds=1)):
            self.own_device()
            self.fill_the_account_count()
            for label, cookie in others.items():
                with self.subTest(label):
                    browser = a3_browser(A3_THIEF, cookie)
                    password_step(browser, self.operator)
                    self.assertEqual(browser.post('/login/second-factor/options').status_code, 429)


# --- A4: the signed-in second-factor pages arm the console's timer (auth-1) -------------------------------------------

A4_SIGN_OUT_FORM = '<form method="post" action="/logout/">'
A4_STATIC = Path(__file__).resolve().parent.parent / 'studio' / 'static' / 'studio'
# ops_session.js run on a rendered page, in a vm: the page's own sign-out form and body data-*, a clock that only the
# harness moves, and a fetch that never answers well (so no ping moves the deadline). It prints what the timer did.
A4_HARNESS = r"""
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const [script, page] = process.argv.slice(2);
const html = fs.readFileSync(page, 'utf8');
const hasForm = /<form[^>]*action="\/logout\/"/.test(html);
const body = (/<body([^>]*)>/.exec(html) || [])[1] || '';
const dataset = {};
for (const [, name, value] of body.matchAll(/data-([a-z-]+)="([^"]*)"/g)) {
  dataset[name.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
}
const start = Date.parse('2026-11-24T12:00:00Z');
const clock = { now: start, timers: [] };
const result = { form: hasForm, dataset, armed: 0, pings: 0, submittedAt: null, action: null, cleared: false };
const form = hasForm ? { attributes: { action: '/logout/' }, setAttribute(key, value) { this.attributes[key] = value; },
  submit() { result.submittedAt = (clock.now - start) / 1000; result.action = this.attributes.action; },
  addEventListener() {}, querySelector: () => ({ value: 'token' }) } : null;
const main = { replaceChildren() { result.cleared = true; } };
const element = () => ({ setAttribute() {}, append() {}, addEventListener() {}, querySelector: () => ({}),
  showModal() { this.open = true; }, close() { this.open = false; }, open: false });
const document = { body: { dataset, append() {} }, hidden: false, activeElement: null, createElement: element,
  querySelector: selector => (selector === 'form[action="/logout/"]' ? form : null), querySelectorAll: () => [],
  getElementById: id => (id === 'main' ? main : null), addEventListener() {} };
const sandbox = { document, console, FormData: class { append() {} }, BroadcastChannel: undefined,
  window: { location: { assign() {} }, addEventListener() {}, localStorage: undefined },
  Date: class extends Date { static now() { return clock.now; } },
  setTimeout: (run, ms) => { const timer = { at: clock.now + ms, run }; clock.timers.push(timer); return timer; },
  clearTimeout: timer => { const at = clock.timers.indexOf(timer); if (at >= 0) clock.timers.splice(at, 1); },
  fetch: async () => { result.pings += 1; return { status: 502, ok: false, json: async () => null }; } };
vm.runInNewContext(fs.readFileSync(script, 'utf8'), sandbox);
result.armed = clock.timers.length;
(async () => {
  const end = start + 3600 * 1000;
  for (;;) {
    await new Promise(resolve => setImmediate(resolve));
    const due = clock.timers.filter(timer => timer.at <= end).sort((a, b) => a.at - b.at)[0];
    if (!due) break;
    clock.timers.splice(clock.timers.indexOf(due), 1);
    clock.now = Math.max(clock.now, due.at);
    due.run();
  }
  console.log(JSON.stringify(result));
})();
"""


@override_settings(STORAGES=PLAIN_STATIC)
class SignedInSecondFactorPagesTimerTests(TestCase):
    """A4: the recovery codes page and the step-up pages are signed-in console pages, and arm the timer."""

    def setUp(self):
        self.operator = f.user('a4-operator')
        ops.grant(self.operator)

    def assert_armed(self, body, label):
        self.assertTrue('src="/static/studio/ops_session.js"' in body, f'{label}: ops_session.js is not loaded')
        self.assertTrue(A4_SIGN_OUT_FORM in body, f'{label}: no sign-out form, which ops_session.js arms on')
        for name in ('data-idle-seconds="', 'data-cap-seconds="', 'data-warning-seconds="', 'data-session="'):
            self.assertTrue(name in body, f'{label}: no {name} on the page')
        self.assertFalse('data-session=""' in body, f'{label}: an empty session tag')

    def codes_page(self):
        self.operator.set_unusable_password()
        self.operator.save()
        _token, code = second_factor.issue_setup_code(self.operator, 'Synthetic Person')
        client = Client(HTTP_HOST=ADMIN)
        self.assertEqual(setup_first_step(client, code).status_code, 303)
        page = setup_key_step(client, Authenticator())
        self.assertEqual(page.status_code, 200)
        self.assertEqual(client.session.get('_auth_user_id'), str(self.operator.pk))
        return page.content.decode()

    def test_the_recovery_codes_page_arms_the_timer(self):
        body = self.codes_page()
        self.assertEqual(body.count('<li>'), settings.RECOVERY_CODE_COUNT)
        self.assert_armed(body, 'the recovery codes page')
        idle = settings.SESSION_IDLE_OPERATOR_SECONDS
        self.assertTrue(f'data-idle-seconds="{idle}"' in body, 'the session was signed in just now')
        self.assertTrue(f'content="{idle + 10};url=/login/?reason=idle"' in body, 'and without script, the refresh')

    def test_the_step_up_pages_arm_the_timer(self):
        add_key(self.operator)
        second_factor.new_recovery_codes(self.operator)
        client = ops.admin_client(self.operator)
        for address in ('/login/second-factor?next=/ops/security', '/login/recovery?next=/ops/security'):
            with self.subTest(address):
                answer = client.get(address)
                self.assertEqual(answer.status_code, 200)
                self.assert_armed(answer.content.decode(), address)

    def test_a_pending_sign_in_s_pages_are_not_signed_in_and_load_no_timer(self):
        add_key(self.operator)
        client = Client(HTTP_HOST=ADMIN)
        self.assertEqual(password_step(client, self.operator).status_code, 302)
        for address in ('/login/second-factor', '/login/recovery'):
            with self.subTest(address):
                body = client.get(address).content.decode()
                self.assertFalse('ops_session.js' in body, f'{address}: a timer on a page signed in as nobody')
                self.assertFalse(A4_SIGN_OUT_FORM in body, f'{address}: a sign-out form for nobody')

    def test_ops_session_js_signs_the_codes_page_out_at_the_idle_limit(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed; the timer is run by node')
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        page, harness = Path(folder.name) / 'codes.html', Path(folder.name) / 'harness.cjs'
        page.write_text(self.codes_page(), encoding='utf-8')
        harness.write_text(A4_HARNESS, encoding='utf-8')
        run = subprocess.run([node, str(harness), str(A4_STATIC / 'ops_session.js'), str(page)], capture_output=True,
                             text=True, timeout=60, check=False)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        seen = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertTrue(seen['form'])
        self.assertGreaterEqual(seen['armed'], 1, 'a timer is armed at load')
        self.assertGreaterEqual(seen['pings'], 1, 'and the first ping is sent')
        self.assertEqual((seen['submittedAt'], seen['action'], seen['cleared']),
                         (settings.SESSION_IDLE_OPERATOR_SECONDS, '/logout/?reason=idle', True),
                         'at the idle limit the screen is cleared and the sign-out form submitted')
