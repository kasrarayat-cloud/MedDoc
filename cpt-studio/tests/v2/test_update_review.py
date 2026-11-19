"""FINAL-V2 amendment 1 (docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208): the codes are updated
automatically after a save - what step 5b's review.py, progress.py and provider_holds.py read while an update is pending,
and the save's own triggers in jobs.change_context. TEXT-ONLY and SYNTHETIC: the fixtures and doubles of
tests/v2/test_update_pipeline.py (design v2's scripted interpreter, the in-process Corti, the legacy chain's fixture);
the worker is driven by jobs.claim_next and jobs.run_job explicitly; nothing is sent anywhere.

11.1's tests whose subject is in step 5b's files, by id (the API's halves are step 5d's): U1 the triggers, as
jobs.change_context answers them (ContextSave); U10 the refusals review.py makes while an update is pending; A17 an
update's assessment that is not final is recorded and never current; U16 truthful progress; U18 member acts and saves
(A18); U19 the case-B details' phase; U20's classification - a provider hold is set and released only from a run's
recorded http_status and sent (A16, A20); and the literals review.py and progress.py hold equal to customer_api's.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ValidationError
from django.utils import timezone

from studio import customer_api, jobs, models, progress, provider_holds, review, types
from studio.interpretation import holds
from tests.support import factories as f
from tests.support import operator as ops
from tests.v2.test_jobs import BARE_429, EXTRACTION, HTTP_500, answered
from tests.v2.test_update_pipeline import D1, D2, HOSPITAL, OFFICE, UpdateCase

Run, Job = models.ProviderRun, models.Job
PROVIDER_WORDS = ('Gemini', 'gemini', 'Corti', 'corti', 'Astra', 'astra', 'Fable', 'fable', 'Google', 'model')
# a finished document's phases: these fixtures are read with no CMS reference loaded, so their coding validation reads
# unavailable and a finished result is 'partial' (progress._partial) - before an update as after it
FINISHED = ('completed', 'partial')


def counts(encounter):
    """The rows a save may add, and the saved values: equal before and after a save that changes nothing."""
    return (models.EncounterContext.objects.filter(encounter=encounter).count(),
            Job.objects.filter(encounter=encounter).count(),
            models.AuditEvent.objects.filter(encounter=encounter).count(),
            Run.objects.filter(encounter=encounter).count(),
            dict(models.Encounter.objects.get(pk=encounter.pk).user_values or {}))


class LiteralTests(UpdateCase):
    """The sentences review.py and progress.py carry are customer_api's (which imports them, so they are held equal
    here rather than read from it at import)."""

    def test_the_update_refusals_and_the_appraise_detail_are_customer_apis(self):
        self.assertEqual(review.UPDATE_DECISION, customer_api.UPDATE_DECISION)
        self.assertEqual(review.UPDATE_DECISION_CHECK, customer_api.UPDATE_DECISION_CHECK)
        self.assertEqual(review.UPDATE_BLOCKER, customer_api.UPDATE_BLOCKER)
        self.assertEqual(progress.APPRAISE_DETAIL, customer_api.APPRAISE_DETAIL)
        self.assertEqual(review.CONTEXT_FACT_NAMES, tuple(types.CONTEXT_FACTS))
        for name in ('RETRY_UPDATE_NOTHING', 'RETRY_UPDATE_HELD', 'RETRY_UPDATE_READING', 'RETRY_UPDATE_REFUSED_BEFORE',
                     'SAVE_TOO_LONG', 'SAVE_UNPREPARED', 'RESTORE_REFUSED', 'PROVIDER_PAUSED'):
            self.assertEqual(jobs._customer_text(name), getattr(customer_api, name))


class TriggerTests(UpdateCase):
    """U1, the save's half (1.2, 1.3): what jobs.change_context answers and writes."""

    def test_u1_an_identical_save_and_a_save_clearing_an_absent_value_write_nothing(self):
        for fixture in (self.v2_fixture, self.legacy_fixture):
            with self.subTest(fixture=fixture.__name__):
                self.new_workspace()
                encounter = fixture()
                self.save(encounter, setting=OFFICE)
                self.drain()
                before = counts(encounter)
                for values in ({'setting': OFFICE}, {'setting': ' office '}, {'patient_status': ''},
                               {'setting': OFFICE, 'billing_context': ''}):
                    saved = self.save(encounter, **values)
                    self.assertTrue(saved.unchanged, values)
                    self.assertEqual((saved.changed, saved.updating, saved.restored), ((), False, False))
                    self.assertEqual(counts(encounter), before, values)

    def test_u1_each_real_change_adds_exactly_one_context_changed_row(self):
        encounter = self.v2_fixture()
        rows = models.AuditEvent.objects.filter(encounter=encounter, event='context.changed')
        for name, value in (('service_date', D1), ('setting', OFFICE), ('billing_context', 'professional'),
                            ('patient_status', 'new')):
            with self.subTest(field=name):
                before = rows.count()
                saved = self.save(encounter, **{name: value})
                self.assertEqual((saved.changed, saved.unchanged), ((name,), False))
                self.assertEqual(rows.count(), before + 1)
                self.drain()

    def test_u1_a_change_and_its_restore_answer_updating_then_restored(self):
        encounter = self.v2_fixture()
        changed = self.save(encounter, setting=OFFICE)
        self.assertEqual((changed.updating, changed.restored, changed.changed), (True, False, ('setting',)))
        restored = self.save(encounter, setting='')
        self.assertEqual((restored.updating, restored.restored, restored.changed), (False, True, ('setting',)))
        [row] = models.AuditEvent.objects.filter(encounter=encounter, event='context.changed', data__has_key='restored')
        self.assertEqual(row.data['restored'], str(encounter.current_assessment_id))


