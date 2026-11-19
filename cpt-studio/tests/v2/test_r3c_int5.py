"""Round r3's integration int5 (DECISIONS D324): the lanes' questions that needed a change outside their owners' files,
each built as its lane gave it and pinned here. Every input is SYNTHETIC (tests/v2/evaluate_fixtures' builders and the
lanes' own scenes, imported from their modules); no document is read and nothing is sent. Red on the lanes' merge (the
five patches applied to int4, nothing else): each class pins a rule the merge does not have, but the boundaries and the
equivalence tests, which hold on both by design.

- ExclusivityCallSiteTests (D324 (2); the claims lane's Q1, studio/jobs.py): exclusivity reads every proposition of a
  slot in any request or round - the questions refused at PLAN time too (asking.UncalibratedRequest: never sent, so no
  record). Each refused entry names its slot (attribute, value, negated), and the stage passes them to
  settle.exclusive: a value whose rival proposition was refused at plan time is held (question_conflict). The claims
  lane's own L4-1 pipeline scene (one request, E6 at X1 answered wrong consistently), with E6's X2 refused at plan time.
- NeverAskedTests (D324 (4); the fold lane's Q-F5, engine/asking.py): what the fold never folds is never asked - on
  every planner path (F2, G1, F11/F12, C6, a ruled-out value in a later round) a Q-FACT question whose established
  answer facts.folds refuses is dropped, asking's C6 conflicts ARE facts.CONFLICTS (K4's anatomy_conflict is a
  fixed-table check), and settle's re-check (asking.eligible) reads facts.folds; the property over every scene of this
  module: every planned Q-FACT question folds.
- CauseRuledOutTests and HemostasisRuledOutTests (D324 (1); the fold lane's Q-F1, Q-F2 and Q-F3, engine/coverage.py
  and engine/evaluate.py): a negation answer removes its value - and only its value - for the field readers of the
  cause and the claimed hemostasis too: an answered "not caused by another act of this procedure" is no silent slot
  (coverage._pure_silent) and rules the procedural adjunct out (coverage._not_adjunct), so F12's question releases what
  it was asked for; an answered "not done for treatment of bleeding" is no claimed hemostasis
  (evaluate._claims_hemostasis). Every other value reads as before.
- PlanReadsOnceTests (D324 (8); the ask lane's Q1 (a) and (b), engine/pairing.py and engine/evaluate.py): the
  Q-ONLESION what-if (pairing.not_on_sets_apart) reads the act through R's own reads, built once per FactSet; evaluate's
  row 8 reads an act's pairs through the caller's coverage.Reader (whatif passes its own); both equal the lanes'
  computation (equivalence over the scenes) - the measured bound is test_r3c_ask.PlanCostTests'.
- OrganClosureTests (P-INDEP for D324 (5); the rules lane's Q1, engine/requirements.py): COLFULL's closure holds every
  anatomy entry's organ, which the colonic route, the colon filed absent and the lower-tract stoma closure read.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from studio import jobs
from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, coverage, evaluate, pairing, whatif
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Id, Outcome
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r3c_ask as TRCA
from tests.v2 import test_r3c_claims as TRCC
from tests.v2 import test_r3c_fold as T
from tests.v2 import test_r3c_rules as TRR

A = ct.Attribute
Kind, Status, Landmark = ct.Kind, ct.Status, ct.Landmark
P, C, R_ = ct.Purpose, ct.Cause, ct.Reason
sup, neg, unres, doubted, X, E, L = EF.sup, EF.neg, EF.unres, EF.doubted, EF.X, EF.E, EF.L
FOLD_REFUSED = 'the fold would refuse its answer: facts.folds'


def q_fact(plan: asking.Plan) -> list[tuple]:
    """Every Q-FACT question a plan asks: (census row, form, subjects, value, negated)."""
    return [(spec.census, spec.form, spec.subjects, spec.value, spec.negated) for spec in plan.specs
            if spec.family is asking.Family.Q_FACT]


def folds(R, spec: asking.QuestionSpec) -> bool:
    subject = F._subject_of(spec.subjects[0]) if spec.subjects else None
    return F.folds(R, subject, spec.attribute, spec.value, spec.negated)


# --- D324 (2) at its jobs.py call site (the claims lane's Q1) ----------------------------------------------------------


class RefusedEntryTests(SimpleTestCase):
    def test_each_refused_entry_names_its_slot(self) -> None:
        # jobs._refused_questions: the slot's fields as settle's records name them, so settle holds that slot only
        spec = TRCC.at_session('X2')
        entries = jobs._refused_questions(asking.UncalibratedRequest(((spec,),)), 1)
        self.assertEqual([(entry['attribute'], entry['value'], entry['negated']) for entry in entries],
                         [('session', 'X2', False)])
        self.assertEqual(settle._slot_of(entries[0]), (('E3',), 'session'))
        records = TRCC.answered(TRCC.request(TRCC.at_session('X1')), {TRCC.at_session('X1').key: 'release'})
        self.assertEqual(TRCC.by_value(settle.exclusive(records, entries))[('X1', False)], TRCC.CONFLICT)
        other = jobs._refused_questions(asking.UncalibratedRequest(((TRCC.fact_spec('fact.purpose', A.PURPOSE,
                                                                                    'removal'),),)), 1)
        self.assertEqual(TRCC.by_value(settle.exclusive(records, other))[('X1', False)], TRCC.SUPPORTED)  # another slot


class ExclusivityCallSiteTests(TRCC.VerifyCase):
    """The claims lane's L4-1 pipeline scene in ONE request (no E1 question), E6 at X1 answered WRONG consistently,
    and E6's rival X2 refused at PLAN time (its request has no calibration item: asking.UncalibratedRequest, patched in
    here - the claims lane measured that today's document-wide pool never refuses one request alone)."""

    def walk_refusing_x2(self):
        real = asking.partition

        def refusing(specs, pool, round_, bound=asking.QUESTION_BOUND):
            rival = tuple(spec for spec in specs if TRCC.spec_of(SimpleItem(spec)) == TRCC.LAST_X2)
            requests = real(tuple(spec for spec in specs if spec not in rival), pool, round_, bound)
            if rival:
                raise asking.UncalibratedRequest((rival,), requests)
            return requests
        with mock.patch.object(asking, 'partition', refusing):
            return self.walk(leave=())

    def test_a_plan_time_refusal_of_the_rival_holds_the_answered_value(self) -> None:
        out = self.walk_refusing_x2()
        # X2 was never sent (no record); its plan-time refusal holds the slot (the merge: X1 supported, 45380 READY - a
        # colonoscopy code on a gastric biopsy)
        self.assertEqual(self.last(out), [('X1', 'unresolved', ['question_conflict'])])
        self.assertEqual(out['statuses']['45380'], 'needs_clarification')

    def test_the_boundary_with_nothing_refused_the_answers_decide(self) -> None:
        # the same scene sent whole: the rival X2 asked and answered (right), and exclusivity holds both as before
        out = self.walk(leave=())
        self.assertEqual(out['statuses']['45380'], 'needs_clarification')


