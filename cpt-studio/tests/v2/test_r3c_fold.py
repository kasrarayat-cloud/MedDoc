"""Round r3's repair lane "fold" (DECISIONS D324 (1) and (4)): engine/facts.py's fold of the established question answers.
SYNTHETIC scenes only (tests/v2/evaluate_fixtures' builders: ids, enumeration members, integer spans); no document is
read and nothing is sent.

D324 (1), a negation answer removes only its value (findings L2-1, L2-2, L6-1):
- NegationFindingTests: each finding's own input - the real plan's question, the answer as settle stores it, the fold,
  and the codes - RED on int4 (an established negation with no options read as "no value at all").
- NegationVariantTests: other forms, values, sessions and shapes, and the boundaries the rule leaves alone.
- NegationPropertyTests: for every negated form, every base shape and every value w other than the answered v, every
  reader reads the answered fact on R_q exactly as on R_base - facts.possibly and the readers built on it, coverage,
  classes, combination and the pair readers - and the codes whose witnesses rest on w only are decided alike.
D324 (4), no answer lifts a fixed-table check (finding L1-02):
- FixedTableFindingTests: K3's session_unreachable never asked and never folded; a silent session answered into a
  family that cannot reach the act's place, or a place answered beyond its session's reach, is never folded.
- RecheckTests: every other fixed-table check re-run on an answered fact (K2, K4, K1's rules), the checks this module
  cannot re-run whole refusing their facts, and the boundaries (a reachable session or place is folded).
- ReasonTableTests: the typed table over the Reason enum classifies every member, a member it does not name is a
  fixed-table check, and every fixed-table reason has its re-check.
"""
from __future__ import annotations

import datetime
from dataclasses import replace
from types import MappingProxyType
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, classes, combination, coverage, evaluate, pairing, whatif
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import FactSet, IsoDate, Outcome
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA

A = ct.Attribute
Kind, Status, SessionKind, Landmark, Extent = ct.Kind, ct.Status, ct.SessionKind, ct.Landmark, ct.Extent
P, C, R_ = ct.Purpose, ct.Cause, ct.Reason
sup, neg, unres, doubted, X, E, L, Y = EF.sup, EF.neg, EF.unres, EF.doubted, EF.X, EF.E, EF.L, EF.Y
ON, TEAM, DC = EF.ON, EF.TEAM, EF.DC
DAY = datetime.date(2026, 11, 9)


def dated(R: FactSet) -> FactSet:
    """``R`` with its encounter's date of service supported before any answer is folded (R_q and R_base share it)."""
    return replace(R, encounter={A.DATE_OF_SERVICE: (sup(IsoDate(DAY, ct.Precision.DAY)),)})


def record(spec_or_subject, attribute=None, value='', negated=False, form='', family='Q-FACT', result='supported',
           reasons=()) -> dict:
    """A question record as contract/settle stores it in events.questions (the fields the fold reads): from a planned
    QuestionSpec, or from a subject id and the answered attribute and value."""
    if isinstance(spec_or_subject, asking.QuestionSpec):
        spec = spec_or_subject
        return {'family': spec.family.value, 'form': spec.form, 'subjects': list(spec.subjects),
                'attribute': spec.attribute.value if spec.attribute else None, 'value': spec.value,
                'unlisted': asking.unlisted_index(spec.subjects), 'negated': spec.negated, 'result': result,
                'reasons': list(reasons), 'proof': [{'start': 200, 'end': 230}]}
    return {'family': family, 'form': form, 'subjects': [str(spec_or_subject)],
            'attribute': attribute.value if attribute is not None else None, 'value': value, 'unlisted': None,
            'negated': negated, 'result': result, 'reasons': list(reasons), 'proof': [{'start': 200, 'end': 230}]}


def _raw(value) -> str:
    """A value as the stored record writes it: an enumeration member's value, an id's or a date's own string."""
    return str(value) if isinstance(value, EF.Id) else value.value


def not_in(subject, session) -> dict:
    """An established G1 answer: "This act was not done during session {X}." (fact.session.not)."""
    return record(subject, A.SESSION, str(session), True, 'fact.session.not')


def negation(subject, attribute, value, form) -> dict:
    return record(subject, attribute, _raw(value), True, form)


def answer(subject, attribute, value, form='') -> dict:
    return record(subject, attribute, _raw(value), False, form or f'fact.{attribute.value}')


def fold(R: FactSet, *records) -> FactSet:
    return F._answered(R, {'questions': list(records)})


def codes(R: FactSet, *proposals) -> dict:
    """Each proposed code's (status, held facts, the item and question the reviewer is shown) through engine/assess
    (tests/v2/test_assess.run)."""
    found = TA.by_code(TA.run(R, *proposals))
    return {code: (item.status, frozenset((held.fact, held.cause, str(held.subject), held.reason)
                                          for held in item.held_facts), item.item, item.question)
            for code, item in found.items()}


def decided(R: FactSet, code: str) -> tuple:
    """evaluate.decide's witnesses of ``code`` (no evidence kept): its held facts - each witness once, whichever
    candidate's row raised it first - whether it is excluded, and its supporting acts. (Which candidate an item names
    is RANK's choice over the candidates' unmet rows: an answer that releases one candidate's witnesses about v may move
    it, and no witness about another value moves.)"""
    found = evaluate.decide(code, (), R)
    return (frozenset((held.fact, held.cause, str(held.subject), held.attribute, held.result, held.reason)
                      for held in found.held_facts), found.exclusion is not None, tuple(found.supporting))


def g1_specs(plan) -> dict:
    return {spec.value: spec for spec in plan.specs if spec.census == 'G1'}


# --- D324 (1): the findings' own inputs ---------------------------------------------------------------------------------


def l2_1_scene() -> FactSet:
    """L2-1 (and the attacker's G1CrossSessionTests): tests/v2/test_assess.two_sessions - a colonoscopy X1 (E1 exam, E2
    snare, E3 biopsy) and an EGD X2 (E4 exam, E5 biopsy) - and E6, an examination done today in the documenting
    clinician's own entry whose session and performer pass 1 left silent: it may be X1's or X2's examination, and it
    fails row 4, so row 7 holds every code of both sessions."""
    doc = TA.two_sessions()
    doc.event(6, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=F.SILENT, date=sup(ON),
              entry=sup(DC))
    return dated(doc.build())


