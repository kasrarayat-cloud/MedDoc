"""Every route of both urlconfs is classified (release 1, C1 item 10; TEC-9 (7)): its view is marked
studio.read_audit.phi_read(kind) with the kind this file expects - and records it (tests/test_read_audit.py holds each
kind's row) - or is listed in NO_PHI_ROUTES with the reason it reads no PHI. A route whose view is neither fails here,
so a new route cannot reach main unclassified. Lane 4's bundle (D2) is listed as Lane 4's: its stub answers 404 to
everyone until studio/bundle_api.py replaces it, and from then on it must carry its mark. Synthetic data only."""
import inspect
import re

from django.test import SimpleTestCase
from django.urls import get_resolver

from studio import read_audit

URLCONFS = ('cptstudio.urls', 'cptstudio.urls_admin')

# Each view that reads PHI, by its dotted name, and the kind its phi_read mark names.
PHI_ROUTES = {
    'studio.api.encounters': read_audit.MEMBER_LIST,
    'studio.api.encounter_detail': read_audit.MEMBER_DETAIL,
    'studio.api.original': read_audit.MEMBER_DOWNLOAD,  # and member.inline, for view=1
    'studio.api.download_report': read_audit.MEMBER_REPORT_DOWNLOAD,
    'studio.operator.index': read_audit.OPS_LIST,
    'studio.operator.encounter_page': read_audit.OPS_DETAIL,
    'studio.operator.content_open': read_audit.OPS_CONTENT_OPEN,
    'studio.operator.original': read_audit.OPS_ORIGINAL,
    'studio.console.workspace_page': read_audit.OPS_WORKSPACE,
    'studio.console.spending_page': read_audit.OPS_SPENDING,
    'studio.console.activity': read_audit.OPS_ACTIVITY,
    'studio.console.reads': read_audit.OPS_READS,
}
# Views another lane owns that read PHI: (kind, lane, item). Accepted unmarked only while still that lane's R1 stub.
OTHER_LANES = {
    'studio.bundle_api.encounter_bundle': (read_audit.MEMBER_BUNDLE_DOWNLOAD, 4, 'D2'),
}
ACT = 'an act: it changes something and answers a redirect, a status or the act\'s own result, never a document'
NO_PHI_ROUTES = {
    # the doctors' host
    'studio.views.index': 'the doctors\' app shell: the page and its scripts; every document it shows comes through '
                          'the API\'s recorded reads',
    'studio.views.health': 'the service\'s health: no account and no data',
    'studio.views.login_view': 'the sign-in page',
    'studio.views.logout_view': 'signing out: it ends the session and redirects',
    'studio.views.account_security': 'the account\'s own password and sign-ins (Lane 2, B4)',
    'studio.views.logout_everywhere': 'ending the account\'s own sessions (Lane 2, B4)',
    'studio.views.activity_ping': 'the session\'s activity time (Lane 2, B5)',
    'studio.api.session': 'who is signed in, the practice\'s name and specialty, and counts: no document',
    'studio.api.answers': f'{ACT} (the answers a member sends; it answers the new round\'s number)',
    'studio.api.decide': f'{ACT} (one decision; it answers that decision)',
    'studio.api.stop': ACT,
    'studio.api.resume': ACT,
    'studio.api.retry': ACT,
    'studio.api.create_report': f'{ACT} (a report is made; its content is read through download_report, recorded)',
    'studio.api.members': 'the practice\'s people - names, roles, access and last sign-in - and no document (C4)',
    'studio.api.member_access': f'{ACT} (one person\'s access in this practice; C4)',
    # the console (both hosts; it answers only on the admin host)
    'studio.operator.reconcile': ACT,
    'studio.operator.retry': ACT,
    'studio.operator.release_holds': ACT,
    'studio.console.people': 'the accounts, their roles and access: no document',
    'studio.console.add_person': f'{ACT} (the new person\'s one-time password; a refusal answering a practice\'s page '
                                 'records that read as ops.workspace first)',
    'studio.console.set_role': f'{ACT} (a refusal answering a practice\'s page records that read first)',
    'studio.console.reset_password': f'{ACT} (the new one-time password; a refusal records a practice\'s page first)',
    'studio.console.set_access': f'{ACT} (a refusal answering a practice\'s page records that read first)',
    'studio.console.unlock_sign_in': f'{ACT} (a sign-in delay cleared; B1)',
    'studio.console.workspaces': 'the practices with their counts: no document',
    'studio.console.create_workspace': ACT,
    'studio.console.sign_ins': 'sign-in attempts - names of accounts, addresses and outcomes - and no document',
    'studio.second_factor_views.keys': 'the operator\'s own security keys (Lane 2, B2)',
    # the admin host's own routes
    'studio.views.admin_home': 'a redirect to the console or the sign-in',
    'studio.views.admin_ops_slash': 'a redirect to /ops/',
    'studio.views.admin_login_view': 'the operator sign-in page',
    'studio.second_factor_views.second_factor': 'the second factor at sign-in (Lane 2, B2)',
    'studio.second_factor_views.second_factor_options': 'the second factor\'s challenge (Lane 2, B2)',
    'studio.second_factor_views.enrol': 'enrolling a key with a setup code (Lane 2, B2)',
    'studio.second_factor_views.enrol_options': 'the enrolment\'s challenge (Lane 2, B2)',
    'studio.second_factor_views.recovery': 'a recovery code at sign-in (Lane 2, B2)',
}
STUB_COMMENT = re.compile(r'# R1 stub: Lane (\d) replaces this \(([A-Z]\d+)\)\n')
RECORDING = re.compile(r'\b(?:_recorded|_record|read_audit\.record)\(')


