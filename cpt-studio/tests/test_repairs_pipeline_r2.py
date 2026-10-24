"""Regressions for refutation round 2 over the pipeline repairs (pipeline:0-5).

Each test reproduces a confirmed round-2 input. Synthetic data only; the provider is an in-process fake.
"""
import importlib
from datetime import date, timedelta

from django.apps import apps as django_apps
from django.test import TestCase, override_settings
from django.utils import timezone

from studio import jobs, models
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE, ApiHarness


@override_settings(**LIVE)
class ResumeOnlyTheLatestCancelledStageTests(ApiHarness, TestCase):
    """pipeline:0 — a stale Resume never re-runs an older stage."""

    def test_a_second_resume_after_the_resumed_send_failed_is_refused(self):
        encounter_id = self.create()
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze: the predict is now queued
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        self.provider.outcomes = ['failed']
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        stale = self.client.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(stale.status_code, 409, stale.content)
        drain()
        self.assertEqual(len(self.provider.sent), 1)

    def test_stop_resume_stop_resume_still_works(self):
        encounter_id = self.create()
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
            drain()
            self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

    def test_resume_after_a_completed_review_is_refused(self):
        encounter_id = self.create()
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        stale = self.client.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).current_assessment_id, assessment.pk)


@override_settings(**LIVE)
class OnlyAnAnswerAnswersTests(ApiHarness, TestCase):
    """pipeline:1 — a run that holds no answer (not sent, failed) is never reused by a context change."""

    def test_a_setting_change_after_a_not_sent_run_sends(self):
        self.provider.outcomes = ['not_sent']
        encounter_id = self.create()
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        run = models.Encounter.objects.get(pk=encounter_id).current_assessment.provider_run
        self.assertEqual(run.state, models.ProviderRun.SUCCEEDED)

    def test_a_setting_change_after_a_failed_run_is_a_new_attempt(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        run = models.Encounter.objects.get(pk=encounter_id).current_assessment.provider_run
        self.assertEqual(run.state, models.ProviderRun.SUCCEEDED)


@override_settings(**LIVE)
class LegacyRunServiceDateTests(ApiHarness, TestCase):
    """pipeline:2 — a run recorded before ProviderRun.service_date existed keeps the date its request carried."""

    def legacy_run(self, encounter_id):
        run = models.Encounter.objects.get(pk=encounter_id).current_assessment.provider_run
        models.ProviderRun.objects.filter(pk=run.pk).update(service_date=None)
        run.refresh_from_db()
        return run

    def test_the_migration_backfills_the_date_from_the_request(self):
        encounter_id = self.create()
        drain()
        run = self.legacy_run(encounter_id)
        migration = importlib.import_module('studio.migrations.0003_decision_sequence_run_service_date')
        migration.backfill_service_date(django_apps, None)
        run.refresh_from_db()
        self.assertEqual(run.service_date, date(2026, 10, 20))

    def test_a_legacy_run_without_the_column_is_not_a_date_mismatch(self):
        encounter_id = self.create()
        drain()
        run = self.legacy_run(encounter_id)
        self.assertEqual(jobs.run_service_date(run), date(2026, 10, 20))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        # A NEW assessment of the new context reused the legacy run: no false "different service date" failure
        # (the old assessment also used this run, so checking the run alone would pass either way).
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
        self.assertEqual(encounter.current_assessment.provider_run_id, run.pk)
        self.assertEqual(encounter.state, 'ready_for_review')
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.FAILED).exists())
        self.assertEqual(len(self.provider.sent), 1)


@override_settings(**LIVE)
class SettledStagesStayResumableTests(ApiHarness, TestCase):
    """pipeline:3 — a stage the sweep settles, or that expires in the queue, can be resumed; it never strands
    the encounter as an extraction failure."""

    def test_an_extract_cut_short_by_a_dead_worker_is_resumable(self):
        encounter_id = self.create()
        job = jobs.claim_next()  # the extract is now 'running' and its worker "dies"
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.state, 'stopped')
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

    def test_a_stage_that_expired_in_the_queue_is_resumable(self):
        encounter_id = self.create()
        models.Job.objects.filter(encounter_id=encounter_id).update(deadline_at=timezone.now() - timedelta(seconds=1))
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

    def test_an_extract_resumed_after_its_text_was_recorded_goes_on_to_analysis(self):
        encounter_id = self.create()
        job = jobs.claim_next()
        jobs.STAGES[models.Job.EXTRACT](job)  # the text is recorded, then the worker dies before saving the job
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.ANALYZE).delete()
        jobs.mark_stale()
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')


@override_settings(**LIVE)
class RoutingSummaryTests(ApiHarness, TestCase):
    """pipeline:4 — the detail's routing is the routing the current assessment used."""

    def test_routing_follows_the_assessment_across_date_changes(self):
        from tests.test_repairs_pipeline import HISTORY_NOTE, HISTORY_QUOTE
        self.provider.selections = [('45385', HISTORY_QUOTE)]
        encounter_id = self.create(HISTORY_NOTE)
        drain()
        for value in ('2026-10-21', '', '2026-10-21'):
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'service_date': value}).status_code,
                             201)
            drain()
            detail = self.client.get(f'/api/encounters/{encounter_id}').json()
            used = models.Encounter.objects.get(pk=encounter_id).current_assessment.routing.result
            # Mention statuses tell the dated and undated routings apart (the 2021 mention reads historical
            # only against a service date); family statuses alone do not.
            shown = {f['family']: [m['status'] for m in f['mentions']] for f in detail['routing']['families']}
            self.assertEqual(shown, {f['family']: [m['status'] for m in f['mentions']] for f in used['findings']},
                             value)


@override_settings(**LIVE)
class DeepJsonTests(ApiHarness, TestCase):
    """pipeline:5 — nesting deeper than the parser allows answers a JSON 400, never an HTML 500."""

    def test_deeply_nested_json_is_a_400(self):
        encounter_id = self.create()
        drain()
        body = b'[' * 10000 + b']' * 10000
        for path in ('decisions', 'addenda', 'context', 'reconcile', 'reports'):
            with self.subTest(path=path):
                response = self.client.post(f'/api/encounters/{encounter_id}/{path}', data=body,
                                            content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error'], 'The request body is not valid JSON.')
