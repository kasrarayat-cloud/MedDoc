"""Round r3's live question stage (DECISIONS D306, D320, D322; build-v2/a2b/r3 DESIGN-v2 e.1-e.8 and (i)): the question
request kind in the connector, the QUESTION stage of studio/jobs.py (one job per round, its requests sent concurrently
under one provider lock after one reservation), its doors, the ONE row binding every run, the settings rows and the
customer surface. TEXT-ONLY and SYNTHETIC: every document is test_jobs' (fictional clinicians, no real patient); every
pass-1 answer is built by hand, every pass-2 answer is a deterministic oracle over the claim set the production
builder makes, and every question answer is built here over the QuestionRequest the stage itself built (captured from
jobs._question_state's wave) - nothing is sent anywhere: the interpreter is the production connector
(fable_adapter.InterpreterF: its request checks, deadlines, one-exchange loop, stream reader, envelope and classifier)
whose one exchange is scripted. The worker is driven by jobs.claim_next and jobs.run_job explicitly.

A pass-2 oracle that leaves a fact's claim without a verdict (appraisal:missing: CENSUS-v2's C2a, a READING row) makes
the planner ask that fact as a question; a question answered with its claim supported by the act's own words and its
exact negation contradicted establishes it, and the engine reads it as a fact."""
from __future__ import annotations

import copy
import dataclasses
import json  # noqa: F401 - the answers' JSON
import threading
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from studio import interpretation, jobs, models
from studio.interpretation import fable_adapter, store
from studio.interpretation import holds as interpretation_holds
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking
from studio.providers.base import request_sha256
from studio.types import RawExchange
from tests.v2 import test_jobs as TJ
from tests.v2.test_fable_adapter import answer_stream
from tests.v2.test_settle import colonoscopy, event, fact, faithful, src

A = ct.Attribute
Run, Job = models.ProviderRun, models.Job
QUESTION = 'question'
QUOTE_MAX_CHARS, QUOTE_MIN_TOKENS, QUOTE_MIN_CHARS = 300, 2, 12
FORBIDDEN = ('fable', 'question', 'proof', 'answer', 'claude', 'anthropic')  # (i): never in a customer's words

# the facts a pass-2 oracle leaves without a verdict, one question each (POLYP's acts: E1 the examination, E2 the
# cold-snare removal; THREE's: E1, and the removals E2, E3, E4)
SESSION_E2 = ('E2', A.SESSION)
SESSION_E1 = ('E1', A.SESSION)
SESSION_E3 = ('E3', A.SESSION)
SESSION_E4 = ('E4', A.SESSION)
THREE = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                 # S1
         'Date of service: 03/14/2031\n'                                                   # S2
         'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                   # S3
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n'                          # S4
         'A 4 mm polyp in the rectum was removed with a cold snare.\n'                     # S5
         'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n'              # S6
         'A 6 mm polyp in the transverse colon was removed with a cold snare.\n')          # S7


def three_answer():
    """THREE's pass-1 answer: the colonoscopy X1 (E1) and three cold-snare removals in it, E2-E4, each at its place."""
    def removal(eid, unit, place, words):
        return event(eid, [unit], 'cold snare', 'was removed', 'snare', session=[fact('X1', src([unit]))],
                     target__places=[fact(place, src([unit], words))],
                     technique__device=[fact('cold_snare', src([unit], 'cold snare'))])
    return colonoscopy(THREE, removal('E2', 'S5', 'rectum', 'rectum'),
                       removal('E3', 'S6', 'sigmoid_colon', 'sigmoid colon'),
                       removal('E4', 'S7', 'transverse_colon', 'transverse colon'))


ANSWERS = {**TJ.ANSWERS, THREE: three_answer}


def leaving(*keys):
    """test_settle's faithful pass 2, with no verdict for each fact claim of ``keys`` (object, attribute): the fact is
    unresolved for appraisal:missing (C2a), a reading the question stage asks."""
    def oracle(claim, role, claim_set):
        missing = {item.claim for item in claim_set.appraised if (item.key.object, item.key.attribute) in keys}
        return None if claim.id in missing else faithful(claim, role, claim_set)
    return oracle


def oracle_quote(text, passage):
    """qstage's release-all quote: the text of a passage's first range (whitespace runs as one space), cut at its last
    space within 300 characters; '' when it holds no such words."""
    for start, end in getattr(passage, 'ranges', ()):
        words = ' '.join(text[start:end].split())
        if len(words) > QUOTE_MAX_CHARS:
            cut = words[:QUOTE_MAX_CHARS + 1]
            words = cut[:cut.rfind(' ')] if ' ' in cut else ''
        if len(words.split()) >= QUOTE_MIN_TOKENS and sum(1 for char in words if not char.isspace()) >= QUOTE_MIN_CHARS:
            return words
    return ''


