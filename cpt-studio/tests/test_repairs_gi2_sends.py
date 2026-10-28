"""Repair round gi2 (session 7c8d38da, the second GI round), cluster SENDS: controlled recovery of provider requests
that conclusively never reached the provider, and the reviewer-requested second review's offer. Synthetic data only; no
network: the provider is an in-process stand-in with the live adapter's name and version (so the real normaliser reads
its runs), or the REAL Corti adapter over a scripted in-process HTTP session. Every document opens with the synthetic
banner.

- R1 (ACCURACY-RESIDUALS p2 sends2-0; investigator "recovery"): a primary request whose attempt conclusively never
  reached the provider - the adapter records 'not_sent' only while the coding request provably has not left (a token
  refusal, unreadable credentials, its own deadline, a coding endpoint it could not connect to) - was never attempted
  again once a member date conflict had been held and was then settled, although the hold's own message says "Correct or
  clear the metadata ..., and the request is made for the agreed date". A save that settles the conflict now makes that
  request, once, through every send rule; every other save that leaves the request unchanged still only re-checks
  (ARCHITECTURE 5.4, round 3 pipeline3:0).
- R2 (investigator "recovery"): the Activity card read "Provider request sent" and "Provider response recorded" beside
  an attempt recorded as not sent, and "Provider response recorded" for an unknown outcome.
- F3 (investigator "eus2"): after an install that bumps the context version, the second-review offer accepted an ask the
  stage then skipped (nothing sent), the button came back and a second press was refused.
- L1 (investigator "eus2"): a second review that conclusively never reached the provider (not sent, or cancelled before
  sending) used up the once-per-revision-and-date bound, so it could never be asked for again without a new, paid
  primary request (an addendum).
"""
import itertools
import json
import tempfile
import threading
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from requests.exceptions import ConnectTimeout, ReadTimeout

from studio import audit, jobs, models, review, serializers
from studio.gi import context as gi_context
from studio.providers.base import ProviderUnavailable
from studio.providers.corti import CortiProvider
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import drain
from tests.test_providers import FakeResponse, dotenv, token_response, write_file
from tests.test_repairs_7c8_p1sends import DATE, UNDATED, Steps, installed_run_in_use
from tests.test_repairs_7c8_p1sends import Provider as P1Provider
from tests.test_repairs_ec5_reportruns import page
from tests.test_repairs_ec5_sends import BANNER, BIOPSY, MEMBER, SNARE
from tests.test_repairs_r1_m import install, run_app_script
from tests.test_services_second_review import LIVE, REPORT, response

Run = models.ProviderRun
NOT_SENT, CANCELLED, FAILED, UNKNOWN, SUCCEEDED = Run.NOT_SENT, Run.CANCELLED, Run.FAILED, Run.UNKNOWN, Run.SUCCEEDED
PRIMARY, SECOND_REVIEW = Run.PRIMARY, Run.SECOND_REVIEW
DOCUMENTED = ('Date of service: 2026-10-16',)  # REPORT's own date, as its request carries it
# A document whose own dates disagree: its request is dateless and the date is asked (not a member conflict).
TWO_DATES = REPORT.replace('Date of service: 2026-10-16\n', 'Date: 10/16/2026\nProcedure date: 10/14/2026\n')
ADDENDUM_TEXT = 'Signed by the fictional endoscopist.'
RUN_FIELDS = ('state', 'sent', 'http_status', 'provider_request_id', 'response_sha256', 'latency_ms', 'usage',
              'usage_basis', 'error', 'request_sha256', 'request_body', 'contexts', 'service_date', 'purpose', 'scope',
              'started_at', 'finished_at', 'reconciled_at', 'reused_from_id', 'revision_id', 'requested_by_id')
# Every scope key and run state this repair's flows may leave behind: nothing new is persisted (ops/install.py reads
# these rows after a rollback under the installed revision's rules).
KNOWN_SCOPE_KEYS = {'held', 'start', 'end', 'primary_run', 'assessment', 'items'}
KNOWN_RUN_STATES = {SUCCEEDED, FAILED, UNKNOWN, NOT_SENT, CANCELLED}


def snapshot(run):
    run = Run.objects.get(pk=run.pk)
    out = {name: getattr(run, name) for name in RUN_FIELDS}
    out['response_bytes'] = bytes(run.response_bytes)
    return out


def hazards():
    """What ops/install.py's undo reads in these rows: what the installed revision (057a7d39) would act on wrongly."""
    return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']


