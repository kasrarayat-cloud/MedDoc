"""Reading results (docs/gemini-migration/FINAL-V2.md 4.1, 4.2 and 1.7; step 2d of 8.1): the typed, text-free FactSet
the engine reads, built from one stored v2 EventInventory row, and the predicates every forked rule reads it through.

**The FactSet** (engine/types.FactSet). ``factset(inventory)`` reads the settled inventory as stored and
``effective(inventory, effective_date)`` reads it with L1 re-judged against the effective date (below). ``inventory``
is store.textfree_v2's view of a row store.load_v2 read (DECISIONS D188): its ``events``, in which every source's
located words are their offsets alone (``at``) and no text remains, so the builder reads no ``words`` or ``text``
record (FINAL-V2 5.7 measure 4: no such name in engine/, and no exception). Anything else - the StoredInventoryV2
itself, its events as stored, a located record holding more than its two offsets - is refused. Both give enumeration
members, ids, dates, results, reasons and integer spans only: every value is parsed into its attribute's domain (an
Enum of contract/types.py, an engine Id or an IsoDate).

A fact's ``spans`` are its sources' cited units, one span from the first unit's start to the last unit's end per
source, for wording. Its ``cited`` holds one Cited per source whose units the row has: the source's link, that units
span, and its located words' offsets (``at``; None when the source cites its whole units) - C-10 (4.6 condition 4)
reads D's statement-linked target and timing words as the ``at`` spans (the units span when there are none) of the
``statement`` sources of D's target and timing facts. Its ``inherited_from`` is the section an act's fact was inherited
from (claim.inherited_from; None for the act's own slot), so 4.5's performer row reads "D's own statement names a
performer" as a performer fact that is not silent and has no ``inherited_from``. Its ``counter`` holds the spans of the
evidence units of a contradicts or qualified verdict (3.2.5, quoted in the hold question; a supports verdict that names
a qualifier but approximate is read as qualified, DECISIONS D186 - approximate never lowers, D224), each once, in the
verdict's order. An anchor's ``units`` are its
units' spans and its kind and status words their located offsets. A single-valued slot is one Fact (a silent one is
state None, result unknown, reason silent: 3.3 row 3); a multi-valued attribute is one Fact per member, and an empty
list is no member, which a rule reads as unknown, never as an absence (P3). Each inherited fact is the stored per-act
fact (1.5, 3.3): settle has already applied the section's occasion, performer and owner, so ``fact(R, E,
DATE_RELATION)`` is E's effective date relation.

A fact's ``options`` are the values it leaves possible besides its claimed value, which ``possibly`` reads (4.2): a
contradicted fact's sides; the readings of every doubt that names its object (or, for an inherited fact, the section it
was taken from), parsed into its attribute's domain (a reading that is no value of that domain belongs to another
attribute of the object and is skipped); and the value of its contrary control when pass 2 did not reject it (3.2.3,
[R:HO-3]). An established fact has none. The doubt rule reads the objects a doubt names, not 1b's DOUBT_ATTRIBUTES row:
every reading so attached is one settle may have applied, so it can only widen what is possible, never narrow it.

**A session K3 demoted** (DECISIONS D244, question Q-N1 option (b)): an event's session fact that is not established and
carries ``session_unreachable`` - K3 found a place of the act in a region its claimed session's family cannot reach, and
nothing was moved (3.1 K3) - is possibly any session whose reach holds the act's place, not its claimed session alone.
The builder adds to that fact's options every other session of the row that may be of a family whose reach holds a place
the act may be at, as K3 reads a reach: catalogue.FAMILY_REACH, the regions a session of each family can reach
(DECISIONS D192), against engine/anatomy.region. A family the table does not list, and a place in no region, are judged
by no reach (K3 never demotes on them), so they hold it (the fail-closed reading: this repair's question R2D-K3). A
place the act may be at is a supported member's value or an open member's value and options (a negated member names
none), and a session is added when its reach holds ANY of them (question R2D-K3P); when no place is known (no member
names one, or a member that is not negated names none), every session's reach may hold it (P3). A session may be of its
supported kind, every other family when its kind is negated, and possibly's families otherwise. So ``possibly`` reads
the widened fact (and every rule that reads the fact's options reads the same sessions): "an EGD and a push enteroscopy;
on withdrawal, a polypectomy of a gastric body polyp" filed in the enteroscopy is possibly the EGD's act. The options
are fixed when the row is read: 9.4's weakenings, which act on the FactSet, leave them as they were, so a weakening
never narrows the sessions.

**An overfilled slot** (AMENDMENT-2 4.3.3, 4.4, adopted by DECISIONS D279 [R:truth-T1][R:truth-T2][R:truth-T5]
[R:truth-T9]): whenever one of the 38 single-valued slot attributes (``SLOTS``: every single-valued attribute of
DOMAINS but the required facts ``REQUIRED_FACTS``) holds more than one stored fact - a list at its key, which store.py
accepts for a gemini-inventory@3 row only and only when every one of them carries ``slot_overfull`` (4.3.6) - the
builder reads it as ONE Fact, the merged view (``_overfilled``): result unresolved, value None, state contradicted,
reason slot_overfull alone, its spans and cited sources every written fact's, ``options`` every value the slot's facts
wrote - each fact's claimed value and, for a fact pass 1 wrote contradicted, its sides - each once in written order,
supported or negated, followed by what each written fact read alone would leave possible besides (a doubt naming its
object, read as ``_fact`` reads one): never a value pass 1 did not write and never the attribute's domain; and
``negated_values`` the written values only denied - denied by a written fact, stated by none, and left possible by no
written fact read alone (a value one written fact denies and another states, or a doubt offers, is not only denied: the
claimed-value readers 4.3.3 c names read it as claimed, as each written fact read alone would - NOTES questions Q1 and
Q1R); a doubt offers every value it reads whenever it names the slot's object (the subject, or a section a written
fact inherits from), compared with the written values directly - a reading of the value every written fact writes and
denies included (DECISIONS D294 RD-1), so the exception D293 N2 rules (a manual ONLY denied) is a slot no doubt reads
the denied value of. Never the first written fact, never silence: ``silent`` is False for it, and ``holds``,
``denied`` and ``established`` are False, so nothing rests on it as established (4.4). Each reader kind of 4.3.3 reads
it, and since the two fields cannot carry what all three kinds need for a value written both stated and denied
(whether a written fact denies, for the possibility readers; whether one states, for the claimed-value readers), each
reads it at its fail-closed side (NOTES question Q1R): ``possibly`` (a) takes every written value as possible, and every
possibility reader that takes an unestablished denial as leaving every value open - ``possibly`` itself among them since
DECISIONS D294 RD-3 - takes EVERY merged view so (``open_denial``), whether or not a written fact denied a value - the
weakest of
its written facts read alone is never narrower; a reader
of what pass 1 STATED (b) reads nothing a merged view holds as stated (classes._claims), since it cannot tell a written
value from a doubt's reading, nor a value one written fact states from one another denies; a claimed-value reader (c)
reads each option not in ``negated_values`` as claimed (``claimed_values``). A written fact that carried K3's
``session_unreachable`` keeps the merged session view widened as that fact alone would be (below), and the literals of
an overfilled occasion are every written fact's, so its acts' inherited date relations are re-judged on all of them
(L1 only demotes). A list of fewer than two facts, a fact without ``slot_overfull``, or a list at a required fact or a
multi-valued attribute is refused (FactSetError), as store.py refuses it.

**The predicates** (4.2): ``holds``, ``denied``, ``established``, ``possibly`` - with the status arm: a status that is
not established leaves every status possible [R:HO-1][R:HO-3] - and ``possibly_of_family``, the kind arm a statement
(4.5) and an exclusion's condition 5 (4.6) read: a kind that is not established leaves every kind of its session's
family possible - requirements_table.FAMILY_KINDS, the one table K2 reads too (DECISIONS D191), never computed here -
and every kind when the session or its kind is not established [R:HO-5]. As a candidate for a code (4.4) an act's kind
is read by ``possibly`` alone: its claimed value, its readings and its control's sibling. A claim pass 1 wrote negated
that is not established (and a merged view) leaves every value possible for ``possibly`` and every reader built on it,
the kind readers included (DECISIONS D294 RD-3, ``open_denial``): weakening an established denial never narrows what
the fact may be. ``possibly_written`` is the reading without that widening, for the claimed-value readers (4.3.3 c) and
the readers of a multi-valued list's members, which RD-3 (a single-valued claim) does not reach. ``apart_by_lesion``
and ``apart_by_place`` set two objects apart only on established, different (disjoint) targets AND rejected pair
controls in both directions: a short list never sets anything apart, and a pair control that was not generated is not
rejected [R:SC-B]. ``apart_by_place`` reads every pair control between the two objects, whatever place it asks about
(``apart_by_controls``, DECISIONS D220, kept by D236): "apart" needs every such control rejected and every current
member of the other object asked by a rejected control. A stored pair control names the object it asks and the value
it asks about, never the object whose value it was (the claim's identity; the FactSet's key), so for a multi-valued
list every pair control asked of either object is read as one between them (fail-closed): under 9.4's weakening - a
member deleted from a list, the pair controls left as they were - the deleted member's unrejected control still keeps
the pair together, and so does an unrejected control another object's place made (repair r2d's question Q1, ruled by
D236: as built, named in 6a's P-MONO). ``apart_by_lesion`` reads only the lesion pair controls between the two objects
as their target lesions name them, (a, lb) and (b, la) (DECISIONS D235): target.lesion is single-valued and no 9.4
weakening deletes or changes it, so these two are exactly the controls between the pair, and a control about a lesion
only a third object names, made for another pair, is not read - 4.2's lesion reading. The every-control scan stays for
the multi-valued sets (place lists here, a statement's listed lesions in engine/pairing.py).

**effective(inventory, effective_date)** (4.2, 6.5): L1 re-judged on the timing facts - an event's date relation and a
section's occasion - from the literals L1 stored with each (checks.literals: for an act's inherited date relation, its
section's occasion literals and the act's own date literals, DECISIONS D193; one that stores none of its own is judged
on its section's occasion literals, a defence kept by D193), with no text read, against the effective date of service
(member precedence, interpretation/dates.py), called identically by assess and by the overlay. It can only demote: an
established timing fact whose literals do not all meet the date as its value requires (on_date_of_service: the
literal holds the date at its own precision - a day equal to it, a month or a year containing it; earlier_date: the
literal's period ends before it; later_date: it starts after it) becomes unresolved with ``literal_mismatch``; with no
effective date, one with a day literal becomes unresolved with ``literal_unchecked`` (3.1 L1, 3.8 probe (b); DECISIONS
D193). Nothing is lifted, and every other fact is read as stored. The claim-time rule (contract/consistency.rejudge) is
a second implementation, because engine/ cannot import date_literals; tests/v2/test_facts.py pins the two equal over
the grid relation x precision x literal x service date (D193).

**The text-free boundary** (P1, 5.7 measures 4 and 5): this module imports the standard library, contract/types.py and
engine's types, anatomy, catalogue (FAMILY_REACH, which requirements_table already imports) and requirements_table only
(no retired v1 module, none of contract's text modules, not store.py: its caller hands it store.textfree_v2's view), and
holds no word list (every module-level collection holds enumeration members - but ``_FINDINGS``, the findings memo of a
few FactSets, DECISIONS D297 ENGB-1). No public function here returns a string
(the private readers of the stored JSON do), and ``mypy --strict`` passes over it. A row this builder cannot read whole
raises FactSetError (a ValueError); nothing is ever read as an empty inventory.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation.contract.types import (AccessOutcome, AnastomosisSubtype, AnatomyType, Approach, Attribute,
                                                  Breadth, Cause, CheckStatus, Completion, DateRelation, DateRole,
                                                  Device, DoubtAbout, Duct, EmBasis, EncounterRelation, Extent,
                                                  FactState, Kind, Landmark, Link, Material, Multiplicity, OtherClass,
                                                  Owner, PartRelation, Performer, PersonRole, Precision, Purpose,
                                                  Qualifier2, Reason, RestatementRole, Result, Route, SectionRole,
                                                  Separate, SessionKind, Station, Status, Structure, Tract,
                                                  UnlistedWhat, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue, requirements_table
from studio.interpretation.engine.types import (Anchor, Cited, Fact, FactSet, Id, IdFamily, IsoDate, Span,
                                                UnlistedStatement, Value)


_T = TypeVar('_T', bound=Enum)


class FactSetError(ValueError):
    """A stored inventory this module cannot read whole into a FactSet: a field missing or of the wrong type, a value
    outside its attribute's domain, an attribute an object does not have. It names the place, never a stored value."""