def question_answer(question, text, pattern='release'):
    """The answer object of one question request: 'release' - every question's claim supported with a quote from each
    passage its proof needs, its control contradicted, every calibration item in the holding direction; 'unclear' -
    every verdict unclear; 'holding' - every claim contradicted and every control supported (the holding direction);
    'breach' - 'release' with the first calibration item's false claim supported; 'incoherent' - 'release' with every
    question's control supported too."""
    verdicts = []
    calibration_seen = False
    for item in question.items:
        if pattern == 'unclear':
            pairs = [(item.claim, 'unclear', []), (item.control, 'unclear', [])]
        elif pattern == 'holding':
            pairs = [(item.claim, 'contradicts', []), (item.control, 'supports', [])]
        elif item.role == 'calibration':
            claim = 'contradicts'
            if pattern == 'breach' and not calibration_seen:
                claim = 'supports'
            calibration_seen = True
            pairs = [(item.claim, claim, []), (item.control, 'supports', [])]
        else:
            passages = list(item.required) or list(item.alternatives[:1])
            quotes = [found for found in (oracle_quote(text, passage) for passage in passages) if found]
            pairs = [(item.claim, 'supports', quotes[:2]),
                     (item.control, 'supports' if pattern == 'incoherent' else 'contradicts', [])]
        for claim_id, value, quotes in pairs:
            verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': quotes})
    verdicts.sort(key=lambda node: int(node['claim'][1:]))
    return {'verdicts': verdicts, 'unlisted': []}


class QuestionInterpreter(TJ.ScriptedInterpreterV2):
    """test_jobs' scripted connector for both passes; a QUESTION request (fable_adapter.request_kind) answered over the
    QuestionRequest the stage built (``built``, by request sha256) by ``pattern``, unless ``question_script`` holds a
    callable (sha, question) -> RawExchange for it, taken in turn. ``barrier``: when set, every question send waits there
    (so only sends in flight together pass it); ``probe``: called from the sending thread before it answers.
    ``question_sent``: the sha256 of every question request sent, in the order the sends began."""

    def __init__(self, answers, *, oracle, built, pattern='release', question_script=None, barrier=None, probe=None):
        super().__init__(answers, oracle=oracle)
        self.built, self.pattern = built, pattern
        self.question_script = list(question_script or [])
        self.barrier, self.probe = barrier, probe
        self.question_sent = []
        self.threads = []
        self.guard = threading.Lock()

    def _exchange(self, body_dict, deadline, purpose):
        if fable_adapter.request_kind(body_dict)[0] != fable_adapter.QUESTION:
            return super()._exchange(body_dict, deadline, purpose)
        sha = request_sha256(body_dict)
        with self.guard:
            self.question_sent.append(sha)
            self.threads.append(threading.current_thread().name)
            scripted = self.question_script.pop(0) if self.question_script else None
        if self.barrier is not None:
            self.barrier.wait(timeout=20)
        if self.probe is not None:
            self.probe()
        question = self.built[sha]
        if scripted is not None:
            return scripted(sha, question)
        text = question.request.contexts[0]
        return TJ.answered(TJ.body(question_answer(question, text, self.pattern)))


def capturing(built):
    """A spy over jobs._question_state that keeps every owed request's QuestionRequest by its sha256 (the parent side of
    the stage: what the child computed and handed back)."""
    real = jobs._question_state

    def spy(job, extraction, fields):
        state = real(job, extraction, fields)
        if state[0] == 'owed':
            for item in state[1]['requests']:
                built[item['request'].canonical_sha256] = item['question']
        return state
    return spy


def one_question_bound():
    """The claims of a request of ONE question with its calibration (asking.calibration_count), so the partition puts
    every question in a request of its own."""
    return 2 * (1 + asking.calibration_count(1))


class QuestionCase(TJ.PipelineCase):
    """test_jobs' v2 pipeline with the question stage: a question-answering connector, the stage's requests captured."""

    def setUp(self):
        super().setUp()
        self.built = {}
        self.enterContext(mock.patch.object(jobs, '_question_state', side_effect=capturing(self.built)))
        self.provider = TJ.FakeProvider([('45378', TJ.EXAM), ('45385', TJ.SNARE)])

    def questioned(self, *keys, **kwargs):
        interpreter = QuestionInterpreter(ANSWERS, oracle=leaving(*keys), built=self.built, **kwargs)
        patcher = mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.interpreter = interpreter
        return interpreter

    def to_questions(self, *keys, text=TJ.POLYP, **kwargs):
        """``text`` (POLYP) uploaded and read through pass 2, its pass 2 leaving ``keys`` unanswered: the appraise stage
        has queued the question stage's round 1 (returned)."""
        self.questioned(*keys, **kwargs)
        encounter, revision = self.upload(text)
        for kind in ('extract', 'interpret', 'appraise'):
            done = self.run_next(kind)
        queued = list(Job.objects.filter(encounter=encounter, state=Job.QUEUED))
        self.assertEqual([job.kind for job in queued], [QUESTION], (done.state, done.error, done.result))
        return encounter, revision, queued[0]

    def question_runs(self, encounter):
        return [run for run in Run.objects.filter(encounter=encounter, purpose=fable_adapter.APPRAISAL)
                .order_by('created_at', 'pk') if 'question' in (run.scope or {})]

    def finish(self, encounter):
        done = self.drain()
        encounter.refresh_from_db()
        return done

    def status(self, encounter, code):
        encounter.refresh_from_db()
        return encounter.current_assessment.proposals.get(code=code).status


# --- the pipeline: questions planned, sent, established, read as facts -----------------------------------------------


