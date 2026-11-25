"""Sign-in slows down instead of locking anyone out (release 1, B1; RELEASE-1-SPEC 4, B1): studio.throttle at both doors -
the address flood, the pair, the username delay and the known-device skip, all before any password is checked; the
LoginAttempt every checked attempt writes; refusals counted, never hidden; and the ruled act clear_signin_failures (B8).
The clock is patched (tests.test_second_factor.Clock). Synthetic data only."""
from __future__ import annotations

import io
import ipaddress
import json
import tempfile
import threading
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections as db_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from studio import models, rate, throttle, views
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_second_factor import ADMIN, CPT, Clock, add_key, key_step

PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
WRONG = 'not-the-password'
ADDRESS_A, ADDRESS_B, ADDRESS_C = '198.51.100.7', '203.0.113.20', '192.0.2.30'


def attempt(username, password=PASSWORD, *, address=ADDRESS_A, host=CPT, client=None):
    client = client or Client(HTTP_HOST=host)
    return client.post('/login/', {'username': username, 'password': password}, REMOTE_ADDR=address)


def sentence(answer):
    return answer.content.decode()


def slash_64(index):
    """An address in the index-th of many IPv6 /64 networks."""
    return str(ipaddress.IPv6Address(0x20010db8000000000000000000000000 + (index << 64) + 0x1234))


