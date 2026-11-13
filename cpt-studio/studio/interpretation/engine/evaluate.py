"""The per-code rule of design v2 (docs/gemini-migration/FINAL-V2.md 4.3, 4.4, 4.6, 4.10, 4.11 and Appendix A; step 4a of
8.1; DECISIONS D182, D188, D189, D191, D194, D197): one proposed code against the settled, text-free FactSet - its
candidates, its supporting acts (E*), every unresolved or failed requirement of every positive candidate, the binding of
each held group, and its exclusion. Forked from v1's events.py and ercp.py with their readers deleted (5.5): the rules
read results, ids and integer spans only, through engine/facts.py's predicates and engine/pairing.py's relations.

**decide(code, kept, R)** is 4.4's outcome function (``decide``):
- route (d) (no link, or a link naming no act) is held, never READY (C-6): one item, performed_status at rank 4, an
  explanation (coding_rule:unprofiled, or not_linked for a code of another family); D80's recognised-only codes
  (99152, 99153) likewise (coding_rule:recognised_only). Neither reads a group.
- For each requirement group (catalogue.requirements): the CANDIDATES are the events possibly of a kind covering the
  group (facts.possibly, the candidate arm of 4.2: the claimed value, the readings, the control's sibling; an umbrella
  covers its members, a tattoo and an injection are one act; a clip or an injection read through catalogue.catalogue_kind
  by possibly - the bleeding control it may be when its purpose is possibly hemostasis, silent included: D157's doubt
  arm, kept by 4.13, step 1e's hand-off R5; itself unless its purpose is supported hemostasis, which makes it a bleeding
  control only) whose status is not denied performed. 4.4 reads no session family here: an act of the code's kind in
  another family's session is a candidate, failing row 6. A candidate SUPPORTS the code when every row of
  SUPPORT below is T (and, for 43264, its YIELD: 4.3's "no support from that act"). When some candidate supports, the
  group is met and E* gains every supporting one. Otherwise the POSITIVE candidates (possibly performed or attempted -
  a doubted status and one pass 2 did not establish included [R:HO-1] - and not established as of another date or
  performer) each record EVERY witness (held fact) of every non-T row [R:HO-8], and questions.choose binds the group
  (4.8). With no positive candidate, the exclusion (4.6) decides: EXCLUDED (reinstatable), or a statement_scope
  question, or not documented (7.6: performed_status, rank 4).
- Then the code-specific rows (4.4's ``code_requirements``) over EVERY supporting act, each non-T row's witnesses added
  to ``held_facts``: there is no early return before them (Q2), and an act that fails one stays in E* while it holds the
  code (the design's literal outcome function; v1's R4 filtered such an act out of E* instead - recorded as a
  question).
- Route (b) (46221) is never READY (Appendix A; D197): after its groups, one item, performed_status at rank 4, cause
  coding_rule:route_b. Its row 6 is its places in the code's regions; exclusion, base and competition read its acts.
- 3.2.6 rule 2 (``on_evidence``): a code whose kept evidence overlaps the unit of a kept unlisted entry (an act, a denial
  or a doubt) is held - performed_status at RANK 2 ("an unlisted unit on its evidence", h2), cause unlisted, quoting the
  unit - and none of its groups is excluded (a citation beside it is asked). No 8.1 row names its owner; built here
  fail-closed, a question for the integration owner (the refutation's D1; the step's NOTES).

**SUPPORT(E, C, g)** (4.3 rows 1-8, each T, U or F with its witnesses):
1. kind: supported and covering g; a positive umbrella (removal, intervention) never supports a method-specific code -
   every catalogue code is one - and asks act_method (rank 9, h5); a clip or an injection supports a bleeding-control
   group only with its purpose supported hemostasis, and its own (injection) group only when its purpose neither is
   supported hemostasis nor claims it unestablished. An unestablished kind or purpose asks performed_status at rank 4
   (step 1f's reading R9(c)).
2. status: supported performed; also attempted_not_completed for a code with the ATT tag (step 1f's hand-off R9(a): the
   tag, never catalogue.examination_code, which also answers the office E/M codes). Attempted on any other code is an
   explanation at rank 4 (C-9: coding_rule:attempted; the 52/53 consideration is assess's). A doubt pass 1 reported on
   status asks rank 2, any other status not established rank 4.
3. the effective date relation supported on_date_of_service (event_time, rank 6).
4. the effective performer supported documenting_team (event_performer, rank 7).
5. the entry supported documenting_clinician (event_entry, rank 5): another owner supported is an explanation.
6. route (a): the session supported, its kind supported the code's family (procedure, rank 8); route (b): every place of
   the act established, its supported places in the code's regions, at least one (act_target, rank 11).
7. the session is done: every event that may be its examination (``examinations``, by its own kind and session facts -
   step 1f's hand-off R9(d)) passes rows 2-5 (an examination begun counts as done, as v1's done does), except that
   beside the session's own done examination an event established as of another occasion (a plan, another date,
   another performer) adds nothing; a session with none is the act's own (T). Another act's own facts never touch it
   (K2).
8. no CONTRADICTION, DOUBT or UNRESOLVED relation from any paired statement (engine/pairing.py, 4.5) - each its rank-1,
   rank-2 or row's item - and no unlisted denial or doubt pairing with it (statement_scope, cause unlisted). A
   contradicted fact among rows 1-7 asks rank 1 (conflict:<kind>) on its own row, a doubt on status rank 2.
E/M (the EM templates): the visit's session encounter supported this_encounter (event_time, rank 6).

**An established failure with no explanation.** 4.8 makes an F an explanation; where neither 4.3 nor
requirements.RULES names one (rows 3, 4 and 6 - the date relation, the performer or the session's family established
otherwise -, route (b)'s place outside its regions, the examination of row 7 established not done, the E/M encounter
established separate, ROUTE's other routes, LIMITED's full reach for 43231 and 43232, XCHG's possible exchange), the
witness is the requirement's question (kind question, cause coding_rule:<rule>): held either way, and every held fact has
a sentence (the step's NOTES, question Q4).

**The code-specific rows** (4.3's second table; Appendix A's tags), each over every supporting act (or its session):
TECH (technique.device in the code's class: another class an explanation, an unestablished or classless device a
question); SITE (D29: every place of the act and its supported lesion established, its supported
places within the class, at least one; every supported place outside the class, none surgically made or unplaced, is
the "another site" explanation); STRUCT:pfc (43240: structure supported pancreatic_fluid_collection, no supported
place biliary or hepatic: D120, D136, D145); ROUTE (43253: route supported eus_transmural; submucosal is the wall
injection's explanation); TRACT (the session's tract, D171(2)); STATIONS (43242, 43259: the three upper stations
supported examined and a reach at or beyond the duodenum, or an empty list with the completeness claim supported and
that reach [R:SC-B]; a station negated is the class explanation); LIMITED (43231, 43232: reached short of the
duodenum; 43237, 43238 - the codes whose profile includes the EGD, step 1f's hand-off #7 - a station negated or
reached short; all three examined is the class explanation); LOWER (D43: the class reach, the stoma codes also an
anatomy entry of type stoma supported and the approach through_stoma, an approach established otherwise the class
explanation); YIELD (43264: yield supported stones, stone
fragments, sludge or debris; negated is "documented as retrieving nothing"; contradicted conflict:stone_extraction; a
filter of SUPPORT, 4.3's "no support from that act");
CAUSE (purpose supported hemostasis and cause supported pre_existing_lesion, spontaneous or earlier_procedure; cause
act_of_this_session or purpose prophylaxis is bundled, rank 18); XCHG (43274, 43275: no possibly-performed counterpart
in the same or an unknown duct; 43276: a stent exchange supporting, or a stent removal and a stent placement each
supporting in one duct, both ducts supported and equal). R6 and COLFULL, ENT, C3+SEP, ADDON, bundling, combination, R7
and R9 are the steps 4b, 4c, 4d and 5a rows that assess appends (4.4).

**Exclusion** (4.6): with no supporting act and no positive candidate, a statement D excludes the code only when (1) D's
kind is supported and covers the group, its session supported of the code's family (route (b): its places in the
code's regions); (2) its deciding fact is established - status negated performed, or supported planned; the date relation
supported earlier_date or later_date; the performer supported other_clinician or other_facility - an attempted status
never decides (C-9); (3) a current denial's breadth is supported and not exceptive (a statement of another date or
performer, or a plan, carries none: K1); (4) the code covers D by citation (C-10, ``cover``); (5) nothing doubts the
code's kinds (no event possibly of them - its kind read with its session's family, 4.2 - possibly done today by the
documenting team; no DOUBT relation; no unlisted denial, doubt or act of them: 3.2.6 rule 3's synthetic doubted act;
and no unlisted unit on the code's kept evidence, rule 2). A partial cover, a citation beside a doubt, a
broad current denial (4.10) the code does not cite, and a denial of the code's kinds whose session or date relation is
not established (its session possibly of the code's family) all ask statement_scope (rank 3, C-7) - a broad denial is
never dropped; otherwise not documented.

**C-10, kept as geometry over offsets** (``cover``; v1's coverage_of and within_words, ported over DECISIONS D188's
text-free view): CITATION when a kept span overlaps D's anchor units and every kept span lies within the union of D's
kind words and status words (its Anchor) and the ``at`` spans of the ``statement`` sources of D's target lesion, target
places and date relation (Fact.cited). PARTIAL when a kept span overlaps and one reaches past that union; NONE
otherwise. v1 read each letter or digit of a kept span; the engine holds no text, so the caller may pass ``kept_words``,
the letter-or-digit runs of the kept spans computed at R1 by an allowlisted character-class function, and without them
every offset of every kept span must lie inside the union (fail-closed: a gap of a space or a stop makes the cover
partial, a statement_scope question, never an exclusion). A source citing its whole units (no located words) adds
nothing (fail-closed).

**The item** (``item``): the one clarification of a held code (questions.item over the evaluation's held facts and any
the caller appends - R6, the class and code checks, the combination - with the groups' positive candidates recomputed).

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, pairing, questions, requirements, requirements_table and types
only - no retired v1 module (5.0), none of contract's text modules, not wording - holds no word, phrase or marker list
(every module-level collection holds enumeration members), reads no text and returns no document string. ``mypy
--strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import (AnatomyType, Approach, Attribute, Breadth, Cause, DateRelation,
                                                  Device, EncounterRelation, Extent, Kind, Landmark, Link, Material,
                                                  Owner, Performer, Purpose, Reason, Result, Route, SessionKind, Status,
                                                  Structure)
from studio.interpretation.engine import anatomy, catalogue, pairing, questions
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag, Template
from studio.interpretation.engine.types import (Cover, Evaluation, Exclusion, Fact, FactSet, HeldFact, Id, IdFamily,
                                                ItemKind, Span, UnlistedStatement)

_A = Attribute
_Q, _E = ItemKind.QUESTION, ItemKind.EXPLANATION
_Rule = questions.Rule


@unique
class Truth(Enum):
    """The truth of a requirement (FINAL-V2 4.2, B's Kleene view): T when its facts hold the needed values, F when a fact
    is established against them, U otherwise (9.1's trace writes it)."""
    T = 'T'
    U = 'U'
    F = 'F'


# --- the items RANK gives each row (4.3, 4.8; engine/requirements.RULES) ------------------------------------------------

_STATUS = rq.Item(rq.Rank.STATUS, rq.FactKey.PERFORMED_STATUS)
_DOUBT = rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS)
_ENTRY = rq.Item(rq.Rank.ENTRY, rq.FactKey.EVENT_ENTRY)
_TIME = rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME)
_PERFORMER = rq.Item(rq.Rank.PERFORMER, rq.FactKey.EVENT_PERFORMER)
_PROCEDURE = rq.Item(rq.Rank.PROCEDURE, rq.FactKey.PROCEDURE)
_METHOD = rq.Item(rq.Rank.METHOD, rq.FactKey.ACT_METHOD)
_TECHNIQUE = rq.Item(rq.Rank.TECHNIQUE, rq.FactKey.TECHNIQUE)
_ACT_TARGET = rq.Item(rq.Rank.ACT_TARGET, rq.FactKey.ACT_TARGET)
_TARGET = rq.Item(rq.Rank.TARGET, rq.FactKey.TARGET)
_STATIONS = rq.Item(rq.Rank.EXAM_STATIONS, rq.FactKey.EXAM_STATIONS)
_EXTENT = rq.Item(rq.Rank.EXTENT, rq.FactKey.EXTENT)
_YIELD = rq.Item(rq.Rank.YIELD, rq.FactKey.ACT_YIELD)
_CAUSE = rq.Item(rq.Rank.BUNDLING, rq.FactKey.ACT_CAUSE)
_BUNDLED = rq.Item(rq.Rank.BUNDLED, rq.FactKey.PERFORMED_STATUS)
_SCOPE = rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE)

