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

Repair r4b (the rulings on refute-4b-r2; each class failing without its repair, the step's NOTES): OneSessionDone
(DECISIONS D227 F2: E13, and the cross-module test D227 asks for - coverage's done_examinations, possible_examinations
and session record against engine/combination.py's session_done, read only, over generated FactSets),
ContradictedNeverReadUnder (D227 F3), ReadUnderCompleteness (D227 F4), AdjunctAsksOnlyForTheSameLesion (D221, mutant
RQ1's reach), LiftReadsItsRelation (F6), D70ReadsPossibleMembers (F7: mutant RM1_FILED_MEMBERS),
FamiliesOfAnActWhoseSessionIsOpen (D227 F8) and NegationLeftOpen (sessions_of under a weakened negation). D227 changed
two round-1/2 expectations, each said where it is: Coverage.test_read_under (a place list read as complete) and
MonotoneRecords (4.3 row 7's open questions counted: row_7_holds).

Repair r4b, round 2 (refute-r4b-r1; each class failing without its repair): SameAsIsAnEquivalence (R1: a chain of
same_as members through other entries joins two lesions as one member does), MissingLesionIdentifiers (R2: 4.11),
ReadUnderListingsKeepTheirDetail (R3: D225), OneSessionDone.test_e13_the_no_proposal_item_never_quotes_a_digital_
examination (R4) and NotDoneSessionsKeepTheirActsListed (R5, built fail-closed: question QR5-1). Changed with them,
each said where: MonotoneRecords now holds completeness incomplete with no open question counted (R5);
OneSessionDone.test_an_established_examination_not_done_leaves_its_session_not_done lists the done snare (R5); and two
D221 cases that held no lesion entry for an id they named (R2): AdjunctAsksOnlyForTheSameLesion's 'a bleeding control
of another lesion' and test_d221_controls' 'a same_as naming a third lesion' now hold that entry.

Repair r4b, round 3 (DECISIONS D231's coverage half and D248 on refute-r4b-r2 G1-G7; each class failing without its
repair, the step's NOTES): SyntheticActIsAPossibleWhole (C1), SyntheticExaminationLeftOpen (C2),
SyntheticActMayMakeAWhole (C3) - each with the unlisted act, the unlisted doubt and the filed doubted form giving one
outcome - UnestablishedCountReadsTheSyntheticAct (D216's audit of the module), ReadByNoCountedCodePerSession (G1, with
refute-r4b-r2's sessions search, and G6's ALL), UnknownIdentityAsksItsLesion (G2, option (b)),
ContradictedIdentityIsAsked (G3), OneEntryPerAct (G4), SameAsWalkCost (G5) and ZeroOneWalk (G7); D227's agreement
generates kept unlisted entries (step 4d's request R1 (c)) and MonotoneRecords reads a scene of synthetic acts. Changed
with them, each said where: four rows of test_d221_one_lesion_or_a_same_as_that_may_join_them_asks and one of
test_d221_controls (G2), NotDoneSessionsKeepTheirActsListed's second session (G1), and the import pin (coverage reads
step 4d's reference for D227's one derivation and D231's synthetic act).

Repair r4b, round 4 (repair r4b-2, on refute-r4b-r1 F1-F3; each test failing without its repair, the step's NOTES):
OneFindingNeverApartByPlace - F1 (a claim that two lesions are not one finding, beside supported members joining them,
is asked whatever the places say, in every SAME LESION rule, and a weakening that adds one never releases the part), F2
(the claim's contradicted arm pinned), F3 built fail-closed (DECISIONS D239's reading for bundling, question QF3: a
weakened identity is never set apart by place; what still is), and refute-r4b-r1's places search with a fixed seed.

Repair r4b of round w8r (DECISIONS D256 P2's coverage half, on refute-r4d-r2 P2; built on step r4d's patch, whose
combination.session_possibly_done is the reference): EstablishedNotDoneTodayIsNeverPossiblyDone - the planned and the
earlier EUS beside an EGD with an office visit act, a pH capsule placement act or a biopsy doubt kept unlisted with no
card, and their filed analog, coverage and 4d reading one answer for each; the controls (carded entries, a claimed
session slot, a dated act, an EUS not settled, K2); possible_examinations' exception; the mirrored predicate pinned to
4d's; and a generated agreement over P2's shapes. Changed with it, said where: OneSessionDone's agreement reads 4d's
possible examination less D256 P2's exception (p2_reference_left_open).

Repair r4b of round w9r (DECISIONS D269's coverage half: Q-P2DATE option (c), refute-r4d-r1 V8R4D1-6, refute-r4b-r1
V8R4B1-3, r4b's question Q3 of round w8r, the integration's I4 residual; built on step r4d's patch of round w9r, whose
combination.not_done_today, session_possibly_done and wholes are the reference): a session whose examination is
established, and established not done on the date of service, lists no possible examination and is never a whole,
whatever an act's date or session slot. EstablishedNotDoneTodayIsNeverPossiblyDone gains the done-when
(test_d269_the_planned_and_the_earlier_eus_beside_an_office_visit_act: dated, undated, a slot empty with a doubt, a slot
claimed with a reading, each beside the EGD's own C3 or D70 claim), C3's and D70's claims naming such a session with
the EGD's own items (test_d269_c3_and_d70_...), the exemption's grid against 4d's reading
(test_d269_the_exemption_is_4ds_..., replacing round w8r's pin of the mirrored predicate, gone with 4d's
combination._unplaced_undated) and Q3's weakening pin (test_d269_q3_...). Changed with it, said where:
p2_reference_left_open reads D269 (none in a session established not done today), so OneSessionDone's agreement does
too and asserts that a session with an examination left open is one 4d reads possibly done; test_p2_controls' rows for
the planned and the earlier EUS expect no whole (round w8r's Q-P2DATE pin among them) and gain Q-NDT's control;
test_p2_possible_examinations reaches dated acts and claimed slots; one_answer reads "part of X2 exactly when X2 is
possibly done" only with no claim of the EGD's own; the generated agreement (p2_scene, now with the EGD's own claim and
V8R4B1-3's slots) asserts no settled whole.
"""
from __future__ import annotations

import ast
import os
import random
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import combination as CB  # read only: D227's reference "session done" (step 4d)
from studio.interpretation.engine import coverage as C
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q  # read only: step 4a's order of a held code's items (4.8)
from studio.interpretation.engine import reading as RD
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


# READ_UNDER's one rule: the EUS forceps biopsy, read under the upper endoscopy in the upper GI regions.
READ_UNDER_REGIONS = catalogue.READ_UNDER[(SessionKind.EUS, Kind.BIOPSY)][1]


def complete(event, listed, rejected=True, regions=READ_UNDER_REGIONS) -> dict:
    """DECISIONS D227 F4: the pair controls that establish ``event``'s place list (``listed``) complete within
    ``regions`` - every landmark outside them that none of its places is compatible with, asked of it ("This act was
    done in the {place}.") and rejected (True) or not."""
    return {(event, A.TARGET_PLACES, landmark): rejected for landmark in Landmark
            if not anatomy.in_regions(landmark, regions)
            and not any(anatomy.compatible(landmark, place) for place in listed)}


def rules(R, part) -> list:
    """(rule, whole, truth) of every bundle of ``part``."""
    return [(bundle.rule, bundle.whole, bundle.truth) for bundle in C.bundles(R, part)]


def first(items):
    return sorted(items, key=lambda item: (item.rank if item.rank is not None else 99,
                                           0 if item.kind is ItemKind.QUESTION else 1))[0]


# The v1 fixtures, as facts: a colonoscopy X1 (E1) to the cecum; its cecal 20 mm polyp L1.
CECAL = {L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.CECUM,))}


# Round r3's silent-link rule (DESIGN-v2 b.8, DECISIONS D308 Q-B; restated at round r3's integration): a procedural
# adjunct whose part_of is silent beside any other act, or whose cause is silent where it may treat bleeding (a silent
# purpose is possibly hemostasis), is a DOUBT - held until Fable's proven answer. A test of another rule (D221's lesion
# arm, the lift's identity, a place, a same_as ...) states that link of its part, so it reads the rule it tests and
# nothing else: its part_of negated (done in its own right - it names no whole, so D221's own exception, _not_adjunct,
# which needs a negation NAMING the whole, is untouched) and its purpose treatment (no bleeding treated: the cause arm's
# premise F). The silent link itself is pinned by tests/v2/test_r3_probe (SilentLinkTests) and test_r3b_int4.
STATED_LINK = {"part_of": neg(None), "purpose": sup(Purpose.TREATMENT)}
# the same link stated where the test reads the part's PURPOSE (an injection's lift): its part_of negated and its cause a
# lesion present before the session (the cause arm F by its cause), its purpose left as the test gives it
LINK_KEEPING_PURPOSE = {"part_of": neg(None), "cause": sup(Cause.PRE_EXISTING_LESION)}


def doubted_links(R, part) -> list:
    """(rule, whole, truth, the attributes its doubts name) of every bundle of ``part``: what the silent-link rule's
    bundles are pinned by (round r3, DESIGN-v2 b.8)."""
    return [(bundle.rule, bundle.whole, bundle.truth, {doubt.attribute for doubt in bundle.doubts})
            for bundle in C.bundles(R, part)]


# Round r3's silent-link bundles of a part beside the examination E1 and an act E2, its cause and its part_of silent: the
# cause arm over every event of the session (any event may have caused the bleeding it may treat), the part arm over the
# act (DESIGN-v2 b.8, DECISIONS D308 Q-B)
SILENT_LINKS = [(C.Rule.PROCEDURAL_ADJUNCT, E1, U, {A.CAUSE}), (C.Rule.PROCEDURAL_ADJUNCT, E2, U, {A.CAUSE, A.PART_OF})]


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
        explanation naming the EMR (rank 18); its part_of naming the EMR with part_relation lift_for or step_of (4.7's
        lift row; refute-4b-r2 F6) bundles it too."""
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
        v2: its purpose and lesion unstated leave the lift possible (U): asked, never its own act. (Restated at round
        r3's integration: beside the lift, the silent-link rule asks its unstated part_of and cause too - DESIGN-v2 b.8;
        with that link stated the lift's own questions are the only ones, as before.)"""
        R = self.lifted()
        self.assertIsNone(C.bundled(R, E3))
        self.assertEqual(rules(R, E3), [(C.Rule.LIFT_INJECTION, E2, U), *[row[:3] for row in SILENT_LINKS]])
        held = C.bundling('45381', (E3,), R)
        self.assertEqual({item.fact for item in held}, {'act_part', 'act_target', 'act_cause'})
        self.assertTrue(all(item.rank == 17 and item.kind is ItemKind.QUESTION for item in held))
        R = self.lifted(**LINK_KEEPING_PURPOSE)
        self.assertIsNone(C.bundled(R, E3))
        self.assertEqual(rules(R, E3), [(C.Rule.LIFT_INJECTION, E2, U)])
        held = C.bundling('45381', (E3,), R)
        self.assertTrue(held)
        self.assertEqual({item.fact for item in held}, {'act_part', 'act_target'})
        self.assertTrue(all(item.rank == 17 and item.kind is ItemKind.QUESTION for item in held))

    def test_an_injection_at_a_disjoint_place_is_its_own_act(self):
        """v1: an injection in the rectum beside the cecal EMR is its own act (45381 READY). v2: by its established
        place, disjoint from the EMR's, with the pair controls rejected (4.2 [R:SC-B]). (Restated at round r3's
        integration: the place sets the LIFT apart, as before; its part_of and cause unstated, the silent-link rule asks
        them - DESIGN-v2 b.8, a doubt no place decides; that link stated, its own act by its place, as before.)"""
        events = {E1: exam(), E2: emr(), E3: act(Kind.INJECTION, places=(sup(Landmark.RECTUM),))}
        R = build(events, lesions=CECAL, controls=controls(E3, (Landmark.RECTUM,), E2, (Landmark.CECUM,)))
        self.assertEqual(doubted_links(R, E3), SILENT_LINKS)  # no LIFT bundle: the place
        events = {E1: exam(), E2: emr(), E3: act(Kind.INJECTION, places=(sup(Landmark.RECTUM),), **LINK_KEEPING_PURPOSE)}
        R = build(events, lesions=CECAL, controls=controls(E3, (Landmark.RECTUM,), E2, (Landmark.CECUM,)))
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth, C.bundling('45381', (E3,), R)), ([], T, ()))
        # SC-B: a place difference counts only with its pair controls rejected - without them it is asked
        R = build(events, lesions=CECAL)
        self.assertEqual(rules(R, E3), [(C.Rule.LIFT_INJECTION, E2, U)])

    def test_a_tattoo_is_never_a_lift_by_place_alone(self):
        """v1: a tattoo in the cecum is never a lift by place alone. v2: the purpose arm is the injection's (a tattoo's
        purpose is no lift), so a marking tattoo is its own act; its part_of naming the EMR still bundles it (v1's
        ONE_ACT arm). (Restated at round r3's integration: never by place alone, as before - but its part_of unstated,
        the silent-link rule asks it, the tattoo's lift by part being its only arm - DESIGN-v2 b.8; stated not a part,
        its own act.)"""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.TATTOO, purpose=sup(Purpose.MARKING),
                                                 places=(sup(Landmark.CECUM),))}, lesions=CECAL)
        self.assertEqual(doubted_links(R, E3), [(C.Rule.LIFT_INJECTION, E2, U, {A.PART_OF, A.PART_RELATION})])
        R = build({E1: exam(), E2: emr(), E3: act(Kind.TATTOO, purpose=sup(Purpose.MARKING), part_of=neg(None),
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
        # (restated at round r3's integration: its part_of unstated beside the snare, the silent-link rule asks it -
        # DESIGN-v2 b.8 - and stated not a part, no adjunct, reportable, as before)
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS),
                                                  cause=sup(Cause.PRE_EXISTING_LESION))})
        self.assertEqual(doubted_links(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U, {A.PART_OF})])
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP, purpose=sup(Purpose.HEMOSTASIS),
                                                  cause=sup(Cause.PRE_EXISTING_LESION), part_of=neg(None))})
        self.assertEqual((C.bundles(R, E3), C.reportable(R, E3)), ((), True))
        cov = C.reconcile(R, [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E2,))], procedure_day=True)
        self.assertEqual([(item.act, item.reason) for item in cov.unresolved],
                         [(Kind.BLEEDING_CONTROL, C.ItemReason.NOT_COVERED)])
        R = build({E1: exam(), E2: snare, E3: act(Kind.CLIP)})
        # beside D157's doubt, round r3's silent links (DESIGN-v2 b.8): its cause and its part_of unstated
        self.assertEqual(rules(R, E3), [(C.Rule.CLIP, None, U), *[row[:3] for row in SILENT_LINKS]])
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
        # an ERCP injection whose purpose may be hemostasis may be a bleeding control: asked, never bundled silently -
        # and (round r3's silent-link rule, DESIGN-v2 b.8) its unstated cause asked beside it, the examination its whole
        R = build({E1: exam(), E2: act(Kind.INJECTION)}, sessions={X1: session(SessionKind.ERCP)})
        self.assertEqual(doubted_links(R, E2), [(C.Rule.FAMILY_BUNDLED, None, U, {A.PURPOSE}),
                                                (C.Rule.PROCEDURAL_ADJUNCT, E1, U, {A.CAUSE})])


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
        relates the ablation to the resection, whatever its place - its own act. (Restated at round r3's integration:
        with its part_of, its cause and its purpose UNSTATED, the silent-link rule asks them whatever its place -
        DESIGN-v2 b.8, DECISIONS D308 Q-B - and Fable's proven part-link answer releases it; with them stated, its own
        act whatever its place, as before.)"""
        for place in (Landmark.TRANSVERSE_COLON, Landmark.ASCENDING_COLON, Landmark.CECUM):
            with self.subTest(place=place):
                R = self.adjunct(places=(sup(place),))
                self.assertEqual(doubted_links(R, E3), SILENT_LINKS)
                self.assertEqual({(item.fact, item.rank) for item in C.bundling('45388', (E3,), R)},
                                 {('act_cause', 17), ('act_part', 17)})
                R = self.adjunct(places=(sup(place),), **STATED_LINK)
                self.assertEqual((rules(R, E3), C.bundling('45388', (E3,), R)), ([], ()))

    def test_an_adjunct_of_a_removal_of_another_encounter_is_its_own_act(self):
        """v1: "... removed with a cold snare in 2024." / "The scar was treated with argon plasma coagulation." part_of
        E2: READY. v2: the whole's date relation established as another date - no whole. (Restated at round r3's
        integration: no whole by its part_of, as before; its purpose and cause unstated, the silent-link rule asks
        the cause over today's events - the examination - DESIGN-v2 b.8; its purpose stated, its own act.)"""
        R = build({E1: exam(), E2: act(Kind.SNARE, date=sup(EARLIER)),
                   E3: act(Kind.ABLATION, part_of=sup(E2), relation=sup(ct.PartRelation.ADJUNCT_OF))})
        self.assertEqual(doubted_links(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E1, U, {A.CAUSE})])
        R = build({E1: exam(), E2: act(Kind.SNARE, date=sup(EARLIER)),
                   E3: act(Kind.ABLATION, part_of=sup(E2), relation=sup(ct.PartRelation.ADJUNCT_OF),
                           purpose=STATED_LINK['purpose'])})
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
        # restated at round r3's integration: its part_of unstated beside the snare, the silent-link rule asks it too
        # (DESIGN-v2 b.8); stated not a part, the cause question alone, as before
        self.assertEqual({(item.fact, item.rank) for item in C.bundling('45382', (E3,), R)},
                         {('act_cause', 17), ('act_part', 17)})
        R = build({E1: exam(), E2: act(Kind.SNARE), E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS),
                                                            cause=sup(Cause.ACT_OF_THIS_SESSION), part_of=neg(None))})
        self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E1, U), (C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
        self.assertEqual({(item.fact, item.rank) for item in C.bundling('45382', (E3,), R)}, {('act_cause', 17)})

    def test_d58_a_part_of_naming_the_examination_sets_nothing_apart(self):
        """v1 D58 variant 3: a part_of naming the examination (the session, C-1). v2: it relates the clip to no act -
        no bundle by it; the clip's own cause decides (here none stated: its own act). (Restated at round r3's
        integration: no bundle by the part_of, as before; the cause unstated, the silent-link rule asks it over every
        event - DESIGN-v2 b.8; stated a lesion present before, its own act.)"""
        R = build({E1: exam(), E2: act(Kind.SNARE),
                   E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS), part_of=sup(E1),
                           relation=sup(ct.PartRelation.ADJUNCT_OF))})
        self.assertEqual(doubted_links(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E1, U, {A.CAUSE}),
                                                (C.Rule.PROCEDURAL_ADJUNCT, E2, U, {A.CAUSE})])
        R = build({E1: exam(), E2: act(Kind.SNARE),
                   E3: act(Kind.BLEEDING_CONTROL, purpose=sup(Purpose.HEMOSTASIS), part_of=sup(E1),
                           relation=sup(ct.PartRelation.ADJUNCT_OF), cause=sup(Cause.PRE_EXISTING_LESION))})
        self.assertEqual(C.bundles(R, E3), ())

    def test_a_part_of_in_doubt_asks_the_part(self):
        """A part_of claimed but not established (pass 2 unclear), or an empty slot a doubt names: asked, act_part."""
        for part in (unres(E2), doubted_empty(E2)):
            with self.subTest(part=part.result):
                # its purpose stated (round r3's integration: a silent one opens the silent-link rule's cause arm, b.8)
                R = self.adjunct(part_of=part, purpose=STATED_LINK['purpose'])
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
        has a done biopsy AND its place list is established complete within the upper GI regions (DECISIONS D227 F4,
        P3: every landmark outside them that its places do not cover excluded by a rejected pair control); with its
        list not established complete it is listed in doubt with a coverage question (round 2 read it under on its
        listed places alone); placed outside them, listed unsupported with why."""
        events = {E1: exam(session=sup(X1)), E2: act(Kind.BIOPSY, session=sup(X1)), E3: exam(session=sup(X2)),
                  E4: act(Kind.BIOPSY, session=sup(X2), places=(sup(Landmark.STOMACH),)),
                  E5: act(Kind.FNA, session=sup(X2))}
        sessions_ = {X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.LOWER)}
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E2,)), C.Counted('sel:1', '43232', SessionKind.EUS,
                                                                                   (E5,))]
        cov = C.reconcile(build(events, sessions=sessions_, controls=complete(E4, (Landmark.STOMACH,))), counted,
                          procedure_day=True)
        self.assertEqual(([(act.event, act.rule) for act in cov.bundled], cov.unresolved), ([(E4, None)], []))
        R = build(events, sessions=sessions_)
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(([act.event for act in cov.bundled], [(item.events, item.reason, item.detail)
                                                               for item in cov.unresolved]),
                         ([], [((E4,), C.ItemReason.IN_DOUBT, C.Detail.READ_UNDER_NOT_ESTABLISHED)]))
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
        self.assertEqual(coding['version'], 'cpt-studio-events@3')  # AMENDMENT-2 8.1: event_coding@3, the writer's
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


# --- DECISIONS D287 (B9), D286 ruling F (B13) and G3-14 (B14), D292's E1j ------------------------------------------


class D287ConflictKeys(SimpleTestCase):
    """DECISIONS D287 (G3-28; build list B9 (i)): whenever a fact key names an act, it names facts.established_kind -
    the catalogue kind of its supported kind with its supported purpose, else Kind.OTHER. For an act whose kind is
    silent, unresolved, doubted, contradicted, negated, supported, or a clip supported for hemostasis, each beside a
    broad denial of its kind and with its own status contradicted: every conflict key from coverage.Reader.conflicts,
    act_witnesses and the bundling verdict, and classes' witnesses, is conflict:<established_kind> - and a relation's
    conflict over an act whose label is OTHER is conflict:other, as in evaluate (as built: the claimed kind, else the
    first side, so an act CPT Studio's reading does not establish was "the snare removal" in a key)."""

    KINDS = (('silent', None, None), ('unresolved', unres(Kind.SNARE), None), ('doubted', doubted(Kind.SNARE, Kind.BIOPSY),
                                                                              None),
             ('contradicted', contra(Kind.SNARE, Kind.BIOPSY), None), ('negated', neg(Kind.SNARE), None),
             ('supported', sup(Kind.SNARE), None), ('a clip supported for hemostasis', sup(Kind.CLIP),
                                                    sup(Purpose.HEMOSTASIS)))

    def scene(self, kind, purpose) -> FactSet:
        act_ = act(Kind.SNARE, kind=kind, status=contra(PERFORMED, PLANNED), purpose=purpose)
        if kind is None:
            act_.pop(A.KIND, None)
        part = act(Kind.INJECTION, part_of=sup(E2), relation=sup(ct.PartRelation.LIFT_FOR))
        return build({E1: exam(), E2: act_, E3: denial(Kind.SNARE if purpose is None else Kind.CLIP), E4: part})

    def test_every_conflict_key_names_the_acts_one_label(self):
        from studio.interpretation.engine import classes as CL

        for name, kind, purpose in self.KINDS:
            with self.subTest(name):
                R = self.scene(kind, purpose)
                label = F.established_kind(R, E2)
                wanted = f'conflict:{label.value}'
                keys = {held.fact for held in C.Reader.of(R).conflicts(E2)}
                keys |= {held.fact for held in C.act_witnesses(R, E2) if held.fact.startswith('conflict:')}
                self.assertTrue(keys, name)
                self.assertEqual(keys, {wanted}, name)
                verdict_keys = {held.fact for held in C.verdict(R, E4).held if held.fact.startswith('conflict:')}
                self.assertLessEqual(verdict_keys, {wanted}, name)
                self.assertEqual(label, Q.act_kind(R, E2, ()))  # questions.act_kind: the same derivation
                self.assertEqual(CL._conflict_kind(E2, R), label)

    def test_a_relation_conflict_over_another_act_is_conflict_other(self):
        """B9 (i) and (iv), g3c's shape 2: the act PERFORMED beside the denial of its kind, so pairing gives the relation
        CONTRADICTION (with its own status contradicted the relation is a doubt, and Reader.conflicts' pair branch is
        never read): over an act whose kind is not established the relation's conflict is conflict:other, the act's one
        label, as evaluate's _row_clean keys it (as built: the denial's kind, "the snare removal"); over a supported snare
        it is conflict:snare. Over a supported clip for hemostasis the pair branch names the first kind through which
        the statement concerns it (conflict:clip), as evaluate does (this step's NOTES, question Q-RELKEY)."""
        for name, kind, purpose, wanted in (
                ('silent', None, None, 'conflict:other'), ('unresolved', unres(Kind.SNARE), None, 'conflict:other'),
                ('doubted', doubted(Kind.SNARE, Kind.BIOPSY), None, 'conflict:other'),
                ('contradicted', contra(Kind.SNARE, Kind.BIOPSY), None, 'conflict:other'),
                ('supported', sup(Kind.SNARE), None, 'conflict:snare'),
                ('a clip supported for hemostasis', sup(Kind.CLIP), sup(Purpose.HEMOSTASIS), 'conflict:clip')):
            with self.subTest(name):
                act_ = act(Kind.SNARE, kind=kind, status=sup(PERFORMED), purpose=purpose)
                if kind is None:
                    act_.pop(A.KIND, None)
                R = build({E1: exam(), E2: act_, E3: denial(Kind.SNARE if purpose is None else Kind.CLIP)})
                relation = {held.fact for held in C.Reader.of(R).conflicts(E2) if held.cause == C.RELATION_CONTRADICTION}
                self.assertEqual(relation, {wanted}, name)
                if wanted == 'conflict:other':
                    self.assertIs(F.established_kind(R, E2), Kind.OTHER)

    def test_a_population_of_conflict_keys_names_established_kinds(self):
        """B9 (iii): over the module's generated agreement scenes, every held fact keyed conflict:<k> on an event that
        Reader.conflicts or act_witnesses gives has k equal to that event's established kind."""
        rng = random.Random(20261116)
        checked = 0
        for _ in range(300):
            R = agreement_scene(rng)
            for event_ in R.events:
                for held in (*C.Reader.of(R).conflicts(event_), *C.act_witnesses(R, event_)):
                    if held.fact.startswith('conflict:') and held.subject == event_:
                        self.assertEqual(held.fact, f'conflict:{F.established_kind(R, event_).value}')
                        checked += 1
        self.assertGreater(checked, 50)


class D286DoneWhole(SimpleTestCase):
    """DECISIONS D286 ruling F (G3-13 option (b); refute-r4b-r1 V9R4B1-1): coverage.inclusion_asks_no_code answers no
    unless the including session is done, so beside a C3 whole that is not done - weakened, or told by nothing - the
    EGD keeps its no_proposal item and completeness reads incomplete (as built: no item, "Every documented service has a
    proposal to review."). Beside a done whole nothing moves; no assessed code's reading moves."""
    SEP = (sup(ct.EncounterRelation.SEPARATE_ENCOUNTER),)
    LATER_ = ct.DateRelation.LATER_DATE

    def scene(self, e2=None, part_of=sup(X2)) -> FactSet:
        events = {E1: exam(session=sup(X1))}
        if e2 is not None:
            events[E2] = e2
        return build(events, sessions={X1: session(SessionKind.EGD, part_of=part_of),
                                       X2: {**session(SessionKind.EUS, tract=ct.Tract.UPPER), A.ENCOUNTER: self.SEP}})

    def items(self, R, counted=()):
        cov = C.reconcile(R, list(counted), procedure_day=True)
        comp = C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0,
                              label=lambda s: str(s.id))
        return [(item.reason, item.detail) for item in cov.unresolved if item.session == X1], comp['state']

    def test_c3_completeness_beside_a_whole_not_done(self):
        """refute-r4b-r1's c3_completeness grid and c3_told_by_nothing: the planned EUS's examination weakened (its kind
        or session unresolved, a doubt on its device reading manual), or the EUS told by nothing - the EGD's no_proposal
        item is listed and completeness is incomplete; as filed (the EUS settled: no whole) the same as before; with
        43235 counted the EGD is covered by its own code."""
        planned = dict(status=sup(PLANNED), date=sup(self.LATER_))
        no_proposal = [(C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED)]
        counted = [C.Counted('sel:0', '43235', SessionKind.EGD, (E1,))]
        for name, e2 in (('as filed (settled)', exam(session=sup(X2), **planned)),
                         ('weakened: kind unresolved', exam(session=sup(X2), kind=unres(Kind.EXAMINATION), **planned)),
                         ('weakened: session unresolved', exam(session=unres(X2), **planned)),
                         ('weakened: device doubt reading manual',
                          exam(session=sup(X2), device=doubted(ct.Device.ENDOSCOPE, ct.Device.MANUAL), **planned)),
                         ('told by nothing', None)):
            with self.subTest(name):
                R = self.scene(e2)
                record = C.sessions(R)
                self.assertFalse(record[X2].done)
                self.assertEqual(self.items(R), (no_proposal, 'incomplete'))
                self.assertEqual(self.items(R, counted)[0], [])
                if record[X1].part_of is not None:
                    self.assertFalse(C.inclusion_asks_no_code(record, record[X1], []))

    def test_c3_counted_eus_weakened_row_lists_the_egd(self):
        """c3_counted_eus.py: 43259 counted for the EUS (supporting E2), E2's kind weakened to unresolved: the EGD's
        no_proposal item is listed (as built the C3 whole, not done, swallowed it)."""
        counted = [C.Counted('sel:1', '43259', SessionKind.EUS, (E2,))]
        R = self.scene(exam(session=sup(X2), status=sup(PLANNED), date=sup(self.LATER_), kind=unres(Kind.EXAMINATION)))
        self.assertIn((C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED), self.items(R, counted)[0])

    def test_beside_a_done_whole_the_part_asks_no_code(self):
        """c3_done_whole_control.py: the EUS done today (its examination E2 done, same encounter): X1 asks no code, as
        v1 read it - with nothing counted X2 carries its own item, and with 43259 counted completeness is
        complete_pending_review."""
        R = build({E1: exam(session=sup(X1)), E2: exam(session=sup(X2))},
                  sessions={X1: session(SessionKind.EGD, part_of=sup(X2)),
                            X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
        record = C.sessions(R)
        self.assertTrue(record[X2].done)
        self.assertTrue(C.inclusion_asks_no_code(record, record[X1], []))
        self.assertEqual(self.items(R)[0], [])
        self.assertEqual(self.items(R, [C.Counted('sel:0', '43259', SessionKind.EUS, (E2,))]),
                         ([], 'complete_pending_review'))

    def test_a_generated_pin_over_the_four_states(self):
        """The module's P-MONO at the records ("What a weakening may not release, reconcile keeps listed"), over the
        including session's four states - done today, possibly done (its date open), settled (planned), told by
        nothing - and each C3 claim form: the part asks no code of its own exactly when the whole it is read in is
        done."""
        planned = exam(session=sup(X2), status=sup(PLANNED), date=sup(self.LATER_))
        for state, e2 in (('done', exam(session=sup(X2))), ('possibly done', exam(session=sup(X2), date=unres(ON))),
                          ('settled', planned), ('told by nothing', None)):
            for claim in (sup(X2), unres(X2), doubted_empty(X2)):
                with self.subTest(state=state, claim=claim.result.value):
                    R = self.scene(e2, claim)
                    record = C.sessions(R)
                    asks_none = C.inclusion_asks_no_code(record, record[X1], [])
                    whole = record[X1].part_of
                    self.assertEqual(asks_none, whole is not None and record[whole].done)
                    listed = (C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED) in self.items(R)[0]
                    self.assertEqual(listed, not asks_none)


class D286EmptySlotClaim(SimpleTestCase):
    """DECISIONS D286 (G3-14 option (a); refute-r4b-r1 V9R4B1-2 = r4b Q1): coverage._part_of_session and 4d's
    combination.wholes read one set - a not-established part_of_session's claimed value and options, an empty slot's
    doubt included, never a session nothing names (as built coverage read facts.possibly, true for every session over
    an empty slot, and 4d read such a slot as no claim)."""

    def egd_beside(self, eus, part_of, *, x3=False) -> FactSet:
        events = {E1: exam(session=sup(X1))}
        if eus == 'planned':
            events[E2] = exam(session=sup(X2), status=sup(PLANNED), date=sup(ct.DateRelation.LATER_DATE))
        elif eus == 'earlier':
            events[E2] = exam(session=sup(X2), date=sup(EARLIER))
        elif eus == 'today':
            events[E2] = exam(session=sup(X2))
        elif eus == 'date open':
            events[E2] = exam(session=sup(X2), date=unres(ON))
        eus_record = {**session(SessionKind.EUS, tract=ct.Tract.UPPER), A.ENCOUNTER:
                      (sup(ct.EncounterRelation.SEPARATE_ENCOUNTER),)}
        sessions_ = {X1: session(SessionKind.EGD, part_of=part_of), X2: eus_record}
        if x3:
            sessions_[X3] = eus_record
        return build(events, sessions=sessions_)

    def answers(self, R):
        record = C.sessions(R)[X1]
        mine = ([(record.part_of, True)] if record.part_of is not None
                else [(record.possibly_part_of, False)] if record.possibly_part_of is not None else [])
        return mine, [(whole.session, whole.established) for whole in CB.wholes(R, X1)]

    def test_every_claim_form_gives_one_answer_in_both_modules(self):
        """r4b Q1's grid (g314_claim_probe.py): the EGD's own claim - C3 supported X2, D70 unresolved X2, D70 claimed X1
        with a doubt reading X2, an empty slot a doubt names (X2), contradicted X1|X2 - beside the planned, the earlier,
        the done, the date-open or the told-by-nothing EUS: coverage's whole equals 4d's in every row (as built the
        empty slot's row differed beside the EUS told by nothing). Beside the EUS told by nothing, the empty slot a
        doubt names makes X2 a possible whole in both, and base_within holds 43235 as for the unresolved claim."""
        member = CB.Member('sel:0', '43235', SessionKind.EGD, X1, (E1,), procedural=True, supported=True)
        for eus in ('planned', 'earlier', 'today', 'date open', None):
            for name, part_of in (('C3 supported X2', sup(X2)), ('D70 unresolved X2', unres(X2)),
                                  ('D70 claimed X1, reading X2', doubted(X1, X2)),
                                  ('an empty slot, a doubt naming X2', doubted_empty(X2)),
                                  ('contradicted X1|X2', contra(X1, X2))):
                with self.subTest(eus=eus, claim=name):
                    R = self.egd_beside(eus, part_of)
                    mine, theirs = self.answers(R)
                    self.assertEqual(mine, theirs)
        for name, part_of in (('an empty slot, a doubt naming X2', doubted_empty(X2)), ('unresolved X2', unres(X2))):
            with self.subTest(told_by_nothing=name):
                R = self.egd_beside(None, part_of)
                self.assertEqual(self.answers(R), ([(X2, False)], [(X2, False)]))
                self.assertEqual([(found.wholes, found.established) for found in CB.base_within([member], R)],
                                 [((X2,), False)])

    def test_v9r4b1_2_an_empty_slot_naming_a_settled_session_names_nothing(self):
        """V9R4B1-2's input (g314_emptyclaim_x3.py): the EGD's part_of_session an empty slot whose doubt names only X2, X2
        planned at a later date (settled), a second upper EUS X3 told by nothing - both modules name no whole, and
        event_coding records (None, None) (as built coverage named X3, which nothing names); a doubt naming X2 and X3
        names X3 in both."""
        R = self.egd_beside('planned', doubted_empty(X2), x3=True)
        self.assertEqual(self.answers(R), ([], []))
        coded = C.event_coding(R, C.sessions(R), {})['sessions']['X1']
        self.assertEqual((coded['part_of'], coded['possibly_part_of']), (None, None))
        R = self.egd_beside('planned', doubted_empty(X2, X3), x3=True)
        self.assertEqual(self.answers(R), ([(X3, False)], [(X3, False)]))


def e1j_colon(*, lesions=None, extra=None, controls_=None) -> FactSet:
    """A colonoscopy X1 to the cecum (its examination E1) with the acts ``extra`` and the lesions ``lesions``."""
    events = {E1: exam()}
    events.update(extra or {})
    return build(events, lesions=lesions, controls=controls_)


class D292BiopsyElsewhere(SimpleTestCase):
    """DECISIONS D292's E1j (HOLDS-ANALYSIS.md, THE FINAL FIX LIST item 1; FINAL-V2 4.7, 4.11, 5.1 row 10): whenever a
    biopsy's target.lesion is a pure empty slot and its place list is established, the bundling rule
    biopsy_of_removed_lesion is F when one supported place of the biopsy, for EVERY removal the rule could pair it with,
    is disjoint from each of that removal's places (its target.places together with its target lesion's established
    places), that removal was asked about it by a rejected pair control, and no place pair control asked of the biopsy or
    of those removals is unrejected. The judge's G2 inputs (build-v2/holds/judge/g2/cases_j.py, synthetic, written for
    the G2 set - outside every development set), at the bundling rule."""
    P_ = A.TARGET_PLACES

    def bundled(self, R, biopsy) -> list:
        return [(bundle.rule, bundle.whole, bundle.truth) for bundle in C.bundles(R, biopsy)
                if bundle.rule is C.Rule.BIOPSY_OF_REMOVED_LESION]

    def snare(self, lesion_id, *places, device=ct.Device.COLD_SNARE, kind=Kind.SNARE) -> dict:
        return act(kind, lesion=None if lesion_id is None else sup(lesion_id), places=tuple(sup(p) for p in places),
                   device=sup(device))

    def biopsy(self, *places) -> dict:
        return act(Kind.BIOPSY, places=tuple(sup(p) for p in places), device=sup(ct.Device.COLD_FORCEPS))

    def test_the_g2_releases(self):
        """JS01 (a sigmoid polyp snared; random biopsies of the right and the left colon), JR01 (two left-sided polyps
        snared, each asked about the right colon), JM03 (a removal whose lesion slot is purely silent): the biopsy was done
        in the right colon, apart from every removal and its lesion, each removal asked about it and rejected - no
        bundle (the biopsy code proceeds on its own rows)."""
        sig, des, right, left = (Landmark.SIGMOID_COLON, Landmark.DESCENDING_COLON, Landmark.RIGHT_COLON,
                                 Landmark.LEFT_COLON)
        for name, R, biopsy in (
                ('JS01', e1j_colon(lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(sig,))},
                                   extra={E2: self.snare(L1, sig), E3: self.biopsy(right, left)},
                                   controls_={(E2, self.P_, right): True}), E3),
                ('JR01', e1j_colon(lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(des,)),
                                            L2: lesion(ct.Multiplicity.SINGLE, places=(sig,))},
                                   extra={E2: self.snare(L1, des), E3: self.snare(L2, sig),
                                          E4: self.biopsy(right, left)},
                                   controls_={(E2, self.P_, right): True, (E3, self.P_, right): True}), E4),
                ('JM03', e1j_colon(extra={E2: self.snare(None, sig), E3: self.biopsy(right, left)},
                                   controls_={(E2, self.P_, right): True}), E3)):
            with self.subTest(name):
                self.assertEqual(self.bundled(R, biopsy), [])
                self.assertTrue(C._biopsy_elsewhere(C._Asker(R, biopsy, C.Reader.of(R))))

    def test_the_g2_holds(self):
        """JS02 (the 'elsewhere' place is the removed lesion's own: a polyp spanning the sigmoid and the descending colon,
        its snare filed at the sigmoid), JS03 (the snare's lesion a doubt between two polyps), JR02 (FR-5: a lesion over
        two segments, the EMR filed at one), JR03 (the removed lesion's place a doubt), JR10 (a place control left
        unrejected), the biopsy naming a lesion, a removal place not established, and a synthetic removal: the biopsy
        stays bundled in doubt (U), as built."""
        sig, des, right, left, trans, splenic, hep, rect = (
            Landmark.SIGMOID_COLON, Landmark.DESCENDING_COLON, Landmark.RIGHT_COLON, Landmark.LEFT_COLON,
            Landmark.TRANSVERSE_COLON, Landmark.SPLENIC_FLEXURE, Landmark.HEPATIC_FLEXURE, Landmark.RECTUM)
        single = ct.Multiplicity.SINGLE
        doubtful_place = {L1: {A.PLACES: (doubted(hep, hep, trans),), A.DISTINCT_FROM: (), A.SAME_AS: (),
                               A.MULTIPLICITY: (sup(single),)}}
        named = self.biopsy(right, left)
        named[A.TARGET_LESION] = (sup(L1),)
        cases = (
            ('JS02', e1j_colon(lesions={L1: lesion(single, places=(sig, des))},
                               extra={E2: self.snare(L1, sig, device=ct.Device.HOT_SNARE), E3: self.biopsy(sig, des)},
                               controls_={(E2, self.P_, des): True}), E3),
            ('JS03', e1j_colon(lesions={L1: lesion(single, places=(sig,)), L2: lesion(single, places=(Landmark.CECUM,))},
                               extra={E2: act(Kind.SNARE, lesion=doubted(L1, L1, L2), places=(sup(sig),),
                                              device=sup(ct.Device.COLD_SNARE)), E3: self.biopsy(right, left)},
                               controls_={(E2, self.P_, right): True}), E3),
            ('JR02', e1j_colon(lesions={L1: lesion(single, places=(splenic, trans))},
                               extra={E2: self.snare(L1, splenic, kind=Kind.EMR, device=ct.Device.SNARE),
                                      E3: self.biopsy(trans, splenic)},
                               controls_={(E2, self.P_, trans): True}), E3),
            ('JR03', e1j_colon(lesions=doubtful_place, extra={E2: self.snare(L1, hep), E3: self.biopsy(right, trans)},
                               controls_={(E2, self.P_, trans): True}), E3),
            ('JR10', e1j_colon(lesions={L1: lesion(single, places=(sig,)), L2: lesion(single, places=(rect,))},
                               extra={E2: self.snare(L1, sig, device=ct.Device.HOT_SNARE), E3: self.snare(L2, rect),
                                      E4: self.biopsy(right, left)},
                               controls_={(E2, self.P_, right): True, (E3, self.P_, right): False}), E4),
            ('the biopsy names a lesion', e1j_colon(lesions={L1: lesion(single, places=(sig,))},
                                                    extra={E2: self.snare(L1, sig), E3: named},
                                                    controls_={(E2, self.P_, right): True}), E3),
            ('a removal place not established', e1j_colon(
                lesions={L1: lesion(single, places=(sig,))},
                extra={E2: act(Kind.SNARE, lesion=sup(L1), places=(unres(sig),), device=sup(ct.Device.COLD_SNARE)),
                       E3: self.biopsy(right, left)}, controls_={(E2, self.P_, right): True}), E3),
            ('a synthetic removal beside', build({E1: exam(), E3: self.biopsy(right, left)},
                                                 unlisted=(UnlistedStatement(units=(unit(40),), what=ct.UnlistedWhat.ACT,
                                                                             kind=Kind.SNARE, session=X1),)), E3))
        for name, R, biopsy in cases:
            with self.subTest(name):
                found = self.bundled(R, biopsy)
                self.assertTrue(found, name)  # never F: bundled, or in doubt, as built
                self.assertFalse(C._biopsy_elsewhere(C._Asker(R, biopsy, C.Reader.of(R))), name)
                if name != 'the biopsy names a lesion':  # that one is bundled outright (the removed lesion, T)
                    self.assertTrue(all(truth is U for _rule, _whole, truth in found), (name, found))

    def test_the_read_set_holds_a_lesions_places_and_the_requirements_name_it(self):
        """P-INDEP: E1j reads a whole's target lesion's places, so BUNDLING's read-set holds (lesion, places) (D292;
        REQUIREMENTS_VERSION moves with it, the integration's label)."""
        reads = {(item.role, item.attribute) for item in rq.RULES[rq.Requirement.BUNDLING].reads}
        self.assertIn((rq.Role.LESION, A.PLACES), reads)


