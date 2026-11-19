"""Round r3's integration (int4, DECISIONS D320; build-v2/a2b/r3b/int4/NOTES.md): the integrator's own repairs and the
lane questions it resolved across the lanes' files, each shown on an input it must change - red on the lanes' merged tree
(int4/merge, the five lanes' patches applied together) - and on a boundary it must leave alone. TEXT-ONLY and
SYNTHETIC: every FactSet is built in code, every stored answer by hand; nothing is sent anywhere.

- QBAnatomyTests (the second refutation's R2E-QB-ANAT, HIGH, a false READY; D316 QB's class): the QB clause reads EVERY
  target a statement names for itself beyond its not-on lesions - its target.anatomy (an anastomosis, a stoma or a pouch:
  unplaceable, anatomy.ALTERED) and its target.structure (any structure but a lesion: a target with no place of its own)
  as well as its places and its segment - so a denial "at the polypectomy site or at the anastomosis" beside a tattoo of
  the anastomosis stays SAME, held relation:contradiction, by the fact pass's act-lesion pair and by an established
  Q-ONLESION answer alike; pair 4's shape (the ruled release) is left alone.
- PlannerPredicateTests (the engine lane's Q-R1, Q-R2, Q-R3 and Q1, the ask lane's Q6): the planner reads the fold's own
  predicates - facts.answerable (so no date check is asked: R3BE-RF1's planner half), facts.JUDGED, facts.pair_judged
  (so no judged act-lesion pair is re-asked: R3BE-RF2's) and the release arm's own what-if, pairing.not_on_sets_apart.
- SilentReachTests (ASK2-1): a silent reach list asks only the code family's reachable outer points.
- UncalibratedStageTests (ASK2-2): a plan-time refusal (no calibration item) is recorded, never a failed stage.
- RecordingFaultTests (RF2-PIPE-3): a failed recording never releases the provider lock with a request in flight, and
  an exception that leaves the round still waits for every request and records what arrived.
- CarriedRFX1Tests, CarriedF3Tests: DECISIONS D316's carried RFX-1 (the D228_DQ2 predicate names only the unclaimed
  corner) and F3 (store.py's mypy --strict errors, a ratchet).
"""
from __future__ import annotations

from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute, Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2fm_lesion as R2FM

A, LM = Attribute, ct.Landmark
E3, E4 = Id.parse('E3'), Id.parse('E4')
L1, Y1 = Id.parse('L1'), Id.parse('Y1')
SINGLE_TARGET, LISTED = ct.Breadth.SINGLE_TARGET, ct.Breadth.LISTED_TARGETS
INDEPENDENT, SAME = pairing.RowResult.INDEPENDENT, pairing.RowResult.SAME
CONTRADICTION = pairing.Relation.CONTRADICTION
sup, unres, neg, doubted = EF.sup, EF.unres, EF.neg, EF.doubted


def doubted_empty(*readings):
    """An empty slot a doubt names (3.3 row 2 over a slot pass 1 left empty): unknown, no claimed value, the doubt's
    readings its options - never a pure-silent slot (coverage._pure_silent)."""
    return EF.fact(ct.Result.UNKNOWN, None, None, options=readings, reasons=(ct.Reason.DOUBT_STATED,))


def target(R, statement=E3, act=E4):
    return pairing.row(R, pairing.Row.TARGET, statement, act)


def held_causes(R, code: str) -> list:
    return sorted({held.cause for held in evaluate.decide(code, (), R).held_facts})


def pair4(**over):
    """Pair 4's shape (D305's ruled release): L1 (single) in the transverse colon, the denial E3 of an injection on its
    single target L1 placed at L1's place only, the tattoo E4 in the transverse colon naming no lesion, the act-lesion
    pair (E4, distinct_from, L1) established - INDEPENDENT, 45381 READY."""
    return R2FM.scene(breadth=over.pop('breadth', SINGLE_TARGET), not_on=over.pop('not_on', (L1,)),
                      denial_places=(LM.TRANSVERSE_COLON,), act_places=(LM.TRANSVERSE_COLON,), **over)


def with_facts(R, subject, **facts):
    """``R`` with ``subject``'s facts given by attribute (each a Fact, single-valued) added or replaced."""
    found = {**R.events[subject], **{getattr(A, name): (fact,) for name, fact in facts.items()}}
    return replace(R, events={**R.events, subject: found})


