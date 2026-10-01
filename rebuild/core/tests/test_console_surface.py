"""The administration console exists on the admin surface only (inventory 7A, F1).

Two processes serve QuillMD: the doctor surface (QUILLMD_ADMIN_SITE=0, app.quillmd.com) and the
administration surface (QUILLMD_ADMIN_SITE=1, admin.quillmd.com, behind an operator allowlist). Every
`/console/` route is mounted in the one URLconf both load, and until this change the middleware only
asked "is this account staff?" — so an administrator signed in on the DOCTOR host, from any address,
had the whole console there, outside the allowlist that guards the admin host.

These tests enumerate the routes FROM THE URL RESOLVER rather than from a list, so a route added later
is covered without anyone remembering to add it, and they fail if the enumeration comes back empty or
misses a route this file names as a known console route (the positive control). A spy replaces every
view callback during the request: on the doctor surface the assertion is that the request NEVER
REACHED THE VIEW, which a view-level 404 (a random primary key, say) cannot fake.
"""
import inspect
import re
import uuid
from pathlib import Path
from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent, User

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}

#: Modules whose every view is an administration view.
ADMIN_MODULES = {'core.admin_views', 'core.retention_views', 'core.disposition_views',
                 'core.disposition_execution_views'}
#: Routes this file KNOWS are console routes: if the enumeration misses any of them, the enumeration
#: is broken, and every assertion over it would be vacuous.
KNOWN_CONSOLE = {'admin_dashboard', 'audit', 'admin_account', 'admin_mfa_reset', 'admin_services',
                 'admin_usage_export', 'retention_holds', 'retention_hold_release', 'disposition_review',
                 'restore_preparation', 'disposition_execution', 'admin_job_detail'}
NGINX = Path(__file__).resolve().parents[2] / 'deploy' / 'production' / 'nginx-quillmd-production.conf'


