"""Coverage and completeness over the settled facts (docs/gemini-migration/FINAL-V2.md 4.7, 4.8, 4.9, 4.10 and 3.2.6;
step 4b of its 8.1), TEXT-ONLY and SYNTHETIC: every FactSet here is hand-built from engine/types' records (enumeration
members, ids, results and integer spans: the engine's whole input, 4.1). No document is read, no provider is called,
nothing touches the network. The sentences quoted in comments are v1's test inputs or the design's own; the engine never
reads them.

The done-when of 8.1 step 4b, each proved here:
- "v1's coverage rule tests re-expressed": tests/test_interpretation_coverage.py's Bundling, ProceduralAdjuncts,
  Coverage, Record, StentIncluded, AdjunctBesideARemoval and PossiblyCurrent, each test re-expressed over facts as the
  rule it pins (the class and test names keep v1's where the rule is v1's; where FINAL-V2 changes the answer - D41's
  lexical identity and D58/D77's place adjacency gone, D45's unknown duct asked rather than explained, C-2's group in
  separate units un-bundled by D196 - the test says so and pins v2's answer);
- "a contradicted act is never bundled out of its question (D3)": ContradictedNeverBundled - S4's failure class D3 (the
  FRESH-1 'Once' shape: a done biopsy of a possibly-current snare's polyp beside "No biopsies were taken."), its twin
  with the whole established, the contradicted WHOLE, and the controls that do bundle;
- "mypy --strict on the module": BoundaryTests, with 5.7 measure 4 and the import fence.
Also: the sessions from the sessions table (C3, C-4, D62, D70, D87), reportable and doubted (D115, D117, D145, unlisted
acts), reconcile, completeness (3.2.6 rule 1), event_coding@2, the service questions (4.8, D89, D125, D149), and P-MONO
for the verdict and for doubted (9.4) under hypothesis.

Round 2 (the repairs of refute-4b-r1, each class failing without its repair; the step's NOTES): RecordsKeepPossibleActs
(C1), EusActsByCatalogueKind (C2), KindNotEstablished (H1), UnfiledActs (L1, H2; and an act its claimed session
cannot hold, found by round 2's own search), ActsOfAnotherFamilyInDoubt (D142's class in doubt, likewise),
C4ReadsTheEusKindByPossibly (M1), UnsupportedKinds (M2), LesionAdjunct (DQ1, built fail-closed), and MonotoneRecords -
P-MONO at the records base_included and completeness read, over two sessions and the weakenings round 1 did not make
(a contradiction, a doubt on an empty slot).
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from enum import Enum
from pathlib import Path

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import coverage as C
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import Anchor, Fact, FactSet, Id, IdFamily, ItemKind, Span, UnlistedStatement
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'coverage.py'

A, Res, State = ct.Attribute, ct.Result, ct.FactState
Kind, Status, SessionKind, Landmark, Purpose, Cause = (ct.Kind, ct.Status, ct.SessionKind, ct.Landmark, ct.Purpose,
                                                       ct.Cause)
PERFORMED, ATTEMPTED, PLANNED = Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED, Status.PLANNED
ON, EARLIER = ct.DateRelation.ON_DATE_OF_SERVICE, ct.DateRelation.EARLIER_DATE
TEAM, DOC = ct.Performer.DOCUMENTING_TEAM, ct.Owner.DOCUMENTING_CLINICIAN
T, U, FF = C.Truth.T, C.Truth.U, C.Truth.F

E1, E2, E3, E4, E5, E6 = (Id(IdFamily.EVENT, n) for n in range(1, 7))
X1, X2, X3 = (Id(IdFamily.SESSION, n) for n in range(1, 4))
L1, L2 = Id(IdFamily.LESION, 1), Id(IdFamily.LESION, 2)


# --- building settled facts --------------------------------------------------------------------------------------------


def fact(result, value, state, *, options=(), reasons=(), spans=()) -> Fact:
    return Fact(result=result, value=value, state=state, options=tuple(options), reasons=tuple(reasons),
                spans=tuple(spans))


def sup(value, **kw) -> Fact:
    """Supported: established, the claim's value."""
    return fact(Res.SUPPORTED, value, State.SUPPORTED, **kw)


def neg(value, **kw) -> Fact:
    """Negated: established, the claim negated."""
    return fact(Res.NEGATED, value, State.NEGATED, **kw)


def unres(value, state=State.SUPPORTED, **kw) -> Fact:
    """Unresolved: an appraisal that did not establish it; the claimed value kept."""
    return fact(Res.UNRESOLVED, value, state, reasons=(ct.Reason.APPRAISAL_UNCLEAR,), **kw)


def doubted(value, *readings, state=State.SUPPORTED) -> Fact:
    """A doubt (3.3 row 2): unknown, the claimed value and the doubt's readings kept."""
    return fact(Res.UNKNOWN, value, state, options=readings, reasons=(ct.Reason.DOUBT_UNCLEAR,))


def doubted_empty(*readings) -> Fact:
    """An EMPTY slot a doubt names (3.3 row 2): unknown, no value, the readings as options."""
    return fact(Res.UNKNOWN, None, None, options=readings, reasons=(ct.Reason.DOUBT_UNCLEAR,))


def contra(*sides) -> Fact:
    """Pass 1's contradicted fact (3.3 row 1): its sides are its options, its value None."""
    return fact(Res.CONTRADICTED, None, State.CONTRADICTED, options=sides, reasons=(ct.Reason.CONTRADICTED_BY_PASS1,))


SILENT = F.SILENT
NAMES = {
    'kind': A.KIND, 'status': A.STATUS, 'session': A.SESSION, 'date': A.DATE_RELATION, 'performer': A.PERFORMER,
    'entry': A.ENTRY, 'purpose': A.PURPOSE, 'cause': A.CAUSE, 'cause_event': A.CAUSE_EVENT, 'part_of': A.PART_OF,
    'relation': A.PART_RELATION, 'lesion': A.TARGET_LESION, 'duct': A.TARGET_DUCT, 'device': A.TECHNIQUE_DEVICE,
    'breadth': A.SCOPE_BREADTH, 'places': A.TARGET_PLACES, 'excepts': A.SCOPE_EXCEPTS, 'covers': A.SCOPE_COVERS,
    'targets': A.SCOPE_TARGETS, 'segment': A.SCOPE_SEGMENT,
}
MANY = {'places', 'excepts', 'covers', 'targets', 'segment'}


def event(**attributes) -> dict:
    """An event's facts by attribute; a multi-valued attribute is a tuple of member facts; an attribute given as None
    is left out (it reads as SILENT, or as no member)."""
    out = {}
    for name, value in attributes.items():
        if value is None:
            continue
        out[NAMES[name]] = tuple(value) if name in MANY else (value,)
    return out


def act(what, **over) -> dict:
    """An established act of kind ``what``: performed, in X1, on the date of service, by the documenting team, in the
    documenting clinician's entry (``kind=`` among ``over`` replaces its kind fact)."""
    base = dict(kind=sup(what), status=sup(PERFORMED), session=sup(X1), date=sup(ON), performer=sup(TEAM),
                entry=sup(DOC))
    base.update(over)
    return event(**base)


def exam(**over) -> dict:
    """The session's examination (C-1: the examination is the session), done."""
    return act(Kind.EXAMINATION, **over)


def denial(kind, **over) -> dict:
    """An established statement-filed denial of ``kind`` (4.10's broad denial by default): its status performed
    negated, session X1, on the date of service, all of its kind, naming no performer and no device."""
    base = dict(kind=sup(kind), status=neg(PERFORMED), session=sup(X1), date=sup(ON),
                breadth=sup(ct.Breadth.ALL_OF_KIND))
    base.update(over)
    return event(**base)


def session(kind, *, tract=None, part_of=None, reached=(), completion=None) -> dict:
    out = {A.KIND: (kind if isinstance(kind, Fact) else sup(kind),), A.REACHED: tuple(reached),
           A.DEVICE_REACHED: (), A.STATIONS: ()}
    if tract is not None:
        out[A.TRACT] = (tract if isinstance(tract, Fact) else sup(tract),)
    if part_of is not None:
        out[A.PART_OF_SESSION] = (part_of if isinstance(part_of, Fact) else sup(part_of),)
    if completion is not None:
        out[A.COMPLETION] = (completion,)
    return out


def lesion(multiplicity=None, places=(), distinct=(), same=()) -> dict:
    out = {A.PLACES: tuple(sup(place) for place in places), A.DISTINCT_FROM: tuple(sup(other) for other in distinct),
           A.SAME_AS: tuple(sup(other) for other in same)}
    if multiplicity is not None:
        out[A.MULTIPLICITY] = (multiplicity if isinstance(multiplicity, Fact) else sup(multiplicity),)
    return out


def unit(n: int) -> Span:
    return Span(100 * n, 100 * n + 40)


def build(events: dict, *, sessions=None, lesions=None, controls=None, unlisted=(), anchors=None) -> FactSet:
    """A settled FactSet: ``events`` in order; one colonoscopy session X1 unless ``sessions`` says otherwise; each
    event's anchor one unit of its own (``anchors`` maps an event to its unit numbers)."""
    if sessions is None:
        sessions = {X1: session(SessionKind.COLONOSCOPY)}
    units = {subject: (subject.number,) for subject in events}
    units.update(anchors or {})
    return FactSet(encounter={}, people={}, sections={}, sessions=sessions, anatomy={}, lesions=lesions or {},
                   events=events,
                   anchors={subject: Anchor(units=tuple(unit(n) for n in units[subject]), kind_words=None,
                                            status_words=None) for subject in events},
                   unlisted=tuple(unlisted), pair_controls=controls or {}, completeness={})


def controls(first, first_places, second, second_places, rejected=True) -> dict:
    """Pair controls both ways (3.2.3 [R:SC-B]): each object asked about each place of the other, each rejected (True)
    or not."""
    out = {}
    for place in second_places:
        out[(first, A.TARGET_PLACES, place)] = rejected
    for place in first_places:
        out[(second, A.TARGET_PLACES, place)] = rejected
    return out


def lesion_controls(first, first_lesion, second, second_lesion, rejected=True) -> dict:
    return {(first, A.TARGET_LESION, second_lesion): rejected, (second, A.TARGET_LESION, first_lesion): rejected}


def rules(R, part) -> list:
    """(rule, whole, truth) of every bundle of ``part``."""
    return [(bundle.rule, bundle.whole, bundle.truth) for bundle in C.bundles(R, part)]


def first(items):
    return sorted(items, key=lambda item: (item.rank if item.rank is not None else 99,
                                           0 if item.kind is ItemKind.QUESTION else 1))[0]


# The v1 fixtures, as facts: a colonoscopy X1 (E1) to the cecum; its cecal 20 mm polyp L1.
CECAL = {L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.CECUM,))}


def emr(**over) -> dict:
    """v1's emr(): "... the 20 mm flat polyp was resected by EMR en bloc." - an EMR of L1 in the cecum."""
    base = dict(lesion=sup(L1), places=(sup(Landmark.CECUM),))
    base.update(over)
    return act(Kind.EMR, **base)


# --- bundling: v1's Bundling class, re-expressed -----------------------------------------------------------------------


