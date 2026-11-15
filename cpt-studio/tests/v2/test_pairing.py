"""Statements against acts: the pairing table (docs/gemini-migration/FINAL-V2.md 4.5, with 4.2, 4.10, 4.11 and 3.2.6 rule
4; step 3d of its 8.1), TEXT-ONLY and SYNTHETIC: every FactSet here is hand-built from engine/types' records (enumeration
members, ids, results and integer spans: the engine's whole input, 4.1). No document is read, no provider is called,
nothing touches the network. The sentences quoted in comments are the design's own (FINAL-V2 4.5, 4.10, 4.11, 3.8, 3.2.3,
2.2 BF17, 1.9); the engine never reads them.

The done-when of 8.1 step 3d, each proved here:
- "every row of 4.5 at every state": SessionRowTests, TimingRowTests, PerformerRowTests, BreadthRowTests,
  TargetRowTests and TechniqueRowTests drive each row over its facts in every state - supported, negated,
  unresolved, doubted (unknown with readings), contradicted, silent - on each side, with the row's own arms (C-8's
  compatible sessions, the general denial and the persons, exceptive and its excepts, the four targets, C-16's devices);
- "independence by any one established difference (HO-2's v3 document READY; 'No prior colonoscopy.' READY; BF17's
  excepted injection READY)": NamedCaseTests and RelationTests (each row alone proving it while every other row is
  unresolved), and P-ANY-ROW in PropertyTests;
- "a general denial covers any performer": the performer row and 4.10's broad denial at every performer of the act,
  including a performer the denial only inherits;
- "possible statements pair (probe (a) beside a genuine snare: held)": WhichPairsTests and NamedCaseTests;
- "an unknown kind or target never sets apart": P-UNKNOWN-KIND (exhaustive over FAMILY_KINDS) and P-UNKNOWN-TARGET, and
  4.11's example;
- "pair controls decide place independence (SC-B's short list: held)": the target row's control arms and SC-B's case,
  in its single-target and its segment form (round 2, the refutation's F1: a segment's act is asked about every place
  of the whole range, its interior included, and a short list beside a segment never releases under either control
  generation - the two ends contract/claims.py asked before DECISIONS D223, or the whole range it asks since);
- "'claimed' turns apart into UNRESOLVED": RelationTests, for every row that can prove independence; and a claimed pair
  no row sets apart asks its first unresolved row's fact, as 4.5 step 2 says (round 2, the refutation's F2);
- "mypy --strict on engine/pairing.py": BoundaryTests, with a positive control.
Also: P-MONO at the pairing level and its same_as corner (round 2: a lesion possibly joined to the act's by same_as is
never set apart by lesion, in any mode); the unlisted pairs of 3.2.6 rule 4; each hold's item at its RANK row, every one
of them among requirements.RULES' clean-row asks; DEVICE_CONTAINS equal to v1's by value; the segment range equal to
contract/claims.py's; 5.7 measure 4 over the module; no retired module, text module or claim builder imported.

Repair r3d (the integration owner's rulings on the refutation of round 2, DECISIONS D220, D223, D228 and D229):
- D228 (DQ1): an act-filed possible statement is set apart by its own target, no pair control required, when both
  targets are established and differ - the refutation's input (a doubted rectal biopsy beside an established
  ascending-colon biopsy, no control: D211 generates none for two biopsies) INDEPENDENT; a target not established on
  either side still sets nothing apart; an act established as of another date or performer keeps the controlled reading
  (TargetRowTests, NamedCaseTests). Round w7r's D238 makes the arm read the controls that exist (below);
- D228 (DQ3): an unlisted pair asks performed_status at RANK row 2, not statement_scope (UnlistedTests);
- D220 in pairing's own listed and segment arms (facts.apart_by_controls, built by repair r2d): every pair control
  between the two objects read, so a member 9.4's weakening deleted leaves its unrejected control holding the pair -
  the refutation's PMONO cases in those two arms, and exhaustively over a grid (TargetRowTests, ScBTests); the single
  arm's case is facts.apart_by_place's, pinned by tests/v2/test_facts.py (D220Tests);
- PT: P-MONO's place-deletion property draws a statement in every target arm against one act, every other row SAME,
  and its generator reaches SC-B's class (a held pair whose only unrejected control asks about the member the weakening
  deletes; pinned); both P-MONO properties assert what the module guarantees: no weakening releases a held act but the
  named releases - D228's (a place deletion beside, or a status weakening into, the arm that requires no pair control;
  narrowed by round w7r's D238 to a control never generated) and repair r2d's two (Q2, a deleted member overlapping the
  other's place without being compatible with it; Q3, a deleted member that was not established) - each checked to be
  exactly that; the which-pairs corner (round 2's Q4, kept by D228) stays out of the weakenings, named (PropertyTests,
  ScBTests); P-UNKNOWN-TARGET names D228's arm (since D238: a control not generated, never one not rejected);
- T1 (mutant X5): a place list with a member not established never sets anything apart, in the listed, the segment and
  the D228 arm, every pair control (the one about that member included) rejected; T2 (mutant X4): an exceptive statement
  that possibly excepts an act whose status is not established is UNRESOLVED on breadth and asks statement_scope, never
  a DOUBT (BreadthRowTests);
- D223's outcome for 3d's R4 input ("No biopsies were taken from the cecum to the hepatic flexure." beside a biopsy
  truly and only in the sigmoid colon): INDEPENDENT once r2c's whole-range pair controls are rejected, on a FactSet and
  end to end through contract/claims.py, settle, the store and the FactSet (NamedCaseTests).

Repair r3d of round w7r (DECISIONS D238 and D239, on refute-r3d-r1's D1 and D2 and round 1's question Q1):
- D238: D228's arm reads the pair controls that EXIST - an unrejected one holds (every place control asked of either
  object, D236's scan; the two lesion controls between the pair, D235), a missing one is not required, so DQ1's outcome
  with no control is kept (TargetRowTests' test_d238_*, ScBTests). End to end through engine/evaluate.decide on
  tests/v2/evaluate_fixtures' colonoscopy: refute-r3d-r1's p3_end_to_end shape (a doubted cold snare truly [rectum,
  transverse colon] filed [rectum], beside the cold snare in the transverse colon) holds 45385 beside an unrejected
  control, either direction; with no control it stays READY, and contract/claims.py generates none for two snares
  (D211) - the repair's question R3D-NC (NamedCaseTests);
- round 1's Q1: (a) and (c) hold; (b), where no control asks about the deleted place, stays INDEPENDENT - the named
  release D228_PLACE, accepted under D228 and D238 (DECISIONS D245); (c) where no control was generated releases by its
  status weakening - D228_STATUS, the repair's question R3D-ST (NamedCaseTests, ScBTests);
- D239: in D228's arm a lesion that may be the act's own - a supported equal lesion, _possibly_same, a claim not
  established whose value or options name the other's lesion (either side), and, read with D238, a lesion pair control
  between them present and not rejected (the repair's question R3D-LC) - is never set apart by place; the
  same-lesion shapes hold 45385 end to end; the controlled arms are unchanged (TargetRowTests, NamedCaseTests);
- 9.4: P-UNKNOWN-TARGET holds in D228's arm for a control generated and not rejected, and excepts there only a control
  not generated (D238); both P-MONO properties name D228's releases exactly (a missing control, never an unrejected
  one: named_release) beside repair r2d's Q2 and Q3 (PropertyTests).
"""
from __future__ import annotations

import dataclasses
import enum
import itertools
import os
import subprocess
import sys
import typing
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation.contract import claims as contract_claims
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import pairing as P
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine import requirements_table as RT
from studio.interpretation.engine.types import Anchor, Fact, FactSet, Id, IdFamily, Span, UnlistedStatement
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'pairing.py'

A, Res, State = ct.Attribute, ct.Result, ct.FactState
Kind, Status, Breadth, Device, Landmark = ct.Kind, ct.Status, ct.Breadth, ct.Device, ct.Landmark
Performer, DateRelation, SessionKind = ct.Performer, ct.DateRelation, ct.SessionKind
INDEPENDENT, UNRESOLVED, SAME = P.RowResult.INDEPENDENT, P.RowResult.UNRESOLVED, P.RowResult.SAME
ON, EARLIER, LATER = DateRelation.ON_DATE_OF_SERVICE, DateRelation.EARLIER_DATE, DateRelation.LATER_DATE
TEAM, OTHER_CLINICIAN, OTHER_FACILITY = Performer.DOCUMENTING_TEAM, Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY
PERFORMED = Status.PERFORMED

E1, E2, E3, E4, E5, E6, E7, E8, E9 = (Id(IdFamily.EVENT, n) for n in range(1, 10))
X1, X2, X3 = (Id(IdFamily.SESSION, n) for n in range(1, 4))
L1, L2, L3, L4 = (Id(IdFamily.LESION, n) for n in range(1, 5))
P1, P2 = Id(IdFamily.PERSON, 1), Id(IdFamily.PERSON, 2)
N1 = Id(IdFamily.SECTION, 1)


# --- building settled facts --------------------------------------------------------------------------------------------


def fact(result: ct.Result, value, state, *, options=(), reasons=(), inherited_from=None) -> Fact:
    return Fact(result=result, value=value, state=state, options=tuple(options), reasons=tuple(reasons), spans=(),
                inherited_from=inherited_from)


def sup(value, **kw) -> Fact:
    """Supported: established, the claim's value."""
    return fact(Res.SUPPORTED, value, State.SUPPORTED, **kw)


def neg(value, **kw) -> Fact:
    """Negated: established, the claim negated."""
    return fact(Res.NEGATED, value, State.NEGATED, **kw)


def unres(value, state=State.SUPPORTED, **kw) -> Fact:
    """Unresolved: a failed check or an appraisal that did not establish it; the claimed value kept."""
    return fact(Res.UNRESOLVED, value, state, reasons=(ct.Reason.APPRAISAL_UNCLEAR,), **kw)


def doubted(value, *readings, state=State.SUPPORTED, **kw) -> Fact:
    """A doubt (3.3 row 2): unknown, the claimed value and the doubt's readings kept."""
    return fact(Res.UNKNOWN, value, state, options=readings, reasons=(ct.Reason.DOUBT_UNCLEAR,), **kw)


def contra(*sides, **kw) -> Fact:
    """Pass 1's contradicted fact (3.3 row 1): its sides are its options, its value None."""
    return fact(Res.CONTRADICTED, None, State.CONTRADICTED, options=sides, reasons=(ct.Reason.CONTRADICTED_BY_PASS1,),
                **kw)


SILENT = F.SILENT
STATES = ('supported', 'negated', 'unresolved', 'doubted', 'contradicted', 'silent')
NOT_ESTABLISHED = ('unresolved', 'doubted', 'contradicted', 'silent')


def in_state(name: str, value, other=None) -> Fact:
    """``value`` in the state ``name`` (a contradicted fact's sides are ``value`` and ``other``)."""
    return {'supported': lambda: sup(value), 'negated': lambda: neg(value), 'unresolved': lambda: unres(value),
            'doubted': lambda: doubted(value), 'contradicted': lambda: contra(value, other if other is not None else value),
            'silent': lambda: SILENT}[name]()


NAMES = {
    'kind': A.KIND, 'status': A.STATUS, 'session': A.SESSION, 'date': A.DATE_RELATION, 'performer': A.PERFORMER,
    'person': A.PERFORMER_PERSON, 'breadth': A.SCOPE_BREADTH, 'excepts': A.SCOPE_EXCEPTS, 'covers': A.SCOPE_COVERS,
    'targets': A.SCOPE_TARGETS, 'segment': A.SCOPE_SEGMENT, 'lesion': A.TARGET_LESION, 'places': A.TARGET_PLACES,
    'device': A.TECHNIQUE_DEVICE, 'purpose': A.PURPOSE,
}
MANY = {'excepts', 'covers', 'targets', 'segment', 'places'}


def event(**attributes) -> dict:
    """An event's facts by attribute; a multi-valued attribute is a tuple of member facts (() for an empty list); an
    attribute given as None is left out (it reads as SILENT, or as no member)."""
    out = {}
    for name, value in attributes.items():
        if value is None:
            continue
        if name in MANY:
            out[NAMES[name]] = tuple(value)
        else:
            out[NAMES[name]] = (value,)
    return out


def denial(**over) -> dict:
    """An established statement-filed denial (4.10's broad denial by default): a snare, its status performed negated,
    session X1, on the date of service, all of its kind, naming no performer and no device."""
    base = dict(kind=sup(Kind.SNARE), status=neg(PERFORMED), session=sup(X1), date=sup(ON),
                breadth=sup(Breadth.ALL_OF_KIND))
    base.update(over)
    return event(**base)


def act(**over) -> dict:
    """An established act: a cold-snare removal in X1, today, by the documenting team, of lesion L1 in the sigmoid colon."""
    base = dict(kind=sup(Kind.SNARE), status=sup(PERFORMED), session=sup(X1), date=sup(ON), performer=sup(TEAM),
                places=(sup(Landmark.SIGMOID_COLON),), lesion=sup(L1), device=sup(Device.COLD_SNARE))
    base.update(over)
    return event(**base)


def session_of(kind) -> dict:
    return {A.KIND: (kind if isinstance(kind, Fact) else sup(kind),)}


def lesion_of(distinct=(), same=()) -> dict:
    return {A.DISTINCT_FROM: tuple(sup(other) for other in distinct), A.SAME_AS: tuple(sup(other) for other in same)}


def build(events: dict, *, sessions=None, lesions=None, controls=None, unlisted=(), anchors=None) -> FactSet:
    """A settled FactSet: ``events`` in order; one colonoscopy session X1 unless ``sessions`` says otherwise; each event's
    anchor one unit of its own."""
    if sessions is None:
        sessions = {X1: session_of(SessionKind.COLONOSCOPY)}
    if anchors is None:
        anchors = {subject: Anchor(units=(Span(100 * subject.number, 100 * subject.number + 40),), kind_words=None,
                                   status_words=None) for subject in events}
    return FactSet(encounter={}, people={}, sections={}, sessions=sessions, anatomy={}, lesions=lesions or {},
                   events=events, anchors=anchors, unlisted=tuple(unlisted), pair_controls=controls or {},
                   completeness={})


def controls_both_ways(statement, act_, statement_places=(), act_places=(), statement_lesions=(), act_lesions=(),
                       rejected=True) -> dict:
    """Pair controls asking the act about each of the statement's places and lesions, and the statement about each of the
    act's (3.2.3 [R:SC-B]), each rejected (True) or not."""
    out = {}
    for place in statement_places:
        out[(act_, A.TARGET_PLACES, place)] = rejected
    for place in act_places:
        out[(statement, A.TARGET_PLACES, place)] = rejected
    for lesion in statement_lesions:
        out[(act_, A.TARGET_LESION, lesion)] = rejected
    for lesion in act_lesions:
        out[(statement, A.TARGET_LESION, lesion)] = rejected
    return out


def claims_pair_controls(statement, statement_places, act_, act_places, rejected) -> dict:
    """The place pair controls as contract/claims.py's pair() generates them, both directions: each object asked about
    every place of the other that none of its own places is compatible with (engine/anatomy.compatible). The places
    given for each object are the places claims.places names for it; ``rejected(subject, place)`` is pass 2's answer
    (True: contradicts)."""
    out = {}
    for asked, own, theirs in ((statement, statement_places, act_places), (act_, act_places, statement_places)):
        for place in dict.fromkeys(theirs):
            if not any(anatomy.compatible(place, mine) for mine in own):
                out[(asked, A.TARGET_PLACES, place)] = rejected(asked, place)
    return out


def claimable(members) -> tuple:
    """The places contract/claims.py's places() names of a target places list: the members claimed with a supported
    state (a member pass 2 did not establish included; a contradicted, negated or silent one never)."""
    return tuple(item.value for item in members if item.state is State.SUPPORTED)


# The whole range of a segment from the cecum to the hepatic flexure (DECISIONS D196): the places every pair control
# of the act must ask about (the refutation's F1).
WHOLE_CECUM_TO_HEPATIC_FLEXURE = P.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)


def row_of(R: FactSet, which: P.Row, statement=E1, act_=E2) -> P.RowResult:
    return P.row(R, which, statement, act_)


def relation_of(R: FactSet, statement=E1, act_=E2) -> P.Pair:
    return P.relation(R, statement, act_)


# A FactSet in which every row is UNRESOLVED for E1 (a statement-filed denial) against E2 (an established act): the base
# that proves one established difference suffices ("whatever else is unknown", 4.5 relation 1).
def all_unresolved(**denial_over) -> dict:
    base = dict(session=unres(X1), date=unres(ON), performer=unres(TEAM), breadth=unres(Breadth.SINGLE_TARGET),
                device=unres(Device.COLD_SNARE))
    base.update(denial_over)
    return denial(**base)


TWO_SESSIONS = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.COLONOSCOPY)}


# --- which pairs (4.5) -------------------------------------------------------------------------------------------------


class WhichPairsTests(SimpleTestCase):
    def test_an_established_denial_is_a_statement_and_an_established_todays_act_is_not(self):
        R = build({E1: denial(), E2: act()})
        self.assertTrue(P.is_statement(R, E1))
        self.assertFalse(P.possible(R, E1))
        self.assertTrue(P.filed_as_statement(R, E1))
        self.assertFalse(P.is_statement(R, E2))
        self.assertEqual(P.statements(R), (E1,))
        self.assertTrue(P.paired(R, E1, E2))
        self.assertFalse(P.paired(R, E2, E1))

    def test_every_status_that_is_not_established_makes_a_possible_statement(self):
        # HO-1, HO-3: doubted, contradicted, failed, unappraised, silent - for an act-filed and a statement-filed claim
        for name, status in (('unresolved, act-filed', unres(PERFORMED)),
                             ('unresolved, statement-filed', unres(PERFORMED, state=State.NEGATED)),
                             ('doubted', doubted(PERFORMED, PERFORMED)),
                             ('contradicted', contra(PERFORMED, PERFORMED)), ('silent', SILENT)):
            with self.subTest(status=name):
                R = build({E1: act(status=status), E2: act(places=(sup(Landmark.RECTUM),))})
                self.assertTrue(P.is_statement(R, E1))
                self.assertTrue(P.possible(R, E1))
                self.assertTrue(P.paired(R, E1, E2))
                # a possible statement is possibly performed too, so the established act... is not a statement
                self.assertFalse(P.paired(R, E2, E1))

    def test_an_act_of_another_date_or_performer_is_a_statement(self):
        for name, over in (('earlier', dict(date=sup(EARLIER))), ('later', dict(date=sup(LATER))),
                           ('today negated', dict(date=neg(ON))),
                           ('other clinician', dict(performer=sup(OTHER_CLINICIAN))),
                           ('other facility', dict(performer=sup(OTHER_FACILITY))),
                           ('inherited other clinician', dict(performer=sup(OTHER_CLINICIAN, inherited_from=N1))),
                           ('team negated', dict(performer=neg(TEAM)))):
            with self.subTest(over=name):
                R = build({E1: act(**over), E2: act(places=(sup(Landmark.RECTUM),))})
                self.assertTrue(P.is_statement(R, E1))
                self.assertFalse(P.possible(R, E1))
                self.assertTrue(P.paired(R, E1, E2))
        for name, over in (('team, today', {}), ('date not established', dict(date=unres(EARLIER))),
                           ('earlier negated', dict(date=neg(EARLIER))), ('performer silent', dict(performer=None)),
                           ('other clinician negated', dict(performer=neg(OTHER_CLINICIAN))),
                           ('planned today', dict(status=sup(Status.PLANNED)))):
            with self.subTest(over=name):
                self.assertFalse(P.is_statement(build({E1: act(**over)}), E1))

    def test_the_act_side_is_every_event_possibly_performed(self):
        for name, status, pairs in (('performed', sup(PERFORMED), True), ('unresolved', unres(PERFORMED), True),
                                    ('doubted', doubted(PERFORMED), True), ('contradicted', contra(PERFORMED, PERFORMED),
                                                                           True),
                                    ('silent', SILENT, True), ('denied', neg(PERFORMED), False),
                                    ('planned', sup(Status.PLANNED), False),
                                    ('attempted', sup(Status.ATTEMPTED_NOT_COMPLETED), False)):
            with self.subTest(status=name):
                R = build({E1: denial(), E2: act(status=status)})
                self.assertEqual(P.paired(R, E1, E2), pairs)

    def test_an_event_never_pairs_with_itself_and_two_possible_statements_pair_both_ways(self):
        R = build({E1: act(status=unres(PERFORMED)), E2: act(status=doubted(PERFORMED))})
        self.assertFalse(P.paired(R, E1, E1))
        self.assertTrue(P.paired(R, E1, E2))
        self.assertTrue(P.paired(R, E2, E1))
        with self.assertRaises(ValueError):
            P.relation(R, E1, E1)

    def test_compatible_kinds_equal_a_tattoo_with_an_injection_and_an_umbrella_over_its_member(self):
        cases = (
            (Kind.SNARE, Kind.SNARE, True), (Kind.TATTOO, Kind.INJECTION, True), (Kind.INJECTION, Kind.TATTOO, True),
            (Kind.REMOVAL, Kind.SNARE, True), (Kind.REMOVAL, Kind.EMR, True), (Kind.INTERVENTION, Kind.BIOPSY, True),
            (Kind.SNARE, Kind.REMOVAL, False),  # D's umbrella covers A's kind, never the other way (catalogue.covers)
            (Kind.SNARE, Kind.BIOPSY, False), (Kind.EMR, Kind.SNARE, False), (Kind.OTHER, Kind.OTHER, False),
            (Kind.CLIP, Kind.BLEEDING_CONTROL, False))
        for statement_kind, act_kind, pairs in cases:
            with self.subTest(statement=statement_kind.value, act=act_kind.value):
                R = build({E1: denial(kind=sup(statement_kind)), E2: act(kind=sup(act_kind))})
                self.assertEqual(P.paired(R, E1, E2), pairs)
                if pairs:
                    self.assertIn(act_kind, relation_of(R).kinds)

    def test_an_act_kind_not_established_is_possible_as_its_claimed_value_options_and_control_sibling(self):
        # 4.2: as a candidate (the act side) an unestablished kind is its claimed value, its readings, its control's
        # sibling; silent, every kind
        R = build({E1: denial(kind=sup(Kind.SNARE)), E2: act(kind=unres(Kind.EMR, options=(Kind.SNARE,)))})
        self.assertTrue(P.paired(R, E1, E2))
        R = build({E1: denial(kind=sup(Kind.SNARE)), E2: act(kind=unres(Kind.EMR))})
        self.assertFalse(P.paired(R, E1, E2))
        R = build({E1: denial(kind=sup(Kind.SNARE)), E2: act(kind=SILENT)})
        self.assertTrue(P.paired(R, E1, E2))

    def test_a_clip_or_injection_that_may_be_for_hemostasis_pairs_with_a_bleeding_control_statement(self):
        # the catalogue reads a clip or an injection whose purpose is hemostasis as a bleeding control
        # (catalogue.catalogue_kind), and one whose purpose is not established may be one (D157, FINAL-V2 4.13)
        for kind in (Kind.CLIP, Kind.INJECTION):
            for name, purpose, pairs in (('hemostasis', sup(ct.Purpose.HEMOSTASIS), True), ('silent', SILENT, True),
                                         ('unresolved', unres(ct.Purpose.HEMOSTASIS), True),
                                         ('doubted towards hemostasis',
                                          doubted(ct.Purpose.PROPHYLAXIS, ct.Purpose.HEMOSTASIS), True),
                                         ('prophylaxis', sup(ct.Purpose.PROPHYLAXIS), False),
                                         ('marking', sup(ct.Purpose.MARKING), False)):
                with self.subTest(kind=kind.value, purpose=name):
                    R = build({E1: denial(kind=sup(Kind.BLEEDING_CONTROL)), E2: act(kind=sup(kind), purpose=purpose)})
                    self.assertEqual(P.paired(R, E1, E2), pairs)
        # never for another kind, and a statement's purpose (never claimed, 3.2.1) widens nothing
        R = build({E1: denial(kind=sup(Kind.BLEEDING_CONTROL)), E2: act(kind=sup(Kind.ABLATION),
                                                                         purpose=sup(ct.Purpose.HEMOSTASIS))})
        self.assertFalse(P.paired(R, E1, E2))
        R = build({E1: denial(kind=sup(Kind.CLIP), purpose=sup(ct.Purpose.HEMOSTASIS)),
                   E2: act(kind=sup(Kind.BLEEDING_CONTROL))})
        self.assertFalse(P.paired(R, E1, E2))

    def test_the_kinds_pairs_and_closure_agree_with_the_requirement_table(self):
        # requirements.statement_kinds (step 1f's closure, 4.9) holds every statement kind that pairs through
        # catalogue.covers; the catalogue's bleeding-control reading is request R1 (the step's NOTES)
        for act_kind in Kind:
            for statement_kind in Kind:
                R = build({E1: denial(kind=sup(statement_kind)), E2: act(kind=sup(act_kind), purpose=sup(
                    ct.Purpose.MARKING))})
                with self.subTest(statement=statement_kind.value, act=act_kind.value):
                    self.assertEqual(P.paired(R, E1, E2), statement_kind in rq.statement_kinds(frozenset({act_kind})))
        # with the act's purpose not established, the catalogue's bleeding-control reading adds exactly the bleeding
        # control statement beside a clip or an injection - the pairs request R1 adds to statement_kinds (the closure)
        for act_kind in Kind:
            for statement_kind in Kind:
                R = build({E1: denial(kind=sup(statement_kind)), E2: act(kind=sup(act_kind), purpose=SILENT)})
                expected = statement_kind in rq.statement_kinds(frozenset({act_kind})) or (
                    statement_kind is Kind.BLEEDING_CONTROL and act_kind in (Kind.CLIP, Kind.INJECTION))
                with self.subTest(statement=statement_kind.value, act=act_kind.value, purpose='silent'):
                    self.assertEqual(P.paired(R, E1, E2), expected)