def all_patterns(resolver=None, prefix=''):
    """(route, URLPattern) for every leaf pattern of the project URLconf, includes flattened."""
    resolver = resolver or get_resolver()
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            yield from all_patterns(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def sample_path(route):
    """A request path that the route matches, with a fresh value for each converter."""
    def value(match):
        converter = match.group(1) or 'str'
        return str(uuid.uuid4()) if converter == 'uuid' else ('1' if converter == 'int' else 'synthetic')
    return '/' + re.sub(r'<(?:(\w+):)?\w+>', value, route)


def is_admin_view(pattern):
    """An administration view by its module, its name, or its own staff gate in its source."""
    callback = pattern.callback
    view = getattr(callback, 'view_class', callback)
    if getattr(view, '__module__', '') in ADMIN_MODULES or (pattern.name or '').startswith('admin_'):
        return True
    try:
        source = inspect.getsource(view)
    except (OSError, TypeError):
        return False
    return bool(re.search(r'\bgate\(request\)|request\.user\.is_staff', source))


def console_routes():
    return [(route, pattern) for route, pattern in all_patterns() if route.startswith('console/')]


class Spy:
    """Replaces every view callback; records which ones a request reached. Never calls the real view."""

    def __init__(self):
        self.reached = []
        self.patches = []

    def __enter__(self):
        for route, pattern in all_patterns():
            def view(request, *args, _route=route, **kwargs):
                self.reached.append(_route)
                return HttpResponse('spy', status=299)
            patcher = patch.object(pattern, 'callback', view)
            patcher.start()
            self.patches.append(patcher)
        return self

    def __exit__(self, *exc):
        for patcher in reversed(self.patches):
            patcher.stop()


class ResolverEnumeration(TestCase):
    def test_the_enumeration_is_not_empty_and_finds_every_known_console_route(self):
        names = {pattern.name for _, pattern in console_routes()}
        self.assertGreaterEqual(len(names), len(KNOWN_CONSOLE))
        self.assertLessEqual(KNOWN_CONSOLE, names, 'the resolver walk missed a known console route')

    def test_every_administration_view_is_mounted_under_console(self):
        """The middleware's surface rule is a PATH rule. An administration view mounted anywhere else
        would be served on the doctor host, so every one must live under /console/."""
        admin = [(route, pattern.name) for route, pattern in all_patterns() if is_admin_view(pattern)]
        self.assertGreaterEqual(len(admin), len(KNOWN_CONSOLE))
        outside = [(route, name) for route, name in admin if not route.startswith('console/')]
        self.assertEqual(outside, [], 'administration views mounted outside /console/')

    def test_every_console_route_is_an_administration_view(self):
        """The converse: a doctor view mounted under /console/ would disappear from the doctor host."""
        self.assertEqual([route for route, pattern in console_routes() if not is_admin_view(pattern)], [])


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class DoctorSurfaceHasNoConsole(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='surface-admin', email='surface-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        self.doctor = User.objects.create_user(username='surface-doctor', email='surface-doctor@synthetic.invalid',
                                               verified_at=timezone.now())

    def mfa_client(self):
        client = Client()
        client.force_login(self.admin)
        session = client.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()
        return client

    def requests(self, client, routes):
        """Every route by GET and POST. Returns [(route, method, status)] and the routes the spy saw."""
        results = []
        with Spy() as spy:
            for route, _ in routes:
                path = sample_path(route)
                for method in ('get', 'post'):
                    results.append((route, method, getattr(client, method)(path).status_code))
        return results, spy.reached

    def test_an_mfa_administrator_on_the_doctor_host_reaches_no_console_view(self):
        routes = console_routes()
        self.assertGreaterEqual(len(routes), len(KNOWN_CONSOLE))
        audit_before = AuditEvent.objects.count()
        results, reached = self.requests(self.mfa_client(), routes)
        self.assertEqual(reached, [], 'a console view was reached on the doctor surface')
        self.assertEqual([r for r in results if r[2] != 404], [], 'console routes must answer 404, not 403 or a redirect')
        self.assertEqual(AuditEvent.objects.count(), audit_before)

    def test_an_administrator_without_an_mfa_session_gets_404_not_the_mfa_redirect(self):
        """A redirect to /mfa/ would tell the caller the route exists and is an administrator's."""
        client = Client()
        client.force_login(self.admin)
        results, reached = self.requests(client, console_routes())
        self.assertEqual(reached, [])
        self.assertEqual([r for r in results if r[2] != 404], [])

    def test_a_clinician_gets_404_and_reaches_nothing(self):
        client = Client()
        client.force_login(self.doctor)
        results, reached = self.requests(client, console_routes())
        self.assertEqual(reached, [])
        self.assertEqual([r for r in results if r[2] != 404], [])

    def test_signed_out_a_console_route_answers_like_a_route_that_does_not_exist(self):
        client = Client()
        missing = client.get('/no-such-route-anywhere/')
        for route, _ in console_routes():
            with self.subTest(route=route):
                response = client.get(sample_path(route))
                self.assertEqual((response.status_code, response.url.split('?')[0]),
                                 (missing.status_code, missing.url.split('?')[0]))

    def test_positive_control_the_doctor_routes_are_still_reached(self):
        """The surface rule must not swallow the doctor application: its dashboard still reaches its view."""
        client = Client()
        client.force_login(self.doctor)
        with Spy() as spy:
            self.assertEqual(client.get('/').status_code, 299)
        self.assertEqual(spy.reached, [''])


@override_settings(ADMIN_SITE=True, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class AdminSurfaceStillServesTheConsole(DoctorSurfaceHasNoConsole):
    """Positive control: the same administrator, the same requests, on the admin surface, reach every
    console view — so the 404s above come from the surface rule, not from a broken fixture or path."""

    def test_an_mfa_administrator_on_the_doctor_host_reaches_no_console_view(self):
        routes = console_routes()
        results, reached = self.requests(self.mfa_client(), routes)
        self.assertEqual(sorted(set(reached)), sorted(route for route, _ in routes))
        self.assertEqual({r[2] for r in results}, {299})

    def test_an_administrator_without_an_mfa_session_gets_404_not_the_mfa_redirect(self):
        client = Client()
        client.force_login(self.admin)
        results, reached = self.requests(client, console_routes())
        self.assertEqual(reached, [])
        self.assertEqual({(r[2]) for r in results}, {302})

    test_signed_out_a_console_route_answers_like_a_route_that_does_not_exist = None
    test_positive_control_the_doctor_routes_are_still_reached = None


# ---------------------------------------------------------------------------------------------------
# The production ingress: the doctor host's nginx server block refuses /console/ before the application.
# ---------------------------------------------------------------------------------------------------

def server_blocks(text):
    """{server_name or 'default': [(modifier, operand, body)]} for every server block's top-level locations."""
    blocks = {}
    for block in re.split(r'\nserver \{', text)[1:]:
        name = re.search(r'^\s*server_name\s+(\S+);', block, re.M)
        locations = re.findall(r'^\s*location\s+(=|\^~|~\*|~)?\s*(\S+)\s*\{(.*?)^\s*\}', block, re.M | re.S)
        blocks[name.group(1) if name else 'default'] = locations
    return blocks


def nginx_location(locations, uri):
    """The location nginx selects for `uri`: exact, then the longest prefix (final if ^~), then regexes in
    order, then that longest prefix — the documented ngx_http_core_module algorithm."""
    for modifier, operand, body in locations:
        if modifier == '=' and uri == operand:
            return body
    prefixes = [(len(operand), modifier, body) for modifier, operand, body in locations
                if modifier in ('', '^~') and uri.startswith(operand)]
    longest = max(prefixes, key=lambda p: p[0]) if prefixes else None
    if longest and longest[1] == '^~':
        return longest[2]
    for modifier, operand, body in locations:
        if modifier in ('~', '~*') and re.search(operand, uri, re.I if modifier == '~*' else 0):
            return body
    return longest[2] if longest else None


class DoctorHostIngress(TestCase):
    def setUp(self):
        self.blocks = server_blocks(NGINX.read_text())
        self.doctor = self.blocks['app.quillmd.com']

    def test_every_console_route_is_refused_by_the_doctor_host_without_reaching_the_application(self):
        routes = console_routes()
        self.assertGreaterEqual(len(routes), len(KNOWN_CONSOLE))
        for uri in [sample_path(route) for route, _ in routes] + ['/console', '/console/']:
            with self.subTest(uri=uri):
                body = nginx_location(self.doctor, uri)
                self.assertIsNotNone(body)
                self.assertRegex(body, r'^\s*return 404;\s*$')
                self.assertNotIn('proxy_pass', body)

    def test_positive_control_every_doctor_route_still_reaches_the_doctor_application(self):
        routes = [route for route, _ in all_patterns() if not route.startswith('console/')]
        self.assertGreater(len(routes), 20)
        for uri in [sample_path(route) for route in routes] + ['/consoles/', '/console-help/']:
            with self.subTest(uri=uri):
                self.assertIn('proxy_pass http://127.0.0.1:9140;', nginx_location(self.doctor, uri) or '')

    def test_the_admin_host_still_proxies_the_console(self):
        self.assertIn('proxy_pass http://127.0.0.1:9141;', nginx_location(self.blocks['admin.quillmd.com'], '/console/'))