class Bundling(SimpleTestCase):
    """v1's Bundling (7.7, COMMON_BUNDLED; C-2, C-5) over facts: one test per rule, each with its control."""

    def lifted(self, **injection):
        return build({E1: exam(), E2: emr(), E3: act(Kind.INJECTION, **injection)}, lesions=CECAL)

    def test_c5_an_injection_at_the_resections_place_is_its_lift(self):
        """v1: an injection in the cecum beside the cecal EMR is part of it, and 45381 is never READY beside 45390.
        v2: its lift is established by its purpose (lift_for_resection) and its lesion (the EMR's): bundled, an
        explanation naming the EMR (rank 18); its part_of naming the EMR (any relation) bundles it too."""
        for name, injection in (('purpose', dict(purpose=sup(Purpose.LIFT_FOR_RESECTION), lesion=sup(L1))),
                                ('part_of', dict(part_of=sup(E2), relation=sup(ct.PartRelation.LIFT_FOR))),
                                ('step', dict(part_of=sup(E2), relation=sup(ct.PartRelation.STEP_OF)))):
            with self.subTest(arm=name):
                R = self.lifted(**injection)
                found = C.bundled(R, E3)
                self.assertEqual((found.rule, found.whole, found.truth), (C.Rule.LIFT_INJECTION, E2, T))
                self.assertEqual(C.verdict(R, E3).truth, FF)
                item = first(C.bundling('45381', (E3,), R))
                self.assertEqual((item.fact, item.kind, item.rank, item.cause, item.subject),
                                 ('performed_status', ItemKind.EXPLANATION, 18, 'coding_rule:lift_injection', E3))
                self.assertIn(unit(2), item.spans)  # the explanation names the whole: its anchor is quoted
                self.assertEqual(C.bundling('45390', (E2,), R), ())  # the EMR is its own act

    def test_c5_an_injection_with_no_place_joins_the_bundling_identity(self):
        """v1: an injection naming no place and no lesion beside the EMR asks its identity (act_target), never READY.
        v2: its purpose and lesion unstated leave the lift possible (U): asked, never its own act."""
        R = self.lifted()
        self.assertIsNone(C.bundled(R, E3))
        self.assertEqual(rules(R, E3), [(C.Rule.LIFT_INJECTION, E2, U)])
        held = C.bundling('45381', (E3,), R)
        self.assertTrue(held)
        self.assertEqual({item.fact for item in held}, {'act_part', 'act_target'})
        self.assertTrue(all(item.rank == 17 and item.kind is ItemKind.QUESTION for item in held))

    def test_an_injection_at_a_disjoint_place_is_its_own_act(self):
        """v1: an injection in the rectum beside the cecal EMR is its own act (45381 READY). v2: by its established
        place, disjoint from the EMR's, with the pair controls rejected (4.2 [R:SC-B])."""
        events = {E1: exam(), E2: emr(), E3: act(Kind.INJECTION, places=(sup(Landmark.RECTUM),))}
        R = build(events, lesions=CECAL, controls=controls(E3, (Landmark.RECTUM,), E2, (Landmark.CECUM,)))
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth, C.bundling('45381', (E3,), R)), ([], T, ()))
        # SC-B: a place difference counts only with its pair controls rejected - without them it is asked
        R = build(events, lesions=CECAL)
        self.assertEqual(rules(R, E3), [(C.Rule.LIFT_INJECTION, E2, U)])

    def test_a_tattoo_is_never_a_lift_by_place_alone(self):
        """v1: a tattoo in the cecum is never a lift by place alone. v2: the purpose arm is the injection's (a tattoo's
        purpose is no lift), so a marking tattoo is its own act; its part_of naming the EMR still bundles it (v1's
        ONE_ACT arm)."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.TATTOO, purpose=sup(Purpose.MARKING),
                                                 places=(sup(Landmark.CECUM),))}, lesions=CECAL)
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth), ([], T))
        R = build({E1: exam(), E2: emr(), E3: act(Kind.TATTOO, part_of=sup(E2), relation=sup(ct.PartRelation.STEP_OF))},
                  lesions=CECAL)
        self.assertEqual(C.bundled(R, E3).rule, C.Rule.LIFT_INJECTION)

    def test_resection_technique_on_the_same_verified_lesion(self):
        """v1: "The 20 mm flat polyp in the cecum was resected by EMR using a hot snare." - 45385 held BUNDLED, the
        technique of that resection."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.SNARE, lesion=sup(L1), places=(sup(Landmark.CECUM),))},
                  lesions=CECAL)
        found = C.bundled(R, E3)
        self.assertEqual((found.rule, found.whole, found.attribute), (C.Rule.RESECTION_TECHNIQUE, E2, A.TARGET_LESION))
        self.assertEqual(first(C.bundling('45385', (E3,), R)).cause, 'coding_rule:resection_technique')

    def biopsied(self, multiplicity, shared: bool, **lesion_over):
        """v1's biopsied(): a biopsy (E3) and a cold-snare removal (E2) of one lesion L1 in the rectum, in one unit
        (``shared``) or two."""
        lesions = {L1: lesion(multiplicity, places=(Landmark.RECTUM,), **lesion_over)}
        events = {E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY, lesion=sup(L1))}
        return build(events, lesions=lesions, anchors={E2: (2,), E3: (2,) if shared else (3,)})

    def test_biopsy_of_a_single_removed_lesion(self):
        R = self.biopsied(ct.Multiplicity.SINGLE, shared=False)
        self.assertEqual((C.bundled(R, E3).rule, C.verdict(R, E3).truth), (C.Rule.BIOPSY_OF_REMOVED_LESION, FF))

    def test_c2_a_group_lesion_with_a_passage_in_common_is_bundled_whatever_its_multiplicity(self):
        R = self.biopsied(ct.Multiplicity.GROUP, shared=True)
        self.assertEqual(C.bundled(R, E3).rule, C.Rule.BIOPSY_OF_REMOVED_LESION)

    def test_c2_a_group_lesion_in_separate_passages_asks_the_identity(self):
        """v1 asked (act_target). v2: DECISIONS D196 - an ESTABLISHED group un-bundles the biopsy (lesion.multiplicity
        is read on the READY path, its control generated); a multiplicity not established is asked, as v1 asked."""
        R = self.biopsied(ct.Multiplicity.GROUP, shared=False)
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth), ([], T))
        R = self.biopsied(doubted(ct.Multiplicity.GROUP, ct.Multiplicity.SINGLE), shared=False)
        self.assertEqual(rules(R, E3), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])
        held = C.verdict(R, E3).held
        self.assertEqual([(item.fact, item.attribute, item.subject) for item in held],
                         [('act_target', A.MULTIPLICITY, L1)])

    def test_a_biopsy_of_a_distinct_lesion_is_its_own_act(self):
        """v1: "A 4 mm polyp in the rectum was biopsied with cold forceps." beside the sigmoid polyp's snare: both
        READY. v2: distinct_from supported and the lesion pair controls rejected set them apart (4.2); without the
        controls the identity is asked (4.11: an unknown identity never sets two acts apart)."""
        lesions = {L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,)),
                   L2: lesion(ct.Multiplicity.SINGLE, places=(Landmark.RECTUM,), distinct=(L1,))}
        events = {E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY, lesion=sup(L2))}
        R = build(events, lesions=lesions, controls=lesion_controls(E3, L2, E2, L1))
        self.assertEqual((rules(R, E3), C.bundling('45380', (E3,), R)), ([], ()))
        R = build(events, lesions=lesions)
        self.assertEqual(rules(R, E3), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])

    def test_a_prophylactic_clip_is_never_separately_reported_and_a_hemostatic_one_is_bleeding_control(self):
        """v1: "Two clips were placed to close the defect." is bundled (no item); "... for hemostasis of the oozing."
        is a bleeding control, listed not covered beside 45385. v2 reads the purpose: prophylaxis bundles (CLIP);
        hemostasis makes it a bleeding control - with its cause stated as a pre-existing lesion, no adjunct, so it is
        reportable and listed; a purpose left open may be either (U, D157's doubt) and is listed in doubt."""
        snare = act(Kind.SNARE, lesion=sup(L1))
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP, purpose=sup(Purpose.PROPHYLAXIS))})
        self.assertEqual(C.bundled(R, E3).rule, C.Rule.CLIP)
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual(([act.event for act in cov.bundled], cov.unresolved), ([E3], []))
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS),
                                                  cause=sup(Cause.PRE_EXISTING_LESION))})
        self.assertEqual((C.bundles(R, E3), C.reportable(R, E3)), ((), True))
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual([(item.act, item.reason) for item in cov.unresolved],
                         [(Kind.BLEEDING_CONTROL, C.ItemReason.NOT_COVERED)])
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP)})
        self.assertEqual(rules(R, E3), [(C.Rule.CLIP, None, U)])
        self.assertTrue(C.doubted(R, E3))
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual([(item.act, item.reason) for item in cov.unresolved], [(Kind.CLIP, C.ItemReason.IN_DOUBT)])

    def test_cannulation_is_part_of_the_ercp(self):
        """v1: "The common bile duct was cannulated." beside a sphincterotomy: listed bundled, 43262 READY."""
        R = build({E1: exam(), E2: act(Kind.CANNULATION, duct=sup(ct.Duct.BILIARY)),
                   E3: act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY))}, sessions={X1: session(SessionKind.ERCP)})
        self.assertEqual(C.bundled(R, E2).rule, C.Rule.CANNULATION)
        cov = C.reconcile(R, [C.Counted('sel:0', '43262', SessionKind.ERCP, (E3,))], procedure_day=True)
        self.assertEqual([act.event for act in cov.bundled], [E2])
        self.assertEqual(C.bundling('43262', (E3,), R), ())

    def test_a_familys_own_bundled_kind(self):
        """FAMILY_BUNDLED (4.7, D191's BUNDLED_KINDS): the ERCP's contrast injection and the reflux study's pH capsule;
        never the EUS's forceps biopsy, which is read under the upper endoscopy (v1's ``kind != 'biopsy'``)."""
        R = build({E1: exam(), E2: act(Kind.INJECTION, purpose=sup(Purpose.OTHER))},
                  sessions={X1: session(SessionKind.ERCP)})
        self.assertEqual(C.bundled(R, E2).rule, C.Rule.FAMILY_BUNDLED)
        R = build({E1: act(Kind.PH_MONITORING), E2: act(Kind.CAPSULE_STUDY)}, sessions={X1: session(SessionKind.REFLUX)})
        self.assertEqual(C.bundled(R, E2).rule, C.Rule.FAMILY_BUNDLED)
        R = build({E1: exam(), E2: act(Kind.BIOPSY)}, sessions={X1: session(SessionKind.EUS)})
        self.assertEqual(C.bundles(R, E2), ())
        self.assertEqual(C.FAMILY_OWN_BUNDLED[SessionKind.EUS], frozenset())
        self.assertEqual(C.FAMILY_OWN_BUNDLED[SessionKind.ERCP], frozenset({Kind.INJECTION}))
        # an ERCP injection whose purpose may be hemostasis may be a bleeding control: asked, never bundled silently
        R = build({E1: exam(), E2: act(Kind.INJECTION)}, sessions={X1: session(SessionKind.ERCP)})
        self.assertEqual(rules(R, E2), [(C.Rule.FAMILY_BUNDLED, None, U)])


# --- the procedural adjuncts: v1's ProceduralAdjuncts and AdjunctBesideARemoval, re-expressed -------------------------


class ProceduralAdjuncts(SimpleTestCase):
    """D30, D79 (4.7: part_relation adjunct_of, or cause act_of_this_session with cause_event); D41's lexical identity
    and D58/D77's place adjacency are gone (4.7, 4.13: causality is part_of and cause)."""

    def adjunct(self, **ablation):
        """v1's adjunct(): the cecal EMR (E2) and "The margins of the resection defect were treated with snare-tip
        soft coagulation." (E3, an ablation)."""
        return build({E1: exam(), E2: emr(), E3: act(Kind.ABLATION, **ablation)}, lesions=CECAL)

    def test_an_ablation_part_of_the_resection_is_bundled_and_its_code_held(self):
        R = self.adjunct(part_of=sup(E2), relation=sup(ct.PartRelation.ADJUNCT_OF))
        found = C.bundled(R, E3)
        self.assertEqual((found.rule, found.whole), (C.Rule.PROCEDURAL_ADJUNCT, E2))
        item = first(C.bundling('45388', (E3,), R))
        self.assertEqual((item.fact, item.kind, item.rank, item.cause),
                         ('performed_status', ItemKind.EXPLANATION, 18, 'coding_rule:procedural_adjunct'))
        self.assertEqual(C.bundling('45390', (E2,), R), ())

    def test_a_bleeding_control_on_the_removed_lesion_is_bundled_by_its_cause(self):
        """v1 bundled by the removal's lesion; v2 by the cause: "Oozing from the polypectomy site ... was controlled
        with a clip for hemostasis." - cause act_of_this_session, cause_event the snare."""
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)),
                   E3: act(Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.ACT_OF_THIS_SESSION),
                           cause_event=sup(E2))})
        found = C.bundled(R, E3)
        self.assertEqual((found.rule, found.whole, found.attribute), (C.Rule.PROCEDURAL_ADJUNCT, E2, A.CAUSE))

    def test_d79_an_attempted_removal_is_a_whole_too(self):
        R = build({E1: exam(), E2: act(Kind.SNARE, status=sup(ATTEMPTED)),
                   E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS),
                           cause=sup(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2))})
        self.assertEqual(C.bundled(R, E3).whole, E2)

    def test_a_standalone_ablation_stays_its_codes(self):
        """v1's D30 control (transverse colon) READY; and v1's D58 cost (the ascending colon, one step from the
        resection, asked) and D41's no-part_of ablation (asked) are gone in v2: with no part_of and no cause, nothing
        relates the ablation to the resection, whatever its place - its own act."""
        for place in (Landmark.TRANSVERSE_COLON, Landmark.ASCENDING_COLON, Landmark.CECUM):
            with self.subTest(place=place):
                R = self.adjunct(places=(sup(place),))
                self.assertEqual((rules(R, E3), C.bundling('45388', (E3,), R)), ([], ()))

    def test_an_adjunct_of_a_removal_of_another_encounter_is_its_own_act(self):
        """v1: "... removed with a cold snare in 2024." / "The scar was treated with argon plasma coagulation." part_of
        E2: READY. v2: the whole's date relation established as another date - no whole."""
        R = build({E1: exam(), E2: act(Kind.SNARE, date=sup(EARLIER)),
                   E3: act(Kind.ABLATION, part_of=sup(E2), relation=sup(ct.PartRelation.ADJUNCT_OF))})
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth), ([], T))

    def test_a_biopsy_part_of_nothing_is_unaffected(self):
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1), places=(sup(Landmark.SIGMOID_COLON),)),
                   E3: act(Kind.BIOPSY, places=(sup(Landmark.TRANSVERSE_COLON),))},
                  lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,))},
                  controls=controls(E3, (Landmark.TRANSVERSE_COLON,), E2, (Landmark.SIGMOID_COLON,)))
        self.assertEqual(C.bundles(R, E3), ())

    def test_a_cause_naming_no_act_asks_which(self):
        """cause act_of_this_session with no cause_event: the bleeding some act of the session caused - asked
        (act_cause, rank 17), once per possible whole, never READY and never explained."""
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS),
                                                            cause=sup(Cause.ACT_OF_THIS_SESSION))})
        self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E1, U), (C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
        self.assertEqual({(item.fact, item.rank) for item in C.bundling('45382', (E3,), R)}, {('act_cause', 17)})

    def test_d58_a_part_of_naming_the_examination_sets_nothing_apart(self):
        """v1 D58 variant 3: a part_of naming the examination (the session, C-1). v2: it relates the clip to no act -
        no bundle by it; the clip's own cause decides (here none stated: its own act)."""
        R = build({E1: exam(), E2: act(Kind.SNARE),
                   E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS), part_of=sup(E1),
                           relation=sup(ct.PartRelation.ADJUNCT_OF))})
        self.assertEqual(C.bundles(R, E3), ())

    def test_a_part_of_in_doubt_asks_the_part(self):
        """A part_of claimed but not established (pass 2 unclear), or an empty slot a doubt names: asked, act_part."""
        for part in (unres(E2), doubted_empty(E2)):
            with self.subTest(part=part.result):
                R = self.adjunct(part_of=part)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                self.assertEqual({item.fact for item in C.verdict(R, E3).held}, {'act_part'})


# --- D45: v1's StentIncluded, re-expressed -----------------------------------------------------------------------------


