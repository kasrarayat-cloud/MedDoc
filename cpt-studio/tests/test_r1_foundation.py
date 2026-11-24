"""Release 1's foundation (RELEASE-1-SPEC section 3, Lane 1): the settings every lane reads, the request's own facts
(studio.request_meta), ending sessions and the session policy's pass-through (studio.sessions). Synthetic data only."""
from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from importlib import import_module
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path
from django.utils import timezone

from studio import console, models, request_meta, sessions, views
from tests.support import coding as f
from tests.test_frontend import PLAIN_STATIC

ROOT = Path(__file__).resolve().parents[1]
ADMIN = 'admin.quillmd.com'
REQUEST_ID = '0123456789abcdef0123456789abcdef'

# --- a probe view, served from this module's own urlconf (ROOT_URLCONF overridden), that reads what is bound -----------
SEEN = []


def probe(request):
    SEEN.append({'bound': request_meta.current_request() is request, 'fields': request_meta.request_fields()})
    return JsonResponse({'ok': True})


def missing(request):
    raise Http404()


urlpatterns = [path('probe', probe), path('missing', missing)]


def load_settings(**environment):
    """cptstudio/settings.py executed afresh under ``environment`` added to this process's (the module the deployment
    reads; django.conf.settings itself is untouched)."""
    spec = importlib.util.spec_from_file_location(f'r1_settings_{uuid.uuid4().hex}', ROOT / 'cptstudio' / 'settings.py')
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, environment):
        spec.loader.exec_module(module)
    return module


class PolicySettingsTests(SimpleTestCase):
    """The owner decisions stand at the specification's recommended answers (RELEASE-1-SPEC section 8)."""

    def test_the_policy_values_are_the_recommended_answers(self):
        expected = {
            'SESSION_IDLE_MEMBER_SECONDS': 900, 'SESSION_IDLE_OPERATOR_SECONDS': 600,  # D1
            'SESSION_MAX_MEMBER_SECONDS': 28800, 'SESSION_MAX_OPERATOR_SECONDS': 28800,  # D1
            'SESSION_IDLE_WARNING_SECONDS': 120, 'SESSION_ACTIVITY_WRITE_SECONDS': 60,
            'SIGNIN_WINDOW_SECONDS': 900, 'SIGNIN_PAIR_LIMIT': 10, 'SIGNIN_USER_DELAY_AFTER': 5,  # D6
            'SIGNIN_DELAY_BASE_SECONDS': 30, 'SIGNIN_DELAY_MAX_SECONDS': 900, 'SIGNIN_CLIENT_LIMIT': 50,
            'KNOWN_DEVICE_DAYS': 90,  # D23
            'PASSWORD_MIN_LENGTH': 15,  # D26
            'STAFF_PASSWORD_UNUSED_SECONDS': 259200,  # D31
            'WEBAUTHN_RP_ID': 'admin.quillmd.com', 'WEBAUTHN_ORIGIN': 'https://admin.quillmd.com',
            'WEBAUTHN_RP_NAME': 'CPT Studio console',
            'SECOND_FACTOR_PENDING_SECONDS': 300, 'SECOND_FACTOR_STEP_UP_SECONDS': 300,  # D3
            'SECOND_FACTOR_ATTEMPTS': 5, 'ENROLMENT_CODE_SECONDS': 1800, 'RECOVERY_CODE_COUNT': 10,
            'READ_AUDIT_DETAIL_DEDUPE_SECONDS': 60, 'CONTENT_GRANT_SECONDS': 900,  # D24
            'EXPORT_LIMIT_PER_MEMBER': (10, 600), 'EXPORT_LIMIT_PER_WORKSPACE': (60, 3600),  # D8
            'UPLOAD_LIMIT_PER_MEMBER': (30, 600), 'BUNDLE_LIMIT_PER_MEMBER': (10, 600),
            'BUNDLE_MAX_BYTES': 24 * 1024 * 1024,
            'FILES_ENCRYPTION': 'off', 'MALWARE_SCAN': 'off',  # D16, D18
            'HEALTH_DIGEST_PREFIX': 'cpt-studio-release:',
        }
        for name, value in expected.items():
            with self.subTest(setting=name):
                self.assertEqual(getattr(settings, name), value)

    def test_the_paths_come_from_the_environment_and_default_to_nothing(self):
        plain = load_settings()
        self.assertEqual((plain.CONVERTER_SOCKET, plain.CONVERTER_REQUIRED, plain.FILES_KEK_FILE, plain.CLAMD_SOCKET),
                         ('', False, '', ''))
        named = load_settings(CPT_STUDIO_CONVERTER_SOCKET='/run/cpt-converter/socket', CPT_STUDIO_CONVERTER_REQUIRED='1',
                              CPT_STUDIO_FILES_KEK_FILE='/run/cpt-studio/files-kek.env',
                              CPT_STUDIO_CLAMD_SOCKET='/run/clamd/socket')
        self.assertEqual((named.CONVERTER_SOCKET, named.CONVERTER_REQUIRED, named.FILES_KEK_FILE, named.CLAMD_SOCKET),
                         ('/run/cpt-converter/socket', True, '/run/cpt-studio/files-kek.env', '/run/clamd/socket'))
        # the two switches are constants of the release: no variable turns either on
        switched = load_settings(CPT_STUDIO_FILES_ENCRYPTION='on', CPT_STUDIO_MALWARE_SCAN='on')
        self.assertEqual((switched.FILES_ENCRYPTION, switched.MALWARE_SCAN), ('off', 'off'))

    def test_the_session_policy_sits_directly_after_authentication(self):
        position = settings.MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        self.assertEqual(settings.MIDDLEWARE[position + 1], 'studio.sessions.SessionPolicyMiddleware')
        self.assertEqual(settings.MIDDLEWARE.count('studio.sessions.SessionPolicyMiddleware'), 1)


