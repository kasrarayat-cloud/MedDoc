"""The enteroscopy classes (docs/gemini-migration/FINAL-V2.md 4.3 ENT, 4.7, 5.5; step 4c of its 8.1), TEXT-ONLY and
SYNTHETIC: engine/classes.py, v1's studio/interpretation/classes.py forked over settled facts.

v1's class tests re-expressed over hand-built settled FactSets (gate 6's form, 9.5), each class named after the v1 test
class it re-expresses - tests/test_interpretation_r4_enteroscopy.py (D108), r5_enteroscopy_route.py (D114) and the class
rules of r5c-r5f (D141, D148, D153, D160) - with what changes under v2 said where it changes:
- a class fits only when every part of 4.3 ENT holds on the session: its kind, its approach (oral for JEJUNAL and ILEAL,
  through_stoma, through_pouch - or, D219, transanal into an established ileal pouch), the anatomy entry it went through
  (a stoma; an ileal pouch, never a gastric pouch or a Roux limb: the done-when of 8.1's 4c row), a supported point in
  the class's reach (and for JEJUNAL, 'not including ileum', no point the oral route reaches only through the ileum
  that may have been reached: D218), and for ILEAL a completion established complete or silent (D217) and no
  examination of the session established attempted unless one is established performed (D72 as D217 reads it);
- an unknown part is a question, an established failure an explanation (4.8), each a HeldFact with its rank and cause
  (a contradicted fact at rank 1, a doubted status at rank 2: requirements.py's RANK rule, D217); a reach list is never
  read as complete (P3): a reach outside the class's own is a question; a doubt is never an absence (P3, P6), an empty
  slot a doubt names included (refute-4c-r1 A);
- round 2 (refute-4c-r1): A, B, C, D, E and F repaired, each pinned by a test named after its finding;
- r4c (refute-4c-r2, DECISIONS D216-D219): A3 (a contradicted or doubted completion), UNRES (an unresolved one), SEQ (an
  attempt beside a performed examination), SILENT-EXAM, DQ2-EXT (the points past the ileum; the small bowel),
  DQ4-CARRIED (a silent completion fits) and DQ1-CARRIED (a transanal pouchoscopy), and D216's synthetic unlisted act in
  the absence conditions - each pinned by a test named after its ruling;
- r4c, D231's classes half: an unlisted DOUBT is a possibly performed act too, so each absence condition that reads the
  synthetic act (act_elsewhere; D72's F; D72's T) gives an unlisted doubt the outcome it gives an unlisted act and the
  same doubt filed as an event whose status is doubted - a test per condition; an unlisted denial is no such act; a card
  naming a session the FactSet does not hold leaves the session possible (4.11), as engine/evaluate.py reads it, and the
  natures classes reads are the natures evaluate reads (O17);
- r4c-2 (refute-r4c-r1): P1 - an examination whose session fact names a session the FactSet does not hold may be the
  session's (4.11; DECISIONS D227's 4d R2-2), so a dangling session id is a question on that session, never a fit (44377
  was READY), and the same doubt filed in such a session gives the unlisted card's outcome (P4); P3 - the synthetic
  act's witness quotes its own units only, so questions.synthetic_entry finds its entry; N1 - the stored order;
- the third and fourth portions of the duodenum stand where v1's duodenum stands: in no enteroscopy class (D204);
- act_elsewhere reads the act's own session fact, never a region (4.7, 4.13): an act placed in another family's
  session holds the enteroscopy act code (performed_status, an explanation), never READY, never excluded;
- every read lies inside the codes' requirement closure (P-READSET, P-INDEP), weakening never turns a misfit into a fit
  (P-MONO, hypothesis), the module keeps 5.7 measure 4, imports no v1 module and passes mypy --strict.
Every fixture here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from studio.interpretation import classes as v1_classes
from studio.interpretation import store
from studio.interpretation.contract.types import (AnatomyType, Approach, Attribute, Completion, DateRelation, Extent,
                                                  FactState, Kind, Owner, Performer, Purpose, Reason, Result,
                                                  SessionKind, Status, UnlistedWhat)
from studio.interpretation.engine import anatomy as AN
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import classes as C
from studio.interpretation.engine import evaluate as EV
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as QS
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine.catalogue import EnteroscopyClass
from studio.interpretation.engine.types import (Anchor, Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Outcome,
                                                Span, UnlistedStatement)
from tests.v2 import test_facts as TF
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'classes.py'
A = Attribute
X1, X2, X3 = (Id(IdFamily.SESSION, n) for n in (1, 2, 3))
E1, E2, E3, E4, E5, E6 = (Id(IdFamily.EVENT, n) for n in range(1, 7))
Y1, Y2, Y3 = (Id(IdFamily.ANATOMY, n) for n in (1, 2, 3))
JEJUNAL, ILEAL, STOMA, POUCH = (EnteroscopyClass.JEJUNAL, EnteroscopyClass.ILEAL, EnteroscopyClass.STOMA,
                                EnteroscopyClass.POUCH)
ORAL, THROUGH_STOMA, THROUGH_POUCH = Approach.ORAL, Approach.THROUGH_STOMA, Approach.THROUGH_POUCH
ENTEROSCOPY = SessionKind.ENTEROSCOPY
# one code of each class, and every catalogue code of the family by class (v1's pin, R4's last test but one)
CODE_OF = {JEJUNAL: '44361', ILEAL: '44377', STOMA: '44382', POUCH: '44386'}
FAMILY_CODES = {
    **{code: JEJUNAL for code in ('44360', '44361', '44363', '44364', '44365', '44366', '44369', '44370', '44372',
                                  '44373')},
    **{code: ILEAL for code in ('44376', '44377', '44378', '44379')},
    **{code: STOMA for code in ('44380', '44381', '44382', '44384')},
    **{code: POUCH for code in ('44385', '44386')}}
JOINED_VENDORS = re.compile(r'(?i)(?<![a-z0-9])(?:corti|astra|fable|openai|anthropic|claude|gemini|google)(?![a-z0-9])')


# --- settled facts, built by hand (9.5's gate-6 form: facts carry no words) -------------------------------------------


def unit(n: int) -> Span:
    """A unit's span in a synthetic revision (S<n>): offsets only, no text."""
    return Span(100 * n, 100 * n + 60)


def sup(value, n: int = 1) -> Fact:
    return Fact(Result.SUPPORTED, value, FactState.SUPPORTED, (), (), (unit(n),))


def neg(value, n: int = 1) -> Fact:
    return Fact(Result.NEGATED, value, FactState.NEGATED, (), (), (unit(n),))


def unresolved(value, reason: Reason = Reason.APPRAISAL_UNCLEAR, options=(), n: int = 1,
               state: FactState = FactState.SUPPORTED) -> Fact:
    return Fact(Result.UNRESOLVED, value, state, tuple(options), (reason,), (unit(n),))


def doubted(value, readings, n: int = 1) -> Fact:
    """A fact a doubt names (3.3 row 2): unknown, its value kept, the doubt's readings its options."""
    return Fact(Result.UNKNOWN, value, FactState.SUPPORTED, tuple(readings), (Reason.DOUBT_UNCLEAR,), (unit(n),))


def contradicted(options, n: int = 1) -> Fact:
    return Fact(Result.CONTRADICTED, None, FactState.CONTRADICTED, tuple(options), (Reason.CONTRADICTED_BY_PASS1,),
                (unit(n),))


def as_fact(value, n: int) -> Fact:
    return value if isinstance(value, Fact) else sup(value, n)


def session(kind=ENTEROSCOPY, *, approach=None, through=None, reached=(), completion=None) -> dict:
    """A session's facts: its kind (S2), approach (S3), reached points (S4, S5, ...), through (S9) and completion (S11);
    a value is read as supported, a Fact as given, None as silent."""
    facts = {A.KIND: (as_fact(kind, 2),), A.REACHED: tuple(as_fact(point, 4 + index)
                                                           for index, point in enumerate(reached))}
    for attribute, value, n in ((A.APPROACH, approach, 3), (A.THROUGH, through, 9), (A.COMPLETION, completion, 11)):
        if value is not None:
            facts[attribute] = (as_fact(value, n),)
    return facts


def event(kind, in_session, *, status=Status.PERFORMED, n: int = 12, **more) -> dict:
    """A done act (4.3 rows 1-5 supported): its kind, session and status at S<n>, its date relation, performer and
    entry at S1 (the document frame); ``more``: other facts by attribute name, as session() reads values."""
    facts = {A.KIND: (as_fact(kind, n),), A.SESSION: (as_fact(in_session, n),), A.STATUS: (as_fact(status, n),),
             A.DATE_RELATION: (sup(DateRelation.ON_DATE_OF_SERVICE),), A.PERFORMER: (sup(Performer.DOCUMENTING_TEAM),),
             A.ENTRY: (sup(Owner.DOCUMENTING_CLINICIAN),)}
    for name, value in more.items():
        facts[Attribute[name.upper()]] = (as_fact(value, n),)
    return facts


def entry(kind, n: int = 13) -> dict:
    """An anatomy entry's facts: its type."""
    return {A.TYPE: (as_fact(kind, n),)}


def factset(sessions: dict, events: dict | None = None, anatomy: dict | None = None, unlisted=()) -> FactSet:
    """The FactSet of these objects, each event's anchor its own unit (S20 + its number); ``unlisted``: the kept
    unlisted statements (3.2.6)."""
    events = events or {}
    return FactSet(encounter={}, people={}, sections={}, sessions=sessions, anatomy=anatomy or {}, lesions={},
                   events=events, anchors={e: Anchor((unit(20 + e.number),), None, None) for e in events},
                   unlisted=tuple(unlisted), pair_controls={}, completeness={})


def ent(*reached, approach=ORAL, through=None, completion=Completion.COMPLETE, anatomy=None, status=Status.PERFORMED,
        kind=ENTEROSCOPY, unlisted=()) -> FactSet:
    """One enteroscopy session X1 (examination E1, a biopsy E2) reaching ``reached``, its approach oral and its
    completion supported complete by default (``completion=None``: a silent slot, which the deeper class reads as
    satisfied - D217)."""
    return factset({X1: session(kind, approach=approach, through=through, reached=reached, completion=completion)},
                   {E1: event(Kind.EXAMINATION, X1, status=status, n=14), E2: event(Kind.BIOPSY, X1, n=15)},
                   anatomy, unlisted)


def unlisted_act(kind: Kind | None = Kind.EXAMINATION, in_session: Id | None = X1, n: int = 30,
                 what: UnlistedWhat = UnlistedWhat.ACT) -> UnlistedStatement:
    """A kept unlisted statement (3.2.6), at S<n>: an act by default (rule 3's synthetic doubted act, D216)."""
    return UnlistedStatement(units=(unit(n),), what=what, kind=kind, session=in_session)


def conflict(value, readings=(), n: int = 1) -> Fact:
    """3.3 row 1 as facts.factset builds a fact a CONFLICT doubt names: contradicted (contradicted_by_pass1), pass 1's
    claim kept (state supported, its value), the doubt's readings its only options (refute-4c-r2 A3, p04)."""
    return Fact(Result.CONTRADICTED, value, FactState.SUPPORTED, tuple(readings), (Reason.CONTRADICTED_BY_PASS1,),
                (unit(n),))


def empty(readings=(), reason: Reason = Reason.DOUBT_STATED, n: int = 1) -> Fact:
    """An EMPTY slot a doubt names (3.3 row 2 before row 3, as facts.factset builds it): no claim (state None, no
    value), result unknown, the doubt's reason, its readings kept as the options."""
    return Fact(Result.UNKNOWN, None, None, tuple(readings), (reason,), (unit(n),))


def held(fact: str, attribute: Attribute, subject: Id, result: Result, kind: ItemKind, cause: str,
         reason: Reason | None, spans, rank: int) -> HeldFact:
    return HeldFact(fact=fact, attribute=attribute, subject=subject, result=result, kind=kind, cause=cause,
                    reason=reason, spans=tuple(spans), rank=rank)


Q, X = ItemKind.QUESTION, ItemKind.EXPLANATION
EXTENT, PROCEDURE, STATUS = 14, 8, 4


def reach_unknown(spans, subject: Id = X1) -> HeldFact:
    """The class's own reach not stated (P3): a question, cause reading_unknown, reason silent."""
    return held('extent', A.REACHED, subject, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, spans, EXTENT)


def beyond_reached(spans, subject: Id = X1) -> HeldFact:
    """A point beyond the jejunal class (an ileal point) supported among the reached points: an explanation."""
    return held('extent', A.REACHED, subject, Result.SUPPORTED, X, C.CLASS_CAUSE, None, spans, EXTENT)


def truths(R: FactSet, session_id: Id = X1) -> dict:
    return {exam_class: C.fits(exam_class, session_id, R) for exam_class in C.CLASSES}


T, U, FF = C.Truth.T, C.Truth.U, C.Truth.F


# --- the class of a code (D108) ---------------------------------------------------------------------------------------


class CodeClassTests(SimpleTestCase):
    def test_every_catalogue_enteroscopy_code_has_exactly_one_class_and_no_other_code_has_one(self):
        """R4's pin: every catalogue code of the family in exactly one class, no other code in any - and v1's own
        code_class, computed here, by value for every catalogue code."""
        family = {str(code) for code, profile in catalogue.CODES.items() if profile.family is ENTEROSCOPY}
        self.assertEqual(family, set(FAMILY_CODES))
        self.assertEqual({code: C.code_class(code) for code in family}, FAMILY_CODES)
        for code in catalogue.CODES:
            with self.subTest(code=code):
                ours = C.code_class(str(code))
                self.assertEqual(ours.value if ours is not None else '', v1_classes.code_class(str(code)))
        for code in ('4436', '044361', '44361 ', '44399', '', 'x'):
            self.assertIsNone(C.code_class(code))

    def test_the_tables_are_catalogues(self):
        """One table decides each rule (step 1e's): the oral and the route classes, and the entry each route needs;
        the approaches each class accepts (D219: transanal for the pouch class only); the points beyond the jejunal
        class (D218: the ileal points and every point of the large bowel's regions)."""
        self.assertEqual(C.ORAL_CLASSES, {JEJUNAL, ILEAL})
        self.assertEqual(C.ROUTE_CLASSES, {STOMA, POUCH})
        self.assertEqual(dict(C.ROUTE_ANATOMY), {THROUGH_STOMA: AnatomyType.STOMA, THROUGH_POUCH: AnatomyType.ILEAL_POUCH})
        self.assertEqual(catalogue.ENTEROSCOPY_DEEPER, {ILEAL})
        self.assertEqual(C.STOPPED_SHORT, {Completion.INCOMPLETE, Completion.TERMINATED})
        self.assertEqual(dict(C.CLASS_APPROACHES), {JEJUNAL: {ORAL}, ILEAL: {ORAL}, STOMA: {THROUGH_STOMA},
                                                    POUCH: {THROUGH_POUCH, Approach.TRANSANAL}})
        large_bowel = {point for point in Extent if AN.region(point) in (AN.Region.COLON, AN.Region.RECTUM,
                                                                          AN.Region.ANUS)}
        self.assertEqual(C.PAST_THE_ILEUM, large_bowel)
        self.assertEqual(dict(C.BEYOND), {JEJUNAL: catalogue.ENTEROSCOPY_CLASS_REACH[ILEAL] | large_bowel})
        self.assertTrue({Extent.ILEOCECAL_VALVE, Extent.CECUM, Extent.APPENDICEAL_ORIFICE, Extent.COLON,
                         Extent.SIGMOID_COLON, Extent.RECTUM, Extent.ANAL_CANAL} <= C.BEYOND[JEJUNAL])
        self.assertTrue({Extent.SMALL_BOWEL, Extent.JEJUNUM, Extent.ANASTOMOSIS, Extent.POUCH, Extent.STOMA,
                         Extent.FOURTH_PORTION_DUODENUM}.isdisjoint(C.BEYOND[JEJUNAL]))


# --- R4 ClassesThatFit: READY controls --------------------------------------------------------------------------------


class ClassesThatFit(SimpleTestCase):
    def test_a_jejunal_reach_fits_44360_to_44373(self):
        """The finding's control (an oral push enteroscopy to the proximal jejunum): every jejunal code fits, and only
        the jejunal class does."""
        R = ent(Extent.JEJUNUM)
        self.assertEqual(truths(R), {JEJUNAL: T, ILEAL: U, STOMA: FF, POUCH: FF})
        for code, exam_class in FAMILY_CODES.items():
            if exam_class is JEJUNAL:
                with self.subTest(code=code):
                    self.assertEqual((C.class_misfit(code, X1, R), C.enteroscopy_hold(code, (E2,), R),
                                      C.misfit_form(code, X1, R)), ((), (), None))

    def test_an_ileal_reach_fits_44376_to_44379(self):
        for point in (Extent.ILEUM, Extent.TERMINAL_ILEUM, Extent.NEO_TERMINAL_ILEUM):
            R = ent(point)
            with self.subTest(reach=point):
                self.assertEqual(truths(R)[ILEAL], T)
                for code in ('44376', '44377', '44378', '44379'):
                    self.assertEqual(C.class_misfit(code, X1, R), ())

    def test_an_ileoscopy_through_its_stoma_fits_44380_to_44384(self):
        """D108's stoma class, under D114's rule that the route is the examination's own: the approach through_stoma
        and the entry passed through a stoma. (v1's control was held for want of route words; v2 has the approach.)"""
        R = ent(Extent.NEO_TERMINAL_ILEUM, approach=THROUGH_STOMA, through=Y1, anatomy={Y1: entry(AnatomyType.STOMA)})
        self.assertEqual(truths(R), {JEJUNAL: FF, ILEAL: FF, STOMA: T, POUCH: FF})
        self.assertEqual(C.routes(X1, R), {THROUGH_STOMA})
        for code in ('44380', '44381', '44382', '44384'):
            self.assertEqual(C.class_misfit(code, X1, R), ())

    def test_a_pouch_examination_through_its_ileal_pouch_fits_44385_and_44386(self):
        """A reach at the pouch itself, or into the pre-pouch ileum (D114's pouchoscopy), through the ileal pouch."""
        for point in (Extent.POUCH, Extent.ILEUM):
            R = ent(point, approach=THROUGH_POUCH, through=Y1, anatomy={Y1: entry(AnatomyType.ILEAL_POUCH)})
            with self.subTest(reach=point):
                self.assertEqual(truths(R)[POUCH], T)
                self.assertEqual(C.routes(X1, R), {THROUGH_POUCH})
                self.assertEqual((C.class_misfit('44385', X1, R), C.class_misfit('44386', X1, R)), ((), ()))

    def test_the_points_passed_on_the_way_never_keep_a_class_from_fitting(self):
        """reached lists the points the endoscope reached (P19): the duodenum passed on the way to the jejunum, or the
        jejunum on the way to the ileum, leaves the class's own reach reached."""
        self.assertEqual(truths(ent(Extent.SECOND_PORTION_DUODENUM, Extent.JEJUNUM))[JEJUNAL], T)
        self.assertEqual(truths(ent(Extent.JEJUNUM, Extent.ILEUM))[ILEAL], T)


# --- R4 FindingInputs: each was READY at 437b708bb --------------------------------------------------------------------


class FindingInputs(SimpleTestCase):
    def test_d108_44377_on_an_oral_enteroscopy_to_the_mid_jejunum_is_held_with_the_class_question(self):
        """The finding's exact input: 44377 ('including ileum') on an oral double-balloon enteroscopy that stopped in the
        jejunum. Its own reach is not stated (a question, never READY), and the jejunal class fits: v1's class
        question."""
        R = ent(Extent.JEJUNUM)
        self.assertEqual(C.class_misfit('44377', X1, R), (reach_unknown([unit(4)]),))
        self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (reach_unknown([unit(4)]),))

    def test_d108_44361_on_a_reach_into_the_proximal_ileum_is_held_with_the_class_question(self):
        """44361 is 'not including ileum': a supported ileal point is established beyond its class (an explanation, v1's
        class form; refute-4c-r1 DQ2's fail-closed reading, NOTES.md Q2)."""
        R = ent(Extent.ILEUM)
        self.assertEqual(C.class_misfit('44361', X1, R), (beyond_reached([unit(4)]),))
        self.assertEqual(C.misfit_form('44361', X1, R), C.ClassForm.CLASS)

    def test_d108_one_session_fits_44361_and_holds_44377(self):
        """The two codes D108's second pin proposes for the one biopsy: the class judges each alone (their competition
        is the combination's, step 4d)."""
        R = ent(Extent.JEJUNUM)
        self.assertEqual((C.class_misfit('44361', X1, R), len(C.class_misfit('44377', X1, R))), ((), 1))

    def test_d108_the_stoma_and_pouch_codes_on_an_oral_enteroscopy_are_held(self):
        """44382 and 44386 on the oral enteroscopy to the mid jejunum: the approach is established oral (an
        explanation), no entry was passed through (a question), and their reach is not stated (a question)."""
        R = ent(Extent.JEJUNUM)
        for code in ('44382', '44386'):
            with self.subTest(code=code):
                self.assertEqual(C.class_misfit(code, X1, R), (
                    held('procedure', A.APPROACH, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(3)], PROCEDURE),
                    held('procedure', A.THROUGH, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, [unit(4)],
                         PROCEDURE),
                    reach_unknown([unit(4)])))
                self.assertEqual(C.misfit_form(code, X1, R), C.ClassForm.CLASS)

    def test_d108_d204_a_reach_at_the_bulb_or_any_portion_of_the_duodenum_fits_no_class(self):
        """A push enteroscopy stopped at the bulb, the second portion (v1's landmark for "third portion" words), the
        duodenum, the ampulla - or, D204, the third or fourth portion: no class fits, R6's extent question."""
        for point in (Extent.DUODENAL_BULB, Extent.SECOND_PORTION_DUODENUM, Extent.THIRD_PORTION_DUODENUM,
                      Extent.FOURTH_PORTION_DUODENUM, Extent.DUODENUM, Extent.AMPULLA):
            R = ent(point)
            with self.subTest(reach=point):
                self.assertEqual(truths(R), {JEJUNAL: U, ILEAL: U, STOMA: FF, POUCH: FF})
                for code in ('44360', '44361', '44369', '44376', '44377'):
                    self.assertEqual(C.class_misfit(code, X1, R), (reach_unknown([unit(4)]),))
                    self.assertEqual(C.misfit_form(code, X1, R), C.ClassForm.EXTENT)

    def test_d108_a_reach_named_only_as_the_small_bowel_fits_no_class(self):
        """As D28 reads its classes: the small bowel named as such may be the jejunum or the ileum."""
        R = ent(Extent.SMALL_BOWEL)
        self.assertEqual(truths(R)[JEJUNAL], U)
        self.assertEqual(truths(R)[ILEAL], U)
        self.assertEqual(C.misfit_form('44361', X1, R), C.ClassForm.EXTENT)

    def test_d108_the_push_enteroscopy_stated_incomplete_at_the_second_portion_is_held(self):
        """The finding's incomplete variant: still the extent question; the jejunal class reads no completion (its
        52/53 consideration and D61's warn are assess's)."""
        R = ent(Extent.SECOND_PORTION_DUODENUM, completion=Completion.INCOMPLETE)
        self.assertEqual(C.class_misfit('44369', X1, R), (reach_unknown([unit(4)]),))
        self.assertEqual(C.misfit_form('44369', X1, R), C.ClassForm.EXTENT)


