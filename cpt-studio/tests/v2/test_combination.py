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
filter, and P6's place lists (round 2: no listed place removed a claim; D240 reads D29's site fit since); DECISIONS
D191 (SAME_DAY_KINDS read from FAMILY_KINDS) and the arbiter's hand-off 1e:R3 (equal to the catalogue entries' kinds,
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

The repair r4d (DECISIONS D227's 4d items, after the refutation build-v2/w34/refute-4d-r2): R2-1 (a procedure day is
established only by an act whose kind is established and is no E/M kind: an E/M event whose kind gains another reading,
or is contradicted between the visit and another kind, is a possible procedure, never a done one - its input (b) and the
contradicted forms, the kind established beyond "no E/M reading", and two P-MONO properties drawn toward the class);
R2-2 (a session id the FactSet does not hold reads as possibly any session for membership, in session_possibly_done and
_may_be_examination_of: D70's reading); R2-3 stays as built (D227: the established-day test above is unchanged); the
low items R2-4 (docstrings) and R2-5 (_today_visit's kind check pinned).

The round r4d of build-v2/w7r (DECISIONS D231, D240, D244 R-N3): SyntheticAct - 3.2.6 rule 3's synthetic act (a kept
unlisted ACT or DOUBT) read by every absence condition of the module, each of r4d's audit rows 1-5 with the
unlisted-versus-filed-doubted pair (row 1 session_done's act-only arm; row 2 D70's possible whole, p4_checks' input as
an act and as a doubt; row 3 D119's PEG arm; row 4 the D55 and D118 openings; row 5 the competition over the act), base
rule (c) and 3.2.6 rule 5 over doubts, the set agreement with evaluate.synthetic_possible, and a property: an added
synthetic act never shrinks a claim, a competition, a hold or a whole; SiteFit - D29's site fit in the claims (D240:
43249 claims the esophageal act and 43245 the duodenal one, and they never compete), its fail-closed arms, its
agreement with evaluate's SITE row over a cross product, and the named release (a deleted place member) in Monotone;
PartOfWhole - a part session's base code held beside a whole its own part_of_session claim names, whatever that
whole's counted codes include (N3: 45330 beside 45378), the weakened claim holding it too, C-4's structural whole
keeping the includes rule (43231).

Its repair round (refute-r4d-r1 of build-v2/w7r): F1, F3 and F4 - base rule (c) and rows 3-5 read a CARDED synthetic
act only (3.2.6 rule 3: "an unlisted act with a session card"; D231: "whose card may be", "with a card"), rows 1 and 2
still read no card as every session: an entry of no kind and no card holds no office visit's base code (F1), an
unlisted biopsy of no session never makes an EGD's and a colonoscopy's codes compete (F3), and no K2 admission stands
in for the card (F4); F6 - D240's named release through a deleted member of the target LESION's places too (SiteFit,
and a Monotone property weakening the lesions' facts).

The round r4d of build-v2/w8r (DECISIONS D253's QE13, D255, D256, D257): AddOnCodes - an add-on code (a key of
engine/assess.ADDON_PRIMARIES) never causes a base hold and is never named in one (99215, 99205, 99245 beside 99417
READY; 99213 beside 99417 not held under rule (a); 43260 beside 43273 READY; 43260 beside 43262 and 43273 held, naming
43262 only; the within rule too; refute-r3c-r1 p02 and p08 through assess); NoCardEntries - D256 P1, Q-CARD option (c):
an entry with no card that names a kind holds every session's base code where step 4b would list its filed doubted form,
as its carded form does (refute-r4d-r2 P1's one-session shape), the admission pinned equal to coverage's over every kind
and session shape and to the filed form's hold over every kind; a kindless entry with no card holds the base code of a
one-session document and stays out of a document of more than one (the named residual Q-UNNAMED, as built); the two
subtests D256 names changed (Base rule (c)'s "a biopsy with no card", F1's f4=biopsy), and with them the card the
FactSet does not hold in Base rule (c) and row 3's two no-card PEG controls (D256 P1 through rule (c)'s own arm);
EstablishedNotDone - D256 P2: a session whose examination is established not done today (planned, another date) is made
possibly done by no entry with no card and no unplaced, undated act (refute-r4d-r2 P2's planned EUS), K2 for an entry
naming a kind, and the letter's date-weakening release named (question Q-P2DATE); PartOfWhole - D257: ``within`` names
the stated whole's counted codes; DigitalExamination - QE13 option (a): session_done reads the digital examination as
evaluate does (a device claiming manual), pinned equal to evaluate.act_only and evaluate._digital.

The round r4d of build-v2/w9r (DECISIONS D268, D269, D271's G3-02): AddOnCodes - D268: base rules (b) and (c) read no
act that a counted add-on code of the same session accounts for as its supporting act (refute-r4d-r1 V8R4D1-1: 43260
beside 43273 with the cholangioscopy documented READY, as 43273 is; without 43273 counted, 43260 held naming the
cholangioscopy, as built); EstablishedNotDone - D269, Q-P2DATE option (c): a session established not done today is made
possibly done by no act, placed, supported, carded or with no card, whatever its date or session slot, and is never a
whole by C3, D70 or C-4 (the Q-P2DATE test restated: 43235 not held beside the planned EUS and an office visit act dated
today or undated, through assess too; refute-r4b-r1 V8R4B1-3's two forms one answer; the I4 residual's planned whole
gone), "established not done" reading every event the document places in the session that may be its examination (the
step's question Q-NDT, with a P-MONO pin over 9.4's single weakenings); NoCardEntries - D269's count (refute-r4d-r1
V8R4D1-3): the planned repeat colonoscopy filed as a session no longer turns the kindless one-session hold off, at the
combination and through assess; DigitalExamination - G3-02: ``_digital``'s kind gate pinned (a done act of a supported
non-examination kind whose device claims manual, alone in its session, makes it done).
"""
from __future__ import annotations

import os
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

# v1, read only for the parity proofs (computed here); engine/ never imports these
from studio.interpretation import combination as v1_combination, mapping as v1_mapping
from studio.interpretation import overlay, wording  # read only: the renderer's slots and sentence of an item (D255)
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS  # read only: ADDON_PRIMARIES (D255), session_acts (D256)
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import combination as C
from studio.interpretation.engine import evaluate as EV  # read only: one rule, two readers (D231, D240, D253)
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Anchor, Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Outcome, Span
from studio.interpretation.engine.types import UnlistedStatement
from studio.validation import checks as v1_checks, engine as v1_engine
from tests.v2 import evaluate_fixtures as EF  # the refuters' assess-level shapes (synthetic fixtures)
from tests.v2 import test_assess as TA
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
X9 = Id(IdFamily.SESSION, 9)  # a session no FactSet here holds (D227 R2-2)
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


def contradicted(*sides, **kw) -> Fact:
    """Contradicted (3.3 row 3): pass 1 reported both sides; no value is kept, the sides are the options."""
    return fact(Res.CONTRADICTED, None, State.CONTRADICTED, options=sides, reasons=(ct.Reason.CONTRADICTED_BY_PASS1,),
                **kw)


def dangling(value, **kw) -> Fact:
    """A session id the FactSet does not hold (settle's I4: the claimed value kept, unresolved, reference_invalid)."""
    return fact(Res.UNRESOLVED, value, State.SUPPORTED, reasons=(ct.Reason.REFERENCE_INVALID,), **kw)


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


ACT_, DOUBT_, DENIAL_ = ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL


def entry_of(kind, session, what=ACT_, at=900) -> UnlistedStatement:
    """A kept unlisted entry (3.2.6): ``what`` (an act unless given) of ``kind`` (None: none named), carded to
    ``session`` (None: no card), on a unit of its own at ``at``."""
    return UnlistedStatement(units=(Span(at, at + 40),), what=what, kind=kind, session=session)


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
        """FINAL-V2 3.2.6 rule 3, as DECISIONS D231, D232 and D256 read it: a synthetic act - a kept unlisted ACT or
        DOUBT (a doubt leaves the act possibly performed: refute-r4a-r1 F1) - CARDED to the session holds the session's
        base code as a doubt (a QUESTION), whatever its kind and whatever the coding lists. An entry carded to another
        session and an unlisted denial hold nothing here. (Round 2 read an unlisted ACT carded to the session alone.)
        With no card, or with a card the FactSet does not hold (read as none, as contract/appraise_read reads it): D256
        P1 (Q-CARD option (c)) - an entry that names a kind holds every session's base code where step 4b would list its
        filed doubted form doubted (a biopsy and a snare: the colonoscopy's and the EGD's both; this subtest changed
        with D256: round 2 of build-v2/w7r held nothing); one that names no kind stays out in this document of two
        sessions (D256's named residual Q-UNNAMED)."""
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        entries = (entry_of(Kind.BIOPSY, X1, at=900), entry_of(Kind.BIOPSY, X1, DOUBT_, at=950),
                   entry_of(None, None, at=1000), entry_of(Kind.SNARE, X9, at=1050),
                   entry_of(None, X2, at=1100), entry_of(Kind.BIOPSY, None, at=1150),
                   entry_of(None, X1, DENIAL_, at=1200))
        carded = tuple(entries[index] for index in (0, 1, 2, 4, 6))  # no entry with no card naming a kind
        R = build({E1: act(Kind.EXAMINATION), E5: act(Kind.EXAMINATION, X2)}, sessions, unlisted=carded)
        coding = {X1: C.SessionActs(), X2: C.SessionActs()}
        found = C.base_included([member('sel:0', '45378', supporting=(E1,))], coding, R)
        self.assertEqual([(b.unlisted, b.unlisted_kinds, b.established, b.named_codes) for b in found],
                         [((0, 1), (Kind.BIOPSY,), False, ())])
        held = C.base_hold(found[0], R)
        self.assertEqual((held.kind, held.spans), (ItemKind.QUESTION, (Span(900, 940), Span(950, 990))))
        # the EGD's base code: the entry carded to it alone (an entry of no kind: nothing the hold can name)
        egd = C.base_included([member('sel:1', '43235', X2, (E5,))], coding, R)
        self.assertEqual([(b.unlisted, b.unlisted_kinds) for b in egd], [((3,), ())])
        members = [member('sel:0', '45378', supporting=(E1,)), member('sel:1', '43235', X2, (E5,))]
        for name, kept in (('no card, no kind (Q-UNNAMED: two sessions)', entries[2]),
                           ('a denial carded X1', entries[6])):
            with self.subTest(control=name):
                control = build({E1: act(Kind.EXAMINATION), E5: act(Kind.EXAMINATION, X2)}, sessions,
                                unlisted=(kept,))
                self.assertEqual(C.base_included(members, coding, control), ())
        for name, kept, kind in (('a card the FactSet does not hold (a snare)', entries[3], Kind.SNARE),
                                 ('a biopsy with no card', entries[5], Kind.BIOPSY)):
            with self.subTest(d256=name):  # D256 P1: both sessions list the act filed in doubt with no session
                R = build({E1: act(Kind.EXAMINATION), E5: act(Kind.EXAMINATION, X2)}, sessions, unlisted=(kept,))
                found = C.base_included(members, coding, R)
                self.assertEqual([(b.code, b.unlisted, b.unlisted_kinds, b.established, b.named_codes)
                                  for b in found],
                                 [('45378', (0,), (kind,), False, ()), ('43235', (0,), (kind,), False, ())])
                self.assertEqual({C.base_hold(b, R).kind for b in found}, {ItemKind.QUESTION})

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

    def test_r2_2_a_session_id_the_factset_does_not_hold_may_be_any_session(self):
        """DECISIONS D227 R2-2 (the refutation build-v2/w34/refute-4d-r2, R2-2; FINAL-V2 4.11: a missing identifier
        manufactures neither a match nor a non-match): the upper EUS X2's examination E2 and its FNA E3 name session
        X9, which the FactSet does not hold (settle's I4 keeps the claimed value, unresolved, reference_invalid). For
        membership each may be in ANY session - as step 4b's coverage.sessions_of reads it, and as its family read
        already was - so X2 is possibly done and the EGD X1 possibly its endoscopic portion: D70's reading, 43235 held
        base_within as a QUESTION, exactly as with their session slot silent (round 2 read them in no session: no
        whole, and 43235 released). The same for the dangling id as a doubt's reading and as a supported value. Its
        family read stays any family (no session of the FactSet is a colonoscopy)."""
        members = [member('sel:0', '43235', X1, (E1,), procedural=True, supported=True),
                   member('sel:1', '43242', X2, (), procedural=True)]
        coding = {X1: C.SessionActs(), X2: C.SessionActs()}

        def naming(session):
            pancreas = (sup(Landmark.PANCREAS),)
            return egd_eus(eus_exam=act(Kind.EXAMINATION, session, places=pancreas),
                           extra={E3: act(Kind.FNA, session, places=pancreas, device=sup(Device.NEEDLE))})

        silent = naming(None)
        self.assertEqual(C.wholes(silent, X1), (C.Whole(X2, False),))
        for name, session in (('unresolved, reference_invalid', dangling(X9)), ('a doubt reading X9', doubted(X1, X9)),
                              ('supported', sup(X9))):
            with self.subTest(name):
                R = naming(session)
                self.assertLessEqual({X1, X2, X9}, set(C.possible_sessions(R, E2)))
                self.assertTrue(C.session_possibly_done(R, X2))
                self.assertEqual(C.wholes(R, X1), C.wholes(silent, X1))
                held = C.combine(members, coding, R).held['sel:0']
                self.assertEqual([(h.fact, h.kind, h.cause) for h in held],
                                 [('base_included', ItemKind.QUESTION, C.WITHIN_CAUSE)])
                self.assertTrue(C.may_be_of_family(R, E2, SessionKind.COLONOSCOPY))
        control = naming(sup(X2))
        self.assertEqual((C.possible_sessions(control, E2), C.wholes(control, X1)), ((X2,), (C.Whole(X2, True),)))

    def test_r2_2_an_examination_naming_no_session_of_the_factset_may_be_any_sessions_examination(self):
        """D227 R2-2 in _may_be_examination_of (the refutation's F3 reading kept): an act-only upper EUS X2 - its FNA E3
        done - beside an examination E4 whose date is not established and whose session fact names X9, a session the
        FactSet does not hold: E4 may be X2's examination and is not done, so X2 is only possibly done and the EGD's
        whole a possible one (a QUESTION, never an established whole: round 2 read E4 in no session and established
        it). With E4 established in the EGD X1 instead (the control), it is no examination of X2, and X2 is done by its
        act (D121)."""
        sessions = {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=sup(ct.Tract.UPPER))}
        for name, session in (('unresolved, reference_invalid', dangling(X9)), ('supported', sup(X9))):
            with self.subTest(name):
                R = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2),
                           E4: act(Kind.EXAMINATION, session, date=unres(ON))}, sessions)
                self.assertTrue(C._may_be_examination_of(R, X2, E4))
                self.assertFalse(C.session_done(R, X2))
                self.assertEqual(C.wholes(R, X1), (C.Whole(X2, False),))
                found = C.base_within([member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,))], R)
                self.assertEqual([(b.within, b.established) for b in found], [(('43242',), False)])
                self.assertEqual(C.base_within_hold(found[0], R).kind, ItemKind.QUESTION)
        control = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2),
                         E4: act(Kind.EXAMINATION, X1, date=unres(ON))}, sessions)
        self.assertFalse(C._may_be_examination_of(control, X2, E4))
        self.assertTrue(C.session_done(control, X2))
        self.assertEqual(C.wholes(control, X1), (C.Whole(X2, True),))


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
    for) and D29's site fit (DECISIONS D240: a target established outside a site code's class), over facts; 4.11 and
    SC-B: an unknown identity and an unrejected pair control never set two acts apart."""

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

    def test_d240_only_a_target_established_outside_the_site_class_sets_an_act_apart(self):
        """D29's site fit in the claims (DECISIONS D240, the installed reading kept; it replaces round 2's P6 reading,
        under which no place list set an act apart). A balloon dilation listed at the distal esophagus and the pylorus
        is claimed by 43249 (esophageal) and 43245 (gastric and duodenal), and they compete; listed at an anastomosis
        (FRESH-2 fb07's shape: never outside a class, D29's "an ambiguous target holds") they compete too. Listed at the
        pylorus alone - every place established outside 43249's class - 43249 claims nothing and 43245 READY on it is
        never held competing_codes (v1's D118 control: "43245 READY, 43249 held for its site"). That is also what 9.4's
        deleted-member weakening reaches from the spanning list: D240's NAMED release (Monotone names it). A device
        established as another class still sets an act apart (R4)."""
        for name, places, competing in (
                ('spanning', (Landmark.DISTAL_ESOPHAGUS, Landmark.PYLORUS), True),
                ('at an anastomosis', (Landmark.ANASTOMOSIS,), True),
                ('the pylorus alone (the esophageal member deleted)', (Landmark.PYLORUS,), False)):
            with self.subTest(name):
                R = dilations(act(Kind.EXAMINATION), act(Kind.DILATION, device=sup(Device.BALLOON),
                                                         places=tuple(sup(place) for place in places)))
                self.assertEqual(E3 in C.claims('43249', R, ()), competing)
                self.assertEqual(C.site_outside('43249', R, E3), not competing)
                self.assertFalse(C.site_outside('43245', R, E3))
                self.assertEqual(compete(R, member('sel:0', '43245', supporting=(E3,)), member('sel:1', '43249')),
                                 {'sel:0': ('43249',), 'sel:1': ('43245',)} if competing else {})
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

    def test_r2_1_an_em_event_whose_kind_gains_another_reading_never_establishes_the_day(self):
        """DECISIONS D227 R2-1 (the refutation build-v2/w34/refute-4d-r2, R2-1, its input (b)): a procedure day is
        established only by an act whose kind is established and is no E/M kind. 99213's own visit E0 carries its
        statement; a colonoscopy examination E1 is told with no date relation (undatable); an event E2 told as an
        office visit (kind supported em_visit or em_prolonged) is filed in a supported session of a procedural family,
        performed and supported on the date. E2 is skipped as the visit, and 99213 is held event_time on E1. One
        weakening gives E2's kind another reading - a doubt reading ANY kind that is no E/M kind: E2 may still be the
        visit, so it is a POSSIBLE procedure (labelled with its session's family), never a done one - the day is not
        established and 99213 stays held event_time on E1 (round 2: E2 was done by its family, the day established,
        99213 READY). Every reading, both E/M kinds, every session family of the procedure day."""
        undatable = (E1, act(Kind.EXAMINATION, X1, date=SILENT))
        # the refutation's input (b) as it stands: E2 in the colonoscopy X1 itself, its kind gaining an examination
        # reading
        for name, kind in (('before', sup(Kind.EM_VISIT)), ('after', doubted(Kind.EM_VISIT, Kind.EXAMINATION))):
            with self.subTest(input_b=name):
                day, held = same_day(office(undatable, (E2, act(kind, X1)), separate=sup(STATED)))
                self.assertEqual((day.established, [(h.fact, h.subject, h.kind) for h in held]),
                                 (False, [('event_time', E1, ItemKind.QUESTION)]))
        readings = sorted(set(Kind) - C.EM_KINDS, key=lambda kind: kind.value)
        self.assertEqual(len(readings), 40)
        for family in sorted(C.SAME_DAY_FAMILIES, key=lambda kind: kind.value):
            sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(family)}
            for em in sorted(C.EM_KINDS, key=lambda kind: kind.value):
                with self.subTest(family=family.value, kind=em.value):
                    day, held = same_day(office(undatable, (E2, act(em, X2)), separate=sup(STATED), sessions=sessions))
                    self.assertEqual((day.procedure_day, day.established, [(h.fact, h.subject) for h in held]),
                                     (False, False, [('event_time', E1)]))
                    for reading in readings:
                        weakened = office(undatable, (E2, act(doubted(em, reading), X2)), separate=sup(STATED),
                                          sessions=sessions)
                        day, held = same_day(weakened)
                        self.assertEqual((day.established, day.done_acts, day.possible_acts, day.possible,
                                          day.undatable, [(h.fact, h.subject) for h in held]),
                                         (False, (), (E2,), (family,), (E1,), [('event_time', E1)]), reading)

    def test_r2_1_a_kind_contradicted_between_the_visit_and_another_establishes_no_day(self):
        """The refutation's R2-1, its settle-reachable form (K2 demotes the session of an act whose SUPPORTED kind its
        session's family does not admit, and reads only a supported kind): E2's kind contradicted between the visit and
        prolonged time, the same with a third side reading an examination, and the visit against an examination alone -
        each filed in the colonoscopy X2, performed today. None is established, so none establishes the day: 99213 stays
        held event_time on the undatable E1 (round 2: the last two READY)."""
        undatable = (E1, act(Kind.EXAMINATION, X1, date=SILENT))
        sessions = {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.COLONOSCOPY)}
        shapes = {'em_visit | em_prolonged': (contradicted(Kind.EM_VISIT, Kind.EM_PROLONGED), ()),
                  'em_visit | em_prolonged | examination': (
                      contradicted(Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.EXAMINATION), (E2,)),
                  'em_visit | examination': (contradicted(Kind.EM_VISIT, Kind.EXAMINATION), (E2,))}
        for name, (kind, possible) in shapes.items():
            with self.subTest(name):
                day, held = same_day(office(undatable, (E2, act(kind, X2)), separate=sup(STATED), sessions=sessions))
                self.assertEqual((day.established, day.done_acts, day.possible_acts,
                                  [(h.fact, h.subject) for h in held]), (False, (), possible, [('event_time', E1)]))

    def test_r2_1_a_done_act_needs_its_kind_established_whatever_its_family(self):
        """D227 R2-1 as ruled - the kind ESTABLISHED, not merely free of an E/M reading: an act filed in a supported
        colonoscopy session, performed today, whose kind is not established (a snare left unresolved, a snare
        doubted toward a biopsy, a snare contradicted by a biopsy, a silent kind) is a possible procedure, never a done
        one, with its session's family as its label. The day is not established, so beside 99213's documented
        statement the undatable act E3 holds it event_time. The control: the snare supported is done, the day
        established, and the undatable act moot (D227 R2-3, as built)."""
        undatable = (E3, act(Kind.EXAMINATION, X2, date=SILENT))
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        shapes = {'unresolved': unres(Kind.SNARE), 'doubted': doubted(Kind.SNARE, Kind.BIOPSY),
                  'contradicted': contradicted(Kind.SNARE, Kind.BIOPSY), 'silent': SILENT}
        for name, kind in shapes.items():
            with self.subTest(name):
                day, held = same_day(office((E1, act(kind)), undatable, separate=sup(STATED), sessions=sessions))
                self.assertEqual((day.done, day.possible, day.done_acts, day.possible_acts, day.established),
                                 ((), (SessionKind.COLONOSCOPY,), (), (E1,), False))
                self.assertEqual([(h.fact, h.subject) for h in held], [('event_time', E3)])
        day, held = same_day(office((E1, act(Kind.SNARE)), undatable, separate=sup(STATED), sessions=sessions))
        self.assertEqual((day.done, day.done_acts, day.established, held),
                         ((SessionKind.COLONOSCOPY,), (E1,), True, ()))

    def test_r2_5_another_event_lends_its_statement_only_when_it_is_a_visit(self):
        """The refutation's R2-5 (its mutant MK1, which drops _today_visit's kind check, survived round 2): another
        event of this encounter lends its separately_identifiable statement only when its kind is supported em_visit
        (D113's "TODAY's visit"). An examination told today by the team in the visit's session with the statement
        supported lends none, nor does an event whose kind may be the visit but is not established, so 99213 beside a
        done colonoscopy is held separate_em. The control: the same event told as a visit lends it."""
        for name, kind, stated in (('an examination', sup(Kind.EXAMINATION), None),
                                   ('the visit in doubt', doubted(Kind.EM_VISIT, Kind.EXAMINATION), None),
                                   ('a visit', sup(Kind.EM_VISIT), E5)):
            with self.subTest(name):
                R = office((E1, act(Kind.EXAMINATION)), (E5, act(kind, X0, separate=sup(STATED))))
                self.assertEqual(C.separate_statement(R, (E0,)).stated, stated)
                self.assertEqual(keys(same_day(R)[1]), [] if stated is not None else ['separate_em'])


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


def _with_reading(found: Fact, reading) -> Fact:
    """An added doubt reading ``reading`` (9.4): an established fact becomes unknown, its value kept and the reading
    added; a fact already open (unresolved, contradicted, unknown) keeps its result and reasons, the reading added to
    its options (the refutation build-v2/w34/refute-4d-r2's q8: a contradicted kind gaining a third reading)."""
    options = tuple(dict.fromkeys((*found.options, reading)))
    if F.established(found):
        return Fact(result=Res.UNKNOWN, value=found.value, state=found.state, options=options,
                    reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans)
    return Fact(result=found.result, value=found.value, state=found.state, options=options, reasons=found.reasons,
                spans=found.spans)


# D227 R2-1's class drawn on purpose (the refutation found it in DAY_FACTS only with 30,000 random examples): events
# told as a visit or prolonged time - or a procedure - filed in sessions of the procedure day's families.
SAME_DAY_FAMILY_LIST = tuple(sorted(C.SAME_DAY_FAMILIES, key=lambda kind: kind.value))
EM_DAY_FACTS = st.fixed_dictionaries({
    'kind': st.one_of(_choice((Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.EM_VISIT, Kind.EXAMINATION, Kind.SNARE,
                               Kind.OTHER)).map(sup),
                      st.just(contradicted(Kind.EM_VISIT, Kind.EM_PROLONGED))),
    'status': _choice((sup(PERFORMED), sup(Status.ATTEMPTED_NOT_COMPLETED), unres(PERFORMED))),
    'session': _choice((sup(X1), sup(X2), sup(X3))),
    'date': _choice((sup(ON), sup(ON), unres(ON), SILENT)),
    'performer': _choice((sup(TEAM), SILENT)),
    'entry': st.just(sup(CLINICIAN)),
})


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
        # DECISIONS D240's NAMED release (the installed D29 reading kept, its exception named here): a deleted place
        # member that sets an act outside a site code's class (site_outside) may take that act - and D118's claims
        # resting on it - out of the code's claims, and so a competition. Every other shrink fails.
        deleted = how == 2 and attribute is A.TARGET_PLACES
        released: set = set()
        for code in CODES:
            lost = set(C.claims(code, R, ())) - set(C.claims(code, W, ()))
            if lost:
                outside = {act_ for act_ in facts
                           if C.site_outside(code, W, act_) and not C.site_outside(code, R, act_)}
                self.assertTrue(deleted and catalogue.site_class(code) is not None and outside,
                                (code, subject, attribute, how, lost))
                released.add(code)
        before, after = compete(R, *members), compete(W, *members)
        code_of = {item.key: item.code for item in members}
        lost_pairs = ({(key, rival) for key, rivals in before.items() for rival in rivals}
                      - {(key, rival) for key, rivals in after.items() for rival in rivals})
        for key, rival in lost_pairs:
            self.assertTrue(code_of[key] in released or rival in released, (key, rival, subject, attribute, how))
        visit = member('sel:v', '99213', X0, (E0,))
        if C.same_day_holds(visit, R, C.procedure_day(R)):
            self.assertTrue(C.same_day_holds(visit, W, C.procedure_day(W)))
        self.assertLessEqual({whole.session for whole in C.wholes(R, X1)}, {whole.session for whole in C.wholes(W, X1)})

    @hypothesis.settings(max_examples=200, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(EVENT_FACTS, min_size=1, max_size=4), weaken=st.data())
    def test_p_mono_a_lesions_facts_weakened_release_only_by_d240s_named_release(self, events, weaken):
        """P-MONO over the LESIONS' facts (refute-r4d-r1 of build-v2/w7r, F6: the property above weakens the events'
        facts only, so D240's named release was exercised through target.places alone): a member of a lesion's places
        or distinct_from to unresolved, an added doubt, or deleted (9.4). A claim or a competition may shrink only when
        a deleted member of a lesion's places sets an act on that lesion outside a site code's class (site_outside) -
        D240's named release, through the lesion as through the act's own places; every other shrink fails, and no
        whole is lost. E9, a balloon dilation listed at the pylorus on L1, is in every FactSet so that the release is
        reached (deleting L1's esophageal member sets it outside 43249's class)."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E9] = act(Kind.DILATION, X1, device=sup(Device.BALLOON), lesion=sup(L1), places=(sup(Landmark.PYLORUS),))
        sessions = {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.ERCP, tract=sup(ct.Tract.UPPER))}
        lesions = {L1: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS, Landmark.PYLORUS), distinct=(L2,)),
                   L2: lesion_of(places=(Landmark.DUODENAL_BULB,))}
        controls = {(subject, A.TARGET_LESION, lesion): True for subject in facts for lesion in (L1, L2)}
        R = build(facts, sessions, lesions=lesions, controls=controls)
        established = [(subject, attribute, index) for subject, by in lesions.items()
                       for attribute, values in by.items() for index, value in enumerate(values)
                       if F.established(value)]
        subject, attribute, index = weaken.draw(st.sampled_from(established))
        how = weaken.draw(st.sampled_from((0, 1, 2)))
        changed = {key: dict(value) for key, value in lesions.items()}
        values = list(lesions[subject][attribute])
        if how == 2:
            del values[index]  # a deleted member of a multi-valued list (9.4), its pair controls left as they were
        else:
            values[index] = _weakened(values[index], how)
        changed[subject][attribute] = tuple(values)
        W = build(facts, sessions, lesions=changed, controls=controls)
        members = [member(f'sel:{index}', code, X1) for index, code in enumerate(CODES)]
        deleted = how == 2 and attribute is A.PLACES
        released: set = set()
        for code in CODES:
            lost = set(C.claims(code, R, ())) - set(C.claims(code, W, ()))
            if lost:
                outside = {act_ for act_ in facts
                           if C.site_outside(code, W, act_) and not C.site_outside(code, R, act_)}
                self.assertTrue(deleted and catalogue.site_class(code) is not None and outside,
                                (code, subject, attribute, how, lost))
                released.add(code)
        before, after = compete(R, *members), compete(W, *members)
        code_of = {item.key: item.code for item in members}
        lost_pairs = ({(key, rival) for key, rivals in before.items() for rival in rivals}
                      - {(key, rival) for key, rivals in after.items() for rival in rivals})
        for key, rival in lost_pairs:
            self.assertTrue(code_of[key] in released or rival in released, (key, rival, subject, attribute, how))
        for session in sessions:
            self.assertLessEqual({whole.session for whole in C.wholes(R, session)},
                                 {whole.session for whole in C.wholes(W, session)})

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

    def test_p_mono_an_em_event_in_a_procedural_session_never_establishes_the_day(self):
        """9.4 P-MONO over the class of DECISIONS D227 R2-1, exhaustively (the round-2 properties drew it too rarely to
        see it: the refutation found it only with 30,000 random examples): an E/M event E2 - its kind supported em_visit
        or em_prolonged, or contradicted between the two - filed in a supported session X2 of each family of the
        procedure day, performed or attempted, supported on the date, beside 99213's documented statement and an
        undatable act E1: 99213 is held event_time. EVERY fact of E2 and of X2 is weakened in turn - an established one
        to unresolved, and each by an added doubt reading EVERY member of its domain (a contradicted kind keeps its
        sides and gains the reading): the day is never established, no act becomes done, and 99213 stays held."""
        visit = member('sel:v', '99213', X0, (E0,))
        checked = 0
        for family in sorted(C.SAME_DAY_FAMILIES, key=lambda kind: kind.value):
            sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)),
                        X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(family)}
            for kind in (sup(Kind.EM_VISIT), sup(Kind.EM_PROLONGED), contradicted(Kind.EM_VISIT, Kind.EM_PROLONGED)):
                for status in (sup(PERFORMED), sup(Status.ATTEMPTED_NOT_COMPLETED)):
                    facts = {E0: act(Kind.EM_VISIT, X0, separate=sup(STATED)),
                             E1: act(Kind.EXAMINATION, X1, date=SILENT), E2: act(kind, X2, status=status)}
                    R = build(facts, sessions)
                    self.assertEqual([(h.fact, h.subject) for h in C.same_day_holds(visit, R, C.procedure_day(R))],
                                     [('event_time', E1)])
                    for subject, objects in ((E2, facts), (X2, sessions)):
                        for attribute, values in objects[subject].items():
                            found = values[0]
                            domain = F.DOMAINS[(subject.family, attribute)]
                            readings = list(domain.enum) if domain.enum is not None else list(sessions)
                            weakenings = [_with_reading(found, reading) for reading in readings]
                            if F.established(found):
                                weakenings.append(_weakened(found, 0))
                            for weakened in weakenings:
                                changed = {key: dict(value) for key, value in objects.items()}
                                changed[subject][attribute] = (weakened,)
                                W = build(changed, sessions) if subject == E2 else build(facts, changed)
                                day = C.procedure_day(W)
                                checked += 1
                                where = (family, kind.result, status.value, subject, attribute, weakened.result,
                                         weakened.options)
                                self.assertEqual((day.established, day.done_acts), (False, ()), where)
                                self.assertTrue(C.same_day_holds(visit, W, day), where)
        self.assertGreater(checked, 5000)

    @hypothesis.settings(max_examples=300, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(EM_DAY_FACTS, min_size=1, max_size=3),
                      families=st.lists(_choice(SAME_DAY_FAMILY_LIST), min_size=2, max_size=2), data=st.data())
    def test_p_mono_an_established_procedure_day_never_appears_under_a_weakening(self, events, families, data):
        """9.4 P-MONO over the same-day rule, drawn toward D227 R2-1's class: up to three events told as a visit,
        prolonged time or a procedure (a kind contradicted between the two E/M kinds included), each filed in a session
        of the procedure day's families, beside 99213's documented statement and an undatable act E9 - so 99213 is held
        exactly while no act establishes the day. ANY fact of any event or session is weakened (an established one to
        unresolved, or any one by an added doubt reading any member of its domain): the established acts never grow,
        the day never becomes established, and a held 99213 stays held."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E0] = act(Kind.EM_VISIT, X0, separate=sup(STATED))
        facts[E9] = act(Kind.EXAMINATION, X1, date=SILENT)
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.COLONOSCOPY),
                    X2: session_of(families[0]), X3: session_of(families[1])}
        R = build(facts, sessions)
        targets = [(table, subject, attribute) for table, objects in (('event', facts), ('session', sessions))
                   for subject, by in objects.items() for attribute, values in by.items() if values]
        table, subject, attribute = data.draw(st.sampled_from(targets))
        objects = {key: dict(value) for key, value in (facts if table == 'event' else sessions).items()}
        found = objects[subject][attribute][0]
        domain = F.DOMAINS[(subject.family, attribute)]
        readings = list(domain.enum) if domain.enum is not None else list(sessions)
        if F.established(found) and data.draw(st.booleans()):
            weakened = _weakened(found, 0)
        else:
            weakened = _with_reading(found, data.draw(st.sampled_from(readings)))
        objects[subject][attribute] = (weakened,)
        W = build(objects, sessions) if table == 'event' else build(facts, objects)
        day_r, day_w = C.procedure_day(R), C.procedure_day(W)
        where = (table, subject, attribute, weakened.result, weakened.options)
        self.assertLessEqual(set(day_w.done_acts), set(day_r.done_acts), where)
        self.assertGreaterEqual(day_r.established, day_w.established, where)
        visit = member('sel:v', '99213', X0, (E0,))
        if C.same_day_holds(visit, R, day_r):
            self.assertTrue(C.same_day_holds(visit, W, day_w), where)


# --- the synthetic act (FINAL-V2 3.2.6 rule 3; DECISIONS D216, D231) --------------------------------------------------


UPPER = sup(ct.Tract.UPPER)


def held_of(combined: C.Combination, key: str) -> list:
    return [(h.fact, h.kind, h.cause) for h in combined.held[key]]


def coding_of(R: FactSet) -> dict:
    """Step 4b's lists with nothing reportable or doubted in any session (the synthetic act is read from the
    FactSet)."""
    return {session: C.SessionActs() for session in R.sessions}


class SyntheticAct(SimpleTestCase):
    """DECISIONS D231's combination half (refute-r4d-r1 RFR4D-DQ1; r4d's audit rows 1-5): 3.2.6 rule 3's synthetic act -
    a kept unlisted ACT or DOUBT (refute-r4a-r1 F1: a doubt leaves the act possibly performed) - is a possibly performed
    act for every absence condition of the module (D216). Each row is pinned by the unlisted-versus-filed-doubted pair:
    the same act filed as a doubted event (in the card's session) gives the same outcome. A denial is no act, and an
    entry carded to a session the rule does not read moves nothing (the controls). Rows 1 and 2 read an entry with no
    card in every session (D231 row 2's "no card, S possible"); base rule (c) and rows 3-5 read a carded entry only
    ("with a session card", "whose card may be", "with a card": refute-r4d-r1 of build-v2/w7r, F1, F3, F4)."""

    # row 1 ------------------------------------------------------------------------------------------------------------

    def act_only_eus(self, *, entries=(), extra=None) -> FactSet:
        """An upper endoscopy X1 (its examination E1 done) beside an act-only upper EUS X2 (its FNA E3 done): C-4 makes
        X1 the endoscopic portion of X2, established (D121: an EUS told through its done act is the session)."""
        events = {E1: act(Kind.EXAMINATION, X1), E3: act(Kind.FNA, X2, places=(sup(Landmark.PANCREAS),))}
        events.update(extra or {})
        return build(events, {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=UPPER)},
                     unlisted=entries)

    def test_d231_row_1_a_synthetic_examination_leaves_an_act_only_session_open(self):
        """Row 1 (D232's reading, "only in an act-only session"): an unlisted examination carded to the act-only EUS -
        or a doubt about one, an act of no kind with no card, or a card the FactSet does not hold - is an examination of
        X2 left open, as its filed form with a doubted date is: X2 is not done, C-4's whole only possible, 43235 held
        base_within as a QUESTION (round 2: done, the whole established, an EXPLANATION). A denial, an examination
        carded to the upper endoscopy and an act of another kind leave X2 done; beside X2's own done examination the
        synthetic one adds nothing (D232)."""
        members = [member('sel:0', '43235', X1, (E1,)), member('sel:1', '43242', X2, (E3,))]
        done = self.act_only_eus()
        self.assertEqual((C.session_done(done, X2), C.wholes(done, X1)), (True, (C.Whole(X2, True),)))
        filed = self.act_only_eus(extra={E4: act(Kind.EXAMINATION, X2, date=doubted(ON, EARLIER))})
        reference = (C.session_done(filed, X2), C.wholes(filed, X1),
                     [(b.within, b.established) for b in C.base_within(members, filed)])
        self.assertEqual(reference, (False, (C.Whole(X2, False),), [(('43242',), False)]))
        for name, entry in (('an examination carded X2', entry_of(Kind.EXAMINATION, X2)),
                            ('a doubt about it', entry_of(Kind.EXAMINATION, X2, DOUBT_)),
                            ('an act of no kind and no card', entry_of(None, None)),
                            ('a card the FactSet does not hold', entry_of(Kind.EXAMINATION, X9))):
            with self.subTest(name):
                R = self.act_only_eus(entries=(entry,))
                self.assertEqual(C.synthetic_examinations(R, X2), (0,))
                within = C.base_within(members, R)
                self.assertEqual((C.session_done(R, X2), C.wholes(R, X1),
                                  [(b.within, b.established) for b in within]), reference)
                self.assertEqual(C.base_within_hold(within[0], R).kind, ItemKind.QUESTION)
        for name, entry in (('a denial', entry_of(Kind.EXAMINATION, X2, DENIAL_)),
                            ('carded to the upper endoscopy', entry_of(Kind.EXAMINATION, X1)),
                            ('an act of another kind', entry_of(Kind.BIOPSY, X2))):
            with self.subTest(control=name):
                R = self.act_only_eus(entries=(entry,))
                self.assertEqual((C.session_done(R, X2), C.wholes(R, X1)), (True, (C.Whole(X2, True),)))
        examined = self.act_only_eus(entries=(entry_of(Kind.EXAMINATION, X2),),
                                     extra={E2: act(Kind.EXAMINATION, X2, places=(sup(Landmark.PANCREAS),))})
        self.assertEqual((C.session_done(examined, X2), C.wholes(examined, X1)), (True, (C.Whole(X2, True),)))

    # row 2 ------------------------------------------------------------------------------------------------------------

    def eus_with_no_event(self, *, entries=(), extra=None) -> FactSet:
        """p4_checks' input (refute-r4d-r1 RFR4D-DQ1): an upper endoscopy X1 (E1 done; 43235 counted) beside an upper
        EUS X2 with no filed event; a colonoscopy X3 too."""
        events = {E1: act(Kind.EXAMINATION, X1)}
        events.update(extra or {})
        return build(events, {X1: session_of(SessionKind.EGD), X2: session_of(SessionKind.EUS, tract=UPPER),
                              X3: session_of(SessionKind.COLONOSCOPY)}, unlisted=entries)

    def test_d231_row_2_an_unlisted_act_or_doubt_makes_its_session_possibly_done(self):
        """Row 2 (D70's possible whole; the done-when): the unlisted FNA carded X2 - as an act and as a doubt, or of no
        kind - makes X2 possibly done, so X1 is possibly its endoscopic portion and 43235 is held base_within as a
        QUESTION, exactly as the FNA filed with its status doubted (round 2: no whole, 43235 READY for the combination).
        With no card, or a card the FactSet does not hold, X2 is possible too (D231: "no card, S possible"; 4.11). A
        denial, and the FNA carded to the colonoscopy X3, set nothing up."""
        members = [member('sel:0', '43235', X1, (E1,), procedural=True, supported=True)]
        filed = self.eus_with_no_event(extra={E3: act(Kind.FNA, X2, status=doubted(PERFORMED),
                                                      places=(sup(Landmark.PANCREAS),))})
        reference = (True, (C.Whole(X2, False),), [('base_included', ItemKind.QUESTION, C.WITHIN_CAUSE)])
        self.assertEqual((C.session_possibly_done(filed, X2), C.wholes(filed, X1),
                          held_of(C.combine(members, coding_of(filed), filed), 'sel:0')), reference)
        for name, entry in (('the FNA carded X2', entry_of(Kind.FNA, X2)),
                            ('a doubt about it', entry_of(Kind.FNA, X2, DOUBT_)),
                            ('of no kind', entry_of(None, X2)),
                            ('with no card', entry_of(Kind.FNA, None)),
                            ('a card the FactSet does not hold', entry_of(Kind.FNA, X9))):
            with self.subTest(name):
                R = self.eus_with_no_event(entries=(entry,))
                self.assertEqual((C.session_possibly_done(R, X2), C.wholes(R, X1),
                                  held_of(C.combine(members, coding_of(R), R), 'sel:0')), reference)
        for name, entries in (('nothing unlisted', ()), ('a denial', (entry_of(Kind.FNA, X2, DENIAL_),)),
                              ('carded to the colonoscopy', (entry_of(Kind.FNA, X3),))):
            with self.subTest(control=name):
                R = self.eus_with_no_event(entries=entries)
                self.assertEqual((C.session_possibly_done(R, X2), C.wholes(R, X1),
                                  held_of(C.combine(members, coding_of(R), R), 'sel:0')), (False, (), []))

    # row 3 ------------------------------------------------------------------------------------------------------------

    def egd_beside_a_tube_session(self, *, entries=(), extra=None) -> FactSet:
        """An upper endoscopy X1 (E1 done; 43235) beside a feeding-tube session X3 with no filed event, and a
        colonoscopy X4 (D119's shape, the PEG told only by pass 2)."""
        events = {E1: act(Kind.EXAMINATION, X1)}
        events.update(extra or {})
        return build(events, {X1: session_of(SessionKind.EGD), X3: session_of(SessionKind.FEEDING_TUBE),
                              X4: session_of(SessionKind.COLONOSCOPY)}, unlisted=entries)

    def test_d231_row_3_an_unlisted_peg_of_the_feeding_tube_session_holds_the_upper_endoscopys_base_code(self):
        """Row 3 (D119's PEG arm: "the unlisted acts of kind PEG or none whose card may be the feeding tube's session"):
        an unlisted PEG carded to the feeding-tube session - as an act or a doubt, of kind PEG or none - holds 43235
        base_included as a QUESTION quoting its unit, as the PEG filed there with its status doubted (step 4b lists it
        doubted) does (round 2: READY). A denial, a tube replacement and a PEG carded to the colonoscopy hold nothing. A
        PEG with no card or with a card the FactSet does not hold is read by no session in row 3 (it reads a carded act:
        refute-r4d-r1 of build-v2/w7r, F3); it holds 43235 through rule (c)'s own no-card arm instead (DECISIONS D256
        P1: the upper endoscopy lists a PEG filed in doubt with no session - these two subtests changed with D256)."""
        members = [member('sel:0', '43235', X1, (E1,))]
        filed = self.egd_beside_a_tube_session(extra={E5: act(Kind.PEG, X3, status=doubted(PERFORMED))})
        reference = [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)]
        self.assertEqual(held_of(C.combine(members, {X1: C.SessionActs(), X3: C.SessionActs(doubted=(E5,)),
                                                     X4: C.SessionActs()}, filed), 'sel:0'), reference)
        for name, entry in (('a PEG carded X3', entry_of(Kind.PEG, X3)),
                            ('a doubt about it', entry_of(Kind.PEG, X3, DOUBT_)),
                            ('of no kind', entry_of(None, X3))):
            with self.subTest(name):
                R = self.egd_beside_a_tube_session(entries=(entry,))
                combined = C.combine(members, coding_of(R), R)
                self.assertEqual(held_of(combined, 'sel:0'), reference)
                self.assertEqual(combined.bases['sel:0'].unlisted, (0,))
                self.assertEqual(C.base_hold(combined.bases['sel:0'], R).spans, (Span(900, 940),))
        for name, entry in (('a denial', entry_of(Kind.PEG, X3, DENIAL_)),
                            ('a tube replacement', entry_of(Kind.TUBE_REPLACEMENT, X3)),
                            ('carded to the colonoscopy', entry_of(Kind.PEG, X4))):
            with self.subTest(control=name):
                R = self.egd_beside_a_tube_session(entries=(entry,))
                self.assertEqual(held_of(C.combine(members, coding_of(R), R), 'sel:0'), [])
        for name, entry in (('with no card', entry_of(Kind.PEG, None)),
                            ('a card the FactSet does not hold', entry_of(Kind.PEG, X9))):
            with self.subTest(d256=name):
                R = self.egd_beside_a_tube_session(entries=(entry,))
                combined = C.combine(members, coding_of(R), R)
                self.assertEqual(C._unlisted_pegs(R, X1), ())  # row 3 reads a carded act only
                self.assertEqual((held_of(combined, 'sel:0'), combined.bases['sel:0'].unlisted), (reference, (0,)))

    # row 4 ------------------------------------------------------------------------------------------------------------

    def test_d231_row_4_an_unlisted_defining_act_opens_a_narrowed_codes_claims(self):
        """Row 4, D55's opening ("an unlisted act of a defining kind (or none) whose card may be of the code's family"):
        an ERCP with a done stone extraction (43264 on it) and 43265 counted with no filed lithotripsy. An unlisted
        lithotripsy carded to the ERCP - an act, a doubt, or of no kind - opens 43265's claims: it claims the
        extraction, and the two compete, as with the lithotripsy filed in doubt (round 2: 43265 claimed nothing). A
        denial, a lithotripsy carded to an upper endoscopy, and one with no card or a card the FactSet does not hold
        (row 4 reads a carded act: refute-r4d-r1 of build-v2/w7r, F3) open nothing."""
        members = [member('sel:0', '43264', X1, (E3,)), member('sel:1', '43265', X1, ())]
        sessions = {X1: session_of(SessionKind.ERCP), X2: session_of(SessionKind.EGD)}
        events = {E1: act(Kind.EXAMINATION), E3: act(Kind.STONE_EXTRACTION)}
        coding = {X1: C.SessionActs(reportable=(E3,)), X2: C.SessionActs()}
        competing = {'sel:0': ('43265',), 'sel:1': ('43264',)}
        filed = C.combine(members, coding, build({**events, E4: act(Kind.LITHOTRIPSY, status=doubted(PERFORMED))},
                                                 sessions))
        self.assertEqual((filed.claims['sel:1'], dict(filed.competes)), ((E3, E4), competing))
        for name, entry in (('carded X1', entry_of(Kind.LITHOTRIPSY, X1)),
                            ('a doubt', entry_of(Kind.LITHOTRIPSY, X1, DOUBT_)), ('of no kind', entry_of(None, X1))):
            with self.subTest(name):
                R = build(events, sessions, unlisted=(entry,))
                combined = C.combine(members, coding, R)
                self.assertEqual((C.claims('43265', R, ()), dict(combined.competes)), ((E3,), competing))
                self.assertEqual(held_of(combined, 'sel:0'), [('competing_codes', ItemKind.QUESTION,
                                                                C.COMPETING_CAUSE)])
        for name, entry in (('a denial', entry_of(Kind.LITHOTRIPSY, X1, DENIAL_)),
                            ('carded to the upper endoscopy', entry_of(Kind.LITHOTRIPSY, X2)),
                            ('with no card', entry_of(Kind.LITHOTRIPSY, None)),
                            ('a card the FactSet does not hold', entry_of(Kind.LITHOTRIPSY, X9))):
            with self.subTest(control=name):
                R = build(events, sessions, unlisted=(entry,))
                self.assertEqual((C.claims('43265', R, ()), dict(C.combine(members, coding, R).competes)), ((), {}))

    def test_d231_row_4_an_unlisted_dilation_is_another_act_of_a_technique_codes_own(self):
        """Row 4, D118's opening: one wire-guided dilation E3 (43248's); 43249 (balloon) may not account for it (R4)
        and has no act of its own, so it claims nothing. An unlisted dilation carded to the upper endoscopy - an act
        or a doubt, or of no kind - is another act of 43249's own (its technique unknown, on one stricture with E3:
        4.11), so 43249 claims E3, as with a dilation of no stated device filed in doubt (round 2: nothing). A denial,
        and a dilation with no card or a card the FactSet does not hold (row 4 reads a carded act: refute-r4d-r1 of
        build-v2/w7r, F3), open nothing."""
        sessions = {X1: session_of(SessionKind.EGD)}
        events = {E1: act(Kind.EXAMINATION), E3: act(Kind.DILATION, device=sup(Device.WIRE_BOUGIE))}
        self.assertEqual(C.claims('43249', build(events, sessions), ()), ())
        filed = build({**events, E4: act(Kind.DILATION, status=doubted(PERFORMED))}, sessions)
        self.assertEqual(C.claims('43249', filed, ()), (E3, E4))
        for name, entry in (('carded X1', entry_of(Kind.DILATION, X1)),
                            ('a doubt', entry_of(Kind.DILATION, X1, DOUBT_)), ('of no kind', entry_of(None, X1))):
            with self.subTest(name):
                self.assertEqual(C.claims('43249', build(events, sessions, unlisted=(entry,)), ()), (E3,))
        for name, entry in (('a denial', entry_of(Kind.DILATION, X1, DENIAL_)),
                            ('with no card', entry_of(Kind.DILATION, None)),
                            ('a card the FactSet does not hold', entry_of(Kind.DILATION, X9))):
            with self.subTest(control=name):
                self.assertEqual(C.claims('43249', build(events, sessions, unlisted=(entry,)), ()), ())

    # row 5 ------------------------------------------------------------------------------------------------------------

    def test_d231_row_5_an_unlisted_act_two_codes_admit_makes_them_compete(self):
        """Row 5, the competition over the act itself ("an unlisted act with a card that two counted codes' kinds both
        admit"): 45385 READY on its snare E2 and 45380 on its biopsy E3. An unlisted act of no kind carded to the
        colonoscopy ("a silent kind admits every kind") - an act or a doubt - may be either code's act, so both are
        held competing_codes, quoting its unit, as with the act filed in that session with its kind silent and its
        status doubted (round 2: both READY). The documented claims are unchanged (step 5a reads them); the synthetic
        claims are recorded beside them. A denial, a snare (45380 never admits it), an act of no kind carded to an upper
        endoscopy, and one with no card or a card the FactSet does not hold (row 5 reads a carded act: refute-r4d-r1 of
        build-v2/w7r, F3) compete for nothing."""
        members = [member('sel:0', '45385', X1, (E2,)), member('sel:1', '45380', X1, (E3,))]
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        events = {E1: act(Kind.EXAMINATION), E2: act(Kind.SNARE, lesion=sup(L1)), E3: act(Kind.BIOPSY)}
        coding = {X1: C.SessionActs(reportable=(E2, E3)), X2: C.SessionActs()}
        competing = {'sel:0': ('45380',), 'sel:1': ('45385',)}
        filed = build({**events, E4: act(SILENT, X1, status=doubted(PERFORMED))}, sessions)
        self.assertEqual(dict(C.combine(members, coding, filed).competes), competing)
        for name, entry in (('of no kind, carded X1', entry_of(None, X1)), ('a doubt', entry_of(None, X1, DOUBT_))):
            with self.subTest(name):
                R = build(events, sessions, unlisted=(entry,))
                combined = C.combine(members, coding, R)
                self.assertEqual(dict(combined.competes), competing)
                self.assertEqual(dict(combined.claims), {'sel:0': (E2,), 'sel:1': (E3,)})
                self.assertEqual((dict(combined.unlisted_claims), dict(combined.unlisted_contested)),
                                 ({'sel:0': (0,), 'sel:1': (0,)}, {'sel:0': (0,), 'sel:1': (0,)}))
                hold = combined.held['sel:0'][-1]
                self.assertEqual((hold.fact, hold.rank, hold.kind, hold.cause, hold.subject, hold.spans),
                                 ('competing_codes', 22, ItemKind.QUESTION, C.COMPETING_CAUSE, None,
                                  (Span(900, 940),)))
        for name, entry in (('a denial', entry_of(None, X1, DENIAL_)), ('a snare', entry_of(Kind.SNARE, X1)),
                            ('carded to the upper endoscopy', entry_of(None, X2)),
                            ('with no card', entry_of(None, None)),
                            ('a card the FactSet does not hold', entry_of(None, X9))):
            with self.subTest(control=name):
                R = build(events, sessions, unlisted=(entry,))
                combined = C.combine(members, coding, R)
                self.assertEqual((dict(combined.competes), dict(combined.unlisted_contested)), ({}, {}))

    def test_d231_row_5_a_narrowed_codes_opened_kinds_admit_an_unlisted_act(self):
        """Row 5 through D55's arm: 43265 READY on its lithotripsy E4 (so its other covered kind, the stone extraction,
        is opened) and 43264 counted with no filed extraction. An unlisted stone extraction carded to the ERCP - an act
        or a doubt - may be either code's act: both held competing_codes, as with the extraction filed in doubt. With
        nothing opening 43265's extraction (its E* empty, no lithotripsy filed or unlisted), only 43264 may account for
        the act and nothing competes."""
        members = [member('sel:0', '43264', X1, ()), member('sel:1', '43265', X1, (E4,))]
        sessions = {X1: session_of(SessionKind.ERCP)}
        events = {E1: act(Kind.EXAMINATION), E4: act(Kind.LITHOTRIPSY)}
        coding = {X1: C.SessionActs(reportable=(E4,))}
        competing = {'sel:0': ('43265',), 'sel:1': ('43264',)}
        filed = build({**events, E3: act(Kind.STONE_EXTRACTION, status=doubted(PERFORMED))}, sessions)
        self.assertEqual(dict(C.combine(members, coding, filed).competes), competing)
        for name, entry in (('carded X1', entry_of(Kind.STONE_EXTRACTION, X1)),
                            ('a doubt', entry_of(Kind.STONE_EXTRACTION, X1, DOUBT_))):
            with self.subTest(name):
                combined = C.combine(members, coding, build(events, sessions, unlisted=(entry,)))
                self.assertEqual((dict(combined.competes), dict(combined.unlisted_claims)),
                                 (competing, {'sel:0': (0,), 'sel:1': (0,)}))
        closed = build({E1: act(Kind.EXAMINATION)}, sessions, unlisted=(entry_of(Kind.STONE_EXTRACTION, X1),))
        combined = C.combine([member('sel:0', '43264', X1, ()), member('sel:1', '43265', X1, ())],
                             {X1: C.SessionActs()}, closed)
        self.assertEqual((dict(combined.unlisted_claims), dict(combined.competes)), ({'sel:0': (0,), 'sel:1': ()}, {}))

    def test_d231_row_5_an_act_shared_by_a_documented_and_a_synthetic_claim_names_both_in_one_item(self):
        """A code competing over a documented act and a synthetic one keeps ONE competing_codes item: its rivals the
        union (documented first), its spans both acts' units."""
        members = [member('sel:0', '43249', X1, (E2,)), member('sel:1', '43248', X1, ())]
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.DILATION, device=SILENT)}, {X1: session_of(SessionKind.EGD)},
                  unlisted=(entry_of(Kind.DILATION, X1),))
        combined = C.combine(members, coding_of(R), R)
        self.assertEqual(dict(combined.competes), {'sel:0': ('43248',), 'sel:1': ('43249',)})
        items = [h for h in combined.held['sel:0'] if h.fact == 'competing_codes']
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0].subject, items[0].spans), (E2, tuple(sorted(span_of(E2) + (Span(900, 940),)))))

    # the card: rule (c) and rows 3-5 read a carded act (refute-r4d-r1 of build-v2/w7r, F1, F3, F4) --------------------

    def test_f1_an_entry_of_no_kind_and_no_card_holds_no_office_visits_base_code(self):
        """refute-r4d-r1 of build-v2/w7r, F1 (critical): an office visit X0 (99213, its separately identifiable
        statement documented) and a same-day colonoscopy X1 (45385 on its cold snare E3), with one unlisted act naming
        no kind and no session. Read in every session, it held 99213 base_included with nothing the hold could name (the
        renderer refused the item and the document failed) and made 99213 and 45385 compete. 3.2.6 rule 3 reads "an
        unlisted act with a session card" and D231 row 5 "with a card": neither code holds the other now, and 99213 has
        no combination hold at all (the established procedure day moots the entry's date: D227 R2-3); with two sessions
        such an entry stays out of every base rule (DECISIONS D256: the named residual Q-UNNAMED). Carded to the
        colonoscopy, it is a possible act of 45385 alone (no rival): nothing either. F4's kinds with no card beside
        45378 alone hold nothing - step 4b never lists an act filed in doubt with no session of kind moderate sedation,
        other, an umbrella of interventions or an office visit beside a colonoscopy - but a biopsy, which it lists,
        holds 45378 (DECISIONS D256 P1, Q-CARD option (c): this subtest changed with D256)."""
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)),
                    X1: session_of(SessionKind.COLONOSCOPY, encounter=sup(THIS))}
        events = {E0: act(Kind.EM_VISIT, X0, separate=sup(STATED)), E1: act(Kind.EXAMINATION, X1),
                  E3: act(Kind.SNARE, X1, lesion=sup(L1), places=(sup(Landmark.SIGMOID_COLON),),
                          device=sup(Device.COLD_SNARE))}
        members = [member('sel:0', '99213', X0, (E0,)), member('sel:1', '45385', X1, (E3,), procedural=True,
                                                               supported=True)]
        coding = {X0: C.SessionActs(), X1: C.SessionActs(reportable=(E3,))}
        for name, entry in (('no kind, no card', entry_of(None, None)), ('no kind, a card the FactSet does not hold',
                                                                         entry_of(None, X9)),
                            ('no kind, carded to the colonoscopy', entry_of(None, X1))):
            with self.subTest(name):
                combined = C.combine(members, coding, build(events, sessions, unlisted=(entry,)))
                self.assertEqual((dict(combined.bases), dict(combined.competes)), ({}, {}))
                self.assertEqual((held_of(combined, 'sel:0'), held_of(combined, 'sel:1')), ([], []))
        for kind in (Kind.MODERATE_SEDATION, Kind.OTHER, Kind.INTERVENTION, Kind.EM_VISIT, Kind.BIOPSY):
            with self.subTest(f4=kind.value):  # F4: no K2 admission stands in for the card; D256 P1: 4b's doubted list
                colon = build({E1: act(Kind.EXAMINATION, X1)}, {X1: session_of(SessionKind.COLONOSCOPY)},
                              unlisted=(entry_of(kind, None),))
                found = C.base_included([member('sel:0', '45378', X1, (E1,))], coding_of(colon), colon)
                self.assertEqual([(b.unlisted, b.unlisted_kinds) for b in found],
                                 [((0,), (Kind.BIOPSY,))] if kind is Kind.BIOPSY else [])

    def test_f3_an_unlisted_biopsy_of_no_session_never_makes_two_sessions_codes_compete(self):
        """refute-r4d-r1 of build-v2/w7r, F3 (high): test_assess's two_sessions shape - a colonoscopy X1 (45380 on its
        transverse-colon biopsy E4) and an upper endoscopy X2 (43239 on its antral biopsy E5) - with one unlisted biopsy
        and no card. Read in every session, it was a possible act of both codes, so the commonest two-session encounter
        was told "43239 and 45380 are proposed for the same documented act". Row 5 reads "an unlisted act with a card":
        with no card it is no act either code competes for, and carded to either session only that session's code may
        account for it (no rival)."""
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        events = {E1: act(Kind.EXAMINATION, X1), E4: act(Kind.BIOPSY, X1, places=(sup(Landmark.TRANSVERSE_COLON),)),
                  E2: act(Kind.EXAMINATION, X2), E5: act(Kind.BIOPSY, X2, places=(sup(Landmark.GASTRIC_ANTRUM),))}
        members = [member('sel:0', '45380', X1, (E4,)), member('sel:1', '43239', X2, (E5,))]
        coding = {X1: C.SessionActs(reportable=(E4,)), X2: C.SessionActs(reportable=(E5,))}
        for name, entry, claimed in (('no card', entry_of(Kind.BIOPSY, None), {'sel:0': (), 'sel:1': ()}),
                                     ('carded to the colonoscopy', entry_of(Kind.BIOPSY, X1),
                                      {'sel:0': (0,), 'sel:1': ()}),
                                     ('carded to the upper endoscopy', entry_of(Kind.BIOPSY, X2),
                                      {'sel:0': (), 'sel:1': (0,)})):
            with self.subTest(name):
                combined = C.combine(members, coding, build(events, sessions, unlisted=(entry,)))
                self.assertEqual((dict(combined.competes), dict(combined.unlisted_claims)), ({}, claimed))
                self.assertEqual((held_of(combined, 'sel:0'), held_of(combined, 'sel:1')), ([], []))

    # rule (c), rule 5, the set and the property -----------------------------------------------------------------------

    def test_a_synthetic_act_that_names_no_kind_leaves_the_hold_naming_the_codes(self):
        """D177(1) beside the widened synthetic act: a lower-tract EUS code (45341) beside an upper EUS code (43242)
        names that code (the recorded residual) while no act is there to name. A doubt carded to the EUS that names no
        kind holds it too, and is no act the hold can name, so the hold still names 43242; a doubt about an FNA is
        named instead (an act). Whether the code is held is unchanged."""
        sessions = {X2: session_of(SessionKind.EUS, tract=UPPER)}
        events = {E2: act(Kind.EXAMINATION, X2), E3: act(Kind.FNA, X2, places=(sup(Landmark.PANCREAS),))}
        members = [member('sel:0', '45341', X2, (E2,)), member('sel:1', '43242', X2, (E3,))]
        for name, entries, expected in (('nothing unlisted', (), ((), (), ('43242',))),
                                        ('a doubt naming no kind', (entry_of(None, X2, DOUBT_),),
                                         ((0,), (), ('43242',))),
                                        ('a doubt about an FNA', (entry_of(Kind.FNA, X2, DOUBT_),),
                                         ((0,), (Kind.FNA,), ()))):
            with self.subTest(name):
                found = C.base_included(members, {X2: C.SessionActs()}, build(events, sessions, unlisted=entries))
                self.assertEqual([(b.unlisted, b.unlisted_kinds, b.named_codes) for b in found], [expected])

    def test_3_2_6_rule_5_an_unlisted_doubt_is_an_undatable_possible_procedure(self):
        """3.2.6 rule 5 over the synthetic act (D231: the same-day rule's release is an absence condition): an unlisted
        doubt of no E/M kind is an undatable possible procedure - event_time, cause unlisted - as an act filed in doubt
        with no date is. A denial, and a doubt about the visit itself, are not (round 2 read unlisted acts alone)."""
        entries = (entry_of(Kind.BIOPSY, None, DOUBT_, at=700), entry_of(None, None, DENIAL_, at=800),
                   entry_of(Kind.EM_VISIT, X0, DOUBT_, at=850))
        day, held = same_day(office(unlisted=entries))
        self.assertEqual(day.undatable_unlisted, (0,))
        self.assertEqual([(h.fact, h.subject, h.cause, h.spans) for h in held],
                         [('event_time', None, C.UNLISTED_CAUSE, (Span(700, 740),))])
        filed = office((E1, act(Kind.BIOPSY, X1, status=doubted(PERFORMED), date=SILENT)))
        self.assertEqual([(h.fact, h.subject) for h in same_day(filed)[1]], [('event_time', E1)])
        self.assertEqual(same_day(office(unlisted=entries[1:]))[1], ())

    def test_the_synthetic_set_is_evaluates(self):
        """D231: "the four modules read one set" - the entries read as synthetic acts here are exactly
        evaluate.synthetic_possible's (step 4a's, read only): the kept unlisted acts and doubts, in stored order."""
        whats = (ACT_, DOUBT_, DENIAL_)
        entries = tuple(entry_of(kind, session, what, at=1000 + 50 * index) for index, (kind, session, what) in
                        enumerate((kind, session, what) for kind in (None, Kind.BIOPSY, Kind.EXAMINATION)
                                  for session in (None, X1, X9) for what in whats))
        R = build({E1: act(Kind.EXAMINATION)}, COLONOSCOPY, unlisted=entries)
        found = tuple(R.unlisted[index] for index in C.synthetic(R))
        self.assertEqual(found, EV.synthetic_possible(R))
        self.assertEqual(len(found), 18)

    @hypothesis.settings(max_examples=150, deadline=None, derandomize=True)
    @hypothesis.given(events=st.lists(EVENT_FACTS, min_size=1, max_size=4),
                      entry=st.builds(entry_of, _choice((None, Kind.EXAMINATION, Kind.FNA, Kind.PEG, Kind.LITHOTRIPSY,
                                                         Kind.DILATION, Kind.SNARE, Kind.BIOPSY, Kind.EM_VISIT,
                                                         Kind.REMOVAL, Kind.STONE_EXTRACTION)),
                                      _choice((X1, X2, X3, X9, None)), _choice((ACT_, DOUBT_, DENIAL_))))
    def test_an_added_synthetic_act_never_releases_anything(self, events, entry):
        """D216's direction, as a property: an added kept unlisted entry (any nature, kind and card) never shrinks a
        claim, a competition, the acts a base hold reads or a whole, and never releases a held member - a doubt is
        never an absence (4.2), so an omission pass 2 reported only ever adds holds."""
        facts = {Id(IdFamily.EVENT, index + 1): event(**item) for index, item in enumerate(events)}
        facts[E0] = act(Kind.EM_VISIT, X0)
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.EGD),
                    X2: session_of(SessionKind.ERCP, tract=UPPER), X3: session_of(SessionKind.EUS, tract=UPPER)}
        lesions = {L1: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS,), distinct=(L2,)), L2: lesion_of()}
        R = build(facts, sessions, lesions=lesions)
        W = build(facts, sessions, lesions=lesions, unlisted=(entry,))
        place = {SessionKind.ERCP: X2, SessionKind.EUS: X3, SessionKind.OFFICE_EM: X0}
        members = [member(f'sel:{index}', code, place.get(catalogue.family_for_code(code), X1))
                   for index, code in enumerate(CODES + ('99213', '43259'))]
        before, after = C.combine(members, coding_of(R), R), C.combine(members, coding_of(W), W)
        where = (entry.what, entry.kind, entry.session)
        self.assertLessEqual({key for key, held in before.held.items() if held},
                             {key for key, held in after.held.items() if held}, where)
        for key in before.claims:
            self.assertLessEqual(set(before.claims[key]), set(after.claims[key]), where)
        self.assertLessEqual({(key, rival) for key, rivals in before.competes.items() for rival in rivals},
                             {(key, rival) for key, rivals in after.competes.items() for rival in rivals}, where)
        for key, found in before.bases.items():
            self.assertLessEqual(set(found.reportable + found.doubted), set(after.bases[key].reportable
                                                                            + after.bases[key].doubted), where)
        for session in sessions:
            self.assertLessEqual({whole.session for whole in C.wholes(R, session)},
                                 {whole.session for whole in C.wholes(W, session)}, where)
            self.assertLessEqual(C.session_possibly_done(R, session), C.session_possibly_done(W, session), where)
            self.assertGreaterEqual(C.session_done(R, session), C.session_done(W, session), where)