# The kinds the rules name (catalogue's tables, as enumeration members).
_POSITIVE: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})
_OTHER_DATES: frozenset[DateRelation] = frozenset({DateRelation.EARLIER_DATE, DateRelation.LATER_DATE})
_OTHER_PERFORMERS: frozenset[Performer] = frozenset({Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY})
_DOUBTS: frozenset[Reason] = frozenset({Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR})
_RETRIEVED: frozenset[Material] = frozenset({Material.STONES, Material.STONE_FRAGMENTS, Material.SLUDGE, Material.DEBRIS})
_BLEEDING_CAUSES: frozenset[Cause] = frozenset({Cause.PRE_EXISTING_LESION, Cause.SPONTANEOUS,
                                                Cause.EARLIER_PROCEDURE})
_UNPLACED: frozenset[Landmark] = anatomy.ALTERED | anatomy.UNPLACED
# XCHG (D105, D127): each stent act's counterparts, which make a possible exchange beside it.
_COUNTERPARTS: Mapping[Kind, frozenset[Kind]] = MappingProxyType({
    Kind.STENT: frozenset({Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE}),
    Kind.STENT_REMOVAL: frozenset({Kind.STENT, Kind.STENT_EXCHANGE})})
_EXCHANGE_PARTS: tuple[tuple[Kind, ...], tuple[Kind, ...]] = ((Kind.STENT_REMOVAL,), (Kind.STENT,))
# The row each pairing row's UNRESOLVED relation is about (its witness's attribute).
_ROW_ATTRIBUTE: Mapping[pairing.Row, Attribute] = MappingProxyType({
    pairing.Row.SESSION: _A.SESSION, pairing.Row.TIMING: _A.DATE_RELATION, pairing.Row.PERFORMER: _A.PERFORMER,
    pairing.Row.BREADTH: _A.SCOPE_BREADTH, pairing.Row.TARGET: _A.TARGET_PLACES,
    pairing.Row.TECHNIQUE: _A.TECHNIQUE_DEVICE})
# C-10's statement-linked target and timing facts whose ``at`` spans join the cover (4.6 condition 4; D188): those the
# statement's pairing reads (requirements.RULES' SUP.8), v1's COVERING less the kind and status (the Anchor's words).
_COVERING: tuple[Attribute, ...] = (_A.TARGET_LESION, _A.TARGET_PLACES, _A.DATE_RELATION)


# --- records ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    """One requirement of one candidate (4.3): which (a requirements.Requirement or a code-specific Tag), its Truth, and
    its witnesses (empty for T)."""
    requirement: rq.Requirement | Tag
    truth: Truth
    witnesses: tuple[HeldFact, ...] = ()


@dataclass(frozen=True, slots=True)
class Support:
    """SUPPORT(E, C, g) with the code's per-act rows: every row's truth and witnesses, in 4.3's order. ``partner``: for
    43276's pair (XCHG), the stent placement beside the removal ``event``."""
    event: Id
    rows: tuple[Row, ...]
    partner: Id | None = None

    @property
    def met(self) -> bool:
        """Every row T: the act supports the code."""
        return all(row.truth is Truth.T for row in self.rows)

    @property
    def witnesses(self) -> tuple[HeldFact, ...]:
        """Every witness of every non-T row, each once, in row order."""
        return tuple(dict.fromkeys(held for row in self.rows for held in row.witnesses))

    @property
    def unmet(self) -> int:
        """How many rows are not T (4.8 binding rule (3))."""
        return sum(1 for row in self.rows if row.truth is not Truth.T)


@dataclass(frozen=True, slots=True)
class _Code:
    """The proposal's code with its link and its requirement spec (engine/requirements.spec)."""
    code: str
    link: catalogue.CodeLink
    spec: rq.Spec

    @property
    def template(self) -> Template:
        return self.spec.template

    def has(self, tag: Tag) -> bool:
        return tag in self.spec.tags


def _code(code: str) -> _Code:
    return _Code(code, catalogue.code_link(code), rq.spec(code))


# --- reading facts ------------------------------------------------------------------------------------------------------


def _fact(R: FactSet, subject: Id | None, attribute: Attribute) -> Fact:
    return facts_.fact(R, subject, attribute)


def _members(R: FactSet, subject: Id | None, attribute: Attribute) -> tuple[Fact, ...]:
    return facts_.members(R, subject, attribute)


def _id(found: Fact) -> Id | None:
    """The supported id a fact names; None unless supported."""
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def _doubted(found: Fact) -> bool:
    """A doubt pass 1 reported (3.3 row 2: unknown with doubt_stated or doubt_unclear)."""
    return found.result is Result.UNKNOWN and any(reason in _DOUBTS for reason in found.reasons)


def _anchor(R: FactSet, event: Id | None) -> tuple[Span, ...]:
    return questions.anchor_units(R, event)


def _quoted(found: Fact | None, R: FactSet, event: Id | None) -> tuple[Span, ...]:
    """What a witness quotes: the fact's own spans, else the event's anchor."""
    if found is not None and found.spans:
        return tuple(sorted(set(found.spans)))
    return _anchor(R, event)


def _session(R: FactSet, event: Id) -> Id | None:
    return _id(_fact(R, event, _A.SESSION))


def other_date(R: FactSet, event: Id) -> bool:
    """4.4's established_other_date: the effective date relation supported earlier_date or later_date."""
    found = _fact(R, event, _A.DATE_RELATION)
    return found.result is Result.SUPPORTED and isinstance(found.value, DateRelation) and found.value in _OTHER_DATES


def other_performer(R: FactSet, event: Id) -> bool:
    """4.4's established_other_performer: the effective performer supported other_clinician or other_facility."""
    found = _fact(R, event, _A.PERFORMER)
    return (found.result is Result.SUPPORTED and isinstance(found.value, Performer)
            and found.value in _OTHER_PERFORMERS)


def positive(R: FactSet, event: Id) -> bool:
    """4.4's positive candidate - possibly today's act, in doubt: possibly performed or possibly attempted_not_completed
    (a status not established leaves every status possible: a doubted act is positive [R:HO-1]), and neither of another
    date nor of another performer established. The same-day rule (4.7, step 4d) reads it."""
    status = _fact(R, event, _A.STATUS)
    return (any(facts_.possibly(status, value) for value in _POSITIVE)
            and not other_date(R, event) and not other_performer(R, event))


def _covers_group(kind: Kind, group: Sequence[Kind]) -> bool:
    return any(catalogue.covers(kind, wanted) for wanted in group)


def _bleeding_group(group: Sequence[Kind]) -> bool:
    return _covers_group(Kind.BLEEDING_CONTROL, group)


def _claims_hemostasis(purpose: Fact) -> bool:
    """A purpose fact that claims hemostasis without establishing it: not established, hemostasis its claimed value or
    one of its options (a doubt's reading, a contradicted side, an unrejected control)."""
    return not facts_.established(purpose) and (purpose.value is Purpose.HEMOSTASIS
                                               or Purpose.HEMOSTASIS in purpose.options)


