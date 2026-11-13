"""The engine's types (docs/gemini-migration/FINAL-V2.md, step 0b of 8.1): the typed, text-free FactSet the coding rules
read (4.1), what a rule decides for one code (Evaluation, HeldFact, 4.4 and 4.8) and the status assess sets (Outcome).

**The boundary is typed** (FINAL-V2 4.1, 5.7 measure 5). Every value the FactSet holds is an Enum member of
contract/types.py, an Id, an IsoDate or an integer Span: never a string, so a string operation on a fact value is a type
error under ``mypy --strict``, and no field here holds document text. engine/facts.py (step 2d) builds the FactSet only
from store.textfree_v2's view of the stored row, in which every source's words are offsets and no text remains
(DECISIONS D188); wording.quote(span) slices the revision after the decision.

**Imports**: the standard library and contract/types.py's enumerations and Span, nothing else - none of the retired v1
modules (5.0), and none of contract's text modules (segment, geometry, fold, date_literals). The records are frozen
dataclasses with slots; the FactSet and an Evaluation freeze the mappings they are given (a MappingProxyType over a
copy), so no rule can change what another reads (P-DET), and are therefore not hashable.
"""
from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation.contract.types import (Attribute, FactState, Kind, Link, Precision, Reason, Result,
                                                  UnlistedWhat)
# Contract's integer span, re-exported (the explicit form mypy --strict reads) so the engine names it as the design does
# (FINAL-V2 8.1 step 0b, 4.1): one Span type, which a card's quoted words use too.
from studio.interpretation.contract.types import Span as Span

_K = TypeVar('_K')
_V = TypeVar('_V')


# --- ids, dates and values --------------------------------------------------------------------------------------------


@unique
class IdFamily(Enum):
    """The object families of pass 1's ids, by the letter that opens each id (FINAL-V2 1.4; 1.2 for units): E events, X
    sessions, N sections, L lesions, Y anatomy entries, P people, S units."""
    EVENT = 'E'
    SESSION = 'X'
    SECTION = 'N'
    LESION = 'L'
    ANATOMY = 'Y'
    PERSON = 'P'
    UNIT = 'S'


@dataclass(frozen=True, slots=True)
class Id:
    """An object's id as the engine holds it (FINAL-V2 4.1: a value is an Enum member or an Id): its family and its
    number, never a string, so a string operation on an id is a type error (5.7 measure 5). str(Id) gives pass 1's form
    ('E3', 'N0'); Id.parse reads it back. ValueError unless family is an IdFamily and number an int >= 0."""
    family: IdFamily
    number: int

    def __post_init__(self) -> None:
        if not isinstance(self.family, IdFamily) or type(self.number) is not int or self.number < 0:
            raise ValueError(f'An id is an IdFamily and an int >= 0; got ({self.family!r}, {self.number!r}).')

    def __str__(self) -> str:
        return f'{self.family.value}{self.number}'

    @classmethod
    def parse(cls, label: str) -> Id:
        """The Id pass 1 writes as ``label``: one family letter, then the number in canonical decimal digits ('E3',
        'N0'; never 'E03', 'E+3', 'E 3' or other digits than 0-9). ValueError otherwise."""
        try:
            family = IdFamily(label[:1])
            number = int(label[1:])
        except ValueError:
            raise ValueError(f'{label!r} is not an id of pass 1.') from None
        if number < 0 or str(number) != label[1:]:
            raise ValueError(f'{label!r} is not an id of pass 1.')
        return cls(family, number)


