"""Round r3's build, the repair after the mandatory adversarial pass over int4 (DECISIONS D324 (10) and its addendum),
lane 'pipe': the two class rules the pipeline's L7 findings were ruled under, each pinned by the finding's own input
first (ported from the verifiers' reproductions), then by other members of its class and by its boundary. TEXT-ONLY and
SYNTHETIC: every document is test_jobs' POLYP or test_question_stage's THREE note (fictional clinicians, no real
patient), driven through the question stage's own scaffolding (test_question_stage.QuestionCase: the production Fable
connector, fable_adapter.InterpreterF, its one exchange scripted). NOTHING is sent to any provider: the network
triggers run the connector's own participants/http.post against a CLOSED local port, against a session whose post
raises what requests raises for a failed name resolution (no I/O), against a deadline already passed and against a
session factory that raises; the credentials trigger runs the LIVE FableInterpreter._exchange with a credentials path
that does not exist (nothing is ever opened) and a session factory that refuses to be called.

L7-A1-BUDGET-UNBOUNDED (D324 (10)). Every run the month's spend counts is bounded by its own reservation or its worst
case, participant runs included (jobs._run_cost: the Fable participant's tool loop is bounded from its own record,
jobs._participant_worst_usd), so ONE unpriced participant run never makes the whole month unbounded
(jobs.account_month_spend). And a cost-door refusal that says nothing about a request leaves it owed: what refuses the
round is the month - its recorded spend, the operator's other spend, or a month that cannot be bounded - and the same
round would be admitted in another month, so the requests stay owed and the stage ends resumable (Resume), queueing
nothing. Only a refusal about the round itself decides it ('refused', DESIGN-v2 e.8): a request whose own worst case
cannot be bounded, or worst cases that together pass the threshold by themselves.

L7-A2-NOTSENT-DECIDES (D324 (10) and its addendum). An outcome that says nothing about the request decides nothing:
nothing left this server because of its credentials, the network or a deadline that passed before the send
(participants/http.Unsent, carried by the connector's not_sent and recorded on the run). The request stays owed and the
stage ends resumable, as PIPE-R1 ends on an installation-wide hold: CANCELLED, nothing written, NOTHING queued - never
an automatic retry, so a persistent failure (a missing credentials file) ends after one attempt per member's Resume. A
not_sent the request itself causes (a body over the connector's size limit) or that carries no cause (a replay with no
recording of the request) still decides, as before."""
from __future__ import annotations

import hashlib
import os
import socket
import tempfile
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from urllib3.exceptions import MaxRetryError, NewConnectionError

from studio import jobs, models, review
from studio.interpretation import fable_adapter
from studio.interpretation.engine import asking
from studio.interpretation.replay import ReplayInterpreterF
from studio.participants import anthropic_fable, http, pricing
from studio.providers.base import canonical_body
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.test_harness_pipeline import BOTH, HarnessCase
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE
from tests.v2 import test_jobs as TJ
from tests.v2 import test_question_stage as TQ
from tests.v2.test_question_stage import (QUESTION, SESSION_E2, SESSION_E3, SESSION_E4, THREE, QuestionCase,
                                          question_answer)

Run, Job = models.ProviderRun, models.Job
OWNER = dict(QUESTION_PROVIDER_CAP_USD='200', QUESTION_SITE_RESERVE_USD='40', QUESTION_OTHER_SPEND_USD='30')
HUGE = dict(QUESTION_PROVIDER_CAP_USD='100000', QUESTION_SITE_RESERVE_USD='40', QUESTION_OTHER_SPEND_USD='0')
NO_CAP = dict(QUESTION_PROVIDER_CAP_USD='')
UNREACHABLE = 'Anthropic could not be reached (ConnectionError); nothing was sent.'
DEADLINE_PASSED = 'The deadline passed before the request was sent; nothing was sent.'
PARTICIPANT_MODEL = anthropic_fable.MODEL  # claude-fable-5-1, the Fable participant's
RECONCILE = 'Synthetic reconciliation: the vendor console was checked for this request.'
_CREDENTIALS_DIR = tempfile.mkdtemp(prefix='r3c-pipe-credentials-')  # empty: the path below is never created
MISSING_CREDENTIALS = os.path.join(_CREDENTIALS_DIR, 'no-such-credentials-file.env')


# --- the network, credentials and deadline triggers: the connector's own code, nothing sent ---------------------------


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _data(question):
    body = question.request.body if question is not None else {'model': fable_adapter.MODEL}
    return http.sendable(body, fable_adapter.DEFAULT_MAX_REQUEST_BYTES, with_original=False)


def _post(session_factory, url, question, *, deadline):
    return http.post(fable_adapter.VENDOR, session_factory, url, _data(question), {'content-type': 'application/json'},
                     deadline=deadline, connect_timeout=5, read_timeout=5, max_response_bytes=1_000_000,
                     requested_model=fable_adapter.MODEL)


