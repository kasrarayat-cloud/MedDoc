"""The operator's second factor (release 1, B2; RELEASE-1-SPEC 3.3 and 4, B2): the console's gate - satisfied() and the
step-up decorator, built in Lane 1 - and the WebAuthn ceremony around it (Lane 2): the admin door's second step, setup with
a code issued on the server, recovery codes, the step-up and the keys page, and the ruled acts issue_enrolment and
reset_second_factor (B8). The ceremony is driven through the real py_webauthn verification by a software authenticator
(Authenticator: an EC P-256 key, made with cryptography, that signs registration and assertion data as a browser hands
them to the server). Synthetic data only."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone as dt_timezone
from importlib import import_module
from pathlib import Path
from unittest import mock

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from webauthn.helpers import bytes_to_base64url

from cptstudio import urls as customer_urls
from studio import models, request_meta, second_factor, second_factor_views, throttle
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC

ADMIN = 'admin.quillmd.com'
CPT = 'cpt.quillmd.com'
MOMENT = datetime(2026, 11, 24, 12, 0, tzinfo=dt_timezone.utc)
NOW = request_meta.epoch_seconds(MOMENT)
PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
UP, UV, AT = 0x01, 0x04, 0x40  # authenticator data flags: user present, user verified, attested credential data
CONSOLE_ROUTES = [str(p.pattern) for p in customer_urls.urlpatterns if str(p.pattern).startswith('ops/')]
SAMPLE_IDS = {'<uuid:encounter_id>': '00000000-0000-4000-8000-000000000001',
              '<uuid:user_id>': '00000000-0000-4000-8000-000000000002',
              '<uuid:workspace_id>': '00000000-0000-4000-8000-000000000003'}


def at(moment):
    return mock.patch.object(timezone, 'now', return_value=moment)


class Clock:
    """timezone.now for a test: a moment that moves only when the test moves it (with: patched while the block runs)."""

    def __init__(self, moment=MOMENT):
        self.moment = moment

    def __call__(self):
        return self.moment

    def advance(self, seconds):
        self.moment += timedelta(seconds=seconds)
        return self.moment

    def __enter__(self):
        self._patch = mock.patch.object(timezone, 'now', side_effect=self)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()


def b64(data):
    return bytes_to_base64url(data)


class Authenticator:
    """A software security key: an EC P-256 key pair (cryptography) that registers with a 'none' attestation and signs
    assertions, each answer shaped as ops_second_factor.js hands a browser's to the server (py_webauthn's JSON)."""

    def __init__(self, *, rp_id=None, origin=None):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.rp_id = rp_id or settings.WEBAUTHN_RP_ID
        self.origin = origin or settings.WEBAUTHN_ORIGIN
        self.sign_count = 0

    @property
    def id(self):
        return b64(self.credential_id)

    def public_key(self):
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})

    def _client(self, kind, challenge, origin, cross_origin):
        return json.dumps({'type': kind, 'challenge': challenge, 'origin': origin or self.origin,
                           'crossOrigin': cross_origin}).encode()

    def register(self, options, *, origin=None, rp_id=None, cross_origin=False):
        client = self._client('webauthn.create', options['challenge'], origin, cross_origin)
        data = (hashlib.sha256((rp_id or self.rp_id).encode()).digest() + bytes([UP | UV | AT])
                + self.sign_count.to_bytes(4, 'big') + bytes(16) + len(self.credential_id).to_bytes(2, 'big')
                + self.credential_id + self.public_key())
        attestation = cbor2.dumps({'fmt': 'none', 'attStmt': {}, 'authData': data})
        return {'id': self.id, 'rawId': self.id, 'type': 'public-key', 'authenticatorAttachment': 'cross-platform',
                'clientExtensionResults': {},
                'response': {'clientDataJSON': b64(client), 'attestationObject': b64(attestation), 'transports': ['usb']}}

    def assertion(self, options, *, origin=None, rp_id=None, count=None, cross_origin=False, signer=None):
        self.sign_count = self.sign_count + 1 if count is None else count
        client = self._client('webauthn.get', options['challenge'], origin, cross_origin)
        data = hashlib.sha256((rp_id or self.rp_id).encode()).digest() + bytes([UP | UV]) + self.sign_count.to_bytes(4, 'big')
        signature = (signer or self.key).sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {'id': self.id, 'rawId': self.id, 'type': 'public-key', 'authenticatorAttachment': 'cross-platform',
                'clientExtensionResults': {},
                'response': {'clientDataJSON': b64(client), 'authenticatorData': b64(data), 'signature': b64(signature),
                             'userHandle': None}}


def add_key(user, authenticator=None, label='Synthetic key'):
    """``user``'s key, stored as setup stores one (a test that is not about setup starts with a key)."""
    authenticator = authenticator or Authenticator()
    models.SecondFactorCredential.objects.create(user=user, rp_id=settings.WEBAUTHN_RP_ID, label=label,
                                                 credential_id=authenticator.id, public_key=authenticator.public_key(),
                                                 transports=['usb'])
    return authenticator


def enrolled_operator(username='platform-operator'):
    """A human operator with a grant and one key: (the account, its authenticator)."""
    user = f.user(username)
    ops.grant(user)
    return user, add_key(user)


def admin_client(**kwargs):
    return Client(HTTP_HOST=ADMIN, **kwargs)


def password_step(client, user, password=PASSWORD, next_url=None):
    data = {'username': user.get_username(), 'password': password}
    if next_url is not None:
        data['next'] = next_url
    return client.post('/login/', data)


def options_of(client, address='/login/second-factor/options', **data):
    answer = client.post(address, data)
    assert answer.status_code == 200, answer.content
    return answer.json()


def key_step(client, authenticator, next_url=None, **assertion):
    """The second step with ``authenticator`` (its options asked for first, as the page does)."""
    data = {'credential': json.dumps(authenticator.assertion(options_of(client), **assertion))}
    if next_url is not None:
        data['next'] = next_url
    return client.post('/login/second-factor', data)


def sign_in(client, user, authenticator, next_url=None, password=PASSWORD):
    """A whole admin-door sign-in: password, then key. The second step's answer."""
    first = password_step(client, user, password=password, next_url=next_url)
    assert (first.status_code, first['Location']) == (302, '/login/second-factor'), first
    return key_step(client, authenticator)


def concrete(route):
    for placeholder, value in SAMPLE_IDS.items():
        route = route.replace(placeholder, value)
    return '/' + route


class GateCase(TestCase):
    def setUp(self):
        self.user = f.user('synthetic-operator')

    def request(self, *, door=request_meta.ADMIN, second_factor_at=NOW, method='get', path='/ops/people', user=None,
                **extra):
        request = getattr(RequestFactory(), method)(path, HTTP_HOST=ADMIN, **extra)
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        if door is not None:
            request.session[request_meta.SESSION_DOOR] = door
        if second_factor_at is not None:
            request.session[request_meta.SESSION_SECOND_FACTOR_AT] = second_factor_at
        request.user = user or self.user
        return request


class SatisfiedTests(GateCase):
    def test_a_second_factor_at_the_admin_door_satisfies(self):
        with at(MOMENT):
            self.assertTrue(second_factor.satisfied(self.request()))
            self.assertTrue(second_factor.satisfied(self.request(second_factor_at=NOW - 7 * 3600)))  # B5 bounds age

    def test_nothing_less_satisfies(self):
        cases = {
            'the cpt door': dict(door=request_meta.CPT),
            'a session from before release 1 (no door)': dict(door=None),
            'a password alone (no second factor)': dict(second_factor_at=None),
            'a marker that is text': dict(second_factor_at=str(NOW)),
            'a marker that is a flag': dict(second_factor_at=True),
            'a marker of nothing': dict(second_factor_at=0),
            'a negative marker': dict(second_factor_at=-5),
            'a marker that is not finite': dict(second_factor_at=float('inf')),
            'a marker in the future': dict(second_factor_at=NOW + 1),
            'a door that is no door': dict(door='Admin'),
        }
        with at(MOMENT):
            for label, arguments in cases.items():
                with self.subTest(label):
                    self.assertFalse(second_factor.satisfied(self.request(**arguments)))
            self.assertFalse(second_factor.satisfied(self.request(user=AnonymousUser())))
            no_session = RequestFactory().get('/ops/', HTTP_HOST=ADMIN)
            no_session.user = self.user
            self.assertFalse(second_factor.satisfied(no_session))


