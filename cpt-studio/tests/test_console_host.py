"""The console only on admin.quillmd.com (release 1, B3; B2 step 4; C3): studio.operator.operator_view answers Django's
404 - exactly what an unknown URL answers - unless all three hold: the request is on the admin host, its session passed
the second factor at the admin door (studio.second_factor.satisfied), and its account is a person holding an operator
grant (studio.operator.is_operator). Every route of the full urlconf under ops/ is swept on cpt.quillmd.com for GET,
HEAD and POST with a valid CSRF token, by an operator whose valid admin-door session cookie was carried to that host.
Synthetic data only."""
from django.conf import settings
from django.test import Client, TestCase, override_settings

from cptstudio import urls as customer_urls
from studio import models, request_meta
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

ADMIN, CPT = settings.ADMIN_HOST, 'cpt.quillmd.com'
CONSOLE_ROUTES = [str(pattern.pattern) for pattern in customer_urls.urlpatterns
                  if str(pattern.pattern).startswith('ops/')]
UNKNOWN = '/opsx/no-such-console-page'
COUNTED = (models.User, models.Membership, models.Workspace, models.AuditEvent, models.AccessRecord,
           models.SecurityEvent, models.OperatorGrant, models.OperatorRevocation, models.CodingRound, models.Job,
           models.InterpreterHoldRelease, models.RateWindow, models.ExportArtifact)


def session_at(user, host, **markers):
    """A client for ``host`` signed in as ``user`` with exactly the session ``markers`` given (no grant is made)."""
    client = Client(HTTP_HOST=host)
    client.force_login(user)
    session = client.session
    session.update(markers)
    session.save()
    return client


@override_settings(STORAGES=PLAIN_STATIC)
class ConsoleHostCase(TestCase):
    def setUp(self):
        self.ws = f.workspace('Gastroenterology')
        self.member = f.member(self.ws, role=models.Membership.VIEWER)
        self.encounter = f.encounter(self.ws, self.member, title='ZZ-TITLE-MARKER synthetic note')
        f.paste(self.encounter, self.member)
        self.operator = f.user('platform-operator')
        ops.grant(self.operator)

    def concrete(self, route):
        ids = {'<uuid:encounter_id>': str(self.encounter.pk), '<uuid:user_id>': str(self.member.pk),
               '<uuid:workspace_id>': str(self.ws.pk)}
        for placeholder, value in ids.items():
            route = route.replace(placeholder, value)
        return '/' + route

    def fields(self, token):
        """What any console form posts - each act's own fields with valid values - and the CSRF token."""
        membership = models.Membership.objects.get(user=self.member)
        return {'csrfmiddlewaretoken': token, 'note': 'A synthetic note long enough for every act.', 'run': '',
                'membership': str(membership.pk), 'role': 'reviewer', 'access': 'off', 'scope': 'practice',
                'username': 'coverage-person', 'name': 'Coverage Person', 'workspace': str(self.ws.pk),
                'category': str(self.ws.category_id), 'requested_by': 'Synthetic ticket 1001',
                'reason': 'support_request', 'reference': 'SYNTHETIC-1001', 'back': ''}

    def with_token(self, client):
        """``client`` holding a CSRF cookie, and the token a form of the site would carry for it."""
        client.get('/login/', HTTP_HOST=CPT)  # the sign-in page sets the CSRF cookie (ensure_csrf_cookie)
        return client.cookies[settings.CSRF_COOKIE_NAME].value

    def counts(self):
        return [model.objects.count() for model in COUNTED]


class DoctorsHostTests(ConsoleHostCase):
    def test_the_sweep_covers_every_console_route_release_1_added(self):
        for route in ('ops/', 'ops/encounters/<uuid:encounter_id>/content', 'ops/activity/reads',
                      'ops/people/<uuid:user_id>/unlock', 'ops/security'):
            self.assertIn(route, CONSOLE_ROUTES)

    def test_every_console_route_answers_404_on_the_doctors_host_to_a_valid_admin_door_session(self):
        # the positive control first: the same kind of session, cookie and token reach the console on the admin host
        control = ops.admin_client(self.operator, enforce_csrf_checks=True)
        token = self.with_token(control)
        self.assertEqual(control.get('/ops/', HTTP_HOST=ADMIN).status_code, 200)
        accepted = control.post('/ops/holds/release', self.fields(token), HTTP_HOST=ADMIN)
        self.assertNotIn(accepted.status_code, (403, 404))  # the gate and the CSRF check both passed
        before = self.counts()
        for route in CONSOLE_ROUTES:
            path = self.concrete(route)
            for method in ('get', 'head', 'post'):
                # a fresh admin-door session per request, its cookie carried to cpt.quillmd.com
                client = ops.admin_client(self.operator, enforce_csrf_checks=True)
                token = self.with_token(client)
                unknown = getattr(client, method)(UNKNOWN, HTTP_HOST=CPT)
                with self.subTest(route=route, method=method):
                    self.assertEqual(client.session[request_meta.SESSION_DOOR], request_meta.ADMIN)
                    if method == 'post':
                        answer = client.post(path, self.fields(token), HTTP_HOST=CPT)
                    else:
                        answer = getattr(client, method)(path, HTTP_HOST=CPT)
                    self.assertEqual(answer.status_code, 404)
                    self.assertEqual(answer.content, unknown.content)
                    self.assertEqual(answer.get('Content-Type'), unknown.get('Content-Type'))
                    self.assertEqual(answer.get('Vary'), unknown.get('Vary'))
                    # a client's X-Forwarded-Host chooses nothing (USE_X_FORWARDED_HOST stays unset)
                    forwarded = getattr(client, method)(path, HTTP_HOST=CPT, HTTP_X_FORWARDED_HOST=ADMIN)
                    self.assertEqual(forwarded.status_code, 404)
        self.assertEqual(self.counts(), before)
        self.assertFalse(models.User.objects.filter(username='coverage-person').exists())

    def test_the_doctors_host_console_answers_nobody(self):
        unknown = Client(HTTP_HOST=CPT).get(UNKNOWN)
        for label, client in (('signed out', Client(HTTP_HOST=CPT)),
                              ('a member', ops.mark_signed_in(session_at(self.member, CPT), door=request_meta.CPT)),
                              ('an operator at the cpt door', ops.client(self.operator, HTTP_HOST=CPT))):
            for route in CONSOLE_ROUTES:
                with self.subTest(caller=label, route=route):
                    answer = client.get(self.concrete(route))
                    self.assertEqual((answer.status_code, answer.content), (404, unknown.content))


