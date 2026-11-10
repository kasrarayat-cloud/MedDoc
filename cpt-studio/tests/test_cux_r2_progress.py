"""Refutation round 2 of the core repair (2026-11-04), lens L5: the derived state and the progress panel say what the
backend did, and never invite a second paid request for one whose outcome is unknown.

- L5-1: an outcome still unknown - a run recorded unknown and not reconciled, or one left 'sending' by a stage that no
  longer runs (decision (k)) - outranks every failure after it: the document reads being_confirmed, with no "Upload it
  again", until it is reconciled. Only the member's own Stop reads first.
- L5-2, L5-6: the worker beats until it is really done - while it finishes its stage after a SIGTERM, and in --once.
- L5-3: a reservation its stage left behind never reached the provider: it is settled not sent (by the send and by the
  stale sweep) and is never read as being confirmed.
- L5-4: a stage an unknown outcome blocked, or one that skipped its work, is never done.
- L5-5: a re-check of what is still open that did not complete says so, and Document review never reads done for it.
- L5-7: the next step of a run that has begun waits its turn; it never reads "Waiting to start" beside done steps.

DB-backed; synthetic data only; nothing is sent (the in-process fakes of the pipeline and harness suites).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import signal
import time
import uuid
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import jobs, models, progress, review
from studio.types import ExtractionResult, RawExchange
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.support.operator import OperatorReads
from tests.test_cux_flow import ProgressCase, run_stages
from tests.test_harness_pipeline import BOTH, HarnessCase
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, RecordedInterpretation, drain
from tests.test_repairs_gi2_present import BIOPSY, SNARE, Harness
from tests.test_repairs_pipeline import INTERPRETATIONS, NO_DATE_NOTE
from tests.test_services_second_review import TwoPassProvider

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
NOTE = 'Checked the vendor console (synthetic): the answer was received and billed once.'
TIME_QUOTE = 'Total time on the date of the encounter was 24 minutes.'


def overrun_assess():
    """The assess child overruns its real bound (the stage fails with the plain message, as jobs._bounded fails it)."""
    real = jobs._bounded

    def bounded(fn, *args, seconds, refusal=None, memory_bytes=None):
        if fn is jobs._assess_child:
            raise jobs.StageFailure(jobs.OVERRUN_MESSAGES['time'].format(seconds=seconds))
        return real(fn, *args, seconds=seconds, refusal=refusal, memory_bytes=memory_bytes)
    return mock.patch('studio.jobs._bounded', side_effect=bounded)


class CustomerReads:
    def customer(self, encounter_id):
        reply = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def assertBeingConfirmed(self, encounter_id):
        """provider_unknown, read and stored; the member reads being_confirmed with no error and no action."""
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(review._unreconciled_unknown(encounter))
        self.assertEqual((encounter.state, review._derive_state(encounter)), ('provider_unknown', 'provider_unknown'))
        doc = self.customer(encounter_id)
        block = doc['progress']
        self.assertEqual((doc['state'], block['phase'], block['error'], block['message'], block['can_resume']),
                         ('being_confirmed', 'being_confirmed', None, progress.MESSAGES['being_confirmed'], False))
        return doc


# --- L5-1: an unknown outcome outranks every failure after it ---------------------------------------------------------

class StatePrecedenceTests(TestCase):
    """The derived state over rows (review._state_and_run): each failure reads as itself with no unknown outcome, and
    as provider_unknown while one is unreconciled; reconciled, the failure reads again. The member's Stop reads
    first."""

    def setUp(self):
        self.s = pf.scenario()
        self.enc = self.s.encounter

    def state(self):
        return review.refresh_state(models.Encounter.objects.get(pk=self.enc.pk))

    def unknown(self, revision=None):
        return pf.provider_run(self.enc, revision or self.s.revision, state=models.ProviderRun.UNKNOWN)

    def settle(self, run):
        models.ProviderRun.objects.filter(pk=run.pk).update(reconciled_at=timezone.now())

    def test_a_failed_stage_after_an_unknown_outcome_waits_on_its_reconciliation(self):
        pf.assess(self.enc, pf.result())
        for kind, failed in (('analyze', 'processing_failed'), ('assess', 'processing_failed'),
                             ('astra', 'processing_failed'), ('astra_peer', 'processing_failed'),
                             ('predict', 'provider_failed')):
            with self.subTest(kind):
                models.Job.objects.filter(encounter=self.enc).delete()
                job = pf.job(self.enc, self.s.revision, kind, 'failed')
                if kind == 'predict':  # its own request, sent and failed
                    pf.provider_run(self.enc, self.s.revision, state=models.ProviderRun.FAILED)
                self.assertEqual(self.state(), failed)  # the control: no unknown outcome
                run = self.unknown()  # an earlier request's outcome, never the failed stage's own request
                models.ProviderRun.objects.filter(pk=run.pk).update(created_at=job.created_at - timedelta(seconds=5))
                self.assertEqual(self.state(), 'provider_unknown')
                self.settle(run)
                self.assertEqual(self.state(), failed)

    def test_the_failures_that_say_upload_again_are_the_ones_an_unknown_outcome_outranks(self):
        """One rule, two readers: the derived failures whose customer error offers a new upload (progress.ERRORS) are
        exactly review.RESUBMIT_STATES, so a failure that starts offering one is outranked by an unknown outcome too."""
        offered = {state for state, (_, action) in progress.ERRORS.items()
                   if action == 'new_document' and state in progress.FAILED_STATES}
        self.assertEqual(offered, set(review.RESUBMIT_STATES))

    def test_a_run_left_sending_by_a_failed_stage_is_the_same_unknown_outcome(self):
        pf.assess(self.enc, pf.result())
        pf.job(self.enc, self.s.revision, 'assess', 'failed')
        orphan = pf.provider_run(self.enc, self.s.revision, state=models.ProviderRun.SENDING)
        self.assertTrue(review._orphaned_sending(self.enc))
        self.assertEqual(self.state(), 'provider_unknown')
        models.ProviderRun.objects.filter(pk=orphan.pk).update(state=models.ProviderRun.FAILED)
        self.assertEqual(self.state(), 'processing_failed')

    def test_a_reading_that_failed_after_an_unknown_outcome_waits_on_it_too(self):
        run = self.unknown()
        added = f.pasted_revision(self.enc, self.s.reviewer, pf.GI_NOTE + '\nAddendum.', extract=False)
        f.record(added, ExtractionResult(status='failed', method='paste', text=''))
        self.assertEqual(self.state(), 'provider_unknown')
        self.settle(run)
        self.assertEqual(self.state(), 'extraction_failed')
        run = pf.provider_run(self.enc, self.s.revision, state=models.ProviderRun.UNKNOWN)
        pending = f.pasted_revision(self.enc, self.s.reviewer, pf.GI_NOTE + '\nAnother.', extract=False)
        pf.job(self.enc, pending, 'extract', 'failed')
        self.assertEqual(self.state(), 'provider_unknown')
        self.settle(run)
        self.assertEqual(self.state(), 'extraction_failed')

    def test_control_no_request_made_offers_nothing_and_reads_as_before(self):
        """provider_not_run says no request was made and offers no action, so it invites no second request: an unknown
        outcome elsewhere leaves it as it was (tests.test_review pins the assessment made with none)."""
        pf.assess(self.enc, pf.result(), no_provider=True)
        self.unknown()
        self.assertEqual(self.state(), 'provider_not_run')
        job = pf.job(self.enc, self.s.revision, 'predict', 'failed')  # it failed before it recorded a request
        models.ProviderRun.objects.filter(encounter=self.enc).update(created_at=job.created_at - timedelta(seconds=5))
        self.assertEqual(self.state(), 'provider_not_run')
        self.assertEqual(progress.ERRORS['provider_not_run'][1], 'none')

    def test_control_the_member_s_own_stop_still_reads_stopped_and_resumable(self):
        pf.assess(self.enc, pf.result())
        self.unknown()
        pf.job(self.enc, self.s.revision, 'assess', 'cancelled')
        self.assertEqual(self.state(), 'stopped')
        self.assertTrue(review.can_resume(models.Encounter.objects.get(pk=self.enc.pk)))


@applied
@override_settings(**BOTH)
class ParticipantUnknownTests(CustomerReads, OperatorReads, HarnessCase):
    """L5-1's inputs (a) and (b), through the real pipeline: a participant left 'sending' after both its outcome writes
    failed (decision (k)'s backstop), and a participant's unknown outcome followed by an assess that overran."""

    def test_a_participant_left_sending_after_its_writes_failed_is_being_confirmed_until_reconciled(self):
        real = jobs._finish_run

        def finish(run, exchange):
            if run.provider == 'astra':
                raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)
        with mock.patch('studio.jobs._finish_run', side_effect=finish), self.assertLogs('studio.jobs', 'ERROR'):
            encounter_id = self.create()
            drain()
        (astra,) = self.runs_of(encounter_id, 'astra')
        self.assertEqual(astra.state, models.ProviderRun.SENDING)
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind='astra').state, models.Job.FAILED)
        self.assertTrue(review._orphaned_sending(self.encounter(encounter_id)))
        doc = self.assertBeingConfirmed(encounter_id)
        steps = {step['key']: step['state'] for step in doc['progress']['steps']}
        self.assertEqual(steps['checking'], 'failed')  # the stage's own truth, never animated
        # the sweep settles the orphan unknown; it still waits on its reconciliation
        models.ProviderRun.objects.filter(pk=astra.pk).update(created_at=timezone.now() - timedelta(hours=1))
        jobs.mark_stale()
        astra.refresh_from_db()
        self.assertEqual((astra.state, astra.sent, astra.reconciled_at),
                         (models.ProviderRun.UNKNOWN, True, None))
        self.assertBeingConfirmed(encounter_id)
        self.assertEqual(len(self.adapters['astra'].sent), 1)
        # its reconciliation releases one new attempt, and the document then reads what that chain did
        reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile', {'provider_run_id': str(astra.pk),
                                                                          'note': NOTE})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(len(self.adapters['astra'].sent), 2)
        self.assertNotIn(self.encounter(encounter_id).state, ('provider_unknown', 'processing_failed'))

    def test_an_unknown_outcome_then_an_assess_that_overran_is_being_confirmed_never_upload_again(self):
        self.adapters['astra'].outcome = 'unknown'
        with overrun_assess():
            encounter_id = self.create()
            drain()
        self.assertEqual([(job.kind, job.state) for job in self.jobs_of(encounter_id)][-1], ('assess', 'failed'))
        (astra,) = self.runs_of(encounter_id, 'astra')
        self.assertEqual((astra.state, astra.sent), (models.ProviderRun.UNKNOWN, True))
        self.assertBeingConfirmed(encounter_id)
        # reconciled, the failure after it is the document's state again - and only then does the page say so
        self.adapters['astra'].outcome = 'succeeded'
        with overrun_assess():
            reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile', {'provider_run_id': str(astra.pk),
                                                                              'note': NOTE})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        encounter = self.encounter(encounter_id)
        self.assertFalse(review._unreconciled_unknown(encounter))
        self.assertEqual(encounter.state, 'processing_failed')
        error = self.customer(encounter_id)['progress']['error']
        self.assertEqual(error, {'text': progress.ERRORS['processing_failed'][0], 'action': 'new_document'})


@applied
@override_settings(**LIVE)
class CortiUnknownTests(CustomerReads, OperatorReads, TestCase):
    """L5-1's input (c): Corti's read times out after sending, then the assess overruns its bound."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', TIME_QUOTE)], outcome='unknown')
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_an_unknown_document_review_then_an_assess_that_overran_is_being_confirmed(self):
        with overrun_assess():
            with self.captureOnCommitCallbacks(execute=True):
                reply = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        encounter_id = reply.json()['id']
        self.assertEqual(models.Job.objects.filter(encounter_id=encounter_id).order_by('-created_at').first().state,
                         models.Job.FAILED)
        self.assertBeingConfirmed(encounter_id)
        self.assertEqual(len(self.provider.sent), 1)


# --- L5-2, L5-6: the worker beats until it is really done -------------------------------------------------------------

SILENT, INTERVAL = 1.5, 0.2  # the two bounds, compressed (jobs.WORKER_SILENT_SECONDS 120 s, HEARTBEAT_SECONDS 30 s)


class HeartbeatLifetimeTests(TransactionTestCase):
    """The real run_worker command (its signal handler, jobs.beat, start_heartbeat, work, claim_next, run_job) over one
    queued stage whose body is a stand-in that outlasts the silent bound; the panel is read from the rows while it runs.
    TransactionTestCase: the heartbeat thread writes on its own connection, as in the worker."""

    def setUp(self):
        self.s = pf.scenario()
        self.job = models.Job.objects.create(
            encounter=self.s.encounter, revision=self.s.revision, kind=models.Job.ASTRA, state=models.Job.QUEUED,
            idempotency_key=f'astra:r2-heartbeat:{uuid.uuid4()}', context=self.s.context,
            deadline_at=timezone.now() + jobs.QUEUE_DEADLINE)
        self.samples, self.threads = {}, []
        handlers = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGINT, handlers[0])
        self.addCleanup(signal.signal, signal.SIGTERM, handlers[1])

    def sample(self, label):
        encounter = models.Encounter.objects.get(pk=self.s.encounter.pk)
        out = progress.encounter_progress(encounter)
        beat = models.WorkerBeat.objects.get(name=jobs.WORKER_NAME)
        self.samples[label] = {'phase': out['phase'], 'job': models.Job.objects.get(pk=self.job.pk).state,
                               'age': (timezone.now() - beat.beat_at).total_seconds(), 'pid': beat.pid,
                               'beating': any(thread.is_alive() for thread in self.threads)}

    def run_worker(self, stage, **options):
        real_start = jobs.start_heartbeat

        def start(should_stop, **kwargs):
            thread = real_start(should_stop, interval=INTERVAL)
            self.threads.append(thread)
            return thread
        with mock.patch.dict(jobs.STAGES, {models.Job.ASTRA: stage}), \
                mock.patch.object(jobs, 'WORKER_SILENT_SECONDS', SILENT), \
                mock.patch.object(jobs, 'remove_stale_ingest_dirs', lambda: None), \
                mock.patch.object(jobs, '_queue_after_participant', lambda job: None), \
                mock.patch('studio.jobs.start_heartbeat', side_effect=start):
            call_command('run_worker', stdout=io.StringIO(), **options)

    def test_a_worker_finishing_its_stage_after_sigterm_keeps_beating_until_its_loop_returns(self):
        def stage(job):
            self.sample('before')
            handler = signal.getsignal(signal.SIGTERM)
            handler(signal.SIGTERM, None)  # what `docker stop` delivers: the handler sets the drain flag
            time.sleep(SILENT * 2.5)  # the stage goes on well past the silent bound
            self.sample('after')
            return {'participant': job.kind, 'state': 'succeeded'}
        self.run_worker(stage, poll_seconds=0.05)
        self.assertEqual(self.samples['before']['phase'], 'processing')
        after = self.samples['after']
        self.assertEqual((after['job'], after['phase'], after['beating'], after['pid']),
                         (models.Job.RUNNING, 'processing', True, os.getpid()))
        self.assertLess(after['age'], SILENT)
        self.assertEqual(models.Job.objects.get(pk=self.job.pk).state, models.Job.SUCCEEDED)
        # done working, the process stops beating (a worker that is gone reads paused once its last beat ages)
        self.assertEqual(len(self.threads), 1)
        self.assertFalse(self.threads[0].is_alive())

    def test_a_once_worker_beats_while_it_drains_the_queue(self):
        models.WorkerBeat.objects.create(name=jobs.WORKER_NAME, beat_at=timezone.now() - timedelta(minutes=10),
                                         revision='earlier', pid=1)  # the stopped long-running worker's last beat

        def stage(job):
            time.sleep(SILENT * 2.5)
            self.sample('during')
            return {'participant': job.kind, 'state': 'succeeded'}
        self.run_worker(stage, once=True)
        during = self.samples['during']
        self.assertEqual((during['job'], during['phase'], during['beating'], during['pid']),
                         (models.Job.RUNNING, 'processing', True, os.getpid()))
        self.assertLess(during['age'], SILENT)
        self.assertEqual(models.Job.objects.get(pk=self.job.pk).state, models.Job.SUCCEEDED)
        self.assertEqual(len(self.threads), 1)
        self.assertFalse(self.threads[0].is_alive())


