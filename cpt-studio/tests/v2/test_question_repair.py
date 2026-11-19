"""Round r3's build, lane 'pipe', its repair pass (DECISIONS D320; the lane's refutation, findings PIPE-R1 and PIPE-R2,
each reproduced): the two class rules, each pinned by the finding's own input first and then by the other members of
its class and its boundary. TEXT-ONLY and SYNTHETIC: every document is test_jobs' POLYP note (fictional clinicians, no
real patient), driven through the question stage's own scaffolding (test_question_stage.QuestionCase: the production
Fable connector, fable_adapter.InterpreterF, with its one exchange scripted) - nothing is sent anywhere.

PIPE-R1. An outcome that sets an INSTALLATION-WIDE hold (one that is not request-bound: auth, permission, quota, a
refusal of the version or the account, a substituted model) never decides its question request: it says nothing about
that request. Only an answer, an answer cut off at its output limit, a request-bound decline and a definite failure of
that request decide it (jobs._question_outcome). The stage pauses on the hold as every reading stage whose own answer
set one does (CANCELLED with jobs.HOLD_SET_MESSAGE, the paused phase), nothing is written, queued or sent, and after an
operator's release a member's Resume sends exactly the requests still owed, once each - so the release report's "a
member's next Resume may send its request again" is true of a question request too. The store refuses a row whose
question request was decided by such a hold.

PIPE-R2. A stage queued from a run's key is that run's OWN stage only while the run's revision is the one it is queued
for (jobs._own_stage_of): every key-builder that names a run checks it - a reconciliation (jobs._reading_reconciled), a
retry (jobs._retry_key) and the sweep's settled path of an orphaned run (jobs.mark_stale) - so the reconciliation of a
superseded revision's question run continues the CURRENT revision's reading from its first stage, as a pass-2 run's
already did."""
from __future__ import annotations

import copy
import json
import threading
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import Client
from django.utils import timezone

from studio import jobs, models, review
from studio.interpretation import fable_adapter, store
from studio.interpretation import holds as interpretation_holds
from studio.interpretation.engine import asking
from tests.support import factories as f
from tests.support import operator as ops
from tests.v2 import test_jobs as TJ
from tests.v2.test_fable_adapter import answer_stream, error_body
from tests.v2.test_holds import an_operator, fable_run
from tests.v2.test_question_stage import (QUESTION, SESSION_E1, SESSION_E2, ConcurrencyTests, QuestionCase,
                                          question_answer)

Run, Job = models.ProviderRun, models.Job
APPRAISAL = fable_adapter.APPRAISAL
RELEASE_NOTE = 'Synthetic release: the account is usable again.'
RECONCILE_NOTE = 'Synthetic reconciliation: the vendor console was checked for this request.'
ADDENDUM = 'Synthetic addendum: the patient was discharged home.'


def exchange(data, status):
    """A scripted question exchange: the same RawExchange whatever request it answers."""
    return lambda sha, question: TJ.answered(data, status=status)


def answering(sha, question):
    """A scripted question exchange answering the request it is given in the release pattern (test_question_stage)."""
    return TJ.answered(TJ.body(question_answer(question, question.request.contexts[0])))


class _Base(QuestionCase):
    def held_round(self, *scripts, keys=(SESSION_E2,)):
        """POLYP read through pass 2 with ``keys`` left unanswered, then its question stage's round sent once with
        ``scripts`` answering its requests in turn: (encounter, revision, the stage as it ended)."""
        encounter, revision, queued = self.to_questions(*keys, question_script=list(scripts))
        done = self.run_next(QUESTION)
        return encounter, revision, done

    def release(self, name='synthetic-operator-repair'):
        released = interpretation_holds.release(user=an_operator(name), note=RELEASE_NOTE)
        self.assertTrue(released)
        self.assertFalse(interpretation_holds.is_held())
        return released

    def inventory(self, revision):
        return models.EventInventory.objects.filter(revision=revision).first()

    def queued(self, encounter):
        return list(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)))


# --- PIPE-R1 ---------------------------------------------------------------------------------------------------------