# --- D29's site fit in the claims (DECISIONS D240) --------------------------------------------------------------------


class SiteFit(SimpleTestCase):
    """DECISIONS D240 (6c B; the installed reading kept - D29: "A verified target outside the class does not support"):
    a site-specific dilation code never claims an act whose target is established outside its class, so the esophageal
    and the duodenal dilation codes of two strictures never compete; anything not established leaves the act claimed
    (fail-closed); the reading equals evaluate's SITE row (one rule, two readers)."""

    def two_strictures(self, second_places=(sup(Landmark.DUODENAL_BULB),), second_lesion=None, lesions=None) -> FactSet:
        """"The distal esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated with a
        balloon." (probe_site_fit's and probe_ho8b_fit's document, as facts): E2 at the distal esophagus, E3 at
        ``second_places`` (and ``second_lesion``)."""
        return build({E1: act(Kind.EXAMINATION, X1),
                      E2: act(Kind.DILATION, X1, device=sup(Device.BALLOON), places=(sup(Landmark.DISTAL_ESOPHAGUS),)),
                      E3: act(Kind.DILATION, X1, device=sup(Device.BALLOON), places=second_places,
                              lesion=second_lesion)}, {X1: session_of(SessionKind.EGD)}, lesions=lesions)

    def test_d240_each_site_code_claims_its_own_sites_act_and_they_never_compete(self):
        """D240's input: 43249 claims the esophageal act and 43245 the duodenal one - with or without their E* - and
        combine holds neither competing_codes (round 2: both held). D118 never re-adds the other site's act (the two
        acts are on one stricture by 4.11, but 43249 could never account for a duodenal dilation), and an E* naming it
        is not claimed (evaluate reads only the acts within the class)."""
        R = self.two_strictures()
        self.assertEqual((C.claims('43249', R, (E2,)), C.claims('43245', R, (E3,))), ((E2,), (E3,)))
        self.assertEqual((C.claims('43249', R, ()), C.claims('43245', R, ())), ((E2,), (E3,)))
        self.assertTrue(C.one_stricture(R, E2, E3))
        self.assertEqual(C.claims('43249', R, (E2, E3)), (E2,))
        members = [member('sel:0', '43249', X1, (E2,), procedural=True, supported=True),
                   member('sel:1', '43245', X1, (E3,), procedural=True, supported=True)]
        combined = C.combine(members, {X1: C.SessionActs(reportable=(E2, E3))}, R)
        self.assertEqual((dict(combined.competes), {key: keys(held) for key, held in combined.held.items()}),
                         ({}, {'sel:0': [], 'sel:1': []}))

    def test_d240_a_target_not_established_outside_the_class_keeps_the_claim(self):
        """Fail-closed (4.2: a doubt is never an absence; 4.11): E3's place unresolved, doubted toward the esophagus,
        absent, at an anastomosis or a stoma (D29's "an ambiguous target holds"), spanning both classes, or its lesion
        not established, or that lesion's place not established - 43249 claims E3 and competes with 43245. E3's place
        taken from its supported lesion counts like its own; a negated place beside an outside one is established."""
        lesion_places = {L2: lesion_of(places=(Landmark.DUODENAL_BULB,)),
                         L3: {A.PLACES: (unres(Landmark.DUODENAL_BULB),), A.DISTINCT_FROM: (), A.SAME_AS: ()}}
        members = (member('sel:0', '43249', supporting=(E2,)), member('sel:1', '43245', supporting=(E3,)))
        kept = {
            'place unresolved': self.two_strictures((unres(Landmark.DUODENAL_BULB),)),
            'place doubted': self.two_strictures((doubted(Landmark.DUODENAL_BULB, Landmark.DISTAL_ESOPHAGUS),)),
            'no place': self.two_strictures(()),
            'an anastomosis': self.two_strictures((sup(Landmark.ANASTOMOSIS),)),
            'a stoma': self.two_strictures((sup(Landmark.STOMA),)),
            'spanning': self.two_strictures((sup(Landmark.DUODENAL_BULB), sup(Landmark.DISTAL_ESOPHAGUS))),
            'lesion unresolved': self.two_strictures((), unres(L2), lesion_places),
            "the lesion's place unresolved": self.two_strictures((), sup(L3), lesion_places),
        }
        for name, R in kept.items():
            with self.subTest(name):
                self.assertFalse(C.site_outside('43249', R, E3))
                self.assertIn(E3, C.claims('43249', R, ()))
                self.assertEqual(compete(R, *members), {'sel:0': ('43245',), 'sel:1': ('43249',)})
        apart = {'through its lesion': self.two_strictures((), sup(L2), lesion_places),
                 'a negated place beside it': self.two_strictures((neg(Landmark.DISTAL_ESOPHAGUS),
                                                                   sup(Landmark.DUODENAL_BULB)))}
        for name, R in apart.items():
            with self.subTest(apart=name):
                self.assertTrue(C.site_outside('43249', R, E3))
                self.assertEqual(compete(R, *members), {})

    def test_d240_a_deleted_member_of_the_lesions_places_is_the_named_release_too(self):
        """D240's named release through the target LESION (refute-r4d-r1 of build-v2/w7r, F6; its row2_separate
        input): a balloon dilation E3 listed at the pylorus on lesion L1, whose places are the distal esophagus and the
        pylorus, may be in 43249's class, so 43249 claims E3 and competes with 43245. Deleting the esophageal member
        from L1's places (9.4's deleted-member weakening, on the lesion's list rather than the act's) sets E3 outside
        43249's class: 43249 claims nothing and the competition ends - the same named release as a deleted
        target.places member, which Monotone names for both lists."""
        members = (member('sel:0', '43245', supporting=(E3,)), member('sel:1', '43249'))
        for name, places, expected in (
                ('the lesion at the distal esophagus and the pylorus', (Landmark.DISTAL_ESOPHAGUS, Landmark.PYLORUS),
                 (False, (E3,), {'sel:0': ('43249',), 'sel:1': ('43245',)})),
                ('its esophageal member deleted', (Landmark.PYLORUS,), (True, (), {}))):
            with self.subTest(name):
                R = build({E1: act(Kind.EXAMINATION, X1),
                           E3: act(Kind.DILATION, X1, device=sup(Device.BALLOON), lesion=sup(L1),
                                   places=(sup(Landmark.PYLORUS),))},
                          {X1: session_of(SessionKind.EGD)}, lesions={L1: lesion_of(places=places)})
                self.assertEqual((C.site_outside('43249', R, E3), C.claims('43249', R, ()), compete(R, *members)),
                                 expected)

    def test_d240_the_site_fit_is_evaluates_site_row(self):
        """One rule, two readers (D240 routes D29 to both): site_outside equals evaluate's SITE row failing (step 4a's,
        read only through evaluate.code_rows) for every site-specific dilation code over a cross product of place lists
        and lesion facts - with both answers exercised."""
        places = ((), (sup(Landmark.DISTAL_ESOPHAGUS),), (sup(Landmark.PYLORUS),), (sup(Landmark.DUODENAL_BULB),),
                  (sup(Landmark.GASTROESOPHAGEAL_JUNCTION),), (sup(Landmark.AMPULLA),), (sup(Landmark.JEJUNUM),),
                  (sup(Landmark.ANASTOMOSIS),), (sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.PYLORUS)),
                  (unres(Landmark.PYLORUS),), (doubted(Landmark.PYLORUS, Landmark.DISTAL_ESOPHAGUS),),
                  (neg(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.PYLORUS)))
        lesions = {L1: lesion_of(places=(Landmark.PYLORUS,)), L2: lesion_of(places=(Landmark.DISTAL_ESOPHAGUS,)),
                   L3: {A.PLACES: (unres(Landmark.PYLORUS),), A.DISTINCT_FROM: (), A.SAME_AS: ()}}
        lesion_facts = (None, sup(L1), sup(L2), sup(L3), unres(L1), neg(L1))
        codes = tuple(str(code) for code in sorted(catalogue.DILATION_SITES))
        answers = {True: 0, False: 0}
        for listed in places:
            for lesion in lesion_facts:
                R = build({E1: act(Kind.EXAMINATION, X1), E3: act(Kind.DILATION, X1, places=listed, lesion=lesion)},
                          {X1: session_of(SessionKind.EGD)}, lesions=lesions)
                for code in codes:
                    rows = [row for row in EV.code_rows(code, rq.spec(code).groups[0], R, E3)
                            if row.requirement is Tag.SITE]
                    self.assertEqual(len(rows), 1, code)
                    outside = C.site_outside(code, R, E3)
                    self.assertEqual(outside, rows[0].truth is EV.Truth.F, (code, listed, lesion))
                    answers[outside] += 1
        self.assertGreater(min(answers.values()), 30, answers)

    def test_d240_codes_with_no_site_class_never_read_it(self):
        """Only the codes D29 names read the site fit: an upper endoscopy's and a colonoscopy's biopsy codes claim
        their acts wherever they are listed."""
        R = build({E1: act(Kind.EXAMINATION), E2: act(Kind.BIOPSY, places=(sup(Landmark.DUODENAL_BULB),))},
                  {X1: session_of(SessionKind.EGD)})
        for code in ('43239', '45380'):
            with self.subTest(code=code):
                self.assertIsNone(catalogue.site_class(code))
                self.assertFalse(C.site_outside(code, R, E2))
        self.assertEqual(C.claims('43239', R, ()), (E2,))