class StentIncluded(SimpleTestCase):
    """D45: an ERCP sphincterotomy or dilation beside a stent placement or exchange of its duct is part of that stent
    service; ducts established apart keep it separate; a duct established on neither act never sets them apart (v1
    explained it as part of the stent; v2 asks it: an unknown identity is a question, 4.11)."""

    def ercp(self, part, whole):
        return build({E1: exam(), E2: act(Kind.CANNULATION, duct=sup(ct.Duct.BILIARY)), E3: part, E4: whole},
                     sessions={X1: session(SessionKind.ERCP)})

    def test_a_sphincterotomy_of_the_stented_duct_is_part_of_the_stent(self):
        R = self.ercp(act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)), act(Kind.STENT, duct=sup(ct.Duct.BILIARY)))
        found = C.bundled(R, E3)
        self.assertEqual((found.rule, found.whole, found.attribute), (C.Rule.STENT_INCLUDED, E4, A.TARGET_DUCT))
        self.assertEqual(C.bundling('43274', (E4,), R), ())

    def test_the_stent_code_alone_leaves_no_act_open(self):
        """v1: 43274 alone beside the biliary sphincterotomy and stent: no unresolved item - the sphincterotomy is part
        of the stent, the cannulation part of the ERCP itself."""
        R = self.ercp(act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)), act(Kind.STENT, duct=sup(ct.Duct.BILIARY)))
        cov = C.reconcile(R, [C.Counted('sel:0', '43274', SessionKind.ERCP, (E4,))], procedure_day=True)
        self.assertEqual(cov.unresolved, [])
        self.assertEqual([(act.event, act.rule) for act in cov.bundled],  # the session's members, in order
                         [(E2, C.Rule.CANNULATION), (E3, C.Rule.STENT_INCLUDED)])

    def test_a_sphincterotomy_of_the_other_duct_is_a_separate_service(self):
        R = self.ercp(act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)),
                      act(Kind.STENT, duct=sup(ct.Duct.PANCREATIC)))
        self.assertEqual((C.bundles(R, E3), C.verdict(R, E3).truth), ((), T))

    def test_a_duct_not_established_never_sets_the_two_apart(self):
        for name, duct in (('no target', None), ('unresolved', unres(ct.Duct.PANCREATIC))):
            with self.subTest(sphincterotomy=name):
                R = self.ercp(act(Kind.SPHINCTEROTOMY, duct=duct), act(Kind.STENT, duct=sup(ct.Duct.PANCREATIC)))
                self.assertEqual(rules(R, E3), [(C.Rule.STENT_INCLUDED, E4, U)])
                held = C.bundling('43262', (E3,), R)
                self.assertEqual({(item.fact, item.attribute) for item in held}, {('act_target', A.TARGET_DUCT)})

    def test_a_dilation_of_the_stented_duct_and_a_stent_exchange(self):
        R = self.ercp(act(Kind.DILATION, duct=sup(ct.Duct.BILIARY)), act(Kind.STENT_EXCHANGE, duct=sup(ct.Duct.BILIARY)))
        self.assertEqual(C.bundled(R, E3).rule, C.Rule.STENT_INCLUDED)

    def test_no_stent_act_of_this_ercp_leaves_the_sphincterotomy_alone(self):
        for name, other in (('a stone extraction', act(Kind.STONE_EXTRACTION, duct=sup(ct.Duct.BILIARY))),
                            ('a planned stent', act(Kind.STENT, status=sup(PLANNED), duct=sup(ct.Duct.BILIARY)))):
            with self.subTest(beside=name):
                R = self.ercp(act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)), other)
                self.assertEqual(C.bundles(R, E3), ())


class DrainageStep(SimpleTestCase):
    """v1's drainage_step (D171 (1), D177 (3)) as 4.7's bundling rule (G3: part_relation access_for or step_of to the
    drainage, or the same lesion; the drainage performed or begun, read by possibly)."""

    def eus(self, fna, drainage, lesions=None, ctl=None):
        return build({E1: exam(), E2: drainage, E3: fna}, sessions={X1: session(SessionKind.EUS)}, lesions=lesions,
                     controls=ctl)

    def test_a_step_by_part_of_or_by_lesion(self):
        for name, fna in (('part_of', act(Kind.FNA, part_of=sup(E2), relation=sup(ct.PartRelation.ACCESS_FOR))),
                          ('lesion', act(Kind.FNA, lesion=sup(L1)))):
            with self.subTest(arm=name):
                R = self.eus(fna, act(Kind.DRAINAGE, lesion=sup(L1)), lesions={L1: lesion(ct.Multiplicity.SINGLE)})
                found = C.drainage_step(R, E3)
                self.assertEqual((found.rule, found.whole, found.truth), (C.Rule.DRAINAGE_STEP, E2, T))

    def test_d177_a_drainage_in_doubt_is_a_doubt_never_an_absence(self):
        R = self.eus(act(Kind.FNA, lesion=sup(L1)), act(Kind.DRAINAGE, lesion=sup(L1), status=doubted(PERFORMED)),
                     lesions={L1: lesion(ct.Multiplicity.SINGLE)})
        found = C.drainage_step(R, E3)
        self.assertEqual((found.whole, found.truth), (E2, U))
        self.assertEqual(first(C.verdict(R, E3).held).rank, 2)  # the drainage's doubted status: performed_status

    def test_an_fna_of_another_lesion_is_no_step(self):
        lesions = {L1: lesion(ct.Multiplicity.SINGLE), L2: lesion(ct.Multiplicity.SINGLE, distinct=(L1,))}
        R = self.eus(act(Kind.FNA, lesion=sup(L2)), act(Kind.DRAINAGE, lesion=sup(L1)), lesions=lesions,
                     ctl=lesion_controls(E3, L2, E2, L1))
        self.assertIsNone(C.drainage_step(R, E3))


# --- D3: a contradicted act is never bundled out of its question ------------------------------------------------------


def once(*, snare_date=None, denial_=True, whole_denial=False):
    """S4's failure class D3 (FRESH-1 'Once'), as facts: the colonoscopy X1 (E1); "Once, a 22 mm polyp was found ... It
    was removed piecemeal" (E2, a snare of L1 whose date relation a doubt names: on_date_of_service or earlier_date);
    "During this procedure, cold forceps biopsies of the polyp were taken." (E3, a biopsy of L1, done today); "No
    biopsies were taken." (E4, a biopsy denial, all of its kind in X1, today) unless ``denial_`` is False; with
    ``whole_denial``, "No polyp was removed." (E5, a removal denial) instead, contradicting the snare."""
    events = {E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1), date=snare_date or doubted(ON, ON, EARLIER)),
              E3: act(Kind.BIOPSY, lesion=sup(L1))}
    if denial_:
        events[E4] = denial(Kind.BIOPSY)
    if whole_denial:
        events[E5] = denial(Kind.REMOVAL)
    return build(events, lesions={L1: lesion(ct.Multiplicity.SINGLE)})


class ContradictedNeverBundled(SimpleTestCase):
    """The done-when "a contradicted act is never bundled out of its question (D3)": FINAL-V2 4.8 rank 1 ("Ranked first
    so a contradicted act is never bundled out of its question"), Appendix C (T5, T6, D3: "a contradicted act is never
    bundled (rank 1)"), S4's D3 ("Contradictions are reported as contradicted states and are never resolved by
    bundling"; the currency7 build bundled the biopsy into the snare: no conflict:biopsy question, nothing listed)."""

    def assert_never_bundled(self, R):
        found = C.verdict(R, E3)
        self.assertTrue(found.contradicted)
        self.assertNotEqual(found.truth, FF)
        self.assertIsNone(C.bundled(R, E3))
        self.assertFalse([item for item in found.held if item.rank == 18 or item.kind is ItemKind.EXPLANATION])
        item = first(found.held)
        self.assertEqual((item.fact, item.rank, item.subject, item.cause),
                         ('conflict:biopsy', 1, E3, 'relation:contradiction'))
        self.assertEqual(item.spans, (unit(3), unit(4)))  # both statements quoted
        held = C.bundling('45380', (E3,), R)  # even were a caller to pass it as supporting
        self.assertEqual(first(held).fact, 'conflict:biopsy')
        self.assertFalse([item for item in held if item.rank == 18])
        return found

    def test_the_once_shape_asks_the_conflict(self):
        R = once()
        found = self.assert_never_bundled(R)
        self.assertEqual(rules(R, E3), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])  # the whole only possibly today
        self.assertIn(('act_part', A.DATE_RELATION, E2), {(item.fact, item.attribute, item.subject)
                                                          for item in found.held})
        # listed in doubt, never as bundled; its service question is the conflict, quoting both statements
        cov = C.reconcile(R, [], procedure_day=True)
        self.assertNotIn(E3, [act.event for act in cov.bundled])
        self.assertIn((C.ItemReason.IN_DOUBT, (E3,)), [(item.reason, item.events) for item in cov.unresolved])
        questions = C.in_doubt_questions(R, cov)
        biopsy = [service for service in questions if service.event == E3]
        self.assertEqual([(service.item.fact, service.item.spans) for service in biopsy],
                         [('conflict:biopsy', (unit(3), unit(4)))])
        # read by 45380's own item, it is covered, never listed bundled either
        cov = C.reconcile(R, [C.Counted('sel:0', '45380', SessionKind.COLONOSCOPY, (), (E3,))], procedure_day=True)
        self.assertNotIn(E3, [act.event for act in cov.bundled])

    def test_the_whole_established_still_never_bundles_it(self):
        """The snare's date relation supported today (the T bundle v1's currency7 build made): the biopsy is still
        never bundled - its conflict asked first, no explanation."""
        R = once(snare_date=sup(ON))
        self.assertEqual(rules(R, E3), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)])
        self.assert_never_bundled(R)

    def test_the_controls_bundle(self):
        """Without the denial the same biopsy IS bundled when the whole is established, and asked when it is only
        possibly today: the guard is the contradiction's, nothing else."""
        R = once(snare_date=sup(ON), denial_=False)
        self.assertEqual((C.verdict(R, E3).truth, C.bundled(R, E3).rule), (FF, C.Rule.BIOPSY_OF_REMOVED_LESION))
        self.assertEqual(first(C.bundling('45380', (E3,), R)).rank, 18)
        R = once(denial_=False)
        self.assertEqual((C.verdict(R, E3).truth, C.verdict(R, E3).contradicted), (U, False))

    def test_a_contradicted_fact_of_the_act_is_its_conflict_too(self):
        """A conflict doubt or K8 (3.3 row 1) on the biopsy's own status: contradicted, rank 1, never bundled."""
        events = {E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)),
                  E3: act(Kind.BIOPSY, lesion=sup(L1), status=contra(PERFORMED, PLANNED))}
        R = build(events, lesions={L1: lesion(ct.Multiplicity.SINGLE)})
        found = C.verdict(R, E3)
        self.assertEqual((found.contradicted, found.truth, first(found.held).fact), (True, U, 'conflict:biopsy'))
        self.assertIsNone(C.bundled(R, E3))

    def test_a_contradicted_whole_is_never_the_reason_its_part_is_explained_away(self):
        """D3's principle on the whole's side: "No polyp was removed." contradicts the snare (4.10: a CONTRADICTION,
        conflict:snare); the biopsy of the snare's polyp is not explained as part of a removal the document also
        denies - its bundling is asked, the snare's conflict first."""
        R = once(snare_date=sup(ON), denial_=False, whole_denial=True)
        found = C.verdict(R, E3)
        self.assertEqual((found.truth, found.contradicted), (U, False))
        item = first(found.held)
        self.assertEqual((item.fact, item.rank, item.subject), ('conflict:snare', 1, E2))
        self.assertIsNone(C.bundled(R, E3))


# --- sessions (4.7: from the sessions table) ---------------------------------------------------------------------------


class Sessions(SimpleTestCase):
    def test_one_session_and_its_examination(self):
        R = build({E1: exam(), E2: act(Kind.SNARE)})
        found = C.sessions(R)[X1]
        self.assertEqual((found.kind, found.event, found.examinations, found.possible, found.unresolved, found.done,
                          found.incomplete, found.events), (SessionKind.COLONOSCOPY, E1, (E1,), (), False, True, False,
                                                            (E1, E2)))

    def test_two_examinations_of_one_family_leave_its_session_unresolved(self):
        """v1: "The colonoscope was reinserted to the splenic flexure." - two done examinations."""
        R = build({E1: exam(), E3: exam()})
        found = C.sessions(R)[X1]
        self.assertEqual((found.event, found.unresolved, found.examinations), (None, True, (E1, E3)))

    def test_d62_a_possible_examination_leaves_todays_session_unresolved(self):
        """v1's PossiblyCurrent: "These were the findings at her index colonoscopy: ..." - an examination whose date
        relation is in doubt is a POSSIBLE examination (D87: listed apart from the done one), never the session."""
        for date in (doubted(ON, ON, EARLIER), unres(ON)):
            with self.subTest(date=date.result):
                R = build({E1: exam(), E3: exam(date=date)})
                found = C.sessions(R)[X1]
                self.assertEqual((found.event, found.unresolved, found.examinations, found.possible),
                                 (None, True, (E1,), (E3,)))
        R = build({E1: exam(), E3: exam(date=sup(EARLIER))})  # established another date: neither
        self.assertEqual((C.sessions(R)[X1].event, C.sessions(R)[X1].possible), (E1, ()))

    def test_incomplete(self):
        R = build({E1: exam(status=sup(ATTEMPTED))})
        self.assertTrue(C.sessions(R)[X1].incomplete)

    def test_c3_part_of_session(self):
        R = build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                  sessions={X1: session(SessionKind.FLEX_SIG, part_of=X2), X2: session(SessionKind.COLONOSCOPY)})
        self.assertEqual((C.sessions(R)[X1].part_of, C.sessions(R)[X2].part_of), (X2, None))
        R = build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                  sessions={X1: session(SessionKind.FLEX_SIG, part_of=unres(X2)), X2: session(SessionKind.COLONOSCOPY)})
        self.assertEqual((C.sessions(R)[X1].part_of, C.sessions(R)[X1].possibly_part_of), (None, X2))

    def egd_and_eus(self, tract, eus_exam=None):
        return build({E1: exam(session=sup(X1)), E2: eus_exam or exam(session=sup(X2))},
                     sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=tract)})

    def test_c4_an_egd_within_an_upper_eus_is_included(self):
        """v1: "A standard gastroscope was advanced to the second portion ..." then "A linear echoendoscope ..." - C-4,
        structurally over the supported session kinds and the EUS's supported tract (4.7's base_within row)."""
        sessions_ = C.sessions(self.egd_and_eus(ct.Tract.UPPER))
        self.assertEqual((sessions_[X1].part_of, sessions_[X1].possibly_part_of), (X2, None))
        cov = C.reconcile(self.egd_and_eus(ct.Tract.UPPER),
                          [C.Counted('sel:0', '43242', SessionKind.EUS, (E2,))], procedure_day=True)
        self.assertEqual(C.included_by(sessions_, cov.covered), {X1: ['43242']})
        self.assertNotIn(X1, [item.session for item in cov.unresolved])

    def test_c4_a_lower_eus_and_d70_an_eus_possibly_upper(self):
        sessions_ = C.sessions(self.egd_and_eus(ct.Tract.LOWER))
        self.assertEqual((sessions_[X1].part_of, sessions_[X1].possibly_part_of), (None, None))
        for tract in (unres(ct.Tract.UPPER), ct.Tract.PANCREATOBILIARY):
            with self.subTest(tract=tract):
                sessions_ = C.sessions(self.egd_and_eus(tract))
                self.assertEqual((sessions_[X1].part_of, sessions_[X1].possibly_part_of), (None, X2))
        # D70: an EUS examination only POSSIBLY of this encounter makes the EGD possibly part of it, never part of it
        sessions_ = C.sessions(self.egd_and_eus(ct.Tract.UPPER, exam(session=sup(X2), date=doubted(ON, ON, EARLIER))))
        self.assertEqual((sessions_[X1].part_of, sessions_[X1].possibly_part_of), (None, X2))

    def test_no_region_move(self):
        """5.4: coding_family's region moves retire - an act Gemini places in the enteroscopy session stays there,
        whatever its place (an EGD place beside a done EGD)."""
        R = build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2)),
                   E3: act(Kind.ABLATION, session=sup(X2), places=(sup(Landmark.GASTRIC_ANTRUM),))},
                  sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.ENTEROSCOPY)})
        sessions_ = C.sessions(R)
        self.assertEqual((sessions_[X1].events, sessions_[X2].events), ((E1,), (E2, E3)))


