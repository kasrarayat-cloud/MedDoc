"""Round r3's build, lane engine (DECISIONS D320; D316 QB, D312 (5), D323 F1 F3 O1): the engine's own correctness under
the question stage. TEXT-ONLY and SYNTHETIC: every FactSet is built in code (tests/v2/evaluate_fixtures' Doc,
test_r2fm_lesion's scene, test_pairing's builders), every stored answer by hand; no document is read and nothing is
sent anywhere.

Each rule is shown on an input it must change - red on the port (int3 + the r3 probe prototype, build-v2/a2b/r3b/port),
green on this lane's tree - and on a boundary it must leave alone:
- QBTests (D316 QB, BLOCKING): an act naming no lesion is NOT set apart from a statement by an established not-on of the
  statement's lesion where the statement's own places beyond its not-on lesions' places hold the act's place - QB's
  recorded scene (a single target L1 in the transverse colon, established not-on, the denial at L1's place AND at the
  whole colon, a tattoo in the transverse colon, no place control) stays SAME, held relation:contradiction; the 9.4
  deletion of that umbrella releases, only into P4-ONLESION's ruled shape (pair 4's), the named release D316_QB of
  tests/v2/test_properties. QD (the RD1 class) stays the one named release of D245's class, unchanged.
- OnlesionArmTests (D323 F1, HIGH): the prototype's separate Q-ONLESION arm is gone; an established Q-ONLESION answer
  (FactSet.off_lesion) is an established not-on read by pairing's one arm (_apart_from_unnamed) under D311's class rule
  and the QB clause - the port's probes q01 and q04 (QB's and RFL2-1's scenes) held with the answer established, pair
  4's shape released by it exactly as by the fact pass's act-lesion pair; ``pairing.not_on_sets_apart``, the arm's own
  what-if, is the planner's test that a SAME rests on the not-on lesions' places alone.
- StomaPossibleTests (D312 (5) with F.11 (3), D310 (1)): a colonoscopy code (45378-45398) is never READY while a stoma
  route is possible - an approach not ESTABLISHED as another route beside an anatomy entry whose type is supported or
  possible as a stoma, or the approach's own through_stoma reading possible - read so that no weakening releases; the
  route table's through-stoma codes READY only with the approach through_stoma and a stoma entry established; and the
  killing tests of the D312 checker's surviving route mutants S3 and S5.
- FoldEnumTests (D323 F3): the fold reads a stored question's family and subject as enumeration members, never by a
  string comparison - FINAL-V2 5.7 measure 4's two guards (tests.test_guard_static's own functions) find nothing in
  engine/facts.py.
- LesionPairRevertTests (D323 O1): b.3 is reverted - D296's fact-pass lesion pairs establish on R_base as on int3.
- ControlledFieldTests (D323 F4's killing test of the port's union mutant M2): a stored row's controlled facts reach
  the FactSet through facts.factset.
- AnswerMonotoneTests (DESIGN-v2 f.2, P-MONO-Q, for the readers this lane owns): with the answers fixed, no single 9.4
  weakening of the facts releases what no ruling names; removing or demoting an answer never grows READY or EXCLUDED;
  EXCLUDED(R_q) == EXCLUDED(R_base).

The repair pass (the lane's refutation: R3BE-RF1 high, R3BE-RF2 medium), each finding's input red on the pre-repair
tree, green here:
- DateCheckFoldTests (R3BE-RF1): an answer never lifts L1's date check (literal_unchecked, literal_mismatch), and the
  timing fact an answer establishes is re-judged by L1 on its stored literals at the FactSet's own effective date - the
  finding's stored row (the note states no date of service; the stage planned at none; the member supplies another day)
  and its variant (two document dates, the member settling on the other) held at the member's date; an unappraised or
  inherited date relation answered only where its own date words meet the assessment's date.
- AnswerablePredicateTests (R3BE-RF1/RF2's class on a Q-FACT): facts.answerable - exactly the facts the question stage
  may ask (not established, no pass-1 contradiction but a conflict, not judged by the fact pass, located) less L1's
  date checks - every Reason classified (an owner pin), its C2b set one with engine/questions.APPRAISAL_CAUSES and
  contract/settle.appraise.
- JudgedPairFoldTests (R3BE-RF2): no Q-ONLESION or Q-LESION answer over a pair the fact pass judged (its stored records'
  reasons, every asking, either order; a pair held unestablished with no record), no Q-REL answer over an established
  covers claim - pair 4's shape with "This act was not done on lesion L1." contradicted held; no weakening makes the
  refusal fall through.
"""
from __future__ import annotations

import collections
import dataclasses
from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy, asking, evaluate, pairing, whatif
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.requirements_table import CODES
from studio.interpretation.engine.types import Attribute, Id, IdFamily
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2fm_lesion as R2FM

A, LM = Attribute, ct.Landmark
E1, E2, E3, E4 = (Id.parse(name) for name in ('E1', 'E2', 'E3', 'E4'))
L1, L2 = Id.parse('L1'), Id.parse('L2')
X1, X2, Y1 = Id.parse('X1'), Id.parse('X2'), Id.parse('Y1')
SINGLE_TARGET, LISTED = ct.Breadth.SINGLE_TARGET, ct.Breadth.LISTED_TARGETS
INDEPENDENT, SAME = pairing.RowResult.INDEPENDENT, pairing.RowResult.SAME
CONTRADICTION = pairing.Relation.CONTRADICTION
sup, unres, neg, doubted = EF.sup, EF.unres, EF.neg, EF.doubted
APP = Path(__file__).resolve().parents[2]


def properties():
    """tests/v2/test_properties (imported when a test needs it: it builds its fixtures and its harness)."""
    from tests.v2 import test_properties
    return test_properties


def target(R, statement=E3, act=E4):
    return pairing.row(R, pairing.Row.TARGET, statement, act)


def relation(R, statement=E3, act=E4):
    return pairing.relation(R, statement, act).relation


def held_causes(R, code: str) -> list:
    return sorted({held.cause for held in evaluate.decide(code, (), R).held_facts})


def qb(*, beyond=(LM.COLON,), act_places=(LM.TRANSVERSE_COLON,), not_on=(L1,), breadth=SINGLE_TARGET, **over):
    """QB's recorded scene (D316; build-v2/a2b/r2f/f-lesion2/probes/mine/x01_questions.py): L1 (single) in the
    transverse colon, the denial E3 of an injection on its single target L1 placed at L1's place and at ``beyond``
    (places or Facts: by default the whole colon, an umbrella it names for itself), the tattoo E4 naming no lesion at
    ``act_places``, the place pair controls contract/claims.pair makes (none here: every place is compatible with one of
    the other object's own), the act-lesion pair (E4, distinct_from, L1) established for ``not_on``."""
    return R2FM.scene(breadth=breadth, not_on=not_on, denial_places=(LM.TRANSVERSE_COLON, *beyond),
                      act_places=act_places, **over)


def rfl2_1(**over):
    """RFL2-1's scene (the port's probe q01): the denial placed at L1's place and in the descending colon, the tattoo
    filed in the transverse colon only, pass 2 SUPPORTED "This act was done in the descending colon." (the act's control
    on that place not rejected)."""
    return R2FM.scene(breadth=SINGLE_TARGET, denial_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON),
                      verdict_of=lambda subject, place: not (subject == E4 and place is LM.DESCENDING_COLON), **over)


def with_segment(R, *ends, statement=E3):
    """``R`` with ``statement``'s scope.segment filed at ``ends`` (places or Facts) beside its target: the statement's
    own places include the segment's whole range (contract/claims.py's reading, DECISIONS D223)."""
    members = tuple(end if not isinstance(end, ct.Landmark) else sup(end) for end in ends)
    return replace(R, events={**R.events, statement: {**R.events[statement], A.SCOPE_SEGMENT: members}})


def answered(R, *pairs):
    """``R`` as R_q with an established Q-ONLESION answer for each (act, lesion) of ``pairs`` (FactSet.off_lesion),
    R_base its base: the FactSet the fold makes of such answers (FoldTests reads it through the fold itself)."""
    return replace(R, off_lesion=R.off_lesion | frozenset(pairs), base=R)


def without_not_on(R, act=E4, lesion=L1):
    """``R`` with the fact pass's act-lesion pair (act, distinct_from, lesion) never asked (no key)."""
    return replace(R, pair_controls={key: value for key, value in R.pair_controls.items()
                                     if key != (act, A.DISTINCT_FROM, lesion)})


def onlesion_record(act: str, lesion: str, result: str = 'supported') -> dict:
    """One stored question record of an established (``result`` supported) Q-ONLESION answer, as contract/settle writes
    it (the fields the fold reads)."""
    return {'family': 'Q-ONLESION', 'form': 'onlesion', 'subjects': [act, lesion], 'unlisted': None,
            'attribute': 'target.lesion', 'value': lesion, 'negated': True, 'result': result, 'reasons': [],
            'proof': [{'start': 100, 'end': 130}, {'start': 200, 'end': 230}]}


# --- (a) D316 QB ------------------------------------------------------------------------------------------------------