class StepUpTests(GateCase):
    def decorated(self, **options):
        calls = []

        @second_factor.requires_recent_second_factor(**options)
        def act(request, *args, **kwargs):
            calls.append((args, kwargs))
            return HttpResponse('done')
        return act, calls

    def test_a_recent_second_factor_does_the_act(self):
        act, calls = self.decorated()
        with at(MOMENT + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS)):  # exactly the limit: still recent
            answer = act(self.request(method='post', path='/ops/people/x/role'), 'x', back='people')
        self.assertEqual((answer.status_code, answer.content, calls), (200, b'done', [(('x',), {'back': 'people'})]))

    def test_an_older_one_goes_to_the_step_up_and_back_to_the_form_page(self):
        act, calls = self.decorated()
        later = at(MOMENT + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS + 1))
        with later:
            posted = act(self.request(method='post', path='/ops/people/x/role',
                                      HTTP_REFERER='http://admin.quillmd.com/ops/workspaces/00000000-0000-4000-8000-'
                                                   '000000000003?done=role'))
            read = act(self.request(path='/ops/activity?kind=people'))
        self.assertEqual(calls, [])  # the act was not done, and its form is never replayed
        self.assertEqual((posted.status_code, posted['Location']),
                         (303, '/login/second-factor?next=%2Fops%2Fworkspaces%2F00000000-0000-4000-8000-'
                               '000000000003%3Fdone%3Drole'))
        self.assertEqual((read.status_code, read['Location']),
                         (302, '/login/second-factor?next=%2Fops%2Factivity%3Fkind%3Dpeople'))

    def test_next_is_only_ever_a_console_page_of_this_host(self):
        act, _ = self.decorated()
        with at(MOMENT + timedelta(hours=1)):
            for referer in ('', 'http://evil.example/ops/people', 'http://admin.quillmd.com/login/',
                            'http://admin.quillmd.com/ops/../login/', 'http://[::1', 'http://admin.quillmd.com/api/session'):
                with self.subTest(referer=referer):
                    answer = act(self.request(method='post', path='/ops/people/x/role', HTTP_REFERER=referer))
                    self.assertEqual(answer['Location'], '/login/second-factor?next=%2Fops%2F')

    def test_a_session_that_is_not_satisfied_meets_the_gate_s_404(self):
        act, calls = self.decorated()
        with at(MOMENT):
            for request in (self.request(door=request_meta.CPT), self.request(second_factor_at=None),
                            self.request(user=AnonymousUser())):
                with self.assertRaises(Http404):
                    act(request)
        self.assertEqual(calls, [])

    def test_the_limit_is_the_setting_at_each_request_unless_given(self):
        act, _ = self.decorated()
        tight, _ = self.decorated(max_age=60)
        with at(MOMENT + timedelta(seconds=120)):
            self.assertEqual(act(self.request()).status_code, 200)
            self.assertEqual(tight(self.request()).status_code, 302)
            with override_settings(SECOND_FACTOR_STEP_UP_SECONDS=100):
                self.assertEqual(act(self.request()).status_code, 302)

        @second_factor.requires_recent_second_factor
        def bare(request):
            return HttpResponse('done')
        with at(MOMENT):
            self.assertEqual(bare(self.request()).status_code, 200)


class ContractTests(SimpleTestCase):
    def test_max_age_is_whole_seconds(self):
        for value in (-1, 1.5, True, '300'):
            with self.subTest(max_age=value), self.assertRaises(ValueError):
                second_factor.requires_recent_second_factor(max_age=value)(lambda request: None)


# --- the ceremony (Lane 2) ---------------------------------------------------------------------------------------------

def session_of(client):
    return import_module(settings.SESSION_ENGINE).SessionStore(client.cookies[settings.SESSION_COOKIE_NAME].value)


def signed_in_as(client):
    return client.session.get('_auth_user_id')


def reason_file(test, text='Synthetic ruled act for a test: the operator lost a key.'):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    path = Path(folder.name) / 'reason.txt'
    path.write_text(text, encoding='utf-8')
    return str(path)


def every_record():
    """Every row a sign-in or a setup writes that a code, key or password must never reach, as one text."""
    rows = []
    for model in (models.SecurityEvent, models.AuditEvent, models.LoginAttempt, models.OneTimeToken,
                  models.SecondFactorCredential, models.RateWindow, Session):
        rows.extend(str(item) for item in model.objects.values())
    return '\n'.join(rows)


@override_settings(STORAGES=PLAIN_STATIC)
class SignInTests(TestCase):
    """The admin door's two steps (B2, item 2)."""

    def setUp(self):
        self.operator, self.key = enrolled_operator()

    def test_a_password_alone_opens_nothing(self):
        client = admin_client()
        answer = password_step(client, self.operator)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/second-factor'))
        session = client.session
        self.assertIsNone(signed_in_as(client), 'login() waits for the key')
        self.assertNotIn(request_meta.SESSION_SECOND_FACTOR_AT, session)
        self.assertIn(second_factor.PENDING, session)
        # every console route answers the pending session exactly as it answers a stranger: the sign-in, never a page
        stranger = admin_client()
        for route in CONSOLE_ROUTES:
            path = concrete(route)
            for method in ('get', 'post'):
                with self.subTest(route=route, method=method):
                    pending, other = getattr(client, method)(path), getattr(stranger, method)(path)
                    self.assertIn(pending.status_code, (302, 303))
                    self.assertEqual((pending.status_code, pending['Location']), (other.status_code, other['Location']))
        replay = Client(HTTP_HOST=CPT)  # the cookie taken to the doctors' host opens nothing there either
        replay.cookies = client.cookies
        for route in CONSOLE_ROUTES:
            with self.subTest(host=CPT, route=route):
                self.assertEqual(replay.get(concrete(route)).status_code, 404)
        attempt = models.LoginAttempt.objects.get()
        self.assertEqual((attempt.door, attempt.outcome, attempt.succeeded), ('admin', 'second_factor_pending', False))

    def test_a_valid_assertion_signs_in_with_the_admin_door_s_keys(self):
        with Clock():
            client = admin_client()
            answer = sign_in(client, self.operator, self.key, next_url='/ops/people')
            self.assertEqual((answer.status_code, answer['Location']), (302, '/ops/people'))
            session = client.session
            self.assertEqual(signed_in_as(client), str(self.operator.pk))
            self.assertEqual([session[name] for name in (request_meta.SESSION_DOOR, request_meta.SESSION_SECOND_FACTOR_AT,
                                                         request_meta.SESSION_AUTH_AT, request_meta.SESSION_LAST_ACTIVE)],
                             ['admin', NOW, NOW, NOW])
            self.assertNotIn(second_factor.PENDING, session)
            self.assertNotIn(second_factor.CHALLENGE, session)
            attempt = models.LoginAttempt.objects.get()
            self.assertEqual((attempt.outcome, attempt.succeeded, str(attempt.sign_in_ref)),
                             ('signed_in', True, session[request_meta.SESSION_SIGN_IN_REF]))
            key = models.SecondFactorCredential.objects.get()
            self.assertEqual((key.sign_count, key.last_used_at), (1, MOMENT))
            self.assertTrue(second_factor.satisfied(type('R', (), {'session': session, 'user': self.operator})()))
            self.assertEqual(client.get('/ops/people').status_code, 200)

    def test_a_replayed_assertion_is_refused(self):
        # a key whose counter stays 0 (as many passkeys report it): only the challenge tells the replay apart
        first = admin_client()
        password_step(first, self.operator)
        signed = self.key.assertion(options_of(first), count=0)
        self.assertEqual(first.post('/login/second-factor', {'credential': json.dumps(signed)}).status_code, 302)
        again = admin_client()
        password_step(again, self.operator)
        options_of(again)  # this sign-in's own challenge
        replayed = again.post('/login/second-factor', {'credential': json.dumps(signed)})
        self.assertEqual(replayed.status_code, 400)
        self.assertIn(second_factor.NOT_VERIFIED, replayed.content.decode())
        self.assertIsNone(signed_in_as(again))
        # within one sign-in the challenge serves one answer, whatever that answer was
        third = admin_client()
        password_step(third, self.operator)
        options = options_of(third)
        third.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options, origin='https://x.example'))})
        late = third.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options, count=0))})
        self.assertEqual(late.status_code, 400)
        self.assertIn(second_factor.NO_CHALLENGE, late.content.decode())
        self.assertIsNone(signed_in_as(third))

    def test_every_other_response_is_refused(self):
        stranger_key = ec.generate_private_key(ec.SECP256R1())
        cases = {
            'another origin': dict(origin='https://cpt.quillmd.com'),
            'the shared parent domain as the relying party': dict(rp_id='quillmd.com'),
            'made inside another origin\'s frame': dict(cross_origin=True),
            'signed by another key': dict(signer=stranger_key),
        }
        for label, assertion in cases.items():
            with self.subTest(label):
                models.RateWindow.objects.filter(scope=second_factor.FAILED_SCOPE).delete()
                client = admin_client()
                password_step(client, self.operator)
                answer = key_step(client, self.key, **assertion)
                self.assertEqual(answer.status_code, 400)
                self.assertIn(second_factor.NOT_VERIFIED, answer.content.decode())
                self.assertIsNone(signed_in_as(client))
        # another account's key
        other, other_key = enrolled_operator('second-operator')
        models.RateWindow.objects.filter(scope=second_factor.FAILED_SCOPE).delete()
        client = admin_client()
        password_step(client, self.operator)
        self.assertEqual(key_step(client, other_key).status_code, 400)
        self.assertIsNone(signed_in_as(client))
        # a signature counter that goes back
        client = admin_client()
        self.assertEqual(sign_in(client, self.operator, self.key).status_code, 302)
        stored = models.SecondFactorCredential.objects.get(user=self.operator).sign_count
        self.assertEqual(stored, self.key.sign_count)
        models.RateWindow.objects.filter(scope=second_factor.FAILED_SCOPE).delete()
        back = admin_client()
        password_step(back, self.operator)
        self.assertEqual(key_step(back, self.key, count=stored - 1).status_code, 400)
        self.assertIsNone(signed_in_as(back))
        self.assertEqual(models.SecondFactorCredential.objects.get(user=self.operator).sign_count, stored)

    def test_five_failures_drop_the_pending_sign_in(self):
        client = admin_client()
        password_step(client, self.operator)
        for _ in range(settings.SECOND_FACTOR_ATTEMPTS):
            answer = key_step(client, self.key, origin='https://x.example')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?reason=key'))
        self.assertEqual(client.get('/login/second-factor')['Location'], '/login/')  # nothing waits for a key any more
        attempt = models.LoginAttempt.objects.get()
        self.assertEqual((attempt.outcome, attempt.succeeded), ('second_factor_failed', False))
        event = models.SecurityEvent.objects.get(event='second_factor.failed')
        self.assertEqual((event.subject_id, event.data['failures']), (self.operator.pk, settings.SECOND_FACTOR_ATTEMPTS))
        self.assertNotIn(self.operator.username, json.dumps(event.data))
        self.assertEqual(throttle.failures_of(self.operator.username)[0], 1)  # it counts toward the username's delay
        page = admin_client().get('/login/?reason=key')
        self.assertIn('The security key could not be verified. Sign in again.', page.content.decode())

    def test_an_account_with_no_key_is_sent_to_setup(self):
        newcomer = f.user('new-operator')
        ops.grant(newcomer)
        client = admin_client()
        password_step(client, newcomer)
        page = client.get('/login/second-factor')
        self.assertEqual(page.status_code, 200)
        self.assertIn('href="/login/enrol"', page.content.decode())
        self.assertEqual(client.post('/login/second-factor/options').status_code, 409)
        self.assertIsNone(signed_in_as(client))

    def test_the_second_step_page_carries_no_inline_script(self):
        client = admin_client()
        password_step(client, self.operator)
        html = client.get('/login/second-factor').content.decode()
        self.assertIn('src="/static/studio/ops_second_factor.js"', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)[^>]*>')
        self.assertNotRegex(html, r'\son[a-z]+=')