# --- reportable and doubted ------------------------------------------------------------------------------------------


class ReportableAndDoubted(SimpleTestCase):
    def test_reportable(self):
        R = build({E1: exam(), E2: act(Kind.SNARE)})
        self.assertEqual((C.reportable(R, E2), C.doubted(R, E2), C.reportable(R, E1)), (True, False, False))

    def test_a_doubted_status_and_one_pass_2_did_not_establish(self):
        """v1: "It is unclear whether biopsies were taken from the transverse colon." (uncertain). 4.7 [R:HO-1]: a
        doubted status, and one pass 2 did not establish, are possibly positive and in doubt."""
        for status in (doubted(PERFORMED), unres(PERFORMED), contra(PERFORMED, PLANNED)):
            with self.subTest(status=status.result):
                R = build({E1: exam(), E3: act(Kind.BIOPSY, status=status)})
                self.assertEqual((C.reportable(R, E3), C.doubted(R, E3)), (False, True))

    def test_each_required_fact_not_supported_is_a_doubt(self):
        for name, over in (('kind', dict(kind=unres(Kind.BIOPSY))), ('date', dict(date=doubted(ON, ON, EARLIER))),
                           ('performer', dict(performer=None)), ('entry', dict(entry=unres(DOC))),
                           ('session', dict(session=unres(X1)))):
            with self.subTest(fact=name):
                R = build({E1: exam(), E3: act(Kind.BIOPSY, **over)})
                self.assertTrue(C.doubted(R, E3))

    def test_a_relation_or_an_unlisted_statement_is_a_doubt(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: denial(Kind.SNARE, status=unres(PERFORMED, State.NEGATED))})
        self.assertTrue(C.doubted(R, E2))  # a possible statement pairs with it (4.5: a DOUBT or UNRESOLVED relation)
        entry = UnlistedStatement(units=(unit(9),), what=ct.UnlistedWhat.DENIAL, kind=Kind.SNARE, session=X1)
        R = build({E1: exam(), E2: act(Kind.SNARE)}, unlisted=(entry,))
        self.assertTrue(C.doubted(R, E2))  # 3.2.6 rule 4

    def test_another_date_or_performer_is_no_doubt(self):
        for over in (dict(date=sup(EARLIER)), dict(performer=sup(ct.Performer.OTHER_CLINICIAN))):
            with self.subTest(over=over):
                R = build({E1: exam(), E3: act(Kind.BIOPSY, status=doubted(PERFORMED), **over)})
                self.assertFalse(C.doubted(R, E3))

    def test_d117_a_removal_whose_method_is_not_stated(self):
        """v1: "A polypectomy of the gastric body polyp was performed." (the removal umbrella): doubted."""
        R = build({E1: exam(), E2: act(Kind.REMOVAL)}, sessions={X1: session(SessionKind.EGD)})
        self.assertEqual((C.reportable(R, E2), C.doubted(R, E2)), (False, True))
        R = build({E1: exam(), E2: act(Kind.REMOVAL)}, sessions={X1: session(SessionKind.ERCP)})
        self.assertFalse(C.doubted(R, E2))  # no removal method in the ERCP's acts

    def test_d115_a_bleeding_control_in_doubt_from_purpose(self):
        """D115 over facts (4.7: "D115's word-derived possible control (now from purpose and cause)"): two clips whose
        purpose is not established may be a bleeding control - doubted; prophylaxis bundles them."""
        R = build({E1: exam(), E2: act(Kind.CLIP, purpose=unres(Purpose.HEMOSTASIS))})
        self.assertTrue(C.doubted(R, E2))
        R = build({E1: exam(), E2: act(Kind.CLIP, purpose=sup(Purpose.PROPHYLAXIS))})
        self.assertFalse(C.doubted(R, E2))

    def test_d145_an_eus_act_of_an_unlisted_kind(self):
        """D137, D145: a lumen-apposing stent (kind stent) in the EUS session is recorded as reportable (done and
        performed) or doubted (begun or in doubt), never both (D156 (3))."""
        R = build({E1: exam(), E2: act(Kind.STENT)}, sessions={X1: session(SessionKind.EUS)})
        self.assertEqual(C.eus_unlisted(R, E2), (True, False))
        R = build({E1: exam(), E2: act(Kind.STENT, status=sup(ATTEMPTED))}, sessions={X1: session(SessionKind.EUS)})
        self.assertEqual(C.eus_unlisted(R, E2), (False, True))
        R = build({E1: exam(), E2: act(Kind.STENT, status=doubted(PERFORMED))}, sessions={X1: session(SessionKind.EUS)})
        self.assertEqual(C.eus_unlisted(R, E2), (False, True))
        coding = C.event_coding(R, C.sessions(R), {})
        self.assertEqual([entry['event'] for entry in coding['sessions']['X1']['doubted']], ['E2'])

    def test_an_unlisted_act_is_a_synthetic_doubted_act_of_its_session(self):
        """3.2.6 rule 3: "an unlisted act with a session card is a synthetic doubted act of that session: it holds the
        session's base code (base_included, as a doubt) and is listed in_doubt"."""
        entry = UnlistedStatement(units=(unit(9),), what=ct.UnlistedWhat.ACT, kind=Kind.BIOPSY, session=X1)
        R = build({E1: exam(), E2: act(Kind.SNARE)}, unlisted=(entry,))
        coding = C.event_coding(R, C.sessions(R), {})
        self.assertEqual(coding['sessions']['X1']['doubted'],
                         [{'event': None, 'kind': 'biopsy', 'lesion': None, 'unlisted': 0}])
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual([(item.reason, item.unlisted, item.evidence) for item in cov.unresolved],
                         [(C.ItemReason.IN_DOUBT, (0,), (unit(9),))])
        self.assertEqual([ref.unlisted for _, ref in cov.in_doubt], [0])
        questions = C.in_doubt_questions(R, cov)
        self.assertEqual([(service.unlisted, service.item.fact, service.item.cause, service.item.rank)
                          for service in questions], [(0, 'performed_status', 'unlisted', 2)])
        # without a session it is no synthetic act (rule 3); completeness still counts it (rule 1)
        entry = UnlistedStatement(units=(unit(9),), what=ct.UnlistedWhat.ACT, kind=Kind.BIOPSY, session=None)
        R = build({E1: exam(), E2: act(Kind.SNARE)}, unlisted=(entry,))
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual((cov.unresolved, cov.unlisted), ([], 1))


# --- coverage: v1's Coverage class, re-expressed -----------------------------------------------------------------------


def snare_only():
    return build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1))},
                 lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,))})


COUNTED_45385 = [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))]


def label(session_):
    return f'service {session_.id}'


class Coverage(SimpleTestCase):
    def test_a_reportable_act_no_code_covers_is_not_covered_and_marked_for_the_second_review(self):
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)),
                   E3: act(Kind.BIOPSY, places=(sup(Landmark.TRANSVERSE_COLON),))},
                  lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,))},
                  controls=controls(E3, (Landmark.TRANSVERSE_COLON,), E2, (Landmark.SIGMOID_COLON,)))
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        record = C.unresolved_record(cov.unresolved)
        self.assertEqual([(item['act'], item['reason'], item['second_review'], item['events']) for item in record],
                         [('biopsy', 'not_covered', True, ['E3'])])
        self.assertEqual(record[0]['evidence'], [[300, 340]])
        self.assertEqual(C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                                        label=label)['state'], 'incomplete')

    def test_a_session_with_no_code_is_no_proposal(self):
        R = build({E0: exam(session=sup(X2)), E1: exam(), E2: act(Kind.SNARE)},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)})
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual([(item.session, item.reason, item.detail) for item in cov.unresolved],
                         [(X2, C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED)])
        self.assertTrue(C.unresolved_record(cov.unresolved)[0]['second_review'])

    def test_an_office_visit_beside_a_same_day_procedure_is_not_listed_not_unresolved(self):
        R = build({E0: act(Kind.EM_VISIT, session=sup(X2)), E1: exam(), E2: act(Kind.SNARE)},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.OFFICE_EM)})
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual((cov.unresolved, [session_.id for session_ in cov.not_listed]), ([], [X2]))
        complete = C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0, label=label)
        self.assertIn('not listed as unresolved: service X2', complete['statement'])

    def test_an_unsupported_act_is_listed_as_such(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.ESD)})
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual([(item.act, item.reason, item.detail) for item in cov.unresolved],
                         [(Kind.ESD, C.ItemReason.UNSUPPORTED, C.Detail.NO_PROFILE)])

    def test_an_act_in_doubt_no_code_depends_on_is_in_doubt_with_a_service_question(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.BIOPSY, status=doubted(PERFORMED))})
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        record = C.unresolved_record(cov.unresolved)
        self.assertEqual([(item['act'], item['reason'], item['second_review']) for item in record],
                         [('biopsy', 'in_doubt', False)])
        questions = C.in_doubt_questions(R, cov)
        self.assertEqual([(service.event, service.item.fact, service.item.rank) for service in questions],
                         [(E3, 'performed_status', 2)])
        self.assertEqual(C.completeness(cov, C.sessions(R), open_questions=len(questions), provider_ok=True,
                                        conflicts=0, label=label)['state'], 'incomplete')

    def test_a_held_codes_candidate_is_covered(self):
        R = build({E1: exam(), E2: act(Kind.SNARE, performer=None)})
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (), (E2,))], procedure_day=True)
        self.assertEqual(cov.unresolved, [])

    def test_complete_pending_review(self):
        R = snare_only()
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        complete = C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0, label=label)
        self.assertEqual((complete['state'], cov.covered), ('complete_pending_review', {X1: ['45385']}))

    def test_an_act_no_code_of_its_service_accounts_for(self):
        """v1 compl-1: an act of its family's catalogue acts that no code of the family accounts for (today the EGD's
        decompression alone) is listed unsupported whatever its outcome - attempted or in doubt, or done."""
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E2,))]
        for status, detail in ((sup(ATTEMPTED), C.Detail.ATTEMPTED_OR_IN_DOUBT),
                               (doubted(PERFORMED), C.Detail.ATTEMPTED_OR_IN_DOUBT),
                               (sup(PERFORMED), C.Detail.NO_CODE_OF_SERVICE)):
            with self.subTest(status=status.result, value=status.value):
                R = build({E1: exam(), E2: act(Kind.BIOPSY), E3: act(Kind.DECOMPRESSION, status=status)},
                          sessions={X1: session(SessionKind.EGD)})
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual([(item.act, item.reason, item.detail) for item in cov.unresolved][:1],
                                 [(Kind.DECOMPRESSION, C.ItemReason.UNSUPPORTED, detail)])

    def test_read_under(self):
        """catalogue.READ_UNDER: an EUS forceps biopsy at an upper site is read under the EGD when a done EGD session
        has a done biopsy; else listed unsupported with why."""
        events = {E1: exam(session=sup(X1)), E2: act(Kind.BIOPSY, session=sup(X1)), E3: exam(session=sup(X2)),
                  E4: act(Kind.BIOPSY, session=sup(X2), places=(sup(Landmark.STOMACH),)),
                  E5: act(Kind.FNA, session=sup(X2))}
        sessions_ = {X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.LOWER)}
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E2,)), C.Counted('sel:1', '43232', SessionKind.EUS,
                                                                                   (E5,))]
        cov = C.reconcile(build(events, sessions=sessions_), counted, procedure_day=True)
        self.assertEqual([(act.event, act.rule) for act in cov.bundled], [(E4, None)])
        events[E4] = act(Kind.BIOPSY, session=sup(X2), places=(sup(Landmark.RECTUM),))
        cov = C.reconcile(build(events, sessions=sessions_), counted, procedure_day=True)
        self.assertEqual([(item.events, item.detail) for item in cov.unresolved],
                         [((E4,), C.Detail.READ_UNDER_NOT_PLACED)])

    def test_unestablished(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: exam(session=sup(X2), status=doubted(PERFORMED))},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)})
        self.assertEqual(C.reconcile(R, COUNTED_45385, procedure_day=True).unestablished, 1)


E0 = Id(IdFamily.EVENT, 0)


# --- the service questions (4.8; D89, D125, D149) ---------------------------------------------------------------------


class ServiceQuestions(SimpleTestCase):
    def two_in_doubt(self):
        """A snare (E2, in the sigmoid colon) and two acts in doubt, each with one witness (its doubted status): a
        biopsy set apart from the snare by its place (E3) and an ablation (E4)."""
        return build({E1: exam(), E2: act(Kind.SNARE, places=(sup(Landmark.SIGMOID_COLON),)),
                      E3: act(Kind.BIOPSY, status=doubted(PERFORMED), places=(sup(Landmark.TRANSVERSE_COLON),)),
                      E4: act(Kind.ABLATION, status=doubted(PERFORMED))},
                     controls=controls(E3, (Landmark.TRANSVERSE_COLON,), E2, (Landmark.SIGMOID_COLON,)))

    def test_one_per_session_and_fact(self):
        R = self.two_in_doubt()
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        questions = C.in_doubt_questions(R, cov)
        self.assertEqual([(service.session, service.item.fact, service.event) for service in questions],
                         [(X1, 'performed_status', E3)])

    def test_d149_an_act_a_codes_item_names_yields_its_slot(self):
        R = self.two_in_doubt()
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        questions = C.in_doubt_questions(R, cov, holding=(E3,))
        self.assertEqual([service.event for service in questions], [E4])

    def test_d89_a_codes_own_item_is_never_asked_twice(self):
        R = self.two_in_doubt()
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        questions = C.in_doubt_questions(R, cov, asked=((E3, 'performed_status'),))
        self.assertEqual([service.event for service in questions], [E4])
        questions = C.in_doubt_questions(R, cov, asked=((E3, 'performed_status'), (E4, 'performed_status')))
        self.assertEqual(questions, [])

    def test_d125_the_extent_question(self):
        R = snare_only()
        found = C.service_extent_questions(R, C.sessions(R))
        self.assertEqual([(service.session, service.item.fact, service.item.rank, service.item.subject)
                          for service in found], [(X1, 'extent', 14, X1)])
        self.assertEqual(C.service_extent_questions(R, C.sessions(R), asked=((X1, 'extent'),)), [])
        R = build({E1: exam(), E2: act(Kind.SNARE)},
                  sessions={X1: session(SessionKind.COLONOSCOPY, reached=(sup(ct.Extent.CECUM),))})
        self.assertEqual(C.service_extent_questions(R, C.sessions(R)), [])
        R = build({E1: exam(), E2: act(Kind.SNARE)},  # D87: a reach not established is a doubt: asked
                  sessions={X1: session(SessionKind.COLONOSCOPY, reached=(unres(ct.Extent.CECUM),))})
        self.assertEqual(C.service_extent_questions(R, C.sessions(R))[0].item.cause, 'appraisal:unclear')


