"""The operator console's controls (owner direction 2026-11-22, DECISIONS D395; studio.console): people and roles,
workspaces, spending and the activity log. The gate (every new URL answers what an unknown URL answers to anyone who is
not an operator, before anything is read or written), each act and its refusals, the one-time password (shown once, in
the POST's own answer, never stored, logged, audited or put in a URL), operator accounts left alone, nothing deleted,
the spending figures against the console's own pricing, and the read-only activity log. Synthetic data only."""
import random
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import console, customer, jobs, models
from tests.support import operator as ops
from tests.support import rounds as r

User, Membership, Workspace, Run = models.User, models.Membership, models.Workspace, models.ProviderRun
UUID = '00000000-0000-4000-8000-0000000000aa'
# The sign-in page names its static files; tests have no collected manifest (as tests/test_frontend.py).
PLAIN_STATIC = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


def page(response) -> str:
    return response.content.decode('utf-8')


def shown_password(response) -> str:
    match = re.search(r'<output class="secret"[^>]*>([^<]+)</output>', page(response))
    assert match, 'no password shown'
    return match.group(1).strip()


REQUESTED_BY = 'Synthetic practice contact, ticket 1042'


class ActsClient:
    """The operator's client as the console's forms post (release 1, C3): every form that changes access carries a
    Requested by, so each POST here sends one unless it names its own; ``raw`` is the client itself."""

    def __init__(self, client, requested_by=REQUESTED_BY):
        self.raw, self.requested_by = client, requested_by

    def post(self, path, data=None, *args, **kwargs):
        if data is None or (isinstance(data, dict) and 'requested_by' not in data):
            data = {**(data or {}), 'requested_by': self.requested_by}
        return self.raw.post(path, data, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.raw, name)


@override_settings(STORAGES=PLAIN_STATIC)
class AdminCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = r.f.member(self.ws, role=Membership.OWNER)
        self.operator_user = r.f.user('platform-operator')
        self.ops = ActsClient(ops.admin_client(self.operator_user))
        self.neuro = models.Category.objects.create(slug='neurosurgery', name='Neurosurgery',
                                                    profiles_version='synthetic@1')

    def counts(self):
        return (User.objects.count(), Membership.objects.count(), Workspace.objects.count(),
                models.AuditEvent.objects.count(), list(User.objects.order_by('pk').values_list('password', 'is_active')),
                list(Membership.objects.order_by('pk').values_list('role', flat=True)))

    def membership(self, user):
        return Membership.objects.get(user=user)

    def sessions_of(self, user):
        return sum(1 for item in Session.objects.all() if item.get_decoded().get('_auth_user_id') == str(user.pk))


class GateTests(AdminCase):
    def test_every_new_url_answers_a_customer_exactly_as_an_unknown_url_and_changes_nothing(self):
        gets = ['/ops/people', '/ops/workspaces', f'/ops/workspaces/{self.ws.pk}', '/ops/spending', '/ops/activity',
                '/ops/activity/sign-ins']
        posts = ['/ops/people/add', f'/ops/people/{self.viewer.pk}/role', f'/ops/people/{self.viewer.pk}/password',
                 f'/ops/people/{self.viewer.pk}/access', '/ops/workspaces/new']
        callers = {'anonymous': Client(), 'reviewer': self.client_for(self.reviewer),
                   'owner': self.client_for(self.owner), 'viewer': self.client_for(self.viewer)}
        unknown = Client().get('/opsx/nothing-here')
        before = self.counts()
        body = {'workspace': str(self.ws.pk), 'username': 'intruder-made', 'role': 'owner', 'name': 'X',
                'membership': str(self.membership(self.viewer).pk), 'access': 'off', 'category': str(self.neuro.pk)}
        for name, caller in callers.items():
            for url in gets + posts:
                for method in ('GET', 'POST'):
                    with self.subTest(caller=name, method=method, url=url):
                        response = caller.get(url) if method == 'GET' else caller.post(url, body)
                        self.assertEqual(response.status_code, 404)
                        self.assertEqual(response.get('Vary'), unknown.get('Vary'))
        self.assertEqual(self.counts(), before)
        self.assertFalse(User.objects.filter(username='intruder-made').exists())

    def test_no_slash_is_appended_and_a_revoked_operator_is_a_stranger_again(self):
        self.assertEqual(self.ops.get('/ops/people/').status_code, 404)
        self.assertEqual(self.ops.get('/ops/people').status_code, 200)
        from studio import operator
        operator.revoke(self.operator_user, 'Synthetic test revocation of the console grant.', 'tests')
        # the revocation ended the old session (C3); a new one, second factor and all (and no new grant)
        again = ops.mark_signed_in(self.client_for(self.operator_user, HTTP_HOST='admin.quillmd.com'), door='admin')
        for url in ('/ops/people', '/ops/workspaces', '/ops/spending', '/ops/activity'):
            with self.subTest(url=url):
                self.assertEqual(again.get(url).status_code, 404)
                self.assertEqual(self.ops.get(url)['Location'], '/login/?next=' + url.replace('/', '%2F'))

    def test_the_acts_check_the_csrf_token_after_the_gate(self):
        strict = ops.admin_client(self.operator_user, enforce_csrf_checks=True)
        before = self.counts()
        for url, body in ((f'/ops/people/{self.viewer.pk}/access', {'access': 'off'}),
                          (f'/ops/people/{self.viewer.pk}/password', {}),
                          ('/ops/workspaces/new', {'name': 'CSRF practice', 'category': str(self.neuro.pk)})):
            with self.subTest(url=url):
                self.assertEqual(strict.post(url, body).status_code, 403)
        self.assertEqual(self.counts(), before)

    def test_methods_are_fixed(self):
        self.assertEqual(self.ops.post('/ops/people', {}).status_code, 405)
        self.assertEqual(self.ops.get('/ops/people/add').status_code, 405)
        self.assertEqual(self.ops.get(f'/ops/people/{self.viewer.pk}/access').status_code, 405)


