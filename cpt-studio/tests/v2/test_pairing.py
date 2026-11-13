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
  generation - the two ends contract/claims.py asks today, or the whole range of the step's request R4);
- "'claimed' turns apart into UNRESOLVED": RelationTests, for every row that can prove independence; and a claimed pair
  no row sets apart asks its first unresolved row's fact, as 4.5 step 2 says (round 2, the refutation's F2);
- "mypy --strict on engine/pairing.py": BoundaryTests, with a positive control.
Also: P-MONO at the pairing level (a weakening never releases a held act; the which-pairs corner the step's NOTES
record as question Q4 is left out and named), and its same_as corner (round 2: a lesion possibly joined to the act's
by same_as is never set apart by lesion, in any mode); the unlisted pairs of 3.2.6 rule 4; each hold's item at its
RANK row, every one of them among requirements.RULES' clean-row asks; DEVICE_CONTAINS equal to v1's by value; the
segment range equal to contract/claims.py's; 5.7 measure 4 over the module; no retired module, text module or claim
builder imported.
"""
from __future__ import annotations

import dataclasses
import enum
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
        # the two ends' controls only (what contract/claims.py asks today): held, however they were answered
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

    def test_a_short_list_beside_a_segment_never_releases_under_either_generation(self):
        # SC-B's short list (P-MONO's list-member deletion, pair controls left as they were) over a grid of segments
        # and act lists, a faithful pass 2 answering each control by the act's true places: deleting a member of a list
        # that reaches into the range never sets the pair apart, whether the controls are asked of the segment's two
        # ends (contract/claims.py today) or of its whole range (the step's request R4); and under R4 a list truly
        # outside the range is set apart (the reading does not hold every segment forever)
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

    def test_an_act_filed_statement_reads_its_own_target_through_facts_predicates(self):
        # 4.5 [R:HO-3]: its own place and lesion facts stand for a single target; the pair controls of 4.2 are read as
        # for any target (the step's question Q2: the reading kept for P-MONO and SC-B)
        both = controls_both_ways(E1, E2, statement_places=(Landmark.RECTUM,), act_places=(Landmark.SIGMOID_COLON,))
        possible = act(status=unres(PERFORMED), lesion=SILENT, places=(sup(Landmark.RECTUM),))
        R = build({E1: possible, E2: act(lesion=SILENT)}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)
        R = build({E1: possible, E2: act(lesion=SILENT)})
        self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        # a denial misfiled as an act gets its act-phrased place claims rejected too: nothing sets it apart
        R = build({E1: act(status=unres(PERFORMED), lesion=SILENT, places=(unres(Landmark.RECTUM),)),
                   E2: act(lesion=SILENT)}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), UNRESOLVED)
        # an act established as of another performer reads its own target the same way
        other = act(performer=sup(OTHER_CLINICIAN, inherited_from=N1), lesion=SILENT, places=(sup(Landmark.RECTUM),))
        R = build({E1: other, E2: act(lesion=SILENT)}, controls=both)
        self.assertEqual(row_of(R, P.Row.TARGET), INDEPENDENT)

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
        self.assertEqual(P.item(pair), rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE))


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
        facts not established (or deletes a list member) or ONE of its pair controls not rejected (or not generated)."""
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
                controls = {**controls, what: False}
            else:
                controls = {key: value for key, value in controls.items() if key != what}
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
        established control to not rejected, a place list member deleted (its pair controls left as they were), an
        event's established status to unresolved. An act held by a pair or an unlisted pair before stays held. Left
        out, and named in the step's NOTES (question Q4): weakening the date relation or performer of an event whose
        status is established, which can take it out of 4.5's "which pairs" (established as another) altogether."""
        R = random_factset(data)
        before = held(R)
        weak = weaken(data, R)
        after = held(weak)
        self.assertLessEqual(before, after, (before, after))

    def test_the_mono_generator_is_not_vacuous(self):
        # measured when the step was built: 310 of P-MONO's 400 examples start with a held act; a generator that
        # stopped producing holds would make P-MONO pass vacuously, so the share is pinned well under that
        counts = {'examples': 0, 'held': 0}

        @hypothesis.settings(**{**SETTINGS, 'max_examples': 100})
        @hypothesis.given(st.data())
        def sample(data):
            counts['examples'] += 1
            counts['held'] += bool(held(random_factset(data)))

        sample()
        self.assertGreaterEqual(counts['examples'], 100)
        self.assertGreater(counts['held'], 0.4 * counts['examples'])


KINDS = (Kind.SNARE, Kind.EMR, Kind.REMOVAL, Kind.BIOPSY, Kind.INJECTION, Kind.TATTOO, Kind.CLIP,
         Kind.BLEEDING_CONTROL)
