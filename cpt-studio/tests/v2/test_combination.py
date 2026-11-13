"""The combination rules of design v2 (docs/gemini-migration/FINAL-V2.md 4.7, 4.1, 4.8, 4.9 and 4.13; step 4d of its
8.1), TEXT-ONLY and SYNTHETIC: every FactSet here is hand-built from engine/types' records (enumeration members, ids,
results and integer spans: the engine's whole input, 4.1), and step 4b's reportable and doubted acts are written as the
SessionActs records engine/combination.py reads. No document is read, no provider is called, nothing touches the
network. The sentences quoted in comments are the design's and v1's tests' own; the engine never reads them.

The done-when of 8.1 step 4d, each proved here:
- "v1's combination tests re-expressed": every test of tests/test_interpretation_combination.py has its counterpart
  below, in a class of the same name (Base, BaseWithin, Competition, SameDayEM, ModifierReview, CopiesPinned), at the
  level the combination owns - the relation and the hold, with its fact key, rank, kind and cause; v1's sentences are
  step 3c's wording and v1's run() is step 5a's assembly, so neither is re-asserted here (the step's NOTES map each
  test);
- "a held code never releases a rival": HeldCodesKeepTheirClaims (D163's, D167's, D74's and D104's shapes, each held
  code competing with the READY rival on the act its hold rests on; the controls whose act is no doubt), and the
  P-MONO properties in Monotone (random FactSets, random weakenings: the claims and the competition never shrink, a
  whole stays a whole; the same-day rule's own inputs - statements, another visit, kinds gaining an E/M or examination
  reading, devices, classes and sessions weakened by any reading of their domain - never release a held E/M code; and
  combine never releases a held member);
- "mypy --strict on the module": BoundaryTests, with a positive control.
Also: 9.3's combination cases - competing with D163 and D167, C-3 with a separate same-day session and with an unlisted
act, the separate statement negated, the modifier review; D118's one stricture and the pair controls (SC-B); R4's
filter, and P6's place lists (no listed place removes a claim: D29's site fit is not read); DECISIONS D191
(SAME_DAY_KINDS read from FAMILY_KINDS) and the arbiter's hand-off 1e:R3 (equal to the catalogue entries' kinds,
BUNDLED_KINDS and UNSUPPORTED_KINDS included); the attributes the rules read are CLAIMED's (P-READSET); P-DET; 5.7
measure 4 over the module; no retired module imported. v1's constants are computed HERE from v1's own modules (retired:
5.0), read only, as tests/v2/test_catalogue_parity.py does.

Round 2 (the refutation build-v2/w34/refute-4d-r1): F1 (an undatable act holds an E/M code until an ESTABLISHED
procedure day moots it; a digital examination left open is a possible procedure, never a done one), F2 (beside only an
unsupported code, base_included is a QUESTION), F3 (a session is done by its examination when it has one), F4
(visit_basis ported), F5 (a session the coding does not list is refused), T1 (the same-day rule's fail-closed arms
pinned, and its own P-MONO property), T2 (D118's possibly-shared lesion and R4's classless device pinned); and two found
while repairing: another visit lends its statement only with its performer established as the team, and a session
negation left open may be in any session.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

# v1, read only for the parity proofs (computed here); engine/ never imports these
from studio.interpretation import combination as v1_combination, mapping as v1_mapping
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import combination as C
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import Anchor, Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span
from studio.interpretation.engine.types import UnlistedStatement
from studio.validation import checks as v1_checks, engine as v1_engine
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'combination.py'

A, Res, State = ct.Attribute, ct.Result, ct.FactState
Kind, Status, SessionKind, Device, Landmark = ct.Kind, ct.Status, ct.SessionKind, ct.Device, ct.Landmark
ON, EARLIER = ct.DateRelation.ON_DATE_OF_SERVICE, ct.DateRelation.EARLIER_DATE
TEAM, OTHER_CLINICIAN = ct.Performer.DOCUMENTING_TEAM, ct.Performer.OTHER_CLINICIAN
PERFORMED, PLANNED = Status.PERFORMED, Status.PLANNED
CLINICIAN, NURSING = ct.Owner.DOCUMENTING_CLINICIAN, ct.Owner.NURSING
THIS, SEPARATE = ct.EncounterRelation.THIS_ENCOUNTER, ct.EncounterRelation.SEPARATE_ENCOUNTER
STATED = ct.Separate.STATED

E0, E1, E2, E3, E4, E5, E6, E7, E8, E9 = (Id(IdFamily.EVENT, n) for n in range(10))
X0, X1, X2, X3, X4 = (Id(IdFamily.SESSION, n) for n in range(5))
L1, L2, L3 = (Id(IdFamily.LESION, n) for n in range(1, 4))


# --- building settled facts -------------------------------------------------------------------------------------------


def fact(result: ct.Result, value, state, *, options=(), reasons=(), spans=()) -> Fact:
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


def doubted(value, *readings, **kw) -> Fact:
    """A doubt (3.3 row 2): unknown, the claimed value and the doubt's readings kept."""
    return fact(Res.UNKNOWN, value, State.SUPPORTED, options=readings, reasons=(ct.Reason.DOUBT_UNCLEAR,), **kw)


SILENT = F.SILENT

EVENT_ATTRIBUTES = {
    'kind': A.KIND, 'status': A.STATUS, 'session': A.SESSION, 'date': A.DATE_RELATION, 'performer': A.PERFORMER,
    'entry': A.ENTRY, 'lesion': A.TARGET_LESION, 'places': A.TARGET_PLACES, 'device': A.TECHNIQUE_DEVICE,
    'purpose': A.PURPOSE, 'other_class': A.OTHER_CLASS, 'separate': A.VISIT_SEPARATELY_IDENTIFIABLE,
    'basis': A.VISIT_BASIS,
}
SESSION_ATTRIBUTES = {'kind': A.KIND, 'tract': A.TRACT, 'encounter': A.ENCOUNTER, 'part_of': A.PART_OF_SESSION}
MANY = {'places'}


def _facts(names: dict, attributes: dict) -> dict:
    out = {}
    for name, value in attributes.items():
        if value is None:
            continue
        out[names[name]] = tuple(value) if name in MANY else (value,)
    return out


def event(**attributes) -> dict:
    """An event's facts by attribute; ``places`` a tuple of member facts; an attribute given as None is left out (it
    reads as SILENT)."""
    return _facts(EVENT_ATTRIBUTES, attributes)


def act(kind, session=X1, **over) -> dict:
    """A done act (4.3 rows 1-5 supported): ``kind`` (or the kind Fact given) in ``session`` (or the session Fact
    given), performed today by the documenting team, told in the documenting clinician's entry."""
    placed = session if isinstance(session, Fact) else sup(session) if session is not None else None
    base = dict(kind=kind if isinstance(kind, Fact) else sup(kind), status=sup(PERFORMED), session=placed, date=sup(ON),
                performer=sup(TEAM), entry=sup(CLINICIAN))
    base.update(over)
    return event(**base)


def session_of(kind, **over) -> dict:
    """A session's facts: its kind supported (or the Fact given), and ``tract``, ``encounter``, ``part_of``."""
    base = dict(kind=kind if isinstance(kind, Fact) else sup(kind))
    base.update(over)
    return _facts(SESSION_ATTRIBUTES, base)


def lesion_of(places=(), distinct=(), same=()) -> dict:
    return {A.PLACES: tuple(sup(place) for place in places), A.DISTINCT_FROM: tuple(sup(item) for item in distinct),
            A.SAME_AS: tuple(sup(item) for item in same)}


def build(events: dict, sessions: dict, *, lesions=None, unlisted=(), controls=None) -> FactSet:
    """A settled FactSet: ``events`` in order, each with an anchor unit of its own (E<n> at 100n)."""
    anchors = {subject: Anchor(units=(Span(100 * subject.number, 100 * subject.number + 40),), kind_words=None,
                               status_words=None) for subject in events}
    return FactSet(encounter={}, people={}, sections={}, sessions=sessions, anatomy={}, lesions=lesions or {},
                   events=events, anchors=anchors, unlisted=tuple(unlisted), pair_controls=controls or {},
                   completeness={})


def member(key: str, code: str, session=X1, supporting=(), **kw) -> C.Member:
    """A counted code, routed to its family as the catalogue routes it."""
    return C.Member(key=key, code=code, family=catalogue.family_for_code(code), session=session,
                    supporting=tuple(supporting), **kw)


def span_of(*events: Id) -> tuple:
    return tuple(sorted(Span(100 * e.number, 100 * e.number + 40) for e in events))


def keys(held: tuple) -> list:
    return [item.fact for item in held]


COLONOSCOPY = {X1: session_of(SessionKind.COLONOSCOPY)}
EXAM_ONLY = tuple(sorted(str(code) for code, profile in catalogue.CODES.items()
                         if profile.family is SessionKind.EUS and profile.covers == (Kind.EXAMINATION,)))


# --- base (FINAL 7.9, D119, D177(1), 3.2.6 rule 3) --------------------------------------------------------------------