# --- the domains: what each attribute's values are (FINAL-V2 1.4; store's v2 shapes) ---------------------------------


@dataclass(frozen=True, slots=True)
class Domain:
    """What the values of one attribute of one object family are (FINAL-V2 1.3: "an enumeration value, an id or an ISO
    date"): ``enum``, an Enum of contract/types.py; else ``family``, an engine IdFamily (a value that is an id of another
    family is kept: before settle establishes a fact its id may name nothing, 1.8); else an IsoDate. ``many``: a
    multi-valued attribute (one Fact per member)."""
    enum: type[Enum] | None = None
    family: IdFamily | None = None
    many: bool = False


def _of(enum: type[Enum], many: bool = False) -> Domain:
    return Domain(enum=enum, many=many)


def _ids(family: IdFamily, many: bool = False) -> Domain:
    return Domain(family=family, many=many)


_DATE = Domain()
_E, _X, _N, _L, _Y, _P = (IdFamily.EVENT, IdFamily.SESSION, IdFamily.SECTION, IdFamily.LESION, IdFamily.ANATOMY,
                          IdFamily.PERSON)
_A = Attribute

# (the object family - None for the encounter -, attribute) -> its Domain: every fact the stored row holds (store.py's
# v2 shapes, field for field), and nothing else.
DOMAINS: Mapping[tuple[IdFamily | None, Attribute], Domain] = MappingProxyType({
    (None, _A.DATE_OF_SERVICE): _DATE, (None, _A.OTHER_DATES_ROLE): _of(DateRole, many=True),
    (None, _A.DOCUMENTING_CLINICIAN): _ids(_P),
    (_P, _A.ROLE): _of(PersonRole),
    (_N, _A.OWNER): _of(Owner), (_N, _A.ROLE): _of(SectionRole), (_N, _A.OCCASION): _of(DateRelation),
    (_N, _A.PERFORMER): _of(Performer), (_N, _A.PERFORMER_PERSON): _ids(_P),
    (_X, _A.EXAMINATION): _ids(_E), (_X, _A.KIND): _of(SessionKind), (_X, _A.ENCOUNTER): _of(EncounterRelation),
    (_X, _A.TRACT): _of(Tract), (_X, _A.APPROACH): _of(Approach), (_X, _A.THROUGH): _ids(_Y),
    (_X, _A.REACHED): _of(Extent, many=True), (_X, _A.DEVICE_REACHED): _of(Extent, many=True),
    (_X, _A.REACHED_ANATOMY): _ids(_Y), (_X, _A.COMPLETION): _of(Completion),
    (_X, _A.STATIONS): _of(Station, many=True), (_X, _A.PART_OF_SESSION): _ids(_X),
    (_Y, _A.TYPE): _of(AnatomyType), (_Y, _A.ORGAN): _of(Landmark), (_Y, _A.SUBTYPE): _of(AnastomosisSubtype),
    (_Y, _A.JOINS): _of(Landmark, many=True),
    (_L, _A.MULTIPLICITY): _of(Multiplicity), (_L, _A.PLACES): _of(Landmark, many=True),
    (_L, _A.DISTINCT_FROM): _ids(_L, many=True), (_L, _A.SAME_AS): _ids(_L, many=True),
    (_E, _A.RESTATEMENTS_ROLE): _of(RestatementRole, many=True), (_E, _A.KIND): _of(Kind),
    (_E, _A.OTHER_CLASS): _of(OtherClass), (_E, _A.STATUS): _of(Status), (_E, _A.SESSION): _ids(_X),
    (_E, _A.DATE_RELATION): _of(DateRelation), (_E, _A.DATE): _DATE, (_E, _A.PERFORMER): _of(Performer),
    (_E, _A.PERFORMER_PERSON): _ids(_P), (_E, _A.ENTRY): _of(Owner),
    (_E, _A.TARGET_LESION): _ids(_L), (_E, _A.TARGET_STRUCTURE): _of(Structure),
    (_E, _A.TARGET_PLACES): _of(Landmark, many=True), (_E, _A.TARGET_ANATOMY): _ids(_Y),
    (_E, _A.TARGET_DUCT): _of(Duct), (_E, _A.TECHNIQUE_DEVICE): _of(Device), (_E, _A.TECHNIQUE_ROUTE): _of(Route),
    (_E, _A.PURPOSE): _of(Purpose), (_E, _A.CAUSE): _of(Cause), (_E, _A.CAUSE_EVENT): _ids(_E),
    (_E, _A.PART_OF): _ids(_E), (_E, _A.PART_RELATION): _of(PartRelation), (_E, _A.YIELD): _of(Material),
    (_E, _A.ACCESS_OUTCOME): _of(AccessOutcome), (_E, _A.SCOPE_BREADTH): _of(Breadth),
    (_E, _A.SCOPE_TARGETS): _ids(_L, many=True), (_E, _A.SCOPE_SEGMENT): _of(Landmark, many=True),
    (_E, _A.SCOPE_COVERS): _ids(_E, many=True), (_E, _A.SCOPE_EXCEPTS): _ids(_E, many=True),
    (_E, _A.VISIT_BASIS): _of(EmBasis), (_E, _A.VISIT_SEPARATELY_IDENTIFIABLE): _of(Separate),
})

# An attribute by the path the stored row writes it at (its value: 'kind', 'target.places', 'restatements.role').
_ATTRIBUTE_AT: Mapping[str, Attribute] = MappingProxyType({attribute.value: attribute for attribute in Attribute})

ESTABLISHED: frozenset[Result] = frozenset({Result.SUPPORTED, Result.NEGATED})
# The results possibly() reads a value list of (4.2): every result that is not established.
OPEN: frozenset[Result] = frozenset({Result.UNRESOLVED, Result.CONTRADICTED, Result.UNKNOWN})
# What L1 wants of a timing fact's literal, compared with the effective date at the literal's precision (3.1 L1).
_WANTS: Mapping[DateRelation, int] = MappingProxyType({DateRelation.ON_DATE_OF_SERVICE: 0,
                                                       DateRelation.EARLIER_DATE: -1, DateRelation.LATER_DATE: 1})
# The attributes a pair control asks about (3.2.3 [R:SC-B]): the builder refuses a pair control of any other, and
# apart_by_controls reads one of these (DECISIONS D220).
PAIR_ATTRIBUTES: frozenset[Attribute] = frozenset({Attribute.TARGET_PLACES, Attribute.TARGET_LESION})
# The timing facts L1 re-judges at assess and read time (an inherited date relation is stored per act, 1.5).
TIMING: frozenset[tuple[IdFamily, Attribute]] = frozenset({(_E, _A.DATE_RELATION), (_N, _A.OCCASION)})
# The single-valued attributes pass 1 reports as exactly one FACT, never as a SLOT (FINAL-V2 1.4; contract/
# extract_schema's FACT arity, and the encounter's date of service and an act's entry, which pass 1 does not report as
# a slot): none of them can be overfilled.
REQUIRED_FACTS: frozenset[tuple[IdFamily | None, Attribute]] = frozenset({
    (None, _A.DATE_OF_SERVICE), (_P, _A.ROLE), (_N, _A.OWNER), (_X, _A.KIND), (_Y, _A.TYPE), (_E, _A.KIND),
    (_E, _A.STATUS), (_E, _A.ENTRY)})
# The 38 single-valued slot attributes (AMENDMENT-2 4.3.3): the only places an overfilled slot - more than one stored
# fact at one key, each carrying slot_overfull - is read, as one merged view (module docstring).
SLOTS: frozenset[tuple[IdFamily | None, Attribute]] = frozenset(
    key for key, domain in DOMAINS.items() if not domain.many and key not in REQUIRED_FACTS)

# A slot with nothing in it, and what an object or attribute the FactSet does not hold reads as (fail-closed: unknown,
# never established, every value possible).
SILENT = Fact(result=Result.UNKNOWN, value=None, state=None, options=(), reasons=(Reason.SILENT,), spans=())

# --- reading JSON data, typed ------------------------------------------------------------------------------------------


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise FactSetError(f'The stored inventory is not readable: {where} is not an object.')
    return value


def _sequence(value: object, where: str) -> Sequence[object]:
    if not isinstance(value, list | tuple):
        raise FactSetError(f'The stored inventory is not readable: {where} is not a list.')
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise FactSetError(f'The stored inventory is not readable: {where} is not a string.')
    return value


def _integer(value: object, where: str) -> int:
    if type(value) is not int:
        raise FactSetError(f'The stored inventory is not readable: {where} is not an integer.')
    return value


def _field(record: Mapping[str, object], name: str, where: str) -> object:
    try:
        return record[name]
    except KeyError:
        raise FactSetError(f'The stored inventory is not readable: {where} lacks {name}.') from None


def _enum(enum: type[_T], value: object, where: str) -> _T:
    try:
        return enum(_string(value, where))
    except ValueError:
        raise FactSetError(f'The stored inventory is not readable: {where} is not a value of {enum.__name__}.') from None


def _id(value: object, where: str) -> Id:
    try:
        return Id.parse(_string(value, where))
    except ValueError:
        raise FactSetError(f'The stored inventory is not readable: {where} is not an id.') from None


# --- dates -------------------------------------------------------------------------------------------------------------


def iso_value(value: str) -> IsoDate:
    """The IsoDate pass 1 writes as ``value`` - YYYY, YYYY-MM or YYYY-MM-DD in canonical ASCII digits, a real date, the
    year at least 1 (store's _v2_date_precision) - by calendar arithmetic only. ValueError for anything else."""
    size = len(value)
    if size == 4:
        precision, rest = Precision.YEAR, '-01-01'
    elif size == 7:
        precision, rest = Precision.MONTH, '-01'
    elif size == 10:
        precision, rest = Precision.DAY, ''
    else:
        raise ValueError('An ISO date is YYYY, YYYY-MM or YYYY-MM-DD.')
    whole = value + rest
    day = datetime.date.fromisoformat(whole)
    if day.isoformat() != whole:
        raise ValueError('An ISO date is written in canonical digits.')
    return IsoDate(day, precision)


