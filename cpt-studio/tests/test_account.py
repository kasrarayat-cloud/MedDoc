"""Members choose and change their own passwords (release 1, B4; RELEASE-1-SPEC 4, B4): the account page on both hosts
(the current password, the validators, this session kept and every other ended, the records), sign out everywhere, the
forced change of a password staff set and its 72-hour expiry at both doors, and the ruled act require_password_change
(B8). The clock is patched (tests.test_second_factor.Clock). Synthetic data only."""
from __future__ import annotations

import io
import json
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils.html import escape

from studio import models, sessions, views
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import ADMIN, CPT, Clock, add_key, key_step

PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
NEW = 'a new password only I know'


def signed_in(user, *, host=None, password=PASSWORD):
    """A client signed in as ``user`` through the doctors' door (cpt.quillmd.com, or the test host)."""
    client = Client(HTTP_HOST=host) if host else Client()
    answer = client.post('/login/', {'username': user.get_username(), 'password': password})
    assert answer.status_code == 302, answer.content
    return client


def change(client, current=PASSWORD, new=NEW, again=None):
    return client.post('/account/', {'current_password': current, 'new_password': new,
                                     'new_password_again': new if again is None else again})


def live_sessions(user):
    return sum(1 for row in Session.objects.all() if row.get_decoded().get('_auth_user_id') == str(user.pk))


def reason_file(test, text='Synthetic ruled act for a test: every password was set by staff.'):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    path = Path(folder.name) / 'reason.txt'
    path.write_text(text, encoding='utf-8')
    return str(path)


@override_settings(STORAGES=PLAIN_STATIC)
class ChangeTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.other_ws = f.workspace('Another synthetic practice')
        self.member = f.member(self.ws)
        models.Membership.objects.create(user=self.member, workspace=self.other_ws, role=models.Membership.VIEWER)

    def test_a_wrong_current_password_is_refused_and_counted_then_refused_for_the_window(self):
        client = signed_in(self.member)
        for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
            refused = change(client, current='not-the-password')
            self.assertEqual(refused.status_code, 400)
            self.assertIn(views.WRONG_CURRENT, refused.content.decode())
        with mock.patch.object(Argon2PasswordHasher, 'verify', wraps=Argon2PasswordHasher().verify) as verify:
            held = change(client)  # the right password, after five wrong ones: refused for the window, nothing hashed
        self.assertEqual(held.status_code, 400)
        self.assertIn('Too many wrong passwords', held.content.decode())
        self.assertEqual(verify.call_count, 0)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(PASSWORD))
        self.assertEqual(models.RateWindow.objects.filter(scope=views.ACCOUNT_SCOPE).values_list('key', flat=True)
                         .distinct().get(), str(self.member.pk))

    def test_the_validators_are_enforced(self):
        client = signed_in(self.member)
        short = 'kq7vz2mw9rtxbnh'[:settings.PASSWORD_MIN_LENGTH - 1]
        refused = change(client, new=short)
        self.assertEqual(refused.status_code, 400)
        self.assertIn(f'at least {settings.PASSWORD_MIN_LENGTH} characters', refused.content.decode())
        self.assertIn(views.NOT_THE_SAME, change(client, again=NEW + 'x').content.decode())
        self.assertIn(views.SAME_AS_BEFORE, change(client, new=PASSWORD).content.decode())
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(PASSWORD))

    def test_this_session_stays_and_every_other_one_ends(self):
        with Clock():
            here, elsewhere, third = signed_in(self.member), signed_in(self.member), signed_in(self.member)
            stranger = signed_in(f.member(self.ws))
            answer = change(here)
            self.assertEqual((answer.status_code, answer['Location']), (302, '/account/?done=changed'))
            self.assertIn(views.CHANGED, here.get(answer['Location']).content.decode())
            self.assertEqual(here.get('/api/session').status_code, 200)  # this session stays signed in
            for gone in (elsewhere, third):
                self.assertEqual(gone.get('/api/session').status_code, 401)
            self.assertEqual(stranger.get('/api/session').status_code, 200)
            self.assertEqual(live_sessions(self.member), 1)
            self.member.refresh_from_db()
            self.assertTrue(self.member.check_password(NEW))
            self.assertIsNotNone(self.member.password_changed_at)
            event = models.SecurityEvent.objects.get(event='password.changed')
            self.assertEqual((event.actor_id, event.subject_id, event.data['sessions_ended']),
                             (self.member.pk, self.member.pk, 2))
            self.assertNotIn(NEW, json.dumps(event.data))
            audited = models.AuditEvent.objects.filter(event='member.password_changed')
            self.assertEqual(set(audited.values_list('workspace_id', flat=True)), {self.ws.pk, self.other_ws.pk})
            self.assertEqual({row.data['user'] for row in audited}, {str(self.member.pk)})

    def test_sign_out_everywhere_ends_every_session_this_one_included(self):
        here, elsewhere = signed_in(self.member), signed_in(self.member)
        stranger = signed_in(f.member(self.ws))
        answer = here.post('/logout/everywhere')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/'))
        for gone in (here, elsewhere):
            self.assertEqual(gone.get('/api/session').status_code, 401)
        self.assertEqual(stranger.get('/api/session').status_code, 200)
        self.assertEqual(live_sessions(self.member), 0)
        self.assertEqual(models.SecurityEvent.objects.get(event='sessions.ended_everywhere').data['sessions_ended'], 2)
        self.assertEqual(Client().get('/logout/everywhere').status_code, 405)

    def test_the_page_is_on_both_hosts_and_a_signed_out_visit_goes_to_the_sign_in(self):
        self.assertEqual(Client().get('/account/')['Location'], '/login/?next=/account/')
        self.assertEqual(Client(HTTP_HOST=ADMIN).get('/account/')['Location'], '/login/?next=/account/')
        page = signed_in(self.member).get('/account/')
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        for fragment in ('name="current_password"', 'name="new_password"', 'name="new_password_again"',
                         'action="/logout/everywhere"', f'at least {settings.PASSWORD_MIN_LENGTH} characters'):
            self.assertIn(fragment, body)
        self.assertNotRegex(body, r'<script')

    def test_the_index_links_the_account_page(self):
        self.assertIn('href="/account/">Account and password</a>', signed_in(self.member).get('/').content.decode())


