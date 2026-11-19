"""Round r3's build, the third repair (DECISIONS D325 (3)), lane 'pipe': the second adversarial pass's L7P2-2 (one
note's question round reserved and sent hundreds of max-effort requests at once, with no cost door), repaired as the two
class rules D325 (3) rules, each pinned by the finding's own input first, then by other members of its class and by its
boundary. TEXT-ONLY and SYNTHETIC: every document is test_jobs' POLYP, test_question_stage's THREE note or a note the
finding's generator writes (fictional names, generated sentences; ported from the attacker's tests/v2/test_l7p_pipe.py),
driven through the question stage's own scaffolding (test_question_stage.QuestionCase: the production Fable connector,
fable_adapter.InterpreterF, its one exchange scripted). NOTHING is sent to any provider.

THE PER-DOCUMENT CEILING (settings.QUESTION_DOCUMENT_CEILING_USD; class d, the owner's figure: 25 US dollars). The
question stage reserves at most that much worst case for one document - its revision - over every round
(jobs._ceiling_refusal over jobs._document_reserved_usd): a round that would pass it, with every reservation the
document already holds, is refused ABOUT ITSELF and never sent - its runs recorded not sent (scope refused 'ceiling'),
deciding 'refused', its questions unresolved (question_request_failed:refused), its codes held for the coder, and no
Resume sends it. A reservation stops counting only when its run's own record proves it cost nothing (jobs._run_cost).

BOUNDED WAVES (settings.QUESTION_ROUND_CONCURRENCY; the owner's figure: 4). At most that many requests of a round are in
flight at once; the rest wait their turn in the SAME job, under the SAME provider lock and the SAME one reservation
(jobs._send_question_round, jobs._send_question_wave). Before each later wave the round asks again every door that can
change while it runs (a member's Stop, a stopping worker, a newer save, an unknown outcome, an installation-wide hold,
the lock: jobs._later_wave_held); a crash mid-wave repeats no send. The stage's deadline and stale threshold are derived
for the most waves the two figures allow (settings._question_stage_rows: one wave at the proposed figures, so 1,588 s and
1,768 s stand); the installer writes both figures into every container it starts (ops/install.question_figures)."""
from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import connections
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.interpretation import fable_adapter
from studio.interpretation import holds as interpretation_holds
from studio.interpretation.engine import asking
from studio.participants import pricing
from studio.providers.base import request_sha256
from tests.v2 import test_jobs as TJ
from tests.v2 import test_question_stage as TQ
from tests.v2 import test_settle as TS
from tests.v2.test_question_stage import (FORBIDDEN, QUESTION, SESSION_E1, SESSION_E2, SESSION_E3, SESSION_E4, THREE,
                                          QuestionCase)

Run, Job = models.ProviderRun, models.Job
APP = Path(__file__).resolve().parents[2]
PROJECT_SETTINGS = importlib.import_module('cptstudio.settings')  # the module itself: its derivation, its privates
RECONCILE = 'Synthetic reconciliation: the vendor console was checked for this request.'
MILLIONTH = Decimal('0.000001')
OWNER = dict(QUESTION_PROVIDER_CAP_USD='200', QUESTION_SITE_RESERVE_USD='40', QUESTION_OTHER_SPEND_USD='30')


# --- the finding's generator (the attacker's tests/v2/test_l7p_pipe.generated, ported as filed) -----------------------

PLACES = [('rectum', 'rectum'), ('sigmoid_colon', 'sigmoid colon'), ('descending_colon', 'descending colon'),
          ('transverse_colon', 'transverse colon'), ('ascending_colon', 'ascending colon'), ('cecum', 'cecum')]


def generated(n_sessions: int, n_acts: int, bare: bool = False, exams: bool = False, listed: bool = True):
    """(text, answer): S1-S3 the header; S4 'Findings: ...' X1's examination E1; S5.. the examinations of X2..Xn; then
    one removal a line, its session silent (the first one TJ.SNARE's words, so the fake Corti's evidence locates)."""
    lines = ['SYNTHETIC COLONOSCOPY REPORT', 'Date of service: 03/14/2031', 'Endoscopist: Corvin Ashdale, MD (fictional)',
             '', 'Findings: The colonoscope was advanced to the cecum.']
    for k in range(2, n_sessions + 1):
        lines.append(f'Colonoscopy {k}: the colonoscope was advanced to the cecum in run {k}.')
    for i in range(n_acts):
        place, words = PLACES[i % len(PLACES)]
        if exams:
            lines.append(f'Examination {i + 1}: the colonoscope was advanced.')
        elif bare:
            lines.append(f'Polyp {i + 1} was removed with a snare.')
        else:
            lines.append(TJ.SNARE if i == 0 else
                         f'Polyp {i + 1}, a 4 mm polyp in the {words}, was removed with a cold snare.')
    text = '\n'.join(lines) + '\n'
    sessions, events = [], []
    for k in range(1, n_sessions + 1):
        unit = f'S{3 + k}'
        sessions.append(TS.session(f'X{k}', TS.fact('colonoscopy', TS.src([unit], 'colonoscope')),
                                   examination=[TS.fact(f'E{k}', TS.src([unit]))] if listed else [],
                                   reached=[TS.fact('cecum', TS.src([unit], 'advanced to the cecum'))]))
        events.append(TS.event(f'E{k}', [unit], 'colonoscope', 'was advanced', 'examination',
                               session=[TS.fact(f'X{k}', TS.src([unit]))]))
    for i in range(n_acts):
        unit, eid = f'S{3 + n_sessions + 1 + i}', f'E{n_sessions + 1 + i}'
        place, words = PLACES[i % len(PLACES)]
        if exams:  # an examination whose session the note never states
            events.append(TS.event(eid, [unit], 'colonoscope', 'was advanced', 'examination'))
        elif bare:  # kind and status only, as its own words say ('a snare': no device, no place)
            events.append(TS.event(eid, [unit], 'snare', 'was removed', 'snare'))
        else:
            events.append(TS.event(eid, [unit], 'cold snare', 'was removed', 'snare',
                                   target__places=[TS.fact(place, TS.src([unit], words))],
                                   technique__device=[TS.fact('cold_snare', TS.src([unit], 'cold snare'))]))
    answer = TS.answer(sections=[TS.opening(), TS.labelled('N1', 'S4', 'Findings:', 'findings')], sessions=sessions,
                       events=events)
    return text, answer


