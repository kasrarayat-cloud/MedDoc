"""studio.sessions (release 1; RELEASE-1-SPEC 3.3, B3, B5, B6, A2): ending an account's sessions (moved from the console,
with one session to keep for B4), the keys every sign-in writes into its session, and SessionPolicyMiddleware - the idle
limit and the cap (B5), the door a session is bound to (B3), the deletion of the cookies' old names (B6), X-CPT-Actor
(A2) and the binding of every request for the records (C1). The forced password change's gate is tests/test_account.py's.
The clock is patched (tests.test_second_factor.Clock), so no test waits. Synthetic data only."""
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

from studio import console, models, request_meta, sessions
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import ADMIN, CPT, MOMENT, NOW, Clock

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


# --- the policy (Lane 2) ------------------------------------------------------------------------------------------------

def member_client(ws=None, **kwargs):
    """A member signed in now (a test client's own sign-in: studio.sessions writes the cpt door's keys)."""
    user = f.member(ws or f.workspace())
    client = Client(**kwargs)
    client.force_login(user)
    return user, client


def session_row(client):
    return Session.objects.filter(session_key=client.session.session_key)


@override_settings(STORAGES=PLAIN_STATIC)
class SignInKeysTests(TestCase):
    def test_every_login_writes_the_keys_of_a_sign_in_and_never_a_second_factor(self):
        with Clock():
            _, client = member_client()
            session = client.session
            self.assertEqual([session[name] for name in (request_meta.SESSION_DOOR, request_meta.SESSION_AUTH_AT,
                                                         request_meta.SESSION_LAST_ACTIVE)], ['cpt', NOW, NOW])
            uuid.UUID(session[request_meta.SESSION_SIGN_IN_REF])
            self.assertNotIn(request_meta.SESSION_SECOND_FACTOR_AT, session)
            # the doors name their own door and the attempt's reference: the session's is its LoginAttempt's
            user = f.member(f.workspace())
            door = Client()
            self.assertEqual(door.post('/login/', {'username': user.username, 'password': 'synthetic-pass-123!'})
                             .status_code, 302)
            attempt = models.LoginAttempt.objects.get(username=user.username)
            self.assertEqual(door.session[request_meta.SESSION_SIGN_IN_REF], str(attempt.sign_in_ref))
            self.assertEqual(door.session[request_meta.SESSION_DOOR], 'cpt')

    def test_a_new_sign_in_drops_an_earlier_second_factor(self):
        operator = f.user('dual-role')
        client = ops.admin_client(operator)
        self.assertIn(request_meta.SESSION_SECOND_FACTOR_AT, client.session)
        client.force_login(operator)  # the same account signs in again on this browser
        self.assertNotIn(request_meta.SESSION_SECOND_FACTOR_AT, client.session)


