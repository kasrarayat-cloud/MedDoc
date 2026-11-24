"""studio/bounded.py: work run in a forked child under a wall clock and a memory allowance - today the Word-to-PDF
conversion of the coding step (studio.fable.docx_package.convert_in_child; tests/test_fable_document.py drives it through
fake converters). The child returns exactly what the function returns; past the wall clock it is killed and reaped; past
the memory allowance the work is refused; an exception inside it is logged and raised without its internals; and every
process group the work reported is killed by the parent, timeout or not (release 1, E1: LibreOffice runs in a session
of its own, which killing the child does not reach). Synthetic data only; no network.

Moved from the earlier pipeline's round-4 suite (tests/test_repairs_r4_lead_bounded.py) when lane E removed the routing
and context extraction those tests also drove; the four generic tests are unchanged but for the function the first one
runs.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import bounded

MIB = 1024 * 1024
# A grandchild that ignores SIGTERM and writes "<its pid> <its session id>" to the note file argv[2] once it runs.
GRANDCHILD = ('import os, signal, sys, time\n'
              'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
              'note = open(sys.argv[2] + ".tmp", "w"); note.write(f"{os.getpid()} {os.getsid(0)}"); note.close()\n'
              'os.rename(sys.argv[2] + ".tmp", sys.argv[2])\n'
              'time.sleep(120)\n')


def marked(marker):
    """The pids of running processes whose command line holds ``marker`` as one of its arguments (a zombie has none)."""
    found = []
    for entry in os.listdir('/proc'):
        if entry.isdigit() and int(entry) != os.getpid():
            try:
                with open(f'/proc/{entry}/cmdline', 'rb') as handle:
                    if marker.encode() in handle.read().split(b'\x00'):
                        found.append(int(entry))
            except OSError:
                continue
    return found


def kill_marked(marker):
    """A failing run never leaves its grandchild behind: everything still carrying the test's own marker is killed."""
    for pid in marked(marker):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def start_grandchild(marker, note):
    """In the bounded child: ignore SIGTERM, start a grandchild in a session of its own (as soffice is started) that
    ignores SIGTERM too, report its process group as soffice_convert does, and never return."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    process = subprocess.Popen([sys.executable, '-c', GRANDCHILD, marker, str(note)], start_new_session=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bounded.report_group(process.pid)
    while not Path(note).exists():
        time.sleep(0.01)
    time.sleep(120)


def _sleep_then(value, seconds):
    time.sleep(seconds)
    return value


def _allocate(megabytes):
    blocks = [bytearray(MIB) for _ in range(megabytes)]
    return len(blocks)


def _fail():
    raise ValueError('synthetic failure inside the bounded child')


def _summary(text, repeat):
    """A pure, Django-free function with a structured answer, as a bounded child is given one."""
    words = (text + ' ') * repeat
    return {'words': len(words.split()), 'first': words.split()[0], 'bytes': words.encode('utf-8'), 'none': None,
            'pages': (1, 2, 3)}


def _reports(*lines):
    """Reports process groups as a child's work would, without starting any: the parent's killing is then a mock's."""
    for sign, pgid in lines:
        (bounded.report_group if sign == '+' else bounded.group_ended)(pgid)
    return 'reported'


def _reports_then_fails(pgid):
    bounded.report_group(pgid)
    raise ValueError('synthetic failure after a process group was started')


def _recording_killpg(calls):
    """A stand-in for os.killpg in the parent: records each call; signal 0 (is the group gone?) answers gone."""
    def killpg(pgid, number):
        calls.append((pgid, number))
        if number == 0:
            raise ProcessLookupError
    return killpg