# --- every row at every state (4.5) ------------------------------------------------------------------------------------


def established_values(found: Fact, domain):
    """The spec's reading of an established fact (4.5: "both established and different"): supported, its value;
    negated, every other value; None when not established."""
    if found.result is Res.SUPPORTED:
        return frozenset({found.value})
    if found.result is Res.NEGATED:
        return frozenset(member for member in domain if member is not found.value)
    return None


def spec_compare(first: Fact, second: Fact, domain) -> P.RowResult:
    one, other = established_values(first, domain), established_values(second, domain)
    if one is None or other is None:
        return UNRESOLVED
    if not one & other:
        return INDEPENDENT
    return SAME if len(one) == 1 and one == other else UNRESOLVED


class SessionRowTests(SimpleTestCase):
    """C-8: INDEPENDENT when both sessions are established and different; UNRESOLVED when either is not established while
    two or more sessions of a compatible family exist; SAME otherwise."""

    def facts(self, value):
        return [(name, in_state(name, value, X2)) for name in STATES]

    def test_every_state_on_each_side(self):
        for sessions, compatible in ((TWO_SESSIONS, 2), ({X1: session_of(SessionKind.COLONOSCOPY)}, 1)):
            for d_name, d_session in self.facts(X1) + [('supported X2', sup(X2))]:
                for a_name, a_session in self.facts(X1) + [('supported X2', sup(X2))]:
                    R = build({E1: denial(session=d_session), E2: act(session=a_session)}, sessions=sessions)
                    both = d_session.result is Res.SUPPORTED and a_session.result is Res.SUPPORTED
                    if both:
                        expected = SAME if d_session.value == a_session.value else INDEPENDENT
                    else:
                        expected = UNRESOLVED if compatible >= 2 else SAME
                    with self.subTest(sessions=compatible, statement=d_name, act=a_name):
                        self.assertEqual(row_of(R, P.Row.SESSION), expected)

    def test_only_sessions_of_a_compatible_family_count(self):
        # a snare: an office visit's session cannot hold it, so one compatible session remains: SAME
        office = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.OFFICE_EM)}
        R = build({E1: denial(session=SILENT), E2: act()}, sessions=office)
        self.assertEqual(row_of(R, P.Row.SESSION), SAME)
        # an upper endoscopy can hold a snare (FAMILY_KINDS): two compatible sessions, UNRESOLVED
        upper = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        R = build({E1: denial(session=SILENT), E2: act()}, sessions=upper)
        self.assertEqual(row_of(R, P.Row.SESSION), UNRESOLVED)
        # a session whose kind is not established may be of any family: it counts
        unknown = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(unres(SessionKind.OFFICE_EM))}
        R = build({E1: denial(session=SILENT), E2: act()}, sessions=unknown)
        self.assertEqual(row_of(R, P.Row.SESSION), UNRESOLVED)
        # the act's unknown session among two compatible sessions is as unknown as the statement's
        R = build({E1: denial(), E2: act(session=unres(X1))}, sessions=TWO_SESSIONS)
        self.assertEqual(row_of(R, P.Row.SESSION), UNRESOLVED)


class TimingRowTests(SimpleTestCase):
    """Both effective date relations established and different: INDEPENDENT; equal: SAME; either not established:
    UNRESOLVED."""

    def test_every_state_on_each_side(self):
        variants = [(f'{name} {value.value}', in_state(name, value, EARLIER if value is ON else ON))
                    for name in STATES for value in (ON, EARLIER)]
        for d_name, d_date in variants:
            for a_name, a_date in variants:
                R = build({E1: denial(date=d_date), E2: act(date=a_date)})
                with self.subTest(statement=d_name, act=a_name):
                    self.assertEqual(row_of(R, P.Row.TIMING), spec_compare(d_date, a_date, DateRelation))

    def test_the_named_arms(self):
        R = build({E1: denial(date=sup(EARLIER)), E2: act()})
        self.assertEqual(row_of(R, P.Row.TIMING), INDEPENDENT)
        R = build({E1: denial(), E2: act()})
        self.assertEqual(row_of(R, P.Row.TIMING), SAME)
        R = build({E1: denial(date=unres(EARLIER)), E2: act()})
        self.assertEqual(row_of(R, P.Row.TIMING), UNRESOLVED)
        R = build({E1: denial(date=neg(ON)), E2: act(date=sup(EARLIER))})  # another date, but which one
        self.assertEqual(row_of(R, P.Row.TIMING), UNRESOLVED)


class PerformerRowTests(SimpleTestCase):
    def act_performers(self):
        return [(name, in_state(name, value, OTHER_CLINICIAN if value is TEAM else TEAM))
                for name in STATES for value in (TEAM, OTHER_CLINICIAN)] + [
            ('inherited other clinician', sup(OTHER_CLINICIAN, inherited_from=N1))]

    def test_a_general_denial_covers_any_performer(self):
        # D's own statement names no performer (silent), or only inherits one from its section (D188): SAME, whatever
        # the act's performer is in whatever state
        for d_name, d_performer in (('silent', SILENT), ('inherited other clinician',
                                                         sup(OTHER_CLINICIAN, inherited_from=N1)),
                                    ('inherited and unresolved', unres(TEAM, inherited_from=N1))):
            for a_name, a_performer in self.act_performers():
                R = build({E1: denial(performer=d_performer), E2: act(performer=a_performer)})
                with self.subTest(statement=d_name, act=a_name):
                    self.assertEqual(row_of(R, P.Row.PERFORMER), SAME)

    def test_a_named_performer_at_every_state(self):
        for d_name in STATES[:-1]:  # every state of a named (not silent) performer
            for d_value in (TEAM, OTHER_FACILITY):
                d_performer = in_state(d_name, d_value, OTHER_CLINICIAN)
                for a_name, a_performer in self.act_performers():
                    R = build({E1: denial(performer=d_performer), E2: act(performer=a_performer)})
                    expected = spec_compare(d_performer, a_performer, Performer)
                    with self.subTest(statement=f'{d_name} {d_value.value}', act=a_name):
                        self.assertEqual(row_of(R, P.Row.PERFORMER), expected)

    def test_two_other_clinicians_are_told_apart_only_by_established_persons(self):
        cases = (
            (sup(P1), sup(P2), INDEPENDENT), (sup(P1), sup(P1), SAME), (sup(P1), SILENT, UNRESOLVED),
            (SILENT, sup(P2), UNRESOLVED), (SILENT, SILENT, UNRESOLVED), (unres(P1), sup(P2), UNRESOLVED),
            (sup(P1), doubted(P2, P1), UNRESOLVED),
            (sup(P1, inherited_from=N1), sup(P2), UNRESOLVED))  # D's person must be its own statement's
        for d_person, a_person, expected in cases:
            R = build({E1: denial(performer=sup(OTHER_CLINICIAN), person=d_person),
                       E2: act(performer=sup(OTHER_CLINICIAN), person=a_person)})
            with self.subTest(statement=d_person, act=a_person):
                self.assertEqual(row_of(R, P.Row.PERFORMER), expected)

    def test_different_classes_are_independent(self):
        R = build({E1: denial(performer=sup(OTHER_CLINICIAN)), E2: act(performer=sup(TEAM))})
        self.assertEqual(row_of(R, P.Row.PERFORMER), INDEPENDENT)
        R = build({E1: denial(performer=sup(OTHER_FACILITY)), E2: act(performer=sup(OTHER_FACILITY))})
        self.assertEqual(row_of(R, P.Row.PERFORMER), SAME)


class BreadthRowTests(SimpleTestCase):
    def test_a_statement_filed_breadth_at_every_state(self):
        for name in STATES:
            for value in Breadth:
                if value is Breadth.EXCEPTIVE:
                    continue
                breadth = in_state(name, value, Breadth.EXCEPTIVE)
                R = build({E1: denial(breadth=breadth), E2: act()})
                expected = SAME if name == 'supported' else UNRESOLVED
                with self.subTest(state=name, breadth=value.value):
                    self.assertEqual(row_of(R, P.Row.BREADTH), expected)

    def test_exceptive_and_its_excepts(self):
        exceptive = sup(Breadth.EXCEPTIVE)
        cases = (
            ('the act excepted, established', (sup(E2),), sup(PERFORMED), INDEPENDENT),
            ('excepted with another act', (sup(E3), sup(E2)), sup(PERFORMED), INDEPENDENT),
            ('possibly excepted, not established', (unres(E2),), sup(PERFORMED), UNRESOLVED),
            ('excepted by a doubt reading only', (doubted(E3, E2),), sup(PERFORMED), UNRESOLVED),
            ('excepted by a contradicted member', (contra(E3, E2),), sup(PERFORMED), UNRESOLVED),
            ('not excepted, the act established', (sup(E3),), sup(PERFORMED), UNRESOLVED),
            ('not excepted, the act not established', (sup(E3),), unres(PERFORMED), SAME),
            ('excepted while the act is not established', (sup(E2),), doubted(PERFORMED), INDEPENDENT))
        for name, excepts, status, expected in cases:
            R = build({E1: denial(kind=sup(Kind.INJECTION), breadth=exceptive, excepts=excepts),
                       E2: act(kind=sup(Kind.INJECTION), status=status), E3: act(kind=sup(Kind.INJECTION))})
            with self.subTest(case=name):
                self.assertEqual(row_of(R, P.Row.BREADTH), expected)

    def test_t2_a_possibly_excepted_act_whose_status_is_not_established_is_unresolved_on_breadth(self):
        # the refutation's T2 (mutant X4): the "possibly excepted" arm was pinned only with the act's status
        # established, where the "no other against an act it does not except" arm answers UNRESOLVED too. With the
        # act's status not established that arm is SAME, so only the possibly-excepted arm keeps the row UNRESOLVED:
        # the pair asks statement_scope (rank 3), never a DOUBT's performed_status (rank 2), whatever else is SAME
        exceptive = sup(Breadth.EXCEPTIVE)
        possibly = (('unresolved', (unres(E2),)), ('a doubt reading', (doubted(E3, E2),)),
                    ('contradicted', (contra(E3, E2),)), ('beside an excepted other act', (sup(E3), unres(E2))))
        statuses = (('unresolved', unres(PERFORMED)), ('doubted', doubted(PERFORMED)),
                    ('contradicted', contra(PERFORMED, Status.PLANNED)), ('silent', SILENT))
        checked = 0
        for name, excepts in possibly:
            for status_name, status in statuses:
                R = build({E1: denial(kind=sup(Kind.INJECTION), breadth=exceptive, excepts=excepts),
                           E2: act(kind=sup(Kind.INJECTION), status=status, lesion=SILENT, device=sup(Device.NEEDLE)),
                           E3: act(kind=sup(Kind.INJECTION), lesion=SILENT, device=sup(Device.NEEDLE))})
                pair = relation_of(R)
                with self.subTest(excepts=name, status=status_name):
                    self.assertEqual(pair.result(P.Row.BREADTH), UNRESOLVED)
                    self.assertEqual([found for _row, found in pair.rows if found is not SAME], [UNRESOLVED])
                    self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                    self.assertIs(pair.row, P.Row.BREADTH)
                    self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
                checked += 1
        self.assertEqual(checked, 16)
        # the act not excepted at all and its status not established: SAME, so the pair is a DOUBT (the arm X4 reaches)
        R = build({E1: denial(kind=sup(Kind.INJECTION), breadth=exceptive, excepts=(sup(E3),)),
                   E2: act(kind=sup(Kind.INJECTION), status=unres(PERFORMED), lesion=SILENT, device=sup(Device.NEEDLE)),
                   E3: act(kind=sup(Kind.INJECTION), lesion=SILENT, device=sup(Device.NEEDLE))})
        pair = relation_of(R)
        self.assertEqual(pair.result(P.Row.BREADTH), SAME)
        self.assertIs(pair.relation, P.Relation.DOUBT)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS))

    def test_an_act_filed_possible_statement_has_no_breadth(self):
        # 4.5 [R:HO-3]: its own target stands for a single target, so the target row decides
        for breadth in (SILENT, unres(Breadth.ALL_OF_KIND), sup(Breadth.EXCEPTIVE)):
            R = build({E1: act(status=unres(PERFORMED), breadth=breadth), E2: act()})
            with self.subTest(breadth=breadth):
                self.assertEqual(row_of(R, P.Row.BREADTH), SAME)
        # a statement-filed possible statement keeps the breadth it was claimed with
        R = build({E1: denial(status=unres(PERFORMED, state=State.NEGATED), breadth=unres(Breadth.ALL_OF_KIND)),
                   E2: act()})
        self.assertEqual(row_of(R, P.Row.BREADTH), UNRESOLVED)
        R = build({E1: denial(status=unres(PERFORMED, state=State.NEGATED)), E2: act()})
        self.assertEqual(row_of(R, P.Row.BREADTH), SAME)
        # an act established as of another performer carries no breadth (K1), which is not established: UNRESOLVED
        R = build({E1: act(performer=sup(OTHER_CLINICIAN, inherited_from=N1)), E2: act()})
        self.assertEqual(row_of(R, P.Row.BREADTH), UNRESOLVED)


