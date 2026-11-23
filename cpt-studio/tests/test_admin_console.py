"""The operator console's controls (owner direction 2026-11-22, DECISIONS D395; studio.console): people and roles,
workspaces, spending and the activity log. The gate (every new URL answers what an unknown URL answers to anyone who is
not an operator, before anything is read or written), each act and its refusals, the one-time password (shown once, in
the POST's own answer, never stored, logged, audited or put in a URL), operator accounts left alone, nothing deleted,
the spending figures against the console's own pricing, and the read-only activity log. Synthetic data only."""
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


@override_settings(STORAGES=PLAIN_STATIC)
class AdminCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = r.f.member(self.ws, role=Membership.OWNER)
        self.operator_user = r.f.user('platform-operator')
        self.ops = ops.client(self.operator_user)
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
        for url in ('/ops/people', '/ops/workspaces', '/ops/spending', '/ops/activity'):
            with self.subTest(url=url):
                self.assertEqual(self.ops.get(url).status_code, 404)

    def test_the_acts_check_the_csrf_token_after_the_gate(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.operator_user)
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
        self.assertEqual(events[0].data, {'user': str(person.pk), 'username': 'dr.rivera', 'role': 'reviewer'})
        self.assertNotIn(password, repr([e.data for e in models.AuditEvent.objects.all()]))
        # the password is on this page only: the People page afterwards does not carry it
        self.assertNotIn(password, page(self.ops.get('/ops/people')))
        # the person signs in through the real sign-in page and lands in the doctor app's workspace
        doctor = Client()
        signed = doctor.post('/login/', {'username': 'dr.rivera', 'password': password})
        self.assertEqual(signed.status_code, 302)
        session = doctor.get('/api/session')
        self.assertEqual(session.status_code, 200)

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
                                      'from': 'viewer', 'to': 'reviewer'})
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

    def test_turning_access_off_stops_sign_in_and_ends_sessions_and_on_restores_it(self):
        session = self.client_for(self.reviewer)
        self.assertEqual(session.get('/api/session').status_code, 200)
        response = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off'})
        self.assertEqual((response.status_code, response['Location']), (303, '/ops/people?done=off'))
        self.reviewer.refresh_from_db()
        self.assertFalse(self.reviewer.is_active)
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        refused = Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(self.sessions_of(self.reviewer), 0)
        self.assertEqual(models.AuditEvent.objects.get(event='operator.access_off').data['sessions_ended'], 1)
        # nothing deleted: the account and its membership stay
        self.assertTrue(Membership.objects.filter(user=self.reviewer, active=True).exists())
        same = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off'})
        self.assertEqual(same['Location'], '/ops/people?done=same-access')
        back_on = self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'on'})
        self.assertEqual(back_on['Location'], '/ops/people?done=on')
        # the session opened before access was turned off never comes back: the person signs in again
        self.assertNotEqual(session.get('/api/session').status_code, 200)
        signed = Client().post('/login/', {'username': self.reviewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(signed.status_code, 302)
        self.assertEqual(list(models.AuditEvent.objects.filter(event__startswith='operator.access_')
                              .order_by('created_at', 'pk').values_list('event', flat=True)),
                         ['operator.access_off', 'operator.access_on'])
        self.assertEqual(self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'maybe'}).status_code, 400)

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
                                                                         'category': 'neurosurgery'}))
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
        self.assertIn('Priced note one', text)
        self.assertIn('whose cost is not known', text)

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
        for words in ('Document added', 'Coding review finished', 'Person added', 'Activity note', 'Another practice'):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertLess(text.index('Person added'), text.index('Document added'))  # newest first
        only_other = page(self.ops.get(f'/ops/activity?workspace={self.other_ws.pk}'))
        self.assertIn('Person added', only_other)
        self.assertNotIn('Activity note', only_other)
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
        self.assertEqual(self.ops.get('/ops/people').status_code, 404)


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
        made = self.ops.post('/ops/workspaces/new', {'name': '  Valley   Endoscopy  ', 'category': str(gi.pk)})
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
        self.assertEqual(held.status_code, 409)
        self.assertIn('<a href="/ops/" aria-current="page">Encounters</a>', page(held))
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
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off'})
        # a sign-in that raced the off act leaves a session written after the act's scan (r2, secure-1)
        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store['_auth_user_id'] = str(self.reviewer.pk)
        store['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        store['_auth_user_hash'] = self.reviewer.get_session_auth_hash()
        store.create()
        self.assertEqual(self.sessions_of(self.reviewer), 1)
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'on'})
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
        self.ops.post(f'/ops/people/{self.reviewer.pk}/access', {'access': 'off'})
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
            for url, body in ((f'/ops/people/{self.viewer.pk}/access', {'access': 'off'}),
                              (f'/ops/people/{self.viewer.pk}/password', {})):
                with self.subTest(url=url):
                    response = self.ops.post(url, body)
                    self.assertEqual(response.status_code, 409)
                    self.assertIn(console.NO_SESSION_STORE, page(response))
                    self.assertNotIn('class="secret"', page(response))
        self.assertEqual(self.counts(), before)

    def test_unicode_spellings_of_one_name_read_alike(self):
        gi = self.ws.category
        Workspace.objects.create(name='Café Partners', category=gi)
        before = self.counts()
        for name in ('Café Partners', 'ＣＡＦＥ́ Partners', 'Ｃafé partners', 'ｎｅｕｒｏｓｕｒｇｅｒｙ'):
            with self.subTest(name=name):
                self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(gi.pk)}).status_code, 409)
        self.assertEqual(self.counts(), before)
        made = self.ops.post('/ops/workspaces/new', {'name': 'Ｖａｌｌｅｙ Clinic', 'category': str(gi.pk)})
        self.assertEqual(made.status_code, 303)
        self.assertTrue(Workspace.objects.filter(name='Valley Clinic').exists())  # a workspace name is stored NFKC (r4-4)
        self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': 'valley clinic', 'category': str(gi.pk)})
                         .status_code, 409)  # read alike (NFKC caseless)
        decomposed = self.ops.post('/ops/workspaces/new', {'name': 'Re\u0301sume\u0301 Health', 'category': str(gi.pk)})
        self.assertEqual(decomposed.status_code, 303)
        self.assertTrue(Workspace.objects.filter(name='R\u00e9sum\u00e9 Health').exists())  # NFC composes it

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
        for name in ('Neurosurgery\u2122', 'Orthopedic Surgery\u00ae', 'NEUROSURGERY\u2122'):
            with self.subTest(name=name):
                self.assertEqual(self.ops.post('/ops/workspaces/new', {'name': name, 'category': str(self.ws.category.pk)})
                                 .status_code, 409)
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