class InstallationHoldTests(_Base):
    """PIPE-R1's class: every outcome that sets an installation-wide hold leaves its request owed and pauses the stage;
    the operator's release and a member's Resume send it again, once, and the code is decided by the answer."""

    def assert_paused_deciding_nothing(self, encounter, revision, done):
        self.assertTrue(interpretation_holds.is_held())
        self.assertEqual((done.state, done.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE), done.result)
        for run in self.question_runs(encounter):
            self.assertIsNone(jobs._question_outcome(run), (run.state, run.http_status))  # owed: decides nothing
        self.assertIsNone(self.inventory(revision))  # no row: nothing was decided
        self.assertEqual(self.queued(encounter), [])  # nothing queued that would send
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertTrue(review.can_resume(encounter))

    def assert_paused_then_sent_again(self, data, status):
        encounter, revision, done = self.held_round(exchange(data, status))
        self.assert_paused_deciding_nothing(encounter, revision, done)
        [report] = [interpretation_holds.release_report(item) for item in self.release()]
        self.assertEqual((report['request_bound'], report['members']), (False, interpretation_holds.UNBLOCKED))
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        sent = self.interpreter.question_sent
        self.assertEqual(len(sent), 2)  # the held request sent again, once
        self.assertEqual(len(set(sent)), 1)  # ... the identical request
        inventory = self.inventory(revision)
        self.assertEqual([item['outcome'] for item in inventory.verification['question_runs']], ['answered'])
        self.assertEqual([item['result'] for item in inventory.events['questions']], ['supported'])
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r1_the_findings_input_a_402_decides_nothing_and_a_resume_after_the_release_sends_it_again(self):
        """The finding's input: pass 2 leaves E2's session claim unanswered, one question request, answered HTTP 402
        billing_error. Before the repair the row was written at once (question_request_failed:hold), 45385 held, and no
        member act ever asked the question again."""
        self.assert_paused_then_sent_again(TJ.HTTP_402, 402)

    def test_r1_a_401_authentication_hold_decides_nothing(self):
        self.assert_paused_then_sent_again(error_body('authentication_error'), 401)

    def test_r1_a_403_permission_hold_decides_nothing(self):
        self.assert_paused_then_sent_again(error_body('permission_error'), 403)

    def test_r1_a_bare_429_quota_hold_decides_nothing(self):
        self.assert_paused_then_sent_again(TJ.BARE_429, 429)

    def test_r1_a_400_refusal_of_the_version_or_account_decides_nothing(self):
        self.assert_paused_then_sent_again(TJ.HTTP_400, 400)

    def test_r1_a_substituted_model_decides_nothing(self):
        substituted = answer_stream(json.dumps({'verdicts': [], 'unlisted': []}), model='claude-synthetic-other-9')
        self.assert_paused_then_sent_again(substituted, 200)

    def test_r1_a_resume_while_the_hold_stands_sends_nothing_and_pauses_again(self):
        encounter, revision, done = self.held_round(exchange(TJ.HTTP_402, 402))
        self.assert_paused_deciding_nothing(encounter, revision, done)
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)  # nothing sent while the hold stands
        self.assertIsNone(self.inventory(revision))
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertTrue(review.can_resume(encounter))
        self.release()
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r1_a_hold_released_at_once_sends_nothing_until_a_member_resumes(self):
        """No automatic retry (D11): the stage that met the hold queued nothing, so a release before anything follows
        sends nothing by itself; only a member's Resume sends the request again."""
        encounter, revision, done = self.held_round(exchange(TJ.HTTP_402, 402))
        self.release()
        self.assertEqual(self.drain(), [])
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r1_a_round_keeps_each_answer_and_sends_only_the_held_request_again(self):
        """Two requests of one round, sent together: one answered, one met by a 402. The answered one is decided and
        never sent again; the stage pauses; after the release a Resume sends the held one alone, once."""
        guard, held = threading.Lock(), []

        def first_held(sha, question):
            with guard:
                first = not held
                if first:
                    held.append(sha)
            return TJ.answered(TJ.HTTP_402, status=402) if first else answering(sha, question)
        with mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                               ConcurrencyTests.partition(specs, pool, round_)):
            encounter, revision, done = self.held_round(first_held, first_held, keys=(SESSION_E2, SESSION_E1))
            self.assertEqual(len(self.interpreter.question_sent), 2)
            self.assertEqual((done.state, done.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE), done.result)
            self.assertEqual(self.queued(encounter), [])
            outcomes = sorted(str(jobs._question_outcome(run)) for run in self.question_runs(encounter))
            self.assertEqual(outcomes, ['None', 'answered'])
            self.assertIsNone(self.inventory(revision))
            self.release()
            self.assertIsNotNone(jobs.resume(encounter, self.user))
            self.finish(encounter)
        sent = self.interpreter.question_sent
        self.assertEqual(len(sent), 3)
        self.assertEqual(sent[2], held[0])  # only the held request, once
        inventory = self.inventory(revision)
        self.assertEqual(sorted(item['outcome'] for item in inventory.verification['question_runs']),
                         ['answered', 'answered'])
        self.assertEqual({item['result'] for item in inventory.events['questions']}, {'supported'})
        self.assertEqual(len(inventory.events['questions']), 2)  # both questions established
        self.assertEqual(self.status(encounter, '45385'), 'ready')