class TargetRowTests(SimpleTestCase):
    def single(self, **over):
        base = dict(breadth=sup(Breadth.SINGLE_TARGET))
        base.update(over)
        return denial(**base)

    def test_all_of_kind_and_exceptive_leave_the_target_out(self):
        for breadth in (Breadth.ALL_OF_KIND, Breadth.EXCEPTIVE):
            R = build({E1: denial(breadth=sup(breadth), places=(sup(Landmark.RECTUM),), excepts=(sup(E3),)),
                       E2: act(places=(SILENT,)), E3: act()})
            with self.subTest(breadth=breadth.value):
                self.assertEqual(row_of(R, P.Row.TARGET), SAME)

    def test_a_single_target_set_apart_by_lesion_needs_distinct_from_and_both_controls(self):
        lesions = {L1: lesion_of(), L2: lesion_of(distinct=(L1,))}
        both = controls_both_ways(E1, E2, statement_lesions=(L1,), act_lesions=(L2,))
        R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L2), places=(SILENT,))}, lesions=lesions,
                  controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        for missing in both:
            with self.subTest(missing=missing):
                partial = {key: value for key, value in both.items() if key != missing}
                R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L2), places=(SILENT,))},
                          lesions=lesions, controls=partial)
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
                R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L2), places=(SILENT,))},
                          lesions=lesions, controls={**both, missing: False})
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L2), places=(SILENT,))},
                  lesions={L1: lesion_of(), L2: lesion_of()}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)  # lesions possibly the same: no distinct_from

    def test_the_same_lesion_is_same(self):
        R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L1), places=(SILENT,))})
        self.assertEqual(row_of(R, P.Row.TARGET), SAME)
        R = build({E1: self.single(lesion=sup(L1)), E2: act(lesion=sup(L2), places=(SILENT,))},
                  lesions={L1: lesion_of(same=(L2,)), L2: lesion_of()})
        self.assertEqual(row_of(R, P.Row.TARGET), SAME)

    def test_a_lesion_possibly_the_same_is_never_set_apart_by_lesion(self):
        # same_as is UNCONTROLLED because it only joins (3.2.3): a statement lesion that same_as possibly joins to the
        # act's lesion never sets the pair apart by lesion, in any mode, whatever distinct_from and the lesion controls
        # say - and read by possibly, a weakened same_as still holds (P-MONO: the round-2 probe O1 went CONTRADICTION
        # -> INDEPENDENT when same_as(L1, L3) was weakened beside a listed statement)
        listed = dict(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1), sup(L2)))
        single = dict(breadth=sup(Breadth.SINGLE_TARGET), lesion=sup(L1))
        segment = dict(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)),
                       lesion=sup(L1))
        controls = controls_both_ways(E1, E2, statement_lesions=(L1, L2), act_lesions=(L3,))
        apart = {L1: lesion_of(distinct=(L3,)), L2: lesion_of(distinct=(L3,)), L3: lesion_of()}
        for mode, over in (('listed', listed), ('single', single), ('segment', segment)):
            R = build({E1: denial(**over), E2: act(lesion=sup(L3), places=(SILENT,))}, lesions=apart, controls=controls)
            with self.subTest(mode=mode, same_as='none'):
                self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
            joins = {'supported': lambda target: sup(target), 'unresolved': lambda target: unres(target),
                     'doubted': lambda target: doubted(L4, target), 'contradicted': lambda target: contra(target, L4)}
            for name, join in joins.items():
                for where, target in ((L1, L3), (L3, L1)):  # in the statement lesion's list, or in the act lesion's
                    lesions = {**apart, where: {**apart[where], A.SAME_AS: (join(target),)}}
                    R = build({E1: denial(**over), E2: act(lesion=sup(L3), places=(SILENT,))}, lesions=lesions,
                              controls=controls)
                    with self.subTest(mode=mode, same_as=name, listed_on=where):
                        self.assertNotEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
            # an established denial of the join (same_as negated) leaves the pair apart
            lesions = {**apart, L1: {**apart[L1], A.SAME_AS: (neg(L3),)}}
            R = build({E1: denial(**over), E2: act(lesion=sup(L3), places=(SILENT,))}, lesions=lesions,
                      controls=controls)
            with self.subTest(mode=mode, same_as='negated'):
                self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)

    def test_a_single_target_set_apart_by_place_needs_both_controls(self):
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        R = build({E1: self.single(places=(sup(Landmark.RECTUM),)), E2: act(lesion=SILENT)}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        for missing in both:
            with self.subTest(missing=missing):
                R = build({E1: self.single(places=(sup(Landmark.RECTUM),)), E2: act(lesion=SILENT)},
                          controls={key: value for key, value in both.items() if key != missing})
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
                R = build({E1: self.single(places=(sup(Landmark.RECTUM),)), E2: act(lesion=SILENT)},
                          controls={**both, missing: False})
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)

    def test_overlapping_places_are_same_and_places_neither_overlapping_nor_disjoint_are_unresolved(self):
        cases = (((Landmark.RECTUM,), (Landmark.SIGMOID_COLON, Landmark.RECTUM), SAME),
                 ((Landmark.SIGMOID_COLON,), (Landmark.COLON,), SAME),  # containment
                 ((Landmark.COLON,), (Landmark.CECUM,), SAME),
                 ((Landmark.RECTUM,), (Landmark.ANASTOMOSIS,), UNRESOLVED),  # a surgically made place: never disjoint
                 ((Landmark.OTHER,), (Landmark.RECTUM,), UNRESOLVED))
        for own, other, expected in cases:
            both = controls_both_ways(E1, E2, statement_places=own, act_places=other)
            R = build({E1: self.single(places=tuple(sup(place) for place in own)),
                       E2: act(lesion=SILENT, places=tuple(sup(place) for place in other))}, controls=both)
            with self.subTest(statement=own, act=other):
                self.assertEqual(row_of(R, P.Row.TARGET), expected)

    def test_an_unknown_target_on_either_side_never_sets_apart(self):
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,),
                                  statement_lesions=(L1,), act_lesions=(L2,))
        lesions = {L1: lesion_of(distinct=(L2,)), L2: lesion_of()}
        for name in NOT_ESTABLISHED:
            for side in ('statement', 'act'):
                place = in_state(name, Landmark.RECTUM if side == 'statement' else Landmark.SIGMOID_COLON,
                                 Landmark.CECUM)
                lesion = in_state(name, L1 if side == 'statement' else L2, L3)
                d = self.single(places=(place,) if side == 'statement' else (sup(Landmark.RECTUM),),
                                lesion=lesion if side == 'statement' else sup(L1))
                a = act(places=(place,) if side == 'act' else (sup(Landmark.SIGMOID_COLON),),
                        lesion=lesion if side == 'act' else sup(L2))
                R = build({E1: d, E2: a}, lesions=lesions, controls=both)
                with self.subTest(state=name, side=side):
                    self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        # an empty place list is no member: unknown, never an absence (P3)
        R = build({E1: self.single(places=()), E2: act(lesion=SILENT)}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)

    def test_listed_targets_read_scope_targets(self):
        # hand-off 2d#6: the target row reads scope.targets for listed_targets
        listed = dict(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1), sup(L2)))
        lesions = {L1: lesion_of(distinct=(L3,)), L2: lesion_of(distinct=(L3,)), L3: lesion_of()}
        both = controls_both_ways(E1, E2, statement_lesions=(L1, L2), act_lesions=(L3,))
        R = build({E1: denial(**listed), E2: act(lesion=sup(L3), places=(SILENT,))}, lesions=lesions, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        R = build({E1: denial(**listed), E2: act(lesion=sup(L2), places=(SILENT,))}, lesions=lesions, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), SAME)
        for name, over, controls in (
                ('a target not established', dict(targets=(sup(L1), unres(L2))), both),
                ('one distinct_from missing', {}, both),
                ('a lesion control missing', {}, {k: v for k, v in both.items() if k != (E2, A.TARGET_LESION, L2)}),
                ('the statement control not rejected', {}, {**both, (E1, A.TARGET_LESION, L3): False})):
            the_lesions = {**lesions, L2: lesion_of()} if name == 'one distinct_from missing' else lesions
            R = build({E1: denial(**{**listed, **over}), E2: act(lesion=sup(L3), places=(SILENT,))},
                      lesions=the_lesions, controls=controls)
            with self.subTest(case=name):
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        # a listed target still makes the act's lesion the same when another target is not established
        R = build({E1: denial(**{**listed, 'targets': (sup(L1), unres(L2))}), E2: act(lesion=sup(L1),
                                                                                    places=(SILENT,))},
                  lesions=lesions)
        self.assertEqual(row_of(R, P.Row.TARGET), SAME)

    def test_a_segment_reads_its_whole_range(self):
        # hand-off 2d#6: scope.segment; its whole range (D196), not only its two ends
        segment = dict(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        whole = WHOLE_CECUM_TO_HEPATIC_FLEXURE
        self.assertEqual(whole, frozenset({Landmark.CECUM, Landmark.APPENDICEAL_ORIFICE, Landmark.ILEOCECAL_VALVE,
                                           Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE}))
        for inside in (Landmark.ASCENDING_COLON, Landmark.CECUM, Landmark.ILEOCECAL_VALVE, Landmark.RIGHT_COLON,
                       Landmark.COLON):
            controls = controls_both_ways(E1, E2, statement_places=whole, act_places=(inside,))
            R = build({E1: denial(**segment), E2: act(lesion=SILENT, places=(sup(inside),))}, controls=controls)
            with self.subTest(inside=inside.value):
                self.assertEqual(row_of(R, P.Row.TARGET), SAME)
        outside = controls_both_ways(E1, E2, statement_places=whole, act_places=(Landmark.SIGMOID_COLON,))
        R = build({E1: denial(**segment), E2: act(lesion=SILENT)}, controls=outside)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        for missing in outside:
            with self.subTest(missing=missing):
                R = build({E1: denial(**segment), E2: act(lesion=SILENT)},
                          controls={key: value for key, value in outside.items() if key != missing})
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
                R = build({E1: denial(**segment), E2: act(lesion=SILENT)}, controls={**outside, missing: False})
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        for name, members in (('an end not established', (sup(Landmark.CECUM), unres(Landmark.HEPATIC_FLEXURE))),
                              ('one place', (sup(Landmark.CECUM),)), ('none', ())):
            R = build({E1: denial(**{**segment, 'segment': members}), E2: act(lesion=SILENT)}, controls=outside)
            with self.subTest(segment=name):
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)

    def test_a_segment_asks_the_act_about_every_place_of_its_whole_range(self):
        # the refutation's F1 (3.2.3 "each place of one object outside the other's places"; 4.11 "an omitted place is
        # as unknown as a missing one"): the segment's interior places are places of the statement, so the act must be
        # asked about each of them - its two ends alone leave a place the act omitted from its list unasked
        segment = dict(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SEGMENT),
                       segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        ends = (Landmark.CECUM, Landmark.HEPATIC_FLEXURE)
        whole = WHOLE_CECUM_TO_HEPATIC_FLEXURE
        outside = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(Landmark.TRANSVERSE_COLON),),
                      device=sup(Device.COLD_FORCEPS))
        # the two ends' controls only (what contract/claims.py asked before DECISIONS D223): held, however they were
        # answered
        ends_only = controls_both_ways(E1, E2, statement_places=ends, act_places=(Landmark.TRANSVERSE_COLON,))
        pair = relation_of(build({E1: denial(**segment), E2: outside}, controls=ends_only))
        self.assertEqual(pair.result(P.Row.TARGET), UNRESOLVED)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertIs(pair.row, P.Row.TARGET)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
        # every place of the whole range asked and rejected: a truly outside act is set apart (45380 READY)
        every = controls_both_ways(E1, E2, statement_places=whole, act_places=(Landmark.TRANSVERSE_COLON,))
        pair = relation_of(build({E1: denial(**segment), E2: outside}, controls=every))
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TARGET)
        # each interior place: unasked, or asked and supported, holds
        for interior in sorted(whole - set(ends), key=lambda place: place.value):
            key = (E2, A.TARGET_PLACES, interior)
            for name, controls in (('not asked', {k: v for k, v in every.items() if k != key}),
                                   ('supported', {**every, key: False})):
                with self.subTest(interior=interior.value, control=name):
                    pair = relation_of(build({E1: denial(**segment), E2: outside}, controls=controls))
                    self.assertEqual(pair.result(P.Row.TARGET), UNRESOLVED)
                    self.assertIsNot(pair.relation, P.Relation.INDEPENDENT)
        # the refutation's input 2: a snare denial from the ascending to the descending colon beside a cold snare done
        # in the transverse and the sigmoid colon, filed [sigmoid]; whole-range controls, pass 2 supporting "This act
        # was done in the transverse colon.": held
        snares = dict(breadth=sup(Breadth.SEGMENT),
                      segment=(sup(Landmark.ASCENDING_COLON), sup(Landmark.DESCENDING_COLON)))
        range_ = P.segment_range(Landmark.ASCENDING_COLON, Landmark.DESCENDING_COLON)
        controls = controls_both_ways(E1, E2, statement_places=range_, act_places=(Landmark.SIGMOID_COLON,))
        controls[(E2, A.TARGET_PLACES, Landmark.TRANSVERSE_COLON)] = False
        pair = relation_of(build({E1: denial(**snares), E2: act(lesion=SILENT)}, controls=controls))
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertIs(pair.row, P.Row.TARGET)

    def test_d220_the_listed_and_segment_arms_read_every_pair_control_between_the_two_objects(self):
        # DECISIONS D220 (the refutation's PMONO, in pairing's own arms; facts.apart_by_controls, repair r2d): "apart"
        # needs every pair control between the two objects rejected, whatever place or lesion it asks about. The
        # refutation's two minimal inputs: before 9.4's deletion the pair is held because the control asking the OTHER
        # object about a member was not rejected; the member deleted (the controls left as they were), it stays held
        rng = P.segment_range(Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON)
        segment = dict(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.DESCENDING_COLON),
                                                              sup(Landmark.SIGMOID_COLON)))
        controls = {(E2, A.TARGET_PLACES, place): True for place in rng}
        controls[(E2, A.TARGET_PLACES, Landmark.RECTOSIGMOID)] = False
        controls[(E1, A.TARGET_PLACES, Landmark.SPLENIC_FLEXURE)] = True
        splenic = act(lesion=SILENT, places=(sup(Landmark.SPLENIC_FLEXURE),))
        listed = dict(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1), sup(L2)))
        listed_controls = {(E2, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True,
                           (E2, A.TARGET_PLACES, Landmark.RECTUM): False,
                           (E1, A.TARGET_PLACES, Landmark.TRANSVERSE_COLON): True}
        transverse = act(lesion=sup(L3), places=(sup(Landmark.TRANSVERSE_COLON),))
        cases = (('segment', denial(**segment, places=(sup(Landmark.RECTOSIGMOID),)), denial(**segment, places=()),
                  splenic, controls, (E2, A.TARGET_PLACES, Landmark.RECTOSIGMOID)),
                 ('listed', denial(**listed, places=(sup(Landmark.SIGMOID_COLON), sup(Landmark.RECTUM))),
                  denial(**listed, places=(sup(Landmark.SIGMOID_COLON),)), transverse, listed_controls,
                  (E2, A.TARGET_PLACES, Landmark.RECTUM)))
        for name, full, short, the_act, the_controls, held_by in cases:
            with self.subTest(arm=name):
                for statement in (full, short):  # before and after the deletion
                    pair = relation_of(build({E1: statement, E2: the_act}, controls=the_controls))
                    self.assertEqual(pair.result(P.Row.TARGET), UNRESOLVED)
                    self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                    self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
                # that control rejected too, both are set apart: the hold was that control's alone
                for statement in (full, short):
                    pair = relation_of(build({E1: statement, E2: the_act}, controls={**the_controls, held_by: True}))
                    self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        # whatever place it asks: an unrejected control asked of either object about a place of neither list (another
        # object's) holds the pair; one asked of a third object never reaches it
        whole = WHOLE_CECUM_TO_HEPATIC_FLEXURE
        segment = dict(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        outside = controls_both_ways(E1, E2, statement_places=whole, act_places=(Landmark.SIGMOID_COLON,))
        events = {E1: denial(**segment), E2: act(lesion=SILENT), E3: act(lesion=SILENT, places=(sup(Landmark.RECTUM),))}
        self.assertIs(relation_of(build(events, controls=outside)).relation, P.Relation.INDEPENDENT)
        for asked, expected in ((E1, P.Relation.UNRESOLVED), (E2, P.Relation.UNRESOLVED),
                                (E3, P.Relation.INDEPENDENT)):
            controls = {**outside, (asked, A.TARGET_PLACES, Landmark.RECTUM): False}
            with self.subTest(asked=asked, about='rectum'):
                self.assertIs(relation_of(build(events, controls=controls)).relation, expected)
        # the lesion arm (listed targets): a lesion control about a third lesion, asked of either object
        lesions = {L1: lesion_of(distinct=(L3,)), L2: lesion_of(distinct=(L3,)), L3: lesion_of(), L4: lesion_of()}
        listed_events = {E1: denial(**listed), E2: act(lesion=sup(L3), places=(SILENT,)), E3: act(lesion=sup(L4))}
        both = controls_both_ways(E1, E2, statement_lesions=(L1, L2), act_lesions=(L3,))
        self.assertIs(relation_of(build(listed_events, lesions=lesions, controls=both)).relation,
                      P.Relation.INDEPENDENT)
        for asked, expected in ((E1, P.Relation.UNRESOLVED), (E2, P.Relation.UNRESOLVED),
                                (E3, P.Relation.INDEPENDENT)):
            controls = {**both, (asked, A.TARGET_LESION, L4): False}
            with self.subTest(asked=asked, about='lesion L4'):
                self.assertIs(relation_of(build(listed_events, lesions=lesions, controls=controls)).relation, expected)
            controls = {**both, (asked, A.TARGET_LESION, L4): True}
            with self.subTest(asked=asked, about='lesion L4 rejected'):
                self.assertIs(relation_of(build(listed_events, lesions=lesions, controls=controls)).relation,
                              P.Relation.INDEPENDENT)

    def test_a_short_list_beside_a_segment_never_releases_under_either_generation(self):
        # SC-B's short list (P-MONO's list-member deletion, pair controls left as they were) over a grid of segments
        # and act lists, a faithful pass 2 answering each control by the act's true places: deleting a member of a list
        # that reaches into the range never sets the pair apart, whether the controls are asked of the segment's two
        # ends (contract/claims.py before DECISIONS D223) or of its whole range (round 2's request R4, which r2c built
        # for D223); and under the whole range a list truly outside the range is set apart (the reading does not hold
        # every segment forever)
        segments = ((Landmark.CECUM, Landmark.HEPATIC_FLEXURE), (Landmark.ASCENDING_COLON, Landmark.DESCENDING_COLON),
                    (Landmark.SIGMOID_COLON, Landmark.RECTUM))
        universe = (Landmark.CECUM, Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE, Landmark.TRANSVERSE_COLON,
                    Landmark.SPLENIC_FLEXURE, Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON, Landmark.RECTUM)
        checked = released_truly_outside = 0
        for first, last in segments:
            range_ = P.segment_range(first, last)
            statement = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SEGMENT), segment=(sup(first), sup(last)))
            for generation, asked in (('ends', (first, last)), ('whole range (R4)', tuple(range_))):
                for one in universe:
                    for two in universe:
                        if one is two:
                            continue
                        truth = {one, two}
                        controls = claims_pair_controls(E1, asked, E2, (one, two),
                                                        lambda subject, place: place not in (
                                                            range_ if subject == E1 else truth))
                        full = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(one), sup(two)),
                                   device=sup(Device.COLD_FORCEPS))
                        inside = any(not anatomy.disjoint(place, mine) for place in truth for mine in range_)
                        found = relation_of(build({E1: statement, E2: full}, controls=controls)).relation
                        if not inside and generation != 'ends':
                            self.assertIs(found, P.Relation.INDEPENDENT, (first, last, one, two))
                            released_truly_outside += 1
                        for kept in (one, two):
                            short = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(kept),),
                                        device=sup(Device.COLD_FORCEPS))
                            relation = relation_of(build({E1: statement, E2: short}, controls=controls)).relation
                            with self.subTest(segment=(first.value, last.value), generation=generation,
                                              truth=(one.value, two.value), kept=kept.value):
                                if inside:
                                    self.assertIsNot(relation, P.Relation.INDEPENDENT)
                            checked += 1
        self.assertGreater(released_truly_outside, 0)
        self.assertEqual(checked, 3 * 2 * 8 * 7 * 2)

    def test_d238_an_act_filed_possible_statement_reads_the_pair_controls_that_exist(self):
        # DECISIONS D228 (DQ1; 4.5's HO-3 paragraph) as D238 rules it (refute-r3d-r1 D1; round 1's question Q1 option
        # (ii)): an act-filed possible statement's own place and lesion facts stand for a single target, set apart when
        # both targets are established and differ, reading the pair controls THAT EXIST - an unrejected one holds, a
        # missing one is not required (DQ1's outcome, with no control under D211, is kept) - whatever its status is short
        # of established
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        (asks_act, asks_statement) = sorted(both, key=lambda key: key[0] != E2)  # (E2, rectum), (E1, sigmoid colon)
        self.assertEqual((asks_act[0], asks_statement[0]), (E2, E1))
        control_sets = {
            'none': ({}, INDEPENDENT), 'both rejected': (both, INDEPENDENT),
            'only the act asked, rejected': ({asks_act: True}, INDEPENDENT),
            'only the statement asked, rejected': ({asks_statement: True}, INDEPENDENT),
            'both not rejected': ({key: False for key in both}, UNRESOLVED),
            'only the act asked, not rejected': ({asks_act: False}, UNRESOLVED),
            'only the statement asked, not rejected': ({asks_statement: False}, UNRESOLVED),
            'the act not rejected, the statement rejected': ({asks_act: False, asks_statement: True}, UNRESOLVED),
            'the statement not rejected, the act rejected': ({asks_act: True, asks_statement: False}, UNRESOLVED),
        }
        statuses = (('unresolved', unres(PERFORMED)), ('doubted', doubted(PERFORMED)),
                    ('contradicted', contra(PERFORMED, Status.PLANNED)), ('silent', SILENT))
        checked = 0
        for status_name, status in statuses:
            possible = act(status=status, lesion=SILENT, places=(sup(Landmark.RECTUM),))
            for controls_name, (controls, expected) in control_sets.items():
                pair = relation_of(build({E1: possible, E2: act(lesion=SILENT)}, controls=controls))
                with self.subTest(status=status_name, controls=controls_name):
                    self.assertTrue(pair.possible)
                    self.assertFalse(P.filed_as_statement(build({E1: possible}), E1))
                    self.assertEqual(pair.result(P.Row.TARGET), expected)
                    if expected is INDEPENDENT:
                        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
                        self.assertIs(pair.row, P.Row.TARGET)
                        self.assertIsNone(P.item(pair))
                    else:  # held, asking whether the statement refers to the act (4.5 step 2's last sentence)
                        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                        self.assertIs(pair.row, P.Row.TARGET)
                        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
                        self.assertEqual(P.cause(pair), 'relation:possible_statement')
                checked += 1
        self.assertEqual(checked, 4 * 9)
        # by lesion: both supported, different, distinct_from supported - no lesion control required; the two between
        # the pair (the statement asked about the act's lesion, the act about the statement's: DECISIONS D235) read when
        # they exist, an unrejected one holding
        lesions = {L1: lesion_of(), L2: lesion_of(distinct=(L1,))}
        possible = act(status=unres(PERFORMED), lesion=sup(L2), places=())
        between = ((E1, A.TARGET_LESION, L1), (E2, A.TARGET_LESION, L2))
        for controls_name, controls, expected in (
                ('none', {}, INDEPENDENT), ('both rejected', dict.fromkeys(between, True), INDEPENDENT),
                ('one rejected, one missing', {between[0]: True}, INDEPENDENT),
                ('both not rejected', dict.fromkeys(between, False), UNRESOLVED),
                ('the statement asked, not rejected', {between[0]: False, between[1]: True}, UNRESOLVED),
                ('the act asked, not rejected', {between[1]: False}, UNRESOLVED)):
            R = build({E1: possible, E2: act(places=())}, lesions=lesions, controls=controls)
            with self.subTest(lesion=True, controls=controls_name):
                self.assertEqual(row_of(R, P.Row.TARGET), expected)
        # the lesions possibly one (no distinct_from; a same_as that may join them): never set apart by lesion
        for name, the_lesions in (('no distinct_from', {L1: lesion_of(), L2: lesion_of()}),
                                  ('same_as unresolved', {L1: lesion_of(),
                                                          L2: {**lesion_of(distinct=(L1,)), A.SAME_AS: (unres(L1),)}}),
                                  ('same_as supported', {L1: lesion_of(), L2: lesion_of(distinct=(L1,), same=(L1,))})):
            R = build({E1: possible, E2: act(places=())}, lesions=the_lesions)
            with self.subTest(lesion=name):
                self.assertNotEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        # places overlapping (SAME) or neither overlapping nor disjoint (an anastomosis): never set apart
        for own, other, expected in (((Landmark.RECTUM,), (Landmark.RECTUM, Landmark.SIGMOID_COLON), SAME),
                                     ((Landmark.SIGMOID_COLON,), (Landmark.COLON,), SAME),
                                     ((Landmark.RECTUM,), (Landmark.ANASTOMOSIS,), UNRESOLVED)):
            R = build({E1: act(status=unres(PERFORMED), lesion=SILENT, places=tuple(sup(place) for place in own)),
                       E2: act(lesion=SILENT, places=tuple(sup(place) for place in other))})
            with self.subTest(statement=own, act=other):
                self.assertEqual(row_of(R, P.Row.TARGET), expected)

    def test_d238_the_controls_read_are_every_place_control_of_either_object_and_the_two_lesion_controls_between(self):
        # which existing controls D228's arm reads (D238 with D220, D235 and D236): every PLACE pair control asked of
        # either object, whatever place it asks about (facts.apart_by_controls' scan, kept by D236 for the place lists:
        # an unrejected control another pair made holds, the class D236 names), never one asked of a third object; and
        # of the LESION controls, only the two between the pair as their target lesions name them (D235), so one about a
        # lesion only a third object names, asked of either object, never holds - the arm's other reading of it (D239's
        # composition, R3D-LC) reads only the lesions the two claims may name
        events = {E1: act(status=doubted(PERFORMED), lesion=SILENT, places=(sup(Landmark.RECTUM),)),
                  E2: act(lesion=SILENT), E3: act(lesion=SILENT, places=(sup(Landmark.TRANSVERSE_COLON),))}
        self.assertIs(relation_of(build(events)).relation, P.Relation.INDEPENDENT)
        for asked, about, expected in ((E1, Landmark.TRANSVERSE_COLON, P.Relation.UNRESOLVED),
                                       (E2, Landmark.TRANSVERSE_COLON, P.Relation.UNRESOLVED),
                                       (E1, Landmark.CECUM, P.Relation.UNRESOLVED),
                                       (E3, Landmark.RECTUM, P.Relation.INDEPENDENT),
                                       (E3, Landmark.SIGMOID_COLON, P.Relation.INDEPENDENT)):
            for rejected in (False, True):
                controls = {(asked, A.TARGET_PLACES, about): rejected}
                with self.subTest(asked=asked, about=about.value, rejected=rejected):
                    found = relation_of(build(events, controls=controls)).relation
                    self.assertIs(found, P.Relation.INDEPENDENT if rejected else expected)
        lesions = {L1: lesion_of(), L2: lesion_of(distinct=(L1,)), L3: lesion_of()}
        events = {E1: act(status=doubted(PERFORMED), lesion=sup(L2), places=()), E2: act(places=()),
                  E3: act(lesion=sup(L3), places=())}
        self.assertIs(relation_of(build(events, lesions=lesions)).relation, P.Relation.INDEPENDENT)
        for asked in (E1, E2):
            for rejected in (False, True):
                controls = {(asked, A.TARGET_LESION, L3): rejected}
                with self.subTest(asked=asked, about='lesion L3', rejected=rejected):
                    self.assertIs(relation_of(build(events, lesions=lesions, controls=controls)).relation,
                                  P.Relation.INDEPENDENT)

    def test_d239_a_lesion_that_may_be_the_acts_own_is_never_set_apart_by_place(self):
        # DECISIONS D239 (refute-r3d-r1 D2): in D228's arm a supported equal lesion, or a lesion possibly equal
        # (_possibly_same, or a lesion claim not established whose value or options name the act's lesion), is never set
        # apart by place - here beside places established and disjoint whose pair controls are all rejected (or none
        # exists), so only the lesion can hold the pair. Built fail-closed, on either side (a claim of the ACT's not
        # established naming the statement's lesion too: weakening either claim must never release, 9.4) and, read with
        # D238, a lesion pair control between the two present and not rejected (question R3D-LC)
        places = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        distinct = {L1: lesion_of(), L2: lesion_of(distinct=(L1,)), L4: lesion_of()}

        def same_as(where, join):
            return {**distinct, where: {**distinct[where], A.SAME_AS: (join,)}}

        held = (
            ('a supported equal lesion', sup(L1), sup(L1), distinct, {}),
            ('the statement unresolved naming it', unres(L1), sup(L1), distinct, {}),
            ('the statement doubted naming it', doubted(L1), sup(L1), distinct, {}),
            ('the statement doubted, a reading names it', doubted(L2, L1), sup(L1), distinct, {}),
            ('the statement contradicted, a side names it', contra(L2, L1), sup(L1), distinct, {}),
            ('the act unresolved naming it', sup(L1), unres(L1), distinct, {}),
            ('the act doubted, a reading names it', sup(L1), doubted(L4, L1), distinct, {}),
            ('both unresolved naming one lesion', unres(L1), unres(L1), distinct, {}),
            ('same_as supported in the statement lesion', sup(L2), sup(L1), same_as(L2, sup(L1)), {}),
            ('same_as unresolved in the statement lesion', sup(L2), sup(L1), same_as(L2, unres(L1)), {}),
            ('same_as doubted, a reading names it', sup(L2), sup(L1), same_as(L2, doubted(L4, L1)), {}),
            ('same_as contradicted in the act lesion', sup(L2), sup(L1), same_as(L1, contra(L2, L4)), {}),
            ('a not-established claim whose lesion same_as may join', unres(L4), sup(L1), same_as(L4, unres(L1)), {}),
            ('R3D-LC: the statement asked about the act lesion, not rejected', sup(L2), sup(L1), distinct,
             {(E1, A.TARGET_LESION, L1): False}),
            ('R3D-LC: the act asked about the statement lesion, not rejected', sup(L2), sup(L1), distinct,
             {(E2, A.TARGET_LESION, L2): False}),
        )
        apart = (
            ('different supported lesions, distinct_from supported', sup(L2), sup(L1), distinct, {}),
            ('different supported lesions, no distinct_from (not possibly equal: D239)', sup(L2), sup(L1),
             {L1: lesion_of(), L2: lesion_of()}, {}),
            ('a negated same_as', sup(L2), sup(L1), same_as(L2, neg(L1)), {}),
            ('the statement unresolved naming another lesion', unres(L4), sup(L1), distinct, {}),
            ('the statement silent', SILENT, sup(L1), distinct, {}),
            ('the act silent', sup(L1), SILENT, distinct, {}),
            ('the statement negated the act lesion', neg(L1), sup(L1), distinct, {}),
            ('a lesion control between them rejected', sup(L2), sup(L1), distinct,
             {(E1, A.TARGET_LESION, L1): True, (E2, A.TARGET_LESION, L2): True}),
        )
        checked = 0
        for expected, cases in ((False, held), (True, apart)):
            for name, mine, theirs, the_lesions, lesion_controls in cases:
                for place_name, place_controls in (('no place control', {}), ('place controls rejected', places)):
                    R = build({E1: act(status=doubted(PERFORMED), lesion=mine, places=(sup(Landmark.RECTUM),)),
                               E2: act(lesion=theirs)}, lesions=the_lesions,
                              controls={**place_controls, **lesion_controls})
                    pair = relation_of(R)
                    with self.subTest(case=name, controls=place_name):
                        self.assertTrue(pair.possible)
                        if expected:
                            self.assertIs(pair.relation, P.Relation.INDEPENDENT)
                            self.assertIs(pair.row, P.Row.TARGET)
                        else:
                            self.assertNotEqual(pair.result(P.Row.TARGET), INDEPENDENT)
                            self.assertIsNot(pair.relation, P.Relation.INDEPENDENT)
                            if Res.SUPPORTED is mine.result is theirs.result and mine.value == theirs.value:
                                self.assertIs(pair.relation, P.Relation.DOUBT)  # the same lesion established: SAME
                    checked += 1
        self.assertEqual(checked, 2 * (len(held) + len(apart)))
        # D239 is D228's arm only: an act of another performer (the controlled single arm) whose lesion is the act's,
        # in a disjoint place, every place control rejected, is set apart by place as before; a statement-filed single
        # target too
        for name, statement in (('another performer', act(performer=sup(OTHER_CLINICIAN, inherited_from=N1),
                                                          places=(sup(Landmark.RECTUM),))),
                                ('statement-filed single target', denial(breadth=sup(Breadth.SINGLE_TARGET),
                                                                         lesion=sup(L1),
                                                                         places=(sup(Landmark.RECTUM),)))):
            R = build({E1: statement, E2: act()}, lesions=distinct, controls=places)
            with self.subTest(arm=name):
                self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)

    def test_d228_a_target_not_established_on_either_side_still_sets_nothing_apart(self):
        # "when both targets are established": a denial misfiled as an act gets its act-phrased place claims rejected
        # too, so nothing sets it apart (4.5's HO-3 paragraph); every state short of established, on either side, for
        # places and for lesions, the pair controls all rejected
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,),
                                  statement_lesions=(L2,), act_lesions=(L1,))
        lesions = {L1: lesion_of(), L2: lesion_of(distinct=(L1,))}
        checked = 0
        for name in NOT_ESTABLISHED:
            for side in ('statement', 'act'):
                place = in_state(name, Landmark.RECTUM if side == 'statement' else Landmark.SIGMOID_COLON,
                                 Landmark.CECUM)
                lesion = in_state(name, L2 if side == 'statement' else L1, L3)
                d = act(status=unres(PERFORMED), places=(place,) if side == 'statement' else (sup(Landmark.RECTUM),),
                        lesion=lesion if side == 'statement' else sup(L2))
                a = act(places=(place,) if side == 'act' else (sup(Landmark.SIGMOID_COLON),),
                        lesion=lesion if side == 'act' else sup(L1))
                R = build({E1: d, E2: a}, lesions=lesions, controls=both)
                with self.subTest(state=name, side=side):
                    self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
                    self.assertIsNot(relation_of(R).relation, P.Relation.INDEPENDENT)
                checked += 1
        self.assertEqual(checked, 8)
        # an empty place list is no member: unknown, never an absence (P3)
        R = build({E1: act(status=unres(PERFORMED), lesion=SILENT, places=()), E2: act(lesion=SILENT)})
        self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)

    def test_d228_reaches_act_filed_possible_statements_only(self):
        # D228 names an act-filed POSSIBLE statement. A statement-filed possible statement (its status claim negated,
        # not established) keeps its breadth's reading, and an act established as of another date or performer (its
        # status established) keeps the pair controls of 4.2 (D220), as before the ruling (round 1's question Q3)
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        for name, statement in (
                ('statement-filed, possible', denial(status=unres(PERFORMED, state=State.NEGATED),
                                                     breadth=sup(Breadth.SINGLE_TARGET),
                                                     places=(sup(Landmark.RECTUM),))),
                ('another performer', act(performer=sup(OTHER_CLINICIAN, inherited_from=N1), lesion=SILENT,
                                          places=(sup(Landmark.RECTUM),))),
                ('another date', act(date=sup(EARLIER), lesion=SILENT, places=(sup(Landmark.RECTUM),)))):
            for controls_name, controls, expected in (
                    ('both rejected', both, INDEPENDENT), ('none', {}, UNRESOLVED),
                    ('one not rejected', {**both, (E2, A.TARGET_PLACES, Landmark.RECTUM): False}, UNRESOLVED),
                    ('one missing', {(E1, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True}, UNRESOLVED)):
                R = build({E1: statement, E2: act(lesion=SILENT)}, controls=controls)
                with self.subTest(statement=name, controls=controls_name):
                    self.assertTrue(P.is_statement(R, E1))
                    self.assertEqual(row_of(R, P.Row.TARGET), expected)

    def test_t1_a_place_list_with_a_member_not_established_never_sets_anything_apart(self):
        # the refutation's T1 (mutant X5): a list is established only when EVERY member is (facts' _supported). Here
        # each list has one supported member and one member in another state, and every pair control - the one about
        # the member that is not established included - is generated (claims.pair()'s rule) and rejected, so only the
        # list's own condition can hold the pair; the same lists with that member supported are set apart
        segment = dict(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        whole = tuple(contract_claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE))
        statements = {
            'listed': (dict(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1),)), ()),
            'segment': (segment, whole),
            'act-filed possible (D228)': (None, ()),
        }
        checked = 0
        for mode, (over, extra) in statements.items():
            for side in ('statement', 'act'):
                for name in ('supported',) + NOT_ESTABLISHED[:-1] + ('negated',):
                    second = in_state(name, Landmark.DESCENDING_COLON, Landmark.CECUM)
                    own = (sup(Landmark.RECTUM), second) if side == 'statement' else (sup(Landmark.RECTUM),)
                    theirs = (sup(Landmark.SIGMOID_COLON), second) if side == 'act' else (sup(Landmark.SIGMOID_COLON),)
                    if over is None:
                        statement = act(kind=sup(Kind.BIOPSY), status=unres(PERFORMED), lesion=SILENT, device=SILENT,
                                        places=own)
                    else:
                        statement = denial(kind=sup(Kind.BIOPSY), places=own, **over)
                    controls = claims_pair_controls(E1, claimable(own) + extra, E2, claimable(theirs),
                                                    lambda subject, place: True)
                    R = build({E1: statement, E2: act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=theirs,
                                                      device=sup(Device.COLD_FORCEPS))}, controls=controls)
                    found = row_of(R, P.Row.TARGET)
                    with self.subTest(mode=mode, side=side, member=name):
                        if name in ('supported', 'negated'):
                            self.assertEqual(found, INDEPENDENT)  # the list established: apart (not vacuous)
                        else:
                            self.assertEqual(found, UNRESOLVED)
                            self.assertIsNot(relation_of(R).relation, P.Relation.INDEPENDENT)
                    checked += 1
        self.assertEqual(checked, 3 * 2 * 5)

    def test_a_statement_filed_breadth_not_established_is_set_apart_by_nothing(self):
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        for breadth in (unres(Breadth.SINGLE_TARGET), SILENT, doubted(Breadth.SINGLE_TARGET)):
            R = build({E1: denial(breadth=breadth, places=(sup(Landmark.RECTUM),)), E2: act(lesion=SILENT)},
                      controls=both)
            with self.subTest(breadth=breadth):
                self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        R = build({E1: denial(breadth=SILENT, places=(sup(Landmark.SIGMOID_COLON),)), E2: act(lesion=SILENT)})
        self.assertEqual(row_of(R, P.Row.TARGET), SAME)

    def test_an_act_whose_kind_has_no_target_is_read_for_no_target_fact(self):
        # step 1f's hand-off (requirements.py's _TARGET_KINDS comment; D195): the row answers as for an unknown target
        # and reads none of that act's target facts
        for kind in (Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION):
            reads = []
            original_fact, original_members = F.fact, F.members

            def record_fact(R, subject, attribute):
                reads.append((subject, attribute))
                return original_fact(R, subject, attribute)

            def record_members(R, subject, attribute):
                reads.append((subject, attribute))
                return original_members(R, subject, attribute)

            R = build({E1: self.single(kind=sup(kind), places=(sup(Landmark.RECTUM),)),
                       E2: act(kind=sup(kind), places=(sup(Landmark.RECTUM),))})
            with mock.patch.object(F, 'fact', record_fact), mock.patch.object(F, 'members', record_members):
                found = row_of(R, P.Row.TARGET)
            with self.subTest(kind=kind.value):
                self.assertEqual(found, UNRESOLVED)
                self.assertIn((E2, A.KIND), reads)
                self.assertFalse({(E2, A.TARGET_LESION), (E2, A.TARGET_PLACES)} & set(reads), reads)