class ScriptProvider(P1Provider):
    """p1sends' stand-in (each send takes the next scripted outcome: 'succeeded', 'failed' - HTTP 500, sent -,
    'unknown' - sent, no response - or 'not_sent' - the token endpoint refused, sent=False), logging each attempt:
    (request sha256, outcome, date contexts). An attempt REACHED the provider unless its outcome is 'not_sent'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = []

    def send(self, request, *, deadline_s):
        exchange = super().send(request, deadline_s=deadline_s)
        self.log.append((request.canonical_sha256, exchange.outcome, tuple(request.contexts[1:])))
        return exchange

    def attempts(self, sha=None):
        return [entry for entry in self.log if sha is None or entry[0] == sha]

    def reached(self, sha=None):
        return [entry for entry in self.attempts(sha) if entry[1] != 'not_sent']


class MarkedSentProvider(ScriptProvider):
    """An adapter that records an attempt 'not_sent' while marking it sent: such an outcome is never trusted as one that
    never left (scripted as 'not_sent_marked_sent')."""

    def send(self, request, *, deadline_s):
        if self.outcomes and self.outcomes[0] == 'not_sent_marked_sent':
            self.outcomes.pop(0)
            self.requests.append(request)
            self.log.append((request.canonical_sha256, 'not_sent_marked_sent', tuple(request.contexts[1:])))
            return RawExchange(outcome='not_sent', sent=True, error='Recorded not sent but marked sent (synthetic).')
        return super().send(request, deadline_s=deadline_s)


class WorkerKilled(BaseException):
    """Stands in for the worker process dying mid-stage: not an Exception, so run_job records nothing."""


class LensSteps(Steps):
    provider_class = ScriptProvider

    def addendum(self, encounter_id, text=ADDENDUM_TEXT):
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def held(self, run):
        return (run.scope or {}).get('held') == Run.HELD_MEMBER_DATE_CONFLICT

    def run_in_use(self, encounter_id):
        return jobs._run_in_use(self.encounter(encounter_id).current_revision)

    def offered(self, encounter_id):
        return self.detail(encounter_id)['second_review']

    def member_conflict(self, encounter_id):
        return gi_context.is_member_conflict(self.encounter(encounter_id).current_context.facts['service_date'])

    def stale(self, job):
        """Age a RUNNING job past the stale cutoff, as a dead worker leaves it."""
        models.Job.objects.filter(pk=job.pk).update(
            started_at=timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS + 5))

    def assert_nothing_new_persisted(self, encounter_id):
        for run in self.runs(encounter_id):
            self.assertIn(run.state, KNOWN_RUN_STATES)
            self.assertLessEqual(set(run.scope or {}), KNOWN_SCOPE_KEYS)


# --- the real Corti adapter over a scripted HTTP session (no network) ------------------------------------------------

class _ScriptedSession:
    def __init__(self, steps, quotes, calls):
        self.steps, self.quotes, self.calls = list(steps), quotes, calls

    def post(self, url, **kwargs):
        self.calls.append(url)
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        if step == 'answer':
            text = json.loads(kwargs['data'])['context'][0]['text']
            return FakeResponse(200, response(text, [q for q in self.quotes if q[1] in text]),
                                headers={'X-Request-Id': 'synthetic-request-1'})
        return step

    def close(self):
        pass


_FILES = itertools.count(1)


def real_corti(case, scripts, quotes=(SNARE,)):
    """The REAL CortiProvider (its own build_request, send and normalize), installed as the provider for ``case``; each
    send() is given the next scripted session. ``provider.calls`` lists every URL posted."""
    tmp = Path(case.enterContext(tempfile.TemporaryDirectory()))
    path = write_file(tmp / f'corti-{next(_FILES)}.env', dotenv())
    calls, queue = [], list(scripts)
    provider = CortiProvider(path, session_factory=lambda: _ScriptedSession(queue.pop(0), list(quotes), calls))
    provider.calls, provider.queue = calls, queue
    case.enterContext(mock.patch('studio.jobs.get_provider', return_value=provider))
    return provider


def auth_refused():
    return [token_response(status=401)]


def answered():
    return [token_response(), 'answer']


class _JumpingClock:
    """corti.monotonic: the first reading starts the send's deadline; every later one is past it."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return 1000.0 if self.calls == 1 else 11_000.0


# --- R1: a save that settles a member date conflict makes the request the hold deferred ------------------------------