class Base(SimpleTestCase):
    """v1's Base class re-expressed. ``coding`` stands for step 4b's event_coding@2: each session's reportable and
    doubted acts, as 4.7 defines them, written here as SessionActs."""

    def colonoscopy(self, *extra, polyp=None) -> FactSet:
        events = {E1: act(Kind.EXAMINATION),
                  E2: polyp if polyp is not None else act(Kind.SNARE, lesion=sup(L1),
                                                          places=(sup(Landmark.SIGMOID_COLON),),
                                                          device=sup(Device.COLD_SNARE))}
        for subject, facts in extra:
            events[subject] = facts
        return build(events, COLONOSCOPY)

    def test_a_base_code_beside_a_code_of_its_session(self):
        R = self.colonoscopy()
        members = [member('sel:0', '45378', supporting=(E1,)), member('sel:1', '45385', supporting=(E2,))]
        found = C.base_included(members, {X1: C.SessionActs(reportable=(E2,))}, R)
        self.assertEqual(len(found), 1)
        base = found[0]
        self.assertEqual((base.key, base.code, base.session, base.beside, base.others, base.named_codes),
                         ('sel:0', '45378', X1, ('45385',), ('45385',), ('45385',)))
        held = C.base_hold(base, R)
        self.assertEqual((held.fact, held.rank, held.kind, held.cause, held.subject, held.attribute, held.result),
                         ('base_included', 21, ItemKind.EXPLANATION, C.BASE_CAUSE, X1, None, None))
        self.assertEqual(held.spans, span_of(E2))
        # the key-bound fact of 4.8, at its RANK row
        self.assertIn(rq.FactKey.BASE_INCLUDED, rq.KEY_BOUND)
        self.assertEqual(rq.RANK[rq.Rank.BASE_INCLUDED], (rq.FactKey.BASE_INCLUDED,))

    def test_a_base_code_beside_a_reportable_act_no_code_accounts_for(self):
        R = self.colonoscopy()
        found = C.base_included([member('sel:0', '45378', supporting=(E1,))], {X1: C.SessionActs(reportable=(E2,))}, R)
        self.assertEqual([(b.named_codes, b.reportable, b.doubted, b.established) for b in found],
                         [((), (E2,), (), True)])
        self.assertEqual(C.base_hold(found[0], R).kind, ItemKind.EXPLANATION)

    def test_a_base_code_beside_a_doubted_act(self):
        """Base rule (c): an act stated in doubt may have been done, and then the base code is included in it - a doubt,
        so a QUESTION (4.8), never READY."""
        R = self.colonoscopy((E3, act(Kind.BIOPSY, status=doubted(PERFORMED))),
                             polyp=act(Kind.OTHER))
        found = C.base_included([member('sel:0', '45378', supporting=(E1,))], {X1: C.SessionActs(doubted=(E3,))}, R)
        self.assertEqual([(b.reportable, b.doubted, b.established) for b in found], [((), (E3,), False)])
        held = C.base_hold(found[0], R)
        self.assertEqual((held.kind, held.spans), (ItemKind.QUESTION, span_of(E3)))

    def test_a_base_code_alone_is_ready(self):
        R = self.colonoscopy(polyp=act(Kind.OTHER))
        members = [member('sel:0', '45378', supporting=(E1,))]
        self.assertEqual(C.base_included(members, {X1: C.SessionActs()}, R), ())
        self.assertEqual(C.combine(members, {X1: C.SessionActs()}, R).held['sel:0'], ())

    def eus(self, fna=True) -> FactSet:
        events = {E2: act(Kind.EXAMINATION, X2)}
        if fna:
            events[E3] = act(Kind.FNA, X2, places=(sup(Landmark.PANCREAS),))
        return build(events, {X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))})

    def test_an_examination_only_eus_code_beside_an_fna_code_of_its_session_is_held(self):
        """Base rule (a) over an examination-only EUS code: beside the FNA code of its session it is held, so the EUS
        examination is never accounted for twice; the FNA code is no base code. Each origin (D40: origin is never
        read)."""
        R = self.eus()
        for origin in ('primary', 'participant'):
            with self.subTest(origin=origin):
                members = [member('sel:0', '43242', X2, (E3,)), member('sel:1', '43259', X2, (E2,), origin=origin)]
                found = C.base_included(members, {X2: C.SessionActs(reportable=(E3,))}, R)
                self.assertEqual([(b.key, b.code, b.named_codes) for b in found], [('sel:1', '43259', ('43242',))])

    def test_every_examination_only_eus_code_beside_an_uncovered_fna_is_held(self):
        """Base rule (b): the session's reportable FNA, which no counted code accounts for, holds every
        examination-only EUS code, as a colonoscopy's snare holds 45378; on an examination-only document each is ready
        (the control)."""
        self.assertEqual(EXAM_ONLY, ('43231', '43237', '43259', '44406', '45341', '45391'))
        with_fna, alone = self.eus(), self.eus(fna=False)
        for code in EXAM_ONLY:
            with self.subTest(code=code):
                found = C.base_included([member('sel:0', code, X2, (E2,))], {X2: C.SessionActs(reportable=(E3,))},
                                        with_fna)
                self.assertEqual([(b.named_codes, b.reportable) for b in found], [((), (E3,))])
                self.assertEqual(C.base_included([member('sel:0', code, X2, (E2,))], {X2: C.SessionActs()}, alone),
                                 ())

    def test_an_em_add_on_is_no_base_code(self):
        """Only a base profile and an examination-only profile are base codes: 99417 is neither."""
        self.assertEqual([code for code in ('99213', '99417', '43259', '43242', '45378', '45385') if C.is_base(code)],
                         ['99213', '43259', '45378'])

    def test_is_base_equals_v1s_over_every_catalogue_code(self):
        for code in sorted(catalogue.CODES):
            with self.subTest(code=code):
                self.assertEqual(C.is_base(str(code)), v1_combination._base(str(code)))
        for odd in ('', '4523', 'abcde', '99999'):
            self.assertEqual(C.is_base(odd), v1_combination._base(odd))

    def test_two_em_codes_of_one_visit_hold_each_other(self):
        """The legacy base rule reads E/M profiles as base codes that cover the visit (R3 Q7), and an office visit's own
        event is never an act beside itself. D40: the two also compete for the one visit."""
        R = build({E0: act(Kind.EM_VISIT, X0)}, {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS))})
        members = [member('sel:0', '99213', X0, (E0,)), member('sel:1', '99214', X0, (E0,))]
        combined = C.combine(members, {X0: C.SessionActs()}, R)
        self.assertEqual([keys(combined.held[key]) for key in ('sel:0', 'sel:1')],
                         [['base_included', 'competing_codes'], ['base_included', 'competing_codes']])
        self.assertEqual((combined.bases['sel:0'].named_codes, combined.competes['sel:0']), (('99214',), ('99214',)))
        alone = C.combine(members[:1], {X0: C.SessionActs()}, R)
        self.assertEqual(alone.held['sel:0'], ())

    def test_d177_the_hold_names_only_codes_of_its_own_tract(self):
        """D177 (1): a lower-tract EUS code is never asked whether it is reported separately from an upper EUS code; it
        names the act instead, and only where nothing of its own tract is left to name does it name the others (the
        recorded residual). WHETHER the code is held is unchanged."""
        R = self.eus()
        members = [member('sel:0', '45341', X2, (E2,)), member('sel:1', '43242', X2, (E3,))]
        with_act = C.base_included(members, {X2: C.SessionActs(reportable=(E3,))}, R)
        self.assertEqual([(b.beside, b.others, b.named_codes) for b in with_act], [(('43242',), (), ())])
        residual = C.base_included(members, {X2: C.SessionActs()}, R)
        self.assertEqual([(b.beside, b.others, b.named_codes) for b in residual], [(('43242',), (), ('43242',))])
        same_tract = C.base_included([member('sel:0', '43259', X2, (E2,)), member('sel:1', '45342', X2, (E3,)),
                                      member('sel:2', '43242', X2, (E3,))], {X2: C.SessionActs()}, R)
        self.assertEqual([b.named_codes for b in same_tract], [('43242',)])

    def test_d119_an_upper_endoscopys_base_code_reads_the_feeding_tube_sessions_peg(self):
        """D119: a PEG filed under the feeding-tube session is an act of the upper endoscopy done with it too: 43235 is
        held beside it. A feeding-tube act that is no PEG, a PEG of a session that cannot be the feeding tube's, and any
        other family's base code read nothing there."""
        sessions = {X1: session_of(SessionKind.EGD), X3: session_of(SessionKind.FEEDING_TUBE),
                    X4: session_of(SessionKind.COLONOSCOPY)}
        R = build({E1: act(Kind.EXAMINATION, X1), E5: act(Kind.PEG, X3), E6: act(Kind.TUBE_REPLACEMENT, X3),
                   E7: act(Kind.PEG, X4), E8: act(Kind.EXAMINATION, X4)}, sessions)
        coding = {X1: C.SessionActs(), X3: C.SessionActs(reportable=(E5, E6)), X4: C.SessionActs(reportable=(E7,))}
        found = C.base_included([member('sel:0', '43235', X1, (E1,))], coding, R)
        self.assertEqual([(b.reportable, b.established) for b in found], [((E5,), True)])
        doubted_peg = C.base_included([member('sel:0', '43235', X1, (E1,))],
                                      {X1: C.SessionActs(), X3: C.SessionActs(doubted=(E5,))}, R)
        self.assertEqual([(b.reportable, b.doubted, b.established) for b in doubted_peg], [((), (E5,), False)])
        self.assertEqual(C.base_included([member('sel:0', '45378', X4, (E8,))], {X4: C.SessionActs(), X3: coding[X3]},
                                         R), ())

    def test_an_unlisted_act_with_a_session_card_holds_the_sessions_base_code(self):
        """FINAL-V2 3.2.6 rule 3: an unlisted act with a session card is a synthetic doubted act of that session - it
        holds the session's base code as a doubt (a QUESTION), whatever the coding lists. An unlisted act of another
        session or of none, and an unlisted denial or doubt, hold nothing here."""
        unlisted = (UnlistedStatement(units=(Span(900, 940),), what=ct.UnlistedWhat.ACT, kind=Kind.BIOPSY, session=X1),
                    UnlistedStatement(units=(Span(950, 990),), what=ct.UnlistedWhat.ACT, kind=None, session=X2),
                    UnlistedStatement(units=(Span(1000, 1040),), what=ct.UnlistedWhat.ACT, kind=None, session=None),
                    UnlistedStatement(units=(Span(1050, 1090),), what=ct.UnlistedWhat.DENIAL, kind=None, session=X1))
        R = build({E1: act(Kind.EXAMINATION)}, COLONOSCOPY, unlisted=unlisted)
        found = C.base_included([member('sel:0', '45378', supporting=(E1,))], {X1: C.SessionActs()}, R)
        self.assertEqual([(b.unlisted, b.established) for b in found], [((0,), False)])
        held = C.base_hold(found[0], R)
        self.assertEqual((held.kind, held.spans), (ItemKind.QUESTION, (Span(900, 940),)))
        control = build({E1: act(Kind.EXAMINATION)}, COLONOSCOPY, unlisted=unlisted[1:])
        self.assertEqual(C.base_included([member('sel:0', '45378', supporting=(E1,))], {X1: C.SessionActs()},
                                         control), ())

    def test_a_code_with_no_session_or_no_base_profile_is_never_a_base(self):
        R = self.colonoscopy()
        self.assertEqual(C.base_included([member('sel:0', '45378', session=None), member('sel:1', '45385')],
                                         {X1: C.SessionActs(reportable=(E2,))}, R), ())

    def test_f2_beside_only_a_code_the_hold_is_a_question(self):
        """The refutation's F2 (4.8: an EXPLANATION only when an established fact fails the requirement): 45378 READY on
        its examination beside 45385 proposed with no snare documented is held base_included as a QUESTION - its
        inclusion rests on a code with no act, and rejecting that code releases it. Only a reportable act of the
        session (an intervention established done, rule (b)) makes it an EXPLANATION. The other code's support is never
        read (it rests on that code's own facts, outside 45378's closure: 4.9), so it moves nothing."""
        R = build({E1: act(Kind.EXAMINATION)}, COLONOSCOPY)
        for supported in (False, True):
            with self.subTest(supported=supported):
                members = [member('sel:0', '45378', supporting=(E1,), procedural=True, supported=True),
                           member('sel:1', '45385', procedural=True, supported=supported)]
                combined = C.combine(members, {X1: C.SessionActs()}, R)
                base = combined.bases['sel:0']
                self.assertEqual((base.beside, base.reportable, base.established), (('45385',), (), False))
                self.assertEqual([(h.fact, h.kind) for h in combined.held['sel:0']],
                                 [('base_included', ItemKind.QUESTION)])
        snare = self.colonoscopy()
        reportable = C.base_included([member('sel:0', '45378', supporting=(E1,)),
                                      member('sel:1', '45385', supporting=(E2,))],
                                     {X1: C.SessionActs(reportable=(E2,))}, snare)
        self.assertEqual((reportable[0].established, C.base_hold(reportable[0], snare).kind),
                         (True, ItemKind.EXPLANATION))

    def test_f5_a_session_the_coding_does_not_list_is_refused_never_read_as_empty(self):
        """The refutation's F5: step 4b's event_coding@2 lists every session, so a base code's session missing from
        ``coding`` is a wiring error - refused (ValueError), never read as a session with no acts, which would release
        45378 beside a snare nobody listed. D119's feeding-tube sessions are read the same way. A code that is no base
        code, or has no session, reads no coding at all."""
        R = self.colonoscopy()
        with self.assertRaises(ValueError):
            C.base_included([member('sel:0', '45378', supporting=(E1,))], {}, R)
        with self.assertRaises(ValueError):
            C.combine([member('sel:0', '45378', supporting=(E1,))], {X2: C.SessionActs()}, R)
        self.assertEqual(C.base_included([member('sel:0', '45385', supporting=(E2,)), member('sel:1', '45378', None)],
                                         {}, R), ())
        sessions = {X1: session_of(SessionKind.EGD), X3: session_of(SessionKind.FEEDING_TUBE)}
        tube = build({E1: act(Kind.EXAMINATION, X1), E5: act(Kind.PEG, X3)}, sessions)
        with self.assertRaises(ValueError):
            C.base_included([member('sel:0', '43235', X1, (E1,))], {X1: C.SessionActs()}, tube)
        self.assertEqual([b.reportable for b in C.base_included(
            [member('sel:0', '43235', X1, (E1,))], {X1: C.SessionActs(), X3: C.SessionActs(reportable=(E5,))}, tube)],
            [(E5,)])
        self.assertEqual(C.session_acts({X1: C.SessionActs(doubted=(E2,))}, X1), C.SessionActs(doubted=(E2,)))


# --- base-within (C3, C-4, D70) ---------------------------------------------------------------------------------------


def egd_eus(*, eus=None, tract=sup(ct.Tract.UPPER), part_of=None, eus_exam=None, egd_exam=None, extra=None) -> FactSet:
    """An upper endoscopy X1 (its examination E1) and an upper EUS X2 (its examination E2, an FNA E3)."""
    events = {E1: egd_exam if egd_exam is not None else act(Kind.EXAMINATION, X1),
              E2: eus_exam if eus_exam is not None else act(Kind.EXAMINATION, X2,
                                                           places=(sup(Landmark.PANCREAS),)),
              E3: act(Kind.FNA, X2, places=(sup(Landmark.PANCREAS),), device=sup(Device.NEEDLE))}
    events.update(extra or {})
    return build(events, {X1: session_of(SessionKind.EGD, part_of=part_of),
                          X2: session_of(eus if eus is not None else SessionKind.EUS, tract=tract)})


