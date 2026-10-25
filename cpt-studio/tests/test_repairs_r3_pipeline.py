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

from studio import audit, jobs, models, review
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

    def test_a_predict_that_died_with_its_run_only_reserved_is_resumable(self):
        # Round 3, evidence:3: the sweep reads the finished runs BEFORE it settles reserved ones as not sent, so a
        # predict whose worker died after reserving its run is cancelled and resumable, never settled as if the
        # provider had answered 'not sent'.
        encounter_id = self.create()
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.PREDICT)
        with mock.patch('studio.jobs.is_stopped', side_effect=_WorkerDied()):  # dies right after reserving
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        run = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual(run.state, models.ProviderRun.RESERVED)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual((job.state, run.state), (models.Job.CANCELLED, models.ProviderRun.NOT_SENT))
        self.assertNotIn('settled', job.result or {})
        self.assertTrue(self.client.get(f'/api/encounters/{encounter_id}').json()['pipeline']['can_resume'])
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

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

    def test_a_falsy_non_string_clarification_id_answers_404(self):
        # Round 3, orchestrator:5: a truthiness test ran before the identifier check, so 0, false, [], {} and 0.0
        # recorded and sent the addendum with no clarification link instead of refusing it.
        encounter_id = self.create()
        drain()
        sends, revisions = len(self.provider.requests), models.SourceRevision.objects.count()
        for value in (0, False, [], {}, 0.0):
            with self.subTest(value=repr(value)):
                response = self.post(f'/api/encounters/{encounter_id}/addenda',
                                     {'text': 'Setting confirmed as office.', 'clarification_id': value,
                                      'synthetic_attestation': 'yes'})
                self.assertEqual(response.status_code, 404, response.content)
                self.assertIn('error', response.json())
        drain()
        self.assertEqual(models.SourceRevision.objects.count(), revisions)
        self.assertEqual(len(self.provider.requests), sends)

    def test_no_clarification_is_null_missing_or_empty(self):
        for extra in ({'clarification_id': None}, {}, {'clarification_id': ''}):
            with self.subTest(extra=extra):
                encounter_id = self.create()
                drain()
                response = self.post(f'/api/encounters/{encounter_id}/addenda',
                                     {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes', **extra})
                self.assertEqual(response.status_code, 201, response.content)
                revision = models.Encounter.objects.get(pk=encounter_id).current_revision
                self.assertIsNone(revision.answers_clarification)

    def test_a_string_identifier_still_works(self):
        encounter_id = self.create()
        drain()
        proposal = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.get(code='99213')
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': str(proposal.pk), 'action': 'approve',
                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
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


@override_settings(**LIVE)
class ContextChangeAfterACancelledAssessTests(ApiHarness, TestCase):
    """Round 3, orchestrator:0 — the run in use is the revision's newest finished request even when the assess that
    would have used it was cancelled (a member's Stop during the send, a swept or expired assess), so a setting or
    billing change, or a Resume after one, never re-sends an identical request that already failed."""

    def stop_during_the_send(self, encounter_id, outcome='failed'):
        """The member presses Stop while the provider request is in flight; the request then returns ``outcome``."""
        send = self.provider.send

        def stopping_send(request, *, deadline_s):
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
            self.provider.send = send
            self.provider.outcomes.insert(0, outcome)
            return send(request, deadline_s=deadline_s)

        self.provider.send = stopping_send

    def change(self, encounter_id, body, status=201):
        response = self.post(f'/api/encounters/{encounter_id}/context', body)
        self.assertEqual(response.status_code, status, response.content)
        drain()

    def assert_failed_once(self, encounter_id, sends=1):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(len(self.provider.requests), sends)
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual(encounter.current_assessment.provider_run.state, models.ProviderRun.FAILED)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)

    def test_a_setting_change_after_a_stop_during_a_failed_send(self):
        encounter_id = self.create()
        self.stop_during_the_send(encounter_id)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual((encounter.state, encounter.current_assessment), ('stopped', None))
        self.change(encounter_id, {'setting': 'office'})
        self.assert_failed_once(encounter_id)

    def test_a_billing_change_after_a_swept_assess(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create()
        for _ in range(3):  # extract, analyze, predict
            jobs.run_job(jobs.claim_next())
        assess = jobs.claim_next()  # its worker dies before it records anything
        self.assertEqual(assess.kind, models.Job.ASSESS)
        models.Job.objects.filter(pk=assess.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        self.assertEqual(models.Job.objects.get(pk=assess.pk).state, models.Job.CANCELLED)
        self.change(encounter_id, {'billing_context': 'professional'})
        self.assert_failed_once(encounter_id)

    def test_a_setting_change_after_an_expired_assess(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create()
        for _ in range(3):
            jobs.run_job(jobs.claim_next())
        models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.ASSESS,
                                  state=models.Job.QUEUED).update(deadline_at=timezone.now() - timedelta(seconds=1))
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        self.change(encounter_id, {'setting': 'office'})
        self.assert_failed_once(encounter_id)

    def test_a_billing_change_after_a_stopped_date_change_whose_send_failed(self):
        encounter_id = self.create()
        drain()  # succeeds for the document's date
        self.stop_during_the_send(encounter_id)
        self.change(encounter_id, {'service_date': '2026-10-19'})
        self.assertEqual(len(self.provider.requests), 2)
        self.change(encounter_id, {'billing_context': 'facility'})
        self.assert_failed_once(encounter_id, sends=2)

    def test_a_resume_after_a_context_change_and_a_stop(self):
        encounter_id = self.create()
        self.stop_during_the_send(encounter_id)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume', {}).status_code, 201)
        drain()
        self.assert_failed_once(encounter_id)

    def test_a_reconciled_unknown_still_gets_its_one_attempt(self):
        # The member released the unknown outcome for one new attempt; a Stop before that attempt ran, then a
        # setting change, must still make it, never re-assess with the released unknown run.
        self.provider.outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': self.unknown_run_id(encounter_id),
                              'note': 'Checked the synthetic provider console: no result exists.'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
        drain()
        self.assertEqual(len(self.provider.requests), 1)
        self.change(encounter_id, {'setting': 'office'})
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

    def test_a_changed_service_date_still_requests_new_proposals(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create()
        self.stop_during_the_send(encounter_id)
        drain()
        self.change(encounter_id, {'service_date': '2026-10-19'})
        self.assertEqual(len(self.provider.requests), 2)