class QuestionPipelineTests(QuestionCase):
    def test_a_reading_hold_is_asked_established_and_read_as_a_fact_so_the_code_goes_ready(self):
        """The must-change input: E2's session left unanswered by pass 2 holds 45385; the stage asks it, Fable's answer
        supports it with E2's own words and contradicts its exact negation, and the engine reads it as a fact: READY."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())  # no row before the end
        done = self.finish(encounter)
        self.assertEqual([job.kind for job in done], [QUESTION, 'analyze', 'predict', 'assess'],
                         [(job.kind, job.state, job.error, job.result) for job in done])
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        [record] = inventory.events['questions']
        self.assertEqual((record['family'], record['attribute'], record['subjects'], record['result']),
                         ('Q-FACT', 'session', ['E2'], 'supported'))
        self.assertEqual(self.status(encounter, '45385'), 'ready')
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.sent, run.purpose, run.scope['question']['round']),
                         (Run.SUCCEEDED, True, 'appraisal', 1))
        self.assertEqual(run.request_body['output_config']['effort'], 'max')  # D306, D320: effort max
        self.assertEqual(run.request_body['max_tokens'], 128000)

    def test_the_same_hold_with_an_unestablished_answer_stays_held(self):
        """The boundary: the same document whose question is answered in the holding direction - nothing established -
        keeps 45385 held, with its question unresolved (recorded held_by_answer, read by nothing) and the row written
        once."""
        encounter, revision, queued = self.to_questions(SESSION_E2, pattern='holding')
        self.finish(encounter)
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        [record] = inventory.events['questions']
        self.assertEqual((record['result'], record['reasons'], record['held_by_answer']),
                         ('unresolved', ['question_contradicts'], True))
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a_document_with_nothing_open_is_written_as_before_with_no_question_stage(self):
        """Round 1's plan empty: the row is written exactly as before r3 (no question field), no question job."""
        self.scripted()
        encounter, revision = self.upload(TJ.POLYP)
        done = self.drain()
        self.assertNotIn(QUESTION, [job.kind for job in done])
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        self.assertNotIn('questions', inventory.events)
        self.assertNotIn('question_runs', inventory.verification)

    def test_an_answer_with_every_verdict_unclear_is_an_unhealthy_request(self):
        # restated at round r3's integration (the ask lane's D319 item beside this lane's stage): a request now carries
        # ONE calibration item (DECISIONS D319), so this request is one question and one item - 2 pairs, under settle's
        # CONTROL_MIN 4, so H4 (controls not rejected) does not read it and the request's health refuses nothing; its
        # question is unresolved by its OWN verdict (d.2 row 2: question_unclear) and 45385 stays held, as before. With
        # the prototype's four items (5 pairs) H4 refused the request (question_health:controls)
        encounter, revision, queued = self.to_questions(SESSION_E2, pattern='unclear')
        self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        [record] = inventory.events['questions']
        self.assertEqual((record['result'], record['reasons']), ('unresolved', ['question_unclear']))
        [health] = inventory.verification['question_health']
        self.assertEqual((health['measures']['pairs'], health['refused']), (2, []))
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_an_incoherent_answer_establishes_nothing(self):
        encounter, revision, queued = self.to_questions(SESSION_E2, pattern='incoherent')
        self.finish(encounter)
        [record] = models.EventInventory.objects.get(revision=revision).events['questions']
        self.assertEqual((record['result'], record['reasons']), ('unresolved', ['question_incoherent']))
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')


class CalibrationAndFailureTests(QuestionCase):
    def test_a_calibration_breach_refuses_its_request_and_its_questions_stay_unresolved(self):
        """H2: the request's known-false calibration claim supported - every question of the request unresolved, its
        health refused, the code held, though each question's own pattern would establish it."""
        encounter, revision, queued = self.to_questions(SESSION_E2, pattern='breach')
        self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        [record] = inventory.events['questions']
        self.assertEqual((record['result'], record['reasons']), ('unresolved', ['question_health:calibration']))
        self.assertTrue(any(item['breach'] for item in inventory.events['calibration']))
        [health] = inventory.verification['question_health']
        self.assertIn('question_health:calibration', health['refused'])
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a_failed_request_leaves_its_questions_unresolved_and_the_stage_goes_on(self):
        """e.5: an HTTP 500 - the request fails alone, its question unresolved (question_request_failed:failed), the row
        written and the document assessed with the hold kept; nothing is sent again."""
        failing = [lambda sha, question: TJ.answered(TJ.HTTP_500, status=500)]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=failing)
        done = self.finish(encounter)
        self.assertEqual([job.kind for job in done][-1], 'assess')
        [record] = models.EventInventory.objects.get(revision=revision).events['questions']
        self.assertEqual(record['reasons'], ['question_request_failed:failed'])
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a_failed_question_request_is_never_the_readings_retry_attempt(self):
        """A failed question request is no reading attempt: a member's retry of the reading answers the pass-2 run, with
        nothing to release - never a question request re-sent through pass 2's door."""
        failing = [lambda sha, question: TJ.answered(TJ.HTTP_500, status=500)]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=failing)
        self.finish(encounter)
        [question_run] = self.question_runs(encounter)
        self.assertEqual(question_run.state, Run.FAILED)
        newest, released = jobs.retry_target(revision)
        self.assertNotEqual(newest.pk, question_run.pk)
        self.assertEqual((newest.purpose, 'question' in (newest.scope or {})), (fable_adapter.APPRAISAL, False))
        self.assertIsNone(released)

    def test_a_hold_setting_answer_records_the_hold_and_pauses_the_stage_deciding_nothing(self):
        """A 402 (billing): the installation-wide hold recorded from the question run, which decides nothing (the
        repair pass's PIPE-R1, restated by its owning function jobs._question_outcome; was: its question unresolved,
        question_request_failed:hold): the stage pauses (CANCELLED, the paused phase), no row is written and the
        request stays owed - tests/v2/test_question_repair.py pins the release and the Resume that sends it again."""
        holding = [lambda sha, question: TJ.answered(TJ.HTTP_402, status=402)]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=holding)
        done = self.run_next(QUESTION)
        self.assertTrue(interpretation_holds.is_held())
        self.assertEqual((done.state, done.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE))
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())
        [run] = self.question_runs(encounter)
        self.assertIsNone(jobs._question_outcome(run))

    def test_an_unknown_outcome_blocks_the_stage_until_it_is_reconciled(self):
        """A send its deadline cut (unknown): the next step is blocked by the unknown-outcome block, sends nothing; a
        member's reconciliation releases exactly one new attempt of that request."""
        cut = [lambda sha, question: TJ.UNKNOWN]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=cut)
        self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.state, Run.UNKNOWN)
        follow = self.run_next(QUESTION)
        self.assertEqual(follow.result, {'blocked': jobs.INTERPRET_BLOCKED})
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertTrue(jobs.reconcile(encounter, run, self.user, 'checked with the vendor'))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 2)  # the one attempt the reconciliation allowed
        self.assertEqual(self.status(encounter, '45385'), 'ready')