class TechniqueRowTests(SimpleTestCase):
    """C-16: SAME when D names no device; UNRESOLVED unless both are established; then INDEPENDENT on devices apart, SAME
    when A's device is among D's, UNRESOLVED otherwise (v1's DEVICE_CONTAINS: a snare covers its cold and hot kinds)."""

    def test_a_statement_naming_no_device_is_same_at_every_act_state(self):
        for name in STATES:
            R = build({E1: denial(device=SILENT), E2: act(device=in_state(name, Device.HOT_SNARE, Device.SNARE))})
            with self.subTest(act=name):
                self.assertEqual(row_of(R, P.Row.TECHNIQUE), SAME)

    def test_v1s_device_arms(self):
        cases = (
            (sup(Device.COLD_SNARE), sup(Device.COLD_SNARE), SAME), (sup(Device.COLD_SNARE), sup(Device.HOT_SNARE),
                                                                     INDEPENDENT),
            (sup(Device.SNARE), sup(Device.COLD_SNARE), SAME), (sup(Device.SNARE), sup(Device.HOT_SNARE), SAME),
            (sup(Device.COLD_SNARE), sup(Device.SNARE), UNRESOLVED),  # a snare where D denies the cold snare
            (sup(Device.FORCEPS), sup(Device.HOT_FORCEPS), SAME), (sup(Device.HOT_FORCEPS), sup(Device.FORCEPS),
                                                                   UNRESOLVED),
            (sup(Device.OTHER), sup(Device.OTHER), UNRESOLVED),  # two "other" devices are never one
            (sup(Device.OTHER), sup(Device.COLD_SNARE), INDEPENDENT), (sup(Device.BALLOON), sup(Device.WIRE_BOUGIE),
                                                                       INDEPENDENT),
            (sup(Device.BOUGIE), sup(Device.WIRE_BOUGIE), INDEPENDENT),
            (sup(Device.COLD_SNARE), neg(Device.COLD_SNARE), INDEPENDENT),  # the act states it was not used
            (sup(Device.COLD_SNARE), neg(Device.SNARE), INDEPENDENT), (sup(Device.SNARE), neg(Device.COLD_SNARE),
                                                                       UNRESOLVED))
        for own, other, expected in cases:
            R = build({E1: denial(device=own), E2: act(device=other)})
            with self.subTest(statement=own, act=other):
                self.assertEqual(row_of(R, P.Row.TECHNIQUE), expected)

    def test_either_device_not_established(self):
        for name in NOT_ESTABLISHED:
            for side in ('statement', 'act'):
                found = in_state(name, Device.HOT_SNARE, Device.COLD_SNARE)
                if side == 'statement' and name == 'silent':
                    continue  # a silent statement device names no device: SAME (above)
                R = build({E1: denial(device=found if side == 'statement' else sup(Device.HOT_SNARE)),
                           E2: act(device=found if side == 'act' else sup(Device.COLD_SNARE))})
                with self.subTest(state=name, side=side):
                    self.assertEqual(row_of(R, P.Row.TECHNIQUE), UNRESOLVED)


# --- the relation (4.5) ------------------------------------------------------------------------------------------------


def proving(which: P.Row):
    """A FactSet in which ``which`` alone proves E1 does not concern E2 and every other row is UNRESOLVED."""
    sessions = TWO_SESSIONS
    if which is P.Row.SESSION:
        return build({E1: all_unresolved(session=sup(X2)), E2: act(lesion=SILENT)}, sessions=sessions)
    if which is P.Row.TIMING:
        return build({E1: all_unresolved(date=sup(EARLIER)), E2: act(lesion=SILENT)}, sessions=sessions)
    if which is P.Row.PERFORMER:
        return build({E1: all_unresolved(performer=sup(OTHER_CLINICIAN)), E2: act(lesion=SILENT)}, sessions=sessions)
    if which is P.Row.BREADTH:
        return build({E1: all_unresolved(kind=sup(Kind.INJECTION), breadth=sup(Breadth.EXCEPTIVE),
                                         excepts=(sup(E2),)),
                      E2: act(kind=sup(Kind.INJECTION), lesion=SILENT)}, sessions=sessions)
    if which is P.Row.TARGET:
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        return build({E1: all_unresolved(breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),)),
                      E2: act(lesion=SILENT)}, sessions=sessions, controls=both)
    return build({E1: all_unresolved(device=sup(Device.HOT_SNARE)), E2: act(lesion=SILENT)}, sessions=sessions)


class RelationTests(SimpleTestCase):
    def test_any_one_row_proving_independence_sets_the_pair_apart_whatever_else_is_unknown(self):
        for which in P.Row:
            R = proving(which)
            pair = relation_of(R)
            with self.subTest(row=which.value):
                self.assertEqual(pair.result(which), INDEPENDENT)
                others = [found for other, found in pair.rows if other is not which]
                self.assertNotIn(INDEPENDENT, others)
                self.assertIn(UNRESOLVED, others)
                self.assertIs(pair.relation, P.Relation.INDEPENDENT)
                self.assertIs(pair.row, which)
                self.assertIsNone(P.item(pair))
                self.assertIsNone(P.cause(pair))

    def test_claimed_turns_apart_into_unresolved(self):
        for which in P.Row:
            for covers in ((sup(E2),), (unres(E2),), (doubted(E3, E2),)):
                R = proving(which)
                events = dict(R.events)
                events[E1] = {**events[E1], A.SCOPE_COVERS: covers}
                R = build(events, sessions=R.sessions, controls=R.pair_controls)
                pair = relation_of(R)
                with self.subTest(row=which.value, covers=covers):
                    self.assertTrue(pair.claimed)
                    self.assertEqual(pair.result(which), INDEPENDENT)
                    self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                    self.assertIsNone(pair.row)
                    self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))

    def test_a_claimed_pair_no_row_sets_apart_asks_its_first_unresolved_rows_fact(self):
        # 4.5 step 1 turns only a claimed pair a row sets apart into UNRESOLVED(statement_scope); a claimed pair with no
        # INDEPENDENT row is step 2's UNRESOLVED(the first unresolved row) and asks that row's fact, as the same pair
        # unclaimed does (the refutation's F2: it asked statement_scope, rank 3, where 4.5 asks event_time, rank 6)
        items = {P.Row.SESSION: rq.Item(rq.Rank.PROCEDURE, rq.FactKey.PROCEDURE),
                 P.Row.TIMING: rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME),
                 P.Row.PERFORMER: rq.Item(rq.Rank.PERFORMER, rq.FactKey.EVENT_PERFORMER),
                 P.Row.BREADTH: rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE),
                 P.Row.TARGET: rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE),
                 P.Row.TECHNIQUE: rq.Item(rq.Rank.TECHNIQUE, rq.FactKey.TECHNIQUE)}
        cases = ((dict(date=unres(ON)), P.Row.TIMING), (dict(session=unres(X1)), P.Row.SESSION),
                 (dict(performer=unres(TEAM)), P.Row.PERFORMER), (dict(device=unres(Device.HOT_SNARE)),
                                                                  P.Row.TECHNIQUE),
                 (dict(breadth=unres(Breadth.ALL_OF_KIND)), P.Row.BREADTH),
                 (dict(breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),)), P.Row.TARGET))
        for over, first in cases:
            for covers in ((sup(E2),), (unres(E2),), (doubted(E3, E2),)):
                claimed = relation_of(build({E1: denial(**over, covers=covers), E2: act()}, sessions=TWO_SESSIONS))
                unclaimed = relation_of(build({E1: denial(**over), E2: act()}, sessions=TWO_SESSIONS))
                with self.subTest(first=first.value, covers=covers):
                    self.assertTrue(claimed.claimed)
                    self.assertNotIn(INDEPENDENT, dict(claimed.rows).values())
                    self.assertIs(claimed.relation, P.Relation.UNRESOLVED)
                    self.assertIs(claimed.row, first)
                    self.assertEqual(P.item(claimed), items[first])
                    self.assertEqual(P.item(claimed), P.item(unclaimed))
                    self.assertEqual(P.cause(claimed), 'relation:unresolved')
        # a claimed possible statement still asks statement_scope (step 2's last sentence)
        possible = act(status=unres(PERFORMED), date=unres(ON), lesion=SILENT, places=(unres(Landmark.RECTUM),))
        pair = relation_of(build({E1: {**possible, A.SCOPE_COVERS: (sup(E2),)}, E2: act()}))
        self.assertTrue(pair.claimed and pair.possible)
        self.assertIs(pair.row, P.Row.TIMING)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))

    def test_covers_naming_another_act_is_not_claimed_and_claimed_leaves_other_relations_alone(self):
        R = proving(P.Row.TIMING)
        events = dict(R.events)
        events[E1] = {**events[E1], A.SCOPE_COVERS: (sup(E3),)}
        pair = relation_of(build(events, sessions=R.sessions))
        self.assertFalse(pair.claimed)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        R = build({E1: denial(covers=(sup(E2),)), E2: act()})
        pair = relation_of(R)
        self.assertTrue(pair.claimed)
        self.assertIs(pair.relation, P.Relation.CONTRADICTION)

    def test_unresolved_names_the_first_unresolved_row_in_45s_order(self):
        cases = ((dict(device=unres(Device.HOT_SNARE), date=unres(ON)), P.Row.TIMING),
                 (dict(device=unres(Device.HOT_SNARE)), P.Row.TECHNIQUE),
                 (dict(breadth=unres(Breadth.ALL_OF_KIND), performer=unres(TEAM)), P.Row.PERFORMER),
                 (dict(breadth=unres(Breadth.ALL_OF_KIND)), P.Row.BREADTH),
                 (dict(breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),)), P.Row.TARGET),
                 (dict(session=unres(X1)), P.Row.SESSION))
        items = {P.Row.SESSION: rq.FactKey.PROCEDURE, P.Row.TIMING: rq.FactKey.EVENT_TIME,
                 P.Row.PERFORMER: rq.FactKey.EVENT_PERFORMER, P.Row.BREADTH: rq.FactKey.STATEMENT_SCOPE,
                 P.Row.TARGET: rq.FactKey.STATEMENT_SCOPE, P.Row.TECHNIQUE: rq.FactKey.TECHNIQUE}
        for over, first in cases:
            R = build({E1: denial(**over), E2: act()}, sessions=TWO_SESSIONS)
            pair = relation_of(R)
            with self.subTest(first=first.value):
                self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                self.assertIs(pair.row, first)
                self.assertEqual(P.item(pair).fact, items[first])
                self.assertEqual(P.cause(pair), 'relation:unresolved')

    def test_every_row_same_gives_contradiction_or_doubt(self):
        R = build({E1: denial(), E2: act()})
        pair = relation_of(R)
        self.assertIs(pair.relation, P.Relation.CONTRADICTION)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.CONFLICT, rq.FactKey.CONFLICT))
        self.assertEqual(rq.fact_key(P.item(pair).fact, next(iter(pair.kinds))), 'conflict:snare')
        self.assertEqual(P.cause(pair), 'relation:contradiction')
        self.assertEqual(pair.spans, (Span(100, 140), Span(200, 240)))  # both statements quoted
        for name, d_status, a_status in (
                ('the statement possible', unres(PERFORMED, state=State.NEGATED), sup(PERFORMED)),
                ('the statement doubted', doubted(PERFORMED, PERFORMED, state=State.NEGATED), sup(PERFORMED)),
                ('the act not established', neg(PERFORMED), unres(PERFORMED)),
                ('the act doubted', neg(PERFORMED), doubted(PERFORMED))):
            R = build({E1: denial(status=d_status), E2: act(status=a_status)})
            pair = relation_of(R)
            with self.subTest(case=name):
                self.assertIs(pair.relation, P.Relation.DOUBT)
                self.assertEqual(P.item(pair), rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS))

    def test_a_possible_statements_unresolved_relation_asks_statement_scope(self):
        R = build({E1: act(status=unres(PERFORMED), date=unres(ON), lesion=SILENT, places=(unres(Landmark.RECTUM),)),
                   E2: act()})
        pair = relation_of(R)
        self.assertTrue(pair.possible)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertIs(pair.row, P.Row.TIMING)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
        self.assertEqual(P.cause(pair), 'relation:possible_statement')

    def test_every_item_is_one_the_clean_requirement_asks(self):
        # requirements.RULES' SUP.8 row (step 1f) names what 4.5's relations ask; pairing asks nothing else
        asks = set(rq.RULES[rq.Requirement.SUP_CLEAN].asks)
        found = set()
        for relation in P.Relation:
            for which in (None, *P.Row):
                for claimed in (False, True):
                    for possible in (False, True):
                        pair = P.Pair(statement=E1, act=E2, relation=relation, row=which, rows=(), claimed=claimed,
                                      possible=possible, kinds=frozenset(), spans=())
                        if P.item(pair) is not None:
                            found.add(P.item(pair))
        unlisted = P.UnlistedPair(index=0, statement=UnlistedStatement(units=(), what=ct.UnlistedWhat.DENIAL,
                                                                       kind=None, session=None), act=E2, spans=())
        found.add(P.item(unlisted))
        self.assertLessEqual(found, asks)
        self.assertEqual(found, asks)
        self.assertEqual(P.cause(unlisted), 'unlisted')

    def test_rows_are_the_relations_rows(self):
        for which in P.Row:
            R = proving(which)
            self.assertEqual(P.rows(R, E1, E2), relation_of(R).rows)
            self.assertEqual(tuple(row for row, _found in P.rows(R, E1, E2)), tuple(P.Row))

    def test_pairs_of_and_pairs_list_every_pair_in_pass_ones_order(self):
        R = build({E1: denial(), E2: act(), E3: denial(date=sup(EARLIER)), E4: act(kind=sup(Kind.BIOPSY))})
        self.assertEqual([(pair.statement, pair.act) for pair in P.pairs(R)], [(E1, E2), (E3, E2)])
        self.assertEqual([pair.statement for pair in P.pairs_of(R, E2)], [E1, E3])
        self.assertEqual(P.pairs_of(R, E4), ())
        self.assertEqual([pair.relation for pair in P.pairs_of(R, E2)],
                         [P.Relation.CONTRADICTION, P.Relation.INDEPENDENT])


# --- the design's named cases ------------------------------------------------------------------------------------------