@override_settings(**LIVE)
class SettlingAMemberDateConflictMakesTheOwedRequestTests(LensSteps):
    """R1. The first attempt conclusively never reached the provider; a member's date conflicts with the documented
    date (held: nothing built or sent, interpretation 19); the member settles it - clears the date, or enters the
    documented one. The request the hold deferred is the byte-identical request the refused attempt carried: it is now
    made once, through every send rule, and the refused run and the hold are kept byte for byte."""

    def refused_then_held(self, outcomes=('not_sent',), text=REPORT):
        self.provider.outcomes = list(outcomes)
        encounter_id = self.create(text)
        drain()
        [refused] = self.runs(encounter_id)
        self.assertEqual((refused.state, refused.sent, refused.purpose), (NOT_SENT, False, PRIMARY))
        self.assertIsNotNone(refused.started_at)  # it went through the send door
        self.context(encounter_id, service_date=MEMBER)
        hold = self.runs(encounter_id)[-1]
        self.assertTrue(self.held(hold))
        self.assertIn('the request is made for the agreed date', hold.error)  # the promise the settle keeps
        self.assertEqual(len(self.provider.log), 1)  # the hold sends nothing
        return encounter_id, refused, hold

    def assert_one_new_attempt(self, encounter_id, refused, hold, before):
        sha = refused.request_sha256
        self.assertEqual(self.provider.log, [(sha, 'not_sent', DOCUMENTED), (sha, 'succeeded', DOCUMENTED)])
        runs = self.runs(encounter_id)
        self.assertEqual(runs[:2], [refused, hold])
        [attempt] = runs[2:]
        self.assertEqual((attempt.state, attempt.sent, attempt.request_sha256, attempt.contexts, attempt.service_date,
                          attempt.purpose),
                         (SUCCEEDED, True, sha, refused.contexts, refused.service_date, PRIMARY))
        self.assertEqual({str(r.pk): snapshot(r) for r in (refused, hold)}, before)  # kept, byte for byte
        self.assertEqual((refused.usage, hold.usage, attempt.usage), ({}, {}, {'creditsConsumed': 0.02}))
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.current_assessment.provider_run_id, attempt.pk)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
        self.assertNotEqual(encounter.state, 'provider_failed')
        self.assertEqual(self.run_in_use(encounter_id), attempt)
        self.assert_nothing_new_persisted(encounter_id)
        return attempt

    def test_clearing_the_conflict_makes_the_request_once(self):
        encounter_id, refused, hold = self.refused_then_held()
        before = {str(r.pk): snapshot(r) for r in (refused, hold)}
        self.context(encounter_id, service_date='')
        self.assert_one_new_attempt(encounter_id, refused, hold, before)

    def test_answering_with_the_documented_date_makes_the_request_once(self):
        encounter_id, refused, hold = self.refused_then_held()
        before = {str(r.pk): snapshot(r) for r in (refused, hold)}
        self.context(encounter_id, service_date=DATE)
        self.assert_one_new_attempt(encounter_id, refused, hold, before)

    def test_the_context_dialogs_whole_body_settles_it_too(self):
        # the dialog posts every field, every time
        encounter_id, refused, hold = self.refused_then_held()
        before = {str(r.pk): snapshot(r) for r in (refused, hold)}
        self.context(encounter_id, service_date='', setting='', billing_context='')
        self.assert_one_new_attempt(encounter_id, refused, hold, before)

    def test_a_save_that_keeps_a_conflict_makes_nothing(self):
        encounter_id, refused, hold = self.refused_then_held()
        self.context(encounter_id, service_date='1999-02-02')  # another date the document does not give: held again
        self.context(encounter_id, setting='office')  # the conflict stands
        self.assertEqual(len(self.provider.log), 1)
        self.assertTrue(self.member_conflict(encounter_id))
        self.context(encounter_id, service_date='')  # settled: the one attempt
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'succeeded'])

    def test_exactly_once_per_settling_save_and_never_behind_another_save(self):
        encounter_id, refused, hold = self.refused_then_held(outcomes=('not_sent', 'not_sent'))
        self.context(encounter_id, service_date='')  # settles: one attempt, conclusively not sent again
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'not_sent'])
        self.context(encounter_id, setting='office')  # leaves the request unchanged: re-checks only (pipeline3:0)
        self.context(encounter_id, billing_context='facility')
        self.context(encounter_id, service_date=DATE)  # the documented date with no conflict settled: re-checks only
        self.assertEqual(len(self.provider.log), 2)
        self.context(encounter_id, service_date=MEMBER)  # held again: nothing
        self.assertEqual(len(self.provider.log), 2)
        self.context(encounter_id, service_date='')  # settles again: one attempt
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'not_sent', 'succeeded'])
        self.assertEqual(len({entry[0] for entry in self.provider.log}), 1)  # one request, once per settling save
        self.assertEqual(len(self.provider.reached()), 1)

    def test_never_automatic(self):
        encounter_id, refused, hold = self.refused_then_held()
        for _ in range(3):
            jobs.mark_stale()
            drain()
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        self.assertEqual(len(self.provider.log), 1)

    def test_a_double_submit_makes_one_attempt(self):
        encounter_id, refused, hold = self.refused_then_held()
        first = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': ''})
        second = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': DATE})
        self.assertEqual((first.status_code, second.status_code), (201, 409))
        self.assertIn('Wait for processing to finish', second.json()['error'])
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'succeeded'])

    def test_an_identical_answered_request_is_reused_not_sent(self):
        encounter_id, refused, hold = self.refused_then_held()
        other = self.create(REPORT)  # another upload of the same report, answered
        drain()
        [answered_run] = self.runs(other)
        self.assertEqual((answered_run.state, answered_run.request_sha256), (SUCCEEDED, refused.request_sha256))
        self.context(encounter_id, service_date='')
        self.assertEqual(len(self.provider.log), 2)  # the first refusal and the other upload: nothing new
        attempt = self.runs(encounter_id)[-1]
        self.assertEqual((attempt.state, attempt.sent, attempt.reused_from_id, attempt.usage),
                         (SUCCEEDED, False, answered_run.pk, {}))

    def test_an_unknown_outcome_still_blocks_until_reconciled(self):
        # the settled attempt's outcome is unknown: from then on nothing is sent until a member reconciles it
        encounter_id, refused, hold = self.refused_then_held(outcomes=('not_sent', 'unknown'))
        self.context(encounter_id, service_date='')
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'unknown'])
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')  # settles a hold again: the run in use is the unknown one
        encounter = self.encounter(encounter_id)
        unknown = self.runs(encounter_id, state=UNKNOWN)[0]
        self.assertEqual(review.latest_job(encounter).kind, models.Job.ASSESS)  # it re-checks with it
        self.assertEqual((encounter.current_assessment.provider_run_id, encounter.current_assessment.context_id),
                         (unknown.pk, encounter.current_context_id))
        self.context(encounter_id, setting='office')
        self.addendum(encounter_id)
        for _ in range(2):
            jobs.mark_stale()
            drain()
        self.assertEqual(len(self.provider.log), 2)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        self.reconcile(encounter_id)
        self.assertEqual(len(self.provider.log), 3)  # the one released attempt

    def test_an_unknown_outcome_elsewhere_in_the_encounter_still_blocks(self):
        # constructed (the system's own transitions cannot reach it: an unknown outcome blocks every later send): an
        # unreconciled unknown second review beside the refused primary. The settling save re-predicts, and the
        # predict's unknown-outcome block sends nothing.
        encounter_id, refused, hold = self.refused_then_held()
        Run.objects.create(
            encounter=refused.encounter, revision=refused.revision, provider=refused.provider,
            adapter_version=refused.adapter_version, request_sha256='e' * 64, request_body={}, contexts=[],
            state=UNKNOWN, sent=True, purpose=SECOND_REVIEW, service_date=refused.service_date,
            error='constructed: the worker stopped while the request was in flight.', started_at=timezone.now(),
            finished_at=timezone.now())
        self.context(encounter_id, service_date='')
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')

    def test_a_failed_request_is_still_never_resent(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create(REPORT)
        drain()
        [failed] = self.runs(encounter_id)
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date=DATE)
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, failed.pk)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_failed')

    def test_a_not_resent_record_of_a_failed_request_stands(self):
        # constructed: the run a predict records where its send door met a request that FAILED (_not_resent_run) is the
        # run in use when a hold is settled. It went through the send door and was not sent, but its request failed in
        # this encounter: it is never owed - nothing is sent and no further not-resent row is recorded.
        self.provider.outcomes = ['failed']
        encounter_id = self.create(REPORT)
        drain()
        [failed] = self.runs(encounter_id)
        now = timezone.now()
        stands = Run.objects.create(
            encounter=failed.encounter, revision=failed.revision, provider=failed.provider,
            adapter_version=failed.adapter_version, request_sha256=failed.request_sha256,
            request_body=failed.request_body, contexts=failed.contexts, state=NOT_SENT, sent=False,
            error=jobs.FAILED_BEFORE_MESSAGE, service_date=failed.service_date, started_at=now, finished_at=now)
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(self.provider.log), 1)
        runs = self.runs(encounter_id)
        self.assertEqual(runs[:2], [failed, stands])
        self.assertEqual([self.held(run) for run in runs[2:]], [True])  # only the hold: no new not-resent row
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, stands.pk)

    def test_a_reconciled_unknowns_released_attempt_that_was_not_sent(self):
        # the released attempt never reached the provider: a settling save makes it once, so the request reaches the
        # provider at most once after the reconciliation
        self.provider.outcomes = ['unknown', 'not_sent']
        encounter_id = self.create(REPORT)
        drain()
        self.reconcile(encounter_id)
        self.assertEqual([entry[1] for entry in self.provider.log], ['unknown', 'not_sent'])
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        sha = self.provider.log[0][0]
        self.assertEqual([entry[1] for entry in self.provider.attempts(sha)], ['unknown', 'not_sent', 'succeeded'])
        self.assertEqual(len(self.provider.reached(sha)), 2)

    def test_settling_onto_a_documents_own_date_question_reattempts_dateless(self):
        # the document's dates disagree (a dateless request); the member's date matches neither (a member conflict);
        # clearing it returns to the document's own question: the deferred request is the dateless one the refused
        # attempt carried, made once - no date is invented, and the question still stands
        self.provider.outcomes = ['not_sent']
        encounter_id = self.create(TWO_DATES)
        drain()
        [refused] = self.runs(encounter_id)
        self.assertEqual((refused.state, len(refused.contexts)), (NOT_SENT, 1))
        self.context(encounter_id, service_date=MEMBER)
        # the request has no date either way: the dateless run in use answers it, so this save re-checks with it - no
        # hold row is recorded and nothing is sent (as installed)
        self.assertEqual(self.runs(encounter_id), [refused])
        self.assertTrue(self.member_conflict(encounter_id))
        self.assertEqual(len(self.provider.log), 1)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.provider.log, [(refused.request_sha256, 'not_sent', ()),
                                             (refused.request_sha256, 'succeeded', ())])
        self.assertTrue(self.date_question(encounter_id))

    def test_the_pinned_contract_is_unchanged(self):
        # no conflict was held: a save that leaves the request unchanged re-checks (5.4; round 3 pipeline3:0)
        self.provider.outcomes = ['not_sent']
        encounter_id = self.create(REPORT)
        drain()
        [refused] = self.runs(encounter_id)
        self.context(encounter_id, setting='office')
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, billing_context='professional')
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, refused.pk)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_failed')

    def test_rollback_reading_after_each_outcome_of_the_attempt(self):
        for outcome, expected in (('succeeded', None), ('not_sent', None), ('failed', None), ('unknown', ['unknown'])):
            with self.subTest(outcome=outcome):
                self.provider.outcomes = ['not_sent', outcome]
                text = REPORT.replace('Colonoscopy report (fictional)', f'Colonoscopy report (fictional, {outcome})')
                encounter_id = self.create(text)
                drain()
                self.context(encounter_id, service_date=MEMBER)
                self.assertIsNone(hazards().get(encounter_id))
                self.context(encounter_id, service_date='')
                attempt = self.runs(encounter_id)[-1]
                self.assertEqual((attempt.state, attempt.purpose), (outcome, PRIMARY))
                revision = self.encounter(encounter_id).current_revision
                self.assertEqual(installed_run_in_use(revision), attempt)  # 057a7d39 reads an ordinary run
                self.assertEqual(hazards().get(encounter_id), expected)  # only classes the installer already knows
                self.assert_nothing_new_persisted(encounter_id)