class QBTests(SimpleTestCase):
    def test_qb_the_recorded_scene_is_held(self):
        # the must-change pin (D316): QB's recorded scene - the port (int3's arm) set it apart, target=independent, and
        # released 45381; int2 held it. The denial's own umbrella holds the tattoo's place and catalogue.covers reads a
        # tattoo and an injection as one act: the note contradicts itself, so the pair stays SAME, a contradiction
        R = qb()
        self.assertEqual([key for key in R.pair_controls if key[1] is A.TARGET_PLACES], [])
        self.assertIs(F.established_not_on(R, E4, L1), True)
        self.assertEqual(target(R), SAME)
        self.assertIs(relation(R), CONTRADICTION)
        self.assertEqual(held_causes(R, '45381'), ['relation:contradiction'])

    def test_qb_every_place_beyond_the_lesions_that_may_hold_the_acts_holds(self):
        # an umbrella holding the act's place, a place it holds, the umbrella in any state but an established negation
        # (its claimed value kept, a doubt's reading, a contradiction's side), and a listed denial too: SAME every time
        cases = {
            'the colon': qb(),
            'the proximal colon': qb(beyond=(LM.PROXIMAL_COLON,)),
            'the colon unresolved': qb(beyond=(unres(LM.COLON),)),
            'a doubt reading the colon': qb(beyond=(doubted(LM.CECUM, LM.COLON),)),
            "a contradiction's side": qb(beyond=(EF.contra(LM.CECUM, LM.COLON),)),
            'an unplaceable anastomosis': qb(beyond=(LM.ANASTOMOSIS,)),
            'a listed denial on L1 and L2 (both in the transverse colon) and the colon': qb(
                breadth=LISTED, l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, L2)),
            'a segment from the hepatic to the splenic flexure filed beside the single target': with_segment(
                qb(beyond=()), LM.HEPATIC_FLEXURE, LM.SPLENIC_FLEXURE),
            'a segment end at the act\'s place, its other end unresolved': with_segment(
                qb(beyond=()), LM.TRANSVERSE_COLON, unres(LM.DESCENDING_COLON)),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(target(R), INDEPENDENT)
                self.assertNotEqual(relation(R), pairing.Relation.INDEPENDENT)

    def test_qb_the_boundary_places_within_the_lesions_or_disjoint_stay_apart(self):
        # the ruled releases the clause must leave alone: pair 4's shape (the denial at its lesion's place alone, or
        # unplaced), a place beyond it disjoint from the act's (the first refutation's q01: L2's cecum), a place beyond
        # it the statement is established NOT about, an act place answered by a rejected statement control
        cases = {
            "pair 4's shape: the denial at L1's place only": qb(beyond=()),
            'the denial beyond L1 in the cecum': qb(beyond=(LM.CECUM,)),
            'the denial beyond L1 in the descending colon': qb(beyond=(LM.DESCENDING_COLON,)),
            'the denial established not about the colon': qb(beyond=(neg(LM.COLON),)),
            "the first refutation's q01 (a listed denial, L2 in the cecum)": R2FM.scene(not_on=(L1,)),
            'the sigmoid colon asked of the denial and rejected': qb(beyond=(), act_places=(LM.TRANSVERSE_COLON,
                                                                                            LM.SIGMOID_COLON)),
            'a segment beyond L1 from the descending colon to the rectum': with_segment(
                qb(beyond=()), LM.DESCENDING_COLON, LM.RECTUM),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertEqual(target(R), INDEPENDENT)
                self.assertIs(relation(R), pairing.Relation.INDEPENDENT)
        placed = qb(beyond=())
        facts = {attribute: members for attribute, members in placed.events[E3].items()
                 if attribute is not A.TARGET_PLACES}
        unplaced = replace(placed, events={**placed.events, E3: facts})
        self.assertEqual(target(unplaced), INDEPENDENT)  # an unplaced denial (pair 4's E10): nothing beyond it

    def test_qb_only_the_not_on_answer_is_narrowed_a_rejected_statement_control_still_answers(self):
        # the clause narrows what an established not-on answers, never SC-B's own second direction: an act place the
        # statement was asked about by a rejected place pair control is answered by that control, whatever the
        # statement's umbrella - the denial beyond L1 in the descending colon, the tattoo also in the sigmoid colon,
        # which claims.pair asks the denial about (rejected): apart; and the same constructed control asked about the
        # transverse colon itself beside QB's umbrella answers it (claims.pair never makes it - a unit pin of the rule's
        # two alternatives, not a reachable input)
        R = qb(act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON), beyond=(LM.DESCENDING_COLON,))
        self.assertIs(R.pair_controls[(E3, A.TARGET_PLACES, LM.SIGMOID_COLON)], True)
        self.assertEqual(target(R), INDEPENDENT)
        answered_by_control = qb(extra={(E3, A.TARGET_PLACES, LM.TRANSVERSE_COLON): True})
        self.assertTrue(pairing._held_beyond(answered_by_control, E3, LM.TRANSVERSE_COLON,
                                             frozenset({LM.TRANSVERSE_COLON})))
        self.assertEqual(target(answered_by_control), INDEPENDENT)
        self.assertEqual(target(qb()), SAME)  # without it: the not-on alone, narrowed

    def test_qb_the_deletion_of_the_umbrella_is_the_one_release_and_lands_in_pair_4s_shape(self):
        # 9.4 over QB's scene (test_properties.weakenings: every fact, every list member deleted, every pair control
        # unrejected, the pair-type outcomes re-derived): the only release is the deletion of the denial's umbrella,
        # which leaves exactly the ruled shape (pair 4's: placed within its not-on lesion's places) - D316_QB
        TP = properties()
        R = qb()
        released = []
        for label, weak, what in TP.weakenings(R):
            if target(weak) is INDEPENDENT:
                released.append(label)
                self.assertTrue(TP._qb_statement_place_deletion(label, what, '45381', R), label)
        self.assertEqual(released, ['deleted E3 target.places[1]'])
        self.assertEqual(target(qb(beyond=())), INDEPENDENT)  # the shape it lands in

    def test_qd_the_rd1_class_stays_the_one_named_act_place_deletion(self):
        # QD (D316: decided with QB): 9.4's deletion of an ACT place no control asks either object about releases, as
        # refute-r2d-r2 RD1 (D245) names it - nothing of the deleted place is left in the FactSet to read; the QB clause
        # narrows it: the remaining act place must be clear of every place beyond the not-on lesions too
        TP = properties()
        twin = R2FM.scene(breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                          act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON))
        released = [label for label, weak, what in TP.weakenings(twin) if target(weak) is INDEPENDENT]
        self.assertEqual(released, ['deleted E4 target.places[1]'])
        umbrella = R2FM.scene(breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.COLON),
                              act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON))
        self.assertNotEqual(target(umbrella), INDEPENDENT)
        # the act's sigmoid colon deleted leaves its transverse colon held by the umbrella; the umbrella deleted leaves
        # the sigmoid colon answered by nothing (no control was made for it): neither releases
        self.assertEqual([label for label, weak, what in TP.weakenings(umbrella) if target(weak) is INDEPENDENT], [])


# --- (d) D323 F1: the one arm -----------------------------------------------------------------------------------------


