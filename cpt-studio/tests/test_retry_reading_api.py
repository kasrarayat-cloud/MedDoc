"""The recorded retry door and the interpreter hold, over HTTP (Gemini migration slice S11; design/FINAL.md 8.3, 11.2 and
11.3; DECISIONS D11; contract C5): POST /api/encounters/<id>/retry-reading for an owner or a reviewer, and the operator
console's retry (with its recorded override of a cut-off answer) and hold release under /ops/.

- A failed reading is retried once: its run released (reconciled_by, reconciled_at, 'released for one retry'), an
  'interpret:...:retry:<run>' stage queued, audited 'interpretation.retry'; nothing is sent by the request itself.
- DECISIONS D60: a retry of a usable answer whose reading failed on this server releases nothing; its stage reads the
  stored answer again and sends nothing - from the member's door and from the console's, on a run an operator had
  reconciled too, whose record stays as the operator wrote it.
- Every refusal reaches the member in CPT Studio's own words (customer_api.KNOWN_ERRORS), naming no provider or model:
  busy, nothing to retry, already read, an unknown outcome, a paused interpreter, and an answer cut off at its output
  limit (MAX_TOKENS; C5: never a member's paid retry).
- The operator's retry may override the cut-off refusal - recorded on the audit row; the hold's state is on the console's
  session and its own endpoint, and its release is the recorded act of manage.py interpreter_hold --release.
- Every /ops/ endpoint is an unknown URL to anyone who is not an operator.

Synthetic data only, no network: the interpreter is the production adapter's Interpreter with one scripted exchange
(tests.test_pipeline_interpret.ScriptedInterpreter).
"""
import json

from django.conf import settings
from django.test import Client, override_settings

from studio import jobs, models, progress
from studio.interpretation import holds
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_pipeline_interpret import UNKNOWN, InterpretCase, answered, envelope

FAILURE = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE', 'message': 'synthetic'}}).encode()
PROVIDER_WORDS = ('gemini', 'google', 'argon')  # 'argon' alone: no customer sentence here names a coagulation
Run = models.ProviderRun


class RetryCase(InterpretCase):
    def setUp(self):
        super().setUp()
        self.member_client = Client()
        self.member_client.force_login(self.user)
        self.operator_user = f.user('operator-retry')
        ops.grant(self.operator_user)
        self.operator_client = Client()
        self.operator_client.force_login(self.operator_user)

    def retry(self, encounter, client=None):
        return (client or self.member_client).post(f'/api/encounters/{encounter.pk}/retry-reading')

    def operator_retry(self, encounter, body=None, client=None):
        return (client or self.operator_client).post(f'/ops/api/encounters/{encounter.pk}/retry-reading',
                                                     data=json.dumps(body or {}), content_type='application/json')

    def failed_reading(self, *after):
        """An encounter whose reading failed (a 503 answer: a definite failure, no hold), with ``after`` scripted for
        the attempts that follow."""
        interpreter = self.scripted(answered(FAILURE, status=503), *after)
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.FAILED)
        return interpreter, encounter, revision

    def assert_refused(self, response, sentence):
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], sentence)
        lowered = response.content.decode().lower()
        self.assertEqual([word for word in PROVIDER_WORDS if word in lowered], [])