# --- helpers ----------------------------------------------------------------------------------------------------------


def figures(ceiling='25', concurrency=4) -> dict:
    """override_settings for the two figures, with the question stage's rows settings derives for them
    (settings._question_stage_rows - its one derivation; a tree without it, int5, is given the figures alone)."""
    out = {'QUESTION_DOCUMENT_CEILING_USD': str(ceiling), 'QUESTION_ROUND_CONCURRENCY': concurrency}
    rows = getattr(PROJECT_SETTINGS, '_question_stage_rows', None)
    if rows is not None:
        waves, deadline, stale = rows(Decimal(str(ceiling)), concurrency)
        out.update(QUESTION_ROUND_WAVES=waves,
                   JOB_DEADLINE_SECONDS={**settings.JOB_DEADLINE_SECONDS, QUESTION: deadline},
                   STALE_RUNNING_SECONDS_BY_KIND={**settings.STALE_RUNNING_SECONDS_BY_KIND, QUESTION: stale})
    return out


def worst_of(question) -> Decimal:
    return Decimal(fable_adapter.worst_case_usd(question.request))


def one_question_each():
    """Every question in a request of its own (test_question_stage's one-question bound): THREE's three questions are a
    round of three requests."""
    return mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                             TQ.REAL_PARTITION(specs, pool, round_, bound=TQ.one_question_bound()))


class Flight:
    """Every question send the scripted connector makes, timed from inside the sending thread: (request sha256,
    start, end), the peak number in flight together, and ``probe`` called from the thread as each send begins. Each
    send holds ``hold`` seconds before it answers, so sends in flight together overlap."""

    def __init__(self, interpreter, hold=0.3, probe=None):
        self.now = self.peak = 0
        self.spans = []
        self.guard = threading.Lock()
        self.scripted = interpreter._exchange
        self.hold, self.probe = hold, probe
        interpreter._exchange = self.exchange

    def exchange(self, body_dict, deadline, purpose):
        if fable_adapter.request_kind(body_dict)[0] != fable_adapter.QUESTION:
            return self.scripted(body_dict, deadline, purpose)
        with self.guard:
            self.now += 1
            self.peak = max(self.peak, self.now)
            number = len(self.spans) + self.now
        start = time.monotonic()
        try:
            if self.probe is not None:
                self.probe(number)
            time.sleep(self.hold)
            return self.scripted(body_dict, deadline, purpose)
        finally:
            end = time.monotonic()
            with self.guard:
                self.now -= 1
                self.spans.append((request_sha256(body_dict), start, end))


class _Case(QuestionCase):
    def inventory(self, revision):
        return models.EventInventory.objects.filter(revision=revision).first()

    def queued(self, encounter):
        return list(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)))

    def round_of_three(self, **kwargs):
        """THREE read through pass 2 with E2-E4's sessions left open: round 1's three requests, one question each."""
        return self.to_questions(SESSION_E2, SESSION_E3, SESSION_E4, text=THREE, **kwargs)

    def generated_document(self, spec):
        n_sessions, n_acts = (int(x) for x in spec.split('x'))
        text, answer = generated(n_sessions, n_acts)
        interpreter = self.questioned()
        interpreter.answers[text] = lambda: answer
        encounter, revision = self.upload(text)
        for kind in ('extract', 'interpret', 'appraise'):
            done = self.run_next(kind)
            self.assertEqual(done.state, Job.SUCCEEDED, (kind, done.error))
        return encounter, revision

    def waves_of(self, runs):
        """The runs grouped by the moment their wave was marked sending (started_at), in order."""
        starts = sorted({run.started_at for run in runs if run.started_at is not None})
        return [[run for run in runs if run.started_at == start] for start in starts]

    def assert_refused_about_itself(self, encounter, revision, why='ceiling'):
        """The ruled outcome of a round over the ceiling: nothing sent, every run of the round recorded not sent and
        refused about itself (decided 'refused'), the row written with its questions unresolved for that reason."""
        runs = [run for run in self.question_runs(encounter) if (run.scope or {}).get('refused')]
        self.assertTrue(runs)
        for run in runs:
            self.assertEqual((run.state, run.sent, run.scope.get('refused')), (Run.NOT_SENT, False, jobs.QUESTION_CEILING))
            self.assertEqual(run.scope[jobs.QUESTION_CEILING]['why'], why, run.scope[jobs.QUESTION_CEILING])
            self.assertEqual(run.error, jobs.QUESTION_CEILING_ERROR)
            self.assertEqual(jobs._question_outcome(run), 'refused')
        return runs


# --- L7P2-2, the ceiling: the finding's own input --------------------------------------------------------------------


class CeilingFindingTests(_Case):
    """The finding's own input (the attacker's ManySessionsPipeline and the verifier's RoundCost): a generated note
    whose acts' session pass 1 left silent, so the planner's A3 asks each act about every family session - the
    shipped default figures, no provider threshold (as the installer leaves it). On int5 one round reserved and sent
    every request at once: 4x20, 10 requests for $52.569680; 16x54, 108 for $573.497888 - with no amount checked."""

    def test_l7p2_2_the_findings_input_4x20_is_refused_about_itself_and_never_sent(self):
        encounter, revision = self.generated_document('4x20')
        self.assertEqual(settings.QUESTION_PROVIDER_CAP_USD, '')  # as installed: the month is not checked
        done = self.run_next(QUESTION)
        self.assertEqual(self.interpreter.question_sent, [])  # int5: 10 requests sent at once
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        runs = self.assert_refused_about_itself(encounter, revision)
        self.assertEqual(len(runs), 10)
        figures_ = runs[0].scope[jobs.QUESTION_CEILING]
        self.assertEqual((figures_['ceiling_usd'], figures_['requests'], figures_['reserved_usd']), ('25', 10, '0'))
        self.assertEqual(Decimal(figures_['round_usd']),
                         sum((Decimal(run.scope['question']['worst_case_usd']) for run in runs), Decimal('0')))
        self.assertGreater(Decimal(figures_['round_usd']), Decimal('52'))
        self.finish(encounter)
        inventory = self.inventory(revision)
        self.assertEqual(len(inventory.events['questions']), 80)
        self.assertEqual({tuple(item['reasons']) for item in inventory.events['questions']},
                         {('question_request_failed:refused',)})
        self.assertEqual(sum(jobs._run_cost(run) for run in self.question_runs(encounter)), 0)  # nothing spent
        for code in ('45378', '45385'):
            self.assertNotEqual(self.status(encounter, code), 'ready')  # the codes held, as on int5
        self.assertIsNone(jobs.resume(encounter, self.user))  # nothing owed: no Resume sends it later
        self.assertEqual(self.interpreter.question_sent, [])

    def test_l7p2_2_the_findings_input_16x54_is_refused_about_itself_and_never_sent(self):
        encounter, revision = self.generated_document('16x54')
        done = self.run_next(QUESTION)
        self.assertEqual(self.interpreter.question_sent, [])  # int5: 108 requests sent at once
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        self.assertEqual(len(self.assert_refused_about_itself(encounter, revision)), 108)