class NamedCaseTests(SimpleTestCase):
    def test_ho2_v3_document_the_historical_denial_is_set_apart(self):
        # "At the 2024 colonoscopy the anastomosis was narrowed, but no dilation was performed." beside today's dilation:
        # 45386 READY (FINAL-V2 4.5 [R:HO-2]); set apart by session and timing
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.COLONOSCOPY)}
        history = denial(kind=sup(Kind.DILATION), session=sup(X2), date=sup(EARLIER),
                         places=(sup(Landmark.ANASTOMOSIS),))
        today = act(kind=sup(Kind.DILATION), lesion=SILENT, places=(sup(Landmark.ANASTOMOSIS),),
                    device=sup(Device.BALLOON))
        pair = relation_of(build({E1: history, E2: today}, sessions=sessions))
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertEqual((pair.result(P.Row.SESSION), pair.result(P.Row.TIMING)), (INDEPENDENT, INDEPENDENT))
        # by timing alone, its session unknown among two compatible sessions (the pre-refutation "first row decides"
        # stopped here, UNRESOLVED(session))
        history = denial(kind=sup(Kind.DILATION), session=unres(X2), date=sup(EARLIER),
                         places=(sup(Landmark.ANASTOMOSIS),))
        pair = relation_of(build({E1: history, E2: today}, sessions=sessions))
        self.assertEqual(pair.result(P.Row.SESSION), UNRESOLVED)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TIMING)

    def test_no_prior_colonoscopy_leaves_the_screening_examination_alone(self):
        # a screening report with "No prior colonoscopy.": 45378 READY (its only code) [R:HO-2]
        prior = denial(kind=sup(Kind.EXAMINATION), session=SILENT, date=sup(EARLIER), breadth=sup(Breadth.ALL_OF_KIND))
        exam = act(kind=sup(Kind.EXAMINATION), lesion=SILENT, places=(sup(Landmark.CECUM),), device=SILENT)
        R = build({E1: exam, E2: prior})
        self.assertEqual(P.statements(R), (E2,))
        pair = relation_of(R, E2, E1)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TIMING)
        self.assertEqual([p.relation for p in P.pairs_of(R, E1)], [P.Relation.INDEPENDENT])
        # the same with its breadth and target not established: timing still suffices
        prior = denial(kind=sup(Kind.EXAMINATION), session=unres(X1), date=sup(EARLIER), breadth=unres(
            Breadth.ALL_OF_KIND))
        pair = relation_of(build({E1: exam, E2: prior}), E2, E1)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)

    def test_bf17_the_excepted_injection_is_set_apart_and_another_is_asked(self):
        # "No other injection was given." breadth exceptive, excepts [E1]: E1's code READY (2.2 BF17)
        no_other = denial(kind=sup(Kind.INJECTION), breadth=sup(Breadth.EXCEPTIVE), excepts=(sup(E1),))
        injection = act(kind=sup(Kind.INJECTION), lesion=SILENT, device=sup(Device.NEEDLE))
        R = build({E1: injection, E2: no_other, E3: injection, E4: act(kind=sup(Kind.TATTOO), lesion=SILENT,
                                                                       device=sup(Device.NEEDLE))})
        pair = relation_of(R, E2, E1)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.BREADTH)
        for other in (E3, E4):  # a "no other" against an act it does not except (a tattoo is one act with an injection)
            pair = relation_of(R, E2, other)
            with self.subTest(act=other):
                self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                self.assertIs(pair.row, P.Row.BREADTH)
                self.assertEqual(P.item(pair).fact, rq.FactKey.STATEMENT_SCOPE)

    def test_410_broad_denial_contradicts_a_snare_by_any_performer(self):
        # "No polyp was removed today.": kind removal, negated, all_of_kind, its session and date established, no
        # performer stated: against a positive snare every row is SAME, a CONTRADICTION, held conflict:snare
        broad = denial(kind=sup(Kind.REMOVAL), performer=SILENT)
        for name, performer in (('team', sup(TEAM)), ('another clinician', sup(OTHER_CLINICIAN)),
                                ('another facility', sup(OTHER_FACILITY)), ('team negated', neg(TEAM)),
                                ('unresolved', unres(TEAM)), ('silent', SILENT),
                                ('inherited', sup(OTHER_CLINICIAN, inherited_from=N1))):
            pair = relation_of(build({E1: broad, E2: act(performer=performer)}))
            with self.subTest(performer=name):
                self.assertEqual(pair.result(P.Row.PERFORMER), SAME)
                self.assertIs(pair.relation, P.Relation.CONTRADICTION)
                self.assertEqual(rq.fact_key(P.item(pair).fact, Kind.SNARE), 'conflict:snare')
                self.assertEqual(pair.kinds, frozenset({Kind.SNARE}))
        # the denial's own section performer (inherited) never narrows it either
        inherited = denial(kind=sup(Kind.REMOVAL), performer=sup(OTHER_CLINICIAN, inherited_from=N1))
        self.assertIs(relation_of(build({E1: inherited, E2: act()})).relation, P.Relation.CONTRADICTION)
        # an unknown breadth pairs UNRESOLVED, never INDEPENDENT (4.10)
        pair = relation_of(build({E1: denial(kind=sup(Kind.REMOVAL), breadth=unres(Breadth.EXCEPTIVE)), E2: act()}))
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)

    def test_probe_a_beside_a_genuine_snare_is_held(self):
        # "A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare. Neither biopsy nor snare
        # polypectomy was performed.": the denial filed as a performed snare, caught by pass 2 - its status, session,
        # timing and places not established (act-phrased claims a faithful pass 2 rejects for an act not done)
        misfiled = act(status=unres(PERFORMED), session=unres(X1), date=unres(ON, inherited_from=N1),
                       performer=SILENT, lesion=SILENT, places=(unres(Landmark.SIGMOID_COLON),), device=SILENT)
        genuine = act()
        R = build({E1: genuine, E2: misfiled})
        self.assertEqual(P.statements(R), (E2,))
        pairs = P.pairs_of(R, E1)
        self.assertEqual([pair.statement for pair in pairs], [E2])
        pair = pairs[0]
        self.assertTrue(pair.possible)
        self.assertIsNot(pair.relation, P.Relation.INDEPENDENT)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
        self.assertEqual(P.cause(pair), 'relation:possible_statement')
        # with pass 2 establishing everything but its status, and its place the snare's: a DOUBT, still held
        caught = act(status=unres(PERFORMED), lesion=SILENT, device=SILENT, performer=SILENT)
        pair = relation_of(build({E1: genuine, E2: caught}), E2, E1)
        self.assertIs(pair.relation, P.Relation.DOUBT)

    def test_scb_short_list_beside_a_rectal_denial_is_held(self):
        # biopsies "from the transverse colon and the rectum" filed with the transverse colon only, beside "No biopsies
        # were taken from the rectum.": the pair control "This act was done in the rectum." is supported (3.2.3)
        rectal = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),))
        short = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(Landmark.TRANSVERSE_COLON),),
                    device=sup(Device.COLD_FORCEPS))
        controls = {(E2, A.TARGET_PLACES, Landmark.RECTUM): False, (E1, A.TARGET_PLACES, Landmark.TRANSVERSE_COLON): True}
        pair = relation_of(build({E1: rectal, E2: short}, controls=controls))
        self.assertEqual(pair.result(P.Row.TARGET), UNRESOLVED)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertIs(pair.row, P.Row.TARGET)
        self.assertEqual(P.item(pair).fact, rq.FactKey.STATEMENT_SCOPE)
        # biopsies from the transverse colon only: the rectal control rejected, the pair set apart (45380 READY)
        controls[(E2, A.TARGET_PLACES, Landmark.RECTUM)] = True
        pair = relation_of(build({E1: rectal, E2: short}, controls=controls))
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TARGET)

    def test_scb_short_list_beside_a_segment_denial_is_held(self):
        # SC-B's case in a segment's form (the refutation's F1): biopsies done in the transverse colon and the ascending
        # colon, filed with the transverse colon only, beside a denial of biopsies from the cecum to the hepatic flexure;
        # the pair controls a faithful pass 2 answers by the act's true places
        segment = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SEGMENT),
                         segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        short = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(Landmark.TRANSVERSE_COLON),),
                    device=sup(Device.COLD_FORCEPS))
        truth = {E1: WHOLE_CECUM_TO_HEPATIC_FLEXURE, E2: {Landmark.TRANSVERSE_COLON, Landmark.ASCENDING_COLON}}

        def faithful(subject, place):
            return place not in truth[subject]

        for generation, asked in (('ends', (Landmark.CECUM, Landmark.HEPATIC_FLEXURE)),
                                  ('whole range (R4)', tuple(WHOLE_CECUM_TO_HEPATIC_FLEXURE))):
            controls = claims_pair_controls(E1, asked, E2, (Landmark.TRANSVERSE_COLON,), faithful)
            pair = relation_of(build({E1: segment, E2: short}, controls=controls))
            with self.subTest(generation=generation):
                self.assertEqual(pair.result(P.Row.TARGET), UNRESOLVED)
                self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                self.assertEqual(P.item(pair).fact, rq.FactKey.STATEMENT_SCOPE)
        # biopsies from the transverse colon only: every place of the range rejected, the pair set apart (45380 READY)
        truth[E2] = {Landmark.TRANSVERSE_COLON}
        controls = claims_pair_controls(E1, tuple(WHOLE_CECUM_TO_HEPATIC_FLEXURE), E2, (Landmark.TRANSVERSE_COLON,),
                                        faithful)
        pair = relation_of(build({E1: segment, E2: short}, controls=controls))
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TARGET)

    def test_r4_the_segment_denial_beside_a_sigmoid_biopsy_pairs_independent_with_r2cs_controls(self):
        # 3d's R4 input, DECISIONS D223: "No biopsies were taken from the cecum to the hepatic flexure." beside a biopsy
        # truly and only in the sigmoid colon. r2c's contract/claims.py asks the biopsy about every place of the
        # segment's whole range (claims.segment_range, its places() for a segment) and the denial about the sigmoid
        # colon; a faithful pass 2 rejects each, and the pair is INDEPENDENT (45380 READY)
        whole = contract_claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)
        self.assertEqual(frozenset(whole), WHOLE_CECUM_TO_HEPATIC_FLEXURE)
        denial_ = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SEGMENT),
                         segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        biopsy = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(Landmark.SIGMOID_COLON),),
                     device=sup(Device.COLD_FORCEPS))
        truth = {E1: frozenset(whole), E2: {Landmark.SIGMOID_COLON}}
        controls = claims_pair_controls(E1, whole, E2, (Landmark.SIGMOID_COLON,),
                                        lambda subject, place: place not in truth[subject])
        self.assertEqual(controls, {**{(E2, A.TARGET_PLACES, place): True for place in whole},
                                    (E1, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True})
        R = build({E1: denial_, E2: biopsy}, controls=controls)
        pair = relation_of(R)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TARGET)
        self.assertEqual([found.relation for found in P.pairs_of(R, E2)], [P.Relation.INDEPENDENT])
        # the controls claims.py asked before D223 (the two ends): held, as the refutation found
        ends = claims_pair_controls(E1, (Landmark.CECUM, Landmark.HEPATIC_FLEXURE), E2, (Landmark.SIGMOID_COLON,),
                                    lambda subject, place: True)
        self.assertIs(relation_of(build({E1: denial_, E2: biopsy}, controls=ends)).relation, P.Relation.UNRESOLVED)
        # any one of r2c's controls supported, unclear or missing: held (an interior place included)
        for key in controls:
            for name, changed in (('not rejected', {**controls, key: False}),
                                  ('missing', {k: v for k, v in controls.items() if k != key})):
                with self.subTest(control=key, change=name):
                    self.assertIs(relation_of(build({E1: denial_, E2: biopsy}, controls=changed)).relation,
                                  P.Relation.UNRESOLVED)

    def test_r4_end_to_end_through_r2cs_claims_settle_the_store_and_the_factset(self):
        # the same input end to end (tests/v2/test_claims.py's own pipeline, r2c's RulingOutcomeTests: pass 1's answer
        # read, checked, claimed by contract/claims.py, appraised by a faithful pass 2 that answers each pair control by
        # the asked object's true places, settled, stored, loaded and read into the FactSet): the controls are r2c's
        # whole-range ones, every one rejected, and the pairing sets the denial apart from the biopsy
        from tests.v2 import test_claims as TC
        whole = contract_claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)

        def answer(filed):
            return TC.frame_answer('colonoscopy', [
                TC.examination(words='colonoscope'),
                TC.event('E2', ['S5'], 'Biopsies', 'were taken', 'biopsy', session=[TC.fact('X1', TC.src(['S5']))],
                         target__places=[TC.fact(place, TC.src(['S5'], 'Biopsies')) for place in filed]),
                TC.event('E3', ['S6'], 'biopsies', 'No biopsies were taken', 'biopsy',
                         TC.neg('performed', TC.src(['S6'], 'No biopsies were taken')),
                         session=[TC.fact('X1', TC.src(['S6']))],
                         scope__breadth=[TC.fact('segment', TC.src(['S6'], 'from the cecum to the hepatic flexure'))],
                         scope__segment=['cecum', 'hepatic_flexure'])], TC.fact('E1', TC.src(['S4'])))

        denial_, biopsy = Id(IdFamily.EVENT, 3), Id(IdFamily.EVENT, 2)
        for name, filed, truly, expected in (
                ('truly and only in the sigmoid colon', ['sigmoid_colon'], {'sigmoid_colon'},
                 P.Relation.INDEPENDENT),
                ('truly also in the ascending colon (a short list)', ['sigmoid_colon'],
                 {'sigmoid_colon', 'ascending_colon'}, P.Relation.UNRESOLVED)):
            _claim_set, _events, R = TC.settled(TC.SEGMENT_RANGE, answer(filed), TC.faithful_oracle(
                places={'E2': truly, 'E3': {place.value for place in whole}}))
            with self.subTest(biopsy=name):
                self.assertEqual(set(R.pair_controls), {(biopsy, A.TARGET_PLACES, place) for place in whole}
                                 | {(denial_, A.TARGET_PLACES, Landmark.SIGMOID_COLON)})
                self.assertEqual({key[2] for key, rejected in R.pair_controls.items() if not rejected},
                                 set() if expected is P.Relation.INDEPENDENT else {Landmark.ASCENDING_COLON})
                pair = P.relation(R, denial_, biopsy)
                self.assertIs(pair.relation, expected)
                self.assertIs(pair.row, P.Row.TARGET)

    def test_dq1_a_doubted_rectal_biopsy_leaves_the_established_ascending_colon_biopsy_alone(self):
        # DECISIONS D228 (DQ1), the refutation's input: E1 an established cold-forceps biopsy in the ascending colon;
        # E2 a biopsy whose status pass 1 doubted, in the rectum. claims.py makes no pair control for a biopsy pair
        # (D211), and none is needed: both targets are established and disjoint, so the possible statement is set
        # apart and E1 is held by no pair (it was UNRESOLVED(target), relation:possible_statement)
        established = act(kind=sup(Kind.BIOPSY), lesion=SILENT, places=(sup(Landmark.ASCENDING_COLON),),
                          device=sup(Device.COLD_FORCEPS))
        doubted_ = act(kind=sup(Kind.BIOPSY), status=doubted(PERFORMED), lesion=SILENT, performer=SILENT,
                       places=(sup(Landmark.RECTUM),), device=SILENT)
        R = build({E1: established, E2: doubted_})
        self.assertEqual(P.statements(R), (E2,))
        (pair,) = P.pairs_of(R, E1)
        self.assertTrue(pair.possible)
        self.assertIs(pair.relation, P.Relation.INDEPENDENT)
        self.assertIs(pair.row, P.Row.TARGET)
        self.assertIsNone(P.item(pair))
        self.assertIsNone(P.cause(pair))
        # the doubted biopsy's own place not established (a denial misfiled as an act): held, as before the ruling
        R = build({E1: established, E2: {**doubted_, A.TARGET_PLACES: (unres(Landmark.RECTUM),)}})
        (pair,) = P.pairs_of(R, E1)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
        self.assertEqual(P.cause(pair), 'relation:possible_statement')

    def test_r3d_q1_a_and_c_hold_and_b_is_the_named_release(self):
        # round 1's question Q1 under DECISIONS D238 (and D245's "r3d Q1"), on its own inputs (round 1's NOTES and
        # logs/r3d-inputs.out): (a) and (c) close - an unrejected control holds in D228's arm; (b), where no control asks
        # about the deleted place, stays INDEPENDENT (the named release D228_PLACE, accepted under D228 and D238); and
        # (c) where no control was generated still releases through its status weakening (D228_STATUS: question R3D-ST)
        biopsy = dict(kind=sup(Kind.BIOPSY), lesion=SILENT, device=sup(Device.COLD_FORCEPS))
        # (a) the doubted rectal biopsy beside the established ascending-colon biopsy, "This act was done in the
        # ascending colon." asked of the doubted one and NOT rejected: held (it was INDEPENDENT)
        established = act(**biopsy, places=(sup(Landmark.ASCENDING_COLON),))
        doubted_ = act(**{**biopsy, 'device': SILENT}, status=doubted(PERFORMED), performer=SILENT,
                       places=(sup(Landmark.RECTUM),))
        for rejected, expected in ((False, P.Relation.UNRESOLVED), (True, P.Relation.INDEPENDENT)):
            controls = {(E2, A.TARGET_PLACES, Landmark.ASCENDING_COLON): rejected}
            pair = relation_of(build({E1: established, E2: doubted_}, controls=controls), E2, E1)
            with self.subTest(q1='a', rejected=rejected):
                self.assertIs(pair.relation, expected)
                if not rejected:
                    self.assertIs(pair.row, P.Row.TARGET)
                    self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))
        # (b) a possible statement filed [sigmoid colon, transverse colon] beside a biopsy in the transverse colon: a
        # DOUBT; its transverse colon deleted (9.4, the controls as claims.pair() made them from the full lists: only the
        # act asked about the sigmoid colon, rejected) - no control asks the act about the transverse colon, so nothing
        # is left to hold the pair: INDEPENDENT, D228_PLACE
        full = act(**biopsy, status=unres(PERFORMED), places=(sup(Landmark.SIGMOID_COLON), sup(Landmark.TRANSVERSE_COLON)))
        short = act(**biopsy, status=unres(PERFORMED), places=(sup(Landmark.SIGMOID_COLON),))
        transverse = act(**biopsy, places=(sup(Landmark.TRANSVERSE_COLON),))
        controls = claims_pair_controls(E1, (Landmark.SIGMOID_COLON, Landmark.TRANSVERSE_COLON), E2,
                                        (Landmark.TRANSVERSE_COLON,), lambda subject, place: True)
        self.assertEqual(controls, {(E2, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True})
        R = build({E1: full, E2: transverse}, controls=controls)
        weak = build({E1: short, E2: transverse}, controls=controls)
        self.assertIs(relation_of(R).relation, P.Relation.DOUBT)
        self.assertIs(relation_of(weak).relation, P.Relation.INDEPENDENT)
        self.assertEqual(named_release(R, weak, ('place', E1, 1, sup(Landmark.TRANSVERSE_COLON)), E2),
                         frozenset({D228_PLACE}))
        # (c) an act told under another clinician (inherited) in the rectum beside the team's biopsy in the sigmoid
        # colon, held because "This act was done in the rectum." asked of the team's biopsy was not rejected; its
        # status weakened to unresolved moves it into D228's arm, which reads that control: still held (it was
        # INDEPENDENT)
        other = act(**biopsy, performer=sup(OTHER_CLINICIAN, inherited_from=N1), places=(sup(Landmark.RECTUM),))
        weakened = {**other, A.STATUS: (unres(PERFORMED),)}
        today = act(**biopsy, places=(sup(Landmark.SIGMOID_COLON),))
        controls = {(E2, A.TARGET_PLACES, Landmark.RECTUM): False, (E1, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True}
        before = relation_of(build({E1: other, E2: today}, controls=controls))
        after = relation_of(build({E1: weakened, E2: today}, controls=controls))
        self.assertEqual((before.relation, before.row), (P.Relation.UNRESOLVED, P.Row.BREADTH))
        self.assertEqual((after.relation, after.row), (P.Relation.UNRESOLVED, P.Row.TARGET))
        self.assertTrue(after.possible)
        # (c) where neither control was generated (two biopsies: D211): held before, set apart after - D228_STATUS
        before = build({E1: other, E2: today})
        after = build({E1: weakened, E2: today})
        self.assertIs(relation_of(before).relation, P.Relation.UNRESOLVED)
        self.assertIs(relation_of(after).relation, P.Relation.INDEPENDENT)
        self.assertEqual(named_release(before, after, ('status', E1), E2), frozenset({D228_STATUS}))

    def test_d238_p3_the_doubted_snare_with_its_transverse_colon_omitted_holds_45385_beside_an_unrejected_control(
            self):
        # refute-r3d-r1 D1, its p3_end_to_end shape, through the per-code rule (engine/evaluate.decide) on
        # tests/v2/evaluate_fixtures' colonoscopy: E2 the cold snare of L1 in the transverse colon (45385 READY alone);
        # E3 a doubted cold snare truly [rectum, transverse colon]. Filed in full: held. Filed [rectum] (the transverse
        # colon omitted) beside an unrejected pair control - E3 asked "This act was done in the transverse colon.", or E2
        # asked about the rectum - held (DECISIONS D238); with that control rejected, or with none, READY. No control at
        # all is what contract/claims.py makes for two snares (D211: two acts of one kind are never paired), so in
        # production this shape stays READY: the named release, question R3D-NC
        from studio.interpretation.engine import evaluate as EV
        from tests.v2 import evaluate_fixtures as EF

        def scene(filed, controls=()):
            doc = EF.colonoscopy(snare=False)
            doc.lesion(1)
            doc.act(2, Kind.SNARE, lesion=EF.sup(L1), places=[EF.sup(Landmark.TRANSVERSE_COLON)],
                    device=EF.sup(Device.COLD_SNARE))
            doc.act(3, Kind.SNARE, status=EF.doubted(PERFORMED), places=[EF.sup(place) for place in filed],
                    device=EF.sup(Device.COLD_SNARE))
            doc.controls.update(dict(controls))
            return doc.build()

        def snare_code(R):
            found = EV.decide('45385', (), R)
            ready = bool(found.supporting) and not found.held_facts and found.exclusion is None
            return ('READY' if ready else 'HELD'), [event.number for event in found.supporting]

        self.assertFalse(contract_claims._place_identity_pair(Kind.SNARE, Kind.SNARE))
        alone = EF.colonoscopy(snare=False)
        alone.lesion(1)
        alone.act(2, Kind.SNARE, lesion=EF.sup(L1), places=[EF.sup(Landmark.TRANSVERSE_COLON)],
                  device=EF.sup(Device.COLD_SNARE))
        self.assertEqual(snare_code(alone.build()), ('READY', [2]))
        self.assertEqual(snare_code(scene([Landmark.RECTUM, Landmark.TRANSVERSE_COLON])), ('HELD', []))
        self.assertEqual(snare_code(scene([Landmark.RECTUM])), ('READY', [2]))  # no control: named (R3D-NC)
        for key in ((E3, A.TARGET_PLACES, Landmark.TRANSVERSE_COLON), (E2, A.TARGET_PLACES, Landmark.RECTUM)):
            with self.subTest(control=key):
                R = scene([Landmark.RECTUM], {key: False})
                self.assertEqual(snare_code(R), ('HELD', []))
                (pair,) = P.pairs_of(R, E2)
                self.assertEqual((pair.statement, pair.relation, pair.row), (E3, P.Relation.UNRESOLVED, P.Row.TARGET))
                self.assertEqual(snare_code(scene([Landmark.RECTUM], {key: True})), ('READY', [2]))

    def test_d239_the_same_lesion_shapes_hold_45385(self):
        # refute-r3d-r1 D2, its p3_end_to_end and p2_own_arm shapes, through the per-code rule on tests/v2/
        # evaluate_fixtures' colonoscopy (E2 the established cold snare of L1 in the sigmoid colon, 45385 READY alone)
        # beside E3 a doubted cold snare told in the RECTUM: a lesion that may be the act's own is never set apart by
        # place in D228's arm (DECISIONS D239), so 45385 is held; a lesion established as another stays READY
        from studio.interpretation.engine import evaluate as EV
        from tests.v2 import evaluate_fixtures as EF

        def scene(lesion=None, lesions=(), act_lesion=None, controls=()):
            doc = EF.colonoscopy()
            if act_lesion is not None:
                doc.events[E2] = {**doc.events[E2], A.TARGET_LESION: (act_lesion,)}
            for number, facts in dict(lesions).items():
                doc.lesions[EF.L(number)] = facts
            over = dict(places=[EF.sup(Landmark.RECTUM)], device=EF.sup(Device.COLD_SNARE))
            if lesion is not None:
                over['lesion'] = lesion
            doc.act(3, Kind.SNARE, status=EF.doubted(PERFORMED), **over)
            doc.controls.update(dict(controls))
            return doc.build()

        def snare_code(R):
            found = EV.decide('45385', (), R)
            ready = bool(found.supporting) and not found.held_facts and found.exclusion is None
            return 'READY' if ready else 'HELD'

        distinct = {2: EF.facts_of(distinct_from=[EF.sup(L1)])}
        for name, R, expected in (
                ('the same polyp: E3 lesion supported L1', scene(EF.sup(L1)), 'HELD'),
                ('E3 lesion unresolved L1', scene(EF.unres(L1)), 'HELD'),
                ('E3 lesion doubted L2, its reading L1', scene(EF.doubted(L2, L1), distinct), 'HELD'),
                ('E3 lesion L2, same_as(L2, L1) unresolved',
                 scene(EF.sup(L2), {2: EF.facts_of(distinct_from=[EF.sup(L1)], same_as=[EF.unres(L1)])}), 'HELD'),
                ('the act side: E2 lesion unresolved L1, E3 lesion supported L1',
                 scene(EF.sup(L1), act_lesion=EF.unres(L1)), 'HELD'),
                ('R3D-LC: E3 lesion L2 distinct from L1, E3 asked about L1 and NOT rejected',
                 scene(EF.sup(L2), distinct, controls={(E3, A.TARGET_LESION, L1): False}), 'HELD'),
                ('E3 lesion L2 distinct from L1', scene(EF.sup(L2), distinct), 'READY'),
                ('E3 lesion silent (DQ1\'s shape)', scene(), 'READY')):
            with self.subTest(case=name):
                self.assertEqual(snare_code(R), expected)
                (pair,) = P.pairs_of(R, E2)
                self.assertIs(pair.relation is P.Relation.INDEPENDENT, expected == 'READY')
        # the same polyp told in the rectum is a DOUBT on the snare: performed_status at rank 2, quoting both
        (pair,) = P.pairs_of(scene(EF.sup(L1)), E2)
        self.assertIs(pair.relation, P.Relation.DOUBT)
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS))

    def test_411_an_unknown_target_asks_statement_scope(self):
        # "Does 'No polyp was removed from the rectum.' refer to the polyp removed with the cold snare?"
        rectal = denial(kind=sup(Kind.REMOVAL), breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),))
        for name, places in (('silent places', ()), ('unresolved', (unres(Landmark.SIGMOID_COLON),)),
                             ('doubted', (doubted(Landmark.SIGMOID_COLON, Landmark.RECTUM),)),
                             ('contradicted', (contra(Landmark.SIGMOID_COLON, Landmark.RECTUM),))):
            pair = relation_of(build({E1: rectal, E2: act(lesion=SILENT, places=places)}))
            with self.subTest(places=name):
                self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                self.assertIs(pair.row, P.Row.TARGET)
                self.assertEqual(P.item(pair).fact, rq.FactKey.STATEMENT_SCOPE)

    def test_19_worked_example(self):
        # E3 ("Neither biopsy ... was performed", all of its kind in X1, no performer) against E5 (a biopsy told in the
        # nursing note, performer [] inherited): every row SAME, a CONTRADICTION; E5's status doubted: a DOUBT
        e3 = denial(kind=sup(Kind.BIOPSY), performer=SILENT)
        e5 = act(kind=sup(Kind.BIOPSY), performer=SILENT, lesion=SILENT, places=(sup(Landmark.RECTUM),),
                 device=sup(Device.COLD_FORCEPS))
        R = build({E3: e3, E5: e5})
        self.assertIs(relation_of(R, E3, E5).relation, P.Relation.CONTRADICTION)
        R = build({E3: e3, E5: {**e5, A.STATUS: (doubted(PERFORMED),)}})
        self.assertIs(relation_of(R, E3, E5).relation, P.Relation.DOUBT)
        # E4 filed as a performed tattoo, its status unresolved: a possible statement that holds a genuine tattoo or
        # injection of X1, never READY on the strength of the misfiling (HO-3)
        e4 = act(kind=sup(Kind.TATTOO), status=unres(PERFORMED), lesion=SILENT, places=(), device=SILENT)
        for kind in (Kind.TATTOO, Kind.INJECTION):
            R = build({E4: e4, E7: act(kind=sup(kind), lesion=SILENT, device=sup(Device.NEEDLE))})
            with self.subTest(genuine=kind.value):
                self.assertIsNot(relation_of(R, E4, E7).relation, P.Relation.INDEPENDENT)