UNAPPRAISED = ct.Reason.UNAPPRAISED


class R2BRemovedFindingTests(SimpleTestCase):
    """DECISIONS D294 G1 (refute generality G1; repair round r2): whenever E1j reads a removal's target lesion it reads
    the removed FINDING - every lesion entry a same_as member, in ANY state, may join to that lesion, directly or
    through other entries and in either direction - and it is F only when every entry's places are established
    landmarks, each disjoint from the biopsy's place (the removal asked about it, rejected); an entry whose places are
    not established, or an id the FactSet does not hold, keeps the rule as it was. same_as is read in the hold direction
    only: whatever a member's state it names its value, so no same_as state releases, and (lesion, same_as) stays a
    hold-only read of BUNDLING (CLAIMED and every pass-2 request unchanged). The scenes were written for this round,
    outside every development set: a polyp at the hepatic flexure reaching into the transverse colon, its hot-snare
    removal filed at the flexure and cold-forceps biopsies of the transverse colon naming no lesion (45385, 45380); and
    an antral polyp reaching into the gastric body, snared at the antrum, the body biopsied (43251, 43239)."""

    P_ = A.TARGET_PLACES
    HEP, TRANS, DES = Landmark.HEPATIC_FLEXURE, Landmark.TRANSVERSE_COLON, Landmark.DESCENDING_COLON
    L3, L9 = Id(IdFamily.LESION, 3), Id(IdFamily.LESION, 9)  # L9: an id the FactSet does not hold

    @staticmethod
    def entry(places, same=(), distinct=()) -> dict:
        """A single lesion entry: its places, its same_as and its distinct_from members (a landmark or an id is read
        supported; a Fact as given)."""
        def as_fact(value):
            return value if isinstance(value, Fact) else sup(value)
        return {A.PLACES: tuple(as_fact(place) for place in places), A.SAME_AS: tuple(as_fact(item) for item in same),
                A.DISTINCT_FROM: tuple(as_fact(item) for item in distinct),
                A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}

    def scene(self, lesions, *, biopsy=(Landmark.TRANSVERSE_COLON,)) -> FactSet:
        """E2 a hot-snare removal of L1 filed at the hepatic flexure; E3 cold-forceps biopsies at ``biopsy`` naming no
        lesion; E2 asked about each biopsy place and rejected (it was done at the flexure)."""
        return e1j_colon(lesions=lesions, extra={
            E2: act(Kind.SNARE, lesion=sup(L1), places=(sup(self.HEP),), device=sup(ct.Device.HOT_SNARE)),
            E3: act(Kind.BIOPSY, places=tuple(sup(place) for place in biopsy), device=sup(ct.Device.COLD_FORCEPS))},
            controls_={(E2, self.P_, place): True for place in biopsy})

    @staticmethod
    def elsewhere(R) -> bool:
        return C._biopsy_elsewhere(C._Asker(R, E3, C.Reader.of(R)))

    @staticmethod
    def biopsy_rule(R) -> list:
        return [bundle.truth for bundle in C.bundles(R, E3) if bundle.rule is C.Rule.BIOPSY_OF_REMOVED_LESION]

    # every state a same_as member naming ``value`` can be in (DECISIONS D294 G1: "in any state")
    @staticmethod
    def states(value) -> tuple:
        return (('supported', sup(value)), ('negated, established', neg(value)), ('unresolved', unres(value)),
                ('a negation left open', unres(value, state=State.NEGATED)), ('doubted', doubted(value)),
                ('contradicted', contra(value, value)))

    def split(self, member_on_l1, member_on_l2, partner_places) -> dict:
        """The finding filed as two entries: L1 (the removal's target, at the flexure) and L2 at ``partner_places``,
        joined by the member given on L1 (naming L2) or on L2 (naming L1)."""
        return {L1: self.entry((self.HEP,), same=() if member_on_l1 is None else (member_on_l1,)),
                L2: self.entry(partner_places, same=() if member_on_l2 is None else (member_on_l2,))}

    def test_a_finding_filed_as_two_entries_is_read_whole(self):
        """The rule must change these: the finding reaches the biopsy's place through an entry joined by same_as -
        either direction, every member state (an established negation included: no state narrows the finding), a chain
        through a third entry, a doubt's reading - or an entry of it holds no established place, or names an id the
        FactSet does not hold. E1j keeps the rule as it was: the biopsy stays bundled in doubt (U), never F."""
        cases = []
        for name, member in self.states(L2):
            cases.append((f'L1 -> L2 {name}, L2 spans', self.split(member, None, (self.HEP, self.TRANS))))
            cases.append((f'L1 -> L2 {name}, L2 only the transverse part', self.split(member, None, (self.TRANS,))))
        for name, member in self.states(L1):
            cases.append((f'L2 -> L1 {name}, L2 spans', self.split(None, member, (self.HEP, self.TRANS))))
        cases += [
            ('L2 places unappraised (no act targets it)',
             self.split(sup(L2), None, tuple(fact(Res.UNRESOLVED, place, State.SUPPORTED, reasons=(UNAPPRAISED,))
                                             for place in (self.HEP, self.TRANS)))),
            ('a chain L1 -> L2 -> L3, L3 the transverse part',
             {L1: self.entry((self.HEP,), same=(L2,)), L2: self.entry((self.HEP,), same=(self.L3,)),
              self.L3: self.entry((self.TRANS,))}),
            ("a doubt's reading names the transverse part (L2 or L3)",
             {L1: self.entry((self.HEP,), same=(doubted(L2, L2, self.L3),)), L2: self.entry((self.HEP,)),
              self.L3: self.entry((self.TRANS,))}),
            ('an id the FactSet does not hold', {L1: self.entry((self.HEP,), same=(self.L9,))}),
        ]
        for name, lesions in cases:
            with self.subTest(name):
                R = self.scene(lesions)
                self.assertFalse(self.elsewhere(R))
                self.assertEqual(self.biopsy_rule(R), [U])

    def test_a_finding_whose_every_entry_lies_apart_still_releases(self):
        """The boundary the rule must leave alone: every entry of the finding established at the flexure (either
        direction, every member state, a chain), and two entries that are NOT one finding (a distinct_from, no link at
        all) with the other polyp in the transverse colon - the biopsy was done where no removal was, as built."""
        cases = []
        for name, member in self.states(L2):
            cases.append((f'L1 -> L2 {name}', self.split(member, None, (self.HEP,))))
        for name, member in self.states(L1):
            cases.append((f'L2 -> L1 {name}', self.split(None, member, (self.HEP,))))
        cases += [
            ('a chain L1 -> L2 -> L3, every entry at the flexure',
             {L1: self.entry((self.HEP,), same=(L2,)), L2: self.entry((self.HEP,), same=(self.L3,)),
              self.L3: self.entry((self.HEP,))}),
            ('L1 distinct_from L2, L2 in the transverse colon',
             {L1: self.entry((self.HEP,), distinct=(L2,)), L2: self.entry((self.TRANS,))}),
            ('two entries, no link, L2 in the transverse colon', {L1: self.entry((self.HEP,)),
                                                                  L2: self.entry((self.TRANS,))}),
        ]
        for name, lesions in cases:
            with self.subTest(name):
                R = self.scene(lesions)
                self.assertTrue(self.elsewhere(R))
                self.assertEqual(self.biopsy_rule(R), [])

    def test_no_weakening_of_the_finding_releases_it(self):
        """9.4's weakenings on the held split (L1 -> L2 supported, L2 spanning): the same_as member made unresolved,
        doubted or a contradiction, a place of either entry made unresolved, the removal's control left unrejected -
        each keeps E1j from releasing."""
        lesions = self.split(sup(L2), None, (self.HEP, self.TRANS))
        self.assertFalse(self.elsewhere(self.scene(lesions)))
        weakened = {
            'same_as unresolved': self.split(unres(L2), None, (self.HEP, self.TRANS)),
            'same_as doubted': self.split(doubted(L2, L2, self.L3), None, (self.HEP, self.TRANS)),
            'same_as contradicted': self.split(contra(L2, self.L3), None, (self.HEP, self.TRANS)),
            "L2's transverse place unresolved": self.split(sup(L2), None, (self.HEP, unres(self.TRANS))),
            "L1's place unresolved": {L1: self.entry((unres(self.HEP),), same=(L2,)),
                                      L2: self.entry((self.HEP, self.TRANS))},
        }
        for name, weak in weakened.items():
            with self.subTest(name):
                self.assertFalse(self.elsewhere(self.scene(weak)))
        import dataclasses
        held = self.scene(lesions)
        open_control = dataclasses.replace(held, pair_controls={key: False for key in held.pair_controls})
        self.assertFalse(self.elsewhere(open_control))

    def test_the_finding_reads_every_member_state_and_its_reach(self):
        """_SameAs.finding: the component of the graph of every id a member names in ANY state (_any_state_ids) - a
        negation's value, a doubt's readings, a contradiction's sides, every lesion for a silent member - directly or
        through other entries, either direction; the bundling identity's own graph (_member_ids) is unchanged."""
        R = build({E1: exam()}, lesions={L1: self.entry((self.HEP,), same=(neg(L2),)), L2: self.entry((self.HEP,)),
                                         self.L3: self.entry((self.TRANS,), same=(contra(L2, self.L9),))})
        same = C._SameAs(R)
        self.assertEqual(same.finding(L1), frozenset({L1, L2, self.L3, self.L9}))
        self.assertEqual(same.finding(self.L9), same.finding(L1))  # one component, either direction
        self.assertFalse(same.one_finding(L1, L2))  # the negation joins nothing for the bundling identity
        self.assertNotIn(L2, C._walk(C._same_as_graph(R), (L1,)))
        silent = build({E1: exam()}, lesions={L1: self.entry((self.HEP,), same=(SILENT,)),
                                              L2: self.entry((self.TRANS,)), self.L3: self.entry((self.DES,))})
        self.assertEqual(C._SameAs(silent).finding(L1), frozenset({L1, L2, self.L3}))
        alone = build({E1: exam()}, lesions={L1: self.entry((self.HEP,)),
                                             L2: self.entry((self.TRANS,), distinct=(L1,))})
        self.assertEqual(C._SameAs(alone).finding(L1), frozenset({L1}))

    def test_through_the_engine_the_held_code_and_its_boundary(self):
        """Through engine/assess on the EGD scene (tests/v2/evaluate_fixtures): the antral polyp L1 same_as L2, which
        reaches into the gastric body; 43251 a hot-snare removal of L1 at the antrum, 43239 cold-forceps biopsies of the
        body naming no lesion, the snare asked about the body and rejected. Held: 43239 in doubt (act_target), 43251
        READY. Its boundary: L2 at the antrum alone - 43239 READY."""
        from tests.v2 import evaluate_fixtures as EF
        from tests.v2 import test_assess as TA
        antrum, body = Landmark.GASTRIC_ANTRUM, Landmark.GASTRIC_BODY

        def egd(partner_places):
            doc = EF.egd()
            doc.lesion(1, lesion_places=[sup(antrum)], multiplicity=sup(ct.Multiplicity.SINGLE), same_as=[sup(L2)])
            doc.lesion(2, lesion_places=[sup(place) for place in partner_places],
                       multiplicity=sup(ct.Multiplicity.SINGLE))
            doc.act(2, Kind.SNARE, lesion=sup(L1), places=[sup(antrum)], device=sup(ct.Device.HOT_SNARE))
            doc.act(3, Kind.BIOPSY, places=[sup(body)], device=sup(ct.Device.COLD_FORCEPS))
            doc.controls[(E2, A.TARGET_PLACES, body)] = True
            found = TA.by_code(TA.run(doc.build(), ('43251', 2), ('43239', 3)))
            return {code: (item.status.value, None if item.item is None else item.item.held.fact)
                    for code, item in found.items()}

        self.assertEqual(egd((antrum, body)),
                         {'43251': ('ready', None), '43239': ('needs_clarification', 'act_target')})
        self.assertEqual(egd((antrum,)), {'43251': ('ready', None), '43239': ('ready', None)})

    def test_same_as_stays_a_hold_only_read(self):
        """The request invariant (D294): E1j reads same_as in the hold direction only, so BUNDLING's read of (lesion,
        same_as) stays on the hold path - no control, no claim and no pass-2 request changes - and (lesion, places)
        stays the READY-path read D292's E1j added."""
        paths = {(item.role, item.attribute): item.paths for item in rq.RULES[rq.Requirement.BUNDLING].reads}
        self.assertEqual(paths[(rq.Role.LESION, A.SAME_AS)], frozenset({rq.Path.HOLD}))
        self.assertEqual(paths[(rq.Role.LESION, A.PLACES)], frozenset({rq.Path.READY}))


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
        # combination (step 4d): D227's one "session done" and D231's synthetic act, read from the reference itself
        self.assertEqual(imported, {'anatomy', 'catalogue', 'combination', 'pairing', 'reading', 'facts',
                                    'requirements'})

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
        (act_cause); stated as this session's act with the snare as cause_event - bundled.

        Restated at round r3's integration: its cause and its part_of unstated - ASKED here, by the silent-link rule
        (DESIGN-v2 b.8, DECISIONS D308 Q-B: the procedure-caused bleeding control), U, never explained; both stated -
        its link to nothing - its own act, as before."""
        R = polypectomy(hemoclips())
        self.assertEqual(doubted_links(R, E3), SILENT_LINKS)
        self.assertEqual({(item.fact, item.attribute) for item in C.verdict(R, E3).held},
                         {('act_cause', A.CAUSE), ('act_part', A.PART_OF)})
        self.assertEqual(C.bundles(polypectomy(hemoclips(part_of=neg(None), cause=sup(Cause.PRE_EXISTING_LESION))), E3),
                         ())
        R = polypectomy(hemoclips(cause=unres(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2)))
        self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
        # its part_of unstated beside the snare: the silent-link rule asks it too (round r3, DESIGN-v2 b.8)
        self.assertEqual({(item.fact, item.attribute) for item in C.verdict(R, E3).held},
                         {('act_cause', A.CAUSE), ('act_part', A.PART_OF)})
        R = polypectomy(hemoclips(cause=sup(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2)))
        self.assertEqual(C.bundled(R, E3).whole, E2)

    def test_an_ablation_of_the_resection_margins_with_no_part_of(self):
        """v1 (D41) asked it. v2: nothing relates it to the EMR - no part_of, no cause - so it is its own act.

        Restated at round r3's integration: nothing STATES its relation to the EMR - its part_of and its cause silent,
        its purpose silent (so possibly hemostasis) - so the silent-link rule asks them (DESIGN-v2 b.8, DECISIONS D308
        Q-B), U; Fable's proven part-link answer releases it. Its link stated (done in its own right, a treatment): its
        own act, as v2 had it."""
        R = build({E1: exam(), E2: emr(), E3: act(Kind.ABLATION)}, lesions=CECAL)
        self.assertEqual(doubted_links(R, E3), SILENT_LINKS)
        self.assertEqual(C.bundles(build({E1: exam(), E2: emr(), E3: act(Kind.ABLATION, **STATED_LINK)},
                                         lesions=CECAL), E3), ())

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
        # restated at round r3's integration: never bundled INTO the removal - the removal (and the examination) appear
        # only as the silent-link rule's U by the control's unstated cause (DESIGN-v2 b.8), never T; the one T is E4
        self.assertEqual([(bundle.whole, bundle.truth, {doubt.attribute for doubt in bundle.doubts})
                          for bundle in C.bundles(R, E3) if bundle.whole != E4], [(E1, U, {A.CAUSE}), (E2, U, {A.CAUSE})])

    def test_d58_places_never_decide(self):
        """v1's D58 variants (the distal sigmoid beside the rectosigmoid, the proximal transverse beside the hepatic
        flexure: adjacent, asked) and its controls (the descending colon, two steps away: READY): in v2 the clip's
        place decides nothing - with its cause unstated it is its own act everywhere; caused by the snare, bundled
        everywhere. (Restated at round r3's integration: with its cause and part_of unstated it is ASKED everywhere by
        the silent-link rule, DESIGN-v2 b.8 - the same bundles at every place; with them stated, its own act
        everywhere.)"""
        for place in (Landmark.SIGMOID_COLON, Landmark.TRANSVERSE_COLON, Landmark.DESCENDING_COLON,
                      Landmark.ASCENDING_COLON, Landmark.ANASTOMOSIS):
            with self.subTest(place=place):
                R = polypectomy(hemoclips(places=(sup(place),)))
                self.assertEqual(doubted_links(R, E3), SILENT_LINKS)
                R = polypectomy(hemoclips(places=(sup(place),), part_of=neg(None),
                                          cause=sup(Cause.PRE_EXISTING_LESION)))
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
        R = self.eus(act(Kind.INJECTION, purpose=STATED_LINK['purpose']))  # the EUS lists the injection: its own act,
        self.assertEqual((C.eus_unlisted(R, E3), C.reportable(R, E3)), ((False, False), True))  # reportable as one
        # restated at round r3's integration: its purpose UNSTATED, it may treat bleeding the EUS caused - the
        # silent-link rule's doubt (DESIGN-v2 b.8): listed, in doubt, never bundled silently
        R = self.eus(act(Kind.INJECTION))
        self.assertEqual((C.eus_unlisted(R, E3), doubted_links(R, E3)),
                         ((False, True), [(C.Rule.PROCEDURAL_ADJUNCT, E1, U, {A.CAUSE})]))
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
    not stated) left 45388 READY. It is now POSSIBLY the removal's adjunct: asked (act_part), never explained -
    DECISIONS D221 rules it so where the two acts may name the same lesion (AdjunctAsksOnlyForTheSameLesion pins the
    rest)."""

    def test_dq1_an_adjunct_of_the_removed_lesion_is_asked_never_explained(self):
        # restated at round r3's integration: the ablations state their link (STATED_LINK), so D221's lesion arm is what
        # they read; the hemostatic clip treats bleeding, so its UNSTATED cause - which D221's own exception reads, and so
        # stays unstated here - is the silent-link rule's doubt over every event too (DESIGN-v2 b.8): the examination's
        # bundle beside the snare's
        adjunct, examination = (C.Rule.PROCEDURAL_ADJUNCT, E2, U), (C.Rule.PROCEDURAL_ADJUNCT, E1, U)
        for name, part, whole, expected in (
                ('ablation beside the EMR', act(Kind.ABLATION, **STATED_LINK, lesion=sup(L1)), emr(), [adjunct]),
                ('hemostatic clip beside the snare', hemoclips(lesion=sup(L1), part_of=neg(None)),
                 act(Kind.SNARE, lesion=sup(L1)), [examination, adjunct]),
                ('a lesion only possibly the same', act(Kind.ABLATION, **STATED_LINK, lesion=unres(L1)), emr(),
                 [adjunct])):
            with self.subTest(name):
                R = build({E1: exam(), E2: whole, E3: part}, lesions=CECAL)
                self.assertEqual(rules(R, E3), expected)
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
                ('no lesion stated (round 1 reading kept)', act(Kind.ABLATION, **STATED_LINK), {}),
                ('another lesion, established apart', act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2)),
                 lesion_controls(E3, L2, E2, L1)),
                # (restated at round r3's integration: each control states the rest of its link - DESIGN-v2 b.8 reads an
                # unstated part_of, or an unstated cause where the part may treat bleeding, as a doubt)
                ('bleeding the lesion had before (cause pre-existing: 4.3 CAUSE decides)',
                 hemoclips(lesion=sup(L1), cause=sup(Cause.PRE_EXISTING_LESION), part_of=neg(None)), {}),
                ('stated not part of the EMR', act(Kind.ABLATION, lesion=sup(L1), part_of=neg(E2),
                                                   purpose=STATED_LINK['purpose']), {}),
                ('a marking injection (no adjunct kind of v1)', act(Kind.INJECTION, lesion=sup(L1),
                                                                    purpose=sup(Purpose.MARKING), part_of=neg(None)),
                 {})):
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
         E4: act(Kind.SNARE, session=sup(X2), lesion=sup(L1)), E5: act(Kind.ABLATION, **STATED_LINK, session=sup(X2), lesion=sup(L1)),
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
    # repair r4b round 3 (DECISIONS D231's coverage half): a biopsy beside a snare kept as an unlisted doubt (C1), and an
    # EGD told only through a done biopsy beside an examination kept as an unlisted act (C2)
    'synthetic_acts': (lambda: build(
        {E1: exam(session=sup(X1)), E3: act(Kind.BIOPSY, session=sup(X1), lesion=sup(L1)),
         E4: act(Kind.BIOPSY, session=sup(X2))},
        sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)},
        lesions={L1: lesion(ct.Multiplicity.SINGLE)},
        unlisted=(UnlistedStatement(units=(unit(7),), what=ct.UnlistedWhat.DOUBT, kind=Kind.SNARE, session=X1),
                  UnlistedStatement(units=(unit(8),), what=ct.UnlistedWhat.ACT, kind=Kind.EXAMINATION, session=X2))),
        [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]),
}