def twin_of(client):
    """A second browser holding a copy of ``client``'s session as it is now: two requests that loaded the same session
    row before either saved it (refutation r2, findings 1 and 2)."""
    store = import_module(settings.SESSION_ENGINE).SessionStore
    data = store(session_key=client.cookies[settings.SESSION_COOKIE_NAME].value).load()
    twin = store()
    for name, value in data.items():
        twin[name] = value
    twin.save()
    other = Client(HTTP_HOST=client.defaults.get('HTTP_HOST', ADMIN))
    other.cookies[settings.SESSION_COOKIE_NAME] = twin.session_key
    return other


@override_settings(STORAGES=PLAIN_STATIC)
class ChallengeTests(TestCase):
    """A challenge serves one response, whatever the response and however many copies of the session ask (refutation
    r2, findings 1 and 3)."""

    def setUp(self):
        self.operator, self.key = enrolled_operator()

    def test_one_assertion_sent_from_two_copies_of_a_pending_session_signs_in_once(self):
        first = admin_client()
        password_step(first, self.operator)
        signed = json.dumps(self.key.assertion(options_of(first), count=0))  # a counter that stays 0, as many keys keep it
        second = twin_of(first)  # the second request loaded the session before the first saved it
        done = first.post('/login/second-factor', {'credential': signed})
        late = second.post('/login/second-factor', {'credential': signed})
        self.assertEqual((done.status_code, done['Location']), (302, '/ops/'))
        self.assertEqual(late.status_code, 400)
        self.assertIn(second_factor.NO_CHALLENGE, late.content.decode())
        self.assertIsNone(signed_in_as(second))
        signed_in = [row for row in Session.objects.all() if row.get_decoded().get('_auth_user_id') == str(self.operator.pk)]
        self.assertEqual(len(signed_in), 1)
        self.assertEqual(list(models.LoginAttempt.objects.values_list('outcome', flat=True)), ['signed_in'])

    def test_one_assertion_sent_from_two_copies_of_a_signed_in_session_steps_up_once(self):
        client = admin_client()
        with Clock() as clock:
            password_step(client, self.operator)
            self.assertEqual(key_step(client, self.key, count=0).status_code, 302)  # a counter that stays 0
            clock.advance(settings.SECOND_FACTOR_STEP_UP_SECONDS + 60)
            signed = json.dumps(self.key.assertion(options_of(client), count=0))
            twin = twin_of(client)
            self.assertEqual(client.post('/login/second-factor', {'credential': signed}).status_code, 302)
            late = twin.post('/login/second-factor', {'credential': signed})
            self.assertEqual(late.status_code, 400)
            self.assertIn(second_factor.NO_CHALLENGE, late.content.decode())
            self.assertEqual(twin.session[request_meta.SESSION_SECOND_FACTOR_AT], NOW, 'the copy was not stepped up')
            self.assertEqual(client.session[request_meta.SESSION_SECOND_FACTOR_AT], NOW + clock_seconds(clock))

    def test_a_challenge_is_used_up_in_the_database_before_the_response_is_read(self):
        client = admin_client()
        password_step(client, self.operator)
        options = options_of(client)
        token = models.OneTimeToken.objects.get(purpose=second_factor.CHALLENGE_PURPOSE)
        self.assertEqual((token.user_id, token.used_at), (self.operator.pk, None))
        self.assertNotIn(options['challenge'], str(list(models.OneTimeToken.objects.values())))  # its digest only
        twin = twin_of(client)
        self.assertEqual(client.post('/login/second-factor', {'credential': 'not a response'}).status_code, 400)
        token.refresh_from_db()
        self.assertIsNotNone(token.used_at, 'a refused response used the challenge up')
        replay = twin.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options, count=0))})
        self.assertEqual(replay.status_code, 400)
        self.assertIn(second_factor.NO_CHALLENGE, replay.content.decode())
        self.assertIsNone(signed_in_as(twin))

    def test_a_challenge_is_used_only_in_the_sign_in_it_was_made_for(self):
        first, other = admin_client(), admin_client()
        password_step(first, self.operator)
        password_step(other, self.operator)
        options = options_of(first)
        # the session of another pending sign-in of the same account, holding this challenge: its own reference differs
        state = session_of(other)
        state[second_factor.CHALLENGE] = session_of(first)[second_factor.CHALLENGE]
        state.save()
        answer = other.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options, count=0))})
        self.assertEqual(answer.status_code, 400)
        self.assertIn(second_factor.NO_CHALLENGE, answer.content.decode())
        self.assertIsNone(signed_in_as(other))

    def test_a_credential_id_the_database_cannot_hold_is_the_ordinary_refusal_and_counts(self):
        cases = {'a NUL in the id': lambda good: {**good, 'id': good['id'] + '\u0000'},
                 'a NUL in rawId': lambda good: {**good, 'rawId': good['rawId'] + '\u0000'},
                 'a character outside base64url': lambda good: {**good, 'id': good['id'] + '='},
                 'an id longer than any credential id': lambda good: {**good, 'id': 'A' * 1401, 'rawId': 'A' * 1401},
                 'an empty id': lambda good: {**good, 'id': ''}}
        for label, bad in cases.items():
            with self.subTest(label):
                models.RateWindow.objects.filter(scope__startswith='second_factor.').delete()
                client = Client(HTTP_HOST=ADMIN, raise_request_exception=False)
                password_step(client, self.operator)
                options = options_of(client)
                good = self.key.assertion(options, count=0)
                answer = client.post('/login/second-factor', {'credential': json.dumps(bad(good))})
                self.assertEqual(answer.status_code, 400)
                self.assertIn(second_factor.NOT_VERIFIED, answer.content.decode())
                self.assertEqual(second_factor.attempts_left(self.operator), settings.SECOND_FACTOR_ATTEMPTS - 1,
                                 'the refusal is counted')
                replay = client.post('/login/second-factor', {'credential': json.dumps(good)})
                self.assertEqual(replay.status_code, 400)  # the challenge went with the refused answer
                self.assertIn(second_factor.NO_CHALLENGE, replay.content.decode())
                self.assertIsNone(signed_in_as(client))