class BaseWithin(SimpleTestCase):
    """v1's BaseWithin class re-expressed, from the FactSet (4.7: part_of_session, C-4 over supported kinds and tracts,
    D70 by possibly)."""

    def within(self, R, *members):
        return C.base_within(list(members), R)

    def test_c4_an_egd_beside_an_upper_eus_is_held_beside_its_code(self):
        R = egd_eus()
        found = self.within(R, member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,)))
        self.assertEqual([(b.key, b.code, b.session, b.wholes, b.within, b.established) for b in found],
                         [('sel:0', '43235', X1, (X2,), ('43242',), True)])
        held = C.base_within_hold(found[0], R)
        self.assertEqual((held.fact, held.rank, held.kind, held.cause, held.subject),
                         ('base_included', 21, ItemKind.EXPLANATION, C.WITHIN_CAUSE, X1))
        self.assertEqual(held.spans, span_of(E1, E2))

    def test_c4_an_egd_beside_an_uncoded_eus_is_held_beside_none(self):
        found = self.within(egd_eus(), member('sel:0', '43235', X1, (E1,)))
        self.assertEqual([(b.wholes, b.within, b.established) for b in found], [((X2,), (), True)])

    def test_c4_an_eus_examination_whose_device_is_not_the_endoscope_is_still_the_session(self):
        """FINAL 5.6 E13 sets apart only a digital examination (a device supported manual): an EUS examination whose
        device is established as another class is still the EUS session. The control: a digital examination alone is no
        session, so it makes no EGD its endoscopic portion."""
        other = egd_eus(eus_exam=act(Kind.EXAMINATION, X2, device=sup(Device.OTHER)))
        self.assertEqual([b.within for b in self.within(other, member('sel:0', '43235', X1, (E1,)),
                                                        member('sel:1', '43242', X2, (E3,)))], [('43242',)])
        digital = build({E1: act(Kind.EXAMINATION, X1), E2: act(Kind.EXAMINATION, X2, device=sup(Device.MANUAL))},
                        {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))})
        self.assertEqual(self.within(digital, member('sel:0', '43235', X1, (E1,))), ())

    def test_d121_an_eus_told_only_through_its_done_act_is_the_session(self):
        """D121, D135: an EUS told only through its done acts (no examination) is the session C-4 reads."""
        R = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2, places=(sup(Landmark.PANCREAS),))},
                  {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))})
        self.assertEqual([(b.within, b.established) for b in self.within(R, member('sel:0', '43235', X1, (E1,)),
                                                                         member('sel:1', '43242', X2, (E3,)))],
                         [(('43242',), True)])

    def test_c3_part_of_names_the_endoscopic_portion_too(self):
        R = egd_eus(eus=SessionKind.EUS, tract=None, part_of=sup(X2))
        found = self.within(R, member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,)))
        self.assertEqual([(b.within, b.established) for b in found], [(('43242',), True)])

    def test_a_lower_eus_includes_no_egd(self):
        R = egd_eus(tract=sup(ct.Tract.LOWER))
        self.assertEqual(self.within(R, member('sel:0', '43235', X1, (E1,)), member('sel:1', '45392', X2, (E3,))),
                         ())

    def test_d70_a_session_that_may_be_the_endoscopic_portion_is_held_as_one_that_is(self):
        """D70: an EUS that may be today's upper EUS - its tract not established, its examination's date not
        established, its kind in doubt, or the part_of_session claim not established - holds the EGD's base code as C-4
        would, a QUESTION, never READY. A fact established against the structure sets up nothing (the controls)."""
        possible = {
            'tract silent': egd_eus(tract=None),
            'tract unresolved': egd_eus(tract=unres(ct.Tract.UPPER)),
            'the EUS examination undatable': egd_eus(
                eus_exam=act(Kind.EXAMINATION, X2, date=unres(ON)),
                extra={E3: act(Kind.FNA, X2, date=unres(ON))}),
            'the EUS kind in doubt': egd_eus(eus=doubted(SessionKind.EUS)),
            'part_of_session unresolved': egd_eus(tract=sup(ct.Tract.LOWER), part_of=unres(X2)),
        }
        for name, R in possible.items():
            with self.subTest(name):
                found = self.within(R, member('sel:0', '43235', X1, (E1,)))
                self.assertEqual([(b.wholes, b.established) for b in found], [((X2,), False)])
                self.assertEqual(C.base_within_hold(found[0], R).kind, ItemKind.QUESTION)
        controls = {
            'tract lower': egd_eus(tract=sup(ct.Tract.LOWER)),
            'the EUS of another date': egd_eus(eus_exam=act(Kind.EXAMINATION, X2, date=sup(EARLIER)),
                                               extra={E3: act(Kind.FNA, X2, date=sup(EARLIER))}),
            'the EUS denied': egd_eus(eus_exam=act(Kind.EXAMINATION, X2, status=neg(PERFORMED)),
                                      extra={E3: act(Kind.FNA, X2, status=neg(PERFORMED))}),
            'another family': egd_eus(eus=SessionKind.COLONOSCOPY),
            'part_of_session negated': egd_eus(tract=sup(ct.Tract.LOWER), part_of=neg(X2)),
        }
        for name, R in controls.items():
            with self.subTest(control=name):
                self.assertEqual(self.within(R, member('sel:0', '43235', X1, (E1,))), ())

    def test_an_eus_whose_tract_may_be_pancreatobiliary_is_a_possible_whole(self):
        """An upper EUS examining the pancreas may be filed with the pancreatobiliary tract: v1 read every EUS not
        placed lower as upper, so the EGD's base code is held as within a possible whole - a QUESTION, never READY,
        never an established whole (the step's NOTES record the question). A tract established as not upper sets up
        none."""
        R = egd_eus(tract=sup(ct.Tract.PANCREATOBILIARY))
        found = self.within(R, member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,)))
        self.assertEqual([(b.within, b.established) for b in found], [(('43242',), False)])
        self.assertEqual(self.within(egd_eus(tract=neg(ct.Tract.UPPER)), member('sel:0', '43235', X1, (E1,))), ())

    def test_f3_a_session_is_done_by_its_examination_when_it_has_one(self):
        """The refutation's F3 (4.3 row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act
        itself)"): an upper EUS whose examination's date is not established beside its done FNA is not established
        done, so C-4's whole is only possible - the EGD's base code a QUESTION, never an EXPLANATION. Its examination
        done, the whole is established. An act-only EUS is done by its act (D121), unless an event that may be its
        examination is left open."""
        open_exam = egd_eus(eus_exam=act(Kind.EXAMINATION, X2, date=unres(ON), places=(sup(Landmark.PANCREAS),)))
        self.assertFalse(C.session_done(open_exam, X2))
        found = self.within(open_exam, member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,)))
        self.assertEqual([(b.wholes, b.established) for b in found], [((X2,), False)])
        self.assertEqual(C.base_within_hold(found[0], open_exam).kind, ItemKind.QUESTION)
        self.assertTrue(C.session_done(egd_eus(), X2))
        act_only = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2)},
                         {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))})
        self.assertTrue(C.session_done(act_only, X2))
        unplaced = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2),
                          E4: act(Kind.EXAMINATION, None, date=unres(ON))},
                         {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))})
        self.assertFalse(C.session_done(unplaced, X2))  # E4 may be X2's examination, and it is not done
        self.assertEqual([w.established for w in C.wholes(unplaced, X1)], [False])

    def test_codes_that_include_no_upper_endoscopy_hold_nothing(self):
        """The whole's counted codes that include no examination of the base code's family hold nothing (43231, the
        esophagoscopic EUS, includes no EGD); only a whole with no counted code holds it beside none."""
        R = egd_eus()
        self.assertEqual(self.within(R, member('sel:0', '43235', X1, (E1,)), member('sel:1', '43231', X2, (E2,))), ())

    def test_combine_reads_base_within_only_where_base_included_does_not_hold(self):
        """v1's order: a base code held base_included carries no second base item."""
        R = egd_eus()
        members = [member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,))]
        within = C.combine(members, {X1: C.SessionActs(), X2: C.SessionActs(reportable=(E3,))}, R)
        self.assertEqual((keys(within.held['sel:0']), within.held['sel:0'][0].cause),
                         (['base_included'], C.WITHIN_CAUSE))
        both = C.combine(members, {X1: C.SessionActs(reportable=(E3,))}, R)
        self.assertEqual((keys(both.held['sel:0']), both.held['sel:0'][0].cause), (['base_included'], C.BASE_CAUSE))


# --- competing (D40, D55, D74, D104, D118, D163, D167) ----------------------------------------------------------------


def ercp(*, extraction=None, lithotripsy=None, extra=None) -> FactSet:
    """An ERCP X1: its examination E1, a stone extraction E3 and a lithotripsy E4 (finding 5's stone clearance, as
    facts)."""
    events = {E1: act(Kind.EXAMINATION), E3: extraction if extraction is not None else act(Kind.STONE_EXTRACTION),
              E4: lithotripsy if lithotripsy is not None else act(Kind.LITHOTRIPSY)}
    if extraction is False:
        del events[E3]
    if lithotripsy is False:
        del events[E4]
    events.update(extra or {})
    return build(events, {X1: session_of(SessionKind.ERCP)})


def compete(R: FactSet, *members_: C.Member) -> dict:
    """The competition over the members' claims (assess's wiring: each counted code's claims, then competition)."""
    return C.competition([(m.key, m.code, m.origin, C.claims(m.code, R, m.supporting)) for m in members_])


class Competition(SimpleTestCase):
    """v1's Competition class re-expressed."""

    def test_two_codes_one_a_participants_whose_events_meet_compete(self):
        entries = [('sel:0', '43249', 'primary', (E2,)), ('sel:1', '43248', 'participant', (E2,)),
                   ('sel:2', '43239', 'primary', (E3,))]
        self.assertEqual(C.competition(entries), {'sel:0': ('43248',), 'sel:1': ('43249',)})
        self.assertEqual(C.contested(entries), {'sel:0': (E2,), 'sel:1': (E2,)})

    def test_two_codes_for_one_act_compete_whoever_proposed_them(self):
        """D40: two codes the proposal provider alone selected for one act compete as any other two do."""
        self.assertEqual(C.competition([('sel:0', '45380', 'primary', (E2,)), ('sel:1', '45385', 'primary', (E2,))]),
                         {'sel:0': ('45385',), 'sel:1': ('45380',)})

    def test_codes_for_different_acts_and_one_code_twice_never_compete(self):
        self.assertEqual(C.competition([('sel:0', '45380', 'primary', (E2,)), ('sel:1', '45385', 'primary', (E3,)),
                                        ('sel:2', '45385', 'participant', (E3,))]), {})

    def test_competition_equals_v1s_on_the_same_entries(self):
        entries = [('sel:0', '43249', 'primary', ('E2',)), ('sel:1', '43248', 'participant', ('E2', 'E5')),
                   ('sel:2', '43239', 'primary', ('E3',)), ('sel:3', '43248', 'primary', ('E5',)),
                   ('sel:4', '43245', 'primary', ())]
        self.assertEqual(C.competition(entries), v1_combination.competition(entries))

    def test_d55_a_narrowed_code_claims_the_acts_its_covers_name_beside_its_defining_kinds(self):
        """D55: the competition reads each counted code's CLAIMS - its E* and, for a code D27 narrows, every act of its
        family of a kind its covers name beside its defining kinds. Exactly three codes have such kinds (43265 the stone
        extraction, 44365 the ablation, 49440 the tube placement). A narrowed code with no defining act claims nothing
        (43265 held not documented), and an act of another date is never claimed."""
        extra = {code: tuple(kind for kind in catalogue.code_link(str(code)).acts if kind not in kinds)
                 for code, kinds in catalogue.DEFINING.items()}
        self.assertEqual({code: kinds for code, kinds in extra.items() if kinds},
                         {43265: (Kind.STONE_EXTRACTION,), 44365: (Kind.ABLATION,), 49440: (Kind.TUBE_PLACEMENT,)})
        v1_extra = {code: tuple(kind for kind in v1_mapping.code_link(code).acts if kind not in kinds)
                    for code, kinds in v1_mapping.DEFINING.items()}
        self.assertEqual({int(code): tuple(Kind(kind) for kind in kinds) for code, kinds in v1_extra.items() if kinds},
                         {code: kinds for code, kinds in extra.items() if kinds})
        R = ercp()
        self.assertEqual(C.claims('43265', R, (E4,)), (E4, E3))  # its lithotripsy, then the extraction
        self.assertEqual(C.claims('43264', R, (E3,)), (E3,))
        self.assertEqual(C.claims('43265', ercp(lithotripsy=False), ()), ())  # not documented: claims nothing
        earlier = ercp(extraction=act(Kind.STONE_EXTRACTION, date=sup(EARLIER)))
        self.assertEqual(C.claims('43265', earlier, (E4,)), (E4,))  # an earlier extraction is not claimed

    def test_an_act_whose_session_is_not_stated_may_be_in_any_session_of_the_document(self):
        """A biopsy whose session slot is empty may be in any session the document has (possible_sessions): beside an
        upper endoscopy and a colonoscopy, 43239 and 45380 both claim it and compete; in an upper endoscopy's note
        alone, a colonoscopy code claims nothing of it. The same reading decides the procedure day's family arm."""
        both = build({E1: act(Kind.EXAMINATION, X1), E5: act(Kind.EXAMINATION, X2), E9: act(Kind.BIOPSY, None)},
                     {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.COLONOSCOPY)})
        self.assertEqual(C.possible_sessions(both, E9), (X1, X2))
        self.assertEqual(compete(both, member('sel:0', '43239', X1), member('sel:1', '45380', X2)),
                         {'sel:0': ('45380',), 'sel:1': ('43239',)})
        upper = build({E1: act(Kind.EXAMINATION, X1), E9: act(Kind.BIOPSY, None)}, {X1: session_of(SessionKind.EGD)})
        self.assertEqual((C.claims('43239', upper, ()), C.claims('45380', upper, ())), ((E9,), ()))

    def test_a_session_negation_left_open_may_be_in_any_session(self):
        """9.4 P-MONO on the session slot (found by the step's wider property search): a biopsy told as "not in the
        upper endoscopy" may be in any session, and so may the same negation not established (its state negated, its
        result unresolved or doubted) - read as its claimed value alone, weakening it took the biopsy from the
        colonoscopy code's claims, and 45380 and 43239 stopped competing."""
        sessions = {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.COLONOSCOPY)}
        open_negation = fact(Res.UNRESOLVED, X1, State.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
        doubted_negation = fact(Res.UNKNOWN, X1, State.NEGATED, options=(X2,), reasons=(ct.Reason.DOUBT_UNCLEAR,))
        for name, found in (('negated', neg(X1)), ('negation unresolved', open_negation),
                            ('negation doubted', doubted_negation)):
            with self.subTest(name):
                R = build({E1: act(Kind.EXAMINATION, X1), E5: act(Kind.EXAMINATION, X2), E9: act(Kind.BIOPSY, found)},
                          sessions)
                self.assertEqual(C.possible_sessions(R, E9), (X1, X2))
                self.assertIn(E9, C.claims('45380', R, ()))
                self.assertEqual(compete(R, member('sel:0', '43239', X1), member('sel:1', '45380', X2)),
                                 {'sel:0': ('45380',), 'sel:1': ('43239',)})

    def test_the_hold_is_the_competing_codes_item(self):
        R = ercp()
        held = C.competing_hold((E3,), R)
        self.assertEqual((held.fact, held.rank, held.kind, held.cause, held.subject, held.attribute, held.result,
                          held.spans), ('competing_codes', 22, ItemKind.QUESTION, C.COMPETING_CAUSE, E3, None, None,
                                        span_of(E3)))
        self.assertEqual((rq.fact_key(C.COMPETING_ITEM.fact), C.COMPETING_ITEM.rank.value),
                         (v1_combination.COMPETING_FACT, 22))


class HeldCodesKeepTheirClaims(SimpleTestCase):
    """"A held code never releases a rival" (8.1 step 4d's done-when; D163, D167, D74, D104, 4.8 Q3): a code's claims
    are read from the acts by possibly, never from its state, so a code held for any reason still claims the act its
    hold rests on, and its rival keeps competing_codes. v1's D163 and D167 pins, re-expressed over facts."""

    def stone_clearance(self, extraction) -> tuple:
        R = ercp(extraction=extraction)
        held = member('sel:0', '43264', supporting=())  # held: no supporting act
        ready = member('sel:1', '43265', supporting=(E4,))  # READY on its lithotripsy
        return R, held, ready

    def test_d163_an_extraction_told_in_a_nursing_entry_holds_the_lithotripsys_43265(self):
        """D163 (D124, D146): 43264 held another_role ("Nurse: The stone fragments were extracted ...") keeps its act;
        43265 READY on the lithotripsy of one stone clearance is held competing_codes beside it."""
        R, held, ready = self.stone_clearance(act(Kind.STONE_EXTRACTION, entry=sup(NURSING)))
        self.assertIn(E3, C.claims('43264', R, ()))
        self.assertEqual(compete(R, held, ready), {'sel:0': ('43265',), 'sel:1': ('43264',)})

    def test_d163_a_code_held_on_a_doubted_or_unestablished_act_keeps_it(self):
        """D163, D167: the extraction stated uncertain, its status or date not established, its performer an
        unconfirmed clinician - each holds 43264 and each keeps 43265 competing (a doubted act is a doubt about the code
        that accounts for it, never an absence: D87)."""
        doubts = {
            'status doubted': act(Kind.STONE_EXTRACTION, status=doubted(PERFORMED)),
            'status unresolved': act(Kind.STONE_EXTRACTION, status=unres(PERFORMED)),
            'attempted': act(Kind.STONE_EXTRACTION, status=sup(Status.ATTEMPTED_NOT_COMPLETED)),
            'date unresolved': act(Kind.STONE_EXTRACTION, date=unres(ON)),
            'date silent': act(Kind.STONE_EXTRACTION, date=SILENT),
            'performer unconfirmed': act(Kind.STONE_EXTRACTION, performer=unres(OTHER_CLINICIAN)),
            'session unresolved': act(Kind.STONE_EXTRACTION, session=unres(X1)),
        }
        for name, extraction in doubts.items():
            with self.subTest(name):
                R, held, ready = self.stone_clearance(extraction)
                self.assertEqual(compete(R, held, ready), {'sel:0': ('43265',), 'sel:1': ('43264',)})

    def test_d163_controls_an_act_that_is_no_doubt_is_never_claimed(self):
        """An extraction denied, planned, done at another date, by a clinician established as another, or in another
        family's session is no act of 43264's: nothing competes and 43265 stays READY. (A clinician established as
        another's extraction is still among 43265's D167 extras, any performer's as v1's current performed acts were;
        no rival claims it, so nothing moves: the step's NOTES record it.)"""
        controls = {
            'denied': act(Kind.STONE_EXTRACTION, status=neg(PERFORMED)),
            'planned': act(Kind.STONE_EXTRACTION, status=sup(PLANNED)),
            'another date': act(Kind.STONE_EXTRACTION, date=sup(EARLIER)),
            'another clinician': act(Kind.STONE_EXTRACTION, performer=sup(OTHER_CLINICIAN)),
            'another family': act(Kind.STONE_EXTRACTION, session=sup(X2)),
        }
        for name, extraction in controls.items():
            with self.subTest(name):
                R = build({E1: act(Kind.EXAMINATION), E3: extraction, E4: act(Kind.LITHOTRIPSY)},
                          {X1: session_of(SessionKind.ERCP), X2: session_of(SessionKind.EGD)})
                self.assertNotIn(E3, C.claims('43264', R, ()))
                self.assertEqual(compete(R, member('sel:0', '43264'), member('sel:1', '43265', supporting=(E4,))),
                                 {})

    def test_d104_d74_a_doubted_defining_act_still_opens_the_narrowed_codes_claims(self):
        """D74, D104: a lithotripsy only doubted (stated uncertain, its date not established) is a doubt about 43265,
        never an absence: 43265 (held) claims the extraction, so 43264 READY on it is held competing_codes. A denied or
        planned lithotripsy claims nothing, and 43264 stays READY."""
        for name, lithotripsy in (('uncertain', act(Kind.LITHOTRIPSY, status=doubted(PERFORMED))),
                                  ('undatable', act(Kind.LITHOTRIPSY, date=unres(ON)))):
            with self.subTest(name):
                R = ercp(lithotripsy=lithotripsy)
                self.assertEqual(compete(R, member('sel:0', '43264', supporting=(E3,)), member('sel:1', '43265')),
                                 {'sel:0': ('43265',), 'sel:1': ('43264',)})
        for name, lithotripsy in (('denied', act(Kind.LITHOTRIPSY, status=neg(PERFORMED))),
                                  ('planned', act(Kind.LITHOTRIPSY, status=sup(PLANNED)))):
            with self.subTest(control=name):
                R = ercp(lithotripsy=lithotripsy)
                self.assertEqual(C.claims('43265', R, ()), ())
                self.assertEqual(compete(R, member('sel:0', '43264', supporting=(E3,)), member('sel:1', '43265')), {})

    def test_d167_the_other_narrowed_codes_compete_for_a_doubted_act_of_their_other_kind(self):
        """D167: 44365 beside 44369 with the ablation stated uncertain, and 49440 beside 49441 with the jejunostomy
        tube's status not established: each pair competes."""
        enteroscopy = build({E1: act(Kind.EXAMINATION), E2: act(Kind.HOT_BIOPSY),
                             E3: act(Kind.ABLATION, status=doubted(PERFORMED))},
                            {X1: session_of(SessionKind.ENTEROSCOPY)})
        self.assertEqual(compete(enteroscopy, member('sel:0', '44365', supporting=(E2,)), member('sel:1', '44369')),
                         {'sel:0': ('44369',), 'sel:1': ('44365',)})
        tube = build({E2: act(Kind.PEG), E3: act(Kind.TUBE_PLACEMENT, status=unres(PERFORMED))},
                     {X1: session_of(SessionKind.FEEDING_TUBE)})
        self.assertEqual(compete(tube, member('sel:0', '49440', supporting=(E2,)), member('sel:1', '49441')),
                         {'sel:0': ('49441',), 'sel:1': ('49440',)})

    def test_a_ready_code_keeps_the_act_a_weakening_took_out_of_its_e_star(self):
        """P-MONO's release, the READY direction (9.4: "the claims never shrink"): 43245 (any technique) READY on a
        balloon dilation E2 and a wire-guided one E3, of two strictures set apart (lesions distinct, their controls
        rejected), competes with 43248 (wire-guided), which may account for E3 only (R4: E2's balloon is another
        technique). Weakening E3's date takes it out of 43245's E* while 43245 stays READY on E2; read from its E*
        alone, 43245 would claim E2 only and lose its competing_codes hold - a release by a weakening. Read by possibly,
        it still claims E3, and the two still compete. (D118 cannot re-add it: 43245 names no technique, and the
        strictures are apart.)"""
        lesions = {L1: lesion_of(distinct=(L2,)), L2: lesion_of()}
        controls = {(E2, A.TARGET_LESION, L2): True, (E3, A.TARGET_LESION, L1): True}

        def strictures(date):
            return build({E1: act(Kind.EXAMINATION),
                          E2: act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                          E3: act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=sup(L2), date=date)},
                         {X1: session_of(SessionKind.EGD)}, lesions=lesions, controls=controls)

        before = strictures(sup(ON))
        self.assertEqual(C.claims('43248', before, (E3,)), (E3,))
        self.assertEqual(compete(before, member('sel:0', '43245', supporting=(E2, E3)),
                                 member('sel:1', '43248', supporting=(E3,))),
                         {'sel:0': ('43248',), 'sel:1': ('43245',)})
        weakened = strictures(unres(ON))
        self.assertEqual(C.claims('43245', weakened, (E2,)), (E2, E3))
        self.assertEqual(compete(weakened, member('sel:0', '43245', supporting=(E2,)), member('sel:1', '43248')),
                         {'sel:0': ('43248',), 'sel:1': ('43245',)})

    def test_claims_never_read_the_codes_state(self):
        """4.8: claims read acts by possibly, never a held code's state: the same code claims the same acts whether its
        E* is given (READY) or empty (held)."""
        R = ercp()
        for code, supporting in (('43264', (E3,)), ('43265', (E4,))):
            with self.subTest(code=code):
                self.assertEqual(set(C.claims(code, R, supporting)), set(C.claims(code, R, ())))