def row_7_holds(R: FactSet, counted) -> int:
    """The counted codes 4.3 row 7 holds in R - a code whose supporting or read event is filed under a session that is
    not done ("the session is done: its examination, when it has one, passes 2-5"; step 4a's _row_done) - each an open
    question of the assessment (4.4), which keeps completeness incomplete. DECISIONS D227's one "session done" (step
    4d's session_done) makes a session whose established examination is not done a session not done, whatever its
    acts: reconcile then lists none of its acts, and its codes' questions carry its completeness."""
    sessions_ = C.sessions(R)
    return sum(1 for item in counted if any(
        C.filed(R, event) in sessions_ and not sessions_[C.filed(R, event)].done
        for event in tuple(item.supporting) + tuple(item.read)))


class MonotoneRecords(SimpleTestCase):
    """9.4 P-MONO at the records base_included reads, over two sessions and the weakenings round 1's Monotone did not
    make (refute-4b-r1 C1, H1, H2): weakening a fact never shrinks a session's reportable-or-doubted entries, never
    turns a verdict that is not T into T, never un-doubts an act, and never turns an incomplete completeness complete -
    with NO open question counted (refute-r4b-r1 R5): a weakening that leaves a session not done (D227's one "session
    done") keeps its acts listed by reconcile itself, whatever step 4a's row 7 holds. Round 1 of this repair needed
    row 7's open questions (row_7_holds) for 24 such weakenings; they are counted here too, as a second reading."""

    def test_p_mono_over_two_sessions_and_contradictions(self):
        checked = 0
        for name, (scene, counted) in RECORD_SCENES.items():
            R = scene()
            before = entries(R)
            verdicts = {event: (C.verdict(R, event).truth, C.doubted(R, event)) for event in R.events}
            cov = C.reconcile(R, counted, procedure_day=True)
            self.assertEqual(row_7_holds(R, counted), 0)
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
                    for open_questions in (0, row_7_holds(weak, counted)):
                        self.assertEqual(C.completeness(cov, C.sessions(weak), open_questions=open_questions,
                                                        provider_ok=True, conflicts=0, label=label)['state'],
                                         'incomplete')
                    checked += 1
        self.assertGreater(checked, 300)  # 281 measured before the synthetic_acts scene


# --- repair r4b (DECISIONS D221; D227's 4b items F2, F3, F4, F8; D229's F6, F7), each pinned by a test --------------


MANUAL, ENDOSCOPE = ct.Device.MANUAL, ct.Device.ENDOSCOPE
NURSING, OTHER_CLINICIAN = ct.Owner.NURSING, ct.Performer.OTHER_CLINICIAN
X9 = Id(IdFamily.SESSION, 9)  # a session id the FactSet does not hold (step 4d's request REQ2)
L3 = Id(IdFamily.LESION, 3)


def session_record(kind) -> dict:
    """A session's facts with ``kind`` its kind fact (None: an empty slot)."""
    return {A.KIND: (kind,) if kind is not None else (), A.REACHED: (), A.DEVICE_REACHED: (), A.STATIONS: ()}


def agreement_scene(rng: random.Random) -> FactSet:
    """One generated FactSet for D227's agreement (refute-4b-r2 F2; step 4d's request REQ2): 1-3 sessions whose kind is
    supported, not established or an empty slot; 1-5 events of an examination's or an act's kind; each of their kind,
    status, session, date relation, performer, entry and device facts supported (most often), negated, not established
    (unresolved, a doubt with readings, contradicted, a negation left open) or an empty slot; session facts naming a
    session of the FactSet or X9, one it does not hold - as the value, a reading or supported; devices manual or not.
    And 0-2 kept unlisted entries (DECISIONS D231 rows 1 and 2, coverage's C2; step 4d's request R1 (c)): an act, a
    doubt or a denial, of kind examination, another kind or none, carded to a session of the FactSet, to X9 or to
    none - so the agreement covers the synthetic examination 4d's session_done reads."""
    ids = [X1, X2, X3][:rng.randint(1, 3)]
    families = [sup(SessionKind.EGD), sup(SessionKind.COLONOSCOPY), sup(SessionKind.EUS), sup(SessionKind.ERCP),
                sup(SessionKind.FLEX_SIG), unres(SessionKind.COLONOSCOPY),
                doubted(SessionKind.EGD, SessionKind.EGD, SessionKind.EUS),
                contra(SessionKind.EGD, SessionKind.ENTEROSCOPY), None]
    sessions_ = {session_id: session_record(rng.choice(families)) for session_id in ids}
    events = {}
    for number in range(1, rng.randint(1, 5) + 1):
        a, b = rng.choice(ids), rng.choice(ids)
        if rng.random() < 0.5:  # half the events done in a session of the FactSet: done sessions are not rare
            events[Id(IdFamily.EVENT, number)] = event(
                kind=rng.choice([sup(Kind.EXAMINATION), sup(Kind.EXAMINATION), sup(Kind.BIOPSY), sup(Kind.SNARE),
                                 sup(Kind.FNA)]),
                session=sup(a), status=rng.choice([sup(PERFORMED), sup(PERFORMED), sup(ATTEMPTED)]), date=sup(ON),
                performer=sup(TEAM), entry=sup(DOC), device=rng.choice([None, None, sup(MANUAL), sup(ENDOSCOPE)]))
            continue
        events[Id(IdFamily.EVENT, number)] = event(
            kind=rng.choice([sup(Kind.EXAMINATION)] * 4 + [
                sup(Kind.BIOPSY), sup(Kind.FNA), sup(Kind.SNARE), unres(Kind.EXAMINATION),
                doubted(Kind.BIOPSY, Kind.EXAMINATION), contra(Kind.EXAMINATION, Kind.BIOPSY),
                neg(Kind.EXAMINATION), neg(Kind.BIOPSY), None]),
            session=rng.choice([sup(a)] * 4 + [
                unres(a), doubted_empty(a, b), doubted(a, b), contra(a, b), neg(a), unres(a, state=State.NEGATED),
                doubted(a, a, state=State.NEGATED), sup(X9), unres(X9), doubted(a, X9), contra(a, X9),
                doubted_empty(X9), None]),
            status=rng.choice([sup(PERFORMED)] * 4 + [
                sup(ATTEMPTED), sup(PLANNED), neg(PERFORMED), unres(PERFORMED), doubted(PERFORMED),
                contra(PERFORMED, PLANNED), None]),
            date=rng.choice([sup(ON)] * 4 + [sup(EARLIER), unres(ON), neg(ON), doubted(ON, ON, EARLIER), None]),
            performer=rng.choice([sup(TEAM)] * 4 + [sup(OTHER_CLINICIAN), unres(TEAM), neg(TEAM), None]),
            entry=rng.choice([sup(DOC)] * 4 + [sup(NURSING), unres(DOC), None]),
            device=rng.choice([None] * 3 + [sup(MANUAL), sup(MANUAL), sup(ENDOSCOPE), unres(MANUAL), neg(MANUAL),
                                            doubted(ENDOSCOPE, MANUAL)]))
    entries = tuple(UnlistedStatement(units=(unit(40 + index),),
                                      what=rng.choice([ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT,
                                                       ct.UnlistedWhat.DENIAL]),
                                      kind=rng.choice([Kind.EXAMINATION, Kind.EXAMINATION, Kind.SNARE, None]),
                                      session=rng.choice([*ids, X9, None]))
                    for index in range(rng.choice([0, 0, 1, 2])))
    return build(events, sessions=sessions_, unlisted=entries)


class OneSessionDone(SimpleTestCase):
    """DECISIONS D227 (refute-4b-r2 F2; w34 O18): "session done" has one derivation - step 4d's
    combination.session_done, the reference, E13's digital examination (a device claiming manual) excepted (D69) - and
    coverage's done_examinations, possible_examinations and session record give its answer on every FactSet. This class
    reads engine/combination.py read only."""

    def test_e13_a_digital_examination_is_no_session(self):
        """refute-4b-r2 q2: a colonoscopy X1 and a digital rectal examination E2 in it (kind examination, device
        supported manual, rows 2-5 supported). The colonoscope's examination E1 is the session's one examination: (a)
        performed, the session done; (b) begun and not completed, the session done and INCOMPLETE - its no_proposal
        item worded so (v1's "(documented as incomplete)"), quoting E1 - where round 2, reading the digital examination
        as a second one, recorded it performed and unresolved; (c) 45378 counted on E1, nothing listed. The extent
        question quotes the colonoscope's examination alone."""
        for status, incomplete, detail in ((sup(PERFORMED), False, C.Detail.SESSION_PERFORMED),
                                           (sup(ATTEMPTED), True, C.Detail.SESSION_INCOMPLETE)):
            with self.subTest(status=status.value):
                R = build({E2: exam(device=sup(MANUAL)), E1: exam(status=status)})
                record = C.sessions(R)[X1]
                self.assertEqual((record.examinations, record.possible, record.event, record.unresolved, record.done,
                                  record.incomplete), ((E1,), (), E1, False, True, incomplete))
                self.assertTrue(CB.session_done(R, X1))
                coded = C.event_coding(R, C.sessions(R), {})['sessions']['X1']
                self.assertEqual((coded['event'], coded['examinations'], coded['possible'], coded['incomplete'],
                                  coded['unresolved']), ('E1', ['E1'], [], incomplete, False))
                cov = C.reconcile(R, [], procedure_day=True)
                self.assertEqual([(item.reason, item.detail, item.evidence) for item in cov.unresolved],
                                 [(C.ItemReason.NO_PROPOSAL, detail, (unit(1),))])
                self.assertEqual([service.item.spans for service in C.service_extent_questions(R, C.sessions(R))],
                                 [(unit(1),)])
        R = build({E2: exam(device=sup(MANUAL)), E1: exam()})
        self.assertEqual(C.reconcile(R, [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))],
                                     procedure_day=True).unresolved, [])

    def test_e13_a_digital_examination_alone_makes_no_session_done(self):
        """A session told only through a digital examination has no examination, none left open, and no act that makes
        it done (4d alike) - a device that CLAIMS manual (supported, unresolved, a doubt reading manual) included
        (DECISIONS D253, QE13 option (a): 4d's session_done reads combination._digital); a device that claims no manual
        (negated, another device, silent) leaves the examination the session's own."""
        for device in (sup(MANUAL), unres(MANUAL), doubted(ENDOSCOPE, MANUAL)):
            with self.subTest(device=(device.result, device.value)):
                R = build({E2: exam(device=device)})
                record = C.sessions(R)[X1]
                self.assertEqual((record.examinations, record.possible, record.event, record.done),
                                 ((), (), None, False))
                self.assertFalse(CB.session_done(R, X1))
        for device in (neg(MANUAL), sup(ENDOSCOPE), None):
            with self.subTest(device=None if device is None else (device.result, device.value)):
                R = build({E2: exam(device=device)})
                record = C.sessions(R)[X1]
                self.assertEqual((record.examinations, record.event, record.done, CB.session_done(R, X1)),
                                 ((E2,), E2, True, True))

    def test_e13_the_no_proposal_item_never_quotes_a_digital_examination(self):
        """refute-r4b-r1 R4 (p6): a colonoscopy told through its acts - a digital rectal examination E2 first in the
        document, then a done cold snare E3 - and no code proposed. The session is done by the snare (E13: the digital
        examination is no session examination), and its no_proposal item quotes the snare, never the digital
        examination (round 1 of this repair claimed it; no test pinned it)."""
        R = build({E2: exam(device=sup(MANUAL)), E3: act(Kind.SNARE)})
        record = C.sessions(R)[X1]
        self.assertEqual((record.examinations, record.event, record.done), ((), None, True))
        cov = C.reconcile(R, [], procedure_day=True)
        self.assertEqual([(item.reason, item.detail, item.evidence) for item in cov.unresolved],
                         [(C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED, (unit(3),))])

    def test_an_established_examination_not_done_leaves_its_session_not_done(self):
        """4.3 row 7 ("its examination, when it has one, passes 2-5"), 4d's reading: a colonoscopy whose established
        examination's date is not established is not done, whatever its acts - its done snare does not make it done
        (round 2 read any done member); every code of it is held by row 7 (row_7_holds). Its done snare, which no
        counted code reads, stays listed as a done session's act would be (refute-r4b-r1 R5, question QR5-1: round 1
        of this repair listed nothing, leaving completeness to row 7's questions, which step 4a may not raise), and
        no no_proposal item is listed for it. Told only through its acts, a session is done by a done act unless an
        event that may be its examination is left open (D121, D135)."""
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]
        R = build({E1: exam(date=unres(ON)), E2: act(Kind.SNARE)})
        self.assertEqual((C.sessions(R)[X1].done, CB.session_done(R, X1), row_7_holds(R, counted)), (False, False, 1))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.reason, item.events) for item in cov.unresolved], [(C.ItemReason.NOT_COVERED, (E2,))])
        self.assertEqual((cov.covered, cov.not_listed), ({}, []))
        R = build({E1: exam(), E2: act(Kind.SNARE)})
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.reason, item.events) for item in cov.unresolved], [(C.ItemReason.NOT_COVERED, (E2,))])
        R = build({E2: act(Kind.SNARE)})  # an act-only session
        self.assertEqual((C.sessions(R)[X1].done, CB.session_done(R, X1)), (True, True))
        R = build({E2: act(Kind.SNARE), E3: exam(session=None, date=unres(ON))})  # an examination left open
        self.assertEqual((C.sessions(R)[X1].possible, C.sessions(R)[X1].done, CB.session_done(R, X1)),
                         ((E3,), False, False))

    def agree(self, R: FactSet) -> dict:
        """D227's agreement on one FactSet, every session: done_examinations, possible_examinations and the session
        record against 4d's reading (combination._examinations, _may_be_examination_of and session_done, read only;
        the examinations left open, and none in a session whose examination is established not done today -
        DECISIONS D269's exemption, which 4d's session_possibly_done makes of every act possibly in it, whatever its
        date or session slot: p2_reference_left_open, which round w8r read with D256 P2's letter); a session with an
        examination left open is one 4d reads possibly done, and one 4d reads established not done today is not;
        returns what the FactSet exercised."""
        view = RD.Reading(R)
        sessions_ = C.sessions(R)
        coded = C.event_coding(R, sessions_, {})['sessions']
        seen = {'done': 0, 'not done': 0, 'act only done': 0, 'established not done': 0, 'left open': 0,
                'manual': 0, 'dangling': 0, 'synthetic left open': 0, 'synthetic beside an examination': 0}
        for session in R.sessions:
            done = tuple(event for event in CB._examinations(R, session) if RD.done(view, event))
            left_open = p2_reference_left_open(R, session)
            # D231 row 1 (C2): 4d's synthetic examinations, read only in a session with no established examination
            synthetic = CB.synthetic_examinations(R, session) if not CB._examinations(R, session) else ()
            record = sessions_[session]
            self.assertEqual(C.done_examinations(R, session), done)
            self.assertEqual(C.possible_examinations(R, session), left_open)
            self.assertEqual(C.possible_unlisted_examinations(R, session), synthetic)
            self.assertEqual((record.examinations, record.possible, record.possible_unlisted),
                             (done, left_open, synthetic))
            self.assertEqual(record.done, CB.session_done(R, session))
            self.assertEqual(record.event is not None, len(done) == 1 and not left_open)
            if record.event is not None:
                self.assertEqual(record.event, done[0])
                self.assertTrue(CB.session_done(R, session))
            self.assertEqual(record.unresolved, len(done) + len(left_open) + len(synthetic) >= 2)
            seen['synthetic left open'] += bool(synthetic)
            seen['synthetic beside an examination'] += bool(CB._examinations(R, session)
                                                            and CB.synthetic_examinations(R, session))
            self.assertEqual(record.incomplete, bool(done) and all(F.holds(F.fact(R, event, A.STATUS), ATTEMPTED)
                                                                   for event in done))
            self.assertEqual((coded[str(session)]['done'], coded[str(session)]['event'],
                              coded[str(session)]['examinations'], coded[str(session)]['possible'],
                              coded[str(session)]['incomplete'], coded[str(session)]['unresolved']),
                             (record.done, None if record.event is None else str(record.event),
                              [str(event) for event in done], [str(event) for event in left_open], record.incomplete,
                              record.unresolved))
            established = CB._examinations(R, session)
            if left_open:
                self.assertTrue(CB.session_possibly_done(R, session))
            if CB.not_done_today(R, session):  # DECISIONS D269
                self.assertEqual((record.possible, record.done, CB.session_possibly_done(R, session)),
                                 ((), False, False))
            seen['done' if record.done else 'not done'] += 1
            seen['act only done'] += bool(record.done and not established)
            seen['established not done'] += bool(established and not done)
            seen['left open'] += bool(left_open)
        seen['manual'] += any(F.holds(F.fact(R, event, A.TECHNIQUE_DEVICE), MANUAL)
                              and F.holds(F.fact(R, event, A.KIND), Kind.EXAMINATION) for event in R.events)
        seen['dangling'] += any(X9 in (F.fact(R, event, A.SESSION).value, *F.fact(R, event, A.SESSION).options)
                                for event in R.events)
        return seen

    def test_d227_coverage_agrees_with_combination_over_generated_factsets(self):
        """The cross-module test D227 asks for: 4,000 generated FactSets (agreement_scene, seeded), every session of
        each. The counts assert that every arm was exercised - done and not done, done by an act alone, an
        established examination not done, an examination left open, a digital examination, a dangling session id, a
        synthetic examination left open in a session told only through its acts and one beside an established
        examination, where it adds nothing (DECISIONS D231 row 1, C2; D232)."""
        rng = random.Random(20261113)
        totals: dict = {}
        for _ in range(4000):
            for name, count in self.agree(agreement_scene(rng)).items():
                totals[name] = totals.get(name, 0) + count
        for name in totals:
            with self.subTest(arm=name):
                self.assertGreater(totals[name], 100, totals)

    def test_d227_the_sessions_4d_reads_for_an_examination(self):
        """4d's membership is the reference's (its possible_sessions): an examination whose session fact is an
        established negation ("not in X1") may still be X1's examination (left open: X1 not done), as an id naming no
        session of the FactSet may be any session's (D227 R2-2); sessions_of keeps every other session for the
        established negation (question QR4-2)."""
        for found in (neg(X1), sup(X9), unres(X9), doubted(X2, X9)):
            with self.subTest(session=(found.result, found.value)):
                R = build({E2: act(Kind.SNARE, session=sup(X1)), E3: exam(session=found, date=unres(ON))},
                          sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)})
                self.assertEqual((C.possible_examinations(R, X1), C.sessions(R)[X1].done, CB.session_done(R, X1)),
                                 ((E3,), False, False))
        R = build({E3: act(Kind.BIOPSY, session=neg(X1))},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)})
        self.assertEqual(C.sessions_of(R, E3), frozenset({X2}))


def eus_beside_egd(eus_biopsy: dict, *, denial_=False, controls_=None, read=()) -> tuple[FactSet, list]:
    """refute-4b-r2 q3 and q6: an EGD X1 (its done examination E1, a done gastric biopsy E3, 43239 counted on E3) and an
    upper EUS X2 (its done examination E2, 43259 counted on E2, reading ``read`` besides) with a done forceps biopsy
    E4 (``eus_biopsy``: its facts over act()'s) and, with ``denial_``, the broad denial E5 "No biopsies were taken
    during the EUS." in X2."""
    events = {E1: exam(session=sup(X1)), E2: exam(session=sup(X2)),
              E3: act(Kind.BIOPSY, session=sup(X1), places=(sup(Landmark.GASTRIC_BODY),)),
              E4: act(Kind.BIOPSY, session=sup(X2), **eus_biopsy)}
    if denial_:
        events[E5] = denial(Kind.BIOPSY, session=sup(X2))
    R = build(events, sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)},
              controls=controls_)
    return R, [C.Counted('sel:0', '43239', SessionKind.EGD, (E3,)),
               C.Counted('sel:1', '43259', SessionKind.EUS, (E2,), tuple(read))]


def state(R: FactSet, cov) -> str:
    return C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0, label=label)['state']