class DecidingOutcomeTests(_Base):
    """PIPE-R1's boundary: what DOES decide a question request is unchanged - a request-bound decline (the model
    declined, or an error event after message_start) and a definite failure leave its questions unresolved for good."""

    def assert_decided(self, data, status, reason, *, held):
        encounter, revision, done = self.held_round(exchange(data, status))
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        self.finish(encounter)
        [record] = self.inventory(revision).events['questions']
        self.assertEqual(record['reasons'], [f'question_request_failed:{reason}'])
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')
        self.assertEqual(interpretation_holds.is_held(), held)
        if held:
            [report] = [interpretation_holds.release_report(item) for item in self.release()]
            self.assertEqual(report['members'], interpretation_holds.BLOCKED)
        jobs.resume(encounter, self.user)  # nothing is owed: a fresh encounter is not resumed
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)  # never sent again
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_r1_boundary_a_decline_decides_its_request(self):
        self.assert_decided(TJ.declined_stream(), 200, 'declined', held=True)

    def test_r1_boundary_an_error_event_after_message_start_decides_its_request(self):
        self.assert_decided(TJ.error_after_start('invalid_request_error'), 200, 'declined', held=True)

    def test_r1_boundary_a_definite_failure_decides_its_request(self):
        self.assert_decided(TJ.HTTP_500, 500, 'failed', held=False)

    def test_r1_boundary_a_per_minute_rate_limit_is_a_definite_failure(self):
        self.assert_decided(error_body('rate_limit_error'), 429, 'failed', held=False)


class OutcomeWordTests(_Base):
    """jobs._question_outcome over every sent outcome shape, read from the run as stored (no hold row needed)."""

    def test_r1_the_outcome_word_of_every_sent_outcome(self):
        encounter, revision = self.upload(TJ.NOTE)
        rows = [
            ('succeeded', 200, TJ.body({'verdicts': [], 'unlisted': []}), 'answered'),
            ('succeeded', 200, answer_stream('', stop_reason='max_tokens'), 'too_long'),
            ('succeeded', 200, TJ.declined_stream(), 'declined'),
            ('succeeded', 200, TJ.error_after_start('invalid_request_error'), 'declined'),
            ('succeeded', 200, TJ.error_first('overloaded_error'), 'failed'),
            ('failed', 500, TJ.HTTP_500, 'failed'),
            ('failed', 429, error_body('rate_limit_error'), 'failed'),
            ('failed', 402, TJ.HTTP_402, None),
            ('failed', 401, error_body('authentication_error'), None),
            ('failed', 403, error_body('permission_error'), None),
            ('failed', 404, error_body('not_found_error'), None),
            ('failed', 429, TJ.BARE_429, None),
            ('failed', 400, TJ.HTTP_400, None),
            ('succeeded', 200, answer_stream('{}', model='claude-synthetic-other-9'), None),
        ]
        for state, status, data, expected in rows:
            with self.subTest(state=state, status=status, expected=expected):
                run = fable_run(encounter, revision, state=state, http_status=status, body=data)
                self.assertEqual(jobs._question_outcome(run), expected)
                self.assertEqual(jobs._sets_installation_hold(run), expected is None)