# --- the ceiling: the rest of its class, and its boundary ---------------------------------------------------------


class CeilingClassTests(_Case):
    def test_a_later_round_that_would_pass_the_ceiling_with_the_earlier_ones_is_refused_about_itself(self):
        """'Over every round': round 1's three requests fit and are sent; round 2's one request, with round 1's
        reservations, would pass the ceiling by a millionth - refused about itself, round 1's answers kept."""
        with one_question_each(), mock.patch.object(asking, 'plan', side_effect=TQ.two_rounds(3)):
            encounter, revision, queued = self.to_questions(SESSION_E2, SESSION_E3, SESSION_E4, SESSION_E1, text=THREE)
            first = self.run_next(QUESTION)
            self.assertEqual((first.state, first.result['sent']), (Job.SUCCEEDED, 3), (first.error, first.result))
            held = sum((Decimal(run.scope['question']['worst_case_usd']) for run in self.question_runs(encounter)),
                       Decimal('0'))
            [second] = [question for sha, question in self.built.items()
                        if sha not in {run.request_sha256 for run in self.question_runs(encounter)}]
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(held + worst_of(second) - MILLIONTH)):
                self.run_next(QUESTION)
                self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 3)
        [refused] = self.assert_refused_about_itself(encounter, revision)
        self.assertEqual(Decimal(refused.scope[jobs.QUESTION_CEILING]['reserved_usd']), held)
        records = self.inventory(revision).events['questions']
        self.assertEqual(sorted((item['result'], tuple(item['reasons'])) for item in records),
                         [('supported', ())] * 3 + [('unresolved', ('question_request_failed:refused',))])

    def test_boundary_a_round_exactly_at_the_ceiling_is_within_it(self):
        with one_question_each():
            encounter, revision, queued = self.round_of_three()
            ceiling = sum((worst_of(question) for question in self.built.values()), Decimal('0'))
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(ceiling)):
                self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_round_one_millionth_over_the_ceiling_is_refused_about_itself(self):
        with one_question_each():
            encounter, revision, queued = self.round_of_three()
            ceiling = sum((worst_of(question) for question in self.built.values()), Decimal('0')) - MILLIONTH
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(ceiling)):
                self.finish(encounter)
        self.assertEqual(self.interpreter.question_sent, [])
        self.assertEqual(len(self.assert_refused_about_itself(encounter, revision)), 3)
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a_ceiling_of_nothing_sends_nothing(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        with override_settings(QUESTION_DOCUMENT_CEILING_USD='0'):
            self.finish(encounter)
        self.assertEqual(self.interpreter.question_sent, [])
        self.assert_refused_about_itself(encounter, revision)
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_a_reservation_that_sent_nothing_is_released_so_its_request_counts_once(self):
        """D324 (10)'s owed outcome (the credentials file missing at send time: nothing left this server) at a ceiling of
        exactly the round: the Resume's reservation of the same three requests fits, since the first three provably
        sent nothing; were they counted, it would be refused."""
        from tests.v2.test_r3c_pipe import credentials_missing

        with one_question_each():
            encounter, revision, queued = self.round_of_three(question_script=[credentials_missing] * 3)
            ceiling = sum((worst_of(question) for question in self.built.values()), Decimal('0'))
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(ceiling)):
                done = self.run_next(QUESTION)
                self.assertEqual((done.state, done.error), (Job.CANCELLED, jobs.INTERPRET_NOT_SENT_MESSAGE))
                self.assertEqual(jobs._document_reserved_usd(revision), 0)
                self.interpreter.question_script = []
                self.assertIsNotNone(jobs.resume(encounter, self.user))
                self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 6)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_member_stop_before_the_send_releases_its_reservations(self):
        """A member's Stop recorded while the round reserves, at a ceiling of exactly the round: the three reservations
        are cancelled (nothing was sent), so the Resume's reservation of the same three fits."""
        real = jobs._ceiling_refusal

        def stopping(revision_, worst):
            jobs.stop_encounter(revision_.encounter, self.user)
            return real(revision_, worst)
        with one_question_each():
            encounter, revision, queued = self.round_of_three()
            ceiling = sum((worst_of(question) for question in self.built.values()), Decimal('0'))
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(ceiling)), \
                    mock.patch.object(jobs, '_ceiling_refusal', side_effect=stopping):
                done = self.run_next(QUESTION)
                self.assertEqual(done.state, Job.CANCELLED, (done.error, done.result))
                self.assertEqual({run.state for run in self.question_runs(encounter)}, {Run.CANCELLED})
                self.assertEqual(jobs._document_reserved_usd(revision), 0)
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(ceiling)):
                jobs.resume(encounter, self.user)
                self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_reservation_that_may_have_been_spent_is_counted(self):
        """An outcome unknown (the deadline cut the stream after the request left): its reservation may have been spent,
        so it is counted. The member's reconciliation releases one new attempt, which with it would pass a ceiling of
        one and a half requests: refused about itself - fail-closed, the code held."""
        cut = [lambda sha, question: TJ.UNKNOWN]
        encounter, revision, queued = self.to_questions(SESSION_E2, question_script=cut)
        [question] = self.built.values()
        with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(worst_of(question) * Decimal('1.5'))):
            self.run_next(QUESTION)
            [run] = self.question_runs(encounter)
            self.assertEqual(run.state, Run.UNKNOWN)
            self.assertEqual(jobs._document_reserved_usd(revision), worst_of(question))
            self.drain()  # the next step: blocked by the unknown outcome
            self.assertTrue(jobs.reconcile(encounter, run, self.user, RECONCILE))
            self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assert_refused_about_itself(encounter, revision)
        self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

    def test_another_documents_reservations_are_not_counted(self):
        """Per document: THREE's document holds its round of three reserved; POLYP's document, at a ceiling of exactly
        its own one request, is sent - it would be refused were THREE's reservations counted."""
        with one_question_each():
            first, first_revision, queued = self.round_of_three()
            self.finish(first)
            self.assertEqual(len(self.interpreter.question_sent), 3)
            held = jobs._document_reserved_usd(first_revision)
            second, second_revision = self.upload(TJ.POLYP)
            for kind in ('extract', 'interpret', 'appraise'):
                self.run_next(kind)
            sent = {run.request_sha256 for run in self.question_runs(first)}
            [question] = [item for sha, item in self.built.items() if sha not in sent]
            with override_settings(QUESTION_DOCUMENT_CEILING_USD=str(worst_of(question))):
                self.finish(second)
        self.assertGreater(held, worst_of(question))
        self.assertEqual(len(self.interpreter.question_sent), 4)
        self.assertEqual(jobs._document_reserved_usd(second_revision), worst_of(question))
        self.assertEqual(self.status(second, '45385'), 'ready')

    def test_the_ceiling_decides_before_the_months_threshold(self):
        """A round the month's other spend would leave owed (D324 (10)) and the ceiling refuses: the ceiling's refusal
        is about the document itself, so it decides - the row written, never a stage left resumable."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        [question] = self.built.values()
        cap = str(Decimal('40') + worst_of(question) + Decimal('1'))  # the round alone fits; the $30 other spend not
        with override_settings(QUESTION_PROVIDER_CAP_USD=cap, QUESTION_SITE_RESERVE_USD='40',
                               QUESTION_OTHER_SPEND_USD='30',
                               QUESTION_DOCUMENT_CEILING_USD=str(worst_of(question) - MILLIONTH)):
            done = self.run_next(QUESTION)
            self.finish(encounter)
        self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
        self.assert_refused_about_itself(encounter, revision)
        self.assertIsNotNone(self.inventory(revision))
        self.assertEqual(self.interpreter.question_sent, [])

    def test_boundary_the_months_own_refusal_is_unchanged_within_the_ceiling(self):
        """BOUNDARY (left alone, D324 (10)): within the ceiling, a round the month's other spend pushes over the
        threshold stays owed - CANCELLED with the threshold's own sentence, no row."""
        encounter, revision, queued = self.to_questions(SESSION_E2)
        [question] = self.built.values()
        cap = str(Decimal('40') + worst_of(question) + Decimal('1'))
        with override_settings(QUESTION_PROVIDER_CAP_USD=cap, QUESTION_SITE_RESERVE_USD='40',
                               QUESTION_OTHER_SPEND_USD='30'):
            done = self.run_next(QUESTION)
        [run] = self.question_runs(encounter)
        self.assertEqual((run.state, run.scope.get('refused')), (Run.NOT_SENT, jobs.QUESTION_BUDGET_MONTH))
        self.assertEqual((done.state, done.error), (Job.CANCELLED, run.error))
        self.assertIsNone(self.inventory(revision))

    def test_a_round_of_more_requests_than_the_stages_waves_is_refused_about_itself(self):
        """The ceiling's own consequence, kept as a door so the stage's derived deadline covers every round it sends:
        more requests than its waves of the concurrency hold (here 1 wave of 2) refuses the round, whatever the
        amount."""
        with one_question_each():
            encounter, revision, queued = self.round_of_three()
            with override_settings(QUESTION_DOCUMENT_CEILING_USD='1000', QUESTION_ROUND_CONCURRENCY=2,
                                   QUESTION_ROUND_WAVES=1):
                self.finish(encounter)
        self.assertEqual(self.interpreter.question_sent, [])
        self.assert_refused_about_itself(encounter, revision, why='waves')

    def test_a_worst_case_or_a_ceiling_that_cannot_be_read_refuses(self):
        encounter, revision, queued = self.to_questions(SESSION_E2)
        self.assertEqual(jobs._ceiling_refusal(revision, [None])['why'], 'unbounded')
        self.assertEqual(jobs._ceiling_refusal(revision, ['-1.000000'])['why'], 'unbounded')
        self.assertEqual(jobs._ceiling_refusal(revision, ['five dollars'])['why'], 'unbounded')
        self.assertIsNone(jobs._ceiling_refusal(revision, ['5.200000', '19.800000']))
        self.assertEqual(jobs._ceiling_refusal(revision, ['5.200000', '19.800001'])['why'], 'ceiling')
        for unreadable in ('', 'NaN', '-1', 'twenty-five'):
            with self.subTest(ceiling=unreadable), override_settings(QUESTION_DOCUMENT_CEILING_USD=unreadable):
                self.assertEqual(jobs._ceiling_refusal(revision, ['1.000000'])['why'], 'unreadable')