class ContradictedNeverReadUnder(SimpleTestCase):
    """DECISIONS D227 F3 (refute-4b-r2 q6; D3, 4.8 rank 1): a contradicted act is never read under another service: it
    is listed in doubt with its conflict question - also where D137's class records it reportable (eus_unlisted), which
    round 2's listing skipped."""

    def test_f3_a_contradicted_eus_biopsy_is_listed_in_doubt_with_its_conflict(self):
        """q6: the EUS biopsy E4 at the gastric body, its place list even established complete, beside the denial E5
        that contradicts it: never read under the EGD's 43239 - listed in doubt, its service question conflict:biopsy
        at rank 1; round 2 listed it bundled and asked nothing."""
        R, counted = eus_beside_egd(dict(places=(sup(Landmark.GASTRIC_BODY),)), denial_=True,
                                    controls_=complete(E4, (Landmark.GASTRIC_BODY,)))
        self.assertEqual(C.Reader(R).conflicts(E4)[0].fact, 'conflict:biopsy')
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(cov.bundled, [])
        self.assertEqual([(item.session, item.reason, item.detail, item.events) for item in cov.unresolved],
                         [(X2, C.ItemReason.IN_DOUBT, C.Detail.IN_DOUBT, (E4,))])
        self.assertEqual([(service.event, service.item.fact, service.item.rank)
                          for service in C.in_doubt_questions(R, cov)], [(E4, 'conflict:biopsy', 1)])
        self.assertEqual(state(R, cov), 'incomplete')

    def test_f3_controls(self):
        """Without the denial the same biopsy is read under the EGD (its list established complete); read by a counted
        code, a contradicted biopsy is that code's to ask (no service item, never bundled)."""
        R, counted = eus_beside_egd(dict(places=(sup(Landmark.GASTRIC_BODY),)),
                                    controls_=complete(E4, (Landmark.GASTRIC_BODY,)))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(([(act.event, act.rule) for act in cov.bundled], cov.unresolved), ([(E4, None)], []))
        R, counted = eus_beside_egd(dict(places=(sup(Landmark.GASTRIC_BODY),)), denial_=True, read=(E4,),
                                    controls_=complete(E4, (Landmark.GASTRIC_BODY,)))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual((cov.bundled, cov.unresolved, cov.in_doubt), ([], [], []))

    def test_d3_a_contradicted_act_of_d137s_class_asks_its_conflict(self):
        """D3 at the listing (the module docstring's claim, refute-4b-r2 F3's 'Where'): an EUS ablation - D137's class,
        recorded reportable - that a denial contradicts was listed not covered (D142) and asked nothing; its conflict is
        now its service question."""
        R = build({E1: exam(), E3: act(Kind.ABLATION), E5: denial(Kind.ABLATION)},
                  sessions={X1: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
        self.assertEqual(C.eus_unlisted(R, E3), (True, False))
        cov = C.reconcile(R, [C.Counted('sel:0', '43259', SessionKind.EUS, (E1,))], procedure_day=True)
        self.assertEqual([(item.reason, item.events) for item in cov.unresolved], [(C.ItemReason.NOT_COVERED, (E3,))])
        self.assertEqual([(service.event, service.item.fact, service.item.rank)
                          for service in C.in_doubt_questions(R, cov)], [(E3, 'conflict:ablation', 1)])


class ReadUnderCompleteness(SimpleTestCase):
    """DECISIONS D227 F4 (refute-4b-r2 q3; P3: no rule reads a list's completeness except through an established
    completeness claim or rejected pair controls): an EUS forceps biopsy is read under the upper endoscopy only when
    its place list is established complete within the upper GI regions - every landmark outside them that its places
    do not cover excluded by a rejected pair control or a negated member; otherwise it is listed in doubt, asking a
    coverage question (act_target, rank 17, coding_rule:read_under), and it holds no code."""

    def test_f4_a_short_list_is_listed_with_a_coverage_question(self):
        """q3: (i) the gastric body and the pancreas, both supported: placed outside, unsupported (v1's listing); (ii)
        the pancreas deleted (9.4's short list): listed in doubt - round 2 read it under the EGD and turned
        completeness complete - its question naming E4 and its place."""
        R, counted = eus_beside_egd(dict(places=(sup(Landmark.GASTRIC_BODY), sup(Landmark.PANCREAS))))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.reason, item.detail, item.events) for item in cov.unresolved],
                         [(C.ItemReason.UNSUPPORTED, C.Detail.READ_UNDER_NOT_PLACED, (E4,))])
        R, counted = eus_beside_egd(dict(places=(sup(Landmark.GASTRIC_BODY, spans=(Span(410, 420),)),)))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(([act.event for act in cov.bundled], [(item.reason, item.detail, item.events)
                                                               for item in cov.unresolved], state(R, cov)),
                         ([], [(C.ItemReason.IN_DOUBT, C.Detail.READ_UNDER_NOT_ESTABLISHED, (E4,))], 'incomplete'))
        questions = C.in_doubt_questions(R, cov)
        self.assertEqual([(service.event, service.item.fact, service.item.rank, service.item.cause,
                           service.item.attribute, service.item.kind) for service in questions],
                         [(E4, 'act_target', 17, 'coding_rule:read_under', A.TARGET_PLACES, ItemKind.QUESTION)])
        self.assertEqual(questions[0].item.spans, (unit(4), Span(410, 420)))
        # it holds no code: E4 is its own act (no bundling item), and the EUS and EGD codes stand on their own acts
        self.assertEqual((C.verdict(R, E4).truth, C.bundling('43239', (E3,), R), C.bundling('43259', (E2,), R)),
                         (T, (), ()))

    def test_f4_completeness_established_by_rejected_pair_controls(self):
        listed = (Landmark.GASTRIC_BODY,)
        full = complete(E4, listed)
        self.assertIn((E4, A.TARGET_PLACES, Landmark.PANCREAS), full)
        self.assertNotIn((E4, A.TARGET_PLACES, Landmark.STOMACH), full)  # compatible with the gastric body: covered
        for name, places, ctl, read_under in (
                ('every landmark outside excluded', (sup(Landmark.GASTRIC_BODY),), full, True),
                ('the pancreas control not rejected', (sup(Landmark.GASTRIC_BODY),),
                 {**full, (E4, A.TARGET_PLACES, Landmark.PANCREAS): False}, False),
                ('the pancreas control never made', (sup(Landmark.GASTRIC_BODY),),
                 {key: value for key, value in full.items() if key[2] is not Landmark.PANCREAS}, False),
                ('the pancreas a negated member instead', (sup(Landmark.GASTRIC_BODY), neg(Landmark.PANCREAS)),
                 {key: value for key, value in full.items() if key[2] is not Landmark.PANCREAS}, True),
                ('a member not established', (sup(Landmark.GASTRIC_BODY), unres(Landmark.DUODENUM)), full, False),
                ('no place stated', (), full, False)):
            with self.subTest(name):
                R, counted = eus_beside_egd(dict(places=places), controls_=ctl)
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual(([act.event for act in cov.bundled], state(R, cov)),
                                 ([E4], 'complete_pending_review') if read_under else ([], 'incomplete'))
                if not read_under:
                    self.assertEqual([(item.detail, item.events) for item in cov.unresolved],
                                     [(C.Detail.READ_UNDER_NOT_ESTABLISHED, (E4,))])
                    self.assertEqual([service.item.fact for service in C.in_doubt_questions(R, cov)], ['act_target'])

    def test_f4_a_deleted_member_never_reads_it_under(self):
        """9.4's deleted member (pair controls left as they were): from lists read under, placed outside or listed,
        deleting any member never turns a listed act into one read under, nor completeness complete."""
        checked = 0
        for places in ((Landmark.GASTRIC_BODY, Landmark.PANCREAS), (Landmark.GASTRIC_BODY, Landmark.DUODENUM),
                       (Landmark.ESOPHAGUS, Landmark.GASTRIC_ANTRUM, Landmark.LIVER), (Landmark.DUODENUM,)):
            for ctl in (complete(E4, places), {}):
                R, counted = eus_beside_egd(dict(places=tuple(sup(place) for place in places)), controls_=ctl)
                cov = C.reconcile(R, counted, procedure_day=True)
                was_listed = not cov.bundled
                for index in range(len(places)):
                    kept = places[:index] + places[index + 1:]
                    with self.subTest(places=places, controls=bool(ctl), deleted=places[index]):
                        weak, _ = eus_beside_egd(dict(places=tuple(sup(place) for place in kept)), controls_=ctl)
                        after = C.reconcile(weak, counted, procedure_day=True)
                        if was_listed:
                            self.assertEqual((after.bundled, state(weak, after)), ([], 'incomplete'))
                        checked += 1
        self.assertGreater(checked, 12)


class AdjunctAsksOnlyForTheSameLesion(SimpleTestCase):
    """DECISIONS D221 (refute-4b-r2 F1, q1; mutant RQ1's reach): the procedural-adjunct arm asks only where the two
    acts may name the same lesion. Two different supported lesion ids that no same_as can join are different findings
    (P5): the arm is F and the ablation's or the bleeding control's code proceeds on its own rows. One lesion id - or a
    same_as that may join them - asks (U, act_part), never explains; a same_as not established asks first, one
    question naming both."""

    def scene(self, part_lesion, *, whole=Kind.SNARE, same=None):
        lesions = {L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,)),
                   L2: lesion(ct.Multiplicity.SINGLE, places=(Landmark.CECUM,))}
        if same is not None:
            lesions[L2] = {**lesions[L2], A.SAME_AS: (same,)}
        return build({E1: exam(), E2: act(whole, lesion=sup(L1), places=(sup(Landmark.SIGMOID_COLON),)),
                      E3: act(Kind.ABLATION, lesion=part_lesion, places=(sup(Landmark.CECUM),), **STATED_LINK)},
                     lesions=lesions)

    def test_d221_another_lesion_is_not_held_by_the_bundling_row(self):
        """q1: a cold snare of polyp L1 (sigmoid) and an APC of angioectasia L2 (cecum), distinct_from stated or not;
        the EGD shape (an EMR of nodule L1, an RFA of the Barrett segment L2); a bleeding control of L2 beside the
        snare of L1 - none held by the bundling row (round 2 asked act_part and act_target in each)."""
        distinct = {L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,), distinct=(L2,)),
                    L2: lesion(ct.Multiplicity.SINGLE, places=(Landmark.CECUM,), distinct=(L1,))}
        for name, R, code in (
                ('another lesion', self.scene(sup(L2)), '45388'),
                ('distinct_from stated', build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)),
                                                E3: act(Kind.ABLATION, lesion=sup(L2), **STATED_LINK)},
                                               lesions=distinct), '45388'),
                ('the EGD shape', build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L1)),
                                         E3: act(Kind.ABLATION, lesion=sup(L2), **STATED_LINK)}, sessions={X1: session(
                                             SessionKind.EGD)}, lesions={L1: lesion(ct.Multiplicity.SINGLE),
                                                                         L2: lesion()}), '43270')):
            with self.subTest(name):
                self.assertEqual((C.bundles(R, E3), C.verdict(R, E3).truth, C.bundling(code, (E3,), R)), ((), T, ()))
                self.assertFalse(C.doubted(R, E3))
        # a bleeding control of another lesion (restated at round r3's integration): it treats bleeding, so the silent-
        # link rule reads its SILENT cause as a doubt (DESIGN-v2 b.8: the procedure-caused bleeding control), its part_of
        # stated - held by the cause arm alone, over every event of the session; D221's lesion arm adds nothing (no
        # bundle of it rests on a lesion or a part_of)
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L1)), E3: hemoclips(lesion=sup(L2), part_of=neg(None))},
                  lesions={L1: lesion(), L2: lesion()})
        with self.subTest('a bleeding control of another lesion'):
            found = C.bundles(R, E3)
            self.assertEqual([(bundle.rule, bundle.whole, bundle.truth) for bundle in found],
                             [(C.Rule.PROCEDURAL_ADJUNCT, E1, U), (C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
            self.assertEqual({doubt.attribute for bundle in found for doubt in bundle.doubts}, {A.CAUSE})
            self.assertEqual({(item.fact, item.attribute) for item in C.bundling('45382', (E3,), R)},
                             {('act_cause', A.CAUSE)})

    def test_d221_one_lesion_or_a_same_as_that_may_join_them_asks(self):
        """DECISIONS D248 G2 (option (b)) changed the last four rows: a lesion fact that is not supported is an unknown
        identity, asked first (its lesion question, act_target), then the part_of - round 2 of this repair asked the
        part_of first and set 'an unresolved other lesion' apart (F, test_d221_controls)."""
        lesion_question = ('act_target', 17, E3, A.TARGET_LESION)
        for name, part, same, first_item in (
                ('one lesion id', sup(L1), None, ('act_part', 17, E3, A.PART_OF)),
                ('a supported same_as', sup(L2), sup(L1), ('act_part', 17, E3, A.PART_OF)),
                ('an unresolved same_as', sup(L2), unres(L1), ('act_target', 17, L2, A.SAME_AS)),
                ('a doubted same_as', sup(L2), doubted(L1), ('act_target', 17, L2, A.SAME_AS)),
                ('a contradicted same_as', sup(L2), contra(L1, L3), ('conflict:ablation', 1, L2, A.SAME_AS)),
                ('its lesion a reading of the other', doubted(L2, L1), None, lesion_question),
                ('its lesion unresolved, the control not rejected', unres(L2, options=(L1,)), None, lesion_question),
                ('a negation of another lesion', neg(L2), None, lesion_question),
                ('an unresolved other lesion (D248 G2)', unres(L2), None, lesion_question)):
            with self.subTest(name):
                R = self.scene(part, same=same)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                held = C.bundling('45388', (E3,), R)
                self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute), first_item)
                self.assertIn(('act_part', E3, A.PART_OF), {(item.fact, item.subject, item.attribute) for item in held})
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])

    def test_d221_a_missing_lesion_identifier_is_unknown(self):
        """4.11: a missing identifier manufactures neither a match nor a non-match. The ablation's lesion supported as
        L3, which names no lesion of the FactSet (settle's I4 leaves such an id unresolved; a constructed FactSet can
        hold it supported): the identity is unknown - asked, resting on that lesion fact - never two different
        findings, nor one finding."""
        R = self.scene(sup(L3))
        self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
        held = {(item.fact, item.rank, item.subject, item.attribute) for item in C.bundling('45388', (E3,), R)}
        self.assertLessEqual({('act_part', 17, E3, A.PART_OF), ('act_target', 17, E3, A.TARGET_LESION)}, held)

    def test_d221_controls(self):
        """Both lesion facts supported (DECISIONS D248 G2: D221's F applies only then): a same_as established as not
        joining them (negated), or a same_as naming a third lesion of the FactSet that nothing joins to the removal's:
        different findings, F. (Round 1 of this repair pinned the last with L3 an id the FactSet does not hold - a
        missing identifier, which MissingLesionIdentifiers reads as unknown: refute-r4b-r1 R2. Round 2 pinned 'an
        unresolved other lesion' here too; D248 G2 makes it U, asked: the test above.)"""
        for name, part, same in (('a rejected same_as', sup(L2), neg(L1)),
                                 ('a same_as naming a third lesion', sup(L2), unres(L3))):
            with self.subTest(name):
                R = self.scene(part, same=same)
                R = FactSet(R.encounter, R.people, R.sections, R.sessions, R.anatomy, {**R.lesions, L3: lesion()},
                            R.events, R.anchors, R.unlisted, R.pair_controls, R.completeness)
                self.assertEqual(C.bundles(R, E3), ())

    def test_d221_monotone_under_9_4s_weakenings(self):
        """9.4 P-MONO over D221's arm (weakenings: an established fact unresolved or doubted, a place member deleted, a
        control not rejected): an act asked by it is never released, and an act set apart becomes at most asked.
        Deleting a same_as member is the one change that releases it (question QR4-1)."""
        checked = 0
        for name, R in (('same lesion', self.scene(sup(L1))),
                        ('a supported same_as', self.scene(sup(L2), same=sup(L1))),
                        ('an open same_as', self.scene(sup(L2), same=unres(L1)))):
            self.assertEqual(C.verdict(R, E3).truth, U)
            base = C.verdict(R, E3).truth
            for change in weakenings(R):
                if change[2] in (A.SAME_AS, A.DISTINCT_FROM) and change[4] is None:
                    continue  # a deleted same_as or distinct_from member: QR4-1
                with self.subTest(scene=name, change=change[:4]):
                    if base is not T:
                        self.assertNotEqual(C.verdict(weaken(R, change), E3).truth, T)
                    checked += 1
        self.assertGreater(checked, 50)
        R = self.scene(sup(L2), same=unres(L1))  # QR4-1, recorded: deleting the same_as member releases the ablation
        released = weaken(R, ('lesions', L2, A.SAME_AS, 0, None))
        self.assertEqual((C.verdict(R, E3).truth, C.verdict(released, E3).truth), (U, T))


class LiftReadsItsRelation(SimpleTestCase):
    """refute-4b-r2 F6 (DECISIONS D229): 4.7's lift row - part_relation lift_for or step_of to an EMR or ESD, or
    purpose lift_for_resection on the same lesion - never a hemostatic injection. A hemostatic injection stated as the
    EMR's adjunct is bundled as its procedural adjunct, never explained as its lift (round 2 read any relation)."""

    def scene(self, **injection):
        return build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L1)), E3: act(Kind.INJECTION, **injection)},
                     lesions=CECAL)

    def by_part(self, relation):
        """The injection part_of the EMR with ``relation``, its purpose neither the lift's nor hemostasis (so the
        lift's purpose arm is F and its part_of arm alone decides)."""
        return self.scene(part_of=sup(E2), relation=relation, purpose=sup(Purpose.OTHER))

    def test_f6_a_hemostatic_injection_stated_as_the_adjunct_is_no_lift(self):
        """q5: an injection for hemostasis, its cause the EMR (cause_event E2), part_of the EMR adjunct_of."""
        stated = dict(purpose=sup(Purpose.HEMOSTASIS), cause=sup(Cause.ACT_OF_THIS_SESSION), cause_event=sup(E2),
                      part_of=sup(E2))
        for relation in (ct.PartRelation.ADJUNCT_OF, ct.PartRelation.LIFT_FOR):
            with self.subTest(relation=relation):
                R = self.scene(relation=sup(relation), **stated)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, T)])
                self.assertEqual(C.bundled(R, E3).rule, C.Rule.PROCEDURAL_ADJUNCT)
                self.assertEqual(first(C.bundling('45382', (E3,), R)).cause, 'coding_rule:procedural_adjunct')

    def test_f6_the_relation_decides_the_lift_by_part_of(self):
        for relation, lift in ((sup(ct.PartRelation.LIFT_FOR), T), (sup(ct.PartRelation.STEP_OF), T),
                               (sup(ct.PartRelation.ADJUNCT_OF), None), (sup(ct.PartRelation.COMPONENT_OF), None),
                               (sup(ct.PartRelation.ACCESS_FOR), None), (unres(ct.PartRelation.LIFT_FOR), U),
                               (doubted(ct.PartRelation.ADJUNCT_OF, ct.PartRelation.LIFT_FOR), U),
                               (neg(ct.PartRelation.ADJUNCT_OF), U), (None, U)):
            with self.subTest(relation=None if relation is None else (relation.result, relation.value)):
                R = self.by_part(relation)
                self.assertEqual([bundle.truth for bundle in C.bundles(R, E3) if bundle.rule is C.Rule.LIFT_INJECTION],
                                 [lift] if lift is not None else [])
                self.assertEqual(C.verdict(R, E3).truth, FF)  # part of the EMR either way: bundled, never READY
        R = build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L1)),  # a tattoo is no adjunct kind: its own act
                   E3: act(Kind.TATTOO, part_of=sup(E2), relation=sup(ct.PartRelation.COMPONENT_OF))}, lesions=CECAL)
        self.assertEqual(C.bundles(R, E3), ())


class D70ReadsPossibleMembers(SimpleTestCase):
    """refute-4b-r2 F7 (DECISIONS D229): round 2's M1 repair read D70's "may be done" over the session's POSSIBLE
    members; mutant RM1_FILED_MEMBERS (its filed members only) survived the suite. q8: a done EGD beside an upper EUS
    told only through an FNA whose session is contradicted between them, or a doubt on its empty slot - the EUS has no
    filed member, and the EGD is possibly its endoscopic portion."""

    def test_f7_an_eus_told_only_by_an_act_possibly_in_it(self):
        for found in (contra(X1, X2), doubted_empty(X1, X2)):
            with self.subTest(session=found.result):
                R = build({E1: exam(session=sup(X1)), E3: act(Kind.FNA, session=found)},
                          sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
                sessions_ = C.sessions(R)
                self.assertEqual((sessions_[X2].events, sessions_[X2].done, C.possible_members(R, X2)),
                                 ((), False, (E3,)))
                self.assertEqual((sessions_[X1].part_of, sessions_[X1].possibly_part_of), (None, X2))
                self.assertEqual(C.event_coding(R, sessions_, {})['sessions']['X1']['possibly_part_of'], 'X2')


class FamiliesOfAnActWhoseSessionIsOpen(SimpleTestCase):
    """DECISIONS D227 F8 (refute-4b-r2 q7, the builder's QR2-8): an act whose own session is not established reads
    every family only when the sessions it may be in do not admit its kind (FAMILY_KINDS, K2's table, D191); otherwise
    its possible sessions' families - "admit" read so that no weakening narrows them (question QR4-3)."""

    def test_f8_an_ercp_contrast_injection_reads_the_ercps_family(self):
        """q7: the ERCP's contrast injection whose session pass 2 left unresolved (the ERCP its only possible session)
        is the ERCP's own: not doubted, as its one session reads it, nothing listed - round 2 read every family, listed
        it in doubt and asked 'procedure'."""
        counted = [C.Counted('sel:0', '43260', SessionKind.ERCP, (E1,))]
        for found in (sup(X1), unres(X1)):
            with self.subTest(session=found.result):
                R = build({E1: exam(), E2: act(Kind.INJECTION, session=found, purpose=sup(Purpose.DIAGNOSTIC))},
                          sessions={X1: session(SessionKind.ERCP)})
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual((C.doubted(R, E2), C.doubted_in(R, E2, X1), cov.unresolved,
                                  C.in_doubt_questions(R, cov), state(R, cov)),
                                 (False, False, [], [], 'complete_pending_review'))

    def test_f8_an_act_its_possible_sessions_cannot_hold_reads_every_family(self):
        """S2's PEG left in a colonoscopy (K2 demoted its session): every family, doubted. And the two weakenings
        under which D227's words read with ANY would narrow it (QR4-3): the PEG's kind gaining a cannulation reading
        (which a colonoscopy admits), and an act of kind other in a session of a family that admits nothing gaining
        a reading of a colonoscopy - each still read under every family and doubted."""
        two = {X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.OTHER_GI)}
        for name, kind, found in (
                ('the PEG', sup(Kind.PEG), unres(X1)),
                ('its kind gaining a reading', doubted(Kind.PEG, Kind.PEG, Kind.CANNULATION), unres(X1)),
                ('kind other in a session admitting nothing', sup(Kind.OTHER), unres(X2)),
                ('its session gaining a reading', sup(Kind.OTHER), doubted(X2, X2, X1))):
            with self.subTest(name):
                R = build({E1: exam(session=sup(X1)), E3: act(Kind.PEG, kind=kind, session=found)}, sessions=two)
                self.assertTrue(C.doubted(R, E3))

    def test_f8_d142s_class_whose_session_is_open_stays_listed(self):
        """The ERCP's foreign body (D142's class: the ERCP admits the kind, its acts do not list it, an EGD's do) whose
        session is not established: read in the ERCP's family it is no reportable act there, so ``doubted`` misses it
        and D142's class in doubt lists it, with its service question (round 2 reached it through every family)."""
        for found in (unres(X1), doubted(X1)):
            with self.subTest(session=found.result):
                R = build({E1: exam(), E3: act(Kind.FOREIGN_BODY, session=found)},
                          sessions={X1: session(SessionKind.ERCP)})
                self.assertFalse(C.doubted(R, E3))
                cov = C.reconcile(R, [C.Counted('sel:0', '43260', SessionKind.ERCP, (E1,))], procedure_day=True)
                self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved],
                                 [(X1, C.ItemReason.IN_DOUBT, (E3,))])
                self.assertEqual([service.event for service in C.in_doubt_questions(R, cov)], [E3])


class NegationLeftOpen(SimpleTestCase):
    """sessions_of (repair r4b): an established negation "not in X1" leaves every other session; the same claim not
    established - unresolved, a doubt - leaves EVERY session (step 4d's possible_sessions alike). facts.possibly reads
    its claimed value alone, so round 2 narrowed every other session to X1, the one it denies: weakening the
    negation dropped the act from X2's records (9.4 P-MONO at the records base_included reads)."""

    def test_a_negation_left_open_leaves_every_session_open(self):
        R = two_sessions(neg(X1))
        self.assertEqual((C.sessions_of(R, E3), entries(R)), (frozenset({X2}), {'X1': set(), 'X2': {'E3'}}))
        for weak in (unres(X1, state=State.NEGATED), doubted(X1, state=State.NEGATED)):
            with self.subTest(session=weak.result):
                R = two_sessions(weak)
                self.assertEqual((C.sessions_of(R, E3), entries(R)),
                                 (frozenset({X1, X2}), {'X1': {'E3'}, 'X2': {'E3'}}))


class OverfilledViewLeftOpen(SimpleTestCase):
    """refute-f3e-r1 F1 (critical) and F3b (AMENDMENT-2 4.3.3 a, 4.4 [R:truth-T1]): coverage's two possibility readers
    that take an unestablished denial as leaving every value open - sessions_of and _lesion_values - take EVERY
    overfilled slot's merged view so (facts.open_denial). A view of one value written both ways ("X1" stated and "X1"
    denied) carries nothing in negated_values, since the claimed-value readers must claim X1, so a reader widening only
    on negated_values read it as X1 alone, narrower than the denial read alone; the view cannot tell whether a written
    fact denied a value, so each reader reads it as the denial would (the step's NOTES question Q1R). Without the
    widening in either reader, its test fails."""

    def test_sessions_of_reads_every_session_view_as_a_written_denial(self):
        from tests.v2.test_combination import overfilled

        S_, N_ = State.SUPPORTED, State.NEGATED
        denial = two_sessions(unres(X1, state=State.NEGATED))
        expected = (frozenset({X1, X2}), {'X1': {'E3'}, 'X2': {'E3'}})
        self.assertEqual((C.sessions_of(denial, E3), entries(denial)), expected)  # the denial read alone
        stated = two_sessions(unres(X1))
        self.assertEqual(C.sessions_of(stated, E3), frozenset({X1}))  # the statement read alone
        for name, view in (('X1 stated, X1 denied', overfilled((S_, X1), (N_, X1))),
                           ('X1 denied, X1 stated', overfilled((N_, X1), (S_, X1))),
                           ('X1 stated, X2 denied', overfilled((S_, X1), (N_, X2))),
                           ('X1 and X2 stated', overfilled((S_, X1), (S_, X2))),
                           ('X1 stated twice', overfilled((S_, X1), (S_, X1)))):
            with self.subTest(name):
                R = two_sessions(view)
                self.assertEqual((C.sessions_of(R, E3), entries(R)), expected)

    def test_lesion_values_reads_every_lesion_view_as_a_written_denial(self):
        from tests.v2.test_combination import overfilled

        S_, N_ = State.SUPPORTED, State.NEGATED
        R = build({E1: exam()}, lesions={L1: lesion(), L2: lesion()})
        self.assertEqual(C._lesion_values(R, unres(L1, state=State.NEGATED)), frozenset({L1, L2}))  # the denial
        self.assertEqual(C._lesion_values(R, unres(L1)), frozenset({L1}))  # the statement read alone
        for name, view in (('L1 stated, L1 denied', overfilled((S_, L1), (N_, L1))),
                           ('L1 denied, L1 stated', overfilled((N_, L1), (S_, L1))),
                           ('L1 stated, L2 denied', overfilled((S_, L1), (N_, L2))),
                           ('L1 and L2 stated', overfilled((S_, L1), (S_, L2)))):
            with self.subTest(name):
                self.assertEqual(C._lesion_values(R, view), frozenset({L1, L2}))


# --- repair r4b, round 2 (refute-r4b-r1 R1-R5), each pinned by a test -----------------------------------------------


L9 = Id(IdFamily.LESION, 9)  # a lesion id the FactSet does not hold (settle's I4: unresolved, reference_invalid)
INVALID = (ct.Reason.REFERENCE_INVALID,)


def lesion_entry(*same) -> dict:
    """A single lesion entry at the ascending colon whose same_as list is ``same``."""
    return {A.PLACES: (sup(Landmark.ASCENDING_COLON),), A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),),
            A.DISTINCT_FROM: (), A.SAME_AS: tuple(same)}