# --- D204: the third and fourth portions of the duodenum stand where v1's duodenum stands ------------------------------


class ThirdAndFourthPortions(SimpleTestCase):
    def test_d204_they_stand_where_v1s_duodenum_stands_in_every_class(self):
        """Every class, every approach and anatomy that would otherwise fit: a reach at the third or fourth portion
        decides exactly as a reach at v1's duodenum or second portion does - the same truths, the same witnesses (but
        the reach cited), the same form - and in no class's reach."""
        def outcome(point):
            out = []
            for approach, through, anatomy in ((ORAL, None, None),
                                               (THROUGH_STOMA, Y1, {Y1: entry(AnatomyType.STOMA)}),
                                               (THROUGH_POUCH, Y1, {Y1: entry(AnatomyType.ILEAL_POUCH)})):
                R = ent(point, approach=approach, through=through, anatomy=anatomy)
                out.append(tuple((exam_class, C.fits(exam_class, X1, R), C.class_misfit(CODE_OF[exam_class], X1, R),
                                  C.misfit_form(CODE_OF[exam_class], X1, R)) for exam_class in C.CLASSES))
            return out

        expected = outcome(Extent.DUODENUM)
        self.assertEqual(outcome(Extent.SECOND_PORTION_DUODENUM), expected)
        for point in (Extent.THIRD_PORTION_DUODENUM, Extent.FOURTH_PORTION_DUODENUM):
            with self.subTest(reach=point):
                self.assertEqual(outcome(point), expected)
                self.assertFalse(any(point in reach for reach in catalogue.ENTEROSCOPY_CLASS_REACH.values()))
        self.assertTrue(all(fit is not T for row in expected for _, fit, _, _ in row))

    def test_d204_the_jejunum_beyond_them_still_fits_the_jejunal_class(self):
        self.assertEqual(truths(ent(Extent.FOURTH_PORTION_DUODENUM, Extent.JEJUNUM))[JEJUNAL], T)


# --- R4 RouteAndCompletion ---------------------------------------------------------------------------------------------


class RouteAndCompletion(SimpleTestCase):
    def test_d108_a_stoma_or_pouch_code_needs_the_entry_its_session_went_through(self):
        """The class's own reach and approach without the entry passed through: a question on through, or on the
        entry's type when that is not established - the class question (D43's stoma arm), never READY."""
        stoma = dict(approach=THROUGH_STOMA)
        cases = {
            'no entry passed through': (ent(Extent.ILEUM, **stoma), held(
                'procedure', A.THROUGH, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, [unit(4)], PROCEDURE)),
            'through not established': (ent(Extent.ILEUM, through=unresolved(Y1, n=9), **stoma,
                                            anatomy={Y1: entry(AnatomyType.STOMA)}), held(
                'procedure', A.THROUGH, X1, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                [unit(9)], PROCEDURE)),
            'its type not established': (ent(Extent.ILEUM, through=Y1, **stoma, anatomy={
                Y1: entry(unresolved(AnatomyType.STOMA, Reason.CONTROL_INCOHERENT, n=13))}), held(
                'procedure', A.TYPE, Y1, Result.UNRESOLVED, Q, 'appraisal:control_incoherent', Reason.CONTROL_INCOHERENT,
                [unit(13)], PROCEDURE)),
            'a denial of passing through': (ent(Extent.ILEUM, through=neg(Y1, 9), **stoma,
                                                anatomy={Y1: entry(AnatomyType.STOMA)}), held(
                'procedure', A.THROUGH, X1, Result.NEGATED, Q, C.CLASS_CAUSE, None, [unit(9)], PROCEDURE)),
        }
        for name, (R, witness) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(C.class_misfit('44382', X1, R), (witness,))
                self.assertEqual(C.misfit_form('44382', X1, R), C.ClassForm.CLASS)

    def test_d108_an_examination_stated_incomplete_never_fits_the_ileal_class(self):
        """D43, D56 and D72 as the deeper class reads them (D217): a completion established incomplete or terminated,
        or an examination of the session established attempted with none established performed, holds 44377 on its
        ileal reach with an explanation; any completion that is neither established nor silent, or an examination
        whose status leaves attempted_not_completed open, with a question - a contradicted fact at rank 1
        (conflict:examination), a doubted status at rank 2 (performed_status), any other at the class row (extent).
        v1's incomplete form ("is stated to be incomplete") only where a deeper part's own claim states the stopping
        short (refute-4c-r1 E); a stopping short that is only possible (a doubt's reading, a control left unrejected,
        a denial of incompleteness) or not claimed at all (a complete claim not established) is v1's class form."""
        complete, INCOMPLETE, CLASS = Completion.COMPLETE, C.ClassForm.INCOMPLETE, C.ClassForm.CLASS
        row, conflict_row, doubt_row = ('extent', EXTENT), ('conflict:examination', 1), ('performed_status', 2)
        cases = {
            'supported incomplete': (dict(completion=sup(Completion.INCOMPLETE, 11)), FF, A.COMPLETION, INCOMPLETE,
                                     row),
            'supported terminated': (dict(completion=sup(Completion.TERMINATED, 11)), FF, A.COMPLETION, INCOMPLETE,
                                     row),
            'negated complete': (dict(completion=neg(complete, 11)), FF, A.COMPLETION, INCOMPLETE, row),
            'unresolved incomplete': (dict(completion=unresolved(Completion.INCOMPLETE, n=11)), U, A.COMPLETION,
                                      INCOMPLETE, row),
            'a doubt reading incomplete': (dict(completion=doubted(complete, [Completion.INCOMPLETE], 11)), U,
                                           A.COMPLETION, CLASS, row),
            'contradicted': (dict(completion=contradicted([complete, Completion.INCOMPLETE], 11)), U, A.COMPLETION,
                             INCOMPLETE, conflict_row),
            'its control not rejected': (dict(completion=unresolved(complete, Reason.CONTROL_INCOHERENT,
                                                                    [Completion.INCOMPLETE], 11)), U, A.COMPLETION,
                                         CLASS, row),
            'a denial of incompleteness not established': (
                dict(completion=unresolved(Completion.INCOMPLETE, n=11, state=FactState.NEGATED)), U, A.COMPLETION,
                CLASS, row),
            'negated incomplete (perhaps terminated)': (dict(completion=neg(Completion.INCOMPLETE, 11)), U,
                                                        A.COMPLETION, CLASS, row),
            # D217 (refute-4c-r2 UNRES): unresolved in any form, a doubt whatever its readings
            'unresolved complete': (dict(completion=unresolved(complete, n=11)), U, A.COMPLETION, CLASS, row),
            'a doubt reading complete': (dict(completion=doubted(complete, [complete], 11)), U, A.COMPLETION, CLASS,
                                         row),
            'the examination attempted': (dict(status=Status.ATTEMPTED_NOT_COMPLETED), FF, A.STATUS, INCOMPLETE, row),
            'the examination doubted attempted': (
                dict(status=doubted(Status.PERFORMED, [Status.ATTEMPTED_NOT_COMPLETED], 14)), U, A.STATUS, CLASS,
                doubt_row),
            'the examination status not established': (
                dict(status=unresolved(Status.PERFORMED, n=14)), U, A.STATUS, CLASS, row),
        }
        self.assertEqual(truths(ent(Extent.ILEUM))[ILEAL], T)
        for name, (options, truth, attribute, form, (fact, rank)) in cases.items():
            R = ent(Extent.ILEUM, **options)
            with self.subTest(case=name):
                fit = C.class_fit(ILEAL, X1, R)
                self.assertEqual(fit.truth, truth)
                (witness,) = fit.witnesses
                self.assertEqual((witness.fact, witness.attribute, witness.subject, witness.rank, witness.kind),
                                 (fact, attribute, E1 if attribute is A.STATUS else X1, rank,
                                  X if truth is FF else Q))
                self.assertEqual(C.misfit_form('44377', X1, R), form)
        for name, completion in (('supported complete', complete), ('silent', None), ('silent, as facts reads a '
                                                                                       'slot it does not hold', F.SILENT)):
            with self.subTest(control=name):
                self.assertEqual(truths(ent(Extent.ILEUM, completion=completion))[ILEAL], T)

    def test_d108_the_jejunal_class_reads_its_reach_only(self):
        """Like D43's limited class: an examination stated incomplete, or begun and not completed, at a jejunal reach
        still fits 44360-44373; the deeper class is the one an incompleteness withholds."""
        for options in (dict(completion=Completion.INCOMPLETE), dict(completion=Completion.TERMINATED),
                        dict(status=Status.ATTEMPTED_NOT_COMPLETED)):
            with self.subTest(options=options):
                self.assertEqual(C.class_misfit('44361', X1, ent(Extent.JEJUNUM, **options)), ())

    def test_d72_reads_every_examination_of_the_session_and_no_other(self):
        """The examinations of a session are found by their own kind and session facts (4.9's EXAMINATION role): an
        attempted examination of another session, or an attempted act that is no examination, never touches the
        class."""
        R = factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE),
                     X2: session(reached=[Extent.ILEUM])},
                    {E1: event(Kind.EXAMINATION, X1, n=14),
                     E3: event(Kind.EXAMINATION, X2, status=Status.ATTEMPTED_NOT_COMPLETED, n=16),
                     E4: event(Kind.BIOPSY, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=17)})
        self.assertEqual(C.examinations(X1, R), (E1,))
        self.assertEqual(C.fits(ILEAL, X1, R), T)
        # an examination whose session is only possibly this one counts (in any state): fail-closed - a question, since
        # its tie to this session is only possible (refute-4c-r1 F); established as this session's, an explanation
        R2 = factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                     {E3: event(Kind.EXAMINATION, unresolved(X2, options=[X1], n=16),
                                status=Status.ATTEMPTED_NOT_COMPLETED, n=16)})
        self.assertEqual(C.examinations(X1, R2), (E3,))
        self.assertEqual(C.fits(ILEAL, X1, R2), U)
        self.assertEqual(C.class_misfit('44377', X1, R2), (
            held('extent', A.SESSION, E3, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                 [unit(16)], EXTENT),))
        self.assertEqual(C.misfit_form('44377', X1, R2), C.ClassForm.CLASS)
        R3 = factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                     {E3: event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=16)})
        self.assertEqual(C.fits(ILEAL, X1, R3), FF)


# --- R4 LeftToTheOtherRules ---------------------------------------------------------------------------------------------


class LeftToTheOtherRules(SimpleTestCase):
    def test_d108_a_reach_not_established_is_a_question_with_its_own_cause(self):
        """A reached point that is not established leaves the class's reach unknown: a question citing that point,
        with the cause its own result and reason give (4.4) - never an explanation; a contradicted one asks rank 1,
        conflict:examination (requirements.py's RANK rule, which D217 applies to the class)."""
        for point, cause, fact, rank in (
                (unresolved(Extent.ILEUM, Reason.APPRAISAL_CONTRADICTS, n=4), 'appraisal:contradicts', 'extent',
                 EXTENT),
                (unresolved(Extent.ILEUM, Reason.WORDS_NOT_IN_UNITS, n=4), 'unestablished:words_not_in_units',
                 'extent', EXTENT),
                (unresolved(Extent.ILEUM, Reason.APPRAISAL_QUALIFIED_HISTORY_ONLY, n=4), 'appraisal:qualified',
                 'extent', EXTENT),
                (doubted(Extent.JEJUNUM, [Extent.ILEUM], 4), C.READING_UNKNOWN, 'extent', EXTENT),
                (contradicted([Extent.JEJUNUM, Extent.ILEUM], 4), C.READING_CONTRADICTED, 'conflict:examination', 1)):
            R = ent(point)
            with self.subTest(cause=cause):
                (witness,) = C.class_misfit('44377', X1, R)
                self.assertEqual(witness, held(fact, A.REACHED, X1, point.result, Q, cause, point.reasons[0],
                                               [unit(4)], rank))
        self.assertEqual(C.class_misfit('44377', X1, ent()), (reach_unknown([]),))  # no point at all

    def test_a_reach_denied_whole_is_an_explanation(self):
        """F only when every point of the class's reach is stated not reached (the point itself, or a point containing
        it): 'the ileum was not reached' explains 44377's hold, and leaves the jejunal class alone."""
        R = ent(Extent.JEJUNUM, neg(Extent.ILEUM, 5))
        self.assertEqual(truths(R), {JEJUNAL: T, ILEAL: FF, STOMA: FF, POUCH: FF})
        self.assertEqual(C.class_misfit('44377', X1, R), (
            held('extent', A.REACHED, X1, Result.NEGATED, X, C.CLASS_CAUSE, None, [unit(4), unit(5)], EXTENT),))
        self.assertEqual(truths(ent(neg(Extent.SMALL_BOWEL, 4)))[JEJUNAL], FF)
        # the pouch class's reach is the ileum or the pouch: both must be denied
        pouch = dict(approach=THROUGH_POUCH, through=Y1, anatomy={Y1: entry(AnatomyType.ILEAL_POUCH)})
        self.assertEqual(C.fits(POUCH, X1, ent(neg(Extent.ILEUM, 4), **pouch)), U)
        self.assertEqual(C.fits(POUCH, X1, ent(neg(Extent.ILEUM, 4), neg(Extent.POUCH, 5), **pouch)), FF)
        self.assertEqual(C.fits(POUCH, X1, ent(neg(Extent.TERMINAL_ILEUM, 4), **pouch)), U)

    def test_a_point_beyond_the_jejunal_class_keeps_44361_from_fitting(self):
        """D218 (refute-4c-r1 DQ2, refute-4c-r2 DQ2-EXT): the jejunal class is 'not including ileum', so a point the oral
        route reaches only through the ileum - an ileal point, and every point of the large bowel - reached beside the
        jejunal one holds 44360-44373: an explanation when supported, a question when only possible (unresolved,
        doubted, or denied without being established), never when it is established not reached. The deeper class is
        unaffected: 44377 fits the same session."""
        R = ent(Extent.JEJUNUM, Extent.ILEUM)
        self.assertEqual(truths(R), {JEJUNAL: FF, ILEAL: T, STOMA: FF, POUCH: FF})
        self.assertEqual(C.class_misfit('44361', X1, R), (beyond_reached([unit(4), unit(5)]),))
        self.assertEqual(C.enteroscopy_hold('44361', (E2,), R), (beyond_reached([unit(4), unit(5)]),))
        self.assertEqual(C.misfit_form('44361', X1, R), C.ClassForm.CLASS)
        for beyond in (Extent.TERMINAL_ILEUM, Extent.NEO_TERMINAL_ILEUM):
            self.assertEqual(C.fits(JEJUNAL, X1, ent(Extent.JEJUNUM, beyond)), FF)
        for name, point in (('unresolved', unresolved(Extent.ILEUM, n=5)),
                            ('a doubt reading the ileum', doubted(Extent.JEJUNUM, [Extent.ILEUM], 5)),
                            ('a denial not established', unresolved(Extent.ILEUM, n=5, state=FactState.NEGATED)),
                            ('a doubt reading the cecum', doubted(Extent.JEJUNUM, [Extent.CECUM], 5)),
                            ('the colon, unresolved', unresolved(Extent.COLON, n=5)),
                            ('contradicted', contradicted([Extent.JEJUNUM, Extent.TERMINAL_ILEUM], 5))):
            R = ent(Extent.JEJUNUM, point)
            with self.subTest(beyond=name):
                self.assertEqual(C.fits(JEJUNAL, X1, R), U)
                (witness,) = C.class_misfit('44361', X1, R)
                self.assertEqual((witness.attribute, witness.kind, witness.result, witness.rank),
                                 (A.REACHED, Q, point.result, 1 if point.result is Result.CONTRADICTED else EXTENT))
        # an ileal point only possible and no jejunal point: the question cites that point (its own cause)
        (witness,) = C.class_misfit('44361', X1, ent(unresolved(Extent.ILEUM, n=4)))
        self.assertEqual(witness, held('extent', A.REACHED, X1, Result.UNRESOLVED, Q, 'appraisal:unclear',
                                       Reason.APPRAISAL_UNCLEAR, [unit(4)], EXTENT))
        # controls: the ileum established not reached, points passed on the way, other points in no class, and the
        # small bowel named as such (D218: it contains the jejunal reach as well as the ileum - no beyond point)
        for others in ((neg(Extent.ILEUM, 5),), (Extent.SECOND_PORTION_DUODENUM,), (Extent.FOURTH_PORTION_DUODENUM,),
                       (neg(Extent.SMALL_BOWEL, 5), Extent.JEJUNUM), (Extent.POUCH,), (Extent.STOMA,),
                       (Extent.ANASTOMOSIS,), (neg(Extent.CECUM, 5),), (Extent.SMALL_BOWEL,),
                       (unresolved(Extent.SMALL_BOWEL, n=5),)):
            with self.subTest(control=others):
                self.assertEqual(C.fits(JEJUNAL, X1, ent(Extent.JEJUNUM, *others)), T)
        self.assertEqual(dict(C.BEYOND), {JEJUNAL: catalogue.ENTEROSCOPY_CLASS_REACH[ILEAL] | C.PAST_THE_ILEUM})
        # the reading's one release (D218, named for 6a's P-MONO): deleting the beyond member releases the jejunal
        # class, P-MONO's deleted-member weakening (Monotone names it as the only release it allows)
        for beyond in (Extent.ILEUM, Extent.CECUM):
            self.assertEqual((C.fits(JEJUNAL, X1, ent(Extent.JEJUNUM, beyond)), C.fits(JEJUNAL, X1, ent(Extent.JEJUNUM))),
                             (FF, T))

    def test_d108_classes_never_ready_never_exclude_and_other_codes_have_no_class_hold(self):
        """The module returns witnesses only. A code of another family has no class and no elsewhere hold, whatever the
        document (R4's pin over every catalogue code)."""
        R = factset({X1: session(approach=ORAL, reached=[Extent.JEJUNUM]), X2: session(SessionKind.EGD)},
                    {E1: event(Kind.EXAMINATION, X1, n=14), E3: event(Kind.ABLATION, X2, n=16)})
        for code in catalogue.CODES:
            if str(code) not in FAMILY_CODES:
                with self.subTest(code=code):
                    self.assertEqual((C.enteroscopy_hold(str(code), (E3,), R), C.class_misfit(str(code), X1, R),
                                      C.misfit_form(str(code), X1, R), C.act_elsewhere(str(code), R)),
                                     ((), (), None, ()))
        self.assertEqual(C.enteroscopy_hold('99999', (E3,), R), ())

    def test_d108_no_cause_and_no_fact_names_a_vendor(self):
        """Causes are operator data that name no vendor (4.4, 4.12): the joined-form pattern of 4.12 and
        customer_api's own net, over every witness of a battery of inputs."""
        from studio import customer_api
        witnesses = []
        for R in (ent(), ent(Extent.JEJUNUM), ent(unresolved(Extent.ILEUM, Reason.APPRAISAL_MISSING, n=4)),
                  ent(Extent.ILEUM, completion=Completion.INCOMPLETE, approach=None),
                  ent(Extent.ILEUM, approach=THROUGH_POUCH, through=Y1,
                      anatomy={Y1: entry(doubted(AnatomyType.ILEAL_POUCH, [AnatomyType.GASTRIC_POUCH]))}),
                  ent(Extent.ILEUM, completion=conflict(Completion.COMPLETE, n=11),
                      status=doubted(Status.PERFORMED, [Status.ATTEMPTED_NOT_COMPLETED], 14)),
                  ent(Extent.ILEUM, status=Status.ATTEMPTED_NOT_COMPLETED, unlisted=[unlisted_act()])):
            for code in FAMILY_CODES:
                witnesses += C.enteroscopy_hold(code, (E2,), R)
        self.assertTrue(witnesses)
        conflicts = {RQ.fact_key(RQ.FactKey.CONFLICT, kind) for kind in Kind}
        self.assertTrue(any(witness.fact in conflicts for witness in witnesses))
        self.assertTrue(any(witness.cause == C.UNLISTED for witness in witnesses))
        for witness in witnesses:
            for value in (witness.fact, witness.cause):
                self.assertIsNone(JOINED_VENDORS.search(value), value)
                self.assertIsNone(customer_api.FORBIDDEN.search(value), value)
            key = RQ.FactKey.CONFLICT if witness.fact in conflicts else RQ.FactKey(witness.fact)
            self.assertIn(witness.rank, {rank.value for rank in RQ.Rank})
            self.assertTrue(any(key in RQ.RANK[rank] and witness.rank == rank.value for rank in RQ.Rank), witness)


# --- refute-4c-r1: a doubt is never an absence (A, D), and silence is unknown (DQ4) ------------------------------------


