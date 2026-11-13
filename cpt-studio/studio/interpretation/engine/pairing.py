"""Statements against acts: the pairing table (docs/gemini-migration/FINAL-V2.md 4.5, with 4.2, 4.10, 4.11 and 3.2.6
rule 4; step 3d of 8.1; DECISIONS D188 and D191). Which statements pair with which acts, each of 4.5's six rows evaluated
on settled facts, and each pair's relation - INDEPENDENT, UNRESOLVED(row), CONTRADICTION or DOUBT - with the item 4.8
ranks it at. The forked rules read it: SUPPORT's clean requirement (4.3 row 8, step 4a), an exclusion's "no DOUBT
relation" (4.6 condition 5) and the doubted acts (4.7, step 4b).

**Which pairs** (4.5 [R:HO-1][R:HO-3][R:HO-5]). A statement D is an event whose status is established negated; or whose
status is not established (a POSSIBLE statement: the reading that it was not done is open, 4.2); or whose effective date
relation or performer is established as another (supported earlier_date or later_date, supported other_clinician or
other_facility, or the documenting team's value negated). D pairs with every OTHER event A for which ``possibly(A.status,
performed)`` and whose kind is compatible with D's: some kind D may be (facts.possibly_of_family: a statement whose kind is
not established may be every kind of its session's family, every kind when the session is not established either, over
requirements_table.FAMILY_KINDS, DECISIONS D191) concerns some kind A may be (facts.possibly: its claimed value, its
options, its control's sibling; every kind when silent) by catalogue.covers: the same kind, a tattoo with an injection, or
D's umbrella covering A's kind. A clip or an injection whose purpose may be hemostasis (facts.possibly) may also be the
bleeding control the catalogue reads it as (catalogue.catalogue_kind; D157's doubt, kept as a rule over facts by 4.13):
the step's NOTES record this reading (question Q1, request R1).

**The rows** (4.5), each INDEPENDENT, UNRESOLVED or SAME, every one evaluated [R:HO-2]:
- session (C-8): INDEPENDENT when both sessions are established (supported) and different; UNRESOLVED when either is not
  established while two or more sessions of a compatible family exist (a session whose kind is not established, or
  whose family's FAMILY_KINDS holds a kind the pair shares); SAME otherwise.
- timing: the effective date relations (the stored per-act facts, inheritance applied by settle, L1 re-judged when the
  caller passes facts.effective's FactSet). INDEPENDENT when both are established and different, SAME when both are
  established and equal, UNRESOLVED otherwise. "Established" reads a negated value as every other value of its
  enumeration, so two established facts differ when their value sets are disjoint, are equal when both are one and the
  same value, and are neither (UNRESOLVED) when they overlap otherwise; the performer and technique rows read it so too.
- performer: "D's own statement names a performer" is D's performer fact not silent and not inherited (DECISIONS D188).
  When it names none the row is SAME: a general denial covers any performer, and a performer D would only inherit
  from its section never narrows it. When it names one: INDEPENDENT when both are established and of different
  classes, or both other_clinician with different established persons (D's person its own); SAME when both are
  established and equal (two other_clinician the same established person); UNRESOLVED otherwise.
- breadth: an act-filed possible statement (its status claim not negated, its status not established) has no breadth
  (4.5 [R:HO-3]): SAME, the target row decides. Otherwise D's breadth established exceptive with A among its
  established excepts is INDEPENDENT; a breadth not established (an act established as of another date or performer
  carries none, K1, and so is UNRESOLVED here), an exceptive breadth that possibly names A without establishing it, or
  one that does not name A while A's status is established (a "no other" against an act it does not except), is
  UNRESOLVED; SAME otherwise (all_of_kind within D's session, which the session row reads; single, listed or segment,
  which the target row reads).
- target: D's breadth established all_of_kind or exceptive leaves the target out of it (SAME). An act whose claimed kind
  has no target (requirements.TARGET_KINDS: a visit, prolonged visit time, moderate sedation, other) is read for no
  target fact, and the row is UNRESOLVED, as for an unknown target. Otherwise D's target is: for single_target, and for
  an act-filed statement (a possible statement filed as an act, or an act established as of another date or performer:
  it has no breadth, and its own target stands for a single target, 4.5 [R:HO-3]), its target.lesion and target.places,
  set apart by facts.apart_by_lesion or facts.apart_by_place (FINAL-V2 4.2: established, different or disjoint, the pair
  controls rejected in both directions [R:SC-B]; for an act-filed statement too, where 4.5's paragraph says "without
  pair controls": the step's questions Q2 and Q3); for listed_targets, its scope.targets (with any target lesion and
  places); for segment, its scope.segment's whole range (segment_range: the two places and every place between them,
  the range contract/claims.py's controls avoid, D196) with any target places - the arbiter triage's hand-off 2d#6 -
  each set apart by the same rule over the whole set: the act asked about EVERY place of the statement's place set
  (its target places and the segment's whole range, not only the segment's two places: 3.2.3's "each place of one
  object outside the other's places", the set the disjointness is judged on) and the statement about every place of
  the act, each control rejected. An interior place of the range that no control asks is an omitted place (4.11), so
  the row is UNRESOLVED until contract/claims.py asks it (the step's request R4). A lesion possibly the same as the
  act's (same_as, in any state that leaves it possible) is never set apart by lesion, in any mode: same_as only joins
  (3.2.3's UNCONTROLLED), and read by possibly, weakening it never releases (P-MONO). A statement-filed event whose
  breadth is not established is set apart by nothing. Otherwise SAME when the same lesion (equal ids, or same_as
  supported) or overlapping places (engine/anatomy.compatible) are established on both sides, and UNRESOLVED: an
  unknown target never proves independence (4.11).
- technique (C-16): when D names no device (its device fact silent), SAME. Otherwise UNRESOLVED unless both devices are
  established; INDEPENDENT when the devices D's statement concerns and the devices A may have used are disjoint, SAME
  when A's are among D's, UNRESOLVED otherwise. A device covers its own kinds (DEVICE_CONTAINS, v1's relations table by
  value: a snare covers the cold and the hot snare, forceps the cold and the hot forceps), so a snare is never "another
  device" than a cold snare, and two "other" devices are never the same one.

**The relation** (4.5): INDEPENDENT when at least one row proves it, unless the pair is ``claimed`` (D's scope.covers
names A, in any state), which is UNRESOLVED instead - Gemini says D applies to A while the facts say apart, and the
disagreement is asked (statement_scope). Otherwise UNRESOLVED on the first unresolved row in 4.5's order. Otherwise
(every row SAME) CONTRADICTION when D's status is established negated and A's is established performed, else DOUBT.
``item`` gives each hold its RANK row (4.8; requirements.RULES' clean row asks exactly these): a CONTRADICTION rank 1
(conflict:<kind>), a DOUBT rank 2 (performed_status), an UNRESOLVED relation the row's fact - session ``procedure``,
timing ``event_time``, performer ``event_performer``, technique ``technique``, breadth and target ``statement_scope``
- ``statement_scope`` for a claimed pair a row set apart (4.5 step 1: the only claimed pair 4.5 turns into
UNRESOLVED(statement_scope); a claimed pair with no INDEPENDENT row is UNRESOLVED on its first unresolved row by step 2
and asks that row's fact), and ``statement_scope`` for every possible statement. ``cause`` is 4.4's
``relation:<type>`` (``relation:possible_statement`` for a possible statement, 3.7), ``unlisted`` for an unlisted pair.

**Unlisted statements** (3.2.6 rule 4): an unlisted denial or doubt pairs UNRESOLVED(statement_scope) with every
possibly-positive act (possibly performed or attempted_not_completed, 4.4) of a kind its kind covers, possibly in its
session; with no kind, with every such act possibly in its session; with no session, of every session. An unlisted act
pairs with nothing here (its rules are 3.2.6 rules 3 and 5).

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, requirements and types only - no retired v1 module, none of
contract's text modules - holds no word, phrase or marker list (every module-level collection holds enumeration members
or is computed from them), reads no text and returns no document string (``cause`` returns CPT Studio's code for a hold's
owner). ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation.contract.types import (Attribute, Breadth, DateRelation, Device, FactState, Kind, Landmark,
                                                  Performer, Purpose, Result, SessionKind, Status, UnlistedWhat)
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import Fact, FactSet, Id, Span, UnlistedStatement, Value

_E = TypeVar('_E', bound=Enum)
_A = Attribute


# --- the relation's vocabulary (FINAL-V2 4.5) --------------------------------------------------------------------------


@unique
class Row(Enum):
    """The rows of 4.5's pairing table, in its order (the order an UNRESOLVED relation names its first unresolved row
    in)."""
    SESSION = 'session'
    TIMING = 'timing'
    PERFORMER = 'performer'
    BREADTH = 'breadth'
    TARGET = 'target'
    TECHNIQUE = 'technique'


@unique
class RowResult(Enum):
    """What one row says of a pair (4.5's three columns): INDEPENDENT (an established difference: D does not concern A
    on this row), UNRESOLVED (the facts cannot tell), SAME (D concerns A on this row, as far as the facts go)."""
    INDEPENDENT = 'independent'
    UNRESOLVED = 'unresolved'
    SAME = 'same'


@unique
class Relation(Enum):
    """A pair's relation (4.5): INDEPENDENT (D does not concern A), UNRESOLVED (whether it does is asked), CONTRADICTION
    (an established denial covers an established act), DOUBT (D covers A, and D is doubted or possible, or A's status is
    not established)."""
    INDEPENDENT = 'independent'
    UNRESOLVED = 'unresolved'
    CONTRADICTION = 'contradiction'
    DOUBT = 'doubt'


@dataclass(frozen=True, slots=True)
class Pair:
    """One statement against one act (4.5), text-free. statement, act: the two events. relation: the pair's Relation.
    row: for INDEPENDENT the first row proving it, for UNRESOLVED the first unresolved row; None for a claimed pair
    turned UNRESOLVED, a CONTRADICTION and a DOUBT. rows: every row's result, in 4.5's order (each row is evaluated,
    [R:HO-2]). claimed: D's scope.covers names A. possible: D is a possible statement (its status not established).
    kinds: the act kinds through which D concerns A (A's possible kinds D's kinds cover; 4.8's conflict:<kind> names
    one). spans: both statements' anchor units, each once, in document order - the hold quotes both (4.5)."""
    statement: Id
    act: Id
    relation: Relation
    row: Row | None
    rows: tuple[tuple[Row, RowResult], ...]
    claimed: bool
    possible: bool
    kinds: frozenset[Kind]
    spans: tuple[Span, ...]

    def result(self, row: Row) -> RowResult:
        """The result of ``row`` for this pair."""
        return dict(self.rows)[row]