@override_settings(**LIVE)
class TheRealAdaptersOutcomesDecideTests(LensSteps):
    """R1 through the REAL Corti adapter: only an outcome it records as not sent (the coding request provably never
    left) is attempted again by a settling save; one that may have reached Corti (unknown) or did (failed) never is."""

    def test_a_token_refusal_then_a_settled_conflict(self):
        corti = real_corti(self, [auth_refused(), answered()])
        encounter_id = self.create(REPORT)
        drain()
        [refused] = self.runs(encounter_id)
        self.assertEqual((refused.state, refused.sent, refused.error),
                         (NOT_SENT, False, 'Corti authentication was refused (HTTP 401); no coding request was sent.'))
        self.assertEqual(len(corti.calls), 1)
        self.assertNotIn('/v2/tools/coding/', corti.calls[0])  # the coding request never left
        self.context(encounter_id, service_date=MEMBER)
        self.assertEqual(len(corti.calls), 1)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(corti.calls), 3)  # one new token request and one coding request
        self.assertTrue(corti.calls[2].endswith('/v2/tools/coding/'))
        attempt = self.runs(encounter_id)[-1]
        self.assertEqual((attempt.state, attempt.sent, attempt.http_status, attempt.provider_request_id,
                          attempt.request_sha256),
                         (SUCCEEDED, True, 200, 'synthetic-request-1', refused.request_sha256))
        self.assertIn('45385', {p.code for p in self.encounter(encounter_id).current_assessment.proposals.all()})

    def test_the_adapters_own_deadline_then_a_settled_conflict(self):
        corti = real_corti(self, [[token_response()], answered()])
        with mock.patch('studio.providers.corti.monotonic', _JumpingClock()):
            encounter_id = self.create(REPORT)
            drain()
        [refused] = self.runs(encounter_id)
        self.assertEqual((refused.state, refused.sent, refused.error),
                         (NOT_SENT, False, 'The deadline passed before Corti authentication; nothing was sent.'))
        self.assertEqual(corti.calls, [])  # nothing was posted at all
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(corti.calls), 2)  # a token request and the coding request: the one new attempt
        self.assertEqual(self.runs(encounter_id)[-1].state, SUCCEEDED)

    def test_a_coding_endpoint_that_could_not_be_connected_then_a_settled_conflict(self):
        corti = real_corti(self, [[token_response(), ConnectTimeout()], answered()])
        encounter_id = self.create(REPORT)
        drain()
        [refused] = self.runs(encounter_id)
        self.assertEqual((refused.state, refused.sent), (NOT_SENT, False))
        self.assertIn('could not be reached', refused.error)
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(corti.calls), 4)
        self.assertEqual(self.runs(encounter_id)[-1].state, SUCCEEDED)

    def test_control_a_read_timeout_after_the_send_is_unknown_and_never_attempted_again(self):
        corti = real_corti(self, [[token_response(), ReadTimeout()], answered()])
        encounter_id = self.create(REPORT)
        drain()
        [unknown] = self.runs(encounter_id)
        self.assertEqual((unknown.state, unknown.sent), (UNKNOWN, True))
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(corti.calls), 2)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')

    def test_control_a_refusal_from_the_coding_endpoint_is_a_sent_failure_never_attempted_again(self):
        corti = real_corti(self, [[token_response(), FakeResponse(429, b'{"error":"synthetic"}')], answered()])
        encounter_id = self.create(REPORT)
        drain()
        [failed] = self.runs(encounter_id)
        self.assertEqual((failed.state, failed.sent, failed.http_status), (FAILED, True, 429))
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(corti.calls), 2)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_failed')