def clock_seconds(clock):
    return int((clock.moment - MOMENT).total_seconds())


@override_settings(STORAGES=PLAIN_STATIC)
class ChallengeRaceTests(TransactionTestCase):
    """The same race over two real database connections, as the refutation's probe ran it (refutation r2, finding 1;
    l2fa/test_race.py): two requests with one session cookie and one signed assertion both load the session, then meet
    at the challenge's single use (a barrier just before it). One signs in; the other is refused - and never reaches the
    key's check at all: the sign-in's own one-time completion (finding 2) and the first request's new session key would
    also stop the second from signing in, so the challenge's single use is proven by the checks counted."""

    def test_two_requests_at_the_same_moment_sign_in_once(self):
        operator, key = enrolled_operator()
        first = admin_client()
        password_step(first, operator)
        signed = json.dumps(key.assertion(options_of(first), count=0))
        second = Client(HTTP_HOST=ADMIN)
        second.cookies[settings.SESSION_COOKIE_NAME] = first.cookies[settings.SESSION_COOKIE_NAME].value
        barrier = threading.Barrier(2, timeout=30)
        original = second_factor._challenge_digest

        def digest_once_both_have_loaded(*args):
            barrier.wait()
            return original(*args)

        answers = {}

        def post(name, client):
            try:
                answers[name] = client.post('/login/second-factor', {'credential': signed})
            finally:
                connection.close()

        with mock.patch.object(second_factor, '_challenge_digest', side_effect=digest_once_both_have_loaded), \
                mock.patch.object(second_factor, 'verify_authentication_response',
                                  wraps=second_factor.verify_authentication_response) as checked:
            threads = [threading.Thread(target=post, args=pair) for pair in (('first', first), ('second', second))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
        self.assertEqual(checked.call_count, 1, 'the second request reached the key check: the challenge served twice')
        self.assertEqual(sorted(answer.status_code for answer in answers.values()), [302, 400])
        signed_in = [row for row in Session.objects.all() if row.get_decoded().get('_auth_user_id') == str(operator.pk)]
        self.assertEqual(len(signed_in), 1)
        self.assertEqual(list(models.LoginAttempt.objects.values_list('outcome', flat=True)), ['signed_in'])


@override_settings(STORAGES=PLAIN_STATIC)
class NextTests(TestCase):
    """Where a finished second factor goes is a path of the admin host alone (refutation r2, finding 5;
    l2fa/test_probes.py P1: a step-up's next of '///ops/people' was answered Location: ///ops/people, which a browser
    reads as https://ops/people)."""

    LEAVING = ('///ops/people', '//ops/people', '////ops/people', '/\\ops/people', '\\/ops/people', '/\t/ops/people',
               '/ops/people\n', '/ops/people\r\nX-Injected: 1', ' /ops/people', '\t/ops/people', '/ops/people\x00',
               '/ops/\u200bpeople', 'https://admin.quillmd.com/ops/people', 'http://ops/people', '//admin.quillmd.com/ops/',
               'ops/people', '/login/', '/ops/../login/', '')

    def test_safe_next_keeps_only_a_path_of_this_host(self):
        for target in self.LEAVING:
            with self.subTest(target=target):
                self.assertEqual(second_factor.safe_next(target, ADMIN), '/ops/')
        for target in ('/ops/people', '/ops/activity?kind=people', '/account/'):
            with self.subTest(target=target):
                self.assertEqual(second_factor.safe_next(target, ADMIN), target)

    def test_a_step_up_by_key_or_by_recovery_code_never_leaves_the_host(self):
        operator, key = enrolled_operator()
        codes = second_factor.new_recovery_codes(operator)
        client = admin_client()
        self.assertEqual(sign_in(client, operator, key).status_code, 302)
        for target in ('///ops/people', '/\\ops/people', '/ops/people\r\nX-Injected: 1'):
            with self.subTest(target=target):
                page = client.get('/login/second-factor', {'next': target})
                self.assertEqual(page.status_code, 200)
                hidden = __import__('re').search(r'name="next" value="([^"]*)"', page.content.decode()).group(1)
                self.assertEqual(hidden, '/ops/')  # the hidden next the form sends back
                back = key_step(client, key, next_url=target)
                self.assertEqual((back.status_code, back['Location']), (302, '/ops/'))
        used = client.post('/login/recovery?next=///ops/people', {'code': codes[0], 'next': '///ops/people'})
        self.assertEqual((used.status_code, used['Location']), (302, '/ops/'))
        back = key_step(client, key, next_url='/ops/people')
        self.assertEqual((back.status_code, back['Location']), (302, '/ops/people'))  # a console page stays

    def test_the_sign_in_s_next_never_leaves_the_host_either(self):
        operator, key = enrolled_operator()
        client = admin_client()
        answer = password_step(client, operator, next_url='///ops/people')
        self.assertEqual(answer['Location'], '/login/second-factor')
        self.assertEqual(client.session[second_factor.PENDING]['next'], '/ops/')
        self.assertEqual(key_step(client, key)['Location'], '/ops/')


@override_settings(STORAGES=PLAIN_STATIC)
class FreshSessionTests(TestCase):
    """A password checked at the admin door ends the session it was posted in, and its sign-in waits for the key in a
    fresh one (refutation r2, finding 4; l2fa/test_probes.py P2 and test_p2_own.py)."""

    def setUp(self):
        self.b, self.b_key = enrolled_operator('operator-b')
        self.a, self.a_key = enrolled_operator('operator-a')

    def check_fresh_pending(self, client, before, user):
        self.assertIsNone(signed_in_as(client), 'the signed-in session went on')
        self.assertNotEqual(client.cookies[settings.SESSION_COOKIE_NAME].value, before)
        self.assertFalse(Session.objects.filter(session_key=before).exists())
        session = client.session
        attempt = models.LoginAttempt.objects.filter(username=user.username).latest('pk')
        self.assertEqual(attempt.outcome, 'second_factor_pending')
        self.assertEqual((session[second_factor.PENDING]['user'], session[second_factor.PENDING]['ref']),
                         (str(user.pk), str(attempt.sign_in_ref)))
        self.assertEqual(session[request_meta.SESSION_SIGN_IN_REF], str(attempt.sign_in_ref))
        for name in (request_meta.SESSION_SECOND_FACTOR_AT, request_meta.SESSION_DOOR, request_meta.SESSION_AUTH_AT):
            self.assertNotIn(name, session)
        page = client.get('/ops/security')
        self.assertEqual(page.status_code, 302)  # the keys page is the sign-in's again, never the signed-in one's
        self.assertNotIn('X-CPT-Actor', page)

    def test_another_operator_s_password_posted_in_a_signed_in_session_ends_it(self):
        client = admin_client()
        self.assertEqual(sign_in(client, self.b, self.b_key).status_code, 302)
        before = client.cookies[settings.SESSION_COOKIE_NAME].value
        answer = password_step(client, self.a)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/second-factor'))
        self.check_fresh_pending(client, before, self.a)
        # and the second step signs A in, in a session of its own
        self.assertEqual(key_step(client, self.a_key).status_code, 302)
        self.assertEqual(signed_in_as(client), str(self.a.pk))

    def test_the_own_password_posted_again_ends_the_signed_in_session_too(self):
        client = admin_client()
        self.assertEqual(sign_in(client, self.b, self.b_key).status_code, 302)
        before = client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(password_step(client, self.b)['Location'], '/login/second-factor')
        self.check_fresh_pending(client, before, self.b)

    def test_an_anonymous_session_is_flushed_before_its_sign_in_waits(self):
        client = admin_client()
        password_step(client, self.a)
        first = client.cookies[settings.SESSION_COOKIE_NAME].value
        password_step(client, self.b)  # the same browser, another password: the earlier pending sign-in goes
        self.check_fresh_pending(client, first, self.b)


@override_settings(STORAGES=PLAIN_STATIC)
class PendingPasswordTests(TestCase):
    """A sign-in waiting for its key is bound to the password it checked: a password change, or a sign-out everywhere,
    ends it, and one changed any other way still refuses it (refutation r2, finding 11; bypass/byp_keep.py)."""

    NEW = 'a fresh synthetic passphrase only I know'

    def setUp(self):
        self.operator, self.key = enrolled_operator()
        self.codes = second_factor.new_recovery_codes(self.operator)

    def waiting(self):
        client = admin_client()
        self.assertEqual(password_step(client, self.operator)['Location'], '/login/second-factor')
        return client

    def test_a_password_change_ends_the_sign_ins_waiting_with_the_old_password(self):
        with Clock() as clock:
            here = admin_client()
            self.assertEqual(sign_in(here, self.operator, self.key).status_code, 302)
            by_key, by_code = self.waiting(), self.waiting()  # someone who knows the old password, twice
            waiting = [client.cookies[settings.SESSION_COOKIE_NAME].value for client in (by_key, by_code)]
            clock.advance(30)
            changed = here.post('/account/', {'current_password': PASSWORD, 'new_password': self.NEW,
                                              'new_password_again': self.NEW})
            self.assertEqual(changed.status_code, 302)
            self.assertEqual(changed['Location'], '/account/?done=changed')
            for key in waiting:
                self.assertFalse(Session.objects.filter(session_key=key).exists(), 'a pending sign-in outlived the change')
            self.assertEqual(models.SecurityEvent.objects.get(event='password.changed').data['sessions_ended'], 2)
            self.assertEqual(by_key.post('/login/second-factor/options').status_code, 403)
            used = by_code.post('/login/recovery', {'code': self.codes[0]})
            self.assertEqual((used.status_code, used['Location']), (302, '/login/'))
            for client in (by_key, by_code):
                self.assertIsNone(signed_in_as(client))
            self.assertEqual(second_factor.recovery_codes_left(self.operator), settings.RECOVERY_CODE_COUNT)
            self.assertEqual(signed_in_as(here), str(self.operator.pk))  # the session that made the change stays

    def test_a_sign_out_everywhere_ends_the_sign_ins_waiting_too(self):
        here = admin_client()
        self.assertEqual(sign_in(here, self.operator, self.key).status_code, 302)
        waiting = self.waiting()
        key = waiting.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(here.post('/logout/everywhere')['Location'], '/login/')
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertEqual(models.SecurityEvent.objects.get(event='sessions.ended_everywhere').data['sessions_ended'], 2)

    def test_a_password_changed_without_ending_any_session_still_refuses_the_old_sign_in(self):
        by_key = self.waiting()
        options = options_of(by_key)  # its challenge, asked for while the old password was still the account's
        by_code = self.waiting()
        self.operator.set_password(self.NEW)  # a change that ended no session
        self.operator.save()
        answer = by_key.post('/login/second-factor', {'credential': json.dumps(self.key.assertion(options))})
        self.assertIsNone(signed_in_as(by_key), 'the old password signed in')
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/'))
        used = by_code.post('/login/recovery', {'code': self.codes[0]})
        self.assertIsNone(signed_in_as(by_code), 'the old password signed in')
        self.assertEqual((used.status_code, used['Location']), (302, '/login/'))
        self.assertEqual(second_factor.recovery_codes_left(self.operator), settings.RECOVERY_CODE_COUNT)
        # the new password waits for the key as before
        fresh = admin_client()
        self.assertEqual(sign_in(fresh, self.operator, self.key, password=self.NEW)['Location'], '/ops/')


@override_settings(STORAGES=PLAIN_STATIC)
class PendingFailureTests(TestCase):
    """A pending sign-in's failures are counted per its reference in the database, so no copy of its session outlives
    them, and its attempt is settled once (refutation r2, finding 2; l2fa/test_race_failures.py)."""

    def setUp(self):
        self.operator, self.key = enrolled_operator()

    def test_a_copy_of_the_session_cannot_keep_a_sign_in_whose_failures_reached_the_limit(self):
        with Clock(MOMENT + timedelta(seconds=250)) as clock:  # 250 s into a 300-second window of the account's count
            client = admin_client()
            password_step(client, self.operator)
            twin = twin_of(client)  # the copy another request saved last, with no failure in it
            for _ in range(settings.SECOND_FACTOR_ATTEMPTS):
                answer = key_step(client, self.key, origin='https://x.example')
            self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?reason=key'))
            clock.advance(60)  # the account's next window; the pending sign-in is 60 s old
            page = twin.get('/login/second-factor')
            self.assertEqual(page.status_code, 302, 'the copy still waits for a key')
            self.assertEqual(page['Location'], '/login/')
            self.assertNotIn(second_factor.PENDING, twin.session)
            self.assertEqual(twin.post('/login/second-factor/options').status_code, 403)
            self.assertIsNone(signed_in_as(twin))
            self.assertEqual(models.LoginAttempt.objects.get().outcome, 'second_factor_failed')

    def test_a_sign_in_whose_attempt_was_settled_meanwhile_never_completes(self):
        client = admin_client()
        password_step(client, self.operator)
        ref = client.session[second_factor.PENDING]['ref']
        # what another copy of the session did with the failure that reached the limit
        self.assertEqual(throttle.settle_second_factor(RequestFactory().post('/'), ref, signed_in=False), 1)
        answer = key_step(client, self.key)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?reason=key'))
        self.assertIsNone(signed_in_as(client))
        self.assertNotIn(second_factor.PENDING, client.session)
        self.assertEqual(models.LoginAttempt.objects.get().outcome, 'second_factor_failed')
        # a recovery code cannot complete it either
        codes = second_factor.new_recovery_codes(self.operator)
        again = admin_client()
        password_step(again, self.operator)
        ref = again.session[second_factor.PENDING]['ref']
        throttle.settle_second_factor(RequestFactory().post('/'), ref, signed_in=False)
        used = again.post('/login/recovery', {'code': codes[0]})
        self.assertEqual((used.status_code, used['Location']), (302, '/login/?reason=key'))
        self.assertIsNone(signed_in_as(again))

    def test_the_page_says_the_attempts_this_sign_in_has_left(self):
        client = admin_client()
        password_step(client, self.operator)
        for _ in range(2):
            key_step(client, self.key, origin='https://x.example')
        models.RateWindow.objects.filter(scope=second_factor.FAILED_SCOPE).delete()  # the account's window has passed
        state = client.session[second_factor.PENDING]
        self.assertEqual(second_factor.attempts_left(self.operator), settings.SECOND_FACTOR_ATTEMPTS)
        self.assertEqual(second_factor.attempts_left(self.operator, state), settings.SECOND_FACTOR_ATTEMPTS - 2)


@override_settings(STORAGES=PLAIN_STATIC)
class PendingFailureRaceTests(TransactionTestCase):
    """Eight wrong answers sent at once from one pending session, over eight connections: every one is counted, the
    sign-in ends in every copy of the session, and one SecurityEvent says so (refutation r2, finding 2)."""

    def test_failures_sent_at_once_end_the_sign_in_in_every_copy_of_the_session(self):
        operator, key = enrolled_operator()
        first = admin_client()
        password_step(first, operator)
        wrong = json.dumps(key.assertion(options_of(first), origin='https://x.example'))
        cookie = first.cookies[settings.SESSION_COOKIE_NAME].value
        clients = [first] + [Client(HTTP_HOST=ADMIN) for _ in range(7)]
        for client in clients[1:]:
            client.cookies[settings.SESSION_COOKIE_NAME] = cookie
        barrier = threading.Barrier(len(clients), timeout=30)
        original = second_factor._take_challenge

        def take_once_all_have_loaded(*args):
            barrier.wait()
            return original(*args)

        statuses = []

        def post(client):
            try:
                statuses.append(client.post('/login/second-factor', {'credential': wrong}).status_code)
            finally:
                connection.close()

        with mock.patch.object(second_factor, '_take_challenge', side_effect=take_once_all_have_loaded):
            threads = [threading.Thread(target=post, args=(client,)) for client in clients]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
        self.assertEqual(len(statuses), len(clients))
        counted = models.RateWindow.objects.filter(scope=second_factor.PENDING_FAILED_SCOPE).values_list('count', flat=True)
        self.assertEqual(sum(counted), len(clients))
        page = first.get('/login/second-factor')
        self.assertEqual(page.status_code, 302, 'a copy of the session still waits for a key')
        self.assertEqual(page['Location'], '/login/')
        self.assertEqual(first.post('/login/second-factor/options').status_code, 403)
        self.assertEqual(models.LoginAttempt.objects.get().outcome, 'second_factor_failed')
        self.assertEqual(models.SecurityEvent.objects.filter(event='second_factor.failed').count(), 1)


@override_settings(STORAGES=PLAIN_STATIC)
class EnrolmentTests(TestCase):
    """Setup with a code issued on the server (B2, item 3): the code, a new password, then the first key."""

    NEW = 'a new password only I know'

    def setUp(self):
        self.operator = f.user('platform-operator')
        ops.grant(self.operator)
        self.operator.set_unusable_password()  # a fresh host's operator: no password works until setup
        self.operator.save()
        self.token, self.code = second_factor.issue_setup_code(self.operator, 'Synthetic Person')

    def start(self, client, code=None, password=None):
        password = password or self.NEW
        return client.post('/login/enrol', {'step': 'code', 'code': code or self.code, 'new_password': password,
                                            'new_password_again': password})

    def finish(self, client, authenticator, label='Blue key'):
        options = options_of(client, '/login/enrol/options')
        return client.post('/login/enrol', {'step': 'key', 'label': label,
                                            'credential': json.dumps(authenticator.register(options))})

    def test_setup_needs_the_code_then_a_new_password_then_the_first_key(self):
        client = admin_client()
        started = self.start(client)
        self.assertEqual((started.status_code, started['Location']), (303, '/login/enrol'))
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(self.NEW))
        self.assertIsNone(self.operator.password_change_required_at)
        self.assertIsNotNone(self.operator.password_changed_at)
        self.assertIn('Register your security key', client.get('/login/enrol').content.decode())
        key = Authenticator()
        done = self.finish(client, key)
        self.assertEqual(done.status_code, 200)
        codes = __import__('re').findall(r'<li>([a-z0-9]{5}-[a-z0-9]{5}-[a-z0-9]{5})</li>', done.content.decode())
        self.assertEqual(len(set(codes)), settings.RECOVERY_CODE_COUNT)
        stored = models.SecondFactorCredential.objects.get(user=self.operator)
        self.assertEqual((stored.rp_id, stored.label, stored.credential_id, stored.transports),
                         (settings.WEBAUTHN_RP_ID, 'Blue key', key.id, ['usb']))
        self.token.refresh_from_db()
        self.assertIsNotNone(self.token.used_at)
        session = client.session
        self.assertEqual((signed_in_as(client), session[request_meta.SESSION_DOOR]), (str(self.operator.pk), 'admin'))
        self.assertIsInstance(session[request_meta.SESSION_SECOND_FACTOR_AT], int)
        self.assertEqual(client.get('/ops/').status_code, 200)
        rows = list(models.SecondFactorRecoveryCode.objects.filter(user=self.operator, used_at__isnull=True))
        self.assertEqual(len(rows), settings.RECOVERY_CODE_COUNT)
        self.assertFalse(any(code.replace('-', '') in row.code_hash for row in rows for code in codes))
        self.assertEqual(sorted(models.SecurityEvent.objects.exclude(event='operator.granted').values_list('event', flat=True)),
                         ['password.changed', 'second_factor.enrolled'])  # setUp's grant writes operator.granted (C3)
        self.assertEqual(models.LoginAttempt.objects.get().outcome, 'signed_in')
        # and the next sign-in is the password, then this key
        self.assertEqual(sign_in(admin_client(), self.operator, key, password=self.NEW)['Location'], '/ops/')

    def test_setup_is_refused_without_a_live_code(self):
        used = f.user('used-operator')
        ops.grant(used)
        used_token, used_code = second_factor.issue_setup_code(used, 'Synthetic Person')
        models.OneTimeToken.objects.filter(pk=used_token.pk).update(used_at=timezone.now())
        revoked = f.user('revoked-code-operator')
        ops.grant(revoked)
        _, revoked_code = second_factor.issue_setup_code(revoked, 'Synthetic Person')
        second_factor.issue_setup_code(revoked, 'Synthetic Person')  # a newer code revokes this one
        cases = {'a code nobody was given': second_factor.new_code(second_factor.SETUP_CODE_GROUPS),
                 'a used code': used_code, 'a revoked code': revoked_code, 'no code': ''}
        for label, code in cases.items():
            with self.subTest(label):
                models.RateWindow.objects.filter(scope=second_factor.SETUP_CODE_SCOPE).delete()
                client = admin_client()
                answer = client.post('/login/enrol', {'step': 'code', 'code': code, 'new_password': self.NEW,
                                                      'new_password_again': self.NEW})
                self.assertEqual(answer.status_code, 400)
                self.assertIn('This setup code cannot be used', answer.content.decode())
                self.assertNotIn(second_factor.ENROLMENT, client.session)
                self.assertEqual(client.post('/login/enrol/options').status_code, 403)
        # an expired code
        client = admin_client()
        with at(self.token.expires_at + timedelta(seconds=1)):
            self.assertEqual(self.start(client).status_code, 400)
        # the code of an account that lost its grant
        from studio import operator
        operator.revoke(self.operator, 'Synthetic test revocation.', 'tests')
        models.RateWindow.objects.filter(scope=second_factor.SETUP_CODE_SCOPE).delete()
        self.assertEqual(self.start(admin_client()).status_code, 400)
        for user in (self.operator, used, revoked):
            user.refresh_from_db()
            self.assertFalse(user.check_password(self.NEW))
        self.assertFalse(models.SecondFactorCredential.objects.exists())
        # the key step alone, with no code presented, makes no key
        stray = admin_client()
        answer = stray.post('/login/enrol', {'step': 'key', 'credential': '{}', 'label': 'x'})
        self.assertEqual(answer.status_code, 400)
        self.assertFalse(models.SecondFactorCredential.objects.exists())

    def test_a_claim_used_or_revoked_meanwhile_registers_no_key(self):
        # a second answer sent at once that finished first, or a new code issued meanwhile: no key is added
        for label, change in (('used', {'used_at': timezone.now()}), ('revoked', {'revoked_at': timezone.now()})):
            with self.subTest(label):
                self.token, self.code = second_factor.issue_setup_code(self.operator, 'Synthetic Person')
                client = admin_client()
                self.assertEqual(self.start(client).status_code, 303)
                options = options_of(client, '/login/enrol/options')
                claim = models.OneTimeToken.objects.get(purpose=second_factor.SETUP_CLAIM_PURPOSE, used_at__isnull=True,
                                                        revoked_at__isnull=True)
                models.OneTimeToken.objects.filter(pk=claim.pk).update(**change)
                answer = client.post('/login/enrol', {'step': 'key', 'label': 'Late key',
                                                      'credential': json.dumps(Authenticator().register(options))})
                self.assertEqual(answer.status_code, 400)
                self.assertFalse(models.SecondFactorCredential.objects.exists())
                self.assertFalse(models.SecondFactorRecoveryCode.objects.exists())
                self.assertIsNone(signed_in_as(client))

    def test_two_answers_at_once_finish_the_setup_once(self):
        # both answers found the claim live; the other one stored its key and used the claim while this one was being
        # checked: the claim is locked and read again before a key is stored, so this one stores nothing
        client = admin_client()
        self.assertEqual(self.start(client).status_code, 303)
        options = options_of(client, '/login/enrol/options')
        original = second_factor.checked_registration

        def checked_while_the_other_finished(*args, **kwargs):
            checked = original(*args, **kwargs)
            models.OneTimeToken.objects.filter(purpose=second_factor.SETUP_CLAIM_PURPOSE).update(used_at=timezone.now())
            return checked

        with mock.patch.object(second_factor, 'checked_registration', side_effect=checked_while_the_other_finished):
            answer = client.post('/login/enrol', {'step': 'key', 'label': 'Second key',
                                                  'credential': json.dumps(Authenticator().register(options))})
        self.assertEqual(answer.status_code, 400)
        self.assertIn(second_factor_views.SETUP_EXPIRED, answer.content.decode())
        self.assertFalse(models.SecondFactorCredential.objects.exists())
        self.assertFalse(models.SecondFactorRecoveryCode.objects.exists())
        self.assertIsNone(signed_in_as(client))

    def test_one_code_sets_the_password_once_from_two_browsers(self):
        first, second = admin_client(), admin_client()
        mine, theirs = 'first new password only I know', 'second new password nobody chose'
        self.assertEqual(self.start(first, password=mine).status_code, 303)
        again = self.start(second, password=theirs)  # the same code, in another browser
        self.assertEqual(again.status_code, 400)
        self.assertIn('This setup code cannot be used', again.content.decode())
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(mine))
        self.assertFalse(self.operator.check_password(theirs))
        self.token.refresh_from_db()
        self.assertIsNotNone(self.token.used_at, 'the first step used the code up')
        self.assertNotIn(second_factor.ENROLMENT, second.session)
        self.assertEqual(second.post('/login/enrol/options').status_code, 403)
        self.assertEqual(models.SecurityEvent.objects.filter(event='password.changed').count(), 1)
        # the first browser finishes the setup with its claim, once
        self.assertIn('Register your security key', first.get('/login/enrol').content.decode())
        key = Authenticator()
        self.assertEqual(self.finish(first, key).status_code, 200)
        claim = models.OneTimeToken.objects.get(purpose=second_factor.SETUP_CLAIM_PURPOSE)
        self.assertIsNotNone(claim.used_at)
        self.assertEqual(models.SecondFactorCredential.objects.get().credential_id, key.id)

    def test_the_claim_lasts_the_setup_code_s_time_and_starts_in_a_fresh_session(self):
        with Clock() as clock:
            self.token, self.code = second_factor.issue_setup_code(self.operator, 'Synthetic Person')  # on this clock
            client = admin_client()
            before = client.get('/login/enrol')
            anonymous = client.cookies[settings.SESSION_COOKIE_NAME].value if settings.SESSION_COOKIE_NAME in client.cookies else ''
            self.assertEqual(before.status_code, 200)
            self.assertEqual(self.start(client).status_code, 303)
            self.assertNotEqual(client.cookies[settings.SESSION_COOKIE_NAME].value, anonymous)
            claim = models.OneTimeToken.objects.get(purpose=second_factor.SETUP_CLAIM_PURPOSE)
            self.assertEqual(claim.expires_at, clock.moment + timedelta(seconds=settings.ENROLMENT_CODE_SECONDS))
            self.assertEqual((claim.user_id, claim.created_by), (self.operator.pk, 'Synthetic Person'))
            clock.advance(settings.ENROLMENT_CODE_SECONDS + 1)
            self.assertEqual(client.post('/login/enrol/options').status_code, 403)
            late = client.post('/login/enrol', {'step': 'key', 'credential': '{}', 'label': 'x'})
            self.assertEqual(late.status_code, 400)
            self.assertIn(second_factor_views.SETUP_EXPIRED, late.content.decode())

    def test_wrong_codes_are_counted_and_refused_for_the_window(self):
        client = admin_client()
        for _ in range(settings.SECOND_FACTOR_ATTEMPTS):
            self.start(client, code=second_factor.new_code(second_factor.SETUP_CODE_GROUPS))
        refused = self.start(client)  # the right code, after five wrong ones from this address
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Too many attempts', refused.content.decode())
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.has_usable_password())

    def test_the_setup_code_never_appears_in_a_response_a_log_line_or_a_record(self):
        models.OneTimeToken.objects.all().delete()
        records = []

        class Keep(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))
        handler, root = Keep(level=logging.DEBUG), logging.getLogger()
        before = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            out = io.StringIO()
            call_command('issue_enrolment', '--username', self.operator.username, '--reason-file', reason_file(self),
                         '--by', 'Synthetic Person', stdout=out)
            code = out.getvalue().rsplit(': ', 1)[1].strip()
            plain = second_factor.plain_code(code, second_factor.SETUP_CODE_GROUPS)
            self.assertIsNotNone(plain)
            client = admin_client()
            answers = [self.start(client, code=code), client.get('/login/enrol'), self.finish(client, Authenticator()),
                       client.get('/ops/security')]
        finally:
            root.removeHandler(handler)
            root.setLevel(before)
        self.assertEqual(out.getvalue().count(code), 1)
        for answer in answers:
            body = answer.content.decode()
            self.assertNotIn(code, body)
            self.assertNotIn(plain, body)
        for line in records:
            self.assertNotIn(code, line)
            self.assertNotIn(plain, line)
        stored = every_record()
        self.assertNotIn(code, stored)
        self.assertNotIn(plain, stored)
        self.assertEqual(models.OneTimeToken.objects.get(purpose=models.OneTimeToken.OPERATOR_SETUP).token_sha256,
                         hashlib.sha256(plain.encode()).hexdigest())