class OnlesionArmTests(SimpleTestCase):
    def test_the_port_probes_q01_and_q04_are_held_with_the_answer_established(self):
        # the must-change pins (D323 F1): QB's and RFL2-1's scenes with NO fact-pass pair and an established Q-ONLESION
        # answer "This act was not done to lesion L1." (TRUE as worded) - the port's separate arm set both apart and
        # released 45381; read by the one arm, both stay SAME, held relation:contradiction, on R_q as on R_base
        for name, R in (('QB', without_not_on(qb())), ('RFL2-1', rfl2_1())):
            with self.subTest(scene=name):
                self.assertNotIn((E4, A.DISTINCT_FROM, L1), R.pair_controls)
                R_q = answered(R, (E4, L1))
                self.assertIs(F.established_not_on(R_q, E4, L1), True)
                self.assertEqual(target(R_q), SAME)
                self.assertIs(relation(R_q), CONTRADICTION)
                self.assertEqual(held_causes(R_q, '45381'), ['relation:contradiction'])
                self.assertEqual(held_causes(R_q.excluding, '45381'), ['relation:contradiction'])

    def test_the_answer_releases_exactly_where_the_fact_pass_pair_would(self):
        # one reading of an established not-on, whichever pass made it: on every scene the target row with the
        # Q-ONLESION answer equals the row with the fact pass's act-lesion pair - pair 4's shape released by both
        # (the boundary), and the held scenes held by both
        scenes = {
            "pair 4's shape": qb(beyond=()),
            'a second act place answered by a rejected statement control': qb(beyond=(), act_places=(
                LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
            'the listed denial, L2 apart by its places': R2FM.scene(not_on=(L1,)),
            'QB': qb(),
            'RFL2-1': rfl2_1(not_on=(L1,)),
            'the denial in the sigmoid colon the tattoo is in': R2FM.scene(
                breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
        }
        expected = {"pair 4's shape": INDEPENDENT, 'a second act place answered by a rejected statement control':
                    INDEPENDENT, 'the listed denial, L2 apart by its places': INDEPENDENT}
        for name, R in scenes.items():
            with self.subTest(scene=name):
                by_answer = answered(without_not_on(R), (E4, L1))
                self.assertEqual(target(by_answer), target(R))
                self.assertEqual(target(R), expected.get(name, SAME))
                self.assertNotEqual(target(without_not_on(R)), INDEPENDENT)  # neither: held (the answer is the release)

    def test_the_answer_is_read_through_the_fold_and_never_on_r_base(self):
        # the stored record through facts._answered: R_q sets pair 4's shape apart, R_base (its base, 4.6's) does not;
        # an unresolved record folds nothing; an answer on an act whose target names a lesion is read by no arm
        R = without_not_on(qb(beyond=()))
        R_q = F._answered(R, {'questions': [onlesion_record('E4', 'L1')]})
        self.assertEqual(R_q.off_lesion, frozenset({(E4, L1)}))
        self.assertEqual(target(R_q), INDEPENDENT)
        self.assertIs(R_q.excluding, R)
        self.assertNotEqual(target(R_q.excluding), INDEPENDENT)
        self.assertIs(F._answered(R, {'questions': [onlesion_record('E4', 'L1', 'unresolved')]}), R)
        named = replace(R, events={**R.events, E4: {**R.events[E4], A.TARGET_LESION: (unres(L2),)}})
        self.assertNotEqual(target(answered(named, (E4, L1))), INDEPENDENT)

    def test_the_listed_arm_reads_the_answer_as_an_asked_lesion(self):
        # a listed denial on L1 and L2 (both at the tattoo's transverse colon): the fact pass asked neither; an answer
        # for each is read by established not-on (an asked lesion), and the pair is apart; an answer for L1 alone leaves
        # L2 read by its finding's places, which hold the tattoo's - held
        R = R2FM.scene(l2_places=(LM.TRANSVERSE_COLON,))
        self.assertNotEqual(target(R), INDEPENDENT)
        self.assertEqual(pairing._asked_about(answered(R, (E4, L1), (E4, L2)), E4), frozenset({L1, L2}))
        self.assertEqual(target(answered(R, (E4, L1), (E4, L2))), INDEPENDENT)
        self.assertNotEqual(target(answered(R, (E4, L1))), INDEPENDENT)

    def test_an_answer_beside_an_act_filed_possible_statement_sets_nothing_apart(self):
        # the boundary of the one arm: D305 and D311 read an established not-on in the single and listed arms only; an
        # act-filed possible statement's own target (D228's arm) reads none, so an answer releases nothing there - and
        # not_on_sets_apart tells the planner so
        doc = EF.colonoscopy(places=[sup(LM.TRANSVERSE_COLON)])
        doc.lesions[L1] = EF.facts_of(multiplicity=sup(ct.Multiplicity.SINGLE),
                                      lesion_places=[sup(LM.TRANSVERSE_COLON)])
        doc.act(3, ct.Kind.INJECTION, status=unres(ct.Status.PERFORMED), lesion=sup(L1),
                places=[sup(LM.TRANSVERSE_COLON)])
        doc.act(4, ct.Kind.TATTOO, places=[sup(LM.TRANSVERSE_COLON)])
        R = doc.build()
        self.assertIs(pairing._mode(R, pairing._context(R, E3, E4)), pairing._Mode.OWN)
        self.assertEqual(target(R), SAME)
        self.assertEqual(target(answered(R, (E4, L1))), SAME)
        self.assertFalse(pairing.not_on_sets_apart(R, E3, E4))

    def test_not_on_sets_apart_is_the_arms_own_what_if(self):
        # True exactly where an established not-on of every lesion of the statement would set the pair apart: pair 4's
        # shape and the listed q01 (L2 apart by its places) - False on QB's and RFL2-1's scenes and the sigmoid twin,
        # where no true answer can release; R itself never changes
        cases = {"pair 4's shape": (without_not_on(qb(beyond=())), True),
                 'the listed q01': (without_not_on(R2FM.scene(not_on=(L1,))), True),
                 'QB': (without_not_on(qb()), False), 'RFL2-1': (rfl2_1(), False),
                 'the sigmoid twin': (without_not_on(R2FM.scene(
                     breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                     act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON))), False)}
        for name, (R, expected) in cases.items():
            with self.subTest(case=name):
                before = (R.off_lesion, dict(R.pair_controls))
                self.assertIs(pairing.not_on_sets_apart(R, E3, E4), expected)
                self.assertEqual((R.off_lesion, dict(R.pair_controls)), before)
                self.assertEqual(target(answered(R, (E4, L1), (E4, L2))) is INDEPENDENT, expected)
        named = without_not_on(qb(beyond=()))
        named = replace(named, events={**named.events, E4: {**named.events[E4], A.TARGET_LESION: (sup(L2),)}})
        self.assertFalse(pairing.not_on_sets_apart(named, E3, E4))  # an act naming a lesion: another arm's


# --- (b) D312 (5), D310 (1): the colonoscopy route table --------------------------------------------------------------


def route_note(approach=None, entry=None, **snare_over):
    """EF.colonoscopy (X1, its examination E1, the cold snare E2 of L1: 45385) with the session's approach ``approach``
    (a Fact, or None for none filed) and an anatomy entry Y1 of type ``entry`` (a Fact, or None for no entry)."""
    doc = EF.colonoscopy(**snare_over)
    if approach is not None:
        doc.sessions[X1][A.APPROACH] = (approach,)
    if entry is not None:
        doc.entry(1, type=entry)
    return doc


def route_holds(R, code: str) -> list:
    return [(held.fact, held.cause, held.attribute, held.kind.value)
            for held in evaluate.decide(code, (), R).held_facts]


class StomaPossibleTests(SimpleTestCase):
    def test_finding_5_a_stoma_entry_beside_an_approach_only_unresolved_holds_the_colonoscopy_code(self):
        # the must-change pin (D312 (5)): an established (or possible) stoma entry beside an approach pass 2 never
        # established - transanal only unresolved - held 45385 on nothing: facts.possibly kept the unresolved claim's
        # value and ruled the stoma route out. A stoma route is possible: held on the approach question
        # round r3's round 7 (DECISIONS D342 (1) (a)): unres's default reason is pass 2's appraisal_unclear - an entry
        # type pass 2 was asked and did not establish is read at its WIDEST: it may be an ileal pouch or the colon filed
        # absent, so the table's own hold answers first (moved by evaluate._may_be, settled_narrows); the stoma pass 2
        # was never asked (unappraised: D340 Q1) keeps the approach question
        for name, entry, expected in (
                ('supported', sup(ct.AnatomyType.STOMA), [('procedure', A.APPROACH, 'question')]),
                ('unresolved', unres(ct.AnatomyType.STOMA), [('procedure', A.TYPE, 'question')]),
                ('unappraised', unres(ct.AnatomyType.STOMA, ct.Reason.UNAPPRAISED),
                 [('procedure', A.APPROACH, 'question')])):
            with self.subTest(entry=name):
                R = route_note(unres(ct.Approach.TRANSANAL, ct.Reason.GEOMETRY_SECTION), entry).build()
                self.assertTrue(evaluate.stoma_possible(R, X1))
                self.assertEqual([(fact, attribute, kind) for fact, _cause, attribute, kind in route_holds(R, '45385')],
                                 expected)

    def test_the_approachs_own_through_stoma_reading_makes_a_stoma_route_possible_without_an_entry(self):
        # F.11 (3): with no anatomy entry at all, the approach's own reading of a stoma route holds the code - its
        # claim, a doubt's reading, a contradiction's side, a pass-1 denial of the anus not established, and an
        # established denial of the anus (a negation reads every other route); none holds a code on a silent approach
        readings = {
            'claimed through_stoma, unresolved': unres(ct.Approach.THROUGH_STOMA, ct.Reason.GEOMETRY_SECTION),
            'a doubt reading through_stoma': doubted(ct.Approach.TRANSANAL, ct.Approach.THROUGH_STOMA),
            "a contradiction's side": EF.contra(ct.Approach.TRANSANAL, ct.Approach.THROUGH_STOMA),
            'transanal denied by pass 1, not established': EF.fact(ct.Result.UNRESOLVED, ct.Approach.TRANSANAL,
                                                                    ct.FactState.NEGATED,
                                                                    reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),
            'transanal denied, established': neg(ct.Approach.TRANSANAL),
        }
        for name, approach in readings.items():
            with self.subTest(approach=name):
                R = route_note(approach).build()
                self.assertTrue(evaluate.stoma_possible(R, X1))
                self.assertTrue(route_holds(R, '45385'))

    def test_the_boundary_an_established_route_or_no_stoma_leaves_the_colonoscopy_code_ready(self):
        # the boundary: an approach established transanal - beside an established stoma entry too (a diverting
        # ileostomy with the colonoscopy through the anus: the route is the established fact, D310 (1)) - through_stoma
        # denied beside a stoma entry, a silent approach with no entry that may be a stoma (int2's reading, D114), and a
        # transanal claim only unresolved with no entry: 45385 READY on each
        cases = {
            'transanal established': route_note(sup(ct.Approach.TRANSANAL)),
            'transanal established, a stoma entry': route_note(sup(ct.Approach.TRANSANAL), sup(ct.AnatomyType.STOMA)),
            'through_stoma denied, a stoma entry': route_note(neg(ct.Approach.THROUGH_STOMA),
                                                              sup(ct.AnatomyType.STOMA)),
            'silent, no entry': route_note(),
            'silent, an anastomosis': route_note(entry=sup(ct.AnatomyType.ANASTOMOSIS)),
            'transanal only unresolved, no entry': route_note(unres(ct.Approach.TRANSANAL, ct.Reason.GEOMETRY_SECTION)),
            'transanal claimed, pass 2 never asked, no entry': route_note(unres(ct.Approach.TRANSANAL,
                                                                                ct.Reason.UNAPPRAISED)),
        }
        # round r3's round 5 (DECISIONS D330 (1), lane rules6): the lower-GI path guard, after this arm, holds two of
        # them with the table's own hold - an approach filed (denied) as anything but per anus establishes no per-anus
        # route (R5R-7), and an anastomosis whose subtype and joins are both silent is the D328 addendum's residual
        guarded = {'through_stoma denied, a stoma entry', 'silent, an anastomosis'}
        # round r3's round 6 (DECISIONS D336 (1) (b) and (e), final check 4): the contract gives per anus no control, so
        # an approach supported per anus is never ESTABLISHED through one - beside an entry that may be a stoma the guard
        # reads it as a silent approach and holds (D312 (5)'s boundary stays for this arm; moved by evaluate.path_guard)
        guarded |= {'transanal established, a stoma entry'}
        # round r3's round 7 (DECISIONS D342 (1) (a)): an approach a failed check left unresolved is read at its WIDEST -
        # it may be through a stoma or a pouch, so the guard's per-anus clause (R5R-7) holds it (moved by
        # evaluate._anus_route_contradicted over _may_be); one pass 2 was never asked (unappraised) reads as filed
        guarded |= {'transanal only unresolved, no entry'}
        for name, doc in cases.items():
            with self.subTest(case=name):
                R = doc.build()
                self.assertFalse(evaluate.stoma_possible(R, X1))
                self.assertEqual(route_holds(R, '45385'),
                                 [('procedure', 'coding_rule:stoma_route', ct.Attribute.TYPE, 'question')]
                                 if name in guarded else [])

    def test_no_weakening_releases_a_colonoscopy_code_a_stoma_route_holds(self):
        # P-MONO over the closure's own inputs (test_properties.weakenings, every fact of every table, every member
        # deleted, ERASING included): from each held note, 45385 is never released by one weakening
        TP = properties()
        held = {
            'an established stoma entry, transanal only unresolved': route_note(
                unres(ct.Approach.TRANSANAL, ct.Reason.GEOMETRY_SECTION), sup(ct.AnatomyType.STOMA)),
            'through_stoma established, no entry': route_note(sup(ct.Approach.THROUGH_STOMA)),
            'transanal denied, established': route_note(neg(ct.Approach.TRANSANAL)),
            'an untyped entry, the approach silent': route_note(entry=F.SILENT),
        }
        for name, doc in held.items():
            R = doc.build()
            self.assertTrue(route_holds(R, '45385'), name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(route_holds(weak, '45385'))
            self.assertGreater(count, 40, name)

    def test_d310_1_the_route_tables_ranges(self):
        # the billing table's two ranges, exactly the catalogue's colonoscopy rows: 44388-44405 and 44408 through a
        # stoma (44406 and 44407, the EUS codes, read LOWER's stoma class), 45378-45398 through the anus
        colonoscopy = {code for code, row in CODES.items() if row.family is ct.SessionKind.COLONOSCOPY}
        self.assertEqual(evaluate.STOMA_ROUTE_CODES, {code for code in colonoscopy if 44388 <= code <= 44408})
        self.assertTrue(evaluate.STOMA_ROUTE_CODES)
        self.assertNotIn(44406, evaluate.STOMA_ROUTE_CODES)
        self.assertNotIn(44407, evaluate.STOMA_ROUTE_CODES)
        self.assertEqual(evaluate.ANUS_ROUTE_CODES, {code for code in colonoscopy if 45378 <= code <= 45398})
        self.assertEqual(sorted(evaluate.STOMA_ROUTE_CODES), [44388, 44389, 44390, 44391, 44392, 44394, 44401, 44402,
                                                              44403, 44404, 44405, 44408])
        self.assertEqual(sorted(evaluate.ANUS_ROUTE_CODES), [45378, 45379, 45380, 45381, 45382, 45384, 45385, 45386,
                                                             45388, 45389, 45390, 45393, 45398])

    def test_d310_1_a_through_stoma_code_is_ready_only_with_the_route_and_the_stoma_established(self):
        # every through-stoma code's route row over every approach and anatomy world: T exactly when the approach is
        # supported through_stoma AND an entry's type supported stoma; every other world holds (U) or explains (F)
        approaches = {'through_stoma': sup(ct.Approach.THROUGH_STOMA), 'transanal': sup(ct.Approach.TRANSANAL),
                      'through_stoma unresolved': unres(ct.Approach.THROUGH_STOMA, ct.Reason.GEOMETRY_SECTION),
                      'silent': None, 'through_stoma denied': neg(ct.Approach.THROUGH_STOMA)}
        entries = {'a stoma': sup(ct.AnatomyType.STOMA), 'a possible stoma': unres(ct.AnatomyType.STOMA),
                   'an anastomosis': sup(ct.AnatomyType.ANASTOMOSIS), 'no entry': None}
        seen = collections.Counter()
        for code in sorted(evaluate.STOMA_ROUTE_CODES):
            spec = evaluate._code(str(code))
            for (a_name, approach), (e_name, entry) in ((a, e) for a in approaches.items() for e in entries.items()):
                R = route_note(approach, entry).build()
                row = evaluate._row_colon_route(spec, (ct.Kind.EXAMINATION,), R, E1)
                ready = a_name == 'through_stoma' and e_name == 'a stoma'
                with self.subTest(code=code, approach=a_name, entry=e_name):
                    self.assertIs(row.truth is evaluate.Truth.T, ready)
                seen[row.truth.name] += 1
        self.assertGreater(seen['T'], 0)
        self.assertGreater(seen['U'], 0)
        self.assertGreater(seen['F'], 0)

    def test_s3_a_twin_whose_act_session_is_open_keeps_the_tables_own_hold_and_is_never_asked(self):
        # the D312 checker's route mutant S3 (the no-stoma hold dropped for an act whose session is open) survived with
        # no status effect: the twin stayed held by the session question alone - and that question then served the twin,
        # so a true session answer would be asked through a code no answer can release. The table's own hold stays,
        # and the planner serves no question to the twin
        R = EF.colonoscopy(session=unres(X1, ct.Reason.GEOMETRY_SECTION)).build()
        self.assertTrue(route_holds(R, '44394'))
        witnesses = [(witness.held.fact, witness.held.cause, witness.held.attribute, witness.held.subject)
                     for candidate in whatif.witnesses(R, '44394') if candidate.event == E2
                     for witness in candidate.witnesses]
        self.assertIn(('procedure', 'coding_rule:stoma_route', A.TYPE, E2), witnesses)
        self.assertIn(A.SESSION, [attribute for _fact, _cause, attribute, _subject in witnesses])
        plan = asking.plan(R, ())
        self.assertFalse([spec for spec in plan.specs if '44394' in plan.serves.get(spec.key, ())])
        self.assertTrue([spec for spec in plan.specs if '45385' in plan.serves.get(spec.key, ())])

    def test_s5_another_established_approach_explains_a_through_stoma_code_away(self):
        # the D312 checker's route mutant S5 (only a denied through_stoma fails a through-stoma code) survived with no
        # status effect: on an established transanal approach the twin stayed held, but by an approach QUESTION on an
        # established fact (and the anatomy hold) instead of the route table's explanation. The explanation is pinned
        R = route_note(sup(ct.Approach.TRANSANAL)).build()
        self.assertEqual(route_holds(R, '44394'), [('procedure', 'coding_rule:stoma_route', A.APPROACH, 'explanation')])
        denied = route_note(neg(ct.Approach.THROUGH_STOMA)).build()
        self.assertEqual(route_holds(denied, '44394'),
                         [('procedure', 'coding_rule:stoma_route', A.APPROACH, 'explanation')])


# --- (e) D323 F3: the fold reads no string ----------------------------------------------------------------------------


class FoldEnumTests(SimpleTestCase):
    def test_5_7_measure_4_finds_nothing_in_engine_facts(self):
        # tests.test_guard_static's own two guards (WordsNeverDecide, NoWordLists) over engine/facts.py: the port's fold
        # compared stored strings with nine string constants (D323 F3); int3 had none. Every pin they met is int3's
        from tests import test_guard_static as G
        source = (APP / 'studio' / 'interpretation' / 'engine' / 'facts.py').read_text(encoding='utf-8')
        used: set = set()
        self.assertEqual(G.words_never_decide(source, 'engine/facts', used), [])
        self.assertEqual(G.no_word_lists(source, 'engine/facts', G._design_values()), [])
        self.assertLessEqual({key[1] for key in used}, {'_pair_controls', '_lesion_pair_presumes',
                                                         '_act_lesion_presumes'})

    def test_the_families_the_fold_reads_are_the_planners(self):
        # one vocabulary: each family the fold reads is engine/asking.Family's, by value (settle stores the value)
        self.assertLessEqual({member.value for member in F.QuestionFamily}, {member.value for member in asking.Family})
        for shipped in (asking.Family.Q_REL, asking.Family.Q_FACT, asking.Family.Q_ONLESION, asking.Family.Q_ABSORB):
            self.assertEqual(F.QuestionFamily(shipped.value).value, shipped.value)
        self.assertEqual(F.QuestionSubject.DOCUMENT.value, 'document')

    def test_a_record_of_no_family_or_no_subject_the_fold_names_folds_nothing(self):
        R = without_not_on(qb(beyond=()))
        self.assertEqual(F._answered(R, {'questions': [onlesion_record('E4', 'L1')]}).off_lesion,
                         frozenset({(E4, L1)}))  # the positive control: the stored family read as its member
        for family in ('Q-ONLESION ', 'q-onlesion', 7, None, ['Q-ONLESION']):
            with self.subTest(family=family):
                R_q = F._answered(R, {'questions': [{**onlesion_record('E4', 'L1'), 'family': family}]})
                self.assertEqual((R_q.off_lesion, R_q.independent, R_q.distinct, R_q.absorbed, R_q.events),
                                 (frozenset(), frozenset(), frozenset(), frozenset(), R.events))
                self.assertNotEqual(target(R_q), INDEPENDENT)
        base = EF.colonoscopy(date=unres(ct.DateRelation.ON_DATE_OF_SERVICE, ct.Reason.GEOMETRY_SECTION)).build()
        record = {'family': 'Q-FACT', 'form': 'fact.date_relation', 'subjects': ['documents'], 'unlisted': None,
                  'attribute': 'date_relation', 'value': 'on_date_of_service', 'negated': False, 'result': 'supported',
                  'reasons': [], 'proof': []}
        self.assertEqual(F._answered(base, {'questions': [record]}).encounter, base.encounter)

    def test_the_lesion_forms_are_read_by_the_one_reading_of_a_lesion_pair_form(self):
        self.assertEqual(F._presumed('lesion.distinct_from', L1, L2), (L1, L2))
        self.assertEqual(F._presumed('lesion.not_member', L1, L2), (L2,))
        self.assertEqual(F._presumed('lesion.not_member.any', L1, L2), ())
        for form in ('lesion.distinct', 'act.not_on_lesion', None, 3):
            with self.subTest(form=form):
                self.assertIsNone(F._presumed(form, L1, L2))


# --- (f) D323 O1: b.3 reverted ----------------------------------------------------------------------------------------


class LesionPairRevertTests(SimpleTestCase):
    def test_a_fact_pass_lesion_pair_establishes_on_r_base_as_on_int3(self):
        # the must-change pin (D323 O1): the port's b.3 read every fact-pass lesion pair as not established (re-asked as
        # Q-LESION, which is not shipped); D296's pair establishes again, on R_base - L01's shape (tests/v2/
        # test_lesion_pair's note): the pair controls rejected, the two lesions apart
        from tests.v2 import test_lesion_pair as LP
        _claims, out = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle())
        fields = LP.row(LP.NOTE, out)
        R = F.factset(LP.view(LP.NOTE, fields))
        self.assertIsNone(R.base)
        self.assertTrue(any(value is True for key, value in R.pair_controls.items()
                            if key[1] is A.DISTINCT_FROM and key[0].family is IdFamily.LESION))
        self.assertTrue(F.apart_by_lesion(R, E4, E2))

    def test_a_pair_not_established_still_sets_nothing_apart(self):
        # the boundary: the pair's sameness control supported too (settle: incoherent, unresolved) - not established,
        # never apart
        from tests.v2 import test_lesion_pair as LP
        _claims, out = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle(control_value='supports'))
        R = F.factset(LP.view(LP.NOTE, LP.row(LP.NOTE, out)))
        self.assertFalse(any(value is True for key, value in R.pair_controls.items()
                             if key[1] is A.DISTINCT_FROM and key[0].family is IdFamily.LESION))
        self.assertFalse(F.apart_by_lesion(R, E4, E2))


class ControlledFieldTests(SimpleTestCase):
    def test_a_stored_rows_controlled_facts_reach_the_factset(self):
        # DECISIONS D323 F4 (the port's union mutant M2 - the prototype's ``controlled=`` dropped from the FactSet -
        # survived every test while the planner then drew no calibration item): facts.factset of a STORED row carries
        # the (subject, attribute) facts the fact pass established with their contrary control rejected, the
        # calibration pool's source (L01-shaped: tests/v2/test_lesion_pair's note through settle and the store)
        from tests.v2 import test_lesion_pair as LP
        _claims, out = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle())
        view = LP.view(LP.NOTE, LP.row(LP.NOTE, out))
        R = F.factset(view)
        self.assertEqual(R.controlled, F._controlled(F._events_of(view)))
        self.assertGreaterEqual(len(R.controlled), 20)
        self.assertLessEqual({(E2, A.KIND), (E2, A.STATUS), (E2, A.TARGET_LESION)}, R.controlled)