@override_settings(**LIVE)
class ConcurrentSettlingSavesTests(TransactionTestCase):
    """R1 under concurrency: two members settle the same held conflict at once (separate database connections). The row
    lock and the busy check let one save through; the request is attempted once."""

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user('reviewer'))
        self.provider = ScriptProvider(first=[], later=[], outcomes=['not_sent'])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.user)
        reply = client.post('/api/encounters', {'text': REPORT, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        self.encounter_id = reply.json()['id']
        drain()
        jobs.change_context(models.Encounter.objects.get(pk=self.encounter_id), self.user, {'service_date': MEMBER})
        drain()
        self.assertEqual(len(self.provider.log), 1)

    def test_two_concurrent_settling_saves_make_one_attempt(self):
        barrier, results = threading.Barrier(2), []

        def save(values):
            try:
                barrier.wait()
                jobs.change_context(models.Encounter.objects.get(pk=self.encounter_id), self.user, values)
                results.append('saved')
            except jobs.Refused as exc:
                results.append(f'refused: {exc}')
            finally:
                connection.close()
        threads = [threading.Thread(target=save, args=(values,))
                   for values in ({'service_date': ''}, {'service_date': DATE})]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual(sorted(results), ['refused: Wait for processing to finish (or stop it) before changing '
                                           'context.', 'saved'])
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['not_sent', 'succeeded'])


# --- R2: the Activity card states each attempt's recorded outcome ----------------------------------------------------

@override_settings(**LIVE)
class TheActivityCardStatesTheRecordedOutcomeTests(LensSteps):
    """R2. 'provider.sending' is recorded before the exchange, so it says only that the attempt started; its
    'provider.finished' line is worded from the outcome that row recorded."""

    EXPECTED = {
        'not_sent': ['Provider request started', 'Provider request not sent'],
        'unknown': ['Provider request started', 'Provider outcome unknown: no complete response was recorded'],
        'failed': ['Provider request started', 'Provider request failed (HTTP 500)'],
        'succeeded': ['Provider request started', 'Provider response recorded'],
    }
    TEXTS = {'not_sent': REPORT, 'unknown': UNDATED, 'failed': TWO_DATES,
             'succeeded': REPORT.replace('(fictional)', '(fictional, answered)', 1)}

    def provider_lines(self, encounter_id):
        return [event['summary'] for event in self.detail(encounter_id)['activity']
                if event['event'] in ('provider.sending', 'provider.finished', 'provider.reused')]

    def test_each_outcome(self):
        for outcome, lines in self.EXPECTED.items():
            with self.subTest(outcome=outcome):
                self.provider.outcomes = [outcome]
                encounter_id = self.create(self.TEXTS[outcome])
                drain()
                [run] = self.runs(encounter_id)
                self.assertEqual(run.state, outcome)
                self.assertEqual(self.provider_lines(encounter_id), lines)

    def test_the_activity_tab_never_says_sent_for_an_attempt_that_was_not(self):
        for outcome in ('not_sent', 'unknown'):
            with self.subTest(outcome=outcome):
                self.provider.outcomes = [outcome]
                encounter_id = self.create(self.TEXTS[outcome])
                drain()
                timeline = page(self.detail(encounter_id))['timeline']
                activity = timeline[timeline.index('| Activity |'):]
                self.assertNotIn('Provider request sent', activity)
                self.assertNotIn('Provider response recorded', activity)
                self.assertIn(f'| {self.EXPECTED[outcome][1]} |', activity)

    def test_a_second_review_attempt_is_worded_the_same_way(self):
        self.provider.outcomes = ['succeeded', 'not_sent']
        encounter_id = self.create(REPORT)
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.provider_lines(encounter_id), ['Provider request started', 'Provider response recorded',
                                                             'Provider request started', 'Provider request not sent'])

    def test_a_reused_answer_and_a_hold_are_unchanged(self):
        first = self.create(REPORT)
        drain()
        second = self.create(REPORT)
        drain()
        self.assertEqual(self.provider_lines(second), ['Retained provider result reused (no new request)'])
        held = self.create(REPORT.replace('(fictional)', '(fictional, held)', 1), service_date=MEMBER)
        drain()
        self.assertEqual(self.provider_lines(held), [])
        self.assertEqual(Run.objects.filter(encounter_id=first).count(), 1)

    def test_a_finished_row_that_recorded_no_outcome_claims_none(self):
        encounter_id = self.create(REPORT)
        drain()
        encounter = self.encounter(encounter_id)
        for data, summary in (({}, 'Provider request finished'),
                              ({'state': 'failed', 'http_status': None}, 'Provider request failed'),
                              ({'state': 'reserved'}, 'Provider request finished')):
            with self.subTest(data=data):
                event = audit.record(encounter.workspace, 'provider.finished', encounter=encounter, **data)
                self.assertEqual(serializers._activity_json(event)['summary'], summary)


# --- F3: the second-review offer refuses a context read under earlier context rules ----------------------------------