@override_settings(STORAGES=PLAIN_STATIC)
class RecoveryTests(TestCase):
    def setUp(self):
        self.operator, self.key = enrolled_operator()
        self.codes = second_factor.new_recovery_codes(self.operator)

    def test_a_recovery_code_stands_in_for_the_key_once(self):
        client = admin_client()
        password_step(client, self.operator)
        page = client.get('/login/recovery')
        self.assertIn(f'You have {settings.RECOVERY_CODE_COUNT} left', page.content.decode())
        typed = self.codes[3].upper().replace('-', ' ')  # case and separators do not matter
        used = client.post('/login/recovery', {'code': typed})
        self.assertEqual((used.status_code, used['Location']), (302, '/ops/'))
        self.assertEqual(client.session[request_meta.SESSION_DOOR], 'admin')
        self.assertIn(request_meta.SESSION_SECOND_FACTOR_AT, client.session)
        event = models.SecurityEvent.objects.get(event='second_factor.recovery_used')
        self.assertEqual(event.data['codes_left'], settings.RECOVERY_CODE_COUNT - 1)
        again = admin_client()
        password_step(again, self.operator)
        refused = again.post('/login/recovery', {'code': self.codes[3]})
        self.assertEqual(refused.status_code, 400)
        self.assertIn('That recovery code cannot be used', refused.content.decode())
        self.assertIsNone(signed_in_as(again))
        self.assertEqual(second_factor.recovery_codes_left(self.operator), settings.RECOVERY_CODE_COUNT - 1)

    def test_new_codes_void_the_old_and_none_is_stored_in_plain_text(self):
        fresh = second_factor.new_recovery_codes(self.operator)
        self.assertEqual(second_factor.recovery_codes_left(self.operator), settings.RECOVERY_CODE_COUNT)
        self.assertFalse(second_factor.use_recovery_code(self.operator, self.codes[0]))
        self.assertTrue(second_factor.use_recovery_code(self.operator, fresh[0]))
        stored = every_record() + str(list(models.SecondFactorRecoveryCode.objects.values()))
        for code in self.codes + fresh:
            self.assertNotIn(code.replace('-', ''), stored)