class SimpleItem:
    """A planned spec dressed as a request item (test_r3c_claims.spec_of reads ``item.spec``)."""

    def __init__(self, spec) -> None:
        self.spec = spec


# --- D324 (4): what the fold never folds is never asked (the fold lane's Q-F5) ------------------------------------------


def g1_tie_scene(reason) -> object:
    """A colonoscopy (E1 its examination, E2 the snare) and E6, a performed examination of today whose kind pass 1 left
    unappraised and whose session it filed X1 unresolved for ``reason``: row 7 holds X1's codes on E6, so the plan asks
    G1 ("E6 was not done during session X1.") where the tie is answerable."""
    doc = EF.colonoscopy()
    doc.event(6, kind=unres(Kind.EXAMINATION, R_.UNAPPRAISED), status=sup(Status.PERFORMED),
              session=unres(X(1), reason), date=sup(EF.ON), entry=sup(EF.DC))
    return doc.build()


def bundled_injection(part_of=F.SILENT, cause=F.SILENT, purpose=F.SILENT) -> object:
    """test_r3_probe's F11/F12 scene: an injection E3 beside the snare E2, its links as given."""
    doc = EF.colonoscopy()
    doc.act(3, Kind.INJECTION, purpose=purpose, part_of=part_of, cause=cause)
    return doc.build()