def chain(callback):
    """The callback a URL resolves to, then every function it wraps (functools.wraps' __wrapped__), outermost first."""
    layers = [callback]
    while hasattr(layers[-1], '__wrapped__'):
        layers.append(layers[-1].__wrapped__)
    return layers


def mark_of(callback):
    """The phi_read kind anywhere in ``callback``'s chain, or None."""
    return next((read_audit.read_kind(layer) for layer in chain(callback) if read_audit.read_kind(layer)), None)


def routes():
    """(urlconf, route, the view's dotted name, the callback) for every route of both urlconfs."""
    out = []
    for urlconf in URLCONFS:
        for pattern in get_resolver(urlconf).url_patterns:
            view = inspect.unwrap(pattern.callback)
            out.append((urlconf, str(pattern.pattern), f'{view.__module__}.{view.__qualname__}', pattern.callback))
    return out


class RouteCoverageTests(SimpleTestCase):
    def test_every_route_is_marked_with_its_kind_or_listed_as_reading_no_phi(self):
        seen = set()
        for urlconf, route, name, callback in routes():
            seen.add(name)
            mark = mark_of(callback)
            with self.subTest(urlconf=urlconf, route=route, view=name):
                if name in PHI_ROUTES:
                    self.assertEqual(mark, PHI_ROUTES[name])
                elif name in OTHER_LANES:
                    kind, lane, item = OTHER_LANES[name]
                    stub = STUB_COMMENT.fullmatch(inspect.getcomments(inspect.unwrap(callback)) or '')
                    if stub is None:  # replaced by its lane: it must carry its mark from then on
                        self.assertEqual(mark, kind)
                    else:
                        self.assertEqual((int(stub.group(1)), stub.group(2)), (lane, item))
                        self.assertIsNone(mark)
                else:
                    self.assertIn(name, NO_PHI_ROUTES, 'a route that is neither marked phi_read nor listed in '
                                                       'NO_PHI_ROUTES with a reason')
                    self.assertIsNone(mark, 'a view listed as reading no PHI carries a phi_read mark')
        # no entry names a view that no longer has a route (a stale entry would hide a removed classification)
        self.assertEqual(set(PHI_ROUTES) - seen, set())
        self.assertEqual(set(NO_PHI_ROUTES) - seen, set())
        self.assertEqual(set(OTHER_LANES) - seen, set())

    def test_every_kind_is_routed_and_every_reason_is_a_sentence(self):
        kinds = set(PHI_ROUTES.values()) | {kind for kind, _lane, _item in OTHER_LANES.values()} | {
            read_audit.MEMBER_INLINE}  # api.original's view=1
        self.assertEqual(kinds, set(read_audit.VIEW_KINDS))
        for name, reason in NO_PHI_ROUTES.items():
            with self.subTest(view=name):
                self.assertGreater(len(reason.split()), 2)

    def test_every_marked_view_records_its_read(self):
        # the marks are honest: each marked view's own code writes its row (each kind's row is held behaviourally in
        # tests/test_read_audit.py; this catches a view marked and never recording)
        for _urlconf, route, name, callback in routes():
            if name in PHI_ROUTES:
                with self.subTest(route=route, view=name):
                    self.assertRegex(inspect.getsource(inspect.unwrap(callback)), RECORDING)

    def test_the_detector_finds_a_mark_through_every_wrapper(self):
        from django.views.decorators.http import require_GET
        from studio.hosts import signed_out_to_sign_in
        from studio.operator import _methods, operator_view

        def fresh():  # phi_read marks the function it is given, so each case gets its own
            def view(request):
                return None
            return view
        marked = signed_out_to_sign_in(operator_view(_methods('GET')(read_audit.phi_read(read_audit.OPS_LIST)(fresh()))))
        self.assertEqual(mark_of(marked), read_audit.OPS_LIST)
        self.assertEqual(mark_of(require_GET(read_audit.phi_read(read_audit.MEMBER_DETAIL)(fresh()))),
                         read_audit.MEMBER_DETAIL)
        self.assertIsNone(mark_of(signed_out_to_sign_in(operator_view(_methods('GET')(fresh())))))