# --- a part session beside the whole its claim names (DECISIONS D244 R-N3) -------------------------------------------


class PartOfWhole(SimpleTestCase):
    """DECISIONS D244 R-N3 (6c's P1; mutation MB): a part session's base code is held beside a whole its own
    part_of_session claim names, whatever that whole's counted codes include."""

    def sigmoidoscopy_in_a_colonoscopy(self, part_of=sup(X1)) -> FactSet:
        """6c's case N3, its right filing (synthetic: "The colonoscope was advanced to the cecum." / "A flexible
        sigmoidoscopy to the sigmoid colon was performed as part of the colonoscopy."): a colonoscopy X1 (E1 done) and a
        flexible sigmoidoscopy X2 (E2 done) whose part_of_session names X1."""
        return build({E1: act(Kind.EXAMINATION, X1), E2: act(Kind.EXAMINATION, X2)},
                     {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.FLEX_SIG, part_of=part_of)})

    def test_r_n3_a_part_sessions_base_code_is_held_beside_its_stated_whole_whatever_its_codes_include(self):
        """N3 (i): 45330 beside 45378, which includes no sigmoidoscopy by the catalogue's table - held base_within as an
        EXPLANATION (C3's established whole), 45378 untouched (round 2: 45330 READY, the whole's codes "hold
        nothing"). DECISIONS D257: ``within`` names the stated whole's counted code, 45378 (refute-r4d-r2 P5: () was
        worded as an endoscopic ultrasound)."""
        R = self.sigmoidoscopy_in_a_colonoscopy()
        members = [member('sel:0', '45378', X1, (E1,), procedural=True, supported=True),
                   member('sel:1', '45330', X2, (E2,), procedural=True, supported=True)]
        self.assertFalse(catalogue.includes_examination('45378', SessionKind.FLEX_SIG))
        self.assertEqual(C.wholes(R, X2), (C.Whole(X1, True),))
        self.assertEqual([(b.key, b.code, b.wholes, b.within, b.established) for b in C.base_within(members, R)],
                         [('sel:1', '45330', (X1,), ('45378',), True)])
        combined = C.combine(members, coding_of(R), R)
        self.assertEqual({key: held_of(combined, key) for key in combined.held},
                         {'sel:0': [], 'sel:1': [('base_included', ItemKind.EXPLANATION, C.WITHIN_CAUSE)]})

    def test_r_n3_the_claim_weakened_holds_it_as_a_question(self):
        """P-MONO: the part_of_session claim not established - unresolved, doubted toward another session, or a
        negation left open - makes X1 a possible whole that still names it: 45330 held as a QUESTION, never released.
        The claim established against it (negated), or silent (6c's variant (iii), its residual), sets nothing up."""
        members = [member('sel:0', '45378', X1, (E1,)), member('sel:1', '45330', X2, (E2,))]
        open_negation = fact(Res.UNRESOLVED, X1, State.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
        for name, part_of in (('unresolved', unres(X1)), ('doubted', doubted(X1, X3)),
                              ('negation open', open_negation)):
            with self.subTest(name):
                R = self.sigmoidoscopy_in_a_colonoscopy(part_of)
                found = C.base_within(members, R)
                self.assertEqual([(b.code, X1 in b.wholes, b.established) for b in found], [('45330', True, False)])
                self.assertEqual(C.base_within_hold(found[0], R).kind, ItemKind.QUESTION)
        for name, part_of in (('negated', neg(X1)), ('silent', None)):
            with self.subTest(control=name):
                self.assertEqual(C.base_within(members, self.sigmoidoscopy_in_a_colonoscopy(part_of)), ())

    def test_r_n3_c4s_structural_whole_keeps_the_includes_rule(self):
        """D244 names C3's stated whole: C-4's structural one keeps 4.7's rule - 43231 (the esophagoscopic EUS)
        includes no EGD, so 43235 beside it is not held (test_codes_that_include_no_upper_endoscopy_hold_nothing). The
        same two codes with the EGD's part_of_session naming the EUS are held (the document states the whole), beside
        43231, the stated whole's counted code (DECISIONS D257)."""
        members = [member('sel:0', '43235', X1, (E1,)), member('sel:1', '43231', X2, (E2,))]
        self.assertEqual(C.base_within(members, egd_eus()), ())
        stated = C.base_within(members, egd_eus(part_of=sup(X2)))
        self.assertEqual([(b.wholes, b.within, b.established) for b in stated], [((X2,), ('43231',), True)])

    def test_d257_within_names_every_counted_code_of_a_stated_whole_and_c4s_including_codes_alone(self):
        """DECISIONS D257 (refute-r4d-r2 P5; r4d Q-N3W): ``within`` names the stated whole's counted codes, whatever
        they include - as D244 holds the code beside the stated whole - each once, in member order: 45330 within the
        colonoscopy names 45378 and 45380 alike, as an EXPLANATION, and as a QUESTION when the claim is only
        possible (unresolved). C-4's structural whole keeps naming only its codes that include the examination (43242,
        not 43231 beside it). A stated whole with no counted code still holds the code beside none."""
        R = self.sigmoidoscopy_in_a_colonoscopy()
        members = [member('sel:0', '45378', X1, (E1,)), member('sel:1', '45330', X2, (E2,)),
                   member('sel:2', '45380', X1, (E1,)), member('sel:3', '45378', X1, (E1,))]
        self.assertEqual([(b.code, b.within, b.established) for b in C.base_within(members, R)],
                         [('45330', ('45378', '45380'), True)])
        possible = C.base_within(members, self.sigmoidoscopy_in_a_colonoscopy(unres(X1)))
        self.assertEqual([(b.code, b.within, b.established) for b in possible],
                         [('45330', ('45378', '45380'), False)])
        self.assertEqual(C.base_within_hold(possible[0], R).kind, ItemKind.QUESTION)
        structural = C.base_within([member('sel:0', '43235', X1, (E1,)), member('sel:1', '43231', X2, (E2,)),
                                    member('sel:2', '43242', X2, (E3,))], egd_eus())
        self.assertEqual([(b.within, b.established) for b in structural], [(('43242',), True)])
        alone = C.base_within([member('sel:1', '45330', X2, (E2,))], R)
        self.assertEqual([(b.wholes, b.within, b.established) for b in alone], [((X1,), (), True)])


# --- the add-on codes (DECISIONS D255) --------------------------------------------------------------------------------


def office_and_prolonged() -> FactSet:
    """An office visit X0 (this encounter): the visit E0 (its basis total time) and its prolonged time E1 -
    test_assess's office_prolonged, as facts."""
    return build({E0: act(Kind.EM_VISIT, X0, basis=sup(ct.EmBasis.TOTAL_TIME)), E1: act(Kind.EM_PROLONGED, X0)},
                 {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS))})