def as_date(value: object) -> datetime.date | None:
    """An effective date given as a date, a YYYY-MM-DD string or None (v1's verify._as_date, by calendar arithmetic).
    ValueError for anything else, a datetime included."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        raise ValueError('An effective date is a date, a YYYY-MM-DD string or None.')
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            found = iso_value(value)
        except ValueError:
            found = None
        if found is not None and found.precision is Precision.DAY:
            return found.value
    raise ValueError('An effective date is a date, a YYYY-MM-DD string or None.')


def compare(literal: IsoDate, service: datetime.date) -> int:
    """-1 when the literal's period ends before ``service``, 0 when it holds it, 1 when it starts after it: the literal
    compared at its own precision (v1's literals.compare, over an IsoDate)."""
    first: tuple[int, ...] = (literal.value.year, literal.value.month, literal.value.day)
    second: tuple[int, ...] = (service.year, service.month, service.day)
    size = {Precision.YEAR: 1, Precision.MONTH: 2}.get(literal.precision, 3)
    first, second = first[:size], second[:size]
    return (first > second) - (first < second)


def rejudged(value: Value | None, literals: Sequence[IsoDate | None], service: datetime.date | None) -> Reason | None:
    """L1 re-judged (3.1 L1; module docstring): the reason a timing fact of ``value`` whose stored ``literals`` were read
    in its own words fails against the effective date ``service``, or None when it passes. A literal that cannot be read
    (None) never meets the date (fail-closed). Only a DateRelation value is judged."""
    if not isinstance(value, DateRelation) or not literals:
        return None
    if service is None:
        unchecked = any(literal is None or literal.precision is Precision.DAY for literal in literals)
        return Reason.LITERAL_UNCHECKED if unchecked else None
    want = _WANTS[value]
    for literal in literals:
        if literal is None or compare(literal, service) != want:
            return Reason.LITERAL_MISMATCH
    return None


# --- the builder ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Doubt:
    about: DoubtAbout
    objects: frozenset[str]
    readings: tuple[str, ...]


@dataclass(slots=True)
class _Context:
    """What reading one stored row needs across its objects: the units' spans, the doubts, the claims (for controls'
    values), and whether L1 is re-judged (``rejudge``) and against which date (``service``). ``occasions``: each
    section's stored occasion literals, by its id, for the date relations its acts inherit."""
    units: Mapping[str, Span]
    doubts: tuple[_Doubt, ...]
    claims: Mapping[str, Mapping[str, object]]
    rejudge: bool
    service: datetime.date | None
    occasions: dict[str, tuple[IsoDate | None, ...]] = field(default_factory=dict)
    # the events whose overfilled session slot holds a written fact K3 demoted (session_unreachable): the merged view
    # is widened as that fact alone would be (module docstring, an overfilled slot)
    unreachable: set[Id] = field(default_factory=set)

    def span(self, units: Sequence[object], where: str) -> Span | None:
        """The span from the first cited unit's start to the last one's end; None when a unit is unknown (an item-level
        finding settle already demoted, 3.1 I1) or none is cited."""
        found = [self.units.get(_string(unit, where)) for unit in units]
        if not found or any(item is None for item in found):
            return None
        first, last = found[0], found[-1]
        assert first is not None and last is not None
        return Span(first.start, last.end)

    def cited(self, sources: Sequence[object], where: str) -> tuple[Cited, ...]:
        """One Cited per stored source, in pass 1's order (DECISIONS D188): its link, the span of its cited units and
        its located words' offsets (``at``: None when it cites its whole units). A source whose units span is unknown
        (a unit the row does not have, or none cited: an item-level finding settle already demoted, 3.1 I1) is still
        read whole, its link and offsets included, and is not cited, as its units are in no fact's ``spans``."""
        out: list[Cited] = []
        for index, source in enumerate(sources):
            place = f'{where}[{index}]'
            record = _mapping(source, place)
            span = self.span(_sequence(_field(record, 'units', place), f'{place}.units'), f'{place}.units')
            link = _enum(Link, _field(record, 'link', place), f'{place}.link')
            at = _located(_field(record, 'at', place), f'{place}.at')
            if span is not None:
                out.append(Cited(link=link, units=span, at=at))
        return tuple(out)

    def counter(self, appraisal: object, where: str) -> tuple[Span, ...]:
        """The spans of the evidence units of a contradicts or qualified verdict (3.2.5: kept as COUNTER sources and
        quoted in the hold question; DECISIONS D188), each once, in the verdict's order; a supports verdict that names
        a qualifier but approximate is read as qualified (DECISIONS D186; approximate is recorded and never lowers,
        1.3 and D224). An evidence unit the row does not have locates nothing and is skipped (the verdict demotes
        all the same, 3.2.5). Empty for any other verdict, or for no appraisal."""
        if appraisal is None:
            return ()
        record = _mapping(appraisal, where)
        raw = _field(record, 'verdict', where)
        qualifiers = tuple(_enum(Qualifier2, item, f'{where}.qualifiers')
                           for item in _sequence(_field(record, 'qualifiers', where), f'{where}.qualifiers'))
        evidence = _sequence(_field(record, 'evidence', where), f'{where}.evidence')
        verdict = None if raw is None else _enum(VerdictValue, raw, f'{where}.verdict')
        countered = verdict is VerdictValue.CONTRADICTS or verdict is VerdictValue.QUALIFIED or (
            verdict is VerdictValue.SUPPORTS and any(item is not Qualifier2.APPROXIMATE for item in qualifiers))
        out: list[Span] = []
        for index, unit in enumerate(evidence):
            span = self.units.get(_string(unit, f'{where}.evidence[{index}]'))
            if countered and span is not None and span not in out:
                out.append(span)
        return tuple(out)

    def readings(self, subjects: Sequence[str], encounter: bool) -> Iterator[str]:
        """The readings of every doubt that names one of ``subjects`` (the encounter's: a date_of_service doubt)."""
        for doubt in self.doubts:
            named = (doubt.about is DoubtAbout.DATE_OF_SERVICE) if encounter else bool(doubt.objects.intersection(
                subjects))
            if named:
                yield from doubt.readings

    def control_value(self, appraisal: object, where: str) -> str | None:
        """The value of the fact's contrary control when pass 2 did not reject it (a verdict other than contradicts, or
        none); None otherwise (3.2.3, [R:HO-3])."""
        if appraisal is None:
            return None
        record = _mapping(appraisal, where)
        control = _field(record, 'control', where)
        if control is None:
            return None
        control = _mapping(control, f'{where}.control')
        verdict = _field(control, 'verdict', f'{where}.control')
        if verdict is not None and _enum(VerdictValue, verdict, f'{where}.control.verdict') is VerdictValue.CONTRADICTS:
            return None
        claim = self.claims.get(_string(_field(control, 'claim', f'{where}.control'), f'{where}.control.claim'))
        if claim is None:
            raise FactSetError(f'The stored inventory is not readable: {where}.control names no stored claim.')
        return _string(_field(claim, 'value', 'a claim'), 'a claim value')


def _value(raw: str, domain: Domain, where: str) -> Value:
    """``raw`` parsed into ``domain``: FactSetError when it is no value of it."""
    found = _maybe(raw, domain)
    if found is None:
        raise FactSetError(f'The stored inventory is not readable: {where} is not a value of its attribute.')
    return found


def _maybe(raw: str, domain: Domain) -> Value | None:
    """``raw`` parsed into ``domain``, or None when it is no value of it."""
    try:
        if domain.enum is not None:
            member: Enum = domain.enum(raw)
            return member
        if domain.family is not None:
            return Id.parse(raw)
        return iso_value(raw)
    except ValueError:
        return None


def _is_fact(value: object) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get('claim'), Mapping) and value.get('result') is not None


def _paths(record: Mapping[str, object], prefix: str, listed: bool) -> Iterator[tuple[Attribute, object, bool, str]]:
    """(attribute, value, listed, path) for every fact path in ``record``: a key whose path ('target.places') is an
    Attribute's value; groups and list items are walked with the path as prefix. ``listed``: the value sits in a list
    item (a restatement's role, an other date's role)."""
    for key, value in record.items():
        path = f'{prefix}{key}'
        attribute = _ATTRIBUTE_AT.get(path)
        if attribute is not None:
            yield attribute, value, listed, path
        elif isinstance(value, Mapping) and not _is_fact(value):
            yield from _paths(_mapping(value, path), f'{path}.', listed)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping) and not _is_fact(item):
                    yield from _paths(_mapping(item, path), f'{path}.', True)


def _fact(record: object, domain: Domain, subject: str, attribute: Attribute, family: IdFamily | None,
          context: _Context, where: str) -> Fact:
    """One stored fact (1.7) as a Fact: text stripped, values parsed, options gathered, L1 re-judged when asked."""
    stored = _mapping(record, where)
    claim = _mapping(_field(stored, 'claim', where), f'{where}.claim')
    raw_state = _field(claim, 'state', f'{where}.claim')
    state = None if raw_state is None else _enum(FactState, raw_state, f'{where}.claim.state')
    raw = _string(_field(claim, 'value', f'{where}.claim'), f'{where}.claim.value')
    value = None if raw == '' else _value(raw, domain, f'{where}.claim.value')
    result = _enum(Result, _field(stored, 'result', where), f'{where}.result')
    reasons = tuple(_enum(Reason, item, f'{where}.reasons')
                    for item in _sequence(_field(stored, 'reasons', where), f'{where}.reasons'))
    cited = context.cited(_sequence(_field(stored, 'sources', where), f'{where}.sources'), f'{where}.sources')
    spans = tuple(dict.fromkeys(item.units for item in cited))
    checks = _mapping(_field(stored, 'checks', where), f'{where}.checks')
    literals = tuple(_literal(item, f'{where}.checks.literals')
                     for item in _sequence(_field(checks, 'literals', f'{where}.checks'), f'{where}.checks.literals'))
    raw_inherited = _field(claim, 'inherited_from', f'{where}.claim')
    inherited = None if raw_inherited is None else _string(raw_inherited, f'{where}.claim.inherited_from')
    inherited_from = None if inherited is None else _id(inherited, f'{where}.claim.inherited_from')
    if inherited_from is not None and inherited_from.family is not _N:
        raise FactSetError(f'The stored inventory is not readable: {where}.claim.inherited_from names no section.')
    counter = context.counter(_field(stored, 'appraisal', where), f'{where}.appraisal')
    if family is not None and (family, attribute) in TIMING:
        if family is _N:
            context.occasions[subject] = literals
        elif not literals and inherited is not None:
            # 3a stores an inherited date relation's literals with the per-act fact (DECISIONS D193); one stored with
            # none of its own is re-judged on its section's occasion literals, a defence D193 keeps
            literals = context.occasions.get(inherited, ())
        if context.rejudge and result in ESTABLISHED:
            failed = rejudged(value, literals, context.service)
            if failed is not None:
                result, reasons = Result.UNRESOLVED, reasons + ((failed,) if failed not in reasons else ())
    options: list[Value] = []
    if result not in ESTABLISHED:
        candidates: list[str] = []
        for index, option in enumerate(_sequence(_field(claim, 'options', f'{where}.claim'), f'{where}.claim.options')):
            side = _mapping(option, f'{where}.claim.options[{index}]')
            candidates.append(_string(_field(side, 'value', f'{where}.claim.options[{index}]'),
                                      f'{where}.claim.options[{index}].value'))
        subjects = [subject] + ([inherited] if inherited is not None else [])
        candidates += list(context.readings(subjects, family is None))
        control = context.control_value(_field(stored, 'appraisal', where), f'{where}.appraisal')
        if control is not None:
            candidates.append(control)
        for candidate in candidates:
            parsed = _maybe(candidate, domain) if candidate != '' else None
            if parsed is not None and parsed != value and parsed not in options:
                options.append(parsed)
    return Fact(result=result, value=value, state=state, options=tuple(options), reasons=reasons, spans=spans,
                cited=cited, inherited_from=inherited_from, counter=counter)


