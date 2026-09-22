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
import pathlib
import unittest
from pathlib import Path
from unittest.mock import patch

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


def _fake_publisher(seconds):
    """A process whose command line contains the publisher command, so the drain must see it."""
    import subprocess
    return subprocess.Popen([sys.executable, '-c',
                             'import time,sys; time.sleep(float(sys.argv[1]))  # publish_operations_status',
                             str(seconds)])


class InterruptionRecovery(unittest.TestCase):
    """⚠️ A `finally` DOES NOT RUN AFTER SIGKILL OR A HOST FAILURE.

    An activation that pauses the publisher timer and is then killed would leave publication
    stopped indefinitely — the "permanently disabled timer" outcome arriving by accident. These
    prove the durable marker and the supported recovery path actually close that.
    """

    def setUp(self):
        self.restored = []
        self.patch = patch.object(exclusion, '_helper_systemctl',
                                  side_effect=lambda a, u: self.restored.append((a, u)))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(lambda: exclusion.TIMER_STATE.unlink(missing_ok=True))
        exclusion.TIMER_STATE.unlink(missing_ok=True)

    def test_the_marker_is_durable_and_written_before_the_pause(self):
        state = exclusion.note_timer_paused('activation:test', prior_active=True)
        self.assertTrue(exclusion.TIMER_STATE.exists())
        owed = exclusion.pause_owed()
        self.assertEqual(owed['owner'], 'activation:test')
        self.assertTrue(owed['must_restore'])
        self.assertTrue(owed['prior_active'])
        self.assertEqual(owed['paused_at'], state['paused_at'])

    def test_recovery_restores_publication_after_an_interruption(self):
        """The SIGKILL case: marker owed, nothing holding exclusion, no finally ever ran."""
        exclusion.note_timer_paused('activation:killed', prior_active=True)
        os.utime(exclusion.TIMER_STATE, (time.time() - 3600, time.time() - 3600))
        result = exclusion.recover_publication()
        self.assertTrue(result['recovered'], result)
        self.assertEqual(self.restored, [('start', exclusion.PUBLISHER_TIMER)])
        self.assertFalse(exclusion.TIMER_STATE.exists(), 'the debt must be cleared once paid')

    def test_recovery_never_interrupts_a_live_activation(self):
        """⚠️ THE DANGEROUS FAILURE MODE. Restarting the publisher mid-act would recreate exactly
        the race the whole repair exists to remove."""
        exclusion.note_timer_paused('activation:live', prior_active=True)
        os.utime(exclusion.TIMER_STATE, (time.time() - 3600, time.time() - 3600))
        with exclusion.hold('activation:live'):
            result = exclusion.recover_publication()
        self.assertFalse(result['recovered'])
        self.assertEqual(result['reason'], 'activation_still_holds_exclusion')
        self.assertEqual(self.restored, [], 'the timer was restarted under a live act')

    def test_recovery_is_a_no_op_when_no_pause_is_owed(self):
        """It runs on every tick of an unrelated timer; it must cost nothing when idle."""
        result = exclusion.recover_publication()
        self.assertFalse(result['recovered'])
        self.assertEqual(result['reason'], 'no_pause_owed')
        self.assertEqual(self.restored, [])

    def test_recovery_waits_out_the_grace_so_it_cannot_race_a_finally(self):
        exclusion.note_timer_paused('activation:just-started', prior_active=True)
        result = exclusion.recover_publication()
        self.assertFalse(result['recovered'])
        self.assertEqual(result['reason'], 'within_grace')
        self.assertEqual(self.restored, [])

    def test_a_completed_activation_leaves_no_debt(self):
        exclusion.note_timer_paused('activation:clean', prior_active=True)
        exclusion.clear_timer_pause('activation:clean')
        self.assertIsNone(exclusion.pause_owed())
        self.assertFalse(exclusion.recover_publication()['recovered'])


class TheDrainSeesWhatTheLockCannot(unittest.TestCase):
    """⚠️ ON A FIRST INSTALLATION THE RUNNING PUBLISHER PREDATES THE LOCK AND NEVER TAKES IT.
    Acquiring the lock therefore cannot drain it, and pausing the timer does not stop a run
    already executing. Only waiting for the process to exit drains that case."""

    def test_a_live_publisher_is_detected_and_waited_for(self):
        child = _fake_publisher(3)
        try:
            self.assertIn(child.pid, exclusion.publisher_processes())
            start = time.monotonic()
            self.assertTrue(exclusion.drain_publisher(timeout=30))
            self.assertGreater(time.monotonic() - start, 0.5, 'the drain returned without waiting')
            self.assertEqual(exclusion.publisher_processes(), [])
        finally:
            child.wait(30)

    def test_the_probe_does_not_match_its_own_process_tree(self):
        """POSITIVE CONTROL for the self-match that has already bitten twice in this work."""
        self.assertEqual(exclusion.publisher_processes('publish_operations_status'), [])
        self.assertNotIn(os.getpid(), exclusion._own_process_tree() and [] or [])
        self.assertIn(os.getpid(), exclusion._own_process_tree())

    def test_the_drain_is_bounded_and_names_the_blocker(self):
        child = _fake_publisher(20)
        try:
            with self.assertRaises(TimeoutError) as caught:
                exclusion.drain_publisher(timeout=1)
            self.assertIn(str(child.pid), str(caught.exception))
        finally:
            child.kill(); child.wait(30)