def ercp_cannulated(*extra) -> FactSet:
    """An ERCP X1: its examination E1 and a biliary cannulation E2 (refute-r3c-r1 p02's "no cholangioscopy act"), then
    ``extra`` (event, facts) pairs in order."""
    events = {E1: act(Kind.EXAMINATION), E2: act(Kind.CANNULATION)}
    events.update(dict(extra))
    return build(events, {X1: session_of(SessionKind.ERCP)})


def worded(found, assessment: AS.Assessment, R: FactSet) -> tuple:
    """(message, the slots' codes and listed acts, the question) of ``found``'s one item as the renderer and read time
    word it (overlay.item_slots, then wording.build; step 5c's and step 3c's, read only)."""
    item = found.item
    slots = overlay.item_slots(item, found.key, assessment.combination, R)
    sentence = wording.build(wording.Message(item.message.value), slots, TA.TEXT)
    return item.message, slots.codes, slots.listed, sentence.question


class AddOnCodes(SimpleTestCase):
    """DECISIONS D255 (refute-r3c-r1 R3C1-02; 4d DQ2; r3c Q3): an add-on code - a key of engine/assess.ADDON_PRIMARIES
    (43273, 91013, 99153, 99417) - is never a code that includes another under rule (a) (base_included, base_explained,
    base_within): it never causes such a hold and is never named in those items' codes. An add-on and its primaries are
    governed by assess's ADDON row alone."""

    def test_d255_the_add_ons_are_the_keys_of_assess_primaries_table(self):
        """combination.is_addon reads the catalogue's add-on profile (engine/assess imports combination); it names
        exactly ADDON_PRIMARIES' keys, and no other code, however written."""
        self.assertEqual({code for code in catalogue.CODES if C.is_addon(str(code))}, set(AS.ADDON_PRIMARIES))
        self.assertEqual(sorted(AS.ADDON_PRIMARIES), [43273, 91013, 99153, 99417])
        odd = ('', '4523', 'abcde', '99999', '45378', '99215', '43260')
        self.assertEqual([code for code in odd if C.is_addon(code)], [])

    def test_d255_an_office_add_on_never_holds_the_visit_code(self):
        """99215, 99205 or 99245 beside 99417 (each a primary of it): no base hold, nothing beside under rule (a), and
        no combination hold at all (refute-r3c-r1 p02: held base_included, "99215 is normally not reported separately
        from it" - the inverse of ADDON_PRIMARIES). 99213 beside 99417 (no primary of it): no rule (a) hold either;
        99417's own ADDON row holds 99417 (assess). Two visit codes still hold each other beside the add-on (rule (a)
        unchanged for every other code), the add-on named by neither."""
        R = office_and_prolonged()
        coding = {X0: C.SessionActs()}
        for code in ('99215', '99205', '99245', '99213'):
            with self.subTest(code=code):
                combined = C.combine([member('sel:0', code, X0, (E0,)), member('sel:1', '99417', X0, (E1,))], coding, R)
                self.assertEqual((dict(combined.bases), dict(combined.within), dict(combined.competes)), ({}, {}, {}))
                self.assertEqual((held_of(combined, 'sel:0'), held_of(combined, 'sel:1')), ([], []))
        both = C.combine([member('sel:0', '99215', X0, (E0,)), member('sel:1', '99214', X0, (E0,)),
                          member('sel:2', '99417', X0, (E1,))], coding, R)
        self.assertEqual([(key, found.beside, found.named_codes) for key, found in both.bases.items()],
                         [('sel:0', ('99214',), ('99214',)), ('sel:1', ('99215',), ('99215',))])

    def test_d255_an_ercp_add_on_never_holds_and_is_never_named_beside_the_diagnostic_code(self):
        """43260 beside 43273 with no cholangioscopy act documented (refute-r3c-r1 p02): no base hold (round 2:
        base_included, "43273 is also proposed ...; 43260 is normally not reported separately from it"). Beside 43262
        and 43273 on a cholangioscopy and a sphincterotomy, reportable: held, naming 43262 only - an EXPLANATION (rule
        (b)'s reportable acts). The within rule (D255 there too): in an ERCP whole the upper endoscopy's own
        part_of_session claim names, 43273 is no counted code of the whole - never named, and the whole whose only
        counted code it is holds 43235 beside none."""
        bare = ercp_cannulated()
        self.assertEqual(C.base_included([member('sel:0', '43260', X1, (E1,)), member('sel:1', '43273', X1, ())],
                                         {X1: C.SessionActs()}, bare), ())
        cut = ercp_cannulated((E3, act(Kind.CHOLANGIOSCOPY)), (E4, act(Kind.SPHINCTEROTOMY)))
        found = C.base_included([member('sel:0', '43262', X1, (E4,)), member('sel:1', '43273', X1, (E3,)),
                                 member('sel:2', '43260', X1, (E1,))], {X1: C.SessionActs(reportable=(E3, E4))}, cut)
        self.assertEqual([(b.code, b.beside, b.others, b.named_codes, b.established) for b in found],
                         [('43260', ('43262',), ('43262',), ('43262',), True)])
        self.assertEqual(C.base_hold(found[0], cut).kind, ItemKind.EXPLANATION)
        stated = build({E1: act(Kind.EXAMINATION), E5: act(Kind.EXAMINATION, X2)},
                       {X1: session_of(SessionKind.ERCP), X2: session_of(SessionKind.EGD, part_of=sup(X1))})
        within = C.base_within([member('sel:0', '43235', X2, (E5,)), member('sel:1', '43260', X1, (E1,)),
                                member('sel:2', '43273', X1, ())], stated)
        self.assertEqual([(b.code, b.wholes, b.within, b.established) for b in within],
                         [('43235', (X1,), ('43260',), True)])
        alone = C.base_within([member('sel:0', '43235', X2, (E5,)), member('sel:2', '43273', X1, ())], stated)
        self.assertEqual([(b.code, b.wholes, b.within) for b in alone], [('43235', (X1,), ())])

    def test_d255_the_refuters_add_on_pairs_through_assess_and_the_renderers_slots(self):
        """refute-r3c-r1 p02 and p08 through engine/assess (test_assess's synthetic fixtures, as the refuter ran them):
        99215, 99205 or 99245 with 99417 - both READY; 99213 with 99417 - 99213 READY (not held under rule (a)), 99417
        held by its ADDON row alone; 43260 with 43273 and no cholangioscopy act - 43260 READY; 43260 with 43262 and
        43273 (test_assess.ercp(stone=False)) - held base_explained, its item naming 43262 only, as the renderer and
        read time word it. p08: the stored record of 99215 with 99417 carries no base question, and rejecting 99215
        leaves nothing that names 99417 as including it."""
        from tests.v2 import test_overlay as TO

        office = TA.office_prolonged().build()
        for code in ('99215', '99205', '99245'):
            with self.subTest(code=code):
                found = TA.by_code(TA.run(office, (code, 1), ('99417', 2)))
                self.assertEqual({key: value.status for key, value in found.items()},
                                 {code: Outcome.READY, '99417': Outcome.READY})
        visit = TA.by_code(TA.run(office, ('99213', 1), ('99417', 2)))
        self.assertEqual((visit['99213'].status, visit['99213'].held_facts), (Outcome.READY, ()))
        self.assertEqual([held.cause for held in visit['99417'].held_facts], [AS.ADDON_CAUSE])
        doc = EF.Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        doc.act(2, Kind.CANNULATION, access=EF.sup(ct.AccessOutcome.ACHIEVED), duct=EF.sup(ct.Duct.BILIARY))
        self.assertEqual(TA.by_code(TA.run(doc.build(), ('43260', 1), ('43273', 2)))['43260'].status, Outcome.READY)
        R = TA.ercp(stone=False).build()
        assessment = TA.run(R, ('43262', 4), ('43273', 3), ('43260', 1))
        found = TA.by_code(assessment)
        self.assertEqual((found['43262'].status, found['43273'].status, found['43260'].status),
                         (Outcome.READY, Outcome.READY, Outcome.NEEDS_CLARIFICATION))
        message, codes, listed, question = worded(found['43260'], assessment, R)
        self.assertEqual((message, codes, listed), (Q.MessageId.BASE_EXPLAINED, ('43262',), ()))
        self.assertIn('43262', question)
        self.assertNotIn('43273', question)
        case = TO.Case(office, ('99215', 1), ('99417', 2))
        self.assertEqual([(row.code, row.status, tuple(row.questions)) for row in case.rows],
                         [('99215', 'ready', ()), ('99417', 'ready', ())])

    def test_d268_an_act_a_counted_add_on_accounts_for_holds_no_base_code_of_its_session(self):
        """DECISIONS D268 (refute-r4d-r1 V8R4D1-1, high; r4d Q-ADDON-ACT option (b), narrowed): base rules (b) and (c)
        read no act that a counted add-on code of the same session accounts for as its supporting act (its E*). At the
        combination: an ERCP X1 (its examination E1, a biliary cannulation E2, a cholangioscopy E3), 43260 and 43273
        counted, 43273's E* the cholangioscopy - reportable (rule (b)) or doubted (rule (c)), the cholangioscopy holds
        43260 beside nothing: no base hold (round w8r: base_explained "Is 43260 reported separately from cholangioscopy
        ...?"). Without 43273 counted the rules read as built: 43260 alone is held, reading the cholangioscopy; and so
        it is when 43273 is matched to another session, or when 43273's E* does not hold the act (the acts are the
        counted add-on's own, never a kind). Beside 43262 (on the sphincterotomy E4) and 43273, 43260 stays held naming
        43262 only, now on the sphincterotomy alone - an EXPLANATION (rule (b))."""
        R = ercp_cannulated((E3, act(Kind.CHOLANGIOSCOPY)))
        diagnostic, addon = member('sel:0', '43260', X1, (E1,)), member('sel:1', '43273', X1, (E3,))
        self.assertEqual((C.addon_acts([diagnostic, addon], X1), C.addon_acts([diagnostic, addon], X2),
                          C.addon_acts([diagnostic], X1)), (frozenset({E3}), frozenset(), frozenset()))
        for rule, coding in (('(b) reportable', C.SessionActs(reportable=(E3,))),
                             ('(c) doubted', C.SessionActs(doubted=(E3,)))):
            with self.subTest(rule=rule):
                self.assertEqual(C.base_included([diagnostic, addon], {X1: coding}, R), ())
                combined = C.combine([diagnostic, addon], {X1: coding}, R)
                self.assertEqual((held_of(combined, 'sel:0'), held_of(combined, 'sel:1')), ([], []))
                for name, members in (('43260 alone', [diagnostic]),
                                      ('43273 matched to another session', [diagnostic,
                                                                            member('sel:1', '43273', X2, (E3,))]),
                                      ("43273's E* without the act", [diagnostic, member('sel:1', '43273', X1, ())])):
                    with self.subTest(rule=rule, as_built=name):
                        found = C.base_included(members, {X1: coding}, R)
                        self.assertEqual([(b.code, b.beside, b.reportable, b.doubted) for b in found],
                                         [('43260', (), coding.reportable, coding.doubted)])
        cut = ercp_cannulated((E3, act(Kind.CHOLANGIOSCOPY)), (E4, act(Kind.SPHINCTEROTOMY)))
        found = C.base_included([member('sel:0', '43262', X1, (E4,)), member('sel:1', '43273', X1, (E3,)),
                                 member('sel:2', '43260', X1, (E1,))], {X1: C.SessionActs(reportable=(E3, E4))}, cut)
        self.assertEqual([(b.code, b.named_codes, b.reportable, b.established) for b in found],
                         [('43260', ('43262',), (E4,), True)])
        self.assertEqual(C.base_hold(found[0], cut).kind, ItemKind.EXPLANATION)

    def test_d268_the_refuters_ercp_through_assess_both_codes_ready(self):
        """D268 on refute-r4d-r1's input (scratch/v8_addon_act.py) through engine/assess: an ERCP, its examination done,
        a biliary cannulation achieved, a cholangioscopy performed; 43260 + 43273 - 43260 READY and 43273 READY, D255's
        stated effect ("43260 beside 43273 alone is READY") reached on its realistic input. Without 43273 counted (43260
        alone) the rules read as built: 43260 held base_explained, its item listing the cholangioscopy. With no
        cholangioscopy act, 43260 + 43273: 43260 READY (D255), 43273 held by its own rule (not documented)."""
        def doc(cholangioscopy=True):
            built = EF.Doc()
            built.session(1, SessionKind.ERCP)
            built.exam(1)
            built.act(2, Kind.CANNULATION, access=EF.sup(ct.AccessOutcome.ACHIEVED), duct=EF.sup(ct.Duct.BILIARY))
            if cholangioscopy:
                built.act(3, Kind.CHOLANGIOSCOPY, duct=EF.sup(ct.Duct.BILIARY))
            return built.build()

        R = doc()
        both = TA.by_code(TA.run(R, ('43260', 1), ('43273', 3)))
        self.assertEqual({code: (found.status, found.held_facts) for code, found in both.items()},
                         {'43260': (Outcome.READY, ()), '43273': (Outcome.READY, ())})
        assessment = TA.run(R, ('43260', 1))
        alone = assessment.codes[0]
        self.assertEqual((alone.status, [held.cause for held in alone.held_facts]),
                         (Outcome.NEEDS_CLARIFICATION, [C.BASE_CAUSE]))
        message, codes, listed, question = worded(alone, assessment, R)
        self.assertEqual((message, codes, listed), (Q.MessageId.BASE_EXPLAINED, (), (Kind.CHOLANGIOSCOPY,)))
        self.assertIn('43260', question)
        bare = TA.by_code(TA.run(doc(False), ('43260', 1), ('43273', 2)))
        self.assertEqual((bare['43260'].status, bare['43273'].status), (Outcome.READY, Outcome.NEEDS_CLARIFICATION))
        self.assertNotIn(C.BASE_CAUSE, [held.cause for held in bare['43273'].held_facts])