PLACES = (Landmark.RECTUM, Landmark.SIGMOID_COLON, Landmark.CECUM, Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE,
          Landmark.COLON, Landmark.ANASTOMOSIS)


def held(R: FactSet) -> set:
    return {subject for subject in R.events
            if any(pair.relation is not P.Relation.INDEPENDENT for pair in P.pairs_of(R, subject))
            or P.unlisted_pairs(R, subject)}


def claimed_places(facts) -> list:
    """claims.places: the members claimed with a supported state, and a segment's two places."""
    found = [item.value for item in facts.get(A.TARGET_PLACES, ()) if item.state is State.SUPPORTED]
    return found + [item.value for item in facts.get(A.SCOPE_SEGMENT, ()) if item.state is State.SUPPORTED]


def claimed_lesions(facts) -> list:
    found = [item.value for item in facts.get(A.TARGET_LESION, ()) if item.state is State.SUPPORTED]
    return found + [item.value for item in facts.get(A.SCOPE_TARGETS, ()) if item.state is State.SUPPORTED]


@st.composite
def random_event(draw, subject):
    status = draw(st.sampled_from([sup(PERFORMED), neg(PERFORMED), unres(PERFORMED), unres(PERFORMED, State.NEGATED),
                                   doubted(PERFORMED), sup(Status.PLANNED), SILENT]))
    places = tuple(state_of(draw, draw(st.sampled_from(PLACES)), Landmark.RECTUM)
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
        segment=tuple(sup(draw(st.sampled_from(PLACES[:5]))) for _ in range(draw(st.sampled_from((0, 2))))),
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
    # pair controls as claims.pair generates them, both directions, over every ordered pair: each object asked about the
    # other's places none of its own is compatible with, and about the other's lesions when their lesions differ
    controls = {}
    for asked, asked_facts in events.items():
        for other, other_facts in events.items():
            if asked == other:
                continue
            own, theirs = claimed_places(asked_facts), claimed_places(other_facts)
            if own and theirs:
                for place in dict.fromkeys(theirs):
                    if not any(anatomy.compatible(place, mine) for mine in own):
                        controls[(asked, A.TARGET_PLACES, place)] = data.draw(st.booleans())
            own_lesions, their_lesions = claimed_lesions(asked_facts), claimed_lesions(other_facts)
            if own_lesions and their_lesions and set(own_lesions) != set(their_lesions):
                for lesion in set(their_lesions) - set(own_lesions):
                    controls[(asked, A.TARGET_LESION, lesion)] = data.draw(st.booleans())
    entries = tuple(UnlistedStatement(units=(Span(900, 940),), what=data.draw(st.sampled_from(list(ct.UnlistedWhat))),
                                      kind=data.draw(st.sampled_from([None, Kind.SNARE, Kind.BIOPSY])),
                                      session=data.draw(st.sampled_from([None, X1, X2])))
                    for _ in range(data.draw(st.integers(0, 1))))
    return build(events, sessions=sessions, lesions=lesions, controls=controls, unlisted=entries)


def weaker(found: Fact, how: str, reading) -> Fact:
    """``found`` weakened: unresolved, or a doubt added (unknown, its readings kept and one added)."""
    if how == 'unresolved':
        return dataclasses.replace(found, result=Res.UNRESOLVED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
    return dataclasses.replace(found, result=Res.UNKNOWN, options=found.options + (reading,),
                               reasons=(ct.Reason.DOUBT_UNCLEAR,))


def weaken(data, R: FactSet) -> FactSet:
    events = {subject: dict(facts) for subject, facts in R.events.items()}
    sessions = {subject: dict(facts) for subject, facts in R.sessions.items()}
    lesions = {subject: dict(facts) for subject, facts in R.lesions.items()}
    controls = dict(R.pair_controls)
    how = data.draw(st.sampled_from(['fact', 'control', 'place', 'status']))
    if how == 'control' and any(controls.values()):
        key = data.draw(st.sampled_from(sorted((key for key, value in controls.items() if value), key=repr)))
        controls[key] = False
    elif how == 'place':
        candidates = [(subject, index) for subject, facts in events.items()
                      for index, _member in enumerate(facts.get(A.TARGET_PLACES, ()))]
        if candidates:
            subject, index = data.draw(st.sampled_from(candidates))
            members = list(events[subject][A.TARGET_PLACES])
            del members[index]
            events[subject][A.TARGET_PLACES] = tuple(members)
    elif how == 'status':
        subject = data.draw(st.sampled_from(sorted(events, key=repr)))
        status = events[subject].get(A.STATUS, (SILENT,))[0]
        if F.established(status):
            events[subject][A.STATUS] = (weaker(status, 'unresolved', None),)
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
    return build(events, sessions=sessions, lesions=lesions, controls=controls, unlisted=R.unlisted, anchors=R.anchors)


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