@override_settings(STORAGES=PLAIN_STATIC)
class OperatorChangeTests(TestCase):
    def setUp(self):
        self.operator = f.user('platform-operator')
        ops.grant(self.operator)
        self.key = add_key(self.operator)

    def test_an_operator_changes_the_password_on_the_admin_host_after_a_recent_key(self):
        with Clock() as clock:
            client = Client(HTTP_HOST=ADMIN)
            client.post('/login/', {'username': self.operator.username, 'password': PASSWORD})
            self.assertEqual(key_step(client, self.key).status_code, 302)
            clock.advance(settings.SECOND_FACTOR_STEP_UP_SECONDS + 60)
            client.get('/account/')  # activity: the session is not idle, but its second factor is old
            stale = change(client)
            self.assertEqual((stale.status_code, stale['Location']), (303, '/login/second-factor?next=%2Faccount%2F'))
            self.operator.refresh_from_db()
            self.assertTrue(self.operator.check_password(PASSWORD))  # not changed, and the form is not replayed
            back = key_step(client, self.key, next_url='/account/')
            self.assertEqual((back.status_code, back['Location']), (302, '/account/'))
            self.assertEqual(change(client)['Location'], '/account/?done=changed')
            self.operator.refresh_from_db()
            self.assertTrue(self.operator.check_password(NEW))

    def test_an_operator_who_is_a_member_cannot_change_it_on_cpt(self):
        models.Membership.objects.create(user=self.operator, workspace=f.workspace(), role=models.Membership.OWNER)
        client = signed_in(self.operator, host=CPT)
        refused = change(client)
        self.assertEqual(refused.status_code, 400)
        self.assertIn(escape(views.OPERATOR_ON_CONSOLE), refused.content.decode())
        self.assertNotIn('name="current_password"', client.get('/account/').content.decode())
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(PASSWORD))