# --- an unlisted entry with no card (DECISIONS D256) ------------------------------------------------------------------


def filed_form(kind, **over) -> dict:
    """The act pass 1 would have filed for a kept unlisted entry of ``kind`` with no card (coverage's
    _filed_doubted_form): its kind supported (an empty slot for None), its status a doubt that it was performed, its
    session slot and every other slot empty."""
    base = dict(kind=None if kind is None else sup(kind), status=doubted(PERFORMED))
    base.update(over)
    return event(**base)


def coverage_coding(R: FactSet) -> dict:
    """Step 4b's own lists: engine/coverage's event_coding@2 over ``R``, converted as engine/assess converts it
    (assess.session_acts) - read only, the reference D256 P1's admission is pinned to."""
    from studio.interpretation.engine import coverage as COV

    return AS.session_acts(COV.event_coding(R, COV.sessions(R), {}))


class NoCardEntries(SimpleTestCase):
    """DECISIONS D256 P1 (refute-r4d-r2 P1, critical; r4d Q-CARD option (c), Q-UNNAMED's one-session half): a kept
    unlisted act or doubt with no card (or a card the FactSet does not hold) that names a kind holds the base code of
    every session where step 4b would list its filed doubted form - the act filed in doubt with its session slot silent
    - among the session's doubted acts (coverage.doubted_in), worded as the carded form is; one that names no kind holds
    the base code when the document tells one session, and stays out in a document of more than one (the named residual
    Q-UNNAMED)."""

    def one_session(self, family, entries=(), extra=None) -> FactSet:
        events = {E1: act(Kind.EXAMINATION, X1)}
        events.update(extra or {})
        return build(events, {X1: session_of(family)}, unlisted=entries)

    def test_d256_p1_one_session_an_entry_with_no_card_holds_the_base_code_as_its_carded_form_does(self):
        """refute-r4d-r2 P1 (q_card_one_session): ONE colonoscopy (45378 alone) or ONE upper endoscopy (43235 alone) and
        one kept unlisted act or doubt whose card pass 2 left empty - a biopsy or a snare; a biopsy, a PEG or a
        dilation. Each holds the base code base_included as a QUESTION quoting its unit and naming its kind, exactly as
        the same entry carded to the session does (round 2 of build-v2/w7r: READY), as a card the FactSet does not hold
        does, and as the act filed in doubt with its session slot silent does through step 4b's doubted list."""
        reference = [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)]
        for family, code, kinds in ((SessionKind.COLONOSCOPY, '45378', (Kind.BIOPSY, Kind.SNARE)),
                                    (SessionKind.EGD, '43235', (Kind.BIOPSY, Kind.PEG, Kind.DILATION))):
            members = [member('sel:0', code, X1, (E1,))]
            for kind in kinds:
                for what in (ACT_, DOUBT_):
                    with self.subTest(code=code, kind=kind.value, what=what.value):
                        records = {}
                        for card in (None, X1, X9):
                            R = self.one_session(family, (entry_of(kind, card, what),))
                            combined = C.combine(members, coding_of(R), R)
                            base = combined.bases['sel:0']
                            records[card] = (held_of(combined, 'sel:0'), base.unlisted, base.unlisted_kinds,
                                             base.named_codes, C.base_hold(base, R).spans)
                        self.assertEqual(records[None], (reference, (0,), (kind,), (), (Span(900, 940),)))
                        self.assertEqual((records[X1], records[X9]), (records[None], records[None]))
                        filed = self.one_session(family, extra={E3: filed_form(kind)})
                        coded = coverage_coding(filed)
                        self.assertEqual(coded[X1].doubted, (E3,))
                        self.assertEqual(held_of(C.combine(members, coded, filed), 'sel:0'), reference)

    def test_d256_p1_through_assess_and_worded_as_the_carded_form(self):
        """The refuter's probe through engine/assess (test_assess's synthetic colonoscopy and upper endoscopy): with no
        card, 45378 beside an unlisted snare and 43235 beside an unlisted PEG are held, their one item BASE_INCLUDED
        naming the act's kind - the same item, slots and sentence as the entry carded to the session."""
        for build_doc, code, kind in ((lambda: EF.colonoscopy(snare=False), '45378', Kind.SNARE),
                                      (EF.egd, '43235', Kind.PEG)):
            results = {}
            for card in (None, X1):
                doc = build_doc()
                doc.unlisted.append(UnlistedStatement(units=(Span(3000, 3040),), what=ACT_, kind=kind, session=card))
                R = doc.build()
                assessment = TA.run(R, (code, 1))
                found = assessment.codes[0]
                results[card] = (found.status,) + worded(found, assessment, R)
            with self.subTest(code=code):
                self.assertEqual(results[None], results[X1])
                self.assertEqual(results[None][:4], (Outcome.NEEDS_CLARIFICATION, Q.MessageId.BASE_INCLUDED, (),
                                                     (kind,)))

    def test_d256_p1_the_admission_is_step_4bs_doubted_list_over_every_kind_and_session_shape(self):
        """D256 P1's admission (``_listed_doubted``) equals step 4b's own: for every kind and every session shape - each
        session kind supported or negated, unresolved, a doubt between two kinds, contradicted, an empty slot - whether
        coverage's event_coding lists the act filed in doubt with its session slot silent among the session's doubted
        acts. coverage imports combination, so combination reads the same derivation; this pins the two readers equal
        (D227's discipline; the step's NOTES, request to the integration for one home). A session the FactSet does not
        hold is none the act may be in."""
        shapes = ([sup(kind) for kind in SessionKind] + [neg(kind) for kind in SessionKind]
                  + [None, unres(SessionKind.EGD), doubted(SessionKind.EGD, SessionKind.EUS),
                     doubted(SessionKind.COLONOSCOPY, SessionKind.FLEX_SIG),
                     contradicted(SessionKind.EUS, SessionKind.ERCP)])
        mismatches, seen = [], set()
        for shape in shapes:
            for kind in Kind:
                R = build({E3: filed_form(kind)}, {X1: {} if shape is None else session_of(shape)})
                listed = E3 in coverage_coding(R)[X1].doubted
                seen.add(listed)
                if C._listed_doubted(R, kind, X1) != listed:
                    mismatches.append((None if shape is None else (shape.result.value, shape.value), kind.value,
                                       listed))
        self.assertEqual(mismatches, [])
        self.assertEqual(seen, {True, False})
        self.assertEqual(len(shapes) * len(Kind), 37 * 42)
        self.assertFalse(C._listed_doubted(build({E3: filed_form(Kind.BIOPSY)}, COLONOSCOPY), Kind.BIOPSY, X9))

    def test_d256_p1_an_entry_with_no_card_holds_exactly_where_its_filed_doubted_form_does(self):
        """D231's pair for D256 P1, over every kind: in a document with an office visit X0 (99213), a colonoscopy X1
        (45378), an upper endoscopy X2 (43235) and an upper EUS X3 (43259), an unlisted act with no card holds a base
        code exactly when the same act filed in doubt with its session slot silent stands in step 4b's doubted list of
        that code's session. Among them: an office visit holds none (never an act beside its own service), nor an
        umbrella of interventions; a biopsy holds the colonoscopy's and the upper endoscopy's codes."""
        sessions = {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS)), X1: session_of(SessionKind.COLONOSCOPY),
                    X2: session_of(SessionKind.EGD), X3: session_of(SessionKind.EUS, tract=UPPER)}
        events = {E0: act(Kind.EM_VISIT, X0), E1: act(Kind.EXAMINATION, X1), E5: act(Kind.EXAMINATION, X2),
                  E6: act(Kind.EXAMINATION, X3)}
        members = [member('sel:0', '99213', X0, (E0,)), member('sel:1', '45378', X1, (E1,)),
                   member('sel:2', '43235', X2, (E5,)), member('sel:3', '43259', X3, (E6,))]
        holding = {}
        for kind in Kind:
            with self.subTest(kind=kind.value):
                unlisted = build(events, sessions, unlisted=(entry_of(kind, None),))
                by_entry = {b.code for b in C.base_included(members, coding_of(unlisted), unlisted) if 0 in b.unlisted}
                filed = build({**events, E7: filed_form(kind)}, sessions)
                by_filed = {b.code for b in C.base_included(members, coverage_coding(filed), filed) if E7 in b.doubted}
                self.assertEqual(by_entry, by_filed)
                holding[kind] = by_entry
        self.assertEqual((holding[Kind.EM_VISIT], holding[Kind.INTERVENTION]), (set(), set()))
        self.assertLessEqual({'45378', '43235'}, holding[Kind.BIOPSY])
        self.assertNotIn('99213', set().union(*holding.values()))

    def test_d256_q_unnamed_a_kindless_entry_with_no_card_holds_only_the_one_session_of_its_document(self):
        """D256, Q-UNNAMED's one-session half: a kept unlisted act or doubt that names no kind and has no card (or a
        card the FactSet does not hold) holds the base code of the document's ONE session - its session can be no other
        - as a QUESTION quoting its unit and naming no kind and no code (DECISIONS D254's label words it, "another act":
        steps 3c and 5c), as its carded form does. AS BUILT, THE NAMED RESIDUAL Q-UNNAMED (D256, measured at D2-D3): in
        a document of more than one session such an entry stays out of every base rule - a colonoscopy beside an upper
        endoscopy here, refute-r4d-r1 F1's office visit beside a colonoscopy in SyntheticAct - while its carded form
        holds its session's code."""
        reference = [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)]
        for family, code in ((SessionKind.COLONOSCOPY, '45378'), (SessionKind.EGD, '43235'),
                             (SessionKind.EUS, '43259')):
            for what in (ACT_, DOUBT_):
                for card in (None, X9, X1):
                    with self.subTest(code=code, what=what.value, card=card):
                        R = self.one_session(family, (entry_of(None, card, what),))
                        combined = C.combine([member('sel:0', code, X1, (E1,))], coding_of(R), R)
                        base = combined.bases['sel:0']
                        self.assertEqual((held_of(combined, 'sel:0'), base.unlisted, base.unlisted_kinds,
                                          base.named_codes, C.base_hold(base, R).spans),
                                         (reference, (0,), (), (), (Span(900, 940),)))
        sessions = {X1: session_of(SessionKind.COLONOSCOPY), X2: session_of(SessionKind.EGD)}
        events = {E1: act(Kind.EXAMINATION, X1), E5: act(Kind.EXAMINATION, X2)}
        members = [member('sel:0', '45378', X1, (E1,)), member('sel:1', '43235', X2, (E5,))]
        for what in (ACT_, DOUBT_):
            for card in (None, X9):
                with self.subTest(residual='Q-UNNAMED', what=what.value, card=card):
                    R = build(events, sessions, unlisted=(entry_of(None, card, what),))
                    self.assertEqual(C.base_included(members, coding_of(R), R), ())
            carded = build(events, sessions, unlisted=(entry_of(None, X1, what),))
            self.assertEqual([(b.code, b.unlisted) for b in C.base_included(members, coding_of(carded), carded)],
                             [('45378', (0,))])
        # through engine/assess (refute-r4d-r2 seam_render S2: a colonoscopy to the cecum, 45378 alone, an unlisted act
        # of no kind and no card): held, its one item BASE_INCLUDED with the slots of its carded form (r4d S2c) - which
        # DECISIONS D254's absence form and label word (steps 3c and 5c); round 2 of build-v2/w7r: READY
        assessed_items = {}
        for card in (None, X1):
            doc = EF.colonoscopy(snare=False)
            doc.unlisted.append(UnlistedStatement(units=(Span(3000, 3040),), what=ACT_, kind=None, session=card))
            R = doc.build()
            assessment = TA.run(R, ('45378', 1))
            found = assessment.codes[0]
            assessed_items[card] = (found.status, found.item.message, [held.fact for held in found.held_facts],
                                    overlay.item_slots(found.item, found.key, assessment.combination, R))
        self.assertEqual(assessed_items[None], assessed_items[X1])
        self.assertEqual(assessed_items[None][:3], (Outcome.NEEDS_CLARIFICATION, Q.MessageId.BASE_INCLUDED,
                                                    ['base_included']))
        office = build({E0: act(Kind.EM_VISIT, X0)}, {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS))},
                       unlisted=(entry_of(None, None),))
        carded_office = build({E0: act(Kind.EM_VISIT, X0)},
                              {X0: session_of(SessionKind.OFFICE_EM, encounter=sup(THIS))},
                              unlisted=(entry_of(None, X0),))
        self.assertEqual([(b.code, b.unlisted) for b in C.base_included([member('sel:0', '99213', X0, (E0,))],
                                                                       coding_of(office), office)],
                         [('99213', (0,))])
        self.assertEqual(C.base_included([member('sel:0', '99213', X0, (E0,))], coding_of(office), office),
                         C.base_included([member('sel:0', '99213', X0, (E0,))], coding_of(carded_office),
                                         carded_office))

    def test_d269_the_one_session_count_leaves_out_a_session_established_not_done_today(self):
        """DECISIONS D269 (refute-r4d-r1 V8R4D1-3, option (a)): D256's "a document that tells one session" counts the
        sessions that are not established not done today. A colonoscopy X1 today (45378 counted) beside a second
        colonoscopy X2 filed as a session of its own whose examination is planned at a later date (the planned repeat:
        the corpus's CK-future filing), done at an earlier date, or denied - and one kept unlisted act or doubt of no
        kind with no card (or a card the FactSet does not hold): 45378 held base_included, a QUESTION naming no kind and
        no code, exactly as without X2 (round w8r: no hold - the document had two sessions). A second session that may
        be done today - its examination done today, its date or status open, no examination at all - still makes two:
        the entry stays out (the named residual Q-UNNAMED, as built). The step's question Q-COUNT: a document whose only
        session is itself established not done today counts none, and keeps the hold (the fail-closed reading of the
        count of none; with two such sessions the entry stays out)."""
        reference = [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)]
        members = [member('sel:0', '45378', X1, (E1,))]
        sessions = {X1: session_of(SessionKind.COLONOSCOPY, encounter=sup(THIS)),
                    X2: session_of(SessionKind.COLONOSCOPY, encounter=sup(SEPARATE))}

        def with_x2(exam, entry):
            events = {E1: act(Kind.EXAMINATION, X1)}
            if exam is not None:
                events[E5] = exam
            return build(events, sessions, unlisted=(entry,))

        settled = (('planned, a later date', act(Kind.EXAMINATION, X2, status=sup(PLANNED), date=sup(LATER))),
                   ('planned, no date', act(Kind.EXAMINATION, X2, status=sup(PLANNED), date=None)),
                   ('done, an earlier date', act(Kind.EXAMINATION, X2, date=sup(EARLIER))),
                   ('denied', act(Kind.EXAMINATION, X2, status=neg(PERFORMED))))
        live = (('done today', act(Kind.EXAMINATION, X2)),
                ('its date open', act(Kind.EXAMINATION, X2, date=unres(EARLIER))),
                ('its status open', act(Kind.EXAMINATION, X2, status=unres(PLANNED))),
                ('no examination', None))
        alone = self.one_session(SessionKind.COLONOSCOPY, (entry_of(None, None),))
        self.assertEqual(held_of(C.combine(members, coding_of(alone), alone), 'sel:0'), reference)
        for what in (ACT_, DOUBT_):
            for card in (None, X9):
                for name, exam in settled:
                    with self.subTest(x2=name, what=what.value, card=card):
                        R = with_x2(exam, entry_of(None, card, what))
                        self.assertEqual((C.not_done_today(R, X1), C.not_done_today(R, X2)), (False, True))
                        combined = C.combine(members, coding_of(R), R)
                        base = combined.bases['sel:0']
                        self.assertEqual((held_of(combined, 'sel:0'), base.unlisted, base.unlisted_kinds,
                                          base.named_codes), (reference, (0,), (), ()))
                for name, exam in live:
                    with self.subTest(residual='Q-UNNAMED', x2=name, what=what.value, card=card):
                        R = with_x2(exam, entry_of(None, card, what))
                        self.assertFalse(C.not_done_today(R, X2))
                        self.assertEqual(C.base_included(members, coding_of(R), R), ())
        planned_only = build({E5: act(Kind.EXAMINATION, X2, status=sup(PLANNED), date=sup(LATER))},
                             {X2: sessions[X2]}, unlisted=(entry_of(None, None),))
        self.assertTrue(C.not_done_today(planned_only, X2))
        self.assertEqual([(b.code, b.unlisted) for b in C.base_included([member('sel:0', '45378', X2, (E5,))],
                                                                       coding_of(planned_only), planned_only)],
                         [('45378', (0,))])  # Q-COUNT: no session counted, the only one keeps the hold
        two_settled = build({E1: act(Kind.EXAMINATION, X1, status=sup(PLANNED)),
                             E5: act(Kind.EXAMINATION, X2, status=sup(PLANNED))}, sessions,
                            unlisted=(entry_of(None, None),))
        self.assertEqual((C.not_done_today(two_settled, X1), C.not_done_today(two_settled, X2)), (True, True))
        self.assertEqual(C.base_included(members, coding_of(two_settled), two_settled), ())

    def test_d269_the_refuters_planned_repeat_through_assess_holds_as_without_it(self):
        """V8R4D1-3's input through engine/assess (scratch/v8_planned_repeat.py): ONE colonoscopy today to the cecum
        (45378 alone) and the planned repeat colonoscopy filed as a session of its own (X2: a separate encounter, its
        examination E5 planned at a later date), beside one kept unlisted act of no kind with no card - 45378 held, its
        one item BASE_INCLUDED, the item and its slots the same as without X2 (round w8r: READY). Carded to X1, and a
        biopsy with no card, hold it with X2 as without it."""
        def doc(entry, planned):
            built = EF.colonoscopy(snare=False)
            if planned:
                built.session(2, SessionKind.COLONOSCOPY, encounter=EF.sup(SEPARATE))
                built.exam(5, session=EF.X(2), status=EF.sup(PLANNED), date=EF.sup(LATER))
            built.unlisted.append(entry)
            return built.build()

        for name, kind, card in (('act, no kind, no card', None, None), ('act, no kind, carded X1', None, X1),
                                 ('biopsy, no card', Kind.BIOPSY, None)):
            results = {}
            for planned in (False, True):
                R = doc(UnlistedStatement((Span(3000, 3040),), ACT_, kind, card), planned)
                assessment = TA.run(R, ('45378', 1))
                found = assessment.codes[0]
                results[planned] = (found.status, found.item.message if found.item else None,
                                    [(held.fact, held.cause) for held in found.held_facts],
                                    overlay.item_slots(found.item, found.key, assessment.combination, R)
                                    if found.item else None)
            with self.subTest(entry=name):
                self.assertEqual(results[True], results[False])
                self.assertEqual(results[True][:3], (Outcome.NEEDS_CLARIFICATION, Q.MessageId.BASE_INCLUDED,
                                                     [('base_included', C.BASE_CAUSE)]))