@dataclass(frozen=True, slots=True)
class UnlistedPair:
    """An unlisted denial or doubt against an act (3.2.6 rule 4): always UNRESOLVED(statement_scope). index: the
    entry's place in FactSet.unlisted; statement: the entry; act: the event; spans: the entry's units and the act's
    anchor units, each once, in document order."""
    index: int
    statement: UnlistedStatement
    act: Id
    spans: tuple[Span, ...]

    @property
    def relation(self) -> Relation:
        """UNRESOLVED: an unlisted statement never supports, excludes or releases anything (3.2.6)."""
        return Relation.UNRESOLVED


# --- the tables (module docstring) -------------------------------------------------------------------------------------

# A device's own kinds (v1's relations.DEVICE_CONTAINS, by value; tests/v2/test_pairing.py proves it equal): a snare
# covers the cold and the hot snare, forceps the cold and the hot forceps.
DEVICE_CONTAINS: Mapping[Device, frozenset[Device]] = MappingProxyType({
    Device.SNARE: frozenset({Device.COLD_SNARE, Device.HOT_SNARE}),
    Device.FORCEPS: frozenset({Device.COLD_FORCEPS, Device.HOT_FORCEPS}),
})
# The other date relations and performers (reading.OTHER_DATES and OTHER_PERFORMERS): a statement's "established as
# another" (4.5), and the documenting values whose negation establishes another.
OTHER_DATES: frozenset[DateRelation] = frozenset({DateRelation.EARLIER_DATE, DateRelation.LATER_DATE})
OTHER_PERFORMERS: frozenset[Performer] = frozenset({Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY})
# The breadths whose target the target row reads (4.5), and those that leave the target out of the statement.
TARGETED: frozenset[Breadth] = frozenset({Breadth.SINGLE_TARGET, Breadth.LISTED_TARGETS, Breadth.SEGMENT})
UNTARGETED: frozenset[Breadth] = frozenset({Breadth.ALL_OF_KIND, Breadth.EXCEPTIVE})
# 4.4's positive: a status that says the act was done, or begun (3.2.6 rule 4's "possibly-positive").
POSITIVE: tuple[Status, ...] = (Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED)