class SplitTests(QuestionCase):
    def test_an_overrun_is_split_in_halves_and_each_half_is_sent_once(self):
        """e.4: a request of two questions cut at its output limit is never read and never re-sent as it is; its halves
        (one question each) are sent as further requests of the same round and settled."""
        cut = [lambda sha, question: TJ.answered(answer_stream('', stop_reason='max_tokens'))]
        encounter, revision, queued = self.to_questions(SESSION_E2, SESSION_E1, question_script=cut)
        self.assertEqual([len([item for item in question.items if item.role == 'question'])
                          for question in self.built.values()], [2])
        self.finish(encounter)
        sent = self.interpreter.question_sent
        self.assertEqual(len(sent), 3)
        self.assertEqual(len(set(sent)), 3)  # the cut request never again
        inventory = models.EventInventory.objects.get(revision=revision)
        runs = inventory.verification['question_runs']
        self.assertEqual([item['outcome'] for item in runs], ['too_long', 'answered', 'answered'])
        self.assertEqual([item['split_of'] for item in runs[1:]], [runs[0]['request_sha256']] * 2)
        self.assertEqual({item['result'] for item in inventory.events['questions']}, {'supported'})

    def test_a_request_of_one_question_that_overruns_leaves_it_unresolved(self):
        cut = [lambda sha, question: TJ.answered(answer_stream('', stop_reason='max_tokens'))]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=cut)
        self.finish(encounter)
        [record] = models.EventInventory.objects.get(revision=revision).events['questions']
        self.assertEqual(record['reasons'], ['question_request_failed:too_long'])
        self.assertEqual(len(self.interpreter.question_sent), 1)


# --- one job per round: concurrent sends, one lock, one reservation, then the next round --------------------------------


def two_rounds(first):
    """engine/asking.plan staged in two rounds, deterministically: round 1 (nothing asked yet) plans the first
    ``first`` questions, later rounds the rest - what a planner that finds new witnesses after round 1's answers does."""
    real = asking.plan

    def plan(R, asked_before=(), events=None, carded=None):
        found = real(R, asked_before, events, carded=carded)
        if not tuple(asked_before):
            keep = found.specs[:first]
            return dataclasses.replace(found, specs=keep,
                                       serves={key: value for key, value in found.serves.items()
                                               if key in {spec.key for spec in keep}})
        return found
    return plan


class ConcurrencyTests(QuestionCase):
    def test_a_round_of_three_requests_is_sent_concurrently_by_one_job_under_one_lock_and_one_reservation(self):
        """D322 (1)-(3): round 1's three requests (one question each) sent by ONE job, in flight together (each send waits
        at a barrier of three), each while the installation-wide provider lock is held by the job's one session, after
        ONE reservation of all three worst cases; then the same job plans round 2 and queues it once; round 2's job
        sends its one request and writes the row."""
        holders = []

        def probe():
            from django.db import connections

            try:
                with connections['default'].cursor() as cursor:
                    # this test database's lock only: an advisory lock's tag names its database, and other test
                    # databases on the same server may hold the same key at the same time
                    cursor.execute("SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND granted AND objsubid = 1 "
                                   'AND database = (SELECT oid FROM pg_database WHERE datname = current_database()) '
                                   'AND (classid::bigint << 32) + objid::bigint = %s', [jobs.PROVIDER_LOCK_KEY])
                    holders.append(tuple(row[0] for row in cursor.fetchall()))
            finally:
                connections['default'].close()
        budget = []
        real_budget = jobs._question_budget_refusal

        def counted(worst):
            budget.append(list(worst))
            return real_budget(worst)
        with mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                               ConcurrencyTests.partition(specs, pool, round_)), \
                mock.patch.object(asking, 'plan', side_effect=two_rounds(3)), \
                mock.patch.object(jobs, '_question_budget_refusal', side_effect=counted):
            encounter, revision, queued = self.to_questions(SESSION_E2, SESSION_E3, SESSION_E4, SESSION_E1,
                                                            text=THREE, barrier=threading.Barrier(3), probe=probe)
            first = self.run_next(QUESTION)
            self.assertEqual((first.state, first.result['round'], first.result['sent']), (Job.SUCCEEDED, 1, 3),
                             (first.error, first.result))
            self.assertEqual(len(self.interpreter.question_sent), 3)
            self.assertEqual(len(set(self.interpreter.threads)), 3)  # one thread per request
            self.assertEqual(len(holders), 3)
            self.assertEqual({len(found) for found in holders}, {1})  # one holder of the lock ...
            self.assertEqual(len({found[0] for found in holders}), 1)  # ... the same session for every send
            self.assertEqual([len(item) for item in budget], [3])  # ONE reservation of all three worst cases
            [second] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
            self.assertEqual((second.kind, jobs._question_parts(second)[1]), (QUESTION, 2))
            self.interpreter.barrier = None
            self.run_next(QUESTION)
            self.assertEqual(len(self.interpreter.question_sent), 4)
            self.assertEqual([len(item) for item in budget], [3, 1])
            self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual([(item['round'], item['batch']) for item in inventory.verification['question_runs']],
                         [(1, 1), (1, 2), (1, 3), (2, 1)])
        self.assertEqual(Job.objects.filter(encounter=encounter, kind=QUESTION).count(), 2)  # one job per round

    @staticmethod
    def partition(specs, pool, round_):
        return REAL_PARTITION(specs, pool, round_, bound=one_question_bound())