def l6_1_scene(session=F.SILENT) -> FactSet:
    """L6-1 (attack/L6-generality/l6/s05_g1_leak.py, as the FactSet its pipeline settles): a same-day EGD X1 (E1 exam,
    E2 antral biopsy: 43239) and a colonoscopy X2 to the cecum (E4 cold snare: 45385) whose examination E3 states that
    another clinician advanced the scope - its own performer claimed other_clinician with no usable fact-pass verdict
    (C2a, appraisal_missing) and its session ``session`` (silent: pass 1 filed it in none)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.EGD, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(Landmark.GASTRIC_ANTRUM)], device=sup(ct.Device.COLD_FORCEPS))
    doc.session(2, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(Extent.CECUM)])
    doc.event(3, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=session, date=sup(ON),
              entry=sup(DC), performer=unres(ct.Performer.OTHER_CLINICIAN, R_.APPRAISAL_MISSING))
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(4, Kind.SNARE, session=X(2), places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)),
            device=sup(ct.Device.COLD_SNARE))
    return dated(doc.build())


def lift_scene(purpose=None) -> FactSet:
    """L2-2 (the attacker's LiftNegationTests): a colonoscopy (E1 exam), an EMR E2 of the sigmoid lesion L1, and an
    injection E3 at the lesion whose purpose pass 1 doubted - a lift for the resection, or hemostasis - its link and
    cause stated (not part of the EMR; a bleeding of the lesion itself), so only the purpose is open."""
    doc = EF.colonoscopy(snare=False)
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(2, Kind.EMR, places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)))
    doc.act(3, Kind.INJECTION, places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)),
            purpose=purpose if purpose is not None else doubted(P.LIFT_FOR_RESECTION, P.HEMOSTASIS),
            part_of=neg(E(2)), cause=sup(C.PRE_EXISTING_LESION))
    return dated(doc.build())


class NegationFindingTests(SimpleTestCase):
    """D324 (1) on each finding's own input: red on int4, where the fold wrote "not v" as an established negation with
    no options, which facts.possibly reads as NO value - so an answer about one session took the examination out of
    every session (L2-1, L6-1), and "not a lift" took away the hemostasis reading nobody answered (L2-2)."""

    def test_l2_1_g1_about_x1_never_releases_x2s_row_7(self) -> None:
        R = l2_1_scene()
        plan = asking.plan(R, ())
        g1 = g1_specs(plan)
        self.assertEqual(sorted(g1), ['X1', 'X2'])
        self.assertIn('45385', plan.serves[g1['X1'].key])
        self.assertIn('43239', plan.serves[g1['X2'].key])
        # TRUTH: E6 is X2's examination. Fable answers both questions right: G1(X1) "not done during X1" supports,
        # its negation contradicts (established); G1(X2) is answered in the holding direction (held_by_answer)
        R_q = fold(R, record(g1['X1']), record(g1['X2'], result='unresolved', reasons=('question_contradicts',)))
        base, after = codes(R, ('45385', 2), ('43239', 5)), codes(R_q, ('45385', 2), ('43239', 5))
        self.assertIs(base['45385'][0], Outcome.NEEDS_CLARIFICATION)
        self.assertIs(after['45385'][0], Outcome.READY)  # released by its own established answer
        self.assertIs(base['43239'][0], Outcome.NEEDS_CLARIFICATION)
        self.assertEqual(after['43239'], base['43239'])  # held exactly as on R_base: nothing was established about X2
        self.assertEqual(evaluate.examinations(R_q, X(2)), evaluate.examinations(R, X(2)))
        self.assertIn(E(6), evaluate.examinations(R_q, X(2)))
        self.assertNotIn(E(6), evaluate.examinations(R_q, X(1)))
        session = F.fact(R_q, E(6), A.SESSION)
        self.assertFalse(F.established(session))
        self.assertEqual(F.ruled_out(session), (X(1),))

    def test_l2_1_an_answer_about_x1_moves_no_x2_outcome_beside_another_answer(self) -> None:
        """The verifier's variant: the real plan also asks E6's performer (F2). With the performer established, X2's
        code is decided by THAT answer - exactly as it is without G1(X1): the X1 answer moves nothing of X2."""
        R = l2_1_scene()
        plan = asking.plan(R, ())
        g1 = g1_specs(plan)
        performer = [spec for spec in plan.specs if spec.attribute is A.PERFORMER and spec.subjects == ('E6',)]
        self.assertEqual(len(performer), 1)
        both = codes(fold(R, record(g1['X1']), record(performer[0])), ('43239', 5))
        alone = codes(fold(R, record(performer[0])), ('43239', 5))
        self.assertEqual(both, alone)

    def test_l2_2_lift_not_keeps_the_doubted_hemostasis_reading(self) -> None:
        R = lift_scene()
        plan = asking.plan(R, ())
        lift_not = [spec for spec in plan.specs if spec.form == 'fact.lift.not']
        self.assertEqual(len(lift_not), 1)
        self.assertIn('45381', plan.serves[lift_not[0].key])
        # the note says no LIFTING injection was used and not why it was given: "not a lift" established; the
        # hemostasis question unclear both ways; "a lift" answered in the holding direction
        records = [record(lift_not[0])]
        for spec in plan.specs:
            if spec.attribute is A.PURPOSE and not spec.negated:
                held = spec.value == P.LIFT_FOR_RESECTION.value
                records.append(record(spec, result='unresolved',
                                      reasons=('question_contradicts' if held else 'question_unclear',)))
        R_q = fold(R, *records)
        after, base = codes(R_q, ('45381', 3), ('45390', 2)), codes(R, ('45381', 3), ('45390', 2))
        self.assertIsNot(base['45381'][0], Outcome.READY)
        self.assertIsNot(after['45381'][0], Outcome.READY)  # the injection may still be a bleeding control
        self.assertLessEqual(set(after['45381'][1]), set(base['45381'][1]))
        self.assertEqual(decided(R_q, '45382'), decided(R, '45382'))  # its purpose question, as on R_base
        self.assertEqual(evaluate.candidates(R_q, (Kind.BLEEDING_CONTROL,)),
                         evaluate.candidates(R, (Kind.BLEEDING_CONTROL,)))
        purpose = F.fact(R_q, E(3), A.PURPOSE)
        self.assertFalse(F.established(purpose))
        self.assertFalse(F.possibly(purpose, P.LIFT_FOR_RESECTION))
        self.assertTrue(F.possibly(purpose, P.HEMOSTASIS))  # pass 1's doubted reading stands, unanswered

    def test_l6_1_g1_about_the_egd_never_releases_the_colonoscopy(self) -> None:
        R = l6_1_scene()
        plan = asking.plan(R, ())
        g1 = g1_specs(plan)
        self.assertEqual(sorted(g1), ['X1', 'X2'])
        # by the words: "E3 was not done during session X1." true; "... X2." false (E3 IS X2's examination)
        R_q = fold(R, record(g1['X1']), record(g1['X2'], result='unresolved', reasons=('question_contradicts',)))
        base, after = codes(R, ('43239', 2), ('45385', 4)), codes(R_q, ('43239', 2), ('45385', 4))
        self.assertIs(base['43239'][0], Outcome.NEEDS_CLARIFICATION)
        self.assertIs(after['43239'][0], Outcome.READY)  # E3 leaves the EGD's row 7 by its own answer
        self.assertIs(base['45385'][0], Outcome.NEEDS_CLARIFICATION)
        self.assertEqual(after['45385'], base['45385'])  # the colonoscopy's examination is still another's: held
        self.assertEqual(evaluate.examinations(R_q, X(2)), (E(3),))


# --- D324 (1): other forms, values, sessions and shapes; the boundaries --------------------------------------------------


def three_sessions(session) -> FactSet:
    """A colonoscopy X1 (E1 exam, E2 snare of L1: 45385), an EGD X2 (E4 exam, E5 antral biopsy: 43239) and an ERCP X3
    (E6 exam, E7 biliary sphincterotomy: 43262), and an examination E9 done today whose performer pass 1 left silent
    (it fails row 4) and whose session is ``session``; a denial E8 of an examination in X2 (4.5's pair reader) and kept
    unlisted doubts naming each session (rule 4's pair reader). Every row-7 reader of every session may read E9."""
    doc = TA.two_sessions()
    doc.session(3, SessionKind.ERCP)
    doc.exam(6, session=X(3))
    doc.act(7, Kind.SPHINCTEROTOMY, session=X(3), duct=sup(ct.Duct.BILIARY))
    doc.event(9, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=session, date=sup(ON),
              entry=sup(DC))
    # E8: a denial of an examination in the EGD (4.5's statement-act pair reader reads it against E9)
    doc.event(8, kind=sup(Kind.EXAMINATION), status=neg(Status.PERFORMED), session=sup(X(2)), date=sup(ON))
    for number in (1, 2, 3):
        doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DOUBT, None, X(number), EF.Span(3000 + 100 * number,
                                                                                         3000 + 100 * number + 40)))
    return dated(doc.build())


SESSION_CODES = {X(1): ('45385', 2), X(2): ('43239', 5), X(3): ('43262', 7)}


class NegationVariantTests(SimpleTestCase):
    """D324 (1) beyond the findings' inputs: three sessions, a claimed or doubted or overfilled session, every negated
    purpose and cause form, two negations composed, and the boundaries the rule leaves alone."""

    def test_three_sessions_not_x1_leaves_x2_and_x3_as_r_base(self) -> None:
        R = three_sessions(F.SILENT)
        R_q = fold(R, not_in(E(9), X(1)))
        for session in (X(2), X(3)):
            with self.subTest(session=session):
                self.assertEqual(evaluate.examinations(R_q, session), evaluate.examinations(R, session))
                self.assertEqual(decided(R_q, SESSION_CODES[session][0]), decided(R, SESSION_CODES[session][0]))
        self.assertNotIn(E(9), evaluate.examinations(R_q, X(1)))
        self.assertNotEqual(decided(R_q, '45385'), decided(R, '45385'))  # X1's row 7 moved, by its own answer

    def test_two_negations_compose(self) -> None:
        R = three_sessions(F.SILENT)
        R_q = fold(R, not_in(E(9), X(1)), not_in(E(9), X(2)))
        session = F.fact(R_q, E(9), A.SESSION)
        self.assertEqual(F.ruled_out(session), (X(1), X(2)))
        self.assertEqual([F.possibly(session, x) for x in (X(1), X(2), X(3))], [False, False, True])
        self.assertEqual(decided(R_q, '43262'), decided(R, '43262'))  # X3 still read as R_base reads it
        self.assertEqual(fold(R, not_in(E(9), X(1)), not_in(E(9), X(1))).events[E(9)][A.SESSION][0].ruled_out, (X(1),))

    def test_a_claimed_session_with_a_doubted_reading_keeps_its_claim(self) -> None:
        # L6-1's reach variant: E3's session claimed X2 with a doubt reading X1 - "not X1" leaves the claimed X2
        R = l6_1_scene(session=doubted(X(2), X(1)))
        R_q = fold(R, not_in(E(3), X(1)))
        session = F.fact(R_q, E(3), A.SESSION)
        self.assertEqual((session.value, session.options, session.result), (X(2), (), ct.Result.UNKNOWN))
        self.assertTrue(evaluate._may_be_in(R_q, E(3), X(2)))
        self.assertFalse(evaluate._may_be_in(R_q, E(3), X(1)))
        self.assertEqual(coverage.sessions_of(R_q, E(3)), frozenset({X(2)}))
        self.assertEqual(codes(R_q, ('45385', 4))['45385'], codes(R, ('45385', 4))['45385'])

    def test_a_claimed_session_answered_not_itself_reads_no_other_session(self) -> None:
        # the attacker's G1ClaimedSessionTests: E6 claimed X1 (its check failed); "not X1" established - X2's codes
        # never read E6 on R_base, and never on R_q
        doc = TA.two_sessions()
        doc.event(6, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED),
                  session=unres(X(1), R_.GEOMETRY_SECTION), date=sup(ON), entry=sup(DC))
        R = dated(doc.build())
        R_q = fold(R, not_in(E(6), X(1)))
        for code in ('43239', '43235'):
            with self.subTest(code=code):
                self.assertEqual(decided(R_q, code), decided(R, code))
        self.assertFalse(F.possibly(F.fact(R_q, E(6), A.SESSION), X(1)))
        self.assertFalse(F.possibly(F.fact(R_q, E(6), A.SESSION), X(2)))  # as on R_base: pass 1 named X1 alone

    def test_an_overfilled_session_view_keeps_every_other_session(self) -> None:
        view = EF.fact(ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED, options=(X(1), X(2)),
                       reasons=(R_.SLOT_OVERFULL,))
        R = three_sessions(view)
        R_q = fold(R, not_in(E(9), X(1)))
        self.assertTrue(F.possibly(F.fact(R_q, E(9), A.SESSION), X(3)))  # the view's open denial reading
        self.assertFalse(F.possibly(F.fact(R_q, E(9), A.SESSION), X(1)))
        self.assertEqual(decided(R_q, '43239'), decided(R, '43239'))

    def test_hemostasis_not_keeps_the_lift_reading(self) -> None:
        # L2-2's reverse (the verifier's V4): "not for hemostasis" established; the lift reading pass 1 doubted stands
        R = lift_scene(purpose=doubted(P.HEMOSTASIS, P.LIFT_FOR_RESECTION))
        R_q = fold(R, negation(E(3), A.PURPOSE, P.HEMOSTASIS, 'fact.hemostasis.not'))
        purpose = F.fact(R_q, E(3), A.PURPOSE)
        self.assertTrue(F.possibly(purpose, P.LIFT_FOR_RESECTION))
        self.assertFalse(F.possibly(purpose, P.HEMOSTASIS))
        ask = coverage._Asker(R_q, E(3))
        before = coverage._enum_in(coverage._Asker(R, E(3)), E(3), A.PURPOSE, frozenset({P.LIFT_FOR_RESECTION}), P,
                                   rq.FactKey.ACT_PART)
        self.assertEqual(coverage._enum_in(ask, E(3), A.PURPOSE, frozenset({P.LIFT_FOR_RESECTION}), P,
                                           rq.FactKey.ACT_PART).truth, before.truth)
        self.assertEqual(evaluate.candidates(R_q, (Kind.BLEEDING_CONTROL,)), ())  # its own value, ruled out

    def test_lift_not_over_a_silent_purpose_keeps_hemostasis_possible(self) -> None:
        # the verifier's V3/P3: a silent purpose - "not a lift" leaves every other purpose, hemostasis included
        R = lift_scene(purpose=F.SILENT)
        R_q = fold(R, negation(E(3), A.PURPOSE, P.LIFT_FOR_RESECTION, 'fact.lift.not'))
        self.assertEqual(combination._act_kinds(R_q, E(3)), combination._act_kinds(R, E(3)))
        self.assertIn(Kind.BLEEDING_CONTROL, combination._act_kinds(R_q, E(3)))
        self.assertEqual(evaluate.candidate_kinds(R_q, (Kind.BLEEDING_CONTROL,), E(3)),
                         evaluate.candidate_kinds(R, (Kind.BLEEDING_CONTROL,), E(3)))
        # beside a proposed bleeding control the injection may still be one: competing codes hold 45381 as on R_base
        # (int4 dropped the bleeding control from the act's kinds and released it)
        base, after = codes(R, ('45381', 3), ('45382', 3)), codes(R_q, ('45381', 3), ('45382', 3))
        self.assertIsNot(after['45381'][0], Outcome.READY)
        competing = {held for held in base['45381'][1] if held[1] == 'coding_rule:competing_codes'}
        self.assertTrue(competing)
        self.assertLessEqual(competing, after['45381'][1])
        self.assertEqual(after['45382'][:2], base['45382'][:2])
        # proposed alone, the injection is read as itself (a silent purpose claims no hemostasis): the lift arm is the
        # one hold, and its own answer releases it
        self.assertIsNot(codes(R, ('45381', 3))['45381'][0], Outcome.READY)
        self.assertIs(codes(R_q, ('45381', 3))['45381'][0], Outcome.READY)

    def test_lift_not_over_a_claimed_hemostasis_keeps_the_claim(self) -> None:
        R = lift_scene(purpose=unres(P.HEMOSTASIS, R_.GEOMETRY_SECTION))
        R_q = fold(R, negation(E(3), A.PURPOSE, P.LIFT_FOR_RESECTION, 'fact.lift.not'))
        purpose = F.fact(R_q, E(3), A.PURPOSE)
        self.assertEqual(evaluate._claims_hemostasis(purpose), evaluate._claims_hemostasis(F.fact(R, E(3), A.PURPOSE)))
        self.assertTrue(F.possibly(purpose, P.HEMOSTASIS))
        self.assertEqual(decided(R_q, '45382'), decided(R, '45382'))

    def test_cause_not_keeps_every_other_cause(self) -> None:
        doc = EF.colonoscopy()
        doc.act(3, Kind.CLIP, places=[sup(Landmark.SIGMOID_COLON)], purpose=sup(P.HEMOSTASIS),
                cause=doubted(C.ACT_OF_THIS_SESSION, C.PRE_EXISTING_LESION))
        R = dated(doc.build())
        R_q = fold(R, negation(E(3), A.CAUSE, C.ACT_OF_THIS_SESSION, 'fact.cause.not'))
        cause = F.fact(R_q, E(3), A.CAUSE)
        self.assertFalse(F.possibly(cause, C.ACT_OF_THIS_SESSION))
        self.assertTrue(F.possibly(cause, C.PRE_EXISTING_LESION))
        # 45382's own CAUSE row asks the cause of the bleeding: still unstated, as on R_base
        rows = [held for held in decided(R_q, '45382')[0] if held[3] is A.CAUSE]
        self.assertEqual(rows, [held for held in decided(R, '45382')[0] if held[3] is A.CAUSE])

    def test_a_positive_answer_at_a_ruled_out_value_is_never_folded(self) -> None:
        # the two answers contradict each other: the positive one never establishes what the negation ruled out
        R = three_sessions(F.SILENT)
        R_q = fold(R, not_in(E(9), X(1)), answer(E(9), A.SESSION, X(1), 'fact.session'))
        self.assertFalse(F.established(F.fact(R_q, E(9), A.SESSION)))
        self.assertFalse(F.possibly(F.fact(R_q, E(9), A.SESSION), X(1)))
        # another value is consistent with it: established
        R_q = fold(R, not_in(E(9), X(1)), answer(E(9), A.SESSION, X(2), 'fact.session'))
        self.assertTrue(F.holds(F.fact(R_q, E(9), A.SESSION), X(2)))

    def test_boundaries_left_alone(self) -> None:
        R = three_sessions(F.SILENT)
        # a positive answer establishes its value, as before
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(9), A.SESSION, X(2), 'fact.session')), E(9), A.SESSION), X(2)))
        # the part link's universal negation ("not done as part of another act") rules out every whole: negated
        doc = EF.colonoscopy()
        doc.act(3, Kind.INJECTION, purpose=F.SILENT, part_of=F.SILENT, cause=F.SILENT)
        base = dated(doc.build())
        part = F.fact(fold(base, record(E(3), A.PART_OF, '', True, 'fact.part_link.any')), E(3), A.PART_OF)
        self.assertIs(part.result, ct.Result.NEGATED)
        self.assertFalse(any(F.possibly(part, whole) for whole in (E(1), E(2))))
        # an established fact is never answered: "not X1" over an established X2 changes nothing
        doc = TA.two_sessions()
        doc.event(6, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=sup(X(2)), date=sup(ON),
                  entry=sup(DC))
        R2 = dated(doc.build())
        self.assertIs(fold(R2, not_in(E(6), X(1))).events[E(6)][A.SESSION][0], R2.events[E(6)][A.SESSION][0])
        # a negated list member stays that member's own negation (every other member and value as before)
        R3 = dated(EF.colonoscopy(places=[unres(Landmark.SIGMOID_COLON, R_.GEOMETRY_SECTION)]).build())
        members = F.members(fold(R3, record(E(2), A.TARGET_PLACES, 'sigmoid_colon', True, 'fact.target.places')),
                            E(2), A.TARGET_PLACES)
        self.assertEqual([(member.result, member.value) for member in members],
                         [(ct.Result.NEGATED, Landmark.SIGMOID_COLON)])
        # an unestablished answer folds nothing
        unresolved = record(E(9), A.SESSION, 'X1', True, 'fact.session.not', result='unresolved')
        self.assertIs(fold(R, unresolved), R)