class PasswordLengthTests(TestCase):
    def test_fourteen_characters_are_refused_and_fifteen_accepted_when_a_password_is_set(self):
        user = models.User(username='synthetic-length')
        with self.assertRaises(ValidationError) as refused:
            validate_password('kq7vz2mw9rtxbnh'[:14], user)
        self.assertIn('at least 15 characters', ' '.join(refused.exception.messages))
        validate_password('kq7vz2mw9rtxbnh', user)  # 15: accepted

    def test_the_validators_never_run_at_sign_in(self):
        # a password set before the minimum rose still signs in: validators apply where a password is set
        user = f.member(f.workspace())
        user.set_password('short-but-old')  # 13 characters, set directly as an older release could have
        user.save()
        answer = Client().post('/login/', {'username': user.username, 'password': 'short-but-old'})
        self.assertEqual((answer.status_code, answer['Location']), (302, '/'))


@override_settings(STORAGES=PLAIN_STATIC)
class CookieNameTests(TestCase):
    """B6: under HTTPS both cookies carry the __Host- prefix, Secure, Path=/ and no Domain; without it they keep today's
    names, which is what every test and the loopback port see."""

    def test_without_https_the_names_are_unchanged(self):
        module = load_settings(CPT_STUDIO_HTTPS='0')
        self.assertEqual((module.SESSION_COOKIE_NAME, module.CSRF_COOKIE_NAME), ('cptstudio_session', 'cptstudio_csrf'))
        self.assertEqual((settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME),
                         ('cptstudio_session', 'cptstudio_csrf'))

    def test_under_https_both_names_take_the_host_prefix_and_its_conditions(self):
        module = load_settings(CPT_STUDIO_HTTPS='1')
        self.assertEqual((module.SESSION_COOKIE_NAME, module.CSRF_COOKIE_NAME),
                         ('__Host-cptstudio_session', '__Host-cptstudio_csrf'))
        self.assertTrue(module.SESSION_COOKIE_SECURE and module.CSRF_COOKIE_SECURE)
        for name in ('SESSION_COOKIE_DOMAIN', 'CSRF_COOKIE_DOMAIN', 'SESSION_COOKIE_PATH', 'CSRF_COOKIE_PATH'):
            with self.subTest(setting=name):
                self.assertFalse(hasattr(module, name), f'{name} must stay Django\'s default (no domain, path /)')
        # and the cookies a browser receives, with those settings in force
        cookie_settings = {name: getattr(module, name) for name in (
            'SESSION_COOKIE_NAME', 'CSRF_COOKIE_NAME', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE')}
        member = f.member(f.workspace())
        with self.settings(**cookie_settings):
            client = Client()
            page = client.get('/login/', secure=True)
            signed = client.post('/login/', {'username': member.username, 'password': 'synthetic-pass-123!'},
                                 secure=True)
        self.assertEqual(signed.status_code, 302)
        for response, name in ((page, '__Host-cptstudio_csrf'), (signed, '__Host-cptstudio_session')):
            with self.subTest(cookie=name):
                cookie = response.cookies[name]
                self.assertTrue(cookie['secure'])
                self.assertEqual(cookie['path'], '/')
                self.assertEqual(cookie['domain'], '')


class RequestMetaTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_client_address_is_views_client_moved_unchanged(self):
        self.assertIs(views._client, request_meta.client_address)
        request = self.factory.get('/', REMOTE_ADDR='198.51.100.7', HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1')
        self.assertEqual(request_meta.client_address(request), '198.51.100.7')  # the header is never trusted alone
        with self.settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')):
            self.assertEqual(request_meta.client_address(request), '203.0.113.9')  # behind the proxy: its header
            self.assertEqual(request_meta.client_address(self.factory.get('/', REMOTE_ADDR='192.0.2.1')), '192.0.2.1')
        long = self.factory.get('/', REMOTE_ADDR='x' * 90)
        self.assertEqual(len(request_meta.client_address(long)), 64)

    def test_client_key_is_the_ipv4_address_or_the_ipv6_slash_64(self):
        cases = {
            '203.0.113.9': '203.0.113.9',
            '2001:db8:1:2:3:4:5:6': '2001:db8:1:2::/64',
            '2001:db8:1:2:ffff:ffff:ffff:ffff': '2001:db8:1:2::/64',  # the same subscriber's network: one key
            '2001:db8:1:3::1': '2001:db8:1:3::/64',  # the next /64: another key
            '::ffff:198.51.100.7': '198.51.100.7',  # an IPv4-mapped address counts as its IPv4 address
            'fe80::1%eth0': 'fe80::/64',
        }
        for address, key in cases.items():
            with self.subTest(address=address):
                self.assertEqual(request_meta.client_key(self.factory.get('/', REMOTE_ADDR=address)), key)

    def test_request_id_is_nginx_s_32_hex_or_nothing(self):
        def rid(value):
            return request_meta.request_id(self.factory.get('/', HTTP_X_REQUEST_ID=value))
        self.assertEqual(rid(REQUEST_ID), REQUEST_ID)
        self.assertEqual(rid(REQUEST_ID.upper()), REQUEST_ID)
        for value in ('', REQUEST_ID[:-1], REQUEST_ID + '0', 'g' * 32, REQUEST_ID[:31] + 'é',
                      REQUEST_ID[:16] + ' ' * 16, 'not-a-request-id'):
            with self.subTest(value=value):
                self.assertEqual(rid(value), '')
        self.assertEqual(request_meta.request_id(self.factory.get('/')), '')

    def test_sign_in_ref_reads_the_session_and_nothing_else(self):
        ref = uuid.uuid4()
        request = self.factory.get('/')
        self.assertIsNone(request_meta.sign_in_ref(request))  # no session at all
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        self.assertIsNone(request_meta.sign_in_ref(request))
        for value, expected in ((str(ref), ref), (ref, ref), ('not-a-uuid', None), (12, None), ('', None)):
            with self.subTest(value=value):
                request.session[request_meta.SESSION_SIGN_IN_REF] = value
                self.assertEqual(request_meta.sign_in_ref(request), expected)

    def test_host_kind_and_the_poll_mark(self):
        self.assertEqual(request_meta.host_kind(self.factory.get('/', HTTP_HOST=ADMIN)), request_meta.ADMIN)
        self.assertEqual(request_meta.host_kind(self.factory.get('/', HTTP_HOST=f'{ADMIN}:443')), request_meta.ADMIN)
        self.assertEqual(request_meta.host_kind(self.factory.get('/', HTTP_HOST='cpt.quillmd.com')), request_meta.CPT)
        self.assertEqual(request_meta.host_kind(self.factory.get('/')), request_meta.CPT)
        self.assertTrue(request_meta.is_poll(self.factory.get('/', HTTP_X_CPT_POLL='1')))
        for value in (None, '0', 'true', ' 1'):
            with self.subTest(value=value):
                headers = {} if value is None else {'HTTP_X_CPT_POLL': value}
                self.assertFalse(request_meta.is_poll(self.factory.get('/', **headers)))

    def test_the_session_keys_and_their_timestamps(self):
        self.assertEqual(request_meta.SESSION_KEYS,
                         ('cpt_door', 'cpt_2fa_at', 'cpt_auth_at', 'cpt_last_active', 'cpt_sign_in_ref'))
        moment = datetime(2026, 11, 24, 12, 0, 30, 999999, tzinfo=dt_timezone.utc)
        self.assertEqual(request_meta.epoch_seconds(moment), 1795521630)
        with mock.patch.object(timezone, 'now', return_value=moment):
            self.assertEqual(request_meta.epoch_seconds(), 1795521630)
        self.assertIsInstance(request_meta.epoch_seconds(), int)

    def test_fields_outside_a_request_are_empty(self):
        self.assertIsNone(request_meta.current_request())
        self.assertEqual(request_meta.request_fields(), {'client': '', 'sign_in_ref': None, 'request_id': ''})
        request = self.factory.get('/', REMOTE_ADDR='192.0.2.\x00', HTTP_X_REQUEST_ID=REQUEST_ID)
        self.assertEqual(request_meta.request_fields(request),
                         {'client': '192.0.2.�', 'sign_in_ref': None, 'request_id': REQUEST_ID})


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
        session = client.session
        ref = uuid.uuid4()
        session[request_meta.SESSION_SIGN_IN_REF] = str(ref)
        session.save()
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