class DoubtedAndSilentSlots(SimpleTestCase):
    def test_a_doubt_naming_an_empty_completion_slot_is_a_question(self):
        """refute-4c-r1 A (critical), hand-built: an EMPTY completion slot a doubt names (3.3 row 2 before row 3; the
        extent doubt D200 maps to the completion too) leaves every completion open - ILEAL U, one question on the
        completion carrying the doubt's reason - whatever its readings. It was T: the empty slot read as silence, and
        silence as no incompleteness, so 44377 was READY on 'it is unclear whether the examination was completed'."""
        for reason, readings in ((Reason.DOUBT_STATED, [Completion.INCOMPLETE]),
                                 (Reason.DOUBT_STATED, [Completion.TERMINATED]),
                                 (Reason.DOUBT_STATED, [Completion.COMPLETE, Completion.INCOMPLETE]),
                                 (Reason.DOUBT_UNCLEAR, [Completion.INCOMPLETE]),
                                 (Reason.DOUBT_STATED, [Completion.COMPLETE])):
            R = ent(Extent.ILEUM, completion=empty(readings, reason, 11))
            with self.subTest(reason=reason, readings=readings):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.class_misfit('44377', X1, R), (
                    held('extent', A.COMPLETION, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, reason, [unit(11)],
                         EXTENT),))
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), C.class_misfit('44377', X1, R))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)  # only possible: not "stated"

    def test_d217_a_silent_completion_fits_the_deeper_class(self):
        """D217 (refute-4c-r2 DQ4-CARRIED; 4c's Q2 option (b)): a SILENT completion slot - nothing stated, no doubt naming
        it - states no incompleteness (D108, D56; the installed reading), so 44376-44379 fit an ileal reach whose
        document does not state its completion. A slot a doubt names, whatever its readings, is still a question
        (refute-4c-r1 A: DoubtedAndSilentSlots' first test). The jejunal, stoma and pouch classes read no
        completion."""
        for completion in (None, F.SILENT):
            R = ent(Extent.ILEUM, completion=completion)
            with self.subTest(completion=completion):
                self.assertEqual(C.fits(ILEAL, X1, R), T)
                for code in ('44376', '44377', '44378', '44379'):
                    self.assertEqual((C.class_misfit(code, X1, R), C.enteroscopy_hold(code, (E2,), R),
                                      C.misfit_form(code, X1, R)), ((), (), None))
        # a silent slot is silence alone: a reading kept beside it, a doubt's reason or a failed check is not silence
        for name, completion in (('a reading kept', Fact(Result.UNKNOWN, None, None, (Completion.COMPLETE,),
                                                         (Reason.SILENT,), (unit(11),))),
                                 ('a doubt reason beside silence', Fact(Result.UNKNOWN, None, None, (),
                                                                        (Reason.SILENT, Reason.DOUBT_UNCLEAR), ())),
                                 ('a finding beside silence', Fact(Result.UNKNOWN, None, None, (),
                                                                   (Reason.SILENT, Reason.SESSION_INCONSISTENT), ())),
                                 ('unresolved, no claim', Fact(Result.UNRESOLVED, None, None, (),
                                                               (Reason.SESSION_INCONSISTENT,), ())),
                                 ('no reason at all', Fact(Result.UNKNOWN, None, None, (), (), ()))):
            with self.subTest(not_silent=name):
                self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, completion=completion)), U)
        self.assertEqual(C.class_misfit('44361', X1, ent(Extent.JEJUNUM, completion=None)), ())
        self.assertEqual(C.class_misfit('44382', X1, ent(Extent.ILEUM, completion=None, approach=THROUGH_STOMA,
                                                         through=Y1, anatomy=STOMA_ENTRY)), ())
        self.assertEqual(C.class_misfit('44386', X1, ent(Extent.POUCH, completion=None, approach=THROUGH_POUCH,
                                                         through=Y1, anatomy=POUCH_ENTRY)), ())

    def test_a_doubt_naming_an_empty_examination_session_slot_places_it_in_doubt(self):
        """refute-4c-r1 A2 and D217's SILENT-EXAM (refute-4c-r2): an examination begun and not completed whose session
        slot is empty - named by a session doubt (whatever its readings), or truly silent - may be X1's examination
        (4.2: a silent fact leaves every value possible): ILEAL U, a question resting on that session fact (its tie is
        only possible), never T. Established as X1's, an explanation; established as another session's (the EGD X2,
        which the FactSet holds: a session it does not hold is MissingSessionIdentifiers'), no examination of X1."""
        def exam(placed):
            return beside_an_egd(factset(
                {X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                {E1: event(Kind.EXAMINATION, placed, status=Status.ATTEMPTED_NOT_COMPLETED, n=14),
                 E2: event(Kind.BIOPSY, X1, n=15)}))

        for readings in ([X1], [X2], []):
            R = exam(empty(readings, n=14))
            with self.subTest(readings=readings):
                self.assertEqual(C.examinations(X1, R), (E1,))
                self.assertEqual(C.class_misfit('44377', X1, R), (
                    held('extent', A.SESSION, E1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.DOUBT_STATED,
                         [unit(14)], EXTENT),))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)
        R = exam(F.SILENT)
        self.assertEqual(C.examinations(X1, R), (E1,))
        self.assertEqual(C.class_misfit('44377', X1, R), (  # its own fact cites nothing: the status's units
            held('extent', A.SESSION, E1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, [unit(14)], EXTENT),))
        self.assertEqual(C.fits(ILEAL, X1, exam(X1)), FF)  # the control: established as X1's, an explanation
        self.assertEqual((C.examinations(X1, exam(X2)), C.fits(ILEAL, X1, exam(X2))), ((), T))

    def test_a_doubt_naming_an_empty_through_or_type_slot_doubts_the_oral_route(self):
        """A through slot left empty that a doubt names (its readings an entry that is a stoma or an ileal pouch), or
        the type slot of the entry passed through left empty, doubted or silent (4.2: every type possible), is D114's
        two-route doubt for the oral classes (U on through) and opens no route; a silent THROUGH doubts nothing (D114's
        problem 4: an anatomy the session did not pass through names no route)."""
        for name, options in (('through, a stoma', dict(through=empty([Y1], n=9), anatomy=STOMA_ENTRY)),
                              ('through, an ileal pouch', dict(through=empty([Y1], n=9), anatomy=POUCH_ENTRY)),
                              ('the type, reading a stoma', dict(through=Y1, anatomy={
                                  Y1: entry(empty([AnatomyType.STOMA], n=13))})),
                              ('the type, no reading', dict(through=Y1, anatomy={Y1: entry(empty([], n=13))})),
                              ('the type silent', dict(through=Y1, anatomy={Y1: entry(F.SILENT)}))):
            R = ent(Extent.ILEUM, **options)
            with self.subTest(slot=name):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                (witness,) = C.class_misfit('44377', X1, R)
                self.assertEqual((witness.attribute, witness.kind, witness.rank), (A.THROUGH, Q, PROCEDURE))
                self.assertEqual(C.routes(X1, R), frozenset())
                self.assertTrue(C.doubted_routes(X1, R))
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, anatomy=STOMA_ENTRY)), T)  # a silent through
        R = ent(Extent.ILEUM, approach=THROUGH_STOMA, through=empty([Y1], n=9), anatomy=STOMA_ENTRY)
        self.assertEqual(C.fits(STOMA, X1, R), U)
        self.assertEqual((C.routes(X1, R), C.doubted_routes(X1, R)), (frozenset(), {THROUGH_STOMA}))

    def test_a_denial_that_is_not_established_leaves_every_value_open(self):
        """refute-4c-r1 D (a false-READY path no explicit test pinned): a denial pass 2 did not establish - 'the
        examination was not complete', unresolved; 'the entry passed through is not an anastomosis', unresolved - may
        be wrong, and so may every other value: the completion may have stopped short (ILEAL U, on the completion), the
        entry may be a stoma or an ileal pouch (the two-route doubt). Read as its claimed value alone, each fitted."""
        R = ent(Extent.ILEUM, completion=unresolved(Completion.COMPLETE, n=11, state=FactState.NEGATED))
        self.assertEqual(C.fits(ILEAL, X1, R), U)
        (witness,) = C.class_misfit('44377', X1, R)
        self.assertEqual((witness.attribute, witness.kind, witness.cause), (A.COMPLETION, Q, 'appraisal:unclear'))
        R = ent(Extent.ILEUM, through=Y1,
                anatomy={Y1: entry(unresolved(AnatomyType.ANASTOMOSIS, n=13, state=FactState.NEGATED))})
        self.assertEqual(C.fits(ILEAL, X1, R), U)
        self.assertEqual(C.doubted_routes(X1, R), {THROUGH_STOMA, THROUGH_POUCH})
        # controls: the same values supported fit
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, completion=Completion.COMPLETE)), T)
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, through=Y1,
                                               anatomy={Y1: entry(AnatomyType.ANASTOMOSIS)})), T)


# --- r4c, D217: the deeper class's completion as a disqualifier (refute-4c-r2 A3, UNRES, DQ4-CARRIED) -------------------


ILEAL_CODES = ('44376', '44377', '44378', '44379')


def completion_question(found: Fact, cause: str, fact: str = 'extent', rank: int = EXTENT) -> HeldFact:
    """The one completion question D217 asks: about X1's completion, citing the fact's own unit (S11)."""
    return held(fact, A.COMPLETION, X1, found.result, Q, cause, found.reasons[0], [unit(11)], rank)


class CompletionAsADisqualifier(SimpleTestCase):
    def test_d217_a3_a_contradicted_completion_is_one_rank_1_question(self):
        """refute-4c-r2 A3 (critical; its probes p04 and p06): a completion pass 1 itself reported contradicted - a
        conflict doubt naming it, whatever value the claim keeps and whatever the doubt reads, or a contradicted claim
        whatever its sides, or a conflict on its empty slot - is U with ONE completion question at rank 1
        (conflict:examination, reading_contradicted, contradicted_by_pass1): 44376-44379 held, never READY. It was T:
        the kept value complete left no stopping short open, and nothing else held 44377."""
        complete, incomplete = Completion.COMPLETE, Completion.INCOMPLETE
        for name, completion in (
                ('p04: a conflict doubt, readings []', conflict(complete, n=11)),
                ('p04: a conflict doubt, readings [complete]', conflict(complete, [complete], 11)),
                ('p04: a conflict doubt, readings [incomplete]', conflict(complete, [incomplete], 11)),
                ('p06: the claim rewritten, the sides [complete]', contradicted([complete], 11)),
                ('both sides stated', contradicted([complete, incomplete], 11)),
                ('a conflict on the empty slot', Fact(Result.CONTRADICTED, None, None, (),
                                                      (Reason.CONTRADICTED_BY_PASS1,), (unit(11),)))):
            R = ent(Extent.ILEUM, completion=completion)
            question = completion_question(completion, C.READING_CONTRADICTED, 'conflict:examination', 1)
            with self.subTest(case=name):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                for code in ILEAL_CODES:
                    self.assertEqual(C.class_misfit(code, X1, R), (question,))
                    self.assertEqual(C.enteroscopy_hold(code, (E2,), R), (question,))
                # v1's incomplete form only where a side states the stopping short (refute-4c-r1 E)
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.INCOMPLETE
                                 if incomplete in completion.options and completion.state is FactState.CONTRADICTED
                                 else C.ClassForm.CLASS)

    def test_d217_a3_a_doubted_completion_is_one_question_whatever_its_readings(self):
        """refute-4c-r2 A3 (p02 (d), p04): a doubt naming the completion - its value complete kept, its readings none,
        complete or a stopping short, its basis stated or unclear - and a doubt naming its empty slot are each U with
        one completion question (extent, reading_unknown, the doubt's reason): 44377 held."""
        complete = Completion.COMPLETE
        for reason in (Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR):
            for readings in ([], [complete], [Completion.INCOMPLETE], [Completion.TERMINATED]):
                for slot, completion in (('the value kept', Fact(Result.UNKNOWN, complete, FactState.SUPPORTED,
                                                                 tuple(readings), (reason,), (unit(11),))),
                                         ('the empty slot', empty(readings, reason, 11))):
                    R = ent(Extent.ILEUM, completion=completion)
                    with self.subTest(reason=reason, readings=readings, slot=slot):
                        self.assertEqual(C.fits(ILEAL, X1, R), U)
                        self.assertEqual(C.enteroscopy_hold('44377', (E2,), R),
                                         (completion_question(completion, C.READING_UNKNOWN),))

    def test_d217_unres_an_unresolved_completion_in_any_form_is_one_question(self):
        """refute-4c-r2 UNRES (p02 (e)): a completion claimed complete that pass 2 did not establish - hedged ("appeared
        complete"), reported, detached, unclear, contradicted by pass 2, its control left unrejected, unappraised - is U
        with one completion question carrying its own cause; it was T (the claimed value alone was read)."""
        for reason, cause in ((Reason.QUALIFIED_HEDGED, 'unestablished:qualified:hedged'),
                              (Reason.QUALIFIED_REPORTED, 'unestablished:qualified:reported'),
                              (Reason.APPRAISAL_DETACHED, 'appraisal:detached'),
                              (Reason.APPRAISAL_UNCLEAR, 'appraisal:unclear'),
                              (Reason.APPRAISAL_CONTRADICTS, 'appraisal:contradicts'),
                              (Reason.APPRAISAL_QUALIFIED_HEDGED, 'appraisal:qualified'),
                              (Reason.CONTROL_INCOHERENT, 'appraisal:control_incoherent'),
                              (Reason.UNAPPRAISED, 'unestablished:unappraised')):
            completion = unresolved(Completion.COMPLETE, reason, n=11)
            R = ent(Extent.ILEUM, completion=completion)
            with self.subTest(reason=reason):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                for code in ILEAL_CODES:
                    self.assertEqual(C.enteroscopy_hold(code, (E2,), R), (completion_question(completion, cause),))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)

    def test_d217_established_incomplete_or_terminated_is_the_incomplete_explanation(self):
        """D217 (4c's Q5 as built): supported incomplete or terminated, or denied complete - F, one explanation on the
        completion (CLASS_CAUSE), v1's incomplete form; the controls fit: established complete, and silent."""
        for completion in (sup(Completion.INCOMPLETE, 11), sup(Completion.TERMINATED, 11),
                           neg(Completion.COMPLETE, 11)):
            R = ent(Extent.ILEUM, completion=completion)
            with self.subTest(completion=completion):
                self.assertEqual(C.fits(ILEAL, X1, R), FF)
                for code in ILEAL_CODES:
                    self.assertEqual(C.enteroscopy_hold(code, (E2,), R), (
                        held('extent', A.COMPLETION, X1, completion.result, X, C.CLASS_CAUSE, None, [unit(11)],
                             EXTENT),))
                    self.assertEqual(C.misfit_form(code, X1, R), C.ClassForm.INCOMPLETE)
        for completion in (sup(Completion.COMPLETE, 11), None):
            with self.subTest(control=completion):
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), ent(Extent.ILEUM, completion=completion)), ())

    def test_d217_a3_p_mono_a_doubt_added_to_a_ready_completion_holds_44377(self):
        """refute-4c-r2 A3's 9.4 case: each weakening of a READY 44377's completion - an added doubt (stated, unclear or
        conflict), the claim unresolved, its control left unrejected - holds it (it was READY after the conflict)."""
        before = sup(Completion.COMPLETE, 11)
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), ent(Extent.ILEUM, completion=before)), ())
        for weaker in (replace(before, result=Result.CONTRADICTED, reasons=(Reason.CONTRADICTED_BY_PASS1,)),
                       replace(before, result=Result.UNKNOWN, reasons=(Reason.DOUBT_STATED,)),
                       replace(before, result=Result.UNKNOWN, reasons=(Reason.DOUBT_UNCLEAR,)),
                       replace(before, result=Result.UNRESOLVED, reasons=(Reason.APPRAISAL_UNCLEAR,)),
                       replace(before, result=Result.UNRESOLVED, options=(Completion.INCOMPLETE,),
                               reasons=(Reason.CONTROL_INCOHERENT,))):
            with self.subTest(weaker=weaker):
                (witness,) = C.enteroscopy_hold('44377', (E2,), ent(Extent.ILEUM, completion=weaker))
                self.assertEqual((witness.attribute, witness.kind), (A.COMPLETION, Q))


# --- r4c, D217: D72 reads the session's examinations (refute-4c-r2 SEQ, SILENT-EXAM) -------------------------------------


def sequence(*, completion=Completion.COMPLETE, attempt=None, performed=None, more=None) -> FactSet:
    """Pass 1's filing of a failed attempt followed by success (extract_prompt's CONTRADICTION clause; refute-4c-r2 SEQ):
    X1 oral to the ileum (``completion``; None silent), E3 an examination of X1 begun and not completed (S13), E1 an
    examination of X1 performed (S14), E2 a biopsy there (S15); ``attempt``, ``performed``: E3's and E1's facts
    replaced by attribute name; ``more``: other events."""
    def changed(facts, change):
        return {**facts, **{Attribute[name.upper()]: (value,) for name, value in change.items()}}

    events = {E3: changed(event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=13), attempt or {}),
              E1: changed(event(Kind.EXAMINATION, X1, n=14), performed or {}), E2: event(Kind.BIOPSY, X1, n=15),
              **(more or {})}
    return factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=completion)}, events)


def attempt_only(*, completion=Completion.COMPLETE, more=None) -> FactSet:
    """X1 oral to the ileum whose one examination, E3, was begun and not completed (an established D72 attempt), a
    biopsy E2 there; ``more``: other events."""
    return factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=completion)},
                   {E3: event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=13),
                    E2: event(Kind.BIOPSY, X1, n=15), **(more or {})})


def attempt_explained(subject: Id = E3, n: int = 13) -> HeldFact:
    """D72's explanation: an examination of X1 established attempted_not_completed."""
    return held('extent', A.STATUS, subject, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(n)], EXTENT)


class ExaminationsOfTheSession(SimpleTestCase):
    def test_d217_seq_an_attempt_beside_an_established_performed_examination_does_not_count(self):
        """refute-4c-r2 SEQ (p02 (a), p04): a failed attempt (E3) followed by a performed examination (E1) of the same
        session, the completion stated complete - ILEAL T, no explanation and no incomplete form (it was F: an
        explanation that could never become T, "stated to be incomplete" on a note that states it complete). The
        completion decides: silent fits as well (D217), and incomplete is the completion's own explanation."""
        for name, R in (('completion complete', sequence()), ('completion silent', sequence(completion=None)),
                        ('E1 told before E3', factset(
                            {X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                            {E1: event(Kind.EXAMINATION, X1, n=14),
                             E3: event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=13),
                             E2: event(Kind.BIOPSY, X1, n=15)}))):
            with self.subTest(case=name):
                self.assertEqual(C.examinations(X1, R), tuple(event for event in R.events
                                                                if event in (E1, E3)))
                self.assertEqual(C.fits(ILEAL, X1, R), T)
                for code, supporting in (('44376', (E1,)), ('44377', (E2,)), ('44378', (E2,)), ('44379', (E2,))):
                    self.assertEqual((C.enteroscopy_hold(code, supporting, R), C.misfit_form(code, X1, R)), ((), None))
        R = sequence(completion=sup(Completion.INCOMPLETE, 11))
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
            held('extent', A.COMPLETION, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(11)], EXTENT),))

    def test_d217_d72_is_f_only_when_every_examination_of_the_session_is_established_attempted(self):
        """D217's D72: an established attempt holds the deeper class with an explanation only when no examination of
        the session may be performed - one for each such attempt; an examination that may be the session's performed
        one (its status, or its tie to the session, not established) makes the class U with a question resting on that
        doubt - a contradicted fact at rank 1, a doubted status at rank 2; an examination established of another
        session (the EGD X2, which the FactSet holds), planned, or denied performed is no performance of this session's
        (NOTES.md Q2)."""
        R = attempt_only()
        self.assertEqual(C.class_misfit('44377', X1, R), (attempt_explained(),))
        self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.INCOMPLETE)
        two = attempt_only(more={E4: event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=17)})
        self.assertEqual(C.class_misfit('44377', X1, two), (attempt_explained(), attempt_explained(E4, 17)))
        questions = {
            "E1's session unresolved, X1 an option": (
                dict(session=unresolved(X2, options=[X1], n=14)),
                held('extent', A.SESSION, E1, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                     [unit(14)], EXTENT)),
            "E1's session silent": (
                dict(session=F.SILENT),
                held('extent', A.SESSION, E1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, [unit(14)],
                     EXTENT)),
            "E1's session contradicted": (
                dict(session=contradicted([X1, X2], 14)),
                held('conflict:examination', A.SESSION, E1, Result.CONTRADICTED, Q, C.READING_CONTRADICTED,
                     Reason.CONTRADICTED_BY_PASS1, [unit(14)], 1)),
            "E1's status unresolved": (
                dict(status=unresolved(Status.PERFORMED, n=14)),
                held('extent', A.STATUS, E1, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                     [unit(14)], EXTENT)),
            "E1's status doubted": (
                dict(status=doubted(Status.PERFORMED, [Status.ATTEMPTED_NOT_COMPLETED], 14)),
                held('performed_status', A.STATUS, E1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.DOUBT_UNCLEAR,
                     [unit(14)], 2)),
            "E1's status contradicted": (
                dict(status=contradicted([Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED], 14)),
                held('conflict:examination', A.STATUS, E1, Result.CONTRADICTED, Q, C.READING_CONTRADICTED,
                     Reason.CONTRADICTED_BY_PASS1, [unit(14)], 1)),
            "E1's kind unresolved": (
                dict(kind=unresolved(Kind.EXAMINATION, n=14)),
                held('extent', A.KIND, E1, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                     [unit(14)], EXTENT)),
        }
        for name, (change, witness) in questions.items():
            R = beside_an_egd(sequence(performed=change))
            with self.subTest(question=name):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.class_misfit('44377', X1, R), (witness,))
                # v1's incomplete form only where the doubted examination's own claims state the attempt (a side of
                # its contradicted status: refute-4c-r1 E); its performance in doubt otherwise is the class form
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.INCOMPLETE
                                 if name == "E1's status contradicted" else C.ClassForm.CLASS)
        for name, change in (('E1 of another session', dict(session=sup(X2, 14))),
                             ('E1 planned', dict(status=sup(Status.PLANNED, 14))),
                             ('E1 denied performed', dict(status=neg(Status.PERFORMED, 14)))):
            R = beside_an_egd(sequence(performed=change))
            with self.subTest(explained=name):
                self.assertEqual(C.fits(ILEAL, X1, R), FF)
                self.assertIn(attempt_explained(), C.class_misfit('44377', X1, R))

    def test_d217_silent_exam_an_attempt_possibly_of_the_session_asks_its_session(self):
        """refute-4c-r2 SILENT-EXAM (p02 (c)): an examination begun and not completed whose session slot is silent,
        unresolved, doubted or contradicted, with X1 possible, makes ILEAL U with a question on its session - it was T
        (a silent slot named no session). A denial of another session leaves X1 possible too (the module's _open
        reading); one established of another session the FactSet holds (the EGD X2), or denied X1, is no examination
        of X1 (a session it does not hold: MissingSessionIdentifiers)."""
        def attempted(placed):
            return beside_an_egd(factset(
                {X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                {E1: event(Kind.EXAMINATION, placed, status=Status.ATTEMPTED_NOT_COMPLETED, n=14),
                 E2: event(Kind.BIOPSY, X1, n=15)}))

        for name, placed, fact, rank in (('silent', F.SILENT, 'extent', EXTENT),
                                         ('unresolved X1', unresolved(X1, n=14), 'extent', EXTENT),
                                         ('unresolved X2, X1 an option', unresolved(X2, options=[X1], n=14), 'extent',
                                          EXTENT),
                                         ('doubted', doubted(X2, [X1], 14), 'extent', EXTENT),
                                         ('contradicted', contradicted([X1, X2], 14), 'conflict:examination', 1),
                                         ('another session denied', neg(X2, 14), 'extent', EXTENT),
                                         ('a denial not established', unresolved(X2, n=14, state=FactState.NEGATED),
                                          'extent', EXTENT)):
            R = attempted(placed)
            with self.subTest(session=name):
                self.assertEqual(C.examinations(X1, R), (E1,))
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                (witness,) = C.class_misfit('44377', X1, R)
                self.assertEqual((witness.fact, witness.attribute, witness.subject, witness.kind, witness.rank,
                                  witness.result), (fact, A.SESSION, E1, Q, rank, placed.result))
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (witness,))
        for name, placed in (('established of X2', X2), ('X1 denied', neg(X1, 14)),
                             ('unresolved X2, no option', unresolved(X2, n=14))):
            R = attempted(placed)
            with self.subTest(control=name):
                self.assertEqual((C.examinations(X1, R), C.fits(ILEAL, X1, R)), ((), T))


