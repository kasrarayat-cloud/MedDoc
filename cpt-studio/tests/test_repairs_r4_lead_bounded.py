"""Round 4: routing and context extraction run under the stage's wall clock and a memory limit (studio/bounded.py).

Round 4 measured routes of 72-113 s and a 1.5 GiB peak on pastes far below the 400,000-character limit
(routing:10, routing:14, structure:8, pipeline:0, pipeline:1, pipeline:3), while JOB_DEADLINE_SECONDS was read nowhere.
An overrun now fails the stage with a plain message (or refuses a member's context change) instead of holding the single
worker. Synthetic data only; no network.
"""
import json
import os
import time
from datetime import date
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, models
from studio.gi import context as gi_context
from studio.gi import detect
from studio.types import to_jsonable
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.support import factories as f

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi'
MIB = 1024 * 1024


def _sleep_then(value, seconds):
    time.sleep(seconds)
    return value


def _allocate(megabytes):
    blocks = [bytearray(MIB) for _ in range(megabytes)]
    return len(blocks)


def _fail():
    raise ValueError('synthetic failure inside the bounded child')


_ROUTE = detect.route
_EXTRACT_CONTEXT = gi_context.extract_context


def _slow_route(text, service_date=None):
    time.sleep(30)
    return _ROUTE(text, service_date)


class RunBoundedTests(SimpleTestCase):
    def test_the_child_returns_exactly_what_the_function_returns(self):
        for path in sorted(FIXTURES.glob('*.txt'))[:4]:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path.name):
                inline = to_jsonable(detect.route(text, date(2026, 10, 21)))
                child = to_jsonable(bounded.run_bounded(detect.route, text, date(2026, 10, 21), seconds=30,
                                                        memory_bytes=512 * MIB))
                self.assertEqual(json.dumps(child, sort_keys=True), json.dumps(inline, sort_keys=True))

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

    def test_the_round_4_quadratic_shapes_end_within_the_deadline(self):
        header = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
        shapes = {
            'routing:10': header + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum'
                          + '; cecum' * 40000 + '.\n',
            'routing:14': header + 'Procedure: EGD' + '; EGD' * 40000 + '.\n',
            'structure:8': header + 'Findings: ' + 'EUS, ' * 10000 + 'done.',
        }
        for name, text in shapes.items():
            with self.subTest(name):
                start = time.monotonic()
                try:
                    bounded.run_bounded(detect.route, text, date(2026, 10, 21), seconds=4, memory_bytes=512 * MIB)
                except bounded.Overrun:
                    pass
                self.assertLess(time.monotonic() - start, 8)


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class BoundedStageTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def test_a_route_past_the_analyze_deadline_fails_the_stage_with_a_plain_message(self):
        deadlines = {'extract': 300, 'analyze': 1, 'predict': 180, 'assess': 60}
        with override_settings(JOB_DEADLINE_SECONDS=deadlines), mock.patch.object(detect, 'route', _slow_route):
            encounter_id = self.create()
            start = time.monotonic()
            drain()
        self.assertLess(time.monotonic() - start, 10)
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ANALYZE)
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertIn('took longer than 1 seconds and was stopped', job.error)
        self.assertEqual(self.provider.sent, [])

    def test_a_context_change_past_its_limit_is_refused_and_changes_nothing(self):
        encounter_id = self.create()
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        before = (dict(encounter.user_values or {}), encounter.current_context_id)

        def slow_context(text):
            time.sleep(30)
            return _EXTRACT_CONTEXT(text)

        with override_settings(CONTEXT_REQUEST_SECONDS=1), mock.patch.object(gi_context, 'extract_context',
                                                                             slow_context):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/encounters/{encounter_id}/context',
                                            data=json.dumps({'setting': 'office'}), content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('took longer than 1 seconds', response.json()['error'])
        encounter.refresh_from_db()
        self.assertEqual((dict(encounter.user_values or {}), encounter.current_context_id), before)