@override_settings(STORAGES=PLAIN_STATIC)
class IdleAndCapTests(TestCase):
    """B5: a session ends after its idle limit or its cap, before the view runs."""

    def test_after_the_idle_limit_the_api_answers_401_and_the_session_row_is_gone(self):
        with Clock() as clock:
            _, kept = member_client()
            _, idle = member_client()
            clock.advance(settings.SESSION_IDLE_MEMBER_SECONDS)  # exactly the limit: still signed in
            self.assertEqual(kept.get('/api/session').status_code, 200)
            clock.advance(1)
            answer = idle.get('/api/session')  # 901 seconds since its last activity
            self.assertEqual((answer.status_code, answer.json()), (401, {'error': 'signed_out', 'reason': 'idle'}))
            self.assertFalse(session_row(idle).exists())
            self.assertEqual(idle.get('/api/session').status_code, 401)  # and it never comes back

    def test_polls_never_keep_a_session_alive_and_the_ping_does(self):
        with Clock() as clock:
            _, polled = member_client()
            _, pinged = member_client()
            ended_after = None
            for step in range(1, 41):  # every 30 seconds for 20 minutes
                clock.advance(30)
                if polled.get('/api/session', HTTP_X_CPT_POLL='1').status_code == 401 and ended_after is None:
                    ended_after = step * 30
                self.assertEqual(pinged.get('/api/session', HTTP_X_CPT_POLL='1').status_code, 200, step)
                if step % 2 == 0:
                    self.assertEqual(pinged.post('/session/activity').status_code, 200, step)
            self.assertEqual(ended_after, 930)  # the first poll past 900 seconds without activity

    def test_the_cap_ends_a_session_at_eight_hours_even_with_steady_activity(self):
        with Clock() as clock:
            _, client = member_client()
            for _ in range(settings.SESSION_MAX_MEMBER_SECONDS // 600):  # something done every ten minutes
                clock.advance(600)
                self.assertEqual(client.get('/api/session').status_code, 200)
            clock.advance(1)
            answer = client.get('/api/session')
            self.assertEqual(answer.status_code, 401)
            self.assertEqual(answer.json(), {'error': 'signed_out', 'reason': 'expired'})
            self.assertFalse(session_row(client).exists())

    def test_an_operator_is_signed_out_after_601_seconds_on_the_admin_host(self):
        with Clock() as clock:
            kept = ops.admin_client(f.user('operator-kept'))
            idle = ops.admin_client(f.user('operator-idle'))
            clock.advance(settings.SESSION_IDLE_OPERATOR_SECONDS)
            self.assertEqual(kept.get('/ops/').status_code, 200)
            clock.advance(1)
            answer = idle.get('/ops/')
            self.assertEqual(answer.status_code, 302)
            self.assertEqual(answer['Location'], '/login/?next=%2Fops%2F&reason=idle')
            self.assertFalse(session_row(idle).exists())
            page = idle.get(answer['Location']).content.decode()
            self.assertIn(f'You were signed out after {settings.SESSION_IDLE_OPERATOR_SECONDS // 60} minutes without '
                          'activity.', page)

    def test_a_session_from_before_release_one_is_refused(self):
        for strip in (request_meta.SESSION_KEYS, (request_meta.SESSION_AUTH_AT,), (request_meta.SESSION_SIGN_IN_REF,)):
            with self.subTest(strip=strip):
                _, api = member_client()
                session = api.session
                for name in strip:
                    session.pop(name, None)
                session.save()
                answer = api.get('/api/session')
                self.assertEqual((answer.status_code, answer.json()), (401, {'error': 'signed_out', 'reason': 'expired'}))
                self.assertFalse(Session.objects.filter(session_key=session.session_key).exists())
        _, page = member_client()
        session = page.session
        for name in request_meta.SESSION_KEYS:
            session.pop(name, None)
        session.save()
        answer = page.get('/')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?next=%2F&reason=expired'))
        self.assertIn('Your session has ended. Sign in again.', page.get(answer['Location']).content.decode())

    def test_a_timestamp_from_the_future_is_no_timestamp_of_this_release(self):
        with Clock() as clock:
            _, client = member_client()
        with Clock(MOMENT - timedelta(minutes=1)):  # the clock went back: the session's keys are of no past moment
            self.assertEqual(client.get('/api/session').status_code, 401)

    def test_the_last_activity_is_written_at_most_once_a_minute_and_never_by_a_poll(self):
        with Clock() as clock:
            _, client = member_client()
            last = lambda: client.session[request_meta.SESSION_LAST_ACTIVE]  # noqa: E731
            clock.advance(30)
            client.get('/api/session')
            self.assertEqual(last(), NOW)
            clock.advance(31)
            client.get('/api/session')
            self.assertEqual(last(), NOW + 61)
            clock.advance(200)
            client.get('/api/session', HTTP_X_CPT_POLL='1')
            self.assertEqual(last(), NOW + 61)

    def test_the_ping_answers_the_time_left(self):
        with Clock() as clock:
            _, client = member_client()
            clock.advance(30)
            answer = client.post('/session/activity')
            self.assertEqual(answer.json(), {'idle_seconds': settings.SESSION_IDLE_MEMBER_SECONDS - 30,
                                             'cap_seconds': settings.SESSION_MAX_MEMBER_SECONDS - 30,
                                             'warning_seconds': settings.SESSION_IDLE_WARNING_SECONDS})
            clock.advance(60)
            self.assertEqual(client.post('/session/activity').json()['idle_seconds'], settings.SESSION_IDLE_MEMBER_SECONDS)
        anonymous = Client().post('/session/activity')
        self.assertEqual((anonymous.status_code, anonymous.json()['error']), (401, 'signed_out'))
        self.assertEqual(Client().get('/session/activity').status_code, 405)

    def test_the_page_s_own_sign_out_after_inactivity_lands_on_the_sentence(self):
        _, client = member_client()
        answer = client.post('/logout/?reason=idle')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?reason=idle'))
        self.assertIsNone(client.session.get('_auth_user_id'))
        _, plain = member_client()
        self.assertEqual(plain.post('/logout/')['Location'], '/login/')
        self.assertIn('You were signed out after 15 minutes without activity.', Client().get('/login/?reason=idle')
                      .content.decode())


@override_settings(STORAGES=PLAIN_STATIC)
class DoorTests(TestCase):
    """B3: a session is bound to the door it was opened at."""

    def test_a_session_taken_to_the_other_host_is_ended(self):
        operator = f.user('platform-operator')
        admin = ops.admin_client(operator)
        on_cpt = Client(HTTP_HOST=CPT)
        on_cpt.cookies = admin.cookies
        answer = on_cpt.get('/api/session')
        self.assertEqual((answer.status_code, answer.json()['reason']), (401, 'expired'))
        self.assertEqual(admin.get('/ops/').status_code, 302)  # the session is gone for its own host too
        _, cpt = member_client(HTTP_HOST=CPT)
        on_admin = Client(HTTP_HOST=ADMIN)
        on_admin.cookies = cpt.cookies
        answer = on_admin.get('/ops/people')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?next=%2Fops%2Fpeople&reason=expired'))
        self.assertEqual(cpt.get('/api/session').status_code, 401)


@override_settings(STORAGES=PLAIN_STATIC)
class CookieAndHeaderTests(TestCase):
    HTTPS_NAMES = dict(SESSION_COOKIE_NAME='__Host-cptstudio_session', CSRF_COOKIE_NAME='__Host-cptstudio_csrf',
                       SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)

    def test_the_old_cookie_names_are_deleted_under_https(self):
        with self.settings(**self.HTTPS_NAMES):
            client = Client()
            client.cookies['cptstudio_session'] = 'a-session-before-release-one'
            client.cookies['cptstudio_csrf'] = 'a-token-before-release-one'
            answer = client.get('/login/', secure=True)
        for name in sessions.OLD_COOKIE_NAMES:
            with self.subTest(name=name):
                self.assertIn(name, answer.cookies)
                cookie = answer.cookies[name]
                self.assertEqual((cookie.value, cookie['max-age'], cookie['path']), ('', 0, '/'))
                self.assertTrue(cookie['secure'])
        self.assertIn('__Host-cptstudio_csrf', answer.cookies)
        # without HTTPS the plain names are this site's own: never deleted
        _, plain = member_client()
        answer = plain.get('/api/session')
        self.assertNotIn(settings.SESSION_COOKIE_NAME, answer.cookies)
        self.assertEqual(answer.status_code, 200)

    def test_a_signed_in_response_names_its_sign_in_and_an_anonymous_one_nothing(self):
        _, client = member_client()
        answer = client.get('/api/session')
        self.assertEqual(answer[sessions.ACTOR_HEADER], client.session[request_meta.SESSION_SIGN_IN_REF])
        self.assertNotIn(sessions.ACTOR_HEADER, Client().get('/login/'))
        self.assertNotIn(sessions.ACTOR_HEADER, Client().get('/api/session'))
        user = f.member(f.workspace())
        signed = Client().post('/login/', {'username': user.username, 'password': 'synthetic-pass-123!'})
        attempt = models.LoginAttempt.objects.get(username=user.username)
        self.assertEqual(signed[sessions.ACTOR_HEADER], str(attempt.sign_in_ref))

    def test_a_request_without_a_session_cookie_never_reads_a_session(self):
        unknown = Client().get('/r1-no-such-route')
        self.assertIsNone(unknown.get('Vary'))  # an unknown URL to a stranger, as before release 1
        self.assertEqual(Client().get('/health/').status_code, 200)