def _tract_order() -> tuple[Landmark, ...]:
    """LANDMARKS2's places in the order a segment's whole range is read in (DECISIONS D196): a walk of engine/anatomy's
    containment, each place right after the narrowest place that holds it, the places one place holds in LANDMARKS2's
    order (v1's, the tract's). The rule contract/claims.py's TRACT_ORDER states, computed here over engine/anatomy's
    tables because the engine imports no claim builder; tests/v2/test_pairing.py proves the two equal (request R2 moves
    both into engine/anatomy.py)."""
    listed = {place: position for position, place in enumerate(Landmark)}

    def narrowest(place: Landmark) -> Landmark | None:
        holders = [outer for outer in Landmark if place in anatomy.CONTAINS[outer]]
        return min(holders, key=lambda outer: (len(anatomy.CONTAINS[outer]), listed[outer]), default=None)

    held: dict[Landmark | None, list[Landmark]] = {}
    for place in Landmark:
        held.setdefault(narrowest(place), []).append(place)
    order: list[Landmark] = []

    def walk(place: Landmark) -> None:
        order.append(place)
        for inner in held.get(place, []):
            walk(inner)

    for outer in held.get(None, []):
        walk(outer)
    return tuple(order)


TRACT_ORDER: tuple[Landmark, ...] = _tract_order()
_PLACE_ORDER: Mapping[Landmark, int] = MappingProxyType({place: position for position, place in enumerate(TRACT_ORDER)})


def segment_range(first: Landmark, last: Landmark) -> frozenset[Landmark]:
    """A segment's whole range (DECISIONS D196; contract/claims.segment_range's rule), whichever end the segment names
    first: its two places, and every place between them in TRACT_ORDER all of whose places (engine/anatomy.CONTAINS)
    are between them too. A place between them that holds one beyond an end reaches outside the segment and is left
    out; a place holding it holds a place of the range too, so it overlaps the segment through that place."""
    one, other = sorted((_PLACE_ORDER[first], _PLACE_ORDER[last]))

    def between(place: Landmark) -> bool:
        return one <= _PLACE_ORDER[place] <= other

    return frozenset(place for place in TRACT_ORDER if between(place) and (
        place is first or place is last or all(between(inner) for inner in anatomy.CONTAINS[place])))


# --- reading one fact --------------------------------------------------------------------------------------------------


def _values(found: Fact, domain: type[_E]) -> frozenset[_E] | None:
    """The values an established fact leaves possible: its value when supported, every other value of ``domain`` when
    negated; None when the fact is not established (or holds no value of ``domain``)."""
    value = found.value
    if not isinstance(value, domain):
        return None
    if found.result is Result.SUPPORTED:
        return frozenset({value})
    if found.result is Result.NEGATED:
        return frozenset(member for member in domain if member is not value)
    return None


def _compare(first: frozenset[_E] | None, second: frozenset[_E] | None) -> RowResult:
    """Two established value sets: INDEPENDENT when disjoint, SAME when both are the same single value, UNRESOLVED
    otherwise (a side not established, or the two overlapping without being one value)."""
    if first is None or second is None:
        return RowResult.UNRESOLVED
    if not first & second:
        return RowResult.INDEPENDENT
    if len(first) == 1 and first == second:
        return RowResult.SAME
    return RowResult.UNRESOLVED


