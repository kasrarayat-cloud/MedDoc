"""Refutation r1, cluster M (upgrade and restore paths). Synthetic data only; no network.

migrate-4: a member-entered service date that conflicts with the document's is held (session interpretation 19), but the
  hold was decided only inside this revision's predict stage. Every member action queued a plain predict for the
  conflicted context, so the installed revision's worker - restored after a failed replacement, or reinstalled -
  read the stored conflict as "no date" and sent a paid request without one, at once or on a later Resume. The hold is
  now recorded where it is decided: no path queues a job that can send for such a context.
"""
import json
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings

from studio import jobs, models, review
from studio.gi import context as gi_context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DOCUMENTED = date(2026, 10, 20)  # OFFICE_NOTE's own date
TWO_DATES = OFFICE_NOTE.replace('Date of service: 2026-10-20\n',
                                'Date of service: 2026-10-20\nDate of service: 2026-10-23\n')
UNDATED = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
REPORT = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy report (fictional) M1
Date of service: 2026-10-16
Place of service: Hospital outpatient department
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
"""
VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
SNARE = ('45385', 'was removed with a cold snare')


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


def member_conflict(context):
    return gi_context.is_member_conflict((context.facts or {}).get('service_date'))


@override_settings(**LIVE)
class MemberDateConflictIsHeldWhereDecidedTests(TestCase):
    """migrate-4: whichever path would start the request for a context whose service date is a member conflict records
    the not-sent held run itself and queues only the assess that reads it - never a predict that a worker reading the
    conflict under other rules would send."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[VISIT, SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- helpers ---------------------------------------------------------------------------------------------------

    def upload(self, text=OFFICE_NOTE, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def finished(self, text=OFFICE_NOTE, **extra):
        encounter_id = self.upload(text, **extra)
        drain()
        return encounter_id

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def set_date(self, encounter_id, value):
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': value})
        self.assertEqual(response.status_code, 201, response.content)

    def run_one(self):
        job = jobs.claim_next()
        self.assertIsNotNone(job)
        jobs.run_job(job)
        return job

    def assert_held_at_queue(self, encounter_id):
        """Nothing that can send is queued for the conflicted context: one assess whose run is the recorded hold."""
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(member_conflict(encounter.current_context))
        queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
        self.assertEqual([job.kind for job in queued], [models.Job.ASSESS])
        self.assertEqual(queued[0].context_id, encounter.current_context_id)
        held = queued[0].provider_run
        self.assertIsNotNone(held)
        self.assertEqual((held.state, held.sent, held.service_date, held.request_sha256, held.contexts),
                         (models.ProviderRun.NOT_SENT, False, None, '', []))
        self.assertEqual(held.scope, {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT})
        self.assertEqual(held.error, jobs.MEMBER_DATE_CONFLICT_MESSAGE)
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        return held

    def assert_no_predict_for_a_member_conflict(self, encounter_id):
        """No predict for a member-conflicted context is queued, or left as the stage a Resume would run again."""
        predicts = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.PREDICT,
                                             state__in=(models.Job.QUEUED, models.Job.RUNNING)).select_related('context')
        self.assertEqual([job.idempotency_key for job in predicts if job.context and member_conflict(job.context)], [])
        latest = review.latest_job(models.Encounter.objects.get(pk=encounter_id))
        self.assertFalse(latest.kind == models.Job.PREDICT and latest.state == models.Job.CANCELLED
                         and member_conflict(latest.context), latest.idempotency_key)

    def assert_settled_on_the_date_question(self, encounter_id, held):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.state, 'needs_clarification')
        self.assertEqual(encounter.current_assessment.provider_run_id, held.pk)
        self.assertIn('Nothing was sent: the service date entered as encounter metadata conflicts with the document',
                      review.readiness(encounter)['blockers'])
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertTrue([q for q in detail['clarifications'] if q['fact'] == 'service_date'])

    # --- the member's own change, the finding's input and its paraphrases ------------------------------------------

    def test_a_conflicting_member_date_queues_only_the_assess_of_a_recorded_hold(self):
        for text, value in ((OFFICE_NOTE, '1998-01-01'), (OFFICE_NOTE, '2026-10-22'), (REPORT, '1998-01-01')):
            with self.subTest(document=text.splitlines()[2][:40], value=value):
                encounter_id = self.finished(text)
                sent = len(self.provider.sent)
                self.set_date(encounter_id, value)
                held = self.assert_held_at_queue(encounter_id)
                self.assertEqual(held.requested_by_id, self.reviewer.pk)
                drain()
                self.assertEqual(len(self.provider.sent), sent)
                self.assert_settled_on_the_date_question(encounter_id, held)

    def test_controls_a_member_date_beside_dates_the_document_disputes_rechecks_the_run_in_use(self):
        # a third side to the document's own conflict: the request in use was already made without a date, so the
        # change re-checks that run - and no predict is queued for the member conflict either way
        encounter_id = self.finished(TWO_DATES)
        sent = len(self.provider.sent)
        self.set_date(encounter_id, '2026-10-22')
        self.assertTrue(member_conflict(models.Encounter.objects.get(pk=encounter_id).current_context))
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), sent)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def test_a_member_date_conflict_entered_at_upload_is_held_by_the_analysis(self):
        encounter_id = self.upload(OFFICE_NOTE, service_date='1998-01-01')
        self.assertEqual(self.run_one().kind, models.Job.EXTRACT)
        self.assertEqual(self.run_one().kind, models.Job.ANALYZE)
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- a Stop, a Resume and a reconciliation on the conflicted context ---------------------------------------------

    def test_a_stopped_hold_resumes_as_the_same_hold(self):
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        held = self.assert_held_at_queue(encounter_id)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.assertEqual(self.assert_held_at_queue(encounter_id).pk, held.pk)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def stopped_with_latest(self, encounter_id, kind, context):
        """Leave ``kind`` for ``context`` as the encounter's latest stage, cancelled by a member's Stop."""
        encounter = models.Encounter.objects.get(pk=encounter_id)
        jobs.enqueue(kind, encounter=encounter, revision=encounter.current_revision, context=context,
                     key=f'{kind}:{context.pk}:left-cancelled', requested_by=self.reviewer)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(review.latest_job(encounter).kind, kind)
        self.assertTrue(review.can_resume(encounter))

    def test_resuming_a_cancelled_predict_on_a_conflicted_context_records_the_hold(self):
        # a predict an earlier state of this code queued for the conflicted context, then stopped
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        context = models.Encounter.objects.get(pk=encounter_id).current_context
        self.stopped_with_latest(encounter_id, models.Job.PREDICT, context)
        holds = models.ProviderRun.objects.filter(encounter_id=encounter_id, state=models.ProviderRun.NOT_SENT).count()
        response = self.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'resumed': models.Job.ASSESS})
        held = self.assert_held_at_queue(encounter_id)
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           state=models.ProviderRun.NOT_SENT).count(), holds + 1)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def test_resuming_an_assess_whose_context_changed_while_stopped_records_the_hold(self):
        # the cancelled assess was for the documented context; the current one is a member conflict, so a Resume
        # starts again from the request - which is held, not queued
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        documented = encounter.current_context
        self.stopped_with_latest(encounter_id, models.Job.ASSESS, documented)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.save(update_fields=['user_values', 'updated_at'])
        conflicted = jobs.make_context(encounter, encounter.current_revision)
        models.Encounter.objects.filter(pk=encounter_id).update(current_context=conflicted)
        self.assertTrue(member_conflict(conflicted))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def test_reconciling_an_unknown_outcome_under_a_conflict_records_the_hold(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.finished()
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN)
        self.provider.outcome = 'succeeded'
        self.set_date(encounter_id, '1998-01-01')
        first = self.assert_held_at_queue(encounter_id)
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(unknown.pk), 'note': 'Checked with the provider: nothing billed.'})
        self.assertEqual(response.status_code, 201, response.content)
        held = self.assert_held_at_queue(encounter_id)
        self.assertNotEqual(held.pk, first.pk)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- the upgrade remake of an earlier context -----------------------------------------------------------------

    def test_an_earlier_context_remade_into_a_member_conflict_is_held_at_the_remake(self):
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        facts = dict(encounter.current_context.facts)
        facts['service_date'] = {'name': 'service_date', 'value': '1998-01-01', 'origin': 'user', 'evidence': [],
                                 'note': gi_context.USER_NOTE}
        earlier = models.EncounterContext.objects.create(
            encounter=encounter, revision=encounter.current_revision, facts=facts,
            user_values={'service_date': '1998-01-01'}, version='gi-context@1', sha256='0' * 64)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.current_context = earlier
        encounter.save(update_fields=['user_values', 'current_context', 'updated_at'])
        jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision, context=earlier,
                     key=f'predict:{earlier.pk}', requested_by=self.reviewer)  # as the installed revision queued it
        remake = self.run_one()
        self.assertIn('remade', remake.result.get('skipped', ''))
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- what keeps reading as it did -------------------------------------------------------------------------------

    def test_controls_every_other_date_still_queues_its_predict(self):
        cases = (
            # a document whose own dates conflict: the request goes without a date, as before, on both revisions
            ('internal conflict', TWO_DATES, {}, None, 1),
            # an undated document: the member's date supplies the date and is sent
            ('member date for an undated note', UNDATED, {'service_date': '2026-10-22'}, '2026-10-22', 1),
            # the member's date agrees with the document's
            ('agreeing member date', OFFICE_NOTE, {'service_date': '2026-10-20'}, '2026-10-20', 1),
        )
        for label, text, extra, sent_date, sends in cases:
            with self.subTest(label):
                encounter_id = self.upload(text, **extra)
                self.run_one()
                self.run_one()
                queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
                self.assertEqual([job.kind for job in queued], [models.Job.PREDICT])
                before = len(self.provider.sent)
                drain()
                self.assertEqual(len(self.provider.sent) - before, sends)
                run = models.ProviderRun.objects.filter(encounter_id=encounter_id).latest('created_at')
                self.assertEqual(run.service_date, date.fromisoformat(sent_date) if sent_date else None)
                self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                                   scope__held__isnull=False).exists())

    def test_controls_clearing_the_conflict_queues_the_predict_for_the_documented_date(self):
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        self.set_date(encounter_id, '')
        queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
        self.assertEqual([job.kind for job in queued], [models.Job.PREDICT])
        drain()
        self.assertEqual(len(self.provider.sent), 1)  # the documented request's retained result is reused
        latest = models.ProviderRun.objects.filter(encounter_id=encounter_id).latest('created_at')
        self.assertEqual((latest.state, latest.sent, latest.service_date),
                         (models.ProviderRun.SUCCEEDED, False, DOCUMENTED))

    def test_a_setting_change_beside_the_conflict_is_held_at_the_change(self):
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def test_without_a_provider_the_conflict_queues_the_assess_and_records_nothing(self):
        encounter_id = self.finished()
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).count()
        with mock.patch('studio.jobs.get_provider', return_value=None):
            self.set_date(encounter_id, '1998-01-01')
            queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
            self.assertEqual([(job.kind, job.provider_run_id) for job in queued], [(models.Job.ASSESS, None)])
            drain()
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs)
        self.assert_no_predict_for_a_member_conflict(encounter_id)

    def test_controls_a_context_that_is_no_longer_current_is_never_held(self):
        # a predict for a superseded context records nothing: every revision's predict stage skips it
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.save(update_fields=['user_values', 'updated_at'])
        superseded = jobs.make_context(encounter, encounter.current_revision)
        self.assertTrue(member_conflict(superseded))
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).count()
        job = jobs._queue_predict(encounter, encounter.current_revision, superseded, key='predict:superseded',
                                  requested_by=self.reviewer)
        self.assertEqual(job.kind, models.Job.PREDICT)
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs)
        drain()
        job.refresh_from_db()
        self.assertEqual(job.result, {'skipped': 'the context is not the current one for this revision; nothing was '
                                                 'sent'})
        self.assertEqual(len(self.provider.sent), 1)