def with_anastomosis(R, entry_facts=None):
    """``R`` holding the anatomy entry Y1: an anastomosis whose organ the note does not state (or ``entry_facts``) -
    round r3's round 5 (DECISIONS D330 (1), lane rules6): its subtype and joins filed as the development set files every
    anastomosis (ileocolic, the ileum and the colon), since one whose subtype and joins are both silent is the D328
    addendum's residual, which the lower-GI path guard now holds, and the pairing rule is what these scenes measure."""
    facts = entry_facts if entry_facts is not None else {
        A.TYPE: (sup(ct.AnatomyType.ANASTOMOSIS),), A.SUBTYPE: (sup(ct.AnastomosisSubtype.ILEOCOLIC),),
        A.JOINS: (sup(LM.ILEUM), sup(LM.COLON))}
    return replace(R, anatomy={**R.anatomy, Y1: facts})


def at_the_anastomosis(fact=None, **over):
    """R2E-QB-ANAT's scene (the second refutation's p02/p05): pair 4's shape with the denial ALSO at the anastomosis Y1,
    its target.anatomy (``fact``: supported by default), and the tattoo at Y1 too."""
    R = with_anastomosis(pair4(**over))
    R = with_facts(R, E3, TARGET_ANATOMY=fact if fact is not None else sup(Y1))
    return with_facts(R, E4, TARGET_ANATOMY=sup(Y1))