# --- D324 (1): the property --------------------------------------------------------------------------------------------


def witnessed(R: FactSet, code: str, candidate) -> frozenset:
    """Every witness ``candidate`` (a whatif.Candidate of ``code``) carries on ``R``: its held fact and source."""
    return frozenset((witness.held, witness.source) for witness in whatif.candidate_witnesses(R, code, candidate.group,
                                                                                            candidate.event))


def session_readers(R: FactSet, w) -> tuple:
    """Every reader of E9's session at the session ``w`` (three_sessions): facts' predicates, evaluate's row-7 readers,
    coverage's, classes', combination's and pairing's rule-4 reader."""
    found = F.fact(R, E(9), A.SESSION)
    return (F.possibly(found, w), F.possibly_written(found, w), evaluate._may_be_in(R, E(9), w),
            E(9) in evaluate.examinations(R, w), w in coverage.sessions_of(R, E(9)), classes._may_name(found, w, R),
            w in combination.possible_sessions(R, E(9)),
            sorted(pair.index for pair in pairing.unlisted_pairs(R, E(9))
                   if R.unlisted[pair.index].session == w),
            pairing.relation(R, E(8), E(9)).relation if pairing.paired(R, E(8), E(9)) else None)


def purpose_readers(R: FactSet, w) -> tuple:
    """Every reader of E3's purpose (lift_scene) at the purpose ``w``: facts' predicates, coverage's enum reader, and
    every reader of the purpose's hemostasis reading when ``w`` is hemostasis (evaluate's candidate and claim readers,
    coverage's catalogue and adjunct readers, combination's act kinds, pairing's and classes' kind readers)."""
    found = F.fact(R, E(3), A.PURPOSE)
    out = [F.possibly(found, w), F.possibly_written(found, w),
           coverage._enum_in(coverage._Asker(R, E(3)), E(3), A.PURPOSE, frozenset({w}), P,
                             rq.FactKey.ACT_PART).truth]
    if w is P.HEMOSTASIS:
        out += [evaluate._claims_hemostasis(found), evaluate.candidate_kinds(R, (Kind.BLEEDING_CONTROL,), E(3)),
                evaluate._possible_kinds(R, E(3)), coverage._purpose_may_be_hemostasis(found),
                coverage._treats_bleeding(R, E(3)), coverage.catalogue_kinds(R, E(3)), combination._act_kinds(R, E(3)),
                pairing._catalogue_reading(R, E(3), frozenset({Kind.INJECTION})),
                classes._may_be_of_group(R, E(3), (Kind.BLEEDING_CONTROL,)), decided(R, '45382')]
    return tuple(out)