@override_settings(STORAGES=PLAIN_STATIC)
class ThrottleCase(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.owner = f.user('owner')
        models.Membership.objects.create(user=self.owner, workspace=self.ws, role=models.Membership.OWNER)


class DelayTests(ThrottleCase):
    def test_tier_one_six_five_wrong_passwords_from_one_address_then_the_right_one_from_another(self):
        # the acceptance test: the right password from address B succeeds only after the delay - and at once with the
        # device cookie of an earlier sign-in from that browser (made from a third address, so B is a new address)
        with Clock() as clock:
            usual = Client(HTTP_HOST=CPT)
            self.assertEqual(attempt('owner', address=ADDRESS_C, client=usual).status_code, 302)  # leaves the cookie
            self.assertIn(throttle.device_cookie_name(), usual.cookies)
            usual.post('/logout/')
            for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
                self.assertEqual(attempt('owner', WRONG, address=ADDRESS_A).status_code, 400)
            refused = attempt('owner', address=ADDRESS_B)
            self.assertEqual(refused.status_code, 400)
            self.assertIn('Too many attempts. Wait 1 minute and try again, or sign in from a device you have used '
                          'before.', sentence(refused))
            self.assertNotIn(settings.SESSION_COOKIE_NAME, refused.cookies)
            known = attempt('owner', address=ADDRESS_B, client=usual)  # the browser that signed in before
            self.assertEqual(known.status_code, 302, 'the known device waited')
            self.assertEqual(known['Location'], '/')
            clock.advance(settings.SIGNIN_DELAY_BASE_SECONDS + 1)
            self.assertEqual(attempt('owner', address=ADDRESS_B).status_code, 302)  # after the delay, from anywhere

    def test_a_flood_from_one_ipv6_slash_64_is_refused_from_that_network_only(self):
        # 100 wrong passwords from addresses rotating inside one /64, for 30 names (each stays under its own delay, so
        # every attempt reaches the password check): the 51st is refused from the network
        network = ipaddress.IPv6Network('2001:db8:1:2::/64')
        answers = [attempt(f'guess-{index % 30}', WRONG, address=str(network[index + 1])) for index in range(100)]
        flooded = sentence(answers[-1])
        self.assertIn('Too many attempts from this network. Wait', flooded)
        self.assertNotIn('a device you have used before', flooded)
        first_flood = next(index for index, answer in enumerate(answers) if 'from this network' in sentence(answer))
        self.assertEqual(first_flood, settings.SIGNIN_CLIENT_LIMIT)  # 50 failed attempts, then the network
        # another name from the same /64 is refused too; the same name from another network meets only its own delay
        self.assertIn('from this network', sentence(attempt('somebody-else', WRONG, address=str(network[999]))))
        elsewhere = sentence(attempt('somebody-else', WRONG, address='2001:db8:9:9::1'))
        self.assertIn(views.SIGN_IN_REFUSED, elsewhere)
        self.assertNotIn('Too many', elsewhere)

    def test_many_networks_raise_the_delay_to_fifteen_minutes_and_no_further(self):
        # a guesser on a new network for every guess, waiting out each delay to the second: the delay doubles from 30 s
        # and stops at 15 minutes; inside every delay each guess is refused, and the sentence names the wait
        with Clock() as clock:
            usual = Client(HTTP_HOST=CPT)
            self.assertEqual(attempt('owner', address=slash_64(0), client=usual).status_code, 302)
            usual.post('/logout/')
            waits = []
            for index in range(1, 11):  # ten failures, each delay waited out to the second
                failures, last = throttle.failures_of('owner')
                wait = throttle.delay_seconds(failures)
                if wait and last is not None and clock.moment < last + timedelta(seconds=wait):
                    refused = attempt('owner', WRONG, address=slash_64(200 + index))
                    self.assertIn('Too many attempts', sentence(refused))
                    waits.append(int(sentence(refused).split('Wait ')[1].split(' minute')[0]))
                    clock.moment = last + timedelta(seconds=wait)  # exactly when the delay ends
                self.assertIn(views.SIGN_IN_REFUSED, sentence(attempt('owner', WRONG, address=slash_64(index))))
            self.assertEqual(waits, [1, 1, 2, 4, 8])  # 30 s, 60 s, 120 s, 240 s and 480 s, as whole minutes
            # the tenth failure meets the ceiling: 15 minutes, never more
            self.assertEqual(throttle.failures_of('owner')[0], 10)
            ceiling = sentence(attempt('owner', address=ADDRESS_B))
            self.assertIn(f'Too many attempts. Wait {settings.SIGNIN_DELAY_MAX_SECONDS // 60} minutes', ceiling)
            # the owner on a known device signs in at once, in the middle of it
            self.assertEqual(attempt('owner', address=ADDRESS_B, client=usual).status_code, 302)
            clock.advance(settings.SIGNIN_DELAY_MAX_SECONDS)
            self.assertEqual(attempt('owner', address='192.0.2.77').status_code, 302)  # and it ends: no lock
        for failures in range(0, 60):
            self.assertLessEqual(throttle.delay_seconds(failures), settings.SIGNIN_DELAY_MAX_SECONDS)
        self.assertEqual([throttle.delay_seconds(n) for n in (4, 5, 6, 9, 10, 40)], [0, 30, 60, 480, 900, 900])

    def test_ten_failures_of_one_pair_refuse_that_pair_only_and_a_known_device_skips_only_the_delay(self):
        device = Client(HTTP_HOST=CPT)
        self.assertEqual(attempt('owner', client=device).status_code, 302)
        device.post('/logout/')
        for _ in range(settings.SIGNIN_PAIR_LIMIT):  # the device cookie skips the username delay, so they all count
            self.assertIn(views.SIGN_IN_REFUSED, sentence(attempt('owner', WRONG, address=ADDRESS_A, client=device)))
        pair = attempt('owner', address=ADDRESS_A, client=device)
        self.assertIn('Too many attempts', sentence(pair))  # the pair: refused, known device or not
        self.assertEqual(pair.status_code, 400)
        self.assertEqual(getattr(pair.cookies.get(settings.SESSION_COOKIE_NAME), 'value', ''), '')  # no session set
        self.assertEqual(attempt('owner', address=ADDRESS_B, client=device).status_code, 302)  # the name elsewhere

    def test_the_refusal_is_the_same_whether_or_not_the_account_exists(self):
        for name in ('owner', 'no-such-account'):
            for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
                attempt(name, WRONG)
        existing, missing = attempt('owner', WRONG), attempt('no-such-account', WRONG)
        self.assertEqual(existing.status_code, missing.status_code)
        strip = lambda answer: sentence(answer).replace('no-such-account', 'owner')  # noqa: E731
        import re
        token = re.compile(r'name="csrfmiddlewaretoken" value="[^"]+"')
        self.assertEqual(token.sub('', strip(existing)), token.sub('', strip(missing)))

    def test_a_refused_attempt_calls_no_password_hasher(self):
        for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
            attempt('owner', WRONG)
        for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
            attempt('no-such-account-yet', WRONG)
        hasher = Argon2PasswordHasher()
        with mock.patch.object(Argon2PasswordHasher, 'verify', wraps=hasher.verify) as verify, \
                mock.patch.object(Argon2PasswordHasher, 'encode', wraps=hasher.encode) as encode:
            for name in ('owner', 'owner', 'no-such-account-yet'):
                refused = attempt(name, address=ADDRESS_A)
                self.assertIn('Too many attempts', sentence(refused), name)
            self.assertEqual((verify.call_count, encode.call_count), (0, 0))
            attempt('somebody', WRONG, address='192.0.2.55')  # the control: a checked attempt hashes
            self.assertGreater(verify.call_count + encode.call_count, 0)


class KnownAddressTests(ThrottleCase):
    """A known address skips the username delay, never the pair or the address limit (refutation r2, finding 8; the
    lead's ruling; lockout/probes/lockprobe/test_p2_rearm.py)."""

    OFFICE = '192.0.2.44'
    POLLERS = ['198.51.100.%d' % number for number in range(1, 6)]

    def test_a_poller_on_five_addresses_for_six_hours_never_keeps_the_doctor_out_of_the_office(self):
        # someone sends a wrong password for 'owner' every 5 s for 6 h from five addresses, re-arming the delay at each
        # lapse; every half hour the doctor signs in from the office (where they signed in before) on a browser with no
        # device cookie, and at the same moment from a network never used before
        with Clock() as clock:
            start = clock.moment
            self.assertEqual(attempt('owner', address=self.OFFICE).status_code, 302)  # a browser since cleared
            office, elsewhere, checked = [], [], 0
            for second in range(5, 6 * 60 * 60 + 1, 5):
                clock.moment = start + timedelta(seconds=second)
                poll = sentence(attempt('owner', WRONG, address=self.POLLERS[(second // 5) % 5]))
                checked += views.SIGN_IN_REFUSED in poll
                self.assertNotIn('from this network', poll)
                if second % 1800 == 0:
                    office.append(attempt('owner', address=self.OFFICE).status_code)
                    elsewhere.append(sentence(attempt('owner', address=f'203.0.113.{second // 1800}')))
            self.assertEqual(office, [302] * 12, 'the doctor at the office signs in on the first try, every time')
            # the written limit: on a new network, without the device cookie, the doctor still waits while the poller
            # keeps the delay armed - never longer than the ceiling at a time; clear_signin_failures is the way back
            self.assertTrue(all('Too many attempts. Wait' in answer for answer in elsewhere))
            # the poller reached the password check only when the delay had lapsed: a few times a window, never 4,320
            self.assertLess(checked, 6 * 4 * 10)

    def test_what_makes_an_address_known(self):
        with Clock() as clock:
            for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
                attempt('owner', WRONG, address=ADDRESS_A)
            known = lambda address: attempt('owner', address=address).status_code == 302  # noqa: E731
            rows = [  # (username, client, succeeded, outcome, days ago)
                ('owner', '2001:db8:1:2::1', True, 'signed_in', 1),  # its /64 is known: 2001:db8:1:2::99 below
                ('owner', '192.0.2.81', True, None, 3),  # an older release's row: succeeded alone
                ('owner', '192.0.2.82', True, 'signed_in', settings.KNOWN_DEVICE_DAYS + 1),  # too long ago
                ('owner', '192.0.2.83', False, 'wrong_password', 1),  # a failure from there is no sign-in
                ('somebody-else', '192.0.2.84', True, 'signed_in', 1),  # another name's sign-in
            ]
            for username, client, succeeded, outcome, days in rows:
                row = models.LoginAttempt.objects.create(username=username, client=client, succeeded=succeeded,
                                                         outcome=outcome, door='cpt' if outcome else None)
                models.LoginAttempt.objects.filter(pk=row.pk).update(created_at=clock.moment - timedelta(days=days))
            self.assertTrue(known('2001:db8:1:2::99'))
            self.assertTrue(known('192.0.2.81'))
            for address in ('192.0.2.82', '192.0.2.83', '192.0.2.84', '2001:db8:1:3::1'):
                with self.subTest(address=address):
                    self.assertFalse(known(address))

    def test_a_known_address_never_skips_the_pair_or_the_address_limit(self):
        self.assertEqual(attempt('owner', address=self.OFFICE).status_code, 302)
        for _ in range(settings.SIGNIN_PAIR_LIMIT):
            self.assertIn(views.SIGN_IN_REFUSED, sentence(attempt('owner', WRONG, address=self.OFFICE)))
        pair = attempt('owner', address=self.OFFICE)  # the right password, from the known address: the pair refuses
        self.assertEqual(pair.status_code, 400)
        self.assertIn('Too many attempts', sentence(pair))


class AddressLimitTests(ThrottleCase):
    """The address limit counts checked failures only, so it ends however often the network keeps trying, and the
    ruled act clears it at once (refutation r2, finding 9; lockout/probes/lockprobe/test_p3_address.py)."""

    OFFICE = '192.0.2.44'

    def flood(self, address=None):
        for index in range(settings.SIGNIN_CLIENT_LIMIT):  # 25 names, twice each: every attempt is checked
            self.assertIn(views.SIGN_IN_REFUSED, sentence(attempt(f'colleague-{index % 25}', 'typo',
                                                                   address=address or self.OFFICE)))

    def test_a_network_that_keeps_trying_is_refused_only_until_its_failures_leave_the_window(self):
        with Clock() as clock:
            start = clock.moment
            usual = Client(HTTP_HOST=CPT)
            self.assertEqual(attempt('owner', address=self.OFFICE, client=usual).status_code, 302)  # a known device
            usual.post('/logout/')
            self.flood()
            answers = []
            for second in range(15, 20 * 60 + 1, 15):  # someone on the office network tries every 15 s, refused
                clock.moment = start + timedelta(seconds=second)
                attempt(f'colleague-{second % 7}', 'retry', address=self.OFFICE)
                if second % 300 == 0:  # the owner, on the usual browser, every 5 minutes
                    answer = attempt('owner', address=self.OFFICE, client=usual)
                    answers.append('in' if answer.status_code == 302 else
                                   'network' if 'from this network' in sentence(answer) else sentence(answer)[:80])
                    if answer.status_code == 302:
                        usual.post('/logout/')
            # refused while the 50 failures are in the 15-minute window (5, 10 and 15 minutes), in at 20 minutes: the
            # sixty refusals of the trickle meanwhile counted for nothing (once the window has passed, the trickle's
            # own attempts reach the password check, and a failure among them counts as any failure does)
            self.assertEqual(answers, ['network'] * 3 + ['in'])
            self.assertGreater(throttle.refused_in('owner'), 0)  # refusals are still counted, for the Sign-ins page
            self.assertGreater(rate.count(throttle.REFUSED_CLIENT, self.OFFICE, since=rate.window_start(60, start)), 0)


@override_settings(STORAGES=PLAIN_STATIC)
class ConcurrentAttemptTests(TransactionTestCase):
    """Attempts sent at the same moment, over real connections, meet the pair limit, the address limit and the account
    page's wrong-password limit one at a time: each takes its place in one atomic hit before any password is checked
    (refutation r2, finding 10; lockout/probes/lockprobe/test_p7_keys_concurrency.py, bypass/byp_race.py). A barrier
    holds every request at the door until all of them are there."""

    def setUp(self):
        self.ws = f.workspace()
        self.owner = f.user('owner')
        models.Membership.objects.create(user=self.owner, workspace=self.ws, role=models.Membership.OWNER)

    def burst(self, target, function, calls):
        """Run ``calls`` (callables) on threads that all wait at ``target.function`` until each has reached it."""
        barrier = threading.Barrier(len(calls), timeout=30)
        original = getattr(target, function)

        def at_once(*args, **kwargs):
            barrier.wait()
            return original(*args, **kwargs)

        results = [None] * len(calls)

        def run(index, call):
            try:
                results[index] = call()
            finally:
                db_connections.close_all()

        with mock.patch.object(target, function, at_once):
            threads = [threading.Thread(target=run, args=pair) for pair in enumerate(calls)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
        return results

    @override_settings(SIGNIN_USER_DELAY_AFTER=10 ** 6, SIGNIN_CLIENT_LIMIT=10 ** 6)
    def test_six_attempts_at_once_one_place_short_of_the_pair_limit_check_one_password(self):
        for _ in range(settings.SIGNIN_PAIR_LIMIT - 1):
            throttle.count_failure('owner', ADDRESS_A)
        answers = self.burst(throttle.Door, 'refusal', [lambda: sentence(attempt('owner', 'guess'))] * 6)
        self.assertEqual(sum(views.SIGN_IN_REFUSED in answer for answer in answers), 1)
        self.assertEqual(sum('Too many attempts' in answer for answer in answers), 5)
        self.assertEqual(models.LoginAttempt.objects.count(), 1)
        pair = models.RateWindow.objects.filter(scope=throttle.FAIL_PAIR, key=throttle.pair_key('owner', ADDRESS_A))
        self.assertEqual(sum(pair.values_list('count', flat=True)), settings.SIGNIN_PAIR_LIMIT)

    @override_settings(SIGNIN_USER_DELAY_AFTER=10 ** 6, SIGNIN_PAIR_LIMIT=10 ** 6)
    def test_six_attempts_at_once_one_place_short_of_the_address_limit_check_one_password(self):
        # the patched clock, one moment for the attempts and the count of their minute (refutation round 3,
        # regression-7: on the real clock a minute boundary inside the test left the count of the minute after it)
        with Clock():
            for index in range(settings.SIGNIN_CLIENT_LIMIT - 1):
                throttle.count_failure(f'colleague-{index}', ADDRESS_A)
            names = [f'guess-{index}' for index in range(6)]
            answers = self.burst(throttle.Door, 'refusal',
                                 [lambda name=name: sentence(attempt(name, 'guess')) for name in names])
            self.assertEqual(sum(views.SIGN_IN_REFUSED in answer for answer in answers), 1)
            self.assertEqual(sum('from this network' in answer for answer in answers), 5)
            self.assertEqual(models.LoginAttempt.objects.count(), 1)
            self.assertEqual(rate.count(throttle.FAIL_CLIENT, ADDRESS_A, since=rate.window_start(60)),
                             settings.SIGNIN_CLIENT_LIMIT)

    def test_sixteen_wrong_current_passwords_at_once_get_five_checks_and_then_none(self):
        member = f.member(self.ws)
        client = Client(HTTP_HOST=CPT)
        self.assertEqual(client.post('/login/', {'username': member.username, 'password': PASSWORD}).status_code, 302)
        cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
        new = 'a fresh synthetic passphrase only I know'

        def guess(current):
            def post():
                other = Client(HTTP_HOST=CPT)
                other.cookies[settings.SESSION_COOKIE_NAME] = cookie
                answer = other.post('/account/', {'current_password': current, 'new_password': new,
                                                  'new_password_again': new})
                body = answer.content.decode()
                return ('changed' if answer.status_code == 302 else 'wrong' if views.WRONG_CURRENT in body
                        else 'held' if 'Too many wrong passwords' in body else f'other {answer.status_code}')
            return post

        first = self.burst(views, '_change_password', [guess(f'wrong-guess-{index}') for index in range(16)])
        self.assertEqual(sorted(first), ['held'] * 11 + ['wrong'] * 5)
        # the right password hidden in a second burst, the window's places already taken: nothing is checked
        second = self.burst(views, '_change_password', [guess(f'wrong-guess-b{index}') for index in range(15)]
                            + [guess(PASSWORD)])
        self.assertEqual(second, ['held'] * 16)
        member.refresh_from_db()
        self.assertTrue(member.check_password(PASSWORD))
        self.assertEqual(views._wrong_passwords(member), settings.SIGNIN_USER_DELAY_AFTER)


class PlaceTests(ThrottleCase):
    """A place taken before the password check is the attempt's failure when it fails, and given back otherwise."""

    def test_a_right_password_and_a_refusal_give_their_places_back(self):
        # the patched clock, one moment for the attempts and the counts of their minute (refutation round 3,
        # regression-7: on the real clock a minute boundary inside the test left the counts of the minute after it)
        with Clock():
            for _ in range(3):
                attempt('owner', WRONG, address=ADDRESS_A)
            counted = lambda scope, key: rate.count(scope, key, since=rate.window_start(60))  # noqa: E731
            pair = throttle.pair_key('owner', ADDRESS_A)
            self.assertEqual((counted(throttle.FAIL_PAIR, pair), counted(throttle.FAIL_CLIENT, ADDRESS_A)), (3, 3))
            self.assertEqual(attempt('owner', address=ADDRESS_A).status_code, 302)  # signed in: no failure
            attempt('owner', host=ADMIN, address=ADDRESS_A)  # no_access at the admin door: no failure either
            self.assertEqual((counted(throttle.FAIL_PAIR, pair), counted(throttle.FAIL_CLIENT, ADDRESS_A)), (3, 3))
            for _ in range(2):
                attempt('owner', WRONG, address=ADDRESS_A)
            refused = attempt('owner', address=ADDRESS_B)  # the username delay: refused, its places given back
            self.assertIn('Too many attempts', sentence(refused))
            self.assertEqual(counted(throttle.FAIL_CLIENT, ADDRESS_B), 0)
            self.assertEqual(counted(throttle.FAIL_PAIR, throttle.pair_key('owner', ADDRESS_B)), 0)
            self.assertEqual(counted(throttle.FAIL_PAIR, pair), 5)


class CrossDoorTests(ThrottleCase):
    def test_a_doctor_s_right_password_at_the_admin_door_is_no_access_and_changes_no_delay(self):
        for _ in range(12):
            refused = attempt('owner', host=ADMIN)
            self.assertEqual(refused.status_code, 400)
            self.assertIn(views.ADMIN_SIGN_IN_REFUSED, sentence(refused))
        self.assertEqual(set(models.LoginAttempt.objects.values_list('door', 'outcome', 'succeeded')),
                         {('admin', 'no_access', False)})
        self.assertEqual(throttle.failures_of('owner'), (0, None))
        signed = attempt('owner', host=CPT)
        self.assertEqual((signed.status_code, signed['Location']), (302, '/'))

    def test_failures_at_either_door_count_toward_one_delay(self):
        for host in (ADMIN, CPT, ADMIN, CPT, ADMIN):
            attempt('owner', WRONG, host=host)
        for host in (CPT, ADMIN):
            self.assertIn('Too many attempts', sentence(attempt('owner', host=host)))


class RecordTests(ThrottleCase):
    def test_every_checked_attempt_writes_one_row_with_its_door_outcome_and_reference(self):
        operator = f.user('platform-operator')
        ops.grant(operator)
        key = add_key(operator)
        expired = f.member(self.ws)
        models.User.objects.filter(pk=expired.pk).update(password_change_required_at=models.User.objects.get(
            pk=expired.pk).date_joined.replace(year=2020))
        cpt = Client(HTTP_HOST=CPT)
        attempt('owner', client=cpt)  # signed_in
        attempt('owner', WRONG)  # wrong_password
        attempt('nobody-at-all')  # unknown_account
        attempt('platform-operator')  # no_access at cpt: no membership
        attempt('owner', host=ADMIN)  # no_access at admin: not an operator
        attempt(expired.username)  # password_expired
        admin = Client(HTTP_HOST=ADMIN)
        attempt('platform-operator', host=ADMIN, client=admin)  # second_factor_pending, then signed_in
        key_step(admin, key)
        rows = list(models.LoginAttempt.objects.order_by('pk').values_list('username', 'door', 'outcome', 'succeeded'))
        self.assertEqual(rows, [('owner', 'cpt', 'signed_in', True), ('owner', 'cpt', 'wrong_password', False),
                                ('nobody-at-all', 'cpt', 'unknown_account', False),
                                ('platform-operator', 'cpt', 'no_access', False), ('owner', 'admin', 'no_access', False),
                                (expired.username, 'cpt', 'password_expired', False),
                                ('platform-operator', 'admin', 'signed_in', True)])
        refs = list(models.LoginAttempt.objects.values_list('sign_in_ref', flat=True))
        self.assertEqual(len(set(refs)), len(refs))
        self.assertTrue(all(isinstance(ref, uuid.UUID) for ref in refs))
        self.assertEqual(str(models.LoginAttempt.objects.get(door='admin', outcome='signed_in').sign_in_ref),
                         admin.session['cpt_sign_in_ref'])
        self.assertEqual(str(models.LoginAttempt.objects.order_by('pk').first().sign_in_ref), cpt.session['cpt_sign_in_ref'])

    def test_every_refusal_is_counted_and_the_first_of_a_minute_writes_one_event(self):
        with Clock() as clock:
            clock.advance(50)  # the delay (30 s from the last failure) then reaches into the next minute
            for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
                attempt('owner', WRONG)
            for _ in range(3):
                self.assertIn('Too many attempts', sentence(attempt('owner')))
            self.assertEqual(throttle.refused_in('owner'), 3)
            self.assertEqual(rate.count(throttle.REFUSED_CLIENT, ADDRESS_A, since=rate.window_start(60)), 3)
            events = models.SecurityEvent.objects.filter(event='signin.throttled')
            self.assertEqual(events.count(), 1)
            clock.advance(15)  # the same delay, the next minute
            self.assertIn('Too many attempts', sentence(attempt('owner')))
            self.assertEqual(events.count(), 2)
            self.assertEqual(throttle.refused_in('owner'), 4)
            event = events.order_by('created_at').first()
            self.assertEqual((event.subject_id, event.data['check'], event.data['door'], event.data['refused_this_minute']),
                             (self.owner.pk, 'username', 'cpt', 1))
            self.assertEqual(event.data['name_key'], throttle.user_key('owner'))
            self.assertNotIn('owner"', json.dumps(event.data))
            self.assertEqual(event.client, ADDRESS_A)
            self.assertEqual(models.LoginAttempt.objects.count(), settings.SIGNIN_USER_DELAY_AFTER)  # refusals: no row

    def test_no_typed_name_is_kept_as_a_counter_key(self):
        attempt('dr.someone@example.org', WRONG)
        keys = set(models.RateWindow.objects.values_list('key', flat=True))
        self.assertFalse(any('example' in key or 'someone' in key for key in keys))
        self.assertIn(throttle.user_key('DR.SOMEONE@EXAMPLE.ORG'), keys)  # case folded: one delay for every case


class DeviceCookieTests(ThrottleCase):
    def test_the_device_cookie_holds_the_account_id_a_random_id_and_a_date(self):
        client = Client(HTTP_HOST=CPT)
        answer = attempt('owner', client=client)
        cookie = answer.cookies[throttle.device_cookie_name()]
        self.assertEqual((cookie['path'], cookie['samesite'], cookie['max-age']),
                         ('/', 'Strict', settings.KNOWN_DEVICE_DAYS * 24 * 60 * 60))
        self.assertTrue(cookie['httponly'])
        payload = signing.loads(cookie.value, salt=throttle.DEVICE_SALT)
        self.assertEqual(set(payload), {'u', 'r', 'd'})
        self.assertEqual(payload['u'], str(self.owner.pk))
        self.assertNotIn('owner', cookie.value)
        self.assertEqual(throttle.device_user_id(cookie.value), self.owner.pk)

    def test_under_https_it_is_a_host_cookie_and_a_forged_or_stale_one_skips_nothing(self):
        with self.settings(HTTPS=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True):
            self.assertEqual(throttle.device_cookie_name(), '__Host-cptstudio_device')
            answer = Client(HTTP_HOST=CPT).post('/login/', {'username': 'owner', 'password': PASSWORD}, secure=True)
            cookie = answer.cookies['__Host-cptstudio_device']
            self.assertTrue(cookie['secure'])
            self.assertEqual((cookie['path'], cookie['domain']), ('/', ''))
        value = throttle.device_cookie_value(self.owner.pk)
        self.assertIsNone(throttle.device_user_id(value[:-2] + 'xx'))
        self.assertIsNone(throttle.device_user_id(signing.dumps({'u': str(self.owner.pk)}, salt='another-salt')))
        later = __import__('time').time() + (settings.KNOWN_DEVICE_DAYS + 1) * 24 * 60 * 60
        with mock.patch('django.core.signing.time.time', return_value=later):
            self.assertIsNone(throttle.device_user_id(value))
        # another account's device cookie skips nothing for this name
        other = f.member(self.ws)
        for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
            attempt('owner', WRONG)
        borrowed = Client(HTTP_HOST=CPT)
        borrowed.cookies[throttle.device_cookie_name()] = throttle.device_cookie_value(other.pk)
        self.assertIn('Too many attempts', sentence(attempt('owner', client=borrowed)))
        mine = Client(HTTP_HOST=CPT)
        mine.cookies[throttle.device_cookie_name()] = throttle.device_cookie_value(self.owner.pk)
        self.assertEqual(attempt('owner', client=mine).status_code, 302)


class ClearTests(ThrottleCase):
    """The ruled act clear_signin_failures, end to end on a synthetic account (B8)."""

    def reason_file(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'reason.txt'
        path.write_text('Synthetic ruled act for a test: a doctor asked for the delay to be cleared.', encoding='utf-8')
        return str(path)

    def run_command(self, *args):
        out = io.StringIO()
        call_command('clear_signin_failures', *args, stdout=out)
        return out.getvalue()

    def test_the_delay_and_the_pairs_are_cleared_and_the_attempts_kept(self):
        for address in (ADDRESS_A, ADDRESS_B):
            for _ in range(3):
                attempt('Owner' if address == ADDRESS_B else 'owner', WRONG, address=address)
        self.assertIn('Too many attempts', sentence(attempt('owner')))
        before = models.LoginAttempt.objects.count()
        output = self.run_command('--username', 'owner', '--reason-file', self.reason_file(), '--by', 'Synthetic Person')
        self.assertIn(str(self.owner.pk), output)
        self.assertNotIn('owner', output.replace(str(self.owner.pk), ''))
        for scope in (throttle.FAIL_USER, throttle.REFUSED_USER, throttle.FAIL_PAIR):
            self.assertFalse(models.RateWindow.objects.filter(scope=scope).exists(), scope)
        self.assertTrue(models.RateWindow.objects.filter(scope=throttle.FAIL_CLIENT).exists())  # an address is no name's
        self.assertEqual(models.LoginAttempt.objects.count(), before)
        event = models.SecurityEvent.objects.get(event='signin.delay_cleared')
        self.assertEqual((event.actor_label, event.subject_id), ('Synthetic Person', self.owner.pk))
        self.assertGreater(event.data['rows_deleted'], 0)
        self.assertEqual(attempt('owner').status_code, 302)

    def test_an_address_is_cleared_at_once_and_its_pairs_with_it(self):
        office = '192.0.2.44'
        for index in range(settings.SIGNIN_CLIENT_LIMIT):
            attempt(f'colleague-{index % 25}', WRONG, address=office)
        for _ in range(3):
            attempt('owner', WRONG, address=office)  # the owner's pair from the office, under its own limit
        self.assertIn('from this network', sentence(attempt('owner', address=office)))
        before = models.LoginAttempt.objects.count()
        output = self.run_command('--address', office, '--reason-file', self.reason_file(), '--by', 'Synthetic Person')
        self.assertIn('counter row(s) deleted', output)
        self.assertNotIn(office, output)
        for scope in (throttle.FAIL_CLIENT, throttle.REFUSED_CLIENT):
            self.assertFalse(models.RateWindow.objects.filter(scope=scope, key=office).exists(), scope)
        self.assertFalse(models.RateWindow.objects.filter(
            scope=throttle.FAIL_PAIR, key=throttle.pair_key('owner', office)).exists())
        self.assertTrue(models.RateWindow.objects.filter(scope=throttle.FAIL_USER).exists())  # the names' own delays stay
        self.assertEqual(models.LoginAttempt.objects.count(), before)
        event = models.SecurityEvent.objects.get(event='signin.address_cleared')
        self.assertEqual((event.actor_label, event.subject_id, event.data['address']), ('Synthetic Person', None, office))
        self.assertGreater(event.data['rows_deleted'], 0)
        self.assertEqual(attempt('owner', address=office).status_code, 302)

    def test_an_ipv6_address_is_cleared_as_its_slash_64(self):
        for index in range(settings.SIGNIN_CLIENT_LIMIT):
            attempt(f'colleague-{index % 25}', WRONG, address=f'2001:db8:1:2::{index + 1:x}')
        self.assertIn('from this network', sentence(attempt('owner', address='2001:db8:1:2::ff')))
        for given in ('2001:db8:1:2:abcd::1', '2001:db8:1:2::/64'):
            with self.subTest(given=given):
                self.run_command('--address', given, '--reason-file', self.reason_file(), '--by', 'Synthetic Person')
                self.assertEqual(models.SecurityEvent.objects.filter(event='signin.address_cleared').latest(
                    'created_at').data['address'], '2001:db8:1:2::/64')
        self.assertEqual(attempt('owner', address='2001:db8:1:2::ff').status_code, 302)

    def test_an_address_that_is_none_or_a_network_of_another_size_is_refused(self):
        for given in ('not-an-address', '2001:db8:1:2::/48', '2001:db8:1:2::1/64', '10.0.0.0/8', '192.0.2.300', ''):
            with self.subTest(given=given), self.assertRaises(CommandError):
                self.run_command('--address', given, '--reason-file', self.reason_file(), '--by', 'Synthetic Person')
        with self.assertRaises(CommandError):  # one of the two, never both
            self.run_command('--address', '192.0.2.44', '--username', 'owner', '--reason-file', self.reason_file(),
                             '--by', 'Synthetic Person')
        self.assertFalse(models.SecurityEvent.objects.exists())

    def test_it_refuses_without_a_person_or_a_known_account(self):
        attempt('owner', WRONG)
        for args in (('--username', 'owner', '--reason-file', self.reason_file(), '--by', 'admin'),
                     ('--username', 'nobody-here', '--reason-file', self.reason_file(), '--by', 'Synthetic Person')):
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.run_command(*args)
        with self.assertRaises(CommandError):
            self.run_command('--username', 'owner', '--reason-file', self.reason_file())
        self.assertEqual(throttle.failures_of('owner')[0], 1)
        self.assertFalse(models.SecurityEvent.objects.exists())