class PeopleTests(AdminCase):
    def test_the_page_lists_every_member_the_operators_and_the_accounts_with_no_workspace(self):
        loose = r.f.user('loose-account')
        response = self.ops.get('/ops/people')
        self.assertEqual(response.status_code, 200)
        text = page(response)
        for user in (self.reviewer, self.viewer, self.agent, self.owner, self.outsider, self.operator_user, loose):
            with self.subTest(user=user.username):
                self.assertIn(user.username, text)
        for words in ('Gastroenterology', 'Another practice', 'Reviewbot (automated agent)', 'Viewer', 'Owner',
                      'Operator accounts open this console', 'Accounts with no workspace', 'Add a person'):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_an_operator_who_is_also_a_member_gets_no_manage_forms(self):
        Membership.objects.create(user=self.operator_user, workspace=self.ws, role=Membership.OWNER)
        text = page(self.ops.get('/ops/people'))
        self.assertIn('Operator account: managed on the server.', text)
        self.assertNotIn(f'/ops/people/{self.operator_user.pk}/', text)
        self.assertIn(f'/ops/people/{self.viewer.pk}/access', text)

    def test_adding_a_person_shows_the_password_once_and_the_person_can_sign_in(self):
        before = models.AuditEvent.objects.count()
        response = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'dr.rivera',
                                                     'name': 'Dr. Maya Rivera', 'role': 'reviewer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('Location', response)
        password = shown_password(response)
        self.assertRegex(password, r'^[a-z2-9]{5}(-[a-z2-9]{5}){3}$')
        person = User.objects.get(username='dr.rivera')
        self.assertEqual((person.display_name, person.actor_kind, person.is_active), ('Dr. Maya Rivera', User.HUMAN, True))
        self.assertTrue(person.check_password(password))
        self.assertNotIn(password, person.password)
        member = self.membership(person)
        self.assertEqual((member.workspace_id, member.role, member.active), (self.ws.pk, 'reviewer', True))
        events = list(models.AuditEvent.objects.order_by('created_at', 'pk')[before:])
        self.assertEqual([(e.event, e.workspace_id, e.encounter_id, e.actor_id) for e in events],
                         [('operator.member_added', self.ws.pk, None, self.operator_user.pk)])
        self.assertEqual(events[0].data, {'user': str(person.pk), 'username': 'dr.rivera', 'role': 'reviewer',
                                          'requested_by': REQUESTED_BY})
        self.assertNotIn(password, repr([e.data for e in models.AuditEvent.objects.all()]))
        # release 1, B4: the password the console showed must be replaced at the first sign-in, within 72 hours
        self.assertIsNotNone(person.password_change_required_at)
        self.assertIn('Dr. Maya Rivera must choose a new password at the first sign-in, within 72 hours', page(response))
        # the password is on this page only: the People page afterwards does not carry it
        self.assertNotIn(password, page(self.ops.get('/ops/people')))
        # the person signs in through the real sign-in page and lands in the doctor app's workspace - or, once the
        # session policy enforces the forced change (Lane 2, B4), on its refusal, which names nothing else
        doctor = Client()
        signed = doctor.post('/login/', {'username': 'dr.rivera', 'password': password})
        self.assertEqual(signed.status_code, 302)
        session = doctor.get('/api/session')
        self.assertIn(session.status_code, (200, 403))
        if session.status_code == 403:
            self.assertEqual(session.json(), {'error': 'password_change_required'})

    def test_adding_a_person_refuses_and_records_nothing(self):
        before = self.counts()
        base = {'workspace': str(self.ws.pk), 'username': 'new.person', 'name': 'New Person', 'role': 'viewer'}
        cases = [({'username': 'New.Person'}, 400), ({'username': 'ab'}, 400), ({'username': 'has space'}, 400),
                 ({'username': '-leading'}, 400), ({'username': 'x' * 41}, 400), ({'username': ''}, 400),
                 ({'role': 'admin'}, 400), ({'role': ''}, 400), ({'workspace': ''}, 400), ({'workspace': UUID}, 400),
                 ({'workspace': 'not-a-uuid'}, 400), ({'name': 'Dr.\x00Nul'}, 400), ({'name': 'n' * 121}, 400),
                 ({'username': self.viewer.username}, 409), ({'username': self.viewer.username.upper()}, 400)]
        for change, status in cases:
            with self.subTest(change=change):
                response = self.ops.post('/ops/people/add', {**base, **change})
                self.assertEqual(response.status_code, status)
                self.assertIn('notice error', page(response))
                self.assertNotIn('class="secret"', page(response))
        self.assertEqual(self.counts(), before)

    def test_a_taken_username_is_refused_whatever_its_case(self):
        legacy = User.objects.create_user(username='Legacy-Name', password='synthetic-pass-123!')
        Membership.objects.create(user=legacy, workspace=self.ws, role=Membership.VIEWER)
        response = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'legacy-name',
                                                     'role': 'viewer'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(User.objects.filter(username__iexact='legacy-name').count(), 1)

    def test_a_refusal_from_a_workspace_page_answers_that_page(self):
        response = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'back': str(self.ws.pk),
                                                     'username': 'BAD', 'role': 'viewer'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('&larr; Every workspace', page(response))

    def test_a_reset_password_works_once_ends_the_old_one_and_every_session(self):
        session = self.client_for(self.viewer)
        self.assertEqual(session.get('/api/session').status_code, 200)
        before = models.AuditEvent.objects.count()
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/password', {})
        self.assertEqual(response.status_code, 200)
        password = shown_password(response)
        self.viewer.refresh_from_db()
        self.assertTrue(self.viewer.check_password(password))
        self.assertIsNone(authenticate(username=self.viewer.username, password='synthetic-pass-123!'))
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        self.assertEqual(self.sessions_of(self.viewer), 0)
        events = list(models.AuditEvent.objects.order_by('created_at', 'pk')[before:])
        self.assertEqual([(e.event, e.workspace_id) for e in events], [('operator.password_reset', self.ws.pk)])
        self.assertEqual(events[0].data['sessions_ended'], 1)
        self.assertNotIn(password, repr(events[0].data))

    def test_operator_accounts_and_accounts_with_no_workspace_are_left_alone(self):
        other_operator = r.f.user('second-operator')
        ops.grant(other_operator)
        Membership.objects.create(user=other_operator, workspace=self.ws, role=Membership.OWNER)
        loose = r.f.user('loose-account')
        before = self.counts()
        for user in (self.operator_user, other_operator, loose):
            membership = Membership.objects.filter(user=user).first()
            for url, body in ((f'/ops/people/{user.pk}/password', {}),
                              (f'/ops/people/{user.pk}/access', {'access': 'off'}),
                              (f'/ops/people/{user.pk}/role', {'role': 'viewer',
                                                               'membership': str(membership.pk) if membership else ''})):
                with self.subTest(user=user.username, url=url):
                    response = self.ops.post(url, body)
                    self.assertEqual(response.status_code, 409)
                    self.assertNotIn('class="secret"', page(response))
        self.assertEqual(self.counts(), before)

    def test_changing_a_role(self):
        member = self.membership(self.viewer)
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['Location'], '/ops/people?done=role')
        member.refresh_from_db()
        self.assertEqual(member.role, 'reviewer')
        event = models.AuditEvent.objects.get(event='operator.role_changed')
        self.assertEqual(event.data, {'user': str(self.viewer.pk), 'username': self.viewer.username,
                                      'from': 'viewer', 'to': 'reviewer', 'requested_by': REQUESTED_BY})
        self.assertIn('The role was changed.', page(self.ops.get(response['Location'])))
        # the same role again changes and records nothing
        again = self.ops.post(f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer'})
        self.assertEqual(again['Location'], '/ops/people?done=same-role')
        self.assertEqual(models.AuditEvent.objects.filter(event='operator.role_changed').count(), 1)
        # the doctor app reads the new role: a reviewer may decide
        self.assertTrue(Membership.objects.get(pk=member.pk).can_review)

    def test_a_role_change_returns_to_the_workspace_page_it_came_from(self):
        member = self.membership(self.viewer)
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/role',
                                 {'membership': str(member.pk), 'role': 'owner', 'back': str(self.ws.pk)})
        self.assertEqual(response['Location'], f'/ops/workspaces/{self.ws.pk}?done=role')
        # a back value that is not one of the person's workspaces falls back to People
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/role',
                                 {'membership': str(member.pk), 'role': 'viewer', 'back': str(self.other_ws.pk)})
        self.assertEqual(response['Location'], '/ops/people?done=role')
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/role',
                                 {'membership': str(member.pk), 'role': 'owner', 'back': 'https://elsewhere.example/'})
        self.assertEqual(response['Location'], '/ops/people?done=role')

    def test_a_role_change_refuses_a_wrong_role_or_another_persons_membership(self):
        before = self.counts()
        mine = self.membership(self.viewer)
        theirs = self.membership(self.reviewer)
        for body, status in (({'membership': str(mine.pk), 'role': 'admin'}, 400),
                             ({'membership': str(theirs.pk), 'role': 'owner'}, 404),
                             ({'membership': 'x', 'role': 'owner'}, 404), ({'role': 'owner'}, 404)):
            with self.subTest(body=body):
                self.assertEqual(self.ops.post(f'/ops/people/{self.viewer.pk}/role', body).status_code, status)
        self.assertEqual(self.ops.post(f'/ops/people/{UUID}/role', {'role': 'owner'}).status_code, 404)
        self.assertEqual(self.counts(), before)

    def test_turning_access_off_everywhere_stops_sign_in_and_ends_sessions_and_on_restores_it(self):
        session = self.client_for(self.reviewer)
        self.assertEqual(session.get('/api/session').status_code, 200)
        response = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'scope': 'everywhere'})
        self.assertEqual((response.status_code, response['Location']), (303, '/ops/people?done=off-everywhere'))
        self.reviewer.refresh_from_db()
        self.assertFalse(self.reviewer.is_active)
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        refused = Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(self.sessions_of(self.reviewer), 0)
        self.assertEqual(models.AuditEvent.objects.get(event='operator.access_off').data['sessions_ended'], 1)
        # nothing deleted: the account and its membership stay
        self.assertTrue(Membership.objects.filter(user=self.reviewer, active=True).exists())
        same = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'scope': 'everywhere'})
        self.assertEqual(same['Location'], '/ops/people?done=same-access')
        back_on = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'on', 'scope': 'everywhere'})
        self.assertEqual(back_on['Location'], '/ops/people?done=on-everywhere')
        # the session opened before access was turned off never comes back: the person signs in again
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        signed = Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(signed.status_code, 302)
        self.assertEqual(list(models.AuditEvent.objects.filter(event__startswith='operator.access_')
                              .order_by('created_at', 'pk').values_list('event', flat=True)),
                         ['operator.access_off', 'operator.access_on'])
        self.assertEqual(self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'maybe'}).status_code, 400)
        self.assertEqual(self.ops.post(f'/ops/people/{self.reviewer.pk}/access',
                                       {'access': 'off', 'scope': 'galaxy'}).status_code, 400)
        self.assertEqual({event.data['scope'] for event in models.AuditEvent.objects.filter(
            event__startswith='operator.access_')}, {'everywhere'})

    def test_the_customer_activity_never_shows_an_operator_act(self):
        enc = self.done(title='Synthetic note for the activity check')
        before = customer.activity_json(enc)
        self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'activity-check', 'role': 'viewer'})
        self.ops.post(f'/ops/people/{self.viewer.pk}/access', {'access': 'off'})
        self.assertEqual(customer.activity_json(enc), before)