def scenes() -> dict:
    """Every scene of this module's planner tests (the property's population)."""
    found = {f'egd {place.value} {name}': T.egd_biopsy(place, session)
             for place in (*T.UNREACHABLE, *T.REACHABLE)
             for name, session in (('silent', F.SILENT), ('claimed', unres(X(1), R_.GEOMETRY_SECTION)))}
    found.update({
        'C6 anatomy_conflict': EF.colonoscopy(date=unres(EF.ON, R_.ANATOMY_CONFLICT)).build(),
        'C6 person_conflict': EF.colonoscopy(date=unres(EF.ON, R_.PERSON_CONFLICT)).build(),
        'G1 session_unreachable': g1_tie_scene(R_.SESSION_UNREACHABLE),
        'G1 geometry': g1_tie_scene(R_.GEOMETRY_SECTION),
        'F11 structure_part_of': bundled_injection(part_of=unres(E(2), R_.STRUCTURE_PART_OF)),
        'F11 F12 silent': bundled_injection(),
        'L2-1': T.l2_1_scene(), 'L6-1': T.l6_1_scene(), 'L2-2': T.lift_scene(),
    })
    return found


class NeverAskedTests(SimpleTestCase):
    def test_l1_02_a_silent_session_the_reach_refuses_is_never_asked(self) -> None:
        # F2's path (the fold lane's measured gap): "E2 was done during session X1." for a biopsy of a place the EGD
        # cannot reach - the merge asks it (and pays) while the fold refuses it
        for place in T.UNREACHABLE:
            with self.subTest(place=place.value):
                found = asking.plan(T.egd_biopsy(place, F.SILENT), ())
                self.assertEqual([item for item in q_fact(found) if item[2] == ('E2',)], [])
                self.assertIn(f'F2 ({FOLD_REFUSED})', found.blocked)
        for place in T.REACHABLE:  # the boundary: a place the session reaches is asked
            with self.subTest(place=place.value):
                self.assertIn(('F2', 'fact.session', ('E2',), 'X1', False),
                              q_fact(asking.plan(T.egd_biopsy(place, F.SILENT), ())))

    def test_g1_over_a_tie_a_fixed_table_check_demoted_is_never_asked(self) -> None:
        self.assertEqual([item for item in q_fact(asking.plan(g1_tie_scene(R_.SESSION_UNREACHABLE), ()))
                          if item[0] == 'G1'], [])
        self.assertIn(('G1', 'fact.session.not', ('E6',), 'X1', True),  # the boundary: a reading's tie is asked
                      q_fact(asking.plan(g1_tie_scene(R_.GEOMETRY_SECTION), ())))

    def test_c6_reads_the_folds_own_conflicts(self) -> None:
        self.assertIs(asking._CONFLICTS, F.CONFLICTS)
        self.assertNotIn(R_.ANATOMY_CONFLICT, asking._CONFLICTS)  # K4's: a fixed-table check (D324 (4))
        anatomy = asking.plan(EF.colonoscopy(date=unres(EF.ON, R_.ANATOMY_CONFLICT)).build(), ())
        self.assertEqual(q_fact(anatomy), [])
        person = asking.plan(EF.colonoscopy(date=unres(EF.ON, R_.PERSON_CONFLICT)).build(), ())
        self.assertIn(('C6', 'fact.date_relation', ('E2',), 'on_date_of_service', False), q_fact(person))

    def test_f11_over_a_part_link_a_fixed_table_check_demoted_is_never_asked(self) -> None:
        found = asking.plan(bundled_injection(part_of=unres(E(2), R_.STRUCTURE_PART_OF)), ())
        self.assertEqual([item for item in q_fact(found) if item[2] == ('E3',)], [])  # F12's too: not releasable
        silent = asking.plan(bundled_injection(), ())  # the boundary: the silent link's three questions
        self.assertEqual(sorted(item[1] for item in q_fact(silent) if item[2] == ('E3',)),
                         ['fact.cause.not', 'fact.hemostasis.not', 'fact.part_link.any'])

    def test_a_value_an_earlier_negation_ruled_out_is_never_planned(self) -> None:
        R = T.l2_1_scene()
        first = asking.plan(R, ())
        R_q = T.fold(R, T.not_in(E(6), X(1)))
        self.assertFalse(F.folds(R_q, E(6), A.SESSION, 'X1'))
        later = asking.plan(R_q, {spec.key for spec in first.specs})
        self.assertFalse([item for item in q_fact(later) if item[2] == ('E6',) and item[3] == 'X1' and not item[4]])

    def test_settles_re_check_reads_the_folds_predicate(self) -> None:
        asked = asking.plan(T.egd_biopsy(T.REACHABLE[0], F.SILENT), ())
        spec = next(spec for spec in asked.specs if spec.subjects == ('E2',) and spec.census == 'F2')
        for place in (*T.UNREACHABLE, *T.REACHABLE):
            R = T.egd_biopsy(place, F.SILENT)
            with self.subTest(place=place.value):
                self.assertEqual(asking.eligible(spec, R), place in T.REACHABLE)
                self.assertEqual(asking.eligible(spec, R), folds(R, spec))

    def test_every_planned_q_fact_question_folds(self) -> None:
        # the property over this module's scenes: what the plan asks, the fold would apply (and settle re-checks it so)
        checked = 0
        for name, R in scenes().items():
            for spec in asking.plan(R, ()).specs:
                if spec.family is asking.Family.Q_FACT:
                    with self.subTest(scene=name, spec=spec.key):
                        self.assertTrue(folds(R, spec))
                        self.assertTrue(asking.eligible(spec, R))
                    checked += 1
        self.assertGreater(checked, 10)  # not vacuous