# --- unlisted statements (3.2.6 rule 4) --------------------------------------------------------------------------------


def unlisted(what=ct.UnlistedWhat.DENIAL, kind=None, session=None):
    return UnlistedStatement(units=(Span(900, 940),), what=what, kind=kind, session=session)


class UnlistedTests(SimpleTestCase):
    def test_rule_4(self):
        sessions = TWO_SESSIONS
        acts = {E1: act(), E2: act(session=sup(X2)), E3: act(session=unres(X2)), E4: act(kind=sup(Kind.BIOPSY)),
                E5: act(status=neg(PERFORMED)), E6: act(status=sup(Status.ATTEMPTED_NOT_COMPLETED)),
                E7: act(kind=sup(Kind.REMOVAL)), E8: act(status=doubted(PERFORMED))}
        cases = (
            ('a snare denial in X1', unlisted(kind=Kind.SNARE, session=X1), {E1, E6, E8}),
            ('a snare doubt in X1', unlisted(what=ct.UnlistedWhat.DOUBT, kind=Kind.SNARE, session=X1), {E1, E6, E8}),
            ('no session', unlisted(kind=Kind.SNARE), {E1, E2, E3, E6, E8}),
            ('no kind', unlisted(session=X1), {E1, E4, E6, E7, E8}),
            ('neither', unlisted(), {E1, E2, E3, E4, E6, E7, E8}),
            ('an umbrella', unlisted(kind=Kind.REMOVAL, session=X1), {E1, E6, E7, E8}),
            ('an unlisted act', unlisted(what=ct.UnlistedWhat.ACT, kind=Kind.SNARE, session=X1), set()))
        for name, entry, expected in cases:
            R = build(acts, sessions=sessions, unlisted=(entry,))
            found = {subject for subject in acts if P.unlisted_pairs(R, subject)}
            with self.subTest(case=name):
                self.assertEqual(found, expected)
        R = build({E1: act()}, unlisted=(unlisted(kind=Kind.SNARE),))
        (pair,) = P.unlisted_pairs(R, E1)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED)
        self.assertEqual((pair.index, pair.act), (0, E1))
        self.assertEqual(pair.spans, (Span(100, 140), Span(900, 940)))
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS))

    def test_d228_an_unlisted_pair_asks_performed_status_at_rank_2(self):
        # DECISIONS D228 (DQ3): an unlisted pair asks performed_status at 4.8's RANK row 2 ("an unlisted denial or doubt
        # of its kind"), not statement_scope (rank 3) - for a denial and a doubt, with and without a kind and a session,
        # against a performed and an attempted act; its cause stays ``unlisted`` and its relation UNRESOLVED
        doubt_item = rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS)
        self.assertIn(doubt_item, rq.RULES[rq.Requirement.SUP_CLEAN].asks)
        checked = 0
        for what in (ct.UnlistedWhat.DENIAL, ct.UnlistedWhat.DOUBT):
            for kind in (Kind.SNARE, Kind.REMOVAL, None):
                for session in (X1, None):
                    for status in (sup(PERFORMED), sup(Status.ATTEMPTED_NOT_COMPLETED), doubted(PERFORMED)):
                        R = build({E1: act(status=status)}, unlisted=(unlisted(what=what, kind=kind, session=session),))
                        (pair,) = P.unlisted_pairs(R, E1)
                        with self.subTest(what=what.value, kind=kind, session=session, status=status.result):
                            self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                            self.assertEqual(P.item(pair), doubt_item)
                            self.assertNotEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE,
                                                                      rq.FactKey.STATEMENT_SCOPE))
                            self.assertEqual(P.cause(pair), 'unlisted')
                        checked += 1
        self.assertEqual(checked, 2 * 3 * 2 * 3)
        # a filed possible statement's UNRESOLVED relation still asks statement_scope (4.5 step 2): only the unlisted
        # pair moved
        R = build({E1: act(status=unres(PERFORMED), date=unres(ON), lesion=SILENT, places=(unres(Landmark.RECTUM),)),
                   E2: act()})
        self.assertEqual(P.item(relation_of(R)), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))


# --- DECISIONS D265: a digital examination is no session's examination on the act side (repair r4a, round w9r) -------


def examination(**over) -> dict:
    """An examination of X1 done today by the documenting team (an endoscopic one: its device silent)."""
    base = dict(kind=sup(Kind.EXAMINATION), status=sup(PERFORMED), session=sup(X1), date=sup(ON), performer=sup(TEAM))
    base.update(over)
    return event(**base)


# The device states of an event filed as an examination: those that claim manual (a digital examination, FINAL 5.6 E13)
# and those that claim none.
CLAIMING = (('supported manual', sup(Device.MANUAL)), ('unresolved manual', unres(Device.MANUAL)),
            ('doubted manual', doubted(Device.MANUAL)), ('contradicted manual/endoscope',
                                                         contra(Device.MANUAL, Device.ENDOSCOPE)))
CLAIMING_NONE = (('silent', None), ('endoscope', sup(Device.ENDOSCOPE)), ('manual negated', neg(Device.MANUAL)))


class D265DigitalExaminationTests(SimpleTestCase):
    """DECISIONS D265 (repair r4a of round w9r owns this module for it; r4a-2 Q4 QDRE, refute-r4a-r2 Q4+): an examination
    statement is never paired with a digital examination as with the session's examination - on the act side an event
    whose device claims manual (``digital_examination``) is never the examination (``act_kinds``), so neither a filed
    denial, nor a possible statement, nor an unlisted doubt or denial of kind examination pairs with it; a device that
    claims no manual leaves the pairing as it was. Any other kind such an act may be still pairs, and so does an unlisted
    entry of no kind; the statement side is read as before (the step's NOTES, question Q-R4A-DRES)."""

    STATEMENTS = (('denial', denial(kind=sup(Kind.EXAMINATION))),
                  ('possible statement', examination(status=unres(PERFORMED))),
                  ('doubted statement', examination(status=doubted(PERFORMED), date=unres(ON))))

    def test_an_examination_statement_never_pairs_with_a_digital_examination(self):
        for device_name, device in CLAIMING + CLAIMING_NONE:
            digital = (device_name, device) in CLAIMING
            for statement_name, statement in self.STATEMENTS:
                with self.subTest(device=device_name, statement=statement_name):
                    R = build({E1: statement, E2: examination(device=device)})
                    self.assertEqual(P.digital_examination(R, E2), digital)
                    self.assertEqual(Kind.EXAMINATION in P.act_kinds(R, E2), not digital)
                    self.assertEqual(P.paired(R, E1, E2), not digital)
                    self.assertEqual(bool(P.pairs_of(R, E2)), not digital)
            for what in (ct.UnlistedWhat.DENIAL, ct.UnlistedWhat.DOUBT):
                for card in (X1, None):
                    with self.subTest(device=device_name, unlisted=what.value, card=card):
                        R = build({E2: examination(device=device)}, unlisted=(unlisted(what, Kind.EXAMINATION, card),))
                        self.assertEqual(bool(P.unlisted_pairs(R, E2)), not digital)
                        R = build({E2: examination(device=device)}, unlisted=(unlisted(what, None, card),))
                        self.assertTrue(P.unlisted_pairs(R, E2))  # an entry of no kind pairs with any act

    def test_a_digital_act_whose_kind_is_open_still_pairs_through_its_other_kinds(self):
        """An event of a silent (or doubted examination|snare) kind whose device claims manual may be a snare: a snare
        denial pairs with it as before, an examination denial never."""
        for kind in (SILENT, doubted(Kind.EXAMINATION, Kind.SNARE)):
            with self.subTest(kind=kind.result):
                R = build({E1: denial(), E2: act(kind=kind, device=sup(Device.MANUAL))})
                self.assertTrue(P.paired(R, E1, E2))
                self.assertEqual(relation_of(R).kinds & {Kind.EXAMINATION}, frozenset())
                R = build({E1: denial(kind=sup(Kind.EXAMINATION)), E2: act(kind=kind, device=sup(Device.MANUAL))})
                self.assertFalse(P.paired(R, E1, E2))

    def test_the_statement_side_is_read_as_before(self):
        """A digital examination that is a statement - "No digital rectal examination was performed." (kind examination,
        device manual, status negated) - still pairs with the session's endoscopic examination (as built: the step's
        NOTES, question Q-R4A-DRES - removing it would release under 9.4's device weakening)."""
        R = build({E1: denial(kind=sup(Kind.EXAMINATION), device=sup(Device.MANUAL)), E2: examination()})
        self.assertTrue(P.paired(R, E1, E2))
        self.assertIsNot(relation_of(R).relation, P.Relation.INDEPENDENT)

    def test_one_derivation_with_questions_and_combination(self):
        """``digital_examination`` is engine/questions.digital_examination's derivation (that function calls it), and
        equals step r4d's combination._digital wherever the event may be the examination, over every device state and
        kind state here."""
        from studio.interpretation.engine import combination, questions
        kinds = (sup(Kind.EXAMINATION), SILENT, doubted(Kind.EXAMINATION, Kind.SNARE), sup(Kind.SNARE))
        for device_name, device in CLAIMING + CLAIMING_NONE:
            for kind in kinds:
                with self.subTest(device=device_name, kind=kind.value):
                    R = build({E2: examination(kind=kind, device=device)})
                    self.assertEqual(P.digital_examination(R, E2), questions.digital_examination(R, E2))
                    if F.possibly(F.fact(R, E2, A.KIND), Kind.EXAMINATION):
                        self.assertEqual(P.digital_examination(R, E2), combination._digital(R, E2))


# --- properties (9.4, at the pairing level; hypothesis) ----------------------------------------------------------------


SETTINGS = dict(max_examples=300, deadline=None, derandomize=True,
                suppress_health_check=[hypothesis.HealthCheck.too_slow, hypothesis.HealthCheck.data_too_large])


def state_of(draw, value, other):
    return in_state(draw(st.sampled_from(STATES)), value, other)


@st.composite
def other_rows(draw, keep: P.Row):
    """Random facts for every row but ``keep``, every state possible: the "whatever else" of 4.5 relation 1."""
    over = {}
    if keep is not P.Row.SESSION:
        over['session'] = state_of(draw, draw(st.sampled_from((X1, X2))), X2)
    if keep is not P.Row.TIMING:
        over['date'] = state_of(draw, draw(st.sampled_from((ON, EARLIER))), LATER)
    if keep is not P.Row.PERFORMER:
        over['performer'] = state_of(draw, draw(st.sampled_from((TEAM, OTHER_CLINICIAN))), TEAM)
        over['person'] = state_of(draw, P1, P2)
    if keep is not P.Row.TECHNIQUE:
        over['device'] = state_of(draw, draw(st.sampled_from((Device.COLD_SNARE, Device.SNARE, Device.OTHER))),
                                  Device.HOT_SNARE)
    return over


def _apart_by_lesion(mode: str):
    """A pair set apart by its lesions alone (no place set established on the statement's side)."""
    lesions = {L1: lesion_of(distinct=(L2,)), L2: lesion_of(), L3: lesion_of(distinct=(L2,))}
    if mode == 'listed':
        statement = denial(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1), sup(L3)))
        own = (L1, L3)
        arm = [('event', E1, A.SCOPE_TARGETS, 0), ('event', E1, A.SCOPE_TARGETS, 1), ('lesion', L1, A.DISTINCT_FROM, 0),
               ('lesion', L3, A.DISTINCT_FROM, 0)]
    elif mode == 'act-filed':
        statement = act(status=unres(PERFORMED), lesion=sup(L1), places=())
        own = (L1,)
        arm = [('event', E1, A.TARGET_LESION, 0), ('lesion', L1, A.DISTINCT_FROM, 0)]
    else:
        statement = denial(breadth=sup(Breadth.SINGLE_TARGET), lesion=sup(L1))
        own = (L1,)
        arm = [('event', E1, A.TARGET_LESION, 0), ('lesion', L1, A.DISTINCT_FROM, 0)]
    events = {E1: statement, E2: act(lesion=sup(L2))}
    controls = controls_both_ways(E1, E2, statement_lesions=own, act_lesions=(L2,))
    return events, lesions, controls, arm + [('event', E2, A.TARGET_LESION, 0)]


def _apart_by_place(mode: str):
    """A pair set apart by its places alone (no lesion on the act's side)."""
    if mode == 'segment':
        statement = denial(breadth=sup(Breadth.SEGMENT), segment=(sup(Landmark.CECUM), sup(Landmark.HEPATIC_FLEXURE)))
        own = tuple(sorted(WHOLE_CECUM_TO_HEPATIC_FLEXURE, key=lambda place: place.value))  # every place (F1)
        arm = [('event', E1, A.SCOPE_SEGMENT, 0), ('event', E1, A.SCOPE_SEGMENT, 1)]
    elif mode == 'act-filed':
        statement = act(status=unres(PERFORMED), lesion=SILENT, places=(sup(Landmark.RECTUM),))
        own = (Landmark.RECTUM,)
        arm = [('event', E1, A.TARGET_PLACES, 0)]
    else:
        statement = denial(breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),))
        own = (Landmark.RECTUM,)
        arm = [('event', E1, A.TARGET_PLACES, 0)]
    events = {E1: statement, E2: act(lesion=SILENT, places=(sup(Landmark.SIGMOID_COLON),))}
    controls = controls_both_ways(E1, E2, statement_places=own, act_places=(Landmark.SIGMOID_COLON,))
    return events, {}, controls, arm + [('event', E2, A.TARGET_PLACES, 0)]


APART = {('lesion', mode): (lambda mode=mode: _apart_by_lesion(mode)) for mode in ('single', 'listed', 'act-filed')}
APART.update({('place', mode): (lambda mode=mode: _apart_by_place(mode)) for mode in ('single', 'segment',
                                                                                     'act-filed')})