REAL_PARTITION = asking.partition  # the production partition, given the one-question bound above


class BudgetTests(QuestionCase):
    """D322 (1), e.8: the combined reservation against the threshold - the budget check and the reservation in one
    transaction, so a round's requests never pass the cap together."""

    def round_of_three(self, cap_over):
        with mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                               ConcurrencyTests.partition(specs, pool, round_)):
            encounter, revision, queued = self.to_questions(SESSION_E2, SESSION_E3, SESSION_E4, text=THREE)
            worst = [Decimal(fable_adapter.worst_case_usd(question.request)) for question in self.built.values()]
            self.assertEqual(len(worst), 3)
            spent = jobs.account_month_spend()
            cap = spent + cap_over(worst)
            with override_settings(QUESTION_PROVIDER_CAP_USD=str(cap), QUESTION_SITE_RESERVE_USD='0',
                                   QUESTION_OTHER_SPEND_USD='0'):
                job = self.run_next(QUESTION)
        return encounter, revision, job

    def test_a_round_whose_worst_cases_together_pass_the_cap_sends_nothing(self):
        """Each request alone fits (the cap leaves room for two and a half), all three together do not: nothing is
        sent, every request recorded not sent (refused), their questions unresolved and the codes held."""
        encounter, revision, job = self.round_of_three(lambda worst: max(worst) * Decimal('2.5'))
        self.assertEqual(self.interpreter.question_sent, [])
        runs = self.question_runs(encounter)
        self.assertEqual({(run.state, run.sent, run.scope.get('refused')) for run in runs},
                         {(Run.NOT_SENT, False, jobs.QUESTION_BUDGET)})
        self.assertEqual(len(runs), 3)
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual({tuple(item['reasons']) for item in inventory.events['questions']},
                         {('question_request_failed:refused',)})

    def test_a_round_whose_worst_cases_together_fit_exactly_is_sent(self):
        encounter, revision, job = self.round_of_three(lambda worst: sum(worst))
        self.assertEqual(len(self.interpreter.question_sent), 3)

    def test_no_threshold_configured_checks_nothing(self):
        self.assertEqual(jobs._question_budget_refusal(['999.000000']), '')
        with override_settings(QUESTION_PROVIDER_CAP_USD='10', QUESTION_SITE_RESERVE_USD='0'):
            self.assertEqual(jobs._question_budget_refusal([None]), jobs.QUESTION_UNBOUNDED_MESSAGE)
            self.assertNotEqual(jobs._question_budget_refusal(['10.000001']), '')
            self.assertEqual(jobs._question_budget_refusal(['10.000000']), '')