def cause_scene(cause) -> FactSet:
    doc = EF.colonoscopy()
    doc.act(3, Kind.CLIP, places=[sup(Landmark.SIGMOID_COLON)], purpose=sup(P.HEMOSTASIS), cause=cause)
    return dated(doc.build())


def cause_readers(R: FactSet, w) -> tuple:
    found = F.fact(R, E(3), A.CAUSE)
    return (F.possibly(found, w), F.possibly_written(found, w),
            coverage._enum_in(coverage._Asker(R, E(3)), E(3), A.CAUSE, frozenset({w}), C, rq.FactKey.ACT_CAUSE).truth,
            [held for held in decided(R, '45382')[0] if held[3] is A.CAUSE])


def _overfilled(*values) -> object:
    return EF.fact(ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED, options=values, reasons=(R_.SLOT_OVERFULL,))


def _open_denial(value) -> object:
    return EF.fact(ct.Result.UNRESOLVED, value, ct.FactState.NEGATED, reasons=(R_.GEOMETRY_SECTION,))


def _empty_doubt(*readings) -> object:
    return EF.fact(ct.Result.UNKNOWN, None, None, options=readings, reasons=(R_.DOUBT_STATED,))


SESSION_SHAPES = {
    'silent': F.SILENT, 'empty doubt X1|X2': _empty_doubt(X(1), X(2)), 'claimed X2 doubting X1': doubted(X(2), X(1)),
    'claimed X1 doubting X2': doubted(X(1), X(2)), 'claimed X1 geometry': unres(X(1), R_.GEOMETRY_SECTION),
    'claimed X2 option X1': unres(X(2), R_.APPRAISAL_MISSING, options=(X(1),)),
    'claimed X1 no verdict': unres(X(1), R_.APPRAISAL_MISSING), 'open denial X2': _open_denial(X(2)),
    'overfilled X1 X2': _overfilled(X(1), X(2)), 'conflict X1': unres(X(1), R_.SESSION_CONFLICT),
    'claimed X3 unappraised': unres(X(3), R_.UNAPPRAISED)}