def _supported_id(found: Fact) -> Id | None:
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def _own(found: Fact) -> bool:
    """The fact is the event's own statement: not silent and not inherited from a section (DECISIONS D188)."""
    return not facts_.silent(found) and found.inherited_from is None


# --- which pairs (FINAL-V2 4.5) ----------------------------------------------------------------------------------------


def possible(R: FactSet, event: Id) -> bool:
    """A POSSIBLE statement (4.5 [R:HO-1][R:HO-3]): the event's status is not established - doubted, contradicted,
    failed, unappraised or not supported by pass 2 - so the reading that it was not done is open (4.2)."""
    return not facts_.established(facts_.fact(R, event, _A.STATUS))


def filed_as_statement(R: FactSet, event: Id) -> bool:
    """Pass 1 filed the event as a statement: its status claim is negated (CLAIMED's statement class, 3.2.1). Every
    other filing - a supported status claim, a contradicted one, a silent one - is act-filed."""
    return facts_.fact(R, event, _A.STATUS).state is FactState.NEGATED


def other_date(R: FactSet, event: Id) -> bool:
    """The event's effective date relation is established as another date: supported earlier_date or later_date, or
    on_date_of_service negated."""
    values = _values(facts_.fact(R, event, _A.DATE_RELATION), DateRelation)
    return values is not None and DateRelation.ON_DATE_OF_SERVICE not in values


def other_performer(R: FactSet, event: Id) -> bool:
    """The event's effective performer is established as another: supported other_clinician or other_facility, or
    documenting_team negated."""
    values = _values(facts_.fact(R, event, _A.PERFORMER), Performer)
    return values is not None and Performer.DOCUMENTING_TEAM not in values


def is_statement(R: FactSet, event: Id) -> bool:
    """4.5's "which pairs", the statement side: the event's status established negated; or not established (a possible
    statement); or its effective date relation or performer established as another."""
    status = facts_.fact(R, event, _A.STATUS)
    return (status.result is Result.NEGATED or not facts_.established(status) or other_date(R, event)
            or other_performer(R, event))


def statements(R: FactSet) -> tuple[Id, ...]:
    """Every statement of the FactSet (is_statement), in pass 1's order."""
    return tuple(event for event in R.events if is_statement(R, event))


def _catalogue_reading(R: FactSet, event: Id, kinds: frozenset[Kind]) -> frozenset[Kind]:
    """``kinds`` with the bleeding control the catalogue reads a clip or an injection as when its purpose is hemostasis
    (catalogue.catalogue_kind), read by possibly: a clip or an injection whose purpose is not established may be a
    bleeding control (D157's doubt, kept as a rule over facts: FINAL-V2 4.13). Module docstring; the step's question
    Q1."""
    if kinds & catalogue.HEMOSTASIS_KINDS and facts_.possibly(facts_.fact(R, event, _A.PURPOSE), Purpose.HEMOSTASIS):
        return kinds | {Kind.BLEEDING_CONTROL}
    return kinds


def act_kinds(R: FactSet, act: Id) -> frozenset[Kind]:
    """Every kind ``act`` may be on the act side of a pair: facts.possibly on its kind (its claimed value, its options,
    its control's sibling; every kind when silent: 4.2's candidate arm), with the catalogue's bleeding-control reading
    (a clip or an injection that may be for hemostasis may be a bleeding control)."""
    return _catalogue_reading(R, act, facts_.possible_kinds(R, act, of_family=False))


def statement_kinds(R: FactSet, statement: Id) -> frozenset[Kind]:
    """Every kind ``statement`` may be on the statement side of a pair: facts.possibly_of_family on its kind - a kind
    not established is every kind of its session's family (requirements_table.FAMILY_KINDS, DECISIONS D191), every kind
    when the session is not established either [R:HO-5]. A statement's purpose is never claimed (3.2.1), so the
    catalogue's reading adds nothing here."""
    return facts_.possible_kinds(R, statement, of_family=True)


def shared_kinds(R: FactSet, statement: Id, act: Id) -> frozenset[Kind]:
    """The act kinds through which ``statement`` concerns ``act``: each kind the act may be that a kind the statement may
    be covers (catalogue.covers: the same kind, a tattoo with an injection, an umbrella covering its member). Empty:
    their kinds are not compatible."""
    kinds = statement_kinds(R, statement)
    return frozenset(kind for kind in act_kinds(R, act) if any(catalogue.covers(own, kind) for own in kinds))


def paired(R: FactSet, statement: Id, act: Id) -> bool:
    """Whether ``statement`` pairs with ``act`` (4.5): two different events, the first a statement (is_statement), the
    second possibly performed (facts.possibly on its status: a status not established leaves every status possible),
    their kinds compatible (shared_kinds)."""
    return (statement != act and is_statement(R, statement)
            and facts_.possibly(facts_.fact(R, act, _A.STATUS), Status.PERFORMED)
            and bool(shared_kinds(R, statement, act)))


# --- the rows (FINAL-V2 4.5) -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Context:
    statement: Id
    act: Id
    filed: bool  # the statement's status claim is negated
    possible: bool  # the statement's status is not established
    kinds: frozenset[Kind]  # shared_kinds


def _context(R: FactSet, statement: Id, act: Id) -> _Context:
    return _Context(statement=statement, act=act, filed=filed_as_statement(R, statement),
                    possible=possible(R, statement), kinds=shared_kinds(R, statement, act))