# --- L7P2-2, bounded waves: the finding's own input --------------------------------------------------------------------


class WaveFindingTests(_Case):
    def test_l7p2_2_the_findings_input_4x20_under_a_raised_ceiling_goes_in_waves_of_the_concurrency(self):
        """The finding's 4x20 round of ten requests under figures that admit it ($60 a document, 3 at once: four waves
        at most): never more than three in flight; four waves of 3, 3, 3 and 1 in the round's order, each starting only
        once the one before it has ended, in ONE job under ONE reservation; every request sent once. On int5 all ten
        were in flight together."""
        n_text, answer = generated(4, 20)
        interpreter = self.questioned()
        interpreter.answers[n_text] = lambda: answer
        flight = Flight(interpreter)
        budget = []
        real = jobs._question_budget_refusal
        with override_settings(**figures('60', 3)), \
                mock.patch.object(jobs, '_question_budget_refusal', side_effect=lambda worst: budget.append(worst)
                                  or real(worst)):
            encounter, revision = self.upload(n_text)
            for kind in ('extract', 'interpret', 'appraise'):
                self.run_next(kind)
            done = self.run_next(QUESTION)
            self.assertLessEqual(flight.peak, 3, flight.spans)  # int5: 10
            self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
            self.finish(encounter)
        runs = self.question_runs(encounter)
        self.assertEqual(len(runs), 10)
        self.assertEqual([len(wave) for wave in self.waves_of(runs)], [3, 3, 3, 1])
        self.assertEqual([len(item) for item in budget], [10])  # one reservation of the whole round
        self.assertEqual(Counter(self.interpreter.question_sent), Counter({run.request_sha256: 1 for run in runs}))
        ended = {sha: end for sha, start, end in flight.spans}
        began = {sha: start for sha, start, end in flight.spans}
        waves = self.waves_of(runs)
        for earlier, later in zip(waves, waves[1:]):
            self.assertLess(max(ended[run.request_sha256] for run in earlier),
                            min(began[run.request_sha256] for run in later))
        self.assertEqual(Job.objects.filter(encounter=encounter, kind=QUESTION).count(), 1)  # the same job


