"""Repair round 3 of release 1, found by builder d3's suite (a lead commit): throttle.reserve read its minute from the
``now`` it took at entry, and rate.hit read the clock again for the bucket it increments, so a minute boundary between the
two hid the window's earlier failures from that reservation - a burst straddling a boundary got up to one more limit of
password checks (the sign-in doors' FAIL_CLIENT and FAIL_PAIR places and the account page's checks use reserve). The
reservation's hit now lands in the window its own reading names. Synthetic key; only the clock is patched."""
import uuid
from datetime import datetime, timezone as dt_timezone
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