# --- L5-3: a reservation its stage left behind is never being confirmed -----------------------------------------------

@applied
@override_settings(**LIVE)
class ReservationTests(CustomerReads, OperatorReads, TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', TIME_QUOTE)])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def failing_read_after_reservation(self):
        """The read of the Stop right after the reservation raises once (the lens's input)."""
        real, calls = jobs._stop_requested, []

        def stop_requested(job, encounter):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError('synthetic: one read failed right after the reservation')
            return real(job, encounter)
        return mock.patch('studio.jobs._stop_requested', side_effect=stop_requested)

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def assertNotBeingConfirmed(self, encounter_id):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertFalse(review._unreconciled_unknown(encounter))
        self.assertEqual((encounter.state, review._derive_state(encounter)), ('provider_failed', 'provider_failed'))
        doc = self.customer(encounter_id)
        self.assertEqual((doc['state'], doc['progress']['phase']), ('failed', 'failed'))
        self.assertNotEqual(doc['progress']['message'], progress.MESSAGES['being_confirmed'])

    def test_a_reservation_whose_stage_failed_before_sending_is_settled_not_sent(self):
        with self.failing_read_after_reservation(), self.assertLogs('studio.jobs', 'ERROR'):
            encounter_id = self.create()
            drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual((run.state, run.sent, run.started_at, run.error),
                         (models.ProviderRun.NOT_SENT, False, None, jobs.UNSENT_RESERVATION_MESSAGE))
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind='predict').state, models.Job.FAILED)
        self.assertNotBeingConfirmed(encounter_id)
        self.assertIsNone(jobs._run_in_use(models.Encounter.objects.get(pk=encounter_id).current_revision))
        # the attempt it reserved is still owed: the member's next request sends it, once
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)

    def test_the_sweep_settles_a_reservation_its_own_settling_left_behind(self):
        with self.failing_read_after_reservation(), mock.patch('studio.jobs._settle_reservation'), \
                self.assertLogs('studio.jobs', 'ERROR'):
            encounter_id = self.create()
            drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual(run.state, models.ProviderRun.RESERVED)
        self.assertNotBeingConfirmed(encounter_id)  # never sent, so never an outcome to confirm
        jobs.mark_stale()  # younger than the cutoff: it is left as it is
        run.refresh_from_db()
        self.assertEqual(run.state, models.ProviderRun.RESERVED)
        with override_settings(STALE_RUNNING_SECONDS=0):
            jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.started_at, run.error),
                         (models.ProviderRun.NOT_SENT, False, None, jobs.ORPHANED_RESERVATION_MESSAGE))
        self.assertIsNone(jobs.reconcile(models.Encounter.objects.get(pk=encounter_id), run, self.reviewer, NOTE))
        self.assertNotBeingConfirmed(encounter_id)
        self.assertEqual(self.provider.sent, [])

    def test_control_the_reservation_of_a_stage_running_now_is_its_request_in_flight(self):
        encounter_id = self.create()
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        job = models.Job.objects.filter(encounter=encounter).order_by('-created_at').first()
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.RUNNING, started_at=timezone.now())
        mine = models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider='corti', adapter_version='test',
            request_sha256='f' * 64, request_body={}, contexts=[], state=models.ProviderRun.RESERVED,
            requested_by=self.reviewer)
        jobs.mark_stale()  # the stage is not stale, and its reservation is younger than the cutoff
        mine.refresh_from_db()
        self.assertEqual(mine.state, models.ProviderRun.RESERVED)
        self.assertEqual(review._derive_state(encounter), 'processing')


