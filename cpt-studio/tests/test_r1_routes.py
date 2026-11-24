"""Release 1's new routes (RELEASE-1-SPEC 3.4): every one is where the specification puts it, on the right host and with
the view it names, and every view that is still an R1 stub answers exactly what an unknown URL answers - Django's 404,
for any method, with the CSRF check enforced, on both hosts - so a half-merged main exposes nothing.

A stub is recognised by the comment its lane removes with it ("# R1 stub: Lane <n> replaces this (<item>)"), so each
lane replaces its own stubs without touching this file: the routes stay pinned, and a replaced view is simply no longer
held to the stub's 404. Synthetic data only."""
from __future__ import annotations

import inspect
import re

from django.test import Client, TestCase, override_settings
from django.urls import Resolver404, get_resolver, resolve

from studio import request_meta
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

ADMIN, CPT = 'admin.quillmd.com', 'cpt.quillmd.com'
URLCONF = {CPT: 'cptstudio.urls', ADMIN: 'cptstudio.urls_admin'}
BOTH, ADMIN_ONLY, CPT_ONLY = {CPT, ADMIN}, {ADMIN}, {CPT}
CONSOLE = BOTH  # console routes live in the full urlconf, and the admin urlconf takes them from it (TEC-1 (a))
# route: (hosts, the view, its lane, its item) - RELEASE-1-SPEC 3.4's table
ROUTES = {
    'account/': (BOTH, 'studio.views.account_security', 2, 'B4'),
    'logout/everywhere': (BOTH, 'studio.views.logout_everywhere', 2, 'B4'),
    'session/activity': (BOTH, 'studio.views.activity_ping', 2, 'B5'),
    'login/second-factor': (ADMIN_ONLY, 'studio.second_factor_views.second_factor', 2, 'B2'),
    'login/second-factor/options': (ADMIN_ONLY, 'studio.second_factor_views.second_factor_options', 2, 'B2'),
    'login/enrol': (ADMIN_ONLY, 'studio.second_factor_views.enrol', 2, 'B2'),
    'login/enrol/options': (ADMIN_ONLY, 'studio.second_factor_views.enrol_options', 2, 'B2'),
    'login/recovery': (ADMIN_ONLY, 'studio.second_factor_views.recovery', 2, 'B2'),
    'ops/security': (CONSOLE, 'studio.second_factor_views.keys', 2, 'B2'),
    'api/members': (CPT_ONLY, 'studio.api.members', 3, 'C4'),
    'api/members/<uuid:user_id>/access': (CPT_ONLY, 'studio.api.member_access', 3, 'C4'),
    'api/encounters/<uuid:encounter_id>/bundle': (CPT_ONLY, 'studio.bundle_api.encounter_bundle', 4, 'D2'),
    'ops/encounters/<uuid:encounter_id>/content': (CONSOLE, 'studio.operator.content_open', 3, 'C2'),
    'ops/activity/reads': (CONSOLE, 'studio.console.reads', 3, 'C1'),
    'ops/people/<uuid:user_id>/unlock': (CONSOLE, 'studio.console.unlock_sign_in', 3, 'B1'),
}
SAMPLE = {'<uuid:user_id>': '00000000-0000-4000-8000-000000000002',
          '<uuid:encounter_id>': '00000000-0000-4000-8000-000000000001'}
STUB_COMMENT = re.compile(r'# R1 stub: Lane (\d) replaces this \(([A-Z]\d+)\)\n')
METHODS = ('get', 'head', 'post', 'put', 'delete')
UNKNOWN = '/r1-no-such-route'


def concrete(route):
    for placeholder, value in SAMPLE.items():
        route = route.replace(placeholder, value)
    return '/' + route


def view_of(route, host):
    """The view behind ``route`` on ``host``, every wrapper (the admin host's sign-in redirect, csrf_exempt) removed."""
    return inspect.unwrap(resolve(concrete(route), urlconf=URLCONF[host]).func)


def stub_mark(view):
    """(lane, item) of an R1 stub, read from its comment; None for a view its lane has replaced."""
    match = STUB_COMMENT.fullmatch(inspect.getcomments(view) or '')
    return (int(match.group(1)), match.group(2)) if match else None


# R1 stub: Lane 9 replaces this (Z9)
def _marked(request):  # the detector's positive control
    raise AssertionError('never called')