PURPOSE_SHAPES = {
    'silent': F.SILENT, 'empty doubt': _empty_doubt(P.LIFT_FOR_RESECTION, P.HEMOSTASIS),
    'lift doubting hemostasis': doubted(P.LIFT_FOR_RESECTION, P.HEMOSTASIS),
    'hemostasis doubting lift': doubted(P.HEMOSTASIS, P.LIFT_FOR_RESECTION),
    'lift geometry': unres(P.LIFT_FOR_RESECTION, R_.GEOMETRY_SECTION),
    'hemostasis no verdict': unres(P.HEMOSTASIS, R_.APPRAISAL_MISSING),
    'prophylaxis unappraised': unres(P.PROPHYLAXIS, R_.UNAPPRAISED), 'open denial hemostasis': _open_denial(P.HEMOSTASIS),
    'overfilled': _overfilled(P.LIFT_FOR_RESECTION, P.HEMOSTASIS)}
CAUSE_SHAPES = {
    'silent': F.SILENT, 'act doubting lesion': doubted(C.ACT_OF_THIS_SESSION, C.PRE_EXISTING_LESION),
    'lesion doubting act': doubted(C.PRE_EXISTING_LESION, C.ACT_OF_THIS_SESSION),
    'act geometry': unres(C.ACT_OF_THIS_SESSION, R_.GEOMETRY_SECTION), 'open denial act': _open_denial(
        C.ACT_OF_THIS_SESSION), 'overfilled': _overfilled(C.ACT_OF_THIS_SESSION, C.SPONTANEOUS)}


class NegationPropertyTests(SimpleTestCase):
    """THE property of D324 (1): for every negated form (fact.session.not, fact.lift.not, fact.hemostasis.not,
    fact.cause.not), every base shape a question may be asked over, and every value w other than the answered v, every
    reader reads the answered fact on R_q exactly as on R_base - and v is ruled out for facts.possibly and every reader
    built on it. Each reader is listed in session_readers, purpose_readers and cause_readers."""

    def check(self, scene, shapes, readers, subject, attribute, form, values, ruled) -> int:
        compared = 0
        for name, shape in shapes.items():
            R = scene(shape)
            R_q = fold(R, negation(subject, attribute, ruled, form))
            found = F.fact(R_q, subject, attribute)
            with self.subTest(form=form, shape=name):
                self.assertFalse(F.established(found))
                self.assertIsInstance(found, F.NarrowedFact)
                self.assertEqual(F.ruled_out(found), (ruled,))
                self.assertFalse(F.possibly(found, ruled))
                self.assertFalse(F.possibly_written(found, ruled))
            for w in values:
                if w == ruled:
                    continue
                with self.subTest(form=form, shape=name, w=w):
                    self.assertEqual(readers(R_q, w), readers(R, w))
                    compared += 1
        return compared

    def test_session_not(self) -> None:
        for ruled in (X(1), X(2)):
            compared = self.check(three_sessions, SESSION_SHAPES, session_readers, E(9), A.SESSION,
                                  'fact.session.not', (X(1), X(2), X(3)), ruled)
            self.assertEqual(compared, len(SESSION_SHAPES) * 2)

    def test_session_not_leaves_every_witness_of_another_session_alone(self) -> None:
        # the witness level: every candidate act of another session - of every candidate code - carries exactly the
        # witnesses it carries on R_base (a code may also hold a candidate of X1, whose row 7 the answer releases)
        for name, shape in SESSION_SHAPES.items():
            R = three_sessions(shape)
            R_q = fold(R, not_in(E(9), X(1)))
            for code in sorted(set(whatif.candidate_codes(R)) | set(whatif.candidate_codes(R_q))):
                for candidate in whatif.witnesses(R, code):
                    home = F.fact(R, candidate.event, A.SESSION)
                    if not F.established(home) or home.value == X(1):
                        continue
                    with self.subTest(shape=name, code=code, event=candidate.event):
                        self.assertEqual(witnessed(R_q, code, candidate), witnessed(R, code, candidate))

    def test_lift_not_and_hemostasis_not(self) -> None:
        for form, ruled in (('fact.lift.not', P.LIFT_FOR_RESECTION), ('fact.hemostasis.not', P.HEMOSTASIS)):
            compared = self.check(lift_scene, PURPOSE_SHAPES, purpose_readers, E(3), A.PURPOSE, form, tuple(P), ruled)
            self.assertEqual(compared, len(PURPOSE_SHAPES) * (len(P) - 1))

    def test_cause_not(self) -> None:
        compared = self.check(cause_scene, CAUSE_SHAPES, cause_readers, E(3), A.CAUSE, 'fact.cause.not', tuple(C),
                              C.ACT_OF_THIS_SESSION)
        self.assertEqual(compared, len(CAUSE_SHAPES) * (len(C) - 1))

    def test_the_answer_rules_its_value_out_for_the_possibility_readers(self) -> None:
        # the release direction, through facts.possibly: row 7's examinations, rule 4's pairs, the bleeding candidacy
        R = three_sessions(F.SILENT)
        R_q = fold(R, not_in(E(9), X(1)))
        self.assertFalse(evaluate._may_be_in(R_q, E(9), X(1)))
        self.assertNotIn(E(9), evaluate.examinations(R_q, X(1)))
        self.assertNotIn(0, [pair.index for pair in pairing.unlisted_pairs(R_q, E(9))])
        R = lift_scene(purpose=F.SILENT)
        R_q = fold(R, negation(E(3), A.PURPOSE, P.HEMOSTASIS, 'fact.hemostasis.not'))
        self.assertNotIn(Kind.BLEEDING_CONTROL, combination._act_kinds(R_q, E(3)))
        self.assertFalse(coverage._treats_bleeding(R_q, E(3)))