class StoreTests(_Base):
    def test_r1_the_store_refuses_a_row_deciding_a_question_request_by_an_installation_hold(self):
        """The store's closed outcome words name only what decides a request: a row binding a request decided by an
        installation-wide hold ('hold') is refused; the same row decided by a definite failure loads."""
        encounter, revision, done = self.held_round(exchange(TJ.HTTP_500, 500))
        self.finish(encounter)
        inventory = self.inventory(revision)
        fields = store.fields_of_v2(inventory)
        appraised = Run.objects.get(pk=inventory.appraisal_run_id).response_sha256

        def load(changed):
            changed['sha256'] = store.content_sha256_v2(changed)
            return store.load_v2(changed, text_sha256=fields['text_sha256'], response_sha256=fields['response_sha256'],
                                 appraisal_response_sha256=appraised)
        load(copy.deepcopy(fields))  # as written: decided by a definite failure
        held = copy.deepcopy(fields)
        held['verification']['question_runs'][0]['outcome'] = 'hold'
        held['verification']['question_health'][0]['refused'] = ['question_request_failed:hold']
        held['events']['questions'][0]['reasons'] = ['question_request_failed:hold']
        with self.assertRaises(store.StoreError):
            load(held)
        self.assertNotIn('hold', store.QUESTION_RUN_OUTCOMES)


class LateHoldTests(_Base):
    """PIPE-R1 when the hold is recorded late: the worker dies after the round's 402 was recorded on its run and before
    the stage settled it (no hold row yet). The startup sweep's settled path decides nothing and sends nothing; the
    next send door records the hold from the run's own bytes (D53, jobs._record_unsettled_holds) before anything is
    sent, so a Resume pauses; after the release a Resume sends the request again, once."""

    def test_r1_a_402_its_worker_never_settled_decides_nothing_and_is_sent_again_only_after_the_release(self):
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=[exchange(TJ.HTTP_402, 402)])

        class Died(BaseException):
            pass
        job = jobs.claim_next()
        with mock.patch.object(jobs, '_settle_question_run', side_effect=Died):
            with self.assertRaises(Died):
                jobs.run_job(job)
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.http_status), (Run.FAILED, 402))
        self.assertFalse(interpretation_holds.is_held())  # its hold is not recorded yet
        self.assertIsNone(jobs._question_outcome(run))
        jobs.mark_stale(startup=True)
        self.drain()  # the settled path: the request is owed, and the settled path never sends
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertIsNone(self.inventory(revision))
        self.assertEqual(self.state(encounter), 'stopped')  # read afresh: the encounter's revision was read since
        self.assertTrue(review.can_resume(encounter))
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.drain()
        self.assertTrue(interpretation_holds.is_held())  # recorded at the send door, before anything was sent
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertIsNone(self.inventory(revision))
        self.release()
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertEqual(self.status(encounter, '45385'), 'ready')


# --- PIPE-R2 ---------------------------------------------------------------------------------------------------------