# --- D324 (1) for the field readers of the cause and the claimed hemostasis (the fold lane's Q-F1, Q-F2, Q-F3) --------


CAUSE_NOT = T.negation(E(3), A.CAUSE, C.ACT_OF_THIS_SESSION, 'fact.cause.not')
PART_ANY = T.record(E(3), A.PART_OF, '', True, 'fact.part_link.any')
HEMOSTASIS_NOT = T.negation(E(3), A.PURPOSE, P.HEMOSTASIS, 'fact.hemostasis.not')
LIFT_NOT = T.negation(E(3), A.PURPOSE, P.LIFT_FOR_RESECTION, 'fact.lift.not')


def bundling_of(R, code: str) -> set:
    return {(witness.held.fact, str(witness.held.subject)) for candidate in whatif.witnesses(R, code)
            for witness in candidate.witnesses if witness.source == 'bundling'}


class CauseRuledOutTests(SimpleTestCase):
    def test_f11_and_f12_answered_release_the_adjunct_arms(self) -> None:
        R = bundled_injection()
        self.assertTrue({('act_cause', 'E3'), ('act_part', 'E3')} <= bundling_of(R, '45381'))
        # the separation answers both established: no bundling arm is left (the merge: the narrowed cause still read as
        # an empty slot, so the by-cause arm stayed open and F12's answer released nothing)
        self.assertEqual(bundling_of(T.fold(R, PART_ANY, CAUSE_NOT), '45381'), set())

    def test_cause_not_alone_rules_the_procedural_adjunct_out(self) -> None:
        R_q = T.fold(bundled_injection(), CAUSE_NOT)
        self.assertTrue(coverage._not_adjunct(R_q, E(3), E(2)))  # as an established "not act_of_this_session"
        self.assertNotIn(('act_cause', 'E3'), bundling_of(R_q, '45381'))
        self.assertIn(('act_part', 'E3'), bundling_of(R_q, '45381'))  # the lift's by-part arm: another value's reader

    def test_a_narrowed_slot_is_no_empty_slot_and_every_other_cause_reads_as_before(self) -> None:
        R = bundled_injection()
        base = F.fact(R, E(3), A.CAUSE)
        narrowed = F.fact(T.fold(R, CAUSE_NOT), E(3), A.CAUSE)
        self.assertTrue(coverage._pure_silent(base))
        self.assertFalse(coverage._pure_silent(narrowed))
        self.assertTrue(coverage._pure_silent(F.SILENT))
        for value in C:
            with self.subTest(cause=value.value):
                self.assertEqual(F.possibly(narrowed, value), value is not C.ACT_OF_THIS_SESSION)

    def test_the_boundaries_no_answer_and_the_premises_negation(self) -> None:
        R = bundled_injection()
        self.assertFalse(coverage._not_adjunct(R, E(3), E(2)))
        # the premise's own negation releases the by-cause arm as before (its reader is facts.possibly)
        self.assertNotIn(('act_cause', 'E3'), bundling_of(T.fold(R, HEMOSTASIS_NOT), '45381'))
        # a cause established at another value, or negated by pass 1, rules the adjunct out as before
        self.assertTrue(coverage._not_adjunct(bundled_injection(cause=sup(C.PRE_EXISTING_LESION)), E(3), E(2)))
        self.assertTrue(coverage._not_adjunct(bundled_injection(cause=neg(C.ACT_OF_THIS_SESSION)), E(3), E(2)))