class PropertyTests(SimpleTestCase):
    @hypothesis.settings(**SETTINGS)
    @hypothesis.given(st.sampled_from([P.Row.SESSION, P.Row.TIMING, P.Row.PERFORMER, P.Row.TECHNIQUE]), st.data())
    def test_p_any_row(self, which, data):
        """P-ANY-ROW [R:HO-2]: a pair with one row proving independence is INDEPENDENT (unless claimed) whatever the
        other rows' states; a pair with none is never INDEPENDENT."""
        R = proving(which)
        over = data.draw(other_rows(which))
        breadth = data.draw(st.sampled_from([sup(Breadth.ALL_OF_KIND), unres(Breadth.SINGLE_TARGET), SILENT,
                                             sup(Breadth.SINGLE_TARGET)]))
        claimed = data.draw(st.booleans())
        statement = {**R.events[E1], **event(breadth=breadth, **over)}
        if claimed:
            statement[A.SCOPE_COVERS] = (sup(E2),)
        act_over = data.draw(other_rows(which))
        act_facts = {**R.events[E2], **event(**{k: v for k, v in act_over.items() if k != 'person'})}
        if which is P.Row.SESSION:
            statement[A.SESSION], act_facts[A.SESSION] = (sup(X2),), (sup(X1),)
        R = build({E1: statement, E2: act_facts}, sessions=R.sessions, controls=R.pair_controls)
        pair = relation_of(R)
        self.assertEqual(pair.result(which), INDEPENDENT)
        self.assertIs(pair.relation, P.Relation.UNRESOLVED if claimed else P.Relation.INDEPENDENT)

    @hypothesis.settings(**SETTINGS)
    @hypothesis.given(st.data())
    def test_a_pair_with_no_independent_row_is_never_independent(self, data):
        over = data.draw(other_rows(P.Row.TARGET))
        breadth = data.draw(st.sampled_from([sup(Breadth.ALL_OF_KIND), unres(Breadth.SINGLE_TARGET), SILENT]))
        R = build({E1: denial(breadth=breadth, **over), E2: act(**data.draw(other_rows(P.Row.TARGET)))},
                  sessions=TWO_SESSIONS)
        pair = relation_of(R)
        if INDEPENDENT not in dict(pair.rows).values():
            self.assertIsNot(pair.relation, P.Relation.INDEPENDENT)
        else:
            self.assertIn(pair.relation, (P.Relation.INDEPENDENT, P.Relation.UNRESOLVED))

    @hypothesis.settings(**SETTINGS)
    @hypothesis.given(st.sampled_from(sorted(APART, key=repr)), st.data())
    def test_p_unknown_target(self, base, data):
        """P-UNKNOWN-TARGET: an unknown, unresolved, doubted or contradicted target on either side, or a pair control
        not rejected, never makes the target row yield INDEPENDENT - for every combination of the other rows' states.
        Each case starts from a pair set apart by exactly one arm (asserted INDEPENDENT), then makes ONE of that arm's
        facts not established (or deletes a list member) or ONE of its pair controls not rejected (or not generated).
        Named: the arm of an act-filed possible statement requires no pair control (DECISIONS D228) and reads the ones
        that exist (D238), so there a control NOT GENERATED leaves the pair apart, and the case asserts that instead;
        a control generated and not rejected holds there as everywhere (round 1's question Q1 (a), closed by D238), and
        so does its facts' clause."""
        arm, mode = base
        events, lesions, controls, facts_of_arm = APART[base]()
        other = data.draw(other_rows(P.Row.TARGET))
        events[E1] = {**events[E1], **event(**other)}
        events[E2] = {**events[E2], **event(**{k: v for k, v in data.draw(other_rows(P.Row.TARGET)).items()})}
        R = build(events, lesions=lesions, controls=controls)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT, (arm, mode))
        what = data.draw(st.sampled_from(sorted(facts_of_arm, key=repr) + sorted(controls, key=repr)))
        if what in controls:
            if data.draw(st.booleans()):
                controls = {**controls, what: False}  # generated and not rejected: never INDEPENDENT, in every arm
            else:
                controls = {key: value for key, value in controls.items() if key != what}
                if mode == 'act-filed':  # not generated: D228's arm requires none (D238)
                    self.assertEqual(row_of(build(events, lesions=lesions, controls=controls), P.Row.TARGET),
                                     INDEPENDENT, (arm, mode, what))
                    return
        else:
            table, subject, attribute, index = what
            source = events if table == 'event' else lesions
            members = list(source[subject][attribute])
            if attribute in (A.TARGET_PLACES, A.SCOPE_SEGMENT) and data.draw(st.booleans()):
                del members[index]  # a short list is never evidence (SC-B); a listed target deleted is a narrower list
            else:
                found = members[index]
                members[index] = in_state(data.draw(st.sampled_from(NOT_ESTABLISHED)), found.value, found.value)
            source[subject] = {**source[subject], attribute: tuple(members)}
        R = build(events, lesions=lesions, controls=controls)
        self.assertIsNot(row_of(R, P.Row.TARGET), INDEPENDENT, (arm, mode, what))

    def test_p_unknown_kind(self):
        """P-UNKNOWN-KIND [R:HO-5], exhaustive over requirements_table.FAMILY_KINDS (D191): a statement whose kind is
        not established - unresolved, doubted or contradicted - pairs with at least every act the same statement with
        an established kind pairs with: with every act of a kind some kind of its session's family covers, and, its
        session not established either, with every act of a kind any kind covers."""
        covered = {kind for kind in Kind if any(rq.catalogue.covers(item, kind) for item in Kind)}
        acts = {Id(IdFamily.EVENT, index): act(kind=sup(kind), purpose=sup(ct.Purpose.MARKING))
                for index, kind in enumerate(Kind, start=20)}
        kind_of = {subject: facts[A.KIND][0].value for subject, facts in acts.items()}
        checked = 0
        for family, family_kinds in RT.FAMILY_KINDS.items():
            for own in family_kinds:
                weak = {E2: unres(own), E3: doubted(own), E4: contra(own, Kind.OTHER)}
                statements = {E1: denial(kind=sup(own))}
                statements.update({subject: denial(kind=kind) for subject, kind in weak.items()})
                statements.update({Id(IdFamily.EVENT, 10 + subject.number): denial(kind=kind, session=unres(X1))
                                   for subject, kind in weak.items()})
                R = build({**statements, **acts}, sessions={X1: session_of(family)})

                def pairs_with(statement):
                    return {kind_of[subject] for subject in acts if P.paired(R, statement, subject)}

                established = pairs_with(E1)
                family_wide = {kind for kind in Kind if any(rq.catalogue.covers(item, kind)
                                                            for item in family_kinds | {own})}
                for subject in weak:
                    with self.subTest(family=family.value, kind=own.value, weak=weak[subject].result.value):
                        unknown = pairs_with(subject)
                        self.assertLessEqual(established, unknown)
                        self.assertEqual(unknown, family_wide)
                        self.assertEqual(pairs_with(Id(IdFamily.EVENT, 10 + subject.number)), covered)
                        checked += 1
        self.assertEqual(checked, 3 * sum(len(kinds) for kinds in RT.FAMILY_KINDS.values()))

    def test_the_unknown_kind_property_turns_red_on_a_narrowed_family_table(self):
        # a mutant FamilyKinds table of {snare} (the triage's 2d#1 mutant) breaks P-UNKNOWN-KIND here
        narrowed = {family: frozenset({Kind.SNARE}) for family in RT.FAMILY_KINDS}
        R = build({E1: denial(kind=unres(Kind.BIOPSY)), E2: act(kind=sup(Kind.EMR))})
        self.assertTrue(P.paired(R, E1, E2))
        with mock.patch.object(F, 'FAMILY_KINDS', narrowed):
            self.assertFalse(P.paired(R, E1, E2))

    @hypothesis.settings(**{**SETTINGS, 'max_examples': 400})
    @hypothesis.given(st.data())
    def test_p_mono_a_weakening_never_releases_a_held_act(self, data):
        """P-MONO at the pairing level (9.4's weakenings): an established fact to unresolved, a doubt added, an
        established control to not rejected, a place list member deleted (the pair controls left as they were: made
        from the full lists by contract/claims.py's rule, a segment's whole range included, DECISIONS D223), an event's
        established status to unresolved. An act held by a pair or an unlisted pair before stays held, but for the
        releases the module is allowed, each checked to be exactly that one (named_release; repair r3d's NOTES):
        D228's as D238 narrows them - the arm of an act-filed possible statement requires no pair control and reads the
        ones that exist, so a place deletion beside it where no control asks the other object about the deleted place
        (D228_PLACE, accepted under D228 and D238 by DECISIONS D245), or a status weakening that moves an act of another
        date or performer into it where a control the controlled reading requires was never generated (D228_STATUS,
        question R3D-ST), can set a pair apart, never through an unrejected control - and repair r2d's two, a deleted
        member that overlapped a place of the other without being compatible with it (r2d's Q2, named by D245) and a
        deleted member that was not established (r2d's Q3, D245's option (b)). D220's class, a held pair whose only
        unrejected control asks about the member the weakening deletes, is never released (ScBTests), and the
        place-deletion property's generator reaches it (test_the_place_deletion_generator_sees_sc_b). Left out, and
        named (round 2's question Q4, which DECISIONS D228 keeps as built): weakening the date relation or performer
        of an event whose status is established, which can take it out of 4.5's "which pairs" (established as
        another) altogether."""
        R = random_factset(data)
        before = held(R)
        weak, how = weaken(data, R)
        for released in sorted(before - held(weak), key=repr):
            self.assertIsNotNone(named_release(R, weak, how, released), (how, released))

    @hypothesis.settings(**{**SETTINGS, 'max_examples': 300})
    @hypothesis.given(st.deferred(lambda: target_pair()), st.data())  # target_pair is defined below the class
    def test_p_mono_a_deleted_place_releases_a_pair_only_by_a_named_release(self, pair, data):
        """P-MONO's place deletion where SC-B lives (the refutation's PT): a statement in every target arm (single,
        listed, segment, an act of another performer, an act-filed possible statement) against one act, every row but
        the target SAME, colonic places from a disjoint set, the pair controls made from the full lists and mostly
        rejected. Deleting a member of either list (the controls left as they were) releases the act only by a named
        release (named_release)."""
        _mode, R = pair
        weak, how = delete_a_place(data, R)
        for released in sorted(held(R) - held(weak), key=repr):
            self.assertIsNotNone(named_release(R, weak, how, released), (how, released))

    def test_the_mono_generators_are_not_vacuous(self):
        # a generator that stopped producing holds would make P-MONO pass vacuously, so each share is pinned well under
        # what it is (measured when r3d was built, 20 seeds of 100 examples: the general generator 0.48 to 0.84, the
        # target generator 0.70 to 0.97; round 2 measured 310 of 400). The general generator's share is measured under
        # 4.2's reading before D220 (facts.apart_by_controls patched), which can only hold less, so it is a lower bound
        # of the module's: test_facts' fixture harvest runs this test and forbids any apart_by_place answer D220
        # changed, and a settled three-event FactSet can hold one (repair r2d's Q1: an unrejected control another
        # object's place made), about one run in thirty (r3d's NOTES)
        counts = {'examples': 0, 'held': 0, 'target examples': 0, 'target held': 0}

        @hypothesis.settings(**{**SETTINGS, 'max_examples': 100})
        @hypothesis.given(st.data())
        def sample(data):
            counts['examples'] += 1
            with mock.patch.object(F, 'apart_by_controls', before_d220):
                counts['held'] += bool(held(random_factset(data)))

        @hypothesis.settings(**{**SETTINGS, 'max_examples': 100})
        @hypothesis.given(target_pair())
        def sample_target(pair):
            counts['target examples'] += 1
            counts['target held'] += bool(held(pair[1]))

        sample()
        sample_target()
        self.assertGreaterEqual(counts['examples'], 100)
        self.assertGreater(counts['held'], 0.25 * counts['examples'])
        self.assertGreaterEqual(counts['target examples'], 100)
        self.assertGreater(counts['target held'], 0.3 * counts['target examples'])

    def test_the_place_deletion_generator_sees_sc_b(self):
        # the refutation's PT: P-MONO could not see SC-B. The place-deletion property's examples must reach D220's
        # class - an act held before the deletion and after it, which the reading before D220 (only the controls
        # asking about the other object's CURRENT members; repair r2d keeps it by value) releases - so that property
        # goes red on round 2's reading; the module holds every one of them. Counted in the arms pairing reads itself
        # (listed, segment): the single arm's answers are facts.apart_by_place's, which test_facts' fixture harvest
        # requires this module's tests that are not hypothesis tests to leave as 4.2 read them before D220 (ScBTests'
        # docstring; r3d's NOTES measure the class in every arm). The general generator, whose three events draw every
        # row at random, did not reach it in r3d's wide search (its NOTES).
        found = {'examples': 0, 'sc_b': 0}

        @hypothesis.settings(**{**SETTINGS, 'max_examples': 400})
        @hypothesis.given(target_pair(modes=('listed', 'segment')), st.data())
        def target(pair, data):
            _mode, R = pair
            weak = delete_a_place(data, R)[0]
            with mock.patch.object(F, 'apart_by_controls', before_d220):
                released_before_d220 = held(R) - held(weak)
            sc_b = released_before_d220 & held(weak)
            self.assertLessEqual(sc_b, held(R))
            found['examples'] += 1
            found['sc_b'] += len(sc_b)

        target()
        self.assertGreaterEqual(found['examples'], 400)
        # hypothesis draws differently from one run to another here (derandomized, its examples still move with the
        # modules loaded), so the pin is far under what was measured (r3d's NOTES: 300 examples, 40 seeds, 5 to 31)
        self.assertGreaterEqual(found['sc_b'], 2, found)


KINDS = (Kind.SNARE, Kind.EMR, Kind.REMOVAL, Kind.BIOPSY, Kind.INJECTION, Kind.TATTOO, Kind.CLIP,
         Kind.BLEEDING_CONTROL)
# The general generator's places: disjoint colonic places (SC-B's ground), the colon (which holds most of them), the
# rectum (which the colon does not), and an anastomosis (never disjoint from anything: r2d's Q2)
PLACES = (Landmark.RECTUM, Landmark.SIGMOID_COLON, Landmark.CECUM, Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE,
          Landmark.TRANSVERSE_COLON, Landmark.DESCENDING_COLON, Landmark.COLON, Landmark.ANASTOMOSIS)
# The target generator's places: pairwise disjoint colonic places, and the colon
TARGET_PLACES = (Landmark.CECUM, Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE, Landmark.TRANSVERSE_COLON,
                 Landmark.SPLENIC_FLEXURE, Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON, Landmark.RECTUM)
TARGET_MODES = ('single', 'listed', 'segment', 'other performer', 'possible')


def held(R: FactSet) -> set:
    return {subject for subject in R.events
            if any(pair.relation is not P.Relation.INDEPENDENT for pair in P.pairs_of(R, subject))
            or P.unlisted_pairs(R, subject)}


def before_d220(R, a, b, attribute, of_a, of_b):
    """facts.apart_by_controls as 4.2 read it before DECISIONS D220 (repair r2d's tests keep it by value): only the
    controls asking each object about the other's CURRENT members, every one rejected."""
    return (all(R.pair_controls.get((a, attribute, value)) is True for value in of_b)
            and all(R.pair_controls.get((b, attribute, value)) is True for value in of_a))


def claimed_places(facts) -> list:
    """claims.places (r2c, DECISIONS D223): the members claimed with a supported state, and a segment's whole range
    (its two places when they are not two places claimed supported)."""
    found = [item.value for item in facts.get(A.TARGET_PLACES, ()) if item.state is State.SUPPORTED]
    ends = [item.value for item in facts.get(A.SCOPE_SEGMENT, ()) if item.state is State.SUPPORTED]
    return found + (list(contract_claims.segment_range(ends[0], ends[1])) if len(ends) == 2 else ends)


def claimed_lesions(facts) -> list:
    found = [item.value for item in facts.get(A.TARGET_LESION, ()) if item.state is State.SUPPORTED]
    return found + [item.value for item in facts.get(A.SCOPE_TARGETS, ()) if item.state is State.SUPPORTED]


def mostly(draw, value, other):
    """``value`` supported three times in four, else in any state (an established place list is SC-B's ground)."""
    return sup(value) if draw(st.integers(0, 3)) else state_of(draw, value, other)


def verdicts(draw, keys) -> dict:
    """Pass 2's verdict on each pair control of ``keys`` (True: rejected): every one rejected but at most one (SC-B's
    class: a pair held by one unrejected control), or - one draw in three - each drawn on its own."""
    keys = list(keys)
    if draw(st.integers(0, 2)) == 0:
        return {key: draw(st.booleans()) for key in keys}
    unrejected = draw(st.sampled_from(keys + [None]))
    return {key: key != unrejected for key in keys}


@st.composite
def random_event(draw, subject):
    status = draw(st.sampled_from([sup(PERFORMED), neg(PERFORMED), unres(PERFORMED), unres(PERFORMED, State.NEGATED),
                                   doubted(PERFORMED), sup(Status.PLANNED), SILENT]))
    places = tuple(mostly(draw, draw(st.sampled_from(PLACES)), Landmark.RECTUM)
                   for _ in range(draw(st.integers(0, 2))))
    breadth = draw(st.sampled_from([None, sup(Breadth.ALL_OF_KIND), sup(Breadth.SINGLE_TARGET),
                                    sup(Breadth.LISTED_TARGETS), sup(Breadth.SEGMENT), sup(Breadth.EXCEPTIVE),
                                    unres(Breadth.SINGLE_TARGET)]))
    return event(
        kind=state_of(draw, draw(st.sampled_from(KINDS)), Kind.SNARE), status=status,
        session=state_of(draw, draw(st.sampled_from((X1, X2))), X2),
        date=draw(st.sampled_from([sup(ON), sup(EARLIER), unres(ON), SILENT, sup(ON, inherited_from=N1)])),
        performer=draw(st.sampled_from([SILENT, sup(TEAM), sup(OTHER_CLINICIAN), unres(TEAM),
                                        sup(OTHER_CLINICIAN, inherited_from=N1)])),
        person=draw(st.sampled_from([None, sup(P1), sup(P2)])),
        breadth=breadth,
        excepts=tuple(state_of(draw, draw(st.sampled_from((E1, E2, E3))), E4) for _ in range(draw(st.integers(0, 1)))),
        covers=tuple(sup(draw(st.sampled_from((E1, E2, E3)))) for _ in range(draw(st.integers(0, 1)))),
        targets=tuple(state_of(draw, draw(st.sampled_from((L1, L2, L3))), L4) for _ in range(draw(st.integers(0, 2)))),
        segment=tuple(sup(draw(st.sampled_from(PLACES[:7]))) for _ in range(draw(st.sampled_from((0, 2))))),
        lesion=state_of(draw, draw(st.sampled_from((L1, L2, L3))), L4), places=places,
        device=state_of(draw, draw(st.sampled_from((Device.COLD_SNARE, Device.SNARE, Device.HOT_SNARE))), Device.OTHER),
        purpose=state_of(draw, draw(st.sampled_from((ct.Purpose.HEMOSTASIS, ct.Purpose.MARKING))),
                         ct.Purpose.PROPHYLAXIS))


def random_factset(data) -> FactSet:
    events = {subject: data.draw(random_event(subject)) for subject in (E1, E2, E3)}
    sessions = {X1: session_of(SessionKind.COLONOSCOPY),
                X2: session_of(data.draw(st.sampled_from([sup(SessionKind.COLONOSCOPY), sup(SessionKind.EGD),
                                                          unres(SessionKind.COLONOSCOPY), sup(SessionKind.OFFICE_EM)])))}
    lesions = {lesion: lesion_of(distinct=tuple(other for other in (L1, L2, L3) if other != lesion
                                                and data.draw(st.booleans())),
                                 same=tuple(other for other in (L1, L2, L3) if other != lesion
                                            and data.draw(st.integers(0, 5)) == 0))
               for lesion in (L1, L2, L3)}
    # pair controls as claims.pair generates them from the FULL lists (9.4: a weakening leaves them as they were), both
    # directions, over every ordered pair: each object asked about the other's places none of its own is compatible
    # with (a segment's places its whole range, DECISIONS D223), and about the other's lesions when their lesions
    # differ. Pass 2's verdicts: either every control rejected but at most one (SC-B's ground: a pair held by one
    # unrejected control), or each control's verdict drawn on its own
    keys = []
    for asked, asked_facts in events.items():
        for other, other_facts in events.items():
            if asked == other:
                continue
            own, theirs = claimed_places(asked_facts), claimed_places(other_facts)
            if own and theirs:
                for place in dict.fromkeys(theirs):
                    if not any(anatomy.compatible(place, mine) for mine in own):
                        keys.append((asked, A.TARGET_PLACES, place))
            own_lesions, their_lesions = claimed_lesions(asked_facts), claimed_lesions(other_facts)
            if own_lesions and their_lesions and set(own_lesions) != set(their_lesions):
                keys.extend((asked, A.TARGET_LESION, lesion) for lesion in sorted(set(their_lesions) - set(own_lesions),
                                                                                  key=repr))
    keys = list(dict.fromkeys(keys))
    controls = verdicts(data.draw, keys)
    entries = tuple(UnlistedStatement(units=(Span(900, 940),), what=data.draw(st.sampled_from(list(ct.UnlistedWhat))),
                                      kind=data.draw(st.sampled_from([None, Kind.SNARE, Kind.BIOPSY])),
                                      session=data.draw(st.sampled_from([None, X1, X2])))
                    for _ in range(data.draw(st.integers(0, 1))))
    return build(events, sessions=sessions, lesions=lesions, controls=controls, unlisted=entries)


@st.composite
def target_pair(draw, modes=TARGET_MODES):
    """(mode, FactSet): a statement E1 in one target arm against one biopsy E2, every row but the target SAME (one
    session, the date of service, the statement naming no performer of its own and no device), each place list one
    or (mostly) two places of TARGET_PLACES (and the colon, for the act), at most one member not established; the pair
    controls made from the full lists by claims.pair()'s rule (a segment's whole range, D223), their verdicts drawn by
    ``verdicts``. The arms: single, listed (lesion L1; the act names none) and segment denials; an act of another
    performer (inherited: 4.5's controlled single target, its breadth UNRESOLVED by K1); an act-filed possible
    statement (D228). ``modes`` narrows the arms drawn."""
    mode = draw(st.sampled_from(modes))

    def members(pool, least):
        size = min(draw(st.sampled_from((2, 2, least))), len(pool))
        return draw(st.lists(st.sampled_from(pool), min_size=size, max_size=size, unique=True))

    own_places = members(TARGET_PLACES, 0 if mode == 'segment' else 1)
    ends = draw(st.lists(st.sampled_from(TARGET_PLACES), min_size=2, max_size=2, unique=True))
    named = list(own_places) + (list(contract_claims.segment_range(ends[0], ends[1])) if mode == 'segment' else [])
    # the act's places: three times in four disjoint from every place the statement names (SC-B's ground), else any
    apart = [place for place in TARGET_PLACES if all(anatomy.disjoint(place, mine) for mine in named)]
    pool = tuple(apart) if apart and draw(st.integers(0, 3)) else TARGET_PLACES + (Landmark.COLON,)
    their_places = members(pool, 1)
    weak = draw(st.sampled_from([('own', place) for place in own_places] + [('theirs', place) for place in their_places]
                                + [None] * 4))  # at most one member not established
    own = tuple(unres(place) if weak == ('own', place) else sup(place) for place in own_places)
    theirs = tuple(unres(place) if weak == ('theirs', place) else sup(place) for place in their_places)
    claimable_own = claimable(own)
    biopsy = dict(kind=sup(Kind.BIOPSY))
    if mode == 'segment':
        statement = denial(**biopsy, breadth=sup(Breadth.SEGMENT), segment=(sup(ends[0]), sup(ends[1])), places=own)
        claimable_own += tuple(contract_claims.segment_range(ends[0], ends[1]))
    elif mode in ('single', 'listed'):
        targets = (sup(L1),) if mode == 'listed' else ()
        statement = denial(**biopsy, breadth=sup(Breadth.SINGLE_TARGET if mode == 'single' else Breadth.LISTED_TARGETS),
                           targets=targets, places=own)
    elif mode == 'other performer':
        statement = act(**biopsy, performer=sup(OTHER_CLINICIAN, inherited_from=N1), lesion=SILENT, device=SILENT,
                        places=own)
    else:
        statement = act(**biopsy, status=unres(PERFORMED), lesion=SILENT, device=SILENT, places=own)
    the_act = act(**biopsy, lesion=SILENT, device=sup(Device.COLD_FORCEPS), places=theirs)
    keys = claims_pair_controls(E1, claimable_own, E2, claimable(theirs), lambda subject, place: True)
    return mode, build({E1: statement, E2: the_act}, controls=verdicts(draw, sorted(keys, key=repr)))