class InstalledStatePathsAreNotTargetSourcePaths(unittest.TestCase):
    """⚠️ THE DEFECT THE IMPORT FIX HID, AND IT WOULD HAVE FAILED SILENTLY.

    On a first install the adapter imports this module from the TARGET WORKTREE, because the
    installed tree does not carry it yet. A `__file__`-relative runtime then puts the lock and the
    pause marker under the worktree while the installed publisher looks in the installed runtime:
    two locks, no exclusion, and every check still passing.
    """

    def setUp(self):
        self.original = exclusion.bound_runtime()
        self.addCleanup(exclusion.bind_runtime, self.original['runtime'])

    def test_binding_moves_every_path_together(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            bound = exclusion.bind_runtime(directory)
            for key in ('lock', 'deferrals', 'timer_state'):
                self.assertTrue(bound[key].startswith(str(pathlib.Path(directory).resolve())),
                                f'{key} did not follow the binding: {bound[key]}')
            self.assertEqual(exclusion.LOCK_PATH.parent, pathlib.Path(directory).resolve())
            self.assertEqual(exclusion.TIMER_STATE.parent, pathlib.Path(directory).resolve())
            self.assertEqual(exclusion.DEFERRALS.parent, pathlib.Path(directory).resolve())

    def test_a_lock_taken_after_binding_is_the_bound_one(self):
        """The failure was silent, so prove the FILE that actually gets locked moves too."""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            exclusion.bind_runtime(directory)
            with exclusion.hold('activation:bound'):
                holder = exclusion.holder()
                self.assertEqual(holder['owner'], 'activation:bound')
                self.assertTrue((pathlib.Path(directory) / '.activation-publication.lock').exists())

    def test_two_runtimes_do_not_exclude_each_other(self):
        """⚠️ THE POSITIVE CONTROL FOR THE WHOLE CLASS: it demonstrates the silent failure mode.
        Holding in one runtime leaves the other free, which is exactly what the unfixed adapter
        would have produced while reporting success."""
        import tempfile
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            exclusion.bind_runtime(a)
            with exclusion.hold('activation:in-a'):
                exclusion.bind_runtime(b)
                queue = multiprocessing.get_context('spawn').Queue()
                child = multiprocessing.get_context('spawn').Process(
                    target=_attempt_in, args=(queue, b))
                child.start(); child.join(30)
                self.assertTrue(queue.get(timeout=10),
                                'a second runtime must NOT be excluded — this is the bug')
            exclusion.bind_runtime(a)


def _attempt_in(queue, runtime):
    from ops import activation_exclusion as x
    x.bind_runtime(runtime)
    with x.attempt('probe') as acquired:
        queue.put(bool(acquired))


class BootstrapRecoveryWithoutTheInstalledHook(unittest.TestCase):
    """⚠️ THE INSTALLED backup_alerts HAS NO recover_publication DURING FIRST INSTALLATION.

    Testing recovery with the future installed version proves nothing about that window. The
    watchdog is the mechanism that exists BEFORE the install, so it is what must be exercised.
    """

    def setUp(self):
        self.original = exclusion.bound_runtime()
        self.addCleanup(exclusion.bind_runtime, self.original['runtime'])
        self.directory = __import__('tempfile').mkdtemp()
        exclusion.bind_runtime(self.directory)

    def test_the_installed_baseline_genuinely_lacks_the_hook(self):
        """The premise, verified rather than assumed."""
        installed = pathlib.Path('/opt/meddoc-pro/rebuild/ops/backup_alerts.py')
        if not installed.exists():
            self.skipTest('installed tree unavailable')
        self.assertNotIn('recover_publication', installed.read_text(),
                         'premise gone: the installed hook now exists, so re-read this test')

    def test_the_watchdog_recovers_a_pause_its_parent_never_cleared(self):
        calls = []
        with patch.object(exclusion, '_helper_systemctl', side_effect=lambda a, u: calls.append(a)):
            exclusion.note_timer_paused('activation:killed-during-first-install', prior_active=True)
            os.utime(exclusion.TIMER_STATE, (time.time() - 3600, time.time() - 3600))
            self.assertIsNotNone(exclusion.pause_owed())
            result = exclusion.recover_publication(grace_seconds=1)
        self.assertTrue(result['recovered'], result)
        self.assertEqual(calls, ['start'])
        self.assertIsNone(exclusion.pause_owed(), 'the debt must clear only after restoration')

    def test_the_debt_survives_a_failed_restoration(self):
        """⚠️ Clearing the marker on a restoration that did not happen would lose the debt and
        leave publication stopped with nothing left to notice."""
        with patch.object(exclusion, '_helper_systemctl',
                          side_effect=RuntimeError('systemctl refused')):
            exclusion.note_timer_paused('activation:restore-fails', prior_active=True)
            os.utime(exclusion.TIMER_STATE, (time.time() - 3600, time.time() - 3600))
            with self.assertRaises(RuntimeError):
                exclusion.recover_publication(grace_seconds=1)
        self.assertIsNotNone(exclusion.pause_owed(),
                             'the debt was cleared although restoration failed')