class QBAnatomyTests(SimpleTestCase):
    def test_the_findings_scene_is_held(self):
        # the must-change pin (R2E-QB-ANAT): the denial's own anastomosis holds the tattoo's place - catalogue.covers
        # reads a tattoo and an injection as one act, so the note contradicts itself; the lanes' tree set it apart
        R = at_the_anastomosis()
        self.assertIs(F.established_not_on(R, E4, L1), True)
        self.assertEqual(target(R), SAME)
        self.assertIs(pairing.relation(R, E3, E4).relation, CONTRADICTION)
        self.assertEqual(held_causes(R, '45381'), ['relation:contradiction'])
        self.assertIs(pairing.not_on_sets_apart(R, E3, E4), False)  # no true Q-ONLESION answer could release it

    def test_every_state_of_the_anatomy_target_but_an_established_negation_holds(self):
        # the anatomy target in any state but an established negation (its claimed value kept, a doubt's reading, a
        # contradiction's side): SAME every time; a listed denial too
        cases = {
            'supported': at_the_anastomosis(),
            'unresolved': at_the_anastomosis(unres(Y1)),
            "a doubt's reading": at_the_anastomosis(doubted(Id.parse('Y2'), Y1)),
            "a doubt's reading of an empty slot": at_the_anastomosis(doubted_empty(Y1)),
            "a contradiction's side": at_the_anastomosis(EF.contra(Id.parse('Y2'), Y1)),
            'the tattoo not at the anastomosis': with_facts(at_the_anastomosis(), E4, TARGET_ANATOMY=EF.SILENT),
            'a listed denial': at_the_anastomosis(breadth=LISTED, l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, Id.parse('L2'))),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(target(R), INDEPENDENT)
                self.assertNotEqual(pairing.relation(R, E3, E4).relation, pairing.Relation.INDEPENDENT)

    def test_every_structure_but_a_lesion_holds(self):
        for structure in (ct.Structure.ANASTOMOSIS, ct.Structure.WALL, ct.Structure.STENT):
            for fact in (sup(structure), unres(structure), doubted_empty(structure)):
                with self.subTest(structure=structure.value, result=fact.result.value):
                    R = with_facts(pair4(), E3, TARGET_STRUCTURE=fact)
                    self.assertEqual(target(R), SAME)
                    self.assertEqual(held_causes(R, '45381'), ['relation:contradiction'])
                    self.assertIs(pairing.not_on_sets_apart(R, E3, E4), False)

    def test_the_boundary_pair_4s_shape_a_lesion_structure_and_an_established_negation_stay_apart(self):
        # the ruled release the clause leaves alone: pair 4's shape; its structure stated as the lesion; the anatomy
        # target or a non-lesion structure established NOT the denial's (an established negation names nothing); the
        # anatomy entry held by the FactSet but named by the act alone
        cases = {
            "pair 4's shape": pair4(),
            'the structure a lesion': with_facts(pair4(), E3, TARGET_STRUCTURE=sup(ct.Structure.LESION)),
            "a doubt's reading of the structure a lesion": with_facts(pair4(), E3,
                                                                      TARGET_STRUCTURE=doubted_empty(ct.Structure.LESION)),
            'a pure-silent anatomy and structure': with_facts(pair4(), E3, TARGET_ANATOMY=EF.SILENT,
                                                             TARGET_STRUCTURE=EF.SILENT),
            'the anatomy established not the denial\'s': at_the_anastomosis(neg(Y1)),
            'an anastomosis structure established not the denial\'s': with_facts(
                pair4(), E3, TARGET_STRUCTURE=neg(ct.Structure.ANASTOMOSIS)),
            'the act alone at the anastomosis': with_facts(with_anastomosis(pair4()), E4, TARGET_ANATOMY=sup(Y1)),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertEqual(target(R), INDEPENDENT)
                self.assertEqual(held_causes(R, '45381'), [])
                self.assertIs(pairing.not_on_sets_apart(R, E3, E4), True)

    def test_an_established_q_onlesion_answer_is_held_there_too(self):
        # D323 F1's one arm: the answer is read as the fact pass's pair is - the scene with the fact pass's pair left
        # unasked and a TRUE Q-ONLESION answer folded in (R_q) stays held; pair 4's shape releases by it
        for name, R, released in (('the finding', at_the_anastomosis(), False), ("pair 4's shape", pair4(), True)):
            with self.subTest(case=name):
                bare = replace(R, pair_controls={key: value for key, value in R.pair_controls.items()
                                                 if key != (E4, A.DISTINCT_FROM, L1)})
                answered = replace(bare, off_lesion=frozenset({(E4, L1)}), base=bare)
                self.assertEqual(target(bare), SAME)
                self.assertEqual(target(answered) is INDEPENDENT, released)


# --- the planner reads the fold's own predicates (the engine lane's Q-R1, Q-R2, Q-R3, Q1; the ask lane's Q6) -------------

def onlesion_specs(plan):
    return [spec for spec in plan.specs if spec.family is asking.Family.Q_ONLESION]


class PlannerPredicateTests(SimpleTestCase):
    """The planner asks only what an answer could establish and the fold would read: facts.answerable is the planner's
    askable test, settle's re-check (asking.eligible) and the fold's, one predicate; asking._C2B IS facts.JUDGED; a
    Q-ONLESION question is never asked over a pair the fact pass judged (facts.pair_judged) nor where the release arm's
    own what-if (pairing.not_on_sets_apart) says no true answer could set the pair apart."""

    def test_the_planner_settle_and_the_fold_share_one_predicate(self):
        self.assertIs(asking._C2B, F.JUDGED)
        for reason in ct.Reason:
            for result in (ct.Result.UNRESOLVED, ct.Result.CONTRADICTED, ct.Result.UNKNOWN):
                found = replace(unres(LM.CECUM), result=result, reasons=(reason,))
                with self.subTest(reason=reason.value, result=result.value):
                    self.assertEqual(asking._askable_open(found), F.answerable(found))
        self.assertTrue(asking._askable_open(unres(LM.CECUM, ct.Reason.UNAPPRAISED)))  # the boundary: a reading open

    def test_a_date_check_is_never_asked(self):
        # R3BE-RF1's planner half: the finding's stored row (the note states no date of service, so L1 demotes both
        # acts' date relations literal_unchecked): the lanes' planner asked both date questions (census F1), which no
        # answer could ever establish (the fold refuses an answer over a date check); none is asked now
        from tests.v2 import test_r3b_engine as RE
        view = RE.dated_view()
        R = F.effective(view, None)
        self.assertEqual([F.fact(R, event, A.DATE_RELATION).reasons for event in (RE.E1, RE.E2)],
                         [(ct.Reason.LITERAL_UNCHECKED,)] * 2)
        plan = asking.plan(R, (), view)
        self.assertEqual([spec for spec in plan.specs if spec.attribute is A.DATE_RELATION], [])
        spec = asking.QuestionSpec(asking.Family.Q_FACT, 'fact.date_relation', ('E2',), A.DATE_RELATION,
                                   'on_date_of_service', False, ('E2',), census='F1')
        self.assertIs(asking.eligible(spec, R), False)  # settle's re-check refuses it too

    def test_a_judged_act_lesion_pair_is_never_asked_and_a_pair_with_no_verdict_is(self):
        # R3BE-RF2's planner half (the refuter's r09): pair 4's shape with "This act was not done on lesion L1."
        # contradicted and its control supported - the fact pass judged the tattoo done on L1; the lanes' planner asked
        # it again as Q-ONLESION (the fold then refuses the answer). The boundary: no usable verdict (C2a) is asked
        from tests.v2 import test_r3b_engine as RE
        judged = RE.p4_view(RE.act_lesion_oracle(RE.said('contradicts'), RE.said('supports')))
        plan = asking.plan(F.factset(judged), (), judged)
        self.assertEqual(onlesion_specs(plan), [])
        self.assertIn(asking.ONLESION_JUDGED, plan.blocked)
        missing = RE.p4_view(RE.act_lesion_oracle(None, RE.said('contradicts')))
        plan = asking.plan(F.factset(missing), (), missing)
        self.assertEqual([(spec.form, spec.subjects) for spec in onlesion_specs(plan)], [('onlesion', ('E4', 'L1'))])

    def test_the_arms_own_what_if_is_a_necessary_condition(self):
        # the planner follows every reading of the release arm: R2E-QB-ANAT's scene (the arm holds it now) asks no
        # Q-ONLESION question - the lanes' planner asked one, its own copy of the QB rule reading no anatomy target -
        # and pair 4's shape still asks it (the fact pass's pair left unasked, so the question is the only release)
        def bare(R):
            return replace(R, pair_controls={key: value for key, value in R.pair_controls.items()
                                             if key != (E4, A.DISTINCT_FROM, L1)})
        for name, R, asked in (('R2E-QB-ANAT', bare(at_the_anastomosis()), False), ("pair 4's shape", bare(pair4()), True)):
            with self.subTest(case=name):
                plan = asking.plan(R)
                self.assertEqual(bool(onlesion_specs(plan)), asked)
                if not asked:
                    self.assertIn(asking.ONLESION_ARM, plan.blocked)


# --- the question stage (studio/jobs.py): ASK2-2 and RF2-PIPE-3 ------------------------------------------------------

def _stage():
    """tests/v2/test_question_stage and the names its scaffolding needs (imported when a stage test runs: it builds the
    v2 pipeline's database scaffolding)."""
    from studio import jobs, models
    from tests.v2 import test_question_stage as QS
    return jobs, models, QS


def uncalibrated_round_case():
    jobs, models, QS = _stage()
    from unittest import mock

    class UncalibratedStageTests(QS.QuestionCase):
        """ASK2-2 (the second refutation, medium; the class rule: a plan-time refusal is data that every caller of
        asking.partition and asking.split records per question, never an exception that fails the stage): a request
        the planner refuses for want of its calibration item (asking.UncalibratedRequest, DECISIONS D323 F4) is never
        sent; its questions are recorded refused - question_health:uncalibrated - in the stage's result, the row is
        written, and the document is assessed with its holds kept. The lanes' stage FAILED the document ('The stored
        answer could not be read'), every retry the same; with the pool emptied from the start the failing job was
        APPRAISE, after passes 1 and 2 were paid."""

        def test_an_empty_pool_at_the_question_stage_refuses_the_request_and_writes_the_row(self):
            encounter, revision, queued = self.to_questions(QS.SESSION_E2)
            with mock.patch.object(asking, 'calibration_pool', return_value=()):
                done = self.finish(encounter)
            kinds = [(job.kind, job.state) for job in done]
            self.assertEqual(kinds[0], (QS.QUESTION, models.Job.SUCCEEDED), kinds)
            self.assertIn(('assess', models.Job.SUCCEEDED), kinds)
            refused = done[0].result['questions']['refused']
            self.assertTrue(refused)
            self.assertEqual({item['reason'] for item in refused}, {asking.UNCALIBRATED})
            self.assertEqual(len(self.interpreter.question_sent), 0)  # nothing sent
            [inventory] = models.EventInventory.objects.filter(revision=revision)
            self.assertNotIn('questions', inventory.events)  # nothing was sent: the row as before r3
            self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

        def test_an_empty_pool_at_the_appraise_stage_writes_the_row_with_no_question_stage(self):
            # the verifier's correction: with the pool empty from the start, round 1 is planned by APPRAISE itself
            from tests.v2 import test_jobs as TJ
            with mock.patch.object(asking, 'calibration_pool', return_value=()):
                self.questioned(QS.SESSION_E2)
                encounter, revision = self.upload(TJ.POLYP)
                done = self.drain()
            kinds = [(job.kind, job.state) for job in done]
            self.assertIn(('appraise', models.Job.SUCCEEDED), kinds)
            self.assertNotIn(QS.QUESTION, [job.kind for job in done])
            self.assertIn(('assess', models.Job.SUCCEEDED), kinds)
            self.assertEqual(len(self.interpreter.question_sent), 0)
            self.assertEqual(models.EventInventory.objects.filter(revision=revision).count(), 1)
            self.assertEqual(self.status(encounter, '45385'), 'needs_clarification')

        def test_the_boundary_a_pool_with_an_item_sends_and_releases(self):
            encounter, revision, queued = self.to_questions(QS.SESSION_E2)
            done = self.finish(encounter)
            self.assertEqual(done[0].state, models.Job.SUCCEEDED)
            self.assertNotIn('refused', done[0].result['questions'])
            self.assertEqual(len(self.interpreter.question_sent), 1)
            self.assertEqual(self.status(encounter, '45385'), 'ready')

    return UncalibratedStageTests


def recording_fault_case():
    jobs, models, QS = _stage()
    import threading
    import time
    from unittest import mock

    from django.db import connection, connections
    from django.db.utils import OperationalError

    from tests.v2 import test_jobs as TJ

    PREFIX = 'cpt-studio-question-'

    def question_threads():
        return [thread for thread in threading.enumerate() if thread.name.startswith(PREFIX) and thread.is_alive()]

    def lock_free():
        """Whether ANOTHER database session takes PROVIDER_LOCK_KEY now (released at once if it does)."""
        found = {}

        def probe():
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute('SELECT pg_try_advisory_lock(%s)', [jobs.PROVIDER_LOCK_KEY])
                    found['free'] = bool(cursor.fetchone()[0])
                    if found['free']:
                        cursor.execute('SELECT pg_advisory_unlock(%s)', [jobs.PROVIDER_LOCK_KEY])
            finally:
                connections['default'].close()
        thread = threading.Thread(target=probe)
        thread.start()
        thread.join(timeout=20)
        return found.get('free')

    class RecordingFaultTests(QS.QuestionCase):
        """RF2-PIPE-3 (the second refutation, medium; carried from the first refutation's R5, the lead's verify-PIPE-R3):
        a round of two requests whose FIRST outcome's recording raises (a database error after its real recording)
        while the second is still in flight. The lanes' stage left the loop through its finally and released the
        single-flight lock with the second request in flight - another job sent meanwhile, the answer was lost and the
        identical request paid again after a sweep and a reconciliation. The class rule: each outcome recorded inside
        its own guard; the lock released only after every request thread of the round has ended."""

        def test_a_failed_recording_keeps_the_lock_until_every_request_has_ended(self):
            gate, inside, during, unlocks = threading.Event(), threading.Event(), {}, []

            def immediate(sha, question):
                return TJ.answered(TJ.body(QS.question_answer(question, question.request.contexts[0])))

            def held(sha, question):
                inside.set()
                gate.wait(timeout=90)
                return TJ.answered(TJ.body(QS.question_answer(question, question.request.contexts[0])))

            def watcher():
                inside.wait(timeout=60)
                time.sleep(0.5)  # the first outcome recorded (and its recording raised) meanwhile
                during['free'] = lock_free()
                gate.set()

            def spy(execute, sql, params, many, context):
                if 'pg_advisory_unlock' in sql:
                    unlocks.append([thread.name for thread in question_threads()])
                return execute(sql, params, many, context)
            real, calls = jobs._finish_question_run, []

            def recording(encounter, run, outcome):
                calls.append(str(run.pk))
                real(encounter, run, outcome)
                if len(calls) == 1:
                    raise OperationalError('synthetic: a database error while the outcome was recorded')
            with mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                                   QS.ConcurrencyTests.partition(specs, pool, round_)):
                encounter, revision, queued = self.to_questions(QS.SESSION_E2, ('E1', A.SESSION),
                                                                question_script=[immediate, held])
                watch = threading.Thread(target=watcher)
                watch.start()
                with mock.patch.object(jobs, '_finish_question_run', side_effect=recording), \
                        connection.execute_wrapper(spy):
                    done = self.run_next(QS.QUESTION)
                watch.join(timeout=30)
                gate.set()
                runs = self.question_runs(encounter)
                self.assertIs(during['free'], False)  # the second request in flight: no other session took the lock
                self.assertEqual(unlocks, [[]])  # unlocked once, no question thread alive
                self.assertEqual(done.state, models.Job.SUCCEEDED, done.error)
                self.assertEqual([run.state for run in runs], [models.ProviderRun.SUCCEEDED] * 2)
                rest = self.finish(encounter)
            sent = list(self.interpreter.question_sent)
            self.assertEqual(len(sent), 2)
            self.assertEqual(len(set(sent)), 2)  # neither request is sent again
            self.assertIn(('assess', models.Job.SUCCEEDED), [(job.kind, job.state) for job in rest])

        def test_an_exception_leaving_the_round_waits_for_every_request_and_records_what_arrived(self):
            # the class rule's other path: ANY exception that leaves the round's loop - here the first outcome's guarded
            # recording itself raising before it records, as a stop arriving there would - releases the lock only after
            # every request thread has ended, and the outcome the second thread delivered meanwhile is recorded as it
            # came (its run SUCCEEDED), never as unknown; the first run, whose recording never happened, is left
            # 'sending' (an unknown outcome to every send door, settled by the stale sweep), never succeeded
            gate, inside, during, unlocks = threading.Event(), threading.Event(), {}, []

            def immediate(sha, question):
                return TJ.answered(TJ.body(QS.question_answer(question, question.request.contexts[0])))

            def held(sha, question):
                inside.set()
                gate.wait(timeout=90)
                return TJ.answered(TJ.body(QS.question_answer(question, question.request.contexts[0])))

            def watcher():
                inside.wait(timeout=60)
                time.sleep(0.5)  # the first outcome taken (and its recording raised) meanwhile
                during['free'] = lock_free()
                gate.set()

            def spy(execute, sql, params, many, context):
                if 'pg_advisory_unlock' in sql:
                    unlocks.append([thread.name for thread in question_threads()])
                return execute(sql, params, many, context)
            real, calls = jobs._record_question_outcome, []

            def recording(encounter, run, outcome):
                calls.append(str(run.pk))
                if len(calls) == 1:
                    raise RuntimeError('synthetic: the round left while an outcome was recorded')
                real(encounter, run, outcome)
            with mock.patch.object(asking, 'partition', side_effect=lambda specs, pool, round_, bound=None:
                                   QS.ConcurrencyTests.partition(specs, pool, round_)):
                encounter, revision, queued = self.to_questions(QS.SESSION_E2, ('E1', A.SESSION),
                                                                question_script=[immediate, held])
                watch = threading.Thread(target=watcher)
                watch.start()
                with mock.patch.object(jobs, '_record_question_outcome', side_effect=recording), \
                        connection.execute_wrapper(spy):
                    done = self.run_next(QS.QUESTION)
                watch.join(timeout=30)
                gate.set()
            runs = self.question_runs(encounter)
            self.assertIs(during['free'], False)  # the second request in flight: no other session took the lock
            self.assertEqual(unlocks, [[]])  # unlocked once, no question thread alive
            self.assertNotEqual(done.state, models.Job.SUCCEEDED)  # the exception ended the stage, as any would
            self.assertEqual(len(calls), 2)
            self.assertEqual(runs[1].state, models.ProviderRun.SUCCEEDED)  # delivered meanwhile: recorded as it came
            self.assertNotEqual(runs[0].state, models.ProviderRun.SUCCEEDED)
            self.assertEqual(len(self.interpreter.question_sent), 2)

    return RecordingFaultTests