# --- bounded waves: the rest of the class, and its boundary --------------------------------------------------------


class WaveClassTests(_Case):
    def holder(self, seen):
        """A probe recording, from inside the sending thread, which database sessions hold the provider lock (this test
        database's lock only), and how many question runs of the document are still reserved."""
        def probe(number):
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND granted AND objsubid = 1 "
                                   'AND database = (SELECT oid FROM pg_database WHERE datname = current_database()) '
                                   'AND (classid::bigint << 32) + objid::bigint = %s', [jobs.PROVIDER_LOCK_KEY])
                    seen.append(tuple(row[0] for row in cursor.fetchall()))
            finally:
                connections['default'].close()
        return probe

    def test_a_round_of_three_at_two_at_once_is_two_waves_under_one_lock_and_one_reservation(self):
        holders, budget = [], []
        real = jobs._question_budget_refusal
        with one_question_each(), override_settings(**figures('25', 2)), \
                mock.patch.object(jobs, '_question_budget_refusal', side_effect=lambda worst: budget.append(worst)
                                  or real(worst)):
            encounter, revision, queued = self.round_of_three()
            flight = Flight(self.interpreter, probe=self.holder(holders))
            done = self.run_next(QUESTION)
            self.finish(encounter)
        self.assertEqual((done.state, done.result['sent']), (Job.SUCCEEDED, 3), (done.error, done.result))
        self.assertLessEqual(flight.peak, 2)
        runs = self.question_runs(encounter)
        self.assertEqual([len(wave) for wave in self.waves_of(runs)], [2, 1])
        self.assertEqual([len(item) for item in budget], [3])  # ONE reservation of all three worst cases
        self.assertEqual(len(holders), 3)
        self.assertEqual({len(found) for found in holders}, {1})  # one holder of the lock ...
        self.assertEqual(len({found[0] for found in holders}), 1)  # ... the same session for every wave
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_one_at_a_time_is_one_wave_a_request_in_the_rounds_order(self):
        with one_question_each(), override_settings(**figures('25', 1)):
            encounter, revision, queued = self.round_of_three()
            flight = Flight(self.interpreter)
            self.run_next(QUESTION)
            self.finish(encounter)
        self.assertEqual(flight.peak, 1)
        runs = self.question_runs(encounter)
        self.assertEqual([len(wave) for wave in self.waves_of(runs)], [1, 1, 1])
        self.assertEqual([run.scope['question']['batch'] for run in sorted(runs, key=lambda run: run.started_at)],
                         [1, 2, 3])  # the waves follow the round's own order
        self.assertEqual(self.interpreter.question_sent, [run.request_sha256 for run in
                                                          sorted(runs, key=lambda run: run.started_at)])
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_each_wave_is_recorded_before_the_next_starts_and_the_later_waves_wait_reserved(self):
        """As each wave starts, in the round's job: every earlier wave's outcome recorded, this wave's runs sending and
        every later one still reserved under the same reservation."""
        states = []
        real = jobs._send_question_wave

        def observed(encounter_, interpreter, requests, runs, places):
            states.append([Run.objects.get(pk=run.pk).state for run in runs])
            return real(encounter_, interpreter, requests, runs, places)
        with one_question_each(), override_settings(**figures('25', 1)), \
                mock.patch.object(jobs, '_send_question_wave', side_effect=observed):
            encounter, revision, queued = self.round_of_three()
            self.run_next(QUESTION)
        self.assertEqual(states, [[Run.SENDING, Run.RESERVED, Run.RESERVED],
                                  [Run.SUCCEEDED, Run.SENDING, Run.RESERVED],
                                  [Run.SUCCEEDED, Run.SUCCEEDED, Run.SENDING]])
        runs = self.question_runs(encounter)
        self.assertEqual({run.state for run in runs}, {Run.SUCCEEDED})
        waves = self.waves_of(runs)
        for earlier, later in zip(waves, waves[1:]):
            self.assertLessEqual(max(run.finished_at for run in earlier), min(run.started_at for run in later))

    def test_the_stage_gate_counts_every_wave(self):
        """A round of three waves needs two whole wave bounds before its last send and recording: a stage started too
        long ago for them is queued again before anything is reserved; one with a second to spare sends."""
        rows = figures('25', 1)
        whole = settings.QUESTION_SEND_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS + jobs.QUESTION_WAVE_WAIT_SECONDS
        need = 2 * whole + settings.QUESTION_SEND_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS
        with one_question_each(), override_settings(**rows):
            encounter, revision, queued = self.round_of_three()
            budget = min(rows['JOB_DEADLINE_SECONDS'][QUESTION], rows['STALE_RUNNING_SECONDS_BY_KIND'][QUESTION])
            job = jobs.claim_next()
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta_s(budget - need + 1))
            job.refresh_from_db()
            done = jobs.run_job(job)
            self.assertEqual((done.state, done.result), (Job.QUEUED, {'requeued': jobs.LOOP_LATE_MESSAGE}))
            self.assertEqual(self.question_runs(encounter), [])
            job = jobs.claim_next()
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta_s(budget - need - 30))
            job.refresh_from_db()
            self.assertEqual(jobs.run_job(job).state, Job.SUCCEEDED)
        self.assertEqual(len(self.interpreter.question_sent), 3)

    def test_boundary_a_round_within_the_concurrency_is_one_wave_in_flight_together_as_before(self):
        """BOUNDARY (left alone, D322 (1)): at the installed figures a round of three is one wave - all three in flight
        together (each waits at a barrier of three), one start."""
        with one_question_each():
            encounter, revision, queued = self.round_of_three(barrier=threading.Barrier(3))
            done = self.run_next(QUESTION)
        self.assertEqual((done.state, done.result['sent']), (Job.SUCCEEDED, 3), (done.error, done.result))
        self.assertEqual([len(wave) for wave in self.waves_of(self.question_runs(encounter))], [3])


def timedelta_s(seconds):
    from datetime import timedelta

    return timedelta(seconds=seconds)


