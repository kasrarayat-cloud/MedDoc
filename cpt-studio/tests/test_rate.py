"""studio.rate (release 1; RELEASE-1-SPEC 3.3 and 3.7): fixed-window counters counted by one atomic upsert, keyed by a
hash, an id or an address - never by a raw typed name. Synthetic values only."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.db import connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import models, rate, request_meta

UTC = dt_timezone.utc
MOMENT = datetime(2026, 11, 24, 12, 0, 30, tzinfo=UTC)
KEY = rate.key_hash('signin-user:owner')


def at(moment):
    return mock.patch.object(timezone, 'now', return_value=moment)


class HitTests(TestCase):
    def test_hits_count_in_their_window_and_the_next_window_starts_again_at_one(self):
        with at(MOMENT):
            self.assertEqual([rate.hit('probe', KEY, window_seconds=60) for _ in range(3)], [1, 2, 3])
        with at(MOMENT + timedelta(seconds=30)):  # 12:01:00, the next minute's window
            self.assertEqual(rate.hit('probe', KEY, window_seconds=60), 1)
        rows = models.RateWindow.objects.filter(scope='probe', key=KEY).order_by('window_start')
        self.assertEqual([(row.window_start, row.count) for row in rows],
                         [(datetime(2026, 11, 24, 12, 0, tzinfo=UTC), 3), (datetime(2026, 11, 24, 12, 1, tzinfo=UTC), 1)])
        self.assertEqual(rows[0].last_at, MOMENT)

    def test_scopes_and_keys_count_apart(self):
        other_key = rate.key_hash('signin-user:operator')
        with at(MOMENT):
            rate.hit('probe', KEY, window_seconds=60)
            self.assertEqual(rate.hit('other', KEY, window_seconds=60), 1)
            self.assertEqual(rate.hit('probe', other_key, window_seconds=60), 1)
            self.assertEqual(rate.hit('probe', KEY, window_seconds=60), 2)

    def test_count_sums_the_windows_that_start_since(self):
        for offset in (0, 60, 61, 3600):
            with at(MOMENT + timedelta(seconds=offset)):
                rate.hit('probe', KEY, window_seconds=60)
        self.assertEqual(rate.count('probe', KEY, since=datetime(2026, 11, 24, 12, 0, tzinfo=UTC)), 4)
        self.assertEqual(rate.count('probe', KEY, since=datetime(2026, 11, 24, 12, 1, tzinfo=UTC)), 3)
        self.assertEqual(rate.count('probe', KEY, since=datetime(2026, 11, 24, 12, 2, tzinfo=UTC)), 1)
        self.assertEqual(rate.count('probe', rate.key_hash('nobody'), since=MOMENT - timedelta(days=1)), 0)

    def test_the_latest_hit_time_never_moves_back(self):
        with at(MOMENT):
            rate.hit('probe', KEY, window_seconds=3600)
        with at(MOMENT - timedelta(seconds=20)):  # a slower request of the same window arrives late
            rate.hit('probe', KEY, window_seconds=3600)
        self.assertEqual(models.RateWindow.objects.get(scope='probe', key=KEY).last_at, MOMENT)

    def test_windows_start_at_whole_multiples_of_their_length(self):
        self.assertEqual(rate.window_start(60, MOMENT), datetime(2026, 11, 24, 12, 0, tzinfo=UTC))
        self.assertEqual(rate.window_start(900, MOMENT), datetime(2026, 11, 24, 12, 0, tzinfo=UTC))
        self.assertEqual(rate.window_start(3600, MOMENT + timedelta(minutes=59)),
                         datetime(2026, 11, 24, 12, 0, tzinfo=UTC))
        for seconds in (0, -60, 1.5, True, '60'):
            with self.subTest(window_seconds=seconds), self.assertRaises(ValueError):
                rate.hit('probe', KEY, window_seconds=seconds)
        for scope in ('', 'Probe', 'probe scope', 'p' * 41, None):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                rate.hit(scope, KEY, window_seconds=60)


class KeyTests(TestCase):
    def test_key_hash_is_stable_keyed_and_never_holds_the_text(self):
        names = ('owner', 'platform-operator', 'doctor@example.org', 'Correct-Horse-Battery-9', '\u00e9l\u00e8ve')
        for name in names:
            with self.subTest(name=name):
                key = rate.key_hash(name)
                self.assertRegex(key, r'^[0-9a-f]{64}$')
                self.assertEqual(key, rate.key_hash(name))
                self.assertNotIn(name.lower(), key)
        self.assertEqual(len({rate.key_hash(name) for name in names}), len(names))
        with override_settings(SECRET_KEY='another-synthetic-secret-key-for-the-rate-test-only'):
            self.assertNotEqual(rate.key_hash('owner'), KEY)  # keyed: a key is not the name's plain digest

    def test_a_typed_name_is_never_a_key(self):
        for typed in ('owner', 'doctor@example.org', 'signin-user:owner', 'x' * 64, KEY.upper(), '', 'a' * 129,
                      '2001:db8::1', '2001:db8:0:0:1::/64', '2001:DB8:1:2::/64', '{%s}' % uuid.uuid4(), None, 7):
            with self.subTest(key=typed), self.assertRaisesMessage(ValueError, 'never typed text'):
                rate.hit('probe', typed, window_seconds=60)
        self.assertFalse(models.RateWindow.objects.exists())

    def test_the_four_key_forms_are_counted(self):
        account = uuid.uuid4()
        for key in (KEY, str(account), account, '203.0.113.9', '2001:db8:1:2::/64'):
            with self.subTest(key=key):
                self.assertEqual(rate.hit('probe', key, window_seconds=60), 1 if key is not account else 2)
        self.assertEqual(set(models.RateWindow.objects.values_list('key', flat=True)),
                         {KEY, str(account), '203.0.113.9', '2001:db8:1:2::/64'})

    def test_every_client_key_is_a_key(self):
        factory = RequestFactory()
        for address in ('203.0.113.9', '2001:db8:1:2:3:4:5:6', '::ffff:198.51.100.7', 'fe80::1%eth0', 'not an address',
                        'doctor@example.org', ''):
            with self.subTest(address=address):
                key = request_meta.client_key(factory.get('/', REMOTE_ADDR=address))
                self.assertGreaterEqual(rate.hit('client', key, window_seconds=60), 1)
                self.assertNotIn('doctor', key)
        # a value that is no address is counted by its keyed hash, never as the text a client sent
        self.assertEqual(request_meta.client_key(factory.get('/', REMOTE_ADDR='doctor@example.org')),
                         rate.key_hash('client:doctor@example.org'))


class ConcurrencyTests(TransactionTestCase):
    """Two threads, each on its own database connection, hit one key 100 times at once: every hit is counted and every
    count from 1 to 200 is answered exactly once - a lost update would repeat a count and end below 200."""

    def test_two_threads_of_a_hundred_hits_count_exactly_two_hundred(self):
        answers, errors = [], []
        start = threading.Barrier(2)

        def worker():
            try:
                start.wait(timeout=30)
                mine = [rate.hit('race', KEY, window_seconds=86400) for _ in range(100)]
                answers.extend(mine)
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connection.close()
        with at(MOMENT):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=120)
        self.assertEqual(errors, [])
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(answers), list(range(1, 201)))
        row = models.RateWindow.objects.get(scope='race', key=KEY)
        self.assertEqual(row.count, 200)
        self.assertEqual(rate.count('race', KEY, since=MOMENT - timedelta(days=1)), 200)