class SameAsIsAnEquivalence(SimpleTestCase):
    """refute-r4b-r1 R1 (critical): a same_as says two lesion entries are one finding (P5), an equivalence - pass 1 may
    file three entries for one finding and link each mention to the first ("APC was applied to the residual tissue at
    the EMR site.", DQ1's own case). Round 1 of this repair read only a same_as joining the two acts' lesions directly,
    so D221's F exit released the APC of L2 beside the EMR of L3 when L2 and L3 were each the same as L1: through step
    4a's decide and the bundling row (4.4), 45388 READY beside the EMR of the same finding. A chain of members through
    other entries now joins them as one member does: in D221's identity (asked), in the other rules' SAME LESION (T
    only through supported members) and in apart_by_lesion's guard (never apart while a chain may join them)."""

    LINKS = {
        'a star: L2 and L3 each the same as L1': {L2: (sup(L1),), L3: (sup(L1),)},
        'L1 listing both': {L1: (sup(L2), sup(L3))},
        'a chain: L2 the same as L1, L1 the same as L3': {L2: (sup(L1),), L1: (sup(L3),)},
        'a chain, its second link unresolved': {L2: (sup(L1),), L1: (unres(L3),)},
        'a chain, its first link doubted': {L2: (doubted(L1),), L3: (sup(L1),)},
    }

    def scene(self, links, *, part=None, whole=Kind.EMR, controls_=None, distinct=False):
        """A colonoscopy X1 (its done examination E1), ``whole`` E2 of L3 and ``part`` E3 (an APC of L2 by default),
        three lesion entries L1-L3 linked by ``links`` ({lesion: its same_as members})."""
        lesions = {lesion_id: lesion_entry(*links.get(lesion_id, ())) for lesion_id in (L1, L2, L3)}
        if distinct:  # the document says L2 and L3 are distinct
            lesions[L2] = {**lesions[L2], A.DISTINCT_FROM: (sup(L3),)}
            lesions[L3] = {**lesions[L3], A.DISTINCT_FROM: (sup(L2),)}
        here = (sup(Landmark.ASCENDING_COLON),)
        return build({E1: exam(), E2: act(whole, lesion=sup(L3), places=here),
                      E3: part if part is not None else act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2), places=here)},
                     lesions=lesions, controls=controls_)

    def test_r1_a_chain_through_a_third_entry_holds_the_ablation(self):
        """p1: the APC of L2 beside the EMR of L3, joined only through L1 - asked (act_part), never explained; an open
        link of the chain is the question asked first, naming the lesion whose list holds it."""
        for name, links in self.LINKS.items():
            with self.subTest(name):
                R = self.scene(links)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                held = C.bundling('45388', (E3,), R)
                self.assertIn(('act_part', E3, A.PART_OF), {(item.fact, item.subject, item.attribute) for item in held})
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                self.assertTrue(C.doubted(R, E3))
                self.assertIsNone(C.bundled(R, E3))
        for name, asked in (('a chain, its second link unresolved', ('act_target', 17, L1, A.SAME_AS)),
                            ('a chain, its first link doubted', ('act_target', 17, L2, A.SAME_AS)),
                            ('a star: L2 and L3 each the same as L1', ('act_part', 17, E3, A.PART_OF))):
            with self.subTest(first_item=name):
                held = C.bundling('45388', (E3,), self.scene(self.LINKS[name]))
                self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute), asked)

    def test_r1_controls(self):
        """No chain: different findings, F (D221). A chain one of whose links is established as not joining (negated),
        or one that reaches L1 alone, joins nothing: F."""
        for name, links in (('no same_as', {}),
                            ('the second link negated', {L2: (sup(L1),), L1: (neg(L3),)}),
                            ('L2 the same as L1 only', {L2: (sup(L1),)})):
            with self.subTest(name):
                R = self.scene(links)
                self.assertEqual((C.bundles(R, E3), C.verdict(R, E3).truth, C.bundling('45388', (E3,), R)),
                                 ((), T, ()))

    def test_r1_the_other_rules_read_the_same_equivalence(self):
        """The SAME LESION of the other rules: a lift injection of L2 beside the EMR of L3 is the EMR's lift through a
        chain of supported members (T, explained) and asked while a link is open (U). apart_by_lesion's guard: a
        biopsy of L2 beside the snare of L3, distinct_from stated both ways and the lesion pair controls rejected, is
        apart (its own act) - but never while a chain through L1 may join them (round 1 read direct links only and set
        it apart: its code released)."""
        # the injection's part_of stated (round r3's integration: the lift's identity read, never the silent link)
        lift = act(Kind.INJECTION, lesion=sup(L2), purpose=sup(Purpose.LIFT_FOR_RESECTION),
                   places=(sup(Landmark.ASCENDING_COLON),), part_of=STATED_LINK['part_of'])
        R = self.scene(self.LINKS['a star: L2 and L3 each the same as L1'], part=lift)
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth), ([(C.Rule.LIFT_INJECTION, E2, T)], FF))
        R = self.scene(self.LINKS['a chain, its second link unresolved'], part=lift)
        self.assertEqual((rules(R, E3), C.verdict(R, E3).truth), ([(C.Rule.LIFT_INJECTION, E2, U)], U))
        biopsy = act(Kind.BIOPSY, lesion=sup(L2), places=(sup(Landmark.ASCENDING_COLON),))
        ctl = lesion_controls(E3, L2, E2, L3)
        for name, links, found in (('no chain: apart', {}, []),
                                   ('a chain through L1, a link unresolved', {L2: (sup(L1),), L1: (unres(L3),)},
                                    [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)]),
                                   ('a chain through L1, a link doubted', {L2: (doubted(L1),), L3: (sup(L1),)},
                                    [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])):
            with self.subTest(name):
                R = self.scene(links, part=biopsy, whole=Kind.SNARE, controls_=ctl, distinct=True)
                self.assertEqual(rules(R, E3), found)

    def test_r1_monotone_under_9_4s_weakenings(self):
        """9.4 P-MONO over the chain scenes (an established fact unresolved or doubted, a place member deleted, a
        control not rejected): the APC asked is never released. Deleting a same_as member stays the one release
        (question QR4-1)."""
        checked = 0
        for name, links in self.LINKS.items():
            R = self.scene(links)
            for change in weakenings(R):
                if change[2] in (A.SAME_AS, A.DISTINCT_FROM) and change[4] is None:
                    continue
                with self.subTest(scene=name, change=change[:4]):
                    self.assertNotEqual(C.verdict(weaken(R, change), E3).truth, T)
                    checked += 1
        self.assertGreater(checked, 150)


class MissingLesionIdentifiers(SimpleTestCase):
    """refute-r4b-r1 R2 (4.11: missing identifiers manufacture neither a match nor a non-match): D221's F exit read a
    lesion id the FactSet does not hold as a different finding - (a) through a same_as member naming one (pass 1 linking
    L2 to an entry it never filed: settle's I4 keeps the claim unresolved, reference_invalid), (b) as the two acts' own
    lesions when the FactSet holds no lesion entry at all. Such an id may be any ONE lesion: the identity is unknown,
    asked - and only where it may join the two acts' findings."""

    def test_r2_a_same_as_naming_a_missing_id_may_join_its_holder_to_any_lesion(self):
        """p3: the APC of L2 beside the EMR of L1, L2 the same as L9 (no such entry): asked, its same_as first."""
        for name, member in (('unresolved, reference_invalid', fact(Res.UNRESOLVED, L9, State.SUPPORTED,
                                                                   reasons=INVALID)),
                             ('supported', sup(L9))):
            with self.subTest(name):
                R = build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L1)), E3: act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2))},
                          lesions={L1: lesion_entry(), L2: lesion_entry(member)})
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                held = C.bundling('45388', (E3,), R)
                self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute),
                                 ('act_target', 17, L2, A.SAME_AS))

    def test_r2_two_missing_ids_with_no_lesion_entry(self):
        """p5: the FactSet holds no lesion entry; the EMR names L1 and the APC L2 (unresolved, reference_invalid; or
        supported): asked, resting on the lesion facts - round 1 read two different findings."""
        for name, part, whole in (('unresolved', fact(Res.UNRESOLVED, L2, State.SUPPORTED, reasons=INVALID),
                                   fact(Res.UNRESOLVED, L1, State.SUPPORTED, reasons=INVALID)),
                                  ('supported', sup(L2), sup(L1))):
            with self.subTest(name):
                R = build({E1: exam(), E2: act(Kind.EMR, lesion=whole), E3: act(Kind.ABLATION, **STATED_LINK, lesion=part)})
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                held = {(item.fact, item.subject, item.attribute) for item in C.bundling('45388', (E3,), R)}
                self.assertLessEqual({('act_part', E3, A.PART_OF), ('act_target', E3, A.TARGET_LESION)}, held)

    def test_r2_a_third_entry_naming_missing_ids(self):
        """A missing id may be ONE lesion: a third entry L3 the same as one missing id joins nothing (F); the same as
        two, it may be both acts' findings at once (asked, its first such member)."""
        L8 = Id(IdFamily.LESION, 8)
        for name, members, found in (('one missing id', (sup(L9),), []),
                                     ('two missing ids', (sup(L9), unres(L8)), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])):
            with self.subTest(name):
                R = build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L1)), E3: act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2))},
                          lesions={L1: lesion_entry(), L2: lesion_entry(), L3: lesion_entry(*members)})
                self.assertEqual(rules(R, E3), found)
                if found:
                    held = C.bundling('45388', (E3,), R)
                    self.assertEqual((held[0].fact, held[0].subject, held[0].attribute), ('act_target', L3, A.SAME_AS))


def two_eus_biopsies(first_places, second_places, *, egd=True) -> tuple[FactSet, list]:
    """refute-r4b-r1 p2: an upper EUS X2 (its done examination E2, 43259 counted on it) with two done forceps biopsies,
    E4 at ``first_places`` and E6 at ``second_places``; with ``egd``, an EGD X1 beside it (its done examination E1 and a
    done gastric biopsy E3, 43239 counted on E3)."""
    events = {E2: exam(session=sup(X2)),
              E4: act(Kind.BIOPSY, session=sup(X2), places=tuple(sup(place) for place in first_places)),
              E6: act(Kind.BIOPSY, session=sup(X2), places=tuple(sup(place) for place in second_places))}
    sessions_ = {X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)}
    counted = [C.Counted('sel:1', '43259', SessionKind.EUS, (E2,))]
    if egd:
        events = {E1: exam(session=sup(X1)), **events,
                  E3: act(Kind.BIOPSY, session=sup(X1), places=(sup(Landmark.GASTRIC_BODY),))}
        sessions_ = {X1: session(SessionKind.EGD), **sessions_}
        counted.insert(0, C.Counted('sel:0', '43239', SessionKind.EGD, (E3,)))
    return build(events, sessions=sessions_), counted


class ReadUnderListingsKeepTheirDetail(SimpleTestCase):
    """refute-r4b-r1 R3 (DECISIONS D225: every customer sentence true for its state): reconcile's merge - v1's one item
    per session and act kind, the first item's reason and Detail kept - joined D227 F4's in-doubt listing of one EUS
    biopsy with v1's read_under_not_placed listing of another, recording the gastric one as not placed at an upper GI
    site (or the pancreatic one as in doubt, and asked). Each read-under listing is now an item of its own Detail; two
    acts of one listing still merge."""

    def items(self, cov) -> set:
        return {(item.session, item.reason, item.detail, item.events) for item in cov.unresolved}

    def test_r3_one_item_per_read_under_detail(self):
        for places, outside, open_ in ((((Landmark.PANCREAS,), (Landmark.GASTRIC_BODY,)), E4, E6),
                                       (((Landmark.GASTRIC_BODY,), (Landmark.PANCREAS,)), E6, E4)):
            with self.subTest(first=places[0]):
                R, counted = two_eus_biopsies(*places)
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual(self.items(cov), {
                    (X2, C.ItemReason.UNSUPPORTED, C.Detail.READ_UNDER_NOT_PLACED, (outside,)),
                    (X2, C.ItemReason.IN_DOUBT, C.Detail.READ_UNDER_NOT_ESTABLISHED, (open_,))})
                self.assertEqual([(item.detail, item.events, ref.event) for item, ref in cov.in_doubt],
                                 [(C.Detail.READ_UNDER_NOT_ESTABLISHED, (open_,), open_)])
                self.assertEqual([(service.event, service.item.fact) for service in C.in_doubt_questions(R, cov)],
                                 [(open_, 'act_target')])
                self.assertEqual(sorted((row['detail'], row['events']) for row in C.unresolved_record(cov.unresolved)),
                                 sorted([('read_under_not_placed', [str(outside)]),
                                         ('read_under_not_established', [str(open_)])]))

    def test_r3_v1s_two_listings_apart_and_one_listing_merged(self):
        """With no EGD reading biopsies: the pancreatic biopsy is not placed, the gastric one has no such service - two
        items (v1 merged them under the first's sentence); two pancreatic biopsies are one item, as v1's merge."""
        R, counted = two_eus_biopsies((Landmark.PANCREAS,), (Landmark.GASTRIC_BODY,), egd=False)
        self.assertEqual(self.items(C.reconcile(R, counted, procedure_day=True)), {
            (X2, C.ItemReason.UNSUPPORTED, C.Detail.READ_UNDER_NOT_PLACED, (E4,)),
            (X2, C.ItemReason.UNSUPPORTED, C.Detail.READ_UNDER_NO_SERVICE, (E6,))})
        R, counted = two_eus_biopsies((Landmark.PANCREAS,), (Landmark.PANCREAS,))
        self.assertEqual(self.items(C.reconcile(R, counted, procedure_day=True)), {
            (X2, C.ItemReason.UNSUPPORTED, C.Detail.READ_UNDER_NOT_PLACED, (E4, E6))})


class NotDoneSessionsKeepTheirActsListed(SimpleTestCase):
    """refute-r4b-r1 R5 (a design question, built fail-closed; the step's NOTES, QR5-1): D227's one "session done" is
    step 4d's, whose membership reads an examination whose session fact is an ESTABLISHED negation ("not in X1") as
    possibly any session's examination; step 4a's row 7 reads it as no examination of X1. On p4's scene 4a proposes
    45385 READY while coverage calls X1 not done - and round 1 of this repair listed no act of a session not done, so the
    dilation no code reads was listed nowhere and completeness read complete_pending_review. Reconcile now reads the
    member acts of a session not done as a done session's (no no_proposal of its own) whenever a code of its family is
    counted - the case the unestablished count skips - so a documented service with no proposal keeps completeness
    incomplete whatever 4a reads."""

    def test_r5_a_done_act_of_a_session_not_done_stays_listed(self):
        """p4: a colonoscopy X1 told through its acts - a done cold snare E3 (45385 counted on it) and a done dilation
        E4 (no code) - and an examination E5 whose session is established not X1, its date unresolved: X1 not done
        (4d alike), the dilation listed not covered, completeness incomplete; the control without E5 lists the same."""
        counted = [C.Counted('sel:0', '45385', SessionKind.COLONOSCOPY, (E3,))]
        for name, extra, done in (('an examination established not in X1', {E5: exam(session=neg(X1),
                                                                                    date=unres(ON))}, False),
                                  ('control: no such examination', {}, True)):
            with self.subTest(name):
                R = build({E3: act(Kind.SNARE, places=(sup(Landmark.SIGMOID_COLON),)),
                           E4: act(Kind.DILATION, places=(sup(Landmark.RECTUM),)), **extra},
                          sessions={X1: session(SessionKind.COLONOSCOPY, reached=(sup(Landmark.CECUM),))})
                self.assertEqual((C.sessions(R)[X1].done, CB.session_done(R, X1)), (done, done))
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved],
                                 [(X1, C.ItemReason.NOT_COVERED, (E4,))])
                self.assertEqual((cov.unestablished, state(R, cov)), (0, 'incomplete'))

    def test_r5_a_session_not_done_beside_its_familys_code_in_another_session(self):
        """Two colonoscopies: X2 done, 45378 counted on its examination; X1 not done (its examination's date
        unresolved) with a done snare no code reads. DECISIONS D248 G1 reads "read by no counted code" per session: no
        counted code's event may be in X1, so X1 is counted unestablished - "a documented service not established as
        performed and read by no proposal" - and completeness is incomplete (round 1: listed nowhere and not counted,
        45378's family being counted - complete_pending_review; round 2 listed the snare not covered; with a code
        whose event may be in X1, X1's acts are read as a done session's: the next test)."""
        R = build({E1: exam(session=sup(X1), date=unres(ON)), E2: exam(session=sup(X2)),
                   E3: act(Kind.SNARE, session=sup(X1))},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.COLONOSCOPY)})
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E2,))]
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved], [])
        self.assertEqual((cov.covered, cov.unestablished, state(R, cov)), ({X2: ['45378']}, 1, 'incomplete'))

    def test_r5_a_session_not_done_its_own_code_reads(self):
        """The R5 gate per session (D248 G1): X1 not done (its examination's date unresolved), 45385 counted on its
        done snare E3 - a code whose event is in X1 - and a done dilation E4 no code reads: X1's acts are read as a
        done session's (the dilation listed not covered) and X1 is not counted unestablished."""
        R = build({E1: exam(session=sup(X1), date=unres(ON)), E2: exam(session=sup(X2)),
                   E3: act(Kind.SNARE, session=sup(X1)), E4: act(Kind.DILATION, session=sup(X1))},
                  sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.COLONOSCOPY)})
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E2,)),
                   C.Counted('sel:1', '45385', SessionKind.COLONOSCOPY, (E3,))]
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.session, item.reason, item.events) for item in cov.unresolved],
                         [(X1, C.ItemReason.NOT_COVERED, (E4,))])
        self.assertEqual((cov.unestablished, state(R, cov)), (0, 'incomplete'))

    def test_r5_a_session_not_done_whose_kind_is_not_established(self):
        """The same reading for a session whose kind is not established (every family it may be of with a counted
        code): its done snare listed as a done session's act, its family None (the snare is in doubt besides - its
        session's kind not established - and the one item per session and act kind keeps the first listing, as for
        a done session whose kind is not established). With no counted code of its family the session is counted
        unestablished instead, and only its doubt lists the snare (v1's count, unchanged)."""
        R = build({E1: exam(date=unres(ON)), E2: act(Kind.SNARE)}, sessions={X1: session(unres(SessionKind.COLONOSCOPY))})
        cov = C.reconcile(R, [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))], procedure_day=True)
        self.assertEqual([(item.session, item.family, item.reason, item.events) for item in cov.unresolved],
                         [(X1, None, C.ItemReason.NOT_COVERED, (E2,))])
        self.assertEqual(cov.unestablished, 0)
        cov = C.reconcile(R, [], procedure_day=True)
        self.assertEqual(([(item.session, item.reason, item.events) for item in cov.unresolved], cov.unestablished),
                         ([(X1, C.ItemReason.IN_DOUBT, (E2,))], 1))


# --- repair r4b, round 3 (DECISIONS D231's coverage half; D248: refute-r4b-r2 G1-G7), each pinned by a test --------


U_ACT, U_DOUBT, U_DENIAL = ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL
L4, L5, L6 = (Id(IdFamily.LESION, n) for n in (4, 5, 6))
E7 = Id(IdFamily.EVENT, 7)


def unlisted(what, kind, session_, n=5) -> UnlistedStatement:
    """A kept unlisted entry (3.2.6 {units, what, kind, session}): ``what`` an act, a denial or a doubt, its kind (None:
    the document names none) and its session card (None: pass 2 named none), quoting unit ``n``."""
    return UnlistedStatement(units=(unit(n),), what=what, kind=kind, session=session_)


# How one act is told, for D231's done-when: kept unlisted as an act or a doubt, with its session card or none, or filed
# in doubt (its status doubted performed, every other fact as act() states it).
TOLD = ('unlisted act', 'unlisted doubt', 'unlisted act, no card', 'unlisted doubt, no card', 'filed in doubt')


def told(form, kind, session_, **filed) -> tuple:
    """(the filed event or None, the kept unlisted entries) for ``form`` (TOLD); ``filed`` over the filed form's facts."""
    if form == 'filed in doubt':
        return act(kind, session=sup(session_), status=doubted(PERFORMED), **filed), ()
    what = U_ACT if form.startswith('unlisted act') else U_DOUBT
    return None, (unlisted(what, kind, None if form.endswith('no card') else session_),)


def with_told(events: dict, form, kind, session_, **filed) -> tuple[dict, tuple]:
    """``events`` with the act told in ``form`` (filed as E5, or kept unlisted), and the unlisted entries."""
    event_, entries = told(form, kind, session_, **filed)
    return ({**events, E5: event_} if event_ is not None else dict(events)), entries


class SyntheticActIsAPossibleWhole(SimpleTestCase):
    """DECISIONS D231's coverage half, C1 (refute-r4d-r1 RFR4D-DQ1's class; r4a-2's audit, its log
    coverage-d216-doubt-audit.out): bundling's possible whole (Reader._compute_bundles) reads 3.2.6 rule 3's synthetic
    act - a kept unlisted ACT or DOUBT with card S, or no card where S is possible - as possibly performed, as the same
    act filed in doubt is read: Reader._synthetic_wholes adds its filed doubted form. Round 2 iterated R.events only, so
    a biopsy of a single polyp beside a snare kept unlisted was its own act (45380 not held by the bundling row) while
    the same snare filed in doubt held it. A bundling into a synthetic act is U, never T, and asks the act's own doubt
    (performed_status at rank 2, cause unlisted, quoting its unit)."""

    def biopsy_beside(self, form, *, whole=Kind.SNARE, card=X1, sessions=None):
        events, entries = with_told({E1: exam(), E3: act(Kind.BIOPSY, lesion=sup(L1),
                                                         places=(sup(Landmark.SIGMOID_COLON),))}, form, whole, card)
        return build(events, sessions=sessions, unlisted=entries,
                     lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,))})

    def outcome(self, R, part, code):
        """What D231's done-when compares: the part's verdict, its bundles' (rule, truth), whether the code is held by
        the bundling row, by a question only, and the top item's (fact, rank) in 4.8's order (step 4a's)."""
        found = C.verdict(R, part)
        held = C.bundling(code, (part,), R)
        top = Q.ranked(held, R)[0] if held else None
        return (found.truth, [(bundle.rule, bundle.truth) for bundle in found.bundles], bool(held),
                all(item.kind is ItemKind.QUESTION for item in held),
                None if top is None else (top.fact, top.rank))

    def test_c1_an_unlisted_act_a_doubt_and_the_filed_doubted_form_give_one_outcome(self):
        """The done-when: the biopsy E3 of the single polyp L1 beside a snare told in each form - U, one
        biopsy_of_removed_lesion bundle, 45380 held by questions, its top item a doubt (rank 2); round 2: T and READY
        for every unlisted form. With nothing beside it: T."""
        expected = (U, [(C.Rule.BIOPSY_OF_REMOVED_LESION, U)], True, True, ('performed_status', 2))
        for form in TOLD:
            with self.subTest(form):
                R = self.biopsy_beside(form)
                self.assertEqual(self.outcome(R, E3, '45380'), expected)
                self.assertTrue(C.doubted(R, E3))
                self.assertIsNone(C.bundled(R, E3))
        R = build({E1: exam(), E3: act(Kind.BIOPSY, lesion=sup(L1), places=(sup(Landmark.SIGMOID_COLON),))},
                  lesions={L1: lesion(ct.Multiplicity.SINGLE, places=(Landmark.SIGMOID_COLON,))})
        self.assertEqual(self.outcome(R, E3, '45380'), (T, [], False, True, None))

    def test_c1_the_synthetic_acts_witness(self):
        """The unlisted forms' bundle names no whole and records the entry (Bundle.unlisted); its item is the entry's
        doubt - performed_status, rank 2, cause unlisted, about no single fact, quoting the entry's unit (the bundle's
        other witnesses quote the part and that unit) - its subject the card's session, None with no card. No
        place-holder id reaches a record: every witness's subject is the part, a lesion, a session or None."""
        for form, subject in (('unlisted act', X1), ('unlisted doubt, no card', None)):
            with self.subTest(form):
                R = self.biopsy_beside(form)
                (bundle,) = C.bundles(R, E3)
                self.assertEqual((bundle.whole, bundle.unlisted, bundle.truth), (None, 0, U))
                doubt = [item for item in C.verdict(R, E3).held if item.cause == C.UNLISTED]
                self.assertEqual([(item.fact, item.rank, item.attribute, item.result, item.subject, item.spans)
                                  for item in doubt], [('performed_status', 2, None, None, subject, (unit(5),))])
                for item in C.verdict(R, E3).held:
                    self.assertTrue(item.subject is None or item.subject in (E3, L1, X1), item)
                self.assertEqual(C.act_item(R, E3), doubt[0])

    def test_c1_controls(self):
        """No synthetic act a bundling rule can read: a card naming another session of the FactSet (established apart
        from the biopsy's), an unlisted DENIAL (a statement, 3.2.6 rule 4), an unlisted act of no removal kind - the
        biopsy is its own act. With two sessions and no card, S is possible: U."""
        two = {X1: session(SessionKind.COLONOSCOPY), X2: session(SessionKind.EGD)}
        for name, R in (('a card naming another session', self.biopsy_beside('unlisted act', card=X2, sessions=two)),
                        ('a dilation kept unlisted', self.biopsy_beside('unlisted act', whole=Kind.DILATION))):
            with self.subTest(name):
                self.assertEqual((C.bundles(R, E3), C.verdict(R, E3).truth), ((), T))
        R = build({E1: exam(), E3: act(Kind.BIOPSY, lesion=sup(L1))}, unlisted=(unlisted(U_DENIAL, Kind.SNARE, X1),),
                  lesions={L1: lesion(ct.Multiplicity.SINGLE)})
        self.assertEqual(C.bundles(R, E3), ())
        R = self.biopsy_beside('unlisted act, no card', sessions=two)
        self.assertEqual([(bundle.rule, bundle.unlisted, bundle.truth) for bundle in C.bundles(R, E3)],
                         [(C.Rule.BIOPSY_OF_REMOVED_LESION, 0, U)])

    def test_c1_every_whole_rule_reads_it_as_its_filed_doubted_form(self):
        """The lift (an injection for lift of L1 beside an EMR), the resection technique (a snare of L1 beside an EMR),
        the procedural adjunct (a bleeding control caused by an act of this session, its cause_event not stated, beside
        a snare), the stent row (an ERCP sphincterotomy of the biliary duct beside a stent placement) and the drainage
        step (an FNA beside a drainage): the whole told in each form - the same truth for the unlisted act, the unlisted
        doubt and the filed doubted form, U each time."""
        cases = (
            # the injection's part_of stated (round r3's integration: the lift read, never the silent link, b.8)
            ('lift', act(Kind.INJECTION, lesion=sup(L1), purpose=sup(Purpose.LIFT_FOR_RESECTION),
                         part_of=STATED_LINK['part_of']), Kind.EMR, SessionKind.COLONOSCOPY, C.Rule.LIFT_INJECTION),
            ('technique', act(Kind.SNARE, lesion=sup(L1)), Kind.EMR, SessionKind.COLONOSCOPY,
             C.Rule.RESECTION_TECHNIQUE),
            ('adjunct', act(Kind.BLEEDING_CONTROL, cause=sup(Cause.ACT_OF_THIS_SESSION)), Kind.SNARE,
             SessionKind.COLONOSCOPY, C.Rule.PROCEDURAL_ADJUNCT),
            ('stent', act(Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY)), Kind.STENT, SessionKind.ERCP,
             C.Rule.STENT_INCLUDED),
            ('drainage', act(Kind.FNA), Kind.DRAINAGE, SessionKind.EUS, C.Rule.DRAINAGE_STEP))
        for name, part, whole, family, rule in cases:
            for form in TOLD:
                with self.subTest(rule=name, form=form):
                    events, entries = with_told({E1: exam(), E3: part}, form, whole, X1)
                    R = build(events, sessions={X1: session(family, tract=ct.Tract.UPPER if family is
                                                            SessionKind.EUS else None)},
                              lesions={L1: lesion(ct.Multiplicity.SINGLE)}, unlisted=entries)
                    self.assertEqual([(bundle.rule, bundle.truth) for bundle in C.bundles(R, E3)
                                      if bundle.whole == E5 or bundle.unlisted is not None], [(rule, U)])
                    self.assertEqual(C.verdict(R, E3).truth, U)

    def test_c1_monotone_and_never_a_released_code(self):
        """9.4 P-MONO over the C1 scenes with an unlisted snare (strong_weakenings: an established fact unresolved,
        doubted or contradicted, a doubt on an empty slot, a deleted member, a control not rejected): the biopsy's
        verdict never turns T and it never stops being doubted. The kept entry is no fact a weakening changes."""
        checked = 0
        for form in TOLD[:4]:
            R = self.biopsy_beside(form)
            for change in strong_weakenings(R):
                weak = strong_weaken(R, change)
                with self.subTest(form=form, change=change[:4]):
                    self.assertNotEqual(C.verdict(weak, E3).truth, T)
                    self.assertTrue(C.doubted(weak, E3))
                    checked += 1
        self.assertGreater(checked, 100)


