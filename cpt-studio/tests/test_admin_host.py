"""The admin host, admin.quillmd.com (owner direction 2026-11-23, DECISIONS D396): the operator sign-in and the console
alone, from cptstudio.urls_admin; cpt.quillmd.com unchanged. Synthetic data only.

Every routing assertion is one whose answer differs between the admin urlconf and the full one (the full urlconf answers
/api/session with 401 and / with a redirect to /login/?next=/), and cpt.quillmd.com is the negative control."""
import inspect
import json
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver

from cptstudio import urls as customer_urls
from cptstudio import urls_admin
from studio import hosts, models, views
from tests.support import coding as factories
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

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

    def admin(self, **kwargs):
        return Client(HTTP_HOST=ADMIN, **kwargs)

    def cpt(self, **kwargs):
        return Client(HTTP_HOST=CPT, **kwargs)

    def signed_in(self, user, host=ADMIN):
        client = Client(HTTP_HOST=host)
        client.force_login(user)
        return client

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
        landed = self.sign_in(client, self.operator.username, next_url='/ops/activity?kind=people')
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
                self.assertEqual(member.get(path).status_code, 404)
                self.assertEqual(member.post(path, {'note': 'x' * 30}).status_code, 404)

    def test_a_cpt_session_replayed_on_the_admin_host_is_the_same_account(self):
        member_cpt = self.signed_in(self.member, CPT)
        replay = self.admin()
        replay.cookies = member_cpt.cookies
        self.assertEqual(replay.get('/ops/people').status_code, 404)  # a member: the gate's 404, never a redirect
        operator_cpt = self.signed_in(self.operator, CPT)
        replay = self.admin()
        replay.cookies = operator_cpt.cookies
        self.assertEqual(replay.get('/ops/people').status_code, 200)

    def test_cpt_is_unchanged(self):
        self.assertEqual(self.cpt().get('/ops/').status_code, 404)  # signed out: still an unknown URL there
        self.assertEqual(self.signed_in(self.member, CPT).get('/ops/').status_code, 404)
        self.assertEqual(self.signed_in(self.operator, CPT).get('/ops/').status_code, 200)

    def test_no_admin_url_records_a_grant(self):
        modules = {inspect.getmodule(p.callback) for p in get_resolver(hosts.ADMIN_URLCONF).url_patterns
                   if isinstance(p, URLPattern)} | {hosts, urls_admin}
        for module in modules:
            source = inspect.getsource(module)
            if module.__name__ == 'studio.operator':
                continue  # its grant and revoke are pinned by tests.test_operator's own sweep
            # any write of a grant or revocation (reads, such as console.py's list of operators, are fine): h1, regression-5
            writes = r'(?:create|get_or_create|update_or_create|bulk_create|update|delete)\('
            self.assertNotRegex(source, rf'Operator(?:Grant|Revocation)\.objects\.(?:[a-z_]+\([^)]*\)\.)*{writes}|'
                                        r'Operator(?:Grant|Revocation)\(|operator\.grant\(|\bgrant\(', module.__name__)
        before = models.OperatorGrant.objects.count()
        for user in (self.member, self.operator):
            client = Client(HTTP_HOST=ADMIN, enforce_csrf_checks=False)
            client.force_login(user)
            for pattern in get_resolver(hosts.ADMIN_URLCONF).url_patterns:
                route = str(pattern.pattern)
                if route == 'logout/':
                    continue
                fields = {'username': user.username, 'reason': 'x' * 20, 'user': str(user.pk), 'workspace': str(self.ws.pk)}
                client.post(concrete(route), data=json.dumps(fields), content_type='application/json')
                client.post(concrete(route), data=fields)  # form-encoded, as the console's forms send it (h1, regression-5)
        self.assertEqual(models.OperatorGrant.objects.count(), before)
        self.assertFalse(models.OperatorGrant.objects.filter(user=self.member).exists())