def _compatible_sessions(R: FactSet, kinds: frozenset[Kind]) -> int:
    """How many sessions may hold an act of the pair's kinds: a session whose kind is not established (any family), or
    whose family's kinds (FAMILY_KINDS, DECISIONS D191) hold one of ``kinds``."""
    count = 0
    for session in R.sessions:
        kind = facts_.fact(R, session, _A.KIND)
        family = kind.value if kind.result is Result.SUPPORTED and isinstance(kind.value, SessionKind) else None
        if family is None or facts_.family_kinds(family) & kinds:
            count += 1
    return count


def _session_row(R: FactSet, p: _Context) -> RowResult:
    """C-8: both sessions established and different; UNRESOLVED when either is not established while two or more
    sessions of a compatible family exist; SAME otherwise."""
    one = _supported_id(facts_.fact(R, p.statement, _A.SESSION))
    other = _supported_id(facts_.fact(R, p.act, _A.SESSION))
    if one is not None and other is not None:
        return RowResult.SAME if one == other else RowResult.INDEPENDENT
    return RowResult.UNRESOLVED if _compatible_sessions(R, p.kinds) >= 2 else RowResult.SAME


def _timing_row(R: FactSet, p: _Context) -> RowResult:
    """Both effective date relations established and different: INDEPENDENT; equal: SAME; either not established:
    UNRESOLVED."""
    return _compare(_values(facts_.fact(R, p.statement, _A.DATE_RELATION), DateRelation),
                    _values(facts_.fact(R, p.act, _A.DATE_RELATION), DateRelation))


def _performer_row(R: FactSet, p: _Context) -> RowResult:
    """4.5's performer row (module docstring): a general denial covers any performer."""
    own = facts_.fact(R, p.statement, _A.PERFORMER)
    if not _own(own):
        return RowResult.SAME
    one = _values(own, Performer)
    other = _values(facts_.fact(R, p.act, _A.PERFORMER), Performer)
    found = _compare(one, other)
    if found is not RowResult.SAME or one != frozenset({Performer.OTHER_CLINICIAN}):
        return found
    person = facts_.fact(R, p.statement, _A.PERFORMER_PERSON)
    first = _supported_id(person) if person.inherited_from is None else None
    second = _supported_id(facts_.fact(R, p.act, _A.PERFORMER_PERSON))
    if first is None or second is None:
        return RowResult.UNRESOLVED
    return RowResult.SAME if first == second else RowResult.INDEPENDENT


def _breadth_row(R: FactSet, p: _Context) -> RowResult:
    """4.5's breadth row (module docstring)."""
    if p.possible and not p.filed:
        return RowResult.SAME  # an act-filed possible statement has no breadth: the target row decides
    breadth = facts_.fact(R, p.statement, _A.SCOPE_BREADTH)
    if breadth.result is not Result.SUPPORTED or not isinstance(breadth.value, Breadth):
        return RowResult.UNRESOLVED
    if breadth.value is not Breadth.EXCEPTIVE:
        return RowResult.SAME
    excepts = facts_.members(R, p.statement, _A.SCOPE_EXCEPTS)
    if any(facts_.holds(member, p.act) for member in excepts):
        return RowResult.INDEPENDENT
    if any(facts_.possibly(member, p.act) for member in excepts):
        return RowResult.UNRESOLVED  # possibly excepted, not established
    if facts_.established(facts_.fact(R, p.act, _A.STATUS)):
        return RowResult.UNRESOLVED  # a "no other" against an act it does not except
    return RowResult.SAME


@unique
class _Mode(Enum):
    """How the target row reads D's target (module docstring)."""
    SINGLE = 'single'  # single_target, and an act-filed statement's own target: facts.apart_by_lesion, apart_by_place
    LISTED = 'listed'  # listed_targets: scope.targets
    SEGMENT = 'segment'  # segment: scope.segment's whole range
    NONE = 'none'  # nothing sets D apart by its target: a statement-filed event whose breadth is not established


_BY_BREADTH: Mapping[Breadth, _Mode] = MappingProxyType({
    Breadth.SINGLE_TARGET: _Mode.SINGLE, Breadth.LISTED_TARGETS: _Mode.LISTED, Breadth.SEGMENT: _Mode.SEGMENT})


@dataclass(frozen=True, slots=True)
class _Target:
    """One side's target as the target row reads it. lesions: every lesion of it when each is established (supported),
    None otherwise; known_lesions: the supported ones. places: its whole place set when established (a target places
    list every member established, one supported at least; a segment's two places supported, read as its whole range),
    None otherwise - the set its disjointness is judged on AND the set a pair control must ask the other object about,
    place by place (3.2.3; the refutation's F1: a segment asked only about its two ends left its interior unasked);
    known_places: the supported places (a segment's whole range when established, else its supported ends)."""
    lesions: frozenset[Id] | None
    known_lesions: frozenset[Id]
    places: frozenset[Landmark] | None
    known_places: frozenset[Landmark]


def _lesions(found: Sequence[Fact]) -> tuple[frozenset[Id] | None, frozenset[Id]]:
    known = frozenset(lesion for lesion in (_supported_id(item) for item in found) if lesion is not None)
    return (known if found and len(known) == len(found) else None), known


def _places(found: Sequence[Fact]) -> tuple[frozenset[Landmark] | None, frozenset[Landmark]]:
    """A place list's whole set when established (facts' _supported: every member established, the supported members'
    places, one at least) and its supported places."""
    known = frozenset(item.value for item in found
                      if item.result is Result.SUPPORTED and isinstance(item.value, Landmark))
    whole = known if found and all(facts_.established(item) for item in found) and known else None
    return whole, known


