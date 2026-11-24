"""Release 1's foundation (RELEASE-1-SPEC section 3, Lane 1): the settings every lane reads, the request's own facts
(studio.request_meta), the security events (studio.security_events) and the operator test helper's sign-in markers
(tests.support.operator). Ending sessions and the session policy: tests/test_sessions.py; the second-factor gate:
tests/test_second_factor.py (both Lane 2's from here). Synthetic data only."""
from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import models, request_meta, second_factor, security_events, views
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

ROOT = Path(__file__).resolve().parents[1]
ADMIN = 'admin.quillmd.com'
REQUEST_ID = '0123456789abcdef0123456789abcdef'


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
        for value in ('', REQUEST_ID[:-1], REQUEST_ID + '0', 'g' * 32, REQUEST_ID[:31] + '\u00e9',
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
                         {'client': '192.0.2.\ufffd', 'sign_in_ref': None, 'request_id': REQUEST_ID})


class SecurityEventTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.actor = f.user('synthetic-operator')
        self.subject = f.member(self.ws)

    def test_one_event_with_ids_counts_and_the_request_s_fields(self):
        request = RequestFactory().post('/ops/people', REMOTE_ADDR='198.51.100.23', HTTP_X_REQUEST_ID=REQUEST_ID)
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        ref = uuid.uuid4()
        request.session[request_meta.SESSION_SIGN_IN_REF] = str(ref)
        moment = datetime(2026, 11, 24, 12, 0, tzinfo=dt_timezone.utc)
        row = security_events.record('signin.throttled', actor=self.actor, subject=self.subject.pk,
                                     workspace_id=self.ws, request=request, refused=3, user_key='a' * 64,
                                     window={'start': moment, 'seconds': 60}, cost=Decimal('0.25'), ids=[self.ws.pk])
        stored = models.SecurityEvent.objects.get()
        self.assertEqual(stored.pk, row.pk)
        self.assertEqual((stored.event, stored.actor_id, stored.actor_label, stored.subject_id, stored.workspace_id),
                         ('signin.throttled', self.actor.pk, '', self.subject.pk, self.ws.pk))
        self.assertEqual(stored.data, {'refused': 3, 'user_key': 'a' * 64, 'window': {'start': moment.isoformat(),
                                       'seconds': 60}, 'cost': '0.25', 'ids': [str(self.ws.pk)]})
        self.assertEqual((stored.client, stored.sign_in_ref, stored.request_id), ('198.51.100.23', ref, REQUEST_ID))

    def test_a_server_act_names_its_person_and_records_no_request(self):
        row = security_events.record('operator.revoked', actor_label='Synthetic Person', subject=self.actor)
        self.assertEqual((row.actor_id, row.actor_label, row.subject_id, row.workspace_id), (None, 'Synthetic Person',
                                                                                             self.actor.pk, None))
        self.assertEqual((row.client, row.sign_in_ref, row.request_id, row.data), ('', None, '', {}))

    def test_the_request_being_served_is_recorded_when_none_is_given(self):
        request = RequestFactory().get('/', REMOTE_ADDR='203.0.113.5', HTTP_X_REQUEST_ID=REQUEST_ID)
        with request_meta.bound(request):
            row = security_events.record('password.changed', actor=self.subject)
        self.assertEqual((row.client, row.request_id), ('203.0.113.5', REQUEST_ID))

    def test_anything_but_ids_counts_and_fixed_words_is_refused(self):
        cases = {
            'a name that is no dotted word': dict(event='Signin Throttled'),
            'a bare word': dict(event='signin'),
            'a long name': dict(event='signin.' + 'x' * 60),
            'typed text': dict(event='signin.throttled', note='x' * 201),
            'an object': dict(event='signin.throttled', what=object()),
            'a number that is not finite': dict(event='signin.throttled', ratio=float('nan')),
            'a name in the data that is no word': dict(event='signin.throttled', counts={'Patient Name': 1}),
            'too deep': dict(event='signin.throttled', a={'b': {'c': {'d': {'e': 1}}}}),  # three levels hold
            'a role for a person': dict(event='operator.revoked', actor_label='x' * 121),
            'an actor that is no account': dict(event='operator.revoked', actor='platform-operator'),
        }
        for label, arguments in cases.items():
            event = arguments.pop('event')
            with self.subTest(label), self.assertRaises(ValueError):
                security_events.record(event, **arguments)
        self.assertFalse(models.SecurityEvent.objects.exists())

    def test_three_levels_of_data_are_held(self):
        row = security_events.record('maintenance.ran', counts={'tables': {'studio_ratewindow': {'deleted': 4}}})
        self.assertEqual(row.data, {'counts': {'tables': {'studio_ratewindow': {'deleted': 4}}}})

    def test_a_write_that_fails_raises(self):
        with mock.patch.object(models.SecurityEvent.objects, 'create', side_effect=DatabaseError('synthetic')):
            with self.assertRaises(DatabaseError):
                security_events.record('second_factor.failed', actor=self.actor)


class OperatorHelperTests(TestCase):
    """tests.support.operator signs a test operator in as its host's door would (RELEASE-1-SPEC section 5's keys)."""

    def gate_request(self, client, user):
        request = RequestFactory().get('/ops/', HTTP_HOST=ADMIN)
        request.session = import_module(settings.SESSION_ENGINE).SessionStore(client.session.session_key)
        request.user = user
        return request

    def test_the_admin_door_carries_the_second_factor_and_the_cpt_door_none(self):
        moment = datetime(2026, 11, 24, 12, 0, tzinfo=dt_timezone.utc)
        with mock.patch.object(timezone, 'now', return_value=moment):
            admin = ops.admin_client(f.user('operator-admin'))
            cpt = ops.client(f.user('operator-cpt'))
        stamp = request_meta.epoch_seconds(moment)
        session = admin.session
        self.assertEqual((session[request_meta.SESSION_DOOR], session[request_meta.SESSION_SECOND_FACTOR_AT],
                          session[request_meta.SESSION_AUTH_AT], session[request_meta.SESSION_LAST_ACTIVE]),
                         ('admin', stamp, stamp, stamp))
        uuid.UUID(session[request_meta.SESSION_SIGN_IN_REF])
        self.assertEqual(cpt.session[request_meta.SESSION_DOOR], 'cpt')
        self.assertNotIn(request_meta.SESSION_SECOND_FACTOR_AT, cpt.session)
        self.assertNotEqual(cpt.session[request_meta.SESSION_SIGN_IN_REF], session[request_meta.SESSION_SIGN_IN_REF])

    def test_the_gate_reads_the_admin_client_as_satisfied_and_the_password_only_one_as_not(self):
        operator_user, password_only_user = f.user('operator-key'), f.user('operator-password')
        with_key = ops.admin_client(operator_user)
        password_only = ops.admin_client(password_only_user, second_factor=False)
        self.assertTrue(second_factor.satisfied(self.gate_request(with_key, operator_user)))
        self.assertFalse(second_factor.satisfied(self.gate_request(password_only, password_only_user)))
        self.assertEqual(password_only.session[request_meta.SESSION_DOOR], 'admin')
        self.assertTrue(models.OperatorGrant.objects.filter(user=password_only_user).exists())
        cpt_user = f.user('operator-cpt-door')
        self.assertFalse(second_factor.satisfied(self.gate_request(ops.client(cpt_user), cpt_user)))

    def test_the_door_follows_the_host(self):
        self.assertEqual([ops.door_of(host) for host in ('admin.quillmd.com', 'admin.quillmd.com:443', 'testserver',
                                                         'cpt.quillmd.com')], ['admin', 'admin', 'cpt', 'cpt'])