class SignInTests(AdminHostCase):
    def test_an_operator_signs_in_and_lands_in_the_console(self):
        client = self.admin()
        answer = self.sign_in(client, self.operator.username)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/'))
        self.assertTrue(models.LoginAttempt.objects.get(username=self.operator.username).succeeded)
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
        self.assertEqual(list(models.LoginAttempt.objects.order_by('pk').values_list('username', 'succeeded')),
                         [(self.member.username, False), (self.operator.username, False)])
        self.assertFalse(models.OperatorGrant.objects.filter(user=self.member).exists())

    def test_an_operator_who_is_also_a_member_signs_in_as_the_operator(self):
        models.Membership.objects.create(user=self.operator, workspace=self.ws, role=models.Membership.OWNER)
        answer = self.sign_in(self.admin(), self.operator.username)
        self.assertEqual(answer['Location'], '/ops/')

    def test_next_may_only_name_a_console_page_on_this_host(self):
        for next_url, landing in (('https://evil.example/ops/', '/ops/'), ('//evil.example/ops/', '/ops/'),
                                  ('/api/session', '/ops/'), ('/', '/ops/'), ('/ops/workspaces', '/ops/workspaces'),
                                  ('https://admin.quillmd.com/ops/people', '/ops/')):
            with self.subTest(next_url=next_url):
                answer = self.sign_in(self.admin(), self.operator.username, next_url=next_url)
                self.assertEqual(answer['Location'], landing)

    def test_the_operator_door_enforces_the_shared_throttle(self):
        # (refutation h1, regression-1) run up the operator's own username at the admin door: the right password is then
        # refused by the throttle, with its own sentence, no session and no successful attempt
        for _ in range(settings.LOGIN_THROTTLE_ATTEMPTS):
            wrong = self.sign_in(self.admin(), self.operator.username, password='not-the-password')
            self.assertIn(views.ADMIN_SIGN_IN_REFUSED, wrong.content.decode())
        right = self.sign_in(self.admin(), self.operator.username)
        self.assertEqual(right.status_code, 400)
        self.assertIn('Too many failed attempts', right.content.decode())
        self.assertNotIn(views.ADMIN_SIGN_IN_REFUSED, right.content.decode())
        self.assertNotIn(settings.SESSION_COOKIE_NAME, right.cookies)
        self.assertFalse(models.LoginAttempt.objects.filter(username=self.operator.username, succeeded=True).exists())

    def test_a_doctor_refused_at_the_operator_door_counts_on_the_doctor_sign_in(self):
        for _ in range(settings.LOGIN_THROTTLE_ATTEMPTS):
            self.sign_in(self.admin(), self.member.username)  # the right password, refused: not an operator
        blocked = self.sign_in(self.cpt(), self.member.username)
        self.assertIn('Too many failed attempts', blocked.content.decode())  # the declared cost of one shared throttle

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
        own = client.post('/login/', data, secure=True, HTTP_ORIGIN='https://admin.quillmd.com')
        self.assertEqual((own.status_code, own['Location']), (302, '/ops/'))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value  # rotated by the sign-in
        act = {'csrfmiddlewaretoken': token, 'username': 'probe-person', 'workspace': str(self.ws.pk), 'role': 'reviewer',
               'display_name': 'Probe Person'}
        before = models.User.objects.count()
        crossed = client.post('/ops/people/add', act, secure=True, HTTP_ORIGIN='https://cpt.quillmd.com')
        self.assertEqual(crossed.status_code, 403)
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
        self.assertRegex(body, r'(?:href|src)="/static/[^"]+"')  # the installer's smoke reads a static reference
        self.assertEqual(self.admin().put('/login/').status_code, 405)


class ConsolePagesUnchangedTests(AdminHostCase):
    def test_every_console_page_renders_the_same_on_both_hosts(self):
        admin, cpt = self.signed_in(self.operator), self.signed_in(self.operator, CPT)
        for path in ('/ops/', '/ops/people', '/ops/workspaces', '/ops/spending', '/ops/activity', '/ops/activity/sign-ins'):
            with self.subTest(path=path):
                one, other = admin.get(path), cpt.get(path)
                self.assertEqual((one.status_code, other.status_code), (200, 200))
                strip = lambda html: re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', '', html.decode())
                self.assertEqual(strip(one.content), strip(other.content))

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