# --- (c) DESIGN-v2 f.2: P-MONO-Q over the readers this lane owns ------------------------------------------------------


class AnswerMonotoneTests(SimpleTestCase):
    """P-MONO-Q (DESIGN-v2 f.2) for the Q-ONLESION reading: each act-lesion fixture of tests/v2/test_properties with the
    fact pass's pair REPLACED by an established Q-ONLESION answer (through the fold, R_q over R_base) - every single 9.4
    weakening of the facts, the answer fixed, releases only what a ruling names (P-MONO's own check); removing the
    answer or demoting it never grows READY or EXCLUDED; and EXCLUDED is R_base's."""

    FIXTURES = ('ACT_LESION_FIXTURE', 'LISTED_FIXTURE', 'SINGLE_FIXTURE', 'QB_FIXTURE')

    def by_answer(self, R):
        stripped = replace(R, pair_controls={key: value for key, value in R.pair_controls.items()
                                             if not (key[1] is A.DISTINCT_FROM and key[0].family is IdFamily.EVENT)})
        records = [onlesion_record(str(key[0]), str(key[2])) for key, value in R.pair_controls.items()
                   if key[1] is A.DISTINCT_FROM and key[0].family is IdFamily.EVENT and value is True]
        return F._answered(stripped, {'questions': records}), records

    def test_p_mono_q_over_the_act_lesion_fixtures(self):
        TP = properties()
        named = []
        for name in self.FIXTURES:
            R0, codes = TP.fixture(getattr(TP, name))
            R_q, records = self.by_answer(R0)
            self.assertTrue(records, name)
            base = TP.assessed(R_q, codes)
            # the answer read as the pair was: the same outcome on every code
            self.assertEqual(TP.ready(base), TP.ready(TP.assessed(R0, codes)), name)
            self.assertEqual(TP.excluded(base), TP.excluded(TP.assessed(R_q.excluding, codes)), name)
            for label, changed, what in TP.weakenings(R_q.excluding):
                weak = F._answered(changed, {'questions': records})
                with self.subTest(fixture=name, weakening=label):
                    after = TP.assessed(weak, codes)
                    named += TP.PMonoTests.check(self, base, after, label, what, R_q)
                    self.assertEqual(TP.excluded(after), TP.excluded(TP.assessed(weak.excluding, codes)))
            for demoted in ([], [{**record, 'result': 'unresolved'} for record in records]):
                weaker = F._answered(R_q.excluding, {'questions': demoted})
                with self.subTest(fixture=name, answers=len(demoted)):
                    after = TP.assessed(weaker, codes)
                    self.assertLessEqual(TP.ready(after), TP.ready(base))
                    self.assertLessEqual(TP.excluded(after), TP.excluded(base))
        # the releases P-MONO's census names on these fixtures under the fact pass's pair, read here through the
        # answer: QB's umbrella deleted (D316_QB) and nothing else
        self.assertEqual(collections.Counter(named), {TP.D316_QB: 1})