class CrashTests(QuestionCase):
    def test_a_crash_after_the_sends_is_finished_by_the_settled_path_with_no_second_send(self):
        """The worker dies after the round's outcomes are recorded and before the stage queues what follows: the startup
        sweep queues its settled path, which recomputes the stage from the stored runs and writes the row - nothing is
        sent again."""
        encounter, revision, queued = self.to_questions(SESSION_E2)

        class Died(BaseException):
            pass
        job = jobs.claim_next()
        with mock.patch.object(jobs, '_settle_question_run', side_effect=Died):
            with self.assertRaises(Died):
                jobs.run_job(job)
        self.assertEqual(Job.objects.get(pk=job.pk).state, Job.RUNNING)
        jobs.mark_stale(startup=True)
        self.assertEqual(Job.objects.get(pk=job.pk).state, Job.SUCCEEDED)
        [settled] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertIn(':settled:', settled.idempotency_key)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_settled_path_whose_round_still_owes_requests_sends_nothing(self):
        """The worker dies after an overrun's outcome was recorded and before the stage queued its halves: the startup
        sweep's settled path recomputes the stage, finds the halves owed and stops, resumable - it never sends and never
        queues a stage that would; a Resume then sends each half once."""
        cut = [lambda sha, question: TJ.answered(answer_stream('', stop_reason='max_tokens'))]
        encounter, revision, queued = self.to_questions(SESSION_E2, SESSION_E1, question_script=cut)

        class Died(BaseException):
            pass
        job = jobs.claim_next()
        with mock.patch.object(jobs, '_settle_question_run', side_effect=Died):
            with self.assertRaises(Died):
                jobs.run_job(job)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        jobs.mark_stale(startup=True)
        self.assertEqual(Job.objects.get(pk=job.pk).state, Job.SUCCEEDED)
        [settled] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertIn(':settled:', settled.idempotency_key)
        self.drain()
        settled.refresh_from_db()
        self.assertEqual(settled.state, Job.CANCELLED, (settled.error, settled.result))
        self.assertEqual(len(self.interpreter.question_sent), 1)  # the settled path sent nothing
        self.assertFalse(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)).exists())
        jobs.resume(encounter, self.user)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 3)  # the two halves, each once
        self.assertEqual(len(set(self.interpreter.question_sent)), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_crash_mid_send_leaves_an_unknown_outcome_and_a_resume_sends_nothing(self):
        """The worker dies while the request is in flight: the startup sweep records its run unknown and the stage
        unknown; a Resume is not offered (the outcome is being confirmed) and nothing is sent until a reconciliation."""
        encounter, revision, queued = self.to_questions(SESSION_E2)

        class Died(BaseException):
            pass
        job = jobs.claim_next()
        with mock.patch.object(jobs, '_finish_question_run', side_effect=Died):
            with self.assertRaises(Died):
                jobs.run_job(job)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.state, Run.SENDING)
        jobs.mark_stale(startup=True)
        run.refresh_from_db()
        self.assertEqual((run.state, Job.objects.get(pk=job.pk).state), (Run.UNKNOWN, Job.UNKNOWN))
        self.assertIsNone(jobs.resume(encounter, self.user))
        self.assertEqual(self.drain(), [])
        self.assertEqual(len(self.interpreter.question_sent), 1)

    def test_a_stopped_stage_resumes_from_its_stored_runs_without_sending_again(self):
        """A member's Stop before the round's send, then Resume: the stage recomputes and sends each request once."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        jobs.stop_encounter(encounter, self.user)
        queued.refresh_from_db()
        self.assertEqual(queued.state, Job.CANCELLED)
        self.assertEqual(self.drain(), [])
        self.assertEqual(self.interpreter.question_sent, [])
        jobs.resume(encounter, self.user)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertEqual(self.status(encounter, '45385'), 'ready')


class DeadlineTests(QuestionCase):
    def test_a_round_that_would_outlast_its_stage_budget_is_queued_again_before_anything_is_reserved(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        job = jobs.claim_next()
        late = settings.JOB_DEADLINE_SECONDS[QUESTION] - settings.QUESTION_SEND_DEADLINE_SECONDS
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=late))
        job.refresh_from_db()
        done = jobs.run_job(job)
        self.assertEqual((done.state, done.result), (Job.QUEUED, {'requeued': jobs.LOOP_LATE_MESSAGE}))
        self.assertEqual(self.question_runs(encounter), [])

    def test_a_round_that_fits_its_budget_is_sent(self):
        """The boundary: started with the question send, its recording and a second to spare inside the budget."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        job = jobs.claim_next()
        spare = (settings.JOB_DEADLINE_SECONDS[QUESTION] - settings.QUESTION_SEND_DEADLINE_SECONDS
                 - jobs.LOOP_RECORDING_SECONDS - 30)
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=spare))
        job.refresh_from_db()
        self.assertEqual(jobs.run_job(job).state, Job.SUCCEEDED)
        self.assertEqual(len(self.interpreter.question_sent), 1)

    def test_the_question_send_is_given_its_own_deadline(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        seen = []
        real = fable_adapter.InterpreterF.send_loop

        def spy(interpreter, request, **kwargs):
            seen.append((kwargs['deadline_s'], interpreter.longest_s(request.body, fable_adapter.APPRAISAL)))
            return real(interpreter, request, **kwargs)
        with mock.patch.object(QuestionInterpreter, 'send_loop', autospec=True, side_effect=spy):
            self.run_next(QUESTION)
        self.assertEqual(seen, [(settings.QUESTION_SEND_DEADLINE_SECONDS, settings.QUESTION_SEND_DEADLINE_SECONDS)])


class RateTests(QuestionCase):
    def answered_at(self, output_tokens, seconds):
        def answer(sha, question):
            exchange = TJ.answered(TJ.body(question_answer(question, question.request.contexts[0])))
            usage = {**copy.deepcopy(exchange.usage), 'output_tokens': output_tokens}
            return dataclasses.replace(exchange, usage=usage, latency_ms=seconds * 1000)
        return answer

    def test_a_question_stream_below_the_rate_floor_is_measured_never_a_hold(self):
        """D310 (9), D320: 50 tokens a second is recorded on the run as below the floor; no hold, the stage goes on."""
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=[self.answered_at(1000, 20)])
        self.finish(encounter)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.scope['question']['rate'], {'tokens_per_second': 50.0, 'below_floor': True})
        self.assertFalse(interpretation_holds.is_held())
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_question_stream_above_the_floor_is_measured_above_it(self):
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=[self.answered_at(3000, 20)])
        self.finish(encounter)
        [run] = self.question_runs(encounter)
        self.assertEqual(run.scope['question']['rate'], {'tokens_per_second': 150.0, 'below_floor': False})


# --- the ONE row binds every run ------------------------------------------------------------------------------------------