@override_settings(**LIVE)
class TheOfferRefusesAContextReadUnderEarlierRulesTests(LensSteps):
    """F3. An install that bumps CONTEXT_VERSION leaves every encounter's current context 'earlier'; stage_review2 sends
    nothing for such a context, so the offer refuses it too, with what reads it again under the current rules."""

    def bump(self):
        self.enterContext(mock.patch.object(jobs, 'CONTEXT_VERSION', 'gi-context@3'))
        self.enterContext(mock.patch.object(jobs, 'EARLIER_CONTEXT_VERSIONS', ('gi-context@1', 'gi-context@2')))

    def assessed(self):
        self.provider.outcomes = ['succeeded']
        encounter_id = self.create(REPORT)
        drain()
        offered = self.offered(encounter_id)
        self.assertTrue(offered['available'], offered)
        return encounter_id

    def assert_refused_with_the_remake(self, encounter_id):
        offered = self.offered(encounter_id)
        self.assertFalse(offered['available'], offered)
        self.assertIn('earlier context rules', offered['reason'])
        jobs_before = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).count()
        reply = self.ask(encounter_id)
        self.assertEqual(reply.status_code, 409, reply.content)
        self.assertEqual(reply.json()['error'], offered['reason'])
        self.assertEqual(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).count(),
                         jobs_before)
        page_codes = page(self.detail(encounter_id))['codesHtml']
        self.assertNotIn('data-action="second-review"', page_codes)

    def assert_one_ask_sends_once(self, encounter_id, sent_before):
        offered = self.offered(encounter_id)
        self.assertTrue(offered['available'], offered)
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.log), sent_before + 1)
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(len(self.provider.log), sent_before + 1)

    def test_after_a_version_bump_the_offer_refuses_and_nothing_is_queued(self):
        encounter_id = self.assessed()
        self.bump()
        self.assert_refused_with_the_remake(encounter_id)
        drain()
        self.assertEqual(len(self.provider.log), 1)

    def test_a_context_save_reads_it_again_and_one_ask_sends_once(self):
        encounter_id = self.assessed()
        self.bump()
        self.assert_refused_with_the_remake(encounter_id)
        self.context(encounter_id, billing_context='')  # an API save of an unchanged value: remade, nothing sent
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).current_context.version, 'gi-context@3')
        self.assert_one_ask_sends_once(encounter_id, 1)

    def test_the_context_dialogs_save_of_a_change_reads_it_again_too(self):
        # the dialog posts every field and refuses a save that changes nothing, so the member saves a change
        encounter_id = self.assessed()
        self.bump()
        self.assert_refused_with_the_remake(encounter_id)
        self.context(encounter_id, service_date='', setting='', billing_context='professional')
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).current_context.version, 'gi-context@3')
        self.assert_one_ask_sends_once(encounter_id, 1)

    def test_an_ask_queued_before_the_bump_is_skipped_and_the_offer_says_why(self):
        encounter_id = self.assessed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        self.bump()
        drain()
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        self.assertEqual(job.result, {'skipped': 'the context changed; nothing was sent'})
        self.assertEqual(len(self.provider.log), 1)
        self.assert_refused_with_the_remake(encounter_id)
        self.context(encounter_id, billing_context='')
        self.assert_one_ask_sends_once(encounter_id, 1)

    def test_control_a_current_context_is_offered_and_asked_as_before(self):
        encounter_id = self.assessed()
        self.assert_one_ask_sends_once(encounter_id, 1)


# --- L1: a second review that conclusively never reached the provider leaves the ask open ----------------------------