# --- a session whose examination is established not done today (DECISIONS D256 P2) ------------------------------------


LATER = ct.DateRelation.LATER_DATE
PLANNED_EUS = act(Kind.EXAMINATION, X2, status=sup(PLANNED), date=sup(LATER))
EARLIER_EUS = act(Kind.EXAMINATION, X2, date=sup(EARLIER))


def doubted_empty(*readings) -> Fact:
    """An EMPTY session slot a doubt names (3.3 row 2): unknown, no value, the readings as options (refute-r4b-r1
    V8R4B1-3's first form)."""
    return fact(Res.UNKNOWN, None, None, options=readings, reasons=(ct.Reason.DOUBT_UNCLEAR,))


# 9.4's weakenings of one established fact, as step 6a's property tests make them (tests/v2/test_properties.py's
# _weakened_fact): to unresolved, a doubt stated or unclear, and a conflict doubt - each keeping the claimed value.
NINE_FOUR = ('unresolved', 'doubt stated', 'doubt unclear', 'doubt conflict')


def nine_four(found: Fact, how: str) -> Fact:
    if how == 'unresolved':
        return Fact(result=Res.UNRESOLVED, value=found.value, state=found.state, options=(),
                    reasons=(ct.Reason.APPRAISAL_UNCLEAR,), spans=found.spans)
    if how in ('doubt stated', 'doubt unclear'):
        reason = ct.Reason.DOUBT_STATED if how == 'doubt stated' else ct.Reason.DOUBT_UNCLEAR
        return Fact(result=Res.UNKNOWN, value=found.value, state=found.state, options=(), reasons=(reason,),
                    spans=found.spans)
    return Fact(result=Res.CONTRADICTED, value=found.value, state=State.CONTRADICTED, options=(found.value,),
                reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=found.spans)