def dilations(first: dict, second: dict, *, lesions=None, controls=None, family=SessionKind.EGD) -> FactSet:
    return build({E1: act(Kind.EXAMINATION), E2: first, E3: second}, {X1: session_of(family)}, lesions=lesions,
                 controls=controls)


class Strictures(SimpleTestCase):
    """D118 (one stricture: same lesion, or places not disjoint), R4 (another technique is no act the code accounts
    for) and P6 (no place list sets an act outside a site class), over facts; 4.11 and SC-B: an unknown identity and an
    unrejected pair control never set two acts apart."""

    def test_d118_two_dilation_codes_of_different_techniques_for_one_stricture_compete(self):
        R = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                      act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=sup(L1)))
        self.assertEqual(C.claims('43249', R, (E2,)), (E2, E3))
        self.assertEqual(compete(R, member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43248',
                                                                                         supporting=(E3,))),
                         {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_d118_two_strictures_set_apart_by_lesion_or_place_never_compete_and_an_unrejected_control_never_sets_apart(
            self):
        lesions = {L1: lesion_of(distinct=(L2,)), L2: lesion_of()}
        lesion_controls = {(E2, A.TARGET_LESION, L2): True, (E3, A.TARGET_LESION, L1): True}
        apart = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                          act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=sup(L2)), lesions=lesions,
                          controls=lesion_controls)
        members = (member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43248', supporting=(E3,)))
        self.assertEqual(compete(apart, *members), {})
        unrejected = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                               act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=sup(L2)), lesions=lesions,
                               controls={(E2, A.TARGET_LESION, L2): True})
        self.assertEqual(compete(unrejected, *members), {'sel:0': ('43248',), 'sel:1': ('43249',)})
        place_controls = {(E2, A.TARGET_PLACES, Landmark.MID_ESOPHAGUS): True,
                          (E3, A.TARGET_PLACES, Landmark.DISTAL_ESOPHAGUS): True}
        by_place = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                             act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), places=(sup(Landmark.MID_ESOPHAGUS),)),
                             controls=place_controls)
        self.assertFalse(C.one_stricture(by_place, E2, E3))
        self.assertEqual(compete(by_place, *members), {})
        short = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                          act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), places=(sup(Landmark.MID_ESOPHAGUS),)))
        self.assertTrue(C.one_stricture(short, E2, E3))  # no control rejected: never set apart (SC-B)
        self.assertEqual(compete(short, *members), {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_d118_an_act_whose_lesion_is_not_established_stays_on_one_stricture(self):
        """4.11: an unknown identity never sets two acts apart. A balloon dilation whose lesion is not established
        (E3) stays on one stricture with the wire dilation of another lesion (E4) - lesion controls rejected or not -
        and with the balloon dilation of its claimed lesion (E2): 43249 and 43248 compete through it."""
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                   E3: act(Kind.DILATION, device=sup(Device.BALLOON), lesion=unres(L1), date=unres(ON)),
                   E4: act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=sup(L2))},
                  {X1: session_of(SessionKind.EGD)}, lesions={L1: lesion_of(distinct=(L2,)), L2: lesion_of()},
                  controls={(E2, A.TARGET_LESION, L2): True, (E4, A.TARGET_LESION, L1): True})
        self.assertTrue(C.one_stricture(R, E4, E3) and C.one_stricture(R, E2, E3))
        self.assertFalse(C.one_stricture(R, E2, E4))
        self.assertEqual(compete(R, member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43248',
                                                                                         supporting=(E4,))),
                         {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_d118_two_dilations_possibly_on_one_lesion_are_one_stricture_whatever_their_places(self):
        """D118's "same lesion" arm, by possibly (the refutation's T2, mutant R4): a balloon dilation of lesion L1 and a
        wire dilation whose lesion may be L1 (not established) stay on one stricture even where their listed places are
        set apart (disjoint, the place pair controls rejected): 43249 claims the wire dilation, and the two compete.
        With both lesions established distinct (controls rejected), the places set them apart."""
        controls = {(E2, A.TARGET_PLACES, Landmark.MID_ESOPHAGUS): True,
                    (E3, A.TARGET_PLACES, Landmark.DISTAL_ESOPHAGUS): True,
                    (E2, A.TARGET_LESION, L2): True, (E3, A.TARGET_LESION, L1): True}
        lesions = {L1: lesion_of(distinct=(L2,)), L2: lesion_of()}

        def pair(second_lesion):
            return dilations(act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1),
                                 places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                             act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), lesion=second_lesion,
                                 places=(sup(Landmark.MID_ESOPHAGUS),)), lesions=lesions, controls=controls)

        maybe_one = pair(unres(L1))
        self.assertTrue(F.apart_by_place(maybe_one, E2, E3))
        self.assertTrue(C.one_stricture(maybe_one, E2, E3))
        self.assertIn(E3, C.claims('43249', maybe_one, (E2,)))
        members = (member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43248', supporting=(E3,)))
        self.assertEqual(compete(maybe_one, *members), {'sel:0': ('43248',), 'sel:1': ('43249',)})
        apart = pair(sup(L2))
        self.assertFalse(C.one_stricture(apart, E2, E3))
        self.assertEqual(compete(apart, *members), {})

    def test_r4_a_device_of_no_technique_class_may_be_any_techniques(self):
        """R4 reads only a device established in ANOTHER technique class (the refutation's T2, mutant R5): a dilation
        whose device is supported but names no class (an endoscope, other) may be a balloon or a wire-guided one, so
        43249 and 43248 both claim it and compete - never read as another technique, which would let one go READY."""
        for device in (Device.ENDOSCOPE, Device.OTHER):
            with self.subTest(device=device):
                self.assertIsNone(catalogue.technique_class(device))
                R = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=sup(device)))
                self.assertEqual((C.claims('43249', R, ()), C.claims('43248', R, ())), ((E3,), (E3,)))
                self.assertEqual(compete(R, member('sel:0', '43249', supporting=(E3,)), member('sel:1', '43248')),
                                 {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_r4_a_dilation_of_another_technique_is_never_claimed(self):
        """R4 (D118's two-balloon control): one balloon dilation; 43249 READY on it, 43248 (wire-guided) held. 43248
        cannot account for a balloon dilation, so nothing competes. With the device not established it may: the two
        compete."""
        R = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=sup(Device.BALLOON)))
        self.assertEqual(C.claims('43248', R, ()), ())
        self.assertEqual(compete(R, member('sel:0', '43249', supporting=(E3,)), member('sel:1', '43248')), {})
        unsettled = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=unres(Device.BALLOON)))
        self.assertEqual(compete(unsettled, member('sel:0', '43249'), member('sel:1', '43248')),
                         {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_p6_no_place_list_sets_an_act_outside_a_site_class(self):
        """P6 and 9.4's P-MONO: a deleted member of a place list never releases a rival, and no control guards an act's
        place list against a site class (3.2.3's pair controls guard two objects' places). A balloon dilation listed at
        the distal esophagus and the pylorus is claimed by 43249 (esophageal) and 43245 (gastric and duodenal); with
        the esophageal member deleted the two still compete - read by its listed places, 43249 would drop it and 43245
        would go READY. The cost (v1's D29 filter, D163's G1 measurement): on a dilation listed at the pylorus alone,
        and at an anastomosis (FRESH-2 fb07's shape), 43245 READY on it is held competing_codes beside 43249 (the
        step's NOTES record the question). A device established as another class still sets an act apart (R4: one
        fact, no list)."""
        for name, places in (('spanning', (Landmark.DISTAL_ESOPHAGUS, Landmark.PYLORUS)),
                             ('the esophageal member deleted', (Landmark.PYLORUS,)),
                             ('at an anastomosis', (Landmark.ANASTOMOSIS,))):
            with self.subTest(name):
                R = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=sup(Device.BALLOON),
                                                         places=tuple(sup(place) for place in places)))
                self.assertIn(E3, C.claims('43249', R, ()))
                self.assertEqual(compete(R, member('sel:0', '43245', supporting=(E3,)), member('sel:1', '43249')),
                                 {'sel:0': ('43249',), 'sel:1': ('43245',)})
        wire = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE),
                                                    places=(sup(Landmark.PYLORUS),)))
        self.assertEqual(compete(wire, member('sel:0', '43245', supporting=(E3,)), member('sel:1', '43249')), {})

    def test_bleeding_control_beside_the_polypectomy_never_competes(self):
        """D163's control (G0's cost): 45382 held beside the polypectomy a clip may be part of claims the clip, never
        the snare - a snare is no bleeding control - so 45385 stays READY."""
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.SNARE, lesion=sup(L1)),
                   E3: act(Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS), lesion=sup(L1))}, COLONOSCOPY)
        self.assertEqual(C.claims('45382', R, ()), (E3,))
        self.assertEqual(compete(R, member('sel:0', '45385', supporting=(E2,)), member('sel:1', '45382')), {})
        prophylaxis = build({E1: act(Kind.EXAMINATION), E3: act(Kind.CLIP, purpose=sup(ct.Purpose.PROPHYLAXIS))},
                            COLONOSCOPY)
        self.assertEqual(C.claims('45382', prophylaxis, ()), ())  # D157: by possibly only
        unknown = build({E1: act(Kind.EXAMINATION), E3: act(Kind.CLIP)}, COLONOSCOPY)
        self.assertEqual(C.claims('45382', unknown, ()), (E3,))  # a clip whose purpose may be hemostasis

    def test_an_umbrella_act_is_claimed_by_no_code(self):
        """An act whose kind is established as an umbrella (removal, intervention) is none of its members by possibly
        (4.2): no code claims it, as v1's READY codes never did, so an "intervention was performed" never holds every
        READY code of its family competing_codes. A doubt's reading of a member makes it that member's candidate."""
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.SNARE), E3: act(Kind.BIOPSY), E7: act(Kind.REMOVAL),
                   E8: act(Kind.INTERVENTION)}, COLONOSCOPY)
        for code in ('45385', '45384', '45390', '45380'):
            with self.subTest(code=code):
                self.assertFalse({E7, E8} & set(C.claims(code, R, ())))
        self.assertEqual(compete(R, member('sel:0', '45385', supporting=(E2,)), member('sel:1', '45384'),
                                 member('sel:2', '45380', supporting=(E3,))), {})
        read_as_snare = build({E1: act(Kind.EXAMINATION),
                               E7: act(doubted(Kind.REMOVAL, Kind.SNARE))}, COLONOSCOPY)
        self.assertEqual(C.claims('45385', read_as_snare, ()), (E7,))

    def test_a_hemostatic_injection_is_a_bleeding_control_for_coding(self):
        """The catalogue's clip rule, by possibly: an injection whose purpose is supported hemostasis is a bleeding
        control, which no injection code accounts for - 43236 claims nothing and 43255 READY on it is never held; one
        whose purpose may be hemostasis (D157's doubt) may be either, and the two compete."""
        egd = {X1: session_of(SessionKind.EGD)}
        hemostatic = build({E1: act(Kind.EXAMINATION, X1),
                            E2: act(Kind.INJECTION, X1, purpose=sup(ct.Purpose.HEMOSTASIS))}, egd)
        self.assertEqual((C.claims('43236', hemostatic, ()), C.claims('43255', hemostatic, ())), ((), (E2,)))
        self.assertEqual(compete(hemostatic, member('sel:0', '43255', supporting=(E2,)), member('sel:1', '43236')), {})
        unknown = build({E1: act(Kind.EXAMINATION, X1), E2: act(Kind.INJECTION, X1)}, egd)
        self.assertEqual(compete(unknown, member('sel:0', '43255'), member('sel:1', '43236')),
                         {'sel:0': ('43236',), 'sel:1': ('43255',)})

    def test_route_b_claims_every_act_of_its_kind_of_any_family(self):
        """Route (b) (46221, an unreconciled band ligation): every act that may be of its kind, of any family - its
        regions (the rectum, the anus) are not read, by P6 (a listed place outside them could be a short list's)."""
        R = build({E2: act(Kind.BAND_LIGATION, X1, places=(sup(Landmark.RECTUM),)),
                   E3: act(Kind.BAND_LIGATION, X1, places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                   E4: act(Kind.BAND_LIGATION, X1), E5: act(Kind.BIOPSY, X1)}, COLONOSCOPY)
        self.assertEqual(C.claims('46221', R, ()), (E2, E3, E4))
        self.assertEqual(C.claims('99213', R, ()), ())  # nothing of its kind
        self.assertEqual(C.claims('99999', R, ()), ())  # route (d): no group, no claim


# --- the same-day E/M (C-3; D81, D94, D109, D111, D130, D133, D134; D113) ---------------------------------------------


def office(*events_, separate=None, sessions=None, unlisted=(), visit=None) -> FactSet:
    """An office visit X0 (this encounter) with its visit E0 (``visit``: E0's facts instead), and ``events_`` as
    (id, facts) pairs."""
    events = {E0: visit if visit is not None else act(Kind.EM_VISIT, X0, separate=separate)}
    for subject, facts in events_:
        events[subject] = facts
    all_sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS))}
    all_sessions.update(sessions if sessions is not None else {X1: session_of(SessionKind.COLONOSCOPY)})
    return build(events, all_sessions, unlisted=unlisted)