class WorkspaceTests(AdminCase):
    def test_the_list_shows_each_workspace_with_its_specialty_and_counts(self):
        r.f.encounter(self.ws, self.reviewer, title='Counted note')
        models.User.objects.filter(pk=self.viewer.pk).update(is_active=False)
        text = page(self.ops.get('/ops/workspaces'))
        self.assertIn('Gastroenterology', text)
        self.assertIn('Synthetic coding', text)
        row = re.search(r'Gastroenterology</a></td><td>Synthetic coding</td>\s*<td class="num">(\d+)</td><td class="num">'
                        r'(\d+)</td><td class="num">(\d+)</td>', text)
        self.assertEqual(row.groups(), ('3', '4', '1'))  # reviewer, agent, owner with access; the viewer is off

    def test_creating_a_workspace_and_adding_its_first_person(self):
        response = self.ops.post('/ops/workspaces/new', {'name': 'Spine Partners', 'category': str(self.neuro.pk)})
        self.assertEqual(response.status_code, 303)
        created = Workspace.objects.get(name='Spine Partners')
        self.assertEqual(response['Location'], f'/ops/workspaces/{created.pk}?done=created')
        self.assertEqual(created.category, self.neuro)
        self.assertTrue(created.synthetic_only)
        event = models.AuditEvent.objects.get(event='operator.workspace_created')
        self.assertEqual((event.workspace_id, event.data), (created.pk, {'name': 'Spine Partners',
                                                                         'category': 'neurosurgery',
                                                                         'requested_by': REQUESTED_BY}))
        text = page(self.ops.get(response['Location']))
        self.assertIn('The workspace was created. Add its people below.', text)
        self.assertIn('Neurosurgery', text)
        added = self.ops.post('/ops/people/add', {'workspace': str(created.pk), 'back': str(created.pk),
                                                  'username': 'spine-owner', 'role': 'owner'})
        password = shown_password(added)
        doctor = Client()
        self.assertEqual(doctor.post('/login/', {'username': 'spine-owner', 'password': password}).status_code, 302)
        listing = doctor.get('/api/encounters')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['encounters'], [])
        self.assertEqual(doctor.get('/api/session').json()['workspace']['name'], 'Spine Partners')

    def test_creating_a_workspace_refuses_and_records_nothing(self):
        before = self.counts()
        for body, status in (({'name': '', 'category': str(self.neuro.pk)}, 400),
                             ({'name': 'No specialty'}, 400), ({'name': 'Bad', 'category': UUID}, 400),
                             ({'name': 'gastroenterology', 'category': str(self.neuro.pk)}, 409),
                             ({'name': 'x' * 121, 'category': str(self.neuro.pk)}, 400),
                             ({'name': 'Nul\x00name', 'category': str(self.neuro.pk)}, 400)):
            with self.subTest(body=body):
                self.assertEqual(self.ops.post('/ops/workspaces/new', body).status_code, status)
        self.assertEqual(self.counts(), before)

    def test_a_workspace_page_lists_only_its_people_and_answers_404_for_an_unknown_one(self):
        text = page(self.ops.get(f'/ops/workspaces/{self.ws.pk}'))
        self.assertIn(self.reviewer.username, text)
        self.assertNotIn(self.outsider.username, text)
        self.assertEqual(self.ops.get(f'/ops/workspaces/{UUID}').status_code, 404)


class SpendingTests(AdminCase):
    def test_the_figures_are_the_consoles_own_pricing_summed_by_day_workspace_and_document(self):
        first = self.done(title='Priced note one')
        second = self.done(title='Priced note two')
        runs = list(Run.objects.filter(purpose__in=jobs.PURPOSES, sent=True))
        self.assertGreaterEqual(len(runs), 4)
        expected = sum((jobs.run_cost(run) for run in runs), Decimal(0))
        # an unpriceable sent run is counted apart with its reserved worst case; an unsent run is not counted
        odd = runs[0]
        Run.objects.filter(pk=odd.pk).update(usage={}, scope={**odd.scope, 'worst_usd': '1.25'})
        Run.objects.filter(pk=runs[1].pk).update(sent=False)
        expected -= jobs.run_cost(odd) + jobs.run_cost(runs[1])
        figures = console.spending()
        self.assertEqual(figures['total']['cost'], expected)
        self.assertEqual(figures['total']['runs'], len(runs) - 1)
        self.assertEqual(figures['total']['unpriced'], 1)
        self.assertEqual(figures['total']['worst'], Decimal('1.25'))
        self.assertEqual(figures['recent']['cost'], expected)
        self.assertEqual(sum(row['cost'] for row in figures['days']), expected)
        self.assertEqual([row['workspace'].pk for row in figures['workspaces']], [self.ws.pk])
        self.assertEqual(figures['workspaces'][0]['documents'], 2)
        self.assertEqual({row['encounter'].pk for row in figures['documents']}, {first.pk, second.pk})
        self.assertEqual(sum(row['cost'] for row in figures['documents']), expected)
        text = page(self.ops.get('/ops/spending'))
        self.assertIn(console.dollars(expected), text)
        self.assertIn(str(first.pk)[:8], text)  # release 1, C2: a document by its short reference, never its title
        self.assertNotIn('Priced note', text)
        self.assertIn('whose cost is not known', text)
        shown = models.AccessRecord.objects.get(view='ops.spending')  # C1: the documents shown
        self.assertEqual((set(shown.encounter_ids), shown.count), ({str(first.pk), str(second.pk)}, 2))

    def test_a_run_older_than_the_window_counts_in_the_total_only(self):
        self.done(title='Old note')
        runs = Run.objects.filter(purpose__in=jobs.PURPOSES, sent=True)
        old_day = timezone.now() - timedelta(days=45)
        runs.update(created_at=old_day, started_at=old_day)
        figures = console.spending()
        self.assertGreater(figures['total']['cost'], 0)
        self.assertEqual(figures['recent']['runs'], 0)
        self.assertEqual(figures['days'], [])

    def test_an_empty_installation(self):
        text = page(self.ops.get('/ops/spending'))
        self.assertIn('No coding run yet.', text)
        self.assertIn('$0.00', text)
        self.assertIn(console.dollars(Decimal(settings.DOCUMENT_CEILING_USD)), text)


class ActivityTests(AdminCase):
    def test_every_event_newest_first_in_plain_words_with_filters_and_pages(self):
        enc = self.done(title='Activity note')
        self.ops.post('/ops/people/add', {'workspace': str(self.other_ws.pk), 'username': 'other-viewer', 'role': 'viewer'})
        text = page(self.ops.get('/ops/activity'))
        for words in ('Document added', 'Coding review finished', 'Person added', str(enc.pk)[:8], 'Another practice'):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertNotIn('Activity note', text)  # release 1, C2: the document by its short reference, never its title
        self.assertLess(text.index('Person added'), text.index('Document added'))  # newest first
        only_other = page(self.ops.get(f'/ops/activity?workspace={self.other_ws.pk}'))
        self.assertIn('Person added', only_other)
        self.assertNotIn(str(enc.pk)[:8], only_other)
        read = models.AccessRecord.objects.filter(view='ops.activity').order_by('created_at')
        self.assertIn(str(enc.pk), read.first().encounter_ids)  # C1: the documents its rows named
        self.assertEqual(read.last().filters, {'workspace': str(self.other_ws.pk), 'kind': None, 'before': None})
        self.assertEqual(read.last().workspace_id, self.other_ws.pk)
        decisions = page(self.ops.get('/ops/activity?kind=operator'))
        self.assertIn('Person added', decisions)
        self.assertNotIn('Document added', decisions)
        self.assertEqual(self.ops.get('/ops/activity?kind=nonsense&page=x').status_code, 200)
        # pages of 100
        for number in range(console.PAGE_SIZE + 5):
            models.AuditEvent.objects.create(workspace=self.ws, encounter=enc, event='export.created',
                                             actor_kind='human', data={'kind': 'draft', 'fmt': 'pdf', 'number': 1})
        first = page(self.ops.get('/ops/activity'))
        self.assertIn('Older &rarr;', first)
        self.assertNotIn('&larr; Newest', first)
        older = re.search(r'href="\?before=([^"]+)">Older', first).group(1)
        second = page(self.ops.get(f'/ops/activity?before={older}'))
        self.assertIn('&larr; Newest', second)

    def test_sign_ins_with_their_result(self):
        Client().post('/login/', {'username': self.reviewer.username, 'password': 'wrong-password-123'})
        Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        text = page(self.ops.get('/ops/activity/sign-ins'))
        self.assertIn('Signed in', text)
        self.assertIn('Refused', text)
        self.assertIn(self.reviewer.username, text)
        failed = page(self.ops.get('/ops/activity/sign-ins?result=failed'))
        self.assertEqual(failed.count('chip bad">Refused'), 1)
        self.assertNotIn('chip ok">Signed in', failed)


class LookTests(AdminCase):
    def test_every_console_page_uses_only_the_sites_own_fonts_and_the_shared_navigation(self):
        enc = self.done(title='Look note')
        for url in ('/ops/', f'/ops/encounters/{enc.pk}', '/ops/people', '/ops/workspaces', f'/ops/workspaces/{self.ws.pk}',
                    '/ops/spending', '/ops/activity', '/ops/activity/sign-ins'):
            with self.subTest(url=url):
                text = page(self.ops.get(url))
                self.assertIn('CPT Studio · Operator console', text)
                self.assertIn('<nav class="topnav" aria-label="Console">', text)
                self.assertIn('action="/logout/"', text)
                self.assertEqual(re.findall(r'url\("([^"]+)"\)', text),
                                 ['/static/studio/fonts/Manrope-Regular.ttf', '/static/studio/fonts/Manrope-SemiBold.ttf',
                                  '/static/studio/fonts/IBMPlexMono-Regular.ttf', '/static/studio/fonts/IBMPlexMono-Medium.ttf'])
                self.assertNotRegex(text, r'https?://(?!www\.w3\.org)')
                self.assertEqual(text.count(' aria-current="page">'), 1 if 'activity' not in url else 2)

    def test_the_served_fonts_are_the_vendored_report_fonts(self):
        root = Path(settings.BASE_DIR) / 'studio'
        for name in ('Manrope-Regular.ttf', 'Manrope-SemiBold.ttf', 'IBMPlexMono-Regular.ttf', 'IBMPlexMono-Medium.ttf',
                     'OFL-Manrope.txt', 'OFL-IBMPlexMono.txt'):
            with self.subTest(name=name):
                self.assertEqual((root / 'static/studio/fonts' / name).read_bytes(),
                                 (root / 'report_fonts' / name).read_bytes())

    def test_signing_out_from_the_console(self):
        response = self.ops.post('/logout/')
        self.assertEqual((response.status_code, response['Location']), (302, '/login/'))
        # signed out on the console's own host: the operator sign-in, and back to the page (D396; release 1, B3)
        self.assertEqual(self.ops.get('/ops/people')['Location'], '/login/?next=%2Fops%2Fpeople')


