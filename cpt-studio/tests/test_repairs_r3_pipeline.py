"""Regressions for refutation round 3 over the round-2 pipeline repairs (pipeline3:1-4).

pipeline3:0 (a metadata change must not re-send) is pinned in test_repairs_pipeline_r2.MetadataChangesNeverResendTests,
beside the round-2 tests it replaced. Synthetic data only; the provider is an in-process fake.
"""
import json
from datetime import date, timedelta
from unittest import mock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import audit, jobs, models
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE, ApiHarness


class _WorkerDied(BaseException):
    """Stands in for a SIGKILL: run_job records an Exception, never a BaseException."""


def nested(depth, leaf='"x"'):
    return '[' * depth + leaf + ']' * depth


@override_settings(**LIVE)
class SweptPredictSettlesByItsOutcomeTests(ApiHarness, TestCase):
    """pipeline3:1 — a predict whose provider outcome was recorded before its worker died is settled by that
    outcome by the stale sweep, never offered as a resumable stage that re-sends an identical failed request."""

    def predict_dies_after_the_outcome(self, encounter_id):
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.PREDICT)
        real = audit.record

        def dies_after_the_outcome(workspace, event, **kwargs):
            real(workspace, event, **kwargs)
            if event == 'provider.finished':
                raise _WorkerDied()

        with mock.patch('studio.jobs.audit.record', side_effect=dies_after_the_outcome):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, models.Job.RUNNING)
        jobs.mark_stale()
        return models.Job.objects.get(pk=job.pk)

    def test_a_failed_outcome_settles_as_provider_failed_and_resume_is_refused(self):
        self.provider.outcomes = ['failed', 'failed']
        encounter_id = self.create()
        job = self.predict_dies_after_the_outcome(encounter_id)
        self.assertEqual(job.state, models.Job.SUCCEEDED)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.state, 'provider_failed')
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertFalse(detail['pipeline']['can_resume'])
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        drain()
        self.assertEqual(len(self.provider.requests), 1)

    def test_a_succeeded_outcome_goes_on_to_review_without_a_second_send(self):
        encounter_id = self.create()
        job = self.predict_dies_after_the_outcome(encounter_id)
        self.assertEqual(job.state, models.Job.SUCCEEDED)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')
        self.assertEqual(len(self.provider.requests), 1)

    def test_a_predict_that_died_before_sending_is_still_resumable(self):
        encounter_id = self.create()
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze
        job = jobs.claim_next()  # the predict is claimed and its worker dies before any run exists
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, models.Job.CANCELLED)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')
        self.assertEqual(len(self.provider.requests), 1)


@override_settings(**LIVE)
class NonStringIdentifiersTests(ApiHarness, TestCase):
    """pipeline3:2 — a nested list in an identifier field answers the endpoint's JSON 404, never an HTML 500
    (the ORM lookup recursed once per level)."""

    def body(self, **fields):
        return '{' + ', '.join(f'"{name}": {value}' for name, value in fields.items()) + '}'

    def test_nested_identifiers_answer_json_404(self):
        encounter_id = self.create()
        drain()
        decisions_before = models.Decision.objects.count()
        revisions_before = models.SourceRevision.objects.count()
        cases = {
            'decisions': self.body(proposal_id=nested(1500), action='"approve"', acknowledgement='"ok"'),
            'addenda': self.body(clarification_id=nested(1500), text='"Setting confirmed as office."',
                                 synthetic_attestation='"yes"'),
            'reconcile': self.body(provider_run_id=nested(1500), note='"Checked the synthetic console twice."'),
        }
        for path, raw in cases.items():
            for depth_raw in (raw, raw.replace(nested(1500), nested(3000)), raw.replace(nested(1500), '17')):
                with self.subTest(path=path, size=len(depth_raw)):
                    response = self.client.post(f'/api/encounters/{encounter_id}/{path}', data=depth_raw,
                                                content_type='application/json')
                    self.assertEqual(response.status_code, 404, response.content[:200])
                    self.assertIn('error', response.json())
        self.assertEqual(models.Decision.objects.count(), decisions_before)
        self.assertEqual(models.SourceRevision.objects.count(), revisions_before)

    def test_the_api_backstop_answers_json_for_a_recursion_anywhere(self):
        from django.test import RequestFactory
        from studio import api

        def recursing_view(request):
            raise RecursionError('maximum recursion depth exceeded')

        request = RequestFactory().post('/api/encounters/x/decisions')
        request.user = self.reviewer
        response = api.api_view(recursing_view)(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['error'], 'The request is nested too deeply.')

    def test_a_string_identifier_still_works(self):
        encounter_id = self.create()
        drain()
        proposal = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.get(code='99213')
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': str(proposal.pk), 'action': 'approve', 'acknowledgement': 'ok'})
        self.assertEqual(response.status_code, 201, response.content)