def connect_refused(sha=None, question=None):
    """The connector's OWN POST (the production default_session, its watched adapter) to a CLOSED local port: a real
    ECONNREFUSED, the watch's never-connected branch."""
    return _post(http.default_session, f'http://127.0.0.1:{_closed_port()}/v1/messages', question,
                 deadline=time.monotonic() + 30)


class _DnsBlipSession(requests.Session):
    def post(self, url, *args, **kwargs):  # no I/O: what requests raises when the name does not resolve
        reason = NewConnectionError(None, 'Failed to establish a new connection: [Errno -3] Temporary failure in '
                                          'name resolution')
        raise requests.exceptions.ConnectionError(MaxRetryError(None, url, reason=reason))


def dns_blip(sha=None, question=None):
    return _post(_DnsBlipSession, 'http://127.0.0.1:9/v1/messages', question, deadline=time.monotonic() + 30)


def deadline_passed(sha=None, question=None):
    """The connector's POST given a deadline that passed before the request could be written."""
    return _post(http.default_session, f'http://127.0.0.1:{_closed_port()}/v1/messages', question,
                 deadline=time.monotonic() - 1)


def _no_session():
    raise OSError('synthetic: no HTTP session can be created on this server')


def no_session(sha=None, question=None):
    return _post(_no_session, 'http://127.0.0.1:9/v1/messages', question, deadline=time.monotonic() + 30)


SESSIONS_CREATED = []


def _refuse_session():
    SESSIONS_CREATED.append('session')
    raise AssertionError('no session may be created: the credentials could not be read')


def credentials_missing(sha=None, question=None):
    """The LIVE interpreter's own _exchange, its credentials file missing at send time (the path is never created) and
    its session factory refusing to be called."""
    assert not os.path.exists(MISSING_CREDENTIALS)
    live = fable_adapter.FableInterpreter(MISSING_CREDENTIALS, session_factory=_refuse_session)
    body = question.request.body if question is not None else None
    return live._exchange(body, time.monotonic() + 30, fable_adapter.APPRAISAL)


def over_size(sha=None, question=None):
    """BOUNDARY: the LIVE interpreter's own _exchange refusing the request ITSELF (its body over the connector's size
    limit) - a not_sent about the request, which decides it."""
    live = fable_adapter.FableInterpreter(MISSING_CREDENTIALS, session_factory=_refuse_session, max_request_bytes=64)
    return live._exchange(question.request.body, time.monotonic() + 30, fable_adapter.APPRAISAL)


def no_recording(sha=None, question=None):
    """BOUNDARY: the replay interpreter's own refusal of a request it holds no recording of - a not_sent that names no
    cause of this server's, which decides its request as before (DESIGN-v2 e.5)."""
    folder = tempfile.mkdtemp(prefix='r3c-pipe-replay-')
    os.makedirs(os.path.join(folder, 'anthropic'))
    return ReplayInterpreterF(folder).recorded(sha or '0' * 64)


def _one_question_each():
    return mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                             TQ.ConcurrencyTests.partition(specs, pool, round_))  # not imported: collected twice


class _Base(QuestionCase):
    def inventory(self, revision):
        return models.EventInventory.objects.filter(revision=revision).first()

    def queued(self, encounter):
        return list(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)))

    def round_of_three(self, scripts):
        """THREE read through pass 2 with E2-E4's sessions left open: round 1's three requests (one question each)."""
        return self.to_questions(SESSION_E2, SESSION_E3, SESSION_E4, text=THREE, question_script=list(scripts))

    def assert_owed_and_resumable(self, encounter, revision, done, message, *, runs=None):
        """The class rule's ending: the stage CANCELLED with ``message`` (resumable), every not-sent run of the round
        deciding nothing (its request still owed), no row written, NOTHING queued, the document 'stopped' with
        Resume."""
        self.assertEqual((done.state, done.error), (Job.CANCELLED, message), done.result)
        for run in runs if runs is not None else self.question_runs(encounter):
            if run.state == Run.NOT_SENT:
                self.assertIsNone(jobs._question_outcome(run), (run.error, run.scope))
        self.assertIsNone(self.inventory(revision))
        self.assertEqual(self.queued(encounter), [])
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertTrue(review.can_resume(encounter))

    def assert_decided(self, revision, reason):
        inventory = self.inventory(revision)
        self.assertIsNotNone(inventory)
        self.assertEqual({tuple(item['reasons']) for item in inventory.events['questions']}, {(reason,)})
        return inventory


# --- L7-A2: an outcome that says nothing about the request decides nothing -------------------------------------------