class BindingTests(UpdateCase):
    """U10, review.py's half (5.3, A7): while an update is pending the earlier codes are never decided on - a decision
    is refused under the row lock, no action is offered, readiness carries UPDATE_BLOCKER, the second review is neither
    offered nor accepted; after the update completes nothing of it stands."""

    def membership(self):
        return models.Membership.objects.get(workspace=self.ws, user=self.user)

    def test_u10_during_an_update_every_decision_is_refused_and_no_action_is_offered(self):
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        proposals = list(earlier.proposals.all())
        self.assertTrue(any(review.allowed_actions(item, earlier, self.membership()) for item in proposals))
        self.save(encounter, setting=OFFICE)
        row = self.fresh_row(encounter)
        for item in proposals:
            self.assertEqual(review.allowed_actions(item, earlier, self.membership()), [])
            for action in (review.APPROVE, review.REJECT, review.REVOKE):
                with self.subTest(code=item.code, action=action), self.assertRaises(ValidationError) as refused:
                    review.record_decision(encounter=row, proposal=item, action=action, user=self.user,
                                           membership=self.membership(), note='Synthetic.',
                                           acknowledgement=review.ACKNOWLEDGEMENTS.get(self.user.actor_kind, ''))
                self.assertEqual(refused.exception.messages, [customer_api.UPDATE_DECISION])
        self.assertFalse(models.Decision.objects.filter(encounter=encounter).exists())
        blockers = review.readiness(row)
        self.assertIn(review.UPDATE_BLOCKER, str(blockers))

    def test_u10_the_second_review_is_neither_offered_nor_accepted_during_an_idle_case_b_update(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        jobs.stop_encounter(encounter, self.user)  # idle: the update waits, nothing queued
        row = self.fresh_row(encounter)
        self.assertEqual(jobs._second_review_bounds(row, row.current_revision, row.current_context,
                                                    row.current_assessment), customer_api.UPDATE_DECISION)
        self.assertFalse(jobs.second_review_status(row)['available'])
        with self.assertRaises(jobs.Refused) as refused:
            jobs.request_second_review(row, self.user)
        self.assertEqual(str(refused.exception), customer_api.UPDATE_DECISION)
        self.assertFalse(Job.objects.filter(encounter=encounter, kind=Job.REVIEW2).exists())
        self.assertFalse(models.AuditEvent.objects.filter(encounter=encounter,
                                                          event='provider.second_review_requested').exists())

    def test_u10_an_a21_update_refuses_with_its_check_sentence(self):
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        Run.objects.filter(pk=earlier.provider_run_id).update(state=Run.UNKNOWN,
                                                              error='Read timed out after the request was sent.')
        jobs.reconcile(encounter, Run.objects.get(pk=earlier.provider_run_id), self.user, 'Synthetic: no answer.')
        row = self.fresh_row(encounter)
        item = earlier.proposals.first()
        with self.assertRaises(ValidationError) as refused:
            review.record_decision(encounter=row, proposal=item, action=review.REJECT, user=self.user,
                                   membership=self.membership(), note='Synthetic.')
        self.assertEqual(refused.exception.messages, [customer_api.UPDATE_DECISION_CHECK])

    def test_u10_after_the_update_completes_nothing_of_the_refusal_stands(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        self.drain()
        row = self.fresh_row(encounter)
        self.assertEqual((review.fresh(row), review.update_pending(row)), (True, False))
        self.assertNotIn(review.UPDATE_BLOCKER, str(review.readiness(row)))
        # (approving the update's final - a v2 assessment - reads its event coding through the overlay, step 5c's
        # reader of event_coding@2: until it lands such an assessment fails closed (D50), so the approval's 201 is
        # step 5d's API test once 5c is in; what is 5b's is that UPDATE_DECISION no longer answers)
        item = row.current_assessment.proposals.first()
        try:
            review.record_decision(encounter=row, proposal=item, action=review.REJECT, user=self.user,
                                   membership=self.membership(), note='Synthetic.')
        except ValidationError as exc:
            self.assertNotIn(customer_api.UPDATE_DECISION, exc.messages)


class SecondReviewHeldTests(UpdateCase):
    """A16 (7.3): the second review's offer is refused while Corti's provider hold stands, with a refusal that is true
    whatever the encounter's state (refutation 5b-r1, X6: a FRESH encounter, where nothing is updating, was told
    "Updating the codes is paused on this installation; resume ..." - RETRY_UPDATE_HELD, the retry_update refusal)."""

    def test_x6_a_fresh_encounter_is_refused_with_the_held_sentence_never_the_update_ones(self):
        encounter = self.v2_fixture()
        row = self.fresh_row(encounter)
        self.assertEqual((review.fresh(row), review.update_pending(row)), (True, False))
        provider_holds.record(encounter.current_assessment.provider_run,
                              provider_holds.Refusal(provider_holds.CORTI, provider_holds.QUOTA, 402))
        reason = jobs._second_review_bounds(row, row.current_revision, row.current_context, row.current_assessment)
        self.assertEqual(reason, jobs.SECOND_REVIEW_HELD)
        self.assertNotIn(reason, (customer_api.RETRY_UPDATE_HELD, customer_api.UPDATE_DECISION))
        self.assertFalse(customer_api.FORBIDDEN.search(reason))  # names no provider or model
        self.assertFalse(jobs.second_review_status(row)['available'])
        with self.assertRaises(jobs.Refused) as refused:
            jobs.request_second_review(row, self.user)
        self.assertEqual(str(refused.exception), jobs.SECOND_REVIEW_HELD)
        self.assertFalse(Job.objects.filter(encounter=encounter, kind=Job.REVIEW2).exists())

    def test_x6_during_an_update_the_update_refusal_is_asked_first(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        jobs.stop_encounter(encounter, self.user)
        provider_holds.record(encounter.current_assessment.provider_run,
                              provider_holds.Refusal(provider_holds.CORTI, provider_holds.QUOTA, 402))
        row = self.fresh_row(encounter)
        self.assertEqual(jobs._second_review_bounds(row, row.current_revision, row.current_context,
                                                    row.current_assessment), customer_api.UPDATE_DECISION)


class NotFinalTests(UpdateCase):
    """A17 [R:races-R3][R:legacy-L6]: while an update is pending an assessment that is not final (an assess #1 that owes
    peer stages) is recorded and never made current - the earlier codes stay current with their open questions; nothing
    is carried or withdrawn. The peer chain is HARNESS.md's: here the update's assessment is made to owe a peer stage
    (jobs.owed_peer_stages, which review.is_final reads), so persist_assessment's rule is what is under test."""

    def test_a17_an_updates_assessment_that_owes_peer_stages_is_recorded_never_current_then_a_restore(self):
        encounter = self.v2_fixture()
        earlier = encounter.current_assessment
        opened = set(models.Clarification.objects.filter(assessment=earlier, state=models.Clarification.OPEN)
                     .values_list('pk', flat=True))
        self.save(encounter, setting=OFFICE)
        real = jobs.owed_peer_stages

        def owes(assessment):
            return ('astra_peer',) if assessment.pk != earlier.pk else real(assessment)
        with mock.patch.object(jobs, 'owed_peer_stages', side_effect=owes), \
                mock.patch.object(jobs, '_queue_peers', return_value=None):
            assess = self.run_next(Job.ASSESS)
        made = models.Assessment.objects.get(pk=assess.result['assessment'])
        row = self.fresh_row(encounter)
        self.assertEqual(row.current_assessment_id, earlier.pk)  # never current
        audit = models.AuditEvent.objects.get(encounter=encounter, event='assessment.created',
                                              data__assessment=str(made.pk))
        self.assertEqual((audit.data['current'], audit.data['withdrawn'], audit.data['carried']), (False, 0, 0))
        self.assertEqual(set(models.Clarification.objects.filter(assessment=earlier, state=models.Clarification.OPEN)
                             .values_list('pk', flat=True)), opened)
        self.assertTrue(review.update_pending(row))
        # U8's third case: a restore after the update's assess #1 was recorded - the earlier codes fresh at once
        self.assertTrue(self.save(encounter, setting='').restored)
        row = self.fresh_row(encounter)
        self.assertEqual((row.current_assessment_id, review.fresh(row)), (earlier.pk, True))
        self.assertNotEqual(jobs._newest_assessment(row.current_revision), made)  # the abandoned assess #1 left out


class ProgressTests(UpdateCase):
    """U16 [R:truth-T2]: the panel during an update - steps from the progress jobs, busy and the phase from the target
    jobs; started_at the first save's; a step that ran for the update keeps its state; no provider or model named."""

    def panel(self, encounter, **kwargs):
        found = progress.encounter_progress(self.fresh_row(encounter), **kwargs)
        for text in (found['message'], (found['error'] or {}).get('text', ''), found['active_detail']):
            for word in PROVIDER_WORDS:
                self.assertNotIn(word, text)
        return found

    def steps(self, found):
        return {step['key']: step['state'] for step in found['steps']}

    def first_save_time(self, encounter):
        return (models.AuditEvent.objects.filter(encounter=encounter, event='context.changed')
                .order_by('created_at').first().created_at)

    def test_u16_a_setting_only_v2_update_reads_updating_with_skipped_steps_then_completed(self):
        encounter = self.v2_fixture()
        self.save(encounter, setting=OFFICE)
        self.save(encounter, setting=HOSPITAL)  # rapid saves in case A: started_at stays the first save's
        found = self.panel(encounter)
        self.assertEqual((found['phase'], found['busy']), ('updating', True))
        self.assertEqual(found['started_at'], progress._iso(self.first_save_time(encounter)))
        states = self.steps(found)
        self.assertEqual((states['reading'], states['identifying']), ('skipped', 'skipped'))
        self.drain()
        found = self.panel(encounter)
        self.assertIn(found['phase'], FINISHED)
        self.assertIsNotNone(found['finished_at'])

    def test_u16_a_legacy_update_names_the_pass_that_runs_and_keeps_its_reading_step_done(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        first = self.first_save_time(encounter)
        self.run_next(jobs.INTERPRET)
        job = jobs.claim_next()
        self.assertEqual(job.kind, jobs.APPRAISE)
        found = self.panel(encounter)
        self.assertEqual((found['phase'], found['active_detail']), ('updating', customer_api.APPRAISE_DETAIL))
        self.assertEqual(self.steps(found)['identifying'], 'active')
        jobs.run_job(job)
        self.run_next(Job.ANALYZE)
        found = self.panel(encounter)  # after the analyze: no reading is owed, its step keeps its state
        self.assertEqual(self.steps(found)['identifying'], 'done')
        self.assertEqual(found['started_at'], progress._iso(first))
        self.drain()
        found = self.panel(encounter)
        self.assertIn(found['phase'], FINISHED)
        self.assertEqual(self.steps(found)['identifying'], 'done')

    def test_u16_r3t2_a_save_beside_a_running_pass_1_reads_in_progress_never_waiting_to_start(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        running = jobs.claim_next()
        self.assertEqual(running.kind, jobs.INTERPRET)
        self.save(encounter, setting=HOSPITAL)  # queues its ':after-save:' twin beside the running pass 1
        found = self.panel(encounter)
        self.assertEqual((found['phase'], self.steps(found)['identifying'], found['active_detail']),
                         ('updating', 'active', progress.DETAILS[jobs.INTERPRET]))
        self.assertNotEqual(found['message'], progress.MESSAGES['queued'])
        jobs.run_job(running)
        found = self.panel(encounter)  # finished, its twin not run yet
        self.assertIn(self.steps(found)['identifying'], ('active', 'done'))
        self.assertNotEqual(found['message'], progress.MESSAGES['queued'])
        self.drain()
        found = self.panel(encounter)
        self.assertIn(found['phase'], FINISHED)
        self.assertEqual(self.steps(found)['identifying'], 'done')

    def test_u16_a_target_job_waiting_behind_a_superseded_running_stage_reads_waiting_for_earlier(self):
        encounter = self.v2_fixture()
        self.save(encounter, setting=OFFICE)
        running = jobs.claim_next()  # the first save's stage, still running when the next save lands
        self.save(encounter, setting=HOSPITAL)
        found = self.panel(encounter)
        self.assertEqual((found['phase'], found['message']), ('updating', progress.WAITING_FOR_EARLIER))
        jobs.run_job(running)
        self.assertTrue(Job.objects.get(pk=running.pk).result.get('superseded'))
        self.drain()
        self.assertIn(self.panel(encounter)['phase'], FINISHED)

    def test_u16_an_upload_reads_its_first_jobs_start_and_never_not_started_before_a_running_step(self):
        encounter, _ = self.upload()
        self.run_next(Job.EXTRACT)
        job = jobs.claim_next()
        self.assertEqual(job.kind, jobs.INTERPRET)
        found = self.panel(encounter)
        first = Job.objects.filter(encounter=encounter).order_by('created_at').first()
        self.assertEqual((found['phase'], found['started_at']), ('processing', progress._iso(first.created_at)))
        self.assertEqual(self.steps(found)['reading'], 'done')
        self.assertEqual(self.steps(found)['identifying'], 'active')
        jobs.run_job(job)
        self.drain()


class W1ProgressTests(UpdateCase):
    """U16's W1 runs [R3:truth-R3T-1][R3:truth-R3T-2]: three saves within moments (a date, a setting, the date back)
    land while the first save's Corti request is in flight; it answers 500, and again 402; the third save re-checks
    with E's own run (no predict of its own). 'Checking suggested codes' never reads failed or stopped for the first
    save's predict - while the third save's chain runs, nor after it completes - and the final carries the last values."""

    panel, steps = ProgressTests.panel, ProgressTests.steps

    def test_u16_w1_three_saves_while_the_first_saves_predict_answers_500_or_402(self):
        from tests.v2.test_update_pipeline import UNDATED, corti_refusal

        for outcome in (corti_refusal(500), corti_refusal(402)):
            with self.subTest(status=outcome.http_status):
                self.new_workspace()
                encounter = self.v2_fixture(UNDATED)
                own = self.panel(encounter)['phase']  # E's own phase (an undated document's codes ask its date)
                self.save(encounter, service_date=D2)
                first = jobs.claim_next()
                self.assertEqual(first.kind, Job.PREDICT)
                seen = {}

                def saves_then_answers(request, *, deadline_s):
                    self.corti.sent.append(request.canonical_sha256)
                    self.save(encounter, setting=OFFICE)
                    self.save(encounter, service_date='')  # the date back: E's own request again
                    seen['during'] = self.steps(self.panel(encounter))
                    return outcome
                with mock.patch.object(self.corti, 'send', side_effect=saves_then_answers):
                    finished = jobs.run_job(first)
                self.assertIn(finished.state, (Job.FAILED, Job.CANCELLED))  # the late finisher's own outcome
                self.assertNotIn(seen['during']['checking'], ('failed', 'stopped'))
                row = self.fresh_row(encounter)
                queued = [job.kind for job in Job.objects.filter(encounter=encounter, state=Job.QUEUED,
                                                                 context_id=row.current_context_id)]
                self.assertEqual(queued, [Job.ASSESS])  # the third save re-checks with E's run: no predict of its own
                found = self.panel(encounter)
                self.assertEqual(found['phase'], 'updating')
                self.assertNotIn(self.steps(found)['checking'], ('failed', 'stopped'))
                self.drain()
                found = self.panel(encounter)
                self.assertEqual(found['phase'], own)  # the update finished: the final's own phase, as E's was
                self.assertIsNotNone(found['finished_at'])
                self.assertNotIn(self.steps(found)['checking'], ('failed', 'stopped'))
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row))
                self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE})
                if outcome.http_status == 402:
                    self.assertTrue(provider_holds.held(provider_holds.CORTI))  # set whatever the stage (A16)
                    self.release_corti()


class MemberActTests(UpdateCase):
    """U18 (A18) [R:races-R4][R:races-R5]: a context save while a member-act stage on the current context is queued or
    running is refused with the busy sentence and writes nothing; after the stage ends the save is accepted."""

    def test_u18_a_save_while_an_answers_recompute_is_queued_and_while_it_runs_is_refused(self):
        encounter = self.v2_fixture()
        recompute = jobs.recompute_after_answers(self.fresh_row(encounter), self.user)
        self.assertIsNotNone(recompute)
        self.assertIn(jobs.AGAIN_MARK, recompute.idempotency_key)
        for when in ('queued', 'running'):
            with self.subTest(when=when):
                if when == 'running':
                    self.assertEqual(jobs.claim_next().pk, recompute.pk)
                before = counts(encounter)
                with self.assertRaises(jobs.Refused) as refused:
                    self.save(encounter, setting=OFFICE)
                self.assertEqual(str(refused.exception), jobs.CONTEXT_BUSY_MESSAGE)
                self.assertEqual(counts(encounter), before)
        jobs.run_job(Job.objects.get(pk=recompute.pk))
        self.assertTrue(self.save(encounter, setting=OFFICE).updating)  # the act ended: accepted
        self.drain()
        self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u18_a_save_while_a_second_review_stage_is_queued_is_refused(self):
        """(The stage is queued as request_second_review queues it, on the current context, under its own key: whether
        one can be asked for on a fixture is _second_review_bounds', tested where it is defined.)"""
        encounter = self.v2_fixture()
        row = self.fresh_row(encounter)
        stage = jobs.enqueue(Job.REVIEW2, encounter=row, revision=row.current_revision, context=row.current_context,
                             provider_run=row.current_assessment.provider_run,
                             key=jobs._second_review_key(row.current_revision, row.current_assessment),
                             requested_by=self.user)
        before = counts(encounter)
        with self.assertRaises(jobs.Refused) as refused:
            self.save(encounter, service_date=D1)
        self.assertEqual(str(refused.exception), jobs.CONTEXT_BUSY_MESSAGE)
        self.assertEqual(counts(encounter), before)
        jobs.stop_encounter(row, self.user)
        stage.refresh_from_db()
        self.assertEqual(stage.state, Job.CANCELLED)
        self.assertFalse(self.save(encounter, service_date=D1).unchanged)


class CaseBDetailsTests(UpdateCase):
    """U19 [R:truth-T3]: a legacy encounter held on a member date conflict, then "Use document date" (case B): while the
    update is pending the phase follows the update - updating, failed with the reading's Retry, paused under a hold -
    never action_needed."""

    def test_u19_a_case_b_date_save_follows_the_update_never_action_needed(self):
        from tests.legacy_chain import legacy_chain

        with legacy_chain():
            encounter, _ = self.upload(values={'service_date': D2})  # the document says D1: a member date conflict
            self.drain()
        self.interpreter.sent.clear()
        row = self.fresh_row(encounter)
        self.assertTrue(progress.date_held(row))
        self.assertEqual(progress.encounter_progress(row)['phase'], 'action_needed')
        self.interpreter.script = {EXTRACTION: [answered(HTTP_500, status=500), answered(BARE_429, status=429)]}
        self.save(encounter, service_date=D1)  # "Use document date"
        row = self.fresh_row(encounter)
        self.assertFalse(progress.date_held(row))
        self.assertEqual(progress.encounter_progress(row)['phase'], 'updating')
        self.drain()
        found = progress.encounter_progress(self.fresh_row(encounter))
        self.assertEqual((found['phase'], found['error']['action']), ('failed', 'retry_reading'))
        jobs.retry_reading(encounter, self.user)
        self.drain()
        self.assertTrue(holds.is_held())
        found = progress.encounter_progress(self.fresh_row(encounter))
        self.assertEqual((found['phase'], found['error']['action']), ('paused', 'resume'))
        operator = f.user()
        ops.grant(operator)
        holds.release(user=operator, note='Synthetic release.')
        jobs.resume(encounter, self.user)
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D1})
        self.assertIn(progress.encounter_progress(row)['phase'], FINISHED)