@override_settings(**LIVE)
class NonTextFieldsTests(ApiHarness, TestCase):
    """pipeline3:4 — a note, acknowledgement or addendum sent as anything but a JSON string answers 400 and is
    never stored (or sent to the provider) as its Python repr."""

    VALUES = [['ok'], {'text': 'ok'}, True, 7, 1.5, [nested(5)]]

    def test_decision_note_and_acknowledgement(self):
        encounter_id = self.create()
        drain()
        proposal = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.get(code='99213')
        for field in ('note', 'acknowledgement'):
            for value in self.VALUES:
                with self.subTest(field=field, value=repr(value)[:30]):
                    data = {'proposal_id': str(proposal.pk), 'action': 'approve', 'acknowledgement': 'ok', field: value}
                    response = self.post(f'/api/encounters/{encounter_id}/decisions', data)
                    self.assertEqual(response.status_code, 400, response.content)
                    self.assertIn('must be text', response.json()['error'])
        self.assertFalse(models.Decision.objects.filter(proposal=proposal).exists())

    def test_addendum_text(self):
        encounter_id = self.create()
        drain()
        sends = len(self.provider.requests)
        for value in self.VALUES + [None, '']:
            with self.subTest(value=repr(value)[:30]):
                response = self.post(f'/api/encounters/{encounter_id}/addenda',
                                     {'text': value, 'synthetic_attestation': 'yes'})
                self.assertEqual(response.status_code, 400, response.content)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).revisions.count(), 1)
        self.assertEqual(len(self.provider.requests), sends)

    def test_a_nul_inside_a_list_is_refused_as_not_text(self):
        encounter_id = self.create()
        drain()
        response = self.client.post(f'/api/encounters/{encounter_id}/addenda',
                                    data=json.dumps({'text': ['a\u0000b'], 'synthetic_attestation': 'yes'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_ordinary_text_still_works(self):
        encounter_id = self.create()
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        revision = models.Encounter.objects.get(pk=encounter_id).current_revision
        self.assertEqual(revision.addendum_text, 'Setting confirmed as office.')


@override_settings(**LIVE)
class MigrationBackfillRoundTripTests(ApiHarness, TransactionTestCase):
    """Round 3, evidence:3 — migration 0003 itself backfills ProviderRun.service_date on a database at 0002 (the
    round-2 test called the helper directly, so dropping the RunPython step from 0003 left it green)."""

    PRE = ('studio', '0002_integration_fields')
    LEAF = ('studio', '0003_decision_sequence_run_service_date')

    def stored_date(self, pk):
        with connection.cursor() as cursor:
            cursor.execute('SELECT service_date FROM studio_providerrun WHERE id = %s', [pk])
            return cursor.fetchone()[0]

    def test_upgrading_from_0002_backfills_the_date_the_request_carried(self):
        encounter_id = self.create()
        drain()
        run = models.Encounter.objects.get(pk=encounter_id).current_assessment.provider_run
        self.assertEqual(run.contexts[1:], ['Date of service: 2026-10-20'])
        try:
            MigrationExecutor(connection).migrate([self.PRE])  # the column is dropped with 0003's reversal
            MigrationExecutor(connection).migrate([self.LEAF])
        finally:
            MigrationExecutor(connection).migrate([self.LEAF])
        self.assertEqual(self.stored_date(run.pk), date(2026, 10, 20))


@override_settings(**LIVE)
class SystemCancelledStagesAreNotMemberStopsTests(ApiHarness, TestCase):
    """pipeline3:3 — the detail tells a member's Stop apart from a stage the system cancelled, and keeps the cause."""

    def test_an_expired_stage_is_not_a_member_stop(self):
        encounter_id = self.create()
        models.Job.objects.filter(encounter_id=encounter_id).update(deadline_at=timezone.now() - timedelta(seconds=1))
        drain()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertEqual(detail['state'], 'stopped')
        self.assertIs(detail['pipeline']['stopped_by_member'], False)
        cancelled = [stage for stage in detail['pipeline']['stages'] if stage['state'] == 'cancelled']
        self.assertTrue(cancelled and cancelled[-1]['error'], detail['pipeline'])

    def test_a_member_stop_is_one(self):
        encounter_id = self.create()
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertEqual(detail['state'], 'stopped')
        self.assertIs(detail['pipeline']['stopped_by_member'], True)