VISIT = member('sel:0', '99213', X0, (E0,))


def same_day(R: FactSet, *codes) -> tuple:
    day = C.procedure_day(R, codes)
    return day, C.same_day_holds(VISIT, R, day)


class SameDayEM(SimpleTestCase):
    """v1's SameDayEM class re-expressed: D21 by date of service (ADJUDICATION C-3), over date relations (4.7)."""

    def test_a_procedure_today_holds_the_visit(self):
        R = office((E1, act(Kind.EXAMINATION)), (E2, act(Kind.SNARE)))
        day, held = same_day(R)
        self.assertEqual((day.procedure_day, day.done, day.done_acts), (True, (SessionKind.COLONOSCOPY,), (E1, E2)))
        self.assertEqual(len(held), 1)
        self.assertEqual((held[0].fact, held[0].rank, held[0].kind, held[0].cause, held[0].subject, held[0].attribute),
                         ('separate_em', 20, ItemKind.QUESTION, C.SAME_DAY_CAUSE, E0,
                          A.VISIT_SEPARATELY_IDENTIFIABLE))
        self.assertEqual(held[0].spans, span_of(E1, E2))

    def test_a_separately_identifiable_visit_stated_is_not_asked(self):
        R = office((E1, act(Kind.EXAMINATION)), separate=sup(STATED, spans=(Span(10, 60),)))
        day, held = same_day(R)
        self.assertEqual((day.procedure_day, held), (True, ()))
        self.assertEqual(C.separate_statement(R, (E0,)), C.SeparateStatement(stated=E0, spans=(Span(10, 60),)))

    def test_the_separate_statement_negated_is_an_explanation_quoting_the_denial(self):
        """4.3 C3+SEP: "separately_identifiable denied: separate_em, the denial quoted" - an explanation, never
        READY."""
        R = office((E1, act(Kind.EXAMINATION)), separate=neg(STATED, spans=(Span(10, 60),)))
        day, held = same_day(R)
        self.assertEqual((held[0].fact, held[0].kind, held[0].result, held[0].subject),
                         ('separate_em', ItemKind.EXPLANATION, Res.NEGATED, E0))
        self.assertEqual(held[0].spans, tuple(sorted((Span(10, 60),) + span_of(E1))))
        unresolved = office((E1, act(Kind.EXAMINATION)), separate=unres(STATED))
        self.assertEqual([h.kind for h in same_day(unresolved)[1]], [ItemKind.QUESTION])  # not established: asked

    def test_c3_a_procedure_earlier_today_in_a_separate_same_day_session_is_the_same_date_of_service(self):
        """The refuter's C-3 scenario, and 9.3's "C-3 with a separate same-day session": the EGD is another encounter's
        ("earlier today") but on the date of service, so the visit is held."""
        R = office((E1, act(Kind.EXAMINATION, X2)),
                   sessions={X2: session_of(SessionKind.EGD, encounter=sup(SEPARATE))})
        day, held = same_day(R)
        self.assertEqual((day.done, keys(held)), ((SessionKind.EGD,), ['separate_em']))

    def test_c3_an_undatable_procedure_asks_its_time(self):
        for name, date in (('unknown', SILENT), ('unresolved', unres(ON)), ('doubted', doubted(ON, EARLIER)),
                           ('unresolved earlier', unres(EARLIER))):
            with self.subTest(name):
                R = office((E1, act(Kind.EXAMINATION, X2, date=date)), sessions={X2: session_of(SessionKind.EGD)})
                day, held = same_day(R)
                self.assertEqual((day.procedure_day, day.undatable), (False, (E1,)))
                self.assertEqual([(h.fact, h.rank, h.kind, h.subject, h.attribute, h.result) for h in held],
                                 [('event_time', 6, ItemKind.QUESTION, E1, A.DATE_RELATION, date.result)])
        cause = same_day(office((E1, act(Kind.EXAMINATION, X2, date=unres(ON))),
                                sessions={X2: session_of(SessionKind.EGD)}))[1][0].cause
        self.assertEqual(cause, 'appraisal:unclear')

    def test_a_procedure_of_another_date_is_no_procedure_day(self):
        R = office((E1, act(Kind.EXAMINATION, X2, date=sup(EARLIER))), sessions={X2: session_of(SessionKind.EGD)})
        day, held = same_day(R)
        self.assertEqual((day.procedure_day, day.undatable_any, held), (False, False, ()))

    def test_c3_an_unlisted_act_is_an_undatable_possible_procedure(self):
        """FINAL-V2 3.2.6 rule 5, and 9.3's "C-3 ... with an unlisted act": an unlisted act is an undatable possible
        procedure - event_time, cause unlisted. An unlisted denial, and an unlisted act of an E/M kind, are not."""
        unlisted = (UnlistedStatement(units=(Span(700, 740),), what=ct.UnlistedWhat.ACT, kind=None, session=None),
                    UnlistedStatement(units=(Span(800, 840),), what=ct.UnlistedWhat.DENIAL, kind=None, session=None),
                    UnlistedStatement(units=(Span(850, 890),), what=ct.UnlistedWhat.ACT, kind=Kind.EM_VISIT,
                                      session=X0))
        R = office(unlisted=unlisted)
        day, held = same_day(R)
        self.assertEqual((day.undatable, day.undatable_unlisted), ((), (0,)))
        self.assertEqual([(h.fact, h.subject, h.cause, h.spans) for h in held],
                         [('event_time', None, C.UNLISTED_CAUSE, (Span(700, 740),))])
        self.assertEqual(same_day(office(unlisted=unlisted[1:]))[1], ())

    def test_the_performer_is_not_read(self):
        """Legacy parity (S3 hazard 7, 4.13): a procedure done today by another clinician makes the procedure day."""
        R = office((E1, act(Kind.EXAMINATION, performer=sup(OTHER_CLINICIAN), entry=sup(ct.Owner.OTHER_CLINICIAN))))
        self.assertEqual(keys(same_day(R)[1]), ['separate_em'])

    def test_a_doubted_procedure_on_the_date_is_a_possible_procedure_day(self):
        """[R:HO-1]: a doubted act, and one whose status pass 2 did not establish, is possibly positive: the procedure
        day is possible and separate_em is asked. A denied or planned procedure makes none."""
        for name, status in (('doubted', doubted(PERFORMED)), ('unresolved', unres(PERFORMED))):
            with self.subTest(name):
                day, held = same_day(office((E1, act(Kind.EXAMINATION, status=status))))
                self.assertEqual((day.done, day.possible, day.possible_acts, keys(held)),
                                 ((), (SessionKind.COLONOSCOPY,), (E1,), ['separate_em']))
        for name, status in (('denied', neg(PERFORMED)), ('planned', sup(PLANNED))):
            with self.subTest(control=name):
                day, held = same_day(office((E1, act(Kind.EXAMINATION, status=status))))
                self.assertEqual((day.procedure_day, held), (False, ()))

    def test_d109_an_act_of_a_procedural_kind_filed_under_the_visit_is_another_gi_service(self):
        """D109, D111: a band ligation filed in the visit's own session (or in a non-GI one) makes the procedure day by
        its kind, named as another GI service. A digital rectal examination (an examination whose device is manual)
        never does (E13)."""
        R = office((E1, act(Kind.BAND_LIGATION, X0)))
        day, held = same_day(R)
        self.assertEqual((day.done, keys(held)), ((SessionKind.OTHER_GI,), ['separate_em']))
        not_gi = office((E1, act(Kind.BAND_LIGATION, X3)), sessions={X3: session_of(SessionKind.NOT_GI)})
        self.assertEqual(same_day(not_gi)[0].done, (SessionKind.OTHER_GI,))
        digital = office((E1, act(Kind.EXAMINATION, X0, device=sup(Device.MANUAL))))
        self.assertEqual(same_day(digital), (C.ProcedureDay(), ()))

    def test_d130_an_act_of_kind_other_counts_by_its_class(self):
        """D130 rewired (4.7: other_class procedure; its head words are gone): an act of kind other filed under the
        visit is a POSSIBLE procedure when its class may be a procedure, never a done one; a laboratory, an order or
        counseling established as such is none."""
        for name, other_class in (('procedure', sup(ct.OtherClass.PROCEDURE)), ('class not given', SILENT),
                                  ('procedure unresolved', unres(ct.OtherClass.PROCEDURE))):
            with self.subTest(name):
                day, held = same_day(office((E1, act(Kind.OTHER, X0, other_class=other_class))))
                self.assertEqual((day.done, day.possible, keys(held)), ((), (SessionKind.OTHER_GI,), ['separate_em']))
        for name, other_class in (('laboratory', sup(ct.OtherClass.LABORATORY)), ('order', sup(ct.OtherClass.ORDER)),
                                  ('counseling', sup(ct.OtherClass.COUNSELING))):
            with self.subTest(control=name):
                self.assertEqual(same_day(office((E1, act(Kind.OTHER, X0, other_class=other_class)))),
                                 (C.ProcedureDay(), ()))

    def test_the_visit_itself_and_its_sedation_never_make_a_procedure_day(self):
        R = office((E1, act(Kind.EM_PROLONGED, X0)), (E2, act(Kind.MODERATE_SEDATION, X4)),
                   sessions={X4: session_of(SessionKind.SEDATION)})
        self.assertEqual(same_day(R), (C.ProcedureDay(), ()))

    def test_a_counted_procedural_code_adds_its_family(self):
        """engine._encounter: a counted procedural code adds its family to the done list when the per-code rule supports
        it, to the possible list otherwise; a code that is no procedure adds nothing."""
        R = office()
        done = C.ProceduralCode('45385', SessionKind.COLONOSCOPY, procedural=True, supported=True)
        held = C.ProceduralCode('43239', SessionKind.EGD, procedural=True, supported=False)
        not_procedure = C.ProceduralCode('91010', SessionKind.MOTILITY, procedural=False, supported=True)
        day, holds = same_day(R, done, held, not_procedure)
        self.assertEqual((day.done, day.possible, keys(holds)),
                         ((SessionKind.COLONOSCOPY,), (SessionKind.EGD,), ['separate_em']))

    def test_the_separate_statement_is_read_from_todays_visits_only(self):
        """D113: the code's own visit, then another visit of this encounter (fb10: the GERD visit stated beside the
        assessment that "is not a separate E/M service" - a denial never releases, nor silences another visit's
        statement); never another encounter's visit."""
        other_today = (E5, act(Kind.EM_VISIT, X0, separate=sup(STATED)))
        R = office((E1, act(Kind.EXAMINATION)), other_today, separate=neg(STATED))
        self.assertEqual(C.separate_statement(R, (E0,)).stated, E5)
        self.assertEqual(same_day(R)[1], ())
        another_encounter = office((E1, act(Kind.EXAMINATION)), (E5, act(Kind.EM_VISIT, X4, separate=sup(STATED))),
                                   sessions={X1: session_of(SessionKind.COLONOSCOPY),
                                             X4: session_of(SessionKind.OFFICE_EM, encounter=sup(SEPARATE))})
        self.assertIsNone(C.separate_statement(another_encounter, (E0,)).stated)
        self.assertEqual(keys(same_day(another_encounter)[1]), ['separate_em'])
        another_date = office((E1, act(Kind.EXAMINATION)), (E5, act(Kind.EM_VISIT, X0, separate=sup(STATED),
                                                                    date=sup(EARLIER))))
        self.assertIsNone(C.separate_statement(another_date, (E0,)).stated)

    def test_f1_a_weakening_never_releases_an_em_code_held_for_an_undatable_act(self):
        """The refutation's F1 (9.4 P-MONO; C-3: an undatable event is "a question and never READY"): the visit's
        statement documented and a colonoscopy act E1 told with no date relation, 99213 is held event_time. Each
        weakening below creates a POSSIBLE procedure day; v1's rule (event_time only with no procedure day at all)
        then released 99213. It stays held event_time on E1: a possible procedure day never moots the undatable act."""
        undatable = (E1, act(Kind.EXAMINATION, X1, date=SILENT))
        shapes = {
            'a digital examination': ((E4, act(Kind.EXAMINATION, X0, device=sup(Device.MANUAL))),
                                      (E4, act(Kind.EXAMINATION, X0, device=unres(Device.MANUAL))),
                                      (E4, act(Kind.EXAMINATION, X0, device=doubted(Device.MANUAL)))),
            'a banding planned today': ((E2, act(Kind.BAND_LIGATION, X0, status=sup(PLANNED))),
                                        (E2, act(Kind.BAND_LIGATION, X0, status=unres(PLANNED)))),
            'labs drawn at the visit': ((E5, act(Kind.OTHER, X0, other_class=sup(ct.OtherClass.LABORATORY))),
                                        (E5, act(Kind.OTHER, X0, other_class=doubted(ct.OtherClass.LABORATORY,
                                                                                     ct.OtherClass.PROCEDURE)))),
        }
        for name, (before, *weakened) in shapes.items():
            with self.subTest(name):
                day, held = same_day(office(undatable, before, separate=sup(STATED)))
                self.assertEqual((day.procedure_day, [(h.fact, h.subject) for h in held]),
                                 (False, [('event_time', E1)]))
                for after in weakened:
                    day, held = same_day(office(undatable, after, separate=sup(STATED)))
                    self.assertEqual((day.procedure_day, day.established), (True, False))
                    self.assertEqual([(h.fact, h.subject) for h in held], [('event_time', E1)])
        visit_doubted = office(undatable, visit=act(doubted(Kind.EM_VISIT, Kind.EXAMINATION), X0,
                                                    separate=sup(STATED)))
        day, held = same_day(visit_doubted)
        self.assertEqual((day.possible_acts, [(h.fact, h.subject) for h in held]), ((E0,), [('event_time', E1)]))

    def test_an_established_procedure_day_moots_an_undatable_act_beside_a_documented_statement(self):
        """v1's release, kept where no weakening can reach it: a done colonoscopy today (an established procedure day)
        and the separate statement documented, an undatable act beside them decides nothing for 99213 - the day is a
        procedure day whatever its date - so 99213 is not held (the refutation's option (A) would hold it event_time;
        the step's NOTES record the question). A counted procedural code alone, supported or not, never establishes the
        day (its support rests on its own facts, outside 99213's closure: 4.9): the day is possible, and the time is
        asked."""
        undatable = (E3, act(Kind.EXAMINATION, X2, date=SILENT))
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        R = office((E1, act(Kind.EXAMINATION)), undatable, separate=sup(STATED), sessions=sessions)
        day, held = same_day(R)
        self.assertEqual((day.established, day.undatable, held), (True, (E3,), ()))
        alone = office(undatable, separate=sup(STATED), sessions=sessions)
        for supported in (True, False):
            with self.subTest(supported=supported):
                code = C.ProceduralCode('45385', SessionKind.COLONOSCOPY, procedural=True, supported=supported)
                day, held = same_day(alone, code)
                self.assertEqual((day.procedure_day, day.established), (True, False))
                self.assertEqual([(h.fact, h.subject) for h in held], [('event_time', E3)])

    def test_on_a_procedure_day_with_no_statement_separate_em_is_the_one_hold(self):
        """v1's item: on a procedure day with no separate statement, the hold is separate_em, whatever undatable act is
        beside it (event_time, rank 6, would otherwise be asked first though it decides nothing the statement does
        not)."""
        undatable = (E3, act(Kind.EXAMINATION, X2, date=SILENT))
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        for name, procedure in (('done', act(Kind.EXAMINATION)), ('possible', act(Kind.EXAMINATION,
                                                                                    status=unres(PERFORMED)))):
            with self.subTest(name):
                day, held = same_day(office((E1, procedure), undatable, sessions=sessions))
                self.assertEqual((day.undatable, keys(held)), ((E3,), ['separate_em']))

    def test_an_event_that_may_be_a_visit_or_a_procedure_is_read_as_a_procedure(self):
        """Fail-closed (the refutation's T1, mutant R6): an event is skipped as the visit only when EVERY kind it may be
        is an E/M kind. A colonoscopy examination whose kind carries a doubt reading em_visit still makes the
        procedure day, and 99213 is held separate_em; an event that can only be a visit or prolonged time never
        does."""
        R = office((E1, act(doubted(Kind.EXAMINATION, Kind.EM_VISIT))))
        day, held = same_day(R)
        self.assertEqual((day.done_acts + day.possible_acts, keys(held)), ((E1,), ['separate_em']))
        only_em = office((E1, act(doubted(Kind.EM_VISIT, Kind.EM_PROLONGED), X0)))
        self.assertEqual(same_day(only_em), (C.ProcedureDay(), ()))

    def test_a_digital_examination_left_open_is_a_possible_procedure_never_a_done_one(self):
        """E13 by facts: an examination filed under the visit is no procedure when its device is supported manual (a
        digital examination); with the device not established it may be one - a POSSIBLE procedure, never a done one
        (a weakened device must not create an established procedure day, F1); established as another device, or
        manual negated, it is done."""
        cases = {'manual': (sup(Device.MANUAL), None), 'unresolved': (unres(Device.MANUAL), False),
                 'doubted': (doubted(Device.MANUAL), False), 'silent': (None, False),
                 'endoscope': (sup(Device.ENDOSCOPE), True), 'manual negated': (neg(Device.MANUAL), True)}
        for name, (device, done) in cases.items():
            with self.subTest(name):
                day = same_day(office((E1, act(Kind.EXAMINATION, X0, device=device))))[0]
                if done is None:
                    self.assertFalse(day.procedure_day)
                else:
                    self.assertEqual((day.procedure_day, day.established, day.done_acts if done else day.possible_acts),
                                     (True, done, (E1,)))

    def test_another_visits_statement_needs_its_performer_established_as_the_team(self):
        """D113 read monotonically: another visit of this encounter lends its statement only when its performer is
        supported documenting_team. One told as another clinician's lends none, and weakening that performer (to
        unresolved) must not lend it either - v1's "no performer verified to another" did, releasing 99213."""
        expected = {'documenting team': (sup(TEAM), E5), 'another clinician': (sup(OTHER_CLINICIAN), None),
                    'another clinician, unresolved': (unres(OTHER_CLINICIAN), None), 'silent': (None, None)}
        for name, (performer, stated) in expected.items():
            with self.subTest(name):
                R = office((E1, act(Kind.EXAMINATION)),
                           (E5, act(Kind.EM_VISIT, X0, separate=sup(STATED), performer=performer)))
                self.assertEqual(C.separate_statement(R, (E0,)).stated, stated)
                self.assertEqual(keys(same_day(R)[1]), [] if stated is not None else ['separate_em'])

    def test_visit_basis_is_the_first_supported_basis_of_the_visits(self):
        """FINAL-V2 5.5 maps v1's visit_basis here (the refutation's F4): the first visit whose visit.basis is
        supported, with its value and spans; a basis not established is none (v1's usable basis)."""
        mdm, time = ct.EmBasis.MEDICAL_DECISION_MAKING, ct.EmBasis.TOTAL_TIME
        R = office((E5, act(Kind.EM_VISIT, X0, basis=sup(mdm, spans=(Span(20, 50),)))),
                   visit=act(Kind.EM_VISIT, X0, basis=unres(time)))
        self.assertEqual(C.visit_basis(R, (E0, E5)), C.VisitBasis(event=E5, basis=mdm, spans=(Span(20, 50),)))
        self.assertIsNone(C.visit_basis(R, (E0,)))
        self.assertIsNone(C.visit_basis(R, ()))

    def test_a_code_outside_the_em_families_gets_no_same_day_hold(self):
        R = office((E1, act(Kind.EXAMINATION)))
        day = C.procedure_day(R)
        self.assertEqual(C.same_day_holds(member('sel:1', '45378', X1, (E1,)), R, day), ())
        self.assertEqual([keys(C.same_day_holds(member('sel:1', code, X0, (E0,)), R, day)) for code in ('99417',)],
                         [['separate_em']])


