"""Platform-operator access (studio.operator; CORE-UX-DESIGN.md 5; release 1, C3). A grant comes only from the management
command, rests on an approval with a review date and a named person who records it, and is for people only: an automated
account is never granted and never an operator, whatever grant row it has. No workspace role ever makes an operator; a
revocation ends the grant and every session of the account; each grant and revocation writes a SecurityEvent; grants are
append-only and no URL records one. The console answers only on the admin host (B3: tests/test_console_host.py); the
console itself (its gate, pages and acts) is tests/test_operator_console.py's. Synthetic data only.
"""
import inspect
import json
import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import CommandError, call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver
from django.utils import timezone

from studio import models, operator
from tests.support import coding as factories
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

ROOT = Path(settings.BASE_DIR)


class _Factories:
    """The old suite's factory names over tests.support.coding: a workspace, a named account of either kind, and a
    membership of a given role."""

    @staticmethod
    def workspace():
        return factories.workspace('Gastroenterology')

    @staticmethod
    def user(username, *, actor_kind=models.User.HUMAN):
        return models.User.objects.create_user(username=username, password='synthetic-pass-123!',
                                               actor_kind=actor_kind, display_name=username.title())

    @staticmethod
    def member(ws, usr, role=models.Membership.REVIEWER):
        models.Membership.objects.create(user=usr, workspace=ws, role=role)
        return usr


f = _Factories