# --- r4c-2, refute-r4c-r1 P1 and P4: a session the FactSet does not hold (4.11; DECISIONS D227's 4d R2-2) -------------


def with_e5(placed, status: Status = Status.ATTEMPTED_NOT_COMPLETED, attempt: bool = False) -> FactSet:
    """refute-r4c-r1 P1's scene: X1 oral to the ileum, its completion stated complete, a biopsy E2 there, beside the EGD
    X2 (a session the FactSet holds); E5 an examination (its kind and ``status`` supported) whose session fact is
    ``placed`` (S18); ``attempt``: E3 too, an examination of X1 established begun and not completed (D72's F scene)."""
    more = {E5: event(Kind.EXAMINATION, placed, status=status, n=18)}
    return attempted_scene(more=more) if attempt else act_only_scene(more=more)


DANGLING = unresolved(X3, Reason.REFERENCE_INVALID, n=18)  # pass 1's I4: settle keeps the claimed id, unresolved
DANGLING_QUESTION = held('extent', A.SESSION, E5, Result.UNRESOLVED, Q, 'unestablished:reference_invalid',
                         Reason.REFERENCE_INVALID, [unit(18)], EXTENT)


class MissingSessionIdentifiers(SimpleTestCase):
    """refute-r4c-r1 P1 (critical, pre-existing) and P4: an examination's session fact that names a session the FactSet
    does not hold - pass 1's I4 reference_invalid, which settle keeps as the claimed value, unresolved
    (coverage.sessions_of) - read as another session left D72 with no examination of X1: 44377 READY. 4.11 (a missing
    identifier manufactures neither a match nor a non-match) and DECISIONS D227's 4d R2-2 (a session id the FactSet
    does not hold reads as possibly any session for membership) make it possibly X1's, as evaluate._may_be_in reads it,
    and as this module already read an unlisted card (D231)."""

    def test_p1_an_examination_whose_session_the_factset_does_not_hold_is_asked_never_a_fit(self):
        """E5, an examination established begun and not completed, beside the act-only X1: its session X3, a session
        the FactSet does not hold - dangling (unresolved, reference_invalid), supported, or a reading beside a held
        session (unresolved, doubted or contradicted) - makes ILEAL U with one question on E5's session (D217's
        SILENT-EXAM), never T; classes' examinations of X1 are evaluate's. Controls: E5 established of the EGD X2
        (held), unresolved X2 with no reading, X1 denied - no examination of X1 in either module, T."""
        cases = {
            'a dangling id (unresolved, reference_invalid)': (DANGLING, DANGLING_QUESTION),
            'supported X3': (sup(X3, 18), held('extent', A.SESSION, E5, Result.SUPPORTED, Q, C.CLASS_CAUSE, None,
                                               [unit(18)], EXTENT)),
            'unresolved X2, a reading X3': (unresolved(X2, options=[X3], n=18), held(
                'extent', A.SESSION, E5, Result.UNRESOLVED, Q, 'appraisal:unclear', Reason.APPRAISAL_UNCLEAR,
                [unit(18)], EXTENT)),
            'doubted X2, read as X3': (doubted(X2, [X3], 18), held(
                'extent', A.SESSION, E5, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.DOUBT_UNCLEAR, [unit(18)],
                EXTENT)),
            'contradicted, X2 or X3': (contradicted([X2, X3], 18), held(
                'conflict:examination', A.SESSION, E5, Result.CONTRADICTED, Q, C.READING_CONTRADICTED,
                Reason.CONTRADICTED_BY_PASS1, [unit(18)], 1)),
        }
        for name, (placed, witness) in cases.items():
            R = with_e5(placed)
            with self.subTest(session=name):
                self.assertEqual(C.examinations(X1, R), (E5,))
                self.assertEqual(EV.examinations(R, X1), C.examinations(X1, R))
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.class_misfit('44377', X1, R), (witness,))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)  # only possibly X1's: not "stated"
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (witness,))
        for name, placed in (('established of the EGD X2', sup(X2, 18)), ('unresolved X2, no reading',
                                                                         unresolved(X2, n=18)),
                             ('X1 denied', neg(X1, 18))):
            R = with_e5(placed)
            with self.subTest(control=name):
                self.assertEqual((C.examinations(X1, R), EV.examinations(R, X1), C.fits(ILEAL, X1, R)), ((), (), T))

    def test_p1_a_performed_examination_whose_session_is_dangling_keeps_d72_from_its_explanation(self):
        """The refuter's second input: E3, an examination of X1 established begun and not completed, and E5, an
        examination established PERFORMED whose session is the dangling X3. E5 may be X1's performed examination, so E3
        is not every examination of X1: U with the one question on E5's session - it was F with D72's explanation on
        E3 (the incomplete form). The control: E5 established of the EGD X2 leaves the explanation."""
        R = with_e5(DANGLING, Status.PERFORMED, attempt=True)
        self.assertEqual(C.examinations(X1, R), (E3, E5))
        self.assertEqual(EV.examinations(R, X1), (E3, E5))
        self.assertEqual(C.fits(ILEAL, X1, R), U)
        self.assertEqual(C.class_misfit('44377', X1, R), (DANGLING_QUESTION,))
        self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)
        control = with_e5(sup(X2, 18), Status.PERFORMED, attempt=True)
        self.assertEqual((C.class_misfit('44377', X1, control), C.misfit_form('44377', X1, control)),
                         ((attempt_explained(),), C.ClassForm.INCOMPLETE))

    def test_p1_through_assess_44377_is_held_by_the_question_on_the_dangling_session_never_ready(self):
        """P1 end to end, on the refuter's input (tests/v2/evaluate_fixtures' scene): assess over X1 oral to the ileum,
        its completion complete, the ileal biopsy E2 (44377 proposed on it), and E5, an examination established begun
        and not completed whose session is the dangling X3: 44377 needs clarification, held by the one question on E5's
        session - it was READY with no held fact (evaluate's row 7 read E5 as X1's and begun as done; classes read it
        as another session's). Without E5, the same scene is READY: the hold is E5's."""
        from tests.v2 import evaluate_fixtures as EF
        from tests.v2 import test_assess as TA

        def scene(placed: Fact | None) -> FactSet:
            doc = EF.Doc()
            doc.session(1, SessionKind.ENTEROSCOPY, approach=EF.sup(ORAL), reached=[EF.sup(Extent.ILEUM)],
                        completion=EF.sup(Completion.COMPLETE))
            doc.act(2, Kind.BIOPSY, places=[EF.sup(EF.Landmark.ILEUM)])
            if placed is not None:
                doc.act(5, Kind.EXAMINATION, session=placed, status=EF.sup(Status.ATTEMPTED_NOT_COMPLETED))
            return doc.build()

        (alone,) = TA.run(scene(None), ('44377', 2)).codes
        self.assertEqual((alone.code, alone.status, tuple(alone.held_facts)), ('44377', Outcome.READY, ()))
        (found,) = TA.run(scene(EF.unres(X3, Reason.REFERENCE_INVALID)), ('44377', 2)).codes
        self.assertEqual(found.status, Outcome.NEEDS_CLARIFICATION)
        self.assertEqual([(held_fact.fact, held_fact.attribute, held_fact.subject, held_fact.kind, held_fact.cause,
                           held_fact.rank) for held_fact in found.held_facts],
                         [('extent', A.SESSION, E5, Q, 'unestablished:reference_invalid', EXTENT)])


# --- r4c, D216: the synthetic unlisted act in the absence conditions -----------------------------------------------------


def beside_an_egd(R: FactSet) -> FactSet:
    """``R`` with an EGD session X2 beside its own (no events of its own): a card naming X2 then names a session the
    FactSet holds, so it is another session's, never a missing identifier (4.11)."""
    return replace(R, sessions={**R.sessions, X2: session(SessionKind.EGD, reached=[Extent.SECOND_PORTION_DUODENUM])})


class UnlistedActsInTheAbsenceConditions(SimpleTestCase):
    def test_d216_a_synthetic_examination_act_keeps_d72_from_its_explanation(self):
        """D216, D231: 3.2.6 rule 3's synthetic doubted act - a kept unlisted act OR DOUBT of kind examination (or of no
        kind named), of X1 (or of no session named) - is a possibly performed examination of X1, so an established
        attempt is no longer every examination of the session: U, one question about the act (performed_status at rank
        2, cause unlisted, about no single fact, quoting its own unit), never D72's explanation. An unlisted act or
        doubt of another session the FactSet holds (the EGD X2) or of another kind, and an unlisted denial, leave the
        explanation (D231: a denial is no possibly performed act)."""
        question = held('performed_status', None, X1, None, Q, C.UNLISTED, None, [unit(30)], 2)
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            for kind, where in ((Kind.EXAMINATION, X1), (None, X1), (Kind.EXAMINATION, None), (None, None)):
                found = unlisted_act(kind, where, what=what)
                R = beside_an_egd(ent(Extent.ILEUM, status=Status.ATTEMPTED_NOT_COMPLETED, unlisted=[found]))
                with self.subTest(what=what, kind=kind, session=where):
                    self.assertEqual(C.unlisted_examinations(X1, R), (found,))
                    self.assertEqual(C.fits(ILEAL, X1, R), U)
                    self.assertEqual(C.class_misfit('44377', X1, R), (question,))
                    self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)
        for name, entry in (('an act of another session', unlisted_act(Kind.EXAMINATION, X2)),
                            ('a doubt of another session', unlisted_act(Kind.EXAMINATION, X2, what=UnlistedWhat.DOUBT)),
                            ('an act of another kind', unlisted_act(Kind.BIOPSY, X1)),
                            ('a doubt of another kind', unlisted_act(Kind.BIOPSY, X1, what=UnlistedWhat.DOUBT)),
                            ('a denial', unlisted_act(what=UnlistedWhat.DENIAL)),
                            ('a denial of no kind and no session', unlisted_act(None, None, what=UnlistedWhat.DENIAL))):
            R = beside_an_egd(ent(Extent.ILEUM, status=Status.ATTEMPTED_NOT_COMPLETED, unlisted=[entry]))
            with self.subTest(control=name):
                self.assertEqual(C.unlisted_examinations(X1, R), ())
                self.assertEqual(C.class_misfit('44377', X1, R), (attempt_explained(E1, 14),))

    def test_d216_a_synthetic_examination_act_may_be_an_attempt_and_never_counts_beside_a_performed_one(self):
        """The synthetic act's status is open (4.2's status arm: a doubted act may have been begun and not completed):
        with no examination of X1 established performed, it is the one question (U); beside an examination established
        performed it does not count (T, D217), as a filed attempt would not - an unlisted act and an unlisted doubt
        alike (D231)."""
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            with self.subTest(what=what):
                R = factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE)},
                            {E2: event(Kind.BIOPSY, X1, n=15)}, unlisted=[unlisted_act(what=what)])
                self.assertEqual(C.class_misfit('44377', X1, R), (
                    held('performed_status', None, X1, None, Q, C.UNLISTED, None, [unit(30)], 2),))
                self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, unlisted=[unlisted_act(what=what)])), T)
        self.assertEqual(C.fits(ILEAL, X1, sequence()), T)

    def test_d216_an_unlisted_act_of_the_group_keeps_act_elsewhere_out(self):
        """D216, D231 on act_elsewhere's absence condition (no positive candidate in doubt): a kept unlisted ablation -
        an act or a doubt; of the push enteroscopy, of the EGD or of no session named - or an unlisted act or doubt of
        no kind named is a possibly performed ablation, so 44369 is not explained as documented in another procedure:
        its own question is the code's (refute-4c-r1 C). A clip or an injection may be a bleeding control (its purpose
        unknown); an unlisted biopsy (act or doubt) and an unlisted denial of an ablation leave the elsewhere act (D231:
        a denial is no possibly performed act)."""
        done = (E3, event(Kind.ABLATION, X1, n=16))
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            for kind, where in ((Kind.ABLATION, X2), (Kind.ABLATION, X1), (Kind.ABLATION, None), (None, X2)):
                found = unlisted_act(kind, where, what=what)
                R = egd_and_push(done, unlisted=[found])
                with self.subTest(what=what, kind=kind, session=where):
                    self.assertEqual(C.unlisted_of_group(R, (Kind.ABLATION,)), (found,))
                    self.assertEqual((C.act_elsewhere('44369', R), C.enteroscopy_hold('44369', (), R)), ((), ()))
        for name, entry in (('an act of a biopsy', unlisted_act(Kind.BIOPSY, X2)),
                            ('a doubt of a biopsy', unlisted_act(Kind.BIOPSY, X2, what=UnlistedWhat.DOUBT)),
                            ('a denial', unlisted_act(Kind.ABLATION, X2, what=UnlistedWhat.DENIAL)),
                            ('a denial of no kind', unlisted_act(None, None, what=UnlistedWhat.DENIAL))):
            R = egd_and_push(done, unlisted=[entry])
            with self.subTest(control=name):
                self.assertEqual(C.unlisted_of_group(R, (Kind.ABLATION,)), ())
                self.assertEqual(C.enteroscopy_hold('44369', (), R), (elsewhere(E3),))
        hemostatic = (E3, event(Kind.CLIP, X1, n=16, purpose=Purpose.HEMOSTASIS))
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            for kind in (Kind.CLIP, Kind.INJECTION, Kind.BLEEDING_CONTROL):
                with self.subTest(bleeding_control=kind, what=what):
                    self.assertEqual(C.act_elsewhere('44366', egd_and_push(
                        hemostatic, unlisted=[unlisted_act(kind, X2, what=what)])), ())
        self.assertEqual(C.act_elsewhere('44366', egd_and_push(hemostatic, unlisted=[unlisted_act(Kind.BIOPSY, X2)])),
                         (C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.BLEEDING_CONTROL,)),))


# --- r4c, D231: an unlisted DOUBT is a possibly performed act too (the classes half; refute-r4a-r1 F1; O17) -----------


def attempted_scene(unlisted=(), more=None) -> FactSet:
    """D72's F scene: X1 oral to the ileum, its completion stated complete, E3 an examination of X1 established begun
    and not completed (S13), a biopsy E2 there (S15), beside an EGD X2 (a card naming X2 names a session the FactSet
    holds); ``unlisted``: the kept unlisted statements; ``more``: other events."""
    return factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE),
                    X2: session(SessionKind.EGD, reached=[Extent.SECOND_PORTION_DUODENUM])},
                   {E3: event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=13),
                    E2: event(Kind.BIOPSY, X1, n=15), **(more or {})}, unlisted=unlisted)


def act_only_scene(unlisted=(), more=None) -> FactSet:
    """D72's T scene: X1 oral to the ileum, its completion stated complete, no examination filed (an act-only session:
    a biopsy E2, S15), beside an EGD X2; ``unlisted``, ``more``: as attempted_scene."""
    return factset({X1: session(approach=ORAL, reached=[Extent.ILEUM], completion=Completion.COMPLETE),
                    X2: session(SessionKind.EGD, reached=[Extent.SECOND_PORTION_DUODENUM])},
                   {E2: event(Kind.BIOPSY, X1, n=15), **(more or {})}, unlisted=unlisted)


def filed_doubt(kind: Kind | None, card: Id | None, status: Fact, n: int = 30) -> dict:
    """The same statement FILED by pass 1 as a doubted act (3.3 row 2): an event of ``kind`` (None: no kind named, a
    silent kind slot) in ``card`` (None: no session named, a silent session slot) whose status is ``status`` (one of
    FILED_DOUBTS: a doubt names it), every other fact of 4.3 rows 1-5 supported, at S<n> - the unit the unlisted entry
    of the same statement quotes."""
    return event(kind if kind is not None else F.SILENT, card if card is not None else F.SILENT, status=status, n=n)


# The status of a filed doubted act (3.3 row 2, as facts.factset builds it): pass 1's performed kept with a doubt's
# readings (none, an attempt, a plan), or the status slot left empty and a doubt naming it.
FILED_DOUBTS = {'performed doubted': doubted(Status.PERFORMED, (), 30),
                'performed doubted, read as begun': doubted(Status.PERFORMED, [Status.ATTEMPTED_NOT_COMPLETED], 30),
                'performed doubted, read as planned': doubted(Status.PERFORMED, [Status.PLANNED], 30),
                'an empty status a doubt names': empty([Status.PERFORMED], n=30)}
# The kinds and cards of one statement, kept unlisted or filed (None: none named; X3: a session the FactSet does not
# hold, 4.11 - refute-r4c-r1 P4: the filed form reads it as the unlisted card does).
EXAM_STATEMENTS = ((Kind.EXAMINATION, X1), (Kind.EXAMINATION, None), (None, X1), (None, None), (Kind.EXAMINATION, X3),
                   (None, X3))


def class_outcome(R: FactSet, code: str = '44377') -> tuple:
    """What the deeper class decides for ``code`` on X1: its truth, v1's form, and each witness's kind, fact and rank
    (what is asked or explained, and at which rank - the witness's subject and cause name where the doubt came from)."""
    return (C.fits(ILEAL, X1, R), C.misfit_form(code, X1, R),
            tuple((witness.kind, witness.fact, witness.rank) for witness in C.class_misfit(code, X1, R)))


def elsewhere_outcome(R: FactSet, code: str = '44369') -> tuple:
    """What act_elsewhere decides for ``code``: its elsewhere acts and the code's witnesses with no supporting act."""
    return C.act_elsewhere(code, R), C.enteroscopy_hold(code, (), R)


