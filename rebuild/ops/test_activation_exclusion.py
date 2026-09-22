"""Exclusion between activation and the publisher, demonstrated rather than asserted.

Every test here exists because the 2026-09-21 activation of `5b2576c5` stopped when a publisher
tick landed inside its window. Timing was rejected as the fix: it shortens a race without
excluding anything.
"""
import json
import multiprocessing
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops import activation_exclusion as exclusion


def _child_attempt(queue):
    """A separate PROCESS, because flock is held per open file description — two attempts in one
    process would both succeed and the test would prove nothing."""
    with exclusion.attempt('test-publisher') as acquired:
        queue.put(bool(acquired))


def _child_hold_and_fail(queue):
    try:
        with exclusion.hold('test-activation-that-fails'):
            queue.put('holding')
            raise RuntimeError('the act failed partway, exactly as the real one did')
    except RuntimeError:
        queue.put('raised')


class ExclusionIsReal(unittest.TestCase):
    def setUp(self):
        self.context = multiprocessing.get_context('spawn')

    def ask_child(self, target):
        queue = self.context.Queue()
        child = self.context.Process(target=target, args=(queue,))
        child.start(); child.join(30)
        self.assertEqual(child.exitcode, 0, 'child process failed')
        out = []
        while not queue.empty():
            out.append(queue.get())
        return out

    def test_a_forced_overlap_is_refused_not_raced(self):
        """THE CASE THAT BROKE THE ACTIVATION. A publisher attempt during a held act must not win."""
        with exclusion.hold('test-activation'):
            self.assertEqual(self.ask_child(_child_attempt), [False])

    def test_the_positive_control_the_refusal_depends_on(self):
        """Without this, `False` above could mean the mechanism is broken rather than working."""
        self.assertEqual(self.ask_child(_child_attempt), [True])

    def test_a_failed_activation_releases_exclusion(self):
        """⚠️ FAILURE CLEANUP. The stopped act left its own advisory lock file behind with a dead
        pid. A mechanism that could wedge publication forever after a failure would be a worse bug
        than the race it fixes."""
        self.assertEqual(self.ask_child(_child_hold_and_fail), ['holding', 'raised'])
        self.assertEqual(self.ask_child(_child_attempt), [True],
                         'publication did not resume after a failed activation')

    def test_a_dead_holder_cannot_wedge_publication(self):
        """flock is kernel-held against a descriptor, so death releases it. This is why the
        mechanism is flock and not a lock FILE whose liveness has to be reasoned about."""
        queue = self.context.Queue()
        child = self.context.Process(target=_child_hold_and_fail, args=(queue,))
        child.start(); child.join(30)
        self.assertEqual(self.ask_child(_child_attempt), [True])

    def test_the_drain_is_bounded_and_refuses_rather_than_hangs(self):
        """An unbounded wait is its own outage. Refusing names the problem."""
        queue = self.context.Queue()
        child = self.context.Process(target=_hold_briefly, args=(queue,))
        child.start()
        self.assertEqual(queue.get(timeout=30), 'holding')
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            with exclusion.hold('test-activation', timeout=1):
                pass
        self.assertLess(time.monotonic() - start, 20)
        child.join(30)

    def test_the_drain_succeeds_once_publication_finishes(self):
        """The blocking acquire IS the drain: it cannot complete until the writer releases."""
        queue = self.context.Queue()
        child = self.context.Process(target=_hold_briefly, args=(queue,))
        child.start()
        self.assertEqual(queue.get(timeout=30), 'holding')
        with exclusion.hold('test-activation', timeout=30):
            pass
        child.join(30)

    def test_every_deferral_is_recorded_so_monitoring_cannot_go_silent(self):
        before = exclusion.DEFERRALS.read_text().count('\n') if exclusion.DEFERRALS.exists() else 0
        exclusion.record('publication_deferred', reason='unit-test', holder='test')
        after = exclusion.DEFERRALS.read_text().splitlines()
        self.assertEqual(len(after), before + 1)
        entry = json.loads(after[-1])
        self.assertEqual(entry['event'], 'publication_deferred')
        self.assertIn('at_utc', entry)


def _hold_briefly(queue):
    with exclusion.hold('test-in-flight-publication'):
        queue.put('holding')
        time.sleep(3)


if __name__ == '__main__':
    unittest.main()