@override_settings(STORAGES=PLAIN_STATIC)
class KeysPageTests(TestCase):
    """/ops/security (B2, item 6) and the step-up (item 5)."""

    def test_keys_are_listed_added_and_removed_each_change_after_a_recent_key(self):
        with Clock() as clock:
            operator, key = enrolled_operator()
            client = admin_client()
            sign_in(client, operator, key)
            page = client.get('/ops/security').content.decode()
            self.assertIn('Synthetic key', page)
            self.assertIn('The last key cannot be removed', page)
            spare = Authenticator()
            options = options_of(client, '/ops/security', action='options')
            added = client.post('/ops/security', {'action': 'add', 'label': 'Spare key',
                                                  'credential': json.dumps(spare.register(options))})
            self.assertEqual((added.status_code, added['Location']), (303, '/ops/security?done=added'))
            self.assertEqual(second_factor.active_keys(operator).count(), 2)
            first = second_factor.active_keys(operator).get(credential_id=key.id)  # the key signed in with
            # six minutes after the key, a change is sent to the step-up and is not made
            clock.advance(6 * 60)
            stale = client.post('/ops/security', {'action': 'remove', 'key': str(first.pk)})
            self.assertEqual((stale.status_code, stale['Location']), (303, '/login/second-factor?next=%2Fops%2Fsecurity'))
            self.assertEqual(second_factor.active_keys(operator).count(), 2)
            self.assertEqual(client.post('/ops/security', {'action': 'options'}).json()['error'], 'step_up')
            # the step-up: the key again, back to the page, and within five minutes the change is made
            step = client.get(stale['Location'])
            self.assertIn('Confirm with your security key', step.content.decode())
            back = key_step(client, key, next_url='/ops/security')
            self.assertEqual((back.status_code, back['Location']), (302, '/ops/security'))
            clock.advance(4 * 60)
            removed = client.post('/ops/security', {'action': 'remove', 'key': str(first.pk)})
            self.assertEqual((removed.status_code, removed['Location']), (303, '/ops/security?done=removed'))
            first.refresh_from_db()
            self.assertEqual((first.removed_at, first.removed_reason), (clock.moment, second_factor.REMOVED_BY_OPERATOR))
            last = second_factor.active_keys(operator).get()
            refused = client.post('/ops/security', {'action': 'remove', 'key': str(last.pk)})
            self.assertEqual(refused.status_code, 400)
            self.assertIn('The last key cannot be removed', refused.content.decode())
            self.assertEqual(list(models.SecurityEvent.objects.filter(event__startswith='second_factor.key_')
                                  .values_list('event', flat=True)),
                             ['second_factor.key_added', 'second_factor.key_removed'])
            # the removed key no longer signs in
            gone = admin_client()
            password_step(gone, operator)
            self.assertEqual(key_step(gone, key).status_code, 400)

    def test_no_password_only_or_cpt_session_reaches_the_keys_page(self):
        operator, _ = enrolled_operator()
        self.assertEqual(ops.admin_client(operator, second_factor=False).get('/ops/security').status_code, 404)
        # B3: a session of the cpt door never satisfies the gate there, even carrying a second-factor time no door writes
        forged = ops.client(operator, HTTP_HOST=CPT)
        session = forged.session
        session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()
        session.save()
        self.assertEqual(forged.get('/ops/security').status_code, 404)
        member = f.member(f.workspace())
        stranger = Client(HTTP_HOST=ADMIN)
        stranger.force_login(member)
        ops.mark_signed_in(stranger, door=request_meta.ADMIN)
        self.assertEqual(stranger.get('/ops/security').status_code, 404)
        self.assertEqual(ops.admin_client(operator).get('/ops/security').status_code, 200)  # the control

    def test_an_operator_session_from_before_release_one_opens_no_console(self):
        operator, _ = enrolled_operator()
        for host, expected in ((CPT, 404), (ADMIN, 302)):
            with self.subTest(host=host):
                client = Client(HTTP_HOST=host)
                client.force_login(operator)
                session = client.session
                for name in request_meta.SESSION_KEYS:
                    session.pop(name, None)
                session.save()  # what a sign-in before release 1 left: none of this release's keys
                answer = client.get('/ops/')
                self.assertEqual(answer.status_code, expected)
                self.assertFalse(Session.objects.filter(session_key=session.session_key).exists())