class MemberRetryTests(RetryCase):
    def test_a_reviewer_retries_a_failed_reading_once_and_it_is_read(self):
        interpreter, encounter, revision = self.failed_reading(answered(envelope()))
        [failed] = self.interpret_runs(revision)
        self.assertEqual(progress.encounter_progress(encounter)['error']['action'], 'retry_reading')
        response = self.retry(encounter)
        self.assertEqual((response.status_code, response.json()), (201, {'retrying': True}))
        failed.refresh_from_db()
        self.assertEqual((failed.reconciled_by_id, failed.reconciliation_note), (self.user.pk, jobs.RETRY_RELEASE_NOTE))
        [queued] = models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED)
        self.assertEqual(queued.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:retry:{failed.pk}')
        [audit] = models.AuditEvent.objects.filter(event='interpretation.retry', encounter=encounter)
        self.assertEqual((audit.actor_id, audit.data['run'], audit.data['released'], audit.data['override']),
                         (self.user.pk, str(failed.pk), True, False))
        self.assertEqual(len(interpreter.sent), 1)  # the request sent nothing; the stage sends
        self.assert_refused(self.retry(encounter), jobs.RETRY_BUSY)  # its stage is queued: one at a time
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 2)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_an_owner_may_retry_and_a_viewer_may_not(self):
        _, encounter, _ = self.failed_reading()
        viewer = f.member(self.ws, f.user('viewer-retry'), role=models.Membership.VIEWER)
        client = Client()
        client.force_login(viewer)
        response = self.retry(encounter, client)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Run.objects.filter(encounter=encounter, reconciled_at__isnull=False).exists())
        owner = f.member(self.ws, f.user('owner-retry'), role=models.Membership.OWNER)
        client = Client()
        client.force_login(owner)
        self.assertEqual(self.retry(encounter, client).status_code, 201)

    def test_another_workspace_answers_not_found_and_a_get_is_not_allowed(self):
        _, encounter, _ = self.failed_reading()
        other = f.member(f.workspace('Elsewhere'), f.user('other-retry'), role=models.Membership.OWNER)
        client = Client()
        client.force_login(other)
        self.assertEqual(self.retry(encounter, client).status_code, 404)
        self.assertEqual(self.member_client.get(f'/api/encounters/{encounter.pk}/retry-reading').status_code, 405)
        self.assertFalse(Run.objects.filter(encounter=encounter, reconciled_at__isnull=False).exists())

    def test_every_refusal_is_worded_for_the_member(self):
        # nothing to retry: no attempt was made (its stage was stopped before it ran)
        encounter, revision = self.through_extract()
        self.assert_refused(self.retry(encounter), jobs.RETRY_BUSY)  # the interpret stage is queued
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        self.assert_refused(self.retry(encounter), jobs.RETRY_NOTHING)

    def test_a_read_document_is_refused(self):
        self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        self.assert_refused(self.retry(encounter), jobs.RETRY_READ)

    def test_an_unknown_outcome_is_refused_until_it_is_reconciled(self):
        self.scripted(UNKNOWN)
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        queued = list(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED))
        self.assertEqual((job.state, queued), (models.Job.SUCCEEDED, []), [(j.kind, j.state) for j in queued])
        self.assert_refused(self.retry(encounter), jobs.RETRY_UNKNOWN)

    def test_a_paused_interpreter_is_refused(self):
        _, encounter, revision = self.failed_reading()
        [failed] = self.interpret_runs(revision)
        models.InterpreterHold.objects.create(reason='quota', http_status=429, run=failed)
        self.assert_refused(self.retry(encounter), jobs.RETRY_PAUSED)
        self.assertIsNone(Run.objects.get(pk=failed.pk).reconciled_at)


class CutOffAnswerTests(RetryCase):
    """C5: an answer cut off at its output limit (MAX_TOKENS) is never a member's paid retry; the operator's override is
    recorded."""

    def setUp(self):
        super().setUp()
        self.interpreter = self.scripted(answered(envelope(finish='MAX_TOKENS')), answered(envelope()))
        self.encounter, self.revision = self.through_extract()
        self.assertEqual(self.run_next('interpret').state, models.Job.FAILED)

    def test_the_member_is_told_the_document_is_too_long_and_nothing_is_released(self):
        self.assert_refused(self.retry(self.encounter), jobs.RETRY_TOO_LONG)
        [run] = self.interpret_runs(self.revision)
        self.assertIsNone(run.reconciled_at)
        self.assertEqual(progress.encounter_progress(self.encounter)['error']['action'], 'new_document')

    def test_an_operator_is_refused_too_unless_the_override_is_asked_and_it_is_recorded(self):
        response = self.operator_retry(self.encounter)
        self.assertEqual((response.status_code, response.json()['error']), (409, jobs.RETRY_TOO_LONG))
        self.assertEqual(self.operator_retry(self.encounter, {'override': 'yes'}).status_code, 400)
        response = self.operator_retry(self.encounter, {'override': True})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['retrying'], response.json()['override']), (True, True))
        [audit] = models.AuditEvent.objects.filter(event='interpretation.retry', encounter=self.encounter)
        self.assertEqual((audit.actor_id, audit.data['override'], audit.data['effect']),
                         (self.operator_user.pk, True, holds.TOO_LONG))
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(self.interpreter.sent), 2)