def single_weakenings(R: FactSet):
    """Every FactSet one 9.4 weakening of ``R`` makes, over the events' and the sessions' established facts: (label,
    the weakened FactSet)."""
    for table in ('events', 'sessions'):
        objects = getattr(R, table)
        for subject, by in objects.items():
            for attribute, values in by.items():
                for position, found in enumerate(values):
                    if not F.established(found):
                        continue
                    for how in NINE_FOUR:
                        changed = {key: dict(value) for key, value in objects.items()}
                        changed[subject][attribute] = (values[:position] + (nine_four(found, how),)
                                                       + values[position + 1:])
                        yield f'{how} {subject} {attribute.value}', replace(R, **{table: changed})


class EstablishedNotDone(SimpleTestCase):
    """DECISIONS D256 P2 as D269 rules it (Q-P2DATE option (c), 4.3 row 7; refute-r4d-r2 P2, high; refute-r4d-r1
    V8R4D1-6; refute-r4b-r1 V8R4B1-3; the integration's I4 residual): a session whose examination is established, and
    established not done on the date of service (planned, or done on another date), is possibly done by NO act - an
    entry with no card or carded, a filed act whatever its date or session slot - and is never a whole for BASE_WITHIN;
    an entry with no card that names a kind makes possibly done only sessions whose family holds that kind (K2). Step
    4b's _part_of_session reads session_possibly_done (D227's one derivation). "Established not done" reads every event
    the document places in the session that may be its examination: one that may be done today keeps the session from
    it (the step's question Q-NDT - read from the established examinations alone, a 9.4 weakening released a whole)."""

    def egd_and_eus(self, eus_exam=None, *, entries=(), extra=None, part_of=None) -> FactSet:
        """The refuter's planned_eus shape: an upper endoscopy X1 today (its examination E1 done; 43235 counted; its
        part_of_session ``part_of``) and an upper EUS X2 of a separate encounter whose examination is ``eus_exam``
        (none: an EUS with no filed event)."""
        events = {E1: act(Kind.EXAMINATION, X1)}
        if eus_exam is not None:
            events[E2] = eus_exam
        events.update(extra or {})
        return build(events, {X1: session_of(SessionKind.EGD, encounter=sup(THIS), part_of=part_of),
                              X2: session_of(SessionKind.EUS, tract=UPPER, encounter=sup(SEPARATE))}, unlisted=entries)

    MEMBERS = [member('sel:0', '43235', X1, (E1,), procedural=True, supported=True)]

    def outcome(self, R: FactSet) -> tuple:
        combined = C.combine(self.MEMBERS, coding_of(R), R)
        return C.session_possibly_done(R, X2), C.wholes(R, X1), held_of(combined, 'sel:0')

    def test_d256_p2_and_d269_no_entry_makes_a_planned_or_earlier_examination_todays(self):
        """refute-r4d-r2 P2 (planned_eus): the EUS's examination established PLANNED at a later date, or done at an
        EARLIER date, and one kept unlisted entry - an office visit act, a pH capsule placement act, an FNA (a kind the
        EUS holds), an act of no kind, a biopsy doubt, an examination - with no card, with a card the FactSet does not
        hold, or CARDED TO THE EUS: the EUS is not possibly done, there is no whole, and 43235 is never held base_within
        (round 2 of build-v2/w7r: held "the endoscopic portion of the endoscopic ultrasound" on every such entry; round
        w8r: still on a carded one - DECISIONS D269: every act possibly in the session, placed or supported, is exempt;
        a carded entry leaves the EUS established not done, the step's question Q-CARDEXAM). The biopsy doubt with no
        card holds 43235 base_included instead (D256 P1: the upper endoscopy lists a biopsy filed in doubt with no
        session), and so does the act of no kind with no card (D269: the document tells one session, the EGD; round w8r:
        nothing, two sessions)."""
        base = [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)]
        for label, exam in (('planned, a later date', PLANNED_EUS), ('done, an earlier date', EARLIER_EUS)):
            self.assertEqual((C.not_done_today(self.egd_and_eus(exam), X2), self.outcome(self.egd_and_eus(exam))),
                             (True, (False, (), [])))
            for name, entry, held in (
                    ('an office visit act', entry_of(Kind.EM_VISIT, None), []),
                    ('a pH capsule placement act', entry_of(Kind.PH_MONITORING, None), []),
                    ('an FNA', entry_of(Kind.FNA, None), []),
                    ('an act of no kind', entry_of(None, None), base),
                    ('a card the FactSet does not hold', entry_of(Kind.FNA, X9), []),
                    ('a biopsy doubt', entry_of(Kind.BIOPSY, None, DOUBT_), base),
                    ('an office visit act carded X2', entry_of(Kind.EM_VISIT, X2), []),
                    ('an FNA doubt carded X2', entry_of(Kind.FNA, X2, DOUBT_), []),
                    ('an act of no kind carded X2', entry_of(None, X2), []),
                    ('an examination carded X2', entry_of(Kind.EXAMINATION, X2), [])):
                with self.subTest(eus=label, entry=name):
                    R = self.egd_and_eus(exam, entries=(entry,))
                    self.assertTrue(C.not_done_today(R, X2))
                    self.assertEqual(self.outcome(R), (False, (), held))

    def test_d256_p2_and_d269_no_filed_act_makes_it_possible_whatever_its_date_or_slot(self):
        """D256 P2's filed half widened by D269 (Q-P2DATE option (c): "whatever the act's date or session slot"): an act
        that may not be the EUS's examination - an office visit act, an FNA - with its session slot silent, claimed
        (unresolved) or supported in the EUS, and its date silent, unresolved, a doubt or supported TODAY, never makes
        the planned or earlier EUS possibly done: no whole, 43235 not held (round w8r: an act filed in the EUS, or dated
        today with no session, still made it possible). The same unplaced act makes an EUS whose examination is not
        established not done possibly done, as before: one done today (C-4: an established whole), one whose status or
        date is open, one with no examination at all."""
        for exam in (PLANNED_EUS, EARLIER_EUS):
            for kind in (Kind.EM_VISIT, Kind.FNA):
                for slot in (None, unres(X2), sup(X2)):
                    for date in (None, unres(ON), doubted(ON, EARLIER), sup(ON)):
                        with self.subTest(exam=exam[A.STATUS][0].value.value, kind=kind.value,
                                          slot=None if slot is None else slot.result.value,
                                          date=None if date is None else date.result.value):
                            R = self.egd_and_eus(exam, extra={E3: act(kind, slot, date=date)})
                            self.assertTrue(C.not_done_today(R, X2))
                            self.assertEqual(self.outcome(R), (False, (), []))
        unplaced = {E3: act(Kind.EM_VISIT, None, date=None)}
        for name, exam, whole in (('done today', act(Kind.EXAMINATION, X2), C.Whole(X2, True)),
                                  ('its status open', act(Kind.EXAMINATION, X2, status=unres(PLANNED)),
                                   C.Whole(X2, False)),
                                  ('its date open', act(Kind.EXAMINATION, X2, date=unres(EARLIER)), C.Whole(X2, False)),
                                  ('no examination', None, C.Whole(X2, False))):
            with self.subTest(control=name):
                R = self.egd_and_eus(exam, extra=unplaced)
                self.assertFalse(C.not_done_today(R, X2))
                self.assertTrue(C.session_possibly_done(R, X2))
                self.assertEqual(C.wholes(R, X1), (whole,))

    def test_d256_p2_a_kind_naming_entry_with_no_card_reads_k2(self):
        """D256 P2 (K2; r4d Q-F7 option (b)): beside an upper EUS X2 with no filed event (an act-only session, nothing
        established about it), an entry with no card that names a kind the EUS family holds (requirements_table
        .FAMILY_KINDS: an FNA, an act of kind other) makes it possibly done - 43235 held base_within as a QUESTION (D231
        row 2) - and so does one of no kind; an office visit, a pH capsule placement or a band ligation, which the EUS
        family holds not, never does (round 2: each did) - the band ligation holds 43235 base_included instead (D256 P1:
        the upper endoscopy lists a band ligation filed in doubt with no session). Carded to the EUS, each does: the
        card names it (the EUS is no session established not done today, so D269 exempts nothing)."""
        within = [('base_included', ItemKind.QUESTION, C.WITHIN_CAUSE)]
        for name, kind in (('an FNA', Kind.FNA), ('kind other', Kind.OTHER), ('no kind', None)):
            with self.subTest(holds=name):
                self.assertEqual(self.outcome(self.egd_and_eus(entries=(entry_of(kind, None),))),
                                 (True, (C.Whole(X2, False),), within))
        for kind, held in ((Kind.EM_VISIT, []), (Kind.PH_MONITORING, []),
                           (Kind.BAND_LIGATION, [('base_included', ItemKind.QUESTION, C.BASE_CAUSE)])):
            with self.subTest(holds_not=kind.value):
                self.assertNotIn(kind, F.family_kinds(SessionKind.EUS))
                self.assertEqual(self.outcome(self.egd_and_eus(entries=(entry_of(kind, None),))), (False, (), held))
                self.assertEqual(self.outcome(self.egd_and_eus(entries=(entry_of(kind, X2),))),
                                 (True, (C.Whole(X2, False),), within))

    def test_d269_q_p2date_option_c_the_planned_eus_beside_an_act_dated_today_or_undated(self):
        """DECISIONS D269, Q-P2DATE option (c) (refute-r4d-r1 V8R4D1-6; r4b Q3; w8r O3): an EGD X1 (43235), an upper EUS
        X2 whose examination is planned at a later date, and an office visit act E3 with no session - dated TODAY, or
        undated (its date unresolved, silent): 43235 not held, one answer (round w8r, AS BUILT: held base_within, "the
        endoscopic portion of the endoscopic ultrasound", when dated, and released when its date was weakened - a 9.4
        release the letter created; option (c) removes it, so O3 needs no naming). Through engine/assess too: 43235
        READY in each. refute-r4b-r1 V8R4B1-3's two forms of an FNA or office visit act E3, performed, its date silent -
        its slot empty with a doubt naming X2 (or X1 and X2), and its slot claimed X1 with a doubt reading X2 (or
        claimed X2 with a reading X1) - give one answer: X2 not possibly done, no whole, no base_within."""
        for date in (sup(ON), unres(ON), None):
            with self.subTest(date=None if date is None else date.result.value):
                R = self.egd_and_eus(PLANNED_EUS, extra={E3: act(Kind.EM_VISIT, None, date=date)})
                self.assertEqual(self.outcome(R), (False, (), []))
                doc = EF.egd()
                doc.session(2, SessionKind.EUS, tract=EF.sup(ct.Tract.UPPER), encounter=EF.sup(SEPARATE))
                doc.exam(2, session=EF.X(2), status=EF.sup(PLANNED), date=EF.sup(LATER))
                doc.act(3, Kind.EM_VISIT, session=F.SILENT, date=date if date is not None else F.SILENT)
                found = TA.run(doc.build(), ('43235', 1)).codes[0]
                self.assertEqual((found.status, found.held_facts), (Outcome.READY, ()))
        for kind in (Kind.FNA, Kind.EM_VISIT):
            answers = {}
            for name, slot in (('empty, a doubt naming X2', doubted_empty(X2)),
                               ('empty, a doubt naming X1 and X2', doubted_empty(X1, X2)),
                               ('claimed X1, a doubt reading X2', doubted(X1, X2)),
                               ('claimed X2, a doubt reading X1', doubted(X2, X1))):
                R = self.egd_and_eus(PLANNED_EUS, extra={E3: act(kind, slot, date=None)})
                answers[name] = (C.session_possibly_done(R, X2), C.wholes(R, X1), C.base_within(self.MEMBERS, R))
            with self.subTest(v8r4b1_3=kind.value):
                self.assertEqual(set(answers.values()), {(False, (), ())}, answers)

    def test_d269_a_session_established_not_done_today_is_never_a_whole(self):
        """DECISIONS D269 (the integration's I4 residual; refute-r3c-r1 F2's companion): the upper endoscopy's own
        part_of_session claim naming the planned or earlier EUS - supported (C3), or not established (D70: unresolved, a
        doubt) - makes no whole of it, so a planned EUS is never named as the whole of today's EGD (round w8r: C3's
        established whole, which the renderer worded "may be ... possibly performed on the date of service" of an EUS
        the document establishes not done; D70's a possible one). The same claims name an EUS that is not established
        not done today: done today (C3 established, an EXPLANATION), its date open (C3 established; D70 possible)."""
        for label, exam in (('planned, a later date', PLANNED_EUS), ('done, an earlier date', EARLIER_EUS)):
            for name, part_of in (('C3', sup(X2)), ('D70 unresolved', unres(X2)), ('D70 a doubt', doubted(X1, X2))):
                with self.subTest(eus=label, claim=name):
                    R = self.egd_and_eus(exam, part_of=part_of)
                    self.assertEqual((C.wholes(R, X1), C.base_within(self.MEMBERS, R), self.outcome(R)),
                                     ((), (), (False, (), [])))
        for label, exam, established in (('done today', act(Kind.EXAMINATION, X2), True),
                                         ('its date open', act(Kind.EXAMINATION, X2, date=unres(EARLIER)), False)):
            for name, part_of, whole in (('C3', sup(X2), True), ('D70 unresolved', unres(X2), established)):
                with self.subTest(control=label, claim=name):
                    R = self.egd_and_eus(exam, part_of=part_of)
                    self.assertEqual(C.wholes(R, X1), (C.Whole(X2, whole),))
                    found = C.base_within(self.MEMBERS, R)
                    self.assertEqual([(b.wholes, b.within, b.established) for b in found], [((X2,), (), whole)])
                    self.assertEqual(C.base_within_hold(found[0], R).kind,
                                     ItemKind.EXPLANATION if whole else ItemKind.QUESTION)

    def test_d256_p2_an_examination_is_established_not_done_today_only_by_established_facts(self):
        """not_done_today: the session's established examinations (kind supported examination, session supported, no
        digital examination) are each established not done on the date of service - planned or denied, or of another
        date; one established done today, or open in status or date, leaves it possibly done today. A session with no
        established examination is not established not done. The step's question Q-NDT: beside its planned examination,
        an event the document places in the session (its session fact CLAIMS it) that may be its examination and may be
        done today - its session claimed but not established, its kind not established or silent, its status open -
        keeps it from being established not done; one established not done today (planned, an earlier date), an
        established digital examination, an event its session fact does not claim it for (a silent slot, an empty slot a
        doubt names, a doubt reading it beside another claim), an act that may not be an examination (an FNA), and a
        kept unlisted examination carded to it (D269's letter, the question Q-CARDEXAM) leave it established not
        done."""
        for name, exam, settled in (
                ('planned', act(Kind.EXAMINATION, X2, status=sup(PLANNED)), True),
                ('denied', act(Kind.EXAMINATION, X2, status=neg(PERFORMED)), True),
                ('an earlier date', EARLIER_EUS, True), ('a later date, planned', PLANNED_EUS, True),
                ('done today', act(Kind.EXAMINATION, X2), False),
                ('its status unresolved', act(Kind.EXAMINATION, X2, status=unres(PLANNED)), False),
                ('its date unresolved', act(Kind.EXAMINATION, X2, date=unres(EARLIER)), False),
                ('its kind unresolved', act(unres(Kind.EXAMINATION), X2, status=sup(PLANNED)), False),
                ('its session unresolved', act(Kind.EXAMINATION, unres(X2), status=sup(PLANNED)), False),
                ('a digital examination', act(Kind.EXAMINATION, X2, status=sup(PLANNED), device=sup(Device.MANUAL)),
                 False)):
            with self.subTest(name):
                self.assertEqual(C.not_done_today(self.egd_and_eus(exam), X2), settled)
        both = self.egd_and_eus(PLANNED_EUS, extra={E3: act(Kind.EXAMINATION, X2)})
        self.assertFalse(C.not_done_today(both, X2))
        kindless = act(Kind.EXAMINATION, unres(X2))
        del kindless[A.KIND]
        for name, extra, settled in (
                ('an examination claimed in it, done today', {E3: act(Kind.EXAMINATION, unres(X2))}, False),
                ('an examination claimed in it, a doubt reading another session', {E3: act(
                    Kind.EXAMINATION, doubted(X2, X1))}, False),
                ('an examination in it whose kind is unresolved, done today', {E3: act(unres(Kind.EXAMINATION), X2)},
                 False),
                ('an act claimed in it whose kind may be the examination', {E3: act(
                    doubted(Kind.SNARE, Kind.EXAMINATION), X2)}, False),
                ('an act of no kind claimed in it, done today', {E3: kindless}, False),
                ('an examination claimed in it, its status open', {E3: act(Kind.EXAMINATION, unres(X2),
                                                                           status=unres(PLANNED))}, False),
                ('an examination claimed in it whose device claims manual', {E3: act(
                    Kind.EXAMINATION, X2, device=unres(Device.MANUAL))}, False),
                ('an examination claimed in it, planned', {E3: act(Kind.EXAMINATION, unres(X2),
                                                                   status=sup(PLANNED))}, True),
                ('an examination claimed in it, an earlier date', {E3: act(Kind.EXAMINATION, unres(X2),
                                                                           date=sup(EARLIER))}, True),
                ('an examination of it, its device supported manual', {E3: act(
                    Kind.EXAMINATION, unres(X2), device=sup(Device.MANUAL))}, True),
                ('an examination with its session slot silent, done today', {E3: act(Kind.EXAMINATION, None)}, True),
                ('an examination with its slot empty, a doubt naming it', {E3: act(Kind.EXAMINATION,
                                                                                   doubted_empty(X2))}, True),
                ('an examination claimed in the EGD, a doubt reading it', {E3: act(Kind.EXAMINATION,
                                                                                   doubted(X1, X2))}, True),
                ('an examination negated in it', {E3: act(Kind.EXAMINATION, neg(X2))}, True),
                ('an FNA done in it today', {E3: act(Kind.FNA, X2)}, True)):
            with self.subTest(q_ndt=name):
                self.assertEqual(C.not_done_today(self.egd_and_eus(PLANNED_EUS, extra=extra), X2), settled)
        for kind in (Kind.EXAMINATION, None, Kind.FNA):
            with self.subTest(q_cardexam=None if kind is None else kind.value):
                R = self.egd_and_eus(PLANNED_EUS, entries=(entry_of(kind, X2), entry_of(kind, X2, DOUBT_, at=950)))
                self.assertTrue(C.not_done_today(R, X2))
                self.assertFalse(C.session_possibly_done(R, X2))

    def test_q_ndt_a_weakening_never_makes_a_session_established_not_done_today(self):
        """The step's question Q-NDT (DECISIONS D269's exemption read over D256 P2's first not_done_today, the
        established examinations alone): an EGD X1 today (43235) beside an upper EUS X2 whose examination E2 is planned
        at a later date and whose examination E3 is done today - X2 is done (by E3), C-4's established whole, 43235 held
        base_within as an EXPLANATION. Read from the established examinations alone, weakening E3's session or its kind
        to unresolved left E2 the only established examination: X2 "established not done", every act exempt, the whole
        and the hold released - a 9.4 release (the step's probe: 888 of 128,492 single weakenings over 1,500 generated
        FactSets). Here E3 still claims X2, may be its examination and may be done today: X2 stays possibly done, the
        whole and the hold stay (a QUESTION). And over every single 9.4 weakening - an established fact to unresolved, a
        doubt stated, unclear or conflict, each keeping its value: step 6a's - of the hand-built shape and of 150
        generated FactSets of it, no whole of X1 is lost, X2 never stops being possibly done, and 43235's base_within
        hold is never released."""
        R = self.egd_and_eus(PLANNED_EUS, extra={E3: act(Kind.EXAMINATION, X2)})
        self.assertEqual((C.not_done_today(R, X2), C.session_done(R, X2), C.wholes(R, X1)),
                         (False, True, (C.Whole(X2, True),)))
        self.assertEqual(self.outcome(R)[2], [('base_included', ItemKind.EXPLANATION, C.WITHIN_CAUSE)])
        for name, weakened in (('its session unresolved', act(Kind.EXAMINATION, unres(X2))),
                               ('its kind unresolved', act(unres(Kind.EXAMINATION), X2)),
                               ('its device a doubt reading manual', act(Kind.EXAMINATION, X2,
                                                                         device=doubted(ENDOSCOPE, MANUAL)))):
            with self.subTest(name):
                W = self.egd_and_eus(PLANNED_EUS, extra={E3: weakened})
                self.assertEqual((C.not_done_today(W, X2), C.session_possibly_done(W, X2),
                                  [whole.session for whole in C.wholes(W, X1)]), (False, True, [X2]))
                self.assertEqual(self.outcome(W)[2], [('base_included', ItemKind.QUESTION, C.WITHIN_CAUSE)])

        def answer(S):
            return ({whole.session for whole in C.wholes(S, X1)}, C.session_possibly_done(S, X2),
                    bool(C.base_within(self.MEMBERS, S)))

        rng = random.Random(20261115)
        scenes = [R]
        for _ in range(150):
            extra = {}
            for number in range(3, 3 + rng.randint(1, 3)):
                made = act(Kind.EXAMINATION, rng.choice([sup(X2), sup(X2), unres(X2), doubted(X1, X2), None]),
                           status=rng.choice([sup(PERFORMED), sup(PERFORMED), doubted(PERFORMED), sup(PLANNED)]),
                           date=rng.choice([sup(ON), sup(ON), unres(ON), sup(EARLIER), sup(LATER), None]),
                           device=rng.choice([None, None, sup(ENDOSCOPE), sup(MANUAL)]))
                kind = rng.choice([sup(Kind.EXAMINATION), sup(Kind.EXAMINATION), sup(Kind.FNA), None])
                if kind is None:
                    del made[A.KIND]
                else:
                    made[A.KIND] = (kind,)
                extra[Id(IdFamily.EVENT, number)] = made
            scenes.append(self.egd_and_eus(rng.choice([PLANNED_EUS, PLANNED_EUS, EARLIER_EUS, act(Kind.EXAMINATION,
                                                                                                   X2)]), extra=extra))
        seen = {'settled': 0, 'not settled': 0, 'weakenings': 0}
        for S in scenes:
            before = answer(S)
            seen['settled' if C.not_done_today(S, X2) else 'not settled'] += 1
            for label, W in single_weakenings(S):
                seen['weakenings'] += 1
                after = answer(W)
                self.assertLessEqual(before[0], after[0], label)
                self.assertLessEqual(before[1], after[1], label)
                self.assertLessEqual(before[2], after[2], label)
        self.assertGreater(min(seen['settled'], seen['not settled']), 20, seen)