class AdminHostTests(ConsoleHostCase):
    def test_signed_out_the_admin_host_sends_the_visitor_to_the_operator_sign_in(self):
        answer = Client(HTTP_HOST=ADMIN).get('/ops/')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?next=%2Fops%2F'))

    def test_a_password_alone_reaches_no_console_route(self):
        password_only = ops.admin_client(self.operator, second_factor=False)
        self.assertEqual(password_only.session[request_meta.SESSION_DOOR], request_meta.ADMIN)
        before = self.counts()
        for route in CONSOLE_ROUTES:
            path = self.concrete(route)
            with self.subTest(route=route):
                self.assertEqual(password_only.get(path).status_code, 404)
                self.assertEqual(password_only.post(path, self.fields('')).status_code, 404)
        self.assertEqual(self.counts(), before)
        self.assertEqual(ops.admin_client(self.operator).get('/ops/').status_code, 200)  # the control: with the key

    def test_a_session_opened_elsewhere_or_before_release_1_reaches_nothing(self):
        now = request_meta.epoch_seconds()
        cases = {
            # a session from before release 1: no door, no second factor
            'no markers': {},
            # a session opened at the cpt door, its cookie carried to the admin host
            'the cpt door': ops.sign_in_markers(request_meta.CPT),
            # a cpt-door session that somehow carries a second-factor time: the door decides (satisfied reads it)
            'the cpt door with a second-factor time': {**ops.sign_in_markers(request_meta.CPT),
                                                       request_meta.SESSION_SECOND_FACTOR_AT: now},
            # a second-factor time from the future, or not a number
            'a future second factor': {**ops.sign_in_markers(request_meta.ADMIN, second_factor=False),
                                       request_meta.SESSION_SECOND_FACTOR_AT: now + 3600},
            'a malformed second factor': {**ops.sign_in_markers(request_meta.ADMIN, second_factor=False),
                                          request_meta.SESSION_SECOND_FACTOR_AT: 'yes'},
        }
        for label, markers in cases.items():
            client = session_at(self.operator, ADMIN, **markers)
            with self.subTest(label):
                self.assertEqual(client.get('/ops/').status_code, 404)
                self.assertEqual(client.get(self.concrete('ops/encounters/<uuid:encounter_id>')).status_code, 404)
        valid = session_at(self.operator, ADMIN, **ops.sign_in_markers(request_meta.ADMIN))
        self.assertEqual(valid.get('/ops/').status_code, 200)  # the control: the admin door's own markers

    def test_an_automated_account_with_a_grant_row_and_a_second_factor_reaches_nothing(self):
        agent = f.user('ops-agent')
        models.User.objects.filter(pk=agent.pk).update(actor_kind=models.User.AGENT)
        agent.refresh_from_db()
        models.OperatorGrant.objects.create(user=agent, reason='Synthetic grant from before release 1.',
                                            granted_by='synthetic installer')
        client = session_at(agent, ADMIN, **ops.sign_in_markers(request_meta.ADMIN))
        for route in CONSOLE_ROUTES:
            with self.subTest(route=route):
                self.assertEqual(client.get(self.concrete(route)).status_code, 404)

    def test_a_member_with_a_second_factor_session_is_no_operator(self):
        client = session_at(self.member, ADMIN, **ops.sign_in_markers(request_meta.ADMIN))
        self.assertEqual(client.get('/ops/').status_code, 404)


class DualRoleTests(ConsoleHostCase):
    def test_a_member_who_is_an_operator_keeps_the_doctors_app_and_the_console_stays_on_the_admin_host(self):
        models.Membership.objects.create(user=self.operator, workspace=self.ws, role=models.Membership.OWNER)
        doctors = ops.client(self.operator, HTTP_HOST=CPT)  # signed in at the cpt door
        self.assertEqual(doctors.get('/').status_code, 200)
        self.assertEqual(doctors.get('/api/session').json()['workspace']['id'], str(self.ws.pk))
        self.assertEqual(doctors.get('/ops/').status_code, 404)
        self.assertEqual(doctors.get(self.concrete('ops/encounters/<uuid:encounter_id>')).status_code, 404)
        self.assertEqual(ops.admin_client(self.operator, second_factor=False).get('/ops/').status_code, 404)
        self.assertEqual(ops.admin_client(self.operator).get('/ops/').status_code, 200)  # after the second factor