@dataclass(frozen=True, slots=True)
class IsoDate:
    """A date value (FINAL-V2 1.3: "an ISO date" at its precision - the encounter's date of service, an act's date) as
    the engine holds it: value, the date, the first day of its month or year at a coarser precision; precision: day |
    month | year. Never text; ``iso`` writes pass 1's form for display and export. ValueError unless value is a
    datetime.date (never a datetime, a str or anything else) and precision a Precision, both checked first; and when
    value is not the first day of its period at that precision."""
    value: datetime.date
    precision: Precision

    def __post_init__(self) -> None:
        if type(self.value) is not datetime.date or not isinstance(self.precision, Precision):
            raise ValueError(f'A date value is a datetime.date and a Precision; got ({self.value!r}, '
                             f'{self.precision!r}).')
        coarse_day = self.precision is not Precision.DAY and self.value.day != 1
        coarse_month = self.precision is Precision.YEAR and self.value.month != 1
        if coarse_day or coarse_month:
            raise ValueError(f'{self.value!r} is not the first day of its period at {self.precision!r}.')

    @property
    def iso(self) -> str:
        """The date as pass 1 writes it: YYYY-MM-DD, YYYY-MM or YYYY."""
        if self.precision is Precision.YEAR:
            return f'{self.value.year:04d}'
        if self.precision is Precision.MONTH:
            return f'{self.value.year:04d}-{self.value.month:02d}'
        return self.value.isoformat()


# A fact's value: an enumeration member of contract/types.py, an id or a date (FINAL-V2 4.1).
Value = Enum | Id | IsoDate


# --- the FactSet (FINAL-V2 4.1, 4.2, 1.7) -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Cited:
    """One stored source of a fact as the engine reads it (FINAL-V2 1.7 sources[]; DECISIONS D188), text-free. link:
    what the cited units are for the object (Link, 1.3). units: the span of its cited units, from the first unit's start
    to the last unit's end. at: the span of its located words (1.7 sources[].words, which store.textfree_v2 gives as
    offsets only), None when the source cites its whole units (pass 1's words ''). C-10 (4.6 condition 4) reads D's
    statement-linked target and timing words as the ``at`` spans of the statement sources of D's target and timing
    facts."""
    link: Link
    units: Span
    at: Span | None


@dataclass(frozen=True, slots=True)
class Fact:
    """One settled fact as the engine reads it (FINAL-V2 4.1: Fact(result, value, state, options, reasons, spans)), with
    the three text-free fields DECISIONS D188 adds, each empty by default, so 4.1's six-field constructor keeps working.

    result: supported | negated | contradicted | unknown | unresolved (Result; 3.3). value: the claimed value in any
    state (an Enum member, an Id or an IsoDate); None only when the slot is silent or the claim value is empty (pass 1's
    contradicted, whose values are its options) - a contradiction from a conflict doubt or K8 keeps the claimed value
    (3.3 row 1). state: the claim's FactState; None when silent. options: the other values the fact leaves possible,
    which 4.2's possibly reads beside the claimed value - a contradicted fact's sides, a doubt's readings (3.3 row 2),
    and the value of a control pass 2 did not reject (3.3 row 9, [R:HO-3]); empty for an established fact. reasons:
    Reason members (3.3). spans: the revision spans the fact rests on (its sources' whole units), for wording.quote
    after the decision.

    cited: one Cited per stored source - its link, its units' span and its located words' span. inherited_from: the
    section an act's fact was inherited from (1.5; 1.7 claim.inherited_from), None when it is the act's own slot; 4.5's
    performer row reads "D's own statement names a performer" as a performer fact that is not silent and has no
    inherited_from. counter: the spans of the evidence units of a contradicts or qualified verdict (3.2.5), quoted in
    the hold question; empty otherwise."""
    result: Result
    value: Value | None
    state: FactState | None
    options: tuple[Value, ...]
    reasons: tuple[Reason, ...]
    spans: tuple[Span, ...]
    cited: tuple[Cited, ...] = ()
    inherited_from: Id | None = None
    counter: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class Anchor:
    """An event's own statement as the engine reads it (FINAL-V2 1.4 EVENT.anchor, located): units, the spans of its
    anchor units, in order; kind_words and status_words, the spans of its kind and status words, None when pass 1 gave
    none. Read by the binding's kept-span overlap (4.8), an exclusion's citation cover (4.6 condition 4, C-10) and the
    same-anchor-unit rules (4.7)."""
    units: tuple[Span, ...]
    kind_words: Span | None
    status_words: Span | None