# --- the digital examination in session_done (DECISIONS D253, QE13 option (a)) ----------------------------------------


MANUAL, ENDOSCOPE = Device.MANUAL, Device.ENDOSCOPE


class DigitalExamination(SimpleTestCase):
    """DECISIONS D253, QE13 option (a) (repair r4a's R2, open request O3): session_done reads FINAL 5.6 E13's digital
    examination as engine/evaluate does - an event that may be an examination whose device CLAIMS manual - so its
    act-only session is evaluate.act_only's and a weakened device never turns a digital rectal examination into the
    session's own examination (D227: step 4b's derivation must give this function's answer)."""

    def test_qe13_an_examination_whose_device_claims_manual_is_no_session_examination(self):
        """A colonoscopy X1 told only through an examination E2 whose device claims manual - supported, unresolved, a
        doubt reading manual - has no examination and is not done (round 2: unresolved or doubted, E2 was the session's
        own examination and made it done); with a done cold snare E3 it is done by the snare - an act-only session
        (D121) - even with E2 planned. A device that claims no manual - negated, another device, silent - leaves E2 the
        session's examination, which decides: done when it is done, not done when it is planned."""
        snare = act(Kind.SNARE, device=sup(Device.COLD_SNARE))
        for device in (sup(MANUAL), unres(MANUAL), doubted(ENDOSCOPE, MANUAL)):
            with self.subTest(claims=(device.result.value, device.value)):
                alone = build({E2: act(Kind.EXAMINATION, device=device)}, COLONOSCOPY)
                self.assertEqual((C._examinations(alone, X1), C.session_done(alone, X1)), ((), False))
                planned = build({E2: act(Kind.EXAMINATION, device=device, status=sup(PLANNED)), E3: snare},
                                COLONOSCOPY)
                self.assertEqual((C._examinations(planned, X1), C.session_done(planned, X1)), ((), True))
        for device in (neg(MANUAL), sup(ENDOSCOPE), None):
            with self.subTest(claims_none=None if device is None else (device.result.value, device.value)):
                alone = build({E2: act(Kind.EXAMINATION, device=device)}, COLONOSCOPY)
                self.assertEqual((C._examinations(alone, X1), C.session_done(alone, X1)), ((E2,), True))
                planned = build({E2: act(Kind.EXAMINATION, device=device, status=sup(PLANNED)), E3: snare},
                                COLONOSCOPY)
                self.assertEqual((C._examinations(planned, X1), C.session_done(planned, X1)), ((E2,), False))

    def test_qe13_a_digital_examination_left_open_never_keeps_an_act_only_session_open(self):
        """The act-only arm reads the same: an event that may be an examination - its kind unresolved, or a doubt
        reading the examination - whose device claims manual is no examination left open (round 2 read it as one when
        its device was not supported), and never the act that makes the session done; a snare done beside it makes the
        session done."""
        snare = act(Kind.SNARE, device=sup(Device.COLD_SNARE))
        for kind in (unres(Kind.EXAMINATION), doubted(Kind.SNARE, Kind.EXAMINATION)):
            for device in (sup(MANUAL), unres(MANUAL)):
                with self.subTest(kind=kind.result.value, device=device.result.value):
                    open_ = act(kind, device=device, date=unres(ON))
                    self.assertTrue(C.session_done(build({E2: open_, E3: snare}, COLONOSCOPY), X1))
                    done = act(kind, device=device)
                    self.assertFalse(C.session_done(build({E2: done}, COLONOSCOPY), X1))
        endoscope = act(unres(Kind.EXAMINATION), device=unres(ENDOSCOPE), date=unres(ON))
        self.assertFalse(C.session_done(build({E2: endoscope, E3: snare}, COLONOSCOPY), X1))

    def test_qe13_the_act_only_session_and_the_digital_examination_are_evaluates(self):
        """One rule, two readers (D227; D253: "the claimed-manual reading holds in evaluate and in combination alike"):
        over every device shape, examination status and kind shape, a session has no established examination here
        exactly where evaluate.act_only holds, and _digital equals evaluate._digital on every event whose kind may be
        the examination."""
        devices = (sup(MANUAL), unres(MANUAL), doubted(ENDOSCOPE, MANUAL), doubted(MANUAL, ENDOSCOPE), neg(MANUAL),
                   sup(ENDOSCOPE), sup(Device.OTHER), contradicted(MANUAL, ENDOSCOPE), unres(ENDOSCOPE), None)
        kinds = (sup(Kind.EXAMINATION), unres(Kind.EXAMINATION), doubted(Kind.SNARE, Kind.EXAMINATION),
                 contradicted(Kind.EXAMINATION, Kind.SNARE))
        count = 0
        for device in devices:
            for kind in kinds:
                for status in (sup(PERFORMED), sup(PLANNED)):
                    R = build({E2: act(kind, device=device, status=status), E3: act(Kind.SNARE)}, COLONOSCOPY)
                    with self.subTest(device=None if device is None else (device.result.value, device.value),
                                      kind=(kind.result.value, kind.value), status=status.value.value):
                        self.assertEqual(not C._examinations(R, X1), EV.act_only(R, X1))
                        self.assertEqual(C._digital(R, E2), EV._digital(R, E2))
                    count += 1
        self.assertEqual(count, 80)

    def test_d253_a_digital_examination_beside_an_examination_of_another_occasion_leaves_the_session_not_done(self):
        """refute-r4a-r2 A2's shape at the combination (D253 repairs evaluate's row 7; this reading is the reference
        it now agrees with): a digital rectal examination E1 (device manual, or claiming it), a cold snare E2 and
        "Colonoscopy in 2019 was normal." filed as an examination E3 of X1 at an earlier date - X1's one examination is
        E3, not done today, so X1 is not done; without the digital examination line, the same."""
        snare = act(Kind.SNARE, device=sup(Device.COLD_SNARE))
        history = act(Kind.EXAMINATION, date=sup(EARLIER))
        for device in (sup(MANUAL), unres(MANUAL), doubted(ENDOSCOPE, MANUAL)):
            with self.subTest(device=device.result.value):
                R = build({E1: act(Kind.EXAMINATION, device=device), E2: snare, E3: history}, COLONOSCOPY)
                self.assertEqual((C._examinations(R, X1), C.session_done(R, X1)), ((E3,), False))
        self.assertFalse(C.session_done(build({E2: snare, E3: history}, COLONOSCOPY), X1))

    def test_g3_02_the_digital_exception_reads_only_an_event_that_may_be_an_examination(self):
        """DECISIONS D271 (refute-r4d-r1 V8R4D1-4; TRIAGE G3-02; r4d's deviation 5 of build-v2/w8r): ``_digital``'s kind
        gate, pinned. A done act of a SUPPORTED kind that is no examination - a cold snare or a biopsy in a colonoscopy,
        a dilation in an upper endoscopy - whose device claims manual (supported, unresolved, a doubt reading manual),
        alone in its session: it is no digital examination (its kind cannot be the examination), so it is the act that
        makes its act-only session done - session_done True, as the module docstring reads E13. Without the gate the
        reading is evaluate._digital's (a device claiming manual, no kind read: True for each of these acts), and the
        session would not be done. The control: the same act whose kind MAY be the examination (unresolved, or a doubt
        reading it) is a digital examination and leaves the session not done."""
        for family, kind in ((SessionKind.COLONOSCOPY, Kind.SNARE), (SessionKind.COLONOSCOPY, Kind.BIOPSY),
                             (SessionKind.EGD, Kind.DILATION)):
            for device in (sup(MANUAL), unres(MANUAL), doubted(ENDOSCOPE, MANUAL)):
                with self.subTest(kind=kind.value, device=(device.result.value, device.value)):
                    R = build({E2: act(kind, device=device)}, {X1: session_of(family)})
                    self.assertEqual((C._digital(R, E2), EV._digital(R, E2)), (False, True))
                    self.assertEqual((C._examinations(R, X1), C.session_done(R, X1)), ((), True))
                    for may_be in (unres(Kind.EXAMINATION), doubted(kind, Kind.EXAMINATION)):
                        control = build({E2: act(may_be, device=device)}, {X1: session_of(family)})
                        self.assertEqual((C._digital(control, E2), C.session_done(control, X1)), (True, False))


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