# --- the separate-lesion modifier review (FINAL 7.9) ------------------------------------------------------------------


class ModifierReview(SimpleTestCase):
    """v1's ModifierReview class re-expressed: target.lesion supported and distinct_from supported (4.7)."""

    def two_lesions(self, distinct=True, rectal=L2) -> tuple:
        lesions = {L1: lesion_of(places=(Landmark.SIGMOID_COLON,), distinct=(L2,) if distinct else ()),
                   L2: lesion_of(places=(Landmark.RECTUM,))}
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.SNARE, lesion=sup(L1), device=sup(Device.COLD_SNARE)),
                   E3: act(Kind.BIOPSY, lesion=sup(rectal) if rectal is not None else unres(L2),
                           device=sup(Device.COLD_FORCEPS))}, COLONOSCOPY, lesions=lesions)
        members = [member('sel:0', '45380', supporting=(E3,)), member('sel:1', '45385', supporting=(E2,))]
        return R, members

    def test_distinct_lesions_offer_the_separate_lesion_review(self):
        R, members = self.two_lesions()
        review = C.modifier_review(R, members[0], members)
        self.assertEqual((review.key, review.code, review.session, review.lesions, review.acts, review.options),
                         ('sel:0', '45380', X1, (L2,), (E3,), (C.Modifier.M59, C.Modifier.XS)))
        self.assertEqual(review.partners, (C.Partner(key='sel:1', code='45385', lesions=(L1,), acts=(E2,)),))
        # distinct_from is read in either lesion's list
        self.assertEqual(C.modifier_review(R, members[1], members).partners[0].code, '45380')

    def test_lesions_not_established_distinct_never_pair(self):
        """An unknown identity never pairs (4.11): no distinct_from, or a lesion not supported."""
        for name, (distinct, rectal) in (('no distinct_from', (False, L2)), ('lesion unresolved', (True, None))):
            with self.subTest(name):
                R, members = self.two_lesions(distinct=distinct, rectal=rectal)
                self.assertIsNone(C.modifier_review(R, members[0], members))
        R, members = self.two_lesions()
        twice = [members[0], member('sel:2', '45380', supporting=(E2,))]
        self.assertIsNone(C.modifier_review(R, twice[0], twice))  # one code twice never pairs
        apart = [members[0], member('sel:1', '45385', session=X2, supporting=(E2,))]
        self.assertIsNone(C.modifier_review(R, apart[0], apart))  # another session never pairs


# --- the constants and rows, pinned to v1's ---------------------------------------------------------------------------