class HemostasisRuledOutTests(SimpleTestCase):
    def test_hemostasis_not_over_a_claimed_hemostasis_releases_the_injections_kind_row(self) -> None:
        R = T.lift_scene(purpose=unres(P.HEMOSTASIS, R_.GEOMETRY_SECTION))
        self.assertTrue(evaluate._claims_hemostasis(F.fact(R, E(3), A.PURPOSE)))
        self.assertIsNot(T.codes(R, ('45381', 3))['45381'][0], Outcome.READY)
        R_q = T.fold(R, HEMOSTASIS_NOT)
        self.assertFalse(evaluate._claims_hemostasis(F.fact(R_q, E(3), A.PURPOSE)))
        found = T.codes(R_q, ('45381', 3))['45381']
        self.assertEqual(found[:2], (Outcome.READY, frozenset()))  # the merge: held on the claimed purpose

    def test_only_its_value_lift_not_keeps_the_claim(self) -> None:
        R = T.lift_scene(purpose=unres(P.HEMOSTASIS, R_.GEOMETRY_SECTION))
        self.assertTrue(evaluate._claims_hemostasis(F.fact(T.fold(R, LIFT_NOT), E(3), A.PURPOSE)))
        doubt = T.lift_scene()  # doubted(lift, hemostasis)
        narrowed = F.fact(T.fold(doubt, HEMOSTASIS_NOT), E(3), A.PURPOSE)
        self.assertFalse(evaluate._claims_hemostasis(narrowed))
        self.assertTrue(F.possibly(narrowed, P.LIFT_FOR_RESECTION))


# --- D324 (8) in the rules lane's files (the ask lane's Q1 (a) and (b)) -------------------------------------------------


def reference_not_on_sets_apart(R, statement: Id, act: Id) -> bool:
    """The lanes' pairing.not_on_sets_apart (int4's): the assumed FactSet read with reads of its own."""
    p = pairing._context(R, statement, act)
    mode = pairing._mode(R, p)
    if mode not in (pairing._Mode.SINGLE, pairing._Mode.LISTED) or not pairing.has_target(R, act):
        return False
    if not F.silent(F.fact(R, act, A.TARGET_LESION)):
        return False
    own = pairing._target(R, statement, mode)
    if own.lesions is None or not own.lesions:
        return False
    assumed = replace(R, off_lesion=R.off_lesion | frozenset((act, lesion) for lesion in own.lesions))
    return pairing._target_row(assumed, pairing._context(assumed, statement, act)) is pairing.RowResult.INDEPENDENT


def onlesion_scenes() -> dict:
    found = {'bound 4x3': TRCA.bound_scene(4, 3), 'bound 6x5': TRCA.bound_scene(6, 5)}
    for structure in (ct.Structure.ULCER, ct.Structure.WALL, ct.Structure.LESION):
        found[f'qb {structure.value}'] = TRR.ulcer_scene(sup(structure))
        found[f'qb listed {structure.value}'] = TRR.ulcer_scene(sup(structure), listed=True)
    return found