@override_settings(STORAGES=PLAIN_STATIC)
class ForcedChangeTests(TestCase):
    """B4, items 3 and 4: a password staff set must be replaced, and stops working 72 hours after it was set."""

    def setUp(self):
        self.ws = f.workspace()
        self.member = f.member(self.ws)
        self.encounter = f.encounter(self.ws, self.member)

    def flag(self, user, moment):
        models.User.objects.filter(pk=user.pk).update(password_change_required_at=moment)

    def test_the_forced_change_gates_the_api_the_pages_and_the_admin_host_until_it_is_made(self):
        with Clock() as clock:
            client = signed_in(self.member)
            self.flag(self.member, clock.moment)  # a reset made while the member is signed in: the gate is immediate
            api = client.get('/api/session')
            self.assertEqual((api.status_code, api.json()), (403, {'error': 'password_change_required'}))
            self.assertEqual(client.get(f'/api/encounters/{self.encounter.pk}').status_code, 403)
            self.assertEqual(client.post('/api/encounters', {}).status_code, 403)
            page = client.get('/')
            self.assertEqual((page.status_code, page['Location']), (302, sessions.FORCED_CHANGE_PAGE))
            self.assertEqual(client.post('/ops/people/add', {})['Location'], sessions.FORCED_CHANGE_PAGE)
            for allowed in ('/account/', '/account/?required=1', '/health/'):
                self.assertEqual(client.get(allowed).status_code, 200, allowed)
            self.assertEqual(client.post('/session/activity').status_code, 200)
            self.assertIn('Choose your own password.', client.get('/account/?required=1').content.decode())
            # the admin host gates its own requests the same way
            operator = f.user('flagged-operator')
            ops.grant(operator)
            self.flag(operator, clock.moment)
            console = ops.admin_client(operator)
            self.assertEqual(console.get('/ops/')['Location'], sessions.FORCED_CHANGE_PAGE)
            self.assertEqual(console.get('/login/second-factor?next=/account/').status_code, 200)  # the step-up stays
            # the change clears the flag and opens everything again
            self.assertEqual(change(client)['Location'], '/account/?done=changed')
            self.member.refresh_from_db()
            self.assertIsNone(self.member.password_change_required_at)
            self.assertEqual(client.get('/api/session').status_code, 200)

    def test_a_staff_set_password_older_than_72_hours_is_refused_exactly_like_a_wrong_password(self):
        with Clock() as clock:
            self.flag(self.member, clock.moment)
            operator = f.user('flagged-operator')
            ops.grant(operator)
            add_key(operator)
            self.flag(operator, clock.moment)
            clock.advance(73 * 60 * 60)
            for host, user, sentence in ((CPT, self.member, views.SIGN_IN_REFUSED),
                                         (ADMIN, operator, views.ADMIN_SIGN_IN_REFUSED)):
                with self.subTest(host=host):
                    expired = Client(HTTP_HOST=host).post('/login/', {'username': user.username, 'password': PASSWORD})
                    wrong = Client(HTTP_HOST=host).post('/login/', {'username': user.username, 'password': 'not-it'})
                    for answer in (expired, wrong):
                        self.assertEqual(answer.status_code, 400)
                        self.assertNotIn(settings.SESSION_COOKIE_NAME, answer.cookies)
                    strip = lambda answer: re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', '',  # noqa: E731
                                                  answer.content.decode())
                    self.assertEqual(strip(expired), strip(wrong))  # the same sentence, the same page
                    self.assertIn(sentence, strip(expired))
                    outcomes = list(models.LoginAttempt.objects.filter(username=user.username).order_by('pk')
                                    .values_list('outcome', flat=True))
                    self.assertEqual(outcomes, ['password_expired', 'wrong_password'])
            events = models.SecurityEvent.objects.filter(event='password.expired_unused')
            self.assertEqual(sorted(events.values_list('subject_id', flat=True)), sorted([self.member.pk, operator.pk]))
            for event in events:
                self.assertNotIn(PASSWORD, json.dumps(event.data))

    def test_at_71_hours_it_signs_in_to_the_forced_change_and_a_changed_password_never_expires(self):
        with Clock() as clock:
            self.flag(self.member, clock.moment)
            clock.advance(71 * 60 * 60)
            client = signed_in(self.member)
            self.assertEqual(client.get('/')['Location'], sessions.FORCED_CHANGE_PAGE)
            self.assertEqual(change(client)['Location'], '/account/?done=changed')
            clock.advance(30 * 24 * 60 * 60)
            signed_in(self.member, password=NEW)  # a password the member chose never expires

    def test_the_72_hours_are_read_from_the_flag_s_own_time(self):
        """This test resets no password: it WRITES password_change_required_at directly, as a reset would (the console's
        reset is Lane 3's, studio.console, and is not on this branch). It proves only that the 72-hour rule reads the
        flag's own time, so a flag written later starts a new clock - not that any reset writes it (refutation r2,
        finding 12: the console's reset once kept the old time, and a member past 72 hours could not get back in).

        The integration test that proves the way back end to end runs once Lanes 2 and 3 are combined: Lane 3's
        tests.test_admin_console.ForcedChangeTests.test_a_reset_after_the_72_hours_lets_the_person_sign_in_to_the_forced_change
        (add-person's flag, 73 hours, the real console reset by an operator with the second factor, then the reset
        password at cpt lands on the forced change). It fails on either branch alone."""
        with Clock() as clock:
            self.flag(self.member, clock.moment)
            clock.advance(73 * 60 * 60)
            refused = Client(HTTP_HOST=CPT).post('/login/', {'username': self.member.username, 'password': PASSWORD})
            self.assertEqual(refused.status_code, 400)  # the first flag's 72 hours have passed
            self.flag(self.member, clock.moment)  # the flag written again, as a reset writes it
            clock.advance(71 * 60 * 60)
            client = Client(HTTP_HOST=CPT)
            answer = client.post('/login/', {'username': self.member.username, 'password': PASSWORD})
            self.assertEqual(answer.status_code, 302, 'the new clock ran out after 71 hours')
            self.assertEqual(client.get('/')['Location'], sessions.FORCED_CHANGE_PAGE)
            clock.advance(2 * 60 * 60)
            again = Client(HTTP_HOST=CPT).post('/login/', {'username': self.member.username, 'password': PASSWORD})
            self.assertEqual(again.status_code, 400)  # and the new clock runs out in its turn


