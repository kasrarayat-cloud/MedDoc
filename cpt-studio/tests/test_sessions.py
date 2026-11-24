"""studio.sessions (release 1; RELEASE-1-SPEC 3.3): ending an account's sessions, moved from the console with an optional
session to keep (B4), and SessionPolicyMiddleware, which Lane 1 leaves a pass-through that binds the request for the
records (studio.request_meta.bound). Lane 2 fills the policy in (B3, B4, B5, B6, A2) and owns this file from then on: its
tests of the idle limit, the cap and the door join these. Synthetic data only."""
from __future__ import annotations

import uuid
from datetime import timedelta
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.models import Session
from django.http import Http404, JsonResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path
from django.utils import timezone

from studio import console, request_meta, sessions
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

REQUEST_ID = '0123456789abcdef0123456789abcdef'

# --- a probe view, served from this module's own urlconf (ROOT_URLCONF overridden), that reads what is bound -----------
SEEN = []


def probe(request):
    SEEN.append({'bound': request_meta.current_request() is request, 'fields': request_meta.request_fields()})
    return JsonResponse({'ok': True})


def missing(request):
    raise Http404()


urlpatterns = [path('probe', probe), path('missing', missing)]


@override_settings(ROOT_URLCONF=__name__, STORAGES=PLAIN_STATIC)
class SessionPolicyMiddlewareTests(TestCase):
    def setUp(self):
        SEEN.clear()

    def test_it_passes_the_request_and_the_response_through_unchanged(self):
        request = RequestFactory().get('/')
        sentinel = object()
        calls = []

        def get_response(passed):
            calls.append((passed, request_meta.current_request()))
            return sentinel
        self.assertIs(sessions.SessionPolicyMiddleware(get_response)(request), sentinel)
        self.assertEqual(calls, [(request, request)])  # once, with this request, bound while it ran
        self.assertIsNone(request_meta.current_request())  # and unbound after

    def test_an_exception_passes_through_and_the_request_is_unbound(self):
        def failing(passed):
            raise RuntimeError('synthetic failure')
        with self.assertRaisesMessage(RuntimeError, 'synthetic failure'):
            sessions.SessionPolicyMiddleware(failing)(RequestFactory().get('/'))
        self.assertIsNone(request_meta.current_request())

    def test_a_real_request_is_bound_with_its_fields_while_its_view_runs(self):
        user = f.member(f.workspace())
        client = Client()
        client.force_login(user)
        ops.mark_signed_in(client, door=request_meta.CPT)  # a release-1 sign-in at the cpt door, kept by the policy
        session = client.session
        ref = uuid.UUID(session[request_meta.SESSION_SIGN_IN_REF])
        response = client.get('/probe', REMOTE_ADDR='198.51.100.23', HTTP_X_REQUEST_ID=REQUEST_ID)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SEEN, [{'bound': True, 'fields': {'client': '198.51.100.23', 'sign_in_ref': ref,
                                                            'request_id': REQUEST_ID}}])
        self.assertIsNone(request_meta.current_request())
        self.assertEqual(Client().get('/missing').status_code, 404)  # an exception's answer is unchanged
        self.assertIsNone(request_meta.current_request())


class EndSessionsTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.other = f.member(self.ws)
        self.store = import_module(settings.SESSION_ENGINE).SessionStore

    def session_of(self, user, *, expired=False):
        store = self.store()
        store['_auth_user_id'] = str(user.pk)
        store.create()
        if expired:
            Session.objects.filter(session_key=store.session_key).update(
                expire_date=timezone.now() - timedelta(days=1))
        return store.session_key

    def keys(self):
        return set(Session.objects.values_list('session_key', flat=True))

    def test_the_console_s_function_moved_here_and_is_imported_back(self):
        self.assertIs(console.end_sessions, sessions.end_sessions)
        self.assertIs(console.Refused, sessions.Refused)
        self.assertEqual((console.SESSION_STORES, console.NO_SESSION_STORE),
                         (sessions.SESSION_STORES, sessions.NO_SESSION_STORE))

    def test_every_live_session_of_the_account_ends_and_no_other(self):
        mine = [self.session_of(self.user) for _ in range(3)]
        old = self.session_of(self.user, expired=True)
        theirs = self.session_of(self.other)
        self.assertEqual(sessions.end_sessions(self.user), 3)
        self.assertEqual(self.keys(), {old, theirs})
        self.assertFalse(set(mine) & self.keys())

    def test_keep_session_key_keeps_exactly_that_one(self):
        mine = [self.session_of(self.user) for _ in range(3)]
        theirs = self.session_of(self.other)
        self.assertEqual(sessions.end_sessions(self.user, keep_session_key=mine[1]), 2)
        self.assertEqual(self.keys(), {mine[1], theirs})
        # another account's session named as the one to keep keeps nothing of this account
        self.assertEqual(sessions.end_sessions(self.other, keep_session_key=mine[1]), 1)
        self.assertEqual(self.keys(), {mine[1]})

    def test_a_store_it_cannot_end_is_refused(self):
        with self.settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies'):
            with self.assertRaises(sessions.Refused) as refused:
                sessions.end_sessions(self.user, keep_session_key='x')
        self.assertEqual((str(refused.exception), refused.exception.status), (sessions.NO_SESSION_STORE, 409))
