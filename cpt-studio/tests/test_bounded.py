"""studio/bounded.py: work run in a forked child under a wall clock and a memory allowance - today the Word-to-PDF
conversion of the coding step (studio.fable.document.convert_docx; tests/test_fable_document.py drives it through a fake
converter). The child returns exactly what the function returns; past the wall clock it is killed and reaped; past the
memory allowance the work is refused; an exception inside it is logged and raised without its internals. Synthetic data
only; no network.

Moved from the earlier pipeline's round-4 suite (tests/test_repairs_r4_lead_bounded.py) when lane E removed the routing
and context extraction those tests also drove; the four generic tests are unchanged but for the function the first one
runs.
"""
import os
import time
from unittest import mock

from django.test import SimpleTestCase

from studio import bounded

MIB = 1024 * 1024


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