class UnlistedDoubtsArePossiblyPerformed(SimpleTestCase):
    """DECISIONS D231 (refute-r4a-r1 F1; r4c's Q3; r4a-2's R3): 3.2.6 rule 3's synthetic act is a kept unlisted ACT or
    an unlisted DOUBT - a doubt about whether an act was done leaves it possibly performed (4.2 [R:HO-1]) - so each
    absence condition of this module that reads the synthetic act gives an unlisted doubt the outcome it gives the
    unlisted act and the outcome the same statement FILED as a doubted act gives: one test per condition, the three
    side by side beside the established outcome without them. An unlisted denial is no possibly performed act (D231
    names acts and doubts)."""

    def test_d231_d72_f_an_unlisted_doubt_keeps_off_the_explanation_as_the_act_and_the_filed_doubt_do(self):
        """D72's F (no examination of the session that may be performed). E3, an examination of X1 established begun and
        not completed, alone: F, D72's explanation (v1's incomplete form). Beside a kept unlisted examination act, a
        kept unlisted examination DOUBT, or the same statement filed as an examination E5 whose status is doubted
        (four doubted forms) - its kind and card named or not -: U, one rank-2 performed_status question, the class
        form, for all three; the act and the doubt give the identical witness (the session's, cause unlisted), the
        filed doubt a witness on E5's status. An unlisted denial, and the same denial filed (E5 denied performed),
        leave the explanation."""
        alone = attempted_scene()
        self.assertEqual(C.class_misfit('44377', X1, alone), (attempt_explained(),))
        self.assertEqual(class_outcome(alone), (FF, C.ClassForm.INCOMPLETE, ((X, 'extent', EXTENT),)))
        question = held('performed_status', None, X1, None, Q, C.UNLISTED, None, [unit(30)], 2)
        doubted_outcome = (U, C.ClassForm.CLASS, ((Q, 'performed_status', 2),))
        for kind, card in EXAM_STATEMENTS:
            act = attempted_scene([unlisted_act(kind, card)])
            doubt = attempted_scene([unlisted_act(kind, card, what=UnlistedWhat.DOUBT)])
            with self.subTest(kind=kind, card=card):
                self.assertEqual(C.class_misfit('44377', X1, act), (question,))
                self.assertEqual(C.class_misfit('44377', X1, doubt), (question,))
                self.assertEqual((class_outcome(act), class_outcome(doubt)), (doubted_outcome, doubted_outcome))
            for name, status in FILED_DOUBTS.items():
                filed = attempted_scene(more={E5: filed_doubt(kind, card, status)})
                with self.subTest(kind=kind, card=card, filed=name):
                    self.assertEqual(class_outcome(filed), class_outcome(doubt))
                    (witness,) = C.class_misfit('44377', X1, filed)
                    self.assertEqual((witness.subject, witness.attribute, witness.result), (E5, A.STATUS,
                                                                                           Result.UNKNOWN))
        for name, R in (('an unlisted denial', attempted_scene([unlisted_act(what=UnlistedWhat.DENIAL)])),
                        ('an unlisted denial of no kind or card', attempted_scene([unlisted_act(
                            None, None, what=UnlistedWhat.DENIAL)])),
                        ('the denial filed', attempted_scene(more={E5: event(Kind.EXAMINATION, X1, n=30,
                                                                             status=neg(Status.PERFORMED, 30))}))):
            with self.subTest(control=name):
                self.assertEqual(C.class_misfit('44377', X1, R), (attempt_explained(),))

    def test_d231_d72_t_an_unlisted_doubt_holds_an_act_only_session_as_the_act_and_the_filed_doubt_do(self):
        """D72's T (no examination of the session that may be attempted). An act-only X1 (its biopsy, no examination
        filed) fits the deeper class. Beside a kept unlisted examination act, a kept unlisted examination DOUBT, or the
        same statement filed as an examination E5 whose status is doubted (four doubted forms) - its kind and card named
        or not -: U, one rank-2 performed_status question, the class form, for all three (a doubted act may have been
        begun, 4.2's status arm). Beside an examination of X1 established performed, none of the three adds anything
        (T: D217, as D232 reads row 7). An unlisted denial adds nothing."""
        self.assertEqual(class_outcome(act_only_scene()), (T, None, ()))
        question = held('performed_status', None, X1, None, Q, C.UNLISTED, None, [unit(30)], 2)
        doubted_outcome = (U, C.ClassForm.CLASS, ((Q, 'performed_status', 2),))
        for kind, card in EXAM_STATEMENTS:
            act = act_only_scene([unlisted_act(kind, card)])
            doubt = act_only_scene([unlisted_act(kind, card, what=UnlistedWhat.DOUBT)])
            with self.subTest(kind=kind, card=card):
                self.assertEqual(C.class_misfit('44377', X1, act), (question,))
                self.assertEqual(C.class_misfit('44377', X1, doubt), (question,))
                self.assertEqual((class_outcome(act), class_outcome(doubt)), (doubted_outcome, doubted_outcome))
            for name, status in FILED_DOUBTS.items():
                filed = act_only_scene(more={E5: filed_doubt(kind, card, status)})
                with self.subTest(kind=kind, card=card, filed=name):
                    self.assertEqual(class_outcome(filed), class_outcome(doubt))
                    (witness,) = C.class_misfit('44377', X1, filed)
                    self.assertEqual((witness.subject, witness.attribute), (E5, A.STATUS))
        performed = {E1: event(Kind.EXAMINATION, X1, n=14)}
        for name, R in (('the act', act_only_scene([unlisted_act()], more=performed)),
                        ('the doubt', act_only_scene([unlisted_act(what=UnlistedWhat.DOUBT)], more=performed)),
                        ('the filed doubt', act_only_scene(more={**performed, E5: filed_doubt(
                            Kind.EXAMINATION, X1, FILED_DOUBTS['performed doubted'])})),
                        ('an unlisted denial', act_only_scene([unlisted_act(what=UnlistedWhat.DENIAL)]))):
            with self.subTest(adds_nothing=name):
                self.assertEqual(class_outcome(R), (T, None, ()))
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), ())

    def test_d231_act_elsewhere_an_unlisted_doubt_keeps_the_group_out_as_the_act_and_the_filed_doubt_do(self):
        """act_elsewhere's absence condition (no positive candidate of the group in doubt), on the parity note's
        encounter: E3, an ablation done and placed in the EGD X1, beside the push enteroscopy X2, alone holds 44369 with
        the elsewhere explanation. Beside a kept unlisted ablation act, a kept unlisted ablation DOUBT, or the same
        statement filed as an ablation E5 whose status is doubted (four doubted forms) - carded to the push, to the EGD
        or to none, or of no kind named -: no elsewhere act and no explanation (the code's own question is 4a's:
        refute-4c-r1 C), for all three. So for 44366's bleeding control beside a clip or an injection whose purpose
        is not stated. An unlisted denial, and the same denial filed (E5 denied performed), leave the explanation."""
        done = (E3, event(Kind.ABLATION, X1, n=16))
        self.assertEqual(elsewhere_outcome(egd_and_push(done)),
                         ((C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.ABLATION,)),), (elsewhere(E3),)))
        for kind, card in ((Kind.ABLATION, X2), (Kind.ABLATION, X1), (Kind.ABLATION, None), (None, X2), (None, None),
                           (Kind.ABLATION, X3)):
            act = egd_and_push(done, unlisted=[unlisted_act(kind, card)])
            doubt = egd_and_push(done, unlisted=[unlisted_act(kind, card, what=UnlistedWhat.DOUBT)])
            with self.subTest(kind=kind, card=card):
                self.assertEqual((elsewhere_outcome(act), elsewhere_outcome(doubt)), (((), ()), ((), ())))
            for name, status in FILED_DOUBTS.items():
                filed = egd_and_push(done, (E5, filed_doubt(kind, card, status)))
                with self.subTest(kind=kind, card=card, filed=name):
                    self.assertEqual(elsewhere_outcome(filed), elsewhere_outcome(doubt))
        hemostatic = (E3, event(Kind.CLIP, X1, n=16, purpose=Purpose.HEMOSTASIS))
        self.assertEqual(elsewhere_outcome(egd_and_push(hemostatic), '44366'),
                         ((C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.BLEEDING_CONTROL,)),), (elsewhere(E3),)))
        for kind in (Kind.CLIP, Kind.INJECTION):
            outcomes = {'act': elsewhere_outcome(egd_and_push(hemostatic, unlisted=[unlisted_act(kind, X2)]), '44366'),
                        'doubt': elsewhere_outcome(egd_and_push(hemostatic, unlisted=[unlisted_act(
                            kind, X2, what=UnlistedWhat.DOUBT)]), '44366'),
                        **{f'filed, {name}': elsewhere_outcome(egd_and_push(hemostatic, (E5, filed_doubt(
                            kind, X2, status))), '44366') for name, status in FILED_DOUBTS.items()}}
            with self.subTest(bleeding_control=kind):
                self.assertEqual(set(outcomes.values()), {((), ())}, outcomes)
        for name, R in (('an unlisted denial', egd_and_push(done, unlisted=[unlisted_act(
                            Kind.ABLATION, X2, what=UnlistedWhat.DENIAL)])),
                        ('an unlisted denial of no kind or card', egd_and_push(done, unlisted=[unlisted_act(
                            None, None, what=UnlistedWhat.DENIAL)])),
                        ('the denial filed', egd_and_push(done, (E5, event(Kind.ABLATION, X2, n=30,
                                                                           status=neg(Status.PERFORMED, 30)))))):
            with self.subTest(control=name):
                self.assertEqual(elsewhere_outcome(R)[1], (elsewhere(E3),))

    def test_d231_an_unlisted_act_told_as_a_doubt_gives_every_rule_the_same_witnesses(self):
        """Over the module's rich inputs, each kept unlisted act told instead as a doubt (the same units, kind and card)
        gives every family code the same witnesses, form and elsewhere acts, and every class the same truth - the
        witnesses do not depend on the entry's nature. Not vacuous: the unlisted acts change the outcome of some inputs
        (removing them changes a witness)."""
        moved = 0
        for index, R in enumerate(rich_factsets()):
            if not any(entry.what is UnlistedWhat.ACT for entry in R.unlisted):
                continue
            told = replace(R, unlisted=tuple(replace(entry, what=UnlistedWhat.DOUBT)
                                             if entry.what is UnlistedWhat.ACT else entry for entry in R.unlisted))
            without = replace(R, unlisted=())
            for code in FAMILY_CODES:
                with self.subTest(factset=index, code=code):
                    self.assertEqual(C.enteroscopy_hold(code, (E1, E2, E5), told),
                                     C.enteroscopy_hold(code, (E1, E2, E5), R))
                    self.assertEqual(C.misfit_form(code, X1, told), C.misfit_form(code, X1, R))
                    self.assertEqual(C.act_elsewhere(code, told), C.act_elsewhere(code, R))
            self.assertEqual(truths(told), truths(R))
            moved += any(C.enteroscopy_hold(code, (E1, E2, E5), without) != C.enteroscopy_hold(code, (E1, E2, E5), R)
                         for code in FAMILY_CODES)
        self.assertGreaterEqual(moved, 10)

    def test_d231_o17_classes_reads_the_set_evaluate_reads(self):
        """O17 (D231: 'so the four modules read one set'): for every nature, kind and card, the kept unlisted entries
        this module reads as possibly performed are engine/evaluate.py's (synthetic_possible: acts and doubts), and the
        synthetic examination acts it reads for the enteroscopy X1 are evaluate's row 7 reading of X1
        (synthetic_examinations) - a card naming X1, none, or a session the FactSet does not hold (X3: 4.11,
        evaluate.synthetic_in) - and never one naming the EGD X2 the FactSet holds."""
        for what in UnlistedWhat:
            for kind in (None, Kind.EXAMINATION, Kind.BIOPSY, Kind.ABLATION, Kind.CLIP):
                for card in (None, X1, X2, X3):
                    R = act_only_scene([unlisted_act(kind, card, what=what)])
                    with self.subTest(what=what, kind=kind, card=card):
                        self.assertEqual(C.synthetic_possible(R), EV.synthetic_possible(R))
                        self.assertEqual(C.unlisted_examinations(X1, R), EV.synthetic_examinations(R, X1))
                        self.assertEqual(bool(C.unlisted_examinations(X1, R)),
                                         what is not UnlistedWhat.DENIAL and kind in (None, Kind.EXAMINATION)
                                         and card is not X2)
        self.assertEqual(C.POSSIBLY_PERFORMED, frozenset({UnlistedWhat.ACT, UnlistedWhat.DOUBT}))

    def test_d231_a_card_naming_a_session_the_factset_does_not_hold_leaves_the_session_possible(self):
        """4.11 (a missing identifier manufactures neither a match nor a non-match; DECISIONS D227's 4d R2-2), as
        engine/evaluate.py's synthetic_in reads a card: an unlisted examination act or doubt whose card names X3, a
        session the FactSet does not hold, is possibly X1's examination - U beside E3's established attempt, U in the
        act-only session - where a card naming the EGD X2, which the FactSet holds, is another session's (F; T).
        refute-r4c-r1 P4: the same statement FILED in X3 as an examination whose status is doubted (each doubted form)
        gives the same outcome (it was F and T: the filed side read X3 as another session, P1), and filed in X2 the
        same outcome as the unlisted card X2."""
        question = held('performed_status', None, X1, None, Q, C.UNLISTED, None, [unit(30)], 2)
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            with self.subTest(what=what):
                missing = unlisted_act(Kind.EXAMINATION, X3, what=what)
                self.assertEqual(C.class_misfit('44377', X1, attempted_scene([missing])), (question,))
                self.assertEqual(C.class_misfit('44377', X1, act_only_scene([missing])), (question,))
                other = unlisted_act(Kind.EXAMINATION, X2, what=what)
                self.assertEqual(C.class_misfit('44377', X1, attempted_scene([other])), (attempt_explained(),))
                self.assertEqual(C.class_misfit('44377', X1, act_only_scene([other])), ())
        doubted_outcome = (U, C.ClassForm.CLASS, ((Q, 'performed_status', 2),))
        for name, status in FILED_DOUBTS.items():
            for card, attempted, act_only in ((X3, doubted_outcome, doubted_outcome),
                                              (X2, (FF, C.ClassForm.INCOMPLETE, ((X, 'extent', EXTENT),)),
                                               (T, None, ()))):
                filed = {E5: filed_doubt(Kind.EXAMINATION, card, status)}
                with self.subTest(filed=name, card=card):
                    self.assertEqual(class_outcome(attempted_scene(more=filed)), attempted)
                    self.assertEqual(class_outcome(act_only_scene(more=filed)), act_only)
                    for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
                        entry = [unlisted_act(Kind.EXAMINATION, card, what=what)]
                        self.assertEqual(class_outcome(attempted_scene(entry)), attempted)
                        self.assertEqual(class_outcome(act_only_scene(entry)), act_only)

    def test_p3_the_synthetic_acts_witness_quotes_its_own_units_only_and_finds_its_entry(self):
        """refute-r4c-r1 P3: contract/appraise_read.py keeps an unlisted entry whose every unit id was unknown, with no
        units. Its synthetic examination act's witness quotes nothing - never X1's reach (S4 here), another statement,
        which it quoted - as evaluate._synthetic_doubt quotes the same act, so questions.synthetic_entry finds the entry
        the witness is about (it found none: the reach is not the entry's units) and the item can name that act, not
        the code's biopsy. An act and a doubt alike, its card X1, none or X3, beside E3's attempt or in the act-only X1;
        with units the witness quotes them (sorted, each once) and finds its entry the same way."""
        for what in (UnlistedWhat.ACT, UnlistedWhat.DOUBT):
            for card in (X1, None, X3):
                for units in ((), (unit(30),), (unit(31), unit(30), unit(31))):
                    entry = UnlistedStatement(units=units, what=what, kind=Kind.EXAMINATION, session=card)
                    for name, R in (('act-only', act_only_scene([entry])), ('attempted', attempted_scene([entry]))):
                        with self.subTest(what=what, card=card, units=units, scene=name):
                            (witness,) = C.class_misfit('44377', X1, R)
                            self.assertEqual(witness, held('performed_status', None, X1, None, Q, C.UNLISTED, None,
                                                           sorted(set(units)), 2))
                            self.assertEqual(QS.synthetic_entry(witness, R, QS.Raised()), entry)
                            self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (witness,))

    def test_n1_every_reader_keeps_the_stored_order_when_acts_and_doubts_mix(self):
        """refute-r4c-r1 N1 (a test gap: no pin of a FactSet mixing acts and doubts): synthetic_possible keeps
        FactSet.unlisted's order, as evaluate.synthetic_possible does - never the acts first -, and so do
        unlisted_examinations (evaluate's row 7 reading), unlisted_of_group, and the deeper class's witnesses, one per
        synthetic act; the denial is read by none of them."""
        doubt31 = unlisted_act(Kind.EXAMINATION, X1, 31, UnlistedWhat.DOUBT)
        denial32 = unlisted_act(Kind.EXAMINATION, X1, 32, UnlistedWhat.DENIAL)
        act33 = unlisted_act(Kind.EXAMINATION, None, 33)
        doubt34 = unlisted_act(None, None, 34, UnlistedWhat.DOUBT)
        act35 = unlisted_act(Kind.ABLATION, X2, 35)
        R = act_only_scene([doubt31, denial32, act33, doubt34, act35])
        self.assertEqual(C.synthetic_possible(R), (doubt31, act33, doubt34, act35))
        self.assertEqual(EV.synthetic_possible(R), C.synthetic_possible(R))
        self.assertEqual(C.unlisted_examinations(X1, R), (doubt31, act33, doubt34))
        self.assertEqual(EV.synthetic_examinations(R, X1), C.unlisted_examinations(X1, R))
        self.assertEqual(C.unlisted_of_group(R, (Kind.ABLATION,)), (doubt34, act35))
        self.assertEqual([witness.spans for witness in C.class_misfit('44377', X1, R)],
                         [(unit(31),), (unit(33),), (unit(34),)])


# --- r4c, D218: the points beyond the jejunal class, and the small bowel (refute-4c-r2 DQ2-EXT) ------------------------


class BeyondTheJejunalClass(SimpleTestCase):
    def test_d218_every_point_past_the_ileum_holds_the_jejunal_class(self):
        """refute-4c-r2 DQ2-EXT (p02 (b)): an oral reach to the jejunum and to a point the oral route reaches only
        through the ileum - the cecum, the ileocecal valve, the appendiceal orifice, every colon point, the rectum, the
        anal canal, an ileal point - is JEJUNAL F, an explanation on that point: 44361 held (it was READY; the
        installed release's furthest landmark fits no jejunal class there)."""
        self.assertEqual(len(C.BEYOND[JEJUNAL]), 20)
        for point in sorted(C.BEYOND[JEJUNAL], key=lambda extent: extent.value):
            R = ent(Extent.JEJUNUM, point)
            with self.subTest(beyond=point):
                self.assertEqual(C.fits(JEJUNAL, X1, R), FF)
                for code in ('44360', '44361', '44369'):
                    self.assertEqual(C.class_misfit(code, X1, R), (beyond_reached([unit(4), unit(5)]),))
                self.assertEqual(C.enteroscopy_hold('44361', (E2,), R), (beyond_reached([unit(4), unit(5)]),))
                self.assertEqual(C.misfit_form('44361', X1, R), C.ClassForm.CLASS)
        for point in (Extent.CECUM, Extent.ILEOCECAL_VALVE, Extent.APPENDICEAL_ORIFICE, Extent.COLON):
            self.assertEqual(truths(ent(Extent.JEJUNUM, point))[JEJUNAL], FF)  # p02 (b) by name

    def test_d218_the_small_bowel_beside_the_jejunum_fits_and_alone_fits_no_class(self):
        """D218: a member that names only a region containing both the jejunal reach and the ileum - the small bowel -
        is no beyond point. [small_bowel, jejunum] fits JEJUNAL (4.3's literal row; the installed extent is the
        jejunum): 44361 READY on the class (refute-4c-r2: it was held); the small bowel alone fits no class (R6's extent
        question), as installed."""
        for reached in ((Extent.SMALL_BOWEL, Extent.JEJUNUM), (Extent.JEJUNUM, Extent.SMALL_BOWEL)):
            R = ent(*reached)
            with self.subTest(reached=reached):
                self.assertEqual(truths(R), {JEJUNAL: T, ILEAL: U, STOMA: FF, POUCH: FF})
                self.assertEqual((C.class_misfit('44361', X1, R), C.enteroscopy_hold('44361', (E2,), R),
                                  C.misfit_form('44361', X1, R)), ((), (), None))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)
        R = ent(Extent.SMALL_BOWEL)
        self.assertEqual(truths(R), {JEJUNAL: U, ILEAL: U, STOMA: FF, POUCH: FF})
        for code in ('44361', '44377'):
            self.assertEqual(C.class_misfit(code, X1, R), (reach_unknown([unit(4)]),))
            self.assertEqual(C.misfit_form(code, X1, R), C.ClassForm.EXTENT)

    def test_d218_no_point_contains_a_beyond_point_without_being_one(self):
        """The anatomy the reading rests on (module docstring, REACH): every point that contains a point beyond the
        jejunal class is itself beyond it, or contains the jejunal reach as well (the small bowel) - so no containing
        point is left to read as 'may lie beyond'."""
        jejunal = catalogue.ENTEROSCOPY_CLASS_REACH[JEJUNAL]
        containers = {point for point in Extent if any(AN.contains(point, far) for far in C.BEYOND[JEJUNAL])}
        self.assertTrue(containers)
        for point in containers:
            with self.subTest(point=point):
                self.assertTrue(point in C.BEYOND[JEJUNAL] or any(AN.contains(point, near) for near in jejunal))
        self.assertEqual({point for point in containers if point not in C.BEYOND[JEJUNAL]}, {Extent.SMALL_BOWEL})


# --- r4c, D219: the pouch class accepts a pouch entered transanally (refute-4c-r1/r2 DQ1, 4c's Q3 option (b)) ------------


class TransanalPouch(SimpleTestCase):
    def test_d219_a_pouch_entered_transanally_through_an_ileal_pouch_fits_the_pouch_class(self):
        """1b's approach definition makes transanal a faithful filing of a pouchoscopy: approach transanal, through Y1
        an established ileal pouch, the pouch or the pre-pouch ileum reached - 44385 and 44386 fit, no witness (it was
        F, the approach's explanation). The oral and stoma classes stay held by the approach (an explanation)."""
        for point in (Extent.POUCH, Extent.ILEUM, Extent.NEO_TERMINAL_ILEUM):
            R = ent(point, approach=Approach.TRANSANAL, through=Y1, anatomy=POUCH_ENTRY)
            with self.subTest(reach=point):
                self.assertEqual(C.fits(POUCH, X1, R), T)
                self.assertEqual(C.routes(X1, R), {THROUGH_POUCH})
                for code in ('44385', '44386'):
                    self.assertEqual((C.class_misfit(code, X1, R), C.enteroscopy_hold(code, (E2,), R),
                                      C.misfit_form(code, X1, R)), ((), (), None))
                for exam_class in (JEJUNAL, ILEAL, STOMA):
                    witnesses = C.class_fit(exam_class, X1, R).witnesses
                    self.assertIn(held('procedure', A.APPROACH, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(3)],
                                       PROCEDURE), witnesses)

    def test_d219_transanal_fits_only_through_an_established_ileal_pouch_entry(self):
        """'when through names an established ileal_pouch entry', and never a gastric pouch or a Roux limb (4.3): through
        an entry established as any other type - its type's explanation; through not stated, not established, or
        naming an entry whose type is not established - a question; never T."""
        explained = {kind: {Y1: entry(kind)} for kind in AnatomyType if kind is not AnatomyType.ILEAL_POUCH}
        for kind, anatomy in explained.items():
            R = ent(Extent.POUCH, approach=Approach.TRANSANAL, through=Y1, anatomy=anatomy)
            with self.subTest(type=kind):
                self.assertEqual(C.fits(POUCH, X1, R), FF)
                self.assertEqual(C.class_misfit('44386', X1, R), (
                    held('procedure', A.TYPE, Y1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(13)], PROCEDURE),))
        for name, options, attribute in (
                ('no through', dict(anatomy=POUCH_ENTRY), A.THROUGH),
                ('through unresolved', dict(through=unresolved(Y1, n=9), anatomy=POUCH_ENTRY), A.THROUGH),
                ('through denied', dict(through=neg(Y1, 9), anatomy=POUCH_ENTRY), A.THROUGH),
                ('its type unresolved', dict(through=Y1, anatomy={Y1: entry(unresolved(AnatomyType.ILEAL_POUCH,
                                                                                       n=13))}), A.TYPE),
                ('its type doubted', dict(through=Y1, anatomy={Y1: entry(doubted(AnatomyType.ILEAL_POUCH,
                                                                                 [AnatomyType.GASTRIC_POUCH], 13))}),
                 A.TYPE),
                ('its type silent', dict(through=Y1, anatomy={Y1: entry(F.SILENT)}), A.TYPE)):
            R = ent(Extent.POUCH, approach=Approach.TRANSANAL, **options)
            with self.subTest(question=name):
                self.assertEqual(C.fits(POUCH, X1, R), U)
                (witness,) = C.class_misfit('44386', X1, R)
                self.assertEqual((witness.attribute, witness.kind, witness.rank), (attribute, Q, PROCEDURE))
        # the stoma class: transanal is no approach of it, through the stoma or not
        R = ent(Extent.ILEUM, approach=Approach.TRANSANAL, through=Y1, anatomy=STOMA_ENTRY)
        self.assertEqual(C.fits(STOMA, X1, R), FF)
        self.assertEqual(C.class_misfit('44382', X1, R)[0].attribute, A.APPROACH)

    def test_d219_a_denial_of_one_accepted_approach_leaves_the_other_open(self):
        """The pouch class accepts two approaches, so denying one leaves the other possible: U, a question on the
        approach, never the explanation of an approach established as another; the oral classes accept one, so a
        denial of the oral route is still their explanation."""
        for denied in (THROUGH_POUCH, Approach.TRANSANAL):
            R = ent(Extent.POUCH, approach=neg(denied, 3), through=Y1, anatomy=POUCH_ENTRY)
            with self.subTest(denied=denied):
                self.assertEqual(C.fits(POUCH, X1, R), U)
                (witness,) = C.class_misfit('44386', X1, R)
                self.assertEqual((witness.attribute, witness.kind, witness.result), (A.APPROACH, Q, Result.NEGATED))
        for approach in (ORAL, THROUGH_STOMA, Approach.TRANSNASAL):
            with self.subTest(another=approach):
                (witness,) = C.class_misfit('44386', X1, ent(Extent.POUCH, approach=approach, through=Y1,
                                                             anatomy=POUCH_ENTRY))
                self.assertEqual((witness.attribute, witness.kind), (A.APPROACH, X))
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, approach=neg(ORAL, 3))), FF)


# --- R5 RouteOfTheExamination (D114: the route is the examination's own) -------------------------------------------------


STOMA_ENTRY = {Y1: entry(AnatomyType.STOMA)}
POUCH_ENTRY = {Y1: entry(AnatomyType.ILEAL_POUCH)}