class CopiesPinned(SimpleTestCase):
    """v1's CopiesPinned re-expressed: the holds are HeldFacts (their sentences are step 3c's wording); the constants
    and rows equal v1's by value."""

    def test_the_constants_and_rows(self):
        self.assertEqual(tuple(kind.value for kind in C.DISTINCT_LESION_KINDS), v1_combination.DISTINCT_LESION_KINDS)
        self.assertEqual(tuple(kind.value for kind in C.DISTINCT_LESION_KINDS), v1_engine.DISTINCT_LESION_KINDS)
        self.assertEqual(tuple(option.value for option in C.Modifier), v1_combination.DISTINCT_LESION_OPTIONS)
        self.assertEqual(tuple(option.value for option in C.Modifier), v1_checks.DISTINCT_LESION_OPTIONS)
        pairs = [('45378', None), ('45385', {'endo_base': '45378'}), ('45380', {})]
        self.assertEqual(C.endoscopic_rows(pairs), v1_combination.endoscopic_rows(pairs))
        self.assertEqual(C.endoscopic_rows(pairs), v1_engine.endoscopic_rows(pairs))

    def test_the_same_day_kinds_equal_v1s_by_value_and_read_the_bundled_and_unsupported_kinds(self):
        """D109, D111: every kind but the visit's, prolonged time, moderate sedation and other - read from D191's one
        table (FAMILY_KINDS), equal to the catalogue entries' kinds with the examination and the umbrellas, and to
        v1's SAME_DAY_KINDS by value (its 'eus_exam' is Kind.EXAMINATION, C-1). The hand-off 1e:R3: the bundled and
        unsupported kinds are read from catalogue.BUNDLED_KINDS and UNSUPPORTED_KINDS (clip, cannulation, ESD,
        balloon expulsion are in only through them)."""
        self.assertEqual(C.SAME_DAY_KINDS, frozenset(Kind) - {Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION,
                                                              Kind.OTHER})
        self.assertEqual(C.SAME_DAY_KINDS, frozenset(Kind.EXAMINATION if value == 'eus_exam' else Kind(value)
                                                     for value in v1_combination.SAME_DAY_KINDS))
        entries = frozenset(kind for family in catalogue.PROCEDURAL_FAMILIES
                            for kind in (*catalogue.FAMILY_ACTS[family], *catalogue.BUNDLED_KINDS[family],
                                         *catalogue.UNSUPPORTED_KINDS[family]))
        self.assertEqual(C.SAME_DAY_KINDS, (entries - {Kind.OTHER}) | {Kind.EXAMINATION} | set(catalogue.UMBRELLAS))
        via_tables = frozenset().union(*(catalogue.BUNDLED_KINDS[family] | catalogue.UNSUPPORTED_KINDS[family]
                                         for family in catalogue.PROCEDURAL_FAMILIES))
        named = frozenset(kind for family in catalogue.PROCEDURAL_FAMILIES for kind in catalogue.FAMILY_ACTS[family])
        self.assertEqual(via_tables - named, {Kind.CLIP, Kind.CANNULATION, Kind.ESD, Kind.BALLOON_EXPULSION})

    def test_the_same_day_families_are_v1s_but_the_non_gi_catch_all(self):
        """D81: v1's SAME_DAY_FAMILIES by value, less gi.unsupported - a non-GI act counts by its kind, or by its class
        for kind other (4.7), never by its family alone (the step's NOTES record the change)."""
        slug = {family: f'gi.{family.value}' for family in SessionKind}
        slug[SessionKind.OTHER_GI], slug[SessionKind.NOT_GI] = 'gi.other', 'gi.unsupported'
        self.assertEqual({slug[family] for family in C.SAME_DAY_FAMILIES},
                         set(v1_combination.SAME_DAY_FAMILIES) - {'gi.unsupported'})

    def test_each_hold_is_at_its_rank_row_and_the_combination_rules_raise_only_these(self):
        """4.8's RANK: base_included 21, competing_codes 22, separate_em 20, event_time 6 - each among
        requirements.RULES' items for the combination and C3+SEP rows."""
        rows = {rq.Requirement.COMBINATION, rq.Tag.C3_SEP}
        raised = {item for row in rows for item in rq.RULES[row].asks + rq.RULES[row].explains}
        for item, rank in ((C.BASE_ITEM, 21), (C.COMPETING_ITEM, 22), (C.SEPARATE_ITEM, 20), (C.TIME_ITEM, 6)):
            with self.subTest(item=item.fact):
                self.assertIn(item, raised)
                self.assertEqual(item.rank.value, rank)

    def test_no_cause_names_a_vendor(self):
        causes = (C.BASE_CAUSE, C.WITHIN_CAUSE, C.COMPETING_CAUSE, C.SAME_DAY_CAUSE, C.UNLISTED_CAUSE,
                  *(f'appraisal:{value.value}' for value in C.APPRAISAL_CAUSES.values()))
        for cause in causes:
            for vendor in ('gemini', 'google', 'corti', 'astra', 'fable', 'openai', 'anthropic', 'claude'):
                self.assertNotIn(vendor, cause.lower())


# --- the set level, determinism, reads and monotonicity ---------------------------------------------------------------


def encounter() -> tuple:
    """An office visit X0 and a colonoscopy X1 today: a snare E2 (45385), a biopsy E3 in doubt, labs drawn at the visit
    (E4, kind other, its class laboratory)."""
    R = office((E1, act(Kind.EXAMINATION)), (E2, act(Kind.SNARE, lesion=sup(L1))),
               (E3, act(Kind.BIOPSY, status=doubted(PERFORMED))),
               (E4, act(Kind.OTHER, X0, other_class=sup(ct.OtherClass.LABORATORY))))
    members = [member('sel:0', '99213', X0, (E0,)), member('sel:1', '45378', X1, (E1,), procedural=True,
                                                           supported=True),
               member('sel:2', '45385', X1, (E2,), procedural=True, supported=True), member('sel:3', '45380', X1)]
    coding = {X0: C.SessionActs(), X1: C.SessionActs(reportable=(E2,), doubted=(E3,))}
    return R, members, coding


class Combine(SimpleTestCase):
    def test_combine_gives_each_member_its_combination_holds(self):
        R, members, coding = encounter()
        combined = C.combine(members, coding, R)
        self.assertEqual({key: keys(held) for key, held in combined.held.items()},
                         {'sel:0': ['separate_em'], 'sel:1': ['base_included'], 'sel:2': [], 'sel:3': []})
        self.assertEqual(combined.bases['sel:1'].named_codes, ('45385', '45380'))
        self.assertEqual(combined.day.done, (SessionKind.COLONOSCOPY,))
        self.assertEqual(combined.claims['sel:3'], (E3,))
        self.assertTrue(all(isinstance(item, HeldFact) for held in combined.held.values() for item in held))

    def test_p_det_identical_inputs_give_identical_outputs(self):
        first, second = C.combine(*_args()), C.combine(*_args())
        self.assertEqual(dict(first.held), dict(second.held))
        self.assertEqual((dict(first.claims), dict(first.competes), first.day), (dict(second.claims),
                                                                                 dict(second.competes), second.day))

    def test_the_rules_read_only_claimed_attributes(self):
        """P-READSET (9.4), for this module: every fact the combination reads (recorded at facts.fact and
        facts.members) is an attribute CLAIMED claims for its object class - an event's as an act or a statement, a
        session's, a lesion's."""
        read: set = set()
        real_fact, real_members = F.fact, F.members

        def fact_(R, subject, attribute):
            read.add((subject.family if subject is not None else None, attribute))
            return real_fact(R, subject, attribute)

        def members_(R, subject, attribute):
            read.add((subject.family if subject is not None else None, attribute))
            return real_members(R, subject, attribute)

        with mock.patch.object(F, 'fact', fact_), mock.patch.object(F, 'members', members_):
            for R, members, coding in (encounter(), _dilation_set(), _within_set()):
                C.combine(members, coding, R)
                C.visit_basis(R, tuple(R.events))
        claimed = {
            IdFamily.EVENT: {entry.attribute for cls in (rq.ObjectClass.ACT, rq.ObjectClass.STATEMENT)
                             for entry in rq.CLAIMED[cls]},
            IdFamily.SESSION: {entry.attribute for entry in rq.CLAIMED[rq.ObjectClass.SESSION]},
            IdFamily.LESION: {entry.attribute for entry in rq.CLAIMED[rq.ObjectClass.LESION]},
        }
        outside = {(family, attribute) for family, attribute in read if attribute not in claimed.get(family, set())}
        self.assertEqual(outside, set())
        self.assertIn((IdFamily.EVENT, A.OTHER_CLASS), read)
        self.assertIn((IdFamily.SESSION, A.PART_OF_SESSION), read)
        self.assertIn((IdFamily.EVENT, A.VISIT_BASIS), read)


def _args():
    R, members, coding = encounter()
    return members, coding, R


def _dilation_set():
    R = dilations(act(Kind.DILATION, device=sup(Device.BALLOON), lesion=sup(L1)),
                  act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE), places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                  lesions={L1: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS,))})
    return R, [member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43248', supporting=(E3,)),
               member('sel:2', '43235', supporting=(E1,))], {X1: C.SessionActs()}


def _within_set():
    R = egd_eus(tract=unres(ct.Tract.UPPER), part_of=unres(X2))
    return R, [member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,))], {X1: C.SessionActs(),
                                                                                           X2: C.SessionActs()}


# Monotone: P-MONO (9.4) over the combination: a weakening (an established fact to unresolved, an added doubt, a deleted
# member of a place list) never shrinks a claim or a competition, never releases a held E/M code's same-day hold, and
# never loses a whole.

CODES = ('45385', '45384', '45380', '45390', '43249', '43248', '43245', '43264', '43265', '43239', '43251', '45378',
         '43235')
KINDS = (Kind.SNARE, Kind.HOT_BIOPSY, Kind.BIOPSY, Kind.REMOVAL, Kind.EMR, Kind.DILATION, Kind.STONE_EXTRACTION,
         Kind.LITHOTRIPSY, Kind.EXAMINATION, Kind.CLIP, Kind.OTHER)


def _choice(values):
    return st.sampled_from(values)


EVENT_FACTS = st.fixed_dictionaries({
    'kind': _choice(KINDS).map(sup),
    'status': _choice((sup(PERFORMED), neg(PERFORMED), sup(PLANNED), unres(PERFORMED), doubted(PERFORMED),
                       sup(Status.ATTEMPTED_NOT_COMPLETED))),
    'session': _choice((sup(X1), sup(X2), unres(X1), SILENT)),
    'date': _choice((sup(ON), sup(EARLIER), unres(ON), unres(EARLIER), SILENT)),
    'performer': _choice((sup(TEAM), sup(OTHER_CLINICIAN), unres(OTHER_CLINICIAN), SILENT)),
    'device': _choice((sup(Device.BALLOON), sup(Device.WIRE_BOUGIE), SILENT)),
    'lesion': _choice((sup(L1), sup(L2), SILENT)),
    'places': _choice(((), (sup(Landmark.DISTAL_ESOPHAGUS),), (sup(Landmark.PYLORUS),), (sup(Landmark.ANASTOMOSIS),),
                       (sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.PYLORUS)))),
    'other_class': _choice((sup(ct.OtherClass.PROCEDURE), sup(ct.OtherClass.LABORATORY), SILENT)),
})


# The same-day rule's own inputs (the refutation's T1: the suite's first property never set a statement, never weakened
# a kind toward an E/M or examination reading, a device toward manual, a class toward procedure, nor a session).
DAY_KINDS = (Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.EXAMINATION, Kind.BAND_LIGATION, Kind.SNARE, Kind.BIOPSY,
             Kind.OTHER, Kind.MODERATE_SEDATION)
DAY_SESSION_KINDS = (SessionKind.NOT_GI, SessionKind.SEDATION, SessionKind.EGD, SessionKind.OFFICE_EM)
DAY_FACTS = st.fixed_dictionaries({
    'kind': _choice(DAY_KINDS).map(sup),
    'status': _choice((sup(PERFORMED), neg(PERFORMED), sup(PLANNED), unres(PERFORMED), doubted(PERFORMED))),
    'session': _choice((sup(X0), sup(X1), sup(X3), unres(X1), SILENT)),
    'date': _choice((sup(ON), sup(EARLIER), unres(ON), SILENT)),
    'performer': _choice((sup(TEAM), sup(OTHER_CLINICIAN), unres(OTHER_CLINICIAN), SILENT)),
    'device': _choice((sup(Device.MANUAL), sup(Device.ENDOSCOPE), sup(Device.BALLOON), SILENT)),
    'other_class': _choice((sup(ct.OtherClass.PROCEDURE), sup(ct.OtherClass.LABORATORY), SILENT)),
    'separate': _choice((sup(STATED), neg(STATED), SILENT)),
})


def _weakened(found: Fact, how: int) -> Fact:
    """A weakening of 9.4's: an established fact to unresolved (its value kept), or an added doubt (its value kept, a
    reading added). The third, a deleted member of a multi-valued list, is the test's own."""
    if how == 0:
        return Fact(result=Res.UNRESOLVED, value=found.value, state=found.state, options=found.options,
                    reasons=(ct.Reason.APPRAISAL_UNCLEAR,), spans=found.spans)
    reading = {Kind: Kind.SNARE, Status: PERFORMED, ct.DateRelation: ON}.get(type(found.value), found.value)
    return Fact(result=Res.UNKNOWN, value=found.value, state=found.state,
                options=tuple(dict.fromkeys((*found.options, reading))), reasons=(ct.Reason.DOUBT_UNCLEAR,),
                spans=found.spans)