class NotSentFindingTests(_Base):
    """The finding's own input (the verifier's reproduction, test_verify_l7a2): a round of THREE question requests, one
    question each, every send answered not_sent by the connector for the network (a connect refused, a DNS failure) or
    the credentials (the file missing at send time). On int4 all three were decided 'not_sent' for good: the row was
    written, 45385 held, and no Resume, retry or sweep ever asked them again."""

    def owed_then_resumed(self, script):
        with _one_question_each():
            encounter, revision, queued = self.round_of_three([script] * 3)
            done = self.run_next(QUESTION)
            self.assertEqual(len(self.interpreter.question_sent), 3)
            self.assert_owed_and_resumable(encounter, revision, done, jobs.INTERPRET_NOT_SENT_MESSAGE)
            self.interpreter.question_script = []  # the network or the credentials fixed: the connector answers
            self.assertIsNotNone(jobs.resume(encounter, self.user))
            self.finish(encounter)
        sent = self.interpreter.question_sent
        self.assertEqual(len(sent), 6)  # each of the three requests sent again, once
        self.assertEqual(sorted(sent[:3]), sorted(sent[3:]))  # ... the identical requests
        inventory = self.inventory(revision)
        self.assertEqual([item['outcome'] for item in inventory.verification['question_runs']], ['answered'] * 3)
        self.assertEqual({item['result'] for item in inventory.events['questions']}, {'supported'})
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a2_the_findings_input_a_connect_refused_round_of_three_stays_owed_and_a_resume_sends_it(self):
        self.owed_then_resumed(connect_refused)

    def test_a2_the_findings_input_a_dns_failure_round_of_three_stays_owed_and_a_resume_sends_it(self):
        self.owed_then_resumed(dns_blip)

    def test_a2_the_findings_input_a_credentials_file_missing_at_send_time_stays_owed(self):
        SESSIONS_CREATED.clear()
        self.owed_then_resumed(credentials_missing)
        self.assertEqual(SESSIONS_CREATED, [])  # nothing was ever about to be sent


class NotSentClassTests(_Base):
    """The class beyond the finding's own input: every trigger D324 names (the deadline before the send too), one
    request or several, a mixed round, a persistent failure - and never an automatic retry."""

    def one_request(self, *scripts):
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=list(scripts))
        return encounter, revision, self.run_next(QUESTION)

    def test_a2_a_deadline_that_passed_before_the_send_leaves_the_request_owed(self):
        encounter, revision, done = self.one_request(deadline_passed)
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.sent, run.error), (Run.NOT_SENT, False, DEADLINE_PASSED))
        self.assert_owed_and_resumable(encounter, revision, done, jobs.INTERPRET_NOT_SENT_MESSAGE)
        self.interpreter.question_script = []
        jobs.resume(encounter, self.user)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a2_no_http_session_on_this_server_leaves_the_request_owed(self):
        encounter, revision, done = self.one_request(no_session)
        [run] = self.question_runs(encounter)
        self.assertTrue(run.error.startswith('No HTTP session could be created'), run.error)
        self.assert_owed_and_resumable(encounter, revision, done, jobs.INTERPRET_NOT_SENT_MESSAGE)

    def test_a2_in_a_mixed_round_only_the_unsent_request_is_sent_again(self):
        """A round of three: one answered, one HTTP 500 (a definite failure, which decides), one never sent for the
        network. The stage records all three and ends resumable; a Resume sends ONLY the unsent one, once."""
        def failing(sha, question):
            return TJ.answered(TJ.HTTP_500, status=500)

        def answering(sha, question):
            return TJ.answered(TJ.body(question_answer(question, question.request.contexts[0])))
        with _one_question_each():
            encounter, revision, queued = self.round_of_three([answering, failing, dns_blip])
            done = self.run_next(QUESTION)
            self.assert_owed_and_resumable(encounter, revision, done, jobs.INTERPRET_NOT_SENT_MESSAGE)
            first = list(self.interpreter.question_sent)
            self.interpreter.question_script = []
            jobs.resume(encounter, self.user)
            self.finish(encounter)
        again = self.interpreter.question_sent[3:]
        self.assertEqual(again, [first[2]])  # the unsent request alone, the identical request, once
        inventory = self.inventory(revision)
        self.assertEqual(sorted(item['outcome'] for item in inventory.verification['question_runs']),
                         ['answered', 'answered', 'failed'])
        self.assertEqual(sorted((item['result'], tuple(item['reasons'])) for item in inventory.events['questions']),
                         [('supported', ()), ('supported', ()), ('unresolved', ('question_request_failed:failed',))])

    def test_a2_a_persistent_failure_is_never_retried_automatically(self):
        """The addendum's caution: deciding nothing is not enough - the stage must end and queue nothing, or it would
        send again at once, every wave. A credentials file that stays missing: the worker drains to nothing after ONE
        attempt of each request, and each member's Resume makes exactly one more."""
        with _one_question_each():
            encounter, revision, queued = self.round_of_three([credentials_missing] * 12)
            ran = []
            for _ in range(6):  # a bounded drain: an automatic retry would show as more question jobs sent
                job = jobs.claim_next()
                if job is None:
                    break
                ran.append(jobs.run_job(job).kind)
            self.assertEqual(ran, [QUESTION])
            self.assertEqual(len(self.interpreter.question_sent), 3)
            self.assertEqual(self.queued(encounter), [])
            for resumes in (1, 2):
                self.assertIsNotNone(jobs.resume(encounter, self.user))
                self.finish(encounter)
                self.assertEqual(len(self.interpreter.question_sent), 3 * (resumes + 1))
                self.assertEqual(self.state(encounter), 'stopped')
                self.assertEqual(self.queued(encounter), [])
        self.assertIsNone(self.inventory(revision))

    def test_a2_boundary_a_request_the_connector_refuses_itself_still_decides_not_sent(self):
        """BOUNDARY (left alone): the live connector refusing the request ITSELF (its body over the size limit) - the
        identical request would be refused again whenever it is sent - decides it, as on int4: the row is written and
        the question unresolved (question_request_failed:not_sent)."""
        encounter, revision, done = self.one_request(over_size)
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, jobs._question_outcome(run)), (Run.NOT_SENT, 'not_sent'))
        self.finish(encounter)
        self.assert_decided(revision, 'question_request_failed:not_sent')
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a2_boundary_a_not_sent_naming_no_cause_of_this_server_still_decides(self):
        """BOUNDARY (left alone): the replay interpreter's own not_sent for a request it holds no recording of names no
        credentials, network or deadline cause: it decides its request as before (DESIGN-v2 e.5)."""
        encounter, revision, done = self.one_request(no_recording)
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        [run] = self.question_runs(encounter)
        self.assertEqual(jobs._question_outcome(run), 'not_sent')
        self.finish(encounter)
        self.assert_decided(revision, 'question_request_failed:not_sent')


