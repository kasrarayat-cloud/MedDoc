"""The Reading-compatible accessor layer (docs/gemini-migration/FINAL-V2.md 4.1; step 2d of 8.1): v1's names for reading
an event inventory - events.Reading and its module functions - kept over the typed, text-free FactSet, so a forked
rule body (steps 4a-4d) changes only where it read words.

- ``Reading(events, encounter_facts, ...)`` and ``Reading.of`` -> ``Reading(R)`` and ``Reading.of``: one FactSet
  (engine/facts.py), its objects in pass 1's order;
- ``usable(event, name)`` -> ``usable(reading, subject, attribute)``: the result is supported (4.1);
- ``value(event, name)`` -> ``value(reading, subject, attribute)``: the claimed value in any state (4.1); None for a
  silent or a contradicted slot;
- ``done(event)`` -> ``done(reading, event)``: 4.3 rows 2-5 (4.7: "done = 4.3 rows 2-5") - the status supported
  performed or attempted_not_completed, the effective date relation supported on_date_of_service, the effective
  performer supported documenting_team, the entry supported documenting_clinician;
- ``verified_other_time`` and ``verified_other_performer``, kept, with 4.4's names ``established_other_date`` and
  ``established_other_performer``: the effective date relation supported earlier_date or later_date; the effective
  performer supported other_clinician or other_facility;
- ``own_passages(event)`` and ``all_passages(event)`` -> ``own_spans(reading, event)`` and ``all_spans(reading,
  event)``: the spans of the event's kind, status and target facts (OWN), or of every attribute v1's ATTRIBUTES named,
  each once, in document order;
- ``anchors(reading, event)``: the event's own statement - its anchor's unit spans, each once, in document order (1.4
  EVENT.anchor);
- ``event_label``, ``lesion_words``, ``group_label`` and ``service_label`` -> ``event_label``, ``lesion_label``,
  ``group_label`` and ``service_label``: the label ids - enumeration members and object ids that wording's label tables
  render (step 3c) - never a sentence.

What v1's Reading also held and v2 does not store is not here: passages (units and spans replace them), the relations
(engine/pairing.py computes them from facts, step 3d), the open questions (the doubts acted on the facts they name, 3.3)
and every word reader (``words_of``, ``statement_text``, ``passages_of``, ``places``: 5.1-5.3).

**The text-free boundary** (P1, 5.7 measures 4 and 5): this module imports the standard library, contract/types.py and
engine's types, facts and catalogue only, reads no text, holds no word list, and returns no string; ``mypy --strict``
passes over it.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from studio.interpretation.contract.types import (Attribute, DateRelation, Device, Kind, Landmark, Owner, Performer,
                                                  Purpose, Result, SessionKind, Status)
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine.types import Anchor, Fact, FactSet, Id, Span, Value

# v1's verify.POSITIVE: a status that says the act was done, or begun (4.3 row 2).
POSITIVE: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})
# v1's events.OWN ('kind', 'status', 'target'): the attributes of the act's own statement, its target as 1.4 splits it.
TARGET: tuple[Attribute, ...] = (Attribute.TARGET_LESION, Attribute.TARGET_STRUCTURE, Attribute.TARGET_PLACES,
                                 Attribute.TARGET_ANATOMY, Attribute.TARGET_DUCT)
OWN: tuple[Attribute, ...] = (Attribute.KIND, Attribute.STATUS) + TARGET
# v1's events.ATTRIBUTES ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose'),
# as 1.4 names them: the session, the kind, the technique, the target, the date relation, the performer, the status, the
# statement's scope and the purpose.
ATTRIBUTES: tuple[Attribute, ...] = (
    (Attribute.SESSION, Attribute.KIND, Attribute.TECHNIQUE_DEVICE, Attribute.TECHNIQUE_ROUTE) + TARGET
    + (Attribute.DATE_RELATION, Attribute.PERFORMER, Attribute.STATUS, Attribute.SCOPE_BREADTH,
       Attribute.SCOPE_TARGETS, Attribute.SCOPE_SEGMENT, Attribute.SCOPE_COVERS, Attribute.SCOPE_EXCEPTS,
       Attribute.PURPOSE))
OTHER_DATES: frozenset[DateRelation] = frozenset({DateRelation.EARLIER_DATE, DateRelation.LATER_DATE})
OTHER_PERFORMERS: frozenset[Performer] = frozenset({Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY})
# The devices v1's event_label never named (its '', 'not_stated', 'other' and 'endoscope'; not_stated is an empty slot
# in v2).
UNNAMED_DEVICES: frozenset[Device] = frozenset({Device.OTHER, Device.ENDOSCOPE})


class Reading:
    """One FactSet, indexed for the forked rules (v1's events.Reading, over facts). ``events``, ``sessions``,
    ``sections``, ``lesions``, ``anatomy`` and ``people``: each family's ids in pass 1's order; ``order``: an event's
    place in that order (v1's ``order``); ``unlisted``: the kept unlisted statements (3.2.6). Read-only: the FactSet is
    frozen, and nothing here changes it."""

    __slots__ = ('facts', 'events', 'sessions', 'sections', 'lesions', 'anatomy', 'people', 'order', 'unlisted')

    def __init__(self, R: FactSet) -> None:
        self.facts = R
        self.events: tuple[Id, ...] = tuple(R.events)
        self.sessions: tuple[Id, ...] = tuple(R.sessions)
        self.sections: tuple[Id, ...] = tuple(R.sections)
        self.lesions: tuple[Id, ...] = tuple(R.lesions)
        self.anatomy: tuple[Id, ...] = tuple(R.anatomy)
        self.people: tuple[Id, ...] = tuple(R.people)
        self.order: Mapping[Id, int] = MappingProxyType({event: index for index, event in enumerate(self.events)})
        self.unlisted = R.unlisted

    @classmethod
    def of(cls, value: Reading | FactSet) -> Reading:
        """``value`` itself when it is a Reading, else a Reading of the FactSet (v1's Reading.of)."""
        return value if isinstance(value, Reading) else cls(value)

    def fact(self, subject: Id | None, attribute: Attribute) -> Fact:
        """facts.fact over this FactSet: the one Fact of a single-valued attribute (SILENT for what it does not hold)."""
        return facts_.fact(self.facts, subject, attribute)

    def members(self, subject: Id | None, attribute: Attribute) -> tuple[Fact, ...]:
        """facts.members over this FactSet: the members of a multi-valued attribute (() for none)."""
        return facts_.members(self.facts, subject, attribute)

    def anchor(self, event: Id) -> Anchor | None:
        """The event's Anchor (its own statement's units and its kind and status words' spans), None for an id the
        FactSet does not hold."""
        return self.facts.anchors.get(event)


# --- reading one object --------------------------------------------------------------------------------------------------


def usable(reading: Reading, subject: Id | None, attribute: Attribute) -> bool:
    """v1's usable over facts: the attribute's result is supported (4.1). A multi-valued attribute is usable when one of
    its members is."""
    return any(member.result is Result.SUPPORTED for member in _all(reading, subject, attribute))


def value(reading: Reading, subject: Id | None, attribute: Attribute) -> Value | None:
    """v1's value over facts: the claimed value in any state (4.1) - supported, negated, doubted or unresolved alike;
    None for a silent slot or a contradicted one (whose values are its options)."""
    return reading.fact(subject, attribute).value


def holds(reading: Reading, subject: Id | None, attribute: Attribute, wanted: Value) -> bool:
    """facts.holds on one attribute of ``subject``: result supported with the value ``wanted`` (for a multi-valued
    attribute, one member)."""
    return any(facts_.holds(member, wanted) for member in _all(reading, subject, attribute))


def _all(reading: Reading, subject: Id | None, attribute: Attribute) -> tuple[Fact, ...]:
    family = subject.family if subject is not None else None
    domain = facts_.DOMAINS.get((family, attribute))
    if domain is not None and domain.many:
        return reading.members(subject, attribute)
    return (reading.fact(subject, attribute),)


def done(reading: Reading, event: Id) -> bool:
    """4.3 rows 2-5 (4.7: "done = 4.3 rows 2-5"), v1's done over facts: the status supported performed or begun
    (attempted_not_completed), the effective date relation supported on_date_of_service, the effective performer
    supported documenting_team, and the entry supported documenting_clinician - each established, never a default. What
    a reportable act and a session's examination are (4.3 row 7, 4.7)."""
    status = reading.fact(event, Attribute.STATUS)
    return (status.result is Result.SUPPORTED and isinstance(status.value, Status) and status.value in POSITIVE
            and holds(reading, event, Attribute.DATE_RELATION, DateRelation.ON_DATE_OF_SERVICE)
            and holds(reading, event, Attribute.PERFORMER, Performer.DOCUMENTING_TEAM)
            and holds(reading, event, Attribute.ENTRY, Owner.DOCUMENTING_CLINICIAN))


def verified_other_time(reading: Reading, event: Id) -> bool:
    """v1's name: the effective date relation is established as another date (supported earlier_date or later_date)."""
    found = reading.fact(event, Attribute.DATE_RELATION)
    return found.result is Result.SUPPORTED and isinstance(found.value, DateRelation) and found.value in OTHER_DATES


def verified_other_performer(reading: Reading, event: Id) -> bool:
    """v1's name: the effective performer is established as another (supported other_clinician or other_facility)."""
    found = reading.fact(event, Attribute.PERFORMER)
    return (found.result is Result.SUPPORTED and isinstance(found.value, Performer)
            and found.value in OTHER_PERFORMERS)


# FINAL-V2 4.4's names for the same two readings.
established_other_date = verified_other_time
established_other_performer = verified_other_performer


def _ordered(spans: Iterable[Span]) -> tuple[Span, ...]:
    return tuple(sorted(set(spans)))


def own_spans(reading: Reading, event: Id, attributes: Sequence[Attribute] = OWN) -> tuple[Span, ...]:
    """v1's own_passages over facts: the spans of the event's ``attributes`` facts (OWN: its kind, status and target),
    each once, in document order - what a question quotes and a support shows."""
    return _ordered(span for attribute in attributes for member in _all(reading, event, attribute)
                    for span in member.spans)


def all_spans(reading: Reading, event: Id) -> tuple[Span, ...]:
    """v1's all_passages over facts: own_spans over every attribute v1's ATTRIBUTES named."""
    return own_spans(reading, event, ATTRIBUTES)


def anchors(reading: Reading, event: Id) -> tuple[Span, ...]:
    """v1's anchors over facts: the event's own statement in the document - its anchor's unit spans, each once, in
    document order (FINAL 7.11 ``source``, 7.8 the unresolved items' evidence; 1.4 EVENT.anchor). () for an id the
    FactSet does not hold."""
    found = reading.anchor(event)
    return _ordered(found.units) if found is not None else ()


# --- the label ids (CPT Studio's words over the values, rendered by wording, step 3c) ------------------------------------


@dataclass(frozen=True, slots=True)
class EventLabel:
    """What v1's event_label named, as ids (reconcile.describe_act's form): ``kind``, the act's catalogue kind (None for
    an examination, or for kind other); ``family``, the session family an examination is the service of (None for
    another act); ``device``, its supported device where v1 named one; ``lesion``, its supported target lesion; else
    ``place``, its first supported target place."""
    kind: Kind | None
    family: SessionKind | None
    device: Device | None
    lesion: Id | None
    place: Landmark | None


@dataclass(frozen=True, slots=True)
class LesionLabel:
    """What v1's lesion_words named, as ids: the lesion (wording quotes its own description, by its span) and its first
    supported place."""
    lesion: Id
    place: Landmark | None


@dataclass(frozen=True, slots=True)
class GroupLabel:
    """What v1's group_label named, as ids: the service (a session family) for a group of examination kinds, else the
    group's kinds, each once."""
    family: SessionKind | None
    kinds: tuple[Kind, ...]


def _supported(found: Fact) -> Value | None:
    return found.value if found.result is Result.SUPPORTED else None


def _first_place(reading: Reading, subject: Id, attribute: Attribute) -> Landmark | None:
    for member in reading.members(subject, attribute):
        if member.result is Result.SUPPORTED and isinstance(member.value, Landmark):
            return member.value
    return None


def event_label(reading: Reading, event: Id) -> EventLabel:
    """v1's event_label as ids (EventLabel): the catalogue kind of the act's claimed kind with its SUPPORTED purpose
    (catalogue.catalogue_kind), or for an examination its session's family; the supported device unless v1 left it
    unnamed; the supported lesion, else the first supported place."""
    kind = reading.fact(event, Attribute.KIND).value
    purpose = _supported(reading.fact(event, Attribute.PURPOSE))
    family = facts_.session_family(reading.facts, event)
    examination = kind is Kind.EXAMINATION
    named = (catalogue.catalogue_kind(kind, purpose if isinstance(purpose, Purpose) else None)
             if isinstance(kind, Kind) and not examination else None)
    device = _supported(reading.fact(event, Attribute.TECHNIQUE_DEVICE))
    lesion = _supported(reading.fact(event, Attribute.TARGET_LESION))
    return EventLabel(kind=named, family=family if examination else None,
                      device=device if isinstance(device, Device) and device not in UNNAMED_DEVICES else None,
                      lesion=lesion if isinstance(lesion, Id) else None,
                      place=None if isinstance(lesion, Id) else _first_place(reading, event, Attribute.TARGET_PLACES))


def lesion_label(reading: Reading, lesion: Id) -> LesionLabel:
    """v1's lesion_words as ids (LesionLabel)."""
    return LesionLabel(lesion=lesion, place=_first_place(reading, lesion, Attribute.PLACES))


def group_label(link: catalogue.CodeLink, group: Sequence[Kind]) -> GroupLabel:
    """v1's group_label as ids (GroupLabel): the session's service for a group of examination kinds, else its kinds."""
    if group and all(kind is Kind.EXAMINATION for kind in group):
        return GroupLabel(family=link.family, kinds=())
    return GroupLabel(family=None, kinds=tuple(dict.fromkeys(group)))


def service_label(family: SessionKind) -> SessionKind:
    """v1's service_label as an id: the family whose service wording names."""
    return family
