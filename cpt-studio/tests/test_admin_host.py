"""The admin host, admin.quillmd.com (owner direction 2026-11-23, DECISIONS D396): the operator sign-in and the console
alone, from cptstudio.urls_admin. Synthetic data only.

Release 1 (RELEASE-1-SPEC B1, B2 and B3, Lane 2's half): the operator door asks for the security key after the password
(the software authenticator of tests.test_second_factor); a session is bound to the door it was opened at; failures at
either door count toward one username delay, and a right password at the wrong door counts toward none; an account with
no membership - a platform operator's included - no longer signs in on cpt.quillmd.com. The console's own host gate
(operator_view answering 404 on cpt.quillmd.com to every session, B3 step 1) is Lane 3's: the tests here that need it
probe for it and say so when they skip.

Every routing assertion is one whose answer differs between the admin urlconf and the full one (the full urlconf answers
/api/session with 401 and / with a redirect to /login/?next=/), and cpt.quillmd.com is the negative control."""
import inspect
import json
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db.models.signals import pre_delete, pre_save
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver

from cptstudio import urls as customer_urls
from cptstudio import urls_admin
from studio import hosts, models, request_meta, second_factor_views, throttle, views
from studio import operator as operator_module
from tests.support import coding as factories
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import Clock, add_key, key_step

ADMIN = 'admin.quillmd.com'
CPT = 'cpt.quillmd.com'
PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
CONSOLE_ROUTES = [str(p.pattern) for p in customer_urls.urlpatterns if str(p.pattern).startswith('ops/')]
SAMPLE_IDS = {'<uuid:encounter_id>': '00000000-0000-4000-8000-000000000001',
              '<uuid:user_id>': '00000000-0000-4000-8000-000000000002',
              '<uuid:workspace_id>': '00000000-0000-4000-8000-000000000003'}


def concrete(route):
    for placeholder, value in SAMPLE_IDS.items():
        route = route.replace(placeholder, value)
    return '/' + route


@override_settings(STORAGES=PLAIN_STATIC)
class AdminHostCase(TestCase):
    def setUp(self):
        self.ws = factories.workspace()
        self.member = factories.member(self.ws)
        self.operator = factories.user('platform-operator')
        ops.grant(self.operator)
        self.key = add_key(self.operator)

    def admin(self, **kwargs):
        return Client(HTTP_HOST=ADMIN, **kwargs)

    def cpt(self, **kwargs):
        return Client(HTTP_HOST=CPT, **kwargs)

    def signed_in(self, user, host=ADMIN):
        """``user`` signed in at ``host``'s own door (at the admin door with the second factor's time, as the second
        step leaves it)."""
        client = Client(HTTP_HOST=host)
        client.force_login(user)
        return ops.mark_signed_in(client, door=ops.door_of(host))

    def sign_in_with_key(self, client, next_url=None, **extra):
        """The operator's two steps at the admin door; the second step's answer."""
        first = self.sign_in(client, self.operator.username, next_url=next_url, **extra)
        self.assertEqual((first.status_code, first['Location']), (302, '/login/second-factor'))
        return key_step(client, self.key)

    def sign_in(self, client, username, password=PASSWORD, next_url=None, **extra):
        data = {'username': username, 'password': password}
        if next_url is not None:
            data['next'] = next_url
        return client.post('/login/', data, **extra)