def _written(record: object, value: Value | None, domain: Domain, where: str) -> tuple[Value, ...]:
    """The values one stored fact's claim writes (AMENDMENT-2 4.3.3): its claimed value, and, for a claim pass 1 wrote
    contradicted, each of its sides (claim.options) parsed into ``domain`` - in written order, each once. A doubt's
    reading or a control's value is no written value."""
    claim = _mapping(_field(_mapping(record, where), 'claim', where), f'{where}.claim')
    out: list[Value] = [value] if value is not None else []
    for index, option in enumerate(_sequence(_field(claim, 'options', f'{where}.claim'), f'{where}.claim.options')):
        place = f'{where}.claim.options[{index}]'
        raw = _string(_field(_mapping(option, place), 'value', place), f'{place}.value')
        parsed = _maybe(raw, domain) if raw != '' else None
        if parsed is not None and parsed not in out:
            out.append(parsed)
    return tuple(out)


def _overfilled(records: Sequence[object], domain: Domain, subject: str, attribute: Attribute,
                family: IdFamily | None, context: _Context, where: str) -> Fact:
    """An overfilled slot as ONE Fact, the merged view (AMENDMENT-2 4.3.3; module docstring, an overfilled slot): result
    unresolved, value None, state contradicted, reason slot_overfull, the spans, cited sources and counters of every
    written fact, options every written value (each fact's claimed value and a written contradiction's sides) in written
    order and then what each written fact read alone leaves possible besides, each once; ``negated_values`` the written
    values only denied: every written fact of which was negated, and which no written fact read alone leaves possible
    besides (a doubt's reading of the object, which ``_digital``'s claimed-manual reading takes as a claim - NOTES
    question Q1R) - every reading of a doubt naming the object (the subject, or a section a written fact inherits from)
    compared with the written values directly, so a reading of the value every written fact writes and denies is
    offered too (DECISIONS D294 RD-1; ``_fact`` removes a fact's own value from its options, so they cannot carry it);
    ``inherited_from`` the written facts' section when they all name one. FactSetError for fewer than two
    facts, for a slot that is none of SLOTS, and for a fact without slot_overfull (store.py refuses such a row)."""
    if (family, attribute) not in SLOTS or len(records) < 2:
        raise FactSetError(f'The stored inventory is not readable: {where} holds more than one fact.')
    timing = family is _N and (family, attribute) in TIMING
    written: list[Value] = []
    denied: list[Value] = []
    stated: set[Value] = set()
    besides: list[Value] = []
    offered: set[Value] = set()
    literals: list[IsoDate | None] = []
    found: list[Fact] = []
    for index, record in enumerate(records):
        place = f'{where}[{index}]'
        one = _fact(record, domain, subject, attribute, family, context, place)
        if Reason.SLOT_OVERFULL not in one.reasons:
            raise FactSetError(f'The stored inventory is not readable: {place} is not overfilled.')
        if timing:
            literals.extend(context.occasions.get(subject, ()))
        values = _written(record, one.value, domain, place)
        written.extend(value for value in values if value not in written)
        if one.state is FactState.NEGATED:
            denied.extend(value for value in values if value not in denied)
        else:
            stated.update(values)
        besides.extend(value for value in one.options if value not in besides)
        offered.update(value for value in one.options if value not in values)  # a doubt's reading, never a side
        found.append(one)
    if timing:
        context.occasions[subject] = tuple(literals)
    # DECISIONS D294 RD-1: a value any doubt naming the slot's object - the subject, or a section a written fact
    # inherits from - reads is offered, compared with the written values directly: never through a written fact's
    # options, from which _fact removes the fact's own value, so a reading of the value EVERY written fact writes is
    # offered too (never in negated_values). With no such doubt nothing is offered (D293 N2's T2 exception unchanged).
    named = [subject, *dict.fromkeys(str(one.inherited_from) for one in found if one.inherited_from is not None)]
    offered.update(parsed for parsed in (_maybe(raw, domain) if raw != '' else None
                                         for raw in context.readings(named, family is None)) if parsed is not None)
    if family is _E and attribute is Attribute.SESSION and any(
            Reason.SESSION_UNREACHABLE in one.reasons for one in found):
        context.unreachable.add(_id(subject, where))
    sections = {one.inherited_from for one in found}
    return Fact(result=Result.UNRESOLVED, value=None, state=FactState.CONTRADICTED,
                options=tuple(dict.fromkeys((*written, *besides))), reasons=(Reason.SLOT_OVERFULL,),
                spans=tuple(dict.fromkeys(span for one in found for span in one.spans)),
                cited=tuple(cited for one in found for cited in one.cited),
                inherited_from=sections.pop() if len(sections) == 1 else None,
                counter=tuple(dict.fromkeys(span for one in found for span in one.counter)),
                negated_values=tuple(value for value in denied if value not in stated and value not in offered))


def _literal(record: object, where: str) -> IsoDate | None:
    """A stored L1 literal ({value, precision}) as an IsoDate, None when it is not written at its precision (such a
    literal never meets a date: fail-closed)."""
    stored = _mapping(record, where)
    precision = _enum(Precision, _field(stored, 'precision', where), f'{where}.precision')
    try:
        found = iso_value(_string(_field(stored, 'value', where), f'{where}.value'))
    except ValueError:
        return None
    return found if found.precision is precision else None


def _object_facts(record: Mapping[str, object], family: IdFamily | None, subject: str, context: _Context,
                  where: str) -> dict[Attribute, tuple[Fact, ...]]:
    """Every fact of one object (or of the encounter, family None), by attribute: each single-valued attribute present
    exactly once - an overfilled slot (a list of facts at a slot's key) as its one merged view (``_overfilled``) -, each
    multi-valued one as its members in order (none when its list is empty)."""
    found: dict[Attribute, list[Fact]] = {}
    for attribute, value, listed, path in _paths(record, '', False):
        place = f'{where}.{path}'
        domain = DOMAINS.get((family, attribute))
        if domain is None:
            raise FactSetError(f'The stored inventory is not readable: {place} is an attribute its object does not '
                               'have.')
        members = found.setdefault(attribute, [])
        if domain.many and not listed:
            items = _sequence(value, place)
            members.extend(_fact(item, domain, subject, attribute, family, context, f'{place}[{index}]')
                           for index, item in enumerate(items))
        elif domain.many:
            members.append(_fact(value, domain, subject, attribute, family, context, place))
        elif listed or members:
            raise FactSetError(f'The stored inventory is not readable: {place} holds more than one fact.')
        elif isinstance(value, list | tuple):
            members.append(_overfilled(value, domain, subject, attribute, family, context, place))  # AMENDMENT-2 4.3.3
        else:
            members.append(_fact(value, domain, subject, attribute, family, context, place))
    for (owner, attribute), domain in DOMAINS.items():
        if owner is family and domain.many:
            found.setdefault(attribute, [])
        elif owner is family and attribute not in found:
            raise FactSetError(f'The stored inventory is not readable: {where} lacks its {attribute.value} fact.')
    return {attribute: tuple(members) for attribute, members in found.items()}


def _events_of(inventory: object) -> Mapping[str, object]:
    """The settled inventory's content as the engine reads it: store.textfree_v2's view, a mapping (DECISIONS D188).
    Anything that is not a mapping - store.load_v2's StoredInventoryV2 itself, whose events hold the stored text - is
    refused; the events as stored are refused where the builder meets their first ``words`` record (a source with no
    ``at``) or text (a located record holding more than its offsets)."""
    if not isinstance(inventory, Mapping):
        raise FactSetError('The stored inventory is not readable: the engine reads store.textfree_v2\'s view of a '
                           'stored row, never the row.')
    return _mapping(inventory, 'the inventory')


def _units(events: Mapping[str, object]) -> dict[str, Span]:
    out: dict[str, Span] = {}
    for index, unit in enumerate(_sequence(_field(events, 'units', 'the inventory'), 'units')):
        record = _mapping(unit, f'units[{index}]')
        start = _integer(_field(record, 'start', f'units[{index}]'), f'units[{index}].start')
        end = _integer(_field(record, 'end', f'units[{index}]'), f'units[{index}].end')
        try:
            out[_string(_field(record, 'id', f'units[{index}]'), f'units[{index}].id')] = Span(start, end)
        except ValueError:
            raise FactSetError(f'The stored inventory is not readable: units[{index}] is no span.') from None
    return out


def _doubts(events: Mapping[str, object]) -> tuple[_Doubt, ...]:
    out = []
    for index, doubt in enumerate(_sequence(_field(events, 'doubts', 'the inventory'), 'doubts')):
        where = f'doubts[{index}]'
        record = _mapping(doubt, where)
        about = _enum(DoubtAbout, _field(record, 'about', where), f'{where}.about')
        objects = frozenset(_string(item, f'{where}.objects')
                            for item in _sequence(_field(record, 'objects', where), f'{where}.objects'))
        readings = tuple(_string(item, f'{where}.readings')
                         for item in _sequence(_field(record, 'readings', where), f'{where}.readings'))
        out.append(_Doubt(about, objects, readings))
    return tuple(out)


def _claims(events: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    out: dict[str, Mapping[str, object]] = {}
    for index, claim in enumerate(_sequence(_field(events, 'claims', 'the inventory'), 'claims')):
        record = _mapping(claim, f'claims[{index}]')
        out[_string(_field(record, 'id', f'claims[{index}]'), f'claims[{index}].id')] = record
    return out


def _lesion_pair_presumes(claim: Mapping[str, object], where: str) -> int:
    """DECISIONS D300 RF-L3: how many of a lesion pair's two lesions its stored claim's form presumes single, by its
    template (contract/claims.LESION_PAIR_FORMS; the store binds the claim to one of them): 2 for D296's distinctness
    ("Lesions {lesion} and {other} are different lesions."), 1 for the membership of the act's lesion
    ("Lesion {other} is not one of the lesions of {lesion}."), 0 for "No lesion of {other} is one of the lesions of
    {lesion}.". FactSetError for any other form."""
    template = _string(_field(claim, 'template', where), f'{where}.template')
    if template == 'lesion.distinct_from':
        return 2
    if template == 'lesion.not_member':
        return 1
    if template == 'lesion.not_member.any':
        return 0
    raise FactSetError(f'The stored inventory is not readable: {where} is no lesion pair claim.')


def _single(lesions: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]], lesion: Id) -> bool:
    """A lesion established as one lesion: its multiplicity supported single."""
    found = lesions.get(lesion, _NOTHING).get(Attribute.MULTIPLICITY, ())
    return len(found) == 1 and holds(found[0], Multiplicity.SINGLE)


