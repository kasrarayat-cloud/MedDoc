"""Round r3, round 4's lane "pairs" (DECISIONS D328 (2), finding R3D-L1-1, high) - the lane's own tests. SYNTHETIC
FactSets (tests/v2 fixtures: invented ids, kinds and places); nothing is sent anywhere.

D328 (2) - A STATEMENT-ACT PAIR'S RELATION IS ONE PROPOSITION ACROSS FAMILIES (D325 (1)'s truth table extended over
families). A release of the pair through one family stands only when every question asked of the SAME pair, in any
family (Q-REL, Q-ONLESION, and Q-LESION if ever built), request or round, got the release direction on both its claim
and its control in an answered, healthy request; anything else holds the pair (question_conflict). The planner asks a
pair through another family only when no earlier answer about the pair holds it. The census extends over the pair
families. Built in contract/settle.exclusive (``pair_scopes``, ``_pair_held``, ``PairAnswers``) and engine/asking.plan
(``_Context.unheld``, PAIR_HELD):
- CrossFamilyPairClassRule: the finding's own input (the third adversarial pass's L1 lens, test_l1r3d_attack, ported):
  round 1's Q-REL "This statement does not deny act E4." answered holding, unclear or incoherent, round 2's Q-ONLESION
  "This act was not done to lesion L1." in the release direction - 45381 READY on int6 (RED there), held now;
- FindingBoundaryTests: the attacker's boundaries - every act-lesion reason the fact pass leaves askable, the
  Q-ONLESION's own holding answer, a judged pair, no answer, and the consistent release;
- PlannerHalfTests: the planner's half alone - no second family after an earlier answer that holds the pair (holding,
  unclear, incoherent, missing, a refused or a failed request), the census reason it is blocked with, an earlier
  answer in the release direction whose proof did not locate (it does not hold), the reverse direction (an earlier
  Q-ONLESION holds the Q-REL), and a different pair's answer, which holds nothing of this one;
- StageVariantTests: the class end to end through the stage beyond the finding's input - the SAME round's two requests
  (two denials of L1, one pair asked through Q-REL and the other through Q-ONLESION, whose not-on releases both: 45381
  READY on int6), each kind of non-release answer, another act's pair (must stay independent), another statement of
  the act naming no lesion (fail-closed at the stage's call, independent when exclusivity reads the FactSet), two Q-REL
  pairs of one act (each its own, as before);
- ExclusiveTests: the rule at the records - both orders, two requests of one round, every blocker, a plan-time refusal,
  a kept unlisted entry's pair, two lesions of one listed statement, the Q-LESION scopes, idempotence and order;
- PairCensusTests: THE CENSUS over the pair families - every set of asked propositions of a pair (Q-REL and one
  Q-ONLESION; Q-REL and the two Q-ONLESIONs of a listed statement; Q-REL and a Q-LESION), every claim and control
  verdict pair from supported, contradicted, unclear and missing, a refused request and a plan-time refusal, beside an
  unrelated pair: a record stays established exactly when every proposition about its pair reads the release direction;
  at the fold, the pair is released exactly then; and no single verdict change from matching to not matching grows
  either (P-MONO-Q).
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Outcome
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_properties as TP

A = ct.Attribute
V = ct.VerdictValue
FAM = asking.Family
Kind, Landmark = ct.Kind, ct.Landmark
sup, X, E, L = EF.sup, EF.X, EF.E, EF.L
RELEASE, HOLD, UNCLEAR, INCOHERENT = ((V.SUPPORTS, V.CONTRADICTS), (V.CONTRADICTS, V.SUPPORTS),
                                      (V.UNCLEAR, V.UNCLEAR), (V.CONTRADICTS, V.CONTRADICTS))
MISSING = (None, None)
BOTH_SUPPORTED = (V.SUPPORTS, V.SUPPORTS)
NOT_RELEASE = {'holding': HOLD, 'unclear': UNCLEAR, 'incoherent': INCOHERENT, 'missing': MISSING,
               'both supported': BOTH_SUPPORTED}
CODES = (('45381', 4), ('45385', 2), ('45378', 1), ('45380', 7))
CONFLICT = 'question_conflict'


def _verdict(value):
    return SimpleNamespace(verdict=SimpleNamespace(verdict=value, qualifiers=(), attached=ct.Attached.YES),
                           quotes_bound=False, quotes=())


# --- the scenes (the finding's, and its class beyond it) ----------------------------------------------------------------


def base_doc(e4_performer=None):
    """R3D-L1-1's scene: a colonoscopy X1 (E1), the cold snare E2 of L1 (single) in the sigmoid colon, E3 an ESTABLISHED
    denial that an injection was given for L1 (single target L1, placed at L1's place), E4 a tattoo in the sigmoid colon
    whose target names no lesion, its performer DOUBTED (documenting team | another clinician) unless given."""
    doc = EF.colonoscopy()
    doc.lesions[L(1)] = {**doc.lesions[L(1)], A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
    doc.act(3, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(4, Kind.TATTOO, places=[sup(Landmark.SIGMOID_COLON)],
            performer=e4_performer if e4_performer is not None else EF.doubted(EF.TEAM, ct.Performer.OTHER_CLINICIAN))
    return doc


DOUBTED = object()


def second_denial(doc, lesion=True, performer=DOUBTED):
    """E5: a second established denial of an injection, of L1 (``lesion``) or naming no lesion, placed at L1's place,
    its own performer doubted (the default: so its pair with the tattoo E4 is UNRESOLVED while E3's is a CONTRADICTION)
    or as given (None: not filed)."""
    doc.act(5, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            places=[sup(Landmark.SIGMOID_COLON)],
            performer=EF.doubted(EF.TEAM, ct.Performer.OTHER_CLINICIAN) if performer is DOUBTED else performer,
            **({'lesion': sup(L(1))} if lesion else {}))


def other_pair(doc, performer=None, lesion=2):
    """Another pair, of another act: E6 an established denial that a biopsy was taken of L2 (or ``lesion``; single,
    descending colon), E7 a biopsy in the descending colon naming no lesion, its performer doubted unless given."""
    doc.lesion(lesion, lesion_places=[sup(Landmark.DESCENDING_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(6, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            lesion=sup(L(lesion)), places=[sup(Landmark.DESCENDING_COLON)])
    doc.act(7, Kind.BIOPSY, places=[sup(Landmark.DESCENDING_COLON)],
            performer=performer if performer is not None else EF.doubted(EF.TEAM, ct.Performer.OTHER_CLINICIAN))


def finish(doc, asked=((4, 1),), reason='appraisal_missing'):
    """The FactSet (every claims-rule pair control rejected, the date of service set) with the fact pass's D305
    act-lesion claims of ``asked`` (act, lesion) left without a usable verdict (``reason``), so the stage may ask them,
    and the row's events."""
    R = TP.paired(doc.build())
    R = TA.dated(replace(R, pair_controls={**R.pair_controls,
                                           **{(E(act), A.DISTINCT_FROM, L(lesion)): False for act, lesion in asked}}))
    events = {'act_lesions': [{'act': f'E{act}', 'lesion': f'L{lesion}', 'reasons': [reason]} for act, lesion in asked]}
    return R, events


def scene(act_lesion_reason='appraisal_missing', performer=None):
    return finish(base_doc(performer), reason=act_lesion_reason)


# --- the stage, DB-free -------------------------------------------------------------------------------------------------


def stage(R, events, answer, *, bound=asking.QUESTION_BOUND, health=None, with_R=False, located=None,
          max_rounds=6):
    """The question stage over ``R`` (R_base) as studio/jobs._question_state_child runs it, DB-free: round by round the
    REAL planner over R_q of every answer so far (the row's events beside it), the partition (``bound`` claims a
    request) with its one calibration item, settle_questions against R_base (every supported claim's proof located),
    then exclusivity over every round's records - called as jobs.py calls it (``exclusive(records, refused)``), or
    reading R_base (``with_R``: this lane's question Q1). ``answer(spec)`` -> (claim, control), each a VerdictValue or
    None (no verdict); ``health(round_, questions)`` -> 'answered' (default), 'breach' (the request's calibration item
    answered wrong: H2 refuses it) or 'failed' (no answer); ``located(spec)`` whether the claim's proof locates
    (default: always)."""
    controlled = frozenset((event, attribute) for event in R.events for attribute in asking._K1_ATTRIBUTES
                           if F.fact(R, event, attribute).result is ct.Result.SUPPORTED) | R.controlled
    pool = asking.calibration_pool(replace(R, controlled=controlled))
    records, asked, plans = [], set(), []
    for round_ in range(1, max_rounds + 1):
        current = {**events, 'questions': list(records)}
        plan = asking.plan(F._answered(R, current), asked, current)
        plans.append(plan)
        if not plan.specs:
            return records, plans
        for batch, request_plan in enumerate(asking.partition(plan.specs, pool, round_, bound), start=1):
            outcome = health(round_, request_plan.questions) if health is not None else 'answered'
            items, verdicts, locations = [], {}, {}
            for number, spec in enumerate(request_plan.questions, start=1):
                claim, control = f'q{number}', f'q{number}n'
                items.append(SimpleNamespace(role='question', spec=spec, claim=claim, control=control,
                                             controls=(control,)))
                for key, value in zip((claim, control), answer(spec)):
                    if value is not None:
                        verdicts[key] = _verdict(value)
                where = located is None or located(spec)
                locations[claim] = SimpleNamespace(located=where, spans=((100 * number, 100 * number + 20),) if where
                                                   else (), reason='' if where else 'proof_unlocated')
            for number, item in enumerate(request_plan.calibration, start=1):
                items.append(SimpleNamespace(role='calibration', spec=item, claim=f'c{number}', control=f'c{number}n',
                                             controls=(f'c{number}n',)))
                right = outcome != 'breach'
                verdicts[f'c{number}'] = _verdict(V.CONTRADICTS if right else V.SUPPORTS)
                verdicts[f'c{number}n'] = _verdict(V.SUPPORTS if right else V.CONTRADICTS)
            read = SimpleNamespace(verdicts=verdicts, missing=(), repeated=()) if outcome != 'failed' else None
            found = settle.settle_questions(SimpleNamespace(items=tuple(items), round=round_, batch=batch), read,
                                            locations if read is not None else {}, R,
                                            'answered' if outcome != 'failed' else 'failed')
            records.extend(found.questions)
        asked |= {spec.key for spec in plan.specs}
        records = settle.exclusive(records, [], R) if with_R else settle.exclusive(records, [])
    raise AssertionError('round bound')


def answers(rel=RELEASE, onlesion=RELEASE, **by_pair):
    """Q-REL answered ``rel`` - a question whose subjects ``by_pair`` names joined by '_' (``E5_E4=HOLD``) as given
    there -; the Q-ONLESION ``onlesion``; every other question (a performer) in the release direction."""
    def answer(spec):
        named = by_pair.get('_'.join(spec.subjects))
        if named is not None:
            return named
        if spec.family is FAM.Q_REL:
            return rel
        if spec.family is FAM.Q_ONLESION:
            return onlesion
        return RELEASE
    return answer


def walk(R, events, answer, **kwargs):
    """The stage, the fold and assess: (45381's status and held facts by code, the records, the plans, R_q)."""
    records, plans = stage(R, events, answer, **kwargs)
    R_q = F._answered(R, {**events, 'questions': records})
    found = {item.code: (item.status.value, sorted({(h.fact, h.cause, str(h.subject)) for h in item.held_facts}))
             for item in TP.assessed(R_q, CODES).codes}
    return found, records, plans, R_q


def relation(R, statement, act):
    return pairing.relation(R, E(statement), E(act)).relation.value


def outcome(rel, onlesion=RELEASE, **kwargs):
    R, events = scene(**kwargs)
    found, records, plans, R_q = walk(R, events, answers(rel, onlesion))
    return found['45381'][0], records, plans, relation(R_q, 3, 4)


def families(plans):
    return [[spec.family.value for spec in plan.specs] for plan in plans]


def record(records, family, subjects):
    (found,) = [item for item in records if item['family'] == family and item['subjects'] == list(subjects)]
    return found


# --- the finding ----------------------------------------------------------------------------------------------------------


class CrossFamilyPairClassRule(SimpleTestCase):
    """R3D-L1-1's expected behaviour (RED on int6): the pair's two families read as one proposition - a release of the
    pair through Q-ONLESION is held while the SAME pair's Q-REL answer, in an earlier round, is not the release."""

    def test_a_holding_rel_answer_holds_the_pair_released_by_onlesion(self) -> None:
        for name, rel in (('holding', HOLD), ('unclear', UNCLEAR), ('incoherent', INCOHERENT)):
            with self.subTest(rel=name):
                self.assertNotEqual(outcome(rel)[0], 'ready')

    def test_the_consistent_release_still_releases(self) -> None:
        self.assertEqual(outcome(RELEASE)[0], 'ready')  # round 1's release: no second family asked


class FindingBoundaryTests(SimpleTestCase):
    """The attacker's boundaries, now: every act-lesion reason the fact pass leaves askable holds the pair (on int6 each
    was READY), with the existing hold (relation:contradiction) and the pair held; the Q-ONLESION's own holding answer
    holds; a pair the fact pass judged is never re-asked and holds; without any answer 45381 is held; and the
    consistent release asks no second family."""

    def test_the_reasons_the_fact_pass_leaves_askable(self) -> None:
        for reason in ('appraisal_missing', 'appraisal_detached', 'unappraised'):
            for name, rel in (('holding', HOLD), ('unclear', UNCLEAR), ('incoherent', INCOHERENT)):
                with self.subTest(reason=reason, rel=name):
                    status, records, plans, pair = outcome(rel, act_lesion_reason=reason)
                    self.assertEqual((status, pair), ('needs_clarification', 'contradiction'))
                    self.assertEqual(families(plans), [['Q-REL', 'Q-FACT'], []])

    def test_the_hold_is_an_existing_reason(self) -> None:
        R, events = scene()
        found, _records, _plans, _R_q = walk(R, events, answers(HOLD))
        self.assertEqual(found['45381'], ('needs_clarification', [('conflict:tattoo', 'relation:contradiction', 'E4')]))

    def test_boundaries(self) -> None:
        self.assertEqual(outcome(HOLD, onlesion=HOLD)[0], 'needs_clarification')
        self.assertEqual(outcome(HOLD, act_lesion_reason='appraisal_unclear')[0], 'needs_clarification')
        R, events = scene()
        self.assertEqual({item.code: item.status.value for item in TP.assessed(R, CODES).codes}['45381'],
                         'needs_clarification')
        status, records, plans, pair = outcome(RELEASE)
        self.assertEqual((status, pair, families(plans)), ('ready', 'independent', [['Q-REL', 'Q-FACT'], []]))
        self.assertEqual(record(records, 'Q-REL', ('E3', 'E4'))['result'], 'supported')


# --- the planner's half ----------------------------------------------------------------------------------------------------


def breach_rel(round_, questions):
    return 'breach' if any(spec.family is FAM.Q_REL for spec in questions) else 'answered'


def fail_rel(round_, questions):
    return 'failed' if any(spec.family is FAM.Q_REL for spec in questions) else 'answered'


class PlannerHalfTests(SimpleTestCase):
    """engine/asking.plan's half of D328 (2): once an earlier answer about a pair holds it, no question of another
    family is asked of the pair - the witness is blocked with PAIR_HELD and its held fact stays held - and an earlier
    answer in the release direction on both members (its proof unlocated) holds nothing."""

    def test_after_each_answer_that_holds_the_pair_no_second_family_is_asked(self) -> None:
        R, events = scene()
        cases = [(name, dict(answer=answers(pattern))) for name, pattern in NOT_RELEASE.items()]
        cases += [('refused request', dict(answer=answers(RELEASE), bound=4, health=breach_rel)),
                  ('failed request', dict(answer=answers(RELEASE), bound=4, health=fail_rel))]
        for name, kwargs in cases:
            with self.subTest(case=name):
                answer = kwargs.pop('answer')
                found, records, plans, R_q = walk(R, events, answer, **kwargs)
                self.assertEqual(families(plans), [['Q-REL', 'Q-FACT'], []])
                self.assertEqual(plans[1].blocked.get(asking.PAIR_HELD), 2)  # each of 45381's candidates reading the pair
                self.assertEqual(record(records, 'Q-FACT', ('E4',))['result'], 'supported')  # the performer
                self.assertNotEqual(record(records, 'Q-REL', ('E3', 'E4'))['result'], 'supported')
                self.assertEqual((found['45381'][0], relation(R_q, 3, 4)), ('needs_clarification', 'contradiction'))

    def test_the_census_reason_is_the_planners_own(self) -> None:
        R, events = scene()
        _found, records, plans, _R_q = walk(R, events, answers(HOLD))
        current = {**events, 'questions': records}
        asked = {spec.key for plan in plans for spec in plan.specs}
        plan = asking.plan(F._answered(R, current), asked, current)
        self.assertEqual(plan.specs, ())
        self.assertEqual(plan.blocked.get(asking.PAIR_HELD), 2)
        # without the records (events naming no question) the same FactSet asks the pair through Q-ONLESION
        unasked = asking.plan(F._answered(R, current), (), events)
        self.assertIn(('Q-ONLESION', ('E4', 'L1')), {(spec.family.value, spec.subjects) for spec in unasked.specs})

    def test_an_answer_in_the_release_direction_holds_nothing(self) -> None:
        """Round 1's Q-REL in the release direction on BOTH members but its proof unlocated (unresolved, never folded):
        it does not hold the pair, so round 2 asks the Q-ONLESION, and its release stands beside it."""
        R, events = scene()
        found, records, plans, R_q = walk(R, events, answers(RELEASE), located=lambda spec: spec.family is not FAM.Q_REL)
        self.assertEqual(families(plans), [['Q-REL', 'Q-FACT'], ['Q-ONLESION'], []])
        self.assertEqual(record(records, 'Q-REL', ('E3', 'E4'))['reasons'], ['proof_unlocated'])
        self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['result'], 'supported')
        self.assertEqual((found['45381'], relation(R_q, 3, 4)), (('ready', []), 'independent'))

    def test_the_reverse_direction(self) -> None:
        """An earlier Q-ONLESION answer about the pair that is not the release holds a later Q-REL of the same pair:
        the round-1 plan of the finding's scene asks the pair's Q-REL (UNRESOLVED on the doubted performer); beside an
        earlier holding, unclear or missing "This act was not done to lesion L1." it is not asked."""
        R, events = scene()
        spec = asking.QuestionSpec(FAM.Q_ONLESION, 'onlesion', ('E4', 'L1'), A.TARGET_LESION, 'L1', True,
                                   ('E4', 'L1'), census='R3/R4')
        self.assertEqual([s.key for s in asking.plan(R, (), events).specs],
                         ['Q-REL|rel.deny|E3,E4|||', 'Q-FACT|fact.performer|E4|performer|documenting_team|'])
        for name, pattern in (('holding', HOLD), ('unclear', UNCLEAR), ('missing', MISSING), ('release', RELEASE)):
            with self.subTest(onlesion=name):
                earlier = settled(R, [(spec, pattern)])
                current = {**events, 'questions': earlier}
                plan = asking.plan(F._answered(R, current), {spec.key}, current)
                if name == 'release':  # the not-on established: the pair is set apart, nothing left to ask of it
                    self.assertNotIn('Q-REL|rel.deny|E3,E4|||', [s.key for s in plan.specs])
                    self.assertNotIn(asking.PAIR_HELD, plan.blocked)
                    continue
                self.assertEqual(plan.specs, ())
                self.assertEqual(plan.blocked.get(asking.PAIR_HELD), 2)

    def test_the_planner_reads_the_pairs_on_its_factset(self) -> None:
        """The planner reads a Q-ONLESION's pairs on the plan's FactSet: E5 denies an injection naming NO lesion, so an
        earlier holding answer about (E5, E4) is about no pair "E4 was not done to L1" is asked of - the not-on is
        still asked for E3's pair (as on int6) - while beside an earlier holding answer about (E3, E4) itself it is
        not."""
        doc = base_doc(e4_performer=sup(EF.TEAM))
        second_denial(doc, lesion=False)
        R, events = finish(doc)
        onlesion = 'Q-ONLESION|onlesion|E4,L1|target.lesion|L1|not'
        self.assertIn(onlesion, [spec.key for spec in asking.plan(R, (), events).specs])
        for statement, asked_again in (('E5', True), ('E3', False)):
            with self.subTest(earlier=statement):
                spec = rel_spec(statement, 'E4')
                current = {**events, 'questions': settled(R, [(spec, HOLD)])}
                plan = asking.plan(F._answered(R, current), {spec.key}, current)
                self.assertEqual(onlesion in [found.key for found in plan.specs], asked_again)
                self.assertEqual(asking.PAIR_HELD in plan.blocked, not asked_again)

    def test_another_pairs_answer_holds_nothing_of_this_one(self) -> None:
        """An earlier holding Q-REL about ANOTHER pair (E6, E7: another statement, another act) does not stop the
        finding's pair (E3, E4) from being asked; the other pair's own Q-ONLESION is held."""
        doc = base_doc()
        other_pair(doc, performer=sup(EF.TEAM))
        R, events = finish(doc, asked=((4, 1), (7, 2)))
        spec = asking.QuestionSpec(FAM.Q_REL, 'rel.deny', ('E6', 'E7'), None, '', False, ('E6', 'E7'), census='R1')
        earlier = settled(R, [(spec, HOLD)])
        current = {**events, 'questions': earlier}
        plan = asking.plan(F._answered(R, current), {spec.key}, current)
        keys = [s.key for s in plan.specs]
        self.assertIn('Q-REL|rel.deny|E3,E4|||', keys)
        self.assertNotIn('Q-ONLESION|onlesion|E7,L2|target.lesion|L2|not', keys)
        self.assertGreater(plan.blocked.get(asking.PAIR_HELD, 0), 0)


# --- records, built by settle_questions -------------------------------------------------------------------------------------


def settled(R, asked, *, health='answered', round_=1, batch=1):
    """The records settle_questions writes for ONE request asking ``asked`` [(spec, (claim, control))] beside one
    calibration item answered right (``health`` 'breach': wrong; 'failed': no answer), every supported claim's proof
    located."""
    controlled = frozenset((event, attribute) for event in R.events for attribute in asking._K1_ATTRIBUTES
                           if F.fact(R, event, attribute).result is ct.Result.SUPPORTED) | R.controlled
    pool = asking.calibration_pool(replace(R, controlled=controlled))
    items, verdicts, locations = [], {}, {}
    for number, (spec, pattern) in enumerate(asked, start=1):
        claim, control = f'q{number}', f'q{number}n'
        items.append(SimpleNamespace(role='question', spec=spec, claim=claim, control=control, controls=(control,)))
        for key, value in zip((claim, control), pattern):
            if value is not None:
                verdicts[key] = _verdict(value)
        locations[claim] = SimpleNamespace(located=True, spans=((100 * number, 100 * number + 20),), reason='')
    items.append(SimpleNamespace(role='calibration', spec=pool[0], claim='c1', control='c1n', controls=('c1n',)))
    right = health != 'breach'
    verdicts['c1'] = _verdict(V.CONTRADICTS if right else V.SUPPORTS)
    verdicts['c1n'] = _verdict(V.SUPPORTS if right else V.CONTRADICTS)
    read = SimpleNamespace(verdicts=verdicts, missing=(), repeated=()) if health != 'failed' else None
    found = settle.settle_questions(SimpleNamespace(items=tuple(items), round=round_, batch=batch), read,
                                    locations if read is not None else {}, R,
                                    'answered' if health != 'failed' else 'failed')
    return [dict(item) for item in found.questions]


def refusal(spec, round_=1):
    """A plan-time refusal of ``spec`` as studio/jobs._refused_questions records it (never sent: no record)."""
    return {'round': round_, 'key': spec.key, 'family': spec.family.value, 'form': spec.form,
            'subjects': list(spec.subjects), 'attribute': spec.attribute.value if spec.attribute is not None else None,
            'value': spec.value, 'negated': spec.negated, 'census': spec.census, 'reason': asking.UNCALIBRATED}


def rel_spec(statement, act, form='rel.deny'):
    return asking.QuestionSpec(FAM.Q_REL, form, (statement, act), None, '', False, (statement, act), census='R1')


def onlesion_spec(act, lesion):
    return asking.QuestionSpec(FAM.Q_ONLESION, 'onlesion', (act, lesion), A.TARGET_LESION, lesion, True,
                               (act, lesion), census='R3/R4')


def lesion_spec(lesion, other):
    return asking.QuestionSpec(FAM.Q_LESION, 'lesion.distinct_from', (lesion, other), A.DISTINCT_FROM, other, False,
                               (lesion, other), census='P1-LESION')


def results(records):
    return {(item['family'], tuple(item['subjects'])): (item['result'], item['reasons']) for item in records}


# --- the stage, end to end ---------------------------------------------------------------------------------------------------


class StageVariantTests(SimpleTestCase):
    """The class end to end through the stage (the REAL planner, settle_questions, exclusivity, the fold, assess)."""

    def same_round(self, rel, *, lesion=True, bound=4, **kwargs):
        doc = base_doc(e4_performer=sup(EF.TEAM))
        second_denial(doc, lesion=lesion)
        R, events = finish(doc)
        return walk(R, events, answers(rel, **kwargs), bound=bound)

    def test_one_round_two_requests_two_denials_of_l1(self) -> None:
        """E3 and E5 both deny an injection for L1: (E3, E4) a CONTRADICTION is asked through Q-ONLESION, (E5, E4)
        UNRESOLVED through Q-REL, in ONE round - each in its own request (bound 4), or in one. The not-on "E4 was not
        done to L1" would release BOTH pairs (pairing's arm reads it for every statement naming L1), so E5's Q-REL
        answered other than the release holds it (on int6: 45381 READY, Fable having said E5 denies the tattoo)."""
        for bound in (4, asking.QUESTION_BOUND):
            for name, pattern in NOT_RELEASE.items():
                with self.subTest(bound=bound, rel=name):
                    found, records, plans, R_q = self.same_round(pattern, bound=bound)
                    self.assertEqual(families(plans)[0], ['Q-ONLESION', 'Q-REL'])
                    self.assertEqual(len({item['batch'] for item in records}), 2 if bound == 4 else 1)
                    self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['reasons'], [CONFLICT])
                    self.assertEqual(found['45381'][0], 'needs_clarification')
                    self.assertEqual((relation(R_q, 3, 4), relation(R_q, 5, 4)), ('contradiction', 'unresolved'))
            with self.subTest(bound=bound, rel='release'):
                found, records, _plans, R_q = self.same_round(RELEASE, bound=bound)
                self.assertEqual(found['45381'], ('ready', []))
                self.assertEqual((relation(R_q, 3, 4), relation(R_q, 5, 4)), ('independent', 'independent'))

    def test_one_round_the_pairs_rel_beside_another_pairs_not_on(self) -> None:
        """The pair's own Q-REL beside ANOTHER pair's Q-ONLESION about the same not-on, in one round: E4's performer
        doubted, so (E3, E4) is UNRESOLVED and asked through Q-REL, while E5 (a denial of L1 naming no performer) is a
        CONTRADICTION and asked through "E4 was not done to L1" - which would set E3's pair apart too (E3 names L1).
        E3's Q-REL answered other than the release holds that not-on (on int6 it released both pairs: 45381 READY)."""
        for name, pattern in NOT_RELEASE.items():
            with self.subTest(rel=name):
                doc = base_doc()
                second_denial(doc, performer=None)
                R, events = finish(doc)
                found, records, plans, R_q = walk(R, events, answers(pattern))
                self.assertEqual(families(plans)[0], ['Q-REL', 'Q-FACT', 'Q-ONLESION'])
                self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['reasons'], [CONFLICT])
                self.assertEqual(found['45381'][0], 'needs_clarification')
                self.assertNotEqual(relation(R_q, 3, 4), 'independent')
        doc = base_doc()
        second_denial(doc, performer=None)
        R, events = finish(doc)
        found, _records, _plans, R_q = walk(R, events, answers(RELEASE))
        self.assertEqual((found['45381'], relation(R_q, 3, 4), relation(R_q, 5, 4)),
                         (('ready', []), 'independent', 'independent'))

    def test_one_round_a_refused_or_failed_request(self) -> None:
        for name, health in (('refused', breach_rel), ('failed', fail_rel)):
            with self.subTest(request=name):
                doc = base_doc(e4_performer=sup(EF.TEAM))
                second_denial(doc)
                R, events = finish(doc)
                found, records, _plans, R_q = walk(R, events, answers(RELEASE), bound=4, health=health)
                self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['reasons'], [CONFLICT])
                self.assertEqual(found['45381'][0], 'needs_clarification')

    def test_the_finding_with_exclusivity_reading_the_factset(self) -> None:
        """The finding's input and the one-round variant with exclusivity reading R_base (this lane's question Q1): the
        same holds."""
        for name, pattern in NOT_RELEASE.items():
            with self.subTest(rel=name):
                R, events = scene()
                found, _records, _plans, _R_q = walk(R, events, answers(pattern), with_R=True)
                self.assertEqual(found['45381'][0], 'needs_clarification')
                doc = base_doc(e4_performer=sup(EF.TEAM))
                second_denial(doc)
                R, events = finish(doc)
                found, records, _plans, _R_q = walk(R, events, answers(pattern), bound=4, with_R=True)
                self.assertEqual(found['45381'][0], 'needs_clarification')

    def test_another_acts_pair_stays_independent(self) -> None:
        """A different pair that must stay independent: (E6, E7), another statement and another act, answered other
        than the release, holds nothing of (E3, E4) - released by its own Q-ONLESION, 45381 READY - while its own
        code 45380 is held, and its round-2 Q-ONLESION is not asked (on int6 it was asked and released 45380)."""
        for name, pattern in (('holding', HOLD), ('unclear', UNCLEAR), ('missing', MISSING)):
            with self.subTest(rel=name):
                doc = base_doc(e4_performer=sup(EF.TEAM))
                other_pair(doc)
                R, events = finish(doc, asked=((4, 1), (7, 2)))
                found, records, plans, R_q = walk(R, events, answers(pattern))
                self.assertEqual(families(plans), [['Q-ONLESION', 'Q-REL', 'Q-FACT'], []])
                self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['result'], 'supported')
                self.assertEqual(found['45381'], ('ready', []))
                self.assertEqual(found['45380'][0], 'needs_clarification')
                self.assertEqual((relation(R_q, 3, 4), relation(R_q, 6, 7)), ('independent', 'contradiction'))
        doc = base_doc(e4_performer=sup(EF.TEAM))
        other_pair(doc)
        R, events = finish(doc, asked=((4, 1), (7, 2)))
        found, _records, _plans, _R_q = walk(R, events, answers(RELEASE))
        self.assertEqual((found['45381'], found['45380']), (('ready', []), ('ready', [])))

    def test_another_statement_of_the_act_naming_no_lesion(self) -> None:
        """E5 denies an injection naming NO lesion: the not-on "E4 was not done to L1" releases no pair of E5's
        (pairing's arm reads E5's own lesions: none), so its Q-REL answered holding is about another pair. At the
        stage's call (no FactSet) exclusivity reads a Q-ONLESION as about every event statement of its act - the
        fail-closed scope - and holds E3's release too; read on R_base it holds only E5's own pair. 45381 is held
        either way (E5's pair), with the existing reasons."""
        doc = base_doc(e4_performer=sup(EF.TEAM))
        second_denial(doc, lesion=False)
        R, events = finish(doc)
        found, records, _plans, R_q = walk(R, events, answers(HOLD))
        self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['reasons'], [CONFLICT])
        self.assertEqual((relation(R_q, 3, 4), relation(R_q, 5, 4)), ('contradiction', 'unresolved'))
        self.assertEqual(found['45381'], ('needs_clarification', [('conflict:tattoo', 'relation:contradiction', 'E4'),
                                                                  ('event_performer', 'relation:unresolved', 'E4')]))
        found, records, _plans, R_q = walk(R, events, answers(HOLD), with_R=True)
        self.assertEqual(record(records, 'Q-ONLESION', ('E4', 'L1'))['result'], 'supported')
        self.assertEqual((relation(R_q, 3, 4), relation(R_q, 5, 4)), ('independent', 'unresolved'))
        self.assertEqual(found['45381'], ('needs_clarification', [('event_performer', 'relation:unresolved', 'E4')]))
        for with_R in (False, True):
            found, _records, _plans, R_q = walk(R, events, answers(RELEASE), with_R=with_R)
            self.assertEqual(found['45381'], ('ready', []))

    def test_two_rel_pairs_of_one_act_are_each_their_own(self) -> None:
        """Two Q-REL answers about two pairs of one act never hold each other (each releases its own pair, as on
        int6): E3 and E5 (both performed, so far as they name a performer, by the documenting team) both UNRESOLVED
        against E4 on its doubted performer, (E3, E4) released, (E5, E4) holding."""
        doc = base_doc()
        second_denial(doc, performer=sup(EF.TEAM))
        R, events = finish(doc)
        found, records, plans, R_q = walk(R, events, answers(RELEASE, **{'E5_E4': HOLD}))
        self.assertEqual(results(records)[('Q-REL', ('E3', 'E4'))], ('supported', []))
        self.assertEqual(relation(R_q, 3, 4), 'independent')
        self.assertEqual(found['45381'][0], 'needs_clarification')
        # and round 2 asks neither pair through Q-ONLESION: its not-on would release E5's pair, which E5's answer holds
        self.assertNotIn('Q-ONLESION', [family for plan in families(plans) for family in plan])