class PasswordTests(TestCase):
    def test_generated_passwords_pass_the_validators_and_differ(self):
        user = User(username='synthetic-check')
        seen = {console.new_password(user) for _ in range(50)}
        self.assertEqual(len(seen), 50)
        for value in seen:
            self.assertRegex(value, r'^[abcdefghjkmnpqrstuvwxyz23456789]{5}(-[abcdefghjkmnpqrstuvwxyz23456789]{5}){3}$')


class RefutationRoundOneTests(AdminCase):
    """The repairs of refutation round 1 (DECISIONS D395), each pinned by the input that broke it."""

    def test_a_name_that_is_no_account_is_never_shown_on_the_sign_ins(self):
        # a person types their password into the username box (data-3, restyle-2)
        Client().post('/login/', {'username': 'jrtmn-jutfn-etn9r-2m4ay', 'password': 'whatever-123'})
        Client().post('/login/', {'username': self.viewer.username, 'password': 'wrong-password-123'})
        text = page(self.ops.get('/ops/activity/sign-ins'))
        self.assertNotIn('jrtmn-jutfn-etn9r-2m4ay', text)
        self.assertIn('a name that is no account', text)
        self.assertIn(self.viewer.username, text)

    def test_spending_counts_a_run_in_flight_or_of_unknown_outcome_at_its_worst_case(self):
        self.done(title='Settled note')
        runs = list(Run.objects.filter(purpose__in=jobs.PURPOSES).order_by('created_at', 'pk'))
        settled = sum((jobs.run_cost(run) for run in runs[2:]), Decimal(0))
        # a send in flight (not yet marked sent), and a run of unknown outcome holding partial usage (money-2, money-5)
        Run.objects.filter(pk=runs[0].pk).update(state=Run.SENDING, sent=False, scope={**runs[0].scope, 'worst_usd': '8.5'})
        Run.objects.filter(pk=runs[1].pk).update(state=Run.UNKNOWN, scope={**runs[1].scope, 'worst_usd': '2.25'})
        figures = console.spending()
        self.assertEqual(figures['total']['unpriced'], 2)
        self.assertEqual(figures['total']['worst'], Decimal('10.75'))
        self.assertEqual(figures['total']['cost'], settled)
        self.assertIn('2 of them not priced', page(self.ops.get('/ops/spending')))

    def test_spending_reads_a_missing_or_unreadable_worst_case_as_the_ceiling_and_never_breaks(self):
        self.done(title='Odd figures')
        runs = list(Run.objects.filter(purpose__in=jobs.PURPOSES).order_by('created_at', 'pk'))
        ceiling = jobs.ceiling_usd()
        for value in (None, 'NaN', '-1', 'Infinity', 'not a number'):
            with self.subTest(worst=value):
                scope = {key: item for key, item in runs[0].scope.items() if key != 'worst_usd'}
                if value is not None:
                    scope['worst_usd'] = value
                Run.objects.filter(pk=runs[0].pk).update(state=Run.UNKNOWN, scope=scope)
                self.assertEqual(console.spending()['total']['worst'], ceiling)
        Run.objects.filter(pk=runs[0].pk).update(state=Run.UNKNOWN, scope={**runs[0].scope, 'worst_usd': '1e40'})
        response = self.ops.get('/ops/spending')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(console.dollars(Decimal('1e90')), '1.000E+90')
        self.assertEqual(console.dollars(Decimal('NaN')), 'not known')

    def test_spending_counts_nothing_for_a_cancelled_run_or_one_refused_before_answering(self):
        self.done(title='Refused note')
        runs = list(Run.objects.filter(purpose__in=jobs.PURPOSES).order_by('created_at', 'pk'))
        Run.objects.filter(pk=runs[0].pk).update(state=Run.CANCELLED)
        Run.objects.filter(pk=runs[1].pk).update(state=Run.FAILED, http_status=429, usage={})
        figures = console.spending()
        self.assertEqual((figures['total']['cost'], figures['total']['unpriced'], figures['total']['runs']),
                         (Decimal(0), 0, 2))

    def test_the_costliest_documents_put_an_unknown_run_by_its_worst_case(self):
        known = self.done(title='Known cost')
        unknown = self.done(title='Unknown cost')
        run = Run.objects.filter(encounter=unknown, purpose=jobs.READER).get()
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, scope={**run.scope, 'worst_usd': '20'})
        order = [row['encounter'].pk for row in console.spending()['documents']]
        self.assertEqual(order, [unknown.pk, known.pk])

    def test_an_event_whose_data_holds_no_plain_value_is_shown_and_never_breaks_the_log(self):
        enc = self.done(title='Odd event')
        models.AuditEvent.objects.create(workspace=self.ws, encounter=enc, event='decision.recorded', actor_kind='human',
                                         data={'action': ['approve'], 'code': {'x': 1}, 'line': 'L1'})
        for url in ('/ops/activity', '/ops/activity?kind=decisions', f'/ops/activity?workspace={self.ws.pk}'):
            with self.subTest(url=url):
                response = self.ops.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('Decision recorded', page(response))

    def test_the_log_pages_by_position_so_a_new_row_never_repeats_or_hides_one(self):
        enc = self.done(title='Paged note')
        moment = timezone.now() - timedelta(minutes=5)
        # 150 rows at one moment (audit rows are append-only, so they are made at it): the page edge falls inside a tie
        with mock.patch.object(timezone, 'now', return_value=moment):
            for _ in range(150):
                models.AuditEvent.objects.create(workspace=self.ws, encounter=enc, event='export.created',
                                                 actor_kind='human', data={'number': 1})
        first = page(self.ops.get('/ops/activity?kind=downloads'))
        older = re.search(r'href="\?kind=downloads&amp;before=([^"]+)">Older', first).group(1)
        # rows arriving between the two reads (newer than everything shown) change nothing on the older page
        for _ in range(30):
            models.AuditEvent.objects.create(workspace=self.ws, encounter=enc, event='export.created', actor_kind='human',
                                             data={'number': 2})
        second = page(self.ops.get(f'/ops/activity?kind=downloads&before={older}'))
        shown_first = first.count('Report made<br>')
        shown_second = second.count('Report made<br>')
        self.assertEqual((shown_first, shown_second), (100, 50))
        self.assertNotIn('Older &rarr;', second)
        bad = self.ops.get('/ops/activity?before=nonsense')
        self.assertEqual(bad.status_code, 200)
        self.assertIn('That page address could not be read', page(bad))

    def test_workspace_names_follow_provisionings_rules_and_never_read_alike(self):
        gi = self.ws.category
        cases = [('​Spine', 400), ('Spine‮Partners', 400), ('---', 400),
                 ('neurosurgery', 409),                    # names another specialty, for this one
                 ('Gastro-enterology', 409),               # reads like the workspace "Gastroenterology"
                 ('GASTROENTEROLOGY', 409)]
        before = self.counts()
        for name, status in cases:
            with self.subTest(name=name):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(gi.pk)})
                self.assertEqual(response.status_code, status)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': '  Valley   Endoscopy  ', 'category': str(gi.pk)})
                         .status_code, 400)  # stored exactly as typed: no stray spaces (r6-4)
        made = self.ops.post('/ops/workspaces/new', {'name': 'Valley Endoscopy', 'category': str(gi.pk)})
        self.assertEqual(made.status_code, 303)
        self.assertTrue(Workspace.objects.filter(name='Valley Endoscopy').exists())
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'valley-endoscopy', 'category': str(self.neuro.pk)})
                         .status_code, 409)

    def test_adding_and_creating_take_provisionings_lock(self):
        for url, body in (('/ops/workspaces/new', {'name': 'Locked Practice', 'category': str(self.neuro.pk)}),
                          ('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'locked-person', 'role': 'viewer'})):
            with self.subTest(url=url), CaptureQueriesContext(connection) as seen:
                self.assertIn(self.ops.post(url, body).status_code, (200, 303))
            self.assertTrue(any('pg_advisory_xact_lock' in item['sql'] for item in seen.captured_queries))

    def test_an_automated_agent_is_never_made_an_owner(self):
        member = self.membership(self.agent)
        response = self.ops.post(f'/ops/people/{self.agent.pk}/role', {'membership': str(member.pk), 'role': 'owner'})
        self.assertEqual(response.status_code, 400)
        self.assertIn(console.AGENT_OWNER, page(response))
        member.refresh_from_db()
        self.assertEqual(member.role, 'reviewer')
        text = page(self.ops.get(f'/ops/workspaces/{self.ws.pk}'))
        agent_form = text[text.index(f'/ops/people/{self.agent.pk}/role'):]
        agent_form = agent_form[:agent_form.index('</select>')]
        self.assertNotIn('value="owner"', agent_form)

    def test_a_refusal_marks_the_page_it_answers_in_the_navigation(self):
        held = self.ops.post('/ops/holds/release', {'note': 'Nothing stands, so this is refused.'})
        self.assertEqual((held.status_code, held['Location']), (303, '/ops/?error=no-hold'))  # release 1, C1
        self.assertIn('<a href="/ops/" aria-current="page">Encounters</a>', page(self.ops.get(held['Location'])))
        back = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'back': str(self.ws.pk), 'username': 'X',
                                                 'role': 'viewer'})
        self.assertIn('<a href="/ops/workspaces" aria-current="page">Workspaces</a>', page(back))

    def test_the_password_page_logs_nothing_that_holds_the_password(self):
        import logging
        with self.assertLogs('django.template', level='DEBUG') as captured:
            logging.getLogger('django.template').debug('marker')
            response = self.ops.post(f'/ops/people/{self.viewer.pk}/password', {})
        password = shown_password(response)
        self.assertFalse([line for line in captured.output if password in line])

    def test_the_fonts_provenance_note_is_not_served(self):
        root = Path(settings.BASE_DIR) / 'studio'
        self.assertEqual(sorted(path.name for path in (root / 'static/studio/fonts').iterdir()),
                         ['IBMPlexMono-Medium.ttf', 'IBMPlexMono-Regular.ttf', 'Manrope-Regular.ttf', 'Manrope-SemiBold.ttf',
                          'OFL-IBMPlexMono.txt', 'OFL-Manrope.txt'])
        self.assertIn('The copies the operator console serves', (root / 'report_fonts/PROVENANCE.md').read_text())


