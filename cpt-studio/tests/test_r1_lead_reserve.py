"""Repair round 3 of release 1, found by builder d3's suite (a lead commit): throttle.reserve read its minute from the
``now`` it took at entry, and rate.hit read the clock again for the bucket it increments, so a minute boundary between the
two hid the window's earlier failures from that reservation - a burst straddling a boundary got up to one more limit of
password checks (the sign-in doors' FAIL_CLIENT and FAIL_PAIR places and the account page's checks use reserve). The
reservation's hit now lands in the window its own reading names. Synthetic key; only the clock is patched."""
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TransactionTestCase

from studio import rate, throttle, views

SCOPE, LIMIT = views.ACCOUNT_SCOPE, 5  # the password change's own scope
BEFORE = datetime(2026, 11, 25, 3, 0, 59, 900000, tzinfo=dt_timezone.utc)
AFTER = datetime(2026, 11, 25, 3, 1, 0, 100000, tzinfo=dt_timezone.utc)


class ReserveAcrossAMinuteTests(TransactionTestCase):
    def test_a_reservation_whose_clock_crosses_a_minute_still_sees_that_minutes_failures(self):
        key = str(uuid.uuid4())
        with mock.patch('django.utils.timezone.now', return_value=BEFORE):
            for _ in range(LIMIT):
                self.assertTrue(throttle.reserve(SCOPE, key, LIMIT))  # five failures, kept, in the 03:00 bucket
            self.assertFalse(throttle.reserve(SCOPE, key, LIMIT))  # control: the sixth, same minute, refused
        clock = iter([BEFORE] + [AFTER] * 50)  # reserve's own reading first, then every later one in the next minute
        with mock.patch('django.utils.timezone.now', side_effect=lambda: next(clock)):
            allowed = throttle.reserve(SCOPE, key, LIMIT)
        self.assertFalse(allowed, 'the window already holds LIMIT failures, yet one more place was given')

    def test_a_hit_given_its_moment_counts_in_that_moments_window(self):
        key = str(uuid.uuid4())
        with mock.patch('django.utils.timezone.now', return_value=AFTER):
            self.assertEqual(rate.hit(SCOPE, key, window_seconds=60, now=BEFORE), 1)
            self.assertEqual(rate.hit(SCOPE, key, window_seconds=60), 1)  # no moment given: the clock's window
        self.assertEqual(rate.count(SCOPE, key, since=rate.window_start(60, BEFORE)), 2)
        self.assertEqual(rate.count(SCOPE, key, since=rate.window_start(60, AFTER)), 1)


class InflightPlaceAcrossAMinuteTests(TransactionTestCase):
    """The same class in Door._take_inflight_place (builder a3's probe 9): the earlier windows' sum was taken against
    refusal()'s moment and the place in rate.hit's own window, so with one attempt in flight a boundary between the two
    counted none ahead - and a name one failure short of the username delay reached the password check."""

    def test_an_attempt_whose_place_crosses_a_minute_still_counts_the_one_in_flight(self):
        from django.test import RequestFactory
        from studio import request_meta
        boundary = datetime(2026, 11, 26, 12, 0, tzinfo=dt_timezone.utc)
        name = 'synthetic-owner-lead'
        with mock.patch('django.utils.timezone.now', return_value=boundary - timedelta(seconds=10)):
            rate.hit(throttle.INFLIGHT_USER, throttle.user_key(name), window_seconds=throttle.MINUTE)  # one in flight
        door = throttle.Door(RequestFactory().post('/login/', REMOTE_ADDR='198.51.100.7'), request_meta.CPT, name)
        later = boundary + timedelta(milliseconds=1)
        with mock.patch('django.utils.timezone.now', return_value=later):  # every reading after the moment: the next minute
            ahead = door._take_inflight_place(boundary - timedelta(milliseconds=1))
        self.assertEqual(ahead, 1, 'one attempt of the name is in flight')