# --- the rule at the records ------------------------------------------------------------------------------------------------


class ExclusiveTests(SimpleTestCase):
    """contract/settle.exclusive's half of D328 (2) over records settle_questions wrote: called as jobs.py calls it
    (no FactSet: fail-closed scopes) and reading R_base."""

    def setUp(self) -> None:
        self.R, self.events = scene(performer=sup(EF.TEAM))  # the pair (E3, E4) a CONTRADICTION on R_base
        self.rel, self.onl = rel_spec('E3', 'E4'), onlesion_spec('E4', 'L1')

    def both(self, rel_pattern, onl_pattern, *, rel_round=1, onl_round=2, rel_health='answered',
             onl_health='answered', R=None):
        records = (settled(self.R, [(self.rel, rel_pattern)], health=rel_health, round_=rel_round)
                   + settled(self.R, [(self.onl, onl_pattern)], health=onl_health, round_=onl_round, batch=2))
        return settle.exclusive(sorted(records, key=lambda item: (item['round'], item['batch'])), [], R)

    def released(self, records):
        R_q = F._answered(self.R, {**self.events, 'questions': records})
        return relation(R_q, 3, 4), '45381' in TP.ready(TP.assessed(R_q, CODES))

    def test_the_finding_both_orders_and_both_scopes(self) -> None:
        for R in (None, self.R):
            for name, pattern in NOT_RELEASE.items():
                for order, rounds in (('rel first', (1, 2)), ('onlesion first', (2, 1)), ('one round', (1, 1))):
                    with self.subTest(R=R is not None, rel=name, order=order):
                        out = self.both(pattern, RELEASE, rel_round=rounds[0], onl_round=rounds[1], R=R)
                        self.assertEqual(results(out)[('Q-ONLESION', ('E4', 'L1'))], ('unresolved', [CONFLICT]))
                        self.assertEqual(self.released(out), ('contradiction', False))
                    with self.subTest(R=R is not None, onlesion=name, order=order):
                        out = self.both(RELEASE, pattern, rel_round=rounds[0], onl_round=rounds[1], R=R)
                        self.assertEqual(results(out)[('Q-REL', ('E3', 'E4'))], ('unresolved', [CONFLICT]))
                        self.assertEqual(self.released(out), ('contradiction', False))
            out = self.both(RELEASE, RELEASE, R=R)
            self.assertEqual([item['result'] for item in out], ['supported', 'supported'])
            self.assertEqual(self.released(out), ('independent', True))

    def test_a_refused_or_failed_request_holds_on_either_side(self) -> None:
        for health in ('breach', 'failed'):
            with self.subTest(rel=health):
                out = self.both(RELEASE, RELEASE, rel_health=health)
                self.assertEqual(results(out)[('Q-ONLESION', ('E4', 'L1'))], ('unresolved', [CONFLICT]))
            with self.subTest(onlesion=health):
                out = self.both(RELEASE, RELEASE, onl_health=health)
                self.assertEqual(results(out)[('Q-REL', ('E3', 'E4'))], ('unresolved', [CONFLICT]))

    def test_a_plan_time_refusal_holds(self) -> None:
        onl = settled(self.R, [(self.onl, RELEASE)], round_=2)
        self.assertEqual(settle.exclusive(onl, [refusal(self.rel)])[0]['reasons'], [CONFLICT])
        rel = settled(self.R, [(self.rel, RELEASE)])
        self.assertEqual(settle.exclusive(rel, [refusal(self.onl)], self.R)[0]['reasons'], [CONFLICT])
        # a Q-FACT refusal is no pair's: it holds no pair-family record
        fact_spec = asking.QuestionSpec(FAM.Q_FACT, 'fact.performer', ('E4',), A.PERFORMER, 'documenting_team', False,
                                        ('E4',), census='F3')
        self.assertEqual(settle.exclusive(onl, [refusal(fact_spec)])[0]['result'], 'supported')

    def test_the_same_proposition_answered_two_ways_holds(self) -> None:
        first = settled(self.R, [(self.onl, RELEASE)], round_=1)
        again = settled(self.R, [(self.onl, UNCLEAR)], round_=2)
        self.assertEqual(results(settle.exclusive(first + again))[('Q-ONLESION', ('E4', 'L1'))][1], ['question_unclear'])
        self.assertEqual(settle.exclusive(first + again)[0]['reasons'], [CONFLICT])
        twice = settled(self.R, [(self.onl, RELEASE)], round_=2)
        self.assertEqual([item['result'] for item in settle.exclusive(first + twice)], ['supported', 'supported'])

    def test_a_kept_unlisted_entrys_pair_is_its_own(self) -> None:
        """A kept unlisted entry's Q-REL ('u:0', E4) is released only by Q-REL answers (pairing.unlisted_pairs): a
        not-on is about no entry's pair, so neither holds the other - in either scope - while an unlisted entry's two
        answers about its own pair do."""
        doc = base_doc(e4_performer=sup(EF.TEAM))
        doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DENIAL, Kind.INJECTION, None, EF.unit(9)))
        R, _events = finish(doc)
        entry = asking.QuestionSpec(FAM.Q_REL, 'rel.deny_or_doubt', ('u:0', 'E4'), None, '', False, ('u:0', 'E4'),
                                    census='U1')
        for scope in (None, R):
            with self.subTest(R=scope is not None):
                out = settle.exclusive(settled(R, [(entry, RELEASE)]) + settled(R, [(self.onl, HOLD)], round_=2),
                                       [], scope)
                self.assertEqual(out[0]['result'], 'supported')
                out = settle.exclusive(settled(R, [(entry, HOLD)]) + settled(R, [(self.onl, RELEASE)], round_=2),
                                       [], scope)
                self.assertEqual(out[1]['result'], 'supported')
        self.assertEqual(settle.pair_scopes({'family': 'Q-REL', 'subjects': ['u:0', 'E4']}),
                         frozenset({settle.PairScope('u:0', 'E4')}))
        self.assertFalse(settle._meets(settle.PairScope('u:0', 'E4'), settle.PairScope(None, 'E4')))

    def test_two_lesions_of_one_listed_statement(self) -> None:
        """E3 denies an injection for L1 and L2 (listed targets): its pair is asked through BOTH not-ons; one of them
        answered other than the release holds the other's release, in either scope (an established "not on L1" beside
        "on L2" would let pairing's listed arm read L2 apart by its finding's places alone). Two not-ons of one act about
        no common statement's pair (read on R_base) hold nothing of each other."""
        doc = EF.colonoscopy()
        doc.lesions[L(1)] = {**doc.lesions[L(1)], A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
        doc.lesion(2, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.act(3, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.LISTED_TARGETS),
                targets=[sup(L(1)), sup(L(2))], places=[sup(Landmark.SIGMOID_COLON)])
        doc.act(4, Kind.TATTOO, places=[sup(Landmark.SIGMOID_COLON)])
        R, _events = finish(doc, asked=((4, 1), (4, 2)))
        one, two = onlesion_spec('E4', 'L1'), onlesion_spec('E4', 'L2')
        for scope in (None, R):
            with self.subTest(R=scope is not None):
                out = settle.exclusive(settled(R, [(one, RELEASE)]) + settled(R, [(two, HOLD)], batch=2), [], scope)
                self.assertEqual(out[0]['reasons'], [CONFLICT])
                out = settle.exclusive(settled(R, [(one, RELEASE)]) + settled(R, [(two, RELEASE)], batch=2), [], scope)
                self.assertEqual([item['result'] for item in out], ['supported', 'supported'])
        # every event that may name L1 is a statement the not-on could set apart: E3, and the snare E2 itself
        self.assertEqual(settle.pair_scopes(settled(R, [(one, RELEASE)])[0], R),
                         frozenset({settle.PairScope('E2', 'E4'), settle.PairScope('E3', 'E4')}))
        # E3 lists L1 only, E5 L2 only: the two not-ons are about two pairs - held apart only without the FactSet
        doc = EF.colonoscopy()
        doc.lesions[L(1)] = {**doc.lesions[L(1)], A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
        doc.lesion(2, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.act(3, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
        doc.act(5, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L(2)), places=[sup(Landmark.SIGMOID_COLON)])
        doc.act(4, Kind.TATTOO, places=[sup(Landmark.SIGMOID_COLON)])
        R, _events = finish(doc, asked=((4, 1), (4, 2)))
        records = settled(R, [(one, RELEASE)]) + settled(R, [(two, HOLD)], batch=2)
        self.assertEqual(settle.exclusive(records, [], R)[0]['result'], 'supported')
        self.assertEqual(settle.exclusive(records)[0]['reasons'], [CONFLICT])

    def test_the_q_lesion_scopes(self) -> None:
        """Q-LESION (not planned: DECISIONS D320, D323 O1) is a pair family too: read on R_base it is about every pair
        of events naming its two lesions so, either way round; with no FactSet, about every event pair - a Q-REL of a
        pair it is about holds its release, and it holds theirs."""
        doc = base_doc(e4_performer=sup(EF.TEAM))
        doc.lesion(2, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.act(8, Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L(2)), places=[sup(Landmark.SIGMOID_COLON)])
        R, _events = finish(doc)
        lesion = settled(R, [(lesion_spec('L1', 'L2'), RELEASE)])[0]
        self.assertEqual(settle.pair_scopes(lesion, R), frozenset({
            settle.PairScope('E2', 'E8'), settle.PairScope('E3', 'E8'), settle.PairScope('E8', 'E2'),
            settle.PairScope('E8', 'E3')}))
        self.assertEqual(settle.pair_scopes(lesion), frozenset({settle.PairScope(None, None)}))
        rel = settled(R, [(rel_spec('E8', 'E2'), HOLD)], round_=2)
        for scope in (None, R):
            self.assertEqual(settle.exclusive([lesion] + rel, [], scope)[0]['reasons'], [CONFLICT])
        unrelated = settled(R, [(rel_spec('E3', 'E4'), HOLD)], round_=2)  # E4 names no lesion: no Q-LESION pair
        self.assertEqual(settle.exclusive([lesion] + unrelated, [], R)[0]['result'], 'supported')
        self.assertEqual(settle.exclusive([lesion] + unrelated)[0]['reasons'], [CONFLICT])

    def test_a_malformed_record_is_about_every_pair(self) -> None:
        self.assertEqual(settle.pair_scopes({'family': 'Q-ONLESION', 'subjects': ['E4']}),
                         frozenset({settle.PairScope(None, None)}))
        self.assertEqual(settle.pair_scopes({'family': 'Q-ONLESION', 'subjects': ['E4', 'L9']}, self.R),
                         frozenset({settle.PairScope(None, 'E4')}))  # a lesion R does not hold: fail-closed
        self.assertEqual(settle.pair_scopes({'family': 'Q-FACT', 'subjects': ['E4']}), frozenset())
        self.assertEqual(settle.pair_scopes({'family': 'Q-ABSORB', 'subjects': ['u:0']}), frozenset())

    def test_a_q_fact_or_q_absorb_answer_is_about_no_pair(self) -> None:
        """A Q-FACT answer (a slot's: D325 (1)'s table) and a Q-ABSORB answer are no pair family's: answered other than
        the release beside an established not-on, they hold nothing of it - in either scope."""
        doubted, _events = scene()  # E4's performer doubted: its Q-FACT is askable there
        fact_spec = asking.QuestionSpec(FAM.Q_FACT, 'fact.performer', ('E4',), A.PERFORMER, 'documenting_team', False,
                                        ('E4',), census='F3')
        absorb = {**settled(doubted, [(fact_spec, UNCLEAR)], round_=2, batch=3)[0], 'family': 'Q-ABSORB',
                  'form': 'absorb', 'subjects': ['u:0'], 'attribute': None, 'value': ''}
        for other in (settled(doubted, [(fact_spec, UNCLEAR)], round_=2, batch=2)[0], absorb):
            for scope in (None, self.R):
                with self.subTest(family=other['family'], R=scope is not None):
                    self.assertEqual(settle.pair_scopes(other, scope), frozenset())
                    out = settle.exclusive(settled(self.R, [(self.onl, RELEASE)]) + [other], [], scope)
                    self.assertEqual(out[0]['result'], 'supported')

    def test_idempotent_ordered_and_other_families_untouched(self) -> None:
        doubted, _events = scene()  # E4's performer doubted: its Q-FACT is askable there
        records = (settled(self.R, [(self.rel, HOLD)]) + settled(self.R, [(self.onl, RELEASE)], round_=2)
                   + settled(doubted, [(asking.QuestionSpec(FAM.Q_FACT, 'fact.performer', ('E4',), A.PERFORMER,
                                                            'documenting_team', False, ('E4',), census='F3'),
                                        RELEASE)], round_=2, batch=3))
        once = settle.exclusive(records)
        self.assertEqual(settle.exclusive(once), once)
        self.assertEqual(settle.exclusive(records[::-1])[::-1], once)
        self.assertEqual([item['result'] for item in once], ['unresolved', 'unresolved', 'supported'])
        self.assertEqual(once[1]['proof'], [])
        self.assertIs(once[0], records[0])  # a record not established is returned as it is
        self.assertTrue(settle.pair_held(settled(self.R, [(self.onl, RELEASE)])[0], records[:1]))
        self.assertFalse(settle.pair_held(settled(self.R, [(self.onl, RELEASE)])[0], records[2:]))


# --- THE CENSUS ---------------------------------------------------------------------------------------------------------

S_, C_, U_, M_ = V.SUPPORTS, V.CONTRADICTS, V.UNCLEAR, None
PATTERNS = tuple(itertools.product((S_, C_, U_, M_), repeat=2))  # every claim and control verdict pair (16)
# a proposition's state: not asked; asked in an answered, healthy request with one verdict pair; asked in a refused
# request (its calibration item answered wrong) or a failed one; refused at plan time (never sent)
STATES = ('absent', *PATTERNS, 'breach', 'failed', 'refused')
AFFIRMED_STATE = STATES.index((S_, C_))
MATCHING = ((S_, C_), (C_, S_))  # the patterns a table accepts: the release direction and the holding one


def census_scene(listed=False):
    """The census's FactSet: the finding's scene with E4's performer established (the pair (E3, E4) a CONTRADICTION on
    R_base), E3's target L1 alone or (``listed``) L1 and L2; and the other pair (E6, E7) of another act."""
    doc = EF.colonoscopy()
    doc.lesions[L(1)] = {**doc.lesions[L(1)], A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
    if listed:
        doc.lesion(3, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.act(3, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.LISTED_TARGETS),
                targets=[sup(L(1)), sup(L(3))], places=[sup(Landmark.SIGMOID_COLON)])
    else:
        doc.act(3, Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(4, Kind.TATTOO, places=[sup(Landmark.SIGMOID_COLON)])
    other_pair(doc, performer=sup(EF.TEAM))
    return finish(doc, asked=((4, 1), (4, 3), (7, 2)) if listed else ((4, 1), (7, 2)))


class _Census:
    """One census: ``specs`` the propositions asked of the pair (E3, E4) and the unrelated pair's one, each record
    written by settle_questions in a request of its own; ``combination`` a state per proposition."""

    def __init__(self, R, specs, other):
        self.R, self.specs, self.other = R, specs, other
        self.made = {}

    def made_for(self, index, state):
        key = (index, state)
        if key not in self.made:
            spec = (self.specs + [self.other])[index]
            if state == 'absent':
                found = ([], [])
            elif state == 'refused':
                found = ([], [refusal(spec, index + 1)])
            elif state in ('breach', 'failed'):
                found = (settled(self.R, [(spec, (S_, C_))], health=state, round_=index + 1), [])
            else:
                found = (settled(self.R, [(spec, state)], round_=index + 1), [])
            self.made[key] = found
        return self.made[key]

    def listed(self, combination):
        records, refused = [], []
        for index, state in enumerate(combination):
            more, entries = self.made_for(index, STATES[state])
            records += more
            refused += entries
        return records, refused

    def expected(self, combination):
        """The oracle: each record's (family, subjects) -> established after exclusivity - its own pattern the release
        direction in a healthy request, and (for the pair's own propositions) every other asked proposition of the
        pair the release direction in a healthy request too; the unrelated pair's record by its own alone."""
        pair = combination[:-1]
        asked = [state for state in pair if STATES[state] != 'absent']
        everyone = all(state == AFFIRMED_STATE for state in asked)
        out = {}
        for index, state in enumerate(combination):
            if STATES[state] in ('absent', 'refused'):
                continue
            spec = (self.specs + [self.other])[index]
            own = state == AFFIRMED_STATE
            out[(spec.family.value, spec.subjects)] = own and (everyone if index < len(pair) else True)
        return out

    def got(self, combination, R=None):
        records, refused = self.listed(combination)
        out = settle.exclusive(records, refused, R)
        return {(item['family'], tuple(item['subjects'])): item['result'] == 'supported' for item in out}


def single_changes(combination, positions):
    """Every combination one member's verdict away from ``combination`` at a proposition of ``positions``, with whether
    the change goes from a pattern some table accepts (MATCHING) to one none accepts."""
    for position in positions:
        state = STATES[combination[position]]
        if not isinstance(state, tuple):
            continue
        for member in (0, 1):
            for value in (S_, C_, U_, M_):
                if value == state[member]:
                    continue
                changed = (value, state[1]) if member == 0 else (state[0], value)
                new = list(combination)
                new[position] = STATES.index(changed)
                yield tuple(new), state in MATCHING and changed not in MATCHING


class PairCensusTests(SimpleTestCase):
    """THE CENSUS of D328 (2) (module docstring), at settle.exclusive over the records settle_questions writes - as
    jobs.py calls it and reading R_base - and at the fold (the pair's relation on R_q, 45381's status)."""

    def run_census(self, census, R_scope, size):
        seen = {}
        for combination in itertools.product(range(len(STATES)), repeat=size):
            got = census.got(combination, R_scope)
            self.assertEqual(got, census.expected(combination), [STATES[state] for state in combination])
            seen[combination] = frozenset(key for key, flag in got.items() if flag)
        return seen

    def check_monotone(self, seen, positions):
        changes = 0
        for combination, before in seen.items():
            for new, away in single_changes(combination, positions):
                if away:
                    changes += 1
                    self.assertLessEqual(seen[new], before, (combination, new))
        return changes

    def test_rel_and_one_onlesion_beside_another_pair(self) -> None:
        R, _events = census_scene()
        census = _Census(R, [rel_spec('E3', 'E4'), onlesion_spec('E4', 'L1')], rel_spec('E6', 'E7'))
        self.assertEqual(len(STATES), 20)
        for scope in (None, R):
            with self.subTest(R=scope is not None):
                seen = self.run_census(census, scope, 3)
                self.assertEqual(len(seen), 20 ** 3)
                self.assertGreater(self.check_monotone(seen, (0, 1, 2)), 10_000)
                self.assertEqual(set().union(*seen.values()), {('Q-REL', ('E3', 'E4')), ('Q-ONLESION', ('E4', 'L1')),
                                                               ('Q-REL', ('E6', 'E7'))})

    def test_rel_and_the_two_onlesions_of_a_listed_statement(self) -> None:
        R, _events = census_scene(listed=True)
        census = _Census(R, [rel_spec('E3', 'E4'), onlesion_spec('E4', 'L1'), onlesion_spec('E4', 'L3')],
                         rel_spec('E6', 'E7'))
        for scope in (None, R):
            with self.subTest(R=scope is not None):
                seen = {}
                for combination in itertools.product(range(len(STATES)), repeat=3):
                    combination = (*combination, AFFIRMED_STATE)  # the other pair released throughout
                    got = census.got(combination, scope)
                    self.assertEqual(got, census.expected(combination), [STATES[state] for state in combination])
                    seen[combination] = frozenset(key for key, flag in got.items() if flag)
                self.assertGreater(self.check_monotone(seen, (0, 1, 2)), 10_000)

    def test_rel_and_a_q_lesion(self) -> None:
        """Q-LESION if ever built: a pair's Q-REL and a Q-LESION about it (E8 denies a snare of L2, E2 the snare of
        L1: "L1 is a different lesion from L2" is about (E8, E2) read on R_base, and about every pair without it)."""
        doc = EF.colonoscopy()
        doc.lesion(2, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.act(8, Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L(2)), places=[sup(Landmark.SIGMOID_COLON)])
        other_pair(doc, performer=sup(EF.TEAM), lesion=5)
        R, _events = finish(doc, asked=((7, 5),))
        census = _Census(R, [rel_spec('E8', 'E2'), lesion_spec('L1', 'L2')], rel_spec('E6', 'E7'))
        for scope in (None, R):
            with self.subTest(R=scope is not None):
                seen = {}
                for combination in itertools.product(range(len(STATES)), repeat=2):
                    combination = (*combination, AFFIRMED_STATE)
                    got = census.got(combination, scope)
                    expected = census.expected(combination)
                    if scope is None:  # without the FactSet the Q-LESION is about every pair: the other pair's too
                        lesion_state = STATES[combination[1]]
                        if lesion_state != 'absent' and combination[1] != AFFIRMED_STATE:
                            expected[('Q-REL', ('E6', 'E7'))] = False
                    self.assertEqual(got, expected, [STATES[state] for state in combination])
                    seen[combination] = frozenset(key for key, flag in got.items() if flag)
                self.assertGreater(self.check_monotone(seen, (0, 1)), 100)

    def test_the_fold_and_ready_level(self) -> None:
        """At the fold: (E3, E4) is INDEPENDENT on R_q - 45381 READY - exactly when every asked proposition of the pair
        reads the release direction in a healthy request (and one is asked); the other pair by its own answer alone;
        and no single verdict change from matching to not matching grows either."""
        R, events = census_scene()
        census = _Census(R, [rel_spec('E3', 'E4'), onlesion_spec('E4', 'L1')], rel_spec('E6', 'E7'))
        codes = (('45381', 4), ('45380', 7))
        for scope in (None, R):
            seen = {}
            for combination in itertools.product(range(len(STATES)), repeat=2):
                for other in (AFFIRMED_STATE, STATES.index((C_, S_))):
                    full = (*combination, other)
                    records, refused = census.listed(full)
                    R_q = F._answered(R, {**events, 'questions': settle.exclusive(records, refused, scope)})
                    asked = [state for state in combination if STATES[state] != 'absent']
                    expected = bool(asked) and all(state == AFFIRMED_STATE for state in asked)
                    with self.subTest(R=scope is not None, states=[STATES[state] for state in full]):
                        self.assertEqual(relation(R_q, 3, 4) == 'independent', expected)
                        self.assertEqual(relation(R_q, 6, 7) == 'independent', other == AFFIRMED_STATE)
                    ready = frozenset(item.code for item in TP.assessed(R_q, codes).codes
                                      if item.status is Outcome.READY)
                    self.assertEqual('45381' in ready, expected)
                    seen[full] = ready
            changes = 0
            for full, before in seen.items():
                for new, away in single_changes(full, (0, 1)):
                    if away:
                        changes += 1
                        self.assertLessEqual(seen[new], before, (full, new))
            self.assertGreater(changes, 50)