def _target(R: FactSet, event: Id, mode: _Mode) -> _Target:
    lesion = facts_.fact(R, event, _A.TARGET_LESION)
    lesion_facts = [] if facts_.silent(lesion) else [lesion]
    if mode is _Mode.LISTED:
        lesion_facts += list(facts_.members(R, event, _A.SCOPE_TARGETS))
    lesions, known_lesions = _lesions(lesion_facts)
    place_facts = facts_.members(R, event, _A.TARGET_PLACES)
    places, known_places = _places(place_facts)
    if mode is _Mode.SEGMENT:
        segment = facts_.members(R, event, _A.SCOPE_SEGMENT)
        ends = [item.value for item in segment if item.result is Result.SUPPORTED and isinstance(item.value, Landmark)]
        whole = segment_range(ends[0], ends[1]) if len(segment) == 2 and len(ends) == 2 else None
        known_places = known_places | (whole if whole is not None else frozenset(ends))
        places = None if whole is None or (place_facts and places is None) else (places or frozenset()) | whole
    return _Target(lesions=lesions, known_lesions=known_lesions, places=places, known_places=known_places)


def _same_lesion(R: FactSet, one: Id, other: Id) -> bool:
    """One lesion: the same id, or same_as supported in either lesion's list (it only joins, 3.2.3)."""
    return one == other or any(facts_.holds(member, other) for member in facts_.members(R, one, _A.SAME_AS)) or any(
        facts_.holds(member, one) for member in facts_.members(R, other, _A.SAME_AS))


def _possibly_same(R: FactSet, one: Id, other: Id) -> bool:
    """Possibly one lesion: the same id, or a same_as member in either lesion's list that possibly names the other
    (facts.possibly: supported, or not established with it as its claimed value or one of its options). The guard
    against setting such a pair apart by lesion: same_as is UNCONTROLLED because it only joins (3.2.3), so it may hold
    and never release, and read by possibly a weakened same_as still holds (P-MONO). The same lesion in SAME reads
    _same_lesion (established)."""
    return one == other or any(facts_.possibly(member, other) for member in facts_.members(R, one, _A.SAME_AS)) or any(
        facts_.possibly(member, one) for member in facts_.members(R, other, _A.SAME_AS))


def _distinct(R: FactSet, one: Id, other: Id) -> bool:
    """distinct_from supported between two lesions, in either lesion's list (facts.apart_by_lesion's arm)."""
    return any(facts_.holds(member, other) for member in facts_.members(R, one, _A.DISTINCT_FROM)) or any(
        facts_.holds(member, one) for member in facts_.members(R, other, _A.DISTINCT_FROM))


def _controls(R: FactSet, keys: Iterable[tuple[Id, Attribute, Value]]) -> bool:
    """The pair controls (3.2.3 [R:SC-B]) that set two targets apart: every one generated and rejected (a control that
    was not generated is not rejected: facts.apart_by_place's rule)."""
    return all(R.pair_controls.get(key) is True for key in keys)


def _disjoint(first: frozenset[Landmark] | None, second: frozenset[Landmark] | None) -> bool:
    """Both place sets established and disjoint on the anatomy chain, pairwise (engine/anatomy.disjoint)."""
    return (first is not None and second is not None
            and all(anatomy.disjoint(one, other) for one in first for other in second))


def _apart_by_lesions(R: FactSet, p: _Context, own: _Target, other: _Target) -> bool:
    """apart_by_lesion over a statement's lesion set (4.2): every lesion of both sides established, none of the
    statement's possibly the act's (_possibly_same), distinct_from supported from each, and the lesion pair controls
    (each object asked about the other's lesions)."""
    if own.lesions is None or other.lesions is None or len(other.lesions) != 1:
        return False
    (lesion,) = other.lesions
    if any(_possibly_same(R, mine, lesion) or not _distinct(R, mine, lesion) for mine in own.lesions):
        return False
    keys = [(p.act, _A.TARGET_LESION, mine) for mine in own.lesions]
    return _controls(R, keys + [(p.statement, _A.TARGET_LESION, lesion)])


def _apart_by_places(R: FactSet, p: _Context, own: _Target, other: _Target) -> bool:
    """apart_by_place over a statement's whole place set (4.2): both sets established and disjoint, and every place
    pair control rejected - the act asked about EVERY place of the statement's set (its target places and a segment's
    whole range, the set the disjointness is judged on), the statement asked about every place of the act: facts.
    apart_by_place's rule over that set. A place of the range no control asks leaves the pair apart by nothing (4.11:
    an omitted place is as unknown as a missing one)."""
    if own.places is None or other.places is None or not _disjoint(own.places, other.places):
        return False
    keys = [(p.act, _A.TARGET_PLACES, place) for place in own.places]
    keys += [(p.statement, _A.TARGET_PLACES, place) for place in other.places]
    return _controls(R, keys)


def _apart_by_own_lesion(R: FactSet, p: _Context) -> bool:
    """A single target set apart by lesion: facts.apart_by_lesion (4.2), unless the two lesions are possibly one
    (_possibly_same; the same guard as the listed and segment targets)."""
    if not facts_.apart_by_lesion(R, p.statement, p.act):
        return False
    one = _supported_id(facts_.fact(R, p.statement, _A.TARGET_LESION))
    other = _supported_id(facts_.fact(R, p.act, _A.TARGET_LESION))
    return one is not None and other is not None and not _possibly_same(R, one, other)