class RefutationRoundTwoTests(AdminCase):
    """The repairs of refutation round 2 (DECISIONS D395), each pinned by the input that broke it."""

    def test_one_cost_reading_on_every_console_page_held_to_the_ceilings_reading(self):
        from studio import operator, spend
        enc = self.done(title='One reading')
        runs = list(Run.objects.filter(encounter=enc).order_by('created_at', 'pk'))
        base = runs[0]
        live = 'https://api.anthropic.example/v1/messages'
        cases = [(Run.SUCCEEDED, True, 200, base.usage, '0.5', live), (Run.SUCCEEDED, True, 200, {}, '0.5', live),
                 (Run.SUCCEEDED, False, None, {}, '0.5', live), (Run.FAILED, True, 429, {}, '0.5', live),
                 (Run.FAILED, True, 200, base.usage, '0.5', live), (Run.FAILED, True, 500, {'input_tokens': 'x'}, '0.5', live),
                 (Run.UNKNOWN, True, None, base.usage, '0.5', live), (Run.SENDING, False, None, {}, '0.5', live),
                 (Run.NOT_SENT, False, None, {}, '0.5', live), (Run.CANCELLED, True, None, base.usage, '0.5', live),
                 (Run.UNKNOWN, True, None, {}, None, live), (Run.RESERVED, False, None, {}, '0.5', live),
                 # a replay calls nothing: its worst case is 0, and a sweep may leave it unknown or sending (r3-4)
                 (Run.UNKNOWN, False, None, base.usage, '0.000000', ''), (Run.SENDING, False, None, {}, '0.000000', ''),
                 (Run.SUCCEEDED, False, None, base.usage, '0.000000', '')]
        for state, sent, status, usage, worst, endpoint in cases:
            with self.subTest(state=state, sent=sent, status=status, usage=bool(usage), worst=worst, endpoint=bool(endpoint)):
                scope = {key: item for key, item in base.scope.items() if key != 'worst_usd'}
                if worst is not None:
                    scope['worst_usd'] = worst
                Run.objects.filter(pk=base.pk).update(state=state, sent=sent, http_status=status, usage=usage, scope=scope,
                                                      endpoint=endpoint)
                run = Run.objects.get(pk=base.pk)
                cost, worst_case = spend.run_spend(run)
                self.assertEqual(cost if cost is not None else worst_case, jobs._held_cost(run))
        # the encounter's round total and the Spending page agree on an unknown run: counted apart, not as its partial cost
        Run.objects.filter(pk=base.pk).update(state=Run.UNKNOWN, sent=True, usage=base.usage, scope=base.scope,
                                              endpoint='https://api.anthropic.example/v1/messages')
        round_cost, unpriced = operator.runs_cost(list(Run.objects.filter(encounter=enc)))
        figures = console.spending()
        self.assertEqual(unpriced, 1)
        self.assertEqual(Decimal(round_cost), figures['total']['cost'])
        self.assertEqual(figures['total']['unpriced'], 1)

    def test_absurd_stored_figures_never_break_the_spending_page(self):
        enc = self.done(title='Absurd figures')
        runs = list(Run.objects.filter(encounter=enc).order_by('created_at', 'pk'))
        for index, run in enumerate(runs[:2]):
            Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, scope={**run.scope, 'worst_usd': '9e999999'})
        response = self.ops.get('/ops/spending')
        self.assertEqual(response.status_code, 200)
        self.assertIn('not known', page(response))

    def test_each_row_shows_the_worst_case_that_places_it(self):
        enc = self.done(title='Worst case shown')
        run = Run.objects.filter(encounter=enc, purpose=jobs.READER).get()
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, scope={**run.scope, 'worst_usd': '20'})
        text = page(self.ops.get('/ops/spending'))
        self.assertIn('1, up to $20.00 more', text)

    def test_the_encounter_page_and_its_refusals_look_no_notice_up(self):
        import logging
        enc = self.done(title='Lookups')
        with self.assertLogs('django.template', level='DEBUG') as captured:
            logging.getLogger('django.template').debug('marker')
            self.ops.get(f'/ops/encounters/{enc.pk}')
            self.ops.post(f'/ops/encounters/{enc.pk}/retry', {})
            self.ops.get('/ops/people')
        self.assertFalse([line for line in captured.output if 'Failed lookup' in line], captured.output)

    def test_turning_access_on_ends_a_session_made_while_it_was_off(self):
        from importlib import import_module
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'scope': 'everywhere'})
        # a sign-in that raced the off act leaves a session written after the act's scan (r2, secure-1)
        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store['_auth_user_id'] = str(self.reviewer.pk)
        store['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        store['_auth_user_hash'] = self.reviewer.get_session_auth_hash()
        store.create()
        self.assertEqual(self.sessions_of(self.reviewer), 1)
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'on', 'scope': 'everywhere'})
        self.assertEqual(self.sessions_of(self.reviewer), 0)
        self.assertEqual(models.AuditEvent.objects.get(event='operator.access_on').data['sessions_ended'], 1)
        replay = Client()
        replay.cookies[settings.SESSION_COOKIE_NAME] = store.session_key
        self.assertNotEqual(replay.get('/api/session').status_code, 200)

    def test_an_expired_session_is_not_counted_or_read(self):
        from importlib import import_module
        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store['_auth_user_id'] = str(self.reviewer.pk)
        store.create()
        Session.objects.filter(session_key=store.session_key).update(expire_date=timezone.now() - timedelta(days=1))
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'scope': 'everywhere'})
        self.assertEqual(models.AuditEvent.objects.get(event='operator.access_off').data['sessions_ended'], 0)

    def test_a_session_store_the_console_cannot_end_refuses_the_acts(self):
        self.assertIn(settings.SESSION_ENGINE, console.SESSION_STORES)  # the deployed setting: Django's database store
        with self.settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies'):
            with self.assertRaises(console.Refused) as refused:
                console.end_sessions(self.viewer)
        self.assertEqual((str(refused.exception), refused.exception.status), (console.NO_SESSION_STORE, 409))
        # an act whose sessions cannot be ended changes nothing at all (the refusal comes inside its transaction)
        before = self.counts()
        with mock.patch.object(console, 'end_sessions', side_effect=console.Refused(console.NO_SESSION_STORE, 409)):
            for url, body in ((f'/ops/people/{self.viewer.pk}/access',
                               {'access': 'off', 'membership': str(self.membership(self.viewer).pk)}),
                              (f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'scope': 'everywhere'}),
                              (f'/ops/people/{self.viewer.pk}/password', {})):
                with self.subTest(url=url):
                    response = self.ops.post(url, body)
                    self.assertEqual(response.status_code, 409)
                    self.assertIn(console.NO_SESSION_STORE, page(response))
                    self.assertNotIn('class="secret"', page(response))
        self.assertEqual(self.counts(), before)

    def test_unicode_spellings_of_one_name_read_alike(self):
        gi = self.ws.category
        Workspace.objects.create(name='Caf\u00e9 Partners', category=gi)
        before = self.counts()
        # a spelling that reads alike is refused as the existing name; one not stored exactly as typed, or outside the
        # name's characters, is refused outright (r5-2, r6)
        for name, status in (('caf\u00e9-partners', 409), ('CAF\u00c9 PARTNERS', 409), ('Cafe Partners', 409),
                             ('Cafe\u0301 Partners', 400),
                             ('\uff23\uff21\uff26\uff25\u0301 Partners', 400), ('\uff23af\u00e9 partners', 400),
                             ('\uff4e\uff45\uff55\uff52\uff4f\uff53\uff55\uff52\uff47\uff45\uff52\uff59', 400)):
            with self.subTest(name=name):
                self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(gi.pk)}).status_code,
                                 status)
        self.assertEqual(self.counts(), before)
        made = self.ops.post('/ops/workspaces/new', {'name': 'Valley Clinic', 'category': str(gi.pk)})
        self.assertEqual(made.status_code, 303)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'valley clinic', 'category': str(gi.pk)})
                         .status_code, 409)  # read alike
        accented = self.ops.post('/ops/workspaces/new', {'name': 'R\u00e9sum\u00e9 Health', 'category': str(gi.pk)})
        self.assertEqual(accented.status_code, 303)

    def test_fillers_and_other_ignorable_characters_are_refused_in_names(self):
        for name in ('\u3164', 'Spine\u3164Center', '\u115fNorth', 'Spine\u034fCenter', '\ufe0fSpine', 'Spine \ufe0fX',
                     '\uffa0Clinic', 'Spine\u2800Center', '\u2800'):
            with self.subTest(name=repr(name)):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(self.neuro.pk)})
                self.assertEqual(response.status_code, 400)
            with self.subTest(person=repr(name)):
                response = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'filler-test',
                                                             'name': name, 'role': 'viewer'})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='filler-test').exists())