class NotSentRecordingTests(_Base):
    """A not_sent whose record could not be written whole (decision (k): _settle_unrecorded writes only small fields)
    keeps its cause in that same write, and the stage reads the run as recorded: the request stays owed and the stage
    ends resumable, exactly as when the outcome was recorded whole - never one automatic resend through a stale copy."""

    def test_a2_a_not_sent_whose_record_could_not_be_written_whole_stays_owed(self):
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=[dns_blip])
        real = jobs._finish_loop

        def failing(run, outcome):
            if 'question' in (run.scope or {}):
                raise RuntimeError('synthetic: the outcome could not be recorded whole')
            return real(run, outcome)
        with mock.patch.object(jobs, '_finish_loop', side_effect=failing):
            done = self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.sent), (Run.NOT_SENT, False))
        self.assertEqual(run.error, 'Nothing was sent; its record could not be written (logged).')
        self.assertEqual((run.scope or {}).get(jobs.QUESTION_UNSENT), http.Unsent.NETWORK.value)
        self.assert_owed_and_resumable(encounter, revision, done, jobs.INTERPRET_NOT_SENT_MESSAGE)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.interpreter.question_script = []
        jobs.resume(encounter, self.user)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertEqual(self.status(encounter, '45385'), 'ready')


class UnsentCauseTests(SimpleTestCase):
    """The connector's half: each trigger's not_sent carries its cause (http.Unsent), its words unchanged; a request
    the connector refuses itself, and anything that may have left, carries none; the one-exchange loop keeps the cause
    on its final (participants/loop.py rebuilds that final from the exchange's fields)."""

    def test_each_trigger_names_its_cause_and_keeps_its_words(self):
        for name, exchange, cause, words in (
                ('connect refused', connect_refused(), http.Unsent.NETWORK, UNREACHABLE),
                ('dns', dns_blip(), http.Unsent.NETWORK, UNREACHABLE),
                ('deadline', deadline_passed(), http.Unsent.DEADLINE, DEADLINE_PASSED),
                ('no session', no_session(), http.Unsent.NETWORK,
                 'No HTTP session could be created (OSError); nothing was sent.')):
            with self.subTest(name=name):
                self.assertEqual((exchange.outcome, exchange.sent, exchange.error), ('not_sent', False, words))
                self.assertIs(http.unsent_cause(exchange), cause)

    def test_the_credentials_trigger_names_credentials_and_a_request_refused_itself_names_none(self):
        refused = fable_adapter.FableInterpreter(MISSING_CREDENTIALS, session_factory=_refuse_session)
        body = {'model': fable_adapter.MODEL}
        exchange = refused._exchange(body, time.monotonic() + 30, fable_adapter.APPRAISAL)  # not a body it builds
        self.assertEqual(exchange.outcome, 'not_sent')
        self.assertIsNone(http.unsent_cause(exchange))
        self.assertIsNone(http.unsent_cause(http.not_sent('Some refusal; nothing was sent.')))
        self.assertIsNone(http.unsent_cause(TJ.UNKNOWN))
        self.assertIsNone(http.unsent_cause(TJ.answered(TJ.HTTP_500, status=500)))

    def test_a_question_request_refused_for_its_credentials_carries_the_cause_through_the_loop(self):
        built = _built_question()
        live = fable_adapter.FableInterpreter(MISSING_CREDENTIALS, session_factory=_refuse_session)
        outcome = live.send_loop(built.request, deadline_s=30, client_request_id='synthetic',
                                 execute_tool=lambda *args: ({}, ()), should_stop=None)
        self.assertEqual((outcome.final.outcome, outcome.final.sent), ('not_sent', False))
        self.assertEqual(outcome.final.error, 'The Anthropic credentials file does not exist. No request was sent.')
        self.assertIs(http.unsent_cause(outcome.final), http.Unsent.CREDENTIALS)
        self.assertEqual(len(outcome.exchanges), 1)

    def test_a_request_the_loop_refuses_before_any_exchange_carries_no_cause(self):
        built = _built_question()
        live = fable_adapter.FableInterpreter(MISSING_CREDENTIALS, session_factory=_refuse_session)
        outcome = live.send_loop(built.request, deadline_s=0, client_request_id='synthetic',
                                 execute_tool=lambda *args: ({}, ()), should_stop=None)  # an invalid deadline
        self.assertEqual(outcome.final.outcome, 'not_sent')
        self.assertIsNone(http.unsent_cause(outcome.final))