class StaleReservationTests(TestCase):
    def test_a_stale_stage_whose_reservation_was_settled_unsent_still_owes_its_attempt(self):
        """The double fault: its reservation was settled unsent (jobs._settle_reservation) and the stage's own failure
        was never recorded (still 'running' when the sweep finds it). That run is no outcome of the stage: the sweep
        cancels the stage for a Resume, as when it settles the reservation itself, and queues no assessment of a request
        that was never sent."""
        s = pf.scenario()
        job = pf.job(s.encounter, s.revision, 'predict', 'running', context=s.context)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(hours=1))
        models.ProviderRun.objects.create(
            encounter=s.encounter, revision=s.revision, provider='corti', adapter_version='test',
            request_sha256='a' * 64, request_body={}, contexts=[], state=models.ProviderRun.NOT_SENT, sent=False,
            error=jobs.UNSENT_RESERVATION_MESSAGE, requested_by=s.reviewer, finished_at=timezone.now())
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)
        self.assertFalse(models.Job.objects.filter(encounter=s.encounter, kind='assess').exists())
        self.assertTrue(review.can_resume(models.Encounter.objects.get(pk=s.encounter.pk)))


# --- L5-4: a blocked or skipped stage is never done -------------------------------------------------------------------

@override_settings(**LIVE)
class BlockedStageTests(RecordedInterpretation, CustomerReads, TestCase):
    """L5-4's input: a document whose first request's outcome is unknown, then a member's date - a new request, which
    the unknown outcome blocks (nothing is sent, nothing assessed)."""
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads OFFICE_NOTE or NO_DATE_NOTE from its
    # recorded synthetic interpretation.
    interpretations = INTERPRETATIONS

    def test_a_document_review_an_unknown_outcome_blocked_is_never_done(self):
        ws = f.workspace()
        reviewer = f.member(ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(reviewer)
        provider = FakeProvider(selections=[('99213', TIME_QUOTE)], outcome='unknown')
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            with self.captureOnCommitCallbacks(execute=True):
                reply = self.client.post('/api/encounters', {'text': NO_DATE_NOTE, 'synthetic_attestation': 'yes'})
            self.assertEqual(reply.status_code, 201, reply.content)
            encounter_id = reply.json()['id']
            drain()
            before = self.customer(encounter_id)
            with self.captureOnCommitCallbacks(execute=True):
                saved = self.client.post(f'/api/encounters/{encounter_id}/context',
                                         data=json.dumps({'service_date': '2026-10-20'}),
                                         content_type='application/json')
            self.assertEqual(saved.status_code, 201, saved.content)
            drain()
            after = self.customer(encounter_id)
        predicts = list(models.Job.objects.filter(encounter_id=encounter_id, kind='predict').order_by('created_at'))
        self.assertIn('blocked', predicts[-1].result)
        self.assertEqual(len(provider.sent), 1)
        self.assertEqual(after['progress']['phase'], 'being_confirmed')
        # each check says what it said before the save: the blocked request asked nothing and validated nothing
        self.assertEqual([check['state'] for check in after['checks']], [check['state'] for check in before['checks']])
        self.assertEqual(after['checks'][0]['state'], 'unavailable')
        steps = {step['key']: step['state'] for step in after['progress']['steps']}
        self.assertEqual(steps['checking'], 'stopped')


class StageRecordTests(ProgressCase):
    """What a finished stage recorded, over rows: blocked, skipped and a re-check's own outcome."""

    def checks(self):
        self.enc.refresh_from_db()
        return {check['key']: check['state'] for check in progress.checks_summary(self.enc)}

    def test_a_blocked_document_review_is_unavailable_and_its_step_stopped(self):
        pf.provider_run(self.enc, self.rev, state=models.ProviderRun.UNKNOWN)  # the outcome that blocks every send
        self.chain('extract', 'analyze')
        blocked = self.job('predict', 'succeeded', 4, result={'blocked': 'a previous request has an unknown outcome'})
        self.assertEqual(progress._jobs_outcome([blocked]), 'unavailable')
        self.assertEqual(progress._fold([blocked]), 'stopped')
        self.assertEqual(self.checks()['document_review'], 'unavailable')
        out = self.progress()
        self.assertEqual((out['phase'], self.states(out)), ('being_confirmed', ['done', 'done', 'stopped',
                                                                                'not_started']))
        # the control: a participant the same door blocked reads unavailable, as before
        held = self.job('astra', 'succeeded', 6, result={'participant': 'astra', 'state': 'blocked'})
        self.assertEqual(progress._jobs_outcome([held]), 'unavailable')

    def test_a_skipped_stage_is_never_done_and_what_came_before_stands(self):
        self.chain('extract', 'analyze', 'predict', 'assess')
        self.final()
        skipped = self.job('review2', 'succeeded', 600, result={'skipped': 'nothing to ask about; nothing was sent'})
        self.assertEqual(progress._jobs_outcome([skipped]), 'not_run')
        self.assertTrue(progress._skip(skipped))
        self.assertEqual(progress._fold([skipped]), 'skipped')
        # the earlier run's checking stands
        self.assertEqual(self.states(self.progress())[:3], ['done', 'done', 'done'])
        # with no final assessment of the current context, a skip leaves the earlier run's reading
        models.Encounter.objects.filter(pk=self.enc.pk).update(current_assessment=None)
        self.assertEqual(self.checks()['document_review'], 'done')
        models.Job.objects.filter(kind='predict').update(result={'provider': 'failed'})
        self.assertEqual(self.checks()['document_review'], 'unavailable')
        # an extract that found its text already recorded did read it
        extract = self.job('extract', 'succeeded', 700, result={'skipped': 'already extracted'})
        self.assertFalse(progress._skip(extract))
        self.assertEqual(progress._fold([extract]), 'done')

    def test_an_assess_reads_coding_validation_from_the_assessment_it_made(self):
        self.chain('extract', 'analyze', 'predict')
        assessment = self.final()
        made = self.job('assess', 'succeeded', 6, result={'assessment': str(assessment.pk)})
        self.assertEqual(progress._jobs_outcome([made]), progress._validation_outcome(assessment))
        gone = self.job('assess', 'succeeded', 8, result={'assessment': 'not-a-uuid'})
        self.assertEqual(progress._jobs_outcome([gone]), 'unavailable')

    def test_a_re_check_s_own_outcome_is_read(self):
        self.chain('extract', 'analyze', 'predict', 'assess')
        self.final()
        for outcome, expected in (('failed', 'unavailable'), ('unknown', 'unavailable'), ('not_sent', 'unavailable'),
                                  ('succeeded', 'done'), ('reused', 'done')):
            with self.subTest(outcome):
                models.Job.objects.filter(kind__in=('review2', 'assess'), created_at__gt=self.t0 + timedelta(
                    seconds=100)).delete()
                self.job('review2', 'succeeded', 600, result={'second_review': outcome, 'run': None})
                self.job('assess', 'queued', 602)
                self.assertEqual(self.checks()['document_review'], expected)
        # the stale sweep records a re-check it settles under 'provider'
        swept = self.job('review2', 'succeeded', 700, result={'provider': 'failed', 'run': None, 'settled': 'x'})
        self.assertEqual(progress._jobs_outcome([swept]), 'unavailable')


# --- L5-5: a re-check that did not complete says so -------------------------------------------------------------------

class FailingRecheck(TwoPassProvider):
    """The re-check (the second request) is answered HTTP 503 after it was sent, as the live adapter returns any
    non-200 answer."""

    def send(self, request, *, deadline_s):
        if self.requests:
            self.requests.append(request)
            data = b'{"error": "synthetic overload"}'
            return RawExchange(outcome='failed', sent=True, http_status=503, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(),
                               error='The coding service answered HTTP 503 (synthetic).')
        return super().send(request, deadline_s=deadline_s)


@applied
class RecheckOutcomeTests(CustomerReads, Harness):
    def ask(self, provider):
        self.use(provider)
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        before = self.customer(encounter_id)
        self.assertEqual(before['recheck'], {'available': True, 'can_request': True})
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        return encounter_id, before

    def test_a_re_check_that_failed_is_never_done_and_the_result_says_it_could_not_be_completed(self):
        encounter_id, before = self.ask(FailingRecheck(first=[SNARE], later=[BIOPSY]))
        run_stages(1)  # the re-check: sent, answered 503
        (second,) = models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review')
        self.assertEqual((second.state, second.sent, second.http_status), (models.ProviderRun.FAILED, True, 503))
        waiting = self.customer(encounter_id)
        self.assertTrue(waiting['progress']['busy'])  # its assess waits
        self.assertEqual(waiting['checks'][0]['state'], 'unavailable')
        drain()
        doc = self.customer(encounter_id)
        self.assertEqual(doc['checks'][0]['state'], 'unavailable')
        self.assertEqual((doc['progress']['phase'], doc['progress']['message'], doc['progress']['error']),
                         ('partial', progress.RECHECK_INCOMPLETE, None))
        self.assertNotEqual(before['progress']['message'], progress.RECHECK_INCOMPLETE)
        self.assertEqual(doc['recheck'], {'available': False, 'can_request': False})  # 5.11: once, whatever its outcome
        self.assertEqual(len(self.provider.requests), 2)
        assessment = self.encounter(encounter_id).current_assessment
        self.assertEqual(progress.recheck_incomplete(assessment), second)

    def test_control_a_re_check_that_was_answered_reads_done(self):
        encounter_id, _ = self.ask(TwoPassProvider(first=[SNARE], later=[BIOPSY, SNARE]))
        drain()
        doc = self.customer(encounter_id)
        self.assertEqual(doc['checks'][0]['state'], 'done')
        self.assertNotEqual(doc['progress']['message'], progress.RECHECK_INCOMPLETE)
        self.assertIsNone(progress.recheck_incomplete(self.encounter(encounter_id).current_assessment))

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)