UncalibratedStageTests = uncalibrated_round_case()
RecordingFaultTests = recording_fault_case()


# --- DECISIONS D316's carried items (round r3's test list) ------------------------------------------------------------

class CarriedRFX1Tests(SimpleTestCase):
    """D316's carried RFX-1 (f-engine's refutation, low, a test gap): test_properties' D228_DQ2 predicate
    (_which_pairs_corner) named ANY release under a weakening of an inherited other date or performer - so a regression
    dropping D309's claimed arm (a plan of an inherited later date whose scope.covers names today's removal) passed
    PMonoTests.check as "DQ2 stays as built". The corner is the UNCLAIMED one: a claimed pair's release is named by no
    ruling. The refuter's p5 scene, its claimed arm removed in memory (int2's pairing.paired), then as built."""

    @staticmethod
    def int2_paired(R, statement, act):
        from studio.interpretation.contract import types as ct_
        return (statement != act and pairing.is_statement(R, statement)
                and F.possibly(F.fact(R, act, A.STATUS), ct_.Status.PERFORMED)
                and bool(pairing.shared_kinds(R, statement, act)))

    def scene(self):
        from tests.v2 import test_r2fe_engine as FE
        R = FE.q4_scene(date=FE.sup(FE.LATER, inherited_from=FE.N1))
        [(label, weak, what)] = [w for w in FE.corner_weakenings(R, (A.DATE_RELATION,))
                                 if w[0] == 'unresolved E3 date_relation[0]']
        return FE, R, label, weak, what

    def test_a_claimed_pairs_release_is_named_by_no_ruling(self):
        from unittest import mock
        from tests.v2 import test_properties as TP
        FE, R, label, weak, what = self.scene()
        self.assertTrue(pairing.relation(R, Id.parse('E3'), Id.parse('E2')).claimed)
        with mock.patch.object(pairing, 'paired', self.int2_paired):  # D309's claimed arm removed: the regression
            base, after = TP.assessed(R, FE.Q4_CODES), TP.assessed(weak, FE.Q4_CODES)
            self.assertEqual({code.code: code.status.value for code in after.codes}['45385'], 'ready')
            self.assertIs(TP._which_pairs_corner(label, what, '45385', R), False)
            with self.assertRaises(AssertionError):  # PMonoTests.check refuses it: READY grew, no ruling accepts it
                TP.PMonoTests.check(TP.PMonoTests(), base, after, label, what, R)

    def test_the_boundary_as_built_the_claimed_pair_is_kept_and_nothing_is_released(self):
        from tests.v2 import test_properties as TP
        FE, R, label, weak, what = self.scene()
        self.assertTrue(pairing.paired(weak, Id.parse('E3'), Id.parse('E2')))
        base, after = TP.assessed(R, FE.Q4_CODES), TP.assessed(weak, FE.Q4_CODES)
        self.assertEqual({code.code: code.status.value for code in after.codes}['45385'], 'needs_clarification')
        self.assertEqual(TP.PMonoTests.check(TP.PMonoTests(), base, after, label, what, R), [])


