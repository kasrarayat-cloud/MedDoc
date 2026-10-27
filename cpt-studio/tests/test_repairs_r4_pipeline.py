"""Regressions for refutation round 4 over the pipeline and API (pipeline:2, pipeline:6).

Synthetic data only; the provider is an in-process fake and nothing leaves the process.
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.providers.base import ProviderUnavailable
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import FIRST_DATE, LIVE, NO_DATE_NOTE, ApiHarness

# A note that documents no place of service: a member's setting supplies it, and a later one changes it. A member's
# setting beside a documented one is a conflict instead (session interpretation 11).
NO_SETTING_NOTE = OFFICE_NOTE.replace('Place of service: Office, in-person outpatient visit\n', '')


class _WorkerDied(BaseException):
    """Stands in for a SIGKILL: run_job records an Exception, never a BaseException."""


@override_settings(**LIVE)
class SweptReservedRunIsNoOutcomeTests(ApiHarness, TestCase):
    """Round 4, pipeline:2 — a predict whose worker died with its run only reserved is settled by the stale sweep as
    not sent, and stays resumable (round 3, evidence:3). That run never reached the send, so it is no provider
    outcome: a setting or billing change makes the one attempt it never made, exactly as a Resume does, instead of
    re-assessing with it as a failed request (cc78bc4c4)."""

    def die_after_reserving(self, how='is_stopped'):
        """Claim the queued predict and kill its worker once its run is reserved; age it and run the sweep."""
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.PREDICT)
        if how == 'is_stopped':  # the claimant's kill: right after the reservation, at the Stop check
            killer = mock.patch('studio.jobs.is_stopped', side_effect=_WorkerDied())
        else:  # the verifier's kill: inside the save that moves the run from reserved to sending
            real_save = models.ProviderRun.save

            def killing_save(run, *args, **kwargs):
                if run.state == models.ProviderRun.SENDING:
                    raise _WorkerDied()
                return real_save(run, *args, **kwargs)
            killer = mock.patch.object(models.ProviderRun, 'save', killing_save)
        with killer:
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        run = models.ProviderRun.objects.order_by('-created_at').first()
        self.assertEqual(run.state, models.ProviderRun.RESERVED)
        # The job is past the stale cutoff. The cutoff is moved rather than the job's start, so the runs an earlier
        # stage recorded keep their real order before this job's start, as they would on a real worker.
        with override_settings(STALE_RUNNING_SECONDS=0):
            jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.started_at, run.sent), (models.ProviderRun.NOT_SENT, None, False))
        self.assertTrue(run.request_sha256)
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, models.Job.CANCELLED)
        return run

    def swept(self, how='is_stopped', text=OFFICE_NOTE):
        encounter_id = self.create(text)
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze
        sends = len(self.provider.requests)
        self.die_after_reserving(how)
        self.assertEqual(len(self.provider.requests), sends)  # nothing was sent
        self.assertTrue(self.client.get(f'/api/encounters/{encounter_id}').json()['pipeline']['can_resume'])
        return encounter_id

    def change(self, encounter_id, body):
        response = self.post(f'/api/encounters/{encounter_id}/context', body)
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def assert_attempt_made(self, encounter_id, sends=1):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(len(self.provider.requests), sends)
        self.assertEqual(encounter.state, 'ready_for_review')
        self.assertEqual(encounter.current_assessment.provider_run.state, models.ProviderRun.SUCCEEDED)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
        self.assertNotIn('The provider request failed', review.readiness(encounter)['blockers'])

    def test_a_setting_change_after_the_sweep_makes_the_attempt(self):
        encounter_id = self.swept()
        self.change(encounter_id, {'setting': 'office'})
        self.assert_attempt_made(encounter_id)

    def test_a_billing_change_after_the_sweep_makes_the_attempt(self):
        encounter_id = self.swept()
        self.change(encounter_id, {'billing_context': 'professional'})
        self.assert_attempt_made(encounter_id)

    def test_the_interfaces_whole_body_after_the_sweep(self):
        encounter_id = self.swept()
        self.change(encounter_id, {'service_date': '', 'setting': 'office', 'billing_context': ''})
        self.assert_attempt_made(encounter_id)

    def test_killed_inside_the_save_that_would_start_the_send(self):
        encounter_id = self.swept(how='save')
        self.change(encounter_id, {'setting': 'office'})
        self.assert_attempt_made(encounter_id)

    def test_a_second_setting_change_then_re_checks_without_sending(self):
        encounter_id = self.swept(text=NO_SETTING_NOTE)
        self.change(encounter_id, {'setting': 'office'})
        self.change(encounter_id, {'setting': 'asc'})
        self.assert_attempt_made(encounter_id, sends=1)

    def test_after_a_failed_request_for_another_date(self):
        # The run in use falls back past the swept run to the failed request for the first date; the request for the
        # new date differs from it, so the attempt for the new date is made, once. The note documents no date of its
        # own, so the member's dates apply (a documented date would make a different member date a conflict).
        self.provider.outcomes = ['failed']
        encounter_id = self.create(NO_DATE_NOTE, service_date=FIRST_DATE)
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'provider_failed')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-19'}).status_code, 201)
        self.die_after_reserving()
        self.change(encounter_id, {'setting': 'office'})
        self.assert_attempt_made(encounter_id, sends=2)
        self.assertIn('Date of service: 2026-10-19', self.provider.requests[-1].contexts)

    def test_the_attempt_a_reconciliation_released_is_still_made(self):
        self.provider.outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': self.unknown_run_id(encounter_id),
                              'note': 'Checked the synthetic provider console: no result exists.'})
        self.assertEqual(response.status_code, 201, response.content)
        self.die_after_reserving()  # the released attempt's worker dies before it sends
        self.assertEqual(len(self.provider.requests), 1)
        self.change(encounter_id, {'setting': 'office'})
        self.assert_attempt_made(encounter_id, sends=2)

    def test_control_a_resume_after_the_sweep(self):
        encounter_id = self.swept()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume', {}).status_code, 201)
        drain()
        self.assert_attempt_made(encounter_id)

    def test_control_a_provider_answer_of_not_sent_still_stands(self):
        # The exchange went through the send (started_at is set): its outcome stands, and a setting change re-checks
        # with it rather than sending the identical request again (round 3, orchestrator:0).
        self.provider.outcomes = ['not_sent']
        encounter_id = self.create()
        drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual(run.state, models.ProviderRun.NOT_SENT)
        self.assertIsNotNone(run.started_at)
        self.change(encounter_id, {'setting': 'office'})
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual(encounter.current_assessment.provider_run_id, run.pk)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)

    def test_control_a_provider_that_could_not_build_the_request_is_asked_again(self):
        # A run recorded when no request could be built carries no request hash; as before, a setting change
        # re-predicts, and the provider, available again, is sent the request once.
        build = self.provider.build_request
        calls = []

        def unavailable_once(text, service_date):
            calls.append(service_date)
            if len(calls) == 1:
                raise ProviderUnavailable('No credentials are configured (synthetic).')
            return build(text, service_date)
        self.provider.build_request = unavailable_once
        encounter_id = self.create()
        drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual((run.state, run.request_sha256, run.started_at), (models.ProviderRun.NOT_SENT, '', None))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'provider_failed')
        self.change(encounter_id, {'setting': 'office'})
        self.assert_attempt_made(encounter_id)


@override_settings(**LIVE)
class RunInUseTests(ApiHarness, TestCase):
    """Round 4, pipeline:2 — exactly the runs the sweep settled from reserved stop standing; every other finished
    run stands as before (cc78bc4c4), whatever it is newer than, except a not-sent run that carries no request
    (refutation p1, sends-0, round 7c8: it answers no request)."""

    def setUp(self):
        super().setUp()
        self.provider.outcomes = ['failed']
        encounter_id = self.create()
        drain()
        self.encounter = models.Encounter.objects.get(pk=encounter_id)
        self.revision = self.encounter.current_revision
        self.failed = models.ProviderRun.objects.get(encounter=self.encounter)
        self.assertEqual(self.failed.state, models.ProviderRun.FAILED)

    def make_run(self, **fields):
        base = dict(encounter=self.encounter, revision=self.revision, provider=self.failed.provider,
                    adapter_version=self.failed.adapter_version, request_sha256=self.failed.request_sha256,
                    request_body=self.failed.request_body, contexts=self.failed.contexts,
                    state=models.ProviderRun.NOT_SENT)
        return models.ProviderRun.objects.create(**{**base, **fields})

    def test_a_reserved_run_the_sweep_settled_does_not_stand(self):
        self.make_run(error='The worker stopped before sending.', finished_at=timezone.now())
        self.assertEqual(jobs._run_in_use(self.revision), self.failed)

    def test_a_provider_answer_of_not_sent_stands(self):
        answered = self.make_run(started_at=timezone.now(), finished_at=timezone.now(), error='Authentication failed.')
        self.assertEqual(jobs._run_in_use(self.revision), answered)

    def test_a_run_recorded_without_a_request_is_no_outcome(self):
        # Round 7c8 (refutation p1, sends-0) updated this pin, which pinned the defect: the run stood, and having no
        # request to compare it let a later metadata save re-send the byte-identical request that FAILED before it.
        self.make_run(request_sha256='', request_body={}, contexts=[], error='No credentials are configured.',
                      finished_at=timezone.now())
        self.assertEqual(jobs._run_in_use(self.revision), self.failed)

    def test_other_finished_states_without_a_start_still_stand(self):
        for state in (models.ProviderRun.FAILED, models.ProviderRun.SUCCEEDED, models.ProviderRun.UNKNOWN):
            with self.subTest(state=state):
                run = self.make_run(state=state, finished_at=timezone.now())
                self.assertEqual(jobs._run_in_use(self.revision), run)


@override_settings(**LIVE)
class ContextValuesAreStringsTests(ApiHarness, TestCase):
    """Round 4, pipeline:6 — POST /context takes, per field, a listed string, or null or '' to clear it (API.md). Any
    other JSON type answers 400 and changes nothing, never a silent clear (the round-3 orchestrator:5 class, on
    another endpoint). A service date is a string in YYYY-MM-DD form only: never a JSON number, a basic or week date
    that date.fromisoformat also accepts; on the upload too."""

    NON_STRINGS = (False, 0, [], {}, 0.0, True, 1, ['office'], {'a': 1}, 1.5)

    def setUp(self):
        super().setUp()
        self.encounter_id = self.create(NO_DATE_NOTE)
        drain()
        self.assertEqual(self.change({'setting': 'office', 'billing_context': 'facility'}).status_code, 201)

    def change(self, body):
        response = self.post(f'/api/encounters/{self.encounter_id}/context', body)
        drain()
        return response

    def snapshot(self):
        encounter = models.Encounter.objects.get(pk=self.encounter_id)
        return (dict(encounter.user_values), encounter.contexts.count(), len(self.provider.requests))

    def assert_refused(self, body):
        before = self.snapshot()
        response = self.change(body)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('error', response.json())
        self.assertEqual(self.snapshot(), before)

    def test_a_non_string_setting_or_billing_context_answers_400(self):
        for field in ('setting', 'billing_context'):
            for value in self.NON_STRINGS:
                with self.subTest(field=field, value=repr(value)):
                    self.assert_refused({field: value})
        self.assertEqual(models.Encounter.objects.get(pk=self.encounter_id).user_values,
                         {'setting': 'office', 'billing_context': 'facility'})

    def test_an_unlisted_string_still_answers_400(self):
        for field, value in (('setting', 'bogus'), ('setting', ' office'), ('billing_context', 'Facility')):
            with self.subTest(field=field, value=value):
                self.assert_refused({field: value})

    def test_null_and_the_empty_string_clear(self):
        for field, value in (('setting', None), ('billing_context', '')):
            with self.subTest(field=field, value=value):
                response = self.change({field: value})
                self.assertEqual(response.status_code, 201, response.content)
                self.assertNotIn(field, models.Encounter.objects.get(pk=self.encounter_id).user_values)

    def test_a_listed_string_is_stored(self):
        response = self.change({'setting': 'asc', 'billing_context': 'professional'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(models.Encounter.objects.get(pk=self.encounter_id).user_values,
                         {'setting': 'asc', 'billing_context': 'professional'})

    def test_a_service_date_that_is_not_a_yyyy_mm_dd_string_answers_400(self):
        for value in (20261020, 20261020.0, '20261020', '2026-W43-2', '2026W432', '2026-W43', '2026-293',
                      '10/20/2026', ' 2026-10-20', '2026-10-20\n', '2026-10-20T00:00', '２０２６-１'
                      '０-２０', '2026-02-30', True, False, 0, [], {}, ['2026-10-20']):
            with self.subTest(value=repr(value)):
                self.assert_refused({'service_date': value})
        self.assertNotIn('service_date', models.Encounter.objects.get(pk=self.encounter_id).user_values)

    def test_a_yyyy_mm_dd_service_date_is_sent_and_null_clears_it(self):
        response = self.change({'service_date': '2026-10-20'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn('Date of service: 2026-10-20', self.provider.requests[-1].contexts)
        response = self.change({'service_date': None})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn('service_date', models.Encounter.objects.get(pk=self.encounter_id).user_values)

    def test_the_upload_takes_only_a_yyyy_mm_dd_service_date(self):
        encounters = models.Encounter.objects.count()
        for value in ('2026-W43-2', '20261020', '2026-W43', '2026-02-30'):
            with self.subTest(value=value):
                response = self.client.post('/api/encounters', {'text': NO_DATE_NOTE, 'synthetic_attestation': 'yes',
                                                                'service_date': value})
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(models.Encounter.objects.count(), encounters)
        for value in ('2026-10-20', ''):
            with self.subTest(value=value):
                self.create(NO_DATE_NOTE, service_date=value)