def candidate_kinds(R: FactSet, group: Sequence[Kind], event: Id) -> frozenset[Kind]:
    """The kinds through which ``event`` is a candidate of ``group`` (4.4): each kind it may be (facts.possibly, the
    candidate arm of 4.2) that covers a kind of the group - a clip or an injection read through catalogue.catalogue_kind
    by possibly (D157's doubt arm, step 1e's hand-off R5): the bleeding control it may be when its purpose is possibly
    hemostasis (silent included) and the group holds the bleeding control; itself, unless its purpose is supported
    hemostasis, which makes it a bleeding control only (v1's catalogue kind)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    purpose = _fact(R, event, _A.PURPOSE)
    found: set[Kind] = set()
    for kind in kinds:
        if kind in catalogue.HEMOSTASIS_KINDS:
            if _bleeding_group(group) and facts_.possibly(purpose, Purpose.HEMOSTASIS):
                found.add(Kind.BLEEDING_CONTROL)
            if not facts_.holds(purpose, Purpose.HEMOSTASIS) and _covers_group(kind, group):
                found.add(kind)
        elif _covers_group(kind, group):
            found.add(kind)
    return frozenset(found)


def is_candidate(R: FactSet, group: Sequence[Kind], event: Id) -> bool:
    """4.4's candidate: possibly of a kind of the group (candidate_kinds) and not denied performed."""
    return (not facts_.denied(_fact(R, event, _A.STATUS), Status.PERFORMED)
            and bool(candidate_kinds(R, group, event)))


def candidates(R: FactSet, group: Sequence[Kind]) -> tuple[Id, ...]:
    """Every candidate of ``group`` in pass 1's order."""
    return tuple(event for event in R.events if is_candidate(R, group, event))


# --- witnesses (4.4 HeldFact, D189) ------------------------------------------------------------------------------------


def _held(fact: str, rank: rq.Rank | None, kind: ItemKind, attribute: Attribute | None, subject: Id | None,
          found: Fact | None, cause: str, spans: tuple[Span, ...]) -> HeldFact:
    """A held fact: its result is the fact's (D189; None for a hold about no single fact), its reason the fact's first
    when the fact is not established."""
    result = found.result if found is not None else None
    reason = found.reasons[0] if found is not None and found.reasons and not facts_.established(found) else None
    return HeldFact(fact=fact, attribute=attribute, subject=subject, result=result, kind=kind, cause=cause,
                    reason=reason, spans=spans, rank=rank.value if rank is not None else None)


def _conflict_kind(R: FactSet, event: Id | None, group: Sequence[Kind]) -> Kind:
    found = questions.act_kind(R, event, group)
    return found if found is not None else Kind.OTHER


def _open(found: Fact, ask: rq.Item, attribute: Attribute, subject: Id, act: Id | None, group: Sequence[Kind],
          R: FactSet, cause: str | None = None) -> HeldFact:
    """The witness of a requirement whose fact is not what it needs (U): a contradicted fact asks rank 1
    (conflict:<the act's kind>); a doubt pass 1 reported on a status asks rank 2; any other the row's ``ask`` - its
    cause the fact's reading (questions.cause_of), or ``cause`` for an established fact a coding rule doubts."""
    spans = _quoted(found, R, act)
    if found.result is Result.CONTRADICTED:
        return _held(rq.fact_key(rq.FactKey.CONFLICT, _conflict_kind(R, act, group)), rq.Rank.CONFLICT, _Q, attribute,
                     subject, found, questions.cause_of(found), spans)
    if attribute is _A.STATUS and _doubted(found):
        return _held(rq.fact_key(_DOUBT.fact), _DOUBT.rank, _Q, attribute, subject, found, questions.cause_of(found),
                     spans)
    reading = cause if cause is not None and facts_.established(found) else questions.cause_of(found)
    return _held(rq.fact_key(ask.fact), ask.rank, _Q, attribute, subject, found, reading, spans)


def _fails(item: rq.Item, explained: bool, attribute: Attribute | None, subject: Id | None, found: Fact | None,
           rule: questions.Rule, R: FactSet, act: Id | None) -> HeldFact:
    """The witness of an established fact failing a coding rule (F): an EXPLANATION where the rule words one, else the
    row's question (the design gives the row no explanation: the requirement asked again, fail-closed)."""
    return _held(rq.fact_key(item.fact), item.rank, _E if explained else _Q, attribute, subject, found,
                 questions.coding_rule(rule), _quoted(found, R, act))


def _row(requirement: rq.Requirement | Tag, witnesses: Sequence[HeldFact], failed: bool = False) -> Row:
    if not witnesses:
        return Row(requirement, Truth.T)
    return Row(requirement, Truth.F if failed else Truth.U, tuple(witnesses))


# --- SUPPORT, rows 1-8 (4.3) --------------------------------------------------------------------------------------------


def _row_kind(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 1 (module docstring)."""
    found = _fact(R, event, _A.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        kind = found.value
        if kind in catalogue.UMBRELLAS:  # h5: a positive umbrella never supports a method-specific code
            return _row(rq.Requirement.SUP_KIND, [_open(found, _METHOD, _A.KIND, event, event, group, R,
                                                        questions.coding_rule(_Rule.UMBRELLA))])
        purpose = _fact(R, event, _A.PURPOSE)
        if kind in catalogue.HEMOSTASIS_KINDS and _covers_group(kind, group):
            # read as itself (an injection code): a purpose supported hemostasis makes it a bleeding control instead,
            # and one that claims hemostasis without establishing it leaves that open (catalogue.catalogue_kind)
            if facts_.holds(purpose, Purpose.HEMOSTASIS):
                return _row(rq.Requirement.SUP_KIND, [_fails(_STATUS, False, _A.PURPOSE, event, purpose,
                                                             _Rule.NOT_DOCUMENTED, R, event)], failed=True)
            if _claims_hemostasis(purpose):
                return _row(rq.Requirement.SUP_KIND, [_open(purpose, _STATUS, _A.PURPOSE, event, event, group, R)])
            return _row(rq.Requirement.SUP_KIND, [])
        if _covers_group(kind, group):
            return _row(rq.Requirement.SUP_KIND, [])
        if kind in catalogue.HEMOSTASIS_KINDS and _bleeding_group(group):
            if facts_.holds(purpose, Purpose.HEMOSTASIS):
                return _row(rq.Requirement.SUP_KIND, [])
            return _row(rq.Requirement.SUP_KIND, [_open(purpose, _STATUS, _A.PURPOSE, event, event, group, R)],
                        failed=facts_.established(purpose))
        return _row(rq.Requirement.SUP_KIND, [_fails(_STATUS, False, _A.KIND, event, found, _Rule.NOT_DOCUMENTED, R,
                                                     event)], failed=True)
    return _row(rq.Requirement.SUP_KIND, [_open(found, _STATUS, _A.KIND, event, event, group, R)],
                failed=facts_.established(found))


def _row_status(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 2 with ATT (module docstring)."""
    found = _fact(R, event, _A.STATUS)
    accepted = _POSITIVE if c.has(Tag.ATT) else frozenset({Status.PERFORMED})
    if found.result is Result.SUPPORTED and isinstance(found.value, Status):
        if found.value in accepted:
            return _row(rq.Requirement.SUP_STATUS, [])
        if found.value is Status.ATTEMPTED_NOT_COMPLETED:  # C-9: a hold, the 52/53 consideration (assess)
            return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, True, _A.STATUS, event, found, _Rule.ATTEMPTED, R,
                                                           event)], failed=True)
        return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, False, _A.STATUS, event, found, _Rule.NOT_DOCUMENTED,
                                                       R, event)], failed=True)
    if found.result is Result.NEGATED:
        return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, False, _A.STATUS, event, found, _Rule.NOT_DOCUMENTED,
                                                       R, event)], failed=True)
    return _row(rq.Requirement.SUP_STATUS, [_open(found, _STATUS, _A.STATUS, event, event, group, R)])