class OperatorConsoleTests(RetryCase):
    def test_every_operator_endpoint_is_an_unknown_url_to_a_member(self):
        _, encounter, _ = self.failed_reading()
        body = json.dumps({'note': 'x' * 20, 'override': True})
        for url, call in ((f'/ops/api/encounters/{encounter.pk}/retry-reading', 'post'), ('/ops/api/interpreter', 'get'),
                          ('/ops/api/interpreter', 'post')):
            with self.subTest(url=url, method=call):
                response = (self.member_client.get(url) if call == 'get'
                            else self.member_client.post(url, data=body, content_type='application/json'))
                self.assertEqual(response.status_code, 404)
        self.assertFalse(Run.objects.filter(encounter=encounter, reconciled_at__isnull=False).exists())

    def test_the_operator_retries_a_failed_reading(self):
        _, encounter, revision = self.failed_reading()
        response = self.operator_retry(encounter)
        self.assertEqual(response.status_code, 201, response.content)
        [failed] = self.interpret_runs(revision)
        self.assertEqual(Run.objects.get(pk=failed.pk).reconciled_by_id, self.operator_user.pk)

    def test_the_hold_is_on_the_console_and_its_release_is_recorded(self):
        _, encounter, revision = self.failed_reading()
        [failed] = self.interpret_runs(revision)
        hold = models.InterpreterHold.objects.create(reason='quota', http_status=429, run=failed)
        session = self.operator_client.get('/ops/api/session').json()
        self.assertEqual((session['interpreter']['held'], [item['id'] for item in session['interpreter']['standing']]),
                         (True, [str(hold.pk)]))
        state = self.operator_client.get('/ops/api/interpreter').json()
        self.assertTrue(state['held'])
        response = self.operator_client.post('/ops/api/interpreter', data=json.dumps({'note': '  '}),
                                             content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.InterpreterHoldRelease.objects.exists())
        response = self.operator_client.post('/ops/api/interpreter',
                                             data=json.dumps({'note': 'Synthetic: the quota was raised for the test.'}),
                                             content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['released'], response.json()['held']), ([str(hold.pk)], False))
        [release] = models.InterpreterHoldRelease.objects.all()
        self.assertEqual((release.hold_id, release.released_by_id, release.note),
                         (hold.pk, self.operator_user.pk, 'Synthetic: the quota was raised for the test.'))
        self.assertFalse(self.operator_client.get('/ops/api/interpreter').json()['held'])
        # the member may retry now the hold is released
        self.assertEqual(self.retry(encounter).status_code, 201)


class UnreadAnswerRetryTests(RetryCase):
    """DECISIONS D60 (the round-2 refutation, finding 15): the retry door on a usable answer whose reading failed on
    this server - the reading child overran (a genuine bounded.Overrun: no reading time for that stage only) - releases
    nothing, so its stage reads the stored answer again: one send in all."""

    NOTE = 'Synthetic operator note: the vendor console shows one answered request (D60 pin).'

    def no_reading_time(self):
        return override_settings(JOB_DEADLINE_SECONDS={**settings.JOB_DEADLINE_SECONDS, 'analyze': 0})

    def test_d60_a_members_retry_of_an_answer_whose_reading_overran_sends_nothing(self):
        interpreter = self.scripted(answered(envelope()), answered(envelope()))
        encounter, revision = self.through_extract()
        with self.no_reading_time():
            self.assertEqual(self.run_next('interpret').state, models.Job.FAILED)
        [run] = self.interpret_runs(revision)
        response = self.retry(encounter)
        self.assertEqual((response.status_code, response.json()), (201, {'retrying': True}))
        [queued] = models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED)
        self.assertEqual(queued.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:retry:{run.pk}')
        [audit] = models.AuditEvent.objects.filter(event='interpretation.retry', encounter=encounter)
        self.assertEqual((audit.data['run'], audit.data['released'], audit.data['effect']),
                         (str(run.pk), False, holds.ANSWERED))
        self.assertIsNone(Run.objects.get(pk=run.pk).reconciled_at)
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.result['provider']), (models.Job.SUCCEEDED, 'reused'), job.error)
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_d60_an_operators_retry_of_a_reconciled_answer_whose_reading_overran_sends_nothing(self):
        """Finding 15 on D52's own path: an unknown outcome holding a usable answer, reconciled by an operator; the
        reconciliation's stage settles it from its exchange (P-6) and its reading overruns. The console's retry keeps
        the operator's record, releases nothing, and its stage reads the stored answer again: nothing is sent."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        run = self.unknown_holding_an_answer(encounter, revision)
        self.assertTrue(jobs.reconcile(encounter, run, self.operator_user, self.NOTE))
        with self.no_reading_time():
            self.assertEqual(self.run_next('interpret').state, models.Job.FAILED)
        run.refresh_from_db()
        recorded = (run.reconciled_by_id, run.reconciled_at, run.reconciliation_note)
        self.assertEqual((run.state, recorded[0], recorded[2]), ('succeeded', self.operator_user.pk, self.NOTE))
        self.assertEqual(jobs.retry_target(revision), (run, None))
        response = self.operator_retry(encounter)
        self.assertEqual(response.status_code, 201, response.content)
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciled_at, run.reconciliation_note), recorded)
        [queued] = models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED)
        self.assertEqual(queued.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:retry:{run.pk}')
        self.assertFalse(jobs.released_for_retry(run))
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.result['provider']), (models.Job.SUCCEEDED, 'reused'), job.error)
        self.assertEqual(interpreter.sent, [])