# --- the records: v1's Record class, re-expressed ----------------------------------------------------------------------


class Record(SimpleTestCase):
    def test_the_event_coding_record(self):
        R = snare_only()
        coding = C.event_coding(R, C.sessions(R), {'sel:0': (X1, (E1,)), 'sel:1': (X1, (E2,))})
        self.assertEqual(coding['version'], 'cpt-studio-events@2')
        found = coding['sessions']['X1']
        self.assertEqual((found['event'], found['kind'], found['part_of'], found['possibly_part_of']),
                         ('E1', 'colonoscopy', None, None))
        self.assertEqual(found['reportable'], [{'event': 'E2', 'kind': 'snare', 'lesion': 'L1', 'unlisted': None}])
        self.assertEqual(coding['codes'], {'sel:0': {'session': 'X1', 'events': ['E1'], 'lesions': []},
                                           'sel:1': {'session': 'X1', 'events': ['E2'], 'lesions': ['L1']}})
        self.assertEqual(coding['lesions']['L1'], {'places': ['sigmoid_colon'], 'multiplicity': 'single',
                                                   'distinct_from': [], 'same_as': []})

    def test_the_second_review_mark_stops_at_the_checked_count(self):
        from studio.interpretation import coverage as v1_coverage
        self.assertEqual(C.SECOND_REVIEW_CHECKED, v1_coverage.SECOND_REVIEW_CHECKED)
        items = [C.Item(X1, SessionKind.COLONOSCOPY, Kind.BIOPSY, C.ItemReason.NOT_COVERED, C.Detail.NOT_COVERED, (),
                        ()) for _ in range(66)]
        marks = [item['second_review'] for item in C.unresolved_record(items)]
        self.assertEqual((marks.count(True), marks[63], marks[64]), (64, True, False))

    def test_completeness_is_worded_as_v1_words_it(self):
        """v1's coverage.completeness pinned: the same record for equivalent inputs (its sentences), and 3.2.6 rule 1's
        reason appended last."""
        from studio.interpretation import coverage as v1_coverage
        office = C.Session(id=X2, kind=SessionKind.OFFICE_EM, done=True)
        procedure = C.Session(id=X1, kind=SessionKind.COLONOSCOPY, done=True)
        item = C.Item(X1, SessionKind.COLONOSCOPY, Kind.BIOPSY, C.ItemReason.NOT_COVERED, C.Detail.NOT_COVERED, (), ())
        cov = C.Coverage(unresolved=[item, item], not_listed=[office], unestablished=1)
        v1_office = v1_coverage.Session(id='gi.office_em', family='gi.office_em', kind='office_em',
                                        label='office / outpatient visit', done=True)
        v1_procedure = v1_coverage.Session(id='gi.colonoscopy', family='gi.colonoscopy', kind='colonoscopy',
                                           label='colonoscopy', done=True)
        v1_cov = v1_coverage.Coverage(unresolved=[{'label': 'x'}, {'label': 'y'}], not_listed=[v1_office],
                                      unestablished=1)
        for flags in ((3, False, 2, 0), (0, True, 0, 0), (1, True, 1, 4)):
            open_questions, provider_ok, conflicts, unverified = flags
            with self.subTest(flags=flags):
                mine = C.completeness(cov, {X1: procedure, X2: office}, open_questions=open_questions,
                                      provider_ok=provider_ok, conflicts=conflicts, unverified=unverified,
                                      label=lambda _: v1_coverage.uncounted_label(v1_office))
                legacy = v1_coverage.completeness(v1_cov, {'a': v1_procedure, 'b': v1_office},
                                                  open_questions=open_questions, provider_ok=provider_ok,
                                                  conflicts=conflicts, unverified=unverified)
                self.assertEqual(mine, legacy)
        clean = C.completeness(C.Coverage(), {X1: procedure}, open_questions=0, provider_ok=True, conflicts=0,
                               label=label)
        self.assertEqual(clean, v1_coverage.completeness(v1_coverage.Coverage(), {'a': v1_procedure},
                                                         open_questions=0, provider_ok=True, conflicts=0))
        unlisted = C.completeness(C.Coverage(unlisted=2), {X1: procedure}, open_questions=0, provider_ok=True,
                                  conflicts=0, label=label)
        self.assertEqual((unlisted['state'], unlisted['reasons']),
                         ('incomplete', ['2 statements of the document that the reading did not list']))

    def test_the_bundled_record(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.CLIP, purpose=sup(Purpose.PROPHYLAXIS))})
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual(C.bundled_record(cov.bundled),
                         [{'service': 'X1', 'event': 'E3', 'act': 'clip', 'rule': 'clip', 'whole': None}])

    def test_the_rule_values_are_v1s_reasons(self):
        """The bundling rules' values are v1's reasons (COMMON_BUNDLED's keys, coverage's adjunct and stent reasons,
        drainage_step), so a stored or worded rule names what v1 named; FAMILY_BUNDLED is a family's own."""
        from studio.gi import catalogue as gi_catalogue
        common = {key for key, _ in gi_catalogue.COMMON_BUNDLED}
        self.assertLessEqual(common, {rule.value for rule in C.Rule})
        self.assertEqual({rule.value for rule in C.Rule} - common,
                         {'family_bundled', 'stent_included', 'procedural_adjunct', 'drainage_step'})


# --- the code-level bundling (4.4's decide) ----------------------------------------------------------------------------


class CodeLevel(SimpleTestCase):
    def test_every_code_has_at_most_one_requirement_group(self):
        """bundling() is per group because no catalogue code has two (catalogue.requirements)."""
        for code in catalogue.CODES:
            with self.subTest(code=code):
                self.assertLessEqual(len(catalogue.requirements(catalogue.code_link(str(code)))), 1)

    def test_an_own_act_supports_the_code(self):
        """v1: a code proceeds on its own acts; its bundled acts are dropped from its support (no hold)."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.SNARE, lesion=sup(L1)),
                   E4: act(Kind.SNARE, lesion=sup(L2))},
                  lesions={**CECAL, L2: lesion(ct.Multiplicity.SINGLE, distinct=(L1,))},
                  controls=lesion_controls(E4, L2, E2, L1))
        self.assertEqual((C.verdict(R, E3).truth, C.verdict(R, E4).truth), (FF, T))
        self.assertEqual(C.bundling('45385', (E3, E4), R), ())
        self.assertTrue(C.bundling('45385', (E3,), R))
        self.assertEqual(C.bundling('45385', (), R), ())

    def test_every_candidates_witnesses(self):
        """HO-8: every supporting act's witnesses, the questions (rank 17) before the explanation (rank 18)."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.SNARE, lesion=sup(L1)), E4: act(Kind.SNARE)}, lesions=CECAL)
        held = C.bundling('45385', (E3, E4), R)
        self.assertEqual(sorted({(item.subject, item.rank) for item in held}, key=str),
                         sorted({(E3, 18), (E4, 17)}, key=str))
        self.assertEqual(first(held).rank, 17)

    def test_the_items_are_the_requirement_tables(self):
        """Each item bundling raises is RANK's (4.8): rank 1 conflict, rank 2 doubt, 17 act_part / act_cause /
        act_target, 18 performed_status (bundled)."""
        allowed = {(1, 'conflict'), (2, 'performed_status'), (17, 'act_part'), (17, 'act_cause'), (17, 'act_target'),
                   (18, 'performed_status')}
        for R, part in ((once(), E3), (once(snare_date=sup(ON), denial_=False), E3),
                        (build({E1: exam(), E2: emr(), E3: act(Kind.INJECTION)}, lesions=CECAL), E3),
                        (build({E1: exam(), E2: act(Kind.SNARE), E3: act(
                            Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS),
                            cause=sup(Cause.ACT_OF_THIS_SESSION))}), E3)):
            for item in C.verdict(R, part).held:
                with self.subTest(item=item.fact):
                    self.assertIn((item.rank, item.fact.split(':')[0]), allowed)
                    self.assertIn(rq.FactKey(item.fact.split(':')[0]), rq.RANK[rq.Rank(item.rank)])


# --- P-MONO (9.4) over the verdict and doubted -------------------------------------------------------------------------


SCENES = {
    'once': lambda: once(snare_date=sup(ON), denial_=False),
    'lift': lambda: build({E1: exam(), E2: emr(), E3: act(Kind.INJECTION, purpose=sup(Purpose.LIFT_FOR_RESECTION),
                                                          lesion=sup(L1), places=(sup(Landmark.CECUM),))},
                          lesions=CECAL),
    'apart': lambda: build({E1: exam(), E2: emr(), E3: act(Kind.INJECTION, places=(sup(Landmark.RECTUM),),
                                                           purpose=sup(Purpose.MARKING))}, lesions=CECAL,
                           controls=controls(E3, (Landmark.RECTUM,), E2, (Landmark.CECUM,))),
    'adjunct': lambda: build({E1: exam(), E2: act(Kind.SNARE), E3: act(
        Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2))}),
    'stent': lambda: build({E1: exam(), E3: act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)),
                            E4: act(Kind.STENT, duct=sup(ct.Duct.PANCREATIC))}, sessions={X1: session(SessionKind.ERCP)}),
    'own': lambda: build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY, lesion=sup(L2))},
                         lesions={L1: lesion(ct.Multiplicity.SINGLE), L2: lesion(ct.Multiplicity.SINGLE, distinct=(L1,))},
                         controls=lesion_controls(E3, L2, E2, L1)),
}


def weakenings(R: FactSet):
    """Every single weakening of 9.4 P-MONO over the events', lesions' and sessions' facts: an established fact made
    unresolved (its value kept), a doubt added to it (unknown, its value kept), a member deleted from a list; and a
    rejected pair control not rejected."""
    for family, table in (('events', R.events), ('lesions', R.lesions), ('sessions', R.sessions)):
        for subject, facts in table.items():
            for attribute, members in facts.items():
                for index, member in enumerate(members):
                    if F.established(member):
                        for weaker in (unres(member.value, member.state or State.SUPPORTED),
                                       doubted(member.value, state=member.state or State.SUPPORTED)):
                            yield family, subject, attribute, index, weaker
                    if len(members) > 1 or attribute in (A.TARGET_PLACES, A.PLACES, A.DISTINCT_FROM, A.SAME_AS):
                        yield family, subject, attribute, index, None
    for key, rejected in R.pair_controls.items():
        if rejected:
            yield 'controls', key, None, 0, None


def weaken(R: FactSet, change) -> FactSet:
    family, subject, attribute, index, weaker = change
    if family == 'controls':
        return FactSet(R.encounter, R.people, R.sections, R.sessions, R.anatomy, R.lesions, R.events, R.anchors,
                       R.unlisted, {**R.pair_controls, subject: False}, R.completeness)
    table = {key: dict(value) for key, value in getattr(R, family).items()}
    members = list(table[subject][attribute])
    if weaker is None:
        del members[index]
    else:
        members[index] = weaker
    table[subject][attribute] = tuple(members)
    parts = {'encounter': R.encounter, 'people': R.people, 'sections': R.sections, 'sessions': R.sessions,
             'anatomy': R.anatomy, 'lesions': R.lesions, 'events': R.events}
    parts[family] = table
    return FactSet(parts['encounter'], parts['people'], parts['sections'], parts['sessions'], parts['anatomy'],
                   parts['lesions'], parts['events'], R.anchors, R.unlisted, R.pair_controls, R.completeness)


class Monotone(SimpleTestCase):
    """9.4 P-MONO at the coverage level: weakening a fact never turns an act that is not its own (bundled F, or in
    doubt U) into its own (T) - so a code held by its bundling is never released by a weakening - never un-doubts an
    act, and never shrinks the acts base_included reads (reportable or doubted, 4.7)."""

    def test_p_mono_exhaustively_over_the_scenes(self):
        checked = 0
        for name, scene in SCENES.items():
            R = scene()
            base = {event: (C.verdict(R, event).truth, C.doubted(R, event), C.reportable(R, event))
                    for event in R.events}
            for change in weakenings(R):
                weak = weaken(R, change)
                for event, (truth, was_doubted, was_reportable) in base.items():
                    after = C.verdict(weak, event).truth
                    with self.subTest(scene=name, change=change[:4], event=event):
                        if truth is not T:
                            self.assertNotEqual(after, T)
                        if was_doubted:
                            self.assertTrue(C.doubted(weak, event))
                        if was_doubted or was_reportable:
                            self.assertTrue(C.doubted(weak, event) or C.reportable(weak, event))
                        checked += 1
        self.assertGreater(checked, 400)

    @hypothesis.settings(max_examples=150, deadline=None, derandomize=True)
    @hypothesis.given(st.sampled_from(sorted(SCENES)), st.data())
    def test_p_mono_under_two_weakenings(self, name, data):
        R = SCENES[name]()
        changes = list(weakenings(R))
        one = data.draw(st.sampled_from(changes))
        weak = weaken(R, one)
        two = data.draw(st.sampled_from(list(weakenings(weak)) or [one]))
        weaker = weaken(weak, two) if two is not one else weak
        for event in R.events:
            if C.verdict(R, event).truth is not T:
                self.assertNotEqual(C.verdict(weaker, event).truth, T)


# --- the text-free boundary (5.7 measure 4, measure 5) -----------------------------------------------------------------


