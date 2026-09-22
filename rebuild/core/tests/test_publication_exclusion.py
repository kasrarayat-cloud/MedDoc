"""The publisher COMMAND defers under activation exclusion, and guarded data does not move.

The module-level tests in `ops/test_activation_exclusion.py` prove the primitive. These prove the
thing that actually broke the activation: a real `publish_operations_status` run landing inside an
act's window must write nothing.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import ServiceHealth

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops import activation_exclusion as exclusion

REPORT = ({'condition': 'synthetic test condition', 'severity': 'ok', 'healthy': True,
           'action': 'none', 'clinical_content_included': False,
           'local_capture': {'run': 'synthetic'}, 'monitor_age_seconds': 1,
           'stale_after_seconds': 600}, 0)


#: ⚠️ A PLAIN SUBPROCESS, NOT A multiprocessing CHILD. A spawned child re-imports this module,
#: which needs Django configured, so the holder never started and every assertion failed on an
#: empty queue — a harness fault that reads exactly like a broken mechanism. This holder imports
#: only the exclusion module and prints one line when it has the lock.
HOLDER = """
import sys, time
sys.path.insert(0, %r)
from ops import activation_exclusion as exclusion
with exclusion.hold('test-activation-window'):
    print('holding', flush=True)
    time.sleep(float(sys.argv[1]))
""" % str(Path(__file__).resolve().parents[2])


class Holder:
    """Holds exclusion in another process for the life of the `with` block."""

    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        self.process = subprocess.Popen(
            [sys.executable, '-c', HOLDER, str(self.seconds)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if line.strip() == 'holding':
                return self
            if self.process.poll() is not None:
                raise AssertionError('holder exited: ' + self.process.stderr.read()[:400])
        raise AssertionError('holder never acquired exclusion')

    def __exit__(self, *exc):
        self.process.wait(timeout=60)
        return False


class TheGuardedRowCannotMoveDuringAnAct(TestCase):
    def setUp(self):
        self.row = ServiceHealth.objects.create(
            key='backup', condition='before the act', severity='ok', healthy=True,
            action='', payload={}, computed_at=timezone.now(), expected_interval_seconds=300)

    def snapshot(self):
        row = ServiceHealth.objects.get(key='backup')
        return (row.condition, row.severity, row.healthy, row.computed_at, row.published_at)

    @patch('core.management.commands.publish_operations_status.collect', return_value=REPORT)
    def test_a_publisher_tick_inside_the_window_writes_nothing(self, _collect):
        """⚠️ THE EXACT CASE THAT STOPPED THE ACTIVATION, forced rather than waited for."""
        before = self.snapshot()
        with Holder(4):
            call_command('publish_operations_status')      # must defer, not raise, not write
            self.assertEqual(self.snapshot(), before, 'the guarded row moved during the act')

    @patch('core.management.commands.publish_operations_status.collect', return_value=REPORT)
    def test_publication_resumes_after_the_act_and_recomputes(self, _collect):
        """POSITIVE CONTROL for the test above, and the resumption requirement in one."""
        before = self.snapshot()
        with Holder(3):
            call_command('publish_operations_status')
            self.assertEqual(self.snapshot(), before)
        call_command('publish_operations_status')          # exclusion is free again
        after = self.snapshot()
        self.assertNotEqual(after, before, 'publication did not resume after the act')
        self.assertEqual(ServiceHealth.objects.get(key='backup').condition,
                         'synthetic test condition')

    @patch('core.management.commands.publish_operations_status.collect', return_value=REPORT)
    def test_a_deferred_tick_claims_no_health_and_is_recorded(self, _collect):
        before_lines = (exclusion.DEFERRALS.read_text().splitlines()
                        if exclusion.DEFERRALS.exists() else [])
        with Holder(3):
            call_command('publish_operations_status')
        after_lines = exclusion.DEFERRALS.read_text().splitlines()
        self.assertGreater(len(after_lines), len(before_lines))
        deferral = [json.loads(l) for l in after_lines[len(before_lines):]
                    if json.loads(l)['event'] == 'publication_deferred']
        self.assertTrue(deferral, 'a deferral must be recorded, never silent')
        self.assertEqual(deferral[-1]['reason'], 'activation_holds_exclusion')
        # the row still says what it said before: no manufactured green
        self.assertEqual(ServiceHealth.objects.get(key='backup').condition, 'before the act')

    @patch('core.management.commands.publish_operations_status.collect', return_value=REPORT)
    def test_observations_are_collected_inside_the_lock_not_before_it(self, collect):
        """A tick that collected first and wrote afterwards would publish a pre-activation picture
        under a current timestamp — a stale reading wearing fresh clothes."""
        collect.reset_mock()
        with Holder(3):
            call_command('publish_operations_status')
            self.assertEqual(collect.call_count, 0,
                             'the deferred tick collected observations it could not publish')
        call_command('publish_operations_status')
        self.assertEqual(collect.call_count, 1)