class SyntheticExaminationLeftOpen(SimpleTestCase):
    """DECISIONS D231's coverage half, C2 (its row 1; D232): the session's possible examinations read a synthetic act of
    kind examination or none that may be in the session (step 4d's combination.synthetic_examinations) - in a session
    told only through its acts it is an examination left open (Session.possible_unlisted), so the session is not done,
    as with its filed doubted form (round 2: done, while 4d read it not done); beside an established examination it
    adds nothing (D232). 4d's session_done answers alike."""

    def act_only(self, form, *, kind=Kind.EXAMINATION, card=X1, sessions=None, extra=None):
        events, entries = with_told({E2: act(Kind.BIOPSY, places=(sup(Landmark.STOMACH),)), **(extra or {})}, form,
                                    kind, card)
        return build(events, sessions=sessions or {X1: session(SessionKind.EGD)}, unlisted=entries)

    def test_c2_an_unlisted_act_a_doubt_and_the_filed_doubted_form_give_one_outcome(self):
        """The done-when: an EGD X1 told only through a done biopsy E2, its examination told in each form - not done,
        no examination, none recorded as its one examination, not unresolved; the unlisted forms recorded as
        possible_unlisted (0,), the filed one as possible (E5,). An unlisted act naming no kind may be the
        examination too. Nothing told: done."""
        for form in TOLD:
            with self.subTest(form):
                R = self.act_only(form)
                record = C.sessions(R)[X1]
                self.assertEqual((record.done, record.examinations, record.event, record.unresolved),
                                 (False, (), None, False))
                self.assertFalse(CB.session_done(R, X1))
                filed = form == 'filed in doubt'
                self.assertEqual((record.possible, record.possible_unlisted),
                                 ((E5,), ()) if filed else ((), (0,)))
                self.assertFalse(C.event_coding(R, C.sessions(R), {})['sessions']['X1']['done'])
        R = self.act_only('unlisted act', kind=None)
        self.assertEqual((C.sessions(R)[X1].done, C.sessions(R)[X1].possible_unlisted), (False, (0,)))
        R = build({E2: act(Kind.BIOPSY, places=(sup(Landmark.STOMACH),))}, sessions={X1: session(SessionKind.EGD)})
        self.assertEqual((C.sessions(R)[X1].done, CB.session_done(R, X1)), (True, True))

    def test_c2_controls_and_d232(self):
        """Done, the synthetic act read nowhere: a card naming another session; an unlisted DENIAL of an examination;
        an unlisted act of another kind (a snare); and beside an established done examination E1 (D232: a synthetic
        examination adds nothing there - no possible_unlisted, the session's one examination still E1). Two unlisted
        examinations in an act-only session leave it unresolved, as two filed ones would."""
        two = {X1: session(SessionKind.EGD), X2: session(SessionKind.COLONOSCOPY)}
        for name, R in (('a card naming another session', self.act_only('unlisted act', card=X2, sessions=two)),
                        ('a snare kept unlisted', self.act_only('unlisted act', kind=Kind.SNARE)),
                        ('beside an established done examination', self.act_only('unlisted doubt',
                                                                                 extra={E1: exam()}))):
            with self.subTest(name):
                record = C.sessions(R)[X1]
                self.assertEqual((record.done, record.possible_unlisted, CB.session_done(R, X1)), (True, (), True))
        R = build({E2: act(Kind.BIOPSY)}, sessions={X1: session(SessionKind.EGD)},
                  unlisted=(unlisted(U_DENIAL, Kind.EXAMINATION, X1),))
        self.assertEqual((C.sessions(R)[X1].done, C.sessions(R)[X1].possible_unlisted), (True, ()))
        R = self.act_only('unlisted doubt', extra={E1: exam()})
        self.assertEqual(C.sessions(R)[X1].event, E1)
        R = build({E2: act(Kind.BIOPSY)}, sessions={X1: session(SessionKind.EGD)},
                  unlisted=(unlisted(U_ACT, Kind.EXAMINATION, X1), unlisted(U_DOUBT, None, None, 6)))
        record = C.sessions(R)[X1]
        self.assertEqual((record.done, record.possible_unlisted, record.unresolved), (False, (0, 1), True))


class SyntheticActMayMakeAWhole(SimpleTestCase):
    """DECISIONS D231's coverage half, C3 (its row 2; D227's one derivation): D70's possible whole in _part_of_session
    reads step 4d's combination.session_possibly_done, the reference - a synthetic act with card S, or no card, or a
    card the FactSet does not hold, makes S possibly done, as the same act filed in doubt does. Round 2 read only the
    session's filed possible members: an upper EUS told only by an unlisted FNA was no possible whole of the EGD."""

    def egd_beside_eus(self, form, *, card=X2):
        events, entries = with_told({E1: exam(session=sup(X1))}, form, Kind.FNA, card)
        return build(events, sessions={X1: session(SessionKind.EGD, reached=(sup(Landmark.DUODENUM),)),
                                       X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)}, unlisted=entries)

    def test_c3_an_unlisted_act_a_doubt_and_the_filed_doubted_form_give_one_outcome(self):
        """The done-when: a done EGD X1 beside an upper EUS X2 with no event of its own, its FNA told in each form - the
        EGD possibly part of X2 (and recorded so), as 4d reads X2 possibly done; with nothing told, part of nothing."""
        for form in TOLD:
            with self.subTest(form):
                R = self.egd_beside_eus(form)
                record = C.sessions(R)[X1]
                self.assertEqual((record.part_of, record.possibly_part_of), (None, X2))
                self.assertTrue(CB.session_possibly_done(R, X2))
                self.assertEqual(C.event_coding(R, C.sessions(R), {})['sessions']['X1']['possibly_part_of'], 'X2')
        R = build({E1: exam(session=sup(X1))}, sessions={X1: session(SessionKind.EGD), X2: session(
            SessionKind.EUS, tract=ct.Tract.UPPER)})
        self.assertEqual((C.sessions(R)[X1].possibly_part_of, CB.session_possibly_done(R, X2)), (None, False))

    def test_c3_controls_and_the_reference(self):
        """The FNA kept unlisted with a card naming the EGD X1: X2 may not be done, part of nothing. A card naming a
        session the FactSet does not hold (X9) may be any session's: possibly part of X2. D70's "may be done" is 4d's
        (session_possibly_done) on every scene here: an act the nursing entry tells now counts as 4d counts it."""
        R = self.egd_beside_eus('unlisted act', card=X1)
        self.assertEqual((C.sessions(R)[X1].possibly_part_of, CB.session_possibly_done(R, X2)), (None, False))
        R = self.egd_beside_eus('unlisted doubt', card=X9)
        self.assertEqual((C.sessions(R)[X1].possibly_part_of, CB.session_possibly_done(R, X2)), (X2, True))
        R = build({E1: exam(session=sup(X1)), E3: act(Kind.FNA, session=sup(X2), date=unres(ON),
                                                      entry=sup(NURSING))},
                  sessions={X1: session(SessionKind.EGD), X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)})
        self.assertEqual((C.sessions(R)[X1].possibly_part_of, CB.session_possibly_done(R, X2)), (X2, True))


class UnestablishedCountReadsTheSyntheticAct(SimpleTestCase):
    """DECISIONS D216 over coverage.py's absence conditions (the step's NOTES list them): the unestablished count's "an
    event possibly in it possibly positive here" reads the synthetic act too - an upper EUS X2 told only by an FNA kept
    unlisted (act or doubt, carded X2 or with no card) beside a done colonoscopy X1 coded 45378 is counted
    unestablished, as the same FNA filed in doubt is (round 2 counted no unlisted form: no filed member)."""

    def test_d216_the_count(self):
        counted = [C.Counted('sel:0', '45378', SessionKind.COLONOSCOPY, (E1,))]
        for form in TOLD:
            with self.subTest(form):
                events, entries = with_told({E1: exam(session=sup(X1))}, form, Kind.FNA, X2)
                R = build(events, sessions={X1: session(SessionKind.COLONOSCOPY, reached=(sup(Landmark.CECUM),)),
                                            X2: session(SessionKind.EUS, tract=ct.Tract.UPPER)}, unlisted=entries)
                cov = C.reconcile(R, counted, procedure_day=True)
                self.assertEqual((cov.unestablished, state(R, cov)), (1, 'incomplete'))
        R = build({E1: exam(session=sup(X1))}, sessions={X1: session(SessionKind.COLONOSCOPY), X2: session(
            SessionKind.EUS, tract=ct.Tract.UPPER)})
        self.assertEqual(C.reconcile(R, counted, procedure_day=True).unestablished, 0)


# refute-r4b-r2 n1's scene: an EGD X1 (its done examination E1 and a done gastric biopsy E3, 43239 counted on E3) or two
# colonoscopies (45380), and a second session X2 of the same family holding its examination E5; both state their reach.
N1_PLACE = {SessionKind.EGD: Landmark.GASTRIC_BODY, SessionKind.COLONOSCOPY: Landmark.SIGMOID_COLON}
N1_REACH = {SessionKind.EGD: Landmark.DUODENUM, SessionKind.COLONOSCOPY: Landmark.CECUM}
N1_CODE = {SessionKind.EGD: '43239', SessionKind.COLONOSCOPY: '45380'}


def second_session(family, e5, *, x2_act=None) -> FactSet:
    events = {E1: exam(session=sup(X1)), E3: act(Kind.BIOPSY, session=sup(X1), places=(sup(N1_PLACE[family]),)),
              E5: e5}
    if x2_act is not None:
        events[E6] = x2_act
    reach = (sup(N1_REACH[family]),)
    return build(events, sessions={X1: session(family, reached=reach), X2: session(family, reached=reach)})


def held_by_rows(R: FactSet, counted) -> int:
    """refute-r4b-r2's monotone model of step 4a's rows 1-7 (its mono_search_sessions, copied): a counted code one of
    whose supporting or read events is not done, or whose session or its kind is not supported, or whose session is not
    done - each an open question of the assessment."""
    sessions_ = C.sessions(R)
    held = 0
    for item in counted:
        for event in tuple(item.supporting) + tuple(item.read):
            filed_in = F.fact(R, event, A.SESSION).value
            if (not C._done(R, event) or F.session_family(R, event) is None or filed_in not in sessions_
                    or not sessions_[filed_in].done):
                held += 1
                break
    return held


def assessed_state(R: FactSet, counted) -> str:
    """Completeness with the open questions the assessment counts (v1's assess.py: the codes' items - held_by_rows'
    model of 4a's rows 1-7 - plus the in-doubt and the extent service questions)."""
    cov = C.reconcile(R, counted, procedure_day=True)
    sessions_ = C.sessions(R)
    service = len(C.in_doubt_questions(R, cov)) + len(C.service_extent_questions(R, sessions_))
    return C.completeness(cov, sessions_, open_questions=held_by_rows(R, counted) + service, provider_ok=True,
                          conflicts=0, label=label)['state']


class ReadByNoCountedCodePerSession(SimpleTestCase):
    """DECISIONS D248 G1 (refute-r4b-r2 G1, n1; medium, a false complete): "read by no counted code" is read per session -
    no counted code's events possibly in it - for the unestablished count and the R5 gate alike. A second session of a
    coded family that a weakening makes not done stays incomplete (round 2: its no_proposal item vanished, the count
    skipped it because a code of its FAMILY was counted elsewhere, and completeness read complete_pending_review)."""

    def test_g1_a_second_session_of_a_coded_family_stays_incomplete(self):
        """n1, both families: X2 done - its no_proposal item; X2 made not done by one 9.4 weakening of E5 (its date
        relation unresolved, its status unresolved, a doubt on its performer) - counted unestablished, nothing listed,
        completeness incomplete with no open question counted (43239 or 45380 is READY on E3 in 4a). Controls: no
        counted code (X1 no_proposal, X2 counted); a done dilation in X2 (X2 counted: no code's event may be in it)."""
        for family in (SessionKind.EGD, SessionKind.COLONOSCOPY):
            counted = [C.Counted('sel:0', N1_CODE[family], family, (E3,))]
            R = second_session(family, exam(session=sup(X2)))
            cov = C.reconcile(R, counted, procedure_day=True)
            self.assertEqual(([(item.session, item.reason) for item in cov.unresolved], cov.unestablished),
                             ([(X2, C.ItemReason.NO_PROPOSAL)], 0))
            for name, e5 in (('date relation unresolved', exam(session=sup(X2), date=unres(ON))),
                             ('status unresolved', exam(session=sup(X2), status=unres(PERFORMED))),
                             ('performer doubted', exam(session=sup(X2), performer=doubted(TEAM)))):
                with self.subTest(family=family.value, weakened=name):
                    R = second_session(family, e5)
                    self.assertFalse(C.sessions(R)[X2].done)
                    cov = C.reconcile(R, counted, procedure_day=True)
                    self.assertEqual((cov.unresolved, cov.unestablished, state(R, cov)), ([], 1, 'incomplete'))
                    self.assertEqual(assessed_state(R, counted), 'incomplete')
            R = second_session(family, exam(session=sup(X2), date=unres(ON)))
            cov = C.reconcile(R, [], procedure_day=True)
            self.assertEqual(([(item.session, item.reason) for item in cov.unresolved], cov.unestablished),
                             ([(X1, C.ItemReason.NO_PROPOSAL)], 1))
            R = second_session(family, exam(session=sup(X2), date=unres(ON)), x2_act=act(Kind.DILATION,
                                                                                         session=sup(X2)))
            cov = C.reconcile(R, counted, procedure_day=True)
            self.assertEqual((cov.unresolved, cov.unestablished, state(R, cov)), ([], 1, 'incomplete'))

    def test_g1_a_code_whose_event_may_be_in_the_session_reads_it(self):
        """The same predicate the other way: 43235 counted on X2's own examination E5 (not done) reads X2, so X2 is not
        counted and its member acts are read as a done session's (the R5 gate) - its done dilation listed; and a code
        whose event's session is open between X1 and X2 (a doubt with both readings) reads both."""
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E3,)), C.Counted('sel:1', '43235',
                                                                                SessionKind.EGD, (E5,))]
        R = second_session(SessionKind.EGD, exam(session=sup(X2), date=unres(ON)),
                           x2_act=act(Kind.DILATION, session=sup(X2)))
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual(([(item.session, item.reason, item.events) for item in cov.unresolved], cov.unestablished),
                         ([(X2, C.ItemReason.NOT_COVERED, (E6,))], 0))
        item = C.Counted('sel:2', '43239', SessionKind.EGD, (E7,))
        R = build({E7: act(Kind.BIOPSY, session=doubted(X1, X1, X2))}, sessions={X1: session(SessionKind.EGD),
                                                                               X2: session(SessionKind.EGD)})
        self.assertEqual([C._counted_family(R, record, [item]) for record in C.sessions(R).values()], [True, True])

    def test_g6_every_family_the_session_is_stated_as(self):
        """refute-r4b-r2 G6 (mutant MR5_COUNTED_ANY: ANY in place of ALL survived): a session whose kind is a doubt
        between the EGD and the EUS, its examination E5 not done (its date unresolved), read by an EGD code (43235 on
        E5) and by no EUS code - as an EUS it is read by no proposal: counted unestablished, completeness incomplete
        with no open question counted. ANY would read it through the R5 gate, list nothing and skip the count. With an
        EUS code reading it too (43259 on E5), it is read under every reading: not counted."""
        R = build({E1: exam(session=sup(X1)), E3: act(Kind.BIOPSY, session=sup(X1)),
                   E5: exam(session=sup(X2), date=unres(ON))},
                  sessions={X1: session(SessionKind.EGD), X2: session(doubted(SessionKind.EGD, SessionKind.EGD,
                                                                              SessionKind.EUS))})
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E3,)), C.Counted('sel:1', '43235', SessionKind.EGD,
                                                                                (E5,))]
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual((cov.unresolved, cov.unestablished, state(R, cov)), ([], 1, 'incomplete'))
        both = counted + [C.Counted('sel:2', '43259', SessionKind.EUS, (E5,))]
        self.assertEqual(C.reconcile(R, both, procedure_day=True).unestablished, 0)

    def test_g1_no_weakening_turns_completeness_complete(self):
        """refute-r4b-r2's own search at the records (its tools/mono_search_sessions.py, seeds 31 and 37, a smaller
        count of trials here; the step's NOTES run the full 300 each): 2-3 sessions with ONE family repeated, codes
        counted for only some sessions; every strong_weakening but the contradictions (a conflict the assessment
        counts); completeness read with held_by_rows' open questions never turns complete. Round 2: 200 and 280
        violating weakenings in 300 trials (every one "same family twice")."""
        checked = 0
        for seed in (31, 37):
            rng = random.Random(seed)
            for _ in range(40):
                R, counted = sessions_scene(rng)
                if assessed_state(R, counted) != 'incomplete':
                    continue
                for change in strong_weakenings(R):
                    if change[4] is not None and change[4].result is Res.CONTRADICTED:
                        continue
                    with self.subTest(seed=seed, change=change[:4]):
                        self.assertEqual(assessed_state(strong_weaken(R, change), counted), 'incomplete')
                        checked += 1
        self.assertGreater(checked, 2000)


def sessions_scene(rng: random.Random) -> tuple[FactSet, list]:
    """refute-r4b-r2's mono_search_sessions scene and codes (copied): 2-3 sessions, families drawn with repeats among the
    EGD, the colonoscopy and the upper EUS, each EGD and colonoscopy stating its reach; most with an examination, 0-2
    biopsies, snares or dilations; base and biopsy codes for a random non-empty subset of the sessions."""
    families_ = [SessionKind.EGD, SessionKind.COLONOSCOPY, SessionKind.EUS]
    code = {SessionKind.EGD: '43235', SessionKind.EUS: '43259', SessionKind.COLONOSCOPY: '45378'}
    biopsy_code = {SessionKind.EGD: '43239', SessionKind.COLONOSCOPY: '45380'}
    place = {SessionKind.EGD: Landmark.GASTRIC_BODY, SessionKind.EUS: Landmark.DUODENUM,
             SessionKind.COLONOSCOPY: Landmark.SIGMOID_COLON}
    reach = {SessionKind.EGD: Landmark.DUODENUM, SessionKind.COLONOSCOPY: Landmark.CECUM}
    count = rng.choice([2, 2, 3])
    first_family = rng.choice(families_)
    families = [first_family] + [rng.choice([first_family, first_family] + families_) for _ in range(count - 1)]
    sessions_ = {sid: session(family, tract=ct.Tract.UPPER if family is SessionKind.EUS else None,
                              reached=(sup(reach[family]),) if family in reach else ())
                 for sid, family in zip((X1, X2, X3), families)}
    events, number = {}, 1
    for sid, family in zip((X1, X2, X3), families):
        if rng.random() < 0.9:
            events[Id(IdFamily.EVENT, number)] = exam(session=sup(sid))
            number += 1
        for _ in range(rng.choice([0, 0, 1, 2])):
            kind = rng.choice([Kind.BIOPSY, Kind.SNARE, Kind.DILATION])
            events[Id(IdFamily.EVENT, number)] = act(kind, session=sup(sid), places=(sup(place[family]),))
            number += 1
    R = build(events, sessions=sessions_)
    out = []
    records = list(C.sessions(R).values())
    chosen = [record for record in records if rng.random() < 0.5] or [records[0]]
    for record in chosen:
        exams = C._examinations(R, record.id)
        members = [event for event in record.events if event not in exams]
        if record.kind in code and exams:
            out.append(C.Counted(f'sel:{len(out)}', code[record.kind], record.kind, (exams[0],)))
        if record.kind in biopsy_code:
            biopsies = [event for event in members if F.holds(F.fact(R, event, A.KIND), Kind.BIOPSY)]
            if biopsies:
                out.append(C.Counted(f'sel:{len(out)}', biopsy_code[record.kind], record.kind, (biopsies[0],)))
    return R, out


class UnknownIdentityAsksItsLesion(SimpleTestCase):
    """DECISIONS D248 G2 (refute-r4b-r2 G2, n2; option (b)): D221's F applies only when BOTH lesion facts are supported.
    A lesion fact that is not supported - unresolved, contradicted, doubted (or negated) - gives U with the lesion
    question (4.11: an unknown identity never sets two acts apart in the adjunct rule); round 2 read it by possibly and
    released 45388 beside the EMR whose lesion the ablation may have treated."""

    def apc_beside_emr(self, apc_lesion, emr_lesion=None):
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3)}
        return build({E1: exam(), E2: act(Kind.EMR, lesion=emr_lesion or sup(L1)),
                      E3: act(Kind.ABLATION, **STATED_LINK, lesion=apc_lesion)}, lesions=lesions)

    def test_g2_n2(self):
        """n2: the APC E3 beside the EMR E2 of L1 (supported), entries L1-L3, no same_as, part_of or cause: (a) its
        lesion supported L2 - different findings, not held by the bundling row (D221); (b) unresolved L2, (c)
        contradicted L2 | L3, (d) doubted L2 reading L3 - U, 45388 held by questions, the lesion question first both
        in the bundling row's order and in step 4a's (4.8: rank, then subject - the part's own two facts tie, and the
        lesion comes first): act_target at rank 17, or for (c) the lesion's conflict at rank 1."""
        R = self.apc_beside_emr(sup(L2))
        self.assertEqual((C.bundles(R, E3), C.verdict(R, E3).truth, C.bundling('45388', (E3,), R)), ((), T, ()))
        for name, found, top in (('(b) unresolved L2', unres(L2), ('act_target', 17)),
                                 ('(c) contradicted L2 | L3', contra(L2, L3), ('conflict:ablation', 1)),
                                 ('(d) doubted L2, reading L3', doubted(L2, L3), ('act_target', 17))):
            with self.subTest(name):
                R = self.apc_beside_emr(found)
                self.assertEqual(rules(R, E3), [(C.Rule.PROCEDURAL_ADJUNCT, E2, U)])
                held = C.bundling('45388', (E3,), R)
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                for item in (held[0], Q.ranked(held, R)[0]):
                    self.assertEqual((item.fact, item.rank, item.subject, item.attribute), (*top, E3,
                                                                                            A.TARGET_LESION))

    def test_g2_either_side_and_a_negation(self):
        """The EMR's lesion unresolved beside the APC's supported L2: U, the EMR's lesion asked (the lesion question of
        the side not supported); the APC's lesion negated ("not L1", established - no supported id): U, asked."""
        R = self.apc_beside_emr(sup(L2), emr_lesion=unres(L1))
        held = C.bundling('45388', (E3,), R)
        self.assertEqual((held[0].fact, held[0].subject, held[0].attribute), ('act_target', E2, A.TARGET_LESION))
        R = self.apc_beside_emr(neg(L1))
        held = C.bundling('45388', (E3,), R)
        self.assertEqual((rules(R, E3), held[0].fact, held[0].subject, held[0].attribute),
                         ([(C.Rule.PROCEDURAL_ADJUNCT, E2, U)], 'act_target', E3, A.TARGET_LESION))


class ContradictedIdentityIsAsked(SimpleTestCase):
    """DECISIONS D248 G3 (refute-r4b-r2 G3, n6): supported same_as members joining two lesions beside a claim that they
    are NOT one finding - a negated same_as member ("L2 is not the same as L3"), or a distinct_from - are the FactSet
    contradicting itself on the two lesions' identity: asked (the claim first), never explained (S4: contradictions are
    never resolved by bundling). Round 2 explained the biopsy as part of the snare through the chain."""

    def biopsy_beside_snare(self, l1_links, l2_links, *, distinct=False, l2_distinct=None):
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3)}
        lesions[L1] = {**lesions[L1], A.SAME_AS: tuple(l1_links)}
        lesions[L2] = {**lesions[L2], A.SAME_AS: tuple(l2_links)}
        controls_ = None
        if distinct:
            lesions[L2] = {**lesions[L2], A.DISTINCT_FROM: (l2_distinct or sup(L3),)}
            lesions[L3] = {**lesions[L3], A.DISTINCT_FROM: (sup(L2),)}
            controls_ = lesion_controls(E4, L2, E2, L3)
        here = (sup(Landmark.ASCENDING_COLON),)
        return build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L3), places=here),
                      E4: act(Kind.BIOPSY, lesion=sup(L2), places=here)}, lesions=lesions, controls=controls_)

    def test_g3_n6(self):
        """n6: (i) L2 = L1 and L1 = L3 by supported members, L2's same_as list naming L3 NEGATED; (ii) the same with
        distinct_from L2-L3 supported both ways and the lesion pair controls rejected - U, 45380 held by questions,
        the negated member first (act_target, rank 17, about L2's same_as); the negation weakened (unresolved, its
        claim still a negation) is asked as well."""
        for name, R in (('(i) the negation', self.biopsy_beside_snare([sup(L3)], [sup(L1), neg(L3)])),
                        ('(ii) and distinct_from with its controls',
                         self.biopsy_beside_snare([sup(L3)], [sup(L1), neg(L3)], distinct=True)),
                        ('the negation left open', self.biopsy_beside_snare(
                            [sup(L3)], [sup(L1), unres(L3, state=State.NEGATED)]))):
            with self.subTest(name):
                self.assertEqual(rules(R, E4), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])
                held = C.bundling('45380', (E4,), R)
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute),
                                 ('act_target', 17, L2, A.SAME_AS))
                self.assertIsNone(C.bundled(R, E4))
        R = self.biopsy_beside_snare([sup(L3)], [sup(L1)], distinct=True, l2_distinct=unres(L3))
        held = C.bundling('45380', (E4,), R)
        self.assertEqual((rules(R, E4), held[0].subject, held[0].attribute),
                         ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)], L2, A.DISTINCT_FROM))

    def test_g3_controls(self):
        """The chain alone: one finding, explained (T, bundled). The negation alone: asked on the lesion (no chain to
        contradict); with distinct_from and its controls: apart, the biopsy its own act. The two acts of one lesion id
        are one finding whatever other entries say."""
        R = self.biopsy_beside_snare([sup(L3)], [sup(L1)])
        self.assertEqual((rules(R, E4), C.verdict(R, E4).truth), ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)], FF))
        R = self.biopsy_beside_snare([], [neg(L3)])
        self.assertEqual(rules(R, E4), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])
        self.assertEqual(C.bundling('45380', (E4,), R)[0].attribute, A.TARGET_LESION)
        R = self.biopsy_beside_snare([], [neg(L3)], distinct=True)
        self.assertEqual((C.bundles(R, E4), C.verdict(R, E4).truth), ((), T))
        here = (sup(Landmark.ASCENDING_COLON),)
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L2), places=here),
                   E4: act(Kind.BIOPSY, lesion=sup(L2), places=here)},
                  lesions={L1: lesion_entry(sup(L2)), L2: lesion_entry(neg(L1)), L3: lesion_entry()})
        self.assertEqual(rules(R, E4), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)])

    def test_g3_the_adjunct_arm_asks_the_claim(self):
        """D221's identity reads the same claim: the APC of L2 beside the EMR of L3, joined by supported members through
        L1, L2's list naming L3 negated - U, the negated member asked first, then the part_of."""
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3)}
        lesions[L1] = {**lesions[L1], A.SAME_AS: (sup(L3),)}
        lesions[L2] = {**lesions[L2], A.SAME_AS: (sup(L1), neg(L3))}
        R = build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L3)), E3: act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2))},
                  lesions=lesions)
        held = C.bundling('45388', (E3,), R)
        self.assertEqual([(item.fact, item.subject, item.attribute) for item in held[:2]],
                         [('act_target', L2, A.SAME_AS), ('act_part', E3, A.PART_OF)])


class OneEntryPerAct(SimpleTestCase):
    """DECISIONS D248 G4 (refute-r4b-r2 G4, n5): beside a session whose kind is not established, two readings listing
    one act differently - an EUS biopsy read under the upper endoscopy with its sites not established (in doubt) and an
    upper-endoscopy biopsy no code reads (not covered) - list it ONCE: the in-doubt listing, its question kept (round
    2: two items for one act, "2 documented services or acts without a supported proposal")."""

    def test_g4_n5(self):
        R = build({E1: exam(session=sup(X1)), E3: act(Kind.BIOPSY, session=sup(X1),
                                                      places=(sup(Landmark.GASTRIC_BODY),)),
                   E2: exam(session=sup(X2)), E4: act(Kind.BIOPSY, session=sup(X2),
                                                      places=(sup(Landmark.GASTRIC_BODY),))},
                  sessions={X1: session(SessionKind.EGD),
                            X2: session(doubted(SessionKind.EUS, SessionKind.EUS, SessionKind.EGD),
                                        tract=ct.Tract.UPPER)})
        counted = [C.Counted('sel:0', '43239', SessionKind.EGD, (E3,)), C.Counted('sel:1', '43259', SessionKind.EUS,
                                                                                (E2,)),
                   C.Counted('sel:2', '43235', SessionKind.EGD, (E2,))]
        cov = C.reconcile(R, counted, procedure_day=True)
        self.assertEqual([(item.session, item.family, item.reason, item.detail, item.events)
                          for item in cov.unresolved if E4 in item.events],
                         [(X2, None, C.ItemReason.IN_DOUBT, C.Detail.READ_UNDER_NOT_ESTABLISHED, (E4,))])
        self.assertEqual([ref.event for _, ref in cov.in_doubt], [E4])
        comp = C.completeness(cov, C.sessions(R), open_questions=0, provider_ok=True, conflicts=0, label=label)
        self.assertIn('1 documented service or act without a supported proposal', comp['statement'])


