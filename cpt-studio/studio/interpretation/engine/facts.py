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
qualifiers is read as qualified, DECISIONS D186), each once, in the verdict's order. An anchor's ``units`` are its
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

**The predicates** (4.2): ``holds``, ``denied``, ``established``, ``possibly`` - with the status arm: a status that is
not established leaves every status possible [R:HO-1][R:HO-3] - and ``possibly_of_family``, the kind arm a statement
(4.5) and an exclusion's condition 5 (4.6) read: a kind that is not established leaves every kind of its session's
family possible - requirements_table.FAMILY_KINDS, the one table K2 reads too (DECISIONS D191), never computed here -
and every kind when the session or its kind is not established [R:HO-5]. As a candidate for a code (4.4) an act's kind
is read by ``possibly`` alone: its claimed value, its readings and its control's sibling. ``apart_by_lesion``
and ``apart_by_place`` set two objects apart only on established, different (disjoint) targets AND rejected pair
controls in both directions: a short list never sets anything apart, and a pair control that was not generated is not
rejected [R:SC-B].

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
engine's types, anatomy and requirements_table only - no retired v1 module, none of contract's text modules, not
store.py (its caller hands it store.textfree_v2's view) - and holds no word list (every module-level collection holds
enumeration members). No public function here returns a string (the private readers of the stored JSON do), and
``mypy --strict`` passes over it. A row this builder cannot read whole raises FactSetError (a ValueError); nothing is
ever read as an empty inventory.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
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
from studio.interpretation.engine import anatomy, requirements_table
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
# The timing facts L1 re-judges at assess and read time (an inherited date relation is stored per act, 1.5).
TIMING: frozenset[tuple[IdFamily, Attribute]] = frozenset({(_E, _A.DATE_RELATION), (_N, _A.OCCASION)})

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
        a qualifier is read as qualified (DECISIONS D186). An evidence unit the row does not have locates nothing and
        is skipped (the verdict demotes all the same, 3.2.5). Empty for any other verdict, or for no appraisal."""
        if appraisal is None:
            return ()
        record = _mapping(appraisal, where)
        raw = _field(record, 'verdict', where)
        qualifiers = tuple(_enum(Qualifier2, item, f'{where}.qualifiers')
                           for item in _sequence(_field(record, 'qualifiers', where), f'{where}.qualifiers'))
        evidence = _sequence(_field(record, 'evidence', where), f'{where}.evidence')
        verdict = None if raw is None else _enum(VerdictValue, raw, f'{where}.verdict')
        countered = verdict is VerdictValue.CONTRADICTS or verdict is VerdictValue.QUALIFIED or (
            verdict is VerdictValue.SUPPORTS and bool(qualifiers))
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
    exactly once, each multi-valued one as its members in order (none when its list is empty)."""
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
        if domain is None or attribute not in (Attribute.TARGET_PLACES, Attribute.TARGET_LESION):
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
    return FactSet(encounter=encounter, people=objects[_P], sections=objects[_N], sessions=objects[_X],
                   anatomy=objects[_Y], lesions=objects[_L], events=objects[_E], anchors=anchors,
                   unlisted=_unlisted(events, context), pair_controls=_pair_controls(context),
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
    fail-closed doubt arm: a doubt is never an absence."""
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
    exclusion's condition 5)."""
    found = fact(R, event, Attribute.KIND)
    if of_family:
        return frozenset(kind for kind in Kind if possibly_of_family(R, event, kind))
    return frozenset(kind for kind in Kind if possibly(found, kind))


def _supported(R: FactSet, subject: Id, attribute: Attribute) -> tuple[Value, ...] | None:
    """The values of a multi-valued attribute when it is established as a set: at least one member, every member
    established, the supported members' values; None otherwise (a member not established, or no member)."""
    found = members(R, subject, attribute)
    if not found or not all(established(member) for member in found):
        return None
    values = tuple(member.value for member in found if member.result is Result.SUPPORTED and member.value is not None)
    return values or None


def apart_by_lesion(R: FactSet, a: Id, b: Id) -> bool:
    """FINAL-V2 4.2 [R:SC-B]: both target lesions established (supported) and different, distinct_from established
    (supported) between them in either lesion's list, and the lesion pair controls rejected in both directions ("This
    act was done to lesion {L}." asked of each object about the other's lesion). A pair control that was not generated
    is not rejected."""
    first, second = fact(R, a, Attribute.TARGET_LESION), fact(R, b, Attribute.TARGET_LESION)
    if first.result is not Result.SUPPORTED or second.result is not Result.SUPPORTED:
        return False
    la, lb = first.value, second.value
    if not isinstance(la, Id) or not isinstance(lb, Id) or la == lb:
        return False
    distinct = any(holds(member, lb) for member in members(R, la, Attribute.DISTINCT_FROM)) or any(
        holds(member, la) for member in members(R, lb, Attribute.DISTINCT_FROM))
    return (distinct and R.pair_controls.get((a, Attribute.TARGET_LESION, lb)) is True
            and R.pair_controls.get((b, Attribute.TARGET_LESION, la)) is True)


def apart_by_place(R: FactSet, a: Id, b: Id) -> bool:
    """FINAL-V2 4.2 [R:SC-B]: both target place sets established (every member established, at least one supported)
    and disjoint on the anatomy chain (engine/anatomy.disjoint, pairwise), and every pair control asking one object
    about a place of the other rejected ("This act was done in the {place}.", both directions). A short list never
    sets anything apart: the omitted place is exactly what a pair control asks, and one that was not generated is not
    rejected."""
    first, second = _supported(R, a, Attribute.TARGET_PLACES), _supported(R, b, Attribute.TARGET_PLACES)
    if first is None or second is None:
        return False
    places_a = [place for place in first if isinstance(place, Landmark)]
    places_b = [place for place in second if isinstance(place, Landmark)]
    if len(places_a) != len(first) or len(places_b) != len(second):
        return False
    if not all(anatomy.disjoint(one, other) for one in places_a for other in places_b):
        return False
    return (all(R.pair_controls.get((a, Attribute.TARGET_PLACES, place)) is True for place in places_b)
            and all(R.pair_controls.get((b, Attribute.TARGET_PLACES, place)) is True for place in places_a))