# --- the repair pass (R3BE-RF1, R3BE-RF2): the fold re-checks every answer against the stored row ----------------------
#
# R3BE-RF1 (HIGH, a false READY): the question stage plans at the document's OWN date (derive with no member value) -
# for a note that states no date of service, none - so L1 demotes every act with a day literal to literal_unchecked and
# the planner asks its date relation; the answer was then folded over ANY open fact at the assessment, where the
# member's date demotes the act literal_mismatch: 45385 READY on an act whose own date words are another day. The
# class rule: an answer never lifts L1 (literal_unchecked and literal_mismatch are date checks, never readings), and the
# timing fact an answer establishes is re-judged by L1 on its stored literals at the FactSet's own effective date.
# R3BE-RF2 (MEDIUM): an answer re-asked a pair the fact pass judged in the holding direction (pair 4's shape: "This
# act was not done on lesion L1." contradicted, its control supported) and established_not_on read the answer anyway:
# 45381 READY. The class rule: no answer is folded over a reading the fact pass judged (C2b), in every family.

def dated_view(date_of_service=None, *, e2=None, questions=()):
    """tests/v2/test_facts.colonoscopy() kept to its examination E1 and its cold snare E2 - both on_date_of_service with
    the day literal 2026-11-09, inherited from the findings section N2 - the encounter's date of service
    ``date_of_service`` (silent by default: the document states none; given, the encounter's other dates dropped, as
    the finding's variant has them) and E2's date relation replaced by ``e2``: the finding's synthetic stored row,
    store.textfree_v2's view, with ``questions`` as events.questions."""
    from tests.v2 import test_facts as TF
    ev = TF.colonoscopy()
    ev['events'] = [item for item in ev['events'] if item['id'] in ('E1', 'E2')]
    # round r3's round 5 (DECISIONS D330 (1), lane rules6): the fixture's anastomosis files its subtype - with subtype and
    # joins both silent it is the D328 addendum's residual, which the lower-GI path guard now holds, so the date rule
    # would no longer be the scene's only hold; filed (ileocolic, as the development set files every anastomosis) it
    # matches the ruled harmless set and the date checks stay what this scene measures
    ev['anatomy'] = [{**ev['anatomy'][0], 'subtype': TF.fact('ileocolic', [TF.src(['S1'])])}]
    ev['encounter']['date_of_service'] = TF.silent() if date_of_service is None else date_of_service
    if date_of_service is not None:
        ev['encounter']['other_dates'] = []
    if e2 is not None:
        ev['events'][1]['date_relation'] = e2
    view = TF.view(ev)
    return {**view, 'questions': list(questions)} if questions else view


def several_dates():
    """The finding's variant: the document gives the encounter two dates (pass 1's contradicted date of service, both
    sides verified: 2026-11-09 at S2, 2026-11-04 at S10)."""
    from tests.v2 import test_facts as TF
    return TF.fact('', [TF.src(['S2']), TF.src(['S10'])], state='contradicted', result='contradicted',
                   reasons=['contradicted_by_pass1'], options=[{'value': '2026-11-09', 'sources': [TF.src(['S2'])]},
                                                               {'value': '2026-11-04', 'sources': [TF.src(['S10'])]}],
                   literals=[{'value': '2026-11-09', 'precision': 'day'}, {'value': '2026-11-04', 'precision': 'day'}])


def date_answer(subject: str, n: int = 1, value: str = 'on_date_of_service') -> dict:
    """One established Q-FACT date-relation answer as contract/settle stores it (claim supported with located proof,
    its exact negation rejected): "This act was done on the date of service." of ``subject``."""
    return {'id': f'q1.1.{n}', 'round': 1, 'batch': 1, 'family': 'Q-FACT', 'form': 'fact.date_relation',
            'subjects': [subject], 'unlisted': None, 'attribute': 'date_relation', 'value': value, 'negated': False,
            'census': 'F1', 'result': 'supported', 'reasons': [], 'held_by_answer': False,
            'proof': [{'start': 200 + n, 'end': 230 + n}, {'start': 100, 'end': 110}]}


ANSWERS = (date_answer('E1', 1), date_answer('E2', 2))


def member_assessed(view, member: str | None, code: str = '45385'):
    """(the effective date, ``code``'s status, E1's and E2's date relations on R_q) of ``view`` assessed as the stage's
    own call does (engine/assess.assess) at the effective date engine/derive gives with the member's service date
    ``member`` (member precedence; None: no member value), the proposal quoting E2's anchor unit (S6)."""
    import datetime
    from studio.interpretation.engine import assess as AS
    from studio.interpretation.engine import derive
    from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
    from tests.v2 import test_assess as TA
    from tests.v2 import test_facts as TF
    derived = derive.derive(view, {} if member is None else {'service_date': member})
    date = datetime.date.fromisoformat(derived.effective) if derived.effective else None
    unit = TF.unit_span(6)
    proposal = NormalizedResponse('corti', 'synthetic@1', codes=(ProviderCode(
        'selected', 'CPT', code, '', (EvidenceSpan(0, unit.start, unit.end, TF.TEXT[unit.start:unit.end], True),)),))
    out = AS.assess(inventory=view, date_of_service=date, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                    provider_status='succeeded', proposals=proposal, reference=TA.Lookup(), member=TA.ENTERED,
                    label=lambda session: str(session.id), participants=(), second=None, answers=())
    R = F.effective(view, date)
    relations = tuple((F.fact(R, event, A.DATE_RELATION).result.value,
                       tuple(reason.value for reason in F.fact(R, event, A.DATE_RELATION).reasons))
                      for event in (E1, E2))
    return date, {item.code: item.status.value for item in out.codes}[code], relations


