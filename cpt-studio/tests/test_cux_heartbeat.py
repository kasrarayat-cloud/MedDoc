"""Core repair (2026-11-03), decision (j): the worker heartbeat (models.WorkerBeat; jobs.beat, start_heartbeat,
worker_responding; run_worker). A beat older than jobs.WORKER_SILENT_SECONDS is a worker that is not responding; no
beat at all is nothing known, never a dead worker."""
from __future__ import annotations

import io
import threading
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import jobs, models
from studio.migrations import __path__ as MIGRATIONS


class BeatTests(TestCase):
    def test_no_beat_is_nothing_known(self):
        self.assertIsNone(jobs.worker_responding())

    def test_a_recent_beat_responds_and_an_old_one_does_not(self):
        now = timezone.now()
        jobs.beat(now=now)
        row = models.WorkerBeat.objects.get(name=jobs.WORKER_NAME)
        self.assertIsNotNone(row.pid)
        self.assertTrue(jobs.worker_responding(now=now + timedelta(seconds=jobs.WORKER_SILENT_SECONDS)))
        self.assertFalse(jobs.worker_responding(now=now + timedelta(seconds=jobs.WORKER_SILENT_SECONDS + 1)))
        jobs.beat(now=now + timedelta(seconds=200))  # one row, updated
        self.assertEqual(models.WorkerBeat.objects.count(), 1)
        self.assertTrue(jobs.worker_responding(now=now + timedelta(seconds=210)))

    def test_a_failed_beat_never_raises(self):
        with mock.patch.object(models.WorkerBeat.objects, 'update_or_create', side_effect=RuntimeError('synthetic')):
            jobs.beat()  # logged, not raised


class HeartbeatThreadTests(SimpleTestCase):
    def test_the_thread_beats_until_told_to_stop(self):
        stop, beats = threading.Event(), []
        with mock.patch('studio.jobs.beat', side_effect=lambda **kw: beats.append(1)), \
                mock.patch('django.db.connection.close'):
            thread = jobs.start_heartbeat(stop.is_set, interval=0.2)
            deadline = timezone.now() + timedelta(seconds=5)
            while len(beats) < 3 and timezone.now() < deadline:
                threading.Event().wait(0.05)
            stop.set()
            thread.join(timeout=5)
        self.assertGreaterEqual(len(beats), 3)
        self.assertFalse(thread.is_alive())
        self.assertTrue(thread.daemon)

    def test_the_worker_command_beats_before_its_loop(self):
        order = []
        thread = mock.Mock()
        with mock.patch('studio.jobs.beat', side_effect=lambda **kw: order.append('beat')), \
                mock.patch('studio.jobs.start_heartbeat',
                           side_effect=lambda stop, **kw: order.append('thread') or thread), \
                mock.patch('studio.jobs.work', side_effect=lambda stop, **kw: order.append('work')):
            call_command('run_worker', stdout=io.StringIO())
        self.assertEqual(order, ['beat', 'thread', 'work'])
        thread.join.assert_called_once()

    def test_the_heartbeat_outlives_the_drain_flag_until_the_loop_returns(self):
        """Refutation r2, L5-2 and L5-6: a SIGTERM asks the worker to stop once its current stage is done, and it is
        busy until then, so the heartbeat stops when the loop has returned - never on the drain flag - and --once beats
        too."""
        import signal

        handlers = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGINT, handlers[0])
        self.addCleanup(signal.signal, signal.SIGTERM, handlers[1])
        for options in ({}, {'once': True}):
            with self.subTest(options):
                given, seen = [], {}
                thread = mock.Mock()

                def start(stop, **kwargs):
                    given.append(stop)
                    return thread

                def loop(*args, **kwargs):
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)  # the drain flag, as docker stop sets it
                    seen['during'] = given[0]()
                    return None
                with mock.patch('studio.jobs.beat'), mock.patch('studio.jobs.start_heartbeat', side_effect=start), \
                        mock.patch('studio.jobs.mark_stale'), mock.patch('studio.jobs.work', side_effect=loop), \
                        mock.patch('studio.jobs.claim_next', side_effect=lambda: loop() or None):
                    call_command('run_worker', stdout=io.StringIO(), **options)
                self.assertEqual(len(given), 1)
                self.assertIs(seen['during'], False)  # the flag is set and the worker is still working: it beats
                self.assertIs(given[0](), True)  # its loop returned: the heartbeat stops
                thread.join.assert_called_once()

    def test_the_migration_is_additive(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(MIGRATIONS[0]).parents[1] / 'ops'))
        import install
        source = (Path(MIGRATIONS[0]) / '0012_cux_worker_beat.py').read_text()
        self.assertTrue(install.migration_verdict(source)['safe'])