class Monotone(SimpleTestCase):
    @hypothesis.settings(max_examples=250, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(EVENT_FACTS, min_size=1, max_size=4), weaken=st.data())
    def test_p_mono_a_weakening_never_shrinks_a_claim_or_a_competition_or_releases_a_hold(self, events, weaken):
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E0] = act(Kind.EM_VISIT, X0)
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.EGD),
                    X2: session_of(SessionKind.ERCP, tract=sup(ct.Tract.UPPER))}
        lesions = {L1: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS,), distinct=(L2,)), L2: lesion_of()}
        controls = {(subject, A.TARGET_LESION, lesion): True for subject in facts for lesion in (L1, L2)}
        R = build(facts, sessions, lesions=lesions, controls=controls)
        established = [(subject, attribute, index) for subject, by in facts.items() if subject != E0
                       for attribute, values in by.items() for index, value in enumerate(values)
                       if F.established(value)]
        hypothesis.assume(established)
        subject, attribute, index = weaken.draw(st.sampled_from(established))
        how = weaken.draw(st.sampled_from((0, 1, 2)))
        changed = {key: dict(value) for key, value in facts.items()}
        values = list(facts[subject][attribute])
        if how == 2 and attribute is A.TARGET_PLACES:
            del values[index]  # a deleted member of a multi-valued list (9.4), its pair controls left as they were
        else:
            values[index] = _weakened(values[index], how % 2)
        changed[subject][attribute] = tuple(values)
        W = build(changed, sessions, lesions=lesions, controls=controls)
        members = [member(f'sel:{index}', code, X1) for index, code in enumerate(CODES)]
        for code in CODES:
            self.assertLessEqual(set(C.claims(code, R, ())), set(C.claims(code, W, ())), (code, subject, attribute))
        before, after = compete(R, *members), compete(W, *members)
        self.assertLessEqual({(key, rival) for key, rivals in before.items() for rival in rivals},
                             {(key, rival) for key, rivals in after.items() for rival in rivals})
        visit = member('sel:v', '99213', X0, (E0,))
        if C.same_day_holds(visit, R, C.procedure_day(R)):
            self.assertTrue(C.same_day_holds(visit, W, C.procedure_day(W)))
        self.assertLessEqual({whole.session for whole in C.wholes(R, X1)}, {whole.session for whole in C.wholes(W, X1)})

    @hypothesis.settings(max_examples=200, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(EVENT_FACTS, min_size=1, max_size=4),
                      kinds=st.lists(_choice((SessionKind.EGD, SessionKind.COLONOSCOPY, SessionKind.ERCP,
                                              SessionKind.EUS)), min_size=2, max_size=2), weaken=st.data())
    def test_p_mono_sessions_and_controls_weakened_never_shrink_a_claim(self, events, kinds, weaken):
        """P-MONO's other weakenings (the refutation's T1: the first property never weakened a session or a control):
        a session's kind, tract or encounter to unresolved or doubted (any reading of its domain), and an established
        pair control left not rejected. The claims and the competition never shrink, and no whole is lost."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        sessions = {X1: session_of(kinds[0], tract=sup(ct.Tract.UPPER)),
                    X2: session_of(kinds[1], tract=sup(ct.Tract.UPPER), encounter=sup(THIS))}
        lesions = {L1: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS,), distinct=(L2,)), L2: lesion_of()}
        controls = {(subject, A.TARGET_LESION, lesion): True for subject in facts for lesion in (L1, L2)}
        R = build(facts, sessions, lesions=lesions, controls=controls)
        targets = [(subject, attribute) for subject, by in sessions.items() for attribute in by]
        target = weaken.draw(st.sampled_from(targets + [None]))
        changed_sessions, changed_controls = {key: dict(value) for key, value in sessions.items()}, dict(controls)
        if target is None:
            changed_controls[weaken.draw(st.sampled_from(sorted(controls, key=str)))] = False
        else:
            subject, attribute = target
            found = sessions[subject][attribute][0]
            if weaken.draw(st.booleans()):
                weakened = _weakened(found, 0)
            else:
                reading = weaken.draw(st.sampled_from(list(F.DOMAINS[(subject.family, attribute)].enum)))
                weakened = Fact(result=Res.UNKNOWN, value=found.value, state=found.state,
                                options=tuple(dict.fromkeys((*found.options, reading))),
                                reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans)
            changed_sessions[subject][attribute] = (weakened,)
        W = build(facts, changed_sessions, lesions=lesions, controls=changed_controls)
        members = [member(f'sel:{index}', code, X1 if index % 2 else X2) for index, code in enumerate(CODES)]
        for code in CODES:
            self.assertLessEqual(set(C.claims(code, R, ())), set(C.claims(code, W, ())), (code, target))
        before, after = compete(R, *members), compete(W, *members)
        self.assertLessEqual({(key, rival) for key, rivals in before.items() for rival in rivals},
                             {(key, rival) for key, rivals in after.items() for rival in rivals})
        for session in (X1, X2):
            self.assertLessEqual({whole.session for whole in C.wholes(R, session)},
                                 {whole.session for whole in C.wholes(W, session)})

    @hypothesis.settings(max_examples=40, deadline=None, derandomize=True)
    @hypothesis.given(own=_choice((sup(STATED), neg(STATED), SILENT)),
                      neighbour=_choice((sup(TEAM), sup(OTHER_CLINICIAN), unres(OTHER_CLINICIAN), SILENT)),
                      procedure=st.fixed_dictionaries({
                          'kind': _choice((Kind.EXAMINATION, Kind.BAND_LIGATION, Kind.OTHER, Kind.SNARE)).map(sup),
                          'session': _choice((sup(X0), sup(X1), sup(X3), SILENT)),
                          'status': _choice((sup(PERFORMED), sup(PLANNED), neg(PERFORMED), unres(PERFORMED))),
                          'date': _choice((sup(ON), sup(EARLIER), unres(ON))),
                          'device': _choice((sup(Device.MANUAL), sup(Device.ENDOSCOPE), SILENT)),
                          'other_class': _choice((sup(ct.OtherClass.LABORATORY), sup(ct.OtherClass.PROCEDURE), SILENT)),
                      }),
                      history=_choice((SILENT, sup(ON), sup(EARLIER))))
    def test_p_mono_every_single_weakening_of_the_visits_and_a_procedure(self, own, neighbour, procedure, history):
        """P-MONO over the same-day rule, exhaustively per example (the refutation's T1): the code's own visit E0 (its
        statement stated, denied or silent), another visit E9 of the encounter today (stated, its performer drawn), a
        candidate procedure E1, and an upper endoscopy's examination E2 told as of today, of another date or with no
        date. EVERY established fact of each event and session is weakened in turn - to unresolved, and by an added
        doubt of EVERY member of its domain - with no counted code, a supported one and an unsupported one: a held E/M
        code is never released."""
        facts = {E0: act(Kind.EM_VISIT, X0, separate=own),
                 E9: act(Kind.EM_VISIT, X0, separate=sup(STATED), performer=neighbour),
                 E1: event(performer=sup(TEAM), entry=sup(CLINICIAN), **procedure),
                 E2: act(Kind.EXAMINATION, X3, date=history)}
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.COLONOSCOPY),
                    X3: session_of(SessionKind.EGD)}
        visit_code = member('sel:v', '99213', X0, (E0,))
        counted = ((), (C.ProceduralCode('45378', SessionKind.COLONOSCOPY, procedural=True, supported=True),),
                   (C.ProceduralCode('45385', SessionKind.COLONOSCOPY, procedural=True, supported=False),))
        R = build(facts, sessions)
        held = [codes for codes in counted if C.same_day_holds(visit_code, R, C.procedure_day(R, codes))]
        for table, objects in (('event', facts), ('session', sessions)):
            for subject, by in objects.items():
                for attribute, values in by.items():
                    if not (values and F.established(values[0])):
                        continue
                    found = values[0]
                    domain = F.DOMAINS[(subject.family, attribute)]
                    readings = list(domain.enum) if domain.enum is not None else list(sessions)
                    weakenings = [_weakened(found, 0)] + [
                        Fact(result=Res.UNKNOWN, value=found.value, state=found.state,
                             options=tuple(dict.fromkeys((*found.options, reading))),
                             reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans) for reading in readings]
                    for weakened in weakenings:
                        changed = {key: dict(value) for key, value in objects.items()}
                        changed[subject][attribute] = (weakened,)
                        W = build(changed, sessions) if table == 'event' else build(facts, changed)
                        for codes in held:
                            self.assertTrue(C.same_day_holds(visit_code, W, C.procedure_day(W, codes)),
                                            (subject, attribute, weakened.result, weakened.options, codes))

    def test_a_weakened_whole_stays_a_whole(self):
        """C-4 and C3 established, each fact weakened in turn: the whole remains, now possible (D70)."""
        base = egd_eus(part_of=sup(X2))
        self.assertEqual(C.wholes(base, X1), (C.Whole(X2, True),))
        for weakened in (egd_eus(part_of=unres(X2)), egd_eus(tract=unres(ct.Tract.UPPER)),
                         egd_eus(eus=unres(SessionKind.EUS))):
            self.assertEqual([whole.session for whole in C.wholes(weakened, X1)], [X2])

    @hypothesis.settings(max_examples=400, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(DAY_FACTS, min_size=1, max_size=4), visit=DAY_FACTS,
                      other_visit=st.booleans(), other=_choice(DAY_SESSION_KINDS), data=st.data())
    def test_p_mono_the_same_day_rule_never_releases_a_held_em_code(self, events, visit, other_visit, other, data):
        """P-MONO over the same-day rule (the refutation's F1 and T1): the visit carries a statement (stated, denied or
        silent), another visit of the encounter may lend one, and ANY established fact of any event - the visits
        included - or session may be weakened: to unresolved, or by an added doubt whose reading is any member of the
        attribute's domain (so a kind may gain an E/M or examination reading, a device manual, a class procedure). A
        held E/M code stays held; an act of the procedure day stays one or becomes undatable, the undatable acts never
        shrink; an established procedure day and a documented statement never appear."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E0] = act(Kind.EM_VISIT, X0, separate=visit['separate'])
        if other_visit:
            facts[E9] = act(Kind.EM_VISIT, X0, separate=sup(STATED), performer=visit['performer'], date=visit['date'])
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.COLONOSCOPY),
                    X3: session_of(other)}
        R = build(facts, sessions)
        targets = [(table, subject, attribute) for table, objects in (('event', facts), ('session', sessions))
                   for subject, by in objects.items() for attribute, values in by.items()
                   if values and F.established(values[0])]
        table, subject, attribute = data.draw(st.sampled_from(targets))
        objects = {key: dict(value) for key, value in (facts if table == 'event' else sessions).items()}
        found = objects[subject][attribute][0]
        if data.draw(st.booleans()):
            weakened = Fact(result=Res.UNRESOLVED, value=found.value, state=found.state, options=found.options,
                            reasons=(ct.Reason.APPRAISAL_UNCLEAR,), spans=found.spans)
        else:
            domain = F.DOMAINS[(subject.family, attribute)]
            readings = list(domain.enum) if domain.enum is not None else list(sessions)
            reading = data.draw(st.sampled_from(readings))
            weakened = Fact(result=Res.UNKNOWN, value=found.value, state=found.state,
                            options=tuple(dict.fromkeys((*found.options, reading))),
                            reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans)
        objects[subject][attribute] = (weakened,)
        W = build(objects, sessions) if table == 'event' else build(facts, objects)
        codes = (C.ProceduralCode('45378', SessionKind.COLONOSCOPY, procedural=True, supported=True),
                 C.ProceduralCode('45385', SessionKind.COLONOSCOPY, procedural=True, supported=False))
        for counted in ((), codes[1:], codes):
            day_r, day_w = C.procedure_day(R, counted), C.procedure_day(W, counted)
            # an act of the procedure day stays one, or becomes undatable (its date weakened): never neither
            self.assertLessEqual(set(day_r.done_acts + day_r.possible_acts),
                                 set(day_w.done_acts + day_w.possible_acts + day_w.undatable))
            self.assertLessEqual(set(day_r.undatable), set(day_w.undatable))
            self.assertGreaterEqual(day_r.established, day_w.established)
            visit_code = member('sel:v', '99213', X0, (E0,))
            if C.same_day_holds(visit_code, R, day_r):
                self.assertTrue(C.same_day_holds(visit_code, W, day_w), (table, subject, attribute, weakened))
        self.assertGreaterEqual(C.separate_statement(R, (E0,)).stated is not None,
                                C.separate_statement(W, (E0,)).stated is not None)

    @hypothesis.settings(max_examples=150, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(DAY_FACTS, min_size=1, max_size=4), visit=DAY_FACTS, data=st.data())
    def test_p_mono_combine_never_releases_a_held_member(self, events, visit, data):
        """P-MONO over combine (4.1's combine): a member held by any combination rule before a weakening is held after
        it, the claims never shrink, and the competition never shrinks (the coding fixed: step 4b's lists are its
        own property)."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E0] = act(Kind.EM_VISIT, X0, separate=visit['separate'])
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.COLONOSCOPY),
                    X3: session_of(SessionKind.EGD)}
        R = build(facts, sessions)
        targets = [(subject, attribute) for subject, by in facts.items() for attribute, values in by.items()
                   if values and F.established(values[0])]
        subject, attribute = data.draw(st.sampled_from(targets))
        changed = {key: dict(value) for key, value in facts.items()}
        found = changed[subject][attribute][0]
        domain = F.DOMAINS[(subject.family, attribute)]
        readings = list(domain.enum) if domain.enum is not None else list(sessions)
        reading = data.draw(st.sampled_from(readings))
        changed[subject][attribute] = (Fact(result=Res.UNKNOWN, value=found.value, state=found.state,
                                            options=tuple(dict.fromkeys((*found.options, reading))),
                                            reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans),)
        W = build(changed, sessions)
        members = [member('sel:v', '99213', X0, (E0,)), member('sel:0', '45378', X1, (E1,), procedural=True,
                                                               supported=True),
                   member('sel:1', '45385', X1, (E2,), procedural=True), member('sel:2', '45380', X1),
                   member('sel:3', '43235', X3, (E3,), procedural=True, supported=True), member('sel:4', '43239', X3)]
        coding = {X0: C.SessionActs(), X1: C.SessionActs(), X3: C.SessionActs()}
        before, after = C.combine(members, coding, R), C.combine(members, coding, W)
        self.assertLessEqual({key for key, held in before.held.items() if held},
                             {key for key, held in after.held.items() if held}, (subject, attribute, reading))
        for key in before.claims:
            self.assertLessEqual(set(before.claims[key]), set(after.claims[key]))
        self.assertLessEqual({(key, rival) for key, rivals in before.competes.items() for rival in rivals},
                             {(key, rival) for key, rivals in after.competes.items() for rival in rivals})


# --- the text-free boundary (FINAL-V2 5.7 measures 4 and 5) -----------------------------------------------------------


class BoundaryTests(SimpleTestCase):
    def test_measure_4_holds_over_the_module(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_a_planted_word_reader_turns_measure_4_red(self):
        source = MODULE.read_text(encoding='utf-8')
        plants = (('from studio.interpretation import facts as v1_facts\n', 'imports studio.interpretation.facts'),
                  ("DONE_STATEMENTS = ('was performed', 'were done')\n", 'a module-level word list'),
                  ("def _x(event):\n    return event.words\n", 'reads .words'),
                  ("def _y(value):\n    return 'performed' in value\n", 'tests membership against a string'))
        for plant, found in plants:
            with self.subTest(plant=plant):
                self.assertTrue(any(found in item for item in measure_4(source + plant, engine=True)))

    def test_the_module_imports_no_retired_module_text_module_or_gi_table(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.combination\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=120, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = set(result.stdout.strip().split(','))
        self.assertIn('studio.interpretation.engine.combination', loaded)
        retired = {'prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations',
                   'mapping', 'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess'}
        self.assertFalse({f'studio.interpretation.{name}' for name in retired} & loaded, loaded)
        text = {'segment', 'geometry', 'fold', 'date_literals', 'claims', 'extract_read', 'extract_prompt',
                'appraise_prompt', 'appraise_read'}
        self.assertFalse({f'studio.interpretation.contract.{name}' for name in text} & loaded, loaded)
        self.assertFalse({name for name in loaded if name.startswith('studio.gi')}, loaded)

    def test_mypy_strict_passes_and_refuses_a_string_operation_on_a_claim(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=600, cwd=APP)

        result = mypy('studio/interpretation/engine/combination.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 1 source file', result.stdout)
        probe = mypy('-c', 'from studio.interpretation.engine.combination import BaseIncluded\n'
                           'def probe(found: BaseIncluded) -> bool:\n'
                           '    return found.session.startswith("X")\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)