MISMATCH = ('unresolved', ('literal_mismatch',))
UNCHECKED = ('unresolved', ('literal_unchecked',))
SUPPORTED = ('supported', ())


class DateCheckFoldTests(SimpleTestCase):
    """R3BE-RF1: an answer never lifts a demotion the assessment's own effective date makes, and every answered timing
    fact is re-judged by L1 on its stored literals at the FactSet's effective date."""

    def test_rf1_the_findings_input_is_held_at_the_members_date(self):
        # the finding's input (refute/probes/r03_date_member.py, r03b_date_assess.py): the note states no date of
        # service, so the stage planned at no effective date - E1 and E2 literal_unchecked - and both date-relation
        # questions were established; the member then supplies 2026-11-08 (or 11-10): the acts' own day literal is
        # 2026-11-09, so 45385 stays held and the answers lift nothing; the port's fold made 45385 READY
        for member in ('2026-11-08', '2026-11-10'):
            with self.subTest(member=member):
                without = member_assessed(dated_view(), member)
                found = member_assessed(dated_view(questions=ANSWERS), member)
                self.assertEqual(without[1:], ('needs_clarification', (MISMATCH, MISMATCH)))
                self.assertEqual(found, without)

    def test_rf1_its_variant_two_document_dates_the_member_settles_on_the_other(self):
        # refute/probes/r03c_date_several.py: the member settles on 2026-11-04, the document's other date - held
        found = member_assessed(dated_view(several_dates(), questions=ANSWERS), '2026-11-04')
        self.assertEqual(found[1:], ('needs_clarification', (MISMATCH, MISMATCH)))
        self.assertEqual(found, member_assessed(dated_view(several_dates()), '2026-11-04'))

    def test_rf1_no_answer_lifts_literal_unchecked_without_a_date_of_service(self):
        # no member value: L1 cannot check the day literal; the answers do not lift it (R7 holds the code besides)
        found = member_assessed(dated_view(questions=ANSWERS), None)
        self.assertEqual(found, (None, 'needs_clarification', (UNCHECKED, UNCHECKED)))

    def test_the_boundary_the_acts_own_date_is_the_members(self):
        # the member supplies the acts' own date: L1 passes, the facts are established without any answer - READY,
        # the answers neither needed nor read (an established fact is never re-answered)
        for questions in ((), ANSWERS):
            with self.subTest(answers=len(questions)):
                self.assertEqual(member_assessed(dated_view(questions=questions), '2026-11-09')[1:],
                                 ('ready', (SUPPORTED, SUPPORTED)))

    def rejudged(self, e2, *, held_without: bool = True):
        """E2's date relation ``e2`` (never established, so L1 never judged it) answered "on the date of service":
        on R_q it is established only where L1 passes on the literals E2's own read records, at the assessment's date
        - never at 11-08 (the literal 2026-11-09 fails it) nor with no date (the day literal unchecked), at 11-09 it
        is, and 45385 is READY there by the answer alone."""
        open_ = ('unresolved', ('unappraised',))
        for member, relation in (('2026-11-08', open_), (None, open_), ('2026-11-09', SUPPORTED)):
            with self.subTest(member=member):
                self.assertEqual(member_assessed(dated_view(e2=e2, questions=ANSWERS[1:]), member)[2][1], relation)
        self.assertEqual(member_assessed(dated_view(e2=e2, questions=ANSWERS[1:]), '2026-11-09')[1], 'ready')
        if held_without:
            self.assertEqual(member_assessed(dated_view(e2=e2), '2026-11-09')[1:],
                             ('needs_clarification', (SUPPORTED, open_)))

    def test_an_answered_timing_fact_is_rejudged_on_its_own_literals(self):
        # E2's date relation filed with its own day literal but never appraised (F4, unappraised: the stage asks it -
        # the verifier's probe v03): the port folded the answer at any date, so 45385 was READY at 11-08
        from tests.v2 import test_facts as TF
        self.rejudged(TF.fact('on_date_of_service', [TF.src(['S2'], 'document_frame')], literals=TF.DAY,
                              inherited_from='N2'))

    def test_an_inherited_date_relation_is_rejudged_on_its_sections_literals(self):
        # the same act storing no literal of its own: L1 reads its section's occasion literals (D193), and so does the
        # fold - the very literals E2's own read recorded
        from tests.v2 import test_facts as TF
        self.rejudged(TF.fact('on_date_of_service', [TF.src(['S2'], 'document_frame')], inherited_from='N2'))

    def test_the_boundary_a_date_relation_no_date_words_fix_is_answered_at_any_date(self):
        # no literal and no section: L1 has nothing to judge (as for an established fact with none), so the answer
        # establishes it at every date - the rule only ever reads the act's own date words
        from tests.v2 import test_facts as TF
        e2 = TF.fact('on_date_of_service', [TF.src(['S6'])])
        for member in ('2026-11-08', None, '2026-11-09'):
            with self.subTest(member=member):
                self.assertEqual(member_assessed(dated_view(e2=e2, questions=ANSWERS[1:]), member)[2][1], SUPPORTED)

    def test_no_answer_is_folded_over_an_l1_demotion_whatever_its_value(self):
        # literal_mismatch and literal_unchecked on the base fact refuse the answer before any value is read - even a
        # value L1 would pass on the same literals (a check failure is never asked: "L1's demotions are date checks")
        base = EF.colonoscopy(date=unres(ct.DateRelation.EARLIER_DATE, ct.Reason.LITERAL_MISMATCH)).build()
        for reason in (ct.Reason.LITERAL_MISMATCH, ct.Reason.LITERAL_UNCHECKED):
            for value in ('on_date_of_service', 'earlier_date'):
                with self.subTest(reason=reason, value=value):
                    R = EF.colonoscopy(date=unres(ct.DateRelation.EARLIER_DATE, reason)).build()
                    R_q = F._answered(R, {'questions': [date_answer('E2', value=value)]})
                    self.assertEqual(F.fact(R_q, E2, A.DATE_RELATION), F.fact(R, E2, A.DATE_RELATION))
        self.assertIs(F.fact(base, E2, A.DATE_RELATION).result, ct.Result.UNRESOLVED)


def performer_answer(subject: str = 'E2', value: str = 'documenting_team') -> dict:
    """An established Q-FACT performer answer ("This act was done by the documenting clinician or a member of their
    team."), as contract/settle stores it."""
    return {**date_answer(subject), 'form': 'fact.performer', 'attribute': 'performer', 'value': value}


# Every reason a stored fact may carry, by what the fold does with an answer over it (R3BE-RF1, R3BE-RF2; an owner pin:
# a reason contract/types.Reason gains must be classified here before any answer is folded over it on purpose).
JUDGED_REASONS = frozenset({
    ct.Reason.APPRAISAL_CONTRADICTS, ct.Reason.APPRAISAL_UNCLEAR, ct.Reason.CONTROL_INCOHERENT,
    ct.Reason.APPRAISAL_QUALIFIED, ct.Reason.APPRAISAL_QUALIFIED_HEDGED, ct.Reason.APPRAISAL_QUALIFIED_CONDITIONAL,
    ct.Reason.APPRAISAL_QUALIFIED_REPORTED, ct.Reason.APPRAISAL_QUALIFIED_PARTIAL, ct.Reason.APPRAISAL_QUALIFIED_NAMED_ONLY,
    ct.Reason.APPRAISAL_QUALIFIED_RESTATEMENT_ONLY, ct.Reason.APPRAISAL_QUALIFIED_REFERENCE_ONLY,
    ct.Reason.APPRAISAL_QUALIFIED_APPROXIMATE, ct.Reason.APPRAISAL_QUALIFIED_NEGATED_CONTEXT,
    ct.Reason.APPRAISAL_QUALIFIED_OTHER_OCCASION, ct.Reason.APPRAISAL_QUALIFIED_OTHER_PERFORMER,
    ct.Reason.APPRAISAL_QUALIFIED_OTHER_ENTRY, ct.Reason.APPRAISAL_QUALIFIED_OTHER_TARGET,
    ct.Reason.APPRAISAL_QUALIFIED_OTHER_ACT, ct.Reason.APPRAISAL_QUALIFIED_SCOPE_LIMITED,
    ct.Reason.APPRAISAL_QUALIFIED_PLANNED_ONLY, ct.Reason.APPRAISAL_QUALIFIED_HISTORY_ONLY})  # C2b: 21
# DECISIONS D324 (4) (round r3c's fold lane; was L1's two date checks alone): every fixed-table check - L1's date
# checks, K3's reach, K2's session consistency, K1's fourteen structure rules and K4's absent organ (facts.FIXED_TABLE)
FIXED_TABLE_REASONS = frozenset({
    ct.Reason.LITERAL_MISMATCH, ct.Reason.LITERAL_UNCHECKED, ct.Reason.SESSION_UNREACHABLE,
    ct.Reason.SESSION_INCONSISTENT, ct.Reason.ANATOMY_CONFLICT, ct.Reason.STRUCTURE_SCOPE, ct.Reason.STRUCTURE_YIELD,
    ct.Reason.STRUCTURE_ACCESS_OUTCOME, ct.Reason.STRUCTURE_CAUSE, ct.Reason.STRUCTURE_PART_OF,
    ct.Reason.STRUCTURE_ENDOSCOPIC, ct.Reason.STRUCTURE_VISIT, ct.Reason.STRUCTURE_OTHER_CLASS,
    ct.Reason.STRUCTURE_STATUS_TIME, ct.Reason.STRUCTURE_EXCEPTIVE, ct.Reason.STRUCTURE_LISTED_TARGETS,
    ct.Reason.STRUCTURE_SINGLE_TARGET, ct.Reason.STRUCTURE_SEGMENT, ct.Reason.STRUCTURE_UMBRELLA})  # 19