def _built_question():
    """A question request the production builder makes (test_question_stage's AdapterTests' way: test_r3_probe's
    stub_request over one Q-REL spec), its body of the question kind."""
    from tests.v2.test_r3_probe import REL, stub_request

    return stub_request([REL])


# --- L7-A1: every run the month counts is bounded; a refusal about the month leaves the request owed ------------------


def _participant_run(encounter, revision, *, state, body=None, sent=True, model=PARTICIPANT_MODEL, usage=None,
                     reconciled=False, started=True, created_at=None, provider=anthropic_fable.NAME,
                     http_status=None):
    """A Fable PARTICIPANT run of the account (provider 'fable', purpose independent), the shape the real loop records
    (jobs._send, _finish_loop): ``state`` its outcome, ``body`` its stored first request."""
    now = timezone.now()
    body = body if body is not None else {'model': model, 'max_tokens': anthropic_fable.MAX_TOKENS,
                                          'messages': [{'role': 'user', 'content': 'Synthetic note text.'}]}
    run = Run.objects.create(
        encounter=encounter, revision=revision, provider=provider, adapter_version=anthropic_fable.ADAPTER_VERSION,
        request_sha256=hashlib.sha256(canonical_body(body)).hexdigest(), request_body=body, contexts=[], state=state,
        sent=sent, http_status=http_status, usage=usage or {}, purpose=Run.INDEPENDENT, requested_model=model,
        endpoint=anthropic_fable.ENDPOINT, error='synthetic participant outcome',
        started_at=now if started else None, finished_at=now if state not in (Run.RESERVED, Run.SENDING) else None,
        reconciled_at=now if reconciled else None)
    if created_at is not None:
        Run.objects.filter(pk=run.pk).update(created_at=created_at)
        run.refresh_from_db()
    return run


def _exchange(run, turn, *, state, body, usage=None, response=b'', http_status=None, calls=()):
    exchange = models.ProviderExchange.objects.create(
        run=run, turn=turn, request_body=body, request_sha256=hashlib.sha256(canonical_body(body)).hexdigest(),
        state=state, http_status=http_status, response_bytes=response,
        response_sha256=hashlib.sha256(response).hexdigest() if response else '', usage=usage or {})
    for call_id, result in calls:
        encoded = canonical_body(result)
        models.ToolCall.objects.create(exchange=exchange, call_id=call_id, tool='cms_lookup', arguments={},
                                       result=result, result_sha256=hashlib.sha256(encoded).hexdigest(),
                                       executed_at=timezone.now())
    return exchange


def _usd(model, usage):
    return Decimal(pricing.estimate(model, usage)['estimated_usd'])


def _worst(tokens, out=anthropic_fable.MAX_TOKENS, model=PARTICIPANT_MODEL):
    """One exchange at its worst (the rule, computed here independently): one input token per byte plus the turn's
    margin, the body's max_tokens as output, at the model's rates."""
    return _usd(model, {'input_tokens': tokens + fable_adapter.PROMPT_MARGIN_TOKENS, 'output_tokens': out})


class _CostCase(_Base):
    def other(self, title='Synthetic other note'):
        encounter = models.Encounter.objects.create(workspace=self.ws, title=title, created_by=self.user)
        return encounter, f.pasted_revision(encounter, self.user, TJ.NOTE, extract=False)

    def fable_unknown(self, encounter, revision):
        """The verifier's V2 shape: one Fable participant run of the month, a read timeout after the request left
        (provider 'fable', purpose independent, UNKNOWN, sent, no status, no usage, no question scope, no exchange)."""
        return _participant_run(encounter, revision, state=Run.UNKNOWN,
                                body={'model': anthropic_fable.MODEL, 'max_tokens': anthropic_fable.MAX_TOKENS})

    def one_document(self, settings_, keys=(SESSION_E2,)):
        encounter, revision, queued = self.to_questions(*keys)
        with override_settings(**settings_):
            done = self.run_next(QUESTION)
        return encounter, revision, done