def weaker(found: Fact, how: str, reading) -> Fact:
    """``found`` weakened: unresolved, or a doubt added (unknown, its readings kept and one added)."""
    if how == 'unresolved':
        return dataclasses.replace(found, result=Res.UNRESOLVED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
    return dataclasses.replace(found, result=Res.UNKNOWN, options=found.options + (reading,),
                               reasons=(ct.Reason.DOUBT_UNCLEAR,))


def weaken(data, R: FactSet) -> tuple[FactSet, tuple]:
    """One of 9.4's weakenings of ``R`` and what it was: ('fact', subject, attribute, index), ('status', subject) (an
    event's status, by either draw), ('control', key), ('place', subject, index, the deleted member), or ('none',)."""
    events = {subject: dict(facts) for subject, facts in R.events.items()}
    sessions = {subject: dict(facts) for subject, facts in R.sessions.items()}
    lesions = {subject: dict(facts) for subject, facts in R.lesions.items()}
    controls = dict(R.pair_controls)
    kind = data.draw(st.sampled_from(['fact', 'control', 'place', 'status']))
    how: tuple = ('none',)
    if kind == 'control' and any(controls.values()):
        key = data.draw(st.sampled_from(sorted((key for key, value in controls.items() if value), key=repr)))
        controls[key] = False
        how = ('control', key)
    elif kind == 'place':
        candidates = [(subject, index) for subject, facts in events.items()
                      for index, _member in enumerate(facts.get(A.TARGET_PLACES, ()))]
        if candidates:
            subject, index = data.draw(st.sampled_from(candidates))
            members = list(events[subject][A.TARGET_PLACES])
            removed = members.pop(index)
            events[subject][A.TARGET_PLACES] = tuple(members)
            how = ('place', subject, index, removed)
    elif kind == 'status':
        subject = data.draw(st.sampled_from(sorted(events, key=repr)))
        status = events[subject].get(A.STATUS, (SILENT,))[0]
        if F.established(status):
            events[subject][A.STATUS] = (weaker(status, 'unresolved', None),)
            how = ('status', subject)
    else:
        targets = []
        for subject, facts in list(events.items()) + list(sessions.items()) + list(lesions.items()):
            status = R.events.get(subject, {}).get(A.STATUS, (SILENT,))[0] if subject.family is IdFamily.EVENT else None
            for attribute, members in facts.items():
                if subject.family is IdFamily.EVENT and attribute in (A.DATE_RELATION, A.PERFORMER) and \
                        status is not None and status.result is Res.SUPPORTED:
                    continue  # the which-pairs corner (question Q4)
                for index, member in enumerate(members):
                    if F.established(member):
                        targets.append((subject, attribute, index))
        if targets:
            subject, attribute, index = data.draw(st.sampled_from(sorted(targets, key=repr)))
            table = events if subject.family is IdFamily.EVENT else sessions if subject.family is IdFamily.SESSION \
                else lesions
            members = list(table[subject][attribute])
            reading = members[index].value
            members[index] = weaker(members[index], data.draw(st.sampled_from(['unresolved', 'doubt'])), reading)
            table[subject][attribute] = tuple(members)
            event_status = subject.family is IdFamily.EVENT and attribute is A.STATUS
            how = ('status', subject) if event_status else ('fact', subject, attribute, index)
    weak = build(events, sessions=sessions, lesions=lesions, controls=controls, unlisted=R.unlisted, anchors=R.anchors)
    return weak, how


def delete_a_place(data, R: FactSet) -> tuple[FactSet, tuple]:
    """9.4's deleted member: one member of one event's target place list deleted, the pair controls left as they
    were; ('place', subject, index, the deleted member)."""
    candidates = [(subject, index) for subject, facts in R.events.items()
                  for index, _member in enumerate(facts.get(A.TARGET_PLACES, ()))]
    subject, index = data.draw(st.sampled_from(candidates))
    events = {name: dict(facts) for name, facts in R.events.items()}
    members = list(events[subject][A.TARGET_PLACES])
    removed = members.pop(index)
    events[subject][A.TARGET_PLACES] = tuple(members)
    weak = build(events, sessions=dict(R.sessions), lesions=dict(R.lesions), controls=dict(R.pair_controls),
                 unlisted=R.unlisted, anchors=R.anchors)
    return weak, ('place', subject, index, removed)


def places_named(R: FactSet, subject: Id) -> set:
    """Every place ``subject``'s target place list names, in any state, and its segment's whole range."""
    facts = R.events.get(subject, {})
    found = {item.value for item in facts.get(A.TARGET_PLACES, ()) if isinstance(item.value, Landmark)}
    ends = [item.value for item in facts.get(A.SCOPE_SEGMENT, ()) if isinstance(item.value, Landmark)]
    return found | (set(P.segment_range(ends[0], ends[1])) if len(ends) == 2 else set())


# The releases P-MONO allows at the pairing level (repair r3d's NOTES), each named by the class it is checked to be.
# Since DECISIONS D238, D228's arm reads every pair control that exists, so both of its releases come through a
# control never generated, never through an unrejected one
D228_PLACE = ('D228/D238: a place deleted beside an act-filed possible statement, no pair control asking the other '
              'object about it (none generated)')
D228_STATUS = ('D228/D238: a status weakened, moving an act of another date or performer into the arm that requires no '
               'pair control, where a control the controlled reading requires was never generated')
R2D_Q2 = "r2d's Q2: a deleted member overlapped a place of the other without being compatible with it"
R2D_Q3 = "r2d's Q3: a deleted member that was not established"


def missing_required(R: FactSet, statement: Id, act_: Id) -> bool:
    """Whether a pair control the controlled single-target reading requires of the two (4.2; facts.apart_by_place and
    apart_by_lesion: each object asked about every supported place of the other, and, their supported lesions
    different, about the other's lesion) was never generated."""
    def supported(subject, attribute):
        return [item.value for item in R.events[subject].get(attribute, ()) if item.result is Res.SUPPORTED]

    keys = [(act_, A.TARGET_PLACES, place) for place in supported(statement, A.TARGET_PLACES)]
    keys += [(statement, A.TARGET_PLACES, place) for place in supported(act_, A.TARGET_PLACES)]
    mine, theirs = supported(statement, A.TARGET_LESION), supported(act_, A.TARGET_LESION)
    if mine and theirs and mine != theirs:
        keys += [(act_, A.TARGET_LESION, mine[0]), (statement, A.TARGET_LESION, theirs[0])]
    return any(key not in R.pair_controls for key in keys)


def unrejected_read(R: FactSet, statement: Id, act_: Id) -> bool:
    """Whether a pair control D228's arm reads (DECISIONS D238) is present and not rejected: a place control asked of
    either object, whatever place it asks about, or a lesion control asking one about the other's supported lesion.
    A D228 release never comes through one."""
    def supported(subject):
        return [item.value for item in R.events[subject].get(A.TARGET_LESION, ()) if item.result is Res.SUPPORTED]

    keys = [key for key in R.pair_controls if key[0] in (statement, act_) and key[1] is A.TARGET_PLACES]
    keys += [(statement, A.TARGET_LESION, lesion) for lesion in supported(act_)]
    keys += [(act_, A.TARGET_LESION, lesion) for lesion in supported(statement)]
    return any(R.pair_controls.get(key) is False for key in keys)


def named_release(R: FactSet, weak: FactSet, how: tuple, released: Id) -> frozenset | None:
    """Why ``released``, held in ``R``, is not held in ``weak`` (``how``: weaken's record): the names of the releases
    the module is allowed, one for each pair that held it - or None when any of them is released otherwise (an
    unlisted pair never releases). Each name is checked to be exactly its class: the pair INDEPENDENT on the target row
    after the weakening, the weakening on one of the pair's two events, and the class's own condition."""
    if P.unlisted_pairs(R, released):
        return None
    names = set()
    for pair in P.pairs_of(R, released):
        if pair.relation is P.Relation.INDEPENDENT:
            continue
        name = _pair_release(R, weak, how, pair.statement, released)
        if name is None:
            return None
        names.add(name)
    return frozenset(names) or None


def _pair_release(R: FactSet, weak: FactSet, how: tuple, statement: Id, act_: Id) -> str | None:
    if how[0] not in ('place', 'status') or how[1] not in (statement, act_) or not P.paired(weak, statement, act_):
        return None
    after = P.relation(weak, statement, act_)
    if after.relation is not P.Relation.INDEPENDENT or after.row is not P.Row.TARGET:
        return None
    own_arm = (not P.filed_as_statement(weak, statement) and P.possible(weak, statement)  # D228's arm, after it,
               and not unrejected_read(weak, statement, act_))  # and never through a control it reads (D238)
    if how[0] == 'status':
        if (own_arm and how[1] == statement and P.is_statement(R, statement) and not P.possible(R, statement)
                and missing_required(R, statement, act_)):
            return D228_STATUS
        return None
    _kind, subject, _index, member = how
    if not F.established(member):
        return R2D_Q3
    other = act_ if subject == statement else statement
    if own_arm and isinstance(member.value, Landmark) and (other, A.TARGET_PLACES, member.value) not in R.pair_controls:
        return D228_PLACE
    if isinstance(member.value, Landmark) and any(
            not anatomy.compatible(member.value, place) and not anatomy.disjoint(member.value, place)
            for place in places_named(R, other)):
        return R2D_Q2
    return None


# --- SC-B under 9.4's deletion, in every controlled arm (the refutation's PMONO and PT; DECISIONS D220) --------------


SC_B_POOL = (Landmark.CECUM, Landmark.HEPATIC_FLEXURE, Landmark.TRANSVERSE_COLON, Landmark.SIGMOID_COLON,
             Landmark.RECTUM)
SC_B_SEGMENT = (Landmark.SPLENIC_FLEXURE, Landmark.DESCENDING_COLON)  # its whole range is disjoint from SC_B_POOL
SC_B_SEGMENT_RANGE = tuple(contract_claims.segment_range(*SC_B_SEGMENT))


def sc_b_statement(mode: str, places: tuple) -> dict:
    """A statement of ``mode`` naming ``places`` (supported), every row but the target SAME beside sc_b's act."""
    biopsy, own = dict(kind=sup(Kind.BIOPSY)), tuple(sup(place) for place in places)
    if mode == 'single':
        return denial(**biopsy, breadth=sup(Breadth.SINGLE_TARGET), places=own)
    if mode == 'listed':
        return denial(**biopsy, breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1),), places=own)
    if mode == 'segment':
        return denial(**biopsy, breadth=sup(Breadth.SEGMENT), segment=tuple(sup(end) for end in SC_B_SEGMENT),
                      places=own)
    if mode == 'other performer':
        return act(**biopsy, performer=sup(OTHER_CLINICIAN, inherited_from=N1), lesion=SILENT, device=SILENT,
                   places=own)
    return act(**biopsy, status=unres(PERFORMED), lesion=SILENT, device=SILENT, places=own)  # 'possible' (D228)


def sc_b_act(places: tuple) -> dict:
    return act(kind=sup(Kind.BIOPSY), lesion=SILENT, device=sup(Device.COLD_FORCEPS),
               places=tuple(sup(place) for place in places))


def sc_b_lists():
    """Every (statement list, act list) of one or two SC_B_POOL places each, the two disjoint."""
    lists = [(place,) for place in SC_B_POOL] + [pair for pair in itertools.combinations(SC_B_POOL, 2)]
    return [(own, theirs) for own in lists for theirs in lists if not set(own) & set(theirs)]


class ScBTests(SimpleTestCase):
    """SC-B under 9.4's deleted-member weakening (FINAL-V2 9.4: "a deleted member of a multi-valued list (places, ...),
    the list's completeness claim and pair controls left as they were [R:SC-B]"), in the arms pairing reads itself
    (listed and segment, through facts.apart_by_controls): the refutation's PMONO class - the pair held only because
    the control asking the OTHER object about a member was not rejected - never released when that member is deleted
    (DECISIONS D220), exhaustively over sc_b_lists; the reading before D220 releases every one of them (so this is the
    class P-MONO had to see). The single arm and an act of another date or performer read facts.apart_by_place,
    repair r2d's predicate, whose own test pins the refutation's single-target case through this module
    (tests/v2/test_facts.py D220Tests); P-MONO's place-deletion property reaches the class in every arm (PropertyTests).
    Kept out of this grid on purpose: test_facts' fixture harvest runs this module's tests that are not hypothesis
    tests and asserts that every apart_by_place answer they cause equals 4.2's reading before D220 (r3d's NOTES)."""

    def test_a_deleted_members_unrejected_control_keeps_the_pair_in_the_listed_and_segment_arms(self):
        counts = {}
        for mode in ('listed', 'segment'):
            for own, theirs in sc_b_lists():
                asked = own + (SC_B_SEGMENT_RANGE if mode == 'segment' else ())
                full = claims_pair_controls(E1, asked, E2, theirs, lambda subject, place: True)
                statement, the_act = sc_b_statement(mode, own), sc_b_act(theirs)
                self.assertIs(relation_of(build({E1: statement, E2: the_act}, controls=full)).relation,
                              P.Relation.INDEPENDENT, (mode, own, theirs))
                for holder, member in [(E1, place) for place in own] + [(E2, place) for place in theirs]:
                    if len(own if holder == E1 else theirs) < 2:
                        continue  # a list of one member deleted is empty, and an empty list sets nothing apart
                    key = (E2 if holder == E1 else E1, A.TARGET_PLACES, member)  # the OTHER object asked about it
                    self.assertIn(key, full)
                    controls = {**full, key: False}
                    short_own = tuple(place for place in own if not (holder == E1 and place is member))
                    short_theirs = tuple(place for place in theirs if not (holder == E2 and place is member))
                    before = build({E1: statement, E2: the_act}, controls=controls)
                    after = build({E1: sc_b_statement(mode, short_own), E2: sc_b_act(short_theirs)},
                                  controls=controls)
                    with self.subTest(mode=mode, statement=own, act=theirs, deleted=(holder, member)):
                        self.assertEqual(relation_of(before).result(P.Row.TARGET), UNRESOLVED)
                        self.assertIsNot(relation_of(before).relation, P.Relation.INDEPENDENT)
                        self.assertEqual(relation_of(after).result(P.Row.TARGET), UNRESOLVED)
                        self.assertIsNot(relation_of(after).relation, P.Relation.INDEPENDENT)
                        with mock.patch.object(F, 'apart_by_controls', before_d220):
                            self.assertIs(relation_of(after).relation, P.Relation.INDEPENDENT)
                    counts[mode] = counts.get(mode, 0) + 1
        self.assertEqual(counts, {'listed': 240, 'segment': 240})

    def test_an_act_filed_possible_statement_reads_the_controls_that_exist_before_and_after(self):
        # DECISIONS D228 as D238 rules it, on the same grid in the arm that requires no pair control: with claims.pair()'s
        # controls all rejected, or with none generated (D211), set apart before and after a deletion; with them all not
        # rejected, or with only the one asking the OTHER object about a member not rejected (SC-B's class, the deleted
        # member's control), held before and after - an unrejected control holds there too, deleted member or not
        checked = 0
        for own, theirs in sc_b_lists():
            for answer, expected in ((True, P.Relation.INDEPENDENT), (None, P.Relation.INDEPENDENT),
                                     (False, P.Relation.UNRESOLVED)):
                full = {} if answer is None else claims_pair_controls(E1, own, E2, theirs, lambda s, p, a=answer: a)
                for statement_places, act_places in ((own, theirs), (own[:1], theirs[:1])):
                    R = build({E1: sc_b_statement('possible', statement_places), E2: sc_b_act(act_places)},
                              controls=full)
                    with self.subTest(statement=statement_places, act=act_places, controls=answer):
                        self.assertIs(relation_of(R).relation, expected)
                    checked += 1
            all_rejected = claims_pair_controls(E1, own, E2, theirs, lambda subject, place: True)
            for holder, member in [(E1, place) for place in own] + [(E2, place) for place in theirs]:
                key = (E2 if holder == E1 else E1, A.TARGET_PLACES, member)
                controls = {**all_rejected, key: False}
                short_own = tuple(place for place in own if not (holder == E1 and place is member)) or own
                short_theirs = tuple(place for place in theirs if not (holder == E2 and place is member)) or theirs
                for statement_places, act_places in ((own, theirs), (short_own, short_theirs)):
                    R = build({E1: sc_b_statement('possible', statement_places), E2: sc_b_act(act_places)},
                              controls=controls)
                    with self.subTest(statement=statement_places, act=act_places, unrejected=key):
                        self.assertIs(relation_of(R).relation, P.Relation.UNRESOLVED)
                    checked += 1
        self.assertEqual(checked, 2 * 3 * len(sc_b_lists())
                         + 2 * sum(len(own) + len(theirs) for own, theirs in sc_b_lists()))

    def test_the_named_releases_are_real_and_narrow(self):
        # each named release (named_release) on its minimal input, and a release outside them is refused: the
        # refutation's single-target PMONO case under the reading before D220 names none
        R = build({E1: act(kind=sup(Kind.BIOPSY), status=unres(PERFORMED), lesion=SILENT, device=SILENT,
                           places=(sup(Landmark.SIGMOID_COLON), sup(Landmark.TRANSVERSE_COLON))),
                   E2: sc_b_act((Landmark.TRANSVERSE_COLON,))},
                  controls={(E2, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True})
        weak = build({E1: {**R.events[E1], A.TARGET_PLACES: (sup(Landmark.SIGMOID_COLON),)}, E2: R.events[E2]},
                     controls=R.pair_controls)
        how = ('place', E1, 1, sup(Landmark.TRANSVERSE_COLON))
        self.assertEqual(held(R) - held(weak), {E2})
        self.assertEqual(named_release(R, weak, how, E2), frozenset({D228_PLACE}))
        # ... and since D238 never where a control asks the other object about the deleted place: rejected, it is
        # r2d's Q2 class when the place overlapped without being compatible (an anastomosis), and not rejected, nothing
        # is released at all
        R = build({E1: act(kind=sup(Kind.BIOPSY), status=unres(PERFORMED), lesion=SILENT, device=SILENT,
                           places=(sup(Landmark.RECTUM), sup(Landmark.ANASTOMOSIS))),
                   E2: sc_b_act((Landmark.SIGMOID_COLON,))},
                  controls=claims_pair_controls(E1, (Landmark.RECTUM, Landmark.ANASTOMOSIS), E2,
                                                (Landmark.SIGMOID_COLON,), lambda subject, place: True))
        self.assertIn((E2, A.TARGET_PLACES, Landmark.ANASTOMOSIS), R.pair_controls)
        weak = build({E1: {**R.events[E1], A.TARGET_PLACES: (sup(Landmark.RECTUM),)}, E2: R.events[E2]},
                     controls=R.pair_controls)
        how = ('place', E1, 1, sup(Landmark.ANASTOMOSIS))
        self.assertEqual(held(R) - held(weak), {E2})
        self.assertEqual(named_release(R, weak, how, E2), frozenset({R2D_Q2}))
        unrejected = {**R.pair_controls, (E2, A.TARGET_PLACES, Landmark.ANASTOMOSIS): False}
        R, weak = (build(dict(found.events), controls=unrejected) for found in (R, weak))
        self.assertEqual(held(R) - held(weak), set())
        # D228's status weakening: an act of another performer, held because "This act was done in the rectum." asked of
        # the team's biopsy was never generated (D211: two biopsies), weakened into a possible statement
        other = sc_b_statement('other performer', (Landmark.RECTUM,))
        controls = {(E1, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True}
        R = build({E1: other, E2: sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = build({E1: {**other, A.STATUS: (unres(PERFORMED),)}, E2: R.events[E2]}, controls=controls)
        self.assertEqual(held(R) - held(weak), {E2})
        self.assertEqual(named_release(R, weak, ('status', E1), E2), frozenset({D228_STATUS}))
        self.assertIsNone(named_release(R, weak, ('fact', E1, A.KIND, 0), E2))
        # ... and since D238 never where that control exists and was not rejected (round 1's Q1 (c)): nothing released
        controls = {**controls, (E2, A.TARGET_PLACES, Landmark.RECTUM): False}
        R = build({E1: other, E2: sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = build({E1: {**other, A.STATUS: (unres(PERFORMED),)}, E2: R.events[E2]}, controls=controls)
        self.assertEqual(held(R) - held(weak), set())

        # a release through a control the arm reads is refused by every name: under round 1's reading of D228's arm (no
        # control read, patched in as the positive control), Q1 (c) as stated releases, and named_release names nothing
        def round_1(R_, p, own, theirs):
            if own.lesions is not None and theirs.lesions is not None and len(own.lesions) == len(theirs.lesions) == 1:
                (mine,), (other_lesion,) = own.lesions, theirs.lesions
                if (mine != other_lesion and P._distinct(R_, mine, other_lesion)
                        and not P._possibly_same(R_, mine, other_lesion)):
                    return True
            return P._disjoint(own.places, theirs.places)

        with mock.patch.object(P, '_apart_by_own_target', round_1):
            self.assertEqual(held(R) - held(weak), {E2})
            self.assertTrue(unrejected_read(weak, E1, E2))
            self.assertIsNone(named_release(R, weak, ('status', E1), E2))
        # the name checks its own class: with every control the controlled reading requires present, a pair set apart
        # after the weakening is never named D228_STATUS
        controls = {**controls, (E2, A.TARGET_PLACES, Landmark.RECTUM): True}
        R = build({E1: other, E2: sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = build({E1: {**other, A.STATUS: (unres(PERFORMED),)}, E2: R.events[E2]}, controls=controls)
        self.assertFalse(missing_required(R, E1, E2))
        self.assertIsNone(_pair_release(R, weak, ('status', E1), E1, E2))
        # r2d's Q3: a deleted member that was not established, every control rejected
        statement = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SINGLE_TARGET),
                           places=(sup(Landmark.RECTUM), unres(Landmark.CECUM)))
        controls = claims_pair_controls(E1, (Landmark.RECTUM, Landmark.CECUM), E2, (Landmark.SIGMOID_COLON,),
                                        lambda subject, place: True)
        R = build({E1: statement, E2: sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = build({E1: {**statement, A.TARGET_PLACES: (sup(Landmark.RECTUM),)}, E2: R.events[E2]}, controls=controls)
        self.assertEqual(held(R) - held(weak), {E2})
        self.assertEqual(named_release(R, weak, ('place', E1, 1, unres(Landmark.CECUM)), E2), frozenset({R2D_Q3}))
        # r2d's Q2: a deleted anastomosis member (never disjoint, never compatible with the sigmoid colon)
        statement = denial(kind=sup(Kind.BIOPSY), breadth=sup(Breadth.SINGLE_TARGET), places=(sup(Landmark.RECTUM),))
        the_act = sc_b_act((Landmark.SIGMOID_COLON, Landmark.ANASTOMOSIS))
        controls = claims_pair_controls(E1, (Landmark.RECTUM,), E2, (Landmark.SIGMOID_COLON, Landmark.ANASTOMOSIS),
                                        lambda subject, place: True)
        R = build({E1: statement, E2: the_act}, controls=controls)
        weak = build({E1: statement, E2: sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        self.assertEqual(held(R) - held(weak), {E2})
        self.assertEqual(named_release(R, weak, ('place', E2, 1, sup(Landmark.ANASTOMOSIS)), E2), frozenset({R2D_Q2}))
        # the refutation's listed-targets PMONO release, under the reading before D220: no named release covers it
        listed = dict(breadth=sup(Breadth.LISTED_TARGETS), targets=(sup(L1), sup(L2)))
        controls = {(E2, A.TARGET_PLACES, Landmark.SIGMOID_COLON): True, (E2, A.TARGET_PLACES, Landmark.RECTUM): False,
                    (E1, A.TARGET_PLACES, Landmark.TRANSVERSE_COLON): True}
        the_act = act(lesion=sup(L3), places=(sup(Landmark.TRANSVERSE_COLON),))
        R = build({E1: denial(**listed, places=(sup(Landmark.SIGMOID_COLON), sup(Landmark.RECTUM))), E2: the_act},
                  controls=controls)
        weak = build({E1: denial(**listed, places=(sup(Landmark.SIGMOID_COLON),)), E2: the_act}, controls=controls)
        self.assertEqual(held(R) - held(weak), set())
        with mock.patch.object(F, 'apart_by_controls', before_d220):
            self.assertEqual(held(R) - held(weak), {E2})
            self.assertIsNone(named_release(R, weak, ('place', E1, 1, sup(Landmark.RECTUM)), E2))



# --- the tables --------------------------------------------------------------------------------------------------------


class TableTests(SimpleTestCase):
    def test_device_contains_equals_v1s_by_value(self):
        # v1's relations.DEVICE_CONTAINS (retired, 5.0), read here only: engine/ never imports it
        from studio.interpretation import relations as v1_relations
        ported = {device.value: frozenset(inner.value for inner in contained)
                  for device, contained in P.DEVICE_CONTAINS.items()}
        self.assertEqual(ported, {key: frozenset(value) for key, value in v1_relations.DEVICE_CONTAINS.items()})

    def test_the_segment_range_equals_contract_claims_by_value(self):
        # one rule, two places (the engine imports no claim builder); request R2 moves it into engine/anatomy.py
        self.assertEqual(P.TRACT_ORDER, contract_claims.TRACT_ORDER)
        for first in Landmark:
            for last in Landmark:
                self.assertEqual(P.segment_range(first, last), frozenset(contract_claims.segment_range(first, last)),
                                 (first, last))

    def test_the_modules_collections_hold_enumeration_members_only(self):
        for name in ('DEVICE_CONTAINS', 'OTHER_DATES', 'OTHER_PERFORMERS', 'TARGETED', 'UNTARGETED', 'POSITIVE',
                     'TRACT_ORDER'):
            table = getattr(P, name)
            values = list(table) + [item for value in getattr(table, 'values', lambda: [])() for item in value]
            with self.subTest(table=name):
                self.assertTrue(values)
                self.assertTrue(all(isinstance(item, enum.Enum) for item in values), values)


# --- the boundary (5.7 measures 4 and 5) -------------------------------------------------------------------------------


class BoundaryTests(SimpleTestCase):
    def test_measure_4_holds_over_the_module(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_a_planted_word_reader_turns_measure_4_red(self):
        source = MODULE.read_text(encoding='utf-8')
        for plant, found in (('from studio.interpretation import lexicon\n', 'imports studio.interpretation.lexicon'),
                             ("NEGATORS = ('no', 'not')\n", 'a module-level word list'),
                             ("def _x(f):\n    return f.words\n", 'reads .words')):
            with self.subTest(plant=plant):
                self.assertTrue(any(found in item for item in measure_4(source + plant, engine=True)))

    def test_the_module_imports_no_retired_module_text_module_or_claim_builder(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.pairing\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=120, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = set(result.stdout.strip().split(','))
        self.assertIn('studio.interpretation.engine.pairing', loaded)
        retired = {'prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations',
                   'mapping', 'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess'}
        self.assertFalse({f'studio.interpretation.{name}' for name in retired} & loaded, loaded)
        text = {'segment', 'geometry', 'fold', 'date_literals', 'claims', 'extract_read', 'extract_prompt',
                'appraise_prompt', 'appraise_read'}
        self.assertFalse({f'studio.interpretation.contract.{name}' for name in text} & loaded, loaded)
        self.assertFalse({name for name in loaded if name.startswith('studio.gi')}, loaded)

    def test_mypy_strict_passes_and_refuses_a_string_operation_on_a_pair(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=600, cwd=APP)

        result = mypy('studio/interpretation/engine/pairing.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 1 source file', result.stdout)
        probe = mypy('-c', 'from studio.interpretation.engine.pairing import Pair\n'
                           'def probe(pair: Pair) -> bool:\n'
                           '    return pair.statement.startswith("E")\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)

    def test_a_pair_holds_no_string(self):
        hints = typing.get_type_hints(P.Pair)
        self.assertEqual(set(hints), {'statement', 'act', 'relation', 'row', 'rows', 'claimed', 'possible', 'kinds',
                                      'spans'})

        def leaves(hint):
            arguments = typing.get_args(hint)
            return [leaf for argument in arguments for leaf in leaves(argument)] if arguments else [hint]

        found = {leaf for hint in hints.values() for leaf in leaves(hint)}
        self.assertNotIn(str, found)
        self.assertLessEqual(found, {Id, P.Relation, P.Row, P.RowResult, bool, Kind, Span, type(None), Ellipsis},
                             found)
        pair = relation_of(build({E1: denial(), E2: act()}))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            pair.relation = P.Relation.INDEPENDENT  # type: ignore[misc]