@override_settings(**LIVE)
class ASecondReviewNeverSentLeavesTheAskOpenTests(LensSteps):
    """L1. The once-per-revision-and-date bound counts every second review that may have reached the provider; one the
    adapter recorded as not sent, one whose request could not be built, one a Stop cancelled before sending and one the
    stale sweep settled before sending never did, so the reviewer may ask again - explicitly: nothing is ever asked by
    itself. An unknown outcome still blocks every ask until reconciled, a failed or answered one still uses the bound, a
    retained identical answer is reused, and two asks at once queue one stage."""

    def assessed(self, outcomes=('succeeded',)):
        """REPORT: the primary answer names the snare removal and leaves the forceps biopsy without a proposal."""
        self.provider.outcomes = list(outcomes)
        encounter_id = self.create(REPORT)
        drain()
        self.assertTrue(self.offered(encounter_id)['available'])
        return encounter_id

    def seconds(self, encounter_id):
        return self.runs(encounter_id, purpose=SECOND_REVIEW)

    def asked(self, encounter_id):
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()

    def assert_asks_again_once(self, encounter_id, never_sent):
        """The offer is open again beside the run that never reached the provider (the panel still names it); one ask
        sends once and fills the biopsy; the bound then stands."""
        before = snapshot(never_sent)
        offered = self.offered(encounter_id)
        self.assertTrue(offered['available'], offered)
        self.assertEqual(offered['reason'], '')
        reached = len(self.provider.reached())
        self.asked(encounter_id)
        runs = self.seconds(encounter_id)
        self.assertEqual(runs[0], never_sent)
        self.assertEqual([(r.state, r.sent) for r in runs[1:]], [(SUCCEEDED, True)])
        self.assertEqual(len(self.provider.reached()), reached + 1)
        self.assertEqual(snapshot(never_sent), before)  # kept, byte for byte
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})
        self.assertEqual(self.encounter(encounter_id).current_assessment.second_run_id, runs[-1].pk)
        self.assertEqual(self.ask(encounter_id).status_code, 409)  # the biopsy is filled; nothing is asked again
        drain()
        self.assertEqual(len(self.provider.reached()), reached + 1)
        self.assert_nothing_new_persisted(encounter_id)
        return runs[-1]

    def test_one_the_adapter_recorded_as_not_sent(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent'))
        self.asked(encounter_id)
        [never] = self.seconds(encounter_id)
        self.assertEqual((never.state, never.sent), (NOT_SENT, False))
        self.assertIsNotNone(never.started_at)
        self.assertEqual(self.offered(encounter_id)['run'], str(never.pk))  # the panel still states how it ended
        second = self.assert_asks_again_once(encounter_id, never)
        self.assertEqual(second.request_sha256, never.request_sha256)  # the same request, now made

    def test_one_cancelled_before_sending_after_a_later_save(self):
        encounter_id = self.assessed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.REVIEW2)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        jobs.run_job(job)  # the Stop is observed after the run is reserved, before anything is sent
        [cancelled] = self.seconds(encounter_id)
        self.assertEqual((cancelled.state, cancelled.sent, cancelled.error),
                         (CANCELLED, False, 'Stopped before sending; nothing was sent.'))
        self.context(encounter_id, billing_context='professional')  # a later save: Resume no longer runs it
        self.assertFalse(self.detail(encounter_id)['pipeline']['can_resume'])
        self.assert_asks_again_once(encounter_id, cancelled)

    def test_one_cancelled_before_sending_resume_or_ask_makes_it_once(self):
        encounter_id = self.assessed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        job = jobs.claim_next()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        jobs.run_job(job)
        [cancelled] = self.seconds(encounter_id)
        self.assertEqual(cancelled.state, CANCELLED)
        self.assertTrue(self.detail(encounter_id)['pipeline']['can_resume'])
        self.assertEqual(self.ask(encounter_id).status_code, 201)  # the explicit ask, instead of the Resume
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)  # busy: one at a time
        drain()
        self.assertEqual(len(self.provider.reached()), 2)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)  # nothing stopped now
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(len(self.provider.reached()), 2)

    def test_one_the_sweep_settled_before_sending(self):
        encounter_id = self.assessed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.REVIEW2)
        with mock.patch('studio.jobs.is_stopped', side_effect=WorkerKilled()), self.assertRaises(WorkerKilled):
            jobs.run_job(job)
        self.stale(job)
        jobs.mark_stale()
        [swept] = self.seconds(encounter_id)
        self.assertEqual((swept.state, swept.sent, swept.started_at, swept.error),
                         (NOT_SENT, False, None, 'The worker stopped before sending.'))
        self.assertEqual(len(self.provider.log), 1)
        self.assert_asks_again_once(encounter_id, swept)

    def test_one_whose_request_could_not_be_built_is_asked_again_and_sends_nothing(self):
        build = self.provider.build_request

        def excerpt_refused(text, service_date):
            if not text.startswith(BANNER):
                raise ProviderUnavailable('The excerpt cannot be sent (synthetic stand-in for an adapter refusal).')
            return build(text, service_date)
        self.provider.build_request = excerpt_refused
        encounter_id = self.assessed()
        self.asked(encounter_id)
        [unbuilt] = self.seconds(encounter_id)
        self.assertEqual((unbuilt.state, unbuilt.sent, unbuilt.request_sha256), (NOT_SENT, False, ''))
        self.assertTrue(self.offered(encounter_id)['available'])
        self.asked(encounter_id)  # explicitly, again: recorded as not sent again, and nothing is sent
        self.assertEqual([(r.state, r.sent) for r in self.seconds(encounter_id)], [(NOT_SENT, False)] * 2)
        self.assertEqual(len(self.provider.log), 1)

    def test_an_identical_answer_retained_elsewhere_is_reused_never_resent(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent', 'succeeded'))
        self.asked(encounter_id)
        [never] = self.seconds(encounter_id)
        other = self.create(REPORT)  # the same report again: its primary answer is reused
        drain()
        self.asked(other)  # its second review is the identical excerpt request, and it is answered
        [answered_run] = self.seconds(other)
        self.assertEqual((answered_run.state, answered_run.request_sha256), (SUCCEEDED, never.request_sha256))
        reached = len(self.provider.reached())
        self.asked(encounter_id)
        reuse = self.seconds(encounter_id)[-1]
        self.assertEqual((reuse.state, reuse.sent, reuse.reused_from_id, reuse.usage),
                         (SUCCEEDED, False, answered_run.pk, {}))
        self.assertEqual(len(self.provider.reached()), reached)
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})

    def test_a_double_ask_queues_one_stage(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent'))
        self.asked(encounter_id)
        first, second = self.ask(encounter_id), self.ask(encounter_id)
        self.assertEqual((first.status_code, second.status_code), (201, 409))
        self.assertIn('Wait for processing to finish', second.json()['error'])
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['succeeded', 'not_sent', 'succeeded'])

    def test_never_asked_by_itself(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent'))
        self.asked(encounter_id)
        jobs_before = models.Job.objects.filter(encounter_id=encounter_id).count()
        self.context(encounter_id, setting='office')  # a re-assessment queues no second review
        for _ in range(3):
            jobs.mark_stale()
            drain()
        self.assertEqual(len(self.provider.log), 2)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2,
                                                   created_at__gt=self.seconds(encounter_id)[0].created_at).exists())
        self.assertGreater(models.Job.objects.filter(encounter_id=encounter_id).count(), jobs_before)

    def test_an_unknown_outcome_still_blocks_every_ask(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'unknown'))
        self.asked(encounter_id)
        [unknown] = self.seconds(encounter_id)
        self.assertEqual((unknown.state, unknown.sent), (UNKNOWN, True))
        self.assertFalse(self.offered(encounter_id)['available'])
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        self.context(encounter_id, setting='office')
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        for _ in range(2):
            jobs.mark_stale()
            drain()
        self.assertEqual(len(self.provider.log), 2)

    def test_an_unknown_outcome_after_a_not_sent_one_still_blocks(self):
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent', 'unknown'))
        self.asked(encounter_id)
        self.asked(encounter_id)  # the second ask: its outcome is unknown
        self.assertEqual([r.state for r in self.seconds(encounter_id)], [NOT_SENT, UNKNOWN])
        self.assertFalse(self.offered(encounter_id)['available'])
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(len(self.provider.log), 3)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')

    def test_a_failed_or_answered_one_still_uses_the_bound(self):
        # the answered one fills nothing (its answer names no code for the biopsy), so the item stays open and only
        # the bound refuses the ask
        for outcome, said in (('failed', 'already requested'), ('succeeded', 'already made')):
            with self.subTest(outcome=outcome):
                self.provider.later = [SNARE]
                self.provider.outcomes = ['succeeded', outcome]
                encounter_id = self.create(REPORT.replace('(fictional)', f'(fictional, {outcome})', 1))
                drain()
                self.asked(encounter_id)
                [second] = self.seconds(encounter_id)
                self.assertEqual((second.state, second.sent), (outcome, True))
                offered = self.offered(encounter_id)
                self.assertTrue(offered['items'])
                self.assertFalse(offered['available'])
                self.assertIn(said, offered['reason'])
                reply = self.ask(encounter_id)
                self.assertEqual(reply.status_code, 409)
                self.assertIn(said, reply.json()['error'])
                sent = len(self.provider.log)
                drain()
                self.assertEqual(len(self.provider.log), sent)

    def test_the_stop_before_its_stage_ran_keeps_resume_as_its_one_route(self):
        # pinned elsewhere (test_repairs_ec5_reportruns): a second review stopped before its stage ran recorded no run;
        # its request was asked for once, and Resume runs it once
        encounter_id = self.assessed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(self.seconds(encounter_id), [])
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.reached()), 2)

    def test_an_ask_after_one_never_sent_resumes_as_deep_as_before(self):
        # Job.idempotency_key holds 200 characters and every Resume appends 44: the key of an ask made after a second
        # review that was never sent keeps the depth the installed key had (a stage stopped and resumed twice)
        encounter_id = self.assessed(outcomes=('succeeded', 'not_sent'))
        self.asked(encounter_id)
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        for _ in range(2):
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
            drain()  # the queued stage was cancelled before it ran: nothing is sent
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['succeeded', 'not_sent', 'succeeded'])
        keys = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).values_list(
            'idempotency_key', flat=True)
        self.assertEqual(len(keys), 4)
        self.assertLessEqual(max(len(key) for key in keys), 200)

    def test_rollback_reading_names_only_classes_the_installer_knows(self):
        # the same answered second review, made after one that was never sent or made directly, reads the same
        control = self.assessed(outcomes=('succeeded', 'succeeded'))
        self.asked(control)
        repaired = self.create(REPORT.replace('(fictional)', '(fictional, retried)', 1))
        self.provider.outcomes = ['succeeded', 'not_sent', 'succeeded']
        drain()
        self.asked(repaired)
        self.asked(repaired)
        self.assertEqual([r.state for r in self.seconds(repaired)], [NOT_SENT, SUCCEEDED])
        read = hazards()
        self.assertEqual(read.get(repaired), read.get(control))
        self.assertEqual(read.get(control), ['second_review'])  # its code is in the decision set, as installed
        unknown = self.create(REPORT.replace('(fictional)', '(fictional, unknown)', 1))
        self.provider.outcomes = ['succeeded', 'not_sent', 'unknown']
        drain()
        self.asked(unknown)
        self.asked(unknown)
        self.assertEqual([r.state for r in self.seconds(unknown)], [NOT_SENT, UNKNOWN])
        self.assertEqual(hazards().get(unknown), ['unknown'])
        for encounter_id in (control, repaired, unknown):
            self.assert_nothing_new_persisted(encounter_id)