@override_settings(STORAGES=PLAIN_STATIC)  # the URL sweep renders the shell and the login page
class GrantTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        # A runner's STATE_DIR (CI's included) need not exist yet: nothing before this test creates it.
        Path(settings.STATE_DIR).mkdir(mode=0o700, parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=settings.STATE_DIR))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.reason = self.tmp / 'reason.txt'
        self.reason.write_text('Synthetic platform operator for the diagnostics tests.\n', encoding='utf-8')

    def test_a_workspace_role_never_makes_an_operator_and_a_grant_survives_every_role(self):
        user = f.member(self.ws, f.user('member'), role=models.Membership.VIEWER)
        membership = models.Membership.objects.get(user=user)
        for role in (models.Membership.REVIEWER, models.Membership.OWNER, models.Membership.VIEWER):
            membership.role = role
            membership.save()
            self.assertFalse(operator.is_operator(user), role)
        ops.grant(user)
        for role, active in ((models.Membership.OWNER, True), (models.Membership.VIEWER, False)):
            membership.role, membership.active = role, active
            membership.save()
            self.assertTrue(operator.is_operator(user), role)
        operator.revoke(user, 'Synthetic test: revoked.', 'tests')
        self.assertFalse(operator.is_operator(user))
        user.is_active = False
        user.save()
        ops.grant(user)
        self.assertFalse(operator.is_operator(user), 'an inactive account is never an operator')

    def test_is_operator_reads_no_membership(self):
        user = f.user('reader')
        ops.grant(user)
        names = set(operator.is_operator.__code__.co_names)  # every global and attribute the function's code reads
        self.assertIn('OperatorGrant', names)
        self.assertFalse({name for name in names if 'membership' in name.lower()}, names)
        with self.assertNumQueries(1):
            self.assertTrue(operator.is_operator(user))

    def grant_command(self, username, *, reason=None, omit=(), **overrides):
        """grant_operator with every required argument - the reason file, a synthetic approval, a review date 90 days
        away and a named person - each replaced by ``overrides`` and left out when named in ``omit``."""
        arguments = {'username': username, 'reason_file': str(reason or self.reason), 'by': 'Synthetic Admin',
                     'authorization_ref': 'docs/foundation/rulings/synthetic-grant.md',
                     'review_by': (timezone.localdate() + timedelta(days=90)).isoformat(), **overrides}
        for name in omit:
            arguments.pop(name)
        return call_command('grant_operator', stdout=_out(), **arguments)

    def test_grant_operator_records_one_grant_from_the_reason_file(self):
        user = f.user('alice')
        review_by = timezone.localdate() + timedelta(days=90)
        self.grant_command('alice', by='synthetic admin', review_by=review_by.isoformat())
        grant = models.OperatorGrant.objects.get(user=user)
        self.assertEqual((grant.reason, grant.granted_by, grant.authorization_ref, grant.review_by),
                         ('Synthetic platform operator for the diagnostics tests.', 'synthetic admin',
                          'docs/foundation/rulings/synthetic-grant.md', review_by))
        out = _out()
        call_command('grant_operator', username='alice', reason_file=str(self.reason), by='Synthetic Admin',
                     authorization_ref='docs/foundation/rulings/synthetic-grant.md',
                     review_by=review_by.isoformat(), stdout=out)
        self.assertIn('already holds operator access', out.getvalue())
        self.assertEqual(models.OperatorGrant.objects.filter(user=user).count(), 1)
        self.assertTrue(operator.is_operator(user))

    def test_grant_operator_refuses_and_records_nothing(self):
        f.user('bob')
        empty = self.tmp / 'empty.txt'
        empty.write_text('   \n', encoding='utf-8')
        inactive = f.user('carol')
        inactive.is_active = False
        inactive.save()
        for username, reason, words in (('nobody-here', self.reason, 'No account is named'),
                                        ('bob', self.tmp / 'missing.txt', 'cannot be read'),
                                        ('bob', empty, 'empty'), ('carol', self.reason, 'not active')):
            with self.subTest(username=username, reason=reason.name), self.assertRaisesRegex(CommandError, words):
                self.grant_command(username, reason=reason)
        self.assertFalse(models.OperatorGrant.objects.exists())

    def test_grant_operator_requires_the_approval_the_review_date_and_the_person(self):
        # release 1, C3: all three are required, and each refusal records nothing
        f.user('bob')
        for missing in ('authorization_ref', 'review_by', 'by'):
            with self.subTest(missing=missing), self.assertRaisesRegex(CommandError, 'arguments are required'):
                self.grant_command('bob', omit=(missing,))
        today = timezone.localdate()
        for label, arguments, words in (
                ('a past review date', {'review_by': (today - timedelta(days=1)).isoformat()}, 'already passed'),
                ('more than 12 months away', {'review_by': (today + timedelta(days=400)).isoformat()}, '12 months'),
                ('not a date', {'review_by': '2026-13-01'}, 'YYYY-MM-DD'),
                ('a blank approval', {'authorization_ref': '   '}, 'authorization reference is required'),
                ('an approval too long', {'authorization_ref': 'x' * 201}, 'at most 200'),
                ('a role as --by', {'by': 'operator'}, 'names a role'),
                ('another role as --by', {'by': '[SECURITY OFFICER]'}, 'names a role'),
                ('a uid as --by', {'by': 'uid 1000'}, 'names a role'),
                ('a blank --by', {'by': '  '}, 'names the person')):
            with self.subTest(label), self.assertRaisesRegex(CommandError, words):
                self.grant_command('bob', **arguments)
        self.assertFalse(models.OperatorGrant.objects.exists())
        self.assertFalse(models.SecurityEvent.objects.exists())
        # the furthest review date allowed is the same day twelve months on
        self.grant_command('bob', review_by=operator.review_limit(today).isoformat())
        self.assertEqual(models.OperatorGrant.objects.get(user__username='bob').review_by, operator.review_limit(today))

    def test_an_automated_account_is_never_granted_and_never_an_operator(self):
        agent = f.user('review-agent', actor_kind=models.User.AGENT)
        with self.assertRaisesRegex(CommandError, 'automated account cannot be an operator'):
            self.grant_command('review-agent')
        with self.assertRaisesRegex(ValueError, 'automated account cannot be an operator'):
            operator.grant(agent, 'Synthetic test reason for an automated account.', 'tests')
        self.assertFalse(models.OperatorGrant.objects.exists())
        self.assertFalse(models.SecurityEvent.objects.exists())
        # a grant row written before release 1 (as the installer once granted ops-agent) gives it no power at all
        models.OperatorGrant.objects.create(user=agent, reason='Synthetic grant from before release 1.',
                                            granted_by='synthetic installer')
        agent.refresh_from_db()
        self.assertFalse(operator.is_operator(agent))
        with self.assertNumQueries(0):
            operator.is_operator(agent)  # refused on the account it already holds, before any query

    def test_a_grant_and_a_revocation_write_their_security_events_with_ids_only(self):
        user = f.user('frank')
        self.grant_command('frank', by='Synthetic Admin')
        grant = models.OperatorGrant.objects.get(user=user)
        granted = models.SecurityEvent.objects.get(event='operator.granted')
        self.assertEqual((granted.subject_id, granted.actor_label, granted.data),
                         (user.pk, 'Synthetic Admin', {'grant': str(grant.pk), 'review_by': grant.review_by.isoformat()}))
        call_command('revoke_operator', username='frank', reason_file=str(self.reason), by='Synthetic Admin',
                     stdout=_out())
        revoked = models.SecurityEvent.objects.get(event='operator.revoked')
        self.assertEqual((revoked.subject_id, revoked.actor_label, revoked.data),
                         (user.pk, 'Synthetic Admin', {'grants': [str(grant.pk)], 'sessions_ended': 0}))
        for row in (granted, revoked):  # ids, a date and counts: never the reason or the approval's text
            self.assertNotIn('Synthetic platform operator', json.dumps(row.data))

    def test_revoke_operator_ends_the_grant_and_refuses_without_one(self):
        user = f.user('dave')
        ops.grant(user)
        call_command('revoke_operator', username='dave', reason_file=str(self.reason), by='synthetic admin',
                     stdout=_out())
        revocation = models.OperatorRevocation.objects.get(grant__user=user)
        self.assertEqual(revocation.revoked_by, 'synthetic admin')
        self.assertFalse(operator.is_operator(user))
        self.assertEqual(models.OperatorGrant.objects.filter(user=user).count(), 1)  # the grant row stays
        for username in ('dave', 'nobody-here'):
            with self.assertRaises(CommandError):
                call_command('revoke_operator', username=username, reason_file=str(self.reason), by='Synthetic Admin',
                             stdout=_out())
        self.assertEqual(models.OperatorRevocation.objects.count(), 1)

    def test_revoke_operator_requires_a_named_person(self):
        user = f.user('gina')
        ops.grant(user)
        with self.assertRaises(CommandError):  # --by left out: argparse's own refusal
            call_command('revoke_operator', username='gina', reason_file=str(self.reason), stdout=_out())
        for by in ('operator', 'Platform-Operator', 'root', 'uid 0', ''):
            with self.subTest(by=by), self.assertRaises(CommandError):
                call_command('revoke_operator', username='gina', reason_file=str(self.reason), by=by, stdout=_out())
        self.assertFalse(models.OperatorRevocation.objects.exists())
        self.assertTrue(operator.is_operator(user))

    def test_a_revocation_ends_every_session_of_the_account(self):
        user, other = f.user('hank'), f.user('ivy')
        ops.grant(user)
        sessions = [ops.admin_client(user), ops.client(user, HTTP_HOST='cpt.quillmd.com'), ops.admin_client(other)]
        self.assertEqual(sessions[0].get('/ops/people').status_code, 200)
        self.assertEqual(sessions_of(user), 2)
        operator.revoke(user, 'Synthetic test revocation.', 'Synthetic Admin')
        self.assertEqual(sessions_of(user), 0)  # every session of the account ended at once
        self.assertEqual(sessions_of(other), 1)  # another account's session stays
        self.assertEqual(models.SecurityEvent.objects.get(event='operator.revoked').data['sessions_ended'], 2)
        self.assertEqual(sessions[0].get('/ops/people').status_code, 302)  # signed out: the admin host's sign-in

    def test_grants_and_revocations_are_append_only(self):
        grant = ops.grant(f.user('erin'))
        grant.reason = 'changed'
        with self.assertRaises(Exception):
            grant.save()
        with self.assertRaises(Exception):
            models.OperatorGrant.objects.all().delete()

    def test_no_url_records_a_grant(self):
        """Statically: no view module of the URLconf names the grant or its writer; behaviourally: an owner and an operator
        posting to every URL pattern record none."""
        modules = set()
        for pattern in get_resolver().url_patterns:
            if isinstance(pattern, URLPattern):
                modules.add(inspect.getmodule(pattern.callback))
        for module in modules:
            source = inspect.getsource(module)
            if module is operator:
                source = source.replace(inspect.getsource(operator.grant), '').replace(
                    inspect.getsource(operator.revoke), '')
            self.assertNotRegex(source, r'OperatorGrant\.objects\.create|OperatorRevocation\.objects\.create|'
                                        r'operator\.grant\(|\bgrant\(', module.__name__)
        writers = [path.relative_to(ROOT) for path in (ROOT / 'studio').rglob('*.py')
                   if re.search(r'operator\.grant\(|OperatorGrant\.objects\.create', path.read_text(encoding='utf-8'))]
        self.assertEqual(sorted(map(str, writers)), ['studio/management/commands/grant_operator.py', 'studio/operator.py'])
        owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        platform = f.user('platform')
        ops.grant(platform)
        before = models.OperatorGrant.objects.count()
        for user in (owner, platform):
            client = Client(enforce_csrf_checks=False)
            client.force_login(user)
            for pattern in get_resolver().url_patterns:
                route = str(pattern.pattern).replace('<uuid:encounter_id>', '00000000-0000-4000-8000-000000000001') \
                    .replace('<uuid:report_id>', '00000000-0000-4000-8000-000000000002')
                if route in ('logout/',):
                    continue
                client.post('/' + route, data=json.dumps({'username': user.username, 'reason': 'x' * 20}),
                            content_type='application/json')
        self.assertEqual(models.OperatorGrant.objects.count(), before)
        self.assertFalse(operator.is_operator(owner))