REFUSED = JUDGED_REASONS | FIXED_TABLE_REASONS | {ct.Reason.ANCHOR_INVALID}  # C4
REASONS_PINNED = 81
# pass 1's contradiction (C1: refused), the act unlocated (C4: refused), a cross-object conflict (C6: answered)
_CONTRADICTED = EF.fact(ct.Result.CONTRADICTED, ct.Performer.DOCUMENTING_TEAM, ct.FactState.CONTRADICTED,
                        reasons=(ct.Reason.CONTRADICTED_BY_PASS1,))
CONTRADICTIONS = ((_CONTRADICTED, False), (unres(ct.Performer.DOCUMENTING_TEAM, ct.Reason.ANCHOR_INVALID), False),
                  (replace(_CONTRADICTED, reasons=(ct.Reason.CONTRADICTED_BY_PASS1, ct.Reason.PERSON_CONFLICT)), True))


class AnswerablePredicateTests(SimpleTestCase):
    """facts.answerable, the one reading the fold gives a Q-FACT answer's base fact: exactly the facts the question stage
    may ask (asking's census: not established, no pass-1 contradiction but a conflict, not judged by the fact pass,
    located) less the fixed-table checks (DECISIONS D324 (4): L1's date checks, K3, K2, K1, K4), for every attribute - a
    timing fact or not."""

    def test_every_reason_is_classified(self):
        # the owner pin, through the fold: every Reason member, as the one reason of E2's unresolved performer, is folded
        # over or refused exactly as REFUSED says; a new member fails here first (REASONS_PINNED), never silently
        # answerable
        self.assertEqual(len(ct.Reason), REASONS_PINNED)
        refused = set()
        for reason in ct.Reason:
            R = EF.colonoscopy(performer=unres(ct.Performer.DOCUMENTING_TEAM, reason)).build()
            if not F.established(F.fact(F._answered(R, {'questions': [performer_answer()]}), E2, A.PERFORMER)):
                refused.add(reason)
        self.assertEqual(refused, REFUSED)

    def test_the_predicate_and_its_sets(self):
        # the one predicate the fold reads, and its named sets: facts.answerable refuses exactly REFUSED as one reason
        # of an unresolved fact; JUDGED, the fixed-table checks and the anchor make it up (DECISIONS D324 (4), round
        # r3c's fold lane: was JUDGED | DATE_CHECKS | anchor, and CONFLICTS held K4's anatomy_conflict)
        self.assertEqual({reason for reason in ct.Reason
                          if not F.answerable(unres(ct.Performer.DOCUMENTING_TEAM, reason))}, REFUSED)
        self.assertEqual(F.JUDGED, JUDGED_REASONS)
        self.assertEqual(F.FIXED_TABLE, FIXED_TABLE_REASONS)
        self.assertLessEqual(F.DATE_CHECKS, F.FIXED_TABLE)
        self.assertEqual(F.JUDGED | F.FIXED_TABLE | {ct.Reason.ANCHOR_INVALID}, REFUSED)
        self.assertEqual(F.CONFLICTS, frozenset({ct.Reason.PERSON_CONFLICT, ct.Reason.INSTRUMENT_CONFLICT,
                                                 ct.Reason.SESSION_CONFLICT}))

    def test_the_judged_reasons_are_every_appraisal_reason_but_no_usable_verdict(self):
        # one source: JUDGED is engine/questions.APPRAISAL_CAUSES' reasons less C2a's two (missing, detached) - the
        # planner's own C2b reads the same table - and every reason contract/settle.appraise gives over every verdict
        # pattern is JUDGED or C2a's; DATE_CHECKS is contract/settle.LITERAL_REASONS
        import itertools
        from studio.interpretation.contract import settle
        from studio.interpretation.engine import questions
        c2a = {ct.Reason.APPRAISAL_MISSING, ct.Reason.APPRAISAL_DETACHED}
        self.assertEqual(JUDGED_REASONS, frozenset(questions.APPRAISAL_CAUSES) - c2a)
        self.assertLessEqual(c2a, set(questions.APPRAISAL_CAUSES))
        given = set()
        for value, qualifiers, attached, evidence, controlled, control in itertools.product(
                (*ct.VerdictValue, None), ((), (ct.Qualifier2.APPROXIMATE,), *((q,) for q in ct.Qualifier2)),
                ct.Attached, (True, False), (True, False), (*ct.VerdictValue, None)):
            verdict = None if value is None else ct.Verdict(claim='K1', verdict=value, attached=attached,
                                                             qualifiers=qualifiers, evidence=('S1',))
            given |= set(settle.appraise(verdict, evidence, controlled, control)[1])
        self.assertEqual(given - c2a, set(JUDGED_REASONS))
        self.assertEqual(F.JUDGED, JUDGED_REASONS)
        self.assertEqual(F.DATE_CHECKS, settle.LITERAL_REASONS)
        self.assertEqual(F.PAIR_ASKABLE, frozenset(c2a | {ct.Reason.UNAPPRAISED}))

    def test_no_answer_is_folded_over_a_judged_fact_of_any_attribute(self):
        # R3BE-RF2's class on a Q-FACT: the fact pass judged E2's performer (each C2b reason); the answer folds nothing,
        # a timing fact or not; the boundary, a fact with no usable verdict (C2a) or never appraised (F4), is answered
        for reason in sorted(JUDGED_REASONS | {ct.Reason.APPRAISAL_MISSING, ct.Reason.APPRAISAL_DETACHED,
                                               ct.Reason.UNAPPRAISED}, key=lambda item: item.value):
            with self.subTest(reason=reason):
                R = EF.colonoscopy(performer=unres(ct.Performer.DOCUMENTING_TEAM, reason),
                                   date=unres(ct.DateRelation.ON_DATE_OF_SERVICE, reason)).build()
                R_q = F._answered(R, {'questions': [performer_answer(), date_answer('E2')]})
                answered = reason not in JUDGED_REASONS
                for attribute in (A.PERFORMER, A.DATE_RELATION):
                    self.assertIs(F.established(F.fact(R_q, E2, attribute)), answered, attribute)

    def test_no_answer_is_folded_over_a_pass_1_contradiction_or_an_unlocated_act_but_a_conflict_is(self):
        for found, answered in CONTRADICTIONS:
            with self.subTest(reasons=found.reasons):
                R = EF.colonoscopy(performer=found).build()
                R_q = F._answered(R, {'questions': [performer_answer()]})
                self.assertIs(F.established(F.fact(R_q, E2, A.PERFORMER)), answered)

    def test_the_predicate_reads_a_contradiction_and_an_anchor_as_the_fold_does(self):
        for found, answered in CONTRADICTIONS:
            with self.subTest(reasons=found.reasons):
                self.assertIs(F.answerable(found), answered)

    def test_a_judged_list_member_is_never_answered_and_a_value_no_member_names_is(self):
        # a multi-valued slot: the member AT the answered value is read; a value the list does not name is appended
        judged = EF.colonoscopy(places=[unres(LM.SIGMOID_COLON, ct.Reason.APPRAISAL_UNCLEAR)]).build()
        record = {**date_answer('E2'), 'form': 'fact.target.places', 'attribute': 'target.places',
                  'value': 'sigmoid_colon'}
        self.assertEqual(F.members(F._answered(judged, {'questions': [record]}), E2, A.TARGET_PLACES),
                         F.members(judged, E2, A.TARGET_PLACES))
        added = F.members(F._answered(judged, {'questions': [{**record, 'value': 'rectum'}]}), E2, A.TARGET_PLACES)
        self.assertEqual([(member.value, member.result) for member in added],
                         [(LM.SIGMOID_COLON, ct.Result.UNRESOLVED), (LM.RECTUM, ct.Result.SUPPORTED)])


def p4_view(oracle=None, *, questions=(), act_lesions=None):
    """Pair 4's shape end to end (tests/v2/test_r2el_lesion's P4: the denial E3 on L1, the tattoo E4 naming no lesion)
    through pass 2 by ``oracle`` (faithful by default), settle and the store - its text-free view, with ``questions``
    as events.questions and, given, ``act_lesions`` as the stored act-lesion records."""
    from tests.v2 import test_r2el_lesion as EL
    _claims, _out, _R, view = EL.run(EL.P4, EL.p4_answer(), EL.FAITHFUL if oracle is None else oracle)
    over = {}
    if questions:
        over['questions'] = list(questions)
    if act_lesions is not None:
        over['act_lesions'] = list(act_lesions)
    return {**view, **over} if over else view


def p4_status(view, code: str = '45381') -> str:
    """``code``'s status assessed on ``view`` as the stage does, proposed on its own sentence."""
    import datetime
    from studio import jobs
    from studio.interpretation.engine import assess as engine_assess
    from studio.interpretation.engine import derive
    from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
    from tests.v2 import test_lesion_pair as LP
    from tests.v2 import test_r2el_lesion as EL
    quote = dict(EL.P4_CODES)[code]
    at = EL.P4.index(quote)
    effective = derive.derive(view, {}).effective
    found = engine_assess.assess(
        inventory=view, date_of_service=datetime.date.fromisoformat(effective) if effective else None, text=EL.P4,
        pages=(), integrity=jobs._Integrity(), provider_status='succeeded', proposals=NormalizedResponse(
            'replay', 'test@1', (ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                              (EvidenceSpan(0, at, at + len(quote), quote, True),)),)),
        reference=LP._NoReference(), member=engine_assess.MemberContext(), label=lambda session: str(session.id))
    return {item.code: item.status.value for item in found.codes}[code]


