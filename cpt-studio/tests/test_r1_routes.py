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
from django.views.decorators.common import no_append_slash
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from studio import request_meta
from studio.hosts import signed_out_to_sign_in
from studio.operator import operator_view
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


def wrapper_chain(callback):
    """The callback a URL resolves to, then every function it wraps (functools.wraps' __wrapped__), outermost first."""
    chain = [callback]
    while hasattr(chain[-1], '__wrapped__'):
        chain.append(chain[-1].__wrapped__)
    return chain


# the function Django's csrf_exempt wraps a view in, and operator_view's gate, whose own csrf_protect runs after the gate
CSRF_EXEMPT_WRAPPER = csrf_exempt(lambda request: None).__code__
OPERATOR_GATE = operator_view(lambda request: None).__code__


def csrf_check_skipped(callback) -> bool:
    """Whether an unsafe request that reaches ``callback`` is served without Django's CSRF check: a layer made by
    csrf_exempt anywhere in its chain (a stub's decorator left on the view that replaced it); behind operator_view, a
    view below the gate marked exempt (the gate's csrf_protect then skips it); else a callback marked exempt
    (CsrfViewMiddleware then skips it - the admin host's console wrapper is marked so, and only a gate inside checks)."""
    chain = wrapper_chain(callback)
    if any(getattr(layer, '__code__', None) is CSRF_EXEMPT_WRAPPER for layer in chain):
        return True
    gates = [index for index, layer in enumerate(chain) if getattr(layer, '__code__', None) is OPERATOR_GATE]
    if gates:
        return bool(getattr(chain[gates[0] + 1], 'csrf_exempt', False))
    return bool(getattr(callback, 'csrf_exempt', False))


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


@override_settings(STORAGES=PLAIN_STATIC)
class ReplacedViewTests(TestCase):
    """A lane that replaces a stub takes the stub's csrf_exempt away with it: every R1 view that is no longer a stub
    keeps Django's CSRF check - CsrfViewMiddleware's, before the view, or behind operator_view the gate's own
    csrf_protect, after it. Today every R1 view is a stub, so the sweep checks none; each lane's replacement is held to it
    the moment its stub comment goes."""

    def test_the_detector_reads_the_csrf_check_as_django_applies_it(self):
        def replaced(request):  # a lane's view, as its stub's place-taker
            return None
        marked = require_POST(replaced)
        marked.csrf_exempt = True
        caught = {
            "a stub's decorators left on the view": csrf_exempt(no_append_slash(replaced)),
            'csrf_exempt below the gate': operator_view(csrf_exempt(replaced)),
            'a view below the gate marked exempt': operator_view(marked),
            "the admin host's console wrapper with no gate inside": signed_out_to_sign_in(require_POST(replaced)),
            'a real exempt view (the admin front page)': resolve('/', urlconf=URLCONF[ADMIN]).func,
        }
        kept = {
            'a plain view': require_POST(replaced),
            'a view behind the gate': operator_view(require_POST(replaced)),
            'the admin host console wrapper around the gate': signed_out_to_sign_in(operator_view(require_POST(replaced))),
            'a real console act (cpt host)': resolve(concrete('ops/people/<uuid:user_id>/role'), urlconf=URLCONF[CPT]).func,
            'a real console act (admin host)': resolve(concrete('ops/people/<uuid:user_id>/role'),
                                                       urlconf=URLCONF[ADMIN]).func,
            'a real customer route': resolve('/api/encounters', urlconf=URLCONF[CPT]).func,
        }
        for label, callback in caught.items():
            with self.subTest(label=label):
                self.assertTrue(csrf_check_skipped(callback))
        for label, callback in kept.items():
            with self.subTest(label=label):
                self.assertFalse(csrf_check_skipped(callback))

    def test_where_the_detector_sees_the_check_django_refuses_a_post_without_a_token(self):
        # the behavioural control for a "kept" reading: an operator who passed the admin door's second factor posting a
        # real console act with no CSRF token is refused 403 - the gate's csrf_protect ran
        operator = f.user('platform-operator')
        member = f.member(f.workspace())
        client = ops.client(operator, HTTP_HOST=ADMIN, enforce_csrf_checks=True)
        answer = client.post(f'/ops/people/{member.pk}/role', {'role': 'viewer'})
        self.assertEqual(answer.status_code, 403)

    def test_a_replaced_view_keeps_the_csrf_check(self):
        for route, (route_hosts, _, _, _) in ROUTES.items():
            for host in route_hosts:
                callback = resolve(concrete(route), urlconf=URLCONF[host]).func
                if stub_mark(inspect.unwrap(callback)) is not None:
                    continue  # still a stub: exempt by design, and held to the unknown URL's 404 (StubAnswerTests)
                with self.subTest(route=route, host=host):
                    self.assertFalse(csrf_check_skipped(callback))