@dataclass(frozen=True, slots=True)
class UnlistedStatement:
    """A kept unlisted statement (FINAL-V2 3.2.6: events.unlisted {units, what, kind, session}) as the engine reads it:
    units, the spans of its units; what, act | denial | doubt (UnlistedWhat); kind, its Kind, None when the document
    names none; session, its session, None when pass 2 named no session card. It never supports, excludes or releases
    anything: five rules consume it, fail-closed (3.2.6)."""
    units: tuple[Span, ...]
    what: UnlistedWhat
    kind: Kind | None
    session: Id | None


def _frozen(mapping: Mapping[_K, _V]) -> Mapping[_K, _V]:
    return MappingProxyType(dict(mapping))


def _frozen_facts(facts: Mapping[Attribute, tuple[Fact, ...]]) -> Mapping[Attribute, tuple[Fact, ...]]:
    return MappingProxyType({attribute: tuple(values) for attribute, values in facts.items()})


def _frozen_objects(objects: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
                    ) -> Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]:
    return MappingProxyType({subject: _frozen_facts(facts) for subject, facts in objects.items()})


@dataclass(frozen=True, slots=True)
class FactSet:
    """The settled inventory as the engine reads it (FINAL-V2 4.1 R): the EventInventory row's objects (1.7), every text
    stripped - enumeration members, ids, results and integer spans only (P1, 5.7 measure 5).

    encounter: the encounter's facts by attribute. people, sections, sessions, anatomy, lesions, events: each object's
    facts by id, in pass 1's order, then by attribute (4.4 reads ``R.events``). A single-valued attribute holds one
    Fact, a multi-valued one (places, reached, stations, joins, distinct_from, same_as, and a statement's scope lists)
    one Fact per member; settle gives a silent slot its own result (3.3 row 3), and facts.py (step 2d) decides how it is
    presented. anchors: each event's Anchor. unlisted: the kept unlisted statements (3.2.6). pair_controls: for each
    pair control (3.2.3 [R:SC-B]) - the object asked, the attribute (target.places or target.lesion) and the place or
    lesion asked - whether pass 2 rejected it, which apart_by_place and apart_by_lesion read (4.2). completeness: for an
    upper EUS session whose station list is empty, the settled result of its completeness claim (3.2.2 [R:SC-B]; 4.3
    STATIONS).

    The row's doubts and claims are not here: each doubt has already acted on the facts it names (3.3 rows 1 and 2, a
    doubt's readings kept as options), and each appraisal on the fact it was about (result, options, pair_controls,
    completeness). Every mapping is frozen at construction."""
    encounter: Mapping[Attribute, tuple[Fact, ...]]
    people: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    sections: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    sessions: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    anatomy: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    lesions: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    events: Mapping[Id, Mapping[Attribute, tuple[Fact, ...]]]
    anchors: Mapping[Id, Anchor]
    unlisted: tuple[UnlistedStatement, ...]
    pair_controls: Mapping[tuple[Id, Attribute, Value], bool]
    completeness: Mapping[Id, Result]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'encounter', _frozen_facts(self.encounter))
        object.__setattr__(self, 'people', _frozen_objects(self.people))
        object.__setattr__(self, 'sections', _frozen_objects(self.sections))
        object.__setattr__(self, 'sessions', _frozen_objects(self.sessions))
        object.__setattr__(self, 'anatomy', _frozen_objects(self.anatomy))
        object.__setattr__(self, 'lesions', _frozen_objects(self.lesions))
        object.__setattr__(self, 'events', _frozen_objects(self.events))
        object.__setattr__(self, 'anchors', _frozen(self.anchors))
        object.__setattr__(self, 'unlisted', tuple(self.unlisted))
        object.__setattr__(self, 'pair_controls', _frozen(self.pair_controls))
        object.__setattr__(self, 'completeness', _frozen(self.completeness))


# --- what a rule decides (FINAL-V2 4.4, 4.6, 4.8) ---------------------------------------------------------------------