def _lesion_pairs(events: Mapping[str, object], context: _Context,
                  lesions: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]) -> dict[tuple[Id, Attribute, Value], bool]:
    """DECISIONS D296: each settled lesion pair claim of the row (the @3 pair's ``lesion_pairs``; an older row has
    none, and a row stored before D296 reads as none: DECISIONS D300 RF-L6), keyed (the statement's lesion,
    distinct_from, the act's lesion) in FactSet.pair_controls: True when settle established the two lesions distinct
    (the claim supported, its sameness control rejected), False otherwise. One lesion pair asked twice is established
    only when every asking was (fail-closed). Read by ``appraised_distinct`` alone, so only ever to set two lesions
    apart, never to join them; every reader of pair_controls by an event's place or lesion ignores these keys (another
    family's subject, another attribute).

    DECISIONS D300 RF-L3: a pair is established only with the multiplicity its claim's form presumes established too
    (``_lesion_pair_presumes``): D296's distinctness both lesions single, the membership of the act's lesion that lesion
    single, the third form neither - so a group, or a lesion not established as one, is set apart only by an
    established non-membership, and a row settled before D300 asked distinctness of a group reads as not established.
    A pair the claim set dropped to keep within its bound (RF-L5: no claim) is not established."""
    out: dict[tuple[Id, Attribute, Value], bool] = {}
    found = events.get('lesion_pairs')
    if found is None:
        return out
    for index, item in enumerate(_sequence(found, 'lesion_pairs')):
        where = f'lesion_pairs[{index}]'
        record = _mapping(item, where)
        lesion = _id(_field(record, 'lesion', where), f'{where}.lesion')
        other = _id(_field(record, 'other', where), f'{where}.other')
        if lesion.family is not _L or other.family is not _L or lesion == other:
            raise FactSetError(f'The stored inventory is not readable: {where} is no pair of two lesions.')
        result = _enum(Result, _field(record, 'result', where), f'{where}.result')
        claim_id = _field(record, 'claim', where)
        established = False
        if claim_id is not None and result is Result.SUPPORTED:
            claim = context.claims.get(_string(claim_id, f'{where}.claim'))
            if claim is None:
                raise FactSetError(f'The stored inventory is not readable: {where} names a claim the row does not '
                                   'hold.')
            presumed = (lesion, other)[2 - _lesion_pair_presumes(claim, f'{where}.claim'):]
            established = all(_single(lesions, entry) for entry in presumed)
        key = (lesion, Attribute.DISTINCT_FROM, other)
        out[key] = out.get(key, True) and established
    return out


def _context(events: Mapping[str, object], rejudge: bool, service: datetime.date | None) -> _Context:
    return _Context(units=_units(events), doubts=_doubts(events), claims=_claims(events), rejudge=rejudge,
                    service=service)


def _located(record: object, where: str) -> Span | None:
    """A located record of store.textfree_v2's view - a source's ``at``, an anchor's kind or status words: {start, end}
    and nothing else (DECISIONS D188) - as its Span; None for none (null). FactSetError for anything else, a record
    holding more than its two offsets included: the builder reads the text-free view, never the row as stored."""
    if record is None:
        return None
    located = _mapping(record, where)
    start = _integer(_field(located, 'start', where), f'{where}.start')
    end = _integer(_field(located, 'end', where), f'{where}.end')
    if len(located) != 2:
        raise FactSetError(f'The stored inventory is not readable: {where} holds more than its offsets.')
    try:
        return Span(start, end)
    except ValueError:
        raise FactSetError(f'The stored inventory is not readable: {where} is no span.') from None


def _anchor(record: Mapping[str, object], context: _Context, where: str) -> Anchor:
    anchor = _mapping(_field(record, 'anchor', where), f'{where}.anchor')
    units = []
    for index, unit in enumerate(_sequence(_field(anchor, 'units', f'{where}.anchor'), f'{where}.anchor.units')):
        span = context.units.get(_string(unit, f'{where}.anchor.units[{index}]'))
        if span is not None and span not in units:
            units.append(span)
    return Anchor(units=tuple(units),
                  kind_words=_located(_field(anchor, 'kind_words', f'{where}.anchor'), f'{where}.anchor.kind_words'),
                  status_words=_located(_field(anchor, 'status_words', f'{where}.anchor'),
                                        f'{where}.anchor.status_words'))


def _pair_controls(context: _Context) -> dict[tuple[Id, Attribute, Value], bool]:
    """Each pair control (3.2.3 [R:SC-B]) - the object asked, target.places or target.lesion, the place or lesion asked
    - and whether pass 2 rejected it (a contradicts verdict). The same question asked twice is rejected only when
    every asking was (fail-closed)."""
    out: dict[tuple[Id, Attribute, Value], bool] = {}
    for claim_id, claim in context.claims.items():
        where = f'the claim {claim_id}'
        if _string(_field(claim, 'role', where), f'{where}.role') != 'pair_control':
            continue
        subject = _id(_field(claim, 'subject', where), f'{where}.subject')
        attribute = _enum(Attribute, _field(claim, 'attribute', where), f'{where}.attribute')
        domain = DOMAINS.get((subject.family, attribute))
        if domain is None or attribute not in PAIR_ATTRIBUTES:
            raise FactSetError(f'The stored inventory is not readable: {where} is a pair control of no target.')
        asked = _value(_string(_field(claim, 'value', where), f'{where}.value'), domain, f'{where}.value')
        verdict = _field(claim, 'verdict', where)
        rejected = verdict is not None and _enum(
            VerdictValue, _field(_mapping(verdict, f'{where}.verdict'), 'verdict', f'{where}.verdict'),
            f'{where}.verdict.verdict') is VerdictValue.CONTRADICTS
        key = (subject, attribute, asked)
        out[key] = out.get(key, True) and rejected
    return out


def _unlisted(events: Mapping[str, object], context: _Context) -> tuple[UnlistedStatement, ...]:
    out = []
    for index, entry in enumerate(_sequence(_field(events, 'unlisted', 'the inventory'), 'unlisted')):
        where = f'unlisted[{index}]'
        record = _mapping(entry, where)
        spans = []
        for unit in _sequence(_field(record, 'units', where), f'{where}.units'):
            span = context.units.get(_string(unit, f'{where}.units'))
            if span is not None and span not in spans:
                spans.append(span)
        what = _enum(UnlistedWhat, _field(record, 'what', where), f'{where}.what')
        raw_kind, raw_session = _field(record, 'kind', where), _field(record, 'session', where)
        kind = None if raw_kind is None else _enum(Kind, raw_kind, f'{where}.kind')
        session = None if raw_session is None else _id(raw_session, f'{where}.session')
        out.append(UnlistedStatement(units=tuple(spans), what=what, kind=kind, session=session))
    return tuple(out)


# --- a session K3 demoted (DECISIONS D244 Q-N1 option (b); module docstring) ------------------------------------------


def _reach_holds(family: SessionKind, place: Landmark) -> bool:
    """Whether a session of ``family`` may hold an act at ``place`` as K3 reads a reach (3.1 K3; DECISIONS D192):
    unless the place lies in a region (engine/anatomy.region) that the family's reach (catalogue.FAMILY_REACH) is
    stated to leave out. A family the table does not list, and a place in no region, are judged by no reach: K3 never
    demotes on them, so they hold it (this repair's question R2D-K3)."""
    region = anatomy.region(place)
    reach = catalogue.FAMILY_REACH.get(family)
    return region is None or reach is None or region in reach


def _families(kind: Fact) -> frozenset[SessionKind]:
    """The families a session may be of, by its kind fact: its supported kind; every other family when it is negated;
    possibly's families otherwise (every family for an empty slot)."""
    if kind.result is Result.SUPPORTED and isinstance(kind.value, SessionKind):
        return frozenset({kind.value})
    if kind.result is Result.NEGATED:
        return frozenset(family for family in SessionKind if family != kind.value)
    return frozenset(family for family in SessionKind if possibly(kind, family))


def _places(members: Sequence[Fact]) -> tuple[Landmark, ...] | None:
    """The places an act may be at, by its target place members: a supported member's value, an open member's value
    and options (possibly's); a negated member names none. None when no place is known: no member names one (an empty
    list, or negated members only - where the act was not done says nothing of where it was), or a member that is not
    negated names none (an empty list is unknown, never an absence, P3)."""
    out: list[Landmark] = []
    for member in members:
        if member.result is Result.NEGATED:
            continue
        values = (member.value,) if member.result is Result.SUPPORTED else (member.value, *member.options)
        found = [value for value in values if isinstance(value, Landmark)]
        if not found:
            return None
        out.extend(value for value in found if value not in out)
    return tuple(out) if out else None


def _k3_widened(sessions: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]], held: Mapping[Attribute, tuple[Fact, ...]],
                overfilled: bool = False) -> Mapping[Attribute, tuple[Fact, ...]]:
    """One event's facts with its session fact widened when K3 demoted it (DECISIONS D244 Q-N1 option (b)): a session
    fact that is not established and carries ``session_unreachable`` gains, after its own options, every other session
    of ``sessions`` (in pass 1's order) that may be of a family whose reach holds any place the act may be at
    (``_reach_holds``, ``_families``, ``_places``; questions R2D-K3 and R2D-K3P). ``overfilled``: the event's session
    slot is overfilled and one of its written facts carried session_unreachable (AMENDMENT-2 4.3.3: the merged view is
    never narrower than that fact read alone). Any other event's facts are returned as they are."""
    found = held.get(Attribute.SESSION, ())
    if not found or found[0].result not in OPEN or not (
            overfilled or Reason.SESSION_UNREACHABLE in found[0].reasons):
        return held
    session = found[0]
    places = _places(held.get(Attribute.TARGET_PLACES, ()))
    added: list[Value] = []
    for candidate, facts_of in sessions.items():
        if candidate == session.value or candidate in session.options:
            continue
        kind = facts_of.get(Attribute.KIND, (SILENT,))[0]
        if places is None or any(_reach_holds(family, place) for family in _families(kind) for place in places):
            added.append(candidate)
    if not added:
        return held
    return {**held, Attribute.SESSION: (replace(session, options=session.options + tuple(added)),)}


def _build(inventory: object, rejudge: bool, service: datetime.date | None) -> FactSet:
    events = _events_of(inventory)
    context = _context(events, rejudge, service)
    encounter = _object_facts(_mapping(_field(events, 'encounter', 'the inventory'), 'encounter'), None, '', context,
                              'encounter')
    objects: dict[IdFamily, dict[Id, Mapping[Attribute, tuple[Fact, ...]]]] = {}
    anchors: dict[Id, Anchor] = {}
    completeness: dict[Id, Result] = {}
    for family, name in ((_P, 'people'), (_N, 'sections'), (_X, 'sessions'), (_Y, 'anatomy'), (_L, 'lesions'),
                         (_E, 'events')):
        found: dict[Id, Mapping[Attribute, tuple[Fact, ...]]] = {}
        for index, item in enumerate(_sequence(_field(events, name, 'the inventory'), name)):
            where = f'{name}[{index}]'
            record = _mapping(item, where)
            raw_id = _string(_field(record, 'id', where), f'{where}.id')
            subject = _id(raw_id, f'{where}.id')
            if subject.family is not family or subject in found:
                raise FactSetError(f'The stored inventory is not readable: {where} has an id of another family or '
                                   'one already used.')
            found[subject] = _object_facts(record, family, raw_id, context, where)
            if family is _E:
                anchors[subject] = _anchor(record, context, where)
            if family is _X:
                check = _field(record, 'completeness', where)
                if check is not None:
                    completeness[subject] = _enum(Result, _field(_mapping(check, f'{where}.completeness'), 'result',
                                                                 f'{where}.completeness'), f'{where}.completeness.result')
        objects[family] = found
    # a session fact K3 demoted is possibly any session whose reach holds the act's place (DECISIONS D244 Q-N1)
    objects[_E] = {subject: _k3_widened(objects[_X], held, subject in context.unreachable)
                   for subject, held in objects[_E].items()}
    return FactSet(encounter=encounter, people=objects[_P], sections=objects[_N], sessions=objects[_X],
                   anatomy=objects[_Y], lesions=objects[_L], events=objects[_E], anchors=anchors,
                   unlisted=_unlisted(events, context),
                   pair_controls={**_pair_controls(context), **_lesion_pairs(events, context, objects[_L])},
                   completeness=completeness)