# --- D324 (4): K3 never asked, never folded, and re-judged on an answered session or place -------------------------------


def egd_biopsy(place, session) -> FactSet:
    """L1-02: an EGD X1 (E1 done today, reached the second portion of the duodenum) and E2, a forceps biopsy at
    ``place`` whose session is ``session``."""
    doc = EF.Doc()
    doc.session(1, SessionKind.EGD, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, session=session, places=[sup(place)] if place is not None else [])
    return dated(doc.build())


UNREACHABLE = (Landmark.JEJUNUM, Landmark.SIGMOID_COLON, Landmark.RECTUM)  # FAMILY_REACH[EGD] holds none of them
REACHABLE = (Landmark.GASTRIC_ANTRUM, Landmark.DUODENAL_BULB, Landmark.SECOND_PORTION_DUODENUM)


class FixedTableFindingTests(SimpleTestCase):
    """D324 (4) on L1-02's input: red on int4, where session_unreachable stayed answerable (only L1's date checks were
    refused), so "This act was done during session X1." - true by the note's words - released 43239 for a jejunal (or
    colonic) biopsy filed in the EGD."""

    def test_l1_02_a_k3_session_is_never_asked_and_never_folded(self) -> None:
        for place in UNREACHABLE:
            with self.subTest(place=place):
                R = egd_biopsy(place, unres(X(1), R_.SESSION_UNREACHABLE))
                plan = asking.plan(R, ())
                self.assertFalse([spec for spec in plan.specs if spec.subjects == ('E2',)
                                  and spec.attribute is A.SESSION])
                self.assertFalse(F.answerable(F.fact(R, E(2), A.SESSION)))
                R_q = fold(R, answer(E(2), A.SESSION, X(1), 'fact.session'))
                self.assertIs(R_q.events[E(2)][A.SESSION][0], R.events[E(2)][A.SESSION][0])
                base, after = codes(R, ('43239', 2)), codes(R_q, ('43239', 2))
                self.assertIs(base['43239'][0], Outcome.NEEDS_CLARIFICATION)
                self.assertEqual(after, base)
                self.assertIn(('procedure', 'unestablished:session_unreachable', 'E2', R_.SESSION_UNREACHABLE),
                              base['43239'][1])

    def test_a_silent_session_answered_into_a_family_that_cannot_reach_the_place_is_never_folded(self) -> None:
        for place in UNREACHABLE:
            with self.subTest(place=place):
                R = egd_biopsy(place, F.SILENT)
                R_q = fold(R, answer(E(2), A.SESSION, X(1), 'fact.session'))
                self.assertFalse(F.established(F.fact(R_q, E(2), A.SESSION)))
                self.assertIsNot(codes(R_q, ('43239', 2))['43239'][0], Outcome.READY)
                self.assertFalse(F.folds(R, E(2), A.SESSION, 'X1'))

    def test_a_reachable_place_is_folded(self) -> None:  # the boundary K3 leaves alone
        for place in REACHABLE:
            with self.subTest(place=place):
                R = egd_biopsy(place, F.SILENT)
                R_q = fold(R, answer(E(2), A.SESSION, X(1), 'fact.session'))
                self.assertTrue(F.holds(F.fact(R_q, E(2), A.SESSION), X(1)))
                self.assertIs(codes(R_q, ('43239', 2))['43239'][0], Outcome.READY)
                self.assertTrue(F.folds(R, E(2), A.SESSION, 'X1'))
        # a session whose check failed for a reading reason is answered, as before
        R = egd_biopsy(Landmark.GASTRIC_ANTRUM, unres(X(1), R_.GEOMETRY_SECTION))
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(2), A.SESSION, X(1), 'fact.session')), E(2), A.SESSION),
                                X(1)))

    def test_an_answered_place_is_re_judged_for_reach(self) -> None:
        for place in UNREACHABLE:
            with self.subTest(place=place):
                R = egd_biopsy(None, sup(X(1)))
                R_q = fold(R, answer(E(2), A.TARGET_PLACES, place, 'fact.target.places'))
                self.assertEqual(F.members(R_q, E(2), A.TARGET_PLACES), ())
                self.assertFalse(F.folds(R, E(2), A.TARGET_PLACES, place.value))
        R = egd_biopsy(None, sup(X(1)))
        R_q = fold(R, answer(E(2), A.TARGET_PLACES, Landmark.GASTRIC_ANTRUM, 'fact.target.places'))
        self.assertEqual([member.value for member in F.members(R_q, E(2), A.TARGET_PLACES)], [Landmark.GASTRIC_ANTRUM])

    def test_a_place_answer_adding_an_unreachable_place_beside_one_already_unreachable_is_never_folded(self) -> None:
        # the check is re-run by its failing COMBINATIONS: a place the answer adds beyond the reach is refused even where
        # another place of the act already fails (that one's session is K3's to demote; the answer's own is the answer's)
        R = egd_biopsy(Landmark.JEJUNUM, unres(X(1), R_.GEOMETRY_SECTION))  # hand-built: K3's own reason left off
        for place, kept in ((Landmark.SIGMOID_COLON, False), (Landmark.RECTUM, False), (Landmark.GASTRIC_ANTRUM, True)):
            with self.subTest(place=place):
                R_q = fold(R, answer(E(2), A.TARGET_PLACES, place, 'fact.target.places'))
                self.assertEqual(place in [member.value for member in F.members(R_q, E(2), A.TARGET_PLACES)], kept)
        self.assertTrue(F._k3_failures(F._Folded(R, {}), E(2)))  # the jejunum already fails without any answer

    def test_an_enteroscopy_reaches_the_jejunum(self) -> None:  # the same answer into a family that reaches it: folded
        doc = EF.Doc()
        doc.session(1, SessionKind.ENTEROSCOPY, reached=[sup(Extent.JEJUNUM)])
        doc.exam(1)
        doc.act(2, Kind.BIOPSY, session=F.SILENT, places=[sup(Landmark.JEJUNUM)])
        R = dated(doc.build())
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(2), A.SESSION, X(1), 'fact.session')), E(2), A.SESSION), X(1)))