class SupersededRevisionTests(_Base):
    """PIPE-R2's class: a key-builder that names a run queues that run's own stage only for the run's own revision."""

    def questioned(self, *keys, **kwargs):
        interpreter = super().questioned(*keys, **kwargs)
        interpreter.answers = _Answers(interpreter.answers)
        return interpreter

    def new_revision(self, encounter):
        """A newer current revision of the encounter, as an addendum makes one (A1: accepted while an earlier
        revision's outcome is unknown): POLYP with an addendum block after its units (jobs.addendum_block_text), its
        pipeline started. Its text is new, so its own pass 1 is a request of its own (as every addendum's is)."""
        number = encounter.revisions.count() + 1
        text = TJ.POLYP + jobs.addendum_block_text(number, timezone.now(), ADDENDUM)
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        review.invalidate_for_new_revision(encounter, revision)
        jobs.start_pipeline(revision, self.user)
        return revision

    def test_r2_the_findings_input_a_superseded_revisions_question_run_reconciled_continues_the_current_revision(self):
        """The finding's input: revision 1's question request ends UNKNOWN; a new revision is added, whose reading the
        unknown outcome blocks; the member reconciles revision 1's question run. Before the repair that queued a
        QUESTION stage for revision 2 keyed by revision 1's pass-2 run, which failed - revision 2 got no reading."""
        encounter, first, queued = self.to_questions(SESSION_E2, question_script=[lambda sha, question: TJ.UNKNOWN])
        self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.revision_id), (Run.UNKNOWN, first.pk))
        second = self.new_revision(encounter)
        before = self.drain()
        self.assertIn({'blocked': jobs.INTERPRET_BLOCKED}, [job.result for job in before])
        self.assertIsNone(self.inventory(second))
        self.assertTrue(jobs.reconcile(encounter, run, self.user, RECONCILE_NOTE))
        [after] = self.queued(encounter)
        self.assertEqual((after.kind, after.revision_id, after.idempotency_key),
                         (jobs.INTERPRET, second.pk, jobs._interpret_key(second, f'after-reconcile:{run.pk}')))
        done = self.finish(encounter)
        self.assertEqual([job for job in done if job.state == Job.FAILED], [])
        self.assertIsNotNone(self.inventory(second))  # revision 2's reading continued to its row
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_assessment.revision_id, second.pk)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r2_boundary_the_same_run_reconciled_while_its_revision_is_current_is_its_own_stage(self):
        encounter, first, queued = self.to_questions(SESSION_E2, question_script=[lambda sha, question: TJ.UNKNOWN])
        self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.drain()  # the next wave's stage: blocked by the unknown outcome
        self.assertTrue(jobs.reconcile(encounter, run, self.user, RECONCILE_NOTE))
        [after] = self.queued(encounter)
        self.assertEqual((after.kind, after.revision_id), (QUESTION, first.pk))
        self.assertTrue(after.idempotency_key.endswith(f':after-reconcile:{run.pk}'))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)  # the one attempt the reconciliation allowed
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r2_a_superseded_revisions_pass_2_run_reconciled_continues_the_current_revision(self):
        """The same rule for a pass-2 run (the contrast the finding names): its appraise stage only on its own
        revision, else the current revision's reading from its first stage."""
        interpreter = self.questioned(SESSION_E2)
        interpreter.script = {APPRAISAL: [TJ.UNKNOWN]}
        encounter, first = self.upload(TJ.POLYP)
        for kind in ('extract', 'interpret', 'appraise'):
            self.run_next(kind)
        [run] = [item for item in Run.objects.filter(encounter=encounter, purpose=APPRAISAL)]
        self.assertEqual(run.state, Run.UNKNOWN)
        second = self.new_revision(encounter)
        self.drain()
        self.assertTrue(jobs.reconcile(encounter, run, self.user, RECONCILE_NOTE))
        [after] = self.queued(encounter)
        self.assertEqual((after.kind, after.revision_id), (jobs.INTERPRET, second.pk))
        self.finish(encounter)
        self.assertIsNotNone(self.inventory(second))
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_r2_a_retry_key_names_a_runs_own_stage_only_on_the_runs_revision(self):
        encounter, first, queued = self.to_questions(SESSION_E2)
        [pass2] = [item for item in Run.objects.filter(encounter=encounter, revision=first, purpose=APPRAISAL)
                   if 'question' not in (item.scope or {})]
        extraction = Run.objects.get(pk=pass2.scope['extraction'])
        self.assertEqual(jobs._retry_key(first, pass2, 'retry'),
                         (jobs.APPRAISE, jobs._appraise_key(first, extraction, pass2.request_sha256[:16],
                                                            f'retry:{pass2.pk}')))
        second = self.new_revision(encounter)
        self.assertEqual(jobs._retry_key(second, pass2, 'retry'),
                         (jobs.INTERPRET, jobs._interpret_key(second, f'retry:{pass2.pk}')))
        self.assertFalse(jobs._own_stage_of(pass2, second))
        self.assertTrue(jobs._own_stage_of(pass2, first))

    def orphaned(self):
        """A question run left 'sending' by a stage that no longer runs, its one exchange recorded answered (the shape
        the sweep settles from its exchange, P-6), older than the sweep's cutoff: (encounter, revision, run)."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.finish(encounter)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.exchanges.count(), 1)
        old = timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS + 60)
        Run.objects.filter(pk=run.pk).update(state=Run.SENDING, response_bytes=b'', response_sha256='', created_at=old)
        return encounter, revision, run

    def settled_paths(self, encounter, run):
        return list(Job.objects.filter(encounter=encounter, kind=QUESTION,
                                       idempotency_key__contains=f':settled:{run.pk}'))

    def test_r2_the_sweep_queues_an_orphaned_runs_settled_path_on_its_own_current_revision(self):
        encounter, revision, run = self.orphaned()
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual(run.state, Run.SUCCEEDED)
        self.assertEqual([job.revision_id for job in self.settled_paths(encounter, run)], [revision.pk])

    def test_r2_the_sweep_queues_no_stage_for_an_orphaned_run_of_a_superseded_revision(self):
        encounter, revision, run = self.orphaned()
        self.new_revision(encounter)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual(run.state, Run.SUCCEEDED)  # settled from its exchange (P-6), as before
        self.assertEqual(self.settled_paths(encounter, run), [])


class SupersededRevisionDoorTests(_Base):
    """The finding's input through the production doors: the member's addendum through the customer API and the
    reconciliation through the operator API (the operator is also a reviewer of the workspace here, so the chain's
    predict, requested by the reconciling user, may start a live provider request)."""

    def setUp(self):
        super().setUp()
        self.member = Client()
        self.member.force_login(self.user)
        self.operator_user = f.user('synthetic-repair-operator')
        ops.grant(self.operator_user)
        f.member(self.ws, self.operator_user, role=models.Membership.REVIEWER)
        self.operator = Client()
        self.operator.force_login(self.operator_user)

    def questioned(self, *keys, **kwargs):
        interpreter = super().questioned(*keys, **kwargs)
        interpreter.answers = _Answers(interpreter.answers)
        return interpreter

    def post(self, client, path, data=None):
        response = client.post(path, json.dumps(data or {}), content_type='application/json')
        return response.status_code, response.json()

    def test_r2_the_findings_input_through_the_addendum_and_operator_apis(self):
        encounter, first, queued = self.to_questions(SESSION_E2, question_script=[lambda sha, question: TJ.UNKNOWN])
        self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        status, body = self.post(self.member, f'/api/encounters/{encounter.pk}/addenda',
                                 {'text': 'Synthetic addendum: the patient was discharged home.',
                                  'synthetic_attestation': 'yes'})
        self.assertEqual(status, 201, body)
        encounter.refresh_from_db()
        second = encounter.current_revision
        self.assertEqual((second.number, second.kind), (2, models.SourceRevision.ADDENDUM))
        self.drain()
        self.assertIsNone(self.inventory(second))
        status, body = self.post(self.operator, f'/ops/api/encounters/{encounter.pk}/reconcile',
                                 {'provider_run_id': str(run.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(status, 201, body)
        [after] = self.queued(encounter)
        self.assertEqual((after.kind, after.revision_id), (jobs.INTERPRET, second.pk))
        done = self.finish(encounter)
        self.assertEqual([job for job in done if job.state == Job.FAILED], [])
        self.assertIsNotNone(self.inventory(second))
        self.assertEqual(self.status(encounter, '45385'), 'ready')


class _Answers(dict):
    """test_jobs' answers by document text; an addendum revision of POLYP (POLYP's units unchanged, the addendum's units
    after them) is answered with POLYP's own pass-1 answer, which cites only POLYP's units."""

    def __missing__(self, text):
        if text.startswith(TJ.POLYP.rstrip('\n')) and 'ADDENDUM (revision' in text:
            return TJ.polyp_answer
        raise KeyError(text)