class RouteOfTheExamination(SimpleTestCase):
    def test_d114_44377_on_an_ileoscopy_through_the_ileostomy_is_held(self):
        """Problem 0: 44377 (an oral enteroscopy) was READY beside the correct 44382. The approach is established
        through the stoma: that explanation alone - the stoma passed through raises no route question beside it, whose
        answer could never release the code (refute-4c-r1 B: it tied the explanation at rank 8 and, a question before
        an explanation (4.8), would have been the item)."""
        R = ent(Extent.NEO_TERMINAL_ILEUM, approach=THROUGH_STOMA, through=Y1, anatomy=STOMA_ENTRY)
        self.assertEqual(C.class_misfit('44377', X1, R), (
            held('procedure', A.APPROACH, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(3)], PROCEDURE),))
        self.assertEqual(C.class_misfit('44382', X1, R), ())
        self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.CLASS)

    def test_an_approach_established_as_another_route_raises_no_route_doubt(self):
        """refute-4c-r1 B, every form of it: an oral class beside an approach established as another route (supported
        through the stoma or the pouch, or the oral route denied) and a through naming the stoma, the ileal pouch, or an
        entry of no established type - one witness, the approach's explanation, for 44361 and 44377 alike. The
        two-route doubt stays wherever the approach may be oral (supported oral, or not established)."""
        for name, approach, anatomy in (('through the stoma', THROUGH_STOMA, STOMA_ENTRY),
                                        ('through the pouch', THROUGH_POUCH, POUCH_ENTRY),
                                        ('the oral route denied', neg(ORAL, 3), STOMA_ENTRY),
                                        ('an untyped entry', THROUGH_STOMA,
                                         {Y1: entry(unresolved(AnatomyType.STOMA, n=13))})):
            for code, point in (('44377', Extent.ILEUM), ('44361', Extent.JEJUNUM)):
                R = ent(point, approach=approach, through=Y1, anatomy=anatomy)
                with self.subTest(case=name, code=code):
                    (witness,) = C.class_misfit(code, X1, R)
                    self.assertEqual((witness.attribute, witness.kind, witness.cause, witness.rank),
                                     (A.APPROACH, X, C.CLASS_CAUSE, PROCEDURE))
        for approach in (ORAL, None, unresolved(THROUGH_STOMA, n=3)):
            R = ent(Extent.ILEUM, approach=approach, through=Y1, anatomy=STOMA_ENTRY)
            with self.subTest(still_doubted=approach):
                self.assertIn(A.THROUGH, {witness.attribute for witness in C.class_misfit('44377', X1, R)})

    def test_d114_44382_is_ready_only_through_its_established_stoma_route(self):
        """Problem 0's other half: the stoma code fits on the approach established through the stoma; an approach not
        stated, or not established, is the route question."""
        base = dict(through=Y1, anatomy=STOMA_ENTRY)
        self.assertEqual(C.class_misfit('44382', X1, ent(Extent.ILEUM, approach=THROUGH_STOMA, **base)), ())
        for approach, witness in (
                (None, held('procedure', A.APPROACH, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT,
                            [unit(4)], PROCEDURE)),
                (unresolved(THROUGH_STOMA, Reason.APPRAISAL_DETACHED, n=3),
                 held('procedure', A.APPROACH, X1, Result.UNRESOLVED, Q, 'appraisal:detached',
                      Reason.APPRAISAL_DETACHED, [unit(3)], PROCEDURE))):
            R = ent(Extent.ILEUM, approach=approach, **base)
            with self.subTest(approach=approach):
                self.assertEqual(C.class_misfit('44382', X1, R), (witness,))
                self.assertEqual(C.misfit_form('44382', X1, R), C.ClassForm.ROUTE)

    def test_d114_44377_on_a_pouchoscopy_into_the_pre_pouch_ileum_is_held_and_44386_fits(self):
        R = ent(Extent.ILEUM, approach=THROUGH_POUCH, through=Y1, anatomy=POUCH_ENTRY)
        self.assertEqual(C.fits(ILEAL, X1, R), FF)
        self.assertEqual(C.class_misfit('44386', X1, R), ())

    def test_d114_the_oral_enteroscopy_beside_an_ileostomy_holds_44382_and_fits_44377_only_orally(self):
        """Problem 4: an oral double-balloon enteroscopy to the proximal ileum in a patient with an end ileostomy (an
        anatomy entry the session did not pass through). 44382 is held; 44377 fits only on the oral approach."""
        R = ent(Extent.ILEUM, anatomy=STOMA_ENTRY)
        self.assertEqual((C.fits(ILEAL, X1, R), C.fits(STOMA, X1, R)), (T, FF))
        unrouted = ent(Extent.ILEUM, approach=None, anatomy=STOMA_ENTRY)
        self.assertEqual(C.fits(ILEAL, X1, unrouted), U)
        self.assertEqual(C.misfit_form('44377', X1, unrouted), C.ClassForm.ROUTE)

    def test_d114_the_oral_enteroscopy_beside_a_j_pouch_holds_44386_and_fits_44377_only_orally(self):
        R = ent(Extent.ILEUM, anatomy=POUCH_ENTRY)
        self.assertEqual((C.fits(ILEAL, X1, R), C.fits(POUCH, X1, R)), (T, FF))
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, approach=None, anatomy=POUCH_ENTRY)), U)

    def test_d114_a_route_stated_two_ways_is_not_verified(self):
        """v1 held a route named in its statement and another named in its own words (D87). v2's two statements are
        the approach and the entry passed through: an oral approach beside a through that may name a stoma or an
        ileal pouch, in any state, is the route question; a gastric pouch, a Roux limb, a bypass or an anastomosis
        doubts nothing, and neither does a through left silent."""
        doubting = {
            'a stoma passed through': dict(through=Y1, anatomy=STOMA_ENTRY),
            'an ileal pouch passed through': dict(through=Y1, anatomy=POUCH_ENTRY),
            'a through not established naming a stoma': dict(through=unresolved(Y1, n=9), anatomy=STOMA_ENTRY),
            'an option naming a stoma': dict(through=unresolved(Y2, options=[Y1], n=9),
                                            anatomy={**STOMA_ENTRY, Y2: entry(AnatomyType.ROUX_LIMB)}),
            'a type doubted as a stoma': dict(through=Y1, anatomy={
                Y1: entry(doubted(AnatomyType.ANASTOMOSIS, [AnatomyType.STOMA]))}),
            'a type its control left open': dict(through=Y1, anatomy={
                Y1: entry(unresolved(AnatomyType.GASTRIC_POUCH, Reason.CONTROL_INCOHERENT,
                                     [AnatomyType.ILEAL_POUCH]))}),
        }
        for name, options in doubting.items():
            R = ent(Extent.ILEUM, **options)
            with self.subTest(doubt=name):
                fit = C.class_fit(ILEAL, X1, R)
                self.assertEqual(fit.truth, U)
                (witness,) = fit.witnesses
                self.assertEqual((witness.fact, witness.attribute, witness.subject, witness.kind, witness.rank),
                                 ('procedure', A.THROUGH, X1, Q, PROCEDURE))
                self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.ROUTE)
        for kind in (AnatomyType.GASTRIC_POUCH, AnatomyType.ROUX_LIMB, AnatomyType.BYPASS, AnatomyType.ANASTOMOSIS,
                     AnatomyType.SURGICALLY_ABSENT, AnatomyType.OTHER_ALTERATION):
            with self.subTest(control=kind):
                self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, through=Y1, anatomy={Y1: entry(kind)})), T)
        self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, through=neg(Y1, 9), anatomy=STOMA_ENTRY)), T)

    def test_d114_the_reach_never_establishes_a_route(self):
        """The reach names the point reached: a reach at the stoma or the pouch never stands for the approach or for the
        entry passed through."""
        R = ent(Extent.STOMA, Extent.NEO_TERMINAL_ILEUM, approach=None, anatomy=STOMA_ENTRY)
        self.assertEqual(C.fits(STOMA, X1, R), U)
        self.assertEqual({w.attribute for w in C.class_misfit('44382', X1, R)}, {A.APPROACH, A.THROUGH})
        self.assertEqual(C.routes(X1, R), frozenset())

    def test_d114_an_approach_not_established_never_verifies_a_route(self):
        for approach in (unresolved(ORAL, Reason.APPRAISAL_CONTRADICTS, n=3), doubted(ORAL, [THROUGH_STOMA], 3),
                         contradicted([ORAL, THROUGH_STOMA], 3), neg(THROUGH_STOMA, 3)):
            with self.subTest(approach=approach):
                self.assertEqual(C.fits(ILEAL, X1, ent(Extent.ILEUM, approach=approach)), U)

    def test_d114_an_incomplete_examination_asks_one_route_question_naming_both(self):
        """The approach unknown and the completion stated incomplete: both witnesses kept, in v1's route form (whose
        one question names the incompleteness too)."""
        R = ent(Extent.ILEUM, approach=None, completion=sup(Completion.INCOMPLETE, 11))
        self.assertEqual(C.class_misfit('44377', X1, R), (
            held('procedure', A.APPROACH, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.SILENT, [unit(4)],
                 PROCEDURE),
            held('extent', A.COMPLETION, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(11)], EXTENT)))
        self.assertEqual(C.misfit_form('44377', X1, R), C.ClassForm.ROUTE)


# --- R5 ScopeOfTheRoute ------------------------------------------------------------------------------------------------


class ScopeOfTheRoute(SimpleTestCase):
    def test_d114_without_a_stoma_or_pouch_the_oral_classes_read_their_approach(self):
        self.assertEqual(C.class_misfit('44377', X1, ent(Extent.ILEUM)), ())

    def test_a_reach_at_the_pouch_needs_its_approach_too(self):
        """v1 (D114) read the route for an ileal reach only, so a reach at the pouch made 44386 READY whatever the words.
        4.3 ENT asks the approach of every class: with none stated it is the route question (fail-closed against v1)."""
        R = ent(Extent.POUCH, approach=None, through=Y1, anatomy=POUCH_ENTRY)
        self.assertEqual(C.fits(POUCH, X1, R), U)
        self.assertEqual(C.misfit_form('44386', X1, R), C.ClassForm.ROUTE)
        self.assertEqual(C.fits(POUCH, X1, ent(Extent.POUCH, approach=THROUGH_POUCH, through=Y1, anatomy=POUCH_ENTRY)), T)

    def test_the_jejunal_class_needs_the_oral_route_beside_a_stoma(self):
        """4.3 ENT: oral for jejunal and ileal (D207, 1e:dev4): an ileoscopy through the ileostomy to the proximal
        jejunum explains 44361's hold (v1 read the jejunal reach only and made it READY; c2e53f8e holds it)."""
        R = ent(Extent.JEJUNUM, approach=THROUGH_STOMA, through=Y1, anatomy=STOMA_ENTRY)
        self.assertEqual(C.fits(JEJUNAL, X1, R), FF)
        self.assertEqual(C.class_misfit('44361', X1, R)[0].attribute, A.APPROACH)

    def test_another_approach_is_an_explanation(self):
        for approach in (Approach.TRANSANAL, Approach.TRANSNASAL, Approach.THROUGH_GASTROSTOMY, Approach.PERCUTANEOUS,
                         neg(ORAL, 3)):
            with self.subTest(approach=approach):
                (witness,) = C.class_misfit('44377', X1, ent(Extent.ILEUM, approach=approach))
                self.assertEqual((witness.attribute, witness.kind, witness.cause), (A.APPROACH, X, C.CLASS_CAUSE))


# --- D141, D148, D153, D160: the pouch is the small-intestinal one (the done-when of 8.1's 4c row) ----------------------


class GastricPouchAndRouxLimb(SimpleTestCase):
    def test_a_gastric_pouch_or_a_roux_limb_never_makes_the_pouch_class(self):
        """The done-when: through a gastric pouch, a Roux limb - or any anatomy type but an ileal pouch, in any state -
        neither pouch code fits, whatever the reach of the pouch class and the approach through_pouch; an established
        other type is an explanation naming that entry."""
        for kind in AnatomyType:
            if kind is AnatomyType.ILEAL_POUCH:
                continue
            for point in (Extent.POUCH, Extent.ILEUM, Extent.TERMINAL_ILEUM, Extent.NEO_TERMINAL_ILEUM):
                for state in (sup(kind, 13), unresolved(kind, n=13), doubted(kind, [], 13)):
                    R = ent(point, approach=THROUGH_POUCH, through=Y1, anatomy={Y1: entry(state)})
                    with self.subTest(kind=kind, reach=point, result=state.result):
                        self.assertNotEqual(C.fits(POUCH, X1, R), T)
                        for code in ('44385', '44386'):
                            witnesses = C.enteroscopy_hold(code, (E1,) if code == '44385' else (E2,), R)
                            self.assertTrue(witnesses)
                            if state.result is Result.SUPPORTED:
                                self.assertEqual(witnesses, (held('procedure', A.TYPE, Y1, Result.SUPPORTED, X,
                                                                  C.CLASS_CAUSE, None, [unit(13)], PROCEDURE),))
        # the Roux-en-Y enteroscopy (D141 problem 0) passed through both the gastric pouch and the Roux limb
        for through in (Y2, Y3):
            R = ent(Extent.ILEUM, approach=THROUGH_POUCH, through=through,
                    anatomy={Y2: entry(AnatomyType.GASTRIC_POUCH), Y3: entry(AnatomyType.ROUX_LIMB)})
            self.assertEqual(C.fits(POUCH, X1, R), FF)
            self.assertEqual(C.routes(X1, R), frozenset())

    def test_d141_a_pouch_of_no_established_type_is_a_doubt(self):
        """A pouch whose type is not established (unresolved, doubted, contradicted) opens no pouch class: a question on
        its type, and a doubted route."""
        for state in (unresolved(AnatomyType.ILEAL_POUCH, n=13),
                      doubted(AnatomyType.ILEAL_POUCH, [AnatomyType.GASTRIC_POUCH], 13),
                      contradicted([AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH], 13)):
            R = ent(Extent.ILEUM, approach=THROUGH_POUCH, through=Y1, anatomy={Y1: entry(state)})
            with self.subTest(result=state.result):
                self.assertEqual(C.fits(POUCH, X1, R), U)
                (witness,) = C.class_misfit('44386', X1, R)
                self.assertEqual((witness.attribute, witness.subject, witness.kind), (A.TYPE, Y1, Q))
                self.assertEqual((C.routes(X1, R), C.doubted_routes(X1, R)), (frozenset(), {THROUGH_POUCH}))

    def test_d148_an_entry_is_typed_by_its_own_type_fact_alone(self):
        """No other anatomy entry types the one passed through: an untyped pouch beside a gastric pouch stays a doubt,
        and an ileal pouch beside a gastric bypass or a PEG's stoma is the ileal pouch."""
        doubt = ent(Extent.ILEUM, approach=THROUGH_POUCH, through=Y1, anatomy={
            Y1: entry(unresolved(AnatomyType.ILEAL_POUCH, n=13)), Y2: entry(AnatomyType.GASTRIC_POUCH)})
        self.assertEqual(C.fits(POUCH, X1, doubt), U)
        for other in (AnatomyType.GASTRIC_POUCH, AnatomyType.BYPASS, AnatomyType.STOMA):
            R = ent(Extent.ILEUM, approach=THROUGH_POUCH, through=Y1,
                    anatomy={Y1: entry(AnatomyType.ILEAL_POUCH), Y2: entry(other)})
            with self.subTest(beside=other):
                self.assertEqual(C.fits(POUCH, X1, R), T)

    def test_d153_d160_the_appraised_through_tells_two_pouches_apart(self):
        """An ileal J-pouch beside a gastric pouch: v1 could not tell which pouch a route phrase named and held every
        pouch route (D160). v2's through names the entry (its control names the other one, D196)."""
        anatomy = {Y1: entry(AnatomyType.ILEAL_POUCH), Y2: entry(AnatomyType.GASTRIC_POUCH)}
        pouch = dict(approach=THROUGH_POUCH, anatomy=anatomy)
        self.assertEqual(C.fits(POUCH, X1, ent(Extent.ILEUM, through=Y1, **pouch)), T)
        self.assertEqual(C.fits(POUCH, X1, ent(Extent.ILEUM, through=Y2, **pouch)), FF)
        self.assertEqual(C.fits(POUCH, X1, ent(Extent.ILEUM, through=unresolved(Y1, options=[Y2], n=9), **pouch)), U)
        self.assertEqual(C.doubted_routes(X1, ent(Extent.ILEUM, through=unresolved(Y1, options=[Y2], n=9), **pouch)),
                         {THROUGH_POUCH})

    def test_d141_the_oral_enteroscopy_through_a_gastric_pouch_and_roux_limb_fits_the_ileal_class(self):
        """D141's problem 0 read faithfully: the scope entered orally and passed the gastric pouch (or the Roux limb)
        into the proximal ileum - 44377 fits, 44386 is held (the approach is no pouch route)."""
        anatomy = {Y2: entry(AnatomyType.GASTRIC_POUCH), Y3: entry(AnatomyType.ROUX_LIMB)}
        for through in (Y2, Y3):
            R = ent(Extent.ILEUM, through=through, anatomy=anatomy)
            with self.subTest(through=through):
                self.assertEqual((C.fits(ILEAL, X1, R), C.fits(POUCH, X1, R)), (T, FF))


# --- R5 RegionOfTheAct, rewired: act_elsewhere reads the act's own session fact ------------------------------------------


def egd_and_push(*acts: tuple[Id, dict], push_reach=Extent.JEJUNUM, unlisted=()) -> FactSet:
    """The parity note's encounter: an EGD X1 (examination E1) and a push enteroscopy X2 (examination E2) to the
    jejunum, with ``acts`` (and the kept ``unlisted`` statements)."""
    return factset({X1: session(SessionKind.EGD, reached=[Extent.SECOND_PORTION_DUODENUM]),
                    X2: session(approach=ORAL, reached=[push_reach])},
                   {E1: event(Kind.EXAMINATION, X1, n=14), E2: event(Kind.EXAMINATION, X2, n=15), **dict(acts)},
                   unlisted=unlisted)


def elsewhere(subject: Id) -> HeldFact:
    return held('performed_status', A.SESSION, subject, Result.SUPPORTED, X, C.ELSEWHERE_CAUSE, None,
                [unit(20 + subject.number)], STATUS)


class ActElsewhere(SimpleTestCase):
    def test_d114_an_act_placed_in_the_upper_endoscopy_holds_the_enteroscopy_act_code(self):
        """The parity note's input, the gastric APC's own session fact the EGD's: 44369 (enteroscopy with ablation) is
        held - documented in another procedure, an explanation at the status row - never READY, never excluded."""
        R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)))
        self.assertEqual(C.act_elsewhere('44369', R), (C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.ABLATION,)),))
        self.assertEqual(C.enteroscopy_hold('44369', (), R), (elsewhere(E3),))

    def test_d114_no_region_and_no_place_is_read(self):
        """No move (5.4): an act of the EGD's session is elsewhere wherever its place; an act of the enteroscopy's
        session is never elsewhere, whatever its place (K3 unresolves such a session fact at settle, never this
        module)."""
        far = egd_and_push((E3, event(Kind.ABLATION, X1, n=16, target_places=Extent.JEJUNUM)))
        self.assertEqual(C.enteroscopy_hold('44369', (), far), (elsewhere(E3),))
        own = egd_and_push((E3, event(Kind.ABLATION, X2, n=16, target_places=Extent.GASTRIC_ANTRUM)))
        self.assertEqual(C.act_elsewhere('44369', own), ())
        self.assertEqual(C.enteroscopy_hold('44369', (E3,), own), ())  # the control: X2's jejunal class fits

    def test_d114_an_act_whose_session_is_not_established_is_no_elsewhere_act(self):
        """D153's 'doubt of family' is SUPPORT row 6's question (procedure, 4.4), never this rule's explanation."""
        for name, act in (('its session unresolved', event(Kind.ABLATION, unresolved(X1, n=16), n=16)),
                          ('its session silent', {**event(Kind.ABLATION, X1, n=16), A.SESSION: (F.SILENT,)}),
                          ('its session doubted', event(Kind.ABLATION, doubted(X1, [X2], 16), n=16))):
            with self.subTest(case=name):
                self.assertEqual(C.act_elsewhere('44369', egd_and_push((E3, act))), ())
        unestablished = factset({X1: session(unresolved(SessionKind.EGD, n=2)), X2: session(approach=ORAL)},
                                {E3: event(Kind.ABLATION, X1, n=16)})
        self.assertEqual(C.act_elsewhere('44369', unestablished), ())

    def test_d114_one_act_of_the_group_in_its_own_family_keeps_the_group_out(self):
        R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)), (E4, event(Kind.ABLATION, X2, n=17)))
        self.assertEqual(C.act_elsewhere('44369', R), ())
        unplaced = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)),
                                (E4, event(Kind.ABLATION, unresolved(X2, n=17), n=17)))
        self.assertEqual(C.act_elsewhere('44369', unplaced), ())  # a doubt of family is no elsewhere act either

    def test_an_act_not_done_is_no_elsewhere_act(self):
        """4.3 rows 2-5 each supported (an act code: performed only): a denied, attempted, other-dated, other-performer,
        other-entry or unestablished act is the evaluation's (step 4a), never an elsewhere act."""
        for name, change in (('denied', dict(status=neg(Status.PERFORMED, 16))),
                             ('attempted', dict(status=Status.ATTEMPTED_NOT_COMPLETED)),
                             ('status in doubt', dict(status=unresolved(Status.PERFORMED, n=16))),
                             ('another date', {'date_relation': DateRelation.EARLIER_DATE}),
                             ('another performer', {'performer': Performer.OTHER_CLINICIAN}),
                             ('another entry', {'entry': Owner.NURSING})):
            facts = event(Kind.ABLATION, X1, n=16, **{k: v for k, v in change.items() if k == 'status'})
            for key, value in change.items():
                if key != 'status':
                    facts[Attribute[key.upper()]] = (sup(value),)
            with self.subTest(case=name):
                self.assertEqual(C.act_elsewhere('44369', egd_and_push((E3, facts))), ())

    def test_d114_examination_codes_and_other_families_never_get_the_elsewhere_hold(self):
        """The examination is the session and never moves; an EGD code's act in the EGD is its own."""
        R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)), (E4, event(Kind.BIOPSY, X1, n=17)))
        for code in ('44360', '44376', '44380', '44385', '43270', '43235', '43239'):
            with self.subTest(code=code):
                self.assertEqual(C.act_elsewhere(code, R), ())
        self.assertEqual(C.act_elsewhere('44361', R), (C.Elsewhere(E4, X1, SessionKind.EGD, (Kind.BIOPSY,)),))

    def test_a_positive_candidate_in_doubt_keeps_the_group_out(self):
        """refute-4c-r1 C: a done ablation of the EGD beside an ablation of the push enteroscopy whose date relation is
        not established - a positive candidate of 44369 (4.4) - is no elsewhere act: that candidate's own question
        (event_time, rank 6) must not be outranked by an explanation (rank 4) that can never become T. So for a candidate
        in doubt on any of rows 1-5 - its kind, status, date relation, performer or entry - in either session. A
        candidate that is not positive (another date or performer established, its status denied or planned) leaves
        the elsewhere act."""
        def ablation(in_session, change):
            return {**event(Kind.ABLATION, in_session, n=17), **{attribute: (value,) for attribute, value in
                                                                 change.items()}}

        doubts = {
            'its date in doubt': {A.DATE_RELATION: unresolved(DateRelation.ON_DATE_OF_SERVICE, n=17)},
            'its status in doubt': {A.STATUS: unresolved(Status.PERFORMED, n=17)},
            'its kind in doubt': {A.KIND: unresolved(Kind.BIOPSY, options=[Kind.ABLATION], n=17)},
            'its performer in doubt': {A.PERFORMER: doubted(Performer.DOCUMENTING_TEAM, [Performer.OTHER_CLINICIAN],
                                                            17)},
            'its entry another': {A.ENTRY: sup(Owner.NURSING, 17)},
            'attempted': {A.STATUS: sup(Status.ATTEMPTED_NOT_COMPLETED, 17)},
        }
        for where in (X2, X1):
            for name, change in doubts.items():
                R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)), (E4, ablation(where, change)))
                with self.subTest(case=name, session=where):
                    self.assertEqual(C.act_elsewhere('44369', R), ())
                    self.assertEqual(C.enteroscopy_hold('44369', (), R), ())
        for name, change in (('another date', {A.DATE_RELATION: sup(DateRelation.EARLIER_DATE, 17)}),
                             ('another performer', {A.PERFORMER: sup(Performer.OTHER_CLINICIAN, 17)}),
                             ('denied', {A.STATUS: neg(Status.PERFORMED, 17)}),
                             ('planned', {A.STATUS: sup(Status.PLANNED, 17)}),
                             ('another kind', {A.KIND: sup(Kind.BIOPSY, 17)})):
            R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)), (E4, ablation(X2, change)))
            with self.subTest(control=name):
                self.assertEqual(C.act_elsewhere('44369', R), (C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.ABLATION,)),))

    def test_every_elsewhere_act_is_a_witness(self):
        """HO-8: every candidate's witness - two gastric ablations, two witnesses."""
        R = egd_and_push((E3, event(Kind.ABLATION, X1, n=16)), (E5, event(Kind.ABLATION, X1, n=18)))
        self.assertEqual(C.enteroscopy_hold('44369', (), R), (elsewhere(E3), elsewhere(E5)))

    def test_a_bleeding_control_is_read_with_its_supported_purpose_and_an_umbrella_never_is(self):
        """catalogue.catalogue_kind: a clip whose purpose is supported hemostasis is a bleeding control (44366's act);
        with its purpose not supported it is a clip, of no group of 44366. An umbrella act never supports (4.3 row
        1)."""
        hemostatic = egd_and_push((E3, event(Kind.CLIP, X1, n=16, purpose=Purpose.HEMOSTASIS)))
        self.assertEqual(C.act_elsewhere('44366', hemostatic),
                         (C.Elsewhere(E3, X1, SessionKind.EGD, (Kind.BLEEDING_CONTROL,)),))
        for purpose in (unresolved(Purpose.HEMOSTASIS, n=16), Purpose.PROPHYLAXIS):
            R = egd_and_push((E3, event(Kind.CLIP, X1, n=16, purpose=purpose)))
            with self.subTest(purpose=purpose):
                self.assertEqual(C.act_elsewhere('44366', R), ())
        for umbrella in (Kind.INTERVENTION, Kind.REMOVAL):
            self.assertEqual(C.act_elsewhere('44364', egd_and_push((E3, event(umbrella, X1, n=16)))), ())

    def test_the_elsewhere_act_and_the_examination_codes_class_are_judged_apart(self):
        """An act code whose only act is elsewhere has no supporting act, so no session's class is judged for it (4.4:
        code_requirements over E*): its one witness is the elsewhere explanation. The enteroscopy's examination code,
        supported by the examination, has its class judged on its own session, and no elsewhere witness."""
        R = factset({X1: session(SessionKind.EGD), X2: session(approach=ORAL, reached=[Extent.ILEUM])},
                    {E2: event(Kind.EXAMINATION, X2, n=15), E3: event(Kind.ABLATION, X1, n=16)})
        self.assertEqual(C.enteroscopy_hold('44369', (), R), (elsewhere(E3),))
        self.assertEqual(C.enteroscopy_hold('44360', (E2,), R), (beyond_reached([unit(4)], X2),))