class BoundaryTests(SimpleTestCase):
    def test_measure_4(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_no_retired_module_text_module_or_wording_is_imported(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        names = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        names |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual({name for name in names if name and name.startswith('studio')},
                         {'studio.interpretation', 'studio.interpretation.contract.types',
                          'studio.interpretation.engine', 'studio.interpretation.engine.types'})
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                    and node.module == 'studio.interpretation.engine' for alias in node.names}
        self.assertEqual(imported, {'anatomy', 'catalogue', 'pairing', 'reading', 'facts', 'requirements'})

    def test_mypy_strict_passes_on_the_module_and_refuses_a_string_operation(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=600, cwd=APP)

        result = mypy('studio/interpretation/engine/coverage.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 1 source file', result.stdout)
        probe = mypy('-c', 'from studio.interpretation.engine.coverage import Bundle\n'
                           'def probe(bundle: Bundle) -> bool:\n'
                           '    return bundle.rule.value.startswith("x") and bundle.part.startswith("E")\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)

    def test_the_records_hold_codes_ids_and_spans_only(self):
        """Every string a record carries is CPT Studio's code - an enumeration value of contract/types.py or of this
        module, a fact key, a cause, an id, the coding version, a proposal key - never document text."""
        values = {member.value for enum in vars(ct).values() if isinstance(enum, type) and issubclass(enum, Enum)
                  for member in enum if isinstance(member.value, str)}
        values |= {member.value for enum in (C.Rule, C.ItemReason, C.Detail, C.Truth) for member in enum}
        values |= {rq.fact_key(key) for key in rq.FactKey if key is not rq.FactKey.CONFLICT}
        values |= {C.CODING_VERSION, 'sel:0'}

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):  # its keys are the record's own field names, CPT Studio's code
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    yield from strings(item)

        def allowed(text):
            if text in values or text.startswith(('conflict:', 'coding_rule:', 'relation:', 'appraisal:',
                                                  'reading_', 'unestablished')):
                return True
            try:
                Id.parse(text)
                return True
            except ValueError:
                return False

        R = once()
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        records = [C.unresolved_record(cov.unresolved), C.bundled_record(cov.bundled),
                   C.event_coding(R, C.sessions(R), {'sel:0': (X1, (E2,))}),
                   [[service.item.fact, service.item.cause] for service in C.in_doubt_questions(R, cov)]]
        found = [text for record in records for text in strings(record)]
        self.assertTrue(found)
        self.assertEqual([text for text in found if not allowed(text)], [])



# --- v1's AdjunctBesideARemoval and PossiblyCurrent, re-expressed (D41, D58, D62 as FINAL-V2 reads them) --------------


def polypectomy(clip: dict, *, snare_places=(Landmark.RECTOSIGMOID,)):
    """v1's hot_snared(): a colonoscopy whose 12 mm polyp L1 at the rectosigmoid is removed with a hot snare (E2),
    beside ``clip`` (E3)."""
    return build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1), places=tuple(sup(place) for place in snare_places)),
                  E3: clip}, lesions={L1: lesion(ct.Multiplicity.SINGLE, places=snare_places)})


def hemoclips(**over) -> dict:
    """v1's hemoclips(): two clips whose hemostasis purpose is supported."""
    base = dict(purpose=sup(Purpose.HEMOSTASIS))
    base.update(over)
    return act(Kind.CLIP, **base)


class AdjunctBesideARemoval(SimpleTestCase):
    """v1's D41 and D58 tests. FINAL-V2 4.7 and 4.13 retire D41's lexical identity and D58/D77's place adjacency:
    causality is part_of and cause. A bleeding control whose cause is not stated is held by its code's own CAUSE row
    (4.3: cause supported pre_existing_lesion, spontaneous or earlier_procedure; step 4a), never by this module's
    bundling; one whose cause is act_of_this_session is bundled into the act cause_event names; one whose cause or
    cause_event is in doubt is asked (act_cause); places never decide."""

    def test_a_bleeding_control_naming_nothing_beside_a_polypectomy(self):
        """v1: "Immediate oozing from the polypectomy site was controlled with two hemoclips for hemostasis." asked
        (D41). v2: its cause unstated - no bundling (the CAUSE row asks act_cause); its cause in doubt - asked here
        (act_cause); stated as this session's act with the snare as cause_event - bundled."""
        self.assertEqual(C.bundles(polypectomy(hemoclips()), E3), ())
        R = polypectomy(hemoclips(cause=unres(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2)))
        self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
        self.assertEqual({(item.fact, item.attribute) for item in C.verdict(R, E3).held}, {('act_cause', A.CAUSE)})
        R = polypectomy(hemoclips(cause=sup(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2)))
        self.assertEqual(C.bundled(R, E3).whole, E2)

    def test_an_ablation_of_the_resection_margins_with_no_part_of(self):
        """v1 (D41) asked it. v2: nothing relates it to the EMR - no part_of, no cause - so it is its own act."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.ABLATION)}, lesions=CECAL)
        self.assertEqual(C.bundles(R, E3), ())

    def test_a_verified_part_of_another_act(self):
        """v1: "The biopsy site oozing was controlled with two hemoclips for hemostasis." part_of the biopsy: set apart
        from the removal, READY (v1 bundled an adjunct into a removal only). v2 (design B's procedure_caused; S4's
        failure class C1: "a bleeding control for bleeding this session's own biopsy ... caused", 43255 and 45382
        READY in v1, held by c2e53f8e): the control is the biopsy's adjunct - bundled into the biopsy, never into the
        removal."""
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)),
                   E3: hemoclips(part_of=sup(E4), relation=sup(ct.PartRelation.ADJUNCT_OF)), E4: act(Kind.BIOPSY)})
        found = C.bundled(R, E3)
        self.assertEqual((found.rule, found.whole), (C.Rule.PROCEDURAL_ADJUNCT, E4))
        self.assertNotIn(E2, [bundle.whole for bundle in C.bundles(R, E3)])

    def test_d58_places_never_decide(self):
        """v1's D58 variants (the distal sigmoid beside the rectosigmoid, the proximal transverse beside the hepatic
        flexure: adjacent, asked) and its controls (the descending colon, two steps away: READY): in v2 the clip's
        place decides nothing - with its cause unstated it is its own act everywhere; caused by the snare, bundled
        everywhere."""
        for place in (Landmark.SIGMOID_COLON, Landmark.TRANSVERSE_COLON, Landmark.DESCENDING_COLON,
                      Landmark.ASCENDING_COLON, Landmark.ANASTOMOSIS):
            with self.subTest(place=place):
                R = polypectomy(hemoclips(places=(sup(place),)))
                self.assertEqual(C.bundles(R, E3), ())
                R = polypectomy(hemoclips(places=(sup(place),), cause=sup(Cause.ACT_OF_THIS_SESSION),
                                          cause_event=sup(E2)))
                self.assertEqual(C.bundled(R, E3).whole, E2)


class PossiblyCurrent(SimpleTestCase):
    """v1's D62 (D54's review) as D68 and D98 complete it: an act possibly of this encounter is a doubt about its own
    code, never an absence for the rules that hold OTHER codes by it."""

    def test_possibly_today_reads_4_2(self):
        for found, expected in ((sup(ON), True), (sup(EARLIER), False), (neg(ON), False), (neg(EARLIER), True),
                                (doubted(ON, ON, EARLIER), True), (doubted(EARLIER, ON), True),
                                (unres(ON), True), (unres(EARLIER), False), (SILENT, True),
                                (contra(ON, EARLIER), True), (contra(EARLIER, ct.DateRelation.LATER_DATE), False)):
            with self.subTest(result=found.result, value=found.value, options=found.options):
                R = build({E1: exam(date=found)})
                self.assertEqual(C.possibly_today(R, E1), expected)

    def test_a_removal_with_an_unanchored_time_still_holds_the_biopsy_of_the_lesion_it_removed(self):
        """v1: "During this colonoscopy, a 6 mm sessile polyp in the sigmoid colon was biopsied and then removed with
        a cold snare." with the removal's time unverified: 45380 held, never READY. v2: the snare possibly today - the
        biopsy's bundling asked (U); established today - bundled (F); either way never its own act."""
        for date, truth in ((doubted(ON, ON, EARLIER), U), (unres(ON), U), (sup(ON), FF)):
            with self.subTest(date=date.result):
                R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1), date=date),
                           E3: act(Kind.BIOPSY, lesion=sup(L1))}, lesions={L1: lesion(ct.Multiplicity.SINGLE)},
                          anchors={E2: (2,), E3: (2,)})
                self.assertEqual(C.verdict(R, E3).truth, truth)
                self.assertTrue(C.bundling('45380', (E3,), R))

    def test_c4_needs_the_egds_own_examination(self):
        """v1's ``own``: C-4 and D70 read the EGD session's one done examination; two leave it unresolved and its own
        items stand."""
        R = build({E1: exam(session=sup(X1)), E3: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                  sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
        self.assertEqual((C.sessions(R)[X1].part_of, C.sessions(R)[X1].possibly_part_of), (None, None))


class Visits(SimpleTestCase):
    """v1's NOT_ACT_KINDS are the examination and the umbrellas: a visit in doubt is listed in doubt by reconcile, and
    event_coding drops every E/M kind from its lists (the session's own service is never an act beside itself)."""

    def test_a_visit_in_doubt(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E0: act(Kind.EM_VISIT, session=sup(X2), status=doubted(PERFORMED))},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.OFFICE_EM)})
        self.assertTrue(C.doubted(R, E0))
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual([(item.session, item.act, item.reason) for item in cov.unresolved],
                         [(X2, Kind.EM_VISIT, C.ItemReason.IN_DOUBT)])
        coding = C.event_coding(R, C.sessions(R), {})
        self.assertEqual((coding['sessions']['X2']['reportable'], coding['sessions']['X2']['doubted']), ([], []))

    def test_a_done_visit_is_reportable_and_never_listed_beside_itself(self):
        R = build({E0: act(Kind.EM_VISIT, session=sup(X2))}, sessions={X2: session(SessionKind.OFFICE_EM)})
        self.assertTrue(C.reportable(R, E0))
        self.assertEqual(C.event_coding(R, C.sessions(R), {})['sessions']['X2']['reportable'], [])
        cov = C.reconcile(R, [C.Counted('sel:0', '99213', SessionKind.OFFICE_EM, (E0,))], procedure_day=False)
        self.assertEqual(cov.unresolved, [])


class EstablishedBundling(SimpleTestCase):
    """An act established as part of one whole (F) carries its explanation alone: a question about ANOTHER possible
    whole could never release it (the bundling is an OR over its bundles - refute-4c-r1 B's shape: a question beside
    an established failure that can never make the code READY must not outrank it)."""

    def test_an_established_bundle_is_explained_never_asked_about_other_wholes(self):
        lesions = {L1: lesion(ct.Multiplicity.SINGLE), L2: lesion(ct.Multiplicity.SINGLE)}
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E4: act(Kind.SNARE, lesion=sup(L2)),
                   E3: act(Kind.BIOPSY, lesion=sup(L1))}, lesions=lesions)
        self.assertEqual(rules(R, E3), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T),
                                        (C.Rule.BIOPSY_OF_REMOVED_LESION, E4, U)])
        found = C.verdict(R, E3)
        self.assertEqual((found.truth, [(item.rank, item.kind) for item in found.held]),
                         (FF, [(18, ItemKind.EXPLANATION)]))
        # beside an act in doubt, the doubt's question (it can release the code) comes first
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E4: act(Kind.SNARE, lesion=sup(L2)),
                   E3: act(Kind.BIOPSY, lesion=sup(L1)), E5: act(Kind.BIOPSY)}, lesions=lesions)
        held = C.bundling('45380', (E3, E5), R)
        self.assertEqual((first(held).subject, first(held).rank), (E5, 17))
        self.assertIn((E3, 18), {(item.subject, item.rank) for item in held})


class IdentityNeverSetsApartUnestablished(SimpleTestCase):
    """4.5's session row and 4.11: an identity (a session, a duct, a lesion) sets two acts apart only when it is
    ESTABLISHED on both sides - a fact that is not established, whatever value pass 1 claimed for it, never does."""

    def test_the_session(self):
        two = {X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.FLEX_SIG)}
        base = {E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY, lesion=sup(L1))}
        lesions = {L1: lesion(ct.Multiplicity.SINGLE)}
        for found, truth in ((unres(X2), U), (doubted(X2), U), (sup(X2), None), (neg(X1), None)):
            with self.subTest(session=found.result):
                R = build({**base, E3: act(Kind.BIOPSY, lesion=sup(L1), session=found)}, sessions=two, lesions=lesions)
                self.assertEqual([bundle.truth for bundle in C.bundles(R, E3)], [truth] if truth else [])

    def test_the_duct(self):
        sessions_ = {X1: session(SessionKind.ERCP)}
        for found, truth in ((unres(ct.Duct.BILIARY), U), (doubted(ct.Duct.BILIARY), U), (sup(ct.Duct.BILIARY), None),
                             (neg(ct.Duct.PANCREATIC), None)):
            with self.subTest(duct=found.result):
                R = build({E1: exam(), E3: act(Kind.SPHINCTEROTOMY, duct=found),
                           E4: act(Kind.STENT, duct=sup(ct.Duct.PANCREATIC))}, sessions=sessions_)
                self.assertEqual([bundle.truth for bundle in C.bundles(R, E3)], [truth] if truth else [])

    def test_the_lesion(self):
        """Different supported lesions with no established distinct_from, or distinct_from without the lesion pair
        controls, are possibly one: asked."""
        for distinct, ctl in (((), {}), ((L1,), {}), ((L1,), lesion_controls(E3, L2, E2, L1, rejected=False))):
            with self.subTest(distinct=distinct, controls=bool(ctl)):
                R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY, lesion=sup(L2))},
                          lesions={L1: lesion(ct.Multiplicity.SINGLE),
                                   L2: lesion(ct.Multiplicity.SINGLE, distinct=distinct)}, controls=ctl)
                self.assertEqual([bundle.truth for bundle in C.bundles(R, E3)], [U])


# --- round 2: the repairs of refute-4b-r1, each pinned by a test that fails without it ---------------------------------


E7, E8 = Id(IdFamily.EVENT, 7), Id(IdFamily.EVENT, 8)