def _mode(R: FactSet, p: _Context) -> _Mode | None:
    """How the target row reads D's target; None when D's breadth established all_of_kind or exceptive leaves the
    target out of the statement. An act-filed statement (a possible statement filed as an act, or an act established
    as of another date or performer) has no breadth: its own target stands for a single target (4.5 [R:HO-3])."""
    if not p.filed:
        return _Mode.SINGLE
    breadth = facts_.fact(R, p.statement, _A.SCOPE_BREADTH)
    if breadth.result is Result.SUPPORTED and isinstance(breadth.value, Breadth):
        return None if breadth.value in UNTARGETED else _BY_BREADTH[breadth.value]
    return _Mode.NONE


def has_target(R: FactSet, act: Id) -> bool:
    """Whether the act's claimed kind has a target (requirements.TARGET_KINDS, DECISIONS D195): its lesion and places
    are claimed, so the target row reads them; an act of another kind is read for none (step 1f's hand-off)."""
    kind = facts_.fact(R, act, _A.KIND).value
    return isinstance(kind, Kind) and kind in rq.TARGET_KINDS


def _target_row(R: FactSet, p: _Context) -> RowResult:
    """4.5's target row (module docstring; 4.11)."""
    mode = _mode(R, p)
    if mode is None:
        return RowResult.SAME
    if not has_target(R, p.act):
        return RowResult.UNRESOLVED
    own, other = _target(R, p.statement, mode), _target(R, p.act, _Mode.SINGLE)
    if mode is _Mode.SINGLE:
        apart = _apart_by_own_lesion(R, p) or facts_.apart_by_place(R, p.statement, p.act)
    else:
        apart = mode is not _Mode.NONE and (_apart_by_lesions(R, p, own, other) or _apart_by_places(R, p, own, other))
    if apart:
        return RowResult.INDEPENDENT
    lesion = next(iter(other.lesions)) if other.lesions is not None and len(other.lesions) == 1 else None
    same = lesion is not None and any(_same_lesion(R, mine, lesion) for mine in own.known_lesions)
    overlap = any(anatomy.compatible(one, two) for one in own.known_places for two in other.known_places)
    return RowResult.SAME if same or overlap else RowResult.UNRESOLVED


def _devices(found: Fact) -> frozenset[Device] | None:
    """The devices an established device fact leaves possible, each device read with its own kinds
    (DEVICE_CONTAINS): supported, the device and its kinds; negated, every other device. None when not established."""
    value = found.value
    if not isinstance(value, Device):
        return None
    covered = frozenset({value}) | DEVICE_CONTAINS.get(value, frozenset())
    if found.result is Result.SUPPORTED:
        return covered
    if found.result is Result.NEGATED:
        return frozenset(device for device in Device if device not in covered)
    return None


def _technique_row(R: FactSet, p: _Context) -> RowResult:
    """C-16 (module docstring)."""
    own = facts_.fact(R, p.statement, _A.TECHNIQUE_DEVICE)
    if facts_.silent(own):
        return RowResult.SAME  # D names no device
    covered, used = _devices(own), _devices(facts_.fact(R, p.act, _A.TECHNIQUE_DEVICE))
    if covered is None or used is None:
        return RowResult.UNRESOLVED
    if not covered & used:
        return RowResult.INDEPENDENT
    return RowResult.SAME if used <= covered and Device.OTHER not in used else RowResult.UNRESOLVED


_ROWS: Mapping[Row, Callable[[FactSet, _Context], RowResult]] = MappingProxyType({
    Row.SESSION: _session_row, Row.TIMING: _timing_row, Row.PERFORMER: _performer_row, Row.BREADTH: _breadth_row,
    Row.TARGET: _target_row, Row.TECHNIQUE: _technique_row})


def row(R: FactSet, which: Row, statement: Id, act: Id) -> RowResult:
    """One row of 4.5 for ``statement`` against ``act`` (module docstring), whether or not the two pair."""
    return _ROWS[which](R, _context(R, statement, act))


def rows(R: FactSet, statement: Id, act: Id) -> tuple[tuple[Row, RowResult], ...]:
    """Every row of 4.5 for ``statement`` against ``act``, in 4.5's order: each is evaluated [R:HO-2]."""
    context = _context(R, statement, act)
    return tuple((which, _ROWS[which](R, context)) for which in Row)


# --- the relation (FINAL-V2 4.5) ---------------------------------------------------------------------------------------


def claimed(R: FactSet, statement: Id, act: Id) -> bool:
    """D's scope.covers names A (4.5 ``claimed``), in any state: a member whose value or one of whose options is A.
    covers is UNCONTROLLED because it can only turn INDEPENDENT into UNRESOLVED (3.2.3)."""
    return any(member.value == act or act in member.options
               for member in facts_.members(R, statement, _A.SCOPE_COVERS))


def _anchor_spans(R: FactSet, event: Id) -> tuple[Span, ...]:
    anchor = R.anchors.get(event)
    return anchor.units if anchor is not None else ()