class RouteTableTests(TestCase):
    def test_every_route_is_on_its_hosts_with_the_view_it_names(self):
        for route, (hosts, view_name, _, _) in ROUTES.items():
            for host, urlconf in URLCONF.items():
                with self.subTest(route=route, host=host):
                    patterns = {str(pattern.pattern) for pattern in get_resolver(urlconf).url_patterns}
                    if host in hosts:
                        self.assertIn(route, patterns)
                        view = view_of(route, host)
                        self.assertEqual(f'{view.__module__}.{view.__qualname__}', view_name)
                    else:
                        self.assertNotIn(route, patterns)
                        with self.assertRaises(Resolver404):
                            resolve(concrete(route), urlconf=urlconf)

    def test_a_stub_names_the_lane_and_item_of_its_route(self):
        self.assertEqual(stub_mark(_marked), (9, 'Z9'))  # the detector finds a stub's comment...
        self.assertIsNone(stub_mark(view_of('ops/people/<uuid:user_id>/role', CPT)))  # ...and not on a real view
        for route, (hosts, _, lane, item) in ROUTES.items():
            for host in hosts:
                mark = stub_mark(view_of(route, host))
                if mark is not None:
                    with self.subTest(route=route, host=host):
                        self.assertEqual(mark, (lane, item))


@override_settings(STORAGES=PLAIN_STATIC)
class StubAnswerTests(TestCase):
    """Each stub answers every caller - signed out, a member, an operator with the admin door's second factor - and
    every method exactly as an unknown URL on the same host answers the same caller. The one difference is the admin
    host's console routes: there a signed-out visitor goes to the operator sign-in first, as for every console route
    (studio.hosts.signed_out_to_sign_in), and the 404 for a signed-in account is compared by status and body only,
    because that redirect's check reads the session first (Vary: Cookie)."""

    def setUp(self):
        ws = f.workspace()
        self.member = f.member(ws)
        self.operator = f.user('platform-operator')
        ops.grant(self.operator)

    def callers(self, host):
        signed_out = Client(HTTP_HOST=host, enforce_csrf_checks=True)
        member = Client(HTTP_HOST=host, enforce_csrf_checks=True)
        member.force_login(self.member)
        ops.mark_signed_in(member, door=ops.door_of(host))
        operator = ops.client(self.operator, HTTP_HOST=host, enforce_csrf_checks=True)
        return {'signed out': signed_out, 'member': member, 'operator': operator}

    def stubs(self):
        found = []
        for route, (hosts, _, _, _) in ROUTES.items():
            for host in hosts:
                if stub_mark(view_of(route, host)) is not None:
                    found.append((route, host))
        return found

    def test_every_stub_answers_as_an_unknown_url(self):
        stubs = self.stubs()
        for host in URLCONF:
            for who, client in self.callers(host).items():
                for method in METHODS:
                    unknown = getattr(client, method)(UNKNOWN)
                    self.assertEqual(unknown.status_code, 404)
                    for route, stub_host in stubs:
                        if stub_host != host:
                            continue
                        console = host == ADMIN and route.startswith('ops/')
                        with self.subTest(route=route, host=host, caller=who, method=method):
                            answer = getattr(client, method)(concrete(route))
                            if console and who == 'signed out':
                                expected = ('302', '/login/?next=' + concrete(route).replace('/', '%2F')) \
                                    if method in ('get', 'head') else ('303', '/login/?next=%2Fops%2F')
                                self.assertEqual((str(answer.status_code), answer['Location']), expected)
                                continue
                            self.assertEqual(answer.status_code, 404)
                            self.assertEqual(answer.content, unknown.content)
                            self.assertEqual(answer.get('Content-Type'), unknown.get('Content-Type'))
                            if not console:
                                self.assertEqual(answer.get('Vary'), unknown.get('Vary'))

    def test_a_stub_is_never_reached_by_appending_a_slash(self):
        for host in URLCONF:
            client = self.callers(host)['member']
            for route, stub_host in self.stubs():
                if stub_host == host and route.endswith('/'):
                    with self.subTest(route=route, host=host):
                        self.assertEqual(client.get(concrete(route)[:-1]).status_code, 404)  # never a 301 to it

    def test_the_callers_are_signed_in_as_their_host_s_door(self):
        # the control for the comparisons above: a signed-in caller really is one, at its host's door
        for host in URLCONF:
            callers = self.callers(host)
            for who in ('member', 'operator'):
                with self.subTest(host=host, caller=who):
                    session = callers[who].session
                    self.assertTrue(session.get('_auth_user_id'))
                    self.assertEqual(session[request_meta.SESSION_DOOR], ops.door_of(host))