class PlanReadsOnceTests(SimpleTestCase):
    def test_the_onlesion_what_if_equals_the_lanes_reading(self) -> None:
        compared = 0
        for name, R in onlesion_scenes().items():
            for statement in R.events:
                for act in R.events:
                    if statement == act:
                        continue
                    with self.subTest(scene=name, statement=str(statement), act=str(act)):
                        want = reference_not_on_sets_apart(R, statement, act)
                        self.assertEqual(pairing.not_on_sets_apart(R, statement, act), want)
                        compared += want
        self.assertGreater(compared, 0)  # not vacuous: some pair is set apart by the assumption

    def test_the_onlesion_what_if_reads_each_acts_lesions_once_per_factset(self) -> None:
        # the ask lane's measured cost (107 s of the bound plan): every assumption re-read every listed lesion's finding
        # to build its own index of the places the findings name (pairing._named) - now it is R's, built once
        R = TRCA.bound_scene(6, 5)
        builds: Counter = Counter()
        real = pairing._named
        held = []  # every FactSet counted kept alive: no id reused during the count

        def counted(R_, reads):
            held.append(R_)
            if reads.named is None:
                builds[id(R_)] += 1
            return real(R_, reads)
        asked = 0
        with mock.patch.object(pairing, '_named', counted):
            for statement in R.events:
                for act in R.events:
                    if statement != act and pairing.not_on_sets_apart(R, statement, act):
                        asked += 1
        self.assertTrue(asked)  # not vacuous: the assumption sets pairs apart
        self.assertEqual(sum(builds.values()), 1, builds)  # R's own index; the merge: one per assumption

    def test_row_8_reads_the_callers_reader(self) -> None:
        R = TRCA.bound_scene(6, 5)
        callers: Counter = Counter()
        real = pairing.pairs_of

        def recording(R_, act):
            import sys
            callers[sys._getframe(1).f_globals.get('__name__')] += 1
            return real(R_, act)
        with mock.patch.object(pairing, 'pairs_of', recording):
            found = asking.plan(R, ())
        self.assertTrue(found.specs)
        self.assertNotIn(evaluate.__name__, callers)  # the merge: evaluate._row_clean once per candidate code
        self.assertIn(coverage.__name__, callers)

    def test_support_through_a_reader_equals_support_without(self) -> None:
        for name, R in {**onlesion_scenes(), 'L2-1': T.l2_1_scene(), 'L2-2': T.lift_scene()}.items():
            reader = coverage.Reader(R)
            for code in whatif.candidate_codes(R):
                for candidate in whatif.witnesses(R, code, reader):
                    with self.subTest(scene=name, code=code, event=str(candidate.event)):
                        self.assertEqual(evaluate.support(code, candidate.group, R, candidate.event, reader),
                                         evaluate.support(code, candidate.group, R, candidate.event))
            other = coverage.Reader(T.lift_scene())  # another FactSet's reader is never read
            code = next(iter(whatif.candidate_codes(R)))
            for candidate in tuple(whatif.witnesses(R, code, reader))[:1]:
                self.assertEqual(evaluate.support(code, candidate.group, R, candidate.event, other),
                                 evaluate.support(code, candidate.group, R, candidate.event))


# --- P-INDEP for D324 (5) (the rules lane's Q1) -------------------------------------------------------------------------


class OrganClosureTests(SimpleTestCase):
    def test_the_route_codes_closure_holds_every_entrys_organ(self) -> None:
        codes = [str(code) for code in TRR.evaluate.STOMA_ROUTE_CODES | TRR.evaluate.ANUS_ROUTE_CODES
                 if Tag.COLFULL in rq.spec(str(code)).tags]
        self.assertGreater(len(codes), 20)
        for code in codes:
            with self.subTest(code=code):
                self.assertIn(A.ORGAN, rq.dependencies(code).reads[rq.Role.ANATOMY])

    def test_an_organ_moves_only_a_code_whose_closure_holds_it(self) -> None:
        # the rules lane's gastrostomy beside a colonoscopy (R2E-STOMA-ORGAN): its organ decides 45385's route row
        stomach, colon = TRR.peg_note(sup(Landmark.STOMACH)), TRR.peg_note(sup(Landmark.SIGMOID_COLON))
        self.assertNotEqual(TRR.held_of(stomach, '45385'), TRR.held_of(colon, '45385'))
        self.assertIn(A.ORGAN, rq.dependencies('45385').reads[rq.Role.ANATOMY])