@unique
class ItemKind(Enum):
    """A held code's item (FINAL-V2 4.8): a question when its requirement is unresolved (U), an explanation when an
    established fact fails it (F)."""
    QUESTION = 'question'
    EXPLANATION = 'explanation'


@dataclass(frozen=True, slots=True)
class HeldFact:
    """One unresolved or failed requirement of a held code (FINAL-V2 4.4; the witness of 4.2): {fact, attribute,
    subject, result, kind, cause, reason, spans, rank}.

    fact: its questions.FORM key, as RANK writes it (4.8: 'conflict:<kind>', 'performed_status', 'event_entry', ...;
    pinned in engine/requirements.py, step 1f). attribute: the attribute it is about (Attribute); None for a hold that
    is about no single fact (a coding relation, member context). subject: the event, session or lesion it is about; None
    for an encounter-scope fact. result: the settled result of the fact the hold rests on (Result; 4.2's witness
    (subject, attribute, result, reason), 9.1's held_facts[].result, DECISIONS D189); None for a hold that is about no
    single fact (a coding relation, member context). kind: question | explanation (ItemKind). cause: who owns the hold
    in measurement (4.4: reading_unknown, reading_contradicted, unestablished:<reason>, appraisal:<verdict or
    coherence>, relation:<type>, unlisted, coding_rule:<id>, context_missing, date_unknown), operator data that names no
    vendor [R:MO-2]. reason: the settle reason of the fact the hold rests on (Reason); None when there is none (an
    established fact failing a coding rule). spans: the spans its item quotes. rank: its rank in RANK; None for the
    encounter-scope service_date, which RANK does not rank (4.8).

    fact and cause are CPT Studio's codes in the parameterized forms 4.4 and 4.8 write them - never document text."""
    fact: str
    attribute: Attribute | None
    subject: Id | None
    result: Result | None
    kind: ItemKind
    cause: str
    reason: Reason | None
    spans: tuple[Span, ...]
    rank: int | None


@unique
class Cover(Enum):
    """How a code covers the statement that excludes it (FINAL-V2 4.6 condition 4; 9.1 exclusion.cover): by citation,
    the only cover (C-10)."""
    CITATION = 'citation'


@dataclass(frozen=True, slots=True)
class Exclusion:
    """The statement that excludes a code (FINAL-V2 4.6; 9.1 exclusion {event, fact, cover, anchor}): event, the
    statement; fact, its deciding attribute (status, date_relation or performer: 4.6 condition 2); cover (Cover);
    anchor, the spans of the statement's anchor."""
    event: Id
    fact: Attribute
    cover: Cover
    anchor: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class Evaluation:
    """What the per-code rule decides for one code (FINAL-V2 4.4 decide: Evaluation(supporting, held_facts, bindings)).

    supporting: E*, the acts that support the code. held_facts: every unresolved or failed requirement, over every
    positive candidate of its groups [R:HO-8] (HeldFact). bindings: for each requirement group still in doubt (its
    kinds, as engine/catalogue.requirements gives it, step 1e), the candidate the item names (4.8's binding). exclusion:
    the statement that excludes the code (4.4 ``excluded(ex)``, 4.6); None unless excluded. The mapping is frozen at
    construction."""
    supporting: tuple[Id, ...]
    held_facts: tuple[HeldFact, ...]
    bindings: Mapping[tuple[Kind, ...], Id]
    exclusion: Exclusion | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'supporting', tuple(self.supporting))
        object.__setattr__(self, 'held_facts', tuple(self.held_facts))
        object.__setattr__(self, 'bindings', _frozen(self.bindings))


@unique
class Outcome(Enum):
    """The status engine/assess.py sets for a code (FINAL-V2 4.4; 9.1 codes[].status): excluded (R1, an exclusion, or a
    member's answer), needs_clarification (any held fact, or the date of service unknown: HELD in 0 and 4.8), else
    ready."""
    READY = 'ready'
    NEEDS_CLARIFICATION = 'needs_clarification'
    EXCLUDED = 'excluded'