def two_sessions(e3_session, kind=Kind.BIOPSY, **e3) -> FactSet:
    """An EGD X1 (its done examination E1) and a colonoscopy X2 (E2), and a done act E3 of ``kind`` whose session fact
    is ``e3_session`` (None: an empty slot)."""
    return build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2)), E3: act(kind, session=e3_session, **e3)},
                 sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.COLONOSCOPY)})


def entries(R, which=('reportable', 'doubted')) -> dict:
    """{session id: the events among its event_coding@2 ``which`` entries} (what base_included reads, step 4d)."""
    coding = C.event_coding(R, C.sessions(R), {})
    return {sid: {entry['event'] for key in which for entry in record[key] if entry['event'] is not None}
            for sid, record in coding['sessions'].items()}


class RecordsKeepPossibleActs(SimpleTestCase):
    """refute-4b-r1 C1 (critical): event_coding@2 listed only the acts FILED under a session, so a weakening of an act's
    session fact (3.3 row 1's contradiction, a doubt on its empty slot) dropped it from every session's entries, and
    step 4d's base_included - which reads those entries as its only input ("an act possibly in the session included")
    - released the base code beside it (45378 READY beside a doubted biopsy). A session's doubted entries now hold
    every act possibly in it (possible_members) and doubted there (doubted_in)."""

    def test_c1_a_weakened_session_keeps_the_act_in_every_session_it_may_be_in(self):
        self.assertEqual(entries(two_sessions(sup(X2))), {'X1': set(), 'X2': {'E3'}})
        for weak, expected in ((contra(X1, X2), {'X1': {'E3'}, 'X2': {'E3'}}),
                               (doubted_empty(X1, X2), {'X1': {'E3'}, 'X2': {'E3'}}),
                               (unres(X2), {'X1': set(), 'X2': {'E3'}}),
                               (doubted(X2, X1, X2), {'X1': {'E3'}, 'X2': {'E3'}})):
            with self.subTest(session=weak.result, options=weak.options):
                R = two_sessions(weak)
                self.assertEqual(entries(R), expected)
                self.assertEqual(entries(R, ('doubted',)), expected)  # a doubt, never a fact
                self.assertTrue(C.doubted(R, E3))

    def test_c1_an_empty_session_slot_is_doubted_in_each_session(self):
        """P12: "Leave it empty when the document does not say which" - the act may be in any session."""
        R = build({E1: exam(), E3: act(Kind.BIOPSY, session=None)})
        self.assertEqual((C.filed(R, E3), entries(R)), (None, {'X1': {'E3'}}))
        self.assertEqual(entries(two_sessions(None)), {'X1': {'E3'}, 'X2': {'E3'}})
        self.assertEqual(C.possible_members(two_sessions(None), X1), (E1, E3))

    def test_c1_an_act_is_doubted_only_where_its_kind_may_be_reportable(self):
        """A PEG whose session is contradicted between the EGD and the colonoscopy is doubted in the EGD only: a
        colonoscopy's catalogue acts hold no PEG (it never holds 45378)."""
        R = two_sessions(contra(X1, X2), kind=Kind.PEG)
        self.assertEqual(entries(R), {'X1': {'E3'}, 'X2': set()})
        self.assertEqual((C.doubted_in(R, E3, X1), C.doubted_in(R, E3, X2)), (True, False))
        R = two_sessions(sup(X2))  # an established session is the act's only one
        self.assertEqual((C.doubted_in(R, E3, X1), C.doubted_in(R, E3, X2), C.reportable(R, E3)), (False, False, True))


class EusActsByCatalogueKind(SimpleTestCase):
    """refute-4b-r1 C2 (critical): D137's class is read by CATALOGUE kind (v1's eus_unprofiled_entries:
    ``catalogue_kind ... in listed``): a hemostatic clip or injection is a bleeding control, which the EUS's entry does
    not list, so it is recorded among the EUS session's acts and holds an examination-only EUS code (43259) beside it.
    Read by its raw kind it was neither reportable nor doubted, and 43259 was released."""

    def eus(self, part) -> FactSet:
        return build({E1: exam(), E3: part}, sessions={X1: session(SessionKind.EUS, tract=ct.Tract.UPPER)})

    def test_c2_a_hemostatic_clip_or_injection_is_recorded(self):
        for kind in (Kind.CLIP, Kind.INJECTION):
            with self.subTest(kind=kind):
                R = self.eus(act(kind, purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.PRE_EXISTING_LESION)))
                self.assertEqual(C.eus_unlisted(R, E3), (True, False))
                record = C.event_coding(R, C.sessions(R), {})['sessions']['X1']
                self.assertEqual((record['reportable'], record['doubted']),
                                 ([{'event': 'E3', 'kind': 'bleeding_control', 'lesion': None, 'unlisted': None}], []))
                self.assertEqual(C.eus_kinds(R, E3), frozenset({Kind.BLEEDING_CONTROL}))

    def test_c2_a_clip_whose_purpose_is_open_is_doubted(self):
        """D157's doubt: a clip whose purpose may be hemostasis may be a bleeding control - in doubt, recorded so."""
        for purpose in (unres(Purpose.HEMOSTASIS), None, doubted(Purpose.PROPHYLAXIS, Purpose.HEMOSTASIS)):
            with self.subTest(purpose=None if purpose is None else purpose.result):
                R = self.eus(act(Kind.CLIP, purpose=purpose))
                self.assertEqual(C.eus_unlisted(R, E3), (False, True))
                self.assertEqual(entries(R, ('doubted',)), {'X1': {'E3'}})

    def test_c2_controls(self):
        R = self.eus(act(Kind.CLIP, purpose=sup(Purpose.PROPHYLAXIS)))  # never reported: bundled (CLIP)
        self.assertEqual((C.eus_unlisted(R, E3), entries(R)), ((False, False), {'X1': set()}))
        R = self.eus(act(Kind.INJECTION))  # the EUS lists the injection: its own act, reportable as one
        self.assertEqual((C.eus_unlisted(R, E3), C.reportable(R, E3)), ((False, False), True))
        R = self.eus(act(Kind.OTHER))  # no catalogue kind (v1's ''): D137's class, as before
        self.assertEqual(C.eus_unlisted(R, E3), (True, False))
        R = self.eus(act(Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.ACT_OF_THIS_SESSION),
                         cause_event=sup(E1)))  # bleeding this EUS caused: its procedural adjunct, never recorded
        self.assertEqual((C.eus_unlisted(R, E3), C.bundled(R, E3).rule), ((False, False), C.Rule.PROCEDURAL_ADJUNCT))


class KindNotEstablished(SimpleTestCase):
    """refute-4b-r1 H1 (high): a done session whose kind is not established was skipped by reconcile and by the
    unestablished count, so completeness read 'complete_pending_review' - "Every documented service has a proposal" -
    beside a done examination no code reads (a weakening of the session's kind released completeness). It is listed
    no_proposal with its family None unless a counted code reads an event possibly in it (v1 grouped it by pass 1's
    claimed family and listed it)."""

    def scene(self, kind) -> FactSet:
        return build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                     sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(kind)})

    def test_h1_a_done_session_whose_kind_is_not_established_is_listed(self):
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]
        for kind, family in ((sup(SessionKind.EGD), SessionKind.EGD), (unres(SessionKind.EGD), None),
                             (doubted(SessionKind.EGD, SessionKind.EGD, SessionKind.ENTEROSCOPY), None),
                             (contra(SessionKind.EGD, SessionKind.ENTEROSCOPY), None)):
            with self.subTest(kind=kind.result):
                R = self.scene(kind)
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual([(item.session, item.family, item.reason, item.events) for item in cov.unresolved],
                                 [(X2, family, C.ItemReason.NO_PROPOSAL, (E2,))])
                complete = C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                                          label=label)
                self.assertEqual(complete['state'], 'incomplete')

    def test_h1_covered_by_a_code_that_reads_an_event_in_it(self):
        R = self.scene(unres(SessionKind.EGD))
        cov = C.reconcile(R, [C.Counted('sel:0', '43235', SessionKind.EGD, (), (E2,))], procedure_day=True)
        self.assertEqual((cov.covered.get(X2), [item.session for item in cov.unresolved]), (['43235'], [X1]))

    def test_h1_covered_only_under_every_reading(self):
        """Read as every family it may be of: an EGD code covers the reading as an EGD, none the reading as an
        enteroscopy - listed no_proposal (family None), covered by nothing. Round 2's own search: covering it by any
        code that read an event POSSIBLY in it let a weakening of another session's examination release it
        (logs/mono-case-242.out)."""
        R = self.scene(doubted(SessionKind.EGD, SessionKind.EGD, SessionKind.ENTEROSCOPY))
        cov = C.reconcile(R, [C.Counted('sel:0', '43235', SessionKind.EGD, (), (E2,))], procedure_day=True)
        self.assertEqual((cov.covered.get(X2), [(item.session, item.family, item.reason) for item in cov.unresolved]),
                         ([], [(X1, SessionKind.COLONOSCOPY, C.ItemReason.NO_PROPOSAL),
                               (X2, None, C.ItemReason.NO_PROPOSAL)]))
        for found in (sup(X1), contra(X1, X2)):  # trial 242's shape: a code of another family, its exam weakened
            with self.subTest(e1_session=found.result):
                events = {E1: exam(session=found), E2: exam(session=sup(X2))}
                R = build(events, sessions={X1: session(SessionKind.ERCP),
                                            X2: session(unres(SessionKind.ENTEROSCOPY))})
                cov = C.reconcile(R, [C.Counted('sel:0', '43260', SessionKind.ERCP, (E1,))], procedure_day=True)
                self.assertIn((X2, C.ItemReason.NO_PROPOSAL), [(item.session, item.reason) for item in cov.unresolved])

    def test_h1_a_session_of_no_supported_family_is_not_read(self):
        """As v1 read no family without a supported catalogue entry (sedation, other GI)."""
        R = self.scene(doubted(SessionKind.SEDATION, SessionKind.SEDATION, SessionKind.OTHER_GI))
        cov = C.reconcile(R, [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))], procedure_day=True)
        self.assertEqual(cov.unresolved, [])


class UnfiledActs(SimpleTestCase):
    """refute-4b-r1 L1 (the builder's Q9, unpinned) and H2 (high): an act filed under no session of the FactSet - an
    empty slot, a contradicted or doubted one, an id naming no session (settle's I4 keeps the claimed value) - is
    listed in doubt with its session None, never dropped; and a session whose examination's session fact is in doubt
    counts as unestablished by its possible members."""

    def test_l1_q9_an_act_filed_under_no_session_is_listed_in_doubt(self):
        for found in (None, contra(X1, X2), doubted_empty(X1)):
            with self.subTest(session=None if found is None else found.result):
                R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.BIOPSY, session=found)})
                cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
                self.assertEqual([(item.session, item.family, item.act, item.reason, item.events)
                                  for item in cov.unresolved], [(None, None, Kind.BIOPSY, C.ItemReason.IN_DOUBT, (E3,))])
                self.assertEqual([ref.event for _, ref in cov.in_doubt], [E3])
                self.assertEqual(C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                                                label=label)['state'], 'incomplete')

    def test_h2a_an_act_filed_under_a_session_id_naming_none(self):
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.BIOPSY, session=unres(Id(IdFamily.SESSION, 7)))})
        self.assertEqual((C.filed(R, E3), C.sessions_of(R, E3)), (Id(IdFamily.SESSION, 7), frozenset({X1})))
        cov = C.reconcile(R, COUNTED_45385, procedure_day=True)
        self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved],
                         [(None, C.ItemReason.IN_DOUBT, (E3,))])
        self.assertEqual(entries(R, ('doubted',)), {'X1': {'E3'}})
        R = two_sessions(contra(X1, Id(IdFamily.SESSION, 7)))  # a reading naming no session leaves every one open
        self.assertEqual(C.sessions_of(R, E3), frozenset({X1, X2}))

    def test_an_act_its_claimed_session_cannot_hold_stays_listed(self):
        """Round 2's own search (logs/q_k2_demoted-*.out): a done PEG filed under a colonoscopy is listed not covered
        (D142) while its session is supported; settle's K2 demotes exactly that session fact (D191: "a peg in a
        colonoscopy session"), and read in the colonoscopy's family alone the act was then doubted nowhere and listed
        nowhere - 'complete_pending_review'. An act whose own session is not established may be of any family (4.2)."""
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]
        for found, session_, reason in ((sup(X1), X1, C.ItemReason.NOT_COVERED), (unres(X1), X1, C.ItemReason.IN_DOUBT),
                                        (contra(X1, X2), None, C.ItemReason.IN_DOUBT)):
            with self.subTest(session=found.result):
                R = build({E1: exam(), E3: act(Kind.PEG, session=found)})
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved],
                                 [(session_, reason, (E3,))])
                self.assertEqual(entries(R), {'X1': set()})  # never a colonoscopy act: it holds no 45378

    def test_h2b_an_examination_whose_session_is_in_doubt_keeps_its_session_counted(self):
        counted = [C.Counted('sel:0', '43235', SessionKind.EGD, (E1,))]
        R = build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                  sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.COLONOSCOPY)})
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(([(item.session, item.reason) for item in cov.unresolved], cov.unestablished),
                         ([(X2, C.ItemReason.NO_PROPOSAL)], 0))
        for weak in (contra(X1, X2), doubted_empty(X1, X2), unres(X2)):
            with self.subTest(session=weak.result):
                R = build({E1: exam(session=sup(X1)), E2: exam(session=weak)},
                          sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.COLONOSCOPY)})
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual((C.sessions(R)[X2].done, cov.unestablished), (False, 1))
                self.assertEqual(C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                                                label=label)['state'], 'incomplete')