class BudgetFindingTests(_CostCase):
    """The finding's own input (the attacker's BudgetUnboundedTests / BudgetUnboundedOwnerFiguresTests and the
    verifier's V2b): with a threshold configured, ONE Fable participant run of the month recorded UNKNOWN (and
    reconciled) made account_month_spend None, so EVERY question round of the installation was refused for the rest of
    the month and each request decided 'refused' for good - while the month's priced spend was a few dollars."""

    def test_a1_the_findings_input_owner_figures_the_round_is_sent(self):
        other, other_revision = self.other()
        participant = self.fable_unknown(other, other_revision)
        self.assertTrue(jobs.reconcile(other, participant, self.user, RECONCILE))
        spent = jobs.account_month_spend()
        self.assertIsInstance(spent, Decimal)  # bounded: never None for the whole month
        self.assertEqual(jobs._run_cost(participant), _worst(len(canonical_body(participant.request_body))))
        encounter, revision, done = self.one_document(OWNER)
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.finish(encounter)
        self.assertEqual(self.status(encounter, '45385'), 'ready')
        with override_settings(**OWNER):
            self.assertEqual(jobs._question_budget_refusal(['5.226488']), '')  # every later round of the month too

    def test_a1_the_findings_input_a_huge_threshold_the_round_is_sent(self):
        other, other_revision = self.other()
        self.fable_unknown(other, other_revision)
        encounter, revision, done = self.one_document(HUGE)
        self.assertEqual(len(self.interpreter.question_sent), 1, (done.state, done.error))
        self.finish(encounter)
        self.assertEqual(self.status(encounter, '45385'), 'ready')


@applied
@override_settings(**LIVE, **BOTH)
class BudgetParticipantPathTests(OperatorReads, HarnessCase):
    """The verifier's V1, the REAL participant path (test_harness_pipeline's in-process fakes, jobs._send and
    _finish_loop): a Fable participant tool loop whose one exchange is a read timeout after the request left is
    bounded by its own record, before and after a real reconciliation, and the owner's figures refuse nothing."""

    def test_a1_a_fable_read_timeout_is_bounded_by_its_own_record(self):
        self.adapters['fable'].outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        [unknown] = [run for run in self.runs_of(encounter_id, 'fable') if run.purpose == Run.INDEPENDENT]
        self.assertEqual((unknown.state, unknown.sent), (Run.UNKNOWN, True))
        cost = jobs._run_cost(unknown)
        self.assertIsInstance(cost, Decimal)
        self.assertGreater(cost, Decimal('0'))
        self.assertIsInstance(jobs.account_month_spend(), Decimal)
        with override_settings(**OWNER):
            self.assertEqual(jobs._question_budget_refusal(['5.226488']), '')
        response = self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(unknown.pk), 'note': RECONCILE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        unknown.refresh_from_db()
        self.assertEqual(jobs._run_cost(unknown), cost)
        with override_settings(**OWNER):
            self.assertEqual(jobs._question_budget_refusal(['5.226488']), '')