@override_settings(**LIVE)
class AnOutcomeMarkedSentIsNeverTrustedAsNeverSentTests(LensSteps):
    """R1 and L1 trust only a 'not_sent' outcome whose run says sent=False: one an adapter marked sent is treated as a
    request that may have reached the provider - never attempted again by a settling save, and it uses up the bound."""

    provider_class = MarkedSentProvider

    def test_a_settling_save_never_attempts_it_again(self):
        self.provider.outcomes = ['not_sent_marked_sent']
        encounter_id = self.create(REPORT)
        drain()
        [marked] = self.runs(encounter_id)
        self.assertEqual((marked.state, marked.sent), (NOT_SENT, True))
        self.context(encounter_id, service_date=MEMBER)
        self.context(encounter_id, service_date='')
        self.assertEqual(len(self.provider.log), 1)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, marked.pk)

    def test_a_second_review_marked_sent_uses_up_the_bound(self):
        self.provider.outcomes = ['succeeded', 'not_sent_marked_sent']
        encounter_id = self.create(REPORT)
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        [marked] = self.runs(encounter_id, purpose=SECOND_REVIEW)
        self.assertEqual((marked.state, marked.sent), (NOT_SENT, True))
        offered = self.offered(encounter_id)
        self.assertFalse(offered['available'])
        self.assertIn('already requested', offered['reason'])
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(len(self.provider.log), 2)


@override_settings(**LIVE)
class ConcurrentAsksAfterANotSentSecondReviewTests(TransactionTestCase):
    """L1 under concurrency: two reviewers ask at once after a second review that was never sent (separate database
    connections). The row lock and the busy check queue one stage; the request is sent once."""

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user('reviewer'))
        self.provider = ScriptProvider(first=[SNARE], later=[BIOPSY, SNARE], outcomes=['succeeded', 'not_sent'])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.user)
        reply = client.post('/api/encounters', {'text': REPORT, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        self.encounter_id = reply.json()['id']
        drain()
        jobs.request_second_review(models.Encounter.objects.get(pk=self.encounter_id), self.user)
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['succeeded', 'not_sent'])

    def test_two_concurrent_asks_send_once(self):
        barrier, results = threading.Barrier(2), []

        def ask():
            try:
                barrier.wait()
                jobs.request_second_review(models.Encounter.objects.get(pk=self.encounter_id), self.user)
                results.append('queued')
            except jobs.Refused as exc:
                results.append(f'refused: {exc}')
            finally:
                connection.close()
        threads = [threading.Thread(target=ask) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual(sorted(results), ['queued', 'refused: Wait for processing to finish (or stop it) before '
                                                     'asking for a second review.'])
        drain()
        self.assertEqual([entry[1] for entry in self.provider.log], ['succeeded', 'not_sent', 'succeeded'])
        asks = models.Job.objects.filter(encounter_id=self.encounter_id, kind=models.Job.REVIEW2)
        self.assertEqual(asks.count(), 2)  # the first ask, and the one of the two that was queued
        sent = Run.objects.filter(encounter_id=self.encounter_id, purpose=SECOND_REVIEW, sent=True)
        self.assertEqual(sent.count(), 1)