def factset(inventory: object) -> FactSet:
    """The FactSet of a stored v2 inventory as settled (module docstring): ``inventory`` is store.textfree_v2's view
    of the row (DECISIONS D188). No L1 re-judge: assess and the overlay read ``effective``."""
    return _build(inventory, False, None)


def effective(inventory: object, effective_date: object) -> FactSet:
    """The FactSet of a stored v2 inventory - store.textfree_v2's view of the row (DECISIONS D188) - with L1 re-judged
    against ``effective_date`` (a date, a YYYY-MM-DD string or None: the effective date of service by member
    precedence, dates.py), from the literals stored with each timing fact, with no text read (FINAL-V2 4.2, 6.5;
    module docstring). It only demotes. ValueError for an effective date that is no date."""
    return _build(inventory, True, as_date(effective_date))


# --- the inventory's dates, for engine/derive.py ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OtherDate:
    """One of the encounter's other dates (FINAL-V2 1.4 ENCOUNTER.other_dates): its value, and its role as a Fact."""
    value: IsoDate
    role: Fact


@dataclass(frozen=True, slots=True)
class EncounterDates:
    """What engine/derive.py reads of the encounter's dates (FINAL-V2 1.4; dates.py's member-date rules): the date of
    service as a Fact; its contradicted sides, the values pass 1 reported with sources (claim.options: a Fact's options
    also hold a doubt's readings, which are no date the document gives); the literals L1 stored with it (its own words'
    dates, checks.literals; None for one that cannot be read); the other dates; and ``checks_passed``, whether its
    stored integrity and L1 checks both passed (checks.integrity and checks.literal ok). For a contradicted date that
    is every side at once - every side's sources passed S2 and I1-I3, and every side's own words state its value (L1
    reads each side's words, and a side that does not locate gives no literal and fails) - which is what v1 verified of
    each candidate (normalize._bind_date: the words bound, verify.date_words). The row keeps a fact's checks, never a
    side's, so a failed check names no side."""
    date_of_service: Fact
    sides: tuple[IsoDate, ...]
    literals: tuple[IsoDate | None, ...]
    others: tuple[OtherDate, ...]
    checks_passed: bool


def encounter_dates(inventory: object) -> EncounterDates:
    """The encounter's dates of a stored v2 inventory (EncounterDates) - store.textfree_v2's view of the row (DECISIONS
    D188) - text-free. FactSetError for a row it cannot read."""
    events = _events_of(inventory)
    context = _context(events, False, None)
    encounter = _mapping(_field(events, 'encounter', 'the inventory'), 'encounter')
    record = _mapping(_field(encounter, 'date_of_service', 'encounter'), 'encounter.date_of_service')
    fact = _fact(record, _DATE, '', Attribute.DATE_OF_SERVICE, None, context, 'encounter.date_of_service')
    claim = _mapping(_field(record, 'claim', 'encounter.date_of_service'), 'encounter.date_of_service.claim')
    sides = []
    for index, option in enumerate(_sequence(_field(claim, 'options', 'encounter.date_of_service.claim'),
                                             'encounter.date_of_service.claim.options')):
        where = f'encounter.date_of_service.claim.options[{index}]'
        side = _value(_string(_field(_mapping(option, where), 'value', where), f'{where}.value'), _DATE,
                      f'{where}.value')
        if isinstance(side, IsoDate):
            sides.append(side)
    checks = _mapping(_field(record, 'checks', 'encounter.date_of_service'), 'encounter.date_of_service.checks')
    literals = tuple(_literal(item, 'encounter.date_of_service.checks.literals')
                     for item in _sequence(_field(checks, 'literals', 'encounter.date_of_service.checks'),
                                           'encounter.date_of_service.checks.literals'))
    where = 'encounter.date_of_service.checks'
    integrity = _enum(CheckStatus, _field(checks, 'integrity', where), f'{where}.integrity')
    literal = _enum(CheckStatus, _field(checks, 'literal', where), f'{where}.literal')
    others = []
    for index, item in enumerate(_sequence(_field(encounter, 'other_dates', 'encounter'), 'encounter.other_dates')):
        where = f'encounter.other_dates[{index}]'
        entry = _mapping(item, where)
        try:
            value = iso_value(_string(_field(entry, 'value', where), f'{where}.value'))
        except ValueError:
            raise FactSetError(f'The stored inventory is not readable: {where}.value is no ISO date.') from None
        role = _fact(_field(entry, 'role', where), DOMAINS[(None, Attribute.OTHER_DATES_ROLE)], '',
                     Attribute.OTHER_DATES_ROLE, None, context, f'{where}.role')
        others.append(OtherDate(value=value, role=role))
    return EncounterDates(date_of_service=fact, sides=tuple(sides), literals=literals, others=tuple(others),
                          checks_passed=integrity is CheckStatus.OK and literal is CheckStatus.OK)


# --- accessors ---------------------------------------------------------------------------------------------------------


_NOTHING: Mapping[Attribute, tuple[Fact, ...]] = MappingProxyType({})


def _facts_of(R: FactSet, subject: Id | None) -> Mapping[Attribute, tuple[Fact, ...]]:
    if subject is None:
        return R.encounter
    table = {_E: R.events, _X: R.sessions, _N: R.sections, _L: R.lesions, _Y: R.anatomy, _P: R.people}.get(
        subject.family)
    return table.get(subject, _NOTHING) if table is not None else _NOTHING


def fact(R: FactSet, subject: Id | None, attribute: Attribute) -> Fact:
    """The one Fact of a single-valued ``attribute`` of ``subject`` (None: the encounter). An object or attribute the
    FactSet does not hold - a dangling id, an attribute of another family - reads as SILENT: unknown, never
    established, every value possible. ValueError for a multi-valued attribute (read ``members``)."""
    family = subject.family if subject is not None else None
    domain = DOMAINS.get((family, attribute))
    if domain is not None and domain.many:
        raise ValueError(f'{attribute.value} is multi-valued: read its members.')
    found = _facts_of(R, subject).get(attribute, ())
    return found[0] if found else SILENT


def members(R: FactSet, subject: Id | None, attribute: Attribute) -> tuple[Fact, ...]:
    """The members of a multi-valued ``attribute`` of ``subject``, in pass 1's order: () for an empty list, a dangling
    id or an attribute it does not hold - unknown, never an absence (P3). ValueError for a single-valued attribute
    (read ``fact``)."""
    family = subject.family if subject is not None else None
    domain = DOMAINS.get((family, attribute))
    if domain is not None and not domain.many:
        raise ValueError(f'{attribute.value} is single-valued: read its fact.')
    return _facts_of(R, subject).get(attribute, ())


# --- the predicates (FINAL-V2 4.2) ---------------------------------------------------------------------------------------


def holds(f: Fact, v: Value) -> bool:
    """Result supported and the value ``v``."""
    return f.result is Result.SUPPORTED and f.value == v


def denied(f: Fact, v: Value) -> bool:
    """Result negated and the value ``v`` (the document explicitly states ``v`` does not hold)."""
    return f.result is Result.NEGATED and f.value == v


def established(f: Fact) -> bool:
    """Result supported or negated (every check passed, pass 2 supported it attached, its control rejected: 3.3 row
    8)."""
    return f.result in ESTABLISHED


def silent(f: Fact) -> bool:
    """Nothing in the document governs the attribute: pass 1 claimed nothing (an empty slot, 1.3)."""
    return f.state is None


def possibly(f: Fact, v: Value) -> bool:
    """FINAL-V2 4.2: ``holds(f, v)``; or the result is unresolved, contradicted or unknown and ``v`` is the claimed
    value, one of the options (a contradicted fact's sides, a doubt's readings, the value of a control pass 2 did not
    reject), or the fact is silent. A status (``v`` a Status) that is not established leaves every status possible
    [R:HO-1][R:HO-3]. An established fact makes possible exactly its supported value (none when negated). This is the
    fail-closed doubt arm: a doubt is never an absence.

    DECISIONS D294 RD-3: a claim pass 1 wrote negated that is not established leaves EVERY value of its domain possible
    (``open_denial``, as classes._open reads it): the denial may be wrong, and a reader that reads the established
    denial as every other value (coverage.may_be: the kinds an act may be) must never read its weakening as the denied
    value alone - so weakening an established denial never narrows what the fact may be, for this predicate and every
    reader built on it (the kind readers, facts.possible_kinds and possibly_of_family, among them). An overfilled slot's
    merged view reads so too, as a written denial read alone now would (AMENDMENT-2 4.4; every view, the fail-closed
    reading of ``open_denial``). The claimed-value readers (AMENDMENT-2 4.3.3 c: the digital examination's device) and
    the readers of a multi-valued list's members, which RD-3 (a single-valued claim) does not reach, read
    ``possibly_written``."""
    if holds(f, v):
        return True
    if f.result not in OPEN:
        return False
    if isinstance(v, Status):
        return True
    return silent(f) or open_denial(f) or f.value == v or v in f.options


def possibly_written(f: Fact, v: Value) -> bool:
    """4.2's ``possibly`` over what the fact itself carries - its supported value; not established, its claimed value,
    its options, or any value when it is silent; a status not established, every status - never D294 RD-3's open
    denial: read by the claimed-value readers (AMENDMENT-2 4.3.3 c: pairing.digital_examination and combination._digital
    read a device that CLAIMS manual, DECISIONS D253's claimed-manual reading) and by the readers of a multi-valued
    list's members (a statement's excepts, a lesion's same_as, an other date's role), which RD-3 does not reach - so
    each keeps the reading it was built and ruled with."""
    if holds(f, v):
        return True
    if f.result not in OPEN:
        return False
    if isinstance(v, Status):
        return True
    return silent(f) or f.value == v or v in f.options


# Every kind of each session family (4.2's "every kind of its session's family"): THE table, which K2 ("an act's session
# kind admits its kind") reads too - requirements_table.FAMILY_KINDS, generated by step 1f from step 1e's tables
# (DECISIONS D191). It is never computed here.
FAMILY_KINDS: Mapping[SessionKind, frozenset[Kind]] = requirements_table.FAMILY_KINDS


def family_kinds(family: SessionKind) -> frozenset[Kind]:
    """Every kind of a session family (FAMILY_KINDS). A family the table holds no row for has none: D191's union is
    empty for a family that has no catalogue entry, no bundled or unsupported kind and is neither endoscopic nor
    procedural."""
    return FAMILY_KINDS.get(family, frozenset())


def session_family(R: FactSet, event: Id) -> SessionKind | None:
    """The family of ``event``'s session when both its session and that session's kind are established (supported);
    None otherwise."""
    session = fact(R, event, Attribute.SESSION)
    if session.result is not Result.SUPPORTED or not isinstance(session.value, Id):
        return None
    kind = fact(R, session.value, Attribute.KIND)
    return kind.value if kind.result is Result.SUPPORTED and isinstance(kind.value, SessionKind) else None


def possibly_of_family(R: FactSet, event: Id, kind: Kind) -> bool:
    """The kind arm of possibly for a statement (4.5) and an exclusion's condition 5 (4.6) [R:HO-5]: ``possibly`` on
    ``event``'s kind, widened, when the kind is not established, to every kind of its session's family - every kind
    when its session, or that session's kind, is not established. A candidate for a code (4.4) reads ``possibly``
    alone."""
    found = fact(R, event, Attribute.KIND)
    if possibly(found, kind):
        return True
    if established(found):
        return False
    family = session_family(R, event)
    return family is None or kind in family_kinds(family)