class RunBoundedTests(SimpleTestCase):
    def test_the_child_returns_exactly_what_the_function_returns(self):
        for text, repeat in (('SYNTHETIC TEST DOCUMENT', 1), ('Procedure: colonoscopy to the cecum.', 400),
                             ('Résumé – naïve café', 3)):
            with self.subTest(text=text, repeat=repeat):
                inline = _summary(text, repeat)
                child = bounded.run_bounded(_summary, text, repeat, seconds=30, memory_bytes=512 * MIB)
                self.assertEqual(child, inline)

    def test_past_the_wall_clock_the_child_is_killed_and_reaped(self):
        pids, real_fork = [], os.fork

        def recording_fork():
            pid = real_fork()
            pids.append(pid)
            return pid

        start = time.monotonic()
        with mock.patch('studio.bounded.os.fork', recording_fork), self.assertRaises(bounded.Overrun) as caught:
            bounded.run_bounded(_sleep_then, 'late', 20, seconds=1, memory_bytes=64 * MIB)
        self.assertEqual(caught.exception.reason, 'time')
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(len(pids), 1)
        with self.assertRaises(ChildProcessError):
            os.waitpid(pids[0], os.WNOHANG)  # killed and already reaped: no zombie is left behind

    def test_past_the_memory_allowance_the_work_is_refused(self):
        with self.assertRaises(bounded.Overrun) as caught:
            bounded.run_bounded(_allocate, 400, seconds=30, memory_bytes=64 * MIB)
        self.assertEqual(caught.exception.reason, 'memory')
        self.assertEqual(bounded.run_bounded(_allocate, 8, seconds=30, memory_bytes=256 * MIB), 8)

    def test_an_exception_in_the_child_is_logged_and_raised_without_internals(self):
        with self.assertLogs('studio.bounded', 'ERROR') as logged, self.assertRaises(RuntimeError) as caught:
            bounded.run_bounded(_fail, seconds=30, memory_bytes=64 * MIB)
        self.assertIn('synthetic failure inside the bounded child', '\n'.join(logged.output))
        self.assertNotIn('synthetic failure', str(caught.exception))


class ProcessGroupTests(SimpleTestCase):
    """E1: what the child's work starts in a session of its own is killed by the parent, whatever the child does."""

    def test_a_runner_that_ignores_sigterm_and_starts_a_grandchild_in_its_own_session_is_gone_after_the_timeout(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        marker, note = f'cpt-lane5-grandchild-{uuid.uuid4().hex}', folder / 'grandchild'
        try:
            with self.assertRaises(bounded.Overrun) as caught:
                bounded.run_bounded(start_grandchild, marker, note, seconds=8, memory_bytes=512 * MIB)
            self.assertEqual(caught.exception.reason, 'time')
            pid, session = map(int, note.read_text().split())  # the positive control: it ran, in its own session
            self.assertEqual(pid, session)
            self.assertNotEqual(session, os.getsid(0))
            self.assertEqual(marked(marker), [])  # gone: neither the child's kill nor SIGTERM would have done it
        finally:
            kill_marked(marker)

    def test_the_parent_kills_each_group_reported_and_not_ended_and_never_its_own(self):
        calls = []
        with mock.patch('studio.bounded.os.killpg', _recording_killpg(calls)):  # the child reports; it kills nothing
            answer = bounded.run_bounded(_reports, ('+', 0), ('+', 1), ('+', os.getpgrp()), ('+', 987_651),
                                         ('-', 987_651), ('+', 987_652), ('+', 987_652), seconds=30,
                                         memory_bytes=64 * MIB)
        self.assertEqual(answer, 'reported')
        self.assertEqual(calls, [(987_652, signal.SIGKILL), (987_652, 0)])

    def test_a_group_reported_before_the_work_failed_is_killed_too(self):
        calls = []
        with mock.patch('studio.bounded.os.killpg', _recording_killpg(calls)), \
                self.assertLogs('studio.bounded', 'ERROR'), self.assertRaises(RuntimeError):
            bounded.run_bounded(_reports_then_fails, 987_654, seconds=30, memory_bytes=64 * MIB)
        self.assertEqual(calls, [(987_654, signal.SIGKILL), (987_654, 0)])

    def test_reports_outside_a_bounded_child_do_nothing(self):
        self.assertIsNone(bounded._GROUPS_FD)
        with mock.patch('studio.bounded.os.write') as write:
            bounded.report_group(12345)
            bounded.group_ended(12345)
        write.assert_not_called()