class RefutationRoundThreeTests(AdminCase):
    """The repairs of refutation round 3 (DECISIONS D395), each pinned by the input that broke it."""

    def test_an_encounter_rounds_cost_is_the_sum_of_its_cards_known_costs(self):
        enc = self.done(title='Cards and round')
        runs = list(Run.objects.filter(encounter=enc).order_by('created_at', 'pk'))
        live = 'https://api.anthropic.example/v1/messages'
        for changes in ({'state': Run.UNKNOWN, 'sent': True, 'endpoint': live},              # partial usage, no known cost
                        {'state': Run.FAILED, 'sent': True, 'http_status': 529, 'usage': {}, 'endpoint': live},  # refused
                        {'state': Run.SUCCEEDED, 'sent': False, 'endpoint': ''}):            # a replay
            with self.subTest(changes=changes):
                Run.objects.filter(pk=runs[0].pk).update(**changes)
                text = page(self.ops.get(f'/ops/encounters/{enc.pk}'))
                cells = re.findall(r'<tr><th>Cost \(USD, estimated\)</th><td class="mono">([^<]*)', text)
                round_cell, cards = cells[0], cells[1:]
                known = [Decimal(cell.split(' ')[0]) for cell in cards if not cell.startswith('not known yet')]
                unknown = sum(1 for cell in cards if cell.startswith('not known yet'))
                self.assertEqual(Decimal(round_cell.strip()), sum(known, Decimal(0)))
                self.assertEqual(text.count('run(s) with no known cost yet'), 1 if unknown else 0)

    def test_a_replay_left_unknown_by_a_sweep_costs_nothing_and_is_not_flagged(self):
        from studio import operator, spend
        enc = self.done(title='Replay swept')
        run = Run.objects.filter(encounter=enc, purpose=jobs.READER).get()
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, sent=False, endpoint='',
                                             scope={**run.scope, 'worst_usd': '0.000000'})
        self.assertEqual(spend.run_spend(Run.objects.get(pk=run.pk)), (Decimal(0), None))
        self.assertEqual(operator.runs_cost(list(Run.objects.filter(encounter=enc)))[1], 0)

    def test_only_the_database_session_store_is_accepted(self):
        self.assertEqual(console.SESSION_STORES, ('django.contrib.sessions.backends.db',))
        with self.settings(SESSION_ENGINE='django.contrib.sessions.backends.cached_db'):
            with self.assertRaises(console.Refused):
                console.end_sessions(self.viewer)

    def test_a_variation_selector_is_refused_everywhere(self):
        # one between a letter and its accent would make a second workspace drawn like the first (r4-1, r4-3)
        Workspace.objects.create(name='Caf\u00e9 Partners', category=self.ws.category)
        before = self.counts()
        for name in ('Cafe\ufe0f\u0301 Partners', 'Spine\ufe0f', 'Dr. Sun \u2600\ufe0f', '\u845b\U000e0100 Clinic'):
            with self.subTest(name=repr(name)):
                self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(self.ws.category.pk)})
                                 .status_code, 400)
                self.assertEqual(self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'selector-x',
                                                                   'name': name, 'role': 'viewer'}).status_code, 400)
        self.assertEqual(self.counts(), before)
        # a person's name keeps what was typed (NFC only): a compatibility character is not rewritten (r3-7)
        self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'kept-name', 'name': 'Dr. \u2160 Rivera',
                                          'role': 'viewer'})
        self.assertEqual(User.objects.get(username='kept-name').display_name, 'Dr. \u2160 Rivera')

    def test_names_alike_are_listed_by_the_consoles_own_reading(self):
        gi = self.ws.category
        Workspace.objects.create(name='\uff2d\uff45\uff52\uff49\uff44\uff49\uff41\uff4e', category=self.neuro)
        refused = self.ops.post('/ops/workspaces/new', {'name': 'Meridian', 'category': str(gi.pk)})
        self.assertEqual(refused.status_code, 409)
        self.assertIn('\uff2d\uff45\uff52\uff49\uff44\uff49\uff41\uff4e', page(refused))
        self.assertNotIn('this run is for', page(refused))

    def test_the_session_store_refusal_names_every_act_it_can_stop(self):
        self.assertIn('access cannot be changed', console.NO_SESSION_STORE)


class RefutationRoundFourTests(AdminCase):
    """The repairs of refutation round 4 (DECISIONS D395), each pinned by the input that broke it."""

    def test_a_sign_provisioning_drops_still_counts_for_the_specialty_rule(self):
        before = self.counts()
        # a trade mark sign is a compatibility character: refused, so it never hides a specialty's name (r4-2, r5-3)
        for name in ('Neurosurgery\u2122', 'NEUROSURGERY\u2122'):
            with self.subTest(name=name):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(self.ws.category.pk)})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Latin letters', page(response))
        # a sign is no letter of a workspace name: refused before any reading (r6)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'Orthopedic Surgery\u00ae',
                                                               'category': str(self.ws.category.pk)}).status_code, 400)
        self.assertEqual(self.counts(), before)

    def test_a_reserved_run_reads_nothing_sent_yet_on_its_card_and_is_not_flagged(self):
        enc = self.done(title='Reserved run')
        run = Run.objects.filter(encounter=enc, purpose=jobs.READER).get()
        Run.objects.filter(pk=run.pk).update(state=Run.RESERVED, sent=False,
                                             endpoint='https://api.anthropic.example/v1/messages')
        text = page(self.ops.get(f'/ops/encounters/{enc.pk}'))
        self.assertIn('nothing sent yet', text)
        self.assertNotIn('run(s) with no known cost yet', text)

    def test_spending_reads_every_run_in_one_query_whatever_is_in_flight(self):
        def queries_with(in_flight):
            enc = self.done(title=f'Flight {in_flight}')
            for run in list(Run.objects.filter(encounter=enc))[:in_flight]:
                Run.objects.filter(pk=run.pk).update(state=Run.SENDING, sent=False,
                                                     endpoint='https://api.anthropic.example/v1/messages')
            with CaptureQueriesContext(connection) as seen:
                console.spending()
            return len(seen.captured_queries)
        self.assertEqual(queries_with(0), queries_with(2))


class RefutationRoundFiveTests(AdminCase):
    """The repairs of refutation round 5 (DECISIONS D395), each pinned by the input that broke it."""

    def test_an_accent_typed_apart_from_a_latin_letter_is_refused(self):
        gi = self.ws.category
        Workspace.objects.create(name='\u00d8rsted Clinic', category=gi)
        before = self.counts()
        for name in ('O\u0338rsted Clinic', 'Cl\u0131\u0301nica Garc\u0131\u0301a', 'Ana\u0131\u0308s Clinic',
                     'Orthoped\u0131\u0307c Surgery', '\u0301Clinic', 'Spine \u0301Center', '\u03b1\u0338thens Clinic', 'Clinic 7\u0301'):
            with self.subTest(name=repr(name)):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(gi.pk)})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.counts(), before)

    def test_a_name_in_another_script_is_refused_a_written_limit(self):
        before = self.counts()
        for name in ('\u0928\u092e\u0938\u094d\u0924\u0947 Clinic', '\u0110akovo Health Centre', '\u0628\u064a\u0645\u0627\u0631\u0633\u062a\u0627\u0646',
                     '\u05d0 Clinic 12', 'Clinic \u1d0b', 'Neurosur\u0261ery'):
            with self.subTest(name=repr(name)):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(self.ws.category.pk)})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Latin letters', page(response))
        self.assertEqual(self.counts(), before)
        made = self.ops.post('/ops/workspaces/new', {'name': "St. Mary's & St. Luke's Gastro-Care (North) 24/7",
                                                      'category': str(self.ws.category.pk)})
        self.assertEqual(made.status_code, 303)

    def test_a_stored_workspace_name_is_exactly_what_was_typed(self):
        typed = 'Riverside Gastro\u00e9nterologie'
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(self.ws.category.pk)})
                         .status_code, 303)
        # what provisioning would look up (the exact text) is what the console stored (r5-2, r6-4)
        self.assertTrue(Workspace.objects.filter(name=typed).exists())

    def test_the_specialty_rule_judges_the_stored_name(self):
        made = self.ops.post('/ops/workspaces/new', {'name': 'NeurosurgeryTM Partners', 'category': str(self.ws.category.pk)})
        self.assertEqual(made.status_code, 303)