def relation(R: FactSet, statement: Id, act: Id) -> Pair:
    """The pair's relation (4.5; module docstring). ValueError unless the two pair (``paired``)."""
    if not paired(R, statement, act):
        raise ValueError(f'{statement} does not pair with {act} (FINAL-V2 4.5).')
    context = _context(R, statement, act)
    results = tuple((which, _ROWS[which](R, context)) for which in Row)
    named = claimed(R, statement, act)
    independent = next((which for which, found in results if found is RowResult.INDEPENDENT), None)
    unresolved = next((which for which, found in results if found is RowResult.UNRESOLVED), None)
    found_row: Row | None
    if independent is not None:
        kind, found_row = (Relation.UNRESOLVED, None) if named else (Relation.INDEPENDENT, independent)
    elif unresolved is not None:
        kind, found_row = Relation.UNRESOLVED, unresolved
    elif (facts_.fact(R, statement, _A.STATUS).result is Result.NEGATED
          and facts_.holds(facts_.fact(R, act, _A.STATUS), Status.PERFORMED)):
        kind, found_row = Relation.CONTRADICTION, None
    else:
        kind, found_row = Relation.DOUBT, None
    spans = tuple(sorted(set(_anchor_spans(R, statement)) | set(_anchor_spans(R, act))))
    return Pair(statement=statement, act=act, relation=kind, row=found_row, rows=results, claimed=named,
                possible=context.possible, kinds=context.kinds, spans=spans)


def pairs_of(R: FactSet, act: Id) -> tuple[Pair, ...]:
    """Every statement paired with ``act``, each with its relation, in pass 1's order of the statements."""
    return tuple(relation(R, statement, act) for statement in R.events if paired(R, statement, act))


def pairs(R: FactSet) -> tuple[Pair, ...]:
    """Every pair of the FactSet: each statement against each act it pairs with, in pass 1's order (statement first)."""
    return tuple(relation(R, statement, act) for statement in R.events for act in R.events
                 if paired(R, statement, act))


# --- unlisted statements (FINAL-V2 3.2.6 rule 4) -----------------------------------------------------------------------


def positive(R: FactSet, act: Id) -> bool:
    """4.4's possibly-positive act: possibly performed or possibly attempted_not_completed (a status not established
    leaves both possible)."""
    status = facts_.fact(R, act, _A.STATUS)
    return any(facts_.possibly(status, value) for value in POSITIVE)


def unlisted_pairs(R: FactSet, act: Id) -> tuple[UnlistedPair, ...]:
    """Every kept unlisted denial or doubt pairing with ``act`` (3.2.6 rule 4; module docstring), in FactSet.unlisted's
    order: the act possibly positive, of a kind the entry's kind covers (any kind when the entry names none), possibly
    in the entry's session (any session when it names none)."""
    if not positive(R, act):
        return ()
    kinds = act_kinds(R, act)
    session = facts_.fact(R, act, _A.SESSION)
    out: list[UnlistedPair] = []
    for index, entry in enumerate(R.unlisted):
        if entry.what is UnlistedWhat.ACT:
            continue
        if entry.kind is not None and not any(catalogue.covers(entry.kind, kind) for kind in kinds):
            continue
        if entry.session is not None and not facts_.possibly(session, entry.session):
            continue
        spans = tuple(sorted(set(entry.units) | set(_anchor_spans(R, act))))
        out.append(UnlistedPair(index=index, statement=entry, act=act, spans=spans))
    return tuple(out)


# --- what a hold asks (FINAL-V2 4.5, 4.8) ------------------------------------------------------------------------------


_ROW_ITEMS: Mapping[Row, rq.Item] = MappingProxyType({
    Row.SESSION: rq.Item(rq.Rank.PROCEDURE, rq.FactKey.PROCEDURE),
    Row.TIMING: rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME),
    Row.PERFORMER: rq.Item(rq.Rank.PERFORMER, rq.FactKey.EVENT_PERFORMER),
    Row.BREADTH: rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE),
    Row.TARGET: rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE),
    Row.TECHNIQUE: rq.Item(rq.Rank.TECHNIQUE, rq.FactKey.TECHNIQUE),
})
_SCOPE = rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE)


def item(pair: Pair | UnlistedPair) -> rq.Item | None:
    """The item a pair's hold asks at its RANK row (4.5, 4.8): None for INDEPENDENT; a CONTRADICTION rank 1
    (conflict:<kind>, the kind from Pair.kinds); a DOUBT rank 2 (performed_status); an UNRESOLVED relation the row's
    fact (session: procedure; timing: event_time; performer: event_performer; technique: technique; breadth and target:
    statement_scope), and statement_scope for a claimed pair a row set apart (Pair.row None: 4.5 step 1), a possible
    statement (step 2's last sentence) and an unlisted pair. A claimed pair no row sets apart is step 2's UNRESOLVED on
    its first unresolved row, and asks that row's fact like any other pair (the refutation's F2)."""
    if isinstance(pair, UnlistedPair):
        return _SCOPE
    if pair.relation is Relation.INDEPENDENT:
        return None
    if pair.relation is Relation.CONTRADICTION:
        return rq.Item(rq.Rank.CONFLICT, rq.FactKey.CONFLICT)
    if pair.relation is Relation.DOUBT:
        return rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS)
    if pair.possible or pair.row is None:
        return _SCOPE
    return _ROW_ITEMS[pair.row]


def cause(pair: Pair | UnlistedPair) -> str | None:
    """The cause a pair's hold carries (4.4 HeldFact.cause, operator data that names no vendor): ``relation:<type>`` -
    ``relation:possible_statement`` for a possible statement (3.7, measured as G-NOISE), else the relation's value -
    and ``unlisted`` for an unlisted pair; None for INDEPENDENT."""
    if isinstance(pair, UnlistedPair):
        return 'unlisted'
    if pair.relation is Relation.INDEPENDENT:
        return None
    if pair.possible:
        return 'relation:possible_statement'
    return f'relation:{pair.relation.value}'