# --- enteroscopy_hold over the supporting acts ------------------------------------------------------------------------


class EnteroscopyHold(SimpleTestCase):
    def test_the_class_of_every_session_of_the_supporting_acts_is_judged(self):
        """Every supporting act's session must fit (4.4: code_requirements over E*, every act's witnesses): a biopsy in
        an ileal session beside one in a jejunal session holds 44361 on the first."""
        R = factset({X1: session(approach=ORAL, reached=[Extent.ILEUM]),
                     X3: session(approach=ORAL, reached=[Extent.JEJUNUM])},
                    {E2: event(Kind.BIOPSY, X1, n=15), E4: event(Kind.BIOPSY, X3, n=17)})
        self.assertEqual(C.sessions_of((E2, E4, E2), R), (X1, X3))
        self.assertEqual(C.enteroscopy_hold('44361', (E2, E4), R), (beyond_reached([unit(4)], X1),))
        self.assertEqual(C.enteroscopy_hold('44361', (E4,), R), ())

    def test_a_supporting_act_whose_session_is_not_supported_is_asked(self):
        R = factset({X1: session(approach=ORAL, reached=[Extent.JEJUNUM])},
                    {E6: event(Kind.BIOPSY, unresolved(X1, Reason.SESSION_UNREACHABLE, n=19), n=19)})
        self.assertEqual(C.enteroscopy_hold('44361', (E6,), R), (
            held('procedure', A.SESSION, E6, Result.UNRESOLVED, Q, 'unestablished:session_unreachable',
                 Reason.SESSION_UNREACHABLE, [unit(19)], PROCEDURE),))

    def test_a_session_that_is_not_an_enteroscopy_fails_the_family_part(self):
        R = ent(Extent.JEJUNUM, kind=SessionKind.EGD)
        self.assertEqual(C.class_misfit('44361', X1, R), (
            held('procedure', A.KIND, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [unit(2)], PROCEDURE),))
        self.assertEqual(C.fits(JEJUNAL, X1, ent(Extent.JEJUNUM, kind=unresolved(ENTEROSCOPY, n=2))), U)


# --- through the store: a settled row as the engine reads it (store.textfree_v2's view, facts.factset) -----------------


ROUX_BASE = (
    'SYNTHETIC ENTEROSCOPY REPORT - FICTIONAL PATIENT - NOT FOR CLINICAL USE',  # S1
    'Date of service: 11/09/2026',  # S2
    'Endoscopist: Synthetic Endoscopist, MD (fictional)',  # S3
    'History: Roux-en-Y gastric bypass with a small gastric pouch.',  # S4
    'Findings: The enteroscope was advanced orally through the gastric pouch and the Roux limb into the proximal ileum.',
    'Biopsies of an ulcer in the proximal ileum were taken with cold forceps.',  # S6
)
# S7: the completion stated (the default), or a doubt about it stated (refute-4c-r1 A's input through the store)
ROUX_COMPLETE = 'The examination was complete to the intended extent.'
ROUX_UNCLEAR = 'It is unclear whether the examination was complete.'
ROUX_LINES = ROUX_BASE + (ROUX_COMPLETE,)
ROUX_DOUBT_LINES = ROUX_BASE + (ROUX_UNCLEAR,)
# S7 the completion stated, S8 a statement in conflict with it (refute-4c-r2 A3's store-path input, tests/probe_rf4c2.py)
ROUX_CONFLICT_LINES = ROUX_BASE + (
    ROUX_COMPLETE, 'A tight stricture in the proximal ileum prevented further advancement of the enteroscope.')
# S8 a statement about the examination that no card describes, kept unlisted (D231's store-path input): told as an act,
# as a doubt, or as a denial.
ROUX_REPEATED = 'The ileal examination was then repeated.'
ROUX_REPEAT_UNCLEAR = 'It is unclear whether the ileal examination was repeated.'
ROUX_NOT_REPEATED = 'The ileal examination was not repeated.'


def roux_text(lines: tuple = ROUX_LINES) -> str:
    return '\n'.join(lines) + '\n'


def roux_span(index: int, lines: tuple = ROUX_LINES) -> Span:
    start = sum(len(line) + 1 for line in lines[:index - 1])
    return Span(start, start + len(lines[index - 1]))


def roux_at(words: str, after: str = '', lines: tuple = ROUX_LINES) -> dict:
    """Words located in the revision where they first occur at or after ``after``: the revision's own slice."""
    text = roux_text(lines)
    start = text.index(words, text.index(after) if after else 0)
    return {'start': start, 'end': start + len(words), 'text': words}


def doubted_slot(reason: str = 'doubt_stated') -> dict:
    """An EMPTY slot a doubt names, as settle stores it (3.3 row 2 before row 3): no claim, result unknown, the doubt's
    reason (store's _V2Fact accepts state null, result unknown, a doubt reason)."""
    return {'claim': TF.claim(None, ''), 'sources': [], 'checks': TF.checks(), 'appraisal': None, 'result': 'unknown',
            'reasons': [reason]}


def roux_row(approach: str = 'oral', *, lines: tuple = ROUX_LINES, completion: dict | None = None,
             doubts: tuple = (), exam_status: str = 'performed', unlisted: tuple = ()) -> dict:
    """The settled inventory of the Roux revision (D141's problem 0, read faithfully): an enteroscopy session X1 whose
    approach is ``approach``, which passed through the gastric pouch Y1 (beside the bypass Y2), reached the ileum and was
    complete (``completion``: another stored completion, with ``doubts``); its examination E1 (its status
    ``exam_status``, established) and a biopsy E2 there, every other fact established through TF's ledger; ``unlisted``:
    the kept unlisted statements (3.2.6), as settle stores them."""
    k = TF.Ledger()
    at = lambda words, after='': roux_at(words, after, lines)  # noqa: E731
    dos = lambda: TF.src(['S2'], 'document_frame', at('11/09/2026'))  # noqa: E731
    clinician = lambda: TF.src(['S3'], 'document_frame')  # noqa: E731
    findings = lambda: TF.src(['S5'], 'section', at('Findings:'))  # noqa: E731
    inherited = dict(inherited_from='N2')
    sections = [
        TF.section('N0', TF.src([], 'section'), owner=TF.fact('documenting_clinician', [clinician()]),
                   role=TF.fact('header', [TF.src(['S1'], 'section')]), occasion=TF.fact('on_date_of_service', [dos()]),
                   performer=TF.fact('documenting_team', [clinician()])),
        TF.section('N1', TF.src(['S4'], 'section', at('History:')),
                   owner=TF.fact('documenting_clinician', [clinician()]),
                   role=TF.fact('history', [TF.src(['S4'], 'section')])),
        TF.section('N2', TF.src(['S5'], 'section', at('Findings:')),
                   owner=TF.fact('documenting_clinician', [clinician()]),
                   role=TF.fact('findings', [TF.src(['S5'], 'section')]),
                   occasion=TF.est(k, 'N2', 'occasion', 'on_date_of_service', [dos()], control='earlier_date',
                                   literals=TF.DAY),
                   performer=TF.fact('documenting_team', [clinician()])),
    ]
    anatomy = [
        {'id': 'Y1', 'type': TF.est(k, 'Y1', 'type', 'gastric_pouch',
                                    [TF.src(['S4'], words=at('small gastric pouch'))], control='ileal_pouch'),
         'organ': TF.silent(), 'subtype': TF.silent(), 'joins': []},
        {'id': 'Y2', 'type': TF.est(k, 'Y2', 'type', 'bypass',
                                    [TF.src(['S4'], words=at('Roux-en-Y gastric bypass'))]),
         'organ': TF.silent(), 'subtype': TF.silent(), 'joins': []},
    ]
    if completion is None:
        completion = TF.est(k, 'X1', 'completion', 'complete',
                            [TF.src(['S7'], words=at('The examination was complete'))], control='incomplete')
    sessions = [TF.session(
        'X1', kind=TF.est(k, 'X1', 'kind', 'enteroscopy', [TF.src(['S1'], 'document_frame')], control='egd'),
        approach=TF.est(k, 'X1', 'approach', approach, [TF.src(['S5'], words=at('advanced orally'))],
                        control='through_stoma' if approach == 'oral' else 'oral'),
        through=TF.est(k, 'X1', 'through', 'Y1', [TF.src(['S5'], words=at('through the gastric pouch'))],
                       control='Y2'),
        reached=[TF.est(k, 'X1', 'reached', 'ileum', [TF.src(['S5'], words=at('proximal ileum'))],
                        control='ileum')],
        completion=completion)]

    def done(eid: str, anchor: str, kind: str, kind_words: dict, status_words: dict, status: str = 'performed',
             **more) -> dict:
        return TF.event(eid, [anchor], kind_words, status_words,
                        kind=TF.est(k, eid, 'kind', kind, [TF.src([anchor], words=kind_words)]),
                        status=TF.est(k, eid, 'status', status, [TF.src([anchor], words=status_words)],
                                      control='performed'),
                        session=TF.est(k, eid, 'session', 'X1', [TF.src([anchor])]),
                        date_relation=TF.est(k, eid, 'date_relation', 'on_date_of_service', [dos()],
                                             control='earlier_date', literals=TF.DAY, **inherited),
                        performer=TF.est(k, eid, 'performer', 'documenting_team', [clinician()],
                                         control='other_clinician', **inherited),
                        entry=TF.est(k, eid, 'entry', 'documenting_clinician', [findings()], control='nursing',
                                     **inherited), **more)

    events = [done('E1', 'S5', 'examination', at('enteroscope'), at('was advanced'), exam_status),
              done('E2', 'S6', 'biopsy', at('Biopsies'), at('were taken'),
                   target={'places': [TF.est(k, 'E2', 'target.places', 'ileum',
                                             [TF.src(['S6'], words=at('proximal ileum', 'Biopsies'))])]})]
    people = [{'id': 'P1', 'name': TF.src(['S3'], words=at('Synthetic Endoscopist')),
               'role': TF.fact('documenting_clinician', [TF.src(['S3'])])}]
    units = [{'id': f'S{n}', 'start': roux_span(n, lines).start, 'end': roux_span(n, lines).end, 'line': n,
              'paragraph': n, 'page': 1, 'forced': False} for n in range(1, len(lines) + 1)]
    return {'units': units, 'encounter': TF.encounter(TF.est(k, '', 'date_of_service', '2026-11-09', [dos()],
                                                            literals=TF.DAY), [], TF.fact('P1', [clinician()])),
            'people': people, 'sections': sections, 'sessions': sessions, 'anatomy': anatomy, 'lesions': [],
            'events': events, 'doubts': list(doubts), 'claims': k.claims, 'unlisted': list(unlisted)}


def roux_factset(approach: str = 'oral', *, lines: tuple = ROUX_LINES, **row) -> FactSet:
    """roux_row written by store.row_v2, read back by store.load_v2 and given as store.textfree_v2's view (DECISIONS
    D188), then built into the FactSet by facts.factset - the engine's own path."""
    text = roux_text(lines)
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    events = roux_row(approach, lines=lines, **row)
    fields = store.row_v2(encounter_id=TF.ENCOUNTER, revision_id=TF.REVISION, provider_run_id=TF.RUN,
                          appraisal_run_id=TF.APPRAISAL_RUN, revision_text=text, text_sha256=sha,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=events,
                          verification=TF.report(len(events['unlisted'])))
    fields = json.loads(json.dumps(fields))
    loaded = store.load_v2(fields, text_sha256=sha, response_sha256='3' * 64, appraisal_response_sha256='5' * 64)
    return F.factset(store.textfree_v2(loaded))


class ThroughTheStore(SimpleTestCase):
    def test_d141_the_oral_enteroscopy_after_a_gastric_bypass_read_from_a_settled_row(self):
        """The class rule over a row the store accepted, as the engine reads it: 44377 fits (the oral route, the gastric
        pouch passed through doubting nothing, the ileum reached), and 44386 is held - the approach is no pouch route,
        and the entry passed through is a gastric pouch - each an explanation citing its fact's own units."""
        R = roux_factset()
        self.assertEqual((C.fits(ILEAL, X1, R), C.fits(POUCH, X1, R)), (T, FF))
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), ())
        self.assertEqual(C.enteroscopy_hold('44386', (E2,), R), (
            held('procedure', A.APPROACH, X1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [roux_span(5)], PROCEDURE),
            held('procedure', A.TYPE, Y1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [roux_span(4)], PROCEDURE)))
        self.assertEqual(C.routes(X1, R), frozenset())

    def test_a_doubt_about_an_empty_completion_slot_holds_44377_through_the_store(self):
        """refute-4c-r1 A (critical), on a row the store accepted, as the engine reads it: 'It is unclear whether the
        examination was complete.' filed as the completion slot left empty and a doubt naming it (basis stated, its
        readings as given). The FactSet keeps the readings as options; the deeper class is a question on the
        completion, so 44377 is held - it was READY, the empty slot read as silence and silence as no incompleteness."""
        for readings in (['incomplete'], ['terminated'], ['complete', 'incomplete'], ['complete']):
            doubts = ({'about': 'completion', 'objects': ['X1'], 'units': ['S7'], 'basis': 'stated',
                       'readings': readings},)
            R = roux_factset(lines=ROUX_DOUBT_LINES, completion=doubted_slot(), doubts=doubts)
            found = F.fact(R, X1, A.COMPLETION)
            with self.subTest(readings=readings):
                self.assertEqual((found.result, found.state, found.value, {value.value for value in found.options}),
                                 (Result.UNKNOWN, None, None, set(readings)))
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
                    held('extent', A.COMPLETION, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.DOUBT_STATED,
                         [roux_span(5, ROUX_DOUBT_LINES)], EXTENT),))
        # the control, the same row with the completion stated: 44377 fits (test_d141_... above)
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), roux_factset()), ())

    def test_the_done_when_through_the_store_a_gastric_pouch_never_makes_the_pouch_class(self):
        """The misreading D141 guarded against, approach through_pouch - or, D219, transanal - beside the gastric pouch
        passed through: the pouch class is still held, on the gastric pouch alone."""
        for approach in ('through_pouch', 'transanal'):
            R = roux_factset(approach)
            with self.subTest(approach=approach):
                self.assertEqual(C.fits(POUCH, X1, R), FF)
                self.assertEqual(C.class_misfit('44386', X1, R), (
                    held('procedure', A.TYPE, Y1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [roux_span(4)],
                         PROCEDURE),))
                self.assertEqual(C.fits(ILEAL, X1, R), FF)

    def test_d217_a3_a_contradicted_or_doubted_completion_holds_44377_through_the_store(self):
        """refute-4c-r2 A3 (critical) on rows the store accepted, as the engine reads them (its probe
        tests/probe_rf4c2.py p1 and p2): the completion claimed complete (S7) with a conflict doubt naming it (S8, a
        stricture stopping the enteroscope; readings none or complete) - contradicted, contradicted_by_pass1, the claim
        kept - or with a stated doubt naming it (S7 'It is unclear whether the examination was complete.'; readings none
        or complete) - unknown, doubt_stated, the value kept. Each holds 44377 with ONE question on the completion (rank
        1 for the conflict); each was READY."""
        for readings in ([], ['complete']):
            completion = TF.fact('complete', [TF.src(['S7'])], state='supported', result='contradicted',
                                 reasons=('contradicted_by_pass1',))
            doubts = ({'about': 'completion', 'objects': ['X1'], 'units': ['S8'], 'basis': 'conflict',
                       'readings': readings},)
            R = roux_factset(lines=ROUX_CONFLICT_LINES, completion=completion, doubts=doubts)
            found = F.fact(R, X1, A.COMPLETION)
            with self.subTest(conflict=readings):
                self.assertEqual((found.result, found.state, found.value, found.options),
                                 (Result.CONTRADICTED, FactState.SUPPORTED, Completion.COMPLETE, ()))
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
                    held('conflict:examination', A.COMPLETION, X1, Result.CONTRADICTED, Q, C.READING_CONTRADICTED,
                         Reason.CONTRADICTED_BY_PASS1, [roux_span(7, ROUX_CONFLICT_LINES)], 1),))
        for readings in ([], ['complete']):
            completion = TF.fact('complete', [TF.src(['S7'])], state='supported', result='unknown',
                                 reasons=('doubt_stated',))
            doubts = ({'about': 'completion', 'objects': ['X1'], 'units': ['S7'], 'basis': 'stated',
                       'readings': readings},)
            R = roux_factset(lines=ROUX_DOUBT_LINES, completion=completion, doubts=doubts)
            with self.subTest(doubt=readings):
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
                    held('extent', A.COMPLETION, X1, Result.UNKNOWN, Q, C.READING_UNKNOWN, Reason.DOUBT_STATED,
                         [roux_span(7, ROUX_DOUBT_LINES)], EXTENT),))
        # the control: a conflict doubt reading incomplete, as the refuter's p3
        completion = TF.fact('complete', [TF.src(['S7'])], state='supported', result='contradicted',
                             reasons=('contradicted_by_pass1',))
        doubts = ({'about': 'completion', 'objects': ['X1'], 'units': ['S8'], 'basis': 'conflict',
                   'readings': ['incomplete']},)
        R = roux_factset(lines=ROUX_CONFLICT_LINES, completion=completion, doubts=doubts)
        (witness,) = C.enteroscopy_hold('44377', (E2,), R)
        self.assertEqual((witness.fact, witness.rank), ('conflict:examination', 1))

    def test_d231_an_unlisted_doubt_holds_44377_through_the_store_as_the_act_does(self):
        """D231 on rows the store accepted, as the engine reads them: the Roux revision with its examination E1 filed as
        begun and not completed (established) and S8, a statement about the examination that no card describes, kept
        unlisted (kind examination, card X1) - 'The ileal examination was then repeated.' as an act, 'It is unclear
        whether the ileal examination was repeated.' as a doubt: 44377 is held with the one unlisted question quoting
        S8, the same for both natures (it was D72's explanation for the doubt). Kept as a denial ('The ileal examination
        was not repeated.'), or not kept at all, it leaves D72's explanation on E1."""
        def stored(line: str, what: str | None) -> tuple:
            lines = ROUX_LINES + (line,)
            unlisted = ({'units': ['S8'], 'what': what, 'kind': 'examination', 'session': 'X1'},) if what else ()
            return lines, roux_factset(lines=lines, exam_status='attempted_not_completed', unlisted=unlisted)

        for what, line in (('act', ROUX_REPEATED), ('doubt', ROUX_REPEAT_UNCLEAR)):
            lines, R = stored(line, what)
            with self.subTest(what=what):
                self.assertEqual([(entry.what, entry.kind, entry.session) for entry in R.unlisted],
                                 [(UnlistedWhat(what), Kind.EXAMINATION, X1)])
                self.assertEqual(C.fits(ILEAL, X1, R), U)
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
                    held('performed_status', None, X1, None, Q, C.UNLISTED, None, [roux_span(8, lines)], 2),))
        for what in ('denial', None):
            lines, R = stored(ROUX_NOT_REPEATED, what)
            with self.subTest(control=what):
                self.assertEqual(C.fits(ILEAL, X1, R), FF)
                self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), (
                    held('extent', A.STATUS, E1, Result.SUPPORTED, X, C.CLASS_CAUSE, None, [roux_span(5, lines)],
                         EXTENT),))

    def test_d217_a_silent_completion_fits_through_the_store(self):
        """D217 on a row the store accepted: the completion slot silent (the Roux note with no completion sentence
        filed) - result unknown, reason silent, nothing kept beside it - and 44377 fits (the installed reading)."""
        R = roux_factset(completion=TF.silent())
        found = F.fact(R, X1, A.COMPLETION)
        self.assertEqual((found.result, found.state, found.value, found.options, found.reasons),
                         (Result.UNKNOWN, None, None, (), (Reason.SILENT,)))
        self.assertEqual(C.fits(ILEAL, X1, R), T)
        self.assertEqual(C.enteroscopy_hold('44377', (E2,), R), ())