class RefutationRoundSixTests(AdminCase):
    """The repairs of refutation round 6 (DECISIONS D395), each pinned by the input that broke it."""

    def test_a_workspace_name_is_refused_unless_stored_exactly_as_typed(self):
        before = self.counts()
        for typed in ('Riverside   Clinic', ' Riverside Clinic', 'Riverside Clinic ', 'Riverside\u00a0Clinic',
                      'Riverside\u3000Clinic', 'Riverside\tClinic', 'Re\u0301sume\u0301 Health'):
            with self.subTest(typed=repr(typed)):
                response = self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(self.ws.category.pk)})
                self.assertEqual(response.status_code, 400)
                self.assertIn('single spaces between words', page(response))
        self.assertEqual(self.counts(), before)

    def test_names_are_compared_with_case_and_accents_aside(self):
        gi = str(self.ws.category.pk)
        Workspace.objects.create(name='Caf\u00e9 Partners', category=self.ws.category)
        before = self.counts()
        for name in ('Cafe Partners', 'CAFE PARTNERS', 'Caf\u00e8 Partners'):
            with self.subTest(name=name):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': gi})
                self.assertEqual(response.status_code, 409)
                self.assertIn('A workspace with that name exists', page(response))
        for name in ('Orthop\u00e9dic Surgery', 'NEUROSURG\u00c9RY'):
            with self.subTest(name=name):
                response = self.ops.post('/ops/workspaces/new', {'name': name, 'category': gi})
                self.assertEqual(response.status_code, 409)
                self.assertIn('names the', page(response))
        self.assertEqual(self.counts(), before)

    def test_a_name_provisioning_stored_is_read_the_same_way(self):
        gi = self.ws.category
        for stored, typed in (('O\u0338rsted Clinic', '\u00d8rsted Clinic'),
                              ('Cl\u0131\u0301nica Garc\u0131\u0301a', 'Cl\u00ednica Garc\u00eda'),
                              ('\u0110akovo Health Centre', '\u00d0akovo Health Centre'),
                              ('Spine \u1d04enter', 'Spine Center')):
            with self.subTest(stored=repr(stored)):
                Workspace.objects.create(name=stored, category=gi)  # as provisioning stores a name: exactly as given
                response = self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(gi.pk)})
                self.assertEqual(response.status_code, 409)
                self.assertIn('A workspace with that name exists', page(response))

    def test_every_allowed_character_reads_as_a_plain_letter_or_digit_or_nothing(self):
        allowed = [chr(point) for point in range(0x110000) if console.name_character_allowed(chr(point))]
        self.assertEqual(len(allowed), 62 + 11 + 62 + 11)  # ASCII letters and digits, the marks, Latin-1's letters, the rest
        for ch in allowed:
            reading = console.name_reading(ch)
            self.assertRegex(reading, r'^[a-z0-9]*$', repr(ch))
            self.assertEqual(bool(reading), ch.isalnum(), repr(ch))

    def test_a_typographic_apostrophe_is_a_plain_mark(self):
        gi = str(self.ws.category.pk)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'St. Mary\u2019s Clinic', 'category': gi})
                         .status_code, 303)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': "St. Mary's Clinic", 'category': gi})
                         .status_code, 409)


class RefutationRoundSevenTests(AdminCase):
    """The repairs of refutation round 7 (DECISIONS D395), each pinned by the input that broke it."""

    def test_a_modifier_letter_or_a_mark_in_a_stored_name_is_set_aside(self):
        gi = self.ws.category
        for stored, typed in (('St. Mary\u02bcs Clinic', 'St. Mary\u2019s Clinic'),
                              ('Hawai\u02bbi Gastro Partners', "Hawai'i Gastro Partners"),
                              ('South Cafe\u02ca Partners', 'South Cafe Partners'),
                              ('West Cafe\u02c9 Partners', 'West Cafe Partners'),
                              ('Upper Cafe\u0345 Partners', 'Upper Cafe Partners')):
            with self.subTest(stored=repr(stored)):
                Workspace.objects.create(name=stored, category=gi)  # as provisioning stores a name: exactly as given
                response = self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(gi.pk)})
                self.assertEqual(response.status_code, 409)
                self.assertIn('A workspace with that name exists', page(response))

    def test_the_characters_sentence_comes_before_the_spacing_sentence(self):
        before = self.counts()
        for typed in ('O\u0323\u0300yo\u0323\u0301 Specialist Hospital', '\u212aelvin Clinic', '\u212bngstr\u00f6m Clinic',
                      '\u09ac\u09c7\u09be Clinic', '\u05d1\u05bc\u05b8 Clinic', 'Hawai\u02bbi Partners'):
            with self.subTest(typed=repr(typed)):
                response = self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(self.ws.category.pk)})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Latin letters', page(response))
                self.assertNotIn('single spaces between words', page(response))
        self.assertEqual(self.counts(), before)

    def test_the_western_european_letters_are_accepted_in_both_cases(self):
        gi = str(self.ws.category.pk)
        for name in ('Clinique du Sacr\u00e9-C\u0153ur', 'A\u0178 CHAMPAGNE CLINIC', 'Meddygfa T\u0177 Gwyn',
                     '\u2018Ohana Clinic', '\u0160ibenik \u017dupa Clinic'):
            with self.subTest(name=name):
                self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': name, 'category': gi}).status_code, 303)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'Clinique du Sacre-Coeur', 'category': gi})
                         .status_code, 409)  # reads alike
        for point in range(0x110000):
            ch = chr(point)
            if console.name_character_allowed(ch) and ch.isalpha():
                for other in (ch.upper(), ch.lower()):
                    self.assertTrue(all(console.name_character_allowed(each) for each in other), repr(ch))

    def test_whatever_is_accepted_is_stored_exactly_as_typed_in_accepted_characters(self):
        rng = random.Random(20261123)
        pool = ['A', 'b', 'e', 'C', 'l', 'i', 'n', 'c', '\u00e9', ' ', ' ', '-', '\u2019', '\u0152', '\u0178', '\u0301',
                '\u00a0', '\u3000', '\t', '\u212a', '\u0131', '\u02bc', '\u0416', '\u0345', '\u0338']
        accepted = 0
        for number in range(400):
            typed = ''.join(rng.choice(pool) for _ in range(rng.randint(1, 7))) + f' W{number}'
            response = self.ops.post('/ops/workspaces/new', {'name': typed, 'category': str(self.ws.category.pk)})
            self.assertIn(response.status_code, (303, 400, 409), repr(typed))
            if response.status_code == 303:
                accepted += 1
                stored = Workspace.objects.get(pk=response['Location'].split('/ops/workspaces/')[1].split('?')[0]).name
                self.assertEqual(stored, typed)
                self.assertTrue(all(console.name_character_allowed(ch) for ch in stored), repr(stored))
        self.assertGreater(accepted, 25)


class StepUpTests(AdminCase):
    """Release 1, B2 step 5: every console act that changes who can see what asks for the key again when the session's
    second factor is older than SECOND_FACTOR_STEP_UP_SECONDS - the browser goes to the second-factor page with the form's
    page as next, and the act is not done (the form is never replayed)."""

    def acts(self):
        member = self.membership(self.viewer)
        return [
            ('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'step-up-person', 'role': 'viewer'}),
            (f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer'}),
            (f'/ops/people/{self.viewer.pk}/password', {}),
            (f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'membership': str(member.pk)}),
            (f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'scope': 'everywhere'}),
            ('/ops/workspaces/new', {'name': 'Step Up Partners', 'category': str(self.neuro.pk)}),
            (f'/ops/people/{self.viewer.pk}/unlock', {}),
        ]

    def test_an_act_six_minutes_after_the_key_goes_to_the_step_up_and_changes_nothing(self):
        later = timezone.now() + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS + 60)
        before = self.counts()
        with mock.patch.object(timezone, 'now', return_value=later):
            for url, body in self.acts():
                with self.subTest(url=url, body=body):
                    answer = self.ops.post(url, body, HTTP_REFERER='http://admin.quillmd.com/ops/people')
                    self.assertEqual((answer.status_code, answer['Location']),
                                     (303, '/login/second-factor?next=%2Fops%2Fpeople'))
            self.assertEqual(self.ops.get('/ops/people').status_code, 200)  # reading needs no step-up
        self.assertEqual(self.counts(), before)
        self.assertFalse(models.SecurityEvent.objects.filter(event='signin.cleared').exists())

    def test_within_five_minutes_of_the_key_the_act_is_done(self):
        within = timezone.now() + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS - 30)
        member = self.membership(self.viewer)
        with mock.patch.object(timezone, 'now', return_value=within):
            answer = self.ops.post(f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer'})
        self.assertEqual((answer.status_code, answer['Location']), (303, '/ops/people?done=role'))


class RequestedByTests(AdminCase):
    """Release 1, C3 item 5 (ADM-14 (7)): every act that changes access asks who at the practice requested it, refuses an
    empty answer, and stores it on the act's audit row."""

    def test_each_act_refuses_an_empty_requested_by_and_records_nothing(self):
        member = self.membership(self.viewer)
        acts = [('/ops/people/add', {'workspace': str(self.ws.pk), 'username': 'asked-person', 'role': 'viewer'}),
                (f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer'}),
                (f'/ops/people/{self.viewer.pk}/password', {}),
                (f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'membership': str(member.pk)}),
                (f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'scope': 'everywhere'}),
                ('/ops/workspaces/new', {'name': 'Asked Partners', 'category': str(self.neuro.pk)})]
        before = self.counts()
        for url, body in acts:
            for answer in ('', '   ', '​', '---'):
                with self.subTest(url=url, requested_by=answer):
                    response = self.ops.post(url, {**body, 'requested_by': answer})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('Requested by', page(response))
        self.assertEqual(self.counts(), before)

    def test_the_requested_by_is_stored_on_each_acts_audit_row(self):
        member = self.membership(self.viewer)
        self.ops.post(f'/ops/people/{self.viewer.pk}/role', {'membership': str(member.pk), 'role': 'reviewer',
                                                             'requested_by': 'Front desk, Dr. Lee\'s office'})
        self.ops.post(f'/ops/people/{self.viewer.pk}/password', {'requested_by': 'Ticket 77'})
        self.ops.post(f'/ops/people/{self.viewer.pk}/access', {'access': 'off', 'membership': str(member.pk),
                                                               'requested_by': 'Ticket 78'})
        rows = {event.event: event.data['requested_by'] for event in models.AuditEvent.objects.filter(
            event__startswith='operator.')}
        self.assertEqual(rows, {'operator.role_changed': 'Front desk, Dr. Lee\'s office',
                                'operator.password_reset': 'Ticket 77', 'operator.access_off': 'Ticket 78'})
        self.assertIn('requested_by Ticket 77', page(self.ops.get('/ops/activity')))