# store.py's mypy --strict errors by error code, on int4 (D316's carried F3: int2 192 -> int3 197 -> int4 198, the r3
# question stage's binding code: name-defined 3, no-any-return 12, no-untyped-call 41, no-untyped-def 85, type-arg 55,
# var-annotated 2). A RATCHET: no count may grow; a change that removes errors lowers its own count here.
STORE_MYPY_RATCHET = {'name-defined': 3, 'no-any-return': 12, 'no-untyped-call': 41, 'no-untyped-def': 85,
                      'type-arg': 55, 'var-annotated': 2}


def mypy_counts(output: str) -> dict[str, int]:
    """{error code: count} of mypy's output lines ('file:line: error: ...  [code]')."""
    import re
    counts: dict[str, int] = {}
    for line in output.splitlines():
        found = re.search(r': error: .*\[([a-z-]+)\]$', line)
        if found:
            counts[found.group(1)] = counts.get(found.group(1), 0) + 1
    return counts


def grown(counts: dict[str, int], ratchet: dict[str, int]) -> dict[str, tuple[int, int]]:
    """Each error code whose count is above the ratchet's (a code the ratchet does not list: above 0)."""
    return {code: (count, ratchet.get(code, 0)) for code, count in counts.items() if count > ratchet.get(code, 0)}


