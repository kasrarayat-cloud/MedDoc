"""Regressions for the refutation pass over the pipeline and API (round 1).

Each test reproduces a confirmed finding's input and asserts the corrected
behaviour. Synthetic data only; the provider is an in-process fake.
"""
import json
import threading
import time
from datetime import date, timedelta
from unittest import mock

from django.db import connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import jobs, models
from studio.types import ExtractionResult, PageSpan, RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
NO_DATE_NOTE = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
RECONCILE_NOTE = 'Checked the provider console: no response was recorded.'


class ScriptedProvider(FakeProvider):
    """FakeProvider whose next outcomes can be scripted, including an HTTP 503 failure."""

    def __init__(self, *args, outcomes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = list(outcomes)
        self.requests = []

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcome
        if outcome == 'failed':
            self.sent.append(request.canonical_sha256)
            return RawExchange(outcome='failed', sent=True, http_status=503, error='Service unavailable (synthetic).')
        saved, self.outcome = self.outcome, outcome
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.outcome = saved


class ApiHarness:
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = ScriptedProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text=OFFICE_NOTE, **extra):
        response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))

    def unknown_run_id(self, encounter_id):
        return str(models.ProviderRun.objects.get(encounter_id=encounter_id, state='unknown').pk)


@override_settings(**LIVE)
class ReconcileReleasesOneAttemptTests(ApiHarness, TestCase):
    """provider:0 and provider:1 — one reconciliation, at most one new provider attempt."""

    def test_reconcile_is_refused_while_a_predict_is_queued(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.create()
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        run_id = self.unknown_run_id(encounter_id)
        # A context change queues a predict; before the worker reaches it, a reconcile is refused
        # instead of queueing a second predict beside it.
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-22'}).status_code, 201)
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIsNone(models.ProviderRun.objects.get(pk=run_id).reconciled_at)
        drain()  # the queued predict meets the unknown outcome and sends nothing
        self.assertEqual(len(self.provider.sent), 1)
        # Reconciled once, against a provider that now fails: exactly one new send, never a retry.
        self.provider.outcomes = ['failed', 'failed', 'failed']
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual([r.state for r in self.runs(encounter_id)], ['unknown', 'failed'])
        self.assertIn('Date of service: 2026-10-22', self.provider.requests[-1].contexts)

    def test_reconcile_during_addendum_processing_is_refused_and_one_attempt_follows(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.create(NO_DATE_NOTE)
        drain()
        run_id = self.unknown_run_id(encounter_id)
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Date of service: 2026-10-20', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        # The addendum's pipeline is queued in the same transaction, so the encounter is busy.
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 409, response.content)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.provider.outcome = 'succeeded'
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        sent = self.provider.requests[-1]
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(sent.contexts[0], encounter.current_revision.text)
        self.assertIn('Date of service: 2026-10-20', sent.contexts)
        self.assertEqual(encounter.current_assessment.provider_run.request_sha256, sent.canonical_sha256)

    def test_predict_with_a_context_that_is_not_current_sends_nothing(self):
        encounter_id = self.create()
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        stale = jobs.make_context(encounter, encounter.current_revision)  # never made current
        job = jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision,
                           context=stale, key=f'predict:{stale.pk}:test')
        drain()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.SUCCEEDED)
        self.assertIn('skipped', job.result)
        self.assertEqual(len(self.provider.sent), 1)