class BindingTests(QuestionCase):
    def test_the_row_binds_every_question_run_by_its_run_request_and_response(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        named = inventory.verification['question_runs']
        runs = self.question_runs(encounter)
        self.assertEqual([(item['provider_run_id'], item['request_sha256'], item['response_sha256']) for item in named],
                         [(str(run.pk), run.request_sha256, run.response_sha256) for run in runs])
        self.assertEqual(jobs._question_runs_bound(store.fields_of_v2(inventory), encounter), '')

    def test_a_row_naming_a_run_as_it_was_not_recorded_is_refused(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        [run] = self.question_runs(encounter)
        Run.objects.filter(pk=run.pk).update(response_sha256='0' * 64)
        self.assertNotEqual(jobs._question_runs_bound(store.fields_of_v2(inventory), encounter), '')
        with self.assertRaises(jobs.StageFailure):
            jobs._stored_inventory(inventory, revision)

    def test_the_store_refuses_a_supported_question_its_request_does_not_establish(self):
        """The RF-L4 pattern for questions: a stored record supported while its request's health refuses - or its
        control was not contradicted - is refused at load; the record as settled loads."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.finish(encounter)
        inventory = models.EventInventory.objects.get(revision=revision)
        fields = store.fields_of_v2(inventory)
        appraised = Run.objects.get(pk=inventory.appraisal_run_id).response_sha256

        def load(changed):
            changed['sha256'] = store.content_sha256_v2(changed)
            return store.load_v2(changed, text_sha256=fields['text_sha256'], response_sha256=fields['response_sha256'],
                                 appraisal_response_sha256=appraised)
        load(copy.deepcopy(fields))  # as written
        unhealthy = copy.deepcopy(fields)
        unhealthy['verification']['question_health'][0]['refused'] = ['question_health:controls']
        with self.assertRaises(store.StoreError):
            load(unhealthy)
        incoherent = copy.deepcopy(fields)
        incoherent['events']['questions'][0]['verdicts']['control'] = 'supports'
        with self.assertRaises(store.StoreError):
            load(incoherent)
        orphan = copy.deepcopy(fields)
        orphan['verification']['question_runs'][0]['round'] = 7
        with self.assertRaises(store.StoreError):
            load(orphan)


# --- the connector's question request kind ----------------------------------------------------------------------------


class ReportTests(QuestionCase):
    """DESIGN-v2 (i): the operator report names, per code, the witnesses established questions released with their
    located spans (the revision's own words at them), each unestablished question's reasons, the calibration and each
    request's health - and names nothing for a row without the stage."""

    def section(self, encounter):
        from studio.interpretation import report
        encounter.refresh_from_db()
        return report.interpretation_section_v2(encounter.current_assessment)['questions']

    def test_the_report_names_the_released_witness_its_spans_and_its_requests_health(self):
        """The must-change input: E2's established session releases 45385, named with its witness and its words."""
        from studio.interpretation import report
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.finish(encounter)
        found = self.section(encounter)
        self.assertEqual((found['asked'], found['established']), (1, 1))
        [released] = found['codes']['45385']['released']
        self.assertEqual(found['codes']['45385']['unestablished'], [])
        self.assertEqual((released['question']['family'], released['question']['attribute'],
                          released['question']['subjects']), ('Q-FACT', 'session', ['E2']))
        self.assertTrue(released['spans'])
        revision.refresh_from_db()  # its text, as the extract stage stored it
        for span in released['spans']:
            self.assertEqual(span['words'], revision.text[span['start']:span['end']])
            self.assertTrue(span['words'].strip())
        [request] = found['requests']
        [run] = self.question_runs(encounter)
        self.assertEqual((request['run'], request['round'], request['batch']), (str(run.pk), 1, 1))
        self.assertEqual(request['health']['refused'], [])
        self.assertIn('tokens_per_second', request['rate'])
        self.assertTrue(found['calibration'])
        self.assertFalse([item for item in found['calibration'] if item['breach']])
        lines = report.render_questions(found)
        self.assertTrue([line for line in lines if line.startswith('question code 45385: released')], lines)

    def test_an_unestablished_question_is_named_with_its_reasons_and_releases_nothing(self):
        """The boundary: the same question answered in the holding direction releases nothing; its reason is named."""
        from studio.interpretation import report
        encounter, revision, queued = self.to_questions(SESSION_E2, pattern='holding')
        self.finish(encounter)
        found = self.section(encounter)
        self.assertEqual((found['asked'], found['established']), (1, 0))
        entry = found['codes']['45385']
        self.assertEqual(entry['released'], [])
        self.assertEqual([item['reasons'] for item in entry['unestablished']], [['question_contradicts']])
        lines = report.render_questions(found)
        self.assertFalse([line for line in lines if 'released' in line], lines)
        self.assertTrue([line for line in lines if line.startswith('question code 45385: not established')], lines)

    def test_a_row_without_the_stage_reports_no_questions(self):
        self.scripted()
        encounter, revision = self.upload(TJ.POLYP)
        self.drain()
        self.assertIsNone(self.section(encounter))


class AdapterTests(SimpleTestCase):
    def test_the_question_deadline_is_derived_from_the_whole_output_at_95_tokens_a_second(self):
        """D322 (4): ceil(128,000 / 95) + 60 = 1,408 s, the module constant and the settings equal to it."""
        derived = fable_adapter.question_deadline_derivation()
        self.assertEqual(derived, {'max_tokens': 128000, 'rate': 95, 'stream_seconds': 1348, 'tail_seconds': 60,
                                   'deadline': 1408})
        self.assertEqual(fable_adapter.QUESTION_SEND_DEADLINE_SECONDS, 1408)
        self.assertEqual((settings.QUESTION_SEND_DEADLINE_SECONDS, settings.QUESTION_READ_TIMEOUT_SECONDS),
                         (1408, 1408))
        self.assertLess(fable_adapter.QUESTION_DEADLINE_RATE, 101.04)  # below the slowest measured max-effort rate

    def test_the_stage_rows_sit_above_the_question_send(self):
        send, child = settings.QUESTION_SEND_DEADLINE_SECONDS, settings.QUESTION_CHILD_SECONDS
        stage = settings.JOB_DEADLINE_SECONDS[QUESTION]
        self.assertEqual(stage, send + jobs.LOOP_RECORDING_SECONDS + child + 45)
        self.assertEqual(settings.STALE_RUNNING_SECONDS_BY_KIND[QUESTION], stage + child + 60)
        self.assertEqual(jobs.stale_threshold(QUESTION), stage + child + 60)
        self.assertGreater(jobs.stale_threshold(QUESTION), stage)
        self.assertGreater(jobs.stale_threshold('appraise'), settings.JOB_DEADLINE_SECONDS['appraise'] + child)

    def test_the_live_interpreter_reads_the_question_rows_and_the_replay_one_its_deadline(self):
        with override_settings(GEMINI_MODE='live', ANTHROPIC_CREDENTIALS_FILE='/nonexistent/anthropic.env',
                               QUESTION_SEND_DEADLINE_SECONDS=1400, QUESTION_READ_TIMEOUT_SECONDS=1390):
            live = fable_adapter.get_interpreter_v2()
        self.assertEqual((live.question_send_deadline, live.question_read_timeout), (1400, 1390))
        self.assertEqual(set(live.send_deadlines), {'interpretation', 'appraisal'})  # the passes' rows unchanged
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent-replay-dir',
                               QUESTION_SEND_DEADLINE_SECONDS=1401):
            replay = fable_adapter.get_interpreter_v2()
        self.assertEqual(replay.question_send_deadline, 1401)

    def test_a_question_body_is_an_appraisal_run_of_its_own_kind(self):
        from tests.v2.test_r3_probe import REL, stub_request

        built = stub_request([REL])
        self.assertEqual(fable_adapter.body_kind(built.request.body), (fable_adapter.APPRAISAL, ''))
        self.assertEqual(fable_adapter.request_kind(built.request.body), (fable_adapter.QUESTION, ''))
        interpreter = fable_adapter.InterpreterF()
        self.assertEqual(interpreter.longest_s(built.request.body, fable_adapter.APPRAISAL),
                         fable_adapter.QUESTION_SEND_DEADLINE_SECONDS)
        altered = copy.deepcopy(built.request.body)
        altered['output_config']['effort'] = 'high'  # a question request is never sent below effort max
        self.assertEqual(fable_adapter.request_kind(altered)[0], '')

    def test_the_worst_case_is_the_body_bound_and_the_whole_output(self):
        from tests.v2.test_r3_probe import REL, stub_request

        from studio.providers.base import canonical_body

        built = stub_request([REL])
        usage = fable_adapter.worst_usage(built.request)
        self.assertEqual(usage['output_tokens'], 128000)
        # a question body marks no cache prefix: every byte of its canonical body an input token, plus the margin
        self.assertEqual((usage['input_tokens'], usage['cache_creation_input_tokens']),
                         (len(canonical_body(built.request.body)) + fable_adapter.PROMPT_MARGIN_TOKENS, 0))
        self.assertGreater(Decimal(fable_adapter.worst_case_usd(built.request)), Decimal('5.12'))
        self.assertIsNone(fable_adapter.worst_case_usd(dataclasses.replace(built.request, body={'max_tokens': 0})))


class SurfaceTests(SimpleTestCase):
    def test_no_new_customer_or_reviewer_string_names_the_question_stage(self):
        """(i): the question stage's job errors and results - what progress and the reviewer can read - name no
        provider, question, proof or answer (they say 'the check of the reading', as pass 2's do)."""
        for name in ('QUESTION_NOT_READ_MESSAGE', 'QUESTION_MOVED', 'QUESTION_SETTLED_MESSAGE',
                     'QUESTION_UNBUILT_MESSAGE', 'QUESTION_ROUNDS_MESSAGE', 'QUESTION_BUDGET_MESSAGE',
                     'QUESTION_UNBOUNDED_MESSAGE', 'QUESTION_LATE_MESSAGE'):
            words = getattr(jobs, name).lower()
            with self.subTest(name=name):
                self.assertFalse([word for word in FORBIDDEN if word in words], words)

    def test_the_question_kind_is_a_context_free_reading_stage(self):
        self.assertIn(QUESTION, jobs.READING_KINDS)
        self.assertIs(jobs.STAGES[QUESTION], jobs.stage_question)
        self.assertEqual(jobs.SENDING_PURPOSES[QUESTION], interpretation.APPRAISAL_PURPOSE)
        self.assertLessEqual(len(QUESTION), Job._meta.get_field('kind').max_length)
        key = jobs._question_key('0' * 8 + '-0000-0000-0000-' + '0' * 12, 8, 'f' * 16,
                                 f'after-reconcile:{"0" * 36}:resume:{"0" * 36}')
        self.assertLessEqual(len(key), Job._meta.get_field('idempotency_key').max_length)


def tracebacks_free(text):  # pragma: no cover - a reading aid for failures
    return '\n'.join(line for line in text.splitlines() if 'Traceback' not in line)