# FINAL-V2 1.8's bounds, refute-r4b-r2's c1 shape: lesions 64, same_as 16 per lesion (unresolved members naming another
# entry, three readings each, every tenth a missing id), events 200 (an examination and 199 acts of eight kinds, each
# naming a lesion).
def bounds_scene() -> FactSet:
    rng = random.Random(20261114)
    lesion_ids = [Id(IdFamily.LESION, n) for n in range(1, 65)]
    missing = [Id(IdFamily.LESION, 100 + n) for n in range(1, 9)]
    lesions = {}
    for lesion_id in lesion_ids:
        others = [other for other in lesion_ids if other != lesion_id]
        members = []
        for _ in range(16):
            value = rng.choice(missing) if rng.random() < 0.1 else rng.choice(others)
            members.append(unres(value, options=tuple(rng.sample(others, 3))))
        lesions[lesion_id] = {A.PLACES: (sup(Landmark.ASCENDING_COLON),), A.DISTINCT_FROM: (),
                              A.SAME_AS: tuple(members), A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
    kinds = [Kind.SNARE, Kind.ABLATION, Kind.BIOPSY, Kind.EMR, Kind.INJECTION, Kind.BLEEDING_CONTROL, Kind.FNA,
             Kind.HOT_BIOPSY]
    events = {E1: exam()}
    for number in range(2, 201):
        events[Id(IdFamily.EVENT, number)] = act(kinds[number % len(kinds)], lesion=sup(lesion_ids[number % 64]),
                                                 places=(sup(Landmark.ASCENDING_COLON),))
    return build(events, lesions=lesions)


class SameAsWalkCost(SimpleTestCase):
    """DECISIONS D248 G5 (refute-r4b-r2 G5; c1_cost_bounds.py): the same_as walk runs once per start set - once per part
    and once per whole lesion set, memoized on the Reader (_SameAs) - never once per (part, whole) pair: round 2 ran
    about parts x events walks, 387.8 s at FINAL-V2 1.8's bounds against round 1's 6.4 s. Counted, not timed (a
    wall-clock bound is a load test: the step's NOTES time it, and the assess job's deadline is a coarse bound here)."""

    def test_g5_the_walk_runs_once_per_start_set(self):
        R = bounds_scene()
        starts: list = []
        real = C._walk

        def counting(graph, start):
            starts.append(frozenset(start))
            return real(graph, start)

        began = time.perf_counter()
        with mock.patch.object(C, '_walk', counting):
            reader = C.Reader(R)
            verdicts = [reader.verdict(event).truth for event in R.events]
        elapsed = time.perf_counter() - began
        self.assertEqual(len(starts), len(set(starts)))  # no start set walked twice
        self.assertLessEqual(len(starts), 64 + 8 + 1)  # at most one walk per lesion id (and missing id) reached
        self.assertEqual(verdicts.count(U), 149)  # refute-r4b-r2 c1's count: the readings are unchanged
        self.assertLess(elapsed, 120)  # settings.JOB_DEADLINE_SECONDS['assess'], of which coverage is one part


class ZeroOneWalk(SimpleTestCase):
    """refute-r4b-r2 G7 (mutant MR1_WALK_NOT_01 - a supported member queued at the back, a plain breadth-first walk -
    survived): _walk finds, for each id, the chain with the fewest members NOT supported, so a join asks the open
    member of the cheapest chain, not of the shortest."""

    def two_chains(self):
        """L2 to L3: a short chain of two open members (L2 -?- L4 -?- L3) and a longer one of one open member (L2 = L5 =
        L6 -?- L3, the first two supported); no chain of supported members alone."""
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3, L4, L5, L6)}
        lesions[L2] = {**lesions[L2], A.SAME_AS: (unres(L4), sup(L5))}
        lesions[L4] = {**lesions[L4], A.SAME_AS: (unres(L3),)}
        lesions[L5] = {**lesions[L5], A.SAME_AS: (sup(L6),)}
        lesions[L6] = {**lesions[L6], A.SAME_AS: (unres(L3),)}
        return build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L3)), E3: act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2))},
                     lesions=lesions)

    def test_g7_the_walk_counts_open_members(self):
        R = self.two_chains()
        cost, chain = C._walk(C._same_as_graph(R), {L2})[L3]
        self.assertEqual((cost, [holder for holder, _member in chain]), (1, [L2, L5, L6]))

    def test_g7_the_join_asks_the_cheapest_chains_open_member(self):
        """The APC of L2 beside the EMR of L3: U, the same_as asked first is L6's (the cheapest chain's one open member),
        never L2's (the shortest chain's first)."""
        R = self.two_chains()
        held = C.bundling('45388', (E3,), R)
        self.assertEqual((held[0].fact, held[0].subject, held[0].attribute), ('act_target', L6, A.SAME_AS))

    def test_g7_a_supported_chain_beside_an_open_shortcut(self):
        """refute-r4b-r2 n3: L2's list holds L3 (unresolved) and L1 (supported), L1's holds L3 (supported) - L2 = L1 = L3
        by supported members: a biopsy of L2 beside the snare of L3 is bundled (explained), and the APC of L2 beside the
        EMR of L3 asks its part_of first."""
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3)}
        lesions[L2] = {**lesions[L2], A.SAME_AS: (unres(L3), sup(L1))}
        lesions[L1] = {**lesions[L1], A.SAME_AS: (sup(L3),)}
        here = (sup(Landmark.ASCENDING_COLON),)
        R = build({E1: exam(), E2: act(Kind.SNARE, lesion=sup(L3), places=here),
                   E4: act(Kind.BIOPSY, lesion=sup(L2), places=here)}, lesions=lesions)
        self.assertEqual((rules(R, E4), C.verdict(R, E4).truth), ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)], FF))
        R = build({E1: exam(), E2: act(Kind.EMR, lesion=sup(L3), places=here),
                   E3: act(Kind.ABLATION, **STATED_LINK, lesion=sup(L2), places=here)}, lesions=lesions)
        held = C.bundling('45388', (E3,), R)
        self.assertEqual((held[0].fact, held[0].subject, held[0].attribute), ('act_part', E3, A.PART_OF))


# --- repair r4b-2 (refute-r4b-r1 F1-F3): one finding is never set apart by place while it may hold --------------------


ASC, SIG = Landmark.ASCENDING_COLON, Landmark.SIGMOID_COLON
# The four SAME LESION rules (refute-r4b-r1's mono_search_places.py): (part kind, whole kind, the part's other facts, the
# session's family, the rule, a code the part supports).
SAME_LESION_PAIRS = {
    'biopsy beside a snare': (Kind.BIOPSY, Kind.SNARE, {}, SessionKind.COLONOSCOPY, C.Rule.BIOPSY_OF_REMOVED_LESION,
                              '45380'),
    'snare beside an EMR': (Kind.SNARE, Kind.EMR, {}, SessionKind.COLONOSCOPY, C.Rule.RESECTION_TECHNIQUE, '45385'),
    # its part_of stated (round r3's integration: STATED_LINK's - the lift's identity read, never the silent link)
    'lift injection beside an EMR': (Kind.INJECTION, Kind.EMR, {'purpose': sup(Purpose.LIFT_FOR_RESECTION),
                                                                'part_of': STATED_LINK['part_of']},
                                     SessionKind.COLONOSCOPY, C.Rule.LIFT_INJECTION, '45381'),
    'FNA beside a drainage': (Kind.FNA, Kind.DRAINAGE, {}, SessionKind.EUS, C.Rule.DRAINAGE_STEP, '43242'),
}


def identity_scene(pair='biopsy beside a snare', *, part_lesion=sup(L2), whole_lesion=sup(L3), same=None,
                   distinct=None, apart=True) -> FactSet:
    """refute-r4b-r1 v1, v5 and v6's scene, for each SAME LESION rule: one session X1 (its done examination E1), the
    whole E2 (its lesion ``whole_lesion``, L3 by default) in the ascending colon and the part E4 (``part_lesion``, L2 by
    default) in the sigmoid colon with the place pair controls rejected both ways (``apart``; else both in the ascending
    colon, no control), three single lesion entries whose same_as and distinct_from lists ``same`` and ``distinct`` give
    ({lesion: its members})."""
    part_kind, whole_kind, extra, family, _rule, _code = SAME_LESION_PAIRS[pair]
    part_place, whole_place = (SIG, ASC) if apart else (ASC, ASC)
    same, distinct = same or {}, distinct or {}

    def entry(lesion_id, place):
        return {A.PLACES: (sup(place),), A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),),
                A.DISTINCT_FROM: tuple(distinct.get(lesion_id, ())), A.SAME_AS: tuple(same.get(lesion_id, ()))}

    lesions = {L1: entry(L1, whole_place), L2: entry(L2, part_place), L3: entry(L3, whole_place)}
    ctl = {(E4, A.TARGET_PLACES, whole_place): True, (E2, A.TARGET_PLACES, part_place): True} if apart else None
    return build({E1: exam(), E2: act(whole_kind, lesion=whole_lesion, places=(sup(whole_place),)),
                  E4: act(part_kind, lesion=part_lesion, places=(sup(part_place),), **extra)},
                 sessions={X1: session(family, tract=ct.Tract.UPPER if family is SessionKind.EUS else None)},
                 lesions=lesions, controls=ctl)


def identity_weakenings(R: FactSet):
    """9.4's weakenings of what the two acts' identity rests on: each act's lesion fact and each same_as member made
    unresolved, doubted (its value kept) or contradicted (its value one side: strong_weakenings' form)."""
    for family, subject, attribute in (('events', E4, A.TARGET_LESION), ('events', E2, A.TARGET_LESION),
                                       *(('lesions', lesion_id, A.SAME_AS) for lesion_id in R.lesions)):
        members = getattr(R, family)[subject].get(attribute, ())
        for index, member in enumerate(members):
            if not F.established(member):
                continue
            for how, weaker in (('unresolved', unres(member.value, member.state)),
                                ('doubted', doubted(member.value, state=member.state)),
                                ('contradicted', contra(member.value, _alternative(R, member.value)))):
                yield f'{subject} {attribute.value}[{index}] {how}', weaken(R, (family, subject, attribute, index,
                                                                                 weaker))


class OneFindingNeverApartByPlace(SimpleTestCase):
    """Repair r4b-2 (refute-r4b-r1 F1, F2, F3). The SAME LESION is never F by place while the two acts may be one finding:
    - F1 (high): beside supported members joining the two lesions, a claim that they are not one finding (D248 G3) was
      U only where the places did not set the acts apart - with the places apart (controls rejected) it fell through to
      the place exit and the part was its own act: 45380 READY where the same FactSet without the claim is bundled, and
      a weakening that ADDS a claim (an established member contradicted) released it (9.4 P-MONO). The claim is now
      asked whatever the places say;
    - F2 (low): the claim's contradicted arm is pinned (mutant MG3_NO_CONTRADICTED_DENIAL survived round r4b);
    - F3 (medium, a design question, pre-existing; built fail-closed - DECISIONS D239's reading, which rules pairing's
      analogue, for bundling; the step's NOTES, question QF3): one 9.4 weakening of the identity of a bundled part (an
      act's lesion fact, a same_as member) left the place exit to release it. The place arm now counts only while the
      two acts' lesion claims cannot name one finding: a common id by possibly, or a same_as that may join them."""

    CHAIN = {L2: (sup(L1),), L1: (sup(L3),)}  # L2 = L1 = L3 by supported members

    def test_f1_a_claim_beside_a_supported_join_is_asked_never_released_by_place(self):
        """refute-r4b-r1 v5 (as filed) and v1 (weakened): the chain and a claim that L2 is not L3 - negated
        (established), distinct_from (supported), the negation left open, or a contradicted member naming L3 - with
        the places apart or the same: U in both, the claim asked first (act_target at rank 17; the contradicted
        member's conflict at rank 1), never explained and never the part's own act, in every SAME LESION rule. Round
        r4b's first patch: its own act, the code released, wherever the places were apart."""
        claims = (
            ('negated', {L2: (sup(L1), neg(L3)), L1: (sup(L3),)}, None, ('act_target', 17, L2, A.SAME_AS)),
            ('distinct_from', self.CHAIN, {L2: (sup(L3),)}, ('act_target', 17, L2, A.DISTINCT_FROM)),
            ('a negation left open', {L2: (sup(L1), unres(L3, state=State.NEGATED)), L1: (sup(L3),)}, None,
             ('act_target', 17, L2, A.SAME_AS)),
            ('contradicted, L3 | L1', {L2: (sup(L1), contra(L3, L1)), L1: (sup(L3),)}, None,
             ('conflict', 1, L2, A.SAME_AS)),
        )
        for pair, (part_kind, _whole, _extra, _family, rule, code) in SAME_LESION_PAIRS.items():
            for name, same, distinct, top in claims:
                for apart in (True, False):
                    with self.subTest(pair, claim=name, apart=apart):
                        R = identity_scene(pair, same=same, distinct=distinct, apart=apart)
                        self.assertEqual(F.apart_by_place(R, E4, E2), apart)
                        self.assertEqual(rules(R, E4), [(rule, E2, U)])
                        held = C.bundling(code, (E4,), R)
                        self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                        fact_key = top[0] if top[0] != 'conflict' else rq.fact_key(rq.FactKey.CONFLICT, part_kind)
                        self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute),
                                         (fact_key, *top[1:]))
                        self.assertIsNone(C.bundled(R, E4))
                        self.assertTrue(C.doubted(R, E4))

    def test_f1_a_weakening_that_adds_a_claim_never_releases(self):
        """refute-r4b-r1 v1 (9.4 P-MONO): the chain and a direct member L2 = L3, the places apart - bundled (explained,
        T); that member contradicted (L3 | L1, the chain still supported): asked, its conflict at rank 1, never the
        part's own act (round r4b: its own act, 45380 READY)."""
        base = identity_scene(same={L2: (sup(L1), sup(L3)), L1: (sup(L3),)})
        self.assertEqual((rules(base, E4), C.verdict(base, E4).truth), ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)], FF))
        weak = identity_scene(same={L2: (sup(L1), contra(L3, L1)), L1: (sup(L3),)})
        self.assertEqual((rules(weak, E4), C.verdict(weak, E4).truth), ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)], U))
        held = C.bundling('45380', (E4,), weak)
        self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute),
                         ('conflict:biopsy', 1, L2, A.SAME_AS))

    def test_f2_a_contradicted_member_naming_the_other_is_a_claim(self):
        """refute-r4b-r1 F2 (mutant MG3_NO_CONTRADICTED_DENIAL: G3's contradicted arm dropped): beside the chain, L2's
        same_as member naming L3 contradicted (L3 | L1, or L3 | L4 - a fourth entry) is a claim that the two are not one
        finding, asked at rank 1 (its conflict) and never explained, the places the same - in the SAME LESION and in
        D221's identity (the APC of L2 beside the EMR of L3: its conflict first, then the part_of). Controls: the chain
        alone is explained (T); a contradicted member that does not name L3 (L1 | L4) is no claim between the two (the
        claim's reach, question QG3): explained."""
        lesions = {lesion_id: lesion_entry() for lesion_id in (L1, L2, L3, L4)}
        here = (sup(ASC),)

        def scene(l2_links, whole=Kind.SNARE, part=Kind.BIOPSY):
            entries = {**lesions, L1: lesion_entry(sup(L3)), L2: lesion_entry(*l2_links)}
            # the ablation's link stated (round r3's integration: STATED_LINK - a silent part_of or cause is the
            # silent-link rule's doubt, DESIGN-v2 b.8, asked before D221's identity)
            link = STATED_LINK if part is Kind.ABLATION else {}
            return build({E1: exam(), E2: act(whole, lesion=sup(L3), places=here),
                          E4: act(part, lesion=sup(L2), places=here, **link)}, lesions=entries)

        for sides in ((L3, L1), (L3, L4)):
            with self.subTest(sides=sides):
                R = scene((sup(L1), contra(*sides)))
                self.assertEqual(rules(R, E4), [(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, U)])
                held = C.bundling('45380', (E4,), R)
                self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                self.assertEqual((held[0].fact, held[0].rank, held[0].subject, held[0].attribute),
                                 ('conflict:biopsy', 1, L2, A.SAME_AS))
                R = scene((sup(L1), contra(*sides)), whole=Kind.EMR, part=Kind.ABLATION)
                held = C.bundling('45388', (E4,), R)
                self.assertEqual([(item.fact, item.subject, item.attribute) for item in held[:2]],
                                 [('conflict:ablation', L2, A.SAME_AS), ('act_part', E4, A.PART_OF)])
        for name, links in (('the chain alone', (sup(L1),)), ('a contradicted member not naming L3',
                                                               (sup(L1), contra(L1, L4)))):
            with self.subTest(name):
                R = scene(links)
                self.assertEqual((rules(R, E4), C.verdict(R, E4).truth),
                                 ([(C.Rule.BIOPSY_OF_REMOVED_LESION, E2, T)], FF))

    def test_f3_a_weakened_identity_is_never_set_apart_by_place(self):
        """refute-r4b-r1 F3 (v6, v2), built fail-closed (question QF3): two acts one finding by supported facts - one
        lesion id, a direct same_as member, or a chain through L1 - with their places established apart are bundled
        (explained, T); every weakening of either act's lesion fact or of a same_as member (unresolved, doubted,
        contradicted: its claim kept among its sides) leaves them possibly one finding: U, asked, never the part's own
        act, in each SAME LESION rule. Round r4b's trees released the part on each (its own act, the code READY)."""
        shapes = {'one lesion id': dict(part_lesion=sup(L3)),
                  'a direct same_as member': dict(same={L2: (sup(L3),)}),
                  'a chain through L1': dict(same=self.CHAIN)}
        checked = 0
        for pair, (_part, _whole, _extra, _family, rule, code) in SAME_LESION_PAIRS.items():
            for shape, kwargs in shapes.items():
                R = identity_scene(pair, **kwargs)
                with self.subTest(pair, shape=shape):
                    self.assertTrue(F.apart_by_place(R, E4, E2))
                    self.assertEqual((rules(R, E4), C.verdict(R, E4).truth), ([(rule, E2, T)], FF))
                for label, weak in identity_weakenings(R):
                    with self.subTest(pair, shape=shape, weakened=label):
                        self.assertTrue(F.apart_by_place(weak, E4, E2))
                        self.assertEqual(rules(weak, E4), [(rule, E2, U)])
                        held = C.bundling(code, (E4,), weak)
                        self.assertTrue(held)
                        self.assertFalse([item for item in held if item.kind is ItemKind.EXPLANATION])
                        checked += 1
        self.assertGreaterEqual(checked, 4 * (6 + 9 + 12))

    def test_f3_controls(self):
        """What still sets the two acts apart by place (each its own act, as before): a lesion stated on one act only
        (P13: a lesion the document does not state relates nothing); two different supported ids that no same_as may
        join (different findings, P5); a claim not established naming only another id no same_as may join; an
        established negation of the other's lesion (it names none). What may name the other's lesion now asks (D239's
        "value or options name the act's lesion"; the round r4b trees released each): a doubt reading it, a doubt naming
        the empty slot with that reading, a negation of it left open. Without the place controls rejected nothing sets
        the two apart: U, as before."""
        for name, part_lesion, truth in (
                ('no lesion stated on the part', SILENT, None),
                ('two different supported ids', sup(L2), None),
                ("the part's lesion unresolved, naming another id", unres(L2), None),
                ("the part's lesion negated, naming the other's", neg(L3), None),
                ("a doubt reading the other's lesion", doubted(L2, L3), U),
                ("a doubt naming the empty slot, reading the other's lesion", doubted_empty(L3), U),
                ("a negation of the other's lesion left open", unres(L3, state=State.NEGATED), U)):
            for pair, (_part, _whole, _extra, _family, rule, code) in SAME_LESION_PAIRS.items():
                with self.subTest(name, pair=pair):
                    R = identity_scene(pair, part_lesion=part_lesion)
                    self.assertTrue(F.apart_by_place(R, E4, E2))
                    self.assertEqual(rules(R, E4), [(rule, E2, truth)] if truth else [])
                    self.assertEqual(bool(C.bundling(code, (E4,), R)), truth is not None)
                    R = identity_scene(pair, part_lesion=part_lesion, apart=False)
                    self.assertEqual([bundle.truth for bundle in C.bundles(R, E4)], [U])

    def test_f1_f3_monotone_over_identity_scenes(self):
        """refute-r4b-r1's search (tools/mono_search_places.py), rebuilt with a fixed seed: the four SAME LESION rules,
        lesions linked by a chain through L1, a direct member or both, beside a claim of non-identity in each form or
        none, the places apart (controls rejected) or the same; every strong weakening of every base that is not the
        part's own act leaves it so, but a deleted same_as member (question QR4-1, counted apart) - round r4b: 813
        violating weakenings of 24,992 (seed 71, 300 trials), every one with the places apart."""
        rng = random.Random(20261114)

        def member(value):
            return rng.choice([sup(value)] * 3 + [neg(value), unres(value), contra(value, L1),
                                                  unres(value, state=State.NEGATED)])

        checked = deleted = 0
        for _ in range(60):
            pair = rng.choice(sorted(SAME_LESION_PAIRS))
            apart = rng.random() < 0.6
            shape = rng.choice(['chain', 'direct', 'both'])
            l2_same, l1_same, l2_distinct = [], [], []
            if shape in ('chain', 'both'):
                l2_same.append(sup(L1))
                l1_same.append(sup(L3))
            if shape in ('direct', 'both'):
                l2_same.append(sup(L3))
            if rng.random() < 0.5:
                claim = rng.choice(['negated', 'distinct', 'contradicted', 'open negation'])
                if claim == 'negated':
                    l2_same.append(neg(L3))
                elif claim == 'distinct':
                    l2_distinct.append(member(L3))
                elif claim == 'contradicted':
                    l2_same.append(contra(L3, L1))
                else:
                    l2_same.append(unres(L3, state=State.NEGATED))
            R = identity_scene(pair, same={L2: l2_same, L1: l1_same}, distinct={L2: l2_distinct}, apart=apart)
            if C.verdict(R, E4).truth is T:
                continue
            for change in strong_weakenings(R):
                weak = strong_weaken(R, change)
                checked += 1
                if C.verdict(weak, E4).truth is not T:
                    continue
                if change[0] == 'lesions' and change[2] is A.SAME_AS and change[4] is None:
                    deleted += 1
                    continue
                self.fail(f'{pair}, apart={apart}: {change[:4]} released the part')
        self.assertGreater(checked, 3000)
        self.assertGreater(deleted, 0)  # QR4-1's release, named apart (a deleted same_as member is no 9.4 weakening)


# --- repair r4b of round w8r (DECISIONS D256 P2's coverage half: refute-r4d-r2 P2), restated by repair r4b of round ---
# --- w9r (DECISIONS D269's coverage half: Q-P2DATE option (c)), each pinned by a test ---------------------------------


LATER = ct.DateRelation.LATER_DATE
SEPARATE = ct.EncounterRelation.SEPARATE_ENCOUNTER


def eus_beside_egd_today(eus, extra=None, entries=(), part_of=None) -> FactSet:
    """refute-r4d-r2 P2's shape (its planned_eus and planned_eus_filed probes): an EGD X1 today, its examination E1 done
    (43235 alone), beside an upper EUS X2 of a separate encounter whose examination E2 is ``eus``: 'planned' (planned,
    at a later date - the corpus's own filing of a planned procedure, cases_checklist.py CK-future), 'earlier' (done at
    an earlier date) - each established not done on the date of service; for the controls 'today' (done today), 'date
    open' (its date relation unresolved) or None (no examination: X2 told by nothing). ``extra``: more events (E3);
    ``entries``: kept unlisted entries; ``part_of``: the EGD's own part_of_session claim (None: an empty slot)."""
    events = {E1: exam(session=sup(X1))}
    if eus == 'planned':
        events[E2] = exam(session=sup(X2), status=sup(PLANNED), date=sup(LATER))
    elif eus == 'earlier':
        events[E2] = exam(session=sup(X2), date=sup(EARLIER))
    elif eus == 'today':
        events[E2] = exam(session=sup(X2))
    elif eus == 'date open':
        events[E2] = exam(session=sup(X2), date=unres(ON))
    events.update(extra or {})
    return build(events, sessions={X1: session(SessionKind.EGD, part_of=part_of), X2: {
        **session(SessionKind.EUS, tract=ct.Tract.UPPER), A.ENCOUNTER: (sup(SEPARATE),)}}, unlisted=entries)


# The done-when's entries of round w8r: refute-r4d-r2 P2's three kept unlisted entries with no card - an office visit
# act, a pH capsule placement act, a biopsy doubt - and their filed analog: the same act filed with its session slot
# silent and its date not established (silent, or unresolved).
P2_FORMS = {
    'an office visit act, no card': ({}, (unlisted(U_ACT, Kind.EM_VISIT, None),)),
    'a pH capsule placement act, no card': ({}, (unlisted(U_ACT, Kind.PH_MONITORING, None),)),
    'a biopsy doubt, no card': ({}, (unlisted(U_DOUBT, Kind.BIOPSY, None),)),
    'an office visit filed, no session, no date': ({E3: act(Kind.EM_VISIT, session=None, date=None)}, ()),
    'a pH capsule placement filed, no session, no date': ({E3: act(Kind.PH_MONITORING, session=None, date=None)}, ()),
    'a biopsy filed in doubt, no session, no date': ({E3: act(Kind.BIOPSY, session=None, date=None,
                                                              status=doubted(PERFORMED))}, ()),
    'an office visit filed, no session, its date unresolved': ({E3: act(Kind.EM_VISIT, session=None,
                                                                        date=unres(ON))}, ()),
}

# DECISIONS D269's done-when (refute-r4d-r1 V8R4D1-6, refute-r4b-r1 V8R4B1-3): an act's session slot and its date, as
# the round's office visit act is told - and the EGD's own part_of_session claim (C3 supported; D70 not established).
D269_SLOTS = (('its slot silent', None), ('its slot empty, a doubt naming X2', doubted_empty(X2)),
              ('its slot empty, a doubt naming X1 and X2', doubted_empty(X1, X2)),
              ('its slot claimed X1, a doubt reading X2', doubted(X1, X2)),
              ('its slot claimed X2, a doubt reading X1', doubted(X2, X1)),
              ('its slot claimed X2, unresolved', unres(X2)), ('placed in X2', sup(X2)))
D269_DATES = (('dated today', sup(ON)), ('undated: silent', None), ('undated: unresolved', unres(ON)),
              ('undated: a doubt', doubted(ON, ON, EARLIER)))
D269_CLAIMS = (('no claim', None), ('C3: supported X2', sup(X2)), ('D70: unresolved X2', unres(X2)),
               ('D70: claimed X1, a doubt reading X2', doubted(X1, X2)),
               # DECISIONS D286 (G3-14): an empty slot a doubt names is a claim, read by its readings in both modules
               ('D70: an empty slot, a doubt naming X2', doubted_empty(X2)),
               ('D70: an empty slot, a doubt naming X1 and X2', doubted_empty(X1, X2)))


def p2_reference_left_open(R: FactSet, session_: Id) -> tuple:
    """Step 4d's reading of the session's possible examinations (DECISIONS D227's one derivation): the events
    combination._may_be_examination_of admits that are not done (reading.done) - and NONE in a session whose
    examination is established not done today (combination.not_done_today): DECISIONS D269, Q-P2DATE option (c), the
    exemption combination.session_possibly_done makes of every act possibly in such a session, whatever its date or
    its session slot. Round w8r read D256 P2's letter here: only an act whose session slot is silent and whose date is
    not established (combination._unplaced_undated, gone with D269) was excepted."""
    if CB.not_done_today(R, session_):
        return ()
    view = RD.Reading(R)
    return tuple(event for event in R.events if CB._may_be_examination_of(R, session_, event)
                 and not RD.done(view, event))


def d256_p2_letter(R: FactSet, event_: Id) -> bool:
    """D256 P2's letter of round w8r, which D269 replaces - read here only to count the inputs D269's widening reaches,
    never by the engine: an act whose session slot is silent (facts.silent: no claim, an empty slot a doubt names
    included) and whose date relation is not established."""
    return F.silent(F.fact(R, event_, A.SESSION)) and not F.established(F.fact(R, event_, A.DATE_RELATION))