def _row_value(requirement: rq.Requirement, attribute: Attribute, wanted: DateRelation | Performer,
               ask: rq.Item, rule: questions.Rule) -> Callable[[_Code, Sequence[Kind], FactSet, Id], Row]:
    """4.3 rows 3 and 4: the act's effective ``attribute`` supported ``wanted``; established otherwise, the row's
    question (no explanation is given for it); not established, its question."""
    def row(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
        found = _fact(R, event, attribute)
        if facts_.holds(found, wanted):
            return _row(requirement, [])
        if facts_.established(found):
            return _row(requirement, [_fails(ask, False, attribute, event, found, rule, R, event)], failed=True)
        return _row(requirement, [_open(found, ask, attribute, event, event, group, R)])
    return row


_row_date = _row_value(rq.Requirement.SUP_DATE, _A.DATE_RELATION, DateRelation.ON_DATE_OF_SERVICE, _TIME,
                       _Rule.TIMING)
_row_performer = _row_value(rq.Requirement.SUP_PERFORMER, _A.PERFORMER, Performer.DOCUMENTING_TEAM, _PERFORMER,
                            _Rule.PERFORMER)


def _row_entry(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 5: the entry supported documenting_clinician; another owner supported is the another-entry explanation."""
    return _row(rq.Requirement.SUP_ENTRY, *_entry(R, event, event, group))


def _entry(R: FactSet, subject: Id, act: Id, group: Sequence[Kind]) -> tuple[list[HeldFact], bool]:
    found = _fact(R, subject, _A.ENTRY)
    if facts_.holds(found, Owner.DOCUMENTING_CLINICIAN):
        return [], False
    if found.result is Result.SUPPORTED and isinstance(found.value, Owner):
        return [_fails(_ENTRY, True, _A.ENTRY, subject, found, _Rule.ENTRY, R, subject)], True
    if found.result is Result.NEGATED:
        return [_fails(_ENTRY, False, _A.ENTRY, subject, found, _Rule.ENTRY, R, subject)], True
    return [_open(found, _ENTRY, _A.ENTRY, subject, act, group, R)], False


def _row_session(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 6: route (a), the session and its kind; route (b), the act's places in the code's regions."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        return _row(rq.Requirement.SUP_SESSION, *_regions(c, group, R, event))
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.SUP_SESSION, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])
    kind = _fact(R, session, _A.KIND)
    if facts_.holds(kind, c.link.family):
        return _row(rq.Requirement.SUP_SESSION, [])
    if facts_.established(kind):
        return _row(rq.Requirement.SUP_SESSION, [_fails(_PROCEDURE, False, _A.KIND, session, kind, _Rule.SESSION, R,
                                                        event)], failed=True)
    return _row(rq.Requirement.SUP_SESSION, [_open(kind, _PROCEDURE, _A.KIND, session, event, group, R)])


def _regions(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> tuple[list[HeldFact], bool]:
    """Route (b)'s row 6: every place of the act established, its supported places in the code's regions, at least
    one."""
    places = _members(R, event, _A.TARGET_PLACES)
    open_ = [member for member in places if not facts_.established(member)]
    if open_:
        return [_open(open_[0], _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R)], False
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    if supported and all(anatomy.in_regions(place, c.link.regions) for place in supported):
        return [], False
    if supported and any(place not in _UNPLACED and not anatomy.in_regions(place, c.link.regions)
                         for place in supported):
        return [_fails(_ACT_TARGET, False, _A.TARGET_PLACES, event, places[0], _Rule.SESSION, R, event)], True
    return [_open(places[0] if places else facts_.SILENT, _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R)], False


def _may_be_in(R: FactSet, event: Id, session: Id) -> bool:
    """Whether ``event`` may be in ``session`` by its own session fact: facts.possibly's (supported: that session; not
    established: the claimed one, a doubt's readings, a contradiction's sides, an unrejected control's, every one for
    an empty slot; negated: none), and every session when the fact names an id the FactSet does not hold, as its value
    or a reading (4.11: a missing identifier manufactures neither a match nor a non-match; step 4b's
    coverage.sessions_of reads it the same way). Monotone: a weakened fact never leaves fewer sessions open."""
    found = _fact(R, event, _A.SESSION)
    named = (found.value,) if facts_.established(found) else (found.value, *found.options)
    if found.result is not Result.NEGATED and any(isinstance(value, Id) and value not in R.sessions
                                                  for value in named):
        return True
    return facts_.possibly(found, session)


def _admits_examination(R: FactSet, session: Id) -> bool:
    """Whether ``session`` may hold an examination: its kind not established, or a family whose kinds hold the
    examination (FAMILY_KINDS, the table K2 reads: DECISIONS D191). An office visit's session holds none."""
    kind = _fact(R, session, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, SessionKind):
        return True
    return Kind.EXAMINATION in facts_.family_kinds(kind.value)


def is_examination_of(R: FactSet, event: Id, session: Id) -> bool:
    """``event`` established as ``session``'s examination by its own facts: kind supported examination, session
    supported ``session``."""
    return (facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.holds(_fact(R, event, _A.SESSION), session))


def another_occasion(R: FactSet, event: Id) -> bool:
    """``event`` established as of another occasion - a plan (status supported planned), another date (4.4's
    established_other_date) or another performer (established_other_performer): the statements K1 and 4.6 condition 3
    read as carrying no breadth. A denial (status negated) is none."""
    return facts_.holds(_fact(R, event, _A.STATUS), Status.PLANNED) or other_date(R, event) or other_performer(R, event)


def examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The events that may be ``session``'s examination (4.3 row 7; step 1f's hand-off R9(d): by their own kind and
    session facts, never session.examination), in pass 1's order: every event established as its examination
    (``is_examination_of``), and every event whose kind is possibly the examination and which may be in it
    (``_may_be_in``: an empty slot included), when its family admits an examination (``_admits_examination``)."""
    admits = _admits_examination(R, session)
    return tuple(event for event in R.events
                 if is_examination_of(R, event, session)
                 or (admits and facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION)
                     and _may_be_in(R, event, session)))


def _done_rows(R: FactSet, exam: Id, exam_group: Sequence[Kind]) -> tuple[list[HeldFact], bool]:
    """Rows 2-5 on an examination (4.3 row 7): the witnesses of every row that is not T (an examination begun counts as
    done, v1's done), and whether one is an established failure."""
    witnesses: list[HeldFact] = []
    failed = False
    status = _fact(R, exam, _A.STATUS)
    if not (status.result is Result.SUPPORTED and isinstance(status.value, Status) and status.value in _POSITIVE):
        if facts_.established(status):
            witnesses.append(_fails(_STATUS, False, _A.STATUS, exam, status, _Rule.EXAMINATION, R, exam))
            failed = True
        else:
            witnesses.append(_open(status, _STATUS, _A.STATUS, exam, exam, exam_group, R))
    for attribute, wanted, ask in ((_A.DATE_RELATION, DateRelation.ON_DATE_OF_SERVICE, _TIME),
                                   (_A.PERFORMER, Performer.DOCUMENTING_TEAM, _PERFORMER)):
        value = _fact(R, exam, attribute)
        if facts_.holds(value, wanted):
            continue
        if facts_.established(value):
            witnesses.append(_fails(ask, False, attribute, exam, value, _Rule.EXAMINATION, R, exam))
            failed = True
        else:
            witnesses.append(_open(value, ask, attribute, exam, exam, exam_group, R))
    held, entry_failed = _entry(R, exam, exam, exam_group)
    witnesses.extend(held)
    return witnesses, failed or entry_failed


def _row_done(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 7: every event that may be the session's examination (``examinations``) passes rows 2-5 (an examination
    begun counts as done); a session with none is the act's own. The examination's facts alone are read (K2).
    - An event that passes rows 2-5 never makes a session not done, whichever session it is: it adds nothing.
    - When an event established as the session's examination passes rows 2-5 (the session's own done examination), an
      event established as of another occasion (``another_occasion``: a plan, another date, another performer) is no
      examination done on the date of service beside it, whatever its tie: it adds nothing. "Repeat colonoscopy in 3
      years." and "Colonoscopy in 2019 was normal.", each filed as an examination with its session slot empty, no
      longer hold every code of every session (the refutation's F1; 4.9 retires D31's "anything unresolved holds
      everything"). Read whatever the tie, so that weakening the tie never releases (P-MONO); without the session's
      own done examination such an event may be its only one, and holds.
    - Otherwise each event's witnesses are recorded: F when it is established as the session's examination and an
      established fact fails rows 2-5, else U, with the witnesses of its kind and session when not established."""
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.SUP_SESSION_DONE, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])
    witnesses: list[HeldFact] = []
    failed = False
    exam_group = (Kind.EXAMINATION,)
    exams = examinations(R, session)
    rows = {exam: _done_rows(R, exam, exam_group) for exam in exams}
    done = any(is_examination_of(R, exam, session) and not rows[exam][0] for exam in exams)
    for exam in exams:
        held, exam_failed = rows[exam]
        if not held or (done and another_occasion(R, exam)):
            continue
        if is_examination_of(R, exam, session):
            failed = failed or exam_failed
        else:
            kind = _fact(R, exam, _A.KIND)
            if not facts_.holds(kind, Kind.EXAMINATION):
                witnesses.append(_open(kind, _STATUS, _A.KIND, exam, exam, exam_group, R))
            tied = _fact(R, exam, _A.SESSION)
            if not facts_.holds(tied, session):
                witnesses.append(_open(tied, _STATUS, _A.SESSION, exam, exam, exam_group, R))
        witnesses.extend(held)
    return _row(rq.Requirement.SUP_SESSION_DONE, witnesses, failed)


def _row_clean(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 8: every relation of a paired statement that is not INDEPENDENT (engine/pairing.py, 4.5) - its item at
    its rank, its cause relation:<type> - and every unlisted denial or doubt pairing with the act (statement_scope,
    cause unlisted)."""
    witnesses: list[HeldFact] = []
    own = _conflict_kind(R, event, group)
    for pair in pairing.pairs_of(R, event):
        found = pairing.item(pair)
        cause = pairing.cause(pair)
        if found is None or cause is None:
            continue
        if found.fact is rq.FactKey.CONFLICT:
            kind = own if own in pair.kinds else min(pair.kinds, key=list(Kind).index, default=own)
            key = rq.fact_key(rq.FactKey.CONFLICT, kind)
        else:
            key = rq.fact_key(found.fact)
        attribute = _ROW_ATTRIBUTE[pair.row] if pair.relation is pairing.Relation.UNRESOLVED and pair.row else _A.STATUS
        witnesses.append(_held(key, found.rank, _Q, attribute, event, None, cause, pair.spans))
    for unlisted in pairing.unlisted_pairs(R, event):
        witnesses.append(_held(rq.fact_key(_SCOPE.fact), _SCOPE.rank, _Q, None, event, None, questions.UNLISTED,
                               unlisted.spans))
    return _row(rq.Requirement.SUP_CLEAN, witnesses)


def _row_encounter(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3's E/M row: the visit's session encounter supported this_encounter (event_time)."""
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [_open(found, _TIME, _A.SESSION, event, event, group, R)])
    encounter = _fact(R, session, _A.ENCOUNTER)
    if facts_.holds(encounter, EncounterRelation.THIS_ENCOUNTER):
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [])
    if facts_.established(encounter):
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [_fails(_TIME, False, _A.ENCOUNTER, session, encounter,
                                                             _Rule.ENCOUNTER, R, event)], failed=True)
    return _row(rq.Requirement.V_THIS_ENCOUNTER, [_open(encounter, _TIME, _A.ENCOUNTER, session, event, group, R)])


_SUPPORT_ROWS: tuple[Callable[[_Code, Sequence[Kind], FactSet, Id], Row], ...] = (
    _row_kind, _row_status, _row_date, _row_performer, _row_entry, _row_session, _row_done, _row_clean)
_EM_TEMPLATES: frozenset[Template] = frozenset({Template.EM, Template.EM_ADDON})


# --- the code-specific rows (4.3's second table) ------------------------------------------------------------------------


def _row_technique(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """TECH: the act's device supported in the code's technique class; another class is the another-technique
    explanation; a device of no class, a denied one or one not established is the technique question."""
    required = c.spec.row.technique if c.spec.row is not None else None
    found = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if found.result is Result.SUPPORTED and isinstance(found.value, Device):
        named = catalogue.technique_class(found.value)
        if named is required:
            return _row(Tag.TECH, [])
        if named is not None:
            return _row(Tag.TECH, [_fails(_TECHNIQUE, True, _A.TECHNIQUE_DEVICE, event, found, _Rule.TECHNIQUE, R,
                                          event)], failed=True)
    return _row(Tag.TECH, [_open(found, _TECHNIQUE, _A.TECHNIQUE_DEVICE, event, event, group, R,
                                 questions.coding_rule(_Rule.TECHNIQUE))])


def _places_of(R: FactSet, event: Id) -> tuple[tuple[Fact, ...], Fact | None]:
    """SITE's places (D29): the act's place facts and its lesion's (when its target lesion is supported); and the first
    fact among them, or its lesion fact, that is not established (None when every one is)."""
    places = list(_members(R, event, _A.TARGET_PLACES))
    lesion = _fact(R, event, _A.TARGET_LESION)
    open_: Fact | None = None if facts_.established(lesion) or facts_.silent(lesion) else lesion
    lesion_id = _id(lesion)
    if lesion_id is not None:
        places += list(_members(R, lesion_id, _A.PLACES))
    for member in places:
        if open_ is None and not facts_.established(member):
            open_ = member
    return tuple(places), open_


def _row_site(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """SITE (D29; module docstring)."""
    site = c.spec.row.site if c.spec.row is not None else None
    if site is None:
        return _row(Tag.SITE, [])
    places, open_ = _places_of(R, event)
    if open_ is not None:
        return _row(Tag.SITE, [_open(open_, _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R)])
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    within = catalogue.SITE_CLASSES[site]
    if supported and all(place in within for place in supported):
        return _row(Tag.SITE, [])
    if supported and all(place not in within and place not in _UNPLACED for place in supported):
        return _row(Tag.SITE, [_fails(_ACT_TARGET, True, _A.TARGET_PLACES, event, places[0], _Rule.SITE, R, event)],
                    failed=True)
    first = places[0] if places else facts_.SILENT
    return _row(Tag.SITE, [_open(first, _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R,
                                 questions.coding_rule(_Rule.SITE))])


def _row_structure(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """STRUCT:pfc (43240): the structure supported pancreatic_fluid_collection and no supported place biliary or hepatic
    (every place established); another structure, or a place set apart, is the another-structure explanation."""
    found = _fact(R, event, _A.TARGET_STRUCTURE)
    places = _members(R, event, _A.TARGET_PLACES)
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    apart = any(anatomy.in_regions(place, catalogue.DEFINING_TARGET_APART) for place in supported)
    open_place = next((member for member in places if not facts_.established(member)), None)
    if facts_.holds(found, Structure.PANCREATIC_FLUID_COLLECTION):
        if apart:
            return _row(Tag.STRUCT_PFC, [_fails(_TARGET, True, _A.TARGET_PLACES, event, places[0], _Rule.STRUCTURE, R,
                                                event)], failed=True)
        if open_place is None:
            return _row(Tag.STRUCT_PFC, [])
        return _row(Tag.STRUCT_PFC, [_open(open_place, _TARGET, _A.TARGET_PLACES, event, event, group, R,
                                           questions.coding_rule(_Rule.STRUCTURE))])
    if facts_.established(found):
        return _row(Tag.STRUCT_PFC, [_fails(_TARGET, bool(supported), _A.TARGET_STRUCTURE, event, found,
                                            _Rule.STRUCTURE, R, event)], failed=True)
    return _row(Tag.STRUCT_PFC, [_open(found, _TARGET, _A.TARGET_STRUCTURE, event, event, group, R,
                                       questions.coding_rule(_Rule.STRUCTURE))])


def _row_route(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """ROUTE (43253): the route supported eus_transmural; submucosal is the wall injection's explanation; another
    established route, or none, the route question."""
    found = _fact(R, event, _A.TECHNIQUE_ROUTE)
    if facts_.holds(found, Route.EUS_TRANSMURAL):
        return _row(Tag.ROUTE, [])
    if facts_.holds(found, Route.SUBMUCOSAL):
        return _row(Tag.ROUTE, [_fails(_TECHNIQUE, True, _A.TECHNIQUE_ROUTE, event, found, _Rule.ROUTE, R, event)],
                    failed=True)
    if facts_.established(found):
        return _row(Tag.ROUTE, [_fails(_TECHNIQUE, False, _A.TECHNIQUE_ROUTE, event, found, _Rule.ROUTE, R, event)],
                    failed=True)
    return _row(Tag.ROUTE, [_open(found, _TECHNIQUE, _A.TECHNIQUE_ROUTE, event, event, group, R,
                                  questions.coding_rule(_Rule.ROUTE))])


def _no_session(requirement: Tag, R: FactSet, event: Id, group: Sequence[Kind]) -> Row:
    found = _fact(R, event, _A.SESSION)
    return _row(requirement, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])


def _row_tract(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """TRACT (D171(2)): the session's tract supported the code's; another supported tract is the another-tract
    explanation."""
    required = c.spec.row.tract if c.spec.row is not None else None
    session = _session(R, event)
    if session is None or required is None:
        return _no_session(Tag.TRACT, R, event, group)
    found = _fact(R, session, _A.TRACT)
    if facts_.holds(found, required):
        return _row(Tag.TRACT, [])
    if facts_.established(found):
        explained = found.result is Result.SUPPORTED
        return _row(Tag.TRACT, [_fails(_PROCEDURE, explained, _A.TRACT, session, found, _Rule.TRACT, R, event)],
                    failed=True)
    return _row(Tag.TRACT, [_open(found, _PROCEDURE, _A.TRACT, session, event, group, R)])


def _reached(R: FactSet, session: Id) -> tuple[tuple[Fact, ...], list[Extent]]:
    found = _members(R, session, _A.REACHED)
    return found, [member.value for member in found if member.result is Result.SUPPORTED
                   and isinstance(member.value, Extent)]


def _contradicted(found: Iterable[Fact]) -> Fact | None:
    return next((member for member in found if member.result is Result.CONTRADICTED), None)


def _row_stations(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """STATIONS (43242, 43259; [R:SC-B]): module docstring."""
    session = _session(R, event)
    if session is None:
        return _no_session(Tag.STATIONS, R, event, group)
    stations = _members(R, session, _A.STATIONS)
    reached, points = _reached(R, session)
    conflict = _contradicted((*stations, *reached))
    if conflict is not None:
        return _row(Tag.STATIONS, [_open(conflict, _STATIONS, _A.STATIONS, session, event, group, R)])
    denied = [member for member in stations if member.result is Result.NEGATED
              and member.value in catalogue.UPPER_STATIONS]
    if denied:
        return _row(Tag.STATIONS, [_fails(_STATIONS, True, _A.STATIONS, session, denied[0], _Rule.STATIONS, R,
                                          event)], failed=True)
    far = any(point in catalogue.FULL_REACH for point in points)
    examined = {member.value for member in stations if member.result is Result.SUPPORTED}
    if not stations:
        complete = R.completeness.get(session) is Result.SUPPORTED
        if complete and far:
            return _row(Tag.STATIONS, [])
    elif all(facts_.established(member) for member in stations) and far and all(
            station in examined for station in catalogue.UPPER_STATIONS):
        return _row(Tag.STATIONS, [])
    first = next((member for member in (*stations, *reached) if not facts_.established(member)), None)
    if first is None:
        return _row(Tag.STATIONS, [_held(rq.fact_key(_STATIONS.fact), _STATIONS.rank, _Q, _A.STATIONS, session,
                                         None, questions.coding_rule(_Rule.STATIONS), _anchor(R, event))])
    return _row(Tag.STATIONS, [_open(first, _STATIONS, _A.STATIONS, session, event, group, R)])


def _row_limited(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """LIMITED (D28, D171(3); step 1f's hand-off #7): 43231 and 43232 need a reach short of the duodenum; 43237 and
    43238, whose profile includes the EGD (catalogue.includes_examination), a station negated or a reach short; all
    three stations examined is the class explanation."""
    session = _session(R, event)
    if session is None:
        return _no_session(Tag.LIMITED, R, event, group)
    stations = _members(R, session, _A.STATIONS)
    reached, points = _reached(R, session)
    conflict = _contradicted((*stations, *reached))
    if conflict is not None:
        return _row(Tag.LIMITED, [_open(conflict, _STATIONS, _A.STATIONS, session, event, group, R)])
    short = (bool(points) and all(facts_.established(member) for member in reached)
             and all(point in catalogue.SHORT_OF_DUODENUM for point in points))
    if catalogue.includes_examination(c.code, SessionKind.EGD):
        examined = {member.value for member in stations if member.result is Result.SUPPORTED}
        if all(station in examined for station in catalogue.UPPER_STATIONS):  # the class explanation, whatever else
            # its witness is an examined upper station (D189: the result it rests on), never a station negated
            # elsewhere (the jejunum) that happens to come first
            witness = next(member for member in stations if member.result is Result.SUPPORTED
                           and member.value in catalogue.UPPER_STATIONS)
            return _row(Tag.LIMITED, [_fails(_STATIONS, True, _A.STATIONS, session, witness, _Rule.LIMITED, R,
                                             event)], failed=True)
        if short or any(member.result is Result.NEGATED and member.value in catalogue.UPPER_STATIONS
                        for member in stations):
            return _row(Tag.LIMITED, [])
    else:
        if short:
            return _row(Tag.LIMITED, [])
        if any(point in catalogue.FULL_REACH for point in points):
            return _row(Tag.LIMITED, [_fails(_STATIONS, False, _A.REACHED, session, reached[0], _Rule.LIMITED, R,
                                             event)], failed=True)
    first = next((member for member in (*reached, *stations) if not facts_.established(member)), None)
    if first is None:
        return _row(Tag.LIMITED, [_held(rq.fact_key(_STATIONS.fact), _STATIONS.rank, _Q, _A.STATIONS, session, None,
                                        questions.coding_rule(_Rule.LIMITED), _anchor(R, event))])
    return _row(Tag.LIMITED, [_open(first, _STATIONS, _A.STATIONS, session, event, group, R)])


def _row_lower(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """LOWER (D43): every reached point established and in the class reach, at least one; the stoma class also an
    anatomy entry of type stoma supported and the approach supported through_stoma. A supported point outside the
    reach, and for the stoma class an approach established otherwise (supported another approach, or through_stoma
    denied), are the misfit: the examination-class explanation (4.3 LOWER: "misfit: held (class)"; 4.8: an established
    failure is an explanation - the refutation's F4)."""
    exam_class = c.spec.row.eus_class if c.spec.row is not None else None
    session = _session(R, event)
    if session is None or exam_class is None:
        return _no_session(Tag.LOWER, R, event, group)
    reached, points = _reached(R, session)
    conflict = _contradicted(reached)
    if conflict is not None:
        return _row(Tag.LOWER, [_open(conflict, _EXTENT, _A.REACHED, session, event, group, R)])
    reach = catalogue.EUS_CLASS_REACH[exam_class]
    outside = next((member for member in reached if member.result is Result.SUPPORTED
                    and isinstance(member.value, Extent) and member.value not in reach), None)
    if outside is not None:
        return _row(Tag.LOWER, [_fails(_EXTENT, True, _A.REACHED, session, outside, _Rule.LOWER, R, event)],
                    failed=True)
    open_ = next((member for member in reached if not facts_.established(member)), None)
    if open_ is not None or not points:
        return _row(Tag.LOWER, [_open(open_ if open_ is not None else facts_.SILENT, _EXTENT, _A.REACHED, session,
                                      event, group, R)])
    if exam_class is catalogue.EusClass.STOMA:
        approach = _fact(R, session, _A.APPROACH)
        stoma = any(facts_.holds(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) for entry in R.anatomy)
        if not facts_.holds(approach, Approach.THROUGH_STOMA):
            if ((approach.result is Result.SUPPORTED and isinstance(approach.value, Approach))
                    or facts_.denied(approach, Approach.THROUGH_STOMA)):  # misfit: the class explanation (4.3 LOWER)
                return _row(Tag.LOWER, [_fails(_EXTENT, True, _A.APPROACH, session, approach, _Rule.LOWER, R,
                                               event)], failed=True)
            return _row(Tag.LOWER, [_open(approach, _EXTENT, _A.APPROACH, session, event, group, R,
                                          questions.coding_rule(_Rule.LOWER))])
        if not stoma:
            return _row(Tag.LOWER, [_held(rq.fact_key(_EXTENT.fact), _EXTENT.rank, _Q, _A.TYPE, session, None,
                                          questions.coding_rule(_Rule.LOWER), _anchor(R, event))])
    return _row(Tag.LOWER, [])


def _row_yield(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """YIELD (43264; D106): module docstring."""
    found = _fact(R, event, _A.YIELD)
    if found.result is Result.CONTRADICTED:
        return _row(Tag.YIELD, [_held(rq.fact_key(rq.FactKey.CONFLICT, Kind.STONE_EXTRACTION), rq.Rank.CONFLICT, _Q,
                                      _A.YIELD, event, found, questions.cause_of(found), _quoted(found, R, event))])
    if found.result is Result.SUPPORTED and isinstance(found.value, Material) and found.value in _RETRIEVED:
        return _row(Tag.YIELD, [])
    if found.result is Result.NEGATED:
        return _row(Tag.YIELD, [_fails(_YIELD, True, _A.YIELD, event, found, _Rule.YIELD, R, event)], failed=True)
    return _row(Tag.YIELD, [_open(found, _YIELD, _A.YIELD, event, event, group, R,
                                  questions.coding_rule(_Rule.YIELD))])


def _row_cause(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """CAUSE (every code covering the bleeding control): module docstring."""
    purpose = _fact(R, event, _A.PURPOSE)
    cause = _fact(R, event, _A.CAUSE)
    conflict = _contradicted((purpose, cause))
    if conflict is not None:
        return _row(Tag.CAUSE, [_open(conflict, _CAUSE, _A.CAUSE, event, event, group, R)])
    if facts_.holds(purpose, Purpose.PROPHYLAXIS):
        return _row(Tag.CAUSE, [_fails(_BUNDLED, True, _A.PURPOSE, event, purpose, _Rule.CAUSE, R, event)],
                    failed=True)
    if not facts_.holds(purpose, Purpose.HEMOSTASIS):
        return _row(Tag.CAUSE, [_open(purpose, _CAUSE, _A.PURPOSE, event, event, group, R,
                                      questions.coding_rule(_Rule.CAUSE))], failed=facts_.established(purpose))
    if facts_.holds(cause, Cause.ACT_OF_THIS_SESSION):
        return _row(Tag.CAUSE, [_fails(_BUNDLED, True, _A.CAUSE, event, cause, _Rule.CAUSE, R, event)], failed=True)
    if cause.result is Result.SUPPORTED and isinstance(cause.value, Cause) and cause.value in _BLEEDING_CAUSES:
        return _row(Tag.CAUSE, [])
    return _row(Tag.CAUSE, [_open(cause, _CAUSE, _A.CAUSE, event, event, group, R,
                                  questions.coding_rule(_Rule.CAUSE))])


def counterparts(R: FactSet, event: Id) -> tuple[Id, ...]:
    """XCHG (D105, D127): the possibly-performed counterparts of a stent act - a stent removal or exchange beside a
    placement, a placement or exchange beside a removal - that nothing sets apart: positive (4.4), possibly of a
    counterpart kind, and neither both ducts supported and different nor both sessions supported and different."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    wanted = frozenset(kind for own in kinds for kind in _COUNTERPARTS.get(own, frozenset()))
    if not wanted:
        return ()
    duct, session = _fact(R, event, _A.TARGET_DUCT), _session(R, event)
    out: list[Id] = []
    for other in R.events:
        if other == event or not positive(R, other):
            continue
        if not facts_.possible_kinds(R, other, of_family=False) & wanted:
            continue
        theirs = _fact(R, other, _A.TARGET_DUCT)
        if (duct.result is Result.SUPPORTED and theirs.result is Result.SUPPORTED and duct.value != theirs.value):
            continue
        other_session = _session(R, other)
        if session is not None and other_session is not None and session != other_session:
            continue
        out.append(other)
    return tuple(out)


def _same_duct(R: FactSet, one: Id, other: Id) -> bool:
    first, second = _fact(R, one, _A.TARGET_DUCT), _fact(R, other, _A.TARGET_DUCT)
    return (first.result is Result.SUPPORTED and second.result is Result.SUPPORTED and first.value is not None
            and first.value == second.value)


def _exchange_witness(R: FactSet, event: Id, other: Id, group: Sequence[Kind]) -> HeldFact:
    """XCHG's hold of a removal or placement beside its counterpart: the duct question while the two ducts are not both
    supported and equal (act_target, rank 11), else whether the two were one exchange (performed_status, rank 4)."""
    spans = tuple(sorted(set(_anchor(R, event)) | set(_anchor(R, other))))
    duct = _fact(R, event, _A.TARGET_DUCT)
    if _same_duct(R, event, other):
        return _held(rq.fact_key(_STATUS.fact), _STATUS.rank, _Q, _A.STATUS, event, None,
                     questions.coding_rule(_Rule.EXCHANGE), spans)
    return _held(rq.fact_key(_ACT_TARGET.fact), _ACT_TARGET.rank, _Q, _A.TARGET_DUCT, event, duct,
                 questions.coding_rule(_Rule.EXCHANGE), spans)


def _row_exchange(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """XCHG for 43274 and 43275: no possibly-performed counterpart in the same or an unknown duct (43276 reads its
    pairs in ``decide``)."""
    if Kind.STENT_EXCHANGE in group:
        return _row(Tag.XCHG, [])
    return _row(Tag.XCHG, [_exchange_witness(R, event, other, group) for other in counterparts(R, event)])


# The code-specific rows 4.4's code_requirements evaluates over every supporting act; YIELD, a row of SUPPORT itself (4.3:
# "no support from that act"). The others are steps 4b-5a's, which assess appends (4.4).
_TAG_ROWS: Mapping[Tag, Callable[[_Code, Sequence[Kind], FactSet, Id], Row]] = MappingProxyType({
    Tag.TECH: _row_technique, Tag.SITE: _row_site, Tag.STRUCT_PFC: _row_structure, Tag.ROUTE: _row_route,
    Tag.TRACT: _row_tract, Tag.STATIONS: _row_stations, Tag.LIMITED: _row_limited, Tag.LOWER: _row_lower,
    Tag.CAUSE: _row_cause, Tag.XCHG: _row_exchange})
_FILTER_ROWS: Mapping[Tag, Callable[[_Code, Sequence[Kind], FactSet, Id], Row]] = MappingProxyType({
    Tag.YIELD: _row_yield})
EVALUATED_TAGS: frozenset[Tag] = frozenset(_TAG_ROWS) | frozenset(_FILTER_ROWS)


def support(code: str, group: Sequence[Kind], R: FactSet, event: Id) -> Support:
    """SUPPORT(E, C, g) (module docstring): every row's truth and witnesses, in 4.3's order - rows 1-8, the E/M encounter
    for an E/M code, and 43264's YIELD."""
    return _support(_code(code), tuple(group), R, event)


def _support(c: _Code, group: tuple[Kind, ...], R: FactSet, event: Id) -> Support:
    rows = [row(c, group, R, event) for row in _SUPPORT_ROWS]
    if c.template in _EM_TEMPLATES:
        rows.append(_row_encounter(c, group, R, event))
    rows += [_FILTER_ROWS[tag](c, group, R, event) for tag in c.spec.tags if tag in _FILTER_ROWS]
    return Support(event, tuple(rows))


def code_rows(code: str, group: Sequence[Kind], R: FactSet, event: Id) -> tuple[Row, ...]:
    """4.4's code_requirements on one supporting act: the code-specific rows this step evaluates (module docstring), in
    Appendix A's tag order."""
    return _code_rows(_code(code), tuple(group), R, event)


def _code_rows(c: _Code, group: tuple[Kind, ...], R: FactSet, event: Id) -> tuple[Row, ...]:
    return tuple(_TAG_ROWS[tag](c, group, R, event) for tag in c.spec.tags if tag in _TAG_ROWS)


# --- 43276's pairs (XCHG) -----------------------------------------------------------------------------------------------


def _pairs(c: _Code, R: FactSet) -> tuple[list[tuple[Id, Id]], list[Support]]:
    """43276's other way of being supported (4.3 XCHG): every stent removal and stent placement that each support the
    code (rows 1-8 over their own kinds) in one duct, both ducts supported and equal - the pairs found; and, for every
    positive removal and positive placement nothing sets apart, the pair as a positive candidate, its witnesses both
    acts' and the duct's (bound by its removal)."""
    removals = [event for event in candidates(R, _EXCHANGE_PARTS[0])]
    placements = [event for event in candidates(R, _EXCHANGE_PARTS[1])]
    found: list[tuple[Id, Id]] = []
    pending: list[Support] = []
    for removal in removals:
        for placement in placements:
            if removal == placement or placement not in counterparts(R, removal):
                continue
            first = _support(c, _EXCHANGE_PARTS[0], R, removal)
            second = _support(c, _EXCHANGE_PARTS[1], R, placement)
            same = _same_duct(R, removal, placement)
            if first.met and second.met and same:
                found.append((removal, placement))
                continue
            if positive(R, removal) and positive(R, placement):
                duct = () if same else (Row(Tag.XCHG, Truth.U, (_exchange_witness(R, removal, placement,
                                                                                   _EXCHANGE_PARTS[0]),)),)
                pending.append(Support(removal, first.rows + second.rows + duct, partner=placement))
    return found, pending


# --- exclusion (4.6) ----------------------------------------------------------------------------------------------------


@unique
class Covered(Enum):
    """How a code's kept spans cover a statement (C-10, 4.6 condition 4): by CITATION (overlapping its anchor, every
    kept span within its covering words), PARTIAL (overlapping, one reaching past them), or NONE (no overlap)."""
    CITATION = 'citation'
    PARTIAL = 'partial'
    NONE = 'none'


def _overlaps(one: Span, other: Span) -> bool:
    return one.start < other.end and other.start < one.end


def covering(R: FactSet, statement: Id) -> tuple[Span, ...]:
    """C-10's covering words of a statement (4.6 condition 4; D188): its anchor's kind and status words, and the ``at``
    spans of the ``statement`` sources of its target lesion, target places and date relation, each once, in order. A
    source citing its whole units (no located words) adds nothing."""
    anchor = R.anchors.get(statement)
    spans: list[Span] = []
    if anchor is not None:
        spans += [found for found in (anchor.kind_words, anchor.status_words) if found is not None]
    for attribute in _COVERING:
        domain = facts_.DOMAINS[(IdFamily.EVENT, attribute)]
        found = _members(R, statement, attribute) if domain.many else (_fact(R, statement, attribute),)
        for member in found:
            spans += [cited.at for cited in member.cited if cited.link is Link.STATEMENT and cited.at is not None]
    return tuple(sorted(set(spans)))


def within(span: Span, words: Sequence[Span]) -> bool:
    """C-10 over offsets: every offset of ``span`` lies inside the union of ``words`` (an empty span always does)."""
    position = span.start
    for part in sorted(words):
        if part.start > position:
            break
        position = max(position, part.end)
        if position >= span.end:
            return True
    return position >= span.end


def cover(R: FactSet, statement: Id, kept: Sequence[Span], kept_words: Sequence[Span] | None = None) -> Covered:
    """C-10 (module docstring): CITATION, PARTIAL or NONE. ``kept_words``: the letter-or-digit runs of the kept spans
    (R1's result); without them each kept span counts whole (fail-closed)."""
    anchor = R.anchors.get(statement)
    if anchor is None or not any(_overlaps(span, unit) for span in kept for unit in anchor.units):
        return Covered.NONE
    words = covering(R, statement)
    read = kept if kept_words is None else kept_words
    return Covered.CITATION if all(within(span, words) for span in read) else Covered.PARTIAL


def _in_family(c: _Code, R: FactSet, statement: Id) -> bool:
    """4.6 condition 1's place: route (a), the statement's session supported and its kind the code's family; route (b),
    every place of the statement established, its supported places in the code's regions, at least one."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        places = _members(R, statement, _A.TARGET_PLACES)
        supported = [member.value for member in places if member.result is Result.SUPPORTED]
        return (bool(supported) and all(facts_.established(member) for member in places)
                and all(isinstance(place, Landmark) and anatomy.in_regions(place, c.link.regions)
                        for place in supported))
    session = _session(R, statement)
    return session is not None and facts_.holds(_fact(R, session, _A.KIND), c.link.family)


def concerns(code: str, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6 condition 1: the statement's kind supported and covering the group; its session supported and of the code's
    family (route (b): its places in the code's regions)."""
    c = _code(code)
    return _concerns(c, group, R, statement)


def _concerns(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    kind = _fact(R, statement, _A.KIND)
    return (kind.result is Result.SUPPORTED and isinstance(kind.value, Kind) and _covers_group(kind.value, group)
            and _in_family(c, R, statement))


def deciding(R: FactSet, statement: Id) -> Attribute | None:
    """4.6 condition 2: the statement's first established deciding fact - status negated performed or supported planned;
    the date relation supported earlier_date or later_date; the performer supported other_clinician or other_facility.
    None when none is established; an attempted status never decides (C-9)."""
    status = _fact(R, statement, _A.STATUS)
    if facts_.denied(status, Status.PERFORMED) or facts_.holds(status, Status.PLANNED):
        return _A.STATUS
    if other_date(R, statement):
        return _A.DATE_RELATION
    if other_performer(R, statement):
        return _A.PERFORMER
    return None


def not_exceptive(R: FactSet, statement: Id) -> bool:
    """4.6 condition 3: a statement of another date or performer, or a plan, carries no breadth (K1); any other (a
    current denial) needs its breadth supported and not exceptive (C-7)."""
    if other_date(R, statement) or other_performer(R, statement) or facts_.holds(_fact(R, statement, _A.STATUS),
                                                                                 Status.PLANNED):
        return True
    breadth = _fact(R, statement, _A.SCOPE_BREADTH)
    return (breadth.result is Result.SUPPORTED and isinstance(breadth.value, Breadth)
            and breadth.value is not Breadth.EXCEPTIVE)


def _possible_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The kinds an event may be when an exclusion asks whether anything doubts a code's kinds (4.2's widened arm), with
    the bleeding control a clip or an injection may be (D157(2))."""
    kinds = facts_.possible_kinds(R, event, of_family=True)
    if kinds & catalogue.HEMOSTASIS_KINDS and facts_.possibly(_fact(R, event, _A.PURPOSE), Purpose.HEMOSTASIS):
        return kinds | {Kind.BLEEDING_CONTROL}
    return kinds


def doubted(R: FactSet, group: Sequence[Kind]) -> bool:
    """4.6 condition 5 fails: an event possibly of the code's kinds (widened by its session's family) is possibly done
    today by the documenting team; or a DOUBT relation touches the kinds; or an unlisted entry is of them (or of no
    kind) - a denial or a doubt (4.6), and an act too: 3.2.6 rule 3 makes an unlisted act a synthetic doubted act, of
    no date and no performer pass 1 filed, so possibly today's act by the documenting team (the refutation's D2, read
    fail-closed: a question for the integration owner, the step's NOTES)."""
    for event in R.events:
        if not any(_covers_group(kind, group) for kind in _possible_kinds(R, event)):
            continue
        status = _fact(R, event, _A.STATUS)
        if (any(facts_.possibly(status, value) for value in _POSITIVE)
                and facts_.possibly(_fact(R, event, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE)
                and facts_.possibly(_fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM)):
            return True
    for pair in pairing.pairs(R):
        if pair.relation is pairing.Relation.DOUBT and any(_covers_group(kind, group) for kind in pair.kinds):
            return True
    return any(entry.kind is None or _covers_group(entry.kind, group) for entry in R.unlisted)


def broad(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.10's broad denial: status negated performed, breadth supported all_of_kind, its session supported (of the
    code's family: it concerns the code), its date relation supported on_date_of_service."""
    return (_concerns(c, group, R, statement)
            and facts_.denied(_fact(R, statement, _A.STATUS), Status.PERFORMED)
            and facts_.holds(_fact(R, statement, _A.SCOPE_BREADTH), Breadth.ALL_OF_KIND)
            and facts_.holds(_fact(R, statement, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE))


def possibly_here(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6's last paragraph: a denial of the code's kinds (its kind possibly one of them, 4.2's widened arm) whose
    session or date relation is not established - possibly this session (a session not established, or one possibly of
    the code's family), possibly today - so a broad denial is never dropped."""
    if not facts_.denied(_fact(R, statement, _A.STATUS), Status.PERFORMED):
        return False
    if not any(_covers_group(kind, group) for kind in _possible_kinds(R, statement)):
        return False
    session, timing = _fact(R, statement, _A.SESSION), _fact(R, statement, _A.DATE_RELATION)
    unplaced = not facts_.established(session) or not facts_.established(timing)
    held = _id(session)
    of_family = held is None or c.link.route is catalogue.LinkRoute.UNRECONCILED or facts_.possibly(
        _fact(R, held, _A.KIND), c.link.family)
    return unplaced and of_family and facts_.possibly(timing, DateRelation.ON_DATE_OF_SERVICE)


@dataclass(frozen=True, slots=True)
class Excluded:
    """The exclusion's answer for one group (4.6): the Exclusion that excludes the code, else the item that holds it (a
    statement_scope question, or None for 7.6's not documented)."""
    exclusion: Exclusion | None
    item: HeldFact | None


def _scope(R: FactSet, statement: Id, kept: Sequence[Span]) -> HeldFact:
    spans = tuple(sorted(set(_anchor(R, statement)) | set(kept)))
    return _held(rq.fact_key(_SCOPE.fact), _SCOPE.rank, _Q, _A.SCOPE_BREADTH, statement, None,
                 questions.coding_rule(_Rule.STATEMENT_SCOPE), spans)


def _exclusion(c: _Code, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
               kept_words: Sequence[Span] | None, evidence_doubted: bool = False) -> Excluded:
    """4.6 (module docstring), over every statement in pass 1's order: the first that meets conditions 1-5 excludes.
    ``evidence_doubted``: an unlisted unit lies on the code's kept evidence (3.2.6 rule 2, ``on_evidence``), which holds
    the code - so a citation is asked, never decided, as beside any doubt (unlisted entries never exclude: 3.2.6)."""
    in_doubt = evidence_doubted or doubted(R, group)
    scope: HeldFact | None = None
    for statement in R.events:
        if _concerns(c, group, R, statement):
            decided = deciding(R, statement)
            covered = cover(R, statement, kept, kept_words)
            if decided is not None and not_exceptive(R, statement):
                if covered is Covered.CITATION and not in_doubt:
                    anchor = R.anchors.get(statement)
                    return Excluded(Exclusion(event=statement, fact=decided, cover=Cover.CITATION,
                                              anchor=tuple(sorted(set(anchor.units))) if anchor is not None else ()),
                                    None)
                if covered is not Covered.NONE and scope is None:
                    scope = _scope(R, statement, kept)
            if covered is Covered.NONE and broad(c, group, R, statement) and scope is None:
                scope = _scope(R, statement, kept)
        if scope is None and possibly_here(c, group, R, statement):
            scope = _scope(R, statement, kept)
    return Excluded(None, scope)


def exclusion(code: str, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
              kept_words: Sequence[Span] | None = None) -> Excluded:
    """4.6 for ``code``'s ``group`` (module docstring), with 3.2.6 rule 2's doubt on the kept evidence."""
    return _exclusion(_code(code), group, kept, R, kept_words, bool(on_evidence(kept, R)))


# --- the never-READY holds and not documented ---------------------------------------------------------------------------


def _code_level(rule: questions.Rule, kind: ItemKind, kept: Sequence[Span]) -> HeldFact:
    """A hold about no single fact (D189: attribute, subject and result None): performed_status at the status row."""
    return _held(rq.fact_key(_STATUS.fact), _STATUS.rank, kind, None, None, None, questions.coding_rule(rule),
                 tuple(sorted(set(kept))))


def on_evidence(kept: Sequence[Span], R: FactSet) -> tuple[UnlistedStatement, ...]:
    """3.2.6 rule 2: every kept unlisted entry - an act, a denial or a doubt - one of whose units one of the code's kept
    spans overlaps, in FactSet.unlisted's order. 3.2.6's own case: "The existing biliary stent was removed and replaced
    with a new plastic stent." with only the placement filed and pass 2's unlisted removal kept; 43274, citing that
    sentence, is held - never READY for what may be an exchange (the refutation's D1)."""
    return tuple(entry for entry in R.unlisted
                 if any(_overlaps(span, unit) for span in kept for unit in entry.units))


def _evidence_hold(entry: UnlistedStatement, R: FactSet, supporting: Sequence[Id]) -> HeldFact:
    """3.2.6 rule 2's hold: performed_status at RANK 2 ("an unlisted unit on its evidence", h2), a question quoting the
    unlisted unit, cause unlisted; about no single fact (D189: attribute and result None). Its subject, the act its item
    names: the first supporting act whose anchor shares a unit with the entry, else None (the item then names the
    group's bound act, else the first supporting act, else the code's own kind)."""
    units = tuple(sorted(set(entry.units)))
    subject = next((event for event in supporting
                    if any(_overlaps(unit, own) for unit in units for own in _anchor(R, event))), None)
    return _held(rq.fact_key(_DOUBT.fact), _DOUBT.rank, _Q, None, subject, None, questions.UNLISTED, units)


# --- decide (4.4) -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Group:
    kinds: tuple[Kind, ...]
    supports: tuple[Support, ...]
    supporting: tuple[Id, ...]
    positive: tuple[Support, ...]


@dataclass(frozen=True, slots=True)
class _Decided:
    evaluation: Evaluation
    groups: tuple[_Group, ...]


def _decide(code: str, kept: Sequence[Span], R: FactSet, kept_words: Sequence[Span] | None) -> _Decided:
    c = _code(code)
    link = c.link
    groups_ = catalogue.requirements(link)
    if not link.linked or not groups_:
        rule = (_Rule.NOT_LINKED if link.reason is catalogue.NoRouteReason.FAMILY_MISMATCH else _Rule.UNPROFILED)
        return _Decided(Evaluation((), (_code_level(rule, _E, kept),), {}), ())
    if catalogue.recognised_only(link):
        return _Decided(Evaluation((), (_code_level(_Rule.RECOGNISED_ONLY, _E, kept),), {}), ())
    supporting: list[Id] = []
    held: list[HeldFact] = []
    bindings: dict[tuple[Kind, ...], Id] = {}
    decided: list[_Group] = []
    acts: list[tuple[tuple[Kind, ...], Id]] = []
    evidence = on_evidence(kept, R)  # 3.2.6 rule 2: an unlisted unit on the kept evidence holds the code
    for group in groups_:
        supports = tuple(_support(c, group, R, event) for event in candidates(R, group))
        found = [entry.event for entry in supports if entry.met]
        pending = [entry for entry in supports if not entry.met and positive(R, entry.event)]
        if Kind.STENT_EXCHANGE in group and c.has(Tag.XCHG) and not found:
            pairs, waiting = _pairs(c, R)
            found += [event for pair in pairs for event in pair]
            pending += waiting
        if found:
            supporting += [event for event in found if event not in supporting]
            acts += [(group, event) for event in found]
            decided.append(_Group(group, supports, tuple(found), ()))
            continue
        if pending:
            for entry in pending:
                held.extend(entry.witnesses)
            bindings[group] = questions.choose(kept, [questions.Candidate(entry.event, entry.witnesses, entry.unmet)
                                                      for entry in pending], R)
            decided.append(_Group(group, supports, (), tuple(pending)))
            continue
        excluded = _exclusion(c, group, kept, R, kept_words, bool(evidence))
        if excluded.exclusion is not None:
            return _Decided(Evaluation((), (), {}, exclusion=excluded.exclusion), ())
        held.append(excluded.item if excluded.item is not None else _code_level(_Rule.NOT_DOCUMENTED, _Q, kept))
        decided.append(_Group(group, supports, (), ()))
    for group, event in acts:  # 4.4's code_requirements over every supporting act: no early return before them (Q2)
        held.extend(witness for row in _code_rows(c, group, R, event) for witness in row.witnesses)
    held.extend(_evidence_hold(entry, R, supporting) for entry in evidence)
    if c.template is Template.ROUTE_B:  # D197: route (b) is never READY; its one item
        held.append(_code_level(_Rule.ROUTE_B, _E, kept))
    return _Decided(Evaluation(tuple(supporting), tuple(dict.fromkeys(held)), bindings), tuple(decided))


def decide(code: str, kept: Sequence[Span], R: FactSet, *, kept_words: Sequence[Span] | None = None) -> Evaluation:
    """4.4's outcome function for ``code`` with its kept evidence spans ``kept`` (R1 already passed) over the settled
    FactSet ``R`` (facts.effective's, L1 re-judged): Evaluation(supporting, held_facts, bindings, exclusion) - module
    docstring. ``kept_words``: the letter-or-digit runs of the kept spans for C-10 (``cover``), None for the
    fail-closed reading. Pure: identical inputs give an identical Evaluation."""
    return _decide(code, kept, R, kept_words).evaluation


def code_facts(code: str, group: Sequence[Kind] = ()) -> questions.CodeFacts:
    """What an item names of ``code`` (questions.CodeFacts): its family, the group's kinds (by default the kinds the
    code accounts for, catalogue.accounted - called, never forked: step 1e's hand-off #5) and its row's technique, site,
    EUS class and tract."""
    c = _code(code)
    kinds = tuple(group) or catalogue.accounted(c.link)
    row = c.spec.row
    return questions.CodeFacts(code=code, family=c.link.family, group=kinds,
                               technique=row.technique if row is not None else None,
                               site=row.site if row is not None else None,
                               exam_class=row.eus_class if row is not None else None,
                               tract=row.tract if row is not None else None)


def groups(code: str, kept: Sequence[Span], R: FactSet, evaluation: Evaluation,
           kept_words: Sequence[Span] | None = None) -> tuple[questions.Group, ...]:
    """Each held group of ``evaluation`` as the item reads it (questions.Group): its positive candidates with their
    witnesses, recomputed (decide is pure), and its binding."""
    out: list[questions.Group] = []
    for group in _decide(code, kept, R, kept_words).groups:
        if group.positive:
            out.append(questions.Group(group.kinds, tuple(questions.Candidate(entry.event, entry.witnesses,
                                                                              entry.unmet)
                                                          for entry in group.positive),
                                       evaluation.bindings.get(group.kinds)))
    return tuple(out)


def item(code: str, kept: Sequence[Span], R: FactSet, evaluation: Evaluation, extra: Sequence[HeldFact] = (),
         kept_words: Sequence[Span] | None = None) -> questions.Item | None:
    """The ONE item of a held code (4.8, D182): questions.item over ``evaluation``'s held facts and ``extra`` (the R6
    facts, the class and code checks, the combination holds assess appends, 4.4), with the groups' bindings. None when
    nothing is held (an excluded or a READY code)."""
    found = groups(code, kept, R, evaluation, kept_words)
    held = tuple(dict.fromkeys((*evaluation.held_facts, *extra)))
    return questions.item(held, found, code_facts(code), R, evaluation.supporting)