class CarriedF3Tests(SimpleTestCase):
    """D316's carried F3 (the int3 checker, low): no gate typed studio/interpretation/store.py, whose mypy --strict
    errors grew 192 -> 197 unnoticed. This ratchet runs mypy --strict --follow-imports=silent on it (as test_pairing's
    BoundaryTests runs it on engine/pairing.py) and fails on any error code whose count grows; the positive control
    shows the ratchet flags one more error."""

    def test_store_mypy_errors_never_grow(self):
        import os
        import subprocess
        import sys
        from pathlib import Path
        tree = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir',
                                 os.devnull, 'studio/interpretation/store.py'], cwd=tree, capture_output=True, text=True,
                                timeout=600)
        counts = mypy_counts(result.stdout)
        self.assertTrue(counts, result.stdout + result.stderr)  # mypy ran and reported (the instrument answers)
        self.assertEqual(grown(counts, STORE_MYPY_RATCHET), {}, result.stdout[-2000:])

    def test_the_ratchet_flags_one_more_error(self):  # the positive control
        line = 'studio/interpretation/store.py:1: error: Function is missing a type annotation  [no-untyped-def]'
        at = '\n'.join([line] * (STORE_MYPY_RATCHET['no-untyped-def'] + 1))
        self.assertEqual(grown(mypy_counts(at), STORE_MYPY_RATCHET), {'no-untyped-def': (86, 85)})
        self.assertEqual(grown(mypy_counts(line + '\n' + line.replace('no-untyped-def', 'misc')), STORE_MYPY_RATCHET),
                         {'misc': (1, 0)})