def p2_scene(rng: random.Random) -> FactSet:
    """One generated FactSet for D269's agreement (and D256 P2's before it): the EGD X1 (E1 done today) beside an upper
    EUS X2 whose examination E2 is established not done today (planned at a later date, done at an earlier date,
    denied) or, for contrast, done today, its date or status unresolved, or absent; 0-3 more events, each of an
    examination's kind, no kind, a kind the EUS family holds (FNA, biopsy) or one it does not (office visit, pH capsule
    placement), its status performed or doubted, its session slot silent, an empty slot a doubt names, claimed or
    established X2, or claimed X1 with a doubt reading X2 (never established X1: the EGD keeps one done examination, so
    its C-4 and D70 arms are read), and its date silent, unresolved, doubted, today or earlier; 0-2 kept unlisted acts
    or doubts of such a kind or none, with no card, carded X1 or X2, or a card naming X9; and the EGD's own
    part_of_session claim (most often none; C3's supported X2, D70's unresolved X2, or claimed X1 with a doubt reading
    X2). No device is stated (DECISIONS D253's QE13 is not read here)."""
    events = {E1: exam(session=sup(X1))}
    shape = rng.choice(['planned', 'earlier', 'denied', 'today', 'date open', 'status open', None])
    if shape == 'planned':
        events[E2] = exam(session=sup(X2), status=sup(PLANNED), date=rng.choice([sup(LATER), None, unres(LATER)]))
    elif shape == 'earlier':
        events[E2] = exam(session=sup(X2), date=sup(EARLIER))
    elif shape == 'denied':
        events[E2] = exam(session=sup(X2), status=neg(PERFORMED))
    elif shape == 'today':
        events[E2] = exam(session=sup(X2))
    elif shape == 'date open':
        events[E2] = exam(session=sup(X2), date=rng.choice([unres(ON), doubted(ON, ON, EARLIER), None]))
    elif shape == 'status open':
        events[E2] = exam(session=sup(X2), status=rng.choice([unres(PLANNED), doubted(PLANNED, PERFORMED)]))
    kinds = [sup(Kind.EXAMINATION), sup(Kind.EXAMINATION), None, sup(Kind.FNA), sup(Kind.BIOPSY), sup(Kind.EM_VISIT),
             sup(Kind.PH_MONITORING), unres(Kind.EXAMINATION)]
    for number in range(3, 3 + rng.randint(0, 3)):
        events[Id(IdFamily.EVENT, number)] = act(
            Kind.EXAMINATION, kind=rng.choice(kinds),
            status=rng.choice([sup(PERFORMED), sup(PERFORMED), doubted(PERFORMED)]),
            session=rng.choice([None, None, None, doubted_empty(X1, X2), doubted_empty(X2), unres(X2), sup(X2),
                                doubted(X2, X1), doubted(X1, X2)]),
            date=rng.choice([None, None, unres(ON), doubted(ON, ON, EARLIER), sup(ON), sup(EARLIER)]))
    entries = tuple(unlisted(rng.choice([U_ACT, U_DOUBT]),
                             rng.choice([Kind.EXAMINATION, Kind.FNA, Kind.BIOPSY, Kind.EM_VISIT, Kind.PH_MONITORING,
                                         None]),
                             rng.choice([None, None, X1, X2, X9]), n=40 + index)
                    for index in range(rng.choice([0, 1, 1, 2])))
    part_of = rng.choice([None, None, None, None, sup(X2), unres(X2), doubted(X1, X2), doubted_empty(X2),
                          doubted_empty(X1, X2)])  # D286: doubted-empty claims in the generated agreement
    return build(events, sessions={X1: session(SessionKind.EGD, part_of=part_of), X2: {
        **session(SessionKind.EUS, tract=ct.Tract.UPPER), A.ENCOUNTER: (sup(SEPARATE),)}}, unlisted=entries)


MEMBER_43235 = CB.Member('sel:0', '43235', SessionKind.EGD, X1, (E1,), procedural=True, supported=True)


class EstablishedNotDoneTodayIsNeverPossiblyDone(SimpleTestCase):
    """DECISIONS D269's coverage half (Q-P2DATE option (c), 4.3 row 7; refute-r4d-r1 V8R4D1-6, refute-r4b-r1 V8R4B1-3,
    r4b's question Q3 of round w8r, the integration's I4 residual; D227's one derivation, step 4d's
    combination.not_done_today, session_possibly_done and wholes the reference - this repair is built on step r4d's
    patch of round w9r), over D256 P2 (refute-r4d-r2 P2, high), which it widens: a session whose examination is
    established, and established not done on the date of service (planned, or done on another date), is possibly done
    by NO act - an entry with no card or carded, a filed act whatever its date or session slot - and is never a whole:
    possible_examinations lists nothing left open in it, and _part_of_session never makes the EGD part of it, by C3's
    supported claim, by D70's claim not established, or by the structural C-4 and D70 arms; an entry with no card that
    names a kind reaches only a session one of whose possible families holds that kind (K2). Round w8r read D256 P2's
    letter: only an act whose session slot is silent and whose date is not established was excepted, so an act dated
    today, an act filed in the EUS or a carded entry still made a planned EUS possibly done, and C3's or D70's claim
    made it the EGD's whole; round 3 of round w7r read 4d's earlier reference, where any entry with no card did (43235
    held base_within beside an EUS that was not done today)."""

    def one_answer(self, R: FactSet) -> list:
        """Coverage's reading of X2 for the EGD X1 against step 4d's, on one FactSet: coverage's part_of (established)
        or possibly_part_of (possible) of X1, as [(session, established)], equals combination.wholes(X1); event_coding
        records it; with no part_of_session claim of the EGD's own - a PURE empty slot: an empty slot a doubt names is
        a claim, read by its readings in both modules (DECISIONS D286, G3-14) - X1 is part of X2 in either sense (the
        structural C-4 and D70 arms alone) exactly when 4d reads X2 possibly done - C3's and D70's claims name X2
        whatever X2's acts; and X2's possible examinations are 4d's reading (p2_reference_left_open) - none, and no whole by any arm,
        when 4d reads X2 established not done today (D269). Returns coverage's."""
        sessions_ = C.sessions(R)
        record = sessions_[X1]
        mine = ([(record.part_of, True)] if record.part_of is not None
                else [(record.possibly_part_of, False)] if record.possibly_part_of is not None else [])
        self.assertEqual(mine, [(whole.session, whole.established) for whole in CB.wholes(R, X1)])
        coded = C.event_coding(R, sessions_, {})['sessions']['X1']
        self.assertEqual((coded['part_of'], coded['possibly_part_of']),
                         (None if record.part_of is None else str(record.part_of),
                          None if record.possibly_part_of is None else str(record.possibly_part_of)))
        if C._pure_silent(F.fact(R, X1, A.PART_OF_SESSION)):
            self.assertEqual(bool(mine), CB.session_possibly_done(R, X2))
        self.assertEqual(sessions_[X2].possible, p2_reference_left_open(R, X2))
        if CB.not_done_today(R, X2):
            self.assertEqual((mine, sessions_[X2].possible), ([], ()))
        return mine

    def test_d269_the_planned_and_the_earlier_eus_beside_an_office_visit_act(self):
        """THE DONE-WHEN (DECISIONS D269): an EGD X1 today (43235 alone) beside an upper EUS X2 whose examination is
        established planned (a later date) or done at an earlier date, and an office visit act E3 - dated today, or
        undated (its date silent, unresolved or a doubt) - its session slot silent, empty with a doubt naming X2 (or X1
        and X2), claimed X1 with a doubt reading X2, claimed X2 with a doubt reading X1, claimed X2 unresolved, or
        placed in X2; and the EGD's own part_of_session claim none, C3's supported X2, D70's unresolved X2, or claimed
        X1 with a doubt reading X2. Coverage and 4d give ONE answer (one_answer): X2 established not done today and not
        possibly done, no whole (combination.wholes; coverage's part_of and possibly_part_of, in the record and in
        event_coding), 43235 not held base_within; X2 lists nothing left open (equal to 4d's reading) and is neither
        done nor unresolved. Round w8r: the dated act and the act filed in X2 made X2 possibly done (D256 P2's letter;
        r4b's pin of Q-P2DATE as built), and C3's or D70's claim made it the EGD's whole in both modules. The same act
        kept unlisted - with no card, carded X2, or carded X9 (an id the FactSet does not hold) - reads the same."""
        count = 0
        for eus in ('planned', 'earlier'):
            for claim, part_of in D269_CLAIMS:
                forms = [(f'{slot_name}, {date_name}', {E3: act(Kind.EM_VISIT, session=slot, date=date)}, ())
                         for slot_name, slot in D269_SLOTS for date_name, date in D269_DATES]
                forms += [(f'kept unlisted, {card_name}', {}, (unlisted(U_ACT, Kind.EM_VISIT, card),))
                          for card_name, card in (('no card', None), ('carded X2', X2), ('carded X9', X9))]
                for name, extra, entries in forms:
                    with self.subTest(eus=eus, claim=claim, act=name):
                        R = eus_beside_egd_today(eus, extra, entries, part_of=part_of)
                        self.assertEqual((CB.not_done_today(R, X2), CB.session_possibly_done(R, X2)), (True, False))
                        self.assertEqual(self.one_answer(R), [])
                        self.assertEqual(CB.base_within([MEMBER_43235], R), ())
                        record = C.sessions(R)[X2]
                        self.assertEqual((record.possible, record.possible_unlisted, record.done, record.unresolved),
                                         ((), (), False, False))
                        self.assertEqual(C.possible_examinations(R, X2), p2_reference_left_open(R, X2))
                        count += 1
        self.assertEqual(count, 2 * len(D269_CLAIMS) * (len(D269_SLOTS) * len(D269_DATES) + 3))

    def test_d269_c3_and_d70_never_make_the_egd_part_of_a_session_established_not_done_today(self):
        """DECISIONS D269 (the integration's I4 residual), _part_of_session's claim arms, read as 4d's wholes reads
        them: the EGD's own part_of_session claim naming the planned or the earlier EUS - supported (C3), or not
        established (D70: unresolved; claimed X1 with a doubt reading X2) - makes it part of nothing, so the EGD keeps
        its own items: with no code counted its no_proposal item is listed, and with 43235 counted it is covered by its
        own code and included in no session (round w8r: C3 made it part of the planned EUS, so inclusion_asks_no_code
        dropped its no_proposal item and included_by named it; D70 made it possibly part of it). Controls, 4d alike: the
        same claims name an EUS that is not established not done today - done today (C3: part of it; D70: C-4's
        established whole) or its date open (C3: part of it; D70: possibly part of it)."""
        counted = [C.Counted('sel:0', '43235', SessionKind.EGD, (E1,))]
        for eus in ('planned', 'earlier'):
            for claim, part_of in D269_CLAIMS[1:]:
                with self.subTest(eus=eus, claim=claim):
                    R = eus_beside_egd_today(eus, part_of=part_of)
                    self.assertEqual(self.one_answer(R), [])
                    sessions_ = C.sessions(R)
                    cov = C.reconcile(R, [], procedure_day=True)
                    self.assertEqual([(item.reason, item.detail, item.events) for item in cov.unresolved
                                      if item.session == X1],
                                     [(C.ItemReason.NO_PROPOSAL, C.Detail.SESSION_PERFORMED, (E1,))])
                    cov = C.reconcile(R, counted, procedure_day=True)
                    self.assertEqual(([item for item in cov.unresolved if item.session == X1], cov.covered.get(X1),
                                      C.included_by(sessions_, cov.covered)), ([], ['43235'], {}))
        for eus, claims in (('today', ((sup(X2), [(X2, True)]), (unres(X2), [(X2, True)]))),
                            ('date open', ((sup(X2), [(X2, True)]), (unres(X2), [(X2, False)])))):
            for part_of, whole in claims:
                with self.subTest(control=eus, claim=part_of.result.value):
                    self.assertEqual(self.one_answer(eus_beside_egd_today(eus, part_of=part_of)), whole)

    def test_p2_the_planned_and_the_earlier_eus_beside_an_egd(self):
        """Round w8r's done-when, which D269 keeps: an EGD X1 today beside an upper EUS X2 whose examination is
        established planned (later) or done at an earlier date, with an office visit act, a pH capsule placement act or
        a biopsy doubt kept unlisted with no card, or the same act filed with no session and no date (or its date
        unresolved): X2 is not possibly done (4d) and the EGD is part of nothing (coverage), one answer in event_coding;
        X2 lists no possible examination, filed or synthetic, and is not done. With nothing beside: the same."""
        for eus in ('planned', 'earlier'):
            for name, (extra, entries) in P2_FORMS.items():
                with self.subTest(eus=eus, form=name):
                    R = eus_beside_egd_today(eus, extra, entries)
                    self.assertTrue(CB.not_done_today(R, X2))
                    self.assertEqual(self.one_answer(R), [])
                    record = C.sessions(R)[X2]
                    self.assertEqual((record.possible, record.possible_unlisted, record.done), ((), (), False))
            with self.subTest(eus=eus, form='nothing beside'):
                self.assertEqual(self.one_answer(eus_beside_egd_today(eus)), [])

    def test_p2_controls(self):
        """What still makes X2 possibly done, read alike by coverage and 4d - and, DECISIONS D269, what no longer does.
        Beside a planned or an earlier EUS (established not done today) NOTHING placed or supported does: the three
        entries carded X2, the office visit filed with its session claimed (unresolved X2), and the office visit filed
        with no session but dated today - round w8r's pin of Q-P2DATE as built (r4b's question Q3, refute-r4d-r1
        V8R4D1-6: X2 possibly done, the EGD possibly part of it, and both released when that date was weakened) - each
        now gives no whole. Only an event the document places in X2 that may be its examination done today keeps X2
        from being established not done (4d's not_done_today, step r4d's question Q-NDT): an examination claimed in X2
        (unresolved), its date silent - X2 possibly done, the EGD possibly part of it. An EUS whose examination is not
        established not done today: done today (C-4: part of it), its date unresolved (D70: possibly part of it); and
        an EUS told by nothing, where D256 P2's K2 decides an entry with no card: one that names a kind the EUS family
        holds (a biopsy doubt, an FNA act) or none makes it possibly done, an office visit or a pH capsule placement act
        never does (carded X2 it does); a filed act is no entry, so K2 does not narrow it."""
        cases = []
        for eus in ('planned', 'earlier'):
            cases += [(eus, 'an office visit act carded X2', {}, (unlisted(U_ACT, Kind.EM_VISIT, X2),), []),
                      (eus, 'a pH capsule placement act carded X2', {}, (unlisted(U_ACT, Kind.PH_MONITORING, X2),),
                       []),
                      (eus, 'a biopsy doubt carded X2', {}, (unlisted(U_DOUBT, Kind.BIOPSY, X2),), []),
                      (eus, 'an office visit filed, session unresolved X2, no date',
                       {E3: act(Kind.EM_VISIT, session=unres(X2), date=None)}, (), []),
                      (eus, 'an office visit filed, no session, dated today (Q-P2DATE, D269 option (c))',
                       {E3: act(Kind.EM_VISIT, session=None)}, (), []),
                      (eus, 'an examination claimed in X2, no date (Q-NDT: X2 not established not done)',
                       {E3: exam(session=unres(X2), date=None)}, (), [(X2, False)])]
        for eus, whole in (('today', [(X2, True)]), ('date open', [(X2, False)])):
            cases += [(eus, name, extra, entries, whole) for name, (extra, entries) in P2_FORMS.items()]
        cases += [(None, 'nothing beside', {}, (), []),
                  (None, 'an office visit act, no card (K2)', {}, (unlisted(U_ACT, Kind.EM_VISIT, None),), []),
                  (None, 'a pH capsule placement act, no card (K2)', {}, (unlisted(U_ACT, Kind.PH_MONITORING, None),),
                   []),
                  (None, 'an office visit act carded X2', {}, (unlisted(U_ACT, Kind.EM_VISIT, X2),), [(X2, False)]),
                  (None, 'a biopsy doubt, no card', {}, (unlisted(U_DOUBT, Kind.BIOPSY, None),), [(X2, False)]),
                  (None, 'an FNA act, no card', {}, (unlisted(U_ACT, Kind.FNA, None),), [(X2, False)]),
                  (None, 'an act of no kind, no card', {}, (unlisted(U_ACT, None, None),), [(X2, False)]),
                  (None, 'an office visit filed, no session, no date', {E3: act(Kind.EM_VISIT, session=None,
                                                                                date=None)}, (), [(X2, False)])]
        for eus, name, extra, entries, whole in cases:
            with self.subTest(eus=eus, form=name):
                R = eus_beside_egd_today(eus, extra, entries)
                self.assertEqual(CB.not_done_today(R, X2), eus in ('planned', 'earlier') and not whole)
                self.assertEqual(self.one_answer(R), whole)

    def test_p2_possible_examinations(self):
        """possible_examinations reads D269: beside a planned or an earlier EUS X2, an examination - or an act of no
        kind - (its status performed or a doubt; its date silent, unresolved, a doubt or today; done only in the 16 rows
        of status performed and date today, a done act being no possible examination of any session whatever D269
        says, which ``widened`` does not count), whose session
        slot does not claim X2 (silent; empty, a doubt naming X2, or X1 and X2; claimed X1 with a doubt reading X2), is
        no possible examination of X2, whatever its date or slot (equal to 4d's reading; round w8r listed it unless its
        slot was silent and its date not established: D256 P2's letter), and X2 is neither unresolved nor done; X1's
        reading is 4d's too (the act left open there exactly when 4d leaves it open, its event None and the session
        unresolved), event_coding records both, and the EGD is part of nothing. Controls, read alike by 4d: an
        examination claimed in X2 (unresolved X2: X2 is then not established not done - step r4d's question Q-NDT), or
        an EUS whose examination is not established not done today (its date unresolved; no examination at all) - X2's
        possible examination, X2 possibly done, the EGD possibly part of it."""
        widened = 0
        for eus in ('planned', 'earlier'):
            for kind in (sup(Kind.EXAMINATION), None):
                for slot in (None, doubted_empty(X2), doubted_empty(X1, X2), doubted(X1, X2)):
                    for status in (sup(PERFORMED), doubted(PERFORMED)):
                        for date in (None, unres(ON), doubted(ON, ON, EARLIER), sup(ON)):
                            with self.subTest(eus=eus, kind=None if kind is None else kind.value,
                                              slot=None if slot is None else (slot.value, slot.options),
                                              status=status.result.value, date=None if date is None else date.result):
                                R = eus_beside_egd_today(eus, {E3: act(Kind.EXAMINATION, kind=kind, session=slot,
                                                                       status=status, date=date)})
                                sessions_ = C.sessions(R)
                                self.assertTrue(CB.not_done_today(R, X2))
                                self.assertEqual((C.possible_examinations(R, X2), sessions_[X2].possible,
                                                  sessions_[X2].unresolved, sessions_[X2].done),
                                                 ((), (), False, False))
                                self.assertEqual(C.possible_examinations(R, X2), p2_reference_left_open(R, X2))
                                left_open = p2_reference_left_open(R, X1)
                                self.assertEqual((C.possible_examinations(R, X1), sessions_[X1].possible), (left_open,
                                                                                                            left_open))
                                self.assertEqual((sessions_[X1].event, sessions_[X1].unresolved),
                                                 (None, True) if left_open else (E1, False))
                                coded = C.event_coding(R, sessions_, {})['sessions']
                                self.assertEqual((coded['X2']['possible'], coded['X1']['possible']),
                                                 ([], [str(event_) for event_ in left_open]))
                                self.assertEqual(self.one_answer(R), [])
                                view = RD.Reading(R)
                                widened += (CB._may_be_examination_of(R, X2, E3) and not RD.done(view, E3)
                                            and not d256_p2_letter(R, E3))
                                if slot is None and date in (None, unres(ON)) and status.result is Res.SUPPORTED:
                                    self.assertEqual(left_open, (E3,))  # round w8r's rows, unchanged
        self.assertGreater(widened, 20)  # D269's reach past D256 P2's letter (round w8r listed each of these for X2)
        for eus, extra, possible in (
                ('planned', {E3: exam(session=unres(X2), date=None)}, (E3,)),
                ('earlier', {E3: exam(session=unres(X2), date=None)}, (E3,)),
                ('date open', {E3: exam(session=None, date=None)}, (E2, E3)),
                (None, {E3: exam(session=None, date=None)}, (E3,))):
            with self.subTest(eus=eus, control=True):
                R = eus_beside_egd_today(eus, extra)
                self.assertFalse(CB.not_done_today(R, X2))
                self.assertEqual((C.possible_examinations(R, X2), C.sessions(R)[X2].possible), (possible, possible))
                self.assertEqual(C.possible_examinations(R, X2), p2_reference_left_open(R, X2))
                self.assertEqual(self.one_answer(R), [(X2, False)])

    def test_d269_the_exemption_is_4ds_over_every_slot_and_date(self):
        """The exemption is 4d's (D227's one derivation; it replaces round w8r's pin of coverage's mirror of
        combination._unplaced_undated, gone with D269): beside a planned or an earlier EUS X2, an event E3 of every kind
        below (an examination, its kind unresolved, no kind, an FNA, an office visit), its status performed or a doubt,
        over every session fact (silent; empty, a doubt naming X1 and X2; supported, unresolved, a doubt, contradicted,
        negated or a negation left open on X1; supported X9, an id the FactSet does not hold; supported, unresolved or a
        doubt claiming X2) and every date fact (silent; supported today or earlier; unresolved; a doubt; negated;
        contradicted): coverage's possible examinations of X2 equal 4d's reading; when 4d reads X2 established not done
        today, they are none, 4d reads X2 not possibly done, X2 is not unresolved and the EGD is part of nothing (one
        answer). The grid reaches both readings of X2 (an examination placed in X2 that may be done today keeps it from
        not_done_today: step r4d's question Q-NDT), and inputs D256 P2's letter left open there - an act dated today, a
        slot a claim or a doubt's reading names - which D269 exempts."""
        seen = {'settled': 0, 'not settled': 0, 'exempt': 0, 'exempt past the letter': 0, 'left open': 0}
        kinds = (sup(Kind.EXAMINATION), unres(Kind.EXAMINATION), None, sup(Kind.FNA), sup(Kind.EM_VISIT))
        slots = (None, doubted_empty(X1, X2), sup(X1), unres(X1), doubted(X1, X2), contra(X1, X2), neg(X1),
                 unres(X1, state=State.NEGATED), sup(X9), sup(X2), unres(X2), doubted(X2, X1))
        dates = (None, sup(ON), sup(EARLIER), unres(ON), doubted(ON, ON, EARLIER), neg(ON), contra(ON, EARLIER))
        for eus in ('planned', 'earlier'):
            for kind in kinds:
                for slot in slots:
                    for status in (sup(PERFORMED), doubted(PERFORMED)):
                        for date in dates:
                            R = eus_beside_egd_today(eus, {E3: act(Kind.EXAMINATION, kind=kind, session=slot,
                                                                   status=status, date=date)})
                            label = (eus, kind, slot, status, date)
                            possible = C.possible_examinations(R, X2)
                            self.assertEqual(possible, p2_reference_left_open(R, X2), label)
                            view = RD.Reading(R)
                            open_by_4d = CB._may_be_examination_of(R, X2, E3) and not RD.done(view, E3)
                            if CB.not_done_today(R, X2):
                                seen['settled'] += 1
                                self.assertEqual((possible, C.sessions(R)[X2].unresolved,
                                                  CB.session_possibly_done(R, X2)), ((), False, False), label)
                                self.assertEqual(self.one_answer(R), [], label)
                                seen['exempt'] += open_by_4d
                                seen['exempt past the letter'] += open_by_4d and not d256_p2_letter(R, E3)
                            else:
                                seen['not settled'] += 1
                                seen['left open'] += E3 in possible
                                self.assertEqual(E3 in possible, open_by_4d, label)
        for arm, count in seen.items():
            with self.subTest(arm=arm):
                self.assertGreater(count, 10, seen)

    def test_d269_q3_a_weakening_never_narrows_a_sessions_possible_examinations(self):
        """r4b's question Q3 of round w8r (refute-r4d-r1 V8R4D1-6's coverage side), now closed by D269: under D256 P2's
        letter, a settled session's possible examinations narrowed under a 9.4 weakening - beside the planned EUS, an
        examination E3 in doubt (status a doubt) with no session and dated today was X2's possible examination, and
        weakening its date to unresolved dropped it (an unplaced, undated act). Under D269 X2 lists none either way,
        while X1 lists E3 both times. And over every single weakening (an established fact to unresolved or a doubt, a
        list member deleted: the module's ``weakenings``) of the done-when's shapes and of 300 generated FactSets
        (p2_scene; no device is stated), neither session's possible examinations lose a member, and X2 never becomes
        established not done today when it was not (step 4d's not_done_today only weakens toward not settled)."""
        R = eus_beside_egd_today('planned', {E3: exam(session=None, status=doubted(PERFORMED), date=sup(ON))})
        W = eus_beside_egd_today('planned', {E3: exam(session=None, status=doubted(PERFORMED), date=unres(ON))})
        self.assertFalse(d256_p2_letter(R, E3))
        self.assertTrue(d256_p2_letter(W, E3))
        for found in (R, W):
            self.assertEqual((C.possible_examinations(found, X2), C.possible_examinations(found, X1)), ((), (E3,)))
        scenes = [eus_beside_egd_today(eus, extra, entries, part_of=part_of)
                  for eus in ('planned', 'earlier', 'today', 'date open', None)
                  for part_of in (None, sup(X2), unres(X2))
                  for extra, entries in (({E3: exam(session=None, status=doubted(PERFORMED), date=sup(ON))}, ()),
                                         ({E3: act(Kind.EM_VISIT, session=doubted(X1, X2))}, ()),
                                         ({E3: exam(session=unres(X2), date=None)}, ()),
                                         ({}, (unlisted(U_ACT, Kind.EM_VISIT, X2),)))]
        rng = random.Random(20261115)
        scenes += [p2_scene(rng) for _ in range(300)]
        checked = 0
        for S in scenes:
            before = {session_: set(C.possible_examinations(S, session_)) for session_ in (X1, X2)}
            settled = CB.not_done_today(S, X2)
            for change in weakenings(S):
                weak = weaken(S, change)
                for session_ in (X1, X2):
                    self.assertLessEqual(before[session_], set(C.possible_examinations(weak, session_)),
                                         (session_, change[:4]))
                self.assertLessEqual(CB.not_done_today(weak, X2), settled, change[:4])
                checked += 1
        self.assertGreater(checked, 3000)

    def test_p2_coverage_agrees_with_combination_over_generated_scenes(self):
        """D227's agreement on D269's shapes: 3,000 generated FactSets (p2_scene, seeded), each read by coverage and by
        step 4d - X1's and X2's possible examinations against 4d's reading (p2_reference_left_open; a session with any
        is one 4d reads possibly done), both sessions' done against 4d's session_done, and the EGD's whole against 4d's
        wholes and session_possibly_done (one_answer). DECISIONS D269: a session 4d reads established not done today
        lists nothing left open and is never a whole - "settled, possibly done" never occurs (round w8r counted it: a
        carded entry, a claimed session slot, a dated act). The counts assert every arm was exercised: a session
        established not done today beside an entry with no card, a carded entry, an act placed in it, an act dated
        today possibly in it, an examination exempt there that D256 P2's letter left open, and an EGD whose own
        part_of_session claim names it (C3 or D70); a session not settled read possibly done; and the EUS done today
        (C-4 or C3)."""
        rng = random.Random(20261115)
        seen = {'settled, an entry with no card': 0, 'settled, a carded entry': 0, 'settled, an act placed in it': 0,
                'settled, an act dated today possibly in it': 0, 'settled, an examination exempt past the letter': 0,
                'settled, named by the EGD\'s claim': 0, 'not settled, possibly done': 0, 'part of the EUS': 0}
        for _ in range(3000):
            R = p2_scene(rng)
            view = RD.Reading(R)
            sessions_ = C.sessions(R)
            for session_ in (X1, X2):
                left_open = p2_reference_left_open(R, session_)
                self.assertEqual(C.possible_examinations(R, session_), left_open)
                self.assertEqual(sessions_[session_].possible, left_open)
                self.assertEqual(sessions_[session_].done, CB.session_done(R, session_))
                if left_open:
                    self.assertTrue(CB.session_possibly_done(R, session_))
            whole = self.one_answer(R)
            if CB.not_done_today(R, X2):
                self.assertEqual(whole, [])
                seen['settled, an entry with no card'] += any(entry.session is None for entry in R.unlisted)
                seen['settled, a carded entry'] += any(entry.session == X2 for entry in R.unlisted)
                seen['settled, an act placed in it'] += any(F.fact(R, event_, A.SESSION).value == X2
                                                            for event_ in R.events if event_ != E2)
                seen['settled, an act dated today possibly in it'] += any(
                    F.holds(F.fact(R, event_, A.DATE_RELATION), ON) and X2 in CB.possible_sessions(R, event_)
                    for event_ in R.events if event_ not in (E1, E2))
                seen['settled, an examination exempt past the letter'] += any(
                    CB._may_be_examination_of(R, X2, event_) and not RD.done(view, event_)
                    and not d256_p2_letter(R, event_) for event_ in R.events)
                seen['settled, named by the EGD\'s claim'] += X2 in (F.fact(R, X1, A.PART_OF_SESSION).value,
                                                                     *F.fact(R, X1, A.PART_OF_SESSION).options)
            else:
                seen['not settled, possibly done'] += bool(whole and not whole[0][1])
                seen['part of the EUS'] += bool(whole and whole[0][1])
        for name, count in seen.items():
            with self.subTest(arm=name):
                self.assertGreater(count, 50, seen)
