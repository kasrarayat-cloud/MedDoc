"""Routing cost on a coordinated list, and the exactness of the bounded pre-trigger reading behind its repair.

A coordinated list of N services is one group, so each of its N targets read every member's pre-triggers over its
whole clause window (_clause_reading_cues): 'EUS, ' x 400 took 21 s. Pre-triggers (cues._pre: a trigger and at most
five fillers, ending at the member) are now read from each member's own PRE_WORDS-word start and shared by every
target whose window reaches back that far. Synthetic text only; pure functions.
"""
import time
from datetime import date

from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi.detect import route, status_for_span

DOS = date(2026, 10, 21)
HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'


class CoordinatedListCostTests(SimpleTestCase):
    def test_a_long_coordinated_list_routes_in_bounded_time(self):
        text = HEADER + 'Findings: ' + 'EUS, ' * 400 + 'EUS.\n'
        start = time.perf_counter()
        result = route(text, DOS)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 10.0)  # 21 s before the repair, about 3 s after it
        self.assertEqual(len(result.finding('gi.eus').mentions), 401)


class BoundedPreTriggerTests(SimpleTestCase):
    """The bounded start finds every pre-trigger a whole-window search finds: a trigger with its five fillers right
    before the member, at the far end of a long clause."""

    NOISE = ' '.join(f'word{n}' for n in range(60))

    def test_a_trigger_five_fillers_back_still_governs(self):
        sentence = f'The mucosa {self.NOISE} looked fine and no prior repeat screening diagnostic upper EGD was needed.'
        text = HEADER + 'Findings: ' + sentence + '\n'
        start = text.index('EGD')
        status, cues = status_for_span(text, start, start + 3, DOS)
        self.assertEqual(status, 'negated', cues)
        self.assertTrue(any(c.startswith('negated: no prior repeat screening diagnostic upper') for c in cues), cues)

    def test_the_bound_covers_the_longest_pre_trigger(self):
        # a trigger of at most six words and at most five fillers: PRE_WORDS keeps twice that
        self.assertGreaterEqual(detect.PRE_WORDS, 2 * (6 + 5))