# --- D324 (4): every other fixed-table check re-run on an answered fact -------------------------------------------------


class RecheckTests(SimpleTestCase):
    """The fold re-runs each fixed-table check on every answered fact it reads, the answer in the folded facts
    (DECISIONS D324 (4)); a check it cannot re-run whole refuses the facts it reads."""

    def test_k2_the_answered_sessions_family_must_admit_the_acts_kind(self) -> None:
        doc = EF.colonoscopy(snare=False)
        doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(4, session=X(2))
        doc.act(3, Kind.PEG, session=F.SILENT, places=[])  # no place: K3 cannot judge it, K2's kind arm alone does
        R = dated(doc.build())
        self.assertNotIn(Kind.PEG, F.family_kinds(SessionKind.COLONOSCOPY))
        self.assertIn(Kind.PEG, F.family_kinds(SessionKind.EGD))
        self.assertFalse(F.established(F.fact(fold(R, answer(E(3), A.SESSION, X(1), 'fact.session')), E(3),
                                              A.SESSION)))
        # refused by K2's kind arm alone: K3 has no place to judge
        self.assertFalse(F._k3_failures(F._Folded(R, {}).at(E(3), {**R.events[E(3)], A.SESSION: (sup(X(1)),)}), E(3)))
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(3), A.SESSION, X(2), 'fact.session')), E(3), A.SESSION),
                                X(2)))
        # K2's existence arm: a session the row does not hold is never established
        self.assertFalse(F.established(F.fact(fold(R, answer(E(3), A.SESSION, X(7), 'fact.session')), E(3),
                                              A.SESSION)))

    def test_k4_no_answered_place_reach_or_station_inside_a_surgically_absent_organ(self) -> None:
        doc = EF.colonoscopy(snare=False)
        doc.entry(1, type=sup(ct.AnatomyType.SURGICALLY_ABSENT))
        doc.anatomy[Y(1)][A.ORGAN] = (sup(Landmark.COLON),)
        doc.act(3, Kind.BIOPSY, places=[])
        doc.sessions[X(1)][A.REACHED] = ()
        R = dated(doc.build())
        for place in (Landmark.TRANSVERSE_COLON, Landmark.COLON, Landmark.SIGMOID_COLON):
            with self.subTest(place=place):
                R_q = fold(R, answer(E(3), A.TARGET_PLACES, place, 'fact.target.places'))
                self.assertEqual(F.members(R_q, E(3), A.TARGET_PLACES), ())
        self.assertEqual(F.members(fold(R, answer(E(3), A.TARGET_PLACES, Landmark.TERMINAL_ILEUM,
                                                  'fact.target.places')), E(3), A.TARGET_PLACES)[0].value,
                         Landmark.TERMINAL_ILEUM)
        self.assertEqual(F.members(fold(R, answer(X(1), A.REACHED, Extent.CECUM, 'fact.reached')), X(1), A.REACHED),
                         ())
        # the absent organ answered, against a place pass 1 stated: never folded either (the entry filed a stoma, its
        # check failed); and an entry K4 itself demoted is never answered
        doc.anatomy[Y(1)][A.TYPE] = (unres(ct.AnatomyType.STOMA, R_.GEOMETRY_SECTION),)
        doc.events[E(3)][A.TARGET_PLACES] = (sup(Landmark.TRANSVERSE_COLON),)
        R = dated(doc.build())
        self.assertFalse(F.established(F.fact(fold(R, answer(Y(1), A.TYPE, ct.AnatomyType.SURGICALLY_ABSENT,
                                                             'fact.type')), Y(1), A.TYPE)))
        self.assertTrue(F.holds(F.fact(fold(R, answer(Y(1), A.TYPE, ct.AnatomyType.STOMA, 'fact.type')), Y(1), A.TYPE),
                                ct.AnatomyType.STOMA))
        doc.anatomy[Y(1)][A.TYPE] = (unres(ct.AnatomyType.SURGICALLY_ABSENT, R_.ANATOMY_CONFLICT),)
        R = dated(doc.build())
        self.assertFalse(F.answerable(F.fact(R, Y(1), A.TYPE)))
        self.assertFalse(F.established(F.fact(fold(R, answer(Y(1), A.TYPE, ct.AnatomyType.SURGICALLY_ABSENT,
                                                             'fact.type')), Y(1), A.TYPE)))

    def test_k1_rules_re_run(self) -> None:
        # the endoscopic rule: a reach answered on a session whose kind is not stated endoscopic
        doc = EF.Doc()
        doc.session(1, EF.fact(ct.Result.UNKNOWN, None, None, reasons=(R_.SILENT,)))
        doc.exam(1)
        R = dated(doc.build())
        self.assertEqual(F.members(fold(R, answer(X(1), A.REACHED, Extent.CECUM, 'fact.reached')), X(1), A.REACHED), ())
        R_ok = dated(EF.colonoscopy(snare=False).build())
        R_ok = replace(R_ok, sessions={**R_ok.sessions, X(1): {**R_ok.sessions[X(1)], A.REACHED: ()}})
        self.assertEqual([m.value for m in F.members(fold(R_ok, answer(X(1), A.REACHED, Extent.CECUM, 'fact.reached')),
                                                    X(1), A.REACHED)], [Extent.CECUM])
        # the visit rule: a visit basis answered on an act that is no visit
        doc = EF.colonoscopy(basis=F.SILENT)
        R = dated(doc.build())
        self.assertFalse(F.established(F.fact(fold(R, answer(E(2), A.VISIT_BASIS, ct.EmBasis.MEDICAL_DECISION_MAKING, 'fact.visit.basis')),
                                              E(2), A.VISIT_BASIS)))
        visit = EF.Doc()
        visit.session(1, SessionKind.OFFICE_EM)
        visit.act(1, Kind.EM_VISIT, basis=F.SILENT)
        R = dated(visit.build())
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(1), A.VISIT_BASIS, ct.EmBasis.MEDICAL_DECISION_MAKING, 'fact.visit.basis')), E(1),
                                       A.VISIT_BASIS), ct.EmBasis.MEDICAL_DECISION_MAKING))
        # status against timing: a later date answered on an act done today (a planned form never asks it)
        R = dated(EF.colonoscopy(date=unres(ON, R_.GEOMETRY_SECTION)).build())
        self.assertFalse(F.established(F.fact(fold(R, answer(E(2), A.DATE_RELATION, ct.DateRelation.LATER_DATE,
                                                             'fact.date_relation')), E(2), A.DATE_RELATION)))
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(2), A.DATE_RELATION, ON, 'fact.date_relation')), E(2),
                                       A.DATE_RELATION), ON))
        # the part rule: a part link answered without its relation; the separation form needs none
        R = dated(EF.colonoscopy(part_of=F.SILENT).build())
        self.assertFalse(F.established(F.fact(fold(R, answer(E(2), A.PART_OF, E(1), 'fact.part_of')), E(2), A.PART_OF)))
        self.assertIs(F.fact(fold(R, record(E(2), A.PART_OF, '', True, 'fact.part_link.any')), E(2), A.PART_OF).result,
                      ct.Result.NEGATED)
        # the cause rule: a stated cause only with a hemostasis purpose; the cause's negation states none
        doc = EF.colonoscopy()
        doc.act(3, Kind.INJECTION, purpose=F.SILENT, cause=F.SILENT)
        R = dated(doc.build())
        self.assertFalse(F.established(F.fact(fold(R, answer(E(3), A.CAUSE, C.PRE_EXISTING_LESION, 'fact.cause')),
                                              E(3), A.CAUSE)))
        self.assertFalse(F.possibly(F.fact(fold(R, negation(E(3), A.CAUSE, C.ACT_OF_THIS_SESSION, 'fact.cause.not')),
                                          E(3), A.CAUSE), C.ACT_OF_THIS_SESSION))
        doc.events[E(3)][A.PURPOSE] = (sup(P.HEMOSTASIS),)
        R = dated(doc.build())
        self.assertTrue(F.holds(F.fact(fold(R, answer(E(3), A.CAUSE, C.PRE_EXISTING_LESION, 'fact.cause')), E(3),
                                       A.CAUSE), C.PRE_EXISTING_LESION))

    def test_the_checks_not_re_run_here_refuse_the_facts_they_read(self) -> None:
        R = dated(EF.colonoscopy(kind=F.SILENT, status=unres(Status.PERFORMED, R_.GEOMETRY_SECTION),
                                 yield_=F.SILENT, breadth=F.SILENT).build())
        for attribute, value in ((A.KIND, Kind.SNARE.value), (A.STATUS, Status.PERFORMED.value),
                                 (A.YIELD, ct.Material.TISSUE.value), (A.SCOPE_BREADTH, ct.Breadth.ALL_OF_KIND.value)):
            with self.subTest(attribute=attribute):
                self.assertFalse(F.folds(R, E(2), attribute, value))
                R_q = fold(R, record(E(2), attribute, value, False, f'fact.{attribute.value}'))
                self.assertFalse(F.established(F.fact(R_q, E(2), attribute)))
        undated = EF.colonoscopy().build()  # the date of service silent: answerable, and still never answered
        self.assertTrue(F.answerable(F.fact(undated, None, A.DATE_OF_SERVICE)))
        self.assertFalse(F.folds(undated, None, A.DATE_OF_SERVICE, '2026-11-09'))
        self.assertFalse(F.folds(R, X(1), A.EXAMINATION, 'E1'))