@override_settings(STORAGES=PLAIN_STATIC)
class CommandTests(TestCase):
    """The ruled acts issue_enrolment and reset_second_factor, end to end on synthetic accounts (B8)."""

    def setUp(self):
        self.operator, self.key = enrolled_operator()

    def run_command(self, name, *args):
        out = io.StringIO()
        call_command(name, *args, stdout=out)
        return out.getvalue()

    def test_issue_enrolment_prints_the_code_once_and_keeps_only_its_digest(self):
        output = self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file',
                                  reason_file(self), '--by', 'Synthetic Person')
        code = output.rsplit(': ', 1)[1].strip()
        token = models.OneTimeToken.objects.get()
        plain = second_factor.plain_code(code, second_factor.SETUP_CODE_GROUPS)
        self.assertEqual((token.token_sha256, token.created_by, token.purpose),
                         (second_factor.code_digest(plain), 'Synthetic Person', models.OneTimeToken.OPERATOR_SETUP))
        self.assertIn(str(self.operator.pk), output)
        self.assertNotIn(self.operator.username, output)
        event = models.SecurityEvent.objects.get(event='second_factor.setup_issued')
        self.assertEqual((event.actor_label, event.subject_id, event.data['token']),
                         ('Synthetic Person', self.operator.pk, str(token.pk)))
        self.assertNotIn(plain, json.dumps(event.data))
        # a second code revokes the first
        self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file', reason_file(self),
                         '--by', 'Synthetic Person')
        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)
        self.assertIsNone(second_factor.setup_token(code))

    def test_issue_enrolment_with_the_installer_s_code_file_prints_no_code(self):
        code = second_factor.new_code(second_factor.SETUP_CODE_GROUPS)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'code'
        path.write_text(code + '\n', encoding='utf-8')
        output = self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file',
                                  reason_file(self), '--by', 'Synthetic Person', '--code-file', str(path))
        self.assertNotIn(code, output)
        self.assertNotIn(code.replace('-', ''), output)
        self.assertEqual(second_factor.setup_token(code).user, self.operator)
        with self.assertRaises(CommandError):  # the same code twice is refused
            self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file',
                             reason_file(self), '--by', 'Synthetic Person', '--code-file', str(path))

    def test_issue_enrolment_refuses_and_records_nothing(self):
        agent = f.user('ops-agent')
        models.User.objects.filter(pk=agent.pk).update(actor_kind=models.User.AGENT)
        ops.grant(agent)
        member = f.member(f.workspace())
        cases = {'a role as --by': (self.operator.username, 'operator'), 'an empty --by': (self.operator.username, ' '),
                 'a uid as --by': (self.operator.username, 'uid 1000'), 'an automated account': (agent.username, 'Synthetic Person'),
                 'an account that is no operator': (member.username, 'Synthetic Person'),
                 'no such account': ('nobody-here', 'Synthetic Person')}
        for label, (username, by) in cases.items():
            with self.subTest(label), self.assertRaises(CommandError):
                self.run_command('issue_enrolment', '--username', username, '--reason-file', reason_file(self), '--by', by)
        with self.assertRaises(CommandError):
            self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file', reason_file(self))
        self.assertFalse(models.OneTimeToken.objects.exists())
        self.assertFalse(models.SecurityEvent.objects.exclude(event='operator.granted').exists())  # setUp's grant (C3)

    def test_reset_second_factor_runs_end_to_end(self):
        second_factor.new_recovery_codes(self.operator)
        signed_in = admin_client()
        sign_in(signed_in, self.operator, self.key)
        output = self.run_command('reset_second_factor', '--username', self.operator.username, '--reason-file',
                                  reason_file(self), '--by', 'Synthetic Person')
        self.assertIn('1 key(s) removed', output)
        self.assertIn(f'{settings.RECOVERY_CODE_COUNT} recovery code(s) voided', output)
        self.assertIn('1 session(s) ended', output)
        self.assertNotIn(self.operator.username, output)
        code = output.rsplit(': ', 1)[1].strip()
        self.assertEqual(second_factor.active_keys(self.operator).count(), 0)
        self.assertEqual(second_factor.recovery_codes_left(self.operator), 0)
        self.assertEqual(signed_in.get('/ops/').status_code, 302)  # the session it ended goes to the sign-in
        self.assertEqual(models.SecondFactorCredential.objects.get().removed_reason, second_factor.REMOVED_BY_RESET)
        event = models.SecurityEvent.objects.get(event='second_factor.reset')
        self.assertEqual((event.data['keys_removed'], event.data['sessions_ended']), (1, 1))
        # the old key opens nothing; the new setup code and a new key do
        client = admin_client()
        password_step(client, self.operator)
        self.assertEqual(client.post('/login/second-factor/options').status_code, 409)
        setup = admin_client()
        password = 'another new password only I know'
        self.assertEqual(setup.post('/login/enrol', {'step': 'code', 'code': code, 'new_password': password,
                                                     'new_password_again': password}).status_code, 303)
        fresh = Authenticator()
        options = options_of(setup, '/login/enrol/options')
        done = setup.post('/login/enrol', {'step': 'key', 'credential': json.dumps(fresh.register(options))})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(setup.get('/ops/').status_code, 200)

    def test_reset_second_factor_refuses_a_role_as_by(self):
        with self.assertRaises(CommandError):
            self.run_command('reset_second_factor', '--username', self.operator.username, '--reason-file',
                             reason_file(self), '--by', 'Platform Operator')
        self.assertEqual(second_factor.active_keys(self.operator).count(), 1)

    # refutation r2, finding 7 (l2fa/test_probes.py P5): every spelling the probe got recorded, and more of its kind
    NOBODY = ('[ ]', '()', '""', 'Operator.', 'the operator', 'Admins', 'sysadmin', 'superuser', 'Claude Code',
              'ops agent', 'Security_Officer', 'n/a.', '<none>', 'bot', '1000', 'operator', 'root', 'uid 1000',
              '[nobody]', 'op\u200berator', '\uff2f\uff30\uff25\uff32\uff21\uff34\uff2f\uff32', 'r\u00adoot', 'ROOT',
              'Sys Admin', 'System Administrator', 'the ops-agent', 'N/A', 'Unknown', '-', 'x', 'A1', '1 2',
              'claude-code', 'Platform-Operator', 'the operators', 'admin user', 'root account', 'on-call',
              'Not applicable', 'installer', 'Engineering-Lead')

    def test_by_names_a_person_in_any_spelling_and_is_recorded_as_one_spelling(self):
        accepted, refused = [], []
        for by in self.NOBODY:
            try:
                self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file',
                                 reason_file(self), '--by', by)
            except CommandError:
                refused.append(by)
            else:
                accepted.append(by)
        self.assertEqual(accepted, [])
        self.assertFalse(models.OneTimeToken.objects.exists())
        self.assertFalse(models.SecurityEvent.objects.exclude(event='operator.granted').exists())  # setUp's grant (C3)
        for by, recorded in (('Synthetic Person', 'Synthetic Person'), ('Jos\u0065\u0301 Garc\u00eda', 'Jos\u00e9 Garc\u00eda'),
                             ('\uff2a\uff4f \uff2c\uff49', 'Jo Li'), ('Ng\u200b Wei', 'Ng Wei'), ("Se\u00e1n  O'Brien", "Se\u00e1n O'Brien"),
                             ('Claude Monet', 'Claude Monet'), ('Rob Root', 'Rob Root')):
            with self.subTest(by=by):
                self.run_command('issue_enrolment', '--username', self.operator.username, '--reason-file',
                                 reason_file(self), '--by', by)
                self.assertEqual(models.OneTimeToken.objects.latest('created_at').created_by, recorded)
                self.assertEqual(models.SecurityEvent.objects.latest('created_at').actor_label, recorded)

    def test_every_ruled_act_refuses_a_role_in_another_spelling(self):
        member = f.member(f.workspace())
        acts = (('issue_enrolment', '--username', self.operator.username),
                ('reset_second_factor', '--username', self.operator.username),
                ('clear_signin_failures', '--username', member.username),
                ('require_password_change', '--username', member.username))
        for act in acts:
            for by in ('the operator', 'Security_Officer', '[ ]', 'uid 1000'):
                with self.subTest(act=act[0], by=by), self.assertRaises(CommandError):
                    self.run_command(*act, '--reason-file', reason_file(self), '--by', by)
        self.assertFalse(models.SecurityEvent.objects.exclude(event='operator.granted').exists())  # setUp's grant (C3)
        self.assertEqual(second_factor.active_keys(self.operator).count(), 1)
        member.refresh_from_db()
        self.assertIsNone(member.password_change_required_at)