class ParticipantBoundTests(_CostCase):
    """The rule's other members: a participant run is bounded by its OWN record in every state the account can hold it
    in - each recorded exchange at its reported usage or at the worst its own body can draw, an exchange the loop may
    have sent with no record of it at the worst of the body it would carry, a PDF original at its expanded size - and
    the month is a Decimal for every such run."""

    def setUp(self):
        super().setUp()
        self.encounter, self.revision = self.other()
        self.body1 = {'model': PARTICIPANT_MODEL, 'max_tokens': anthropic_fable.MAX_TOKENS,
                      'messages': [{'role': 'user', 'content': 'Synthetic note: a cold snare polypectomy.'}]}
        self.body2 = {**self.body1, 'messages': [*self.body1['messages'], {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': 'toolu_1', 'name': 'cms_lookup', 'input': {'code': '45385'}}]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'toolu_1', 'content': '{"ok":1}'}]}]}
        self.usage1 = {'input_tokens': 1200, 'output_tokens': 300}
        self.response1 = b'{"type":"message","model":"claude-fable-5-1","stop_reason":"tool_use","content":[]}'

    def test_a1_unknown_after_a_tool_turn_prices_the_answered_exchange_and_bounds_the_unknown_one(self):
        run = _participant_run(self.encounter, self.revision, state=Run.UNKNOWN, body=self.body1)
        _exchange(run, 1, state='succeeded', body=self.body1, usage=self.usage1, response=self.response1,
                  http_status=200, calls=[('toolu_1', {'ok': 1})])
        _exchange(run, 2, state='unknown', body=self.body2)
        expected = _usd(PARTICIPANT_MODEL, self.usage1) + _worst(len(canonical_body(self.body2)))
        self.assertEqual(jobs._run_cost(run), expected)

    def test_a1_a_loop_left_in_flight_after_a_tool_turn_bounds_the_exchange_it_holds_no_record_of(self):
        """A worker that died mid-loop (SENDING; the sweep would record it unknown): exchange 1 answered, asking for a
        tool; exchange 2 in flight with no record. Exchange 2 is bounded by the body it would carry: exchange 1's body
        grown by exchange 1's answer and the tool results it carried, each result with its frame."""
        for state in (Run.SENDING, Run.UNKNOWN):
            with self.subTest(state=state):
                run = _participant_run(self.encounter, self.revision, state=state, body=self.body1)
                _exchange(run, 1, state='succeeded', body=self.body1, usage=self.usage1, response=self.response1,
                          http_status=200, calls=[('toolu_1', {'ok': 1}), ('toolu_2', {'codes': ['45385']})])
                grown = (len(canonical_body(self.body1)) + len(self.response1) + jobs.FOLLOW_UP_FRAME_BYTES
                         + sum(len(canonical_body(result)) + len(call_id) + jobs.FOLLOW_UP_FRAME_BYTES
                               for call_id, result in (('toolu_1', {'ok': 1}), ('toolu_2', {'codes': ['45385']}))))
                expected = _usd(PARTICIPANT_MODEL, self.usage1) + _worst(grown)
                self.assertEqual(jobs._run_cost(run), expected)

    def test_a1_a_run_with_no_exchange_recorded_is_bounded_by_its_own_request(self):
        for state in (Run.RESERVED, Run.SENDING, Run.UNKNOWN):
            with self.subTest(state=state):
                run = _participant_run(self.encounter, self.revision, state=state, body=self.body1,
                                       sent=state != Run.RESERVED)
                self.assertEqual(jobs._run_cost(run), _worst(len(canonical_body(self.body1))))

    def test_a1_an_answer_the_table_cannot_price_is_bounded_by_its_exchanges(self):
        """A SUCCEEDED run whose reported usage states no usage the table prices (no output count): each exchange at the
        worst its own body can draw - never None."""
        unpriced = {'input_tokens': 1200}
        run = _participant_run(self.encounter, self.revision, state=Run.SUCCEEDED, body=self.body1, usage=unpriced,
                               http_status=200)
        _exchange(run, 1, state='succeeded', body=self.body1, usage=unpriced, response=self.response1,
                  http_status=200)
        self.assertEqual(jobs._run_cost(run), _worst(len(canonical_body(self.body1))))

    def test_a1_a_pdf_original_is_counted_at_its_expanded_size(self):
        holder = http.placeholder({'sha256': 'a' * 64, 'bytes': 30_000})
        body = {**self.body1, 'messages': [{'role': 'user', 'content': [
            {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': holder}}]}]}
        run = _participant_run(self.encounter, self.revision, state=Run.UNKNOWN, body=body)
        expanded = http.expanded_length(len(canonical_body(body)), holder, '')
        self.assertGreater(expanded, 40_000)
        self.assertEqual(http.sent_length(body), expanded)
        self.assertEqual(jobs._run_cost(run), _worst(expanded))

    def test_a1_an_exchange_answered_with_an_error_body_adds_nothing(self):
        """A failed exchange with an error body and no usage generated nothing (as _run_cost reads a failed run): it
        adds 0, the unknown one its bound (the arithmetic of each exchange, on a synthetic sequence)."""
        run = _participant_run(self.encounter, self.revision, state=Run.UNKNOWN, body=self.body1)
        _exchange(run, 1, state='failed', body=self.body1, http_status=529, response=b'{"type":"error"}')
        _exchange(run, 2, state='unknown', body=self.body1)
        self.assertEqual(jobs._run_cost(run), _worst(len(canonical_body(self.body1))))

    def test_a1_every_state_of_both_account_providers_bounds_the_month(self):
        """The property D324 states: never None for the whole month - every state a participant or an interpreter run
        of the account can be recorded in gives a Decimal, so the month does too."""
        question = _built_question().request.body
        for provider, body, model in ((anthropic_fable.NAME, self.body1, PARTICIPANT_MODEL),
                                      (fable_adapter.NAME, question, fable_adapter.MODEL)):
            for state in (Run.RESERVED, Run.SENDING, Run.UNKNOWN, Run.SUCCEEDED, Run.FAILED, Run.NOT_SENT,
                          Run.CANCELLED):
                with self.subTest(provider=provider, state=state):
                    run = _participant_run(self.encounter, self.revision, state=state, body=body, model=model,
                                           provider=provider,
                                           sent=state not in (Run.RESERVED, Run.NOT_SENT, Run.CANCELLED))
                    cost = jobs._run_cost(run)
                    self.assertIsInstance(cost, Decimal)
                    if state in (Run.NOT_SENT, Run.CANCELLED):  # BOUNDARY (unchanged): a run that sent nothing
                        self.assertEqual(cost, Decimal('0'))
        self.assertIsInstance(jobs.account_month_spend(), Decimal)

    def test_a1_boundary_last_months_runs_are_not_counted(self):
        run = _participant_run(self.encounter, self.revision, state=Run.UNKNOWN, body=self.body1)
        before = jobs.account_month_spend()
        start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        Run.objects.filter(pk=run.pk).update(created_at=start - timedelta(seconds=1))
        self.assertEqual(jobs.account_month_spend(), before - jobs._run_cost(run))


class BudgetOwedTests(_CostCase):
    """The rule's second half: a cost-door refusal that says nothing about the request leaves it owed. The month - its
    recorded spend, the operator's other spend, or a month that cannot be bounded - is what refuses, while the round's
    own worst cases fit the threshold: nothing is decided, the stage ends resumable and queues nothing, and a Resume
    once the month allows it sends the round once. A refusal about the round itself still decides (the boundary)."""

    def threshold_for(self, extra):
        """The cap (site reserve 40) leaving the round's one worst case and ``extra`` dollars under the threshold."""
        [question] = self.built.values()
        worst = Decimal(fable_adapter.worst_case_usd(question.request))
        return str(Decimal('40') + worst + Decimal(extra)), worst

    def test_a1_a_refusal_the_other_spend_causes_leaves_the_round_owed_and_a_resume_sends_it(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        cap, worst = self.threshold_for('1')  # the round alone fits by $1; the operator's $30 does not
        with override_settings(QUESTION_PROVIDER_CAP_USD=cap, QUESTION_SITE_RESERVE_USD='40',
                               QUESTION_OTHER_SPEND_USD='30'):
            done = self.run_next(QUESTION)
            self.assertEqual(self.interpreter.question_sent, [])
            [run] = self.question_runs(encounter)
            self.assertEqual((run.state, run.sent), (Run.NOT_SENT, False))
            self.assertTrue(run.error.startswith('Nothing was sent: the worst case of this round'), run.error)
            self.assert_owed_and_resumable(encounter, revision, done, run.error)
            # a Resume while the month still refuses sends nothing and ends resumable again (no loop)
            jobs.resume(encounter, self.user)
            self.finish(encounter)
            self.assertEqual(self.interpreter.question_sent, [])
            self.assertEqual(self.state(encounter), 'stopped')
            self.assertEqual(self.queued(encounter), [])
        with override_settings(**NO_CAP):  # the month allows it again (a new month, or the owner's top-up)
            jobs.resume(encounter, self.user)
            self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a1_a_refusal_the_months_recorded_spend_causes_leaves_the_round_owed(self):
        """The month's recorded spend (one participant run of the month, bounded at its worst case) is what passes the
        threshold, with no other spend: owed, resumable."""
        other, other_revision = self.other()
        participant = self.fable_unknown(other, other_revision)
        encounter, revision, queued = self.to_questions(SESSION_E2)
        cap, worst = self.threshold_for(str(jobs._run_cost(participant) / 2))
        with override_settings(QUESTION_PROVIDER_CAP_USD=cap, QUESTION_SITE_RESERVE_USD='40',
                               QUESTION_OTHER_SPEND_USD='0'):
            done = self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.assertEqual(self.interpreter.question_sent, [])
        self.assert_owed_and_resumable(encounter, revision, done, run.error)

    def test_a1_a_month_that_cannot_be_bounded_refuses_nothing_about_the_request(self):
        """A run of the account whose model the price table holds no rates for cannot be bounded (never a guessed
        rate): the month cannot be checked, and that refusal says nothing about the request - owed, resumable."""
        other, other_revision = self.other()
        _participant_run(other, other_revision, state=Run.UNKNOWN, model='claude-synthetic-unpriced-9',
                         body={'model': 'claude-synthetic-unpriced-9', 'max_tokens': 1000})
        self.assertIsNone(jobs.account_month_spend())
        encounter, revision, done = self.one_document(OWNER)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.error, jobs.QUESTION_UNBOUNDED_MESSAGE)
        self.assert_owed_and_resumable(encounter, revision, done, jobs.QUESTION_UNBOUNDED_MESSAGE)

    def test_a1_boundary_a_round_over_the_threshold_by_itself_still_decides_refused(self):
        """BOUNDARY (left alone, DESIGN-v2 e.8): the round's own worst case passes the threshold with nothing else
        spent - it is refused whatever the month: decided 'refused', the row written, the code held."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        [question] = self.built.values()
        worst = Decimal(fable_adapter.worst_case_usd(question.request))
        with override_settings(QUESTION_PROVIDER_CAP_USD=str(Decimal('40') + worst / 2),
                               QUESTION_SITE_RESERVE_USD='40', QUESTION_OTHER_SPEND_USD='0'):
            done = self.run_next(QUESTION)
            self.finish(encounter)
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        [run] = self.question_runs(encounter)
        self.assertEqual(jobs._question_outcome(run), 'refused')
        self.assert_decided(revision, 'question_request_failed:refused')
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a1_boundary_a_request_whose_own_worst_case_cannot_be_bounded_is_refused_about_itself(self):
        with override_settings(QUESTION_PROVIDER_CAP_USD='10', QUESTION_SITE_RESERVE_USD='0'):
            self.assertEqual(jobs._question_budget_refusal([None]), jobs.QUESTION_UNBOUNDED_MESSAGE)
            self.assertTrue(jobs._refused_for_itself([None]))
            self.assertTrue(jobs._refused_for_itself(['10.000001']))
            self.assertFalse(jobs._refused_for_itself(['10.000000']))
            self.assertFalse(jobs._refused_for_itself(['4.000000', '6.000000']))
            self.assertTrue(jobs._refused_for_itself(['4.000000', '6.000001']))