class ActsOfAnotherFamilyInDoubt(SimpleTestCase):
    """Round 2's own search (logs/q_d142_in_doubt*.out): D142 lists not covered a done act of a kind its session's
    family does not list among its acts though a supported family does - reachable past settle's K2 where the family's
    codes account for the kind and its acts do not (the ERCP's foreign body). In doubt (its status, date or kind not
    established) it was listed nowhere - v1's compl-1 and doubted read the family's acts - so a weakening released
    completeness. It is listed in doubt, with its service question."""

    def test_d142_in_doubt_is_listed(self):
        counted = [C.Counted('sel:0', '43260', SessionKind.ERCP, (E1,))]
        for name, over, reason in (('done', {}, C.ItemReason.NOT_COVERED),
                                   ('status unresolved', dict(status=unres(PERFORMED)), C.ItemReason.IN_DOUBT),
                                   ('date in doubt', dict(date=doubted(ON, ON, EARLIER)), C.ItemReason.IN_DOUBT),
                                   ('kind contradicted', dict(kind=contra(Kind.FOREIGN_BODY, Kind.DECOMPRESSION)),
                                    C.ItemReason.IN_DOUBT)):
            with self.subTest(name):
                R = build({E1: exam(), E3: act(Kind.FOREIGN_BODY, **over)}, sessions={X1: session(SessionKind.ERCP)})
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual([(item.reason, item.events) for item in cov.unresolved], [(reason, (E3,))])
                if reason is C.ItemReason.IN_DOUBT:
                    self.assertEqual([service.event for service in C.in_doubt_questions(R, cov)], [E3])
        R = build({E1: exam(), E3: act(Kind.FOREIGN_BODY, date=sup(EARLIER))}, sessions={X1: session(SessionKind.ERCP)})
        self.assertEqual(C.reconcile(R, counted, procedure_day=True).unresolved, [])  # another date: no act of today


class C4ReadsTheEusKindByPossibly(SimpleTestCase):
    """refute-4b-r1 M1 (medium): C-4's EUS was read by its established kind only, so a done EGD beside an upper EUS
    whose kind is not established was possibly part of nothing; 4.7: "possibly_part_of by possibly"."""

    def scene(self, kind) -> FactSet:
        return build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                     sessions={X1: session(SessionKind.EGD), X2: session(kind, tract=ct.Tract.UPPER)})

    def test_m1_an_eus_kind_not_established_leaves_the_egd_possibly_part_of_it(self):
        for kind, expected in ((sup(SessionKind.EUS), (X2, None)), (unres(SessionKind.EUS), (None, X2)),
                               (doubted(SessionKind.EUS, SessionKind.EUS, SessionKind.ERCP), (None, X2)),
                               (contra(SessionKind.EUS, SessionKind.ERCP), (None, X2)),
                               (sup(SessionKind.ERCP), (None, None)), (neg(SessionKind.EUS), (None, None))):
            with self.subTest(kind=kind.result, value=kind.value):
                found = C.sessions(self.scene(kind))[X1]
                self.assertEqual((found.part_of, found.possibly_part_of), expected)


class UnsupportedKinds(SimpleTestCase):
    """refute-4b-r1 M2 (medium), hand-off 1e:R3: reconcile reads each family's UNSUPPORTED_KINDS besides v1's
    UNSUPPORTED_ACTS - the anorectal balloon expulsion, which its catalogue entry says "is listed for the reviewer",
    was listed nowhere; the EUS's drainage, which its acts also list (43240), stays the EUS's act."""

    def test_m2_the_table(self):
        self.assertEqual(C.unsupported_kinds(SessionKind.ANORECTAL), frozenset({Kind.ESD, Kind.BALLOON_EXPULSION}))
        for family in (SessionKind.EUS, SessionKind.EGD, SessionKind.COLONOSCOPY, SessionKind.ERCP):
            with self.subTest(family=family):
                self.assertEqual(C.unsupported_kinds(family), frozenset({Kind.ESD}))

    def test_m2_a_balloon_expulsion_is_listed_unsupported(self):
        R = build({E1: act(Kind.MANOMETRY), E2: act(Kind.BALLOON_EXPULSION)},
                  sessions={X1: session(SessionKind.ANORECTAL)})
        cov = C.reconcile(R, [C.Counted('sel:0', '91122', SessionKind.ANORECTAL, (E1,))], procedure_day=True)
        self.assertEqual([(item.act, item.reason, item.detail, item.events) for item in cov.unresolved],
                         [(Kind.BALLOON_EXPULSION, C.ItemReason.UNSUPPORTED, C.Detail.NO_PROFILE, (E2,))])
        cov = C.reconcile(R, [], procedure_day=True)  # no code: the session's no_proposal, and the act
        self.assertEqual([(item.act, item.reason) for item in cov.unresolved],
                         [(None, C.ItemReason.NO_PROPOSAL), (Kind.BALLOON_EXPULSION, C.ItemReason.UNSUPPORTED)])

    def test_m2_an_eus_drainage_stays_the_eus_act(self):
        R = build({E1: exam(), E2: act(Kind.FNA), E3: act(Kind.DRAINAGE)},
                  sessions={X1: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
        cov = C.reconcile(R, [C.Counted('sel:0', '43238', SessionKind.EUS, (E2,))], procedure_day=True)
        self.assertEqual([(item.act, item.reason) for item in cov.unresolved],
                         [(Kind.DRAINAGE, C.ItemReason.NOT_COVERED)])


class LesionAdjunct(SimpleTestCase):
    """refute-4b-r1 DQ1 (a design question, built fail-closed and listed): v1's D30 bundled an ablation or a bleeding
    control of the removal's verified lesion (a FACT arm 4.7's "gone" column does not retire); round 1 dropped it, so
    "APC was applied to the residual tissue at the EMR site." (an ablation of L1 beside the EMR of L1, part_of and cause
    not stated) left 45388 READY. It is now POSSIBLY the removal's adjunct: asked (act_part), never explained - whether
    the lesion alone bundles it is the design's to say."""

    def test_dq1_an_adjunct_of_the_removed_lesion_is_asked_never_explained(self):
        for name, part, whole in (
                ('ablation beside the EMR', act(Kind.ABLATION, lesion=sup(L1)), emr()),
                ('hemostatic clip beside the snare', hemoclips(lesion=sup(L1)), act(Kind.SNARE, lesion=sup(L1))),
                ('a lesion only possibly the same', act(Kind.ABLATION, lesion=unres(L1)), emr())):
            with self.subTest(name):
                R = build({E1: exam(), E2: whole, E3: part}, lesions=CECAL)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                found = C.verdict(R, E3)
                self.assertEqual(found.truth, U)
                self.assertIn(('act_part', 17, E3, A.PART_OF), {(item.fact, item.rank, item.subject, item.attribute)
                                                               for item in found.held})
                held = C.bundling('45388', (E3,), R)
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION or item.rank == 18])
                self.assertIsNone(C.bundled(R, E3))

    def test_dq1_controls(self):
        lesions = {**CECAL, L2: lesion(ct.Multiplicity.SINGLE, distinct=(L1,))}
        for name, part, ctl in (
                ('no lesion stated (round 1 reading kept)', act(Kind.ABLATION), {}),
                ('another lesion, established apart', act(Kind.ABLATION, lesion=sup(L2)),
                 lesion_controls(E3, L2, E2, L1)),
                ('bleeding the lesion had before (cause pre-existing: 4.3 CAUSE decides)',
                 hemoclips(lesion=sup(L1), cause=sup(Cause.PRE_EXISTING_LESION)), {}),
                ('stated not part of the EMR', act(Kind.ABLATION, lesion=sup(L1), part_of=neg(E2)), {}),
                ('a marking injection (no adjunct kind of v1)', act(Kind.INJECTION, lesion=sup(L1),
                                                                    purpose=sup(Purpose.MARKING)), {})):
            with self.subTest(name):
                R = build({E1: exam(), E2: emr(), E3: part}, lesions=lesions, controls=ctl)
                self.assertNotIn(C.Rule.PROCEDURAL_ADJUNCT, [bundle.rule for bundle in C.bundles(R, E3)])
        R = build({E1: exam(), E2: emr(), E3: act(Kind.ABLATION, lesion=sup(L1), part_of=sup(E2),
                                                     relation=sup(ct.PartRelation.ADJUNCT_OF))}, lesions=CECAL)
        self.assertEqual(C.bundled(R, E3).whole, E2)  # stated part of the EMR: explained, as before


# --- 9.4 P-MONO at the records, under the weakenings round 1 did not make ----------------------------------------------


def _alternative(R: FactSet, value):
    """Another value of ``value``'s domain (a contradiction's second side): the next member of its enumeration, or the
    next object of its family that the FactSet holds (another number when it holds none)."""
    if isinstance(value, Enum):
        members = list(type(value))
        return members[(members.index(value) + 1) % len(members)]
    if isinstance(value, Id):
        tables = {IdFamily.EVENT: R.events, IdFamily.SESSION: R.sessions, IdFamily.LESION: R.lesions}
        table = tables.get(value.family, {})
        others = [other for other in table if other != value]
        return others[0] if others else Id(value.family, value.number + 1)
    return None


# An empty slot a doubt may name, with the reading it names (3.3 row 2): the act's session, part_of, cause and lesion.
_EMPTY_SLOTS = {A.SESSION: X1, A.PART_OF: E2, A.CAUSE: Cause.ACT_OF_THIS_SESSION, A.CAUSE_EVENT: E2,
                A.TARGET_LESION: L1, A.PURPOSE: Purpose.HEMOSTASIS}


def strong_weakenings(R: FactSet):
    """9.4 P-MONO's weakenings, round 1's plus those it did not make (refute-4b-r1 C1, H1, H2): every established fact
    made unresolved, doubted (its value kept) or CONTRADICTED (3.3 row 1: a doubt with basis conflict, its value one
    side); a doubt on each EMPTY slot of _EMPTY_SLOTS; a member deleted from a list; a rejected pair control not
    rejected."""
    for family, table in (('events', R.events), ('lesions', R.lesions), ('sessions', R.sessions)):
        for subject, facts in table.items():
            for attribute, members in facts.items():
                for index, member in enumerate(members):
                    if F.established(member):
                        state = member.state or State.SUPPORTED
                        yield family, subject, attribute, index, unres(member.value, state)
                        yield family, subject, attribute, index, doubted(member.value, state=state)
                        other = _alternative(R, member.value)
                        if other is not None:
                            yield family, subject, attribute, index, contra(member.value, other)
                    if len(members) > 1 or attribute in (A.TARGET_PLACES, A.PLACES, A.DISTINCT_FROM, A.SAME_AS):
                        yield family, subject, attribute, index, None
            if family == 'events':
                for attribute, reading in _EMPTY_SLOTS.items():
                    if not facts.get(attribute):
                        yield 'empty', subject, attribute, 0, doubted_empty(reading)
    for key, rejected in R.pair_controls.items():
        if rejected:
            yield 'controls', key, None, 0, None


def strong_weaken(R: FactSet, change) -> FactSet:
    family, subject, attribute, index, weaker = change
    if family != 'empty':
        return weaken(R, change)
    events = {key: dict(value) for key, value in R.events.items()}
    events[subject][attribute] = (weaker,)
    return FactSet(R.encounter, R.people, R.sections, R.sessions, R.anatomy, R.lesions, events, R.anchors, R.unlisted,
                   R.pair_controls, R.completeness)


# Two-session scenes, each with the counted codes its completeness reads (incomplete: every scene leaves something).
RECORD_SCENES = {
    'egd_and_colonoscopy': (lambda: build(
        {E1: exam(session=sup(X1)), E2: exam(session=sup(X2)), E3: act(Kind.BIOPSY, session=sup(X2), lesion=sup(L1)),
         E4: act(Kind.SNARE, session=sup(X2), lesion=sup(L1)), E5: act(Kind.ABLATION, session=sup(X2), lesion=sup(L1)),
         E6: act(Kind.PEG, session=sup(X1))},
        sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.COLONOSCOPY)},
        lesions={L1: lesion(ct.Multiplicity.SINGLE)}), [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E2,))]),
    'upper_eus_and_egd': (lambda: build(
        {E1: exam(session=sup(X1)), E2: exam(session=sup(X2)), E3: act(Kind.STENT, session=sup(X1)),
         E4: act(Kind.CLIP, session=sup(X1), purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.PRE_EXISTING_LESION)),
         E5: act(Kind.BIOPSY, session=sup(X2))},
        sessions={X1: session(SessionKind.EUS, tract=ct.Tract.UPPER), X2: session(SessionKind.EGD)}),
        [C.Counted('sel:0', '43259', SessionKind.EUS, (E1,))]),
    # refute-4b-r1 H1/H2 (p4): a session told only by its done examination, no code reading it
    'examination_only': (lambda: build(
        {E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
        sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)}),
        [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]),
    # round 2's search: a PEG filed under a colonoscopy (D142 while its session is supported; K2 demotes it)
    'act_its_session_cannot_hold': (lambda: build(
        {E1: exam(session=sup(X1)), E3: act(Kind.PEG, session=sup(X1))},
        sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.FLEX_SIG)}),
        [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]),
    # round 2's search: D142's class reachable past K2 (the ERCP's foreign body), done and read by no code
    'ercp_foreign_body': (lambda: build(
        {E1: exam(session=sup(X1)), E3: act(Kind.FOREIGN_BODY, session=sup(X1)), E4: exam(session=sup(X2))},
        sessions={X1: session(SessionKind.ERCP), X2: session(SessionKind.EGD)}),
        [C.Counted('sel:0', '43260', SessionKind.ERCP, (E1,)), C.Counted('sel:1', '43235', SessionKind.EGD, (E4,))]),
}


class MonotoneRecords(SimpleTestCase):
    """9.4 P-MONO at the records base_included reads, over two sessions and the weakenings round 1's Monotone did not
    make (refute-4b-r1 C1, H1, H2): weakening a fact never shrinks a session's reportable-or-doubted entries, never
    turns a verdict that is not T into T, never un-doubts an act, and never turns an incomplete completeness complete."""

    def test_p_mono_over_two_sessions_and_contradictions(self):
        checked = 0
        for name, (scene, counted) in RECORD_SCENES.items():
            R = scene()
            before = entries(R)
            verdicts = {event: (C.verdict(R, event).truth, C.doubted(R, event)) for event in R.events}
            cov = C.reconcile(R, counted, procedure_day=True)
            self.assertEqual(C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                                            label=label)['state'], 'incomplete')
            for change in strong_weakenings(R):
                weak = strong_weaken(R, change)
                with self.subTest(scene=name, change=change[:4], weaker=None if change[4] is None else (
                        change[4].result, change[4].value, change[4].options)):
                    after = entries(weak)
                    for sid, acts in before.items():
                        self.assertLessEqual(acts, after[sid])
                    for event, (truth, was_doubted) in verdicts.items():
                        if truth is not T:
                            self.assertNotEqual(C.verdict(weak, event).truth, T)
                        if was_doubted:
                            self.assertTrue(C.doubted(weak, event))
                    cov = C.reconcile(weak, counted, procedure_day=True)
                    self.assertEqual(C.completeness(cov, C.sessions(weak), open_questions=0, provider_ok=True,
                                                    conflicts=0, label=label)['state'], 'incomplete')
                    checked += 1
        self.assertGreater(checked, 250)  # 281 measured