# --- L5-7: the next step of a run that has begun waits its turn -------------------------------------------------------

class NextStepTests(ProgressCase):
    def test_a_run_that_has_begun_says_its_next_step_waits_its_turn(self):
        made = self.chain('extract', 'analyze', 'predict', last='queued')
        out = self.progress(now=made[-1].created_at + timedelta(seconds=20))
        self.assertEqual((out['phase'], out['message']), ('queued', progress.NEXT_STEP_QUEUED))
        self.assertEqual(self.states(out), ['done', 'done', 'waiting', 'not_started'])
        self.assertNotIn('Waiting to start', out['message'])

    def test_control_a_run_not_begun_waits_to_start_and_a_retry_or_a_long_wait_says_its_own_words(self):
        first = self.job('extract', 'queued', 0)
        self.assertEqual(self.progress(now=first.created_at + timedelta(seconds=5))['message'],
                         progress.MESSAGES['queued'])
        models.Job.objects.filter(pk=first.pk).delete()
        made = self.chain('extract', 'analyze', 'predict', last='queued')
        models.Job.objects.filter(pk=made[-1].pk).update(result={'requeued': 'the provider lock is busy'})
        self.assertEqual(self.progress(now=made[-1].created_at + timedelta(seconds=5))['message'],
                         progress.TAKING_TURN)
        late = made[-1].created_at + timedelta(seconds=0.7 * jobs.QUEUE_DEADLINE.total_seconds())
        self.assertEqual((self.progress(now=late)['slow'], self.progress(now=late)['message']),
                         (True, progress.QUEUE_SLOW))

    def test_the_new_sentences_promise_nothing_and_name_nothing_internal(self):
        from tests.test_cux_flow import UNSAID
        promised = ('automatic', 'will start', 'will stop', 'limit', 'deadline', 'time out', 'expire', 'minutes')
        for message in (progress.NEXT_STEP_QUEUED, progress.RECHECK_INCOMPLETE):
            self.assertIsNone(UNSAID.search(message), message)
            self.assertFalse([word for word in promised if word in message.lower()], message)