@override_settings(**LIVE)
class ContextChangeRepredictTests(ApiHarness, TestCase):
    """provider:2 and fidelity:1 — the run in use is compared on its own request, not the previous context."""

    def test_setting_change_after_stopped_date_change_repredicts_for_the_new_date(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-22'}).status_code, 201)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        run = encounter.current_assessment.provider_run
        self.assertEqual(run.service_date, date(2026, 10, 22))
        self.assertIn('Date of service: 2026-10-22', run.contexts)
        self.assertEqual(jobs.context_service_date(encounter.current_assessment.context), date(2026, 10, 22))

    def test_setting_change_with_the_same_date_reassesses_without_sending(self):
        encounter_id = self.create()
        drain()
        first = models.Encounter.objects.get(pk=encounter_id).current_assessment
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertNotEqual(encounter.current_assessment.pk, first.pk)
        self.assertNotEqual(encounter.current_assessment.context_id, first.context_id)
        self.assertEqual(encounter.current_assessment.provider_run_id, first.provider_run_id)

    def test_assess_refuses_a_run_requested_for_another_service_date(self):
        encounter_id = self.create()
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        run = encounter.current_assessment.provider_run
        encounter.user_values = {'service_date': '2026-10-25'}
        encounter.save(update_fields=['user_values'])
        ctx = jobs.make_context(encounter, encounter.current_revision)
        encounter.current_context = ctx
        encounter.save(update_fields=['current_context'])
        job = jobs.enqueue(models.Job.ASSESS, encounter=encounter, revision=encounter.current_revision,
                           context=ctx, provider_run=run, key='assess:date-mismatch:test')
        drain()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertIn('different service date', job.error)


@override_settings(**LIVE)
class WorkerSweepTests(ApiHarness, TestCase):
    """provider:3 — an orphaned send is settled by the running worker, with no restart."""

    def test_running_worker_settles_an_orphaned_send(self):
        encounter_id = self.create()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        revision = encounter.current_revision
        orphan = {}

        def first_claim_creates_orphan():
            if not orphan:
                # What a worker killed inside send() leaves behind, already older than the cutoff.
                orphan['job'] = f_job = models.Job.objects.create(
                    encounter=encounter, revision=revision, kind=models.Job.PREDICT, state=models.Job.RUNNING,
                    idempotency_key='predict:orphan:test', deadline_at=timezone.now() + timedelta(minutes=30),
                    started_at=timezone.now() - timedelta(minutes=11))
                orphan['run'] = models.ProviderRun.objects.create(
                    encounter=encounter, revision=revision, provider='corti', adapter_version='x',
                    request_sha256='0' * 64, request_body={}, contexts=[], state=models.ProviderRun.SENDING,
                    started_at=f_job.started_at)
            return None

        ticks = iter(range(0, 10_000, 61))
        loops = iter(range(5))
        with mock.patch('studio.jobs.claim_next', side_effect=first_claim_creates_orphan):
            jobs.work(lambda: next(loops, None) is None, poll_seconds=0, clock=lambda: next(ticks))
        orphan['job'].refresh_from_db()
        orphan['run'].refresh_from_db()
        self.assertEqual(orphan['run'].state, models.ProviderRun.UNKNOWN)
        self.assertEqual(orphan['job'].state, models.Job.UNKNOWN)


@override_settings(**LIVE)
class StopRecordTests(ApiHarness, TestCase):
    """provider:6 — a Stop recorded while a stage runs survives the worker's save."""

    def test_stop_on_a_running_job_keeps_who_and_when(self):
        self.create()
        job = jobs.claim_next()
        self.assertEqual(job.state, models.Job.RUNNING)
        real = jobs.STAGES[models.Job.EXTRACT]

        def stage_with_concurrent_stop(running_job):
            jobs.stop_encounter(running_job.encounter, self.reviewer)
            return real(running_job)

        with mock.patch.dict(jobs.STAGES, {models.Job.EXTRACT: stage_with_concurrent_stop}):
            jobs.run_job(job)
        job.refresh_from_db()
        self.assertIsNotNone(job.stop_requested_at)
        self.assertEqual(job.stop_requested_by_id, self.reviewer.pk)


@override_settings(**LIVE)
class InputBoundaryTests(ApiHarness, TestCase):
    """security:2 and ingest:13 — text the database cannot store answers a JSON 400, never a 500."""

    def test_nul_in_pasted_text_is_refused_with_json(self):
        response = self.client.post('/api/encounters', {'text': 'Synthetic\x00 note.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('NUL', response.json()['error'])
        self.assertFalse(models.Encounter.objects.exists())

    def test_nul_in_title_is_removed(self):
        encounter_id = self.create(title='a\x00b')
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).title, 'a b')

    def test_lone_surrogate_or_nul_in_addendum_and_notes_is_refused(self):
        encounter_id = self.create()
        drain()
        for text in ('Addendum with a NUL \u0000 character.', 'Lone surrogate \ud800 here.'):
            response = self.post(f'/api/encounters/{encounter_id}/addenda',
                                 {'text': text, 'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 400, response.content)
        proposal = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.first()
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': str(proposal.pk), 'action': 'reject', 'note': 'bad\x00note'})
        self.assertEqual(response.status_code, 400, response.content)

    def test_login_with_nul_in_username_fails_normally_and_is_counted(self):
        anonymous = Client(enforce_csrf_checks=False)
        response = anonymous.post('/login/', {'username': 'reviewer\x00', 'password': 'synthetic-pass-123!'})
        self.assertEqual(response.status_code, 400)
        attempt = models.LoginAttempt.objects.get()
        self.assertEqual(attempt.username, 'reviewer�')
        self.assertFalse(attempt.succeeded)


@override_settings(**LIVE)
class AddendumExtractionTests(ApiHarness, TestCase):
    """ingest:1 and ingest:7 — an addendum keeps the parent's limitations and cannot exceed the limit."""

    def test_addendum_keeps_the_parents_partial_status_and_messages(self):
        encounter = f.encounter(self.ws, self.reviewer)
        parent = models.SourceRevision.objects.create(
            encounter=encounter, number=1, kind=models.SourceRevision.PASTE, pasted_text='x',
            synthetic_attested_by=self.reviewer, synthetic_attested_at=timezone.now(), created_by=self.reviewer)
        text = 'Page one text.\n\nPage two was a scanned image.'
        f.record(parent, ExtractionResult(
            status='partial', method='pdf_text', text=text, pages=(PageSpan(1, 0, 14), PageSpan(2, 16, len(text))),
            messages=('Page 2 has no usable text layer and OCR is not available on this server.',),
            ocr_pages=(2,), engine={'ingest': 'test'}))
        parent.refresh_from_db()
        child = models.SourceRevision.objects.create(
            encounter=encounter, number=2, kind=models.SourceRevision.ADDENDUM, parent=parent,
            addendum_text='Setting confirmed as office.', synthetic_attested_by=self.reviewer,
            synthetic_attested_at=timezone.now(), created_by=self.reviewer)
        encounter.current_revision = child
        encounter.save(update_fields=['current_revision'])
        job = jobs.enqueue(models.Job.EXTRACT, encounter=encounter, revision=child, key=f'extract:{child.pk}')
        jobs.stage_extract(job)
        child.refresh_from_db()
        self.assertEqual(child.extraction_status, 'partial')
        self.assertIn('Page 2 has no usable text layer and OCR is not available on this server.', child.messages)
        self.assertEqual(child.ocr_pages, [2])
        self.assertEqual(child.pages, parent.pages)
        self.assertTrue(child.text.startswith(parent.text))

    @override_settings(MAX_PASTE_CHARS=2000)
    def test_addendum_that_would_exceed_the_limit_is_refused_before_any_revision(self):
        encounter_id = self.create(OFFICE_NOTE + 'x' * (1990 - len(OFFICE_NOTE)))
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Setting confirmed as office; billing context is professional.',
                              'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('the limit is 2,000', response.json()['error'])
        self.assertEqual(models.SourceRevision.objects.filter(encounter_id=encounter_id).count(), 1)


@override_settings(**LIVE)
class ConcurrentContextTests(TransactionTestCase):
    """fidelity:3 — a second concurrent context change waits for the first and is refused, never half-applied."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.provider = ScriptedProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.reviewer)
        response = client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        self.encounter = models.Encounter.objects.get(pk=response.json()['id'])
        drain()

    def test_second_change_blocks_on_the_lock_then_is_refused(self):
        entered, release, results = threading.Event(), threading.Event(), {}
        real_make_context = jobs.make_context

        def slow_make_context(*args, **kwargs):
            if threading.current_thread().name == 'A':
                entered.set()
                release.wait(10)
            return real_make_context(*args, **kwargs)

        def change(name, values):
            try:
                results[name] = jobs.change_context(self.encounter, self.reviewer, values)
            except jobs.Refused as exc:
                results[name] = exc
            finally:
                connection.close()

        with mock.patch('studio.jobs.make_context', side_effect=slow_make_context):
            a = threading.Thread(target=change, args=('A', {'service_date': '2026-10-22'}), name='A')
            a.start()
            self.assertTrue(entered.wait(10))
            b = threading.Thread(target=change, args=('B', {'billing_context': 'facility'}), name='B')
            b.start()
            time.sleep(0.5)
            self.assertTrue(b.is_alive(), 'the second change must wait for the first one\'s lock')
            release.set()
            a.join(10)
            b.join(10)
        self.assertIsInstance(results['A'], models.EncounterContext)
        self.assertIsInstance(results['B'], jobs.Refused)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.user_values, {'service_date': '2026-10-22'})
        self.assertEqual(self.encounter.current_context.user_values, self.encounter.user_values)