def act_lesion_oracle(claim, control):
    """Pass 2 answering the act-lesion claim ("This act was not done on lesion L1.") by ``claim`` and its control by
    ``control`` - each a verdict dict maker over test_settle.verdict, or None for no verdict - every other claim
    faithfully."""
    from tests.v2 import test_r2el_lesion as EL
    from tests.v2.test_settle import faithful

    def oracle(item, role, claim_set):
        pairs = EL.acts_of(claim_set)
        for make, found in ((claim, {pair.claim for pair in pairs}), (control, {pair.control for pair in pairs})):
            if item.id in found:
                return None if make is None else make(item)
        return faithful(item, role, claim_set)
    return oracle


def said(value, **over):
    from tests.v2.test_settle import verdict
    return lambda claim: verdict(claim, value, **over)


ONLESION = onlesion_record('E4', 'L1')


class JudgedPairFoldTests(SimpleTestCase):
    """R3BE-RF2: no answer is folded over a reading the fact pass judged - Q-ONLESION and Q-LESION by the pair's stored
    records, Q-REL by its covers claim, Q-FACT by the fact (AnswerablePredicateTests)."""

    def outcome(self, view):
        R = F.factset(view)
        return F.established_not_on(R, E4, L1), target(R, E3, E4), p4_status(view)

    def test_rf2_the_findings_input_is_held(self):
        # the finding's input (refute/probes/r09_onlesion_c2b.py): pass 2 CONTRADICTED "This act was not done on lesion
        # L1." and SUPPORTED its control - the fact pass judged the tattoo done on L1 (C2b); the planner re-asked it as
        # Q-ONLESION and an established answer made 45381 READY through established_not_on's OR. Held now, as without
        # the answer
        view = p4_view(act_lesion_oracle(said('contradicts'), said('supports')))
        self.assertEqual([(item['act'], item['lesion'], item['result'], item['reasons'])
                          for item in view['act_lesions']], [('E4', 'L1', 'unresolved', ['appraisal_contradicts'])])
        held = (False, SAME, 'needs_clarification')
        self.assertEqual(self.outcome(view), held)
        self.assertEqual(self.outcome({**view, 'questions': [ONLESION]}), held)

    def test_every_judgment_the_fact_pass_makes_of_the_pair_refuses_the_answer(self):
        # each holding-direction or abstaining verdict pattern of 3.2.3's table: the claim unclear, qualified,
        # contradicted with its control contradicted too (uninformative), both supported (incoherent)
        for name, claim, control in (('unclear', said('unclear'), said('contradicts')),
                                     ('qualified', said('qualified', qualifiers=['hedged']), said('contradicts')),
                                     ('uninformative', said('contradicts'), said('contradicts')),
                                     ('incoherent', said('supports'), said('supports'))):
            with self.subTest(pattern=name):
                view = p4_view(act_lesion_oracle(claim, control))
                self.assertEqual(view['act_lesions'][0]['result'], 'unresolved')
                self.assertTrue(set(view['act_lesions'][0]['reasons']) <= {reason.value for reason in JUDGED_REASONS})
                self.assertEqual(self.outcome({**view, 'questions': [ONLESION]}), (False, SAME, 'needs_clarification'))

    def test_the_boundary_a_pair_with_no_usable_verdict_or_never_asked_is_answered(self):
        # C2a (the claim's verdict missing, or detached; the control's missing) and a pair dropped for the bound
        # (unappraised): no judgment of the fact pass - the answer releases 45381 exactly as the established pair does
        self.assertEqual(self.outcome(p4_view()), (True, INDEPENDENT, 'ready'))
        for name, claim, control in (('claim missing', None, said('contradicts')),
                                     ('claim detached', said('supports', attached='no'), said('contradicts')),
                                     ('control missing', said('supports'), None)):
            with self.subTest(pattern=name):
                view = p4_view(act_lesion_oracle(claim, control))
                self.assertTrue(set(view['act_lesions'][0]['reasons']) <= {'appraisal_missing', 'appraisal_detached'})
                self.assertEqual(self.outcome(view)[2], 'needs_clarification')
                self.assertEqual(self.outcome({**view, 'questions': [ONLESION]}), (True, INDEPENDENT, 'ready'))
        dropped = p4_view(act_lesion_oracle(None, None))
        dropped = {**dropped, 'act_lesions': [{**dropped['act_lesions'][0], 'reasons': ['unappraised']}]}
        self.assertEqual(F._answered(F.factset(dropped), {**dropped, 'questions': [ONLESION]}).off_lesion,
                         frozenset({(E4, L1)}))

    def test_p_mono_q_the_judged_pairs_answer_is_inert_under_every_weakening(self):
        # DESIGN-v2 f.2 for this reading: with the stored records and the answer fixed, under every single 9.4
        # weakening of the facts (tests/v2/test_properties.weakenings - its "pair control ... not rejected" included) the
        # answer over the judged pair decides 45381 and the pair's target row exactly as the weakened row without it
        # does: no weakening makes the refusal fall through to a release
        TP = properties()
        view = p4_view(act_lesion_oracle(said('contradicts'), said('supports')))
        events = {**view, 'questions': [ONLESION]}
        base = F.factset(view)
        weakened = 0
        for label, changed, _what in TP.weakenings(base):
            with self.subTest(weakening=label):
                R_q = F._answered(changed, events)
                self.assertEqual(R_q.off_lesion, frozenset())
                self.assertEqual(held_causes(R_q, '45381'), held_causes(changed, '45381'))
                self.assertEqual(target(R_q), target(changed))
                weakened += 1
        self.assertGreater(weakened, 20)

    def test_every_asking_of_the_pair_is_read(self):
        # one pair asked twice, once without a usable verdict and once judged: judged (fail-closed, as _act_lesions
        # establishes a pair only when every asking did)
        view = p4_view(act_lesion_oracle(said('contradicts'), said('supports')))
        missing = {**view['act_lesions'][0], 'result': 'unresolved', 'reasons': ['appraisal_missing']}
        for records in ([missing, view['act_lesions'][0]], [view['act_lesions'][0], missing]):
            with self.subTest(first=records[0]['reasons']):
                self.assertEqual(self.outcome({**view, 'act_lesions': records, 'questions': [ONLESION]})[:2],
                                 (False, SAME))

    def test_a_pair_held_unestablished_with_no_record_to_say_why_is_judged(self):
        # refute/probes/r04_onlesion_reask.py's input: pair 4's shape where the fact pass's act-lesion pair is held
        # unestablished (pair_controls False) - with no stored record the fold cannot tell C2a from C2b, so it refuses
        R = replace(qb(beyond=()), pair_controls={**qb(beyond=()).pair_controls, (E4, A.DISTINCT_FROM, L1): False})
        R_q = F._answered(R, {'questions': [ONLESION]})
        self.assertEqual(R_q.off_lesion, frozenset())
        self.assertIs(F.established_not_on(R_q, E4, L1), False)
        self.assertEqual(held_causes(R_q, '45381'), ['relation:contradiction'])
        # the boundary: never asked (no key, no record) is answered (OnlesionArmTests' fold pin)
        self.assertEqual(F._answered(without_not_on(R), {'questions': [ONLESION]}).off_lesion, frozenset({(E4, L1)}))

    def test_a_q_lesion_answer_over_a_lesion_pair_the_fact_pass_judged_is_refused(self):
        # Q-LESION (not planned in this build, D323 O1; the fold still reads it): the lesion pair's stored record, in
        # either order, carrying a judgment refuses the answer; no usable verdict (C2a) or unappraised does not
        doc = EF.colonoscopy()
        doc.lesions[Id.parse('L1')][A.MULTIPLICITY] = (sup(ct.Multiplicity.SINGLE),)
        doc.lesion(2, lesion_places=[sup(LM.RECTUM)], multiplicity=sup(ct.Multiplicity.SINGLE))
        R = doc.build()
        record = {'family': 'Q-LESION', 'form': 'lesion.distinct_from', 'subjects': ['L1', 'L2'], 'unlisted': None,
                  'attribute': 'distinct_from', 'value': 'L2', 'negated': False, 'result': 'supported',
                  'reasons': [], 'proof': [{'start': 1, 'end': 20}]}
        for order in (('L1', 'L2'), ('L2', 'L1')):
            for reasons, distinct in ((['appraisal_unclear'], frozenset()), (['control_incoherent'], frozenset()),
                                      (['appraisal_missing'], frozenset({(L1, L2)})),
                                      (['unappraised'], frozenset({(L1, L2)}))):
                with self.subTest(order=order, reasons=reasons):
                    pairs = [{'lesion': order[0], 'other': order[1], 'claim': None, 'control': None,
                              'result': 'unresolved', 'reasons': reasons}]
                    found = F._answered(R, {'questions': [record], 'lesion_pairs': pairs})
                    self.assertEqual(found.distinct, distinct)
        self.assertEqual(F._answered(R, {'questions': [record]}).distinct, frozenset({(L1, L2)}))  # never asked

    def test_a_q_rel_answer_never_sets_apart_a_pair_whose_covers_claim_the_fact_pass_established(self):
        # Q-REL's C2b: "this statement does not concern act A" is never folded over the fact pass's established "this
        # statement covers act A" (asking's C7a); a covers claim the fact pass did not establish (C7b-other) is
        # answered
        record = {'family': 'Q-REL', 'form': 'rel', 'subjects': ['E3', 'E2'], 'unlisted': None, 'attribute': None,
                  'value': '', 'negated': False, 'result': 'supported', 'reasons': [], 'proof': [{'start': 1, 'end': 9}]}
        for covers, independent in ((sup(E2), frozenset()), (unres(E2, ct.Reason.APPRAISAL_UNCLEAR), {(E3, E2)}),
                                    (unres(E2, ct.Reason.UNAPPRAISED), {(E3, E2)})):
            with self.subTest(covers=covers.result):
                doc = EF.colonoscopy()
                doc.event(3, kind=sup(ct.Kind.EXAMINATION), status=sup(ct.Status.PLANNED), session=sup(X1),
                          covers=[covers])
                R_q = F._answered(doc.build(), {'questions': [record]})
                self.assertEqual(R_q.independent, frozenset(independent))