@override_settings(STORAGES=PLAIN_STATIC)
class RequirePasswordChangeTests(TestCase):
    """The ruled act require_password_change (D22), end to end on synthetic accounts (B8)."""

    def run_command(self, *args):
        out = io.StringIO()
        call_command('require_password_change', *args, stdout=out)
        return out.getvalue()

    def test_every_human_account_is_flagged_and_no_agent_ever(self):
        ws = f.workspace()
        people = [f.member(ws), f.member(ws)]
        agent = f.member(ws)
        models.User.objects.filter(pk=agent.pk).update(actor_kind=models.User.AGENT)
        with Clock() as clock:
            output = self.run_command('--all', '--reason-file', reason_file(self), '--by', 'Synthetic Person')
            for person in people:
                person.refresh_from_db()
                self.assertEqual(person.password_change_required_at, clock.moment)
                self.assertIn(str(person.pk), output)
                self.assertNotIn(person.username, output)
            agent.refresh_from_db()
            self.assertIsNone(agent.password_change_required_at)
            self.assertIn('1 automated account(s) never flagged', output)
            self.assertEqual(models.SecurityEvent.objects.filter(event='password.change_required').count(), 2)
            # run again: the clocks already running are kept, never restarted
            clock.advance(3600)
            again = self.run_command('--all', '--reason-file', reason_file(self), '--by', 'Synthetic Person')
            self.assertIn('0 account(s) must choose a new password', again)
            people[0].refresh_from_db()
            self.assertEqual(people[0].password_change_required_at, clock.moment - timedelta(seconds=3600))
            with self.assertRaises(CommandError):
                self.run_command('--username', agent.username, '--reason-file', reason_file(self), '--by',
                                 'Synthetic Person')
            agent.refresh_from_db()
            self.assertIsNone(agent.password_change_required_at)
            # a flagged member's next sign-in opens the account page only
            self.assertEqual(signed_in(people[1]).get('/')['Location'], sessions.FORCED_CHANGE_PAGE)

    def test_it_refuses_without_a_person_or_a_reason(self):
        member = f.member(f.workspace())
        for args in (('--username', member.username, '--reason-file', reason_file(self), '--by', 'installer'),
                     ('--username', member.username, '--reason-file', '/nonexistent/reason', '--by', 'Synthetic Person'),
                     ('--username', 'nobody-here', '--reason-file', reason_file(self), '--by', 'Synthetic Person')):
            with self.subTest(args=args[-1]), self.assertRaises(CommandError):
                self.run_command(*args)
        member.refresh_from_db()
        self.assertIsNone(member.password_change_required_at)
        self.assertFalse(models.SecurityEvent.objects.exists())
