"""Platform-operator access (studio.operator; CORE-UX-DESIGN.md 5). A grant comes only from the management command and
no workspace role ever makes an operator; a revocation ends it; grants are append-only and no URL records one. An
operator with no membership signs in on the same page and lands on the console; one who is also a member signs in as the
member. The console itself (its gate, pages and acts) is tests/test_operator_console.py's. Synthetic data only.
"""
import inspect
import json
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver

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

    def test_grant_operator_records_one_grant_from_the_reason_file(self):
        user = f.user('alice')
        call_command('grant_operator', username='alice', reason_file=str(self.reason), by='synthetic admin', stdout=_out())
        grant = models.OperatorGrant.objects.get(user=user)
        self.assertEqual((grant.reason, grant.granted_by),
                         ('Synthetic platform operator for the diagnostics tests.', 'synthetic admin'))
        out = _out()
        call_command('grant_operator', username='alice', reason_file=str(self.reason), stdout=out)
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
                call_command('grant_operator', username=username, reason_file=str(reason), stdout=_out())
        self.assertFalse(models.OperatorGrant.objects.exists())

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
                call_command('revoke_operator', username=username, reason_file=str(self.reason), stdout=_out())
        self.assertEqual(models.OperatorRevocation.objects.count(), 1)

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
    def setUp(self):
        self.ws = f.workspace()

    def login(self, username, next_url=None):
        data = {'username': username, 'password': 'synthetic-pass-123!'}
        if next_url:
            data['next'] = next_url
        return Client().post('/login/', data)

    def test_an_operator_without_a_membership_signs_in_and_lands_on_the_diagnostics(self):
        user = f.user('ops-agent', actor_kind=models.User.AGENT)
        ops.grant(user)
        response = self.login('ops-agent')
        self.assertEqual((response.status_code, response['Location']), (302, '/ops/'))
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get('/')['Location'], '/ops/')
        self.assertEqual(client.get('/api/session').status_code, 404)  # no workspace of their own
        self.assertEqual(client.get('/ops/').status_code, 200)
        where = '/ops/encounters/00000000-0000-4000-8000-000000000001'
        asked = self.login('ops-agent', where)
        self.assertEqual(asked['Location'], where)

    def test_a_member_operator_lands_where_members_land(self):
        user = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        ops.grant(user)
        self.assertEqual(self.login('owner')['Location'], '/')
        client = Client()
        client.force_login(user)
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