# --- what the module reads (P-READSET, P-INDEP) --------------------------------------------------------------------------


_ROLE_FAMILY = {RQ.Role.SESSION: IdFamily.SESSION, RQ.Role.ANATOMY: IdFamily.ANATOMY, RQ.Role.LESION: IdFamily.LESION,
                **{role: IdFamily.EVENT for role in (RQ.Role.ACT, RQ.Role.EXAMINATION, RQ.Role.VISIT,
                                                     RQ.Role.SESSION_ACT, RQ.Role.COUNTERPART, RQ.Role.WHOLE,
                                                     RQ.Role.STATEMENT, RQ.Role.SAME_DAY_ACT)}}


def rich_factsets() -> list:
    """Inputs that drive every branch: classes fitting and not, every route and anatomy (a transanal pouchoscopy among
    them), points beyond the jejunal class (an ileal and a colon point) and the small bowel beside the jejunum, deeper
    parts (a doubted, an empty doubted, a contradicted, a stated and a silent completion; an examination established
    attempted, one not established, one whose session is silent; a synthetic examination act, kept as an act or - D231 -
    as a doubt), elsewhere acts and an unlisted act or doubt of their group."""
    out = []
    completions = (doubted(Completion.COMPLETE, [Completion.INCOMPLETE], 11), None, empty([Completion.INCOMPLETE], n=11),
                   conflict(Completion.COMPLETE, n=11), sup(Completion.COMPLETE, 11))
    approaches = (ORAL, THROUGH_STOMA, THROUGH_POUCH, None, unresolved(ORAL, n=3), Approach.TRANSANAL)
    for index, approach in enumerate(approaches):
        for anatomy in (STOMA_ENTRY, POUCH_ENTRY, {Y1: entry(unresolved(AnatomyType.ILEAL_POUCH, n=13))}):
            for turn, reached in enumerate((
                    (Extent.JEJUNUM,), (Extent.ILEUM, Extent.POUCH), (neg(Extent.ILEUM, 4),), (),
                    (Extent.JEJUNUM, Extent.ILEUM), (Extent.JEJUNUM, unresolved(Extent.TERMINAL_ILEUM, n=5)),
                    (Extent.JEJUNUM, Extent.CECUM), (Extent.SMALL_BOWEL, Extent.JEJUNUM))):
                sessions = {X1: session(approach=approach, through=Y1 if index % 2 else empty([Y1], n=9),
                                        reached=reached, completion=completions[(index + turn) % len(completions)]),
                            X2: session(SessionKind.EGD)}
                exam_status = (unresolved(Status.PERFORMED, n=14), Status.ATTEMPTED_NOT_COMPLETED)[turn % 2]
                events = {E1: event(Kind.EXAMINATION, X1, status=exam_status, n=14),
                          E2: event(Kind.BIOPSY, X1, n=15),
                          E3: event(Kind.CLIP, X2, n=16, purpose=Purpose.HEMOSTASIS),
                          E4: event(Kind.ABLATION, X2, n=17),
                          E5: event(Kind.BIOPSY, unresolved(X1, n=18), n=18)}
                if turn % 3 == 0:
                    events[E6] = {**event(Kind.EXAMINATION, X1, status=Status.ATTEMPTED_NOT_COMPLETED, n=19),
                                  A.SESSION: (F.SILENT,)}
                unlisted = ([unlisted_act(), unlisted_act(Kind.ABLATION, None, n=31)] if turn % 4 == 1 else
                            [unlisted_act(what=UnlistedWhat.DOUBT),
                             unlisted_act(Kind.ABLATION, None, n=31, what=UnlistedWhat.DOUBT)] if turn % 4 == 3 else [])
                out.append(factset(sessions, events, anatomy, unlisted))
    return out


class Reads(SimpleTestCase):
    def test_every_read_lies_inside_the_codes_requirement_closure_and_is_claimed(self):
        """A recording proxy over facts.fact and facts.members (P-READSET's form): every (object family, attribute) the
        module reads for an enteroscopy code is one its requirements read (engine/requirements.dependencies, by role)
        and one CLAIMED claims for that object class (3.2.1), so P-INDEP's perturbations outside the closure cannot
        move it."""
        reads: list = []
        every: set = set()
        real_fact, real_members = F.fact, F.members

        def fact(R, subject, attribute):
            reads.append((subject.family if subject is not None else None, attribute))
            return real_fact(R, subject, attribute)

        def members(R, subject, attribute):
            reads.append((subject.family if subject is not None else None, attribute))
            return real_members(R, subject, attribute)

        F.fact, F.members = fact, members
        try:
            for code in FAMILY_CODES:
                closure = RQ.dependencies(code)
                allowed = {(_ROLE_FAMILY[role], attribute) for role, attributes in closure.reads.items()
                           if role in _ROLE_FAMILY for attribute in attributes}
                for R in rich_factsets():
                    del reads[:]
                    C.enteroscopy_hold(code, (E1, E2, E5), R)
                    C.misfit_form(code, X1, R)
                    with self.subTest(code=code):
                        self.assertTrue(reads)
                        self.assertLessEqual(set(reads), allowed, set(reads) - allowed)
                    every.update(reads)
        finally:
            F.fact, F.members = real_fact, real_members
        # the reads the inputs drove: every attribute the class and elsewhere rules name, so the pin is not vacuous
        self.assertEqual({attribute for family, attribute in every if family is IdFamily.SESSION},
                         {A.KIND, A.APPROACH, A.THROUGH, A.REACHED, A.COMPLETION})
        self.assertEqual({attribute for family, attribute in every if family is IdFamily.EVENT},
                         {A.KIND, A.SESSION, A.STATUS, A.DATE_RELATION, A.PERFORMER, A.ENTRY, A.PURPOSE})
        self.assertEqual({attribute for family, attribute in every if family is IdFamily.ANATOMY}, {A.TYPE})
        claimed_classes = {IdFamily.SESSION: RQ.ObjectClass.SESSION, IdFamily.ANATOMY: RQ.ObjectClass.ANATOMY}
        for family, attribute in every:
            with self.subTest(read=(family, attribute)):
                if family is IdFamily.EVENT:
                    self.assertTrue(any(RQ.claimed(RQ.ObjectClass.ACT, attribute, kind) for kind in Kind), attribute)
                else:
                    self.assertTrue(RQ.claimed(claimed_classes[family], attribute), attribute)

    def test_the_session_examination_slot_and_the_reach_anatomy_are_never_read(self):
        """The session's examination slot is no claim (it would settle unappraised, 3.2.1); reached_anatomy and
        device_reached are in no class rule's read-set (K6, P19)."""
        source = MODULE.read_text(encoding='utf-8')
        for name in ('EXAMINATION)', 'REACHED_ANATOMY', 'DEVICE_REACHED'):
            self.assertNotIn(f'_A.{name}', source)


# --- P-MONO (9.4): weakening never turns a misfit into a fit ----------------------------------------------------------


_EXTENT_POOL = (Extent.JEJUNUM, Extent.ILEUM, Extent.TERMINAL_ILEUM, Extent.NEO_TERMINAL_ILEUM, Extent.POUCH,
                Extent.SECOND_PORTION_DUODENUM, Extent.FOURTH_PORTION_DUODENUM, Extent.SMALL_BOWEL, Extent.STOMA,
                Extent.CECUM, Extent.COLON, Extent.ILEOCECAL_VALVE, Extent.RECTUM)
_SINGLE = ('kind', 'approach', 'through', 'completion', 'Y1', 'Y2', 'exam_status', 'exam_session', 'exam_kind',
           'exam2_status', 'exam2_session', 'exam2_kind')
# The session's slots a spec may leave silent (None), each at its unit: 9.4's added doubt names an empty slot too.
_SILENT_SLOTS = {'approach': 3, 'through': 9, 'completion': 11}
# The kept unlisted statements a spec may carry (3.2.6; D216's and D231's synthetic acts and doubts among them, and a
# denial, which is none): never weakened.
_UNLISTED_POOL = ((), (unlisted_act(),), (unlisted_act(None, None),), (unlisted_act(Kind.BIOPSY, X1),),
                  (unlisted_act(what=UnlistedWhat.DOUBT),), (unlisted_act(None, None, what=UnlistedWhat.DOUBT),),
                  (unlisted_act(what=UnlistedWhat.DENIAL),))


def _fact(draw, values, n: int, *, silent_ok: bool = True):
    choice = draw(st.integers(0 if silent_ok else 1, 5))
    value = draw(st.sampled_from(values))
    if choice == 0:
        return None
    if choice == 1 or choice == 2:
        return sup(value, n)
    if choice == 3:
        return neg(value, n)
    if choice == 4:
        return unresolved(value, options=[draw(st.sampled_from(values))], n=n)
    return doubted(value, [draw(st.sampled_from(values))], n)


def _fitting(exam_class: EnteroscopyClass, draw) -> dict:
    """A session on which ``exam_class`` fits (every part T) or sits at a boundary of it, with other points reached -
    passed on the way, or deeper than the class's reach (an ileal or a colon point beside a jejunal one, which holds
    the jejunal class: D218) - and harmless anatomy: an approach the class accepts (D219's transanal for the pouch
    class among them), a completion stated complete or silent (D217: both fit), one examination performed, and no
    second examination or unlisted statement (specs adds them)."""
    route = exam_class in C.ROUTE_CLASSES
    point = draw(st.sampled_from(sorted(catalogue.ENTEROSCOPY_CLASS_REACH[exam_class], key=lambda e: e.value)))
    passed = draw(st.lists(st.sampled_from((Extent.SECOND_PORTION_DUODENUM, Extent.FOURTH_PORTION_DUODENUM,
                                            Extent.STOMA, Extent.ILEUM, Extent.TERMINAL_ILEUM, Extent.CECUM,
                                            Extent.SMALL_BOWEL)), max_size=2))
    approach = draw(st.sampled_from(sorted(C.CLASS_APPROACHES[exam_class], key=lambda e: e.value)))
    return {
        'kind': sup(ENTEROSCOPY, 2), 'approach': sup(approach, 3),
        'through': sup(Y1, 9) if route else draw(st.sampled_from((None, sup(Y2, 9)))),
        'completion': draw(st.sampled_from((None, sup(Completion.COMPLETE, 11)))),
        'reached': [sup(extent, 4 + index) for index, extent in enumerate(passed + [point])],
        'Y1': sup(catalogue.ENTEROSCOPY_CLASS_ANATOMY.get(exam_class, AnatomyType.STOMA), 13),
        'Y2': sup(draw(st.sampled_from((AnatomyType.GASTRIC_POUCH, AnatomyType.ROUX_LIMB))), 14),
        'exam_status': sup(Status.PERFORMED, 15), 'exam_session': sup(X1, 15), 'exam_kind': sup(Kind.EXAMINATION, 15),
        'exam2_status': None, 'exam2_session': None, 'exam2_kind': None, 'unlisted': (),
    }


@st.composite
def specs(draw) -> dict:
    """A session that fits a random class, each fact then replaced, with a chance, by a random one in any state - so
    the inputs fall on both sides of every part's boundary."""
    spec = _fitting(draw(st.sampled_from(C.CLASSES)), draw)
    random = {
        'kind': lambda: _fact(draw, (ENTEROSCOPY, ENTEROSCOPY, SessionKind.EGD), 2, silent_ok=False),
        'approach': lambda: _fact(draw, tuple(Approach), 3),
        'through': lambda: _fact(draw, (Y1, Y2), 9),
        'completion': lambda: _fact(draw, tuple(Completion), 11),
        'reached': lambda: [_fact(draw, _EXTENT_POOL, 4 + index, silent_ok=False)
                            for index in range(draw(st.integers(0, 3)))],
        'Y1': lambda: _fact(draw, tuple(AnatomyType), 13, silent_ok=False),
        'Y2': lambda: _fact(draw, tuple(AnatomyType), 14, silent_ok=False),
        'exam_status': lambda: _fact(draw, tuple(Status), 15, silent_ok=False),
        'exam_session': lambda: _fact(draw, (X1, X2, X3), 15, silent_ok=False),
        'exam_kind': lambda: _fact(draw, (Kind.EXAMINATION, Kind.EXAMINATION, Kind.BIOPSY), 15, silent_ok=False),
    }
    for name, make in random.items():
        if draw(st.integers(0, 9)) < 2:
            spec[name] = make()
    # the deeper parts' boundary (D43, D56, D72 as D217 reads it): a stated incompleteness, an attempted examination
    # alone, or an attempt beside a second examination (performed, attempted or planned; of X1 or not; possibly no
    # examination) - pass 1's sequence among them (refute-4c-r2 SEQ)
    deeper = draw(st.integers(0, 9))
    if deeper == 0:
        spec['completion'] = sup(draw(st.sampled_from(sorted(C.STOPPED_SHORT, key=lambda c: c.value))), 11)
    elif deeper == 1:
        spec['exam_status'] = sup(Status.ATTEMPTED_NOT_COMPLETED, 15)
    elif deeper in (2, 3):
        spec['exam_status'] = sup(Status.ATTEMPTED_NOT_COMPLETED, 15)
        spec['exam2_status'] = draw(st.sampled_from((sup(Status.PERFORMED, 16), sup(Status.ATTEMPTED_NOT_COMPLETED, 16),
                                                     sup(Status.PLANNED, 16))))
        spec['exam2_session'] = draw(st.sampled_from((sup(X1, 16), sup(X1, 16), sup(X2, 16), F.SILENT,
                                                      unresolved(X3, Reason.REFERENCE_INVALID, n=16))))
        spec['exam2_kind'] = draw(st.sampled_from((sup(Kind.EXAMINATION, 16), sup(Kind.EXAMINATION, 16),
                                                   unresolved(Kind.EXAMINATION, n=16))))
    if draw(st.integers(0, 9)) < 2:
        spec['unlisted'] = draw(st.sampled_from(_UNLISTED_POOL))
    return spec


def build(spec: dict) -> FactSet:
    """The spec's FactSet: X1 and its facts, beside the EGD X2 - so an examination's session X2 names another
    session the FactSet holds, and X3 one it does not hold (4.11; DECISIONS D227's 4d R2-2: possibly X1)."""
    sessions = {X1: {A.KIND: (spec['kind'],), A.REACHED: tuple(spec['reached'])}, X2: session(SessionKind.EGD)}
    for name, attribute in (('approach', A.APPROACH), ('through', A.THROUGH), ('completion', A.COMPLETION)):
        if spec[name] is not None:
            sessions[X1][attribute] = (spec[name],)
    events = {E1: {A.KIND: (spec['exam_kind'],), A.SESSION: (spec['exam_session'],),
                   A.STATUS: (spec['exam_status'],)}}
    if spec['exam2_status'] is not None:  # a second examination: E3, all three of its facts given
        events[E3] = {A.KIND: (spec['exam2_kind'],), A.SESSION: (spec['exam2_session'],),
                      A.STATUS: (spec['exam2_status'],)}
    return factset(sessions, events, {Y1: {A.TYPE: (spec['Y1'],)}, Y2: {A.TYPE: (spec['Y2'],)}}, spec['unlisted'])


def _weaker(found: Fact, extra) -> list:
    """Every weakening of one fact (9.4): an established fact to unresolved, with or without an unrejected control's
    value; an added doubt - stated, unclear or conflict (its reading; a conflict keeps the claim, contradicted:
    refute-4c-r2 A3)."""
    readings = tuple(found.options) + (extra,)
    out = [replace(found, result=Result.UNKNOWN, options=readings, reasons=(Reason.DOUBT_STATED,)),
           replace(found, result=Result.UNKNOWN, options=readings, reasons=(Reason.DOUBT_UNCLEAR,)),
           replace(found, result=Result.CONTRADICTED, options=readings, reasons=(Reason.CONTRADICTED_BY_PASS1,))]
    if F.established(found):
        out += [replace(found, result=Result.UNRESOLVED, reasons=(Reason.APPRAISAL_UNCLEAR,)),
                replace(found, result=Result.UNRESOLVED, options=(extra,), reasons=(Reason.CONTROL_INCOHERENT,))]
    return out


def _weaker_silent(extra, n: int) -> list:
    """Every weakening of a silent slot (9.4's added doubt, on an empty slot): a stated or a conflict doubt naming it,
    its reading kept."""
    return [empty([extra], Reason.DOUBT_STATED, n),
            Fact(Result.CONTRADICTED, None, None, (extra,), (Reason.CONTRADICTED_BY_PASS1,), (unit(n),))]


def weakenings(spec: dict, extra_of: Callable[[str], object]) -> Iterable[tuple[Fact | None, dict]]:
    """(the reached member deleted, or None; the weaker spec) for every weakening of one fact."""
    for name in _SINGLE:
        if spec[name] is not None:
            for weaker in _weaker(spec[name], extra_of(name)):
                yield None, {**spec, name: weaker}
        elif name in _SILENT_SLOTS:
            for weaker in _weaker_silent(extra_of(name), _SILENT_SLOTS[name]):
                yield None, {**spec, name: weaker}
    for index, point in enumerate(spec['reached']):
        yield point, {**spec, 'reached': spec['reached'][:index] + spec['reached'][index + 1:]}  # a deleted member
        for weaker in _weaker(point, extra_of('reached')):
            yield None, {**spec, 'reached': spec['reached'][:index] + [weaker] + spec['reached'][index + 1:]}


def beyond_member(member: Fact | None) -> bool:
    """The one weakening D218's reading lets release (named for 6a's P-MONO): a deleted reached member that may name a
    point beyond the jejunal class - stated here independently of the module: not negated, its value or an option an
    ileal point or a point of the large bowel's regions (the colon, the rectum, the anal canal). The small bowel is no
    such point (D218)."""
    far = catalogue.ENTEROSCOPY_CLASS_REACH[ILEAL] | {
        point for point in Extent if AN.region(point) in (AN.Region.COLON, AN.Region.RECTUM, AN.Region.ANUS)}
    return (member is not None and member.result is not Result.NEGATED
            and any(isinstance(value, Extent) and value in far for value in (member.value, *member.options)))


_EXTRA_DOMAIN = {'kind': tuple(SessionKind), 'approach': tuple(Approach), 'through': (Y1, Y2),
                 'completion': tuple(Completion), 'Y1': tuple(AnatomyType), 'Y2': tuple(AnatomyType),
                 'exam_status': tuple(Status), 'exam_session': (X1, X2, X3), 'exam_kind': tuple(Kind),
                 'exam2_status': tuple(Status), 'exam2_session': (X1, X2, X3), 'exam2_kind': tuple(Kind),
                 'reached': _EXTENT_POOL}


class Monotone(SimpleTestCase):
    @settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(specs(), st.data())
    def test_p_mono_weakening_never_turns_a_misfit_into_a_fit(self, spec, data):
        """For random settled sessions and every weakening of one fact (established to unresolved, an unrejected
        control's value, an added doubt - stated, unclear or conflict - on a fact or a silent slot, a deleted reached
        member): a class that does not fit never fits after it, and a code with a witness keeps one. The one release
        allowed is D218's, named: a deleted member that may be beyond the jejunal class releases that class."""
        before = build(spec)
        fits_before = {exam_class: C.fits(exam_class, X1, before) for exam_class in C.CLASSES}
        held_before = {code: bool(C.enteroscopy_hold(code, (E1,), before)) for code in CODE_OF.values()}
        extra_of = lambda name: data.draw(st.sampled_from(_EXTRA_DOMAIN[name]))  # noqa: E731
        for deleted, weaker in weakenings(spec, extra_of):
            after = build(weaker)
            exempt = beyond_member(deleted)  # D218: the jejunal class only, and only by this deletion
            for exam_class, truth in fits_before.items():
                if truth is not T and C.fits(exam_class, X1, after) is T:
                    self.assertTrue(exam_class is JEJUNAL and exempt, (exam_class, spec, weaker))
            for code, was_held in held_before.items():
                if was_held and not C.enteroscopy_hold(code, (E1,), after):
                    self.assertTrue(code == CODE_OF[JEJUNAL] and exempt, (code, spec, weaker))

    def test_p_det_identical_inputs_give_identical_witnesses(self):
        for R in rich_factsets()[:12]:
            for code in FAMILY_CODES:
                self.assertEqual(C.enteroscopy_hold(code, (E1, E2), R), C.enteroscopy_hold(code, (E1, E2), R))


# --- the boundary: 5.7 measure 4, the imports, mypy --strict ------------------------------------------------------------


class BoundaryTests(SimpleTestCase):
    def test_the_module_keeps_measure_4(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_it_imports_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.classes\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = result.stdout.strip().split(',')
        self.assertIn('studio.interpretation.engine.classes', loaded)
        self.assertEqual([m for m in loaded if m.startswith('studio.') and not m.startswith(
            ('studio.interpretation.engine', 'studio.interpretation.contract')) and m != 'studio.interpretation'], [])
        self.assertNotIn('studio.interpretation.contract.segment', loaded)
        self.assertNotIn('studio.interpretation.contract.geometry', loaded)

    def test_mypy_strict_passes(self):
        result = subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull,
                                 'studio/interpretation/engine/classes.py'], capture_output=True, text=True,
                                timeout=600, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 1 source file', result.stdout)

    def test_witnesses_hold_no_text(self):
        """Every witness field is an Enum, an Id, an int, a Span, or CPT Studio's own fact and cause codes (P1)."""
        causes = set()
        for R in rich_factsets():
            for code in FAMILY_CODES:
                for witness in C.enteroscopy_hold(code, (E1, E2, E5), R):
                    self.assertIsInstance(witness, HeldFact)
                    self.assertTrue(all(isinstance(span, Span) for span in witness.spans))
                    self.assertIsInstance(witness.subject, Id)
                    self.assertTrue(witness.attribute is None or isinstance(witness.attribute, Attribute))
                    self.assertTrue(witness.cause in {C.CLASS_CAUSE, C.ELSEWHERE_CAUSE, C.READING_UNKNOWN,
                                                      C.READING_CONTRADICTED, C.UNLISTED}
                                    or witness.cause.split(':')[0] in {'appraisal', 'unestablished'}, witness.cause)
                    causes.add(witness.cause.split(':')[0])
        self.assertTrue({C.CLASS_CAUSE.split(':')[0], C.READING_UNKNOWN, C.READING_CONTRADICTED, C.UNLISTED,
                         'appraisal'} <= causes, causes)