def possible_kinds(R: FactSet, event: Id, *, of_family: bool) -> frozenset[Kind]:
    """Every Kind ``event`` may be: by ``possibly`` (a candidate, 4.4), or by ``possibly_of_family`` (a statement or an
    exclusion's condition 5) - in both, every kind for a kind claim pass 1 wrote negated that is not established
    (DECISIONS D294 RD-3: the denial may be wrong)."""
    found = fact(R, event, Attribute.KIND)
    if of_family:
        return frozenset(kind for kind in Kind if possibly_of_family(R, event, kind))
    return frozenset(kind for kind in Kind if possibly(found, kind))


def established_kind(R: FactSet, event: Id) -> Kind:
    """The one label of an act (DECISIONS D287, D267's heading, D254 rule 2; build list B9): the catalogue kind of its
    SUPPORTED kind with its supported purpose (catalogue.catalogue_kind: a clip or an injection supported for hemostasis
    is a bleeding control), else Kind.OTHER - an act whose kind is negated, doubted, unresolved, contradicted, silent or
    an overfilled slot's, or other, is "another act". Every fact key that names an act names this kind
    (questions.act_kind, evaluate's, coverage's and classes' conflict keys read this one derivation)."""
    found = fact(R, event, Attribute.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        purpose = fact(R, event, Attribute.PURPOSE)
        named = catalogue.catalogue_kind(found.value, purpose.value if purpose.result is Result.SUPPORTED
                                         and isinstance(purpose.value, Purpose) else None)
        if named is not None:
            return named
    return Kind.OTHER


def overfilled(f: Fact) -> bool:
    """The merged view of an overfilled slot (AMENDMENT-2 4.3.3; module docstring): unresolved for slot_overfull, its
    state contradicted."""
    return f.state is FactState.CONTRADICTED and Reason.SLOT_OVERFULL in f.reasons


def open_denial(f: Fact) -> bool:
    """Whether a fact that is not established reads, for a possibility reader that takes an unestablished denial as
    leaving every value open (classes._open and _may_name, combination._named_sessions, coverage.sessions_of and
    _lesion_values: AMENDMENT-2 4.3.3 a; and, by DECISIONS D294 RD-3, ``possibly`` itself and every reader built on it),
    as such a denial: a claim pass 1 wrote negated (state negated), and every
    overfilled slot's merged view (``overfilled``). Whenever a written fact of the view denies a value, the view must
    leave every value open, as that denial read alone would (4.4: never stronger than any single written fact read
    alone, for any reader); and the view cannot tell from its options and ``negated_values`` whether one does, since a
    value one written fact states and another denies is not only denied (the claimed-value readers must claim it), so
    every view is read so - the fail-closed reading of NOTES question Q1R: a view of written values that are all stated
    leaves open more than 4.3.3 a asks, never less. The caller reads an established fact first."""
    return f.state is FactState.NEGATED or overfilled(f)


def claimed_values(f: Fact) -> tuple[Value, ...]:
    """The values pass 1's own claim of ``f`` states, as AMENDMENT-2 4.3.3 c's claimed-value readers read them: its
    value when its claim is supported (in any result but negated); a contradiction's sides - pass 1's own contradicted
    claim, whose settled value is empty, a fact settled contradicted, and an overfilled slot's merged view - its value
    and each option not in ``negated_values`` (for the view: every value a written fact states, a value another written
    fact denies included, and every reading a doubt offers - never a value only denied); nothing for a silent slot, a
    negated claim or a negated result. Each 9.4 weakening keeps a claimed value (an established fact to unresolved, an
    added doubt), and a weakening never removes a side, so these only grow under a weakening."""
    if silent(f) or f.result is Result.NEGATED or f.state is FactState.NEGATED:
        return ()
    if f.state is FactState.CONTRADICTED or f.result is Result.CONTRADICTED:
        return tuple(value for value in dict.fromkeys((f.value, *f.options))
                     if value is not None and value not in f.negated_values)
    return (f.value,) if f.value is not None else ()


def _supported(R: FactSet, subject: Id, attribute: Attribute) -> tuple[Value, ...] | None:
    """The values of a multi-valued attribute when it is established as a set: at least one member, every member
    established, the supported members' values; None otherwise (a member not established, or no member)."""
    found = members(R, subject, attribute)
    if not found or not all(established(member) for member in found):
        return None
    values = tuple(member.value for member in found if member.result is Result.SUPPORTED and member.value is not None)
    return values or None


def apart_by_controls(R: FactSet, a: Id, b: Id, attribute: Attribute, of_a: Iterable[Value],
                      of_b: Iterable[Value]) -> bool:
    """DECISIONS D220 (FINAL-V2 4.2, 3.2.3 [R:SC-B]): whether the pair controls on ``attribute`` (target.places or
    target.lesion) set ``a`` and ``b`` apart - EVERY pair control between the two objects rejected, whatever place or
    lesion it asks about, and every current member of each object covered by a rejected control asked of the other
    (each of ``of_b`` asked of ``a``, each of ``of_a`` asked of ``b``). A control that was not generated is not
    rejected.

    It is the reading for MULTI-VALUED sets (DECISIONS D235): a place list (apart_by_place), a statement's listed
    lesions (engine/pairing.py). A stored pair control names the object it asks and the value it asks about, never the
    object whose value it was (store's claim identity; the FactSet's key, engine/types.FactSet), so for a list, whose
    members 9.4's weakening may delete, which controls are "between" two objects cannot be told from the FactSet: every
    pair control asked of either object about ``attribute`` is read as one between them (fail-closed). An unrejected one
    keeps the pair together - the control of a member 9.4's weakening deleted from the other's list (the pair controls
    left as they were), and equally one another object's place made, which on a settled FactSet holds a pair 4.2's
    reading set apart (repair r2d's question Q1; DECISIONS D236, as built). A single-valued target lesion names its
    between controls itself, and apart_by_lesion reads only those (D235). So it is never more apart than 4.2's reading,
    and under 9.4's weakenings it only loses apartness: a deleted member whose control was generated removes only a
    coverage requirement and leaves its control read, and a control not rejected or a member demoted removes an
    apartness. (A deleted member whose control was never generated removes a coverage requirement that could not be met,
    so the call it was given may answer apart after the deletion - refute-r2d-r2 RD1; through apart_by_place it is
    unreachable, as claims.pair()'s rule is symmetric. What a deletion changes outside the controls - the disjointness
    of the lists, and whether a list is established - is apart_by_place's: r2d's questions Q2 and Q3, ruled by D245.)
    ValueError for an attribute no pair control asks about."""
    if attribute not in PAIR_ATTRIBUTES:
        raise ValueError(f'{attribute.value} is no attribute a pair control asks about.')
    asked = (a, b)
    if any(not rejected for (subject, about, _value), rejected in R.pair_controls.items()
           if about is attribute and subject in asked):
        return False
    return (all(R.pair_controls.get((a, attribute, value)) is True for value in of_b)
            and all(R.pair_controls.get((b, attribute, value)) is True for value in of_a))


def appraised_distinct(R: FactSet, one: Id, other: Id) -> bool:
    """DECISIONS D296: two lesions established distinct by a lesion pair claim - its claim supported and its sameness
    control rejected (settle's coherence table) - in either orientation (R.pair_controls keyed (lesion, distinct_from,
    lesion), True). Read only where 4.2's apart_by_lesion reads distinct_from, to set two lesions apart: through
    ``established_distinct``, every reader of an established distinctness (DECISIONS D300 RF-L2). A membership pair
    (D300 RF-L3) is True only as an established non-membership, the multiplicity its form presumes established too
    (``_lesion_pairs``)."""
    return (R.pair_controls.get((one, Attribute.DISTINCT_FROM, other)) is True
            or R.pair_controls.get((other, Attribute.DISTINCT_FROM, one)) is True)


# --- lesion identity: the same_as join (P5) and an established distinctness (DECISIONS D300 RF-L1, RF-L2) ----------


def _possible_ids(R: FactSet, member: Fact) -> tuple[Id, ...]:
    """The lesion ids a same_as member may name, as engine/coverage's _member_ids reads it (``possibly``): supported, its
    value; an established negation ("L1 is not the same as L2"), none; not established, its claimed value and its
    options; every lesion of the FactSet for a silent one."""
    if member.result is Result.NEGATED:
        return ()
    if member.result is Result.SUPPORTED:
        return (member.value,) if isinstance(member.value, Id) else ()
    if silent(member):
        return tuple(R.lesions)
    return tuple(dict.fromkeys(value for value in (member.value, *member.options) if isinstance(value, Id)))


@dataclass(frozen=True, slots=True)
class _Joins:
    """A FactSet's same_as join (``possibly_one_finding``): ``component``, each id a member may join to another - each
    lesion, by each member of its same_as list, to every id that member may name (``_possible_ids``), an id the
    FactSet does not hold included, either way - mapped to its component (an id joined to none is in none); ``unknown``,
    each component's ids the FactSet does not hold; ``anywhere``, whether one component holds two of them."""
    component: Mapping[Id, frozenset[Id]]
    unknown: Mapping[frozenset[Id], frozenset[Id]]
    anywhere: bool


def _joins(R: FactSet) -> _Joins:
    graph: dict[Id, list[Id]] = {}
    for holder in R.lesions:
        for member in members(R, holder, Attribute.SAME_AS):
            for other in _possible_ids(R, member):
                if other != holder:
                    graph.setdefault(holder, []).append(other)
                    graph.setdefault(other, []).append(holder)
    component: dict[Id, frozenset[Id]] = {}
    for start in graph:
        if start in component:
            continue
        seen, stack = {start}, [start]
        while stack:
            for other in graph.get(stack.pop(), ()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        for node in seen:
            component[node] = frozenset(seen)
    unknown = {found: frozenset(node for node in found if node not in R.lesions) for found in component.values()}
    return _Joins(component=component, unknown=unknown,
                  anywhere=any(len(found) >= 2 for found in unknown.values()))


# Each FactSet's same_as join, computed once (the target row reads it per statement and act; engine/coverage's _SameAs
# memoizes the bundling's per Reader, DECISIONS D248 G5's cost). Keyed by the FactSet's id, each entry holding the
# FactSet itself, so the id cannot name another FactSet while its entry stands; the _JOINS_KEPT FactSets read last, the
# one read longest ago dropped first (a dropped one is computed again). A FactSet never changes, so an entry never goes
# stale. Not a word list: it holds FactSets and their joins.
_JOINS: dict[int, tuple[FactSet, _Joins]] = {}
_JOINS_KEPT = 8


def _joins_of(R: FactSet) -> _Joins:
    entry = _JOINS.pop(id(R), None)
    if entry is None or entry[0] is not R:
        entry = (R, _joins(R))
        while len(_JOINS) >= _JOINS_KEPT:
            del _JOINS[next(iter(_JOINS))]
    _JOINS[id(R)] = entry
    return entry[1]


def possibly_one_finding(R: FactSet, one: Id, other: Id) -> bool:
    """DECISIONS D300 RF-L1 (P5: one id per distinct finding, and a same_as says two entries are one finding): whether
    same_as members, in any state that leaves them possible, may join two lesion ids - the same id; one component of the
    same_as graph, directly or through other entries (``_joins``: each member read by ``possibly``, as
    engine/coverage._SameAs.join reads it); an id the FactSet does not hold in either one's component, other than the
    id itself (4.11: it may be the other lesion); or two such ids in one component anywhere (they may be both). The
    same answer as ``coverage._SameAs(R).join((one,), (other,)) is not None``, which tests/v2 pins: one reading, two
    callers (engine/pairing cannot import engine/coverage). Read so, nothing sets the two apart by lesion
    (``established_distinct``) and no lesion pair claim is asked between them (contract/claims.same_as_joins, its
    claim-time twin over pass 1's lists in any state). Every 9.4 weakening of a member widens what it may name, so a
    weakening never turns it False: same_as stays a hold-only read (3.2.3's UNCONTROLLED)."""
    if one == other:
        return True
    joins = _joins_of(R)
    found = joins.component.get(one)
    if found is not None and other in found:
        return True
    for side in (one, other):
        reach = joins.component.get(side)
        if reach is not None and joins.unknown[reach] - {side}:
            return True
    return joins.anywhere


def established_distinct(R: FactSet, one: Id, other: Id) -> bool:
    """DECISIONS D300 RF-L2 (with RF-L1): THE reading of two lesions established distinct, which every reader of an
    established distinctness reads - 4.2's apart_by_lesion and so its callers (engine/pairing's single target row,
    engine/coverage._apart's bundling identity, engine/combination.one_stricture's D118), engine/pairing's listed,
    segment and own arms, and the separate-lesion modifier review (engine/combination.lesions_distinct, 59/XS): two
    different ids, distinct_from supported between them in either lesion's list, or a lesion pair claim established
    (``appraised_distinct``: D296, read as a written distinct_from) - and never while same_as may join them
    (``possibly_one_finding``). Two readers read pass 1's written distinct_from as pass 1's own claim, never this:
    engine/coverage._SameAs.denials (a contradiction is pass 1's own) and the event coding's distinct_from list."""
    if one == other:
        return False
    written = any(holds(member, other) for member in members(R, one, Attribute.DISTINCT_FROM)) or any(
        holds(member, one) for member in members(R, other, Attribute.DISTINCT_FROM))
    return (written or appraised_distinct(R, one, other)) and not possibly_one_finding(R, one, other)


def apart_by_lesion(R: FactSet, a: Id, b: Id) -> bool:
    """FINAL-V2 4.2 [R:SC-B], DECISIONS D235: both target lesions established (supported) and different, distinct_from
    established (supported) between them in either lesion's list - or, by DECISIONS D296, the two established distinct
    by a lesion pair claim (``appraised_distinct``) - and the lesion pair controls BETWEEN the two objects,
    as their target lesions name them, rejected: ``a`` asked about ``b``'s lesion and ``b`` about ``a``'s ("This act was
    done to lesion {L}."), (a, lb) and (b, la). target.lesion is single-valued and no 9.4 weakening deletes or changes
    it, so these two are exactly the lesion controls between the pair: a lesion control asked of either object about a
    lesion only a third object names was made for another pair and is not read (refute-r2d-r2 RL1: one unclear control
    made for (E4, E5) held the biopsy E4 against the snare E3, established apart by lesion). A control that was not
    generated is not rejected. The every-control scan (``apart_by_controls``) stays for the multi-valued sets.
    DECISIONS D300: the distinctness is ``established_distinct`` - the one reading every reader of it shares (RF-L2),
    never while same_as may join the two lesions, directly or through other entries (RF-L1)."""
    first, second = fact(R, a, Attribute.TARGET_LESION), fact(R, b, Attribute.TARGET_LESION)
    if first.result is not Result.SUPPORTED or second.result is not Result.SUPPORTED:
        return False
    la, lb = first.value, second.value
    if not isinstance(la, Id) or not isinstance(lb, Id) or la == lb:
        return False
    return (established_distinct(R, la, lb) and R.pair_controls.get((a, Attribute.TARGET_LESION, lb)) is True
            and R.pair_controls.get((b, Attribute.TARGET_LESION, la)) is True)


def apart_by_place(R: FactSet, a: Id, b: Id) -> bool:
    """FINAL-V2 4.2 [R:SC-B], DECISIONS D220 and D236: both target place sets established (every member established, at
    least one supported) and disjoint on the anatomy chain (engine/anatomy.disjoint, pairwise), and the place pair
    controls setting them apart (``apart_by_controls``): every place of each object asked of the other by a rejected
    control ("This act was done in the {place}.", both directions), and every place pair control asked of either object
    rejected, whatever place it asks about. A short list never sets anything apart: the omitted place is exactly what a
    pair control asks, one that was not generated is not rejected, and a member deleted from a list leaves its
    unrejected control read (9.4's weakening). Two deletions still set a pair apart, as the controls already do (repair
    r2d's questions Q2 and Q3, ruled by D245): a deleted member that overlapped a place of the other without being
    compatible with it (engine/anatomy: neither compatible nor disjoint), its control on the other rejected (Q2, named
    in 6a's P-MONO); and a deleted member that was not established, its control (when one was made) rejected (Q3: 9.4's
    deletion weakens an established member only, so that release is the removed doubt's own)."""
    first, second = _supported(R, a, Attribute.TARGET_PLACES), _supported(R, b, Attribute.TARGET_PLACES)
    if first is None or second is None:
        return False
    places_a = [place for place in first if isinstance(place, Landmark)]
    places_b = [place for place in second if isinstance(place, Landmark)]
    if len(places_a) != len(first) or len(places_b) != len(second):
        return False
    if not all(anatomy.disjoint(one, other) for one in places_a for other in places_b):
        return False
    return apart_by_controls(R, a, b, Attribute.TARGET_PLACES, places_a, places_b)


# --- the finding an act's target lesion stands for (DECISIONS D294 G1, D297 ENGB-1) -----------------------------------


def any_state_ids(R: FactSet, member: Fact) -> tuple[Id, ...]:
    """The lesion ids a same_as member names in ANY state (DECISIONS D294 G1): its claimed value and its options,
    whatever its result - a supported member, an established negation ("L1 is not the same as L2") and one left open
    all name their value - and every lesion of the FactSet for a silent one (an empty slot leaves every value
    possible). No state of the member, and so no verdict of pass 2 on one, narrows what it names: read so, same_as only
    widens a finding (3.2.3's UNCONTROLLED: it only joins, and joining bundles or holds)."""
    if silent(member):
        return tuple(R.lesions)
    return tuple(dict.fromkeys(value for value in (member.value, *member.options) if isinstance(value, Id)))


@dataclass(frozen=True, slots=True)
class FindingPlaces:
    """The places of the finding a lesion belongs to (``finding_places``; DECISIONS D297 ENGB-1). ``entries``: the
    finding, the lesion first (``finding``). ``members``: every place member of each entry the FactSet holds, entry by
    entry in ``entries``' order, each entry's in pass 1's order. ``unknown``: the first entry whose places are not
    established (``_supported``: no member, a member not established, or none supported) or that the FactSet does not
    hold (a dangling id); None when every entry of the finding has established places."""
    entries: tuple[Id, ...]
    members: tuple[Fact, ...]
    unknown: Id | None


def _components(R: FactSet) -> dict[Id, frozenset[Id]]:
    """Every id the same_as graph joins - each lesion linked, by each member of its same_as list, to every id that
    member names in ANY state (``any_state_ids``), an id the FactSet does not hold included, either way - mapped to its
    component; an id no member names and whose list is empty is in none (it stands alone). Built in the FactSet's
    order."""
    graph: dict[Id, list[Id]] = {}
    for holder in R.lesions:
        for member in members(R, holder, Attribute.SAME_AS):
            for other in any_state_ids(R, member):
                if other != holder:
                    graph.setdefault(holder, []).append(other)
                    graph.setdefault(other, []).append(holder)
    components: dict[Id, frozenset[Id]] = {}
    for start in graph:
        if start in components:
            continue
        seen = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for other in graph.get(node, ()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        component = frozenset(seen)
        for node in component:
            components[node] = component
    return components


# Each FactSet's findings, computed once (DECISIONS D248 G5's cost, as engine/coverage's _SameAs memoizes per Reader:
# SITE and D240's site fit read a finding per code and act and hold no Reader - a dense same_as graph at FINAL-V2 1.8's
# bounds took one assessment from 22 s to 148 s unmemoized). Keyed by the FactSet's id, each entry holding the FactSet
# itself, so the id cannot name another FactSet while its entry stands; the _FINDINGS_KEPT FactSets read last, the one
# read longest ago dropped first (a dropped one is computed again). A FactSet never changes, so an entry never goes
# stale. The engine runs one assessment per process at a time (gunicorn's sync workers, the jobs' stage processes).
_FINDINGS: dict[int, tuple[FactSet, dict[Id, frozenset[Id]], dict[Id, FindingPlaces]]] = {}
_FINDINGS_KEPT = 8


def _findings_of(R: FactSet) -> tuple[dict[Id, frozenset[Id]], dict[Id, FindingPlaces]]:
    """``R``'s components (``_components``) and its finding places read so far, computed once per FactSet; ``R``
    becomes the FactSet read last."""
    entry = _FINDINGS.pop(id(R), None)
    if entry is None or entry[0] is not R:
        entry = (R, _components(R), {})
        while len(_FINDINGS) >= _FINDINGS_KEPT:
            del _FINDINGS[next(iter(_FINDINGS))]
    _FINDINGS[id(R)] = entry
    return entry[1], entry[2]


def finding(R: FactSet, lesion: Id) -> tuple[Id, ...]:
    """The FINDING ``lesion`` belongs to (DECISIONS D294 G1, D297 ENGB-1; P5: one id per distinct finding, so the
    engine's lesion is its same_as component and a finding filed as two entries is one finding): every lesion entry a
    same_as member in ANY state (``any_state_ids``) may join to ``lesion``, directly or through other entries and in
    either direction (a member of either entry's list), together with every id such a member names that the FactSet
    does not hold (a dangling id, which the caller reads as unknown) - ``lesion`` first, then the others by number.
    Every state of a member names at least its value, so the finding never narrows with a member's state: same_as is
    read in the hold direction only. Computed from the FactSet alone, once per FactSet, so it is deterministic."""
    component = _findings_of(R)[0].get(lesion, frozenset({lesion}))
    return (lesion, *sorted(component - {lesion}, key=lambda entry: entry.number))


def finding_places(R: FactSet, lesion: Id) -> FindingPlaces:
    """The places an act whose target lesion is ``lesion`` stands at, as EVERY rule that reads an act's target lesion's
    places reads them (DECISIONS D297 ENGB-1, the class rule of D294 G1): E1j (engine/coverage._biopsy_elsewhere: the
    removed lesion's places), SITE's lesion arm (engine/evaluate._places_of), D240's site fit
    (engine/combination.site_outside) and the place SITE's explanation names (engine/questions._site_places) - one
    reading, never a copy. They are the places of every entry of the lesion's FINDING (``finding``: every lesion entry a
    same_as member in any state may join to it, directly or through other entries, either direction); and an entry
    whose places are not established, or an id the FactSet does not hold (``unknown``), leaves each such rule held and
    open - never READY, never excluded: a place nobody established may be anywhere (4.2, 4.11; P3: an empty list is
    unknown, never an absence). Read so, a same_as member only adds entries, and each entry adds established places or
    leaves the rule open, so a wider finding never releases or excludes what a narrower one held: same_as stays a
    hold-only read (3.2.3's UNCONTROLLED) and no claim, control or pass-2 request changes."""
    read = _findings_of(R)[1]
    cached = read.get(lesion)
    if cached is not None:
        return cached
    entries = finding(R, lesion)
    found: list[Fact] = []
    unknown: Id | None = None
    for entry in entries:
        held = entry in R.lesions
        if held:
            found.extend(members(R, entry, Attribute.PLACES))
        if unknown is None and (not held or _supported(R, entry, Attribute.PLACES) is None):
            unknown = entry
    places = read[lesion] = FindingPlaces(entries, tuple(found), unknown)
    return places