# --- ASK2-1: the A3 reach values a silent reach list asks ----------------------------------------------------------------

def a3_scene(family, act_kind, place, reached=()):
    """The second refutation's p05c scene: one session of ``family`` (its reach list SILENT unless ``reached``), its
    examination E1 done and one act E2 at ``place``, every act's frame facts controlled (so the calibration pool draws)."""
    doc = EF.Doc()
    doc.session(1, family, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=list(reached))
    doc.exam(1)
    doc.act(2, act_kind, places=[sup(place)])
    R = doc.build()
    return replace(R, controlled=frozenset({(EF.E(n), attribute) for n in (1, 2)
                                            for attribute in (A.DATE_RELATION, A.ENTRY, A.PERFORMER, A.SESSION)}))


def a3_values(R) -> list:
    return sorted(spec.value for spec in asking.plan(R).specs if spec.census == 'A3' and spec.attribute is A.REACHED)


class SilentReachTests(SimpleTestCase):
    """ASK2-1 (the second refutation, medium; the class rule: every value a question asks is one its subject's own family
    can hold, read from the catalogue's billing tables, never every member of an enumeration): an EGD or a flexible
    sigmoidoscopy whose pass 1 filed no reached point asked one A3 question per Extent member - 51 in 7 requests, about
    $36 reserved for a short note. Now the values are the code family's reachable points (catalogue.FAMILY_REACH) that
    move the witness, and of them only the outermost (a deeper point reached establishes the outer one containing it)."""

    def test_an_egd_and_a_flexible_sigmoidoscopy_ask_their_familys_outer_points_in_one_request(self):
        for family, place, expected in (
                (ct.SessionKind.EGD, LM.GASTRIC_ANTRUM, ['duodenum', 'esophagus', 'stomach']),
                (ct.SessionKind.FLEX_SIG, LM.SIGMOID_COLON, ['anal_canal', 'colon', 'rectum'])):
            with self.subTest(family=family.value):
                R = a3_scene(family, ct.Kind.BIOPSY, place)
                self.assertEqual(a3_values(R), expected)
                plan = asking.plan(R)
                self.assertEqual(len(asking.partition(plan.specs, asking.calibration_pool(R), 1)), 1)

    def test_every_value_asked_is_one_the_family_reaches(self):
        from studio.interpretation.engine import anatomy, catalogue
        for family, place in ((ct.SessionKind.EGD, LM.GASTRIC_ANTRUM), (ct.SessionKind.FLEX_SIG, LM.SIGMOID_COLON)):
            with self.subTest(family=family.value):
                regions = catalogue.FAMILY_REACH[family]
                self.assertTrue(all(anatomy.region(ct.Extent(value)) in regions
                                    for value in a3_values(a3_scene(family, ct.Kind.BIOPSY, place))))

    def test_the_boundary_a_colfull_reach_and_a_filed_reach(self):
        # COLFULL keeps its full colonoscopy reach, the outermost of it (the cecum, the small bowel); a filed reach asks
        # no A3 question at all (F8 asks the claimed value)
        self.assertEqual(a3_values(a3_scene(ct.SessionKind.COLONOSCOPY, ct.Kind.BIOPSY, LM.SIGMOID_COLON)),
                         ['cecum', 'small_bowel'])
        self.assertEqual(a3_values(a3_scene(ct.SessionKind.EGD, ct.Kind.BIOPSY, LM.GASTRIC_ANTRUM,
                                            reached=(unres(ct.Extent.SECOND_PORTION_DUODENUM),))), [])