# --- D324 (4): the typed table over the Reason enum --------------------------------------------------------------------


def performer_answer() -> dict:
    return record(E(2), A.PERFORMER, TEAM.value, False, 'fact.performer')


class ReasonTableTests(SimpleTestCase):
    """REASON_CLASSES: every Reason member classified, a member it does not name a fixed-table check, and every
    fixed-table reason with its re-check."""

    def test_every_member_is_classified_once(self) -> None:
        self.assertEqual(set(F.REASON_CLASSES), set(ct.Reason))
        named = [reason for _, reasons in F._CLASSED for reason in reasons]
        self.assertEqual(len(named), len(set(named)))
        counts = {kind: sum(1 for value in F.REASON_CLASSES.values() if value is kind) for kind in F.ReasonClass}
        self.assertEqual(counts, {F.ReasonClass.READING: 36, F.ReasonClass.FIXED_TABLE: 19, F.ReasonClass.JUDGED: 21,
                                  F.ReasonClass.UNLOCATED: 1, F.ReasonClass.CONTRADICTION: 1,
                                  F.ReasonClass.CONFLICT: 3})
        self.assertEqual(F.FIXED_TABLE, frozenset({
            R_.LITERAL_MISMATCH, R_.LITERAL_UNCHECKED, R_.SESSION_UNREACHABLE, R_.SESSION_INCONSISTENT,
            R_.ANATOMY_CONFLICT, *(reason for reason in ct.Reason if reason.value.startswith('structure_'))}))

    def test_a_member_the_table_does_not_name_is_a_fixed_table_check(self) -> None:
        unnamed = MappingProxyType({reason: kind for reason, kind in F.REASON_CLASSES.items()
                                    if reason is not R_.DOUBT_STATED})
        found = doubted(TEAM, ct.Performer.OTHER_CLINICIAN)
        self.assertTrue(F.answerable(found))
        with mock.patch.object(F, 'REASON_CLASSES', unnamed):
            self.assertIs(F.reason_class(R_.DOUBT_STATED), F.ReasonClass.FIXED_TABLE)
            self.assertFalse(F.answerable(found))

    def test_the_named_sets_are_the_tables(self) -> None:
        self.assertLessEqual(F.DATE_CHECKS, F.FIXED_TABLE)
        for name, kind in (('JUDGED', F.ReasonClass.JUDGED), ('FIXED_TABLE', F.ReasonClass.FIXED_TABLE),
                           ('CONFLICTS', F.ReasonClass.CONFLICT)):
            with self.subTest(name=name):
                self.assertEqual(getattr(F, name), frozenset(r for r, k in F.REASON_CLASSES.items() if k is kind))
        self.assertNotIn(R_.ANATOMY_CONFLICT, F.CONFLICTS)

    def test_every_fixed_table_reason_has_its_recheck(self) -> None:
        self.assertEqual(set(F._RECHECKS), set(F.FIXED_TABLE))
        for reason, checks in F._RECHECKS.items():
            with self.subTest(reason=reason):
                self.assertTrue(checks)
                self.assertTrue(all(check.reads for check in checks))
        # K3's re-check reads the answered session and the answered place (D324 (4): "an answered session or place is
        # re-judged for reach")
        k3 = F._RECHECKS[R_.SESSION_UNREACHABLE][0]
        self.assertIn((F._E, A.SESSION), k3.reads)
        self.assertIn((F._E, A.TARGET_PLACES), k3.reads)

    def test_every_reason_is_folded_or_refused_by_its_class(self) -> None:
        refused = set()
        for reason in ct.Reason:
            R = EF.colonoscopy(performer=unres(TEAM, reason)).build()
            if not F.established(F.fact(fold(R, performer_answer()), E(2), A.PERFORMER)):
                refused.add(reason)
        self.assertEqual(refused, set(F.FIXED_TABLE | F.JUDGED | {R_.ANCHOR_INVALID}))

    def test_the_planner_asks_no_session_a_fixed_table_check_demoted(self) -> None:
        for reason in (R_.SESSION_UNREACHABLE, R_.SESSION_INCONSISTENT):
            with self.subTest(reason=reason):
                R = egd_biopsy(Landmark.GASTRIC_ANTRUM, unres(X(1), reason))
                self.assertFalse([spec for spec in asking.plan(R, ()).specs if spec.subjects == ('E2',)
                                  and spec.attribute is A.SESSION])
        # the boundary: a reading reason on the same fact is asked
        R = egd_biopsy(Landmark.GASTRIC_ANTRUM, unres(X(1), R_.GEOMETRY_SECTION))
        self.assertTrue([spec for spec in asking.plan(R, ()).specs if spec.subjects == ('E2',)
                         and spec.attribute is A.SESSION])