@override_settings(STORAGES=PLAIN_STATIC)
class LoginTests(TestCase):
    """Where an operator's sign-in leads is the doors' (Lane 2: the cpt door loses its operator branch, B3 step 2); what
    is held here is the console's side of it (B3, C3): no session from cpt.quillmd.com ever reaches the console, an
    operator who is also a member keeps the doctors' app, and an account that is no operator is refused."""

    def setUp(self):
        self.ws = f.workspace()

    def login(self, username, next_url=None):
        data = {'username': username, 'password': 'synthetic-pass-123!'}
        if next_url:
            data['next'] = next_url
        return Client().post('/login/', data)

    def test_an_operator_without_a_membership_reaches_no_console_on_the_doctors_host(self):
        user = f.user('platform-operator')
        ops.grant(user)
        for host in ('testserver', 'cpt.quillmd.com'):
            client = ops.client(user, HTTP_HOST=host)  # a session opened at the cpt door
            with self.subTest(host=host):
                self.assertEqual(client.get('/ops/').status_code, 404)
                self.assertEqual(client.get('/api/session').status_code, 404)  # no workspace of their own
        self.assertEqual(ops.admin_client(user).get('/ops/').status_code, 200)  # the console is the admin host's

    def test_an_automated_account_signs_in_to_no_console(self):
        agent = f.user('ops-agent', actor_kind=models.User.AGENT)
        models.OperatorGrant.objects.create(user=agent, reason='Synthetic grant from before release 1.',
                                            granted_by='synthetic installer')
        response = self.login('ops-agent')  # no membership and no operator power: the wrong-password answer
        self.assertEqual(response.status_code, 400)
        self.assertIn('The username or password is not correct.', response.content.decode())
        signed_in = ops.mark_signed_in(_signed_in(agent, 'admin.quillmd.com'), door='admin')  # the door's markers
        self.assertEqual(signed_in.get('/ops/').status_code, 404)

    def test_a_member_operator_lands_where_members_land(self):
        user = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        ops.grant(user)
        self.assertEqual(self.login('owner')['Location'], '/')
        client = ops.mark_signed_in(_signed_in(user), door='cpt')
        self.assertEqual(client.get('/').status_code, 200)

    def test_without_a_membership_or_a_grant_sign_in_is_refused_as_before(self):
        f.user('stranger')
        revoked = f.user('former')
        ops.grant(revoked)
        operator.revoke(revoked, 'Synthetic test: revoked.', 'tests')
        for username in ('stranger', 'former'):
            response = self.login(username)
            self.assertEqual(response.status_code, 400, username)
            self.assertIn('The username or password is not correct.', response.content.decode())


class MigrationTests(SimpleTestCase):
    def test_the_operator_migration_is_additive_for_the_rolling_install(self):
        from ops import install
        verdict = install.migration_verdict((ROOT / 'studio' / 'migrations' / '0010_cux_operator.py').read_text())
        self.assertEqual(verdict, {'safe': True, 'why': [
            'reportartifact.audience: NOT NULL with a database default (db_default)',
            'OperatorGrant: a new table no older revision reads', 'OperatorRevocation: a new table no older revision reads']})


def _out():
    import io
    return io.StringIO()


def _signed_in(user, host='testserver'):
    client = Client(HTTP_HOST=host)
    client.force_login(user)
    return client


def sessions_of(user):
    """How many stored sessions are signed in as ``user``."""
    return sum(1 for item in Session.objects.all() if item.get_decoded().get('_auth_user_id') == str(user.pk))