# --- bounded waves: a crash, a Stop, a stopping worker and the other doors before a later wave -------------------------


class WaveDoorTests(_Case):
    def one_at_a_time(self, **kwargs):
        self.enterContext(one_question_each())
        self.enterContext(override_settings(**figures('25', 1)))
        return self.round_of_three(**kwargs)

    def test_a_crash_mid_wave_repeats_no_send(self):
        """The worker dies while wave 2 of 3 is being recorded: wave 1's outcome is kept, wave 2's run is left sending
        (the startup sweep settles it unknown) and wave 3's reservation is settled not sent. Nothing is sent until a
        member reconciles the unknown outcome; then wave 2's request is sent once more (the reconciliation's one
        attempt) and wave 3's once - no other send is repeated."""
        class Died(BaseException):
            pass
        real, calls = jobs._finish_question_run, []

        def dying(encounter_, run, outcome):
            calls.append(run.pk)
            if len(calls) == 2:
                raise Died()
            return real(encounter_, run, outcome)
        encounter, revision, queued = self.one_at_a_time()
        job = jobs.claim_next()
        with mock.patch.object(jobs, '_finish_question_run', side_effect=dying):
            with self.assertRaises(Died):
                jobs.run_job(job)
        self.assertEqual(len(self.interpreter.question_sent), 2)
        first, second, third = sorted(self.question_runs(encounter), key=lambda run: run.scope['question']['batch'])
        self.assertEqual((first.state, second.state, third.state, third.started_at),
                         (Run.SUCCEEDED, Run.SENDING, Run.NOT_SENT, None))
        jobs.mark_stale(startup=True)
        second.refresh_from_db()
        self.assertEqual((second.state, Job.objects.get(pk=job.pk).state), (Run.UNKNOWN, Job.UNKNOWN))
        self.assertIsNone(jobs.resume(encounter, self.user))
        self.assertEqual([item.result for item in self.drain()], [])
        self.assertEqual(len(self.interpreter.question_sent), 2)
        self.assertTrue(jobs.reconcile(encounter, second, self.user, RECONCILE))
        self.finish(encounter)
        sent = Counter(self.interpreter.question_sent)
        self.assertEqual(sent, Counter({first.request_sha256: 1, second.request_sha256: 2, third.request_sha256: 1}))
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_member_stop_during_a_wave_cancels_the_later_waves(self):
        """A member's Stop recorded while wave 1 is in flight: wave 1 finishes and is recorded, nothing more is sent
        (waves 2 and 3 cancelled), the stage queued after it is stopped before it starts; a Resume sends each owed
        request once."""
        stopped = threading.Event()
        encounter, revision, queued = self.one_at_a_time()
        Flight(self.interpreter, probe=lambda number: stopped.set())
        real = jobs._stop_requested

        def stopping(job, encounter_):  # the Stop the member recorded meanwhile, written as the round asks for it
            if stopped.is_set() and not models.Encounter.objects.get(pk=encounter_.pk).stopped_at:
                jobs.stop_encounter(encounter_, self.user)
            return real(job, encounter_)
        with mock.patch.object(jobs, '_stop_requested', side_effect=stopping):
            done = self.run_next(QUESTION)
            self.assertEqual(len(self.interpreter.question_sent), 1)
            self.assertEqual(sorted(run.state for run in self.question_runs(encounter)),
                             sorted([Run.SUCCEEDED, Run.CANCELLED, Run.CANCELLED]))
            self.assertEqual(done.state, Job.SUCCEEDED, (done.error, done.result))
            self.drain()
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertEqual(self.queued(encounter), [])
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.finish(encounter)
        self.assertEqual(Counter(self.interpreter.question_sent).most_common(1)[0][1], 1)
        self.assertEqual(len(self.interpreter.question_sent), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_stopping_worker_starts_no_further_wave_and_the_next_worker_sends_the_rest(self):
        asked = threading.Event()
        encounter, revision, queued = self.one_at_a_time()
        Flight(self.interpreter, probe=lambda number: asked.set())  # the deploy's SIGTERM arrives during wave 1
        with mock.patch.dict(jobs._WORKER, {'should_stop': asked.is_set}):
            done = self.run_next(QUESTION)
        self.assertEqual((done.state, len(self.interpreter.question_sent)), (Job.SUCCEEDED, 1), done.error)
        runs = sorted(self.question_runs(encounter), key=lambda run: run.scope['question']['batch'])
        self.assertEqual([(run.state, run.started_at is None, run.error) for run in runs[1:]],
                         [(Run.NOT_SENT, True, jobs.ORPHANED_RESERVATION_MESSAGE)] * 2)
        self.assertEqual(jobs._document_reserved_usd(revision), Decimal(runs[0].scope['question']['worst_case_usd']))
        [following] = self.queued(encounter)
        self.assertEqual(following.kind, QUESTION)
        self.finish(encounter)  # the next worker
        self.assertEqual(Counter(self.interpreter.question_sent), Counter({run.request_sha256: 1 for run in runs}))
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_a_lost_lock_before_a_later_wave_releases_the_rest_for_the_next_stage(self):
        encounter, revision, queued = self.one_at_a_time()
        answers = [True, False]  # wave 1 holds the lock; before wave 2 this session no longer does
        real = jobs._holds_provider_lock
        with mock.patch.object(jobs, '_holds_provider_lock', side_effect=lambda: answers.pop(0) if answers else real()):
            done = self.run_next(QUESTION)
        self.assertEqual(answers, [])
        self.assertEqual((done.state, len(self.interpreter.question_sent)), (Job.SUCCEEDED, 1), done.error)
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 3)
        self.assertEqual(len(set(self.interpreter.question_sent)), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_an_unknown_outcome_holds_the_later_waves(self):
        """Wave 1's outcome unknown: the unknown-outcome block every send door reads holds waves 2 and 3 too (int5 sent
        them all together before any outcome); after the member's reconciliation each owed request is sent once."""
        encounter, revision, queued = self.one_at_a_time(question_script=[lambda sha, question: TJ.UNKNOWN])
        done = self.run_next(QUESTION)
        self.assertEqual((done.state, len(self.interpreter.question_sent)), (Job.SUCCEEDED, 1), done.error)
        unknown = [run for run in self.question_runs(encounter) if run.state == Run.UNKNOWN]
        self.assertEqual(len(unknown), 1)
        self.drain()  # the next stage: blocked by the unknown outcome
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertTrue(jobs.reconcile(encounter, unknown[0], self.user, RECONCILE))
        self.finish(encounter)
        self.assertEqual(len(self.interpreter.question_sent), 4)  # the reconciliation's one attempt, and the two owed
        self.assertEqual(len(set(self.interpreter.question_sent)), 3)
        self.assertEqual(self.status(encounter, '45385'), 'ready')

    def test_an_installation_wide_hold_set_by_a_wave_holds_the_later_waves(self):
        """Wave 1's answer sets an installation-wide hold (a 402): nothing more is sent, the stage pauses on it
        (PIPE-R1), every request stays owed."""
        holding = [lambda sha, question: TJ.answered(TJ.HTTP_402, status=402)]
        encounter, revision, queued = self.one_at_a_time(question_script=holding)
        done = self.run_next(QUESTION)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        self.assertTrue(interpretation_holds.is_held())
        self.assertEqual((done.state, done.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE))
        for run in self.question_runs(encounter):
            self.assertIsNone(jobs._question_outcome(run), (run.state, run.error))
        self.assertIsNone(self.inventory(revision))

    def test_a_newer_reading_of_the_document_stops_the_later_waves(self):
        """The stage superseded while wave 1 is in flight (3.4: it sends nothing from there on): waves 2 and 3 are
        released unsent and nothing more is sent for this revision."""
        superseded = threading.Event()
        encounter, revision, queued = self.one_at_a_time()
        Flight(self.interpreter, probe=lambda number: superseded.set())
        real = jobs._superseded
        with mock.patch.object(jobs, '_superseded', side_effect=lambda job: (review.SUPERSEDED_REVISION
                                                                             if superseded.is_set() else real(job))):
            done = self.run_next(QUESTION)
        self.assertEqual(len(self.interpreter.question_sent), 1)
        runs = sorted(self.question_runs(encounter), key=lambda run: run.scope['question']['batch'])
        self.assertEqual([run.state for run in runs], [Run.SUCCEEDED, Run.NOT_SENT, Run.NOT_SENT])
        self.assertNotEqual(done.state, Job.FAILED, done.error)


# --- the settings: the figures, the floor, the derived rows ------------------------------------------------------------


def settings_literal(name):
    for node in ast.parse((APP / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


def load_settings(**environment):
    """cptstudio/settings.py loaded in a fresh process with ``environment`` (synthetic values only): (exit, the figures
    and rows it derived, or its error's last line)."""
    script = ('import cptstudio.settings as s\n'
              "print(repr((s.QUESTION_DOCUMENT_CEILING_USD, s.QUESTION_ROUND_CONCURRENCY, s.QUESTION_ROUND_WAVES, "
              "s.JOB_DEADLINE_SECONDS['question'], s.STALE_RUNNING_SECONDS_BY_KIND['question'])))\n")
    base = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1',
            'CPT_STUDIO_SECRET_KEY': 'synthetic-settings-check-only'}
    completed = subprocess.run([sys.executable, '-c', script], cwd=APP, env={**base, **environment},
                               capture_output=True, text=True, timeout=60)
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    return completed.returncode, lines[-1] if lines else ''


class SettingsTests(SimpleTestCase):
    def test_the_proposed_figures_are_one_wave_so_the_stage_keeps_its_rows(self):
        self.assertEqual((settings.QUESTION_DOCUMENT_CEILING_USD, settings.QUESTION_ROUND_CONCURRENCY), ('25', 4))
        self.assertEqual(settings.QUESTION_ROUND_WAVES, 1)
        self.assertEqual((settings.JOB_DEADLINE_SECONDS[QUESTION], settings.STALE_RUNNING_SECONDS_BY_KIND[QUESTION]),
                         (1588, 1768))
        # the literals the installer's tests read with ast are the rows at the installed figures
        self.assertEqual((settings_literal('JOB_DEADLINE_SECONDS')[QUESTION],
                          settings_literal('STALE_RUNNING_SECONDS_BY_KIND')[QUESTION]), (1588, 1768))
        floor = Decimal(settings.QUESTION_REQUEST_FLOOR_USD)
        self.assertLessEqual(4 * floor, Decimal('25'))
        self.assertGreater(5 * floor, Decimal('25'))  # so at most 4 requests a document: one wave of 4

    def test_the_request_floor_is_the_adapters_and_the_price_tables(self):
        from tests.v2.test_r3_probe import REL, stub_request

        rates = pricing.FABLE_52_RATES
        derived = (Decimal(fable_adapter.MAX_TOKENS) * rates['output']
                   + Decimal(fable_adapter.PROMPT_MARGIN_TOKENS) * rates['input']) / Decimal(1_000_000)
        self.assertEqual(Decimal(settings.QUESTION_REQUEST_FLOOR_USD), derived)
        self.assertEqual(fable_adapter.MODEL, pricing.FABLE_52)
        built = stub_request([REL])
        self.assertGreater(worst_of(built), Decimal(settings.QUESTION_REQUEST_FLOOR_USD))
        self.assertEqual(built.request.body['max_tokens'], fable_adapter.MAX_TOKENS)

    def test_the_derivation_reads_the_jobs_own_figures(self):
        self.assertEqual(PROJECT_SETTINGS._wave_recording_seconds, jobs.LOOP_RECORDING_SECONDS)
        self.assertEqual(PROJECT_SETTINGS._wave_wait_seconds, jobs.QUESTION_WAVE_WAIT_SECONDS)
        self.assertEqual(PROJECT_SETTINGS._queue_window_seconds, jobs.QUEUE_DEADLINE.total_seconds())
        self.assertEqual(PROJECT_SETTINGS._stage_work_seconds, 45)  # test_question_stage's stage row: its 45 s of work

    def test_the_rows_grow_one_whole_wave_bound_a_wave(self):
        rows = PROJECT_SETTINGS._question_stage_rows
        send, child = settings.QUESTION_SEND_DEADLINE_SECONDS, settings.QUESTION_CHILD_SECONDS
        whole = send + jobs.LOOP_RECORDING_SECONDS + jobs.QUESTION_WAVE_WAIT_SECONDS
        floor = Decimal(settings.QUESTION_REQUEST_FLOOR_USD)
        for ceiling in ('0', '5.127', '5.128', '10.255', '10.256', '25', '30', '50', '60', '87'):
            for concurrency in (1, 2, 3, 4, 8, 64):
                requests = int(Decimal(ceiling) // floor)
                waves = max(1, -(-requests // concurrency))
                stale = child + (waves - 1) * whole + send + jobs.LOOP_RECORDING_SECONDS + 45 + child + 60
                with self.subTest(ceiling=ceiling, concurrency=concurrency):
                    if stale > jobs.QUEUE_DEADLINE.total_seconds():
                        with self.assertRaises(RuntimeError):
                            rows(Decimal(ceiling), concurrency)
                        continue
                    deadline = stale - child - 60
                    self.assertEqual(rows(Decimal(ceiling), concurrency), (waves, deadline, stale))
                    self.assertEqual(deadline, (waves - 1) * whole + 1588)
        self.assertEqual(rows(Decimal('25'), 1), (4, 6037, 6217))
        self.assertEqual(rows(Decimal('50'), 3), (3, 4554, 4734))
        for refused in (('88', 4), ('100', 4), ('1E+40', 1000)):
            with self.subTest(refused=refused), self.assertRaises(RuntimeError):
                rows(Decimal(refused[0]), refused[1])

    def test_a_fresh_process_loads_the_figures_and_refuses_one_it_cannot_use(self):
        self.assertEqual(load_settings(), (0, repr(('25', 4, 1, 1588, 1768))))
        self.assertEqual(load_settings(CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD='50',
                                       CPT_STUDIO_QUESTION_ROUND_CONCURRENCY='3'), (0, repr(('50', 3, 3, 4554, 4734))))
        self.assertEqual(load_settings(CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD='0'), (0, repr(('0', 4, 1, 1588, 1768))))
        for name, value in (('CEILING_USD', ''), ('CEILING_USD', '-1'), ('CEILING_USD', 'NaN'),
                            ('CEILING_USD', 'twenty-five'), ('CONCURRENCY', ''), ('CONCURRENCY', '0'),
                            ('CONCURRENCY', '-1'), ('CONCURRENCY', '1.5'), ('CONCURRENCY', 'four')):
            variable = ('CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD' if name == 'CEILING_USD'
                        else 'CPT_STUDIO_QUESTION_ROUND_CONCURRENCY')
            with self.subTest(variable=variable, value=value):
                code, last = load_settings(**{variable: value})
                self.assertNotEqual(code, 0)
                self.assertIn(f'RuntimeError: {variable} must be', last)
        code, last = load_settings(CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD='100')
        self.assertNotEqual(code, 0)
        self.assertIn('within the queue window', last)


# --- the installer: both figures in every container it starts ----------------------------------------------------------


def _install():
    sys.path.insert(0, str(APP / 'ops'))
    try:
        return importlib.import_module('install')
    finally:
        sys.path.remove(str(APP / 'ops'))


class InstallTests(SimpleTestCase):
    IMAGE, REVISION, RULING = 'sha256:' + 'c' * 64, 'b' * 40, 'docs/synthetic-ruling.md'

    def env(self, argv):
        return dict(value.split('=', 1) for flag, value in zip(argv, argv[1:]) if flag == '-e')

    def test_every_container_is_given_both_figures_at_the_revisions_settings_values(self):
        install = _install()
        expected = {'CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD': settings.QUESTION_DOCUMENT_CEILING_USD,
                    'CPT_STUDIO_QUESTION_ROUND_CONCURRENCY': str(settings.QUESTION_ROUND_CONCURRENCY)}
        self.assertEqual(install.question_figures(), expected)
        self.assertEqual(expected, {'CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD': '25',
                                    'CPT_STUDIO_QUESTION_ROUND_CONCURRENCY': '4'})
        web = install.service_args('web', self.IMAGE, self.REVISION, 'live', self.RULING, interpreter='live')
        worker = install.service_args('worker', self.IMAGE, self.REVISION, 'live', self.RULING, interpreter='live')
        oneshot = install.runtime_env('disabled', '')
        for argv in (web, worker, oneshot):
            with self.subTest(argv=argv[:4]):
                self.assertEqual({name: value for name, value in self.env(argv).items() if 'QUESTION' in name},
                                 expected)
        self.assertEqual(self.env(web), self.env(worker))  # the web is named everything the worker is

    def test_a_default_the_settings_would_refuse_is_refused_before_anything_starts(self):
        install = _install()
        good = ("QUESTION_DOCUMENT_CEILING_USD = _env('QUESTION_DOCUMENT_CEILING_USD', '25')\n"
                "_concurrency = _env('QUESTION_ROUND_CONCURRENCY', '4')\n")
        self.assertEqual(install.question_figures(good), {'CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD': '25',
                                                          'CPT_STUDIO_QUESTION_ROUND_CONCURRENCY': '4'})
        for source in (good.replace("'25'", "'-1'"), good.replace("'25'", "'NaN'"), good.replace("'4'", "'0'"),
                       good.replace("'4'", "'4.5'"), good.replace("'4'", "'four'"), good.splitlines()[0] + '\n',
                       good + "_again = _env('QUESTION_ROUND_CONCURRENCY', '2')\n"):
            with self.subTest(source=source), self.assertRaises(install.InstallError):
                install.question_figures(source)

    def test_install_md_documents_both_figures(self):
        said = ' '.join((APP / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())
        for words in ('`CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD` (25 US dollars',
                      '`CPT_STUDIO_QUESTION_ROUND_CONCURRENCY` (4)', 'is refused about itself and never sent',
                      'in the same job, under the same lock and the same reservation', '`QUESTION_ROUND_WAVES`',
                      'A worker asked to stop starts no further wave'):
            with self.subTest(words=words):
                self.assertIn(words, said)


# --- the customer surface ---------------------------------------------------------------------------------------------


class SurfaceTests(SimpleTestCase):
    def test_the_ceiling_says_only_existing_words(self):
        """D320 (i): a run the ceiling refused carries CPT Studio's existing plain sentence for a run recorded not sent
        (the serializers' own), naming no provider, question, proof or answer; the figures are in its scope."""
        from studio import serializers

        self.assertEqual(jobs.QUESTION_CEILING_ERROR, 'Nothing was sent.')
        self.assertIn("'Nothing was sent.'", Path(serializers.__file__).read_text(encoding='utf-8'))
        self.assertFalse([word for word in FORBIDDEN if word in jobs.QUESTION_CEILING_ERROR.lower()])
        self.assertIn(jobs.ORPHANED_RESERVATION_MESSAGE, Path(jobs.__file__).read_text(encoding='utf-8'))