class RoutingTests(AdminHostCase):
    def test_the_admin_host_answers_from_its_own_urlconf(self):
        self.assertEqual(self.admin().get('/api/session').status_code, 404)
        self.assertEqual(self.cpt().get('/api/session').status_code, 401)  # the negative control
        answer = self.admin().get('/')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/'))
        control = self.cpt().get('/')
        self.assertEqual((control.status_code, control['Location']), (302, '/login/?next=/'))

    def test_every_method_of_the_admin_root_redirects_alike(self):
        # with the CSRF check enforced, as a browser or a monitor meets it (refutation h1, gate-1)
        for method in ('get', 'head', 'post', 'put', 'patch', 'delete', 'options'):
            with self.subTest(method=method):
                answer = getattr(self.admin(enforce_csrf_checks=True), method)('/')
                self.assertEqual((answer.status_code, answer['Location']), (302, '/login/'))
        foreign = self.admin(enforce_csrf_checks=True).post('/', secure=True, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(foreign.status_code, 403)
        for method in ('get', 'head', 'post', 'put', 'patch', 'delete', 'options'):  # and /ops (refutation h2, repairs-4)
            with self.subTest(path='/ops', method=method):
                answer = getattr(self.admin(enforce_csrf_checks=True), method)('/ops')
                self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        foreign = self.admin(enforce_csrf_checks=True).post('/ops', secure=True, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(foreign.status_code, 403)
        answer = self.signed_in(self.operator).head('/')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        answer = self.signed_in(self.member).get('/')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/'))  # no doctor app here

    def test_the_host_is_read_without_its_port_or_trailing_dot(self):
        for host in ('admin.quillmd.com:443', 'admin.quillmd.com.'):
            with self.subTest(host=host):
                self.assertEqual(Client(HTTP_HOST=host).get('/api/session').status_code, 404)
        self.assertEqual(Client(HTTP_HOST='evil.example').get('/').status_code, 400)

    def test_no_doctor_app_or_api_route_is_on_the_admin_host(self):
        member = self.signed_in(self.member)
        for path in ('/api/session', '/api/encounters', '/api/reports/00000000-0000-4000-8000-000000000002/download'):
            with self.subTest(path=path):
                self.assertEqual(member.get(path).status_code, 404)
        self.assertEqual({str(p.pattern) for p in get_resolver(hosts.ADMIN_URLCONF).url_patterns},
                         set(urls_admin.OPEN_ROUTES) | set(CONSOLE_ROUTES))

    def test_ops_without_its_slash_redirects_on_the_admin_host_only(self):
        answer = self.admin().get('/ops')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        self.assertEqual(self.signed_in(self.operator, CPT).get('/ops').status_code, 404)  # unchanged on cpt


class ConsoleGateTests(AdminHostCase):
    def test_a_signed_out_visit_to_a_console_page_goes_to_sign_in_and_back(self):
        answer = self.admin().get('/ops/activity?kind=people')
        self.assertEqual(answer.status_code, 302)
        self.assertEqual(answer['Location'], '/login/?next=%2Fops%2Factivity%3Fkind%3Dpeople')
        self.assertEqual(self.admin().head('/ops/people')['Location'], '/login/?next=%2Fops%2Fpeople')
        client = self.admin()
        landed = self.sign_in_with_key(client, next_url='/ops/activity?kind=people')  # back after the key (B2)
        self.assertEqual((landed.status_code, landed['Location']), (302, '/ops/activity?kind=people'))
        self.assertEqual(client.get('/ops/people').status_code, 200)

    def test_every_console_route_meets_the_gate_for_anyone_not_an_operator(self):
        member = self.signed_in(self.member)
        for route in CONSOLE_ROUTES:
            path = concrete(route)
            with self.subTest(route=route):
                self.assertEqual(self.admin().get(path).status_code, 302)  # signed out: to the sign-in
                posted = self.admin().post(path, {'note': 'x' * 30})  # a form sent after the session ended
                self.assertEqual((posted.status_code, posted['Location']), (303, '/login/?next=%2Fops%2F'))
                # with the CSRF check enforced: no cookie at all, and a stale token (refutation h2, repairs-3)
                enforced = self.admin(enforce_csrf_checks=True)
                self.assertEqual(enforced.post(path, {'note': 'x' * 30}).status_code, 303)
                enforced.cookies[settings.CSRF_COOKIE_NAME] = 'stale' * 6 + 'xx'
                self.assertEqual(enforced.post(path, {'csrfmiddlewaretoken': 'stale' * 6 + 'xx'}).status_code, 303)
                self.assertEqual(member.get(path).status_code, 404)
                self.assertEqual(member.post(path, {'note': 'x' * 30}).status_code, 404)

    def test_a_session_taken_to_the_other_host_is_ended(self):
        # B3 (it replaces "a cpt session replayed on the admin host is the same account", whose operator got the
        # console): a session is bound to the door it was opened at, so a cpt session replayed here ends before any view
        for user in (self.member, self.operator):
            with self.subTest(user=user.username):
                on_cpt = self.signed_in(user, CPT)
                key = on_cpt.session.session_key
                replay = self.admin()
                replay.cookies = on_cpt.cookies
                answer = replay.get('/ops/people')
                self.assertEqual((answer.status_code, answer['Location']),
                                 (302, '/login/?next=%2Fops%2Fpeople&reason=expired'))
                self.assertFalse(Session.objects.filter(session_key=key).exists())
        # and an admin-door session, second factor and all, opens nothing on cpt.quillmd.com
        admin = self.signed_in(self.operator)
        self.assertEqual(admin.get('/ops/people').status_code, 200)  # the control: it is a console session
        replay = self.cpt()
        replay.cookies = admin.cookies
        self.assertEqual(replay.get('/ops/').status_code, 404)
        self.assertEqual(admin.get('/ops/people').status_code, 302)  # ended for its own host too

    def test_the_console_is_closed_on_cpt_as_far_as_the_doors_decide(self):
        # B3 (it replaces "cpt is unchanged", whose operator got 200 on cpt.quillmd.com/ops/): the doors' half
        self.assertEqual(self.cpt().get('/ops/').status_code, 404)  # signed out: an unknown URL there
        self.assertEqual(self.signed_in(self.member, CPT).get('/ops/').status_code, 404)
        # an operator with no membership no longer signs in on cpt.quillmd.com: the wrong-password answer, no session
        refused = self.sign_in(self.cpt(), self.operator.username)
        self.assertEqual(refused.status_code, 400)
        self.assertIn(views.SIGN_IN_REFUSED, refused.content.decode())
        self.assertNotIn(settings.SESSION_COOKIE_NAME, refused.cookies)
        attempt = models.LoginAttempt.objects.get(username=self.operator.username)
        self.assertEqual((attempt.door, attempt.outcome, attempt.succeeded), ('cpt', 'no_access', False))
        # the front page sends no operator to the console: an account without a workspace gets the 404
        self.assertEqual(self.signed_in(self.operator, CPT).get('/').status_code, 404)

    def test_an_operator_s_own_cpt_session_meets_404_on_the_console(self):
        # B3's dual role: the doctors' app works on cpt and the console answers 404 there; on admin the console works
        # after the second factor. The 404 on cpt is the console's own gate (Lane 3, B3 step 1).
        models.Membership.objects.create(user=self.operator, workspace=self.ws, role=models.Membership.OWNER)
        member_door = self.cpt()
        self.assertEqual(self.sign_in(member_door, self.operator.username).status_code, 302)  # signs in as the member
        self.assertEqual(member_door.session[request_meta.SESSION_DOOR], 'cpt')
        self.assertNotIn(request_meta.SESSION_SECOND_FACTOR_AT, member_door.session)
        self.assertEqual(member_door.get('/api/session').status_code, 200)
        self.assertEqual(self.sign_in_with_key(self.admin())['Location'], '/ops/')
        if member_door.get('/ops/').status_code == 200:
            self.skipTest('the console\'s host gate (B3 step 1, Lane 3) is not in this tree yet')
        for route in CONSOLE_ROUTES:
            with self.subTest(route=route):
                self.assertEqual(member_door.get(concrete(route)).status_code, 404)

    def test_no_admin_url_records_or_ends_a_grant(self):
        # (refutation h2, repairs-2 and fresh-5) the authority is behavioural: every admin route is posted with real ids
        # and each act's own valid fields, as the member and as the operator, while any write of a grant or a revocation is
        # recorded by signal - whatever module or alias would make it
        writes = []

        def record(sender, **kwargs):
            writes.append(sender.__name__)
        receivers = [(signal, model) for signal in (pre_save, pre_delete)
                     for model in (models.OperatorGrant, models.OperatorRevocation)]
        for signal, model in receivers:
            signal.connect(record, sender=model, weak=False, dispatch_uid=f'admin-sweep-{signal}-{model.__name__}')
        try:
            encounter = factories.encounter(self.ws, self.member)
            membership = models.Membership.objects.get(user=self.member)
            ids = {'<uuid:encounter_id>': str(encounter.pk), '<uuid:user_id>': str(self.member.pk),
                   '<uuid:workspace_id>': str(self.ws.pk)}
            field_sets = [
                {'username': 'sweep-person', 'workspace': str(self.ws.pk), 'role': 'reviewer', 'name': 'Sweep Person'},
                {'membership': str(membership.pk), 'role': 'owner', 'back': '/ops/people'},
                {'access': 'off', 'back': '/ops/people'}, {'access': 'on', 'back': '/ops/people'},
                {'name': 'Sweep Workspace', 'category': str(self.ws.category.pk)},
                {'note': 'A synthetic note long enough for every act.', 'run': '1'},
                {'username': self.member.username, 'reason': 'x' * 20, 'user': str(self.member.pk)},
            ]
            for user in (self.member, self.operator):
                client = self.signed_in(user)  # at the admin door, with the second factor's time
                for pattern in get_resolver(hosts.ADMIN_URLCONF).url_patterns:
                    route = str(pattern.pattern)
                    if route in ('logout/', 'logout/everywhere'):  # each would end the sweep's own session
                        continue
                    path = '/' + route
                    for placeholder, value in ids.items():
                        path = path.replace(placeholder, value)
                    for fields in field_sets:
                        client.post(path, data=fields)
                        client.post(path, data=json.dumps(fields), content_type='application/json')
        finally:
            for signal, model in receivers:
                signal.disconnect(record, sender=model, dispatch_uid=f'admin-sweep-{signal}-{model.__name__}')
        self.assertEqual(writes, [])
        self.assertTrue(operator_module.is_operator(self.operator))
        self.assertFalse(operator_module.is_operator(self.member))
        self.assertTrue(models.User.objects.filter(username='sweep-person').exists())  # the sweep reached the acts' bodies
        for module in (hosts, urls_admin, views, second_factor_views):  # the admin host's own modules: no grant writer
            self.assertNotRegex(inspect.getsource(module), r'\bOperator(?:Grant|Revocation)\b|operator\.(?:grant|revoke)\(',
                                module.__name__)

class SignInTests(AdminHostCase):
    def test_an_operator_signs_in_and_lands_in_the_console(self):
        client = self.admin()
        answer = self.sign_in_with_key(client)  # the password, then the key (B2)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        attempt = models.LoginAttempt.objects.get(username=self.operator.username)
        self.assertEqual((attempt.door, attempt.outcome, attempt.succeeded), ('admin', 'signed_in', True))
        self.assertEqual(client.get('/ops/').status_code, 200)
        out = client.post('/logout/')
        self.assertEqual((out.status_code, out['Location']), (302, '/login/'))
        self.assertEqual(client.get('/ops/people')['Location'], '/login/?next=%2Fops%2Fpeople')

    def test_any_other_account_is_refused_like_a_wrong_password(self):
        refused = self.sign_in(self.admin(), self.member.username)
        wrong = self.sign_in(self.admin(), self.operator.username, password='not-the-password')
        for answer in (refused, wrong):
            self.assertEqual(answer.status_code, 400)
            self.assertIn(views.ADMIN_SIGN_IN_REFUSED, answer.content.decode())
            self.assertNotIn(settings.SESSION_COOKIE_NAME, answer.cookies)
        self.assertEqual(list(models.LoginAttempt.objects.order_by('pk').values_list('username', 'succeeded', 'door',
                                                                                     'outcome')),
                         [(self.member.username, False, 'admin', 'no_access'),
                          (self.operator.username, False, 'admin', 'wrong_password')])
        self.assertFalse(models.OperatorGrant.objects.filter(user=self.member).exists())

    def test_an_operator_who_is_also_a_member_signs_in_as_the_operator(self):
        models.Membership.objects.create(user=self.operator, workspace=self.ws, role=models.Membership.OWNER)
        self.assertEqual(self.sign_in_with_key(self.admin())['Location'], '/ops/')

    def test_next_may_only_name_a_console_page_on_this_host(self):
        for next_url, landing in (('https://evil.example/ops/', '/ops/'), ('//evil.example/ops/', '/ops/'),
                                  ('/api/session', '/ops/'), ('/', '/ops/'), ('/ops/workspaces', '/ops/workspaces'),
                                  ('https://admin.quillmd.com/ops/people', '/ops/'),
                                  # paths that climb out of the console or name no console page (refutation h2, fresh-3)
                                  ('/ops/../login/', '/ops/'), ('/ops/%2e%2e/login/', '/ops/'), ('/ops/\\evil.example', '/ops/'),
                                  ('/ops/no-such-page', '/ops/'), ('/ops/people?tab=x', '/ops/people?tab=x'),
                                  ('/account/', '/account/')):  # the account page too (an operator's password change)
            with self.subTest(next_url=next_url):
                answer = self.sign_in_with_key(self.admin(), next_url=next_url)
                self.assertEqual(answer['Location'], landing)

    def test_failures_at_either_door_count_toward_one_username_delay(self):
        # B1 (it replaces "the operator door enforces the shared throttle"): failures at either door count toward one
        # delay for the username; the right password is then refused at both doors, with the delay's own sentence, no
        # session and no successful attempt - and signs in once the delay has passed
        with Clock() as clock:
            for client in (self.admin(), self.admin(), self.admin(), self.cpt(), self.cpt()):
                self.sign_in(client, self.operator.username, password='not-the-password')
            for client, refused in ((self.admin(), views.ADMIN_SIGN_IN_REFUSED), (self.cpt(), views.SIGN_IN_REFUSED)):
                right = self.sign_in(client, self.operator.username)
                self.assertEqual(right.status_code, 400)
                self.assertIn('Too many attempts. Wait 1 minute', right.content.decode())
                self.assertNotIn(refused, right.content.decode())
                self.assertNotIn(settings.SESSION_COOKIE_NAME, right.cookies)
            self.assertFalse(models.LoginAttempt.objects.filter(username=self.operator.username, succeeded=True).exists())
            clock.advance(settings.SIGNIN_DELAY_BASE_SECONDS + 1)
            self.assertEqual(self.sign_in_with_key(self.admin())['Location'], '/ops/')

    def test_a_right_password_at_the_wrong_door_counts_toward_no_delay(self):
        # B1 (it replaces "a doctor refused at the operator door counts on the doctor sign-in", the declared cost of the
        # old shared throttle): a doctor's right password at the admin door is no_access, and changes nothing at cpt
        for _ in range(settings.SIGNIN_PAIR_LIMIT + 2):
            refused = self.sign_in(self.admin(), self.member.username)
            self.assertIn(views.ADMIN_SIGN_IN_REFUSED, refused.content.decode())
        self.assertEqual(throttle.failures_of(self.member.username)[0], 0)
        signed = self.sign_in(self.cpt(), self.member.username)
        self.assertEqual((signed.status_code, signed['Location']), (302, '/'))
        self.assertEqual(set(models.LoginAttempt.objects.filter(username=self.member.username, door='admin')
                             .values_list('outcome', flat=True)), {'no_access'})

    def test_csrf_and_the_origin_hold_on_the_admin_host(self):
        client = self.admin(enforce_csrf_checks=True)
        client.get('/login/', secure=True)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        data = {'username': self.operator.username, 'password': PASSWORD, 'csrfmiddlewaretoken': token}
        foreign = client.post('/login/', data, secure=True, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(foreign.status_code, 403)
        # the customer host is no trusted origin here, though CSRF_TRUSTED_ORIGINS names it (refutation h1, door-1)
        from_cpt = client.post('/login/', data, secure=True, HTTP_ORIGIN='https://cpt.quillmd.com')
        self.assertEqual(from_cpt.status_code, 403)
        referer_only = client.post('/login/', data, secure=True, HTTP_REFERER='https://cpt.quillmd.com/')
        self.assertEqual(referer_only.status_code, 403)
        malformed = client.post('/login/', data, secure=True, HTTP_REFERER='https://[')  # a 403, never a 500 (h2, fresh-1)
        self.assertEqual(malformed.status_code, 403)
        plain = self.admin(enforce_csrf_checks=True)  # a plain request is judged by its Referer too (h2, fresh-4)
        plain.get('/login/')
        plain_data = {**data, 'csrfmiddlewaretoken': plain.cookies[settings.CSRF_COOKIE_NAME].value}
        self.assertEqual(plain.post('/login/', plain_data, HTTP_REFERER='http://evil.example/').status_code, 403)
        own = client.post('/login/', data, secure=True, HTTP_ORIGIN='https://admin.quillmd.com')
        self.assertEqual((own.status_code, own['Location']), (302, '/login/second-factor'))
        # the second step under the same rules: its own origin and the CSRF token, for the options and the answer
        mine = {'secure': True, 'HTTP_ORIGIN': 'https://admin.quillmd.com'}
        self.assertEqual(client.post('/login/second-factor/options', **mine).status_code, 403)  # no token: refused
        options = client.post('/login/second-factor/options', {'csrfmiddlewaretoken': token}, **mine).json()
        assertion = json.dumps(self.key.assertion(options))
        crossed = client.post('/login/second-factor', {'csrfmiddlewaretoken': token, 'credential': assertion},
                              secure=True, HTTP_ORIGIN='https://cpt.quillmd.com')
        self.assertEqual(crossed.status_code, 403)
        signed = client.post('/login/second-factor', {'csrfmiddlewaretoken': token, 'credential': assertion}, **mine)
        self.assertEqual((signed.status_code, signed['Location']), (302, '/ops/'))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value  # rotated by the sign-in
        act = {'csrfmiddlewaretoken': token, 'username': 'probe-person', 'workspace': str(self.ws.pk), 'role': 'reviewer',
               'display_name': 'Probe Person'}
        before = models.User.objects.count()
        crossed = client.post('/ops/people/add', act, secure=True, HTTP_ORIGIN='https://cpt.quillmd.com')
        self.assertEqual(crossed.status_code, 403)
        self.assertEqual(client.post('/ops/people/add', act, secure=True, HTTP_REFERER='https://[').status_code, 403)
        self.assertEqual(models.User.objects.count(), before)

    def test_the_sign_in_page_is_the_console_s_and_names_a_static_asset(self):
        page = self.admin().get('/login/')
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        for needle in ('CPT Studio · Operator console', '<h1 id="signin-title">Operator sign-in</h1>',
                       'Doctors sign in at <a href="https://cpt.quillmd.com/login/">'):
            self.assertIn(needle, body)
        self.assertNotIn('<nav class="topnav"', body)
        self.assertNotIn('action="/logout/"', body)
        self.assertNotIn(settings.RELEASE_SHA, body)  # B7: the sign-in page tells a visitor no build
        self.assertNotIn('release', body)
        self.assertNotIn('ops_session.js', body)  # no session to watch before the sign-in
        self.assertRegex(body, r'(?:href|src)="/static/[^"]+"')  # the installer's smoke reads a static reference
        self.assertEqual(self.admin().put('/login/').status_code, 405)


class ConsolePagesTests(AdminHostCase):
    PAGES = ('/ops/', '/ops/people', '/ops/workspaces', '/ops/spending', '/ops/activity', '/ops/activity/sign-ins')

    def test_every_console_page_renders_on_the_admin_host_after_the_second_factor(self):
        # (it replaces "every console page renders the same on both hosts": release 1 serves the console on the admin
        # host only, B3)
        client = self.admin()
        self.assertEqual(self.sign_in_with_key(client)['Location'], '/ops/')
        for path in self.PAGES + ('/ops/security',):
            with self.subTest(path=path):
                page = client.get(path)
                self.assertEqual(page.status_code, 200)
                body = page.content.decode()
                self.assertIn('src="/static/studio/ops_session.js"', body)  # B5: the console signs itself out
                self.assertIn('<noscript><meta http-equiv="refresh" content="610;url=/login/?reason=idle"></noscript>',
                              body)

    def test_no_console_page_renders_on_cpt_once_its_gate_is_in(self):
        on_cpt = ops.client(self.operator, HTTP_HOST=CPT)  # a cpt-door operator session, as no door makes any more
        if on_cpt.get('/ops/').status_code == 200:
            self.skipTest('the console\'s host gate (B3 step 1, Lane 3) is not in this tree yet')
        for path in self.PAGES:
            with self.subTest(path=path):
                self.assertEqual(on_cpt.get(path).status_code, 404)

class AdminSignInStaticTests(SimpleTestCase):
    """The admin sign-in page under the manifest storage the image builds with, after collectstatic: every static file it
    names by href or src - what ops/install.py's smoke_web reads, by its own STATIC_REFERENCE_RE - answers 200
    (refutation h1, regression-4)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._root = tempfile.TemporaryDirectory()
        cls._static = override_settings(STATIC_ROOT=Path(cls._root.name) / 'static')
        cls._static.enable()
        call_command('collectstatic', interactive=False, verbosity=0)

    @classmethod
    def tearDownClass(cls):
        cls._static.disable()
        cls._root.cleanup()
        super().tearDownClass()

    def test_every_static_reference_on_the_admin_sign_in_page_answers(self):
        source = (Path(settings.BASE_DIR) / 'ops' / 'install.py').read_text(encoding='utf-8')
        line = next(each for each in source.splitlines() if each.startswith('STATIC_REFERENCE_RE = re.compile('))
        pattern = line[len("STATIC_REFERENCE_RE = re.compile(r'''"):-len("''')")]
        page = Client(HTTP_HOST=ADMIN).get('/login/')
        self.assertEqual(page.status_code, 200)
        references = sorted(set(re.findall(pattern, page.content.decode())))
        self.assertTrue(references)
        for reference in references:
            with self.subTest(reference=reference):
                self.assertEqual(Client(HTTP_HOST=ADMIN).get(reference).status_code, 200)