class PracticeAccessTests(AdminCase):
    """Release 1, C4 item 4: the console's switch is the membership's, this practice only, by default; "Turn off
    everywhere" (the account's is_active) stays apart."""

    def test_access_off_here_closes_this_workspace_only_and_ends_sessions_when_it_was_the_only_one(self):
        session = self.client_for(self.reviewer)
        member = self.membership(self.reviewer)
        response = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'membership': str(member.pk)})
        self.assertEqual((response.status_code, response['Location']), (303, '/ops/people?done=off'))
        member.refresh_from_db()
        self.reviewer.refresh_from_db()
        self.assertEqual((member.active, self.reviewer.is_active), (False, True))
        self.assertEqual(self.sessions_of(self.reviewer), 0)  # it was their only workspace
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        event = models.AuditEvent.objects.get(event='operator.access_off')
        self.assertEqual((event.workspace_id, event.data['scope'], event.data['membership'], event.data['sessions_ended']),
                         (self.ws.pk, 'practice', str(member.pk), 1))
        on = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'on', 'membership': str(member.pk)})
        self.assertEqual(on['Location'], '/ops/people?done=on')
        member.refresh_from_db()
        self.assertTrue(member.active)
        signed = Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(signed.status_code, 302)

    def test_a_person_in_two_practices_keeps_the_other_one_and_their_session(self):
        Membership.objects.create(user=self.reviewer, workspace=self.other_ws, role=Membership.VIEWER)
        session = self.client_for(self.reviewer)
        here = Membership.objects.get(user=self.reviewer, workspace=self.ws)
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off', 'membership': str(here.pk)})
        self.assertEqual(self.sessions_of(self.reviewer), 1)
        self.assertEqual(session.get('/api/session').json()['workspace']['id'], str(self.other_ws.pk))
        self.assertTrue(User.objects.get(pk=self.reviewer.pk).is_active)
        self.assertNotIn('sessions_ended', models.AuditEvent.objects.get(event='operator.access_off').data)

    def test_the_practice_switch_needs_one_of_the_persons_memberships(self):
        other = self.membership(self.outsider)
        before = self.counts()
        for body in ({'access': 'off'}, {'access': 'off', 'membership': str(other.pk)},
                     {'access': 'off', 'membership': 'x'}):
            with self.subTest(body=body):
                self.assertEqual(self.ops.post(f'/ops/people/{self.reviewer.pk}/access', body).status_code, 404)
        self.assertEqual(self.counts(), before)

    def test_the_people_page_offers_both_switches(self):
        text = page(self.ops.get('/ops/people'))
        self.assertIn('Turn access off in this workspace', text)
        self.assertIn('Turn off everywhere', text)
        self.assertIn('Clear sign-in delay', text)
        self.assertIn('No patient details.', text)


class UnlockTests(AdminCase):
    """Release 1, B1 step 8: Clear sign-in delay deletes the username's RateWindow rows (any scope) and writes a
    SecurityEvent; sign-in records are never deleted."""

    def test_clearing_a_delay_deletes_the_names_counters_and_records_it(self):
        from studio import rate
        key = console.signin_user_key(self.reviewer.username)
        self.assertEqual(key, rate.key_hash('signin-user:' + self.reviewer.username.casefold()))
        rate.hit('signin.failed.user', key, window_seconds=900)
        rate.hit('signin.refused.user', key, window_seconds=60)
        other_key = console.signin_user_key(self.viewer.username)
        rate.hit('signin.failed.user', other_key, window_seconds=900)
        rate.hit('signin.refused.client', '198.51.100.7', window_seconds=60)
        Client().post('/login/', {'username': self.reviewer.username, 'password': 'wrong-password-123'})
        attempts = models.LoginAttempt.objects.count()
        response = self.ops.post(f'/ops/people/{self.reviewer.pk}/unlock', {'back': str(self.ws.pk)})
        self.assertEqual((response.status_code, response['Location']), (303, f'/ops/workspaces/{self.ws.pk}?done=unlocked'))
        self.assertFalse(models.RateWindow.objects.filter(key=key).exists())
        self.assertEqual(models.RateWindow.objects.filter(key__in=[other_key, '198.51.100.7']).count(), 2)
        self.assertEqual(models.LoginAttempt.objects.count(), attempts)  # never deleted
        event = models.SecurityEvent.objects.get(event='signin.cleared')
        self.assertEqual((event.subject_id, event.actor_id, event.data), (self.reviewer.pk, self.operator_user.pk,
                                                                           {'rate_rows': 2}))
        self.assertEqual(models.AuditEvent.objects.get(event='operator.signin_cleared').data['count'], 2)
        self.assertIn('The sign-in delay was cleared.', page(self.ops.get(response['Location'])))

    def test_an_operators_account_is_cleared_on_the_server_only(self):
        other = r.f.user('second-operator')
        ops.grant(other)
        answer = self.ops.post(f'/ops/people/{other.pk}/unlock', {})
        self.assertEqual(answer.status_code, 409)
        self.assertFalse(models.SecurityEvent.objects.filter(event='signin.cleared').exists())


class OperatorsCardTests(AdminCase):
    """Release 1, C3 item 4 (ADM-8): the Operators card shows each grant's approval and review date, and flags the
    overdue ones and the grants with none for the periodic access review."""

    def test_each_grant_shows_its_approval_and_review_date_and_the_overdue_are_flagged(self):
        reviewed = r.f.user('reviewed-operator')
        models.OperatorGrant.objects.create(user=reviewed, reason='Synthetic grant.', granted_by='Synthetic Admin',
                                            authorization_ref='docs/foundation/rulings/synthetic-1.md',
                                            review_by=timezone.localdate() + timedelta(days=30))
        overdue = r.f.user('overdue-operator')
        models.OperatorGrant.objects.create(user=overdue, reason='Synthetic grant.', granted_by='Synthetic Admin',
                                            authorization_ref='docs/foundation/rulings/synthetic-2.md',
                                            review_by=timezone.localdate() - timedelta(days=1))
        agent = r.f.user('ops-agent')
        User.objects.filter(pk=agent.pk).update(actor_kind=User.AGENT)
        models.OperatorGrant.objects.create(user=agent, reason='Synthetic grant from before release 1.',
                                            granted_by='synthetic installer')
        rows = {row['person'].username: row for row in console.operator_rows()}
        self.assertEqual((rows['reviewed-operator']['overdue'], rows['reviewed-operator']['unreviewed']), (False, False))
        self.assertEqual(rows['overdue-operator']['overdue'], True)
        self.assertEqual((rows['ops-agent']['unreviewed'], rows['ops-agent']['automated']), (True, True))
        text = page(self.ops.get('/ops/people'))
        for fragment in ('docs/foundation/rulings/synthetic-1.md', 'overdue', 'none recorded',
                         'automated account: holds no operator power', 'by Synthetic Admin'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)


class SignInsPageTests(AdminCase):
    """Release 1, B1 steps 4 and 5: the Sign-ins page names each attempt's door and outcome, and how many attempts the
    throttle refused in the last hour (they reach no password check, so they are counted, not listed)."""

    def test_the_refused_count_and_the_outcomes(self):
        from studio import rate
        for _ in range(3):
            rate.hit(console.SIGNIN_REFUSED_SCOPE, '198.51.100.7', window_seconds=60)
        rate.hit(console.SIGNIN_REFUSED_SCOPE, '2001:db8:1:2::/64', window_seconds=60)
        old = rate.window_start(60, timezone.now() - timedelta(hours=2))
        models.RateWindow.objects.create(scope=console.SIGNIN_REFUSED_SCOPE, key='198.51.100.8', window_start=old,
                                         count=40, last_at=old)
        models.LoginAttempt.objects.create(username=self.reviewer.username, client='198.51.100.7', succeeded=False,
                                           door='admin', outcome=models.LoginAttempt.NO_ACCESS)
        self.assertEqual(console.refused_last_hour(), 4)
        text = page(self.ops.get('/ops/activity/sign-ins'))
        self.assertIn('4 attempts refused by the throttle in the last hour', text)
        self.assertIn('Right password, no access at this door', text)
        self.assertIn('<td>admin</td>', text)
        self.assertIn('Nobody is locked out.', text)


class ForcedChangeTests(AdminCase):
    """Release 1, B4 step 3: the console's add-person and reset start the clock of a staff-set password; each reset
    starts a new one."""

    def test_a_reset_starts_a_new_clock_and_the_page_says_so(self):
        first = timezone.now() - timedelta(hours=10)
        User.objects.filter(pk=self.viewer.pk).update(password_change_required_at=first)
        response = self.ops.post(f'/ops/people/{self.viewer.pk}/password', {})
        self.assertEqual(response.status_code, 200)
        self.viewer.refresh_from_db()
        self.assertGreater(self.viewer.password_change_required_at, first)
        self.assertIn('must choose a new password at the first sign-in, within 72 hours', page(response))
