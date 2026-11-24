"""Release 1, repair round 1, builder A: the records, the second factor and the console (refutation of the integrated
release, findings failclosed-0 to -5 and -7, bypass-0, phileak-3, auth-0, auth-1 and auth-2). Synthetic data only.

A1  A security act whose SecurityEvent cannot be written does not happen. PostgreSQL itself refuses the record - a
    BEFORE INSERT trigger that raises, or a CHECK (false) NOT VALID constraint - and nothing in the code under test is
    patched; the tests are TransactionTestCases, so every write autocommits as it does in production (no
    ATOMIC_REQUESTS). Each act is shown not to have happened, then to happen with its record once the record can be
    written (the non-vacuity control).
"""
from __future__ import annotations

import io
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings

from studio import models, rate, second_factor, throttle
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import ADMIN, CPT, PASSWORD, Authenticator, add_key, options_of, password_step

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