class HoldClassificationTests(UpdateCase):
    """U20's rule (A16, A20): a provider hold is set only from a run's RECORDED http_status and sent - never an error
    text or a body - one per run, a reuse sets none, and only an operator's recorded release ends it."""

    def run_of(self, provider, status, sent, **extra):
        encounter = getattr(self, '_encounter', None) or self.v2_fixture()
        self._encounter = encounter
        return Run.objects.create(encounter=encounter, revision=encounter.current_revision, provider=provider,
                                  adapter_version='synthetic@1', request_sha256='d' * 64, request_body={}, contexts=[],
                                  state=Run.FAILED if sent else Run.NOT_SENT, sent=sent, http_status=status,
                                  error=extra.pop('error', ''), finished_at=timezone.now(), **extra)

    def test_u20_the_classification_table(self):
        table = [
            # Corti's coding service: sent
            ('corti', 401, True, provider_holds.AUTH), ('corti', 402, True, provider_holds.QUOTA),
            ('corti', 403, True, provider_holds.PERMISSION), ('corti', 429, True, provider_holds.QUOTA),
            ('replay', 402, True, provider_holds.QUOTA), ('corti', 400, True, None), ('corti', 404, True, None),
            ('corti', 500, True, None), ('corti', 503, True, None), ('corti', None, True, None),
            # Corti's token endpoint: not sent, its status recorded - any 4xx
            ('corti', 400, False, provider_holds.AUTH), ('corti', 401, False, provider_holds.AUTH),
            ('corti', 402, False, provider_holds.QUOTA), ('corti', 403, False, provider_holds.PERMISSION),
            ('corti', 429, False, provider_holds.QUOTA), ('corti', 500, False, None), ('corti', 302, False, None),
            ('corti', None, False, None),
            # a participant's exchange: any 4xx but 413
            ('astra', 429, True, provider_holds.QUOTA), ('fable', 400, True, provider_holds.REFUSED),
            ('fable', 413, True, None), ('fable', 500, True, None), ('astra', 401, False, None),
            # Gemini's runs are interpretation.holds', never these
            ('gemini', 429, True, None), ('gemini', 402, True, None),
        ]
        for name, status, sent, reason in table:
            with self.subTest(provider=name, status=status, sent=sent):
                found = provider_holds.classify(name, status, sent)
                self.assertEqual(found.reason if found is not None else None, reason)
        # a status is an int, never text: a "402" string or a bool is no status
        self.assertIsNone(provider_holds.classify('corti', '402', True))
        self.assertIsNone(provider_holds.classify('corti', True, True))

    def test_u20_an_error_text_that_names_a_refusal_sets_nothing(self):
        run = self.run_of('corti', 500, True, error='HTTP 402 Payment Required; quota exceeded; 401 unauthorized')
        self.assertIsNone(provider_holds.record(run))
        self.assertFalse(provider_holds.held('corti'))

    def test_u20_one_hold_per_run_none_for_a_reuse_and_only_an_operators_release_ends_it(self):
        run = self.run_of('corti', 402, True)
        hold = provider_holds.record(run)
        self.assertEqual(provider_holds.record(run).pk, hold.pk)  # one run sets at most one hold
        self.assertTrue(provider_holds.sets_hold(run) and provider_holds.held('replay'))
        reuse = self.run_of('corti', 402, True, reused_from=run)
        self.assertIsNone(provider_holds.record(reuse))
        member = self.user
        with self.assertRaises(PermissionError):
            provider_holds.release('corti', user=member, note='Synthetic: not an operator.')
        self.assertTrue(provider_holds.held('corti'))
        operator = f.user()
        ops.grant(operator)
        with self.assertRaises(ValueError):
            provider_holds.release('corti', user=operator, note='   ')
        [released] = provider_holds.release('corti', user=operator, note='Synthetic: the quota was raised.')
        self.assertEqual(released.hold_id, hold.pk)
        self.assertFalse(provider_holds.held('corti'))
        self.assertTrue(provider_holds.sets_hold(run))  # the row stays: still a hold-setting run
        self.assertEqual(provider_holds.record(run).pk, hold.pk)  # settling it again never sets it again
        self.assertFalse(provider_holds.held('corti'))
        self.assertEqual(provider_holds.release('corti', user=operator, note='Synthetic: again.'), [])

    def test_u20_a_refusal_no_row_names_is_read_by_status_for_a_retry_never_as_a_hold_setting_run(self):
        run = self.run_of('corti', 429, True)  # recorded before the install: no ProviderHold row names it
        self.assertFalse(provider_holds.sets_hold(run))
        self.assertTrue(provider_holds.retry_refused(run))
        self.assertTrue(provider_holds.retry_refused(SimpleNamespace(provider='corti', http_status=401, sent=False)))
        self.assertFalse(provider_holds.retry_refused(SimpleNamespace(provider='corti', http_status=500, sent=False)))
        self.assertFalse(provider_holds.retry_refused(SimpleNamespace(provider='astra', http_status=429, sent=True)))
